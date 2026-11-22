"""Home Assistant Backup platform callbacks and System/Device JSON export/import bundles (`L2b`)."""

from __future__ import annotations

import re
import secrets
from typing import Any, Final

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
    CONF_BLE_CATEGORY,
    CONF_BLE_REF_POWER,
    CONF_BLE_TARGET_ADDRESS,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DOCK_ITEMS,
    CONF_GAMES_ITEMS,
    CONF_HOME_CATEGORIES,
    CONF_IGNORED_DISCOVERED_DEVICES,
    CONF_MA_PLAYER_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PINNED_ITEMS,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_IDS,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_SITE_ID,
    CONF_SYNC_DEVICE_AREA,
    CONF_SYSTEM_CONFIG_REV,
    CONF_TOOLS_ITEMS,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_SITE_ID,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
)
from .hub_registry import (
    get_latter_system,
    get_system_config_lock,
    get_system_config_rev,
    iter_coordinators,
)
from .studio.settings_cleaners import (
    DEVICE_PREF_SPECS,
    DEVICE_SETTING_KEYS,
    SYSTEM_SETTING_KEYS,
    SettingsScopeError,
    clean_device_settings,
    clean_system_settings,
    resolve_device_pref_value,
)
from .wallpapers.store import (
    export_photo_library_metadata,
    restore_photo_library_metadata,
)

_MAX_FAVORITES_RESTORE: Final = 50
_MAX_FAVORITE_ID_LEN: Final = 128
_MAX_SITE_ID_LEN: Final = 64
_MAX_REMOTE_SLOTS: Final = 10
_MAX_IGNORED_ITEMS: Final = 100
_MAX_IGNORED_ID_LEN: Final = 64

DEVICE_CONFIG_EXPORT_KEYS: Final[tuple[str, ...]] = (
    CONF_DEVICE_SLUG,
    CONF_DEVICE_GROUP,
    CONF_DEFAULT_SPEAKER,
    CONF_MA_PLAYER_ENTITY,
    CONF_DEFAULT_AREA,
    CONF_NATIVE_BLE_TRACKING,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_BLE_CATEGORY,
    CONF_BLE_REF_POWER,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_SYNC_DEVICE_AREA,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_DOCK_ITEMS,
    CONF_PINNED_ITEMS,
    CONF_AREA_CATEGORIES,
    CONF_HOME_CATEGORIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_TOOLS_ITEMS,
    CONF_GAMES_ITEMS,
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_IDS,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_SHUFFLE,
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

    async with get_system_config_lock(hass):
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


def _serialize_device_snapshot(_hass: HomeAssistant, coordinator: Any) -> dict[str, Any]:
    """Build a portable dictionary snapshot of a single device's Latter config & live ESPHome controls."""
    pref_keys = {s.key for s in DEVICE_PREF_SPECS}
    dev_cfg: dict[str, Any] = {}
    for k in DEVICE_CONFIG_EXPORT_KEYS:
        val = coordinator.get_opt(k)
        if val is not None:
            dev_cfg[k] = val
        elif k in pref_keys:
            dev_cfg[k] = resolve_device_pref_value(coordinator.device_data, k)
        elif k == CONF_TOOLS_ITEMS:
            dev_cfg[k] = coordinator.tools_items_csv
        elif k == CONF_GAMES_ITEMS:
            dev_cfg[k] = coordinator.games_items_csv
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
    }


