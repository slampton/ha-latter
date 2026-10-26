"""Server-Side Web Companion Studio & REST API for Latter (Global Household + Fleet + Per-Device)."""

from __future__ import annotations

from http import HTTPStatus
import logging
from pathlib import Path
from typing import Any

from aiohttp import web

import re

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .ble_engine import _iter_devices
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
    CONF_CUSTOM_PALETTES,
    CONF_DEVICE_CUSTOM_COLOR,
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
    DEFAULT_SITE_ID,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DEFAULT_ART_SIZE,
    DEFAULT_DEVICE_PROFILE,
    DEFAULT_DISPLAY_SHAPE,
    DEFAULT_PAGE_SIZE,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DEFAULT_WEB_THEME,
    DOMAIN,
    GLOBAL_CONFIG_KEYS,
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
from .vpn_engine import allocate_next_tunnel_ip, build_wireguard_provisioning_snippets, generate_wireguard_keypair
from .wallpaper_engine import (
    delete_uploaded_wallpaper,
    list_wallpaper_catalog,
    save_uploaded_wallpaper,
)

_LOGGER = logging.getLogger(__name__)

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
    """Persist updates to `.storage/latter.household` and broadcast to all loaded device coordinators."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    global_cfg: dict[str, Any] = domain_data.setdefault(DATA_GLOBAL_CONFIG, {})
    global_cfg.update(updates)
    store = domain_data.get(DATA_GLOBAL_STORE)
    if store is not None:
        await store.async_save(global_cfg)
    for coord in _get_all_coordinators(hass):
        await coord.async_on_global_config_updated()


def _build_fleet_shared_controls(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Discover shared ESPHome select/switch/number controls across all onboarded devices for 1-click Fleet Sync."""
    coords = _get_all_coordinators(hass)
    by_label: dict[str, dict[str, Any]] = {}
    for coord in coords:
        esp_info = get_esphome_device_entities(hass, coord.device_slug)
        for sec in esp_info.get("sections", []):
            sec_id = sec.get("id", "")
            if sec_id not in ("voice", "sleep", "display", "sound", "music", "room"):
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

    esphome_svcs = hass.services.async_services().get("esphome", {})
    slug = coordinator.device_slug
    has_native_slots = any(
        (s.endswith("_set_browse_slots") or s.endswith("_set_room_slots")) and slug in s
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

    device_capabilities = {
        "tier": dev_tier,
        "tier_label": dev_tier_label,
        "has_display": has_display,
        "has_power": has_power,
        "has_voice": has_voice,
        "has_audio": has_audio,
        "has_ble_beacon": has_native_slots or has_ble_beacon_entity,
        "has_vpn_mixin": has_vpn_entities or coordinator.vpn_enabled,
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
        CONF_CUSTOM_PALETTES: coordinator.custom_palettes,
        CONF_DEVICE_CUSTOM_COLOR: coordinator.device_custom_color,
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
        CONF_VPN_PRIVATE_KEY: str(coordinator.get_opt(CONF_VPN_PRIVATE_KEY, "") or ""),
        CONF_VPN_PUBLIC_KEY: str(coordinator.get_opt(CONF_VPN_PUBLIC_KEY, "") or ""),
        CONF_VPN_PRESHARED_KEY: str(coordinator.get_opt(CONF_VPN_PRESHARED_KEY, "") or ""),
        CONF_VPN_HOTSPOT_SSID: str(coordinator.get_opt(CONF_VPN_HOTSPOT_SSID, "") or ""),
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

    device_groups, saved_profiles = get_device_groups_and_profiles(hass)
    group_name_map = {g["id"]: g["name"] for g in device_groups if isinstance(g, dict) and g.get("id")}

    fleet_devices: list[dict[str, Any]] = []
    for c in _get_all_coordinators(hass):
        c_room_name, c_room_attrs = c.get_room_context_payload()
        c_media_state, _ = c.get_active_media_payload()
        c_grp = c.device_group
        c_has_audio = bool(c.local_speaker) or any(
            s.endswith("_set_browse_slots") and c.device_slug in s
            for s in esphome_svcs
        )
        fleet_devices.append(
            {
                "entry_id": c.entry.entry_id,
                "device_slug": c.device_slug,
                "title": c.device_slug.replace("_", " ").title(),
                "device_profile": c.device_profile,
                "device_group": c_grp,
                "device_group_name": group_name_map.get(c_grp, c_grp.replace("_", " ").title()),
                "site_id": c.site_id,
                "display_shape": c.display_shape,
                "active_area_name": c_room_name,
                "active_speaker": c.active_speaker if c_has_audio else "",
                "has_audio": c_has_audio,
                "media_state": c_media_state if c_has_audio else "",
                "ble_closest_proxy": c_room_attrs.get("ble_closest_proxy", ""),
                "companion_url": f"/api/latter/companion/{c.entry.entry_id}?token={c.get_signed_token()}",
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
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
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

    return {
        "entry_id": coordinator.entry.entry_id,
        "title": coordinator.device_slug.replace("_", " ").title(),
        "version": INTEGRATION_VERSION,
        "capabilities": device_capabilities,
        "health_warnings": health_warnings,
        "fleet_devices": fleet_devices,
        "unbridged_devices": unbridged_devices,
        "fleet_controls": _build_fleet_shared_controls(hass),
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
        "ha_themes": _get_ha_installed_themes(hass),
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
        # If the user is browsing via a reverse proxy (e.g. Nginx HTTPS domain) and hasn't hardcoded an override,
        # dynamically link the ESPHome 'Visit' button to the active browser origin while keeping ESP32 URLs on LAN IP.
        if not coordinator.companion_base_url:
            fwd_proto = request.headers.get("X-Forwarded-Proto") or request.scheme
            fwd_host = request.headers.get("X-Forwarded-Host") or request.host
            if fwd_host and "nabu.casa" not in fwd_host.lower():
                browser_base = f"{fwd_proto}://{fwd_host}".rstrip("/")
                token = coordinator.get_signed_token()
                visit_url = f"{browser_base}/api/latter/companion/{coordinator.entry.entry_id}?token={token}"
                inject_esphome_visit_link(self.hass, coordinator.device_slug, visit_url)
        from . import (
            _async_scan_all_esphome_devices_for_discovery,
            is_latter_compatible_esphome_device,
        )

        _async_scan_all_esphome_devices_for_discovery(self.hass)
        # Auto-onboard any newly connected Native Latter device (e.g. Wrist Assist / Pocket Assistant)
        onboarded_slugs = {c.device_slug for c in _get_all_coordinators(self.hass)}
        dev_reg = dr.async_get(self.hass)
        ent_reg = er.async_get(self.hass)
        for dev in _iter_devices(dev_reg):
            dev_entries = er.async_entries_for_device(ent_reg, dev.id)
            if not any(e.platform == "esphome" for e in dev_entries):
                continue
            raw_name = str(dev.name_by_user or dev.name or "").strip()
            if not raw_name:
                continue
            cand_slug = re.sub(r"[^a-z0-9]+", "_", raw_name.lower()).strip("_")
            if not cand_slug or cand_slug in onboarded_slugs:
                continue
            if is_latter_compatible_esphome_device(self.hass, dev, cand_slug):
                is_watch = "wrist" in cand_slug or "206" in str(dev.model or "").lower()
                await self.hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "user"},
                    data={
                        CONF_DEVICE_SLUG: cand_slug,
                        CONF_DEVICE_PROFILE: "mobile_display",
                        CONF_DISPLAY_SHAPE: "square" if is_watch else "circle",
                        CONF_ART_SIZE: "410x502" if is_watch else DEFAULT_ART_SIZE,
                        CONF_DEFAULT_SPEAKER: f"media_player.{cand_slug}",
                    },
                )
                onboarded_slugs.add(cand_slug)

        await async_list_vault_backups(self.hass)
        payload = _build_companion_state_payload(self.hass, coordinator)
        return web.json_response(payload)

    async def post(self, request: web.Request, entry_id: str) -> web.Response:
        """Save updated configuration, manage wallpapers, or execute a live entity/device/fleet action."""
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
            await _async_save_and_broadcast_global_config(
                self.hass, {CONF_BLE_ROOM_OFFSETS: offsets}
            )
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
                await _async_save_and_broadcast_global_config(
                    self.hass, {CONF_BLE_ROOM_OFFSETS: offsets}
                )
                coordinator.async_set_active_area(
                    target_area_id, handoff_media=False, sync_device_registry=True
                )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "fleet_entity_action":
            entity_ids = body.get("entity_ids") or []
            action = str(body.get("action") or "toggle").strip()
            level = body.get("level")
            option = body.get("option")
            if isinstance(entity_ids, list):
                for ent_id in entity_ids:
                    if isinstance(ent_id, str) and ent_id.strip():
                        await async_execute_room_action(
                            self.hass,
                            entity_id=ent_id.strip(),
                            action=action,
                            level=int(float(level)) if level is not None else None,
                            option=str(option) if option is not None else None,
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
            coordinator._notify_listeners()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "set_theme":
            theme_val = _normalize_web_theme(body.get("web_theme"))
            await _async_save_and_broadcast_global_config(
                self.hass, {CONF_WEB_THEME: theme_val}
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
            merged_device: dict[str, Any] = {
                **coordinator.entry.data,
                **(coordinator.entry.options or {}),
            }
            global_updates: dict[str, Any] = {}

            device_keys = (
                CONF_DEVICE_SLUG,
                CONF_DEVICE_PROFILE,
                CONF_DEVICE_GROUP,
                CONF_DISPLAY_SHAPE,
                CONF_DEFAULT_PAGE_SIZE,
                CONF_DEFAULT_SPEAKER,
                CONF_DEFAULT_AREA,
                CONF_NATIVE_BLE_TRACKING,
                CONF_BLE_BEACON_UUID,
                CONF_PRESENCE_ENTITY,
                CONF_BLE_AUTO_SWITCH,
                CONF_SYNC_DEVICE_AREA,
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
                    if k == CONF_ART_SIZE:
                        s_val = str(val or DEFAULT_ART_SIZE).strip().lower()
                        val = s_val if "x" in s_val else int(s_val or DEFAULT_ART_SIZE)
                    elif k == CONF_DEFAULT_PAGE_SIZE:
                        val = max(1, min(20, int(val or DEFAULT_PAGE_SIZE)))
                    elif k == CONF_WALLPAPER_CYCLE_MINUTES:
                        val = max(0, int(val or DEFAULT_WALLPAPER_CYCLE_MINUTES))
                    merged_device[k] = val

            for k in GLOBAL_CONFIG_KEYS:
                if k in incoming_cfg:
                    val = incoming_cfg[k]
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
            inject_esphome_visit_link(
                self.hass,
                coordinator.device_slug,
                coordinator.build_companion_url(),
            )
            coordinator._bind_wallpaper_cycle_timer()
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
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
                f"/api/latter/companion/{remaining[0].entry.entry_id}?token={remaining[0].get_signed_token()}&scope=system"
                if remaining
                else "/config/integrations/integration/latter"
            )
            await self.hass.config_entries.async_remove(target_coord.entry.entry_id)
            if remaining and coordinator.entry.entry_id != target_coord.entry.entry_id:
                return web.json_response(
                    _build_companion_state_payload(self.hass, coordinator)
                )
            return web.json_response({"removed": True, "redirect_url": redirect_url})

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
                _build_companion_state_payload(self.hass, coordinator)
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
                    c._notify_listeners()
                    break
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
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
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "delete_device_group":
            g_id = str(body.get("group_id") or "").strip()
            groups, _ = get_device_groups_and_profiles(self.hass)
            groups = [g for g in groups if g.get("id") != g_id]
            await _async_save_and_broadcast_global_config(
                self.hass, {CONF_DEVICE_GROUPS: groups}
            )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
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
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "delete_profile":
            p_id = str(body.get("profile_id") or "").strip()
            _, profiles = get_device_groups_and_profiles(self.hass)
            profiles = [p for p in profiles if p.get("id") != p_id]
            await _async_save_and_broadcast_global_config(
                self.hass, {CONF_SAVED_PROFILES: profiles}
            )
            return web.json_response(
                _build_companion_state_payload(self.hass, coordinator)
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
                _build_companion_state_payload(self.hass, coordinator)
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
                _build_companion_state_payload(self.hass, coordinator)
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
                _build_companion_state_payload(self.hass, coordinator)
            )

        if cmd == "delete_vault_backup":
            b_id = str(body.get("backup_id") or "").strip()
            if b_id:
                await async_delete_vault_backup(self.hass, b_id)
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
  /* Native Home Assistant Default Dark & Light Theme Tokens (Inherits live HA variables when embedded) */
  :root, [data-theme="dark"] {
    --primary-background-color: #111111;
    --secondary-background-color: #1c1c1c;
    --card-background-color: #1c1c1c;
    --primary-text-color: #e1e1e1;
    --secondary-text-color: #9b9b9b;
    --primary-color: #03a9f4;
    --accent-color: #ff9800;
    --divider-color: rgba(225, 225, 225, 0.12);
    --input-fill-color: #141414;
    --success-color: #4caf50;
    --warning-color: #ff9800;
    --error-color: #db4437;

    --bg: var(--primary-background-color);
    --sidebar: var(--secondary-background-color);
    --card: var(--card-background-color);
    --card-hover: rgba(3, 169, 244, 0.08);
    --border: var(--divider-color);
    --input-bg: var(--input-fill-color);
    --text: var(--primary-text-color);
    --text-strong: var(--primary-text-color);
    --muted: var(--secondary-text-color);
    --accent: var(--primary-color);
    --accent-solid: var(--primary-color);
    --accent-subtle: rgba(3, 169, 244, 0.14);
    --success: var(--success-color);
    --warning: var(--warning-color);
    --danger: var(--error-color);
  }
  [data-theme="light"] {
    --primary-background-color: #fafafa;
    --secondary-background-color: #f0f0f0;
    --card-background-color: #ffffff;
    --primary-text-color: #212121;
    --secondary-text-color: #727272;
    --primary-color: #03a9f4;
    --accent-color: #ff9800;
    --divider-color: rgba(0, 0, 0, 0.12);
    --input-fill-color: #f5f5f5;
    --success-color: #4caf50;
    --warning-color: #ff9800;
    --error-color: #db4437;

    --bg: var(--primary-background-color);
    --sidebar: var(--secondary-background-color);
    --card: var(--card-background-color);
    --card-hover: rgba(3, 169, 244, 0.08);
    --border: var(--divider-color);
    --input-bg: var(--input-fill-color);
    --text: var(--primary-text-color);
    --text-strong: var(--primary-text-color);
    --muted: var(--secondary-text-color);
    --accent: var(--primary-color);
    --accent-solid: var(--primary-color);
    --accent-subtle: rgba(3, 169, 244, 0.12);
    --success: var(--success-color);
    --warning: var(--warning-color);
    --danger: var(--error-color);
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
    grid-template-columns: 256px minmax(0, 1fr);
    min-height: 100vh;
  }
  aside.sidebar {
    background: var(--sidebar);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    padding: 14px 12px;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 11px;
    padding: 2px 6px 12px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 12px;
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
  /* SCOPE SWITCHER (HOUSEHOLD & FLEET vs DEVICE) */
  .scope-box {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px;
    margin-bottom: 12px;
  }
  .scope-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
    background: var(--input-bg);
    padding: 3px;
    border-radius: 6px;
    border: 1px solid var(--border);
  }
  .scope-tab {
    padding: 6px 8px;
    border-radius: 5px;
    border: none;
    background: transparent;
    color: var(--muted);
    font-size: 12px;
    font-weight: 700;
    cursor: pointer;
    text-align: center;
    transition: background 0.12s ease, color 0.12s ease;
  }
  .scope-tab.active {
    background: var(--accent-solid);
    color: #ffffff;
  }
  .device-picker-wrap {
    margin-top: 8px;
  }
  .device-picker-wrap label {
    display: block;
    font-size: 10.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--muted);
    margin-bottom: 4px;
  }
  .device-picker-wrap select {
    padding: 7px 9px;
    font-size: 12.5px;
    font-weight: 600;
  }
  .nav-group-label {
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 11px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.9px;
    color: var(--text-strong);
    margin: 14px 4px 5px;
    padding: 0 6px 5px;
    border-bottom: 1px solid var(--border);
  }
  .nav-group-label:first-child {
    margin-top: 2px;
  }
  .nav-group-label::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 2px;
    background: var(--accent);
    flex-shrink: 0;
  }
  .nav-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    width: calc(100% - 12px);
    margin-left: 12px;
    padding: 8px 12px 8px 14px;
    border-radius: 0 7px 7px 0;
    border: 1px solid transparent;
    border-left: 2px solid var(--border);
    background: transparent;
    color: var(--muted);
    font-weight: 500;
    font-size: 13px;
    cursor: pointer;
    text-align: left;
    white-space: nowrap;
    transition: background 0.12s ease, color 0.12s ease, border-color 0.12s ease;
  }
  .nav-btn:hover {
    background: var(--card-hover);
    color: var(--text-strong);
    border-left-color: var(--muted);
  }
  .nav-btn.active {
    background: var(--accent-subtle);
    color: var(--text-strong);
    font-weight: 700;
    border-color: rgba(104, 153, 211, 0.28);
    border-left: 3px solid var(--accent);
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
  .scope-pill {
    display: inline-flex;
    align-items: center;
    padding: 5px 10px;
    border-radius: 6px;
    background: var(--accent-subtle);
    border: 1px solid var(--accent);
    color: var(--accent);
    font-size: 11.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.4px;
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
    white-space: nowrap;
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
    white-space: nowrap;
  }
  button.btn-action {
    background: var(--accent-subtle);
    color: var(--text-strong);
    border: 1px solid var(--accent);
    height: 38px;
    padding: 0 12px;
    border-radius: 7px;
    font-weight: 600;
    cursor: pointer;
    font-size: 12.5px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
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
    white-space: nowrap;
  }
  .content-wrap {
    max-width: 1180px;
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
  .summary-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 9px 0;
    border-bottom: 1px solid var(--border);
    font-size: 13px;
    gap: 10px;
  }
  .summary-row:last-child { border-bottom: none; }
  .summary-row span { color: var(--muted); }
  .summary-row strong { color: var(--text-strong); font-weight: 600; }
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
    grid-template-columns: repeat(auto-fill, minmax(195px, 1fr));
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
    white-space: nowrap;
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
    .nav-group-label { display: none; }
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
      margin-left: 0;
      border-radius: 7px;
      padding: 8px 12px;
      font-size: 12.5px;
      background: var(--card);
      border: 1px solid var(--border);
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
  <!-- DUAL-SCOPE SIDEBAR: HOUSEHOLD (GLOBAL) vs DEVICE -->
  <aside class="sidebar">
    <!-- SCOPE & DEVICE SWITCHER -->
    <div class="scope-box">
      <div class="scope-tabs">
        <button class="scope-tab" id="tab-scope-household" onclick="setScope('household')">System</button>
        <button class="scope-tab active" id="tab-scope-device" onclick="setScope('device')">Device</button>
      </div>
      <div class="device-picker-wrap" id="device-picker-wrap">
        <label>Active Device</label>
        <select id="fleet-device-picker" onchange="switchFleetDevice(this.value)"></select>
      </div>
    </div>

    <!-- HOUSEHOLD (GLOBAL) NAVIGATION -->
    <div class="nav-list hidden" id="nav-scope-household">
      <div class="nav-group-label">System</div>
      <button class="nav-btn" data-view="fleet_overview" onclick="switchView('fleet_overview', this)">
        <span>Overview & Devices</span>
        <span class="nav-badge" id="nav-fleet-count">1</span>
      </button>
      <button class="nav-btn" data-view="room_tracking" onclick="switchView('room_tracking', this)">
        <span>Room Calibration</span>
      </button>
      <button class="nav-btn" data-view="fleet_sync" onclick="switchView('fleet_sync', this)">
        <span>Groups &amp; Profiles</span>
      </button>
      <button class="nav-btn" data-view="backups" onclick="switchView('backups', this)">
        <span>Backup &amp; Restore</span>
      </button>

      <div class="nav-group-label">Shared Integrations</div>
      <button class="nav-btn" data-view="remotes" onclick="switchView('remotes', this)">
        <span>Remote Controls</span>
      </button>
      <button class="nav-btn" data-view="volume_routing" onclick="switchView('volume_routing', this)">
        <span>Volume Routing</span>
      </button>
      <button class="nav-btn" data-view="household" onclick="switchView('household', this)">
        <span>Shared Entities</span>
      </button>
      <button class="nav-btn" data-view="macros" onclick="switchView('macros', this)">
        <span>Macros & YAML</span>
      </button>
      <button class="nav-btn" data-view="studio_settings" onclick="switchView('studio_settings', this)">
        <span>Studio Settings</span>
      </button>
    </div>

    <!-- DEVICE-SCOPED NAVIGATION (CAPABILITY-AWARE) -->
    <div class="nav-list" id="nav-scope-device">
      <div class="nav-group-label">Overview</div>
      <button class="nav-btn active" data-view="dashboard" onclick="switchView('dashboard', this)">
        <span>Device Overview</span>
        <span class="nav-badge" id="nav-room-badge">--</span>
      </button>

      <div class="nav-group-label" id="nav-grp-dev-settings">Device Settings</div>
      <button class="nav-btn" id="nav-btn-home_display" data-view="home_display" onclick="switchView('home_display', this)">
        <span>Home &amp; Display</span>
      </button>
      <button class="nav-btn" id="nav-btn-power" data-view="power" onclick="switchView('power', this)">
        <span>Power</span>
      </button>
      <button class="nav-btn" id="nav-btn-voice" data-view="voice" onclick="switchView('voice', this)">
        <span>Voice Assistant</span>
      </button>
      <button class="nav-btn" id="nav-btn-audio" data-view="audio" onclick="switchView('audio', this)">
        <span>Audio &amp; Media</span>
      </button>

      <div class="nav-group-label">Connectivity &amp; Add-Ons</div>
      <button class="nav-btn" id="nav-btn-ble_addon" data-view="ble_addon" onclick="switchView('ble_addon', this)">
        <span>BLE Tracking &amp; Proxy</span>
        <span class="nav-badge" id="nav-ble-addon-badge">Add-On</span>
      </button>
      <button class="nav-btn" id="nav-btn-roaming_vpn" data-view="roaming_vpn" onclick="switchView('roaming_vpn', this)">
        <span>Roaming &amp; VPN</span>
        <span class="nav-badge" id="nav-vpn-addon-badge">Add-On</span>
      </button>

      <div class="nav-group-label">Administration</div>
      <button class="nav-btn" data-view="system" onclick="switchView('system', this)">
        <span>Diagnostics &amp; Identity</span>
        <span class="nav-badge" id="nav-esp-badge">0</span>
      </button>
    </div>

    <div class="sidebar-footer">
      <div class="field" style="margin-bottom:0;">
        <label>Home Assistant Theme</label>
        <select id="cfg-web_theme" onchange="onThemeChanged(this.value)">
          <option value="ha_auto">Home Assistant (Auto)</option>
          <option value="ha_dark">Home Assistant (Dark)</option>
          <option value="ha_light">Home Assistant (Light)</option>
        </select>
      </div>
    </div>
  </aside>

  <!-- MAIN CONTENT AREA -->
  <div class="main-area">
    <header class="topbar">
      <div class="topbar-status">
        <div style="display:flex;align-items:center;gap:10px;margin-right:6px;">
          <img src="/api/latter/brand/icon.png" alt="Latter" style="width:28px;height:28px;border-radius:6px;object-fit:contain;flex-shrink:0;" onerror="this.style.display='none'">
          <strong id="hdr-title" style="font-size:15px;color:var(--text-strong);">Latter</strong>
          <span class="nav-badge" id="hdr-sub">v1.8.8</span>
        </div>
        <div id="topbar-household-chips" class="hidden" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
          <div class="status-chip"><span id="top-hh-devices">Devices: --</span></div>
          <div class="status-chip"><span id="top-hh-alarm">Alarm: --</span></div>
        </div>
        <div id="topbar-device-chips" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
          <div class="status-chip"><span class="dot-live"></span><span id="top-room">Room: --</span></div>
          <div class="status-chip"><span id="top-speaker">Speaker: --</span></div>
          <div class="status-chip"><span id="top-media">Media: Idle</span></div>
        </div>
      </div>
      <div class="topbar-actions">
        <div id="dirty-indicator" class="dirty-banner">Unsaved</div>
        <button class="btn-secondary" onclick="refreshState(true)">Sync</button>
        <button class="btn-primary" onclick="saveAllConfig()">Save Changes</button>
      </div>
    </header>

    <div class="content-wrap">
      <!-- ================================================================== -->
      <!-- HOUSEHOLD SCOPE: 1. OVERVIEW & DEVICES                             -->
      <!-- ================================================================== -->
      <section id="view-fleet_overview" class="hidden">
        <div class="page-header">
          <h2>System Overview &amp; Devices</h2>
          <p>System-wide view of all onboarded ESPHome devices and shared integrations.</p>
        </div>

        <div class="card" style="margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:6px;">
            <div>
              <h3 style="margin:0;">Onboarded ESPHome Devices</h3>
              <p class="desc" style="margin:4px 0 0;">Select any device to inspect its live telemetry, assign its group, or customize per-device settings.</p>
            </div>
            <div id="bridge-device-bar" style="display:none;align-items:center;gap:8px;flex-wrap:wrap;">
              <select id="bridge-device-picker" style="min-width:230px;"></select>
              <button class="btn-secondary" style="border-color:var(--accent);color:var(--accent);" onclick="bridgeSelectedEsphomeDevice()">+ Bridge Existing Device</button>
            </div>
          </div>
          <div id="fleet-devices-list" class="native-controls-box"></div>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Shared System Configuration</h3>
            <p class="desc">Settings configured in the System scope apply automatically across all devices.</p>
            <div class="summary-row"><span>Security Alarm</span><strong id="hh-sum-alarm">--</strong></div>
            <div class="summary-row"><span>Primary Camera</span><strong id="hh-sum-camera">--</strong></div>
            <div class="summary-row"><span>Weather Provider</span><strong id="hh-sum-weather">--</strong></div>
            <div class="summary-row"><span>Calibrated BLE Rooms</span><strong id="hh-sum-ble">0</strong></div>
          </div>

          <div class="card">
            <h3>Quick System Navigation</h3>
            <p class="desc">Jump directly to room calibration, device groups &amp; profiles, backups, and shared entity mappings.</p>
            <div style="display:flex;flex-wrap:wrap;gap:8px;">
              <button class="btn-secondary" onclick="navigateToView('room_tracking')">Room Calibration</button>
              <button class="btn-secondary" onclick="navigateToView('fleet_sync')">Groups &amp; Profiles</button>
              <button class="btn-secondary" onclick="navigateToView('backups')">Backup &amp; Restore</button>
              <button class="btn-secondary" onclick="navigateToView('remotes')">Remote Controls</button>
              <button class="btn-secondary" onclick="navigateToView('volume_routing')">Volume Routing</button>
              <button class="btn-secondary" onclick="navigateToView('household')">Shared Entities</button>
              <button class="btn-secondary" onclick="navigateToView('macros')">Macros &amp; YAML</button>
            </div>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- HOUSEHOLD SCOPE: 2. ROOM CALIBRATION (GLOBAL SITE SURVEY)          -->
      <!-- ================================================================== -->
      <section id="view-room_tracking" class="hidden">
        <div class="page-header">
          <h2>Room Calibration</h2>
          <p>Calibrate Bluetooth proxy signal offsets for your home. Room offsets are shared globally across all mobile devices.</p>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:4px;">
            <h3 style="margin:0;">Site Survey & Per-Room Signal Offsets</h3>
            <label style="font-size:12px;font-weight:600;color:var(--accent);display:inline-flex;align-items:center;gap:6px;cursor:pointer;">
              <input type="checkbox" id="survey-fast-mode" onchange="toggleSurveyFastMode(this.checked)"> Fast Refresh (1.5s)
            </label>
          </div>
          <p class="desc">Walk from room to room with your active mobile device (<strong id="survey-device-name">Pocket Assistant</strong>) to compare live <strong>Raw dBm</strong>, <strong>Effective dBm</strong>, and <strong>Estimated Distance</strong>. Click <strong>Prioritize Here</strong> while standing in a room to calculate the offset needed to win over adjacent rooms.</p>
          <div id="rssi-container"></div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- HOUSEHOLD SCOPE: 3. DEVICE GROUPS & REUSABLE PROFILES              -->
      <!-- ================================================================== -->
      <section id="view-fleet_sync" class="hidden">
        <div class="page-header">
          <h2>Device Groups &amp; Reusable Profiles</h2>
          <p>Organize your ESPHome devices into logical groups, save reusable configuration profiles, and apply settings to a single device, a group, or your entire home.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:6px;">
              <h3 style="margin:0;">Reusable Configuration Profiles</h3>
            </div>
            <p class="desc">Capture display, dock, wake word, sensitivity, brightness, and sleep settings from the active device (<strong id="prof-active-dev-label">Device</strong>) as a reusable profile, or apply an existing profile to any target.</p>
            <div style="display:grid;grid-template-columns:1fr 1.2fr auto;gap:8px;margin-bottom:14px;">
              <input type="text" id="new-profile-name" placeholder="Profile Name (e.g. Guest Room)">
              <input type="text" id="new-profile-desc" placeholder="Optional description">
              <button class="btn-primary" onclick="captureCurrentDeviceProfile()">Capture Profile</button>
            </div>
            <div class="field">
              <label>Apply Profile Target Scope</label>
              <select id="profile-target-scope"></select>
            </div>
            <div id="saved-profiles-list" class="native-controls-box"></div>
          </div>

          <div class="card">
            <h3>Device Groups</h3>
            <p class="desc">Assign devices to logical groups (such as <em>Handheld Displays</em>, <em>Bedrooms</em>, or <em>Wall Panels</em>) for targeted profile deployment and group controls.</p>
            <div style="display:grid;grid-template-columns:1fr 1.3fr auto;gap:8px;margin-bottom:14px;">
              <input type="text" id="new-group-name" placeholder="New Group Name">
              <input type="text" id="new-group-desc" placeholder="Description">
              <button class="btn-secondary" onclick="createDeviceGroup()">+ Add Group</button>
            </div>
            <div id="device-groups-list" class="native-controls-box"></div>
          </div>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:6px;">
            <div>
              <h3 style="margin:0;">Live Group &amp; Multi-Device Controls</h3>
              <p class="desc" style="margin:4px 0 0;">Dispatch wake word, sensitivity, display, or sleep changes across all devices or a selected Device Group.</p>
            </div>
            <div style="min-width:220px;">
              <select id="group-ctrl-filter" onchange="renderFleetOverview(STATE.fleet_devices, STATE.fleet_controls, STATE.config)"></select>
            </div>
          </div>
          <div id="fleet-controls-list" class="native-controls-box"></div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- HOUSEHOLD SCOPE: 3B. SYSTEM & DEVICE BACKUP & RESTORE              -->
      <!-- ================================================================== -->
      <section id="view-backups" class="hidden">
        <div class="page-header">
          <h2>Backup &amp; Restore</h2>
          <p>Back up and restore your System configuration or individual ESPHome devices (including live on-device preferences) to the internal Latter Vault or your computer.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Create Snapshot or Export to Computer</h3>
            <p class="desc">Snapshots include Latter entity mappings, BLE room offsets, custom color palettes, and live ESPHome settings (wake words, sensitivities, timeouts, brightness, and sorting).</p>
            <div class="field">
              <label>Backup Scope</label>
              <select id="bkp-scope-select">
                <option value="system">Full System &amp; All Devices (.storage/latter.household + Devices)</option>
                <option value="device">Active Device Only (Latter Config + Live ESPHome Controls)</option>
              </select>
            </div>
            <div class="field">
              <label>Snapshot Label (Optional)</label>
              <input type="text" id="bkp-label-input" placeholder="e.g. Before Firmware Update, Baseline Config">
            </div>
            <div class="toggle-row" style="margin-bottom:14px;">
              <span>Include Roaming WireGuard Private Keys</span>
              <input type="checkbox" id="bkp-include-vpn" checked>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;">
              <button class="btn-primary" onclick="createVaultSnapshot()">Save to Internal Vault</button>
              <button class="btn-secondary" onclick="exportBackupToComputer('')">Download .JSON to Computer</button>
            </div>
          </div>

          <div class="card">
            <h3>Restore from Computer File (.JSON)</h3>
            <p class="desc">Upload a previously downloaded <code>latter-system-backup-*.json</code> or <code>latter-device-*.json</code> file from your computer. Device backups can be restored to the original device or cloned onto the currently selected device.</p>
            <div class="field">
              <label>Select Backup .JSON File</label>
              <input type="file" id="bkp-upload-file" accept=".json,application/json">
            </div>
            <div class="toggle-row" style="margin-bottom:14px;">
              <span>Also Restore Live ESPHome Device Preferences (Wake Word, Timeouts, Brightness)</span>
              <input type="checkbox" id="bkp-restore-esp" checked>
            </div>
            <button class="btn-primary" onclick="restoreFromUploadedFile()">Upload &amp; Restore Backup</button>
          </div>
        </div>

        <div class="card">
          <h3>Internal Snapshot Vault (<code>.storage/latter.backups</code>)</h3>
          <p class="desc">Restore any saved snapshot in 1 click, download a copy to your computer, or delete old restore points.</p>
          <div id="vault-backups-list" class="native-controls-box"></div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- HOUSEHOLD SCOPE: 4. VOLUME ROUTING (GLOBAL AVR OVERRIDES)          -->
      <!-- ================================================================== -->
      <section id="view-volume_routing" class="hidden">
        <div class="page-header">
          <h2>Volume Routing</h2>
          <p>Route volume commands to an external AV Receiver or amplifier whenever any device streams to a mapped speaker.</p>
        </div>

        <div class="card">
          <h3>External AVR & Amplifier Volume Overrides</h3>
          <p class="desc">When any Latter device controls playback on the selected Music Assistant speaker, volume up/down/set commands are routed to the target volume entity.</p>
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
      </section>

      <!-- ================================================================== -->
      <!-- HOUSEHOLD SCOPE: 5. REMOTE CONTROLS                                -->
      <!-- ================================================================== -->
      <section id="view-remotes" class="hidden">
        <div class="page-header">
          <h2>Remote Controls</h2>
          <p>Assign up to four household media players, AV receivers, or TVs and select the command protocol for each slot.</p>
        </div>

        <div class="card">
          <h3>Remote Control Slots</h3>
          <p class="desc">Select either a <code>remote.*</code> or <code>media_player.*</code> entity for each slot. Latter automatically pairs sibling entities on the same device.</p>
          <div class="grid-2" style="margin-bottom:0;">
            <div class="remote-slot-card" id="rslot-card-1">
              <div class="remote-slot-hdr">
                <strong>Slot 1</strong>
                <button class="btn-secondary" id="rslot-btn-1" onclick="activateRemoteSlot(1)">Set Active</button>
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>Target Entity</label>
                <select id="cfg-remote_1" onchange="markDirty()"></select>
              </div>
              <div id="embedded-remote-slot-1" class="native-controls-box"></div>
            </div>

            <div class="remote-slot-card" id="rslot-card-2">
              <div class="remote-slot-hdr">
                <strong>Slot 2</strong>
                <button class="btn-secondary" id="rslot-btn-2" onclick="activateRemoteSlot(2)">Set Active</button>
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>Target Entity</label>
                <select id="cfg-remote_2" onchange="markDirty()"></select>
              </div>
              <div id="embedded-remote-slot-2" class="native-controls-box"></div>
            </div>

            <div class="remote-slot-card" id="rslot-card-3">
              <div class="remote-slot-hdr">
                <strong>Slot 3</strong>
                <button class="btn-secondary" id="rslot-btn-3" onclick="activateRemoteSlot(3)">Set Active</button>
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>Target Entity</label>
                <select id="cfg-remote_3" onchange="markDirty()"></select>
              </div>
              <div id="embedded-remote-slot-3" class="native-controls-box"></div>
            </div>

            <div class="remote-slot-card" id="rslot-card-4">
              <div class="remote-slot-hdr">
                <strong>Slot 4</strong>
                <button class="btn-secondary" id="rslot-btn-4" onclick="activateRemoteSlot(4)">Set Active</button>
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>Target Entity</label>
                <select id="cfg-remote_4" onchange="markDirty()"></select>
              </div>
              <div id="embedded-remote-slot-4" class="native-controls-box"></div>
            </div>
          </div>
          <div id="embedded-remote-general" class="native-controls-box" style="margin-top:12px;"></div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- HOUSEHOLD SCOPE: 6. HOUSEHOLD ENTITIES                             -->
      <!-- ================================================================== -->
      <section id="view-household" class="hidden">
        <div class="page-header">
          <h2>Shared Entities</h2>
          <p>Configure shared security alarm, camera, weather provider, calendars, pinned entities, and notifications.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Global Entities</h3>
            <p class="desc">Primary entities shared across all rooms and devices.</p>
            <div class="field">
              <label>Security Alarm (alarm_control_panel)</label>
              <select id="cfg-alarm_entity" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>Primary Camera (camera.*)</label>
              <select id="cfg-camera_entity" onchange="markDirty(); renderCameraPreview(this.value);"></select>
            </div>
            <div id="cam-preview-box" style="display:none;align-items:center;gap:12px;margin-bottom:13px;padding:10px;background:var(--input-bg);border:1px solid var(--border);border-radius:8px;">
              <img id="cam-preview-img" class="wp-thumb circle" style="width:76px;height:76px;" alt="Camera Snapshot">
              <div style="flex:1;min-width:0;">
                <strong style="font-size:12.5px;color:var(--text-strong);display:block;">Camera Snapshot Preview</strong>
                <small style="color:var(--muted);display:block;margin:2px 0 6px;">Served via <code>/api/latter/camera/&lt;slug&gt;</code></small>
                <button class="btn-secondary" style="padding:5px 10px;font-size:11.5px;" onclick="renderCameraPreview(document.getElementById('cfg-camera_entity').value)">Refresh</button>
              </div>
            </div>
            <div class="field">
              <label>Weather Forecast Provider</label>
              <select id="cfg-weather_entity" onchange="markDirty()"></select>
            </div>
            <div class="field" style="margin-bottom:0;">
              <label>Shared Calendars (calendar.*)</label>
              <div style="display:flex;gap:8px;">
                <select id="cal-entity-picker"></select>
                <button class="btn-secondary" onclick="addCalendarEntity()">Add</button>
              </div>
              <div id="calendar-chips" class="chip-list"></div>
            </div>
          </div>

          <div class="card">
            <h3>Pinned Entities & Notification Test</h3>
            <p class="desc">Pin entities to the top of Room Control, or test sending an on-screen alert (<code>latter.notify_device</code>).</p>
            <div style="display:flex;gap:8px;margin-bottom:10px;">
              <select id="pin-entity-picker"></select>
              <button class="btn-secondary" onclick="addPinnedEntity()">Pin Entity</button>
            </div>
            <div id="pinned-chips" class="chip-list" style="margin-bottom:14px;"></div>

            <div style="padding-top:12px;border-top:1px solid var(--border);">
              <label style="font-size:12px;font-weight:700;color:var(--text-strong);display:block;margin-bottom:6px;">Send Test Notification</label>
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
                  <input type="checkbox" id="test-alert-cam" checked> Include Camera Snapshot
                </label>
                <button class="btn-primary" onclick="sendTestNotification()">Send Notification</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- HOUSEHOLD SCOPE: 7. MACROS & YAML                                  -->
      <!-- ================================================================== -->
      <section id="view-macros" class="hidden">
        <div class="page-header">
          <h2>Macros & YAML</h2>
          <p>Bind on-device macro slots or hardware triggers to Home Assistant entities and export ESPHome YAML snippets.</p>
        </div>

        <div class="card" style="margin-bottom:16px;">
          <h3>Macro & Trigger Bindings</h3>
          <p class="desc">Map slot IDs (such as <code>macro_1</code>..<code>macro_5</code> in the Pocket Assistant Macros tool or custom hardware buttons) to any Home Assistant entity via <code>latter.trigger_binding</code>.</p>
          <div id="bindings-list"></div>
          <button class="btn-secondary" onclick="addBindingRow('', '', 'toggle'); markDirty();">+ Add Binding</button>
        </div>

        <div class="card" style="margin-bottom:16px;">
          <h3>1-Line Drop-In ESPHome Mixin Packages</h3>
          <p class="desc">Add any of these 1-line packages under <code>packages:</code> in an existing ESPHome device's YAML to unlock BLE room tracking, WireGuard roaming VPN, or stationary BLE room scanning with zero substitution variables required.</p>
          <div class="grid-2" style="margin-bottom:0;">
            <div style="background:var(--input-bg);border:1px solid var(--border);border-radius:8px;padding:12px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <strong style="color:var(--text-strong);font-size:13px;">1. Roaming BLE Room Presence Beacon</strong>
                <button class="btn-secondary" style="padding:4px 10px;font-size:11.5px;" onclick="copyTextById('mixin-ble-beacon')">Copy</button>
              </div>
              <small style="color:var(--muted);display:block;margin-bottom:8px;">Makes any portable/battery ESP32 trackable room-to-room by Latter (disambiguated automatically by hardware MAC).</small>
              <pre id="mixin-ble-beacon" class="mono" style="margin:0;padding:8px;background:var(--card);border:1px solid var(--border);border-radius:6px;overflow-x:auto;">packages:
  latter.ble: github://slampton/esphome-latter-core/mixins/ble_beacon.yaml@main</pre>
            </div>

            <div style="background:var(--input-bg);border:1px solid var(--border);border-radius:8px;padding:12px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <strong style="color:var(--text-strong);font-size:13px;">2. Roaming WireGuard VPN Tunnel</strong>
                <button class="btn-secondary" style="padding:4px 10px;font-size:11.5px;" onclick="copyTextById('mixin-vpn')">Copy</button>
              </div>
              <small style="color:var(--muted);display:block;margin-bottom:8px;">Adds encrypted remote access over phone hotspots + live VPN status sensors (generate keys in Device &rarr; Roaming &amp; VPN).</small>
              <pre id="mixin-vpn" class="mono" style="margin:0;padding:8px;background:var(--card);border:1px solid var(--border);border-radius:6px;overflow-x:auto;">packages:
  latter.vpn: github://slampton/esphome-latter-core/mixins/roaming_vpn.yaml@main</pre>
            </div>

            <div style="background:var(--input-bg);border:1px solid var(--border);border-radius:8px;padding:12px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <strong style="color:var(--text-strong);font-size:13px;">3. Stationary Room BLE Scanner Proxy</strong>
                <button class="btn-secondary" style="padding:4px 10px;font-size:11.5px;" onclick="copyTextById('mixin-ble-proxy')">Copy</button>
              </div>
              <small style="color:var(--muted);display:block;margin-bottom:8px;">Turns any mains-powered ESP32 node into an active room Bluetooth scanner for Latter's Room Calibration radar.</small>
              <pre id="mixin-ble-proxy" class="mono" style="margin:0;padding:8px;background:var(--card);border:1px solid var(--border);border-radius:6px;overflow-x:auto;">packages:
  latter.proxy: github://slampton/esphome-latter-core/mixins/ble_proxy.yaml@main</pre>
            </div>

            <div style="background:var(--input-bg);border:1px solid var(--border);border-radius:8px;padding:12px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <strong style="color:var(--text-strong);font-size:13px;">4. Core Studio Discovery &amp; Diagnostics</strong>
                <button class="btn-secondary" style="padding:4px 10px;font-size:11.5px;" onclick="copyTextById('mixin-core')">Copy</button>
              </div>
              <small style="color:var(--muted);display:block;margin-bottom:8px;">Adds Uptime, Wi-Fi Signal, Restart button, and automatic Latter discovery for custom nodes.</small>
              <pre id="mixin-core" class="mono" style="margin:0;padding:8px;background:var(--card);border:1px solid var(--border);border-radius:6px;overflow-x:auto;">packages:
  latter.core: github://slampton/esphome-latter-core/mixins/diagnostics.yaml@main</pre>
            </div>
          </div>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:8px;">
            <div>
              <h3 style="margin:0;">ESPHome YAML Generator</h3>
              <p class="desc" style="margin:4px 0 0;">Generate a copy-pasteable ESPHome YAML contract for custom devices.</p>
            </div>
            <button class="btn-secondary" onclick="copyGeneratedYaml()">Copy YAML</button>
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

      <!-- ================================================================== -->
      <!-- HOUSEHOLD SCOPE: 8. STUDIO SETTINGS                                -->
      <!-- ================================================================== -->
      <section id="view-studio_settings" class="hidden">
        <div class="page-header">
          <h2>Studio Settings</h2>
          <p>Global web interface appearance and external reverse-proxy URL configuration.</p>
        </div>

        <div class="card">
          <h3>Appearance & Reverse Proxy</h3>
          <div class="grid-2" style="margin-bottom:0;">
            <div class="field" style="margin-bottom:0;">
              <label>Home Assistant Theme</label>
              <select id="cfg-web_theme_mobile" onchange="onThemeChanged(this.value)">
                <option value="ha_auto">Home Assistant (Auto)</option>
                <option value="ha_dark">Home Assistant (Dark)</option>
                <option value="ha_light">Home Assistant (Light)</option>
              </select>
            </div>
            <div class="field" style="margin-bottom:0;">
              <label>Companion HTTPS Base URL Override (e.g. https://ha.example.com)</label>
              <input type="text" id="cfg-companion_base_url" placeholder="Auto-detected from Home Assistant Network settings" oninput="markDirty()">
            </div>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE SCOPE: 0. SELECT A DEVICE PROMPT (WHEN UNSELECTED)          -->
      <!-- ================================================================== -->
      <section id="view-select_device_prompt" class="hidden">
        <div class="page-header">
          <h2>Select a Device</h2>
          <p>Choose an onboarded ESPHome device from the list below or the sidebar dropdown to view its dashboard and device-specific settings.</p>
        </div>
        <div class="card">
          <h3>Available Devices</h3>
          <div id="prompt-devices-list" class="native-controls-box"></div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE SCOPE: 1. DEVICE OVERVIEW (CAPABILITY-AWARE)                -->
      <!-- ================================================================== -->
      <section id="view-dashboard">
        <div class="page-header">
          <h2 id="dash-header-title">Device Overview</h2>
          <p id="dash-header-desc">Live device sensors, configurable parameters, hardware diagnostics, and quick backups.</p>
        </div>

        <div class="hero-stats">
          <div class="stat-box"><span>Integration Tier</span><strong id="st-tier">--</strong></div>
          <div class="stat-box"><span>Assigned Room</span><strong id="st-room">--</strong></div>
          <div class="stat-box"><span>Device Group</span><strong id="st-group">Unassigned</strong></div>
          <div class="stat-box"><span>Exposed Entities</span><strong id="st-entities">0</strong></div>
        </div>

        <div class="grid-2">
          <!-- LEFT CARD: LIVE DEVICE CONTROLS & SENSORS -->
          <div class="card">
            <h3 id="dash-primary-card-title">Device Controls &amp; Live Sensors</h3>
            <p class="desc" id="dash-primary-card-desc">Directly inspect and adjust this ESPHome device's exposed sensors, numbers, switches, and options.</p>
            <div id="dash-device-entities" class="native-controls-box"></div>
          </div>

          <!-- RIGHT CARD: DEVICE MANAGEMENT, BACKUP & OPTIONAL CONTEXT -->
          <div class="card">
            <h3>Device Management &amp; Quick Actions</h3>
            <p class="desc">Assign this device's room or group, trigger a quick backup, or enable optional Latter add-on modules.</p>
            <div class="field">
              <label>Assigned Room / Area</label>
              <select id="quick-area" onchange="quickSwitchArea(this.value)"></select>
            </div>
            <div class="field" id="dash-speaker-field">
              <label>Active Speaker Target</label>
              <select id="quick-speaker" onchange="quickSwitchSpeaker(this.value)"></select>
            </div>
            <div class="summary-row">
              <span>ESPHome Model / Version</span>
              <strong id="dash-hw-model">--</strong>
            </div>
            <div class="summary-row">
              <span>BLE Room Tracking</span>
              <strong id="dash-ble-mode">--</strong>
            </div>
            <div class="summary-row" id="dash-row-ble-proxy">
              <span>Nearest BLE Proxy</span>
              <strong id="dash-ble-proxy">--</strong>
            </div>
            <div class="summary-row" id="dash-row-media">
              <span>Now Playing</span>
              <strong id="dash-media-summary">Idle</strong>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:16px;">
              <button class="btn-primary" onclick="createDeviceQuickBackup()">Backup Device</button>
              <button class="btn-secondary" onclick="exportBackupToComputer('device')">Download .JSON</button>
              <button class="btn-secondary" onclick="navigateToView('ble_addon')">BLE Add-On</button>
              <button class="btn-secondary" onclick="navigateToView('roaming_vpn')">Roaming VPN</button>
              <button class="btn-secondary" onclick="navigateToView('system')">Diagnostics</button>
            </div>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE SCOPE: 5B. BLE TRACKING & PROXY ADD-ON                      -->
      <!-- ================================================================== -->
      <section id="view-ble_addon" class="hidden">
        <div class="page-header">
          <h2>BLE Room Tracking &amp; Scanner Proxy</h2>
          <p>Configure Bluetooth room presence tracking for this device, or install a 1-line YAML mixin to enable it.</p>
        </div>

        <div class="card" id="ble-addon-missing-banner" style="margin-bottom:16px;border-color:var(--accent);">
          <h3>Add-On Available: 1-Line BLE Mixin for ESPHome</h3>
          <p class="desc">This device does not currently broadcast a Latter BLE iBeacon. Depending on whether this device is portable or stationary, paste one of the 1-line packages below into its YAML in ESPHome Device Builder and recompile:</p>
          <div class="grid-2" style="margin-bottom:0;">
            <div style="background:var(--input-bg);border:1px solid var(--border);border-radius:8px;padding:12px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <strong style="color:var(--text-strong);">Option A: Portable / Handheld Device (BLE Beacon)</strong>
                <button class="btn-secondary" style="padding:4px 10px;font-size:11.5px;" onclick="copyTextById('dev-ble-beacon-snip')">Copy</button>
              </div>
              <small style="color:var(--muted);display:block;margin-bottom:8px;">Broadcasts a BLE iBeacon so Latter tracks which room this device is in.</small>
              <pre id="dev-ble-beacon-snip" class="mono" style="margin:0;padding:8px;background:var(--card);border:1px solid var(--border);border-radius:6px;overflow-x:auto;">packages:
  latter.ble: github://slampton/esphome-latter-core/mixins/ble_beacon.yaml@main</pre>
            </div>
            <div style="background:var(--input-bg);border:1px solid var(--border);border-radius:8px;padding:12px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <strong style="color:var(--text-strong);">Option B: Stationary Room Sensor (BLE Scanner Proxy)</strong>
                <button class="btn-secondary" style="padding:4px 10px;font-size:11.5px;" onclick="copyTextById('dev-ble-proxy-snip')">Copy</button>
              </div>
              <small style="color:var(--muted);display:block;margin-bottom:8px;">Turns this stationary ESP32 (e.g. Bed Presence) into an active room Bluetooth scanner for your mobile displays.</small>
              <pre id="dev-ble-proxy-snip" class="mono" style="margin:0;padding:8px;background:var(--card);border:1px solid var(--border);border-radius:6px;overflow-x:auto;">packages:
  latter.proxy: github://slampton/esphome-latter-core/mixins/ble_proxy.yaml@main</pre>
            </div>
          </div>
        </div>

        <div class="card">
          <h3>Device BLE Tracking Settings</h3>
          <p class="desc">Configure how Latter tracks this device across room Bluetooth proxies when beaconing is enabled.</p>
          <div class="toggle-row">
            <span>Enable ESPHome BLE Proxy Room Tracking for This Device</span>
            <input type="checkbox" id="cfg-native_ble_tracking_ mirror" onchange="document.getElementById('cfg-native_ble_tracking').checked = this.checked; markDirty();">
          </div>
          <div class="toggle-row" style="margin-bottom:10px;">
            <span>Auto-Switch Active Room on Movement</span>
            <input type="checkbox" id="cfg-ble_auto_switch_mirror" onchange="document.getElementById('cfg-ble_auto_switch').checked = this.checked; markDirty();">
          </div>
          <button class="btn-secondary" onclick="navigateToView('room_tracking')">Open Global Room Calibration Radar &rarr;</button>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE SCOPE: 2. HOME & DISPLAY                                    -->
      <!-- ================================================================== -->
      <section id="view-home_display" class="hidden">
        <div class="page-header">
          <h2>Home & Display</h2>
          <p>Configure this device's home screen layout, clock face, display brightness, color profile, and wallpapers.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Home Screen</h3>
            <p class="desc">Configure your device's clock style, home shortcuts, weather background, and dock order.</p>
            <div id="embedded-home" class="native-controls-box" style="margin-bottom:14px;"></div>
            <div class="field" style="margin-bottom:0;">
              <label>Home Dock App Order (comma-separated tokens)</label>
              <input type="text" id="cfg-dock_apps" placeholder="music,room,remote,games,tools" oninput="markDirty()">
            </div>
          </div>

          <div class="card">
            <h3>Display Settings</h3>
            <p class="desc">Adjust screen brightness, UI color profile, auto-brightness schedule, and screen geometry.</p>
            <div id="embedded-display" class="native-controls-box" style="margin-bottom:14px;"></div>
            <div class="field" style="margin-bottom:14px;padding:12px;border-radius:10px;background:var(--input-bg);border:1px solid var(--border);">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <label style="margin-bottom:0;font-weight:600;">Custom Color Profile & Household Library</label>
                <button type="button" class="btn-secondary" style="padding:4px 10px;font-size:12px;" onclick="openColorWheelModal('device')">+ Color Wheel...</button>
              </div>
              <div style="display:flex;gap:8px;align-items:center;">
                <span id="dev-color-swatch" style="width:24px;height:24px;border-radius:50%;border:2px solid #fff;background:#3898FF;flex-shrink:0;"></span>
                <select id="dev-custom-palette-select" onchange="onSelectDeviceCustomPalette(this.value)" style="flex:1;"></select>
              </div>
            </div>
            <div class="field" style="margin-bottom:0;">
              <label>Screen Bezel Mask & Resolution</label>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                <select id="cfg-display_shape" onchange="markDirty()">
                  <option value="circle">Circular Display</option>
                  <option value="square">Square / Rectangular</option>
                </select>
                <select id="cfg-art_size" onchange="markDirty()">
                  <option value="466">466x466 px (1.75" Round)</option>
                  <option value="410x502">410x502 px (2.06" Watch)</option>
                  <option value="360">360x360 px</option>
                  <option value="240">240x240 px</option>
                  <option value="480">480x480 px (Wall Panel)</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Upload Wallpaper</h3>
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
            <h3>Wallpaper Rotation</h3>
            <p class="desc">Star multiple wallpapers in the gallery below to rotate through favorites automatically.</p>
            <div class="field" style="margin-bottom:0;">
              <label>Rotation Interval</label>
              <select id="cfg-wallpaper_cycle_minutes" onchange="markDirty()">
                <option value="0">Off (Keep Selected Wallpaper)</option>
                <option value="15">Every 15 Minutes</option>
                <option value="60">Every Hour</option>
                <option value="360">Every 6 Hours</option>
                <option value="1440">Every 24 Hours</option>
              </select>
            </div>
          </div>
        </div>

        <div class="card">
          <h3>Wallpaper Gallery</h3>
          <p class="desc">Low-power AMOLED presets and uploaded custom wallpapers for this device.</p>
          <div id="wp-gallery-grid" class="wp-gallery"></div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE SCOPE: 3. POWER                                             -->
      <!-- ================================================================== -->
      <section id="view-power" class="hidden">
        <div class="page-header">
          <h2>Power Management</h2>
          <p>Configure sleep timeouts, wake gestures, docked screensaver behavior, and monitor battery health for this device.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Sleep & Wake Behavior</h3>
            <p class="desc">Control inactivity timeouts, pickup-to-wake, tap-to-wake, docked screensaver, and hardware hibernate.</p>
            <div id="embedded-sleep" class="native-controls-box"></div>
          </div>

          <div class="card">
            <h3>Battery & Power Telemetry</h3>
            <p class="desc">Live battery charge level, charging status, PMIC voltage, and internal temperature.</p>
            <div id="embedded-battery" class="native-controls-box"></div>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE SCOPE: 4. VOICE ASSISTANT                                   -->
      <!-- ================================================================== -->
      <section id="view-voice" class="hidden">
        <div class="page-header">
          <h2>Voice Assistant</h2>
          <p>Configure on-device wake words, detection sensitivity, and room context synchronization for Assist.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Wake Word & Microphone</h3>
            <p class="desc">Hardware controls exposed by this device's voice pipeline.</p>
            <div id="embedded-voice" class="native-controls-box"></div>
          </div>

          <div class="card">
            <h3>Room Context Sync</h3>
            <p class="desc">Automatically update this device's Home Assistant Area assignment when its active room changes so room-aware voice commands target the current room.</p>
            <div class="toggle-row">
              <span>Sync Active Room to Home Assistant Device Area</span>
              <input type="checkbox" id="cfg-sync_device_area" onchange="markDirty()">
            </div>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE SCOPE: 5. AUDIO & MEDIA                                     -->
      <!-- ================================================================== -->
      <section id="view-audio" class="hidden">
        <div class="page-header">
          <h2>Audio & Media</h2>
          <p>Configure onboard sound chimes, library sorting, and default speaker behavior for this device.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Sound & Library Sorting</h3>
            <p class="desc">Adjust onboard alert volume, chimes, volume step size, and Music Assistant browse sort order.</p>
            <div id="embedded-sound" class="native-controls-box" style="margin-bottom:10px;"></div>
            <div id="embedded-music" class="native-controls-box"></div>
          </div>

          <div class="card">
            <h3>Device Speaker & Room Handoff</h3>
            <p class="desc">Select this device's default speaker and room media handoff behavior. (Shared AVR volume overrides are configured in System &rarr; Volume Routing.)</p>
            <div class="field">
              <label>Default Speaker Entity</label>
              <select id="cfg-default_speaker" onchange="markDirty()"></select>
            </div>
            <div class="toggle-row" style="margin-bottom:12px;">
              <span>Auto-Link Room Speaker & Remote on Room Change</span>
              <input type="checkbox" id="cfg-area_handoff" onchange="markDirty()">
            </div>
            <button class="btn-secondary" onclick="navigateToView('volume_routing')">Configure Global Volume Routing &rarr;</button>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE SCOPE: 6. ROAMING & WIREGUARD VPN                           -->
      <!-- ================================================================== -->
      <section id="view-roaming_vpn" class="hidden">
        <div class="page-header">
          <h2>Roaming &amp; WireGuard VPN</h2>
          <p>Keep this device connected to Home Assistant and Latter when away from home over an encrypted ESPHome WireGuard tunnel.</p>
        </div>

        <div class="card" id="vpn-addon-missing-banner" style="margin-bottom:16px;border-color:var(--accent);">
          <h3>Add-On Not Yet Installed on This Device</h3>
          <p class="desc" style="margin-bottom:0;">This device does not currently report an active WireGuard component. To enable remote roaming on this device: <strong>1)</strong> Click <strong>Generate WireGuard Keys</strong> below, <strong>2)</strong> Copy the <strong>1-Line Mixin Package</strong> snippet in Box 1 into your device's YAML in ESPHome Device Builder, and <strong>3)</strong> Recompile.</p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>System WireGuard Endpoint</h3>
            <p class="desc">Configure your home WireGuard server endpoint and public key once for all roaming devices.</p>
            <div class="field">
              <label>Public Endpoint (Hostname/IP:Port)</label>
              <input type="text" id="cfg-vpn_endpoint" placeholder="vpn.example.com:51820" oninput="markDirty()">
            </div>
            <div class="field">
              <label>WireGuard Server Public Key (Base64)</label>
              <input type="text" id="cfg-vpn_server_public_key" placeholder="Server Curve25519 Public Key" oninput="markDirty()">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
              <div class="field" style="margin-bottom:0;">
                <label>Tunnel Subnet (CIDR)</label>
                <input type="text" id="cfg-vpn_subnet" placeholder="10.10.10.0/24" oninput="markDirty()">
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>Home Assistant Tunnel IP</label>
                <input type="text" id="cfg-vpn_ha_ip" placeholder="10.10.10.1" oninput="markDirty()">
              </div>
            </div>
          </div>

          <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:4px;">
              <h3 style="margin:0;">Device Roaming Identity</h3>
              <button class="btn-primary" onclick="generateDeviceVpnKeys()">Generate WireGuard Keys</button>
            </div>
            <p class="desc">Generate a dedicated Curve25519 keypair and tunnel IP for this ESPHome device.</p>
            <div class="toggle-row" style="margin-bottom:10px;">
              <span>Enable Roaming WireGuard Profile</span>
              <input type="checkbox" id="cfg-vpn_enabled" onchange="markDirty()">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
              <div class="field">
                <label>Device Tunnel IP</label>
                <input type="text" id="cfg-vpn_client_ip" placeholder="10.10.10.2" oninput="markDirty()">
              </div>
              <div class="field">
                <label>Phone Hotspot / Travel Wi-Fi SSID</label>
                <input type="text" id="cfg-vpn_hotspot_ssid" placeholder="iPhone Hotspot" oninput="markDirty()">
              </div>
            </div>
            <div class="field">
              <label>Device Public Key (Add to WireGuard Server)</label>
              <input type="text" id="cfg-vpn_public_key" readonly class="mono">
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
              <div class="field" style="margin-bottom:0;">
                <label>Device Private Key</label>
                <input type="text" id="cfg-vpn_private_key" class="mono" oninput="markDirty()">
              </div>
              <div class="field" style="margin-bottom:0;">
                <label>Preshared Key (PSK)</label>
                <input type="text" id="cfg-vpn_preshared_key" class="mono" oninput="markDirty()">
              </div>
            </div>
          </div>
        </div>

        <div class="grid-2">
          <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
              <h3 style="margin:0;">1. ESPHome WireGuard & Hotspot YAML</h3>
              <button class="btn-secondary" onclick="copyTextById('vpn-esphome-yaml')">Copy ESPHome YAML</button>
            </div>
            <p class="desc">Paste into your device's ESPHome YAML configuration to enable multi-Wi-Fi roaming and WireGuard.</p>
            <pre id="vpn-esphome-yaml" class="mono" style="background:var(--input-bg);border:1px solid var(--border);border-radius:7px;padding:12px;overflow-x:auto;max-height:260px;margin:0;color:var(--text-strong);line-height:1.45;"></pre>
          </div>

          <div class="card">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
              <h3 style="margin:0;">2. WireGuard Server / HA Add-on Peer Config</h3>
              <button class="btn-secondary" onclick="copyTextById('vpn-server-peer')">Copy Peer Config</button>
            </div>
            <p class="desc">Add this peer block to your WireGuard server (UniFi, OPNsense, or Home Assistant WireGuard Add-on).</p>
            <pre id="vpn-server-peer" class="mono" style="background:var(--input-bg);border:1px solid var(--border);border-radius:7px;padding:12px;overflow-x:auto;max-height:260px;margin:0;color:var(--text-strong);line-height:1.45;"></pre>
          </div>
        </div>
      </section>

      <!-- ================================================================== -->
      <!-- DEVICE SCOPE: 7. DIAGNOSTICS & IDENTITY                            -->
      <!-- ================================================================== -->
      <section id="view-system" class="hidden">
        <div class="page-header">
          <h2>Diagnostics &amp; Identity</h2>
          <p>Execute device actions, view network diagnostics, and configure device identity and tracking options.</p>
        </div>

        <div class="card" style="margin-bottom:16px;">
          <h3>Device Actions</h3>
          <p class="desc">One-tap actions exposed by this ESPHome device.</p>
          <div id="embedded-actions" class="action-btn-grid"></div>
        </div>

        <div class="grid-2">
          <div class="card">
            <h3>Network & Diagnostics</h3>
            <p class="desc">Wi-Fi signal, IP address, uptime, memory, and firmware status.</p>
            <div id="embedded-network" class="native-controls-box"></div>
          </div>

          <div class="card">
            <h3>Device Identity & Presence Tracking</h3>
            <p class="desc">Configure this device's slug, archetype, and BLE beacon tracking.</p>
            <div class="field">
              <label>ESPHome Device Slug (sensor.&lt;slug&gt;_*)</label>
              <input type="text" id="cfg-device_slug" oninput="markDirty(); renderYamlGenerator();">
            </div>
            <div class="field">
              <label>Device Archetype, Group &amp; Room Cards Per Page</label>
              <div style="display:grid;grid-template-columns:1.4fr 1.2fr 0.7fr;gap:8px;">
                <select id="cfg-device_profile" onchange="markDirty()">
                  <option value="mobile_display">Mobile Smart Display</option>
                  <option value="stationary_display">Stationary Wall / Desk Display</option>
                  <option value="headless_node">Headless Sensor / Button Node</option>
                </select>
                <select id="cfg-device_group" onchange="markDirty()"></select>
                <input type="number" id="cfg-default_page_size" min="1" max="20" value="3" oninput="markDirty(); renderYamlGenerator();">
              </div>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">
              <button type="button" class="btn-secondary" onclick="createDeviceQuickBackup()">Backup This Device</button>
              <button type="button" class="btn-secondary" onclick="exportBackupToComputer('device')">Download Device .JSON</button>
              <button type="button" class="btn-secondary" onclick="navigateToView('fleet_sync')">Apply Profile &rarr;</button>
              <button type="button" class="btn-danger" onclick="removeManagedDevice(STATE.entry_id, STATE.title)">Remove Device</button>
            </div>
            <div class="toggle-row">
              <span>Enable ESPHome BLE Proxy Room Tracking</span>
              <input type="checkbox" id="cfg-native_ble_tracking" onchange="markDirty()">
            </div>
            <div class="toggle-row" style="margin-bottom:10px;">
              <span>Auto-Switch Active Room on Movement</span>
              <input type="checkbox" id="cfg-ble_auto_switch" onchange="markDirty()">
            </div>
            <div id="embedded-room-ble" class="native-controls-box" style="margin-bottom:12px;"></div>
            <div class="field">
              <label>Default Fallback Room</label>
              <select id="cfg-default_area" onchange="markDirty()"></select>
            </div>
            <div class="field">
              <label>BLE iBeacon UUID</label>
              <input type="text" id="cfg-ble_beacon_uuid" oninput="markDirty(); renderYamlGenerator();">
            </div>
            <div class="field" style="margin-bottom:0;">
              <label>External Room Sensor Override (Optional)</label>
              <select id="cfg-presence_entity" onchange="markDirty()"></select>
            </div>
          </div>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-bottom:12px;">
            <div>
              <h3 style="margin:0;">Entity Inspector</h3>
              <p class="desc" style="margin:4px 0 0;">Search and inspect all raw entities registered to this ESPHome device.</p>
            </div>
            <input type="text" id="esp-search" style="max-width:300px;" placeholder="Filter by name or entity_id..." oninput="renderRawEntityList()">
          </div>
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
let CALENDARS = [];
let IS_DIRTY = false;
let INITIAL_FORM_LOADED = false;
// If opened via 'Visit' link on a different hostname (e.g. nabu.casa vs local IP), match the referrer's HA origin
try {
  if (document.referrer && window.parent === window) {
    const refUrl = new URL(document.referrer);
    if (refUrl.origin !== window.location.origin && (refUrl.pathname.startsWith("/config") || refUrl.pathname.startsWith("/latter"))) {
      window.location.replace(refUrl.origin + window.location.pathname + window.location.search);
    }
  }
} catch (_e) {}
const URL_PARAMS = new URLSearchParams(window.location.search);
const ENTERED_VIA_HOUSEHOLD = ["system", "household"].includes(URL_PARAMS.get("scope"));
let CURRENT_SCOPE = ENTERED_VIA_HOUSEHOLD ? "household" : "device";
let DEVICE_SELECTED = !ENTERED_VIA_HOUSEHOLD;
let CURRENT_THEME_PREF = localStorage.getItem("latter_web_theme") || "ha_auto";
let POLL_TIMER = null;

const HOUSEHOLD_VIEWS = [
  "fleet_overview",
  "room_tracking",
  "fleet_sync",
  "backups",
  "remotes",
  "volume_routing",
  "household",
  "macros",
  "studio_settings"
];

const DEVICE_VIEWS = [
  "select_device_prompt",
  "dashboard",
  "home_display",
  "power",
  "voice",
  "audio",
  "ble_addon",
  "roaming_vpn",
  "system"
];

const ALL_VIEWS = HOUSEHOLD_VIEWS.concat(DEVICE_VIEWS);

const HA_CSS_VARS = [
  "--primary-background-color",
  "--secondary-background-color",
  "--card-background-color",
  "--primary-text-color",
  "--secondary-text-color",
  "--primary-color",
  "--accent-color",
  "--divider-color",
  "--success-color",
  "--warning-color",
  "--error-color"
];

const sysMedia = window.matchMedia("(prefers-color-scheme: dark)");
sysMedia.addEventListener("change", () => {
  if (CURRENT_THEME_PREF === "ha_auto") applyTheme("ha_auto");
});

function clearCustomCssVars() {
  HA_CSS_VARS.forEach(v => document.documentElement.style.removeProperty(v));
  document.documentElement.style.removeProperty("--input-fill-color");
}

function trySyncFromParentHaFrame() {
  try {
    const hostWin = (window.parent && window.parent !== window) ? window.parent : window.opener;
    if (!hostWin || !hostWin.document) return false;
    const computed = hostWin.getComputedStyle(hostWin.document.documentElement);
    const bg = computed.getPropertyValue("--primary-background-color").trim();
    if (!bg) return false;
    HA_CSS_VARS.forEach(v => {
      const val = computed.getPropertyValue(v).trim();
      if (val) document.documentElement.style.setProperty(v, val);
    });
    document.documentElement.style.setProperty("--input-fill-color", bg);
    return true;
  } catch (_e) {
    return false;
  }
}

function populateThemeDropdowns(haThemes, selectedPref) {
  ["cfg-web_theme", "cfg-web_theme_mobile"].forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    const baseOpts = [
      {id: "ha_auto", name: "Home Assistant (Auto)"},
      {id: "ha_dark", name: "Home Assistant (Dark)"},
      {id: "ha_light", name: "Home Assistant (Light)"}
    ];
    Object.keys(haThemes || {}).sort().forEach(tName => {
      baseOpts.push({id: tName, name: `HA Theme: ${tName}`});
    });
    sel.innerHTML = baseOpts.map(o =>
      `<option value="${o.id}" ${o.id === selectedPref ? 'selected' : ''}>${o.name}</option>`
    ).join("");
  });
}

function applyTheme(pref) {
  CURRENT_THEME_PREF = pref || "ha_auto";
  if (CURRENT_THEME_PREF === "dark") CURRENT_THEME_PREF = "ha_dark";
  if (CURRENT_THEME_PREF === "light") CURRENT_THEME_PREF = "ha_light";
  if (CURRENT_THEME_PREF === "system") CURRENT_THEME_PREF = "ha_auto";

  clearCustomCssVars();
  const haThemes = STATE?.ha_themes || {};

  if (CURRENT_THEME_PREF === "ha_dark") {
    document.body.setAttribute("data-theme", "dark");
  } else if (CURRENT_THEME_PREF === "ha_light") {
    document.body.setAttribute("data-theme", "light");
  } else if (haThemes[CURRENT_THEME_PREF]) {
    document.body.setAttribute("data-theme", sysMedia.matches ? "dark" : "light");
    const tVars = haThemes[CURRENT_THEME_PREF];
    Object.entries(tVars).forEach(([k, v]) => {
      document.documentElement.style.setProperty(`--${k}`, v);
    });
    if (tVars["ha-card-background"] && !tVars["card-background-color"]) {
      document.documentElement.style.setProperty("--card-background-color", tVars["ha-card-background"]);
    }
    if (tVars["primary-background-color"]) {
      document.documentElement.style.setProperty("--input-fill-color", tVars["primary-background-color"]);
    }
  } else {
    document.body.setAttribute("data-theme", sysMedia.matches ? "dark" : "light");
    trySyncFromParentHaFrame();
  }

  localStorage.setItem("latter_web_theme", CURRENT_THEME_PREF);
  ["cfg-web_theme", "cfg-web_theme_mobile"].forEach(id => {
    const sel = document.getElementById(id);
    if (sel && sel.value !== CURRENT_THEME_PREF) sel.value = CURRENT_THEME_PREF;
  });
}

applyTheme(CURRENT_THEME_PREF);
if (CURRENT_SCOPE === "household") {
  window.addEventListener("DOMContentLoaded", () => setScope("household", "fleet_overview"));
}

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

function updateTopHeaderForScope() {
  const isHH = (CURRENT_SCOPE === "household") || !DEVICE_SELECTED;
  const devTitle = STATE?.esphome?.device?.name || STATE?.title || "Device";
  document.getElementById("hdr-title").textContent = isHH ? "Latter" : devTitle;
  document.getElementById("topbar-household-chips").classList.toggle("hidden", !isHH);
  document.getElementById("topbar-device-chips").classList.toggle("hidden", isHH);
  document.getElementById("nav-scope-device").classList.toggle("hidden", CURRENT_SCOPE !== "device" || !DEVICE_SELECTED);
}

function setScope(scope, targetView=null) {
  CURRENT_SCOPE = scope === "household" ? "household" : "device";
  document.getElementById("tab-scope-household").classList.toggle("active", CURRENT_SCOPE === "household");
  document.getElementById("tab-scope-device").classList.toggle("active", CURRENT_SCOPE === "device");
  document.getElementById("nav-scope-household").classList.toggle("hidden", CURRENT_SCOPE !== "household");
  document.getElementById("device-picker-wrap").classList.toggle("hidden", CURRENT_SCOPE !== "device");
  updateTopHeaderForScope();

  if (CURRENT_SCOPE === "household") {
    switchView(targetView || "fleet_overview", null);
  } else if (!DEVICE_SELECTED) {
    switchView("select_device_prompt", null);
  } else {
    switchView(targetView || "dashboard", null);
  }
  if (STATE) {
    renderFleetOverview(STATE.fleet_devices, STATE.fleet_controls, STATE.config);
  }
}

function switchView(viewId, btnEl) {
  const neededScope = HOUSEHOLD_VIEWS.includes(viewId) ? "household" : "device";
  if (CURRENT_SCOPE !== neededScope) {
    setScope(neededScope, viewId);
    return;
  }
  if (CURRENT_SCOPE === "device" && !DEVICE_SELECTED && viewId !== "select_device_prompt") {
    viewId = "select_device_prompt";
  }
  document.querySelectorAll("aside .nav-btn").forEach(b => b.classList.remove("active"));
  if (btnEl) {
    btnEl.classList.add("active");
  } else {
    const matchBtn = document.querySelector(`aside .nav-btn[data-view="${viewId}"]`);
    if (matchBtn) matchBtn.classList.add("active");
  }
  ALL_VIEWS.forEach(id => {
    const el = document.getElementById("view-" + id);
    if (el) el.classList.toggle("hidden", id !== viewId);
  });
}

function navigateToView(viewId) {
  switchView(viewId, null);
  window.scrollTo({top: 0, behavior: "smooth"});
}

function selectCurrentDevice() {
  DEVICE_SELECTED = true;
  setScope("device", "dashboard");
}

function switchFleetDevice(companionUrl) {
  if (!companionUrl) {
    DEVICE_SELECTED = false;
    setScope("device", "select_device_prompt");
    return;
  }
  const curBase = window.location.pathname + "?token=" + (URL_PARAMS.get("token") || "");
  if (companionUrl === curBase || companionUrl === window.location.pathname + window.location.search) {
    selectCurrentDevice();
  } else {
    window.location.href = companionUrl;
  }
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
    const distText = (hasSignal && r.distance_m != null)
      ? ` &bull; Est. Distance: <strong style="color:var(--text-strong);">~${r.distance_m}m (${r.distance_ft}ft)</strong>`
      : "";
    const sigText = hasSignal
      ? `Raw: <strong>${r.raw_rssi} dBm</strong> &bull; Offset: <strong>${offSign} dB</strong> &rarr; Effective: <strong style="color:var(--accent);">${r.effective_rssi} dBm</strong>${distText}`
      : `Offset: <strong>${offSign} dB</strong> &bull; Waiting for beacon packet...`;
    const winBadge = r.is_winner
      ? `<span class="state-badge" style="border-color:var(--success);color:var(--success);margin-left:6px;">ACTIVE</span>`
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
          <button class="btn-secondary" style="padding:4px 10px;font-size:11.5px;margin-left:4px;border-color:var(--accent);color:var(--accent);" title="Auto-calculate dB offset so this room wins at your current spot" onclick="autoCalibrateHere('${r.area_id}')">Prioritize Here</button>
        </div>
      </div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:6px;">${sigText}</div>
      <div class="rssi-track"><div class="rssi-fill" style="width:${pct}%;opacity:${hasSignal ? 1 : 0.2};"></div></div>
    </div>`;
  }).join("");
}

function renderFleetOverview(fleetDevices, fleetControls, cfg) {
  const countBadge = document.getElementById("nav-fleet-count");
  if (countBadge) countBadge.textContent = String((fleetDevices || []).length);

  const groups = STATE?.device_groups || [];
  const profiles = STATE?.saved_profiles || [];
  const backups = STATE?.vault_backups || [];

  const profDevLbl = document.getElementById("prof-active-dev-label");
  if (profDevLbl) profDevLbl.textContent = STATE?.title || cfg?.device_slug || "Active Device";

  const picker = document.getElementById("fleet-device-picker");
  if (picker && fleetDevices) {
    const placeholder = `<option value="" ${!DEVICE_SELECTED ? 'selected' : ''}>— Select a Device —</option>`;
    picker.innerHTML = placeholder + fleetDevices.map(d =>
      `<option value="${d.companion_url}" ${(DEVICE_SELECTED && d.is_current) ? 'selected' : ''}>${d.title} (${d.active_area_name})</option>`
    ).join("");
  }

  // Populate Device Group selector on the Device Identity card
  const devGrpSel = document.getElementById("cfg-device_group");
  if (devGrpSel && groups.length) {
    const curGrp = cfg?.device_group || "handhelds";
    devGrpSel.innerHTML = groups.map(g =>
      `<option value="${g.id}" ${g.id === curGrp ? 'selected' : ''}>Group: ${g.name}</option>`
    ).join("");
  }

  // Populate Profile Target Scope & Live Group Control Filter dropdowns
  const targetScopes = [
    {id: "current", name: `Current Device (${STATE?.title || cfg?.device_slug || 'Active'})`},
    {id: "all", name: `All Onboarded Devices (${(fleetDevices || []).length})`}
  ];
  groups.forEach(g => {
    const cnt = (fleetDevices || []).filter(d => d.device_group === g.id).length;
    targetScopes.push({id: `group:${g.id}`, name: `Group: ${g.name} (${cnt})`});
  });
  (fleetDevices || []).forEach(d => {
    targetScopes.push({id: `device:${d.device_slug}`, name: `Device: ${d.title}`});
  });

  const profScopeSel = document.getElementById("profile-target-scope");
  if (profScopeSel) {
    const prevVal = profScopeSel.value || "current";
    profScopeSel.innerHTML = targetScopes.map(o =>
      `<option value="${o.id}" ${o.id === prevVal ? 'selected' : ''}>${o.name}</option>`
    ).join("");
  }

  const grpFilterSel = document.getElementById("group-ctrl-filter");
  let activeFilter = "all";
  if (grpFilterSel) {
    activeFilter = grpFilterSel.value || "all";
    const filterOpts = [
      {id: "all", name: `Target: All Devices (${(fleetDevices || []).length})`}
    ];
    groups.forEach(g => {
      const cnt = (fleetDevices || []).filter(d => d.device_group === g.id).length;
      filterOpts.push({id: `group:${g.id}`, name: `Target Group: ${g.name} (${cnt})`});
    });
    filterOpts.push({id: "arch:mobile_display", name: "Archetype: Mobile Displays"});
    filterOpts.push({id: "arch:stationary_display", name: "Archetype: Stationary Displays"});
    grpFilterSel.innerHTML = filterOpts.map(o =>
      `<option value="${o.id}" ${o.id === activeFilter ? 'selected' : ''}>${o.name}</option>`
    ).join("");
  }

  const rowsHtml = (fleetDevices || []).map(d => {
    const spk = (d.active_speaker || "").replace("media_player.", "");
    const spkMeta = (d.has_audio && spk) ? ` &bull; Speaker: <strong>${spk}</strong>` : "";
    const proxyMeta = d.ble_closest_proxy ? ` &bull; Proxy: ${d.ble_closest_proxy}` : "";
    const isActDev = DEVICE_SELECTED && d.is_current && CURRENT_SCOPE === "device";
    const actAction = d.is_current
      ? `selectCurrentDevice()`
      : `switchFleetDevice('${d.companion_url}')`;
    const grpOpts = groups.map(g =>
      `<option value="${g.id}" ${g.id === d.device_group ? 'selected' : ''}>${g.name}</option>`
    ).join("");
    return `<div class="native-ctrl-row">
      <div class="lbl">
        ${d.title}
        <span class="state-badge" style="margin-left:6px;">${d.device_group_name || d.device_group || 'Unassigned'}</span>
        ${isActDev ? '<span class="state-badge" style="margin-left:4px;border-color:var(--success);color:var(--success);">Active</span>' : ''}
        <small>Slug: <code>${d.device_slug}</code> &bull; Room: <strong>${d.active_area_name}</strong>${spkMeta}${proxyMeta}</small>
      </div>
      <div class="widget">
        <select style="min-width:140px;" title="Assign Device Group" onchange="assignDeviceGroup('${d.device_slug}', this.value)">${grpOpts}</select>
        <button class="btn-primary" onclick="${actAction}">Manage Device</button>
        <button class="btn-danger" title="Remove device from Latter" onclick="removeManagedDevice('${d.entry_id}', '${d.title.replace(/'/g, "")}')">✕</button>
      </div>
    </div>`;
  }).join("");

  const listBox = document.getElementById("fleet-devices-list");
  if (listBox) listBox.innerHTML = rowsHtml;
  const promptBox = document.getElementById("prompt-devices-list");
  if (promptBox) promptBox.innerHTML = rowsHtml;

  const unbridged = STATE?.unbridged_devices || [];
  const bridgeBar = document.getElementById("bridge-device-bar");
  const bridgePicker = document.getElementById("bridge-device-picker");
  if (bridgeBar && bridgePicker) {
    if (unbridged.length > 0) {
      bridgeBar.style.display = "flex";
      bridgePicker.innerHTML = unbridged.map(u =>
        `<option value="${u.slug}" data-area="${u.area_id || ''}">${u.name}</option>`
      ).join("");
    } else {
      bridgeBar.style.display = "none";
    }
  }

  // Render Reusable Profiles List
  const profBox = document.getElementById("saved-profiles-list");
  if (profBox) {
    if (!profiles.length) {
      profBox.innerHTML = `<p class="desc">No profiles saved yet.</p>`;
    } else {
      profBox.innerHTML = profiles.map(p => {
        const ctrlCnt = Object.keys(p.esphome_controls || {}).length;
        const isBuiltin = String(p.id || "").startsWith("preset_");
        return `<div class="native-ctrl-row">
          <div class="lbl">
            ${p.name} <span class="state-badge" style="margin-left:6px;">${ctrlCnt} controls</span>
            <small>${p.description || ''}</small>
          </div>
          <div class="widget">
            <button class="btn-primary" onclick="applySavedProfile('${p.id}')">Apply</button>
            ${!isBuiltin ? `<button class="btn-danger" onclick="deleteSavedProfile('${p.id}')">✕</button>` : ''}
          </div>
        </div>`;
      }).join("");
    }
  }

  // Render Device Groups List
  const grpBox = document.getElementById("device-groups-list");
  if (grpBox) {
    grpBox.innerHTML = groups.map(g => {
      const members = (fleetDevices || []).filter(d => d.device_group === g.id);
      const memNames = members.length ? members.map(m => m.title).join(", ") : "No devices assigned";
      const isDefault = ["unassigned", "handhelds", "bedrooms", "common_areas", "wall_panels", "sensors"].includes(g.id);
      return `<div class="native-ctrl-row">
        <div class="lbl">
          ${g.name} <span class="state-badge" style="margin-left:6px;">${members.length} device${members.length === 1 ? '' : 's'}</span>
          <small>${g.description || ''} &bull; Members: <strong>${memNames}</strong></small>
        </div>
        <div class="widget">
          ${!isDefault ? `<button class="btn-danger" onclick="deleteDeviceGroup('${g.id}')">✕</button>` : ''}
        </div>
      </div>`;
    }).join("");
  }

  // Render Filtered Live Group Controls
  const fBox = document.getElementById("fleet-controls-list");
  if (fBox) {
    if (!fleetControls || !fleetControls.length) {
      fBox.innerHTML = `<p class="desc">No shared ESPHome controls discovered.</p>`;
    } else {
      const filteredRows = fleetControls.map(fc => {
        const matchingTargets = (fc.targets || []).filter(t => {
          if (activeFilter === "all") return true;
          if (activeFilter.startsWith("group:")) return t.device_group === activeFilter.split(":")[1];
          if (activeFilter.startsWith("arch:")) return t.device_profile === activeFilter.split(":")[1];
          return true;
        });
        if (!matchingTargets.length) return "";
        const entIdsJson = JSON.stringify(matchingTargets.map(t => t.entity_id)).replace(/"/g, "&quot;");
        const devCount = matchingTargets.length;
        const curState = matchingTargets[0].state ?? fc.state;
        let widget = `<span class="state-badge">${curState}</span>`;
        if (fc.domain === "select" && fc.options && fc.options.length) {
          const opts = fc.options.map(o => `<option value="${o}" ${o===curState?'selected':''}>${o}</option>`).join("");
          widget = `<select onchange="fleetSelect(${entIdsJson}, this.value)">${opts}</select>`;
        } else if (fc.domain === "switch") {
          const isOn = curState === "on";
          widget = `<button class="${isOn ? 'btn-primary' : 'btn-secondary'}" onclick="fleetToggle(${entIdsJson}, '${isOn ? 'turn_off' : 'turn_on'}')">${isOn ? 'ON' : 'OFF'}</button>`;
        } else if (fc.domain === "number") {
          const minV = fc.min ?? 0;
          const maxV = fc.max ?? 100;
          const stepV = fc.step ?? 1;
          const numVal = parseFloat(curState) || 0;
          widget = `<input type="range" min="${minV}" max="${maxV}" step="${stepV}" value="${numVal}" onchange="fleetNumber(${entIdsJson}, this.value)"><span class="state-badge">${curState} ${fc.unit || ''}</span>`;
        }
        return `<div class="native-ctrl-row">
          <div class="lbl">
            ${fc.name}
            <small>${fc.section_title} &bull; Applies to ${devCount} matching device${devCount > 1 ? 's' : ''}</small>
          </div>
          <div class="widget">${widget}</div>
        </div>`;
      }).filter(Boolean).join("");
      fBox.innerHTML = filteredRows || `<p class="desc">No devices match the selected group filter.</p>`;
    }
  }

  // Render Internal Snapshot Vault List
  const vBox = document.getElementById("vault-backups-list");
  if (vBox) {
    if (!backups.length) {
      vBox.innerHTML = `<p class="desc">No snapshots saved in the internal vault yet. Click <strong>Save to Internal Vault</strong> above to create a restore point.</p>`;
    } else {
      vBox.innerHTML = backups.map(b => {
        const isSys = b.scope === "system";
        const scopeBadge = isSys
          ? `<span class="state-badge" style="border-color:var(--accent);color:var(--accent);">SYSTEM (${b.device_count} dev)</span>`
          : `<span class="state-badge">DEVICE: ${b.target_device}</span>`;
        const tsClean = (b.created_at || "").replace("T", " ").slice(0, 19);
        return `<div class="native-ctrl-row">
          <div class="lbl">
            ${b.name} ${scopeBadge}
            <small>Created: <strong>${tsClean}</strong> &bull; Saved ESPHome Controls: <strong>${b.control_count || 0}</strong> &bull; v${b.version || ''}</small>
          </div>
          <div class="widget">
            <button class="btn-primary" onclick="restoreVaultSnapshot('${b.id}', '${b.name.replace(/'/g, "")}')">Restore</button>
            <button class="btn-secondary" onclick="downloadVaultSnapshot('${b.id}')">Download .JSON</button>
            <button class="btn-danger" onclick="deleteVaultSnapshot('${b.id}')">✕</button>
          </div>
        </div>`;
      }).join("");
    }
  }

  document.getElementById("hh-sum-alarm").textContent = cfg.alarm_entity || "None";
  document.getElementById("hh-sum-camera").textContent = cfg.camera_entity || "None";
  document.getElementById("hh-sum-weather").textContent = cfg.weather_entity || "None";
  document.getElementById("hh-sum-ble").textContent = String(Object.keys(cfg.ble_room_offsets || {}).length);
}

async function fleetSelect(entityIds, option) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "fleet_entity_action", entity_ids: entityIds, option})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast(`Applied '${option}' across ${entityIds.length} device(s)`);
  }
}

async function fleetToggle(entityIds, action) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "fleet_entity_action", entity_ids: entityIds, action})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast(`Applied ${action} across ${entityIds.length} device(s)`);
  }
}

async function fleetNumber(entityIds, level) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "fleet_entity_action", entity_ids: entityIds, level})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast(`Applied ${level} across ${entityIds.length} device(s)`);
  }
}

async function setBleOffset(areaId, offsetDb) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "set_ble_room_offset", area_id: areaId, offset_db: offsetDb})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("Saved global BLE room offset");
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
    showToast("Calibrated & prioritized current room globally");
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
    showToast("Sent notification to device");
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
  document.getElementById("embedded-sleep").innerHTML = sleepItems.length
    ? sleepItems.map(it => renderNativeControlRow(it)).join("")
    : `<p class="desc">No on-device Sleep & Wake entities exposed.</p>`;

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
    `<button class="btn-action" title="${it.name}" onclick="espAction('${it.entity_id}', 'press')">${it.name}</button>`
  ).join("");

  const batItems = getSectionItems("battery");
  document.getElementById("embedded-battery").innerHTML = batItems.length
    ? batItems.map(it => renderNativeControlRow(it)).join("")
    : `<p class="desc">No battery telemetry entities reported.</p>`;

  const netItems = getSectionItems("network").concat(getSectionItems("other"));
  document.getElementById("embedded-network").innerHTML = netItems.length
    ? netItems.map(it => renderNativeControlRow(it)).join("")
    : `<p class="desc">No network or diagnostic entities reported.</p>`;

  // Populate the primary Device Controls & Live Sensors box on Device Overview
  const dashBox = document.getElementById("dash-device-entities");
  if (dashBox) {
    let primaryItems = getSectionItems("other")
      .concat(getSectionItems("room"))
      .concat(getSectionItems("home"))
      .concat(getSectionItems("display"))
      .concat(getSectionItems("battery"))
      .concat(getSectionItems("actions"));
    if (!primaryItems.length) {
      primaryItems = getSectionItems("network");
    }
    dashBox.innerHTML = primaryItems.length
      ? primaryItems.slice(0, 18).map(it => renderNativeControlRow(it, true)).join("")
      : `<p class="desc">No configurable controls or sensors reported by this device yet.</p>`;
  }

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
  if (!box) return;
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

function renderCalendarChips() {
  const box = document.getElementById("calendar-chips");
  if (!box) return;
  box.innerHTML = CALENDARS.map((ent, idx) =>
    `<div class="chip"><span>${ent}</span><b onclick="removeCalendarEntity(${idx})">✕</b></div>`
  ).join("");
}

function addCalendarEntity() {
  const val = document.getElementById("cal-entity-picker").value;
  if (val && !CALENDARS.includes(val)) {
    CALENDARS.push(val);
    renderCalendarChips();
    markDirty();
  }
}

function removeCalendarEntity(idx) {
  CALENDARS.splice(idx, 1);
  renderCalendarChips();
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
    <input type="text" class="b-slot" placeholder="Slot ID (e.g. macro_1)" value="${slot}" oninput="markDirty()">
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
    `# Latter v1.7+ ESPHome Companion Wire Snippet for '${nodeHyphen}' (slug: ${slug})`,
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
    lines.push(`#       slot: "macro_1"`);
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

function copyTextById(elId) {
  const text = document.getElementById(elId)?.textContent || "";
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    showToast("Copied snippet to clipboard");
  });
}

async function generateDeviceVpnKeys() {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "generate_vpn_keys"})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), true);
    showToast("Generated Curve25519 WireGuard keys for device");
  }
}

