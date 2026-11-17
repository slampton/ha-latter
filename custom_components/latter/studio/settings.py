"""Latter Studio settings scopes, command routing, target checks, and catalog push gate.

Standard library only (no Home Assistant imports), so unit tests exercise this exact code.
A System save writes only System settings (`.storage/latter.site`); a Device save writes only that
Device's settings (its config subentry). The websocket type is the command scope: `latter/system/command`
runs System commands and `latter/device/command` runs Device commands on the Device named by `subentry_id`.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any, Literal, Protocol, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    ZoneInfo("UTC")
    _SYSTEM_HAS_TZDATA = True
except ZoneInfoNotFoundError:
    _SYSTEM_HAS_TZDATA = False

_PROTOCOL_V3_DATA: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parent.parent / "protocol_v3.json").read_text(
        encoding="utf-8"
    )
)

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
        "set_ble_scanner_offset",
        "set_area_fusion",
        "capture_ble_area_signature",
        "clear_ble_area_signature",
        "system_entity_action",
        "send_announcement",
        "check_system_updates",
        "clear_internal_logs",
        "remove_device",
        "add_latter_device",
        "add_ble_device",
        "create_device_group",
        "delete_device_group",
        "update_group_baseline",
        "apply_batch_device_setting",
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
    "dismiss_ringing",
    "cancel_timer",
    "reset_stopwatch",
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
    "ble_attenuation",
    "ble_max_radius_m",
    "ble_max_velocity_mps",
    "ble_away_timeout_s",
)

@dataclass(frozen=True, slots=True)
class DevicePrefSpec:
    """Declarative specification for one Protocol v3 `device_prefs` subentry preference."""

    key: str
    label: str
    domain: Literal["select", "switch", "number", "text"]
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
    group_tier: Literal["behavior", "display", "interface"] | None
    options: tuple[str, ...] = ()
    min_val: int | None = None
    max_val: int | None = None
    step: int | None = None
    unit: str = ""


WAKE_WORD_MODE_OPTIONS: tuple[str, ...] = ("Docked Only", "Always On", "Disabled")
TAP_TO_WAKE_OPTIONS: tuple[str, ...] = (
    "Single Tap",
    "Double Tap",
    "Docked Only",
    "Disabled",
)
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
    "Pinned",
    "Time App",
    "Clock Face",
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
    "Modern Analog",
    "Hybrid Digital",
)
HOME_CLOCK_TAP_OPTIONS: tuple[str, ...] = ("Time App", "Clock Face")
TIME_FORMAT_OPTIONS: tuple[str, ...] = ("12-Hour (AM/PM)", "24-Hour")
MAX_WORLD_CLOCKS = 4
DEFAULT_ALARMS_SUMMARY = "07:00|0|1;08:30|0|2;09:00|0|2"

WORLD_CLOCK_CATALOG: tuple[dict[str, Any], ...] = (
    # Canonical standard time zones ordered from UTC-12:00 through UTC+14:00
    {"iana": "Etc/GMT+12", "city": "UTC-12", "std_off": -720, "dst_off": -720, "std_abbr": "UTC-12", "dst_abbr": "UTC-12", "rule": "none"},
    {"iana": "Pacific/Pago_Pago", "city": "Pago Pago", "std_off": -660, "dst_off": -660, "std_abbr": "SST", "dst_abbr": "SST", "rule": "none"},
    {"iana": "Pacific/Honolulu", "city": "Honolulu", "std_off": -600, "dst_off": -600, "std_abbr": "HST", "dst_abbr": "HST", "rule": "none"},
    {"iana": "Pacific/Marquesas", "city": "Marquesas", "std_off": -570, "dst_off": -570, "std_abbr": "MART", "dst_abbr": "MART", "rule": "none"},
    {"iana": "America/Anchorage", "city": "Anchorage", "std_off": -540, "dst_off": -480, "std_abbr": "AKST", "dst_abbr": "AKDT", "rule": "us"},
    {"iana": "America/Los_Angeles", "city": "Los Angeles", "std_off": -480, "dst_off": -420, "std_abbr": "PST", "dst_abbr": "PDT", "rule": "us"},
    {"iana": "Etc/GMT+8", "city": "UTC-8", "std_off": -480, "dst_off": -480, "std_abbr": "UTC-8", "dst_abbr": "UTC-8", "rule": "none"},
    {"iana": "America/Denver", "city": "Denver", "std_off": -420, "dst_off": -360, "std_abbr": "MST", "dst_abbr": "MDT", "rule": "us"},
    {"iana": "America/Phoenix", "city": "Phoenix", "std_off": -420, "dst_off": -420, "std_abbr": "MST", "dst_abbr": "MST", "rule": "none"},
    {"iana": "America/Chicago", "city": "Chicago", "std_off": -360, "dst_off": -300, "std_abbr": "CST", "dst_abbr": "CDT", "rule": "us"},
    {"iana": "America/Regina", "city": "Regina", "std_off": -360, "dst_off": -360, "std_abbr": "CST", "dst_abbr": "CST", "rule": "none"},
    {"iana": "America/New_York", "city": "New York", "std_off": -300, "dst_off": -240, "std_abbr": "EST", "dst_abbr": "EDT", "rule": "us"},
    {"iana": "America/Lima", "city": "Lima", "std_off": -300, "dst_off": -300, "std_abbr": "EST", "dst_abbr": "EST", "rule": "none"},
    {"iana": "America/Halifax", "city": "Halifax", "std_off": -240, "dst_off": -180, "std_abbr": "AST", "dst_abbr": "ADT", "rule": "us"},
    {"iana": "America/Puerto_Rico", "city": "Puerto Rico", "std_off": -240, "dst_off": -240, "std_abbr": "AST", "dst_abbr": "AST", "rule": "none"},
    {"iana": "America/St_Johns", "city": "St. John's", "std_off": -210, "dst_off": -150, "std_abbr": "NST", "dst_abbr": "NDT", "rule": "us"},
    {"iana": "America/Sao_Paulo", "city": "Sao Paulo", "std_off": -180, "dst_off": -180, "std_abbr": "BRT", "dst_abbr": "BRT", "rule": "none"},
    {"iana": "Etc/GMT+2", "city": "UTC-2", "std_off": -120, "dst_off": -120, "std_abbr": "UTC-2", "dst_abbr": "UTC-2", "rule": "none"},
    {"iana": "Atlantic/Azores", "city": "Azores", "std_off": -60, "dst_off": 0, "std_abbr": "AZOT", "dst_abbr": "AZOST", "rule": "eu"},
    {"iana": "Atlantic/Cape_Verde", "city": "Cape Verde", "std_off": -60, "dst_off": -60, "std_abbr": "CVT", "dst_abbr": "CVT", "rule": "none"},
    {"iana": "Atlantic/Reykjavik", "city": "Reykjavik", "std_off": 0, "dst_off": 0, "std_abbr": "GMT", "dst_abbr": "GMT", "rule": "none"},
    {"iana": "Europe/London", "city": "London", "std_off": 0, "dst_off": 60, "std_abbr": "GMT", "dst_abbr": "BST", "rule": "eu"},
    {"iana": "Europe/Berlin", "city": "Berlin", "std_off": 60, "dst_off": 120, "std_abbr": "CET", "dst_abbr": "CEST", "rule": "eu"},
    {"iana": "Africa/Lagos", "city": "Lagos", "std_off": 60, "dst_off": 60, "std_abbr": "WAT", "dst_abbr": "WAT", "rule": "none"},
    {"iana": "Europe/Athens", "city": "Athens", "std_off": 120, "dst_off": 180, "std_abbr": "EET", "dst_abbr": "EEST", "rule": "eu"},
    {"iana": "Africa/Johannesburg", "city": "Johannesburg", "std_off": 120, "dst_off": 120, "std_abbr": "SAST", "dst_abbr": "SAST", "rule": "none"},
    {"iana": "Asia/Riyadh", "city": "Riyadh", "std_off": 180, "dst_off": 180, "std_abbr": "AST", "dst_abbr": "AST", "rule": "none"},
    {"iana": "Asia/Tehran", "city": "Tehran", "std_off": 210, "dst_off": 210, "std_abbr": "IRST", "dst_abbr": "IRST", "rule": "none"},
    {"iana": "Asia/Dubai", "city": "Dubai", "std_off": 240, "dst_off": 240, "std_abbr": "GST", "dst_abbr": "GST", "rule": "none"},
    {"iana": "Asia/Kabul", "city": "Kabul", "std_off": 270, "dst_off": 270, "std_abbr": "AFT", "dst_abbr": "AFT", "rule": "none"},
    {"iana": "Asia/Karachi", "city": "Karachi", "std_off": 300, "dst_off": 300, "std_abbr": "PKT", "dst_abbr": "PKT", "rule": "none"},
    {"iana": "Asia/Kolkata", "city": "Kolkata", "std_off": 330, "dst_off": 330, "std_abbr": "IST", "dst_abbr": "IST", "rule": "none"},
    {"iana": "Asia/Kathmandu", "city": "Kathmandu", "std_off": 345, "dst_off": 345, "std_abbr": "NPT", "dst_abbr": "NPT", "rule": "none"},
    {"iana": "Asia/Dhaka", "city": "Dhaka", "std_off": 360, "dst_off": 360, "std_abbr": "BST", "dst_abbr": "BST", "rule": "none"},
    {"iana": "Asia/Yangon", "city": "Yangon", "std_off": 390, "dst_off": 390, "std_abbr": "MMT", "dst_abbr": "MMT", "rule": "none"},
    {"iana": "Asia/Bangkok", "city": "Bangkok", "std_off": 420, "dst_off": 420, "std_abbr": "ICT", "dst_abbr": "ICT", "rule": "none"},
    {"iana": "Asia/Singapore", "city": "Singapore", "std_off": 480, "dst_off": 480, "std_abbr": "SGT", "dst_abbr": "SGT", "rule": "none"},
    {"iana": "Australia/Eucla", "city": "Eucla", "std_off": 525, "dst_off": 525, "std_abbr": "ACWST", "dst_abbr": "ACWST", "rule": "none"},
    {"iana": "Asia/Tokyo", "city": "Tokyo", "std_off": 540, "dst_off": 540, "std_abbr": "JST", "dst_abbr": "JST", "rule": "none"},
    {"iana": "Australia/Adelaide", "city": "Adelaide", "std_off": 570, "dst_off": 630, "std_abbr": "ACST", "dst_abbr": "ACDT", "rule": "au"},
    {"iana": "Australia/Darwin", "city": "Darwin", "std_off": 570, "dst_off": 570, "std_abbr": "ACST", "dst_abbr": "ACST", "rule": "none"},
    {"iana": "Australia/Sydney", "city": "Sydney", "std_off": 600, "dst_off": 660, "std_abbr": "AEST", "dst_abbr": "AEDT", "rule": "au"},
    {"iana": "Australia/Brisbane", "city": "Brisbane", "std_off": 600, "dst_off": 600, "std_abbr": "AEST", "dst_abbr": "AEST", "rule": "none"},
    {"iana": "Australia/Lord_Howe", "city": "Lord Howe", "std_off": 630, "dst_off": 660, "std_abbr": "LHST", "dst_abbr": "LHDT", "rule": "au30"},
    {"iana": "Pacific/Guadalcanal", "city": "Guadalcanal", "std_off": 660, "dst_off": 660, "std_abbr": "SBT", "dst_abbr": "SBT", "rule": "none"},
    {"iana": "Pacific/Auckland", "city": "Auckland", "std_off": 720, "dst_off": 780, "std_abbr": "NZST", "dst_abbr": "NZDT", "rule": "nz"},
    {"iana": "Etc/GMT-12", "city": "UTC+12", "std_off": 720, "dst_off": 720, "std_abbr": "UTC+12", "dst_abbr": "UTC+12", "rule": "none"},
    {"iana": "Pacific/Chatham", "city": "Chatham", "std_off": 765, "dst_off": 825, "std_abbr": "CHAST", "dst_abbr": "CHADT", "rule": "nz"},
    {"iana": "Pacific/Tongatapu", "city": "Tongatapu", "std_off": 780, "dst_off": 780, "std_abbr": "TOT", "dst_abbr": "TOT", "rule": "none"},
    {"iana": "Pacific/Kiritimati", "city": "Kiritimati", "std_off": 840, "dst_off": 840, "std_abbr": "LINT", "dst_abbr": "LINT", "rule": "none"},
    # Additional regional aliases supported when host lacks system tzdata
    {"iana": "America/Toronto", "city": "Toronto", "std_off": -300, "dst_off": -240, "std_abbr": "EST", "dst_abbr": "EDT", "rule": "us"},
    {"iana": "America/Argentina/Buenos_Aires", "city": "Buenos Aires", "std_off": -180, "dst_off": -180, "std_abbr": "ART", "dst_abbr": "ART", "rule": "none"},
    {"iana": "Europe/Paris", "city": "Paris", "std_off": 60, "dst_off": 120, "std_abbr": "CET", "dst_abbr": "CEST", "rule": "eu"},
    {"iana": "Europe/Zurich", "city": "Zurich", "std_off": 60, "dst_off": 120, "std_abbr": "CET", "dst_abbr": "CEST", "rule": "eu"},
    {"iana": "Africa/Cairo", "city": "Cairo", "std_off": 120, "dst_off": 180, "std_abbr": "EET", "dst_abbr": "EEST", "rule": "eg"},
    {"iana": "Asia/Hong_Kong", "city": "Hong Kong", "std_off": 480, "dst_off": 480, "std_abbr": "HKT", "dst_abbr": "HKT", "rule": "none"},
    {"iana": "Asia/Shanghai", "city": "Shanghai", "std_off": 480, "dst_off": 480, "std_abbr": "CST", "dst_abbr": "CST", "rule": "none"},
    {"iana": "Asia/Seoul", "city": "Seoul", "std_off": 540, "dst_off": 540, "std_abbr": "KST", "dst_abbr": "KST", "rule": "none"},
)
WORLD_CLOCK_CATALOG_MAP: dict[str, dict[str, Any]] = {
    str(item["iana"]): item for item in WORLD_CLOCK_CATALOG
}
_IANA_ZONE_RE = re.compile(r"^[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)+$")
_PINNED_UTC_ALIASES: frozenset[str] = frozenset(
    {"UTC", "Etc/UTC", "GMT", "Etc/GMT", "Etc/GMT+0", "Etc/GMT-0", "Etc/GMT0"}
)
_ALARM_RECORD_RE = re.compile(r"^(\d{1,2}):(\d{2})\|([01])\|([0-3])$")


def is_valid_iana_zone(iana: str) -> bool:
    """Return True when `iana` is a valid non-UTC IANA zone ID."""
    tok = str(iana or "").strip()
    if not tok or len(tok) > 48 or tok in _PINNED_UTC_ALIASES:
        return False
    if not _IANA_ZONE_RE.match(tok):
        return False
    if tok in WORLD_CLOCK_CATALOG_MAP:
        return True
    if _SYSTEM_HAS_TZDATA:
        try:
            ZoneInfo(tok)
            return True
        except (ZoneInfoNotFoundError, ValueError):
            return False
    return False


def sanitize_clock_label(val: Any, max_bytes: int = 32) -> str:
    """Return a single-line delimiter-safe clock label truncated cleanly to `max_bytes` UTF-8 bytes."""
    raw = str(val or "")
    chars: list[str] = []
    prev_space = True
    for ch in raw:
        code = ord(ch)
        if (
            code < 0x20
            or code == 0x7F
            or ch in ("|", ";", "\x1e", "\x1f", " ", "\t", "\r", "\n")
        ):
            if not prev_space:
                chars.append(" ")
                prev_space = True
            continue
        chars.append(ch)
        prev_space = False
    cleaned = "".join(chars).strip()
    encoded = cleaned.encode("utf-8")
    if len(encoded) > max_bytes:
        cleaned = encoded[:max_bytes].decode("utf-8", errors="ignore").rstrip()
    return cleaned


def default_city_for_iana(iana: str) -> str:
    """Return the catalog city or humanized IANA tail for `iana`."""
    clean = str(iana or "").strip()
    cat = WORLD_CLOCK_CATALOG_MAP.get(clean)
    if cat is not None:
        return str(cat["city"])
    tail = clean.rsplit("/", 1)[-1].replace("_", " ")
    return sanitize_clock_label(tail) or clean


def parse_world_clocks_spec(
    val: Any, *, strict: bool = False
) -> list[tuple[str, str]]:
    """Parse and validate up to 4 `'<label>|<iana>'` World Clock entries."""
    if val is None:
        return []
    raw_items: Iterable[Any]
    if isinstance(val, (list, tuple)):
        raw_items = val
    else:
        raw_items = str(val).split(";")

    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_items:
        if isinstance(raw, Mapping):
            raw_lbl = str(raw.get("label") or "")
            iana = str(raw.get("iana") or "").strip()
            if not iana and not raw_lbl.strip():
                continue
        else:
            rec = str(raw or "").strip()
            if not rec:
                continue
            if "|" not in rec:
                if strict:
                    raise ValueError(
                        f"Invalid World Clock record (expected '<label>|<iana>'): {rec}"
                    )
                continue
            raw_lbl, raw_iana = rec.split("|", 1)
            iana = raw_iana.strip()

        if iana in _PINNED_UTC_ALIASES:
            if strict:
                raise ValueError(
                    "Use Show UTC Clock instead of adding UTC to World Clocks"
                )
            continue
        if not is_valid_iana_zone(iana):
            if strict:
                raise ValueError(f"Unknown IANA time zone: {iana or '(empty)'}")
            continue

        cleaned_lbl = sanitize_clock_label(raw_lbl)
        if not cleaned_lbl and strict:
            raise ValueError("World Clock city label is required")
        lbl = cleaned_lbl or default_city_for_iana(iana)
        dedup_key = (lbl.lower(), iana)
        if dedup_key in seen:
            continue
        if len(out) >= MAX_WORLD_CLOCKS:
            if strict:
                raise ValueError(
                    f"A Device supports at most {MAX_WORLD_CLOCKS} World Clocks"
                )
            break
        seen.add(dedup_key)
        out.append((lbl, iana))
    return out


def normalize_world_clocks_spec(val: Any, *, strict: bool = False) -> str:
    """Validate and canonicalize up to 4 semicolon-delimited `'<label>|<iana>'` World Clocks."""
    return ";".join(
        f"{lbl}|{iana}"
        for lbl, iana in parse_world_clocks_spec(val, strict=strict)
    )


def normalize_alarms_summary(val: Any, *, strict: bool = False) -> str:
    """Validate and canonicalize 3 semicolon-separated `HH:MM|0..1|0..3` alarm records."""
    text = str(val or "").strip()
    if not text:
        if strict:
            raise ValueError("Alarms summary requires 3 alarm slots")
        return DEFAULT_ALARMS_SUMMARY
    parts = [p.strip() for p in text.split(";")]
    if len(parts) != 3:
        if strict:
            raise ValueError("Alarms summary requires exactly 3 semicolon-separated slots")
        return DEFAULT_ALARMS_SUMMARY
    normalized: list[str] = []
    for part in parts:
        m = _ALARM_RECORD_RE.match(part)
        if not m:
            if strict:
                raise ValueError(f"Invalid alarm record: {part or '(empty)'}")
            return DEFAULT_ALARMS_SUMMARY
        hh, mm, en, rec = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        if not (0 <= hh <= 23 and 0 <= mm <= 59):
            if strict:
                raise ValueError(f"Alarm time out of range: {part}")
            return DEFAULT_ALARMS_SUMMARY
        normalized.append(f"{hh:02d}:{mm:02d}|{en}|{rec}")
    return ";".join(normalized)
AREA_CATEGORIES_CATALOG: tuple[dict[str, Any], ...] = tuple(
    _PROTOCOL_V3_DATA["catalogs"]["area_categories"]
)
AREA_CATEGORY_TOKENS: tuple[str, ...] = tuple(
    c["token"] for c in AREA_CATEGORIES_CATALOG
)
DEFAULT_AREA_CATEGORIES: str = _PROTOCOL_V3_DATA["defaults"]["area_categories"]


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


HOME_CATEGORIES_CATALOG: tuple[dict[str, Any], ...] = tuple(
    _PROTOCOL_V3_DATA["catalogs"]["home_categories"]
)
HOME_CATEGORY_TOKENS: tuple[str, ...] = tuple(
    c["token"] for c in HOME_CATEGORIES_CATALOG
)
DEFAULT_HOME_CATEGORIES: str = _PROTOCOL_V3_DATA["defaults"]["home_categories"]


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


TOOLS_ITEMS_CATALOG: tuple[dict[str, Any], ...] = tuple(
    _PROTOCOL_V3_DATA["catalogs"]["tools_items"]
)
TOOLS_ITEM_TOKENS: tuple[str, ...] = tuple(
    c["token"] for c in TOOLS_ITEMS_CATALOG
)
DEFAULT_TOOLS_ITEMS: str = str(_PROTOCOL_V3_DATA["defaults"]["tools_items"])


def parse_tools_items(csv: Any) -> list[str]:
    """Return the known Tools launcher tokens named in `csv`, in order, without duplicates."""
    raw_items = csv if isinstance(csv, (list, tuple)) else str(csv or "").split(",")
    out: list[str] = []
    for raw in raw_items:
        tok = str(raw).strip().lower()
        if tok in TOOLS_ITEM_TOKENS and tok not in out:
            out.append(tok)
    return out


def normalize_tools_items(csv: Any) -> str:
    """Return `csv` as canonical comma-separated Tools items; raise ValueError if empty or unknown."""
    raw_items = csv if isinstance(csv, (list, tuple)) else str(csv or "").split(",")
    names = [str(t).strip().lower() for t in raw_items if str(t).strip()]
    unknown = sorted({t for t in names if t not in TOOLS_ITEM_TOKENS})
    if unknown:
        raise ValueError(f"Unknown Tool: {', '.join(unknown)}")
    items = parse_tools_items(csv)
    if not items:
        raise ValueError("Keep at least one Tool enabled")
    return ",".join(items)


GAMES_ITEMS_CATALOG: tuple[dict[str, Any], ...] = tuple(
    _PROTOCOL_V3_DATA["catalogs"]["games_items"]
)
GAMES_ITEM_TOKENS: tuple[str, ...] = tuple(
    c["token"] for c in GAMES_ITEMS_CATALOG
)
DEFAULT_GAMES_ITEMS: str = str(_PROTOCOL_V3_DATA["defaults"]["games_items"])


def parse_games_items(csv: Any) -> list[str]:
    """Return the known Games launcher tokens named in `csv`, in order, without duplicates."""
    raw_items = csv if isinstance(csv, (list, tuple)) else str(csv or "").split(",")
    out: list[str] = []
    for raw in raw_items:
        tok = str(raw).strip().lower()
        if tok in GAMES_ITEM_TOKENS and tok not in out:
            out.append(tok)
    return out


def normalize_games_items(csv: Any) -> str:
    """Return `csv` as canonical comma-separated Games items; raise ValueError if empty or unknown."""
    raw_items = csv if isinstance(csv, (list, tuple)) else str(csv or "").split(",")
    names = [str(t).strip().lower() for t in raw_items if str(t).strip()]
    unknown = sorted({t for t in names if t not in GAMES_ITEM_TOKENS})
    if unknown:
        raise ValueError(f"Unknown Game: {', '.join(unknown)}")
    items = parse_games_items(csv)
    if not items:
        raise ValueError("Keep at least one Game enabled")
    return ",".join(items)


ACTIVITY_SOURCES_CATALOG: tuple[dict[str, Any], ...] = tuple(
    _PROTOCOL_V3_DATA["catalogs"]["activity_sources"]
)
ACTIVITY_SOURCE_KEYS: tuple[str, ...] = tuple(
    c["token"] for c in ACTIVITY_SOURCES_CATALOG
)
DEFAULT_ACTIVITY_SOURCES: str = str(_PROTOCOL_V3_DATA["defaults"]["activity_sources"])


def normalize_activity_sources(value: Any) -> str:
    """Return the sources as canonical CSV ("" = every source off); raise ValueError for an unknown key."""
    raw = value if isinstance(value, (list, tuple)) else str(value or "").split(",")
    names = {str(t).strip().lower() for t in raw if str(t).strip()}
    unknown = sorted(names - set(ACTIVITY_SOURCE_KEYS))
    if unknown:
        raise ValueError(f"Unknown Activity Card source: {', '.join(unknown)}")
    return ",".join(k for k in ACTIVITY_SOURCE_KEYS if k in names)


# ---------------------------------------------------------------------------
# Universal Shortcut Engine (`dock_items` & `pinned_items`)
# ---------------------------------------------------------------------------

SHORTCUT_ROUTES_CATALOG: tuple[dict[str, Any], ...] = tuple(
    _PROTOCOL_V3_DATA["catalogs"]["shortcut_routes"]
)
SHORTCUT_ROUTE_MAP: dict[str, dict[str, Any]] = {
    str(r["token"]): r for r in SHORTCUT_ROUTES_CATALOG
}
SHORTCUT_ROUTE_TOKENS: tuple[str, ...] = tuple(SHORTCUT_ROUTE_MAP.keys())
DEFAULT_DOCK_ROUTES: str = str(_PROTOCOL_V3_DATA["defaults"]["dock_routes"])

MAX_DOCK_ITEMS = 24
MAX_PINNED_ITEMS = 96
SHORTCUT_LABEL_MAX = 24

SHORTCUT_DOMAIN_ACTIONS: dict[str, tuple[tuple[str, str], ...]] = {
    "light": (("toggle", "Toggle"), ("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "switch": (("toggle", "Toggle"), ("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "input_boolean": (("toggle", "Toggle"), ("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "fan": (("toggle", "Toggle"), ("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "cover": (
        ("toggle", "Toggle"),
        ("open_cover", "Open"),
        ("close_cover", "Close"),
        ("stop_cover", "Stop"),
    ),
    "valve": (
        ("toggle", "Toggle"),
        ("open_valve", "Open"),
        ("close_valve", "Close"),
        ("stop_valve", "Stop"),
    ),
    "scene": (("turn_on", "Activate"),),
    "script": (("turn_on", "Run"), ("turn_off", "Stop")),
    "automation": (
        ("trigger", "Trigger"),
        ("toggle", "Toggle Enable"),
        ("turn_on", "Enable"),
        ("turn_off", "Disable"),
    ),
    "button": (("press", "Press"),),
    "input_button": (("press", "Press"),),
    "lock": (("lock", "Lock"), ("unlock", "Unlock"), ("open", "Unlatch")),
    "alarm_control_panel": (
        ("disarm", "Disarm"),
        ("arm_home", "Arm Home"),
        ("arm_away", "Arm Away"),
        ("arm_night", "Arm Night"),
        ("arm_vacation", "Arm Vacation"),
    ),
    "vacuum": (
        ("start", "Start"),
        ("pause", "Pause"),
        ("return_to_base", "Return To Base"),
        ("stop", "Stop"),
        ("clean_spot", "Spot Clean"),
        ("locate", "Locate"),
    ),
    "lawn_mower": (
        ("start_mowing", "Start Mowing"),
        ("pause", "Pause"),
        ("dock", "Dock"),
    ),
    "media_player": (
        ("media_play_pause", "Play / Pause"),
        ("turn_on", "Turn On"),
        ("turn_off", "Turn Off"),
        ("media_next_track", "Next Track"),
    ),
    "climate": (("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "humidifier": (("toggle", "Toggle"), ("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "siren": (("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "water_heater": (("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "select": (("select_next", "Next Option"), ("select_previous", "Previous Option")),
    "input_select": (("select_next", "Next Option"), ("select_previous", "Previous Option")),
}
SHORTCUT_SUPPORTED_DOMAINS: frozenset[str] = frozenset(SHORTCUT_DOMAIN_ACTIONS.keys())
SHORTCUT_DOMAIN_ACTION_SETS: dict[str, frozenset[str]] = {
    dom: frozenset(act for act, _ in acts)
    for dom, acts in SHORTCUT_DOMAIN_ACTIONS.items()
}
_MDI_ICON_RE = re.compile(r"^mdi:[a-z0-9]+(?:-[a-z0-9]+)*$")
_ENTITY_ID_RE = re.compile(r"^([a-z0-9_]+)\.([a-z0-9_]+)$")


def default_dock_items() -> list[dict[str, Any]]:
    """Return the canonical default Home Dock `ShortcutItem` list."""
    out: list[dict[str, Any]] = []
    for raw in DEFAULT_DOCK_ROUTES.split(","):
        tok = raw.strip().lower()
        if tok in SHORTCUT_ROUTE_MAP and tok != "settings:root":
            out.append(
                {
                    "kind": "route",
                    "target": tok,
                    "action": "",
                    "label": "",
                    "icon": "",
                    "confirm": False,
                }
            )
    return out


def sanitize_shortcut_label(val: Any, max_chars: int = SHORTCUT_LABEL_MAX) -> str:
    """Return a single-line delimiter-safe shortcut label capped at `max_chars` characters."""
    raw = str(val or "")
    chars: list[str] = []
    prev_space = True
    for ch in raw:
        code = ord(ch)
        if (
            code < 0x20
            or code == 0x7F
            or ch in ("|", "\x1e", "\x1f", " ", "\t", "\r", "\n")
        ):
            if not prev_space:
                chars.append(" ")
                prev_space = True
            continue
        chars.append(ch)
        prev_space = False
    cleaned = "".join(chars).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip()
    return cleaned


def normalize_mdi_icon(val: Any, *, strict: bool = False) -> str:
    """Validate and normalize an optional `mdi:<slug>` icon string (`""` = default icon)."""
    raw = str(val or "").strip().lower().replace("_", "-")
    if not raw:
        return ""
    if raw.startswith("mdi-"):
        raw = "mdi:" + raw[4:]
    elif not raw.startswith("mdi:") and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", raw):
        raw = f"mdi:{raw}"
    if _MDI_ICON_RE.fullmatch(raw):
        return raw
    if strict:
        raise ValueError(f"Invalid MDI icon: {val!r}")
    return ""


def normalize_shortcut_item(
    raw: Any,
    *,
    is_dock: bool,
    strict: bool = True,
) -> dict[str, Any] | None:
    """Validate and normalize one `ShortcutItem` dict (`route` or `entity`)."""
    if not isinstance(raw, Mapping):
        if strict:
            raise ValueError("Each shortcut item must be an object")
        return None
    kind = str(raw.get("kind") or "").strip().lower()
    if kind == "route":
        target = str(raw.get("target") or "").strip().lower()
        if is_dock and target in ("settings:root", "app:settings"):
            # Settings is always rendered last on the Home Dock by firmware.
            return None
        spec = SHORTCUT_ROUTE_MAP.get(target)
        if spec is None:
            if strict:
                raise ValueError(f"Unknown shortcut route: {target or '(empty)'}")
            return None
        if not is_dock and bool(spec.get("dock_only")):
            if strict:
                raise ValueError(f"Route '{target}' can only be placed on the App Dock")
            return None
        label = sanitize_shortcut_label(raw.get("label"))
        icon = normalize_mdi_icon(raw.get("icon"), strict=strict)
        return {
            "kind": "route",
            "target": target,
            "action": "",
            "label": label,
            "icon": icon,
            "confirm": False,
        }

    if kind == "entity":
        target = str(raw.get("target") or "").strip().lower()
        m_ent = _ENTITY_ID_RE.fullmatch(target)
        if not m_ent:
            if strict:
                raise ValueError(f"Invalid entity_id: {target or '(empty)'}")
            return None
        domain = m_ent.group(1)
        allowed_actions = SHORTCUT_DOMAIN_ACTION_SETS.get(domain)
        if allowed_actions is None:
            if strict:
                raise ValueError(f"Unsupported shortcut entity domain: {domain}")
            return None
        action = str(raw.get("action") or "").strip().lower()
        if not action and not strict:
            action = SHORTCUT_DOMAIN_ACTIONS[domain][0][0]
        if action not in allowed_actions:
            if strict:
                raise ValueError(
                    f"Unsupported action '{action or '(empty)'}' for domain '{domain}'"
                )
            return None
        label = sanitize_shortcut_label(raw.get("label"))
        icon = normalize_mdi_icon(raw.get("icon"), strict=strict)
        raw_confirm = raw.get("confirm")
        if raw_confirm is None:
            confirm = bool(is_dock)
        elif isinstance(raw_confirm, str):
            confirm = raw_confirm.strip().lower() in ("1", "true", "on", "yes")
        else:
            confirm = bool(raw_confirm)
        return {
            "kind": "entity",
            "target": target,
            "action": action,
            "label": label,
            "icon": icon,
            "confirm": confirm,
        }

    if strict:
        raise ValueError(f"Unknown shortcut kind: {kind or '(empty)'}")
    return None


def _normalize_shortcut_list(
    val: Any,
    *,
    is_dock: bool,
    max_items: int,
    strict: bool,
) -> list[dict[str, Any]]:
    if not isinstance(val, (list, tuple)):
        if strict:
            name = "dock_items" if is_dock else "pinned_items"
            raise ValueError(f"{name} must be a list")
        return default_dock_items() if is_dock else []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for raw in val:
        norm = normalize_shortcut_item(raw, is_dock=is_dock, strict=strict)
        if norm is None:
            continue
        dedup_key = (norm["kind"], norm["target"], norm["action"])
        if dedup_key in seen:
            continue
        if len(out) >= max_items:
            if strict:
                label = "App Dock" if is_dock else "Pinned App"
                raise ValueError(f"{label} supports at most {max_items} shortcuts")
            break
        seen.add(dedup_key)
        out.append(norm)
    return out


def normalize_dock_items(
    val: Any, *, strict: bool = False
) -> list[dict[str, Any]]:
    """Validate and normalize a Device's `dock_items` list (`None` -> default Home Dock)."""
    if val is None:
        return default_dock_items()
    return _normalize_shortcut_list(
        val, is_dock=True, max_items=MAX_DOCK_ITEMS, strict=strict
    )