def build_backup_bundle(
    hass: HomeAssistant,
    scope: str,
    coordinators: list[Any],
    target_coordinator: Any | None = None,
    name: str = "",
) -> dict[str, Any]:
    """Construct a complete, portable JSON backup bundle for `'system'` or `'device'` scope."""
    now = dt_util.now()
    now_iso = now.isoformat(timespec="seconds")
    clean_scope = "system" if scope == "system" else "device"
    backup_id = f"bkp_{int(now.timestamp())}_{secrets.token_hex(3)}"

    domain_data = hass.data.get(DOMAIN, {})
    raw_global = dict(domain_data.get(DATA_GLOBAL_CONFIG) or {})
    global_export = {
        k: raw_global[k]
        for k in GLOBAL_CONFIG_KEYS
        if k != CONF_SECURITY_PIN_HASH and k in raw_global and raw_global[k] is not None
    }

    if clean_scope == "system":
        devices_map = {coord.device_slug: _serialize_device_snapshot(hass, coord) for coord in coordinators}
        label = name.strip() or f"System Backup ({now.strftime('%Y-%m-%d %H:%M')})"
        photo_lib = export_photo_library_metadata()
        return {
            "id": backup_id,
            "schema": "latter.backup.v3",
            "version": INTEGRATION_VERSION,
            "scope": "system",
            "name": label,
            "created_at": now_iso,
            "target_device": "all",
            "device_count": len(devices_map),
            "global_config": global_export,
            "photo_collections": photo_lib["photo_collections"],
            "photo_metadata": photo_lib["photo_metadata"],
            "preset_collections": photo_lib["preset_collections"],
            "devices": devices_map,
        }

    if target_coordinator is None:
        raise ValueError("A Device backup needs a target Device")
    dev_snap = _serialize_device_snapshot(hass, target_coordinator)
    label = name.strip() or f"{dev_snap['title']} ({now.strftime('%Y-%m-%d %H:%M')})"
    return {
        "id": backup_id,
        "schema": "latter.backup.v3",
        "version": INTEGRATION_VERSION,
        "scope": "device",
        "name": label,
        "created_at": now_iso,
        "target_device": target_coordinator.device_slug,
        "device_count": 1,
        "device": dev_snap,
    }


def _build_restored_device_config(
    coord: Any, incoming_cfg: dict[str, Any], *, preserve_slug: bool
) -> dict[str, Any]:
    if preserve_slug:
        incoming_cfg[CONF_DEVICE_SLUG] = coord.device_slug
    merged: dict[str, Any] = dict(coord.device_data)
    cleanable = {
        k: incoming_cfg[k]
        for k in DEVICE_SETTING_KEYS
        if k in incoming_cfg and incoming_cfg[k] is not None
    }
    if cleanable:
        try:
            sanitized = clean_device_settings(
                cleanable,
                current=merged,
                is_round_display=bool(getattr(coord, "is_round_display", True)),
                supports_hw_jpeg=bool(getattr(coord, "supports_hw_jpeg", False)),
            )
        except SettingsScopeError as err:
            raise ValueError(str(err)) from err
        merged.update(sanitized)

    if CONF_BLE_REF_POWER in incoming_cfg and incoming_cfg[CONF_BLE_REF_POWER] is None:
        merged.pop(CONF_BLE_REF_POWER, None)
    if isinstance(incoming_cfg.get(CONF_WALLPAPER_FAVORITES), list):
        merged[CONF_WALLPAPER_FAVORITES] = [
            str(x).strip()[:_MAX_FAVORITE_ID_LEN]
            for x in incoming_cfg[CONF_WALLPAPER_FAVORITES][:_MAX_FAVORITES_RESTORE]
            if str(x or "").strip()
        ]
    if CONF_SITE_ID in incoming_cfg and incoming_cfg[CONF_SITE_ID] is not None:
        raw_site = str(incoming_cfg[CONF_SITE_ID]).strip().lower()
        clean_site = re.sub(r"[^a-z0-9_-]+", "_", raw_site).strip("_-")[:_MAX_SITE_ID_LEN]
        merged[CONF_SITE_ID] = clean_site or DEFAULT_SITE_ID
    if preserve_slug:
        merged[CONF_DEVICE_SLUG] = coord.device_slug
    return merged


async def _async_apply_device_snapshot_to_coordinator(
    _hass: HomeAssistant,
    coord: Any,
    dev_snap: dict[str, Any],
    preserve_slug: bool = True,
) -> int:
    """Restore a single device snapshot onto a target `LatterCoordinator`."""
    incoming_cfg = dict(dev_snap.get("device_config") or {})
    merged = _build_restored_device_config(coord, incoming_cfg, preserve_slug=preserve_slug)

    async with coord.config_lock:
        coord.update_device_config(merged)
    sync_ble = getattr(coord, "sync_ble_tracker", None)
    if callable(sync_ble):
        sync_ble()

    if dev_snap.get("active_area_id"):
        coord.active_area_id = str(dev_snap["active_area_id"])
    if isinstance(dev_snap.get("active_remote_slot"), int):
        coord.active_remote_slot = max(1, min(_MAX_REMOTE_SLOTS, int(dev_snap["active_remote_slot"])))

    if hasattr(coord, "bind_wallpaper_cycle_timer"):
        coord.bind_wallpaper_cycle_timer()
    if hasattr(coord, "bind_screensaver_cycle_timer"):
        coord.bind_screensaver_cycle_timer()
    coord.schedule_persist_runtime_state()
    coord.async_notify_listeners()
    return 0


