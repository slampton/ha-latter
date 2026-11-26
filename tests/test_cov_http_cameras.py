"""Targeted real-HA 2026.11 coverage tests for HTTP views, signing, and camera streaming."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

from aiohttp import MultipartReader, web
from homeassistant.components import camera as ha_camera, ffmpeg as ha_ffmpeg
from homeassistant.helpers import aiohttp_client as ha_aiohttp_client
from homeassistant.setup import async_setup_component
from PIL import Image, ImageDraw, ImageFont
import pytest

from custom_components.latter.cameras import (
    capabilities as cap_mod,
    stream_hub as hub_mod,
    transcode as transcode_mod,
)
from custom_components.latter.cameras.capabilities import (
    _resolve_platform_and_stream_kind,
    resolve_camera_capabilities,
)
from custom_components.latter.cameras.stream_hub import (
    LatterCameraStreamHub,
    async_shutdown_camera_stream_hub,
)
from custom_components.latter.cameras.transcode import (
    CameraFetchError,
    CameraIngest,
    CameraIngestLimitError,
    CameraSubscriber,
    CameraTranscodeError,
    LoopbackMjpegTransport,
    MjpegStreamParser,
    _apply_rotation,
    _draw_centered_line,
    _load_tile_font,
    build_ffmpeg_video_cmd,
    compose_grid_frame,
    compute_contain_size,
    format_mjpeg_chunk,
    inspect_jpeg_header,
    transcode_camera_frame,
)
from custom_components.latter.const import (
    CONF_CAMERA_CONFIGS,
    CONF_CAMERA_ENTITIES,
    CONF_WALLPAPER_MODE,
    DAY_NIGHT_SKY_NATIVE_URL,
    DAY_NIGHT_SKY_PRESET_ID,
)
from custom_components.latter.http import (
    camera_views,
    proxy_views,
    signing as signing_mod,
    wallpaper_views,
)
from custom_components.latter.http.camera_views import (
    LatterCameraAudioStreamView,
    LatterCameraGridView,
    LatterCameraSnapshotView,
    LatterCameraStreamView,
    _async_pipe_ffmpeg_audio,
    _async_stream_mjpeg_iterator,
    _AudioStreamConfig,
    _build_camera_audio_ffmpeg_cmd,
    _clamp_video_query_dim,
    _is_allowed_stream_url,
    _parse_grid_requested_cameras,
    _terminate_ffmpeg_process,
    async_shutdown_doorbell_streams,
)
from custom_components.latter.http.proxy_views import (
    LatterArtworkTranscoderView,
    _is_private_or_loopback_client,
    _parse_dimensions_and_shape,
    _resolve_artwork_candidates_and_path,
)
from custom_components.latter.http.signing import UrlSigner, camera_allowlist_hash
from custom_components.latter.http.wallpaper_views import (
    LatterWallpaperProxyView,
    LatterWallpaperUploadView,
    _parse_multipart_float,
    _transcode_media_preview_jpeg,
    _transcode_photo_to_baseline_jpeg,
)
from custom_components.latter.hub_registry import (
    get_domain_data,
    get_global_config,
    register_studio_subscriber,
)
from custom_components.latter.media_cache import (
    MAX_MULTIPART_PARTS,
    MAX_UPSTREAM_IMAGE_BYTES,
    clear_http_caches,
)
from custom_components.latter.wallpapers.models import get_wallpaper_root
from custom_components.latter.wallpapers.store import (
    async_refresh_wallpaper_cache,
    delete_photo,
)
from tests.helpers import (
    install_camera_mocks,
    make_jpeg_bytes,
    mock_clientsession_get,
    register_entity,
)


def _make_get_request(url: str, *, remote: str | None = None) -> Any:
    parsed = urlsplit(url)
    query = {k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
    return SimpleNamespace(query=query, headers={}, remote=remote)


def _make_sof0_stub(width: int = 320, height: int = 192) -> bytes:
    sof0 = (
        b"\xff\xc0"
        + (17).to_bytes(2, "big")
        + b"\x08"
        + height.to_bytes(2, "big")
        + width.to_bytes(2, "big")
        + b"\x03"
        + b"\x01\x22\x00"
        + b"\x02\x11\x01"
        + b"\x03\x11\x01"
    )
    sos = b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x00"
    return sof0 + sos


class _MockStreamContent:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    async def iter_chunked(self, _size: int = 65536) -> AsyncIterator[bytes]:
        for chunk in self._chunks:
            yield chunk


class _MockHttpResp:
    def __init__(
        self,
        *,
        status: int = 200,
        chunks: list[bytes] | None = None,
        content_length: int | None = None,
    ) -> None:
        self.status = status
        self.content_length = content_length
        self.content = _MockStreamContent(chunks if chunks is not None else [])

    async def __aenter__(self) -> _MockHttpResp:
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        return None


class _MultipartPart:
    def __init__(
        self,
        name: str,
        *,
        text_val: str = "",
        file_bytes: bytes | None = None,
        filename: str = "photo.jpg",
    ) -> None:
        self.name = name
        self._text_val = text_val
        self._file_bytes = file_bytes
        self.filename = filename
        self._offset = 0
        self.released = False

    async def read_chunk(self, size: int = 65536) -> bytes:
        buf = (
            self._file_bytes
            if self._file_bytes is not None
            else self._text_val.encode("utf-8")
        )
        if self._offset >= len(buf):
            return b""
        chunk = buf[self._offset : self._offset + size]
        self._offset += size
        return chunk

    async def release(self) -> None:
        self.released = True


class _NestedMultipartStub(MultipartReader):
    """Lightweight `MultipartReader` subclass for exercising nested-part skip branches."""

    def __init__(self) -> None:
        self.released = False

    async def release(self) -> None:
        self.released = True


class _MultipartReaderStub:
    def __init__(self, parts: list[Any]) -> None:
        self._parts = list(parts)

    async def next(self) -> Any:
        return self._parts.pop(0) if self._parts else None


class _MultipartRequestStub:
    def __init__(
        self,
        *,
        parts: list[Any],
        query: dict[str, str] | None = None,
        is_admin: bool = True,
        content_length: int | None = None,
    ) -> None:
        self._user = SimpleNamespace(is_admin=is_admin)
        self._parts = parts
        self.query = query or {}
        self.content_length = content_length

    def get(self, key: str, default: Any = None) -> Any:
        if key == "hass_user":
            return self._user
        return default

    async def multipart(self) -> _MultipartReaderStub:
        return _MultipartReaderStub(self._parts)


class _FakeStdoutPipe:
    def __init__(
        self,
        chunks: list[bytes],
        *,
        stall_event: asyncio.Event | None = None,
        on_read: Any = None,
    ) -> None:
        self._chunks = list(chunks)
        self._stall_event = stall_event
        self._on_read = on_read

    async def read(self, _n: int = 4096) -> bytes:
        if self._on_read is not None:
            self._on_read()
        if self._chunks:
            return self._chunks.pop(0)
        if self._stall_event is not None:
            await self._stall_event.wait()
        return b""


class _FakeSubproc:
    def __init__(
        self,
        chunks: list[bytes] | None = None,
        *,
        has_stdout: bool = True,
        returncode: int | None = None,
        hang_terminate: bool = False,
        raise_lookup: bool = False,
        stall_event: asyncio.Event | None = None,
        on_read: Any = None,
    ) -> None:
        self.stdout = (
            _FakeStdoutPipe(chunks or [], stall_event=stall_event, on_read=on_read)
            if has_stdout
            else None
        )
        self.returncode = returncode
        self.terminated = False
        self.killed = False
        self._hang_terminate = hang_terminate
        self._raise_lookup = raise_lookup
        self._wait_gate = asyncio.Event()

    def terminate(self) -> None:
        if self._raise_lookup:
            raise ProcessLookupError("process already exited")
        self.terminated = True
        if not self._hang_terminate:
            self.returncode = 0
            self._wait_gate.set()

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9
        self._wait_gate.set()

    async def wait(self) -> int:
        if self.returncode is not None:
            return self.returncode
        await self._wait_gate.wait()
        return self.returncode if self.returncode is not None else 0


@pytest.mark.asyncio
async def test_camera_capabilities_edge_branches(hass: Any) -> None:
    """Exercise registry platform lookup, bool/string audio attrs, and invalid supported_features."""
    register_entity(hass, "camera.mjpeg_reg", platform="mjpeg")
    assert (
        _resolve_platform_and_stream_kind(
            hass, "camera.mjpeg_reg", "", {}, (False, False)
        )
        == "mjpeg"
    )
    assert (
        _resolve_platform_and_stream_kind(
            hass, "camera.unregistered", "", {}, (False, False)
        )
        == "snapshot"
    )

    hass.states.async_set("camera.aud_bool_true", "idle", {"has_audio": True})
    hass.states.async_set("camera.aud_bool_false", "idle", {"audio": False})
    hass.states.async_set("camera.aud_str_yes", "idle", {"has_audio": "yes"})
    hass.states.async_set("camera.aud_str_no", "idle", {"audio": "0"})
    hass.states.async_set(
        "camera.bad_features", "idle", {"supported_features": "not-an-int"}
    )

    assert resolve_camera_capabilities(hass, "camera.aud_bool_true")["has_audio"] is True
    assert resolve_camera_capabilities(hass, "camera.aud_bool_false")["has_audio"] is False
    assert resolve_camera_capabilities(hass, "camera.aud_str_yes")["has_audio"] is True
    assert resolve_camera_capabilities(hass, "camera.aud_str_no")["has_audio"] is False

    bad_cap = resolve_camera_capabilities(hass, "camera.bad_features")
    assert bad_cap["stream_kind"] == "snapshot"
    assert bad_cap["has_audio"] is False
    assert cap_mod._CAMERA_FEATURE_STREAM == 2


@pytest.mark.asyncio
async def test_url_signing_edge_branches(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise UrlSigner LAN invalidation, network error fallback, default ports, and empty guards."""
    signer = UrlSigner(hass, "sub_signing_test", b"k" * 32)
    domain_data = get_domain_data(hass)
    domain_data.probed_lan_ip = "192.168.10.42"
    signer._cached_lan_base_url = "http://192.168.10.42:8123"
    signer._cached_lan_base_url_mono = 123.0

    signer.invalidate_lan_base_url()
    assert signer._cached_lan_base_url is None
    assert signer._cached_lan_base_url_mono == 0.0
    assert domain_data.probed_lan_ip == ""

    async def _fail_source_ip(_hass: Any) -> str:
        raise RuntimeError("adapter unavailable")

    monkeypatch.setattr(signing_mod.ha_network, "async_get_source_ip", _fail_source_ip)
    primed = await signer.async_prime_lan_base_url()
    assert primed.startswith("http")

    # Default HTTP/HTTPS ports omit `:80` and `:443`
    monkeypatch.setattr(
        signing_mod, "get_url", lambda *_a, **_kw: "http://10.20.30.40:80"
    )
    signer.invalidate_lan_base_url()
    assert signer.get_lan_base_url() == "http://10.20.30.40"

    monkeypatch.setattr(
        signing_mod, "get_url", lambda *_a, **_kw: "https://10.20.30.40:443"
    )
    signer.invalidate_lan_base_url()
    assert signer.get_lan_base_url() == "https://10.20.30.40"

    # Empty-input guards and native Day & Night Sky URL
    assert signer.build_camera_snapshot_url("dev", "", 466, 466, "circle") == ""
    assert signer.build_camera_snapshot_url("dev", None, 466, 466, "circle") == ""
    assert (
        signer.build_camera_allowlist_snapshot_url(
            "dev", ["  ", ""], None, 466, 466, "circle"
        )
        == ""
    )
    assert signer.build_camera_audio_url("dev", "  ", "light") == ""
    assert signer.build_wallpaper_url("dev", "   ", 466, 466, "square") == ""
    assert (
        signer.build_wallpaper_url(
            "dev", DAY_NIGHT_SKY_PRESET_ID, 466, 466, "square", mode="wallpaper"
        )
        == DAY_NIGHT_SKY_NATIVE_URL
    )
    assert signer.build_media_preview_url("", "pic.jpg") == ""
    assert signer.build_media_preview_url("local", "   ") == ""


