"""Admin-gated WebSocket API commands for Latter Studio.

The websocket type is the scope (`studio/settings.py`): `latter/system/*` commands never act on the
Studio's selected Device (a System command that acts on one Device names it in its own payload), and
`latter/device/*` commands act on the Device named by the message's required `subentry_id`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import copy
import logging
import math
import re
import time
from typing import Any
from urllib.parse import quote

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.util import dt as dt_util
import voluptuous as vol

from ..areas import async_execute_area_action
from ..backup import async_restore_backup_bundle, build_backup_bundle
from ..config_flow import _bound_elsewhere, _device_title, _device_unique_id
from ..const import (
    CONF_ACTIVITY_SOURCES,
    CONF_AREA_FUSION_CONFIG,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AREA_SIGNATURES,
    CONF_BLE_CATEGORY,
    CONF_BLE_SCANNER_OFFSETS,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_GROUPS,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_ESPHOME_DEVICE_ID,
    CONF_IGNORED_DISCOVERED_DEVICES,
    CONF_MA_PLAYER_ENTITY,
    CONF_SECURITY_PIN,
    CONF_SECURITY_PIN_HASH,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DEFAULT_BLE_CATEGORY,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_DEVICE_REMOTE_GROUP,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    STUDIO_REV,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
    normalize_device_slug,
)
from ..coordinator import LatterCoordinator
from ..doorbell import async_execute_doorbell_intercom
from ..groups import (
    DEFAULT_DEVICE_GROUPS,
    GROUP_ALL_DEVICE_KEYS,
    async_apply_group_baseline_to_coordinators,
    async_reset_device,
    coordinator_supports_group_key,
    default_group_baseline_config,
    get_device_groups,
    resolve_behavior_key_value,
    seed_group_baseline_from_coordinator,
)
from ..hub import (
    async_save_and_broadcast_global_config,
    get_latter_system,
    get_system_config_lock,
    get_system_config_rev,
    iter_coordinators,
)
from ..identity import (
    device_entities,
    get_bound_esphome_device,
    is_esphome_device,
    is_latter_compatible_esphome_device,
)
from ..media import async_refresh_ma_link
from ..presence import (
    area_fusion_sensor_choices,
    get_all_areas_presence_summary,
    get_area_signatures_summary,
    get_ble_fabric,
)
from ..protocol import hash_security_pin, normalize_activity_sources
from ..wallpapers import (
    delete_uploaded_wallpaper,
    known_wallpaper_ids,
    wallpaper_snapshot_token,
)
from .payload import (
    STUDIO_BULK_CONTROL_DOMAINS,
    _build_system_shared_controls,
    build_studio_state_payload,
    is_coordinator_online_for_studio,
    log_studio_event,
    resolve_target_coordinator,
)
from .settings import (
    ALLOWED_DEVICE_ACTIONS,
    DEVICE_ENTITY_VERBS,
    MAX_IGNORED_DISCOVERED,
    SYSTEM_ENTITY_VERBS,
    CatalogGate,
    Scope,
    SectionHashGate,
    SettingsScopeError,
    TargetNotAllowed,
    UnknownStudioCommand,
    allowed_entity_targets,
    checked_entity_verb,
    clean_announcement,
    clean_area_fusion,
    clean_device_settings,
    clean_system_settings,
    command_scope,
    find_by_subentry_id,
    system_settings_view,
)

_LOGGER = logging.getLogger(__name__)
_SURVEY_COALESCE_INTERVAL_S = 0.25


def _str_cap(max_len: int) -> Any:
    """Voluptuous validator for strings capped at `max_len` characters."""
    return vol.All(str, vol.Length(max=max_len))


def _non_bool_number(val: Any) -> int | float:
    """Reject booleans while accepting finite int/float numbers."""
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise vol.Invalid("Expected a number")
    if not math.isfinite(float(val)):
        raise vol.Invalid("Expected a finite number")
    return val


def _non_bool_int(val: Any) -> int:
    """Reject booleans while accepting integers."""
    if isinstance(val, bool) or not isinstance(val, int):
        raise vol.Invalid("Expected an integer")
    return val


_COMMAND_PAYLOAD_SCHEMAS: dict[str, vol.Schema] = {
    "set_ble_scanner_offset": vol.Schema(
        {
            vol.Optional("scanner_source"): _str_cap(128),
            vol.Optional("offset_db"): vol.Any(_non_bool_number, None),
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "set_area_fusion": vol.Schema(
        {
            vol.Optional("area_id"): _str_cap(128),
            vol.Optional("mode"): _str_cap(32),
            vol.Optional("threshold_pct"): vol.Any(_non_bool_number, str),
            vol.Optional("sensors"): [_str_cap(128)],
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "capture_ble_area_signature": vol.Schema(
        {
            vol.Optional("area_id"): _str_cap(128),
            vol.Optional("survey_subentry_id"): _str_cap(128),
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "clear_ble_area_signature": vol.Schema(
        {vol.Optional("area_id"): _str_cap(128)},
        extra=vol.PREVENT_EXTRA,
    ),
    "system_entity_action": vol.Schema(
        {
            vol.Optional("entity_ids"): [vol.Any(_str_cap(128), None)],
            vol.Optional("action"): _str_cap(64),
            vol.Optional("level"): vol.Any(_non_bool_number, str, None),
            vol.Optional("option"): vol.Any(_str_cap(128), None),
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "esphome_entity_action": vol.Schema(
        {
            vol.Optional("entity_id"): vol.Any(_str_cap(128), None),
            vol.Optional("action"): _str_cap(64),
            vol.Optional("level"): vol.Any(_non_bool_number, str, None),
            vol.Optional("option"): vol.Any(_str_cap(128), None),
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "device_action": vol.Schema(
        {vol.Optional("action"): _str_cap(64)},
        extra=vol.PREVENT_EXTRA,
    ),
    "test_doorbell_speaker": vol.Schema(
        {
            vol.Optional("subentry_id"): _str_cap(128),
            vol.Optional("camera_entity"): _str_cap(128),
            vol.Optional("message"): _str_cap(250),
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "send_announcement": vol.Schema(
        {
            vol.Optional("mode"): _str_cap(32),
            vol.Optional("target_device"): _str_cap(128),
            vol.Optional("title"): _str_cap(64),
            vol.Optional("message"): _str_cap(500),
            vol.Optional("priority"): _str_cap(32),
            vol.Optional("include_camera"): bool,
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "check_system_updates": vol.Schema({}, extra=vol.PREVENT_EXTRA),
    "clear_internal_logs": vol.Schema({}, extra=vol.PREVENT_EXTRA),
    "select_wallpaper": vol.Schema(
        {vol.Optional("source_id"): _str_cap(128)},
        extra=vol.PREVENT_EXTRA,
    ),
    "toggle_wallpaper_favorite": vol.Schema(
        {
            vol.Optional("source_id"): _str_cap(128),
            vol.Optional("source_ids"): [_str_cap(128)],
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "delete_wallpaper": vol.Schema(
        {vol.Optional("source_id"): _str_cap(128)},
        extra=vol.PREVENT_EXTRA,
    ),
    "mint_camera_preview_url": vol.Schema(
        {vol.Optional("camera_entity"): _str_cap(128)},
        extra=vol.PREVENT_EXTRA,
    ),
    "ignore_discovered_device": vol.Schema(
        {vol.Optional("esphome_device_id"): _str_cap(128)},
        extra=vol.PREVENT_EXTRA,
    ),
    "unignore_discovered_device": vol.Schema(
        {vol.Optional("esphome_device_id"): _str_cap(128)},
        extra=vol.PREVENT_EXTRA,
    ),
    "save_system_config": vol.Schema(
        {
            vol.Optional("config"): dict,
            vol.Optional("expected_config_rev"): vol.Any(_non_bool_int, None),
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "save_device_config": vol.Schema(
        {
            vol.Optional("config"): dict,
            vol.Optional("expected_config_rev"): vol.Any(_non_bool_int, None),
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "remove_device": vol.Schema(
        {vol.Optional("subentry_id"): _str_cap(128)},
        extra=vol.PREVENT_EXTRA,
    ),
    "add_latter_device": vol.Schema(
        {
            vol.Optional("esphome_device_id"): _str_cap(128),
            vol.Optional("device_group"): _str_cap(64),
            vol.Optional("assigned_person"): _str_cap(128),
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "add_ble_device": vol.Schema(
        {
            vol.Optional("name"): _str_cap(64),
            vol.Optional("target_address"): _str_cap(128),
            vol.Optional("assigned_person"): _str_cap(128),
            vol.Optional(CONF_BLE_CATEGORY): _str_cap(32),
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "create_device_group": vol.Schema(
        {
            vol.Optional("name"): _str_cap(64),
            vol.Optional("description"): _str_cap(200),
            vol.Optional("source_subentry_id"): _str_cap(128),
            vol.Optional("assign_source"): bool,
            vol.Optional("include_display"): bool,
            vol.Optional("include_interface"): bool,
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "delete_device_group": vol.Schema(
        {vol.Optional("group_id"): _str_cap(64)},
        extra=vol.PREVENT_EXTRA,
    ),
    "update_group_baseline": vol.Schema(
        {
            vol.Optional("group_id"): _str_cap(64),
            vol.Optional("include_display"): bool,
            vol.Optional("include_interface"): bool,
            vol.Optional("source_subentry_id"): _str_cap(128),
            vol.Optional("copy_keys"): [_str_cap(64)],
            vol.Optional("config"): dict,
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "apply_batch_device_setting": vol.Schema(
        {
            vol.Optional("target"): _str_cap(96),
            vol.Optional("config"): dict,
            vol.Optional("source_subentry_id"): _str_cap(128),
            vol.Optional("copy_keys"): [_str_cap(64)],
        },
        extra=vol.PREVENT_EXTRA,
    ),
    "rotate_signing_key": vol.Schema({}, extra=vol.PREVENT_EXTRA),
    "set_security_pin": vol.Schema(
        {
            vol.Optional("subentry_id"): _str_cap(128),
            vol.Optional("pin"): _str_cap(32),
            vol.Optional("clear"): bool,
        },
        extra=vol.PREVENT_EXTRA,
    ),
}


class StudioCommandError(Exception):
    """A Studio command rejected its input; sent to the panel as a websocket error with `code`."""

    def __init__(self, code: str, message: str) -> None:
        """Store the websocket error code alongside the message."""
        super().__init__(message)
        self.code = code


def _check_studio_rev(
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> bool:
    """Validate mandatory `studio_rev`; send `studio_rev_mismatch` and return False on mismatch."""
    rev = msg.get("studio_rev")
    if rev != STUDIO_REV:
        connection.send_error(
            msg["id"],
            "studio_rev_mismatch",
            f"Studio client revision ({rev}) does not match backend revision ({STUDIO_REV}); reload Latter Studio.",
        )
        return False
    return True


def _payload_device(
    hass: HomeAssistant, body: dict[str, Any], purpose: str
) -> LatterCoordinator:
    """Return the Device a System command names in its payload (`subentry_id`), else fail."""
    coord = find_by_subentry_id(
        iter_coordinators(hass), str(body.get("subentry_id") or "")
    )
    if coord is None:
        raise StudioCommandError("not_found", f"Choose {purpose}")
    return coord


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
    return str(option)[:128] if option is not None else None


def _apply_wallpaper_config(
    coordinator: LatterCoordinator,
    *,
    source: str | None = None,
    favorites: list[str] | None = None,
    cycle_minutes: int | None = None,
) -> None:
    """Persist wallpaper source/favorites/rotation, re-bind the rotation timer, and notify listeners."""
    merged: dict[str, Any] = dict(coordinator.device_data)
    if source is not None:
        merged[CONF_WALLPAPER_SOURCE] = source
        coordinator.current_wallpaper = source
        coordinator._configured_wallpaper_source = source
        coordinator._schedule_persist_runtime_state()
    if favorites is not None:
        merged[CONF_WALLPAPER_FAVORITES] = favorites
    if cycle_minutes is not None:
        merged[CONF_WALLPAPER_CYCLE_MINUTES] = max(0, int(cycle_minutes))
    coordinator.update_device_config(merged)
    if coordinator.wallpaper_cycle_minutes > 0 and source != "":
        coordinator.ensure_active_wallpaper_for_rotation()
    coordinator._bind_wallpaper_cycle_timer()
    coordinator.async_notify_listeners()


# ---------------------------------------------------------------------------
# Command Handlers (Dispatch Dict)
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
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_offsets = live_cfg.get(CONF_BLE_SCANNER_OFFSETS)
        offsets: dict[str, float] = {}
        if isinstance(raw_offsets, dict):
            for k, v in raw_offsets.items():
                norm_k = str(k or "").strip().upper()
                if norm_k:
                    try:
                        offsets[norm_k] = round(max(-25.0, min(25.0, float(v))), 1)
                    except (TypeError, ValueError):
                        pass
        if abs(offset_val) < 0.1:
            offsets.pop(scanner_source, None)
        else:
            offsets[scanner_source] = round(max(-25.0, min(25.0, offset_val)), 1)
        await async_save_and_broadcast_global_config(
            hass, {CONF_BLE_SCANNER_OFFSETS: offsets}
        )


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
    allowed_sensors = {
        s["entity_id"] for s in area_fusion_sensor_choices(hass, area_id)
    }
    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_fusion = live_cfg.get(CONF_AREA_FUSION_CONFIG) or {}
        fusion_cfg = dict(raw_fusion) if isinstance(raw_fusion, dict) else {}
        current_area = fusion_cfg.get(area_id)
        fusion_cfg[area_id] = clean_area_fusion(
            current_area if isinstance(current_area, dict) else {},
            {k: body[k] for k in ("mode", "threshold_pct", "sensors") if k in body},
            allowed_sensors,
        )
        await async_save_and_broadcast_global_config(
            hass, {CONF_AREA_FUSION_CONFIG: fusion_cfg}
        )
    fabric = get_ble_fabric(hass)
    fabric.rebind_fusion_sensor_listener()
    fabric.notify_occupancy_listeners()


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
            "invalid_format",
            "survey_subentry_id is required: select the BLE survey Device",
        )
    survey_coord = find_by_subentry_id(iter_coordinators(hass), survey_id)
    if survey_coord is None:
        raise StudioCommandError(
            "not_found", f"No Latter Device with subentry_id '{survey_id}'"
        )
    if survey_coord._ble_tracker is None:
        raise StudioCommandError(
            "not_supported",
            f"{survey_coord.device_title} has no BLE tracker: enable Track the Area with BLE Proxies for it first",
        )

    scanners_sig = survey_coord._ble_tracker.capture_area_signature()
    if not scanners_sig:
        raise StudioCommandError(
            "not_ready",
            "No fresh Bluetooth proxy readings yet for this Device — wait a few seconds and try again",
        )

    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_sigs = live_cfg.get(CONF_BLE_AREA_SIGNATURES)
        signatures = dict(raw_sigs) if isinstance(raw_sigs, dict) else {}
        signatures[target_area_id] = {
            "scanners": scanners_sig,
            "captured_at": dt_util.utcnow().isoformat(timespec="seconds"),
            "sample_count": sum(int(v.get("n", 1)) for v in scanners_sig.values()),
        }
        await async_save_and_broadcast_global_config(
            hass, {CONF_BLE_AREA_SIGNATURES: signatures}
        )
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
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_sigs = live_cfg.get(CONF_BLE_AREA_SIGNATURES)
        signatures = dict(raw_sigs) if isinstance(raw_sigs, dict) else {}
        signatures.pop(target_area_id, None)
        await async_save_and_broadcast_global_config(
            hass, {CONF_BLE_AREA_SIGNATURES: signatures}
        )


async def _cmd_system_entity_action(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    shared_controls = _build_system_shared_controls(hass)
    allowed = {
        str(target["entity_id"])
        for ctrl in shared_controls
        for target in ctrl["targets"]
        if target.get("entity_id")
    }
    entity_ids = allowed_entity_targets(
        body.get("entity_ids") or [], allowed, "a shared control of a Latter Device"
    )
    action = checked_entity_verb(body, SYSTEM_ENTITY_VERBS)
    level_val = _optional_level(body)
    opt_val = _optional_option(body)
    try:
        for ent_id in entity_ids:
            await async_execute_area_action(
                hass,
                entity_id=ent_id,
                action=action or "toggle",
                level=level_val,
                option=opt_val,
                blocking=True,
                raise_on_missing=True,
            )
    except ServiceValidationError as err:
        raise StudioCommandError("invalid_format", str(err)) from err
    except HomeAssistantError as err:
        raise StudioCommandError("command_failed", str(err)) from err


async def _cmd_esphome_entity_action(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    assert coordinator is not None
    allowed = {e.entity_id for e in device_entities(hass, coordinator.esphome_device_id)}
    (entity_id,) = allowed_entity_targets(
        [body.get("entity_id")], allowed, f"an entity of {coordinator.device_title}"
    )
    action = checked_entity_verb(body, DEVICE_ENTITY_VERBS)
    level_val = _optional_level(body)
    opt_val = _optional_option(body)
    try:
        await async_execute_area_action(
            hass,
            entity_id=entity_id,
            action=action or "toggle",
            level=level_val,
            option=opt_val,
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
    assert coordinator is not None
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
        raise StudioCommandError("invalid_format", "Add a camera in Shared Entities first")
    if cam_ent not in cameras:
        raise StudioCommandError("not_allowed", f"'{cam_ent}' isn't one of the System cameras")
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
            e.entity_id
            for e in device_entities(hass, c.esphome_device_id, domain="update")
        ]
        for c in coords
    }
    all_ids = [eid for ids in update_ids.values() for eid in ids]
    if all_ids:
        try:
            async with asyncio.timeout(30):
                await hass.services.async_call(
                    "homeassistant",
                    "update_entity",
                    {"entity_id": all_ids},
                    blocking=True,
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
            if any(
                (st := hass.states.get(eid)) is not None and st.state == "on"
                for eid in ids
            )
        ),
    }


async def _cmd_select_wallpaper(
    _hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    assert coordinator is not None
    source_id = str(body.get("source_id") or "").strip()
    async with coordinator.config_lock:
        if not source_id:
            _apply_wallpaper_config(coordinator, source="", cycle_minutes=0)
            return
        known = known_wallpaper_ids()
        if source_id not in known:
            raise StudioCommandError(
                "not_allowed", "Unknown wallpaper: pick one from this Device's gallery"
            )
        valid_favs = [f for f in coordinator.wallpaper_favorites if f in known]
        next_cycle: int | None = None
        if (
            coordinator.wallpaper_cycle_minutes > 0
            and valid_favs
            and source_id not in valid_favs
        ):
            next_cycle = 0
        _apply_wallpaper_config(
            coordinator, source=source_id, cycle_minutes=next_cycle
        )


async def _cmd_toggle_wallpaper_favorite(
    _hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    assert coordinator is not None
    async with coordinator.config_lock:
        known = known_wallpaper_ids()
        if "source_ids" in body:
            raw_ids = body.get("source_ids")
            if not isinstance(raw_ids, list):
                raise StudioCommandError("invalid_format", "source_ids must be a list")
            cleaned: list[str] = []
            seen: set[str] = set()
            for item in raw_ids:
                sid = str(item or "").strip()
                if sid and sid not in seen:
                    seen.add(sid)
                    cleaned.append(sid)
            if cleaned and any(sid not in known for sid in cleaned):
                raise StudioCommandError(
                    "not_allowed",
                    "Unknown wallpaper: pick one from this Device's gallery",
                )
            _apply_wallpaper_config(coordinator, favorites=cleaned)
            return

        source_id = str(body.get("source_id") or "").strip()
        favs = list(coordinator.wallpaper_favorites)
        if source_id in favs:
            favs.remove(source_id)
        else:
            if source_id not in known:
                raise StudioCommandError(
                    "not_allowed",
                    "Unknown wallpaper: pick one from this Device's gallery",
                )
            favs.append(source_id)
        _apply_wallpaper_config(coordinator, favorites=favs)


def _prune_deleted_wallpaper_from_coordinators(
    hass: HomeAssistant, source_id: str
) -> None:
    """Remove a deleted wallpaper from favorites and advance rotation (or clear static source)."""
    for c in iter_coordinators(hass):
        if source_id not in c.wallpaper_favorites and c.wallpaper_source != source_id:
            continue
        favs = [f for f in c.wallpaper_favorites if f != source_id]
        was_active = c.wallpaper_source == source_id
        if was_active and c.wallpaper_cycle_minutes > 0:
            _apply_wallpaper_config(c, source="", favorites=favs)
            if c.ensure_active_wallpaper_for_rotation():
                c._bind_wallpaper_cycle_timer()
                c.async_notify_listeners()
            else:
                _apply_wallpaper_config(c, source="", favorites=favs, cycle_minutes=0)
        else:
            new_active = "" if was_active else c.wallpaper_source
            _apply_wallpaper_config(c, source=new_active, favorites=favs)


async def _cmd_delete_wallpaper(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    source_id = str(body.get("source_id") or "").strip()
    if not source_id:
        raise StudioCommandError("invalid_format", "source_id is required")
    deleted = await hass.async_add_executor_job(
        delete_uploaded_wallpaper,
        hass,
        source_id,
    )
    if not deleted:
        raise StudioCommandError("not_found", "That wallpaper isn't an uploaded photo")
    _prune_deleted_wallpaper_from_coordinators(hass, source_id)


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
        ttl_s=600,
    )
    extra["camera_entity"] = cam_ent
    extra["preview_url"] = (
        f"/api/latter/camera/system"
        f"?entity_id={quote(cam_ent, safe='')}&w=320&h=180&shape=square&sig={sig}"
    )
    extra["expires_in"] = 600


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
        raise StudioCommandError(
            "not_found", f"Unknown ESPHome device '{esp_dev_id}'"
        )
    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
        raw_ignored = live_cfg.get(CONF_IGNORED_DISCOVERED_DEVICES) or []
        ignored = [
            str(x).strip()
            for x in (raw_ignored if isinstance(raw_ignored, list) else [])
            if str(x or "").strip()
        ]
        if esp_dev_id not in ignored:
            ignored.append(esp_dev_id)
            ignored = ignored[:MAX_IGNORED_DISCOVERED]
            await async_save_and_broadcast_global_config(
                hass, {CONF_IGNORED_DISCOVERED_DEVICES: ignored}
            )
    log_studio_event(
        hass, "INFO", "studio", f"Ignored discovered device '{_device_title(dev)}'"
    )


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
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
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
        if expected_rev is not None and int(expected_rev) != get_system_config_rev(hass):
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


async def _cmd_save_device_config(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    assert coordinator is not None
    raw_cfg = dict(body.get("config") or {})
    expected_rev = body.get("expected_config_rev")
    async with coordinator.config_lock:
        if expected_rev is not None and int(expected_rev) != coordinator.device_config_rev:
            raise StudioCommandError(
                "conflict",
                "Settings changed in another session; refreshed latest state.",
            )
        current = coordinator.device_data
        updates = clean_device_settings(
            raw_cfg,
            current=current,
            is_round_display=coordinator.is_round_display,
            strict_traits=True,
        )

        if CONF_DEVICE_REMOTE_GROUP in updates:
            valid_groups = {DEFAULT_DEVICE_REMOTE_GROUP, "all"} | {
                f"group:{g['id']}"
                for g in system_settings_view(global_cfg)["remote_groups"]
            }
            if updates[CONF_DEVICE_REMOTE_GROUP] not in valid_groups:
                raise StudioCommandError(
                    "not_found", "Unknown remote group: save the System settings first"
                )

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
        merged_device.pop(CONF_SECURITY_PIN, None)
        for gk in set(GLOBAL_CONFIG_KEYS) - {CONF_SECURITY_PIN_HASH}:
            merged_device.pop(gk, None)

        ma_link_changed = merged_device.get(CONF_MA_PLAYER_ENTITY, "") != current.get(
            CONF_MA_PLAYER_ENTITY, ""
        )
        group_in_updates = CONF_DEVICE_GROUP in updates
        new_grp_id = str(merged_device.get(CONF_DEVICE_GROUP) or "").strip()
        old_grp_id = coordinator.device_group
        target_grp: dict[str, Any] | None = None
        if group_in_updates:
            if new_grp_id in ("", DEFAULT_DEVICE_GROUP):
                new_grp_id = DEFAULT_DEVICE_GROUP
                merged_device[CONF_DEVICE_GROUP] = DEFAULT_DEVICE_GROUP
            else:
                groups = get_device_groups(hass)
                target_grp = next(
                    (g for g in groups if g.get("id") == new_grp_id), None
                )
                if target_grp is None:
                    raise StudioCommandError(
                        "not_found", f"Unknown Device Group '{new_grp_id}'"
                    )
                merged_device[CONF_DEVICE_GROUP] = new_grp_id
        group_changed = bool(group_in_updates and new_grp_id != old_grp_id)
        if merged_device != current or group_changed:
            coordinator.update_device_config(
                merged_device, preserve_group=(target_grp is not None)
            )
            await coordinator.async_apply_options()
        if target_grp is not None:
            await async_apply_group_baseline_to_coordinators(
                hass, target_grp, [coordinator]
            )
        if ma_link_changed:
            async_refresh_ma_link(hass, coordinator)
        coordinator._bind_wallpaper_cycle_timer()
        coordinator.async_notify_listeners()
    log_studio_event(
        hass,
        "INFO",
        coordinator.device_slug,
        f"Saved Device settings for '{coordinator.device_slug}'",
    )


async def _cmd_clear_internal_logs(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    _body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    hass.data.setdefault(DOMAIN, {})["internal_logs"] = []
    log_studio_event(hass, "INFO", "studio", "Cleared internal diagnostic log")


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
    hass.config_entries.async_remove_subentry(
        target_coord.entry, target_coord.subentry_id
    )
    log_studio_event(
        hass,
        "INFO",
        "studio",
        f"Removed device '{removed_slug}' from Latter",
    )
    extra["removed"] = True
    extra["removed_subentry_id"] = target_coord.subentry_id


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
    esp_dev_id = str(body.get("esphome_device_id") or "").strip()
    if not esp_dev_id:
        raise StudioCommandError(
            "invalid_format", "Choose a discovered Latter ESPHome Device"
        )
    dev = get_bound_esphome_device(hass, esp_dev_id)
    if (
        dev is None
        or not is_esphome_device(hass, dev)
        or not is_latter_compatible_esphome_device(hass, dev)
    ):
        raise StudioCommandError(
            "not_latter_device",
            "Selected ESPHome device is not running Latter firmware",
        )
    target_uid = _device_unique_id(dev)
    if _bound_elsewhere(system_entries[0], dev, target_uid):
        raise StudioCommandError(
            "already_configured",
            f"'{_device_title(dev)}' is already managed in Latter",
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
        raise StudioCommandError(
            "not_found", f"Unknown person entity '{assigned_person}'"
        )
    init_data: dict[str, Any] = {
        CONF_ESPHOME_DEVICE_ID: dev.id,
        CONF_DEVICE_GROUP: raw_group,
    }
    if assigned_person:
        init_data[CONF_ASSIGNED_PERSON] = assigned_person
    await hass.config_entries.subentries.async_init(
        (system_entries[0].entry_id, SUBENTRY_DEVICE),
        context={"source": "user"},
        data=init_data,
    )
    async with get_system_config_lock(hass):
        live_cfg: dict[str, Any] = hass.data.setdefault(DOMAIN, {}).setdefault(
            DATA_GLOBAL_CONFIG, {}
        )
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
        (c for c in iter_coordinators(hass) if c.esphome_device_id == dev.id),
        None,
    )
    extra["adopted_esphome_device_id"] = dev.id
    if adopted_coord is not None:
        extra["adopted_subentry_id"] = adopted_coord.subentry_id
    else:
        matched_sub = next(
            (
                sub.subentry_id
                for sub in system_entries[0].subentries.values()
                if sub.data.get(CONF_ESPHOME_DEVICE_ID) == dev.id
            ),
            "",
        )
        if matched_sub:
            extra["adopted_subentry_id"] = matched_sub
    log_studio_event(
        hass,
        "INFO",
        "studio",
        f"Adopted Latter device '{_device_title(dev)}'",
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
        raise StudioCommandError(
            "invalid_format", "A BLE tag needs a name and a target address"
        )
    if any(c.device_slug == target_slug for c in iter_coordinators(hass)):
        raise StudioCommandError(
            "already_configured", f"A Device named '{target_slug}' already exists"
        )
    await hass.config_entries.subentries.async_init(
        (system_entries[0].entry_id, SUBENTRY_BLE_TAG),
        context={"source": "user"},
        data={
            "name": raw_name,
            CONF_BLE_TARGET_ADDRESS: target_addr,
            CONF_BLE_CATEGORY: raw_cat,
            CONF_ASSIGNED_PERSON: assigned_person,
        },
    )
    adopted_ble = next(
        (c for c in iter_coordinators(hass) if c.device_slug == target_slug),
        None,
    )
    if adopted_ble is not None:
        extra["adopted_subentry_id"] = adopted_ble.subentry_id


async def _cmd_create_device_group(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    g_name = str(body.get("name") or "").strip()[:64]
    g_desc = str(body.get("description") or "").strip()[:200]
    if not g_name:
        raise StudioCommandError("invalid_format", "A Device Group needs a name")
    g_id = re.sub(r"[^a-z0-9]+", "_", g_name.lower()).strip("_")[:48] or "group"
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
        if not c.is_ble_tag and str(c.get_opt(CONF_DEVICE_GROUP) or "").strip() == g_id:
            async with c.config_lock:
                c.update_device_config(
                    {**c.device_data, CONF_DEVICE_GROUP: DEFAULT_DEVICE_GROUP}
                )
            c.async_notify_listeners()


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

        all_coords = iter_coordinators(hass)
        member_targets = [
            c for c in all_coords if not c.is_ble_tag and c.device_group == g_id
        ]

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
        raw_updates = dict(body.get("config") or {})

        if source_sub_id:
            source_coord = find_by_subentry_id(all_coords, source_sub_id)
            if source_coord is None or source_coord.is_ble_tag:
                raise StudioCommandError(
                    "not_found", f"No Latter Device with subentry_id '{source_sub_id}'"
                )
            only_keys: list[str] | None = None
            if raw_copy_keys is not None:
                if not isinstance(raw_copy_keys, list):
                    raise StudioCommandError(
                        "invalid_format", "copy_keys must be a list"
                    )
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

        if raw_updates:
            filtered = {
                k: v for k, v in raw_updates.items() if k in GROUP_ALL_DEVICE_KEYS
            }
            if not filtered:
                raise StudioCommandError(
                    "invalid_format",
                    "No supported Device Group baseline settings in payload",
                )
            cleaned = clean_device_settings(filtered, current=grp.get("device_config"))
            if CONF_DEVICE_REMOTE_GROUP in cleaned:
                valid_groups = {DEFAULT_DEVICE_REMOTE_GROUP, "all"} | {
                    f"group:{g['id']}"
                    for g in system_settings_view(global_cfg)["remote_groups"]
                }
                if cleaned[CONF_DEVICE_REMOTE_GROUP] not in valid_groups:
                    raise StudioCommandError(
                        "not_found",
                        "Unknown remote group: save the System settings first",
                    )
            group_updates = {
                k: v for k, v in cleaned.items() if k in GROUP_ALL_DEVICE_KEYS
            }
            if group_updates:
                dev_cfg = dict(
                    grp.get("device_config")
                    or default_group_baseline_config(
                        include_display=bool(grp.get("include_display", False)),
                        include_interface=bool(grp.get("include_interface", False)),
                    )
                )
                dev_cfg.update(group_updates)
                grp["device_config"] = dev_cfg
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
    log_studio_event(
        hass,
        "INFO",
        "studio",
        f"Updated baseline for '{grp.get('name', g_id)}' ({len(member_targets)} Device(s))",
    )


async def _cmd_apply_batch_device_setting(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    raw_target = str(body.get("target") or "all").strip() or "all"

    all_coords_full = iter_coordinators(hass)
    all_coords = [c for c in all_coords_full if not c.is_ble_tag]

    raw_updates = dict(body.get("config") or {})
    source_sub_id = str(body.get("source_subentry_id") or "").strip()
    raw_copy_keys = body.get("copy_keys")
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
            if ck in GROUP_ALL_DEVICE_KEYS and coordinator_supports_group_key(
                source_coord, ck
            ):
                if ck == CONF_WALLPAPER_SOURCE:
                    raw_updates[ck] = source_coord.wallpaper_source
                else:
                    raw_updates[ck] = resolve_behavior_key_value(src_data, ck)

    allowed_keys = set(GROUP_ALL_DEVICE_KEYS)
    filtered = {k: v for k, v in raw_updates.items() if k in allowed_keys}
    if not filtered:
        raise StudioCommandError(
            "invalid_format", "No supported batch device settings in payload"
        )
    validated_once = clean_device_settings(filtered, current=None)
    if CONF_DEVICE_REMOTE_GROUP in validated_once:
        valid_groups = {DEFAULT_DEVICE_REMOTE_GROUP, "all"} | {
            f"group:{g['id']}"
            for g in system_settings_view(global_cfg)["remote_groups"]
        }
        if validated_once[CONF_DEVICE_REMOTE_GROUP] not in valid_groups:
            raise StudioCommandError(
                "not_found", "Unknown remote group: save the System settings first"
            )

    if raw_target == "all":
        targets = all_coords
    elif raw_target == "online":
        targets = [
            c for c in all_coords if is_coordinator_online_for_studio(hass, c)
        ]
    elif raw_target == "roaming":
        targets = [c for c in all_coords if c.is_roaming_device]
    elif raw_target == "stationary":
        targets = [c for c in all_coords if not c.is_roaming_device]
    else:
        target_id = (
            raw_target[6:].strip() if raw_target.startswith("group:") else raw_target
        )
        targets = [c for c in all_coords if c.device_group == target_id]

    for c in targets:
        dev_filtered = {
            k: v
            for k, v in filtered.items()
            if coordinator_supports_group_key(c, k)
        }
        if not dev_filtered:
            continue
        async with c.config_lock:
            dev_cleaned = clean_device_settings(
                dev_filtered,
                current=c.device_data,
                is_round_display=c.is_round_display,
            )
            merged = {**c.device_data, **dev_cleaned}
            wp_override = CONF_WALLPAPER_SOURCE in dev_cleaned
            if merged != c.device_data or wp_override:
                if wp_override:
                    wp_val = str(merged.get(CONF_WALLPAPER_SOURCE) or "").strip()
                    c.current_wallpaper = wp_val
                    c._configured_wallpaper_source = wp_val
                c.update_device_config(merged)
                await c.async_apply_options()
                c._bind_wallpaper_cycle_timer()
                c.async_notify_listeners()


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
    async with get_system_config_lock(hass):
        await sys_obj.async_rotate_hmac_secret()
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
            pin_hash = await hass.async_add_executor_job(
                hash_security_pin, raw_pin
            )
        except ValueError as err:
            raise StudioCommandError("invalid_format", str(err)) from err
        async with get_system_config_lock(hass):
            await async_save_and_broadcast_global_config(
                hass, {CONF_SECURITY_PIN_HASH: pin_hash}
            )
        log_studio_event(hass, "INFO", "system", "Updated System security PIN")


_CommandHandler = Callable[
    [HomeAssistant, LatterCoordinator | None, dict[str, Any], dict[str, Any], dict[str, Any]],
    Awaitable[None],
]

_STUDIO_COMMAND_HANDLERS: dict[str, _CommandHandler] = {
    "set_ble_scanner_offset": _cmd_set_ble_scanner_offset,
    "set_area_fusion": _cmd_set_area_fusion,
    "capture_ble_area_signature": _cmd_capture_ble_area_signature,
    "clear_ble_area_signature": _cmd_clear_ble_area_signature,
    "system_entity_action": _cmd_system_entity_action,
    "esphome_entity_action": _cmd_esphome_entity_action,
    "test_doorbell_speaker": _cmd_test_doorbell_speaker,
    "send_announcement": _cmd_send_announcement,
    "check_system_updates": _cmd_check_system_updates,
    "select_wallpaper": _cmd_select_wallpaper,
    "toggle_wallpaper_favorite": _cmd_toggle_wallpaper_favorite,
    "delete_wallpaper": _cmd_delete_wallpaper,
    "mint_camera_preview_url": _cmd_mint_camera_preview_url,
    "ignore_discovered_device": _cmd_ignore_discovered_device,
    "unignore_discovered_device": _cmd_unignore_discovered_device,
    "save_system_config": _cmd_save_system_config,
    "save_device_config": _cmd_save_device_config,
    "device_action": _cmd_device_action,
    "clear_internal_logs": _cmd_clear_internal_logs,
    "remove_device": _cmd_remove_device,
    "add_latter_device": _cmd_add_latter_device,
    "add_ble_device": _cmd_add_ble_device,
    "create_device_group": _cmd_create_device_group,
    "delete_device_group": _cmd_delete_device_group,
    "update_group_baseline": _cmd_update_group_baseline,
    "apply_batch_device_setting": _cmd_apply_batch_device_setting,
    "rotate_signing_key": _cmd_rotate_signing_key,
    "set_security_pin": _cmd_set_security_pin,
}


async def _async_execute_studio_command(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    cmd: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Validate payload schema, execute a Studio command, and return extra response fields."""
    handler = _STUDIO_COMMAND_HANDLERS.get(cmd)
    if handler is None:
        raise StudioCommandError("unknown_command", f"Unsupported Studio command: {cmd}")
    schema = _COMMAND_PAYLOAD_SCHEMAS.get(cmd)
    if schema is not None:
        try:
            body = dict(schema(body))
        except vol.Invalid as err:
            raise StudioCommandError("invalid_format", str(err)) from err
    extra: dict[str, Any] = {}
    global_cfg: dict[str, Any] = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
    await handler(hass, coordinator, body, global_cfg, extra)
    return extra


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/system/get_state",
        vol.Optional("subentry_id"): vol.Any(str, None),
        vol.Optional("include_logs", default=False): bool,
        vol.Required("studio_rev"): int,
    }
)
@websocket_api.async_response
async def ws_handle_get_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the current Latter Studio state payload."""
    if not _check_studio_rev(connection, msg):
        return
    coord = resolve_target_coordinator(hass, msg.get("subentry_id"))
    connection.send_result(
        msg["id"],
        build_studio_state_payload(
            hass,
            coord,
            include_logs=bool(msg.get("include_logs", False)),
        ),
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/system/subscribe",
        vol.Optional("subentry_id"): vol.Any(str, None),
        vol.Optional("survey_subentry_id"): vol.Any(str, None),
        vol.Optional("include_logs", default=False): bool,
        vol.Required("studio_rev"): int,
    }
)
@websocket_api.async_response
async def ws_handle_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to live Latter Studio state and scoped 4 Hz BLE survey updates."""
    if not _check_studio_rev(connection, msg):
        return
    sub_id = msg.get("subentry_id")
    survey_sub_id = str(msg.get("survey_subentry_id") or "").strip()
    include_logs = bool(msg.get("include_logs", False))
    unsubs: list[Any] = []
    debounce_cancel: list[Any] = [None]
    survey_timer_cancel: list[Any] = [None]
    last_survey_sent_mono: list[float] = [0.0]
    pending_survey_event: list[dict[str, Any] | None] = [None]
    catalog_gate = CatalogGate()
    section_gate = SectionHashGate()

    init_sys = get_latter_system(hass)
    init_raw_cfg = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
    last_wp_token: list[int] = [wallpaper_snapshot_token()]
    last_hmac: list[bytes] = [init_sys.hmac_secret if init_sys is not None else b""]
    last_sigs_raw: list[Any] = [
        copy.deepcopy(init_raw_cfg.get(CONF_BLE_AREA_SIGNATURES))
    ]
    ble_dirty: list[bool] = [False]

    coord = resolve_target_coordinator(hass, sub_id)
    initial_payload = build_studio_state_payload(
        hass,
        coord,
        include_catalog=True,
        include_logs=include_logs,
    )
    section_gate.record_initial(initial_payload)

    @callback
    def _push_now(_now: Any = None) -> None:
        debounce_cancel[0] = None
        cur_coord = resolve_target_coordinator(hass, sub_id)
        cur_sys = get_latter_system(hass)
        cur_wp_tok = wallpaper_snapshot_token()
        cur_hmac = cur_sys.hmac_secret if cur_sys is not None else b""
        cur_raw_cfg = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
        cur_sigs = cur_raw_cfg.get(CONF_BLE_AREA_SIGNATURES)

        skip: set[str] = set()
        if not ble_dirty[0] and section_gate.has_sent("discovered_ble_devices"):
            skip.add("discovered_ble_devices")
        if (
            cur_wp_tok == last_wp_token[0]
            and cur_hmac == last_hmac[0]
            and section_gate.has_sent("system_wallpapers")
        ):
            skip.add("system_wallpapers")
        else:
            last_wp_token[0] = cur_wp_tok
            last_hmac[0] = cur_hmac
        if (
            not ble_dirty[0]
            and cur_sigs == last_sigs_raw[0]
            and section_gate.has_sent("ble_area_signatures")
        ):
            skip.add("ble_area_signatures")
        else:
            last_sigs_raw[0] = copy.deepcopy(cur_sigs)
        ble_dirty[0] = False

        payload = build_studio_state_payload(
            hass,
            cur_coord,
            include_catalog=catalog_gate.take(),
            include_logs=include_logs,
            skip_sections=skip,
        )
        section_gate.filter_sections(payload)
        connection.send_message(websocket_api.event_message(msg["id"], payload))

    @callback
    def _schedule_push() -> None:
        if debounce_cancel[0] is not None:
            return
        debounce_cancel[0] = async_call_later(hass, 0.4, _push_now)

    coord_unsubs: dict[int, Any] = {}

    @callback
    def _track_coordinators() -> None:
        current = iter_coordinators(hass)
        current_ids = {id(c) for c in current}
        changed = False
        for cid in list(coord_unsubs):
            if cid not in current_ids:
                changed = True
                u = coord_unsubs.pop(cid)
                if callable(u):
                    u()
        for c in current:
            cid = id(c)
            if cid not in coord_unsubs:
                changed = True
                coord_unsubs[cid] = c.async_add_listener(_schedule_push)
        if changed:
            ble_dirty[0] = True

    _track_coordinators()
    ble_dirty[0] = False

    ble_fabric = get_ble_fabric(hass)
    unsubs.append(ble_fabric.register_occupancy_listener(_schedule_push))

    if survey_sub_id:

        @callback
        def _flush_pending_survey(_now: Any = None) -> None:
            survey_timer_cancel[0] = None
            ev = pending_survey_event[0]
            pending_survey_event[0] = None
            if ev is None:
                return
            last_survey_sent_mono[0] = time.monotonic()
            connection.send_message(websocket_api.event_message(msg["id"], ev))

        @callback
        def _on_survey_delta(delta: dict[str, Any]) -> None:
            target_coord = find_by_subentry_id(
                iter_coordinators(hass), survey_sub_id
            )
            if target_coord is None or target_coord._ble_tracker is None:
                return
            if str(delta.get("device_slug") or "") != target_coord._ble_tracker._raw_slug:
                return
            ev_payload = {
                "type": "ble_survey_delta",
                "subentry_id": target_coord.subentry_id,
                "ble_packets_seen": int(
                    delta.get("packets_seen")
                    if delta.get("packets_seen") is not None
                    else target_coord._ble_tracker.packets_seen
                ),
                "ble_closest_proxy": str(
                    delta.get("closest_scanner")
                    if delta.get("closest_scanner") is not None
                    else target_coord._ble_tracker.closest_scanner
                ),
                "ble_survey_rows": (
                    delta["calibration"]
                    if isinstance(delta.get("calibration"), list)
                    else target_coord._ble_tracker.get_scanner_calibration_telemetry()
                ),
                "ble_area_signatures": (
                    delta["area_signatures"]
                    if isinstance(delta.get("area_signatures"), list)
                    else get_area_signatures_summary(hass)
                ),
                "area_presence_grid": get_all_areas_presence_summary(hass),
            }
            now_m = time.monotonic()
            elapsed = now_m - last_survey_sent_mono[0]
            if elapsed >= _SURVEY_COALESCE_INTERVAL_S and survey_timer_cancel[0] is None:
                last_survey_sent_mono[0] = now_m
                connection.send_message(
                    websocket_api.event_message(msg["id"], ev_payload)
                )
            else:
                pending_survey_event[0] = ev_payload
                if survey_timer_cancel[0] is None:
                    delay = max(0.05, _SURVEY_COALESCE_INTERVAL_S - max(0.0, elapsed))
                    survey_timer_cancel[0] = async_call_later(
                        hass, delay, _flush_pending_survey
                    )

        unsubs.append(ble_fabric.register_survey_listener(_on_survey_delta))

    state_unsub: list[Any] = [None]

    @callback
    def _entity_changed(_event: Any) -> None:
        _schedule_push()

    @callback
    def _track_device_states() -> None:
        if callable(state_unsub[0]):
            state_unsub[0]()
            state_unsub[0] = None
        target = resolve_target_coordinator(hass, sub_id) if sub_id else None
        watched = [target] if target is not None else iter_coordinators(hass)
        entity_ids = sorted(
            {
                e.entity_id
                for c in watched
                for e in device_entities(hass, c.esphome_device_id)
                if target is not None or e.domain in STUDIO_BULK_CONTROL_DOMAINS
            }
        )
        if entity_ids:
            state_unsub[0] = async_track_state_change_event(
                hass, entity_ids, _entity_changed
            )

    _track_device_states()

    @callback
    def _registry_changed(_event: Any) -> None:
        catalog_gate.mark_dirty()
        ble_dirty[0] = True
        _track_coordinators()
        _track_device_states()
        _schedule_push()

    for registry_event in (
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        dr.EVENT_DEVICE_REGISTRY_UPDATED,
        ar.EVENT_AREA_REGISTRY_UPDATED,
    ):
        unsubs.append(hass.bus.async_listen(registry_event, _registry_changed))

    @callback
    def _unsub_all() -> None:
        if callable(debounce_cancel[0]):
            debounce_cancel[0]()
            debounce_cancel[0] = None
        if callable(survey_timer_cancel[0]):
            survey_timer_cancel[0]()
            survey_timer_cancel[0] = None
        pending_survey_event[0] = None
        if callable(state_unsub[0]):
            state_unsub[0]()
            state_unsub[0] = None
        for u in coord_unsubs.values():
            if callable(u):
                u()
        coord_unsubs.clear()
        for u in unsubs:
            if callable(u):
                u()
        unsubs.clear()

    connection.subscriptions[msg["id"]] = _unsub_all
    connection.send_result(msg["id"], {"subscribed": True})
    connection.send_message(websocket_api.event_message(msg["id"], initial_payload))


