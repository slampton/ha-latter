"""Constant-time HMAC-SHA256 resource signing and LAN URL builders (`L1a`)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import hashlib
import hmac
import time
from typing import Final
from urllib.parse import quote, urlparse

from homeassistant.components import network as ha_network
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url

from ..const import (
    DAY_NIGHT_SKY_NATIVE_URL,
    DAY_NIGHT_SKY_PRESET_ID,
    DOMAIN,
    normalize_noise_reduction,
)

SIG_BUCKET_SECONDS: Final[int] = 86400
PAYLOAD_TTL_DAYS: Final[int] = 2
ON_DEMAND_TTL_SECONDS: Final[int] = 600
LAN_BASE_URL_TTL_SECONDS: Final[float] = 300.0
_MAC_HEX_CHARS: Final[int] = 32
_PROBED_LAN_IP_KEY: Final = "_probed_lan_ip"
_HTTP_DEFAULT_PORT: Final = 80
_HTTPS_DEFAULT_PORT: Final = 443
_MIN_PREVIEW_DIM: Final = 32
_MAX_PREVIEW_DIM: Final = 240

_CROP_HASH_RESOLVER: Callable[[str], str] | None = None


def register_crop_hash_resolver(resolver: Callable[[str], str]) -> None:
    """Register the `L1b` photo crop-hash resolver without importing `wallpapers` upward in `L1a`."""
    global _CROP_HASH_RESOLVER
    _CROP_HASH_RESOLVER = resolver


def day_bucketed_expiry(now_s: int, ttl_days: int) -> int:
    """Return the first UTC midnight at least `ttl_days` days after `now_s`."""
    if ttl_days < 1:
        raise ValueError("ttl_days must be >= 1")
    return (int(now_s) // SIG_BUCKET_SECONDS + ttl_days + 1) * SIG_BUCKET_SECONDS


def exact_expiry(now_s: int, ttl_s: int) -> int:
    """Return an expiry exactly `ttl_s` seconds after `now_s`."""
    if ttl_s < 1:
        raise ValueError("ttl_s must be >= 1")
    return int(now_s) + int(ttl_s)


def _mac(secret: bytes, scope: str, resource: str, exp: str) -> str:
    msg = f"{scope}|{resource}|{exp}".encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()[:_MAC_HEX_CHARS]


def sign(secret: bytes, scope: str, resource: str, exp: int) -> str:
    """Return the `<exp>.<mac>` signature binding `scope`, `resource`, and `exp`."""
    exp_s = str(int(exp))
    return f"{exp_s}.{_mac(secret, scope, resource, exp_s)}"


def verify(
    secret: bytes, scope: str, resource: str, sig: str | None, now_s: int
) -> bool:
    """Return True if `sig` is an unexpired signature for `scope` + `resource` (constant-time MAC compare)."""
    if not sig or "." not in sig:
        return False
    exp_s, mac = sig.split(".", 1)
    if not exp_s.isascii() or not exp_s.isdigit():
        return False
    if int(exp_s) < int(now_s):
        return False
    expected = _mac(secret, scope, resource, exp_s)
    return hmac.compare_digest(mac.encode("utf-8"), expected.encode("utf-8"))


def camera_allowlist_hash(allowed_cameras: Iterable[str]) -> str:
    """Return an 8-hex-char digest binding a Device's ordered visible camera allow-list."""
    joined = ",".join(str(c).strip() for c in allowed_cameras if str(c).strip())
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8]


