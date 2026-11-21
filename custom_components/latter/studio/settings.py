"""Latter Studio settings scopes, command routing, target checks, and catalog push gate.

Standard library only (no Home Assistant imports), so unit tests exercise this exact code.
A System save writes only System settings (`.storage/latter.site`); a Device save writes only that
Device's settings (its config subentry). The websocket type is the command scope: `latter/system/command`
runs System commands and `latter/device/command` runs Device commands on the Device named by `subentry_id`.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Literal, Protocol, TypeVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones

_AVAILABLE_IANA_ZONES: frozenset[str] | None = None
_ZONEINFO_CACHE: dict[str, ZoneInfo | None] = {}

_PROTOCOL_V3_DATA: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parent.parent / "protocol_v3.json").read_text(
        encoding="utf-8"
    )
)

# ---------------------------------------------------------------------------
# Catalog & Section Push Gates
# ---------------------------------------------------------------------------

HEAVY_SUBSCRIPTION_SECTIONS: tuple[str, ...] = (
    "discovered_ble_devices",
    "system_wallpapers",
    "photo_collections",
    "ble_area_signatures",
)


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


class SectionHashGate:
    """Per-subscription content-digest gate omitting unchanged heavy System sections on live pushes."""

    def __init__(self) -> None:
        """Initialize empty section digest map."""
        self._digests: dict[str, str] = {}

    def mark_dirty(self, *keys: str) -> None:
        """Force the next live push to resend the specified sections (or all when empty)."""
        if not keys:
            self._digests.clear()
            return
        for k in keys:
            self._digests.pop(k, None)

    def has_sent(self, key: str) -> bool:
        """Return True if `key` has already been pushed on this subscription."""
        return key in self._digests

    def record_initial(
        self,
        payload: Mapping[str, Any],
        keys: Iterable[str] = HEAVY_SUBSCRIPTION_SECTIONS,
    ) -> None:
        """Record baseline section digests from the initial full subscription push without stripping."""
        for k in keys:
            if k in payload:
                raw = json.dumps(payload[k], sort_keys=True, separators=(",", ":"))
                self._digests[k] = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def filter_sections(
        self,
        payload: dict[str, Any],
        keys: Iterable[str] = HEAVY_SUBSCRIPTION_SECTIONS,
    ) -> dict[str, Any]:
        """Strip sections whose content digest is unchanged since the previous push on this subscription."""
        for k in keys:
            if k not in payload:
                continue
            raw = json.dumps(payload[k], sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
            if self._digests.get(k) == digest:
                payload.pop(k, None)
            else:
                self._digests[k] = digest
        return payload


# ---------------------------------------------------------------------------
# Studio Command Scopes & Target Checks
# ---------------------------------------------------------------------------

_STUDIO_CONTRACT: dict[str, Any] = _PROTOCOL_V3_DATA["studio_contract"]

SYSTEM_COMMANDS: frozenset[str] = frozenset(_STUDIO_CONTRACT["system_commands"])

DEVICE_COMMANDS: frozenset[str] = frozenset(_STUDIO_CONTRACT["device_commands"])

ALLOWED_DEVICE_ACTIONS: tuple[str, ...] = tuple(
    _STUDIO_CONTRACT["allowed_device_actions"]
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
    """Return the action verb of an entity action; option/level verbs must be empty or known."""
    action = str(body.get("action") or "").strip().lower()
    if body.get("option") is not None or body.get("level") is not None:
        allowed_param_verbs = {"", *verbs, "select_option", "set_value", "set_level"}
        if action not in allowed_param_verbs:
            raise TargetNotAllowed(f"Unsupported action '{action}'")
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
)
SYSTEM_SETTING_KEYS: tuple[str, ...] = (
    *SYSTEM_ENTITY_KEYS,
    "thermostat_entities",
    "lock_entities",
    "garage_entities",
    "vacuum_entities",
    "broadcast_speakers",
    "broadcast_phrases",
    "camera_entities",
    "camera_configs",
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
    "ignored_discovered_devices",
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
        "hw_jpeg",
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
    esphome_section: str = ""


def snap_calendar_lookahead_days(val: Any) -> int:
    """Snap `calendar_lookahead_days` to one of the canonical horizons (7, 14, 30, 60)."""
    if isinstance(val, bool):
        return 30
    try:
        ival = int(float(val))
    except (TypeError, ValueError):
        return 30
    if ival <= 10:
        return 7
    if ival <= 21:
        return 14
    if ival <= 45:
        return 30
    return 60


MAX_WORLD_CLOCKS = 4
DEFAULT_ALARMS_SUMMARY = "07:00|0|1;08:30|0|2;09:00|0|2"

WORLD_CLOCK_ZONES: tuple[dict[str, Any], ...] = tuple(
    _PROTOCOL_V3_DATA["world_clock_zones"]
)
WORLD_CLOCK_CATALOG: tuple[dict[str, Any], ...] = WORLD_CLOCK_ZONES + tuple(
    _PROTOCOL_V3_DATA.get("world_clock_aliases", ())
)
WORLD_CLOCK_CATALOG_MAP: dict[str, dict[str, Any]] = {
    str(item["iana"]): item for item in WORLD_CLOCK_CATALOG
}
_IANA_ZONE_RE = re.compile(r"^[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)+$")
_PINNED_UTC_ALIASES: frozenset[str] = frozenset(
    {"UTC", "Etc/UTC", "GMT", "Etc/GMT", "Etc/GMT+0", "Etc/GMT-0", "Etc/GMT0"}
)
_ALARM_RECORD_RE = re.compile(r"^(\d{1,2}):(\d{2})\|([01])\|([0-3])$")
_MODEL_UPPER_ACRONYMS: frozenset[str] = frozenset(
    {
        "s3",
        "p4",
        "c3",
        "c6",
        "h2",
        "amoled",
        "ips",
        "lcd",
        "oled",
        "tft",
        "dsi",
        "qspi",
        "rgb",
        "ble",
        "usb",
        "hd",
        "fhd",
        "ai",
        "ir",
        "poe",
    }
)


def warm_timezone_cache(extra_zones: Iterable[str] = ()) -> None:
    """Populate available IANA zone set and common `ZoneInfo` objects off the event loop."""
    global _AVAILABLE_IANA_ZONES
    try:
        zones = frozenset(available_timezones())
    except Exception:  # noqa: BLE001
        zones = frozenset()
    _AVAILABLE_IANA_ZONES = zones
    for item in WORLD_CLOCK_CATALOG:
        iana = str(item.get("iana") or "").strip()
        if iana and iana not in _ZONEINFO_CACHE:
            if zones and iana not in zones:
                _ZONEINFO_CACHE[iana] = None
                continue
            try:
                _ZONEINFO_CACHE[iana] = ZoneInfo(iana)
            except (ZoneInfoNotFoundError, ValueError):
                _ZONEINFO_CACHE[iana] = None
    for raw_extra in extra_zones:
        iana = str(raw_extra or "").strip()
        if iana and iana not in _ZONEINFO_CACHE:
            try:
                _ZONEINFO_CACHE[iana] = ZoneInfo(iana)
            except (ZoneInfoNotFoundError, ValueError):
                _ZONEINFO_CACHE[iana] = None


def get_cached_zoneinfo(iana: str) -> ZoneInfo | None:
    """Return a cached `ZoneInfo` object for `iana`, avoiding repeated tzdata disk opens."""
    tok = str(iana or "").strip()
    if not tok:
        return None
    if tok in _ZONEINFO_CACHE:
        return _ZONEINFO_CACHE[tok]
    if _AVAILABLE_IANA_ZONES is not None and _AVAILABLE_IANA_ZONES and tok not in _AVAILABLE_IANA_ZONES:
        _ZONEINFO_CACHE[tok] = None
        return None
    try:
        tz = ZoneInfo(tok)
    except (ZoneInfoNotFoundError, ValueError):
        _ZONEINFO_CACHE[tok] = None
        return None
    _ZONEINFO_CACHE[tok] = tz
    return tz


def is_valid_iana_zone(iana: str) -> bool:
    """Return True when `iana` is a valid non-UTC IANA zone ID."""
    tok = str(iana or "").strip()
    if not tok or len(tok) > 48 or tok in _PINNED_UTC_ALIASES:
        return False
    if not _IANA_ZONE_RE.match(tok):
        return False
    if tok in WORLD_CLOCK_CATALOG_MAP:
        return True
    if _AVAILABLE_IANA_ZONES is not None and _AVAILABLE_IANA_ZONES:
        return tok in _AVAILABLE_IANA_ZONES
    return get_cached_zoneinfo(tok) is not None


def _humanize_slug_tokens(raw: str) -> str:
    """Convert a kebab/snake hardware or model slug into a clean human-readable title."""
    text = str(raw or "").strip()
    if not text:
        return ""
    if " " in text and "_" not in text:
        return text
    parts = [p for p in re.split(r"[-_\s]+", text) if p]
    if not parts:
        return text
    formatted: list[str] = []
    for tok in parts:
        low = tok.lower()
        if low in _MODEL_UPPER_ACRONYMS:
            formatted.append(low.upper())
        elif re.fullmatch(r"\d+(?:\.\d+)?(?:in|mm|px)?", low) or any(
            c.isupper() for c in tok[1:]
        ):
            formatted.append(tok)
        else:
            formatted.append(tok.capitalize())
    return " ".join(formatted)


def humanize_device_model_label(
    raw_model: str,
    manifest: Mapping[str, Any] | None = None,
    *,
    fallback: str = "",
) -> str:
    """Return a humanized model title + `(WxH)` resolution without exposing raw kebab/snake slugs."""
    m = manifest or {}
    w = int(m.get("w") or 0)
    h = int(m.get("h") or 0)
    board_lbl = _humanize_slug_tokens(str(m.get("board") or ""))
    model_lbl = _humanize_slug_tokens(raw_model)
    if w > 0 and h > 0:
        dims = f"({w}x{h})"
        if model_lbl:
            return model_lbl if dims in model_lbl else f"{model_lbl} {dims}"
        if board_lbl:
            return f"{board_lbl} {dims}"
        return f"Latter Display {dims}"
    return model_lbl or board_lbl or fallback


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


DEVICE_PREF_SPECS: tuple[DevicePrefSpec, ...] = tuple(
    DevicePrefSpec(
        key=str(raw["key"]),
        label=str(raw["label"]),
        domain=raw["domain"],
        default=raw["default"],
        section=str(raw["section"]),
        capability=raw["capability"],
        group_tier=raw.get("group_tier"),
        options=tuple(str(o) for o in (raw.get("options") or ())),
        min_val=int(raw["min"]) if raw.get("min") is not None else None,
        max_val=int(raw["max"]) if raw.get("max") is not None else None,
        step=int(raw["step"]) if raw.get("step") is not None else None,
        unit=str(raw.get("unit") or ""),
        esphome_section=str(raw.get("esphome_section") or ""),
    )
    for raw in _PROTOCOL_V3_DATA["device_pref_specs"]
)

DEVICE_PREF_SPEC_MAP: dict[str, DevicePrefSpec] = {s.key: s for s in DEVICE_PREF_SPECS}
DEVICE_PREF_KEYS: tuple[str, ...] = tuple(s.key for s in DEVICE_PREF_SPECS)

WAKE_WORD_MODE_OPTIONS: tuple[str, ...] = tuple(
    DEVICE_PREF_SPEC_MAP["wake_word_mode"].options
)
START_SCREEN_OPTIONS: tuple[str, ...] = tuple(
    DEVICE_PREF_SPEC_MAP["start_screen"].options
)
RETURN_TO_HOME_TIMEOUT_OPTIONS: tuple[str, ...] = tuple(
    DEVICE_PREF_SPEC_MAP["return_to_home_timeout"].options
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
    if spec.domain == "text":
        if key == "world_clocks":
            return normalize_world_clocks_spec(raw, strict=False)
        if key == "local_clock_label":
            return sanitize_clock_label(raw)
        if key == "alarms_summary":
            return normalize_alarms_summary(raw, strict=False)
        return str(raw).strip()
    if key == "calendar_lookahead_days":
        return snap_calendar_lookahead_days(raw)
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
    "ble_category",
    "assigned_person",
    "area_categories",
    "home_categories",
    "tools_items",
    "games_items",
    "activity_sources",
    "wallpaper_mode",
    "wallpaper_source",
    "wallpaper_collection",
    "screensaver_photo_mode",
    "screensaver_photo_source",
    "screensaver_photo_collection",
    "security_pin_policy",
)
DEVICE_BOOL_KEYS: tuple[str, ...] = (
    "native_ble_tracking",
    "ble_auto_switch",
    "sync_device_area",
    "area_handoff",
    "activity_card",
    "screensaver_shuffle",
)
DEVICE_SETTING_KEYS: tuple[str, ...] = (
    *DEVICE_TEXT_KEYS,
    *DEVICE_BOOL_KEYS,
    "dock_items",
    "pinned_items",
    "broadcast_speaker_entities",
    "camera_visible_entities",
    "camera_carousel_entities",
    "wallpaper_favorites",
    "wallpaper_cycle_minutes",
    "screensaver_photo_ids",
    "screensaver_cycle_minutes",
    "device_custom_color",
    "area_follow_dwell_s",
    "ble_ref_power",
    *DEVICE_PREF_KEYS,
)

PHOTO_POOL_MODES: tuple[str, ...] = ("off", "single", "collection", "custom")
MAX_PHOTO_POOL_IDS = 100

MAX_LIST_ITEMS = 10
MAX_THERMOSTATS = 8
MAX_LOCKS = 8
MAX_GARAGES = 6
MAX_VACUUMS = 6
MAX_BROADCAST_SPEAKERS = 32
MAX_BROADCAST_PHRASES = 12
MAX_BROADCAST_PHRASE_LEN = 64
DEFAULT_STUDIO_BROADCAST_PHRASES: tuple[str, ...] = (
    "Dinner is ready",
    "Come upstairs",
    "Leaving soon",
)
MAX_CALENDARS = 50
MAX_CUSTOM_PALETTES = 24
MAX_REMOTE_GROUPS = 20
MAX_REMOTE_GROUP_NAME_LEN = 64
MAX_PALETTE_NAME_LEN = 48
MAX_ANNOUNCE_TITLE_LEN = 64
MAX_ANNOUNCE_MESSAGE_LEN = 500
MAX_IGNORED_DISCOVERED = 100
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
BLE_CATEGORIES: tuple[str, ...] = ("auto", "phone", "ble_tag")
_HEX_COLOR = re.compile(r"^#[0-9A-F]{6}$")
_REMOTE_GROUP_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,48}$")
_REMOTE_GROUP_REF = re.compile(r"^group:[A-Za-z0-9_-]{1,48}$")


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


def _broadcast_phrases(val: Any, *, strict: bool = False) -> list[str]:
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


def _camera_configs(val: Any, *, strict: bool = False) -> dict[str, dict[str, Any]]:
    """Validate and normalize per-camera display labels, action toggles, and unlock entity bindings."""
    if val is None:
        return {}
    if not isinstance(val, Mapping):
        if strict:
            raise SettingsScopeError("camera_configs must be a mapping keyed by camera entity ID")
        return {}
    out: dict[str, dict[str, Any]] = {}
    for raw_key, raw_entry in list(val.items())[:MAX_LIST_ITEMS]:
        cam_id = _text(raw_key)[:128]
        if not cam_id.startswith("camera."):
            if strict:
                raise SettingsScopeError(f"Expected a camera.* key in camera_configs, got {cam_id}")
            continue
        if not isinstance(raw_entry, Mapping):
            if strict:
                raise SettingsScopeError(f"camera_configs[{cam_id}] must be an object")
            continue
        raw_label = _text(raw_entry.get("label"))
        clean_label = (
            raw_label.replace("|", " ")
            .replace("\x1e", " ")
            .replace("\x1f", " ")
            .replace("\r", " ")
            .replace("\n", " ")
            .strip()[:32]
        )
        unlock_ent = _text(raw_entry.get("unlock_entity"))[:128]
        if unlock_ent and not unlock_ent.startswith(("lock.", "cover.")):
            if strict:
                raise SettingsScopeError(
                    f"Expected a lock.* or cover.* entity for camera_configs[{cam_id}].unlock_entity, got {unlock_ent}"
                )
            unlock_ent = ""
        entry: dict[str, Any] = {}
        if clean_label:
            entry["label"] = clean_label
        for flag_key in ("show_listen", "show_talk", "show_reply"):
            raw_flag = raw_entry.get(flag_key)
            if isinstance(raw_flag, bool):
                entry[flag_key] = raw_flag
            elif raw_flag is not None and strict:
                raise SettingsScopeError(
                    f"camera_configs[{cam_id}].{flag_key} must be a boolean or null"
                )
        if unlock_ent:
            entry["unlock_entity"] = unlock_ent
        if entry:
            out[cam_id] = entry
    return out


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


def _remote_groups(val: Any, *, strict: bool = False) -> list[dict[str, Any]]:
    if not isinstance(val, (list, tuple)):
        if strict:
            raise SettingsScopeError("remote_groups must be a list")
        return []
    if strict and len(val) > MAX_REMOTE_GROUPS:
        raise SettingsScopeError(
            f"remote_groups supports at most {MAX_REMOTE_GROUPS} groups"
        )
    out: list[dict[str, Any]] = []
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
        name = _text(item.get("name"))[:MAX_REMOTE_GROUP_NAME_LEN] or gid
        area_id = _text(item.get("area_id"))[:64]
        out.append(
            {
                "id": gid,
                "name": name,
                "area_id": area_id,
                "remotes": _entity_list(item.get("remotes")),
            }
        )
        if len(out) >= MAX_REMOTE_GROUPS:
            break
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
            name = _text(item.get("name"))[:MAX_PALETTE_NAME_LEN] or hex_val
            out.append({"name": name, "hex": hex_val})
    return out[:MAX_CUSTOM_PALETTES]


def _ignored_device_ids(val: Any, *, strict: bool = False) -> list[str]:
    if not isinstance(val, (list, tuple)):
        if strict:
            raise SettingsScopeError("ignored_discovered_devices must be a list")
        return []
    out: list[str] = []
    for item in val:
        dev_id = _text(item)[:128]
        if dev_id and dev_id not in out:
            out.append(dev_id)
        if len(out) >= MAX_IGNORED_DISCOVERED:
            break
    return out


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


def _domain_entity_list(val: Any, prefix: str, limit: int, label: str) -> list[str]:
    if not isinstance(val, (list, tuple)):
        raise SettingsScopeError(f"{label} must be a list of entity IDs")
    out: list[str] = []
    for item in val:
        ent = _text(item)
        if not ent:
            continue
        if not ent.startswith(prefix):
            raise SettingsScopeError(
                f"Expected a {prefix}* entity for {label}, got {ent}"
            )
        if ent not in out:
            out.append(ent)
    return out[:limit]


def _safe_domain_entity_list(val: Any, prefix: str, limit: int) -> list[str]:
    if not isinstance(val, (list, tuple)):
        return []
    out: list[str] = []
    for item in val:
        ent = _text(item)
        if ent and ent.startswith(prefix) and ent not in out:
            out.append(ent)
    return out[:limit]


def clean_system_settings(incoming: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a System save (`camera_entities` is the sole canonical camera list)."""
    _check_scope(incoming, SYSTEM_SETTING_KEYS, "System")
    out: dict[str, Any] = {}
    for key in SYSTEM_ENTITY_KEYS:
        if key in incoming:
            ent = _text(incoming[key])[:128]
            if ent:
                expected_prefix = "weather." if key == "weather_entity" else "alarm_control_panel."
                if not ent.startswith(expected_prefix):
                    raise SettingsScopeError(
                        f"Expected a {expected_prefix}* entity for {key}, got {ent}"
                    )
            out[key] = ent
    if "thermostat_entities" in incoming:
        out["thermostat_entities"] = _domain_entity_list(
            incoming["thermostat_entities"],
            "climate.",
            MAX_THERMOSTATS,
            "thermostat_entities",
        )
    if "lock_entities" in incoming:
        out["lock_entities"] = _domain_entity_list(
            incoming["lock_entities"],
            "lock.",
            MAX_LOCKS,
            "lock_entities",
        )
    if "garage_entities" in incoming:
        out["garage_entities"] = _domain_entity_list(
            incoming["garage_entities"],
            "cover.",
            MAX_GARAGES,
            "garage_entities",
        )
    if "vacuum_entities" in incoming:
        out["vacuum_entities"] = _domain_entity_list(
            incoming["vacuum_entities"],
            "vacuum.",
            MAX_VACUUMS,
            "vacuum_entities",
        )
    if "broadcast_speakers" in incoming:
        out["broadcast_speakers"] = _domain_entity_list(
            incoming["broadcast_speakers"],
            "media_player.",
            MAX_BROADCAST_SPEAKERS,
            "broadcast_speakers",
        )
    if "broadcast_phrases" in incoming:
        out["broadcast_phrases"] = _broadcast_phrases(
            incoming["broadcast_phrases"], strict=True
        )
    if "camera_entities" in incoming:
        out["camera_entities"] = _domain_entity_list(
            incoming["camera_entities"],
            "camera.",
            MAX_LIST_ITEMS,
            "camera_entities",
        )
    if "camera_configs" in incoming:
        out["camera_configs"] = _camera_configs(incoming["camera_configs"], strict=True)
    if "remotes_list" in incoming:
        out["remotes_list"] = _entity_list(incoming["remotes_list"])
    if "calendar_entities" in incoming:
        out["calendar_entities"] = _domain_entity_list(
            incoming["calendar_entities"],
            "calendar.",
            MAX_CALENDARS,
            "calendar_entities",
        )
    if "remote_groups" in incoming:
        out["remote_groups"] = _remote_groups(incoming["remote_groups"], strict=True)
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
    if "ignored_discovered_devices" in incoming:
        out["ignored_discovered_devices"] = _ignored_device_ids(
            incoming["ignored_discovered_devices"], strict=True
        )
    return out