async function removeManagedDevice(entryId, title) {
  if (!confirm(`Remove '${title || entryId}' from Latter? (Your ESPHome device itself will remain in Home Assistant, and you can re-add or bridge it anytime.)`)) {
    return;
  }
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "remove_device", entry_id: entryId})
  });
  if (resp.ok) {
    const data = await resp.json();
    if (data.removed && data.redirect_url) {
      window.location.href = data.redirect_url;
      return;
    }
    applyStateToDom(data, false);
    showToast(`Removed '${title}' from Latter`);
  }
}

async function bridgeSelectedEsphomeDevice() {
  const picker = document.getElementById("bridge-device-picker");
  if (!picker || !picker.value) return;
  const slug = picker.value;
  const optEl = picker.options[picker.selectedIndex];
  const areaId = optEl ? (optEl.getAttribute("data-area") || "") : "";
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "bridge_esphome_device", device_slug: slug, area_id: areaId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast(`Bridged ESPHome device '${slug}' into Latter Studio`);
  }
}

async function assignDeviceGroup(deviceSlug, groupId) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "set_device_group", device_slug: deviceSlug, device_group: groupId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast(`Assigned ${deviceSlug} to group '${groupId}'`);
  }
}

async function createDeviceGroup() {
  const nameEl = document.getElementById("new-group-name");
  const descEl = document.getElementById("new-group-desc");
  const name = (nameEl?.value || "").trim();
  if (!name) {
    showToast("Enter a group name first");
    return;
  }
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "create_device_group", name, description: (descEl?.value || "").trim()})
  });
  if (resp.ok) {
    if (nameEl) nameEl.value = "";
    if (descEl) descEl.value = "";
    applyStateToDom(await resp.json(), false);
    showToast(`Created device group '${name}'`);
  }
}