async def _async_restore_system_global_config(
    hass: HomeAssistant, global_cfg_in: dict[str, Any]
) -> None:
    sys_cleanable = {
        k: global_cfg_in[k]
        for k in SYSTEM_SETTING_KEYS
        if k in global_cfg_in and global_cfg_in[k] is not None
    }
    try:
        sanitized_sys = clean_system_settings(sys_cleanable) if sys_cleanable else {}
    except SettingsScopeError as err:
        raise ValueError(str(err)) from err

    async with get_system_config_lock(hass):
        domain_data = hass.data.setdefault(DOMAIN, {})
        global_cfg: dict[str, Any] = domain_data.setdefault(DATA_GLOBAL_CONFIG, {})
        for k in GLOBAL_CONFIG_KEYS:
            if k != CONF_SECURITY_PIN_HASH and k in sanitized_sys:
                global_cfg[k] = sanitized_sys[k]
        raw_ignored = global_cfg_in.get(CONF_IGNORED_DISCOVERED_DEVICES)
        if isinstance(raw_ignored, list):
            global_cfg[CONF_IGNORED_DISCOVERED_DEVICES] = [
                clean_id
                for item in raw_ignored[:_MAX_IGNORED_ITEMS]
                if isinstance(item, str) and (clean_id := item.strip()[:_MAX_IGNORED_ID_LEN])
            ]
        global_cfg[CONF_SYSTEM_CONFIG_REV] = get_system_config_rev(hass) + 1
        if (sys_obj := get_latter_system(hass)) is not None:
            sys_obj.config = global_cfg
        if (store := domain_data.get(DATA_GLOBAL_STORE)) is not None:
            await store.async_save(global_cfg)


async def async_restore_backup_bundle(
    hass: HomeAssistant,
    bundle: dict[str, Any],
    coordinators: list[Any],
    target_coordinator: Any | None = None,
) -> dict[str, Any]:
    """Restore a System or Device backup bundle (from uploaded Computer JSON file)."""
    if not isinstance(bundle, dict) or bundle.get("schema") != "latter.backup.v3":
        raise ValueError("Invalid Latter backup bundle schema")

    scope = str(bundle.get("scope") or "device")
    if scope == "system":
        if isinstance(global_cfg_in := bundle.get("global_config"), dict):
            await _async_restore_system_global_config(hass, global_cfg_in)
        if any(k in bundle for k in ("photo_collections", "photo_metadata", "preset_collections")):
            await hass.async_add_executor_job(
                restore_photo_library_metadata,
                hass,
                bundle.get("photo_collections"),
                bundle.get("photo_metadata"),
                bundle.get("preset_collections"),
            )
        restored_devices = 0
        if isinstance(devices_map := (bundle.get("devices") or {}), dict):
            for coord in coordinators:
                if isinstance(snap := devices_map.get(coord.device_slug), dict):
                    await _async_apply_device_snapshot_to_coordinator(hass, coord, snap, preserve_slug=True)
                    restored_devices += 1
                await coord.async_on_global_config_updated()
        return {"scope": "system", "restored_devices": restored_devices, "restored_controls": 0}

    dev_snap = bundle.get("device")
    if not isinstance(dev_snap, dict):
        raise ValueError("Backup bundle is missing 'device' payload")
    if target_coordinator is None:
        raise ValueError("A Device backup must be restored onto a selected Device")
    await _async_apply_device_snapshot_to_coordinator(hass, target_coordinator, dev_snap, preserve_slug=True)
    return {
        "scope": "device",
        "target_device": target_coordinator.device_slug,
        "restored_devices": 1,
        "restored_controls": 0,
    }
