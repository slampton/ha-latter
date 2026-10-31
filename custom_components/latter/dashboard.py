"""Server-Side Web Companion Studio & REST API for Latter (Global System + Per-Device)."""

from __future__ import annotations

from http import HTTPStatus
import logging
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .ble_engine import (
    _iter_devices,
    get_all_areas_presence_summary,
    get_ble_fabric,
    get_discovered_ble_candidates,
)
from .backup_engine import (
    async_apply_profile_to_coordinators,
    async_create_vault_backup,
    async_delete_vault_backup,
    async_get_vault_backup,
    async_list_vault_backups,
    async_restore_backup_bundle,
    build_backup_bundle,
    capture_profile_from_coordinator,
    get_device_groups_and_profiles,
)
from .browse_engine import is_music_assistant_player
from .const import (
    API_BRAND_ICON_PATH,
    API_SIDEBAR_ICON_JS_PATH,
    API_STUDIO_ROOT_PATH,
    API_COMPANION_API_PATH,
    API_COMPANION_UI_PATH,
    CONF_ALARM_ENTITY,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_FUSION_CONFIG,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_ASSIGNED_PERSON,
    CONF_ASSIGNED_ROLE,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_BLE_AREA_OFFSETS,
    CONF_CALENDAR_ENTITIES,
    CONF_CAMERA_ENTITIES,
    CONF_CAMERA_ENTITY,
    CONF_GARAGE_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_THERMOSTAT_ENTITY,
    CONF_VACUUM_ENTITY,
    CONF_COMPANION_BASE_URL,
    CONF_CUSTOM_PALETTES,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DOORBELL_ANC_MODE,
    CONF_SIP_DTMF_CODE,
    CONF_SIP_ENABLED,
    CONF_SIP_EXTENSION,
    CONF_SIP_PASSWORD,
    CONF_SIP_PORT,
    CONF_SIP_SERVER,
    CONF_SIP_SPEED_DIALS,
    CONF_SIP_USERNAME,
    DEFAULT_DOORBELL_ANC_MODE,
    DEFAULT_SIP_DTMF_CODE,
    DEFAULT_SIP_PORT,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_GROUPS,
    CONF_DEVICE_PROFILE,
    CONF_DEVICE_SLUG,
    CONF_SAVED_PROFILES,
    DEFAULT_DEVICE_GROUP,
    CONF_DISPLAY_SHAPE,
    CONF_DOCK_APPS,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PRESENCE_ENTITY,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_REMOTE_GROUPS,
    CONF_REMOTES_LIST,
    CONF_SYNC_DEVICE_AREA,
    CONF_VOLUME_OVERRIDES,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_SITE_ID,
    CONF_VPN_CLIENT_IP,
    CONF_VPN_ENABLED,
    CONF_VPN_ENDPOINT,
    CONF_VPN_HA_IP,
    CONF_VPN_HOTSPOT_SSID,
    CONF_VPN_PRESHARED_KEY,
    CONF_VPN_PRIVATE_KEY,
    CONF_VPN_PUBLIC_KEY,
    CONF_VPN_SERVER_PUBLIC_KEY,
    CONF_VPN_SUBNET,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    CONF_WEB_THEME,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DEFAULT_ART_SIZE,
    DEFAULT_DEVICE_PROFILE,
    DEFAULT_PAGE_SIZE,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DEFAULT_WEB_THEME,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
    INTEGRATION_VERSION,
    normalize_device_slug,
)
from .coordinator import LatterCoordinator
from .repairs import async_audit_coordinator_health
from .area_engine import (
    async_execute_area_action,
    find_esphome_device_id,
    get_area_entities,
    get_esphome_device_entities,
)
from .vpn_engine import allocate_next_tunnel_ip, build_wireguard_provisioning_snippets, generate_wireguard_keypair
from .wallpaper_engine import (
    async_refresh_wallpaper_cache,
    delete_uploaded_wallpaper,
    list_wallpaper_catalog,
    save_uploaded_wallpaper,
)

_LOGGER = logging.getLogger(__name__)

MAX_INTERNAL_LOGS = 150


def log_studio_event(
    hass: HomeAssistant, level: str, source: str, message: str
) -> None:
    """Append a timestamped diagnostic event to Latter's in-memory Studio ring buffer."""
    from homeassistant.util import dt as dt_util

    domain_data = hass.data.setdefault(DOMAIN, {})
    logs: list[dict[str, str]] = domain_data.setdefault("internal_logs", [])
    ts = dt_util.now().strftime("%Y-%m-%d %H:%M:%S")
    logs.insert(
        0,
        {
            "ts": ts,
            "level": level.upper(),
            "source": source,
            "message": str(message),
        },
    )
    del logs[MAX_INTERNAL_LOGS:]


def _get_combined_system_and_studio_logs(hass: HomeAssistant) -> list[dict[str, str]]:
    """Combine Latter Studio events with live entries from Home Assistant's native system_log handler."""
    from datetime import datetime

    combined: list[dict[str, str]] = list(
        hass.data.get(DOMAIN, {}).get("internal_logs", [])
    )

    # Pull relevant entries from Home Assistant's native system_log integration
    try:
        sys_log = hass.data.get("system_log")
        records = getattr(sys_log, "records", None)
        if records is not None:
            raw_list = list(records.values()) if hasattr(records, "values") else list(records)
            for rec in reversed(raw_list[-200:]):
                d = rec.to_dict() if hasattr(rec, "to_dict") else {}
                logger_name = str(d.get("name") or "")
                msgs = d.get("message")
                msg_str = str(msgs[0] if isinstance(msgs, list) and msgs else (msgs or ""))
                exc_str = str(d.get("exception") or "").strip()
                haystack = f"{logger_name} {msg_str} {exc_str}".lower()
                if not any(
                    k in haystack
                    for k in ("latter", "esphome", "aioesphomeapi", "sendspin", "music_assistant", "assist_satellite")
                ):
                    continue
                ts_val = d.get("timestamp")
                ts_str = (
                    datetime.fromtimestamp(float(ts_val)).strftime("%Y-%m-%d %H:%M:%S")
                    if ts_val
                    else ""
                )
                full_msg = f"{msg_str}\n{exc_str}".strip() if exc_str else msg_str
                combined.append(
                    {
                        "ts": ts_str,
                        "level": str(d.get("level") or "ERROR").upper(),
                        "source": f"ha:{logger_name}",
                        "message": full_msg[:600],
                    }
                )
    except Exception:  # noqa: BLE001
        pass

    combined.sort(key=lambda x: x.get("ts") or "", reverse=True)
    return combined[:MAX_INTERNAL_LOGS]

def _normalize_web_theme(raw_theme: Any) -> str:
    """Normalize theme selection ('ha_auto', 'ha_dark', 'ha_light', or an installed HA theme name)."""
    val = str(raw_theme or "ha_auto").strip()
    if not val or val in ("system", "auto"):
        return "ha_auto"
    if val == "dark":
        return "ha_dark"
    if val == "light":
        return "ha_light"
    return val


def _get_ha_installed_themes(hass: HomeAssistant) -> dict[str, dict[str, str]]:
    """Extract installed Home Assistant themes and their core CSS variables from frontend storage."""
    out: dict[str, dict[str, str]] = {}
    fe_data = hass.data.get("frontend_themes") or hass.data.get("frontend", {})
    raw_themes = getattr(fe_data, "themes", None) or (
        fe_data.get("themes") if isinstance(fe_data, dict) else None
    )
    if not isinstance(raw_themes, dict):
        return out

    wanted_keys = (
        "primary-color",
        "accent-color",
        "primary-background-color",
        "secondary-background-color",
        "card-background-color",
        "ha-card-background",
        "primary-text-color",
        "secondary-text-color",
        "divider-color",
        "success-color",
        "warning-color",
        "error-color",
    )
    for t_name, t_dict in raw_themes.items():
        if not isinstance(t_dict, dict):
            continue
        extracted: dict[str, str] = {}
        for k in wanted_keys:
            if k in t_dict and isinstance(t_dict[k], str):
                extracted[k] = t_dict[k]
        # Also check nested modes: {"modes": {"dark": {...}, "light": {...}}}
        modes = t_dict.get("modes")
        if isinstance(modes, dict):
            mode_dict = modes.get("dark") or modes.get("light") or {}
            if isinstance(mode_dict, dict):
                for k in wanted_keys:
                    if k not in extracted and k in mode_dict and isinstance(mode_dict[k], str):
                        extracted[k] = mode_dict[k]
        if extracted:
            out[str(t_name)] = extracted
    return out


def _get_all_coordinators(hass: HomeAssistant) -> list[LatterCoordinator]:
    """Return all active LatterCoordinator instances sorted by device_slug."""
    domain_data = hass.data.get(DOMAIN, {})
    coords = [
        v for v in domain_data.values() if isinstance(v, LatterCoordinator)
    ]
    return sorted(coords, key=lambda c: c.device_slug)


