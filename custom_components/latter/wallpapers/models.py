"""System Photo Library dataclasses, presets, focal-point crop math, and sky renderer (`L1b`)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from PIL import Image, ImageDraw, ImageOps

from ..const import (
    DAY_NIGHT_SKY_NATIVE_URL as DAY_NIGHT_SKY_NATIVE_URL,
    DAY_NIGHT_SKY_PRESET_ID as DAY_NIGHT_SKY_PRESET_ID,
)
from ..media_cache import validate_pil_image_dimensions

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

PHOTO_PREFIX: Final = "photo:"
PRIVATE_DIR_PARTS: Final[tuple[str, ...]] = (".storage", "latter", "wallpapers")
ORIGINALS_SUBDIR: Final = "originals"
INDEX_FILENAME: Final = "index.json"
IMAGE_SUFFIXES: Final[tuple[str, ...]] = (".jpg", ".jpeg", ".png", ".webp")
MAX_WALLPAPER_UPLOAD_BYTES: Final[int] = 15 * 1024 * 1024
MAX_ORIGINAL_LONG_EDGE: Final[int] = 1600
MAX_MEDIA_IMPORT_BATCH: Final[int] = 100
MAX_COLLECTIONS: Final[int] = 64
MAX_COLLECTION_NAME_LEN: Final[int] = 48
MAX_PHOTO_NAME_LEN: Final[int] = 64

VIRTUAL_COLLECTION_ALL: Final = "__all__"
VIRTUAL_COLLECTION_DEFAULTS: Final = "__defaults__"
VIRTUAL_COLLECTION_UPLOADS: Final = "__uploads__"
VIRTUAL_COLLECTION_UNCATEGORIZED: Final = "__uncategorized__"
VIRTUAL_COLLECTION_IDS: Final[frozenset[str]] = frozenset(
    {
        VIRTUAL_COLLECTION_ALL,
        VIRTUAL_COLLECTION_DEFAULTS,
        VIRTUAL_COLLECTION_UPLOADS,
        VIRTUAL_COLLECTION_UNCATEGORIZED,
    }
)

PHOTO_KEY_RE: Final = re.compile(r"^[a-z0-9_]{4,48}$")
COLLECTION_ID_RE: Final = re.compile(r"^col_[a-z0-9_]{4,32}$")

BUILTIN_WALLPAPERS_DIR: Final[Path] = Path(__file__).resolve().parent

BUILTIN_WALLPAPER_PRESETS: Final[tuple[dict[str, str], ...]] = (
    {
        "id": DAY_NIGHT_SKY_PRESET_ID,
        "name": "Day & Night Sky",
        "file": "",
        "kind": "dynamic_preset",
    },
    {
        "id": "preset:forest_mountains",
        "name": "Forest Mountains",
        "file": "forest_mountains.jpg",
        "kind": "preset",
    },
    {
        "id": "preset:wheat_field",
        "name": "Wheat Field",
        "file": "wheat_field.jpg",
        "kind": "preset",
    },
    {
        "id": "preset:ocean_waves",
        "name": "Ocean Waves",
        "file": "ocean_waves.jpg",
        "kind": "preset",
    },
    {
        "id": "preset:sahara_dunes",
        "name": "Sahara Dunes",
        "file": "sahara_dunes.jpg",
        "kind": "preset",
    },
    {
        "id": "preset:andromeda_galaxy",
        "name": "Andromeda Galaxy",
        "file": "andromeda_galaxy.jpg",
        "kind": "preset",
    },
    {
        "id": "preset:mars_crater",
        "name": "Mars Crater",
        "file": "mars_crater.jpg",
        "kind": "preset",
    },
)

PRESET_BY_ID: Final[dict[str, dict[str, str]]] = {p["id"]: p for p in BUILTIN_WALLPAPER_PRESETS}
_PRESET_FILE_BY_ID: Final[dict[str, str]] = {
    p["id"]: p["file"] for p in BUILTIN_WALLPAPER_PRESETS if p["file"]
}

_MIN_RENDER_DIM: Final[int] = 64
_MAX_RENDER_DIM: Final[int] = 1920
_MIN_CROP_DIM: Final[int] = 16
_MAX_CROP_ZOOM: Final[float] = 4.0
_MIN_STAR_RADIUS_DIM: Final[int] = 160
_STAR_COUNT: Final[int] = 64


@dataclass(frozen=True, slots=True)
class PhotoCrop:
    """Normalized focal-point crop metadata (`x`, `y` in 0..1; `zoom` in 1..3)."""

    x: float = 0.5
    y: float = 0.5
    zoom: float = 1.0

    def as_dict(self) -> dict[str, float]:
        """Serialize crop metadata to a plain dict."""
        return {"x": self.x, "y": self.y, "zoom": self.zoom}

    def crop_hash(self) -> str:
        """Return a short deterministic cache-bust digest for this crop."""
        raw = f"{self.x:.4f}|{self.y:.4f}|{self.zoom:.4f}"
        return hashlib.md5(raw.encode("utf-8"), usedforsecurity=False).hexdigest()[:8]


@dataclass(frozen=True, slots=True)
class PhotoCollectionRecord:
    """One user-created photo collection/album."""

    id: str
    name: str

    def as_dict(self) -> dict[str, str]:
        """Serialize collection metadata."""
        return {"id": self.id, "name": self.name}


@dataclass(frozen=True, slots=True)
class PhotoRecord:
    """Immutable metadata record for one custom photo in the System Photo Library."""

    id: str
    filename: str
    name: str
    width: int
    height: int
    crop: PhotoCrop
    collections: tuple[str, ...]
    content_sha256: str
    source_kind: str
    media_source_path: str
    added_at: str

    def to_index_dict(self) -> dict[str, Any]:
        """Serialize record for `index.json` storage."""
        return {
            "filename": self.filename,
            "name": self.name,
            "width": self.width,
            "height": self.height,
            "crop": self.crop.as_dict(),
            "collections": list(self.collections),
            "content_sha256": self.content_sha256,
            "source_kind": self.source_kind,
            "media_source_path": self.media_source_path,
            "added_at": self.added_at,
        }


@dataclass(frozen=True, slots=True)
class PhotoLibrarySnapshot:
    """Immutable snapshot of collections, custom photos, and preset collection tags."""

    collections: tuple[PhotoCollectionRecord, ...] = ()
    photos: MappingProxyType[str, PhotoRecord] = MappingProxyType({})
    photo_order: tuple[str, ...] = ()
    preset_collections: MappingProxyType[str, tuple[str, ...]] = MappingProxyType({})


def clean_display_name(raw: Any, fallback: str, max_len: int) -> str:
    """Return a clean single-line display name trimmed to `max_len`."""
    text = " ".join(str(raw or "").split()).strip()
    if not text:
        text = fallback
    return text[:max_len].strip() or fallback


def humanize_filename_stem(filename: str) -> str:
    """Derive a clean default display title from an image filename."""
    stem = Path(filename or "photo").stem
    cleaned = " ".join(re.sub(r"[_\-]+", " ", stem).split()).strip()
    return cleaned[:MAX_PHOTO_NAME_LEN] if cleaned else "Photo"


def is_dynamic_preset(source_id: str) -> bool:
    """Return True if `source_id` is a firmware-rendered dynamic wallpaper preset."""
    preset = PRESET_BY_ID.get(str(source_id or "").strip())
    return bool(preset and preset.get("kind") == "dynamic_preset")


def _clamp_crop_float(val: Any, default: float, lo: float, hi: float) -> float:
    if val is None or isinstance(val, bool):
        return default
    try:
        f = float(val)
    except (TypeError, ValueError):
        return default
    return round(max(lo, min(hi, f)), 4) if math.isfinite(f) else default


def normalize_crop(crop_x: Any = 0.5, crop_y: Any = 0.5, crop_zoom: Any = 1.0) -> PhotoCrop:
    """Clamp and round `(crop_x, crop_y, crop_zoom)` into valid non-destructive bounds."""
    return PhotoCrop(
        x=_clamp_crop_float(crop_x, 0.5, 0.0, 1.0),
        y=_clamp_crop_float(crop_y, 0.5, 0.0, 1.0),
        zoom=_clamp_crop_float(crop_zoom, 1.0, 1.0, 3.0),
    )


def private_root(config_dir: Path | str) -> Path:
    """Return Latter's private wallpaper root under the Home Assistant config directory."""
    return Path(config_dir).joinpath(*PRIVATE_DIR_PARTS)


