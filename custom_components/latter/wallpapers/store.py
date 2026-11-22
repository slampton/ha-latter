"""Transactional System Photo Library index store, CRUD mutations, and backup restore."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import contextlib
from datetime import UTC, datetime
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import secrets
import threading
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

from PIL import Image, ImageOps

from ..http.signing import register_crop_hash_resolver
from ..media_cache import evict_wallpaper_lru_cache, validate_pil_image_dimensions
from .models import (
    COLLECTION_ID_RE,
    INDEX_FILENAME,
    MAX_COLLECTION_NAME_LEN,
    MAX_COLLECTIONS,
    MAX_ORIGINAL_LONG_EDGE,
    MAX_PHOTO_NAME_LEN,
    MAX_WALLPAPER_UPLOAD_BYTES,
    ORIGINALS_SUBDIR,
    PHOTO_KEY_RE,
    PHOTO_PREFIX,
    PRESET_BY_ID,
    PhotoCollectionRecord,
    PhotoCrop,
    PhotoLibrarySnapshot,
    PhotoRecord,
    clean_display_name,
    get_wallpaper_root,
    humanize_filename_stem,
    make_photo_source,
    normalize_crop,
    parse_photo_source,
    resolve_photo_path,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

LIBRARY_LOCK: Final = threading.RLock()
_PHOTO_LIBRARY_SNAPSHOT: PhotoLibrarySnapshot = PhotoLibrarySnapshot()
_LOADED_WALLPAPER_ROOT: Path | None = None
_DEFAULT_FALLBACK_DIM: Final[int] = 960
_ORIGINAL_JPEG_QUALITY: Final[int] = 92
_MAX_STEM_LEN: Final[int] = 24


def originals_dir(root: Path) -> Path:
    """Return `<root>/originals` directory path."""
    return root / ORIGINALS_SUBDIR


def _index_path(root: Path) -> Path:
    return root / INDEX_FILENAME


def _write_index_atomic(root: Path, snapshot: PhotoLibrarySnapshot) -> None:
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
            pid: list(cols) for pid, cols in snapshot.preset_collections.items() if cols
        },
    }
    raw = json.dumps(payload, indent=2, sort_keys=False)
    tmp_path = root / f".{INDEX_FILENAME}.{secrets.token_hex(4)}.tmp"
    tmp_path.write_text(raw, encoding="utf-8")
    os.replace(tmp_path, _index_path(root))


def _parse_raw_collections(raw_cols: object) -> tuple[list[PhotoCollectionRecord], set[str], bool]:
    collections: list[PhotoCollectionRecord] = []
    valid_col_ids: set[str] = set()
    changed = False
    if not isinstance(raw_cols, list):
        return collections, valid_col_ids, changed
    for item in raw_cols:
        if not isinstance(item, Mapping):
            continue
        cid = str(item.get("id") or "").strip()
        cname = clean_display_name(item.get("name"), "", MAX_COLLECTION_NAME_LEN)
        if not cid or not COLLECTION_ID_RE.match(cid) or not cname or cid in valid_col_ids:
            changed = True
            continue
        valid_col_ids.add(cid)
        collections.append(PhotoCollectionRecord(id=cid, name=cname))
        if len(collections) >= MAX_COLLECTIONS:
            break
    return collections, valid_col_ids, changed


def _scan_existing_originals(orig_dir: Path) -> dict[str, Path]:
    existing: dict[str, Path] = {}
    if not orig_dir.is_dir():
        return existing
    for file_path in sorted(orig_dir.iterdir(), key=lambda p: p.name.lower()):
        if file_path.is_file() and file_path.suffix.lower() == ".jpg":
            key = file_path.stem.lower()
            if PHOTO_KEY_RE.match(key):
                existing[f"{PHOTO_PREFIX}{key}"] = file_path
    return existing


def _parse_indexed_photo_entry(
    pid: str,
    meta: Mapping[str, Any],
    file_path: Path,
    valid_col_ids: set[str],
) -> tuple[PhotoRecord | None, bool]:
    key = parse_photo_source(pid)
    if key is None:
        return None, True
    raw_crop = meta.get("crop")
    crop = (
        normalize_crop(raw_crop.get("x", 0.5), raw_crop.get("y", 0.5), raw_crop.get("zoom", 1.0))
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
    changed = False
    if w <= 0 or h <= 0:
        try:
            with Image.open(file_path) as im:
                w, h = im.size
        except Exception:  # noqa: BLE001
            w = h = _DEFAULT_FALLBACK_DIM
        changed = True
    source_kind = str(meta.get("source_kind") or "upload").strip().lower()
    if source_kind not in ("upload", "media_import"):
        source_kind = "upload"
    rec = PhotoRecord(
        id=pid,
        filename=f"{key}.jpg",
        name=clean_display_name(meta.get("name"), humanize_filename_stem(f"{key}.jpg"), MAX_PHOTO_NAME_LEN),
        width=w,
        height=h,
        crop=crop,
        collections=tags,
        content_sha256=str(meta.get("content_sha256") or "").strip().lower(),
        source_kind=source_kind,
        media_source_path=str(meta.get("media_source_path") or "").strip(),
        added_at=str(meta.get("added_at") or "").strip(),
    )
    return rec, changed


def _adopt_orphan_original(pid: str, file_path: Path) -> PhotoRecord | None:
    try:
        raw_b = file_path.read_bytes()
        sha = hashlib.sha256(raw_b).hexdigest()
        with Image.open(io.BytesIO(raw_b)) as im:
            w, h = im.size
    except Exception:  # noqa: BLE001
        return None
    return PhotoRecord(
        id=pid,
        filename=file_path.name,
        name=humanize_filename_stem(file_path.name),
        width=w,
        height=h,
        crop=PhotoCrop(),
        collections=(),
        content_sha256=sha,
        source_kind="upload",
        media_source_path="",
        added_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )


def _parse_preset_collections(
    raw_pcols: object, valid_col_ids: set[str]
) -> tuple[dict[str, tuple[str, ...]], bool]:
    preset_cols: dict[str, tuple[str, ...]] = {}
    changed = False
    if not isinstance(raw_pcols, Mapping):
        return preset_cols, changed
    for pid_raw, col_list in raw_pcols.items():
        pid = str(pid_raw or "").strip()
        if pid not in PRESET_BY_ID or not isinstance(col_list, list):
            changed = True
            continue
        cleaned = tuple(
            dict.fromkeys(str(c).strip() for c in col_list if str(c).strip() in valid_col_ids)
        )
        if cleaned:
            preset_cols[pid] = cleaned
    return preset_cols, changed


def _build_snapshot_from_raw(
    root: Path, raw_index: Mapping[str, Any]
) -> tuple[PhotoLibrarySnapshot, bool]:
    collections, valid_col_ids, col_changed = _parse_raw_collections(raw_index.get("collections"))
    existing_files = _scan_existing_originals(originals_dir(root))
    changed = col_changed

    photos: dict[str, PhotoRecord] = {}
    photo_order: list[str] = []
    raw_photos = raw_index.get("photos")
    if isinstance(raw_photos, Mapping):
        for pid_raw, meta in raw_photos.items():
            pid = str(pid_raw or "").strip().lower()
            if pid not in existing_files or not isinstance(meta, Mapping):
                changed = True
                continue
            rec, rec_changed = _parse_indexed_photo_entry(pid, meta, existing_files[pid], valid_col_ids)
            changed = changed or rec_changed
            if rec is not None:
                photos[pid] = rec
                photo_order.append(pid)

    for pid, file_path in existing_files.items():
        if pid in photos:
            continue
        changed = True
        if (adopted := _adopt_orphan_original(pid, file_path)) is not None:
            photos[pid] = adopted
            photo_order.append(pid)

    preset_cols, pcol_changed = _parse_preset_collections(
        raw_index.get("preset_collections"), valid_col_ids
    )
    snap = PhotoLibrarySnapshot(
        collections=tuple(collections),
        photos=MappingProxyType(photos),
        photo_order=tuple(photo_order),
        preset_collections=MappingProxyType(preset_cols),
    )
    return snap, (changed or pcol_changed)


def _load_photo_library_sync(root: Path) -> PhotoLibrarySnapshot:
    global _PHOTO_LIBRARY_SNAPSHOT, _LOADED_WALLPAPER_ROOT
    with LIBRARY_LOCK:
        resolved_root = root.resolve()
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
        _LOADED_WALLPAPER_ROOT = resolved_root
        return snap


def ensure_loaded_locked(root: Path) -> PhotoLibrarySnapshot:
    """Load `index.json` from disk when the in-memory snapshot doesn't match `root` yet."""
    if root.resolve() != _LOADED_WALLPAPER_ROOT:
        return _load_photo_library_sync(root)
    return _PHOTO_LIBRARY_SNAPSHOT


