"""Pure-stdlib Studio System & Device settings cleaners, view builders, and TypedDicts (`L0b`)."""

from __future__ import annotations

from collections.abc import Mapping
import math
import re
from typing import Final, TypedDict

from ..protocol_specs import (
    ACTIVITY_SOURCE_KEYS as ACTIVITY_SOURCE_KEYS,
    ACTIVITY_SOURCES_CATALOG as ACTIVITY_SOURCES_CATALOG,
    AREA_CATEGORIES_CATALOG as AREA_CATEGORIES_CATALOG,
    AREA_CATEGORY_TOKENS as AREA_CATEGORY_TOKENS,
    DEFAULT_ACTIVITY_SOURCES as DEFAULT_ACTIVITY_SOURCES,
    DEFAULT_ALARMS_SUMMARY as DEFAULT_ALARMS_SUMMARY,
    DEFAULT_AREA_CATEGORIES as DEFAULT_AREA_CATEGORIES,
    DEFAULT_DOCK_ROUTES as DEFAULT_DOCK_ROUTES,
    DEFAULT_GAMES_ITEMS as DEFAULT_GAMES_ITEMS,
    DEFAULT_HOME_CATEGORIES as DEFAULT_HOME_CATEGORIES,
    DEFAULT_TOOLS_ITEMS as DEFAULT_TOOLS_ITEMS,
    DEVICE_PREF_KEYS as DEVICE_PREF_KEYS,
    DEVICE_PREF_SPEC_MAP as DEVICE_PREF_SPEC_MAP,
    DEVICE_PREF_SPECS as DEVICE_PREF_SPECS,
    GAMES_ITEM_TOKENS as GAMES_ITEM_TOKENS,
    GAMES_ITEMS_CATALOG as GAMES_ITEMS_CATALOG,
    HOME_CATEGORIES_CATALOG as HOME_CATEGORIES_CATALOG,
    HOME_CATEGORY_TOKENS as HOME_CATEGORY_TOKENS,
    MAX_DOCK_ITEMS as MAX_DOCK_ITEMS,
    MAX_PINNED_ITEMS as MAX_PINNED_ITEMS,
    MAX_WORLD_CLOCKS as MAX_WORLD_CLOCKS,
    RETURN_TO_HOME_TIMEOUT_OPTIONS as RETURN_TO_HOME_TIMEOUT_OPTIONS,
    SHORTCUT_DOMAIN_ACTION_SETS as SHORTCUT_DOMAIN_ACTION_SETS,
    SHORTCUT_DOMAIN_ACTIONS as SHORTCUT_DOMAIN_ACTIONS,
    SHORTCUT_LABEL_MAX as SHORTCUT_LABEL_MAX,
    SHORTCUT_ROUTE_MAP as SHORTCUT_ROUTE_MAP,
    SHORTCUT_ROUTE_TOKENS as SHORTCUT_ROUTE_TOKENS,
    SHORTCUT_ROUTES_CATALOG as SHORTCUT_ROUTES_CATALOG,
    SHORTCUT_SUPPORTED_DOMAINS as SHORTCUT_SUPPORTED_DOMAINS,
    START_SCREEN_OPTIONS as START_SCREEN_OPTIONS,
    TOOLS_ITEM_TOKENS as TOOLS_ITEM_TOKENS,
    TOOLS_ITEMS_CATALOG as TOOLS_ITEMS_CATALOG,
    WAKE_WORD_MODE_OPTIONS as WAKE_WORD_MODE_OPTIONS,
    WORLD_CLOCK_CATALOG as WORLD_CLOCK_CATALOG,
    WORLD_CLOCK_CATALOG_MAP as WORLD_CLOCK_CATALOG_MAP,
    WORLD_CLOCK_ZONES as WORLD_CLOCK_ZONES,
    DevicePrefSpec as DevicePrefSpec,
    ShortcutItemDict as ShortcutItemDict,
    default_city_for_iana as default_city_for_iana,
    default_dock_items as default_dock_items,
    get_cached_zoneinfo as get_cached_zoneinfo,
    humanize_device_model_label as humanize_device_model_label,
    is_valid_iana_zone as is_valid_iana_zone,
    normalize_activity_sources as normalize_activity_sources,
    normalize_alarms_summary as normalize_alarms_summary,
    normalize_area_categories as normalize_area_categories,
    normalize_dock_items as normalize_dock_items,
    normalize_games_items as normalize_games_items,
    normalize_home_categories as normalize_home_categories,
    normalize_mdi_icon as normalize_mdi_icon,
    normalize_pinned_items as normalize_pinned_items,
    normalize_shortcut_item as normalize_shortcut_item,
    normalize_tools_items as normalize_tools_items,
    normalize_world_clocks_spec as normalize_world_clocks_spec,
    parse_area_categories as parse_area_categories,
    parse_games_items as parse_games_items,
    parse_home_categories as parse_home_categories,
    parse_tools_items as parse_tools_items,
    parse_world_clocks_spec as parse_world_clocks_spec,
    resolve_device_pref_value as resolve_device_pref_value,
    sanitize_clock_label as sanitize_clock_label,
    sanitize_shortcut_label as sanitize_shortcut_label,
    snap_calendar_lookahead_days as snap_calendar_lookahead_days,
    warm_timezone_cache as warm_timezone_cache,
)

# ---------------------------------------------------------------------------
# Concrete TypedDicts for Studio Settings (`M-P2-25`)
# ---------------------------------------------------------------------------


class CameraConfigEntryDict(TypedDict, total=False):
    label: str
    show_listen: bool
    show_talk: bool
    show_reply: bool
    unlock_entity: str


class VolumeOverrideDict(TypedDict):
    speaker: str
    target: str


class RemoteGroupDict(TypedDict):
    id: str
    name: str
    area_id: str
    remotes: list[str]


class CustomPaletteDict(TypedDict):
    name: str
    hex: str


class AreaFusionConfigDict(TypedDict, total=False):
    mode: str
    threshold_pct: int
    sensors: list[str]


