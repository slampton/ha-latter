"""Thread-safe LRU image caches, circular-mask surfaces, and Baseline-JPEG transcoder (`L1a`)."""

from __future__ import annotations

from collections import OrderedDict
import io
import threading
from typing import Final

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

MAX_ART_CACHE_ENTRIES: Final = 24
MAX_THUMB_CACHE_ENTRIES: Final = 128
THUMB_CACHE_MAX_DIM: Final = 240
MAX_UPSTREAM_IMAGE_BYTES: Final = 8 * 1024 * 1024
MAX_IMAGE_SIDE: Final = 8192
MAX_IMAGE_PIXELS: Final = 25_000_000
MAX_MULTIPART_PARTS: Final = 16
MAX_MULTIPART_TEXT_BYTES: Final = 1024

_MAX_MASK_CACHE_ENTRIES: Final = 16
_LARGE_FRAME_PIXELS: Final = 300_000
_ROT_90: Final = 90
_ROT_180: Final = 180
_ROT_270: Final = 270

type ImageCacheKey = tuple[str, int, int, bool, float]

_IMAGE_CACHE_LOCK: Final = threading.Lock()
TRANSCODE_SEMAPHORE: Final = threading.BoundedSemaphore(4)
_TRANSCODE_SEMAPHORE: Final = TRANSCODE_SEMAPHORE

_ARTWORK_LRU_CACHE: OrderedDict[ImageCacheKey, bytes] = OrderedDict()
_THUMB_LRU_CACHE: OrderedDict[ImageCacheKey, bytes] = OrderedDict()
_CIRCULAR_MASK_CACHE: dict[tuple[int, int], tuple[Image.Image, Image.Image]] = {}


def validate_pil_image_dimensions(img: Image.Image) -> None:
    """Reject oversize or decompression-bomb images (`> 8192 px` side or `> 25 MP`) before decode (`M-P1-34`)."""
    w, h = img.size
    if (
        w <= 0
        or h <= 0
        or w > MAX_IMAGE_SIDE
        or h > MAX_IMAGE_SIDE
        or (w * h) > MAX_IMAGE_PIXELS
    ):
        raise ValueError(
            f"Image dimensions {w}x{h} exceed safety ceiling ({MAX_IMAGE_SIDE}px / {MAX_IMAGE_PIXELS} pixels)"
        )


def clear_http_caches() -> None:
    """Clear in-memory LRU caches for artwork, thumbnails, and circular masks under `_IMAGE_CACHE_LOCK`."""
    with _IMAGE_CACHE_LOCK:
        _ARTWORK_LRU_CACHE.clear()
        _THUMB_LRU_CACHE.clear()
        _CIRCULAR_MASK_CACHE.clear()


def get_circular_mask_surfaces(
    width: int, height: int
) -> tuple[Image.Image, Image.Image]:
    """Return thread-safe cached `(mask_L, black_bg_RGB)` PIL surfaces for `(width, height)` (`M-P0-03`, `M-P1-34`)."""
    key = (width, height)
    with _IMAGE_CACHE_LOCK:
        cached = _CIRCULAR_MASK_CACHE.get(key)
        if cached is not None:
            return cached
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, width - 1, height - 1), fill=255)
    black_bg = Image.new("RGB", (width, height), (0, 0, 0))
    with _IMAGE_CACHE_LOCK:
        if len(_CIRCULAR_MASK_CACHE) >= _MAX_MASK_CACHE_ENTRIES:
            _CIRCULAR_MASK_CACHE.clear()
        _CIRCULAR_MASK_CACHE[key] = (mask, black_bg)
    return mask, black_bg


_get_circular_mask_surfaces = get_circular_mask_surfaces


def transcode_to_baseline_jpeg(  # noqa: PLR0913, PLR0917
    raw_bytes: bytes,
    width: int,
    height: int,
    circular_mask: bool = False,
    darken: float = 1.0,
    rotate_deg: int = 0,
    fast_live: bool = False,
) -> bytes:
    """Decode any image format, resize to `(width, height)`, and encode non-progressive Baseline JPEG."""
    with TRANSCODE_SEMAPHORE, Image.open(io.BytesIO(raw_bytes)) as img:
        validate_pil_image_dimensions(img)
        img_rgb = img.convert("RGB")
        if rotate_deg == _ROT_90:
            img_rgb = img_rgb.transpose(Image.Transpose.ROTATE_270)
        elif rotate_deg == _ROT_180:
            img_rgb = img_rgb.transpose(Image.Transpose.ROTATE_180)
        elif rotate_deg == _ROT_270:
            img_rgb = img_rgb.transpose(Image.Transpose.ROTATE_90)
        fitted = ImageOps.fit(
            img_rgb,
            (width, height),
            method=(
                Image.Resampling.BILINEAR
                if fast_live
                else Image.Resampling.LANCZOS
            ),
            centering=(0.5, 0.5),
        )
        if darken < 1.0:
            fitted = ImageEnhance.Brightness(fitted).enhance(darken)
        if circular_mask:
            mask, black_bg = get_circular_mask_surfaces(width, height)
            fitted = Image.composite(fitted, black_bg, mask)

        out = io.BytesIO()
        live_quality = 72 if (width * height > _LARGE_FRAME_PIXELS) else 80
        fitted.save(
            out,
            format="JPEG",
            quality=live_quality if fast_live else 85,
            optimize=not fast_live,
            progressive=False,
            subsampling=2,
        )
        return out.getvalue()


_transcode_to_baseline_jpeg = transcode_to_baseline_jpeg


def cache_for_dims(
    width: int, height: int
) -> tuple[OrderedDict[ImageCacheKey, bytes], int]:
    """Select the 128-entry thumbnail cache (`<= 240 px`) or 24-entry full-size art cache."""
    if max(int(width), int(height)) <= THUMB_CACHE_MAX_DIM:
        return _THUMB_LRU_CACHE, MAX_THUMB_CACHE_ENTRIES
    return _ARTWORK_LRU_CACHE, MAX_ART_CACHE_ENTRIES


_cache_for_dims = cache_for_dims


def cache_get(
    bucket: OrderedDict[ImageCacheKey, bytes],
    key: ImageCacheKey,
) -> bytes | None:
    """Thread-safely look up and touch `key` in `bucket`."""
    with _IMAGE_CACHE_LOCK:
        val = bucket.get(key)
        if val is not None:
            bucket.move_to_end(key)
        return val


_cache_get = cache_get


def cache_put(
    bucket: OrderedDict[ImageCacheKey, bytes],
    key: ImageCacheKey,
    value: bytes,
    limit: int,
) -> None:
    """Thread-safely insert `value` under `key` in `bucket`, evicting oldest items past `limit`."""
    with _IMAGE_CACHE_LOCK:
        bucket[key] = value
        while len(bucket) > limit:
            bucket.popitem(last=False)


_cache_put = cache_put


def evict_wallpaper_lru_cache(source_id: str) -> None:
    """Thread-safely evict all cached full-size and thumbnail entries for a deleted or recropped photo (`M-P0-03`)."""
    prefix = f"wp:{source_id}"
    with _IMAGE_CACHE_LOCK:
        for cache in (_ARTWORK_LRU_CACHE, _THUMB_LRU_CACHE):
            stale_keys = [
                k for k in cache if k[0] == prefix or k[0].startswith(f"{prefix}:")
            ]
            for k in stale_keys:
                cache.pop(k, None)
