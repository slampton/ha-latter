"""Studio WebSocket `latter/system/command` handlers across System config, Groups, Photos, and Presence."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from datetime import timedelta
import logging
import math
import re
from typing import Any, Final
from urllib.parse import quote

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util import dt as dt_util
import probatio as vol

from ..areas.registry import area_illuminance_sensor_choices, resolve_area_ambient_light
from ..const import (
    CONF_AREA_FUSION_CONFIG,
    CONF_AREA_ILLUMINANCE_CONFIG,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AREA_SIGNATURES,
    CONF_BLE_CATEGORY,
    CONF_BLE_SCANNER_OFFSETS,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_GROUPS,
    CONF_ESPHOME_DEVICE_ID,
    CONF_IGNORED_DISCOVERED_DEVICES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_IDS,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SECURITY_PIN,
    CONF_SECURITY_PIN_HASH,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    DEFAULT_BLE_CATEGORY,
    DEFAULT_DEVICE_GROUP,
    DOMAIN,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
    normalize_device_slug,
)
from ..coordinator import LatterCoordinator
from ..doorbell import async_execute_doorbell_intercom
from ..groups.device_groups import (
    DEFAULT_DEVICE_GROUPS,
    GROUP_ALL_DEVICE_KEYS,
    async_apply_group_baseline_to_coordinators,
    coordinator_supports_group_key,
    default_group_baseline_config,
    get_device_groups,
    reset_builtin_group_entry,
    resolve_behavior_key_value,
    seed_group_baseline_from_coordinator,
)
from ..hub_registry import (
    get_domain_data,
    get_global_config,
    get_latter_system,
    get_system_config_lock,
    get_system_config_rev,
    iter_coordinators,
    notify_studio_subscribers,
)
from ..hub_sync import (
    async_rotate_hub_hmac_secret,
    async_save_and_broadcast_global_config,
)
from ..identity import (
    bound_elsewhere,
    device_entities,
    device_title,
    device_unique_id,
    get_bound_esphome_device,
    is_esphome_device,
    is_latter_compatible_esphome_device,
)
from ..presence.area_fusion import area_fusion_sensor_choices
from ..presence.ble_fabric import get_ble_fabric
from ..protocol_policy import hash_security_pin
from ..wallpapers.media_import import (
    import_media_photos_sync,
    list_media_folder_sync,
)
from ..wallpapers.store import (
    bulk_update_photos,
    create_collection,
    delete_collection,
    delete_photo,
    rename_collection,
    update_photo_metadata,
)
from .device_commands import (
    CommandHandler,
    evaluate_bedtime_if_ready,
    validate_device_camera_lists,
    validate_remote_group_choice,
)
from .payload import (
    StudioCommandError,
    is_coordinator_online_for_studio,
    log_studio_event,
)
from .settings_cleaners import (
    MAX_IGNORED_DISCOVERED,
    clean_announcement,
    clean_area_fusion,
    clean_area_illuminance,
    clean_device_settings,
    clean_system_settings,
    system_settings_view,
)
from .state_gates import find_by_subentry_id

_LOGGER = logging.getLogger(__name__)

_GROUP_NAME_MAX_LEN: Final = 64
_GROUP_DESC_MAX_LEN: Final = 200
_GROUP_ID_MAX_LEN: Final = 48
_GROUP_PREFIX_LEN: Final = 6
_MEDIA_THUMB_DIM: Final = 160
_CAMERA_PREVIEW_TTL_S: Final = 600
_SCANNER_OFFSET_ABS_MAX: Final = 25.0
_SCANNER_OFFSET_ZERO_EPS: Final = 0.1
_DARK_LUX_MAX: Final = 500.0
_BRIGHT_LUX_MAX: Final = 100000.0
_BRIGHT_LUX_MIN_DELTA: Final = 5.0
_LUX_DECIMAL_CUTOFF: Final = 10.0
_MIN_POS_MEAN_SAMPLES: Final = 4
_RECORDER_CALIBRATION_DAYS: Final = 7
_UPDATE_ENTITY_TIMEOUT_S: Final = 30
_IBEACON_PREFIX: Final = "ibeacon:"


# ---------------------------------------------------------------------------
# System Settings, Device Groups, Batch Controls & Security PIN Handlers
# ---------------------------------------------------------------------------


async def _cmd_save_system_config(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    updates = clean_system_settings(dict(body.get("config") or {}))
    expected_rev = body.get("expected_config_rev")
    async with get_system_config_lock(hass):
        if expected_rev is not None and int(expected_rev) != get_system_config_rev(
            hass
        ):
            raise StudioCommandError(
                "conflict",
                "Settings changed in another session; refreshed latest state.",
            )
        live_cfg = get_global_config(hass)
        changed = {k: v for k, v in updates.items() if live_cfg.get(k) != v}
        if changed:
            await async_save_and_broadcast_global_config(hass, changed)
    log_studio_event(hass, "INFO", "studio", "Saved System settings")


async def _cmd_create_device_group(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    g_name = str(body.get("name") or "").strip()[:_GROUP_NAME_MAX_LEN]
    g_desc = str(body.get("description") or "").strip()[:_GROUP_DESC_MAX_LEN]
    if not g_name:
        raise StudioCommandError("invalid_format", "A Device Group needs a name")
    g_id = (
        re.sub(r"[^a-z0-9]+", "_", g_name.lower()).strip("_")[:_GROUP_ID_MAX_LEN]
        or "group"
    )
    if g_id in (
        "auto",
        DEFAULT_DEVICE_GROUP,
        "all",
        "online",
        "roaming",
        "stationary",
    ):
        raise StudioCommandError(
            "invalid_format", f"'{g_name}' is a reserved Device Group name"
        )
    source_sub_id = str(body.get("source_subentry_id") or "").strip()
    assign_source = bool(body.get("assign_source"))
    include_display = bool(body.get("include_display", False))
    include_interface = bool(body.get("include_interface", False))
    source_coord: LatterCoordinator | None = None
    if source_sub_id:
        source_coord = find_by_subentry_id(iter_coordinators(hass), source_sub_id)
        if source_coord is None or source_coord.is_ble_tag:
            raise StudioCommandError(
                "not_found", f"No Latter Device with subentry_id '{source_sub_id}'"
            )

    async with get_system_config_lock(hass):
        groups = get_device_groups(hass)
        if any(g.get("id") == g_id for g in groups):
            raise StudioCommandError(
                "already_configured", f"A group named '{g_name}' already exists"
            )
        new_group: dict[str, Any] = {
            "id": g_id,
            "name": g_name,
            "description": g_desc or f"Custom group ({g_name})",
            "builtin": False,
            "include_display": include_display,
            "include_interface": include_interface,
            "device_config": default_group_baseline_config(
                include_display=include_display,
                include_interface=include_interface,
            ),
        }
        if source_coord is not None:
            seed_group_baseline_from_coordinator(hass, new_group, source_coord)

        groups.append(new_group)
        await async_save_and_broadcast_global_config(
            hass, {CONF_DEVICE_GROUPS: groups}
        )
    if assign_source and source_coord is not None:
        async with source_coord.config_lock:
            source_coord.update_device_config(
                {**source_coord.device_data, CONF_DEVICE_GROUP: g_id},
                preserve_group=True,
            )
        source_coord.async_notify_listeners()


async def _cmd_delete_device_group(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    g_id = str(body.get("group_id") or "").strip()
    if any(b["id"] == g_id for b in DEFAULT_DEVICE_GROUPS):
        raise StudioCommandError(
            "not_allowed", "Built-in Device Groups cannot be deleted"
        )
    async with get_system_config_lock(hass):
        groups = [g for g in get_device_groups(hass) if g.get("id") != g_id]
        await async_save_and_broadcast_global_config(
            hass, {CONF_DEVICE_GROUPS: groups}
        )
    for c in iter_coordinators(hass):
        if (
            not c.is_ble_tag
            and str(c.get_opt(CONF_DEVICE_GROUP) or "").strip() == g_id
        ):
            async with c.config_lock:
                c.update_device_config(
                    {**c.device_data, CONF_DEVICE_GROUP: DEFAULT_DEVICE_GROUP}
                )
            c.async_notify_listeners()


def _apply_group_scope_and_seed(
    hass: HomeAssistant,
    grp: dict[str, Any],
    body: dict[str, Any],
    all_coords: list[LatterCoordinator],
) -> bool:
    """Update scope flags and optional source-device seeding on `grp`, returning `did_update`."""
    did_update = False
    if "include_display" in body:
        grp["include_display"] = bool(body["include_display"])
        did_update = True
    if "include_interface" in body:
        grp["include_interface"] = bool(body["include_interface"])
        did_update = True
    if "include_display" in body or "include_interface" in body:
        seeded_defs = default_group_baseline_config(
            include_display=bool(grp.get("include_display", False)),
            include_interface=bool(grp.get("include_interface", False)),
        )
        cur_cfg = dict(grp.get("device_config") or {})
        for k, v in seeded_defs.items():
            cur_cfg.setdefault(k, v)
        grp["device_config"] = cur_cfg

    source_sub_id = str(body.get("source_subentry_id") or "").strip()
    raw_copy_keys = body.get("copy_keys")
    if source_sub_id:
        source_coord = find_by_subentry_id(all_coords, source_sub_id)
        if source_coord is None or source_coord.is_ble_tag:
            raise StudioCommandError(
                "not_found", f"No Latter Device with subentry_id '{source_sub_id}'"
            )
        only_keys: list[str] | None = None
        if raw_copy_keys is not None:
            if not isinstance(raw_copy_keys, list):
                raise StudioCommandError("invalid_format", "copy_keys must be a list")
            only_keys = [
                str(k).strip()
                for k in raw_copy_keys
                if str(k).strip() in GROUP_ALL_DEVICE_KEYS
            ]
            if not only_keys:
                raise StudioCommandError(
                    "invalid_format", "copy_keys contains no supported group keys"
                )
        seed_group_baseline_from_coordinator(
            hass, grp, source_coord, only_keys=only_keys
        )
        did_update = True
    return did_update


def _apply_group_config_updates(
    grp: dict[str, Any],
    raw_updates: dict[str, Any],
    global_cfg: dict[str, Any],
) -> bool:
    """Validate and merge `raw_updates` into `grp['device_config']`."""
    filtered = {k: v for k, v in raw_updates.items() if k in GROUP_ALL_DEVICE_KEYS}
    if not filtered:
        raise StudioCommandError(
            "invalid_format",
            "No supported Device Group baseline settings in payload",
        )
    cleaned = clean_device_settings(filtered, current=grp.get("device_config"))
    validate_remote_group_choice(cleaned, global_cfg)
    validate_device_camera_lists(cleaned, global_cfg)
    group_updates = {k: v for k, v in cleaned.items() if k in GROUP_ALL_DEVICE_KEYS}
    if not group_updates:
        return False
    dev_cfg = dict(
        grp.get("device_config")
        or default_group_baseline_config(
            include_display=bool(grp.get("include_display", False)),
            include_interface=bool(grp.get("include_interface", False)),
        )
    )
    dev_cfg.update(group_updates)
    grp["device_config"] = dev_cfg
    return True


def _replace_builtin_group_with_default(
    groups: list[dict[str, Any]], g_id: str
) -> dict[str, Any]:
    """Reset built-in `g_id` in `groups` in place and return the reset entry."""
    reset_grp = reset_builtin_group_entry(g_id)
    if reset_grp is None:
        raise StudioCommandError(
            "not_allowed",
            "Only built-in Device Groups can be reset to preset defaults",
        )
    for idx_g, existing_g in enumerate(groups):
        if existing_g.get("id") == g_id:
            groups[idx_g] = reset_grp
            break
    return reset_grp


async def _cmd_update_group_baseline(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    g_id = str(body.get("group_id") or "").strip()
    is_reset = body.get("reset_to_default") is True
    async with get_system_config_lock(hass):
        groups = get_device_groups(hass)
        grp = next((g for g in groups if g.get("id") == g_id), None)
        if grp is None:
            raise StudioCommandError("not_found", f"Unknown Device Group '{g_id}'")

        all_coords = list(iter_coordinators(hass))
        member_targets = [
            c for c in all_coords if not c.is_ble_tag and c.device_group == g_id
        ]

        if is_reset:
            grp = _replace_builtin_group_with_default(groups, g_id)
        else:
            did_update = _apply_group_scope_and_seed(hass, grp, body, all_coords)
            raw_updates = dict(body.get("config") or {})
            if raw_updates and _apply_group_config_updates(grp, raw_updates, global_cfg):
                did_update = True
            if not did_update:
                raise StudioCommandError(
                    "invalid_format",
                    "Provide baseline settings, scope toggles, or a source Device to update the group",
                )
        await async_save_and_broadcast_global_config(
            hass, {CONF_DEVICE_GROUPS: groups}
        )

    if member_targets:
        await async_apply_group_baseline_to_coordinators(hass, grp, member_targets)
    await evaluate_bedtime_if_ready(hass)
    verb = "Reset preset defaults" if is_reset else "Updated baseline"
    log_studio_event(
        hass,
        "INFO",
        "studio",
        f"{verb} for '{grp.get('name', g_id)}' ({len(member_targets)} Device(s))",
    )


def _extract_batch_updates_payload(
    body: dict[str, Any],
    all_coords_full: list[LatterCoordinator],
    global_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Resolve and validate batch updates from `config` and optional `source_subentry_id`."""
    raw_updates = dict(body.get("config") or {})
    source_sub_id = str(body.get("source_subentry_id") or "").strip()
    raw_copy_keys = body.get("copy_keys")
    allowed_keys = set(GROUP_ALL_DEVICE_KEYS) | {"bedtime_active", "do_not_disturb"}

    if source_sub_id:
        source_coord = find_by_subentry_id(all_coords_full, source_sub_id)
        if source_coord is None or source_coord.is_ble_tag:
            raise StudioCommandError(
                "not_found", f"No Latter Device with subentry_id '{source_sub_id}'"
            )
        if not isinstance(raw_copy_keys, list) or not raw_copy_keys:
            raise StudioCommandError(
                "invalid_format",
                "copy_keys is required when copying batch settings from a Device",
            )
        src_data = source_coord.device_data
        for raw_k in raw_copy_keys:
            ck = str(raw_k or "").strip()
            if ck in allowed_keys and coordinator_supports_group_key(
                source_coord, ck
            ):
                raw_updates[ck] = (
                    source_coord.wallpaper_source
                    if ck == CONF_WALLPAPER_SOURCE
                    else resolve_behavior_key_value(src_data, ck)
                )

    filtered = {k: v for k, v in raw_updates.items() if k in allowed_keys}
    if not filtered:
        raise StudioCommandError(
            "invalid_format", "No supported batch device settings in payload"
        )
    validated_once = clean_device_settings(filtered, current=None)
    validate_remote_group_choice(validated_once, global_cfg)
    validate_device_camera_lists(validated_once, global_cfg)
    return filtered


