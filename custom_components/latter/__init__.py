"""The Latter (Universal ESPHome Companion & Entity Middleware) integration."""

from __future__ import annotations

import logging
import re
import secrets
from typing import Any

from homeassistant.config_entries import ConfigEntry, SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_SERVICE_REGISTERED,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery_flow,
    entity_registry as er,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .ble_engine import _iter_devices
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
    LatterSidebarIconJsView,
    LatterStudioRootView,
    get_studio_panel_token,
)
from .doorbell_engine import (
    LatterCameraAudioStreamView,
    LatterDoorbellTalkbackView,
    LatterRotatableCameraSnapshotView,
)
from .http import (
    LatterArtworkTranscoderView,
    LatterMapSnapshotView,
    LatterWallpaperProxyView,
)
from .sip_engine import get_sip_engine
from .area_engine import inject_esphome_visit_link, inject_hacs_update_brand_icon
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type LatterConfigEntry = ConfigEntry[LatterCoordinator]

LATTER_CONTRACT_ACTION_SUFFIXES: tuple[str, ...] = (
    "_set_browse_slots",
    "_set_area_slots",
    "_show_notification",
    "_latter_ping",
)


def _slugify_device_name(name: str) -> str:
    """Convert an ESPHome device name into a normalized slug."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def is_latter_compatible_esphome_device(
    hass: HomeAssistant, device: dr.DeviceEntry, slug: str
) -> bool:
    """Return True ONLY if the ESPHome device implements the Latter API contract or Latter project namespace."""
    # 1. Check registered ESPHome API contract actions (_set_browse_slots, _set_area_slots, _show_notification, _latter_ping)
    esphome_services = hass.services.async_services().get("esphome", {})
    for suffix in LATTER_CONTRACT_ACTION_SUFFIXES:
        exact = f"{slug}{suffix}"
        if exact in esphome_services:
            return True
        for svc_name in esphome_services:
            if svc_name.endswith(suffix) and slug in svc_name:
                return True

    # 2. Check ESPHome project namespace or Latter OTA update entity
    model_str = f"{device.model or ''} {device.sw_version or ''}".lower()
    if "latter" in model_str or hass.states.get(f"update.{slug}_project_firmware") is not None:
        return True

    return False


async def _async_ensure_global_store(
    hass: HomeAssistant, seed_entry: ConfigEntry | None = None
) -> dict[str, Any]:
    """Load or initialize the shared Site configuration store (`.storage/latter.site`), migrating legacy `.storage/latter.household` if present."""
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
def _async_scan_all_esphome_devices_for_discovery(hass: HomeAssistant) -> None:
    """Self-heal crashed flows, abort non-Latter discovery flows, and discover Latter-compatible ESPHome devices."""
    dev_reg = dr.async_get(hass)
    devices_by_slug: dict[str, dr.DeviceEntry] = {}
    for dev in _iter_devices(dev_reg):
        dev_name = str(dev.name_by_user or dev.name or "").strip()
        if dev_name:
            devices_by_slug[_slugify_device_name(dev_name)] = dev

    # 1. Clean up only crashed flows (step_id is None) or unsupported discovery flows
    for flow in list(hass.config_entries.flow.async_progress_by_handler(DOMAIN)):
        fid = flow.get("flow_id")
        if not fid:
            continue
        if flow.get("step_id") is None:
            hass.config_entries.flow.async_abort(fid)
            continue
        ctx = flow.get("context", {})
        if ctx.get("source") != SOURCE_INTEGRATION_DISCOVERY:
            continue
        unique_id = str(ctx.get("unique_id") or "")
        flow_slug = unique_id.removeprefix(f"{DOMAIN}_") if unique_id.startswith(f"{DOMAIN}_") else ""
        if not flow_slug:
            continue
        dev = devices_by_slug.get(flow_slug)
        if dev is None or not is_latter_compatible_esphome_device(hass, dev, flow_slug):
            hass.config_entries.flow.async_abort(fid)

    # 2. Trigger discovery for any unconfigured Latter-compatible ESPHome devices
    for dev in _iter_devices(dev_reg):
        _async_check_esphome_device_for_discovery(hass, dev)


@callback
def _async_check_esphome_device_for_discovery(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> None:
    """Trigger a Latter discovery flow ONLY if the ESPHome device implements the Latter contract."""
    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_device(ent_reg, device.id)
    if not any(e.platform == "esphome" for e in entries):
        return

    dev_name = str(device.name_by_user or device.name or "").strip()
    if not dev_name:
        return

    slug = _slugify_device_name(dev_name)
    if not slug:
        return

    if not is_latter_compatible_esphome_device(hass, device, slug):
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
    """Set up the Latter domain, register services, and scan for Latter-compatible ESPHome devices."""
    hass.data.setdefault(DOMAIN, {})
    await _async_ensure_global_store(hass)
    await async_setup_services(hass)
    @callback
    def _on_ha_started(_ev: Event) -> None:
        _async_scan_all_esphome_devices_for_discovery(hass)

    if hass.is_running:
        _async_scan_all_esphome_devices_for_discovery(hass)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_ha_started)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> bool:
    """Set up Latter from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    await _async_ensure_global_store(hass, seed_entry=entry)

    if DATA_HMAC_SECRET not in domain_data:
        domain_data[DATA_HMAC_SECRET] = secrets.token_bytes(32)
        hass.http.register_view(LatterArtworkTranscoderView(hass))
        hass.http.register_view(LatterWallpaperProxyView(hass))
        hass.http.register_view(LatterRotatableCameraSnapshotView(hass))
        hass.http.register_view(LatterCameraAudioStreamView(hass))
        hass.http.register_view(LatterDoorbellTalkbackView(hass))
        hass.http.register_view(LatterMapSnapshotView(hass))
        await get_sip_engine(hass).async_start_or_reload()
        hass.http.register_view(LatterCompanionDashboardView(hass))
        hass.http.register_view(LatterCompanionApiView(hass))
        hass.http.register_view(LatterBrandIconView(hass))
        hass.http.register_view(LatterStudioRootView(hass))
        hass.http.register_view(LatterSidebarIconJsView(hass))
        try:
            from homeassistant.components import frontend
            frontend.add_extra_js_url(hass, "/api/latter/brand/sidebar_icon.js")
            panel_token = get_studio_panel_token(domain_data[DATA_HMAC_SECRET])
            frontend.async_register_built_in_panel(
                hass,
                component_name="iframe",
                sidebar_title="Latter",
                sidebar_icon="latter:logo",
                frontend_url_path="latter",
                config={"url": f"/api/latter/studio?scope=system&token={panel_token}"},
                require_admin=False,
                update=True,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Sidebar panel registration skipped: %s", err)

    coordinator = LatterCoordinator(
        hass=hass,
        entry=entry,
        hmac_secret=domain_data[DATA_HMAC_SECRET],
    )
    await coordinator.async_setup()
    entry.runtime_data = coordinator
    domain_data[entry.entry_id] = coordinator

    clean_title = coordinator.device_slug.replace("_", " ").title()
    if entry.title.lower().startswith("latter (") or entry.title != clean_title:
        hass.config_entries.async_update_entry(entry, title=clean_title)

    inject_esphome_visit_link(
        hass, coordinator.device_slug, coordinator.build_companion_url()
    )
    inject_hacs_update_brand_icon(hass)
    hass.loop.call_soon(_async_scan_all_esphome_devices_for_discovery, hass)

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
                dev_name = str(dev.name_by_user or dev.name or "").strip()
                if dev_name:
                    upd_slug = _slugify_device_name(dev_name)
                    for val in domain_data.values():
                        if isinstance(val, LatterCoordinator) and val.device_slug == upd_slug:
                            inject_esphome_visit_link(
                                hass, val.device_slug, val.build_companion_url()
                            )

                @callback
                def _delayed_scan(_now: Any) -> None:
                    _async_scan_all_esphome_devices_for_discovery(hass)

                async_call_later(hass, 5.0, _delayed_scan)

        @callback
        def _on_service_registered(event: Event) -> None:
            if event.data.get("domain") != "esphome":
                return
            svc = str(event.data.get("service") or "")
            if any(svc.endswith(sfx) for sfx in LATTER_CONTRACT_ACTION_SUFFIXES):
                _async_scan_all_esphome_devices_for_discovery(hass)

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
        unsub_svc = hass.bus.async_listen(
            EVENT_SERVICE_REGISTERED, _on_service_registered
        )
        unsub_upd = hass.bus.async_listen(
            EVENT_STATE_CHANGED, _on_update_entity_state_changed
        )
        domain_data[DATA_DISCOVERY_UNSUB] = (unsub_dev, unsub_svc, unsub_upd)

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
        remaining = [
            v for v in hass.data.get(DOMAIN, {}).values() if isinstance(v, LatterCoordinator)
        ]
        if not remaining and "sip_engine" in hass.data.get(DOMAIN, {}):
            hass.data[DOMAIN]["sip_engine"].async_stop()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> None:
    """Re-trigger discovery scan when a device entry is removed so it can be re-added in 1 click."""
    _async_scan_all_esphome_devices_for_discovery(hass)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: LatterConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow users to remove stale device entries from the Home Assistant Device Registry."""
    return True