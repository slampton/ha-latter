"""State payload builder for Latter Studio (`L3`)."""

from __future__ import annotations

from collections.abc import Collection
from typing import Any, Final

import homeassistant.const as ha_const
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from ..areas.registry import resolve_area_ambient_light
from ..const import (
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_AREA_CATEGORIES,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_CATEGORY,
    CONF_BLE_REF_POWER,
    CONF_BLE_TARGET_ADDRESS,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_DOCK_ITEMS,
    CONF_GAMES_ITEMS,
    CONF_HOME_CATEGORIES,
    CONF_MA_PLAYER_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PINNED_ITEMS,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_IDS,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_SYNC_DEVICE_AREA,
    CONF_TOOLS_ITEMS,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DEFAULT_DEVICE_GROUP,
    DOMAIN,
    INTEGRATION_VERSION,
    MIN_FIRMWARE_SDK_REV,
    STUDIO_REV,
)
from ..coordinator import LatterCoordinator
from ..groups.device_groups import get_device_groups
from ..groups.esphome_inspector import (
    get_esphome_device_entities,
    present_section_ids,
)
from ..hub_registry import get_latter_system, get_system_config_rev, iter_coordinators
from ..identity import esphome_service, get_discovered_latter_devices
from ..presence.ble_discovery import (
    describe_ble_target_model,
    get_discovered_ble_candidates,
    inspect_companion_ble_transmitter,
)
from ..presence.ble_fabric import get_all_areas_presence_summary
from ..presence.ble_registry import (
    count_area_ble_proxies,
    get_area_signatures_summary,
)
from ..protocol_specs import (
    DEVICE_PREF_SPECS,
    WORLD_CLOCK_ZONES,
    humanize_device_model_label,
    resolve_device_pref_value,
)
from ..wallpapers.pools import list_photo_collections, list_wallpaper_catalog
from .payload_sections import (
    build_entity_catalog,
    build_system_shared_controls,
)
from .payload_shared import (
    MAX_INTERNAL_LOGS,
    STUDIO_BULK_CONTROL_DOMAINS,
    _build_issues,
    build_device_prefs_payload,
    build_issues,
    build_pref_specs_catalog,
    build_quick_actions_payload,
    build_speaker_volume_payload,
    get_combined_system_and_studio_logs,
    is_coordinator_online_for_studio,
    load_studio_locales_sync,
    log_studio_event,
    resolve_studio_locale_strings,
    resolve_target_coordinator,
)
from .settings_cleaners import system_settings_view

_DEFAULT_BLE_REF_POWER_DBM: Final = -59
_DEFAULT_BRIGHTNESS_PCT: Final = 80


def _parse_rounded_sensor_int(state_obj: Any) -> int | None:
    """Parse an integer sensor reading from an entity state, or `None` when unavailable."""
    if state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
        return None
    try:
        return round(float(state_obj.state))
    except ValueError:
        return None


def _has_esphome_firmware_update(
    hass: HomeAssistant, ent_reg: er.EntityRegistry, coord: LatterCoordinator
) -> bool:
    """Return True when the bound ESPHome device has an active firmware update entity."""
    c_upd_st = coord.device_state("update", "_project_firmware")
    if c_upd_st is not None and c_upd_st.state == "on":
        return True
    c_dev_id = coord.esphome_device_id
    if not c_dev_id:
        return False
    return any(
        e_reg.platform == "esphome"
        and e_reg.domain == "update"
        and (st_e := hass.states.get(e_reg.entity_id)) is not None
        and st_e.state == "on"
        for e_reg in er.async_entries_for_device(ent_reg, c_dev_id)
    )


