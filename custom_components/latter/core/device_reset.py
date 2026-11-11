"""Reset a Latter Device to defaults: the settings saved on the device and/or its Latter options."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from ..const import CONF_BLE_TARGET_ADDRESS, DOMAIN
from .identity import esphome_service, get_bound_esphome_device
from .reset_policy import (
    BLE_TAG_IDENTITY_KEYS,
    DEVICE_IDENTITY_KEYS,
    reset_flags_error,
    reset_subentry_data,
)

if TYPE_CHECKING:
    from .device_coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)

FACTORY_RESET_MIN_SDK_REV = 2026110261

_FLAG_ERRORS: dict[str, str] = {
    "reset_nothing_selected": "Select what to reset: the device settings, the Latter options, or both.",
    "reset_ble_tag_has_no_device_settings": "A BLE tag has no device settings to reset. Reset only its Latter options.",
}


async def async_reset_device(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    *,
    device_settings: bool = True,
    latter_options: bool = True,
) -> None:
    """Reset a Latter Device."""
    from ..config_flow import ble_tag_option_defaults, device_option_defaults

    error_key = reset_flags_error(
        device_settings, latter_options, is_ble_tag=coordinator.is_ble_tag
    )
    if error_key is not None:
        raise ServiceValidationError(
            _FLAG_ERRORS[error_key],
            translation_domain=DOMAIN,
            translation_key=error_key,
        )

    reset_action: str | None = None
    if device_settings:
        reset_action = esphome_service(
            hass, coordinator.esphome_device_id, "latter_factory_reset"
        )
        if reset_action is None:
            raise ServiceValidationError(
                f"{coordinator.device_title} doesn't offer Reset to defaults. Update its firmware "
                f"to Latter SDK rev {FACTORY_RESET_MIN_SDK_REV} or later.",
                translation_domain=DOMAIN,
                translation_key="factory_reset_unsupported",
                translation_placeholders={
                    "device": coordinator.device_title,
                    "sdk_rev": str(FACTORY_RESET_MIN_SDK_REV),
                },
            )

    if latter_options:
        current = coordinator.device_data
        if coordinator.is_ble_tag:
            defaults = ble_tag_option_defaults(
                coordinator.device_slug, str(current.get(CONF_BLE_TARGET_ADDRESS) or "")
            )
            identity_keys = BLE_TAG_IDENTITY_KEYS
        else:
            defaults = device_option_defaults(
                hass,
                get_bound_esphome_device(hass, coordinator.esphome_device_id),
                coordinator.hardware_manifest,
            )
            identity_keys = DEVICE_IDENTITY_KEYS
        coordinator.update_device_config(
            reset_subentry_data(current, defaults, identity_keys)
        )
        await coordinator.async_apply_options()
        coordinator._bind_wallpaper_cycle_timer()
        coordinator.async_notify_listeners()
        _LOGGER.info("Reset the Latter options of '%s' to defaults", coordinator.device_slug)

    if reset_action is not None:
        try:
            await hass.services.async_call("esphome", reset_action, {}, blocking=True)
        except HomeAssistantError as err:
            raise HomeAssistantError(
                f"{coordinator.device_title} didn't accept Reset to defaults: {err}",
                translation_domain=DOMAIN,
                translation_key="factory_reset_failed",
                translation_placeholders={
                    "device": coordinator.device_title,
                    "error": str(err),
                },
            ) from err
        _LOGGER.info(
            "Sent latter_factory_reset to '%s'; the device erases its saved settings and restarts",
            coordinator.device_slug,
        )
