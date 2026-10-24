"""Server-Side Web Companion Studio & REST API for Latter."""

from __future__ import annotations

from http import HTTPStatus
import logging
from pathlib import Path
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar

from .browse_engine import is_music_assistant_player
from .const import (
    API_BRAND_ICON_PATH,
    API_COMPANION_API_PATH,
    API_COMPANION_UI_PATH,
    CONF_ALARM_ENTITY,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_ROOM_OFFSETS,
    CONF_CALENDAR_ENTITIES,
    CONF_CAMERA_ENTITY,
    CONF_COMPANION_BASE_URL,
    CONF_CUSTOM_BINDINGS,
    CONF_CUSTOM_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_PROFILE,
    CONF_DEVICE_SLUG,
    CONF_DISPLAY_SHAPE,
    CONF_DOCK_APPS,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PRESENCE_ENTITY,
    CONF_REMOTE_1,
    CONF_REMOTE_2,
    CONF_REMOTE_3,
    CONF_REMOTE_4,
    CONF_SYNC_DEVICE_AREA,
    CONF_VOL_SPEAKER_1,
    CONF_VOL_SPEAKER_2,
    CONF_VOL_TARGET_1,
    CONF_VOL_TARGET_2,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    CONF_WEB_THEME,
    DEFAULT_ART_SIZE,
    DEFAULT_DEVICE_PROFILE,
    DEFAULT_DISPLAY_SHAPE,
    DEFAULT_PAGE_SIZE,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DEFAULT_WEB_THEME,
    DOMAIN,
    INTEGRATION_VERSION,
)
from .coordinator import LatterCoordinator
from .repairs import async_audit_coordinator_health
from .room_engine import (
    async_execute_room_action,
    get_area_entities,
    get_esphome_device_entities,
    inject_esphome_visit_link,
)
from .wallpaper_engine import (
    delete_uploaded_wallpaper,
    list_wallpaper_catalog,
    save_uploaded_wallpaper,
)

_LOGGER = logging.getLogger(__name__)

VALID_WEB_THEMES: set[str] = {"dark", "light", "system"}


def _normalize_web_theme(raw_theme: Any) -> str:
    """Normalize legacy or custom theme strings to 'dark', 'light', or 'system'."""
    val = str(raw_theme or DEFAULT_WEB_THEME).strip().lower()
    if val in VALID_WEB_THEMES:
        return val
    if "light" in val or "day" in val or "warm" in val:
        return "light"
    return "dark"


def _build_companion_state_payload(
    hass: HomeAssistant, coordinator: LatterCoordinator
) -> dict[str, Any]:
    """Build the JSON payload consumed by the Latter Web Companion Studio."""
    area_reg = ar.async_get(hass)
    areas_list = [
        {"id": a.id, "name": a.name}
        for a in sorted(area_reg.async_list_areas(), key=lambda x: x.name.lower())
    ]

    ma_speakers: list[dict[str, str]] = []
    remotes_list: list[dict[str, str]] = []
    volume_targets: list[dict[str, str]] = []
    alarms_list: list[dict[str, str]] = []
    cameras_list: list[dict[str, str]] = []
    weathers_list: list[dict[str, str]] = []
    calendars_list: list[dict[str, str]] = []
    presence_sensors: list[dict[str, str]] = []
    bindable_entities: list[dict[str, str]] = []

    for state_obj in sorted(
        hass.states.async_all(), key=lambda s: s.entity_id
    ):
        ent_id = state_obj.entity_id
        domain = state_obj.domain
        friendly = str(state_obj.attributes.get("friendly_name") or ent_id)
        suffix_state = " [Off/Unavailable]" if state_obj.state == "unavailable" else ""
        item = {"id": ent_id, "name": f"{friendly} ({ent_id}){suffix_state}", "domain": domain}

        if domain == "media_player":
            remotes_list.append(item)
            volume_targets.append(item)
            if (
                ent_id == coordinator.local_speaker
                or is_music_assistant_player(hass, state_obj)
            ):
                ma_speakers.append(item)
        elif domain == "remote":
            remotes_list.append(item)
        elif domain in ("number", "input_number"):
            volume_targets.append(item)
        elif domain == "alarm_control_panel":
            alarms_list.append(item)
        elif domain == "camera":
            cameras_list.append(item)
        elif domain == "weather":
            weathers_list.append(item)
        elif domain == "calendar":
            calendars_list.append(item)
        elif domain in ("sensor", "device_tracker", "input_text"):
            presence_sensors.append(item)

        if domain in (
            "light",
            "scene",
            "cover",
            "fan",
            "switch",
            "climate",
            "script",
            "automation",
            "button",
            "input_boolean",
            "lock",
            "alarm_control_panel",
            "media_player",
        ):
            bindable_entities.append(item)

    _, room_attrs = coordinator.get_room_context_payload()
    media_state, media_attrs = coordinator.get_active_media_payload()
    _, remote_attrs = coordinator.get_remote_config_payload()
    esphome_inspector = get_esphome_device_entities(
        hass, coordinator.device_slug
    )
    active_room_cards = get_area_entities(
        hass,
        area_id=coordinator.active_area_id,
        domain_filter="all",
        custom_entities=coordinator.custom_entities,
        local_speaker=coordinator.local_speaker,
    )
    wallpapers_catalog = list_wallpaper_catalog(
        hass,
        coordinator.device_slug,
        coordinator.wallpaper_source,
        coordinator.wallpaper_favorites,
    )

    saved_theme = _normalize_web_theme(
        coordinator.get_opt(CONF_WEB_THEME, DEFAULT_WEB_THEME)
    )

    config_data = {
        CONF_DEVICE_SLUG: coordinator.device_slug,
        CONF_DEVICE_PROFILE: coordinator.get_opt(
            CONF_DEVICE_PROFILE, DEFAULT_DEVICE_PROFILE
        ),
        CONF_DISPLAY_SHAPE: coordinator.display_shape,
        CONF_DEFAULT_PAGE_SIZE: coordinator.default_page_size,
        CONF_WEB_THEME: saved_theme,
        CONF_COMPANION_BASE_URL: coordinator.companion_base_url,
        CONF_DEFAULT_SPEAKER: coordinator.get_opt(
            CONF_DEFAULT_SPEAKER, coordinator.active_speaker
        ),
        CONF_VOL_SPEAKER_1: coordinator.get_opt(CONF_VOL_SPEAKER_1, ""),
        CONF_VOL_TARGET_1: coordinator.get_opt(CONF_VOL_TARGET_1, ""),
        CONF_VOL_SPEAKER_2: coordinator.get_opt(CONF_VOL_SPEAKER_2, ""),
        CONF_VOL_TARGET_2: coordinator.get_opt(CONF_VOL_TARGET_2, ""),
        CONF_DEFAULT_AREA: coordinator.get_opt(CONF_DEFAULT_AREA, ""),
        CONF_NATIVE_BLE_TRACKING: coordinator.native_ble_tracking_enabled,
        CONF_BLE_BEACON_UUID: coordinator.ble_beacon_uuid,
        CONF_BLE_ROOM_OFFSETS: coordinator.ble_room_offsets,
        CONF_PRESENCE_ENTITY: coordinator.presence_entity or "",
        CONF_BLE_AUTO_SWITCH: coordinator.ble_auto_switch_enabled,
        CONF_SYNC_DEVICE_AREA: coordinator.sync_device_area_enabled,
        CONF_AREA_HANDOFF: coordinator.area_handoff_enabled,
        CONF_ALARM_ENTITY: coordinator.get_opt(CONF_ALARM_ENTITY, "")
        or coordinator.alarm_entity
        or "",
        CONF_CAMERA_ENTITY: coordinator.camera_entity or "",
        CONF_REMOTE_1: coordinator.get_opt(CONF_REMOTE_1, ""),
        CONF_REMOTE_2: coordinator.get_opt(CONF_REMOTE_2, ""),
        CONF_REMOTE_3: coordinator.get_opt(CONF_REMOTE_3, ""),
        CONF_REMOTE_4: coordinator.get_opt(CONF_REMOTE_4, ""),
        CONF_WEATHER_ENTITY: coordinator.weather_entity or "",
        CONF_CALENDAR_ENTITIES: coordinator.calendar_entities,
        CONF_CUSTOM_ENTITIES: coordinator.custom_entities,
        CONF_CUSTOM_BINDINGS: coordinator.custom_bindings,
        CONF_DOCK_APPS: coordinator.dock_apps_csv,
        CONF_WALLPAPER_SOURCE: coordinator.wallpaper_source,
        CONF_WALLPAPER_FAVORITES: coordinator.wallpaper_favorites,
        CONF_WALLPAPER_CYCLE_MINUTES: coordinator.wallpaper_cycle_minutes,
        CONF_ART_SIZE: coordinator.art_size,
    }

    try:
        health_warnings = async_audit_coordinator_health(hass, coordinator)
    except Exception:  # noqa: BLE001
        health_warnings = []

    ble_survey_rows: list[dict[str, Any]] = []
    if coordinator._ble_tracker is not None and hasattr(
        coordinator._ble_tracker, "get_room_calibration_telemetry"
    ):
        ble_survey_rows = coordinator._ble_tracker.get_room_calibration_telemetry()

    return {
        "entry_id": coordinator.entry.entry_id,
        "title": coordinator.entry.title,
        "version": INTEGRATION_VERSION,
        "health_warnings": health_warnings,
        "config": config_data,
        "esphome": esphome_inspector,
        "wallpapers": wallpapers_catalog,
        "live": {
            "active_area_id": coordinator.active_area_id or "",
            "active_area_name": room_attrs.get("area_name", "Home"),
            "room_temp": room_attrs.get("room_temp"),
            "room_humidity": room_attrs.get("room_humidity"),
            "lights_on": room_attrs.get("lights_on", 0),
            "covers_open": room_attrs.get("covers_open", 0),
            "entity_count": room_attrs.get("entity_count", 0),
            "room_cards": active_room_cards[:12],
            "ble_closest_proxy": room_attrs.get("ble_closest_proxy", ""),
            "ble_packets_seen": room_attrs.get("ble_packets_seen", 0),
            "ble_rssi_by_room": room_attrs.get("ble_rssi_by_room", {}),
            "ble_survey_rows": ble_survey_rows,
            "ble_scanners_map": room_attrs.get("ble_scanners_map", {}),
            "active_speaker": coordinator.active_speaker,
            "local_speaker": coordinator.local_speaker,
            "volume_entity": media_attrs.get("volume_entity", ""),
            "media_state": media_state,
            "media_title": media_attrs.get("title", "Idle"),
            "media_artist": media_attrs.get("artist", "None"),
            "media_art_url": media_attrs.get("art_url", "none"),
            "alarm_state": room_attrs.get("alarm_state", "none"),
            "wallpaper_url": room_attrs.get("wallpaper_url", "none"),
            "active_remote_slot": coordinator.active_remote_slot,
            "remote_slots_meta": remote_attrs,
        },
        "catalog": {
            "areas": areas_list,
            "ma_speakers": ma_speakers,
            "volume_targets": volume_targets,
            "remotes": remotes_list,
            "alarms": alarms_list,
            "cameras": cameras_list,
            "weathers": weathers_list,
            "calendars": calendars_list,
            "presence_sensors": presence_sensors,
            "bindable_entities": bindable_entities,
        },
    }