def test_camera_transcode_edge_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise JPEG header scanner, rotation/quality paths, grid fallbacks, FFmpeg args, and MJPEG buffers."""
    # compute_contain_size non-positive source guards
    assert compute_contain_size(0, 100, 466, 466) == (464, 464)
    assert compute_contain_size(100, -1, 320, 240) == (320, 240)

    # inspect_jpeg_header edge cases
    assert inspect_jpeg_header(b"tiny") == (False, 0, 0)
    assert inspect_jpeg_header(b"NOT_JPEG_DATA_AT_ALL") == (False, 0, 0)

    sof_body = _make_sof0_stub(320, 192)
    # Non-0xFF padding byte + RST0 marker before SOF0
    padded = b"\xff\xd8\x00\xff\xd0" + sof_body + b"\xff\xd9"
    assert inspect_jpeg_header(padded) == (True, 320, 192)
    # Trailing 0xFF run reaches end of buffer
    assert inspect_jpeg_header(b"\xff\xd8" + b"\xff" * 20) == (False, 0, 0)
    # SOS before any SOF terminates scan cleanly
    assert inspect_jpeg_header(b"\xff\xd8\xff\xda" + b"\x00" * 20) == (False, 0, 0)
    # Segment length < 2 aborts scan cleanly
    assert inspect_jpeg_header(b"\xff\xd8\xff\xe0\x00\x01" + b"\x00" * 20) == (
        False,
        0,
        0,
    )
    # Valid APP0 segment ending at tail with no SOF falls through to (False, 0, 0)
    assert inspect_jpeg_header(b"\xff\xd8\xff\xe0\x00\x10" + b"\x00" * 16) == (
        False,
        0,
        0,
    )

    # Rotations 0/180/270 and explicit quality
    sample_img = Image.new("RGB", (64, 32), (10, 20, 30))
    assert _apply_rotation(sample_img, 0) is sample_img
    assert _apply_rotation(sample_img, 180).size == (64, 32)
    assert _apply_rotation(sample_img, 270).size == (32, 64)

    raw_rect = make_jpeg_bytes(320, 192)
    out_180 = transcode_camera_frame(raw_rect, 320, 240, rot=180, quality=75)
    assert inspect_jpeg_header(out_180)[1:] == (320, 192)
    out_270 = transcode_camera_frame(
        raw_rect, 320, 320, rot=270, fast_live=False, quality=120
    )
    assert inspect_jpeg_header(out_270)[1:] == (192, 320)

    # _load_tile_font TypeError fallback
    orig_load_default = ImageFont.load_default

    def _no_size_load_default(*args: Any, **kwargs: Any) -> Any:
        if kwargs:
            raise TypeError("size kwarg unsupported")
        return orig_load_default(*args)

    _load_tile_font.cache_clear()
    try:
        with monkeypatch.context() as mp:
            mp.setattr(transcode_mod.ImageFont, "load_default", _no_size_load_default)
            fallback_font = _load_tile_font(16)
            assert fallback_font is not None
    finally:
        _load_tile_font.cache_clear()

    # _draw_centered_line fallback when textbbox raises TypeError
    canvas = Image.new("RGB", (120, 80), (0, 0, 0))
    real_draw = ImageDraw.Draw(canvas)
    fallback_texts: list[tuple[Any, ...]] = []

    class _DrawNoBbox:
        def textbbox(self, *_args: Any, **_kwargs: Any) -> Any:
            raise TypeError("textbbox unsupported")

        def text(self, pos: tuple[int, int], txt: str, **kw: Any) -> None:
            fallback_texts.append((pos, txt, kw))
            real_draw.text(pos, txt, **kw)

    _draw_centered_line(_DrawNoBbox(), 60, 40, "Offline", ImageFont.load_default())  # type: ignore[arg-type]
    assert len(fallback_texts) == 1
    assert fallback_texts[0][1] == "Offline"

    # compose_grid_frame with fit="fill" and empty label offline quadrant
    grid_fill = compose_grid_frame([raw_rect, None], ["Porch", ""], 466, 466, fit="fill")
    assert inspect_jpeg_header(grid_fill)[1:] == (464, 464)

    # build_ffmpeg_video_cmd rot=180, rot=270, and invalid URL schemes
    cmd_180 = build_ffmpeg_video_cmd(
        "ffmpeg", "rtsp://10.0.0.1/s", 320, 240, 10, rot=180
    )
    assert "hflip,vflip" in cmd_180[cmd_180.index("-vf") + 1]
    cmd_270 = build_ffmpeg_video_cmd(
        "ffmpeg", "rtsp://10.0.0.1/s", 320, 240, 10, rot=270
    )
    assert "transpose=2" in cmd_270[cmd_270.index("-vf") + 1]
    with pytest.raises(ValueError, match="Unsupported camera stream URL scheme"):
        build_ffmpeg_video_cmd("ffmpeg", "file:///etc/passwd", 320, 240, 10)
    with pytest.raises(ValueError, match="Unsupported camera stream URL scheme"):
        build_ffmpeg_video_cmd("ffmpeg", "-i rtsp://10.0.0.1/s", 320, 240, 10)

    # MjpegStreamParser edge cases
    parser = MjpegStreamParser(max_frame_bytes=64)
    assert parser.feed(b"") == []
    assert parser.feed(b"X" * 5000) == []
    assert len(parser._buf) == 64

    parser_soi = MjpegStreamParser()
    mini_frame = b"\xff\xd8" + sof_body + b"\xff\xd9"
    assert parser_soi.feed(b"garbage_prefix" + mini_frame) == [mini_frame]

    parser_big = MjpegStreamParser(max_frame_bytes=32)
    assert parser_big.feed(b"\xff\xd8" + b"\x00" * 64) == []
    assert len(parser_big._buf) == 0

    # LoopbackMjpegTransport overflow drop & close on full queue
    q: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=1)
    transport = LoopbackMjpegTransport(q)
    assert transport.is_closing() is False
    transport.write(b"first")
    transport.write(b"second")
    assert q.qsize() == 1
    transport.close()
    assert transport.is_closing() is True
    assert q.get_nowait() is None

    # CameraIngest.desired_profile with empty subscribers
    empty_ingest = CameraIngest(entity_id="camera.empty")
    assert empty_ingest.desired_profile() == (480, 320, 10, "contain", 0)


@pytest.mark.asyncio
async def test_proxy_views_artwork_and_client_ip_branches(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise query parsing, LAN IP classification, entity media_image cache/limits, and HTTP error paths."""
    clear_http_caches()
    # 1) Pure helpers
    assert _parse_dimensions_and_shape(
        _make_get_request("/x?w=not_int&h=bad"), 466, 466
    ) == (466, 466, False, "square")
    assert _is_private_or_loopback_client(_make_get_request("/x", remote=None)) is True
    assert (
        _is_private_or_loopback_client(_make_get_request("/x", remote="127.0.0.1"))
        is True
    )
    assert (
        _is_private_or_loopback_client(_make_get_request("/x", remote="fe80::1%eth0"))
        is True
    )
    assert (
        _is_private_or_loopback_client(
            _make_get_request("/x", remote="::ffff:192.168.1.5")
        )
        is True
    )
    assert (
        _is_private_or_loopback_client(_make_get_request("/x", remote="::ffff:8.8.8.8"))
        is False
    )
    assert (
        _is_private_or_loopback_client(_make_get_request("/x", remote="93.184.216.34"))
        is False
    )
    assert (
        _is_private_or_loopback_client(_make_get_request("/x", remote="not-an-ip"))
        is False
    )

    entry, _sys_obj, coord = await setup_latter_hub(hass)
    try:
        view = LatterArtworkTranscoderView(hass)
        art_sig = coord.sign_payload_resource("artwork|466|466|square")

        # Unknown target device -> 404; invalid signature -> 403
        r_unknown = await view.get(
            _make_get_request("/api/latter/artwork/unknown_dev?w=466&h=466"),
            "unknown_dev",
        )
        assert r_unknown.status == 404

        r_bad_sig = await view.get(
            _make_get_request(
                f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig=bad"
            ),
            coord.device_slug,
        )
        assert r_bad_sig.status == 403

        # Missing speaker state + no fallback pic -> 404
        hass.states.async_remove(coord.active_speaker)
        coord.last_valid_raw_pic = ""
        r_no_art = await view.get(
            _make_get_request(
                f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"
            ),
            coord.device_slug,
        )
        assert r_no_art.status == 404

        # Fallback to coord.last_valid_raw_pic when speaker has no picture attr
        coord.last_valid_raw_pic = "/api/media_player_proxy/fallback_art?t=1"
        cands, pic_path = _resolve_artwork_candidates_and_path(hass, coord)
        assert coord.active_speaker in cands
        assert pic_path == "/api/media_player_proxy/fallback_art?t=1"

        # Entity media_player.async_get_media_image paths
        valid_jpeg = make_jpeg_bytes(120, 120)
        ent_mode: dict[str, Any] = {"mode": "no_method"}

        class _FakeEntityNoMethod:
            pass

        class _FakeMediaEntity:
            async def async_get_media_image(self) -> tuple[bytes | None, str | None]:
                mode = ent_mode["mode"]
                if mode == "raise":
                    raise RuntimeError("media_image failed")
                if mode == "oversize":
                    return (b"\xff" * (MAX_UPSTREAM_IMAGE_BYTES + 1), "image/jpeg")
                if mode == "valid":
                    return (valid_jpeg, "image/jpeg")
                return (None, None)

        fake_mp_comp = SimpleNamespace(
            get_entity=lambda eid: (
                _FakeEntityNoMethod()
                if ent_mode["mode"] == "no_method"
                else (_FakeMediaEntity() if eid == coord.active_speaker else None)
            )
        )

        with monkeypatch.context() as mp:
            mp.setitem(hass.data, "media_player", fake_mp_comp)

            # Oversize entity image -> 413 early response
            ent_mode["mode"] = "oversize"
            hass.states.async_set(
                coord.active_speaker, "playing", {"media_title": "Big Cover"}
            )
            r_ent_413 = await view.get(
                _make_get_request(
                    f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"
                ),
                coord.device_slug,
            )
            assert r_ent_413.status == 413

            # Valid entity image with media_title token -> MISS then HIT
            ent_mode["mode"] = "valid"
            r_ent_miss = await view.get(
                _make_get_request(
                    f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"
                ),
                coord.device_slug,
            )
            assert r_ent_miss.status == 200
            assert r_ent_miss.headers["X-Latter-Cache"] == "MISS"

            r_ent_hit = await view.get(
                _make_get_request(
                    f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"
                ),
                coord.device_slug,
            )
            assert r_ent_hit.status == 200
            assert r_ent_hit.headers["X-Latter-Cache"] == "HIT"

            # Valid entity image without any state token -> hashes raw prefix
            hass.states.async_set(coord.active_speaker, "playing", {})
            r_ent_notok = await view.get(
                _make_get_request(
                    f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"
                ),
                coord.device_slug,
            )
            assert r_ent_notok.status == 200
            assert r_ent_notok.headers["X-Latter-Cache"] == "MISS"

            # Entity raising error falls through to local HA HTTP fetch -> test 502 status
            ent_mode["mode"] = "raise"
            hass.states.async_set(
                coord.active_speaker,
                "playing",
                {"entity_picture": "/api/media_player_proxy/status500"},
            )
            mock_clientsession_get(
                mp, lambda _u, **_kw: _MockHttpResp(status=500, chunks=[])
            )
            mp.setattr(
                proxy_views,
                "async_get_clientsession",
                lambda *a, **kw: ha_aiohttp_client.async_get_clientsession(*a, **kw),
            )
            r_502_status = await view.get(
                _make_get_request(
                    f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"
                ),
                coord.device_slug,
            )
            assert r_502_status.status == 502

            # Entity without method falls through -> streamed > 8 MB without Content-Length -> 413
            ent_mode["mode"] = "no_method"
            hass.states.async_set(
                coord.active_speaker,
                "playing",
                {"entity_picture": "/api/media_player_proxy/stream_oversize"},
            )
            big_chunk = b"\x00" * (1024 * 1024)
            mock_clientsession_get(
                mp,
                lambda _u, **_kw: _MockHttpResp(
                    status=200, chunks=[big_chunk] * 9, content_length=None
                ),
            )
            r_413_chunked = await view.get(
                _make_get_request(
                    f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"
                ),
                coord.device_slug,
            )
            assert r_413_chunked.status == 413

            # session.get raising exception -> 502
            hass.states.async_set(
                coord.active_speaker,
                "playing",
                {"entity_picture": "/api/media_player_proxy/net_err"},
            )

            def _raise_get(_u: str, **_kw: Any) -> Any:
                raise RuntimeError("connection dropped")

            mock_clientsession_get(mp, _raise_get)
            r_502_exc = await view.get(
                _make_get_request(
                    f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"
                ),
                coord.device_slug,
            )
            assert r_502_exc.status == 502

            # Upstream returns non-image bytes -> 422 Pillow error
            hass.states.async_set(
                coord.active_speaker,
                "playing",
                {"entity_picture": "/api/media_player_proxy/corrupt_img"},
            )
            mock_clientsession_get(
                mp,
                lambda _u, **_kw: _MockHttpResp(
                    status=200, chunks=[b"NOT_AN_IMAGE"], content_length=12
                ),
            )
            r_422 = await view.get(
                _make_get_request(
                    f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"
                ),
                coord.device_slug,
            )
            assert r_422.status == 422
    finally:
        clear_http_caches()
        assert await hass.config_entries.async_unload(entry.entry_id) is True


