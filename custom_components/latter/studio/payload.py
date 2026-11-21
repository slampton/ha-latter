"""State payload builder for Latter Studio."""

from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any

import homeassistant.const as ha_const
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util

from ..areas import resolve_area_ambient_light
from ..cameras import resolve_camera_capabilities
from ..config_flow import get_discovered_latter_devices
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
from ..doorbell import resolve_doorbell_ring_entities
from ..groups import (
    coordinator_supports_pref,
    get_device_groups,
    get_esphome_device_entities,
    present_section_ids,
    resolve_behavior_key_value,
)
from ..hub import (
    get_area_state_index,
    get_latter_system,
    get_system_config_rev,
    iter_coordinators,
)
from ..identity import esphome_service
from ..media import ma_player_entities
from ..media_browse import is_music_assistant_player
from ..presence import (
    count_area_ble_proxies,
    describe_ble_target_model,
    get_all_areas_presence_summary,
    get_area_signatures_summary,
    get_discovered_ble_candidates,
    inspect_companion_ble_transmitter,
)
from ..protocol import (
    SHORTCUT_SUPPORTED_DOMAINS,
    resolve_shortcut_entity_icon,
)
from ..repairs import parse_device_issue_id
from ..wallpapers import (
    VIRTUAL_COLLECTION_ALL,
    VIRTUAL_COLLECTION_DEFAULTS,
    VIRTUAL_COLLECTION_UNCATEGORIZED,
    VIRTUAL_COLLECTION_UPLOADS,
    list_photo_collections,
    list_wallpaper_catalog,
)
from .settings import (
    ACTIVITY_SOURCES_CATALOG,
    AREA_CATEGORIES_CATALOG,
    DEVICE_PREF_SPECS,
    GAMES_ITEMS_CATALOG,
    HOME_CATEGORIES_CATALOG,
    TOOLS_ITEMS_CATALOG,
    WORLD_CLOCK_ZONES,
    find_by_subentry_id,
    humanize_device_model_label,
    resolve_device_pref_value,
    system_settings_view,
)

__all__ = [
    "MAX_INTERNAL_LOGS",
    "STUDIO_BULK_CONTROL_DOMAINS",
    "build_studio_state_payload",
    "is_coordinator_online_for_studio",
    "load_studio_locales_sync",
    "log_studio_event",
    "resolve_studio_locale_strings",
    "resolve_target_coordinator",
]

_LOCALE_OVERLAYS_CACHE: dict[str, dict[str, str]] = {}
_LOCALES_LOADED: bool = False


def load_studio_locales_sync() -> dict[str, dict[str, str]]:
    """Load optional `<lang>.json` Studio translation overlays from `studio/locales/` (executor)."""
    global _LOCALES_LOADED
    locales_dir = Path(__file__).resolve().parent / "locales"
    loaded: dict[str, dict[str, str]] = {}
    if locales_dir.is_dir():
        for path in sorted(locales_dir.glob("*.json")):
            code = path.stem.strip().lower().replace("_", "-")
            if not code or code == "en":
                continue
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(raw, dict):
                loaded[code] = {
                    str(k): str(v)
                    for k, v in raw.items()
                    if isinstance(k, str) and isinstance(v, str)
                }
    _LOCALE_OVERLAYS_CACHE.clear()
    _LOCALE_OVERLAYS_CACHE.update(loaded)
    _LOCALES_LOADED = True
    return loaded


def resolve_studio_locale_strings(hass: HomeAssistant) -> dict[str, str]:
    """Return cached non-English Studio translation strings for `hass.config.language`, or `{}`."""
    lang = (
        str(getattr(getattr(hass, "config", None), "language", "") or "en")
        .strip()
        .lower()
        .replace("_", "-")
    )
    if not lang or lang == "en" or lang.startswith("en-"):
        return {}
    if not _LOCALES_LOADED:
        load_studio_locales_sync()
    exact = _LOCALE_OVERLAYS_CACHE.get(lang)
    if exact is not None:
        return dict(exact)
    base = lang.split("-", 1)[0]
    fallback = _LOCALE_OVERLAYS_CACHE.get(base)
    return dict(fallback) if fallback is not None else {}

MAX_INTERNAL_LOGS = 150
STUDIO_BULK_CONTROL_DOMAINS: frozenset[str] = frozenset({"select", "switch", "number"})
_CATALOG_DOMAINS: tuple[str, ...] = (
    "media_player",
    "remote",
    "number",
    "input_number",
    "alarm_control_panel",
    "camera",
    "climate",
    "lock",
    "cover",
    "vacuum",
    "weather",
    "calendar",
    "person",
)


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


def resolve_target_coordinator(
    hass: HomeAssistant, subentry_id: str | None
) -> LatterCoordinator | None:
    """Return the Device coordinator whose subentry_id equals subentry_id exactly, else None."""
    return find_by_subentry_id(iter_coordinators(hass), subentry_id)


def build_device_prefs_payload(
    coordinator: LatterCoordinator,
) -> list[dict[str, Any]]:
    """Build the clean native typed device_prefs list for a LatterCoordinator."""
    if coordinator.is_ble_tag:
        return []

    dev_data = coordinator.device_data
    prefs: list[dict[str, Any]] = []
    for spec in DEVICE_PREF_SPECS:
        if not coordinator_supports_pref(coordinator, spec):
            continue
        val = resolve_device_pref_value(dev_data, spec.key)
        opts = list(spec.options)
        if (
            spec.key == "start_screen"
            and not resolve_device_pref_value(dev_data, "home_screen_enabled")
            and val == "Home"
        ):
            val = "Time App"
        elif spec.key == "clock_face" and not coordinator.is_round_display:
            opts = [o for o in opts if o != "Modern Analog"]
            if val == "Modern Analog":
                val = "Minimal Digital"
        prefs.append(
            {
                "key": spec.key,
                "label": spec.label,
                "section": spec.section,
                "group_tier": spec.group_tier,
                "domain": spec.domain,
                "value": val,
                "options": opts,
                "min": spec.min_val,
                "max": spec.max_val,
                "step": spec.step,
                "unit": spec.unit,
            }
        )
    return prefs


