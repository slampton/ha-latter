"""Admin-gated WebSocket API commands for Latter Studio.

The websocket type is the scope (`studio/scope.py`): `latter/system/*` commands never act on the
Studio's selected Device (a System command that acts on one Device names it in its own payload), and
`latter/device/*` commands act on the Device named by the message's required `subentry_id`.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_call_later

from ..area_engine import async_execute_area_action
from ..backup_engine import (
    async_apply_profile_to_coordinators,
    async_restore_backup_bundle,
    build_backup_bundle,
    capture_profile_from_coordinator,
    get_device_groups_and_profiles,
)
from ..ble_engine import get_ble_fabric
from ..const import (
    CONF_AREA_FUSION_CONFIG,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AREA_OFFSETS,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEVICE_GROUPS,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_MA_PLAYER_ENTITY,
    CONF_SAVED_PROFILES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DEFAULT_DEVICE_REMOTE_GROUP,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    SUBENTRY_BLE_TAG,
    normalize_device_slug,
)
from ..coordinator import LatterCoordinator
from ..device_reset import async_reset_device
from ..doorbell_engine import async_execute_doorbell_intercom
from ..identity import device_entities
from ..media_engine import async_refresh_ma_link
from ..wallpaper_engine import (
    async_refresh_wallpaper_cache,
    delete_uploaded_wallpaper,
    known_wallpaper_ids,
    save_uploaded_wallpaper,
)
from .payload import (
    _build_system_shared_controls,
    _get_all_coordinators,
    async_save_and_broadcast_global_config,
    build_studio_state_payload,
    log_studio_event,
    resolve_target_coordinator,
)
from .scope import (
    DEVICE_ENTITY_VERBS,
    SYSTEM_ENTITY_VERBS,
    Scope,
    TargetNotAllowed,
    UnknownStudioCommand,
    allowed_entity_targets,
    checked_entity_verb,
    command_scope,
    find_by_subentry_id,
)
from .settings import (
    SettingsScopeError,
    clean_device_settings,
    clean_system_settings,
    system_settings_view,
)

_LOGGER = logging.getLogger(__name__)

STUDIO_REV = 3


class StudioCommandError(Exception):
    """A Studio command rejected its input; sent to the panel as a websocket error with `code`."""

    def __init__(self, code: str, message: str) -> None:
        """Store the websocket error code alongside the message."""
        super().__init__(message)
        self.code = code


def _payload_device(hass: HomeAssistant, body: dict[str, Any], purpose: str) -> LatterCoordinator:
    """Return the Device a System command names in its payload (`subentry_id`), else fail."""
    coord = find_by_subentry_id(_get_all_coordinators(hass), str(body.get("subentry_id") or ""))
    if coord is None:
        raise StudioCommandError("not_found", f"Choose {purpose}")
    return coord


def _optional_level(body: dict[str, Any]) -> int | None:
    level = body.get("level")
    return int(float(level)) if level is not None else None


def _optional_option(body: dict[str, Any]) -> str | None:
    option = body.get("option")
    return str(option) if option is not None else None


async def _async_execute_studio_command(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    cmd: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    """Execute a Studio command and return extra response fields.

    `coordinator` is the Device of a Device command and None for System commands.
    """
    extra: dict[str, Any] = {}
    global_cfg: dict[str, Any] = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}

    if cmd == "set_ble_area_offset":
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

    elif cmd == "set_area_fusion_mode":
        area_id = str(body.get("area_id") or "").strip()
        mode_val = str(body.get("mode") or "weighted").strip().lower()
        if mode_val not in ("weighted", "any_or", "ble_only", "ble_and_sensor"):
            mode_val = "weighted"
        if area_id:
            raw_fusion = global_cfg.get(CONF_AREA_FUSION_CONFIG) or {}
            fusion_cfg = (
                dict(raw_fusion) if isinstance(raw_fusion, dict) else {}
            )
            cur_area_cfg = (
                dict(fusion_cfg.get(area_id) or {})
                if isinstance(fusion_cfg.get(area_id), dict)
                else {}
            )
            cur_area_cfg["mode"] = mode_val
            if "threshold_pct" in body and body["threshold_pct"] is not None:
                cur_area_cfg["threshold_pct"] = max(
                    20, min(95, int(body["threshold_pct"]))
                )
            if "sensors" in body and isinstance(body["sensors"], list):
                cur_area_cfg["sensors"] = [
                    str(s).strip()
                    for s in body["sensors"]
                    if str(s or "").strip()
                ]
            fusion_cfg[area_id] = cur_area_cfg
            await async_save_and_broadcast_global_config(
                hass, {CONF_AREA_FUSION_CONFIG: fusion_cfg}
            )
            get_ble_fabric(hass).notify_occupancy_listeners()

    elif cmd == "auto_calibrate_here":
        target_area_id = str(body.get("area_id") or "").strip()
        survey_id = str(body.get("survey_subentry_id") or "").strip()
        if not target_area_id:
            raise StudioCommandError("invalid_format", "area_id is required")
        if not survey_id:
            raise StudioCommandError(
                "invalid_format",
                "survey_subentry_id is required: select the BLE survey device",
            )
        survey_coord = next(
            (c for c in _get_all_coordinators(hass) if c.subentry_id == survey_id),
            None,
        )
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
            if r["area_id"] != target_area_id
            and r["effective_rssi"] is not None
        ]
        offsets = dict(survey_coord.ble_area_offsets)
        if target_row and target_row["raw_rssi"] is not None and competing:
            best_competing_eff = max(competing)
            needed_offset = (
                best_competing_eff - target_row["raw_rssi"]
            ) + 6.0
            offsets[target_area_id] = round(
                max(-25.0, min(25.0, needed_offset)), 1
            )
        elif target_row:
            offsets[target_area_id] = round(
                max(
                    -25.0,
                    min(
                        25.0,
                        float(offsets.get(target_area_id, 0.0)) + 5.0,
                    ),
                ),
                1,
            )
        await async_save_and_broadcast_global_config(
            hass, {CONF_BLE_AREA_OFFSETS: offsets}
        )
        survey_coord.async_set_active_area(
            target_area_id, handoff_media=False, sync_device_registry=True
        )

    elif cmd == "system_entity_action":
        allowed = {
            str(target["entity_id"])
            for ctrl in _build_system_shared_controls(hass)
            for target in ctrl["targets"]
            if target.get("entity_id")
        }
        entity_ids = allowed_entity_targets(
            body.get("entity_ids") or [], allowed, "a shared control of a Latter Device"
        )
        action = checked_entity_verb(body, SYSTEM_ENTITY_VERBS)
        for ent_id in entity_ids:
            await async_execute_area_action(
                hass,
                entity_id=ent_id,
                action=action or "toggle",
                level=_optional_level(body),
                option=_optional_option(body),
            )

    elif cmd == "esphome_entity_action":
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

    elif cmd == "test_doorbell_speaker":
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

    elif cmd == "send_test_notification":
        title = str(body.get("title") or "").strip()
        message = str(body.get("message") or "").strip()
        priority = str(body.get("priority") or "normal").strip()
        target_slug = str(body.get("target_device") or "").strip()
        if not target_slug:
            raise StudioCommandError(
                "invalid_format", "target_device is required (a Device or 'all')"
            )
        if not title or not message:
            raise StudioCommandError("invalid_format", "A test notification needs a title and a message")
        cam_ent = ""
        if bool(body.get("include_camera", False)):
            cameras = system_settings_view(global_cfg)["camera_entities"]
            if not cameras:
                raise StudioCommandError(
                    "invalid_format",
                    "Add a camera in Shared Entities first, or turn off the camera snapshot",
                )
            cam_ent = cameras[0]
        await hass.services.async_call(
            DOMAIN,
            "notify",
            {
                "target_device": target_slug,
                "title": title,
                "message": message,
                "priority": priority,
                "chime": True,
                **({"camera_entity": cam_ent} if cam_ent else {}),
            },
            blocking=True,
        )

    elif cmd == "check_system_updates":
        update_ids = [
            e.entity_id
            for c in _get_all_coordinators(hass)
            for e in device_entities(hass, c.esphome_device_id, domain="update")
        ]
        if update_ids and hass.services.has_service("homeassistant", "update_entity"):
            await hass.services.async_call(
                "homeassistant",
                "update_entity",
                {"entity_id": update_ids},
                blocking=False,
            )

    elif cmd == "upload_wallpaper":
        filename = str(body.get("filename") or "wallpaper.jpg")
        data_b64 = str(body.get("data_b64") or "")
        if not data_b64:
            raise StudioCommandError("invalid_format", "No image data in the upload")
        new_source = await hass.async_add_executor_job(
            save_uploaded_wallpaper,
            hass,
            coordinator.device_slug,
            filename,
            data_b64,
        )
        favs = list(coordinator.wallpaper_favorites)
        if new_source not in favs:
            favs.append(new_source)
        merged_wp: dict[str, Any] = {
            **coordinator.device_data,
            CONF_WALLPAPER_SOURCE: new_source,
            CONF_WALLPAPER_FAVORITES: favs,
        }
        coordinator.current_wallpaper = new_source
        coordinator._configured_wallpaper_source = new_source
        coordinator._schedule_persist_runtime_state()
        coordinator.update_device_config(merged_wp)
        coordinator.async_notify_listeners()

    elif cmd == "select_wallpaper":
        source_id = str(body.get("source_id") or "").strip()
        if source_id:
            await async_refresh_wallpaper_cache(hass, coordinator.device_slug)
            if source_id not in known_wallpaper_ids(coordinator.device_slug):
                raise StudioCommandError(
                    "not_allowed", "Unknown wallpaper: pick one from this Device's gallery"
                )
        merged_sel: dict[str, Any] = {
            **coordinator.device_data,
            CONF_WALLPAPER_SOURCE: source_id,
        }
        coordinator.current_wallpaper = source_id
        coordinator._configured_wallpaper_source = source_id
        coordinator._schedule_persist_runtime_state()
        coordinator.update_device_config(merged_sel)
        coordinator.async_notify_listeners()

    elif cmd == "toggle_wallpaper_favorite":
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
        merged_fav: dict[str, Any] = {
            **coordinator.device_data,
            CONF_WALLPAPER_FAVORITES: favs,
        }
        coordinator.update_device_config(merged_fav)
        coordinator._bind_wallpaper_cycle_timer()
        coordinator.async_notify_listeners()

    elif cmd == "delete_wallpaper":
        source_id = str(body.get("source_id") or "").strip()
        deleted = await hass.async_add_executor_job(
            delete_uploaded_wallpaper,
            hass,
            coordinator.device_slug,
            source_id,
        )
        if not deleted:
            raise StudioCommandError(
                "not_found", "That wallpaper isn't one of this Device's uploads"
            )
        favs = [f for f in coordinator.wallpaper_favorites if f != source_id]
        new_active = (
            ""
            if coordinator.wallpaper_source == source_id
            else coordinator.wallpaper_source
        )
        merged_del: dict[str, Any] = {
            **coordinator.device_data,
            CONF_WALLPAPER_SOURCE: new_active,
            CONF_WALLPAPER_FAVORITES: favs,
        }
        coordinator.current_wallpaper = new_active
        coordinator._configured_wallpaper_source = new_active
        coordinator._schedule_persist_runtime_state()
        coordinator.update_device_config(merged_del)
        coordinator.async_notify_listeners()

    elif cmd == "save_system_config":
        updates = clean_system_settings(dict(body.get("config") or {}))
        changed = {k: v for k, v in updates.items() if global_cfg.get(k) != v}
        if changed:
            await async_save_and_broadcast_global_config(hass, changed)
        log_studio_event(hass, "INFO", "studio", "Saved System settings")

    elif cmd == "save_device_config":
        updates = clean_device_settings(dict(body.get("config") or {}))
        current = coordinator.device_data
        merged_device: dict[str, Any] = {**current, **updates}
        for gk in GLOBAL_CONFIG_KEYS:
            merged_device.pop(gk, None)
        ma_link_changed = merged_device.get(CONF_MA_PLAYER_ENTITY, "") != current.get(
            CONF_MA_PLAYER_ENTITY, ""
        )
        if merged_device != current:
            coordinator.update_device_config(merged_device)
            await coordinator.async_apply_options()
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

    elif cmd == "clear_internal_logs":
        hass.data.setdefault(DOMAIN, {})["internal_logs"] = []
        log_studio_event(
            hass, "INFO", "studio", "Cleared internal diagnostic log"
        )

    elif cmd == "remove_device":
        target_coord = find_by_subentry_id(
            _get_all_coordinators(hass), str(body.get("subentry_id") or "")
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

    elif cmd == "add_ble_device":
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
        if any(c.device_slug == target_slug for c in _get_all_coordinators(hass)):
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

    elif cmd == "set_device_remote_group":
        rg_coord = _payload_device(hass, body, "a Device")
        rem_grp = str(body.get("device_remote_group") or DEFAULT_DEVICE_REMOTE_GROUP).strip()
        valid_groups = {DEFAULT_DEVICE_REMOTE_GROUP, "all"} | {
            f"group:{g['id']}" for g in system_settings_view(global_cfg)["remote_groups"]
        }
        if rem_grp not in valid_groups:
            raise StudioCommandError(
                "not_found", "Unknown remote group: save the System settings first"
            )
        merged_rg: dict[str, Any] = {
            **rg_coord.device_data,
            CONF_DEVICE_REMOTE_GROUP: rem_grp,
        }
        rg_coord.update_device_config(merged_rg)
        rg_coord.async_notify_listeners()

    elif cmd == "create_device_group":
        g_name = str(body.get("name") or "").strip()
        g_desc = str(body.get("description") or "").strip()
        if not g_name:
            raise StudioCommandError("invalid_format", "A Device group needs a name")
        g_id = re.sub(r"[^a-z0-9]+", "_", g_name.lower()).strip("_") or "group"
        groups, _ = get_device_groups_and_profiles(hass)
        if any(g.get("id") == g_id for g in groups):
            raise StudioCommandError("already_configured", f"A group named '{g_name}' already exists")
        groups.append(
            {
                "id": g_id,
                "name": g_name,
                "description": g_desc or f"Custom group ({g_name})",
            }
        )
        await async_save_and_broadcast_global_config(
            hass, {CONF_DEVICE_GROUPS: groups}
        )

    elif cmd == "delete_device_group":
        g_id = str(body.get("group_id") or "").strip()
        groups, _ = get_device_groups_and_profiles(hass)
        groups = [g for g in groups if g.get("id") != g_id]
        await async_save_and_broadcast_global_config(
            hass, {CONF_DEVICE_GROUPS: groups}
        )

    elif cmd == "capture_profile":
        source_coord = _payload_device(hass, body, "the Device to capture from")
        p_name = str(body.get("name") or "").strip()
        p_desc = str(body.get("description") or "").strip()
        _, profiles = get_device_groups_and_profiles(hass)
        new_prof = capture_profile_from_coordinator(
            hass, source_coord, name=p_name, description=p_desc
        )
        profiles = [p for p in profiles if p.get("name") != new_prof["name"]]
        profiles.insert(0, new_prof)
        await async_save_and_broadcast_global_config(
            hass, {CONF_SAVED_PROFILES: profiles[:30]}
        )

    elif cmd == "delete_profile":
        p_id = str(body.get("profile_id") or "").strip()
        _, profiles = get_device_groups_and_profiles(hass)
        profiles = [p for p in profiles if p.get("id") != p_id]
        await async_save_and_broadcast_global_config(
            hass, {CONF_SAVED_PROFILES: profiles}
        )

    elif cmd == "apply_profile":
        p_id = str(body.get("profile_id") or "").strip()
        target_scope = str(body.get("target_scope") or "").strip()
        _, profiles = get_device_groups_and_profiles(hass)
        prof = next((p for p in profiles if p.get("id") == p_id), None)
        if prof is None:
            raise StudioCommandError("not_found", f"Unknown profile '{p_id}'")
        all_coords = _get_all_coordinators(hass)
        if target_scope == "all":
            targets = all_coords
        elif target_scope.startswith("group:"):
            grp_id = target_scope.split(":", 1)[1]
            targets = [c for c in all_coords if c.device_group == grp_id]
        elif target_scope.startswith("device:"):
            d_coord = find_by_subentry_id(all_coords, target_scope.split(":", 1)[1])
            if d_coord is None:
                raise StudioCommandError(
                    "not_found", f"Unknown Device in target scope '{target_scope}'"
                )
            targets = [d_coord]
        else:
            raise StudioCommandError(
                "invalid_format", f"Unknown target scope '{target_scope}'"
            )
        await async_apply_profile_to_coordinators(hass, prof, targets)

    else:
        raise StudioCommandError("unknown_command", f"Unsupported Studio command: {cmd}")

    return extra


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/system/get_state",
        vol.Optional("subentry_id"): vol.Any(str, None),
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
    if msg.get("studio_rev") != STUDIO_REV:
        _LOGGER.debug(
            "Ignoring get_state from a stale cached Studio client (studio_rev != %s)", STUDIO_REV
        )
        connection.send_result(msg["id"], None)
        return
    coord = resolve_target_coordinator(hass, msg.get("subentry_id"))
    if coord is not None:
        await async_refresh_wallpaper_cache(hass, coord.device_slug)
    connection.send_result(
        msg["id"],
        build_studio_state_payload(hass, coord),
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/system/subscribe",
        vol.Optional("subentry_id"): vol.Any(str, None),
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
    if msg.get("studio_rev") != STUDIO_REV:
        _LOGGER.debug(
            "Ignoring subscribe from a stale cached Studio client (studio_rev != %s)", STUDIO_REV
        )
        connection.send_result(msg["id"], None)
        return
    sub_id = msg.get("subentry_id")
    unsubs: list[Any] = []
    debounce_cancel: list[Any] = [None]

    @callback
    def _push_now(_now: Any = None) -> None:
        debounce_cancel[0] = None
        coord = resolve_target_coordinator(hass, sub_id)
        connection.send_message(
            websocket_api.event_message(
                msg["id"],
                build_studio_state_payload(hass, coord),
            )
        )

    @callback
    def _schedule_push() -> None:
        if debounce_cancel[0] is not None:
            return
        debounce_cancel[0] = async_call_later(hass, 0.4, _push_now)

    for c in _get_all_coordinators(hass):
        unsubs.append(c.async_add_listener(_schedule_push))

    ble_fabric = get_ble_fabric(hass)
    unsubs.append(ble_fabric.register_occupancy_listener(_schedule_push))

    @callback
    def _unsub_all() -> None:
        if callable(debounce_cancel[0]):
            debounce_cancel[0]()
            debounce_cancel[0] = None
        for u in unsubs:
            if callable(u):
                u()
        unsubs.clear()

    connection.subscriptions[msg["id"]] = _unsub_all
    coord = resolve_target_coordinator(hass, sub_id)
    if coord is not None:
        await async_refresh_wallpaper_cache(hass, coord.device_slug)
    connection.send_result(
        msg["id"],
        build_studio_state_payload(hass, coord),
    )


async def _async_handle_ws_command_impl(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    scope: Scope,
) -> None:
    """Run a Studio command on its own websocket type and answer with the Studio state.

    The state in the answer is built for the Studio's selected Device (`subentry_id`), so the page
    keeps its Device; a System command never acts on that Device.
    """
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
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Latter Studio command '%s' failed: %s", cmd, err)
        connection.send_error(msg["id"], "command_failed", str(err))
        return

    if selected is not None and extra.get("removed_subentry_id") == selected.subentry_id:
        selected = None
    connection.send_result(
        msg["id"],
        {
            **build_studio_state_payload(hass, selected),
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
    }
)
@websocket_api.async_response
async def ws_handle_system_export(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Export the System's non-secret settings and every Device's settings as JSON."""
    bundle = build_backup_bundle(
        hass=hass,
        scope="system",
        coordinators=_get_all_coordinators(hass),
    )
    connection.send_result(msg["id"], {"bundle": bundle})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/device/export",
        vol.Required("subentry_id"): str,
    }
)
@websocket_api.async_response
async def ws_handle_device_export(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Export one Device's non-secret settings as JSON."""
    coord = resolve_target_coordinator(hass, msg["subentry_id"])
    if coord is None:
        connection.send_error(
            msg["id"], "not_found", f"No Latter Device with subentry_id '{msg['subentry_id']}'"
        )
        return
    bundle = build_backup_bundle(
        hass=hass,
        scope="device",
        coordinators=_get_all_coordinators(hass),
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
            coordinators=_get_all_coordinators(hass),
            target_coordinator=target,
            restore_esphome_entities=bool(msg.get("restore_esphome_entities", True)),
        )
    except ValueError as err:
        connection.send_error(msg["id"], "invalid_format", str(err))
        return
    connection.send_result(
        msg["id"],
        build_studio_state_payload(
            hass, resolve_target_coordinator(hass, msg.get("subentry_id"))
        ),
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/system/import",
        vol.Optional("subentry_id"): vol.Any(str, None),
        vol.Required("bundle"): dict,
        vol.Optional("restore_esphome_entities", default=True): bool,
    }
)
@websocket_api.async_response
async def ws_handle_system_import(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Restore a System backup (System settings and every Device it names)."""
    if str(msg["bundle"].get("scope") or "") != "system":
        connection.send_error(
            msg["id"], "invalid_format", "This is a Device backup: choose the Device to restore it onto"
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
    }
)
@websocket_api.async_response
async def ws_handle_device_import(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Restore a Device backup onto the Device named by `subentry_id` (it may be a different Device)."""
    if str(msg["bundle"].get("scope") or "") != "device":
        connection.send_error(
            msg["id"], "invalid_format", "This is a System backup: restore it without choosing a Device"
        )
        return
    coord = resolve_target_coordinator(hass, msg["subentry_id"])
    if coord is None:
        connection.send_error(
            msg["id"], "not_found", f"No Latter Device with subentry_id '{msg['subentry_id']}'"
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
    }
)
@websocket_api.async_response
async def ws_handle_device_reset(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Reset a Device to defaults (device settings and/or Latter options) through the same path as latter.reset_device."""
    coord = resolve_target_coordinator(hass, msg["subentry_id"])
    if coord is None:
        connection.send_error(
            msg["id"], "not_found", f"No Latter device with subentry_id '{msg['subentry_id']}'"
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
    connection.send_result(msg["id"], build_studio_state_payload(hass, coord))


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
