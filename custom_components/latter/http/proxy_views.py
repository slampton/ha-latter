"""Local-only signed artwork transcoder and brand icon HTTP views (`L3`, 2 of 8 HTTP views, `M-P3-03`)."""

from __future__ import annotations

import hashlib
from http import HTTPStatus
import ipaddress
import logging
from pathlib import Path
from typing import TypedDict, Unpack

from aiohttp import ClientTimeout, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url

from ..const import API_ARTWORK_PROXY_PATH, API_BRAND_ICON_PATH
from ..coordinator import LatterCoordinator, resolve_coordinator
from ..media.linking import resolve_ma_counterpart_entity
from ..media_cache import (
    _ARTWORK_LRU_CACHE,
    MAX_ART_CACHE_ENTRIES,
    MAX_UPSTREAM_IMAGE_BYTES,
    cache_get,
    cache_put,
    transcode_to_baseline_jpeg,
)

_LOGGER = logging.getLogger(__name__)

_DEFAULT_MIN_DIM = 32
_DEFAULT_MAX_DIM = 1200
_LOCAL_FETCH_CHUNK_BYTES = 65536
_LOCAL_FETCH_TIMEOUT_S = 8
_DIGEST_PREFIX_BYTES = 4096
_DIGEST_HEX_LEN = 16


class _RenderDimOpts(TypedDict, total=False):
    """Keyword bounds and circle-mask defaults for `_parse_dimensions_and_shape`."""

    min_dim: int
    max_dim: int
    default_circle: bool | None


def _parse_dimensions_and_shape(
    request: web.Request,
    default_w: int,
    default_h: int,
    **opts: Unpack[_RenderDimOpts],
) -> tuple[int, int, bool, str]:
    """Parse and clamp `(width, height, is_circle, shape_str)` query parameters."""
    min_dim = opts.get("min_dim", _DEFAULT_MIN_DIM)
    max_dim = opts.get("max_dim", _DEFAULT_MAX_DIM)
    default_circle = opts.get("default_circle")
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
    **opts: Unpack[_RenderDimOpts],
) -> tuple[int, int, bool, str]:
    """Parse and clamp render params for a Device coordinator."""
    default_w, default_h = coordinator.art_dimensions
    return _parse_dimensions_and_shape(request, default_w, default_h, **opts)


def _is_private_or_loopback_client(request: web.Request) -> bool:
    """Return True when `request.remote` is absent (in-process test) or a private/loopback/link-local LAN IP (`M-P1-33`)."""
    host_str = str(getattr(request, "remote", None) or "").strip()
    if not host_str:
        return True
    if "%" in host_str:
        host_str = host_str.split("%", 1)[0]
    try:
        ip = ipaddress.ip_address(host_str)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local)


def _jpeg_cache_response(jpeg_bytes: bytes, *, hit: bool) -> web.Response:
    return web.Response(
        body=jpeg_bytes,
        content_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Latter-Cache": "HIT" if hit else "MISS",
        },
    )


def _resolve_artwork_candidates_and_path(
    hass: HomeAssistant, coordinator: LatterCoordinator
) -> tuple[list[str], str | None]:
    """Return `(candidate_speakers, fallback_pic_path)` for `coordinator`."""
    ma_counterpart = resolve_ma_counterpart_entity(hass, coordinator.active_speaker)
    candidates: list[str] = []
    for spk in (coordinator.active_speaker, ma_counterpart):
        if spk and spk not in candidates:
            candidates.append(spk)

    pic_path: str | None = None
    for spk in candidates:
        st_obj = hass.states.get(spk)
        if st_obj is None:
            continue
        attrs = st_obj.attributes
        cand_pic = (
            attrs.get("entity_picture_local")
            or attrs.get("entity_picture")
            or attrs.get("media_image_url")
        )
        if cand_pic:
            pic_path = str(cand_pic)
            break
    if not pic_path and coordinator.last_valid_raw_pic:
        pic_path = str(coordinator.last_valid_raw_pic)
    return candidates, pic_path


