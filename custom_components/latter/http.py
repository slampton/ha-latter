"""HMAC-SHA256 resource signing, LAN URL builders, and all 9 signed HTTP views for Latter."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Iterable
import hashlib
import hmac
from http import HTTPStatus
import io
import ipaddress
import logging
import math
from pathlib import Path
import shutil
import socket
import time
from typing import TYPE_CHECKING
from urllib.parse import quote_plus, urlparse, urlsplit
import wave

from aiohttp import ClientTimeout, web
from homeassistant.components import network as ha_network
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from .const import (
    API_ARTWORK_PROXY_PATH,
    API_BRAND_ICON_PATH,
    API_CAMERA_AUDIO_STREAM_PATH,
    API_CAMERA_GRID_PATH,
    API_CAMERA_PROXY_PATH,
    API_CAMERA_STREAM_PATH,
    API_MAP_PROXY_PATH,
    API_WALLPAPER_PROXY_PATH,
    API_WALLPAPER_UPLOAD_PATH,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    DEFAULT_ART_SIZE,
    DOMAIN,
    INTEGRATION_VERSION,
    normalize_device_slug,
    normalize_noise_reduction,
)
from .wallpapers import (
    MAX_WALLPAPER_UPLOAD_BYTES,
    get_wallpaper_root,
    list_wallpaper_catalog,
    parse_upload_source,
    read_upload_bytes,
    render_builtin_preset_image,
    save_uploaded_wallpaper_bytes,
)

if TYPE_CHECKING:
    from .coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pure HMAC-SHA256 Resource Signatures (Day-Bucketed & Exact Expiry)
# ---------------------------------------------------------------------------

SIG_BUCKET_SECONDS: int = 86400
PAYLOAD_TTL_DAYS: int = 2
ON_DEMAND_TTL_SECONDS: int = 600
_MAC_HEX_CHARS: int = 32
_PROBED_LAN_IP_KEY = "_probed_lan_ip"


def day_bucketed_expiry(now_s: int, ttl_days: int) -> int:
    """Return the first UTC midnight at least `ttl_days` days after `now_s` (valid for ttl_days to ttl_days + 1 days)."""
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
    """Return the `<exp>.<mac>` signature binding `scope` (the Device's subentry ID or 'system'), `resource` and `exp`."""
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

    def invalidate_lan_base_url(self) -> None:
        """Invalidate the cached numeric LAN base URL when HA network config changes."""
        self._cached_lan_base_url = None
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
        return self.get_lan_base_url()

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
        """Resolve the numeric-IP LAN HTTP base URL purely from memory / HA config (zero event-loop socket calls)."""
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
            return ""
        base_url = self.get_lan_base_url()
        sig = self.sign_payload_resource(f"camera:{cam_ent}|{width}|{height}|{shape}")
        v_tag = cache_bust or sig[:8]
        return (
            f"{base_url}/api/latter/camera/{device_slug}"
            f"?entity_id={cam_ent}&w={width}&h={height}&shape={shape}&sig={sig}&v={v_tag}"
        )

    def build_camera_allowlist_snapshot_url(
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
            return ""
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
            return ""
        base_url = self.get_lan_base_url()
        sig = self.sign_payload_resource(
            f"wallpaper:{clean_src}|{width}|{height}|{shape}"
        )
        digest = hashlib.md5(
            f"{clean_src}|{shape}|{width}x{height}".encode()
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


# ---------------------------------------------------------------------------
# Image Transcoding, LRU Caches, Live Camera Prefetch & Audio Stream Helpers
# ---------------------------------------------------------------------------

HTTP_USER_AGENT = (
    f"HomeAssistant-Latter/{INTEGRATION_VERSION} (+https://github.com/slampton/ha-latter)"
)

MAX_ART_CACHE_ENTRIES = 24
MAX_UPSTREAM_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB hard stream cap on upstream artwork downloads
_ARTWORK_LRU_CACHE: OrderedDict[tuple[str, int, int, bool, float], bytes] = OrderedDict()

_CIRCULAR_MASK_CACHE: dict[tuple[int, int], tuple[Image.Image, Image.Image]] = {}

_MAP_GEOCODE_CACHE: OrderedDict[str, tuple[float, float]] = OrderedDict()
MAX_MAP_GEOCODE_CACHE = 64
_MAP_JPEG_CACHE: OrderedDict[str, bytes] = OrderedDict()
_OSM_TILE_CACHE: OrderedDict[tuple[int, int, int], bytes] = OrderedDict()
MAX_OSM_TILE_CACHE = 128

SILENCE_FALLBACK_MS: int = 250
_FFMPEG_STREAM_SEMAPHORE = asyncio.Semaphore(2)
_ACTIVE_DEVICE_STREAMS: dict[str, asyncio.subprocess.Process] = {}


def clear_http_caches() -> None:
    """Clear in-memory LRU caches for artwork, maps, and circular masks."""
    _ARTWORK_LRU_CACHE.clear()
    _MAP_GEOCODE_CACHE.clear()
    _MAP_JPEG_CACHE.clear()
    _OSM_TILE_CACHE.clear()
    _CIRCULAR_MASK_CACHE.clear()


async def async_shutdown_camera_feeds(hass: HomeAssistant | None = None) -> None:
    """Shut down shared camera video ingests and clear HTTP caches on integration unload."""
    if hass is not None:
        from .cameras import async_shutdown_camera_stream_hub

        await async_shutdown_camera_stream_hub(hass)
    clear_http_caches()


async def async_shutdown_doorbell_streams(hass: HomeAssistant | None = None) -> None:
    """Terminate all active FFmpeg camera audio subprocesses on integration unload."""
    _ = hass
    active = list(_ACTIVE_DEVICE_STREAMS.items())
    _ACTIVE_DEVICE_STREAMS.clear()
    for _sub_id, proc in active:
        if proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=1.5)
            except TimeoutError:
                proc.kill()
            except ProcessLookupError:
                pass


def _build_silence_wav(
    duration_ms: int = SILENCE_FALLBACK_MS, sample_rate: int = 48000
) -> bytes:
    """Build a short PCM16 mono silent WAV buffer at the device's I2S bus sample rate."""
    num_samples = max(160, int(sample_rate * (duration_ms / 1000.0)))
    out_io = io.BytesIO()
    with wave.open(out_io, "wb") as wf_out:
        wf_out.setnchannels(1)
        wf_out.setsampwidth(2)
        wf_out.setframerate(sample_rate)
        wf_out.writeframes(b"\x00\x00" * num_samples)
    return out_io.getvalue()


def build_noise_reduction_filter(level: str) -> str:
    """Build the FFmpeg audio filter chain for a doorbell listen stream."""
    if level == "off":
        return "highpass=f=60,alimiter=limit=0.95"
    if level == "light":
        return (
            "highpass=f=100,lowpass=f=4000,"
            "afftdn=nf=-20,"
            "acompressor=threshold=-18dB:ratio=2.5:attack=5:release=90,"
            "alimiter=limit=0.91"
        )
    return (
        "highpass=f=120,lowpass=f=3600,"
        "afftdn=nf=-26,"
        "equalizer=f=1800:t=q:w=1.2:g=3,"
        "acompressor=threshold=-20dB:ratio=3.2:attack=4:release=75:makeup=2,"
        "alimiter=limit=0.89"
    )


def _get_circular_mask_surfaces(
    width: int, height: int
) -> tuple[Image.Image, Image.Image]:
    """Return cached (mask_L, black_bg_RGB) PIL surfaces for (width, height)."""
    key = (width, height)
    cached = _CIRCULAR_MASK_CACHE.get(key)
    if cached is not None:
        return cached
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, width - 1, height - 1), fill=255)
    black_bg = Image.new("RGB", (width, height), (0, 0, 0))
    if len(_CIRCULAR_MASK_CACHE) >= 16:
        _CIRCULAR_MASK_CACHE.clear()
    _CIRCULAR_MASK_CACHE[key] = (mask, black_bg)
    return mask, black_bg


