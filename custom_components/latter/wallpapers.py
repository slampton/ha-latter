"""Bundled Default Wallpapers, Uploaded-Wallpaper References, & Immutable Snapshot Gallery Manager."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
import io
import logging
from pathlib import Path
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from PIL import Image, ImageOps

from .const import normalize_device_slug

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

UPLOAD_PREFIX = "upload:"
PRIVATE_DIR_PARTS: tuple[str, ...] = (".storage", "latter", "wallpapers")
IMAGE_SUFFIXES: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp")
MAX_WALLPAPER_UPLOAD_BYTES: int = 15 * 1024 * 1024  # 15 MB hard upload cap

_SLUG = re.compile(r"^[a-z0-9_]+$")
_FILE = re.compile(r"^[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)$", re.IGNORECASE)

BUILTIN_WALLPAPERS_DIR: Path = Path(__file__).resolve().parent / "wallpapers"

BUILTIN_WALLPAPER_PRESETS: tuple[dict[str, str], ...] = (
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

_PRESET_FILE_BY_ID: dict[str, str] = {
    p["id"]: p["file"] for p in BUILTIN_WALLPAPER_PRESETS
}

# Immutable snapshot swapped atomically by awaited executor jobs (never mutated in-place across threads)
_WALLPAPER_SNAPSHOT: MappingProxyType[str, tuple[tuple[str, str], ...]] = (
    MappingProxyType({})
)


def private_root(config_dir: Path | str) -> Path:
    """Return Latter's private wallpaper root under the Home Assistant config directory."""
    return Path(config_dir).joinpath(*PRIVATE_DIR_PARTS)


def make_upload_source(device_slug: str, filename: str) -> str:
    """Return the `upload:<slug>/<file>` reference for an uploaded file."""
    if not _SLUG.match(device_slug) or not _FILE.match(filename):
        raise ValueError(
            f"Invalid wallpaper reference parts: {device_slug!r}, {filename!r}"
        )
    return f"{UPLOAD_PREFIX}{device_slug}/{filename}"


def parse_upload_source(source: str) -> tuple[str, str] | None:
    """Return (device_slug, filename) for a valid `upload:` reference, else None."""
    if not source.startswith(UPLOAD_PREFIX):
        return None
    slug, sep, filename = source[len(UPLOAD_PREFIX) :].partition("/")
    if not sep or not _SLUG.match(slug) or not _FILE.match(filename):
        return None
    return slug, filename


def resolve_upload_path(root: Path, source: str) -> Path | None:
    """Return the file inside `root` for a valid `upload:` reference, else None (never outside `root`)."""
    parsed = parse_upload_source(source)
    if parsed is None:
        return None
    path = (root / parsed[0] / parsed[1]).resolve()
    return path if path.is_relative_to(root.resolve()) else None


def read_upload_bytes(root: Path, source: str) -> bytes | None:
    """Return the bytes of an uploaded wallpaper, or None if the reference is invalid or the file is gone (executor)."""
    path = resolve_upload_path(root, source)
    if path is None or not path.is_file():
        return None
    return path.read_bytes()


def get_wallpaper_root(hass: HomeAssistant) -> Path:
    """Return Latter's private wallpaper root (`<config>/.storage/latter/wallpapers`, never served by HA)."""
    return private_root(hass.config.config_dir)


def get_device_wallpaper_dir(hass: HomeAssistant, device_slug: str) -> Path:
    """Return the private upload directory of one Device or `'system'` (`<wallpaper root>/<slug>`)."""
    return get_wallpaper_root(hass) / normalize_device_slug(device_slug)


def render_builtin_preset_image(
    preset_id: str, width: int = 466, height: int = 466
) -> Image.Image:
    """Load a bundled default wallpaper and center-crop to (width, height)."""
    width = max(64, min(1920, int(width)))
    height = max(64, min(1920, int(height)))
    fname = _PRESET_FILE_BY_ID.get(preset_id, "forest_mountains.jpg")
    img_path = BUILTIN_WALLPAPERS_DIR / fname
    with Image.open(img_path) as img:
        rgb = img.convert("RGB")
        if rgb.size == (width, height):
            return rgb.copy()
        return ImageOps.fit(
            rgb,
            (width, height),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )


def _scan_single_dir(wp_dir: Path, slug: str) -> tuple[tuple[str, str], ...]:
    """Scan uploaded wallpaper files in one directory into an immutable tuple."""
    entries: list[tuple[str, str]] = []
    if wp_dir.is_dir():
        for file_path in sorted(wp_dir.glob("*"), key=lambda p: p.name.lower()):
            if file_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            try:
                source_id = make_upload_source(slug, file_path.name)
            except ValueError:
                continue
            entries.append((source_id, file_path.name))
    return tuple(entries)


def _scan_all_wallpapers_sync(
    root: Path,
) -> MappingProxyType[str, tuple[tuple[str, str], ...]]:
    """Scan all uploaded wallpaper directories in a worker thread and swap an immutable snapshot."""
    global _WALLPAPER_SNAPSHOT
    fresh: dict[str, tuple[tuple[str, str], ...]] = {}
    if root.is_dir():
        for sub_dir in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not sub_dir.is_dir():
                continue
            slug = normalize_device_slug(sub_dir.name)
            if slug != sub_dir.name:
                continue
            fresh[slug] = _scan_single_dir(sub_dir, slug)
    snapshot = MappingProxyType(fresh)
    _WALLPAPER_SNAPSHOT = snapshot
    return snapshot


