"""Pure-stdlib Repairs issue ID builders and device-hello health evaluator (`L0a`)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

# ---------------------------------------------------------------------------
# Per-Device Repair Issue IDs
# ---------------------------------------------------------------------------

ISSUE_CRASHED: Final = "device_crashed"
ISSUE_BROWNOUT: Final = "device_brownout"
ISSUE_ROLLED_BACK: Final = "firmware_rolled_back"

DEVICE_HEALTH_ISSUE_KINDS: Final[tuple[str, ...]] = (
    ISSUE_CRASHED,
    ISSUE_BROWNOUT,
    ISSUE_ROLLED_BACK,
)

DEVICE_ISSUE_KINDS: Final[tuple[str, ...]] = (
    "link_ma_player",
    "missing_mapped_entity",
    "ble_no_proxies",
    "slot_push_failing",
    *DEVICE_HEALTH_ISSUE_KINDS,
)

CRASH_RESETS: Final[frozenset[str]] = frozenset(
    {"panic", "int-wdt", "task-wdt", "wdt", "stall"}
)
BROWNOUT_RESET: Final = "brownout"
CLEAN_RESETS: Final[frozenset[str]] = frozenset(
    {"power-on", "external", "software", "deep-sleep", "usb"}
)


def link_ma_player_issue_id(subentry_id: str) -> str:
    """Issue: the Device's speaker has no Music Assistant counterpart."""
    return f"link_ma_player_{subentry_id}"


def missing_mapped_entity_issue_id(subentry_id: str) -> str:
    """Issue: an entity mapped for the Device no longer exists."""
    return f"missing_mapped_entity_{subentry_id}"


def ble_no_proxies_issue_id(subentry_id: str) -> str:
    """Issue: BLE Area tracking is on but no Area-assigned Bluetooth proxy exists."""
    return f"ble_no_proxies_{subentry_id}"


def slot_push_failing_issue_id(subentry_id: str) -> str:
    """Issue: pushing browse/Area slots to the Device keeps failing."""
    return f"slot_push_failing_{subentry_id}"


def device_health_issue_id(kind: str, subentry_id: str) -> str:
    """Issue: a device health problem (`device_crashed`, `device_brownout`, `firmware_rolled_back`)."""
    return f"{kind}_{subentry_id}"


def device_issue_ids(subentry_id: str) -> list[str]:
    """Return every repair issue ID that can exist for one Device."""
    return [
        link_ma_player_issue_id(subentry_id),
        missing_mapped_entity_issue_id(subentry_id),
        ble_no_proxies_issue_id(subentry_id),
        slot_push_failing_issue_id(subentry_id),
        *(device_health_issue_id(kind, subentry_id) for kind in DEVICE_HEALTH_ISSUE_KINDS),
    ]


def parse_device_issue_id(
    issue_id: str, subentry_ids: set[str]
) -> tuple[str, str] | None:
    """Return `(kind, subentry_id)` for a per-Device issue of a known Device, else `None`."""
    for kind in DEVICE_ISSUE_KINDS:
        prefix = f"{kind}_"
        if issue_id.startswith(prefix) and issue_id[len(prefix) :] in subentry_ids:
            return kind, issue_id[len(prefix) :]
    return None


# ---------------------------------------------------------------------------
# Device Health Evaluation (`device_hello` Manifest)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeviceHealth:
    """Health fields of one `device_hello` manifest (`None` when the firmware didn't report them)."""

    sdk: int | None
    reset: str | None
    crash: bool | None
    rollback: bool | None


@dataclass(frozen=True, slots=True)
class HealthActions:
    """Repairs to raise (`issue_kind -> extra_placeholders`) and to delete (`issue_kinds`)."""

    raise_issues: dict[str, dict[str, str]] = field(default_factory=dict)
    delete_issues: frozenset[str] = frozenset()


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, (float, str)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def parse_device_health(manifest: Mapping[str, object] | None) -> DeviceHealth:
    """Extract the health fields from a `device_hello` manifest."""
    m = manifest or {}
    raw_reset = m.get("reset")
    reset = (
        str(raw_reset).strip().lower()
        if raw_reset not in (None, "")
        else None
    )
    crash = _int_or_none(m.get("crash"))
    rollback = _int_or_none(m.get("rollback"))
    return DeviceHealth(
        sdk=_int_or_none(m.get("sdk")),
        reset=reset,
        crash=None if crash is None else crash == 1,
        rollback=None if rollback is None else rollback == 1,
    )


def evaluate_device_health(health: DeviceHealth) -> HealthActions:
    """Decide which health repairs one boot's hello raises or clears."""
    raise_issues: dict[str, dict[str, str]] = {}
    delete: set[str] = set()
    sdk = str(health.sdk) if health.sdk is not None else "unknown"

    if health.reset in CRASH_RESETS or health.crash is True:
        reason = (
            health.reset
            if health.reset in CRASH_RESETS
            else (health.reset or "crash")
        )
        raise_issues[ISSUE_CRASHED] = {"reason": reason, "sdk": sdk}
        if health.reset == BROWNOUT_RESET:
            raise_issues[ISSUE_BROWNOUT] = {"sdk": sdk}
    elif health.reset == BROWNOUT_RESET:
        raise_issues[ISSUE_BROWNOUT] = {"sdk": sdk}
    elif health.reset in CLEAN_RESETS:
        delete.update({ISSUE_CRASHED, ISSUE_BROWNOUT})

    if health.rollback is True:
        raise_issues[ISSUE_ROLLED_BACK] = {"sdk": sdk}
    elif health.rollback is False:
        delete.add(ISSUE_ROLLED_BACK)

    return HealthActions(raise_issues=raise_issues, delete_issues=frozenset(delete))
