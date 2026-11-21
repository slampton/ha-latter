"""Shared System Photo Library, Collections, Non-Destructive Crop, HA /media Import, & Pool Resolver."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import io
import json
import logging
import math
import os
from pathlib import Path
import re
import secrets
import threading
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from PIL import Image, ImageDraw, ImageOps

from .const import normalize_device_slug

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

PHOTO_PREFIX = "photo:"
PRIVATE_DIR_PARTS: tuple[str, ...] = (".storage", "latter", "wallpapers")
ORIGINALS_SUBDIR = "originals"
INDEX_FILENAME = "index.json"
IMAGE_SUFFIXES: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp")
MAX_WALLPAPER_UPLOAD_BYTES: int = 15 * 1024 * 1024  # 15 MB hard upload cap
MAX_ORIGINAL_LONG_EDGE: int = 1600
MAX_MEDIA_IMPORT_BATCH: int = 100
MAX_COLLECTIONS: int = 64
MAX_COLLECTION_NAME_LEN: int = 48
MAX_PHOTO_NAME_LEN: int = 64

DAY_NIGHT_SKY_PRESET_ID = "preset:day_night_sky"
DAY_NIGHT_SKY_NATIVE_URL = "latter://day_night_sky"

VIRTUAL_COLLECTION_ALL = "__all__"
VIRTUAL_COLLECTION_DEFAULTS = "__defaults__"
VIRTUAL_COLLECTION_UPLOADS = "__uploads__"
VIRTUAL_COLLECTION_UNCATEGORIZED = "__uncategorized__"
VIRTUAL_COLLECTION_IDS: frozenset[str] = frozenset(
    {
        VIRTUAL_COLLECTION_ALL,
        VIRTUAL_COLLECTION_DEFAULTS,
        VIRTUAL_COLLECTION_UPLOADS,
        VIRTUAL_COLLECTION_UNCATEGORIZED,
    }
)

_PHOTO_KEY_RE = re.compile(r"^[a-z0-9_]{4,48}$")
_COLLECTION_ID_RE = re.compile(r"^col_[a-z0-9_]{4,32}$")

BUILTIN_WALLPAPERS_DIR: Path = Path(__file__).resolve().parent / "wallpapers"

BUILTIN_WALLPAPER_PRESETS: tuple[dict[str, str], ...] = (
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

_PRESET_BY_ID: dict[str, dict[str, str]] = {
    p["id"]: p for p in BUILTIN_WALLPAPER_PRESETS
}
_PRESET_FILE_BY_ID: dict[str, str] = {
    p["id"]: p["file"] for p in BUILTIN_WALLPAPER_PRESETS if p["file"]
}


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
        return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]


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


_LIBRARY_LOCK = threading.RLock()
_PHOTO_LIBRARY_SNAPSHOT: PhotoLibrarySnapshot = PhotoLibrarySnapshot()


def is_dynamic_preset(source_id: str) -> bool:
    """Return True if `source_id` is a firmware-rendered dynamic wallpaper preset."""
    preset = _PRESET_BY_ID.get(str(source_id or "").strip())
    return bool(preset and preset.get("kind") == "dynamic_preset")


def normalize_crop(
    crop_x: Any = 0.5, crop_y: Any = 0.5, crop_zoom: Any = 1.0
) -> PhotoCrop:
    """Clamp and round `(crop_x, crop_y, crop_zoom)` into valid non-destructive bounds."""

    def _flt(val: Any, default: float, lo: float, hi: float) -> float:
        if val is None or isinstance(val, bool):
            return default
        try:
            f = float(val)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(f):
            return default
        return round(max(lo, min(hi, f)), 4)

    return PhotoCrop(
        x=_flt(crop_x, 0.5, 0.0, 1.0),
        y=_flt(crop_y, 0.5, 0.0, 1.0),
        zoom=_flt(crop_zoom, 1.0, 1.0, 3.0),
    )


def _clean_display_name(raw: Any, fallback: str, max_len: int) -> str:
    """Return a clean single-line display name trimmed to `max_len`."""
    text = " ".join(str(raw or "").split()).strip()
    if not text:
        text = fallback
    return text[:max_len].strip() or fallback


def _humanize_filename_stem(filename: str) -> str:
    stem = Path(filename or "photo").stem
    cleaned = re.sub(r"[_\-]+", " ", stem).strip()
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return "Photo"
    return cleaned[:MAX_PHOTO_NAME_LEN]


def private_root(config_dir: Path | str) -> Path:
    """Return Latter's private wallpaper root under the Home Assistant config directory."""
    return Path(config_dir).joinpath(*PRIVATE_DIR_PARTS)


def get_wallpaper_root(hass: HomeAssistant) -> Path:
    """Return Latter's private wallpaper root (`<config>/.storage/latter/wallpapers`, never served by HA)."""
    return private_root(hass.config.config_dir)


def make_photo_source(photo_key: str) -> str:
    """Return the canonical `photo:<key>` identifier for a library photo."""
    clean = str(photo_key or "").strip().lower()
    if not _PHOTO_KEY_RE.match(clean):
        raise ValueError(f"Invalid photo key: {photo_key!r}")
    return f"{PHOTO_PREFIX}{clean}"


def parse_photo_source(source: str) -> str | None:
    """Return `<key>` for a valid `photo:<key>` reference, else None."""
    if not isinstance(source, str) or not source.startswith(PHOTO_PREFIX):
        return None
    key = source[len(PHOTO_PREFIX) :]
    if not _PHOTO_KEY_RE.match(key):
        return None
    return key


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


