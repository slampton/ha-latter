"""Bundled Default Wallpapers & Shared Gallery File Manager for Latter."""

from __future__ import annotations

import base64
import hashlib
import io
import logging
from collections.abc import Callable
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote

from PIL import Image, ImageOps

from homeassistant.core import HomeAssistant

from .const import normalize_device_slug
from .wallpaper_refs import (
    IMAGE_SUFFIXES,
    make_upload_source,
    parse_upload_source,
    private_root,
    resolve_upload_path,
)

_LOGGER = logging.getLogger(__name__)

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
)

_PRESET_FILE_BY_ID: dict[str, str] = {
    p["id"]: p["file"] for p in BUILTIN_WALLPAPER_PRESETS
}


def get_wallpaper_root(hass: HomeAssistant) -> Path:
    """Return Latter's private wallpaper root (`<config>/.storage/latter/wallpapers`, never served by HA)."""
    return private_root(hass.config.config_dir)


def get_device_wallpaper_dir(hass: HomeAssistant, device_slug: str) -> Path:
    """Return the private upload directory of one Device or `"system"` (`<wallpaper root>/<slug>`)."""
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


def render_builtin_preset_bytes(
    preset_id: str, width: int = 466, height: int = 466
) -> bytes:
    """Render a bundled default wallpaper as PNG bytes."""
    img = render_builtin_preset_image(preset_id, width, height)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


_WALLPAPER_FILES_CACHE: dict[str, list[tuple[str, str]]] = {}
_WALLPAPER_ROOT_SCANNED: bool = False


def _scan_wallpaper_dir_sync(wp_dir: Path, slug: str) -> list[tuple[str, str]]:
    """Scan uploaded wallpaper files in one directory in a worker thread and update the in-memory cache."""
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
    _WALLPAPER_FILES_CACHE[slug] = entries
    return entries


def _scan_all_wallpapers_sync(root: Path) -> None:
    """Scan all uploaded wallpaper directories under `root` in a worker thread."""
    global _WALLPAPER_ROOT_SCANNED
    seen_slugs: set[str] = set()
    if root.is_dir():
        for sub_dir in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not sub_dir.is_dir():
                continue
            slug = normalize_device_slug(sub_dir.name)
            if slug != sub_dir.name:
                continue
            seen_slugs.add(slug)
            _scan_wallpaper_dir_sync(sub_dir, slug)
    for stale in set(_WALLPAPER_FILES_CACHE) - seen_slugs:
        _WALLPAPER_FILES_CACHE.pop(stale, None)
    _WALLPAPER_ROOT_SCANNED = True


def _all_cached_uploads() -> list[tuple[str, str]]:
    """Return all cached uploaded wallpapers across the System (`system` first, then each Device)."""
    out: list[tuple[str, str]] = []
    seen_files: set[str] = set()
    ordered_slugs = ["system"] + sorted(k for k in _WALLPAPER_FILES_CACHE if k != "system")
    for s in ordered_slugs:
        for source_id, fname in _WALLPAPER_FILES_CACHE.get(s, []):
            if fname in seen_files:
                continue
            seen_files.add(fname)
            out.append((source_id, fname))
    return out


async def async_refresh_wallpaper_cache(
    hass: HomeAssistant, device_slug: str = "system"
) -> None:
    """Populate the uploaded wallpaper file cache in the executor without blocking the event loop."""
    _ = device_slug
    await hass.async_add_executor_job(_scan_all_wallpapers_sync, get_wallpaper_root(hass))


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
    """Return built-in default presets + shared uploads, each with a signed Studio thumbnail URL."""
    fav_set = set(favorites or [])
    items: list[dict[str, Any]] = []
    slug = normalize_device_slug(device_slug)
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

    if not _WALLPAPER_ROOT_SCANNED:
        hass.async_add_executor_job(_scan_all_wallpapers_sync, get_wallpaper_root(hass))

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


def save_uploaded_wallpaper(
    hass: HomeAssistant,
    device_slug: str,
    filename: str,
    base64_data: str,
) -> str:
    """Decode a base64 image upload, save it as an RGB JPEG in Latter's private wallpaper storage, and return its `upload:` ID."""
    if "," in base64_data:
        base64_data = base64_data.split(",", 1)[1]
    raw_bytes = base64.b64decode(base64_data)

    slug = normalize_device_slug(device_slug or "system")
    wp_dir = get_device_wallpaper_dir(hass, slug)
    wp_dir.mkdir(parents=True, exist_ok=True)

    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(filename or "wallpaper").stem).strip("_")
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
        fitted.save(out_path, format="JPEG", quality=92, optimize=True, progressive=False)

    _scan_wallpaper_dir_sync(wp_dir, slug)
    source_id = make_upload_source(slug, out_name)
    from .http import evict_wallpaper_lru_cache

    evict_wallpaper_lru_cache(source_id)
    return source_id


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
        _scan_wallpaper_dir_sync(root / owner_slug, owner_slug)
        from .http import evict_wallpaper_lru_cache

        evict_wallpaper_lru_cache(source_id)
        return True
    return False