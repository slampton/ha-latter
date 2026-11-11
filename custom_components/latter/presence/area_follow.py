"""Voice Follows Me dwell gate and BLE presence beacon policy.

Standard library only (no Home Assistant imports). Which Devices may follow is
`core.traits.manifest_is_roaming` (`stationary == 0` / `wearable == 1` only).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

NON_AREA_STATES: frozenset[str] = frozenset(
    {"", "unknown", "unavailable", "none", "away", "not_home"}
)
_CLOCK_TOLERANCE_S = 0.25

Trigger = Literal["hello", "options"]
BeaconAction = Literal["turn_on", "turn_off"]


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
        """Register an Area update and return what to do now."""
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


def decide_beacon_action(
    tracking_enabled: bool, switch_state: str | None, trigger: Trigger
) -> BeaconAction | None:
    """Return the BLE presence beacon switch action to take (`turn_on` / `turn_off`), or None."""
    if switch_state not in ("on", "off"):
        return None
    if tracking_enabled:
        return "turn_on" if switch_state == "off" else None
    if trigger == "options" and switch_state == "on":
        return "turn_off"
    return None
