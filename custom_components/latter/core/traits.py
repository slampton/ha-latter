"""Device traits from the hardware manifest a Latter device reports.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
Behaviour that depends on what kind of hardware a Device is reads these traits, never a
profile name.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def manifest_flag(manifest: Mapping[str, Any], key: str) -> int | None:
    """Return an integer hardware-manifest trait, or None when it is missing or malformed."""
    if key not in manifest:
        return None
    try:
        return int(manifest[key])
    except (TypeError, ValueError):
        return None


def manifest_is_roaming(manifest: Mapping[str, Any]) -> bool:
    """Return True for roaming hardware: `stationary == 0`, or `wearable == 1`. Unknown traits are not roaming."""
    return (
        manifest_flag(manifest, "stationary") == 0
        or manifest_flag(manifest, "wearable") == 1
    )


def manifest_is_wearable(manifest: Mapping[str, Any]) -> bool:
    """Return True only when the manifest reports `wearable == 1`."""
    return manifest_flag(manifest, "wearable") == 1


def manifest_has_display(manifest: Mapping[str, Any]) -> bool:
    """Return False only when the manifest reports `display == 0` (a headless node)."""
    return manifest_flag(manifest, "display") != 0
