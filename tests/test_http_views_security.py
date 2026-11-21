"""Integration tests for Latter HTTP views, HMAC resource signing, 15 MB upload cap, 8 MB stream cap, SSRF blocking, and map pan clamping."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

from PIL import Image
import pytest

from custom_components.latter import async_unload_entry
from custom_components.latter.cameras import DATA_CAMERA_HUB
from custom_components.latter.const import (
    CONF_CAMERA_ENTITIES,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
)
from custom_components.latter.http import (
    MAX_UPSTREAM_IMAGE_BYTES,
    MAX_WALLPAPER_UPLOAD_BYTES,
    ON_DEMAND_TTL_SECONDS,
    PAYLOAD_TTL_DAYS,
    LatterArtworkTranscoderView,
    LatterBrandIconView,
    LatterCameraGridView,
    LatterCameraSnapshotView,
    LatterCameraStreamView,
    LatterWallpaperProxyView,
    LatterWallpaperUploadView,
    day_bucketed_expiry,
    exact_expiry,
    sign,
    verify,
)
from custom_components.latter.wallpapers import (
    DAY_NIGHT_SKY_PRESET_ID,
    async_refresh_wallpaper_cache,
    create_collection,
    delete_photo,
)


def _make_jpeg_bytes(w: int = 64, h: int = 64) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (40, 90, 160)).save(buf, format="JPEG", progressive=False)
    return buf.getvalue()


def _make_png_bytes(w: int = 256, h: int = 256) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 50, 70)).save(buf, format="PNG")
    return buf.getvalue()


def _make_get_request(url: str) -> Any:
    parsed = urlsplit(url)
    query = {k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
    return SimpleNamespace(query=query, headers={})


class _MockContent:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    async def iter_chunked(self, size: int = 65536) -> Any:
        for idx in range(0, len(self._payload), size):
            yield self._payload[idx : idx + size]


class _MockHttpResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        body: bytes = b"",
        json_data: Any = None,
        content_length: int | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self._json_data = json_data
        self.content_length = content_length
        self.content = _MockContent(body)

    async def __aenter__(self) -> _MockHttpResponse:
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        return None

    async def read(self) -> bytes:
        return self._body

    async def json(self) -> Any:
        return self._json_data


class _MultipartPart:
    def __init__(
        self,
        name: str,
        *,
        text_val: str = "",
        file_bytes: bytes | None = None,
        filename: str = "photo.jpg",
        oversize_chunks: int = 0,
    ) -> None:
        self.name = name
        self._text_val = text_val
        self._file_bytes = file_bytes
        self.filename = filename
        self._offset = 0
        self._oversize_chunks = oversize_chunks

    async def text(self) -> str:
        return self._text_val

    async def read_chunk(self, size: int = 65536) -> bytes:
        if self._oversize_chunks > 0:
            self._oversize_chunks -= 1
            return b"\xFF" * size
        buf = self._file_bytes if self._file_bytes is not None else self._text_val.encode("utf-8")
        if self._offset >= len(buf):
            return b""
        chunk = buf[self._offset : self._offset + size]
        self._offset += size
        return chunk

    async def release(self) -> None:
        return None


class _MultipartReader:
    def __init__(self, parts: list[_MultipartPart]) -> None:
        self._parts = list(parts)

    async def next(self) -> _MultipartPart | None:
        return self._parts.pop(0) if self._parts else None


class _MultipartRequest:
    def __init__(
        self,
        *,
        is_admin: bool = True,
        parts: list[_MultipartPart] | None = None,
        content_length: int | None = None,
        query: dict[str, str] | None = None,
    ) -> None:
        self._user = SimpleNamespace(is_admin=is_admin) if is_admin is not None else None
        self._parts = parts
        self.content_length = content_length
        self.query = query or {}

    def get(self, key: str, default: Any = None) -> Any:
        if key == "hass_user":
            return self._user
        return default

    async def multipart(self) -> _MultipartReader:
        if self._parts is None:
            raise ValueError("Not multipart")
        return _MultipartReader(self._parts)


@pytest.mark.asyncio
async def test_hmac_rotation_and_wallpaper_upload_and_proxy_views(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify 48h rotatable HMAC signing, zero-device 'system' wallpaper preview, and 15 MB multipart upload cap."""
    assert PAYLOAD_TTL_DAYS == 2
    assert ON_DEMAND_TTL_SECONDS == 600
    assert MAX_WALLPAPER_UPLOAD_BYTES == 15 * 1024 * 1024

    # Pure signing & expiry verification
    exp_day = day_bucketed_expiry(1_000_000, PAYLOAD_TTL_DAYS)
    sig_day = sign(b"secret_a", "pocket", "wallpaper:preset:aurora|466|466|circle", exp_day)
    assert verify(b"secret_a", "pocket", "wallpaper:preset:aurora|466|466|circle", sig_day, 1_000_060)
    assert not verify(b"secret_b", "pocket", "wallpaper:preset:aurora|466|466|circle", sig_day, 1_000_060)

    exp_short = exact_expiry(1_000_000, ON_DEMAND_TTL_SECONDS)
    sig_ondemand = sign(b"secret_a", "pocket", "camera_audio:camera.front", exp_short)
    assert not verify(b"secret_a", "pocket", "camera_audio:camera.front", sig_ondemand, 1_001_000)

    # 1) Zero-device hub setup -> 'system' wallpaper preview signing MUST work (binding mode!)
    entry0, sys0, coord0 = await setup_latter_hub(hass, with_device=False)
    assert coord0 is None
    wp_view = LatterWallpaperProxyView(hass)
    sys_sig = sys0.url_signer.sign_payload_resource(
        "wallpaper:preset:forest_mountains|466|466|square|wallpaper"
    )
    resp_sys = await wp_view.get(
        _make_get_request(
            f"/api/latter/wallpaper/system?src=preset:forest_mountains&w=466&h=466&mode=wallpaper&sig={sys_sig}"
        ),
        "system",
    )
    assert resp_sys.status == 200
    assert resp_sys.content_type == "image/jpeg"

    # Cross-mode signature reuse must fail (403)
    resp_wrong_mode = await wp_view.get(
        _make_get_request(
            f"/api/latter/wallpaper/system?src=preset:forest_mountains&w=466&h=466&mode=screensaver&sig={sys_sig}"
        ),
        "system",
    )
    assert resp_wrong_mode.status == 403

    # Day & Night Sky split preview & live sun.sun screensaver render
    dns_split_sig = sys0.url_signer.sign_payload_resource(
        f"wallpaper:{DAY_NIGHT_SKY_PRESET_ID}|240|240|square|wallpaper"
    )
    resp_dns_split = await wp_view.get(
        _make_get_request(
            f"/api/latter/wallpaper/system?src={DAY_NIGHT_SKY_PRESET_ID}&w=240&h=240&mode=wallpaper&sig={dns_split_sig}"
        ),
        "system",
    )
    assert resp_dns_split.status == 200
    assert resp_dns_split.content_type == "image/jpeg"

    hass.states.async_set("sun.sun", "below_horizon")
    dns_ss_sig = sys0.url_signer.sign_payload_resource(
        f"wallpaper:{DAY_NIGHT_SKY_PRESET_ID}|240|240|square|screensaver"
    )
    resp_dns_ss = await wp_view.get(
        _make_get_request(
            f"/api/latter/wallpaper/system?src={DAY_NIGHT_SKY_PRESET_ID}&w=240&h=240&mode=screensaver&sig={dns_ss_sig}"
        ),
        "system",
    )
    assert resp_dns_ss.status == 200

    resp_bad_sig = await wp_view.get(
        _make_get_request("/api/latter/wallpaper/system?src=preset:forest_mountains&w=466&h=466&sig=invalid"),
        "system",
    )
    assert resp_bad_sig.status == 403
    assert await async_unload_entry(hass, entry0) is True

    # 2) Device setup + LatterWallpaperUploadView RBAC, size cap, validation, and catalog update
    hass2 = type(hass)(config_dir=hass.config.config_dir)
    entry, _sys_obj, coord = await setup_latter_hub(hass2, with_device=True)
    upload_view = LatterWallpaperUploadView(hass2)
    wp_view2 = LatterWallpaperProxyView(hass2)

    # Non-admin rejected (403)
    r_403 = await upload_view.post(_MultipartRequest(is_admin=False, parts=[]))
    assert r_403.status == 403

    # Non-multipart rejected (400)
    r_400_bad = await upload_view.post(_MultipartRequest(is_admin=True, parts=None))
    assert r_400_bad.status == 400

    # Missing file rejected (400)
    r_400_empty = await upload_view.post(
        _MultipartRequest(is_admin=True, parts=[_MultipartPart("scope", text_val="system")])
    )
    assert r_400_empty.status == 400

    # Oversized Content-Length rejected (413)
    r_413_hdr = await upload_view.post(
        _MultipartRequest(is_admin=True, parts=[], content_length=MAX_WALLPAPER_UPLOAD_BYTES + 200_000)
    )
    assert r_413_hdr.status == 413

    # Oversized streaming chunks > 15 MB rejected (413)
    r_413_stream = await upload_view.post(
        _MultipartRequest(
            is_admin=True,
            parts=[_MultipartPart("file", oversize_chunks=(MAX_WALLPAPER_UPLOAD_BYTES // 65536) + 2)],
        )
    )
    assert r_413_stream.status == 413

    # Corrupt image rejected (422)
    r_422 = await upload_view.post(
        _MultipartRequest(
            is_admin=True,
            parts=[_MultipartPart("file", file_bytes=b"NOT_AN_IMAGE_PAYLOAD", filename="bad.jpg")],
        )
    )
    assert r_422.status == 422

    # Unknown subentry_id on device-scoped upload returns 404
    jpeg_raw = _make_jpeg_bytes(120, 120)
    r_404_unknown = await upload_view.post(
        _MultipartRequest(
            is_admin=True,
            parts=[
                _MultipartPart("scope", text_val="device"),
                _MultipartPart("subentry_id", text_val="sub_unknown_ghost"),
                _MultipartPart("file", file_bytes=jpeg_raw, filename="ghost.jpg"),
            ],
        )
    )
    assert r_404_unknown.status == 404

    # Valid device-scoped upload with crop, name, and collection metadata (200)
    col_rec = create_collection(hass2, "Uploads")
    r_200_dev = await upload_view.post(
        _MultipartRequest(
            is_admin=True,
            parts=[
                _MultipartPart("subentry_id", text_val=coord.subentry_id),
                _MultipartPart("crop_x", text_val="0.3"),
                _MultipartPart("crop_y", text_val="0.7"),
                _MultipartPart("crop_zoom", text_val="1.5"),
                _MultipartPart("name", text_val="Golden Sunset"),
                _MultipartPart("collection_id", text_val=col_rec["id"]),
                _MultipartPart("file", file_bytes=jpeg_raw, filename="sunset.jpg"),
            ],
        )
    )
    assert r_200_dev.status == 200
    body_dev = json.loads(r_200_dev.body.decode("utf-8"))
    assert body_dev["ok"] is True
    uploaded_src = body_dev["source_id"]
    assert uploaded_src.startswith("photo:")
    assert body_dev["photo"]["name"] == "Golden Sunset"
    assert body_dev["photo"]["crop"] == {"x": 0.3, "y": 0.7, "zoom": 1.5}
    assert body_dev["photo"]["collections"] == [col_rec["id"]]
    assert coord.wallpaper_source == uploaded_src

    # Proxy serves the uploaded wallpaper & hits LRU cache on second request
    dev_sig = coord.sign_payload_resource(
        f"wallpaper:{uploaded_src}|466|466|circle|wallpaper"
    )
    r_wp_miss = await wp_view2.get(
        _make_get_request(
            f"/api/latter/wallpaper/{coord.device_slug}?src={uploaded_src}&w=466&h=466&mode=wallpaper&sig={dev_sig}"
        ),
        coord.device_slug,
    )
    assert r_wp_miss.status == 200
    assert r_wp_miss.headers["X-Latter-Cache"] == "MISS"

    r_wp_hit = await wp_view2.get(
        _make_get_request(
            f"/api/latter/wallpaper/{coord.device_slug}?src={uploaded_src}&w=466&h=466&mode=wallpaper&sig={dev_sig}"
        ),
        coord.device_slug,
    )
    assert r_wp_hit.status == 200
    assert r_wp_hit.headers["X-Latter-Cache"] == "HIT"

    # Screensaver mode (darken=1.0) serves brighter pixels than wallpaper mode (darken=0.78)
    ss_sig = coord.sign_payload_resource(
        f"wallpaper:{uploaded_src}|466|466|square|screensaver"
    )
    r_ss = await wp_view2.get(
        _make_get_request(
            f"/api/latter/wallpaper/{coord.device_slug}?src={uploaded_src}&w=466&h=466&shape=square&mode=screensaver&sig={ss_sig}"
        ),
        coord.device_slug,
    )
    assert r_ss.status == 200
    with (
        Image.open(io.BytesIO(r_wp_miss.body)) as im_wp,
        Image.open(io.BytesIO(r_ss.body)) as im_ss,
    ):
        assert sum(im_ss.getpixel((233, 233))) > sum(im_wp.getpixel((233, 233)))

    # Studio original mode & separate thumbnail LRU cache (<= 240 px)
    orig_sig = coord.sign_payload_resource(
        f"wallpaper:{uploaded_src}|1200|1200|square|original"
    )
    r_orig = await wp_view2.get(
        _make_get_request(
            f"/api/latter/wallpaper/{coord.device_slug}?src={uploaded_src}&w=1200&h=1200&shape=square&mode=original&sig={orig_sig}"
        ),
        coord.device_slug,
    )
    assert r_orig.status == 200

    # Signed `/media` preview thumbnail security check
    from pathlib import Path

    media_dir = Path(hass2.config.config_dir) / "media_test"
    media_dir.mkdir(parents=True, exist_ok=True)
    (media_dir / "sample.jpg").write_bytes(jpeg_raw)
    hass2.config.media_dirs = {"local": str(media_dir)}
    m_url = _sys_obj.url_signer.build_media_preview_url("local", "sample.jpg", 160, 160)
    r_media_ok = await wp_view2.get(_make_get_request(m_url), "system")
    assert r_media_ok.status == 200
    assert r_media_ok.content_type == "image/jpeg"
    # Traversal attempt rejected (404 / 403)
    bad_m_sig = _sys_obj.url_signer.sign_on_demand_resource(
        "media_preview:local|../secret.jpg|160|160", ttl_s=600
    )
    r_media_trav = await wp_view2.get(
        _make_get_request(
            f"/api/latter/wallpaper/system?media_root=local&media_path=../secret.jpg&w=160&h=160&sig={bad_m_sig}"
        ),
        "system",
    )
    assert r_media_trav.status == 404

    # 720x720 square display manifest serves native 720x720 album art and 720x720 wallpapers
    hass2.states.async_set(
        f"sensor.{coord.device_slug}_system_hardware_manifest",
        json.dumps({"v": 2, "contract": 3, "w": 720, "h": 720, "shape": "square", "display": 1}),
    )
    assert coord.art_dimensions == (720, 720)
    assert coord.wallpaper_dimensions == (720, 720)
    wp_720_url = coord.build_wallpaper_url()
    assert "w=720&h=720&shape=square&mode=wallpaper" in wp_720_url
    r_wp_720 = await wp_view2.get(_make_get_request(wp_720_url), coord.device_slug)
    assert r_wp_720.status == 200
    with Image.open(io.BytesIO(r_wp_720.body)) as img_720:
        assert img_720.size == (720, 720)

    # Omitting w/h query params on wallpaper proxy also defaults to coordinator.wallpaper_dimensions (720x720)
    sig_720 = parse_qs(urlsplit(wp_720_url).query)["sig"][0]
    r_wp_720_default = await wp_view2.get(
        _make_get_request(
            f"/api/latter/wallpaper/{coord.device_slug}?src={uploaded_src}&shape=square&mode=wallpaper&sig={sig_720}"
        ),
        coord.device_slug,
    )
    assert r_wp_720_default.status == 200
    with Image.open(io.BytesIO(r_wp_720_default.body)) as img_720_def:
        assert img_720_def.size == (720, 720)

    # Delete uploaded photo (canonical System signature without device_slug)
    assert delete_photo(hass2, uploaded_src) is True
    await async_refresh_wallpaper_cache(hass2)
    assert await async_unload_entry(hass2, entry) is True


@pytest.mark.asyncio
async def test_artwork_camera_map_and_brand_icon_views(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify 8 MB artwork cap, SSRF host blocking, camera allow-list + live feed shutdown, map pan ±4 clamp (no Home Pin), and brand icon."""
    assert MAX_UPSTREAM_IMAGE_BYTES == 8 * 1024 * 1024

    entry, _sys_obj, coord = await setup_latter_hub(hass)

    # 1) Artwork Transcoder View: SSRF block, 8 MB cap, valid transcode + LRU hit
    art_view = LatterArtworkTranscoderView(hass)
    art_sig = coord.sign_payload_resource("artwork|466|466|square")

    # External HTTP/HTTPS artwork URL blocked (403 — Zero-WAN local-only artwork)
    hass.states.async_set(
        coord.active_speaker,
        "playing",
        {"entity_picture": "http://93.184.216.34/cover.jpg"},
    )
    r_ssrf = await art_view.get(
        _make_get_request(f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"),
        coord.device_slug,
    )
    assert r_ssrf.status == 403

    # > 8 MB local HA proxy image rejected (413)
    hass.states.async_set(
        coord.active_speaker,
        "playing",
        {"entity_picture": "/api/media_player_proxy/media_player.pocket_assistant_music?token=huge"},
    )
    hass.data["_mock_http_get"] = lambda _url, **_kw: _MockHttpResponse(
        status=200,
        body=b"x",
        content_length=MAX_UPSTREAM_IMAGE_BYTES + 1024,
    )
    r_8mb = await art_view.get(
        _make_get_request(f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"),
        coord.device_slug,
    )
    assert r_8mb.status == 413

    # Valid local HA proxy artwork transcoded & cached (allow_redirects=False)
    valid_jpeg = _make_jpeg_bytes(100, 100)
    seen_art_kwargs: list[dict[str, Any]] = []
    hass.states.async_set(
        coord.active_speaker,
        "playing",
        {"entity_picture": "/api/media_player_proxy/media_player.pocket_assistant_music?token=ok1"},
    )

    def _local_art_get(_url: str, **kw: Any) -> _MockHttpResponse:
        seen_art_kwargs.append(dict(kw))
        return _MockHttpResponse(
            status=200,
            body=valid_jpeg,
            content_length=len(valid_jpeg),
        )

    hass.data["_mock_http_get"] = _local_art_get
    r_art_ok = await art_view.get(
        _make_get_request(f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"),
        coord.device_slug,
    )
    assert r_art_ok.status == 200
    assert r_art_ok.headers["X-Latter-Cache"] == "MISS"

    r_art_hit = await art_view.get(
        _make_get_request(f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"),
        coord.device_slug,
    )
    assert r_art_hit.status == 200
    assert r_art_hit.headers["X-Latter-Cache"] == "HIT"

    # 2) Camera Snapshot View: allow-list check, rotation check, live feed poll, and clean unload
    cam_view = LatterCameraSnapshotView(hass)
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_CAMERA_ENTITIES] = ["camera.porch"]
    hass.states.async_set("camera.porch", "streaming", {"friendly_name": "Porch"})

    unlisted_sig = coord.sign_payload_resource("camera:camera.hidden|466|466|circle")
    r_unlisted = await cam_view.get(
        _make_get_request(
            f"/api/latter/camera/{coord.device_slug}?entity_id=camera.hidden&w=466&h=466&shape=circle&sig={unlisted_sig}"
        ),
        coord.device_slug,
    )
    assert r_unlisted.status == 404

    cam_sig = coord.sign_payload_resource("camera:camera.porch|466|466|circle")
    r_bad_rot = await cam_view.get(
        _make_get_request(
            f"/api/latter/camera/{coord.device_slug}?entity_id=camera.porch&w=466&h=466&shape=circle&rot=45&sig={cam_sig}"
        ),
        coord.device_slug,
    )
    assert r_bad_rot.status == 400

    r_cam_ok = await cam_view.get(
        _make_get_request(
            f"/api/latter/camera/{coord.device_slug}?entity_id=camera.porch&w=466&h=466&shape=circle&rot=90&sig={cam_sig}"
        ),
        coord.device_slug,
    )
    assert r_cam_ok.status == 200
    assert r_cam_ok.content_type == "image/jpeg"
    assert r_cam_ok.body.startswith(b"\xff\xd8")

    # 3) Protocol-relative //evil.example.com artwork path is also blocked (403)
    assert seen_art_kwargs and seen_art_kwargs[0].get("allow_redirects") is False
    hass.states.async_set(
        coord.active_speaker,
        "playing",
        {"entity_picture": "//evil.example.com/cover.jpg"},
    )
    r_proto_rel = await art_view.get(
        _make_get_request(f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"),
        coord.device_slug,
    )
    assert r_proto_rel.status == 403

    # 4) Brand Icon View
    brand_view = LatterBrandIconView(hass)
    r_icon = await brand_view.get(_make_get_request("/api/latter/brand/icon.png"))
    assert r_icon.status == 200
    assert r_icon.content_type == "image/png"

    # 5) Camera Stream & 2x2 Grid Views: signed allow-list, bad sig, unauthorized camera rejection, and MJPEG framing
    stream_view = LatterCameraStreamView(hass)
    grid_view = LatterCameraGridView(hass)
    stream_url = coord.build_camera_stream_url()
    assert "/api/latter/camera_stream/" in stream_url
    stream_sig = parse_qs(urlsplit(stream_url).query)["sig"][0]

    r_stream_bad_sig = await stream_view.get(
        _make_get_request(
            f"/api/latter/camera_stream/{coord.device_slug}?entity_id=camera.porch&sig=bad.sig"
        ),
        coord.device_slug,
    )
    assert r_stream_bad_sig.status == 403

    r_stream_unlisted = await stream_view.get(
        _make_get_request(
            f"/api/latter/camera_stream/{coord.device_slug}?entity_id=camera.hidden&sig={stream_sig}"
        ),
        coord.device_slug,
    )
    assert r_stream_unlisted.status == 403

    r_stream_bad_rot = await stream_view.get(
        _make_get_request(
            f"/api/latter/camera_stream/{coord.device_slug}?entity_id=camera.porch&rot=45&sig={stream_sig}"
        ),
        coord.device_slug,
    )
    assert r_stream_bad_rot.status == 400

    r_grid_bad_sig = await grid_view.get(
        _make_get_request(
            f"/api/latter/camera_grid/{coord.device_slug}?cameras=camera.porch&sig=bad.sig"
        ),
        coord.device_slug,
    )
    assert r_grid_bad_sig.status == 403

    r_grid_unlisted = await grid_view.get(
        _make_get_request(
            f"/api/latter/camera_grid/{coord.device_slug}?cameras=camera.porch,camera.hidden&sig={stream_sig}"
        ),
        coord.device_slug,
    )
    assert r_grid_unlisted.status == 403

    # Unload shuts down LatterCameraStreamHub cleanly
    assert await async_unload_entry(hass, entry) is True
    assert DATA_CAMERA_HUB not in hass.data.get(DOMAIN, {})
