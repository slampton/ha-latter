"""Latter Studio settings scopes, command routing, target checks, and catalog push gate.

Standard library only (no Home Assistant imports), so unit tests exercise this exact code.
A System save writes only System settings (`.storage/latter.site`); a Device save writes only that
Device's settings (its config subentry). The websocket type is the command scope: `latter/system/command`
runs System commands and `latter/device/command` runs Device commands on the Device named by `subentry_id`.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
import re
from typing import Any, Literal, Protocol, TypeVar

# ---------------------------------------------------------------------------
# Catalog Push Gate
# ---------------------------------------------------------------------------


class CatalogGate:
    """Per-subscription flag: does the next live push need the entity catalog?"""

    def __init__(self) -> None:
        """Start clean: the subscription's first answer already carried the catalog."""
        self._dirty = False

    def mark_dirty(self) -> None:
        """A registry changed; the next push carries the catalog."""
        self._dirty = True

    def take(self) -> bool:
        """Return True once after a registry change, then False until the next one."""
        dirty, self._dirty = self._dirty, False
        return dirty


# ---------------------------------------------------------------------------
# Studio Command Scopes & Target Checks
# ---------------------------------------------------------------------------

SYSTEM_COMMANDS: frozenset[str] = frozenset(
    {
        "set_ble_area_offset",
        "set_area_fusion",
        "auto_calibrate_here",
        "system_entity_action",
        "send_announcement",
        "check_system_updates",
        "clear_internal_logs",
        "remove_device",
        "add_ble_device",
        "set_device_remote_group",
        "create_device_group",
        "delete_device_group",
        "sync_device_group",
        "seed_group_baseline",
        "set_group_device_setting",
        "test_doorbell_speaker",
        "delete_system_wallpaper",
        "save_system_config",
        "rotate_signing_key",
        "set_security_pin",
    }
)

DEVICE_COMMANDS: frozenset[str] = frozenset(
    {
        "esphome_entity_action",
        "select_wallpaper",
        "toggle_wallpaper_favorite",
        "delete_wallpaper",
        "save_device_config",
    }
)

DEVICE_ENTITY_VERBS: frozenset[str] = frozenset(
    {"press", "install", "check", "toggle", "turn_on", "turn_off"}
)
SYSTEM_ENTITY_VERBS: frozenset[str] = frozenset({"turn_on", "turn_off"})

Scope = Literal["system", "device"]


class _HasSubentryId(Protocol):
    subentry_id: str


T = TypeVar("T", bound=_HasSubentryId)


class UnknownStudioCommand(KeyError):
    """The Studio sent a command this integration doesn't implement."""


class TargetNotAllowed(ValueError):
    """A Studio entity action named an entity or verb outside what the command may touch."""


def command_scope(cmd: str) -> Scope:
    """Return the scope (`system` or `device`) whose websocket type runs `cmd`."""
    if cmd in DEVICE_COMMANDS:
        return "device"
    if cmd in SYSTEM_COMMANDS:
        return "system"
    raise UnknownStudioCommand(cmd)


def find_by_subentry_id[T: _HasSubentryId](
    items: Iterable[T], subentry_id: str | None
) -> T | None:
    """Return the item whose `subentry_id` equals `subentry_id` exactly, else None (no other matching)."""
    target = str(subentry_id or "").strip()
    if not target:
        return None
    return next((item for item in items if item.subentry_id == target), None)


def allowed_entity_targets(
    requested: Iterable[Any], allowed: Collection[str], what: str
) -> list[str]:
    """Return the requested entity IDs if every one of them is in `allowed`, else raise TargetNotAllowed."""
    ids: list[str] = []
    for item in requested:
        ent = str(item or "").strip()
        if ent and ent not in ids:
            ids.append(ent)
    if not ids:
        raise TargetNotAllowed("No entity given")
    rejected = [ent for ent in ids if ent not in allowed]
    if rejected:
        raise TargetNotAllowed(f"Not {what}: {', '.join(rejected)}")
    return ids


def checked_entity_verb(body: Mapping[str, Any], verbs: Collection[str]) -> str:
    """Return the action verb of an entity action; an option or level needs no verb, anything else must be in `verbs`."""
    action = str(body.get("action") or "").strip().lower()
    if body.get("option") is not None or body.get("level") is not None:
        return action
    if action not in verbs:
        raise TargetNotAllowed(f"Unsupported action '{action or '(none)'}'")
    return action


# ---------------------------------------------------------------------------
# System & Device Settings Scopes
# ---------------------------------------------------------------------------

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