def _resolve_system_device_area(
    area_reg: ar.AreaRegistry,
    coord: LatterCoordinator,
    c_dev_entry: dr.DeviceEntry | None,
    live_area_state: str,
    *,
    is_online: bool,
) -> tuple[str, str, bool]:
    """Resolve `(area_id, area_label, has_assigned_area)` for a `system_devices` row."""
    static_area_id = (
        str(coord.get_opt(CONF_DEFAULT_AREA) or "").strip()
        or (str(c_dev_entry.area_id or "").strip() if c_dev_entry else "")
        if (not coord.is_ble_tag and not coord.native_ble_tracking_enabled)
        else ""
    )
    a_obj = area_reg.async_get_area(static_area_id) if static_area_id else None
    if a_obj is not None:
        return static_area_id, a_obj.name, True
    if not (coord.native_ble_tracking_enabled or coord.is_ble_tag):
        return "", "", False

    c_away = coord.is_device_away()
    tracker = coord.ble_tracker
    roaming_aid = (
        str(tracker.current_area_id or "").strip()
        if coord.is_ble_tag and tracker is not None
        else str(coord.active_area_id or "").strip()
    )
    roaming_area_obj = (
        area_reg.async_get_area(roaming_aid) if roaming_aid and not c_away else None
    )
    area_id = roaming_aid if roaming_area_obj is not None else ""
    if (
        not c_away
        and (not coord.is_ble_tag or is_online)
        and live_area_state not in ("", "Away", "Unassigned")
    ):
        return area_id, f"{live_area_state} (Roaming)", False
    return area_id, "Roaming", False


def _resolve_system_device_status(
    coord: LatterCoordinator, *, is_online: bool, has_update: bool
) -> tuple[str, str]:
    """Resolve `(status_code, status_label)` for a `system_devices` row."""
    if coord.is_ble_tag:
        if is_online:
            return "online", "Online"
        return ("away", "Away") if coord.is_device_away() else ("scanning", "Scanning")
    if has_update:
        return "update", "Update available"
    if is_online:
        return "online", "Online"
    return (
        ("offline", "Sleeping")
        if coord.is_ble_sleep_expected()
        else ("offline", "Offline")
    )


def _build_system_device_item(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    current_subentry_id: str,
    group_name_map: dict[str, str],
    registries: tuple[ar.AreaRegistry, dr.DeviceRegistry, er.EntityRegistry],
) -> dict[str, Any]:
    """Build one Device/BLE-tag summary dict for `system_devices`."""
    area_reg, dev_reg, ent_reg = registries
    c_area_name = coord.active_area_name
    live_area_state, _ = coord.get_current_area_and_distance()
    c_ble_cat = coord.effective_ble_category if coord.is_ble_tag else ""
    c_grp = coord.device_group
    c_manifest = coord.hardware_manifest
    c_dev_id = coord.esphome_device_id
    c_has_native_svc = bool(
        esphome_service(hass, c_dev_id, "latter_set_slots")
        or esphome_service(hass, c_dev_id, "latter_show_notification")
        or c_manifest
    )
    tracker = coord.ble_tracker
    c_survey_rows = (
        tracker.get_scanner_calibration_telemetry()
        if tracker is not None and hasattr(tracker, "get_scanner_calibration_telemetry")
        else []
    )
    c_ip_st = coord.device_state("sensor", "_ip_address")
    c_ip_val = (
        str(c_ip_st.state)
        if (c_ip_st and c_ip_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""))
        else ""
    )
    got_dev = dev_reg.async_get(c_dev_id) if c_dev_id else None
    c_dev_entry = got_dev if isinstance(got_dev, dr.DeviceEntry) else None
    raw_model = str((c_dev_entry.model if c_dev_entry else "") or "").strip()
    c_model_label = (
        describe_ble_target_model(hass, coord.ble_target_address)
        if coord.is_ble_tag
        else humanize_device_model_label(raw_model, c_manifest)
    )
    c_is_online = is_coordinator_online_for_studio(hass, coord)
    c_has_update = _has_esphome_firmware_update(hass, ent_reg, coord)
    c_area_id, c_area_label, c_has_assigned_area = _resolve_system_device_area(
        area_reg, coord, c_dev_entry, live_area_state, is_online=c_is_online
    )
    c_status_code, c_status_label = _resolve_system_device_status(
        coord, is_online=c_is_online, has_update=c_has_update
    )
    c_chg_st = coord.device_state("binary_sensor", "_battery_charging")
    c_usb_st = coord.device_state("binary_sensor", "_usb_power_connected")

    return {
        "subentry_id": coord.subentry_id,
        "device_slug": coord.device_slug,
        "title": coord.device_title,
        "model_label": c_model_label,
        "area_id": c_area_id,
        "has_assigned_area": c_has_assigned_area,
        "area_label": c_area_label,
        "status_code": c_status_code,
        "status_label": c_status_label,
        "is_online": c_is_online,
        "kind": "ble_tag" if coord.is_ble_tag else "device",
        "ble_category": c_ble_cat,
        "has_display": coord.has_display,
        "has_battery": coord.has_battery,
        "is_roaming": coord.is_roaming_device,
        "hw_jpeg": coord.supports_hw_jpeg,
        "device_group": c_grp,
        "device_remote_group": coord.device_remote_group,
        "device_group_name": (
            ("Phones" if c_ble_cat == "phone" else "BLE tags")
            if coord.is_ble_tag
            else (
                "Custom"
                if c_grp == DEFAULT_DEVICE_GROUP
                else group_name_map.get(c_grp, c_grp.replace("_", " ").title())
            )
        ),
        "assigned_person": coord.assigned_person,
        "active_area_name": live_area_state if coord.is_ble_tag else c_area_name,
        "is_latter_native": bool(
            not coord.is_ble_tag
            and (
                c_has_native_svc
                or coord.device_entity("update", "_project_firmware") is not None
            )
        ),
        "battery_level": _parse_rounded_sensor_int(
            coord.device_state("sensor", "_battery_level")
        ),
        "is_charging": bool(c_chg_st and c_chg_st.state == "on"),
        "is_usb_connected": bool(c_usb_st and c_usb_st.state == "on"),
        "wifi_rssi": _parse_rounded_sensor_int(
            coord.device_state("sensor", "_system_wi_fi_signal", "_wi_fi_signal")
        ),
        "ip_address": c_ip_val,
        "has_ble": bool(
            coord.native_ble_tracking_enabled
            or tracker is not None
            or c_has_native_svc
            or coord.has_ble_beacon
        ),
        "ble_tracked": bool(coord.is_ble_tag or coord.native_ble_tracking_enabled),
        "ble_survey_rows": c_survey_rows,
        "ble_packets_seen": tracker.packets_seen if tracker is not None else 0,
        "is_current": coord.subentry_id == current_subentry_id,
    }


