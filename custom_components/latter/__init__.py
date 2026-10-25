"""The Latter (Universal ESPHome Companion & Entity Middleware) integration."""

from __future__ import annotations

import logging
import re
import secrets
from typing import Any

from homeassistant.config_entries import ConfigEntry, SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery_flow,
    entity_registry as er,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEVICE_SLUG,
    DATA_DISCOVERY_UNSUB,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DATA_HMAC_SECRET,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
    GLOBAL_STORAGE_KEY,
    INTEGRATION_VERSION,
    PLATFORMS,
    STORAGE_VERSION,
)
from .coordinator import LatterCoordinator
from .dashboard import (
    LatterBrandIconView,
    LatterCompanionApiView,
    LatterCompanionDashboardView,
)
from .http import (
    LatterArtworkTranscoderView,
    LatterCameraSnapshotView,
    LatterWallpaperProxyView,
)
from .room_engine import inject_esphome_visit_link, inject_hacs_update_brand_icon
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type LatterConfigEntry = ConfigEntry[LatterCoordinator]


def _slugify_device_name(name: str) -> str:
    """Convert an ESPHome device name into a normalized slug."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


async def _async_ensure_global_store(
    hass: HomeAssistant, seed_entry: ConfigEntry | None = None
) -> dict[str, Any]:
    """Load or initialize the shared Global Household configuration store (`.storage/latter.household`)."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if DATA_GLOBAL_STORE not in domain_data:
        store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, GLOBAL_STORAGE_KEY
        )
        domain_data[DATA_GLOBAL_STORE] = store
        loaded = await store.async_load()
        domain_data[DATA_GLOBAL_CONFIG] = dict(loaded) if isinstance(loaded, dict) else {}

    global_cfg: dict[str, Any] = domain_data[DATA_GLOBAL_CONFIG]
    if seed_entry is not None:
        merged_entry = {**seed_entry.data, **(seed_entry.options or {})}
        changed = False
        for k in GLOBAL_CONFIG_KEYS:
            if k not in global_cfg and k in merged_entry and merged_entry[k] not in (None, "", [], {}):
                global_cfg[k] = merged_entry[k]
                changed = True
        if changed:
            await domain_data[DATA_GLOBAL_STORE].async_save(global_cfg)

    return global_cfg


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Latter domain and register domain-level services (Platinum action-setup)."""
    hass.data.setdefault(DOMAIN, {})
    await _async_ensure_global_store(hass)
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> bool:
    """Set up Latter from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    await _async_ensure_global_store(hass, seed_entry=entry)

    if DATA_HMAC_SECRET not in domain_data:
        domain_data[DATA_HMAC_SECRET] = secrets.token_bytes(32)
        hass.http.register_view(LatterArtworkTranscoderView(hass))
        hass.http.register_view(LatterWallpaperProxyView(hass))
        hass.http.register_view(LatterCameraSnapshotView(hass))
        hass.http.register_view(LatterCompanionDashboardView(hass))
        hass.http.register_view(LatterCompanionApiView(hass))
        hass.http.register_view(LatterBrandIconView(hass))

    coordinator = LatterCoordinator(
        hass=hass,
        entry=entry,
        hmac_secret=domain_data[DATA_HMAC_SECRET],
    )
    await coordinator.async_setup()
    entry.runtime_data = coordinator
    domain_data[entry.entry_id] = coordinator

    inject_esphome_visit_link(
        hass, coordinator.device_slug, coordinator.build_companion_url()
    )
    inject_hacs_update_brand_icon(hass)

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

        @callback
        def _on_update_entity_state_changed(event: Event) -> None:
            ent_id = str(event.data.get("entity_id") or "")
            if ent_id.startswith("update."):
                new_st = event.data.get("new_state")
                if new_st is not None:
                    friendly = str(new_st.attributes.get("friendly_name") or "").lower()
                    if "latter" in ent_id.lower() or "latter" in friendly:
                        pic = str(new_st.attributes.get("entity_picture") or "")
                        if pic != "/api/latter/brand/icon.png":
                            inject_hacs_update_brand_icon(hass)

        unsub_dev = hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, _on_device_registry_updated
        )
        unsub_upd = hass.bus.async_listen(
            EVENT_STATE_CHANGED, _on_update_entity_state_changed
        )
        domain_data[DATA_DISCOVERY_UNSUB] = (unsub_dev, unsub_upd)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass)

    coordinator._notify_listeners()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _LOGGER.info(
        "Latter v%s initialized for ESPHome device '%s' (active_speaker: %s, companion_url: %s)",
        INTEGRATION_VERSION,
        coordinator.device_slug,
        coordinator.active_speaker,
        coordinator.build_companion_url(),
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: LatterConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> bool:
    """Unload a Latter config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: LatterCoordinator | None = hass.data[DOMAIN].pop(
            entry.entry_id, None
        )
        if coordinator is not None:
            await coordinator.async_shutdown()
    return unload_ok