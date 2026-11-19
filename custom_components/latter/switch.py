"""Sleep-safe Tier 2 Switch entities (`switch.<device_slug>_*`) for Latter Devices."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import build_device_entity_id
from .coordinator import LatterCoordinator
from .hub import LatterSystemHub, get_latter_system

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up curated sleep-safe Latter switch controls for each display Device subentry."""
    runtime = entry.runtime_data
    if isinstance(runtime, LatterSystemHub):
        coordinators = list(runtime.coordinators.values())
    else:
        sys_obj = get_latter_system(hass)
        coordinators = list(sys_obj.coordinators.values()) if sys_obj else []

    for coordinator in coordinators:
        if coordinator.is_ble_tag or not coordinator.has_display:
            continue
        async_add_entities(
            [LatterBedtimeModeSwitch(coordinator)],
            config_subentry_id=coordinator.subentry_id,
        )


class LatterBedtimeModeSwitch(SwitchEntity):
    """Exposes switch.<device_slug>_bedtime_mode backed by the Device subentry."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "bedtime_mode"
    _attr_icon = "mdi:weather-night"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Bedtime Mode switch control."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.subentry_id}_bedtime_mode"
        self.entity_id = build_device_entity_id(
            coordinator.device_slug, "bedtime_mode", "switch"
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
        """Write updated bedtime preference state to Home Assistant."""
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        """Return True when Bedtime Mode is active for this Device."""
        return bool(self.coordinator.get_device_pref("bedtime_active"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable Bedtime Mode on the Device subentry (pushes immediately when online)."""
        _ = kwargs
        await self.coordinator.async_update_device_prefs({"bedtime_active": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable Bedtime Mode on the Device subentry (pushes immediately when online)."""
        _ = kwargs
        await self.coordinator.async_update_device_prefs({"bedtime_active": False})