async function deleteDeviceGroup(groupId) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "delete_device_group", group_id: groupId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("Removed device group");
  }
}

async function captureCurrentDeviceProfile() {
  const nameEl = document.getElementById("new-profile-name");
  const descEl = document.getElementById("new-profile-desc");
  const name = (nameEl?.value || "").trim() || `${STATE?.title || 'Device'} Profile`;
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "capture_profile", name, description: (descEl?.value || "").trim()})
  });
  if (resp.ok) {
    if (nameEl) nameEl.value = "";
    if (descEl) descEl.value = "";
    applyStateToDom(await resp.json(), false);
    showToast(`Saved reusable profile '${name}'`);
  }
}

async function applySavedProfile(profileId) {
  const scope = document.getElementById("profile-target-scope")?.value || "current";
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "apply_profile", profile_id: profileId, target_scope: scope})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), true);
    showToast(`Applied profile to ${scope}`);
  }
}

async function deleteSavedProfile(profileId) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "delete_profile", profile_id: profileId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("Deleted profile");
  }
}

async function createVaultSnapshot() {
  const scope = document.getElementById("bkp-scope-select")?.value || "system";
  const name = (document.getElementById("bkp-label-input")?.value || "").trim();
  const incVpn = document.getElementById("bkp-include-vpn")?.checked ?? true;
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "create_vault_backup", scope, name, include_vpn_secrets: incVpn})
  });
  if (resp.ok) {
    const lblEl = document.getElementById("bkp-label-input");
    if (lblEl) lblEl.value = "";
    applyStateToDom(await resp.json(), false);
    showToast(`Saved ${scope.toUpperCase()} snapshot to Internal Vault`);
  }
}

