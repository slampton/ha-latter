"""Pure-stdlib Protocol v3 schema specs, catalogs, World Clock / Alarm / Shortcut normalizers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Final, Literal, TypedDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones


class WorldClockZoneDict(TypedDict, total=False):
    """Schema entry from `studio_contract.json` `world_clock_zones` / `world_clock_aliases`."""

    iana: str
    city: str
    region: str
    std_abbr: str
    dst_abbr: str
    std_off: int
    dst_off: int
    rule: str


class CatalogItemDict(TypedDict, total=False):
    """Merged Protocol v3 + Studio contract catalog item."""

    token: str
    label: str
    group: str
    icon: str
    dock_only: bool
    capability: str


class ShortcutItemDict(TypedDict):
    """Normalized Home Dock or Pinned App shortcut item."""

    kind: Literal["route", "entity"]
    target: str
    action: str
    label: str
    icon: str
    confirm: bool
    badge_style: str
    accent: str


_AVAILABLE_IANA_ZONES: frozenset[str] | None = None
_ZONEINFO_CACHE: dict[str, ZoneInfo | None] = {}

PROTOCOL_V3_DATA: Final[dict[str, Any]] = json.loads(
    (Path(__file__).resolve().parent / "protocol_v3.json").read_text(encoding="utf-8")
)
STUDIO_CONTRACT_DATA: Final[dict[str, Any]] = json.loads(
    (Path(__file__).resolve().parent / "studio_contract.json").read_text(
        encoding="utf-8"
    )
)
PROTOCOL_V3_DOMAINS: Final[tuple[str, ...]] = tuple(
    PROTOCOL_V3_DATA["domains"].keys()
)
STUDIO_CONTRACT: Final[dict[str, Any]] = STUDIO_CONTRACT_DATA["studio_contract"]

SYSTEM_COMMANDS: Final[frozenset[str]] = frozenset(STUDIO_CONTRACT["system_commands"])
DEVICE_COMMANDS: Final[frozenset[str]] = frozenset(STUDIO_CONTRACT["device_commands"])
ALLOWED_DEVICE_ACTIONS: Final[tuple[str, ...]] = tuple(
    STUDIO_CONTRACT["allowed_device_actions"]
)
DEVICE_ENTITY_VERBS: Final[frozenset[str]] = frozenset(
    {"press", "install", "check", "toggle", "turn_on", "turn_off"}
)

PrefDomain = Literal["select", "switch", "number", "text"]
PrefCapability = Literal[
    "display",
    "display_imu",
    "display_battery",
    "display_or_audio",
    "hw_jpeg",
    "mic",
    "speaker",
    "beacon",
    "beacon_battery",
]
PrefGroupTier = Literal["behavior", "display", "interface"]


@dataclass(frozen=True, slots=True)
class DevicePrefSpec:
    """Declarative specification for one Protocol v3 `device_prefs` subentry preference."""

    key: str
    label: str
    domain: PrefDomain
    default: bool | int | str
    section: str
    capability: PrefCapability
    group_tier: PrefGroupTier | None
    options: tuple[str, ...] = ()
    min_val: int | None = None
    max_val: int | None = None
    step: int | None = None
    unit: str = ""


_LOOKAHEAD_SNAP_7: Final = 10
_LOOKAHEAD_SNAP_14: Final = 21
_LOOKAHEAD_SNAP_30: Final = 45
_DEFAULT_LOOKAHEAD_DAYS: Final = 30
_SPACE_ORD: Final = 0x20
_DEL_ORD: Final = 0x7F
_MAX_IANA_LEN: Final = 48
_ALARM_SLOT_COUNT: Final = 3
_MAX_HOUR: Final = 23
_MAX_MINUTE: Final = 59


def snap_calendar_lookahead_days(val: object) -> int:
    """Snap `calendar_lookahead_days` to one of the canonical horizons (7, 14, 30, 60)."""
    if isinstance(val, bool) or not isinstance(val, (int, float, str)):
        return _DEFAULT_LOOKAHEAD_DAYS
    try:
        ival = int(float(val))
    except (TypeError, ValueError, OverflowError):
        return _DEFAULT_LOOKAHEAD_DAYS
    if ival <= _LOOKAHEAD_SNAP_7:
        return 7
    if ival <= _LOOKAHEAD_SNAP_14:
        return 14
    if ival <= _LOOKAHEAD_SNAP_30:
        return _DEFAULT_LOOKAHEAD_DAYS
    return 60


MAX_WORLD_CLOCKS: Final = 4
DEFAULT_ALARMS_SUMMARY: Final = "07:00|0|1;08:30|0|2;09:00|0|2"

WORLD_CLOCK_ZONES: Final[tuple[WorldClockZoneDict, ...]] = tuple(
    STUDIO_CONTRACT_DATA["world_clock_zones"]
)
WORLD_CLOCK_CATALOG: Final[tuple[WorldClockZoneDict, ...]] = WORLD_CLOCK_ZONES + tuple(
    STUDIO_CONTRACT_DATA.get("world_clock_aliases", ())
)
WORLD_CLOCK_CATALOG_MAP: Final[dict[str, WorldClockZoneDict]] = {
    str(item["iana"]): item for item in WORLD_CLOCK_CATALOG
}
_IANA_ZONE_RE: Final = re.compile(r"^[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)+$")
_PINNED_UTC_ALIASES: Final[frozenset[str]] = frozenset(
    {"UTC", "Etc/UTC", "GMT", "Etc/GMT", "Etc/GMT+0", "Etc/GMT-0", "Etc/GMT0"}
)
_ALARM_RECORD_RE: Final = re.compile(r"^(\d{1,2}):(\d{2})\|([01])\|([0-3])$")
_MODEL_UPPER_ACRONYMS: Final[frozenset[str]] = frozenset(
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


def _try_load_zoneinfo(iana: str) -> ZoneInfo | None:
    try:
        return ZoneInfo(iana)
    except (ZoneInfoNotFoundError, ValueError):
        return None


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
            _ZONEINFO_CACHE[iana] = (
                None if (zones and iana not in zones) else _try_load_zoneinfo(iana)
            )
    for raw_extra in extra_zones:
        iana = str(raw_extra or "").strip()
        if iana and iana not in _ZONEINFO_CACHE:
            _ZONEINFO_CACHE[iana] = _try_load_zoneinfo(iana)


def get_cached_zoneinfo(iana: str) -> ZoneInfo | None:
    """Return a cached `ZoneInfo` object for `iana`, avoiding repeated tzdata disk opens."""
    tok = str(iana or "").strip()
    if not tok:
        return None
    if tok in _ZONEINFO_CACHE:
        return _ZONEINFO_CACHE[tok]
    if _AVAILABLE_IANA_ZONES and tok not in _AVAILABLE_IANA_ZONES:
        _ZONEINFO_CACHE[tok] = None
        return None
    tz = _try_load_zoneinfo(tok)
    _ZONEINFO_CACHE[tok] = tz
    return tz


def is_valid_iana_zone(iana: str) -> bool:
    """Return True when `iana` is a valid non-UTC IANA zone ID."""
    tok = str(iana or "").strip()
    if not tok or len(tok) > _MAX_IANA_LEN or tok in _PINNED_UTC_ALIASES:
        return False
    if not _IANA_ZONE_RE.match(tok):
        return False
    if tok in WORLD_CLOCK_CATALOG_MAP:
        return True
    if _AVAILABLE_IANA_ZONES:
        return tok in _AVAILABLE_IANA_ZONES
    return get_cached_zoneinfo(tok) is not None


def _humanize_slug_tokens(raw: str) -> str:
    """Convert a kebab/snake hardware or model slug into a clean human-readable title."""
    text = str(raw or "").strip()
    if not text or (" " in text and "_" not in text):
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


def _int_from_mapping(mapping: Mapping[str, object], key: str) -> int:
    val = mapping.get(key)
    if isinstance(val, bool) or not isinstance(val, (int, float, str)):
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def humanize_device_model_label(
    raw_model: str,
    manifest: Mapping[str, object] | None = None,
    *,
    fallback: str = "",
) -> str:
    """Return a humanized model title + `(WxH)` resolution without exposing raw kebab/snake slugs."""
    m = manifest or {}
    w = _int_from_mapping(m, "w")
    h = _int_from_mapping(m, "h")
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


def sanitize_clock_label(val: object, max_bytes: int = 32) -> str:
    """Return a single-line delimiter-safe clock label truncated cleanly to `max_bytes` UTF-8 bytes."""
    raw = str(val or "")
    chars: list[str] = []
    prev_space = True
    for ch in raw:
        code = ord(ch)
        if (
            code < _SPACE_ORD
            or code == _DEL_ORD
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
    if cat is not None and "city" in cat:
        return str(cat["city"])
    tail = clean.rsplit("/", 1)[-1].replace("_", " ")
    return sanitize_clock_label(tail) or clean


def _extract_world_clock_raw_pair(
    raw: object, *, strict: bool
) -> tuple[str, str] | None:
    if isinstance(raw, Mapping):
        raw_lbl = str(raw.get("label") or "")
        iana = str(raw.get("iana") or "").strip()
        return None if (not iana and not raw_lbl.strip()) else (raw_lbl, iana)
    rec = str(raw or "").strip()
    if not rec:
        return None
    if "|" not in rec:
        if strict:
            raise ValueError(
                f"Invalid World Clock record (expected '<label>|<iana>'): {rec}"
            )
        return None
    raw_lbl, raw_iana = rec.split("|", 1)
    return raw_lbl, raw_iana.strip()


def _validate_world_clock_pair(
    raw_lbl: str, iana: str, *, strict: bool
) -> tuple[str, str] | None:
    if iana in _PINNED_UTC_ALIASES:
        if strict:
            raise ValueError(
                "Use Show UTC Clock instead of adding UTC to World Clocks"
            )
        return None
    if not is_valid_iana_zone(iana):
        if strict:
            raise ValueError(f"Unknown IANA time zone: {iana or '(empty)'}")
        return None
    cleaned_lbl = sanitize_clock_label(raw_lbl)
    if not cleaned_lbl and strict:
        raise ValueError("World Clock city label is required")
    return (cleaned_lbl or default_city_for_iana(iana)), iana


def parse_world_clocks_spec(
    val: object, *, strict: bool = False
) -> list[tuple[str, str]]:
    """Parse and validate up to 4 `'<label>|<iana>'` World Clock entries."""
    if val is None:
        return []
    raw_items: Iterable[object] = (
        val if isinstance(val, (list, tuple)) else str(val).split(";")
    )
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_items:
        extracted = _extract_world_clock_raw_pair(raw, strict=strict)
        if extracted is None:
            continue
        validated = _validate_world_clock_pair(
            extracted[0], extracted[1], strict=strict
        )
        if validated is None:
            continue
        lbl, iana = validated
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


def normalize_world_clocks_spec(val: object, *, strict: bool = False) -> str:
    """Validate and canonicalize up to 4 semicolon-delimited `'<label>|<iana>'` World Clocks."""
    return ";".join(
        f"{lbl}|{iana}"
        for lbl, iana in parse_world_clocks_spec(val, strict=strict)
    )


def _format_single_alarm_slot(part: str, *, strict: bool) -> str | None:
    m = _ALARM_RECORD_RE.match(part)
    if not m:
        if strict:
            raise ValueError(f"Invalid alarm record: {part or '(empty)'}")
        return None
    hh, mm, en, rec = (
        int(m.group(1)),
        int(m.group(2)),
        int(m.group(3)),
        int(m.group(4)),
    )
    if not (0 <= hh <= _MAX_HOUR and 0 <= mm <= _MAX_MINUTE):
        if strict:
            raise ValueError(f"Alarm time out of range: {part}")
        return None
    return f"{hh:02d}:{mm:02d}|{en}|{rec}"


def normalize_alarms_summary(val: object, *, strict: bool = False) -> str:
    """Validate and canonicalize 3 semicolon-separated `HH:MM|0..1|0..3` alarm records."""
    text = str(val or "").strip()
    if not text:
        if strict:
            raise ValueError("Alarms summary requires 3 alarm slots")
        return DEFAULT_ALARMS_SUMMARY
    parts = [p.strip() for p in text.split(";")]
    if len(parts) != _ALARM_SLOT_COUNT:
        if strict:
            raise ValueError(
                "Alarms summary requires exactly 3 semicolon-separated slots"
            )
        return DEFAULT_ALARMS_SUMMARY
    normalized: list[str] = []
    for part in parts:
        slot = _format_single_alarm_slot(part, strict=strict)
        if slot is None:
            return DEFAULT_ALARMS_SUMMARY
        normalized.append(slot)
    return ";".join(normalized)


# ---------------------------------------------------------------------------
# Protocol v3 Category & Launcher Catalogs (merged with studio_contract.json)
# ---------------------------------------------------------------------------

_CATALOG_UI: Final[dict[str, Any]] = STUDIO_CONTRACT_DATA["catalog_ui"]
_SHORTCUT_ROUTE_GROUPS: Final[dict[str, str]] = _CATALOG_UI["shortcut_route_groups"]
_CATALOG_LABELS: Final[dict[str, dict[str, str]]] = _CATALOG_UI["catalog_labels"]


def _merge_labeled_catalog(cat_name: str) -> tuple[CatalogItemDict, ...]:
    raw_items: list[dict[str, Any]] = PROTOCOL_V3_DATA["catalogs"][cat_name]
    labels_map = _CATALOG_LABELS.get(cat_name)
    if not isinstance(labels_map, dict):
        raise RuntimeError(f"studio_contract.json catalog_ui.catalog_labels missing {cat_name!r}")
    raw_tokens = {str(item["token"]) for item in raw_items}
    if set(labels_map.keys()) != raw_tokens:
        raise RuntimeError(
            f"studio_contract.json catalog_ui.catalog_labels[{cat_name!r}] keys do not match protocol_v3.json"
        )
    merged: list[CatalogItemDict] = []
    for raw in raw_items:
        tok = str(raw["token"])
        item: CatalogItemDict = {"token": tok, "label": str(labels_map[tok])}
        if raw.get("capability"):
            item["capability"] = str(raw["capability"])
        merged.append(item)
    return tuple(merged)


def _merge_shortcut_routes() -> tuple[CatalogItemDict, ...]:
    raw_routes: list[dict[str, Any]] = PROTOCOL_V3_DATA["catalogs"]["shortcut_routes"]
    raw_tokens = {str(r["token"]) for r in raw_routes}
    if set(_SHORTCUT_ROUTE_GROUPS.keys()) != raw_tokens:
        raise RuntimeError(
            "studio_contract.json catalog_ui.shortcut_route_groups keys do not match protocol_v3.json"
        )
    merged: list[CatalogItemDict] = []
    for raw in raw_routes:
        tok = str(raw["token"])
        item: CatalogItemDict = {
            "token": tok,
            "label": str(raw["label"]),
            "group": str(_SHORTCUT_ROUTE_GROUPS[tok]),
        }
        if raw.get("dock_only"):
            item["dock_only"] = True
        if raw.get("capability"):
            item["capability"] = str(raw["capability"])
        merged.append(item)
    return tuple(merged)


AREA_CATEGORIES_CATALOG: Final[tuple[CatalogItemDict, ...]] = _merge_labeled_catalog(
    "area_categories"
)
AREA_CATEGORY_TOKENS: Final[tuple[str, ...]] = tuple(
    str(c["token"]) for c in AREA_CATEGORIES_CATALOG
)
DEFAULT_AREA_CATEGORIES: Final[str] = str(
    PROTOCOL_V3_DATA["defaults"]["area_categories"]
)

HOME_CATEGORIES_CATALOG: Final[tuple[CatalogItemDict, ...]] = _merge_labeled_catalog(
    "home_categories"
)
HOME_CATEGORY_TOKENS: Final[tuple[str, ...]] = tuple(
    str(c["token"]) for c in HOME_CATEGORIES_CATALOG
)
DEFAULT_HOME_CATEGORIES: Final[str] = str(
    PROTOCOL_V3_DATA["defaults"]["home_categories"]
)

TOOLS_ITEMS_CATALOG: Final[tuple[CatalogItemDict, ...]] = _merge_labeled_catalog(
    "tools_items"
)
TOOLS_ITEM_TOKENS: Final[tuple[str, ...]] = tuple(
    str(c["token"]) for c in TOOLS_ITEMS_CATALOG
)
DEFAULT_TOOLS_ITEMS: Final[str] = str(PROTOCOL_V3_DATA["defaults"]["tools_items"])

GAMES_ITEMS_CATALOG: Final[tuple[CatalogItemDict, ...]] = _merge_labeled_catalog(
    "games_items"
)
GAMES_ITEM_TOKENS: Final[tuple[str, ...]] = tuple(
    str(c["token"]) for c in GAMES_ITEMS_CATALOG
)
DEFAULT_GAMES_ITEMS: Final[str] = str(PROTOCOL_V3_DATA["defaults"]["games_items"])

ACTIVITY_SOURCES_CATALOG: Final[tuple[CatalogItemDict, ...]] = _merge_labeled_catalog(
    "activity_sources"
)
ACTIVITY_SOURCE_KEYS: Final[tuple[str, ...]] = tuple(
    str(c["token"]) for c in ACTIVITY_SOURCES_CATALOG
)
DEFAULT_ACTIVITY_SOURCES: Final[str] = str(
    PROTOCOL_V3_DATA["defaults"]["activity_sources"]
)


def _parse_token_csv(csv: object, allowed_tokens: tuple[str, ...]) -> list[str]:
    raw_items = csv if isinstance(csv, (list, tuple)) else str(csv or "").split(",")
    out: list[str] = []
    for raw in raw_items:
        tok = str(raw).strip().lower()
        if tok in allowed_tokens and tok not in out:
            out.append(tok)
    return out


def _normalize_token_csv(
    csv: object,
    allowed_tokens: tuple[str, ...],
    *,
    unknown_label: str,
    empty_message: str,
) -> str:
    raw_items = csv if isinstance(csv, (list, tuple)) else str(csv or "").split(",")
    names = [str(t).strip().lower() for t in raw_items if str(t).strip()]
    unknown = sorted({t for t in names if t not in allowed_tokens})
    if unknown:
        raise ValueError(f"Unknown {unknown_label}: {', '.join(unknown)}")
    items = _parse_token_csv(csv, allowed_tokens)
    if not items:
        raise ValueError(empty_message)
    return ",".join(items)


def parse_area_categories(csv: str | None) -> list[str]:
    """Return the known Area category tokens named in `csv`, in order, without duplicates."""
    return _parse_token_csv(csv, AREA_CATEGORY_TOKENS)


def normalize_area_categories(csv: str | None) -> str:
    """Return `csv` as canonical comma-separated Area categories; raise ValueError if empty or unknown."""
    return _normalize_token_csv(
        csv,
        AREA_CATEGORY_TOKENS,
        unknown_label="Area category",
        empty_message="Keep at least one Area category enabled",
    )


def parse_home_categories(csv: str | None) -> list[str]:
    """Return the known Home Hub category tokens named in `csv`, in order, without duplicates."""
    return _parse_token_csv(csv, HOME_CATEGORY_TOKENS)


def normalize_home_categories(csv: str | None) -> str:
    """Return `csv` as canonical comma-separated Home Hub categories; raise ValueError if empty or unknown."""
    return _normalize_token_csv(
        csv,
        HOME_CATEGORY_TOKENS,
        unknown_label="Home category",
        empty_message="Keep at least one Home category enabled",
    )


def parse_tools_items(csv: object) -> list[str]:
    """Return the known Tools launcher tokens named in `csv`, in order, without duplicates."""
    return _parse_token_csv(csv, TOOLS_ITEM_TOKENS)


def normalize_tools_items(csv: object) -> str:
    """Return `csv` as canonical comma-separated Tools items; raise ValueError if empty or unknown."""
    return _normalize_token_csv(
        csv,
        TOOLS_ITEM_TOKENS,
        unknown_label="Tool",
        empty_message="Keep at least one Tool enabled",
    )


def parse_games_items(csv: object) -> list[str]:
    """Return the known Games launcher tokens named in `csv`, in order, without duplicates."""
    return _parse_token_csv(csv, GAMES_ITEM_TOKENS)


def normalize_games_items(csv: object) -> str:
    """Return `csv` as canonical comma-separated Games items; raise ValueError if empty or unknown."""
    return _normalize_token_csv(
        csv,
        GAMES_ITEM_TOKENS,
        unknown_label="Game",
        empty_message="Keep at least one Game enabled",
    )


def normalize_activity_sources(value: object) -> str:
    """Return the sources as canonical CSV (`""` = every source off); raise ValueError for an unknown key."""
    raw = value if isinstance(value, (list, tuple)) else str(value or "").split(",")
    names = {str(t).strip().lower() for t in raw if str(t).strip()}
    unknown = sorted(names - set(ACTIVITY_SOURCE_KEYS))
    if unknown:
        raise ValueError(f"Unknown Activity Card source: {', '.join(unknown)}")
    return ",".join(k for k in ACTIVITY_SOURCE_KEYS if k in names)


# ---------------------------------------------------------------------------
# Universal Shortcut Engine (`dock_items` & `pinned_items`)
# ---------------------------------------------------------------------------

SHORTCUT_ROUTES_CATALOG: Final[tuple[CatalogItemDict, ...]] = _merge_shortcut_routes()
SHORTCUT_ROUTE_MAP: Final[dict[str, CatalogItemDict]] = {
    str(r["token"]): r for r in SHORTCUT_ROUTES_CATALOG
}
SHORTCUT_ROUTE_TOKENS: Final[tuple[str, ...]] = tuple(SHORTCUT_ROUTE_MAP.keys())
NAVIGATE_EXTRA_ROUTES: Final[frozenset[str]] = frozenset(
    {"home", "app:home", "app:settings", "quick_actions"}
)
NAVIGATE_ROUTES: Final[frozenset[str]] = (
    frozenset(SHORTCUT_ROUTE_TOKENS) | NAVIGATE_EXTRA_ROUTES
)
DEFAULT_DOCK_ROUTES: Final[str] = str(PROTOCOL_V3_DATA["defaults"]["dock_routes"])
SHORTCUT_BADGE_STYLES_CATALOG: Final[tuple[CatalogItemDict, ...]] = (
    _merge_labeled_catalog("shortcut_badge_styles")
)
SHORTCUT_BADGE_STYLE_TOKENS: Final[tuple[str, ...]] = tuple(
    str(c["token"]) for c in SHORTCUT_BADGE_STYLES_CATALOG
)
SHORTCUT_ACCENTS_CATALOG: Final[tuple[CatalogItemDict, ...]] = _merge_labeled_catalog(
    "shortcut_accents"
)
SHORTCUT_ACCENT_TOKENS: Final[tuple[str, ...]] = tuple(
    str(c["token"]) for c in SHORTCUT_ACCENTS_CATALOG
)


def normalize_navigate_route(raw: object) -> str:
    """Return a canonical `latter.navigate` route token, or raise `ValueError`."""
    token = str(raw or "").strip().lower()
    if token not in NAVIGATE_ROUTES:
        raise ValueError(f"Unknown navigate route: {token or '(empty)'}")
    return token

MAX_DOCK_ITEMS: Final = 24
MAX_PINNED_ITEMS: Final = 96
SHORTCUT_LABEL_MAX: Final = 24

SHORTCUT_DOMAIN_ACTIONS: Final[dict[str, tuple[tuple[str, str], ...]]] = {
    "light": (("toggle", "Toggle"), ("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "switch": (("toggle", "Toggle"), ("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "input_boolean": (
        ("toggle", "Toggle"),
        ("turn_on", "Turn On"),
        ("turn_off", "Turn Off"),
    ),
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
    "humidifier": (
        ("toggle", "Toggle"),
        ("turn_on", "Turn On"),
        ("turn_off", "Turn Off"),
    ),
    "siren": (("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "water_heater": (("turn_on", "Turn On"), ("turn_off", "Turn Off")),
    "select": (("select_next", "Next Option"), ("select_previous", "Previous Option")),
    "input_select": (
        ("select_next", "Next Option"),
        ("select_previous", "Previous Option"),
    ),
}
SHORTCUT_SUPPORTED_DOMAINS: Final[frozenset[str]] = frozenset(
    SHORTCUT_DOMAIN_ACTIONS.keys()
)
SHORTCUT_DOMAIN_ACTION_SETS: Final[dict[str, frozenset[str]]] = {
    dom: frozenset(act for act, _ in acts)
    for dom, acts in SHORTCUT_DOMAIN_ACTIONS.items()
}
_MDI_ICON_RE: Final = re.compile(r"^mdi:[a-z0-9]+(?:-[a-z0-9]+)*$")
_ENTITY_ID_RE: Final = re.compile(r"^([a-z0-9_]+)\.([a-z0-9_]+)$")


def default_dock_items() -> list[ShortcutItemDict]:
    """Return the canonical default Home Dock `ShortcutItemDict` list."""
    out: list[ShortcutItemDict] = []
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
                    "badge_style": "",
                    "accent": "",
                }
            )
    return out


def sanitize_shortcut_label(val: object, max_chars: int = SHORTCUT_LABEL_MAX) -> str:
    """Return a single-line delimiter-safe shortcut label capped at `max_chars` characters."""
    raw = str(val or "")
    chars: list[str] = []
    prev_space = True
    for ch in raw:
        code = ord(ch)
        if (
            code < _SPACE_ORD
            or code == _DEL_ORD
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


def normalize_mdi_icon(val: object, *, strict: bool = False) -> str:
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


def normalize_shortcut_badge_style(val: object, *, strict: bool = False) -> str:
    """Validate and normalize a shortcut badge style (`""` for default glass, or `"inverted"`)."""
    if val is None:
        return ""
    raw = str(val).strip().lower()
    if not raw or raw == "glass":
        return ""
    if raw in SHORTCUT_BADGE_STYLE_TOKENS:
        return raw
    if strict:
        raise ValueError(f"Unknown shortcut badge style: {val!r}")
    return ""


def normalize_shortcut_accent(val: object, *, strict: bool = False) -> str:
    """Validate and normalize a shortcut semantic accent (`""` for default, or a catalog accent token)."""
    if val is None:
        return ""
    raw = str(val).strip().lower()
    if not raw or raw == "default":
        return ""
    if raw in SHORTCUT_ACCENT_TOKENS:
        return raw
    if strict:
        raise ValueError(f"Unknown shortcut accent: {val!r}")
    return ""


def _normalize_route_shortcut(
    raw: Mapping[str, object], *, is_dock: bool, strict: bool
) -> ShortcutItemDict | None:
    target = str(raw.get("target") or "").strip().lower()
    if is_dock and target in ("settings:root", "app:settings"):
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
    return {
        "kind": "route",
        "target": target,
        "action": "",
        "label": sanitize_shortcut_label(raw.get("label")),
        "icon": normalize_mdi_icon(raw.get("icon"), strict=strict),
        "confirm": False,
        "badge_style": normalize_shortcut_badge_style(
            raw.get("badge_style"), strict=strict
        ),
        "accent": normalize_shortcut_accent(raw.get("accent"), strict=strict),
    }


def _resolve_shortcut_confirm(raw_confirm: object, *, is_dock: bool) -> bool:
    if raw_confirm is None:
        return is_dock
    if isinstance(raw_confirm, str):
        return raw_confirm.strip().lower() in ("1", "true", "on", "yes")
    return bool(raw_confirm)


def _normalize_entity_shortcut(
    raw: Mapping[str, object], *, is_dock: bool, strict: bool
) -> ShortcutItemDict | None:
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
    return {
        "kind": "entity",
        "target": target,
        "action": action,
        "label": sanitize_shortcut_label(raw.get("label")),
        "icon": normalize_mdi_icon(raw.get("icon"), strict=strict),
        "confirm": _resolve_shortcut_confirm(raw.get("confirm"), is_dock=is_dock),
        "badge_style": normalize_shortcut_badge_style(
            raw.get("badge_style"), strict=strict
        ),
        "accent": normalize_shortcut_accent(raw.get("accent"), strict=strict),
    }


def normalize_shortcut_item(
    raw: object,
    *,
    is_dock: bool,
    strict: bool = True,
) -> ShortcutItemDict | None:
    """Validate and normalize one `ShortcutItemDict` (`route` or `entity`)."""
    if not isinstance(raw, Mapping):
        if strict:
            raise ValueError("Each shortcut item must be an object")
        return None
    kind = str(raw.get("kind") or "").strip().lower()
    if kind == "route":
        return _normalize_route_shortcut(raw, is_dock=is_dock, strict=strict)
    if kind == "entity":
        return _normalize_entity_shortcut(raw, is_dock=is_dock, strict=strict)
    if strict:
        raise ValueError(f"Unknown shortcut kind: {kind or '(empty)'}")
    return None


def _normalize_shortcut_list(
    val: object,
    *,
    is_dock: bool,
    max_items: int,
    strict: bool,
) -> list[ShortcutItemDict]:
    if not isinstance(val, (list, tuple)):
        if strict:
            name = "dock_items" if is_dock else "pinned_items"
            raise ValueError(f"{name} must be a list")
        return default_dock_items() if is_dock else []
    out: list[ShortcutItemDict] = []
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
    val: object, *, strict: bool = False
) -> list[ShortcutItemDict]:
    """Validate and normalize a Device's `dock_items` list (`None` -> default Home Dock)."""
    if val is None:
        return default_dock_items()
    return _normalize_shortcut_list(
        val, is_dock=True, max_items=MAX_DOCK_ITEMS, strict=strict
    )


