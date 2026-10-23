"""Server-Side Web Companion Dashboard & REST API for Latter."""

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
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_PROFILE,
    CONF_DEVICE_SLUG,
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
    CONF_WEATHER_ENTITY,
    DEFAULT_ART_SIZE,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_DEVICE_PROFILE,
    DEFAULT_DOCK_APPS,
    DOMAIN,
)
from .coordinator import LatterCoordinator
from .room_engine import async_execute_room_action

_LOGGER = logging.getLogger(__name__)


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
    all_media_players: list[dict[str, str]] = []
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
            all_media_players.append(item)
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
    _, media_attrs = coordinator.get_active_media_payload()

    config_data = {
        CONF_DEVICE_SLUG: coordinator.device_slug,
        CONF_DEVICE_PROFILE: coordinator.get_opt(
            CONF_DEVICE_PROFILE, DEFAULT_DEVICE_PROFILE
        ),
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
        CONF_ART_SIZE: coordinator.art_size,
    }

    return {
        "entry_id": coordinator.entry.entry_id,
        "title": coordinator.entry.title,
        "version": "1.1.0",
        "config": config_data,
        "live": {
            "active_area_id": coordinator.active_area_id or "",
            "active_area_name": room_attrs.get("area_name", "Home"),
            "room_temp": room_attrs.get("room_temp"),
            "room_humidity": room_attrs.get("room_humidity"),
            "lights_on": room_attrs.get("lights_on", 0),
            "covers_open": room_attrs.get("covers_open", 0),
            "ble_closest_proxy": room_attrs.get("ble_closest_proxy", ""),
            "ble_packets_seen": room_attrs.get("ble_packets_seen", 0),
            "ble_rssi_by_room": room_attrs.get("ble_rssi_by_room", {}),
            "active_speaker": coordinator.active_speaker,
            "local_speaker": coordinator.local_speaker,
            "volume_entity": media_attrs.get("volume_entity", ""),
            "media_title": media_attrs.get("title", "Idle"),
            "media_artist": media_attrs.get("artist", "None"),
            "alarm_state": room_attrs.get("alarm_state", "none"),
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
        """Return live state, configuration, and entity catalog."""
        coordinator = self._resolve_coordinator(request, entry_id)
        if coordinator is None:
            return web.json_response(
                {"error": "Unauthorized or unknown entry"},
                status=HTTPStatus.FORBIDDEN,
            )
        payload = _build_companion_state_payload(self.hass, coordinator)
        return web.json_response(payload)

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        """Save updated configuration or execute a live test action."""
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

        if cmd == "set_active_area":
            area_id = str(body.get("area_id") or "")
            if area_id:
                coordinator.async_set_active_area(
                    area_id, sync_device_registry= bool(body.get("sync_device", False))
                )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "test_binding":
            entity_id = str(body.get("entity_id") or "").strip()
            action = str(body.get("action") or "toggle").strip()
            level = body.get("level")
            if entity_id:
                await async_execute_room_action(
                    self.hass,
                    entity_id=entity_id,
                    action=action,
                    level=int(level) if level is not None else None,
                )
            return web.json_response({"ok": True})

        if cmd == "save_config":
            incoming_cfg = body.get("config") or {}
            merged: dict[str, Any] = {
                **coordinator.entry.data,
                **(coordinator.entry.options or {}),
            }

            for k in (
                CONF_DEVICE_SLUG,
                CONF_DEVICE_PROFILE,
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
                CONF_ART_SIZE,
            ):
                if k in incoming_cfg:
                    val = incoming_cfg[k]
                    if k == CONF_ART_SIZE:
                        val = int(val or DEFAULT_ART_SIZE)
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
  :root {
    --bg: #0b111e;
    --card: #131c2e;
    --card-border: #1e293b;
    --text: #f1f5f9;
    --muted: #94a3b8;
    --accent: #00d2ff;
    --accent-2: #6366f1;
    --success: #10b981;
    --warn: #f59e0b;
    --danger: #ef4444;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: radial-gradient(circle at top right, #162238, var(--bg) 60%);
    color: var(--text);
    min-height: 100vh;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: rgba(19, 28, 46, 0.85);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--card-border);
    position: sticky;
    top: 0;
    z-index: 20;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .brand-badge {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    color: #0b111e;
    font-size: 18px;
    box-shadow: 0 0 16px rgba(0, 210, 255, 0.35);
  }
  .brand h1 {
    margin: 0;
    font-size: 18px;
    letter-spacing: 0.4px;
  }
  .brand small {
    color: var(--muted);
    font-size: 12px;
    display: block;
  }
  .actions {
    display: flex;
    gap: 10px;
    align-items: center;
  }
  button {
    background: linear-gradient(135deg, var(--accent), #0284c7);
    color: #08101d;
    border: none;
    padding: 9px 18px;
    border-radius: 8px;
    font-weight: 700;
    cursor: pointer;
    font-size: 13px;
    transition: transform 0.12s, opacity 0.15s;
  }
  button:hover { opacity: 0.92; }
  button:active { transform: scale(0.98); }
  button.secondary {
    background: #1e293b;
    color: var(--text);
    border: 1px solid #334155;
  }
  button.danger {
    background: rgba(239, 68, 68, 0.18);
    color: #fca5a5;
    border: 1px solid rgba(239, 68, 68, 0.35);
    padding: 6px 10px;
  }
  .container {
    max-width: 1120px;
    margin: 24px auto;
    padding: 0 16px 64px;
  }
  .tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }
  .tab {
    padding: 10px 18px;
    border-radius: 10px;
    background: var(--card);
    border: 1px solid var(--card-border);
    color: var(--muted);
    cursor: pointer;
    font-weight: 600;
    font-size: 13px;
  }
  .tab.active {
    color: var(--accent);
    border-color: var(--accent);
    background: rgba(0, 210, 255, 0.08);
  }
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 18px;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    padding: 20px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  }
  .card h2 {
    margin: 0 0 6px;
    font-size: 16px;
    color: var(--text);
  }
  .card p.desc {
    margin: 0 0 16px;
    font-size: 12.5px;
    color: var(--muted);
    line-height: 1.45;
  }
  .field {
    margin-bottom: 14px;
  }
  .field label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: var(--muted);
    margin-bottom: 6px;
  }
  select, input[type="text"] {
    width: 100%;
    padding: 9px 12px;
    border-radius: 8px;
    border: 1px solid #334155;
    background: #0f172a;
    color: var(--text);
    font-size: 13px;
  }
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    font-size: 13px;
  }
  .stat-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 16px;
  }
  .pill {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 10px 14px;
    flex: 1 1 130px;
  }
  .pill span {
    display: block;
    font-size: 11px;
    color: var(--muted);
  }
  .pill strong {
    font-size: 15px;
    color: var(--accent);
  }
  .rssi-bar {
    margin-bottom: 10px;
  }
  .rssi-header {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    margin-bottom: 4px;
  }
  .rssi-track {
    height: 8px;
    background: #0f172a;
    border-radius: 99px;
    overflow: hidden;
  }
  .rssi-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-2), var(--accent));
    border-radius: 99px;
    transition: width 0.3s ease;
  }
  .binding-row {
    display: grid;
    grid-template-columns: 1.1fr 1.6fr 0.9fr auto auto;
    gap: 8px;
    align-items: center;
    margin-bottom: 10px;
    background: #0f172a;
    padding: 10px;
    border-radius: 10px;
    border: 1px solid #1e293b;
  }
  @media (max-width: 720px) {
    .binding-row { grid-template-columns: 1fr; }
  }
  .toast {
    position: fixed;
    bottom: 20px;
    right: 20px;
    background: var(--success);
    color: #052e16;
    padding: 12px 20px;
    border-radius: 10px;
    font-weight: 700;
    font-size: 13px;
    display: none;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }
  .hidden { display: none !important; }
  .chip-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 8px;
  }
  .chip {
    background: rgba(0, 210, 255, 0.12);
    border: 1px solid rgba(0, 210, 255, 0.35);
    color: var(--text);
    padding: 5px 10px;
    border-radius: 99px;
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .chip b {
    cursor: pointer;
    color: #fca5a5;
  }
</style>
</head>
<body>
<header>
  <div class="brand">
    <div class="brand-badge">L</div>
    <div>
      <h1 id="hdr-title">Latter Companion Studio</h1>
      <small id="hdr-sub">Universal ESPHome Entity & Room Middleware</small>
    </div>
  </div>
  <div class="actions">
    <button class="secondary" onclick="refreshState()">Refresh</button>
    <button onclick="saveAllConfig()">Save Changes</button>
  </div>
</header>

<div class="container">
  <div class="tabs">
    <div class="tab active" onclick="switchTab('overview', this)">1. Overview & BLE Radar</div>
    <div class="tab" onclick="switchTab('media', this)">2. Media, Remotes & Alarm</div>
    <div class="tab" onclick="switchTab('mapper', this)">3. Universal Entity & Trigger Mapper</div>
    <div class="tab" onclick="switchTab('display', this)">4. UI, Dock & Display</div>
  </div>

  <!-- TAB 1: OVERVIEW & BLE RADAR -->
  <div id="tab-overview" class="grid">
    <div class="card">
      <h2>Live Device Telemetry</h2>
      <p class="desc">Real-time state of your ESPHome node without running an on-device web server.</p>
      <div class="stat-pills">
        <div class="pill"><span>Active Room</span><strong id="st-room">--</strong></div>
        <div class="pill"><span>Room Climate</span><strong id="st-climate">--</strong></div>
        <div class="pill"><span>Active Speaker</span><strong id="st-speaker">--</strong></div>
        <div class="pill"><span>Home Alarm</span><strong id="st-alarm">--</strong></div>
      </div>
      <div class="field">
        <label>ESPHome Device Slug</label>
        <input type="text" id="cfg-device_slug">
      </div>
      <div class="field">
        <label>Device Archetype / Profile</label>
        <select id="cfg-device_profile">
          <option value="mobile_display">Mobile Smart Display (Pocket Assistant)</option>
          <option value="stationary_display">Stationary Room Display / Wall Panel</option>
          <option value="headless_node">Headless Sensor / Button / Audio Node</option>
        </select>
      </div>
      <div class="field">
        <label>Quick Active Room Override (Instant Switch)</label>
        <select id="quick-area" onchange="quickSwitchArea(this.value)"></select>
      </div>
    </div>

    <div class="card">
      <h2>BLE Room Presence & Voice Sync Radar</h2>
      <p class="desc">Tracks your portable device's BLE iBeacon across fixed ESPHome BLE proxies in each room.</p>
      <div class="toggle-row">
        <span>Built-In ESPHome BLE Proxy Tracking (Zero-Config)</span>
        <input type="checkbox" id="cfg-native_ble_tracking">
      </div>
      <div class="toggle-row">
        <span>Auto-Switch Active Room When Walking Between Rooms</span>
        <input type="checkbox" id="cfg-ble_auto_switch">
      </div>
      <div class="toggle-row">
        <span>Sync Active Room to HA Device Registry (Room-Aware Voice Assistant)</span>
        <input type="checkbox" id="cfg-sync_device_area">
      </div>
      <div class="toggle-row">
        <span>Unified Area Handoff (Auto-link Room Speaker & Remote)</span>
        <input type="checkbox" id="cfg-area_handoff">
      </div>
      <div class="field" style="margin-top:12px;">
        <label>BLE iBeacon UUID</label>
        <input type="text" id="cfg-ble_beacon_uuid">
      </div>
      <div class="field">
        <label>External BLE Room Sensor Override (Optional Bermuda Sensor)</label>
        <select id="cfg-presence_entity"></select>
      </div>
      <h2 style="margin-top:18px;font-size:14px;">Live Room Proxy Signal Strength (EMA RSSI)</h2>
      <div id="rssi-container" style="margin-top:10px;"></div>
    </div>
  </div>

  <!-- TAB 2: MEDIA, REMOTES & ALARM -->
  <div id="tab-media" class="grid hidden">
    <div class="card">
      <h2>Music Assistant & AVR Volume Overrides</h2>
      <p class="desc">Bind your default Music Assistant player and optionally route volume control to a separate AV Receiver or amplifier.</p>
      <div class="field">
        <label>Default Music Assistant Speaker</label>
        <select id="cfg-default_speaker"></select>
      </div>
      <div class="field">
        <label>Volume Override 1: When Streaming to Speaker...</label>
        <select id="cfg-vol_speaker_1"></select>
      </div>
      <div class="field">
        <label>Volume Override 1: Control Volume on Entity (AVR / Number)...</label>
        <select id="cfg-vol_target_1"></select>
      </div>
      <div class="field">
        <label>Volume Override 2: When Streaming to Speaker...</label>
        <select id="cfg-vol_speaker_2"></select>
      </div>
      <div class="field">
        <label>Volume Override 2: Control Volume on Entity (AVR / Number)...</label>
        <select id="cfg-vol_target_2"></select>
      </div>
    </div>

    <div class="card">
      <h2>4-Slot TV / Media Remotes & Security Alarm</h2>
      <p class="desc">Replaces hardcoded YAML remote substitutions. Pick either the remote.* or media_player.* entity—Latter binds both automatically.</p>
      <div class="field">
        <label>TV / Media Remote Slot 1</label>
        <select id="cfg-remote_1"></select>
      </div>
      <div class="field">
        <label>TV / Media Remote Slot 2</label>
        <select id="cfg-remote_2"></select>
      </div>
      <div class="field">
        <label>TV / Media Remote Slot 3</label>
        <select id="cfg-remote_3"></select>
      </div>
      <div class="field">
        <label>TV / Media Remote Slot 4</label>
        <select id="cfg-remote_4"></select>
      </div>
      <hr style="border:0;border-top:1px solid #1e293b;margin:16px 0;">
      <div class="field">
        <label>Home Security Alarm Entity (alarm_control_panel)</label>
        <select id="cfg-alarm_entity"></select>
      </div>
      <div class="field">
        <label>Weather Provider Entity</label>
        <select id="cfg-weather_entity"></select>
      </div>
    </div>
  </div>

  <!-- TAB 3: UNIVERSAL ENTITY & TRIGGER MAPPER -->
  <div id="tab-mapper" class="grid hidden">
    <div class="card" style="grid-column: 1 / -1;">
      <h2>Universal Hardware Trigger & Slot Bindings (Headless or Display Nodes)</h2>
      <p class="desc">Map any custom button press, sensor trigger, or UI slot ID (e.g. <code>btn_1_single</code>, <code>btn_1_double</code>, <code>macro_goodnight</code>) to any Home Assistant entity—so ESPHome firmware never needs hardcoded entity IDs or YAML substitutions. Call <code>latter.trigger_binding</code> with <code>slot: "your_slot_id"</code> from ESPHome.</p>
      <div id="bindings-list"></div>
      <button class="secondary" onclick="addBindingRow('', '', 'toggle')">+ Add Trigger / Slot Binding</button>
    </div>

    <div class="card" style="grid-column: 1 / -1;">
      <h2>Pinned Room / Home Entities</h2>
      <p class="desc">Pin specific entities so they always appear at the top of your device's Room / Home control list regardless of area.</p>
      <div style="display:flex;gap:10px;">
        <select id="pin-entity-picker"></select>
        <button class="secondary" onclick="addPinnedEntity()">Pin Entity</button>
      </div>
      <div id="pinned-chips" class="chip-list"></div>
    </div>
  </div>

  <!-- TAB 4: UI, DOCK & DISPLAY -->
  <div id="tab-display" class="grid hidden">
    <div class="card">
      <h2>Home Dock & Display Settings</h2>
      <p class="desc">Customize the comma-separated order of apps shown in the sliding Home Dock on display devices and configure Pillow JPEG artwork scaling.</p>
      <div class="field">
        <label>Home Dock App Order (comma-separated)</label>
        <input type="text" id="cfg-dock_apps" placeholder="music,room,weather,remote,calendar,games,tools">
      </div>
      <div class="field">
        <label>Album Art & Wallpaper Proxy Resolution</label>
        <select id="cfg-art_size">
          <option value="466">466x466 (Full Native AMOLED)</option>
          <option value="233">233x233 (Fast Low-Bandwidth Thumbnail)</option>
        </select>
      </div>
      <div class="field">
        <label>Default Room / Startup Area Fallback</label>
        <select id="cfg-default_area"></select>
      </div>
    </div>
  </div>
</div>

<div id="toast" class="toast">Saved!</div>

<script>
const API_URL = window.location.pathname + "/api" + window.location.search;
let STATE = null;
let PINNED = [];

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.style.display = "block";
  setTimeout(() => { t.style.display = "none"; }, 2600);
}