async function createDeviceQuickBackup() {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "create_vault_backup", scope: "device", name: "", include_vpn_secrets: true})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("Saved device snapshot to Internal Vault");
  }
}

function triggerJsonDownload(bundle) {
  const dateStr = new Date().toISOString().slice(0, 10);
  const slugPart = bundle.scope === "system" ? "system" : `device-${bundle.target_device || 'esphome'}`;
  const filename = `latter-${slugPart}-backup-${dateStr}.json`;
  const blob = new Blob([JSON.stringify(bundle, null, 2)], {type: "application/json"});
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, 200);
}

async function exportBackupToComputer(overrideScope) {
  const scope = overrideScope || document.getElementById("bkp-scope-select")?.value || "system";
  const incVpn = document.getElementById("bkp-include-vpn")?.checked ?? true;
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "export_backup_json", scope, include_vpn_secrets: incVpn})
  });
  if (resp.ok) {
    const data = await resp.json();
    if (data.bundle) {
      triggerJsonDownload(data.bundle);
      showToast(`Downloaded ${scope.toUpperCase()} backup .JSON`);
    }
  }
}

async function downloadVaultSnapshot(backupId) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "export_backup_json", backup_id: backupId})
  });
  if (resp.ok) {
    const data = await resp.json();
    if (data.bundle) {
      triggerJsonDownload(data.bundle);
      showToast("Downloaded snapshot .JSON");
    }
  }
}

