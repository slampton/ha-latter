"""The Latter integration: Home Assistant middleware for Latter displays."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
import logging
import secrets
import time
from typing import Any
import uuid

from homeassistant.config_entries import (
    SOURCE_INTEGRATION_DISCOVERY,
    ConfigEntry,
)
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
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

from .config_defaults import (
    BUILTIN_GROUP_PRESET_VERSION,
    CONF_BUILTIN_GROUP_PRESET_VERSION,
)
from .const import (
    CONF_ESPHOME_DEVICE_ID,
    CONF_SYSTEM_BLE_UUID,
    DATA_DISCOVERY_UNSUB,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DATA_HMAC_SECRET,
    DEFAULT_BLE_BEACON_UUID,
    DEVICE_SUBENTRY_TYPES,
    DOMAIN,
    GLOBAL_STORAGE_KEY,
    INTEGRATION_VERSION,
    PLATFORMS,
    STORAGE_VERSION,
)
from .coordinator import LatterCoordinator, register_rpc_receiver_factory
from .groups.device_groups import (
    async_sync_coordinators_to_builtin_presets,
    upgrade_stored_builtin_groups,
)
from .http.camera_views import (
    LatterCameraAudioStreamView,
    LatterCameraGridView,
    LatterCameraSnapshotView,
    LatterCameraStreamView,
    async_shutdown_camera_feeds,
    async_shutdown_doorbell_streams,
)
from .http.proxy_views import LatterArtworkTranscoderView, LatterBrandIconView
from .http.signing import register_crop_hash_resolver
from .http.wallpaper_views import LatterWallpaperProxyView, LatterWallpaperUploadView
from .hub_registry import (
    LatterSystemHub,
    async_stop_area_state_index,
    get_area_state_index,
    get_latter_system,
    get_system_config_lock,
    iter_coordinators,
    register_hub_hooks,
)
from .hub_sync import attach_hub_sync_methods
from .identity import (
    LATTER_CONTRACT_ACTION_SUFFIXES,
    device_unique_id,
    esphome_service,
    get_ignored_discovered_device_ids,
    is_esphome_device,
    is_latter_compatible_esphome_device,
    iter_devices,
)
from .media.browse import clear_browse_cache
from .media.linking import async_heal_coordinator_ma_links, clear_ma_counterpart_cache
from .protocol_specs import warm_timezone_cache
from .repairs import async_delete_device_issues
from .services.public_actions import async_setup_services, async_unload_services
from .services.rpc_dispatcher import LatterRpcDispatcher
from .services.rpc_receiver import LatterRpcReceiver
from .services.rpc_slots import async_push_active_area_entities
from .studio.panel import (
    async_register_studio_icon_module,
    async_register_studio_panel,
    async_unregister_studio_panel,
)
from .wallpapers.store import async_refresh_wallpaper_cache, get_photo_crop_hash

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type LatterRuntimeData = LatterSystemHub
type LatterConfigEntry = ConfigEntry[LatterRuntimeData]

PING_ACTION = "latter_ping"
_SECRET_HEX_LEN = 64
_OWN_WRITE_SUPPRESS_S = 2.0

register_crop_hash_resolver(get_photo_crop_hash)
register_hub_hooks(rpc_dispatcher_factory=LatterRpcDispatcher)
register_rpc_receiver_factory(LatterRpcReceiver)


@callback
def async_register_http_views(hass: HomeAssistant) -> None:
    """Register all 8 local-only signed/admin HTTP views once on `hass.http`."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("views_registered"):
        return
    domain_data["views_registered"] = True
    hass.http.register_view(LatterArtworkTranscoderView(hass))
    hass.http.register_view(LatterWallpaperProxyView(hass))
    hass.http.register_view(LatterWallpaperUploadView(hass))
    hass.http.register_view(LatterCameraSnapshotView(hass))
    hass.http.register_view(LatterCameraStreamView(hass))
    hass.http.register_view(LatterCameraGridView(hass))
    hass.http.register_view(LatterCameraAudioStreamView(hass))
    hass.http.register_view(LatterBrandIconView(hass))


