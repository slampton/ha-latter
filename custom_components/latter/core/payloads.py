"""Pure Protocol v3 payload packer and domain field formatters for Latter."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
import hashlib
import secrets
from typing import Any
import unicodedata

PROTOCOL_V3_DOMAINS: tuple[str, ...] = (
    "area_context",
    "active_media",
    "remote_config",
    "weather_forecast",
    "calendar_agenda",
)


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
    "", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
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
        """Bump per-domain revisions across all 5 domains so a reconnected device receives a full snapshot."""
        for dom in PROTOCOL_V3_DOMAINS:
            self._domain_revs[dom] = max(1, self._domain_revs.get(dom, 1)) + 1
            self.rev = max(self.rev, self._domain_revs[dom])
        self._domain_hashes.clear()
