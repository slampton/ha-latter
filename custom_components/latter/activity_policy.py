"""Home Activity Card: a Device's `activity_card` switch and its `activity_sources` setting.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
Protocol v3 carries them as `area_context.activity_card` (bool) and `area_context.activity_sources`
(csv of the sources that are on, in canonical order). The defaults are `defaults.activity_card` and
`defaults.activity_sources` in protocol_v3.json (const.DEFAULT_ACTIVITY_*, checked by the tests).
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
    """Return (activity_card, activity_sources) for Protocol v3.

    The card is sent as off when it's switched off or every source is off, so the device never gets an
    "on" card with an empty source list (an empty field means "not set" under the absent_value rule).
    """
    clean = normalize_activity_sources(sources)
    return (1 if card_on and clean else 0), clean