def normalize_pinned_items(
    val: object, *, strict: bool = False
) -> list[ShortcutItemDict]:
    """Validate and normalize a Device's `pinned_items` list (`None` -> `[]`)."""
    if val is None:
        return []
    return _normalize_shortcut_list(
        val, is_dock=False, max_items=MAX_PINNED_ITEMS, strict=strict
    )


# ---------------------------------------------------------------------------
# Protocol v3 Device Preference Specs & Value Resolver
# ---------------------------------------------------------------------------

_DEVICE_PREF_UI: Final[dict[str, dict[str, Any]]] = STUDIO_CONTRACT_DATA[
    "device_pref_ui"
]

_PROTOCOL_PREF_KEYS: Final[set[str]] = {
    str(raw["key"]) for raw in PROTOCOL_V3_DATA["device_pref_specs"]
}
if set(_DEVICE_PREF_UI.keys()) != _PROTOCOL_PREF_KEYS:
    raise RuntimeError(
        "studio_contract.json device_pref_ui keys do not match protocol_v3.json device_pref_specs"
    )

DEVICE_PREF_SPECS: Final[tuple[DevicePrefSpec, ...]] = tuple(
    DevicePrefSpec(
        key=str(raw["key"]),
        label=str(_DEVICE_PREF_UI[str(raw["key"])]["label"]),
        domain=raw["domain"],
        default=raw["default"],
        section=str(_DEVICE_PREF_UI[str(raw["key"])]["section"]),
        capability=raw["capability"],
        group_tier=_DEVICE_PREF_UI[str(raw["key"])].get("group_tier"),
        options=tuple(str(o) for o in (raw.get("options") or ())),
        min_val=int(raw["min"]) if raw.get("min") is not None else None,
        max_val=int(raw["max"]) if raw.get("max") is not None else None,
        step=int(raw["step"]) if raw.get("step") is not None else None,
        unit=str(_DEVICE_PREF_UI[str(raw["key"])].get("unit") or ""),
    )
    for raw in PROTOCOL_V3_DATA["device_pref_specs"]
)