def commit_snapshot_locked(root: Path, new_snap: PhotoLibrarySnapshot) -> None:
    """Atomically write `index.json` and swap `_PHOTO_LIBRARY_SNAPSHOT` under `LIBRARY_LOCK`."""
    global _PHOTO_LIBRARY_SNAPSHOT, _LOADED_WALLPAPER_ROOT
    _write_index_atomic(root, new_snap)
    _PHOTO_LIBRARY_SNAPSHOT = new_snap
    _LOADED_WALLPAPER_ROOT = root.resolve()


def encode_original_jpeg(raw_bytes: bytes) -> tuple[bytes, int, int]:
    """Decode, EXIF-transpose, downscale to `<= 1600 px` long edge, and encode Baseline JPEG outside lock."""
    with Image.open(io.BytesIO(raw_bytes)) as img:
        validate_pil_image_dimensions(img)
        rgb = ImageOps.exif_transpose(img).convert("RGB")
        w, h = rgb.size
        if w <= 0 or h <= 0:
            raise ValueError("Invalid image dimensions")
        long_edge = max(w, h)
        if long_edge > MAX_ORIGINAL_LONG_EDGE:
            scale = float(MAX_ORIGINAL_LONG_EDGE) / float(long_edge)
            rgb = rgb.resize(
                (max(1, round(w * scale)), max(1, round(h * scale))),
                resample=Image.Resampling.LANCZOS,
            )
            w, h = rgb.size
        out = io.BytesIO()
        rgb.save(out, format="JPEG", quality=_ORIGINAL_JPEG_QUALITY, optimize=True, progressive=False)
        return out.getvalue(), w, h


