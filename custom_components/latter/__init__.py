"""The Latter integration: Home Assistant middleware for Latter displays."""

from __future__ import annotations

import logging
import secrets
import time
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    SOURCE_INTEGRATION_DISCOVERY,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_SERVICE_REGISTERED,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery_flow,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .ble_engine import _iter_devices
from .const import (
    CONF_ESPHOME_DEVICE_ID,
    DATA_DISCOVERY_UNSUB,
    DEVICE_SUBENTRY_TYPES,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DATA_HMAC_SECRET,
    DOMAIN,
    GLOBAL_STORAGE_KEY,
    INTEGRATION_VERSION,
    PLATFORMS,
    STORAGE_VERSION,
)
from .coordinator import LatterCoordinator
from .doorbell_engine import LatterCameraAudioStreamView
from .http import (
    LatterArtworkTranscoderView,
    LatterCameraSnapshotView,
    LatterMapSnapshotView,
    LatterWallpaperProxyView,
)
from .config_flow import _device_unique_id
from .device_ping import async_ping_bound_devices
from .identity import (
    LATTER_CONTRACT_ACTION_SUFFIXES,
    esphome_service,
    is_esphome_device,
    is_latter_compatible_esphome_device,
)
from .media_engine import clear_ma_counterpart_cache
from .repairs import async_delete_device_issues
from .services import async_push_active_area_entities, async_setup_services
from .studio import (
    LatterBrandIconView,
    async_register_studio_panel,
    async_unregister_studio_panel,
)
from .system import LatterSystem, get_latter_system

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type LatterConfigEntry = ConfigEntry[LatterSystem]


async def _async_ensure_global_store(hass: HomeAssistant) -> dict[str, Any]:
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

    if changed:
        await domain_data[DATA_GLOBAL_STORE].async_save(global_cfg)

    get_latter_system(hass)
    return global_cfg


@callback
def _async_scan_all_esphome_devices_for_discovery(hass: HomeAssistant) -> None:
    """Self-heal crashed flows, abort stale discovery flows, and discover Latter-compatible ESPHome devices."""
    dev_reg = dr.async_get(hass)
    esphome_devices = [d for d in _iter_devices(dev_reg) if is_esphome_device(hass, d)]
    devices_by_uid = {_device_unique_id(d): d for d in esphome_devices}

    # 1. Clean up only crashed flows (step_id is None) or discovery flows whose device no longer qualifies
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
        dev = devices_by_uid.get(str(ctx.get("unique_id") or ""))
        if dev is None or not is_latter_compatible_esphome_device(hass, dev):
            hass.config_entries.flow.async_abort(fid)

    # 2. Trigger discovery for any unconfigured Latter-compatible ESPHome devices
    for dev in esphome_devices:
        _async_check_esphome_device_for_discovery(hass, dev)


