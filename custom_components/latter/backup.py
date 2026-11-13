"""Home Assistant Backup platform callbacks and System/Device JSON export/import bundles for Latter."""

from __future__ import annotations

import secrets
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_AREA_CATEGORIES,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DOCK_APPS,
    CONF_HOME_CATEGORIES,
    CONF_MA_PLAYER_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_SITE_ID,
    CONF_SYNC_DEVICE_AREA,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DEFAULT_DEVICE_GROUP,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
)
from .groups import apply_esphome_controls_to_device, capture_live_esphome_controls
from .hub import get_latter_system, iter_coordinators
from .studio.settings import DEVICE_PREF_SPECS, resolve_device_pref_value

DEVICE_CONFIG_EXPORT_KEYS: tuple[str, ...] = (
    CONF_DEVICE_SLUG,
    CONF_DEVICE_GROUP,
    CONF_DEFAULT_SPEAKER,
    CONF_MA_PLAYER_ENTITY,
    CONF_DEFAULT_AREA,
    CONF_NATIVE_BLE_TRACKING,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_SYNC_DEVICE_AREA,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_DOCK_APPS,
    CONF_AREA_CATEGORIES,
    CONF_HOME_CATEGORIES,
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_WALLPAPER_SOURCE,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_SECURITY_PIN_POLICY,
    "device_remote_group",
    CONF_SITE_ID,
    *tuple(s.key for s in DEVICE_PREF_SPECS if s.key != "weather_sim_condition"),
)


async def async_pre_backup(hass: HomeAssistant) -> None:
    """Flush in-memory Site configuration and per-device runtime stores to disk before HA creates a backup."""
    domain_data: dict[str, Any] = hass.data.get(DOMAIN, {})
    if not isinstance(domain_data, dict):
        return

    global_store = domain_data.get(DATA_GLOBAL_STORE)
    global_cfg = domain_data.get(DATA_GLOBAL_CONFIG)
    if global_store is not None and isinstance(global_cfg, dict):
        await global_store.async_save(global_cfg)

    seen_ids: set[int] = set()
    for coord in iter_coordinators(hass):
        seen_ids.add(id(coord))
        flush_fn = getattr(coord, "async_flush_runtime_state", None)
        if callable(flush_fn):
            await flush_fn()

    for item in domain_data.values():
        if id(item) in seen_ids:
            continue
        seen_ids.add(id(item))
        flush_fn = getattr(item, "async_flush_runtime_state", None)
        if callable(flush_fn):
            await flush_fn()


async def async_post_backup(hass: HomeAssistant) -> None:
    """Complete Home Assistant Core backup hook."""


