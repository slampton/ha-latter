"""Latter Studio settings scopes: what a System save and a Device save may write.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
A System save writes only System settings (`.storage/latter.site`); a Device save writes only that
Device's settings (its config subentry). Each rejects keys from the other scope, so one can never
overwrite the other. Settings managed by their own Studio commands (BLE offsets, fusion, groups,
profiles, wallpapers, remote group assignment) are not part of either save.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

# Must name GLOBAL_CONFIG_KEYS values in const.py (checked by tests/test_studio.py).
SYSTEM_ENTITY_KEYS: tuple[str, ...] = (
    "weather_entity",
    "alarm_entity",
    "thermostat_entity",
    "lock_entity",
    "garage_entity",
    "vacuum_entity",
)
SYSTEM_SETTING_KEYS: tuple[str, ...] = (
    *SYSTEM_ENTITY_KEYS,
    "camera_entities",
    "remotes_list",
    "remote_groups",
    "volume_overrides",
    "calendar_entities",
    "custom_palettes",
    "doorbell_noise_reduction",
)

# Device subentry keys a Device save may write.
DEVICE_TEXT_KEYS: tuple[str, ...] = (
    "device_group",
    "default_speaker",
    "ma_player_entity",
    "default_area",
    "ble_beacon_uuid",
    "ble_target_address",
    "presence_entity",
    "assigned_person",
    "dock_apps",
)
DEVICE_BOOL_KEYS: tuple[str, ...] = (
    "native_ble_tracking",
    "ble_auto_switch",
    "sync_device_area",
    "area_handoff",
)
DEVICE_SETTING_KEYS: tuple[str, ...] = (
    *DEVICE_TEXT_KEYS,
    *DEVICE_BOOL_KEYS,
    "default_page_size",
    "wallpaper_cycle_minutes",
    "device_custom_color",
    "area_follow_dwell_s",
)

MAX_LIST_ITEMS = 10
MAX_CALENDARS = 50
MAX_CUSTOM_PALETTES = 24
# Voice Follows Me: how long a BLE-detected Area must stay stable before the Device moves (seconds).
DWELL_MIN_S = 3
DWELL_MAX_S = 60
DEFAULT_DWELL_S = 10
NOISE_REDUCTION_LEVELS: tuple[str, ...] = ("strong", "light", "off")
DEFAULT_NOISE_REDUCTION = "strong"
_HEX_COLOR = re.compile(r"^#[0-9A-F]{6}$")


class SettingsScopeError(ValueError):
    """A save named keys outside its scope, or a value that isn't valid."""


def _check_scope(incoming: Mapping[str, Any], allowed: tuple[str, ...], scope: str) -> None:
    unknown = sorted(str(k) for k in incoming if k not in allowed)
    if unknown:
        raise SettingsScopeError(
            f"{scope} settings don't include: {', '.join(unknown)}"
        )


def _text(val: Any) -> str:
    return str(val or "").strip()


def _entity_list(val: Any, limit: int = MAX_LIST_ITEMS) -> list[str]:
    if not isinstance(val, (list, tuple)):
        return []
    out: list[str] = []
    for item in val:
        ent = _text(item)
        if ent and ent not in out:
            out.append(ent)
    return out[:limit]


def _volume_overrides(val: Any) -> list[dict[str, str]]:
    if not isinstance(val, (list, tuple)):
        return []
    out: list[dict[str, str]] = []
    for item in val:
        if isinstance(item, Mapping):
            spk, tgt = _text(item.get("speaker")), _text(item.get("target"))
            if spk and tgt:
                out.append({"speaker": spk, "target": tgt})
    return out[:MAX_LIST_ITEMS]


def _remote_groups(val: Any) -> list[dict[str, Any]]:
    if not isinstance(val, (list, tuple)):
        return []
    out: list[dict[str, Any]] = []
    for item in val:
        if not isinstance(item, Mapping):
            continue
        gid = _text(item.get("id"))
        if not gid:
            continue
        out.append(
            {
                "id": gid,
                "name": _text(item.get("name")) or gid,
                "area_id": _text(item.get("area_id")),
                "remotes": _entity_list(item.get("remotes")),
            }
        )
    return out