async def _async_try_entity_media_image(
    hass: HomeAssistant,
    candidates: list[str],
    dims: tuple[int, int, bool],
) -> tuple[bytes | None, tuple[str, int, int, bool, float] | None, web.Response | None]:
    """Query `media_player` entity `async_get_media_image()`, returning `(raw_bytes, cache_key, early_response)`."""
    comp = hass.data.get("media_player")
    get_entity = getattr(comp, "get_entity", None)
    if not callable(get_entity):
        return None, None, None

    width, height, circular = dims
    for spk in candidates:
        ent = get_entity(spk)
        get_img = getattr(ent, "async_get_media_image", None)
        if not callable(get_img):
            continue
        st_spk = hass.states.get(spk)
        tok = ""
        if st_spk is not None:
            tok = str(
                st_spk.attributes.get("entity_picture_local")
                or st_spk.attributes.get("entity_picture")
                or st_spk.attributes.get("media_image_url")
                or st_spk.attributes.get("media_title")
                or ""
            )
        if tok:
            ent_cache_key = (f"ent:{spk}:{tok}", width, height, circular, 1.0)
            cached_ent = cache_get(_ARTWORK_LRU_CACHE, ent_cache_key)
            if cached_ent is not None:
                return None, None, _jpeg_cache_response(cached_ent, hit=True)
        try:
            img_data, _mime = await get_img()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("async_get_media_image(%s) failed: %s", spk, err)
            img_data = None
        if img_data:
            if len(img_data) > MAX_UPSTREAM_IMAGE_BYTES:
                return (
                    None,
                    None,
                    web.Response(
                        status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        text="Upstream artwork exceeds 8 MB limit",
                    ),
                )
            raw_bytes = bytes(img_data)
            digest_tok = (
                tok
                or hashlib.sha256(raw_bytes[:_DIGEST_PREFIX_BYTES]).hexdigest()[
                    :_DIGEST_HEX_LEN
                ]
            )
            return (
                raw_bytes,
                (f"ent:{spk}:{digest_tok}", width, height, circular, 1.0),
                None,
            )
    return None, None, None


