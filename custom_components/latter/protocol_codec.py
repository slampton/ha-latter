"""Pure-stdlib Protocol v3 payload packer, multi-tier delimiter escaping, and record formatters (`L0b`)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
import hashlib
import math
import re
import secrets
from typing import Any, Final
import unicodedata

from .protocol_specs import (
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
    PROTOCOL_V3_DATA,
    PROTOCOL_V3_DOMAINS as PROTOCOL_V3_DOMAINS,
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
    DevicePrefSpec,
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

FIELD_SEP: Final = "\x1f"
RECORD_SEP: Final = "\x1e"
SUBFIELD_SEP: Final = "|"
SHORTCUTS_CHUNK_SIZE: Final = 18

_CTRL_MAX_ORD: Final = 0x1F
_DEL_ORD: Final = 0x7F
_DAYS_PER_WEEK: Final = 7
_DECEMBER_MONTH: Final = 12
_MINUTES_PER_HOUR: Final = 60
_MAX_CAL_CHUNK_SIZE: Final = 16
_MAX_CAL_IDX: Final = 7
_MAX_MINUTE_IN_DAY: Final = 1439
_MIDNIGHT_END_MINUTE: Final = 1440
_MAX_PERCENT: Final = 100
_COLOR_PALETTE_MOD: Final = 6
_EPOCH_BITS: Final = 31

_V3_FIELD_UNSAFE_RE: Final = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]")
_SWITCH_TRUE_TOKENS: Final[frozenset[str]] = frozenset({"1", "true", "on", "yes"})
_SWITCH_FALSE_TOKENS: Final[frozenset[str]] = frozenset({"0", "false", "off", "no"})
_HEX_RGB_RE: Final = re.compile(r"^#[0-9A-Fa-f]{6}$")
_UTC_ZONE_ALIASES: Final[frozenset[str]] = frozenset(
    {"UTC", "Etc/UTC", "GMT", "Etc/GMT", "Etc/GMT+0", "Etc/GMT-0", "Etc/GMT0"}
)

CALENDAR_MAX_RECORDS: Final = 5
CALENDAR_TIME_MAX: Final = 16
CALENDAR_TITLE_MAX: Final = 48
CALENDAR_LOCATION_MAX: Final = 64
_DAY_ABBR: Final[tuple[str, ...]] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_MONTH_ABBR: Final[tuple[str, ...]] = (
    "", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)
HA_ABSENT_STATES: Final[frozenset[str]] = frozenset({"", "unknown", "unavailable"})

CAMERAS_MAX_RECORDS: Final = 10
CAMERA_NAME_MAX: Final = 32
HUB_ENTITY_NAME_MAX: Final = 32
THERMOSTATS_MAX_RECORDS: Final = 8
LOCKS_MAX_RECORDS: Final = 8
GARAGES_MAX_RECORDS: Final = 6
VACUUMS_MAX_RECORDS: Final = 6
AREA_CLIMATES_MAX_RECORDS: Final = 6
BROADCAST_PHRASES_MAX_RECORDS: Final = 12
BROADCAST_PHRASE_MAX_LEN: Final = 64
REMOTE_MAX_RECORDS: Final = 10
REMOTE_LABEL_MAX: Final = 32
REMOTE_KINDS: Final[tuple[str, ...]] = ("remote", "media_player")
FORECAST_MAX_RECORDS: Final = 5
FORECAST_COND_MAX: Final = 24
CALENDAR_SOURCES_MAX: Final = 8
CALENDAR_SOURCE_LABEL_MAX: Final = 32
CALENDAR_LOCATIONS_MAX: Final = 12
CALENDAR_LOCATION_ITEM_MAX: Final = 64
CALENDAR_WINDOW_MAX_EVENTS: Final = 64
CALENDAR_WINDOW_CHUNK_SIZE: Final = 12
CALENDAR_WINDOW_UID_MAX: Final = 96
CALENDAR_WINDOW_TITLE_MAX: Final = 64
CALENDAR_WINDOW_LOCATION_MAX: Final = 64
CALENDAR_WINDOW_DESC_MAX: Final = 160

_DEVICE_PREFS_BODY_NAMES: Final[tuple[str, ...]] = tuple(
    str(f["name"]) for f in PROTOCOL_V3_DATA["domains"]["device_prefs"]["fields"]
)
_UNESCAPE_MAP: Final[dict[str, str]] = {"\\": "\\", "p": "|", "s": ";"}


def ha_value(val: Any) -> Any:
    """Return `""` for a value Home Assistant reports as absent (`None`, `""`, `unknown`, `unavailable`)."""
    if val is None:
        return ""
    if isinstance(val, str) and val.strip().lower() in HA_ABSENT_STATES:
        return ""
    return val


def utf8_safe_truncate(s: str | None, max_bytes: int) -> str:
    """Truncate `s` to at most `max_bytes` UTF-8 bytes without splitting any multi-byte codepoint."""
    if not s or max_bytes <= 0:
        return ""
    raw = str(s).encode("utf-8", errors="replace")
    return raw[:max_bytes].decode("utf-8", errors="ignore")


def escape_v3_subfield(val: object) -> str:
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
        if ch == "\\" and i + 1 < n and (mapped := _UNESCAPE_MAP.get(s[i + 1])) is not None:
            out.append(mapped)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


class V3Records(tuple[Sequence[Any], ...]):
    """A Protocol v3 `records` field: a tuple of records, each a sequence of subfields."""


def _is_control_or_sep_char(ch: str) -> bool:
    code = ord(ch)
    return code <= _CTRL_MAX_ORD or code == _DEL_ORD or unicodedata.category(ch) in ("Cc", "Zl", "Zp")


def sanitize_v3_subfield(val: object, max_len: int | None = None) -> str:
    """Return one subfield of a records field: no separators, no control characters, capped."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "1" if val else "0"
    s = str(val).replace(SUBFIELD_SEP, "/")
    s = " ".join("".join(" " if _is_control_or_sep_char(ch) else ch for ch in s).split())
    return s[:max_len].rstrip() if max_len is not None and len(s) > max_len else s


