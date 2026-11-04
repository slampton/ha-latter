"""State payload builder and brand icon views for Latter Studio."""

from __future__ import annotations

from datetime import datetime
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
from homeassistant.util import dt as dt_util

from ..area_engine import (
    find_esphome_device_id,
    get_area_entities,
    get_esphome_device_entities,
)
from ..backup_engine import get_device_groups_and_profiles
from ..ble_engine import (
    _iter_devices,
    get_all_areas_presence_summary,
    get_discovered_ble_candidates,
)
from ..browse_engine import is_music_assistant_player
from ..const import (
    API_BRAND_ICON_PATH,
    API_SIDEBAR_ICON_JS_PATH,
    CONF_ALARM_ENTITY,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_FUSION_CONFIG,
    CONF_AREA_HANDOFF,
    CONF_ART_SIZE,
    CONF_ASSIGNED_PERSON,
    CONF_ASSIGNED_ROLE,
    CONF_BLE_AREA_OFFSETS,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_CALENDAR_ENTITIES,
    CONF_CAMERA_ENTITIES,
    CONF_CAMERA_ENTITY,
    CONF_COMPANION_BASE_URL,
    CONF_CUSTOM_PALETTES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_PROFILE,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DISPLAY_SHAPE,
    CONF_DOCK_APPS,
    CONF_DOORBELL_ANC_MODE,
    CONF_GARAGE_ENTITY,
    CONF_LOCK_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PRESENCE_ENTITY,
    CONF_REMOTE_GROUPS,
    CONF_REMOTES_LIST,
    CONF_SITE_ID,
    CONF_SYNC_DEVICE_AREA,
    CONF_THERMOSTAT_ENTITY,
    CONF_VACUUM_ENTITY,
    CONF_VOLUME_OVERRIDES,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DEFAULT_DOORBELL_ANC_MODE,
    DOMAIN,
    INTEGRATION_VERSION,
    normalize_device_slug,
)
from ..coordinator import LatterCoordinator
from ..identity import esphome_service
from ..repairs import async_audit_coordinator_health
from ..system import get_latter_system
from ..wallpaper_engine import list_wallpaper_catalog

MAX_INTERNAL_LOGS = 150


