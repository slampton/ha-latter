"""Voice Follows Me policy: which Devices may follow, and the dwell gate for BLE-driven Area moves.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
`area_controller.LatterAreaFollowController` drives `AreaFollowDwell` with Home Assistant timers
and performs the Device Registry write.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Any

# States an Area source can report that are not an Area. They never move a Device and they
# cancel a pending dwell: Latter never clears or changes an Area on away/unknown.
NON_AREA_STATES: frozenset[str] = frozenset(
    {"", "unknown", "unavailable", "none", "away", "not_home"}
)
# Timer callbacks may run a hair before the monotonic deadline they were scheduled for.
_CLOCK_TOLERANCE_S = 0.25


def _manifest_flag(manifest: Mapping[str, Any], key: str) -> int | None:
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
        _manifest_flag(manifest, "stationary") == 0
        or _manifest_flag(manifest, "wearable") == 1
    )


def is_area_id(value: str | None) -> bool:
    """Return True if `value` names an Area rather than an away/unknown placeholder."""
    return bool(value) and str(value).strip().lower() not in NON_AREA_STATES


class FollowAction(Enum):
    """What the controller should do with an Area update request."""

    IGNORE = "ignore"
    COMMIT = "commit"
    DWELL = "dwell"
    PENDING = "pending"


class AreaFollowDwell:
    """Dwell gate: BLE-driven moves must stay stable for `dwell_s`; explicit picks apply at once."""

    def __init__(self) -> None:
        """Start with no pending move."""
        self.pending_area_id: str | None = None
        self.due_at: float | None = None

    def cancel(self) -> None:
        """Drop any pending move."""
        self.pending_area_id = None
        self.due_at = None

    def request(
        self, target_area_id: str | None, *, ble_driven: bool, dwell_s: float, now: float
    ) -> FollowAction:
        """Register an Area update and return what to do now.

        - A non-Area value cancels any pending move (IGNORE).
        - A BLE-driven move to the Area already pending keeps its original deadline (PENDING).
        - Any other BLE-driven move restarts the dwell (DWELL; commit once `take_due` says so).
        - An explicit pick, or a zero dwell, applies immediately (COMMIT).
        """
        if not is_area_id(target_area_id):
            self.cancel()
            return FollowAction.IGNORE
        assert target_area_id is not None
        if ble_driven and dwell_s > 0:
            if self.pending_area_id == target_area_id and self.due_at is not None:
                return FollowAction.PENDING
            self.pending_area_id = target_area_id
            self.due_at = now + float(dwell_s)
            return FollowAction.DWELL
        self.cancel()
        return FollowAction.COMMIT

    def take_due(self, target_area_id: str, now: float) -> bool:
        """Return True, and clear the pending move, if `target_area_id` is still pending and its dwell has elapsed."""
        if (
            self.pending_area_id != target_area_id
            or self.due_at is None
            or now + _CLOCK_TOLERANCE_S < self.due_at
        ):
            return False
        self.cancel()
        return True
