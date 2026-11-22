"""Signed wallpaper/screensaver proxy and admin multipart photo upload HTTP views (`L3`, 2 of 8 HTTP views, `M-P3-03`)."""

from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
import io
import logging
import math
from pathlib import Path
from typing import TypedDict, Unpack

from aiohttp import BodyPartReader, MultipartReader, web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from PIL import Image, ImageEnhance, ImageOps

from ..const import (
    API_WALLPAPER_PROXY_PATH,
    API_WALLPAPER_UPLOAD_PATH,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    DAY_NIGHT_SKY_PRESET_ID,
    DEFAULT_ART_SIZE,
    normalize_device_slug,
)
from ..coordinator import LatterCoordinator, resolve_coordinator
from ..hub_registry import get_latter_system, iter_coordinators
from ..media_cache import (
    _THUMB_LRU_CACHE,
    MAX_MULTIPART_PARTS,
    MAX_MULTIPART_TEXT_BYTES,
    MAX_THUMB_CACHE_ENTRIES,
    THUMB_CACHE_MAX_DIM,
    TRANSCODE_SEMAPHORE,
    cache_for_dims,
    cache_get,
    cache_put,
    get_circular_mask_surfaces,
    validate_pil_image_dimensions,
)
from ..presence.ble_fabric import get_ble_fabric
from ..studio.state_gates import find_by_subentry_id
from ..wallpapers.media_import import resolve_media_path
from ..wallpapers.models import (
    MAX_WALLPAPER_UPLOAD_BYTES,
    crop_and_fit_image,
    get_wallpaper_root,
    parse_photo_source,
    read_photo_bytes,
    render_builtin_preset_image,
)
from ..wallpapers.pools import list_photo_collections, list_wallpaper_catalog
from ..wallpapers.store import get_photo_crop, save_uploaded_photo_bytes
from .proxy_views import _parse_dimensions_and_shape

_LOGGER = logging.getLogger(__name__)

_MULTIPART_OVERHEAD_BYTES = 65536
_UPLOAD_CHUNK_BYTES = 65536
_PREVIEW_DEFAULT_DIM = 160
_PREVIEW_MIN_DIM = 32
_ORIG_MIN_EDGE = 64
_ORIG_MAX_EDGE = 1600
_WALLPAPER_DARKEN_FACTOR = 0.78


class _PhotoTranscodeOpts(TypedDict, total=False):
    """Keyword options for `_transcode_photo_to_baseline_jpeg`."""

    circular_mask: bool
    darken: float
    crop_x: float
    crop_y: float
    crop_zoom: float
    original_aspect: bool


class _PresetRenderOpts(TypedDict, total=False):
    """Keyword options for `_render_preset_to_baseline_jpeg`."""

    circular_mask: bool
    darken: float
    mode: str
    is_night: bool


@dataclass(slots=True)
class _WallpaperTargetSpec:
    """Validated target parameters for `LatterWallpaperProxyView`."""

    wp_source: str
    width: int
    height: int
    is_circle: bool
    mode_raw: str


@dataclass(slots=True)
class _ParsedUploadForm:
    """Parsed fields from a multipart photo upload request."""

    upload_scope: str = ""
    explicit_device_slug: str = ""
    target_slug: str = "system"
    subentry_id: str = ""
    filename: str = "photo.jpg"
    raw_bytes: bytes | None = None
    crop_x: float = 0.5
    crop_y: float = 0.5
    crop_zoom: float = 1.0
    photo_name: str | None = None
    collection_id: str | None = None


