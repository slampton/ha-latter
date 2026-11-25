"""On-device Screen Light entity (`light.<device_slug>_screen`) for Latter Displays."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import LightEntity
from homeassistant.components.light.const import ATTR_BRIGHTNESS, ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LatterCoordinator
from .hub_registry import LatterSystemHub, get_latter_system

PARALLEL_UPDATES = 0
_MAX_HA_BRIGHTNESS = 255
_MAX_BRIGHTNESS_PCT = 100


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[LatterSystemHub],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up `light.<device_slug>_screen` for each display Device subentry."""
    runtime = getattr(entry, "runtime_data", None)
    if isinstance(runtime, LatterSystemHub):
        coordinators: list[LatterCoordinator] = list(runtime.coordinators.values())
    else:
        sys_obj = get_latter_system(hass)
        coordinators = list(sys_obj.coordinators.values()) if sys_obj else []

    for coordinator in coordinators:
        if coordinator.is_ble_tag or not coordinator.has_display:
            continue
        async_add_entities(
            [LatterScreenLight(coordinator)],
            config_subentry_id=coordinator.subentry_id,
        )


class LatterScreenLight(LightEntity):
    """Exposes `light.<device_slug>_screen` with `1..100%` brightness and radio-honest availability."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "screen"
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, coordinator: LatterCoordinator) -> None:
        """Initialize the Screen light entity."""
        self.coordinator = coordinator
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_unique_id = f"{coordinator.subentry_id}_screen"

    @property
    def device_info(self) -> DeviceInfo:
        """Return canonical Latter `DeviceInfo`."""
        return self.coordinator.get_device_info()

    @property
    def available(self) -> bool:
        """Return True while the bound ESPHome device has a live radio connection."""
        return self.coordinator.radio_connected

    @property
    def is_on(self) -> bool:
        """Return True while the screen is actively awake (`display_power_state == 0`)."""
        return self.coordinator.display_power_state == 0

    @property
    def brightness(self) -> int:
        """Return screen brightness scaled to Home Assistant's `0..255` range."""
        return max(
            1,
            min(
                _MAX_HA_BRIGHTNESS,
                round(
                    self.coordinator.display_brightness_pct
                    * _MAX_HA_BRIGHTNESS
                    / _MAX_BRIGHTNESS_PCT
                ),
            ),
        )

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
        """Write updated screen state to Home Assistant."""
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Wake the screen and optionally update display brightness."""
        pct: int | None = None
        if ATTR_BRIGHTNESS in kwargs and kwargs[ATTR_BRIGHTNESS] is not None:
            pct = max(
                1,
                min(
                    _MAX_BRIGHTNESS_PCT,
                    round(
                        int(kwargs[ATTR_BRIGHTNESS])
                        * _MAX_BRIGHTNESS_PCT
                        / _MAX_HA_BRIGHTNESS
                    ),
                ),
            )
        await self.coordinator.async_set_screen_light(
            turn_on=True, brightness_pct=pct
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the display backlight."""
        _ = kwargs
        await self.coordinator.async_set_screen_light(turn_on=False)
