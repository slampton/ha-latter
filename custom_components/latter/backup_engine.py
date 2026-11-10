"""System & Device JSON Export/Import and Unified Device Group Baselines Engine for Latter."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
import re
import secrets
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .area_engine import async_execute_area_action, get_esphome_device_entities
from .const import (
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_GROUPS,
    CONF_DEVICE_SLUG,
    CONF_DOCK_APPS,
    CONF_MA_PLAYER_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
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
from .system import get_latter_system

_LOGGER = logging.getLogger(__name__)

DEVICE_CONFIG_EXPORT_KEYS: tuple[str, ...] = (
    CONF_DEVICE_SLUG,
    CONF_DEVICE_GROUP,
    CONF_DEFAULT_PAGE_SIZE,
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
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_WALLPAPER_SOURCE,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_DEVICE_CUSTOM_COLOR,
    "device_remote_group",
    CONF_SITE_ID,
)

# Tier 2: Operational Behavior keys synced automatically by a Device Group's baseline.
GROUP_BEHAVIOR_DEVICE_KEYS: tuple[str, ...] = (
    CONF_NATIVE_BLE_TRACKING,
    CONF_BLE_AUTO_SWITCH,
    CONF_SYNC_DEVICE_AREA,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
)

# Tier 3: Personal & Area Appearance/Layout keys preserved per-device on group join/sync.
GROUP_APPEARANCE_DEVICE_KEYS: tuple[str, ...] = (
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DOCK_APPS,
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_WALLPAPER_SOURCE,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_DEVICE_CUSTOM_COLOR,
    "device_remote_group",
)

PROFILE_DEVICE_KEYS: tuple[str, ...] = (
    CONF_DEFAULT_PAGE_SIZE,
    CONF_NATIVE_BLE_TRACKING,
    CONF_BLE_AUTO_SWITCH,
    CONF_SYNC_DEVICE_AREA,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_DOCK_APPS,
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_WALLPAPER_SOURCE,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_DEVICE_CUSTOM_COLOR,
    "device_remote_group",
)

# Tier 3 ESPHome controls (personal/Area appearance & layout; not overwritten when syncing a Group's Tier 2 baseline).
APPEARANCE_ESPHOME_CONTROL_KEYS: frozenset[str] = frozenset(
    {
        "select:clock_face",
        "select:time_format",
        "select:color_profile",
        "select:start_screen",
        "select:screensaver_style",
        "select:visual_profile",
        "select:default_category",
        "switch:show_all_category",
        "switch:show_all_in_category",
        "switch:weather_background",
        "switch:sun",
        "switch:moon",
        "switch:wake_greeting",
        "select:album_art_style",
        "select:overlay_style",
        "select:album_sort_order",
        "select:artist_album_sort_order",
        "select:podcast_sort_order",
        "switch:show_speaker_shortcut",
        "switch:show_library_shortcut",
    }
)

# Diagnostic/simulation controls excluded from group baselines and snapshots.
EXCLUDED_ESPHOME_CONTROL_KEYS: frozenset[str] = frozenset(
    {
        "switch:telemetry_profiler",
        "select:condition_simulation",
    }
)

# Canonical 7-control specs matching kPowerProfiles in esphome-latter-core/include/ui_system.h.
POWER_PROFILE_SPECS: dict[str, dict[str, str]] = {
    "Portable Carry": {
        "select:wake_word_mode": "Docked Only",
        "select:tap_to_wake": "Docked Only",
        "select:pickup_to_wake": "Docked Only",
        "select:battery_screen_timeout": "30s",
        "select:docked_idle_timeout": "1 min",
        "select:battery_hibernate_timeout": "15 min",
        "switch:docked_screensaver": "on",
    },
    "Handheld Roaming": {
        "select:wake_word_mode": "Docked Only",
        "select:tap_to_wake": "Always On",
        "select:pickup_to_wake": "Always On",
        "select:battery_screen_timeout": "30s",
        "select:docked_idle_timeout": "1 min",
        "select:battery_hibernate_timeout": "30 min",
        "switch:docked_screensaver": "on",
    },
    "Wearable Watch": {
        "select:wake_word_mode": "Docked Only",
        "select:tap_to_wake": "Always On",
        "select:pickup_to_wake": "Always On",
        "select:battery_screen_timeout": "15s",
        "select:docked_idle_timeout": "1 min",
        "select:battery_hibernate_timeout": "15 min",
        "switch:docked_screensaver": "on",
    },
    "Tabletop Dock": {
        "select:wake_word_mode": "Docked Only",
        "select:tap_to_wake": "Docked Only",
        "select:pickup_to_wake": "Disabled",
        "select:battery_screen_timeout": "30s",
        "select:docked_idle_timeout": "5 min",
        "select:battery_hibernate_timeout": "15 min",
        "switch:docked_screensaver": "on",
    },
    "Always-On Wall / Desk": {
        "select:wake_word_mode": "Always On",
        "select:tap_to_wake": "Always On",
        "select:pickup_to_wake": "Disabled",
        "select:battery_screen_timeout": "Never",
        "select:docked_idle_timeout": "5 min",
        "select:battery_hibernate_timeout": "Disabled",
        "switch:docked_screensaver": "on",
    },
}

DEFAULT_DEVICE_GROUPS: list[dict[str, Any]] = [
    {
        "id": "unassigned",
        "name": "Unassigned",
        "description": "Default group with no baseline settings applied",
        "builtin": True,
        "device_config": {},
        "esphome_controls": {},
    },
    {
        "id": "handhelds",
        "name": "Handhelds",
        "description": "Battery-powered roaming displays with pickup and tap wake",
        "builtin": True,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
        },
        "esphome_controls": {
            "select:power_profile": "Handheld Roaming",
            **POWER_PROFILE_SPECS["Handheld Roaming"],
            "select:auto_brightness_mode": "Sun Synchronized",
            "select:day_brightness": "90%",
            "select:night_brightness": "70%",
        },
    },
    {
        "id": "wearables",
        "name": "Wearables",
        "description": "Compact wearable displays with double-tap wake on battery and 15s screen timeout",
        "builtin": True,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
        },
        "esphome_controls": {
            "select:power_profile": "Wearable Watch",
            **POWER_PROFILE_SPECS["Wearable Watch"],
            "select:auto_brightness_mode": "Sun Synchronized",
            "select:day_brightness": "80%",
            "select:night_brightness": "60%",
        },
    },
    {
        "id": "bedrooms",
        "name": "Bedrooms",
        "description": "Nightstand and quiet tabletop displays with dimmed night brightness and docked wake word",
        "builtin": True,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: False,
            CONF_BLE_AUTO_SWITCH: False,
            CONF_SYNC_DEVICE_AREA: False,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
        },
        "esphome_controls": {
            "select:power_profile": "Tabletop Dock",
            **POWER_PROFILE_SPECS["Tabletop Dock"],
            "select:auto_brightness_mode": "Sun Synchronized",
            "select:day_brightness": "80%",
            "select:night_brightness": "60%",
            "number:alert_volume": 50,
        },
    },
    {
        "id": "common_areas",
        "name": "Common Areas",
        "description": "Shared tabletop displays with Always-On wake word and 5 min docked idle timeout",
        "builtin": True,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: False,
            CONF_BLE_AUTO_SWITCH: False,
            CONF_SYNC_DEVICE_AREA: False,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
        },
        "esphome_controls": {
            "select:power_profile": "Custom",
            "select:wake_word_mode": "Always On",
            "select:tap_to_wake": "Always On",
            "select:pickup_to_wake": "Disabled",
            "select:battery_screen_timeout": "30s",
            "select:docked_idle_timeout": "5 min",
            "select:battery_hibernate_timeout": "15 min",
            "switch:docked_screensaver": "on",
            "select:auto_brightness_mode": "Sun Synchronized",
            "select:day_brightness": "90%",
            "select:night_brightness": "70%",
        },
    },
    {
        "id": "wall_panels",
        "name": "Wall & Desk Panels",
        "description": "Stationary mains-powered panels with Always-On wake word and no battery hibernate",
        "builtin": True,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: False,
            CONF_BLE_AUTO_SWITCH: False,
            CONF_SYNC_DEVICE_AREA: False,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
        },
        "esphome_controls": {
            "select:power_profile": "Always-On Wall / Desk",
            **POWER_PROFILE_SPECS["Always-On Wall / Desk"],
            "select:auto_brightness_mode": "Sun Synchronized",
            "select:day_brightness": "90%",
            "select:night_brightness": "70%",
        },
    },
]

_BUILTIN_GROUPS_BY_ID: dict[str, dict[str, Any]] = {
    g["id"]: g for g in DEFAULT_DEVICE_GROUPS
}


def canonical_control_key(domain: str, label: str) -> str:
    """Build a slug-independent control key ('select:wake_word_mode') for cross-device restore & group baselines."""
    clean = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return f"{domain.strip().lower()}:{clean}"


def is_behavior_esphome_control(ckey: str) -> bool:
    """Return True if a canonical ESPHome control key belongs to Tier 2 Operational Behavior."""
    return ckey not in APPEARANCE_ESPHOME_CONTROL_KEYS and ckey not in EXCLUDED_ESPHOME_CONTROL_KEYS


def capture_live_esphome_controls(
    hass: HomeAssistant,
    esphome_device_id: str | None,
    *,
    behavior_only: bool = False,
) -> dict[str, Any]:
    """Capture configurable ESPHome entities (select, switch, number) of the bound device."""
    esp_info = get_esphome_device_entities(hass, esphome_device_id)
    controls: dict[str, Any] = {}
    for sec in esp_info.get("sections", []):
        for item in sec.get("items", []):
            dom = str(item.get("domain") or "")
            if dom not in ("select", "switch", "number"):
                continue
            state_val = item.get("state")
            if state_val in (None, "unavailable", "unknown", ""):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            ckey = canonical_control_key(dom, name)
            if ckey in EXCLUDED_ESPHOME_CONTROL_KEYS:
                continue
            if behavior_only and not is_behavior_esphome_control(ckey):
                continue
            if dom == "number":
                try:
                    controls[ckey] = float(state_val)
                except (ValueError, TypeError):
                    controls[ckey] = state_val
            else:
                controls[ckey] = str(state_val)
    return controls


def _same_control_val(a: Any, b: Any) -> bool:
    """Compare two control values, treating numeric strings ('80' vs '80.0') and booleans/switches consistently."""
    sa = str(a).strip()
    sb = str(b).strip()
    if sa == sb:
        return True
    if sa.lower() in ("on", "true", "1") and sb.lower() in ("on", "true", "1"):
        return True
    if sa.lower() in ("off", "false", "0") and sb.lower() in ("off", "false", "0"):
        return True
    try:
        return abs(float(sa) - float(sb)) < 1e-4
    except (ValueError, TypeError):
        return False


async def apply_esphome_controls_to_device(
    hass: HomeAssistant, esphome_device_id: str | None, controls: dict[str, Any]
) -> int:
    """Apply a dictionary of canonical ESPHome control values ('domain:clean_name': val) to a live device."""
    if not isinstance(controls, dict) or not controls:
        return 0
    esp_info = get_esphome_device_entities(hass, esphome_device_id)
    by_ckey: dict[str, dict[str, Any]] = {}
    for sec in esp_info.get("sections", []):
        for item in sec.get("items", []):
            dom = str(item.get("domain") or "")
            if dom not in ("select", "switch", "number"):
                continue
            name = str(item.get("name") or "").strip()
            ent_id = str(item.get("entity_id") or "").strip()
            if not name or not ent_id:
                continue
            by_ckey[canonical_control_key(dom, name)] = item

    async def _apply_one(ckey: str, target_val: Any, force: bool = False) -> int:
        item = by_ckey.get(ckey)
        if item is None:
            return 0
        dom = str(item.get("domain") or "")
        ent_id = str(item.get("entity_id") or "").strip()
        cur_val = item.get("state")
        if not force and _same_control_val(target_val, cur_val):
            return 0
        if dom == "select":
            opts = item.get("options") or []
            if not opts or str(target_val) in opts:
                await async_execute_area_action(
                    hass, entity_id=ent_id, action="select", option=str(target_val)
                )
                return 1
        elif dom == "switch":
            want_on = str(target_val).lower() in ("on", "true", "1")
            await async_execute_area_action(
                hass,
                entity_id=ent_id,
                action="turn_on" if want_on else "turn_off",
            )
            return 1
        elif dom == "number":
            try:
                num_v = float(target_val)
                await async_execute_area_action(
                    hass, entity_id=ent_id, action="set_level", level=int(round(num_v))
                )
                return 1
            except (ValueError, TypeError):
                pass
        return 0

    applied = 0
    prof_name = str(controls.get("select:power_profile") or "").strip()
    prof_spec = POWER_PROFILE_SPECS.get(prof_name)

    # Apply the named Power Mode first so the firmware sets its 7 underlying sleep/wake controls atomically
    # without tripping mark_power_profile_custom_if_manual().
    if prof_spec is not None and "select:power_profile" in by_ckey:
        applied += await _apply_one("select:power_profile", prof_name, force=True)

    for ckey, target_val in controls.items():
        if ckey == "select:power_profile":
            continue
        if prof_spec is not None and ckey in prof_spec and _same_control_val(target_val, prof_spec[ckey]):
            continue
        applied += await _apply_one(ckey, target_val)

    return applied


def _serialize_device_snapshot(hass: HomeAssistant, coordinator: Any) -> dict[str, Any]:
    """Build a portable dictionary snapshot of a single device's Latter config & live ESPHome controls."""
    dev_cfg: dict[str, Any] = {}
    for k in DEVICE_CONFIG_EXPORT_KEYS:
        val = coordinator.get_opt(k)
        if val is not None:
            dev_cfg[k] = val
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
        "esphome_controls": capture_live_esphome_controls(hass, coordinator.esphome_device_id),
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
        if k in raw_global and raw_global[k] is not None:
            global_export[k] = raw_global[k]

    if clean_scope == "system":
        devices_map: dict[str, Any] = {}
        for coord in coordinators:
            devices_map[coord.device_slug] = _serialize_device_snapshot(hass, coord)
        label = name.strip() or f"System Backup ({dt_util.now().strftime('%Y-%m-%d %H:%M')})"
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

    # Device-scope restore (can restore to original device OR clone onto currently active device)
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