def _transcode_to_baseline_jpeg(
    raw_bytes: bytes,
    width: int,
    height: int,
    circular_mask: bool = False,
    darken: float = 1.0,
    rotate_deg: int = 0,
    fast_live: bool = False,
) -> bytes:
    """Decode any image format, resize to (w, h), and encode non-progressive Baseline JPEG."""
    with Image.open(io.BytesIO(raw_bytes)) as img:
        img_rgb = img.convert("RGB")
        if rotate_deg == 90:
            img_rgb = img_rgb.transpose(Image.Transpose.ROTATE_270)
        elif rotate_deg == 180:
            img_rgb = img_rgb.transpose(Image.Transpose.ROTATE_180)
        elif rotate_deg == 270:
            img_rgb = img_rgb.transpose(Image.Transpose.ROTATE_90)
        fitted = ImageOps.fit(
            img_rgb,
            (width, height),
            method=Image.Resampling.BILINEAR if fast_live else Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        if darken < 1.0:
            fitted = ImageEnhance.Brightness(fitted).enhance(darken)

        if circular_mask:
            mask, black_bg = _get_circular_mask_surfaces(width, height)
            fitted = Image.composite(fitted, black_bg, mask)

        out = io.BytesIO()
        live_quality = 72 if (width * height > 300000) else 80
        fitted.save(
            out,
            format="JPEG",
            quality=live_quality if fast_live else 85,
            optimize=not fast_live,
            progressive=False,
            subsampling=2,
        )
        return out.getvalue()


def _render_preset_to_baseline_jpeg(
    preset_id: str,
    width: int,
    height: int,
    circular_mask: bool = False,
    darken: float = 0.78,
) -> bytes:
    """Render a bundled default wallpaper directly to Baseline JPEG in a single pass."""
    fitted = render_builtin_preset_image(preset_id, width, height)
    if darken < 1.0:
        fitted = ImageEnhance.Brightness(fitted).enhance(darken)
    if circular_mask:
        mask, black_bg = _get_circular_mask_surfaces(width, height)
        fitted = Image.composite(fitted, black_bg, mask)
    out = io.BytesIO()
    fitted.save(
        out,
        format="JPEG",
        quality=85,
        optimize=True,
        progressive=False,
        subsampling=2,
    )
    return out.getvalue()


def evict_wallpaper_lru_cache(source_id: str) -> None:
    """Evict all cached resolutions/shapes for a deleted or updated wallpaper source."""
    prefix = f"wp:{source_id}"
    stale_keys = [k for k in _ARTWORK_LRU_CACHE if k[0] == prefix]
    for k in stale_keys:
        _ARTWORK_LRU_CACHE.pop(k, None)


def _parse_dimensions_and_shape(
    request: web.Request,
    default_w: int,
    default_h: int,
    *,
    min_dim: int = 32,
    max_dim: int = 1200,
    default_circle: bool | None = None,
) -> tuple[int, int, bool, str]:
    """Parse and clamp (width, height, is_circle, shape_str) query parameters."""
    try:
        width = max(min_dim, min(max_dim, int(request.query.get("w") or default_w)))
        height = max(min_dim, min(max_dim, int(request.query.get("h") or default_h)))
    except ValueError:
        width, height = default_w, default_h

    if default_circle is None:
        is_circle = (
            request.query.get("mask") == "circle"
            or request.query.get("shape") == "circle"
        )
    else:
        is_circle = default_circle
        if request.query.get("shape") in ("circle", "square"):
            is_circle = request.query.get("shape") == "circle"
    return width, height, is_circle, ("circle" if is_circle else "square")


def _parse_render_params(
    request: web.Request,
    coordinator: LatterCoordinator,
    *,
    min_dim: int = 32,
    max_dim: int = 1200,
    default_circle: bool | None = None,
) -> tuple[int, int, bool, str]:
    """Parse and clamp render params for a Device coordinator."""
    default_w, default_h = coordinator.art_dimensions
    return _parse_dimensions_and_shape(
        request,
        default_w,
        default_h,
        min_dim=min_dim,
        max_dim=max_dim,
        default_circle=default_circle,
    )


def _is_public_global_ip(raw_ip: str) -> bool:
    """Return True only if raw_ip parses as a globally routable unicast IP address."""
    try:
        ip = ipaddress.ip_address(raw_ip)
    except ValueError:
        return False
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    )


def _resolve_and_check_public_host(hostname: str, port: int) -> bool:
    """Resolve hostname via DNS in an executor thread and require every returned address to be globally routable."""
    try:
        ipaddress.ip_address(hostname)
        return _is_public_global_ip(hostname)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(hostname, port, 0, socket.SOCK_STREAM)
    except OSError:
        return False
    if not infos:
        return False
    return all(_is_public_global_ip(str(info[4][0])) for info in infos if info[4])


async def _async_is_safe_external_artwork_url(hass: HomeAssistant, url: str) -> bool:
    """Block SSRF against loopback, private RFC1918, and cloud metadata IPs on external artwork URLs."""
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return await hass.async_add_executor_job(
        _resolve_and_check_public_host, parsed.hostname, port
    )


