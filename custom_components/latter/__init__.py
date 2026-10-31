"""The Latter (Universal ESPHome Companion & Entity Middleware) integration."""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry, SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_SERVICE_REGISTERED,
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
    CONF_ESPHOME_DEVICE_ID,
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
    normalize_device_slug,
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
from .services import async_push_active_area_entities, async_setup_services

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
    val = normalize_device_slug(name)
    return "" if val == "esphome_device" and name.strip().lower() != "esphome_device" else val


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
    """Load or initialize the shared Site configuration store (`.storage/latter.site`)."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if DATA_GLOBAL_STORE not in domain_data:
        store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, GLOBAL_STORAGE_KEY
        )
        domain_data[DATA_GLOBAL_STORE] = store
        loaded = await store.async_load()
        domain_data[DATA_GLOBAL_CONFIG] = dict(loaded) if isinstance(loaded, dict) else {}

    global_cfg: dict[str, Any] = domain_data[DATA_GLOBAL_CONFIG]
    changed = False
    secret_hex = str(global_cfg.get("hmac_secret_hex") or "").strip()
    if len(secret_hex) != 64:
        secret_hex = secrets.token_hex(32)
        global_cfg["hmac_secret_hex"] = secret_hex
        changed = True
    try:
        domain_data[DATA_HMAC_SECRET] = bytes.fromhex(secret_hex)
    except ValueError:
        secret_hex = secrets.token_hex(32)
        global_cfg["hmac_secret_hex"] = secret_hex
        domain_data[DATA_HMAC_SECRET] = bytes.fromhex(secret_hex)
        changed = True

    if seed_entry is not None:
        merged_entry = {**seed_entry.data, **(seed_entry.options or {})}
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
    devices_by_uid: dict[str, tuple[dr.DeviceEntry, str]] = {}
    for dev in _iter_devices(dev_reg):
        dev_name = str(dev.name_by_user or dev.name or "").strip()
        if dev_name:
            slug = _slugify_device_name(dev_name)
            if slug:
                devices_by_uid[f"{DOMAIN}_{slug}"] = (dev, slug)
                for _ctype, cval in dev.connections:
                    if cval:
                        devices_by_uid[f"{DOMAIN}_{dr.format_mac(str(cval))}"] = (dev, slug)

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
        if not unique_id.startswith(f"{DOMAIN}_"):
            continue
        pair = devices_by_uid.get(unique_id)
        if pair is None or not is_latter_compatible_esphome_device(hass, pair[0], pair[1]):
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

    mac_uid = ""
    for _ctype, cval in device.connections:
        if cval:
            mac_uid = f"{DOMAIN}_{dr.format_mac(str(cval))}"
            break

    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.unique_id in (f"{DOMAIN}_{slug}", mac_uid) and entry.unique_id:
            return
        if entry.data.get(CONF_ESPHOME_DEVICE_ID) == device.id:
            return
        if normalize_device_slug(str(entry.data.get(CONF_DEVICE_SLUG, ""))) == slug:
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

    if "views_registered" not in domain_data:
        domain_data["views_registered"] = True
        hass.http.register_view(LatterArtworkTranscoderView(hass))
        hass.http.register_view(LatterWallpaperProxyView(hass))
        hass.http.register_view(LatterRotatableCameraSnapshotView(hass))
        hass.http.register_view(LatterCameraAudioStreamView(hass))
        hass.http.register_view(LatterDoorbellTalkbackView(hass))
        hass.http.register_view(LatterMapSnapshotView(hass))
        hass.http.register_view(LatterCompanionDashboardView(hass))
        hass.http.register_view(LatterCompanionApiView(hass))
        hass.http.register_view(LatterBrandIconView(hass))
        hass.http.register_view(LatterStudioRootView(hass))
        hass.http.register_view(LatterSidebarIconJsView(hass))
        try:
            from homeassistant.components import frontend
            frontend.add_extra_js_url(hass, "/api/latter/brand/sidebar_icon.js")
            panel_token = get_studio_panel_token(hass)
            frontend.async_register_built_in_panel(
                hass,
                component_name="iframe",
                sidebar_title="Latter",
                sidebar_icon="latter:logo",
                frontend_url_path="latter",
                config={"url": f"/api/latter/studio?scope=system&token={panel_token}"},
                require_admin=True,
                update=True,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Sidebar panel registration skipped: %s", err)

    await get_sip_engine(hass).async_start_or_reload()

    coordinator = LatterCoordinator(
        hass=hass,
        entry=entry,
        hmac_secret=domain_data[DATA_HMAC_SECRET],
    )
    coordinator.on_area_changed_push_slots = (
        lambda c: async_push_active_area_entities(hass, c)
    )
    await coordinator.async_setup()
    entry.runtime_data = coordinator
    domain_data[entry.entry_id] = coordinator

    clean_title = coordinator.device_slug.replace("_", " ").title()
    if entry.title.lower().startswith("latter (") or entry.title != clean_title:
        hass.config_entries.async_update_entry(entry, title=clean_title)

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
            own_writes = domain_data.get("_own_area_writes")
            if isinstance(own_writes, dict) and dev_id in own_writes:
                expected_area, write_ts = own_writes[dev_id]
                if (
                    (time.monotonic() - float(write_ts)) < 2.0
                    and dev is not None
                    and dev.area_id == expected_area
                ):
                    own_writes.pop(dev_id, None)
                    return
            if dev is not None:
                _async_check_esphome_device_for_discovery(hass, dev)

                prev_timer = domain_data.pop("_unsub_delayed_scan", None)
                if callable(prev_timer):
                    prev_timer()

                @callback
                def _delayed_scan(_now: Any) -> None:
                    domain_data.pop("_unsub_delayed_scan", None)
                    _async_scan_all_esphome_devices_for_discovery(hass)

                domain_data["_unsub_delayed_scan"] = async_call_later(
                    hass, 5.0, _delayed_scan
                )

        @callback
        def _on_service_registered(event: Event) -> None:
            if event.data.get("domain") != "esphome":
                return
            svc = str(event.data.get("service") or "")
            if any(svc.endswith(sfx) for sfx in LATTER_CONTRACT_ACTION_SUFFIXES):
                _async_scan_all_esphome_devices_for_discovery(hass)

        unsub_dev = hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, _on_device_registry_updated
        )
        unsub_svc = hass.bus.async_listen(
            EVENT_SERVICE_REGISTERED, _on_service_registered
        )
        domain_data[DATA_DISCOVERY_UNSUB] = (unsub_dev, unsub_svc)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    coordinator.async_notify_listeners()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _LOGGER.info(
        "Latter v%s initialized for ESPHome device '%s' (active_speaker: %s)",
        INTEGRATION_VERSION,
        coordinator.device_slug,
        coordinator.active_speaker,
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: LatterConfigEntry) -> None:
    """Apply updated options in-place, or schedule a config entry reload if structural keys changed."""
    coordinator: LatterCoordinator | None = getattr(
        entry, "runtime_data", None
    ) or hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator is None or coordinator.has_structural_changes():
        hass.config_entries.async_schedule_reload(entry.entry_id)
        return
    await coordinator.async_apply_options()


async def async_unload_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> bool:
    """Unload a Latter config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: LatterCoordinator | None = hass.data[DOMAIN].pop(
            entry.entry_id, None
        )
        if coordinator is not None:
            coordinator.async_cleanup()
        remaining = [
            v for v in hass.data.get(DOMAIN, {}).values() if isinstance(v, LatterCoordinator)
        ]
        if not remaining:
            delayed_unsub = hass.data.get(DOMAIN, {}).pop("_unsub_delayed_scan", None)
            if callable(delayed_unsub):
                delayed_unsub()
            for unsub in hass.data.get(DOMAIN, {}).pop(DATA_DISCOVERY_UNSUB, ()):
                unsub()
            if "sip_engine" in hass.data.get(DOMAIN, {}):
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