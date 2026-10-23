"""Sensor platform for Latter exposing Pocket Assistant v2.1+ / ESPHome entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ENTITY_ACTIVE_MEDIA,
    ENTITY_CALENDAR_AGENDA,
    ENTITY_REMOTE_CONFIG,
    ENTITY_ROOM_CONTEXT,
    ENTITY_WEATHER_FORECAST,
)
from .coordinator import LatterCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Latter sensors from a config entry."""
    coordinator: LatterCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PocketAssistantActiveMediaSensor(coordinator),
            PocketAssistantWeatherForecastSensor(coordinator),
            PocketAssistantRoomContextSensor(coordinator),
            PocketAssistantCalendarAgendaSensor(coordinator),
            PocketAssistantRemoteConfigSensor(coordinator),
        ]
    )


class _BaseLatterSensor(SensorEntity):
    """Base sensor subscribed to LatterCoordinator updates."""

    _attr_should_poll = False

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize base sensor."""
        self.coordinator = coordinator

    @property
    def device_info(self) -> DeviceInfo:
        """Return DeviceInfo with a 1-click 'Visit' link to the Latter Web Companion Studio."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=f"Latter ({self.coordinator.device_slug})",
            manufacturer="Lampton Labs",
            model="Latter ESPHome Companion Middleware",
            sw_version="1.1.0",
            configuration_url=self.coordinator.build_companion_url(),
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write updated state to Home Assistant."""
        self.async_write_ha_state()


class PocketAssistantActiveMediaSensor(_BaseLatterSensor):
    """Exposes sensor.pocket_assistant_active_media with idle-guarded 2s position updates."""

    _attr_name = "Pocket Assistant Active Media"
    _attr_icon = "mdi:music-circle"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize active media sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_active_media"
        self.entity_id = ENTITY_ACTIVE_MEDIA

    @property
    def native_value(self) -> str:
        """Return active speaker playback state."""
        state, _ = self.coordinator.get_active_media_payload()
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return media attributes."""
        _, attrs = self.coordinator.get_active_media_payload()
        return attrs


class PocketAssistantWeatherForecastSensor(_BaseLatterSensor):
    """Exposes sensor.pocket_assistant_weather_forecast with 5-day semicolon string."""

    _attr_name = "Pocket Assistant Weather Forecast"
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize weather forecast sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_weather_forecast"
        self.entity_id = ENTITY_WEATHER_FORECAST

    @property
    def native_value(self) -> str:
        """Return semicolon-delimited 5-day forecast (DAY:HIGH:LOW:COND;...)."""
        return self.coordinator.forecast_string

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return current weather attributes."""
        return self.coordinator.weather_attributes


class PocketAssistantRoomContextSensor(_BaseLatterSensor):
    """Exposes sensor.pocket_assistant_room_context for BLE Area-Aware Room Control, Telemetry & Alarm."""

    _attr_name = "Pocket Assistant Room Context"
    _attr_icon = "mdi:floor-plan"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize room context sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_room_context"
        self.entity_id = ENTITY_ROOM_CONTEXT

    @property
    def native_value(self) -> str:
        """Return active room area name."""
        state, _ = self.coordinator.get_room_context_payload()
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return room entity summary, telemetry, alarm state, and companion_url."""
        _, attrs = self.coordinator.get_room_context_payload()
        return attrs


class PocketAssistantCalendarAgendaSensor(_BaseLatterSensor):
    """Exposes sensor.pocket_assistant_calendar_agenda with upcoming family events."""

    _attr_name = "Pocket Assistant Calendar Agenda"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize calendar agenda sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_calendar_agenda"
        self.entity_id = ENTITY_CALENDAR_AGENDA

    @property
    def native_value(self) -> str:
        """Return semicolon-delimited upcoming agenda string."""
        return self.coordinator.calendar_agenda_string

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return structured upcoming event list."""
        return {
            "event_count": len(self.coordinator.calendar_events),
            "events": self.coordinator.calendar_events,
            "calendars": self.coordinator.calendar_entities,
        }


class PocketAssistantRemoteConfigSensor(_BaseLatterSensor):
    """Exposes sensor.pocket_assistant_remote_config replacing the 4 YAML remote substitutions."""

    _attr_name = "Pocket Assistant Remote Config"
    _attr_icon = "mdi:remote-tv"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize 4-slot remote config sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_remote_config"
        self.entity_id = ENTITY_REMOTE_CONFIG

    @property
    def native_value(self) -> str:
        """Return active remote slot name."""
        state, _ = self.coordinator.get_remote_config_payload()
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return slot_1..4 names, remote_entity, media_player_entity, and states."""
        _, attrs = self.coordinator.get_remote_config_payload()
        return attrs