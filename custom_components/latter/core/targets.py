"""Special values for ``target_device`` in ``latter.notify`` and ``latter.intercom_broadcast``.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
Any other ``target_device`` value names one Latter Device and must resolve, or the service
call fails with ``unknown_target``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

TARGET_ALL = "all"
TARGET_OCCUPIED_AREAS = "occupied_areas"
PERSON_PREFIX = "person."

TargetKind = Literal["none", "all", "occupied_areas", "person", "device"]


def target_kind(value: Any) -> TargetKind:
    """Classify a ``target_device`` value."""
    text = str(value or "").strip().lower()
    if not text:
        return "none"
    if text == TARGET_ALL:
        return "all"
    if text == TARGET_OCCUPIED_AREAS:
        return "occupied_areas"
    if text.startswith(PERSON_PREFIX):
        return "person"
    return "device"


def other_latter_devices(candidates: Iterable[Any], caller_slug: str) -> list[Any]:
    """Return the Latter Devices other than the caller: objects with a ``device_slug`` that aren't BLE tags."""
    return [
        c
        for c in candidates
        if getattr(c, "device_slug", None)
        and not getattr(c, "is_ble_tag", False)
        and c.device_slug != caller_slug
    ]


def call_target_slugs(candidates: Iterable[Any], caller_slug: str, target: Any) -> list[str]:
    """Return the slugs ``call_target`` rings: every other Latter Device for ``all`` (or empty), else the named one."""
    others = other_latter_devices(candidates, caller_slug)
    text = str(target or "").strip()
    if text.lower() in ("", TARGET_ALL):
        return [c.device_slug for c in others]
    return [c.device_slug for c in others if c.device_slug == text]