def _transcode_photo_to_baseline_jpeg(
    raw_bytes: bytes,
    width: int,
    height: int,
    **opts: Unpack[_PhotoTranscodeOpts],
) -> bytes:
    """Decode a library photo, apply non-destructive crop (or preserve original aspect), and encode Baseline JPEG."""
    circular_mask = opts.get("circular_mask", False)
    darken = opts.get("darken", _WALLPAPER_DARKEN_FACTOR)
    crop_x = opts.get("crop_x", 0.5)
    crop_y = opts.get("crop_y", 0.5)
    crop_zoom = opts.get("crop_zoom", 1.0)
    original_aspect = opts.get("original_aspect", False)

    with TRANSCODE_SEMAPHORE, Image.open(io.BytesIO(raw_bytes)) as img:
        validate_pil_image_dimensions(img)
        rgb = img.convert("RGB")
        if original_aspect:
            max_edge = max(_ORIG_MIN_EDGE, min(_ORIG_MAX_EDGE, max(int(width), int(height))))
            w, h = rgb.size
            if max(w, h) > max_edge:
                scale = float(max_edge) / float(max(w, h))
                fitted = rgb.resize(
                    (max(1, round(w * scale)), max(1, round(h * scale))),
                    resample=Image.Resampling.LANCZOS,
                )
            else:
                fitted = rgb.copy()
        else:
            fitted = crop_and_fit_image(rgb, width, height, crop_x, crop_y, crop_zoom)
            if darken < 1.0:
                fitted = ImageEnhance.Brightness(fitted).enhance(darken)
            if circular_mask:
                mask, black_bg = get_circular_mask_surfaces(width, height)
                fitted = Image.composite(fitted, black_bg, mask)

        out = io.BytesIO()
        fitted.save(
            out,
            format="JPEG",
            quality=88 if original_aspect else 85,
            optimize=True,
            progressive=False,
            subsampling=2,
        )
        return out.getvalue()


def _transcode_media_preview_jpeg(file_path: Path, width: int, height: int) -> bytes:
    """Read an HA `/media` image (`<= 15 MB`), EXIF-transpose, and encode a thumbnail Baseline JPEG."""
    size = file_path.stat().st_size
    if size <= 0 or size > MAX_WALLPAPER_UPLOAD_BYTES:
        raise ValueError("Media file exceeds 15 MB preview cap")
    raw_bytes = file_path.read_bytes()
    with TRANSCODE_SEMAPHORE, Image.open(io.BytesIO(raw_bytes)) as img:
        validate_pil_image_dimensions(img)
        rgb = ImageOps.exif_transpose(img).convert("RGB")
        fitted = ImageOps.fit(
            rgb,
            (width, height),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        out = io.BytesIO()
        fitted.save(
            out,
            format="JPEG",
            quality=80,
            optimize=True,
            progressive=False,
            subsampling=2,
        )
        return out.getvalue()


def _render_preset_to_baseline_jpeg(
    preset_id: str,
    width: int,
    height: int,
    **opts: Unpack[_PresetRenderOpts],
) -> bytes:
    """Render a bundled default wallpaper or Day & Night Sky directly to Baseline JPEG."""
    circular_mask = opts.get("circular_mask", False)
    darken = opts.get("darken", _WALLPAPER_DARKEN_FACTOR)
    mode = opts.get("mode", "wallpaper")
    is_night = opts.get("is_night", False)

    with TRANSCODE_SEMAPHORE:
        fitted = render_builtin_preset_image(
            preset_id, width, height, mode=mode, is_night=is_night
        )
        eff_darken = (
            1.0
            if preset_id == DAY_NIGHT_SKY_PRESET_ID and mode != "screensaver"
            else darken
        )
        if eff_darken < 1.0:
            fitted = ImageEnhance.Brightness(fitted).enhance(eff_darken)
        if circular_mask:
            mask, black_bg = get_circular_mask_surfaces(width, height)
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


def _jpeg_response(jpeg_bytes: bytes, *, hit: bool) -> web.Response:
    return web.Response(
        body=jpeg_bytes,
        content_type="image/jpeg",
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Latter-Cache": "HIT" if hit else "MISS",
        },
    )


