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

from .config_flow import _device_unique_id
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
from .coordinator import LatterCoordinator
from .http import (
    LatterArtworkTranscoderView,
    LatterBrandIconView,
    LatterCameraAudioStreamView,
    LatterCameraSnapshotView,
    LatterMapSnapshotView,
    LatterWallpaperProxyView,
    LatterWallpaperUploadView,
    async_shutdown_camera_feeds,
    async_shutdown_doorbell_streams,
)
from .hub import (
    LatterSystemHub,
    async_stop_area_state_index,
    get_area_state_index,
    get_latter_system,
    iter_coordinators,
)
from .identity import (
    LATTER_CONTRACT_ACTION_SUFFIXES,
    esphome_service,
    is_esphome_device,
    is_latter_compatible_esphome_device,
)
from .media import async_heal_coordinator_ma_links, clear_ma_counterpart_cache
from .media_browse import clear_browse_cache
from .presence import _iter_devices
from .repairs import async_delete_device_issues
from .services import async_push_active_area_entities, async_setup_services
from .studio import async_register_studio_panel, async_unregister_studio_panel
from .wallpapers import async_refresh_wallpaper_cache

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type LatterConfigEntry = ConfigEntry[LatterSystemHub]

PING_ACTION = "latter_ping"


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

    get_latter_system(hass)
    return global_cfg


@callback
def _async_scan_all_esphome_devices_for_discovery(hass: HomeAssistant) -> None:
    """Self-heal crashed flows, abort stale discovery flows, and discover Latter-compatible ESPHome devices."""
    dev_reg = dr.async_get(hass)
    esphome_devices = [d for d in _iter_devices(dev_reg) if is_esphome_device(hass, d)]
    devices_by_uid = {_device_unique_id(d): d for d in esphome_devices}

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
    await get_area_state_index(hass).async_start()
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
            action = event.data.get("action")
            if action not in ("create", "update"):
                return
            dev_id = event.data.get("device_id")
            if not dev_id:
                return
            dev_reg = dr.async_get(hass)
            dev = dev_reg.async_get(dev_id)
            own_writes = domain_data.get("_own_area_writes")
            if isinstance(own_writes, dict) and dev_id in own_writes:
                expected_area, write_ts = own_writes[dev_id]
                cur_area = str(dev.area_id or "").strip() if dev is not None else ""
                if (
                    (time.monotonic() - float(write_ts)) < 2.0
                    and dev is not None
                    and cur_area == str(expected_area or "").strip()
                ):
                    own_writes.pop(dev_id, None)
                    for coord in iter_coordinators(hass):
                        coord.async_record_own_area_write(dev_id, cur_area)
                    return
            if dev is not None:
                _async_check_esphome_device_for_discovery(hass, dev)
                _schedule_debounced_discovery_scan(5.0)
                if action == "update":
                    changes = event.data.get("changes")
                    if isinstance(changes, dict) and "area_id" not in changes:
                        return
                    new_area = str(dev.area_id or "").strip()
                    for coord in iter_coordinators(hass):
                        if coord.is_ble_tag:
                            continue
                        if (
                            dev.id == coord.esphome_device_id
                            or bool(
                                dev.identifiers
                                & coord.get_device_info()["identifiers"]
                            )
                            or (
                                coord.esphome_device_id
                                and dev.via_device_id == coord.esphome_device_id
                            )
                        ):
                            coord.async_on_ha_device_area_updated(dev.id, new_area)

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
    await get_area_state_index(hass).async_start()
    sys_obj = get_latter_system(hass)
    if sys_obj is None:
        return False

    await sys_obj.url_signer.async_prime_lan_base_url()
    await async_refresh_wallpaper_cache(hass, "system")

    if "views_registered" not in domain_data:
        domain_data["views_registered"] = True
        hass.http.register_view(LatterArtworkTranscoderView(hass))
        hass.http.register_view(LatterWallpaperProxyView(hass))
        hass.http.register_view(LatterWallpaperUploadView(hass))
        hass.http.register_view(LatterCameraSnapshotView(hass))
        hass.http.register_view(LatterCameraAudioStreamView(hass))
        hass.http.register_view(LatterMapSnapshotView(hass))
        hass.http.register_view(LatterBrandIconView(hass))

    await async_register_studio_panel(hass)

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

    async_heal_coordinator_ma_links(hass)
    for coordinator in list(sys_obj.coordinators.values()):
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
        await coord.async_apply_options()


async def async_unload_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> bool:
    """Unload the Latter System hub entry and all its device subentry coordinators."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await async_shutdown_camera_feeds()
        await async_shutdown_doorbell_streams(hass)
        clear_browse_cache()
        clear_ma_counterpart_cache(hass)
        domain_data = hass.data.get(DOMAIN, {})
        sys_obj = get_latter_system(hass)
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
            if esp_dev is not None:
                for ctype, cval in esp_dev.connections:
                    if ctype == dr.CONNECTION_NETWORK_MAC and cval:
                        active_identifiers.add((DOMAIN, dr.format_mac(str(cval))))

    sys_obj = getattr(config_entry, "runtime_data", None)
    if isinstance(sys_obj, LatterSystemHub):
        for coord in sys_obj.coordinators.values():
            active_identifiers.update(coord.get_device_info().get("identifiers", set()))

    return not bool(device_entry.identifiers & active_identifiers)
