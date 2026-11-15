"""Pure Protocol v3 payload packer, dock/activity policies, and PBKDF2 security policy for Latter.

Standard library only (no Home Assistant imports), so standalone unit tests exercise this exact code.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
import hashlib
import hmac
import json
from pathlib import Path
import secrets
from typing import Any
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .studio.settings import (
    AREA_CATEGORY_TOKENS,
    DEFAULT_AREA_CATEGORIES,
    DEFAULT_HOME_CATEGORIES,
    DEVICE_PREF_SPEC_MAP,
    HOME_CATEGORY_TOKENS,
    WORLD_CLOCK_CATALOG_MAP,
    normalize_alarms_summary,
    normalize_area_categories,
    normalize_home_categories,
    normalize_world_clocks_spec,
    parse_area_categories,
    parse_home_categories,
    parse_world_clocks_spec,
    resolve_device_pref_value,
    sanitize_clock_label,
)

# ---------------------------------------------------------------------------
# Protocol v3 Payload Packer & Record Formatters
# ---------------------------------------------------------------------------

_PROTOCOL_V3_DATA: dict[str, Any] = json.loads(
    (Path(__file__).resolve().parent / "protocol_v3.json").read_text(encoding="utf-8")
)

PROTOCOL_V3_DOMAINS: tuple[str, ...] = tuple(_PROTOCOL_V3_DATA["domains"].keys())

FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"
SUBFIELD_SEP = "|"

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


class V3Records(tuple):
    """A Protocol v3 "records" field: a tuple of records, each a sequence of subfields.

    `DomainPayloadPacker.pack` encodes it with `encode_v3_records` (records joined with 0x1E,
    subfields with '|'); every other field goes through `sanitize_v3_field`.
    """


def sanitize_v3_subfield(val: Any, max_len: int | None = None) -> str:
    """Return one subfield of a records field: no separators, no control characters, capped.

    '|' becomes '/', every control character (0x1F, 0x1E, 0x1D, newlines, tabs, ...) becomes a space,
    whitespace runs collapse to one space, and the result is trimmed and cut to `max_len` characters.
    """
    if val is None:
        return ""
    if isinstance(val, bool):
        return "1" if val else "0"
    s = str(val).replace(SUBFIELD_SEP, "/")
    s = "".join(" " if unicodedata.category(ch) in ("Cc", "Zl", "Zp") else ch for ch in s)
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
        return str(round(float(val)))
    except (TypeError, ValueError, OverflowError):
        return ""


# area_context.cameras_summary: entity_id|name|area_id|snapshot_url
CAMERAS_MAX_RECORDS = 10
CAMERA_NAME_MAX = 32


def camera_records(cameras: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for the configured cameras, in configured order (`entity_id`, `name`, `area_id`, `snapshot_url`)."""
    return build_v3_records(
        ((c.get("entity_id"), c.get("name"), c.get("area_id"), c.get("snapshot_url")) for c in cameras),
        (None, CAMERA_NAME_MAX, None, None),
        CAMERAS_MAX_RECORDS,
    )


# area_context.intercom_targets_summary: target_id|label|kind
INTERCOM_MAX_RECORDS = 10
INTERCOM_LABEL_MAX = 32
INTERCOM_KINDS: tuple[str, ...] = ("all", "device")


def intercom_target_records(targets: Iterable[Mapping[str, Any]]) -> V3Records:
    """Records for call_target: `kind` all (every other Latter Device) or device (one Latter Device)."""
    rows = []
    for t in targets:
        kind = str(t.get("kind") or "")
        if kind not in INTERCOM_KINDS:
            raise ValueError(f"Unknown intercom target kind: {kind!r}")
        rows.append((t.get("target_id"), t.get("label"), kind))
    return build_v3_records(rows, (None, INTERCOM_LABEL_MAX, None), INTERCOM_MAX_RECORDS)


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


def sanitize_v3_field(val: Any) -> str:
    """Convert a field value to a delimiter-safe Protocol v3 string (a V3Records field is encoded as records)."""
    if val is None:
        return ""
    if isinstance(val, V3Records):
        return encode_v3_records(val)
    if isinstance(val, bool):
        return "1" if val else "0"
    s = str(val)
    for ch in ("\x1f", "\x1e", "\x1d", "\n", "\r"):
        if ch in s:
            s = s.replace(ch, " ")
    return s