async function restoreVaultSnapshot(backupId, label) {
  const restoreEsp = document.getElementById("bkp-restore-esp")?.checked ?? true;
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "restore_backup", backup_id: backupId, restore_esphome_entities: restoreEsp})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), true);
    showToast(`Restored snapshot '${label}'`);
  }
}

async function deleteVaultSnapshot(backupId) {
  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "delete_vault_backup", backup_id: backupId})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), false);
    showToast("Deleted snapshot from vault");
  }
}

function restoreFromUploadedFile() {
  const input = document.getElementById("bkp-upload-file");
  if (!input || !input.files || !input.files.length) {
    showToast("Choose a .JSON backup file first");
    return;
  }
  const restoreEsp = document.getElementById("bkp-restore-esp")?.checked ?? true;
  const file = input.files[0];
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const parsed = JSON.parse(reader.result);
      const bundle = parsed.bundle || parsed;
      const resp = await fetch(API_URL, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({command: "restore_backup", bundle, restore_esphome_entities: restoreEsp})
      });
      if (resp.ok) {
        input.value = "";
        applyStateToDom(await resp.json(), true);
        showToast(`Restored ${bundle.scope || 'backup'} from file`);
      } else {
        showToast("Restore failed: invalid backup file");
      }
    } catch (_e) {
      showToast("Invalid JSON backup file");
    }
  };
  reader.readAsText(file);
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
  const mediaSummary = live.media_title && live.media_title !== "Idle"
    ? `${live.media_title} (${live.media_artist})`
    : `${live.media_state || 'idle'}`;

  const caps = data.capabilities || {};
  const devTitle = esp?.device?.name || data.title;
  document.getElementById("hdr-sub").textContent = `v${data.version || '2.1.2'}`;
  document.getElementById("survey-device-name").textContent = devTitle;
  document.getElementById("nav-room-badge").textContent = roomName;
  document.getElementById("top-room").textContent = `Room: ${roomName}`;
  const topSpkChip = document.getElementById("top-speaker")?.parentElement;
  const topMedChip = document.getElementById("top-media")?.parentElement;
  if (topSpkChip) topSpkChip.style.display = (caps.has_audio && spkShort) ? "inline-flex" : "none";
  if (topMedChip) topMedChip.style.display = (caps.has_audio && spkShort) ? "inline-flex" : "none";
  document.getElementById("top-speaker").textContent = `Speaker: ${spkShort || 'None'}`;
  document.getElementById("top-media").textContent = `Media: ${mediaSummary}`;
  document.getElementById("top-hh-devices").textContent = `Devices: ${(data.fleet_devices || []).length}`;
  document.getElementById("top-hh-alarm").textContent = `Alarm: ${(live.alarm_state || 'none').toUpperCase()}`;
  updateTopHeaderForScope();

  // Capability-Aware Sidebar Tabs & Add-On Badges
  const showDisplay = !!caps.has_display;
  const showPower = !!caps.has_power;
  const showVoice = !!caps.has_voice;
  const showAudio = !!caps.has_audio;
  const anySettingsTab = showDisplay || showPower || showVoice || showAudio;
  document.getElementById("nav-grp-dev-settings")?.classList.toggle("hidden", !anySettingsTab);
  document.getElementById("nav-btn-home_display")?.classList.toggle("hidden", !showDisplay);
  document.getElementById("nav-btn-power")?.classList.toggle("hidden", !showPower);
  document.getElementById("nav-btn-voice")?.classList.toggle("hidden", !showVoice);
  document.getElementById("nav-btn-audio")?.classList.toggle("hidden", !showAudio);

  const bleBadge = document.getElementById("nav-ble-addon-badge");
  if (bleBadge) bleBadge.textContent = caps.has_ble_beacon ? "Active" : "Add-On";
  const vpnBadge = document.getElementById("nav-vpn-addon-badge");
  if (vpnBadge) vpnBadge.textContent = caps.has_vpn_mixin ? "Active" : "Add-On";

  const bleBanner = document.getElementById("ble-addon-missing-banner");
  if (bleBanner) bleBanner.style.display = caps.has_ble_beacon ? "none" : "block";
  const vpnBanner = document.getElementById("vpn-addon-missing-banner");
  if (vpnBanner) vpnBanner.style.display = caps.has_vpn_mixin ? "none" : "block";

  // Device-Centric Hero Stats on Device Overview
  document.getElementById("dash-header-title").textContent = `${devTitle} — Overview`;
  document.getElementById("st-tier").textContent = caps.tier_label || "ESPHome Device";
  document.getElementById("st-room").textContent = roomName;
  const grpList = data.device_groups || [];
  const grpObj = grpList.find(g => g.id === cfg.device_group);
  document.getElementById("st-group").textContent = grpObj ? grpObj.name : (cfg.device_group || "Unassigned");
  document.getElementById("st-entities").textContent = `${caps.total_entities || 0} Entities`;

  const hwModel = `${esp?.device?.model || 'ESPHome'}${esp?.device?.sw_version ? ' (' + esp.device.sw_version + ')' : ''}`;
  document.getElementById("dash-hw-model").textContent = hwModel;
  document.getElementById("dash-ble-mode").textContent = (caps.has_ble_beacon && cfg.native_ble_tracking)
    ? (cfg.ble_auto_switch ? "Enabled (Auto-Switch)" : "Enabled (Manual Switch)")
    : "Not Active (See BLE Add-On)";
  const winRow = (live.ble_survey_rows || []).find(r => r.is_winner);
  const distSuffix = (winRow && winRow.distance_m != null) ? ` (~${winRow.distance_m}m / ${winRow.distance_ft}ft)` : "";
  document.getElementById("dash-ble-proxy").textContent = (live.ble_closest_proxy || "None") + distSuffix;
  const proxyRow = document.getElementById("dash-row-ble-proxy");
  if (proxyRow) proxyRow.style.display = caps.has_ble_beacon ? "flex" : "none";
  const spkField = document.getElementById("dash-speaker-field");
  if (spkField) spkField.style.display = caps.has_audio ? "block" : "none";
  const medRow = document.getElementById("dash-row-media");
  if (medRow) medRow.style.display = caps.has_audio ? "flex" : "none";
  document.getElementById("dash-media-summary").textContent = mediaSummary;

  [1, 2, 3, 4].forEach(idx => {
    const isAct = actSlotIdx === idx;
    const card = document.getElementById(`rslot-card-${idx}`);
    const btn = document.getElementById(`rslot-btn-${idx}`);
    if (card) card.classList.toggle("active-slot", isAct);
    if (btn) {
      btn.textContent = isAct ? "Active on Device" : "Set Active";
      btn.className = isAct ? "btn-primary" : "btn-secondary";
    }
  });

  populateSelect("quick-area", cat.areas, live.active_area_id, true);
  populateSelect("quick-speaker", cat.ma_speakers, live.active_speaker, true);
  renderRssiBars(live.ble_survey_rows, live.ble_packets_seen);
  renderWallpaperGallery(data.wallpapers, cfg.device_slug, cfg.display_shape);
  if (data.vpn_snippets) {
    const wy = document.getElementById("vpn-esphome-yaml");
    const sp = document.getElementById("vpn-server-peer");
    if (wy) wy.textContent = data.vpn_snippets.esphome_yaml || "";
    if (sp) sp.textContent = [data.vpn_snippets.server_peer_conf || "", data.vpn_snippets.ha_addon_yaml || ""].join("\\n\\n");
  }

  const activeEl = document.activeElement;
  if (!activeEl || !["SELECT", "INPUT"].includes(activeEl.tagName)) {
    renderCohesiveDeviceSections();
    renderFleetOverview(data.fleet_devices, data.fleet_controls, cfg);
  }

  if (!INITIAL_FORM_LOADED || forceFormUpdate) {
    INITIAL_FORM_LOADED = true;
    populateThemeDropdowns(data.ha_themes, cfg.web_theme || "ha_auto");
    applyTheme(cfg.web_theme || "ha_auto");
    renderCohesiveDeviceSections();
    renderFleetOverview(data.fleet_devices, data.fleet_controls, cfg);

    document.getElementById("cfg-device_slug").value = cfg.device_slug || "";
    document.getElementById("cfg-companion_base_url").value = cfg.companion_base_url || "";
    document.getElementById("cfg-vpn_endpoint").value = cfg.vpn_endpoint || "";
    document.getElementById("cfg-vpn_server_public_key").value = cfg.vpn_server_public_key || "";
    document.getElementById("cfg-vpn_subnet").value = cfg.vpn_subnet || "10.10.10.0/24";
    document.getElementById("cfg-vpn_ha_ip").value = cfg.vpn_ha_ip || "10.10.10.1";
    document.getElementById("cfg-vpn_enabled").checked = !!cfg.vpn_enabled;
    document.getElementById("cfg-vpn_client_ip").value = cfg.vpn_client_ip || "";
    document.getElementById("cfg-vpn_hotspot_ssid").value = cfg.vpn_hotspot_ssid || "";
    document.getElementById("cfg-vpn_public_key").value = cfg.vpn_public_key || "";
    document.getElementById("cfg-vpn_private_key").value = cfg.vpn_private_key || "";
    document.getElementById("cfg-vpn_preshared_key").value = cfg.vpn_preshared_key || "";
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
    populateSelect("cal-entity-picker", cat.calendars, "", false);
    populateSelect("pin-entity-picker", cat.bindable_entities, "", false);

    CALENDARS = Array.isArray(cfg.calendar_entities) ? [...cfg.calendar_entities] : [];
    renderCalendarChips();
    PINNED = Array.isArray(cfg.custom_entities) ? [...cfg.custom_entities] : [];
    renderPinnedChips();

    const bList = document.getElementById("bindings-list");
    bList.innerHTML = "";
    (cfg.custom_bindings || []).forEach(b => addBindingRow(b.slot, b.entity_id, b.action));
    renderYamlGenerator();
    clearDirty();
  }
  renderCustomColorPalettes();
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
    vpn_endpoint: document.getElementById("cfg-vpn_endpoint").value.trim(),
    vpn_server_public_key: document.getElementById("cfg-vpn_server_public_key").value.trim(),
    vpn_subnet: document.getElementById("cfg-vpn_subnet").value.trim(),
    vpn_ha_ip: document.getElementById("cfg-vpn_ha_ip").value.trim(),
    vpn_enabled: document.getElementById("cfg-vpn_enabled").checked,
    vpn_client_ip: document.getElementById("cfg-vpn_client_ip").value.trim(),
    vpn_hotspot_ssid: document.getElementById("cfg-vpn_hotspot_ssid").value.trim(),
    vpn_public_key: document.getElementById("cfg-vpn_public_key").value.trim(),
    vpn_private_key: document.getElementById("cfg-vpn_private_key").value.trim(),
    vpn_preshared_key: document.getElementById("cfg-vpn_preshared_key").value.trim(),
    device_profile: document.getElementById("cfg-device_profile").value,
    device_group: document.getElementById("cfg-device_group")?.value || "handhelds",
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
    art_size: document.getElementById("cfg-art_size").value.includes("x") ? document.getElementById("cfg-art_size").value : (parseInt(document.getElementById("cfg-art_size").value, 10) || 466),
    calendar_entities: CALENDARS,
    custom_entities: PINNED,
    custom_bindings: bindings,
    custom_palettes: Array.isArray((STATE?.config || {}).custom_palettes) ? STATE.config.custom_palettes : [],
    device_custom_color: (STATE?.config || {}).device_custom_color || "#3898FF",
  };

  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({command: "save_config", config})
  });
  if (resp.ok) {
    applyStateToDom(await resp.json(), true);
    showToast("Saved device & household configuration");
  }
}

