"""Site-level Calendar Agenda, Weather Forecast, and Sun/Moon Sky Telemetry Feeds."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .protocol import (
    V3Records,
    calendar_agenda_records,
    forecast_records,
    ha_value,
)

_LOGGER = logging.getLogger(__name__)

MAX_AGENDA_EVENTS = 25
DAY_ABBR: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
MOON_PHASES: tuple[str, ...] = (
    "new_moon",
    "waxing_crescent",
    "first_quarter",
    "waxing_gibbous",
    "full_moon",
    "waning_gibbous",
    "last_quarter",
    "waning_crescent",
)
_REF_NEW_MOON_UTC_S: float = 947182440.0  # 2000-01-06 18:14:00 UTC
_SYNODIC_MONTH_S: float = 29.53058867 * 86400.0


def _opt_float(val: Any) -> float | None:
    """Parse an optional float value rounded to 1 decimal place."""
    if val is None:
        return None
    try:
        return round(float(val), 1)
    except (ValueError, TypeError):
        return None


def compute_moon_phase(utc_timestamp_s: float) -> str:
    """Compute the canonical 8-bucket Home Assistant moon phase for `utc_timestamp_s`."""
    frac = ((float(utc_timestamp_s) - _REF_NEW_MOON_UTC_S) / _SYNODIC_MONTH_S) % 1.0
    idx = int((frac * 8.0) + 0.5) % 8
    return MOON_PHASES[idx]


def read_sun_and_moon_fields(hass: HomeAssistant) -> dict[str, Any]:
    """Read `sun.sun` and `sensor.moon_phase` (falling back to astronomical computation)."""
    sun_obj = hass.states.get("sun.sun")
    sun_attrs = sun_obj.attributes if sun_obj is not None else {}

    moon_val = ""
    for moon_ent in ("sensor.moon_phase", "sensor.moon"):
        st = hass.states.get(moon_ent)
        if st is not None:
            cand = ha_value(st.state)
            if cand in MOON_PHASES:
                moon_val = cand
                break
    if not moon_val:
        moon_val = compute_moon_phase(dt_util.utcnow().timestamp())

    return {
        "sun_state": ha_value(sun_obj.state) if sun_obj is not None else "",
        "sun_elevation": _opt_float(sun_attrs.get("elevation")),
        "sun_azimuth": _opt_float(sun_attrs.get("azimuth")),
        "sun_next_rising": ha_value(sun_attrs.get("next_rising")),
        "sun_next_setting": ha_value(sun_attrs.get("next_setting")),
        "moon_phase": moon_val,
    }


def _discover_calendars(hass: HomeAssistant, configured: list[str]) -> list[str]:
    """Return configured calendar entity_ids or auto-discover indexed calendars."""
    from .hub import get_area_state_index

    if configured:
        valid = [c for c in configured if hass.states.get(c) is not None]
        if valid:
            return valid
    return [
        state_obj.entity_id
        for state_obj in get_area_state_index(hass).states_for_domain("calendar")
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

    raw_events.sort(key=lambda x: (x["start_dt"], x["summary"].lower(), x["calendar_id"]))

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
        time_label, title, location, _all_day = calendar_agenda_records(
            [ev], now_local.date()
        )[0]
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
    """Fetch upcoming events across calendars with calendar.get_events."""
    records, raw_rows = await async_fetch_raw_calendar_events(
        hass,
        calendar_entities,
        days=days,
        max_events=max_events,
    )
    return records, build_calendar_browse_items(raw_rows, map_url_builder=map_url_builder)


async def async_fetch_calendar_snapshot(
    hass: HomeAssistant,
    calendar_entities: list[str],
    days: int = 30,
    map_url_builder: Callable[[str], str] | None = None,
) -> tuple[V3Records, list[dict[str, Any]]]:
    """Fetch the calendar agenda records (Protocol v3) and the structured event list."""
    return await async_fetch_calendar_agenda(
        hass,
        calendar_entities,
        days=days,
        map_url_builder=map_url_builder,
    )


async def async_fetch_weather_snapshot(
    hass: HomeAssistant,
    weather_entity: str | None,
) -> tuple[V3Records, dict[str, Any]] | None:
    """Fetch the daily forecast with weather.get_forecasts; return (forecast_5d records, weather + sky fields)."""
    sky = read_sun_and_moon_fields(hass)
    if not weather_entity:
        return V3Records(), {
            "condition": "",
            "temperature": None,
            "humidity": None,
            "wind_speed": None,
            "wind_bearing": None,
            "high": None,
            "low": None,
            **sky,
        }

    state_obj = hass.states.get(weather_entity)
    if state_obj is None:
        return None

    attrs = state_obj.attributes
    forecasts: list[dict[str, Any]] = []
    try:
        resp = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"entity_id": weather_entity, "type": "daily"},
            blocking=True,
            return_response=True,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("weather.get_forecasts failed for %s: %s", weather_entity, err)
    else:
        if isinstance(resp, dict) and isinstance(resp.get(weather_entity), dict):
            forecasts = [
                f
                for f in resp[weather_entity].get("forecast") or []
                if isinstance(f, dict)
            ]

    days: list[dict[str, Any]] = []
    for item in forecasts:
        parsed = dt_util.parse_datetime(str(item.get("datetime") or ""))
        if parsed is None:
            continue
        days.append(
            {
                "day": DAY_ABBR[dt_util.as_local(parsed).weekday()],
                "condition": str(item.get("condition") or ""),
                "high": _opt_float(item.get("temperature")),
                "low": _opt_float(item.get("templow")),
            }
        )

    today = days[0] if days else {}
    return forecast_records(days), {
        "condition": ha_value(state_obj.state),
        "temperature": _opt_float(attrs.get("temperature")),
        "humidity": _opt_float(attrs.get("humidity")),
        "wind_speed": _opt_float(attrs.get("wind_speed")),
        "wind_bearing": _opt_float(attrs.get("wind_bearing")),
        "high": today.get("high"),
        "low": today.get("low"),
        **sky,
    }


def init_weather_attributes(
    pack_fn: Callable[..., tuple[int, str]],
) -> dict[str, Any]:
    """Build initial unknown weather_attributes dictionary for a fresh coordinator."""
    w_rev, w_payload = pack_fn(
        "weather_forecast",
        "",
        None,
        None,
        None,
        None,
        None,
        None,
        V3Records(),
        "",
        None,
        None,
        "",
        "",
        "",
    )
    return {
        "condition": "",
        "temperature": None,
        "humidity": None,
        "wind_speed": None,
        "wind_bearing": None,
        "high": None,
        "low": None,
        "sun_state": "",
        "sun_elevation": None,
        "sun_azimuth": None,
        "sun_next_rising": "",
        "sun_next_setting": "",
        "moon_phase": "",
        "rev": w_rev,
        "payload": w_payload,
    }


@callback
def apply_coordinator_calendar_snapshot(
    coordinator: Any, records: V3Records, raw_rows: list[dict[str, Any]]
) -> None:
    """Apply a Site-level calendar agenda snapshot and build device-scoped map snapshot URLs."""
    coordinator.calendar_records = records
    coordinator.calendar_events = build_calendar_browse_items(
        raw_rows, map_url_builder=coordinator.build_map_snapshot_url
    )
    coordinator.async_notify_listeners()


async def async_refresh_coordinator_calendar(
    coordinator: Any, days: int = 30
) -> None:
    """Fetch upcoming calendar events (via shared Site feed for 30-day agendas) and update state."""
    from .hub import get_latter_system

    sys_obj = get_latter_system(coordinator.hass)
    if sys_obj is not None and days == 30:
        records, raw_rows = await sys_obj.async_refresh_calendar_agenda(days=30)
        if coordinator.subentry_id not in sys_obj.coordinators:
            apply_coordinator_calendar_snapshot(coordinator, records, raw_rows)
        return
    records, events = await async_fetch_calendar_snapshot(
        coordinator.hass,
        coordinator.calendar_entities,
        days=days,
        map_url_builder=coordinator.build_map_snapshot_url,
    )
    coordinator.calendar_records = records
    coordinator.calendar_events = events
    coordinator.async_notify_listeners()


def build_calendar_agenda_payload(coordinator: Any) -> tuple[int, dict[str, Any]]:
    """Return upcoming event count and Protocol v3 `calendar_agenda` payload."""
    count = len(coordinator.calendar_events)
    next_event = (
        str(coordinator.calendar_events[0].get("name") or "")
        if coordinator.calendar_events
        else ""
    )
    cal_rev, cal_payload = coordinator._pack_domain_payload(
        "calendar_agenda",
        coordinator.calendar_records,
        count,
        next_event,
    )
    return count, {
        "event_count": count,
        "next_event": next_event,
        "events": coordinator.calendar_events,
        "calendars": coordinator.calendar_entities,
        "rev": cal_rev,
        "payload": cal_payload,
    }


@callback
def apply_coordinator_weather_snapshot(
    coordinator: Any,
    weather_ent: str | None,
    snap: tuple[V3Records, dict[str, Any]] | None,
) -> None:
    """Apply a Site-level weather forecast snapshot and pack `weather_forecast`."""
    if not weather_ent:
        sky = snap[1] if snap is not None and isinstance(snap[1], dict) else {}
        sun_state = str(sky.get("sun_state") or "")
        sun_elev = sky.get("sun_elevation")
        sun_azim = sky.get("sun_azimuth")
        sun_rise = str(sky.get("sun_next_rising") or "")
        sun_set = str(sky.get("sun_next_setting") or "")
        moon_ph = str(sky.get("moon_phase") or "")
        coordinator.forecast_records = V3Records()
        w_rev, w_payload = coordinator._pack_domain_payload(
            "weather_forecast",
            "",
            None,
            None,
            None,
            None,
            None,
            None,
            coordinator.forecast_records,
            sun_state,
            sun_elev,
            sun_azim,
            sun_rise,
            sun_set,
            moon_ph,
        )
        coordinator.weather_attributes = {
            "condition": "",
            "temperature": None,
            "humidity": None,
            "wind_speed": None,
            "wind_bearing": None,
            "high": None,
            "low": None,
            "sun_state": sun_state,
            "sun_elevation": sun_elev,
            "sun_azimuth": sun_azim,
            "sun_next_rising": sun_rise,
            "sun_next_setting": sun_set,
            "moon_phase": moon_ph,
            "weather_entity": "",
            "rev": w_rev,
            "payload": w_payload,
        }
        coordinator.async_notify_listeners()
        return
    if snap is None:
        return
    records, w_fields = snap
    coordinator.forecast_records = records
    w_rev, w_payload = coordinator._pack_domain_payload(
        "weather_forecast",
        w_fields["condition"],
        w_fields["temperature"],
        w_fields["humidity"],
        w_fields["wind_speed"],
        w_fields["wind_bearing"],
        w_fields["high"],
        w_fields["low"],
        coordinator.forecast_records,
        w_fields.get("sun_state", ""),
        w_fields.get("sun_elevation"),
        w_fields.get("sun_azimuth"),
        w_fields.get("sun_next_rising", ""),
        w_fields.get("sun_next_setting", ""),
        w_fields.get("moon_phase", ""),
    )
    coordinator.weather_attributes = {
        **w_fields,
        "weather_entity": weather_ent,
        "rev": w_rev,
        "payload": w_payload,
    }
    coordinator.async_notify_listeners()


async def async_refresh_coordinator_weather(coordinator: Any) -> None:
    """Fetch the daily forecast (via shared Site feed) and pack `weather_forecast`."""
    from .hub import get_latter_system

    sys_obj = get_latter_system(coordinator.hass)
    if sys_obj is not None:
        await sys_obj.async_refresh_weather_forecast()
        if coordinator.subentry_id not in sys_obj.coordinators:
            apply_coordinator_weather_snapshot(
                coordinator, sys_obj.weather_entity, sys_obj.weather_snapshot
            )
        return
    weather_ent = coordinator.weather_entity
    if not weather_ent:
        apply_coordinator_weather_snapshot(coordinator, None, None)
        return
    snap = await async_fetch_weather_snapshot(coordinator.hass, weather_ent)
    apply_coordinator_weather_snapshot(coordinator, weather_ent, snap)
