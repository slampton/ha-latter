"""Sleep-safe Tier 2 Number entities (`number.<device_slug>_*`) for Latter Devices."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LatterCoordinator
from .hub_registry import LatterSystemHub

PARALLEL_UPDATES = 0
_MIN_ALERT_VOL = 20
_MAX_ALERT_VOL = 100
_STEP_ALERT_VOL = 5


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[LatterSystemHub],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up curated sleep-safe Latter number controls for each Device subentry."""
    coordinators: list[LatterCoordinator] = list(entry.runtime_data.coordinators.values())

    for coordinator in coordinators:
        if coordinator.is_ble_tag or not coordinator.has_speaker:
            continue
        async_add_entities(
            [LatterAlertVolumeNumber(coordinator)],
            config_subentry_id=coordinator.subentry_id,
        )


class LatterAlertVolumeNumber(NumberEntity):
    """Exposes `number.<device_slug>_alert_volume` backed by the Device subentry."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "alert_volume"
    _attr_native_min_value = float(_MIN_ALERT_VOL)
    _attr_native_max_value = float(_MAX_ALERT_VOL)
    _attr_native_step = float(_STEP_ALERT_VOL)
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Alert Volume number control."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.subentry_id}_alert_volume"

    @property
    def device_info(self) -> DeviceInfo:
        """Return canonical Latter `DeviceInfo`."""
        return self.coordinator.get_device_info()

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Accept in-place entity_id renames without tearing down subscriptions."""
        super().async_entity_id_changed(old_entity_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write updated preference state to Home Assistant."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        """Return the configured alert volume percentage."""
        return float(self.coordinator.get_device_pref("alert_volume"))

    async def async_set_native_value(self, value: float) -> None:
        """Persist the alert volume in the Device subentry (pushes immediately when online)."""
        stepped = max(
            _MIN_ALERT_VOL,
            min(_MAX_ALERT_VOL, int(round(value / _STEP_ALERT_VOL) * _STEP_ALERT_VOL)),
        )
        await self.coordinator.async_update_device_prefs({"alert_volume": stepped})