@callback
def _async_check_esphome_device_for_discovery(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> None:
    """Trigger a Latter discovery flow ONLY if no Latter hub entry exists yet and the ESPHome device implements the Latter contract."""
    if hass.config_entries.async_entries(DOMAIN):
        return
    if not is_esphome_device(hass, device):
        return
    if not is_latter_compatible_esphome_device(hass, device):
        return
    discovery_flow.async_create_flow(
        hass,
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_ESPHOME_DEVICE_ID: device.id},
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Latter domain, register services, and scan for Latter-compatible ESPHome devices."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    await _async_ensure_global_store(hass)
    await async_setup_services(hass)

    @callback
    def _schedule_debounced_discovery_scan(delay_s: float = 2.0) -> None:
        prev_timer = domain_data.pop("_unsub_delayed_scan", None)
        if callable(prev_timer):
            prev_timer()

        @callback
        def _delayed_scan(_now: Any) -> None:
            domain_data.pop("_unsub_delayed_scan", None)
            _async_scan_all_esphome_devices_for_discovery(hass)

        domain_data["_unsub_delayed_scan"] = async_call_later(
            hass, delay_s, _delayed_scan
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
                _schedule_debounced_discovery_scan(5.0)

        @callback
        def _on_service_registered(event: Event) -> None:
            if event.data.get("domain") != "esphome":
                return
            svc = str(event.data.get("service") or "")
            if any(svc.endswith(sfx) for sfx in LATTER_CONTRACT_ACTION_SUFFIXES):
                _schedule_debounced_discovery_scan(1.0)

        unsub_dev = hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, _on_device_registry_updated
        )
        unsub_svc = hass.bus.async_listen(
            EVENT_SERVICE_REGISTERED, _on_service_registered
        )
        domain_data[DATA_DISCOVERY_UNSUB] = (unsub_dev, unsub_svc)

    @callback
    def _on_ha_started(_ev: Event) -> None:
        _async_scan_all_esphome_devices_for_discovery(hass)

    if hass.is_running:
        _async_scan_all_esphome_devices_for_discovery(hass)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_ha_started)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> bool:
    """Set up the Latter System hub entry and all configured Device subentries."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    await _async_ensure_global_store(hass)
    sys_obj = get_latter_system(hass)
    if sys_obj is None:
        return False

    if "views_registered" not in domain_data:
        domain_data["views_registered"] = True
        hass.http.register_view(LatterArtworkTranscoderView(hass))
        hass.http.register_view(LatterWallpaperProxyView(hass))
        hass.http.register_view(LatterCameraSnapshotView(hass))
        hass.http.register_view(LatterCameraAudioStreamView(hass))
        hass.http.register_view(LatterMapSnapshotView(hass))
        hass.http.register_view(LatterBrandIconView(hass))

    await async_register_studio_panel(hass)

    # Register the System-level service device for Site & Area entities
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "system")},
        entry_type=dr.DeviceEntryType.SERVICE,
        name="Latter System",
        manufacturer="Lampton Labs",
        model="Latter Site & BLE Fabric Engine",
        sw_version=INTEGRATION_VERSION,
        configuration_url="homeassistant://latter",
    )

    entry.runtime_data = sys_obj
    sys_obj.bind_feed_listeners()

    device_subentries = [
        sub
        for sub in entry.subentries.values()
        if sub.subentry_type in DEVICE_SUBENTRY_TYPES
    ]
    for sub in device_subentries:
        coordinator = LatterCoordinator(
            hass=hass,
            entry=entry,
            hmac_secret=domain_data[DATA_HMAC_SECRET],
            subentry=sub,
        )
        coordinator.on_area_changed_push_slots = (
            lambda c: async_push_active_area_entities(hass, c)
        )
        await coordinator.async_setup()
        domain_data[coordinator.subentry_id] = coordinator
        sys_obj.coordinators[coordinator.subentry_id] = coordinator
        _LOGGER.info(
            "Latter v%s initialized device subentry '%s' (%s, active_speaker: %s)",
            INTEGRATION_VERSION,
            coordinator.device_slug,
            coordinator.subentry_id,
            coordinator.active_speaker,
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    for coordinator in list(sys_obj.coordinators.values()):
        coordinator.async_notify_listeners()

    # Services are registered (async_setup) and the coordinators exist: ask every bound Device for a
    # fresh device_hello, in case it sent one while Home Assistant was still starting.
    entry.async_create_background_task(
        hass, _async_ping_bound_devices(hass, sys_obj), name="latter_ping_bound_devices"
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_ping_bound_devices(hass: HomeAssistant, sys_obj: LatterSystem) -> None:
    """Call each bound Device's latter_ping action; the firmware answers with latter.device_hello."""

    async def _call(service: str) -> None:
        await hass.services.async_call("esphome", service, {}, blocking=True)

    pinged = await async_ping_bound_devices(
        [coord.esphome_device_id for coord in list(sys_obj.coordinators.values())],
        lambda dev_id, action: esphome_service(hass, dev_id, action),
        _call,
        lambda service, err: _LOGGER.debug("esphome.%s failed: %s", service, err),
    )
    if pinged:
        _LOGGER.debug("Asked %d Device(s) to resend latter.device_hello", len(pinged))


async def _async_update_listener(hass: HomeAssistant, entry: LatterConfigEntry) -> None:
    """Reload when device subentries are added/removed or structural keys change; otherwise apply options in-place."""
    sys_obj: LatterSystem = entry.runtime_data
    current_sub_ids = {
        sub.subentry_id
        for sub in entry.subentries.values()
        if sub.subentry_type in DEVICE_SUBENTRY_TYPES
    }
    loaded_sub_ids = set(sys_obj.coordinators.keys())
    if current_sub_ids != loaded_sub_ids:
        for removed_id in loaded_sub_ids - current_sub_ids:
            async_delete_device_issues(hass, removed_id)
        hass.config_entries.async_schedule_reload(entry.entry_id)
        return

    for coord in list(sys_obj.coordinators.values()):
        live_sub = entry.subentries.get(coord.subentry_id)
        if live_sub is not None:
            coord.subentry = live_sub
        if coord.has_structural_changes():
            hass.config_entries.async_schedule_reload(entry.entry_id)
            return

    for coord in list(sys_obj.coordinators.values()):
        await coord.async_apply_options()


async def async_unload_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> bool:
    """Unload the Latter System hub entry and all its device subentry coordinators."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        clear_ma_counterpart_cache(hass)
        domain_data = hass.data.get(DOMAIN, {})
        sys_obj = get_latter_system(hass)
        if sys_obj is not None:
            sys_obj.async_cleanup_feeds()
            for sub_id, coord in list(sys_obj.coordinators.items()):
                if coord.entry.entry_id == entry.entry_id:
                    sys_obj.coordinators.pop(sub_id, None)
                    domain_data.pop(sub_id, None)
                    coord.async_cleanup()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> None:
    """Unregister Studio panel and re-trigger discovery scan when the Latter System entry is removed."""
    async_unregister_studio_panel(hass)
    _async_scan_all_esphome_devices_for_discovery(hass)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: LatterConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow users to remove stale device entries from the Home Assistant Device Registry."""
    return True