def _select_batch_target_coordinators(
    hass: HomeAssistant,
    all_coords: list[LatterCoordinator],
    raw_target: str,
) -> list[LatterCoordinator]:
    """Filter non-BLE coordinators matching `raw_target`."""
    if raw_target == "all":
        return all_coords
    if raw_target == "online":
        return [c for c in all_coords if is_coordinator_online_for_studio(hass, c)]
    if raw_target == "roaming":
        return [c for c in all_coords if c.is_roaming_device]
    if raw_target == "stationary":
        return [c for c in all_coords if not c.is_roaming_device]
    target_id = (
        raw_target[_GROUP_PREFIX_LEN:].strip()
        if raw_target.startswith("group:")
        else raw_target
    )
    return [c for c in all_coords if c.device_group == target_id]


async def _async_apply_batch_to_coordinator(
    coord: LatterCoordinator, filtered: dict[str, Any]
) -> None:
    """Apply supported `filtered` batch settings to a single `coord` under `config_lock`."""
    dev_filtered = {
        k: v for k, v in filtered.items() if coordinator_supports_group_key(coord, k)
    }
    if not dev_filtered:
        return
    async with coord.config_lock:
        dev_cleaned = clean_device_settings(
            dev_filtered,
            current=coord.device_data,
            is_round_display=coord.is_round_display,
            supports_hw_jpeg=coord.supports_hw_jpeg,
        )
        merged = {**coord.device_data, **dev_cleaned}
        wp_override = CONF_WALLPAPER_SOURCE in dev_cleaned
        if wp_override and CONF_WALLPAPER_MODE not in dev_cleaned:
            wp_val = str(merged.get(CONF_WALLPAPER_SOURCE) or "").strip()
            merged[CONF_WALLPAPER_MODE] = "single" if wp_val else "off"
        if (
            CONF_WALLPAPER_COLLECTION in dev_cleaned
            and CONF_WALLPAPER_MODE not in dev_cleaned
        ):
            col_val = str(merged.get(CONF_WALLPAPER_COLLECTION) or "").strip()
            merged[CONF_WALLPAPER_MODE] = "collection" if col_val else "off"
        if (
            CONF_SCREENSAVER_PHOTO_COLLECTION in dev_cleaned
            and CONF_SCREENSAVER_PHOTO_MODE not in dev_cleaned
        ):
            ss_col = str(merged.get(CONF_SCREENSAVER_PHOTO_COLLECTION) or "").strip()
            merged[CONF_SCREENSAVER_PHOTO_MODE] = "collection" if ss_col else "off"
        if merged != coord.device_data or wp_override:
            if wp_override:
                wp_val = str(merged.get(CONF_WALLPAPER_SOURCE) or "").strip()
                coord.current_wallpaper = wp_val
                coord.set_configured_wallpaper_source(wp_val)
            coord.update_device_config(merged, defer_apply=True)
            await coord.async_apply_options()
            coord.bind_wallpaper_cycle_timer()
            coord.bind_screensaver_cycle_timer()
            coord.async_notify_listeners()


