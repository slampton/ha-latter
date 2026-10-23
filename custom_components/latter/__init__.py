"""The Latter (ESPHome Companion & Entity Middleware) integration."""

from __future__ import annotations

import logging
import secrets

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DATA_HMAC_SECRET, DOMAIN, PLATFORMS
from .coordinator import LatterCoordinator
from .http import LatterImageProxyView
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Latter from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    if DATA_HMAC_SECRET not in domain_data:
        domain_data[DATA_HMAC_SECRET] = secrets.token_bytes(32)
        hass.http.register_view(LatterImageProxyView(hass))

    coordinator = LatterCoordinator(
        hass=hass,
        entry=entry,
        hmac_secret=domain_data[DATA_HMAC_SECRET],
    )
    await coordinator.async_setup()
    domain_data[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _LOGGER.info(
        "Latter initialized for ESPHome device '%s' (active speaker: %s)",
        coordinator.device_slug,
        coordinator.active_speaker,
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Latter config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: LatterCoordinator | None = hass.data[DOMAIN].pop(
            entry.entry_id, None
        )
        if coordinator is not None:
            await coordinator.async_shutdown()
    return unload_ok