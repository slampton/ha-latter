"""Sleep-safe Tier 2 Select entities (`select.<device_slug>_*`) for Latter Devices."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_DEVICE_GROUP,
    CONF_GLASS_STYLE,
    DEFAULT_DEVICE_GROUP,
    DOMAIN,
)
from .coordinator import LatterCoordinator
from .groups.device_groups import (
    async_apply_group_baseline_to_coordinators,
    get_device_groups,
)
from .hub_registry import LatterSystemHub, get_latter_system
from .protocol_specs import GLASS_STYLE_OPTIONS, WAKE_WORD_MODE_OPTIONS

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[LatterSystemHub],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up curated sleep-safe Latter select controls for each Device subentry."""
    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, LatterSystemHub):
        coordinators: list[LatterCoordinator] = list(runtime.coordinators.values())
    else:
        sys_obj = get_latter_system(hass)
        coordinators = list(sys_obj.coordinators.values()) if sys_obj else []

    for coordinator in coordinators:
        if coordinator.is_ble_tag:
            continue
        dev_entities: list[SelectEntity] = [LatterDeviceGroupSelect(coordinator)]
        if coordinator.has_mic:
            dev_entities.append(LatterWakeWordModeSelect(coordinator))
        if coordinator.has_display:
            dev_entities.append(LatterGlassStyleSelect(coordinator))
        async_add_entities(dev_entities, config_subentry_id=coordinator.subentry_id)


class _BaseLatterSelect(SelectEntity):
    """Base sleep-safe select entity backed by the Device subentry and Protocol v3 `device_prefs`."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

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
        """Write updated preference state to Home Assistant."""
        self.async_write_ha_state()

    @property
    def current_option(self) -> str | None:
        """Return the active subentry preference option."""
        return str(self.coordinator.get_device_pref(self._pref_key))

    async def async_select_option(self, option: str) -> None:
        """Persist the selected option in the Device subentry (pushes immediately when online)."""
        await self.coordinator.async_update_device_prefs({self._pref_key: option})


class LatterDeviceGroupSelect(SelectEntity):
    """Exposes `select.<device_slug>_device_group` across built-in/custom Device Groups and Custom."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "device_group"

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Device Group select."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.subentry_id}_device_group"

    @property
    def device_info(self) -> DeviceInfo:
        """Return canonical Latter `DeviceInfo`."""
        return self.coordinator.get_device_info()

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator and global config updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write updated Device Group state to Home Assistant."""
        self.async_write_ha_state()

    @property
    def options(self) -> list[str]:
        """Return all configured Device Group names plus `Custom`."""
        groups = get_device_groups(self.coordinator.hass)
        return [*(str(g["name"]) for g in groups), "Custom"]

    @property
    def current_option(self) -> str | None:
        """Return the active Device Group display name or `'Custom'`."""
        gid = self.coordinator.device_group
        if not gid or gid == DEFAULT_DEVICE_GROUP:
            return "Custom"
        for grp in get_device_groups(self.coordinator.hass):
            if grp.get("id") == gid:
                return str(grp["name"])
        return "Custom"

    async def async_select_option(self, option: str) -> None:
        """Apply the chosen Device Group baseline (or switch to Custom)."""
        target = option.strip()
        if target == "Custom" or target.lower() == DEFAULT_DEVICE_GROUP:
            self.coordinator.update_device_config(
                {**self.coordinator.device_data, CONF_DEVICE_GROUP: DEFAULT_DEVICE_GROUP},
                preserve_group=True,
            )
            await self.coordinator.async_apply_options()
            self.coordinator.async_update_listeners()
            self.coordinator.async_notify_listeners()
            return
        groups = get_device_groups(self.coordinator.hass)
        matched = next(
            (g for g in groups if g.get("name") == target or g.get("id") == target),
            None,
        )
        if matched is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_option",
                translation_placeholders={"option": option},
            )
        await async_apply_group_baseline_to_coordinators(
            self.coordinator.hass, matched, [self.coordinator]
        )


class LatterWakeWordModeSelect(_BaseLatterSelect):
    """Exposes `select.<device_slug>_wake_word_mode`."""

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Wake Word Mode select."""
        super().__init__(coordinator, "wake_word_mode", WAKE_WORD_MODE_OPTIONS)


class LatterGlassStyleSelect(_BaseLatterSelect):
    """Exposes `select.<device_slug>_glass_style`."""

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize Glass Style select."""
        super().__init__(coordinator, CONF_GLASS_STYLE, GLASS_STYLE_OPTIONS)