async def async_ping_bound_devices(
    esphome_device_ids: Iterable[str | None],
    resolve_service: Callable[[str, str], str | None],
    call_service: Callable[[str], Awaitable[None]],
    on_error: Callable[[str, Exception], None] | None = None,
) -> list[str]:
    """Call `latter_ping` on every bound Device whose ESPHome action is registered."""
    pinged: list[str] = []
    seen: set[str] = set()
    for dev_id in esphome_device_ids:
        if not dev_id or dev_id in seen:
            continue
        seen.add(dev_id)
        service = resolve_service(dev_id, PING_ACTION)
        if not service:
            continue
        try:
            await call_service(service)
        except Exception as err:  # noqa: BLE001
            if on_error is not None:
                on_error(service, err)
            continue
        pinged.append(service)
    return pinged


async def _async_ensure_global_store(hass: HomeAssistant) -> dict[str, Any]:
    """Load or initialize the shared Site configuration store (`.storage/latter.site`)."""
    async with get_system_config_lock(hass):
        domain_data = hass.data.setdefault(DOMAIN, {})
        had_existing_store = bool(
            DATA_GLOBAL_STORE in domain_data and domain_data.get(DATA_GLOBAL_CONFIG)
        )
        if DATA_GLOBAL_STORE not in domain_data:
            store: Store[dict[str, Any]] = Store(
                hass, STORAGE_VERSION, GLOBAL_STORAGE_KEY
            )
            domain_data[DATA_GLOBAL_STORE] = store
            loaded = await store.async_load()
            had_existing_store = isinstance(loaded, dict) and bool(loaded)
            domain_data[DATA_GLOBAL_CONFIG] = (
                dict(loaded) if isinstance(loaded, dict) else {}
            )

        global_cfg: dict[str, Any] = domain_data[DATA_GLOBAL_CONFIG]
        changed = False
        if global_cfg.get(CONF_BUILTIN_GROUP_PRESET_VERSION) != BUILTIN_GROUP_PRESET_VERSION:
            if had_existing_store:
                upgrade_stored_builtin_groups(global_cfg)
                domain_data["_pending_builtin_group_preset_upgrade"] = True
            else:
                global_cfg[CONF_BUILTIN_GROUP_PRESET_VERSION] = BUILTIN_GROUP_PRESET_VERSION
            changed = True
        secret_hex = str(global_cfg.get("hmac_secret_hex") or "").strip()
        if len(secret_hex) != _SECRET_HEX_LEN:
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

        sys_ble_uuid = str(global_cfg.get(CONF_SYSTEM_BLE_UUID) or "").strip().upper()
        try:
            parsed_uuid = uuid.UUID(sys_ble_uuid) if sys_ble_uuid else None
        except ValueError:
            parsed_uuid = None
        if parsed_uuid is None or str(parsed_uuid).upper() == DEFAULT_BLE_BEACON_UUID:
            sys_ble_uuid = str(uuid.UUID(bytes=secrets.token_bytes(16), version=4)).upper()
            global_cfg[CONF_SYSTEM_BLE_UUID] = sys_ble_uuid
            changed = True

        if changed:
            await domain_data[DATA_GLOBAL_STORE].async_save(global_cfg)

    sys_obj = get_latter_system(hass)
    if sys_obj is not None:
        attach_hub_sync_methods(sys_obj)
    return global_cfg


@callback
def _async_scan_all_esphome_devices_for_discovery(hass: HomeAssistant) -> None:
    """Self-heal crashed flows, abort stale discovery flows, and discover Latter-compatible ESPHome devices."""
    dev_reg = dr.async_get(hass)
    esphome_devices = [d for d in iter_devices(dev_reg) if is_esphome_device(hass, d)]
    devices_by_uid = {device_unique_id(d): d for d in esphome_devices}

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

    for dev in esphome_devices:
        _async_check_esphome_device_for_discovery(hass, dev)


