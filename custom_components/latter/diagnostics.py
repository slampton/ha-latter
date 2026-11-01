"""Diagnostics support for Latter."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .coordinator import LatterCoordinator, resolve_coordinator
from .system import LatterSystem, get_latter_system

TO_REDACT: set[str] = {
    "alert_camera_url",
    "art_url",
    "ble_beacon_uuid",
    "ble_target_address",
    "companion_base_url",
    "companion_url",
    "hmac_secret_hex",
    "mac",
    "vpn_client_ip",
    "vpn_endpoint",
    "vpn_preshared_key",
    "vpn_private_key",
    "vpn_public_key",
    "wallpaper_url",
}


def _build_coordinator_diagnostics(coordinator: LatterCoordinator) -> dict[str, Any]:
    """Build diagnostic snapshot for a single LatterCoordinator."""
    media_state, media_attrs = coordinator.get_active_media_payload()
    area_state, area_attrs = coordinator.get_area_context_payload()
    remote_state, remote_attrs = coordinator.get_remote_config_payload()
    return {
        "subentry_id": coordinator.subentry_id,
        "title": coordinator.device_title,
        "device_data": coordinator.device_data,
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
            "last_area_follow_write": coordinator.last_area_follow_write,
        },
        "sensors": {
            "active_media": {"state": media_state, "attributes": media_attrs},
            "area_context": {"state": area_state, "attributes": area_attrs},
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


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the Latter System hub entry and all its device subentries."""
    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, LatterCoordinator):
        return async_redact_data(_build_coordinator_diagnostics(runtime), TO_REDACT)

    sys_obj = runtime if isinstance(runtime, LatterSystem) else get_latter_system(hass)
    if sys_obj is None:
        return {"entry_data": async_redact_data(dict(entry.data), TO_REDACT)}

    payload: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "data": dict(entry.data),
            "options": dict(entry.options),
            "subentry_count": len(entry.subentries),
        },
        "system_config": dict(sys_obj.config),
        "devices": {
            sub_id: _build_coordinator_diagnostics(coord)
            for sub_id, coord in sys_obj.coordinators.items()
        },
    }
    return async_redact_data(payload, TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for an individual Latter device or the Latter System service device."""
    coord = resolve_coordinator(hass, device.id)
    if coord is not None:
        return async_redact_data(_build_coordinator_diagnostics(coord), TO_REDACT)
    return await async_get_config_entry_diagnostics(hass, entry)
