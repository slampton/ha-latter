"""Diagnostics support for Latter."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import LatterCoordinator

TO_REDACT: set[str] = {
    "alert_camera_url",
    "art_url",
    "ble_beacon_uuid",
    "companion_base_url",
    "companion_url",
    "mac",
    "wallpaper_url",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Latter config entry."""
    coordinator: LatterCoordinator | None = getattr(
        entry, "runtime_data", None
    ) or hass.data.get(DOMAIN, {}).get(entry.entry_id)

    if coordinator is None:
        return {"entry_data": async_redact_data(dict(entry.data), TO_REDACT)}

    media_state, media_attrs = coordinator.get_active_media_payload()
    room_state, room_attrs = coordinator.get_room_context_payload()
    remote_state, remote_attrs = coordinator.get_remote_config_payload()

    payload: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
        "runtime": {
            "device_slug": coordinator.device_slug,
            "device_profile": coordinator.device_profile,
            "display_shape": coordinator.display_shape,
            "default_page_size": coordinator.default_page_size,
            "local_speaker": coordinator.local_speaker,
            "active_speaker": coordinator.active_speaker,
            "last_speaker": coordinator.last_speaker,
            "active_area_id": coordinator.active_area_id,
            "active_remote_slot": coordinator.active_remote_slot,
            "volume_overrides": coordinator.volume_overrides,
        },
        "sensors": {
            "active_media": {"state": media_state, "attributes": media_attrs},
            "room_context": {"state": room_state, "attributes": room_attrs},
            "remote_config": {"state": remote_state, "attributes": remote_attrs},
            "weather_forecast": {
                "state": coordinator.forecast_string,
                "attributes": coordinator.weather_attributes,
            },
            "calendar_agenda": {
                "state": coordinator.calendar_agenda_string,
                "event_count": len(coordinator.calendar_events),
            },
        },
    }

    return async_redact_data(payload, TO_REDACT)