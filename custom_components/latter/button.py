"""Tier 2 Action Button entities (`button.<device_slug>_*`) for Latter Devices."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.components.button.const import ButtonDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LatterCoordinator
from .hub_registry import LatterSystemHub, get_latter_system

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[LatterSystemHub],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up curated Latter action buttons for each Device subentry."""
    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, LatterSystemHub):
        coordinators: list[LatterCoordinator] = list(runtime.coordinators.values())
    else:
        sys_obj = get_latter_system(hass)
        coordinators = list(sys_obj.coordinators.values()) if sys_obj else []

    for coordinator in coordinators:
        if coordinator.is_ble_tag:
            continue
        dev_entities: list[ButtonEntity] = []
        if coordinator.has_speaker:
            dev_entities.append(LatterFindMyDeviceButton(coordinator))
        if coordinator.has_display:
            dev_entities.append(LatterDismissAlertButton(coordinator))
        if dev_entities:
            async_add_entities(dev_entities, config_subentry_id=coordinator.subentry_id)


class _BaseLatterButton(ButtonEntity):
    """Base radio-honest action button subscribed to `LatterCoordinator` updates."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: LatterCoordinator, suffix: str) -> None:
        """Initialize the device action button."""
        self.coordinator = coordinator
        self._attr_translation_key = suffix
        self._attr_unique_id = f"{coordinator.subentry_id}_{suffix}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return canonical Latter `DeviceInfo`."""
        return self.coordinator.get_device_info()

    @property
    def available(self) -> bool:
        """Return True while the bound ESPHome device has a live radio connection."""
        return self.coordinator.radio_connected

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator updates so availability stays accurate."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write updated button availability to Home Assistant."""
        self.async_write_ha_state()


class LatterFindMyDeviceButton(_BaseLatterButton):
    """Exposes `button.<device_slug>_find_my_device`."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Find My Device button."""
        super().__init__(coordinator, "find_my_device")

    async def async_press(self) -> None:
        """Play the Find My Device locator chime over ESPHome."""
        await self.coordinator.async_send_device_command(
            "find_my", raise_if_offline=True
        )


class LatterDismissAlertButton(_BaseLatterButton):
    """Exposes `button.<device_slug>_dismiss_alert`."""

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Dismiss Alert button."""
        super().__init__(coordinator, "dismiss_alert")

    async def async_press(self) -> None:
        """Dismiss any active notification banner or ringing timer/alarm alert."""
        await self.coordinator.async_dismiss_alert()