def log_studio_event(
    hass: HomeAssistant, level: str, source: str, message: str
) -> None:
    """Append a timestamped diagnostic event to Latter's in-memory Studio ring buffer."""
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
    combined: list[dict[str, str]] = list(
        hass.data.get(DOMAIN, {}).get("internal_logs", [])
    )

    try:
        sys_log = hass.data.get("system_log")
        records = getattr(sys_log, "records", None)
        if records is not None:
            raw_list = (
                list(records.values())
                if hasattr(records, "values")
                else list(records)
            )
            for rec in reversed(raw_list[-200:]):
                d = rec.to_dict() if hasattr(rec, "to_dict") else {}
                logger_name = str(d.get("name") or "")
                msgs = d.get("message")
                msg_str = str(
                    msgs[0]
                    if isinstance(msgs, list) and msgs
                    else (msgs or "")
                )
                exc_str = str(d.get("exception") or "").strip()
                haystack = f"{logger_name} {msg_str} {exc_str}".lower()
                if not any(
                    k in haystack
                    for k in (
                        "latter",
                        "esphome",
                        "aioesphomeapi",
                        "sendspin",
                        "music_assistant",
                        "assist_satellite",
                    )
                ):
                    continue
                ts_val = d.get("timestamp")
                ts_str = (
                    datetime.fromtimestamp(float(ts_val)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
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


def _get_all_coordinators(hass: HomeAssistant) -> list[LatterCoordinator]:
    """Return all active LatterCoordinator instances sorted by device_slug."""
    sys_obj = get_latter_system(hass)
    if sys_obj is not None and sys_obj.coordinators:
        return sorted(
            sys_obj.coordinators.values(), key=lambda c: c.device_slug
        )
    domain_data = hass.data.get(DOMAIN, {})
    coords = [
        v for v in domain_data.values() if isinstance(v, LatterCoordinator)
    ]
    return sorted(coords, key=lambda c: c.device_slug)


def resolve_target_coordinator(
    hass: HomeAssistant,
    subentry_id: str | None = None,
    device_slug: str | None = None,
) -> LatterCoordinator | None:
    """Resolve a target LatterCoordinator by subentry_id or device_slug."""
    all_coords = _get_all_coordinators(hass)
    if not all_coords:
        return None
    if subentry_id:
        target = str(subentry_id).strip()
        for c in all_coords:
            if c.subentry_id == target or c.entry.entry_id == target:
                return c
            if c.device_slug == normalize_device_slug(target):
                return c
    if device_slug:
        norm = normalize_device_slug(str(device_slug))
        for c in all_coords:
            if c.device_slug == norm:
                return c
    return all_coords[0]


async def async_save_and_broadcast_global_config(
    hass: HomeAssistant, updates: dict[str, Any]
) -> None:
    """Persist updates to `.storage/latter.site` and broadcast to all loaded device coordinators."""
    if not updates:
        return
    domain_data = hass.data.setdefault(DOMAIN, {})
    global_cfg: dict[str, Any] = domain_data.setdefault(DATA_GLOBAL_CONFIG, {})
    changed_keys = {k for k, v in updates.items() if global_cfg.get(k) != v}
    global_cfg.update(updates)
    store = domain_data.get(DATA_GLOBAL_STORE)
    if store is not None:
        await store.async_save(global_cfg)
    for coord in _get_all_coordinators(hass):
        await coord.async_on_global_config_updated(changed_keys or set(updates.keys()))


def _build_system_shared_controls(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Discover shared ESPHome select/switch/number controls across all onboarded devices for 1-click System Sync."""
    coords = _get_all_coordinators(hass)
    by_label: dict[str, dict[str, Any]] = {}
    for coord in coords:
        esp_info = get_esphome_device_entities(
            hass,
            coord.device_slug,
            esphome_device_id=coord.esphome_device_id,
        )
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


def build_studio_state_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
) -> dict[str, Any]:
    """Build the JSON payload consumed by the Latter Studio custom panel."""
    if coordinator is None:
        all_c = _get_all_coordinators(hass)
        if not all_c:
            return {
                "entry_id": "",
                "title": "Latter System",
                "version": INTEGRATION_VERSION,
                "system_devices": [],
                "system_controls": [],
                "device_groups": [],
                "saved_profiles": [],
                "config": {},
                "live": {},
                "catalog": {"areas": []},
            }
        coordinator = all_c[0]

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

    local_spk_id = coordinator.local_speaker
    local_ma_id = coordinator.local_ma_speaker

    for state_obj in sorted(
        hass.states.async_all(), key=lambda s: s.entity_id
    ):
        ent_id = state_obj.entity_id
        domain = state_obj.domain
        friendly = str(state_obj.attributes.get("friendly_name") or ent_id)
        suffix_state = (
            " [Off/Unavailable]" if state_obj.state == "unavailable" else ""
        )
        item = {
            "id": ent_id,
            "name": f"{friendly} ({ent_id}){suffix_state}",
            "domain": domain,
        }

        if domain == "media_player":
            remotes_list.append(item)
            volume_targets.append(item)
            if (
                local_spk_id
                and local_ma_id
                and ent_id == local_ma_id
                and local_ma_id != local_spk_id
            ):
                # Avoid listing two speaker entities for the same physical device;
                # local_speaker represents the built-in speaker and links to local_ma_speaker automatically.
                continue
            if (
                ent_id == local_spk_id
                or is_music_assistant_player(hass, state_obj)
            ):
                if ent_id == local_spk_id:
                    clean_lbl = (
                        friendly[:-6].strip()
                        if friendly.lower().endswith(" music") and len(friendly) > 6
                        else friendly
                    )
                    ma_speakers.append(
                        {
                            "id": ent_id,
                            "name": f"{clean_lbl} — Built-in Speaker ({ent_id}){suffix_state}",
                            "domain": domain,
                        }
                    )
                else:
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
                cam_sig = coordinator.sign_resource(
                    f"camera:{ent_id}|320|180|square"
                )
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
            p_slug = re.sub(
                r"[^a-z0-9]+", "_", ent_id.split(".", 1)[-1].lower()
            ).strip("_")
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
        hass,
        coordinator.device_slug,
        esphome_device_id=coordinator.esphome_device_id,
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

    slug = coordinator.device_slug
    has_native_slots = bool(
        esphome_service(
            hass,
            coordinator.esphome_device_id,
            "set_browse_slots",
            fallback_slug=slug,
        )
        or esphome_service(
            hass,
            coordinator.esphome_device_id,
            "set_area_slots",
            fallback_slug=slug,
        )
        or coordinator.hardware_manifest
    )
    has_mixin_ping = bool(
        esphome_service(
            hass, coordinator.esphome_device_id, "latter_ping", fallback_slug=slug
        )
    )

    sec_ids = {
        s.get("id")
        for s in esphome_inspector.get("sections", [])
        if s.get("count", 0) > 0
    }
    all_esp_items: list[dict[str, Any]] = []
    for s in esphome_inspector.get("sections", []):
        all_esp_items.extend(s.get("items") or [])

    has_ble_beacon_entity = any(
        "ble" in str(it.get("entity_id") or "").lower()
        and "beacon" in str(it.get("entity_id") or "").lower()
        for it in all_esp_items
    )
    local_spk = coordinator.local_speaker
    has_display = has_native_slots or ("display" in sec_ids) or ("home" in sec_ids)
    has_power = ("sleep" in sec_ids) or ("battery" in sec_ids)
    has_voice = "voice" in sec_ids
    has_audio = (
        has_native_slots
        or bool(local_spk)
        or ("sound" in sec_ids)
        or ("music" in sec_ids)
    )

    if has_native_slots:
        dev_tier = 1
        dev_tier_label = "Tier 1: Native Latter"
    elif has_mixin_ping or has_ble_beacon_entity:
        dev_tier = 2
        dev_tier_label = "Tier 2: Mixin Enabled"
    else:
        dev_tier = 3
        dev_tier_label = "Tier 3: Bridged Device"

    hw_manifest = coordinator.hardware_manifest
    if "imu" in hw_manifest:
        has_imu = bool(hw_manifest.get("imu"))
    else:
        has_imu = any(
            "imu" in str(it.get("entity_id") or "").lower()
            for it in all_esp_items
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
        "is_roaming_device": coordinator.is_roaming_device,
        "total_entities": len(all_esp_items),
    }

    raw_def_spk = str(coordinator.get_opt(CONF_DEFAULT_SPEAKER, "") or "").strip()
    if (
        raw_def_spk
        and local_spk_id
        and local_ma_id
        and raw_def_spk == local_ma_id
    ):
        raw_def_spk = local_spk_id

    config_data = {
        CONF_DEVICE_SLUG: coordinator.device_slug,
        CONF_DEVICE_PROFILE: coordinator.device_profile,
        CONF_DEVICE_GROUP: coordinator.device_group,
        CONF_DISPLAY_SHAPE: coordinator.display_shape,
        CONF_DEFAULT_PAGE_SIZE: coordinator.default_page_size,
        CONF_COMPANION_BASE_URL: coordinator.companion_base_url,
        CONF_DEFAULT_SPEAKER: raw_def_spk,
        CONF_VOLUME_OVERRIDES: [
            {"speaker": k, "target": v}
            for k, v in coordinator.volume_overrides.items()
        ],
        CONF_DEFAULT_AREA: coordinator.get_opt(CONF_DEFAULT_AREA, ""),
        CONF_NATIVE_BLE_TRACKING: coordinator.native_ble_tracking_enabled,
        CONF_BLE_BEACON_UUID: coordinator.ble_beacon_uuid,
        CONF_BLE_TARGET_ADDRESS: coordinator.ble_target_address,
        CONF_BLE_AREA_OFFSETS: coordinator.ble_area_offsets,
        CONF_AREA_FUSION_CONFIG: coordinator.get_opt(CONF_AREA_FUSION_CONFIG, {})
        or {},
        CONF_PRESENCE_ENTITY: coordinator.presence_entity or "",
        CONF_ASSIGNED_PERSON: coordinator.assigned_person,
        CONF_ASSIGNED_ROLE: coordinator.assigned_role,
        CONF_BLE_AUTO_SWITCH: coordinator.ble_auto_switch_enabled,
        CONF_SYNC_DEVICE_AREA: coordinator.sync_device_area_enabled,
        CONF_AREA_FOLLOW_DWELL_S: coordinator.area_follow_dwell_s,
        CONF_AREA_HANDOFF: coordinator.area_handoff_enabled,
        CONF_ALARM_ENTITY: str(
            coordinator.get_opt(CONF_ALARM_ENTITY, "") or ""
        ),
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
            coordinator.get_opt(
                CONF_DOORBELL_ANC_MODE, coordinator.doorbell_anc_mode
            )
            or DEFAULT_DOORBELL_ANC_MODE
        ),
        CONF_DOCK_APPS: coordinator.dock_apps_csv,
        CONF_WALLPAPER_SOURCE: coordinator.wallpaper_source,
        CONF_WALLPAPER_FAVORITES: coordinator.wallpaper_favorites,
        CONF_WALLPAPER_CYCLE_MINUTES: coordinator.wallpaper_cycle_minutes,
        CONF_ART_SIZE: coordinator.art_size,
        CONF_SITE_ID: coordinator.site_id,
    }

    try:
        health_warnings = async_audit_coordinator_health(hass, coordinator)
    except Exception:  # noqa: BLE001
        health_warnings = []

    ble_survey_rows: list[dict[str, Any]] = []
    if coordinator._ble_tracker is not None and hasattr(
        coordinator._ble_tracker, "get_area_calibration_telemetry"
    ):
        ble_survey_rows = (
            coordinator._ble_tracker.get_area_calibration_telemetry()
        )

    device_groups, saved_profiles = get_device_groups_and_profiles(hass)
    group_name_map = {
        g["id"]: g["name"]
        for g in device_groups
        if isinstance(g, dict) and g.get("id")
    }

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    system_devices: list[dict[str, Any]] = []
    for c in _get_all_coordinators(hass):
        c_area_name, c_area_attrs = c.get_area_context_payload()
        c_media_state, _ = c.get_active_media_payload()
        c_grp = c.device_group
        c_manifest = c.hardware_manifest
        c_has_native_svc = bool(
            esphome_service(
                hass,
                c.esphome_device_id,
                "set_browse_slots",
                fallback_slug=c.device_slug,
            )
            or esphome_service(
                hass,
                c.esphome_device_id,
                "set_area_slots",
                fallback_slug=c.device_slug,
            )
            or esphome_service(
                hass,
                c.esphome_device_id,
                "show_notification",
                fallback_slug=c.device_slug,
            )
            or c_manifest
        )
        c_has_audio = bool(c.local_speaker) or c_has_native_svc
        c_has_ble = bool(
            c.native_ble_tracking_enabled
            or c._ble_tracker is not None
            or c_has_native_svc
            or hass.states.get(
                f"switch.{c.device_slug}_area_ble_presence_beacon"
            )
            is not None
            or hass.states.get(f"switch.{c.device_slug}_ble_presence_beacon")
            is not None
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
        c_chg_st = hass.states.get(
            f"binary_sensor.{c.device_slug}_battery_charging"
        )
        c_usb_st = hass.states.get(
            f"binary_sensor.{c.device_slug}_usb_power_connected"
        )
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

        c_dev_id = c.esphome_device_id or find_esphome_device_id(
            hass, c.device_slug
        )
        c_dev_entry = dev_reg.async_get(c_dev_id) if c_dev_id else None
        raw_model = str(
            (c_dev_entry.model if c_dev_entry else "") or ""
        ).strip()
        c_is_latter_native = bool(
            c.device_profile != "ble_beacon"
            and (
                c_has_native_svc
                or hass.states.get(f"update.{c.device_slug}_project_firmware")
                is not None
                or "latter" in raw_model.lower()
            )
        )
        c_w = int(c_manifest.get("w") or 0)
        c_h = int(c_manifest.get("h") or 0)
        c_board = str(c_manifest.get("board") or "").strip()
        if c.device_profile == "ble_beacon":
            c_model_label = (
                "Private BLE (Phone/Watch)"
                if "private_ble" in c.ble_target_address
                or "." in c.ble_target_address
                else "BLE Beacon / Tag"
            )
        elif c_w > 0 and c_h > 0:
            c_model_label = (
                f"{raw_model} ({c_w}x{c_h})"
                if raw_model
                else f"Latter Display ({c_w}x{c_h}{f' {c_board}' if c_board else ''})"
            )
        else:
            c_model_label = raw_model or "ESPHome Node"

        ha_assigned_area_id = (
            str(c_dev_entry.area_id or "").strip()
            if (c_dev_entry and not c.sync_device_area_enabled)
            else ""
        ) or str(c.get_opt(CONF_DEFAULT_AREA) or "").strip()
        if (
            not ha_assigned_area_id
            and not c.native_ble_tracking_enabled
            and c_dev_entry
            and c_dev_entry.area_id
        ):
            ha_assigned_area_id = str(c_dev_entry.area_id).strip()

        a_obj = (
            area_reg.async_get_area(ha_assigned_area_id)
            if ha_assigned_area_id
            else None
        )
        c_has_assigned_area = a_obj is not None
        c_area_label = a_obj.name if a_obj is not None else "Roaming"

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
            c_seen = bool(
                c._ble_tracker
                and c._ble_tracker.packets_seen > 0
                and not c_away
            )
            c_status_label = (
                f"Online ({c_area_name})"
                if c_seen
                else ("Away" if c_away else "Scanning")
            )
        else:
            c_status_label = (
                "Update Available"
                if c_has_update
                else ("Online" if c_is_online else "Offline")
            )

        system_devices.append(
            {
                "entry_id": c.subentry_id,
                "subentry_id": c.subentry_id,
                "device_slug": c.device_slug,
                "title": (
                    str(c_dev_entry.name_by_user or c_dev_entry.name).strip()
                    if c_dev_entry
                    and (c_dev_entry.name_by_user or c_dev_entry.name)
                    else c.device_title
                ),
                "model_label": c_model_label,
                "has_assigned_area": c_has_assigned_area,
                "area_label": c_area_label,
                "status_label": c_status_label,
                "device_profile": c.device_profile,
                "device_group": c_grp,
                "device_remote_group": c.device_remote_group,
                "device_group_name": group_name_map.get(
                    c_grp, c_grp.replace("_", " ").title()
                ),
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
                "companion_url": f"/latter/devices/{c.subentry_id}",
                "is_current": c.subentry_id == coordinator.subentry_id,
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
        if (
            not cand_slug
            or cand_slug in onboarded_slugs
            or cand_slug in seen_unbridged
        ):
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
        "entry_id": coordinator.subentry_id,
        "subentry_id": coordinator.subentry_id,
        "title": coordinator.device_title,
        "version": INTEGRATION_VERSION,
        "capabilities": device_capabilities,
        "internal_logs": internal_logs,
        "health_warnings": health_warnings,
        "system_devices": system_devices,
        "unbridged_devices": unbridged_devices,
        "discovered_ble_devices": get_discovered_ble_candidates(
            hass,
            onboarded_slugs,
            {
                c.ble_target_address
                for c in _get_all_coordinators(hass)
                if c.ble_target_address
            },
        ),
        "system_controls": _build_system_shared_controls(hass),
        "device_groups": device_groups,
        "saved_profiles": saved_profiles,
        "config": config_data,
        "esphome": esphome_inspector,
        "wallpapers": wallpapers_catalog,
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
            "weather_condition": coordinator.weather_attributes.get(
                "condition", "unknown"
            ),
            "weather_temp": coordinator.weather_attributes.get("temperature"),
            "wallpaper_url": area_attrs.get("wallpaper_url", "none"),
            "doorbell_talk_state": coordinator.doorbell_talk_state,
            "doorbell_anc_mode": coordinator.doorbell_anc_mode,
            "active_remote_slot": coordinator.active_remote_slot,
            "remote_slots_meta": remote_attrs,
            "device_sw_version": str(
                (
                    hass.states.get(
                        f"sensor.{coordinator.device_slug}_firmware_version"
                    ).state
                    if hass.states.get(
                        f"sensor.{coordinator.device_slug}_firmware_version"
                    )
                    and hass.states.get(
                        f"sensor.{coordinator.device_slug}_firmware_version"
                    ).state
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
                        hass.states.get(
                            str(it.get("entity_id"))
                        ).attributes.get("latest_version")
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


class LatterBrandIconView(HomeAssistantView):
    """Serve the Latter brand icon PNG for Studio and HACS."""

    url = API_BRAND_ICON_PATH
    name = "api:latter:brand_icon"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the brand icon view."""
        self.hass = hass
        self._icon_path = Path(__file__).parent.parent / "brand" / "icon.png"

    async def get(self, request: web.Request) -> web.Response:
        """Return the PNG icon bytes."""
        if not self._icon_path.is_file():
            return web.Response(status=404, text="Icon not found")
        data = await self.hass.async_add_executor_job(
            self._icon_path.read_bytes
        )
        return web.Response(
            body=data,
            content_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )


_SIDEBAR_ICON_JS = """(function() {
  const ICON_PATH = "M4 6C4 4.89543 4.89543 4 6 4H18C19.1046 4 20 4.89543 20 6V15C20 16.1046 19.1046 17 18 17H6C4.89543 17 4 16.1046 4 15V6ZM6 6V15H18V6H6ZM12 7.5C12.5523 7.5 13 7.94772 13 8.5V12.5C13 13.0523 12.5523 13.5 12 13.5C11.4477 13.5 11 13.0523 11 12.5V8.5C11 7.94772 11.4477 7.5 12 7.5ZM9 9.5C9.55228 9.5 10 9.94772 10 10.5C10 11.0523 9.55228 11.5 9 11.5C8.44772 11.5 8 11.0523 8 10.5C8 9.94772 8.44772 9.5 9 9.5ZM15 9.5C15.5523 9.5 16 9.94772 16 10.5C16 11.0523 15.5523 11.5 15 11.5C14.4477 11.5 14 11.0523 14 10.5C14 9.94772 14.4477 9.5 15 9.5ZM8 19H16C16.5523 19 17 19.4477 17 20C17 20.5523 16.5523 21 16 21H8C7.44772 21 7 20.5523 7 20C7 19.4477 7.44772 19 8 19Z";
  window.customIcons = window.customIcons || {};
  window.customIcons["latter"] = {
    getIcon: async function(iconName) {
      return { path: ICON_PATH, viewBox: "0 0 24 24" };
    },
    getIconList: async function() {
      return [{ name: "logo" }, { name: "latter" }];
    }
  };
  window.customIconsets = window.customIconsets || {};
  window.customIconsets["latter"] = window.customIcons["latter"].getIcon;
})();
"""


class LatterSidebarIconJsView(HomeAssistantView):
    """Serve the custom `latter:logo` SVG iconset registration script for the HA sidebar."""

    url = API_SIDEBAR_ICON_JS_PATH
    name = "api:latter:sidebar_icon_js"
    requires_auth = False

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the sidebar icon JS view."""
        self.hass = hass

    async def get(self, request: web.Request) -> web.Response:
        """Return the JS snippet that registers `latter:logo` in HA's frontend."""
        return web.Response(
            text=_SIDEBAR_ICON_JS,
            content_type="application/javascript",
            headers={"Cache-Control": "public, max-age=86400"},
        )