def clean_device_settings(
    incoming: Mapping[str, Any],
    current: Mapping[str, Any] | None = None,
    *,
    is_round_display: bool | None = None,
    supports_hw_jpeg: bool | None = None,
    strict_traits: bool = False,
) -> dict[str, Any]:
    """Validate and normalize a Device save."""
    _check_scope(incoming, DEVICE_SETTING_KEYS, "Device")
    out: dict[str, Any] = {}
    for key in DEVICE_TEXT_KEYS:
        if key in incoming:
            out[key] = _text(incoming[key])[:256]
    for key in DEVICE_BOOL_KEYS:
        if key in incoming:
            raw_b = incoming[key]
            if isinstance(raw_b, str):
                out[key] = raw_b.strip().lower() in ("1", "true", "on", "yes")
            else:
                out[key] = bool(raw_b)
    try:
        if "wallpaper_cycle_minutes" in incoming:
            if isinstance(incoming["wallpaper_cycle_minutes"], bool):
                raise ValueError("boolean")
            out["wallpaper_cycle_minutes"] = max(
                0, int(incoming["wallpaper_cycle_minutes"])
            )
        if "screensaver_cycle_minutes" in incoming:
            if isinstance(incoming["screensaver_cycle_minutes"], bool):
                raise ValueError("boolean")
            out["screensaver_cycle_minutes"] = max(
                0, int(incoming["screensaver_cycle_minutes"])
            )
        if "area_follow_dwell_s" in incoming:
            out["area_follow_dwell_s"] = max(
                DWELL_MIN_S, min(DWELL_MAX_S, int(incoming["area_follow_dwell_s"]))
            )
    except (TypeError, ValueError) as err:
        raise SettingsScopeError(f"Not a whole number: {err}") from None

    for pool_mode_key in ("wallpaper_mode", "screensaver_photo_mode"):
        if pool_mode_key in out:
            pm = out[pool_mode_key].lower()
            if pm not in PHOTO_POOL_MODES:
                raise SettingsScopeError(
                    f"Unknown {pool_mode_key}: {pm or '(empty)'}"
                )
            out[pool_mode_key] = pm

    for pool_ids_key in ("wallpaper_favorites", "screensaver_photo_ids"):
        if pool_ids_key in incoming:
            raw_pids = incoming[pool_ids_key]
            if not isinstance(raw_pids, (list, tuple)):
                raise SettingsScopeError(f"{pool_ids_key} must be a list of photo IDs")
            cleaned_pids: list[str] = []
            for item in raw_pids:
                pid = _text(item)[:128]
                if pid and pid not in cleaned_pids:
                    cleaned_pids.append(pid)
                if len(cleaned_pids) >= MAX_PHOTO_POOL_IDS:
                    break
            out[pool_ids_key] = cleaned_pids

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

    if "broadcast_speaker_entities" in incoming:
        out["broadcast_speaker_entities"] = _domain_entity_list(
            incoming["broadcast_speaker_entities"],
            "media_player.",
            MAX_BROADCAST_SPEAKERS,
            "broadcast_speaker_entities",
        )

    if "camera_visible_entities" in incoming:
        out["camera_visible_entities"] = _domain_entity_list(
            incoming["camera_visible_entities"],
            "camera.",
            MAX_LIST_ITEMS,
            "camera_visible_entities",
        )

    if "camera_carousel_entities" in incoming:
        out["camera_carousel_entities"] = _domain_entity_list(
            incoming["camera_carousel_entities"],
            "camera.",
            MAX_LIST_ITEMS,
            "camera_carousel_entities",
        )

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
            if isinstance(raw_v, bool):
                raise SettingsScopeError(f"Expected a whole number for {spec.key}, not a boolean")
            try:
                num_v = int(raw_v)
            except (TypeError, ValueError) as err:
                raise SettingsScopeError(f"Not a whole number: {err}") from None
            if spec.key == "calendar_lookahead_days":
                num_v = snap_calendar_lookahead_days(num_v)
            else:
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

    if is_round_display is False and out.get("clock_face") == "Modern Analog":
        if strict_traits:
            raise SettingsScopeError(
                "Modern Analog clock face is only supported on round displays"
            )
        out["clock_face"] = "Minimal Digital"

    if supports_hw_jpeg is False and out.get("camera_doorbell_popup") == "Live Video":
        if strict_traits:
            raise SettingsScopeError(
                "Live Video doorbell popup requires hardware JPEG decoding"
            )
        out["camera_doorbell_popup"] = "Snapshot"

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
    if "ble_category" in out:
        ble_cat = (out["ble_category"] or "auto").lower()
        if ble_cat not in BLE_CATEGORIES:
            raise SettingsScopeError(
                f"Unknown BLE category: {ble_cat}"
            )
        out["ble_category"] = ble_cat
    return out