@pytest.mark.asyncio
async def test_wallpaper_views_proxy_and_upload_edge_branches(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise wallpaper proxy error/cache paths, original aspect downscale, and multipart upload edges."""
    clear_http_caches()
    wp_view = LatterWallpaperProxyView(hass)
    upload_view = LatterWallpaperUploadView(hass)

    # 1) Uninitialized System checks before hub setup
    r_uninit_media = await wp_view.get(
        _make_get_request(
            "/api/latter/wallpaper/system?media_root=local&media_path=a.jpg&sig=bad"
        ),
        "system",
    )
    assert r_uninit_media.status == 404

    r_uninit_sys = await wp_view.get(
        _make_get_request(
            "/api/latter/wallpaper/system?src=preset:forest_mountains&sig=bad"
        ),
        "system",
    )
    assert r_uninit_sys.status == 404

    # 2) Pure transcode & multipart float helpers
    wide_jpeg = make_jpeg_bytes(400, 200)
    downscaled_orig = _transcode_photo_to_baseline_jpeg(
        wide_jpeg, 128, 128, original_aspect=True
    )
    with Image.open(io.BytesIO(downscaled_orig)) as im_down:
        assert im_down.size == (128, 64)

    media_dir = Path(hass.config.config_dir) / "media_cov_test"
    media_dir.mkdir(parents=True, exist_ok=True)
    empty_file = media_dir / "empty.jpg"
    empty_file.write_bytes(b"")
    with pytest.raises(ValueError, match="15 MB"):
        _transcode_media_preview_jpeg(empty_file, 160, 160)

    assert _parse_multipart_float("not-a-float", 0.5) == 0.5
    assert _parse_multipart_float("nan", 0.5) == 0.5

    # 3) Hub-backed wallpaper proxy and upload edge branches
    entry, sys_obj, coord = await setup_latter_hub(hass)
    created_photo_ids: list[str] = []
    try:
        valid_file = media_dir / "ok.jpg"
        valid_file.write_bytes(wide_jpeg)
        hass.config.media_dirs = {"local": str(media_dir)}

        # Media preview: non-system scope (403), invalid sig (403), cache MISS -> HIT, corrupt/empty (422)
        r_media_scope = await wp_view.get(
            _make_get_request(
                f"/api/latter/wallpaper/{coord.device_slug}?media_root=local&media_path=ok.jpg&sig=x"
            ),
            coord.device_slug,
        )
        assert r_media_scope.status == 403

        r_media_badsig = await wp_view.get(
            _make_get_request(
                "/api/latter/wallpaper/system?media_root=local&media_path=ok.jpg&sig=bad"
            ),
            "system",
        )
        assert r_media_badsig.status == 403

        ok_m_url = sys_obj.url_signer.build_media_preview_url("local", "ok.jpg", 160, 160)
        r_m_miss = await wp_view.get(_make_get_request(ok_m_url), "system")
        assert r_m_miss.status == 200
        assert r_m_miss.headers["X-Latter-Cache"] == "MISS"

        r_m_hit = await wp_view.get(_make_get_request(ok_m_url), "system")
        assert r_m_hit.status == 200
        assert r_m_hit.headers["X-Latter-Cache"] == "HIT"

        empty_m_url = sys_obj.url_signer.build_media_preview_url(
            "local", "empty.jpg", 160, 160
        )
        r_m_422 = await wp_view.get(_make_get_request(empty_m_url), "system")
        assert r_m_422.status == 422

        # Singleflight coalescing + Semaphore(2) bounded concurrency for concurrent `/media` previews
        import threading

        for idx in range(5):
            (media_dir / f"batch_{idx}.jpg").write_bytes(wide_jpeg)

        orig_preview_fn = wallpaper_views._transcode_media_preview_jpeg
        singleflight_calls = 0
        sf_gate = threading.Event()
        sf_entered = threading.Event()

        def _gated_singleflight(fp: Path, w: int, h: int) -> bytes:
            nonlocal singleflight_calls
            singleflight_calls += 1
            sf_entered.set()
            sf_gate.wait(timeout=2.0)
            return orig_preview_fn(fp, w, h)

        sf_url = sys_obj.url_signer.build_media_preview_url("local", "batch_0.jpg", 160, 160)
        with monkeypatch.context() as mp:
            mp.setattr(wallpaper_views, "_transcode_media_preview_jpeg", _gated_singleflight)
            t1 = asyncio.create_task(wp_view.get(_make_get_request(sf_url), "system"))
            t2 = asyncio.create_task(wp_view.get(_make_get_request(sf_url), "system"))
            t3 = asyncio.create_task(wp_view.get(_make_get_request(sf_url), "system"))
            await asyncio.to_thread(sf_entered.wait, 2.0)
            await asyncio.sleep(0.02)
            sf_gate.set()
            res_sf = await asyncio.gather(t1, t2, t3)
        assert singleflight_calls == 1
        assert all(r.status == 200 for r in res_sf)
        assert res_sf[0].body == res_sf[1].body == res_sf[2].body

        # Bounded concurrency: 4 distinct concurrent previews never exceed 2 simultaneous executor jobs
        active_conc = 0
        peak_conc = 0
        conc_lock = threading.Lock()

        def _tracked_preview(fp: Path, w: int, h: int) -> bytes:
            nonlocal active_conc, peak_conc
            with conc_lock:
                active_conc += 1
                peak_conc = max(peak_conc, active_conc)
            try:
                import time as _time

                _time.sleep(0.03)
                return orig_preview_fn(fp, w, h)
            finally:
                with conc_lock:
                    active_conc -= 1

        distinct_urls = [
            sys_obj.url_signer.build_media_preview_url("local", f"batch_{i}.jpg", 160, 160)
            for i in range(1, 5)
        ]
        with monkeypatch.context() as mp:
            mp.setattr(wallpaper_views, "_transcode_media_preview_jpeg", _tracked_preview)
            res_conc = await asyncio.gather(
                *(wp_view.get(_make_get_request(u), "system") for u in distinct_urls)
            )
        assert all(r.status == 200 for r in res_conc)
        assert peak_conc <= wallpaper_views._MAX_CONCURRENT_HTTP_TRANSCODES

        # Wallpaper proxy validation errors
        r_bad_mode = await wp_view.get(
            _make_get_request(
                "/api/latter/wallpaper/system?mode=bogus&src=preset:forest_mountains"
            ),
            "system",
        )
        assert r_bad_mode.status == 400

        r_sys_nosrc = await wp_view.get(
            _make_get_request("/api/latter/wallpaper/system?mode=wallpaper"),
            "system",
        )
        assert r_sys_nosrc.status == 404

        r_unknown_dev = await wp_view.get(
            _make_get_request(
                "/api/latter/wallpaper/nonexistent_dev?src=preset:forest_mountains"
            ),
            "nonexistent_dev",
        )
        assert r_unknown_dev.status == 404

        # Device with wallpaper mode off and omitted src -> 404
        coord.update_device_config({**coord.device_data, CONF_WALLPAPER_MODE: "off"})
        r_dev_nosrc = await wp_view.get(
            _make_get_request(f"/api/latter/wallpaper/{coord.device_slug}"),
            coord.device_slug,
        )
        assert r_dev_nosrc.status == 404

        # Preset rendering failure -> 422
        bad_preset_sig = sys_obj.url_signer.sign_payload_resource(
            "wallpaper:preset:forest_mountains|240|240|square|wallpaper"
        )
        with monkeypatch.context() as mp:
            mp.setattr(
                wallpaper_views,
                "render_builtin_preset_image",
                lambda *_a, **_kw: (_ for _ in ()).throw(RuntimeError("render fail")),
            )
            r_preset_422 = await wp_view.get(
                _make_get_request(
                    f"/api/latter/wallpaper/system?src=preset:forest_mountains&w=240&h=240&sig={bad_preset_sig}"
                ),
                "system",
            )
            assert r_preset_422.status == 422

        # Missing photo file -> 404
        missing_sig = sys_obj.url_signer.sign_payload_resource(
            "wallpaper:photo:missing_1234|240|240|square|wallpaper"
        )
        r_photo_404 = await wp_view.get(
            _make_get_request(
                f"/api/latter/wallpaper/system?src=photo:missing_1234&w=240&h=240&sig={missing_sig}"
            ),
            "system",
        )
        assert r_photo_404.status == 404

        # Corrupt photo bytes on disk -> 422
        orig_dir = get_wallpaper_root(hass) / "originals"
        orig_dir.mkdir(parents=True, exist_ok=True)
        corrupt_path = orig_dir / "corrupt_1234.jpg"
        corrupt_path.write_bytes(b"NOT_JPEG_DATA")
        corrupt_sig = sys_obj.url_signer.sign_payload_resource(
            "wallpaper:photo:corrupt_1234|240|240|square|wallpaper"
        )
        r_photo_422 = await wp_view.get(
            _make_get_request(
                f"/api/latter/wallpaper/system?src=photo:corrupt_1234&w=240&h=240&sig={corrupt_sig}"
            ),
            "system",
        )
        assert r_photo_422.status == 422
        corrupt_path.unlink(missing_ok=True)

        # Unsupported wallpaper source scheme -> 403
        bad_src_sig = sys_obj.url_signer.sign_payload_resource(
            "wallpaper:ftp://unsupported|240|240|square|wallpaper"
        )
        r_bad_src = await wp_view.get(
            _make_get_request(
                f"/api/latter/wallpaper/system?src=ftp://unsupported&w=240&h=240&sig={bad_src_sig}"
            ),
            "system",
        )
        assert r_bad_src.status == 403

        # Multipart upload edge branches:
        # a) Too many multipart parts -> 400
        too_many = [
            _MultipartPart("extra", text_val="x")
            for _ in range(MAX_MULTIPART_PARTS + 1)
        ]
        r_400_parts = await upload_view.post(_MultipartRequestStub(parts=too_many))
        assert r_400_parts.status == 400

        # b) Oversize text field (`crop_x` > 64 bytes) -> 413
        r_413_txt = await upload_view.post(
            _MultipartRequestStub(
                parts=[_MultipartPart("crop_x", text_val="9" * 80)]
            )
        )
        assert r_413_txt.status == 413

        # c) Unknown `device_slug` -> 404
        r_404_slug = await upload_view.post(
            _MultipartRequestStub(
                parts=[
                    _MultipartPart("device_slug", text_val="ghost_panel"),
                    _MultipartPart("file", file_bytes=wide_jpeg, filename="g.jpg"),
                ]
            )
        )
        assert r_404_slug.status == 404

        # d) System-scoped upload with unknown field + nested MultipartReader skipped -> 200 + Studio notify
        studio_notifies: list[int] = []
        unsub_studio = register_studio_subscriber(
            hass, lambda: studio_notifies.append(1)
        )
        nested_stub = _NestedMultipartStub()
        ignored_part = _MultipartPart("ignored_meta", text_val="noop")
        try:
            r_200_sys = await upload_view.post(
                _MultipartRequestStub(
                    parts=[
                        _MultipartPart("scope", text_val="system"),
                        nested_stub,
                        ignored_part,
                        _MultipartPart("file", file_bytes=wide_jpeg, filename="sys.jpg"),
                    ]
                )
            )
        finally:
            unsub_studio()
        assert r_200_sys.status == 200
        assert len(studio_notifies) == 1
        assert nested_stub.released is True
        assert ignored_part.released is True
        body_sys = json.loads(r_200_sys.body.decode("utf-8"))
        created_photo_ids.append(body_sys["photo_id"])
        assert body_sys["wallpapers"] == body_sys["system_wallpapers"]

        # e) Valid explicit `device_slug` resolves coordinator and binds wallpaper -> 200
        r_200_slug = await upload_view.post(
            _MultipartRequestStub(
                parts=[
                    _MultipartPart("device_slug", text_val=coord.device_slug),
                    _MultipartPart("file", file_bytes=wide_jpeg, filename="dev.jpg"),
                ]
            )
        )
        assert r_200_slug.status == 200
        body_slug = json.loads(r_200_slug.body.decode("utf-8"))
        created_photo_ids.append(body_slug["photo_id"])
        assert coord.wallpaper_source == body_slug["photo_id"]
    finally:
        for pid in created_photo_ids:
            delete_photo(hass, pid)
        await async_refresh_wallpaper_cache(hass)
        clear_http_caches()
        assert await hass.config_entries.async_unload(entry.entry_id) is True


@pytest.mark.asyncio
async def test_camera_views_snapshot_stream_grid_and_audio(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise camera view URL validation, subprocess cleanup, system snapshots, video/grid errors, and audio piping."""
    # 1) Pure helpers & uninitialized checks
    assert _is_allowed_stream_url(None) is False
    assert _is_allowed_stream_url("") is False
    assert _is_allowed_stream_url("   ") is False
    assert _is_allowed_stream_url("-i rtsp://10.0.0.1/s") is False
    assert _is_allowed_stream_url("file:///etc/passwd") is False
    assert _is_allowed_stream_url("rtsp://10.0.0.1/s") is True
    assert _is_allowed_stream_url("https://10.0.0.1/s") is True

    assert _clamp_video_query_dim("invalid", 480) == 480
    assert _parse_grid_requested_cameras("", ["camera.a", "camera.b"]) == [
        "camera.a",
        "camera.b",
    ]

    # _terminate_ffmpeg_process: exited, normal, timeout->kill, ProcessLookupError
    p_done = _FakeSubproc(returncode=0)
    await _terminate_ffmpeg_process(p_done, 0.05)  # type: ignore[arg-type]
    assert p_done.terminated is False

    p_ok = _FakeSubproc()
    await _terminate_ffmpeg_process(p_ok, 0.2)  # type: ignore[arg-type]
    assert p_ok.terminated is True and p_ok.killed is False

    p_hang = _FakeSubproc(hang_terminate=True)
    await _terminate_ffmpeg_process(p_hang, 0.01)  # type: ignore[arg-type]
    assert p_hang.terminated is True and p_hang.killed is True

    p_gone = _FakeSubproc(raise_lookup=True)
    await _terminate_ffmpeg_process(p_gone, 0.05)  # type: ignore[arg-type]

    # _terminate_ffmpeg_process guards ProcessLookupError raised during kill() after timeout
    class _KillGoneSubproc(_FakeSubproc):
        def kill(self) -> None:
            raise ProcessLookupError("exited before kill")

    p_kill_gone = _KillGoneSubproc(hang_terminate=True)
    with monkeypatch.context() as mp:
        mp.setattr(camera_views, "_PROC_KILL_WAIT_S", 0.02)
        await _terminate_ffmpeg_process(p_kill_gone, 0.01)  # type: ignore[arg-type]

    # async_shutdown_doorbell_streams terminates tracked procs
    p_tracked = _FakeSubproc()
    camera_views._ACTIVE_DEVICE_STREAMS["sub_shutdown_test"] = p_tracked  # type: ignore[assignment]
    await async_shutdown_doorbell_streams(hass)
    assert p_tracked.terminated is True
    assert "sub_shutdown_test" not in camera_views._ACTIVE_DEVICE_STREAMS

    # Uninitialized snapshot checks
    snap_view = LatterCameraSnapshotView(hass)
    r_unk = await snap_view.get(
        _make_get_request("/api/latter/camera/ghost_dev?entity_id=camera.a"),
        "ghost_dev",
    )
    assert r_unk.status == 404
    r_sys_uninit = await snap_view.get(
        _make_get_request("/api/latter/camera/system?entity_id=camera.a"),
        "system",
    )
    assert r_sys_uninit.status == 404

    # _async_stream_mjpeg_iterator error & mid-stream disconnect branches
    async def _empty_iter() -> AsyncIterator[bytes]:
        if False:
            yield b""

    async def _limit_iter() -> AsyncIterator[bytes]:
        raise CameraIngestLimitError("saturated")
        yield b""

    async def _fetch_err_iter() -> AsyncIterator[bytes]:
        raise CameraFetchError("offline")
        yield b""

    r_empty = await _async_stream_mjpeg_iterator(
        _make_get_request("/"), _empty_iter(), "no frames", "test"
    )
    assert r_empty.status == 502
    r_429 = await _async_stream_mjpeg_iterator(
        _make_get_request("/"), _limit_iter(), "no frames", "test"
    )
    assert r_429.status == 429
    r_502 = await _async_stream_mjpeg_iterator(
        _make_get_request("/"), _fetch_err_iter(), "no frames", "test"
    )
    assert r_502.status == 502

    for exc_cls in (ConnectionResetError, RuntimeError):

        async def _two_chunks() -> AsyncIterator[bytes]:
            yield b"chunk1"
            yield b"chunk2"

        writes: list[bytes] = []

        async def _fake_prepare(_self: Any, _req: Any) -> None:
            return None

        async def _failing_write(
            _self: Any,
            data: bytes,
            _exc_cls: type[Exception] = exc_cls,
            _writes: list[bytes] = writes,
        ) -> None:
            _writes.append(data)
            if len(_writes) == 2:
                raise _exc_cls("client gone")

        with monkeypatch.context() as mp:
            mp.setattr(web.StreamResponse, "prepare", _fake_prepare)
            mp.setattr(web.StreamResponse, "write", _failing_write)
            resp_mjpeg = await _async_stream_mjpeg_iterator(
                _make_get_request("/"), _two_chunks(), "no frames", "test"
            )
            assert resp_mjpeg.status == 200
            assert writes == [b"chunk1", b"chunk2"]

    # 2) Hub-backed tests
    images, streams = install_camera_mocks(
        monkeypatch,
        images={
            "camera.porch": make_jpeg_bytes(320, 240),
            "camera.broken": RuntimeError("down"),
            "camera.corrupt": b"NOT_A_JPEG",
        },
        streams={"camera.porch": "rtsp://10.0.0.10/porch"},
    )
    _ = images
    entry, sys_obj, coord = await setup_latter_hub(hass)
    try:
        get_global_config(hass)[CONF_CAMERA_ENTITIES] = [
            "camera.porch",
            "camera.broken",
            "camera.corrupt",
        ]
        hass.states.async_set("camera.porch", "streaming", {"friendly_name": "Porch"})
        hass.states.async_set("camera.broken", "idle", {"friendly_name": "Broken"})
        hass.states.async_set("camera.corrupt", "idle", {"friendly_name": "Corrupt"})

        # Device snapshot validation: non-camera entity_id (404), invalid sig (403)
        r_noncam = await snap_view.get(
            _make_get_request(
                f"/api/latter/camera/{coord.device_slug}?entity_id=light.desk"
            ),
            coord.device_slug,
        )
        assert r_noncam.status == 404

        r_badsig = await snap_view.get(
            _make_get_request(
                f"/api/latter/camera/{coord.device_slug}?entity_id=camera.porch&sig=invalid"
            ),
            coord.device_slug,
        )
        assert r_badsig.status == 403

        # Device snapshot errors: CameraFetchError (502) and CameraTranscodeError (422)
        broken_sig = coord.sign_payload_resource(
            "camera:camera.broken|466|466|circle"
        )
        r_fetch_502 = await snap_view.get(
            _make_get_request(
                f"/api/latter/camera/{coord.device_slug}?entity_id=camera.broken&w=466&h=466&shape=circle&sig={broken_sig}"
            ),
            coord.device_slug,
        )
        assert r_fetch_502.status == 502

        corrupt_sig = coord.sign_payload_resource(
            "camera:camera.corrupt|466|466|circle"
        )
        r_trans_422 = await snap_view.get(
            _make_get_request(
                f"/api/latter/camera/{coord.device_slug}?entity_id=camera.corrupt&w=466&h=466&shape=circle&sig={corrupt_sig}"
            ),
            coord.device_slug,
        )
        assert r_trans_422.status == 422

        # System-scoped snapshot preview: missing entity (404), bad sig (403), missing state (404), valid (200)
        r_sys_noent = await snap_view.get(
            _make_get_request("/api/latter/camera/system?entity_id=light.bad"),
            "system",
        )
        assert r_sys_noent.status == 404

        r_sys_badsig = await snap_view.get(
            _make_get_request(
                "/api/latter/camera/system?entity_id=camera.porch&sig=bad"
            ),
            "system",
        )
        assert r_sys_badsig.status == 403

        absent_sig = sys_obj.url_signer.sign_payload_resource(
            "camera:camera.absent|320|180|square"
        )
        r_sys_absent = await snap_view.get(
            _make_get_request(
                f"/api/latter/camera/system?entity_id=camera.absent&sig={absent_sig}"
            ),
            "system",
        )
        assert r_sys_absent.status == 404

        porch_sys_sig = sys_obj.url_signer.sign_payload_resource(
            "camera:camera.porch|320|180|square"
        )
        r_sys_ok = await snap_view.get(
            _make_get_request(
                f"/api/latter/camera/system?entity_id=camera.porch&sig={porch_sys_sig}"
            ),
            "system",
        )
        assert r_sys_ok.status == 200
        assert r_sys_ok.body.startswith(b"\xff\xd8")

        # Stream & Grid validation: WAN client (403), unknown device (404), empty allow-list (404), display=0 (400)
        stream_view = LatterCameraStreamView(hass)
        grid_view = LatterCameraGridView(hass)
        audio_view = LatterCameraAudioStreamView(hass)

        r_wan_stream = await stream_view.get(
            _make_get_request(
                f"/api/latter/camera_stream/{coord.device_slug}?sig=x",
                remote="93.184.216.34",
            ),
            coord.device_slug,
        )
        assert r_wan_stream.status == 403

        r_unk_stream = await stream_view.get(
            _make_get_request("/api/latter/camera_stream/ghost_dev?sig=x"),
            "ghost_dev",
        )
        assert r_unk_stream.status == 404

        # Empty camera allow-list -> 404 on stream, grid, and audio
        get_global_config(hass)[CONF_CAMERA_ENTITIES] = []
        coord.active_carousel_camera = ""
        max_w, max_h = coord.video_max_dims
        empty_sig = coord.sign_payload_resource(
            f"camera_stream:{camera_allowlist_hash([])}|{max_w}|{max_h}|{coord.video_max_fps}"
        )
        r_empty_stream = await stream_view.get(
            _make_get_request(
                f"/api/latter/camera_stream/{coord.device_slug}?sig={empty_sig}"
            ),
            coord.device_slug,
        )
        assert r_empty_stream.status == 404

        r_empty_grid = await grid_view.get(
            _make_get_request(
                f"/api/latter/camera_grid/{coord.device_slug}?sig={empty_sig}"
            ),
            coord.device_slug,
        )
        assert r_empty_grid.status == 404

        r_wan_audio = await audio_view.get(
            _make_get_request(
                f"/api/latter/camera_audio/{coord.device_slug}?sig=x",
                remote="93.184.216.34",
            ),
            coord.device_slug,
        )
        assert r_wan_audio.status == 403

        r_empty_audio = await audio_view.get(
            _make_get_request(f"/api/latter/camera_audio/{coord.device_slug}?sig=x"),
            coord.device_slug,
        )
        assert r_empty_audio.status == 404

        # Headless display=0 manifest -> video_max_dims == (0, 0) -> 400
        orig_hello_manifest = coord._runtime.hello_manifest
        coord._runtime.hello_manifest = {"v": 2, "contract": 3, "display": 0, "w": 0, "h": 0}
        headless_max_w, headless_max_h = coord.video_max_dims
        assert (headless_max_w, headless_max_h) == (0, 0)
        headless_sig = coord.sign_payload_resource(
            f"camera_stream:{camera_allowlist_hash(coord.visible_camera_entities)}"
            f"|{headless_max_w}|{headless_max_h}|{coord.video_max_fps}"
        )
        r_headless = await stream_view.get(
            _make_get_request(
                f"/api/latter/camera_stream/{coord.device_slug}?sig={headless_sig}"
            ),
            coord.device_slug,
        )
        assert r_headless.status == 400
        coord._runtime.hello_manifest = orig_hello_manifest

        # _build_camera_audio_ffmpeg_cmd variants (RTSP/FLAC vs HTTP/WAV)
        cfg_rtsp = _AudioStreamConfig(
            coord=coord,
            cam_ent="camera.porch",
            nr_level="aggressive",
            fmt="flac",
            out_rate=48000,
            out_ch=1,
        )
        cmd_rtsp = _build_camera_audio_ffmpeg_cmd(
            "/usr/bin/ffmpeg", "rtsp://10.0.0.10/porch", cfg_rtsp
        )
        assert "-rtsp_transport" in cmd_rtsp
        assert cmd_rtsp[cmd_rtsp.index("-c:a") + 1] == "flac"
        assert cmd_rtsp[cmd_rtsp.index("-f") + 1] == "flac"

        cfg_http = _AudioStreamConfig(
            coord=coord,
            cam_ent="camera.porch",
            nr_level="light",
            fmt="wav",
            out_rate=16000,
            out_ch=2,
        )
        cmd_http = _build_camera_audio_ffmpeg_cmd(
            "/usr/bin/ffmpeg", "http://10.0.0.10/audio", cfg_http
        )
        assert "-rtsp_transport" not in cmd_http
        assert cmd_http[cmd_http.index("-c:a") + 1] == "pcm_s16le"
        assert cmd_http[cmd_http.index("-f") + 1] == "wav"
        assert cmd_http[cmd_http.index("-ac") + 1] == "2"

        # Audio stream view: semaphore 429, active stream replacement + piping, error exits
        get_global_config(hass)[CONF_CAMERA_ENTITIES] = ["camera.porch"]
        audio_sig = coord.sign_on_demand_resource(
            "camera_audio:camera.porch|aggressive|flac"
        )
        audio_url = (
            f"/api/latter/camera_audio/{coord.device_slug}"
            f"?entity_id=camera.porch&nr=aggressive&fmt=flac&sig={audio_sig}"
        )

        with monkeypatch.context() as mp:
            mp.setattr(
                ha_ffmpeg,
                "get_ffmpeg_manager",
                lambda _h: SimpleNamespace(binary="/usr/bin/ffmpeg"),
            )
            # Exhaust semaphore -> 429
            await camera_views._FFMPEG_STREAM_SEMAPHORE.acquire()
            await camera_views._FFMPEG_STREAM_SEMAPHORE.acquire()
            try:
                r_audio_429 = await audio_view.get(
                    _make_get_request(audio_url), coord.device_slug
                )
                assert r_audio_429.status == 429
            finally:
                camera_views._FFMPEG_STREAM_SEMAPHORE.release()
                camera_views._FFMPEG_STREAM_SEMAPHORE.release()

            # Happy path with pre-existing process replaced and audio chunks piped
            prev_proc = _FakeSubproc()
            camera_views._ACTIVE_DEVICE_STREAMS[coord.subentry_id] = prev_proc  # type: ignore[assignment]
            new_proc = _FakeSubproc([b"fLaC", b"audio_payload"])
            audio_written: list[bytes] = []

            async def _spawn_audio(*_cmd: str, **_kw: Any) -> _FakeSubproc:
                return new_proc

            async def _noop_prepare(_self: Any, _req: Any) -> None:
                return None

            async def _rec_write(_self: Any, data: bytes) -> None:
                audio_written.append(data)

            mp.setattr(asyncio, "create_subprocess_exec", _spawn_audio)
            mp.setattr(web.StreamResponse, "prepare", _noop_prepare)
            mp.setattr(web.StreamResponse, "write", _rec_write)

            r_audio_ok = await audio_view.get(
                _make_get_request(audio_url), coord.device_slug
            )
            assert r_audio_ok.status == 200
            assert prev_proc.terminated is True
            assert new_proc.terminated is True
            assert b"".join(audio_written) == b"fLaCaudio_payload"
            assert coord.subentry_id not in camera_views._ACTIVE_DEVICE_STREAMS

            # ConnectionResetError and RuntimeError during _async_pipe_ffmpeg_audio
            for err_cls in (ConnectionResetError, RuntimeError):
                err_proc = _FakeSubproc([b"chunkA"])

                async def _spawn_err(
                    *_cmd: str, _p: _FakeSubproc = err_proc, **_kw: Any
                ) -> _FakeSubproc:
                    return _p

                async def _err_write(
                    _self: Any, _data: bytes, _cls: type[Exception] = err_cls
                ) -> None:
                    raise _cls("write aborted")

                mp.setattr(asyncio, "create_subprocess_exec", _spawn_err)
                mp.setattr(web.StreamResponse, "write", _err_write)
                r_aborted = await _async_pipe_ffmpeg_audio(
                    _make_get_request(audio_url), cfg_rtsp, cmd_rtsp
                )
                assert r_aborted.status == 200
                assert err_proc.terminated is True

            # Audio read timeout terminates wedged RTSP subprocess cleanly
            stall_ev = asyncio.Event()
            wedged_proc = _FakeSubproc([], stall_event=stall_ev)

            async def _spawn_wedged(*_cmd: str, **_kw: Any) -> _FakeSubproc:
                return wedged_proc

            mp.setattr(asyncio, "create_subprocess_exec", _spawn_wedged)
            mp.setattr(web.StreamResponse, "write", _rec_write)
            mp.setattr(camera_views, "_AUDIO_READ_TIMEOUT_S", 0.02)
            r_timeout = await _async_pipe_ffmpeg_audio(
                _make_get_request(audio_url), cfg_rtsp, cmd_rtsp
            )
            assert r_timeout.status == 200
            assert wedged_proc.terminated is True
            assert coord.subentry_id not in camera_views._ACTIVE_DEVICE_STREAMS
            stall_ev.set()

            # Camera-switch self-deadlock regression: Device A switches while both audio slots are full
            mp.setattr(camera_views, "_AUDIO_READ_TIMEOUT_S", 5.0)
            stream1_stall = asyncio.Event()
            stream1_started = asyncio.Event()

            class _SwitchingSubproc(_FakeSubproc):
                def terminate(self) -> None:
                    super().terminate()
                    stream1_stall.set()

            proc_first = _SwitchingSubproc([b"fLaC"], stall_event=stream1_stall)
            proc_second = _FakeSubproc([b"fLaC_new"])
            spawn_iter = iter([proc_first, proc_second])

            async def _spawn_switch(*_cmd: str, **_kw: Any) -> _FakeSubproc:
                p = next(spawn_iter)
                if p is proc_first:
                    stream1_started.set()
                return p

            mp.setattr(asyncio, "create_subprocess_exec", _spawn_switch)
            # Occupy 1 slot for another device; Device A occupies the 2nd slot
            await camera_views._FFMPEG_STREAM_SEMAPHORE.acquire()
            try:
                t_first = asyncio.create_task(
                    audio_view.get(_make_get_request(audio_url), coord.device_slug)
                )
                await asyncio.wait_for(stream1_started.wait(), timeout=1.0)
                await asyncio.sleep(0.01)
                assert camera_views._FFMPEG_STREAM_SEMAPHORE.locked() is True
                # Device A switches cameras -> reaps proc_first BEFORE acquiring semaphore -> 200 (not 429!)
                r_switched = await audio_view.get(
                    _make_get_request(audio_url), coord.device_slug
                )
                assert r_switched.status == 200
                assert proc_first.terminated is True
                assert proc_second.terminated is True
                await asyncio.wait_for(t_first, timeout=1.0)
            finally:
                camera_views._FFMPEG_STREAM_SEMAPHORE.release()

            # Cached off-loop shutil.which lookup when ffmpeg manager raises
            which_calls = 0

            def _raise_mgr(_h: Any) -> Any:
                raise RuntimeError("no ffmpeg manager")

            def _spy_which(_bin: str) -> str:
                nonlocal which_calls
                which_calls += 1
                return "/usr/local/bin/ffmpeg"

            mp.setattr(ha_ffmpeg, "get_ffmpeg_manager", _raise_mgr)
            mp.setattr(camera_views.shutil, "which", _spy_which)
            mp.setattr(camera_views, "_FFMPEG_BIN_CHECKED", False)
            mp.setattr(camera_views, "_CACHED_FFMPEG_BIN", None)
            assert await camera_views._async_resolve_ffmpeg_binary(hass) == "/usr/local/bin/ffmpeg"
            assert await camera_views._async_resolve_ffmpeg_binary(hass) == "/usr/local/bin/ffmpeg"
            assert which_calls == 1

        # Silence WAV fallback when stream URL is disallowed
        streams["camera.porch"] = "file:///etc/passwd"
        r_silence = await audio_view.get(
            _make_get_request(audio_url), coord.device_slug
        )
        assert r_silence.status == 200
        assert r_silence.content_type == "audio/wav"
        assert r_silence.body.startswith(b"RIFF")
    finally:
        camera_views._ACTIVE_DEVICE_STREAMS.clear()
        assert await hass.config_entries.async_unload(entry.entry_id) is True


@pytest.mark.asyncio
async def test_camera_views_real_aiohttp_mjpeg_and_audio_wire(
    hass: Any,
    setup_latter_hub: Any,
    aiohttp_client: Any,
    socket_enabled: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify real aiohttp_client HTTP wire streaming for single MJPEG, 2x2 grid, and FFmpeg audio."""
    _ = socket_enabled
    assert await async_setup_component(hass, "http", {}) is True
    _images, streams = install_camera_mocks(
        monkeypatch,
        images={"camera.porch": make_jpeg_bytes(320, 240)},
        streams={},
    )
    monkeypatch.setattr(ha_camera, "async_get_mjpeg_stream", None, raising=False)

    entry, _sys_obj, coord = await setup_latter_hub(hass)
    try:
        get_global_config(hass)[CONF_CAMERA_ENTITIES] = ["camera.porch"]
        get_global_config(hass)[CONF_CAMERA_CONFIGS] = {
            "camera.porch": {"label": "Front Entry"}
        }
        hass.states.async_set("camera.porch", "idle", {"friendly_name": "Porch"})
        client = await aiohttp_client(hass.http.app)

        # Single camera MJPEG stream over real HTTP (uses Tier 3 Snapshot mock)
        stream_sig = parse_qs(urlsplit(coord.build_camera_stream_url()).query)["sig"][0]
        async with client.get(
            f"/api/latter/camera_stream/{coord.device_slug}?entity_id=camera.porch&fps=15&sig={stream_sig}"
        ) as resp_s:
            assert resp_s.status == 200
            chunk_s = await resp_s.content.read(1024)
            assert b"--latterframe\r\n" in chunk_s

        # 2x2 Grid stream omitting `cameras` param (defaults to allowed + label_overrides)
        async with client.get(
            f"/api/latter/camera_grid/{coord.device_slug}?fps=15&sig={stream_sig}"
        ) as resp_g:
            assert resp_g.status == 200
            chunk_g = await resp_g.content.read(1024)
            assert b"--latterframe\r\n" in chunk_g

        # Audio WAV stream over real HTTP with fake FFmpeg subprocess
        streams["camera.porch"] = "rtsp://10.0.0.10/porch"
        audio_sig = coord.sign_on_demand_resource("camera_audio:camera.porch|light|wav")
        with monkeypatch.context() as mp:
            mp.setattr(
                ha_ffmpeg,
                "get_ffmpeg_manager",
                lambda _h: SimpleNamespace(binary="/usr/bin/ffmpeg"),
            )

            async def _spawn_wav(*_cmd: str, **_kw: Any) -> _FakeSubproc:
                return _FakeSubproc([b"RIFF", b"WAVEdata"])

            mp.setattr(asyncio, "create_subprocess_exec", _spawn_wav)
            async with client.get(
                f"/api/latter/camera_audio/{coord.device_slug}?entity_id=camera.porch&nr=light&fmt=wav&sig={audio_sig}"
            ) as resp_a:
                assert resp_a.status == 200
                assert resp_a.content_type == "audio/wav"
                assert await resp_a.read() == b"RIFFWAVEdata"

        # Allow closed MJPEG/grid handlers to observe disconnect cleanly before unload
        await asyncio.sleep(0.12)
    finally:
        assert await hass.config_entries.async_unload(entry.entry_id) is True
        await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_stream_hub_rtsp_and_lifecycle_branches(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise stream_hub FFmpeg lookup, stream source cache, terminate escalation, RTSP loops, and lifecycle edges."""
    # Uninitialized shutdown no-op
    await async_shutdown_camera_stream_hub(hass)

    hub = LatterCameraStreamHub(hass, max_concurrent_ingests=2, idle_timeout_s=5.0)
    try:
        # 1) _async_resolve_ffmpeg_binary via get_ffmpeg_manager
        with monkeypatch.context() as mp:
            mp.setattr(
                ha_ffmpeg,
                "get_ffmpeg_manager",
                lambda _h: SimpleNamespace(binary="/opt/bin/ffmpeg"),
            )
            assert await hub._async_resolve_ffmpeg_binary() == "/opt/bin/ffmpeg"

        # 2) _async_get_stream_source error, whitespace-empty, and valid URL paths
        async def _flaky_source(_h: Any, eid: str) -> str | None:
            if eid == "camera.err_src":
                raise RuntimeError("source error")
            if eid == "camera.blank_src":
                return "   "
            return "  rtsp://10.0.0.5/live  "

        with monkeypatch.context() as mp:
            mp.setattr(ha_camera, "async_get_stream_source", _flaky_source)
            assert await hub._async_get_stream_source("camera.err_src") is None
            assert await hub._async_get_stream_source("camera.blank_src") is None
            assert await hub._async_get_stream_source("camera.ok_src") == "rtsp://10.0.0.5/live"

        # 3) _async_terminate_proc timeout->kill & ProcessLookupError
        with monkeypatch.context() as mp:
            mp.setattr(hub_mod, "_PROC_TERM_TIMEOUT_S", 0.01)
            mp.setattr(hub_mod, "_PROC_KILL_WAIT_S", 0.05)
            p_hang = _FakeSubproc(hang_terminate=True)
            await hub._async_terminate_proc(p_hang)  # type: ignore[arg-type]
            assert p_hang.terminated is True and p_hang.killed is True

            p_gone = _FakeSubproc(raise_lookup=True)
            await hub._async_terminate_proc(p_gone)  # type: ignore[arg-type]

        # 4) Re-subscribe cancels pending idle_task and upgrades profile -> sets restart_event
        install_camera_mocks(
            monkeypatch, images={"camera.reattach": make_jpeg_bytes(320, 240)}
        )
        monkeypatch.setattr(ha_camera, "async_get_mjpeg_stream", None, raising=False)
        ing1, sub1 = await hub._subscribe("camera.reattach", 320, 240, 5, fit="fill")
        hub._unsubscribe(ing1, sub1)
        assert ing1.idle_task is not None and not ing1.idle_task.done()

        ing2, sub2 = await hub._subscribe("camera.reattach", 480, 320, 10, fit="contain")
        assert ing2 is ing1
        assert ing1.idle_task is None
        assert ing1.restart_event.is_set() is True
        await asyncio.sleep(0)
        hub._unsubscribe(ing2, sub2)
        await hub._async_stop_ingest(ing1)

        # 5) _async_stop_ingest releases semaphore directly when _task is None
        await hub._video_semaphore.acquire()
        orphan = CameraIngest(entity_id="camera.orphan", sem_acquired=True)
        hub._ingests["camera.orphan"] = orphan
        await hub._async_stop_ingest(orphan)
        assert orphan.sem_acquired is False
        assert "camera.orphan" not in hub._ingests

        # 6) _async_prime_snapshot: missing async_get_image, empty content, and CancelledError
        prime_ing = CameraIngest(entity_id="camera.prime")
        with monkeypatch.context() as mp:
            mp.setattr(ha_camera, "async_get_image", None, raising=False)
            await hub._async_prime_snapshot(prime_ing, (320, 240, "contain", 0))
            assert prime_ing.latest_seq == 0

            async def _empty_img(*_a: Any, **_kw: Any) -> Any:
                return SimpleNamespace(content=b"")

            mp.setattr(ha_camera, "async_get_image", _empty_img)
            await hub._async_prime_snapshot(prime_ing, (320, 240, "contain", 0))
            assert prime_ing.latest_seq == 0

            gate = asyncio.Event()

            async def _slow_img(*_a: Any, **_kw: Any) -> Any:
                await gate.wait()
                return SimpleNamespace(content=make_jpeg_bytes(64, 64))

            mp.setattr(ha_camera, "async_get_image", _slow_img)
            t_prime = asyncio.create_task(
                hub._async_prime_snapshot(prime_ing, (320, 240, "contain", 0))
            )
            await asyncio.sleep(0.005)
            t_prime.cancel()
            with pytest.raises(asyncio.CancelledError):
                await t_prime

        # 7) _async_read_rtsp_stdout_loop: immediate restart, timeout, mid-read restart, prime_task cancel + close
        frame_bytes = make_jpeg_bytes(320, 192)
        parser = MjpegStreamParser()
        profile = (320, 240, "contain", 0)

        # Immediate restart_event set
        ing_rst = CameraIngest(entity_id="camera.rtsp1")
        ing_rst.restart_event.set()
        assert (
            await hub._async_read_rtsp_stdout_loop(
                ing_rst, _FakeStdoutPipe([]), parser, profile  # type: ignore[arg-type]
            )
            is True
        )

        # Read timeout
        stall = asyncio.Event()
        ing_to = CameraIngest(entity_id="camera.rtsp2")
        with monkeypatch.context() as mp:
            mp.setattr(hub_mod, "FFMPEG_READ_TIMEOUT_SECONDS", 0.02)
            assert (
                await hub._async_read_rtsp_stdout_loop(
                    ing_to,
                    _FakeStdoutPipe([], stall_event=stall),  # type: ignore[arg-type]
                    MjpegStreamParser(),
                    profile,
                )
                is False
            )

        # Mid-read restart_event
        ing_mid = CameraIngest(entity_id="camera.rtsp3")

        async def _trigger_restart() -> None:
            await asyncio.sleep(0.01)
            ing_mid.restart_event.set()

        trig = asyncio.create_task(_trigger_restart())
        assert (
            await hub._async_read_rtsp_stdout_loop(
                ing_mid,
                _FakeStdoutPipe([], stall_event=stall),  # type: ignore[arg-type]
                MjpegStreamParser(),
                profile,
            )
            is True
        )
        await trig

        # Live frame cancels pending prime_task & exits loop via ingest.closed -> returns False
        ing_close = CameraIngest(entity_id="camera.rtsp4")
        prime_ref = asyncio.create_task(stall.wait())
        ing_close.prime_task = prime_ref

        def _mark_closed() -> None:
            ing_close.closed = True

        assert (
            await hub._async_read_rtsp_stdout_loop(
                ing_close,
                _FakeStdoutPipe([format_mjpeg_chunk(frame_bytes)], on_read=_mark_closed),  # type: ignore[arg-type]
                MjpegStreamParser(),
                profile,
            )
            is False
        )
        assert ing_close.prime_task is None
        assert ing_close.live_seq == 1
        with contextlib.suppress(asyncio.CancelledError):
            await prime_ref
        stall.set()

        # 8) _async_run_rtsp_tier: proc.stdout is None & subprocess exec raises OSError
        ing_rt = CameraIngest(entity_id="camera.rtsp5")
        with monkeypatch.context() as mp:

            async def _no_stdout_proc(*_cmd: str, **_kw: Any) -> _FakeSubproc:
                return _FakeSubproc(has_stdout=False)

            mp.setattr(asyncio, "create_subprocess_exec", _no_stdout_proc)
            assert (
                await hub._async_run_rtsp_tier(
                    ing_rt, "ffmpeg", "rtsp://10.0.0.1/s", (320, 240, 5, "contain", 0)
                )
                is False
            )

            async def _exec_oserror(*_cmd: str, **_kw: Any) -> Any:
                raise OSError("cannot spawn ffmpeg")

            mp.setattr(asyncio, "create_subprocess_exec", _exec_oserror)
            assert (
                await hub._async_run_rtsp_tier(
                    ing_rt, "ffmpeg", "rtsp://10.0.0.1/s", (320, 240, 5, "contain", 0)
                )
                is False
            )

        # 9) _async_try_rtsp_ingest_step closed & restarted returns, plus _async_run_ingest control flow
        with monkeypatch.context() as mp:
            mp.setattr(
                hub, "_async_get_stream_source", lambda _e: asyncio.sleep(0, result="rtsp://10.0.0.1/s")
            )
            mp.setattr(
                hub, "_async_resolve_ffmpeg_binary", lambda: asyncio.sleep(0, result="/usr/bin/ffmpeg")
            )

            ing_s1 = CameraIngest(entity_id="camera.step1")
            ing_s1.latest_frame = frame_bytes

            async def _tier_closes(ing: CameraIngest, *_a: Any) -> bool:
                ing.closed = True
                return False

            mp.setattr(hub, "_async_run_rtsp_tier", _tier_closes)
            assert await hub._async_try_rtsp_ingest_step(ing_s1, 1) == (True, 1)

            ing_s2 = CameraIngest(entity_id="camera.step2")
            ing_s2.latest_frame = frame_bytes
            mp.setattr(
                hub, "_async_run_rtsp_tier", lambda *_a: asyncio.sleep(0, result=True)
            )
            assert await hub._async_try_rtsp_ingest_step(ing_s2, 2) == (True, 0)

        # _async_run_ingest branches: closed after rtsp, closed after mjpeg, mjpeg_ok continue, snapshot exit, crash
        with monkeypatch.context() as mp:
            mp.setattr(hub_mod, "_TIER_RETRY_BACKOFF_S", 0.001)

            # Closed after rtsp step
            ing_r1 = CameraIngest(entity_id="camera.run1")

            async def _step_close(ing: CameraIngest, _a: int) -> tuple[bool, int]:
                ing.closed = True
                return False, 0

            mp.setattr(hub, "_async_try_rtsp_ingest_step", _step_close)
            await hub._async_run_ingest(ing_r1)

            # Closed after mjpeg tier
            ing_r2 = CameraIngest(entity_id="camera.run2")
            mp.setattr(
                hub,
                "_async_try_rtsp_ingest_step",
                lambda _i, _a: asyncio.sleep(0, result=(False, 0)),
            )

            async def _mjpeg_close(ing: CameraIngest) -> bool:
                ing.closed = True
                return False

            mp.setattr(hub, "_async_run_mjpeg_tier", _mjpeg_close)
            await hub._async_run_ingest(ing_r2)

            # mjpeg_ok True -> loops -> next call sets closed
            ing_r3 = CameraIngest(entity_id="camera.run3")
            mjpeg_calls = 0

            async def _mjpeg_once(ing: CameraIngest) -> bool:
                nonlocal mjpeg_calls
                mjpeg_calls += 1
                if mjpeg_calls == 1:
                    return True
                ing.closed = True
                return False

            mp.setattr(hub, "_async_run_mjpeg_tier", _mjpeg_once)
            await hub._async_run_ingest(ing_r3)
            assert mjpeg_calls == 2

            # snapshot tier exits cleanly on ingest.closed
            ing_r4 = CameraIngest(entity_id="camera.run4")
            mp.setattr(
                hub, "_async_run_mjpeg_tier", lambda _i: asyncio.sleep(0, result=False)
            )

            async def _snap_close(ing: CameraIngest) -> None:
                ing.closed = True

            mp.setattr(hub, "_async_run_snapshot_tier", _snap_close)
            await hub._async_run_ingest(ing_r4)
            assert ing_r4.source_tier == "snapshot"

            # Unexpected error inside loop -> publish_error + cleanup from _ingests
            ing_r5 = CameraIngest(entity_id="camera.run5")
            hub._ingests["camera.run5"] = ing_r5

            async def _step_crash(_i: CameraIngest, _a: int) -> tuple[bool, int]:
                raise RuntimeError("loop exploded")

            mp.setattr(hub, "_async_try_rtsp_ingest_step", _step_crash)
            await hub._async_run_ingest(ing_r5)
            assert isinstance(ing_r5.latest_error, RuntimeError)
            assert "camera.run5" not in hub._ingests
    finally:
        await hub.async_shutdown()


@pytest.mark.asyncio
async def test_stream_hub_mjpeg_snapshot_waiter_and_grid_branches(
    hass: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise MJPEG consumer/queue paths, snapshot transcode errors, keepalive waiters, and grid timing."""
    hub = LatterCameraStreamHub(hass, max_concurrent_ingests=4, idle_timeout_s=0.1)
    try:
        # 1) _async_publish_upstream_jpeg: transcode downscale & corrupt frame error
        ing_up = CameraIngest(
            entity_id="camera.up", stream_w=320, stream_h=240, stream_fit="contain"
        )
        big_jpeg = make_jpeg_bytes(640, 360)
        await hub._async_publish_upstream_jpeg(ing_up, big_jpeg)
        assert ing_up.latest_frame is not None
        assert inspect_jpeg_header(ing_up.latest_frame)[1:] == (320, 176)

        seq_before = ing_up.latest_seq
        await hub._async_publish_upstream_jpeg(ing_up, b"\xff\xd8CORRUPT\xff\xd9")
        assert ing_up.latest_seq == seq_before

        # 2) _async_consume_mjpeg_return_value: None, __aiter__, content.iter_chunked, unknown object
        small_chunk = format_mjpeg_chunk(make_jpeg_bytes(160, 128))
        ing_con = CameraIngest(entity_id="camera.con", stream_w=320, stream_h=240)
        assert (
            await hub._async_consume_mjpeg_return_value(
                ing_con, MjpegStreamParser(), None
            )
            is False
        )
        assert (
            await hub._async_consume_mjpeg_return_value(
                ing_con, MjpegStreamParser(), object()
            )
            is False
        )

        class _AsyncIterStream:
            async def __aiter__(self) -> AsyncIterator[bytes]:
                yield small_chunk
                ing_con.restart_event.set()
                yield small_chunk

        assert (
            await hub._async_consume_mjpeg_return_value(
                ing_con, MjpegStreamParser(), _AsyncIterStream()
            )
            is True
        )

        ing_con.restart_event.clear()

        class _ChunkedResp:
            class _Content:
                async def iter_chunked(self, _n: int) -> AsyncIterator[bytes]:
                    yield small_chunk
                    ing_con.closed = True
                    yield small_chunk

            content = _Content()

        assert (
            await hub._async_consume_mjpeg_return_value(
                ing_con, MjpegStreamParser(), _ChunkedResp()
            )
            is True
        )

        # 3) _async_run_mjpeg_tier & _async_step_mjpeg_queue:
        # a) Push-mode transport writes chunk while producer is alive
        ing_push = CameraIngest(entity_id="camera.push", stream_w=320, stream_h=240)

        async def _push_mjpeg(_h: Any, req: Any, _eid: str) -> None:
            req.transport.write(small_chunk)
            await asyncio.sleep(0.01)

        with monkeypatch.context() as mp:
            mp.setattr(ha_camera, "async_get_mjpeg_stream", _push_mjpeg)
            assert await hub._async_run_mjpeg_tier(ing_push) is True
            assert ing_push.source_tier == "mjpeg"

        # b) Timeout while producer hangs -> cancels get_task & producer
        hang_gate = asyncio.Event()

        async def _hang_mjpeg(_h: Any, _req: Any, _eid: str) -> None:
            await hang_gate.wait()

        with monkeypatch.context() as mp:
            mp.setattr(ha_camera, "async_get_mjpeg_stream", _hang_mjpeg)
            mp.setattr(hub_mod, "FFMPEG_READ_TIMEOUT_SECONDS", 0.02)
            assert (
                await hub._async_run_mjpeg_tier(
                    CameraIngest(entity_id="camera.hang_mjpeg")
                )
                is False
            )

        # c) Producer raises RuntimeError -> caught in _async_run_mjpeg_tier
        async def _boom_mjpeg(_h: Any, _req: Any, _eid: str) -> None:
            raise RuntimeError("mjpeg failed")

        with monkeypatch.context() as mp:
            mp.setattr(ha_camera, "async_get_mjpeg_stream", _boom_mjpeg)
            assert (
                await hub._async_run_mjpeg_tier(
                    CameraIngest(entity_id="camera.boom_mjpeg")
                )
                is False
            )

        # d) Cancelled _async_run_mjpeg_tier re-raises CancelledError & cancels producer
        with monkeypatch.context() as mp:
            mp.setattr(ha_camera, "async_get_mjpeg_stream", _hang_mjpeg)
            t_mjpeg = asyncio.create_task(
                hub._async_run_mjpeg_tier(CameraIngest(entity_id="camera.cancel_mjpeg"))
            )
            await asyncio.sleep(0.01)
            t_mjpeg.cancel()
            with pytest.raises(asyncio.CancelledError):
                await t_mjpeg

        # e) _async_step_mjpeg_queue with pre-cancelled producer
        cancelled_prod: asyncio.Task[Any] = asyncio.create_task(hang_gate.wait())
        cancelled_prod.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled_prod
        q_step: asyncio.Queue[bytes | None] = asyncio.Queue()
        assert await hub._async_step_mjpeg_queue(
            CameraIngest(entity_id="camera.cprod"),
            q_step,
            cancelled_prod,
            MjpegStreamParser(),
        ) == (False, False)
        hang_gate.set()

        # 4) _async_poll_single_snapshot cancel & _async_run_snapshot_tier failure retry loop
        snap_gate = asyncio.Event()

        async def _slow_snap(*_a: Any, **_kw: Any) -> Any:
            await snap_gate.wait()
            return SimpleNamespace(content=make_jpeg_bytes(64, 64))

        with monkeypatch.context() as mp:
            mp.setattr(ha_camera, "async_get_image", _slow_snap)
            t_snap = asyncio.create_task(
                hub._async_poll_single_snapshot(
                    CameraIngest(entity_id="camera.snap_cancel"),
                    (320, 240, "contain", 0),
                )
            )
            await asyncio.sleep(0.005)
            t_snap.cancel()
            with pytest.raises(asyncio.CancelledError):
                await t_snap
        snap_gate.set()

        ing_fail_snap = CameraIngest(entity_id="camera.snap_fail")
        orig_sleep = asyncio.sleep

        async def _sleep_and_close(_delay: float) -> None:
            ing_fail_snap.closed = True
            await orig_sleep(0)

        with monkeypatch.context() as mp:
            mp.setattr(
                hub,
                "_async_poll_single_snapshot",
                lambda _i, _p: orig_sleep(0, result=False),
            )
            mp.setattr(hub_mod.asyncio, "sleep", _sleep_and_close)
            await hub._async_run_snapshot_tier(ing_fail_snap)

        # 5) async_get_snapshot CameraTranscodeError on warm hit and cold miss
        warm_bad = CameraIngest(entity_id="camera.warm_bad", stream_w=320, stream_h=240)
        warm_bad.publish(b"CORRUPT_WARM", (320, 240, "contain", 0))
        hub._ingests["camera.warm_bad"] = warm_bad
        with pytest.raises(CameraTranscodeError):
            await hub.async_get_snapshot("camera.warm_bad", 160, 128)
        hub._ingests.pop("camera.warm_bad", None)

        install_camera_mocks(monkeypatch, images={"camera.cold_bad": b"CORRUPT_COLD"})
        with pytest.raises(CameraTranscodeError):
            await hub.async_get_snapshot("camera.cold_bad", 160, 128)

        # 6) _async_wait_next_ingest_frame timeout/error variants & async_iter_stream_frames keepalive + None race
        sub = CameraSubscriber(160, 128, 10, "contain", 0, False)
        ing_w = CameraIngest(entity_id="camera.waiter")
        # Timeout with neither frame nor error -> None
        assert await hub._async_wait_next_ingest_frame(ing_w, sub, 0.01) is None
        # Timeout with error only -> CameraFetchError
        ing_w.latest_error = RuntimeError("timeout err")
        with pytest.raises(CameraFetchError):
            await hub._async_wait_next_ingest_frame(ing_w, sub, 0.01)
        # Event wakes up with error only -> CameraFetchError
        ing_w2 = CameraIngest(entity_id="camera.waiter2")

        async def _wake_err() -> None:
            await orig_sleep(0.005)
            ing_w2.publish_error(RuntimeError("woke with err"))

        w_task = asyncio.create_task(_wake_err())
        with pytest.raises(CameraFetchError):
            await hub._async_wait_next_ingest_frame(ing_w2, sub, 0.5)
        await w_task

        # Keepalive yield + frame-cleared-during-sleep continue inside async_iter_stream_frames
        ing_ka = CameraIngest(entity_id="camera.keepalive", stream_w=160, stream_h=128)
        ka_frame = make_jpeg_bytes(160, 128)
        ing_ka.publish(ka_frame, (160, 128, "contain", 0))
        hub._ingests["camera.keepalive"] = ing_ka

        gen_ka = hub.async_iter_stream_frames(
            "camera.keepalive", 160, 128, fps=1, wait_timeout_s=0.02
        )
        # Frame 1 emitted immediately
        assert await anext(gen_ka) == ka_frame
        # No new seq -> timeout yields keepalive frame (lines 722-724, 770-771)
        assert await anext(gen_ka) == ka_frame

        # Trigger FPS pacing sleep race where latest_frame becomes None during sleep (line 759)
        ing_ka.publish(ka_frame, (160, 128, "contain", 0))
        race_fired = False
        repub_handle: asyncio.TimerHandle | None = None

        async def _race_sleep(_delay: float) -> None:
            nonlocal race_fired, repub_handle
            if not race_fired:
                race_fired = True
                ing_ka.latest_frame = None
                repub_handle = asyncio.get_running_loop().call_later(
                    0.005, ing_ka.publish, ka_frame, (160, 128, "contain", 0)
                )
                return
            await orig_sleep(0)

        with monkeypatch.context() as mp:
            mp.setattr(hub_mod.asyncio, "sleep", _race_sleep)
            assert await anext(gen_ka) == ka_frame
            assert race_fired is True
        if repub_handle is not None:
            repub_handle.cancel()
        await gen_ka.aclose()
        await hub._async_stop_ingest(ing_ka)

        # 7) Grid label overrides, unexpected slot error, first-frame waiter cancellation, and 2nd-frame pacing sleep
        assert hub._resolve_grid_labels(
            ["camera.driveway", "camera.patio"], {"camera.driveway": "Driveway Custom"}
        ) == ["Driveway Custom", "Patio"]

        with monkeypatch.context() as mp:

            async def _sub_boom(*_a: Any, **_kw: Any) -> Any:
                raise RuntimeError("subscribe error")

            mp.setattr(hub, "_subscribe", _sub_boom)
            assert await hub._async_try_subscribe_grid_slot(
                "camera.bad", (160, 128, 5), "contain"
            ) == (None, None)

        # Two delayed snapshot cameras so async_iter_grid_frames exercises first-frame waiter + 2nd frame pacing
        async def _delayed_grid_img(_h: Any, eid: str, **_kw: Any) -> ha_camera.Image:
            await orig_sleep(0.015 if eid == "camera.g_fast" else 0.25)
            return ha_camera.Image("image/jpeg", make_jpeg_bytes(160, 128))

        with monkeypatch.context() as mp:
            mp.setattr(ha_camera, "async_get_image", _delayed_grid_img)
            mp.setattr(
                ha_camera,
                "async_get_stream_source",
                lambda _h, _e: orig_sleep(0, result=None),
            )
            mp.setattr(ha_camera, "async_get_mjpeg_stream", None, raising=False)
            grid_gen = hub.async_iter_grid_frames(
                ["camera.g_fast", "camera.g_slow"],
                320,
                240,
                fps=15,
                label_overrides={"camera.g_fast": "Fast Cam"},
            )
            gf1 = await anext(grid_gen)
            gf2 = await anext(grid_gen)
            assert inspect_jpeg_header(gf1)[1:] == (320, 240)
            assert inspect_jpeg_header(gf2)[1:] == (320, 240)
            await grid_gen.aclose()

        # Grid producer error propagation & lock-missing unsubscribe fallback
        err_prod = hub_mod._GridProducer(
            key=(("camera.err",), 320, 240, 5, "contain", ("Err",)),
            cams=("camera.err",),
            labels=("Err",),
            out_w=320,
            out_h=240,
            fps=5,
            fit_mode="contain",
            stale_after_s=5.0,
        )
        err_prod.publish_error(RuntimeError("grid compose failed"))
        with pytest.raises(CameraFetchError, match="grid compose failed"):
            await hub._async_wait_next_grid_frame(err_prod, 0.01)
        tok = object()
        err_prod.subscribers.add(tok)
        await hub._async_unsubscribe_grid(err_prod, tok)
        assert err_prod.closed is True
    finally:
        await hub.async_shutdown()