async def _async_download_local_artwork_bytes(
    hass: HomeAssistant, pic_url: str
) -> tuple[bytes | None, web.Response | None]:
    """Download bounded local HA artwork bytes without following redirects."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(
            pic_url,
            timeout=ClientTimeout(total=_LOCAL_FETCH_TIMEOUT_S),
            allow_redirects=False,
        ) as resp:
            if resp.status != HTTPStatus.OK:
                return None, web.Response(
                    status=HTTPStatus.BAD_GATEWAY,
                    text=f"Upstream returned {resp.status}",
                )
            if resp.content_length and resp.content_length > MAX_UPSTREAM_IMAGE_BYTES:
                return None, web.Response(
                    status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    text="Upstream artwork exceeds 8 MB limit",
                )
            chunks = bytearray()
            async for chunk in resp.content.iter_chunked(_LOCAL_FETCH_CHUNK_BYTES):
                chunks.extend(chunk)
                if len(chunks) > MAX_UPSTREAM_IMAGE_BYTES:
                    return None, web.Response(
                        status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        text="Upstream artwork exceeds 8 MB limit",
                    )
            return bytes(chunks), None
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Failed fetching local HA artwork from %s: %s", pic_url, err)
        return None, web.Response(
            status=HTTPStatus.BAD_GATEWAY, text="Upstream error"
        )


async def _async_fetch_local_ha_artwork(
    hass: HomeAssistant,
    pic_path: str | None,
    dims: tuple[int, int, bool],
) -> tuple[bytes | None, tuple[str, int, int, bool, float] | None, web.Response | None]:
    """Fetch local `/` HA artwork path with redirect blocking and 8 MB byte ceiling (`M-P1-31`)."""
    if not pic_path:
        return None, None, web.Response(status=HTTPStatus.NOT_FOUND, text="No artwork")
    raw_pic = str(pic_path).strip()
    if not (raw_pic.startswith("/") and not raw_pic.startswith("//")):
        return (
            None,
            None,
            web.Response(
                status=HTTPStatus.FORBIDDEN,
                text="External artwork URLs are disabled",
            ),
        )
    try:
        base_url = get_url(hass, allow_internal=True, prefer_external=False)
    except Exception:  # noqa: BLE001
        base_url = "http://127.0.0.1:8123"
    width, height, circular = dims
    pic_url = f"{base_url.rstrip('/')}{raw_pic}"
    cache_key = (pic_url, width, height, circular, 1.0)
    cached_bytes = cache_get(_ARTWORK_LRU_CACHE, cache_key)
    if cached_bytes is not None:
        return None, None, _jpeg_cache_response(cached_bytes, hit=True)
    raw_bytes, err_resp = await _async_download_local_artwork_bytes(hass, pic_url)
    if err_resp is not None or raw_bytes is None:
        return None, None, err_resp
    return raw_bytes, cache_key, None


async def _async_serve_speaker_artwork(
    hass: HomeAssistant,
    request: web.Request,
    coordinator: LatterCoordinator,
) -> web.Response:
    """Fetch active speaker artwork strictly via HA Core `media_player` entity or local `/` HA paths (`M-P1-31`, Zero-WAN)."""
    width, height, circular, shape_str = _parse_render_params(
        request, coordinator, default_circle=None
    )
    if not coordinator.verify_resource(
        f"artwork|{width}|{height}|{shape_str}",
        sig=request.query.get("sig"),
    ):
        return web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")

    candidates, pic_path = _resolve_artwork_candidates_and_path(hass, coordinator)
    dims = (width, height, circular)
    raw_bytes, cache_key, early_resp = await _async_try_entity_media_image(
        hass, candidates, dims
    )
    if early_resp is not None:
        return early_resp
    if raw_bytes is None:
        raw_bytes, cache_key, early_resp = await _async_fetch_local_ha_artwork(
            hass, pic_path, dims
        )
        if early_resp is not None or raw_bytes is None:
            return early_resp or web.Response(
                status=HTTPStatus.NOT_FOUND, text="No artwork"
            )

    try:
        jpeg_bytes = await hass.async_add_executor_job(
            transcode_to_baseline_jpeg,
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

    if cache_key is not None:
        cache_put(_ARTWORK_LRU_CACHE, cache_key, jpeg_bytes, MAX_ART_CACHE_ENTRIES)
    return _jpeg_cache_response(jpeg_bytes, hit=False)


class LatterArtworkTranscoderView(HomeAssistantView):
    """Universal Baseline-JPEG artwork proxy (`/api/latter/artwork/{target_device}`)."""

    requires_auth = False
    url = API_ARTWORK_PROXY_PATH
    name = "api:latter:artwork_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the universal artwork transcoder view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Handle GET /api/latter/artwork/{target_device}?w=...&h=...&v=..."""
        coordinator = resolve_coordinator(self.hass, target_device)
        if coordinator is None:
            return web.Response(
                status=HTTPStatus.NOT_FOUND, text="Unknown target device"
            )
        return await _async_serve_speaker_artwork(self.hass, request, coordinator)


class LatterBrandIconView(HomeAssistantView):
    """Serve the Latter brand icon PNG for Studio and HACS."""

    url = API_BRAND_ICON_PATH
    name = "api:latter:brand_icon"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the brand icon view."""
        self.hass = hass
        self._icon_path = Path(__file__).resolve().parent.parent / "brand" / "icon.png"
        self._cached_bytes: bytes | None = None

    async def get(self, _request: web.Request) -> web.Response:
        """Return the PNG icon bytes."""
        if self._cached_bytes is None:
            if not self._icon_path.is_file():
                return web.Response(
                    status=HTTPStatus.NOT_FOUND, text="Icon not found"
                )
            self._cached_bytes = await self.hass.async_add_executor_job(
                self._icon_path.read_bytes
            )
        return web.Response(
            body=self._cached_bytes,
            content_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )
