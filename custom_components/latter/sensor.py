"""Sensor platform for Latter exposing device-scoped (`sensor.<device_slug>_*`) entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, INTEGRATION_VERSION, build_device_entity_id, normalize_device_slug
from .coordinator import LatterCoordinator
from .area_engine import find_esphome_device_id

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Latter sensors from a config entry."""
    coordinator: LatterCoordinator = (
        getattr(entry, "runtime_data", None) or hass.data[DOMAIN][entry.entry_id]
    )
    entities: list[SensorEntity] = []
    if coordinator.device_profile == "ble_beacon":
        entities.extend(
            [
                LatterCurrentAreaSensor(coordinator),
                LatterBleDistanceSensor(coordinator),
                LatterAreaContextSensor(coordinator),
            ]
        )
    else:
        entities.extend(
            [
                LatterCurrentAreaSensor(coordinator),
                LatterBleDistanceSensor(coordinator),
                LatterActiveMediaSensor(coordinator),
                LatterWeatherForecastSensor(coordinator),
                LatterAreaContextSensor(coordinator),
                LatterCalendarAgendaSensor(coordinator),
                LatterRemoteConfigSensor(coordinator),
            ]
        )

    # Automatically purge any legacy _current_room / _room_context entities from HA Entity Registry
    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    for ent_entry in list(er.async_entries_for_config_entry(ent_reg, entry.entry_id)):
        if ent_entry.entity_id.endswith(("_current_room", "_room_context")):
            ent_reg.async_remove(ent_entry.entity_id)

    domain_data = hass.data.setdefault(DOMAIN, {})
    registered_persons: set[str] = domain_data.setdefault("registered_person_sensors", set())

    @callback
    def _async_ensure_person_sensors() -> None:
        person_ent = coordinator.assigned_person
        if person_ent and person_ent.startswith("person.") and person_ent not in registered_persons:
            registered_persons.add(person_ent)
            async_add_entities(
                [
                    LatterPersonCurrentAreaSensor(coordinator, person_ent),
                    LatterPersonBleDistanceSensor(coordinator, person_ent),
                ]
            )

    _async_ensure_person_sensors()
    entry.async_on_unload(
        coordinator.async_add_listener(_async_ensure_person_sensors)
    )
    async_add_entities(entities)


class _BaseLatterSensor(SensorEntity):
    """Base sensor subscribed to LatterCoordinator updates."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _unrecorded_attributes = frozenset(
        {
            "alert_camera_url",
            "art_url",
            "ble_beacon_uuid",
            "ble_area_offsets",
            "ble_rssi_by_area",
            "ble_scanners_map",
            "ble_target_macs",
            "camera_entities",
            "cameras_summary",
            "camera_snapshot_url",
            "companion_url",
            "doorbell_speakers_map",
            "intercom_targets_summary",
            "custom_bindings",
            "custom_bindings_summary",
            "custom_entities",
            "custom_palettes",
            "entities_summary",
            "events",
            "slots_summary",
            "wallpaper_url",
        }
    )

    def __init__(self, coordinator: LatterCoordinator, suffix: str, label: str) -> None:
        """Initialize base sensor with a device-scoped entity_id under its Latter DeviceEntry."""
        self.coordinator = coordinator
        slug = coordinator.device_slug
        self._attr_translation_key = suffix
        self._attr_name = label
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{suffix}"
        self.entity_id = build_device_entity_id(slug, suffix)

    @property
    def device_info(self) -> DeviceInfo:
        """Return canonical Latter DeviceInfo so every config entry has an expandable Device card in Home Assistant."""
        pretty_device = self.coordinator.device_slug.replace("_", " ").title()
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry.entry_id)},
            name=pretty_device,
            manufacturer="Lampton Labs",
            model="Latter ESPHome Companion Middleware",
            sw_version=INTEGRATION_VERSION,
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


class LatterActiveMediaSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_active_media with idle-guarded 2s position updates."""

    _attr_icon = "mdi:music-circle"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize active media sensor."""
        super().__init__(coordinator, "active_media", "Active Media")

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


class LatterWeatherForecastSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_weather_forecast with 5-day semicolon string."""

    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize weather forecast sensor."""
        super().__init__(coordinator, "weather_forecast", "Weather Forecast")

    @property
    def native_value(self) -> str:
        """Return semicolon-delimited 5-day forecast (DAY:HIGH:LOW:COND;...)."""
        return self.coordinator.forecast_string

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return current weather attributes."""
        return self.coordinator.weather_attributes


class LatterAreaContextSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_area_context for Area Control, Telemetry & Alarm."""

    _attr_icon = "mdi:floor-plan"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize area context sensor."""
        super().__init__(coordinator, "area_context", "Area Context")

    @property
    def native_value(self) -> str:
        """Return active area name."""
        state, _ = self.coordinator.get_area_context_payload()
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return area entity summary, telemetry, alarm state, and companion_url."""
        _, attrs = self.coordinator.get_area_context_payload()
        return attrs


class LatterCalendarAgendaSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_calendar_agenda with upcoming family events."""

    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize calendar agenda sensor."""
        super().__init__(coordinator, "calendar_agenda", "Calendar Agenda")

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


class LatterRemoteConfigSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_remote_config replacing hardcoded YAML remote substitutions."""

    _attr_icon = "mdi:remote-tv"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize 4-slot remote config sensor."""
        super().__init__(coordinator, "remote_config", "Remote Config")

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

class LatterCurrentAreaSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_current_area with live area name or 'Away'."""

    _attr_icon = "mdi:map-marker-radius"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize current area sensor."""
        super().__init__(coordinator, "current_area", "Current Area")

    @property
    def native_value(self) -> str:
        """Return active area name or 'Away'."""
        state, _ = self.coordinator.get_current_area_and_distance()
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return BLE distance, closest proxy, and person assignment."""
        _, attrs = self.coordinator.get_current_area_and_distance()
        return attrs


class LatterBleDistanceSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_ble_distance with estimated distance (ft) to the winning area proxy."""

    _attr_icon = "mdi:map-marker-distance"
    _attr_native_unit_of_measurement = "ft"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize BLE distance sensor."""
        super().__init__(coordinator, "ble_distance", "BLE Distance")

    @property
    def native_value(self) -> float | None:
        """Return estimated distance in feet to the closest area proxy."""
        _, attrs = self.coordinator.get_current_area_and_distance()
        return attrs.get("distance_ft")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return distance in meters, RSSI, and closest proxy."""
        _, attrs = self.coordinator.get_current_area_and_distance()
        return attrs


class LatterPersonCurrentAreaSensor(_BaseLatterSensor):
    """Exposes sensor.<person_slug>_current_area as a native Entity Registry sensor."""

    def __init__(self, coordinator: LatterCoordinator, person_entity: str) -> None:
        """Initialize person current area sensor."""
        self._person_entity = person_entity
        p_slug = normalize_device_slug(person_entity.split(".", 1)[-1])
        p_st = coordinator.hass.states.get(person_entity)
        p_friendly = (
            str(p_st.attributes.get("friendly_name") or "").strip()
            if p_st
            else ""
        ) or p_slug.replace("_", " ").title()
        super().__init__(coordinator, f"person_{p_slug}_current_area", f"{p_friendly} Current Area")
        self._attr_has_entity_name = False
        self._attr_unique_id = f"{DOMAIN}_person_{p_slug}_current_area"
        self.entity_id = f"sensor.{p_slug}_current_area"

    @property
    def icon(self) -> str:
        """Return dynamic icon based on area state."""
        return "mdi:account-location" if self.native_value not in ("Away", "Unassigned") else "mdi:account-arrow-right"

    @property
    def native_value(self) -> str:
        """Return freshest area name across all devices carried by this person."""
        area_name, _ = self.coordinator.get_person_area_and_distance(self._person_entity)
        return area_name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return person BLE area tracking attributes."""
        _, attrs = self.coordinator.get_person_area_and_distance(self._person_entity)
        return attrs


class LatterPersonBleDistanceSensor(_BaseLatterSensor):
    """Exposes sensor.<person_slug>_ble_distance as a native Entity Registry sensor."""

    _attr_icon = "mdi:map-marker-distance"
    _attr_native_unit_of_measurement = "ft"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: LatterCoordinator, person_entity: str) -> None:
        """Initialize person BLE distance sensor."""
        self._person_entity = person_entity
        p_slug = normalize_device_slug(person_entity.split(".", 1)[-1])
        p_st = coordinator.hass.states.get(person_entity)
        p_friendly = (
            str(p_st.attributes.get("friendly_name") or "").strip()
            if p_st
            else ""
        ) or p_slug.replace("_", " ").title()
        super().__init__(coordinator, f"person_{p_slug}_ble_distance", f"{p_friendly} BLE Distance")
        self._attr_has_entity_name = False
        self._attr_unique_id = f"{DOMAIN}_person_{p_slug}_ble_distance"
        self.entity_id = f"sensor.{p_slug}_ble_distance"

    @property
    def native_value(self) -> float | None:
        """Return estimated distance in feet for this person."""
        _, attrs = self.coordinator.get_person_area_and_distance(self._person_entity)
        return attrs.get("distance_ft")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return person BLE distance attributes."""
        _, attrs = self.coordinator.get_person_area_and_distance(self._person_entity)
        return attrs