def mint_unique_photo_id(stem_source: str, existing: Mapping[str, Any]) -> tuple[str, str]:
    """Generate a unique `(photo_id, filename)` pair under `LIBRARY_LOCK`."""
    stem = re.sub(r"[^a-z0-9_]+", "_", Path(stem_source or "photo").stem.lower()).strip("_")[
        :_MAX_STEM_LEN
    ]
    key_base = f"{stem}_{secrets.token_hex(4)}" if stem else f"img_{secrets.token_hex(5)}"
    photo_id = make_photo_source(key_base)
    while photo_id in existing:
        key_base = f"img_{secrets.token_hex(6)}"
        photo_id = make_photo_source(key_base)
    return photo_id, f"{key_base}.jpg"


def collection_counts(snap: PhotoLibrarySnapshot) -> dict[str, int]:
    """Count total photos + presets assigned to each user collection."""
    counts: dict[str, int] = {c.id: 0 for c in snap.collections}
    for rec in snap.photos.values():
        for cid in rec.collections:
            if cid in counts:
                counts[cid] += 1
    for cols in snap.preset_collections.values():
        for cid in cols:
            if cid in counts:
                counts[cid] += 1
    return counts


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


def create_collection(hass: HomeAssistant, name: str) -> dict[str, Any]:
    """Create a new photo collection and persist `index.json` atomically."""
    clean_name = clean_display_name(name, "", MAX_COLLECTION_NAME_LEN)
    if not clean_name:
        raise ValueError("Collection name is required")
    root = get_wallpaper_root(hass)
    with LIBRARY_LOCK:
        snap = ensure_loaded_locked(root)
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
        commit_snapshot_locked(root, new_snap)
        return {"id": rec.id, "name": rec.name, "count": 0}


def rename_collection(hass: HomeAssistant, collection_id: str, name: str) -> dict[str, Any]:
    """Rename an existing photo collection and persist `index.json` atomically."""
    cid = str(collection_id or "").strip()
    clean_name = clean_display_name(name, "", MAX_COLLECTION_NAME_LEN)
    if not clean_name:
        raise ValueError("Collection name is required")
    root = get_wallpaper_root(hass)
    with LIBRARY_LOCK:
        snap = ensure_loaded_locked(root)
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
        commit_snapshot_locked(root, new_snap)
        return {"id": cid, "name": clean_name, "count": collection_counts(new_snap).get(cid, 0)}


