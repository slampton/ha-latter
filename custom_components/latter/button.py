"""Tier 2 Action Button entities (`button.<device_slug>_*`) for Latter Devices."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    """Set up curated Latter action buttons for each Device subentry."""
    runtime = entry.runtime_data
    if isinstance(runtime, LatterSystemHub):
        coordinators = list(runtime.coordinators.values())
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
            dev_entities.append(LatterActivateScreensaverButton(coordinator))
        if dev_entities:
            async_add_entities(dev_entities, config_subentry_id=coordinator.subentry_id)


class _BaseLatterButton(ButtonEntity):
    """Base action button forwarding to `esphome.<node>_latter_device_command`."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, coordinator: LatterCoordinator, suffix: str, command: str
    ) -> None:
        """Initialize the device action button."""
        self.coordinator = coordinator
        self._command = command
        self._attr_translation_key = suffix
        self._attr_unique_id = f"{coordinator.subentry_id}_{suffix}"
        self.entity_id = build_device_entity_id(
            coordinator.device_slug, suffix, "button"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return canonical Latter DeviceInfo."""
        return self.coordinator.get_device_info()

    async def async_press(self) -> None:
        """Send the immediate device command over ESPHome (raises HomeAssistantError when sleeping)."""
        await self.coordinator.async_send_device_command(
            self._command, raise_if_offline=True
        )


class LatterFindMyDeviceButton(_BaseLatterButton):
    """Exposes button.<device_slug>_find_my_device."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_icon = "mdi:bell-alert-outline"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Find My Device button."""
        super().__init__(coordinator, "find_my_device", "find_my")


class LatterActivateScreensaverButton(_BaseLatterButton):
    """Exposes button.<device_slug>_activate_screensaver."""

    _attr_icon = "mdi:weather-night"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Activate Screensaver button."""
        super().__init__(coordinator, "activate_screensaver", "activate_screensaver")