def _normalize_group_entry(raw: Mapping[str, Any] | dict[str, Any]) -> dict[str, Any]:
    """Normalize a single Device Group entry, merging built-in baseline defaults when not yet customized."""
    gid = str(raw.get("id") or "").strip()
    builtin_def = _BUILTIN_GROUPS_BY_ID.get(gid)
    base_dev = dict(builtin_def.get("device_config") or {}) if builtin_def else {}
    base_esp = dict(builtin_def.get("esphome_controls") or {}) if builtin_def else {}
    if isinstance(raw.get("device_config"), dict):
        for k, v in raw["device_config"].items():
            if k in GROUP_BEHAVIOR_DEVICE_KEYS and v is not None:
                base_dev[k] = v
    if isinstance(raw.get("esphome_controls"), dict):
        for k, v in raw["esphome_controls"].items():
            if is_behavior_esphome_control(str(k)) and v is not None:
                base_esp[str(k)] = v
    return {
        "id": gid,
        "name": str((builtin_def["name"] if builtin_def else raw.get("name")) or gid),
        "description": str(
            (builtin_def["description"] if builtin_def else raw.get("description")) or ""
        ),
        "builtin": gid in _BUILTIN_GROUPS_BY_ID,
        "device_config": base_dev,
        "esphome_controls": base_esp,
    }


