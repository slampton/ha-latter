"""Family Calendar Agenda Serialization & Event Creation Engine for Latter."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DAY_ABBR: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def _discover_calendars(hass: HomeAssistant, configured: list[str]) -> list[str]:
    """Return configured calendar entity_ids or auto-discover all available calendars."""
    if configured:
        return [c for c in configured if hass.states.get(c) is not None]
    return [
        state_obj.entity_id
        for state_obj in hass.states.async_all("calendar")
        if state_obj.state not in ("unavailable", "unknown")
    ]


def _format_event_time_label(start_dt: datetime, now_local: datetime) -> str:
    """Format a compact time prefix (e.g. '14:30', 'TOM 09:00', 'FRI 18:00')."""
    local_start = dt_util.as_local(start_dt)
    days_ahead = (local_start.date() - now_local.date()).days
    time_str = local_start.strftime("%H:%M")

    if days_ahead <= 0:
        return f"TODAY {time_str}"
    if days_ahead == 1:
        return f"TOM {time_str}"
    day_name = DAY_ABBR[local_start.weekday()]
    return f"{day_name} {time_str}"


async def async_fetch_calendar_agenda(
    hass: HomeAssistant,
    calendar_entities: list[str],
    days: int = 7,
    max_events: int = 10,
) -> tuple[str, list[dict[str, Any]]]:
    """Fetch upcoming events across calendars and return (semicolon_string, slot_items)."""
    targets = _discover_calendars(hass, calendar_entities)
    if not targets or not hass.services.has_service("calendar", "get_events"):
        return "NONE", []

    now_utc = dt_util.utcnow()
    now_local = dt_util.now()
    end_utc = now_utc + timedelta(days=max(1, min(days, 30)))

    try:
        resp = await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": targets,
                "start_date_time": now_utc.isoformat(),
                "end_date_time": end_utc.isoformat(),
            },
            blocking=True,
            return_response=True,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("calendar.get_events failed: %s", err)
        return "NONE", []

    raw_events: list[dict[str, Any]] = []
    if isinstance(resp, dict):
        for cal_id, cal_data in resp.items():
            events_list = (
                cal_data.get("events", []) if isinstance(cal_data, dict) else []
            )
            for ev in events_list:
                if not isinstance(ev, dict):
                    continue
                summary = str(ev.get("summary") or "Event").strip()
                start_raw = ev.get("start")
                end_raw = ev.get("end")
                if not start_raw:
                    continue

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
                    continue

                raw_events.append(
                    {
                        "summary": summary,
                        "start_dt": dt_util.as_local(parsed_start),
                        "start_raw": str(start_raw),
                        "end_raw": str(end_raw or ""),
                        "location": str(ev.get("location") or ""),
                        "calendar_id": cal_id,
                        "all_day": is_all_day,
                    }
                )

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
        time_label = _format_event_time_label(ev["start_dt"], now_local)
        if ev["all_day"]:
            time_label = time_label.split(" ")[0] + " ALL DAY"
        clean_summary = ev["summary"].replace(";", ",").replace("|", "-")
        segments.append(f"{time_label}|{clean_summary}")

        slot_items.append(
            {
                "name": f"{time_label}: {clean_summary}",
                "id": f"{ev['calendar_id']}|{ev['start_raw']}",
                "type": "calendar_event",
                "active": idx == 0,
                "summary": clean_summary,
                "start": ev["start_raw"],
                "end": ev["end_raw"],
                "location": ev["location"],
            }
        )

    return ";".join(segments[:5]), slot_items