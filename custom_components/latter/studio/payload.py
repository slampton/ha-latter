"""State payload builder and brand icon views for Latter Studio."""

from __future__ import annotations

from datetime import UTC, datetime
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
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util

from ..area_engine import get_esphome_device_entities
from ..backup_engine import get_device_groups_and_profiles
from ..ble_engine import (
    count_area_ble_proxies,
    get_all_areas_presence_summary,
    get_discovered_ble_candidates,
)
from ..browse_engine import is_music_assistant_player
from ..const import (
    API_BRAND_ICON_PATH,
    API_SIDEBAR_ICON_JS_PATH,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_PAGE_SIZE,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DOCK_APPS,
    CONF_MA_PLAYER_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PRESENCE_ENTITY,
    CONF_SYNC_DEVICE_AREA,
    CONF_WALLPAPER_CYCLE_MINUTES,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    DOMAIN,
    INTEGRATION_VERSION,
)
from ..coordinator import LatterCoordinator
from ..identity import esphome_service
from ..issue_ids import parse_device_issue_id
from ..media_engine import ma_player_entities
from ..system import get_latter_system
from ..wallpaper_engine import list_wallpaper_catalog
from .scope import find_by_subentry_id
from .settings import system_settings_view

MAX_INTERNAL_LOGS = 150


