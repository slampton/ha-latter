"""System & Device Backup/Restore Vault and Reusable Device Profiles Engine for Latter."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import re
import secrets
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    BACKUPS_STORAGE_KEY,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_GROUPS,
    CONF_DEVICE_PROFILE,
    CONF_DEVICE_SLUG,
    CONF_DISPLAY_SHAPE,
    CONF_DOCK_APPS,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PRESENCE_ENTITY,
    CONF_SAVED_PROFILES,
    CONF_SITE_ID,
    CONF_SYNC_DEVICE_AREA,
    CONF_VPN_CLIENT_IP,
    CONF_VPN_ENABLED,
    CONF_VPN_HOTSPOT_SSID,
    CONF_VPN_PRESHARED_KEY,
    CONF_VPN_PRIVATE_KEY,
    CONF_VPN_PUBLIC_KEY,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    DATA_BACKUPS_STORE,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DEFAULT_DEVICE_GROUP,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    STORAGE_VERSION,
)
from .room_engine import async_execute_room_action, get_esphome_device_entities

_LOGGER = logging.getLogger(__name__)

MAX_VAULT_BACKUPS = 25

DEVICE_CONFIG_EXPORT_KEYS: tuple[str, ...] = (
    CONF_DEVICE_SLUG,
    CONF_DEVICE_PROFILE,
    CONF_DEVICE_GROUP,
    CONF_DISPLAY_SHAPE,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEFAULT_AREA,
    CONF_NATIVE_BLE_TRACKING,
    CONF_BLE_BEACON_UUID,
    CONF_PRESENCE_ENTITY,
    CONF_BLE_AUTO_SWITCH,
    CONF_SYNC_DEVICE_AREA,
    CONF_AREA_HANDOFF,
    CONF_DOCK_APPS,
    CONF_WALLPAPER_SOURCE,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_ART_SIZE,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_SITE_ID,
    CONF_VPN_ENABLED,
    CONF_VPN_CLIENT_IP,
    CONF_VPN_PRIVATE_KEY,
    CONF_VPN_PUBLIC_KEY,
    CONF_VPN_PRESHARED_KEY,
    CONF_VPN_HOTSPOT_SSID,
)

VPN_SECRET_KEYS: tuple[str, ...] = (
    CONF_VPN_PRIVATE_KEY,
    CONF_VPN_PRESHARED_KEY,
)

PROFILE_DEVICE_KEYS: tuple[str, ...] = (
    CONF_DEVICE_PROFILE,
    CONF_DISPLAY_SHAPE,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_NATIVE_BLE_TRACKING,
    CONF_BLE_AUTO_SWITCH,
    CONF_SYNC_DEVICE_AREA,
    CONF_AREA_HANDOFF,
    CONF_DOCK_APPS,
    CONF_WALLPAPER_SOURCE,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_ART_SIZE,
    CONF_DEVICE_CUSTOM_COLOR,
)

DEFAULT_DEVICE_GROUPS: list[dict[str, str]] = [
    {"id": "handhelds", "name": "Handheld Displays", "description": "Battery-powered mobile smart displays"},
    {"id": "bedrooms", "name": "Bedrooms", "description": "Nightstand & bedroom companion devices"},
    {"id": "common_areas", "name": "Common Areas", "description": "Living room, kitchen & family room devices"},
    {"id": "wall_panels", "name": "Wall Panels", "description": "Stationary mounted control panels"},
]

BUILTIN_STARTER_PROFILES: list[dict[str, Any]] = [
    {
        "id": "preset_handheld_standard",
        "name": "Standard Handheld (Balanced)",
        "archetype": "mobile_display",
        "description": "Balanced battery life, Docked-Only wake word, 30s battery screen timeout, and full Home dock.",
        "device_config": {
            CONF_DEVICE_PROFILE: "mobile_display",
            CONF_DISPLAY_SHAPE: "circle",
            CONF_DEFAULT_PAGE_SIZE: 3,
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_HANDOFF: False,
            CONF_DOCK_APPS: "music,alarm,room,remote,games,tools",
            CONF_ART_SIZE: 466,
        },
        "esphome_controls": {
            "select:wake_word_mode": "Docked Only",
            "select:battery_screen_timeout": "30s",
            "select:docked_idle_timeout": "1 min",
            "select:battery_hibernate_timeout": "15 min",
            "select:pickup_to_wake": "Always On",
            "select:tap_to_wake": "Docked Only",
            "select:auto_brightness_mode": "Sun Synchronized",
            "select:day_brightness": "90%",
            "select:night_brightness": "70%",
            "switch:docked_screensaver": "on",
            "switch:ble_presence_beacon": "on",
        },
    },
    {
        "id": "preset_nightstand_quiet",
        "name": "Bedroom Nightstand (Quiet / Dim)",
        "archetype": "mobile_display",
        "description": "Dimmed night brightness (60%), Ambient Clock screensaver, 15s battery timeout, and quieter 50% alerts.",
        "device_config": {
            CONF_DEVICE_PROFILE: "mobile_display",
            CONF_DISPLAY_SHAPE: "circle",
            CONF_DEFAULT_PAGE_SIZE: 3,
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_HANDOFF: False,
            CONF_DOCK_APPS: "music,alarm,room,remote,tools",
            CONF_ART_SIZE: 466,
        },
        "esphome_controls": {
            "select:wake_word_mode": "Docked Only",
            "select:battery_screen_timeout": "15s",
            "select:docked_idle_timeout": "30s",
            "select:screensaver_style": "Ambient Clock",
            "select:auto_brightness_mode": "Sun Synchronized",
            "select:day_brightness": "80%",
            "select:night_brightness": "60%",
            "switch:docked_screensaver": "on",
            "number:alert_volume": 50,
        },
    },
    {
        "id": "preset_wall_panel",
        "name": "Stationary Wall / Desk Panel",
        "archetype": "stationary_display",
        "description": "Always-On wake word, Tap-to-Wake Always On, 5 min idle timeout, and stationary room assignment.",
        "device_config": {
            CONF_DEVICE_PROFILE: "stationary_display",
            CONF_NATIVE_BLE_TRACKING: False,
            CONF_BLE_AUTO_SWITCH: False,
            CONF_SYNC_DEVICE_AREA: False,
            CONF_AREA_HANDOFF: False,
        },
        "esphome_controls": {
            "select:wake_word_mode": "Always On",
            "select:tap_to_wake": "Always On",
            "select:docked_idle_timeout": "5 min",
            "select:battery_hibernate_timeout": "Disabled",
            "switch:ble_presence_beacon": "off",
        },
    },
]


def _canonical_control_key(domain: str, label: str) -> str:
    """Build a slug-independent control key ('select:wake_word_mode') for cross-device restore & profiles."""
    clean = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return f"{domain.strip().lower()}:{clean}"


def capture_live_esphome_controls(hass: HomeAssistant, device_slug: str) -> dict[str, Any]:
    """Capture all configurable ESPHome entities (select, switch, number) for a device."""
    esp_info = get_esphome_device_entities(hass, device_slug)
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
            ckey = _canonical_control_key(dom, name)
            if dom == "number":
                try:
                    controls[ckey] = float(state_val)
                except (ValueError, TypeError):
                    controls[ckey] = state_val
            else:
                controls[ckey] = str(state_val)
    return controls


async def apply_esphome_controls_to_device(
    hass: HomeAssistant, device_slug: str, controls: dict[str, Any]
) -> int:
    """Apply a dictionary of canonical ESPHome control values ('domain:clean_name': val) to a live device."""
    if not isinstance(controls, dict) or not controls:
        return 0
    esp_info = get_esphome_device_entities(hass, device_slug)
    applied = 0
    for sec in esp_info.get("sections", []):
        for item in sec.get("items", []):
            dom = str(item.get("domain") or "")
            if dom not in ("select", "switch", "number"):
                continue
            name = str(item.get("name") or "").strip()
            ent_id = str(item.get("entity_id") or "").strip()
            if not name or not ent_id:
                continue
            ckey = _canonical_control_key(dom, name)
            if ckey not in controls:
                continue
            target_val = controls[ckey]
            cur_val = item.get("state")
            if str(target_val) == str(cur_val):
                continue

            if dom == "select":
                opts = item.get("options") or []
                if not opts or str(target_val) in opts:
                    await async_execute_room_action(
                        hass, entity_id=ent_id, action="select", option=str(target_val)
                    )
                    applied += 1
            elif dom == "switch":
                want_on = str(target_val).lower() in ("on", "true", "1")
                await async_execute_room_action(
                    hass,
                    entity_id=ent_id,
                    action="turn_on" if want_on else "turn_off",
                )
                applied += 1
            elif dom == "number":
                try:
                    num_v = float(target_val)
                    await async_execute_room_action(
                        hass, entity_id=ent_id, action="set_level", level=int(round(num_v))
                    )
                    applied += 1
                except (ValueError, TypeError):
                    pass
    return applied


async def _async_get_backups_store(hass: HomeAssistant) -> tuple[Store[dict[str, Any]], dict[str, Any]]:
    """Load or initialize the In-Integration Backup Vault (`.storage/latter.backups`)."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if DATA_BACKUPS_STORE not in domain_data:
        store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, BACKUPS_STORAGE_KEY)
        domain_data[DATA_BACKUPS_STORE] = store
        loaded = await store.async_load()
        domain_data["backups_data"] = (
            loaded if isinstance(loaded, dict) and "snapshots" in loaded else {"snapshots": []}
        )
    return domain_data[DATA_BACKUPS_STORE], domain_data["backups_data"]


