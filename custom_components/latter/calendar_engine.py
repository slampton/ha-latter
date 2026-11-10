"""Family Calendar Agenda Serialization & Event Creation Engine for Latter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .payloads import V3Records, calendar_agenda_records

_LOGGER = logging.getLogger(__name__)

MAX_AGENDA_EVENTS = 25


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


def _parse_event_dict(
    ev: dict[str, Any], cal_id: str, now_local: datetime
) -> dict[str, Any] | None:
    """Parse one event from calendar.get_events into a normalized structure."""
    start_raw = ev.get("start")
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
        "summary": str(ev.get("summary") or "Event").strip(),
        "start_dt": dt_util.as_local(parsed_start),
        "start_raw": str(start_raw),
        "end_raw": str(ev.get("end") or ""),
        "location": str(ev.get("location") or "").strip(),
        "calendar_id": cal_id,
        "all_day": is_all_day,
    }


async def async_fetch_raw_calendar_events(
    hass: HomeAssistant,
    calendar_entities: list[str],
    days: int = 30,
    max_events: int = MAX_AGENDA_EVENTS,
) -> tuple[V3Records, list[dict[str, Any]]]:
    """Fetch and deduplicate upcoming events once across calendars for the entire Site."""
    targets = _discover_calendars(hass, calendar_entities)
    if not targets:
        return V3Records(), []

    now_utc = dt_util.utcnow()
    now_local = dt_util.now()
    lookahead_days = max(1, min(int(days or 30), 60))
    end_utc = now_utc + timedelta(days=lookahead_days)

    raw_events: list[dict[str, Any]] = []
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
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("calendar.get_events failed for %s: %s", cal_id, err)
            continue
        cal_data = resp.get(cal_id) if isinstance(resp, dict) else None
        events_list = cal_data.get("events", []) if isinstance(cal_data, dict) else []
        for ev in events_list:
            if isinstance(ev, dict):
                parsed = _parse_event_dict(ev, cal_id, now_local)
                if parsed is not None:
                    raw_events.append(parsed)

    # Deterministic order (the payload rev is a content hash): start, then title, then calendar.
    raw_events.sort(key=lambda x: (x["start_dt"], x["summary"].lower(), x["calendar_id"]))

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

    records = calendar_agenda_records(unique_events, now_local.date())
    raw_rows: list[dict[str, Any]] = []
    for ev in unique_events:
        time_label, title, location, _all_day = calendar_agenda_records([ev], now_local.date())[0]
        raw_rows.append(
            {
                "time_label": time_label,
                "title": title,
                "location": location,
                "start": ev["start_raw"],
                "end": ev["end_raw"],
            }
        )
    return records, raw_rows


def build_calendar_browse_items(
    raw_rows: list[dict[str, Any]],
    map_url_builder: Callable[[str], str] | None = None,
) -> list[dict[str, Any]]:
    """Build device-scoped calendar browse slots (with signed map snapshot URLs) from fetched event rows."""
    slot_items: list[dict[str, Any]] = []
    for idx, row in enumerate(raw_rows):
        time_label = row["time_label"]
        title = row["title"]
        location = row["location"]
        map_url = (
            map_url_builder(location)
            if (location and callable(map_url_builder))
            else ""
        )
        slot_items.append(
            {
                "name": f"{time_label}: {title}",
                "id": f"{time_label}|{title}|{location}|{map_url}",
                "type": "calendar_event",
                "active": idx == 0,
                "summary": title,
                "start": row["start"],
                "end": row["end"],
                "location": location,
                "map_url": map_url,
            }
        )
    return slot_items


async def async_fetch_calendar_agenda(
    hass: HomeAssistant,
    calendar_entities: list[str],
    days: int = 30,
    max_events: int = MAX_AGENDA_EVENTS,
    map_url_builder: Callable[[str], str] | None = None,
) -> tuple[V3Records, list[dict[str, Any]]]:
    """Fetch upcoming events across calendars with calendar.get_events.

    Returns (summary records for the calendar_agenda payload, browse slot items for up to `max_events`).
    """
    records, raw_rows = await async_fetch_raw_calendar_events(
        hass,
        calendar_entities,
        days=days,
        max_events=max_events,
    )
    return records, build_calendar_browse_items(raw_rows, map_url_builder=map_url_builder)