def build_system_section(
    hass: HomeAssistant,
    current_subentry_id: str,
    *,
    all_coords: list[LatterCoordinator] | None = None,
    include_logs: bool = False,
    skip_sections: Collection[str] = (),
) -> dict[str, Any]:
    """Build the System-scoped part of the Studio payload (no Device needed)."""
    device_groups = get_device_groups(hass)
    group_name_map = {
        g["id"]: g["name"]
        for g in device_groups
        if isinstance(g, dict) and g.get("id")
    }
    registries = (ar.async_get(hass), dr.async_get(hass), er.async_get(hass))
    coords = all_coords if all_coords is not None else list(iter_coordinators(hass))
    system_devices = [
        _build_system_device_item(
            hass, c, current_subentry_id, group_name_map, registries
        )
        for c in coords
    ]
    raw_global_cfg = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
    onboarded_slugs = {c.device_slug for c in coords}
    sys_obj = get_latter_system(hass)
    sign_fn = (
        sys_obj.url_signer.sign_payload_resource if sys_obj is not None else None
    )

    section: dict[str, Any] = {
        "internal_logs": (
            get_combined_system_and_studio_logs(hass) if include_logs else []
        ),
        "system_info": {
            "ha_version": str(
                getattr(ha_const, "__version__", "")
                or getattr(getattr(hass, "config", None), "version", "")
                or ""
            ),
            "integration_version": INTEGRATION_VERSION,
            "min_firmware_sdk_rev": MIN_FIRMWARE_SDK_REV,
            "studio_rev": STUDIO_REV,
        },
        "locale_strings": resolve_studio_locale_strings(hass),
        "system_devices": system_devices,
        "issues": build_issues(hass, coords),
        "ble_proxy_count": count_area_ble_proxies(hass),
        "discovered_latter_devices": get_discovered_latter_devices(hass),
        "ignored_latter_devices": get_discovered_latter_devices(
            hass, only_ignored=True
        ),
        "system_controls": build_system_shared_controls(hass, coords),
        "device_groups": device_groups,
        "system_config": system_settings_view(raw_global_cfg),
        "has_security_pin": bool(raw_global_cfg.get(CONF_SECURITY_PIN_HASH)),
    }
    if "ble_area_signatures" not in skip_sections:
        section["ble_area_signatures"] = get_area_signatures_summary(hass)
    if "discovered_ble_devices" not in skip_sections:
        section["discovered_ble_devices"] = get_discovered_ble_candidates(
            hass,
            onboarded_slugs,
            {c.ble_target_address for c in coords if c.ble_target_address},
        )
    if "photo_collections" not in skip_sections:
        section["photo_collections"] = list_photo_collections()
    if "system_wallpapers" not in skip_sections:
        section["system_wallpapers"] = list_wallpaper_catalog(
            hass,
            "system",
            "",
            [],
            sign_resource=sign_fn,
            display_shape="square",
        )
    return section