def _serialize_device_snapshot(
    hass: HomeAssistant, coordinator: Any, include_vpn_secrets: bool = True
) -> dict[str, Any]:
    """Build a portable dictionary snapshot of a single device's Latter config & live ESPHome controls."""
    dev_cfg: dict[str, Any] = {}
    for k in DEVICE_CONFIG_EXPORT_KEYS:
        if not include_vpn_secrets and k in VPN_SECRET_KEYS:
            continue
        val = coordinator.get_opt(k)
        if val is not None:
            dev_cfg[k] = val
    dev_cfg.setdefault(CONF_DEVICE_GROUP, DEFAULT_DEVICE_GROUP)
    return {
        "device_slug": coordinator.device_slug,
        "title": coordinator.device_slug.replace("_", " ").title(),
        "device_profile": coordinator.device_profile,
        "device_group": str(dev_cfg.get(CONF_DEVICE_GROUP) or DEFAULT_DEVICE_GROUP),
        "display_shape": coordinator.display_shape,
        "active_area_id": coordinator.active_area_id or "",
        "active_speaker": coordinator.active_speaker,
        "active_remote_slot": coordinator.active_remote_slot,
        "device_config": dev_cfg,
        "esphome_controls": capture_live_esphome_controls(hass, coordinator.device_slug),
    }