def _replace_photo_collections(rec: PhotoRecord, tags: tuple[str, ...]) -> PhotoRecord:
    return PhotoRecord(
        id=rec.id,
        filename=rec.filename,
        name=rec.name,
        width=rec.width,
        height=rec.height,
        crop=rec.crop,
        collections=tags,
        content_sha256=rec.content_sha256,
        source_kind=rec.source_kind,
        media_source_path=rec.media_source_path,
        added_at=rec.added_at,
    )


def delete_collection(hass: HomeAssistant, collection_id: str) -> bool:
    """Delete a collection and remove its tag from every photo and preset."""
    cid = str(collection_id or "").strip()
    root = get_wallpaper_root(hass)
    with LIBRARY_LOCK:
        snap = ensure_loaded_locked(root)
        if not any(c.id == cid for c in snap.collections):
            return False
        new_cols = tuple(c for c in snap.collections if c.id != cid)
        new_photos = {
            pid: (
                _replace_photo_collections(rec, tuple(x for x in rec.collections if x != cid))
                if cid in rec.collections
                else rec
            )
            for pid, rec in snap.photos.items()
        }
        new_pcols = {
            pid: filtered
            for pid, cols in snap.preset_collections.items()
            if (filtered := tuple(x for x in cols if x != cid))
        }
        new_snap = PhotoLibrarySnapshot(
            collections=new_cols,
            photos=MappingProxyType(new_photos),
            photo_order=snap.photo_order,
            preset_collections=MappingProxyType(new_pcols),
        )
        commit_snapshot_locked(root, new_snap)
        return True


def _clean_collection_tag_list(
    collections: Sequence[str], valid_col_ids: set[str]
) -> tuple[str, ...]:
    col_list: list[str] = []
    for raw_c in collections:
        c_tok = str(raw_c or "").strip()
        if not c_tok:
            continue
        if c_tok not in valid_col_ids:
            raise ValueError(f"Unknown collection '{c_tok}'")
        if c_tok not in col_list:
            col_list.append(c_tok)
    return tuple(col_list)