def get_wallpaper_root(hass: HomeAssistant) -> Path:
    """Return Latter's private wallpaper root (`<config>/.storage/latter/wallpapers`)."""
    return private_root(hass.config.config_dir)


def make_photo_source(photo_key: str) -> str:
    """Return the canonical `photo:<key>` identifier for a library photo."""
    clean = str(photo_key or "").strip().lower()
    if not PHOTO_KEY_RE.match(clean):
        raise ValueError(f"Invalid photo key: {photo_key!r}")
    return f"{PHOTO_PREFIX}{clean}"


def parse_photo_source(source: str) -> str | None:
    """Return `<key>` for a valid `photo:<key>` reference, else None."""
    if not isinstance(source, str) or not source.startswith(PHOTO_PREFIX):
        return None
    key = source[len(PHOTO_PREFIX) :]
    return key if PHOTO_KEY_RE.match(key) else None


def resolve_photo_path(root: Path, source: str) -> Path | None:
    """Return the file inside `<root>/originals/` for a valid `photo:` reference, else None."""
    key = parse_photo_source(source)
    if key is None:
        return None
    originals_dir = (root / ORIGINALS_SUBDIR).resolve()
    candidate = (originals_dir / f"{key}.jpg").resolve()
    return candidate if candidate.is_relative_to(originals_dir) else None