class AreaIlluminanceConfigDict(TypedDict, total=False):
    entity_id: str
    dark_lux: float
    bright_lux: float


class SystemSettingsViewDict(TypedDict):
    weather_entity: str
    alarm_entity: str
    thermostat_entities: list[str]
    lock_entities: list[str]
    garage_entities: list[str]
    vacuum_entities: list[str]
    broadcast_speakers: list[str]
    broadcast_phrases: list[str]
    camera_entities: list[str]
    camera_configs: dict[str, CameraConfigEntryDict]
    remotes_list: list[str]
    remote_groups: list[RemoteGroupDict]
    volume_overrides: list[VolumeOverrideDict]
    calendar_entities: list[str]
    custom_palettes: list[CustomPaletteDict]
    doorbell_noise_reduction: str
    ble_attenuation: float
    ble_max_radius_m: float
    ble_max_velocity_mps: float
    ble_away_timeout_s: int
    ignored_discovered_devices: list[str]


class AnnouncementDispatchDict(TypedDict):
    service: str
    data: dict[str, str | bool]
    include_camera: bool


type SettingValue = (
    bool | int | float | str | list[str] | list[ShortcutItemDict] | list[VolumeOverrideDict]
    | list[RemoteGroupDict] | list[CustomPaletteDict] | dict[str, CameraConfigEntryDict] | None
)

# ---------------------------------------------------------------------------
# System & Device Settings Scopes & Constants
# ---------------------------------------------------------------------------

SYSTEM_ENTITY_KEYS: Final[tuple[str, ...]] = ("weather_entity", "alarm_entity")
SYSTEM_SETTING_KEYS: Final[tuple[str, ...]] = (
    *SYSTEM_ENTITY_KEYS,
    "thermostat_entities", "lock_entities", "garage_entities", "vacuum_entities",
    "broadcast_speakers", "broadcast_phrases", "camera_entities", "camera_configs",
    "remotes_list", "remote_groups", "volume_overrides", "calendar_entities",
    "custom_palettes", "doorbell_noise_reduction", "ble_attenuation",
    "ble_max_radius_m", "ble_max_velocity_mps", "ble_away_timeout_s", "ignored_discovered_devices",
)

DEVICE_TEXT_KEYS: Final[tuple[str, ...]] = (
    "device_group", "device_remote_group", "default_speaker", "ma_player_entity",
    "default_area", "ble_beacon_uuid", "ble_target_address", "ble_category",
    "assigned_person", "area_categories", "home_categories", "tools_items",
    "games_items", "activity_sources", "wallpaper_mode", "wallpaper_source",
    "wallpaper_collection", "screensaver_photo_mode", "screensaver_photo_source",
    "screensaver_photo_collection", "security_pin_policy",
)
DEVICE_BOOL_KEYS: Final[tuple[str, ...]] = (
    "native_ble_tracking", "ble_auto_switch", "sync_device_area",
    "area_handoff", "activity_card", "screensaver_shuffle",
)
DEVICE_SETTING_KEYS: Final[tuple[str, ...]] = (
    *DEVICE_TEXT_KEYS,
    *DEVICE_BOOL_KEYS,
    "dock_items", "pinned_items", "broadcast_speaker_entities",
    "camera_visible_entities", "camera_carousel_entities",
    "wallpaper_favorites", "wallpaper_cycle_minutes",
    "screensaver_photo_ids", "screensaver_cycle_minutes",
    "device_custom_color", "area_follow_dwell_s", "ble_ref_power",
    *DEVICE_PREF_KEYS,
)

PHOTO_POOL_MODES: Final[tuple[str, ...]] = ("off", "single", "collection", "custom")
MAX_PHOTO_POOL_IDS: Final = 100
MAX_LIST_ITEMS: Final = 10
MAX_THERMOSTATS: Final = 8
MAX_LOCKS: Final = 8
MAX_GARAGES: Final = 6
MAX_VACUUMS: Final = 6
MAX_BROADCAST_SPEAKERS: Final = 32
MAX_BROADCAST_PHRASES: Final = 12
MAX_BROADCAST_PHRASE_LEN: Final = 64
DEFAULT_STUDIO_BROADCAST_PHRASES: Final[tuple[str, ...]] = (
    "Dinner is ready", "Come upstairs", "Leaving soon",
)
MAX_CALENDARS: Final = 50
MAX_CUSTOM_PALETTES: Final = 24
MAX_REMOTE_GROUPS: Final = 20
MAX_REMOTE_GROUP_NAME_LEN: Final = 64
MAX_PALETTE_NAME_LEN: Final = 48
MAX_ANNOUNCE_TITLE_LEN: Final = 64
MAX_ANNOUNCE_MESSAGE_LEN: Final = 500
MAX_IGNORED_DISCOVERED: Final = 100
DWELL_MIN_S: Final = 3
DWELL_MAX_S: Final = 60
DEFAULT_BLE_ATTENUATION: Final = 2.2
BLE_ATTENUATION_MIN: Final = 1.5
BLE_ATTENUATION_MAX: Final = 4.5
DEFAULT_BLE_MAX_RADIUS_M: Final = 12.0
BLE_MAX_RADIUS_MIN_M: Final = 2.0
BLE_MAX_RADIUS_MAX_M: Final = 50.0
DEFAULT_BLE_MAX_VELOCITY_MPS: Final = 3.5
BLE_MAX_VELOCITY_MIN_MPS: Final = 0.5
BLE_MAX_VELOCITY_MAX_MPS: Final = 15.0
DEFAULT_BLE_AWAY_TIMEOUT_S: Final = 180
BLE_AWAY_TIMEOUT_MIN_S: Final = 30
BLE_AWAY_TIMEOUT_MAX_S: Final = 900
BLE_REF_POWER_MIN_DBM: Final = -90
BLE_REF_POWER_MAX_DBM: Final = -30
NOISE_REDUCTION_LEVELS: Final[tuple[str, ...]] = ("strong", "light", "off")
DEFAULT_NOISE_REDUCTION: Final = "strong"
SECURITY_PIN_POLICIES: Final[tuple[str, ...]] = ("auto", "allow", "require_pin", "block")
BLE_CATEGORIES: Final[tuple[str, ...]] = ("auto", "phone", "ble_tag")
FUSION_MODES: Final[tuple[str, ...]] = ("weighted", "any_or", "ble_only", "ble_and_sensor")
FUSION_THRESHOLD_MIN: Final = 20
FUSION_THRESHOLD_MAX: Final = 95
ILLUMINANCE_DARK_LUX_MIN: Final = 0.0
ILLUMINANCE_DARK_LUX_MAX: Final = 500.0
ILLUMINANCE_BRIGHT_LUX_MIN: Final = 1.0
ILLUMINANCE_BRIGHT_LUX_MAX: Final = 100000.0
ANNOUNCE_PRIORITIES: Final[tuple[str, ...]] = ("normal", "warning", "critical")
NOTIFY_SPECIAL_TARGETS: Final[tuple[str, ...]] = ("all", "occupied_areas")
BROADCAST_TARGETS: Final[tuple[str, ...]] = ("all", "occupied_areas")