async def _async_handle_ws_command_impl(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    scope: Scope,
) -> None:
    """Run a Studio command on its own websocket type and answer with the Studio state."""
    if not _check_studio_rev(connection, msg):
        return
    cmd = str(msg["command"]).strip()
    body = dict(msg.get("payload") or {})
    selected = resolve_target_coordinator(hass, msg.get("subentry_id"))
    try:
        try:
            cmd_scope = command_scope(cmd)
        except UnknownStudioCommand:
            raise StudioCommandError(
                "unknown_command", f"Unsupported Studio command: {cmd}"
            ) from None
        if cmd_scope != scope:
            raise StudioCommandError(
                "wrong_scope", f"'{cmd}' is a {cmd_scope} command, not a {scope} command"
            )
        if scope == "device" and selected is None:
            raise StudioCommandError(
                "not_found", f"No Latter Device with subentry_id '{msg.get('subentry_id')}'"
            )
        extra = await _async_execute_studio_command(
            hass, selected if scope == "device" else None, cmd, body
        )
    except StudioCommandError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    except TargetNotAllowed as err:
        connection.send_error(msg["id"], "not_allowed", str(err))
        return
    except SettingsScopeError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    except Exception as err:
        _LOGGER.exception("Latter Studio command '%s' failed: %s", cmd, err)
        connection.send_error(msg["id"], "command_failed", str(err))
        return

    if cmd == "mint_camera_preview_url":
        connection.send_result(msg["id"], extra)
        return

    if selected is not None and extra.get("removed_subentry_id") == selected.subentry_id:
        selected = None
    elif selected is None and extra.get("adopted_subentry_id"):
        selected = resolve_target_coordinator(hass, str(extra["adopted_subentry_id"]))
    connection.send_result(
        msg["id"],
        {
            **build_studio_state_payload(
                hass,
                selected,
                include_catalog=False,
                include_logs=(cmd == "clear_internal_logs"),
            ),
            **extra,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/system/command",
        vol.Required("command"): str,
        vol.Optional("subentry_id"): vol.Any(str, None),
        vol.Optional("payload", default={}): dict,
        vol.Required("studio_rev"): int,
    }
)
@websocket_api.async_response
async def ws_handle_system_command(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Execute an admin-gated System command from Latter Studio."""
    await _async_handle_ws_command_impl(hass, connection, msg, "system")


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/device/command",
        vol.Required("command"): str,
        vol.Required("subentry_id"): str,
        vol.Optional("payload", default={}): dict,
        vol.Required("studio_rev"): int,
    }
)
@websocket_api.async_response
async def ws_handle_device_command(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Execute an admin-gated Device command from Latter Studio."""
    await _async_handle_ws_command_impl(hass, connection, msg, "device")


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/system/export",
        vol.Required("studio_rev"): int,
    }
)
@websocket_api.async_response
async def ws_handle_system_export(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Export the System's non-secret settings and every Device's settings as JSON."""
    if not _check_studio_rev(connection, msg):
        return
    bundle = build_backup_bundle(
        hass=hass,
        scope="system",
        coordinators=iter_coordinators(hass),
    )
    connection.send_result(msg["id"], {"bundle": bundle})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/device/export",
        vol.Required("subentry_id"): str,
        vol.Required("studio_rev"): int,
    }
)
@websocket_api.async_response
async def ws_handle_device_export(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Export one Device's non-secret settings as JSON."""
    if not _check_studio_rev(connection, msg):
        return
    coord = resolve_target_coordinator(hass, msg["subentry_id"])
    if coord is None:
        connection.send_error(
            msg["id"],
            "not_found",
            f"No Latter Device with subentry_id '{msg['subentry_id']}'",
        )
        return
    bundle = build_backup_bundle(
        hass=hass,
        scope="device",
        coordinators=iter_coordinators(hass),
        target_coordinator=coord,
    )
    connection.send_result(msg["id"], {"bundle": bundle})


async def _async_restore_bundle(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    target: LatterCoordinator | None,
) -> None:
    """Restore a backup bundle and answer with the Studio state."""
    try:
        await async_restore_backup_bundle(
            hass,
            bundle=msg["bundle"],
            coordinators=iter_coordinators(hass),
            target_coordinator=target,
        )
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(
        msg["id"],
        build_studio_state_payload(
            hass,
            resolve_target_coordinator(hass, msg.get("subentry_id")),
            include_catalog=False,
        ),
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/system/import",
        vol.Optional("subentry_id"): vol.Any(str, None),
        vol.Required("bundle"): dict,
        vol.Required("studio_rev"): int,
    }
)
@websocket_api.async_response
async def ws_handle_system_import(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Restore a System backup (System settings and every Device it names)."""
    if not _check_studio_rev(connection, msg):
        return
    if str(msg["bundle"].get("scope") or "") != "system":
        connection.send_error(
            msg["id"],
            "invalid_format",
            "This is a Device backup: choose the Device to restore it onto",
        )
        return
    await _async_restore_bundle(hass, connection, msg, None)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/device/import",
        vol.Required("subentry_id"): str,
        vol.Required("bundle"): dict,
        vol.Required("studio_rev"): int,
    }
)
@websocket_api.async_response
async def ws_handle_device_import(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Restore a Device backup onto the Device named by `subentry_id`."""
    if not _check_studio_rev(connection, msg):
        return
    if str(msg["bundle"].get("scope") or "") != "device":
        connection.send_error(
            msg["id"],
            "invalid_format",
            "This is a System backup: restore it without choosing a Device",
        )
        return
    coord = resolve_target_coordinator(hass, msg["subentry_id"])
    if coord is None:
        connection.send_error(
            msg["id"],
            "not_found",
            f"No Latter Device with subentry_id '{msg['subentry_id']}'",
        )
        return
    await _async_restore_bundle(hass, connection, msg, coord)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/device/reset",
        vol.Required("subentry_id"): str,
        vol.Optional("device_settings", default=True): bool,
        vol.Optional("latter_options", default=True): bool,
        vol.Required("studio_rev"): int,
    }
)
@websocket_api.async_response
async def ws_handle_device_reset(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Reset a Device to defaults through the same path as latter.reset_device."""
    if not _check_studio_rev(connection, msg):
        return
    coord = resolve_target_coordinator(hass, msg["subentry_id"])
    if coord is None:
        connection.send_error(
            msg["id"],
            "not_found",
            f"No Latter device with subentry_id '{msg['subentry_id']}'",
        )
        return
    try:
        await async_reset_device(
            hass,
            coord,
            device_settings=msg["device_settings"],
            latter_options=msg["latter_options"],
        )
    except ServiceValidationError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "command_failed", str(err))
        return
    log_studio_event(
        hass,
        "INFO",
        coord.device_slug,
        "Reset to defaults ("
        + ", ".join(
            part
            for part, on in (
                ("device settings", msg["device_settings"]),
                ("Latter options", msg["latter_options"]),
            )
            if on
        )
        + ")",
    )
    connection.send_result(
        msg["id"], build_studio_state_payload(hass, coord, include_catalog=False)
    )


@callback
def async_register_studio_ws_commands(hass: HomeAssistant) -> None:
    """Register all Latter Studio WebSocket API commands."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get("_studio_ws_registered") == INTEGRATION_VERSION:
        return
    domain_data["_studio_ws_registered"] = INTEGRATION_VERSION
    for handler in (
        ws_handle_get_state,
        ws_handle_subscribe,
        ws_handle_system_command,
        ws_handle_device_command,
        ws_handle_system_export,
        ws_handle_device_export,
        ws_handle_system_import,
        ws_handle_device_import,
        ws_handle_device_reset,
    ):
        websocket_api.async_register_command(hass, handler)