def read_photo_bytes(root: Path, source: str) -> bytes | None:
    """Return the bytes of a library original photo, or None if invalid or missing (executor)."""
    path = resolve_photo_path(root, source)
    if path is None or not path.is_file():
        return None
    return path.read_bytes()


def compute_crop_box(  # noqa: PLR0913, PLR0917
    src_w: int,
    src_h: int,
    dst_w: int,
    dst_h: int,
    crop_x: float = 0.5,
    crop_y: float = 0.5,
    crop_zoom: float = 1.0,
) -> tuple[float, float, float, float]:
    """Compute focal-point cover crop `(left, top, right, bottom)` guaranteeing zero black bars."""
    if src_w <= 0 or src_h <= 0:
        raise ValueError("Source image has invalid dimensions")

    target_w = max(_MIN_CROP_DIM, min(_MAX_RENDER_DIM, int(dst_w)))
    target_h = max(_MIN_CROP_DIM, min(_MAX_RENDER_DIM, int(dst_h)))
    fx = max(0.0, min(1.0, float(crop_x)))
    fy = max(0.0, min(1.0, float(crop_y)))
    zoom = max(1.0, min(_MAX_CROP_ZOOM, float(crop_zoom)))

    src_aspect = float(src_w) / float(src_h)
    dst_aspect = float(target_w) / float(target_h)
    if src_aspect >= dst_aspect:
        base_h = float(src_h)
        base_w = base_h * dst_aspect
    else:
        base_w = float(src_w)
        base_h = base_w / dst_aspect

    win_w = max(1.0, min(float(src_w), base_w / zoom))
    win_h = max(1.0, min(float(src_h), base_h / zoom))
    cx = fx * float(src_w)
    cy = fy * float(src_h)
    left = max(0.0, min(float(src_w) - win_w, cx - (win_w * 0.5)))
    top = max(0.0, min(float(src_h) - win_h, cy - (win_h * 0.5)))
    right = min(float(src_w), left + win_w)
    bottom = min(float(src_h), top + win_h)
    return (left, top, right, bottom)


def crop_and_fit_image(  # noqa: PLR0913, PLR0917
    img: Image.Image,
    dst_w: int,
    dst_h: int,
    crop_x: float = 0.5,
    crop_y: float = 0.5,
    crop_zoom: float = 1.0,
) -> Image.Image:
    """Focal-point cover crop & Lanczos resize guaranteeing zero black bars on any aspect ratio."""
    rgb = img if img.mode == "RGB" else img.convert("RGB")
    src_w, src_h = rgb.size
    target_w = max(_MIN_CROP_DIM, min(_MAX_RENDER_DIM, int(dst_w)))
    target_h = max(_MIN_CROP_DIM, min(_MAX_RENDER_DIM, int(dst_h)))
    box = compute_crop_box(src_w, src_h, target_w, target_h, crop_x, crop_y, crop_zoom)
    return rgb.resize((target_w, target_h), resample=Image.Resampling.LANCZOS, box=box)


def _paint_sky_gradient(
    width: int, height: int, top_rgb: tuple[int, int, int], bot_rgb: tuple[int, int, int]
) -> Image.Image:
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    denom = max(1, height - 1)
    for y in range(height):
        t = y / denom
        col = (
            round(top_rgb[0] + (bot_rgb[0] - top_rgb[0]) * t),
            round(top_rgb[1] + (bot_rgb[1] - top_rgb[1]) * t),
            round(top_rgb[2] + (bot_rgb[2] - top_rgb[2]) * t),
        )
        draw.line([(0, y), (width - 1, y)], fill=col)
    return img


