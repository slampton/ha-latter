"""Uploaded-wallpaper references and private storage paths for Latter.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
Uploads live in Latter's private storage, `<config>/.storage/latter/wallpapers/<device_slug>/`,
which Home Assistant never serves. They are referenced as `upload:<device_slug>/<file>` and served
only through the signed, expiring Latter wallpaper view. Earlier versions stored uploads under
`<config>/www/latter_wallpapers/<device_slug>/` (served unauthenticated at `/local/`); startup moves
those files and rewrites the stored references.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
import re
import shutil
from typing import Any

UPLOAD_PREFIX = "upload:"
PRIVATE_DIR_PARTS: tuple[str, ...] = (".storage", "latter", "wallpapers")
PUBLIC_DIR_PARTS: tuple[str, ...] = ("www", "latter_wallpapers")
PUBLIC_URL_PREFIX = "/local/latter_wallpapers/"
IMAGE_SUFFIXES: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp")

_SLUG = re.compile(r"^[a-z0-9_]+$")
_FILE = re.compile(r"^[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)$", re.IGNORECASE)


def private_root(config_dir: Path | str) -> Path:
    """Return Latter's private wallpaper root under the Home Assistant config directory."""
    return Path(config_dir).joinpath(*PRIVATE_DIR_PARTS)


def public_root(config_dir: Path | str) -> Path:
    """Return the old, publicly served wallpaper root (`<config>/www/latter_wallpapers`)."""
    return Path(config_dir).joinpath(*PUBLIC_DIR_PARTS)


def make_upload_source(device_slug: str, filename: str) -> str:
    """Return the `upload:<slug>/<file>` reference for an uploaded file."""
    if not _SLUG.match(device_slug) or not _FILE.match(filename):
        raise ValueError(f"Invalid wallpaper reference parts: {device_slug!r}, {filename!r}")
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


def migrate_public_source(source: str) -> str:
    """Rewrite an old `/local/latter_wallpapers/<slug>/<file>` reference to `upload:<slug>/<file>`."""
    if not source.startswith(PUBLIC_URL_PREFIX):
        return source
    slug, sep, filename = source[len(PUBLIC_URL_PREFIX) :].partition("/")
    if sep and _SLUG.match(slug) and _FILE.match(filename):
        return f"{UPLOAD_PREFIX}{slug}/{filename}"
    return source


def migrate_wallpaper_settings(data: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return a copy of `data` with wallpaper references rewritten, or None when nothing changed."""
    changed = False
    out = dict(data)
    src = data.get("wallpaper_source")
    if isinstance(src, str) and (new_src := migrate_public_source(src)) != src:
        out["wallpaper_source"] = new_src
        changed = True
    favs = data.get("wallpaper_favorites")
    if isinstance(favs, list):
        new_favs = [migrate_public_source(f) if isinstance(f, str) else f for f in favs]
        if new_favs != favs:
            out["wallpaper_favorites"] = new_favs
            changed = True
    return out if changed else None


def migrate_profiles(profiles: Iterable[Any]) -> list[Any] | None:
    """Return saved profiles with their wallpaper references rewritten, or None when nothing changed."""
    changed = False
    out: list[Any] = []
    for prof in profiles:
        if isinstance(prof, Mapping) and isinstance(prof.get("device_config"), Mapping):
            new_cfg = migrate_wallpaper_settings(prof["device_config"])
            if new_cfg is not None:
                prof = {**prof, "device_config": new_cfg}
                changed = True
        out.append(prof)
    return out if changed else None


def move_public_uploads(config_dir: Path | str) -> int:
    """Move uploads from `<config>/www/latter_wallpapers/` to private storage; return the number moved.

    Runs in an executor. A file already present in private storage is kept and the public copy
    removed. Emptied public directories are deleted.
    """
    src_root = public_root(config_dir)
    if not src_root.is_dir():
        return 0
    dst_root = private_root(config_dir)
    moved = 0
    for slug_dir in sorted(p for p in src_root.iterdir() if p.is_dir()):
        if not _SLUG.match(slug_dir.name):
            continue
        for file_path in sorted(p for p in slug_dir.iterdir() if p.is_file()):
            if file_path.suffix.lower() not in IMAGE_SUFFIXES or not _FILE.match(file_path.name):
                continue
            target = dst_root / slug_dir.name / file_path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                file_path.unlink()
            else:
                shutil.move(str(file_path), str(target))
                moved += 1
        if not any(slug_dir.iterdir()):
            slug_dir.rmdir()
    if not any(src_root.iterdir()):
        src_root.rmdir()
    return moved