class UrlSigner:
    """Signs and verifies scoped HMAC-SHA256 resource URLs with zero event-loop socket calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        hmac_secret: bytes,
    ) -> None:
        """Initialize the URL signer for a specific Latter device subentry or system scope."""
        self.hass = hass
        self.entry_id = entry_id
        self._hmac_secret = hmac_secret
        self._cached_lan_base_url: str | None = None
        self._cached_lan_base_url_mono: float = 0.0

    def invalidate_lan_base_url(self) -> None:
        """Invalidate the cached numeric LAN base URL when HA network config changes."""
        self._cached_lan_base_url = None
        self._cached_lan_base_url_mono = 0.0
        domain_data = self.hass.data.get(DOMAIN)
        if isinstance(domain_data, dict):
            domain_data.pop(_PROBED_LAN_IP_KEY, None)

    async def async_prime_lan_base_url(self) -> str:
        """Asynchronously resolve and cache the numeric LAN IP via HA's network adapter registry."""
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        if not domain_data.get(_PROBED_LAN_IP_KEY):
            try:
                probed = await ha_network.async_get_source_ip(self.hass)
            except Exception:  # noqa: BLE001
                probed = ""
            if probed:
                domain_data[_PROBED_LAN_IP_KEY] = str(probed)
        self._cached_lan_base_url = None
        self._cached_lan_base_url_mono = 0.0
        return self.get_lan_base_url()

    def sign_payload_resource(
        self, resource: str, ttl_days: int = PAYLOAD_TTL_DAYS
    ) -> str:
        """Sign a resource whose URL is embedded in a payload: day-bucketed, identical all UTC day."""
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
        """Resolve the numeric-IP LAN HTTP base URL purely from memory / HA config with a 300 s TTL."""
        now_m = time.monotonic()
        if (
            self._cached_lan_base_url
            and (now_m - self._cached_lan_base_url_mono) < LAN_BASE_URL_TTL_SECONDS
        ):
            return self._cached_lan_base_url

        active_port = getattr(getattr(self.hass, "http", None), "server_port", None)
        try:
            raw_url = get_url(self.hass, allow_internal=True, prefer_external=False)
        except Exception:  # noqa: BLE001
            raw_url = ""

        parsed = urlparse(raw_url) if raw_url else None
        host = (parsed.hostname or "") if parsed else ""
        port = parsed.port if (parsed and parsed.port) else active_port
        scheme = (parsed.scheme or "http") if parsed else "http"

        if not host or host.endswith(".local") or host == "localhost":
            domain_data = self.hass.data.get(DOMAIN, {})
            cached_ip = (
                str(domain_data.get(_PROBED_LAN_IP_KEY) or "")
                if isinstance(domain_data, dict)
                else ""
            )
            host = cached_ip or host or "homeassistant.local"
            scheme = "http"
            port = active_port

        if port and not (
            (scheme == "http" and int(port) == _HTTP_DEFAULT_PORT)
            or (scheme == "https" and int(port) == _HTTPS_DEFAULT_PORT)
        ):
            resolved = f"{scheme}://{host}:{int(port)}"
        else:
            resolved = f"{scheme}://{host}"
        self._cached_lan_base_url = resolved
        self._cached_lan_base_url_mono = now_m
        return resolved

    def build_camera_snapshot_url(  # noqa: PLR0913, PLR0917
        self,
        device_slug: str,
        camera_entity_id: str | None,
        width: int,
        height: int,
        shape: str,
        cache_bust: str = "",
    ) -> str:
        """Build the local LAN HTTP Baseline-JPEG camera snapshot URL for ESP32 `online_image`."""
        cam_ent = (camera_entity_id or "").strip()
        if not cam_ent:
            return ""
        base_url = self.get_lan_base_url()
        sig = self.sign_payload_resource(f"camera:{cam_ent}|{width}|{height}|{shape}")
        v_tag = cache_bust or sig[:8]
        return (
            f"{base_url}/api/latter/camera/{device_slug}"
            f"?entity_id={cam_ent}&w={width}&h={height}&shape={shape}&sig={sig}&v={v_tag}"
        )

    def build_camera_allowlist_snapshot_url(  # noqa: PLR0913, PLR0917
        self,
        device_slug: str,
        allowed_cameras: Iterable[str],
        camera_entity_id: str | None,
        width: int,
        height: int,
        shape: str,
        cache_bust: str = "",
    ) -> str:
        """Build an allowlist-scoped Baseline-JPEG snapshot URL permitting switching across visible cameras."""
        cams = [str(c).strip() for c in allowed_cameras if str(c).strip()]
        if not cams:
            return ""
        cam_ent = (camera_entity_id or cams[0]).strip()
        base_url = self.get_lan_base_url()
        allow_hash = camera_allowlist_hash(cams)
        sig = self.sign_payload_resource(
            f"camera_allow:{allow_hash}|{width}|{height}|{shape}"
        )
        v_tag = cache_bust or sig[:8]
        return (
            f"{base_url}/api/latter/camera/{device_slug}"
            f"?entity_id={cam_ent}&w={width}&h={height}&shape={shape}&sig={sig}&v={v_tag}"
        )

    def build_camera_stream_url(
        self,
        device_slug: str,
        allowed_cameras: Iterable[str],
        max_w: int,
        max_h: int,
        max_fps: int,
    ) -> str:
        """Build the 48h signed base URL for live MJPEG single and 2x2 grid camera streaming."""
        cams = [str(c).strip() for c in allowed_cameras if str(c).strip()]
        if not cams or int(max_w) <= 0 or int(max_h) <= 0:
            return ""
        base_url = self.get_lan_base_url()
        allow_hash = camera_allowlist_hash(cams)
        sig = self.sign_payload_resource(
            f"camera_stream:{allow_hash}|{int(max_w)}|{int(max_h)}|{int(max_fps)}"
        )
        return f"{base_url}/api/latter/camera_stream/{device_slug}?sig={sig}"

    def build_camera_audio_url(
        self,
        device_slug: str,
        camera_entity_id: str | None,
        nr_level: str,
        fmt: str = "flac",
    ) -> str:
        """Build the on-demand LAN HTTP camera audio stream URL signing `camera_audio:<entity>|<nr>|<fmt>`."""
        cam_ent = (camera_entity_id or "").strip()
        if not cam_ent:
            return ""
        nr_norm = normalize_noise_reduction(nr_level)
        fmt_norm = "wav" if str(fmt or "").strip().lower() == "wav" else "flac"
        base_url = self.get_lan_base_url()
        sig = self.sign_on_demand_resource(
            f"camera_audio:{cam_ent}|{nr_norm}|{fmt_norm}"
        )
        return (
            f"{base_url}/api/latter/camera_audio/{device_slug}"
            f"?entity_id={cam_ent}&nr={nr_norm}&fmt={fmt_norm}"
            f"&v={int(time.time())}&sig={sig}"
        )

    def build_wallpaper_url(  # noqa: PLR0913
        self,
        device_slug: str,
        wallpaper_source: str,
        width: int,
        height: int,
        shape: str,
        *,
        mode: str = "wallpaper",
        crop_hash: str = "",
    ) -> str:
        """Build the device-scoped Baseline-JPEG wallpaper or screensaver photo URL."""
        clean_src = (wallpaper_source or "").strip()
        if not clean_src:
            return ""
        clean_mode = (
            "screensaver"
            if str(mode or "").strip().lower() == "screensaver"
            else "wallpaper"
        )
        if clean_mode == "wallpaper" and clean_src == DAY_NIGHT_SKY_PRESET_ID:
            return DAY_NIGHT_SKY_NATIVE_URL
        base_url = self.get_lan_base_url()
        sig = self.sign_payload_resource(
            f"wallpaper:{clean_src}|{width}|{height}|{shape}|{clean_mode}"
        )
        c_hash = crop_hash or (
            _CROP_HASH_RESOLVER(clean_src) if _CROP_HASH_RESOLVER is not None else ""
        )
        digest = hashlib.md5(
            f"{clean_src}|{shape}|{width}x{height}|{clean_mode}|{c_hash}".encode(),
            usedforsecurity=False,
        ).hexdigest()[:10]
        return (
            f"{base_url}/api/latter/wallpaper/{device_slug}"
            f"?w={width}&h={height}&shape={shape}&mode={clean_mode}"
            f"&src={quote(clean_src, safe='')}&sig={sig}&v={digest}"
        )

    def build_media_preview_url(
        self,
        root: str,
        relpath: str,
        width: int = 160,
        height: int = 160,
    ) -> str:
        """Build a short-lived (600 s) signed thumbnail URL for an HA `/media` file."""
        clean_root = str(root or "").strip()
        clean_rel = str(relpath or "").strip()
        if not clean_root or not clean_rel:
            return ""
        w = max(_MIN_PREVIEW_DIM, min(_MAX_PREVIEW_DIM, int(width)))
        h = max(_MIN_PREVIEW_DIM, min(_MAX_PREVIEW_DIM, int(height)))
        sig = self.sign_on_demand_resource(
            f"media_preview:{clean_root}|{clean_rel}|{w}|{h}",
            ttl_s=ON_DEMAND_TTL_SECONDS,
        )
        return (
            f"/api/latter/wallpaper/system"
            f"?media_root={quote(clean_root, safe='')}"
            f"&media_path={quote(clean_rel, safe='')}"
            f"&w={w}&h={h}&sig={sig}"
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
        digest = hashlib.md5(
            cache_bust.encode("utf-8"), usedforsecurity=False
        ).hexdigest()[:10]
        return (
            f"{base_url}/api/latter/artwork/{device_slug}"
            f"?w={width}&h={height}&shape={shape}&sig={sig}&v={digest}"
        )
