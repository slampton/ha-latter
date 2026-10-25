"""Family Calendar Agenda Serialization & Event Creation Engine for Latter."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DAY_ABBR: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
MONTH_ABBR: tuple[str, ...] = (
    "", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)


def _discover_calendars(hass: HomeAssistant, configured: list[str]) -> list[str]:
    """Return configured calendar entity_ids or auto-discover all available calendars."""
    if configured:
        valid = [c for c in configured if hass.states.get(c) is not None]
        if valid:
            return valid
    return [
        state_obj.entity_id
        for state_obj in hass.states.async_all("calendar")
        if state_obj.state not in ("unavailable", "unknown")
    ]


def _format_event_time_label(start_dt: datetime, now_local: datetime, all_day: bool = False) -> str:
    """Format a compact time prefix ('TODAY 14:30', 'TOM 09:00', 'FRI 18:00', 'NOV 08 14:30')."""
    local_start = dt_util.as_local(start_dt)
    days_ahead = (local_start.date() - now_local.date()).days
    time_str = "ALL DAY" if all_day else local_start.strftime("%H:%M")

    if days_ahead <= 0:
        return f"TODAY {time_str}"
    if days_ahead == 1:
        return f"TOM {time_str}"
    if days_ahead < 7:
        day_name = DAY_ABBR[local_start.weekday()]
        return f"{day_name} {time_str}"
    month_name = MONTH_ABBR[local_start.month]
    if all_day:
        return f"{month_name} {local_start.day:02d}"
    return f"{month_name} {local_start.day:02d} {time_str}"


def _parse_event_dict(
    ev: dict[str, Any], cal_id: str, now_local: datetime
) -> dict[str, Any] | None:
    """Parse a raw calendar event dictionary into a normalized structure."""
    summary = str(ev.get("summary") or ev.get("message") or "Event").strip()
    start_raw = ev.get("start") or ev.get("start_time")
    end_raw = ev.get("end") or ev.get("end_time")
    if not start_raw:
        return None

    parsed_start = dt_util.parse_datetime(str(start_raw))
    is_all_day = False
    if parsed_start is None:
        parsed_date = dt_util.parse_date(str(start_raw))
        if parsed_date is not None:
            is_all_day = True
            parsed_start = datetime.combine(
                parsed_date,
                datetime.min.time(),
                tzinfo=now_local.tzinfo,
            )
    if parsed_start is None:
        return None

    return {
        "summary": summary,
        "start_dt": dt_util.as_local(parsed_start),
        "start_raw": str(start_raw),
        "end_raw": str(end_raw or ""),
        "location": str(ev.get("location") or ""),
        "calendar_id": cal_id,
        "all_day": is_all_day,
    }


async def async_fetch_calendar_agenda(
    hass: HomeAssistant,
    calendar_entities: list[str],
    days: int = 30,
    max_events: int = 25,
    map_url_builder: Any = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Fetch upcoming events across calendars and return (semicolon_string, slot_items)."""
    targets = _discover_calendars(hass, calendar_entities)
    if not targets:
        return "NONE", []

    now_utc = dt_util.utcnow()
    now_local = dt_util.now()
    lookahead_days = max(1, min(int(days or 30), 60))
    end_utc = now_utc + timedelta(days=lookahead_days)

    raw_events: list[dict[str, Any]] = []
    if hass.services.has_service("calendar", "get_events"):
        for cal_id in targets:
            try:
                resp = await hass.services.async_call(
                    "calendar",
                    "get_events",
                    {
                        "entity_id": cal_id,
                        "start_date_time": now_utc.isoformat(),
                        "end_date_time": end_utc.isoformat(),
                    },
                    blocking=True,
                    return_response=True,
                )
                if isinstance(resp, dict):
                    cal_data = resp.get(cal_id) or next(iter(resp.values()), {})
                    events_list = (
                        cal_data.get("events", []) if isinstance(cal_data, dict) else []
                    )
                    for ev in events_list:
                        if isinstance(ev, dict):
                            parsed = _parse_event_dict(ev, cal_id, now_local)
                            if parsed is not None:
                                raw_events.append(parsed)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("calendar.get_events failed for %s: %s", cal_id, err)

    # Fallback: also inspect state attributes of each calendar entity in case get_events is unsupported
    for cal_id in targets:
        st = hass.states.get(cal_id)
        if st and st.attributes.get("message") and st.attributes.get("start_time"):
            parsed = _parse_event_dict(dict(st.attributes), cal_id, now_local)
            if parsed is not None and parsed["start_dt"] >= (now_local - timedelta(hours=12)):
                raw_events.append(parsed)

    raw_events.sort(key=lambda x: x["start_dt"])

    # Deduplicate identical summary + start time across shared family calendars
    seen: set[tuple[str, str]] = set()
    unique_events: list[dict[str, Any]] = []
    for ev in raw_events:
        dedup_key = (ev["summary"].lower(), ev["start_dt"].isoformat())
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        unique_events.append(ev)
        if len(unique_events) >= max_events:
            break

    if not unique_events:
        return "NONE", []

    segments: list[str] = []
    slot_items: list[dict[str, Any]] = []

    for idx, ev in enumerate(unique_events):
        time_label = _format_event_time_label(ev["start_dt"], now_local, ev["all_day"])
        clean_summary = ev["summary"].replace(";", ",").replace("|", "-")
        clean_loc = str(ev.get("location") or "").replace("|", "-").strip()
        map_url = (
            map_url_builder(clean_loc)
            if (clean_loc and callable(map_url_builder))
            else "none"
        )
        segments.append(f"{time_label}|{clean_summary}")

        slot_items.append(
            {
                "name": f"{time_label}: {clean_summary}",
                "id": f"{time_label}|{clean_summary}|{clean_loc}|{map_url}",
                "type": "calendar_event",
                "active": idx == 0,
                "summary": clean_summary,
                "start": ev["start_raw"],
                "end": ev["end_raw"],
                "location": clean_loc,
                "map_url": map_url,
            }
        )

    return ";".join(segments[:5]), slot_items