_build_system_section = build_system_section


def _build_device_capabilities(
    coordinator: LatterCoordinator,
    sec_ids: set[str],
    local_spk_id: str,
) -> dict[str, Any]:
    """Build capability flags for the targeted `coordinator`."""
    return {
        "has_display": coordinator.has_display,
        "has_imu": coordinator.has_imu,
        "is_round": coordinator.is_round_display,
        "has_battery": coordinator.has_battery,
        "has_power": not coordinator.is_ble_tag
        and (
            coordinator.has_display
            or coordinator.has_battery
            or ("sleep" in sec_ids)
            or ("battery" in sec_ids)
        ),
        "has_voice": not coordinator.is_ble_tag
        and (coordinator.has_mic or ("voice" in sec_ids)),
        "has_audio": (
            not coordinator.is_ble_tag
            and (
                coordinator.has_audio
                or bool(local_spk_id)
                or ("sound" in sec_ids)
                or ("music" in sec_ids)
            )
        ),
        "has_ble_beacon": coordinator.has_ble_beacon,
        "is_roaming_device": coordinator.is_roaming_device,
        "hw_jpeg": coordinator.supports_hw_jpeg,
        "video_max_fps": coordinator.video_max_fps,
        "video_grid_fps": coordinator.video_grid_fps,
    }