async def _async_serve_speaker_artwork(
    hass: HomeAssistant,
    request: web.Request,
    coordinator: LatterCoordinator,
) -> web.Response:
    """Fetch active speaker artwork, transcode to Baseline JPEG (8 MB cap + RAM LRU cache), and serve over HTTP."""
    from .media import resolve_ma_counterpart_entity

    width, height, circular, shape_str = _parse_render_params(
        request, coordinator, default_circle=None
    )

    if not coordinator.verify_resource(
        f"artwork|{width}|{height}|{shape_str}",
        sig=request.query.get("sig"),
    ):
        return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")

    state_obj = hass.states.get(coordinator.active_speaker)
    pic_path = None
    if state_obj is not None:
        attrs = state_obj.attributes
        pic_path = (
            attrs.get("entity_picture_local")
            or attrs.get("entity_picture")
            or attrs.get("media_image_url")
        )
    if not pic_path:
        ma_counterpart = resolve_ma_counterpart_entity(
            hass, coordinator.active_speaker
        )
        if ma_counterpart and ma_counterpart != coordinator.active_speaker:
            ma_st = hass.states.get(ma_counterpart)
            if ma_st is not None:
                m_attrs = ma_st.attributes
                pic_path = (
                    m_attrs.get("entity_picture_local")
                    or m_attrs.get("entity_picture")
                    or m_attrs.get("media_image_url")
                )
    if not pic_path and coordinator.last_valid_raw_pic:
        pic_path = coordinator.last_valid_raw_pic

    if not pic_path:
        return web.Response(status=HTTPStatus.NOT_FOUND, text="No artwork")

    raw_pic = str(pic_path)
    is_local_ha_path = raw_pic.startswith("/")
    pic_url = raw_pic
    if is_local_ha_path:
        try:
            base_url = get_url(hass, allow_internal=True, prefer_external=False)
        except Exception:  # noqa: BLE001
            base_url = "http://127.0.0.1:8123"
        pic_url = f"{base_url}{raw_pic}"
    elif not await _async_is_safe_external_artwork_url(hass, pic_url):
        return web.Response(
            status=HTTPStatus.FORBIDDEN, text="Blocked upstream artwork host"
        )

    cache_key = (pic_url, width, height, circular, 1.0)
    cached_bytes = _ARTWORK_LRU_CACHE.get(cache_key)
    if cached_bytes is not None:
        _ARTWORK_LRU_CACHE.move_to_end(cache_key)
        return web.Response(
            body=cached_bytes,
            content_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=300", "X-Latter-Cache": "HIT"},
        )

    session = async_get_clientsession(hass)
    try:
        async with session.get(
            pic_url,
            timeout=ClientTimeout(total=8),
            allow_redirects=is_local_ha_path,
        ) as resp:
            if resp.status != HTTPStatus.OK:
                return web.Response(
                    status=HTTPStatus.BAD_GATEWAY,
                    text=f"Upstream returned {resp.status}",
                )
            if resp.content_length and resp.content_length > MAX_UPSTREAM_IMAGE_BYTES:
                return web.Response(
                    status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    text="Upstream artwork exceeds 8 MB limit",
                )
            chunks = bytearray()
            async for chunk in resp.content.iter_chunked(65536):
                chunks.extend(chunk)
                if len(chunks) > MAX_UPSTREAM_IMAGE_BYTES:
                    return web.Response(
                        status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        text="Upstream artwork exceeds 8 MB limit",
                    )
            raw_bytes = bytes(chunks)
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
        headers={"Cache-Control": "private, max-age=300", "X-Latter-Cache": "MISS"},
    )


# ---------------------------------------------------------------------------
# All 7 Signed / Admin HTTP Views
# ---------------------------------------------------------------------------


class LatterArtworkTranscoderView(HomeAssistantView):
    """Universal Baseline-JPEG artwork proxy (/api/latter/artwork/{target_device})."""

    requires_auth = False
    url = API_ARTWORK_PROXY_PATH
    name = "api:latter:artwork_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the universal artwork transcoder view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Handle GET /api/latter/artwork/{target_device}?w=...&h=...&v=..."""
        from .coordinator import resolve_coordinator

        coordinator = resolve_coordinator(self.hass, target_device)
        if coordinator is None:
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="Unknown target device"
            )
        return await _async_serve_speaker_artwork(self.hass, request, coordinator)


class LatterWallpaperProxyView(HomeAssistantView):
    """Serves signed Baseline-JPEG wallpapers (/api/latter/wallpaper/{target_device}), including zero-device 'system' scope."""

    requires_auth = False
    url = API_WALLPAPER_PROXY_PATH
    name = "api:latter:wallpaper_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the wallpaper proxy view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Handle GET /api/latter/wallpaper/{target_device}?w=...&h=...&src=..."""
        from .coordinator import resolve_coordinator
        from .hub import get_latter_system

        coordinator = resolve_coordinator(self.hass, target_device)
        if coordinator is not None:
            wp_source = str(
                request.query.get("src") or coordinator.wallpaper_source
            ).strip()
            if not wp_source:
                return web.Response(
                    status=HTTPStatus.NOT_FOUND, text="No wallpaper configured"
                )
            def_w, def_h = coordinator.wallpaper_dimensions
            width, height, is_circle, shape_str = _parse_dimensions_and_shape(
                request,
                def_w,
                def_h,
                default_circle=(coordinator.display_shape == "circle"),
            )
            verified = coordinator.verify_resource(
                f"wallpaper:{wp_source}|{width}|{height}|{shape_str}",
                sig=request.query.get("sig"),
            )
        elif normalize_device_slug(target_device) == "system":
            sys_obj = get_latter_system(self.hass)
            if sys_obj is None:
                return web.Response(
                    status=HTTPStatus.NOT_FOUND, text="Latter System not initialized"
                )
            wp_source = str(request.query.get("src") or "").strip()
            if not wp_source:
                return web.Response(
                    status=HTTPStatus.NOT_FOUND, text="No wallpaper specified"
                )
            width, height, is_circle, shape_str = _parse_dimensions_and_shape(
                request,
                DEFAULT_ART_SIZE,
                DEFAULT_ART_SIZE,
                default_circle=False,
            )
            verified = sys_obj.url_signer.verify_resource(
                f"wallpaper:{wp_source}|{width}|{height}|{shape_str}",
                sig=request.query.get("sig"),
            )
        else:
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="Unknown target device"
            )

        if not verified:
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")

        darken_factor = 0.78
        cache_key = (f"wp:{wp_source}", width, height, is_circle, darken_factor)
        cached_bytes = _ARTWORK_LRU_CACHE.get(cache_key)
        if cached_bytes is not None:
            _ARTWORK_LRU_CACHE.move_to_end(cache_key)
            return web.Response(
                body=cached_bytes,
                content_type="image/jpeg",
                headers={
                    "Cache-Control": "private, max-age=300",
                    "X-Latter-Cache": "HIT",
                },
            )

        if wp_source.startswith("preset:"):
            try:
                jpeg_bytes = await self.hass.async_add_executor_job(
                    _render_preset_to_baseline_jpeg,
                    wp_source,
                    width,
                    height,
                    is_circle,
                    darken_factor,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Wallpaper preset rendering failed: %s", err)
                return web.Response(
                    status=HTTPStatus.UNPROCESSABLE_ENTITY,
                    text="Wallpaper processing error",
                )
        elif parse_upload_source(wp_source) is not None:
            raw_bytes = await self.hass.async_add_executor_job(
                read_upload_bytes, get_wallpaper_root(self.hass), wp_source
            )
            if not raw_bytes:
                return web.Response(
                    status=HTTPStatus.NOT_FOUND, text="Wallpaper source unreadable"
                )
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
                    status=HTTPStatus.UNPROCESSABLE_ENTITY,
                    text="Wallpaper processing error",
                )
        else:
            return web.Response(
                status=HTTPStatus.FORBIDDEN, text="Unsupported wallpaper source"
            )

        _ARTWORK_LRU_CACHE[cache_key] = jpeg_bytes
        if len(_ARTWORK_LRU_CACHE) > MAX_ART_CACHE_ENTRIES:
            _ARTWORK_LRU_CACHE.popitem(last=False)

        return web.Response(
            body=jpeg_bytes,
            content_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=300", "X-Latter-Cache": "MISS"},
        )