class LatterCompanionApiView(HomeAssistantView):
    """JSON REST API for the Latter Server-Side Web Companion Studio."""

    requires_auth = False
    url = API_COMPANION_API_PATH
    name = "api:latter:companion_api"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API view."""
        self.hass = hass

    def _resolve_coordinator(
        self, request: web.Request, entry_id: str
    ) -> LatterCoordinator | None:
        domain_data = self.hass.data.get(DOMAIN, {})
        coordinator: LatterCoordinator | None = domain_data.get(entry_id)
        if not isinstance(coordinator, LatterCoordinator):
            return None
        token = request.query.get("token") or request.headers.get("X-Latter-Token")
        if not coordinator.verify_token(token):
            return None
        return coordinator

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        """Return live state, configuration, ESPHome device inspector, and entity catalog."""
        coordinator = self._resolve_coordinator(request, entry_id)
        if coordinator is None:
            return web.json_response(
                {"error": "Unauthorized or unknown entry"},
                status=HTTPStatus.FORBIDDEN,
            )
        payload = _build_companion_state_payload(self.hass, coordinator)
        return web.json_response(payload)

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        """Save updated configuration, manage wallpapers, or execute a live entity/device action."""
        coordinator = self._resolve_coordinator(request, entry_id)
        if coordinator is None:
            return web.json_response(
                {"error": "Unauthorized or unknown entry"},
                status=HTTPStatus.FORBIDDEN,
            )

        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return web.json_response(
                {"error": "Invalid JSON body"}, status=HTTPStatus.BAD_REQUEST
            )

        cmd = str(body.get("command") or "save_config")

        if cmd == "set_ble_room_offset":
            area_id = str(body.get("area_id") or "").strip()
            offset_val = float(body.get("offset_db") or 0.0)
            offsets = dict(coordinator.ble_room_offsets)
            if abs(offset_val) < 0.1:
                offsets.pop(area_id, None)
            elif area_id:
                offsets[area_id] = round(max(-25.0, min(25.0, offset_val)), 1)
            merged_off: dict[str, Any] = {
                **coordinator.entry.data,
                **(coordinator.entry.options or {}),
                CONF_BLE_ROOM_OFFSETS: offsets,
            }
            self.hass.config_entries.async_update_entry(
                coordinator.entry, data=merged_off, options=merged_off
            )
            if coordinator._ble_tracker is not None:
                coordinator._ble_tracker.set_room_offsets(offsets)
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "auto_calibrate_here":
            target_area_id = str(body.get("area_id") or "").strip()
            if target_area_id and coordinator._ble_tracker is not None:
                rows = coordinator._ble_tracker.get_room_calibration_telemetry()
                target_row = next(
                    (r for r in rows if r["area_id"] == target_area_id), None
                )
                competing = [
                    r["effective_rssi"]
                    for r in rows
                    if r["area_id"] != target_area_id
                    and r["effective_rssi"] is not None
                ]
                offsets = dict(coordinator.ble_room_offsets)
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
                merged_cal: dict[str, Any] = {
                    **coordinator.entry.data,
                    **(coordinator.entry.options or {}),
                    CONF_BLE_ROOM_OFFSETS: offsets,
                }
                self.hass.config_entries.async_update_entry(
                    coordinator.entry, data=merged_cal, options=merged_cal
                )
                coordinator._ble_tracker.set_room_offsets(offsets)
                coordinator.async_set_active_area(
                    target_area_id, handoff_media=False, sync_device_registry=True
                )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "send_test_notification":
            title = str(body.get("title") or "Doorbell Alert").strip()
            message = str(body.get("message") or "Motion detected at Front Door").strip()
            priority = str(body.get("priority") or "normal").strip()
            inc_cam = bool(body.get("include_camera", False))
            cam_ent = coordinator.camera_entity if inc_cam else None
            await self.hass.services.async_call(
                DOMAIN,
                "notify_device",
                {
                    "device_slug": coordinator.device_slug,
                    "title": title,
                    "message": message,
                    "priority": priority,
                    "chime": True,
                    **({"camera_entity": cam_ent} if cam_ent else {}),
                },
                blocking=True,
            )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "set_theme":
            theme_val = _normalize_web_theme(body.get("web_theme"))
            merged_theme: dict[str, Any] = {
                **coordinator.entry.data,
                **(coordinator.entry.options or {}),
                CONF_WEB_THEME: theme_val,
            }
            self.hass.config_entries.async_update_entry(
                coordinator.entry, data=merged_theme, options=merged_theme
            )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "activate_remote_slot":
            slot_num = max(1, min(4, int(body.get("slot") or 1)))
            coordinator.active_remote_slot = slot_num
            coordinator._schedule_persist_runtime_state()
            coordinator._notify_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "upload_wallpaper":
            filename = str(body.get("filename") or "wallpaper.jpg")
            data_b64 = str(body.get("data_b64") or "")
            if data_b64:
                new_source = await self.hass.async_add_executor_job(
                    save_uploaded_wallpaper,
                    self.hass,
                    coordinator.device_slug,
                    filename,
                    data_b64,
                )
                favs = list(coordinator.wallpaper_favorites)
                if new_source not in favs:
                    favs.append(new_source)
                merged_wp: dict[str, Any] = {
                    **coordinator.entry.data,
                    **(coordinator.entry.options or {}),
                    CONF_WALLPAPER_SOURCE: new_source,
                    CONF_WALLPAPER_FAVORITES: favs,
                }
                self.hass.config_entries.async_update_entry(
                    coordinator.entry, data=merged_wp, options=merged_wp
                )
                coordinator._notify_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "select_wallpaper":
            source_id = str(body.get("source_id") or "").strip()
            merged_sel: dict[str, Any] = {
                **coordinator.entry.data,
                **(coordinator.entry.options or {}),
                CONF_WALLPAPER_SOURCE: source_id,
            }
            self.hass.config_entries.async_update_entry(
                coordinator.entry, data=merged_sel, options=merged_sel
            )
            coordinator._notify_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "toggle_wallpaper_favorite":
            source_id = str(body.get("source_id") or "").strip()
            favs = list(coordinator.wallpaper_favorites)
            if source_id in favs:
                favs.remove(source_id)
            elif source_id:
                favs.append(source_id)
            merged_fav: dict[str, Any] = {
                **coordinator.entry.data,
                **(coordinator.entry.options or {}),
                CONF_WALLPAPER_FAVORITES: favs,
            }
            self.hass.config_entries.async_update_entry(
                coordinator.entry, data=merged_fav, options=merged_fav
            )
            coordinator._bind_wallpaper_cycle_timer()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "delete_wallpaper":
            source_id = str(body.get("source_id") or "").strip()
            if source_id:
                await self.hass.async_add_executor_job(
                    delete_uploaded_wallpaper,
                    self.hass,
                    coordinator.device_slug,
                    source_id,
                )
                favs = [f for f in coordinator.wallpaper_favorites if f != source_id]
                new_active = (
                    ""
                    if coordinator.wallpaper_source == source_id
                    else coordinator.wallpaper_source
                )
                merged_del: dict[str, Any] = {
                    **coordinator.entry.data,
                    **(coordinator.entry.options or {}),
                    CONF_WALLPAPER_SOURCE: new_active,
                    CONF_WALLPAPER_FAVORITES: favs,
                }
                self.hass.config_entries.async_update_entry(
                    coordinator.entry, data=merged_del, options=merged_del
                )
                coordinator._notify_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "set_active_area":
            area_id = str(body.get("area_id") or "")
            if area_id:
                coordinator.async_set_active_area(
                    area_id,
                    handoff_media=False,
                    sync_device_registry=bool(body.get("sync_device", False)),
                )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "set_active_speaker":
            speaker_id = str(body.get("speaker") or "").strip()
            if speaker_id:
                coordinator.async_set_active_speaker(speaker_id, transfer_queue=True)
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd in ("test_binding", "esphome_entity_action", "room_card_action"):
            entity_id = str(body.get("entity_id") or "").strip()
            action = str(body.get("action") or "toggle").strip()
            level = body.get("level")
            option = body.get("option")
            if entity_id:
                await async_execute_room_action(
                    self.hass,
                    entity_id=entity_id,
                    action=action,
                    level=int(float(level)) if level is not None else None,
                    option=str(option) if option is not None else None,
                )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "save_config":
            incoming_cfg = body.get("config") or {}
            merged: dict[str, Any] = {
                **coordinator.entry.data,
                **(coordinator.entry.options or {}),
            }

            for k in (
                CONF_DEVICE_SLUG,
                CONF_DEVICE_PROFILE,
                CONF_DISPLAY_SHAPE,
                CONF_DEFAULT_PAGE_SIZE,
                CONF_WEB_THEME,
                CONF_COMPANION_BASE_URL,
                CONF_DEFAULT_SPEAKER,
                CONF_VOL_SPEAKER_1,
                CONF_VOL_TARGET_1,
                CONF_VOL_SPEAKER_2,
                CONF_VOL_TARGET_2,
                CONF_DEFAULT_AREA,
                CONF_NATIVE_BLE_TRACKING,
                CONF_BLE_BEACON_UUID,
                CONF_PRESENCE_ENTITY,
                CONF_BLE_AUTO_SWITCH,
                CONF_SYNC_DEVICE_AREA,
                CONF_AREA_HANDOFF,
                CONF_ALARM_ENTITY,
                CONF_CAMERA_ENTITY,
                CONF_REMOTE_1,
                CONF_REMOTE_2,
                CONF_REMOTE_3,
                CONF_REMOTE_4,
                CONF_WEATHER_ENTITY,
                CONF_CALENDAR_ENTITIES,
                CONF_CUSTOM_ENTITIES,
                CONF_CUSTOM_BINDINGS,
                CONF_DOCK_APPS,
                CONF_WALLPAPER_SOURCE,
                CONF_WALLPAPER_CYCLE_MINUTES,
                CONF_ART_SIZE,
            ):
                if k in incoming_cfg:
                    val = incoming_cfg[k]
                    if k == CONF_ART_SIZE:
                        val = int(val or DEFAULT_ART_SIZE)
                    elif k == CONF_DEFAULT_PAGE_SIZE:
                        val = max(1, min(20, int(val or DEFAULT_PAGE_SIZE)))
                    elif k == CONF_WALLPAPER_CYCLE_MINUTES:
                        val = max(0, int(val or DEFAULT_WALLPAPER_CYCLE_MINUTES))
                    elif k == CONF_WEB_THEME:
                        val = _normalize_web_theme(val)
                    merged[k] = val

            self.hass.config_entries.async_update_entry(
                coordinator.entry, data=merged, options=merged
            )
            inject_esphome_visit_link(
                self.hass,
                coordinator.device_slug,
                coordinator.build_companion_url(),
            )
            coordinator._bind_wallpaper_cycle_timer()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        return web.json_response(
            {"error": f"Unknown command: {cmd}"}, status=HTTPStatus.BAD_REQUEST
        )


COMPANION_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<link rel="icon" type="image/png" href="/api/latter/brand/icon.png">
<title>Latter Companion Studio</title>
<style>
  :root, [data-theme="dark"] {
    --bg: #080a0f;
    --sidebar: #0d1118;
    --card: #121822;
    --card-hover: #18202e;
    --border: #1e2736;
    --input-bg: #0a0e15;
    --text: #dce3ec;
    --text-strong: #f1f5f9;
    --muted: #8492a6;
    --accent: #6899d3;
    --accent-solid: #2b5b94;
    --accent-subtle: rgba(104, 153, 211, 0.11);
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
  }
  [data-theme="light"] {
    --bg: #dde3ea;
    --sidebar: #e6ebf1;
    --card: #eef2f6;
    --card-hover: #e2e8f0;
    --border: #cbd5e1;
    --input-bg: #e2e8f0;
    --text: #1e293b;
    --text-strong: #0f172a;
    --muted: #475569;
    --accent: #2b5b94;
    --accent-solid: #2b5b94;
    --accent-subtle: rgba(43, 91, 148, 0.10);
    --success: #059669;
    --warning: #d97706;
    --danger: #dc2626;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    font-size: 13.5px;
    -webkit-tap-highlight-color: transparent;
  }
  code, .mono {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    font-size: 12px;
  }
  .app-shell {
    display: grid;
    grid-template-columns: 242px minmax(0, 1fr);
    min-height: 100vh;
  }
  aside.sidebar {
    background: var(--sidebar);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    padding: 16px 12px;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 4px 8px 16px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 14px;
  }
  .brand-text { min-width: 0; }
  .brand-text h1 {
    margin: 0;
    font-size: 14px;
    font-weight: 700;
    color: var(--text-strong);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .brand-text small {
    color: var(--muted);
    font-size: 11px;
    display: block;
    margin-top: 2px;
    font-variant-numeric: tabular-nums;
  }
  .nav-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    padding: 10px 12px;
    border-radius: 7px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--muted);
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    text-align: left;
    white-space: nowrap;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .nav-btn:hover {
    background: var(--card-hover);
    color: var(--text-strong);
  }
  .nav-btn.active {
    background: var(--accent-subtle);
    color: var(--accent);
    border-color: var(--accent);
  }
  .nav-badge {
    font-size: 11px;
    padding: 1px 7px;
    border-radius: 5px;
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }
  .sidebar-footer {
    margin-top: auto;
    padding-top: 14px;
    border-top: 1px solid var(--border);
  }
  .main-area {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }
  header.topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 24px;
    background: var(--sidebar);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 15;
    flex-wrap: wrap;
    gap: 10px;
  }
  .topbar-status {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .status-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 10px;
    border-radius: 6px;
    background: var(--card);
    border: 1px solid var(--border);
    font-size: 12px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .dot-live {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--success);
  }
  .topbar-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .dirty-banner {
    display: none;
    align-items: center;
    font-size: 11.5px;
    font-weight: 700;
    color: var(--warning);
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.35);
    padding: 5px 10px;
    border-radius: 6px;
  }
  .dirty-banner.visible { display: inline-flex; }
  button.btn-primary {
    background: var(--accent-solid);
    color: #ffffff;
    border: 1px solid transparent;
    padding: 8px 14px;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
    font-size: 12.5px;
  }
  button.btn-secondary {
    background: var(--card);
    color: var(--text-strong);
    border: 1px solid var(--border);
    padding: 8px 13px;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
    font-size: 12.5px;
  }
  button.btn-action {
    background: var(--accent-subtle);
    color: var(--text-strong);
    border: 1px solid var(--accent);
    padding: 10px 14px;
    border-radius: 7px;
    font-weight: 700;
    cursor: pointer;
    font-size: 13px;
    text-align: center;
    transition: background 0.15s ease;
  }
  button.btn-action:hover {
    background: var(--accent-solid);
    color: #ffffff;
  }
  button.btn-danger {
    background: rgba(239, 68, 68, 0.12);
    color: var(--danger);
    border: 1px solid rgba(239, 68, 68, 0.3);
    padding: 6px 10px;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
  }
  .content-wrap {
    max-width: 1200px;
    width: 100%;
    margin: 0 auto;
    padding: 22px 24px 64px;
  }
  .page-header { margin-bottom: 18px; }
  .page-header h2 {
    margin: 0 0 4px;
    font-size: 18px;
    font-weight: 700;
    color: var(--text-strong);
  }
  .page-header p {
    margin: 0;
    color: var(--muted);
    font-size: 13px;
    line-height: 1.45;
  }
  .grid-2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 16px;
    margin-bottom: 16px;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 9px;
    padding: 18px;
    min-width: 0;
  }
  .card h3 {
    margin: 0 0 5px;
    font-size: 14.5px;
    font-weight: 700;
    color: var(--text-strong);
  }
  .card p.desc {
    margin: 0 0 14px;
    font-size: 12.5px;
    color: var(--muted);
    line-height: 1.45;
  }
  .hero-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 10px;
    margin-bottom: 16px;
  }
  .stat-box {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 11px 13px;
  }
  .stat-box span {
    display: block;
    font-size: 10.5px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--muted);
    margin-bottom: 3px;
  }
  .stat-box strong {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-strong);
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-variant-numeric: tabular-nums;
  }
  .field { margin-bottom: 13px; }
  .field label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    margin-bottom: 5px;
  }
  select, input[type="text"], input[type="number"] {
    width: 100%;
    padding: 9px 11px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--input-bg);
    color: var(--text-strong);
    font-size: 13.5px;
  }
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    gap: 12px;
  }
  .toggle-row:last-child { border-bottom: none; }
  .rssi-bar { margin-bottom: 10px; }
  .rssi-header {
    display: flex;
    justify-content: space-between;
    font-size: 12.5px;
    margin-bottom: 4px;
    font-variant-numeric: tabular-nums;
  }
  .rssi-track {
    height: 7px;
    background: var(--input-bg);
    border-radius: 4px;
    overflow: hidden;
    border: 1px solid var(--border);
  }
  .rssi-fill {
    height: 100%;
    background: var(--accent-solid);
    border-radius: 4px;
    transition: width 0.25s ease;
  }
  .room-cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
    gap: 8px;
    margin-top: 10px;
  }
  .room-mini-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-radius: 7px;
    background: var(--input-bg);
    border: 1px solid var(--border);
    cursor: pointer;
  }
  .room-mini-card.on {
    border-color: var(--accent);
    background: var(--accent-subtle);
  }
  .room-mini-card strong {
    font-size: 12.5px;
    color: var(--text-strong);
    display: block;
  }
  .room-mini-card small {
    font-size: 11px;
    color: var(--muted);
  }
  .native-controls-box {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .native-ctrl-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 9px 12px;
    background: var(--input-bg);
    border: 1px solid var(--border);
    border-radius: 7px;
  }
  .native-ctrl-row .lbl {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-strong);
    min-width: 0;
  }
  .native-ctrl-row .lbl small {
    display: block;
    font-weight: 400;
    font-size: 11px;
    color: var(--muted);
  }
  .native-ctrl-row .widget {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .native-ctrl-row select {
    width: auto;
    min-width: 150px;
    max-width: 220px;
    padding: 7px 10px;
  }
  .native-ctrl-row input[type="range"] {
    width: 120px;
    accent-color: var(--accent-solid);
  }
  .native-ctrl-row input[type="number"] {
    width: 78px;
    padding: 6px 8px;
    text-align: right;
  }
  .remote-slot-card {
    background: var(--input-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .remote-slot-card.active-slot {
    border-color: var(--accent);
    background: var(--accent-subtle);
  }
  .remote-slot-hdr {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }
  .remote-slot-hdr strong {
    font-size: 13.5px;
    color: var(--text-strong);
  }
  .action-btn-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 8px;
  }
  .state-badge {
    display: inline-block;
    padding: 4px 8px;
    border-radius: 5px;
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--accent);
    font-weight: 600;
    font-size: 11.5px;
    font-variant-numeric: tabular-nums;
  }
  .wp-gallery {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(175px, 1fr));
    gap: 12px;
    margin-top: 12px;
  }
  .wp-card {
    background: var(--input-bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    text-align: center;
  }
  .wp-card.active {
    border-color: var(--accent);
    background: var(--accent-subtle);
  }
  .wp-thumb {
    width: 112px;
    height: 112px;
    object-fit: cover;
    border: 1px solid var(--border);
    background: #000;
  }
  .wp-thumb.circle { border-radius: 50%; }
  .wp-thumb.square { border-radius: 8px; }
  .wp-title {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-strong);
    line-height: 1.3;
  }
  .wp-actions {
    display: flex;
    gap: 6px;
    width: 100%;
    justify-content: center;
    margin-top: auto;
  }
  .binding-row {
    display: grid;
    grid-template-columns: 1.1fr 1.6fr 0.9fr auto auto;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
    background: var(--input-bg);
    padding: 9px;
    border-radius: 7px;
    border: 1px solid var(--border);
  }
  .chip-list { display: flex; flex-wrap: wrap; gap: 7px; margin-top: 10px; }
  .chip {
    background: var(--input-bg);
    border: 1px solid var(--border);
    color: var(--text-strong);
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .chip b { cursor: pointer; color: var(--danger); }
  .toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: var(--card);
    color: var(--text-strong);
    border: 1px solid var(--accent);
    padding: 10px 16px;
    border-radius: 7px;
    font-weight: 600;
    font-size: 12.5px;
    display: none;
    z-index: 50;
  }
  .hidden { display: none !important; }

  @media (max-width: 860px) {
    .app-shell { grid-template-columns: 1fr; }
    aside.sidebar {
      position: sticky;
      top: 0;
      z-index: 25;
      height: auto;
      padding: 10px 12px;
      border-right: none;
      border-bottom: 1px solid var(--border);
    }
    .brand {
      padding: 0 0 8px;
      margin-bottom: 8px;
      justify-content: space-between;
    }
    .nav-list {
      flex-direction: row;
      overflow-x: auto;
      padding-bottom: 4px;
      gap: 6px;
      scrollbar-width: none;
    }
    .nav-list::-webkit-scrollbar { display: none; }
    .nav-btn {
      width: auto;
      padding: 8px 12px;
      font-size: 12.5px;
      background: var(--card);
      border-color: var(--border);
    }
    .sidebar-footer { display: none; }
    header.topbar {
      position: static;
      padding: 10px 14px;
    }
    .content-wrap { padding: 16px 14px 72px; }
    .grid-2 { grid-template-columns: 1fr; }
    .hero-stats { grid-template-columns: repeat(2, 1fr); }
    .binding-row { grid-template-columns: 1fr; }
    .native-ctrl-row {
      flex-direction: column;
      align-items: stretch;
      gap: 8px;
    }
    .native-ctrl-row .widget { justify-content: space-between; }
    .native-ctrl-row select { max-width: 100%; width: 100%; }
  }
</style>
</head>
<body data-theme="dark">
<div class="app-shell">
  <!-- UNIFIED DOMAIN-FIRST SIDEBAR -->
  <aside class="sidebar">
    <div class="brand">
      <div style="display:flex;align-items:center;gap:10px;min-width:0;">
        <img src="/api/latter/brand/icon.png" alt="Latter" style="width:34px;height:34px;border-radius:8px;object-fit:contain;flex-shrink:0;" onerror="this.style.display='none'">
        <div class="brand-text">
          <h1 id="hdr-title">Latter Studio</h1>
          <small id="hdr-sub">v1.6.0</small>
        </div>
      </div>
    </div>

    <div class="nav-list">
      <button class="nav-btn active" onclick="switchView('dashboard', this)">
        <span>Dashboard & Radar</span>
        <span class="nav-badge" id="nav-room-badge">--</span>
      </button>
      <button class="nav-btn" onclick="switchView('home_display', this)">
        <span>Home & Display</span>
      </button>
      <button class="nav-btn" onclick="switchView('voice', this)">
        <span>Voice Assistant</span>
      </button>
      <button class="nav-btn" onclick="switchView('audio', this)">
        <span>Audio, Music & Sound</span>
      </button>
      <button class="nav-btn" onclick="switchView('remotes', this)">
        <span>TV Remotes & Home</span>
      </button>
      <button class="nav-btn" onclick="switchView('system', this)">
        <span>System & Triggers</span>
      </button>
      <button class="nav-btn" onclick="switchView('raw', this)">
        <span>All Entities</span>
        <span class="nav-badge" id="nav-esp-badge">0</span>
      </button>
    </div>

    <div class="sidebar-footer">
      <div class="field" style="margin-bottom:0;">
        <label>Appearance</label>
        <select id="cfg-web_theme" onchange="onThemeChanged(this.value)">
          <option value="dark">Dark</option>
          <option value="light">Light</option>
          <option value="system">System</option>
        </select>
      </div>
    </div>
  </aside>

  <!-- MAIN CONTENT AREA -->
  <div class="main-area">
    <header class="topbar">
      <div class="topbar-status">
        <div class="status-chip"><span class="dot-live"></span><span id="top-room">Room: --</span></div>
        <div class="status-chip"><span id="top-speaker">Speaker: --</span></div>
        <div class="status-chip"><span id="top-media">Media: Idle</span></div>
      </div>
      <div class="topbar-actions">
        <div id="dirty-indicator" class="dirty-banner">Unsaved</div>
        <button class="btn-secondary" onclick="refreshState(true)">Sync</button>
        <button class="btn-primary" onclick="saveAllConfig()">Save Changes</button>
      </div>
    </header>

    <div class="content-wrap">
      <!-- 1. DASHBOARD & BLE ROOM RADAR -->
      <section id="view-dashboard">
        <div class="page-header">
          <h2>Dashboard & BLE Room Radar</h2>
          <p>Live device telemetry, active room controls, and multi-proxy Bluetooth RSSI triangulation.</p>
        </div>

        <div class="hero-stats">
          <div class="stat-box"><span>Active Room</span><strong id="st-room">--</strong></div>
          <div class="stat-box"><span>Room Climate</span><strong id="st-climate">--</strong></div>
          <div class="stat-box"><span>Active Speaker</span><strong id="st-speaker">--</strong></div>
          <div class="stat-box"><span>Home Security</span><strong id="st-alarm">--</strong></div>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Active Room & Speaker Context</h3>
            <p class="desc">Switch the active room or speaker, or tap any curated room entity below to toggle it.</p>
            <div class="field">
              <label>Active Room</label>
              <select id="quick-area" onchange="quickSwitchArea(this.value)"></select>
            </div>
            <div class="field">
              <label>Active Speaker</label>
              <select id="quick-speaker" onchange="quickSwitchSpeaker(this.value)"></select>
            </div>
            <label style="font-size:11.5px;font-weight:600;color:var(--muted);display:block;margin-top:12px;">Active Room Entities (<span id="st-card-count">0</span>)</label>
            <div id="live-room-cards" class="room-cards-grid"></div>
          </div>

          <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:4px;">
              <h3 style="margin:0;">BLE Site Survey & Room Calibration</h3>
              <label style="font-size:12px;font-weight:600;color:var(--accent);display:inline-flex;align-items:center;gap:6px;cursor:pointer;">
                <input type="checkbox" id="survey-fast-mode" onchange="toggleSurveyFastMode(this.checked)"> Live Walk-Around Mode (1.5s)
              </label>
            </div>
            <p class="desc">Walk from room to room with your device to compare live <strong>Raw dBm</strong> vs. <strong>Calibrated Effective dBm</strong>. Tap <strong>Prioritize Here</strong> while standing in a room to auto-calculate the exact dB bias needed to win over competing proxies, or fine-tune with <code>-1</code> / <code>+1</code> dB.</p>

            <div id="rssi-container" style="margin-bottom:14px;"></div>

            <div id="embedded-room-ble" class="native-controls-box" style="margin-bottom:12px;"></div>

            <div class="toggle-row">
              <span>Built-In ESPHome BLE Proxy Tracking</span>
              <input type="checkbox" id="cfg-native_ble_tracking" onchange="markDirty()">
            </div>
            <div class="toggle-row">
              <span>Auto-Switch Active Room on Movement</span>
              <input type="checkbox" id="cfg-ble_auto_switch" onchange="markDirty()">
            </div>
          </div>
        </div>
      </section>

      <!-- 2. HOME, DISPLAY, SLEEP & WALLPAPERS -->
      <section id="view-home_display" class="hidden">
        <div class="page-header">
          <h2>Home Screen, Display, Sleep & Wallpapers</h2>
          <p>Cohesive control over your device's clock face, brightness, themes, sleep/wake behavior, and wallpapers.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Home Screen & Dock Layout</h3>
            <p class="desc">Configure your device's clock style, home shortcuts, weather backdrop, and dock app order.</p>
            <div id="embedded-home" class="native-controls-box" style="margin-bottom:14px;"></div>
            <div class="field" style="margin-bottom:0;">
              <label>Home Dock App Order (comma-separated tokens)</label>
              <input type="text" id="cfg-dock_apps" placeholder="music,room,remote,games,tools" oninput="markDirty()">
            </div>
          </div>

          <div class="card">
            <h3>Display & Sleep / Wake Behavior</h3>
            <p class="desc">Adjust screen brightness, UI color profile, inactivity timeouts, and wake gestures.</p>
            <div id="embedded-display" class="native-controls-box" style="margin-bottom:10px;"></div>
            <div id="embedded-sleep" class="native-controls-box"></div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Upload New Photo Wallpaper</h3>
            <p class="desc">Photos are automatically center-cropped, darkened for legibility, and transcoded to Baseline JPEG.</p>
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
              <input type="file" id="wp-file-input" accept="image/*" style="flex:1;">
              <button class="btn-primary" onclick="uploadWallpaperFile()">Upload & Use</button>
            </div>
            <div class="field" style="margin-top:14px;margin-bottom:0;">
              <label>Active Wallpaper Source (/local/... or preset:...)</label>
              <div style="display:flex;gap:8px;">
                <input type="text" id="cfg-wallpaper_source" placeholder="preset:amoled_rings or /local/wallpaper.jpg" oninput="markDirty()">
                <button class="btn-secondary" onclick="selectWallpaperSource('')">Clear</button>
              </div>
            </div>
          </div>

          <div class="card">
            <h3>Wallpaper Rotation & Screen Geometry</h3>
            <p class="desc">Star multiple wallpapers below to rotate through favorites automatically.</p>
            <div class="field">
              <label>Rotate Favorite Wallpapers</label>
              <select id="cfg-wallpaper_cycle_minutes" onchange="markDirty()">
                <option value="0">Off (Keep Selected Wallpaper)</option>
                <option value="15">Every 15 Minutes</option>
                <option value="60">Every Hour</option>
                <option value="360">Every 6 Hours</option>
                <option value="1440">Every 24 Hours</option>
              </select>
            </div>
            <div class="field" style="margin-bottom:0;">
              <label>Screen Bezel Mask & Resolution</label>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <select id="cfg-display_shape" onchange="markDirty()">
                  <option value="circle">Circular Display</option>
                  <option value="square">Square / Rectangular</option>
                </select>
                <select id="cfg-art_size" onchange="markDirty()">
                  <option value="466">466x466 px</option>
                  <option value="360">360x360 px</option>
                  <option value="240">240x240 px</option>
                  <option value="480">480x480 px</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <h3>Wallpaper Gallery (AMOLED Low-Power Presets & Uploaded Photos)</h3>
          <p class="desc">AMOLED presets use &gt;80% pure black pixels to maximize battery life.</p>
          <div id="wp-gallery-grid" class="wp-gallery"></div>
        </div>
      </section>

      <!-- 3. VOICE ASSISTANT -->
      <section id="view-voice" class="hidden">
        <div class="page-header">
          <h2>Voice Assistant & Room-Aware Context</h2>
          <p>Configure on-device wake words, microphone hardware controls, and automatic room context synchronization for Home Assistant Assist.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Wake Word, Microphone & Sensitivity</h3>
            <p class="desc">Live hardware controls exposed by your ESPHome device's voice pipeline.</p>
            <div id="embedded-voice" class="native-controls-box"></div>
          </div>

          <div class="card">
            <h3>Room-Aware Voice Assistant Sync</h3>
            <p class="desc">When enabled, Latter automatically updates your ESPHome device's Home Assistant Area assignment as you walk between rooms—so saying <em>"Turn on the lights"</em> targets the room you are currently standing in.</p>
            <div class="toggle-row">
              <span>Sync Active Room to HA Device Area (Room-Aware Assist)</span>
              <input type="checkbox" id="cfg-sync_device_area" onchange="markDirty()">
            </div>
            <div class="field" style="margin-top:14px;margin-bottom:0;">
              <label>Default Fallback Room (When BLE Tracking Is Off)</label>
              <select id="cfg-default_area" onchange="markDirty()"></select>
            </div>
          </div>
        </div>
      </section>

      <!-- 4. AUDIO, MUSIC & SOUND -->
      <section id="view-audio" class="hidden">
        <div class="page-header">
          <h2>Audio, Music Assistant & On-Device Sound</h2>
          <p>Unified control over Music Assistant speakers, AVR volume overrides, library sorting, and onboard speaker chimes.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>On-Device Sound & Music Sorting</h3>
            <p class="desc">Adjust onboard alert volume, chimes, volume step increments, and Music Assistant browse sort order.</p>
            <div id="embedded-sound" class="native-controls-box" style="margin-bottom:10px;"></div>
            <div id="embedded-music" class="native-controls-box"></div>
          </div>

          <div class="card">
            <h3>Default Speaker & AVR Volume Overrides</h3>
            <p class="desc">Route volume commands to an external AV Receiver or amplifier when streaming to a mapped Music Assistant player.</p>
            <div class="field">
              <label>Default Speaker Entity</label>
              <select id="cfg-default_speaker" onchange="markDirty()"></select>
            </div>
            <div class="toggle-row" style="margin-bottom:12px;">
              <span>Unified Area Handoff (Auto-link Room Speaker & Remote)</span>
              <input type="checkbox" id="cfg-area_handoff" onchange="markDirty()">
            </div>
            <div class="field">
              <label>Override 1: When Streaming to Speaker &rarr; Control Volume On</label>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <select id="cfg-vol_speaker_1" onchange="markDirty()"></select>
                <select id="cfg-vol_target_1" onchange="markDirty()"></select>
              </div>
            </div>
            <div class="field" style="margin-bottom:0;">
              <label>Override 2: When Streaming to Speaker &rarr; Control Volume On</label>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <select id="cfg-vol_speaker_2" onchange="markDirty()"></select>
                <select id="cfg-vol_target_2" onchange="markDirty()"></select>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 5. TV REMOTES, SECURITY & HOME -->
      <section id="view-remotes" class="hidden">
        <div class="page-header">
          <h2>4-Slot TV Remotes, Security, Doorbell Camera & Alerts</h2>
          <p>Assign each remote slot's Home Assistant entity and protocol profile in one place, plus configure your home alarm, doorbell camera peephole, weather, and notifications.</p>
        </div>

        <div class="card" style="margin-bottom:16px;">
          <h3>Unified 4-Slot TV / Media Remotes</h3>
          <p class="desc">Pick either the <code>remote.*</code> or <code>media_player.*</code> entity for each slot—Latter automatically pairs sibling entities and adapts navigation commands (Android TV, Apple TV, Roku, LG webOS, Denon/Marantz).</p>
          <div class="grid-2" style="margin-bottom:0;">
            <div class="remote-slot-card" id="rslot-card-1">
              <div class="remote-slot-hdr">
                <strong>Remote Slot 1</strong>
                <button class="btn-secondary" id="rslot-btn-1" onclick="activateRemoteSlot(1)">Set Active</button>
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>Target TV / Media Player Entity</label>
                <select id="cfg-remote_1" onchange="markDirty()"></select>
              </div>
              <div id="embedded-remote-slot-1" class="native-controls-box"></div>
            </div>

            <div class="remote-slot-card" id="rslot-card-2">
              <div class="remote-slot-hdr">
                <strong>Remote Slot 2</strong>
                <button class="btn-secondary" id="rslot-btn-2" onclick="activateRemoteSlot(2)">Set Active</button>
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>Target TV / Media Player Entity</label>
                <select id="cfg-remote_2" onchange="markDirty()"></select>
              </div>
              <div id="embedded-remote-slot-2" class="native-controls-box"></div>
            </div>

            <div class="remote-slot-card" id="rslot-card-3">
              <div class="remote-slot-hdr">
                <strong>Remote Slot 3</strong>
                <button class="btn-secondary" id="rslot-btn-3" onclick="activateRemoteSlot(3)">Set Active</button>
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>Target TV / Media Player Entity</label>
                <select id="cfg-remote_3" onchange="markDirty()"></select>
              </div>
              <div id="embedded-remote-slot-3" class="native-controls-box"></div>
            </div>

            <div class="remote-slot-card" id="rslot-card-4">
              <div class="remote-slot-hdr">
                <strong>Remote Slot 4</strong>
                <button class="btn-secondary" id="rslot-btn-4" onclick="activateRemoteSlot(4)">Set Active</button>
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>Target TV / Media Player Entity</label>
                <select id="cfg-remote_4" onchange="markDirty()"></select>
              </div>
              <div id="embedded-remote-slot-4" class="native-controls-box"></div>
            </div>
          </div>
          <div id="embedded-remote-general" class="native-controls-box" style="margin-top:12px;"></div>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Security Alarm, Doorbell Camera & Weather</h3>
            <div class="field">
              <label>Home Security Alarm (alarm_control_panel)</label>
              <select id="cfg-alarm_entity" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Primary Doorbell / Peephole Camera (camera.*)</label>
              <select id="cfg-camera_entity" onchange="markDirty(); renderCameraPreview(this.value);"></select>
            </div>
            <div id="cam-preview-box" style="display:none;align-items:center;gap:12px;margin-bottom:13px;padding:10px;background:var(--input-bg);border:1px solid var(--border);border-radius:8px;">
              <img id="cam-preview-img" class="wp-thumb circle" style="width:76px;height:76px;" alt="Camera Snapshot">
              <div style="flex:1;min-width:0;">
                <strong style="font-size:12.5px;color:var(--text-strong);display:block;">Live Baseline-JPEG Transcoder Preview</strong>
                <small style="color:var(--muted);display:block;margin:2px 0 6px;">Served via <code>/api/latter/camera/&lt;slug&gt;</code></small>
                <button class="btn-secondary" style="padding:5px 10px;font-size:11.5px;" onclick="renderCameraPreview(document.getElementById('cfg-camera_entity').value)">Refresh Snapshot</button>
              </div>
            </div>
            <div class="field" style="margin-bottom:0;">
              <label>Weather Forecast Provider</label>
              <select id="cfg-weather_entity" onchange="markDirty()"></select>
            </div>
          </div>

          <div class="card">
            <h3>Pinned Entities & Smart Notification Dispatcher</h3>
            <p class="desc">Pin entities to the top of Room Control, or test dispatching an on-screen toast / doorbell peephole alert (<code>latter.notify_device</code>).</p>
            <div style="display:flex;gap:8px;margin-bottom:10px;">
              <select id="pin-entity-picker"></select>
              <button class="btn-secondary" onclick="addPinnedEntity()">Pin</button>
            </div>
            <div id="pinned-chips" class="chip-list" style="margin-bottom:14px;"></div>

            <div style="padding-top:12px;border-top:1px solid var(--border);">
              <label style="font-size:12px;font-weight:700;color:var(--text-strong);display:block;margin-bottom:6px;">Test Device Alert / Doorbell Popup (<code>latter.notify_device</code>)</label>
              <div style="display:grid;grid-template-columns:1fr 1.4fr auto;gap:8px;margin-bottom:8px;">
                <input type="text" id="test-alert-title" value="Front Door">
                <input type="text" id="test-alert-msg" value="Person detected at Front Door">
                <select id="test-alert-prio" style="width:auto;">
                  <option value="normal">Normal</option>
                  <option value="warning">Warning</option>
                  <option value="critical">Critical</option>
                </select>
              </div>
              <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;">
                <label style="font-size:12px;color:var(--muted);display:inline-flex;align-items:center;gap:6px;cursor:pointer;">
                  <input type="checkbox" id="test-alert-cam" checked> Include Camera Peephole Snapshot
                </label>
                <button class="btn-action" style="padding:7px 14px;font-size:12px;" onclick="sendTestNotification()">Send Alert to Device</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 6. SYSTEM, BATTERY, DIAGNOSTICS & HARDWARE TRIGGERS -->
      <section id="view-system" class="hidden">
        <div class="page-header">
          <h2>System Diagnostics, Power & Hardware Triggers</h2>
          <p>Execute device actions, monitor battery/network health, map custom hardware triggers, and export ESPHome YAML snippets.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Device Actions</h3>
            <p class="desc">One-tap hardware actions exposed by your ESPHome device.</p>
            <div id="embedded-actions" class="action-btn-grid" style="margin-bottom:14px;"></div>
            <h3>Battery & Power Telemetry</h3>
            <div id="embedded-battery" class="native-controls-box"></div>
          </div>

          <div class="card">
            <h3>Network & System Diagnostics</h3>
            <p class="desc">Live Wi-Fi signal, IP/MAC address, uptime, and firmware status.</p>
            <div id="embedded-network" class="native-controls-box"></div>
          </div>
        </div>

        <div class="card" style="margin-bottom:16px;">
          <h3>Universal Hardware Trigger & Macro Bindings</h3>
          <p class="desc">Map any custom slot ID sent by your firmware (<code>latter.trigger_binding</code>) to any Home Assistant entity.</p>
          <div id="bindings-list"></div>
          <button class="btn-secondary" onclick="addBindingRow('', '', 'toggle'); markDirty();">+ Add Trigger Binding</button>
        </div>

        <div class="card">
          <h3>Studio Appearance, Reverse Proxy & Device Profile</h3>
          <div class="grid-2" style="margin-bottom:0;">
            <div>
              <div class="field">
                <label>Studio Appearance (Dark / Light / System)</label>
                <select id="cfg-web_theme_mobile" onchange="onThemeChanged(this.value)">
                  <option value="dark">Dark</option>
                  <option value="light">Light</option>
                  <option value="system">System</option>
                </select>
              </div>
              <div class="field">
                <label>Companion HTTPS Base URL Override (e.g. https://ha.example.com)</label>
                <input type="text" id="cfg-companion_base_url" placeholder="Auto-detected from Home Assistant Network settings" oninput="markDirty()">
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>ESPHome Device Slug (sensor.&lt;slug&gt;_*)</label>
                <input type="text" id="cfg-device_slug" oninput="markDirty(); renderYamlGenerator();">
              </div>
            </div>
            <div>
              <div class="field">
                <label>Device Archetype & Room Cards Per Page</label>
                <div style="display:grid;grid-template-columns:2fr 1fr;gap:8px;">
                  <select id="cfg-device_profile" onchange="markDirty()">
                    <option value="mobile_display">Mobile Smart Display</option>
                    <option value="stationary_display">Stationary Wall / Desk Display</option>
                    <option value="headless_node">Headless Sensor / Button Node</option>
                  </select>
                  <input type="number" id="cfg-default_page_size" min="1" max="20" value="3" oninput="markDirty(); renderYamlGenerator();">
                </div>
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>BLE iBeacon UUID & External Sensor Override</label>
                <input type="text" id="cfg-ble_beacon_uuid" style="margin-bottom:6px;" oninput="markDirty(); renderYamlGenerator();">
                <select id="cfg-presence_entity" onchange="markDirty()"></select>
              </div>
            </div>
          </div>
        </div>

        <div class="card" style="margin-top:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:8px;">
            <div>
              <h3 style="margin:0;">ESPHome YAML Integration Generator</h3>
              <p class="desc" style="margin:4px 0 0;">Generate a modular, copy-pasteable ESPHome YAML contract tailored to this device's slug and slot capacity.</p>
            </div>
            <button class="btn-action" onclick="copyGeneratedYaml()">Copy YAML Snippet</button>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:14px;margin-bottom:12px;padding:10px 12px;background:var(--input-bg);border:1px solid var(--border);border-radius:7px;font-size:12.5px;">
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;"><input type="checkbox" id="yg-sensors" checked onchange="renderYamlGenerator()"> Push Sensors (<code>sensor.&lt;slug&gt;_*</code>)</label>
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;"><input type="checkbox" id="yg-browse" checked onchange="renderYamlGenerator()"> 5-Slot List Callback (<code>set_browse_slots</code>)</label>
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;"><input type="checkbox" id="yg-room" checked onchange="renderYamlGenerator()"> Room Slider Callback (<code>set_room_slots</code>)</label>
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;"><input type="checkbox" id="yg-ble" checked onchange="renderYamlGenerator()"> BLE Presence Beacon</label>
            <label style="display:flex;align-items:center;gap:6px;cursor:pointer;"><input type="checkbox" id="yg-actions" checked onchange="renderYamlGenerator()"> Action Examples (<code>latter.*</code>)</label>
          </div>
          <pre id="yaml-gen-output" class="mono" style="background:var(--input-bg);border:1px solid var(--border);border-radius:7px;padding:14px;overflow-x:auto;max-height:380px;margin:0;color:var(--text-strong);line-height:1.45;"></pre>
        </div>
      </section>

      <!-- 7. ALL ENTITIES (RAW POWER-USER INSPECTOR) -->
      <section id="view-raw" class="hidden">
        <div class="page-header">
          <h2>All Device Entities (Raw Inspector)</h2>
          <p>Search and inspect every raw entity registered to this ESPHome device in Home Assistant.</p>
        </div>
        <div class="card" style="margin-bottom:14px;padding:11px 14px;">
          <input type="text" id="esp-search" placeholder="Filter all device entities by name or entity_id..." oninput="renderRawEntityList()">
        </div>
        <div class="card">
          <div id="raw-entity-items" class="native-controls-box"></div>
        </div>
      </section>
    </div>
  </div>
</div>

<div id="toast" class="toast">Saved</div>

<script>
const API_URL = window.location.pathname + "/api" + window.location.search;
let STATE = null;
let PINNED = [];
let IS_DIRTY = false;
let INITIAL_FORM_LOADED = false;
let CURRENT_THEME_PREF = localStorage.getItem("latter_web_theme") || "dark";
let POLL_TIMER = null;

const sysMedia = window.matchMedia("(prefers-color-scheme: dark)");
sysMedia.addEventListener("change", () => {
  if (CURRENT_THEME_PREF === "system") applyTheme("system");
});

function resolveEffectiveTheme(pref) {
  if (pref === "system") return sysMedia.matches ? "dark" : "light";
  return pref === "light" ? "light" : "dark";
}

function applyTheme(pref) {
  const valid = ["dark", "light", "system"];
  CURRENT_THEME_PREF = valid.includes(pref) ? pref : "dark";
  document.body.setAttribute("data-theme", resolveEffectiveTheme(CURRENT_THEME_PREF));
  localStorage.setItem("latter_web_theme", CURRENT_THEME_PREF);
  ["cfg-web_theme", "cfg-web_theme_mobile"].forEach(id => {
    const sel = document.getElementById(id);
    if (sel && sel.value !== CURRENT_THEME_PREF) sel.value = CURRENT_THEME_PREF;
  });
}

applyTheme(CURRENT_THEME_PREF);

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.style.display = "block";
  setTimeout(() => { t.style.display = "none"; }, 2400);
}

function markDirty() {
  IS_DIRTY = true;
  document.getElementById("dirty-indicator").classList.add("visible");
}

function clearDirty() {
  IS_DIRTY = false;
  document.getElementById("dirty-indicator").classList.remove("visible");
}

async function onThemeChanged(themePref) {
  applyTheme(themePref);
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "set_theme", web_theme: themePref})
  });
  if (resp.ok) showToast(`Appearance set to ${themePref}`);
}

function switchView(viewId, btnEl) {
  document.querySelectorAll("aside .nav-btn").forEach(b => b.classList.remove("active"));
  btnEl.classList.add("active");
  ["dashboard", "home_display", "voice", "audio", "remotes", "system", "raw"].forEach(id => {
    const el = document.getElementById("view-" + id);
    if (el) el.classList.toggle("hidden", id !== viewId);
  });
}

function populateSelect(selId, items, selectedVal, allowEmpty=true) {
  const sel = document.getElementById(selId);
  if (!sel) return;
  sel.innerHTML = "";
  if (allowEmpty) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "— None / Auto —";
    sel.appendChild(opt);
  }
  (items || []).forEach(item => {
    const opt = document.createElement("option");
    opt.value = item.id;
    opt.textContent = item.name;
    if (item.id === selectedVal) opt.selected = true;
    sel.appendChild(opt);
  });
}

function toggleSurveyFastMode(enabled) {
  if (POLL_TIMER) clearInterval(POLL_TIMER);
  const intervalMs = enabled ? 1500 : 5000;
  POLL_TIMER = setInterval(() => refreshState(false), intervalMs);
  if (enabled) refreshState(false);
}

function renderRssiBars(surveyRows, packetsSeen) {
  const box = document.getElementById("rssi-container");
  if (!box) return;
  const rows = surveyRows || [];
  if (!rows.length) {
    box.innerHTML = `<p class="desc">No Bluetooth proxies discovered yet (Packets seen: ${packetsSeen || 0}).</p>`;
    return;
  }
  box.innerHTML = rows.map(r => {
    const hasSignal = r.raw_rssi !== null && r.raw_rssi !== undefined;
    const eff = hasSignal ? r.effective_rssi : -100;
    const pct = hasSignal ? Math.max(6, Math.min(100, Math.round(((eff + 100) / 55) * 100))) : 0;
    const offSign = r.offset_db > 0 ? `+${r.offset_db}` : `${r.offset_db}`;
    const ageText = hasSignal ? `${r.age_seconds}s ago` : "No signal yet";
    const sigText = hasSignal
      ? `Raw: <strong>${r.raw_rssi} dBm</strong> &bull; Bias: <strong>${offSign} dB</strong> &rarr; Effective: <strong style="color:var(--accent);">${r.effective_rssi} dBm</strong>`
      : `Bias: <strong>${offSign} dB</strong> &bull; Waiting for beacon packet...`;
    const winBadge = r.is_winner
      ? `<span class="state-badge" style="border-color:var(--success);color:var(--success);margin-left:6px;">ACTIVE WINNER</span>`
      : "";

    return `<div style="background:var(--input-bg);border:1px solid ${r.is_winner ? 'var(--accent)' : 'var(--border)'};border-radius:8px;padding:10px 12px;margin-bottom:8px;">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:5px;">
        <div>
          <strong style="color:var(--text-strong);font-size:13.5px;">${r.area_name}</strong>
          <small style="color:var(--muted);margin-left:6px;">(${r.scanner} &bull; ${ageText})</small>
          ${winBadge}
        </div>
        <div style="display:flex;align-items:center;gap:4px;">
          <button class="btn-secondary" style="padding:4px 8px;font-size:11.5px;" onclick="setBleOffset('${r.area_id}', ${Number(r.offset_db) - 1})">-1 dB</button>
          <span class="state-badge" style="min-width:52px;text-align:center;">${offSign} dB</span>
          <button class="btn-secondary" style="padding:4px 8px;font-size:11.5px;" onclick="setBleOffset('${r.area_id}', ${Number(r.offset_db) + 1})">+1 dB</button>
          ${r.offset_db !== 0 ? `<button class="btn-danger" style="padding:4px 7px;font-size:11px;" title="Reset to 0 dB" onclick="setBleOffset('${r.area_id}', 0)">0</button>` : ''}
          <button class="btn-action" style="padding:4px 10px;font-size:11.5px;margin-left:4px;" title="Auto-calculate dB offset so this room wins at your current spot" onclick="autoCalibrateHere('${r.area_id}')">Prioritize Here</button>
        </div>
      </div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:6px;">${sigText}</div>
      <div class="rssi-track"><div class="rssi-fill" style="width:${pct}%;opacity:${hasSignal ? 1 : 0.2};"></div></div>
    </div>`;
  }).join("");
}

async function setBleOffset(areaId, offsetDb) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "set_ble_room_offset", area_id: areaId, offset_db: offsetDb})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("BLE calibration updated");
  }
}

async function autoCalibrateHere(areaId) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "auto_calibrate_here", area_id: areaId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("Calibrated & prioritized current room!");
  }
}

function renderCameraPreview(camEntityId) {
  const box = document.getElementById("cam-preview-box");
  const img = document.getElementById("cam-preview-img");
  if (!box || !img) return;
  if (!camEntityId) {
    box.style.display = "none";
    return;
  }
  const slug = STATE?.config?.device_slug || "esphome_device";
  const shape = STATE?.config?.display_shape === "square" ? "square" : "circle";
  img.className = `wp-thumb ${shape}`;
  img.src = `/api/latter/camera/${slug}?entity_id=${encodeURIComponent(camEntityId)}&w=240&h=240&shape=${shape}&v=${Date.now()}`;
  box.style.display = "flex";
}

async function sendTestNotification() {
  const title = document.getElementById("test-alert-title").value.trim() || "Alert";
  const message = document.getElementById("test-alert-msg").value.trim() || "Test notification";
  const priority = document.getElementById("test-alert-prio").value;
  const include_camera = document.getElementById("test-alert-cam").checked;
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      command: "send_test_notification",
      title,
      message,
      priority,
      include_camera
    })
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("Dispatched notification to device");
  }
}

function renderLiveRoomCards(cards) {
  const box = document.getElementById("live-room-cards");
  document.getElementById("st-card-count").textContent = (cards || []).length;
  if (!cards || !cards.length) {
    box.innerHTML = `<p class="desc">No curated entities found in this area.</p>`;
    return;
  }
  box.innerHTML = cards.map(c => `
    <div class="room-mini-card ${c.active ? 'on' : ''}" onclick="toggleRoomCard('${c.id}')">
      <div>
        <strong>${c.name}</strong>
        <small>${c.type}</small>
      </div>
      <span class="state-badge">${c.active ? 'ON' : 'OFF'}</span>
    </div>
  `).join("");
}

async function toggleRoomCard(entity_id) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "room_card_action", entity_id, action: "toggle"})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast(`Toggled ${entity_id}`);
  }
}

function renderNativeControlRow(item, showEntityId=false) {
  const stateText = `${item.state}${item.unit ? ' ' + item.unit : ''}`;
  let widgetHtml = `<span class="state-badge">${stateText}</span>`;

  if (item.domain === "button") {
    widgetHtml = `<button class="btn-secondary" onclick="espAction('${item.entity_id}', 'press')">Run</button>`;
  } else if (item.domain === "switch" || item.domain === "light" || item.domain === "fan") {
    const isOn = item.state === "on";
    widgetHtml = `<button class="${isOn ? 'btn-primary' : 'btn-secondary'}" onclick="espAction('${item.entity_id}', 'toggle')">${isOn ? 'ON' : 'OFF'}</button>`;
  } else if (item.domain === "select" && item.options && item.options.length) {
    const opts = item.options.map(o => `<option value="${o}" ${o===item.state?'selected':''}>${o}</option>`).join("");
    widgetHtml = `<select onchange="espSelect('${item.entity_id}', this.value)">${opts}</select>`;
  } else if (item.domain === "number") {
    const minV = item.min ?? 0;
    const maxV = item.max ?? 100;
    const stepV = item.step ?? 1;
    const numVal = parseFloat(item.state) || 0;
    widgetHtml = `
      <input type="range" min="${minV}" max="${maxV}" step="${stepV}" value="${numVal}" onchange="espNumber('${item.entity_id}', this.value)">
      <span class="state-badge">${stateText}</span>
    `;
  }

  return `<div class="native-ctrl-row">
    <div class="lbl">
      ${item.name}
      ${showEntityId ? `<small>${item.entity_id}</small>` : ''}
    </div>
    <div class="widget">${widgetHtml}</div>
  </div>`;
}

function getSectionItems(secId) {
  const sections = STATE?.esphome?.sections || [];
  const found = sections.find(s => s.id === secId);
  return found ? (found.items || []) : [];
}

function renderCohesiveDeviceSections() {
  const esp = STATE?.esphome;
  if (!esp) return;
  const sections = esp.sections || [];
  const totalCount = sections.reduce((acc, s) => acc + s.count, 0);
  document.getElementById("nav-esp-badge").textContent = totalCount;

  const roomItems = getSectionItems("room");
  document.getElementById("embedded-room-ble").innerHTML = roomItems.map(it => renderNativeControlRow(it)).join("");

  const homeItems = getSectionItems("home");
  document.getElementById("embedded-home").innerHTML = homeItems.length
    ? homeItems.map(it => renderNativeControlRow(it)).join("")
    : `<p class="desc">No on-device Home Screen entities exposed.</p>`;

  const dispItems = getSectionItems("display");
  document.getElementById("embedded-display").innerHTML = dispItems.map(it => renderNativeControlRow(it)).join("");

  const sleepItems = getSectionItems("sleep");
  document.getElementById("embedded-sleep").innerHTML = sleepItems.map(it => renderNativeControlRow(it)).join("");

  const voiceItems = getSectionItems("voice");
  document.getElementById("embedded-voice").innerHTML = voiceItems.length
    ? voiceItems.map(it => renderNativeControlRow(it)).join("")
    : `<p class="desc">No on-device Voice Assistant entities exposed by this firmware.</p>`;

  const soundItems = getSectionItems("sound");
  document.getElementById("embedded-sound").innerHTML = soundItems.map(it => renderNativeControlRow(it)).join("");
  const musicItems = getSectionItems("music");
  document.getElementById("embedded-music").innerHTML = musicItems.map(it => renderNativeControlRow(it)).join("");

  const remoteItems = getSectionItems("remote");
  const slotBuckets = {1: [], 2: [], 3: [], 4: [], general: []};
  remoteItems.forEach(it => {
    const txt = `${it.name} ${it.entity_id}`.toLowerCase();
    if (txt.includes("slot 1") || txt.includes("slot_1") || txt.includes("remote 1") || txt.includes("remote_1")) slotBuckets[1].push(it);
    else if (txt.includes("slot 2") || txt.includes("slot_2") || txt.includes("remote 2") || txt.includes("remote_2")) slotBuckets[2].push(it);
    else if (txt.includes("slot 3") || txt.includes("slot_3") || txt.includes("remote 3") || txt.includes("remote_3")) slotBuckets[3].push(it);
    else if (txt.includes("slot 4") || txt.includes("slot_4") || txt.includes("remote 4") || txt.includes("remote_4")) slotBuckets[4].push(it);
    else slotBuckets.general.push(it);
  });
  [1, 2, 3, 4].forEach(idx => {
    const box = document.getElementById(`embedded-remote-slot-${idx}`);
    if (box) box.innerHTML = slotBuckets[idx].map(it => renderNativeControlRow(it)).join("");
  });
  document.getElementById("embedded-remote-general").innerHTML = slotBuckets.general.map(it => renderNativeControlRow(it)).join("");

  const actionItems = getSectionItems("actions");
  document.getElementById("embedded-actions").innerHTML = actionItems.map(it =>
    `<button class="btn-action" onclick="espAction('${it.entity_id}', 'press')">${it.name}</button>`
  ).join("");

  const batItems = getSectionItems("battery");
  document.getElementById("embedded-battery").innerHTML = batItems.map(it => renderNativeControlRow(it)).join("");

  const netItems = getSectionItems("network").concat(getSectionItems("other"));
  document.getElementById("embedded-network").innerHTML = netItems.length
    ? netItems.map(it => renderNativeControlRow(it)).join("")
    : `<p class="desc">No network or diagnostic entities reported.</p>`;

  renderRawEntityList();
}

function renderRawEntityList() {
  const esp = STATE?.esphome;
  if (!esp || !esp.sections) return;
  const query = (document.getElementById("esp-search")?.value || "").trim().toLowerCase();
  let allItems = [];
  esp.sections.forEach(s => { allItems = allItems.concat(s.items || []); });
  if (query) {
    allItems = allItems.filter(it =>
      it.name.toLowerCase().includes(query) || it.entity_id.toLowerCase().includes(query)
    );
  }
  const box = document.getElementById("raw-entity-items");
  if (box) {
    box.innerHTML = allItems.map(it => renderNativeControlRow(it, true)).join("");
  }
}

async function activateRemoteSlot(slotNum) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "activate_remote_slot", slot: slotNum})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast(`Active remote set to Slot ${slotNum}`);
  }
}

function renderWallpaperGallery(wallpapers, slug, shape) {
  const box = document.getElementById("wp-gallery-grid");
  if (!box) return;
  const shapeClass = shape === "square" ? "square" : "circle";
  box.innerHTML = (wallpapers || []).map(wp => {
    const encSrc = encodeURIComponent(wp.id);
    const thumbUrl = `/api/latter/wallpaper/${slug}?w=240&h=240&shape=${shapeClass}&src=${encSrc}`;
    const starLabel = wp.favorite ? "★ Fav" : "☆ Fav";
    const delBtn = wp.deletable
      ? `<button class="btn-danger" onclick="deleteWallpaper('${wp.id}')">✕</button>`
      : "";
    return `<div class="wp-card ${wp.active ? 'active' : ''}">
      <img class="wp-thumb ${shapeClass}" src="${thumbUrl}" loading="lazy" alt="${wp.name}">
      <div class="wp-title">${wp.name}</div>
      <div class="wp-actions">
        <button class="${wp.active ? 'btn-primary' : 'btn-secondary'}" onclick="selectWallpaperSource('${wp.id}')">${wp.active ? 'Active' : 'Use'}</button>
        <button class="${wp.favorite ? 'btn-primary' : 'btn-secondary'}" onclick="toggleWallpaperFav('${wp.id}')">${starLabel}</button>
        ${delBtn}
      </div>
    </div>`;
  }).join("");
}

async function uploadWallpaperFile() {
  const input = document.getElementById("wp-file-input");
  if (!input.files || !input.files.length) {
    showToast("Select an image file first");
    return;
  }
  const file = input.files[0];
  const reader = new FileReader();
  reader.onload = async () => {
    const resp = await fetch(API_URL, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        command: "upload_wallpaper",
        filename: file.name,
        data_b64: reader.result
      })
    });
    if (resp.ok) {
      input.value = "";
      applyStateToDom(await resp.json(), true);
      showToast("Wallpaper uploaded & activated");
    }
  };
  reader.readAsDataURL(file);
}

async function selectWallpaperSource(sourceId) {
  document.getElementById("cfg-wallpaper_source").value = sourceId;
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "select_wallpaper", source_id: sourceId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast(sourceId ? "Wallpaper activated" : "Wallpaper disabled");
  }
}

async function toggleWallpaperFav(sourceId) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "toggle_wallpaper_favorite", source_id: sourceId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("Updated wallpaper favorites");
  }
}

async function deleteWallpaper(sourceId) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "delete_wallpaper", source_id: sourceId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("Deleted wallpaper");
  }
}

async function espAction(entity_id, action) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "esphome_entity_action", entity_id, action})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast(`${action.toUpperCase()}: ${entity_id}`);
  }
}

async function espSelect(entity_id, option) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "esphome_entity_action", entity_id, option})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast(`Selected ${option}`);
  }
}

async function espNumber(entity_id, level) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "esphome_entity_action", entity_id, level})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast(`Updated ${entity_id} = ${level}`);
  }
}

function renderPinnedChips() {
  const box = document.getElementById("pinned-chips");
  box.innerHTML = PINNED.map((ent, idx) =>
    `<div class="chip"><span>${ent}</span><b onclick="removePinned(${idx})">✕</b></div>`
  ).join("");
}

function addPinnedEntity() {
  const val = document.getElementById("pin-entity-picker").value;
  if (val && !PINNED.includes(val)) {
    PINNED.push(val);
    renderPinnedChips();
    markDirty();
  }
}

function removePinned(idx) {
  PINNED.splice(idx, 1);
  renderPinnedChips();
  markDirty();
}

function addBindingRow(slot="", entity_id="", action="toggle") {
  const list = document.getElementById("bindings-list");
  const row = document.createElement("div");
  row.className = "binding-row";
  const entOptions = (STATE?.catalog?.bindable_entities || []).map(e =>
    `<option value="${e.id}" ${e.id === entity_id ? 'selected' : ''}>${e.name}</option>`
  ).join("");
  row.innerHTML = `
    <input type="text" class="b-slot" placeholder="Slot ID (e.g. button_1)" value="${slot}" oninput="markDirty()">
    <select class="b-ent" onchange="markDirty()"><option value="">— Target Entity —</option>${entOptions}</select>
    <select class="b-act" onchange="markDirty()">
      <option value="toggle" ${action==='toggle'?'selected':''}>Toggle</option>
      <option value="turn_on" ${action==='turn_on'?'selected':''}>Turn On</option>
      <option value="turn_off" ${action==='turn_off'?'selected':''}>Turn Off</option>
      <option value="step_up" ${action==='step_up'?'selected':''}>Step Up (+10%)</option>
      <option value="step_down" ${action==='step_down'?'selected':''}>Step Down (-10%)</option>
    </select>
    <button class="btn-secondary" onclick="testBindingRow(this)">Test</button>
    <button class="btn-danger" onclick="this.parentElement.remove(); markDirty();">✕</button>
  `;
  list.appendChild(row);
}

async function testBindingRow(btn) {
  const row = btn.parentElement;
  const entity_id = row.querySelector(".b-ent").value;
  const action = row.querySelector(".b-act").value;
  if (!entity_id) return;
  await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "test_binding", entity_id, action})
  });
  showToast("Triggered " + action + " on " + entity_id);
}

function renderYamlGenerator() {
  const box = document.getElementById("yaml-gen-output");
  if (!box) return;
  const slug = (document.getElementById("cfg-device_slug")?.value || STATE?.config?.device_slug || "esphome_device").trim().toLowerCase().replace(/-/g, "_");
  const nodeHyphen = slug.replace(/_/g, "-");
  const roomSlots = Math.max(1, Math.min(20, parseInt(document.getElementById("cfg-default_page_size")?.value || STATE?.config?.default_page_size || 3, 10)));
  const uuid = (document.getElementById("cfg-ble_beacon_uuid")?.value || STATE?.config?.ble_beacon_uuid || "504F434B-4554-4153-5354-000000000210").trim();

  const incSensors = document.getElementById("yg-sensors")?.checked;
  const incBrowse = document.getElementById("yg-browse")?.checked;
  const incRoom = document.getElementById("yg-room")?.checked;
  const incBle = document.getElementById("yg-ble")?.checked;
  const incActions = document.getElementById("yg-actions")?.checked;

  const lines = [
    `# Latter v1.6+ ESPHome Companion Wire Snippet for '${nodeHyphen}' (slug: ${slug})`,
    `esphome:`,
    `  name: ${nodeHyphen}`,
    ``
  ];

  if (incBrowse || incRoom) {
    lines.push(`api:`);
    lines.push(`  actions:`);
    if (incBrowse) {
      lines.push(`    # 5-Slot List Callback (Music, Room Picker 'room_areas', Calendar)`);
      lines.push(`    - action: set_browse_slots`);
      lines.push(`      variables:`);
      lines.push(`        mode: string`);
      lines.push(`        page: int`);
      lines.push(`        total_pages: int`);
      lines.push(`        has_prev: bool`);
      lines.push(`        has_next: bool`);
      for (let i = 1; i <= 5; i++) {
        lines.push(`        s${i}_name: string`);
        lines.push(`        s${i}_id: string`);
        lines.push(`        s${i}_type: string`);
        lines.push(`        s${i}_active: bool`);
      }
    }
    if (incRoom) {
      lines.push(`    # ${roomSlots}-Slot Interactive Room Control Callback (includes sX_level 0..100 or -1)`);
      lines.push(`    - action: set_room_slots`);
      lines.push(`      variables:`);
      lines.push(`        mode: string`);
      lines.push(`        page: int`);
      lines.push(`        total_pages: int`);
      lines.push(`        has_prev: bool`);
      lines.push(`        has_next: bool`);
      for (let i = 1; i <= roomSlots; i++) {
        lines.push(`        s${i}_name: string`);
        lines.push(`        s${i}_id: string`);
        lines.push(`        s${i}_type: string`);
        lines.push(`        s${i}_active: bool`);
        lines.push(`        s${i}_level: int`);
      }
    }
    lines.push(``);
  }

  if (incSensors) {
    lines.push(`# Device-Scoped Latter Push Sensors`);
    lines.push(`text_sensor:`);
    lines.push(`  - platform: homeassistant`);
    lines.push(`    id: latter_active_media`);
    lines.push(`    entity_id: sensor.${slug}_active_media`);
    lines.push(`  - platform: homeassistant`);
    lines.push(`    id: latter_room_context`);
    lines.push(`    entity_id: sensor.${slug}_room_context`);
    lines.push(`  - platform: homeassistant`);
    lines.push(`    id: latter_weather_forecast`);
    lines.push(`    entity_id: sensor.${slug}_weather_forecast`);
    lines.push(`  - platform: homeassistant`);
    lines.push(`    id: latter_remote_config`);
    lines.push(`    entity_id: sensor.${slug}_remote_config`);
    lines.push(`  - platform: homeassistant`);
    lines.push(`    id: latter_calendar_agenda`);
    lines.push(`    entity_id: sensor.${slug}_calendar_agenda`);
    lines.push(``);
  }

  if (incBle) {
    lines.push(`# Zero-Config BLE Room Presence Beacon`);
    lines.push(`esp32_ble_beacon:`);
    lines.push(`  type: iBeacon`);
    lines.push(`  uuid: "${uuid}"`);
    lines.push(`  major: 1`);
    lines.push(`  minor: 1`);
    lines.push(``);
  }

  if (incActions) {
    lines.push(`# Example Outbound Latter Actions (use inside touch/button/rotary handlers)`);
    lines.push(`# - homeassistant.action:`);
    lines.push(`#     action: latter.room_browse`);
    lines.push(`#     data:`);
    lines.push(`#       device_slug: "${slug}"`);
    lines.push(`#       mode: "entities"`);
    lines.push(`#       domain_filter: "all"`);
    lines.push(`#       page: "1"`);
    lines.push(`# - homeassistant.action:`);
    lines.push(`#     action: latter.trigger_binding`);
    lines.push(`#     data:`);
    lines.push(`#       device_slug: "${slug}"`);
    lines.push(`#       slot: "button_1_single"`);
  }

  box.textContent = lines.join("\\n");
}

function copyGeneratedYaml() {
  const text = document.getElementById("yaml-gen-output")?.textContent || "";
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    showToast("Copied ESPHome YAML snippet to clipboard");
  });
}

function applyStateToDom(data, forceFormUpdate=false) {
  STATE = data;
  const cfg = data.config;
  const live = data.live;
  const cat = data.catalog;
  const esp = data.esphome;

  const roomName = live.active_area_name || "Home";
  const spkShort = (live.active_speaker || "").replace("media_player.", "");
  const tempStr = live.room_temp != null ? `${live.room_temp}°` : "--";
  const humStr = live.room_humidity != null ? ` • ${live.room_humidity}%` : "";

  document.getElementById("hdr-title").textContent = esp?.device?.name || data.title;
  document.getElementById("hdr-sub").textContent = `Latter v${data.version || '1.6.0'}`;
  document.getElementById("nav-room-badge").textContent = roomName;
  document.getElementById("top-room").textContent = `Room: ${roomName}`;
  document.getElementById("top-speaker").textContent = `Speaker: ${spkShort}`;
  document.getElementById("top-media").textContent = live.media_title && live.media_title !== "Idle"
    ? `${live.media_title} (${live.media_artist})`
    : `Media: ${live.media_state || 'idle'}`;

  document.getElementById("st-room").textContent = roomName;
  document.getElementById("st-climate").textContent = tempStr + humStr;
  document.getElementById("st-speaker").textContent = spkShort;
  document.getElementById("st-alarm").textContent = (live.alarm_state || "none").toUpperCase();

  [1, 2, 3, 4].forEach(idx => {
    const isAct = (live.active_remote_slot || 1) === idx;
    const card = document.getElementById(`rslot-card-${idx}`);
    const btn = document.getElementById(`rslot-btn-${idx}`);
    if (card) card.classList.toggle("active-slot", isAct);
    if (btn) {
      btn.textContent = isAct ? "Active on Device" : "Set Active";
      btn.className = isAct ? "btn-primary" : "btn-secondary";
    }
  });

  populateSelect("quick-area", cat.areas, live.active_area_id, false);
  populateSelect("quick-speaker", cat.ma_speakers, live.active_speaker, false);
  renderLiveRoomCards(live.room_cards);
  renderRssiBars(live.ble_survey_rows, live.ble_packets_seen);
  renderWallpaperGallery(data.wallpapers, cfg.device_slug, cfg.display_shape);

  const activeEl = document.activeElement;
  if (!activeEl || !["SELECT", "INPUT"].includes(activeEl.tagName)) {
    renderCohesiveDeviceSections();
  }

  if (!INITIAL_FORM_LOADED || forceFormUpdate) {
    INITIAL_FORM_LOADED = true;
    applyTheme(cfg.web_theme || "dark");
    renderCohesiveDeviceSections();

    document.getElementById("cfg-device_slug").value = cfg.device_slug || "";
    document.getElementById("cfg-companion_base_url").value = cfg.companion_base_url || "";
    document.getElementById("cfg-device_profile").value = cfg.device_profile || "mobile_display";
    document.getElementById("cfg-display_shape").value = cfg.display_shape || "circle";
    document.getElementById("cfg-default_page_size").value = cfg.default_page_size ?? 3;
    document.getElementById("cfg-native_ble_tracking").checked = !!cfg.native_ble_tracking;
    document.getElementById("cfg-ble_auto_switch").checked = !!cfg.ble_auto_switch;
    document.getElementById("cfg-sync_device_area").checked = !!cfg.sync_device_area;
    document.getElementById("cfg-area_handoff").checked = !!cfg.area_handoff;
    document.getElementById("cfg-ble_beacon_uuid").value = cfg.ble_beacon_uuid || "";
    document.getElementById("cfg-dock_apps").value = cfg.dock_apps || "";
    document.getElementById("cfg-wallpaper_source").value = cfg.wallpaper_source || "";
    document.getElementById("cfg-wallpaper_cycle_minutes").value = String(cfg.wallpaper_cycle_minutes || 0);
    document.getElementById("cfg-art_size").value = String(cfg.art_size || 466);

    populateSelect("cfg-default_area", cat.areas, cfg.default_area);
    populateSelect("cfg-presence_entity", cat.presence_sensors, cfg.presence_entity);
    populateSelect("cfg-default_speaker", cat.ma_speakers, cfg.default_speaker, false);
    populateSelect("cfg-vol_speaker_1", cat.ma_speakers, cfg.vol_speaker_1);
    populateSelect("cfg-vol_target_1", cat.volume_targets, cfg.vol_target_1);
    populateSelect("cfg-vol_speaker_2", cat.ma_speakers, cfg.vol_speaker_2);
    populateSelect("cfg-vol_target_2", cat.volume_targets, cfg.vol_target_2);
    populateSelect("cfg-remote_1", cat.remotes, cfg.remote_1);
    populateSelect("cfg-remote_2", cat.remotes, cfg.remote_2);
    populateSelect("cfg-remote_3", cat.remotes, cfg.remote_3);
    populateSelect("cfg-remote_4", cat.remotes, cfg.remote_4);
    populateSelect("cfg-alarm_entity", cat.alarms, cfg.alarm_entity);
    populateSelect("cfg-camera_entity", cat.cameras, cfg.camera_entity);
    renderCameraPreview(cfg.camera_entity);
    populateSelect("cfg-weather_entity", cat.weathers, cfg.weather_entity);
    populateSelect("pin-entity-picker", cat.bindable_entities, "", false);

    PINNED = Array.isArray(cfg.custom_entities) ? [...cfg.custom_entities] : [];
    renderPinnedChips();

    const bList = document.getElementById("bindings-list");
    bList.innerHTML = "";
    (cfg.custom_bindings || []).forEach(b => addBindingRow(b.slot, b.entity_id, b.action));
    renderYamlGenerator();
    clearDirty();
  }
}

async function refreshState(forceForm=false) {
  const resp = await fetch(API_URL);
  if (resp.ok) {
    const data = await resp.json();
    applyStateToDom(data, forceForm);
  }
}

async function quickSwitchArea(areaId) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "set_active_area", area_id: areaId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("Switched active room");
  }
}

async function quickSwitchSpeaker(speakerId) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "set_active_speaker", speaker: speakerId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("Switched active speaker");
  }
}

async function saveAllConfig() {
  const bindings = [];
  document.querySelectorAll("#bindings-list .binding-row").forEach(row => {
    const slot = row.querySelector(".b-slot").value.trim();
    const entity_id = row.querySelector(".b-ent").value.trim();
    const action = row.querySelector(".b-act").value.trim();
    if (slot && entity_id) bindings.push({slot, entity_id, action});
  });

  const config = {
    device_slug: document.getElementById("cfg-device_slug").value.trim(),
    companion_base_url: document.getElementById("cfg-companion_base_url").value.trim(),
    device_profile: document.getElementById("cfg-device_profile").value,
    display_shape: document.getElementById("cfg-display_shape").value,
    default_page_size: parseInt(document.getElementById("cfg-default_page_size").value, 10) || 3,
    web_theme: document.getElementById("cfg-web_theme").value,
    native_ble_tracking: document.getElementById("cfg-native_ble_tracking").checked,
    ble_auto_switch: document.getElementById("cfg-ble_auto_switch").checked,
    sync_device_area: document.getElementById("cfg-sync_device_area").checked,
    area_handoff: document.getElementById("cfg-area_handoff").checked,
    ble_beacon_uuid: document.getElementById("cfg-ble_beacon_uuid").value.trim(),
    presence_entity: document.getElementById("cfg-presence_entity").value,
    default_speaker: document.getElementById("cfg-default_speaker").value,
    vol_speaker_1: document.getElementById("cfg-vol_speaker_1").value,
    vol_target_1: document.getElementById("cfg-vol_target_1").value,
    vol_speaker_2: document.getElementById("cfg-vol_speaker_2").value,
    vol_target_2: document.getElementById("cfg-vol_target_2").value,
    remote_1: document.getElementById("cfg-remote_1").value,
    remote_2: document.getElementById("cfg-remote_2").value,
    remote_3: document.getElementById("cfg-remote_3").value,
    remote_4: document.getElementById("cfg-remote_4").value,
    alarm_entity: document.getElementById("cfg-alarm_entity").value,
    camera_entity: document.getElementById("cfg-camera_entity").value,
    weather_entity: document.getElementById("cfg-weather_entity").value,
    default_area: document.getElementById("cfg-default_area").value,
    dock_apps: document.getElementById("cfg-dock_apps").value.trim(),
    wallpaper_source: document.getElementById("cfg-wallpaper_source").value.trim(),
    wallpaper_cycle_minutes: parseInt(document.getElementById("cfg-wallpaper_cycle_minutes").value, 10) || 0,
    art_size: parseInt(document.getElementById("cfg-art_size").value, 10),
    custom_entities: PINNED,
    custom_bindings: bindings,
  };

  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "save_config", config})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), true);
    showToast("Configuration saved");
  }
}

refreshState(true);
toggleSurveyFastMode(false);
</script>
</body>
</html>
"""