function switchTab(tabId, el) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  el.classList.add("active");
  ["overview", "media", "mapper", "display"].forEach(id => {
    document.getElementById("tab-" + id).classList.toggle("hidden", id !== tabId);
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
  items.forEach(item => {
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
    box.innerHTML = `<p class="desc">No BLE iBeacon packets received recently (Total seen: ${packetsSeen || 0}). Turn ON the BLE Room Beacon on your device to see live room proxy signal bars.</p>`;
    return;
  }
  entries.sort((a, b) => b[1] - a[1]);
  box.innerHTML = entries.map(([room, dbm]) => {
    const pct = Math.max(8, Math.min(100, Math.round(((dbm + 100) / 60) * 100)));
    return `<div class="rssi-bar">
      <div class="rssi-header"><strong>${room}</strong><span>${dbm} dBm</span></div>
      <div class="rssi-track"><div class="rssi-fill" style="width:${pct}%"></div></div>
    </div>`;
  }).join("");
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
  }
}

function removePinned(idx) {
  PINNED.splice(idx, 1);
  renderPinnedChips();
}

function addBindingRow(slot="", entity_id="", action="toggle") {
  const list = document.getElementById("bindings-list");
  const row = document.createElement("div");
  row.className = "binding-row";
  const entOptions = (STATE?.catalog?.bindable_entities || []).map(e =>
    `<option value="${e.id}" ${e.id === entity_id ? 'selected' : ''}>${e.name}</option>`
  ).join("");
  row.innerHTML = `
    <input type="text" class="b-slot" placeholder="Slot ID (e.g. button_1)" value="${slot}">
    <select class="b-ent"><option value="">— Target Entity —</option>${entOptions}</select>
    <select class="b-act">
      <option value="toggle" ${action==='toggle'?'selected':''}>Toggle</option>
      <option value="turn_on" ${action==='turn_on'?'selected':''}>Turn On</option>
      <option value="turn_off" ${action==='turn_off'?'selected':''}>Turn Off</option>
      <option value="step_up" ${action==='step_up'?'selected':''}>Step Up (+10%)</option>
      <option value="step_down" ${action==='step_down'?'selected':''}>Step Down (-10%)</option>
    </select>
    <button class="secondary" onclick="testBindingRow(this)">Test</button>
    <button class="danger" onclick="this.parentElement.remove()">✕</button>
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

function applyStateToDom(data) {
  STATE = data;
  const cfg = data.config;
  const live = data.live;
  const cat = data.catalog;

  document.getElementById("hdr-title").textContent = `${data.title} — Web Companion`;
  document.getElementById("st-room").textContent = live.active_area_name || "Home";
  const tempStr = live.room_temp != null ? `${live.room_temp}°` : "--";
  const humStr = live.room_humidity != null ? ` • ${live.room_humidity}%` : "";
  document.getElementById("st-climate").textContent = tempStr + humStr;
  document.getElementById("st-speaker").textContent = (live.active_speaker || "").replace("media_player.", "");
  document.getElementById("st-alarm").textContent = (live.alarm_state || "none").toUpperCase();

  document.getElementById("cfg-device_slug").value = cfg.device_slug || "";
  document.getElementById("cfg-device_profile").value = cfg.device_profile || "mobile_display";
  document.getElementById("cfg-native_ble_tracking").checked = !!cfg.native_ble_tracking;
  document.getElementById("cfg-ble_auto_switch").checked = !!cfg.ble_auto_switch;
  document.getElementById("cfg-sync_device_area").checked = !!cfg.sync_device_area;
  document.getElementById("cfg-area_handoff").checked = !!cfg.area_handoff;
  document.getElementById("cfg-ble_beacon_uuid").value = cfg.ble_beacon_uuid || "";
  document.getElementById("cfg-dock_apps").value = cfg.dock_apps || "";
  document.getElementById("cfg-art_size").value = String(cfg.art_size || 466);

  populateSelect("quick-area", cat.areas, live.active_area_id, false);
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

  renderRssiBars(live.ble_rssi_by_room, live.ble_packets_seen);
}

async function refreshState() {
  const resp = await fetch(API_URL);
  if (resp.ok) {
    const data = await resp.json();
    applyStateToDom(data);
  }
}

async function quickSwitchArea(areaId) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "set_active_area", area_id: areaId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json());
    showToast("Switched active room!");
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
    applyStateToDom(await resp.json());
    showToast("Configuration saved & applied!");
  }
}

refreshState();
setInterval(refreshState, 5000);
</script>
</body>
</html>
"""


class LatterCompanionDashboardView(HomeAssistantView):
    """Serves the Latter Server-Side Web Companion Dashboard HTML."""

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
                text="Invalid or missing Latter companion token. Open via the 'Visit' link on the Latter device page in Home Assistant.",
            )

        return web.Response(
            body=COMPANION_HTML_TEMPLATE,
            content_type="text/html",
            charset="utf-8",
        )