"""The Latter (Universal ESPHome Companion & Entity Middleware) integration."""

from __future__ import annotations

import asyncio
import logging
import secrets
import time
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigSubentry,
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
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    normalize_device_slug,
)
from .coordinator import LatterCoordinator
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
from .identity import get_bound_esphome_device
from .media_engine import clear_ma_counterpart_cache
from .services import async_push_active_area_entities, async_setup_services
from .studio import (
    LatterBrandIconView,
    LatterSidebarIconJsView,
    async_register_studio_panel,
    async_unregister_studio_panel,
)
from .system import LatterSystem, get_latter_system

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type LatterConfigEntry = ConfigEntry[LatterSystem]

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
    esphome_services = hass.services.async_services_for_domain("esphome")
    for suffix in LATTER_CONTRACT_ACTION_SUFFIXES:
        exact = f"{slug}{suffix}"
        if exact in esphome_services:
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
        for sub in seed_entry.subentries.values():
            for k in GLOBAL_CONFIG_KEYS:
                if k not in global_cfg and k in sub.data and sub.data[k] not in (None, "", [], {}):
                    global_cfg[k] = sub.data[k]
                    changed = True
    if changed:
        await domain_data[DATA_GLOBAL_STORE].async_save(global_cfg)

    get_latter_system(hass)
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
    """Trigger a Latter discovery flow ONLY if no Latter hub entry exists yet and the ESPHome device implements the Latter contract."""
    existing_entries = hass.config_entries.async_entries(DOMAIN)
    if existing_entries:
        return

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

    discovery_flow.async_create_flow(
        hass,
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_DEVICE_SLUG: slug, "name": dev_name},
    )


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Atomically migrate VERSION 1 per-device ConfigEntries into ConfigSubentries on the single VERSION 2 Latter System hub entry."""
    if entry.version >= 2:
        return True

    domain_data = hass.data.setdefault(DOMAIN, {})
    lock: asyncio.Lock = domain_data.setdefault("_migration_lock", asyncio.Lock())
    async with lock:
        if entry.version >= 2:
            return True

        await _async_ensure_global_store(hass, seed_entry=entry)
        all_entries = hass.config_entries.async_entries(DOMAIN)
        hub_entry = next(
            (
                e
                for e in all_entries
                if e.version >= 2 and not e.data.get("_migrated_to_hub")
            ),
            all_entries[0],
        )

        dev_reg = dr.async_get(hass)
        ent_reg = er.async_get(hass)
        v1_entries = [
            e
            for e in all_entries
            if e.version < 2 and not e.data.get("_migrated_to_hub")
        ]

        existing_sub_uids = {
            sub.unique_id for sub in hub_entry.subentries.values() if sub.unique_id
        }
        existing_sub_slugs = {
            normalize_device_slug(str(sub.data.get(CONF_DEVICE_SLUG, "")))
            for sub in hub_entry.subentries.values()
            if sub.data.get(CONF_DEVICE_SLUG)
        }

        for v1_entry in v1_entries:
            await _async_ensure_global_store(hass, seed_entry=v1_entry)
            raw_merged = {**v1_entry.data, **(v1_entry.options or {})}
            slug = normalize_device_slug(str(raw_merged.get(CONF_DEVICE_SLUG, "")))
            dev_data = {
                k: v for k, v in raw_merged.items() if k not in GLOBAL_CONFIG_KEYS
            }

            if slug and slug != "esphome_device":
                dev_data[CONF_DEVICE_SLUG] = slug
                matched_dev = get_bound_esphome_device(
                    hass,
                    str(dev_data.get(CONF_ESPHOME_DEVICE_ID) or "") or None,
                    fallback_slug=slug,
                )
                mac_str = ""
                if matched_dev is not None:
                    dev_data[CONF_ESPHOME_DEVICE_ID] = matched_dev.id
                    for _ctype, cval in matched_dev.connections:
                        if cval:
                            mac_str = dr.format_mac(str(cval))
                            dev_data["mac"] = mac_str
                            break

                sub_uid = (
                    f"{DOMAIN}_{mac_str}"
                    if mac_str
                    else (str(v1_entry.unique_id or "") or f"{DOMAIN}_{slug}")
                )
                sub_title = (
                    v1_entry.title
                    if v1_entry.title and v1_entry.title.lower() != "latter"
                    else slug.replace("_", " ").title()
                )

                # Remove legacy v1 device & entities keyed by (DOMAIN, v1_entry.entry_id) so subentry entities register without _2 suffixes
                for old_latter_dev in list(
                    dr.async_entries_for_config_entry(dev_reg, v1_entry.entry_id)
                ):
                    if (DOMAIN, v1_entry.entry_id) in old_latter_dev.identifiers:
                        for ent_entry in list(
                            er.async_entries_for_device(
                                ent_reg, old_latter_dev.id, include_disabled_entities=True
                            )
                        ):
                            ent_reg.async_remove(ent_entry.entity_id)
                        dev_reg.async_remove_device(old_latter_dev.id)

                if sub_uid not in existing_sub_uids and slug not in existing_sub_slugs:
                    subentry = ConfigSubentry(
                        data=MappingProxyType(dev_data),
                        subentry_type="device",
                        title=sub_title,
                        unique_id=sub_uid,
                    )
                    hass.config_entries.async_add_subentry(hub_entry, subentry)
                    existing_sub_uids.add(sub_uid)
                    existing_sub_slugs.add(slug)

                    # Migrate per-device runtime storage (.storage/latter.runtime.<old_entry_id> -> <subentry_id>)
                    old_store: Store[dict[str, Any]] = Store(
                        hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{v1_entry.entry_id}"
                    )
                    loaded_rt = await old_store.async_load()
                    if isinstance(loaded_rt, dict) and loaded_rt:
                        new_store: Store[dict[str, Any]] = Store(
                            hass,
                            STORAGE_VERSION,
                            f"{STORAGE_KEY_PREFIX}.{subentry.subentry_id}",
                        )
                        await new_store.async_save(loaded_rt)
                        await old_store.async_remove()

            if v1_entry.entry_id != hub_entry.entry_id:
                hass.config_entries.async_update_entry(
                    v1_entry,
                    data={"_migrated_to_hub": hub_entry.entry_id},
                    options={},
                    version=2,
                )

        hass.config_entries.async_update_entry(
            hub_entry,
            title="Latter",
            unique_id=DOMAIN,
            data={},
            options={},
            version=2,
        )
        _LOGGER.info(
            "Migrated %d Latter v1 device entries into ConfigSubentries on System hub entry %s",
            len(v1_entries),
            hub_entry.entry_id,
        )
        return True


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
    if entry.data.get("_migrated_to_hub"):
        hass.async_create_task(
            hass.config_entries.async_remove(entry.entry_id)
        )
        return True

    domain_data = hass.data.setdefault(DOMAIN, {})
    await _async_ensure_global_store(hass, seed_entry=entry)
    sys_obj = get_latter_system(hass)
    if sys_obj is None:
        return False

    if "views_registered" not in domain_data:
        domain_data["views_registered"] = True
        hass.http.register_view(LatterArtworkTranscoderView(hass))
        hass.http.register_view(LatterWallpaperProxyView(hass))
        hass.http.register_view(LatterRotatableCameraSnapshotView(hass))
        hass.http.register_view(LatterCameraAudioStreamView(hass))
        hass.http.register_view(LatterDoorbellTalkbackView(hass))
        hass.http.register_view(LatterMapSnapshotView(hass))
        hass.http.register_view(LatterBrandIconView(hass))
        hass.http.register_view(LatterSidebarIconJsView(hass))

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

    # If the entry was created with inline device data and no subentries yet, promote it to a ConfigSubentry
    if not entry.subentries and entry.data.get(CONF_DEVICE_SLUG):
        slug = normalize_device_slug(str(entry.data.get(CONF_DEVICE_SLUG, "")))
        if slug and slug != "esphome_device":
            dev_data = {
                k: v
                for k, v in {**entry.data, **(entry.options or {})}.items()
                if k not in GLOBAL_CONFIG_KEYS
            }
            sub_uid = str(entry.unique_id or f"{DOMAIN}_{slug}")
            if sub_uid == DOMAIN:
                sub_uid = f"{DOMAIN}_{slug}"
            subentry = ConfigSubentry(
                data=MappingProxyType(dev_data),
                subentry_type="device",
                title=slug.replace("_", " ").title(),
                unique_id=sub_uid,
            )
            hass.config_entries.async_add_subentry(entry, subentry)
            hass.config_entries.async_update_entry(
                entry, title="Latter", unique_id=DOMAIN, data={}, options={}
            )

    entry.runtime_data = sys_obj

    device_subentries = [
        sub
        for sub in entry.subentries.values()
        if sub.subentry_type == "device"
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

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: LatterConfigEntry) -> None:
    """Reload when device subentries are added/removed or structural keys change; otherwise apply options in-place."""
    if entry.data.get("_migrated_to_hub"):
        return
    sys_obj: LatterSystem = entry.runtime_data
    current_sub_ids = {
        sub.subentry_id
        for sub in entry.subentries.values()
        if sub.subentry_type == "device"
    }
    loaded_sub_ids = set(sys_obj.coordinators.keys())
    if current_sub_ids != loaded_sub_ids:
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
    if entry.data.get("_migrated_to_hub"):
        return True

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        async_unregister_studio_panel(hass)
        clear_ma_counterpart_cache(hass)
        domain_data = hass.data.get(DOMAIN, {})
        sys_obj = get_latter_system(hass)
        if sys_obj is not None:
            for sub_id, coord in list(sys_obj.coordinators.items()):
                if coord.entry.entry_id == entry.entry_id:
                    sys_obj.coordinators.pop(sub_id, None)
                    domain_data.pop(sub_id, None)
                    coord.async_cleanup()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: LatterConfigEntry) -> None:
    """Re-trigger discovery scan when the Latter System entry is removed."""
    _async_scan_all_esphome_devices_for_discovery(hass)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: LatterConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """Allow users to remove stale device entries from the Home Assistant Device Registry."""
    return True
