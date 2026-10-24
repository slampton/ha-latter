"""Server-Side Web Companion Studio & REST API for Latter."""

from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Any

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar

from .browse_engine import is_music_assistant_player
from .const import (
    API_COMPANION_API_PATH,
    API_COMPANION_UI_PATH,
    CONF_ALARM_ENTITY,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_CALENDAR_ENTITIES,
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
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    CONF_WEB_THEME,
    DEFAULT_ART_SIZE,
    DEFAULT_DEVICE_PROFILE,
    DEFAULT_DISPLAY_SHAPE,
    DEFAULT_PAGE_SIZE,
    DEFAULT_WEB_THEME,
    DOMAIN,
    INTEGRATION_VERSION,
)
from .coordinator import LatterCoordinator
from .room_engine import (
    async_execute_room_action,
    get_area_entities,
    get_esphome_device_entities,
)

_LOGGER = logging.getLogger(__name__)

VALID_WEB_THEMES: set[str] = {"amoled_midnight", "daylight_clean", "cyber_cyan"}


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
    weathers_list: list[dict[str, str]] = []
    calendars_list: list[dict[str, str]] = []
    presence_sensors: list[dict[str, str]] = []
    bindable_entities: list[dict[str, str]] = []

    for state_obj in sorted(
        hass.states.async_all(), key=lambda s: s.entity_id
    ):
        if state_obj.state in ("unavailable",):
            continue
        ent_id = state_obj.entity_id
        domain = state_obj.domain
        friendly = str(state_obj.attributes.get("friendly_name") or ent_id)
        item = {"id": ent_id, "name": f"{friendly} ({ent_id})", "domain": domain}

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

    saved_theme = str(
        coordinator.get_opt(CONF_WEB_THEME, DEFAULT_WEB_THEME)
    ).strip()
    if saved_theme not in VALID_WEB_THEMES:
        saved_theme = DEFAULT_WEB_THEME

    config_data = {
        CONF_DEVICE_SLUG: coordinator.device_slug,
        CONF_DEVICE_PROFILE: coordinator.get_opt(
            CONF_DEVICE_PROFILE, DEFAULT_DEVICE_PROFILE
        ),
        CONF_DISPLAY_SHAPE: coordinator.display_shape,
        CONF_DEFAULT_PAGE_SIZE: coordinator.default_page_size,
        CONF_WEB_THEME: saved_theme,
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
        CONF_PRESENCE_ENTITY: coordinator.presence_entity or "",
        CONF_BLE_AUTO_SWITCH: coordinator.ble_auto_switch_enabled,
        CONF_SYNC_DEVICE_AREA: coordinator.sync_device_area_enabled,
        CONF_AREA_HANDOFF: coordinator.area_handoff_enabled,
        CONF_ALARM_ENTITY: coordinator.get_opt(CONF_ALARM_ENTITY, "")
        or coordinator.alarm_entity
        or "",
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
        CONF_ART_SIZE: coordinator.art_size,
    }

    return {
        "entry_id": coordinator.entry.entry_id,
        "title": coordinator.entry.title,
        "version": INTEGRATION_VERSION,
        "config": config_data,
        "esphome": esphome_inspector,
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
            "active_speaker": coordinator.active_speaker,
            "local_speaker": coordinator.local_speaker,
            "volume_entity": media_attrs.get("volume_entity", ""),
            "media_state": media_state,
            "media_title": media_attrs.get("title", "Idle"),
            "media_artist": media_attrs.get("artist", "None"),
            "media_art_url": media_attrs.get("art_url", "none"),
            "alarm_state": room_attrs.get("alarm_state", "none"),
            "wallpaper_url": room_attrs.get("wallpaper_url", "none"),
        },
        "catalog": {
            "areas": areas_list,
            "ma_speakers": ma_speakers,
            "volume_targets": volume_targets,
            "remotes": remotes_list,
            "alarms": alarms_list,
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
        """Save updated configuration or execute a live entity/device action."""
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

        if cmd == "set_theme":
            theme_val = str(body.get("web_theme") or DEFAULT_WEB_THEME).strip()
            if theme_val not in VALID_WEB_THEMES:
                theme_val = DEFAULT_WEB_THEME
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
                CONF_ART_SIZE,
            ):
                if k in incoming_cfg:
                    val = incoming_cfg[k]
                    if k == CONF_ART_SIZE:
                        val = int(val or DEFAULT_ART_SIZE)
                    elif k == CONF_DEFAULT_PAGE_SIZE:
                        val = max(1, min(20, int(val or DEFAULT_PAGE_SIZE)))
                    merged[k] = val

            self.hass.config_entries.async_update_entry(
                coordinator.entry, data=merged, options=merged
            )
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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Latter Companion Studio</title>
<style>
  :root, [data-theme="amoled_midnight"] {
    --bg: #05070b;
    --sidebar: #0b0f17;
    --card: #101622;
    --card-hover: #161e2e;
    --border: #1e293b;
    --input-bg: #090d14;
    --text: #f8fafc;
    --muted: #94a3b8;
    --accent: #38bdf8;
    --accent-2: #818cf8;
    --accent-glow: rgba(56, 189, 248, 0.14);
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
  }
  [data-theme="daylight_clean"] {
    --bg: #f1f5f9;
    --sidebar: #ffffff;
    --card: #ffffff;
    --card-hover: #f8fafc;
    --border: #e2e8f0;
    --input-bg: #f8fafc;
    --text: #0f172a;
    --muted: #64748b;
    --accent: #0284c7;
    --accent-2: #4f46e5;
    --accent-glow: rgba(2, 132, 199, 0.10);
    --success: #059669;
    --warning: #d97706;
    --danger: #dc2626;
    --shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
  }
  [data-theme="cyber_cyan"] {
    --bg: #0b111e;
    --sidebar: #0f172a;
    --card: #152036;
    --card-hover: #1c2b47;
    --border: #233554;
    --input-bg: #0b111e;
    --text: #f1f5f9;
    --muted: #94a3b8;
    --accent: #00d2ff;
    --accent-2: #6366f1;
    --accent-glow: rgba(0, 210, 255, 0.14);
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
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
  }
  .app-shell {
    display: grid;
    grid-template-columns: 260px minmax(0, 1fr);
    min-height: 100vh;
  }
  aside.sidebar {
    background: var(--sidebar);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    padding: 20px 14px;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 4px 8px 18px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 16px;
  }
  .brand-badge {
    width: 38px;
    height: 38px;
    border-radius: 11px;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    color: #fff;
    font-size: 18px;
    flex-shrink: 0;
  }
  .brand-text { min-width: 0; }
  .brand-text h1 {
    margin: 0;
    font-size: 15px;
    font-weight: 700;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .brand-text small {
    color: var(--muted);
    font-size: 11.5px;
    display: block;
    margin-top: 2px;
  }
  .nav-group-label {
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--muted);
    padding: 10px 10px 6px;
  }
  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    width: 100%;
    padding: 10px 12px;
    margin-bottom: 4px;
    border-radius: 10px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--muted);
    font-weight: 600;
    font-size: 13.5px;
    cursor: pointer;
    text-align: left;
    transition: all 0.15s ease;
  }
  .nav-btn:hover {
    background: var(--card-hover);
    color: var(--text);
  }
  .nav-btn.active {
    background: var(--accent-glow);
    color: var(--accent);
    border-color: rgba(56, 189, 248, 0.3);
  }
  .nav-btn .nav-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .nav-badge {
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 99px;
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--muted);
  }
  .sidebar-footer {
    margin-top: auto;
    padding-top: 16px;
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 10px;
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
    padding: 14px 28px;
    background: var(--sidebar);
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 15;
    flex-wrap: wrap;
    gap: 12px;
  }
  .topbar-status {
    display: flex;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
  }
  .status-chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 6px 12px;
    border-radius: 99px;
    background: var(--card);
    border: 1px solid var(--border);
    font-size: 12.5px;
    font-weight: 600;
  }
  .dot-live {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
  }
  .topbar-actions {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .dirty-banner {
    display: none;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    font-weight: 700;
    color: var(--warning);
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.35);
    padding: 6px 12px;
    border-radius: 8px;
  }
  .dirty-banner.visible { display: inline-flex; }
  button.btn-primary {
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    color: #ffffff;
    border: none;
    padding: 9px 18px;
    border-radius: 9px;
    font-weight: 700;
    cursor: pointer;
    font-size: 13px;
    box-shadow: 0 2px 10px var(--accent-glow);
  }
  button.btn-secondary {
    background: var(--card);
    color: var(--text);
    border: 1px solid var(--border);
    padding: 8px 14px;
    border-radius: 9px;
    font-weight: 600;
    cursor: pointer;
    font-size: 13px;
  }
  button.btn-secondary:hover { background: var(--card-hover); }
  button.btn-danger {
    background: rgba(239, 68, 68, 0.14);
    color: var(--danger);
    border: 1px solid rgba(239, 68, 68, 0.3);
    padding: 7px 11px;
    border-radius: 8px;
    font-weight: 700;
    cursor: pointer;
  }
  .content-wrap {
    max-width: 1180px;
    width: 100%;
    margin: 0 auto;
    padding: 26px 28px 72px;
  }
  .page-header {
    margin-bottom: 22px;
  }
  .page-header h2 {
    margin: 0 0 6px;
    font-size: 21px;
    font-weight: 700;
  }
  .page-header p {
    margin: 0;
    color: var(--muted);
    font-size: 13.5px;
    line-height: 1.5;
  }
  .grid-2 {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: 20px;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px;
    box-shadow: var(--shadow);
    min-width: 0;
  }
  .card h3 {
    margin: 0 0 6px;
    font-size: 15.5px;
    font-weight: 700;
  }
  .card p.desc {
    margin: 0 0 16px;
    font-size: 12.5px;
    color: var(--muted);
    line-height: 1.45;
  }
  .hero-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px;
    margin-bottom: 20px;
  }
  .stat-box {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px;
  }
  .stat-box span {
    display: block;
    font-size: 11.5px;
    font-weight: 600;
    color: var(--muted);
    margin-bottom: 4px;
  }
  .stat-box strong {
    font-size: 17px;
    font-weight: 700;
    color: var(--accent);
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .field { margin-bottom: 14px; }
  .field label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    margin-bottom: 6px;
  }
  select, input[type="text"], input[type="number"] {
    width: 100%;
    padding: 9px 12px;
    border-radius: 9px;
    border: 1px solid var(--border);
    background: var(--input-bg);
    color: var(--text);
    font-size: 13px;
  }
  select:focus, input:focus {
    outline: 2px solid var(--accent);
    border-color: transparent;
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
  .rssi-bar { margin-bottom: 11px; }
  .rssi-header {
    display: flex;
    justify-content: space-between;
    font-size: 12.5px;
    margin-bottom: 5px;
  }
  .rssi-track {
    height: 8px;
    background: var(--input-bg);
    border-radius: 99px;
    overflow: hidden;
    border: 1px solid var(--border);
  }
  .rssi-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-2), var(--accent));
    border-radius: 99px;
    transition: width 0.3s ease;
  }
  .room-cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 10px;
    margin-top: 12px;
  }
  .room-mini-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 11px 14px;
    border-radius: 10px;
    background: var(--input-bg);
    border: 1px solid var(--border);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .room-mini-card.on {
    border-color: var(--accent);
    background: var(--accent-glow);
  }
  .room-mini-card strong {
    font-size: 13px;
    display: block;
  }
  .room-mini-card small {
    font-size: 11px;
    color: var(--muted);
  }
  .esp-layout {
    display: grid;
    grid-template-columns: 240px minmax(0, 1fr);
    gap: 18px;
    align-items: start;
  }
  .esp-nav { display: flex; flex-direction: column; gap: 6px; }
  .esp-nav-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    border-radius: 9px;
    background: var(--input-bg);
    border: 1px solid var(--border);
    color: var(--text);
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
  }
  .esp-nav-btn.active {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--accent-glow);
  }
  .entity-list { display: flex; flex-direction: column; gap: 9px; }
  .entity-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 14px;
    align-items: center;
    padding: 11px 14px;
    background: var(--input-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    font-size: 13px;
  }
  .entity-row.wide-val { grid-template-columns: 1fr; gap: 8px; }
  .entity-row .meta strong { display: block; font-size: 13.5px; }
  .entity-row .meta small { color: var(--muted); font-size: 11px; }
  .entity-row .ctrl {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .state-badge {
    display: inline-block;
    padding: 5px 10px;
    border-radius: 7px;
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--accent);
    font-weight: 700;
    font-size: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .binding-row {
    display: grid;
    grid-template-columns: 1.1fr 1.6fr 0.9fr auto auto;
    gap: 8px;
    align-items: center;
    margin-bottom: 10px;
    background: var(--input-bg);
    padding: 10px;
    border-radius: 10px;
    border: 1px solid var(--border);
  }
  .chip-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
  .chip {
    background: var(--accent-glow);
    border: 1px solid var(--accent);
    color: var(--text);
    padding: 5px 11px;
    border-radius: 99px;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .chip b { cursor: pointer; color: var(--danger); }
  .toast {
    position: fixed;
    bottom: 22px;
    right: 22px;
    background: var(--success);
    color: #ffffff;
    padding: 12px 20px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 13px;
    display: none;
    z-index: 50;
    box-shadow: var(--shadow);
  }
  .hidden { display: none !important; }
  @media (max-width: 900px) {
    .app-shell { grid-template-columns: 1fr; }
    aside.sidebar {
      position: static;
      height: auto;
      border-right: none;
      border-bottom: 1px solid var(--border);
    }
    .esp-layout { grid-template-columns: 1fr; }
    .binding-row { grid-template-columns: 1fr; }
  }
</style>
</head>
<body data-theme="amoled_midnight">
<div class="app-shell">
  <!-- LEFT SIDEBAR NAVIGATION -->
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-badge">L</div>
      <div class="brand-text">
        <h1 id="hdr-title">Latter Studio</h1>
        <small id="hdr-sub">ESPHome Companion</small>
      </div>
    </div>

    <div class="nav-group-label">Live & Everyday</div>
    <button class="nav-btn active" onclick="switchView('dashboard', this)">
      <span class="nav-left"><span>Dashboard & Radar</span></span>
      <span class="nav-badge" id="nav-room-badge">--</span>
    </button>
    <button class="nav-btn" onclick="switchView('esphome', this)">
      <span class="nav-left"><span>Device Controls</span></span>
      <span class="nav-badge" id="nav-esp-badge">0</span>
    </button>

    <div class="nav-group-label">Entity Mapping</div>
    <button class="nav-btn" onclick="switchView('audio', this)">
      <span class="nav-left"><span>Audio & Speakers</span></span>
    </button>
    <button class="nav-btn" onclick="switchView('remotes', this)">
      <span class="nav-left"><span>TV Remotes & Home</span></span>
    </button>
    <button class="nav-btn" onclick="switchView('mapper', this)">
      <span class="nav-left"><span>Buttons & Pinned</span></span>
    </button>

    <div class="nav-group-label">System</div>
    <button class="nav-btn" onclick="switchView('display', this)">
      <span class="nav-left"><span>Display & Advanced</span></span>
    </button>

    <div class="sidebar-footer">
      <div class="field" style="margin-bottom:0;">
        <label>Studio Color Theme (Auto-Saves)</label>
        <select id="cfg-web_theme" onchange="onThemeChanged(this.value)">
          <option value="amoled_midnight">AMOLED Midnight (Dark)</option>
          <option value="daylight_clean">Daylight Clean (Light)</option>
          <option value="cyber_cyan">Cyber Cyan</option>
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
        <div id="dirty-indicator" class="dirty-banner">Unsaved Changes</div>
        <button class="btn-secondary" onclick="refreshState(true)">Sync Now</button>
        <button class="btn-primary" onclick="saveAllConfig()">Save Changes</button>
      </div>
    </header>

    <div class="content-wrap">
      <!-- VIEW 1: DASHBOARD & ROOM RADAR -->
      <section id="view-dashboard">
        <div class="page-header">
          <h2>Live Overview & BLE Room Radar</h2>
          <p>Monitor your device's active room, test curated room cards in real time, and view multi-room ESPHome BLE proxy signal strength.</p>
        </div>

        <div class="hero-stats">
          <div class="stat-box"><span>Active Room</span><strong id="st-room">--</strong></div>
          <div class="stat-box"><span>Ambient Climate</span><strong id="st-climate">--</strong></div>
          <div class="stat-box"><span>Active Speaker</span><strong id="st-speaker">--</strong></div>
          <div class="stat-box"><span>Home Security</span><strong id="st-alarm">--</strong></div>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Active Room Context & Live Cards</h3>
            <p class="desc">Switch the device's active room or click any curated card below to toggle it in Home Assistant.</p>
            <div class="field">
              <label>Active Room (Instant Switch)</label>
              <select id="quick-area" onchange="quickSwitchArea(this.value)"></select>
            </div>
            <div class="field">
              <label>Active Speaker (Instant Switch)</label>
              <select id="quick-speaker" onchange="quickSwitchSpeaker(this.value)"></select>
            </div>
            <label style="font-size:12px;font-weight:600;color:var(--muted);display:block;margin-top:14px;">Curated Cards Pushed to Device (<span id="st-card-count">0</span>)</label>
            <div id="live-room-cards" class="room-cards-grid"></div>
          </div>

          <div class="card">
            <h3>BLE Room Presence Radar</h3>
            <p class="desc">Live smoothed RSSI (dBm) reported by each room's ESPHome Bluetooth proxy for your device's beacon.</p>
            <div id="rssi-container" style="margin-bottom:16px;"></div>

            <div class="toggle-row">
              <span>Built-In ESPHome BLE Proxy Room Tracking</span>
              <input type="checkbox" id="cfg-native_ble_tracking" onchange="markDirty()">
            </div>
            <div class="toggle-row">
              <span>Auto-Switch Active Room When Walking Between Rooms</span>
              <input type="checkbox" id="cfg-ble_auto_switch" onchange="markDirty()">
            </div>
            <div class="toggle-row">
              <span>Sync Active Room to HA Device Area (Room-Aware Voice Assistant)</span>
              <input type="checkbox" id="cfg-sync_device_area" onchange="markDirty()">
            </div>
          </div>
        </div>
      </section>

      <!-- VIEW 2: ESPHOME DEVICE CONTROLS -->
      <section id="view-esphome" class="hidden">
        <div class="page-header">
          <h2 id="esp-dev-title">ESPHome Device Controls</h2>
          <p id="esp-dev-meta">Inspect and adjust every setting, switch, select, number, and diagnostic sensor exposed by your ESPHome firmware.</p>
        </div>

        <div class="card" style="margin-bottom:18px;padding:14px 18px;">
          <input type="text" id="esp-search" placeholder="Search device controls or sensors by name or entity_id..." oninput="renderActiveEspSection()">
        </div>

        <div class="esp-layout">
          <div class="card" style="padding:14px;">
            <div id="esp-nav-list" class="esp-nav"></div>
          </div>
          <div class="card">
            <h3 id="esp-sec-title">Category</h3>
            <p class="desc" id="esp-sec-desc"></p>
            <div id="esp-sec-items" class="entity-list"></div>
          </div>
        </div>
      </section>

      <!-- VIEW 3: AUDIO & SPEAKERS -->
      <section id="view-audio" class="hidden">
        <div class="page-header">
          <h2>Music Assistant & AVR Volume Overrides</h2>
          <p>Configure your default speaker and optionally route volume control to a separate AV Receiver or amplifier when streaming to a specific room player.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Default Speaker & Room Handoff</h3>
            <p class="desc">Your device defaults to its own local speaker on boot unless a remote speaker is actively playing.</p>
            <div class="field">
              <label>Default Speaker Entity</label>
              <select id="cfg-default_speaker" onchange="markDirty()"></select>
            </div>
            <div class="toggle-row">
              <span>Unified Area Handoff (Link Room Speaker & Remote on Manual Switch)</span>
              <input type="checkbox" id="cfg-area_handoff" onchange="markDirty()">
            </div>
          </div>

          <div class="card">
            <h3>Streamer &rarr; AV Receiver Volume Overrides</h3>
            <p class="desc">When streaming to a Music Assistant player plugged into an external AVR/amplifier, route volume slider & buttons to the AVR.</p>
            <div class="field">
              <label>Override 1: When Streaming to Speaker...</label>
              <select id="cfg-vol_speaker_1" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Override 1: Control Physical Volume on Entity...</label>
              <select id="cfg-vol_target_1" onchange="markDirty()"></select>
            </div>
            <hr style="border:0;border-top:1px solid var(--border);margin:14px 0;">
            <div class="field">
              <label>Override 2: When Streaming to Speaker...</label>
              <select id="cfg-vol_speaker_2" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Override 2: Control Physical Volume on Entity...</label>
              <select id="cfg-vol_target_2" onchange="markDirty()"></select>
            </div>
          </div>
        </div>
      </section>

      <!-- VIEW 4: TV REMOTES & HOME -->
      <section id="view-remotes" class="hidden">
        <div class="page-header">
          <h2>4-Slot TV Remotes, Security Alarm & Weather</h2>
          <p>Assign up to 4 TVs or media players (Android TV, Apple TV, Roku, LG webOS, Denon/Marantz) and bind your home's alarm and weather provider.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>4-Slot Hybrid TV / Media Remotes</h3>
            <p class="desc">Pick either the <code>remote.*</code> or <code>media_player.*</code> entity—Latter automatically binds both sibling entities on the device.</p>
            <div class="field">
              <label>Remote Slot 1</label>
              <select id="cfg-remote_1" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Remote Slot 2</label>
              <select id="cfg-remote_2" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Remote Slot 3</label>
              <select id="cfg-remote_3" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Remote Slot 4</label>
              <select id="cfg-remote_4" onchange="markDirty()"></select>
            </div>
          </div>

          <div class="card">
            <h3>Home Security Alarm & Weather Provider</h3>
            <p class="desc">Used by the Home Security screen and 5-day weather forecast engine.</p>
            <div class="field">
              <label>Home Security Alarm (alarm_control_panel)</label>
              <select id="cfg-alarm_entity" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Weather Provider Entity</label>
              <select id="cfg-weather_entity" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Default Startup Room Fallback</label>
              <select id="cfg-default_area" onchange="markDirty()"></select>
            </div>
          </div>
        </div>
      </section>

      <!-- VIEW 5: BUTTONS & PINNED ENTITIES -->
      <section id="view-mapper" class="hidden">
        <div class="page-header">
          <h2>Universal Button Mapper & Pinned Entities</h2>
          <p>Bind hardware buttons, rotary encoders, or touch macros (<code>latter.trigger_binding</code>) and pin favorite entities to the top of Room Control.</p>
        </div>

        <div class="card" style="margin-bottom:20px;">
          <h3>Hardware Trigger & Slot Bindings</h3>
          <p class="desc">Map any slot ID sent by your firmware (e.g. <code>button_1_single</code>, <code>macro_goodnight</code>) to any Home Assistant entity.</p>
          <div id="bindings-list"></div>
          <button class="btn-secondary" onclick="addBindingRow('', '', 'toggle'); markDirty();">+ Add Trigger Binding</button>
        </div>

        <div class="card">
          <h3>Pinned Room / Home Entities</h3>
          <p class="desc">Pinned entities always appear first in your device's Room Control list regardless of which room you are in.</p>
          <div style="display:flex;gap:10px;">
            <select id="pin-entity-picker"></select>
            <button class="btn-secondary" onclick="addPinnedEntity()">Pin Entity</button>
          </div>
          <div id="pinned-chips" class="chip-list"></div>
        </div>
      </section>

      <!-- VIEW 6: DISPLAY & ADVANCED -->
      <section id="view-display" class="hidden">
        <div class="page-header">
          <h2>Display Geometry, Wallpaper & Advanced BLE</h2>
          <p>Configure screen shape, artwork transcoding resolution, pagination size, Home Dock tokens, and advanced BLE parameters.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Screen Geometry & Pagination</h3>
            <div class="field">
              <label>ESPHome Device Slug (sensor.&lt;slug&gt;_*)</label>
              <input type="text" id="cfg-device_slug" oninput="markDirty()">
            </div>
            <div class="field">
              <label>Device Archetype</label>
              <select id="cfg-device_profile" onchange="markDirty()">
                <option value="mobile_display">Mobile Smart Display (e.g. Pocket Assistant)</option>
                <option value="stationary_display">Stationary Room Display / Wall Panel</option>
                <option value="headless_node">Headless Sensor / Button / Audio Node</option>
              </select>
            </div>
            <div class="field">
              <label>Display Geometry / Mask</label>
              <select id="cfg-display_shape" onchange="markDirty()">
                <option value="circle">Circular Display (Bezel-Masked)</option>
                <option value="square">Square / Rectangular Display</option>
              </select>
            </div>
            <div class="field">
              <label>Artwork & Wallpaper Transcoder Resolution</label>
              <select id="cfg-art_size" onchange="markDirty()">
                <option value="466">466x466 (1.75" Round AMOLED)</option>
                <option value="360">360x360 (Round LCD / AMOLED)</option>
                <option value="240">240x240 (Compact Display)</option>
                <option value="233">233x233 (Fast Low-Bandwidth Thumbnail)</option>
                <option value="480">480x480 (Large Wall Panel)</option>
              </select>
            </div>
            <div class="field">
              <label>Room Control Cards Per Page (1–20)</label>
              <input type="number" id="cfg-default_page_size" min="1" max="20" value="3" oninput="markDirty()">
            </div>
          </div>

          <div class="card">
            <h3>Home Dock, Wallpaper & BLE Override</h3>
            <div class="field">
              <label>Home Dock App Tokens (comma-separated)</label>
              <input type="text" id="cfg-dock_apps" placeholder="music,room,remote,games,tools" oninput="markDirty()">
            </div>
            <div class="field">
              <label>Photo Wallpaper Source (/local/... or https://...)</label>
              <input type="text" id="cfg-wallpaper_source" placeholder="/local/wallpaper.jpg" oninput="markDirty()">
            </div>
            <hr style="border:0;border-top:1px solid var(--border);margin:14px 0;">
            <div class="field">
              <label>BLE iBeacon UUID</label>
              <input type="text" id="cfg-ble_beacon_uuid" oninput="markDirty()">
            </div>
            <div class="field">
              <label>External BLE Room Sensor Override (Optional Bermuda Sensor)</label>
              <select id="cfg-presence_entity" onchange="markDirty()"></select>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</div>

<div id="toast" class="toast">Saved!</div>

<script>
const API_URL = window.location.pathname + "/api" + window.location.search;
let STATE = null;
let PINNED = [];
let ACTIVE_ESP_SEC = null;
let IS_DIRTY = false;
let INITIAL_FORM_LOADED = false;

const savedLocalTheme = localStorage.getItem("latter_web_theme");
if (savedLocalTheme) {
  document.body.setAttribute("data-theme", savedLocalTheme);
}

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.style.display = "block";
  setTimeout(() => { t.style.display = "none"; }, 2600);
}

function markDirty() {
  IS_DIRTY = true;
  document.getElementById("dirty-indicator").classList.add("visible");
}

function clearDirty() {
  IS_DIRTY = false;
  document.getElementById("dirty-indicator").classList.remove("visible");
}

function applyTheme(themeName) {
  const valid = ["amoled_midnight", "daylight_clean", "cyber_cyan"];
  const chosen = valid.includes(themeName) ? themeName : "amoled_midnight";
  document.body.setAttribute("data-theme", chosen);
  localStorage.setItem("latter_web_theme", chosen);
  const sel = document.getElementById("cfg-web_theme");
  if (sel && sel.value !== chosen) sel.value = chosen;
}

async function onThemeChanged(themeName) {
  applyTheme(themeName);
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "set_theme", web_theme: themeName})
  });
  if (resp.ok) {
    showToast("Theme saved!");
  }
}

