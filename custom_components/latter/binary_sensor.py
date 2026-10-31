"""Per-Area BLE Occupancy Binary Sensors for the Latter integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .ble_engine import get_ble_fabric, get_ble_proxy_area_ids
from .const import DOMAIN
from .coordinator import LatterCoordinator

PARALLEL_UPDATES = 0
DATA_CREATED_AREA_OCCUPANCY_IDS = "created_area_occupancy_ids"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up per-area BLE occupancy binary sensors once across the Latter domain."""
    coordinator: LatterCoordinator = entry.runtime_data
    domain_data = hass.data.setdefault(DOMAIN, {})
    created_areas: set[str] = domain_data.setdefault(
        DATA_CREATED_AREA_OCCUPANCY_IDS, set()
    )
    entry_area_ids: set[str] = set()

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
        new_entities.append(
            LatterAreaBleOccupancyBinarySensor(
                hass, coordinator, area_entry.id, area_entry.name
            )
        )

    @callback
    def _cleanup_entry_areas() -> None:
        created_areas.difference_update(entry_area_ids)

    entry.async_on_unload(_cleanup_entry_areas)

    if new_entities:
        async_add_entities(new_entities)


class LatterAreaBleOccupancyBinarySensor(BinarySensorEntity):
    """Binary sensor representing aggregated BLE presence occupancy in a Home Assistant Area."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: LatterCoordinator,
        area_id: str,
        area_name: str,
    ) -> None:
        """Initialize the per-area BLE occupancy binary sensor."""
        self.hass = hass
        self.coordinator = coordinator
        self._area_id = area_id
        self._area_name = area_name
        self._attr_name = f"{area_name} BLE Occupancy"
        self._attr_unique_id = f"latter_area_ble_occupancy_{area_id}"
        self._attr_suggested_area = area_name
        self._cached_occ: dict[str, Any] | None = None

    def _get_occ(self) -> dict[str, Any]:
        """Return cached or freshly evaluated occupancy snapshot for this Area."""
        if self._cached_occ is None:
            self._cached_occ = get_ble_fabric(self.hass).get_area_occupancy(self._area_id)
        return self._cached_occ

    @property
    def device_info(self) -> DeviceInfo:
        """Return canonical Latter DeviceInfo."""
        return self.coordinator.get_device_info()

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
            "fusion_mode": occ.get("fusion_mode", "auto_bayes"),
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
            "closest_distance_m": occ["closest_distance_m"],
            "closest_distance_ft": occ.get("closest_distance_ft"),
        }
