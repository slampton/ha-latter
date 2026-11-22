"""Studio WebSocket command handlers for System/Device config saves, Device Groups, and security PINs (`L3`)."""

from __future__ import annotations

import re
from typing import Any, Final

from homeassistant.core import HomeAssistant
import voluptuous as vol

from ..const import (
    CONF_ACTIVITY_SOURCES,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_GROUPS,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_MA_PLAYER_ENTITY,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SECURITY_PIN,
    CONF_SECURITY_PIN_HASH,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_DEVICE_REMOTE_GROUP,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
)
from ..coordinator import LatterCoordinator
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
    get_latter_system,
    get_system_config_lock,
    get_system_config_rev,
    iter_coordinators,
)
from ..hub_sync import (
    async_evaluate_hub_bedtime_schedules,
    async_rotate_hub_hmac_secret,
    async_save_and_broadcast_global_config,
)
from ..media.linking import async_refresh_ma_link
from ..protocol_policy import hash_security_pin
from ..protocol_specs import normalize_activity_sources
from .payload_shared import (
    StudioCommandError,
    is_coordinator_online_for_studio,
    log_studio_event,
)
from .settings_cleaners import (
    SettingsScopeError,
    clean_device_settings,
    clean_system_settings,
    system_settings_view,
)
from .state_gates import find_by_subentry_id

_GROUP_NAME_MAX_LEN: Final = 64
_GROUP_DESC_MAX_LEN: Final = 200
_GROUP_ID_MAX_LEN: Final = 48
_GROUP_PREFIX_LEN: Final = 6


async def _evaluate_bedtime_if_ready(hass: HomeAssistant) -> None:
    """Re-evaluate hub bedtime schedules when `LatterSystemHub` is initialized."""
    sys_obj = get_latter_system(hass)
    if sys_obj is not None:
        if hasattr(sys_obj, "async_evaluate_bedtime_schedules"):
            await sys_obj.async_evaluate_bedtime_schedules()
        else:
            await async_evaluate_hub_bedtime_schedules(sys_obj)


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
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        changed = {k: v for k, v in updates.items() if live_cfg.get(k) != v}
        if changed:
            await async_save_and_broadcast_global_config(hass, changed)
    log_studio_event(hass, "INFO", "studio", "Saved System settings")


def _validate_remote_group_choice(
    updates: dict[str, Any], global_cfg: dict[str, Any]
) -> None:
    """Verify `CONF_DEVICE_REMOTE_GROUP` references a known System remote group."""
    if CONF_DEVICE_REMOTE_GROUP not in updates:
        return
    valid_groups = {DEFAULT_DEVICE_REMOTE_GROUP, "all"} | {
        f"group:{g['id']}"
        for g in system_settings_view(global_cfg)["remote_groups"]
    }
    if updates[CONF_DEVICE_REMOTE_GROUP] not in valid_groups:
        raise StudioCommandError(
            "not_found", "Unknown remote group: save the System settings first"
        )


def _validate_device_camera_lists(
    updates: dict[str, Any], global_cfg: dict[str, Any]
) -> None:
    """Ensure per-Device camera and broadcast speaker selections reference configured System entities."""
    sys_view = system_settings_view(global_cfg)
    if (
        CONF_CAMERA_VISIBLE_ENTITIES in updates
        or CONF_CAMERA_CAROUSEL_ENTITIES in updates
    ):
        system_cameras = set(sys_view["camera_entities"])
        for key in (CONF_CAMERA_VISIBLE_ENTITIES, CONF_CAMERA_CAROUSEL_ENTITIES):
            if key not in updates:
                continue
            for cam_id in updates[key]:
                if cam_id not in system_cameras:
                    raise StudioCommandError(
                        "not_found",
                        f"Camera '{cam_id}' is not configured in System shared entities",
                    )
    if CONF_BROADCAST_SPEAKER_ENTITIES in updates:
        system_speakers = set(sys_view["broadcast_speakers"])
        for spk_id in updates[CONF_BROADCAST_SPEAKER_ENTITIES]:
            if spk_id not in system_speakers:
                raise StudioCommandError(
                    "not_found",
                    f"Broadcast speaker '{spk_id}' is not configured in System shared entities",
                )