class LatterWallpaperUploadView(HomeAssistantView):
    """Admin-authenticated multipart wallpaper upload endpoint (`POST /api/latter/wallpaper/upload`, <= 15 MB)."""

    requires_auth = True
    url = API_WALLPAPER_UPLOAD_PATH
    name = "api:latter:wallpaper_upload"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the multipart wallpaper upload view."""
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        """Handle admin multipart/form-data upload (`file` <= 15 MB, optional `device_slug` / `subentry_id`)."""
        from .coordinator import resolve_coordinator
        from .hub import get_latter_system, iter_coordinators
        from .presence import get_ble_fabric
        from .studio.settings import find_by_subentry_id

        user = request.get("hass_user")
        if user is None or not getattr(user, "is_admin", False):
            return web.json_response(
                {"error": "Administrator privileges required"},
                status=HTTPStatus.FORBIDDEN,
            )

        if (
            request.content_length is not None
            and request.content_length > MAX_WALLPAPER_UPLOAD_BYTES + 65536
        ):
            return web.json_response(
                {"error": "Wallpaper upload exceeds 15 MB limit"},
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )

        upload_scope = ""
        explicit_device_slug = str(request.query.get("device_slug") or "").strip()
        target_slug = normalize_device_slug(explicit_device_slug or "system")
        subentry_id = str(request.query.get("subentry_id") or "").strip()
        filename = "wallpaper.jpg"
        raw_bytes: bytes | None = None

        try:
            reader = await request.multipart()
        except Exception:  # noqa: BLE001
            return web.json_response(
                {"error": "Expected multipart/form-data request"},
                status=HTTPStatus.BAD_REQUEST,
            )

        while True:
            part = await reader.next()
            if part is None:
                break
            field_name = str(getattr(part, "name", "") or "")
            if field_name == "scope":
                upload_scope = (await part.text()).strip().lower()
            elif field_name == "device_slug":
                val = (await part.text()).strip()
                if val:
                    explicit_device_slug = val
                    target_slug = normalize_device_slug(val)
            elif field_name == "subentry_id":
                val = (await part.text()).strip()
                if val:
                    subentry_id = val
            elif field_name == "file":
                filename = str(getattr(part, "filename", None) or filename)
                chunks = bytearray()
                while True:
                    chunk = await part.read_chunk(65536)
                    if not chunk:
                        break
                    chunks.extend(chunk)
                    if len(chunks) > MAX_WALLPAPER_UPLOAD_BYTES:
                        return web.json_response(
                            {"error": "Wallpaper upload exceeds 15 MB limit"},
                            status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        )
                raw_bytes = bytes(chunks)
            else:
                await part.release()

        if not raw_bytes:
            return web.json_response(
                {"error": "Multipart 'file' field is missing or empty"},
                status=HTTPStatus.BAD_REQUEST,
            )

        coord: LatterCoordinator | None = None
        if upload_scope == "system":
            target_slug = "system"
        elif subentry_id:
            coord = find_by_subentry_id(iter_coordinators(self.hass), subentry_id)
            if coord is None:
                return web.json_response(
                    {"error": f"Unknown subentry_id: {subentry_id}"},
                    status=HTTPStatus.NOT_FOUND,
                )
            target_slug = coord.device_slug
        elif explicit_device_slug and target_slug != "system":
            coord = resolve_coordinator(self.hass, target_slug)
            if coord is None:
                return web.json_response(
                    {"error": f"Unknown device_slug: {target_slug}"},
                    status=HTTPStatus.NOT_FOUND,
                )
            target_slug = coord.device_slug

        try:
            source_id, out_filename = await self.hass.async_add_executor_job(
                save_uploaded_wallpaper_bytes,
                self.hass,
                target_slug,
                filename,
                raw_bytes,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Wallpaper multipart upload failed: %s", err)
            return web.json_response(
                {"error": f"Invalid image upload: {err}"},
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
            )

        sys_obj = get_latter_system(self.hass)
        sys_signer = (
            sys_obj.url_signer.sign_payload_resource
            if sys_obj is not None
            else None
        )
        system_wallpapers = list_wallpaper_catalog(
            self.hass,
            "system",
            "",
            [],
            sign_resource=sys_signer,
            display_shape="square",
        )

        if coord is not None:
            async with coord.config_lock:
                favs = list(coord.wallpaper_favorites)
                if source_id not in favs:
                    favs.append(source_id)
                merged = {
                    **coord.device_data,
                    CONF_WALLPAPER_SOURCE: source_id,
                    CONF_WALLPAPER_FAVORITES: favs,
                }
                coord.current_wallpaper = source_id
                coord._configured_wallpaper_source = source_id
                coord._schedule_persist_runtime_state()
                coord.update_device_config(merged)
            coord._bind_wallpaper_cycle_timer()
            coord.async_notify_listeners()
            wallpapers = list_wallpaper_catalog(
                self.hass,
                coord.device_slug,
                coord.wallpaper_source,
                coord.wallpaper_favorites,
                sign_resource=coord.sign_payload_resource,
                display_shape=coord.display_shape,
            )
        else:
            wallpapers = system_wallpapers
            get_ble_fabric(self.hass).notify_occupancy_listeners()

        return web.json_response(
            {
                "ok": True,
                "filename": out_filename,
                "source_id": source_id,
                "wallpapers": wallpapers,
                "system_wallpapers": system_wallpapers,
            }
        )


class LatterCameraSnapshotView(HomeAssistantView):
    """Fetches a live frame from an allow-listed camera.* entity and transcodes to Baseline JPEG."""

    requires_auth = False
    url = API_CAMERA_PROXY_PATH
    name = "api:latter:camera_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the camera snapshot transcoder view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Handle GET /api/latter/camera/{target_device}?entity_id=camera.front_door&w=466&h=466&shape=circle&fit=contain"""
        from .cameras import (
            CameraFetchError,
            CameraTranscodeError,
            get_camera_stream_hub,
            normalize_fit_mode,
        )
        from .coordinator import resolve_coordinator
        from .hub import get_latter_system

        coordinator = resolve_coordinator(self.hass, target_device)
        if coordinator is not None:
            cam_entity = str(
                request.query.get("entity_id") or coordinator.camera_entity or ""
            ).strip()
            if not cam_entity or not cam_entity.startswith("camera."):
                return web.Response(
                    status=HTTPStatus.NOT_FOUND, text="No camera entity specified"
                )
            width, height, is_circle, shape_str = _parse_render_params(
                request,
                coordinator,
                default_circle=(coordinator.display_shape == "circle"),
            )
            visible_cams = coordinator.visible_camera_entities
            visible_set = set(visible_cams)
            allow_hash = camera_allowlist_hash(visible_cams)
            sig = request.query.get("sig")
            allow_sig_ok = bool(visible_cams) and coordinator.verify_resource(
                f"camera_allow:{allow_hash}|{width}|{height}|{shape_str}",
                sig=sig,
            )
            single_sig_ok = coordinator.verify_resource(
                f"camera:{cam_entity}|{width}|{height}|{shape_str}",
                sig=sig,
            )
            if not (allow_sig_ok or single_sig_ok):
                return web.Response(
                    status=HTTPStatus.FORBIDDEN, text="Invalid signature"
                )
            if allow_sig_ok:
                if cam_entity not in visible_set:
                    return web.Response(
                        status=HTTPStatus.FORBIDDEN,
                        text="Camera entity not in allow-list",
                    )
            else:
                allowed_single = visible_set | (
                    {coordinator.alert_camera_entity}
                    if coordinator.alert_camera_entity
                    else set()
                )
                if cam_entity not in allowed_single:
                    return web.Response(
                        status=HTTPStatus.NOT_FOUND,
                        text="Camera entity not in allow-list",
                    )
        elif normalize_device_slug(target_device) == "system":
            sys_obj = get_latter_system(self.hass)
            if sys_obj is None:
                return web.Response(
                    status=HTTPStatus.NOT_FOUND, text="Latter System not initialized"
                )
            cam_entity = str(request.query.get("entity_id") or "").strip()
            if not cam_entity or not cam_entity.startswith("camera."):
                return web.Response(
                    status=HTTPStatus.NOT_FOUND, text="No camera entity specified"
                )
            width, height, is_circle, shape_str = _parse_dimensions_and_shape(
                request,
                320,
                180,
                default_circle=False,
            )
            if not sys_obj.url_signer.verify_resource(
                f"camera:{cam_entity}|{width}|{height}|{shape_str}",
                sig=request.query.get("sig"),
            ):
                return web.Response(
                    status=HTTPStatus.FORBIDDEN, text="Invalid signature"
                )
            if self.hass.states.get(cam_entity) is None:
                return web.Response(
                    status=HTTPStatus.NOT_FOUND, text="Camera entity not found"
                )
        else:
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="Unknown target device"
            )

        rot_str = (request.query.get("rot") or "0").strip()
        if rot_str not in ("0", "90", "180", "270"):
            return web.Response(
                status=HTTPStatus.BAD_REQUEST, text="Invalid rotation angle"
            )
        rotate_deg = int(rot_str)

        raw_fit = request.query.get("fit")
        fit_mode = normalize_fit_mode(raw_fit) if raw_fit is not None else "contain"

        try:
            jpeg_bytes, from_memory = await get_camera_stream_hub(
                self.hass
            ).async_get_snapshot(
                cam_entity,
                width,
                height,
                fit=fit_mode,
                rot=rotate_deg,
                circular_mask=(is_circle and fit_mode == "fill"),
            )
        except CameraFetchError as err:
            _LOGGER.debug("Camera snapshot fetch failed for %s: %s", cam_entity, err)
            return web.Response(
                status=HTTPStatus.BAD_GATEWAY, text="Camera snapshot unavailable"
            )
        except CameraTranscodeError as err:
            _LOGGER.debug("Camera snapshot Pillow transcode failed: %s", err)
            return web.Response(
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
                text="Camera image processing error",
            )

        return web.Response(
            body=jpeg_bytes,
            content_type="image/jpeg",
            headers={
                "Cache-Control": "private, no-store, max-age=0",
                "X-Latter-Cam-Cache": "HIT" if from_memory else "MISS",
            },
        )


