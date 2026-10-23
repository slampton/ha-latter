"""Universal Baseline-JPEG Artwork & Wallpaper Transcoder Proxy Views for Latter."""

from __future__ import annotations

from collections import OrderedDict
from http import HTTPStatus
import io
import logging
from pathlib import Path

from aiohttp import web
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url

from .const import (
    API_ARTWORK_PROXY_PATH,
    API_IMAGE_PROXY_PATH,
    API_WALLPAPER_PROXY_PATH,
    DOMAIN,
)
from .coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)

MAX_ART_CACHE_ENTRIES = 16
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

    norm_slug = target_id_or_slug.strip().lower().replace("-", "_")
    coordinators = [
        v for v in domain_data.values() if isinstance(v, LatterCoordinator)
    ]
    for coord in coordinators:
        if coord.device_slug == norm_slug:
            return coord
    return coordinators[0] if coordinators else None


async def _async_serve_speaker_artwork(
    hass: HomeAssistant,
    request: web.Request,
    coordinator: LatterCoordinator,
    require_token: bool = False,
) -> web.Response:
    """Fetch active speaker artwork, transcode to Baseline JPEG (with RAM LRU cache), and serve over HTTP."""
    token = request.query.get("token")
    if require_token and not coordinator.verify_token(token):
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
        async with session.get(pic_url, timeout=8, allow_redirects=True) as resp:
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
        return await _async_serve_speaker_artwork(
            self.hass, request, coordinator, require_token=False
        )


class LatterImageProxyView(HomeAssistantView):
    """Backward-compatible signed image proxy view (/api/latter/image_proxy/{entry_id}?token=...)."""

    requires_auth = False
    url = API_IMAGE_PROXY_PATH
    name = "api:latter:image_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the image proxy view."""
        self.hass = hass

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        """Handle GET /api/latter/image_proxy/{entry_id}?token=..."""
        coordinator = _resolve_coordinator_by_target(self.hass, entry_id)
        if coordinator is None:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Unknown entry")
        return await _async_serve_speaker_artwork(
            self.hass, request, coordinator, require_token=True
        )


class LatterWallpaperProxyView(HomeAssistantView):
    """Serves baseline JPEG photo wallpapers (circularly masked or square based on display_shape)."""

    requires_auth = False
    url = API_WALLPAPER_PROXY_PATH
    name = "api:latter:wallpaper_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the wallpaper proxy view."""
        self.hass = hass

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        """Handle GET /api/latter/wallpaper/{entry_id}?token=..."""
        coordinator = _resolve_coordinator_by_target(self.hass, entry_id)
        if coordinator is None:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Unknown entry")

        token = request.query.get("token")
        if token and not coordinator.verify_token(token):
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")

        wp_source = coordinator.wallpaper_source
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

        cache_key = (f"wp:{wp_source}", width, height, is_circle, 0.78)
        cached_bytes = _ARTWORK_LRU_CACHE.get(cache_key)
        if cached_bytes is not None:
            _ARTWORK_LRU_CACHE.move_to_end(cache_key)
            return web.Response(
                body=cached_bytes,
                content_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=300", "X-Latter-Cache": "HIT"},
            )

        raw_bytes: bytes | None = None

        if wp_source.startswith(("/local/", "/config/www/")):
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
                async with session.get(url, timeout=8, allow_redirects=True) as resp:
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
                0.78,
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