async def _async_save_and_broadcast_global_config(
    hass: HomeAssistant, updates: dict[str, Any]
) -> None:
    """Persist updates to `.storage/latter.system` and broadcast to all loaded device coordinators."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    global_cfg: dict[str, Any] = domain_data.setdefault(DATA_GLOBAL_CONFIG, {})
    global_cfg.update(updates)
    store = domain_data.get(DATA_GLOBAL_STORE)
    if store is not None:
        await store.async_save(global_cfg)
    for coord in _get_all_coordinators(hass):
        await coord.async_on_global_config_updated()


def _build_system_shared_controls(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Discover shared ESPHome select/switch/number controls across all onboarded devices for 1-click System Sync."""
    coords = _get_all_coordinators(hass)
    by_label: dict[str, dict[str, Any]] = {}
    for coord in coords:
        esp_info = get_esphome_device_entities(hass, coord.device_slug)
        for sec in esp_info.get("sections", []):
            sec_id = sec.get("id", "")
            if sec_id not in ("voice", "sleep", "display", "sound", "music", "area"):
                continue
            for item in sec.get("items", []):
                dom = item.get("domain")
                if dom not in ("select", "switch", "number"):
                    continue
                lbl = str(item.get("name") or "").strip()
                if not lbl:
                    continue
                key = f"{sec_id}:{dom}:{lbl.lower()}"
                bucket = by_label.setdefault(
                    key,
                    {
                        "key": key,
                        "section": sec_id,
                        "section_title": sec.get("title", sec_id.title()),
                        "name": lbl,
                        "domain": dom,
                        "state": item.get("state"),
                        "options": item.get("options", []),
                        "min": item.get("min"),
                        "max": item.get("max"),
                        "step": item.get("step"),
                        "unit": item.get("unit", ""),
                        "targets": [],
                    },
                )
                bucket["targets"].append(
                    {
                        "device_slug": coord.device_slug,
                        "device_group": coord.device_group,
                        "device_profile": coord.device_profile,
                        "entity_id": item.get("entity_id"),
                        "state": item.get("state"),
                    }
                )
    return sorted(
        by_label.values(),
        key=lambda x: (x["section"], x["name"].lower()),
    )


_SECRET_MASK = "••••••••"