def _clamp_video_query_dim(raw: str | None, max_dim: int) -> int:
    """Parse an integer query dimension, clamp to `[64, max_dim]`, and align down to 16px."""
    from .cameras import align16

    try:
        parsed = int(raw) if raw is not None and str(raw).strip() else max_dim
    except (TypeError, ValueError):
        parsed = max_dim
    return align16(min(max_dim, parsed), maximum=max_dim)


class LatterCameraStreamView(HomeAssistantView):
    """Streams live 16px-aligned Baseline 4:2:0 MJPEG video for a single allow-listed camera."""

    requires_auth = False
    url = API_CAMERA_STREAM_PATH
    name = "api:latter:camera_stream"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the single-camera MJPEG stream view."""
        self.hass = hass

    async def get(
        self, request: web.Request, target_device: str
    ) -> web.StreamResponse:
        """Handle GET /api/latter/camera_stream/{target_device}?entity_id=...&w=...&h=...&fps=...&fit=contain&rot=0&sig=..."""
        from .cameras import (
            MJPEG_CONTENT_TYPE,
            CameraFetchError,
            CameraIngestLimitError,
            get_camera_stream_hub,
            normalize_fit_mode,
            normalize_fps,
        )
        from .coordinator import resolve_coordinator

        coord = resolve_coordinator(self.hass, target_device)
        if coord is None:
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="Unknown target device"
            )

        allowed = coord.visible_camera_entities
        max_w, max_h = coord.video_max_dims
        max_fps = coord.video_max_fps
        allow_hash = camera_allowlist_hash(allowed)
        if not coord.verify_resource(
            f"camera_stream:{allow_hash}|{max_w}|{max_h}|{max_fps}",
            sig=request.query.get("sig"),
        ):
            return web.Response(
                status=HTTPStatus.FORBIDDEN, text="Invalid or missing signature"
            )

        if max_w <= 0 or max_h <= 0:
            return web.Response(
                status=HTTPStatus.BAD_REQUEST, text="Device does not support video"
            )

        cam_entity = (
            request.query.get("entity_id")
            or coord.active_carousel_camera
            or (allowed[0] if allowed else "")
        ).strip()
        if not cam_entity or not cam_entity.startswith("camera."):
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="No camera entity configured"
            )
        if cam_entity not in set(allowed):
            return web.Response(
                status=HTTPStatus.FORBIDDEN, text="Camera entity not in allow-list"
            )

        rot_str = (request.query.get("rot") or "0").strip()
        if rot_str not in ("0", "90", "180", "270"):
            return web.Response(
                status=HTTPStatus.BAD_REQUEST, text="Invalid rotation angle"
            )
        rotate_deg = int(rot_str)

        req_w = _clamp_video_query_dim(request.query.get("w"), max_w)
        req_h = _clamp_video_query_dim(request.query.get("h"), max_h)
        req_fps = min(max_fps, normalize_fps(request.query.get("fps"), default=max_fps))
        fit_mode = normalize_fit_mode(request.query.get("fit"))
        is_circle = (request.query.get("shape") or "").strip().lower() == "circle"

        hub = get_camera_stream_hub(self.hass)
        stream_iter = hub.async_iter_mjpeg_chunks(
            cam_entity,
            req_w,
            req_h,
            fps=req_fps,
            fit=fit_mode,
            rot=rotate_deg,
            circular_mask=(is_circle and fit_mode == "fill"),
        )
        try:
            try:
                first_chunk = await anext(stream_iter)
            except StopAsyncIteration:
                return web.Response(
                    status=HTTPStatus.BAD_GATEWAY, text="Camera stream unavailable"
                )
            except CameraIngestLimitError:
                return web.Response(
                    status=HTTPStatus.TOO_MANY_REQUESTS,
                    text="Maximum concurrent camera streams reached",
                )
            except CameraFetchError as err:
                _LOGGER.debug("Camera stream start failed for %s: %s", cam_entity, err)
                return web.Response(
                    status=HTTPStatus.BAD_GATEWAY, text="Camera stream unavailable"
                )

            resp = web.StreamResponse(
                status=HTTPStatus.OK,
                headers={
                    "Content-Type": MJPEG_CONTENT_TYPE,
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                    "X-Accel-Buffering": "no",
                },
            )
            await resp.prepare(request)
            try:
                await resp.write(first_chunk)
                async for chunk in stream_iter:
                    await resp.write(chunk)
            except (asyncio.CancelledError, ConnectionResetError):
                pass
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Camera stream closed for %s: %s", cam_entity, err)
            return resp
        finally:
            await stream_iter.aclose()


class LatterCameraGridView(HomeAssistantView):
    """Streams a server-side 2x2 composited Baseline 4:2:0 MJPEG grid for up to 4 allow-listed cameras."""

    requires_auth = False
    url = API_CAMERA_GRID_PATH
    name = "api:latter:camera_grid"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the 2x2 camera grid MJPEG stream view."""
        self.hass = hass

    async def get(
        self, request: web.Request, target_device: str
    ) -> web.StreamResponse:
        """Handle GET /api/latter/camera_grid/{target_device}?cameras=cam1,cam2,...&w=...&h=...&fps=...&fit=contain&sig=..."""
        from .cameras import (
            MJPEG_CONTENT_TYPE,
            CameraFetchError,
            CameraIngestLimitError,
            get_camera_stream_hub,
            normalize_fit_mode,
            normalize_fps,
        )
        from .coordinator import resolve_coordinator

        coord = resolve_coordinator(self.hass, target_device)
        if coord is None:
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="Unknown target device"
            )

        allowed = coord.visible_camera_entities
        allowed_set = set(allowed)
        max_w, max_h = coord.video_max_dims
        max_fps = coord.video_max_fps
        grid_fps = min(max_fps, coord.video_grid_fps)
        allow_hash = camera_allowlist_hash(allowed)
        if not coord.verify_resource(
            f"camera_stream:{allow_hash}|{max_w}|{max_h}|{max_fps}",
            sig=request.query.get("sig"),
        ):
            return web.Response(
                status=HTTPStatus.FORBIDDEN, text="Invalid or missing signature"
            )

        if max_w <= 0 or max_h <= 0:
            return web.Response(
                status=HTTPStatus.BAD_REQUEST, text="Device does not support video"
            )

        raw_csv = str(request.query.get("cameras") or "").strip()
        if raw_csv:
            requested: list[str] = []
            for tok in raw_csv.split(","):
                cid = tok.strip()
                if cid and cid not in requested:
                    requested.append(cid)
            requested = requested[:4]
        else:
            requested = list(allowed[:4])

        if not requested:
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="No cameras configured for grid"
            )
        if any(
            not cid.startswith("camera.") or cid not in allowed_set for cid in requested
        ):
            return web.Response(
                status=HTTPStatus.FORBIDDEN,
                text="One or more camera entities not in allow-list",
            )

        req_w = _clamp_video_query_dim(request.query.get("w"), max_w)
        req_h = _clamp_video_query_dim(request.query.get("h"), max_h)
        req_fps = min(grid_fps, normalize_fps(request.query.get("fps"), default=grid_fps))
        fit_mode = normalize_fit_mode(request.query.get("fit"))

        hub = get_camera_stream_hub(self.hass)
        stream_iter = hub.async_iter_grid_mjpeg_chunks(
            requested,
            req_w,
            req_h,
            fps=req_fps,
            fit=fit_mode,
        )
        try:
            try:
                first_chunk = await anext(stream_iter)
            except StopAsyncIteration:
                return web.Response(
                    status=HTTPStatus.BAD_GATEWAY, text="Camera grid stream unavailable"
                )
            except CameraIngestLimitError:
                return web.Response(
                    status=HTTPStatus.TOO_MANY_REQUESTS,
                    text="Maximum concurrent camera streams reached",
                )
            except CameraFetchError as err:
                _LOGGER.debug("Camera grid start failed: %s", err)
                return web.Response(
                    status=HTTPStatus.BAD_GATEWAY, text="Camera grid stream unavailable"
                )

            resp = web.StreamResponse(
                status=HTTPStatus.OK,
                headers={
                    "Content-Type": MJPEG_CONTENT_TYPE,
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                    "X-Accel-Buffering": "no",
                },
            )
            await resp.prepare(request)
            try:
                await resp.write(first_chunk)
                async for chunk in stream_iter:
                    await resp.write(chunk)
            except (asyncio.CancelledError, ConnectionResetError):
                pass
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Camera grid stream closed: %s", err)
            return resp
        finally:
            await stream_iter.aclose()