def encode_v3_records(records: Iterable[Sequence[object]]) -> str:
    """Encode records as `0x1E`-joined records of `|`-joined, sanitized subfields."""
    return RECORD_SEP.join(
        SUBFIELD_SEP.join(sanitize_v3_subfield(sub) for sub in rec) for rec in records
    )


def build_v3_records(
    rows: Iterable[Sequence[object]], caps: Sequence[int | None], max_records: int
) -> V3Records:
    """Return up to `max_records` sanitized records; `caps[i]` caps subfield `i` (`None` = uncapped)."""
    out: list[tuple[str, ...]] = []
    for row in rows:
        if len(out) >= max_records:
            break
        out.append(tuple(sanitize_v3_subfield(val, cap) for val, cap in zip(row, caps, strict=True)))
    return V3Records(out)


def _whole_number(val: object) -> str:
    if val is None or isinstance(val, bool) or not isinstance(val, (int, float, str)):
        return ""
    try:
        fval = float(val)
        return str(round(fval)) if math.isfinite(fval) else ""
    except (TypeError, ValueError, OverflowError):
        return ""


def _finite_float_field(val: object) -> float | str:
    if val is None or isinstance(val, bool) or val == "" or not isinstance(val, (int, float, str)):
        return ""
    try:
        fval = float(val)
    except (TypeError, ValueError, OverflowError):
        return ""
    return fval if math.isfinite(fval) else ""


def _temp_tenths(val: object) -> str:
    if val is None or isinstance(val, bool) or not isinstance(val, (int, float, str)):
        return ""
    try:
        fval = float(val)
        if not math.isfinite(fval):
            return ""
        val_f = round(fval, 1)
        return str(int(val_f)) if val_f.is_integer() else f"{val_f:.1f}"
    except (TypeError, ValueError, OverflowError):
        return ""


