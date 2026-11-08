"""Special values for ``target_device`` in ``latter.notify`` and ``latter.intercom_broadcast``.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
Any other ``target_device`` value names one Latter Device and must resolve, or the service
call fails with ``unknown_target``.
"""

from __future__ import annotations

from typing import Any, Literal

TARGET_ALL = "all"
TARGET_OCCUPIED_AREAS = "occupied_areas"
PERSON_PREFIX = "person."

TargetKind = Literal["none", "all", "occupied_areas", "person", "device"]


def target_kind(value: Any) -> TargetKind:
    """Classify a ``target_device`` value.

    ``all`` and ``occupied_areas`` match case-insensitively; ``person.<id>`` is a person entity.
    Everything else is a Device reference (slug, subentry ID or Home Assistant device ID).
    """
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