@callback
def _async_check_esphome_device_for_discovery(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> None:
    """Trigger a Latter discovery flow ONLY if no Latter hub entry exists yet and the ESPHome device implements the Latter contract."""
    if hass.config_entries.async_entries(DOMAIN):
        return
    if device.id in get_ignored_discovered_device_ids(hass):
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


@callback
def _handle_device_registry_update_for_coordinators(
    hass: HomeAssistant, dev: dr.DeviceEntry, event_data: Any
) -> None:
    changes = event_data.get("changes")
    area_changed = not isinstance(changes, dict) or "area_id" in changes
    name_changed = (
        not isinstance(changes, dict)
        or "name" in changes
        or "name_by_user" in changes
    )
    if not area_changed and not name_changed:
        return
    new_area = str(dev.area_id or "").strip()
    for coord in iter_coordinators(hass):
        if coord.is_ble_tag:
            continue
        if name_changed and dev.id == coord.esphome_device_id:
            coord.async_sync_ha_device_name()
        if area_changed and (
            dev.id == coord.esphome_device_id
            or bool(dev.identifiers & coord.get_device_info()["identifiers"])
            or (
                coord.esphome_device_id
                and dev.via_device_id == coord.esphome_device_id
            )
        ):
            coord.async_on_ha_device_area_updated(dev.id, new_area)


@callback
def _register_domain_bus_listeners(
    hass: HomeAssistant,
    domain_data: dict[str, Any],
    schedule_scan: Callable[[float], None],
) -> None:
    if DATA_DISCOVERY_UNSUB in domain_data:
        return

    @callback
    def _on_device_registry_updated(event: Event[Any]) -> None:
        action = event.data.get("action")
        dev_id = event.data.get("device_id")
        if action not in ("create", "update") or not dev_id:
            return
        got_dev = dr.async_get(hass).async_get(dev_id)
        dev = got_dev if isinstance(got_dev, dr.DeviceEntry) else None
        own_writes = domain_data.get("_own_area_writes")
        if isinstance(own_writes, dict) and dev_id in own_writes:
            expected_area, write_ts = own_writes[dev_id]
            cur_area = str(dev.area_id or "").strip() if dev is not None else ""
            if (
                (time.monotonic() - float(write_ts)) < _OWN_WRITE_SUPPRESS_S
                and dev is not None
                and cur_area == str(expected_area or "").strip()
            ):
                own_writes.pop(dev_id, None)
                for coord in iter_coordinators(hass):
                    coord.async_record_own_area_write(dev_id, cur_area)
                return
        if dev is None:
            return
        _async_check_esphome_device_for_discovery(hass, dev)
        schedule_scan(5.0)
        if action == "update":
            _handle_device_registry_update_for_coordinators(hass, dev, event.data)

    @callback
    def _on_entity_registry_updated(event: Event[Any]) -> None:
        if event.data.get("action") != "update":
            return
        old_entity_id = str(event.data.get("old_entity_id") or "").strip()
        new_entity_id = str(event.data.get("entity_id") or "").strip()
        if not old_entity_id or not new_entity_id or old_entity_id == new_entity_id:
            return
        ent_entry = er.async_get(hass).async_get(new_entity_id)
        ent_dev_id = ent_entry.device_id if ent_entry is not None else None
        for coord in iter_coordinators(hass):
            coord.async_on_ha_entity_renamed(old_entity_id, new_entity_id, ent_dev_id)

    @callback
    def _on_service_registered(event: Event[Any]) -> None:
        if event.data.get("domain") != "esphome":
            return
        svc = str(event.data.get("service") or "")
        if any(svc.endswith(sfx) for sfx in LATTER_CONTRACT_ACTION_SUFFIXES):
            schedule_scan(1.0)

    domain_data[DATA_DISCOVERY_UNSUB] = (
        hass.bus.async_listen(
            dr.EVENT_DEVICE_REGISTRY_UPDATED, _on_device_registry_updated
        ),
        hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, _on_entity_registry_updated
        ),
        hass.bus.async_listen(EVENT_SERVICE_REGISTERED, _on_service_registered),
    )