DEVICE_PREF_SPEC_MAP: Final[dict[str, DevicePrefSpec]] = {
    s.key: s for s in DEVICE_PREF_SPECS
}
DEVICE_PREF_KEYS: Final[tuple[str, ...]] = tuple(s.key for s in DEVICE_PREF_SPECS)

WAKE_WORD_MODE_OPTIONS: Final[tuple[str, ...]] = tuple(
    DEVICE_PREF_SPEC_MAP["wake_word_mode"].options
)
START_SCREEN_OPTIONS: Final[tuple[str, ...]] = tuple(
    DEVICE_PREF_SPEC_MAP["start_screen"].options
)
RETURN_TO_HOME_TIMEOUT_OPTIONS: Final[tuple[str, ...]] = tuple(
    DEVICE_PREF_SPEC_MAP["return_to_home_timeout"].options
)
GLASS_STYLE_OPTIONS: Final[tuple[str, ...]] = tuple(
    DEVICE_PREF_SPEC_MAP["glass_style"].options
)


def _resolve_text_pref(key: str, raw: object) -> str:
    if key == "world_clocks":
        return normalize_world_clocks_spec(raw, strict=False)
    if key == "local_clock_label":
        return sanitize_clock_label(raw)
    if key == "alarms_summary":
        return normalize_alarms_summary(raw, strict=False)
    return str(raw).strip()


def _resolve_number_pref(spec: DevicePrefSpec, raw: object) -> bool | int | str:
    if spec.key == "calendar_lookahead_days":
        return snap_calendar_lookahead_days(raw)
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return spec.default
    try:
        ival = int(raw)
    except (TypeError, ValueError):
        return spec.default
    if spec.min_val is not None:
        ival = max(spec.min_val, ival)
    if spec.max_val is not None:
        ival = min(spec.max_val, ival)
    return ival


def resolve_device_pref_value(
    cfg: Mapping[str, object], key: str
) -> bool | int | str:
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
        return _resolve_text_pref(key, raw)
    return _resolve_number_pref(spec, raw)
