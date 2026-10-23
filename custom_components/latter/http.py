"""Authenticated HTTP Image & Circular Wallpaper Proxy Views for Latter."""

from __future__ import annotations

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

from .const import API_IMAGE_PROXY_PATH, API_WALLPAPER_PROXY_PATH, DOMAIN
from .coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)


def _center_crop_and_encode_jpeg(
    raw_bytes: bytes, target_size: int, circular_mask: bool = False, darken: float = 1.0
) -> bytes:
    """Decode image bytes, center-crop to square, optionally apply circular bezel mask, and encode baseline JPEG."""
    with Image.open(io.BytesIO(raw_bytes)) as img:
        img_rgb = img.convert("RGB")
        fitted = ImageOps.fit(
            img_rgb,
            (target_size, target_size),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        if darken < 1.0:
            fitted = ImageEnhance.Brightness(fitted).enhance(darken)

        if circular_mask:
            mask = Image.new("L", (target_size, target_size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, target_size - 1, target_size - 1), fill=255)
            black_bg = Image.new("RGB", (target_size, target_size), (0, 0, 0))
            fitted = Image.composite(fitted, black_bg, mask)

        out = io.BytesIO()
        fitted.save(out, format="JPEG", quality=82, optimize=True, progressive=False)
        return out.getvalue()


class LatterImageProxyView(HomeAssistantView):
    """Serves resized 466x466 baseline JPEGs to ESP32-S3 online_image over signed URL."""

    requires_auth = False
    url = API_IMAGE_PROXY_PATH
    name = "api:latter:image_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the image proxy view."""
        self.hass = hass

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        """Handle GET /api/latter/image_proxy/{entry_id}?token=..."""
        domain_data = self.hass.data.get(DOMAIN, {})
        coordinator: LatterCoordinator | None = domain_data.get(entry_id)
        if not isinstance(coordinator, LatterCoordinator):
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Unknown entry")

        token = request.query.get("token")
        if not coordinator.verify_token(token):
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")

        state_obj = self.hass.states.get(coordinator.active_speaker)
        pic_path = None
        if state_obj is not None:
            pic_path = (
                state_obj.attributes.get("entity_picture_local")
                or state_obj.attributes.get("entity_picture")
            )
        if not pic_path and coordinator.last_valid_raw_pic:
            pic_path = coordinator.last_valid_raw_pic

        if not pic_path:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="No artwork")

        pic_url = str(pic_path)
        if pic_url.startswith("/"):
            try:
                base_url = get_url(
                    self.hass, allow_internal=True, prefer_external=False
                )
            except Exception:  # noqa: BLE001
                base_url = "http://127.0.0.1:8123"
            pic_url = f"{base_url}{pic_url}"

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(pic_url, timeout=8) as resp:
                if resp.status != HTTPStatus.OK:
                    return web.Response(
                        status=HTTPStatus.BAD_GATEWAY,
                        text=f"Upstream returned {resp.status}",
                    )
                raw_bytes = await resp.read()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed fetching artwork from %s: %s", pic_url, err)
            return web.Response(status=HTTPStatus.BAD_GATEWAY, text="Upstream error")

        circular = request.query.get("mask") == "circle"
        try:
            jpeg_bytes = await self.hass.async_add_executor_job(
                _center_crop_and_encode_jpeg,
                raw_bytes,
                coordinator.art_size,
                circular,
                1.0,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Pillow decode/resize failed: %s", err)
            return web.Response(
                status=HTTPStatus.UNPROCESSABLE_ENTITY, text="Image processing error"
            )

        return web.Response(
            body=jpeg_bytes,
            content_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=300"},
        )


class LatterWallpaperProxyView(HomeAssistantView):
    """Serves pre-masked 466x466 circular baseline JPEG photo wallpapers to ESP32-S3 online_image."""

    requires_auth = False
    url = API_WALLPAPER_PROXY_PATH
    name = "api:latter:wallpaper_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the circular wallpaper proxy view."""
        self.hass = hass

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        """Handle GET /api/latter/wallpaper/{entry_id}?token=..."""
        domain_data = self.hass.data.get(DOMAIN, {})
        coordinator: LatterCoordinator | None = domain_data.get(entry_id)
        if not isinstance(coordinator, LatterCoordinator):
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Unknown entry")

        token = request.query.get("token")
        if not coordinator.verify_token(token):
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")

        wp_source = coordinator.wallpaper_source
        if not wp_source:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="No wallpaper configured")

        raw_bytes: bytes | None = None

        # Support local /config/www/... or /local/... files or HTTP(S) URLs
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
                async with session.get(url, timeout=8) as resp:
                    if resp.status == HTTPStatus.OK:
                        raw_bytes = await resp.read()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Failed fetching wallpaper from %s: %s", url, err)

        if not raw_bytes:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Wallpaper source unreadable")

        try:
            jpeg_bytes = await self.hass.async_add_executor_job(
                _center_crop_and_encode_jpeg,
                raw_bytes,
                coordinator.art_size,
                True,
                0.78,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Wallpaper Pillow processing failed: %s", err)
            return web.Response(
                status=HTTPStatus.UNPROCESSABLE_ENTITY, text="Wallpaper processing error"
            )

        return web.Response(
            body=jpeg_bytes,
            content_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=300"},
        )