def build_speaker_volume_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
) -> dict[str, Any] | None:
    """Return local speaker volume metadata outside esphome.sections."""
    if coordinator.is_ble_tag or not coordinator.has_speaker:
        return None
    local_spk = coordinator.local_speaker
    if not local_spk:
        return None
    spk_st = hass.states.get(local_spk)
    vol_raw = (
        spk_st.attributes.get("volume_level")
        if spk_st is not None and spk_st.state not in ("unavailable", "unknown")
        else None
    )
    vol_pct = (
        round(float(vol_raw) * 100)
        if isinstance(vol_raw, (int, float))
        else None
    )
    dev_data = coordinator.device_data
    return {
        "entity_id": local_spk,
        "name": "Speaker Volume",
        "domain": "number",
        "volume_pct": vol_pct,
        "state": str(vol_pct) if vol_pct is not None else "unavailable",
        "min": 0,
        "max": 100,
        "step": int(resolve_device_pref_value(dev_data, "volume_step_size")),
        "unit": "%",
    }


def build_quick_actions_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
) -> list[dict[str, Any]]:
    """Return quick action buttons outside esphome.sections."""
    if coordinator.is_ble_tag:
        return []
    can_run_cmd = is_coordinator_online_for_studio(hass, coordinator) and bool(
        coordinator.is_device_online()
        or esphome_service(hass, coordinator.esphome_device_id, "latter_device_command")
    )
    cmd_state = "unknown" if can_run_cmd else "unavailable"
    action_specs: list[tuple[str, str, str]] = []
    if coordinator.has_speaker:
        action_specs.append(("find_my", "Find My Device", "identify"))
    if coordinator.has_mic:
        action_specs.append(("trigger_va", "Trigger Voice Assistant", ""))
    if coordinator.has_display:
        action_specs.append(("activate_screensaver", "Activate Screensaver", ""))
    action_specs.append(("restart", "Restart Device", "restart"))

    actions: list[dict[str, Any]] = []
    for cmd_key, label, dclass in action_specs:
        actions.append(
            {
                "key": cmd_key,
                "device_command": cmd_key,
                "label": label,
                "domain": "button",
                "state": cmd_state,
                "device_class": dclass,
            }
        )
    return actions


_SHARED_SECTION_TITLES: dict[str, str] = {
    "display": "Display",
    "interface": "Interface",
    "audio": "Audio",
    "power": "Power",
    "presence": "Presence",
    "security": "Security",
}

_SHARED_SECTION_ORDER: dict[str, int] = {
    "display": 0,
    "interface": 1,
    "audio": 2,
    "power": 3,
    "presence": 4,
    "security": 5,
}


def is_coordinator_online_for_studio(
    hass: HomeAssistant,
    coord: LatterCoordinator,
) -> bool:
    """Return True when `coord` is online using Studio's unified connection state check."""
    if coord.is_ble_tag:
        c_away = coord.is_device_away()
        return bool(
            coord._ble_tracker
            and coord._ble_tracker.packets_seen > 0
            and not c_away
        )
    if coord._rpc_receiver.is_device_unavailable():
        return False
    if coord.is_device_online():
        return True
    if coord.device_entity(
        "sensor", "_system_wi_fi_signal", "_wi_fi_signal", "_ip_address"
    ):
        return False
    c_dev_id = coord.esphome_device_id
    if c_dev_id:
        ent_reg = er.async_get(hass)
        for e_reg in er.async_entries_for_device(ent_reg, c_dev_id):
            if e_reg.platform != "esphome" or e_reg.domain in (
                "select",
                "update",
                "button",
            ):
                continue
            st_e = hass.states.get(e_reg.entity_id)
            if st_e is None or st_e.state in ("unavailable", "unknown", ""):
                continue
            if (
                e_reg.domain == "binary_sensor"
                and (
                    st_e.attributes.get("device_class")
                    or e_reg.original_device_class
                )
                == "connectivity"
            ):
                if st_e.state == "on":
                    return True
                continue
            return True
    return False