def normalize_pinned_items(
    val: Any, *, strict: bool = False
) -> list[dict[str, Any]]:
    """Validate and normalize a Device's `pinned_items` list (`None` -> `[]`)."""
    if val is None:
        return []
    return _normalize_shortcut_list(
        val, is_dock=False, max_items=MAX_PINNED_ITEMS, strict=strict
    )


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
    DevicePrefSpec("wake_word_mode", "Wake Word Mode", "select", "Docked Only", "audio", "mic", "behavior", options=WAKE_WORD_MODE_OPTIONS),
    DevicePrefSpec("tap_to_wake", "Tap to Wake", "select", "Docked Only", "power", "display", "behavior", options=TAP_TO_WAKE_OPTIONS),
    DevicePrefSpec("pickup_to_wake", "Pickup to Wake", "select", "Docked Only", "power", "display_imu", "behavior", options=WAKE_GESTURE_OPTIONS),
    DevicePrefSpec("battery_screen_timeout", "Battery Screen Timeout", "select", "30s", "power", "display_battery", "behavior", options=BATTERY_SCREEN_TIMEOUT_OPTIONS),
    DevicePrefSpec("docked_idle_timeout", "Docked Idle Timeout", "select", "1 min", "display", "display", "behavior", options=DOCKED_IDLE_TIMEOUT_OPTIONS),
    DevicePrefSpec("battery_hibernate_timeout", "Battery Hibernate Timeout", "select", "15 min", "power", "display_battery", "behavior", options=BATTERY_HIBERNATE_TIMEOUT_OPTIONS),
    DevicePrefSpec("docked_screensaver", "Docked Screensaver", "switch", True, "display", "display", "behavior"),
    DevicePrefSpec("screensaver_style", "Screensaver Style", "select", "Ambient Clock", "display", "display", "display", options=SCREENSAVER_STYLE_OPTIONS),
    DevicePrefSpec("hold_crown_power_off", "Hold Crown to Power Off", "switch", False, "power", "display_battery", "behavior"),
    DevicePrefSpec("auto_brightness_mode", "Auto Brightness Mode", "select", "Sun Synchronized", "display", "display", "behavior", options=AUTO_BRIGHTNESS_MODE_OPTIONS),
    DevicePrefSpec("manual_brightness", "Manual Brightness", "select", "90%", "display", "display", "behavior", options=BRIGHTNESS_PCT_OPTIONS),
    DevicePrefSpec("day_brightness", "Day Brightness", "select", "90%", "display", "display", "behavior", options=BRIGHTNESS_PCT_OPTIONS),
    DevicePrefSpec("night_brightness", "Night Brightness", "select", "70%", "display", "display", "behavior", options=BRIGHTNESS_PCT_OPTIONS),
    DevicePrefSpec("day_start_hour", "Day Start Hour", "number", 7, "display", "display", "behavior", min_val=0, max_val=23, step=1, unit="h"),
    DevicePrefSpec("night_start_hour", "Night Start Hour", "number", 20, "display", "display", "behavior", min_val=0, max_val=23, step=1, unit="h"),
    DevicePrefSpec("color_profile", "Color Profile", "select", "Steel Blue", "display", "display", "display", options=COLOR_PROFILE_OPTIONS),
    DevicePrefSpec("va_visual_profile", "Visual Profile", "select", "Nebula", "display", "display", "display", options=VA_VISUAL_PROFILE_OPTIONS),
    DevicePrefSpec("home_screen_enabled", "Enable Home Screen", "switch", True, "interface", "display", "interface"),
    DevicePrefSpec("start_screen", "Start Screen", "select", "Home", "interface", "display", "interface", options=START_SCREEN_OPTIONS),
    DevicePrefSpec("return_to_home_timeout", "Return to Home Timeout", "select", "2 min", "interface", "display", "interface", options=RETURN_TO_HOME_TIMEOUT_OPTIONS),
    DevicePrefSpec("clock_face", "Clock Face", "select", "Minimal Digital", "display", "display", "display", options=CLOCK_FACE_OPTIONS),
    DevicePrefSpec("time_format", "Time Format", "select", "12-Hour (AM/PM)", "display", "display", "display", options=TIME_FORMAT_OPTIONS),
    DevicePrefSpec("weather_background", "Weather Background", "switch", True, "display", "display", "display"),
    DevicePrefSpec("home_sun", "Sun", "switch", True, "display", "display", "display"),
    DevicePrefSpec("home_moon", "Moon", "switch", True, "display", "display", "display"),
    DevicePrefSpec("wake_greeting", "Wake Greeting", "switch", True, "display", "display", "display"),
    DevicePrefSpec("album_art_style", "Album Art Style", "select", "Full Screen", "display", "display", "display", options=ALBUM_ART_STYLE_OPTIONS),
    DevicePrefSpec("music_overlay_style", "Overlay Style", "select", "Art + Metadata", "display", "display", "display", options=MUSIC_OVERLAY_STYLE_OPTIONS),
    DevicePrefSpec("show_speaker_shortcut", "Show Speaker Shortcut", "switch", True, "interface", "display", "interface"),
    DevicePrefSpec("show_library_shortcut", "Show Library Shortcut", "switch", True, "interface", "display", "interface"),
    DevicePrefSpec("album_sort_order", "Album Sort Order", "select", "Alphabetical", "interface", "display", "interface", options=ALBUM_SORT_OPTIONS),
    DevicePrefSpec("artist_album_sort_order", "Artist Album Sort Order", "select", "Oldest on Top", "interface", "display", "interface", options=ARTIST_ALBUM_SORT_OPTIONS),
    DevicePrefSpec("podcast_sort_order", "Podcast Sort Order", "select", "Newest on Top", "interface", "display", "interface", options=PODCAST_SORT_OPTIONS),
    DevicePrefSpec("ww_sens_okay_nabu", "Okay Nabu Sensitivity", "select", "Moderately sensitive", "audio", "mic", "behavior", options=WW_SENSITIVITY_OPTIONS),
    DevicePrefSpec("ww_sens_hey_luna", "Hey Luna Sensitivity", "select", "Moderately sensitive", "audio", "mic", "behavior", options=WW_SENSITIVITY_OPTIONS),
    DevicePrefSpec("ww_sens_hey_jarvis", "Hey Jarvis Sensitivity", "select", "Moderately sensitive", "audio", "mic", "behavior", options=WW_SENSITIVITY_OPTIONS),
    DevicePrefSpec("ww_sens_hey_mycroft", "Hey Mycroft Sensitivity", "select", "Moderately sensitive", "audio", "mic", "behavior", options=WW_SENSITIVITY_OPTIONS),
    DevicePrefSpec("ww_sens_alexa", "Alexa Sensitivity", "select", "Moderately sensitive", "audio", "mic", "behavior", options=WW_SENSITIVITY_OPTIONS),
    DevicePrefSpec("wake_screen_on_assist", "Wake Screen on Assist", "switch", True, "audio", "display", "behavior"),
    DevicePrefSpec("alert_volume", "Alert Volume", "number", 80, "audio", "speaker", "behavior", min_val=20, max_val=100, step=5, unit="%"),
    DevicePrefSpec("volume_step_size", "Volume Step Size", "number", 5, "audio", "speaker", "behavior", min_val=1, max_val=10, step=1, unit="%"),
    DevicePrefSpec("game_sound_effects", "Game Sound Effects", "switch", True, "audio", "display", "behavior"),
    DevicePrefSpec("ble_beacon_mode", "BLE Beacon Mode", "select", "Handheld Only", "presence", "beacon_battery", "behavior", options=BLE_BEACON_MODE_OPTIONS),
    DevicePrefSpec("weather_sim_condition", "Weather Simulation", "select", "Live (Home Assistant)", "developer", "display", None, options=WEATHER_SIM_CONDITION_OPTIONS),
    DevicePrefSpec("home_clock_tap_action", "Home Time Tap", "select", "Time App", "interface", "display", "interface", options=HOME_CLOCK_TAP_OPTIONS),
    DevicePrefSpec("local_clock_label", "Local Clock Label", "text", "", "time", "display", None),
    DevicePrefSpec("show_utc_clock", "Show UTC Clock", "switch", False, "interface", "display", "interface"),
    DevicePrefSpec("world_clocks", "World Clocks", "text", "", "interface", "display", "interface"),
    DevicePrefSpec("alarms_summary", "Alarms", "text", DEFAULT_ALARMS_SUMMARY, "time", "display", None),
)

