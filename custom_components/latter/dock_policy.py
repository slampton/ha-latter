"""Home dock policy: the Device's `dock_apps` setting is the one source for its Home dock.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
`dock_apps` (Protocol v3 `area_ctx` field `dock_apps`) lists the dock apps in order. The firmware
uses it for the order, but decides visibility with one "Home: Shortcut <App>" switch per app, and
appends any app whose switch is on even when the list leaves it out. So Latter drives those
switches from `dock_apps` whenever the Device's options are applied and on every device_hello,
like the presence beacon. Cameras have no switch: the firmware shows them only when listed.
"""

from __future__ import annotations

from typing import Literal

DOCK_APP_TOKENS: tuple[str, ...] = (
    "music",
    "alarm",
    "area",
    "remote",
    "camera",
    "games",
    "tools",
)

# Entity ID suffix of each app's "Home: Shortcut <App>" switch on the bound ESPHome device.
DOCK_SWITCH_SUFFIXES: dict[str, str] = {
    "music": "_home_shortcut_music",
    "alarm": "_home_shortcut_alarm",
    "area": "_home_shortcut_area",
    "remote": "_home_shortcut_remote",
    "games": "_home_shortcut_games",
    "tools": "_home_shortcut_tools",
}

SwitchAction = Literal["turn_on", "turn_off"]


def parse_dock_apps(csv: str | None) -> list[str]:
    """Return the known dock apps named in `csv`, in order, without duplicates."""
    out: list[str] = []
    for raw in str(csv or "").replace(";", ",").replace("|", ",").replace(" ", ",").split(","):
        tok = raw.strip().lower()
        if tok in DOCK_APP_TOKENS and tok not in out:
            out.append(tok)
    return out


def normalize_dock_apps(csv: str | None) -> str:
    """Return `csv` as canonical comma-separated dock apps; raise ValueError if it names none or an unknown app."""
    names = [t.strip().lower() for t in str(csv or "").split(",") if t.strip()]
    unknown = sorted({t for t in names if t not in DOCK_APP_TOKENS})
    if unknown:
        raise ValueError(f"Unknown dock app: {', '.join(unknown)}")
    apps = parse_dock_apps(csv)
    if not apps:
        raise ValueError("The Home dock needs at least one app")
    return ",".join(apps)


def dock_switch_action(enabled: bool, switch_state: str | None) -> SwitchAction | None:
    """Return the action that makes an app's Shortcut switch match `enabled`, or None.

    `switch_state` is "on", "off", or None when the switch is missing, unavailable or unknown
    (then Latter doesn't act).
    """
    if switch_state not in ("on", "off"):
        return None
    if enabled and switch_state == "off":
        return "turn_on"
    if not enabled and switch_state == "on":
        return "turn_off"
    return None
