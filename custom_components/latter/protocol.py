"""Pure Protocol v3 payload packer, dock/activity policies, and PBKDF2 / PIN session-key security for Latter.

Standard library only (no Home Assistant imports), so standalone unit tests exercise this exact code.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import secrets
import time
from typing import Any
import unicodedata

from .studio.settings import (
    ACTIVITY_SOURCE_KEYS as ACTIVITY_SOURCE_KEYS,
    AREA_CATEGORY_TOKENS as AREA_CATEGORY_TOKENS,
    DEFAULT_AREA_CATEGORIES as DEFAULT_AREA_CATEGORIES,
    DEFAULT_DOCK_ROUTES as DEFAULT_DOCK_ROUTES,
    DEFAULT_GAMES_ITEMS as DEFAULT_GAMES_ITEMS,
    DEFAULT_HOME_CATEGORIES as DEFAULT_HOME_CATEGORIES,
    DEFAULT_TOOLS_ITEMS as DEFAULT_TOOLS_ITEMS,
    DEVICE_PREF_SPEC_MAP as DEVICE_PREF_SPEC_MAP,
    GAMES_ITEM_TOKENS as GAMES_ITEM_TOKENS,
    GAMES_ITEMS_CATALOG as GAMES_ITEMS_CATALOG,
    HOME_CATEGORY_TOKENS as HOME_CATEGORY_TOKENS,
    MAX_DOCK_ITEMS as MAX_DOCK_ITEMS,
    MAX_PINNED_ITEMS as MAX_PINNED_ITEMS,
    SHORTCUT_DOMAIN_ACTION_SETS as SHORTCUT_DOMAIN_ACTION_SETS,
    SHORTCUT_DOMAIN_ACTIONS as SHORTCUT_DOMAIN_ACTIONS,
    SHORTCUT_LABEL_MAX as SHORTCUT_LABEL_MAX,
    SHORTCUT_ROUTE_MAP as SHORTCUT_ROUTE_MAP,
    SHORTCUT_ROUTE_TOKENS as SHORTCUT_ROUTE_TOKENS,
    SHORTCUT_ROUTES_CATALOG as SHORTCUT_ROUTES_CATALOG,
    SHORTCUT_SUPPORTED_DOMAINS as SHORTCUT_SUPPORTED_DOMAINS,
    TOOLS_ITEM_TOKENS as TOOLS_ITEM_TOKENS,
    TOOLS_ITEMS_CATALOG as TOOLS_ITEMS_CATALOG,
    WORLD_CLOCK_CATALOG_MAP as WORLD_CLOCK_CATALOG_MAP,
    default_dock_items as default_dock_items,
    get_cached_zoneinfo as get_cached_zoneinfo,
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
)

# ---------------------------------------------------------------------------
# Protocol v3 Payload Packer, Multi-Tier Delimiter Escaping & Record Formatters
# ---------------------------------------------------------------------------

_PROTOCOL_V3_DATA: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parent / "protocol_v3.json").read_text(encoding="utf-8")
)

PROTOCOL_V3_DOMAINS: tuple[str, ...] = tuple(_PROTOCOL_V3_DATA["domains"].keys())

FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"
SUBFIELD_SEP = "|"

_V3_FIELD_UNSAFE_RE = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]")
_SWITCH_TRUE_TOKENS: frozenset[str] = frozenset({"1", "true", "on", "yes"})
_SWITCH_FALSE_TOKENS: frozenset[str] = frozenset({"0", "false", "off", "no"})
_HEX_RGB_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_LOWER_HEX_RE = re.compile(r"^[0-9a-f]+$")

# calendar_agenda.summary (protocol type "records"): up to CALENDAR_MAX_RECORDS records of
# time|title|location|all_day, each text subfield capped at the length below (characters, after sanitizing).
CALENDAR_MAX_RECORDS = 5
CALENDAR_TIME_MAX = 16
CALENDAR_TITLE_MAX = 48
CALENDAR_LOCATION_MAX = 64
_DAY_ABBR: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_MONTH_ABBR: tuple[str, ...] = (
    "",
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
)

# Home Assistant reports a missing value as one of these states; Protocol v3 sends "" instead (never a sentinel).
HA_ABSENT_STATES: frozenset[str] = frozenset({"", "unknown", "unavailable"})


def ha_value(val: Any) -> Any:
    """Return "" for a value Home Assistant reports as absent (None, "", unknown, unavailable), else the value."""
    if val is None:
        return ""
    if isinstance(val, str) and val.strip().lower() in HA_ABSENT_STATES:
        return ""
    return val


def utf8_safe_truncate(s: str | None, max_bytes: int) -> str:
    """Truncate `s` to at most `max_bytes` UTF-8 bytes without splitting any multi-byte codepoint."""
    if not s or max_bytes <= 0:
        return ""
    text = str(s)
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return raw.decode("utf-8", errors="ignore")
    return raw[:max_bytes].decode("utf-8", errors="ignore")


def escape_v3_subfield(val: Any) -> str:
    """Escape `\\` -> `\\\\`, `|` -> `\\p`, `;` -> `\\s` after stripping control characters."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "1" if val else "0"
    clean = _V3_FIELD_UNSAFE_RE.sub(" ", str(val))
    return clean.replace("\\", "\\\\").replace("|", "\\p").replace(";", "\\s")


def unescape_v3_subfield(val: str | None) -> str:
    """Decode a subfield encoded with `escape_v3_subfield` (`\\\\` -> `\\`, `\\p` -> `|`, `\\s` -> `;`)."""
    if not val:
        return ""
    s = str(val)
    if "\\" not in s:
        return s
    out: list[str] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "\\" and i + 1 < n:
            nxt = s[i + 1]
            if nxt == "\\":
                out.append("\\")
                i += 2
                continue
            if nxt == "p":
                out.append("|")
                i += 2
                continue
            if nxt == "s":
                out.append(";")
                i += 2
                continue
        out.append(ch)
        i += 1
    return "".join(out)


class V3Records(tuple[Sequence[Any], ...]):
    """A Protocol v3 "records" field: a tuple of records, each a sequence of subfields.

    `DomainPayloadPacker.pack` encodes it with `encode_v3_records` (records joined with 0x1E,
    subfields with '|'); every other field goes through `sanitize_v3_field`.
    """


def sanitize_v3_subfield(val: Any, max_len: int | None = None) -> str:
    """Return one subfield of a records field: no separators, no control characters, capped.

    '|' becomes '/', every control character (0x00..0x1F, 0x7F, U+2028, U+2029, ...) becomes a space,
    whitespace runs collapse to one space, and the result is trimmed and cut to `max_len` characters.
    """
    if val is None:
        return ""
    if isinstance(val, bool):
        return "1" if val else "0"
    s = str(val).replace(SUBFIELD_SEP, "/")
    s = "".join(
        " "
        if (ord(ch) <= 0x1F or ord(ch) == 0x7F or unicodedata.category(ch) in ("Cc", "Zl", "Zp"))
        else ch
        for ch in s
    )
    s = " ".join(s.split())
    if max_len is not None and len(s) > max_len:
        s = s[:max_len].rstrip()
    return s


def encode_v3_records(records: Iterable[Sequence[Any]]) -> str:
    """Encode records as 0x1E-joined records of '|'-joined, sanitized subfields ("" for no records)."""
    return RECORD_SEP.join(
        SUBFIELD_SEP.join(sanitize_v3_subfield(sub) for sub in rec) for rec in records
    )


