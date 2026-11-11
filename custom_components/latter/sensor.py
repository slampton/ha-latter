"""Sensor platform for Latter exposing device-scoped (`sensor.<device_slug>_*`) and System-scoped entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, build_device_entity_id, normalize_device_slug
from .core.device_coordinator import (
    LatterCoordinator,
    resolve_person_area_and_distance,
)
from .core.hub import LatterSystem, get_latter_system, get_system_device_info
from .presence.ble_fabric import get_ble_fabric, get_ble_proxy_area_ids

PARALLEL_UPDATES = 0
DATA_CREATED_AREA_OCCUPANT_IDS = "created_area_occupant_ids"
MAX_OCCUPANTS_STATE_CHARS = 250


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Latter sensors for all device subentries and System-level Area/Person entities."""
    runtime = entry.runtime_data
    if isinstance(runtime, LatterSystem):
        coordinators = list(runtime.coordinators.values())
    elif isinstance(runtime, LatterCoordinator):
        coordinators = [runtime]
    else:
        sys_obj = get_latter_system(hass)
        coordinators = list(sys_obj.coordinators.values()) if sys_obj else []

    for coordinator in coordinators:
        dev_entities: list[SensorEntity] = []
        if coordinator.is_ble_tag:
            dev_entities.extend(
                [
                    LatterCurrentAreaSensor(coordinator),
                    LatterBleDistanceSensor(coordinator),
                ]
            )
        else:
            dev_entities.extend(
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
        async_add_entities(dev_entities, config_subentry_id=coordinator.subentry_id)

    domain_data = hass.data.setdefault(DOMAIN, {})
    registered_persons: set[str] = domain_data.setdefault(
        "registered_person_sensors", set()
    )
    created_area_occupants: set[str] = domain_data.setdefault(
        DATA_CREATED_AREA_OCCUPANT_IDS, set()
    )
    entry_area_ids: set[str] = set()
    entry_persons: set[str] = set()
    area_entities_by_id: dict[str, LatterAreaOccupantsSensor] = {}
    system_entities: list[SensorEntity] = []

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
        entry_area_ids.add(area_id)
        ent = LatterAreaOccupantsSensor(hass, area_entry.id, area_entry.name)
        area_entities_by_id[area_id] = ent
        system_entities.append(ent)

    @callback
    def _async_on_area_registry_updated(event: Event) -> None:
        action = event.data.get("action")
        area_id = str(event.data.get("area_id") or "").strip()
        if not area_id:
            return
        if action == "create":
            if area_id in created_area_occupants:
                return
            area_entry = ar.async_get(hass).async_get_area(area_id)
            if area_entry is None:
                return
            created_area_occupants.add(area_id)
            entry_area_ids.add(area_id)
            ent = LatterAreaOccupantsSensor(hass, area_entry.id, area_entry.name)
            area_entities_by_id[area_id] = ent
            async_add_entities([ent])
        elif action == "update":
            ent = area_entities_by_id.get(area_id)
            area_entry = ar.async_get(hass).async_get_area(area_id)
            if ent is not None and area_entry is not None:
                ent.update_area_metadata(area_entry.name)
        elif action == "remove":
            created_area_occupants.discard(area_id)
            entry_area_ids.discard(area_id)
            ent = area_entities_by_id.pop(area_id, None)
            if ent is not None:
                ent_reg = er.async_get(hass)
                if ent_reg.async_get(ent.entity_id) is not None:
                    ent_reg.async_remove(ent.entity_id)
                if ent.hass is not None:
                    hass.async_create_task(ent.async_remove())

    @callback
    def _async_ensure_person_sensors() -> None:
        new_person_entities: list[SensorEntity] = []
        for coord in coordinators:
            person_ent = coord.assigned_person
            if (
                person_ent
                and person_ent.startswith("person.")
                and person_ent not in registered_persons
            ):
                registered_persons.add(person_ent)
                entry_persons.add(person_ent)
                new_person_entities.extend(
                    [
                        LatterPersonCurrentAreaSensor(hass, person_ent),
                        LatterPersonBleDistanceSensor(hass, person_ent),
                    ]
                )
        if new_person_entities:
            async_add_entities(new_person_entities)

    @callback
    def _cleanup_entry_tracked_ids() -> None:
        created_area_occupants.difference_update(entry_area_ids)
        registered_persons.difference_update(entry_persons)
        area_entities_by_id.clear()

    if system_entities:
        async_add_entities(system_entities)

    _async_ensure_person_sensors()
    entry.async_on_unload(_cleanup_entry_tracked_ids)
    entry.async_on_unload(
        hass.bus.async_listen(
            ar.EVENT_AREA_REGISTRY_UPDATED, _async_on_area_registry_updated
        )
    )
    for coordinator in coordinators:
        entry.async_on_unload(
            coordinator.async_add_listener(_async_ensure_person_sensors)
        )


class _BaseLatterSensor(SensorEntity):
    """Base sensor subscribed to LatterCoordinator updates."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _unrecorded_attributes = frozenset({"rev"})

    def __init__(self, coordinator: LatterCoordinator, suffix: str) -> None:
        """Initialize base sensor with a device-scoped entity_id under its Latter DeviceEntry."""
        self.coordinator = coordinator
        slug = coordinator.device_slug
        self._attr_translation_key = suffix
        self._attr_unique_id = f"{coordinator.subentry_id}_{suffix}"
        self.entity_id = build_device_entity_id(slug, suffix)

    @property
    def device_info(self) -> DeviceInfo:
        """Return canonical Latter DeviceInfo."""
        return self.coordinator.get_device_info()

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
    """Exposes sensor.<device_slug>_active_media."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_visible_default = False

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize active media sensor."""
        super().__init__(coordinator, "active_media")

    @property
    def native_value(self) -> str | None:
        """Return active speaker playback state."""
        state, _ = self.coordinator.get_active_media_payload()
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return Protocol v3 active_media revision."""
        _, attrs = self.coordinator.get_active_media_payload()
        return {"rev": attrs.get("rev", 0)}


class LatterWeatherForecastSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_weather_forecast."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_visible_default = False

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize weather forecast sensor."""
        super().__init__(coordinator, "weather_forecast")

    @property
    def native_value(self) -> str | None:
        """Return the weather entity's current condition."""
        cond = self.coordinator.weather_attributes.get("condition")
        return str(cond) if cond else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return Protocol v3 weather_forecast revision."""
        attrs = self.coordinator.weather_attributes
        return {"rev": attrs.get("rev", 0)}


class LatterAreaContextSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_area_context."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_visible_default = False

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize area context sensor."""
        super().__init__(coordinator, "area_context")

    @property
    def native_value(self) -> str:
        """Return active area name."""
        state, _ = self.coordinator.get_area_context_payload()
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return Protocol v3 area_context revision."""
        _, attrs = self.coordinator.get_area_context_payload()
        return {"rev": attrs.get("rev", 0)}


class LatterCalendarAgendaSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_calendar_agenda."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_visible_default = False

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize calendar agenda sensor."""
        super().__init__(coordinator, "calendar_agenda")

    @property
    def native_value(self) -> int:
        """Return the number of upcoming agenda events."""
        count, _ = self.coordinator.get_calendar_agenda_payload()
        return count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return Protocol v3 calendar_agenda revision."""
        _, attrs = self.coordinator.get_calendar_agenda_payload()
        return {"rev": attrs.get("rev", 0)}


class LatterRemoteConfigSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_remote_config."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_visible_default = False

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize 4-slot remote config sensor."""
        super().__init__(coordinator, "remote_config")

    @property
    def native_value(self) -> str | None:
        """Return active remote slot name."""
        state, _ = self.coordinator.get_remote_config_payload()
        return state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return Protocol v3 remote_config revision."""
        _, attrs = self.coordinator.get_remote_config_payload()
        return {"rev": attrs.get("rev", 0)}


class LatterCurrentAreaSensor(_BaseLatterSensor):
    """Exposes sensor.<device_slug>_current_area with live area name or 'Away'."""

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize current area sensor."""
        super().__init__(coordinator, "current_area")

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
    """Exposes sensor.<device_slug>_ble_distance with estimated distance (ft)."""

    _attr_native_unit_of_measurement = "ft"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize BLE distance sensor."""
        super().__init__(coordinator, "ble_distance")

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


class _BaseLatterPersonSensor(SensorEntity):
    """Base sensor for a person's fused BLE area and distance across all devices assigned to them."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, person_entity: str) -> None:
        """Initialize the person sensor under the Latter System service device."""
        self.hass = hass
        self._person_entity = person_entity
        self._person_slug = normalize_device_slug(person_entity.split(".", 1)[-1])
        p_st = hass.states.get(person_entity)
        self._person_friendly = (
            str(p_st.attributes.get("friendly_name") or "").strip()
            if p_st
            else ""
        ) or self._person_slug.replace("_", " ").title()
        self._attr_translation_placeholders = {"person_name": self._person_friendly}
        self._cached_person: tuple[str, dict[str, Any]] | None = None

    def _get_person_state(self) -> tuple[str, dict[str, Any]]:
        """Return cached or freshly evaluated person area and distance snapshot."""
        if self._cached_person is None:
            self._cached_person = resolve_person_area_and_distance(self.hass, self._person_entity)
        return self._cached_person

    @property
    def device_info(self) -> DeviceInfo:
        """Attach person sensors to the System-level Latter service device."""
        return get_system_device_info()

    async def async_added_to_hass(self) -> None:
        """Subscribe to real-time updates from the shared BLE Fabric and all device coordinators."""
        await super().async_added_to_hass()
        fabric = get_ble_fabric(self.hass)
        self._cached_person = resolve_person_area_and_distance(self.hass, self._person_entity)
        self.async_on_remove(
            fabric.register_occupancy_listener(self._handle_person_update)
        )
        sys_obj = get_latter_system(self.hass)
        coords = (
            list(sys_obj.coordinators.values())
            if sys_obj and sys_obj.coordinators
            else [
                v
                for v in self.hass.data.get(DOMAIN, {}).values()
                if isinstance(v, LatterCoordinator)
            ]
        )
        for coord in coords:
            self.async_on_remove(
                coord.async_add_listener(self._handle_person_update)
            )

    @callback
    def _handle_person_update(self) -> None:
        """Write updated person location/distance state to Home Assistant."""
        self._cached_person = resolve_person_area_and_distance(self.hass, self._person_entity)
        self.async_write_ha_state()


class LatterPersonCurrentAreaSensor(_BaseLatterPersonSensor):
    """Exposes sensor.<person_slug>_current_area under the Latter System service device."""

    _attr_translation_key = "person_current_area"

    def __init__(self, hass: HomeAssistant, person_entity: str) -> None:
        """Initialize person current area sensor."""
        super().__init__(hass, person_entity)
        self._attr_unique_id = f"{DOMAIN}_person_{self._person_slug}_current_area"
        self.entity_id = f"sensor.{self._person_slug}_current_area"

    @property
    def icon(self) -> str:
        """Return dynamic icon based on area state."""
        return (
            "mdi:account-location"
            if self.native_value not in ("Away", "Unassigned")
            else "mdi:account-arrow-right"
        )

    @property
    def native_value(self) -> str:
        """Return freshest area name across all devices carried by this person."""
        area_name, _ = self._get_person_state()
        return area_name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return person BLE area tracking attributes."""
        _, attrs = self._get_person_state()
        return attrs


class LatterPersonBleDistanceSensor(_BaseLatterPersonSensor):
    """Exposes sensor.<person_slug>_ble_distance under the Latter System service device."""

    _attr_translation_key = "person_ble_distance"
    _attr_icon = "mdi:map-marker-distance"
    _attr_native_unit_of_measurement = "ft"
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, person_entity: str) -> None:
        """Initialize person BLE distance sensor."""
        super().__init__(hass, person_entity)
        self._attr_unique_id = f"{DOMAIN}_person_{self._person_slug}_ble_distance"
        self.entity_id = f"sensor.{self._person_slug}_ble_distance"

    @property
    def native_value(self) -> float | None:
        """Return estimated distance in feet for this person."""
        _, attrs = self._get_person_state()
        return attrs.get("distance_ft")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return person BLE distance attributes."""
        _, attrs = self._get_person_state()
        return attrs


def format_bounded_occupant_names(
    names: list[str], max_chars: int = MAX_OCCUPANTS_STATE_CHARS
) -> str:
    """Format occupant names cleanly under HA's 255-character state limit."""
    clean = [str(n).strip() for n in names if str(n).strip()]
    if not clean:
        return ""
    joined = ", ".join(clean)
    if len(joined) <= max_chars:
        return joined

    included: list[str] = []
    for idx, name in enumerate(clean):
        remaining = len(clean) - idx
        suffix = f" (+{remaining})"
        candidate_list = [*included, name]
        next_remaining = remaining - 1
        next_suffix = f" (+{next_remaining})" if next_remaining > 0 else ""
        candidate = ", ".join(candidate_list) + next_suffix
        if len(candidate) <= max_chars:
            included.append(name)
        else:
            if not included:
                return f"{name[: max_chars - len(suffix) - 1]}…{suffix}"
            return f"{', '.join(included)} (+{remaining})"
    return ", ".join(included)[:max_chars]


class LatterAreaOccupantsSensor(SensorEntity):
    """Exposes sensor.<area_slug>_occupants with bounded state (<255 chars) and full `occupant_names` attribute."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "area_occupants"

    def __init__(
        self,
        hass: HomeAssistant,
        area_id: str,
        area_name: str,
    ) -> None:
        """Initialize the per-area occupants sensor."""
        self.hass = hass
        self._area_id = area_id
        self._area_name = area_name
        a_slug = normalize_device_slug(area_id or area_name)
        self._attr_unique_id = f"latter_area_occupants_{area_id}"
        self._attr_suggested_area = area_name
        self._attr_translation_placeholders = {"area_name": area_name}
        self.entity_id = f"sensor.{a_slug}_occupants"
        self._cached_occ: dict[str, Any] | None = None

    @callback
    def update_area_metadata(self, area_name: str) -> None:
        """Refresh the Area name when the Area registry entry is renamed."""
        self._area_name = area_name
        self._attr_suggested_area = area_name
        self._attr_translation_placeholders = {"area_name": area_name}
        if self.hass is not None:
            self.async_write_ha_state()

    def _get_occ(self) -> dict[str, Any]:
        """Return cached or freshly evaluated occupancy snapshot for this Area."""
        if self._cached_occ is None:
            self._cached_occ = get_ble_fabric(self.hass).get_area_occupancy(self._area_id)
        return self._cached_occ

    @property
    def device_info(self) -> DeviceInfo:
        """Attach Area occupancy sensors to the System-level Latter service device."""
        return get_system_device_info()

    async def async_added_to_hass(self) -> None:
        """Subscribe to real-time updates from the shared Latter BLE Fabric."""
        await super().async_added_to_hass()
        fabric = get_ble_fabric(self.hass)
        self._cached_occ = fabric.get_area_occupancy(self._area_id)
        self.async_on_remove(
            fabric.register_occupancy_listener(self._handle_occupancy_update)
        )

    @callback
    def _handle_occupancy_update(self) -> None:
        """Push updated occupant state to Home Assistant."""
        self._cached_occ = get_ble_fabric(self.hass).get_area_occupancy(self._area_id)
        self.async_write_ha_state()

    @property
    def icon(self) -> str:
        """Return dynamic icon based on area occupancy."""
        return "mdi:account-group" if self.native_value != "Empty" else "mdi:account-off-outline"

    @property
    def native_value(self) -> str:
        """Return comma-separated occupant names (<255 chars), 'Occupied (Sensor)', or 'Empty'."""
        occ = self._get_occ()
        names = list(occ.get("occupant_names") or [])
        if names:
            return format_bounded_occupant_names(names)
        if occ.get("is_occupied"):
            return "Occupied (Sensor)"
        return "Empty"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed occupant list, sensor fusion status, and signal attributes."""
        occ = self._get_occ()
        return {
            "area_id": self._area_id,
            "area_name": self._area_name,
            "floor_id": occ.get("floor_id"),
            "is_occupied": occ.get("is_occupied", False),
            "occupant_count": len(occ.get("occupant_names") or []),
            "occupant_names": list(occ.get("occupant_names") or []),
            "persons": occ.get("persons", []),
            "occupied_by": occ.get("occupied_by", []),
            "fusion_mode": occ.get("fusion_mode", "weighted"),
            "confidence_pct": occ.get("confidence_pct", 0),
            "ble_occupied": occ.get("ble_occupied", False),
            "sensor_occupied": occ.get("sensor_occupied", False),
            "active_sensors": occ.get("active_sensors", []),
            "closest_device": occ.get("closest_device"),
            "winning_rssi": occ.get("winning_rssi"),
            "closest_distance_m": occ.get("closest_distance_m"),
            "closest_distance_ft": occ.get("closest_distance_ft"),
        }
