"""Symlink-confined Home Assistant `/media` folder browser and lock-free batch importer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
import hashlib
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from .models import (
    IMAGE_SUFFIXES,
    MAX_MEDIA_IMPORT_BATCH,
    MAX_WALLPAPER_UPLOAD_BYTES,
    PhotoCrop,
    PhotoLibrarySnapshot,
    PhotoRecord,
    get_wallpaper_root,
    humanize_filename_stem,
)
from .store import (
    LIBRARY_LOCK,
    commit_snapshot_locked,
    encode_original_jpeg,
    ensure_loaded_locked,
    get_photo_library_snapshot,
    mint_unique_photo_id,
    originals_dir,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

type _PreparedItem = tuple[str, str, Path, str, tuple[bytes, int, int] | None]


def _normalize_media_relpath(relpath: str) -> str | None:
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
    raw_root_dir = (
        media_dirs.get(str(root or "").strip())
        if isinstance(media_dirs, Mapping) and media_dirs
        else None
    )
    norm_rel = _normalize_media_relpath(relpath) if raw_root_dir else None
    if not raw_root_dir or norm_rel is None:
        return None
    try:
        root_dir = Path(raw_root_dir).resolve(strict=True)
        target = (root_dir / norm_rel) if norm_rel else root_dir
        resolved = target.resolve(strict=True)
    except OSError:
        return None
    return resolved if root_dir.is_dir() and resolved.is_relative_to(root_dir) else None


def _discover_valid_media_roots(
    raw_dirs: Mapping[str, str],
) -> tuple[list[dict[str, str]], dict[str, Path]]:
    roots: list[dict[str, str]] = []
    valid_dirs: dict[str, Path] = {}
    for key in sorted(raw_dirs.keys(), key=lambda k: (k != "local", k.lower())):
        try:
            rpath = Path(raw_dirs[key]).resolve(strict=True)
        except OSError:
            continue
        if rpath.is_dir():
            valid_dirs[key] = rpath
            roots.append({"id": str(key), "name": str(key).replace("_", " ").title()})
    return roots, valid_dirs


def _scan_media_directory_entries(
    target_dir: Path,
    root_dir: Path,
    selected_root: str,
    norm_sub: str,
    imported_paths: set[str],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
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
        rel_posix = f"{norm_sub}/{entry.name}" if norm_sub else entry.name
        if resolved.is_dir():
            folders.append({"name": entry.name, "subpath": rel_posix})
        elif resolved.is_file() and entry.suffix.lower() in IMAGE_SUFFIXES:
            try:
                size_bytes = resolved.stat().st_size
            except OSError:
                continue
            if size_bytes > 0:
                images.append(
                    {
                        "name": entry.name,
                        "relpath": rel_posix,
                        "size_bytes": size_bytes,
                        "too_large": size_bytes > MAX_WALLPAPER_UPLOAD_BYTES,
                        "already_imported": f"{selected_root}/{rel_posix}" in imported_paths,
                    }
                )
    return folders, images


def list_media_folder_sync(
    media_dirs: Mapping[str, str] | None,
    root: str = "",
    subpath: str = "",
) -> dict[str, Any]:
    """List subfolders and supported image files strictly confined inside `hass.config.media_dirs`."""
    raw_dirs = media_dirs if isinstance(media_dirs, Mapping) else {}
    roots, valid_dirs = _discover_valid_media_roots(raw_dirs)
    if not valid_dirs:
        return {
            "roots": [],
            "root": "",
            "subpath": "",
            "parent_subpath": None,
            "folders": [],
            "images": [],
        }

    selected_root = str(root or "").strip() or ("local" if "local" in valid_dirs else roots[0]["id"])
    if selected_root not in valid_dirs:
        raise ValueError(f"Unknown media folder root '{selected_root}'")

    norm_sub = _normalize_media_relpath(subpath)
    if norm_sub is None:
        raise ValueError("Invalid media folder subpath")

    target_dir = resolve_media_path(raw_dirs, selected_root, norm_sub)
    if target_dir is None or not target_dir.is_dir():
        raise ValueError("Media folder does not exist or is outside allowed media directory")

    snap = get_photo_library_snapshot()
    imported_paths = {rec.media_source_path for rec in snap.photos.values() if rec.media_source_path}
    folders, images = _scan_media_directory_entries(
        target_dir, valid_dirs[selected_root], selected_root, norm_sub, imported_paths
    )
    parent_subpath: str | None = (
        (norm_sub.rsplit("/", 1)[0] if "/" in norm_sub else "") if norm_sub else None
    )
    return {
        "roots": roots,
        "root": selected_root,
        "subpath": norm_sub,
        "parent_subpath": parent_subpath,
        "folders": folders,
        "images": images,
    }


def _validate_media_import_source(
    media_dirs: Mapping[str, str], root_key: str, relpath: str
) -> tuple[tuple[str, Path, bytes] | None, str | None]:
    norm_rel = _normalize_media_relpath(relpath)
    resolved = resolve_media_path(media_dirs, root_key, norm_rel) if norm_rel else None
    if not norm_rel or resolved is None or not resolved.is_file():
        return None, "Invalid media path" if not norm_rel else "File not found or outside media root"
    if resolved.suffix.lower() not in IMAGE_SUFFIXES:
        return None, "Unsupported image format"
    try:
        size_bytes = resolved.stat().st_size
        if size_bytes <= 0 or size_bytes > MAX_WALLPAPER_UPLOAD_BYTES:
            return None, "Empty file" if size_bytes <= 0 else "File exceeds 15 MB limit"
        return (norm_rel, resolved, resolved.read_bytes()), None
    except OSError as err:
        return None, str(err)


def _prepare_single_media_item(
    media_dirs: Mapping[str, str],
    root_key: str,
    relpath: str,
    dedup_state: tuple[bool, set[str], set[str]],
) -> tuple[_PreparedItem | None, str | None]:
    deduplicate, initial_shas, batch_seen_sha = dedup_state
    validated, err_msg = _validate_media_import_source(media_dirs, root_key, relpath)
    if validated is None:
        return None, err_msg
    norm_rel, resolved, raw_bytes = validated
    content_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    if deduplicate and (content_sha256 in initial_shas or content_sha256 in batch_seen_sha):
        return (relpath, norm_rel, resolved, content_sha256, None), None

    try:
        encoded_triplet = encode_original_jpeg(raw_bytes)
    except Exception as err:  # noqa: BLE001
        return None, f"Invalid image: {err}"
    if deduplicate:
        batch_seen_sha.add(content_sha256)
    return (relpath, norm_rel, resolved, content_sha256, encoded_triplet), None


def _commit_prepared_media_batch(
    wp_root: Path,
    root_key: str,
    cid: str,
    deduplicate: bool,
    prepared_items: list[_PreparedItem],
) -> tuple[int, int, list[dict[str, str]], list[dict[str, Any]]]:
    orig_dir = originals_dir(wp_root)
    imported = 0
    skipped = 0
    commit_failures: list[dict[str, str]] = []
    created_photos: list[dict[str, Any]] = []

    with LIBRARY_LOCK:
        snap = ensure_loaded_locked(wp_root)
        if cid and cid not in {c.id for c in snap.collections}:
            raise ValueError(f"Unknown collection '{cid}'")
        new_photos = dict(snap.photos)
        new_order = list(snap.photo_order)
        sha_to_pid = {rec.content_sha256: pid for pid, rec in new_photos.items() if rec.content_sha256}
        mutated = False

        for relpath, norm_rel, resolved, content_sha256, opt_triplet in prepared_items:
            existing_pid = sha_to_pid.get(content_sha256) if deduplicate else None
            if existing_pid is not None and existing_pid in new_photos:
                skipped += 1
                ex_rec = new_photos[existing_pid]
                if cid and cid not in ex_rec.collections:
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

            if opt_triplet is None:
                try:
                    triplet = encode_original_jpeg(resolved.read_bytes())
                except Exception as err:  # noqa: BLE001
                    commit_failures.append({"path": relpath, "error": f"Invalid image: {err}"})
                    continue
            else:
                triplet = opt_triplet

            jpeg_bytes, width, height = triplet
            photo_id, out_name = mint_unique_photo_id(resolved.stem, new_photos)
            (orig_dir / out_name).write_bytes(jpeg_bytes)
            rec = PhotoRecord(
                id=photo_id,
                filename=out_name,
                name=humanize_filename_stem(resolved.name),
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
            commit_snapshot_locked(
                wp_root,
                PhotoLibrarySnapshot(
                    snap.collections,
                    MappingProxyType(new_photos),
                    tuple(new_order),
                    snap.preset_collections,
                ),
            )
    return imported, skipped, commit_failures, created_photos


def import_media_photos_sync(
    hass: HomeAssistant,
    media_dirs: Mapping[str, str] | None,
    root: str,
    paths: Sequence[str],
    collection_id: str | None = None,
    deduplicate: bool = True,
) -> dict[str, Any]:
    """Batch-import images from HA `/media` into the Photo Library with lock-free PIL decode."""
    root_key = str(root or "").strip()
    if not isinstance(media_dirs, Mapping) or root_key not in media_dirs:
        raise ValueError(f"Unknown media folder root '{root_key}'")
    path_list = [str(p or "").strip() for p in (paths or ()) if str(p or "").strip()]
    if not path_list:
        return {"imported": 0, "skipped": 0, "failed": [], "photos": []}
    if len(path_list) > MAX_MEDIA_IMPORT_BATCH:
        raise ValueError(f"Cannot import more than {MAX_MEDIA_IMPORT_BATCH} photos in one batch")

    wp_root = get_wallpaper_root(hass)
    originals_dir(wp_root).mkdir(parents=True, exist_ok=True)
    cid = str(collection_id or "").strip()

    with LIBRARY_LOCK:
        initial_snap = ensure_loaded_locked(wp_root)
        if cid and cid not in {c.id for c in initial_snap.collections}:
            raise ValueError(f"Unknown collection '{cid}'")
        initial_shas = {
            rec.content_sha256 for rec in initial_snap.photos.values() if rec.content_sha256
        }

    failed: list[dict[str, str]] = []
    prepared_items: list[_PreparedItem] = []
    batch_seen_sha: set[str] = set()
    for relpath in path_list:
        item, err_msg = _prepare_single_media_item(
            media_dirs, root_key, relpath, (deduplicate, initial_shas, batch_seen_sha)
        )
        if err_msg is not None:
            failed.append({"path": relpath, "error": err_msg})
        elif item is not None:
            prepared_items.append(item)

    if not prepared_items:
        return {"imported": 0, "skipped": 0, "failed": failed, "photos": []}

    imported, skipped, commit_failures, created_photos = _commit_prepared_media_batch(
        wp_root, root_key, cid, deduplicate, prepared_items
    )
    failed.extend(commit_failures)
    return {
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "photos": created_photos,
    }