_HEX_COLOR: Final = re.compile(r"^#[0-9A-F]{6}$")
_REMOTE_GROUP_ID_RE: Final = re.compile(r"^[A-Za-z0-9_-]{1,48}$")
_REMOTE_GROUP_REF: Final = re.compile(r"^group:[A-Za-z0-9_-]{1,48}$")
_MAX_ENTITY_ID_LEN: Final = 128
_MAX_CAM_LABEL_LEN: Final = 32
_MAX_AREA_ID_LEN: Final = 64
_MAX_DEVICE_TEXT_LEN: Final = 256


class SettingsScopeError(ValueError):
    """A save named keys outside its scope, or a value that isn't valid."""


def _check_scope(incoming: Mapping[str, object], allowed: tuple[str, ...], scope: str) -> None:
    unknown = sorted(str(k) for k in incoming if k not in allowed)
    if unknown:
        raise SettingsScopeError(f"{scope} settings don't include: {', '.join(unknown)}")


def _text(val: object) -> str:
    return str(val or "").strip()


def _coerce_bool(val: object) -> bool:
    if isinstance(val, str):
        return val.strip().lower() in ("1", "true", "on", "yes")
    return bool(val)


def _entity_list(val: object, limit: int = MAX_LIST_ITEMS) -> list[str]:
    if not isinstance(val, (list, tuple)):
        return []
    out: list[str] = []
    for item in val:
        ent = _text(item)
        if ent and ent not in out:
            out.append(ent)
    return out[:limit]


def _broadcast_phrases(val: object, *, strict: bool = False) -> list[str]:
    if val is None:
        return []
    if not isinstance(val, (list, tuple)):
        if strict:
            raise SettingsScopeError("broadcast_phrases must be a list of strings")
        return []
    out: list[str] = []
    for item in val:
        phrase = _text(item)[:MAX_BROADCAST_PHRASE_LEN]
        if phrase and phrase not in out:
            out.append(phrase)
    return out[:MAX_BROADCAST_PHRASES]


def _clean_single_camera_config(
    cam_id: str, raw_entry: Mapping[str, object], *, strict: bool
) -> CameraConfigEntryDict:
    clean_label = (
        _text(raw_entry.get("label"))
        .replace("|", " ").replace("\x1e", " ").replace("\x1f", " ").replace("\r", " ").replace("\n", " ")
        .strip()[:_MAX_CAM_LABEL_LEN]
    )
    unlock_ent = _text(raw_entry.get("unlock_entity"))[:_MAX_ENTITY_ID_LEN]
    if unlock_ent and not unlock_ent.startswith(("lock.", "cover.")):
        if strict:
            raise SettingsScopeError(
                f"Expected a lock.* or cover.* entity for camera_configs[{cam_id}].unlock_entity, got {unlock_ent}"
            )
        unlock_ent = ""
    entry: CameraConfigEntryDict = {}
    if clean_label:
        entry["label"] = clean_label
    for flag_key in ("show_listen", "show_talk", "show_reply"):
        raw_flag = raw_entry.get(flag_key)
        if isinstance(raw_flag, bool):
            if flag_key == "show_listen":
                entry["show_listen"] = raw_flag
            elif flag_key == "show_talk":
                entry["show_talk"] = raw_flag
            else:
                entry["show_reply"] = raw_flag
        elif raw_flag is not None and strict:
            raise SettingsScopeError(f"camera_configs[{cam_id}].{flag_key} must be a boolean or null")
    if unlock_ent:
        entry["unlock_entity"] = unlock_ent
    return entry


def _camera_configs(val: object, *, strict: bool = False) -> dict[str, CameraConfigEntryDict]:
    """Validate and normalize per-camera display labels, action toggles, and unlock entity bindings."""
    if val is None:
        return {}
    if not isinstance(val, Mapping):
        if strict:
            raise SettingsScopeError("camera_configs must be a mapping keyed by camera entity ID")
        return {}
    out: dict[str, CameraConfigEntryDict] = {}
    for raw_key, raw_entry in list(val.items())[:MAX_LIST_ITEMS]:
        cam_id = _text(raw_key)[:_MAX_ENTITY_ID_LEN]
        if not cam_id.startswith("camera."):
            if strict:
                raise SettingsScopeError(f"Expected a camera.* key in camera_configs, got {cam_id}")
            continue
        if not isinstance(raw_entry, Mapping):
            if strict:
                raise SettingsScopeError(f"camera_configs[{cam_id}] must be an object")
            continue
        if entry := _clean_single_camera_config(cam_id, raw_entry, strict=strict):
            out[cam_id] = entry
    return out