def _render_day_sky(width: int, height: int) -> Image.Image:
    base = _paint_sky_gradient(width, height, (34, 114, 214), (130, 194, 246)).convert("RGBA")
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    clouds = (
        (0.24, 0.30, 0.34, 0.08, 42),
        (0.56, 0.22, 0.42, 0.07, 36),
        (0.76, 0.44, 0.36, 0.09, 44),
        (0.32, 0.56, 0.44, 0.08, 34),
        (0.62, 0.66, 0.38, 0.07, 30),
    )
    for cx_f, cy_f, rx_f, ry_f, alpha in clouds:
        cx, cy = cx_f * width, cy_f * height
        rx, ry = max(8.0, rx_f * width), max(4.0, ry_f * height)
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(255, 255, 255, alpha))
        draw.ellipse(
            (cx - rx * 0.65, cy - ry * 1.15, cx + rx * 0.55, cy + ry * 0.75),
            fill=(255, 255, 255, min(255, alpha + 18)),
        )
    return Image.alpha_composite(base, overlay).convert("RGB")


def _render_night_sky(width: int, height: int) -> Image.Image:
    img = _paint_sky_gradient(width, height, (8, 16, 40), (22, 38, 76))
    draw = ImageDraw.Draw(img)
    for idx in range(_STAR_COUNT):
        hx = ((idx * 2654435761) ^ 0x5A17) & 0xFFFF
        hy = ((idx * 2246822519) ^ 0x9E37) & 0xFFFF
        sx = int((hx / 65535.0) * (width - 2)) + 1
        sy = int((hy / 65535.0) * (height * 0.85)) + 1
        bright = 180 + ((idx * 37) % 75)
        col = (bright, bright, min(255, bright + 12))
        if idx % 9 == 0 and min(width, height) >= _MIN_STAR_RADIUS_DIM:
            draw.ellipse((sx - 1, sy - 1, sx + 1, sy + 1), fill=col)
        else:
            draw.point((sx, sy), fill=col)
    return img


def render_day_night_sky_preview_image(
    width: int = 466,
    height: int = 466,
    *,
    mode: str = "split",
    is_night: bool = False,
) -> Image.Image:
    """Render a crisp split Day/Night preview or a live Day/Night sky image."""
    w = max(_MIN_RENDER_DIM, min(_MAX_RENDER_DIM, int(width)))
    h = max(_MIN_RENDER_DIM, min(_MAX_RENDER_DIM, int(height)))
    if mode == "live":
        return _render_night_sky(w, h) if is_night else _render_day_sky(w, h)

    day_img = _render_day_sky(w, h)
    night_img = _render_night_sky(w, h)
    mask = Image.new("L", (w, h), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.polygon([(int(w * 0.62), 0), (w, 0), (w, h), (int(w * 0.38), h)], fill=255)
    combined = Image.composite(night_img, day_img, mask)
    draw = ImageDraw.Draw(combined)
    draw.line(
        [(int(w * 0.62), 0), (int(w * 0.38), h)],
        fill=(220, 236, 255),
        width=max(1, min(w, h) // 160),
    )
    return combined


def render_builtin_preset_image(
    preset_id: str,
    width: int = 466,
    height: int = 466,
    *,
    mode: str = "wallpaper",
    is_night: bool = False,
) -> Image.Image:
    """Load a bundled default wallpaper or render Day & Night Sky to `(width, height)`."""
    w = max(_MIN_RENDER_DIM, min(_MAX_RENDER_DIM, int(width)))
    h = max(_MIN_RENDER_DIM, min(_MAX_RENDER_DIM, int(height)))
    if preset_id == DAY_NIGHT_SKY_PRESET_ID:
        return render_day_night_sky_preview_image(
            w, h, mode="live" if mode == "screensaver" else "split", is_night=is_night
        )
    fname = _PRESET_FILE_BY_ID.get(preset_id, "forest_mountains.jpg")
    img_path = BUILTIN_WALLPAPERS_DIR / fname
    with Image.open(img_path) as img:
        validate_pil_image_dimensions(img)
        rgb = img.convert("RGB")
        if rgb.size == (w, h):
            return rgb.copy()
        return ImageOps.fit(rgb, (w, h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