def system_settings_view(global_cfg: Mapping[str, Any]) -> dict[str, Any]:
    """Return the System settings as Studio shows them, read straight from `.storage/latter.site`."""
    cams = _safe_domain_entity_list(
        global_cfg.get("camera_entities"), "camera.", MAX_LIST_ITEMS
    )
    view: dict[str, Any] = {
        key: _text(global_cfg.get(key)) for key in SYSTEM_ENTITY_KEYS
    }
    view.update(
        {
            "thermostat_entities": _safe_domain_entity_list(
                global_cfg.get("thermostat_entities"), "climate.", MAX_THERMOSTATS
            ),
            "lock_entities": _safe_domain_entity_list(
                global_cfg.get("lock_entities"), "lock.", MAX_LOCKS
            ),
            "garage_entities": _safe_domain_entity_list(
                global_cfg.get("garage_entities"), "cover.", MAX_GARAGES
            ),
            "vacuum_entities": _safe_domain_entity_list(
                global_cfg.get("vacuum_entities"), "vacuum.", MAX_VACUUMS
            ),
            "broadcast_speakers": _safe_domain_entity_list(
                global_cfg.get("broadcast_speakers"),
                "media_player.",
                MAX_BROADCAST_SPEAKERS,
            ),
            "broadcast_phrases": (
                _broadcast_phrases(global_cfg.get("broadcast_phrases"))
                if "broadcast_phrases" in global_cfg
                else list(DEFAULT_STUDIO_BROADCAST_PHRASES)
            ),
            "camera_entities": cams,
            "camera_configs": _camera_configs(global_cfg.get("camera_configs")),
            "remotes_list": _entity_list(global_cfg.get("remotes_list")),
            "remote_groups": _remote_groups(global_cfg.get("remote_groups")),
            "volume_overrides": _volume_overrides(global_cfg.get("volume_overrides")),
            "calendar_entities": _safe_domain_entity_list(
                global_cfg.get("calendar_entities"), "calendar.", MAX_CALENDARS
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
            "ignored_discovered_devices": _ignored_device_ids(
                global_cfg.get("ignored_discovered_devices")
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
    if len(message) > MAX_ANNOUNCE_MESSAGE_LEN:
        raise SettingsScopeError(
            f"Announcement message must be at most {MAX_ANNOUNCE_MESSAGE_LEN} characters"
        )
    if mode == "notify":
        if target not in device_slugs and target not in NOTIFY_SPECIAL_TARGETS:
            raise SettingsScopeError(
                f"Not a Latter Device or notify target: {target or '(empty)'}"
            )
        title = _text(body.get("title"))
        if not title:
            raise SettingsScopeError("Enter a title")
        if len(title) > MAX_ANNOUNCE_TITLE_LEN:
            raise SettingsScopeError(
                f"Announcement title must be at most {MAX_ANNOUNCE_TITLE_LEN} characters"
            )
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