def _int_or_zero(val: object) -> int:
    if isinstance(val, bool) or not isinstance(val, (int, float, str)):
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def thermostat_records(thermostats: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for configured Home Hub thermostats (`entity_id|name|area_id|state|target_temp|current_temp|caps`)."""
    rows = (
        (
            t.get("entity_id"), t.get("name"), t.get("area_id"), t.get("state"),
            _temp_tenths(t.get("target_temp")), _temp_tenths(t.get("current_temp")), _int_or_zero(t.get("caps")),
        )
        for t in thermostats
    )
    return build_v3_records(rows, (None, HUB_ENTITY_NAME_MAX, None, 24, None, None, None), THERMOSTATS_MAX_RECORDS)


def entry_records(entries: Iterable[Mapping[str, Any]], max_records: int) -> V3Records:
    """Records for configured Home Hub locks or garage doors (`entity_id|name|area_id|state`)."""
    rows = ((e.get("entity_id"), e.get("name"), e.get("area_id"), e.get("state")) for e in entries)
    return build_v3_records(rows, (None, HUB_ENTITY_NAME_MAX, None, 24), max_records)


def vacuum_records(vacuums: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for configured Home Hub robot vacuums (`entity_id|name|area_id|state|caps`)."""
    rows = (
        (v.get("entity_id"), v.get("name"), v.get("area_id"), v.get("state"), _int_or_zero(v.get("caps")))
        for v in vacuums
    )
    return build_v3_records(rows, (None, HUB_ENTITY_NAME_MAX, None, 24, None), VACUUMS_MAX_RECORDS)


def area_climate_records(climates: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for active-Area climate entities (`entity_id|name|state|target_temp|current_temp|caps`)."""
    rows = (
        (
            c.get("entity_id"), c.get("name"), c.get("state"),
            _temp_tenths(c.get("target_temp")), _temp_tenths(c.get("current_temp")), _int_or_zero(c.get("caps")),
        )
        for c in climates
    )
    return build_v3_records(rows, (None, HUB_ENTITY_NAME_MAX, 24, None, None, None), AREA_CLIMATES_MAX_RECORDS)


def camera_records(cameras: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for configured cameras, in configured order (`entity_id|name|area_id|caps|unlock_entity`)."""
    rows = (
        (c.get("entity_id"), c.get("name"), c.get("area_id"), _int_or_zero(c.get("caps")), c.get("unlock_entity") or "")
        for c in cameras
    )
    return build_v3_records(rows, (None, CAMERA_NAME_MAX, None, None, None), CAMERAS_MAX_RECORDS)


def broadcast_phrase_records(phrases: Iterable[object]) -> V3Records:
    """Pack ordered Quick Broadcast phrases for `area_context.broadcast_phrases`."""
    rows: list[tuple[str]] = []
    seen: set[str] = set()
    for item in phrases:
        clean = str(item or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            rows.append((clean,))
            if len(rows) >= BROADCAST_PHRASES_MAX_RECORDS:
                break
    return build_v3_records(rows, (BROADCAST_PHRASE_MAX_LEN,), BROADCAST_PHRASES_MAX_RECORDS)


def remote_slot_records(slots: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for the configured remote slots (`index` 1-based); `kind` is the domain of `entity_id`."""
    rows: list[tuple[object, ...]] = []
    for s in slots:
        entity_id = str(s.get("entity_id") or "")
        kind = entity_id.split(".", 1)[0] if "." in entity_id else ""
        if kind not in REMOTE_KINDS:
            raise ValueError(f"A remote slot needs a remote or media_player entity, got {entity_id!r}")
        rows.append((int(s["index"]), s.get("label"), entity_id, kind, s.get("area_id"), s.get("state")))
    return build_v3_records(rows, (None, REMOTE_LABEL_MAX, None, None, None, None), REMOTE_MAX_RECORDS)


def forecast_records(days: Iterable[Mapping[str, Any]]) -> V3Records:
    """Daily forecast records: `day` (`MON..SUN`), `condition`, `high` and `low` as whole degrees."""
    rows = (
        (d.get("day"), d.get("condition"), _whole_number(d.get("high")), _whole_number(d.get("low")))
        for d in days
    )
    return build_v3_records(rows, (3, FORECAST_COND_MAX, None, None), FORECAST_MAX_RECORDS)


def normalize_temp_unit(unit: object) -> str:
    """Normalize a temperature unit token to `'C'`, `'F'`, or `''`."""
    raw = str(unit or "").strip().lstrip("°").strip().upper()
    if raw in ("C", "CELSIUS"):
        return "C"
    return "F" if raw in ("F", "FAHRENHEIT") else ""


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


def _clamp_volume_field(volume: int | float | None) -> int | str:
    if volume is None or isinstance(volume, bool):
        return ""
    try:
        fvol = float(volume)
        return max(0, min(_MAX_PERCENT, round(fvol))) if math.isfinite(fvol) else ""
    except (TypeError, ValueError, OverflowError):
        return ""


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
    return (
        ha_value(state), ha_value(title), ha_value(artist), ha_value(album),
        _finite_float_field(duration), _finite_float_field(position), _clamp_volume_field(volume),
        ha_value(media_type), ha_value(art_url), ha_value(active_speaker), ha_value(speaker_name),
        ha_value(last_speaker), ha_value(local_speaker), bool(is_local), bool(shuffle),
        ha_value(repeat), bool(muted), bool(favorite), max(0, int(queue_count or 0)), max(0, int(media_caps or 0)),
    )


def calendar_time_label(local_start: datetime, today: date, all_day: bool) -> str:
    """Return the agenda record's time: `'TODAY 14:30'`, `'TOM 09:00'`, `'FRI 18:00'`, `'NOV 08 14:30'`."""
    days_ahead = (local_start.date() - today).days
    time_str = "ALL DAY" if all_day else local_start.strftime("%H:%M")
    if days_ahead <= 0:
        return f"TODAY {time_str}"
    if days_ahead == 1:
        return f"TOM {time_str}"
    if days_ahead < _DAYS_PER_WEEK:
        return f"{_DAY_ABBR[local_start.weekday()]} {time_str}"
    month_day = f"{_MONTH_ABBR[local_start.month]} {local_start.day:02d}"
    return month_day if all_day else f"{month_day} {time_str}"


def calendar_agenda_records(events: Iterable[Mapping[str, Any]], today: date) -> V3Records:
    """Return `calendar_agenda.summary` records for events already sorted by start."""
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


def calendar_sources_records(sources: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for configured/discovered calendars (`entity_id|label|color_idx|can_create|can_delete`)."""
    rows: list[tuple[object, ...]] = []
    for idx, src in enumerate(sources):
        if idx >= CALENDAR_SOURCES_MAX:
            break
        ent_id = str(src.get("entity_id") or "").strip()
        if not ent_id:
            continue
        default_lbl = ent_id.split(".", 1)[-1].replace("_", " ").title()
        label = str(src.get("label") or default_lbl).strip()
        color_idx = int(src.get("color_idx", idx % _COLOR_PALETTE_MOD)) % _COLOR_PALETTE_MOD
        can_create = "1" if bool(src.get("can_create", False)) else "0"
        can_delete = "1" if bool(src.get("can_delete", False)) else "0"
        rows.append((ent_id, label, str(color_idx), can_create, can_delete))
    return build_v3_records(rows, (None, CALENDAR_SOURCE_LABEL_MAX, 1, 1, 1), CALENDAR_SOURCES_MAX)


def calendar_locations_records(locations: Iterable[object]) -> V3Records:
    """Single-subfield `0x1E`-joined location suggestions (`zone.*` friendly names + recent locations)."""
    rows: list[tuple[str]] = []
    seen: set[str] = set()
    for raw in locations:
        clean = sanitize_v3_subfield(raw, CALENDAR_LOCATION_ITEM_MAX)
        if clean and (key := clean.lower()) not in seen:
            seen.add(key)
            rows.append((clean,))
            if len(rows) >= CALENDAR_LOCATIONS_MAX:
                break
    return V3Records(rows)


def _sanitize_window_field(val: object, max_len: int | None = None) -> str:
    """Sanitize a `latter_set_calendar_view` `0x1F`-delimited event field while preserving literal `|`."""
    if val is None:
        return ""
    if isinstance(val, bool):
        return "1" if val else "0"
    s = " ".join("".join(" " if _is_control_or_sep_char(ch) else ch for ch in str(val)).split())
    return s[:max_len].rstrip() if max_len is not None and len(s) > max_len else s


def pack_calendar_window_chunks(
    events: Sequence[Mapping[str, Any]],
    window_start: str,
    window_end: str,
    *,
    req_id: int = 0,
    chunk_size: int = CALENDAR_WINDOW_CHUNK_SIZE,
) -> list[dict[str, Any]]:
    """Pack up to 64 structured calendar events into `latter_set_calendar_view` action chunk dicts."""
    eff_chunk_size = max(1, min(_MAX_CAL_CHUNK_SIZE, int(chunk_size)))
    encoded_records: list[str] = []
    for ev in events[:CALENDAR_WINDOW_MAX_EVENTS]:
        start_ymd = _sanitize_window_field(ev.get("start_ymd"), 10)
        end_ymd = _sanitize_window_field(ev.get("end_ymd") or start_ymd, 10)
        if not start_ymd:
            continue
        all_day = bool(ev.get("all_day"))
        start_min = -1 if all_day else max(-1, min(_MAX_MINUTE_IN_DAY, int(ev.get("start_min", 0))))
        end_min = -1 if all_day else max(-1, min(_MIDNIGHT_END_MINUTE, int(ev.get("end_min", -1))))
        cal_idx = max(0, min(_MAX_CAL_IDX, int(ev.get("cal_idx", 0))))
        uid = _sanitize_window_field(ev.get("uid"), CALENDAR_WINDOW_UID_MAX)
        rec_id = _sanitize_window_field(ev.get("recurrence_id"), CALENDAR_WINDOW_UID_MAX)
        title = _sanitize_window_field(ev.get("summary") or "Event", CALENDAR_WINDOW_TITLE_MAX) or "Event"
        loc = _sanitize_window_field(ev.get("location"), CALENDAR_WINDOW_LOCATION_MAX)
        desc = _sanitize_window_field(ev.get("description"), CALENDAR_WINDOW_DESC_MAX)
        encoded_records.append(
            FIELD_SEP.join(
                (
                    start_ymd, end_ymd, str(start_min), str(end_min), "1" if all_day else "0",
                    str(cal_idx), uid, rec_id, title, loc, desc,
                )
            )
        )

    chunk_count = max(1, math.ceil(len(encoded_records) / eff_chunk_size))
    clean_req = max(0, int(req_id))
    clean_ws = _sanitize_window_field(window_start, 10)
    clean_we = _sanitize_window_field(window_end, 10)
    return [
        {
            "req_id": clean_req,
            "chunk_index": idx,
            "chunk_count": chunk_count,
            "window_start": clean_ws,
            "window_end": clean_we,
            "events": RECORD_SEP.join(encoded_records[idx * eff_chunk_size : (idx + 1) * eff_chunk_size]),
        }
        for idx in range(chunk_count)
    ]


def sanitize_v3_field(val: object) -> str:
    """Convert a field value to a delimiter-safe Protocol v3 string (`V3Records` encoded as records)."""
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
    """Content-hashed per-domain Protocol v3 payload packer (`'v3\\x1f<epoch>\\x1f<rev>\\x1f...'`)."""

    def __init__(self, epoch: int | None = None) -> None:
        """Initialize the packer with a 31-bit session epoch."""
        self.epoch: int = int(epoch) if epoch else (secrets.randbits(_EPOCH_BITS) or 1)
        self.rev: int = 1
        self._domain_hashes: dict[str, str] = {}
        self._domain_revs: dict[str, int] = dict.fromkeys(PROTOCOL_V3_DOMAINS, 1)

    def _bump_or_keep_rev(self, domain: str, digest: str) -> int:
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
        return cur_rev

    def pack(self, domain: str, *fields: object) -> tuple[int, str]:
        """Pack domain fields with content-hashed per-domain revision."""
        body = FIELD_SEP.join(sanitize_v3_field(f) for f in fields)
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        cur_rev = self._bump_or_keep_rev(domain, digest)
        return cur_rev, f"v3\x1f{self.epoch}\x1f{cur_rev}\x1f{body}"

    def pack_shortcuts(
        self,
        dock_records: V3Records,
        pinned_records: V3Records,
        *,
        chunk_size: int = SHORTCUTS_CHUNK_SIZE,
    ) -> tuple[int, tuple[str, ...]]:
        """Pack chunked `shortcuts` frames sharing one content-hashed revision across all chunks."""
        eff_chunk_size = max(1, int(chunk_size))
        dock_blob = encode_v3_records(dock_records)
        pinned_full_blob = encode_v3_records(pinned_records)
        digest = hashlib.sha256(f"{dock_blob}\x1f{pinned_full_blob}".encode()).hexdigest()[:16]
        cur_rev = self._bump_or_keep_rev("shortcuts", digest)
        pinned_total = len(pinned_records)
        chunk_count = max(1, math.ceil(pinned_total / eff_chunk_size))
        frames = [
            f"v3\x1f{self.epoch}\x1f{cur_rev}\x1f"
            + FIELD_SEP.join(
                (
                    str(chunk_idx),
                    str(chunk_count),
                    dock_blob if chunk_idx == 0 else "",
                    str(pinned_total),
                    encode_v3_records(pinned_records[chunk_idx * eff_chunk_size : (chunk_idx + 1) * eff_chunk_size]),
                )
            )
            for chunk_idx in range(chunk_count)
        ]
        return cur_rev, tuple(frames)

    def force_republish_all_domains(self) -> None:
        """Bump per-domain revisions across all 7 domains so a reconnected device receives a full snapshot."""
        for dom in PROTOCOL_V3_DOMAINS:
            self._domain_revs[dom] = max(1, self._domain_revs.get(dom, 1)) + 1
            self.rev = max(self.rev, self._domain_revs[dom])
        self._domain_hashes.clear()


def _safe_launcher_csv(raw: object, normalizer: Any, fallback: str) -> str:
    try:
        return str(normalizer(raw))
    except ValueError:
        return fallback


def _apply_pref_trait_clamps(
    name: str,
    val: bool | int | str,
    *,
    home_enabled: bool,
    is_round_display: bool,
    supports_hw_jpeg: bool,
) -> bool | int | str:
    if name == "start_screen" and not home_enabled and val == "Home":
        return "Time App"
    if name == "clock_face" and not is_round_display and val == "Modern Analog":
        return "Minimal Digital"
    if name == "camera_doorbell_popup" and not supports_hw_jpeg:
        return "Snapshot"
    return val


def _resolve_pref_body_field(
    name: str,
    cfg: Mapping[str, Any],
    *,
    overrides: Mapping[str, bool | int | str],
    home_enabled: bool,
    is_round_display: bool,
    supports_hw_jpeg: bool,
) -> bool | int | str:
    if name in overrides:
        return overrides[name]
    if name == "tools_items":
        return _safe_launcher_csv(cfg.get("tools_items", DEFAULT_TOOLS_ITEMS), normalize_tools_items, DEFAULT_TOOLS_ITEMS)
    if name == "games_items":
        return _safe_launcher_csv(cfg.get("games_items", DEFAULT_GAMES_ITEMS), normalize_games_items, DEFAULT_GAMES_ITEMS)
    val = resolve_device_pref_value(cfg, name)
    return _apply_pref_trait_clamps(
        name, val, home_enabled=home_enabled, is_round_display=is_round_display, supports_hw_jpeg=supports_hw_jpeg
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
    overrides: dict[str, bool | int | str] = {
        "prefs_seq": max(0, int(prefs_seq)),
        "ble_beacon_enabled": bool(native_ble_tracking),
        "theme_color_hex": clean_hex,
    }
    if do_not_disturb is not None:
        overrides["do_not_disturb"] = bool(do_not_disturb)
    return tuple(
        _resolve_pref_body_field(
            name,
            cfg,
            overrides=overrides,
            home_enabled=home_enabled,
            is_round_display=is_round_display,
            supports_hw_jpeg=supports_hw_jpeg,
        )
        for name in _DEVICE_PREFS_BODY_NAMES
    )


def _parse_strict_switch_token(val: str) -> bool | None:
    low = val.lower()
    if low in _SWITCH_TRUE_TOKENS:
        return True
    return False if low in _SWITCH_FALSE_TOKENS else None


def _parse_dirty_special_key(key: str, val: str, out: dict[str, Any]) -> bool:
    if key == "ble_beacon_enabled":
        sw_val = _parse_strict_switch_token(val)
        if sw_val is not None:
            out["native_ble_tracking"] = sw_val
        return True
    if key == "theme_color_hex":
        if _HEX_RGB_RE.fullmatch(val):
            out["device_custom_color"] = val.upper()
        return True
    if key in ("tools_items", "games_items"):
        norm = normalize_tools_items if key == "tools_items" else normalize_games_items
        try:
            out[key] = norm(val)
        except ValueError:
            pass
        return True
    return False


def _parse_dirty_text_spec_value(key: str, val: str) -> str | None:
    if key == "world_clocks":
        return normalize_world_clocks_spec(val, strict=False)
    if key == "local_clock_label":
        return sanitize_clock_label(val)
    if key == "alarms_summary":
        try:
            return normalize_alarms_summary(val, strict=True)
        except ValueError:
            return None
    return None


def _parse_dirty_number_spec_value(spec: DevicePrefSpec, val: str) -> int | None:
    try:
        fval = float(val)
        if not math.isfinite(fval):
            return None
        ival = int(fval)
    except (TypeError, ValueError, OverflowError):
        return None
    if spec.key == "calendar_lookahead_days":
        return snap_calendar_lookahead_days(ival)
    if spec.min_val is not None:
        ival = max(spec.min_val, ival)
    if spec.max_val is not None:
        ival = min(spec.max_val, ival)
    return ival


def _parse_dirty_spec_value(spec: DevicePrefSpec, val: str) -> bool | int | str | None:
    if spec.domain == "switch":
        return _parse_strict_switch_token(val)
    if spec.domain == "select":
        return val if val in spec.options else None
    if spec.domain == "text":
        return _parse_dirty_text_spec_value(spec.key, val)
    return _parse_dirty_number_spec_value(spec, val)


def parse_dirty_prefs_records(raw: str | None) -> dict[str, Any]:
    """Parse `0x1E`-delimited `key=val` preference records from `device_hello` or `set_device_prefs`."""
    out: dict[str, Any] = {}
    text = str(raw or "")
    if not text:
        return out
    for rec in text.split(RECORD_SEP):
        if "=" not in rec:
            continue
        raw_key, raw_val = rec.split("=", 1)
        key, val = raw_key.strip(), raw_val.strip()
        if _parse_dirty_special_key(key, val, out):
            continue
        spec = DEVICE_PREF_SPEC_MAP.get(key)
        if spec is not None and (parsed := _parse_dirty_spec_value(spec, val)) is not None:
            out[key] = parsed
    return out


# ---------------------------------------------------------------------------
# Time Zone & World Clock Wire Builders (`area_context`)
# ---------------------------------------------------------------------------


def _nth_weekday_of_month(year: int, month: int, weekday: int, nth: int) -> date:
    """Return the `nth` (`1..4`) or last (`-1`) occurrence of `weekday` (`0=Mon..6=Sun`) in `year`-`month`."""
    if nth > 0:
        first = date(year, month, 1)
        delta = (weekday - first.weekday()) % _DAYS_PER_WEEK
        return first + timedelta(days=delta + (nth - 1) * _DAYS_PER_WEEK)
    next_m = date(year + 1, 1, 1) if month == _DECEMBER_MONTH else date(year, month + 1, 1)
    last = next_m - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % _DAYS_PER_WEEK)


def _dst_northern(yr: int, std_off_min: int, now_utc: datetime, rule: str) -> bool:
    if rule == "us":
        s_loc = datetime(yr, 3, _nth_weekday_of_month(yr, 3, 6, 2).day, 2, 0, tzinfo=UTC)
        e_loc = datetime(yr, 11, _nth_weekday_of_month(yr, 11, 6, 1).day, 2, 0, tzinfo=UTC)
        return (s_loc - timedelta(minutes=std_off_min)) <= now_utc < (e_loc - timedelta(minutes=std_off_min + _MINUTES_PER_HOUR))
    if rule == "eu":
        s_utc = datetime(yr, 3, _nth_weekday_of_month(yr, 3, 6, -1).day, 1, 0, tzinfo=UTC)
        e_utc = datetime(yr, 10, _nth_weekday_of_month(yr, 10, 6, -1).day, 1, 0, tzinfo=UTC)
        return s_utc <= now_utc < e_utc
    s_loc = datetime(yr, 4, _nth_weekday_of_month(yr, 4, 4, -1).day, 0, 0, tzinfo=UTC)
    e_loc = datetime(yr, 10, _nth_weekday_of_month(yr, 10, 3, -1).day, 23, 59, tzinfo=UTC)
    return (s_loc - timedelta(minutes=std_off_min)) <= now_utc <= (e_loc - timedelta(minutes=std_off_min + _MINUTES_PER_HOUR))


def _dst_southern(yr: int, std_off_min: int, now_utc: datetime, rule: str) -> bool:
    if rule in ("au", "au30"):
        end_hr = 3 if rule == "au" else 2
        dst_shift = _MINUTES_PER_HOUR if rule == "au" else 30
        e_loc = datetime(yr, 4, _nth_weekday_of_month(yr, 4, 6, 1).day, end_hr, 0, tzinfo=UTC)
        s_loc = datetime(yr, 10, _nth_weekday_of_month(yr, 10, 6, 1).day, 2, 0, tzinfo=UTC)
        return now_utc < (e_loc - timedelta(minutes=std_off_min + dst_shift)) or now_utc >= (s_loc - timedelta(minutes=std_off_min))
    e_utc = datetime(yr, 4, _nth_weekday_of_month(yr, 4, 6, 1).day, 3, 0, tzinfo=UTC) - timedelta(hours=13)
    s_utc = datetime(yr, 9, _nth_weekday_of_month(yr, 9, 6, -1).day, 2, 0, tzinfo=UTC) - timedelta(hours=12)
    return now_utc < e_utc or now_utc >= s_utc


def _catalog_dst_active(rule: str, std_off_min: int, now_utc: datetime) -> bool:
    """Evaluate DST rule in UTC when host OS lacks `/usr/share/zoneinfo` (e.g. bare Windows Python)."""
    if rule in ("us", "eu", "eg"):
        return _dst_northern(now_utc.year, std_off_min, now_utc, rule)
    return _dst_southern(now_utc.year, std_off_min, now_utc, rule) if rule in ("au", "au30", "nz") else False


def _format_utc_offset_abbr(offset_min: int) -> str:
    if offset_min == 0:
        return "UTC"
    sign = "+" if offset_min >= 0 else "-"
    hh, mm = divmod(abs(offset_min), _MINUTES_PER_HOUR)
    return f"UTC{sign}{hh}" if mm == 0 else f"UTC{sign}{hh}:{mm:02d}"


def format_tz_record(
    iana: str, now_utc: datetime | None = None, custom_label: str | None = None
) -> str:
    """Format `<iana>|<label>|<abbr>|<utc_offset_min>|<is_dst>` for `area_context`."""
    clean_iana = sanitize_v3_field(iana).strip()
    if not clean_iana:
        return ""
    safe_iana = escape_v3_subfield(clean_iana)
    if clean_iana in _UTC_ZONE_ALIASES:
        return f"{safe_iana}|UTC|UTC|0|0"

    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    cat_entry = WORLD_CLOCK_CATALOG_MAP.get(clean_iana)
    override_lbl = sanitize_clock_label(custom_label) if custom_label else ""
    if override_lbl:
        city = override_lbl
    else:
        raw_city = (
            str(cat_entry["city"])
            if cat_entry is not None and "city" in cat_entry
            else clean_iana.rsplit("/", 1)[-1].replace("_", " ")
        )
        city = sanitize_clock_label(raw_city) or safe_iana
    safe_city = escape_v3_subfield(city)

    tz = get_cached_zoneinfo(clean_iana)
    if tz is not None:
        local_dt = now.astimezone(tz)
        off_td = local_dt.utcoffset() or timedelta(0)
        dst_td = local_dt.dst() or timedelta(0)
        off_min = round(off_td.total_seconds() / _MINUTES_PER_HOUR)
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
    hass_time_zone: str | None, world_clocks_spec: str | None, now_utc: datetime | None = None
) -> tuple[str, str]:
    """Build `(local_tz_info, world_clocks_summary)` for Protocol v3 `area_context`."""
    now = (now_utc or datetime.now(UTC)).astimezone(UTC)
    local_tz_info = format_tz_record(str(hass_time_zone or "").strip(), now)
    world_records = [
        rec
        for lbl, zone_id in parse_world_clocks_spec(world_clocks_spec, strict=False)
        if (rec := format_tz_record(zone_id, now, custom_label=lbl))
    ]
    return local_tz_info, ";".join(world_records)