def get_device_groups(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return the normalized Device Groups list (each with its Tier 2 baseline) from Global System Config."""
    domain_data = hass.data.get(DOMAIN, {})
    global_cfg = domain_data.get(DATA_GLOBAL_CONFIG) or {}
    raw_groups = global_cfg.get(CONF_DEVICE_GROUPS)
    if not isinstance(raw_groups, list) or not raw_groups:
        return [_normalize_group_entry(g) for g in DEFAULT_DEVICE_GROUPS]

    by_id: dict[str, dict[str, Any]] = {}
    custom_order: list[str] = []
    for item in raw_groups:
        if not isinstance(item, dict):
            continue
        gid = str(item.get("id") or "").strip()
        if not gid or gid == "sensors":
            continue
        by_id[gid] = _normalize_group_entry(item)
        if gid not in _BUILTIN_GROUPS_BY_ID and gid not in custom_order:
            custom_order.append(gid)

    out: list[dict[str, Any]] = []
    for bdef in DEFAULT_DEVICE_GROUPS:
        bid = bdef["id"]
        out.append(by_id.get(bid) or _normalize_group_entry(bdef))
    for cid in custom_order:
        out.append(by_id[cid])
    return out


def compute_device_group_sync_status(
    hass: HomeAssistant,
    coordinator: Any,
    groups: list[dict[str, Any]] | None = None,
) -> str:
    """Return 'in_sync', 'customized', or 'unmanaged' comparing the device's Tier 2 settings to its Group baseline."""
    if getattr(coordinator, "is_ble_tag", False):
        return "unmanaged"
    grp_id = str(getattr(coordinator, "device_group", "") or DEFAULT_DEVICE_GROUP).strip()
    if not grp_id or grp_id == DEFAULT_DEVICE_GROUP:
        return "unmanaged"
    group_list = groups if groups is not None else get_device_groups(hass)
    grp = next((g for g in group_list if g.get("id") == grp_id), None)
    if grp is None:
        return "unmanaged"

    base_dev = grp.get("device_config") or {}
    base_esp = grp.get("esphome_controls") or {}
    if not base_dev and not base_esp:
        return "unmanaged"

    is_roaming = bool(getattr(coordinator, "is_roaming_device", True))
    for k, want_v in base_dev.items():
        if k not in GROUP_BEHAVIOR_DEVICE_KEYS:
            continue
        if k in (CONF_SYNC_DEVICE_AREA, CONF_AREA_FOLLOW_DWELL_S) and not is_roaming:
            continue
        cur_v = coordinator.get_opt(k)
        if isinstance(want_v, bool):
            if bool(cur_v) != want_v:
                return "customized"
        elif not _same_control_val(cur_v, want_v):
            return "customized"

    live_esp = capture_live_esphome_controls(
        hass, coordinator.esphome_device_id, behavior_only=True
    )
    if live_esp:
        base_prof = str(base_esp.get("select:power_profile") or "").strip()
        live_prof = str(live_esp.get("select:power_profile") or "").strip()
        prof_spec = POWER_PROFILE_SPECS.get(base_prof)
        for ckey, want_val in base_esp.items():
            if ckey not in live_esp:
                continue
            if prof_spec is not None and ckey in prof_spec and live_prof == base_prof:
                continue
            if not _same_control_val(live_esp[ckey], want_val):
                return "customized"

    return "in_sync"


def seed_group_baseline_from_coordinator(
    hass: HomeAssistant,
    group: dict[str, Any],
    coordinator: Any,
) -> dict[str, Any]:
    """Capture a Device's Tier 2 Operational Behavior settings into `group` as its new baseline."""
    dev_cfg: dict[str, Any] = {}
    for k in GROUP_BEHAVIOR_DEVICE_KEYS:
        val = coordinator.get_opt(k)
        if val is not None:
            dev_cfg[k] = val
    esp_ctrls = capture_live_esphome_controls(
        hass, coordinator.esphome_device_id, behavior_only=True
    )
    return {
        **group,
        "device_config": dev_cfg,
        "esphome_controls": esp_ctrls,
    }


def update_group_baseline_esphome_control(
    group: dict[str, Any],
    ckey: str,
    value: Any,
) -> bool:
    """Update a single Tier 2 ESPHome control in `group`'s baseline; return True if the baseline changed."""
    if not is_behavior_esphome_control(ckey):
        return False
    esp_ctrls = dict(group.get("esphome_controls") or {})
    if ckey == "select:power_profile":
        prof_name = str(value).strip()
        esp_ctrls["select:power_profile"] = prof_name
        spec = POWER_PROFILE_SPECS.get(prof_name)
        if spec is not None:
            esp_ctrls.update(spec)
    else:
        esp_ctrls[ckey] = value
        cur_prof = str(esp_ctrls.get("select:power_profile") or "").strip()
        spec = POWER_PROFILE_SPECS.get(cur_prof)
        if spec is not None and ckey in spec and not _same_control_val(value, spec[ckey]):
            esp_ctrls["select:power_profile"] = "Custom"
    if esp_ctrls == (group.get("esphome_controls") or {}):
        return False
    group["esphome_controls"] = esp_ctrls
    return True


async def async_apply_group_baseline_to_coordinators(
    hass: HomeAssistant,
    group: dict[str, Any],
    targets: list[Any],
) -> dict[str, int]:
    """Apply a Device Group's Tier 2 Operational Baseline across one or more target coordinators."""
    dev_cfg = group.get("device_config") or {}
    esp_ctrls = group.get("esphome_controls") or {}
    updated_devices = 0
    updated_controls = 0

    for coord in targets:
        if getattr(coord, "is_ble_tag", False):
            continue
        merged: dict[str, Any] = dict(coord.device_data)
        is_roaming = bool(getattr(coord, "is_roaming_device", True))
        changed_cfg = False
        for k in GROUP_BEHAVIOR_DEVICE_KEYS:
            if k not in dev_cfg or dev_cfg[k] is None:
                continue
            if k in (CONF_SYNC_DEVICE_AREA, CONF_AREA_FOLLOW_DWELL_S) and not is_roaming:
                continue
            if merged.get(k) != dev_cfg[k]:
                merged[k] = dev_cfg[k]
                changed_cfg = True
        if changed_cfg:
            coord.update_device_config(merged)
            await coord.async_apply_options()
        coord.async_notify_listeners()
        updated_devices += 1
        if isinstance(esp_ctrls, dict) and esp_ctrls:
            updated_controls += await apply_esphome_controls_to_device(
                hass, coord.esphome_device_id, esp_ctrls
            )

    if updated_controls > 0:
        await asyncio.sleep(0.2)
        for coord in targets:
            coord.async_notify_listeners()

    return {
        "updated_devices": updated_devices,
        "updated_controls": updated_controls,
    }