def _build_device_config_data(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    clean_wallpaper_favorites: list[str],
    clean_screensaver_photo_ids: list[str],
) -> dict[str, Any]:
    """Build the Device `config` view dictionary for Studio."""
    local_spk_id = coordinator.local_speaker
    local_ma_id = coordinator.local_ma_speaker
    raw_def_spk = str(coordinator.get_opt(CONF_DEFAULT_SPEAKER, "") or "").strip()
    if (
        raw_def_spk
        and local_spk_id
        and local_ma_id
        and raw_def_spk == local_ma_id
    ):
        raw_def_spk = local_spk_id

    dev_pref_data = coordinator.device_data
    effective_default_area = str(
        coordinator.get_opt(CONF_DEFAULT_AREA, "") or ""
    ).strip()
    if (
        not coordinator.is_ble_tag
        and not coordinator.native_ble_tracking_enabled
        and not effective_default_area
        and coordinator.esphome_device_id
    ):
        esp_entry = dr.async_get(hass).async_get(coordinator.esphome_device_id)
        if esp_entry and esp_entry.area_id:
            effective_default_area = str(esp_entry.area_id).strip()

    config_data: dict[str, Any] = {
        CONF_DEVICE_SLUG: coordinator.device_slug,
        "kind": "ble_tag" if coordinator.is_ble_tag else "device",
        "is_roaming": coordinator.is_roaming_device,
        "display_shape": coordinator.display_shape,
        CONF_DEVICE_GROUP: coordinator.device_group,
        CONF_DEVICE_REMOTE_GROUP: coordinator.device_remote_group,
        CONF_DEFAULT_SPEAKER: raw_def_spk,
        CONF_MA_PLAYER_ENTITY: str(coordinator.get_opt(CONF_MA_PLAYER_ENTITY, "") or ""),
        CONF_DEFAULT_AREA: effective_default_area,
        CONF_NATIVE_BLE_TRACKING: coordinator.native_ble_tracking_enabled,
        CONF_BLE_BEACON_UUID: coordinator.ble_beacon_uuid,
        CONF_BLE_TARGET_ADDRESS: coordinator.ble_target_address,
        CONF_BLE_CATEGORY: coordinator.configured_ble_category,
        "effective_ble_category": coordinator.effective_ble_category,
        CONF_BLE_REF_POWER: (
            round(coordinator.ble_ref_power)
            if coordinator.ble_ref_power is not None
            else None
        ),
        CONF_ASSIGNED_PERSON: coordinator.assigned_person,
        CONF_BLE_AUTO_SWITCH: coordinator.ble_auto_switch_enabled,
        CONF_SYNC_DEVICE_AREA: coordinator.sync_device_area_enabled,
        CONF_AREA_FOLLOW_DWELL_S: coordinator.area_follow_dwell_s,
        CONF_AREA_HANDOFF: coordinator.area_handoff_enabled,
        CONF_DEVICE_CUSTOM_COLOR: coordinator.device_custom_color,
        CONF_DOCK_ITEMS: coordinator.dock_items,
        CONF_PINNED_ITEMS: coordinator.pinned_items,
        CONF_AREA_CATEGORIES: coordinator.area_categories_csv,
        CONF_HOME_CATEGORIES: coordinator.home_categories_csv,
        CONF_BROADCAST_SPEAKER_ENTITIES: coordinator.configured_broadcast_speaker_entities,
        CONF_CAMERA_VISIBLE_ENTITIES: coordinator.configured_camera_visible_entities,
        CONF_CAMERA_CAROUSEL_ENTITIES: coordinator.configured_camera_carousel_entities,
        CONF_TOOLS_ITEMS: coordinator.tools_items_csv,
        CONF_GAMES_ITEMS: coordinator.games_items_csv,
        CONF_ACTIVITY_CARD: coordinator.activity_card_enabled,
        CONF_ACTIVITY_SOURCES: coordinator.activity_sources_csv,
        CONF_WALLPAPER_MODE: coordinator.wallpaper_mode,
        CONF_WALLPAPER_SOURCE: coordinator.wallpaper_source,
        CONF_WALLPAPER_COLLECTION: coordinator.wallpaper_collection,
        CONF_WALLPAPER_FAVORITES: clean_wallpaper_favorites,
        CONF_WALLPAPER_CYCLE_MINUTES: coordinator.wallpaper_cycle_minutes,
        CONF_SCREENSAVER_PHOTO_MODE: coordinator.screensaver_photo_mode,
        CONF_SCREENSAVER_PHOTO_SOURCE: coordinator.configured_screensaver_photo_source,
        CONF_SCREENSAVER_PHOTO_COLLECTION: coordinator.screensaver_photo_collection,
        CONF_SCREENSAVER_PHOTO_IDS: clean_screensaver_photo_ids,
        CONF_SCREENSAVER_CYCLE_MINUTES: coordinator.screensaver_cycle_minutes,
        CONF_SCREENSAVER_SHUFFLE: coordinator.screensaver_shuffle,
        CONF_SECURITY_PIN_POLICY: coordinator.configured_security_pin_policy,
        "has_security_pin": coordinator.has_security_pin,
        **{
            spec.key: resolve_device_pref_value(dev_pref_data, spec.key)
            for spec in DEVICE_PREF_SPECS
        },
    }
    if (
        not config_data.get("home_screen_enabled", True)
        and config_data.get("start_screen") == "Home"
    ):
        config_data["start_screen"] = "Time App"
    if (
        not coordinator.supports_hw_jpeg
        and config_data.get("camera_doorbell_popup") == "Live Video"
    ):
        config_data["camera_doorbell_popup"] = "Snapshot"
    return config_data