def _strip_global_keys_from_device_cfg(merged: dict[str, Any]) -> None:
    """Remove write-only PIN and System-scoped keys from a Device config dict."""
    merged.pop(CONF_SECURITY_PIN, None)
    for gk in set(GLOBAL_CONFIG_KEYS) - {CONF_SECURITY_PIN_HASH}:
        merged.pop(gk, None)


def _resolve_device_group_transition(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    updates: dict[str, Any],
    merged_device: dict[str, Any],
) -> tuple[bool, str, dict[str, Any] | None]:
    """Validate and resolve `(group_changed, new_grp_id, target_grp)` for `save_device_config`."""
    if CONF_DEVICE_GROUP not in updates:
        return False, coordinator.device_group, None
    new_grp_id = str(merged_device.get(CONF_DEVICE_GROUP) or "").strip()
    old_grp_id = coordinator.device_group
    target_grp: dict[str, Any] | None = None
    if new_grp_id in ("", DEFAULT_DEVICE_GROUP):
        new_grp_id = DEFAULT_DEVICE_GROUP
        merged_device[CONF_DEVICE_GROUP] = DEFAULT_DEVICE_GROUP
    else:
        groups = get_device_groups(hass)
        target_grp = next((g for g in groups if g.get("id") == new_grp_id), None)
        if target_grp is None:
            raise StudioCommandError(
                "not_found", f"Unknown Device Group '{new_grp_id}'"
            )
        merged_device[CONF_DEVICE_GROUP] = new_grp_id
    return bool(new_grp_id != old_grp_id), new_grp_id, target_grp