def log_studio_event(
    hass: HomeAssistant, level: str, source: str, message: str
) -> None:
    """Append a diagnostic event (UTC ISO timestamp; Studio formats it for the user) to the Studio ring buffer."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    logs: list[dict[str, str]] = domain_data.setdefault("internal_logs", [])
    ts = dt_util.utcnow().isoformat(timespec="seconds")
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
                    datetime.fromtimestamp(float(ts_val), tz=UTC).isoformat(
                        timespec="seconds"
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
    hass: HomeAssistant, subentry_id: str | None
) -> LatterCoordinator | None:
    """Return the Device coordinator whose subentry_id equals subentry_id exactly, else None."""
    return find_by_subentry_id(_get_all_coordinators(hass), subentry_id)


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
            hass, coord.esphome_device_id, coord.device_slug
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
                        "is_roaming": coord.is_roaming_device,
                        "entity_id": item.get("entity_id"),
                        "state": item.get("state"),
                    }
                )
    return sorted(
        by_label.values(),
        key=lambda x: (x["section"], x["name"].lower()),
    )


def _build_entity_catalog(
    hass: HomeAssistant, coordinator: LatterCoordinator | None
) -> dict[str, Any]:
    """Build the entity pickers for Studio (camera previews and speaker de-duplication need a Device)."""
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

    allowed_cams_set: set[str] = set()
    local_spk_id = ""
    local_ma_id = ""
    if coordinator is not None:
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
            " (unavailable)" if state_obj.state == "unavailable" else ""
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
                            "name": f"{clean_lbl} — built-in speaker ({ent_id}){suffix_state}",
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
            if coordinator is not None and ent_id in allowed_cams_set:
                cam_sig = coordinator.sign_payload_resource(
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

    ma_players: list[dict[str, str]] = []
    for ma_entry in ma_player_entities(hass):
        ma_st = hass.states.get(ma_entry.entity_id)
        ma_name = str(
            (ma_st.attributes.get("friendly_name") if ma_st else None)
            or ma_entry.name
            or ma_entry.original_name
            or ma_entry.entity_id
        )
        ma_players.append({"id": ma_entry.entity_id, "name": f"{ma_name} ({ma_entry.entity_id})"})
    ma_players.sort(key=lambda item: item["name"].lower())

    return {
        "areas": areas_list,
        "ma_speakers": ma_speakers,
        "ma_players": ma_players,
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
    }


def _build_issues(
    hass: HomeAssistant, coords: list[LatterCoordinator]
) -> list[dict[str, str]]:
    """Return Latter's active Home Assistant repairs (the same ones Settings › Repairs shows).

    `kind` is the repair's translation key; per-Device repairs name their Device. `detail` carries the
    one placeholder Studio shows (the crash reason, or the list of missing entities).
    """
    by_sub = {c.subentry_id: c for c in coords}
    out: list[dict[str, str]] = []
    for issue in ir.async_get(hass).issues.values():
        if issue.domain != DOMAIN or not issue.active or issue.dismissed_version is not None:
            continue
        parsed = parse_device_issue_id(issue.issue_id, set(by_sub))
        kind, sub_id = parsed if parsed else (str(issue.translation_key or issue.issue_id), "")
        placeholders = issue.translation_placeholders or {}
        severity = getattr(issue.severity, "value", issue.severity)
        out.append(
            {
                "issue_id": issue.issue_id,
                "kind": kind,
                "severity": str(severity or "warning"),
                "subentry_id": sub_id,
                "device_title": by_sub[sub_id].device_title if sub_id else "",
                "detail": str(
                    placeholders.get("reason") or placeholders.get("missing_list") or ""
                ),
            }
        )
    out.sort(key=lambda i: (i["device_title"].lower(), i["kind"]))
    return out


def _build_system_section(
    hass: HomeAssistant, current_subentry_id: str
) -> dict[str, Any]:
    """Build the System-scoped part of the Studio payload (no Device needed)."""
    area_reg = ar.async_get(hass)
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
        c_grp = c.device_group
        c_manifest = c.hardware_manifest
        c_has_native_svc = bool(
            esphome_service(
                hass,
                c.esphome_device_id,
                "set_browse_slots",
            )
            or esphome_service(
                hass,
                c.esphome_device_id,
                "set_area_slots",
            )
            or esphome_service(
                hass,
                c.esphome_device_id,
                "show_notification",
            )
            or c_manifest
        )
        c_has_ble = bool(
            c.native_ble_tracking_enabled
            or c._ble_tracker is not None
            or c_has_native_svc
            or c.device_entity("switch", "_area_ble_presence_beacon", "_ble_presence_beacon")
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
        c_bat_st = c.device_state("sensor", "_battery_level")
        c_chg_st = c.device_state("binary_sensor", "_battery_charging")
        c_usb_st = c.device_state("binary_sensor", "_usb_power_connected")
        c_wifi_st = c.device_state(
            "sensor", "_system_wi_fi_signal", "_wi_fi_signal", "_wifi_signal"
        )
        c_ip_st = c.device_state("sensor", "_ip_address")
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

        c_dev_id = c.esphome_device_id
        c_dev_entry = dev_reg.async_get(c_dev_id) if c_dev_id else None
        raw_model = str(
            (c_dev_entry.model if c_dev_entry else "") or ""
        ).strip()
        c_is_latter_native = bool(
            not c.is_ble_tag
            and (
                c_has_native_svc
                or c.device_entity("update", "_project_firmware") is not None
                or "latter" in raw_model.lower()
            )
        )
        c_w = int(c_manifest.get("w") or 0)
        c_h = int(c_manifest.get("h") or 0)
        c_board = str(c_manifest.get("board") or "").strip()
        if c.is_ble_tag:
            c_model_label = (
                "Private BLE (phone or watch)"
                if "private_ble" in c.ble_target_address
                or "." in c.ble_target_address
                else "BLE beacon or tag"
            )
        elif c_w > 0 and c_h > 0:
            c_model_label = (
                f"{raw_model} ({c_w}x{c_h})"
                if raw_model
                else f"Latter display ({c_w}x{c_h}{f' {c_board}' if c_board else ''})"
            )
        else:
            c_model_label = raw_model

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
        c_area_label = (
            a_obj.name
            if a_obj is not None
            else ("Roaming" if (c.is_roaming_device or c.is_ble_tag) else "")
        )

        c_upd_st = c.device_state("update", "_project_firmware")
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
        if c.is_ble_tag:
            c_away = c.is_device_away()
            c_seen = bool(
                c._ble_tracker
                and c._ble_tracker.packets_seen > 0
                and not c_away
            )
            c_is_online = c_seen
            c_status_label = (
                f"Online ({c_area_name})"
                if c_seen
                else ("Away" if c_away else "Scanning")
            )
        else:
            c_status_label = (
                "Update available"
                if c_has_update
                else ("Online" if c_is_online else "Offline")
            )

        system_devices.append(
            {
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
                "is_online": c_is_online,
                "kind": "ble_tag" if c.is_ble_tag else "device",
                "has_display": c.has_display,
                "is_roaming": c.is_roaming_device,
                "device_group": c_grp,
                "device_remote_group": c.device_remote_group,
                "device_group_name": group_name_map.get(
                    c_grp, c_grp.replace("_", " ").title()
                ),
                "assigned_person": c.assigned_person,
                "active_area_name": c_area_name,
                "is_latter_native": c_is_latter_native,
                "battery_level": c_bat_val,
                "is_charging": bool(c_chg_st and c_chg_st.state == "on"),
                "is_usb_connected": bool(c_usb_st and c_usb_st.state == "on"),
                "wifi_rssi": c_wifi_val,
                "ip_address": c_ip_val,
                "has_ble": c_has_ble,
                "ble_tracked": bool(c.is_ble_tag or c.native_ble_tracking_enabled),
                "ble_survey_rows": c_survey_rows,
                "ble_packets_seen": c_packets_seen,
                "is_current": c.subentry_id == current_subentry_id,
            }
        )

    internal_logs = _get_combined_system_and_studio_logs(hass)

    all_coords = _get_all_coordinators(hass)
    onboarded_slugs = {c.device_slug for c in all_coords}

    return {
        "internal_logs": internal_logs,
        "system_devices": system_devices,
        "issues": _build_issues(hass, all_coords),
        "ble_proxy_count": count_area_ble_proxies(hass),
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
        "system_config": system_settings_view(
            hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
        ),
    }


def _build_now_playing(
    hass: HomeAssistant, coordinator: LatterCoordinator
) -> dict[str, str]:
    """Return the Device's active speaker and what it's playing, read from Home Assistant ("" when unknown)."""
    spk_id = coordinator.active_speaker or ""
    st = hass.states.get(spk_id) if spk_id else None
    if (
        (st is None or st.state in ("unavailable", "unknown"))
        and coordinator.is_local_speaker_entity(spk_id)
        and coordinator.local_ma_speaker
    ):
        st = hass.states.get(coordinator.local_ma_speaker) or st
    speaker_name = ""
    if spk_id:
        speaker_name = (
            coordinator.device_title
            if coordinator.is_local_speaker_entity(spk_id)
            else str((st.attributes.get("friendly_name") if st else "") or spk_id)
        )
    media_state = st.state if st is not None and st.state not in ("unavailable", "unknown") else ""
    active = media_state in ("playing", "paused", "buffering")
    return {
        "speaker_name": speaker_name,
        "media_state": media_state,
        "media_title": str(st.attributes.get("media_title") or "") if active and st else "",
        "media_artist": str(st.attributes.get("media_artist") or "") if active and st else "",
    }


def build_studio_state_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
) -> dict[str, Any]:
    """Build the Studio payload: the System part always, plus the Device part when a Device is targeted.

    `system_config` (System settings) never depends on the selected Device; `config` holds only
    that Device's own settings.
    """
    base: dict[str, Any] = {
        "subentry_id": coordinator.subentry_id if coordinator is not None else "",
        "title": coordinator.device_title if coordinator is not None else "",
        "version": INTEGRATION_VERSION,
        **_build_system_section(
            hass, coordinator.subentry_id if coordinator is not None else ""
        ),
        "catalog": _build_entity_catalog(hass, coordinator),
    }
    presence_grid = get_all_areas_presence_summary(hass)
    if coordinator is None:
        return {
            **base,
            "capabilities": {},
            "config": {},
            "esphome": {"device": {}, "sections": []},
            "wallpapers": [],
            "live": {"area_presence_grid": presence_grid},
        }

    local_spk_id = coordinator.local_speaker
    local_ma_id = coordinator.local_ma_speaker
    _, area_attrs = coordinator.get_area_context_payload()
    esphome_inspector = get_esphome_device_entities(
        hass, coordinator.esphome_device_id, coordinator.device_slug
    )
    wallpapers_catalog = list_wallpaper_catalog(
        hass,
        coordinator.device_slug,
        coordinator.wallpaper_source,
        coordinator.wallpaper_favorites,
        sign_resource=coordinator.sign_payload_resource,
        display_shape=coordinator.display_shape,
    )

    has_native_slots = bool(
        esphome_service(
            hass,
            coordinator.esphome_device_id,
            "set_browse_slots",
        )
        or esphome_service(
            hass,
            coordinator.esphome_device_id,
            "set_area_slots",
        )
        or coordinator.hardware_manifest
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
    device_capabilities = {
        "has_display": has_native_slots or ("display" in sec_ids) or ("home" in sec_ids),
        "has_power": ("sleep" in sec_ids) or ("battery" in sec_ids),
        "has_voice": "voice" in sec_ids,
        "has_audio": (
            has_native_slots
            or bool(local_spk_id)
            or ("sound" in sec_ids)
            or ("music" in sec_ids)
        ),
        "has_ble_beacon": has_native_slots or has_ble_beacon_entity,
        "is_roaming_device": coordinator.is_roaming_device,
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
        "kind": "ble_tag" if coordinator.is_ble_tag else "device",
        "is_roaming": coordinator.is_roaming_device,
        "display_shape": coordinator.display_shape,
        CONF_DEVICE_GROUP: coordinator.device_group,
        CONF_DEFAULT_PAGE_SIZE: coordinator.default_page_size,
        CONF_DEFAULT_SPEAKER: raw_def_spk,
        CONF_MA_PLAYER_ENTITY: str(coordinator.get_opt(CONF_MA_PLAYER_ENTITY, "") or ""),
        CONF_DEFAULT_AREA: coordinator.get_opt(CONF_DEFAULT_AREA, ""),
        CONF_NATIVE_BLE_TRACKING: coordinator.native_ble_tracking_enabled,
        CONF_BLE_BEACON_UUID: coordinator.ble_beacon_uuid,
        CONF_BLE_TARGET_ADDRESS: coordinator.ble_target_address,
        CONF_PRESENCE_ENTITY: coordinator.presence_entity or "",
        CONF_ASSIGNED_PERSON: coordinator.assigned_person,
        CONF_BLE_AUTO_SWITCH: coordinator.ble_auto_switch_enabled,
        CONF_SYNC_DEVICE_AREA: coordinator.sync_device_area_enabled,
        CONF_AREA_FOLLOW_DWELL_S: coordinator.area_follow_dwell_s,
        CONF_AREA_HANDOFF: coordinator.area_handoff_enabled,
        CONF_DEVICE_CUSTOM_COLOR: coordinator.device_custom_color,
        CONF_DOCK_APPS: coordinator.dock_apps_csv,
        CONF_WALLPAPER_CYCLE_MINUTES: coordinator.wallpaper_cycle_minutes,
    }

    ble_survey_rows: list[dict[str, Any]] = []
    if coordinator._ble_tracker is not None and hasattr(
        coordinator._ble_tracker, "get_area_calibration_telemetry"
    ):
        ble_survey_rows = (
            coordinator._ble_tracker.get_area_calibration_telemetry()
        )

    fw_st = coordinator.device_state("sensor", "_firmware_version")
    fw_version = (
        str(fw_st.state)
        if fw_st is not None and fw_st.state not in ("unavailable", "unknown", "")
        else str(esphome_inspector.get("device", {}).get("sw_version") or "")
    )
    update_items = [
        it for it in all_esp_items if it.get("domain") == "update" and it.get("entity_id")
    ]
    fw_update_entity = str(update_items[0]["entity_id"]) if update_items else ""
    fw_latest_state = hass.states.get(fw_update_entity) if fw_update_entity else None

    latter_idents = coordinator.get_device_info()["identifiers"]
    latter_dev = next(
        (
            d
            for d in dr.async_entries_for_config_entry(
                dr.async_get(hass), coordinator.entry.entry_id
            )
            if d.identifiers & latter_idents
        ),
        None,
    )

    return {
        **base,
        "capabilities": device_capabilities,
        "config": config_data,
        "esphome": esphome_inspector,
        "wallpapers": wallpapers_catalog,
        # Home Assistant's own pages for this Device: its ESPHome device page and Latter's diagnostics.
        "links": {
            "entry_id": coordinator.entry.entry_id,
            "esphome_device_id": coordinator.esphome_device_id or "",
            "latter_device_id": latter_dev.id if latter_dev is not None else "",
        },
        "live": {
            "active_area_name": str(area_attrs.get("area_name") or ""),
            "ble_closest_proxy": str(area_attrs.get("ble_closest_proxy") or ""),
            "ble_packets_seen": area_attrs.get("ble_packets_seen", 0),
            "ble_survey_rows": ble_survey_rows,
            "area_presence_grid": presence_grid,
            "now": _build_now_playing(hass, coordinator),
            "device_sw_version": fw_version,
            "fw_update_entity": fw_update_entity,
            "fw_update_available": any(it.get("state") == "on" for it in update_items),
            "fw_latest_version": str(
                (fw_latest_state.attributes.get("latest_version") if fw_latest_state else "")
                or ""
            ),
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