def _serialize_device_snapshot(hass: HomeAssistant, coordinator: Any) -> dict[str, Any]:
    """Build a portable dictionary snapshot of a single device's Latter config & live ESPHome controls."""
    pref_keys = {s.key for s in DEVICE_PREF_SPECS}
    dev_cfg: dict[str, Any] = {}
    for k in DEVICE_CONFIG_EXPORT_KEYS:
        val = coordinator.get_opt(k)
        if val is not None:
            dev_cfg[k] = val
        elif k in pref_keys:
            dev_cfg[k] = resolve_device_pref_value(coordinator.device_data, k)
    dev_cfg.setdefault(CONF_DEVICE_GROUP, DEFAULT_DEVICE_GROUP)
    return {
        "device_slug": coordinator.device_slug,
        "title": coordinator.device_slug.replace("_", " ").title(),
        "device_group": str(dev_cfg.get(CONF_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP),
        "display_shape": coordinator.display_shape,
        "active_area_id": coordinator.active_area_id or "",
        "active_speaker": coordinator.active_speaker,
        "active_remote_slot": coordinator.active_remote_slot,
        "device_config": dev_cfg,
        "esphome_controls": capture_live_esphome_controls(
            hass, coordinator.esphome_device_id
        ),
    }


def build_backup_bundle(
    hass: HomeAssistant,
    scope: str,
    coordinators: list[Any],
    target_coordinator: Any | None = None,
    name: str = "",
) -> dict[str, Any]:
    """Construct a complete, portable JSON backup bundle for 'system' or 'device' scope."""
    now_iso = dt_util.now().isoformat(timespec="seconds")
    clean_scope = "system" if scope == "system" else "device"
    backup_id = f"bkp_{int(dt_util.now().timestamp())}_{secrets.token_hex(3)}"

    domain_data = hass.data.get(DOMAIN, {})
    raw_global = dict(domain_data.get(DATA_GLOBAL_CONFIG) or {})
    global_export: dict[str, Any] = {}
    for k in GLOBAL_CONFIG_KEYS:
        if k == CONF_SECURITY_PIN_HASH:
            continue
        if k in raw_global and raw_global[k] is not None:
            global_export[k] = raw_global[k]

    if clean_scope == "system":
        devices_map: dict[str, Any] = {}
        for coord in coordinators:
            devices_map[coord.device_slug] = _serialize_device_snapshot(hass, coord)
        label = (
            name.strip()
            or f"System Backup ({dt_util.now().strftime('%Y-%m-%d %H:%M')})"
        )
        return {
            "id": backup_id,
            "schema": "latter.backup.v2",
            "version": INTEGRATION_VERSION,
            "scope": "system",
            "name": label,
            "created_at": now_iso,
            "target_device": "all",
            "device_count": len(devices_map),
            "global_config": global_export,
            "devices": devices_map,
        }

    coord = target_coordinator
    if coord is None:
        raise ValueError("A Device backup needs a target Device")
    dev_snap = _serialize_device_snapshot(hass, coord)
    label = (
        name.strip()
        or f"{dev_snap['title']} ({dt_util.now().strftime('%Y-%m-%d %H:%M')})"
    )
    return {
        "id": backup_id,
        "schema": "latter.backup.v2",
        "version": INTEGRATION_VERSION,
        "scope": "device",
        "name": label,
        "created_at": now_iso,
        "target_device": coord.device_slug,
        "device_count": 1,
        "device": dev_snap,
    }


async def _async_apply_device_snapshot_to_coordinator(
    hass: HomeAssistant,
    coord: Any,
    dev_snap: dict[str, Any],
    preserve_slug: bool = True,
    restore_esphome_entities: bool = True,
) -> int:
    """Restore a single device snapshot onto a target LatterCoordinator."""
    incoming_cfg = dict(dev_snap.get("device_config") or {})
    if preserve_slug:
        incoming_cfg[CONF_DEVICE_SLUG] = coord.device_slug

    merged: dict[str, Any] = dict(coord.device_data)
    for k in DEVICE_CONFIG_EXPORT_KEYS:
        if k in incoming_cfg and incoming_cfg[k] is not None:
            merged[k] = incoming_cfg[k]

    coord.update_device_config(merged)

    if dev_snap.get("active_area_id"):
        coord.active_area_id = str(dev_snap["active_area_id"])
    if isinstance(dev_snap.get("active_remote_slot"), int):
        coord.active_remote_slot = max(1, min(10, int(dev_snap["active_remote_slot"])))

    coord._bind_wallpaper_cycle_timer()
    coord._schedule_persist_runtime_state()
    coord.async_notify_listeners()

    applied_controls = 0
    if restore_esphome_entities and isinstance(dev_snap.get("esphome_controls"), dict):
        applied_controls = await apply_esphome_controls_to_device(
            hass, coord.esphome_device_id, dev_snap["esphome_controls"]
        )
    return applied_controls


async def async_restore_backup_bundle(
    hass: HomeAssistant,
    bundle: dict[str, Any],
    coordinators: list[Any],
    target_coordinator: Any | None = None,
    restore_esphome_entities: bool = True,
) -> dict[str, Any]:
    """Restore a System or Device backup bundle (from uploaded Computer JSON file)."""
    if not isinstance(bundle, dict) or bundle.get("schema") != "latter.backup.v2":
        raise ValueError("Invalid Latter backup bundle schema")

    scope = str(bundle.get("scope") or "device")
    restored_devices = 0
    restored_controls = 0

    if scope == "system":
        global_cfg_in = bundle.get("global_config")
        if isinstance(global_cfg_in, dict):
            domain_data = hass.data.setdefault(DOMAIN, {})
            global_cfg: dict[str, Any] = domain_data.setdefault(DATA_GLOBAL_CONFIG, {})
            for k in GLOBAL_CONFIG_KEYS:
                if k == CONF_SECURITY_PIN_HASH:
                    continue
                if k in global_cfg_in:
                    global_cfg[k] = global_cfg_in[k]
            sys_obj = get_latter_system(hass)
            if sys_obj is not None:
                sys_obj.config = global_cfg
            store = domain_data.get(DATA_GLOBAL_STORE)
            if store is not None:
                await store.async_save(global_cfg)

        devices_map = bundle.get("devices") or {}
        if isinstance(devices_map, dict):
            for coord in coordinators:
                snap = devices_map.get(coord.device_slug)
                if isinstance(snap, dict):
                    restored_controls += await _async_apply_device_snapshot_to_coordinator(
                        hass,
                        coord,
                        snap,
                        preserve_slug=True,
                        restore_esphome_entities=restore_esphome_entities,
                    )
                    restored_devices += 1
                await coord.async_on_global_config_updated()

        return {
            "scope": "system",
            "restored_devices": restored_devices,
            "restored_controls": restored_controls,
        }

    dev_snap = bundle.get("device")
    if not isinstance(dev_snap, dict):
        raise ValueError("Backup bundle is missing 'device' payload")

    coord = target_coordinator
    if coord is None:
        raise ValueError("A Device backup must be restored onto a selected Device")

    restored_controls = await _async_apply_device_snapshot_to_coordinator(
        hass,
        coord,
        dev_snap,
        preserve_slug=True,
        restore_esphome_entities=restore_esphome_entities,
    )
    return {
        "scope": "device",
        "target_device": coord.device_slug,
        "restored_devices": 1,
        "restored_controls": restored_controls,
    }
