"""Studio WebSocket `latter/device/command` handlers and Device setting validators."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import math
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import probatio as vol

from ..areas.actions import async_execute_area_action
from ..const import (
    CONF_ACTIVITY_SOURCES,
    CONF_BLE_BEACON_UUID,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_MA_PLAYER_ENTITY,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_IDS,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_SECURITY_PIN,
    CONF_SECURITY_PIN_HASH,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_DEVICE_REMOTE_GROUP,
    GLOBAL_CONFIG_KEYS,
)
from ..coordinator import LatterCoordinator
from ..groups.device_groups import (
    active_group_keys,
    coordinator_supports_group_key,
    get_device_groups,
)
from ..hub_registry import get_latter_system
from ..hub_sync import async_evaluate_hub_bedtime_schedules
from ..identity import device_entities
from ..media.linking import async_refresh_ma_link
from ..presence.ble_registry import normalize_uuid_hex
from ..protocol_specs import normalize_activity_sources
from ..wallpapers.models import VIRTUAL_COLLECTION_IDS
from ..wallpapers.pools import known_collection_ids, known_wallpaper_ids
from .payload import StudioCommandError, log_studio_event
from .settings_cleaners import (
    SettingsScopeError,
    clean_device_settings,
    system_settings_view,
)
from .state_gates import (
    ALLOWED_DEVICE_ACTIONS,
    DEVICE_ENTITY_VERBS,
    allowed_entity_targets,
    checked_entity_verb,
)

MAX_CUSTOM_PHOTO_POOL: Final = 200
_OPT_STR_MAX_LEN: Final = 128

CommandHandler = Callable[
    [HomeAssistant, LatterCoordinator | None, dict[str, Any], dict[str, Any], dict[str, Any]],
    Awaitable[None],
]


async def evaluate_bedtime_if_ready(hass: HomeAssistant) -> None:
    """Re-evaluate hub bedtime schedules when `LatterSystemHub` is initialized."""
    sys_obj = get_latter_system(hass)
    if sys_obj is not None:
        if hasattr(sys_obj, "async_evaluate_bedtime_schedules"):
            await sys_obj.async_evaluate_bedtime_schedules()
        else:
            await async_evaluate_hub_bedtime_schedules(sys_obj)


def validate_remote_group_choice(
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


def validate_device_camera_lists(
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


def _normalize_device_beacon_uuid_update(
    coordinator: LatterCoordinator, updates: dict[str, Any]
) -> None:
    """Keep auto-derived or default BLE UUIDs unpinned so System UUID rotation stays automatic."""
    if CONF_BLE_BEACON_UUID not in updates or coordinator.is_ble_tag:
        return
    norm_submitted = normalize_uuid_hex(str(updates[CONF_BLE_BEACON_UUID] or ""))
    if norm_submitted in {
        normalize_uuid_hex(DEFAULT_BLE_BEACON_UUID),
        normalize_uuid_hex(coordinator.derived_ble_beacon_uuid),
    }:
        updates[CONF_BLE_BEACON_UUID] = ""


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


def _prepare_device_config_updates(
    coordinator: LatterCoordinator,
    raw_cfg: dict[str, Any],
    current: dict[str, Any],
    global_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Validate and normalize incoming `save_device_config` settings."""
    updates = clean_device_settings(
        raw_cfg,
        current=current,
        is_round_display=coordinator.is_round_display,
        supports_hw_jpeg=coordinator.supports_hw_jpeg,
        strict_traits=True,
    )
    validate_remote_group_choice(updates, global_cfg)
    validate_device_camera_lists(updates, global_cfg)
    _normalize_device_beacon_uuid_update(coordinator, updates)

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
    return updates


def _merge_group_baseline_for_device(
    coordinator: LatterCoordinator,
    current: dict[str, Any],
    target_grp: dict[str, Any],
    new_grp_id: str,
    explicit_other_updates: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Merge `target_grp`'s active baseline with `explicit_other_updates` for one atomic save."""
    dev_cfg = target_grp.get("device_config") or {}
    baseline_raw: dict[str, Any] = {}
    for key in active_group_keys(target_grp):
        if (
            key not in dev_cfg
            or dev_cfg[key] is None
            or not coordinator_supports_group_key(coordinator, key)
        ):
            continue
        want_v = dev_cfg[key]
        if (
            key == "clock_face"
            and want_v == "Modern Analog"
            and not coordinator.is_round_display
        ):
            want_v = "Minimal Digital"
        baseline_raw[key] = want_v

    baseline_cleaned = (
        clean_device_settings(
            baseline_raw,
            current=current,
            is_round_display=coordinator.is_round_display,
            supports_hw_jpeg=coordinator.supports_hw_jpeg,
        )
        if baseline_raw
        else {}
    )
    combined: dict[str, Any] = {
        **current,
        **baseline_cleaned,
        CONF_DEVICE_GROUP: new_grp_id,
        **explicit_other_updates,
    }
    _strip_global_keys_from_device_cfg(combined)
    wp_override = (
        CONF_WALLPAPER_SOURCE in baseline_cleaned
        or CONF_WALLPAPER_SOURCE in explicit_other_updates
    )
    return combined, wp_override


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
        updates = _prepare_device_config_updates(
            coordinator, raw_cfg, current, global_cfg
        )
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
        if group_changed and target_grp is not None and not coordinator.is_ble_tag:
            combined, wp_override = _merge_group_baseline_for_device(
                coordinator, current, target_grp, new_grp_id, explicit_other_updates
            )
            if combined != current or wp_override:
                if wp_override:
                    wp_val = str(combined.get(CONF_WALLPAPER_SOURCE) or "").strip()
                    coordinator.current_wallpaper = wp_val
                    coordinator.set_configured_wallpaper_source(wp_val)
                coordinator.update_device_config(
                    combined,
                    preserve_group=not bool(explicit_other_updates),
                    defer_apply=True,
                )
                await coordinator.async_apply_options()
        elif merged_device != current or group_changed:
            coordinator.update_device_config(
                merged_device,
                preserve_group=bool(
                    CONF_DEVICE_GROUP in updates and new_grp_id == DEFAULT_DEVICE_GROUP
                ),
                defer_apply=True,
            )
            await coordinator.async_apply_options()
        if ma_link_changed:
            async_refresh_ma_link(hass, coordinator)
        coordinator.bind_wallpaper_cycle_timer()
        coordinator.bind_screensaver_cycle_timer()
        coordinator.async_notify_listeners()
    await evaluate_bedtime_if_ready(hass)
    log_studio_event(
        hass,
        "INFO",
        coordinator.device_slug,
        f"Saved Device settings for '{coordinator.device_slug}'",
    )


def _optional_level(body: dict[str, Any]) -> int | None:
    level = body.get("level")
    if level is None:
        return None
    if isinstance(level, bool):
        raise StudioCommandError("invalid_format", "level must be a number")
    try:
        fval = float(level)
    except (TypeError, ValueError) as err:
        raise StudioCommandError("invalid_format", f"Invalid level: {err}") from None
    if not math.isfinite(fval):
        raise StudioCommandError("invalid_format", "level must be a finite number")
    return round(fval)


def _optional_option(body: dict[str, Any]) -> str | None:
    option = body.get("option")
    return str(option)[:_OPT_STR_MAX_LEN] if option is not None else None


async def _cmd_esphome_entity_action(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    if coordinator is None:
        raise StudioCommandError("not_found", "Device required")
    allowed = {e.entity_id for e in device_entities(hass, coordinator.esphome_device_id)}
    (entity_id,) = allowed_entity_targets(
        [body.get("entity_id")], allowed, f"an entity of {coordinator.device_title}"
    )
    action = checked_entity_verb(body, DEVICE_ENTITY_VERBS)
    try:
        await async_execute_area_action(
            hass,
            entity_id=entity_id,
            action=action or "toggle",
            level=_optional_level(body),
            option=_optional_option(body),
            blocking=True,
            raise_on_missing=True,
        )
    except ServiceValidationError as err:
        raise StudioCommandError("invalid_format", str(err)) from err
    except HomeAssistantError as err:
        raise StudioCommandError("command_failed", str(err)) from err


async def _cmd_device_action(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    if coordinator is None:
        raise StudioCommandError("not_found", "Device required")
    action = str(body.get("action") or "").strip().lower()
    if action not in ALLOWED_DEVICE_ACTIONS:
        raise StudioCommandError(
            "invalid_format",
            f"Unsupported device action '{action}' (expected one of {', '.join(ALLOWED_DEVICE_ACTIONS)})",
        )
    try:
        await coordinator.async_send_device_command(action, raise_if_offline=True)
    except HomeAssistantError as err:
        raise StudioCommandError("command_failed", str(err)) from err
    log_studio_event(
        hass,
        "INFO",
        coordinator.device_slug,
        f"Sent device action '{action}' to '{coordinator.device_slug}'",
    )


def _clean_custom_photo_ids(
    raw_photo_ids: Any, known_ids: set[str]
) -> list[str]:
    """Validate and deduplicate `photo_ids` for custom photo pool mode."""
    if not isinstance(raw_photo_ids, list):
        raise StudioCommandError("invalid_format", "photo_ids must be a list")
    cleaned_ids: list[str] = []
    for item in raw_photo_ids:
        pid = str(item or "").strip()
        if pid and pid not in cleaned_ids:
            if pid not in known_ids:
                raise StudioCommandError("not_allowed", f"Unknown photo '{pid}'")
            cleaned_ids.append(pid)
    if not cleaned_ids:
        raise StudioCommandError(
            "invalid_format", "Select at least one photo for custom mode"
        )
    if len(cleaned_ids) > MAX_CUSTOM_PHOTO_POOL:
        raise StudioCommandError(
            "invalid_format",
            f"Custom photo pool cannot exceed {MAX_CUSTOM_PHOTO_POOL} photos",
        )
    return cleaned_ids


def _validate_photo_pool_selection(
    body: dict[str, Any], *, target: str, mode: str
) -> tuple[str, str, list[str]]:
    """Validate `source_id`, `collection_id`, or `photo_ids` for `set_device_photo_pool`."""
    known_ids = known_wallpaper_ids(include_dynamic=(target == "wallpaper"))
    valid_collections = VIRTUAL_COLLECTION_IDS | known_collection_ids()
    source_id = str(body.get("source_id") or "").strip()
    collection_id = str(body.get("collection_id") or "").strip()
    cleaned_ids: list[str] = []

    if mode == "single":
        if not source_id or source_id not in known_ids:
            raise StudioCommandError(
                "not_allowed", "Choose a valid photo from the Photo Library"
            )
    elif mode == "collection":
        if not collection_id or collection_id not in valid_collections:
            raise StudioCommandError(
                "not_found",
                f"Unknown photo collection '{collection_id or '(empty)'}'",
            )
    elif mode == "custom":
        cleaned_ids = _clean_custom_photo_ids(body.get("photo_ids"), known_ids)
    return source_id, collection_id, cleaned_ids


def _apply_wallpaper_pool_locked(
    coordinator: LatterCoordinator,
    merged: dict[str, Any],
    mode: str,
    selection: tuple[str, str, list[str]],
    cycle_minutes: Any,
) -> None:
    """Mutate `merged` and coordinator runtime state for `target == 'wallpaper'`."""
    source_id, collection_id, cleaned_ids = selection
    merged[CONF_WALLPAPER_MODE] = mode
    if mode == "off":
        merged[CONF_WALLPAPER_SOURCE] = ""
        merged[CONF_WALLPAPER_COLLECTION] = ""
        merged[CONF_WALLPAPER_CYCLE_MINUTES] = 0
        coordinator.current_wallpaper = ""
        coordinator.set_configured_wallpaper_source("")
    elif mode == "single":
        merged[CONF_WALLPAPER_SOURCE] = source_id
        merged[CONF_WALLPAPER_COLLECTION] = ""
        coordinator.current_wallpaper = source_id
        coordinator.set_configured_wallpaper_source(source_id)
        if cycle_minutes is None:
            merged[CONF_WALLPAPER_CYCLE_MINUTES] = 0
    elif mode == "collection":
        merged[CONF_WALLPAPER_COLLECTION] = collection_id
        merged[CONF_WALLPAPER_SOURCE] = ""
        coordinator.current_wallpaper = ""
        coordinator.set_configured_wallpaper_source("")
    elif mode == "custom":
        merged[CONF_WALLPAPER_FAVORITES] = list(cleaned_ids)
        merged[CONF_WALLPAPER_COLLECTION] = ""
        merged[CONF_WALLPAPER_SOURCE] = ""
        coordinator.current_wallpaper = ""
        coordinator.set_configured_wallpaper_source("")
    if cycle_minutes is not None:
        merged[CONF_WALLPAPER_CYCLE_MINUTES] = max(0, int(cycle_minutes))
    coordinator.update_device_config(merged)
    coordinator.bind_wallpaper_cycle_timer()


def _apply_screensaver_pool_locked(
    coordinator: LatterCoordinator,
    merged: dict[str, Any],
    mode: str,
    selection: tuple[str, str, list[str]],
    timing: tuple[Any, Any],
) -> None:
    """Mutate `merged` and coordinator runtime state for `target == 'screensaver'`."""
    source_id, collection_id, cleaned_ids = selection
    cycle_minutes, shuffle = timing
    merged[CONF_SCREENSAVER_PHOTO_MODE] = mode
    if mode == "off":
        merged[CONF_SCREENSAVER_PHOTO_SOURCE] = ""
        merged[CONF_SCREENSAVER_PHOTO_COLLECTION] = ""
        coordinator.current_screensaver_photo = ""
    elif mode == "single":
        merged[CONF_SCREENSAVER_PHOTO_SOURCE] = source_id
        merged[CONF_SCREENSAVER_PHOTO_COLLECTION] = ""
        coordinator.current_screensaver_photo = source_id
    elif mode == "collection":
        merged[CONF_SCREENSAVER_PHOTO_COLLECTION] = collection_id
        merged[CONF_SCREENSAVER_PHOTO_SOURCE] = ""
        coordinator.current_screensaver_photo = ""
    elif mode == "custom":
        merged[CONF_SCREENSAVER_PHOTO_IDS] = list(cleaned_ids)
        merged[CONF_SCREENSAVER_PHOTO_COLLECTION] = ""
        merged[CONF_SCREENSAVER_PHOTO_SOURCE] = ""
        coordinator.current_screensaver_photo = ""
    if cycle_minutes is not None:
        merged[CONF_SCREENSAVER_CYCLE_MINUTES] = max(0, int(cycle_minutes))
    if shuffle is not None:
        merged[CONF_SCREENSAVER_SHUFFLE] = bool(shuffle)
    coordinator.update_device_config(merged)
    coordinator.bind_screensaver_cycle_timer()


async def _cmd_set_device_photo_pool(
    _hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    if coordinator is None:
        raise StudioCommandError("not_found", "Device required")
    if coordinator.is_ble_tag or not coordinator.has_display:
        raise StudioCommandError(
            "not_supported",
            f"{coordinator.device_title} has no display for photo pools",
        )
    target = str(body.get("target") or "").strip().lower()
    if target not in ("wallpaper", "screensaver"):
        raise StudioCommandError(
            "invalid_format", "target must be 'wallpaper' or 'screensaver'"
        )
    mode = str(body.get("mode") or "").strip().lower()
    if mode not in ("off", "single", "collection", "custom"):
        raise StudioCommandError(
            "invalid_format", "mode must be one of off, single, collection, custom"
        )
    selection = _validate_photo_pool_selection(body, target=target, mode=mode)
    cycle_minutes = body.get("cycle_minutes")
    shuffle = body.get("shuffle")

    async with coordinator.config_lock:
        merged = dict(coordinator.device_data)
        if target == "wallpaper":
            _apply_wallpaper_pool_locked(
                coordinator, merged, mode, selection, cycle_minutes
            )
        else:
            _apply_screensaver_pool_locked(
                coordinator, merged, mode, selection, (cycle_minutes, shuffle)
            )
        coordinator.schedule_persist_runtime_state()
        coordinator.async_notify_listeners()


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


DEVICE_COMMAND_SCHEMAS: dict[str, vol.Schema] = {
    "save_device_config": _schema({
        vol.Optional("config"): dict,
        vol.Optional("expected_config_rev"): vol.Any(_non_bool_int, None),
    }),
    "device_action": _schema({vol.Optional("action"): _str_cap(64)}),
    "esphome_entity_action": _schema({
        vol.Optional("entity_id"): vol.Any(_str_cap(128), None),
        vol.Optional("action"): _str_cap(64),
        vol.Optional("level"): vol.Any(_non_bool_number, str, None),
        vol.Optional("option"): vol.Any(_str_cap(128), None),
    }),
    "set_device_photo_pool": _schema({
        vol.Optional("target"): _str_cap(32),
        vol.Optional("mode"): _str_cap(32),
        vol.Optional("source_id"): vol.Any(_str_cap(128), None),
        vol.Optional("collection_id"): vol.Any(_str_cap(64), None),
        vol.Optional("photo_ids"): [_str_cap(128)],
        vol.Optional("cycle_minutes"): vol.Any(_non_bool_int, None),
        vol.Optional("shuffle"): vol.Any(bool, None),
    }),
}

DEVICE_COMMAND_HANDLERS: dict[str, CommandHandler] = {
    "save_device_config": _cmd_save_device_config,
    "device_action": _cmd_device_action,
    "esphome_entity_action": _cmd_esphome_entity_action,
    "set_device_photo_pool": _cmd_set_device_photo_pool,
}

__all__ = [
    "DEVICE_COMMAND_HANDLERS",
    "DEVICE_COMMAND_SCHEMAS",
    "MAX_CUSTOM_PHOTO_POOL",
    "CommandHandler",
    "_cmd_device_action",
    "_cmd_esphome_entity_action",
    "_cmd_save_device_config",
    "_cmd_set_device_photo_pool",
    "evaluate_bedtime_if_ready",
    "validate_device_camera_lists",
    "validate_remote_group_choice",
]
