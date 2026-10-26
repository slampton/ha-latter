"""Universal Baseline-JPEG Artwork, Wallpaper & Camera Peephole Transcoder Views for Latter."""

from __future__ import annotations

from collections import OrderedDict
from http import HTTPStatus
import io
import logging
from pathlib import Path

from aiohttp import ClientTimeout, web
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url

from .const import (
    API_ARTWORK_PROXY_PATH,
    API_CAMERA_PROXY_PATH,
    API_MAP_PROXY_PATH,
    API_WALLPAPER_PROXY_PATH,
    DOMAIN,
    normalize_device_slug,
)
from .coordinator import LatterCoordinator
from .wallpaper_engine import render_builtin_preset_bytes

_LOGGER = logging.getLogger(__name__)

MAX_ART_CACHE_ENTRIES = 24
# (pic_url, width, height, circular_mask, darken) -> encoded_baseline_jpeg_bytes
_ARTWORK_LRU_CACHE: OrderedDict[tuple[str, int, int, bool, float], bytes] = OrderedDict()


def _transcode_to_baseline_jpeg(
    raw_bytes: bytes,
    width: int,
    height: int,
    circular_mask: bool = False,
    darken: float = 1.0,
) -> bytes:
    """Decode any image format (PNG/WebP/Progressive JPEG/GIF), resize to (w, h), and encode non-progressive Baseline JPEG."""
    with Image.open(io.BytesIO(raw_bytes)) as img:
        img_rgb = img.convert("RGB")
        fitted = ImageOps.fit(
            img_rgb,
            (width, height),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        if darken < 1.0:
            fitted = ImageEnhance.Brightness(fitted).enhance(darken)

        if circular_mask:
            mask = Image.new("L", (width, height), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, width - 1, height - 1), fill=255)
            black_bg = Image.new("RGB", (width, height), (0, 0, 0))
            fitted = Image.composite(fitted, black_bg, mask)

        out = io.BytesIO()
        fitted.save(
            out,
            format="JPEG",
            quality=85,
            optimize=True,
            progressive=False,
        )
        return out.getvalue()


def _resolve_coordinator_by_target(
    hass: HomeAssistant, target_id_or_slug: str
) -> LatterCoordinator | None:
    """Resolve a LatterCoordinator by config entry_id or ESPHome device_slug."""
    domain_data = hass.data.get(DOMAIN, {})
    direct = domain_data.get(target_id_or_slug)
    if isinstance(direct, LatterCoordinator):
        return direct

    norm_slug = normalize_device_slug(target_id_or_slug)
    coordinators = [
        v for v in domain_data.values() if isinstance(v, LatterCoordinator)
    ]
    for coord in coordinators:
        if coord.device_slug == norm_slug:
            return coord
    return coordinators[0] if len(coordinators) == 1 else None


