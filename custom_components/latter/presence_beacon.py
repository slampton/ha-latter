"""Presence beacon policy: when Latter turns a Device's "Area: BLE Presence Beacon" switch on or off.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
The firmware ships the beacon off (a new or reset device doesn't advertise until presence is
set up), so Latter turns it on for Devices that use its native BLE Area tracking.
"""

from __future__ import annotations

from typing import Literal

Trigger = Literal["hello", "options"]
BeaconAction = Literal["turn_on", "turn_off"]


def decide_beacon_action(
    tracking_enabled: bool, switch_state: str | None, trigger: Trigger
) -> BeaconAction | None:
    """Return the switch action to take, or None.

    - `switch_state` is the beacon switch's state: "on", "off", or None when the switch is
      missing, unavailable or unknown (then Latter never acts).
    - On a device_hello (every boot, including after a reset) Latter only turns the beacon on
      for a tracked Device; it never turns it off.
    - After options are applied (Studio, options flow, onboarding, reset) the beacon mirrors the
      Device's native BLE tracking option.
    """
    if switch_state not in ("on", "off"):
        return None
    if tracking_enabled:
        return "turn_on" if switch_state == "off" else None
    if trigger == "options" and switch_state == "on":
        return "turn_off"
    return None