function switchView(viewId, btnEl) {
  document.querySelectorAll(". sidebar .nav-btn, aside .nav-btn").forEach(b => b.classList.remove("active"));
  btnEl.classList.add("active");
  ["dashboard", "esphome", "audio", "remotes", "mapper", "display"].forEach(id => {
    document.getElementById("view-" + id).classList.toggle("hidden", id !== viewId);
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

function renderRssiBars(rssiMap, packetsSeen) {
  const box = document.getElementById("rssi-container");
  const entries = Object.entries(rssiMap || {});
  if (!entries.length) {
    box.innerHTML = `<p class="desc">Waiting for BLE iBeacon packets (Seen: ${packetsSeen || 0}). Ensure the BLE Presence Beacon switch is ON on your device.</p>`;
    return;
  }
  entries.sort((a, b) => b[1] - a[1]);
  box.innerHTML = entries.map(([room, dbm]) => {
    const pct = Math.max(8, Math.min(100, Math.round(((dbm + 100) / 55) * 100)));
    return `<div class="rssi-bar">
      <div class="rssi-header"><strong>${room}</strong><span>${dbm} dBm</span></div>
      <div class="rssi-track"><div class="rssi-fill" style="width:${pct}%"></div></div>
    </div>`;
  }).join("");
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

function selectEspSection(secId) {
  ACTIVE_ESP_SEC = secId;
  renderEspInspector();
}

function renderEspInspector() {
  const esp = STATE?.esphome;
  if (!esp) return;
  const sections = esp.sections || [];
  const totalCount = sections.reduce((acc, s) => acc + s.count, 0);
  document.getElementById("nav-esp-badge").textContent = totalCount;

  if (!sections.length) {
    document.getElementById("esp-nav-list").innerHTML = "";
    document.getElementById("esp-sec-title").textContent = "No ESPHome Entities Found";
    document.getElementById("esp-sec-desc").textContent = "Check that your ESPHome device slug matches your node in Home Assistant.";
    document.getElementById("esp-sec-items").innerHTML = "";
    return;
  }

  if (!ACTIVE_ESP_SEC || (ACTIVE_ESP_SEC !== "__all__" && !sections.some(s => s.id === ACTIVE_ESP_SEC))) {
    ACTIVE_ESP_SEC = sections[0].id;
  }

  const navBox = document.getElementById("esp-nav-list");
  navBox.innerHTML = [
    `<div class="esp-nav-btn ${ACTIVE_ESP_SEC === '__all__' ? 'active' : ''}" onclick="selectEspSection('__all__')">
      <span>All Controls</span>
      <span class="nav-badge">${totalCount}</span>
    </div>`
  ].concat(sections.map(s => `
    <div class="esp-nav-btn ${s.id === ACTIVE_ESP_SEC ? 'active' : ''}" onclick="selectEspSection('${s.id}')">
      <span>${s.title}</span>
      <span class="nav-badge">${s.count}</span>
    </div>
  `)).join("");

  renderActiveEspSection();
}

function renderActiveEspSection() {
  const esp = STATE?.esphome;
  if (!esp || !esp.sections) return;
  const query = (document.getElementById("esp-search")?.value || "").trim().toLowerCase();

  let activeTitle = "All Device Entities";
  let activeDesc = "Showing all controls, options, sensors, and diagnostic entities.";
  let rawItems = [];

  if (ACTIVE_ESP_SEC === "__all__" || query.length > 0) {
    esp.sections.forEach(s => { rawItems = rawItems.concat(s.items); });
    if (query.length > 0) {
      activeTitle = `Filtered Entities ("${query}")`;
      rawItems = rawItems.filter(it =>
        it.name.toLowerCase().includes(query) || it.entity_id.toLowerCase().includes(query)
      );
    }
  } else {
    const sec = esp.sections.find(s => s.id === ACTIVE_ESP_SEC) || esp.sections[0];
    if (sec) {
      activeTitle = sec.title;
      activeDesc = sec.description;
      rawItems = sec.items;
    }
  }

  document.getElementById("esp-sec-title").textContent = activeTitle;
  document.getElementById("esp-sec-desc").textContent = activeDesc;

  const box = document.getElementById("esp-sec-items");
  if (!rawItems.length) {
    box.innerHTML = `<p class="desc">No matching entities in this view.</p>`;
    return;
  }

  box.innerHTML = rawItems.map(item => {
    const stateText = `${item.state}${item.unit ? ' ' + item.unit : ''}`;
    const isLongState = stateText.length > 36 && !["button", "switch", "select", "number"].includes(item.domain);
    let controlHtml = `<span class="state-badge">${stateText}</span>`;

    if (item.domain === "button") {
      controlHtml = `<button class="btn-secondary" onclick="espAction('${item.entity_id}', 'press')">Trigger</button>`;
    } else if (item.domain === "switch" || item.domain === "light" || item.domain === "fan") {
      const isOn = item.state === "on";
      controlHtml = `<button class="${isOn ? 'btn-primary' : 'btn-secondary'}" onclick="espAction('${item.entity_id}', 'toggle')">${isOn ? 'ON' : 'OFF'}</button>`;
    } else if (item.domain === "select" && item.options && item.options.length) {
      const opts = item.options.map(o => `<option value="${o}" ${o===item.state?'selected':''}>${o}</option>`).join("");
      controlHtml = `<select style="width:auto;min-width:150px;" onchange="espSelect('${item.entity_id}', this.value)">${opts}</select>`;
    } else if (item.domain === "number") {
      controlHtml = `<input type="number" style="width:95px;text-align:right;" value="${item.state}" min="${item.min ?? 0}" max="${item.max ?? 100}" step="${item.step ?? 1}" onchange="espNumber('${item.entity_id}', this.value)">${item.unit ? `<span style="font-size:12px;color:var(--muted);">${item.unit}</span>` : ''}`;
    }

    return `<div class="entity-row ${isLongState ? 'wide-val' : ''}">
      <div class="meta">
        <strong>${item.name}</strong>
        <small>${item.entity_id} • ${item.domain}</small>
      </div>
      <div class="ctrl">${controlHtml}</div>
    </div>`;
  }).join("");
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
    showToast(`Set ${entity_id} = ${level}`);
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

function applyStateToDom(data, forceFormUpdate=false) {
  STATE = data;
  const cfg = data.config;
  const live = data.live;
  const cat = data.catalog;
  const esp = data.esphome;

  // Always update live telemetry badges, room cards, BLE radar, and ESPHome live states
  const roomName = live.active_area_name || "Home";
  const spkShort = (live.active_speaker || "").replace("media_player.", "");
  const tempStr = live.room_temp != null ? `${live.room_temp}°` : "--";
  const humStr = live.room_humidity != null ? ` • ${live.room_humidity}%` : "";

  document.getElementById("hdr-title").textContent = esp?.device?.name || data.title;
  document.getElementById("hdr-sub").textContent = `Latter v${data.version || '1.4'}`;
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

  populateSelect("quick-area", cat.areas, live.active_area_id, false);
  populateSelect("quick-speaker", cat.ma_speakers, live.active_speaker, false);
  renderLiveRoomCards(live.room_cards);
  renderRssiBars(live.ble_rssi_by_room, live.ble_packets_seen);

  if (esp && esp.device) {
    document.getElementById("esp-dev-title").textContent = `${esp.device.name} (${esp.device.model})`;
    document.getElementById("esp-dev-meta").textContent = `Manufacturer: ${esp.device.manufacturer} • Firmware: ${esp.device.sw_version || 'ESPHome'} • MAC: ${esp.device.mac || 'N/A'}`;
    // Only re-render ESPHome list if user isn't actively focused on a select/number inside it
    const activeEl = document.activeElement;
    if (!activeEl || !document.getElementById("esp-sec-items")?.contains(activeEl)) {
      renderEspInspector();
    }
  }

  // NEVER overwrite form inputs during background 5s polling if the user has unsaved edits!
  if (!INITIAL_FORM_LOADED || forceFormUpdate) {
    INITIAL_FORM_LOADED = true;
    applyTheme(cfg.web_theme || "amoled_midnight");

    document.getElementById("cfg-device_slug").value = cfg.device_slug || "";
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
    populateSelect("cfg-weather_entity", cat.weathers, cfg.weather_entity);
    populateSelect("pin-entity-picker", cat.bindable_entities, "", false);

    PINNED = Array.isArray(cfg.custom_entities) ? [...cfg.custom_entities] : [];
    renderPinnedChips();

    const bList = document.getElementById("bindings-list");
    bList.innerHTML = "";
    (cfg.custom_bindings || []).forEach(b => addBindingRow(b.slot, b.entity_id, b.action));
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
    showToast("Switched active room!");
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
    showToast("Switched active speaker!");
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
    weather_entity: document.getElementById("cfg-weather_entity").value,
    default_area: document.getElementById("cfg-default_area").value,
    dock_apps: document.getElementById("cfg-dock_apps").value.trim(),
    wallpaper_source: document.getElementById("cfg-wallpaper_source").value.trim(),
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
    showToast("Configuration saved & applied!");
  }
}

refreshState(true);
setInterval(() => refreshState(false), 5000);
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