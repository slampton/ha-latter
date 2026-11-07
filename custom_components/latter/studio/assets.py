"""Studio panel asset helpers.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def content_digest(path: Path) -> str:
    """Return a short SHA-256 digest of a file, used as the panel module's cache-buster (executor)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