def build_backup_bundle(
    hass: HomeAssistant,
    scope: str,
    coordinators: list[Any],
    target_coordinator: Any | None = None,
    name: str = "",
    include_vpn_secrets: bool = True,
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
            devices_map[coord.device_slug] = _serialize_device_snapshot(
                hass, coord, include_vpn_secrets=include_vpn_secrets
            )
        label = name.strip() or f"System Backup ({dt_util.now().strftime('%Y-%m-%d %H:%M')})"
        return {
            "id": backup_id,
            "schema": "latter.backup.v1",
            "version": INTEGRATION_VERSION,
            "scope": "system",
            "name": label,
            "created_at": now_iso,
            "target_device": "all",
            "device_count": len(devices_map),
            "include_vpn_secrets": bool(include_vpn_secrets),
            "global_config": global_export,
            "devices": devices_map,
        }

    coord = target_coordinator or (coordinators[0] if coordinators else None)
    if coord is None:
        raise ValueError("No target device coordinator available for device backup")
    dev_snap = _serialize_device_snapshot(
        hass, coord, include_vpn_secrets=include_vpn_secrets
    )
    label = (
        name.strip()
        or f"{dev_snap['title']} ({dt_util.now().strftime('%Y-%m-%d %H:%M')})"
    )
    return {
        "id": backup_id,
        "schema": "latter.backup.v1",
        "version": INTEGRATION_VERSION,
        "scope": "device",
        "name": label,
        "created_at": now_iso,
        "target_device": coord.device_slug,
        "device_count": 1,
        "include_vpn_secrets": bool(include_vpn_secrets),
        "device": dev_snap,
    }


async def async_list_vault_backups(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return metadata summaries for all snapshots stored in the In-Integration Vault."""
    _store, data = await _async_get_backups_store(hass)
    snaps = data.get("snapshots") or []
    summaries: list[dict[str, Any]] = []
    for s in snaps:
        if not isinstance(s, dict) or not s.get("id"):
            continue
        dev_obj = s.get("device") or {}
        ctrl_count = len(dev_obj.get("esphome_controls") or {}) if s.get("scope") == "device" else sum(
            len((d or {}).get("esphome_controls") or {}) for d in (s.get("devices") or {}).values()
        )
        summaries.append(
            {
                "id": s["id"],
                "name": s.get("name", s["id"]),
                "scope": s.get("scope", "device"),
                "created_at": s.get("created_at", ""),
                "target_device": s.get("target_device", ""),
                "device_count": int(s.get("device_count") or 1),
                "control_count": ctrl_count,
                "version": s.get("version", INTEGRATION_VERSION),
            }
        )
    return summaries


async def async_create_vault_backup(
    hass: HomeAssistant,
    scope: str,
    coordinators: list[Any],
    target_coordinator: Any | None = None,
    name: str = "",
    include_vpn_secrets: bool = True,
) -> dict[str, Any]:
    """Create a new System or Device snapshot and save it to `.storage/latter.backups`."""
    store, data = await _async_get_backups_store(hass)
    bundle = build_backup_bundle(
        hass=hass,
        scope=scope,
        coordinators=coordinators,
        target_coordinator=target_coordinator,
        name=name,
        include_vpn_secrets=include_vpn_secrets,
    )
    snaps: list[dict[str, Any]] = list(data.get("snapshots") or [])
    snaps.insert(0, bundle)
    data["snapshots"] = snaps[:MAX_VAULT_BACKUPS]
    await store.async_save(data)
    return bundle


async def async_get_vault_backup(hass: HomeAssistant, backup_id: str) -> dict[str, Any] | None:
    """Retrieve a full backup bundle from `.storage/latter.backups` by ID."""
    _store, data = await _async_get_backups_store(hass)
    for s in data.get("snapshots") or []:
        if isinstance(s, dict) and s.get("id") == backup_id:
            return s
    return None


async def async_delete_vault_backup(hass: HomeAssistant, backup_id: str) -> bool:
    """Delete a snapshot from `.storage/latter.backups`."""
    store, data = await _async_get_backups_store(hass)
    before = len(data.get("snapshots") or [])
    data["snapshots"] = [
        s for s in (data.get("snapshots") or [])
        if isinstance(s, dict) and s.get("id") != backup_id
    ]
    if len(data["snapshots"]) != before:
        await store.async_save(data)
        return True
    return False


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

    merged: dict[str, Any] = {
        **coord.entry.data,
        **(coord.entry.options or {}),
    }
    for k in DEVICE_CONFIG_EXPORT_KEYS:
        if k in incoming_cfg and incoming_cfg[k] is not None:
            merged[k] = incoming_cfg[k]

    hass.config_entries.async_update_entry(
        coord.entry, data=merged, options=merged
    )

    if dev_snap.get("active_area_id"):
        coord.active_area_id = str(dev_snap["active_area_id"])
    if isinstance(dev_snap.get("active_remote_slot"), int):
        coord.active_remote_slot = max(1, min(4, int(dev_snap["active_remote_slot"])))

    coord._bind_wallpaper_cycle_timer()
    coord._schedule_persist_runtime_state()
    coord._notify_listeners()

    applied_controls = 0
    if restore_esphome_entities and isinstance(dev_snap.get("esphome_controls"), dict):
        applied_controls = await apply_esphome_controls_to_device(
            hass, coord.device_slug, dev_snap["esphome_controls"]
        )
    return applied_controls


async def async_restore_backup_bundle(
    hass: HomeAssistant,
    bundle: dict[str, Any],
    coordinators: list[Any],
    target_coordinator: Any | None = None,
    restore_esphome_entities: bool = True,
) -> dict[str, Any]:
    """Restore a System or Device backup bundle (from Vault or uploaded Computer JSON file)."""
    if not isinstance(bundle, dict) or bundle.get("schema") != "latter.backup.v1":
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
        snap_slug = str(dev_snap.get("device_slug") or "")
        coord = next((c for c in coordinators if c.device_slug == snap_slug), None)
    if coord is None and coordinators:
        coord = coordinators[0]
    if coord is None:
        raise ValueError("No target device available to restore onto")

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


def get_device_groups_and_profiles(hass: HomeAssistant) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Return (device_groups, saved_profiles) from Global Household Config, seeded with defaults."""
    domain_data = hass.data.get(DOMAIN, {})
    global_cfg = domain_data.get(DATA_GLOBAL_CONFIG) or {}

    raw_groups = global_cfg.get(CONF_DEVICE_GROUPS)
    groups: list[dict[str, str]] = (
        list(raw_groups)
        if isinstance(raw_groups, list) and raw_groups
        else list(DEFAULT_DEVICE_GROUPS)
    )

    raw_profiles = global_cfg.get(CONF_SAVED_PROFILES)
    profiles: list[dict[str, Any]] = (
        list(raw_profiles)
        if isinstance(raw_profiles, list) and raw_profiles
        else list(BUILTIN_STARTER_PROFILES)
    )
    return groups, profiles


def capture_profile_from_coordinator(
    hass: HomeAssistant,
    coordinator: Any,
    name: str,
    description: str = "",
) -> dict[str, Any]:
    """Capture a reusable Device Profile from a live coordinator's settings and ESPHome entities."""
    profile_id = f"prof_{int(dt_util.now().timestamp())}_{secrets.token_hex(2)}"
    dev_cfg: dict[str, Any] = {}
    for k in PROFILE_DEVICE_KEYS:
        val = coordinator.get_opt(k)
        if val is not None:
            dev_cfg[k] = val
    return {
        "id": profile_id,
        "name": name.strip() or f"{coordinator.device_slug.replace('_', ' ').title()} Profile",
        "archetype": coordinator.device_profile,
        "description": description.strip() or f"Captured from {coordinator.device_slug}",
        "created_at": dt_util.now().isoformat(timespec="seconds"),
        "device_config": dev_cfg,
        "esphome_controls": capture_live_esphome_controls(hass, coordinator.device_slug),
    }


async def async_apply_profile_to_coordinators(
    hass: HomeAssistant,
    profile: dict[str, Any],
    targets: list[Any],
) -> dict[str, int]:
    """Apply a reusable Device Profile across one or more target coordinators (single device or group)."""
    dev_cfg = profile.get("device_config") or {}
    esp_ctrls = profile.get("esphome_controls") or {}
    updated_devices = 0
    updated_controls = 0

    for coord in targets:
        merged: dict[str, Any] = {
            **coord.entry.data,
            **(coord.entry.options or {}),
        }
        for k in PROFILE_DEVICE_KEYS:
            if k in dev_cfg and dev_cfg[k] is not None:
                merged[k] = dev_cfg[k]
        hass.config_entries.async_update_entry(
            coord.entry, data=merged, options=merged
        )
        coord._bind_wallpaper_cycle_timer()
        coord._notify_listeners()
        updated_devices += 1
        if isinstance(esp_ctrls, dict) and esp_ctrls:
            updated_controls += await apply_esphome_controls_to_device(
                hass, coord.device_slug, esp_ctrls
            )

    if updated_controls > 0:
        await asyncio.sleep(0.2)
        for coord in targets:
            coord._notify_listeners()

    return {
        "updated_devices": updated_devices,
        "updated_controls": updated_controls,
    }