def _volume_overrides(val: object) -> list[VolumeOverrideDict]:
    if not isinstance(val, (list, tuple)):
        return []
    out: list[VolumeOverrideDict] = []
    for item in val:
        if isinstance(item, Mapping):
            spk, tgt = _text(item.get("speaker")), _text(item.get("target"))
            if spk and tgt:
                out.append({"speaker": spk, "target": tgt})
    return out[:MAX_LIST_ITEMS]


def _remote_groups(val: object, *, strict: bool = False) -> list[RemoteGroupDict]:
    if not isinstance(val, (list, tuple)):
        if strict:
            raise SettingsScopeError("remote_groups must be a list")
        return []
    if strict and len(val) > MAX_REMOTE_GROUPS:
        raise SettingsScopeError(f"remote_groups supports at most {MAX_REMOTE_GROUPS} groups")
    out: list[RemoteGroupDict] = []
    seen_ids: set[str] = set()
    for item in val:
        if not isinstance(item, Mapping):
            if strict:
                raise SettingsScopeError("Each remote group must be an object")
            continue
        gid = _text(item.get("id"))
        if not gid:
            continue
        if not _REMOTE_GROUP_ID_RE.fullmatch(gid):
            if strict:
                raise SettingsScopeError(
                    f"Invalid remote group id '{gid}' (use 1-48 letters, digits, '_' or '-')"
                )
            continue
        if gid in seen_ids:
            if strict:
                raise SettingsScopeError(f"Duplicate remote group id '{gid}'")
            continue
        seen_ids.add(gid)
        out.append(
            {
                "id": gid,
                "name": _text(item.get("name"))[:MAX_REMOTE_GROUP_NAME_LEN] or gid,
                "area_id": _text(item.get("area_id"))[:_MAX_AREA_ID_LEN],
                "remotes": _entity_list(item.get("remotes")),
            }
        )
        if len(out) >= MAX_REMOTE_GROUPS:
            break
    return out


def _custom_palettes(val: object) -> list[CustomPaletteDict]:
    if not isinstance(val, (list, tuple)):
        return []
    out: list[CustomPaletteDict] = []
    for item in val:
        if not isinstance(item, Mapping):
            continue
        hex_val = _text(item.get("hex")).upper()
        if _HEX_COLOR.match(hex_val) and all(p["hex"] != hex_val for p in out):
            out.append({"name": _text(item.get("name"))[:MAX_PALETTE_NAME_LEN] or hex_val, "hex": hex_val})
    return out[:MAX_CUSTOM_PALETTES]


def _ignored_device_ids(val: object, *, strict: bool = False) -> list[str]:
    if not isinstance(val, (list, tuple)):
        if strict:
            raise SettingsScopeError("ignored_discovered_devices must be a list")
        return []
    out: list[str] = []
    for item in val:
        dev_id = _text(item)[:_MAX_ENTITY_ID_LEN]
        if dev_id and dev_id not in out:
            out.append(dev_id)
        if len(out) >= MAX_IGNORED_DISCOVERED:
            break
    return out


def _noise_reduction(val: object) -> str:
    level = _text(val).lower()
    return level if level in NOISE_REDUCTION_LEVELS else DEFAULT_NOISE_REDUCTION


def _ble_float(
    val: object, default: float, lo: float, hi: float, ndigits: int, *, strict: bool = False
) -> float:
    if val is None or (isinstance(val, str) and not val.strip()):
        return default
    if isinstance(val, bool) or not isinstance(val, (int, float, str)):
        if strict:
            msg = "Expected a number, not a boolean" if isinstance(val, bool) else f"Not a number: {val!r}"
            raise SettingsScopeError(msg)
        return default
    try:
        fval = float(val)
    except (TypeError, ValueError) as err:
        if strict:
            raise SettingsScopeError(f"Not a number: {err}") from None
        return default
    if not math.isfinite(fval):
        if strict:
            raise SettingsScopeError("Expected a finite number")
        return default
    return round(max(lo, min(hi, fval)), ndigits)


def _ble_int(val: object, default: int, lo: int, hi: int, *, strict: bool = False) -> int:
    if val is None or (isinstance(val, str) and not val.strip()):
        return default
    if isinstance(val, bool) or not isinstance(val, (int, float, str)):
        if strict:
            msg = "Expected a whole number, not a boolean" if isinstance(val, bool) else f"Not a whole number: {val!r}"
            raise SettingsScopeError(msg)
        return default
    try:
        fval = float(val)
    except (TypeError, ValueError) as err:
        if strict:
            raise SettingsScopeError(f"Not a whole number: {err}") from None
        return default
    if not math.isfinite(fval):
        if strict:
            raise SettingsScopeError("Expected a finite whole number")
        return default
    return max(lo, min(hi, round(fval)))


def _seed_area_fusion_current(current: Mapping[str, object]) -> AreaFusionConfigDict:
    out: AreaFusionConfigDict = {}
    if isinstance(raw_mode := current.get("mode"), str):
        out["mode"] = raw_mode
    raw_pct = current.get("threshold_pct")
    if isinstance(raw_pct, int) and not isinstance(raw_pct, bool):
        out["threshold_pct"] = int(raw_pct)
    if isinstance(raw_sensors := current.get("sensors"), list):
        out["sensors"] = [str(s) for s in raw_sensors if isinstance(s, str)]
    return out


