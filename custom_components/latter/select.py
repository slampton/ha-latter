"""Sleep-safe Tier 2 Select entities (`select.<device_slug>_*`) for Latter Devices."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import build_device_entity_id
from .coordinator import LatterCoordinator
from .hub import LatterSystemHub, get_latter_system
from .studio.settings import POWER_PROFILE_OPTIONS, WAKE_WORD_MODE_OPTIONS

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up curated sleep-safe Latter select controls for each Device subentry."""
    runtime = entry.runtime_data
    if isinstance(runtime, LatterSystemHub):
        coordinators = list(runtime.coordinators.values())
    else:
        sys_obj = get_latter_system(hass)
        coordinators = list(sys_obj.coordinators.values()) if sys_obj else []

    for coordinator in coordinators:
        if coordinator.is_ble_tag:
            continue
        dev_entities: list[SelectEntity] = []
        if coordinator.has_display:
            dev_entities.append(LatterPowerProfileSelect(coordinator))
        if coordinator.has_mic:
            dev_entities.append(LatterWakeWordModeSelect(coordinator))
        if dev_entities:
            async_add_entities(dev_entities, config_subentry_id=coordinator.subentry_id)


class _BaseLatterSelect(SelectEntity):
    """Base sleep-safe select entity backed by the Device subentry and Protocol v3 `device_prefs`."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: LatterCoordinator,
        pref_key: str,
        options: tuple[str, ...],
    ) -> None:
        """Initialize the select entity for `pref_key`."""
        self.coordinator = coordinator
        self._pref_key = pref_key
        self._attr_translation_key = pref_key
        self._attr_options = list(options)
        self._attr_unique_id = f"{coordinator.subentry_id}_{pref_key}"
        self.entity_id = build_device_entity_id(
            coordinator.device_slug, pref_key, "select"
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
        """Write updated preference state to Home Assistant."""
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return the active subentry preference option."""
        return str(self.coordinator.get_device_pref(self._pref_key))

    async def async_select_option(self, option: str) -> None:
        """Persist the selected option in the Device subentry (pushes immediately when online)."""
        await self.coordinator.async_update_device_prefs({self._pref_key: option})


class LatterPowerProfileSelect(_BaseLatterSelect):
    """Exposes select.<device_slug>_power_profile."""

    _attr_icon = "mdi:lightning-bolt-outline"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Power Profile select."""
        super().__init__(coordinator, "power_profile", POWER_PROFILE_OPTIONS)


class LatterWakeWordModeSelect(_BaseLatterSelect):
    """Exposes select.<device_slug>_wake_word_mode."""

    _attr_icon = "mdi:account-voice"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Wake Word Mode select."""
        super().__init__(coordinator, "wake_word_mode", WAKE_WORD_MODE_OPTIONS)
