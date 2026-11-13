"""Per-Area BLE Occupancy and per-Device Timer/Alarm Binary Sensors for Latter."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, build_device_entity_id, normalize_device_slug
from .coordinator import LatterCoordinator
from .hub import LatterSystemHub, get_latter_system, get_system_device_info
from .presence import get_ble_fabric, get_ble_proxy_area_ids

PARALLEL_UPDATES = 0
DATA_CREATED_AREA_OCCUPANCY_IDS = "created_area_occupancy_ids"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up per-Device timer/alarm binary sensors and per-Area BLE occupancy binary sensors."""
    runtime = entry.runtime_data
    if isinstance(runtime, LatterSystemHub):
        coordinators = list(runtime.coordinators.values())
    else:
        sys_obj = get_latter_system(hass)
        coordinators = list(sys_obj.coordinators.values()) if sys_obj else []

    for coordinator in coordinators:
        if not coordinator.is_ble_tag and coordinator.has_display:
            async_add_entities(
                [
                    LatterTimerActiveBinarySensor(coordinator),
                    LatterAlarmRingingBinarySensor(coordinator),
                ],
                config_subentry_id=coordinator.subentry_id,
            )
    domain_data = hass.data.setdefault(DOMAIN, {})
    created_areas: set[str] = domain_data.setdefault(
        DATA_CREATED_AREA_OCCUPANCY_IDS, set()
    )
    entry_area_ids: set[str] = set()
    area_entities_by_id: dict[str, LatterAreaBleOccupancyBinarySensor] = {}

    area_reg = ar.async_get(hass)
    proxy_areas = get_ble_proxy_area_ids(hass)
    candidate_areas = proxy_areas or {a.id for a in area_reg.async_list_areas()}

    new_entities: list[LatterAreaBleOccupancyBinarySensor] = []
    for area_id in sorted(candidate_areas):
        if area_id in created_areas:
            continue
        area_entry = area_reg.async_get_area(area_id)
        if area_entry is None:
            continue
        created_areas.add(area_id)
        entry_area_ids.add(area_id)
        ent = LatterAreaBleOccupancyBinarySensor(hass, area_entry.id, area_entry.name)
        area_entities_by_id[area_id] = ent
        new_entities.append(ent)

    @callback
    def _async_on_area_registry_updated(event: Event) -> None:
        action = event.data.get("action")
        area_id = str(event.data.get("area_id") or "").strip()
        if not area_id:
            return
        if action == "create":
            if area_id in created_areas:
                return
            area_entry = ar.async_get(hass).async_get_area(area_id)
            if area_entry is None:
                return
            created_areas.add(area_id)
            entry_area_ids.add(area_id)
            ent = LatterAreaBleOccupancyBinarySensor(
                hass, area_entry.id, area_entry.name
            )
            area_entities_by_id[area_id] = ent
            async_add_entities([ent])
        elif action == "update":
            ent = area_entities_by_id.get(area_id)
            area_entry = ar.async_get(hass).async_get_area(area_id)
            if ent is not None and area_entry is not None:
                ent.update_area_metadata(area_entry.name)
        elif action == "remove":
            created_areas.discard(area_id)
            entry_area_ids.discard(area_id)
            ent = area_entities_by_id.pop(area_id, None)
            if ent is not None:
                ent_reg = er.async_get(hass)
                if ent_reg.async_get(ent.entity_id) is not None:
                    ent_reg.async_remove(ent.entity_id)
                if ent.hass is not None:
                    hass.async_create_task(ent.async_remove())

    @callback
    def _cleanup_entry_areas() -> None:
        created_areas.difference_update(entry_area_ids)
        area_entities_by_id.clear()

    entry.async_on_unload(_cleanup_entry_areas)
    entry.async_on_unload(
        hass.bus.async_listen(
            ar.EVENT_AREA_REGISTRY_UPDATED, _async_on_area_registry_updated
        )
    )

    if new_entities:
        async_add_entities(new_entities)


class LatterAreaBleOccupancyBinarySensor(BinarySensorEntity):
    """Binary sensor representing aggregated BLE presence occupancy in a Home Assistant Area."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_translation_key = "area_ble_occupancy"

    def __init__(
        self,
        hass: HomeAssistant,
        area_id: str,
        area_name: str,
    ) -> None:
        """Initialize the per-area BLE occupancy binary sensor."""
        self.hass = hass
        self._area_id = area_id
        self._area_name = area_name
        a_slug = normalize_device_slug(area_id or area_name)
        self._attr_unique_id = f"latter_area_ble_occupancy_{area_id}"
        self._attr_suggested_area = area_name
        self._attr_translation_placeholders = {"area_name": area_name}
        self.entity_id = f"binary_sensor.{a_slug}_ble_occupancy"
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
        """Attach Area BLE occupancy sensors to the System-level Latter service device."""
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
        """Push updated occupancy state to Home Assistant."""
        self._cached_occ = get_ble_fabric(self.hass).get_area_occupancy(self._area_id)
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True if any tracked BLE beacon or device is currently in this area."""
        occ = self._get_occ()
        return bool(occ["is_occupied"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed occupant list, sensor fusion status, and strongest signal telemetry for the area."""
        occ = self._get_occ()
        return {
            "area_id": self._area_id,
            "area_name": self._area_name,
            "floor_id": occ.get("floor_id"),
            "fusion_mode": occ.get("fusion_mode", "weighted"),
            "confidence_pct": occ.get("confidence_pct", 0),
            "ble_occupied": occ.get("ble_occupied", False),
            "sensor_occupied": occ.get("sensor_occupied", False),
            "active_sensors": occ.get("active_sensors", []),
            "tracker_count": occ["tracker_count"],
            "occupied_by": occ["occupied_by"],
            "occupant_names": occ.get("occupant_names", []),
            "persons": occ.get("persons", []),
            "closest_device": occ["closest_device"],
            "winning_rssi": occ["winning_rssi"],
            "closest_distance_m": occ.get("closest_distance_m"),
            "closest_distance_ft": occ.get("closest_distance_ft"),
        }


class _BaseLatterDeviceBinarySensor(BinarySensorEntity):
    """Base binary sensor subscribed to event-driven LatterCoordinator updates."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: LatterCoordinator, suffix: str) -> None:
        """Initialize the device binary sensor."""
        self.coordinator = coordinator
        self._attr_translation_key = suffix
        self._attr_unique_id = f"{coordinator.subentry_id}_{suffix}"
        self.entity_id = build_device_entity_id(
            coordinator.device_slug, suffix, "binary_sensor"
        )

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
        """Write updated binary state to Home Assistant."""
        self.async_write_ha_state()


class LatterTimerActiveBinarySensor(_BaseLatterDeviceBinarySensor):
    """Exposes binary_sensor.<device_slug>_timer_active."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize timer active binary sensor."""
        super().__init__(coordinator, "timer_active")

    @property
    def is_on(self) -> bool:
        """Return True while the countdown timer is actively ticking."""
        return self.coordinator.timer_running


class LatterAlarmRingingBinarySensor(_BaseLatterDeviceBinarySensor):
    """Exposes binary_sensor.<device_slug>_alarm_ringing."""

    _attr_device_class = BinarySensorDeviceClass.SOUND
    _attr_icon = "mdi:alarm-bell"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize alarm ringing binary sensor."""
        super().__init__(coordinator, "alarm_ringing")

    @property
    def is_on(self) -> bool:
        """Return True while an alarm or expired timer alert is actively ringing."""
        return self.coordinator.alarm_ringing
