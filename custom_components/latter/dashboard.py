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
                    elif k == CONF_WEB_THEME:
                        val = _normalize_web_theme(val)
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
  :root, [data-theme="dark"] {
    --bg: #07090e;
    --sidebar: #0c1017;
    --card: #111722;
    --card-hover: #172030;
    --border: #1e293b;
    --input-bg: #090d14;
    --text: #e2e8f0;
    --text-strong: #f8fafc;
    --muted: #8b9bb4;
    --accent: #38bdf8;
    --accent-solid: #0284c7;
    --accent-subtle: rgba(56, 189, 248, 0.10);
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
    --accent: #0369a1;
    --accent-solid: #0284c7;
    --accent-subtle: rgba(2, 132, 199, 0.10);
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
  }
  code, .mono {
    font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
    font-size: 12px;
  }
  .app-shell {
    display: grid;
    grid-template-columns: 248px minmax(0, 1fr);
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
    margin-bottom: 12px;
  }
  .brand-badge {
    width: 32px;
    height: 32px;
    border-radius: 7px;
    background: var(--accent-solid);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    color: #ffffff;
    font-size: 15px;
    flex-shrink: 0;
    letter-spacing: -0.5px;
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
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .nav-group-label {
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.7px;
    color: var(--muted);
    padding: 12px 10px 5px;
  }
  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: 100%;
    padding: 9px 11px;
    margin-bottom: 2px;
    border-radius: 7px;
    border: 1px solid transparent;
    background: transparent;
    color: var(--muted);
    font-weight: 600;
    font-size: 13px;
    cursor: pointer;
    text-align: left;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .nav-btn:hover {
    background: var(--card-hover);
    color: var(--text-strong);
  }
  .nav-btn.active {
    background: var(--accent-subtle);
    color: var(--accent);
    border-color: var(--border);
  }
  .nav-badge {
    font-size: 11px;
    padding: 1px 7px;
    border-radius: 5px;
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--muted);
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
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
    gap: 10px;
    flex-wrap: wrap;
  }
  .status-chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 5px 10px;
    border-radius: 6px;
    background: var(--card);
    border: 1px solid var(--border);
    font-size: 12px;
    font-weight: 600;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
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
    padding: 7px 14px;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
    font-size: 12.5px;
  }
  button.btn-primary:hover { opacity: 0.92; }
  button.btn-secondary {
    background: var(--card);
    color: var(--text-strong);
    border: 1px solid var(--border);
    padding: 7px 13px;
    border-radius: 6px;
    font-weight: 600;
    cursor: pointer;
    font-size: 12.5px;
  }
  button.btn-secondary:hover { background: var(--card-hover); }
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
  .page-header {
    margin-bottom: 18px;
  }
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
    grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
    gap: 16px;
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
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }
  .stat-box {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 12px 14px;
  }
  .stat-box span {
    display: block;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--muted);
    margin-bottom: 4px;
  }
  .stat-box strong {
    font-size: 15.5px;
    font-weight: 700;
    color: var(--text-strong);
    display: block;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
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
    padding: 8px 10px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--input-bg);
    color: var(--text-strong);
    font-size: 13px;
  }
  select:focus, input:focus {
    outline: 1px solid var(--accent);
    border-color: var(--accent);
  }
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 0;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    gap: 12px;
  }
  .toggle-row:last-child { border-bottom: none; }
  .rssi-bar { margin-bottom: 10px; }
  .rssi-header {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    margin-bottom: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
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
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 8px;
    margin-top: 10px;
  }
  .room-mini-card {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 12px;
    border-radius: 7px;
    background: var(--input-bg);
    border: 1px solid var(--border);
    cursor: pointer;
    transition: background 0.12s ease;
  }
  .room-mini-card:hover { background: var(--card-hover); }
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
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .esp-layout {
    display: grid;
    grid-template-columns: 230px minmax(0, 1fr);
    gap: 16px;
    align-items: start;
  }
  .esp-nav { display: flex; flex-direction: column; gap: 4px; }
  .esp-nav-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 11px;
    border-radius: 6px;
    background: var(--input-bg);
    border: 1px solid var(--border);
    color: var(--text);
    cursor: pointer;
    font-size: 12.5px;
    font-weight: 600;
  }
  .esp-nav-btn.active {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--accent-subtle);
  }
  .entity-list { display: flex; flex-direction: column; gap: 7px; }
  .entity-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 12px;
    align-items: center;
    padding: 10px 12px;
    background: var(--input-bg);
    border: 1px solid var(--border);
    border-radius: 7px;
    font-size: 13px;
  }
  .entity-row.wide-val { grid-template-columns: 1fr; gap: 8px; }
  .entity-row .meta strong { display: block; font-size: 13px; color: var(--text-strong); }
  .entity-row .meta small {
    color: var(--muted);
    font-size: 11px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .entity-row .ctrl {
    display: flex;
    align-items: center;
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
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
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
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
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
<body data-theme="dark">
<div class="app-shell">
  <!-- LEFT SIDEBAR NAVIGATION -->
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-badge">L</div>
      <div class="brand-text">
        <h1 id="hdr-title">Latter Studio</h1>
        <small id="hdr-sub">v1.4.6</small>
      </div>
    </div>

    <div class="nav-group-label">Live & Everyday</div>
    <button class="nav-btn active" onclick="switchView('dashboard', this)">
      <span>Dashboard & Radar</span>
      <span class="nav-badge" id="nav-room-badge">--</span>
    </button>
    <button class="nav-btn" onclick="switchView('esphome', this)">
      <span>Device Controls</span>
      <span class="nav-badge" id="nav-esp-badge">0</span>
    </button>

    <div class="nav-group-label">Entity Mapping</div>
    <button class="nav-btn" onclick="switchView('audio', this)">
      <span>Audio & Speakers</span>
    </button>
    <button class="nav-btn" onclick="switchView('remotes', this)">
      <span>TV Remotes & Home</span>
    </button>
    <button class="nav-btn" onclick="switchView('mapper', this)">
      <span>Buttons & Pinned</span>
    </button>

    <div class="nav-group-label">System</div>
    <button class="nav-btn" onclick="switchView('display', this)">
      <span>Display & Advanced</span>
    </button>

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
        <div id="dirty-indicator" class="dirty-banner">Unsaved Changes</div>
        <button class="btn-secondary" onclick="refreshState(true)">Sync</button>
        <button class="btn-primary" onclick="saveAllConfig()">Save Changes</button>
      </div>
    </header>

    <div class="content-wrap">
      <!-- VIEW 1: DASHBOARD & ROOM RADAR -->
      <section id="view-dashboard">
        <div class="page-header">
          <h2>Overview & BLE Room Presence</h2>
          <p>Live device telemetry, active room controls, and multi-proxy Bluetooth RSSI triangulation.</p>
        </div>

        <div class="hero-stats">
          <div class="stat-box"><span>Active Room</span><strong id="st-room">--</strong></div>
          <div class="stat-box"><span>Ambient Climate</span><strong id="st-climate">--</strong></div>
          <div class="stat-box"><span>Active Speaker</span><strong id="st-speaker">--</strong></div>
          <div class="stat-box"><span>Home Security</span><strong id="st-alarm">--</strong></div>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Active Context & Curated Room Entities</h3>
            <p class="desc">Override the active room or speaker, or click any curated entity below to toggle it directly.</p>
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
            <h3>BLE Proxy Signal Telemetry (EMA RSSI)</h3>
            <p class="desc">Smoothed signal strength (dBm) reported by each room's ESPHome Bluetooth proxy.</p>
            <div id="rssi-container" style="margin-bottom:14px;"></div>

            <div class="toggle-row">
              <span>Built-In ESPHome BLE Proxy Tracking</span>
              <input type="checkbox" id="cfg-native_ble_tracking" onchange="markDirty()">
            </div>
            <div class="toggle-row">
              <span>Auto-Switch Active Room on Movement</span>
              <input type="checkbox" id="cfg-ble_auto_switch" onchange="markDirty()">
            </div>
            <div class="toggle-row">
              <span>Sync Active Room to HA Device Area (Assist Voice Context)</span>
              <input type="checkbox" id="cfg-sync_device_area" onchange="markDirty()">
            </div>
          </div>
        </div>
      </section>

      <!-- VIEW 2: ESPHOME DEVICE CONTROLS -->
      <section id="view-esphome" class="hidden">
        <div class="page-header">
          <h2 id="esp-dev-title">ESPHome Device Controls</h2>
          <p id="esp-dev-meta">Inspect and control all entities exposed by the ESPHome node.</p>
        </div>

        <div class="card" style="margin-bottom:16px;padding:12px 14px;">
          <input type="text" id="esp-search" placeholder="Filter entities by name or entity_id..." oninput="renderActiveEspSection()">
        </div>

        <div class="esp-layout">
          <div class="card" style="padding:12px;">
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
          <h2>Audio Routing & AVR Volume Overrides</h2>
          <p>Configure default Music Assistant playback targets and external AV Receiver volume mappings.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Default Speaker & Room Handoff</h3>
            <p class="desc">Resets to the device's local speaker on boot/wake unless a remote speaker is actively playing.</p>
            <div class="field">
              <label>Default Speaker Entity</label>
              <select id="cfg-default_speaker" onchange="markDirty()"></select>
            </div>
            <div class="toggle-row">
              <span>Unified Area Handoff (Link Room Speaker & Remote)</span>
              <input type="checkbox" id="cfg-area_handoff" onchange="markDirty()">
            </div>
          </div>

          <div class="card">
            <h3>Streamer &rarr; AV Receiver Volume Overrides</h3>
            <p class="desc">Route volume commands to an external AVR or amplifier entity when streaming to a mapped player.</p>
            <div class="field">
              <label>Override 1: Source Speaker</label>
              <select id="cfg-vol_speaker_1" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Override 1: Volume Target Entity (media_player / number)</label>
              <select id="cfg-vol_target_1" onchange="markDirty()"></select>
            </div>
            <hr style="border:0;border-top:1px solid var(--border);margin:12px 0;">
            <div class="field">
              <label>Override 2: Source Speaker</label>
              <select id="cfg-vol_speaker_2" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Override 2: Volume Target Entity (media_player / number)</label>
              <select id="cfg-vol_target_2" onchange="markDirty()"></select>
            </div>
          </div>
        </div>
      </section>

      <!-- VIEW 4: TV REMOTES & HOME -->
      <section id="view-remotes" class="hidden">
        <div class="page-header">
          <h2>TV Remotes, Security Alarm & Weather</h2>
          <p>Bind up to 4 TV/media remotes, home security alarm panel, and weather forecast provider.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>4-Slot Hybrid TV / Media Remotes</h3>
            <p class="desc">Select either <code>remote.*</code> or <code>media_player.*</code>; sibling entities on the same device are paired automatically.</p>
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
            <h3>Security Alarm & Weather Provider</h3>
            <p class="desc">Entities used by the Home Security control view and 5-day weather serializer.</p>
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
          <h2>Hardware Trigger Bindings & Pinned Entities</h2>
          <p>Map custom firmware trigger slots (<code>latter.trigger_binding</code>) and pin global entities to Room Control.</p>
        </div>

        <div class="card" style="margin-bottom:16px;">
          <h3>Hardware Trigger & Slot Bindings</h3>
          <p class="desc">Bind any slot identifier (e.g. <code>button_1_single</code>, <code>macro_goodnight</code>) to a target Home Assistant entity and action.</p>
          <div id="bindings-list"></div>
          <button class="btn-secondary" onclick="addBindingRow('', '', 'toggle'); markDirty();">+ Add Trigger Binding</button>
        </div>

        <div class="card">
          <h3>Pinned Room / Home Entities</h3>
          <p class="desc">Pinned entities appear at the top of Room Control across all areas.</p>
          <div style="display:flex;gap:8px;">
            <select id="pin-entity-picker"></select>
            <button class="btn-secondary" onclick="addPinnedEntity()">Pin Entity</button>
          </div>
          <div id="pinned-chips" class="chip-list"></div>
        </div>
      </section>

      <!-- VIEW 6: DISPLAY & ADVANCED -->
      <section id="view-display" class="hidden">
        <div class="page-header">
          <h2>Display Geometry, Wallpaper & BLE Tuning</h2>
          <p>Configure hardware profile, image transcoder dimensions, slot pagination, and BLE beacon settings.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Hardware Profile & Pagination</h3>
            <div class="field">
              <label>ESPHome Device Slug (sensor.&lt;slug&gt;_*)</label>
              <input type="text" id="cfg-device_slug" oninput="markDirty()">
            </div>
            <div class="field">
              <label>Device Archetype</label>
              <select id="cfg-device_profile" onchange="markDirty()">
                <option value="mobile_display">Mobile Smart Display</option>
                <option value="stationary_display">Stationary Wall / Desk Display</option>
                <option value="headless_node">Headless Sensor / Button / Audio Node</option>
              </select>
            </div>
            <div class="field">
              <label>Display Geometry</label>
              <select id="cfg-display_shape" onchange="markDirty()">
                <option value="circle">Circular (Bezel-Masked Corners)</option>
                <option value="square">Square / Rectangular</option>
              </select>
            </div>
            <div class="field">
              <label>Artwork & Wallpaper Transcoder Resolution</label>
              <select id="cfg-art_size" onchange="markDirty()">
                <option value="466">466x466 (1.75" Round AMOLED)</option>
                <option value="360">360x360 (Round LCD / AMOLED)</option>
                <option value="240">240x240 (Compact Display)</option>
                <option value="233">233x233 (Low-Bandwidth Thumbnail)</option>
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
            <hr style="border:0;border-top:1px solid var(--border);margin:12px 0;">
            <div class="field">
              <label>BLE iBeacon UUID</label>
              <input type="text" id="cfg-ble_beacon_uuid" oninput="markDirty()">
            </div>
            <div class="field">
              <label>External BLE Room Sensor Override (Optional)</label>
              <select id="cfg-presence_entity" onchange="markDirty()"></select>
            </div>
          </div>
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
let ACTIVE_ESP_SEC = null;
let IS_DIRTY = false;
let INITIAL_FORM_LOADED = false;
let CURRENT_THEME_PREF = localStorage.getItem("latter_web_theme") || "dark";

const sysMedia = window.matchMedia("(prefers-color-scheme: dark)");
sysMedia.addEventListener("change", () => {
  if (CURRENT_THEME_PREF === "system") {
    applyTheme("system");
  }
});

function resolveEffectiveTheme(pref) {
  if (pref === "system") {
    return sysMedia.matches ? "dark" : "light";
  }
  return pref === "light" ? "light" : "dark";
}

function applyTheme(pref) {
  const valid = ["dark", "light", "system"];
  CURRENT_THEME_PREF = valid.includes(pref) ? pref : "dark";
  const effective = resolveEffectiveTheme(CURRENT_THEME_PREF);
  document.body.setAttribute("data-theme", effective);
  localStorage.setItem("latter_web_theme", CURRENT_THEME_PREF);
  const sel = document.getElementById("cfg-web_theme");
  if (sel && sel.value !== CURRENT_THEME_PREF) {
    sel.value = CURRENT_THEME_PREF;
  }
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
  if (resp.ok) {
    showToast(`Appearance set to ${themePref}`);
  }
}

function switchView(viewId, btnEl) {
  document.querySelectorAll("aside .nav-btn").forEach(b => b.classList.remove("active"));
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
    box.innerHTML = `<p class="desc">No recent BLE iBeacon packets (Seen: ${packetsSeen || 0}). Ensure BLE Presence Beacon is ON.</p>`;
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
    document.getElementById("esp-sec-desc").textContent = "Verify that the device slug matches your ESPHome node.";
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

  const roomName = live.active_area_name || "Home";
  const spkShort = (live.active_speaker || "").replace("media_player.", "");
  const tempStr = live.room_temp != null ? `${live.room_temp}°` : "--";
  const humStr = live.room_humidity != null ? ` • ${live.room_humidity}%` : "";

  document.getElementById("hdr-title").textContent = esp?.device?.name || data.title;
  document.getElementById("hdr-sub").textContent = `Latter v${data.version || '1.4.6'}`;
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
    const activeEl = document.activeElement;
    if (!activeEl || !document.getElementById("esp-sec-items")?.contains(activeEl)) {
      renderEspInspector();
    }
  }

  if (!INITIAL_FORM_LOADED || forceFormUpdate) {
    INITIAL_FORM_LOADED = true;
    applyTheme(cfg.web_theme || "dark");

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
    showToast("Configuration saved");
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