def _custom_palettes(val: Any) -> list[dict[str, str]]:
    if not isinstance(val, (list, tuple)):
        return []
    out: list[dict[str, str]] = []
    for item in val:
        if not isinstance(item, Mapping):
            continue
        hex_val = _text(item.get("hex")).upper()
        if _HEX_COLOR.match(hex_val) and all(p["hex"] != hex_val for p in out):
            out.append({"name": _text(item.get("name")) or hex_val, "hex": hex_val})
    return out[:MAX_CUSTOM_PALETTES]


def _noise_reduction(val: Any) -> str:
    level = _text(val).lower()
    return level if level in NOISE_REDUCTION_LEVELS else DEFAULT_NOISE_REDUCTION


def clean_dwell_s(val: Any) -> int:
    """Return a Voice Follows Me dwell in whole seconds, clamped to 3-60 (the default for a non-number)."""
    try:
        return max(DWELL_MIN_S, min(DWELL_MAX_S, int(float(val))))
    except (TypeError, ValueError):
        return DEFAULT_DWELL_S


FUSION_MODES: tuple[str, ...] = ("weighted", "any_or", "ble_only", "ble_and_sensor")
FUSION_THRESHOLD_MIN = 20
FUSION_THRESHOLD_MAX = 95
DEFAULT_FUSION_THRESHOLD = 50


def clean_area_fusion(
    current: Mapping[str, Any], update: Mapping[str, Any], allowed_sensors: set[str]
) -> dict[str, Any]:
    """Return one Area's fusion settings after a Studio change (`area_fusion_config[<area_id>]`).

    `update` may name `mode`, `threshold_pct` (20-95 %, used by the weighted mode) and `sensors` (the
    Area's sensors that count; an empty list means all of them). Every sensor must be one the Area
    actually has (`allowed_sensors`, discovered server-side); anything else is rejected.
    """
    out: dict[str, Any] = {k: current[k] for k in ("mode", "threshold_pct", "sensors") if k in current}
    if "mode" in update:
        mode = _text(update["mode"]).lower()
        if mode not in FUSION_MODES:
            raise SettingsScopeError(f"Unknown fusion mode: {mode or '(empty)'}")
        out["mode"] = mode
    if "threshold_pct" in update:
        try:
            pct = int(update["threshold_pct"])
        except (TypeError, ValueError):
            raise SettingsScopeError("The occupancy threshold must be a whole percent") from None
        out["threshold_pct"] = max(FUSION_THRESHOLD_MIN, min(FUSION_THRESHOLD_MAX, pct))
    if "sensors" in update:
        if not isinstance(update["sensors"], (list, tuple)):
            raise SettingsScopeError("sensors must be a list of entity IDs")
        sensors: list[str] = []
        for item in update["sensors"]:
            ent = _text(item)
            if ent and ent not in sensors:
                sensors.append(ent)
        unknown = [s for s in sensors if s not in allowed_sensors]
        if unknown:
            raise SettingsScopeError(f"Not a sensor of this Area: {', '.join(unknown)}")
        out["sensors"] = sensors
    return out