DEVICE_TEXT_KEYS: tuple[str, ...] = (
    "device_group",
    "default_speaker",
    "ma_player_entity",
    "default_area",
    "ble_beacon_uuid",
    "ble_target_address",
    "assigned_person",
    "dock_apps",
    "activity_sources",
    "security_pin_policy",
)
DEVICE_BOOL_KEYS: tuple[str, ...] = (
    "native_ble_tracking",
    "ble_auto_switch",
    "sync_device_area",
    "area_handoff",
    "activity_card",
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
DWELL_MIN_S = 3
DWELL_MAX_S = 60
NOISE_REDUCTION_LEVELS: tuple[str, ...] = ("strong", "light", "off")
DEFAULT_NOISE_REDUCTION = "strong"
SECURITY_PIN_POLICIES: tuple[str, ...] = ("auto", "allow", "require_pin", "block")
_HEX_COLOR = re.compile(r"^#[0-9A-F]{6}$")


class SettingsScopeError(ValueError):
    """A save named keys outside its scope, or a value that isn't valid."""


def _check_scope(
    incoming: Mapping[str, Any], allowed: tuple[str, ...], scope: str
) -> None:
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


FUSION_MODES: tuple[str, ...] = ("weighted", "any_or", "ble_only", "ble_and_sensor")
FUSION_THRESHOLD_MIN = 20
FUSION_THRESHOLD_MAX = 95
DEFAULT_FUSION_THRESHOLD = 50


def clean_area_fusion(
    current: Mapping[str, Any], update: Mapping[str, Any], allowed_sensors: set[str]
) -> dict[str, Any]:
    """Return one Area's fusion settings after a Studio change (`area_fusion_config[<area_id>]`)."""
    out: dict[str, Any] = {
        k: current[k] for k in ("mode", "threshold_pct", "sensors") if k in current
    }
    if "mode" in update:
        mode = _text(update["mode"]).lower()
        if mode not in FUSION_MODES:
            raise SettingsScopeError(f"Unknown fusion mode: {mode or '(empty)'}")
        out["mode"] = mode
    if "threshold_pct" in update:
        try:
            pct = int(update["threshold_pct"])
        except (TypeError, ValueError):
            raise SettingsScopeError(
                "The occupancy threshold must be a whole percent"
            ) from None
        out["threshold_pct"] = max(
            FUSION_THRESHOLD_MIN, min(FUSION_THRESHOLD_MAX, pct)
        )
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
            raise SettingsScopeError(
                f"Not a sensor of this Area: {', '.join(unknown)}"
            )
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
        out["calendar_entities"] = _entity_list(
            incoming["calendar_entities"], limit=MAX_CALENDARS
        )
    if "remote_groups" in incoming:
        out["remote_groups"] = _remote_groups(incoming["remote_groups"])
    if "volume_overrides" in incoming:
        out["volume_overrides"] = _volume_overrides(incoming["volume_overrides"])
    if "custom_palettes" in incoming:
        out["custom_palettes"] = _custom_palettes(incoming["custom_palettes"])
    if "doorbell_noise_reduction" in incoming:
        out["doorbell_noise_reduction"] = _noise_reduction(
            incoming["doorbell_noise_reduction"]
        )
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
            out["default_page_size"] = max(
                1, min(20, int(incoming["default_page_size"]))
            )
        if "wallpaper_cycle_minutes" in incoming:
            out["wallpaper_cycle_minutes"] = max(
                0, int(incoming["wallpaper_cycle_minutes"])
            )
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
    if "security_pin_policy" in out:
        pol = out["security_pin_policy"].lower()
        if pol not in SECURITY_PIN_POLICIES:
            raise SettingsScopeError(
                f"Unknown security PIN policy: {pol or '(empty)'}"
            )
        out["security_pin_policy"] = pol
    return out


def system_settings_view(global_cfg: Mapping[str, Any]) -> dict[str, Any]:
    """Return the System settings as Studio shows them, read straight from `.storage/latter.site`."""
    cams = _entity_list(global_cfg.get("camera_entities"))
    if not cams and _text(global_cfg.get("camera_entity")):
        cams = [_text(global_cfg.get("camera_entity"))]
    view: dict[str, Any] = {
        key: _text(global_cfg.get(key)) for key in SYSTEM_ENTITY_KEYS
    }
    view.update(
        {
            "camera_entities": cams,
            "remotes_list": _entity_list(global_cfg.get("remotes_list")),
            "remote_groups": _remote_groups(global_cfg.get("remote_groups")),
            "volume_overrides": _volume_overrides(global_cfg.get("volume_overrides")),
            "calendar_entities": _entity_list(
                global_cfg.get("calendar_entities"), limit=MAX_CALENDARS
            ),
            "custom_palettes": _custom_palettes(global_cfg.get("custom_palettes")),
            "doorbell_noise_reduction": _noise_reduction(
                global_cfg.get("doorbell_noise_reduction")
            ),
        }
    )
    return view


ANNOUNCE_PRIORITIES: tuple[str, ...] = ("normal", "warning", "critical")
NOTIFY_SPECIAL_TARGETS: tuple[str, ...] = ("all", "occupied_areas")
BROADCAST_TARGETS: tuple[str, ...] = ("all", "occupied_areas")


def clean_announcement(
    body: Mapping[str, Any], device_slugs: set[str]
) -> dict[str, Any]:
    """Validate a Studio announcement and return {"service", "data", "include_camera"}."""
    mode = _text(body.get("mode")).lower()
    target = _text(body.get("target_device"))
    message = _text(body.get("message"))
    if not message:
        raise SettingsScopeError("Enter a message")
    if mode == "notify":
        if target not in device_slugs and target not in NOTIFY_SPECIAL_TARGETS:
            raise SettingsScopeError(
                f"Not a Latter Device or notify target: {target or '(empty)'}"
            )
        title = _text(body.get("title"))
        if not title:
            raise SettingsScopeError("Enter a title")
        priority = _text(body.get("priority")).lower() or "normal"
        if priority not in ANNOUNCE_PRIORITIES:
            raise SettingsScopeError(f"Unknown priority: {priority}")
        return {
            "service": "notify",
            "data": {
                "target_device": target,
                "title": title,
                "message": message,
                "priority": priority,
                "chime": True,
            },
            "include_camera": bool(body.get("include_camera")),
        }
    if mode == "broadcast":
        if target not in BROADCAST_TARGETS:
            raise SettingsScopeError(
                f"Broadcast goes to every speaker or to occupied Areas, not {target or '(empty)'}"
            )
        data: dict[str, Any] = {"message": message}
        if target == "occupied_areas":
            data["target_device"] = "occupied_areas"
        return {
            "service": "intercom_broadcast",
            "data": data,
            "include_camera": False,
        }
    raise SettingsScopeError(f"Unknown announcement mode: {mode or '(empty)'}")