@callback
def _cancel_delayed_discovery_scan(domain_data: dict[str, Any]) -> None:
    """Cancel any pending debounced ESPHome discovery scan timer."""
    prev_timer = domain_data.pop("_unsub_delayed_scan", None)
    if callable(prev_timer):
        prev_timer()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Latter domain, register services, and scan for Latter-compatible ESPHome devices."""
    _ = config
    domain_data = hass.data.setdefault(DOMAIN, {})
    await async_register_studio_icon_module(hass)
    await hass.async_add_executor_job(
        warm_timezone_cache,
        [str(getattr(getattr(hass, "config", None), "time_zone", "") or "")],
    )
    await _async_ensure_global_store(hass)
    await get_area_state_index(hass).async_start()
    await async_setup_services(hass)

    @callback
    def _schedule_debounced_discovery_scan(delay_s: float = 2.0) -> None:
        _cancel_delayed_discovery_scan(domain_data)
        if hass.is_stopping:
            return

        @callback
        def _delayed_scan(_now: Any) -> None:
            domain_data.pop("_unsub_delayed_scan", None)
            if not hass.is_stopping:
                _async_scan_all_esphome_devices_for_discovery(hass)

        domain_data["_unsub_delayed_scan"] = async_call_later(
            hass, delay_s, _delayed_scan
        )

    _register_domain_bus_listeners(
        hass, domain_data, _schedule_debounced_discovery_scan
    )

    if "_unsub_stop_cleanup" not in domain_data:

        @callback
        def _on_ha_stop(_ev: Event[Any]) -> None:
            domain_data.pop("_unsub_stop_cleanup", None)
            started_unsub = domain_data.pop("_unsub_started_scan", None)
            if callable(started_unsub):
                started_unsub()
            _cancel_delayed_discovery_scan(domain_data)
            unsubs = domain_data.pop(DATA_DISCOVERY_UNSUB, ())
            if isinstance(unsubs, tuple):
                for unsub in unsubs:
                    if callable(unsub):
                        unsub()
            clear_ma_counterpart_cache(hass)
            async_stop_area_state_index(hass)

        domain_data["_unsub_stop_cleanup"] = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _on_ha_stop
        )

    @callback
    def _on_ha_started(_ev: Event[Any]) -> None:
        domain_data.pop("_unsub_started_scan", None)
        _async_scan_all_esphome_devices_for_discovery(hass)

    if hass.is_running:
        _async_scan_all_esphome_devices_for_discovery(hass)
    elif "_unsub_started_scan" not in domain_data:
        domain_data["_unsub_started_scan"] = hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, _on_ha_started
        )
    return True


async def _async_init_entry_coordinators(
    hass: HomeAssistant,
    entry: LatterConfigEntry,
    sys_obj: LatterSystemHub,
    hmac_secret: bytes,
) -> None:
    device_subentries = [
        sub
        for sub in entry.subentries.values()
        if sub.subentry_type in DEVICE_SUBENTRY_TYPES
    ]
    initialized_coords: list[LatterCoordinator] = []
    try:
        for sub in device_subentries:
            coordinator = LatterCoordinator(
                hass=hass,
                entry=entry,
                hmac_secret=hmac_secret,
                subentry=sub,
            )
            if coordinator.rpc_receiver is None and not coordinator.is_ble_tag:
                LatterRpcReceiver(hass, coordinator)
            coordinator.on_area_changed_push_slots = (
                lambda c: async_push_active_area_entities(hass, c)
            )
            sys_obj.coordinators[coordinator.subentry_id] = coordinator
            try:
                await coordinator.async_setup()
            except Exception:
                coordinator.async_cleanup()
                sys_obj.coordinators.pop(coordinator.subentry_id, None)
                raise
            initialized_coords.append(coordinator)
            _LOGGER.info(
                "Latter v%s initialized device subentry '%s' (%s, active_speaker: %s)",
                INTEGRATION_VERSION,
                coordinator.device_slug,
                coordinator.subentry_id,
                coordinator.active_speaker,
            )
    except Exception:
        for prev_coord in initialized_coords:
            prev_coord.async_cleanup()
            sys_obj.coordinators.pop(prev_coord.subentry_id, None)
        sys_obj.async_cleanup_feeds()
        raise


async def async_setup_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> bool:
    """Set up the Latter System hub entry and all configured Device subentries."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    await hass.async_add_executor_job(
        warm_timezone_cache,
        [str(getattr(getattr(hass, "config", None), "time_zone", "") or "")],
    )
    await _async_ensure_global_store(hass)
    await get_area_state_index(hass).async_start()
    await async_setup_services(hass)
    sys_obj = get_latter_system(hass)
    if sys_obj is None:
        return False
    attach_hub_sync_methods(sys_obj)

    if sys_obj.url_signer is not None:
        await sys_obj.url_signer.async_prime_lan_base_url()
    await async_refresh_wallpaper_cache(hass)
    async_register_http_views(hass)
    await async_register_studio_panel(hass)

    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "system")},
        entry_type=dr.DeviceEntryType.SERVICE,
        name="Latter System",
        manufacturer="Latter",
        model="Latter Site & BLE Fabric Engine",
        sw_version=INTEGRATION_VERSION,
        configuration_url="homeassistant://latter",
    )

    entry.runtime_data = sys_obj
    sys_obj.bind_feed_listeners()

    await _async_init_entry_coordinators(
        hass, entry, sys_obj, domain_data[DATA_HMAC_SECRET]
    )

    if domain_data.pop("_pending_builtin_group_preset_upgrade", False):
        await async_sync_coordinators_to_builtin_presets(
            hass, list(sys_obj.coordinators.values())
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_heal_coordinator_ma_links(hass)
    for coordinator in list(sys_obj.coordinators.values()):
        coordinator.async_sync_ha_device_name()
        coordinator.async_sync_ha_device_areas()
        coordinator.async_notify_listeners()

    entry.async_create_background_task(
        hass, _async_ping_bound_devices(hass, sys_obj), name="latter_ping_bound_devices"
    )

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_ping_bound_devices(
    hass: HomeAssistant, sys_obj: LatterSystemHub
) -> None:
    """Call each bound Device's `latter_ping` action; the firmware answers with `latter.device_hello`."""

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
    sys_obj: LatterSystemHub = entry.runtime_data
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
        if coord.has_option_changes():
            await coord.async_apply_options()


async def async_unload_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> bool:
    """Unload the Latter System hub entry and all its device subentry coordinators."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await async_shutdown_camera_feeds(hass)
        await async_shutdown_doorbell_streams(hass)
        clear_browse_cache()
        clear_ma_counterpart_cache(hass)
        domain_data = hass.data.get(DOMAIN, {})
        if isinstance(domain_data, dict):
            _cancel_delayed_discovery_scan(domain_data)
        runtime = getattr(entry, "runtime_data", None)
        sys_obj = runtime if isinstance(runtime, LatterSystemHub) else get_latter_system(hass)
        if sys_obj is not None:
            sys_obj.async_cleanup_feeds()
            for sub_id, coord in list(sys_obj.coordinators.items()):
                if coord.entry.entry_id == entry.entry_id:
                    sys_obj.coordinators.pop(sub_id, None)
                    if isinstance(domain_data, dict):
                        domain_data.pop(sub_id, None)
                    coord.async_cleanup()
        async_stop_area_state_index(hass)
        async_unregister_studio_panel(hass)
        other_loaded = any(
            other.entry_id != entry.entry_id
            and isinstance(getattr(other, "runtime_data", None), LatterSystemHub)
            for other in hass.config_entries.async_entries(DOMAIN)
        )
        if not other_loaded:
            await async_unload_services(hass)
    return bool(unload_ok)


async def async_remove_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> None:
    """Unregister Studio panel, icon module, repairs, and services when the Latter System entry is removed."""
    for sub_id in entry.subentries:
        async_delete_device_issues(hass, sub_id)
    async_unregister_studio_panel(hass, remove_icon_module=True)
    if not hass.config_entries.async_entries(DOMAIN):
        await async_unload_services(hass)
    _async_scan_all_esphome_devices_for_discovery(hass)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: LatterConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow removing only genuinely stale/orphaned device entries, never the System hub or an active subentry."""
    if (DOMAIN, "system") in device_entry.identifiers:
        return False

    active_identifiers: set[tuple[str, str]] = set()
    for sub in config_entry.subentries.values():
        if sub.subentry_type not in DEVICE_SUBENTRY_TYPES:
            continue
        active_identifiers.add((DOMAIN, sub.subentry_id))
        mac = str(sub.data.get("mac") or "").strip()
        if mac:
            active_identifiers.add((DOMAIN, dr.format_mac(mac)))
        esp_dev_id = str(sub.data.get(CONF_ESPHOME_DEVICE_ID) or "").strip()
        if esp_dev_id:
            esp_dev = dr.async_get(hass).async_get(esp_dev_id)
            if isinstance(esp_dev, dr.DeviceEntry):
                for ctype, cval in esp_dev.connections:
                    if ctype == dr.CONNECTION_NETWORK_MAC and cval:
                        active_identifiers.add((DOMAIN, dr.format_mac(str(cval))))

    sys_obj = getattr(config_entry, "runtime_data", None)
    if isinstance(sys_obj, LatterSystemHub):
        for coord in sys_obj.coordinators.values():
            active_identifiers.update(coord.get_device_info().get("identifiers", set()))

    return not bool(device_entry.identifiers & active_identifiers)