def clean_system_settings(incoming: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a System save. The primary camera (`camera_entity`) is derived, never sent."""
    _check_scope(incoming, SYSTEM_SETTING_KEYS, "System")
    out: dict[str, Any] = {}
    for key in SYSTEM_ENTITY_KEYS:
        if key in incoming:
            out[key] = _text(incoming[key])
    if "camera_entities" in incoming:
        cams = _entity_list(incoming["camera_entities"])
        out["camera_entities"] = cams
        out["camera_entity"] = cams[0] if cams else ""
    if "remotes_list" in incoming:
        out["remotes_list"] = _entity_list(incoming["remotes_list"])
    if "calendar_entities" in incoming:
        out["calendar_entities"] = _entity_list(incoming["calendar_entities"], limit=MAX_CALENDARS)
    if "remote_groups" in incoming:
        out["remote_groups"] = _remote_groups(incoming["remote_groups"])
    if "volume_overrides" in incoming:
        out["volume_overrides"] = _volume_overrides(incoming["volume_overrides"])
    if "custom_palettes" in incoming:
        out["custom_palettes"] = _custom_palettes(incoming["custom_palettes"])
    if "doorbell_noise_reduction" in incoming:
        out["doorbell_noise_reduction"] = _noise_reduction(incoming["doorbell_noise_reduction"])
    return out


def clean_device_settings(incoming: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a Device save."""
    _check_scope(incoming, DEVICE_SETTING_KEYS, "Device")
    out: dict[str, Any] = {}
    for key in DEVICE_TEXT_KEYS:
        if key in incoming:
            out[key] = _text(incoming[key])
    for key in DEVICE_BOOL_KEYS:
        if key in incoming:
            out[key] = bool(incoming[key])
    try:
        if "default_page_size" in incoming:
            out["default_page_size"] = max(1, min(20, int(incoming["default_page_size"])))
        if "wallpaper_cycle_minutes" in incoming:
            out["wallpaper_cycle_minutes"] = max(0, int(incoming["wallpaper_cycle_minutes"]))
        if "area_follow_dwell_s" in incoming:
            out["area_follow_dwell_s"] = max(
                DWELL_MIN_S, min(DWELL_MAX_S, int(incoming["area_follow_dwell_s"]))
            )
    except (TypeError, ValueError) as err:
        raise SettingsScopeError(f"Not a whole number: {err}") from None
    if "device_custom_color" in incoming:
        color = _text(incoming["device_custom_color"]).upper()
        if not _HEX_COLOR.match(color):
            raise SettingsScopeError(f"Not a #RRGGBB color: {color or '(empty)'}")
        out["device_custom_color"] = color
    return out


def system_settings_view(global_cfg: Mapping[str, Any]) -> dict[str, Any]:
    """Return the System settings as Studio shows them, read straight from `.storage/latter.site`."""
    cams = _entity_list(global_cfg.get("camera_entities"))
    if not cams and _text(global_cfg.get("camera_entity")):
        cams = [_text(global_cfg.get("camera_entity"))]
    view: dict[str, Any] = {key: _text(global_cfg.get(key)) for key in SYSTEM_ENTITY_KEYS}
    view.update(
        {
            "camera_entities": cams,
            "remotes_list": _entity_list(global_cfg.get("remotes_list")),
            "remote_groups": _remote_groups(global_cfg.get("remote_groups")),
            "volume_overrides": _volume_overrides(global_cfg.get("volume_overrides")),
            "calendar_entities": _entity_list(global_cfg.get("calendar_entities"), limit=MAX_CALENDARS),
            "custom_palettes": _custom_palettes(global_cfg.get("custom_palettes")),
            "doorbell_noise_reduction": _noise_reduction(global_cfg.get("doorbell_noise_reduction")),
        }
    )
    return view


ANNOUNCE_PRIORITIES: tuple[str, ...] = ("normal", "warning", "critical")
# Special targets (targets.py; a test keeps these in sync): every Device, or the Devices in occupied Areas.
NOTIFY_SPECIAL_TARGETS: tuple[str, ...] = ("all", "occupied_areas")
BROADCAST_TARGETS: tuple[str, ...] = ("all", "occupied_areas")


def clean_announcement(body: Mapping[str, Any], device_slugs: set[str]) -> dict[str, Any]:
    """Validate a Studio announcement and return {"service", "data", "include_camera"}.

    `mode` is `notify` (an on-screen alert on Latter Devices: `latter.notify`) or `broadcast` (spoken with
    TTS on speakers: `latter.intercom_broadcast`). The targets are the ones those services accept.
    """
    mode = _text(body.get("mode")).lower()
    target = _text(body.get("target_device"))
    message = _text(body.get("message"))
    if not message:
        raise SettingsScopeError("Enter a message")
    if mode == "notify":
        if target not in device_slugs and target not in NOTIFY_SPECIAL_TARGETS:
            raise SettingsScopeError(f"Not a Latter Device or notify target: {target or '(empty)'}")
        title = _text(body.get("title"))
        if not title:
            raise SettingsScopeError("Enter a title")
        priority = _text(body.get("priority")).lower() or "normal"
        if priority not in ANNOUNCE_PRIORITIES:
            raise SettingsScopeError(f"Unknown priority: {priority}")
        return {
            "service": "notify",
            "data": {"target_device": target, "title": title, "message": message, "priority": priority, "chime": True},
            "include_camera": bool(body.get("include_camera")),
        }
    if mode == "broadcast":
        if target not in BROADCAST_TARGETS:
            raise SettingsScopeError(f"Broadcast goes to every speaker or to occupied Areas, not {target or '(empty)'}")
        data: dict[str, Any] = {"message": message}
        if target == "occupied_areas":
            data["target_device"] = "occupied_areas"
        return {"service": "intercom_broadcast", "data": data, "include_camera": False}
    raise SettingsScopeError(f"Unknown announcement mode: {mode or '(empty)'}")