def update_photo_metadata(
    hass: HomeAssistant,
    photo_id: str,
    *,
    name: str | None = None,
    crop: Mapping[str, Any] | None = None,
    collections: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Update a photo's name, non-destructive crop, or collections (presets support collections only)."""
    pid = str(photo_id or "").strip()
    root = get_wallpaper_root(hass)
    crop_changed = False
    with LIBRARY_LOCK:
        snap = ensure_loaded_locked(root)
        valid_col_ids = {c.id for c in snap.collections}
        cleaned_cols = (
            _clean_collection_tag_list(collections, valid_col_ids)
            if collections is not None
            else None
        )
        if pid in PRESET_BY_ID:
            if name is not None or crop is not None:
                raise ValueError("Built-in presets cannot be renamed or cropped")
            new_pcols = dict(snap.preset_collections)
            if cleaned_cols is not None:
                if cleaned_cols:
                    new_pcols[pid] = cleaned_cols
                else:
                    new_pcols.pop(pid, None)
            commit_snapshot_locked(
                root,
                PhotoLibrarySnapshot(
                    snap.collections, snap.photos, snap.photo_order, MappingProxyType(new_pcols)
                ),
            )
            preset = PRESET_BY_ID[pid]
            return {
                "id": pid,
                "name": preset["name"],
                "kind": preset["kind"],
                "collections": list(new_pcols.get(pid, ())),
                "crop": PhotoCrop().as_dict(),
                "crop_changed": False,
            }

        if (rec := snap.photos.get(pid)) is None:
            raise ValueError(f"Unknown photo '{pid}'")
        new_name = clean_display_name(name, "", MAX_PHOTO_NAME_LEN) if name is not None else rec.name
        if not new_name:
            raise ValueError("Photo name cannot be empty")
        new_crop = (
            normalize_crop(
                crop.get("x", rec.crop.x), crop.get("y", rec.crop.y), crop.get("zoom", rec.crop.zoom)
            )
            if crop is not None
            else rec.crop
        )
        crop_changed = new_crop != rec.crop
        updated_rec = PhotoRecord(
            id=rec.id,
            filename=rec.filename,
            name=new_name,
            width=rec.width,
            height=rec.height,
            crop=new_crop,
            collections=cleaned_cols if cleaned_cols is not None else rec.collections,
            content_sha256=rec.content_sha256,
            source_kind=rec.source_kind,
            media_source_path=rec.media_source_path,
            added_at=rec.added_at,
        )
        new_photos = {**snap.photos, pid: updated_rec}
        commit_snapshot_locked(
            root,
            PhotoLibrarySnapshot(
                snap.collections, MappingProxyType(new_photos), snap.photo_order, snap.preset_collections
            ),
        )

    if crop_changed:
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


def _mutate_tag_list(tags: list[str], add_cid: str, rem_cid: str) -> bool:
    changed = False
    if add_cid and add_cid not in tags:
        tags.append(add_cid)
        changed = True
    if rem_cid and rem_cid in tags:
        tags.remove(rem_cid)
        changed = True
    return changed


def _apply_bulk_collection_tags(
    target_ids: list[str],
    new_photos: dict[str, PhotoRecord],
    new_pcols: dict[str, tuple[str, ...]],
    add_cid: str,
    rem_cid: str,
) -> int:
    updated_count = 0
    for pid in target_ids:
        if pid in new_photos:
            rec = new_photos[pid]
            tags = list(rec.collections)
            if _mutate_tag_list(tags, add_cid, rem_cid):
                new_photos[pid] = _replace_photo_collections(rec, tuple(tags))
                updated_count += 1
        elif pid in PRESET_BY_ID:
            tags = list(new_pcols.get(pid, ()))
            if _mutate_tag_list(tags, add_cid, rem_cid):
                if tags:
                    new_pcols[pid] = tuple(tags)
                else:
                    new_pcols.pop(pid, None)
                updated_count += 1
    return updated_count


def bulk_update_photos(
    hass: HomeAssistant,
    photo_ids: Sequence[str],
    *,
    add_collection: str | None = None,
    remove_collection: str | None = None,
    delete: bool = False,
) -> dict[str, Any]:
    """Batch-assign/remove a collection or batch-delete custom photos in one atomic index write."""
    root = get_wallpaper_root(hass)
    target_ids = list(dict.fromkeys(str(p or "").strip() for p in (photo_ids or ()) if str(p or "").strip()))
    if not target_ids:
        return {"updated": 0, "deleted_ids": []}

    deleted_ids: list[str] = []
    paths_to_unlink: list[Path] = []
    updated_count = 0
    with LIBRARY_LOCK:
        snap = ensure_loaded_locked(root)
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
                if (target_path := resolve_photo_path(root, pid)) is not None:
                    paths_to_unlink.append(target_path)
                new_photos.pop(pid, None)
                if pid in new_order:
                    new_order.remove(pid)
                deleted_ids.append(pid)
                updated_count += 1
        else:
            updated_count = _apply_bulk_collection_tags(
                target_ids, new_photos, new_pcols, add_cid, rem_cid
            )

        if updated_count > 0:
            commit_snapshot_locked(
                root,
                PhotoLibrarySnapshot(
                    snap.collections,
                    MappingProxyType(new_photos),
                    tuple(new_order),
                    MappingProxyType(new_pcols),
                ),
            )
            for p_unlink in paths_to_unlink:
                with contextlib.suppress(OSError):
                    p_unlink.unlink(missing_ok=True)

    for pid in deleted_ids:
        evict_wallpaper_lru_cache(pid)
    return {"updated": updated_count, "deleted_ids": deleted_ids}


def delete_photo(hass: HomeAssistant, photo_id: str) -> bool:
    """Delete a custom photo (`photo:<key>`) from private storage and `index.json`."""
    return bool(bulk_update_photos(hass, [photo_id], delete=True)["deleted_ids"])


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
    """Validate, EXIF-transpose, downscale to `<= 1600 px` outside lock, and save into the Photo Library."""
    if not raw_bytes:
        raise ValueError("Empty photo upload")
    if len(raw_bytes) > MAX_WALLPAPER_UPLOAD_BYTES:
        raise ValueError("Photo upload exceeds 15 MB limit")

    content_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    jpeg_bytes, width, height = encode_original_jpeg(raw_bytes)
    crop = normalize_crop(crop_x, crop_y, crop_zoom)
    display_name = clean_display_name(
        name, humanize_filename_stem(filename or "photo.jpg"), MAX_PHOTO_NAME_LEN
    )
    clean_source_kind = source_kind if source_kind in ("upload", "media_import") else "upload"

    root = get_wallpaper_root(hass)
    orig_dir = originals_dir(root)
    orig_dir.mkdir(parents=True, exist_ok=True)

    with LIBRARY_LOCK:
        snap = ensure_loaded_locked(root)
        cid = str(collection_id or "").strip()
        if cid and cid not in {c.id for c in snap.collections}:
            raise ValueError(f"Unknown collection '{cid}'")
        photo_id, out_name = mint_unique_photo_id(filename or "photo", snap.photos)
        (orig_dir / out_name).write_bytes(jpeg_bytes)
        rec = PhotoRecord(
            id=photo_id,
            filename=out_name,
            name=display_name,
            width=width,
            height=height,
            crop=crop,
            collections=(cid,) if cid else (),
            content_sha256=content_sha256,
            source_kind=clean_source_kind,
            media_source_path=str(media_source_path or "").strip(),
            added_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        commit_snapshot_locked(
            root,
            PhotoLibrarySnapshot(
                snap.collections,
                MappingProxyType({**snap.photos, photo_id: rec}),
                (*snap.photo_order, photo_id),
                snap.preset_collections,
            ),
        )

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
            pid: list(cols) for pid, cols in snap.preset_collections.items() if cols
        },
    }