def _build_system_shared_controls(
    hass: HomeAssistant,
    coords: list[LatterCoordinator] | None = None,
) -> list[dict[str, Any]]:
    """Build tab-aligned shared controls across all onboarded Latter Devices."""
    all_coords = [
        c
        for c in (coords if coords is not None else iter_coordinators(hass))
        if not c.is_ble_tag
    ]
    coord_meta = [
        (c, is_coordinator_online_for_studio(hass, c), c.is_roaming_device)
        for c in all_coords
    ]
    controls: list[dict[str, Any]] = []

    for spec in DEVICE_PREF_SPECS:
        if spec.group_tier is None or spec.domain not in STUDIO_BULK_CONTROL_DOMAINS:
            continue
        targets: list[dict[str, Any]] = []
        for coord, is_online, is_roaming in coord_meta:
            if not coordinator_supports_pref(coord, spec):
                continue
            cur_val = resolve_device_pref_value(coord.device_data, spec.key)
            if spec.key == "clock_face" and not coord.is_round_display and cur_val == "Modern Analog":
                cur_val = "Minimal Digital"
            state_val = (
                ("on" if cur_val else "off")
                if spec.domain == "switch"
                else str(cur_val)
            )
            targets.append(
                {
                    "device_slug": coord.device_slug,
                    "device_group": coord.device_group,
                    "is_online": is_online,
                    "is_roaming": is_roaming,
                    "pref_key": spec.key,
                    "state": state_val,
                }
            )
        if not targets:
            continue
        sec_title = _SHARED_SECTION_TITLES.get(spec.section, spec.section.title())
        def_state = (
            ("on" if spec.default else "off")
            if spec.domain == "switch"
            else str(spec.default)
        )
        controls.append(
            {
                "key": f"{spec.section}:{spec.domain}:{spec.label.lower()}",
                "pref_key": spec.key,
                "tier": spec.group_tier,
                "section": spec.section,
                "section_title": sec_title,
                "name": spec.label,
                "domain": spec.domain,
                "state": def_state,
                "options": list(spec.options),
                "min": spec.min_val,
                "max": spec.max_val,
                "step": spec.step,
                "unit": spec.unit,
                "targets": targets,
            }
        )

    def _targets_for(
        conf_key: str,
        *,
        roaming_only: bool = False,
        display_only: bool = False,
        state_fn: Any,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for coord, is_online, is_roaming in coord_meta:
            if roaming_only and not is_roaming:
                continue
            if display_only and not coord.has_display:
                continue
            out.append(
                {
                    "device_slug": coord.device_slug,
                    "device_group": coord.device_group,
                    "is_online": is_online,
                    "is_roaming": is_roaming,
                    "pref_key": conf_key,
                    "state": str(state_fn(coord)),
                }
            )
        return out

    subentry_behavior_switches: tuple[tuple[str, str, str, bool], ...] = (
        (CONF_NATIVE_BLE_TRACKING, "Track the Area with BLE Proxies", "presence", False),
        (CONF_BLE_AUTO_SWITCH, "Auto-Switch Active Area", "presence", False),
        (CONF_SYNC_DEVICE_AREA, "Voice Follows Me", "audio", True),
        (CONF_AREA_HANDOFF, "Media Follows Device to New Area", "audio", False),
    )
    for conf_key, label, sec_id, roaming_only in subentry_behavior_switches:
        targets = _targets_for(
            conf_key,
            roaming_only=roaming_only,
            state_fn=lambda c, ck=conf_key: "on"
            if bool(resolve_behavior_key_value(c.device_data, ck))
            else "off",
        )
        if not targets:
            continue
        controls.append(
            {
                "key": f"{sec_id}:switch:{label.lower()}",
                "pref_key": conf_key,
                "tier": "behavior",
                "section": sec_id,
                "section_title": _SHARED_SECTION_TITLES[sec_id],
                "name": label,
                "domain": "switch",
                "state": "off",
                "options": [],
                "min": None,
                "max": None,
                "step": None,
                "unit": "",
                "targets": targets,
            }
        )

    dwell_targets = _targets_for(
        CONF_AREA_FOLLOW_DWELL_S,
        roaming_only=True,
        state_fn=lambda c: str(
            resolve_behavior_key_value(c.device_data, CONF_AREA_FOLLOW_DWELL_S)
        ),
    )
    if dwell_targets:
        controls.append(
            {
                "key": "audio:number:area follow dwell",
                "pref_key": CONF_AREA_FOLLOW_DWELL_S,
                "tier": "behavior",
                "section": "audio",
                "section_title": _SHARED_SECTION_TITLES["audio"],
                "name": "Area Follow Dwell",
                "domain": "number",
                "state": "10",
                "options": [],
                "min": 3,
                "max": 60,
                "step": 1,
                "unit": "s",
                "targets": dwell_targets,
            }
        )

    pin_targets = _targets_for(
        CONF_SECURITY_PIN_POLICY,
        state_fn=lambda c: str(
            resolve_behavior_key_value(c.device_data, CONF_SECURITY_PIN_POLICY)
        ),
    )
    if pin_targets:
        controls.append(
            {
                "key": "security:select:perimeter security policy",
                "pref_key": CONF_SECURITY_PIN_POLICY,
                "tier": "behavior",
                "section": "security",
                "section_title": _SHARED_SECTION_TITLES["security"],
                "name": "Perimeter Security Policy",
                "domain": "select",
                "state": "auto",
                "options": ["auto", "allow", "require_pin", "block"],
                "option_labels": {
                    "auto": "Auto (Roaming Requires PIN)",
                    "allow": "Allow Without PIN",
                    "require_pin": "Always Require PIN",
                    "block": "Block Sensitive Actions",
                },
                "min": None,
                "max": None,
                "step": None,
                "unit": "",
                "targets": pin_targets,
            }
        )

    color_targets = _targets_for(
        CONF_DEVICE_CUSTOM_COLOR,
        display_only=True,
        state_fn=lambda c: c.device_custom_color,
    )
    if color_targets:
        controls.append(
            {
                "key": "display:color:custom accent color",
                "pref_key": CONF_DEVICE_CUSTOM_COLOR,
                "tier": "display",
                "section": "display",
                "section_title": _SHARED_SECTION_TITLES["display"],
                "name": "Custom Accent Color",
                "domain": "color",
                "state": "#3898FF",
                "options": [],
                "min": None,
                "max": None,
                "step": None,
                "unit": "",
                "targets": color_targets,
            }
        )

    wp_targets = _targets_for(
        CONF_WALLPAPER_SOURCE,
        display_only=True,
        state_fn=lambda c: c.wallpaper_source,
    )
    if wp_targets:
        sys_wps = list_wallpaper_catalog(
            hass, "system", "", [], sign_resource=None, display_shape="square"
        )
        wp_opts: list[str] = [""]
        wp_labels: dict[str, str] = {"": "None (Weather / Solid)"}
        for wp in sys_wps:
            sid = str(wp.get("id") or "").strip()
            if sid and sid not in wp_labels:
                wp_opts.append(sid)
                wp_labels[sid] = str(wp.get("name") or wp.get("label") or sid)
        controls.append(
            {
                "key": "display:select:wallpaper",
                "pref_key": CONF_WALLPAPER_SOURCE,
                "tier": "display",
                "section": "display",
                "section_title": _SHARED_SECTION_TITLES["display"],
                "name": "Wallpaper",
                "domain": "select",
                "state": "",
                "options": wp_opts,
                "option_labels": wp_labels,
                "min": None,
                "max": None,
                "step": None,
                "unit": "",
                "targets": wp_targets,
            }
        )

    wp_rot_targets = _targets_for(
        CONF_WALLPAPER_CYCLE_MINUTES,
        display_only=True,
        state_fn=lambda c: str(c.wallpaper_cycle_minutes),
    )
    if wp_rot_targets:
        controls.append(
            {
                "key": "display:select:wallpaper rotation",
                "pref_key": CONF_WALLPAPER_CYCLE_MINUTES,
                "tier": "display",
                "section": "display",
                "section_title": _SHARED_SECTION_TITLES["display"],
                "name": "Wallpaper Rotation",
                "domain": "select",
                "state": "0",
                "options": ["0", "5", "15", "30", "60", "360", "1440"],
                "option_labels": {
                    "0": "Off (Static)",
                    "5": "Every 5 min",
                    "15": "Every 15 min",
                    "30": "Every 30 min",
                    "60": "Every 1 hr",
                    "360": "Every 6 hr",
                    "1440": "Every 24 hr",
                },
                "min": None,
                "max": None,
                "step": None,
                "unit": "",
                "targets": wp_rot_targets,
            }
        )

    col_opts = [
        VIRTUAL_COLLECTION_ALL,
        VIRTUAL_COLLECTION_DEFAULTS,
        VIRTUAL_COLLECTION_UPLOADS,
        VIRTUAL_COLLECTION_UNCATEGORIZED,
    ]
    col_labels: dict[str, str] = {
        VIRTUAL_COLLECTION_ALL: "All photos",
        VIRTUAL_COLLECTION_DEFAULTS: "Defaults",
        VIRTUAL_COLLECTION_UPLOADS: "My photos",
        VIRTUAL_COLLECTION_UNCATEGORIZED: "Uncategorized",
    }
    for col in list_photo_collections():
        cid = str(col.get("id") or "").strip()
        if cid and cid not in col_labels:
            col_opts.append(cid)
            col_labels[cid] = str(col.get("name") or cid)

    wp_col_targets = _targets_for(
        CONF_WALLPAPER_COLLECTION,
        display_only=True,
        state_fn=lambda c: c.wallpaper_collection,
    )
    if wp_col_targets:
        controls.append(
            {
                "key": "display:select:wallpaper collection",
                "pref_key": CONF_WALLPAPER_COLLECTION,
                "tier": "display",
                "section": "display",
                "section_title": _SHARED_SECTION_TITLES["display"],
                "name": "Wallpaper collection",
                "domain": "select",
                "state": "",
                "options": ["", *col_opts],
                "option_labels": {"": "Not using a collection", **col_labels},
                "min": None,
                "max": None,
                "step": None,
                "unit": "",
                "targets": wp_col_targets,
            }
        )

    ss_col_targets = _targets_for(
        CONF_SCREENSAVER_PHOTO_COLLECTION,
        display_only=True,
        state_fn=lambda c: c.screensaver_photo_collection,
    )
    if ss_col_targets:
        controls.append(
            {
                "key": "display:select:photo frame collection",
                "pref_key": CONF_SCREENSAVER_PHOTO_COLLECTION,
                "tier": "display",
                "section": "display",
                "section_title": _SHARED_SECTION_TITLES["display"],
                "name": "Photo Frame collection",
                "domain": "select",
                "state": VIRTUAL_COLLECTION_ALL,
                "options": col_opts,
                "option_labels": col_labels,
                "min": None,
                "max": None,
                "step": None,
                "unit": "",
                "targets": ss_col_targets,
            }
        )

    ss_rot_targets = _targets_for(
        CONF_SCREENSAVER_CYCLE_MINUTES,
        display_only=True,
        state_fn=lambda c: str(c.screensaver_cycle_minutes),
    )
    if ss_rot_targets:
        controls.append(
            {
                "key": "display:select:photo frame rotation",
                "pref_key": CONF_SCREENSAVER_CYCLE_MINUTES,
                "tier": "display",
                "section": "display",
                "section_title": _SHARED_SECTION_TITLES["display"],
                "name": "Photo Frame rotation",
                "domain": "select",
                "state": "5",
                "options": ["0", "1", "5", "15", "30", "60"],
                "option_labels": {
                    "0": "Off (Static)",
                    "1": "Every 1 min",
                    "5": "Every 5 min",
                    "15": "Every 15 min",
                    "30": "Every 30 min",
                    "60": "Every 1 hr",
                },
                "min": None,
                "max": None,
                "step": None,
                "unit": "",
                "targets": ss_rot_targets,
            }
        )

    ss_shuf_targets = _targets_for(
        CONF_SCREENSAVER_SHUFFLE,
        display_only=True,
        state_fn=lambda c: "on" if c.screensaver_shuffle else "off",
    )
    if ss_shuf_targets:
        controls.append(
            {
                "key": "display:switch:photo frame shuffle",
                "pref_key": CONF_SCREENSAVER_SHUFFLE,
                "tier": "display",
                "section": "display",
                "section_title": _SHARED_SECTION_TITLES["display"],
                "name": "Shuffle Photo Frame photos",
                "domain": "switch",
                "state": "off",
                "options": [],
                "min": None,
                "max": None,
                "step": None,
                "unit": "",
                "targets": ss_shuf_targets,
            }
        )

    act_card_targets = _targets_for(
        CONF_ACTIVITY_CARD,
        display_only=True,
        state_fn=lambda c: "on" if c.activity_card_enabled else "off",
    )
    if act_card_targets:
        controls.append(
            {
                "key": "interface:switch:home activity card",
                "pref_key": CONF_ACTIVITY_CARD,
                "tier": "interface",
                "section": "interface",
                "section_title": _SHARED_SECTION_TITLES["interface"],
                "name": "Home Activity Card",
                "domain": "switch",
                "state": "on",
                "options": [],
                "min": None,
                "max": None,
                "step": None,
                "unit": "",
                "targets": act_card_targets,
            }
        )

    act_src_targets = _targets_for(
        CONF_ACTIVITY_SOURCES,
        display_only=True,
        state_fn=lambda c: c.activity_sources_csv,
    )
    if act_src_targets:
        controls.append(
            {
                "key": "interface:pills:activity card sources",
                "pref_key": CONF_ACTIVITY_SOURCES,
                "tier": "interface",
                "section": "interface",
                "section_title": _SHARED_SECTION_TITLES["interface"],
                "name": "Activity Card Sources",
                "domain": "pills",
                "state": "",
                "options": [str(c["token"]) for c in ACTIVITY_SOURCES_CATALOG],
                "option_labels": {
                    str(c["token"]): str(c["label"]) for c in ACTIVITY_SOURCES_CATALOG
                },
                "min": 0,
                "max": None,
                "step": None,
                "unit": "",
                "targets": act_src_targets,
            }
        )

    home_cat_targets = _targets_for(
        CONF_HOME_CATEGORIES,
        display_only=True,
        state_fn=lambda c: c.home_categories_csv,
    )
    if home_cat_targets:
        controls.append(
            {
                "key": "interface:pills:home hub categories",
                "pref_key": CONF_HOME_CATEGORIES,
                "tier": "interface",
                "section": "interface",
                "section_title": _SHARED_SECTION_TITLES["interface"],
                "name": "Home Hub Categories",
                "domain": "pills",
                "state": "",
                "options": [str(c["token"]) for c in HOME_CATEGORIES_CATALOG],
                "option_labels": {
                    str(c["token"]): str(c["label"]) for c in HOME_CATEGORIES_CATALOG
                },
                "min": 1,
                "max": None,
                "step": None,
                "unit": "",
                "targets": home_cat_targets,
            }
        )

    area_cat_targets = _targets_for(
        CONF_AREA_CATEGORIES,
        display_only=True,
        state_fn=lambda c: c.area_categories_csv,
    )
    if area_cat_targets:
        controls.append(
            {
                "key": "interface:pills:area control categories",
                "pref_key": CONF_AREA_CATEGORIES,
                "tier": "interface",
                "section": "interface",
                "section_title": _SHARED_SECTION_TITLES["interface"],
                "name": "Area Control Categories",
                "domain": "pills",
                "state": "",
                "options": [str(c["token"]) for c in AREA_CATEGORIES_CATALOG],
                "option_labels": {
                    str(c["token"]): str(c["label"]) for c in AREA_CATEGORIES_CATALOG
                },
                "min": 1,
                "max": None,
                "step": None,
                "unit": "",
                "targets": area_cat_targets,
            }
        )

    tools_targets = _targets_for(
        CONF_TOOLS_ITEMS,
        display_only=True,
        state_fn=lambda c: c.tools_items_csv,
    )
    if tools_targets:
        controls.append(
            {
                "key": "interface:pills:tools",
                "pref_key": CONF_TOOLS_ITEMS,
                "tier": "interface",
                "section": "interface",
                "section_title": _SHARED_SECTION_TITLES["interface"],
                "name": "Tools",
                "domain": "pills",
                "state": "",
                "options": [str(c["token"]) for c in TOOLS_ITEMS_CATALOG],
                "option_labels": {
                    str(c["token"]): str(c["label"]) for c in TOOLS_ITEMS_CATALOG
                },
                "min": 1,
                "max": None,
                "step": None,
                "unit": "",
                "targets": tools_targets,
            }
        )

    games_targets = _targets_for(
        CONF_GAMES_ITEMS,
        display_only=True,
        state_fn=lambda c: c.games_items_csv,
    )
    if games_targets:
        controls.append(
            {
                "key": "interface:pills:games",
                "pref_key": CONF_GAMES_ITEMS,
                "tier": "interface",
                "section": "interface",
                "section_title": _SHARED_SECTION_TITLES["interface"],
                "name": "Games",
                "domain": "pills",
                "state": "",
                "options": [str(c["token"]) for c in GAMES_ITEMS_CATALOG],
                "option_labels": {
                    str(c["token"]): str(c["label"]) for c in GAMES_ITEMS_CATALOG
                },
                "min": 1,
                "max": None,
                "step": None,
                "unit": "",
                "targets": games_targets,
            }
        )

    rem_targets = _targets_for(
        CONF_DEVICE_REMOTE_GROUP,
        display_only=True,
        state_fn=lambda c: c.device_remote_group,
    )
    if rem_targets:
        raw_global_cfg = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
        rem_groups = system_settings_view(raw_global_cfg).get("remote_groups") or []
        rem_opts: list[str] = ["area_auto"]
        rem_labels: dict[str, str] = {"area_auto": "Match Active Area"}
        for rg in rem_groups:
            rg_id = f"group:{rg['id']}"
            rem_opts.append(rg_id)
            rem_labels[rg_id] = f"Group: {rg['name']}"
        rem_opts.append("all")
        rem_labels["all"] = "All System Remotes"
        controls.append(
            {
                "key": "interface:select:remote control scope",
                "pref_key": CONF_DEVICE_REMOTE_GROUP,
                "tier": "interface",
                "section": "interface",
                "section_title": _SHARED_SECTION_TITLES["interface"],
                "name": "Remote Control Scope",
                "domain": "select",
                "state": "area_auto",
                "options": rem_opts,
                "option_labels": rem_labels,
                "min": None,
                "max": None,
                "step": None,
                "unit": "",
                "targets": rem_targets,
            }
        )

    return sorted(
        controls,
        key=lambda x: (_SHARED_SECTION_ORDER.get(x["section"], 99), x["name"].lower()),
    )


def _is_garage_cover_state(state_obj: Any) -> bool:
    """Return True strictly for garage door `cover.*` entities (excluding blinds, curtains, gates, and interior doors)."""
    dev_class = str(state_obj.attributes.get("device_class") or "").strip().lower()
    if dev_class == "garage":
        return True
    if dev_class != "":
        return False
    friendly = str(state_obj.attributes.get("friendly_name") or "")
    return "garage" in f"{state_obj.entity_id} {friendly}".lower()


def _enrich_hub_catalog_item(
    base_item: dict[str, str],
    state_obj: Any,
    idx: Any,
    area_reg: ar.AreaRegistry,
) -> dict[str, Any]:
    """Attach `area_name` for Studio Home Hub & Camera catalog entries."""
    enriched: dict[str, Any] = dict(base_item)
    area_id = idx.resolve_entity_area_id(state_obj.entity_id) or ""
    area_entry = area_reg.async_get_area(area_id) if area_id else None
    if area_entry is not None:
        enriched["area_name"] = area_entry.name
    return enriched


def _build_entity_catalog(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    all_coords: list[LatterCoordinator] | None = None,
) -> dict[str, Any]:
    """Build the entity pickers for Studio using `AreaStateIndex` (zero full-state scans)."""
    area_reg = ar.async_get(hass)
    areas_list = [
        {"id": a.id, "name": a.name}
        for a in sorted(area_reg.async_list_areas(), key=lambda x: x.name.lower())
    ]

    ma_speakers: list[dict[str, str]] = []
    remotes_list: list[dict[str, str]] = []
    volume_targets: list[dict[str, str]] = []
    alarms_list: list[dict[str, Any]] = []
    cameras_list: list[dict[str, Any]] = []
    climates_list: list[dict[str, Any]] = []
    locks_list: list[dict[str, Any]] = []
    garages_list: list[dict[str, Any]] = []
    vacuums_list: list[dict[str, Any]] = []
    weathers_list: list[dict[str, Any]] = []
    calendars_list: list[dict[str, str]] = []
    persons_list: list[dict[str, str]] = []

    _ = all_coords
    local_spk_id = ""
    local_ma_id = ""
    if coordinator is not None:
        local_spk_id = coordinator.local_speaker
        local_ma_id = coordinator.local_ma_speaker

    idx = get_area_state_index(hass)
    catalog_states = []
    for dom in _CATALOG_DOMAINS:
        catalog_states.extend(idx.states_for_domain(dom))

    all_cam_ids = [s.entity_id for s in catalog_states if s.domain == "camera"]
    doorbell_ring_map = (
        resolve_doorbell_ring_entities(hass, all_cam_ids) if all_cam_ids else {}
    )
    global_cfg = (hass.data.get(DOMAIN, {}) or {}).get(DATA_GLOBAL_CONFIG) or {}
    raw_vol_ov = global_cfg.get("volume_overrides")
    vol_overrides_map: dict[str, str] = {}
    if isinstance(raw_vol_ov, list):
        for ov in raw_vol_ov:
            if isinstance(ov, dict):
                spk = str(ov.get("speaker") or "").strip()
                tgt = str(ov.get("target") or "").strip()
                if spk and tgt:
                    vol_overrides_map[spk] = tgt
    elif isinstance(raw_vol_ov, dict):
        for k, v in raw_vol_ov.items():
            if k and v:
                vol_overrides_map[str(k).strip()] = str(v).strip()

    for state_obj in sorted(catalog_states, key=lambda s: s.entity_id):
        ent_id = state_obj.entity_id
        domain = state_obj.domain
        friendly = str(state_obj.attributes.get("friendly_name") or ent_id)
        suffix_state = (
            " (unavailable)" if state_obj.state == "unavailable" else ""
        )
        item = {
            "id": ent_id,
            "name": f"{friendly} ({ent_id}){suffix_state}",
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
                        _enrich_hub_catalog_item(
                            {
                                "id": ent_id,
                                "name": f"{clean_lbl} — built-in speaker ({ent_id}){suffix_state}",
                            },
                            state_obj,
                            idx,
                            area_reg,
                        )
                    )
                else:
                    ma_speakers.append(
                        _enrich_hub_catalog_item(item, state_obj, idx, area_reg)
                    )
        elif domain == "remote":
            remotes_list.append(item)
        elif domain in ("number", "input_number"):
            volume_targets.append(item)
        elif domain == "alarm_control_panel":
            alarms_list.append(_enrich_hub_catalog_item(item, state_obj, idx, area_reg))
        elif domain == "camera":
            enriched_cam = _enrich_hub_catalog_item(item, state_obj, idx, area_reg)
            cam_caps = resolve_camera_capabilities(
                hass,
                ent_id,
                doorbell_ring_map=doorbell_ring_map,
                volume_overrides=vol_overrides_map,
            )
            enriched_cam["stream_kind"] = cam_caps["stream_kind"]
            enriched_cam["has_audio"] = cam_caps["has_audio"]
            enriched_cam["has_talkback"] = cam_caps["has_talkback"]
            enriched_cam["is_doorbell"] = cam_caps["is_doorbell"]
            cameras_list.append(enriched_cam)
        elif domain == "climate":
            climates_list.append(_enrich_hub_catalog_item(item, state_obj, idx, area_reg))
        elif domain == "lock":
            locks_list.append(_enrich_hub_catalog_item(item, state_obj, idx, area_reg))
        elif domain == "cover":
            if _is_garage_cover_state(state_obj):
                garages_list.append(_enrich_hub_catalog_item(item, state_obj, idx, area_reg))
        elif domain == "vacuum":
            vacuums_list.append(_enrich_hub_catalog_item(item, state_obj, idx, area_reg))
        elif domain == "weather":
            weathers_list.append(_enrich_hub_catalog_item(item, state_obj, idx, area_reg))
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
                }
            )

    ma_players: list[dict[str, str]] = []
    for ma_entry in ma_player_entities(hass):
        ma_st = hass.states.get(ma_entry.entity_id)
        ma_name = str(
            (ma_st.attributes.get("friendly_name") if ma_st else None)
            or ma_entry.name
            or ma_entry.original_name
            or ma_entry.entity_id
        )
        ma_suffix = (
            " (unavailable)"
            if ma_st is not None and ma_st.state == "unavailable"
            else ""
        )
        ma_players.append(
            {
                "id": ma_entry.entity_id,
                "name": f"{ma_name} ({ma_entry.entity_id}){ma_suffix}",
            }
        )
    ma_players.sort(key=lambda item: item["name"].lower())

    area_name_by_id = {a["id"]: a["name"] for a in areas_list}
    shortcut_entities: list[dict[str, str]] = []
    seen_sc_ids: set[str] = set()
    for sc_dom in sorted(SHORTCUT_SUPPORTED_DOMAINS):
        for st_obj in idx.states_for_domain(sc_dom):
            eid = st_obj.entity_id
            if eid in seen_sc_ids:
                continue
            seen_sc_ids.add(eid)
            friendly_lbl = str(st_obj.attributes.get("friendly_name") or eid)
            dclass = str(st_obj.attributes.get("device_class") or "")
            ent_icon = resolve_shortcut_entity_icon(
                sc_dom,
                device_class=dclass,
                entity_icon=str(st_obj.attributes.get("icon") or ""),
                state=str(st_obj.state or ""),
            )
            aid = idx.resolve_entity_area_id(eid) or ""
            area_lbl = area_name_by_id.get(aid, "")
            shortcut_entities.append(
                {
                    "id": eid,
                    "name": friendly_lbl,
                    "domain": sc_dom,
                    "device_class": dclass,
                    "icon": ent_icon,
                    "area_name": area_lbl,
                }
            )
    shortcut_entities.sort(
        key=lambda item: (
            item["area_name"] == "",
            item["area_name"].lower(),
            item["name"].lower(),
            item["id"],
        )
    )

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
        "shortcut_entities": shortcut_entities,
    }


