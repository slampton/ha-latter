"""Scoped, expiring HMAC-SHA256 resource URL signer and LAN URL builders for Latter."""

from __future__ import annotations

import hashlib
import socket
import time
from urllib.parse import quote_plus, urlparse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url

from .resource_signing import (
    ON_DEMAND_TTL_SECONDS,
    PAYLOAD_TTL_DAYS,
    day_bucketed_expiry,
    exact_expiry,
    sign,
    verify,
)


class UrlSigner:
    """Signs and verifies Device-scoped HMAC-SHA256 resource URLs (day-bucketed or exact expiry)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        hmac_secret: bytes,
    ) -> None:
        """Initialize the URL signer for a specific Latter device entry."""
        self.hass = hass
        self.entry_id = entry_id
        self._hmac_secret = hmac_secret
        self._cached_lan_base_url: str | None = None

    def invalidate_lan_base_url(self) -> None:
        """Invalidate the cached numeric LAN base URL when HA network config changes."""
        self._cached_lan_base_url = None

    def sign_payload_resource(
        self, resource: str, ttl_days: int = PAYLOAD_TTL_DAYS
    ) -> str:
        """Sign a resource whose URL is embedded in a payload: day-bucketed, so it is identical all UTC day."""
        exp = day_bucketed_expiry(int(time.time()), ttl_days)
        return sign(self._hmac_secret, self.entry_id, resource, exp)

    def sign_on_demand_resource(
        self, resource: str, ttl_s: int = ON_DEMAND_TTL_SECONDS
    ) -> str:
        """Sign a resource whose URL is minted on demand and never embedded in a payload: exact expiry."""
        exp = exact_expiry(int(time.time()), ttl_s)
        return sign(self._hmac_secret, self.entry_id, resource, exp)

    def verify_resource(self, resource: str, sig: str | None = None) -> bool:
        """Verify a resource-scoped expiring signature (either mode)."""
        return verify(
            self._hmac_secret, self.entry_id, resource, sig, int(time.time())
        )

    def get_lan_base_url(self) -> str:
        """Resolve the numeric-IP LAN HTTP base URL and active HTTP port for ESP32 online_image clients."""
        if self._cached_lan_base_url:
            return self._cached_lan_base_url

        active_port = getattr(getattr(self.hass, "http", None), "server_port", None)
        raw_url = ""
        try:
            raw_url = get_url(self.hass, allow_internal=True, prefer_external=False)
        except Exception:  # noqa: BLE001
            raw_url = ""

        parsed = urlparse(raw_url) if raw_url else None
        host = (parsed.hostname or "") if parsed else ""
        port = parsed.port if (parsed and parsed.port) else active_port
        scheme = (parsed.scheme or "http") if parsed else "http"

        if not host or host.endswith(".local") or host == "localhost":
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.connect(("10.254.254.254", 1))
                    host = sock.getsockname()[0]
            except Exception:  # noqa: BLE001
                host = host or "homeassistant.local"
            scheme = "http"
            port = active_port

        if port and not (
            (scheme == "http" and int(port) == 80)
            or (scheme == "https" and int(port) == 443)
        ):
            resolved = f"{scheme}://{host}:{int(port)}"
        else:
            resolved = f"{scheme}://{host}"
        self._cached_lan_base_url = resolved
        return resolved

    def build_camera_snapshot_url(
        self,
        device_slug: str,
        camera_entity_id: str | None,
        width: int,
        height: int,
        shape: str,
        cache_bust: str = "",
    ) -> str:
        """Build the local LAN HTTP Baseline-JPEG camera snapshot URL for ESP32 online_image."""
        cam_ent = (camera_entity_id or "").strip()
        if not cam_ent:
            return "none"
        base_url = self.get_lan_base_url()
        sig = self.sign_payload_resource(f"camera:{cam_ent}|{width}|{height}|{shape}")
        v_tag = cache_bust or sig[:8]
        return (
            f"{base_url}/api/latter/camera/{device_slug}"
            f"?entity_id={cam_ent}&w={width}&h={height}&shape={shape}&sig={sig}&v={v_tag}"
        )

    def build_map_snapshot_url(
        self,
        device_slug: str,
        location: str,
        width: int,
        height: int,
        shape: str,
    ) -> str:
        """Build the local LAN HTTP Baseline-JPEG map snapshot URL for a calendar event location."""
        clean_loc = (location or "").strip()
        if not clean_loc:
            return "none"
        base_url = self.get_lan_base_url()
        sig = self.sign_payload_resource(f"map:{clean_loc}|{width}|{height}|{shape}")
        return (
            f"{base_url}/api/latter/map/{device_slug}"
            f"?w={width}&h={height}&shape={shape}&q={quote_plus(clean_loc)}&sig={sig}"
        )

    def build_wallpaper_url(
        self,
        device_slug: str,
        wallpaper_source: str,
        width: int,
        height: int,
        shape: str,
    ) -> str:
        """Build the device-scoped Baseline-JPEG photo wallpaper URL."""
        clean_src = (wallpaper_source or "").strip()
        if not clean_src:
            return "none"
        base_url = self.get_lan_base_url()
        sig = self.sign_payload_resource(f"wallpaper:{clean_src}|{width}|{height}|{shape}")
        digest = hashlib.md5(
            f"{clean_src}|{shape}|{width}x{height}".encode("utf-8")
        ).hexdigest()[:10]
        return (
            f"{base_url}/api/latter/wallpaper/{device_slug}"
            f"?w={width}&h={height}&shape={shape}&sig={sig}&v={digest}"
        )

    def build_proxy_art_url(
        self,
        device_slug: str,
        width: int,
        height: int,
        shape: str,
        cache_bust: str,
    ) -> str:
        """Build the universal Baseline-JPEG artwork URL."""
        base_url = self.get_lan_base_url()
        sig = self.sign_payload_resource(f"artwork|{width}|{height}|{shape}")
        digest = hashlib.md5(cache_bust.encode("utf-8")).hexdigest()[:10]
        return (
            f"{base_url}/api/latter/artwork/{device_slug}"
            f"?w={width}&h={height}&shape={shape}&sig={sig}&v={digest}"
        )
