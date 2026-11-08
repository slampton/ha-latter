"""Uploaded-wallpaper references and private storage paths for Latter.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
Uploads live in Latter's private storage, `<config>/.storage/latter/wallpapers/<device_slug>/`,
which Home Assistant never serves. They are referenced as `upload:<device_slug>/<file>` and served
only through the signed, expiring Latter wallpaper view.
"""

from __future__ import annotations

from pathlib import Path
import re

UPLOAD_PREFIX = "upload:"
PRIVATE_DIR_PARTS: tuple[str, ...] = (".storage", "latter", "wallpapers")
IMAGE_SUFFIXES: tuple[str, ...] = (".jpg", ".jpeg", ".png", ".webp")

_SLUG = re.compile(r"^[a-z0-9_]+$")
_FILE = re.compile(r"^[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)$", re.IGNORECASE)


def private_root(config_dir: Path | str) -> Path:
    """Return Latter's private wallpaper root under the Home Assistant config directory."""
    return Path(config_dir).joinpath(*PRIVATE_DIR_PARTS)


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
