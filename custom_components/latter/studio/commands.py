"""Admin-gated WebSocket API commands for Latter Studio.

The websocket type is the scope (`studio/settings.py`): `latter/system/*` commands never act on the
Studio's selected Device (a System command that acts on one Device names it in its own payload), and
`latter/device/*` commands act on the Device named by the message's required `subentry_id`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
import re
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
import voluptuous as vol

from ..areas import async_execute_area_action
from ..backup import async_restore_backup_bundle, build_backup_bundle
from ..const import (
    CONF_ACTIVITY_SOURCES,
    CONF_AREA_FUSION_CONFIG,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AREA_OFFSETS,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_GROUPS,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DOCK_APPS,
    CONF_MA_PLAYER_ENTITY,
    CONF_SECURITY_PIN,
    CONF_SECURITY_PIN_HASH,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DEFAULT_DEVICE_REMOTE_GROUP,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    STUDIO_REV,
    SUBENTRY_BLE_TAG,
    normalize_device_slug,
)
from ..coordinator import LatterCoordinator
from ..doorbell import async_execute_doorbell_intercom
from ..groups import (
    GROUP_APPEARANCE_DEVICE_KEYS,
    GROUP_BEHAVIOR_DEVICE_KEYS,
    async_apply_group_baseline_to_coordinators,
    async_reset_device,
    get_device_groups,
    seed_group_baseline_from_coordinator,
    update_group_baseline_esphome_control,
)
from ..hub import (
    async_save_and_broadcast_global_config,
    get_latter_system,
    iter_coordinators,
)
from ..identity import device_entities
from ..media import async_refresh_ma_link
from ..presence import (
    area_fusion_sensor_choices,
    get_all_areas_presence_summary,
    get_ble_fabric,
)
from ..protocol import hash_security_pin, normalize_activity_sources, normalize_dock_apps
from ..wallpapers import (
    async_refresh_wallpaper_cache,
    delete_uploaded_wallpaper,
    known_wallpaper_ids,
)
from .payload import (
    STUDIO_BULK_CONTROL_DOMAINS,
    _build_system_shared_controls,
    build_studio_state_payload,
    log_studio_event,
    resolve_target_coordinator,
)
from .settings import (
    DEVICE_ENTITY_VERBS,
    SYSTEM_ENTITY_VERBS,
    CatalogGate,
    Scope,
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
    """Validate `studio_rev` when supplied; send `studio_rev_mismatch` and return False on mismatch."""
    rev = msg.get("studio_rev")
    if rev is not None and rev != STUDIO_REV:
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
    return int(float(level)) if level is not None else None


def _optional_option(body: dict[str, Any]) -> str | None:
    option = body.get("option")
    return str(option) if option is not None else None


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


async def _cmd_set_ble_area_offset(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    area_id = str(body.get("area_id") or "").strip()
    offset_val = float(body.get("offset_db") or 0.0)
    raw_offsets = global_cfg.get(CONF_BLE_AREA_OFFSETS)
    offsets = dict(raw_offsets) if isinstance(raw_offsets, dict) else {}
    if abs(offset_val) < 0.1:
        offsets.pop(area_id, None)
    elif area_id:
        offsets[area_id] = round(max(-25.0, min(25.0, offset_val)), 1)
    await async_save_and_broadcast_global_config(
        hass, {CONF_BLE_AREA_OFFSETS: offsets}
    )


async def _cmd_set_area_fusion(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    area_id = str(body.get("area_id") or "").strip()
    if not area_id or ar.async_get(hass).async_get_area(area_id) is None:
        raise StudioCommandError("not_found", f"Unknown Area '{area_id}'")
    allowed_sensors = {
        s["entity_id"] for s in area_fusion_sensor_choices(hass, area_id)
    }
    raw_fusion = global_cfg.get(CONF_AREA_FUSION_CONFIG) or {}
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


async def _cmd_auto_calibrate_here(
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
    if not survey_id:
        raise StudioCommandError(
            "invalid_format",
            "survey_subentry_id is required: select the BLE survey device",
        )
    survey_coord = find_by_subentry_id(iter_coordinators(hass), survey_id)
    if survey_coord is None:
        raise StudioCommandError(
            "not_found", f"No Latter device with subentry_id '{survey_id}'"
        )
    if survey_coord._ble_tracker is None:
        raise StudioCommandError(
            "not_supported",
            f"{survey_coord.device_title} has no BLE tracker: enable Built-in BLE Area Tracking for it first",
        )

    rows = survey_coord._ble_tracker.get_area_calibration_telemetry()
    target_row = next(
        (r for r in rows if r["area_id"] == target_area_id), None
    )
    competing = [
        r["effective_rssi"]
        for r in rows
        if r["area_id"] != target_area_id and r["effective_rssi"] is not None
    ]
    offsets = dict(survey_coord.ble_area_offsets)
    if target_row and target_row["raw_rssi"] is not None and competing:
        best_competing_eff = max(competing)
        needed_offset = (best_competing_eff - target_row["raw_rssi"]) + 6.0
        offsets[target_area_id] = round(
            max(-25.0, min(25.0, needed_offset)), 1
        )
    elif target_row:
        offsets[target_area_id] = round(
            max(
                -25.0,
                min(25.0, float(offsets.get(target_area_id, 0.0)) + 5.0),
            ),
            1,
        )
    await async_save_and_broadcast_global_config(
        hass, {CONF_BLE_AREA_OFFSETS: offsets}
    )
    survey_coord.async_set_active_area(
        target_area_id, handoff_media=False, sync_device_registry=True
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
    for ent_id in entity_ids:
        await async_execute_area_action(
            hass,
            entity_id=ent_id,
            action=action or "toggle",
            level=level_val,
            option=opt_val,
        )
    target_grp_id = str(body.get("group_id") or "").strip()
    ckey = str(body.get("canonical_key") or "").strip()
    if not ckey and entity_ids:
        matched_ctrl = next(
            (
                c
                for c in shared_controls
                if any(t.get("entity_id") == entity_ids[0] for t in c.get("targets", []))
            ),
            None,
        )
        if matched_ctrl:
            ckey = str(matched_ctrl.get("canonical_key") or "")
    if target_grp_id and target_grp_id not in ("all", "roaming", "stationary") and ckey:
        groups = get_device_groups(hass)
        grp = next((g for g in groups if g.get("id") == target_grp_id), None)
        if grp is not None:
            saved_val: Any = opt_val
            if saved_val is None and level_val is not None:
                saved_val = level_val
            elif saved_val is None and action in ("turn_on", "turn_off"):
                saved_val = "on" if action == "turn_on" else "off"
            if saved_val is not None and update_group_baseline_esphome_control(
                grp, ckey, saved_val
            ):
                await async_save_and_broadcast_global_config(
                    hass, {CONF_DEVICE_GROUPS: groups}
                )


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
    await async_execute_area_action(
        hass,
        entity_id=entity_id,
        action=action or "toggle",
        level=_optional_level(body),
        option=_optional_option(body),
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
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    assert coordinator is not None
    source_id = str(body.get("source_id") or "").strip()
    if not source_id:
        _apply_wallpaper_config(coordinator, source="", cycle_minutes=0)
        return
    await async_refresh_wallpaper_cache(hass, coordinator.device_slug)
    known = known_wallpaper_ids(coordinator.device_slug)
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
    _apply_wallpaper_config(coordinator, source=source_id, cycle_minutes=next_cycle)


async def _cmd_toggle_wallpaper_favorite(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    assert coordinator is not None
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
        if cleaned:
            await async_refresh_wallpaper_cache(hass, coordinator.device_slug)
            known = known_wallpaper_ids(coordinator.device_slug)
            if any(sid not in known for sid in cleaned):
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
        await async_refresh_wallpaper_cache(hass, coordinator.device_slug)
        if source_id not in known_wallpaper_ids(coordinator.device_slug):
            raise StudioCommandError(
                "not_allowed", "Unknown wallpaper: pick one from this Device's gallery"
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
    coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    assert coordinator is not None
    source_id = str(body.get("source_id") or "").strip()
    deleted = await hass.async_add_executor_job(
        delete_uploaded_wallpaper,
        hass,
        coordinator.device_slug,
        source_id,
    )
    if not deleted:
        raise StudioCommandError("not_found", "That wallpaper isn't an uploaded photo")
    await async_refresh_wallpaper_cache(hass, coordinator.device_slug)
    _prune_deleted_wallpaper_from_coordinators(hass, source_id)


async def _cmd_delete_system_wallpaper(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    source_id = str(body.get("source_id") or "").strip()
    deleted = await hass.async_add_executor_job(
        delete_uploaded_wallpaper,
        hass,
        "system",
        source_id,
    )
    if not deleted:
        raise StudioCommandError("not_found", "That wallpaper isn't an uploaded photo")
    await async_refresh_wallpaper_cache(hass, "system")
    _prune_deleted_wallpaper_from_coordinators(hass, source_id)


async def _cmd_save_system_config(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    updates = clean_system_settings(dict(body.get("config") or {}))
    changed = {k: v for k, v in updates.items() if global_cfg.get(k) != v}
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
    updates = clean_device_settings(raw_cfg)

    if CONF_DEVICE_REMOTE_GROUP in updates:
        valid_groups = {DEFAULT_DEVICE_REMOTE_GROUP, "all"} | {
            f"group:{g['id']}" for g in system_settings_view(global_cfg)["remote_groups"]
        }
        if updates[CONF_DEVICE_REMOTE_GROUP] not in valid_groups:
            raise StudioCommandError(
                "not_found", "Unknown remote group: save the System settings first"
            )

    try:
        if CONF_DOCK_APPS in updates:
            updates[CONF_DOCK_APPS] = normalize_dock_apps(updates[CONF_DOCK_APPS])
        if CONF_ACTIVITY_SOURCES in updates:
            updates[CONF_ACTIVITY_SOURCES] = normalize_activity_sources(
                updates[CONF_ACTIVITY_SOURCES]
            )
    except ValueError as err:
        raise SettingsScopeError(str(err)) from None

    current = coordinator.device_data
    if (
        CONF_WALLPAPER_CYCLE_MINUTES in updates
        and updates[CONF_WALLPAPER_CYCLE_MINUTES] > 0
    ):
        await async_refresh_wallpaper_cache(hass, coordinator.device_slug)
    elif (
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
    new_grp_id = str(merged_device.get(CONF_DEVICE_GROUP) or "").strip()
    old_grp_id = str(current.get(CONF_DEVICE_GROUP) or "").strip()
    group_changed = bool(new_grp_id and new_grp_id != old_grp_id)
    if merged_device != current:
        coordinator.update_device_config(merged_device)
        await coordinator.async_apply_options()
    if group_changed and new_grp_id != "unassigned":
        groups = get_device_groups(hass)
        grp = next((g for g in groups if g.get("id") == new_grp_id), None)
        if grp is not None:
            await async_apply_group_baseline_to_coordinators(
                hass, grp, [coordinator]
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


async def _cmd_add_ble_device(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    system_entries = hass.config_entries.async_entries(DOMAIN)
    if not system_entries:
        raise StudioCommandError("not_found", "Latter System entry is not set up")
    raw_name = str(body.get("name") or "").strip()
    target_addr = str(body.get("target_address") or "").strip()
    assigned_person = str(body.get("assigned_person") or "").strip()
    target_slug = normalize_device_slug(raw_name) if raw_name else ""
    if not target_slug or not target_addr:
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
            CONF_ASSIGNED_PERSON: assigned_person,
        },
    )


async def _cmd_create_device_group(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    g_name = str(body.get("name") or "").strip()
    g_desc = str(body.get("description") or "").strip()
    if not g_name:
        raise StudioCommandError("invalid_format", "A Device Group needs a name")
    g_id = re.sub(r"[^a-z0-9]+", "_", g_name.lower()).strip("_") or "group"
    groups = get_device_groups(hass)
    if any(g.get("id") == g_id for g in groups):
        raise StudioCommandError(
            "already_configured", f"A group named '{g_name}' already exists"
        )
    groups.append(
        {
            "id": g_id,
            "name": g_name,
            "description": g_desc or f"Custom group ({g_name})",
            "device_config": {},
            "esphome_controls": {},
        }
    )
    await async_save_and_broadcast_global_config(
        hass, {CONF_DEVICE_GROUPS: groups}
    )


async def _cmd_delete_device_group(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    g_id = str(body.get("group_id") or "").strip()
    groups = get_device_groups(hass)
    groups = [g for g in groups if g.get("id") != g_id]
    await async_save_and_broadcast_global_config(
        hass, {CONF_DEVICE_GROUPS: groups}
    )


async def _cmd_sync_device_group(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    g_id = str(body.get("group_id") or "").strip()
    sub_id = str(body.get("subentry_id") or "").strip()
    groups = get_device_groups(hass)
    all_coords = iter_coordinators(hass)
    if sub_id:
        target_coord = find_by_subentry_id(all_coords, sub_id)
        if target_coord is None:
            raise StudioCommandError(
                "not_found", f"No Latter Device with subentry_id '{sub_id}'"
            )
        g_id = g_id or target_coord.device_group
        targets = [target_coord]
    else:
        targets = [c for c in all_coords if c.device_group == g_id]
    grp = next((g for g in groups if g.get("id") == g_id), None)
    if grp is None:
        raise StudioCommandError("not_found", f"Unknown Device Group '{g_id}'")
    await async_apply_group_baseline_to_coordinators(hass, grp, targets)
    log_studio_event(
        hass,
        "INFO",
        "studio",
        f"Synced {len(targets)} device(s) to group '{grp.get('name', g_id)}' baseline",
    )


async def _cmd_seed_group_baseline(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    g_id = str(body.get("group_id") or "").strip()
    source_coord = _payload_device(
        hass, body, "the Device to seed the group baseline from"
    )
    groups = get_device_groups(hass)
    grp = next((g for g in groups if g.get("id") == g_id), None)
    if grp is None:
        raise StudioCommandError("not_found", f"Unknown Device Group '{g_id}'")
    seed_group_baseline_from_coordinator(hass, grp, source_coord)
    await async_save_and_broadcast_global_config(
        hass, {CONF_DEVICE_GROUPS: groups}
    )
    log_studio_event(
        hass,
        "INFO",
        "studio",
        f"Updated '{grp.get('name', g_id)}' baseline from '{source_coord.device_slug}'",
    )


async def _cmd_set_group_device_setting(
    hass: HomeAssistant,
    _coordinator: LatterCoordinator | None,
    body: dict[str, Any],
    _global_cfg: dict[str, Any],
    _extra: dict[str, Any],
) -> None:
    g_id = str(body.get("group_id") or "all").strip()
    raw_updates = dict(body.get("config") or {})
    allowed_keys = set(GROUP_BEHAVIOR_DEVICE_KEYS) | set(GROUP_APPEARANCE_DEVICE_KEYS)
    filtered = {k: v for k, v in raw_updates.items() if k in allowed_keys}
    if not filtered:
        raise StudioCommandError(
            "invalid_format", "No supported group device settings in payload"
        )
    cleaned = clean_device_settings(filtered)
    all_coords = iter_coordinators(hass)
    if g_id == "all":
        targets = [c for c in all_coords if not c.is_ble_tag]
    elif g_id == "roaming":
        targets = [c for c in all_coords if not c.is_ble_tag and c.is_roaming_device]
    elif g_id == "stationary":
        targets = [
            c for c in all_coords if not c.is_ble_tag and not c.is_roaming_device
        ]
    else:
        targets = [
            c for c in all_coords if not c.is_ble_tag and c.device_group == g_id
        ]
    for c in targets:
        merged = {**c.device_data, **cleaned}
        if merged != c.device_data:
            c.update_device_config(merged)
            await c.async_apply_options()
            c._bind_wallpaper_cycle_timer()
            c.async_notify_listeners()
    if g_id not in ("all", "roaming", "stationary"):
        groups = get_device_groups(hass)
        grp = next((g for g in groups if g.get("id") == g_id), None)
        if grp is not None:
            behavior_updates = {
                k: v for k, v in cleaned.items() if k in GROUP_BEHAVIOR_DEVICE_KEYS
            }
            if behavior_updates:
                dev_cfg = dict(grp.get("device_config") or {})
                dev_cfg.update(behavior_updates)
                grp["device_config"] = dev_cfg
                await async_save_and_broadcast_global_config(
                    hass, {CONF_DEVICE_GROUPS: groups}
                )


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
                pin_hash = hash_security_pin(raw_pin)
            except ValueError as err:
                raise StudioCommandError("invalid_format", str(err)) from err
            log_msg = f"Updated security PIN for '{target_coord.device_slug}'"
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
        await async_save_and_broadcast_global_config(
            hass, {CONF_SECURITY_PIN_HASH: ""}
        )
        log_studio_event(hass, "INFO", "system", "Cleared System security PIN")
    else:
        raw_pin = str(body.get("pin") or "").strip()
        try:
            pin_hash = hash_security_pin(raw_pin)
        except ValueError as err:
            raise StudioCommandError("invalid_format", str(err)) from err
        await async_save_and_broadcast_global_config(
            hass, {CONF_SECURITY_PIN_HASH: pin_hash}
        )
        log_studio_event(hass, "INFO", "system", "Updated System security PIN")


_CommandHandler = Callable[
    [HomeAssistant, LatterCoordinator | None, dict[str, Any], dict[str, Any], dict[str, Any]],
    Awaitable[None],
]

_STUDIO_COMMAND_HANDLERS: dict[str, _CommandHandler] = {
    "set_ble_area_offset": _cmd_set_ble_area_offset,
    "set_area_fusion": _cmd_set_area_fusion,
    "auto_calibrate_here": _cmd_auto_calibrate_here,
    "system_entity_action": _cmd_system_entity_action,
    "esphome_entity_action": _cmd_esphome_entity_action,
    "test_doorbell_speaker": _cmd_test_doorbell_speaker,
    "send_announcement": _cmd_send_announcement,
    "check_system_updates": _cmd_check_system_updates,
    "select_wallpaper": _cmd_select_wallpaper,
    "toggle_wallpaper_favorite": _cmd_toggle_wallpaper_favorite,
    "delete_wallpaper": _cmd_delete_wallpaper,
    "delete_system_wallpaper": _cmd_delete_system_wallpaper,
    "save_system_config": _cmd_save_system_config,
    "save_device_config": _cmd_save_device_config,
    "clear_internal_logs": _cmd_clear_internal_logs,
    "remove_device": _cmd_remove_device,
    "add_ble_device": _cmd_add_ble_device,
    "create_device_group": _cmd_create_device_group,
    "delete_device_group": _cmd_delete_device_group,
    "sync_device_group": _cmd_sync_device_group,
    "seed_group_baseline": _cmd_seed_group_baseline,
    "set_group_device_setting": _cmd_set_group_device_setting,
    "rotate_signing_key": _cmd_rotate_signing_key,
    "set_security_pin": _cmd_set_security_pin,
}


async def _async_execute_studio_command(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    cmd: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Execute a Studio command via `_STUDIO_COMMAND_HANDLERS` and return extra response fields."""
    handler = _STUDIO_COMMAND_HANDLERS.get(cmd)
    if handler is None:
        raise StudioCommandError("unknown_command", f"Unsupported Studio command: {cmd}")
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
        vol.Optional("studio_rev"): vol.Any(int, None),
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
    if coord is not None:
        await async_refresh_wallpaper_cache(hass, coord.device_slug)
    await async_refresh_wallpaper_cache(hass, "system")
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
        vol.Optional("studio_rev"): vol.Any(int, None),
    }
)
@websocket_api.async_response
async def ws_handle_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to live Latter Studio state and BLE survey updates."""
    if not _check_studio_rev(connection, msg):
        return
    sub_id = msg.get("subentry_id")
    survey_sub_id = str(msg.get("survey_subentry_id") or "").strip()
    include_logs = bool(msg.get("include_logs", False))
    unsubs: list[Any] = []
    debounce_cancel: list[Any] = [None]
    catalog_gate = CatalogGate()

    @callback
    def _push_now(_now: Any = None) -> None:
        debounce_cancel[0] = None
        coord = resolve_target_coordinator(hass, sub_id)
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                build_studio_state_payload(
                    hass,
                    coord,
                    include_catalog=catalog_gate.take(),
                    include_logs=include_logs,
                ),
            )
        )

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
        for cid in list(coord_unsubs):
            if cid not in current_ids:
                u = coord_unsubs.pop(cid)
                if callable(u):
                    u()
        for c in current:
            cid = id(c)
            if cid not in coord_unsubs:
                coord_unsubs[cid] = c.async_add_listener(_schedule_push)

    _track_coordinators()

    ble_fabric = get_ble_fabric(hass)
    unsubs.append(ble_fabric.register_occupancy_listener(_schedule_push))

    @callback
    def _on_survey_delta(delta: dict[str, Any]) -> None:
        target_id = survey_sub_id or str(sub_id or "")
        coords = iter_coordinators(hass)
        target_coord = find_by_subentry_id(coords, target_id) if target_id else None
        if target_coord is None:
            slug = str(delta.get("device_slug") or "")
            target_coord = next((c for c in coords if c.device_slug == slug), None)
        if target_coord is None or target_coord._ble_tracker is None:
            return
        if survey_sub_id and target_coord.subentry_id != survey_sub_id:
            return
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                {
                    "type": "ble_survey_delta",
                    "subentry_id": target_coord.subentry_id,
                    "ble_packets_seen": target_coord._ble_tracker.packets_seen,
                    "ble_closest_proxy": target_coord._ble_tracker.closest_scanner,
                    "ble_survey_rows": target_coord._ble_tracker.get_area_calibration_telemetry(),
                    "area_presence_grid": get_all_areas_presence_summary(hass),
                },
            )
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
    coord = resolve_target_coordinator(hass, sub_id)
    if coord is not None:
        await async_refresh_wallpaper_cache(hass, coord.device_slug)
    await async_refresh_wallpaper_cache(hass, "system")
    connection.send_result(
        msg["id"],
        build_studio_state_payload(hass, coord, include_logs=include_logs),
    )


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

    if selected is not None and extra.get("removed_subentry_id") == selected.subentry_id:
        selected = None
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
        vol.Optional("studio_rev"): vol.Any(int, None),
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
        vol.Optional("studio_rev"): vol.Any(int, None),
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
        vol.Optional("studio_rev"): vol.Any(int, None),
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
        vol.Optional("studio_rev"): vol.Any(int, None),
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
            restore_esphome_entities=bool(msg.get("restore_esphome_entities", True)),
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
        vol.Optional("restore_esphome_entities", default=True): bool,
        vol.Optional("studio_rev"): vol.Any(int, None),
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
        vol.Optional("restore_esphome_entities", default=True): bool,
        vol.Optional("studio_rev"): vol.Any(int, None),
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
        vol.Optional("studio_rev"): vol.Any(int, None),
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