def _build_companion_state_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    *,
    include_vpn_secrets: bool = False,
    uid: str = "",
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
    cameras_list: list[dict[str, Any]] = []
    climates_list: list[dict[str, str]] = []
    locks_list: list[dict[str, str]] = []
    garages_list: list[dict[str, str]] = []
    vacuums_list: list[dict[str, str]] = []
    weathers_list: list[dict[str, str]] = []
    calendars_list: list[dict[str, str]] = []
    persons_list: list[dict[str, str]] = []
    presence_sensors: list[dict[str, str]] = []

    allowed_cams_set = set(coordinator.camera_entities)
    if coordinator.camera_entity:
        allowed_cams_set.add(coordinator.camera_entity)

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
            cam_item: dict[str, Any] = dict(item)
            if ent_id in allowed_cams_set:
                cam_sig = coordinator.sign_resource(f"camera:{ent_id}")
                cam_item["preview_url"] = (
                    f"/api/latter/camera/{coordinator.device_slug}"
                    f"?entity_id={quote(ent_id, safe='')}&w=320&h=180&shape=square&sig={cam_sig}"
                )
            cameras_list.append(cam_item)
        elif domain == "climate":
            climates_list.append(item)
        elif domain == "lock":
            locks_list.append(item)
        elif domain == "cover":
            garages_list.append(item)
        elif domain == "vacuum":
            vacuums_list.append(item)
        elif domain == "weather":
            weathers_list.append(item)
        elif domain == "calendar":
            calendars_list.append(item)
        elif domain == "person":
            p_slug = re.sub(r"[^a-z0-9]+", "_", ent_id.split(".", 1)[-1].lower()).strip("_")
            persons_list.append(
                {
                    "id": ent_id,
                    "name": f"{friendly} (sensor.{p_slug}_current_area)",
                    "friendly": friendly,
                    "area_sensor": f"sensor.{p_slug}_current_area",
                }
            )
        elif domain in ("sensor", "device_tracker", "input_text"):
            presence_sensors.append(item)

    _, area_attrs = coordinator.get_area_context_payload()
    media_state, media_attrs = coordinator.get_active_media_payload()
    _, remote_attrs = coordinator.get_remote_config_payload()
    esphome_inspector = get_esphome_device_entities(
        hass, coordinator.device_slug
    )
    active_area_cards = get_area_entities(
        hass,
        area_id=coordinator.active_area_id,
        domain_filter="all",
        local_speaker=coordinator.local_speaker,
    )
    wallpapers_catalog = list_wallpaper_catalog(
        hass,
        coordinator.device_slug,
        coordinator.wallpaper_source,
        coordinator.wallpaper_favorites,
        sign_resource=coordinator.sign_resource,
        display_shape=coordinator.display_shape,
    )

    esphome_svcs = hass.services.async_services().get("esphome", {})
    slug = coordinator.device_slug
    has_native_slots = any(
        (s.endswith("_set_browse_slots") or s.endswith("_set_area_slots")) and slug in s
        for s in esphome_svcs
    )
    has_mixin_ping = any(
        s.endswith("_latter_ping") and slug in s for s in esphome_svcs
    )

    sec_ids = {s.get("id") for s in esphome_inspector.get("sections", []) if s.get("count", 0) > 0}
    all_esp_items: list[dict[str, Any]] = []
    for s in esphome_inspector.get("sections", []):
        all_esp_items.extend(s.get("items") or [])

    has_vpn_entities = any(
        "vpn" in str(it.get("entity_id") or "").lower()
        or "wireguard" in str(it.get("entity_id") or "").lower()
        or "vpn" in str(it.get("name") or "").lower()
        for it in all_esp_items
    )
    has_ble_beacon_entity = any(
        "ble" in str(it.get("entity_id") or "").lower()
        and "beacon" in str(it.get("entity_id") or "").lower()
        for it in all_esp_items
    )
    local_spk = coordinator.local_speaker
    has_display = has_native_slots or ("display" in sec_ids) or ("home" in sec_ids)
    has_power = ("sleep" in sec_ids) or ("battery" in sec_ids)
    has_voice = "voice" in sec_ids
    has_audio = has_native_slots or bool(local_spk) or ("sound" in sec_ids) or ("music" in sec_ids)

    if has_native_slots:
        dev_tier = 1
        dev_tier_label = "Tier 1: Native Latter"
    elif has_mixin_ping or has_vpn_entities or has_ble_beacon_entity:
        dev_tier = 2
        dev_tier_label = "Tier 2: Mixin Enabled"
    else:
        dev_tier = 3
        dev_tier_label = "Tier 3: Bridged Device"

    dev_model_meta = (
        f"{esphome_inspector.get('device', {}).get('model', '')} "
        f"{esphome_inspector.get('device', {}).get('sw_version', '')} "
        f"{coordinator.art_size} {slug}"
    ).lower()
    is_no_imu_hw = any(k in dev_model_meta for k in ("p4_35", "p4-35", "p4_4b", "p4-4b", "320x480", "720"))
    has_imu = (not is_no_imu_hw) and (
        has_native_slots
        or any("imu" in str(it.get("entity_id") or "").lower() for it in all_esp_items)
    )
    device_capabilities = {
        "tier": dev_tier,
        "tier_label": dev_tier_label,
        "has_display": has_display,
        "has_imu": has_imu,
        "has_power": has_power,
        "has_voice": has_voice,
        "has_audio": has_audio,
        "has_ble_beacon": has_native_slots or has_ble_beacon_entity,
        "has_vpn_mixin": has_vpn_entities or coordinator.vpn_enabled,
        "is_roaming_device": coordinator.is_roaming_device,
        "total_entities": len(all_esp_items),
    }

    saved_theme = _normalize_web_theme(
        coordinator.get_opt(CONF_WEB_THEME, DEFAULT_WEB_THEME)
    )

    config_data = {
        CONF_DEVICE_SLUG: coordinator.device_slug,
        CONF_DEVICE_PROFILE: coordinator.get_opt(
            CONF_DEVICE_PROFILE, DEFAULT_DEVICE_PROFILE
        ),
        CONF_DEVICE_GROUP: coordinator.device_group,
        CONF_DISPLAY_SHAPE: coordinator.display_shape,
        CONF_DEFAULT_PAGE_SIZE: coordinator.default_page_size,
        CONF_WEB_THEME: saved_theme,
        CONF_COMPANION_BASE_URL: coordinator.companion_base_url,
        CONF_DEFAULT_SPEAKER: coordinator.get_opt(
            CONF_DEFAULT_SPEAKER, coordinator.active_speaker
        ),
        CONF_VOLUME_OVERRIDES: [
            {"speaker": k, "target": v}
            for k, v in coordinator.volume_overrides.items()
        ],
        CONF_DEFAULT_AREA: coordinator.get_opt(CONF_DEFAULT_AREA, ""),
        CONF_NATIVE_BLE_TRACKING: coordinator.native_ble_tracking_enabled,
        CONF_BLE_BEACON_UUID: coordinator.ble_beacon_uuid,
        CONF_BLE_TARGET_ADDRESS: coordinator.ble_target_address,
        CONF_BLE_AREA_OFFSETS: coordinator.ble_area_offsets,
        CONF_AREA_FUSION_CONFIG: coordinator.get_opt(CONF_AREA_FUSION_CONFIG, {}) or {},
        CONF_PRESENCE_ENTITY: coordinator.presence_entity or "",
        CONF_ASSIGNED_PERSON: coordinator.assigned_person,
        CONF_ASSIGNED_ROLE: coordinator.assigned_role,
        CONF_BLE_AUTO_SWITCH: coordinator.ble_auto_switch_enabled,
        CONF_SYNC_DEVICE_AREA: coordinator.sync_device_area_enabled,
        CONF_AREA_FOLLOW_DWELL_S: coordinator.area_follow_dwell_s,
        CONF_AREA_HANDOFF: coordinator.area_handoff_enabled,
        CONF_ALARM_ENTITY: coordinator.get_opt(CONF_ALARM_ENTITY, "")
        or coordinator.alarm_entity
        or "",
        CONF_CAMERA_ENTITY: coordinator.camera_entity or "",
        CONF_CAMERA_ENTITIES: coordinator.camera_entities,
        CONF_THERMOSTAT_ENTITY: coordinator.thermostat_entity or "",
        CONF_LOCK_ENTITY: coordinator.lock_entity or "",
        CONF_GARAGE_ENTITY: coordinator.garage_entity or "",
        CONF_VACUUM_ENTITY: coordinator.vacuum_entity or "",
        CONF_REMOTES_LIST: coordinator.get_remote_entities_list(),
        CONF_REMOTE_GROUPS: coordinator.remote_groups,
        CONF_DEVICE_REMOTE_GROUP: coordinator.device_remote_group,
        CONF_WEATHER_ENTITY: coordinator.weather_entity or "",
        CONF_CALENDAR_ENTITIES: coordinator.calendar_entities,
        CONF_CUSTOM_PALETTES: coordinator.custom_palettes,
        CONF_DEVICE_CUSTOM_COLOR: coordinator.device_custom_color,
        CONF_DOORBELL_ANC_MODE: str(
            coordinator.get_opt(CONF_DOORBELL_ANC_MODE, coordinator.doorbell_anc_mode)
            or DEFAULT_DOORBELL_ANC_MODE
        ),
        CONF_SIP_ENABLED: bool(coordinator.get_opt(CONF_SIP_ENABLED, False)),
        CONF_SIP_SERVER: str(coordinator.get_opt(CONF_SIP_SERVER, "") or ""),
        CONF_SIP_PORT: int(coordinator.get_opt(CONF_SIP_PORT, DEFAULT_SIP_PORT) or DEFAULT_SIP_PORT),
        CONF_SIP_USERNAME: str(coordinator.get_opt(CONF_SIP_USERNAME, "latter") or "latter"),
        CONF_SIP_PASSWORD: (
            _SECRET_MASK
            if str(coordinator.get_opt(CONF_SIP_PASSWORD, "") or "")
            else ""
        ),
        "has_sip_password": bool(
            str(coordinator.get_opt(CONF_SIP_PASSWORD, "") or "")
        ),
        CONF_SIP_EXTENSION: str(coordinator.get_opt(CONF_SIP_EXTENSION, "101") or "101"),
        CONF_SIP_DTMF_CODE: str(coordinator.get_opt(CONF_SIP_DTMF_CODE, DEFAULT_SIP_DTMF_CODE) or DEFAULT_SIP_DTMF_CODE),
        CONF_SIP_SPEED_DIALS: str(coordinator.get_opt(CONF_SIP_SPEED_DIALS, "") or ""),
        CONF_DOCK_APPS: coordinator.dock_apps_csv,
        CONF_WALLPAPER_SOURCE: coordinator.wallpaper_source,
        CONF_WALLPAPER_FAVORITES: coordinator.wallpaper_favorites,
        CONF_WALLPAPER_CYCLE_MINUTES: coordinator.wallpaper_cycle_minutes,
        CONF_ART_SIZE: coordinator.art_size,
        CONF_SITE_ID: coordinator.site_id,
        CONF_VPN_ENDPOINT: str(coordinator.get_opt(CONF_VPN_ENDPOINT, "") or ""),
        CONF_VPN_SERVER_PUBLIC_KEY: str(coordinator.get_opt(CONF_VPN_SERVER_PUBLIC_KEY, "") or ""),
        CONF_VPN_SUBNET: str(coordinator.get_opt(CONF_VPN_SUBNET, "10.10.10.0/24") or "10.10.10.0/24"),
        CONF_VPN_HA_IP: str(coordinator.get_opt(CONF_VPN_HA_IP, "10.10.10.1") or "10.10.10.1"),
        CONF_VPN_ENABLED: coordinator.vpn_enabled,
        CONF_VPN_CLIENT_IP: coordinator.vpn_client_ip,
        CONF_VPN_PRIVATE_KEY: (
            str(coordinator.get_opt(CONF_VPN_PRIVATE_KEY, "") or "")
            if include_vpn_secrets
            else (
                _SECRET_MASK
                if str(coordinator.get_opt(CONF_VPN_PRIVATE_KEY, "") or "")
                else ""
            )
        ),
        "has_vpn_private_key": bool(
            str(coordinator.get_opt(CONF_VPN_PRIVATE_KEY, "") or "")
        ),
        CONF_VPN_PUBLIC_KEY: str(coordinator.get_opt(CONF_VPN_PUBLIC_KEY, "") or ""),
        CONF_VPN_PRESHARED_KEY: (
            str(coordinator.get_opt(CONF_VPN_PRESHARED_KEY, "") or "")
            if include_vpn_secrets
            else (
                _SECRET_MASK
                if str(coordinator.get_opt(CONF_VPN_PRESHARED_KEY, "") or "")
                else ""
            )
        ),
        "has_vpn_preshared_key": bool(
            str(coordinator.get_opt(CONF_VPN_PRESHARED_KEY, "") or "")
        ),
        CONF_VPN_HOTSPOT_SSID: str(coordinator.get_opt(CONF_VPN_HOTSPOT_SSID, "") or ""),
    }

    try:
        health_warnings = async_audit_coordinator_health(hass, coordinator)
    except Exception:  # noqa: BLE001
        health_warnings = []

    ble_survey_rows: list[dict[str, Any]] = []
    if coordinator._ble_tracker is not None and hasattr(
        coordinator._ble_tracker, "get_area_calibration_telemetry"
    ):
        ble_survey_rows = coordinator._ble_tracker.get_area_calibration_telemetry()

    device_groups, saved_profiles = get_device_groups_and_profiles(hass)
    group_name_map = {g["id"]: g["name"] for g in device_groups if isinstance(g, dict) and g.get("id")}

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    system_devices: list[dict[str, Any]] = []
    for c in _get_all_coordinators(hass):
        c_area_name, c_area_attrs = c.get_area_context_payload()
        c_media_state, _ = c.get_active_media_payload()
        c_grp = c.device_group
        c_has_audio = bool(c.local_speaker) or any(
            s.endswith("_set_browse_slots") and c.device_slug in s
            for s in esphome_svcs
        )
        c_has_ble = bool(
            c.native_ble_tracking_enabled
            or c._ble_tracker is not None
            or any(
                (s.endswith("_set_browse_slots") or s.endswith("_set_area_slots"))
                and c.device_slug in s
                for s in esphome_svcs
            )
            or hass.states.get(f"switch.{c.device_slug}_area_ble_presence_beacon") is not None
            or hass.states.get(f"switch.{c.device_slug}_ble_presence_beacon") is not None
        )
        c_survey_rows = (
            c._ble_tracker.get_area_calibration_telemetry()
            if c._ble_tracker is not None
            and hasattr(c._ble_tracker, "get_area_calibration_telemetry")
            else []
        )
        c_packets_seen = (
            c._ble_tracker.packets_seen if c._ble_tracker is not None else 0
        )
        c_bat_st = hass.states.get(f"sensor.{c.device_slug}_battery_level")
        c_chg_st = hass.states.get(f"binary_sensor.{c.device_slug}_battery_charging")
        c_usb_st = hass.states.get(f"binary_sensor.{c.device_slug}_usb_power_connected")
        c_wifi_st = (
            hass.states.get(f"sensor.{c.device_slug}_wi_fi_signal")
            or hass.states.get(f"sensor.{c.device_slug}_wifi_signal")
            or hass.states.get(f"sensor.{c.device_slug}_system_wi_fi_signal")
        )
        c_ip_st = hass.states.get(f"sensor.{c.device_slug}_ip_address")
        c_ip_val = (
            str(c_ip_st.state)
            if (c_ip_st and c_ip_st.state not in ("unavailable", "unknown", ""))
            else ""
        )
        c_bat_val: int | None = None
        if c_bat_st and c_bat_st.state not in ("unavailable", "unknown", ""):
            try:
                c_bat_val = int(round(float(c_bat_st.state)))
            except ValueError:
                c_bat_val = None
        c_wifi_val: int | None = None
        if c_wifi_st and c_wifi_st.state not in ("unavailable", "unknown", ""):
            try:
                c_wifi_val = int(round(float(c_wifi_st.state)))
            except ValueError:
                c_wifi_val = None

        c_dev_id = find_esphome_device_id(hass, c.device_slug)
        c_dev_entry = dev_reg.async_get(c_dev_id) if c_dev_id else None
        raw_model = str((c_dev_entry.model if c_dev_entry else "") or "").strip()
        m_low = f"{raw_model} {c.device_slug}".lower()
        c_is_latter_native = bool(
            c.device_profile != "ble_beacon"
            and (
                any(
                    (
                        s.endswith("_set_browse_slots")
                        or s.endswith("_set_area_slots")
                        or s.endswith("_show_notification")
                    )
                    and c.device_slug in s
                    for s in esphome_svcs
                )
                or hass.states.get(f"update.{c.device_slug}_project_firmware") is not None
                or "latter" in m_low
            )
        )
        if c.device_profile == "ble_beacon":
            c_model_label = (
                "Private BLE (Phone/Watch)"
                if "private_ble" in c.ble_target_address or "." in c.ble_target_address
                else "BLE Beacon / Tag"
            )
        elif "175" in m_low or "466x466" in m_low:
            c_model_label = 'Round Display 1.75"'
        elif "206" in m_low or "410x502" in m_low:
            c_model_label = 'Wearable Display 2.06"'
        elif "216" in m_low or "mobile_assistant" in m_low or "mobile-assistant" in m_low:
            c_model_label = 'Mobile Assistant 2.16"'
        elif "p4_35" in m_low or "p4-35" in m_low or "remote_assistant" in m_low or "remote-assistant" in m_low:
            c_model_label = 'Remote Assistant 3.5" P4'
        elif "4b" in m_low or "desk_assistant" in m_low or "desk-assistant" in m_low:
            c_model_label = 'Desk Assistant 4.0" P4'
        else:
            c_model_label = raw_model or "ESPHome Node"

        # Area column: If a Home Assistant Area is assigned (and not a BLE-roaming device without a fixed area),
        # show the assigned Area name; otherwise show "Roaming".
        ha_assigned_area_id = (
            str(c_dev_entry.area_id or "").strip()
            if (c_dev_entry and not c.sync_device_area_enabled)
            else ""
        ) or str(c.get_opt(CONF_DEFAULT_AREA) or "").strip()
        if not ha_assigned_area_id and not c.native_ble_tracking_enabled and c_dev_entry and c_dev_entry.area_id:
            ha_assigned_area_id = str(c_dev_entry.area_id).strip()

        a_obj = area_reg.async_get_area(ha_assigned_area_id) if ha_assigned_area_id else None
        c_has_assigned_area = a_obj is not None
        c_area_label = a_obj.name if a_obj is not None else "Roaming"

        # Status column: "Update Available", "Online", or "Offline"
        c_upd_st = hass.states.get(f"update.{c.device_slug}_project_firmware")
        c_has_update = bool(c_upd_st and c_upd_st.state == "on")
        c_is_online = bool(c_wifi_val is not None or c_ip_val)
        if not c_is_online and c_dev_id:
            for e_reg in er.async_entries_for_device(ent_reg, c_dev_id):
                if e_reg.platform == "esphome":
                    st_e = hass.states.get(e_reg.entity_id)
                    if st_e and st_e.state not in ("unavailable", "unknown"):
                        c_is_online = True
                        break
                    if e_reg.domain == "update" and st_e and st_e.state == "on":
                        c_has_update = True
        if c.device_profile == "ble_beacon":
            c_away = c.is_device_away()
            c_seen = bool(c._ble_tracker and c._ble_tracker.packets_seen > 0 and not c_away)
            c_status_label = f"Online ({c_area_name})" if c_seen else ("Away" if c_away else "Scanning")
        else:
            c_status_label = (
                "Update Available"
                if c_has_update
                else ("Online" if c_is_online else "Offline")
            )

        system_devices.append(
            {
                "entry_id": c.entry.entry_id,
                "device_slug": c.device_slug,
                "title": (
                    str(c_dev_entry.name_by_user or c_dev_entry.name).strip()
                    if c_dev_entry and (c_dev_entry.name_by_user or c_dev_entry.name)
                    else c.device_slug.replace("_", " ").title()
                ),
                "model_label": c_model_label,
                "has_assigned_area": c_has_assigned_area,
                "area_label": c_area_label,
                "status_label": c_status_label,
                "device_profile": c.device_profile,
                "device_group": c_grp,
                "device_remote_group": c.device_remote_group,
                "device_group_name": group_name_map.get(c_grp, c_grp.replace("_", " ").title()),
                "site_id": c.site_id,
                "display_shape": c.display_shape,
                "active_area_name": c_area_name,
                "active_speaker": c.active_speaker if c_has_audio else "",
                "has_audio": c_has_audio,
                "is_latter_native": c_is_latter_native,
                "media_state": c_media_state if c_has_audio else "",
                "battery_level": c_bat_val,
                "is_charging": bool(c_chg_st and c_chg_st.state == "on"),
                "is_usb_connected": bool(c_usb_st and c_usb_st.state == "on"),
                "wifi_rssi": c_wifi_val,
                "ip_address": c_ip_val,
                "has_ble": c_has_ble,
                "ble_survey_rows": c_survey_rows,
                "ble_packets_seen": c_packets_seen,
                "ble_closest_proxy": c_area_attrs.get("ble_closest_proxy", ""),
                "companion_url": (
                    f"/api/latter/companion/{c.entry.entry_id}"
                    f"?uid={quote(uid, safe='')}&sig={c.sign_resource(f'studio|{uid}', ttl_s=8 * 3600)}"
                    if uid
                    else f"/api/latter/companion/{c.entry.entry_id}"
                ),
                "is_current": c.entry.entry_id == coordinator.entry.entry_id,
            }
        )

    vault_backups = hass.data.get(DOMAIN, {}).get("backups_data", {}).get("snapshots", [])
    vault_summaries: list[dict[str, Any]] = []
    for s in vault_backups:
        if isinstance(s, dict) and s.get("id"):
            dev_obj = s.get("device") or {}
            ctrl_cnt = (
                len(dev_obj.get("esphome_controls") or {})
                if s.get("scope") == "device"
                else sum(
                    len((d or {}).get("esphome_controls") or {})
                    for d in (s.get("devices") or {}).values()
                )
            )
            vault_summaries.append(
                {
                    "id": s["id"],
                    "name": s.get("name", s["id"]),
                    "scope": s.get("scope", "device"),
                    "created_at": s.get("created_at", ""),
                    "target_device": s.get("target_device", ""),
                    "device_count": int(s.get("device_count") or 1),
                    "control_count": ctrl_cnt,
                    "version": s.get("version", INTEGRATION_VERSION),
                }
            )

    onboarded_slugs = {c.device_slug for c in _get_all_coordinators(hass)}
    unbridged_devices: list[dict[str, str]] = []
    seen_unbridged: set[str] = set()
    for dev in _iter_devices(dev_reg):
        dev_entries = er.async_entries_for_device(ent_reg, dev.id)
        if not any(e.platform == "esphome" for e in dev_entries):
            continue
        raw_name = str(dev.name_by_user or dev.name or "").strip()
        if not raw_name:
            continue
        cand_slug = re.sub(r"[^a-z0-9]+", "_", raw_name.lower()).strip("_")
        if not cand_slug or cand_slug in onboarded_slugs or cand_slug in seen_unbridged:
            continue
        seen_unbridged.add(cand_slug)
        area_obj = area_reg.async_get_area(dev.area_id) if dev.area_id else None
        area_lbl = f" • {area_obj.name}" if area_obj else ""
        model_lbl = f" ({dev.model})" if dev.model else ""
        unbridged_devices.append(
            {
                "slug": cand_slug,
                "name": f"{raw_name}{model_lbl}{area_lbl}",
                "area_id": dev.area_id or "",
            }
        )
    unbridged_devices.sort(key=lambda d: d["name"].lower())

    internal_logs = _get_combined_system_and_studio_logs(hass)

    return {
        "entry_id": coordinator.entry.entry_id,
        "title": coordinator.device_slug.replace("_", " ").title(),
        "version": INTEGRATION_VERSION,
        "capabilities": device_capabilities,
        "internal_logs": internal_logs,
        "health_warnings": health_warnings,
        "system_devices": system_devices,
        "unbridged_devices": unbridged_devices,
        "discovered_ble_devices": get_discovered_ble_candidates(
            hass,
            onboarded_slugs,
            {c.ble_target_address for c in _get_all_coordinators(hass) if c.ble_target_address},
        ),
        "system_controls": _build_system_shared_controls(hass),
        "device_groups": device_groups,
        "saved_profiles": saved_profiles,
        "vault_backups": vault_summaries,
        "config": config_data,
        "esphome": esphome_inspector,
        "wallpapers": wallpapers_catalog,
        "vpn_snippets": build_wireguard_provisioning_snippets(
            coordinator.device_slug, config_data, config_data
        ),
        "live": {
            "active_area_id": coordinator.active_area_id or "",
            "active_area_name": area_attrs.get("area_name", "Home"),
            "area_temp": area_attrs.get("area_temp"),
            "area_humidity": area_attrs.get("area_humidity"),
            "lights_on": area_attrs.get("lights_on", 0),
            "covers_open": area_attrs.get("covers_open", 0),
            "entity_count": area_attrs.get("entity_count", 0),
            "area_cards": active_area_cards[:12],
            "ble_closest_proxy": area_attrs.get("ble_closest_proxy", ""),
            "ble_packets_seen": area_attrs.get("ble_packets_seen", 0),
            "ble_rssi_by_area": area_attrs.get("ble_rssi_by_area", {}),
            "ble_survey_rows": ble_survey_rows,
            "ble_scanners_map": area_attrs.get("ble_scanners_map", {}),
            "area_presence_grid": get_all_areas_presence_summary(hass),
            "active_speaker": coordinator.active_speaker,
            "local_speaker": coordinator.local_speaker,
            "volume_entity": media_attrs.get("volume_entity", ""),
            "media_state": media_state,
            "media_title": media_attrs.get("title", "Idle"),
            "media_artist": media_attrs.get("artist", "None"),
            "media_art_url": media_attrs.get("art_url", "none"),
            "alarm_state": area_attrs.get("alarm_state", "none"),
            "thermostat_state": area_attrs.get("thermostat_state", "off"),
            "thermostat_temp": area_attrs.get("thermostat_temp"),
            "lock_state": area_attrs.get("lock_state", "locked"),
            "garage_state": area_attrs.get("garage_state", "closed"),
            "vacuum_state": area_attrs.get("vacuum_state", "docked"),
            "weather_condition": coordinator.weather_attributes.get("condition", "unknown"),
            "weather_temp": coordinator.weather_attributes.get("temperature"),
            "wallpaper_url": area_attrs.get("wallpaper_url", "none"),
            "doorbell_talk_state": coordinator.doorbell_talk_state,
            "doorbell_anc_mode": coordinator.doorbell_anc_mode,
            "active_remote_slot": coordinator.active_remote_slot,
            "remote_slots_meta": remote_attrs,
            "device_sw_version": str(
                (
                    hass.states.get(f"sensor.{coordinator.device_slug}_firmware_version").state
                    if hass.states.get(f"sensor.{coordinator.device_slug}_firmware_version")
                    and hass.states.get(f"sensor.{coordinator.device_slug}_firmware_version").state
                    not in ("unavailable", "unknown", "")
                    else esphome_inspector.get("device", {}).get("sw_version")
                )
                or INTEGRATION_VERSION
            ),
            "fw_update_entity": next(
                (
                    str(it.get("entity_id"))
                    for it in all_esp_items
                    if it.get("domain") == "update" and it.get("entity_id")
                ),
                "",
            ),
            "fw_update_available": any(
                it.get("domain") == "update" and it.get("state") == "on"
                for it in all_esp_items
            ),
            "fw_latest_version": next(
                (
                    str(
                        hass.states.get(str(it.get("entity_id"))).attributes.get("latest_version")
                        or ""
                    )
                    for it in all_esp_items
                    if it.get("domain") == "update"
                    and it.get("entity_id")
                    and hass.states.get(str(it.get("entity_id")))
                ),
                "",
            ),
        },
        "ha_themes": _get_ha_installed_themes(hass),
        "catalog": {
            "areas": areas_list,
            "ma_speakers": ma_speakers,
            "volume_targets": volume_targets,
            "remotes": remotes_list,
            "alarms": alarms_list,
            "cameras": cameras_list,
            "climates": climates_list,
            "locks": locks_list,
            "garages": garages_list,
            "vacuums": vacuums_list,
            "weathers": weathers_list,
            "calendars": calendars_list,
            "persons": persons_list,
            "presence_sensors": presence_sensors,
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

    async def _async_resolve_coordinator(
        self, request: web.Request, entry_id: str
    ) -> tuple[LatterCoordinator | None, str]:
        domain_data = self.hass.data.get(DOMAIN, {})
        coordinator: LatterCoordinator | None = domain_data.get(entry_id)
        if not isinstance(coordinator, LatterCoordinator):
            return None, ""
        uid = (
            request.query.get("uid")
            or request.headers.get("X-Latter-Uid")
            or ""
        ).strip()
        sig = (
            request.query.get("sig")
            or request.headers.get("X-Latter-Sig")
            or ""
        ).strip()
        if not uid or not sig:
            return None, ""
        if not coordinator.verify_resource(f"studio|{uid}", sig=sig):
            return None, ""
        user = await self.hass.auth.async_get_user(uid)
        if user is None or not user.is_active or not user.is_admin:
            return None, ""
        return coordinator, uid

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        """Return live state, configuration, ESPHome device inspector, and entity catalog."""
        coordinator, uid = await self._async_resolve_coordinator(request, entry_id)
        if coordinator is None:
            return web.json_response(
                {"error": "Unauthorized or unknown entry"},
                status=HTTPStatus.FORBIDDEN,
            )
        from . import _async_scan_all_esphome_devices_for_discovery

        _async_scan_all_esphome_devices_for_discovery(self.hass)
        await async_refresh_wallpaper_cache(self.hass, coordinator.device_slug)
        await async_list_vault_backups(self.hass)
        payload = _build_companion_state_payload(self.hass, coordinator, uid=uid)
        return web.json_response(payload)

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        """Save updated configuration, manage wallpapers, or execute a live entity/device/system action."""
        coordinator, uid = await self._async_resolve_coordinator(request, entry_id)
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

        if cmd == "set_ble_area_offset":
            area_id = str(body.get("area_id") or "").strip()
            offset_val = float(body.get("offset_db") or 0.0)
            offsets = dict(coordinator.ble_area_offsets)
            if abs(offset_val) < 0.1:
                offsets.pop(area_id, None)
            elif area_id:
                offsets[area_id] = round(max(-25.0, min(25.0, offset_val)), 1)
            await _async_save_and_broadcast_global_config(
                self.hass, {CONF_BLE_AREA_OFFSETS: offsets}
            )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "set_area_fusion_mode":
            area_id = str(body.get("area_id") or "").strip()
            mode_val = str(body.get("mode") or "auto_bayes").strip().lower()
            if mode_val not in ("auto_bayes", "any_or", "ble_only", "ble_and_sensor"):
                mode_val = "auto_bayes"
            if area_id:
                raw_fusion = coordinator.get_opt(CONF_AREA_FUSION_CONFIG, {})
                fusion_cfg = dict(raw_fusion) if isinstance(raw_fusion, dict) else {}
                cur_area_cfg = dict(fusion_cfg.get(area_id) or {}) if isinstance(fusion_cfg.get(area_id), dict) else {}
                cur_area_cfg["mode"] = mode_val
                if "threshold_pct" in body and body["threshold_pct"] is not None:
                    cur_area_cfg["threshold_pct"] = max(20, min(95, int(body["threshold_pct"])))
                if "sensors" in body and isinstance(body["sensors"], list):
                    cur_area_cfg["sensors"] = [str(s).strip() for s in body["sensors"] if str(s or "").strip()]
                fusion_cfg[area_id] = cur_area_cfg
                await _async_save_and_broadcast_global_config(
                    self.hass, {CONF_AREA_FUSION_CONFIG: fusion_cfg}
                )
                get_ble_fabric(self.hass).notify_occupancy_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "auto_calibrate_here":
            target_area_id = str(body.get("area_id") or "").strip()
            survey_slug = str(body.get("survey_device_slug") or "").strip()
            survey_coord = coordinator
            if survey_slug:
                matched_c = next(
                    (
                        c
                        for c in _get_all_coordinators(self.hass)
                        if c.device_slug == survey_slug and c._ble_tracker is not None
                    ),
                    None,
                )
                if matched_c is not None:
                    survey_coord = matched_c
            elif survey_coord._ble_tracker is None:
                fallback_c = next(
                    (
                        c
                        for c in _get_all_coordinators(self.hass)
                        if c._ble_tracker is not None
                    ),
                    None,
                )
                if fallback_c is not None:
                    survey_coord = fallback_c

            if target_area_id and survey_coord._ble_tracker is not None:
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
                await _async_save_and_broadcast_global_config(
                    self.hass, {CONF_BLE_AREA_OFFSETS: offsets}
                )
                survey_coord.async_set_active_area(
                    target_area_id, handoff_media=False, sync_device_registry=True
                )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "system_entity_action":
            entity_ids = body.get("entity_ids") or []
            action = str(body.get("action") or "toggle").strip()
            level = body.get("level")
            option = body.get("option")
            if isinstance(entity_ids, list):
                for ent_id in entity_ids:
                    if isinstance(ent_id, str) and ent_id.strip():
                        await async_execute_area_action(
                            self.hass,
                            entity_id=ent_id.strip(),
                            action=action,
                            level=int(float(level)) if level is not None else None,
                            option=str(option) if option is not None else None,
                        )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "test_doorbell_talkback":
            from .doorbell_engine import async_execute_doorbell_intercom

            cam_ent = str(body.get("camera_entity") or coordinator.camera_entity or "").strip()
            msg = str(body.get("message") or "Hello! Please leave the package by the front door.").strip()
            anc = str(body.get("anc_mode") or coordinator.doorbell_anc_mode or "ultra").strip()
            coordinator.doorbell_anc_mode = anc
            await async_execute_doorbell_intercom(
                self.hass,
                coordinator,
                action="talk_message",
                camera_entity=cam_ent,
                message=msg,
                anc_mode=anc,
            )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "send_test_notification":
            title = str(body.get("title") or "Doorbell Alert").strip()
            message = str(body.get("message") or "Motion detected at Front Door").strip()
            priority = str(body.get("priority") or "normal").strip()
            inc_cam = bool(body.get("include_camera", False))
            target_slug = str(body.get("target_device") or coordinator.device_slug).strip()
            cam_ent = coordinator.camera_entity if inc_cam else None
            await self.hass.services.async_call(
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
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "generate_vpn_keys":
            keys = generate_wireguard_keypair()
            subnet = str(coordinator.get_opt(CONF_VPN_SUBNET, "10.10.10.0/24") or "10.10.10.0/24")
            used_ips = [
                c.vpn_client_ip
                for c in _get_all_coordinators(self.hass)
                if c.entry.entry_id != coordinator.entry.entry_id and c.vpn_client_ip
            ]
            server_ip, next_client_ip = allocate_next_tunnel_ip(subnet, used_ips)
            client_ip = coordinator.vpn_client_ip or next_client_ip
            merged_vpn: dict[str, Any] = {
                **coordinator.entry.data,
                **(coordinator.entry.options or {}),
                CONF_VPN_ENABLED: True,
                CONF_VPN_CLIENT_IP: client_ip,
                CONF_VPN_PRIVATE_KEY: keys["private_key"],
                CONF_VPN_PUBLIC_KEY: keys["public_key"],
                CONF_VPN_PRESHARED_KEY: keys["preshared_key"],
            }
            self.hass.config_entries.async_update_entry(
                coordinator.entry, data=merged_vpn, options=merged_vpn
            )
            if not coordinator.get_opt(CONF_VPN_HA_IP):
                await _async_save_and_broadcast_global_config(
                    self.hass, {CONF_VPN_HA_IP: server_ip, CONF_VPN_SUBNET: subnet}
                )
            coordinator.async_notify_listeners()
            return web.json_response(
                _build_companion_state_payload(
                    self.hass, coordinator, include_vpn_secrets=True, uid=uid
                )
            )

        if cmd == "check_system_updates":
            for st_u in self.hass.states.async_all("update"):
                eid_low = st_u.entity_id.lower()
                if "latter" in eid_low or any(
                    c.device_slug in eid_low for c in _get_all_coordinators(self.hass)
                ):
                    if self.hass.services.has_service("homeassistant", "update_entity"):
                        await self.hass.services.async_call(
                            "homeassistant",
                            "update_entity",
                            {"entity_id": st_u.entity_id},
                            blocking=False,
                        )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "set_theme":
            theme_val = _normalize_web_theme(body.get("web_theme"))
            await _async_save_and_broadcast_global_config(
                self.hass, {CONF_WEB_THEME: theme_val}
            )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "activate_remote_slot":
            slot_num = max(1, min(10, int(body.get("slot") or 1)))
            coordinator.active_remote_slot = slot_num
            coordinator._schedule_persist_runtime_state()
            coordinator.async_notify_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
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
                coordinator.current_wallpaper = new_source
                coordinator._configured_wallpaper_source = new_source
                coordinator._schedule_persist_runtime_state()
                self.hass.config_entries.async_update_entry(
                    coordinator.entry, data=merged_wp, options=merged_wp
                )
                coordinator.async_notify_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "select_wallpaper":
            source_id = str(body.get("source_id") or "").strip()
            merged_sel: dict[str, Any] = {
                **coordinator.entry.data,
                **(coordinator.entry.options or {}),
                CONF_WALLPAPER_SOURCE: source_id,
            }
            coordinator.current_wallpaper = source_id
            coordinator._configured_wallpaper_source = source_id
            coordinator._schedule_persist_runtime_state()
            self.hass.config_entries.async_update_entry(
                coordinator.entry, data=merged_sel, options=merged_sel
            )
            coordinator.async_notify_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
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
            coordinator.async_notify_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
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
                coordinator.current_wallpaper = new_active
                coordinator._configured_wallpaper_source = new_active
                coordinator._schedule_persist_runtime_state()
                self.hass.config_entries.async_update_entry(
                    coordinator.entry, data=merged_del, options=merged_del
                )
                coordinator.async_notify_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
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
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "set_active_speaker":
            speaker_id = str(body.get("speaker") or "").strip()
            if speaker_id:
                coordinator.async_set_active_speaker(speaker_id, transfer_queue=True)
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd in ("esphome_entity_action", "area_card_action"):
            entity_id = str(body.get("entity_id") or "").strip()
            action = str(body.get("action") or "toggle").strip()
            level = body.get("level")
            option = body.get("option")
            if entity_id:
                await async_execute_area_action(
                    self.hass,
                    entity_id=entity_id,
                    action=action,
                    level=int(float(level)) if level is not None else None,
                    option=str(option) if option is not None else None,
                )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "save_config":
            incoming_cfg = body.get("config") or {}
            merged_device: dict[str, Any] = {
                **coordinator.entry.data,
                **(coordinator.entry.options or {}),
            }
            global_updates: dict[str, Any] = {}

            if "camera_entities" in incoming_cfg and isinstance(incoming_cfg["camera_entities"], list):
                clean_cams = [
                    str(x).strip()
                    for x in incoming_cfg["camera_entities"][:10]
                    if str(x or "").strip()
                ]
                incoming_cfg[CONF_CAMERA_ENTITIES] = clean_cams
                incoming_cfg[CONF_CAMERA_ENTITY] = clean_cams[0] if clean_cams else ""

            if "remotes_list" in incoming_cfg and isinstance(incoming_cfg["remotes_list"], list):
                incoming_cfg[CONF_REMOTES_LIST] = [
                    str(x).strip()
                    for x in incoming_cfg["remotes_list"][:10]
                    if str(x or "").strip()
                ]

            if "volume_overrides" in incoming_cfg and isinstance(incoming_cfg["volume_overrides"], list):
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
                CONF_DEVICE_SLUG,
                CONF_DEVICE_PROFILE,
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
                CONF_ASSIGNED_ROLE,
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
                CONF_VPN_ENABLED,
                CONF_VPN_CLIENT_IP,
                CONF_VPN_PRIVATE_KEY,
                CONF_VPN_PUBLIC_KEY,
                CONF_VPN_PRESHARED_KEY,
                CONF_VPN_HOTSPOT_SSID,
            )

            for k in device_keys:
                if k in incoming_cfg:
                    val = incoming_cfg[k]
                    if k in (CONF_VPN_PRIVATE_KEY, CONF_VPN_PRESHARED_KEY) and val == _SECRET_MASK:
                        continue
                    if k == CONF_DEVICE_SLUG:
                        clean_s = normalize_device_slug(str(val or ""))
                        if not clean_s or clean_s == "esphome_device":
                            val = coordinator.device_slug
                        else:
                            val = clean_s
                    elif k == CONF_ART_SIZE:
                        s_val = str(val or DEFAULT_ART_SIZE).strip().lower()
                        val = s_val if "x" in s_val else int(s_val or DEFAULT_ART_SIZE)
                    elif k == CONF_DEFAULT_PAGE_SIZE:
                        val = max(1, min(20, int(val or DEFAULT_PAGE_SIZE)))
                    elif k == CONF_WALLPAPER_CYCLE_MINUTES:
                        val = max(0, int(val or DEFAULT_WALLPAPER_CYCLE_MINUTES))
                    merged_device[k] = val
            log_studio_event(
                self.hass,
                "INFO",
                coordinator.device_slug,
                f"Saved configuration for '{merged_device.get(CONF_DEVICE_SLUG, coordinator.device_slug)}'",
            )

            for k in GLOBAL_CONFIG_KEYS:
                if k in incoming_cfg:
                    val = incoming_cfg[k]
                    if k == CONF_SIP_PASSWORD and val == _SECRET_MASK:
                        continue
                    if k == CONF_WEB_THEME:
                        val = _normalize_web_theme(val)
                    global_updates[k] = val
                    merged_device[k] = val

            self.hass.config_entries.async_update_entry(
                coordinator.entry, data=merged_device, options=merged_device
            )
            if global_updates:
                await _async_save_and_broadcast_global_config(
                    self.hass, global_updates
                )
                from .sip_engine import get_sip_engine

                await get_sip_engine(self.hass).async_start_or_reload()
            coordinator._bind_wallpaper_cycle_timer()
            coordinator.async_notify_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "log_client_error":
            msg = str(body.get("message") or "Unknown client error")
            src = str(body.get("source") or "webui")
            log_studio_event(self.hass, "ERROR", src, msg)
            return web.json_response({"logged": True})

        if cmd == "clear_internal_logs":
            self.hass.data.setdefault(DOMAIN, {})["internal_logs"] = []
            log_studio_event(self.hass, "INFO", "studio", "Cleared internal diagnostic log")
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "remove_device":
            target_entry_id = str(body.get("entry_id") or "").strip()
            target_slug = str(body.get("device_slug") or "").strip()
            all_coords = _get_all_coordinators(self.hass)
            target_coord = next(
                (
                    c
                    for c in all_coords
                    if c.entry.entry_id == target_entry_id or (target_slug and c.device_slug == target_slug)
                ),
                None,
            )
            if target_coord is None:
                return web.json_response(
                    {"error": "Target device not found"}, status=HTTPStatus.NOT_FOUND
                )
            remaining = [
                c for c in all_coords if c.entry.entry_id != target_coord.entry.entry_id
            ]
            redirect_url = (
                f"/api/latter/companion/{remaining[0].entry.entry_id}?uid={quote(uid, safe='')}&sig={remaining[0].sign_resource(f'studio|{uid}', ttl_s=8 * 3600)}&scope=system"
                if remaining
                else "/config/integrations/integration/latter"
            )
            removed_slug = target_coord.device_slug
            await self.hass.config_entries.async_remove(target_coord.entry.entry_id)
            log_studio_event(
                self.hass, "INFO", "studio", f"Removed device '{removed_slug}' from Latter"
            )
            if remaining and coordinator.entry.entry_id != target_coord.entry.entry_id:
                return web.json_response(
                    _build_companion_state_payload(self.hass, coordinator, uid=uid)
                )
            return web.json_response({"removed": True, "redirect_url": redirect_url})

        if cmd == "add_ble_device":
            raw_name = str(body.get("name") or body.get("device_slug") or "ble_device").strip()
            target_addr = str(body.get("target_address") or "").strip()
            assigned_person = str(body.get("assigned_person") or "").strip()
            target_slug = normalize_device_slug(raw_name) if raw_name else "ble_device"
            if target_slug and target_addr:
                existing = [
                    c for c in _get_all_coordinators(self.hass)
                    if c.device_slug == target_slug
                ]
                if not existing:
                    await self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "user"},
                        data={
                            CONF_DEVICE_SLUG: target_slug,
                            CONF_DEVICE_PROFILE: "ble_beacon",
                            CONF_DEVICE_GROUP: DEFAULT_DEVICE_GROUP,
                            CONF_DEFAULT_SPEAKER: "",
                            CONF_NATIVE_BLE_TRACKING: True,
                            CONF_BLE_AUTO_SWITCH: True,
                            CONF_SYNC_DEVICE_AREA: False,
                            CONF_BLE_TARGET_ADDRESS: target_addr,
                            CONF_ASSIGNED_PERSON: assigned_person,
                            CONF_ART_SIZE: DEFAULT_ART_SIZE,
                        },
                    )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "bridge_esphome_device":
            raw_slug = str(body.get("device_slug") or "").strip()
            target_slug = re.sub(r"[^a-z0-9]+", "_", raw_slug.lower()).strip("_")
            if target_slug:
                existing = [
                    c for c in _get_all_coordinators(self.hass)
                    if c.device_slug == target_slug
                ]
                if not existing:
                    default_area = str(body.get("area_id") or "").strip()
                    await self.hass.config_entries.flow.async_init(
                        DOMAIN,
                        context={"source": "user"},
                        data={
                            CONF_DEVICE_SLUG: target_slug,
                            CONF_DEVICE_PROFILE: "headless_node",
                            CONF_DEVICE_GROUP: DEFAULT_DEVICE_GROUP,
                            CONF_DEFAULT_SPEAKER: "",
                            CONF_NATIVE_BLE_TRACKING: False,
                            CONF_BLE_AUTO_SWITCH: False,
                            CONF_SYNC_DEVICE_AREA: False,
                            CONF_ART_SIZE: DEFAULT_ART_SIZE,
                            **({CONF_DEFAULT_AREA: default_area} if default_area else {}),
                        },
                    )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "set_device_remote_group":
            target_slug = str(body.get("device_slug") or coordinator.device_slug).strip()
            rem_grp = str(body.get("device_remote_group") or "area_auto").strip()
            for c in _get_all_coordinators(self.hass):
                if c.device_slug == target_slug:
                    merged_rg: dict[str, Any] = {
                        **c.entry.data,
                        **(c.entry.options or {}),
                        CONF_DEVICE_REMOTE_GROUP: rem_grp,
                    }
                    self.hass.config_entries.async_update_entry(
                        c.entry, data=merged_rg, options=merged_rg
                    )
                    c.async_notify_listeners()
                    break
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "set_device_group":
            target_slug = str(body.get("device_slug") or coordinator.device_slug).strip()
            group_id = str(body.get("device_group") or DEFAULT_DEVICE_GROUP).strip()
            for c in _get_all_coordinators(self.hass):
                if c.device_slug == target_slug:
                    merged_grp: dict[str, Any] = {
                        **c.entry.data,
                        **(c.entry.options or {}),
                        CONF_DEVICE_GROUP: group_id,
                    }
                    self.hass.config_entries.async_update_entry(
                        c.entry, data=merged_grp, options=merged_grp
                    )
                    c.async_notify_listeners()
                    break
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "create_device_group":
            g_name = str(body.get("name") or "").strip()
            g_desc = str(body.get("description") or "").strip()
            if g_name:
                g_id = re.sub(r"[^a-z0-9]+", "_", g_name.lower()).strip("_") or "group"
                groups, _ = get_device_groups_and_profiles(self.hass)
                if not any(g.get("id") == g_id for g in groups):
                    groups.append(
                        {
                            "id": g_id,
                            "name": g_name,
                            "description": g_desc or f"Custom group ({g_name})",
                        }
                    )
                    await _async_save_and_broadcast_global_config(
                        self.hass, {CONF_DEVICE_GROUPS: groups}
                    )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "delete_device_group":
            g_id = str(body.get("group_id") or "").strip()
            groups, _ = get_device_groups_and_profiles(self.hass)
            groups = [g for g in groups if g.get("id") != g_id]
            await _async_save_and_broadcast_global_config(
                self.hass, {CONF_DEVICE_GROUPS: groups}
            )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "capture_profile":
            p_name = str(body.get("name") or "").strip()
            p_desc = str(body.get("description") or "").strip()
            _, profiles = get_device_groups_and_profiles(self.hass)
            new_prof = capture_profile_from_coordinator(
                self.hass, coordinator, name=p_name, description=p_desc
            )
            profiles = [p for p in profiles if p.get("name") != new_prof["name"]]
            profiles.insert(0, new_prof)
            await _async_save_and_broadcast_global_config(
                self.hass, {CONF_SAVED_PROFILES: profiles[:30]}
            )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "delete_profile":
            p_id = str(body.get("profile_id") or "").strip()
            _, profiles = get_device_groups_and_profiles(self.hass)
            profiles = [p for p in profiles if p.get("id") != p_id]
            await _async_save_and_broadcast_global_config(
                self.hass, {CONF_SAVED_PROFILES: profiles}
            )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "apply_profile":
            p_id = str(body.get("profile_id") or "").strip()
            target_scope = str(body.get("target_scope") or "current").strip()
            _, profiles = get_device_groups_and_profiles(self.hass)
            prof = next((p for p in profiles if p.get("id") == p_id), None)
            if prof is not None:
                all_coords = _get_all_coordinators(self.hass)
                if target_scope == "all":
                    targets = all_coords
                elif target_scope.startswith("group:"):
                    grp_id = target_scope.split(":", 1)[1]
                    targets = [c for c in all_coords if c.device_group == grp_id]
                elif target_scope.startswith("device:"):
                    d_slug = target_scope.split(":", 1)[1]
                    targets = [c for c in all_coords if c.device_slug == d_slug]
                else:
                    targets = [coordinator]
                await async_apply_profile_to_coordinators(self.hass, prof, targets)
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "create_vault_backup":
            b_scope = str(body.get("scope") or "device").strip()
            b_name = str(body.get("name") or "").strip()
            inc_vpn = bool(body.get("include_vpn_secrets", True))
            await async_create_vault_backup(
                self.hass,
                scope=b_scope,
                coordinators=_get_all_coordinators(self.hass),
                target_coordinator=coordinator,
                name=b_name,
                include_vpn_secrets=inc_vpn,
            )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "export_backup_json":
            b_scope = str(body.get("scope") or "device").strip()
            b_id = str(body.get("backup_id") or "").strip()
            inc_vpn = bool(body.get("include_vpn_secrets", True))
            if b_id:
                bundle = await async_get_vault_backup(self.hass, b_id)
                if bundle is None:
                    return web.json_response(
                        {"error": "Backup snapshot not found"},
                        status=HTTPStatus.NOT_FOUND,
                    )
            else:
                bundle = build_backup_bundle(
                    hass=self.hass,
                    scope=b_scope,
                    coordinators=_get_all_coordinators(self.hass),
                    target_coordinator=coordinator,
                    include_vpn_secrets=inc_vpn,
                )
            return web.json_response({"bundle": bundle})

        if cmd == "restore_backup":
            b_id = str(body.get("backup_id") or "").strip()
            bundle = body.get("bundle")
            if b_id and not isinstance(bundle, dict):
                bundle = await async_get_vault_backup(self.hass, b_id)
            if not isinstance(bundle, dict):
                return web.json_response(
                    {"error": "Valid backup bundle or backup_id required"},
                    status=HTTPStatus.BAD_REQUEST,
                )
            restore_esp = bool(body.get("restore_esphome_entities", True))
            await async_restore_backup_bundle(
                self.hass,
                bundle=bundle,
                coordinators=_get_all_coordinators(self.hass),
                target_coordinator=coordinator,
                restore_esphome_entities=restore_esp,
            )
            await async_list_vault_backups(self.hass)
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        if cmd == "delete_vault_backup":
            b_id = str(body.get("backup_id") or "").strip()
            if b_id:
                await async_delete_vault_backup(self.hass, b_id)
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator, uid=uid)
            )

        return web.json_response(
            {"error": f"Unknown command: {cmd}"}, status=HTTPStatus.BAD_REQUEST
        )


