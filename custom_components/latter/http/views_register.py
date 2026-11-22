"""Registration of all 8 local-only signed and admin HTTP views for Latter (`L3`, `M-P3-03`)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from ..const import DOMAIN
from .camera_views import (
    LatterCameraAudioStreamView,
    LatterCameraGridView,
    LatterCameraSnapshotView,
    LatterCameraStreamView,
    async_shutdown_camera_feeds,
    async_shutdown_doorbell_streams,
)
from .proxy_views import LatterArtworkTranscoderView, LatterBrandIconView
from .wallpaper_views import LatterWallpaperProxyView, LatterWallpaperUploadView

__all__ = [
    "LatterArtworkTranscoderView",
    "LatterBrandIconView",
    "LatterCameraAudioStreamView",
    "LatterCameraGridView",
    "LatterCameraSnapshotView",
    "LatterCameraStreamView",
    "LatterWallpaperProxyView",
    "LatterWallpaperUploadView",
    "async_register_http_views",
    "async_shutdown_camera_feeds",
    "async_shutdown_doorbell_streams",
]


@callback
def async_register_http_views(hass: HomeAssistant) -> None:
    """Register all 8 local-only signed/admin HTTP views once on `hass.http`."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("views_registered"):
        return
    domain_data["views_registered"] = True
    hass.http.register_view(LatterArtworkTranscoderView(hass))
    hass.http.register_view(LatterWallpaperProxyView(hass))
    hass.http.register_view(LatterWallpaperUploadView(hass))
    hass.http.register_view(LatterCameraSnapshotView(hass))
    hass.http.register_view(LatterCameraStreamView(hass))
    hass.http.register_view(LatterCameraGridView(hass))
    hass.http.register_view(LatterCameraAudioStreamView(hass))
    hass.http.register_view(LatterBrandIconView(hass))