let cwTargetScope = "device";
let cwSelectedHex = "#3898FF";

function ensureColorWheelModal() {
  if (document.getElementById("latter-cw-modal")) return;
  const modal = document.createElement("div");
  modal.id = "latter-cw-modal";
  modal.style.cssText = "position:fixed;inset:0;background:rgba(8,12,18,0.82);backdrop-filter:blur(6px);z-index:9999;display:none;align-items:center;justify-content:center;padding:16px;";
  modal.innerHTML = `
    <div class="card" style="max-width:380px;width:100%;margin:0;text-align:center;position:relative;">
      <h3 style="margin-bottom:4px;">HSV Color Wheel Picker</h3>
      <p class="desc" style="margin-bottom:12px;">Click or drag on the wheel to choose a specific color. Saving adds it to your System-Wide Household Color Library.</p>
      <div style="display:flex;justify-content:center;margin-bottom:14px;">
        <canvas id="latter-cw-canvas" width="220" height="220" style="border-radius:50%;cursor:crosshair;box-shadow:0 4px 20px rgba(0,0,0,0.45);"></canvas>
      </div>
      <div style="display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:12px;">
        <span id="latter-cw-preview" style="width:32px;height:32px;border-radius:50%;border:2px solid #fff;background:#3898FF;"></span>
        <input type="text" id="latter-cw-hex" value="#3898FF" style="width:110px;font-family:monospace;text-align:center;" oninput="onCwHexInput(this.value)">
      </div>
      <div class="field" style="text-align:left;margin-bottom:14px;">
        <label>Color Profile Name (System-Wide Library)</label>
        <input type="text" id="latter-cw-name" placeholder="e.g. Sunset Coral, Cyber Violet">
      </div>
      <div style="display:flex;gap:8px;justify-content:flex-end;">
        <button type="button" class="btn-secondary" onclick="closeColorWheelModal()">Cancel</button>
        <button type="button" class="btn-primary" onclick="saveColorWheelSelection()">Save to Household Library</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  const canvas = document.getElementById("latter-cw-canvas");
  const ctx = canvas.getContext("2d");
  const cx = 110, cy = 110, r = 108;
  const img = ctx.createImageData(220, 220);
  for (let y = 0; y < 220; y++) {
    for (let x = 0; x < 220; x++) {
      const dx = x - cx, dy = y - cy;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const idx = (y * 220 + x) * 4;
      if (dist <= r) {
        let hue = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
        let sat = Math.min(1, dist / r);
        const [cr, cg, cb] = hsvToRgbJS(hue, sat, 1.0);
        img.data[idx] = cr; img.data[idx + 1] = cg; img.data[idx + 2] = cb; img.data[idx + 3] = 255;
      } else {
        img.data[idx + 3] = 0;
      }
    }
  }
  ctx.putImageData(img, 0, 0);

  let dragging = false;
  const pickAt = (ev) => {
    const rect = canvas.getBoundingClientRect();
    const x = (ev.touches ? ev.touches[0].clientX : ev.clientX) - rect.left;
    const y = (ev.touches ? ev.touches[0].clientY : ev.clientY) - rect.top;
    const dx = x - cx, dy = y - cy;
    const dist = Math.min(r, Math.sqrt(dx * dx + dy * dy));
    const hue = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
    const sat = dist / r;
    const [cr, cg, cb] = hsvToRgbJS(hue, sat, 1.0);
    const hex = "#" + [cr, cg, cb].map(v => v.toString(16).padStart(2, "0")).join("").toUpperCase();
    setCwHex(hex);
  };
  canvas.addEventListener("mousedown", (e) => { dragging = true; pickAt(e); });
  window.addEventListener("mousemove", (e) => { if (dragging) pickAt(e); });
  window.addEventListener("mouseup", () => { dragging = false; });
  canvas.addEventListener("touchstart", (e) => { dragging = true; pickAt(e); e.preventDefault(); }, {passive: false});
  canvas.addEventListener("touchmove", (e) => { if (dragging) pickAt(e); e.preventDefault(); }, {passive: false});
  canvas.addEventListener("touchend", () => { dragging = false; });
}

function hsvToRgbJS(h, s, v) {
  let c = v * s;
  let x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  let m = v - c;
  let r = 0, g = 0, b = 0;
  if (h < 60) { r = c; g = x; }
  else if (h < 120) { r = x; g = c; }
  else if (h < 180) { g = c; b = x; }
  else if (h < 240) { g = x; b = c; }
  else if (h < 300) { r = x; b = c; }
  else { r = c; b = x; }
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
}

function setCwHex(hex) {
  cwSelectedHex = hex.toUpperCase();
  const prev = document.getElementById("latter-cw-preview");
  const inp = document.getElementById("latter-cw-hex");
  if (prev) prev.style.background = cwSelectedHex;
  if (inp && document.activeElement !== inp) inp.value = cwSelectedHex;
}

function onCwHexInput(val) {
  let v = val.trim().toUpperCase();
  if (!v.startsWith("#")) v = "#" + v;
  if (/^#[0-9A-F]{6}$/.test(v)) {
    cwSelectedHex = v;
    const prev = document.getElementById("latter-cw-preview");
    if (prev) prev.style.background = v;
  }
}

function openColorWheelModal(scope) {
  ensureColorWheelModal();
  cwTargetScope = scope || "device";
  const curHex = ((STATE && STATE.config && STATE.config.device_custom_color) || "#3898FF").toUpperCase();
  setCwHex(curHex);
  const nameInp = document.getElementById("latter-cw-name");
  if (nameInp) nameInp.value = "";
  document.getElementById("latter-cw-modal").style.display = "flex";
}

function closeColorWheelModal() {
  const m = document.getElementById("latter-cw-modal");
  if (m) m.style.display = "none";
}

async function saveColorWheelSelection() {
  const nameInp = document.getElementById("latter-cw-name");
  const name = (nameInp && nameInp.value.trim()) ? nameInp.value.trim() : `Custom (${cwSelectedHex})`;
  STATE.config = STATE.config || {};
  let pals = Array.isArray(STATE.config.custom_palettes) ? [...STATE.config.custom_palettes] : [];
  const existing = pals.find(p => (p.hex || "").toUpperCase() === cwSelectedHex);
  if (existing) {
    existing.name = name;
  } else {
    pals.unshift({name, hex: cwSelectedHex});
  }
  STATE.config.custom_palettes = pals;
  STATE.config.device_custom_color = cwSelectedHex;
  closeColorWheelModal();
  await applyDeviceCustomColor(cwSelectedHex, true);
}

async function applyDeviceCustomColor(hexColor, alsoSwitchSelect) {
  STATE.config = STATE.config || {};
  STATE.config.device_custom_color = hexColor.toUpperCase();
  await saveAllConfig();
  if (alsoSwitchSelect) {
    const secs = ((STATE.esphome || {}).sections || []);
    for (const s of secs) {
      for (const it of (s.items || [])) {
        if (it.domain === "select" && (it.name || "").toLowerCase().includes("color profile") && (it.options || []).includes("Custom")) {
          await espSelect(it.entity_id, "Custom");
        }
      }
    }
  }
}

async function onSelectDeviceCustomPalette(val) {
  if (val === "__new__") {
    openColorWheelModal("device");
    renderCustomColorPalettes();
    return;
  }
  if (val && val.startsWith("#")) {
    await applyDeviceCustomColor(val, true);
  }
}

async function deleteCustomPalette(hexColor) {
  STATE.config = STATE.config || {};
  let pals = Array.isArray(STATE.config.custom_palettes) ? STATE.config.custom_palettes : [];
  STATE.config.custom_palettes = pals.filter(p => (p.hex || "").toUpperCase() !== hexColor.toUpperCase());
  await saveAllConfig();
}

function renderCustomColorPalettes() {
  if (!STATE || !STATE.config) return;
  const pals = Array.isArray(STATE.config.custom_palettes) ? STATE.config.custom_palettes : [];
  const curHex = (STATE.config.device_custom_color || "#3898FF").toUpperCase();

  // Dynamically inject the System-Wide Custom Color Library card into Studio Settings if not yet present
  const studioSec = document.getElementById("view-studio_settings");
  if (studioSec && !document.getElementById("sys-custom-palettes-card")) {
    const card = document.createElement("div");
    card.id = "sys-custom-palettes-card";
    card.className = "card";
    card.style.marginTop = "16px";
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:8px;">
        <div>
          <h3 style="margin-bottom:4px;">Household Custom Color Profiles (System-Wide Library)</h3>
          <p class="desc" style="margin-bottom:0;">Create custom UI color profiles on the HSV Color Wheel once at the system level and reuse them across any device in your home.</p>
        </div>
        <button type="button" class="btn-primary" onclick="openColorWheelModal('system')">+ Open Color Wheel...</button>
      </div>
      <div id="sys-custom-palettes-list" style="display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;"></div>
    `;
    studioSec.appendChild(card);
  }

  const sw = document.getElementById("dev-color-swatch");
  if (sw) sw.style.background = curHex;

  const sel = document.getElementById("dev-custom-palette-select");
  if (sel) {
    let optsHtml = "";
    if (pals.length === 0) {
      optsHtml += `<option value="${curHex}">Active Custom (${curHex})</option>`;
    } else {
      for (const p of pals) {
        const h = (p.hex || "").toUpperCase();
        const selAttr = (h === curHex) ? "selected" : "";
        optsHtml += `<option value="${h}" ${selAttr}>${p.name || h} (${h})</option>`;
      }
    }
    optsHtml += `<option value="__new__">+ Create New Color (Wheel)...</option>`;
    sel.innerHTML = optsHtml;
  }

  const sysBox = document.getElementById("sys-custom-palettes-list");
  if (sysBox) {
    if (pals.length === 0) {
      sysBox.innerHTML = `<p class="desc" style="margin:0;">No custom household colors saved yet. Click "+ Open Color Wheel..." to create one.</p>`;
    } else {
      sysBox.innerHTML = pals.map(p => {
        const h = (p.hex || "").toUpperCase();
        return `
          <div style="display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;background:var(--input-bg);border:1px solid var(--border);">
            <span style="width:16px;height:16px;border-radius:50%;background:${h};border:1px solid #fff;"></span>
            <strong style="font-size:13px;">${p.name || h}</strong>
            <code style="font-size:11px;opacity:0.75;">${h}</code>
            <button type="button" class="btn-secondary" style="padding:2px 8px;font-size:11px;" onclick="applyDeviceCustomColor('${h}', true)">Apply</button>
            <button type="button" class="btn-secondary" style="padding:2px 6px;font-size:11px;color:var(--danger);" onclick="deleteCustomPalette('${h}')">&times;</button>
          </div>
        `;
      }).join("");
    }
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


class LatterStudioRootView(HomeAssistantView):
    """Master entry point (`/api/latter/studio?scope=household`) used by the Home Assistant Sidebar Panel."""

    requires_auth = False
    url = API_STUDIO_ROOT_PATH
    name = "api:latter:studio_root"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the master Studio redirector view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Redirect to the Household Studio view using the first active coordinator."""
        coords = _get_all_coordinators(self.hass)
        if not coords:
            return web.Response(
                status=HTTPStatus.NOT_FOUND,
                text="No Latter devices configured yet. Add an ESPHome device under Settings -> Devices & Services -> Latter.",
            )
        primary = coords[0]
        scope = request.query.get("scope") or "system"
        token = primary.get_signed_token()
        target_url = f"/api/latter/companion/{primary.entry.entry_id}?token={token}&scope={scope}"
        raise web.HTTPFound(location=target_url)


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