def clean_area_fusion(
    current: Mapping[str, object], update: Mapping[str, object], allowed_sensors: set[str]
) -> AreaFusionConfigDict:
    """Return one Area's fusion settings after a Studio change (`area_fusion_config[<area_id>]`)."""
    out = _seed_area_fusion_current(current)
    if "mode" in update:
        mode = _text(update["mode"]).lower()
        if mode not in FUSION_MODES:
            raise SettingsScopeError(f"Unknown fusion mode: {mode or '(empty)'}")
        out["mode"] = mode
    if "threshold_pct" in update:
        raw_pct = update["threshold_pct"]
        if isinstance(raw_pct, bool) or not isinstance(raw_pct, (int, float, str)):
            raise SettingsScopeError("The occupancy threshold must be a whole percent")
        try:
            pct = int(raw_pct)
        except (TypeError, ValueError):
            raise SettingsScopeError("The occupancy threshold must be a whole percent") from None
        out["threshold_pct"] = max(FUSION_THRESHOLD_MIN, min(FUSION_THRESHOLD_MAX, pct))
    if "sensors" in update:
        raw_sensors = update["sensors"]
        if not isinstance(raw_sensors, (list, tuple)):
            raise SettingsScopeError("sensors must be a list of entity IDs")
        sensors: list[str] = []
        for item in raw_sensors:
            ent = _text(item)
            if ent and ent not in sensors:
                sensors.append(ent)
        if unknown := [s for s in sensors if s not in allowed_sensors]:
            raise SettingsScopeError(f"Not a sensor of this Area: {', '.join(unknown)}")
        out["sensors"] = sensors
    return out


def _seed_existing_lux(raw: object, lo: float, hi: float) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    return max(lo, min(hi, val)) if math.isfinite(val) else None


def _parse_updated_lux(
    raw: object, *, label: str, bounds: tuple[float, float], range_msg: str, ndigits: int
) -> float:
    lo, hi = bounds
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise SettingsScopeError(f"{label} must be a number")
    try:
        val = float(raw)
    except (TypeError, ValueError):
        raise SettingsScopeError(f"{label} must be a number") from None
    if not math.isfinite(val):
        raise SettingsScopeError(f"{label} must be a finite number")
    if val < lo or val > hi:
        raise SettingsScopeError(range_msg)
    return round(val, ndigits)


def clean_area_illuminance(
    current: Mapping[str, object], update: Mapping[str, object], allowed_sensors: set[str]
) -> AreaIlluminanceConfigDict:
    """Return one Area's ambient light calibration after a Studio change (`area_illuminance_config[<area_id>]`)."""
    out: AreaIlluminanceConfigDict = {}
    if isinstance(current.get("entity_id"), str):
        out["entity_id"] = str(current["entity_id"])
    if (cur_d := _seed_existing_lux(current.get("dark_lux"), ILLUMINANCE_DARK_LUX_MIN, ILLUMINANCE_DARK_LUX_MAX)) is not None:
        out["dark_lux"] = cur_d
    if (cur_b := _seed_existing_lux(current.get("bright_lux"), ILLUMINANCE_BRIGHT_LUX_MIN, ILLUMINANCE_BRIGHT_LUX_MAX)) is not None:
        out["bright_lux"] = cur_b

    if "entity_id" in update:
        ent = _text(update["entity_id"])
        if ent in ("", "auto"):
            out["entity_id"] = "auto"
        elif ent == "disabled":
            out["entity_id"] = "disabled"
        elif ent in allowed_sensors:
            out["entity_id"] = ent
        else:
            raise SettingsScopeError(f"Not an illuminance sensor of this Area: {ent}")

    if "dark_lux" in update:
        out["dark_lux"] = _parse_updated_lux(
            update["dark_lux"],
            label="Dark lux",
            bounds=(ILLUMINANCE_DARK_LUX_MIN, ILLUMINANCE_DARK_LUX_MAX),
            range_msg="Dark lux must be between 0 and 500 lx",
            ndigits=2,
        )
    if "bright_lux" in update:
        out["bright_lux"] = _parse_updated_lux(
            update["bright_lux"],
            label="Bright lux",
            bounds=(ILLUMINANCE_BRIGHT_LUX_MIN, ILLUMINANCE_BRIGHT_LUX_MAX),
            range_msg="Bright lux must be between 1 and 100000 lx",
            ndigits=1,
        )

    dark_eff = float(out.get("dark_lux", 0.5))
    bright_eff = float(out.get("bright_lux", 40.0))
    if ("dark_lux" in update or "bright_lux" in update) and bright_eff <= dark_eff:
        raise SettingsScopeError("Bright lux must be greater than dark lux")
    if bright_eff < dark_eff + 1.0:
        out["bright_lux"] = round(min(ILLUMINANCE_BRIGHT_LUX_MAX, dark_eff + 1.0), 1)
    return out


def _domain_entity_list(val: object, prefix: str, limit: int, label: str) -> list[str]:
    if not isinstance(val, (list, tuple)):
        raise SettingsScopeError(f"{label} must be a list of entity IDs")
    out: list[str] = []
    for item in val:
        ent = _text(item)
        if not ent:
            continue
        if not ent.startswith(prefix):
            raise SettingsScopeError(f"Expected a {prefix}* entity for {label}, got {ent}")
        if ent not in out:
            out.append(ent)
    return out[:limit]


def _safe_domain_entity_list(val: object, prefix: str, limit: int) -> list[str]:
    if not isinstance(val, (list, tuple)):
        return []
    out: list[str] = []
    for item in val:
        ent = _text(item)
        if ent and ent.startswith(prefix) and ent not in out:
            out.append(ent)
    return out[:limit]


_SYSTEM_DOMAIN_LIST_SPECS: Final[tuple[tuple[str, str, int], ...]] = (
    ("thermostat_entities", "climate.", MAX_THERMOSTATS),
    ("lock_entities", "lock.", MAX_LOCKS),
    ("garage_entities", "cover.", MAX_GARAGES),
    ("vacuum_entities", "vacuum.", MAX_VACUUMS),
    ("broadcast_speakers", "media_player.", MAX_BROADCAST_SPEAKERS),
    ("camera_entities", "camera.", MAX_LIST_ITEMS),
    ("calendar_entities", "calendar.", MAX_CALENDARS),
)

_SYSTEM_BLE_FLOAT_SPECS: Final[tuple[tuple[str, float, float, float, int], ...]] = (
    ("ble_attenuation", DEFAULT_BLE_ATTENUATION, BLE_ATTENUATION_MIN, BLE_ATTENUATION_MAX, 2),
    ("ble_max_radius_m", DEFAULT_BLE_MAX_RADIUS_M, BLE_MAX_RADIUS_MIN_M, BLE_MAX_RADIUS_MAX_M, 1),
    ("ble_max_velocity_mps", DEFAULT_BLE_MAX_VELOCITY_MPS, BLE_MAX_VELOCITY_MIN_MPS, BLE_MAX_VELOCITY_MAX_MPS, 1),
)