class LatterCameraAudioStreamView(HomeAssistantView):
    """Streams live RTSP camera audio through an FFmpeg noise-reduction filter to a Latter device."""

    requires_auth = False
    url = API_CAMERA_AUDIO_STREAM_PATH
    name = "api:latter:camera_audio_stream"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the camera audio stream view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.StreamResponse:
        """Stream live de-noised FLAC/WAV audio from a camera's RTSP source."""
        from .coordinator import resolve_coordinator

        coord = resolve_coordinator(self.hass, target_device)
        if coord is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        cam_ent = (
            request.query.get("entity_id")
            or coord.active_carousel_camera
            or coord.camera_entity
            or ""
        ).strip()
        if not cam_ent:
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="No camera entity configured"
            )

        raw_nr = (request.query.get("nr") or coord.doorbell_noise_reduction).strip().lower()
        raw_fmt = (request.query.get("fmt") or "flac").strip().lower()

        if not coord.verify_resource(
            f"camera_audio:{cam_ent}|{raw_nr}|{raw_fmt}",
            sig=request.query.get("sig"),
        ):
            return web.Response(
                status=HTTPStatus.FORBIDDEN, text="Invalid or missing signature"
            )

        nr_level = normalize_noise_reduction(raw_nr)
        fmt = "wav" if raw_fmt == "wav" else "flac"

        allowed_cams = set(coord.camera_entities)
        if coord.active_carousel_camera:
            allowed_cams.add(coord.active_carousel_camera)
        if cam_ent not in allowed_cams:
            return web.Response(
                status=HTTPStatus.FORBIDDEN, text="Camera entity not authorized"
            )

        manifest = coord.hardware_manifest
        audio_info = manifest.get("audio")
        out_rate = (
            int(audio_info.get("out_rate") or 48000)
            if isinstance(audio_info, dict)
            else 48000
        )
        out_ch = (
            int(audio_info.get("out_ch") or 1)
            if isinstance(audio_info, dict)
            else 1
        )
        out_rate = out_rate if out_rate in (16000, 22050, 24000, 44100, 48000) else 48000
        out_ch = 2 if out_ch == 2 else 1

        stream_url: str | None = None
        try:
            from homeassistant.components import camera as ha_camera

            stream_url = await ha_camera.async_get_stream_source(self.hass, cam_ent)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("camera.async_get_stream_source(%s) failed: %s", cam_ent, err)

        ffmpeg_bin: str | None = None
        try:
            from homeassistant.components.ffmpeg import get_ffmpeg_manager

            ffmpeg_bin = get_ffmpeg_manager(self.hass).binary
        except Exception:  # noqa: BLE001
            ffmpeg_bin = shutil.which("ffmpeg")

        if not stream_url or not ffmpeg_bin:
            return web.Response(
                body=_build_silence_wav(sample_rate=out_rate),
                content_type="audio/wav",
            )

        prev_proc = _ACTIVE_DEVICE_STREAMS.pop(coord.subentry_id, None)
        if prev_proc is not None and prev_proc.returncode is None:
            try:
                prev_proc.terminate()
                await asyncio.wait_for(prev_proc.wait(), timeout=1.5)
            except TimeoutError:
                prev_proc.kill()
            except ProcessLookupError:
                pass

        try:
            await asyncio.wait_for(_FFMPEG_STREAM_SEMAPHORE.acquire(), timeout=0.25)
        except TimeoutError:
            return web.Response(
                status=HTTPStatus.TOO_MANY_REQUESTS,
                text="Maximum concurrent camera audio streams reached",
            )

        filtergraph = build_noise_reduction_filter(nr_level)
        out_codec = "flac" if fmt == "flac" else "pcm_s16le"
        out_fmt = "flac" if fmt == "flac" else "wav"
        content_type = "audio/flac" if fmt == "flac" else "audio/wav"

        cmd = [
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-rw_timeout",
            "5000000",
            "-i",
            stream_url,
            "-t",
            "120",
            "-vn",
            "-af",
            filtergraph,
            "-ar",
            str(out_rate),
            "-ac",
            str(out_ch),
            "-c:a",
            out_codec,
            "-f",
            out_fmt,
            "pipe:1",
        ]

        try:
            resp = web.StreamResponse(
                status=HTTPStatus.OK,
                headers={
                    "Content-Type": content_type,
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                },
            )
            await resp.prepare(request)

            proc: asyncio.subprocess.Process | None = None
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                _ACTIVE_DEVICE_STREAMS[coord.subentry_id] = proc
                if proc.stdout is not None:
                    while True:
                        chunk = await proc.stdout.read(4096)
                        if not chunk:
                            break
                        await resp.write(chunk)
            except (asyncio.CancelledError, ConnectionResetError):
                pass
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Camera audio stream ended for %s: %s", cam_ent, err)
            finally:
                if _ACTIVE_DEVICE_STREAMS.get(coord.subentry_id) is proc:
                    _ACTIVE_DEVICE_STREAMS.pop(coord.subentry_id, None)
                if proc is not None and proc.returncode is None:
                    try:
                        proc.terminate()
                        await asyncio.wait_for(proc.wait(), timeout=3.0)
                    except TimeoutError:
                        proc.kill()
                        await proc.wait()
                    except ProcessLookupError:
                        pass

            return resp
        finally:
            _FFMPEG_STREAM_SEMAPHORE.release()