_STUDIO_HTML_PATH = Path(__file__).parent / "frontend" / "studio.html"


def get_studio_panel_token(hass: HomeAssistant) -> str:
    """Return the per-boot in-memory random token for the Home Assistant sidebar panel."""
    import secrets

    domain_data = hass.data.setdefault(DOMAIN, {})
    tok = domain_data.get("studio_panel_token")
    if not isinstance(tok, str) or not tok:
        tok = secrets.token_urlsafe(32)
        domain_data["studio_panel_token"] = tok
    return tok


def verify_studio_panel_token(hass: HomeAssistant, token: str | None) -> bool:
    """Verify the per-boot in-memory studio panel token in constant time."""
    import hmac

    if not token:
        return False
    expected = hass.data.get(DOMAIN, {}).get("studio_panel_token")
    if isinstance(expected, str) and expected:
        return hmac.compare_digest(token, expected)
    return False


_STUDIO_AUTH_BOOTSTRAP_HTML = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Latter Studio Auth</title></head>
<body style="background:#111;color:#9b9b9b;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
<div id="msg">Verifying Home Assistant session...</div>
<script>
(async () => {
  try {
    let raw = localStorage.getItem("hassTokens");
    if (!raw && window.parent && window.parent !== window) {
      try { raw = window.parent.localStorage.getItem("hassTokens"); } catch (_e) {}
    }
    if (!raw) throw new Error("No Home Assistant session found");
    const tokens = JSON.parse(raw);
    const accessToken = tokens && tokens.access_token;
    if (!accessToken) throw new Error("Missing access_token");
    const resp = await fetch(window.location.pathname + window.location.search, {
      method: "POST",
      headers: {"Authorization": "Bearer " + accessToken, "Content-Type": "application/json"},
      body: JSON.stringify({action: "exchange_studio_token"})
    });
    if (!resp.ok) throw new Error("Unauthorized");
    const data = await resp.json();
    if (data.redirect_url) {
      window.location.replace(data.redirect_url);
      return;
    }
    throw new Error("Invalid redirect response");
  } catch (_err) {
    document.getElementById("msg").textContent = "403 Forbidden: Admin privileges required.";
  }
})();
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
        """Serve the single-page Latter Companion Studio from frontend/studio.html."""
        domain_data = self.hass.data.get(DOMAIN, {})
        coordinator: LatterCoordinator | None = domain_data.get(entry_id)
        if not isinstance(coordinator, LatterCoordinator):
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Unknown Latter entry")

        uid = (request.query.get("uid") or "").strip()
        sig = (request.query.get("sig") or "").strip()
        if not uid or not sig or not coordinator.verify_resource(f"studio|{uid}", sig=sig):
            return web.Response(
                status=HTTPStatus.FORBIDDEN,
                text="Invalid or missing Latter Studio signature. Open via the Home Assistant sidebar or the 'Visit' link on the device page.",
            )

        user = await self.hass.auth.async_get_user(uid)
        if user is None or not user.is_active or not user.is_admin:
            return web.Response(
                status=HTTPStatus.FORBIDDEN,
                text="Admin privileges required.",
            )

        html_body = await self.hass.async_add_executor_job(
            _STUDIO_HTML_PATH.read_text, "utf-8"
        )
        return web.Response(
            body=html_body,
            content_type="text/html",
            charset="utf-8",
        )


