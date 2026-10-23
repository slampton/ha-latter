"""The Latter (ESPHome Companion & Entity Middleware) integration."""

from __future__ import annotations

import logging
import re
import secrets

from homeassistant.config_entries import ConfigEntry, SOURCE_INTEGRATION_DISCOVERY
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    device_registry as dr,
    discovery_flow,
    entity_registry as er,
)

from .const import (
    CONF_DEVICE_SLUG,
    DATA_DISCOVERY_UNSUB,
    DATA_HMAC_SECRET,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import LatterCoordinator
from .dashboard import LatterCompanionApiView, LatterCompanionDashboardView
from .http import LatterImageProxyView, LatterWallpaperProxyView
from .room_engine import inject_esphome_visit_link
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


def _slugify_device_name(name: str) -> str:
    """Convert an ESPHome device name into a normalized slug."""
    s = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return s


@callback
def _async_check_esphome_device_for_discovery(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> None:
    """Trigger a Latter discovery flow if a newly added ESPHome device is not configured or ignored."""
    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_device(ent_reg, device.id)
    if not any(e.platform == "esphome" for e in entries):
        return

    dev_name = str(device.name_by_user or device.name or "").strip()
    if not dev_name:
        return

    if "proxy" in dev_name.lower() and not any(
        e.domain in ("media_player", "light", "switch", "button", "select", "number")
        and e.entity_category is None
        for e in entries
    ):
        return

    slug = _slugify_device_name(dev_name)
    if not slug:
        return

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id == f"{DOMAIN}_{slug}":
            return
        if str(entry.data.get(CONF_DEVICE_SLUG, "")).lower() == slug:
            return

    discovery_flow.async_create_flow(
        hass,
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_DEVICE_SLUG: slug, "name": dev_name},
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Latter from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    if DATA_HMAC_SECRET not in domain_data:
        domain_data[DATA_HMAC_SECRET] = secrets.token_bytes(32)
        hass.http.register_view(LatterImageProxyView(hass))
        hass.http.register_view(LatterWallpaperProxyView(hass))
        hass.http.register_view(LatterCompanionDashboardView(hass))
        hass.http.register_view(LatterCompanionApiView(hass))

    coordinator = LatterCoordinator(
        hass=hass,
        entry=entry,
        hmac_secret=domain_data[DATA_HMAC_SECRET],
    )
    await coordinator.async_setup()
    domain_data[entry.entry_id] = coordinator

    inject_esphome_visit_link(
        hass, coordinator.device_slug, coordinator.build_companion_url()
    )

    if DATA_DISCOVERY_UNSUB not in domain_data:
        @callback
        def _on_device_registry_updated(event: Event) -> None:
            if event.data.get("action") not in ("create", "update"):
                return
            dev_id = event.data.get("device_id")
            if not dev_id:
                return
            dev_reg = dr.async_get(hass)
            dev = dev_reg.async_get(dev_id)
            if dev is not None:
                _async_check_esphome_device_for_discovery(hass, dev)

        domain_data[DATA_DISCOVERY_UNSUB] = hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, _on_device_registry_updated
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _LOGGER.info(
        "Latter v1.2.2 initialized for ESPHome device '%s' (companion_url: %s)",
        coordinator.device_slug,
        coordinator.build_companion_url(),
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