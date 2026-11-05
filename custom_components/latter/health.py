"""Device health from the device_hello manifest: crash, brownout and firmware-rollback repairs.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
The firmware reports, per boot:

- `sdk`: LATTER_SDK_REV of the running build.
- `reset`: the reset reason (power-on, external, software, panic, int-wdt, task-wdt, wdt,
  deep-sleep, brownout, unknown).
- `crash`: 1 while ESPHome's crash handler holds a crash record (its decoded backtrace is
  logged to every log client until the device restarts).
- `rollback`: 1 while the running firmware is the one that replaced an update that failed to
  boot (stays 1 until a successful OTA).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

CRASH_RESETS: frozenset[str] = frozenset({"panic", "int-wdt", "task-wdt", "wdt"})
BROWNOUT_RESET = "brownout"
CLEAN_RESETS: frozenset[str] = frozenset({"power-on", "external", "software", "deep-sleep"})

ISSUE_CRASHED = "device_crashed"
ISSUE_BROWNOUT = "device_brownout"
ISSUE_ROLLED_BACK = "firmware_rolled_back"


@dataclass(frozen=True)
class DeviceHealth:
    """Health fields of one device_hello manifest (None when the firmware didn't report them)."""

    sdk: int | None
    reset: str | None
    crash: bool | None
    rollback: bool | None


@dataclass(frozen=True)
class HealthActions:
    """Repairs to raise (issue kind -> extra placeholders) and to delete (issue kinds)."""

    raise_issues: dict[str, dict[str, str]] = field(default_factory=dict)
    delete_issues: frozenset[str] = frozenset()


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_device_health(manifest: Mapping[str, Any] | None) -> DeviceHealth:
    """Extract the health fields from a device_hello manifest."""
    m = manifest or {}
    reset = str(m["reset"]).strip().lower() if m.get("reset") not in (None, "") else None
    crash = _int_or_none(m.get("crash"))
    rollback = _int_or_none(m.get("rollback"))
    return DeviceHealth(
        sdk=_int_or_none(m.get("sdk")),
        reset=reset,
        crash=None if crash is None else crash == 1,
        rollback=None if rollback is None else rollback == 1,
    )


def evaluate_device_health(health: DeviceHealth) -> HealthActions:
    """Decide which health repairs one boot's hello raises or clears.

    - A crash reset (panic or any watchdog) raises `device_crashed`; a brownout raises
      `device_brownout`. A clean reset (power-on, external, software, deep-sleep) clears both.
      `unknown` or a missing reason leaves both as they are.
    - `rollback == 1` raises `firmware_rolled_back`; `rollback == 0` clears it.
    """
    raise_issues: dict[str, dict[str, str]] = {}
    delete: set[str] = set()
    sdk = str(health.sdk) if health.sdk is not None else "unknown"

    if health.reset in CRASH_RESETS:
        raise_issues[ISSUE_CRASHED] = {"reason": health.reset, "sdk": sdk}
    elif health.reset == BROWNOUT_RESET:
        raise_issues[ISSUE_BROWNOUT] = {"sdk": sdk}
    elif health.reset in CLEAN_RESETS:
        delete.update({ISSUE_CRASHED, ISSUE_BROWNOUT})

    if health.rollback is True:
        raise_issues[ISSUE_ROLLED_BACK] = {"sdk": sdk}
    elif health.rollback is False:
        delete.add(ISSUE_ROLLED_BACK)

    return HealthActions(raise_issues=raise_issues, delete_issues=frozenset(delete))
