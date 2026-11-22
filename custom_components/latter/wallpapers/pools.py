"""Wallpaper & Screensaver Photo Frame catalog builders and rotation pool resolvers (`L1b`)."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from ..const import normalize_device_slug
from .models import (
    BUILTIN_WALLPAPER_PRESETS,
    PRESET_BY_ID,
    VIRTUAL_COLLECTION_ALL,
    VIRTUAL_COLLECTION_DEFAULTS,
    VIRTUAL_COLLECTION_UNCATEGORIZED,
    VIRTUAL_COLLECTION_UPLOADS,
    PhotoCrop,
    PhotoLibrarySnapshot,
    PhotoRecord,
)
from .store import collection_counts, get_photo_library_snapshot

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def ordered_wallpaper_ids(*, include_dynamic: bool = True) -> list[str]:
    """Return all library photo IDs in deterministic display order (defaults, then custom photos)."""
    snap = get_photo_library_snapshot()
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
    snap = snapshot if snapshot is not None else get_photo_library_snapshot()
    return {c.id for c in snap.collections}


def list_photo_collections(
    snapshot: PhotoLibrarySnapshot | None = None,
) -> list[dict[str, Any]]:
    """Return all user photo collections with live item counts."""
    snap = snapshot if snapshot is not None else get_photo_library_snapshot()
    counts = collection_counts(snap)
    return [{"id": c.id, "name": c.name, "count": counts.get(c.id, 0)} for c in snap.collections]


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
    snap = get_photo_library_snapshot()
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
        thumb_mode = "wallpaper" if preset["kind"] == "dynamic_preset" else "screensaver"
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
        if (rec := snap.photos.get(pid)) is None:
            continue
        items.append(
            _serialize_photo_item(
                rec,
                active=(pid == active_source),
                favorite=(pid in fav_set),
                thumb_url=_build_thumb_url(pid, mode="screensaver", crop_tag=rec.crop.crop_hash()),
                orig_url=_build_orig_url(pid),
            )
        )
    return items


def _resolve_collection_pool(
    col: str, snap: PhotoLibrarySnapshot, *, include_dynamic: bool
) -> list[str]:
    if not col:
        return []
    preset_ids = [
        p["id"]
        for p in BUILTIN_WALLPAPER_PRESETS
        if include_dynamic or p["kind"] != "dynamic_preset"
    ]
    virtual_pools: dict[str, list[str]] = {
        VIRTUAL_COLLECTION_ALL: preset_ids + list(snap.photo_order),
        VIRTUAL_COLLECTION_DEFAULTS: preset_ids,
        VIRTUAL_COLLECTION_UPLOADS: list(snap.photo_order),
    }
    if col in virtual_pools:
        return virtual_pools[col]
    if col == VIRTUAL_COLLECTION_UNCATEGORIZED:
        return [
            pid
            for pid in snap.photo_order
            if (rec := snap.photos.get(pid)) is not None and not rec.collections
        ]
    if col in {c.id for c in snap.collections}:
        matched_presets = [
            pid for pid in preset_ids if col in snap.preset_collections.get(pid, ())
        ]
        matched_photos = [
            pid
            for pid in snap.photo_order
            if (rec := snap.photos.get(pid)) is not None and col in rec.collections
        ]
        return matched_presets + matched_photos
    return []


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
    snap = snapshot if snapshot is not None else get_photo_library_snapshot()
    clean_mode = str(mode or "off").strip().lower()
    if clean_mode == "off":
        return []

    def _allowed_preset(pid: str) -> bool:
        preset = PRESET_BY_ID.get(pid)
        return preset is not None and (include_dynamic or preset["kind"] != "dynamic_preset")

    if clean_mode == "single":
        sid = str(single_source or "").strip()
        return [sid] if sid and (sid in snap.photos or _allowed_preset(sid)) else []
    if clean_mode == "collection":
        return _resolve_collection_pool(
            str(collection_id or "").strip(), snap, include_dynamic=include_dynamic
        )
    if clean_mode == "custom":
        out: list[str] = []
        seen: set[str] = set()
        for raw_id in custom_ids or ():
            pid = str(raw_id or "").strip()
            if pid and pid not in seen and (pid in snap.photos or _allowed_preset(pid)):
                seen.add(pid)
                out.append(pid)
        return out
    return []
