"""Latter Studio settings scopes, command routing, target checks, and catalog push gate.

Standard library only (no Home Assistant imports), so unit tests exercise this exact code.
A System save writes only System settings (`.storage/latter.site`); a Device save writes only that
Device's settings (its config subentry). The websocket type is the command scope: `latter/system/command`
runs System commands and `latter/device/command` runs Device commands on the Device named by `subentry_id`.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
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
        "device_action",
        "select_wallpaper",
        "toggle_wallpaper_favorite",
        "delete_wallpaper",
        "save_device_config",
    }
)

ALLOWED_DEVICE_ACTIONS: tuple[str, ...] = (
    "restart",
    "find_my",
    "activate_screensaver",
    "trigger_va",
    "log_memory_report",
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

@dataclass(frozen=True, slots=True)
class DevicePrefSpec:
    """Declarative specification for one Protocol v3 `device_prefs` subentry preference."""

    key: str
    label: str
    domain: Literal["select", "switch", "number"]
    default: Any
    section: str
    capability: Literal[
        "display",
        "display_imu",
        "display_battery",
        "mic",
        "speaker",
        "beacon",
        "beacon_battery",
    ]
    group_tier: Literal["behavior", "appearance"] | None
    options: tuple[str, ...] = ()
    min_val: int | None = None
    max_val: int | None = None
    step: int | None = None
    unit: str = ""


POWER_PROFILE_OPTIONS: tuple[str, ...] = (
    "Portable Carry",
    "Handheld Roaming",
    "Wearable Watch",
    "Tabletop Dock",
    "Always-On Wall / Desk",
    "Custom",
)
WAKE_WORD_MODE_OPTIONS: tuple[str, ...] = ("Docked Only", "Always On", "Disabled")
WAKE_GESTURE_OPTIONS: tuple[str, ...] = ("Always On", "Docked Only", "Disabled")
BATTERY_SCREEN_TIMEOUT_OPTIONS: tuple[str, ...] = (
    "10s",
    "15s",
    "30s",
    "1 min",
    "2 min",
    "Never",
)
DOCKED_IDLE_TIMEOUT_OPTIONS: tuple[str, ...] = (
    "10s",
    "15s",
    "30s",
    "1 min",
    "2 min",
    "5 min",
    "Never",
)
BATTERY_HIBERNATE_TIMEOUT_OPTIONS: tuple[str, ...] = (
    "5 min",
    "10 min",
    "15 min",
    "30 min",
    "Disabled",
)
SCREENSAVER_STYLE_OPTIONS: tuple[str, ...] = (
    "Ambient Clock",
    "Aurora",
    "Starfield",
    "Digital Rain",
    "Fireworks",
)
AUTO_BRIGHTNESS_MODE_OPTIONS: tuple[str, ...] = (
    "Disabled",
    "Sun Synchronized",
    "Time Schedule",
)
BRIGHTNESS_PCT_OPTIONS: tuple[str, ...] = ("60%", "70%", "80%", "90%", "100%")
COLOR_PROFILE_OPTIONS: tuple[str, ...] = (
    "Steel Blue",
    "Pink",
    "Blue",
    "Green",
    "Custom",
)
VA_VISUAL_PROFILE_OPTIONS: tuple[str, ...] = (
    "Nebula",
    "Solaris",
    "Rings",
    "Light Bar",
    "Dot Wave",
)
START_SCREEN_OPTIONS: tuple[str, ...] = (
    "Home",
    "Clock",
    "Media",
    "Home Hub",
    "Area Controls",
    "Remote",
    "Weather",
    "Cameras",
    "Games",
    "Tools",
)
RETURN_TO_HOME_TIMEOUT_OPTIONS: tuple[str, ...] = (
    "15s",
    "30s",
    "1 min",
    "2 min",
    "5 min",
    "10 min",
    "Never",
)
CLOCK_FACE_OPTIONS: tuple[str, ...] = (
    "Minimal Digital",
    "Modern Roman (Analog)",
    "Modern Digital (Bold)",
)
TIME_FORMAT_OPTIONS: tuple[str, ...] = ("12-Hour (AM/PM)", "24-Hour")
AREA_CATEGORY_TOKENS: tuple[str, ...] = (
    "scene",
    "light",
    "cover",
    "fan",
    "switch",
    "climate",
    "media",
    "all",
)
DEFAULT_AREA_CATEGORIES = "scene,light,cover,fan,switch,climate,media"


def parse_area_categories(csv: str | None) -> list[str]:
    """Return the known Area category tokens named in `csv`, in order, without duplicates."""
    out: list[str] = []
    for raw in str(csv or "").split(","):
        tok = raw.strip().lower()
        if tok in AREA_CATEGORY_TOKENS and tok not in out:
            out.append(tok)
    return out


def normalize_area_categories(csv: str | None) -> str:
    """Return `csv` as canonical comma-separated Area categories; raise ValueError if empty or unknown."""
    names = [t.strip().lower() for t in str(csv or "").split(",") if t.strip()]
    unknown = sorted({t for t in names if t not in AREA_CATEGORY_TOKENS})
    if unknown:
        raise ValueError(f"Unknown Area category: {', '.join(unknown)}")
    cats = parse_area_categories(csv)
    if not cats:
        raise ValueError("Keep at least one Area category enabled")
    return ",".join(cats)


HOME_CATEGORY_TOKENS: tuple[str, ...] = (
    "alarm",
    "thermostat",
    "entry",
    "vacuum",
)
DEFAULT_HOME_CATEGORIES = "alarm,thermostat,entry,vacuum"


def parse_home_categories(csv: str | None) -> list[str]:
    """Return the known Home Hub category tokens named in `csv`, in order, without duplicates."""
    out: list[str] = []
    for raw in str(csv or "").split(","):
        tok = raw.strip().lower()
        if tok in HOME_CATEGORY_TOKENS and tok not in out:
            out.append(tok)
    return out


def normalize_home_categories(csv: str | None) -> str:
    """Return `csv` as canonical comma-separated Home Hub categories; raise ValueError if empty or unknown."""
    names = [t.strip().lower() for t in str(csv or "").split(",") if t.strip()]
    unknown = sorted({t for t in names if t not in HOME_CATEGORY_TOKENS})
    if unknown:
        raise ValueError(f"Unknown Home category: {', '.join(unknown)}")
    cats = parse_home_categories(csv)
    if not cats:
        raise ValueError("Keep at least one Home category enabled")
    return ",".join(cats)


ALBUM_ART_STYLE_OPTIONS: tuple[str, ...] = (
    "Full Screen",
    "Letterbox",
    "Standard",
    "None",
)
MUSIC_OVERLAY_STYLE_OPTIONS: tuple[str, ...] = (
    "Art Only",
    "Art + Metadata",
    "Always Visible",
)
ALBUM_SORT_OPTIONS: tuple[str, ...] = (
    "Alphabetical",
    "Newest on Top",
    "Oldest on Top",
)
ARTIST_ALBUM_SORT_OPTIONS: tuple[str, ...] = (
    "Oldest on Top",
    "Newest on Top",
    "Alphabetical",
)
PODCAST_SORT_OPTIONS: tuple[str, ...] = ("Newest on Top", "Oldest on Top")
WW_SENSITIVITY_OPTIONS: tuple[str, ...] = (
    "Slightly sensitive",
    "Moderately sensitive",
    "Very sensitive",
)
BLE_BEACON_MODE_OPTIONS: tuple[str, ...] = (
    "Handheld Only",
    "Handheld + Screen Off",
    "Always",
)
WEATHER_SIM_CONDITION_OPTIONS: tuple[str, ...] = (
    "Live (Home Assistant)",
    "Clear Night",
    "Sunny / Clear Day",
    "Partly Cloudy (Day)",
    "Partly Cloudy (Night)",
    "Cloudy / Overcast (Day)",
    "Cloudy / Overcast (Night)",
    "Fog / Mist (Day)",
    "Fog / Mist (Night)",
    "Rainy (Day)",
    "Rainy (Night)",
    "Pouring / Heavy Rain",
    "Snow (Day)",
    "Snow (Night)",
    "Thunderstorm (Day)",
    "Thunderstorm (Night)",
    "Windy",
)

DEVICE_PREF_SPECS: tuple[DevicePrefSpec, ...] = (
    DevicePrefSpec("power_profile", "Power Profile", "select", "Portable Carry", "sleep", "display", "behavior", options=POWER_PROFILE_OPTIONS),
    DevicePrefSpec("wake_word_mode", "Wake Word Mode", "select", "Docked Only", "voice", "mic", "behavior", options=WAKE_WORD_MODE_OPTIONS),
    DevicePrefSpec("tap_to_wake", "Tap to Wake", "select", "Docked Only", "sleep", "display", "behavior", options=WAKE_GESTURE_OPTIONS),
    DevicePrefSpec("pickup_to_wake", "Pickup to Wake", "select", "Docked Only", "sleep", "display_imu", "behavior", options=WAKE_GESTURE_OPTIONS),
    DevicePrefSpec("battery_screen_timeout", "Battery Screen Timeout", "select", "30s", "sleep", "display_battery", "behavior", options=BATTERY_SCREEN_TIMEOUT_OPTIONS),
    DevicePrefSpec("docked_idle_timeout", "Docked Idle Timeout", "select", "1 min", "sleep", "display", "behavior", options=DOCKED_IDLE_TIMEOUT_OPTIONS),
    DevicePrefSpec("battery_hibernate_timeout", "Battery Hibernate Timeout", "select", "15 min", "sleep", "display_battery", "behavior", options=BATTERY_HIBERNATE_TIMEOUT_OPTIONS),
    DevicePrefSpec("docked_screensaver", "Docked Screensaver", "switch", True, "sleep", "display", "behavior"),
    DevicePrefSpec("screensaver_style", "Screensaver Style", "select", "Ambient Clock", "sleep", "display", "appearance", options=SCREENSAVER_STYLE_OPTIONS),
    DevicePrefSpec("hold_crown_power_off", "Hold Crown to Power Off", "switch", False, "sleep", "display_battery", "behavior"),
    DevicePrefSpec("auto_brightness_mode", "Auto Brightness Mode", "select", "Sun Synchronized", "display", "display", "behavior", options=AUTO_BRIGHTNESS_MODE_OPTIONS),
    DevicePrefSpec("manual_brightness", "Manual Brightness", "select", "90%", "display", "display", "behavior", options=BRIGHTNESS_PCT_OPTIONS),
    DevicePrefSpec("day_brightness", "Day Brightness", "select", "90%", "display", "display", "behavior", options=BRIGHTNESS_PCT_OPTIONS),
    DevicePrefSpec("night_brightness", "Night Brightness", "select", "70%", "display", "display", "behavior", options=BRIGHTNESS_PCT_OPTIONS),
    DevicePrefSpec("day_start_hour", "Day Start Hour", "number", 7, "display", "display", "behavior", min_val=0, max_val=23, step=1, unit="h"),
    DevicePrefSpec("night_start_hour", "Night Start Hour", "number", 20, "display", "display", "behavior", min_val=0, max_val=23, step=1, unit="h"),
    DevicePrefSpec("color_profile", "Color Profile", "select", "Steel Blue", "display", "display", "appearance", options=COLOR_PROFILE_OPTIONS),
    DevicePrefSpec("va_visual_profile", "Visual Profile", "select", "Nebula", "voice", "display", "appearance", options=VA_VISUAL_PROFILE_OPTIONS),
    DevicePrefSpec("home_screen_enabled", "Enable Home Screen", "switch", True, "display", "display", "appearance"),
    DevicePrefSpec("start_screen", "Start Screen", "select", "Home", "display", "display", "appearance", options=START_SCREEN_OPTIONS),
    DevicePrefSpec("return_to_home_timeout", "Return to Home Timeout", "select", "2 min", "display", "display", "appearance", options=RETURN_TO_HOME_TIMEOUT_OPTIONS),
    DevicePrefSpec("clock_face", "Clock Face", "select", "Minimal Digital", "display", "display", "appearance", options=CLOCK_FACE_OPTIONS),
    DevicePrefSpec("time_format", "Time Format", "select", "12-Hour (AM/PM)", "display", "display", "appearance", options=TIME_FORMAT_OPTIONS),
    DevicePrefSpec("weather_background", "Weather Background", "switch", True, "home", "display", "appearance"),
    DevicePrefSpec("home_sun", "Sun", "switch", True, "home", "display", "appearance"),
    DevicePrefSpec("home_moon", "Moon", "switch", True, "home", "display", "appearance"),
    DevicePrefSpec("wake_greeting", "Wake Greeting", "switch", True, "home", "display", "appearance"),
    DevicePrefSpec("album_art_style", "Album Art Style", "select", "Full Screen", "music", "display", "appearance", options=ALBUM_ART_STYLE_OPTIONS),
    DevicePrefSpec("music_overlay_style", "Overlay Style", "select", "Art + Metadata", "music", "display", "appearance", options=MUSIC_OVERLAY_STYLE_OPTIONS),
    DevicePrefSpec("show_speaker_shortcut", "Show Speaker Shortcut", "switch", True, "music", "display", "appearance"),
    DevicePrefSpec("show_library_shortcut", "Show Library Shortcut", "switch", True, "music", "display", "appearance"),
    DevicePrefSpec("album_sort_order", "Album Sort Order", "select", "Alphabetical", "music", "display", "appearance", options=ALBUM_SORT_OPTIONS),
    DevicePrefSpec("artist_album_sort_order", "Artist Album Sort Order", "select", "Oldest on Top", "music", "display", "appearance", options=ARTIST_ALBUM_SORT_OPTIONS),
    DevicePrefSpec("podcast_sort_order", "Podcast Sort Order", "select", "Newest on Top", "music", "display", "appearance", options=PODCAST_SORT_OPTIONS),
    DevicePrefSpec("ww_sens_okay_nabu", "Okay Nabu Sensitivity", "select", "Moderately sensitive", "voice", "mic", "behavior", options=WW_SENSITIVITY_OPTIONS),
    DevicePrefSpec("ww_sens_hey_luna", "Hey Luna Sensitivity", "select", "Moderately sensitive", "voice", "mic", "behavior", options=WW_SENSITIVITY_OPTIONS),
    DevicePrefSpec("ww_sens_hey_jarvis", "Hey Jarvis Sensitivity", "select", "Moderately sensitive", "voice", "mic", "behavior", options=WW_SENSITIVITY_OPTIONS),
    DevicePrefSpec("ww_sens_hey_mycroft", "Hey Mycroft Sensitivity", "select", "Moderately sensitive", "voice", "mic", "behavior", options=WW_SENSITIVITY_OPTIONS),
    DevicePrefSpec("ww_sens_alexa", "Alexa Sensitivity", "select", "Moderately sensitive", "voice", "mic", "behavior", options=WW_SENSITIVITY_OPTIONS),
    DevicePrefSpec("wake_screen_on_assist", "Wake Screen on Assist", "switch", True, "voice", "display", "behavior"),
    DevicePrefSpec("alert_volume", "Alert Volume", "number", 80, "sound", "speaker", "behavior", min_val=20, max_val=100, step=5, unit="%"),
    DevicePrefSpec("volume_step_size", "Volume Step Size", "number", 5, "sound", "speaker", "behavior", min_val=1, max_val=10, step=1, unit="%"),
    DevicePrefSpec("game_sound_effects", "Game Sound Effects", "switch", True, "sound", "display", "behavior"),
    DevicePrefSpec("ble_beacon_mode", "BLE Beacon Mode", "select", "Handheld Only", "area", "beacon_battery", "behavior", options=BLE_BEACON_MODE_OPTIONS),
    DevicePrefSpec("weather_sim_condition", "Weather Simulation", "select", "Live (Home Assistant)", "developer", "display", None, options=WEATHER_SIM_CONDITION_OPTIONS),
)

DEVICE_PREF_SPEC_MAP: dict[str, DevicePrefSpec] = {s.key: s for s in DEVICE_PREF_SPECS}
DEVICE_PREF_KEYS: tuple[str, ...] = tuple(s.key for s in DEVICE_PREF_SPECS)

POWER_PROFILE_PREFS: dict[str, dict[str, Any]] = {
    "Portable Carry": {
        "wake_word_mode": "Docked Only",
        "tap_to_wake": "Docked Only",
        "pickup_to_wake": "Docked Only",
        "battery_screen_timeout": "30s",
        "docked_idle_timeout": "1 min",
        "battery_hibernate_timeout": "15 min",
        "docked_screensaver": True,
    },
    "Handheld Roaming": {
        "wake_word_mode": "Docked Only",
        "tap_to_wake": "Always On",
        "pickup_to_wake": "Always On",
        "battery_screen_timeout": "30s",
        "docked_idle_timeout": "1 min",
        "battery_hibernate_timeout": "30 min",
        "docked_screensaver": True,
    },
    "Wearable Watch": {
        "wake_word_mode": "Docked Only",
        "tap_to_wake": "Always On",
        "pickup_to_wake": "Always On",
        "battery_screen_timeout": "15s",
        "docked_idle_timeout": "1 min",
        "battery_hibernate_timeout": "15 min",
        "docked_screensaver": True,
    },
    "Tabletop Dock": {
        "wake_word_mode": "Docked Only",
        "tap_to_wake": "Docked Only",
        "pickup_to_wake": "Disabled",
        "battery_screen_timeout": "30s",
        "docked_idle_timeout": "5 min",
        "battery_hibernate_timeout": "15 min",
        "docked_screensaver": True,
    },
    "Always-On Wall / Desk": {
        "wake_word_mode": "Always On",
        "tap_to_wake": "Always On",
        "pickup_to_wake": "Disabled",
        "battery_screen_timeout": "Never",
        "docked_idle_timeout": "5 min",
        "battery_hibernate_timeout": "Disabled",
        "docked_screensaver": True,
    },
}
POWER_PROFILE_SUBKEYS: frozenset[str] = frozenset(
    {
        "wake_word_mode",
        "tap_to_wake",
        "pickup_to_wake",
        "battery_screen_timeout",
        "docked_idle_timeout",
        "battery_hibernate_timeout",
        "docked_screensaver",
    }
)


def resolve_device_pref_value(cfg: Mapping[str, Any], key: str) -> Any:
    """Return the validated value for `key` from `cfg`, falling back to its spec default."""
    spec = DEVICE_PREF_SPEC_MAP[key]
    raw = cfg.get(key)
    if raw is None:
        return spec.default
    if spec.domain == "switch":
        if isinstance(raw, str):
            return raw.strip().lower() in ("1", "true", "on", "yes")
        return bool(raw)
    if spec.domain == "select":
        val = str(raw).strip()
        return val if val in spec.options else spec.default
    try:
        ival = int(raw)
    except (TypeError, ValueError):
        return spec.default
    if spec.min_val is not None:
        ival = max(spec.min_val, ival)
    if spec.max_val is not None:
        ival = min(spec.max_val, ival)
    return ival


DEVICE_TEXT_KEYS: tuple[str, ...] = (
    "device_group",
    "device_remote_group",
    "default_speaker",
    "ma_player_entity",
    "default_area",
    "ble_beacon_uuid",
    "ble_target_address",
    "assigned_person",
    "dock_apps",
    "area_categories",
    "home_categories",
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
    "wallpaper_cycle_minutes",
    "device_custom_color",
    "area_follow_dwell_s",
    *DEVICE_PREF_KEYS,
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
_REMOTE_GROUP_REF = re.compile(r"^group:[A-Za-z0-9_-]+$")


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


def clean_device_settings(
    incoming: Mapping[str, Any], current: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Validate and normalize a Device save."""
    _check_scope(incoming, DEVICE_SETTING_KEYS, "Device")
    out: dict[str, Any] = {}
    for key in DEVICE_TEXT_KEYS:
        if key in incoming:
            out[key] = _text(incoming[key])
    for key in DEVICE_BOOL_KEYS:
        if key in incoming:
            raw_b = incoming[key]
            if isinstance(raw_b, str):
                out[key] = raw_b.strip().lower() in ("1", "true", "on", "yes")
            else:
                out[key] = bool(raw_b)
    try:
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

    if "area_categories" in out:
        try:
            out["area_categories"] = normalize_area_categories(out["area_categories"])
        except ValueError as err:
            raise SettingsScopeError(str(err)) from None

    if "home_categories" in out:
        try:
            out["home_categories"] = normalize_home_categories(out["home_categories"])
        except ValueError as err:
            raise SettingsScopeError(str(err)) from None

    for spec in DEVICE_PREF_SPECS:
        if spec.key not in incoming:
            continue
        raw_v = incoming[spec.key]
        if spec.domain == "switch":
            if isinstance(raw_v, str):
                out[spec.key] = raw_v.strip().lower() in ("1", "true", "on", "yes")
            else:
                out[spec.key] = bool(raw_v)
        elif spec.domain == "select":
            opt_v = _text(raw_v)
            if opt_v not in spec.options:
                raise SettingsScopeError(
                    f"Unknown option for {spec.key}: {opt_v or '(empty)'}"
                )
            out[spec.key] = opt_v
        else:
            try:
                num_v = int(raw_v)
            except (TypeError, ValueError) as err:
                raise SettingsScopeError(f"Not a whole number: {err}") from None
            if spec.min_val is not None:
                num_v = max(spec.min_val, num_v)
            if spec.max_val is not None:
                num_v = min(spec.max_val, num_v)
            out[spec.key] = num_v

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
        out["start_screen"] = "Clock"

    if "power_profile" in out:
        preset = POWER_PROFILE_PREFS.get(str(out["power_profile"]))
        if preset is not None:
            for sub_k, sub_v in preset.items():
                if sub_k not in incoming:
                    out[sub_k] = sub_v
    elif any(sub_k in out for sub_k in POWER_PROFILE_SUBKEYS):
        cur_prof = (
            resolve_device_pref_value(current, "power_profile")
            if current is not None
            else "Custom"
        )
        preset = POWER_PROFILE_PREFS.get(str(cur_prof))
        if preset is None or any(
            sub_k in out and out[sub_k] != preset[sub_k]
            for sub_k in POWER_PROFILE_SUBKEYS
        ):
            out["power_profile"] = "Custom"

    if (
        out.get("native_ble_tracking") is True
        and "ble_auto_switch" not in incoming
        and current is not None
        and not bool(current.get("native_ble_tracking", True))
    ):
        out["ble_auto_switch"] = True

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
    if "device_remote_group" in out:
        rem_grp = out["device_remote_group"] or "area_auto"
        if rem_grp not in ("area_auto", "all") and not _REMOTE_GROUP_REF.match(rem_grp):
            raise SettingsScopeError(
                f"Unknown remote group mode: {rem_grp}"
            )
        out["device_remote_group"] = rem_grp
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