def _build_issues(
    hass: HomeAssistant, coords: list[LatterCoordinator]
) -> list[dict[str, str]]:
    """Return Latter's active Home Assistant repairs (the same ones Settings -> Repairs shows)."""
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
    hass: HomeAssistant,
    current_subentry_id: str,
    *,
    all_coords: list[LatterCoordinator] | None = None,
    include_logs: bool = False,
    skip_sections: Collection[str] = (),
) -> dict[str, Any]:
    """Build the System-scoped part of the Studio payload (no Device needed)."""
    area_reg = ar.async_get(hass)
    device_groups = get_device_groups(hass)
    group_name_map = {
        g["id"]: g["name"]
        for g in device_groups
        if isinstance(g, dict) and g.get("id")
    }

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    coords = all_coords if all_coords is not None else iter_coordinators(hass)

    system_devices: list[dict[str, Any]] = []
    for c in coords:
        c_area_name = c.active_area_name
        live_area_state, _ = c.get_current_area_and_distance()
        c_ble_cat = c.effective_ble_category if c.is_ble_tag else ""
        c_grp = c.device_group
        c_manifest = c.hardware_manifest
        c_has_native_svc = bool(
            esphome_service(
                hass,
                c.esphome_device_id,
                "latter_set_slots",
            )
            or esphome_service(
                hass,
                c.esphome_device_id,
                "latter_show_notification",
            )
            or c_manifest
        )
        c_has_ble = bool(
            c.native_ble_tracking_enabled
            or c._ble_tracker is not None
            or c_has_native_svc
            or c.has_ble_beacon
        )
        c_survey_rows = (
            c._ble_tracker.get_scanner_calibration_telemetry()
            if c._ble_tracker is not None
            and hasattr(c._ble_tracker, "get_scanner_calibration_telemetry")
            else []
        )
        c_packets_seen = (
            c._ble_tracker.packets_seen if c._ble_tracker is not None else 0
        )
        c_bat_st = c.device_state("sensor", "_battery_level")
        c_chg_st = c.device_state("binary_sensor", "_battery_charging")
        c_usb_st = c.device_state("binary_sensor", "_usb_power_connected")
        c_wifi_st = c.device_state(
            "sensor", "_system_wi_fi_signal", "_wi_fi_signal"
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
                c_bat_val = round(float(c_bat_st.state))
            except ValueError:
                c_bat_val = None
        c_wifi_val: int | None = None
        if c_wifi_st and c_wifi_st.state not in ("unavailable", "unknown", ""):
            try:
                c_wifi_val = round(float(c_wifi_st.state))
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
            )
        )
        if c.is_ble_tag:
            c_model_label = describe_ble_target_model(hass, c.ble_target_address)
        else:
            c_model_label = humanize_device_model_label(raw_model, c_manifest)

        static_area_id = (
            str(c.get_opt(CONF_DEFAULT_AREA) or "").strip()
            or (str(c_dev_entry.area_id or "").strip() if c_dev_entry else "")
            if (not c.is_ble_tag and not c.native_ble_tracking_enabled)
            else ""
        )

        a_obj = (
            area_reg.async_get_area(static_area_id)
            if static_area_id
            else None
        )
        c_has_assigned_area = a_obj is not None
        c_upd_st = c.device_state("update", "_project_firmware")
        c_has_update = bool(c_upd_st and c_upd_st.state == "on")
        if not c_has_update and c_dev_id:
            for e_reg in er.async_entries_for_device(ent_reg, c_dev_id):
                if e_reg.platform == "esphome" and e_reg.domain == "update":
                    st_e = hass.states.get(e_reg.entity_id)
                    if st_e and st_e.state == "on":
                        c_has_update = True
                        break
        c_is_online = is_coordinator_online_for_studio(hass, c)
        c_away = c.is_device_away()
        if a_obj is not None:
            c_area_id = static_area_id
            c_area_label = a_obj.name
        elif c.native_ble_tracking_enabled or c.is_ble_tag:
            roaming_aid = (
                str(c._ble_tracker.current_area_id or "").strip()
                if c.is_ble_tag and c._ble_tracker is not None
                else str(c.active_area_id or "").strip()
            )
            roaming_area_obj = (
                area_reg.async_get_area(roaming_aid)
                if roaming_aid and not c_away
                else None
            )
            c_area_id = roaming_aid if roaming_area_obj is not None else ""
            if (
                not c_away
                and (not c.is_ble_tag or c_is_online)
                and live_area_state not in ("", "Away", "Unassigned")
            ):
                c_area_label = f"{live_area_state} (Roaming)"
            else:
                c_area_label = "Roaming"
        else:
            c_area_id = ""
            c_area_label = ""

        if c.is_ble_tag:
            if c_is_online:
                c_status_code = "online"
                c_status_label = "Online"
            elif c_away:
                c_status_code = "away"
                c_status_label = "Away"
            else:
                c_status_code = "scanning"
                c_status_label = "Scanning"
        else:
            if c_has_update:
                c_status_code = "update"
                c_status_label = "Update available"
            elif c_is_online:
                c_status_code = "online"
                c_status_label = "Online"
            elif c.is_ble_sleep_expected():
                c_status_code = "offline"
                c_status_label = "Sleeping"
            else:
                c_status_code = "offline"
                c_status_label = "Offline"

        system_devices.append(
            {
                "subentry_id": c.subentry_id,
                "device_slug": c.device_slug,
                "title": c.device_title,
                "model_label": c_model_label,
                "area_id": c_area_id,
                "has_assigned_area": c_has_assigned_area,
                "area_label": c_area_label,
                "status_code": c_status_code,
                "status_label": c_status_label,
                "is_online": c_is_online,
                "kind": "ble_tag" if c.is_ble_tag else "device",
                "ble_category": c_ble_cat,
                "has_display": c.has_display,
                "has_battery": c.has_battery,
                "is_roaming": c.is_roaming_device,
                "hw_jpeg": c.supports_hw_jpeg,
                "device_group": c_grp,
                "device_remote_group": c.device_remote_group,
                "device_group_name": (
                    ("Phones" if c_ble_cat == "phone" else "BLE tags")
                    if c.is_ble_tag
                    else (
                        "Custom"
                        if c_grp == DEFAULT_DEVICE_GROUP
                        else group_name_map.get(
                            c_grp, c_grp.replace("_", " ").title()
                        )
                    )
                ),
                "assigned_person": c.assigned_person,
                "active_area_name": live_area_state if c.is_ble_tag else c_area_name,
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

    internal_logs = (
        _get_combined_system_and_studio_logs(hass) if include_logs else []
    )

    raw_global_cfg = hass.data.get(DOMAIN, {}).get(DATA_GLOBAL_CONFIG) or {}
    system_view = system_settings_view(raw_global_cfg)
    onboarded_slugs = {c.device_slug for c in coords}
    sys_obj = get_latter_system(hass)
    sign_fn = (
        sys_obj.url_signer.sign_payload_resource if sys_obj is not None else None
    )

    section: dict[str, Any] = {
        "internal_logs": internal_logs,
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
        "issues": _build_issues(hass, coords),
        "ble_proxy_count": count_area_ble_proxies(hass),
        "discovered_latter_devices": get_discovered_latter_devices(hass),
        "ignored_latter_devices": get_discovered_latter_devices(
            hass, only_ignored=True
        ),
        "system_controls": _build_system_shared_controls(hass, coords),
        "device_groups": device_groups,
        "system_config": system_view,
        "has_security_pin": bool(raw_global_cfg.get(CONF_SECURITY_PIN_HASH)),
    }
    if "ble_area_signatures" not in skip_sections:
        section["ble_area_signatures"] = get_area_signatures_summary(hass)
    if "discovered_ble_devices" not in skip_sections:
        section["discovered_ble_devices"] = get_discovered_ble_candidates(
            hass,
            onboarded_slugs,
            {
                c.ble_target_address
                for c in coords
                if c.ble_target_address
            },
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


def _build_pref_specs_catalog() -> list[dict[str, Any]]:
    """Serialize canonical `DevicePrefSpec` metadata for Studio runtime consumers."""
    return [
        {
            "key": spec.key,
            "label": spec.label,
            "domain": spec.domain,
            "default": spec.default,
            "section": spec.section,
            "esphome_section": spec.esphome_section,
            "group_tier": spec.group_tier,
            "options": list(spec.options),
            "min": spec.min_val,
            "max": spec.max_val,
            "step": spec.step,
            "unit": spec.unit,
            "capability": spec.capability,
        }
        for spec in DEVICE_PREF_SPECS
    ]


def build_studio_state_payload(
    hass: HomeAssistant,
    coordinator: LatterCoordinator | None,
    *,
    include_catalog: bool = True,
    include_logs: bool = False,
    skip_sections: Collection[str] = (),
) -> dict[str, Any]:
    """Build the Studio payload: the System part always, plus the Device part when a Device is targeted."""
    all_coords = iter_coordinators(hass)
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
        **_build_system_section(
            hass,
            coordinator.subentry_id if coordinator is not None else "",
            all_coords=all_coords,
            include_logs=include_logs,
            skip_sections=skip_sections,
        ),
    }
    if include_catalog:
        base["catalog"] = _build_entity_catalog(
            hass, coordinator, all_coords=all_coords
        )
        base["pref_specs"] = _build_pref_specs_catalog()
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

    local_spk_id = coordinator.local_speaker
    local_ma_id = coordinator.local_ma_speaker
    esphome_inspector = get_esphome_device_entities(
        hass, coordinator.esphome_device_id, coordinator.device_slug
    )
    device_prefs = build_device_prefs_payload(coordinator)
    quick_actions = build_quick_actions_payload(hass, coordinator)
    speaker_volume = build_speaker_volume_payload(hass, coordinator)
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
    all_esp_items: list[dict[str, Any]] = []
    for s in esphome_inspector.get("sections", []):
        all_esp_items.extend(s.get("items") or [])

    device_capabilities = {
        "has_display": coordinator.has_display,
        "has_imu": coordinator.has_imu,
        "is_round": coordinator.is_round_display,
        "has_battery": coordinator.has_battery,
        "has_power": ("sleep" in sec_ids) or ("battery" in sec_ids),
        "has_voice": not coordinator.is_ble_tag and (coordinator.has_mic or ("voice" in sec_ids)),
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
    config_data = {
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

    return {
        **base,
        "capabilities": device_capabilities,
        "config": config_data,
        "device_prefs": device_prefs,
        "quick_actions": quick_actions,
        "speaker_volume": speaker_volume,
        "esphome": esphome_inspector,
        "wallpapers": wallpapers_catalog,
        "links": {
            "entry_id": coordinator.entry.entry_id,
            "esphome_device_id": coordinator.esphome_device_id or "",
            "latter_device_id": latter_dev.id if latter_dev is not None else "",
        },
        "live": {
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
            "ble_closest_proxy": coordinator._ble_tracker.closest_scanner if coordinator._ble_tracker else "",
            "ble_detected_ref_power": (
                round(float(getattr(coordinator._ble_tracker, "effective_ref_power_dbm", -59)))
                if coordinator._ble_tracker is not None
                else -59
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
            **(
                {}
                if coordinator.is_ble_tag
                else {
                    "timer_running": bool(coordinator.timer_running),
                    "timer_paused": bool(coordinator.timer_paused),
                    "timer_remaining_sec": int(
                        coordinator.current_timer_remaining_sec
                    ),
                    "timer_ends_at": (
                        coordinator.timer_ends_at_utc
                        if coordinator.timer_running
                        else ""
                    ),
                    "stopwatch_running": bool(coordinator.stopwatch_running),
                    "stopwatch_paused": bool(coordinator.stopwatch_paused),
                    "stopwatch_elapsed_sec": int(
                        coordinator.current_stopwatch_elapsed_sec
                    ),
                    "stopwatch_started_at": (
                        coordinator.stopwatch_started_at_utc
                        if coordinator.stopwatch_running
                        else ""
                    ),
                    "alarm_ringing": bool(coordinator.alarm_ringing),
                }
            ),
        },
    }
