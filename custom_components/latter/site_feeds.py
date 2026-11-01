"""Shared system-level weather forecast and calendar agenda feeds for Latter."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .calendar_engine import async_fetch_calendar_agenda

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
) -> tuple[str, dict[str, Any]] | None:
    """Fetch 5-day daily forecast via weather.get_forecasts and return (forecast_string, weather_fields)."""
    if not weather_entity:
        return None

    state_obj = hass.states.get(weather_entity)
    if state_obj is None:
        return None

    attrs = state_obj.attributes
    temp_r = _opt_float(attrs.get("temperature"))
    hum_r = _opt_float(attrs.get("humidity"))
    ws_r = _opt_float(attrs.get("wind_speed"))
    wb_r = _opt_float(attrs.get("wind_bearing"))

    forecasts: list[dict[str, Any]] = []
    if hass.services.has_service("weather", "get_forecasts"):
        try:
            resp = await hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity, "type": "daily"},
                blocking=True,
                return_response=True,
            )
            if isinstance(resp, dict) and weather_entity in resp:
                forecasts = resp[weather_entity].get("forecast") or []
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("weather.get_forecasts failed for %s: %s", weather_entity, err)

    if not forecasts and isinstance(attrs.get("forecast"), list):
        forecasts = attrs.get("forecast")

    hi_r = temp_r
    lo_r = temp_r
    segments: list[str] = []

    for idx, item in enumerate(forecasts[:5]):
        f_high = _opt_float(item.get("temperature"))
        if f_high is None:
            f_high = temp_r
        f_low = _opt_float(item.get("templow"))
        if f_low is None:
            f_low = f_high
        f_cond = str(item.get("condition") or state_obj.state or "sunny")

        if idx == 0:
            if f_high is not None:
                hi_r = f_high
            if f_low is not None:
                lo_r = f_low

        dt_raw = item.get("datetime")
        day_label = "DAY"
        if dt_raw:
            parsed = dt_util.parse_datetime(str(dt_raw))
            if parsed is not None:
                local_dt = dt_util.as_local(parsed)
                day_label = DAY_ABBR[local_dt.weekday()]

        h_int = int(round(f_high)) if f_high is not None else 0
        l_int = int(round(f_low)) if f_low is not None else h_int
        segments.append(f"{day_label}:{h_int}:{l_int}:{f_cond}")

    forecast_str = ";".join(segments) if segments else "NONE"
    return forecast_str, {
        "condition": str(state_obj.state),
        "temperature": temp_r,
        "humidity": hum_r,
        "wind_speed": ws_r,
        "wind_bearing": wb_r,
        "high": hi_r,
        "low": lo_r,
    }


async def async_fetch_calendar_snapshot(
    hass: HomeAssistant,
    calendar_entities: list[str],
    days: int = 30,
    map_url_builder: Callable[[str], str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """Fetch upcoming calendar agenda string and structured event list."""
    return await async_fetch_calendar_agenda(
        hass,
        calendar_entities,
        days=days,
        map_url_builder=map_url_builder,
    )
