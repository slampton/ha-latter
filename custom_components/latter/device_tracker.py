"""BLE Device Tracker platform for Latter (`device_tracker.<device_slug>` for Home/Away person tracking)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LatterCoordinator
from .hub import LatterSystemHub, get_latter_system
from .identity import find_device_entity_by_suffix
from .presence import get_ble_fabric

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up `device_tracker.<device_slug>` entities for each Latter device and BLE tag subentry."""
    runtime = entry.runtime_data
    if isinstance(runtime, LatterSystemHub):
        coordinators = list(runtime.coordinators.values())
    else:
        sys_obj = get_latter_system(hass)
        coordinators = list(sys_obj.coordinators.values()) if sys_obj else []

    for coordinator in coordinators:
        async_add_entities(
            [LatterBleDeviceTracker(coordinator)],
            config_subentry_id=coordinator.subentry_id,
        )


class LatterBleDeviceTracker(TrackerEntity):
    """Exposes `device_tracker.<device_slug>` (`home` / `not_home`) for Home Assistant `person` entities."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_translation_key = "ble_tracker"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize the BLE device tracker under its Latter DeviceEntry."""
        self.coordinator = coordinator
        slug = coordinator.device_slug
        self._attr_unique_id = f"{coordinator.subentry_id}_ble_tracker"
        self.entity_id = f"device_tracker.{slug}"

    @property
    def device_info(self) -> DeviceInfo:
        """Attach to the canonical Latter DeviceEntry for this subentry."""
        return self.coordinator.get_device_info()

    @property
    def source_type(self) -> SourceType:
        """Return Bluetooth LE as the tracker source type."""
        return SourceType.BLUETOOTH_LE

    @property
    def in_zones(self) -> list[str] | None:
        """Return ['zone.home'] when home, [] when away, or None when BLE tracking is disabled or awaiting initial fix."""
        if not self.coordinator.native_ble_tracking_enabled:
            return None
        if self.coordinator.is_device_away():
            return []
        tracker = self.coordinator._ble_tracker
        if tracker is not None and (tracker.packets_seen > 0 or tracker.current_area_id):
            return ["zone.home"]
        if not self.coordinator.is_ble_tag and self.coordinator.esphome_device_id:
            wifi_ent_id = find_device_entity_by_suffix(
                self.coordinator.hass,
                self.coordinator.esphome_device_id,
                "sensor",
                ("_wi_fi_signal", "_wifi_signal", "_ip_address"),
            )
            wifi_st = (
                self.coordinator.hass.states.get(wifi_ent_id) if wifi_ent_id else None
            )
            if wifi_st is not None and wifi_st.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
                "",
            ):
                return ["zone.home"]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return current Area, closest BLE proxy, distance, RSSI, and assigned person."""
        _, attrs = self.coordinator.get_current_area_and_distance()
        return {
            "area_id": attrs["area_id"],
            "area_name": attrs["area_name"],
            "closest_proxy": attrs["closest_proxy"],
            "distance_ft": attrs["distance_ft"],
            "distance_m": attrs["distance_m"],
            "rssi": attrs["rssi"],
            "assigned_person": attrs["assigned_person"],
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator and BLE fabric updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_tracker_update)
        )
        self.async_on_remove(
            get_ble_fabric(self.hass).register_occupancy_listener(
                self._handle_tracker_update
            )
        )

    @callback
    def _handle_tracker_update(self) -> None:
        """Write updated tracker state to Home Assistant."""
        self.async_write_ha_state()
