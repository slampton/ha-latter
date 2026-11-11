"""Home Activity Card: a Device's `activity_card` switch and its `activity_sources` setting.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
"""

from __future__ import annotations

from typing import Any

# Canonical order; Studio shows one switch per source in this order.
ACTIVITY_SOURCE_KEYS: tuple[str, ...] = ("calendar", "music_queue", "stopwatch", "alarms", "timers")


def normalize_activity_sources(value: Any) -> str:
    """Return the sources as canonical CSV ("" = every source off); raise ValueError for an unknown key."""
    raw = value if isinstance(value, (list, tuple)) else str(value or "").split(",")
    names = {str(t).strip().lower() for t in raw if str(t).strip()}
    unknown = sorted(names - set(ACTIVITY_SOURCE_KEYS))
    if unknown:
        raise ValueError(f"Unknown Activity Card source: {', '.join(unknown)}")
    return ",".join(k for k in ACTIVITY_SOURCE_KEYS if k in names)


def activity_payload(card_on: bool, sources: str) -> tuple[int, str]:
    """Return (activity_card, activity_sources) for Protocol v3."""
    clean = normalize_activity_sources(sources)
    return (1 if card_on and clean else 0), clean