def compute_crop_box(
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

    target_w = max(16, min(1920, int(dst_w)))
    target_h = max(16, min(1920, int(dst_h)))
    fx = max(0.0, min(1.0, float(crop_x)))
    fy = max(0.0, min(1.0, float(crop_y)))
    zoom = max(1.0, min(4.0, float(crop_zoom)))

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


def crop_and_fit_image(
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
    target_w = max(16, min(1920, int(dst_w)))
    target_h = max(16, min(1920, int(dst_h)))
    box = compute_crop_box(src_w, src_h, target_w, target_h, crop_x, crop_y, crop_zoom)
    return rgb.resize(
        (target_w, target_h),
        resample=Image.Resampling.LANCZOS,
        box=box,
    )


def _paint_sky_gradient(
    width: int,
    height: int,
    top_rgb: tuple[int, int, int],
    bot_rgb: tuple[int, int, int],
) -> Image.Image:
    """Generate a smooth vertical sky gradient RGB image."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    denom = max(1, height - 1)
    for y in range(height):
        t = y / denom
        r = round(top_rgb[0] + (bot_rgb[0] - top_rgb[0]) * t)
        g = round(top_rgb[1] + (bot_rgb[1] - top_rgb[1]) * t)
        b = round(top_rgb[2] + (bot_rgb[2] - top_rgb[2]) * t)
        draw.line([(0, y), (width - 1, y)], fill=(r, g, b))
    return img


def _render_day_sky(width: int, height: int) -> Image.Image:
    """Render calm daytime blue sky with soft translucent wispy clouds (zero sun/storm)."""
    base = _paint_sky_gradient(width, height, (34, 114, 214), (130, 194, 246)).convert(
        "RGBA"
    )
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
        draw.ellipse(
            (cx - rx, cy - ry, cx + rx, cy + ry),
            fill=(255, 255, 255, alpha),
        )
        draw.ellipse(
            (cx - rx * 0.65, cy - ry * 1.15, cx + rx * 0.55, cy + ry * 0.75),
            fill=(255, 255, 255, min(255, alpha + 18)),
        )
    return Image.alpha_composite(base, overlay).convert("RGB")


def _render_night_sky(width: int, height: int) -> Image.Image:
    """Render deep starry night sky dome (zero moon/storm)."""
    img = _paint_sky_gradient(width, height, (8, 16, 40), (22, 38, 76))
    draw = ImageDraw.Draw(img)
    star_count = 64
    for idx in range(star_count):
        # Deterministic LCG scatter matching calm night-sky aesthetics
        hx = ((idx * 2654435761) ^ 0x5A17) & 0xFFFF
        hy = ((idx * 2246822519) ^ 0x9E37) & 0xFFFF
        sx = int((hx / 65535.0) * (width - 2)) + 1
        sy = int((hy / 65535.0) * (height * 0.85)) + 1
        bright = 180 + ((idx * 37) % 75)
        col = (bright, bright, min(255, bright + 12))
        if idx % 9 == 0 and min(width, height) >= 160:
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
    w = max(64, min(1920, int(width)))
    h = max(64, min(1920, int(height)))
    if mode == "live":
        return _render_night_sky(w, h) if is_night else _render_day_sky(w, h)

    day_img = _render_day_sky(w, h)
    night_img = _render_night_sky(w, h)
    mask = Image.new("L", (w, h), 0)
    mdraw = ImageDraw.Draw(mask)
    # Clean diagonal split (day top-left, night bottom-right)
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
    w = max(64, min(1920, int(width)))
    h = max(64, min(1920, int(height)))
    if preset_id == DAY_NIGHT_SKY_PRESET_ID:
        return render_day_night_sky_preview_image(
            w,
            h,
            mode="live" if mode == "screensaver" else "split",
            is_night=is_night,
        )
    fname = _PRESET_FILE_BY_ID.get(preset_id, "forest_mountains.jpg")
    img_path = BUILTIN_WALLPAPERS_DIR / fname
    with Image.open(img_path) as img:
        rgb = img.convert("RGB")
        if rgb.size == (w, h):
            return rgb.copy()
        return ImageOps.fit(
            rgb,
            (w, h),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )


def _index_path(root: Path) -> Path:
    return root / INDEX_FILENAME


def _originals_dir(root: Path) -> Path:
    return root / ORIGINALS_SUBDIR


def _write_index_atomic(root: Path, snapshot: PhotoLibrarySnapshot) -> None:
    """Atomically persist `index.json` inside `root`."""
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "collections": [c.as_dict() for c in snapshot.collections],
        "photos": {
            pid: snapshot.photos[pid].to_index_dict()
            for pid in snapshot.photo_order
            if pid in snapshot.photos
        },
        "preset_collections": {
            pid: list(cols)
            for pid, cols in snapshot.preset_collections.items()
            if cols
        },
    }
    raw = json.dumps(payload, indent=2, sort_keys=False)
    tmp_path = root / f".{INDEX_FILENAME}.{secrets.token_hex(4)}.tmp"
    tmp_path.write_text(raw, encoding="utf-8")
    os.replace(tmp_path, _index_path(root))


def _build_snapshot_from_raw(
    root: Path, raw_index: Mapping[str, Any]
) -> tuple[PhotoLibrarySnapshot, bool]:
    """Build an immutable `PhotoLibrarySnapshot` from parsed index data reconciled with `originals/`."""
    orig_dir = _originals_dir(root)
    changed = False

    collections: list[PhotoCollectionRecord] = []
    valid_col_ids: set[str] = set()
    raw_cols = raw_index.get("collections")
    if isinstance(raw_cols, list):
        for item in raw_cols:
            if not isinstance(item, Mapping):
                continue
            cid = str(item.get("id") or "").strip()
            cname = _clean_display_name(item.get("name"), "", MAX_COLLECTION_NAME_LEN)
            if not cid or not _COLLECTION_ID_RE.match(cid) or not cname or cid in valid_col_ids:
                changed = True
                continue
            valid_col_ids.add(cid)
            collections.append(PhotoCollectionRecord(id=cid, name=cname))
            if len(collections) >= MAX_COLLECTIONS:
                break

    existing_files: dict[str, Path] = {}
    if orig_dir.is_dir():
        for file_path in sorted(orig_dir.iterdir(), key=lambda p: p.name.lower()):
            if not file_path.is_file() or file_path.suffix.lower() != ".jpg":
                continue
            key = file_path.stem.lower()
            if _PHOTO_KEY_RE.match(key):
                existing_files[f"{PHOTO_PREFIX}{key}"] = file_path

    photos: dict[str, PhotoRecord] = {}
    photo_order: list[str] = []
    raw_photos = raw_index.get("photos")
    if isinstance(raw_photos, Mapping):
        for pid_raw, meta in raw_photos.items():
            pid = str(pid_raw or "").strip().lower()
            if pid not in existing_files or not isinstance(meta, Mapping):
                changed = True
                continue
            parsed_key = parse_photo_source(pid)
            if parsed_key is None:
                changed = True
                continue
            key = parsed_key
            raw_crop = meta.get("crop")
            crop = (
                normalize_crop(
                    raw_crop.get("x", 0.5),
                    raw_crop.get("y", 0.5),
                    raw_crop.get("zoom", 1.0),
                )
                if isinstance(raw_crop, Mapping)
                else PhotoCrop()
            )
            raw_tags = meta.get("collections")
            tags = tuple(
                dict.fromkeys(
                    str(cid).strip()
                    for cid in (raw_tags if isinstance(raw_tags, list) else [])
                    if str(cid).strip() in valid_col_ids
                )
            )
            try:
                w = max(1, int(meta.get("width") or 0))
                h = max(1, int(meta.get("height") or 0))
            except (TypeError, ValueError):
                w, h = 0, 0
            if w <= 0 or h <= 0:
                try:
                    with Image.open(existing_files[pid]) as im:
                        w, h = im.size
                except Exception:  # noqa: BLE001
                    w, h = 960, 960
                changed = True
            source_kind = str(meta.get("source_kind") or "upload").strip().lower()
            if source_kind not in ("upload", "media_import"):
                source_kind = "upload"
            rec = PhotoRecord(
                id=pid,
                filename=f"{key}.jpg",
                name=_clean_display_name(
                    meta.get("name"),
                    _humanize_filename_stem(f"{key}.jpg"),
                    MAX_PHOTO_NAME_LEN,
                ),
                width=w,
                height=h,
                crop=crop,
                collections=tags,
                content_sha256=str(meta.get("content_sha256") or "").strip().lower(),
                source_kind=source_kind,
                media_source_path=str(meta.get("media_source_path") or "").strip(),
                added_at=str(meta.get("added_at") or "").strip(),
            )
            photos[pid] = rec
            photo_order.append(pid)

    # Adopt any valid JPEG in originals/ missing from index.json
    for pid, file_path in existing_files.items():
        if pid in photos:
            continue
        changed = True
        try:
            raw_b = file_path.read_bytes()
            sha = hashlib.sha256(raw_b).hexdigest()
            with Image.open(io.BytesIO(raw_b)) as im:
                w, h = im.size
        except Exception:  # noqa: BLE001
            continue
        photos[pid] = PhotoRecord(
            id=pid,
            filename=file_path.name,
            name=_humanize_filename_stem(file_path.name),
            width=w,
            height=h,
            crop=PhotoCrop(),
            collections=(),
            content_sha256=sha,
            source_kind="upload",
            media_source_path="",
            added_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        photo_order.append(pid)

    preset_cols: dict[str, tuple[str, ...]] = {}
    raw_pcols = raw_index.get("preset_collections")
    if isinstance(raw_pcols, Mapping):
        for pid_raw, col_list in raw_pcols.items():
            pid = str(pid_raw or "").strip()
            if pid not in _PRESET_BY_ID or not isinstance(col_list, list):
                changed = True
                continue
            cleaned = tuple(
                dict.fromkeys(
                    str(c).strip() for c in col_list if str(c).strip() in valid_col_ids
                )
            )
            if cleaned:
                preset_cols[pid] = cleaned

    snap = PhotoLibrarySnapshot(
        collections=tuple(collections),
        photos=MappingProxyType(photos),
        photo_order=tuple(photo_order),
        preset_collections=MappingProxyType(preset_cols),
    )
    return snap, changed


def _load_photo_library_sync(root: Path) -> PhotoLibrarySnapshot:
    """Load `index.json` + `originals/` in a worker thread and swap `_PHOTO_LIBRARY_SNAPSHOT`."""
    global _PHOTO_LIBRARY_SNAPSHOT
    with _LIBRARY_LOCK:
        idx_file = _index_path(root)
        raw_index: dict[str, Any] = {}
        if idx_file.is_file():
            try:
                parsed = json.loads(idx_file.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    raw_index = parsed
            except (OSError, ValueError) as err:
                _LOGGER.warning("Failed reading wallpaper index %s: %s", idx_file, err)
        snap, changed = _build_snapshot_from_raw(root, raw_index)
        if changed and (root.is_dir() or snap.photos or snap.collections):
            try:
                _write_index_atomic(root, snap)
            except OSError as err:
                _LOGGER.debug("Skipping index write during scan: %s", err)
        _PHOTO_LIBRARY_SNAPSHOT = snap
        return snap


def get_photo_library_snapshot() -> PhotoLibrarySnapshot:
    """Return the current immutable `PhotoLibrarySnapshot`."""
    return _PHOTO_LIBRARY_SNAPSHOT


def wallpaper_snapshot_token() -> int:
    """Return an O(1) identity token for the current immutable photo library snapshot."""
    return id(_PHOTO_LIBRARY_SNAPSHOT)


async def async_refresh_wallpaper_cache(hass: HomeAssistant) -> PhotoLibrarySnapshot:
    """Populate the immutable Photo Library snapshot via awaited executor load."""
    snap: PhotoLibrarySnapshot = await hass.async_add_executor_job(
        _load_photo_library_sync, get_wallpaper_root(hass)
    )
    return snap


def get_photo_crop(source_id: str) -> PhotoCrop:
    """Return the stored `PhotoCrop` for `source_id`, or default centered `PhotoCrop()`."""
    rec = _PHOTO_LIBRARY_SNAPSHOT.photos.get(str(source_id or "").strip())
    return rec.crop if rec is not None else PhotoCrop()


def get_photo_crop_hash(source_id: str) -> str:
    """Return a short cache-bust hash reflecting the photo's current non-destructive crop."""
    return get_photo_crop(source_id).crop_hash()


def ordered_wallpaper_ids(*, include_dynamic: bool = True) -> list[str]:
    """Return all library photo IDs in deterministic display order (defaults, then custom photos)."""
    snap = _PHOTO_LIBRARY_SNAPSHOT
    preset_ids = [
        p["id"]
        for p in BUILTIN_WALLPAPER_PRESETS
        if include_dynamic or p["kind"] != "dynamic_preset"
    ]
    return preset_ids + list(snap.photo_order)


def known_wallpaper_ids(*, include_dynamic: bool = True) -> set[str]:
    """Return the set of valid photo IDs (defaults + custom photos)."""
    return set(ordered_wallpaper_ids(include_dynamic=include_dynamic))


def known_collection_ids(snapshot: PhotoLibrarySnapshot | None = None) -> set[str]:
    """Return valid user collection IDs (`col_*`)."""
    snap = snapshot if snapshot is not None else _PHOTO_LIBRARY_SNAPSHOT
    return {c.id for c in snap.collections}


def list_photo_collections(
    snapshot: PhotoLibrarySnapshot | None = None,
) -> list[dict[str, Any]]:
    """Return all user photo collections with live item counts."""
    snap = snapshot if snapshot is not None else _PHOTO_LIBRARY_SNAPSHOT
    counts: dict[str, int] = {c.id: 0 for c in snap.collections}
    for rec in snap.photos.values():
        for cid in rec.collections:
            if cid in counts:
                counts[cid] += 1
    for cols in snap.preset_collections.values():
        for cid in cols:
            if cid in counts:
                counts[cid] += 1
    return [
        {"id": c.id, "name": c.name, "count": counts.get(c.id, 0)}
        for c in snap.collections
    ]


def _serialize_photo_item(
    rec: PhotoRecord,
    *,
    active: bool,
    favorite: bool,
    thumb_url: str,
    orig_url: str,
) -> dict[str, Any]:
    return {
        "id": rec.id,
        "name": rec.name,
        "filename": rec.filename,
        "kind": "uploaded",
        "active": active,
        "favorite": favorite,
        "deletable": True,
        "thumb_url": thumb_url,
        "orig_url": orig_url,
        "width": rec.width,
        "height": rec.height,
        "crop": rec.crop.as_dict(),
        "collections": list(rec.collections),
        "source_kind": rec.source_kind,
        "media_source_path": rec.media_source_path,
        "added_at": rec.added_at,
    }


def list_wallpaper_catalog(
    hass: HomeAssistant,
    device_slug: str,
    active_source: str,
    favorites: Sequence[str],
    *,
    sign_resource: Callable[[str], str] | None = None,
    display_shape: str = "circle",
) -> list[dict[str, Any]]:
    """Return built-in default presets + shared custom photos with signed Studio URLs & metadata."""
    _ = hass
    snap = _PHOTO_LIBRARY_SNAPSHOT
    fav_set = set(favorites or ())
    items: list[dict[str, Any]] = []
    slug = normalize_device_slug(device_slug or "system")
    wp_shape = "square" if display_shape == "square" else "circle"

    def _build_thumb_url(src_id: str, *, mode: str, crop_tag: str = "") -> str:
        if sign_resource is None:
            return ""
        sig = sign_resource(f"wallpaper:{src_id}|240|240|{wp_shape}|{mode}")
        v_q = f"&v={crop_tag}" if crop_tag else ""
        return (
            f"/api/latter/wallpaper/{slug}"
            f"?w=240&h=240&shape={wp_shape}&mode={mode}"
            f"&src={quote(src_id, safe='')}&sig={sig}{v_q}"
        )

    def _build_orig_url(src_id: str) -> str:
        if sign_resource is None:
            return ""
        sig = sign_resource(f"wallpaper:{src_id}|1200|1200|square|original")
        return (
            f"/api/latter/wallpaper/{slug}"
            f"?w=1200&h=1200&shape=square&mode=original"
            f"&src={quote(src_id, safe='')}&sig={sig}"
        )

    for preset in BUILTIN_WALLPAPER_PRESETS:
        pid = preset["id"]
        is_dyn = preset["kind"] == "dynamic_preset"
        thumb_mode = "wallpaper" if is_dyn else "screensaver"
        items.append(
            {
                "id": pid,
                "name": preset["name"],
                "kind": preset["kind"],
                "active": pid == active_source,
                "favorite": pid in fav_set,
                "deletable": False,
                "thumb_url": _build_thumb_url(pid, mode=thumb_mode),
                "orig_url": "",
                "width": 720,
                "height": 720,
                "crop": PhotoCrop().as_dict(),
                "collections": list(snap.preset_collections.get(pid, ())),
                "source_kind": preset["kind"],
                "media_source_path": "",
                "added_at": "",
            }
        )

    for pid in snap.photo_order:
        rec = snap.photos.get(pid)
        if rec is None:
            continue
        items.append(
            _serialize_photo_item(
                rec,
                active=(pid == active_source),
                favorite=(pid in fav_set),
                thumb_url=_build_thumb_url(
                    pid, mode="screensaver", crop_tag=rec.crop.crop_hash()
                ),
                orig_url=_build_orig_url(pid),
            )
        )

    return items


def resolve_photo_pool(
    mode: str,
    single_source: str,
    collection_id: str,
    custom_ids: Sequence[str],
    *,
    include_dynamic: bool,
    snapshot: PhotoLibrarySnapshot | None = None,
) -> list[str]:
    """Pure pool resolver for Wallpaper and Screensaver Photo Frame pools."""
    snap = snapshot if snapshot is not None else _PHOTO_LIBRARY_SNAPSHOT
    clean_mode = str(mode or "off").strip().lower()
    if clean_mode == "off":
        return []

    def _allowed_preset(pid: str) -> bool:
        preset = _PRESET_BY_ID.get(pid)
        if preset is None:
            return False
        return include_dynamic or preset["kind"] != "dynamic_preset"

    if clean_mode == "single":
        sid = str(single_source or "").strip()
        if not sid:
            return []
        if sid in snap.photos or _allowed_preset(sid):
            return [sid]
        return []

    if clean_mode == "collection":
        col = str(collection_id or "").strip()
        if not col:
            return []
        preset_ids = [
            p["id"]
            for p in BUILTIN_WALLPAPER_PRESETS
            if include_dynamic or p["kind"] != "dynamic_preset"
        ]
        if col == VIRTUAL_COLLECTION_ALL:
            return preset_ids + list(snap.photo_order)
        if col == VIRTUAL_COLLECTION_DEFAULTS:
            return preset_ids
        if col == VIRTUAL_COLLECTION_UPLOADS:
            return list(snap.photo_order)
        if col == VIRTUAL_COLLECTION_UNCATEGORIZED:
            return [
                pid
                for pid in snap.photo_order
                if (rec := snap.photos.get(pid)) is not None and not rec.collections
            ]
        if col in {c.id for c in snap.collections}:
            matched_presets = [
                pid
                for pid in preset_ids
                if col in snap.preset_collections.get(pid, ())
            ]
            matched_photos = [
                pid
                for pid in snap.photo_order
                if (rec := snap.photos.get(pid)) is not None and col in rec.collections
            ]
            return matched_presets + matched_photos
        return []

    if clean_mode == "custom":
        out: list[str] = []
        seen: set[str] = set()
        for raw_id in custom_ids or ():
            pid = str(raw_id or "").strip()
            if not pid or pid in seen:
                continue
            if pid in snap.photos or _allowed_preset(pid):
                seen.add(pid)
                out.append(pid)
        return out

    return []


# ---------------------------------------------------------------------------
# Photo & Collection CRUD (Executor Thread Mutations)
# ---------------------------------------------------------------------------


def _ensure_loaded_locked(root: Path) -> PhotoLibrarySnapshot:
    """Load index from disk when the in-memory snapshot doesn't match `root` yet."""
    return _PHOTO_LIBRARY_SNAPSHOT


def _encode_original_jpeg(raw_bytes: bytes) -> tuple[bytes, int, int]:
    """Decode, EXIF-transpose, downscale to <= 1600 px long edge preserving aspect ratio, and encode Baseline JPEG."""
    with Image.open(io.BytesIO(raw_bytes)) as img:
        transposed = ImageOps.exif_transpose(img)
        rgb = transposed.convert("RGB")
        w, h = rgb.size
        if w <= 0 or h <= 0:
            raise ValueError("Invalid image dimensions")
        long_edge = max(w, h)
        if long_edge > MAX_ORIGINAL_LONG_EDGE:
            scale = float(MAX_ORIGINAL_LONG_EDGE) / float(long_edge)
            new_w = max(1, round(w * scale))
            new_h = max(1, round(h * scale))
            rgb = rgb.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)
            w, h = rgb.size
        out = io.BytesIO()
        rgb.save(out, format="JPEG", quality=92, optimize=True, progressive=False)
        return out.getvalue(), w, h


def create_collection(hass: HomeAssistant, name: str) -> dict[str, Any]:
    """Create a new photo collection and persist `index.json` atomically."""
    global _PHOTO_LIBRARY_SNAPSHOT
    clean_name = _clean_display_name(name, "", MAX_COLLECTION_NAME_LEN)
    if not clean_name:
        raise ValueError("Collection name is required")
    root = get_wallpaper_root(hass)
    with _LIBRARY_LOCK:
        snap = _PHOTO_LIBRARY_SNAPSHOT
        if len(snap.collections) >= MAX_COLLECTIONS:
            raise ValueError(f"At most {MAX_COLLECTIONS} collections are supported")
        low_name = clean_name.lower()
        if any(c.name.lower() == low_name for c in snap.collections):
            raise ValueError(f"A collection named '{clean_name}' already exists")
        existing_ids = {c.id for c in snap.collections}
        col_id = f"col_{secrets.token_hex(4)}"
        while col_id in existing_ids:
            col_id = f"col_{secrets.token_hex(4)}"
        rec = PhotoCollectionRecord(id=col_id, name=clean_name)
        new_snap = PhotoLibrarySnapshot(
            collections=(*snap.collections, rec),
            photos=snap.photos,
            photo_order=snap.photo_order,
            preset_collections=snap.preset_collections,
        )
        _write_index_atomic(root, new_snap)
        _PHOTO_LIBRARY_SNAPSHOT = new_snap
        return {"id": rec.id, "name": rec.name, "count": 0}


def rename_collection(
    hass: HomeAssistant, collection_id: str, name: str
) -> dict[str, Any]:
    """Rename an existing photo collection and persist `index.json` atomically."""
    global _PHOTO_LIBRARY_SNAPSHOT
    cid = str(collection_id or "").strip()
    clean_name = _clean_display_name(name, "", MAX_COLLECTION_NAME_LEN)
    if not clean_name:
        raise ValueError("Collection name is required")
    root = get_wallpaper_root(hass)
    with _LIBRARY_LOCK:
        snap = _PHOTO_LIBRARY_SNAPSHOT
        if not any(c.id == cid for c in snap.collections):
            raise ValueError(f"Unknown collection '{cid}'")
        low_name = clean_name.lower()
        if any(c.id != cid and c.name.lower() == low_name for c in snap.collections):
            raise ValueError(f"A collection named '{clean_name}' already exists")
        new_cols = tuple(
            PhotoCollectionRecord(id=c.id, name=clean_name) if c.id == cid else c
            for c in snap.collections
        )
        new_snap = PhotoLibrarySnapshot(
            collections=new_cols,
            photos=snap.photos,
            photo_order=snap.photo_order,
            preset_collections=snap.preset_collections,
        )
        _write_index_atomic(root, new_snap)
        _PHOTO_LIBRARY_SNAPSHOT = new_snap
        counts = {c["id"]: c["count"] for c in list_photo_collections(new_snap)}
        return {"id": cid, "name": clean_name, "count": counts.get(cid, 0)}


def delete_collection(hass: HomeAssistant, collection_id: str) -> bool:
    """Delete a collection and remove its tag from every photo and preset."""
    global _PHOTO_LIBRARY_SNAPSHOT
    cid = str(collection_id or "").strip()
    root = get_wallpaper_root(hass)
    with _LIBRARY_LOCK:
        snap = _PHOTO_LIBRARY_SNAPSHOT
        if not any(c.id == cid for c in snap.collections):
            return False
        new_cols = tuple(c for c in snap.collections if c.id != cid)
        new_photos: dict[str, PhotoRecord] = {}
        for pid, rec in snap.photos.items():
            if cid in rec.collections:
                new_photos[pid] = PhotoRecord(
                    id=rec.id,
                    filename=rec.filename,
                    name=rec.name,
                    width=rec.width,
                    height=rec.height,
                    crop=rec.crop,
                    collections=tuple(x for x in rec.collections if x != cid),
                    content_sha256=rec.content_sha256,
                    source_kind=rec.source_kind,
                    media_source_path=rec.media_source_path,
                    added_at=rec.added_at,
                )
            else:
                new_photos[pid] = rec
        new_pcols: dict[str, tuple[str, ...]] = {}
        for pid, cols in snap.preset_collections.items():
            filtered = tuple(x for x in cols if x != cid)
            if filtered:
                new_pcols[pid] = filtered
        new_snap = PhotoLibrarySnapshot(
            collections=new_cols,
            photos=MappingProxyType(new_photos),
            photo_order=snap.photo_order,
            preset_collections=MappingProxyType(new_pcols),
        )
        _write_index_atomic(root, new_snap)
        _PHOTO_LIBRARY_SNAPSHOT = new_snap
        return True


def update_photo_metadata(
    hass: HomeAssistant,
    photo_id: str,
    *,
    name: str | None = None,
    crop: Mapping[str, Any] | None = None,
    collections: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Update a photo's name, non-destructive crop, or collections (presets support collections only)."""
    global _PHOTO_LIBRARY_SNAPSHOT
    pid = str(photo_id or "").strip()
    root = get_wallpaper_root(hass)
    crop_changed = False
    with _LIBRARY_LOCK:
        snap = _PHOTO_LIBRARY_SNAPSHOT
        valid_col_ids = {c.id for c in snap.collections}
        cleaned_cols: tuple[str, ...] | None = None
        if collections is not None:
            col_list: list[str] = []
            for raw_c in collections:
                c_tok = str(raw_c or "").strip()
                if not c_tok:
                    continue
                if c_tok not in valid_col_ids:
                    raise ValueError(f"Unknown collection '{c_tok}'")
                if c_tok not in col_list:
                    col_list.append(c_tok)
            cleaned_cols = tuple(col_list)

        if pid in _PRESET_BY_ID:
            if name is not None or crop is not None:
                raise ValueError("Built-in presets cannot be renamed or cropped")
            new_pcols = dict(snap.preset_collections)
            if cleaned_cols is not None:
                if cleaned_cols:
                    new_pcols[pid] = cleaned_cols
                else:
                    new_pcols.pop(pid, None)
            new_snap = PhotoLibrarySnapshot(
                collections=snap.collections,
                photos=snap.photos,
                photo_order=snap.photo_order,
                preset_collections=MappingProxyType(new_pcols),
            )
            _write_index_atomic(root, new_snap)
            _PHOTO_LIBRARY_SNAPSHOT = new_snap
            preset = _PRESET_BY_ID[pid]
            return {
                "id": pid,
                "name": preset["name"],
                "kind": preset["kind"],
                "collections": list(new_pcols.get(pid, ())),
                "crop": PhotoCrop().as_dict(),
                "crop_changed": False,
            }

        rec = snap.photos.get(pid)
        if rec is None:
            raise ValueError(f"Unknown photo '{pid}'")

        new_name = (
            _clean_display_name(name, "", MAX_PHOTO_NAME_LEN)
            if name is not None
            else rec.name
        )
        if not new_name:
            raise ValueError("Photo name cannot be empty")
        new_crop = (
            normalize_crop(
                crop.get("x", rec.crop.x),
                crop.get("y", rec.crop.y),
                crop.get("zoom", rec.crop.zoom),
            )
            if crop is not None
            else rec.crop
        )
        crop_changed = new_crop != rec.crop
        new_tags = cleaned_cols if cleaned_cols is not None else rec.collections
        updated_rec = PhotoRecord(
            id=rec.id,
            filename=rec.filename,
            name=new_name,
            width=rec.width,
            height=rec.height,
            crop=new_crop,
            collections=new_tags,
            content_sha256=rec.content_sha256,
            source_kind=rec.source_kind,
            media_source_path=rec.media_source_path,
            added_at=rec.added_at,
        )
        new_photos = dict(snap.photos)
        new_photos[pid] = updated_rec
        new_snap = PhotoLibrarySnapshot(
            collections=snap.collections,
            photos=MappingProxyType(new_photos),
            photo_order=snap.photo_order,
            preset_collections=snap.preset_collections,
        )
        _write_index_atomic(root, new_snap)
        _PHOTO_LIBRARY_SNAPSHOT = new_snap

    if crop_changed:
        from .http import evict_wallpaper_lru_cache

        evict_wallpaper_lru_cache(pid)

    return {
        "id": updated_rec.id,
        "name": updated_rec.name,
        "filename": updated_rec.filename,
        "kind": "uploaded",
        "width": updated_rec.width,
        "height": updated_rec.height,
        "crop": updated_rec.crop.as_dict(),
        "collections": list(updated_rec.collections),
        "source_kind": updated_rec.source_kind,
        "media_source_path": updated_rec.media_source_path,
        "added_at": updated_rec.added_at,
        "crop_changed": crop_changed,
    }


def bulk_update_photos(
    hass: HomeAssistant,
    photo_ids: Sequence[str],
    *,
    add_collection: str | None = None,
    remove_collection: str | None = None,
    delete: bool = False,
) -> dict[str, Any]:
    """Batch-assign/remove a collection or batch-delete custom photos in one atomic index write."""
    global _PHOTO_LIBRARY_SNAPSHOT
    root = get_wallpaper_root(hass)
    target_ids = list(
        dict.fromkeys(str(p or "").strip() for p in (photo_ids or ()) if str(p or "").strip())
    )
    if not target_ids:
        return {"updated": 0, "deleted_ids": []}

    deleted_ids: list[str] = []
    updated_count = 0
    with _LIBRARY_LOCK:
        snap = _PHOTO_LIBRARY_SNAPSHOT
        valid_col_ids = {c.id for c in snap.collections}
        add_cid = str(add_collection or "").strip()
        rem_cid = str(remove_collection or "").strip()
        if add_cid and add_cid not in valid_col_ids:
            raise ValueError(f"Unknown collection '{add_cid}'")
        if rem_cid and rem_cid not in valid_col_ids:
            raise ValueError(f"Unknown collection '{rem_cid}'")

        new_photos = dict(snap.photos)
        new_order = list(snap.photo_order)
        new_pcols = dict(snap.preset_collections)

        if delete:
            for pid in target_ids:
                if pid not in new_photos:
                    continue
                target_path = resolve_photo_path(root, pid)
                if target_path is not None and target_path.is_file():
                    target_path.unlink()
                new_photos.pop(pid, None)
                if pid in new_order:
                    new_order.remove(pid)
                deleted_ids.append(pid)
                updated_count += 1
        else:
            for pid in target_ids:
                if pid in new_photos:
                    rec = new_photos[pid]
                    tags = list(rec.collections)
                    changed_one = False
                    if add_cid and add_cid not in tags:
                        tags.append(add_cid)
                        changed_one = True
                    if rem_cid and rem_cid in tags:
                        tags.remove(rem_cid)
                        changed_one = True
                    if changed_one:
                        new_photos[pid] = PhotoRecord(
                            id=rec.id,
                            filename=rec.filename,
                            name=rec.name,
                            width=rec.width,
                            height=rec.height,
                            crop=rec.crop,
                            collections=tuple(tags),
                            content_sha256=rec.content_sha256,
                            source_kind=rec.source_kind,
                            media_source_path=rec.media_source_path,
                            added_at=rec.added_at,
                        )
                        updated_count += 1
                elif pid in _PRESET_BY_ID:
                    tags = list(new_pcols.get(pid, ()))
                    changed_one = False
                    if add_cid and add_cid not in tags:
                        tags.append(add_cid)
                        changed_one = True
                    if rem_cid and rem_cid in tags:
                        tags.remove(rem_cid)
                        changed_one = True
                    if changed_one:
                        if tags:
                            new_pcols[pid] = tuple(tags)
                        else:
                            new_pcols.pop(pid, None)
                        updated_count += 1

        if updated_count > 0:
            new_snap = PhotoLibrarySnapshot(
                collections=snap.collections,
                photos=MappingProxyType(new_photos),
                photo_order=tuple(new_order),
                preset_collections=MappingProxyType(new_pcols),
            )
            _write_index_atomic(root, new_snap)
            _PHOTO_LIBRARY_SNAPSHOT = new_snap

    if deleted_ids:
        from .http import evict_wallpaper_lru_cache

        for pid in deleted_ids:
            evict_wallpaper_lru_cache(pid)

    return {"updated": updated_count, "deleted_ids": deleted_ids}


def delete_photo(hass: HomeAssistant, photo_id: str) -> bool:
    """Delete a custom photo (`photo:<key>`) from private storage and `index.json`."""
    res = bulk_update_photos(hass, [photo_id], delete=True)
    return bool(res["deleted_ids"])


def save_uploaded_photo_bytes(
    hass: HomeAssistant,
    filename: str,
    raw_bytes: bytes,
    *,
    crop_x: float = 0.5,
    crop_y: float = 0.5,
    crop_zoom: float = 1.0,
    name: str | None = None,
    collection_id: str | None = None,
    source_kind: str = "upload",
    media_source_path: str = "",
) -> dict[str, Any]:
    """Validate, EXIF-transpose, downscale to <= 1600 px, and save raw image bytes into the shared Photo Library."""
    global _PHOTO_LIBRARY_SNAPSHOT
    if not raw_bytes:
        raise ValueError("Empty photo upload")
    if len(raw_bytes) > MAX_WALLPAPER_UPLOAD_BYTES:
        raise ValueError("Photo upload exceeds 15 MB limit")

    content_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    jpeg_bytes, width, height = _encode_original_jpeg(raw_bytes)
    crop = normalize_crop(crop_x, crop_y, crop_zoom)
    display_name = _clean_display_name(
        name, _humanize_filename_stem(filename or "photo.jpg"), MAX_PHOTO_NAME_LEN
    )
    clean_source_kind = (
        source_kind if source_kind in ("upload", "media_import") else "upload"
    )

    root = get_wallpaper_root(hass)
    orig_dir = _originals_dir(root)
    orig_dir.mkdir(parents=True, exist_ok=True)

    with _LIBRARY_LOCK:
        snap = _PHOTO_LIBRARY_SNAPSHOT
        valid_col_ids = {c.id for c in snap.collections}
        cid = str(collection_id or "").strip()
        if cid and cid not in valid_col_ids:
            raise ValueError(f"Unknown collection '{cid}'")
        tags: tuple[str, ...] = (cid,) if cid else ()

        stem = re.sub(
            r"[^a-z0-9_]+", "_", Path(filename or "photo").stem.lower()
        ).strip("_")[:24]
        key_base = f"{stem}_{secrets.token_hex(4)}" if stem else f"img_{secrets.token_hex(5)}"
        photo_id = make_photo_source(key_base)
        while photo_id in snap.photos:
            key_base = f"img_{secrets.token_hex(6)}"
            photo_id = make_photo_source(key_base)
        out_name = f"{key_base}.jpg"
        out_path = orig_dir / out_name
        out_path.write_bytes(jpeg_bytes)

        rec = PhotoRecord(
            id=photo_id,
            filename=out_name,
            name=display_name,
            width=width,
            height=height,
            crop=crop,
            collections=tags,
            content_sha256=content_sha256,
            source_kind=clean_source_kind,
            media_source_path=str(media_source_path or "").strip(),
            added_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        new_photos = dict(snap.photos)
        new_photos[photo_id] = rec
        new_order = (*snap.photo_order, photo_id)
        new_snap = PhotoLibrarySnapshot(
            collections=snap.collections,
            photos=MappingProxyType(new_photos),
            photo_order=new_order,
            preset_collections=snap.preset_collections,
        )
        _write_index_atomic(root, new_snap)
        _PHOTO_LIBRARY_SNAPSHOT = new_snap

    from .http import evict_wallpaper_lru_cache

    evict_wallpaper_lru_cache(photo_id)
    return {
        "id": rec.id,
        "filename": rec.filename,
        "name": rec.name,
        "kind": "uploaded",
        "width": rec.width,
        "height": rec.height,
        "crop": rec.crop.as_dict(),
        "collections": list(rec.collections),
        "source_kind": rec.source_kind,
        "media_source_path": rec.media_source_path,
        "added_at": rec.added_at,
    }


# ---------------------------------------------------------------------------
# Home Assistant /media Folder Browser & Batch Importer (Symlink-Safe Confinement)
# ---------------------------------------------------------------------------


def _normalize_media_relpath(relpath: str) -> str | None:
    """Normalize a relative posix path inside a media root, rejecting traversal or absolute segments."""
    raw = str(relpath or "").replace("\\", "/").strip()
    if not raw or raw == ".":
        return ""
    if "\x00" in raw or raw.startswith("/"):
        return None
    parts: list[str] = []
    for seg in raw.split("/"):
        if not seg or seg == ".":
            continue
        if seg == ".." or seg.startswith("."):
            return None
        parts.append(seg)
    return "/".join(parts)


def resolve_media_path(
    media_dirs: Mapping[str, str] | None, root: str, relpath: str = ""
) -> Path | None:
    """Resolve `(root, relpath)` strictly inside `media_dirs[root]` with symlink-escape rejection."""
    if not isinstance(media_dirs, Mapping) or not media_dirs:
        return None
    root_key = str(root or "").strip()
    raw_root_dir = media_dirs.get(root_key)
    if not raw_root_dir:
        return None
    norm_rel = _normalize_media_relpath(relpath)
    if norm_rel is None:
        return None
    try:
        root_dir = Path(raw_root_dir).resolve(strict=True)
    except OSError:
        return None
    if not root_dir.is_dir():
        return None
    target = (root_dir / norm_rel) if norm_rel else root_dir
    try:
        resolved = target.resolve(strict=True)
    except OSError:
        return None
    if not resolved.is_relative_to(root_dir):
        return None
    return resolved


def list_media_folder_sync(
    media_dirs: Mapping[str, str] | None,
    root: str = "",
    subpath: str = "",
) -> dict[str, Any]:
    """List subfolders and supported image files strictly confined inside `hass.config.media_dirs`."""
    raw_dirs = media_dirs if isinstance(media_dirs, Mapping) else {}
    roots: list[dict[str, str]] = []
    valid_dirs: dict[str, Path] = {}
    for key in sorted(raw_dirs.keys(), key=lambda k: (k != "local", k.lower())):
        try:
            rpath = Path(raw_dirs[key]).resolve(strict=True)
        except OSError:
            continue
        if rpath.is_dir():
            valid_dirs[key] = rpath
            roots.append(
                {
                    "id": str(key),
                    "name": str(key).replace("_", " ").title(),
                }
            )

    if not valid_dirs:
        return {
            "roots": [],
            "root": "",
            "subpath": "",
            "parent_subpath": None,
            "folders": [],
            "images": [],
        }

    selected_root = str(root or "").strip()
    if not selected_root:
        selected_root = "local" if "local" in valid_dirs else roots[0]["id"]
    if selected_root not in valid_dirs:
        raise ValueError(f"Unknown media folder root '{selected_root}'")

    norm_sub = _normalize_media_relpath(subpath)
    if norm_sub is None:
        raise ValueError("Invalid media folder subpath")

    root_dir = valid_dirs[selected_root]
    target_dir = resolve_media_path(raw_dirs, selected_root, norm_sub)
    if target_dir is None or not target_dir.is_dir():
        raise ValueError("Media folder does not exist or is outside allowed media directory")

    snap = _PHOTO_LIBRARY_SNAPSHOT
    imported_paths = {
        rec.media_source_path
        for rec in snap.photos.values()
        if rec.media_source_path
    }

    folders: list[dict[str, str]] = []
    images: list[dict[str, Any]] = []
    for entry in sorted(target_dir.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith("."):
            continue
        try:
            resolved = entry.resolve(strict=True)
        except OSError:
            continue
        if not resolved.is_relative_to(root_dir):
            continue
        rel_posix = (
            f"{norm_sub}/{entry.name}" if norm_sub else entry.name
        )
        if resolved.is_dir():
            folders.append({"name": entry.name, "subpath": rel_posix})
        elif resolved.is_file() and entry.suffix.lower() in IMAGE_SUFFIXES:
            try:
                size_bytes = resolved.stat().st_size
            except OSError:
                continue
            if size_bytes <= 0:
                continue
            images.append(
                {
                    "name": entry.name,
                    "relpath": rel_posix,
                    "size_bytes": size_bytes,
                    "too_large": size_bytes > MAX_WALLPAPER_UPLOAD_BYTES,
                    "already_imported": f"{selected_root}/{rel_posix}" in imported_paths,
                }
            )

    parent_subpath: str | None = None
    if norm_sub:
        parent_subpath = norm_sub.rsplit("/", 1)[0] if "/" in norm_sub else ""

    return {
        "roots": roots,
        "root": selected_root,
        "subpath": norm_sub,
        "parent_subpath": parent_subpath,
        "folders": folders,
        "images": images,
    }


def import_media_photos_sync(
    hass: HomeAssistant,
    media_dirs: Mapping[str, str] | None,
    root: str,
    paths: Sequence[str],
    collection_id: str | None = None,
    deduplicate: bool = True,
) -> dict[str, Any]:
    """Batch-import images from HA `/media` into the Photo Library with SHA-256 deduplication."""
    global _PHOTO_LIBRARY_SNAPSHOT
    root_key = str(root or "").strip()
    if not isinstance(media_dirs, Mapping) or root_key not in media_dirs:
        raise ValueError(f"Unknown media folder root '{root_key}'")
    path_list = [str(p or "").strip() for p in (paths or ()) if str(p or "").strip()]
    if not path_list:
        return {"imported": 0, "skipped": 0, "failed": [], "photos": []}
    if len(path_list) > MAX_MEDIA_IMPORT_BATCH:
        raise ValueError(
            f"Cannot import more than {MAX_MEDIA_IMPORT_BATCH} photos in one batch"
        )

    wp_root = get_wallpaper_root(hass)
    orig_dir = _originals_dir(wp_root)
    orig_dir.mkdir(parents=True, exist_ok=True)

    imported = 0
    skipped = 0
    failed: list[dict[str, str]] = []
    created_photos: list[dict[str, Any]] = []

    with _LIBRARY_LOCK:
        snap = _PHOTO_LIBRARY_SNAPSHOT
        valid_col_ids = {c.id for c in snap.collections}
        cid = str(collection_id or "").strip()
        if cid and cid not in valid_col_ids:
            raise ValueError(f"Unknown collection '{cid}'")

        new_photos = dict(snap.photos)
        new_order = list(snap.photo_order)
        sha_to_pid: dict[str, str] = {
            rec.content_sha256: pid
            for pid, rec in new_photos.items()
            if rec.content_sha256
        }
        mutated = False

        for relpath in path_list:
            norm_rel = _normalize_media_relpath(relpath)
            if not norm_rel:
                failed.append({"path": relpath, "error": "Invalid media path"})
                continue
            resolved = resolve_media_path(media_dirs, root_key, norm_rel)
            if resolved is None or not resolved.is_file():
                failed.append({"path": relpath, "error": "File not found or outside media root"})
                continue
            if resolved.suffix.lower() not in IMAGE_SUFFIXES:
                failed.append({"path": relpath, "error": "Unsupported image format"})
                continue
            try:
                size_bytes = resolved.stat().st_size
            except OSError as err:
                failed.append({"path": relpath, "error": str(err)})
                continue
            if size_bytes <= 0:
                failed.append({"path": relpath, "error": "Empty file"})
                continue
            if size_bytes > MAX_WALLPAPER_UPLOAD_BYTES:
                failed.append({"path": relpath, "error": "File exceeds 15 MB limit"})
                continue
            try:
                raw_bytes = resolved.read_bytes()
            except OSError as err:
                failed.append({"path": relpath, "error": str(err)})
                continue

            content_sha256 = hashlib.sha256(raw_bytes).hexdigest()
            existing_pid = sha_to_pid.get(content_sha256) if deduplicate else None
            if existing_pid is not None and existing_pid in new_photos:
                skipped += 1
                if cid:
                    ex_rec = new_photos[existing_pid]
                    if cid not in ex_rec.collections:
                        new_photos[existing_pid] = PhotoRecord(
                            id=ex_rec.id,
                            filename=ex_rec.filename,
                            name=ex_rec.name,
                            width=ex_rec.width,
                            height=ex_rec.height,
                            crop=ex_rec.crop,
                            collections=(*ex_rec.collections, cid),
                            content_sha256=ex_rec.content_sha256,
                            source_kind=ex_rec.source_kind,
                            media_source_path=ex_rec.media_source_path,
                            added_at=ex_rec.added_at,
                        )
                        mutated = True
                continue

            try:
                jpeg_bytes, width, height = _encode_original_jpeg(raw_bytes)
            except Exception as err:  # noqa: BLE001
                failed.append({"path": relpath, "error": f"Invalid image: {err}"})
                continue

            stem = re.sub(
                r"[^a-z0-9_]+", "_", resolved.stem.lower()
            ).strip("_")[:24]
            key_base = f"{stem}_{secrets.token_hex(4)}" if stem else f"img_{secrets.token_hex(5)}"
            photo_id = make_photo_source(key_base)
            while photo_id in new_photos:
                key_base = f"img_{secrets.token_hex(6)}"
                photo_id = make_photo_source(key_base)
            out_name = f"{key_base}.jpg"
            (orig_dir / out_name).write_bytes(jpeg_bytes)

            rec = PhotoRecord(
                id=photo_id,
                filename=out_name,
                name=_humanize_filename_stem(resolved.name),
                width=width,
                height=height,
                crop=PhotoCrop(),
                collections=(cid,) if cid else (),
                content_sha256=content_sha256,
                source_kind="media_import",
                media_source_path=f"{root_key}/{norm_rel}",
                added_at=datetime.now(UTC).isoformat(timespec="seconds"),
            )
            new_photos[photo_id] = rec
            new_order.append(photo_id)
            sha_to_pid[content_sha256] = photo_id
            imported += 1
            mutated = True
            created_photos.append(
                {
                    "id": rec.id,
                    "filename": rec.filename,
                    "name": rec.name,
                    "kind": "uploaded",
                    "width": rec.width,
                    "height": rec.height,
                    "crop": rec.crop.as_dict(),
                    "collections": list(rec.collections),
                    "source_kind": rec.source_kind,
                    "media_source_path": rec.media_source_path,
                    "added_at": rec.added_at,
                }
            )

        if mutated:
            new_snap = PhotoLibrarySnapshot(
                collections=snap.collections,
                photos=MappingProxyType(new_photos),
                photo_order=tuple(new_order),
                preset_collections=snap.preset_collections,
            )
            _write_index_atomic(wp_root, new_snap)
            _PHOTO_LIBRARY_SNAPSHOT = new_snap

    return {
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "photos": created_photos,
    }


# ---------------------------------------------------------------------------
# Backup Export / Restore Helpers
# ---------------------------------------------------------------------------


def export_photo_library_metadata(
    snapshot: PhotoLibrarySnapshot | None = None,
) -> dict[str, Any]:
    """Export collections, photo names/crops/tags, and preset collection tags for System backups."""
    snap = snapshot if snapshot is not None else _PHOTO_LIBRARY_SNAPSHOT
    return {
        "photo_collections": [c.as_dict() for c in snap.collections],
        "photo_metadata": {
            pid: {
                "name": rec.name,
                "crop": rec.crop.as_dict(),
                "collections": list(rec.collections),
            }
            for pid in snap.photo_order
            if (rec := snap.photos.get(pid)) is not None
        },
        "preset_collections": {
            pid: list(cols)
            for pid, cols in snap.preset_collections.items()
            if cols
        },
    }


def restore_photo_library_metadata(
    hass: HomeAssistant,
    collections_in: Any,
    photo_metadata_in: Any,
    preset_collections_in: Any = None,
) -> None:
    """Restore collections and photo/preset metadata onto existing library originals (executor)."""
    global _PHOTO_LIBRARY_SNAPSHOT
    root = get_wallpaper_root(hass)
    evict_ids: list[str] = []

    with _LIBRARY_LOCK:
        snap = _PHOTO_LIBRARY_SNAPSHOT
        new_cols_list: list[PhotoCollectionRecord] = []
        valid_col_ids: set[str] = set()
        if isinstance(collections_in, list):
            for item in collections_in:
                if not isinstance(item, Mapping):
                    continue
                cid = str(item.get("id") or "").strip()
                cname = _clean_display_name(
                    item.get("name"), "", MAX_COLLECTION_NAME_LEN
                )
                if cid and _COLLECTION_ID_RE.match(cid) and cname and cid not in valid_col_ids:
                    valid_col_ids.add(cid)
                    new_cols_list.append(PhotoCollectionRecord(id=cid, name=cname))
                    if len(new_cols_list) >= MAX_COLLECTIONS:
                        break
        else:
            new_cols_list = list(snap.collections)
            valid_col_ids = {c.id for c in new_cols_list}

        new_photos = dict(snap.photos)
        if isinstance(photo_metadata_in, Mapping):
            for pid, meta in photo_metadata_in.items():
                if pid not in new_photos or not isinstance(meta, Mapping):
                    continue
                rec = new_photos[pid]
                raw_crop = meta.get("crop")
                crop = (
                    normalize_crop(
                        raw_crop.get("x", rec.crop.x),
                        raw_crop.get("y", rec.crop.y),
                        raw_crop.get("zoom", rec.crop.zoom),
                    )
                    if isinstance(raw_crop, Mapping)
                    else rec.crop
                )
                raw_tags = meta.get("collections")
                tags = (
                    tuple(
                        dict.fromkeys(
                            str(c).strip()
                            for c in raw_tags
                            if str(c).strip() in valid_col_ids
                        )
                    )
                    if isinstance(raw_tags, list)
                    else tuple(c for c in rec.collections if c in valid_col_ids)
                )
                new_name = _clean_display_name(
                    meta.get("name"), rec.name, MAX_PHOTO_NAME_LEN
                )
                if crop != rec.crop:
                    evict_ids.append(pid)
                new_photos[pid] = PhotoRecord(
                    id=rec.id,
                    filename=rec.filename,
                    name=new_name,
                    width=rec.width,
                    height=rec.height,
                    crop=crop,
                    collections=tags,
                    content_sha256=rec.content_sha256,
                    source_kind=rec.source_kind,
                    media_source_path=rec.media_source_path,
                    added_at=rec.added_at,
                )
        else:
            for pid, rec in list(new_photos.items()):
                filtered_tags = tuple(c for c in rec.collections if c in valid_col_ids)
                if filtered_tags != rec.collections:
                    new_photos[pid] = PhotoRecord(
                        id=rec.id,
                        filename=rec.filename,
                        name=rec.name,
                        width=rec.width,
                        height=rec.height,
                        crop=rec.crop,
                        collections=filtered_tags,
                        content_sha256=rec.content_sha256,
                        source_kind=rec.source_kind,
                        media_source_path=rec.media_source_path,
                        added_at=rec.added_at,
                    )

        new_pcols: dict[str, tuple[str, ...]] = {}
        if isinstance(preset_collections_in, Mapping):
            for pid, cols in preset_collections_in.items():
                if pid not in _PRESET_BY_ID or not isinstance(cols, list):
                    continue
                cleaned = tuple(
                    dict.fromkeys(
                        str(c).strip() for c in cols if str(c).strip() in valid_col_ids
                    )
                )
                if cleaned:
                    new_pcols[pid] = cleaned
        else:
            for pid, cols in snap.preset_collections.items():
                filtered = tuple(c for c in cols if c in valid_col_ids)
                if filtered:
                    new_pcols[pid] = filtered

        new_snap = PhotoLibrarySnapshot(
            collections=tuple(new_cols_list),
            photos=MappingProxyType(new_photos),
            photo_order=snap.photo_order,
            preset_collections=MappingProxyType(new_pcols),
        )
        _write_index_atomic(root, new_snap)
        _PHOTO_LIBRARY_SNAPSHOT = new_snap

    if evict_ids:
        from .http import evict_wallpaper_lru_cache

        for pid in evict_ids:
            evict_wallpaper_lru_cache(pid)
