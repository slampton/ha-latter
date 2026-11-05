"""Admin-gated WebSocket API commands for Latter Studio."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
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
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_FUSION_CONFIG,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AREA_OFFSETS,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_CAMERA_ENTITIES,
    CONF_CAMERA_ENTITY,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_GROUPS,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DISPLAY_SHAPE,
    CONF_DOCK_APPS,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PRESENCE_ENTITY,
    CONF_REMOTES_LIST,
    CONF_SAVED_PROFILES,
    CONF_SITE_ID,
    CONF_SYNC_DEVICE_AREA,
    CONF_VOLUME_OVERRIDES,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DEFAULT_ART_SIZE,
    DEFAULT_PAGE_SIZE,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    SUBENTRY_BLE_TAG,
    normalize_device_slug,
)
from ..coordinator import LatterCoordinator
from ..doorbell_engine import async_execute_doorbell_intercom
from ..wallpaper_engine import (
    async_refresh_wallpaper_cache,
    delete_uploaded_wallpaper,
    save_uploaded_wallpaper,
)
from ..identity import device_entities
from .payload import (
    _get_all_coordinators,
    async_save_and_broadcast_global_config,
    build_studio_state_payload,
    log_studio_event,
    resolve_target_coordinator,
)
from .scope import UnknownStudioCommand, command_requires_device, find_by_subentry_id

_LOGGER = logging.getLogger(__name__)


class StudioCommandError(Exception):
    """A Studio command rejected its input; sent to the panel as a websocket error with `code`."""

    def __init__(self, code: str, message: str) -> None:
        """Store the websocket error code alongside the message."""
        super().__init__(message)
        self.code = code


async def _async_execute_studio_command(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    cmd: str,
    body: dict[str, Any],
) -> tuple[LatterCoordinator | None, dict[str, Any]]:
    """Execute a Studio command and return `(updated_coordinator, extra_response_fields)`."""
    extra: dict[str, Any] = {}
    try:
        needs_device = command_requires_device(cmd, body)
    except UnknownStudioCommand:
        raise StudioCommandError(
            "unknown_command", f"Unsupported Studio command: {cmd}"
        ) from None
    if needs_device and coordinator is None:
        raise StudioCommandError(
            "device_required", f"'{cmd}' needs a Device: select one in Studio first"
        )
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
        entity_ids = body.get("entity_ids") or []
        action = str(body.get("action") or "toggle").strip()
        level = body.get("level")
        option = body.get("option")
        if isinstance(entity_ids, list):
            for ent_id in entity_ids:
                if isinstance(ent_id, str) and ent_id.strip():
                    await async_execute_area_action(
                        hass,
                        entity_id=ent_id.strip(),
                        action=action,
                        level=int(float(level)) if level is not None else None,
                        option=str(option) if option is not None else None,
                    )

    elif cmd == "esphome_entity_action":
        entity_id = str(body.get("entity_id") or "").strip()
        action = str(body.get("action") or "toggle").strip()
        level = body.get("level")
        option = body.get("option")
        if entity_id:
            await async_execute_area_action(
                hass,
                entity_id=entity_id,
                action=action,
                level=int(float(level)) if level is not None else None,
                option=str(option) if option is not None else None,
            )

    elif cmd == "test_doorbell_speaker":
        cam_ent = str(
            body.get("camera_entity") or coordinator.camera_entity or ""
        ).strip()
        msg = str(
            body.get("message")
            or "Hello! Please leave the package by the front door."
        ).strip()
        await async_execute_doorbell_intercom(
            hass,
            coordinator,
            action="talk_message",
            camera_entity=cam_ent,
            message=msg,
        )

    elif cmd == "send_test_notification":
        title = str(body.get("title") or "Doorbell Alert").strip()
        message = str(
            body.get("message") or "Motion detected at Front Door"
        ).strip()
        priority = str(body.get("priority") or "normal").strip()
        inc_cam = bool(body.get("include_camera", False))
        target_slug = str(body.get("target_device") or "").strip()
        if not target_slug:
            raise StudioCommandError(
                "invalid_format", "target_device is required (a Device or 'all')"
            )
        cam_ent = coordinator.camera_entity if inc_cam and coordinator else None
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
        if data_b64:
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
        elif source_id:
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
        if source_id:
            await hass.async_add_executor_job(
                delete_uploaded_wallpaper,
                hass,
                coordinator.device_slug,
                source_id,
            )
            favs = [
                f for f in coordinator.wallpaper_favorites if f != source_id
            ]
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

    elif cmd == "save_config":
        incoming_cfg = dict(body.get("config") or {})
        merged_device: dict[str, Any] = dict(coordinator.device_data)
        global_updates: dict[str, Any] = {}

        if "camera_entities" in incoming_cfg and isinstance(
            incoming_cfg["camera_entities"], list
        ):
            clean_cams = [
                str(x).strip()
                for x in incoming_cfg["camera_entities"][:10]
                if str(x or "").strip()
            ]
            incoming_cfg[CONF_CAMERA_ENTITIES] = clean_cams
            incoming_cfg[CONF_CAMERA_ENTITY] = (
                clean_cams[0] if clean_cams else ""
            )

        if "remotes_list" in incoming_cfg and isinstance(
            incoming_cfg["remotes_list"], list
        ):
            incoming_cfg[CONF_REMOTES_LIST] = [
                str(x).strip()
                for x in incoming_cfg["remotes_list"][:10]
                if str(x or "").strip()
            ]

        if "volume_overrides" in incoming_cfg and isinstance(
            incoming_cfg["volume_overrides"], list
        ):
            incoming_cfg[CONF_VOLUME_OVERRIDES] = [
                {
                    "speaker": str(x.get("speaker") or "").strip(),
                    "target": str(x.get("target") or "").strip(),
                }
                for x in incoming_cfg["volume_overrides"][:10]
                if isinstance(x, dict)
                and str(x.get("speaker") or "").strip()
                and str(x.get("target") or "").strip()
            ]

        device_keys = (
                    CONF_DEVICE_GROUP,
            CONF_DEVICE_REMOTE_GROUP,
            CONF_DISPLAY_SHAPE,
            CONF_DEFAULT_PAGE_SIZE,
            CONF_DEFAULT_SPEAKER,
            CONF_DEFAULT_AREA,
            CONF_NATIVE_BLE_TRACKING,
            CONF_BLE_BEACON_UUID,
            CONF_BLE_TARGET_ADDRESS,
            CONF_PRESENCE_ENTITY,
            CONF_ASSIGNED_PERSON,
            CONF_BLE_AUTO_SWITCH,
            CONF_SYNC_DEVICE_AREA,
            CONF_AREA_FOLLOW_DWELL_S,
            CONF_AREA_HANDOFF,
            CONF_DOCK_APPS,
            CONF_WALLPAPER_SOURCE,
            CONF_WALLPAPER_CYCLE_MINUTES,
            CONF_ART_SIZE,
            CONF_DEVICE_CUSTOM_COLOR,
            CONF_SITE_ID,
        )

        for k in device_keys:
            if k in incoming_cfg:
                val = incoming_cfg[k]
                if k == CONF_ART_SIZE:
                    s_val = str(val or DEFAULT_ART_SIZE).strip().lower()
                    val = (
                        s_val
                        if "x" in s_val
                        else int(s_val or DEFAULT_ART_SIZE)
                    )
                elif k == CONF_DEFAULT_PAGE_SIZE:
                    val = max(1, min(20, int(val or DEFAULT_PAGE_SIZE)))
                elif k == CONF_WALLPAPER_CYCLE_MINUTES:
                    val = max(0, int(val or DEFAULT_WALLPAPER_CYCLE_MINUTES))
                merged_device[k] = val

        for gk in GLOBAL_CONFIG_KEYS:
            merged_device.pop(gk, None)

        current_global = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG, {}) or {}
        for k in GLOBAL_CONFIG_KEYS:
            if k in incoming_cfg and incoming_cfg[k] != current_global.get(k):
                global_updates[k] = incoming_cfg[k]

        if merged_device != dict(coordinator.device_data):
            coordinator.update_device_config(merged_device)
            await coordinator.async_apply_options()
        if global_updates:
            await async_save_and_broadcast_global_config(hass, global_updates)
        coordinator._bind_wallpaper_cycle_timer()
        coordinator.async_notify_listeners()
        log_studio_event(
            hass,
            "INFO",
            coordinator.device_slug,
            f"Saved configuration for '{coordinator.device_slug}'",
        )

    elif cmd == "log_client_error":
        msg = str(body.get("message") or "Unknown client error")
        src = str(body.get("source") or "webui")
        log_studio_event(hass, "ERROR", src, msg)
        extra["logged"] = True

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
        coordinator = None
        extra["removed"] = True
        extra["next_subentry_id"] = ""

    elif cmd == "add_ble_device":
        system_entries = hass.config_entries.async_entries(DOMAIN)
        if not system_entries:
            raise StudioCommandError("not_found", "Latter System entry is not set up")
        raw_name = str(
            body.get("name") or body.get("device_slug") or "ble_device"
        ).strip()
        target_addr = str(body.get("target_address") or "").strip()
        assigned_person = str(body.get("assigned_person") or "").strip()
        target_slug = (
            normalize_device_slug(raw_name) if raw_name else "ble_device"
        )
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
        rg_coord = find_by_subentry_id(
            _get_all_coordinators(hass), str(body.get("subentry_id") or "")
        )
        if rg_coord is None:
            raise StudioCommandError(
                "not_found", "subentry_id of the Device is missing or unknown"
            )
        rem_grp = str(body.get("device_remote_group") or "area_auto").strip()
        merged_rg: dict[str, Any] = {
            **rg_coord.device_data,
            CONF_DEVICE_REMOTE_GROUP: rem_grp,
        }
        rg_coord.update_device_config(merged_rg)
        rg_coord.async_notify_listeners()

    elif cmd == "create_device_group":
        g_name = str(body.get("name") or "").strip()
        g_desc = str(body.get("description") or "").strip()
        if g_name:
            g_id = (
                re.sub(r"[^a-z0-9]+", "_", g_name.lower()).strip("_") or "group"
            )
            groups, _ = get_device_groups_and_profiles(hass)
            if not any(g.get("id") == g_id for g in groups):
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
        p_name = str(body.get("name") or "").strip()
        p_desc = str(body.get("description") or "").strip()
        _, profiles = get_device_groups_and_profiles(hass)
        new_prof = capture_profile_from_coordinator(
            hass, coordinator, name=p_name, description=p_desc
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
        target_scope = str(body.get("target_scope") or "current").strip()
        _, profiles = get_device_groups_and_profiles(hass)
        prof = next((p for p in profiles if p.get("id") == p_id), None)
        if prof is not None:
            all_coords = _get_all_coordinators(hass)
            if target_scope == "all":
                targets = all_coords
            elif target_scope.startswith("group:"):
                grp_id = target_scope.split(":", 1)[1]
                targets = [c for c in all_coords if c.device_group == grp_id]
            elif target_scope.startswith("device:"):
                d_coord = find_by_subentry_id(
                    all_coords, target_scope.split(":", 1)[1]
                )
                if d_coord is None:
                    raise StudioCommandError(
                        "not_found", f"Unknown Device in target scope '{target_scope}'"
                    )
                targets = [d_coord]
            elif target_scope == "current" and coordinator is not None:
                targets = [coordinator]
            else:
                raise StudioCommandError(
                    "invalid_format", f"Unknown target scope '{target_scope}'"
                )
            await async_apply_profile_to_coordinators(hass, prof, targets)

    elif cmd == "export_backup_json":
        b_scope = str(body.get("scope") or "device").strip()
        extra["bundle"] = build_backup_bundle(
            hass=hass,
            scope=b_scope,
            coordinators=_get_all_coordinators(hass),
            target_coordinator=coordinator,
        )

    elif cmd == "restore_backup":
        bundle = body.get("bundle")
        if not isinstance(bundle, dict):
            raise ValueError("Valid backup bundle required")
        restore_esp = bool(body.get("restore_esphome_entities", True))
        await async_restore_backup_bundle(
            hass,
            bundle=bundle,
            coordinators=_get_all_coordinators(hass),
            target_coordinator=coordinator,
            restore_esphome_entities=restore_esp,
        )

    else:
        raise StudioCommandError("unknown_command", f"Unsupported Studio command: {cmd}")

    return coordinator, extra


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
    if msg.get("studio_rev") != 2:
        _LOGGER.debug(
            "Ignoring get_state from stale cached Studio JS client (missing studio_rev=2)"
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
    """Subscribe to live Latter Studio state & BLE survey updates."""
    if msg.get("studio_rev") != 2:
        _LOGGER.debug(
            "Ignoring subscribe from stale cached Studio JS client (missing studio_rev=2)"
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
) -> None:
    """Execute an admin-gated System or Device command from Latter Studio."""
    coord = resolve_target_coordinator(hass, msg.get("subentry_id"))
    cmd = str(msg["command"]).strip()
    body = dict(msg.get("payload") or {})
    try:
        updated_coord, extra = await _async_execute_studio_command(
            hass, coord, cmd, body
        )
    except PermissionError as err:
        connection.send_error(msg["id"], "forbidden", str(err))
        return
    except StudioCommandError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("Latter Studio command '%s' failed: %s", cmd, err)
        connection.send_error(msg["id"], "command_failed", str(err))
        return

    state_payload = build_studio_state_payload(hass, updated_coord)
    connection.send_result(
        msg["id"],
        {
            **state_payload,
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
    await _async_handle_ws_command_impl(hass, connection, msg)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/device/command",
        vol.Required("command"): str,
        vol.Optional("subentry_id"): vol.Any(str, None),
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
    await _async_handle_ws_command_impl(hass, connection, msg)


async def _async_handle_ws_export_impl(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    *,
    is_device: bool,
) -> None:
    """Export non-secret System or Device configuration JSON."""
    coord = resolve_target_coordinator(hass, msg.get("subentry_id"))
    scope = "device" if is_device else str(msg.get("scope", "system"))
    if scope != "system" and coord is None:
        connection.send_error(
            msg["id"], "device_required", "Select a Device to export a Device backup"
        )
        return
    bundle = build_backup_bundle(
        hass=hass,
        scope=scope,
        coordinators=_get_all_coordinators(hass),
        target_coordinator=coord,
    )
    connection.send_result(msg["id"], {"bundle": bundle})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/system/export",
        vol.Optional("subentry_id"): vol.Any(str, None),
        vol.Optional("scope", default="system"): str,
    }
)
@websocket_api.async_response
async def ws_handle_system_export(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Export non-secret System configuration JSON."""
    await _async_handle_ws_export_impl(
        hass, connection, msg, is_device=msg.get("scope") == "device"
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/device/export",
        vol.Optional("subentry_id"): vol.Any(str, None),
        vol.Optional("scope", default="device"): str,
    }
)
@websocket_api.async_response
async def ws_handle_device_export(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Export non-secret Device configuration JSON."""
    await _async_handle_ws_export_impl(hass, connection, msg, is_device=True)


async def _async_handle_ws_import_impl(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Import and restore a System or Device JSON snapshot."""
    coord = resolve_target_coordinator(hass, msg.get("subentry_id"))
    if str(msg["bundle"].get("scope") or "device") != "system" and coord is None:
        connection.send_error(
            msg["id"], "device_required", "Select the Device to restore this backup onto"
        )
        return
    await async_restore_backup_bundle(
        hass,
        bundle=msg["bundle"],
        coordinators=_get_all_coordinators(hass),
        target_coordinator=coord,
        restore_esphome_entities=bool(
            msg.get("restore_esphome_entities", True)
        ),
    )
    connection.send_result(
        msg["id"],
        build_studio_state_payload(hass, coord),
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
    """Import and restore a System JSON snapshot."""
    await _async_handle_ws_import_impl(hass, connection, msg)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "latter/device/import",
        vol.Optional("subentry_id"): vol.Any(str, None),
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
    """Import and restore a Device JSON snapshot."""
    await _async_handle_ws_import_impl(hass, connection, msg)


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
    ):
        websocket_api.async_register_command(hass, handler)
