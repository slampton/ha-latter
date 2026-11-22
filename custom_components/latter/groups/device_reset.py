"""Device factory-reset and Latter options-reset policy & execution (`L2a`)."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from ..config_defaults import ble_tag_option_defaults
from ..const import CONF_BLE_TARGET_ADDRESS, DOMAIN, MIN_FIRMWARE_SDK_REV
from ..identity import esphome_service, get_bound_esphome_device
from ..protocol_specs import DEVICE_PREF_KEYS
from .device_groups import device_option_defaults

if TYPE_CHECKING:
    from ..coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)

DEVICE_IDENTITY_KEYS: Final[tuple[str, ...]] = (
    "esphome_device_id",
    "mac",
    "device_slug",
    "ma_player_entity",
)

BLE_TAG_IDENTITY_KEYS: Final[tuple[str, ...]] = (
    "device_slug",
    "ble_target_address",
)

FACTORY_RESET_MIN_SDK_REV: Final = MIN_FIRMWARE_SDK_REV

_FLAG_ERRORS: Final[dict[str, str]] = {
    "reset_nothing_selected": "Select what to reset: the device settings, the Latter options, or both.",
    "reset_ble_tag_has_no_device_settings": "A BLE tag has no device settings to reset. Reset only its Latter options.",
}


def reset_flags_error(
    device_settings: bool, latter_options: bool, *, is_ble_tag: bool
) -> str | None:
    """Return the translation key of the reason a reset request is invalid, or `None` if valid."""
    if not device_settings and not latter_options:
        return "reset_nothing_selected"
    if device_settings and is_ble_tag:
        return "reset_ble_tag_has_no_device_settings"
    return None


def reset_subentry_data(
    current: Mapping[str, Any],
    defaults: Mapping[str, Any],
    identity_keys: tuple[str, ...],
) -> dict[str, Any]:
    """Return the subentry data after a reset: defaults plus the identity keys from `current`."""
    out = {k: v for k, v in defaults.items() if k not in identity_keys}
    for key in identity_keys:
        if key in current:
            out[key] = current[key]
    return out


async def async_reset_device(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    *,
    device_settings: bool = True,
    latter_options: bool = True,
) -> None:
    """Reset a Latter Device's on-device NVS preferences and/or Home Assistant Latter options."""
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
        coordinator.update_device_config(reset_subentry_data(current, defaults, identity_keys))
        await coordinator.async_apply_options()
        coordinator.bind_wallpaper_cycle_timer()
        coordinator.bind_screensaver_cycle_timer()
        coordinator.async_notify_listeners()
        _LOGGER.info("Reset the Latter options of '%s' to defaults", coordinator.device_slug)
    elif device_settings and not coordinator.is_ble_tag:
        stripped = {
            k: v for k, v in coordinator.device_data.items() if k not in DEVICE_PREF_KEYS
        }
        if stripped != coordinator.device_data:
            coordinator.update_device_config(stripped)
            coordinator.async_notify_listeners()

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