async def _cmd_apply_batch_device_setting(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    raw_target = str(body.get("target") or "all").strip() or "all"
    all_coords_full = list(iter_coordinators(hass))
    all_coords = [c for c in all_coords_full if not c.is_ble_tag]
    filtered = _extract_batch_updates_payload(body, all_coords_full, global_cfg)
    targets = _select_batch_target_coordinators(hass, all_coords, raw_target)
    if targets:
        await asyncio.gather(
            *(_async_apply_batch_to_coordinator(c, filtered) for c in targets)
        )
    await evaluate_bedtime_if_ready(hass)


async def _cmd_rotate_signing_key(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    _body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    sys_obj = get_latter_system(hass)
    if sys_obj is None:
        raise StudioCommandError("not_ready", "Latter System is not initialized")
    if hasattr(sys_obj, "async_rotate_hmac_secret"):
        await sys_obj.async_rotate_hmac_secret()
    else:
        await async_rotate_hub_hmac_secret(sys_obj)
    log_studio_event(hass, "INFO", "system", "Rotated HTTP resource signing key")


async def _cmd_set_security_pin(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    target_sub_id = str(body.get("subentry_id") or "").strip()
    if target_sub_id:
        target_coord = find_by_subentry_id(iter_coordinators(hass), target_sub_id)
        if target_coord is None:
            raise StudioCommandError(
                "not_found", f"No Latter Device with subentry_id '{target_sub_id}'"
            )
        if body.get("clear"):
            pin_hash = ""
            log_msg = f"Cleared security PIN for '{target_coord.device_slug}'"
        else:
            raw_pin = str(body.get("pin") or "").strip()
            try:
                pin_hash = await hass.async_add_executor_job(
                    hash_security_pin, raw_pin
                )
            except ValueError as err:
                raise StudioCommandError("invalid_format", str(err)) from err
            log_msg = f"Updated security PIN for '{target_coord.device_slug}'"
        async with target_coord.config_lock:
            merged_pin_cfg: dict[str, Any] = {
                **target_coord.device_data,
                CONF_SECURITY_PIN_HASH: pin_hash,
            }
            merged_pin_cfg.pop(CONF_SECURITY_PIN, None)
            target_coord.update_device_config(merged_pin_cfg, defer_apply=True)
            await target_coord.async_apply_options()
            target_coord.async_notify_listeners()
        log_studio_event(hass, "INFO", target_coord.device_slug, log_msg)
    elif body.get("clear"):
        async with get_system_config_lock(hass):
            await async_save_and_broadcast_global_config(
                hass, {CONF_SECURITY_PIN_HASH: ""}
            )
        log_studio_event(hass, "INFO", "system", "Cleared System security PIN")
    else:
        raw_pin = str(body.get("pin") or "").strip()
        try:
            pin_hash = await hass.async_add_executor_job(hash_security_pin, raw_pin)
        except ValueError as err:
            raise StudioCommandError("invalid_format", str(err)) from err
        async with get_system_config_lock(hass):
            await async_save_and_broadcast_global_config(
                hass, {CONF_SECURITY_PIN_HASH: pin_hash}
            )
        log_studio_event(hass, "INFO", "system", "Updated System security PIN")


# ---------------------------------------------------------------------------
# Photo Library, Media Import, Announcements & Camera Preview Handlers
# ---------------------------------------------------------------------------


def _payload_device(
    hass: HomeAssistant, body: dict[str, Any], purpose: str
) -> LatterCoordinator:
    """Return the Device a System command names in its payload (`subentry_id`), else fail."""
    coords: list[LatterCoordinator] = list(iter_coordinators(hass))
    coord = find_by_subentry_id(coords, str(body.get("subentry_id") or ""))
    if coord is None:
        raise StudioCommandError("not_found", f"Choose {purpose}")
    return coord


async def _cmd_test_doorbell_speaker(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    speaker_coord = _payload_device(hass, body, "the Device to test from")
    cameras = system_settings_view(global_cfg)["camera_entities"]
    cam_ent = str(body.get("camera_entity") or "").strip()
    if not cameras:
        raise StudioCommandError(
            "invalid_format", "Add a camera in Shared Entities first"
        )
    if cam_ent not in cameras:
        raise StudioCommandError(
            "not_allowed", f"'{cam_ent}' isn't one of the System cameras"
        )
    msg = str(body.get("message") or "").strip()
    if not msg:
        raise StudioCommandError("invalid_format", "message is required")
    await async_execute_doorbell_intercom(
        hass,
        speaker_coord,
        action="talk_message",
        camera_entity=cam_ent,
        message=msg,
    )


async def _cmd_send_announcement(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    announcement = clean_announcement(
        body, {c.device_slug for c in iter_coordinators(hass) if not c.is_ble_tag}
    )
    data = dict(announcement["data"])
    if announcement["include_camera"]:
        cameras = system_settings_view(global_cfg)["camera_entities"]
        if not cameras:
            raise StudioCommandError(
                "invalid_format",
                "Add a camera in Shared Entities first, or turn off the camera snapshot",
            )
        data["camera_entity"] = cameras[0]
    await hass.services.async_call(
        DOMAIN, announcement["service"], data, blocking=True
    )


def _prune_wallpaper_deleted_ids(
    coord: LatterCoordinator, merged: dict[str, Any], deleted_ids: set[str]
) -> bool:
    """Prune `deleted_ids` from a coordinator's wallpaper pool, returning True when mutated."""
    changed = False
    wp_favs = [f for f in coord.wallpaper_favorites if f not in deleted_ids]
    if wp_favs != coord.wallpaper_favorites:
        merged[CONF_WALLPAPER_FAVORITES] = wp_favs
        changed = True
    if coord.wallpaper_mode == "single" and coord.configured_wallpaper_source in deleted_ids:
        merged[CONF_WALLPAPER_MODE] = "off"
        merged[CONF_WALLPAPER_SOURCE] = ""
        coord.current_wallpaper = ""
        coord.set_configured_wallpaper_source("")
        return True
    if coord.wallpaper_mode == "custom" and not wp_favs:
        merged[CONF_WALLPAPER_MODE] = "off"
        merged[CONF_WALLPAPER_SOURCE] = ""
        merged[CONF_WALLPAPER_CYCLE_MINUTES] = 0
        coord.current_wallpaper = ""
        return True
    if coord.current_wallpaper in deleted_ids or coord.wallpaper_source in deleted_ids:
        coord.current_wallpaper = ""
        return True
    return changed


def _prune_screensaver_deleted_ids(
    coord: LatterCoordinator, merged: dict[str, Any], deleted_ids: set[str]
) -> bool:
    """Prune `deleted_ids` from a coordinator's screensaver pool, returning True when mutated."""
    changed = False
    ss_ids = [f for f in coord.screensaver_photo_ids if f not in deleted_ids]
    if ss_ids != coord.screensaver_photo_ids:
        merged[CONF_SCREENSAVER_PHOTO_IDS] = ss_ids
        changed = True
    if (
        coord.screensaver_photo_mode == "single"
        and coord.configured_screensaver_photo_source in deleted_ids
    ) or (coord.screensaver_photo_mode == "custom" and not ss_ids):
        merged[CONF_SCREENSAVER_PHOTO_MODE] = "off"
        merged[CONF_SCREENSAVER_PHOTO_SOURCE] = ""
        coord.current_screensaver_photo = ""
        return True
    if (
        coord.current_screensaver_photo in deleted_ids
        or coord.screensaver_photo_source in deleted_ids
    ):
        coord.current_screensaver_photo = ""
        return True
    return changed


async def _prune_coordinator_deleted_photos(
    coord: LatterCoordinator, deleted_ids: set[str]
) -> None:
    """Prune `deleted_ids` from a single coordinator's wallpaper and screensaver pools under lock."""
    async with coord.config_lock:
        merged = dict(coord.device_data)
        wp_changed = _prune_wallpaper_deleted_ids(coord, merged, deleted_ids)
        ss_changed = _prune_screensaver_deleted_ids(coord, merged, deleted_ids)
        if wp_changed or ss_changed:
            if merged != coord.device_data:
                coord.update_device_config(merged)
            coord.bind_wallpaper_cycle_timer()
            coord.bind_screensaver_cycle_timer()
            coord.async_notify_listeners()


async def _prune_deleted_photos_from_coordinators(
    hass: HomeAssistant, deleted_ids: set[str]
) -> None:
    """Remove deleted photo IDs from all Devices' wallpaper & screensaver pools under each lock."""
    if not deleted_ids:
        return
    targets = [c for c in iter_coordinators(hass) if not c.is_ble_tag]
    if targets:
        await asyncio.gather(
            *(_prune_coordinator_deleted_photos(c, deleted_ids) for c in targets)
        )


async def _prune_coordinator_deleted_collection(
    coord: LatterCoordinator, collection_id: str
) -> None:
    """Clear references to a deleted collection on a single coordinator under `config_lock`."""
    async with coord.config_lock:
        merged = dict(coord.device_data)
        changed = False
        if (
            coord.wallpaper_mode == "collection"
            and coord.wallpaper_collection == collection_id
        ):
            merged[CONF_WALLPAPER_MODE] = "off"
            merged[CONF_WALLPAPER_COLLECTION] = ""
            merged[CONF_WALLPAPER_SOURCE] = ""
            coord.current_wallpaper = ""
            coord.set_configured_wallpaper_source("")
            changed = True
        if (
            coord.screensaver_photo_mode == "collection"
            and coord.screensaver_photo_collection == collection_id
        ):
            merged[CONF_SCREENSAVER_PHOTO_MODE] = "off"
            merged[CONF_SCREENSAVER_PHOTO_COLLECTION] = ""
            coord.current_screensaver_photo = ""
            changed = True
        if changed:
            coord.update_device_config(merged)
            coord.bind_wallpaper_cycle_timer()
            coord.bind_screensaver_cycle_timer()
            coord.async_notify_listeners()


async def _prune_deleted_collection_from_coordinators(
    hass: HomeAssistant, collection_id: str
) -> None:
    """Clear references to a deleted collection from all Devices' wallpaper & screensaver pools."""
    targets = [c for c in iter_coordinators(hass) if not c.is_ble_tag]
    if targets:
        await asyncio.gather(
            *(_prune_coordinator_deleted_collection(c, collection_id) for c in targets)
        )


def _rebind_collection_pool_coordinators(hass: HomeAssistant) -> None:
    """Refresh cycle timers on coordinators currently using a collection pool."""
    for c in iter_coordinators(hass):
        if not c.is_ble_tag and (
            c.wallpaper_mode == "collection"
            or c.screensaver_photo_mode == "collection"
        ):
            c.bind_wallpaper_cycle_timer()
            c.bind_screensaver_cycle_timer()
            c.async_notify_listeners()


async def _cmd_create_photo_collection(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    raw_name = str(body.get("name") or "").strip()
    if not raw_name:
        raise StudioCommandError("invalid_format", "Collection name is required")
    try:
        col = await hass.async_add_executor_job(create_collection, hass, raw_name)
    except ValueError as err:
        raise StudioCommandError("invalid_format", str(err)) from err
    extra["collection"] = col
    notify_studio_subscribers(hass)


async def _cmd_rename_photo_collection(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    col_id = str(body.get("collection_id") or "").strip()
    raw_name = str(body.get("name") or "").strip()
    if not col_id or not raw_name:
        raise StudioCommandError(
            "invalid_format", "collection_id and name are required"
        )
    try:
        col = await hass.async_add_executor_job(
            rename_collection, hass, col_id, raw_name
        )
    except ValueError as err:
        code = "not_found" if "Unknown collection" in str(err) else "invalid_format"
        raise StudioCommandError(code, str(err)) from err
    extra["collection"] = col
    notify_studio_subscribers(hass)


async def _cmd_delete_photo_collection(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    col_id = str(body.get("collection_id") or "").strip()
    if not col_id:
        raise StudioCommandError("invalid_format", "collection_id is required")
    deleted = await hass.async_add_executor_job(delete_collection, hass, col_id)
    if not deleted:
        raise StudioCommandError("not_found", f"Unknown collection '{col_id}'")
    await _prune_deleted_collection_from_coordinators(hass, col_id)
    extra["deleted_collection_id"] = col_id
    notify_studio_subscribers(hass)


async def _cmd_update_photo_metadata(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    photo_id = str(body.get("photo_id") or "").strip()
    if not photo_id:
        raise StudioCommandError("invalid_format", "photo_id is required")
    name = body.get("name") if "name" in body else None
    crop = body.get("crop") if "crop" in body else None
    collections = body.get("collections") if "collections" in body else None
    if name is None and crop is None and collections is None:
        raise StudioCommandError(
            "invalid_format", "Provide name, crop, or collections to update"
        )
    try:
        res = await hass.async_add_executor_job(
            lambda: update_photo_metadata(
                hass,
                photo_id,
                name=name,
                crop=crop,
                collections=collections,
            )
        )
    except ValueError as err:
        code = "not_found" if "Unknown photo" in str(err) else "invalid_format"
        raise StudioCommandError(code, str(err)) from err
    crop_changed = bool(res.pop("crop_changed", False))
    extra["photo"] = res
    if crop_changed or collections is not None:
        for c in iter_coordinators(hass):
            if c.is_ble_tag:
                continue
            if photo_id in {
                c.wallpaper_source,
                c.screensaver_photo_source,
            } or (
                collections is not None
                and "collection" in {c.wallpaper_mode, c.screensaver_photo_mode}
            ):
                c.bind_wallpaper_cycle_timer()
                c.bind_screensaver_cycle_timer()
                c.async_notify_listeners()
    notify_studio_subscribers(hass)


async def _cmd_bulk_update_photos(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    photo_ids = body.get("photo_ids")
    if not isinstance(photo_ids, list) or not photo_ids:
        raise StudioCommandError("invalid_format", "photo_ids must be a non-empty list")
    add_col = body.get("add_collection")
    rem_col = body.get("remove_collection")
    do_delete = bool(body.get("delete", False))
    if not do_delete and not add_col and not rem_col:
        raise StudioCommandError(
            "invalid_format",
            "Specify add_collection, remove_collection, or delete",
        )
    try:
        res = await hass.async_add_executor_job(
            lambda: bulk_update_photos(
                hass,
                photo_ids,
                add_collection=add_col,
                remove_collection=rem_col,
                delete=do_delete,
            )
        )
    except ValueError as err:
        raise StudioCommandError("invalid_format", str(err)) from err
    if res["deleted_ids"]:
        await _prune_deleted_photos_from_coordinators(hass, set(res["deleted_ids"]))
    elif res["updated"] > 0:
        _rebind_collection_pool_coordinators(hass)
    extra["bulk_result"] = res
    notify_studio_subscribers(hass)


async def _cmd_delete_photo(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    photo_id = str(body.get("photo_id") or "").strip()
    if not photo_id:
        raise StudioCommandError("invalid_format", "photo_id is required")
    deleted = await hass.async_add_executor_job(delete_photo, hass, photo_id)
    if not deleted:
        raise StudioCommandError(
            "not_found", "That photo isn't a deletable custom photo"
        )
    await _prune_deleted_photos_from_coordinators(hass, {photo_id})
    extra["deleted_photo_id"] = photo_id
    notify_studio_subscribers(hass)


async def _cmd_browse_media_folder(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    root = str(body.get("root") or "").strip()
    subpath = str(body.get("subpath") or "").strip()
    media_dirs = getattr(hass.config, "media_dirs", None)
    try:
        listing = await hass.async_add_executor_job(
            list_media_folder_sync, media_dirs, root, subpath
        )
    except ValueError as err:
        raise StudioCommandError("invalid_format", str(err)) from err
    sys_obj = get_latter_system(hass)
    used_root = str(listing.get("root") or "")
    for img in listing.get("images") or []:
        rel = str(img.get("relpath") or "")
        img["thumb_url"] = (
            sys_obj.url_signer.build_media_preview_url(
                used_root, rel, _MEDIA_THUMB_DIM, _MEDIA_THUMB_DIM
            )
            if (sys_obj is not None and used_root and rel and not img.get("too_large"))
            else ""
        )
    extra.update(listing)


async def _cmd_import_media_photos(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    root = str(body.get("root") or "").strip()
    paths = body.get("paths")
    if not root:
        raise StudioCommandError("invalid_format", "root is required")
    if not isinstance(paths, list) or not paths:
        raise StudioCommandError(
            "invalid_format", "Select at least one photo to import"
        )
    collection_id = str(body.get("collection_id") or "").strip()
    new_col_name = str(body.get("new_collection_name") or "").strip()
    deduplicate = bool(body.get("deduplicate", True))
    if not collection_id and new_col_name:
        try:
            created = await hass.async_add_executor_job(
                create_collection, hass, new_col_name
            )
            collection_id = str(created["id"])
        except ValueError as err:
            raise StudioCommandError("invalid_format", str(err)) from err

    media_dirs = getattr(hass.config, "media_dirs", None)
    try:
        result = await hass.async_add_executor_job(
            lambda: import_media_photos_sync(
                hass,
                media_dirs,
                root,
                paths,
                collection_id=collection_id or None,
                deduplicate=deduplicate,
            )
        )
    except ValueError as err:
        raise StudioCommandError("invalid_format", str(err)) from err
    extra["import_result"] = {
        "imported": result["imported"],
        "skipped": result["skipped"],
        "failed": result["failed"],
        "collection_id": collection_id,
    }
    if result["imported"] > 0:
        _rebind_collection_pool_coordinators(hass)
    notify_studio_subscribers(hass)


async def _cmd_mint_camera_preview_url(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    cam_ent = str(body.get("camera_entity") or "").strip()
    if not cam_ent or not cam_ent.startswith("camera."):
        raise StudioCommandError(
            "invalid_format", "camera_entity must be a valid camera.* entity ID"
        )
    if hass.states.get(cam_ent) is None:
        raise StudioCommandError("not_found", f"Camera '{cam_ent}' was not found")
    sys_obj = get_latter_system(hass)
    if sys_obj is None:
        raise StudioCommandError("not_ready", "Latter System is not initialized")
    sig = sys_obj.url_signer.sign_on_demand_resource(
        f"camera:{cam_ent}|320|180|square",
        ttl_s=_CAMERA_PREVIEW_TTL_S,
    )
    extra["camera_entity"] = cam_ent
    extra["preview_url"] = (
        f"/api/latter/camera/system"
        f"?entity_id={quote(cam_ent, safe='')}&w=320&h=180&shape=square&sig={sig}"
    )
    extra["expires_in"] = _CAMERA_PREVIEW_TTL_S


# ---------------------------------------------------------------------------
# Area Presence, Illuminance Calibration, BLE Signatures & Onboarding Handlers
# ---------------------------------------------------------------------------


async def _cmd_set_ble_scanner_offset(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    scanner_source = str(body.get("scanner_source") or "").strip().upper()
    if not scanner_source:
        raise StudioCommandError("invalid_format", "scanner_source is required")
    raw_offset = body.get("offset_db", 0.0)
    if isinstance(raw_offset, bool):
        raise StudioCommandError("invalid_format", "offset_db must be a number")
    try:
        offset_val = float(raw_offset if raw_offset is not None else 0.0)
    except (TypeError, ValueError) as err:
        raise StudioCommandError("invalid_format", f"Invalid offset_db: {err}") from None
    if not math.isfinite(offset_val):
        raise StudioCommandError("invalid_format", "offset_db must be a finite number")

    async with get_system_config_lock(hass):
        live_cfg = get_global_config(hass)
        raw_offsets = live_cfg.get(CONF_BLE_SCANNER_OFFSETS)
        offsets: dict[str, float] = {}
        if isinstance(raw_offsets, dict):
            for k, v in raw_offsets.items():
                norm_k = str(k or "").strip().upper()
                if not norm_k:
                    continue
                try:
                    clamped = max(-_SCANNER_OFFSET_ABS_MAX, min(_SCANNER_OFFSET_ABS_MAX, float(v)))
                    offsets[norm_k] = round(clamped, 1)
                except (TypeError, ValueError) as err:
                    _LOGGER.debug("Ignoring malformed scanner offset %s: %s", norm_k, err)
        if abs(offset_val) < _SCANNER_OFFSET_ZERO_EPS:
            offsets.pop(scanner_source, None)
        else:
            clamped_new = max(-_SCANNER_OFFSET_ABS_MAX, min(_SCANNER_OFFSET_ABS_MAX, offset_val))
            offsets[scanner_source] = round(clamped_new, 1)
        await async_save_and_broadcast_global_config(hass, {CONF_BLE_SCANNER_OFFSETS: offsets})


async def _cmd_set_area_fusion(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    area_id = str(body.get("area_id") or "").strip()
    if not area_id or ar.async_get(hass).async_get_area(area_id) is None:
        raise StudioCommandError("not_found", f"Unknown Area '{area_id}'")
    allowed_sensors = {s["entity_id"] for s in area_fusion_sensor_choices(hass, area_id)}
    async with get_system_config_lock(hass):
        live_cfg = get_global_config(hass)
        raw_fusion = live_cfg.get(CONF_AREA_FUSION_CONFIG) or {}
        fusion_cfg = dict(raw_fusion) if isinstance(raw_fusion, dict) else {}
        current_area = fusion_cfg.get(area_id)
        fusion_cfg[area_id] = clean_area_fusion(
            current_area if isinstance(current_area, dict) else {},
            {k: body[k] for k in ("mode", "threshold_pct", "sensors") if k in body},
            allowed_sensors,
        )
        await async_save_and_broadcast_global_config(hass, {CONF_AREA_FUSION_CONFIG: fusion_cfg})
    fabric = get_ble_fabric(hass)
    fabric.rebind_fusion_sensor_listener()
    fabric.notify_occupancy_listeners()


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Linearly interpolated percentile (`q` in `0..1`) over a non-empty sorted list."""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = max(0.0, min(1.0, q)) * (len(sorted_vals) - 1)
    lo = math.floor(pos)
    hi = min(len(sorted_vals) - 1, lo + 1)
    return sorted_vals[lo] + (pos - lo) * (sorted_vals[hi] - sorted_vals[lo])


def _append_non_negative_float(dest: list[float], raw: Any) -> None:
    if raw is None or isinstance(raw, bool):
        return
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return
    if math.isfinite(val) and val >= 0.0:
        dest.append(val)


def compute_illuminance_calibration_from_stats(
    rows: list[Mapping[str, Any]],
) -> tuple[float, float] | None:
    """Derive `(dark_lux, bright_lux)` from hourly HA recorder statistics rows."""
    mins: list[float] = []
    means: list[float] = []
    for row in rows:
        _append_non_negative_float(mins, row.get("min"))
        _append_non_negative_float(means, row.get("mean"))
    if not means:
        return None
    mins_sorted = sorted(mins or means)
    means_sorted = sorted(means)
    dark_raw = max(0.0, min(_DARK_LUX_MAX, _percentile(mins_sorted, 0.10)))
    dark_lux = round(dark_raw, 1) if dark_raw < _LUX_DECIMAL_CUTOFF else float(round(dark_raw))

    pos_means = [v for v in means_sorted if v > dark_lux + 0.1]
    if len(pos_means) >= _MIN_POS_MEAN_SAMPLES:
        bright_raw = _percentile(pos_means, 0.90)
    elif pos_means:
        bright_raw = max(pos_means)
    else:
        bright_raw = _percentile(means_sorted, 0.90)
    bright_raw = max(dark_lux + _BRIGHT_LUX_MIN_DELTA, min(_BRIGHT_LUX_MAX, bright_raw))
    bright_lux = (
        round(bright_raw, 1) if bright_raw < _LUX_DECIMAL_CUTOFF else float(round(bright_raw))
    )
    return (dark_lux, bright_lux)


def _refresh_coordinators_ambient_light(hass: HomeAssistant) -> None:
    """Clear ambient-light deadband caches and notify all Device coordinators immediately."""
    for coord in iter_coordinators(hass):
        coord.last_ambient_light = ("", None, "")
        coord.cached_area_payload = None
        coord.async_notify_listeners()


async def _cmd_set_area_illuminance(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    area_id = str(body.get("area_id") or "").strip()
    if not area_id or ar.async_get(hass).async_get_area(area_id) is None:
        raise StudioCommandError("not_found", f"Unknown Area '{area_id}'")
    allowed_sensors = {str(s["entity_id"]) for s in area_illuminance_sensor_choices(hass, area_id)}
    async with get_system_config_lock(hass):
        live_cfg = get_global_config(hass)
        raw_lux = live_cfg.get(CONF_AREA_ILLUMINANCE_CONFIG) or {}
        lux_cfg = dict(raw_lux) if isinstance(raw_lux, dict) else {}
        current_area = lux_cfg.get(area_id)
        lux_cfg[area_id] = clean_area_illuminance(
            current_area if isinstance(current_area, dict) else {},
            {k: body[k] for k in ("entity_id", "dark_lux", "bright_lux") if k in body},
            allowed_sensors,
        )
        await async_save_and_broadcast_global_config(hass, {CONF_AREA_ILLUMINANCE_CONFIG: lux_cfg})
    _refresh_coordinators_ambient_light(hass)


def _collect_illuminance_targets(
    hass: HomeAssistant, target_area_id: str
) -> tuple[list[tuple[str, str, str]], list[str]]:
    area_reg = ar.async_get(hass)
    if target_area_id:
        area_entry = area_reg.async_get_area(target_area_id)
        if area_entry is None:
            raise StudioCommandError("not_found", f"Unknown Area '{target_area_id}'")
        target_areas = [area_entry]
    else:
        target_areas = list(area_reg.async_list_areas())

    area_targets: list[tuple[str, str, str]] = []
    skipped: list[str] = []
    for area_entry in target_areas:
        ambient = resolve_area_ambient_light(hass, area_entry.id)
        if ambient["configured_entity"] == "disabled":
            skipped.append(area_entry.name)
            continue
        eid = str(ambient["resolved_entity"] or "")
        if not eid:
            if target_area_id:
                raise StudioCommandError(
                    "invalid_format", f"No illuminance sensor found in {area_entry.name}"
                )
            continue
        area_targets.append((area_entry.id, area_entry.name, eid))

    if not area_targets:
        raise StudioCommandError("invalid_format", "No illuminance sensors found to calibrate")
    return area_targets, skipped


async def _async_fetch_illuminance_stats(
    hass: HomeAssistant, statistic_ids: list[str]
) -> Mapping[str, Sequence[Mapping[str, Any]]]:
    try:
        from homeassistant.components.recorder.statistics import statistics_during_period
        from homeassistant.helpers.recorder import get_instance

        end_dt = dt_util.utcnow()
        start_dt = end_dt - timedelta(days=_RECORDER_CALIBRATION_DAYS)
        rec = get_instance(hass)
        return await rec.async_add_executor_job(
            statistics_during_period,
            hass,
            start_dt,
            end_dt,
            set(statistic_ids),
            "hour",
            None,
            {"min", "mean"},
        )
    except Exception as err:
        _LOGGER.debug("Recorder statistics unavailable for illuminance calibration: %s", err)
        raise StudioCommandError(
            "failed",
            "Recorder hourly statistics are unavailable for ambient light calibration",
        ) from err


async def _cmd_calibrate_area_illuminance(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    if "recorder" not in hass.config.components:
        raise StudioCommandError(
            "not_supported",
            "Home Assistant recorder component is not enabled for ambient light calibration",
        )
    target_area_id = str(body.get("area_id") or "").strip()
    area_targets, skipped = _collect_illuminance_targets(hass, target_area_id)
    stats_by_eid = await _async_fetch_illuminance_stats(
        hass, sorted({eid for _, _, eid in area_targets})
    )

    calibrated: list[dict[str, Any]] = []
    async with get_system_config_lock(hass):
        live_cfg = get_global_config(hass)
        raw_lux = live_cfg.get(CONF_AREA_ILLUMINANCE_CONFIG) or {}
        lux_cfg = dict(raw_lux) if isinstance(raw_lux, dict) else {}
        for aid, aname, eid in area_targets:
            rows = list(stats_by_eid.get(eid) or [])
            cal = compute_illuminance_calibration_from_stats(rows)
            if cal is None:
                skipped.append(aname)
                continue
            dark_lux, bright_lux = cal
            cur = dict(lux_cfg.get(aid) or {}) if isinstance(lux_cfg.get(aid), dict) else {}
            cur["dark_lux"] = dark_lux
            cur["bright_lux"] = bright_lux
            lux_cfg[aid] = cur
            calibrated.append(
                {
                    "area_id": aid,
                    "area_name": aname,
                    "entity_id": eid,
                    "dark_lux": dark_lux,
                    "bright_lux": bright_lux,
                    "samples": len(rows),
                }
            )
        if not calibrated:
            raise StudioCommandError(
                "invalid_format",
                "Not enough recorded illuminance history yet (wait for hourly statistics)",
            )
        await async_save_and_broadcast_global_config(hass, {CONF_AREA_ILLUMINANCE_CONFIG: lux_cfg})

    _refresh_coordinators_ambient_light(hass)
    extra["calibrated"] = calibrated
    extra["skipped"] = skipped
    log_studio_event(
        hass, "INFO", "system", f"Auto-calibrated ambient light for {len(calibrated)} Area(s)"
    )


async def _cmd_capture_ble_area_signature(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    target_area_id = str(body.get("area_id") or "").strip()
    survey_id = str(body.get("survey_subentry_id") or "").strip()
    if not target_area_id:
        raise StudioCommandError("invalid_format", "area_id is required")
    if ar.async_get(hass).async_get_area(target_area_id) is None:
        raise StudioCommandError("not_found", f"Unknown Area '{target_area_id}'")
    if not survey_id:
        raise StudioCommandError(
            "invalid_format", "survey_subentry_id is required: select the BLE survey Device"
        )
    survey_coord = find_by_subentry_id(iter_coordinators(hass), survey_id)
    if survey_coord is None:
        raise StudioCommandError("not_found", f"No Latter Device with subentry_id '{survey_id}'")
    tracker = survey_coord.ble_tracker
    if tracker is None:
        raise StudioCommandError(
            "not_supported",
            f"{survey_coord.device_title} has no BLE tracker: enable Track the Area with BLE Proxies for it first",
        )

    scanners_sig = tracker.capture_area_signature()
    if not scanners_sig:
        raise StudioCommandError(
            "not_ready",
            "No fresh Bluetooth proxy readings yet for this Device — wait a few seconds and try again",
        )

    async with get_system_config_lock(hass):
        live_cfg = get_global_config(hass)
        raw_sigs = live_cfg.get(CONF_BLE_AREA_SIGNATURES)
        signatures = dict(raw_sigs) if isinstance(raw_sigs, dict) else {}
        signatures[target_area_id] = {
            "scanners": scanners_sig,
            "captured_at": dt_util.utcnow().isoformat(timespec="seconds"),
            "sample_count": sum(int(v.get("n", 1)) for v in scanners_sig.values()),
        }
        await async_save_and_broadcast_global_config(hass, {CONF_BLE_AREA_SIGNATURES: signatures})
    survey_coord.async_set_active_area(
        target_area_id, handoff_media=False, sync_device_registry=True
    )


async def _cmd_clear_ble_area_signature(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    target_area_id = str(body.get("area_id") or "").strip()
    if not target_area_id:
        raise StudioCommandError("invalid_format", "area_id is required")
    async with get_system_config_lock(hass):
        live_cfg = get_global_config(hass)
        raw_sigs = live_cfg.get(CONF_BLE_AREA_SIGNATURES)
        signatures = dict(raw_sigs) if isinstance(raw_sigs, dict) else {}
        signatures.pop(target_area_id, None)
        await async_save_and_broadcast_global_config(hass, {CONF_BLE_AREA_SIGNATURES: signatures})


async def _cmd_check_system_updates(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    _body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    coords = [c for c in iter_coordinators(hass) if not c.is_ble_tag]
    update_ids = {
        c.subentry_id: [
            e.entity_id for e in device_entities(hass, c.esphome_device_id, domain="update")
        ]
        for c in coords
    }
    all_ids = [eid for ids in update_ids.values() for eid in ids]
    if all_ids:
        try:
            async with asyncio.timeout(_UPDATE_ENTITY_TIMEOUT_S):
                await hass.services.async_call(
                    "homeassistant", "update_entity", {"entity_id": all_ids}, blocking=True
                )
        except TimeoutError:
            raise StudioCommandError(
                "timeout", "The firmware check took longer than 30 seconds; try again"
            ) from None
    extra["update_check"] = {
        "checked": sum(1 for ids in update_ids.values() if ids),
        "available": sum(
            1
            for ids in update_ids.values()
            if any((st := hass.states.get(eid)) is not None and st.state == "on" for eid in ids)
        ),
    }


async def _cmd_clear_internal_logs(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    _body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    get_domain_data(hass).internal_logs.clear()
    log_studio_event(hass, "INFO", "studio", "Cleared internal diagnostic log")


async def _cmd_ignore_discovered_device(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    esp_dev_id = str(body.get("esphome_device_id") or "").strip()
    if not esp_dev_id:
        raise StudioCommandError("invalid_format", "esphome_device_id is required")
    dev = get_bound_esphome_device(hass, esp_dev_id)
    if dev is None:
        raise StudioCommandError("not_found", f"Unknown ESPHome device '{esp_dev_id}'")
    async with get_system_config_lock(hass):
        live_cfg = get_global_config(hass)
        raw_ignored = live_cfg.get(CONF_IGNORED_DISCOVERED_DEVICES) or []
        ignored = [
            str(x).strip()
            for x in (raw_ignored if isinstance(raw_ignored, list) else [])
            if str(x or "").strip()
        ]
        if esp_dev_id not in ignored:
            ignored = [*ignored, esp_dev_id][:MAX_IGNORED_DISCOVERED]
            await async_save_and_broadcast_global_config(
                hass, {CONF_IGNORED_DISCOVERED_DEVICES: ignored}
            )
    log_studio_event(hass, "INFO", "studio", f"Ignored discovered device '{device_title(dev)}'")


async def _cmd_unignore_discovered_device(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    esp_dev_id = str(body.get("esphome_device_id") or "").strip()
    if not esp_dev_id:
        raise StudioCommandError("invalid_format", "esphome_device_id is required")
    async with get_system_config_lock(hass):
        live_cfg = get_global_config(hass)
        raw_ignored = live_cfg.get(CONF_IGNORED_DISCOVERED_DEVICES) or []
        ignored = [
            str(x).strip()
            for x in (raw_ignored if isinstance(raw_ignored, list) else [])
            if str(x or "").strip() and str(x).strip() != esp_dev_id
        ]
        if ignored != raw_ignored:
            await async_save_and_broadcast_global_config(
                hass, {CONF_IGNORED_DISCOVERED_DEVICES: ignored}
            )


async def _cmd_remove_device(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    target_coord = find_by_subentry_id(
        iter_coordinators(hass), str(body.get("subentry_id") or "")
    )
    if target_coord is None:
        raise StudioCommandError(
            "not_found", "subentry_id of the Device to remove is missing or unknown"
        )
    removed_slug = target_coord.device_slug
    hass.config_entries.async_remove_subentry(target_coord.entry, target_coord.subentry_id)
    log_studio_event(hass, "INFO", "studio", f"Removed device '{removed_slug}' from Latter")
    extra["removed"] = True
    extra["removed_subentry_id"] = target_coord.subentry_id


def _validate_add_latter_device_request(
    hass: HomeAssistant, system_entry: Any, body: dict[str, Any]
) -> tuple[dr.DeviceEntry, dict[str, Any]]:
    esp_dev_id = str(body.get("esphome_device_id") or "").strip()
    if not esp_dev_id:
        raise StudioCommandError("invalid_format", "Choose a discovered Latter ESPHome Device")
    dev = get_bound_esphome_device(hass, esp_dev_id)
    if (
        dev is None
        or not is_esphome_device(hass, dev)
        or not is_latter_compatible_esphome_device(hass, dev)
    ):
        raise StudioCommandError(
            "not_latter_device", "Selected ESPHome device is not running Latter firmware"
        )
    if bound_elsewhere(system_entry, dev, device_unique_id(dev)):
        raise StudioCommandError(
            "already_configured", f"'{device_title(dev)}' is already managed in Latter"
        )
    raw_group = str(body.get("device_group") or "auto").strip() or "auto"
    if raw_group not in ("auto", DEFAULT_DEVICE_GROUP) and not any(
        g.get("id") == raw_group for g in get_device_groups(hass)
    ):
        raise StudioCommandError("not_found", f"Unknown Device Group '{raw_group}'")
    assigned_person = str(body.get("assigned_person") or "").strip()
    if assigned_person and (
        not assigned_person.startswith("person.")
        or (
            hass.states.get(assigned_person) is None
            and er.async_get(hass).async_get(assigned_person) is None
        )
    ):
        raise StudioCommandError("not_found", f"Unknown person entity '{assigned_person}'")
    init_data: dict[str, Any] = {CONF_ESPHOME_DEVICE_ID: dev.id, CONF_DEVICE_GROUP: raw_group}
    if assigned_person:
        init_data[CONF_ASSIGNED_PERSON] = assigned_person
    return dev, init_data


async def _cmd_add_latter_device(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    system_entries = hass.config_entries.async_entries(DOMAIN)
    if not system_entries:
        raise StudioCommandError("not_found", "Latter System entry is not set up")
    dev, init_data = _validate_add_latter_device_request(hass, system_entries[0], body)
    flow_res = await hass.config_entries.subentries.async_init(
        (system_entries[0].entry_id, SUBENTRY_DEVICE),
        context={"source": "user"},
        data=init_data,
    )
    if isinstance(flow_res, Mapping) and flow_res.get("type") != "create_entry":
        reason = str(
            flow_res.get("reason")
            or next(iter((flow_res.get("errors") or {}).values()), "")
            or "invalid_format"
        )
        raise StudioCommandError(reason, f"Could not add '{device_title(dev)}' ({reason})")
    async with get_system_config_lock(hass):
        live_cfg = get_global_config(hass)
        raw_ignored = live_cfg.get(CONF_IGNORED_DISCOVERED_DEVICES) or []
        if isinstance(raw_ignored, list) and dev.id in raw_ignored:
            cleaned_ignored = [
                str(x).strip()
                for x in raw_ignored
                if str(x or "").strip() and str(x).strip() != dev.id
            ]
            await async_save_and_broadcast_global_config(
                hass, {CONF_IGNORED_DISCOVERED_DEVICES: cleaned_ignored}
            )
    adopted_coord = next(
        (c for c in iter_coordinators(hass) if c.esphome_device_id == dev.id), None
    )
    extra["adopted_esphome_device_id"] = dev.id
    matched_sub = (
        adopted_coord.subentry_id
        if adopted_coord is not None
        else next(
            (
                sub.subentry_id
                for sub in system_entries[0].subentries.values()
                if sub.data.get(CONF_ESPHOME_DEVICE_ID) == dev.id
            ),
            "",
        )
    )
    if matched_sub:
        extra["adopted_subentry_id"] = matched_sub
    log_studio_event(hass, "INFO", "studio", f"Adopted Latter device '{device_title(dev)}'")


def _normalize_ble_target_key(raw: str) -> str:
    s = str(raw or "").strip()
    if not s:
        return ""
    if re.fullmatch(r"(?:[0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{12}", s):
        return str(dr.format_mac(s)).upper()
    low = s.lower()
    return low[len(_IBEACON_PREFIX) :].strip() if low.startswith(_IBEACON_PREFIX) else low


def _ensure_ble_target_unique(
    hass: HomeAssistant, system_entry: Any, target_slug: str, target_addr: str
) -> None:
    norm_key = _normalize_ble_target_key(target_addr)
    for existing in iter_coordinators(hass):
        if existing.device_slug == target_slug:
            raise StudioCommandError(
                "already_configured", f"A Device named '{target_slug}' already exists"
            )
        existing_addr = str(getattr(existing, "ble_target_address", "") or "").strip()
        if norm_key and existing_addr and _normalize_ble_target_key(existing_addr) == norm_key:
            raise StudioCommandError(
                "already_configured",
                f"Target '{target_addr}' is already tracked by '{existing.device_slug}'",
            )
    for sub in system_entry.subentries.values():
        sub_addr = str(sub.data.get(CONF_BLE_TARGET_ADDRESS) or "").strip()
        if norm_key and sub_addr and _normalize_ble_target_key(sub_addr) == norm_key:
            raise StudioCommandError(
                "already_configured", f"Target '{target_addr}' is already configured in Latter"
            )


async def _cmd_add_ble_device(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    extra: dict[str, Any],
) -> None:
    system_entries = hass.config_entries.async_entries(DOMAIN)
    if not system_entries:
        raise StudioCommandError("not_found", "Latter System entry is not set up")
    raw_name = str(body.get("name") or "").strip()
    target_addr = str(body.get("target_address") or "").strip()
    assigned_person = str(body.get("assigned_person") or "").strip()
    raw_cat = str(body.get(CONF_BLE_CATEGORY) or DEFAULT_BLE_CATEGORY).strip().lower()
    if raw_cat not in ("auto", "phone", "ble_tag"):
        raise StudioCommandError("invalid_format", f"Unknown BLE category '{raw_cat}'")
    target_slug = normalize_device_slug(raw_name) if raw_name else ""
    if not target_slug or target_slug == "esphome_device" or not target_addr:
        raise StudioCommandError("invalid_format", "A BLE tag needs a name and a target address")
    _ensure_ble_target_unique(hass, system_entries[0], target_slug, target_addr)
    flow_res = await hass.config_entries.subentries.async_init(
        (system_entries[0].entry_id, SUBENTRY_BLE_TAG),
        context={"source": "user"},
        data={
            "name": raw_name,
            CONF_BLE_TARGET_ADDRESS: target_addr,
            CONF_BLE_CATEGORY: raw_cat,
            CONF_ASSIGNED_PERSON: assigned_person,
        },
    )
    if isinstance(flow_res, Mapping) and flow_res.get("type") != "create_entry":
        reason = str(
            flow_res.get("reason")
            or next(iter((flow_res.get("errors") or {}).values()), "")
            or "invalid_format"
        )
        raise StudioCommandError(reason, f"Could not add BLE tag '{raw_name}' ({reason})")
    adopted_ble = next(
        (c for c in iter_coordinators(hass) if c.device_slug == target_slug), None
    )
    if adopted_ble is not None:
        extra["adopted_subentry_id"] = adopted_ble.subentry_id


# ---------------------------------------------------------------------------
# System Command Schemas & Dispatch Table
# ---------------------------------------------------------------------------


def _str_cap(max_len: int) -> Any:
    return vol.All(str, vol.Length(max=max_len))


def _non_bool_int(val: Any) -> int:
    if isinstance(val, bool) or not isinstance(val, int):
        raise vol.Invalid("Expected an integer")
    return val


def _non_bool_number(val: Any) -> int | float:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise vol.Invalid("Expected a number")
    if not math.isfinite(float(val)):
        raise vol.Invalid("Expected a finite number")
    return val


def _schema(fields: dict[Any, Any]) -> vol.Schema:
    return vol.Schema(fields, extra=vol.PREVENT_EXTRA)


SYSTEM_COMMAND_SCHEMAS: dict[str, vol.Schema] = {
    "set_ble_scanner_offset": _schema({
        vol.Optional("scanner_source"): _str_cap(128),
        vol.Optional("offset_db"): vol.Any(_non_bool_number, None),
    }),
    "set_area_fusion": _schema({
        vol.Optional("area_id"): _str_cap(128),
        vol.Optional("mode"): _str_cap(32),
        vol.Optional("threshold_pct"): vol.Any(_non_bool_number, str),
        vol.Optional("sensors"): [_str_cap(128)],
    }),
    "set_area_illuminance": _schema({
        vol.Optional("area_id"): _str_cap(128),
        vol.Optional("entity_id"): _str_cap(128),
        vol.Optional("dark_lux"): vol.Any(_non_bool_number, str),
        vol.Optional("bright_lux"): vol.Any(_non_bool_number, str),
    }),
    "calibrate_area_illuminance": _schema({vol.Optional("area_id"): _str_cap(128)}),
    "capture_ble_area_signature": _schema({
        vol.Optional("area_id"): _str_cap(128),
        vol.Optional("survey_subentry_id"): _str_cap(128),
    }),
    "clear_ble_area_signature": _schema({vol.Optional("area_id"): _str_cap(128)}),
    "check_system_updates": _schema({}),
    "clear_internal_logs": _schema({}),
    "ignore_discovered_device": _schema({vol.Optional("esphome_device_id"): _str_cap(128)}),
    "unignore_discovered_device": _schema({vol.Optional("esphome_device_id"): _str_cap(128)}),
    "remove_device": _schema({vol.Optional("subentry_id"): _str_cap(128)}),
    "add_latter_device": _schema({
        vol.Optional("esphome_device_id"): _str_cap(128),
        vol.Optional("device_group"): _str_cap(64),
        vol.Optional("assigned_person"): _str_cap(128),
    }),
    "add_ble_device": _schema({
        vol.Optional("name"): _str_cap(64),
        vol.Optional("target_address"): _str_cap(128),
        vol.Optional("assigned_person"): _str_cap(128),
        vol.Optional(CONF_BLE_CATEGORY): _str_cap(32),
    }),
    "test_doorbell_speaker": _schema({
        vol.Optional("subentry_id"): _str_cap(128),
        vol.Optional("camera_entity"): _str_cap(128),
        vol.Optional("message"): _str_cap(250),
    }),
    "send_announcement": _schema({
        vol.Optional("mode"): _str_cap(32),
        vol.Optional("target_device"): _str_cap(128),
        vol.Optional("title"): _str_cap(64),
        vol.Optional("message"): _str_cap(500),
        vol.Optional("priority"): _str_cap(32),
        vol.Optional("include_camera"): bool,
    }),
    "create_photo_collection": _schema({vol.Optional("name"): _str_cap(64)}),
    "rename_photo_collection": _schema({
        vol.Optional("collection_id"): _str_cap(64),
        vol.Optional("name"): _str_cap(64),
    }),
    "delete_photo_collection": _schema({vol.Optional("collection_id"): _str_cap(64)}),
    "update_photo_metadata": _schema({
        vol.Optional("photo_id"): _str_cap(128),
        vol.Optional("name"): _str_cap(96),
        vol.Optional("crop"): dict,
        vol.Optional("collections"): [_str_cap(64)],
    }),
    "bulk_update_photos": _schema({
        vol.Optional("photo_ids"): [_str_cap(128)],
        vol.Optional("add_collection"): vol.Any(_str_cap(64), None),
        vol.Optional("remove_collection"): vol.Any(_str_cap(64), None),
        vol.Optional("delete"): bool,
    }),
    "delete_photo": _schema({vol.Optional("photo_id"): _str_cap(128)}),
    "browse_media_folder": _schema({
        vol.Optional("root"): _str_cap(64),
        vol.Optional("subpath"): _str_cap(512),
    }),
    "import_media_photos": _schema({
        vol.Optional("root"): _str_cap(64),
        vol.Optional("paths"): [_str_cap(512)],
        vol.Optional("collection_id"): vol.Any(_str_cap(64), None),
        vol.Optional("new_collection_name"): vol.Any(_str_cap(64), None),
        vol.Optional("deduplicate"): bool,
    }),
    "mint_camera_preview_url": _schema({vol.Optional("camera_entity"): _str_cap(128)}),
    "save_system_config": _schema({
        vol.Optional("config"): dict,
        vol.Optional("expected_config_rev"): vol.Any(_non_bool_int, None),
    }),
    "create_device_group": _schema({
        vol.Optional("name"): _str_cap(64),
        vol.Optional("description"): _str_cap(200),
        vol.Optional("source_subentry_id"): _str_cap(128),
        vol.Optional("assign_source"): bool,
        vol.Optional("include_display"): bool,
        vol.Optional("include_interface"): bool,
    }),
    "delete_device_group": _schema({vol.Optional("group_id"): _str_cap(64)}),
    "update_group_baseline": _schema({
        vol.Optional("group_id"): _str_cap(64),
        vol.Optional("include_display"): bool,
        vol.Optional("include_interface"): bool,
        vol.Optional("source_subentry_id"): _str_cap(128),
        vol.Optional("copy_keys"): [_str_cap(64)],
        vol.Optional("config"): dict,
        vol.Optional("reset_to_default"): bool,
    }),
    "apply_batch_device_setting": _schema({
        vol.Optional("target"): _str_cap(96),
        vol.Optional("config"): dict,
        vol.Optional("source_subentry_id"): _str_cap(128),
        vol.Optional("copy_keys"): [_str_cap(64)],
    }),
    "rotate_signing_key": _schema({}),
    "set_security_pin": _schema({
        vol.Optional("subentry_id"): _str_cap(128),
        vol.Optional("pin"): _str_cap(32),
        vol.Optional("clear"): bool,
    }),
}

SYSTEM_COMMAND_HANDLERS: dict[str, CommandHandler] = {
    "set_ble_scanner_offset": _cmd_set_ble_scanner_offset,
    "set_area_fusion": _cmd_set_area_fusion,
    "set_area_illuminance": _cmd_set_area_illuminance,
    "calibrate_area_illuminance": _cmd_calibrate_area_illuminance,
    "capture_ble_area_signature": _cmd_capture_ble_area_signature,
    "clear_ble_area_signature": _cmd_clear_ble_area_signature,
    "send_announcement": _cmd_send_announcement,
    "check_system_updates": _cmd_check_system_updates,
    "clear_internal_logs": _cmd_clear_internal_logs,
    "remove_device": _cmd_remove_device,
    "add_latter_device": _cmd_add_latter_device,
    "ignore_discovered_device": _cmd_ignore_discovered_device,
    "unignore_discovered_device": _cmd_unignore_discovered_device,
    "add_ble_device": _cmd_add_ble_device,
    "create_device_group": _cmd_create_device_group,
    "delete_device_group": _cmd_delete_device_group,
    "update_group_baseline": _cmd_update_group_baseline,
    "apply_batch_device_setting": _cmd_apply_batch_device_setting,
    "test_doorbell_speaker": _cmd_test_doorbell_speaker,
    "mint_camera_preview_url": _cmd_mint_camera_preview_url,
    "delete_photo": _cmd_delete_photo,
    "create_photo_collection": _cmd_create_photo_collection,
    "rename_photo_collection": _cmd_rename_photo_collection,
    "delete_photo_collection": _cmd_delete_photo_collection,
    "update_photo_metadata": _cmd_update_photo_metadata,
    "bulk_update_photos": _cmd_bulk_update_photos,
    "browse_media_folder": _cmd_browse_media_folder,
    "import_media_photos": _cmd_import_media_photos,
    "save_system_config": _cmd_save_system_config,
    "rotate_signing_key": _cmd_rotate_signing_key,
    "set_security_pin": _cmd_set_security_pin,
}

__all__ = [
    "SYSTEM_COMMAND_HANDLERS",
    "SYSTEM_COMMAND_SCHEMAS",
    "_cmd_add_ble_device",
    "_cmd_add_latter_device",
    "_cmd_apply_batch_device_setting",
    "_cmd_browse_media_folder",
    "_cmd_bulk_update_photos",
    "_cmd_calibrate_area_illuminance",
    "_cmd_capture_ble_area_signature",
    "_cmd_check_system_updates",
    "_cmd_clear_ble_area_signature",
    "_cmd_clear_internal_logs",
    "_cmd_create_device_group",
    "_cmd_create_photo_collection",
    "_cmd_delete_device_group",
    "_cmd_delete_photo",
    "_cmd_delete_photo_collection",
    "_cmd_ignore_discovered_device",
    "_cmd_import_media_photos",
    "_cmd_mint_camera_preview_url",
    "_cmd_remove_device",
    "_cmd_rename_photo_collection",
    "_cmd_rotate_signing_key",
    "_cmd_save_system_config",
    "_cmd_send_announcement",
    "_cmd_set_area_fusion",
    "_cmd_set_area_illuminance",
    "_cmd_set_ble_scanner_offset",
    "_cmd_set_security_pin",
    "_cmd_test_doorbell_speaker",
    "_cmd_unignore_discovered_device",
    "_cmd_update_group_baseline",
    "_cmd_update_photo_metadata",
    "compute_illuminance_calibration_from_stats",
]