DEVICE_PREF_SPEC_MAP: dict[str, DevicePrefSpec] = {s.key: s for s in DEVICE_PREF_SPECS}
DEVICE_PREF_KEYS: tuple[str, ...] = tuple(s.key for s in DEVICE_PREF_SPECS)


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
    if spec.domain == "text":
        if key == "world_clocks":
            return normalize_world_clocks_spec(raw, strict=False)
        if key == "local_clock_label":
            return sanitize_clock_label(raw)
        if key == "alarms_summary":
            return normalize_alarms_summary(raw, strict=False)
        return str(raw).strip()
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
    "area_categories",
    "home_categories",
    "tools_items",
    "games_items",
    "activity_sources",
    "wallpaper_source",
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
    "dock_items",
    "pinned_items",
    "wallpaper_cycle_minutes",
    "device_custom_color",
    "area_follow_dwell_s",
    "ble_ref_power",
    *DEVICE_PREF_KEYS,
)

MAX_LIST_ITEMS = 10
MAX_CALENDARS = 50
MAX_CUSTOM_PALETTES = 24
DWELL_MIN_S = 3
DWELL_MAX_S = 60
DEFAULT_BLE_ATTENUATION = 2.2
BLE_ATTENUATION_MIN = 1.5
BLE_ATTENUATION_MAX = 4.5
DEFAULT_BLE_MAX_RADIUS_M = 12.0
BLE_MAX_RADIUS_MIN_M = 2.0
BLE_MAX_RADIUS_MAX_M = 50.0
DEFAULT_BLE_MAX_VELOCITY_MPS = 3.5
BLE_MAX_VELOCITY_MIN_MPS = 0.5
BLE_MAX_VELOCITY_MAX_MPS = 15.0
DEFAULT_BLE_AWAY_TIMEOUT_S = 180
BLE_AWAY_TIMEOUT_MIN_S = 30
BLE_AWAY_TIMEOUT_MAX_S = 900
BLE_REF_POWER_MIN_DBM = -90
BLE_REF_POWER_MAX_DBM = -30
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