def build_v3_records(
    rows: Iterable[Sequence[Any]], caps: Sequence[int | None], max_records: int
) -> V3Records:
    """Return up to `max_records` sanitized records; `caps[i]` caps subfield i (None = identifiers, uncapped)."""
    out: list[tuple[str, ...]] = []
    for row in rows:
        if len(out) >= max_records:
            break
        out.append(tuple(sanitize_v3_subfield(val, cap) for val, cap in zip(row, caps, strict=True)))
    return V3Records(out)


def _whole_number(val: Any) -> str:
    """Return a rounded whole number as text, or "" when the value is unknown."""
    if val is None or isinstance(val, bool):
        return ""
    try:
        fval = float(val)
        if not math.isfinite(fval):
            return ""
        return str(round(fval))
    except (TypeError, ValueError, OverflowError):
        return ""


def _finite_float_field(val: Any) -> float | str:
    """Return a finite float for Protocol v3 `f32` fields, or "" when absent/non-finite."""
    if val is None or isinstance(val, bool) or val == "":
        return ""
    try:
        fval = float(val)
    except (TypeError, ValueError, OverflowError):
        return ""
    return fval if math.isfinite(fval) else ""


# area_context.cameras_summary: entity_id|name|area_id|caps|unlock_entity
CAMERAS_MAX_RECORDS = 10
CAMERA_NAME_MAX = 32
HUB_ENTITY_NAME_MAX = 32
THERMOSTATS_MAX_RECORDS = 8
LOCKS_MAX_RECORDS = 8
GARAGES_MAX_RECORDS = 6
VACUUMS_MAX_RECORDS = 6
AREA_CLIMATES_MAX_RECORDS = 6


def _temp_tenths(val: Any) -> str:
    """Return a temperature formatted to whole or .1 precision, or '' when unknown."""
    if val is None or isinstance(val, bool):
        return ""
    try:
        fval = float(val)
        if not math.isfinite(fval):
            return ""
        val_f = round(fval, 1)
        return str(int(val_f)) if val_f.is_integer() else f"{val_f:.1f}"
    except (TypeError, ValueError, OverflowError):
        return ""