def _latlon_to_tile_xy(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """Convert (lat, lon) in degrees to fractional Web Mercator tile coordinates at zoom."""
    lat_rad = math.radians(max(-85.0511, min(85.0511, lat)))
    n = float(1 << zoom)
    xtile = (lon + 180.0) / 360.0 * n
    ytile = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return xtile, ytile


def _compose_map_snapshot_jpeg(
    tile_images: dict[tuple[int, int], bytes],
    view_tx: float,
    view_ty: float,
    event_tx: float,
    event_ty: float,
    base_tx: int,
    base_ty: int,
    width: int,
    height: int,
    circular_mask: bool,
) -> bytes:
    """Stitch 3x3 256px OSM tiles centered on (view_tx, view_ty) and draw the Event vector pin (no Home Pin)."""
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
        for g in range(0, 768, 48):
            draw_c.line([(g, 0), (g, 768)], fill=(32, 42, 56), width=1)
            draw_c.line([(0, g), (768, g)], fill=(32, 42, 56), width=1)

    v_px = int((view_tx - base_tx) * 256.0)
    v_py = int((view_ty - base_ty) * 256.0)

    half_w = width // 2
    half_h = height // 2
    left = max(0, min(768 - width, v_px - half_w))
    top = max(0, min(768 - height, v_py - half_h))
    cropped = canvas.crop((left, top, left + width, top + height))

    d = ImageDraw.Draw(cropped)
    pin_x = int((event_tx - base_tx) * 256.0) - left
    pin_y = int((event_ty - base_ty) * 256.0) - top

    # Event Destination Vector Pin only — Home coordinates are never read or rendered on map snapshots
    if -32 <= pin_x <= width + 32 and -32 <= pin_y <= height + 40:
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
        mask, black_bg = _get_circular_mask_surfaces(width, height)
        cropped = Image.composite(cropped, black_bg, mask)

    out = io.BytesIO()
    cropped.save(out, format="JPEG", quality=86, optimize=True, progressive=False)
    return out.getvalue()


class LatterMapSnapshotView(HomeAssistantView):
    """Geocodes an address or non-home HA zone and renders a Baseline-JPEG map snapshot (`±4` pan clamp, no Home Pin)."""

    requires_auth = False
    url = API_MAP_PROXY_PATH
    name = "api:latter:map_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the map snapshot view."""
        self.hass = hass

    async def _async_resolve_coordinates(
        self, query: str
    ) -> tuple[float, float] | None:
        """Resolve an address string, 'lat,lon', or non-home HA zone name to (lat, lon)."""
        from .hub import get_area_state_index

        q_clean = query.strip()
        if not q_clean:
            return None

        cache_key = q_clean.lower()
        if cache_key in _MAP_GEOCODE_CACHE:
            _MAP_GEOCODE_CACHE.move_to_end(cache_key)
            return _MAP_GEOCODE_CACHE[cache_key]

        def _store_geocode(coords: tuple[float, float]) -> tuple[float, float]:
            _MAP_GEOCODE_CACHE[cache_key] = coords
            while len(_MAP_GEOCODE_CACHE) > MAX_MAP_GEOCODE_CACHE:
                _MAP_GEOCODE_CACHE.popitem(last=False)
            return coords

        if "," in q_clean:
            parts = [p.strip() for p in q_clean.split(",", 1)]
            try:
                lat_v = float(parts[0])
                lon_v = float(parts[1])
                if -90.0 <= lat_v <= 90.0 and -180.0 <= lon_v <= 180.0:
                    return _store_geocode((lat_v, lon_v))
            except ValueError:
                pass

        for st in get_area_state_index(self.hass).states_for_domain("zone"):
            if st.entity_id == "zone.home":
                continue
            z_name = str(
                st.attributes.get("friendly_name") or st.name or ""
            ).lower()
            if z_name and z_name == cache_key:
                lat_z = st.attributes.get("latitude")
                lon_z = st.attributes.get("longitude")
                if lat_z is not None and lon_z is not None:
                    return _store_geocode((float(lat_z), float(lon_z)))

        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": q_clean, "format": "json", "limit": "1"},
                headers={"User-Agent": HTTP_USER_AGENT},
                timeout=ClientTimeout(total=5),
            ) as resp:
                if resp.status == HTTPStatus.OK:
                    data = await resp.json()
                    if isinstance(data, list) and data:
                        lat_n = float(data[0]["lat"])
                        lon_n = float(data[0]["lon"])
                        return _store_geocode((lat_n, lon_n))
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Nominatim geocode fallback for '%s': %s", q_clean, err)

        return None

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Handle GET /api/latter/map/{target_device}?q=...&z=15&pan_x=0&pan_y=0&w=466&h=466"""
        from .coordinator import resolve_coordinator

        coordinator = resolve_coordinator(self.hass, target_device)
        if coordinator is None:
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="Unknown target device"
            )

        query = str(request.query.get("q") or "").strip()
        width, height, is_circle, shape_str = _parse_render_params(
            request,
            coordinator,
            min_dim=128,
            max_dim=768,
            default_circle=(coordinator.display_shape == "circle"),
        )

        if not coordinator.verify_resource(
            f"map:{query}|{width}|{height}|{shape_str}",
            sig=request.query.get("sig"),
        ):
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")

        zoom = 15
        pan_x = 0
        pan_y = 0
        try:
            if request.query.get("z"):
                zoom = max(10, min(18, int(request.query.get("z", "15"))))
            if request.query.get("pan_x"):
                pan_x = max(-4, min(4, int(request.query.get("pan_x", "0"))))
            if request.query.get("pan_y"):
                pan_y = max(-4, min(4, int(request.query.get("pan_y", "0"))))
        except ValueError:
            pass

        cache_id = f"{query.lower()}|{width}x{height}|{int(is_circle)}|z{zoom}|px{pan_x}|py{pan_y}"
        if cache_id in _MAP_JPEG_CACHE:
            _MAP_JPEG_CACHE.move_to_end(cache_id)
            return web.Response(
                body=_MAP_JPEG_CACHE[cache_id],
                content_type="image/jpeg",
                headers={
                    "Cache-Control": "private, max-age=600",
                    "X-Latter-Cache": "HIT",
                },
            )

        coords = await self._async_resolve_coordinates(query)
        if coords is None:
            return web.Response(
                status=HTTPStatus.NOT_FOUND,
                text="Map location could not be geocoded",
            )
        lat, lon = coords
        event_tx, event_ty = _latlon_to_tile_xy(lat, lon, zoom)

        view_tx = event_tx + (pan_x * 0.62)
        view_ty = event_ty + (pan_y * 0.62)
        base_tx = int(view_tx) - 1
        base_ty = int(view_ty) - 1

        session = async_get_clientsession(self.hass)
        tile_images: dict[tuple[int, int], bytes] = {}
        n_tiles = 1 << zoom

        async def _fetch_single_tile(gx: int, gy: int) -> None:
            tx = gx % n_tiles
            if gy < 0 or gy >= n_tiles:
                return
            t_key = (zoom, tx, gy)
            if t_key in _OSM_TILE_CACHE:
                _OSM_TILE_CACHE.move_to_end(t_key)
                tile_images[(gx, gy)] = _OSM_TILE_CACHE[t_key]
                return
            tile_url = f"https://tile.openstreetmap.org/{zoom}/{tx}/{gy}.png"
            try:
                async with session.get(
                    tile_url,
                    headers={
                        "User-Agent": HTTP_USER_AGENT,
                        "Accept": "image/png,image/*;q=0.8",
                    },
                    timeout=ClientTimeout(total=4.0),
                ) as t_resp:
                    if t_resp.status == HTTPStatus.OK:
                        raw_t = await t_resp.read()
                        tile_images[(gx, gy)] = raw_t
                        _OSM_TILE_CACHE[t_key] = raw_t
                        while len(_OSM_TILE_CACHE) > MAX_OSM_TILE_CACHE:
                            _OSM_TILE_CACHE.popitem(last=False)
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
            view_tx,
            view_ty,
            event_tx,
            event_ty,
            base_tx,
            base_ty,
            width,
            height,
            is_circle,
        )

        _MAP_JPEG_CACHE[cache_id] = jpeg_bytes
        while len(_MAP_JPEG_CACHE) > MAX_ART_CACHE_ENTRIES:
            _MAP_JPEG_CACHE.popitem(last=False)

        return web.Response(
            body=jpeg_bytes,
            content_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=600", "X-Latter-Cache": "MISS"},
        )


class LatterBrandIconView(HomeAssistantView):
    """Serve the Latter brand icon PNG for Studio and HACS."""

    url = API_BRAND_ICON_PATH
    name = "api:latter:brand_icon"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the brand icon view."""
        self.hass = hass
        self._icon_path = Path(__file__).resolve().parent / "brand" / "icon.png"
        self._cached_bytes: bytes | None = None

    async def get(self, request: web.Request) -> web.Response:
        """Return the PNG icon bytes."""
        if self._cached_bytes is None:
            if not self._icon_path.is_file():
                return web.Response(status=HTTPStatus.NOT_FOUND, text="Icon not found")
            self._cached_bytes = await self.hass.async_add_executor_job(
                self._icon_path.read_bytes
            )
        return web.Response(
            body=self._cached_bytes,
            content_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )
