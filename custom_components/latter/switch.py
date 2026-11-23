"""Curated Switch entities (`switch.<device_slug>_*`) for Latter Devices."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up curated Latter switch controls for each Device subentry."""
    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, LatterSystemHub):
        coordinators: list[LatterCoordinator] = list(runtime.coordinators.values())
    else:
        sys_obj = get_latter_system(hass)
        coordinators = list(sys_obj.coordinators.values()) if sys_obj else []

    for coordinator in coordinators:
        if coordinator.is_ble_tag:
            continue
        dev_entities: list[SwitchEntity] = []
        if coordinator.has_display:
            dev_entities.extend(
                [
                    LatterBedtimeModeSwitch(coordinator),
                    LatterScreensaverSwitch(coordinator),
                ]
            )
        if coordinator.has_display or coordinator.has_speaker:
            dev_entities.append(LatterDoNotDisturbSwitch(coordinator))
        if dev_entities:
            async_add_entities(
                dev_entities,
                config_subentry_id=coordinator.subentry_id,
            )


class _BaseLatterSwitch(SwitchEntity):
    """Base switch subscribed to `LatterCoordinator` updates."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: LatterCoordinator, suffix: str) -> None:
        """Initialize the switch entity."""
        self.coordinator = coordinator
        self._attr_translation_key = suffix
        self._attr_unique_id = f"{coordinator.subentry_id}_{suffix}"

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
    def _handle_coordinator_update(self) -> None:
        """Write updated switch state to Home Assistant."""
        self.async_write_ha_state()


class LatterBedtimeModeSwitch(_BaseLatterSwitch):
    """Exposes sleep-safe `switch.<device_slug>_bedtime_mode` backed by the Device subentry."""

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Bedtime Mode switch control."""
        super().__init__(coordinator, "bedtime_mode")

    @property
    def available(self) -> bool:
        """Remain available across deep sleep so preference changes queue cleanly."""
        return True

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


class LatterDoNotDisturbSwitch(_BaseLatterSwitch):
    """Exposes sleep-safe `switch.<device_slug>_do_not_disturb` backed by the Device subentry."""

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Do Not Disturb switch control."""
        super().__init__(coordinator, "do_not_disturb")

    @property
    def available(self) -> bool:
        """Remain available across deep sleep so preference changes queue cleanly."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True when Do Not Disturb is active for this Device."""
        return self.coordinator.do_not_disturb

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable Do Not Disturb on the Device subentry."""
        _ = kwargs
        await self.coordinator.async_update_device_prefs({"do_not_disturb": True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable Do Not Disturb on the Device subentry."""
        _ = kwargs
        await self.coordinator.async_update_device_prefs({"do_not_disturb": False})


class LatterScreensaverSwitch(_BaseLatterSwitch):
    """Exposes live `switch.<device_slug>_screensaver` reflecting ambient screensaver state."""

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Screensaver switch control."""
        super().__init__(coordinator, "screensaver")

    @property
    def available(self) -> bool:
        """Return True while the bound ESPHome device has a live radio connection."""
        return self.coordinator.radio_connected

    @property
    def is_on(self) -> bool:
        """Return True while the ambient screensaver is actively displayed."""
        return self.coordinator.screensaver_active

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate the ambient screensaver immediately."""
        _ = kwargs
        await self.coordinator.async_set_screensaver(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Exit the ambient screensaver and wake the screen."""
        _ = kwargs
        await self.coordinator.async_set_screensaver(False)