def thermostat_records(thermostats: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for configured Home Hub thermostats (`entity_id|name|area_id|state|target_temp|current_temp|caps`)."""
    return build_v3_records(
        (
            (
                t.get("entity_id"),
                t.get("name"),
                t.get("area_id"),
                t.get("state"),
                _temp_tenths(t.get("target_temp")),
                _temp_tenths(t.get("current_temp")),
                int(t.get("caps") or 0),
            )
            for t in thermostats
        ),
        (None, HUB_ENTITY_NAME_MAX, None, 24, None, None, None),
        THERMOSTATS_MAX_RECORDS,
    )


def entry_records(entries: Iterable[Mapping[str, Any]], max_records: int) -> V3Records:
    """Records for configured Home Hub locks or garage doors (`entity_id|name|area_id|state`)."""
    return build_v3_records(
        (
            (e.get("entity_id"), e.get("name"), e.get("area_id"), e.get("state"))
            for e in entries
        ),
        (None, HUB_ENTITY_NAME_MAX, None, 24),
        max_records,
    )


def vacuum_records(vacuums: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for configured Home Hub robot vacuums (`entity_id|name|area_id|state|caps`)."""
    return build_v3_records(
        (
            (
                v.get("entity_id"),
                v.get("name"),
                v.get("area_id"),
                v.get("state"),
                int(v.get("caps") or 0),
            )
            for v in vacuums
        ),
        (None, HUB_ENTITY_NAME_MAX, None, 24, None),
        VACUUMS_MAX_RECORDS,
    )


def area_climate_records(climates: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for active-Area climate entities (`entity_id|name|state|target_temp|current_temp|caps`)."""
    return build_v3_records(
        (
            (
                c.get("entity_id"),
                c.get("name"),
                c.get("state"),
                _temp_tenths(c.get("target_temp")),
                _temp_tenths(c.get("current_temp")),
                int(c.get("caps") or 0),
            )
            for c in climates
        ),
        (None, HUB_ENTITY_NAME_MAX, 24, None, None, None),
        AREA_CLIMATES_MAX_RECORDS,
    )


def camera_records(cameras: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for configured cameras, in configured order (`entity_id|name|area_id|caps|unlock_entity`)."""
    return build_v3_records(
        (
            (
                c.get("entity_id"),
                c.get("name"),
                c.get("area_id"),
                int(c.get("caps") or 0),
                c.get("unlock_entity") or "",
            )
            for c in cameras
        ),
        (None, CAMERA_NAME_MAX, None, None, None),
        CAMERAS_MAX_RECORDS,
    )


# area_context.broadcast_phrases: phrase (up to 12 phrases, max 64 chars each)
BROADCAST_PHRASES_MAX_RECORDS = 12
BROADCAST_PHRASE_MAX_LEN = 64


def broadcast_phrase_records(phrases: Iterable[Any]) -> V3Records:
    """Pack ordered Quick Broadcast phrases for `area_context.broadcast_phrases`."""
    rows: list[tuple[str]] = []
    seen: set[str] = set()
    for item in phrases:
        clean = str(item or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        rows.append((clean,))
        if len(rows) >= BROADCAST_PHRASES_MAX_RECORDS:
            break
    return build_v3_records(
        rows, (BROADCAST_PHRASE_MAX_LEN,), BROADCAST_PHRASES_MAX_RECORDS
    )


# remote_config.slots_summary: index|label|entity_id|kind|area_id|state
REMOTE_MAX_RECORDS = 10
REMOTE_LABEL_MAX = 32
REMOTE_KINDS: tuple[str, ...] = ("remote", "media_player")


def remote_slot_records(slots: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for the configured remote slots (`index` 1-based); `kind` is the domain of `entity_id`."""
    rows = []
    for s in slots:
        entity_id = str(s.get("entity_id") or "")
        kind = entity_id.split(".", 1)[0] if "." in entity_id else ""
        if kind not in REMOTE_KINDS:
            raise ValueError(f"A remote slot needs a remote or media_player entity, got {entity_id!r}")
        rows.append((int(s["index"]), s.get("label"), entity_id, kind, s.get("area_id"), s.get("state")))
    return build_v3_records(rows, (None, REMOTE_LABEL_MAX, None, None, None, None), REMOTE_MAX_RECORDS)


# weather_forecast.forecast_5d: day|cond|high|low
FORECAST_MAX_RECORDS = 5
FORECAST_COND_MAX = 24


def forecast_records(days: Iterable[Mapping[str, Any]]) -> V3Records:
    """Daily forecast records: `day` (MON..SUN), `condition`, `high` and `low` as whole degrees ("" if unknown)."""
    return build_v3_records(
        (
            (d.get("day"), d.get("condition"), _whole_number(d.get("high")), _whole_number(d.get("low")))
            for d in days
        ),
        (3, FORECAST_COND_MAX, None, None),
        FORECAST_MAX_RECORDS,
    )


def normalize_temp_unit(unit: Any) -> str:
    """Normalize a temperature unit token to `'C'`, `'F'`, or `''`."""
    raw = str(unit or "").strip().lstrip("°").strip().upper()
    if raw in ("C", "CELSIUS"):
        return "C"
    if raw in ("F", "FAHRENHEIT"):
        return "F"
    return ""


def pack_weather_forecast_fields(
    condition: Any = "",
    temperature: Any = None,
    humidity: Any = None,
    wind_speed: Any = None,
    wind_bearing: Any = None,
    high: Any = None,
    low: Any = None,
    forecast_5d: V3Records | None = None,
    sun_state: Any = "",
    sun_elevation: Any = None,
    sun_azimuth: Any = None,
    sun_next_rising: Any = "",
    sun_next_setting: Any = "",
    moon_phase: Any = "",
    temp_unit: Any = "",
) -> tuple[Any, ...]:
    """Return the 15 ordered body fields (`indices 3..17`) for Protocol v3 `weather_forecast`."""
    return (
        ha_value(condition),
        _finite_float_field(temperature),
        _finite_float_field(humidity),
        _finite_float_field(wind_speed),
        _finite_float_field(wind_bearing),
        _finite_float_field(high),
        _finite_float_field(low),
        forecast_5d if isinstance(forecast_5d, V3Records) else V3Records(),
        ha_value(sun_state),
        _finite_float_field(sun_elevation),
        _finite_float_field(sun_azimuth),
        ha_value(sun_next_rising),
        ha_value(sun_next_setting),
        ha_value(moon_phase),
        normalize_temp_unit(temp_unit),
    )


def pack_active_media_fields(
    state: Any = "",
    title: Any = "",
    artist: Any = "",
    album: Any = "",
    duration: Any = None,
    position: Any = None,
    volume: int | None = None,
    media_type: Any = "",
    art_url: Any = "",
    active_speaker: Any = "",
    speaker_name: Any = "",
    last_speaker: Any = "",
    local_speaker: Any = "",
    is_local: bool = False,
    shuffle: bool = False,
    repeat: Any = "",
    muted: bool = False,
    favorite: bool = False,
    queue_count: int = 0,
    media_caps: int = 0,
) -> tuple[Any, ...]:
    """Return the 20 ordered body fields (`indices 3..22`) for Protocol v3 `active_media`."""
    vol_field: int | str = ""
    if volume is not None and not isinstance(volume, bool):
        try:
            fvol = float(volume)
            if math.isfinite(fvol):
                vol_field = max(0, min(100, round(fvol)))
        except (TypeError, ValueError, OverflowError):
            vol_field = ""
    return (
        ha_value(state),
        ha_value(title),
        ha_value(artist),
        ha_value(album),
        _finite_float_field(duration),
        _finite_float_field(position),
        vol_field,
        ha_value(media_type),
        ha_value(art_url),
        ha_value(active_speaker),
        ha_value(speaker_name),
        ha_value(last_speaker),
        ha_value(local_speaker),
        bool(is_local),
        bool(shuffle),
        ha_value(repeat),
        bool(muted),
        bool(favorite),
        max(0, int(queue_count or 0)),
        max(0, int(media_caps or 0)),
    )


def calendar_time_label(local_start: datetime, today: date, all_day: bool) -> str:
    """Return the agenda record's time: 'TODAY 14:30', 'TOM 09:00', 'FRI 18:00', 'NOV 08 14:30'."""
    days_ahead = (local_start.date() - today).days
    time_str = "ALL DAY" if all_day else local_start.strftime("%H:%M")
    if days_ahead <= 0:
        return f"TODAY {time_str}"
    if days_ahead == 1:
        return f"TOM {time_str}"
    if days_ahead < 7:
        return f"{_DAY_ABBR[local_start.weekday()]} {time_str}"
    month_day = f"{_MONTH_ABBR[local_start.month]} {local_start.day:02d}"
    return month_day if all_day else f"{month_day} {time_str}"


def calendar_agenda_records(events: Iterable[dict[str, Any]], today: date) -> V3Records:
    """Return calendar_agenda.summary records for events already sorted by start."""
    out: list[tuple[str, str, str, str]] = []
    for ev in events:
        if len(out) >= CALENDAR_MAX_RECORDS:
            break
        all_day = bool(ev.get("all_day"))
        out.append(
            (
                sanitize_v3_subfield(calendar_time_label(ev["start_dt"], today, all_day), CALENDAR_TIME_MAX),
                sanitize_v3_subfield(ev.get("summary"), CALENDAR_TITLE_MAX),
                sanitize_v3_subfield(ev.get("location"), CALENDAR_LOCATION_MAX),
                "1" if all_day else "0",
            )
        )
    return V3Records(out)


# calendar_agenda.calendars_meta: entity_id|label|color_idx|can_create|can_delete
CALENDAR_SOURCES_MAX = 8
CALENDAR_SOURCE_LABEL_MAX = 32
CALENDAR_LOCATIONS_MAX = 12
CALENDAR_LOCATION_ITEM_MAX = 64

# latter_set_calendar_view structured event window chunks
CALENDAR_WINDOW_MAX_EVENTS = 64
CALENDAR_WINDOW_CHUNK_SIZE = 12
CALENDAR_WINDOW_UID_MAX = 96
CALENDAR_WINDOW_TITLE_MAX = 64
CALENDAR_WINDOW_LOCATION_MAX = 64
CALENDAR_WINDOW_DESC_MAX = 160


def calendar_sources_records(sources: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for configured/discovered calendars (`entity_id|label|color_idx|can_create|can_delete`)."""
    rows: list[tuple[Any, ...]] = []
    for idx, src in enumerate(sources):
        if idx >= CALENDAR_SOURCES_MAX:
            break
        ent_id = str(src.get("entity_id") or "").strip()
        if not ent_id:
            continue
        label = str(src.get("label") or ent_id.split(".", 1)[-1].replace("_", " ").title()).strip()
        color_idx = int(src.get("color_idx", idx % 6)) % 6
        can_create = "1" if bool(src.get("can_create", False)) else "0"
        can_delete = "1" if bool(src.get("can_delete", False)) else "0"
        rows.append((ent_id, label, str(color_idx), can_create, can_delete))
    return build_v3_records(
        rows,
        (None, CALENDAR_SOURCE_LABEL_MAX, 1, 1, 1),
        CALENDAR_SOURCES_MAX,
    )


def calendar_locations_records(locations: Iterable[Any]) -> V3Records:
    """Single-subfield 0x1E-joined location suggestions (`zone.*` friendly names + recent event locations)."""
    rows: list[tuple[str]] = []
    seen: set[str] = set()
    for raw in locations:
        clean = sanitize_v3_subfield(raw, CALENDAR_LOCATION_ITEM_MAX)
        if not clean:
            continue
        key = clean.lower()
        if key in seen:
            continue
        seen.add(key)
        rows.append((clean,))
        if len(rows) >= CALENDAR_LOCATIONS_MAX:
            break
    return V3Records(rows)


def _sanitize_window_field(val: Any, max_len: int | None = None) -> str:
    """Sanitize a `latter_set_calendar_view` 0x1F-delimited event field while preserving literal '|' characters."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "1" if val else "0"
    s = "".join(
        " "
        if (ord(ch) <= 0x1F or ord(ch) == 0x7F or unicodedata.category(ch) in ("Cc", "Zl", "Zp"))
        else ch
        for ch in str(val)
    )
    s = " ".join(s.split())
    if max_len is not None and len(s) > max_len:
        s = s[:max_len].rstrip()
    return s


def pack_calendar_window_chunks(
    events: Sequence[Mapping[str, Any]],
    window_start: str,
    window_end: str,
    *,
    req_id: int = 0,
    chunk_size: int = CALENDAR_WINDOW_CHUNK_SIZE,
) -> list[dict[str, Any]]:
    """Pack up to 64 structured calendar events into `latter_set_calendar_view` action chunk dicts."""
    eff_chunk_size = max(1, min(16, int(chunk_size)))
    encoded_records: list[str] = []
    for ev in events[:CALENDAR_WINDOW_MAX_EVENTS]:
        start_ymd = _sanitize_window_field(ev.get("start_ymd"), 10)
        end_ymd = _sanitize_window_field(ev.get("end_ymd") or start_ymd, 10)
        if not start_ymd:
            continue
        all_day = bool(ev.get("all_day"))
        start_min = -1 if all_day else max(-1, min(1439, int(ev.get("start_min", 0))))
        end_min = -1 if all_day else max(-1, min(1440, int(ev.get("end_min", -1))))
        cal_idx = max(0, min(7, int(ev.get("cal_idx", 0))))
        uid = _sanitize_window_field(ev.get("uid"), CALENDAR_WINDOW_UID_MAX)
        rec_id = _sanitize_window_field(ev.get("recurrence_id"), CALENDAR_WINDOW_UID_MAX)
        title = _sanitize_window_field(ev.get("summary") or "Event", CALENDAR_WINDOW_TITLE_MAX) or "Event"
        loc = _sanitize_window_field(ev.get("location"), CALENDAR_WINDOW_LOCATION_MAX)
        desc = _sanitize_window_field(ev.get("description"), CALENDAR_WINDOW_DESC_MAX)
        encoded_records.append(
            FIELD_SEP.join(
                (
                    start_ymd,
                    end_ymd,
                    str(start_min),
                    str(end_min),
                    "1" if all_day else "0",
                    str(cal_idx),
                    uid,
                    rec_id,
                    title,
                    loc,
                    desc,
                )
            )
        )

    chunk_count = max(1, math.ceil(len(encoded_records) / eff_chunk_size))
    clean_req = max(0, int(req_id))
    clean_ws = _sanitize_window_field(window_start, 10)
    clean_we = _sanitize_window_field(window_end, 10)
    chunks: list[dict[str, Any]] = []
    for idx in range(chunk_count):
        slice_recs = encoded_records[idx * eff_chunk_size : (idx + 1) * eff_chunk_size]
        chunks.append(
            {
                "req_id": clean_req,
                "chunk_index": idx,
                "chunk_count": chunk_count,
                "window_start": clean_ws,
                "window_end": clean_we,
                "events": RECORD_SEP.join(slice_recs),
            }
        )
    return chunks


def sanitize_v3_field(val: Any) -> str:
    """Convert a field value to a delimiter-safe Protocol v3 string (a V3Records field is encoded as records)."""
    if val is None:
        return ""
    if isinstance(val, V3Records):
        return encode_v3_records(val)
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, float) and not math.isfinite(val):
        return ""
    return _V3_FIELD_UNSAFE_RE.sub(" ", str(val))


class DomainPayloadPacker:
    """Content-hashed per-domain Protocol v3 payload packer ('v3\\x1f<epoch>\\x1f<rev>\\x1f...')."""

    def __init__(self, epoch: int | None = None) -> None:
        """Initialize the packer with a 31-bit session epoch."""
        self.epoch: int = int(epoch) if epoch else (secrets.randbits(31) or 1)
        self.rev: int = 1
        self._domain_hashes: dict[str, str] = {}
        self._domain_revs: dict[str, int] = dict.fromkeys(PROTOCOL_V3_DOMAINS, 1)

    def pack(self, domain: str, *fields: Any) -> tuple[int, str]:
        """Pack domain fields with content-hashed per-domain revision."""
        clean_fields = [sanitize_v3_field(f) for f in fields]
        body = FIELD_SEP.join(clean_fields)
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        prev_digest = self._domain_hashes.get(domain)
        cur_rev = self._domain_revs.get(domain, 0)
        if prev_digest is None:
            cur_rev = max(1, cur_rev)
            self._domain_hashes[domain] = digest
            self._domain_revs[domain] = cur_rev
        elif prev_digest != digest:
            cur_rev = max(1, cur_rev) + 1
            self._domain_hashes[domain] = digest
            self._domain_revs[domain] = cur_rev
            self.rev = max(self.rev, cur_rev)
        return cur_rev, f"v3\x1f{self.epoch}\x1f{cur_rev}\x1f{body}"

    def pack_shortcuts(
        self,
        dock_records: V3Records,
        pinned_records: V3Records,
        *,
        chunk_size: int = 18,
    ) -> tuple[int, tuple[str, ...]]:
        """Pack chunked `shortcuts` frames sharing one content-hashed revision across all chunks."""
        eff_chunk_size = max(1, int(chunk_size))
        dock_blob = encode_v3_records(dock_records)
        pinned_full_blob = encode_v3_records(pinned_records)
        digest = hashlib.sha256(
            f"{dock_blob}\x1f{pinned_full_blob}".encode()
        ).hexdigest()[:16]
        prev_digest = self._domain_hashes.get("shortcuts")
        cur_rev = self._domain_revs.get("shortcuts", 0)
        if prev_digest is None:
            cur_rev = max(1, cur_rev)
            self._domain_hashes["shortcuts"] = digest
            self._domain_revs["shortcuts"] = cur_rev
        elif prev_digest != digest:
            cur_rev = max(1, cur_rev) + 1
            self._domain_hashes["shortcuts"] = digest
            self._domain_revs["shortcuts"] = cur_rev
            self.rev = max(self.rev, cur_rev)

        pinned_total = len(pinned_records)
        chunk_count = max(1, math.ceil(pinned_total / eff_chunk_size))
        frames: list[str] = []
        for chunk_idx in range(chunk_count):
            dock_field = dock_blob if chunk_idx == 0 else ""
            slice_recs = pinned_records[
                chunk_idx * eff_chunk_size : (chunk_idx + 1) * eff_chunk_size
            ]
            pinned_field = encode_v3_records(slice_recs)
            body = FIELD_SEP.join(
                (
                    str(chunk_idx),
                    str(chunk_count),
                    dock_field,
                    str(pinned_total),
                    pinned_field,
                )
            )
            frames.append(f"v3\x1f{self.epoch}\x1f{cur_rev}\x1f{body}")
        return cur_rev, tuple(frames)

    def force_republish_all_domains(self) -> None:
        """Bump per-domain revisions across all 7 domains so a reconnected device receives a full snapshot."""
        for dom in PROTOCOL_V3_DOMAINS:
            self._domain_revs[dom] = max(1, self._domain_revs.get(dom, 1)) + 1
            self.rev = max(self.rev, self._domain_revs[dom])
        self._domain_hashes.clear()


_DEVICE_PREFS_BODY_NAMES: tuple[str, ...] = tuple(
    f["name"] for f in _PROTOCOL_V3_DATA["domains"]["device_prefs"]["fields"]
)


def pack_device_prefs_fields(
    prefs_seq: int,
    cfg: Mapping[str, Any],
    *,
    native_ble_tracking: bool,
    custom_color_hex: str,
    is_round_display: bool = True,
    supports_hw_jpeg: bool = True,
    do_not_disturb: bool | None = None,
) -> tuple[Any, ...]:
    """Return the ordered body fields (`indices 3..70`) for Protocol v3 `device_prefs`."""
    home_enabled = bool(resolve_device_pref_value(cfg, "home_screen_enabled"))
    clean_hex = str(custom_color_hex or "").strip().upper()
    if clean_hex and not _HEX_RGB_RE.fullmatch(clean_hex):
        clean_hex = ""
    out: list[Any] = []
    for name in _DEVICE_PREFS_BODY_NAMES:
        if name == "prefs_seq":
            out.append(max(0, int(prefs_seq)))
        elif name == "ble_beacon_enabled":
            out.append(bool(native_ble_tracking))
        elif name == "theme_color_hex":
            out.append(clean_hex)
        elif name == "do_not_disturb" and do_not_disturb is not None:
            out.append(bool(do_not_disturb))
        elif name == "tools_items":
            try:
                out.append(
                    normalize_tools_items(cfg.get("tools_items", DEFAULT_TOOLS_ITEMS))
                )
            except ValueError:
                out.append(DEFAULT_TOOLS_ITEMS)
        elif name == "games_items":
            try:
                out.append(
                    normalize_games_items(cfg.get("games_items", DEFAULT_GAMES_ITEMS))
                )
            except ValueError:
                out.append(DEFAULT_GAMES_ITEMS)
        else:
            val = resolve_device_pref_value(cfg, name)
            if name == "start_screen" and not home_enabled and val == "Home":
                val = "Time App"
            elif name == "clock_face" and not is_round_display and val == "Modern Analog":
                val = "Minimal Digital"
            elif name == "camera_doorbell_popup" and not supports_hw_jpeg:
                val = "Snapshot"
            out.append(val)
    return tuple(out)


def _parse_strict_switch_token(val: str) -> bool | None:
    low = val.lower()
    if low in _SWITCH_TRUE_TOKENS:
        return True
    if low in _SWITCH_FALSE_TOKENS:
        return False
    return None


def parse_dirty_prefs_records(raw: str | None) -> dict[str, Any]:
    """Parse 0x1E-delimited `key=val` preference records from `device_hello` or `set_device_prefs`."""
    out: dict[str, Any] = {}
    text = str(raw or "")
    if not text:
        return out
    for rec in text.split(RECORD_SEP):
        if "=" not in rec:
            continue
        raw_key, raw_val = rec.split("=", 1)
        key = raw_key.strip()
        val = raw_val.strip()
        if key == "ble_beacon_enabled":
            sw_val = _parse_strict_switch_token(val)
            if sw_val is not None:
                out["native_ble_tracking"] = sw_val
            continue
        if key == "theme_color_hex":
            if _HEX_RGB_RE.fullmatch(val):
                out["device_custom_color"] = val.upper()
            continue
        if key == "tools_items":
            try:
                out["tools_items"] = normalize_tools_items(val)
            except ValueError:
                pass
            continue
        if key == "games_items":
            try:
                out["games_items"] = normalize_games_items(val)
            except ValueError:
                pass
            continue
        spec = DEVICE_PREF_SPEC_MAP.get(key)
        if spec is None:
            continue
        if spec.domain == "switch":
            sw_val = _parse_strict_switch_token(val)
            if sw_val is not None:
                out[key] = sw_val
        elif spec.domain == "select":
            if val in spec.options:
                out[key] = val
        elif spec.domain == "text":
            if key == "world_clocks":
                out[key] = normalize_world_clocks_spec(val, strict=False)
            elif key == "local_clock_label":
                out[key] = sanitize_clock_label(val)
            elif key == "alarms_summary":
                try:
                    out[key] = normalize_alarms_summary(val, strict=True)
                except ValueError:
                    continue
        elif spec.domain == "number":
            try:
                fval = float(val)
                if not math.isfinite(fval):
                    continue
                ival = int(fval)
            except (TypeError, ValueError, OverflowError):
                continue
            if key == "calendar_lookahead_days":
                ival = snap_calendar_lookahead_days(ival)
            else:
                if spec.min_val is not None:
                    ival = max(spec.min_val, ival)
                if spec.max_val is not None:
                    ival = min(spec.max_val, ival)
            out[key] = ival
    return out


def _nth_weekday_of_month(year: int, month: int, weekday: int, nth: int) -> date:
    """Return the `nth` (1..4) or last (`-1`) occurrence of `weekday` (0=Mon..6=Sun) in `year`-`month`."""
    if nth > 0:
        first = date(year, month, 1)
        delta = (weekday - first.weekday()) % 7
        return first + timedelta(days=delta + (nth - 1) * 7)
    next_m = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = next_m - timedelta(days=1)
    delta = (last.weekday() - weekday) % 7
    return last - timedelta(days=delta)


def _catalog_dst_active(rule: str, std_off_min: int, now_utc: datetime) -> bool:
    """Evaluate DST rule in UTC when host OS lacks `/usr/share/zoneinfo` (e.g. bare Windows Python)."""
    yr = now_utc.year
    if rule == "us":
        start_local = datetime(yr, 3, _nth_weekday_of_month(yr, 3, 6, 2).day, 2, 0, tzinfo=UTC)
        end_local = datetime(yr, 11, _nth_weekday_of_month(yr, 11, 6, 1).day, 2, 0, tzinfo=UTC)
        start_utc = start_local - timedelta(minutes=std_off_min)
        end_utc = end_local - timedelta(minutes=std_off_min + 60)
        return start_utc <= now_utc < end_utc
    if rule == "eu":
        start_utc = datetime(yr, 3, _nth_weekday_of_month(yr, 3, 6, -1).day, 1, 0, tzinfo=UTC)
        end_utc = datetime(yr, 10, _nth_weekday_of_month(yr, 10, 6, -1).day, 1, 0, tzinfo=UTC)
        return start_utc <= now_utc < end_utc
    if rule == "eg":
        start_local = datetime(yr, 4, _nth_weekday_of_month(yr, 4, 4, -1).day, 0, 0, tzinfo=UTC)
        end_local = datetime(yr, 10, _nth_weekday_of_month(yr, 10, 3, -1).day, 23, 59, tzinfo=UTC)
        start_utc = start_local - timedelta(minutes=std_off_min)
        end_utc = end_local - timedelta(minutes=std_off_min + 60)
        return start_utc <= now_utc <= end_utc
    if rule == "au":
        end_local = datetime(yr, 4, _nth_weekday_of_month(yr, 4, 6, 1).day, 3, 0, tzinfo=UTC)
        start_local = datetime(yr, 10, _nth_weekday_of_month(yr, 10, 6, 1).day, 2, 0, tzinfo=UTC)
        end_utc = end_local - timedelta(minutes=std_off_min + 60)
        start_utc = start_local - timedelta(minutes=std_off_min)
        return now_utc < end_utc or now_utc >= start_utc
    if rule == "au30":
        end_local = datetime(yr, 4, _nth_weekday_of_month(yr, 4, 6, 1).day, 2, 0, tzinfo=UTC)
        start_local = datetime(yr, 10, _nth_weekday_of_month(yr, 10, 6, 1).day, 2, 0, tzinfo=UTC)
        end_utc = end_local - timedelta(minutes=std_off_min + 30)
        start_utc = start_local - timedelta(minutes=std_off_min)
        return now_utc < end_utc or now_utc >= start_utc
    if rule == "nz":
        end_utc = datetime(yr, 4, _nth_weekday_of_month(yr, 4, 6, 1).day, 3, 0, tzinfo=UTC) - timedelta(hours=13)
        start_utc = datetime(yr, 9, _nth_weekday_of_month(yr, 9, 6, -1).day, 2, 0, tzinfo=UTC) - timedelta(hours=12)
        return now_utc < end_utc or now_utc >= start_utc
    return False


def _format_utc_offset_abbr(offset_min: int) -> str:
    if offset_min == 0:
        return "UTC"
    sign = "+" if offset_min >= 0 else "-"
    abs_m = abs(offset_min)
    hh, mm = divmod(abs_m, 60)
    return f"UTC{sign}{hh}" if mm == 0 else f"UTC{sign}{hh}:{mm:02d}"


def format_tz_record(
    iana: str,
    now_utc: datetime | None = None,
    custom_label: str | None = None,
) -> str:
    """Format `<iana>|<label>|<abbr>|<utc_offset_min>|<is_dst>` for `area_context`."""
    clean_iana = sanitize_v3_field(iana).strip()
    if not clean_iana:
        return ""
    safe_iana = escape_v3_subfield(clean_iana)
    if clean_iana in ("UTC", "Etc/UTC", "GMT", "Etc/GMT", "Etc/GMT+0", "Etc/GMT-0", "Etc/GMT0"):
        return f"{safe_iana}|UTC|UTC|0|0"

    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    cat_entry = WORLD_CLOCK_CATALOG_MAP.get(clean_iana)
    override_lbl = sanitize_clock_label(custom_label) if custom_label else ""
    if override_lbl:
        city = override_lbl
    else:
        city = (
            str(cat_entry["city"])
            if cat_entry is not None
            else clean_iana.rsplit("/", 1)[-1].replace("_", " ")
        )
        city = sanitize_clock_label(city) or safe_iana
    safe_city = escape_v3_subfield(city)

    tz = get_cached_zoneinfo(clean_iana)
    if tz is not None:
        local_dt = now.astimezone(tz)
        off_td = local_dt.utcoffset() or timedelta(0)
        dst_td = local_dt.dst() or timedelta(0)
        off_min = round(off_td.total_seconds() / 60)
        is_dst = dst_td.total_seconds() != 0
        raw_abbr = _V3_FIELD_UNSAFE_RE.sub("", local_dt.tzname() or "").replace("|", "").replace(";", "").strip()
        if (not raw_abbr or raw_abbr[0] in "+-") and cat_entry is not None:
            raw_abbr = str(cat_entry["dst_abbr" if is_dst else "std_abbr"])
        abbr = escape_v3_subfield(raw_abbr or _format_utc_offset_abbr(off_min))
        return f"{safe_iana}|{safe_city}|{abbr}|{off_min}|{'1' if is_dst else '0'}"
    if cat_entry is None:
        return ""
    is_dst = _catalog_dst_active(str(cat_entry["rule"]), int(cat_entry["std_off"]), now)
    off_min = int(cat_entry["dst_off" if is_dst else "std_off"])
    abbr = escape_v3_subfield(str(cat_entry["dst_abbr" if is_dst else "std_abbr"]))
    return f"{safe_iana}|{safe_city}|{abbr}|{off_min}|{'1' if is_dst else '0'}"


def build_time_zone_payloads(
    hass_time_zone: str | None,
    world_clocks_spec: str | None,
    now_utc: datetime | None = None,
) -> tuple[str, str]:
    """Build `(local_tz_info, world_clocks_summary)` for Protocol v3 `area_context`."""
    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    local_tz_info = format_tz_record(str(hass_time_zone or "").strip(), now)
    world_records: list[str] = []
    for lbl, zone_id in parse_world_clocks_spec(world_clocks_spec, strict=False):
        rec = format_tz_record(zone_id, now, custom_label=lbl)
        if rec:
            world_records.append(rec)
    return local_tz_info, ";".join(world_records)


# ---------------------------------------------------------------------------
# Universal Shortcut Engine, Home Dock & Activity Card Policies
# ---------------------------------------------------------------------------

SHORTCUTS_CHUNK_SIZE = 18


__all_area_categories__ = (
    ACTIVITY_SOURCE_KEYS,
    AREA_CATEGORY_TOKENS,
    DEFAULT_AREA_CATEGORIES,
    parse_area_categories,
    normalize_area_categories,
    HOME_CATEGORY_TOKENS,
    DEFAULT_HOME_CATEGORIES,
    parse_home_categories,
    normalize_home_categories,
    TOOLS_ITEMS_CATALOG,
    TOOLS_ITEM_TOKENS,
    DEFAULT_TOOLS_ITEMS,
    parse_tools_items,
    normalize_tools_items,
    GAMES_ITEMS_CATALOG,
    GAMES_ITEM_TOKENS,
    DEFAULT_GAMES_ITEMS,
    parse_games_items,
    normalize_games_items,
    DEFAULT_DOCK_ROUTES,
    MAX_DOCK_ITEMS,
    MAX_PINNED_ITEMS,
    SHORTCUT_ROUTES_CATALOG,
    SHORTCUT_ROUTE_MAP,
    SHORTCUT_ROUTE_TOKENS,
    SHORTCUT_DOMAIN_ACTIONS,
    SHORTCUT_DOMAIN_ACTION_SETS,
    SHORTCUT_SUPPORTED_DOMAINS,
    default_dock_items,
    normalize_dock_items,
    normalize_pinned_items,
    normalize_shortcut_item,
    sanitize_shortcut_label,
)


def resolve_shortcut_entity_icon(
    domain: str,
    *,
    device_class: str = "",
    entity_icon: str = "",
    state: str = "",
) -> str:
    """Return the canonical `mdi:<slug>` icon for an entity shortcut when no custom override is set."""
    explicit = normalize_mdi_icon(entity_icon, strict=False)
    if explicit:
        return explicit
    dom = str(domain or "").strip().lower()
    dclass = str(device_class or "").strip().lower()
    st = str(state or "").strip().lower()
    if dom == "light":
        return "mdi:lightbulb"
    if dom in ("switch", "input_boolean"):
        return "mdi:power-plug" if dclass == "outlet" else "mdi:toggle-switch"
    if dom == "cover":
        if dclass == "garage":
            return "mdi:garage-open" if st in ("open", "opening") else "mdi:garage"
        if dclass == "gate":
            return "mdi:gate"
        if dclass == "door":
            return "mdi:door-open" if st in ("open", "opening") else "mdi:door-closed"
        if dclass == "curtain":
            return "mdi:curtains"
        if dclass in ("blind", "shade", "shutter"):
            return "mdi:blinds-horizontal"
        return "mdi:window-shutter"
    if dom == "fan":
        return "mdi:fan"
    if dom == "valve":
        return "mdi:pipe-valve"
    if dom == "scene":
        return "mdi:palette"
    if dom == "script":
        return "mdi:script-text-play"
    if dom == "automation":
        return "mdi:robot"
    if dom in ("button", "input_button"):
        return "mdi:gesture-tap-button"
    if dom == "lock":
        return "mdi:lock-open" if st in ("unlocked", "unlocking", "open", "opening") else "mdi:lock"
    if dom == "alarm_control_panel":
        return "mdi:shield-home"
    if dom == "vacuum":
        return "mdi:robot-vacuum"
    if dom == "lawn_mower":
        return "mdi:robot-mower"
    if dom == "media_player":
        return "mdi:television" if dclass in ("tv", "receiver") else "mdi:speaker"
    if dom == "climate":
        return "mdi:thermostat"
    if dom == "humidifier":
        return "mdi:air-humidifier"
    if dom == "siren":
        return "mdi:bullhorn"
    if dom == "water_heater":
        return "mdi:water-boiler"
    if dom in ("select", "input_select"):
        return "mdi:form-select"
    return "mdi:flash"


def resolve_shortcut_live_state(domain: str, raw_state: str | None) -> int:
    """Map an HA entity state to compact shortcut wire state (`-1` stateless, `0` off, `1` on, `2` unavailable)."""
    if raw_state is None:
        return 2
    st = str(raw_state).strip().lower()
    if st == "unavailable":
        return 2
    dom = str(domain or "").strip().lower()
    if dom in ("scene", "button", "input_button", "select", "input_select"):
        return -1
    if st in ("", "unknown"):
        return 0 if dom in ("script", "automation") else -1
    if dom in ("cover", "valve"):
        return 1 if st in ("open", "opening") else 0
    if dom == "lock":
        return 1 if st in ("unlocked", "unlocking", "open", "opening") else 0
    if dom == "alarm_control_panel":
        return 0 if st == "disarmed" else 1
    if dom in ("vacuum", "lawn_mower"):
        return 1 if st in ("cleaning", "mowing", "returning") else 0
    if dom == "media_player":
        return 1 if st in ("playing", "buffering") else 0
    if dom in ("climate", "water_heater"):
        return 0 if st == "off" else 1
    return 1 if st == "on" else 0


def shortcut_records(
    items: Iterable[Mapping[str, Any]], *, max_records: int = MAX_PINNED_ITEMS
) -> V3Records:
    """Encode resolved shortcut items (`kind|target|action|label|icon|confirm|state`) into `V3Records`."""
    rows: list[tuple[Any, ...]] = []
    for it in items:
        kind = str(it.get("kind") or "")
        target = str(it.get("target") or "")
        action = str(it.get("action") or "") if kind == "entity" else ""
        label = str(it.get("label") or "")
        icon = str(it.get("icon") or "")
        confirm = "1" if (kind == "entity" and bool(it.get("confirm"))) else "0"
        raw_state = it.get("state")
        if kind != "entity" or raw_state is None or isinstance(raw_state, bool):
            state_val = -1
        else:
            try:
                f_state = float(raw_state)
                state_val = int(f_state) if math.isfinite(f_state) else -1
            except (TypeError, ValueError, OverflowError):
                state_val = -1
            if state_val not in (-1, 0, 1, 2):
                state_val = -1
        rows.append((kind, target, action, label, icon, confirm, str(state_val)))
    return build_v3_records(
        rows,
        (None, None, None, SHORTCUT_LABEL_MAX, None, 1, 2),
        max_records,
    )


def activity_payload(card_on: bool, sources: str) -> tuple[int, str]:
    """Return (activity_card, activity_sources) for Protocol v3."""
    clean = normalize_activity_sources(sources)
    return (1 if card_on and clean else 0), clean


# ---------------------------------------------------------------------------
# 3-Tier Perimeter Security Policy, PIN Session-Key Wrap & Brute-Force Lockout
# ---------------------------------------------------------------------------

SECURITY_PIN_POLICIES: tuple[str, ...] = ("auto", "allow", "require_pin", "block")
MIN_PIN_LEN: int = 4
MAX_PIN_LEN: int = 12
PIN_SESSION_KEY_BYTES: int = 32
PIN_WRAP_PREFIX: str = "v1:"
PBKDF2_ITERATIONS: int = 200_000
_HASH_SCHEME: str = "pbkdf2_sha256"
_SALT_BYTES: int = 16

_GARAGE_COVER_CLASSES: frozenset[str] = frozenset({"garage", "gate", "door"})
_OPENING_COVER_ACTIONS: frozenset[str] = frozenset(
    {"turn_on", "open", "open_cover", "toggle", "set_level"}
)


class PinWrapError(ValueError):
    """Raised when a `v1:` session-key wrapped PIN fails format, key, replay, MAC, or digit validation."""

    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason


def normalize_security_pin_policy(value: str | None) -> str:
    """Return a valid security PIN policy (`auto`, `allow`, `require_pin`, `block`), else `auto`."""
    cleaned = str(value or "").strip().lower()
    return cleaned if cleaned in SECURITY_PIN_POLICIES else "auto"


def effective_security_pin_policy(
    configured_policy: str | None,
    *,
    is_roaming: bool,
    alarm_has_code: bool,
) -> str:
    """Resolve `auto` to `require_pin` on stationary displays or when an alarm code is active."""
    norm = normalize_security_pin_policy(configured_policy)
    if norm in ("allow", "require_pin", "block"):
        return norm
    if (not is_roaming) or alarm_has_code:
        return "require_pin"
    return "allow"


def is_valid_pin_digits(pin: str | None) -> bool:
    """Return True if `pin` is `MIN_PIN_LEN..MAX_PIN_LEN` (`4..12`) ASCII digits."""
    if not isinstance(pin, str):
        return False
    stripped = pin.strip()
    return MIN_PIN_LEN <= len(stripped) <= MAX_PIN_LEN and stripped.isascii() and stripped.isdigit()


def is_wrapped_pin_code(code: str | None) -> bool:
    """Return True if `code` carries the `v1:` PIN session-key envelope prefix."""
    return isinstance(code, str) and code.strip().startswith(PIN_WRAP_PREFIX)


def mint_pin_session_key() -> tuple[str, bytes]:
    """Mint a random 8-hex `key_id` and 32-byte HMAC-SHA256 session key for bound PIN transport."""
    return secrets.token_hex(4), secrets.token_bytes(PIN_SESSION_KEY_BYTES)


def _validate_pin_key_material(key_id: str, key_bytes: bytes) -> tuple[str, bytes]:
    kid = str(key_id or "").strip().lower()
    if len(kid) != 8 or not _LOWER_HEX_RE.fullmatch(kid):
        raise ValueError("PIN session key_id must be 8 lowercase hex characters")
    raw_key = bytes(key_bytes)
    if len(raw_key) != PIN_SESSION_KEY_BYTES:
        raise ValueError(f"PIN session key_bytes must be {PIN_SESSION_KEY_BYTES} bytes")
    return kid, raw_key


def wrap_pin_code(
    key_id: str,
    key_bytes: bytes,
    nonce: int,
    entity_id: str,
    action: str,
    code: str,
) -> str:
    """Encrypt-then-MAC wrap a `4..12` digit PIN as `v1:<key_id>:<nonce_hex8>:<ct_hex>:<mac_hex32>`."""
    kid, raw_key = _validate_pin_key_material(key_id, key_bytes)
    nonce_int = int(nonce)
    if nonce_int < 1 or nonce_int > 0xFFFFFFFF:
        raise ValueError("PIN session nonce must be in 1..0xFFFFFFFF")
    clean_code = str(code or "").strip()
    if not is_valid_pin_digits(clean_code):
        raise ValueError(f"PIN code must be {MIN_PIN_LEN} to {MAX_PIN_LEN} ASCII digits")

    nonce_hex8 = f"{nonce_int:08x}"
    ent = str(entity_id or "").strip()
    act = str(action or "").strip()
    pt_bytes = clean_code.encode("ascii")
    keystream = hmac.new(
        raw_key,
        f"stream|{kid}|{nonce_hex8}".encode(),
        hashlib.sha256,
    ).digest()[: len(pt_bytes)]
    ct_hex = bytes(b ^ k for b, k in zip(pt_bytes, keystream, strict=True)).hex()
    mac_hex32 = hmac.new(
        raw_key,
        f"latter-pin-v1|{kid}|{nonce_hex8}|{ent}|{act}|{ct_hex}".encode(),
        hashlib.sha256,
    ).hexdigest()[:32]
    return f"v1:{kid}:{nonce_hex8}:{ct_hex}:{mac_hex32}"


def unwrap_pin_code(
    key_id: str,
    key_bytes: bytes,
    last_nonce: int,
    entity_id: str,
    action: str,
    wrapped: str,
) -> tuple[str, int]:
    """Verify and decrypt a `v1:` wrapped PIN, returning `(plaintext_pin, nonce)`."""
    expected_kid, raw_key = _validate_pin_key_material(key_id, key_bytes)
    if int(last_nonce) < 0:
        raise ValueError("last_nonce must be >= 0")

    parts = str(wrapped or "").strip().split(":")
    if len(parts) != 5 or parts[0] != "v1":
        raise PinWrapError("malformed", "Invalid v1 PIN envelope format")
    wire_kid, nonce_hex8, ct_hex, wire_mac = parts[1], parts[2], parts[3], parts[4]
    if (
        len(wire_kid) != 8
        or len(nonce_hex8) != 8
        or len(wire_mac) != 32
        or len(ct_hex) % 2 != 0
        or not (2 * MIN_PIN_LEN <= len(ct_hex) <= 2 * MAX_PIN_LEN)
        or not _LOWER_HEX_RE.fullmatch(wire_kid)
        or not _LOWER_HEX_RE.fullmatch(nonce_hex8)
        or not _LOWER_HEX_RE.fullmatch(ct_hex)
        or not _LOWER_HEX_RE.fullmatch(wire_mac)
    ):
        raise PinWrapError("malformed", "Invalid hex field in v1 PIN envelope")

    if not hmac.compare_digest(wire_kid, expected_kid):
        raise PinWrapError("key_mismatch", "PIN session key_id mismatch")

    nonce_int = int(nonce_hex8, 16)
    if nonce_int < 1 or nonce_int <= int(last_nonce):
        raise PinWrapError("replay", "PIN session nonce replay or out-of-order")

    ent = str(entity_id or "").strip()
    act = str(action or "").strip()
    expected_mac = hmac.new(
        raw_key,
        f"latter-pin-v1|{expected_kid}|{nonce_hex8}|{ent}|{act}|{ct_hex}".encode(),
        hashlib.sha256,
    ).hexdigest()[:32]
    if not hmac.compare_digest(wire_mac, expected_mac):
        raise PinWrapError("bad_mac", "PIN session MAC verification failed")

    ct_bytes = bytes.fromhex(ct_hex)
    keystream = hmac.new(
        raw_key,
        f"stream|{expected_kid}|{nonce_hex8}".encode(),
        hashlib.sha256,
    ).digest()[: len(ct_bytes)]
    pt_bytes = bytes(c ^ k for c, k in zip(ct_bytes, keystream, strict=True))
    try:
        pin = pt_bytes.decode("ascii")
    except UnicodeDecodeError as err:
        raise PinWrapError("invalid_digits", "Decrypted PIN is non-ASCII") from err
    if not is_valid_pin_digits(pin):
        raise PinWrapError("invalid_digits", "Decrypted PIN is not 4 to 12 ASCII digits")
    return pin, nonce_int


class PinLockoutTracker:
    """Pure-stdlib exponential-backoff brute-force lockout tracker for PIN verification."""

    def __init__(
        self,
        *,
        max_failures: int = 5,
        base_cooldown_s: float = 60.0,
        max_cooldown_s: float = 900.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures: int = max(1, int(max_failures))
        self.base_cooldown_s: float = max(1.0, float(base_cooldown_s))
        self.max_cooldown_s: float = max(self.base_cooldown_s, float(max_cooldown_s))
        self._clock: Callable[[], float] = clock
        self._failures: dict[str, int] = {}
        self._locked_until: dict[str, float] = {}

    def _now(self, now: float | None) -> float:
        return float(now) if now is not None else float(self._clock())

    def remaining_cooldown(self, scope: str = "global", *, now: float | None = None) -> float:
        """Return seconds remaining in active lockout for `scope`, or `0.0` when unlocked."""
        key = str(scope or "global")
        until = self._locked_until.get(key, 0.0)
        if until <= 0.0:
            return 0.0
        rem = until - self._now(now)
        if rem <= 0.0:
            self._locked_until.pop(key, None)
            return 0.0
        return rem

    def is_locked_out(self, scope: str = "global", *, now: float | None = None) -> bool:
        """Return True if `scope` is currently under an active brute-force cooldown."""
        return self.remaining_cooldown(scope, now=now) > 0.0

    def failure_count(self, scope: str = "global") -> int:
        """Return the consecutive failure count recorded for `scope`."""
        return self._failures.get(str(scope or "global"), 0)

    def record_failure(self, scope: str = "global", *, now: float | None = None) -> float:
        """Record a failed PIN attempt for `scope` and return any newly applied cooldown in seconds."""
        key = str(scope or "global")
        t = self._now(now)
        count = self._failures.get(key, 0) + 1
        self._failures[key] = count
        if count < self.max_failures:
            return 0.0
        exponent = min(count - self.max_failures, 20)
        cooldown = min(self.max_cooldown_s, self.base_cooldown_s * (2**exponent))
        self._locked_until[key] = max(self._locked_until.get(key, 0.0), t + cooldown)
        return self._locked_until[key] - t

    def record_success(self, scope: str = "global") -> None:
        """Clear consecutive failures and cooldown for `scope` after a valid PIN."""
        key = str(scope or "global")
        self._failures.pop(key, None)
        self._locked_until.pop(key, None)

    def reset(self, scope: str | None = None) -> None:
        """Clear lockout state for `scope`, or all scopes when `scope` is None."""
        if scope is None:
            self._failures.clear()
            self._locked_until.clear()
            return
        self.record_success(scope)


def hash_security_pin(pin: str) -> str:
    """Hash a 4-12 digit PIN with PBKDF2-HMAC-SHA256 and a random 128-bit salt."""
    cleaned = str(pin or "").strip()
    if not is_valid_pin_digits(cleaned):
        raise ValueError(f"Security PIN must be {MIN_PIN_LEN} to {MAX_PIN_LEN} digits")
    salt = secrets.token_bytes(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        cleaned.encode("ascii"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"{_HASH_SCHEME}${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_security_pin(pin: str | None, stored_hash: str | None) -> bool:
    """Verify `pin` against `stored_hash` in constant time."""
    if not is_valid_pin_digits(pin) or not stored_hash or not isinstance(stored_hash, str):
        return False
    parts = stored_hash.strip().split("$")
    if len(parts) != 4 or parts[0] != _HASH_SCHEME:
        return False
    try:
        iters = int(parts[1])
        if iters < 10_000 or iters > 1_000_000:
            return False
        salt = bytes.fromhex(parts[2])
        expected_dk = bytes.fromhex(parts[3])
    except ValueError:
        return False
    if len(salt) < 8 or len(expected_dk) != 32:
        return False
    candidate_dk = hashlib.pbkdf2_hmac(
        "sha256",
        str(pin).strip().encode("ascii"),
        salt,
        iters,
    )
    return hmac.compare_digest(candidate_dk, expected_dk)


def is_sensitive_perimeter_action(
    domain: str,
    action: str,
    *,
    device_class: str = "",
    entity_id: str = "",
    level: int | None = None,
) -> bool:
    """Return True only for perimeter-opening actions; closing/arming actions are always allowed."""
    dom = str(domain or "").strip().lower()
    act = str(action or "").strip().lower()
    if dom == "lock":
        return act in ("unlock", "open")
    if dom == "alarm_control_panel":
        return act == "disarm"
    if dom == "cover":
        dclass = str(device_class or "").strip().lower()
        ent_low = str(entity_id or "").strip().lower()
        is_perimeter_cover = dclass in _GARAGE_COVER_CLASSES or any(
            tok in ent_low for tok in ("garage", "gate")
        )
        if not is_perimeter_cover or act not in _OPENING_COVER_ACTIONS:
            return False
        return not (act == "set_level" and level is not None and int(level) <= 0)
    return False


def check_perimeter_action_allowed(
    policy: str,
    *,
    provided_code: str | None,
    stored_pin_hash: str | None,
    alarm_accepts_passthrough_code: bool = False,
) -> tuple[bool, str]:
    """Check whether a sensitive perimeter action is permitted under `policy`.

    Returns `(allowed, error_translation_key)`.
    """
    norm = policy if policy in ("allow", "require_pin", "block") else "require_pin"
    if norm == "allow":
        return True, ""
    if norm == "block":
        return False, "security_action_blocked"

    code = str(provided_code or "").strip()
    if not code:
        return False, "security_pin_required"
    if stored_pin_hash:
        if verify_security_pin(code, stored_pin_hash):
            return True, ""
        return False, "security_pin_invalid"
    if alarm_accepts_passthrough_code and is_valid_pin_digits(code):
        return True, ""
    return False, "security_pin_not_configured"
