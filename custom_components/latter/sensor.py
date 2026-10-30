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
from homeassistant.helpers import area_registry as ar, device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .ble_engine import get_ble_fabric, get_ble_proxy_area_ids
from .const import DOMAIN, INTEGRATION_VERSION, build_device_entity_id, normalize_device_slug
from .coordinator import LatterCoordinator
from .area_engine import find_esphome_device_id

PARALLEL_UPDATES = 0
DATA_CREATED_AREA_OCCUPANT_IDS = "created_area_occupant_ids"


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

    domain_data = hass.data.setdefault(DOMAIN, {})
    registered_persons: set[str] = domain_data.setdefault("registered_person_sensors", set())
    created_area_occupants: set[str] = domain_data.setdefault(DATA_CREATED_AREA_OCCUPANT_IDS, set())

    area_reg = ar.async_get(hass)
    proxy_areas = get_ble_proxy_area_ids(hass)
    candidate_areas = proxy_areas or {a.id for a in area_reg.async_list_areas()}
    for area_id in sorted(candidate_areas):
        if area_id in created_area_occupants:
            continue
        area_entry = area_reg.async_get_area(area_id)
        if area_entry is None:
            continue
        created_area_occupants.add(area_id)
        entities.append(
            LatterAreaOccupantsSensor(hass, coordinator, area_entry.id, area_entry.name)
        )

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


class LatterAreaOccupantsSensor(SensorEntity):
    """Exposes sensor.<area_slug>_occupants with live occupant names and Bayesian sensor fusion telemetry."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: LatterCoordinator,
        area_id: str,
        area_name: str,
    ) -> None:
        """Initialize the per-area occupants sensor."""
        self.hass = hass
        self.coordinator = coordinator
        self._area_id = area_id
        self._area_name = area_name
        a_slug = normalize_device_slug(area_id or area_name)
        self._attr_name = f"{area_name} Occupants"
        self._attr_unique_id = f"latter_area_occupants_{area_id}"
        self._attr_suggested_area = area_name
        self.entity_id = f"sensor.{a_slug}_occupants"

    @property
    def device_info(self) -> DeviceInfo:
        """Return canonical Latter DeviceInfo."""
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
        """Subscribe to real-time updates from the shared Latter BLE Fabric."""
        await super().async_added_to_hass()
        fabric = get_ble_fabric(self.hass)
        self.async_on_remove(
            fabric.register_occupancy_listener(self._handle_occupancy_update)
        )

    @callback
    def _handle_occupancy_update(self) -> None:
        """Push updated occupant state to Home Assistant."""
        self.async_write_ha_state()

    @property
    def icon(self) -> str:
        """Return dynamic icon based on area occupancy."""
        return "mdi:account-group" if self.native_value != "Empty" else "mdi:account-off-outline"

    @property
    def native_value(self) -> str:
        """Return comma-separated occupant names, 'Occupied (Sensor)', or 'Empty'."""
        occ = get_ble_fabric(self.hass).get_area_occupancy(self._area_id)
        names = occ.get("occupant_names") or []
        if names:
            return ", ".join(names)
        if occ.get("is_occupied"):
            return "Occupied (Sensor)"
        return "Empty"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed occupant list, sensor fusion status, and signal attributes."""
        occ = get_ble_fabric(self.hass).get_area_occupancy(self._area_id)
        return {
            "area_id": self._area_id,
            "area_name": self._area_name,
            "floor_id": occ.get("floor_id"),
            "is_occupied": occ.get("is_occupied", False),
            "occupant_count": len(occ.get("occupant_names") or []),
            "occupant_names": occ.get("occupant_names", []),
            "persons": occ.get("persons", []),
            "occupied_by": occ.get("occupied_by", []),
            "fusion_mode": occ.get("fusion_mode", "auto_bayes"),
            "confidence_pct": occ.get("confidence_pct", 0),
            "ble_occupied": occ.get("ble_occupied", False),
            "sensor_occupied": occ.get("sensor_occupied", False),
            "active_sensors": occ.get("active_sensors", []),
            "closest_device": occ.get("closest_device"),
            "winning_rssi": occ.get("winning_rssi"),
            "closest_distance_m": occ.get("closest_distance_m"),
            "closest_distance_ft": occ.get("closest_distance_ft"),
        }
