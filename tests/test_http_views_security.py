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
from custom_components.latter.const import (
    CONF_CAMERA_ENTITIES,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
)
from custom_components.latter.http.resource_signing import (
    ON_DEMAND_TTL_SECONDS,
    PAYLOAD_TTL_DAYS,
    day_bucketed_expiry,
    exact_expiry,
    sign,
    verify,
)
from custom_components.latter.http.views import (
    MAX_UPSTREAM_IMAGE_BYTES,
    MAX_WALLPAPER_UPLOAD_BYTES,
    LatterArtworkTranscoderView,
    LatterBrandIconView,
    LatterCameraSnapshotView,
    LatterMapSnapshotView,
    LatterWallpaperProxyView,
    LatterWallpaperUploadView,
)
from custom_components.latter.http.wallpapers import (
    async_refresh_wallpaper_cache,
    delete_uploaded_wallpaper,
)


def _make_jpeg_bytes(w: int = 64, h: int = 64) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (40, 90, 160)).save(buf, format="JPEG")
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
        if self._file_bytes is None or self._offset >= len(self._file_bytes):
            return b""
        chunk = self._file_bytes[self._offset : self._offset + size]
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

    # 1) Zero-device hub setup -> 'system' wallpaper preview signing MUST work
    entry0, sys0, coord0 = await setup_latter_hub(hass, with_device=False)
    assert coord0 is None
    wp_view = LatterWallpaperProxyView(hass)
    sys_sig = sys0.url_signer.sign_payload_resource("wallpaper:preset:aurora|466|466|square")
    resp_sys = await wp_view.get(
        _make_get_request(f"/api/latter/wallpaper/system?src=preset:aurora&w=466&h=466&sig={sys_sig}"),
        "system",
    )
    assert resp_sys.status == 200
    assert resp_sys.content_type == "image/jpeg"

    resp_bad_sig = await wp_view.get(
        _make_get_request("/api/latter/wallpaper/system?src=preset:aurora&w=466&h=466&sig=invalid"),
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

    # Valid device-scoped upload (200)
    jpeg_raw = _make_jpeg_bytes(120, 120)
    r_200_dev = await upload_view.post(
        _MultipartRequest(
            is_admin=True,
            parts=[
                _MultipartPart("subentry_id", text_val=coord.subentry_id),
                _MultipartPart("file", file_bytes=jpeg_raw, filename="sunset.jpg"),
            ],
        )
    )
    assert r_200_dev.status == 200
    body_dev = json.loads(r_200_dev.body.decode("utf-8"))
    assert body_dev["ok"] is True
    uploaded_src = body_dev["source_id"]
    assert coord.wallpaper_source == uploaded_src

    # Proxy serves the uploaded wallpaper & hits LRU cache on second request
    dev_sig = coord.sign_payload_resource(f"wallpaper:{uploaded_src}|466|466|circle")
    r_wp_miss = await wp_view2.get(
        _make_get_request(
            f"/api/latter/wallpaper/{coord.device_slug}?src={uploaded_src}&w=466&h=466&sig={dev_sig}"
        ),
        coord.device_slug,
    )
    assert r_wp_miss.status == 200
    assert r_wp_miss.headers["X-Latter-Cache"] == "MISS"

    r_wp_hit = await wp_view2.get(
        _make_get_request(
            f"/api/latter/wallpaper/{coord.device_slug}?src={uploaded_src}&w=466&h=466&sig={dev_sig}"
        ),
        coord.device_slug,
    )
    assert r_wp_hit.status == 200
    assert r_wp_hit.headers["X-Latter-Cache"] == "HIT"

    # Delete uploaded wallpaper
    assert delete_uploaded_wallpaper(hass2, coord.device_slug, uploaded_src) is True
    await async_refresh_wallpaper_cache(hass2, coord.device_slug)
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

    # SSRF private/loopback external URL blocked (403)
    hass.states.async_set(
        coord.active_speaker,
        "playing",
        {"entity_picture": "http://169.254.169.254/latest/meta-data"},
    )
    r_ssrf = await art_view.get(
        _make_get_request(f"/api/latter/artwork/{coord.device_slug}?w=466&h=466&sig={art_sig}"),
        coord.device_slug,
    )
    assert r_ssrf.status == 403

    # > 8 MB upstream image rejected (413)
    hass.states.async_set(
        coord.active_speaker,
        "playing",
        {"entity_picture": "http://93.184.216.34/huge.jpg"},
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

    # Valid public artwork transcoded & cached
    valid_jpeg = _make_jpeg_bytes(100, 100)
    hass.states.async_set(
        coord.active_speaker,
        "playing",
        {"entity_picture": "http://93.184.216.34/cover.jpg"},
    )
    hass.data["_mock_http_get"] = lambda _url, **_kw: _MockHttpResponse(
        status=200,
        body=valid_jpeg,
        content_length=len(valid_jpeg),
    )
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

    # 3) Map Snapshot View: zone.home ignored, non-home zone.office resolved, pan_x/pan_y clamped to ±4
    map_view = LatterMapSnapshotView(hass)
    hass.states.async_set(
        "zone.home",
        "0",
        {"friendly_name": "Home", "latitude": 37.80, "longitude": -122.27},
    )
    hass.states.async_set(
        "zone.office",
        "0",
        {"friendly_name": "Office", "latitude": 37.79, "longitude": -122.40},
    )
    tile_png = _make_png_bytes(256, 256)

    def _map_http_mock(url: str, **_kw: Any) -> _MockHttpResponse:
        if "nominatim" in url:
            return _MockHttpResponse(status=200, json_data=[])
        return _MockHttpResponse(status=200, body=tile_png)

    hass.data["_mock_http_get"] = _map_http_mock

    # Querying 'Home' must NOT resolve zone.home coordinates -> 404 when Nominatim returns empty
    home_sig = coord.sign_payload_resource("map:Home|466|466|circle")
    r_home_ignored = await map_view.get(
        _make_get_request(f"/api/latter/map/{coord.device_slug}?q=Home&w=466&h=466&shape=circle&sig={home_sig}"),
        coord.device_slug,
    )
    assert r_home_ignored.status == 404

    # Non-home zone 'Office' resolves & extreme pan_x=99 clamps identically to pan_x=4!
    off_sig = coord.sign_payload_resource("map:Office|466|466|circle")
    r_pan_99 = await map_view.get(
        _make_get_request(
            f"/api/latter/map/{coord.device_slug}?q=Office&pan_x=99&pan_y=-99&w=466&h=466&shape=circle&sig={off_sig}"
        ),
        coord.device_slug,
    )
    assert r_pan_99.status == 200
    assert r_pan_99.headers["X-Latter-Cache"] == "MISS"

    # Requesting pan_x=4&pan_y=-4 MUST hit the exact same cache key as pan_x=99&pan_y=-99!
    r_pan_4 = await map_view.get(
        _make_get_request(
            f"/api/latter/map/{coord.device_slug}?q=Office&pan_x=4&pan_y=-4&w=466&h=466&shape=circle&sig={off_sig}"
        ),
        coord.device_slug,
    )
    assert r_pan_4.status == 200
    assert r_pan_4.headers["X-Latter-Cache"] == "HIT"

    # 4) Brand Icon View
    brand_view = LatterBrandIconView(hass)
    r_icon = await brand_view.get(_make_get_request("/api/latter/brand/icon.png"))
    assert r_icon.status == 200
    assert r_icon.content_type == "image/png"

    # Unload shuts down _LiveCameraFeeds cleanly
    assert await async_unload_entry(hass, entry) is True
    assert cam_view._live._feeds == {}