class DomainPayloadPacker:
    """Content-hashed per-domain Protocol v3 payload packer ('v3\\x1f<epoch>\\x1f<rev>\\x1f...')."""

    def __init__(self, epoch: int | None = None) -> None:
        """Initialize the packer with a 31-bit session epoch."""
        self.epoch: int = int(epoch) if epoch else (secrets.randbits(31) or 1)
        self.rev: int = 1
        self._domain_hashes: dict[str, str] = {}
        self._domain_revs: dict[str, int] = {dom: 1 for dom in PROTOCOL_V3_DOMAINS}

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

    def force_republish_all_domains(self) -> None:
        """Bump per-domain revisions across all 6 domains so a reconnected device receives a full snapshot."""
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
) -> tuple[Any, ...]:
    """Return the 53 ordered body fields (wire indices 3..55) for Protocol v3 `device_prefs`."""
    home_enabled = bool(resolve_device_pref_value(cfg, "home_screen_enabled"))
    clean_hex = str(custom_color_hex or "").strip().upper()
    out: list[Any] = []
    for name in _DEVICE_PREFS_BODY_NAMES:
        if name == "prefs_seq":
            out.append(max(0, int(prefs_seq)))
        elif name == "ble_beacon_enabled":
            out.append(bool(native_ble_tracking))
        elif name == "theme_color_hex":
            out.append(clean_hex)
        else:
            val = resolve_device_pref_value(cfg, name)
            if name == "start_screen" and not home_enabled and val == "Home":
                val = "Time App"
            elif name == "clock_face" and not is_round_display and val == "Modern Analog":
                val = "Minimal Digital"
            out.append(val)
    return tuple(out)


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
            out["native_ble_tracking"] = val.lower() in ("1", "true", "on", "yes")
            continue
        spec = DEVICE_PREF_SPEC_MAP.get(key)
        if spec is None:
            continue
        if spec.domain == "switch":
            out[key] = val.lower() in ("1", "true", "on", "yes")
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
                ival = int(float(val))
            except (TypeError, ValueError):
                continue
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
    clean_iana = str(iana or "").strip()
    if not clean_iana:
        return ""
    if clean_iana in ("UTC", "Etc/UTC", "GMT", "Etc/GMT"):
        return f"{clean_iana}|UTC|UTC|0|0"

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
        city = sanitize_clock_label(city) or clean_iana

    try:
        tz = ZoneInfo(clean_iana)
        local_dt = now.astimezone(tz)
        off_td = local_dt.utcoffset() or timedelta(0)
        dst_td = local_dt.dst() or timedelta(0)
        off_min = round(off_td.total_seconds() / 60)
        is_dst = dst_td.total_seconds() != 0
        raw_abbr = (local_dt.tzname() or "").replace("|", "").replace(";", "").strip()
        if (not raw_abbr or raw_abbr[0] in "+-") and cat_entry is not None:
            raw_abbr = str(cat_entry["dst_abbr" if is_dst else "std_abbr"])
        abbr = raw_abbr or _format_utc_offset_abbr(off_min)
        return f"{clean_iana}|{city}|{abbr}|{off_min}|{'1' if is_dst else '0'}"
    except (ZoneInfoNotFoundError, ValueError):
        if cat_entry is None:
            return ""
        is_dst = _catalog_dst_active(str(cat_entry["rule"]), int(cat_entry["std_off"]), now)
        off_min = int(cat_entry["dst_off" if is_dst else "std_off"])
        abbr = str(cat_entry["dst_abbr" if is_dst else "std_abbr"])
        return f"{clean_iana}|{city}|{abbr}|{off_min}|{'1' if is_dst else '0'}"


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
# Home Dock & Activity Card Policies
# ---------------------------------------------------------------------------

DOCK_APP_TOKENS: tuple[str, ...] = tuple(
    c["token"] for c in _PROTOCOL_V3_DATA["catalogs"]["dock_apps"]
)

# Canonical order; Studio shows one switch per source in this order.
ACTIVITY_SOURCE_KEYS: tuple[str, ...] = tuple(
    c["token"] for c in _PROTOCOL_V3_DATA["catalogs"]["activity_sources"]
)


__all_area_categories__ = (
    AREA_CATEGORY_TOKENS,
    DEFAULT_AREA_CATEGORIES,
    parse_area_categories,
    normalize_area_categories,
    HOME_CATEGORY_TOKENS,
    DEFAULT_HOME_CATEGORIES,
    parse_home_categories,
    normalize_home_categories,
)


def parse_dock_apps(csv: str | None) -> list[str]:
    """Return the known dock apps named in `csv`, in order, without duplicates."""
    out: list[str] = []
    for raw in str(csv or "").split(","):
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


def normalize_activity_sources(value: Any) -> str:
    """Return the sources as canonical CSV ("" = every source off); raise ValueError for an unknown key."""
    raw = value if isinstance(value, (list, tuple)) else str(value or "").split(",")
    names = {str(t).strip().lower() for t in raw if str(t).strip()}
    unknown = sorted(names - set(ACTIVITY_SOURCE_KEYS))
    if unknown:
        raise ValueError(f"Unknown Activity Card source: {', '.join(unknown)}")
    return ",".join(k for k in ACTIVITY_SOURCE_KEYS if k in names)


def activity_payload(card_on: bool, sources: str) -> tuple[int, str]:
    """Return (activity_card, activity_sources) for Protocol v3."""
    clean = normalize_activity_sources(sources)
    return (1 if card_on and clean else 0), clean


# ---------------------------------------------------------------------------
# 3-Tier Perimeter Security Policy & PBKDF2-HMAC-SHA256 PIN Verification
# ---------------------------------------------------------------------------

SECURITY_PIN_POLICIES: tuple[str, ...] = ("auto", "allow", "require_pin", "block")
PBKDF2_ITERATIONS: int = 200_000
_HASH_SCHEME: str = "pbkdf2_sha256"
_SALT_BYTES: int = 16

_GARAGE_COVER_CLASSES: frozenset[str] = frozenset({"garage", "gate", "door"})
_OPENING_COVER_ACTIONS: frozenset[str] = frozenset(
    {"turn_on", "open", "open_cover", "toggle", "set_level"}
)


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
    """Return True if `pin` is 4 to 12 ASCII digits."""
    if not isinstance(pin, str):
        return False
    stripped = pin.strip()
    return 4 <= len(stripped) <= 12 and stripped.isascii() and stripped.isdigit()


def hash_security_pin(pin: str) -> str:
    """Hash a 4-12 digit PIN with PBKDF2-HMAC-SHA256 and a random 128-bit salt."""
    cleaned = str(pin or "").strip()
    if not is_valid_pin_digits(cleaned):
        raise ValueError("Security PIN must be 4 to 12 digits")
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
    if dom == "doorbell":
        return act == "unlock_door"
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