class LatterStudioRootView(HomeAssistantView):
    """Master entry point (`/api/latter/studio?scope=system`) used by the Home Assistant Sidebar Panel."""

    requires_auth = False
    url = API_STUDIO_ROOT_PATH
    name = "api:latter:studio_root"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the master Studio redirector view."""
        self.hass = hass

    async def _async_resolve_request_user(self, request: web.Request) -> Any:
        """Resolve an authenticated Home Assistant user from request context or Bearer header."""
        user = request.get("hass_user")
        if user is None:
            auth_hdr = request.headers.get("Authorization", "")
            if auth_hdr.startswith("Bearer "):
                bearer = auth_hdr.removeprefix("Bearer ").strip()
                refresh_token = await self.hass.auth.async_validate_access_token(bearer)
                if refresh_token is not None:
                    user = refresh_token.user
        return user

    async def get(self, request: web.Request) -> web.Response:
        """Redirect to the Studio view ONLY if an authenticated admin session or valid panel bootstrap token is present."""
        coords = _get_all_coordinators(self.hass)
        if not coords:
            return web.Response(
                status=HTTPStatus.NOT_FOUND,
                text="No Latter devices configured yet. Add an ESPHome device under Settings -> Devices & Services -> Latter.",
            )
        user = await self._async_resolve_request_user(request)
        if user is not None:
            if not user.is_active or not user.is_admin:
                return web.json_response(
                    {"error": "Admin privileges required"},
                    status=HTTPStatus.FORBIDDEN,
                )
            primary = coords[0]
            scope = request.query.get("scope") or "system"
            sig = primary.sign_resource(f"studio|{user.id}", ttl_s=8 * 3600)
            target_url = (
                f"/api/latter/companion/{primary.entry.entry_id}"
                f"?uid={quote(user.id, safe='')}&sig={sig}&scope={quote(scope, safe='')}"
            )
            raise web.HTTPFound(location=target_url)

        token = request.query.get("token")
        if not verify_studio_panel_token(self.hass, token):
            return web.json_response(
                {"error": "Admin privileges required"},
                status=HTTPStatus.FORBIDDEN,
            )
        return web.Response(
            body=_STUDIO_AUTH_BOOTSTRAP_HTML,
            content_type="text/html",
            charset="utf-8",
        )

    async def post(self, request: web.Request) -> web.Response:
        """Exchange a valid admin Home Assistant Bearer token for a signed Studio redirect URL."""
        coords = _get_all_coordinators(self.hass)
        if not coords:
            return web.json_response({"error": "No devices"}, status=HTTPStatus.NOT_FOUND)

        user = await self._async_resolve_request_user(request)
        if user is None or not user.is_active or not user.is_admin:
            return web.json_response(
                {"error": "Admin privileges required"},
                status=HTTPStatus.FORBIDDEN,
            )

        primary = coords[0]
        scope = request.query.get("scope") or "system"
        sig = primary.sign_resource(f"studio|{user.id}", ttl_s=8 * 3600)
        target_url = (
            f"/api/latter/companion/{primary.entry.entry_id}"
            f"?uid={quote(user.id, safe='')}&sig={sig}&scope={quote(scope, safe='')}"
        )
        return web.json_response({"redirect_url": target_url})


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


SIDEBAR_ICON_JS = """
window.customIcons = window.customIcons || {};
window.customIcons["latter"] = {
  getIcon: async (iconName) => {
    return {
      viewBox: "0 0 24 24",
      path: "M4 5.5A1.5 1.5 0 0 1 5.5 4h1A1.5 1.5 0 0 1 8 5.5v13A1.5 1.5 0 0 1 6.5 20h-1A1.5 1.5 0 0 1 4 18.5v-13ZM16 5.5A1.5 1.5 0 0 1 17.5 4h1A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-1A1.5 1.5 0 0 1 16 18.5v-13ZM4 16.5h16v2A1.5 1.5 0 0 1 18.5 20h-13A1.5 1.5 0 0 1 4 18.5v-2ZM8 5.25h8v2.5H8v-2.5ZM8 10.75h8v2.5H8v-2.5Z"
    };
  },
  getIconList: async () => [{ name: "logo" }]
};
"""


class LatterSidebarIconJsView(HomeAssistantView):
    """Serves the custom unframed Latter SVG icon set (`latter:logo`) for the Home Assistant sidebar."""

    requires_auth = False
    url = API_SIDEBAR_ICON_JS_PATH
    name = "api:latter:sidebar_icon_js"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the sidebar icon JS view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Serve the custom icon registration script."""
        return web.Response(
            body=SIDEBAR_ICON_JS.strip(),
            content_type="application/javascript",
            charset="utf-8",
            headers={"Cache-Control": "public, max-age=3600"},
        )