def _build_device_live_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    esphome_inspector: dict[str, Any],
    wallpapers_catalog: list[dict[str, Any]],
    presence_grid: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the `live` telemetry and status dictionary for the selected Device."""
    all_esp_items: list[dict[str, Any]] = [
        item
        for sec in esphome_inspector.get("sections", [])
        for item in (sec.get("items") or [])
    ]
    fw_st = coordinator.device_state("sensor", "_firmware_version")
    fw_version = (
        str(fw_st.state)
        if fw_st is not None and fw_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN, "")
        else str(esphome_inspector.get("device", {}).get("sw_version") or "")
    )
    update_items = [
        it
        for it in all_esp_items
        if it.get("domain") == "update" and it.get("entity_id")
    ]
    fw_update_entity = str(update_items[0]["entity_id"]) if update_items else ""

    wp_thumb_by_id = {
        str(item.get("id") or ""): str(item.get("thumb_url") or "")
        for item in wallpapers_catalog
    }
    wp_pool = coordinator.resolve_wallpaper_rotation_pool()
    ss_pool = coordinator.resolve_screensaver_photo_pool()
    active_wp_id = coordinator.wallpaper_source
    active_ss_id = coordinator.screensaver_photo_source
    active_ambient = (
        resolve_area_ambient_light(hass, coordinator.active_area_id or None)
        if not coordinator.is_ble_tag
        else {
            "resolved_entity": "",
            "resolved_name": "",
            "lux_display": "",
            "ambient_pct": None,
        }
    )
    active_area_name = (
        coordinator.get_current_area_and_distance()[0]
        if coordinator.is_ble_tag
        else coordinator.active_area_name
    )
    local_spk_id = coordinator.local_speaker
    local_ma_id = coordinator.local_ma_speaker
    tracker = coordinator.ble_tracker

    live: dict[str, Any] = {
        "active_wallpaper_id": active_wp_id,
        "active_wallpaper_thumb_url": wp_thumb_by_id.get(active_wp_id, ""),
        "wallpaper_pool_count": len(wp_pool),
        "active_screensaver_photo_id": active_ss_id,
        "active_screensaver_photo_thumb_url": wp_thumb_by_id.get(active_ss_id, ""),
        "screensaver_pool_count": len(ss_pool),
        "active_area_name": active_area_name,
        "active_area_lux_display": active_ambient["lux_display"],
        "active_area_ambient_pct": active_ambient["ambient_pct"],
        "active_area_illuminance_entity": active_ambient["resolved_entity"],
        "active_area_illuminance_name": active_ambient["resolved_name"],
        "ma_link_matched": bool(
            local_ma_id
            or not local_spk_id
            or not hass.config_entries.async_entries("music_assistant")
        ),
        "ble_closest_proxy": tracker.closest_scanner if tracker is not None else "",
        "ble_detected_ref_power": (
            round(float(getattr(tracker, "effective_ref_power_dbm", _DEFAULT_BLE_REF_POWER_DBM)))
            if tracker is not None
            else _DEFAULT_BLE_REF_POWER_DBM
        ),
        "ble_transmitter_status": (
            inspect_companion_ble_transmitter(hass, coordinator.ble_target_address)
            if coordinator.is_ble_tag
            else None
        ),
        "area_presence_grid": presence_grid,
        "device_sw_version": fw_version,
        "sdk_rev": str(coordinator.hardware_manifest.get("sdk") or ""),
        "fw_update_entity": fw_update_entity,
        "fw_update_available": any(it.get("state") == "on" for it in update_items),
        "effective_security_pin_policy": coordinator.security_pin_policy,
        "has_security_pin": coordinator.has_security_pin,
        "is_ble_sleep_expected": bool(coordinator.is_ble_sleep_expected()),
    }
    if not coordinator.is_ble_tag:
        live.update(
            {
                "radio_connected": bool(
                    getattr(
                        coordinator,
                        "radio_connected",
                        is_coordinator_online_for_studio(hass, coordinator),
                    )
                ),
                "display_power_state": int(
                    getattr(coordinator, "display_power_state", 0)
                ),
                "display_brightness_pct": int(
                    getattr(
                        coordinator,
                        "display_brightness_pct",
                        _DEFAULT_BRIGHTNESS_PCT,
                    )
                ),
                "screensaver_active": bool(
                    getattr(coordinator, "screensaver_active", False)
                ),
                "telemetry": getattr(coordinator, "device_telemetry", None),
                "timer_running": bool(coordinator.timer_running),
                "timer_paused": bool(coordinator.timer_paused),
                "timer_remaining_sec": int(coordinator.current_timer_remaining_sec),
                "timer_ends_at": (
                    coordinator.timer_ends_at_utc if coordinator.timer_running else ""
                ),
                "stopwatch_running": bool(coordinator.stopwatch_running),
                "stopwatch_paused": bool(coordinator.stopwatch_paused),
                "stopwatch_elapsed_sec": int(coordinator.current_stopwatch_elapsed_sec),
                "stopwatch_started_at": (
                    coordinator.stopwatch_started_at_utc
                    if coordinator.stopwatch_running
                    else ""
                ),
                "alarm_ringing": bool(coordinator.alarm_ringing),
            }
        )
    return live


def build_studio_state_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    *,
    include_catalog: bool = True,
    include_logs: bool = False,
    skip_sections: Collection[str] = (),
) -> dict[str, Any]:
    """Build the Studio payload: the System part always, plus the Device part when a Device is targeted."""
    all_coords = list(iter_coordinators(hass))
    base: dict[str, Any] = {
        "type": "state",
        "subentry_id": coordinator.subentry_id if coordinator is not None else "",
        "title": coordinator.device_title if coordinator is not None else "",
        "version": INTEGRATION_VERSION,
        "studio_rev": STUDIO_REV,
        "system_config_rev": get_system_config_rev(hass),
        "device_config_rev": (
            coordinator.device_config_rev if coordinator is not None else 0
        ),
        **build_system_section(
            hass,
            coordinator.subentry_id if coordinator is not None else "",
            all_coords=all_coords,
            include_logs=include_logs,
            skip_sections=skip_sections,
        ),
    }
    if include_catalog:
        base["catalog"] = build_entity_catalog(
            hass, coordinator, all_coords=all_coords
        )
        base["pref_specs"] = build_pref_specs_catalog()
        base["world_clock_zones"] = list(WORLD_CLOCK_ZONES)
    presence_grid = get_all_areas_presence_summary(hass)
    if coordinator is None:
        return {
            **base,
            "capabilities": {},
            "config": {},
            "device_prefs": [],
            "quick_actions": [],
            "speaker_volume": None,
            "esphome": {"device": {}, "sections": []},
            "wallpapers": [],
            "live": {"area_presence_grid": presence_grid},
        }

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
    valid_wp_ids = {str(item.get("id") or "") for item in wallpapers_catalog}
    valid_ss_ids = {
        str(item.get("id") or "")
        for item in wallpapers_catalog
        if item.get("kind") != "dynamic_preset"
    }
    clean_wallpaper_favorites = list(
        dict.fromkeys(
            pid for pid in coordinator.wallpaper_favorites if pid in valid_wp_ids
        )
    )
    clean_screensaver_photo_ids = list(
        dict.fromkeys(
            pid for pid in coordinator.screensaver_photo_ids if pid in valid_ss_ids
        )
    )
    sec_ids = present_section_ids(esphome_inspector.get("sections"))
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
        "capabilities": _build_device_capabilities(
            coordinator, sec_ids, coordinator.local_speaker
        ),
        "config": _build_device_config_data(
            hass,
            coordinator,
            clean_wallpaper_favorites,
            clean_screensaver_photo_ids,
        ),
        "device_prefs": build_device_prefs_payload(coordinator),
        "quick_actions": build_quick_actions_payload(hass, coordinator),
        "speaker_volume": build_speaker_volume_payload(hass, coordinator),
        "esphome": esphome_inspector,
        "wallpapers": wallpapers_catalog,
        "links": {
            "entry_id": coordinator.entry.entry_id,
            "esphome_device_id": coordinator.esphome_device_id or "",
            "latter_device_id": latter_dev.id if latter_dev is not None else "",
        },
        "live": _build_device_live_payload(
            hass,
            coordinator,
            esphome_inspector,
            wallpapers_catalog,
            presence_grid,
        ),
    }


__all__ = [
    "MAX_INTERNAL_LOGS",
    "STUDIO_BULK_CONTROL_DOMAINS",
    "_build_issues",
    "_build_system_section",
    "build_device_prefs_payload",
    "build_entity_catalog",
    "build_issues",
    "build_pref_specs_catalog",
    "build_quick_actions_payload",
    "build_speaker_volume_payload",
    "build_studio_state_payload",
    "build_system_section",
    "build_system_shared_controls",
    "is_coordinator_online_for_studio",
    "load_studio_locales_sync",
    "log_studio_event",
    "resolve_studio_locale_strings",
    "resolve_target_coordinator",
]