def _clean_system_single_entities(incoming: Mapping[str, object], out: dict[str, SettingValue]) -> None:
    for key in SYSTEM_ENTITY_KEYS:
        if key not in incoming:
            continue
        ent = _text(incoming[key])[:_MAX_ENTITY_ID_LEN]
        if ent:
            expected = "weather." if key == "weather_entity" else "alarm_control_panel."
            if not ent.startswith(expected):
                raise SettingsScopeError(f"Expected a {expected}* entity for {key}, got {ent}")
        out[key] = ent


def _clean_system_ble_and_misc(incoming: Mapping[str, object], out: dict[str, SettingValue]) -> None:
    for key, dflt, lo, hi, ndigits in _SYSTEM_BLE_FLOAT_SPECS:
        if key in incoming:
            out[key] = _ble_float(incoming[key], dflt, lo, hi, ndigits, strict=True)
    if "ble_away_timeout_s" in incoming:
        out["ble_away_timeout_s"] = _ble_int(
            incoming["ble_away_timeout_s"],
            DEFAULT_BLE_AWAY_TIMEOUT_S,
            BLE_AWAY_TIMEOUT_MIN_S,
            BLE_AWAY_TIMEOUT_MAX_S,
            strict=True,
        )
    if "ignored_discovered_devices" in incoming:
        out["ignored_discovered_devices"] = _ignored_device_ids(incoming["ignored_discovered_devices"], strict=True)


def clean_system_settings(incoming: Mapping[str, object]) -> dict[str, SettingValue]:
    """Validate and normalize a System save (`camera_entities` is the sole canonical camera list)."""
    _check_scope(incoming, SYSTEM_SETTING_KEYS, "System")
    out: dict[str, SettingValue] = {}
    _clean_system_single_entities(incoming, out)
    for key, prefix, limit in _SYSTEM_DOMAIN_LIST_SPECS:
        if key in incoming:
            out[key] = _domain_entity_list(incoming[key], prefix, limit, key)
    if "broadcast_phrases" in incoming:
        out["broadcast_phrases"] = _broadcast_phrases(incoming["broadcast_phrases"], strict=True)
    if "camera_configs" in incoming:
        out["camera_configs"] = _camera_configs(incoming["camera_configs"], strict=True)
    if "remotes_list" in incoming:
        out["remotes_list"] = _entity_list(incoming["remotes_list"])
    if "remote_groups" in incoming:
        out["remote_groups"] = _remote_groups(incoming["remote_groups"], strict=True)
    if "volume_overrides" in incoming:
        out["volume_overrides"] = _volume_overrides(incoming["volume_overrides"])
    if "custom_palettes" in incoming:
        out["custom_palettes"] = _custom_palettes(incoming["custom_palettes"])
    if "doorbell_noise_reduction" in incoming:
        out["doorbell_noise_reduction"] = _noise_reduction(incoming["doorbell_noise_reduction"])
    _clean_system_ble_and_misc(incoming, out)
    return out