def _restore_photo_records(
    existing_photos: Mapping[str, PhotoRecord],
    photo_metadata_in: Any,
    valid_col_ids: set[str],
    evict_ids: list[str],
) -> dict[str, PhotoRecord]:
    new_photos = dict(existing_photos)
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
                tuple(dict.fromkeys(str(c).strip() for c in raw_tags if str(c).strip() in valid_col_ids))
                if isinstance(raw_tags, list)
                else tuple(c for c in rec.collections if c in valid_col_ids)
            )
            if crop != rec.crop:
                evict_ids.append(pid)
            new_photos[pid] = PhotoRecord(
                id=rec.id,
                filename=rec.filename,
                name=clean_display_name(meta.get("name"), rec.name, MAX_PHOTO_NAME_LEN),
                width=rec.width,
                height=rec.height,
                crop=crop,
                collections=tags,
                content_sha256=rec.content_sha256,
                source_kind=rec.source_kind,
                media_source_path=rec.media_source_path,
                added_at=rec.added_at,
            )
        return new_photos

    for pid, rec in list(new_photos.items()):
        filtered_tags = tuple(c for c in rec.collections if c in valid_col_ids)
        if filtered_tags != rec.collections:
            new_photos[pid] = _replace_photo_collections(rec, filtered_tags)
    return new_photos


def restore_photo_library_metadata(
    hass: HomeAssistant,
    collections_in: Any,
    photo_metadata_in: Any,
    preset_collections_in: Any = None,
) -> None:
    """Restore collections and photo/preset metadata onto existing library originals (executor)."""
    root = get_wallpaper_root(hass)
    evict_ids: list[str] = []

    with LIBRARY_LOCK:
        snap = ensure_loaded_locked(root)
        if isinstance(collections_in, list):
            new_cols_list, valid_col_ids, _ = _parse_raw_collections(collections_in)
        else:
            new_cols_list = list(snap.collections)
            valid_col_ids = {c.id for c in new_cols_list}

        new_photos = _restore_photo_records(
            snap.photos, photo_metadata_in, valid_col_ids, evict_ids
        )
        if isinstance(preset_collections_in, Mapping):
            new_pcols, _ = _parse_preset_collections(preset_collections_in, valid_col_ids)
        else:
            new_pcols = {
                pid: filtered
                for pid, cols in snap.preset_collections.items()
                if (filtered := tuple(c for c in cols if c in valid_col_ids))
            }

        commit_snapshot_locked(
            root,
            PhotoLibrarySnapshot(
                collections=tuple(new_cols_list),
                photos=MappingProxyType(new_photos),
                photo_order=snap.photo_order,
                preset_collections=MappingProxyType(new_pcols),
            ),
        )

    for pid in evict_ids:
        evict_wallpaper_lru_cache(pid)


register_crop_hash_resolver(
    lambda src: get_photo_crop_hash(src) if parse_photo_source(src) else ""
)