def _ble_float(
    val: Any, default: float, lo: float, hi: float, ndigits: int, *, strict: bool = False
) -> float:
    if val is None or (isinstance(val, str) and not val.strip()):
        return default
    if isinstance(val, bool):
        if strict:
            raise SettingsScopeError("Expected a number, not a boolean")
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


def _ble_int(
    val: Any, default: int, lo: int, hi: int, *, strict: bool = False
) -> int:
    if val is None or (isinstance(val, str) and not val.strip()):
        return default
    if isinstance(val, bool):
        if strict:
            raise SettingsScopeError("Expected a whole number, not a boolean")
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
    if "ble_attenuation" in incoming:
        out["ble_attenuation"] = _ble_float(
            incoming["ble_attenuation"],
            DEFAULT_BLE_ATTENUATION,
            BLE_ATTENUATION_MIN,
            BLE_ATTENUATION_MAX,
            2,
            strict=True,
        )
    if "ble_max_radius_m" in incoming:
        out["ble_max_radius_m"] = _ble_float(
            incoming["ble_max_radius_m"],
            DEFAULT_BLE_MAX_RADIUS_M,
            BLE_MAX_RADIUS_MIN_M,
            BLE_MAX_RADIUS_MAX_M,
            1,
            strict=True,
        )
    if "ble_max_velocity_mps" in incoming:
        out["ble_max_velocity_mps"] = _ble_float(
            incoming["ble_max_velocity_mps"],
            DEFAULT_BLE_MAX_VELOCITY_MPS,
            BLE_MAX_VELOCITY_MIN_MPS,
            BLE_MAX_VELOCITY_MAX_MPS,
            1,
            strict=True,
        )
    if "ble_away_timeout_s" in incoming:
        out["ble_away_timeout_s"] = _ble_int(
            incoming["ble_away_timeout_s"],
            DEFAULT_BLE_AWAY_TIMEOUT_S,
            BLE_AWAY_TIMEOUT_MIN_S,
            BLE_AWAY_TIMEOUT_MAX_S,
            strict=True,
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

    if "ble_ref_power" in incoming:
        raw_ref = incoming["ble_ref_power"]
        if raw_ref is None or (isinstance(raw_ref, str) and not raw_ref.strip()):
            out["ble_ref_power"] = None
        elif isinstance(raw_ref, bool):
            raise SettingsScopeError("ble_ref_power must be an integer in -90..-30 dBm")
        else:
            try:
                ref_f = float(raw_ref)
            except (TypeError, ValueError) as err:
                raise SettingsScopeError(f"Invalid ble_ref_power: {err}") from None
            if not math.isfinite(ref_f):
                raise SettingsScopeError("ble_ref_power must be a finite number")
            out["ble_ref_power"] = max(
                BLE_REF_POWER_MIN_DBM,
                min(BLE_REF_POWER_MAX_DBM, round(ref_f)),
            )

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

    if "tools_items" in incoming:
        try:
            out["tools_items"] = normalize_tools_items(incoming["tools_items"])
        except ValueError as err:
            raise SettingsScopeError(str(err)) from None

    if "games_items" in incoming:
        try:
            out["games_items"] = normalize_games_items(incoming["games_items"])
        except ValueError as err:
            raise SettingsScopeError(str(err)) from None

    if "activity_sources" in incoming:
        try:
            out["activity_sources"] = normalize_activity_sources(
                incoming["activity_sources"]
            )
        except ValueError as err:
            raise SettingsScopeError(str(err)) from None

    if "dock_items" in incoming:
        try:
            out["dock_items"] = normalize_dock_items(
                incoming["dock_items"], strict=True
            )
        except ValueError as err:
            raise SettingsScopeError(str(err)) from None

    if "pinned_items" in incoming:
        try:
            out["pinned_items"] = normalize_pinned_items(
                incoming["pinned_items"], strict=True
            )
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
        elif spec.domain == "text":
            try:
                if spec.key == "world_clocks":
                    out[spec.key] = normalize_world_clocks_spec(raw_v, strict=True)
                elif spec.key == "local_clock_label":
                    out[spec.key] = sanitize_clock_label(raw_v)
                elif spec.key == "alarms_summary":
                    out[spec.key] = normalize_alarms_summary(raw_v, strict=True)
                else:
                    out[spec.key] = _text(raw_v)
            except ValueError as err:
                raise SettingsScopeError(str(err)) from None
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
        out["start_screen"] = "Time App"

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
            "ble_attenuation": _ble_float(
                global_cfg.get("ble_attenuation"),
                DEFAULT_BLE_ATTENUATION,
                BLE_ATTENUATION_MIN,
                BLE_ATTENUATION_MAX,
                2,
            ),
            "ble_max_radius_m": _ble_float(
                global_cfg.get("ble_max_radius_m"),
                DEFAULT_BLE_MAX_RADIUS_M,
                BLE_MAX_RADIUS_MIN_M,
                BLE_MAX_RADIUS_MAX_M,
                1,
            ),
            "ble_max_velocity_mps": _ble_float(
                global_cfg.get("ble_max_velocity_mps"),
                DEFAULT_BLE_MAX_VELOCITY_MPS,
                BLE_MAX_VELOCITY_MIN_MPS,
                BLE_MAX_VELOCITY_MAX_MPS,
                1,
            ),
            "ble_away_timeout_s": _ble_int(
                global_cfg.get("ble_away_timeout_s"),
                DEFAULT_BLE_AWAY_TIMEOUT_S,
                BLE_AWAY_TIMEOUT_MIN_S,
                BLE_AWAY_TIMEOUT_MAX_S,
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