def _require_int(raw: object, key: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        msg = (
            f"Expected a whole number for {key}, not a boolean"
            if isinstance(raw, bool)
            else f"Not a whole number: {raw!r}"
        )
        raise SettingsScopeError(msg)
    try:
        return int(raw)
    except (TypeError, ValueError) as err:
        raise SettingsScopeError(f"Not a whole number: {err}") from None


def _clean_device_scalars(incoming: Mapping[str, object], out: dict[str, SettingValue]) -> None:
    for key in DEVICE_TEXT_KEYS:
        if key in incoming:
            out[key] = _text(incoming[key])[:_MAX_DEVICE_TEXT_LEN]
    for key in DEVICE_BOOL_KEYS:
        if key in incoming:
            out[key] = _coerce_bool(incoming[key])
    for cycle_key in ("wallpaper_cycle_minutes", "screensaver_cycle_minutes"):
        if cycle_key in incoming:
            out[cycle_key] = max(0, _require_int(incoming[cycle_key], cycle_key))
    if "area_follow_dwell_s" in incoming:
        dwell = _require_int(incoming["area_follow_dwell_s"], "area_follow_dwell_s")
        out["area_follow_dwell_s"] = max(DWELL_MIN_S, min(DWELL_MAX_S, dwell))


def _clean_device_ble_ref_power(raw_ref: object) -> int | None:
    if raw_ref is None or (isinstance(raw_ref, str) and not raw_ref.strip()):
        return None
    if isinstance(raw_ref, bool) or not isinstance(raw_ref, (int, float, str)):
        raise SettingsScopeError("ble_ref_power must be an integer in -90..-30 dBm")
    try:
        ref_f = float(raw_ref)
    except (TypeError, ValueError) as err:
        raise SettingsScopeError(f"Invalid ble_ref_power: {err}") from None
    if not math.isfinite(ref_f):
        raise SettingsScopeError("ble_ref_power must be a finite number")
    return max(BLE_REF_POWER_MIN_DBM, min(BLE_REF_POWER_MAX_DBM, round(ref_f)))


def _clean_device_pools_and_ble(incoming: Mapping[str, object], out: dict[str, SettingValue]) -> None:
    for pool_mode_key in ("wallpaper_mode", "screensaver_photo_mode"):
        if pool_mode_key in out:
            pm = str(out[pool_mode_key] or "").lower()
            if pm not in PHOTO_POOL_MODES:
                raise SettingsScopeError(f"Unknown {pool_mode_key}: {pm or '(empty)'}")
            out[pool_mode_key] = pm

    for pool_ids_key in ("wallpaper_favorites", "screensaver_photo_ids"):
        if pool_ids_key not in incoming:
            continue
        raw_pids = incoming[pool_ids_key]
        if not isinstance(raw_pids, (list, tuple)):
            raise SettingsScopeError(f"{pool_ids_key} must be a list of photo IDs")
        cleaned_pids: list[str] = []
        for item in raw_pids:
            pid = _text(item)[:_MAX_ENTITY_ID_LEN]
            if pid and pid not in cleaned_pids:
                cleaned_pids.append(pid)
            if len(cleaned_pids) >= MAX_PHOTO_POOL_IDS:
                break
        out[pool_ids_key] = cleaned_pids

    if "ble_ref_power" in incoming:
        out["ble_ref_power"] = _clean_device_ble_ref_power(incoming["ble_ref_power"])


def _clean_device_lists_and_shortcuts(incoming: Mapping[str, object], out: dict[str, SettingValue]) -> None:
    try:
        if "area_categories" in out:
            out["area_categories"] = normalize_area_categories(str(out["area_categories"]))
        if "home_categories" in out:
            out["home_categories"] = normalize_home_categories(str(out["home_categories"]))
        if "tools_items" in incoming:
            out["tools_items"] = normalize_tools_items(incoming["tools_items"])
        if "games_items" in incoming:
            out["games_items"] = normalize_games_items(incoming["games_items"])
        if "activity_sources" in incoming:
            out["activity_sources"] = normalize_activity_sources(incoming["activity_sources"])
        if "dock_items" in incoming:
            out["dock_items"] = normalize_dock_items(incoming["dock_items"], strict=True)
        if "pinned_items" in incoming:
            out["pinned_items"] = normalize_pinned_items(incoming["pinned_items"], strict=True)
    except ValueError as err:
        raise SettingsScopeError(str(err)) from None

    for key, prefix, limit in (
        ("broadcast_speaker_entities", "media_player.", MAX_BROADCAST_SPEAKERS),
        ("camera_visible_entities", "camera.", MAX_LIST_ITEMS),
        ("camera_carousel_entities", "camera.", MAX_LIST_ITEMS),
    ):
        if key in incoming:
            out[key] = _domain_entity_list(incoming[key], prefix, limit, key)


def _clean_text_pref_spec(key: str, raw_v: object) -> str:
    try:
        if key == "world_clocks":
            return normalize_world_clocks_spec(raw_v, strict=True)
        if key == "local_clock_label":
            return sanitize_clock_label(raw_v)
        if key == "alarms_summary":
            return normalize_alarms_summary(raw_v, strict=True)
        return _text(raw_v)
    except ValueError as err:
        raise SettingsScopeError(str(err)) from None


def _clean_single_pref_spec(spec: DevicePrefSpec, raw_v: object) -> bool | int | str:
    if spec.domain == "switch":
        return _coerce_bool(raw_v)
    if spec.domain == "select":
        opt_v = _text(raw_v)
        if opt_v not in spec.options:
            raise SettingsScopeError(f"Unknown option for {spec.key}: {opt_v or '(empty)'}")
        return opt_v
    if spec.domain == "text":
        return _clean_text_pref_spec(spec.key, raw_v)
    num_v = _require_int(raw_v, spec.key)
    if spec.key == "calendar_lookahead_days":
        return snap_calendar_lookahead_days(num_v)
    if spec.min_val is not None:
        num_v = max(spec.min_val, num_v)
    if spec.max_val is not None:
        num_v = min(spec.max_val, num_v)
    return num_v


def _validate_device_enum_strings(incoming: Mapping[str, object], out: dict[str, SettingValue]) -> None:
    if "device_custom_color" in incoming:
        color = _text(incoming["device_custom_color"]).upper()
        if not _HEX_COLOR.match(color):
            raise SettingsScopeError(f"Not a #RRGGBB color: {color or '(empty)'}")
        out["device_custom_color"] = color
    if "security_pin_policy" in out:
        pol = str(out["security_pin_policy"] or "").lower()
        if pol not in SECURITY_PIN_POLICIES:
            raise SettingsScopeError(f"Unknown security PIN policy: {pol or '(empty)'}")
        out["security_pin_policy"] = pol
    if "device_remote_group" in out:
        rem_grp = str(out["device_remote_group"] or "") or "area_auto"
        if rem_grp not in ("area_auto", "all") and not _REMOTE_GROUP_REF.match(rem_grp):
            raise SettingsScopeError(f"Unknown remote group mode: {rem_grp}")
        out["device_remote_group"] = rem_grp
    if "ble_category" in out:
        ble_cat = (str(out["ble_category"] or "") or "auto").lower()
        if ble_cat not in BLE_CATEGORIES:
            raise SettingsScopeError(f"Unknown BLE category: {ble_cat}")
        out["ble_category"] = ble_cat


def _apply_device_enums_and_traits(
    incoming: Mapping[str, object],
    current: Mapping[str, object] | None,
    out: dict[str, SettingValue],
    *,
    is_round_display: bool | None,
    supports_hw_jpeg: bool | None,
    strict_traits: bool,
) -> None:
    eff_home_enabled = (
        out["home_screen_enabled"]
        if "home_screen_enabled" in out
        else resolve_device_pref_value(current or {}, "home_screen_enabled")
    )
    eff_start = (
        out["start_screen"]
        if "start_screen" in out
        else resolve_device_pref_value(current or {}, "start_screen")
    )
    if not eff_home_enabled and eff_start == "Home":
        out["start_screen"] = "Time App"

    if is_round_display is False and out.get("clock_face") == "Modern Analog":
        if strict_traits:
            raise SettingsScopeError("Modern Analog clock face is only supported on round displays")
        out["clock_face"] = "Minimal Digital"

    if supports_hw_jpeg is False and out.get("camera_doorbell_popup") == "Live Video":
        if strict_traits:
            raise SettingsScopeError("Live Video doorbell popup requires hardware JPEG decoding")
        out["camera_doorbell_popup"] = "Snapshot"

    if (
        out.get("native_ble_tracking") is True
        and "ble_auto_switch" not in incoming
        and current is not None
        and not bool(current.get("native_ble_tracking", True))
    ):
        out["ble_auto_switch"] = True

    _validate_device_enum_strings(incoming, out)


def clean_device_settings(
    incoming: Mapping[str, object],
    current: Mapping[str, object] | None = None,
    *,
    is_round_display: bool | None = None,
    supports_hw_jpeg: bool | None = None,
    strict_traits: bool = False,
) -> dict[str, SettingValue]:
    """Validate and normalize a Device save."""
    _check_scope(incoming, DEVICE_SETTING_KEYS, "Device")
    out: dict[str, SettingValue] = {}
    _clean_device_scalars(incoming, out)
    _clean_device_pools_and_ble(incoming, out)
    _clean_device_lists_and_shortcuts(incoming, out)
    for spec in DEVICE_PREF_SPECS:
        if spec.key in incoming:
            out[spec.key] = _clean_single_pref_spec(spec, incoming[spec.key])
    _apply_device_enums_and_traits(
        incoming,
        current,
        out,
        is_round_display=is_round_display,
        supports_hw_jpeg=supports_hw_jpeg,
        strict_traits=strict_traits,
    )
    return out


def system_settings_view(global_cfg: Mapping[str, object]) -> SystemSettingsViewDict:
    """Return the System settings as Studio shows them, read straight from `.storage/latter.site`."""
    return {
        "weather_entity": _text(global_cfg.get("weather_entity")),
        "alarm_entity": _text(global_cfg.get("alarm_entity")),
        "thermostat_entities": _safe_domain_entity_list(global_cfg.get("thermostat_entities"), "climate.", MAX_THERMOSTATS),
        "lock_entities": _safe_domain_entity_list(global_cfg.get("lock_entities"), "lock.", MAX_LOCKS),
        "garage_entities": _safe_domain_entity_list(global_cfg.get("garage_entities"), "cover.", MAX_GARAGES),
        "vacuum_entities": _safe_domain_entity_list(global_cfg.get("vacuum_entities"), "vacuum.", MAX_VACUUMS),
        "broadcast_speakers": _safe_domain_entity_list(global_cfg.get("broadcast_speakers"), "media_player.", MAX_BROADCAST_SPEAKERS),
        "broadcast_phrases": (
            _broadcast_phrases(global_cfg.get("broadcast_phrases"))
            if "broadcast_phrases" in global_cfg
            else list(DEFAULT_STUDIO_BROADCAST_PHRASES)
        ),
        "camera_entities": _safe_domain_entity_list(global_cfg.get("camera_entities"), "camera.", MAX_LIST_ITEMS),
        "camera_configs": _camera_configs(global_cfg.get("camera_configs")),
        "remotes_list": _entity_list(global_cfg.get("remotes_list")),
        "remote_groups": _remote_groups(global_cfg.get("remote_groups")),
        "volume_overrides": _volume_overrides(global_cfg.get("volume_overrides")),
        "calendar_entities": _safe_domain_entity_list(global_cfg.get("calendar_entities"), "calendar.", MAX_CALENDARS),
        "custom_palettes": _custom_palettes(global_cfg.get("custom_palettes")),
        "doorbell_noise_reduction": _noise_reduction(global_cfg.get("doorbell_noise_reduction")),
        "ble_attenuation": _ble_float(global_cfg.get("ble_attenuation"), DEFAULT_BLE_ATTENUATION, BLE_ATTENUATION_MIN, BLE_ATTENUATION_MAX, 2),
        "ble_max_radius_m": _ble_float(global_cfg.get("ble_max_radius_m"), DEFAULT_BLE_MAX_RADIUS_M, BLE_MAX_RADIUS_MIN_M, BLE_MAX_RADIUS_MAX_M, 1),
        "ble_max_velocity_mps": _ble_float(global_cfg.get("ble_max_velocity_mps"), DEFAULT_BLE_MAX_VELOCITY_MPS, BLE_MAX_VELOCITY_MIN_MPS, BLE_MAX_VELOCITY_MAX_MPS, 1),
        "ble_away_timeout_s": _ble_int(global_cfg.get("ble_away_timeout_s"), DEFAULT_BLE_AWAY_TIMEOUT_S, BLE_AWAY_TIMEOUT_MIN_S, BLE_AWAY_TIMEOUT_MAX_S),
        "ignored_discovered_devices": _ignored_device_ids(global_cfg.get("ignored_discovered_devices")),
    }


def clean_announcement(body: Mapping[str, object], device_slugs: set[str]) -> AnnouncementDispatchDict:
    """Validate a Studio announcement and return `{"service", "data", "include_camera"}`."""
    mode = _text(body.get("mode")).lower()
    target = _text(body.get("target_device"))
    message = _text(body.get("message"))
    if not message:
        raise SettingsScopeError("Enter a message")
    if len(message) > MAX_ANNOUNCE_MESSAGE_LEN:
        raise SettingsScopeError(f"Announcement message must be at most {MAX_ANNOUNCE_MESSAGE_LEN} characters")
    if mode == "notify":
        if target not in device_slugs and target not in NOTIFY_SPECIAL_TARGETS:
            raise SettingsScopeError(f"Not a Latter Device or notify target: {target or '(empty)'}")
        title = _text(body.get("title"))
        if not title:
            raise SettingsScopeError("Enter a title")
        if len(title) > MAX_ANNOUNCE_TITLE_LEN:
            raise SettingsScopeError(f"Announcement title must be at most {MAX_ANNOUNCE_TITLE_LEN} characters")
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
            raise SettingsScopeError(
                f"Broadcast goes to every speaker or to occupied Areas, not {target or '(empty)'}"
            )
        data: dict[str, str | bool] = {"message": message}
        if target == "occupied_areas":
            data["target_device"] = "occupied_areas"
        return {"service": "intercom_broadcast", "data": data, "include_camera": False}
    raise SettingsScopeError(f"Unknown announcement mode: {mode or '(empty)'}")