async def _cmd_save_device_config(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    if coordinator is None:
        raise StudioCommandError("not_found", "Device required")
    raw_cfg = dict(body.get("config") or {})
    expected_rev = body.get("expected_config_rev")
    async with coordinator.config_lock:
        if (
            expected_rev is not None
            and int(expected_rev) != coordinator.device_config_rev
        ):
            raise StudioCommandError(
                "conflict",
                "Settings changed in another session; refreshed latest state.",
            )
        current = coordinator.device_data
        updates = clean_device_settings(
            raw_cfg,
            current=current,
            is_round_display=coordinator.is_round_display,
            supports_hw_jpeg=coordinator.supports_hw_jpeg,
            strict_traits=True,
        )
        _validate_remote_group_choice(updates, global_cfg)
        _validate_device_camera_lists(updates, global_cfg)

        try:
            if CONF_ACTIVITY_SOURCES in updates:
                updates[CONF_ACTIVITY_SOURCES] = normalize_activity_sources(
                    updates[CONF_ACTIVITY_SOURCES]
                )
        except ValueError as err:
            raise SettingsScopeError(str(err)) from None

        if (
            CONF_WALLPAPER_CYCLE_MINUTES in updates
            and updates[CONF_WALLPAPER_CYCLE_MINUTES] == 0
            and CONF_WALLPAPER_SOURCE not in updates
            and coordinator.current_wallpaper
        ):
            updates[CONF_WALLPAPER_SOURCE] = coordinator.current_wallpaper

        merged_device: dict[str, Any] = {**current, **updates}
        _strip_global_keys_from_device_cfg(merged_device)
        ma_link_changed = merged_device.get(CONF_MA_PLAYER_ENTITY, "") != current.get(
            CONF_MA_PLAYER_ENTITY, ""
        )
        group_changed, new_grp_id, target_grp = _resolve_device_group_transition(
            hass, coordinator, updates, merged_device
        )
        explicit_other_updates = {
            k: v for k, v in updates.items() if k != CONF_DEVICE_GROUP
        }
        if group_changed and target_grp is not None:
            await async_apply_group_baseline_to_coordinators(
                hass, target_grp, [coordinator]
            )
            if explicit_other_updates:
                post_baseline = {**coordinator.device_data, **explicit_other_updates}
                _strip_global_keys_from_device_cfg(post_baseline)
                coordinator.update_device_config(post_baseline, preserve_group=False)
                await coordinator.async_apply_options()
        elif merged_device != current or group_changed:
            coordinator.update_device_config(
                merged_device,
                preserve_group=bool(
                    CONF_DEVICE_GROUP in updates and new_grp_id == DEFAULT_DEVICE_GROUP
                ),
            )
            await coordinator.async_apply_options()
        if ma_link_changed:
            async_refresh_ma_link(hass, coordinator)
        coordinator.bind_wallpaper_cycle_timer()
        coordinator.bind_screensaver_cycle_timer()
        coordinator.async_notify_listeners()
    await _evaluate_bedtime_if_ready(hass)
    log_studio_event(
        hass,
        "INFO",
        coordinator.device_slug,
        f"Saved Device settings for '{coordinator.device_slug}'",
    )


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
    _validate_remote_group_choice(cleaned, global_cfg)
    _validate_device_camera_lists(cleaned, global_cfg)
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


async def _cmd_update_group_baseline(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    g_id = str(body.get("group_id") or "").strip()
    async with get_system_config_lock(hass):
        groups = get_device_groups(hass)
        grp = next((g for g in groups if g.get("id") == g_id), None)
        if grp is None:
            raise StudioCommandError("not_found", f"Unknown Device Group '{g_id}'")

        all_coords = list(iter_coordinators(hass))
        member_targets = [
            c for c in all_coords if not c.is_ble_tag and c.device_group == g_id
        ]

        if body.get("reset_to_default") is True:
            reset_grp = reset_builtin_group_entry(g_id)
            if reset_grp is None:
                raise StudioCommandError(
                    "not_allowed",
                    "Only built-in Device Groups can be reset to preset defaults",
                )
            for idx_g, existing_g in enumerate(groups):
                if existing_g.get("id") == g_id:
                    groups[idx_g] = reset_grp
                    grp = reset_grp
                    break
            await async_save_and_broadcast_global_config(
                hass, {CONF_DEVICE_GROUPS: groups}
            )
            if member_targets:
                await async_apply_group_baseline_to_coordinators(
                    hass, grp, member_targets
                )
            log_studio_event(
                hass,
                "INFO",
                "studio",
                f"Reset preset defaults for '{grp.get('name', g_id)}' ({len(member_targets)} Device(s))",
            )
            return

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
    await _evaluate_bedtime_if_ready(hass)
    log_studio_event(
        hass,
        "INFO",
        "studio",
        f"Updated baseline for '{grp.get('name', g_id)}' ({len(member_targets)} Device(s))",
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
    _validate_remote_group_choice(validated_once, global_cfg)
    _validate_device_camera_lists(validated_once, global_cfg)
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
            coord.update_device_config(merged)
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
    for c in targets:
        await _async_apply_batch_to_coordinator(c, filtered)
    await _evaluate_bedtime_if_ready(hass)


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
            target_coord.update_device_config(merged_pin_cfg)
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


def _str_cap(max_len: int) -> Any:
    return vol.All(str, vol.Length(max=max_len))


def _non_bool_int(val: Any) -> int:
    if isinstance(val, bool) or not isinstance(val, int):
        raise vol.Invalid("Expected an integer")
    return val


def _schema(fields: dict[Any, Any]) -> vol.Schema:
    return vol.Schema(fields, extra=vol.PREVENT_EXTRA)


GROUPS_SECURITY_SCHEMAS: dict[str, vol.Schema] = {
    "save_system_config": _schema({
        vol.Optional("config"): dict,
        vol.Optional("expected_config_rev"): vol.Any(_non_bool_int, None),
    }),
    "save_device_config": _schema({
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

__all__ = [
    "GROUPS_SECURITY_SCHEMAS",
    "_cmd_apply_batch_device_setting",
    "_cmd_create_device_group",
    "_cmd_delete_device_group",
    "_cmd_rotate_signing_key",
    "_cmd_save_device_config",
    "_cmd_save_system_config",
    "_cmd_set_security_pin",
    "_cmd_update_group_baseline",
    "_validate_device_camera_lists",
]
