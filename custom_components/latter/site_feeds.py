"""Shared system-level weather forecast and calendar agenda feeds for Latter."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .calendar_engine import async_fetch_calendar_agenda
from .payloads import V3Records, forecast_records, ha_value

_LOGGER = logging.getLogger(__name__)

DAY_ABBR: tuple[str, ...] = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def _opt_float(val: Any) -> float | None:
    """Parse an optional float value rounded to 1 decimal place."""
    if val is None:
        return None
    try:
        return round(float(val), 1)
    except (ValueError, TypeError):
        return None


async def async_fetch_weather_snapshot(
    hass: HomeAssistant,
    weather_entity: str | None,
) -> tuple[V3Records, dict[str, Any]] | None:
    """Fetch the daily forecast with weather.get_forecasts; return (forecast_5d records, weather fields).

    Values the weather entity doesn't report stay None (sent empty, shown as unknown on the device).
    """
    if not weather_entity:
        return None

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
            forecasts = [f for f in resp[weather_entity].get("forecast") or [] if isinstance(f, dict)]

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
    }


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