class LatterCompanionDashboardView(HomeAssistantView):
    """Serves the Latter Server-Side Web Companion Studio HTML."""

    requires_auth = False
    url = API_COMPANION_UI_PATH
    name = "api:latter:companion_ui"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the Companion UI view."""
        self.hass = hass

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        """Serve the single-page Latter Companion Studio."""
        domain_data = self.hass.data.get(DOMAIN, {})
        coordinator: LatterCoordinator | None = domain_data.get(entry_id)
        if not isinstance(coordinator, LatterCoordinator):
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Unknown Latter entry")

        token = request.query.get("token")
        if not coordinator.verify_token(token):
            return web.Response(
                status=HTTPStatus.FORBIDDEN,
                text="Invalid or missing Latter companion token. Open via the 'Visit' link on the Latter or ESPHome device page in Home Assistant.",
            )

        return web.Response(
            body=COMPANION_HTML_TEMPLATE,
            content_type="text/html",
            charset="utf-8",
        )


class LatterBrandIconView(HomeAssistantView):
    """Serves the Latter brand icon (`custom_components/latter/brand/icon.png`) for the Web Companion Studio."""

    requires_auth = False
    url = API_BRAND_ICON_PATH
    name = "api:latter:brand_icon"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the brand icon view."""
        self.hass = hass
        self._icon_path = Path(__file__).parent / "brand" / "icon.png"

    async def get(self, request: web.Request) -> web.Response:
        """Serve icon.png with caching headers."""
        if not self._icon_path.is_file():
            return web.Response(status=HTTPStatus.NOT_FOUND)
        raw_bytes = await self.hass.async_add_executor_job(
            self._icon_path.read_bytes
        )
        return web.Response(
            body=raw_bytes,
            content_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )