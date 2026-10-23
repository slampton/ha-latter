"""Authenticated HTTP Image Proxy View for Latter (466x466 JPEG downscaler)."""

from __future__ import annotations

import io
import logging
from http import HTTPStatus

from aiohttp import web
from PIL import Image, ImageOps

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url

from .const import API_IMAGE_PROXY_PATH, DOMAIN
from .coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)


def _center_crop_and_encode_jpeg(raw_bytes: bytes, target_size: int) -> bytes:
    """Decode arbitrary image bytes, center-crop to square, and encode baseline JPEG."""
    with Image.open(io.BytesIO(raw_bytes)) as img:
        img_rgb = img.convert("RGB")
        fitted = ImageOps.fit(
            img_rgb,
            (target_size, target_size),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
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
        if state_obj is None:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Speaker unavailable")

        pic_path = (
            state_obj.attributes.get("entity_picture_local")
            or state_obj.attributes.get("entity_picture")
        )
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

        try:
            jpeg_bytes = await self.hass.async_add_executor_job(
                _center_crop_and_encode_jpeg, raw_bytes, coordinator.art_size
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