def _replace_slug_in_snapshot(slug: str, entries: tuple[tuple[str, str], ...]) -> None:
    """Atomically replace a single slug's entries in the immutable snapshot."""
    global _WALLPAPER_SNAPSHOT
    updated = dict(_WALLPAPER_SNAPSHOT)
    if entries:
        updated[slug] = entries
    else:
        updated.pop(slug, None)
    _WALLPAPER_SNAPSHOT = MappingProxyType(updated)


def _all_cached_uploads() -> list[tuple[str, str]]:
    """Return all cached uploaded wallpapers across the System (`system` first, then each Device)."""
    snap = _WALLPAPER_SNAPSHOT
    out: list[tuple[str, str]] = []
    seen_files: set[str] = set()
    ordered_slugs = ["system", *sorted(k for k in snap if k != "system")]
    for s in ordered_slugs:
        for source_id, fname in snap.get(s, ()):
            if fname in seen_files:
                continue
            seen_files.add(fname)
            out.append((source_id, fname))
    return out


async def async_refresh_wallpaper_cache(
    hass: HomeAssistant, device_slug: str = "system"
) -> MappingProxyType[str, tuple[tuple[str, str], ...]]:
    """Populate the immutable uploaded wallpaper snapshot via awaited executor scan."""
    _ = device_slug
    return await hass.async_add_executor_job(
        _scan_all_wallpapers_sync, get_wallpaper_root(hass)
    )


def known_wallpaper_ids(device_slug: str = "system") -> set[str]:
    """Return the wallpaper IDs a Device may select: the built-in presets and all shared uploads."""
    _ = device_slug
    return {p["id"] for p in BUILTIN_WALLPAPER_PRESETS} | {
        source_id for source_id, _ in _all_cached_uploads()
    }


def list_wallpaper_catalog(
    hass: HomeAssistant,
    device_slug: str,
    active_source: str,
    favorites: list[str],
    *,
    sign_resource: Callable[[str], str] | None = None,
    display_shape: str = "circle",
) -> list[dict[str, Any]]:
    """Return built-in default presets + shared uploads from the frozen snapshot, each with a signed Studio thumbnail URL."""
    _ = hass
    fav_set = set(favorites or [])
    items: list[dict[str, Any]] = []
    slug = normalize_device_slug(device_slug or "system")
    wp_shape = "square" if display_shape == "square" else "circle"

    def _build_thumb_url(src_id: str) -> str:
        if sign_resource is None:
            return ""
        sig = sign_resource(f"wallpaper:{src_id}|240|240|{wp_shape}")
        return (
            f"/api/latter/wallpaper/{slug}"
            f"?w=240&h=240&shape={wp_shape}&src={quote(src_id, safe='')}&sig={sig}"
        )

    for preset in BUILTIN_WALLPAPER_PRESETS:
        pid = preset["id"]
        items.append(
            {
                "id": pid,
                "name": preset["name"],
                "kind": "preset",
                "active": pid == active_source,
                "favorite": pid in fav_set,
                "deletable": False,
                "thumb_url": _build_thumb_url(pid),
            }
        )

    for source_id, fname in _all_cached_uploads():
        stem = Path(fname).stem
        items.append(
            {
                "id": source_id,
                "name": stem.replace("_", " ").title(),
                "filename": fname,
                "kind": "uploaded",
                "active": source_id == active_source,
                "favorite": source_id in fav_set,
                "deletable": True,
                "thumb_url": _build_thumb_url(source_id),
            }
        )

    return items


def save_uploaded_wallpaper_bytes(
    hass: HomeAssistant,
    device_slug: str,
    filename: str,
    raw_bytes: bytes,
) -> tuple[str, str]:
    """Validate, center-crop, and save raw image bytes (<= 15 MB) as RGB Baseline JPEG; return `(source_id, out_filename)`."""
    if not raw_bytes:
        raise ValueError("Empty wallpaper upload")
    if len(raw_bytes) > MAX_WALLPAPER_UPLOAD_BYTES:
        raise ValueError("Wallpaper upload exceeds 15 MB limit")

    slug = normalize_device_slug(device_slug or "system")
    wp_dir = get_device_wallpaper_dir(hass, slug)
    wp_dir.mkdir(parents=True, exist_ok=True)

    stem = re.sub(
        r"[^a-zA-Z0-9_-]+", "_", Path(filename or "wallpaper").stem
    ).strip("_")
    if not stem:
        stem = "wallpaper"
    short_hash = hashlib.md5(raw_bytes).hexdigest()[:6]
    out_name = f"{stem[:28]}_{short_hash}.jpg"
    out_path = wp_dir / out_name

    with Image.open(io.BytesIO(raw_bytes)) as img:
        rgb = img.convert("RGB")
        fitted = ImageOps.fit(
            rgb, (960, 960), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)
        )
        fitted.save(
            out_path, format="JPEG", quality=92, optimize=True, progressive=False
        )

    _replace_slug_in_snapshot(slug, _scan_single_dir(wp_dir, slug))
    source_id = make_upload_source(slug, out_name)
    from .http import evict_wallpaper_lru_cache

    evict_wallpaper_lru_cache(source_id)
    return source_id, out_name


def delete_uploaded_wallpaper(
    hass: HomeAssistant,
    device_slug: str,
    source_id: str,
) -> bool:
    """Delete an uploaded wallpaper (`upload:<slug>/<file>`) from Latter's private storage."""
    _ = device_slug
    parsed = parse_upload_source(source_id)
    if parsed is None:
        return False
    owner_slug = parsed[0]
    root = get_wallpaper_root(hass)
    target = resolve_upload_path(root, source_id)
    if target is not None and target.is_file():
        target.unlink()
        _replace_slug_in_snapshot(
            owner_slug, _scan_single_dir(root / owner_slug, owner_slug)
        )
        from .http import evict_wallpaper_lru_cache

        evict_wallpaper_lru_cache(source_id)
        return True
    return False