def _validate_media_preview_params(
    hass: HomeAssistant,
    request: web.Request,
    target_device: str,
    media_root: str,
    media_path: str,
) -> tuple[tuple[int, int] | None, web.Response | None]:
    """Validate scope and signature for `/media` import thumbnail requests."""
    if normalize_device_slug(target_device) != "system":
        return None, web.Response(
            status=HTTPStatus.FORBIDDEN, text="Media previews require system scope"
        )
    sys_obj = get_latter_system(hass)
    if sys_obj is None or sys_obj.url_signer is None:
        return None, web.Response(
            status=HTTPStatus.NOT_FOUND, text="Latter System not initialized"
        )
    width, height, _is_circle, _shape_str = _parse_dimensions_and_shape(
        request,
        _PREVIEW_DEFAULT_DIM,
        _PREVIEW_DEFAULT_DIM,
        min_dim=_PREVIEW_MIN_DIM,
        max_dim=THUMB_CACHE_MAX_DIM,
        default_circle=False,
    )
    if not sys_obj.url_signer.verify_resource(
        f"media_preview:{media_root}|{media_path}|{width}|{height}",
        sig=request.query.get("sig"),
    ):
        return None, web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")
    return (width, height), None


async def _async_serve_media_preview(
    hass: HomeAssistant,
    request: web.Request,
    target_device: str,
    media_root: str,
    media_path: str,
) -> web.Response:
    """Serve a signed 160x160 `/media` import thumbnail."""
    dims, err_resp = _validate_media_preview_params(
        hass, request, target_device, media_root, media_path
    )
    if err_resp is not None or dims is None:
        return err_resp or web.Response(status=HTTPStatus.FORBIDDEN)
    width, height = dims

    media_dirs = getattr(hass.config, "media_dirs", None)
    resolved = await hass.async_add_executor_job(
        resolve_media_path, media_dirs, media_root, media_path
    )
    if resolved is None or not resolved.is_file():
        return web.Response(status=HTTPStatus.NOT_FOUND, text="Media file not found")

    m_key = (f"media:{media_root}/{media_path}", width, height, False, 1.0)
    cached_m = cache_get(_THUMB_LRU_CACHE, m_key)
    if cached_m is not None:
        return _jpeg_response(cached_m, hit=True)
    try:
        jpeg_bytes = await hass.async_add_executor_job(
            _transcode_media_preview_jpeg, resolved, width, height
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Media preview transcode failed: %s", err)
        return web.Response(
            status=HTTPStatus.UNPROCESSABLE_ENTITY, text="Media preview error"
        )
    cache_put(_THUMB_LRU_CACHE, m_key, jpeg_bytes, MAX_THUMB_CACHE_ENTRIES)
    return _jpeg_response(jpeg_bytes, hit=False)


def _resolve_wallpaper_target(
    hass: HomeAssistant,
    request: web.Request,
    target_device: str,
    mode_raw: str,
) -> tuple[_WallpaperTargetSpec | None, web.Response | None]:
    """Validate signature and dimensions for device or system wallpaper requests."""
    coordinator = resolve_coordinator(hass, target_device)
    if coordinator is not None:
        fallback_src = (
            coordinator.screensaver_photo_source
            if mode_raw == "screensaver"
            else coordinator.wallpaper_source
        )
        wp_source = str(request.query.get("src") or fallback_src).strip()
        if not wp_source:
            return None, web.Response(
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
            f"wallpaper:{wp_source}|{width}|{height}|{shape_str}|{mode_raw}",
            sig=request.query.get("sig"),
        )
    elif normalize_device_slug(target_device) == "system":
        sys_obj = get_latter_system(hass)
        if sys_obj is None or sys_obj.url_signer is None:
            return None, web.Response(
                status=HTTPStatus.NOT_FOUND, text="Latter System not initialized"
            )
        wp_source = str(request.query.get("src") or "").strip()
        if not wp_source:
            return None, web.Response(
                status=HTTPStatus.NOT_FOUND, text="No wallpaper specified"
            )
        width, height, is_circle, shape_str = _parse_dimensions_and_shape(
            request, DEFAULT_ART_SIZE, DEFAULT_ART_SIZE, default_circle=False
        )
        verified = sys_obj.url_signer.verify_resource(
            f"wallpaper:{wp_source}|{width}|{height}|{shape_str}|{mode_raw}",
            sig=request.query.get("sig"),
        )
    else:
        return None, web.Response(
            status=HTTPStatus.NOT_FOUND, text="Unknown target device"
        )

    if not verified:
        return None, web.Response(status=HTTPStatus.FORBIDDEN, text="Invalid signature")
    return _WallpaperTargetSpec(wp_source, width, height, is_circle, mode_raw), None


async def _async_render_wallpaper_source(
    hass: HomeAssistant,
    spec: _WallpaperTargetSpec,
    darken_factor: float,
    *,
    is_night: bool,
) -> tuple[bytes | None, web.Response | None]:
    """Render a preset or transcode a photo library item into Baseline JPEG."""
    if spec.wp_source.startswith("preset:"):
        try:
            jpeg_bytes = await hass.async_add_executor_job(
                lambda: _render_preset_to_baseline_jpeg(
                    spec.wp_source,
                    spec.width,
                    spec.height,
                    circular_mask=(spec.is_circle and spec.mode_raw != "original"),
                    darken=darken_factor,
                    mode=spec.mode_raw,
                    is_night=is_night,
                )
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Wallpaper preset rendering failed: %s", err)
            return None, web.Response(
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
                text="Wallpaper processing error",
            )
        return jpeg_bytes, None

    if parse_photo_source(spec.wp_source) is not None:
        raw_bytes = await hass.async_add_executor_job(
            read_photo_bytes, get_wallpaper_root(hass), spec.wp_source
        )
        if not raw_bytes:
            return None, web.Response(
                status=HTTPStatus.NOT_FOUND, text="Wallpaper source unreadable"
            )
        crop = get_photo_crop(spec.wp_source)
        try:
            jpeg_bytes = await hass.async_add_executor_job(
                lambda: _transcode_photo_to_baseline_jpeg(
                    raw_bytes,
                    spec.width,
                    spec.height,
                    circular_mask=(spec.is_circle and spec.mode_raw != "original"),
                    darken=darken_factor,
                    crop_x=crop.x,
                    crop_y=crop.y,
                    crop_zoom=crop.zoom,
                    original_aspect=(spec.mode_raw == "original"),
                )
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Wallpaper Pillow processing failed: %s", err)
            return None, web.Response(
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
                text="Wallpaper processing error",
            )
        return jpeg_bytes, None

    return None, web.Response(
        status=HTTPStatus.FORBIDDEN, text="Unsupported wallpaper source"
    )


class LatterWallpaperProxyView(HomeAssistantView):
    """Serves signed Baseline-JPEG wallpapers, Photo Frame screensavers, originals, and `/media` previews."""

    requires_auth = False
    url = API_WALLPAPER_PROXY_PATH
    name = "api:latter:wallpaper_proxy"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the wallpaper proxy view."""
        self.hass = hass

    async def get(self, request: web.Request, target_device: str) -> web.Response:
        """Handle GET /api/latter/wallpaper/{target_device}?w=...&h=...&mode=...&src=..."""
        media_root = str(request.query.get("media_root") or "").strip()
        media_path = str(request.query.get("media_path") or "").strip()
        if media_root or media_path:
            return await _async_serve_media_preview(
                self.hass, request, target_device, media_root, media_path
            )

        mode_raw = str(request.query.get("mode") or "wallpaper").strip().lower()
        if mode_raw not in ("wallpaper", "screensaver", "original"):
            return web.Response(
                status=HTTPStatus.BAD_REQUEST, text="Invalid wallpaper mode"
            )

        spec, err_resp = _resolve_wallpaper_target(
            self.hass, request, target_device, mode_raw
        )
        if err_resp is not None or spec is None:
            return err_resp or web.Response(status=HTTPStatus.NOT_FOUND)

        darken_factor = _WALLPAPER_DARKEN_FACTOR if mode_raw == "wallpaper" else 1.0
        sun_state = self.hass.states.get("sun.sun")
        is_night = bool(sun_state is not None and sun_state.state == "below_horizon")
        cache_tag = f"wp:{spec.wp_source}"
        if mode_raw == "original":
            cache_tag = f"wp:{spec.wp_source}:orig"
        elif spec.wp_source == DAY_NIGHT_SKY_PRESET_ID and mode_raw == "screensaver":
            cache_tag = f"wp:{spec.wp_source}:{'night' if is_night else 'day'}"

        cache_bucket, cache_limit = cache_for_dims(spec.width, spec.height)
        cache_key = (cache_tag, spec.width, spec.height, spec.is_circle, darken_factor)
        cached_bytes = cache_get(cache_bucket, cache_key)
        if cached_bytes is not None:
            return _jpeg_response(cached_bytes, hit=True)

        jpeg_bytes, render_err = await _async_render_wallpaper_source(
            self.hass, spec, darken_factor, is_night=is_night
        )
        if render_err is not None or jpeg_bytes is None:
            return render_err or web.Response(status=HTTPStatus.UNPROCESSABLE_ENTITY)

        cache_put(cache_bucket, cache_key, jpeg_bytes, cache_limit)
        return _jpeg_response(jpeg_bytes, hit=False)


def _parse_multipart_float(raw: str, default: float) -> float:
    try:
        val = float(raw)
        return val if math.isfinite(val) else default
    except (TypeError, ValueError):
        return default


async def _async_read_bounded_part_text(
    part: BodyPartReader, max_bytes: int = MAX_MULTIPART_TEXT_BYTES
) -> str:
    """Read a multipart text field up to `max_bytes`, rejecting oversize metadata fields (`M-P1-34`)."""
    buf = bytearray()
    while True:
        chunk = await part.read_chunk(min(1024, max_bytes + 1))
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise ValueError("Multipart text field exceeds size limit")
    return buf.decode("utf-8", errors="replace").strip()


_MULTIPART_TEXT_FIELD_LIMITS: dict[str, int] = {
    "scope": MAX_MULTIPART_TEXT_BYTES,
    "device_slug": MAX_MULTIPART_TEXT_BYTES,
    "subentry_id": MAX_MULTIPART_TEXT_BYTES,
    "crop_x": 64,
    "crop_y": 64,
    "crop_zoom": 64,
    "name": 256,
    "collection_id": 128,
}


def _apply_multipart_text_value(
    form: _ParsedUploadForm, field_name: str, val: str
) -> None:
    """Assign a bounded text multipart field onto `_ParsedUploadForm`."""
    if field_name == "scope":
        form.upload_scope = val.lower()
    elif field_name == "device_slug" and val:
        form.explicit_device_slug = val
        form.target_slug = normalize_device_slug(val)
    elif field_name == "subentry_id" and val:
        form.subentry_id = val
    elif field_name == "crop_x":
        form.crop_x = _parse_multipart_float(val, 0.5)
    elif field_name == "crop_y":
        form.crop_y = _parse_multipart_float(val, 0.5)
    elif field_name == "crop_zoom":
        form.crop_zoom = _parse_multipart_float(val, 1.0)
    elif field_name == "name":
        form.photo_name = val or None
    elif field_name == "collection_id":
        form.collection_id = val or None


async def _async_apply_multipart_field(
    form: _ParsedUploadForm, part: BodyPartReader
) -> web.Response | None:
    """Ingest a single multipart field into `form`, returning an error `web.Response` if oversize."""
    field_name = str(getattr(part, "name", "") or "")
    max_text_len = _MULTIPART_TEXT_FIELD_LIMITS.get(field_name)
    if max_text_len is not None:
        val = await _async_read_bounded_part_text(part, max_text_len)
        _apply_multipart_text_value(form, field_name, val)
        return None
    if field_name == "file":
        form.filename = str(getattr(part, "filename", None) or form.filename)
        chunks = bytearray()
        while True:
            chunk = await part.read_chunk(_UPLOAD_CHUNK_BYTES)
            if not chunk:
                break
            chunks.extend(chunk)
            if len(chunks) > MAX_WALLPAPER_UPLOAD_BYTES:
                return web.json_response(
                    {"error": "Wallpaper upload exceeds 15 MB limit"},
                    status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                )
        form.raw_bytes = bytes(chunks)
    else:
        await part.release()
    return None


async def _async_parse_upload_multipart(
    request: web.Request,
) -> tuple[_ParsedUploadForm | None, web.Response | None]:
    """Parse bounded multipart fields from `request`."""
    explicit_slug = str(request.query.get("device_slug") or "").strip()
    form = _ParsedUploadForm(
        explicit_device_slug=explicit_slug,
        target_slug=normalize_device_slug(explicit_slug or "system"),
        subentry_id=str(request.query.get("subentry_id") or "").strip(),
    )
    try:
        reader = await request.multipart()
    except Exception:  # noqa: BLE001
        return None, web.json_response(
            {"error": "Expected multipart/form-data request"},
            status=HTTPStatus.BAD_REQUEST,
        )

    parts_seen = 0
    while True:
        part = await reader.next()
        if part is None:
            break
        parts_seen += 1
        if parts_seen > MAX_MULTIPART_PARTS:
            return None, web.json_response(
                {"error": "Too many multipart form fields"},
                status=HTTPStatus.BAD_REQUEST,
            )
        if isinstance(part, MultipartReader):
            await part.release()
            continue
        try:
            err_resp = await _async_apply_multipart_field(form, part)
        except ValueError as err:
            return None, web.json_response(
                {"error": str(err)}, status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE
            )
        if err_resp is not None:
            return None, err_resp

    if not form.raw_bytes:
        return None, web.json_response(
            {"error": "Multipart 'file' field is missing or empty"},
            status=HTTPStatus.BAD_REQUEST,
        )
    return form, None


def _resolve_upload_coordinator(
    hass: HomeAssistant, form: _ParsedUploadForm
) -> tuple[LatterCoordinator | None, web.Response | None]:
    """Resolve optional target `LatterCoordinator` for a photo upload."""
    if form.upload_scope == "system":
        form.target_slug = "system"
        return None, None
    if form.subentry_id:
        coord = find_by_subentry_id(iter_coordinators(hass), form.subentry_id)
        if coord is None:
            return None, web.json_response(
                {"error": f"Unknown subentry_id: {form.subentry_id}"},
                status=HTTPStatus.NOT_FOUND,
            )
        return coord, None
    if form.explicit_device_slug and form.target_slug != "system":
        coord = resolve_coordinator(hass, form.target_slug)
        if coord is None:
            return None, web.json_response(
                {"error": f"Unknown device_slug: {form.target_slug}"},
                status=HTTPStatus.NOT_FOUND,
            )
        return coord, None
    return None, None


async def _async_apply_uploaded_wallpaper(
    hass: HomeAssistant, coord: LatterCoordinator, source_id: str
) -> list[dict[str, object]]:
    """Assign `source_id` as `coord`'s active wallpaper and return its refreshed wallpaper catalog."""
    async with coord.config_lock:
        merged = {
            **coord.device_data,
            CONF_WALLPAPER_MODE: "single",
            CONF_WALLPAPER_SOURCE: source_id,
        }
        coord.current_wallpaper = source_id
        coord.set_configured_wallpaper_source(source_id)
        coord.schedule_persist_runtime_state()
        coord.update_device_config(merged)
    coord.bind_wallpaper_cycle_timer()
    coord.async_notify_listeners()
    coord_slug = coord.device_slug
    coord_wp_src = coord.wallpaper_source
    coord_wp_favs = list(coord.wallpaper_favorites)
    coord_signer = coord.sign_payload_resource
    coord_shape = coord.display_shape
    catalog: list[dict[str, object]] = await hass.async_add_executor_job(
        lambda: list_wallpaper_catalog(
            hass,
            coord_slug,
            coord_wp_src,
            coord_wp_favs,
            sign_resource=coord_signer,
            display_shape=coord_shape,
        )
    )
    return catalog


class LatterWallpaperUploadView(HomeAssistantView):
    """Admin-authenticated multipart photo upload endpoint (`POST /api/latter/wallpaper/upload`, `<= 15 MB`)."""

    requires_auth = True
    url = API_WALLPAPER_UPLOAD_PATH
    name = "api:latter:wallpaper_upload"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the multipart photo upload view."""
        self.hass = hass

    async def post(self, request: web.Request) -> web.Response:
        """Handle admin multipart/form-data upload (`file` <= 15 MB, optional crop/name/collection/device)."""
        user = request.get("hass_user")
        if user is None or not getattr(user, "is_admin", False):
            return web.json_response(
                {"error": "Administrator privileges required"},
                status=HTTPStatus.FORBIDDEN,
            )
        if (
            request.content_length is not None
            and request.content_length
            > MAX_WALLPAPER_UPLOAD_BYTES + _MULTIPART_OVERHEAD_BYTES
        ):
            return web.json_response(
                {"error": "Wallpaper upload exceeds 15 MB limit"},
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )

        form, err_resp = await _async_parse_upload_multipart(request)
        if err_resp is not None or form is None or form.raw_bytes is None:
            return err_resp or web.json_response(
                {"error": "Multipart 'file' field is missing or empty"},
                status=HTTPStatus.BAD_REQUEST,
            )

        coord, coord_err = _resolve_upload_coordinator(self.hass, form)
        if coord_err is not None:
            return coord_err

        raw_bytes = form.raw_bytes
        try:
            saved_photo = await self.hass.async_add_executor_job(
                lambda: save_uploaded_photo_bytes(
                    self.hass,
                    form.filename,
                    raw_bytes,
                    crop_x=form.crop_x,
                    crop_y=form.crop_y,
                    crop_zoom=form.crop_zoom,
                    name=form.photo_name,
                    collection_id=form.collection_id,
                )
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Photo multipart upload failed: %s", err)
            return web.json_response(
                {"error": f"Invalid image upload: {err}"},
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
            )

        source_id = str(saved_photo["id"])
        out_filename = str(saved_photo["filename"])
        sys_obj = get_latter_system(self.hass)
        sys_signer = (
            sys_obj.url_signer.sign_payload_resource
            if sys_obj is not None and sys_obj.url_signer is not None
            else None
        )
        system_wallpapers = await self.hass.async_add_executor_job(
            lambda: list_wallpaper_catalog(
                self.hass,
                "system",
                "",
                [],
                sign_resource=sys_signer,
                display_shape="square",
            )
        )
        photo_collections = await self.hass.async_add_executor_job(
            list_photo_collections
        )

        if coord is not None:
            wallpapers = await _async_apply_uploaded_wallpaper(
                self.hass, coord, source_id
            )
        else:
            wallpapers = system_wallpapers
            get_ble_fabric(self.hass).notify_occupancy_listeners()

        photo_entry = next(
            (w for w in system_wallpapers if w.get("id") == source_id), saved_photo
        )
        return web.json_response(
            {
                "ok": True,
                "photo_id": source_id,
                "filename": out_filename,
                "source_id": source_id,
                "photo": photo_entry,
                "photo_collections": photo_collections,
                "wallpapers": wallpapers,
                "system_wallpapers": system_wallpapers,
            }
        )