async def _async_serve_speaker_artwork(
    hass: HomeAssistant,
    request: web.Request,
    coordinator: LatterCoordinator,
) -> web.Response:
    """Fetch active speaker artwork, transcode to Baseline JPEG (with RAM LRU cache), and serve over HTTP."""
    token = request.query.get("token")
    if token and not coordinator.verify_token(token):
        return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")

    default_dim = coordinator.art_size
    try:
        width = max(32, min(1200, int(request.query.get("w") or default_dim)))
        height = max(32, min(1200, int(request.query.get("h") or width)))
    except ValueError:
        width, height = default_dim, default_dim

    circular = request.query.get("mask") == "circle" or request.query.get("shape") == "circle"

    state_obj = hass.states.get(coordinator.active_speaker)
    pic_path = None
    if state_obj is not None:
        attrs = state_obj.attributes
        pic_path = (
            attrs.get("entity_picture_local")
            or attrs.get("entity_picture")
            or attrs.get("media_image_url")
        )
    if not pic_path and coordinator.last_valid_raw_pic:
        pic_path = coordinator.last_valid_raw_pic

    if not pic_path:
        return web.Response(status=HTTPStatus.NOT_FOUND, text="No artwork")

    pic_url = str(pic_path)
    if pic_url.startswith("/"):
        try:
            base_url = get_url(
                hass, allow_internal=True, prefer_external=False
            )
        except Exception:  # noqa: BLE001
            base_url = "http://127.0.0.1:8123"
        pic_url = f"{base_url}{pic_url}"

    cache_key = (pic_url, width, height, circular, 1.0)
    cached_bytes = _ARTWORK_LRU_CACHE.get(cache_key)
    if cached_bytes is not None:
        _ARTWORK_LRU_CACHE.move_to_end(cache_key)
        return web.Response(
            body=cached_bytes,
            content_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=300", "X-Latter-Cache": "HIT"},
        )

    session = async_get_clientsession(hass)
    try:
        async with session.get(pic_url, timeout=ClientTimeout(total=8), allow_redirects=True) as resp:
            if resp.status != HTTPStatus.OK:
                return web.Response(
                    status=HTTPStatus.BAD_GATEWAY,
                    text=f"Upstream returned {resp.status}",
                )
            raw_bytes = await resp.read()
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Failed fetching artwork from %s: %s", pic_url, err)
        return web.Response(status=HTTPStatus.BAD_GATEWAY, text="Upstream error")

    try:
        jpeg_bytes = await hass.async_add_executor_job(
            _transcode_to_baseline_jpeg,
            raw_bytes,
            width,
            height,
            circular,
            1.0,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Pillow decode/resize failed: %s", err)
        return web.Response(
            status=HTTPStatus.UNPROCESSABLE_ENTITY, text="Image processing error"
        )

    _ARTWORK_LRU_CACHE[cache_key] = jpeg_bytes
    if len(_ARTWORK_LRU_CACHE) > MAX_ART_CACHE_ENTRIES:
        _ARTWORK_LRU_CACHE.popitem(last=False)

    return web.Response(
        body=jpeg_bytes,
        content_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=300", "X-Latter-Cache": "MISS"},
    )


class LatterArtworkTranscoderView(HomeAssistantView):
    """Universal Baseline-JPEG artwork proxy (/api/latter/artwork/{target_device}?w=466&h=466&v=...)."""

    requires_auth = False
    url = API_ARTWORK_PROXY_PATH
    name = "api:latter:artwork_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the universal artwork transcoder view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Handle GET /api/latter/artwork/{target_device}?w=...&h=...&v=..."""
        coordinator = _resolve_coordinator_by_target(self.hass, target_device)
        if coordinator is None:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Unknown target device")
        return await _async_serve_speaker_artwork(self.hass, request, coordinator)


class LatterWallpaperProxyView(HomeAssistantView):
    """Serves baseline JPEG photo or procedural AMOLED wallpapers (/api/latter/wallpaper/{target_device}?w=...&h=...)."""

    requires_auth = False
    url = API_WALLPAPER_PROXY_PATH
    name = "api:latter:wallpaper_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the wallpaper proxy view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Handle GET /api/latter/wallpaper/{target_device}?w=...&h=...&src=..."""
        coordinator = _resolve_coordinator_by_target(self.hass, target_device)
        if coordinator is None:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Unknown target device")

        token = request.query.get("token")
        if token and not coordinator.verify_token(token):
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")

        wp_source = str(request.query.get("src") or coordinator.wallpaper_source).strip()
        if not wp_source:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="No wallpaper configured")

        default_dim = coordinator.art_size
        try:
            width = max(32, min(1200, int(request.query.get("w") or default_dim)))
            height = max(32, min(1200, int(request.query.get("h") or width)))
        except ValueError:
            width, height = default_dim, default_dim

        is_circle = coordinator.display_shape == "circle"
        if request.query.get("shape") in ("circle", "square"):
            is_circle = request.query.get("shape") == "circle"

        darken_factor = 1.0 if wp_source.startswith("preset:") else 0.78
        cache_key = (f"wp:{wp_source}", width, height, is_circle, darken_factor)
        cached_bytes = _ARTWORK_LRU_CACHE.get(cache_key)
        if cached_bytes is not None:
            _ARTWORK_LRU_CACHE.move_to_end(cache_key)
            return web.Response(
                body=cached_bytes,
                content_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=300", "X-Latter-Cache": "HIT"},
            )

        raw_bytes: bytes | None = None

        if wp_source.startswith("preset:"):
            raw_bytes = await self.hass.async_add_executor_job(
                render_builtin_preset_bytes, wp_source, width, height
            )
        elif wp_source.startswith(("/local/", "/config/www/")):
            rel = wp_source.replace("/local/", "").replace("/config/www/", "").lstrip("/")
            local_file = Path(self.hass.config.path("www")) / rel
            if local_file.is_file():
                raw_bytes = await self.hass.async_add_executor_job(
                    local_file.read_bytes
                )
        elif wp_source.startswith(("http://", "https://", "/")):
            url = wp_source
            if url.startswith("/"):
                try:
                    base_url = get_url(
                        self.hass, allow_internal=True, prefer_external=False
                    )
                except Exception:  # noqa: BLE001
                    base_url = "http://127.0.0.1:8123"
                url = f"{base_url}{url}"
            session = async_get_clientsession(self.hass)
            try:
                async with session.get(url, timeout=ClientTimeout(total=8), allow_redirects=True) as resp:
                    if resp.status == HTTPStatus.OK:
                        raw_bytes = await resp.read()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Failed fetching wallpaper from %s: %s", url, err)

        if not raw_bytes:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Wallpaper source unreadable")

        try:
            jpeg_bytes = await self.hass.async_add_executor_job(
                _transcode_to_baseline_jpeg,
                raw_bytes,
                width,
                height,
                is_circle,
                darken_factor,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Wallpaper Pillow processing failed: %s", err)
            return web.Response(
                status=HTTPStatus.UNPROCESSABLE_ENTITY, text="Wallpaper processing error"
            )

        _ARTWORK_LRU_CACHE[cache_key] = jpeg_bytes
        if len(_ARTWORK_LRU_CACHE) > MAX_ART_CACHE_ENTRIES:
            _ARTWORK_LRU_CACHE.popitem(last=False)

        return web.Response(
            body=jpeg_bytes,
            content_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=300", "X-Latter-Cache": "MISS"},
        )


class LatterCameraSnapshotView(HomeAssistantView):
    """Fetches a live frame from any Home Assistant camera.* entity and transcodes to Baseline JPEG (/api/latter/camera/{target_device})."""

    requires_auth = False
    url = API_CAMERA_PROXY_PATH
    name = "api:latter:camera_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the camera snapshot transcoder view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Handle GET /api/latter/camera/{target_device}?entity_id=camera.front_door&w=466&h=466&shape=circle"""
        coordinator = _resolve_coordinator_by_target(self.hass, target_device)
        if coordinator is None:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Unknown target device")

        token = request.query.get("token")
        if token and not coordinator.verify_token(token):
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")

        cam_entity = str(
            request.query.get("entity_id") or coordinator.camera_entity or ""
        ).strip()
        if not cam_entity or not cam_entity.startswith("camera."):
            return web.Response(status=HTTPStatus.NOT_FOUND, text="No camera entity specified")

        default_dim = coordinator.art_size
        try:
            width = max(32, min(1200, int(request.query.get("w") or default_dim)))
            height = max(32, min(1200, int(request.query.get("h") or width)))
        except ValueError:
            width, height = default_dim, default_dim

        is_circle = coordinator.display_shape == "circle"
        if request.query.get("shape") in ("circle", "square"):
            is_circle = request.query.get("shape") == "circle"

        try:
            from homeassistant.components import camera

            image_obj = await camera.async_get_image(
                self.hass, cam_entity, timeout=8
            )
            raw_bytes = image_obj.content
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Camera snapshot fetch failed for %s: %s", cam_entity, err)
            return web.Response(
                status=HTTPStatus.BAD_GATEWAY, text="Camera snapshot unavailable"
            )

        try:
            jpeg_bytes = await self.hass.async_add_executor_job(
                _transcode_to_baseline_jpeg,
                raw_bytes,
                width,
                height,
                is_circle,
                1.0,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Camera snapshot Pillow transcode failed: %s", err)
            return web.Response(
                status=HTTPStatus.UNPROCESSABLE_ENTITY, text="Camera image processing error"
            )

        return web.Response(
            body=jpeg_bytes,
            content_type="image/jpeg",
            headers={"Cache-Control": "no-store, max-age=0"},
        )


_MAP_GEOCODE_CACHE: dict[str, tuple[float, float]] = {}
_MAP_JPEG_CACHE: OrderedDict[str, bytes] = OrderedDict()


def _latlon_to_tile_xy(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Convert (lat, lon) in degrees to fractional Web Mercator tile coordinates at zoom."""
    import math

    lat_rad = math.radians(max(-85.0511, min(85.0511, lat)))
    n = float(1 << zoom)
    xtile = (lon + 180.0) / 360.0 * n
    ytile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return xtile, ytile


def _compose_map_snapshot_jpeg(
    tile_images: dict[tuple[int, int], bytes],
    center_tx: float,
    center_ty: float,
    base_tx: int,
    base_ty: int,
    width: int,
    height: int,
    circular_mask: bool,
    label: str,
) -> bytes:
    """Stitch 3x3 256px map tiles centered on (center_tx, center_ty), draw a vector map pin, and encode Baseline JPEG."""
    canvas = Image.new("RGB", (768, 768), (20, 26, 36))
    tiles_loaded = 0
    for dy in range(3):
        for dx in range(3):
            raw = tile_images.get((base_tx + dx, base_ty + dy))
            if raw:
                try:
                    with Image.open(io.BytesIO(raw)) as t_img:
                        canvas.paste(t_img.convert("RGB"), (dx * 256, dy * 256))
                        tiles_loaded += 1
                except Exception:  # noqa: BLE001
                    pass

    draw_c = ImageDraw.Draw(canvas)
    if tiles_loaded == 0:
        # Offline fallback vector radar grid
        for g in range(0, 768, 48):
            draw_c.line([(g, 0), (g, 768)], fill=(32, 42, 56), width=1)
            draw_c.line([(0, g), (768, g)], fill=(32, 42, 56), width=1)

    px = int((center_tx - base_tx) * 256.0)
    py = int((center_ty - base_ty) * 256.0)

    half_w = width // 2
    half_h = height // 2
    left = max(0, min(768 - width, px - half_w))
    top = max(0, min(768 - height, py - half_h))
    cropped = canvas.crop((left, top, left + width, top + height))

    pin_x = px - left
    pin_y = py - top
    d = ImageDraw.Draw(cropped)

    # Outer accuracy halo + drop shadow + sculpted crimson/gold vector map pin
    d.ellipse(
        (pin_x - 28, pin_y - 28, pin_x + 28, pin_y + 28),
        outline=(56, 152, 255),
        width=2,
    )
    d.ellipse(
        (pin_x - 6, pin_y - 3, pin_x + 6, pin_y + 5),
        fill=(10, 14, 20),
    )
    d.polygon(
        [(pin_x, pin_y), (pin_x - 13, pin_y - 22), (pin_x + 13, pin_y - 22)],
        fill=(235, 52, 62),
    )
    d.ellipse(
        (pin_x - 14, pin_y - 36, pin_x + 14, pin_y - 8),
        fill=(235, 52, 62),
        outline=(255, 255, 255),
        width=2,
    )
    d.ellipse(
        (pin_x - 5, pin_y - 27, pin_x + 5, pin_y - 17),
        fill=(255, 255, 255),
    )

    if circular_mask:
        mask = Image.new("L", (width, height), 0)
        md = ImageDraw.Draw(mask)
        md.ellipse((0, 0, width - 1, height - 1), fill=255)
        black_bg = Image.new("RGB", (width, height), (0, 0, 0))
        cropped = Image.composite(cropped, black_bg, mask)

    out = io.BytesIO()
    cropped.save(out, format="JPEG", quality=86, optimize=True, progressive=False)
    return out.getvalue()


class LatterMapSnapshotView(HomeAssistantView):
    """Geocodes an address or HA zone and renders a 466x466 Baseline-JPEG map snapshot (/api/latter/map/{target_device})."""

    requires_auth = False
    url = API_MAP_PROXY_PATH
    name = "api:latter:map_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the map snapshot view."""
        self.hass = hass

    async def _async_resolve_coordinates(self, query: str) -> tuple[float, float]:
        """Resolve an address string, 'lat,lon', or HA zone name to (lat, lon)."""
        q_clean = query.strip()
        if not q_clean:
            return float(self.hass.config.latitude or 37.8044), float(
                self.hass.config.longitude or -122.2712
            )

        cache_key = q_clean.lower()
        if cache_key in _MAP_GEOCODE_CACHE:
            return _MAP_GEOCODE_CACHE[cache_key]

        # 1. Check if query is already "lat,lon"
        if "," in q_clean:
            parts = [p.strip() for p in q_clean.split(",", 1)]
            try:
                lat_v = float(parts[0])
                lon_v = float(parts[1])
                if -90.0 <= lat_v <= 90.0 and -180.0 <= lon_v <= 180.0:
                    _MAP_GEOCODE_CACHE[cache_key] = (lat_v, lon_v)
                    return lat_v, lon_v
            except ValueError:
                pass

        # 2. Check Home Assistant zone.* entities
        for st in self.hass.states.async_all("zone"):
            z_name = str(st.attributes.get("friendly_name") or st.name or "").lower()
            if z_name and (z_name in cache_key or cache_key in z_name):
                lat_z = st.attributes.get("latitude")
                lon_z = st.attributes.get("longitude")
                if lat_z is not None and lon_z is not None:
                    coords = (float(lat_z), float(lon_z))
                    _MAP_GEOCODE_CACHE[cache_key] = coords
                    return coords

        # 3. Geocode via OpenStreetMap Nominatim
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q_clean, "format": "json", "limit": "1"},
                headers={"User-Agent": "HomeAssistant-Latter-Companion/1.9"},
                timeout=ClientTimeout(total=5),
            ) as resp:
                if resp.status == HTTPStatus.OK:
                    data = await resp.json()
                    if isinstance(data, list) and data:
                        lat_n = float(data[0]["lat"])
                        lon_n = float(data[0]["lon"])
                        _MAP_GEOCODE_CACHE[cache_key] = (lat_n, lon_n)
                        return lat_n, lon_n
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Nominatim geocode fallback for '%s': %s", q_clean, err)

        return float(self.hass.config.latitude or 37.8044), float(
            self.hass.config.longitude or -122.2712
        )

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Handle GET /api/latter/map/{target_device}?q=1900+Broadway+Oakland&w=466&h=466&shape=circle"""
        coordinator = _resolve_coordinator_by_target(self.hass, target_device)
        default_dim = coordinator.art_size if coordinator else 466
        try:
            width = max(128, min(768, int(request.query.get("w") or default_dim)))
            height = max(128, min(768, int(request.query.get("h") or width)))
        except ValueError:
            width, height = default_dim, default_dim

        is_circle = (coordinator.display_shape == "circle") if coordinator else True
        if request.query.get("shape") in ("circle", "square"):
            is_circle = request.query.get("shape") == "circle"

        query = str(request.query.get("q") or "").strip()
        zoom = 15
        try:
            if request.query.get("z"):
                zoom = max(10, min(18, int(request.query.get("z", "15"))))
        except ValueError:
            zoom = 15

        cache_id = f"{query.lower()}|{width}x{height}|{int(is_circle)}|z{zoom}"
        if cache_id in _MAP_JPEG_CACHE:
            _MAP_JPEG_CACHE.move_to_end(cache_id)
            return web.Response(
                body=_MAP_JPEG_CACHE[cache_id],
                content_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=600", "X-Latter-Cache": "HIT"},
            )

        lat, lon = await self._async_resolve_coordinates(query)
        center_tx, center_ty = _latlon_to_tile_xy(lat, lon, zoom)
        base_tx = int(center_tx) - 1
        base_ty = int(center_ty) - 1

        import asyncio

        session = async_get_clientsession(self.hass)
        tile_images: dict[tuple[int, int], bytes] = {}
        n_tiles = 1 << zoom

        async def _fetch_single_tile(gx: int, gy: int) -> None:
            tx = gx % n_tiles
            if gy < 0 or gy >= n_tiles:
                return
            tile_url = f"https://tile.openstreetmap.org/{zoom}/{tx}/{gy}.png"
            try:
                async with session.get(
                    tile_url,
                    headers={
                        "User-Agent": "HomeAssistant-Latter/1.9.3 (+https://github.com/slampton/ha-latter)",
                        "Accept": "image/png,image/*;q=0.8",
                    },
                    timeout=ClientTimeout(total=4.0),
                ) as t_resp:
                    if t_resp.status == HTTPStatus.OK:
                        tile_images[(gx, gy)] = await t_resp.read()
            except Exception:  # noqa: BLE001
                pass

        await asyncio.gather(
            *[
                _fetch_single_tile(base_tx + dx, base_ty + dy)
                for dy in range(3)
                for dx in range(3)
            ]
        )

        jpeg_bytes = await self.hass.async_add_executor_job(
            _compose_map_snapshot_jpeg,
            tile_images,
            center_tx,
            center_ty,
            base_tx,
            base_ty,
            width,
            height,
            is_circle,
            query,
        )

        _MAP_JPEG_CACHE[cache_id] = jpeg_bytes
        while len(_MAP_JPEG_CACHE) > MAX_ART_CACHE_ENTRIES:
            _MAP_JPEG_CACHE.popitem(last=False)

        return web.Response(
            body=jpeg_bytes,
            content_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=600", "X-Latter-Cache": "MISS"},
        )