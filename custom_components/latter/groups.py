"""Device Groups, Power Profile baselines, Studio entity classification, and Device reset for Latter."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify

from .const import (
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_AREA_CATEGORIES,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUPS,
    CONF_DOCK_APPS,
    CONF_HOME_CATEGORIES,
    CONF_NATIVE_BLE_TRACKING,
    CONF_SECURITY_PIN_POLICY,
    CONF_SYNC_DEVICE_AREA,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DEFAULT_DEVICE_GROUP,
    DOMAIN,
)
from .identity import device_entities, esphome_service, get_bound_esphome_device
from .studio.settings import (
    DEVICE_PREF_KEYS,
    DEVICE_PREF_SPEC_MAP,
    DEVICE_PREF_SPECS,
    POWER_PROFILE_PREFS,
    POWER_PROFILE_SUBKEYS,
    DevicePrefSpec,
    clean_device_settings,
    resolve_device_pref_value,
)

if TYPE_CHECKING:
    from .coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ESPHome Entity Section Classification
# ---------------------------------------------------------------------------

ASSIST_SATELLITE_TRANSLATION_KEYS: frozenset[str] = frozenset(
    {"pipeline", "pipeline_n", "vad_sensitivity", "wake_word", "wake_word_n"}
)

QUICK_ACTION_BUTTON_KEYWORDS: tuple[str, ...] = (
    "find_my",
    "find my",
    "trigger_va",
    "trigger_voice",
    "voice_assistant",
    "voice assistant",
    "activate_screensaver",
    "screensaver",
    "hibernate",
    "restart",
    "identify",
)

DIAGNOSTIC_BUTTON_KEYWORDS: tuple[str, ...] = (
    "memory_report",
    "log_memory",
    "factory_reset",
    "safe_mode",
)

DEVELOPER_ENTITY_KEYWORDS: tuple[str, ...] = (
    "telemetry_profiler",
    "log_memory",
    "memory_report",
    "ram_low_water",
    "ram_largest_block",
    "psram_low_water",
    "weather_sim",
    "weather_simulation",
)

UNIVERSAL_SECTION_META: tuple[tuple[str, str, str], ...] = (
    (
        "home",
        "Home screen",
        "Clock face, weather background, home dock shortcuts, and home screen behavior.",
    ),
    (
        "display",
        "Display & appearance",
        "Screen brightness, color profile, UI theme, and boot animations.",
    ),
    (
        "sleep",
        "Sleep & wake",
        "Inactivity timeouts, screensaver, pickup-to-wake, tap-to-wake, and hibernate schedule.",
    ),
    (
        "voice",
        "Voice assistant",
        "Wake word models, microphone mute, and voice detection sensitivity.",
    ),
    (
        "sound",
        "Sound & alerts",
        "Onboard speaker chimes, alert volume, and volume step increments.",
    ),
    (
        "music",
        "Music & media",
        "Media player entity and library, artist, album, and podcast sorting options.",
    ),
    (
        "area",
        "Area & BLE presence",
        "BLE presence beacon toggle and automatic area handoff settings.",
    ),
    (
        "remote",
        "TV & media remote",
        "Active remote slot selection and on-device remote behavior.",
    ),
    (
        "battery",
        "Battery & power",
        "Battery charge level, charging status, PMIC voltage, and internal temperature.",
    ),
    (
        "actions",
        "Device actions",
        "One-tap restart, hibernate, refresh, and maintenance triggers.",
    ),
    (
        "network",
        "Network & diagnostics",
        "Wi-Fi signal strength, IP/MAC address, status sensors, and firmware updates.",
    ),
    (
        "developer",
        "Developer",
        "Telemetry profiler, memory reports, heap low-water marks, and weather simulation.",
    ),
    (
        "other",
        "General & custom entities",
        "Additional sensors, switches, and custom project entities.",
    ),
)


def classify_esphome_entity_section(
    entity_id: str,
    friendly_name: str,
    domain: str,
    device_class: str,
    entity_category: str | None,
    translation_key: str | None = None,
    device_object_prefixes: tuple[str, ...] = (),
) -> tuple[str, str | None]:
    """Classify an ESPHome entity into a focused section; returns (section_id, custom_section_title_or_None)."""
    name_clean = friendly_name.strip()
    dev_cls = device_class.lower()

    if domain == "assist_satellite" or (
        domain == "select" and (translation_key or "") in ASSIST_SATELLITE_TRANSLATION_KEYS
    ):
        return "voice", None

    ent_suffix = entity_id.split(".", 1)[-1].lower()
    for prefix in device_object_prefixes:
        if prefix and ent_suffix.startswith(prefix + "_"):
            ent_suffix = ent_suffix[len(prefix) + 1 :]
            break
    clean_low = name_clean.lower()

    if any(k in clean_low or k in ent_suffix for k in DEVELOPER_ENTITY_KEYWORDS):
        return "developer", None

    if domain == "button" or dev_cls in ("restart", "identify"):
        if dev_cls in ("restart", "identify") or any(
            k in clean_low or k in ent_suffix for k in QUICK_ACTION_BUTTON_KEYWORDS
        ):
            return "actions", None
        is_diag_button = any(
            k in clean_low or k in ent_suffix for k in DIAGNOSTIC_BUTTON_KEYWORDS
        )
        if not is_diag_button:
            prefix_low = name_clean.split(":", 1)[0].strip().lower() if ":" in name_clean else ""
            if prefix_low not in ("system", "network", "wifi", "diagnostics", "developer"):
                return "actions", None

    if ":" in name_clean:
        prefix_raw = name_clean.split(":", 1)[0].strip()
        prefix_low = prefix_raw.lower()
        if prefix_low in ("home", "home screen", "clock"):
            return "home", None
        if prefix_low in ("display", "ui", "screen", "theme", "appearance"):
            return "display", None
        if prefix_low in ("sleep & wake", "sleep", "wake"):
            return "sleep", None
        if prefix_low in ("voice", "wake word", "assist", "mic", "microphone"):
            return "voice", None
        if prefix_low in ("sound", "audio", "chime", "alerts"):
            return "sound", None
        if prefix_low in ("music", "media", "player"):
            return "music", None
        if prefix_low in ("ble", "area", "presence"):
            return "area", None
        if prefix_low in ("remote", "tv"):
            return "remote", None
        if prefix_low in ("battery", "power", "pmic"):
            return "battery", None
        if prefix_low in ("action", "actions"):
            return "actions", None
        if prefix_low == "developer":
            return "developer", None
        if prefix_low in ("system", "network", "wifi", "diagnostics"):
            return "network", None
        if 2 <= len(prefix_raw) <= 24:
            sec_slug = "custom_" + re.sub(r"[^a-z0-9]+", "_", prefix_low).strip("_")
            return sec_slug, prefix_raw

    if dev_cls in ("battery", "voltage", "current", "power", "energy") or any(
        k in clean_low or k in ent_suffix
        for k in (
            "battery",
            "charging",
            "charger",
            "vbus",
            "axp2101",
            "pmic",
            "voltage",
            "internal_temp",
            "die_temp",
            "imu_temp",
        )
    ):
        return "battery", None

    if (
        domain == "update"
        or dev_cls in ("signal_strength", "timestamp", "duration")
        or any(
            k in clean_low or k in ent_suffix
            for k in (
                "wifi",
                "wi-fi",
                "wi_fi",
                "rssi",
                "signal",
                "ip_address",
                "ip address",
                "mac_address",
                "mac address",
                "ssid",
                "bssid",
                "uptime",
                "free_heap",
                "heap",
                "psram",
                "memory",
                "cpu",
                "firmware",
                "version",
                "esphome",
                "status",
                "online",
                "connected",
                "safe_mode",
            )
        )
        or (
            entity_category == "diagnostic"
            and domain in ("sensor", "binary_sensor", "text_sensor")
        )
    ):
        return "network", None

    if any(
        k in clean_low or k in ent_suffix
        for k in ("clock", "weather_background", "shortcut_", "dock", "home_")
    ):
        return "home", None

    if any(
        k in clean_low or k in ent_suffix
        for k in (
            "sleep",
            "wake_on",
            "pickup_to_wake",
            "tap_to_wake",
            "screensaver",
            "hibernate",
            "timeout",
        )
    ):
        return "sleep", None

    if any(
        k in clean_low or k in ent_suffix
        for k in (
            "display",
            "screen",
            "brightness",
            "backlight",
            "amoled",
            "theme",
            "color_profile",
            "boot",
        )
    ):
        return "display", None

    if any(
        k in clean_low or k in ent_suffix
        for k in (
            "voice",
            "wake_word",
            "micro_wake",
            "mic",
            "microphone",
            "sensitivity",
            "assist",
        )
    ):
        return "voice", None

    if any(
        k in clean_low or k in ent_suffix
        for k in (
            "sound",
            "chime",
            "beep",
            "ringtone",
            "speaker_volume",
            "alert_volume",
            "volume_step",
            "dac",
            "es8311",
        )
    ):
        return "sound", None

    if any(k in clean_low or k in ent_suffix for k in ("ble", "beacon", "ibeacon", "presence", "area")):
        return "area", None

    if any(
        k in clean_low or k in ent_suffix
        for k in ("remote", "slot_1", "slot_2", "slot_3", "slot_4")
    ):
        return "remote", None

    if domain == "media_player" or any(
        k in clean_low or k in ent_suffix
        for k in (
            "music",
            "album",
            "artist",
            "podcast",
            "queue",
            "playlist",
            "sort",
            "track",
            "speaker",
        )
    ):
        return "music", None

    if entity_category == "diagnostic":
        return "network", None

    return "other", None


def present_section_ids(sections: object) -> set[str]:
    """Return the ids of the Device's entity sections that hold at least one entity."""
    if not isinstance(sections, (list, tuple)):
        return set()
    return {
        str(sec.get("id"))
        for sec in sections
        if isinstance(sec, dict) and sec.get("id") and sec.get("items")
    }


def _apply_ha_display_precision(
    entry: er.RegistryEntry | None, raw_val: float, default_precision: int = 0
) -> int | float:
    """Format a numeric sensor value using Home Assistant's Entity Registry display_precision."""
    prec: int | None = None
    if entry is not None and isinstance(entry.options, dict):
        sensor_opts = entry.options.get("sensor")
        if isinstance(sensor_opts, dict):
            if sensor_opts.get("display_precision") is not None:
                prec = int(sensor_opts["display_precision"])
            elif sensor_opts.get("suggested_display_precision") is not None:
                prec = int(sensor_opts["suggested_display_precision"])
    if prec is None:
        prec = default_precision
    if prec <= 0:
        return round(raw_val)
    return round(raw_val, prec)


def get_esphome_device_entities(
    hass: HomeAssistant,
    esphome_device_id: str | None,
    device_slug: str = "",
) -> dict[str, Any]:
    """Inspect and semantically group all entities of the bound ESPHome device."""
    bound_dev = get_bound_esphome_device(hass, esphome_device_id)
    target_device_id = bound_dev.id if bound_dev is not None else None
    dev_reg = dr.async_get(hass)

    dev_meta: dict[str, str] = {
        "device_id": target_device_id or "",
        "name": device_slug,
        "model": "ESPHome Node",
        "manufacturer": "ESPHome",
        "sw_version": "",
        "mac": "",
    }
    if target_device_id:
        dev = dev_reg.async_get(target_device_id)
        if dev:
            dev_meta["name"] = str(dev.name_by_user or dev.name or device_slug)
            dev_meta["model"] = str(dev.model or "ESPHome Node")
            dev_meta["manufacturer"] = str(dev.manufacturer or "ESPHome")
            dev_meta["sw_version"] = str(dev.sw_version or "")
            for _ctype, cval in dev.connections:
                dev_meta["mac"] = str(cval)
                break

    sections_map: dict[str, list[dict[str, Any]]] = {
        sec_id: [] for sec_id, _title, _desc in UNIVERSAL_SECTION_META
    }
    custom_sec_titles: dict[str, str] = {}

    entries: list[er.RegistryEntry] = device_entities(
        hass,
        target_device_id,
        include_disabled=False,
    )

    dev_prefix = dev_meta["name"].strip()
    slug_words = device_slug.strip().replace("_", " ").replace("-", " ")
    object_prefixes = tuple(
        sorted(
            {p for p in (slugify(dev_prefix), slugify(device_slug)) if p},
            key=len,
            reverse=True,
        )
    )

    domain_sort_order = {
        "switch": 1,
        "select": 2,
        "number": 3,
        "light": 4,
        "button": 5,
        "media_player": 6,
        "binary_sensor": 7,
        "sensor": 8,
        "update": 9,
    }

    for entry in entries:
        state_obj = hass.states.get(entry.entity_id)
        state_val = state_obj.state if state_obj else "unavailable"
        if entry.domain == "sensor" and state_val not in ("unavailable", "unknown", ""):
            try:
                num_v = float(state_val)
                fmt_v = _apply_ha_display_precision(entry, num_v, default_precision=1)
                state_val = str(fmt_v)
            except ValueError:
                pass
        attrs = state_obj.attributes if state_obj else {}
        if getattr(entry, "has_entity_name", False) and (entry.name or entry.original_name):
            raw_friendly = str(entry.name or entry.original_name)
        else:
            raw_friendly = str(
                attrs.get("friendly_name")
                or entry.name
                or entry.original_name
                or entry.entity_id
            )
        clean_name = raw_friendly
        for candidate_prefix in (dev_prefix, slug_words):
            if candidate_prefix and clean_name.lower().startswith(candidate_prefix.lower() + " "):
                clean_name = clean_name[len(candidate_prefix) + 1 :].strip() or raw_friendly

        unit = str(attrs.get("unit_of_measurement") or "")
        dev_class = str(
            attrs.get("device_class") or entry.original_device_class or ""
        )
        cat = entry.entity_category

        sec_id, custom_title = classify_esphome_entity_section(
            entry.entity_id,
            clean_name,
            entry.domain,
            dev_class,
            cat,
            translation_key=entry.translation_key,
            device_object_prefixes=object_prefixes,
        )
        if custom_title and sec_id not in sections_map:
            sections_map[sec_id] = []
            custom_sec_titles[sec_id] = custom_title

        display_label = (
            clean_name.split(":", 1)[1].strip()
            if ":" in clean_name and clean_name.split(":", 1)[1].strip()
            else clean_name
        )

        item: dict[str, Any] = {
            "entity_id": entry.entity_id,
            "name": display_label,
            "key": entry.translation_key or "",
            "domain": entry.domain,
            "state": state_val,
            "unit": unit,
            "device_class": dev_class,
            "category": str(cat.value if cat else "primary"),
            "options": list(attrs.get("options") or []),
            "min": attrs.get("min"),
            "max": attrs.get("max"),
            "step": attrs.get("step"),
            "_sort": (
                domain_sort_order.get(entry.domain, 50),
                clean_name.lower(),
            ),
        }
        sections_map[sec_id].append(item)

    sections_list: list[dict[str, Any]] = []
    for sec_id, sec_title, sec_desc in UNIVERSAL_SECTION_META:
        if sec_id == "other":
            continue
        sec_items = sections_map.get(sec_id, [])
        if not sec_items:
            continue
        sec_items.sort(key=lambda x: x["_sort"])
        for it in sec_items:
            it.pop("_sort", None)
        sections_list.append(
            {
                "id": sec_id,
                "title": sec_title,
                "description": sec_desc,
                "items": sec_items,
            }
        )

    for sec_id, sec_title in sorted(custom_sec_titles.items(), key=lambda x: x[1].lower()):
        sec_items = sections_map.get(sec_id, [])
        if not sec_items:
            continue
        sec_items.sort(key=lambda x: x["_sort"])
        for it in sec_items:
            it.pop("_sort", None)
        sections_list.append(
            {
                "id": sec_id,
                "title": sec_title,
                "description": f"Entities grouped under the '{sec_title}:' prefix.",
                "items": sec_items,
            }
        )

    other_items = sections_map.get("other", [])
    if other_items:
        other_items.sort(key=lambda x: x["_sort"])
        for it in other_items:
            it.pop("_sort", None)
        sections_list.append(
            {
                "id": "other",
                "title": "General & custom entities",
                "description": "Additional sensors, switches, and custom project entities (spillover).",
                "items": other_items,
            }
        )

    return {
        "device": dev_meta,
        "sections": sections_list,
    }


# ---------------------------------------------------------------------------
# Device Groups & Power Profile Baselines
# ---------------------------------------------------------------------------

def coordinator_supports_pref(coordinator: Any, spec: DevicePrefSpec) -> bool:
    """Return True when `coordinator`'s hardware supports preference `spec`."""
    if getattr(coordinator, "is_ble_tag", False):
        return False
    cap = spec.capability
    if cap == "display":
        return bool(getattr(coordinator, "has_display", True))
    if cap == "display_imu":
        return bool(getattr(coordinator, "has_display", True)) and bool(
            getattr(coordinator, "has_imu", True)
        )
    if cap == "display_battery":
        return bool(getattr(coordinator, "has_display", True)) and bool(
            getattr(coordinator, "has_battery", True)
        )
    if cap == "mic":
        return bool(getattr(coordinator, "has_mic", True))
    if cap == "speaker":
        return bool(getattr(coordinator, "has_speaker", True))
    if cap == "beacon":
        return bool(getattr(coordinator, "has_ble_beacon", True))
    if cap == "beacon_battery":
        return bool(getattr(coordinator, "has_ble_beacon", True)) and bool(
            getattr(coordinator, "has_battery", True)
        )
    return True


# Tier 2: Operational Behavior keys synced automatically by a Device Group's baseline.
GROUP_BEHAVIOR_DEVICE_KEYS: tuple[str, ...] = (
    CONF_NATIVE_BLE_TRACKING,
    CONF_BLE_AUTO_SWITCH,
    CONF_SYNC_DEVICE_AREA,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_SECURITY_PIN_POLICY,
    *tuple(s.key for s in DEVICE_PREF_SPECS if s.group_tier == "behavior"),
)

# Tier 3: Personal & Area Appearance/Layout keys preserved per-device on group join/sync.
GROUP_APPEARANCE_DEVICE_KEYS: tuple[str, ...] = (
    CONF_DOCK_APPS,
    CONF_AREA_CATEGORIES,
    CONF_HOME_CATEGORIES,
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_WALLPAPER_SOURCE,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_DEVICE_CUSTOM_COLOR,
    "device_remote_group",
    *tuple(s.key for s in DEVICE_PREF_SPECS if s.group_tier == "appearance"),
)

# Tier 3 ESPHome controls (personal/Area appearance & layout; not overwritten when syncing a Group's Tier 2 baseline).
APPEARANCE_ESPHOME_CONTROL_KEYS: frozenset[str] = frozenset(
    {
        "select:clock_face",
        "select:time_format",
        "select:color_profile",
        "switch:enable_home_screen",
        "select:start_screen",
        "select:return_to_home_timeout",
        "select:screensaver_style",
        "select:visual_profile",
        "switch:weather_background",
        "switch:sun",
        "switch:moon",
        "switch:wake_greeting",
        "select:album_art_style",
        "select:overlay_style",
        "select:album_sort_order",
        "select:artist_album_sort_order",
        "select:podcast_sort_order",
        "switch:show_speaker_shortcut",
        "switch:show_library_shortcut",
    }
)

# Diagnostic/simulation controls excluded from group baselines and snapshots.
EXCLUDED_ESPHOME_CONTROL_KEYS: frozenset[str] = frozenset(
    {
        "switch:telemetry_profiler",
        "select:weather_simulation",
    }
)

# Canonical 7-control specs matching kPowerProfiles in esphome-latter-core/include/ui_system.h.
POWER_PROFILE_SPECS: dict[str, dict[str, str]] = {
    "Portable Carry": {
        "select:wake_word_mode": "Docked Only",
        "select:tap_to_wake": "Docked Only",
        "select:pickup_to_wake": "Docked Only",
        "select:battery_screen_timeout": "30s",
        "select:docked_idle_timeout": "1 min",
        "select:battery_hibernate_timeout": "15 min",
        "switch:docked_screensaver": "on",
    },
    "Handheld Roaming": {
        "select:wake_word_mode": "Docked Only",
        "select:tap_to_wake": "Always On",
        "select:pickup_to_wake": "Always On",
        "select:battery_screen_timeout": "30s",
        "select:docked_idle_timeout": "1 min",
        "select:battery_hibernate_timeout": "30 min",
        "switch:docked_screensaver": "on",
    },
    "Wearable Watch": {
        "select:wake_word_mode": "Docked Only",
        "select:tap_to_wake": "Always On",
        "select:pickup_to_wake": "Always On",
        "select:battery_screen_timeout": "15s",
        "select:docked_idle_timeout": "1 min",
        "select:battery_hibernate_timeout": "15 min",
        "switch:docked_screensaver": "on",
    },
    "Tabletop Dock": {
        "select:wake_word_mode": "Docked Only",
        "select:tap_to_wake": "Docked Only",
        "select:pickup_to_wake": "Disabled",
        "select:battery_screen_timeout": "30s",
        "select:docked_idle_timeout": "5 min",
        "select:battery_hibernate_timeout": "15 min",
        "switch:docked_screensaver": "on",
    },
    "Always-On Wall / Desk": {
        "select:wake_word_mode": "Always On",
        "select:tap_to_wake": "Always On",
        "select:pickup_to_wake": "Disabled",
        "select:battery_screen_timeout": "Never",
        "select:docked_idle_timeout": "5 min",
        "select:battery_hibernate_timeout": "Disabled",
        "switch:docked_screensaver": "on",
    },
}

DEFAULT_DEVICE_GROUPS: list[dict[str, Any]] = [
    {
        "id": "unassigned",
        "name": "Unassigned",
        "description": "Default group with no baseline settings applied",
        "builtin": True,
        "device_config": {},
        "esphome_controls": {},
    },
    {
        "id": "handhelds",
        "name": "Handhelds",
        "description": "Battery-powered roaming displays with pickup and tap wake",
        "builtin": True,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "power_profile": "Handheld Roaming",
            **POWER_PROFILE_PREFS["Handheld Roaming"],
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": "90%",
            "night_brightness": "70%",
            "ble_beacon_mode": "Handheld Only",
        },
        "esphome_controls": {},
    },
    {
        "id": "wearables",
        "name": "Wearables",
        "description": "Compact wearable displays with double-tap wake on battery and 15s screen timeout",
        "builtin": True,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "power_profile": "Wearable Watch",
            **POWER_PROFILE_PREFS["Wearable Watch"],
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": "80%",
            "night_brightness": "60%",
            "ble_beacon_mode": "Handheld + Screen Off",
        },
        "esphome_controls": {},
    },
    {
        "id": "bedrooms",
        "name": "Bedrooms",
        "description": "Nightstand and quiet tabletop displays with dimmed night brightness and docked wake word",
        "builtin": True,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: False,
            CONF_BLE_AUTO_SWITCH: False,
            CONF_SYNC_DEVICE_AREA: False,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "power_profile": "Tabletop Dock",
            **POWER_PROFILE_PREFS["Tabletop Dock"],
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": "80%",
            "night_brightness": "60%",
            "alert_volume": 50,
        },
        "esphome_controls": {},
    },
    {
        "id": "common_areas",
        "name": "Common Areas",
        "description": "Shared tabletop displays with Always-On wake word and 5 min docked idle timeout",
        "builtin": True,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: False,
            CONF_BLE_AUTO_SWITCH: False,
            CONF_SYNC_DEVICE_AREA: False,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "power_profile": "Custom",
            "wake_word_mode": "Always On",
            "tap_to_wake": "Always On",
            "pickup_to_wake": "Disabled",
            "battery_screen_timeout": "30s",
            "docked_idle_timeout": "5 min",
            "battery_hibernate_timeout": "15 min",
            "docked_screensaver": True,
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": "90%",
            "night_brightness": "70%",
        },
        "esphome_controls": {},
    },
    {
        "id": "wall_panels",
        "name": "Wall & Desk Panels",
        "description": "Stationary mains-powered panels with Always-On wake word and no battery hibernate",
        "builtin": True,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: False,
            CONF_BLE_AUTO_SWITCH: False,
            CONF_SYNC_DEVICE_AREA: False,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "power_profile": "Always-On Wall / Desk",
            **POWER_PROFILE_PREFS["Always-On Wall / Desk"],
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": "90%",
            "night_brightness": "70%",
        },
        "esphome_controls": {},
    },
]

_BUILTIN_GROUPS_BY_ID: dict[str, dict[str, Any]] = {
    g["id"]: g for g in DEFAULT_DEVICE_GROUPS
}


def canonical_control_key(domain: str, label: str) -> str:
    """Build a slug-independent control key ('select:wake_word_mode') for cross-device restore & group baselines."""
    clean = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return f"{domain.strip().lower()}:{clean}"


def is_behavior_esphome_control(ckey: str) -> bool:
    """Return True if a canonical ESPHome control key belongs to Tier 2 Operational Behavior."""
    return ckey not in APPEARANCE_ESPHOME_CONTROL_KEYS and ckey not in EXCLUDED_ESPHOME_CONTROL_KEYS


def capture_live_esphome_controls(
    hass: HomeAssistant,
    esphome_device_id: str | None,
    *,
    behavior_only: bool = False,
) -> dict[str, Any]:
    """Capture configurable ESPHome entities (select, switch, number) of the bound device."""
    esp_info = get_esphome_device_entities(hass, esphome_device_id)
    controls: dict[str, Any] = {}
    for sec in esp_info.get("sections", []):
        for item in sec.get("items", []):
            dom = str(item.get("domain") or "")
            if dom not in ("select", "switch", "number"):
                continue
            state_val = item.get("state")
            if state_val in (None, "unavailable", "unknown", ""):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            ckey = canonical_control_key(dom, name)
            if ckey in EXCLUDED_ESPHOME_CONTROL_KEYS:
                continue
            if behavior_only and not is_behavior_esphome_control(ckey):
                continue
            if dom == "number":
                try:
                    controls[ckey] = float(state_val)
                except (ValueError, TypeError):
                    controls[ckey] = state_val
            else:
                controls[ckey] = str(state_val)
    return controls


def _same_control_val(a: Any, b: Any) -> bool:
    """Compare two control values, treating numeric strings ('80' vs '80.0') and booleans/switches consistently."""
    sa = str(a).strip()
    sb = str(b).strip()
    if sa == sb:
        return True
    if sa.lower() in ("on", "true", "1") and sb.lower() in ("on", "true", "1"):
        return True
    if sa.lower() in ("off", "false", "0") and sb.lower() in ("off", "false", "0"):
        return True
    try:
        return abs(float(sa) - float(sb)) < 1e-4
    except (ValueError, TypeError):
        return False


async def apply_esphome_controls_to_device(
    hass: HomeAssistant, esphome_device_id: str | None, controls: dict[str, Any]
) -> int:
    """Apply a dictionary of canonical ESPHome control values ('domain:clean_name': val) to a live device."""
    from .areas import async_execute_area_action

    if not isinstance(controls, dict) or not controls:
        return 0
    esp_info = get_esphome_device_entities(hass, esphome_device_id)
    by_ckey: dict[str, dict[str, Any]] = {}
    for sec in esp_info.get("sections", []):
        for item in sec.get("items", []):
            dom = str(item.get("domain") or "")
            if dom not in ("select", "switch", "number"):
                continue
            name = str(item.get("name") or "").strip()
            ent_id = str(item.get("entity_id") or "").strip()
            if not name or not ent_id:
                continue
            by_ckey[canonical_control_key(dom, name)] = item

    async def _apply_one(ckey: str, target_val: Any, force: bool = False) -> int:
        item = by_ckey.get(ckey)
        if item is None:
            return 0
        dom = str(item.get("domain") or "")
        ent_id = str(item.get("entity_id") or "").strip()
        cur_val = item.get("state")
        if not force and _same_control_val(target_val, cur_val):
            return 0
        if dom == "select":
            opts = item.get("options") or []
            if not opts or str(target_val) in opts:
                await async_execute_area_action(
                    hass, entity_id=ent_id, action="select", option=str(target_val)
                )
                return 1
        elif dom == "switch":
            want_on = str(target_val).lower() in ("on", "true", "1")
            await async_execute_area_action(
                hass,
                entity_id=ent_id,
                action="turn_on" if want_on else "turn_off",
            )
            return 1
        elif dom == "number":
            try:
                num_v = float(target_val)
                await async_execute_area_action(
                    hass, entity_id=ent_id, action="set_level", level=round(num_v)
                )
                return 1
            except (ValueError, TypeError):
                pass
        return 0

    applied = 0
    prof_name = str(controls.get("select:power_profile") or "").strip()
    prof_spec = POWER_PROFILE_SPECS.get(prof_name)

    if prof_spec is not None and "select:power_profile" in by_ckey:
        applied += await _apply_one("select:power_profile", prof_name, force=True)

    for ckey, target_val in controls.items():
        if ckey == "select:power_profile":
            continue
        if prof_spec is not None and ckey in prof_spec and _same_control_val(target_val, prof_spec[ckey]):
            continue
        applied += await _apply_one(ckey, target_val)

    return applied


def _normalize_group_entry(raw: Mapping[str, Any] | dict[str, Any]) -> dict[str, Any]:
    """Normalize a single Device Group entry, merging built-in baseline defaults when not yet customized."""
    gid = str(raw.get("id") or "").strip()
    builtin_def = _BUILTIN_GROUPS_BY_ID.get(gid)
    base_dev = dict(builtin_def.get("device_config") or {}) if builtin_def else {}
    base_esp = dict(builtin_def.get("esphome_controls") or {}) if builtin_def else {}
    if isinstance(raw.get("device_config"), dict):
        for k, v in raw["device_config"].items():
            if k in GROUP_BEHAVIOR_DEVICE_KEYS and v is not None:
                base_dev[k] = v
    if isinstance(raw.get("esphome_controls"), dict):
        for k, v in raw["esphome_controls"].items():
            if is_behavior_esphome_control(str(k)) and v is not None:
                base_esp[str(k)] = v
    return {
        "id": gid,
        "name": str((builtin_def["name"] if builtin_def else raw.get("name")) or gid),
        "description": str(
            (builtin_def["description"] if builtin_def else raw.get("description")) or ""
        ),
        "builtin": gid in _BUILTIN_GROUPS_BY_ID,
        "device_config": base_dev,
        "esphome_controls": base_esp,
    }


def get_device_groups(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return the normalized Device Groups list (each with its Tier 2 baseline) from Global System Config."""
    domain_data = hass.data.get(DOMAIN, {})
    global_cfg = domain_data.get(DATA_GLOBAL_CONFIG) or {}
    raw_groups = global_cfg.get(CONF_DEVICE_GROUPS)
    if not isinstance(raw_groups, list) or not raw_groups:
        return [_normalize_group_entry(g) for g in DEFAULT_DEVICE_GROUPS]

    by_id: dict[str, dict[str, Any]] = {}
    custom_order: list[str] = []
    for item in raw_groups:
        if not isinstance(item, dict):
            continue
        gid = str(item.get("id") or "").strip()
        if not gid or gid == "sensors":
            continue
        by_id[gid] = _normalize_group_entry(item)
        if gid not in _BUILTIN_GROUPS_BY_ID and gid not in custom_order:
            custom_order.append(gid)

    out: list[dict[str, Any]] = []
    for bdef in DEFAULT_DEVICE_GROUPS:
        bid = bdef["id"]
        out.append(by_id.get(bid) or _normalize_group_entry(bdef))
    for cid in custom_order:
        out.append(by_id[cid])
    return out


def compute_device_group_sync_status(
    hass: HomeAssistant,
    coordinator: Any,
    groups: list[dict[str, Any]] | None = None,
) -> str:
    """Return 'in_sync', 'customized', or 'unmanaged' comparing the device's Tier 2 settings to its Group baseline."""
    if getattr(coordinator, "is_ble_tag", False):
        return "unmanaged"
    grp_id = str(getattr(coordinator, "device_group", "") or DEFAULT_DEVICE_GROUP).strip()
    if not grp_id or grp_id == DEFAULT_DEVICE_GROUP:
        return "unmanaged"
    group_list = groups if groups is not None else get_device_groups(hass)
    grp = next((g for g in group_list if g.get("id") == grp_id), None)
    if grp is None:
        return "unmanaged"

    base_dev = grp.get("device_config") or {}
    base_esp = grp.get("esphome_controls") or {}
    if not base_dev and not base_esp:
        return "unmanaged"

    is_roaming = bool(getattr(coordinator, "is_roaming_device", True))
    dev_data = getattr(coordinator, "device_data", {}) or {}
    base_prof = str(base_dev.get("power_profile") or "").strip()
    cur_prof = resolve_device_pref_value(dev_data, "power_profile")
    prof_preset = POWER_PROFILE_PREFS.get(base_prof)
    for k, want_v in base_dev.items():
        if k not in GROUP_BEHAVIOR_DEVICE_KEYS:
            continue
        if k in (CONF_SYNC_DEVICE_AREA, CONF_AREA_FOLLOW_DWELL_S) and not is_roaming:
            continue
        spec = DEVICE_PREF_SPEC_MAP.get(k)
        if spec is not None:
            if not coordinator_supports_pref(coordinator, spec):
                continue
            if (
                prof_preset is not None
                and k in POWER_PROFILE_SUBKEYS
                and cur_prof == base_prof
                and _same_control_val(want_v, prof_preset.get(k))
            ):
                continue
            cur_v = resolve_device_pref_value(dev_data, k)
        else:
            cur_v = coordinator.get_opt(k)
        if isinstance(want_v, bool):
            if bool(cur_v) != want_v:
                return "customized"
        elif not _same_control_val(cur_v, want_v):
            return "customized"

    live_esp = capture_live_esphome_controls(
        hass, coordinator.esphome_device_id, behavior_only=True
    )
    if live_esp and base_esp:
        base_esp_prof = str(base_esp.get("select:power_profile") or "").strip()
        live_prof = str(live_esp.get("select:power_profile") or "").strip()
        prof_spec = POWER_PROFILE_SPECS.get(base_esp_prof)
        for ckey, want_val in base_esp.items():
            if ckey not in live_esp:
                continue
            if prof_spec is not None and ckey in prof_spec and live_prof == base_esp_prof:
                continue
            if not _same_control_val(live_esp[ckey], want_val):
                return "customized"

    return "in_sync"


def seed_group_baseline_from_coordinator(
    hass: HomeAssistant,
    group: dict[str, Any],
    coordinator: Any,
) -> dict[str, Any]:
    """Capture a Device's Operational Behavior settings into `group` as its new baseline."""
    dev_cfg: dict[str, Any] = {}
    dev_data = getattr(coordinator, "device_data", {}) or {}
    for k in GROUP_BEHAVIOR_DEVICE_KEYS:
        spec = DEVICE_PREF_SPEC_MAP.get(k)
        if spec is not None:
            if coordinator_supports_pref(coordinator, spec):
                dev_cfg[k] = resolve_device_pref_value(dev_data, k)
        else:
            val = coordinator.get_opt(k)
            if val is not None:
                dev_cfg[k] = val
    esp_ctrls = capture_live_esphome_controls(
        hass, coordinator.esphome_device_id, behavior_only=True
    )
    group["device_config"] = dev_cfg
    group["esphome_controls"] = esp_ctrls
    return group


def update_group_baseline_esphome_control(
    group: dict[str, Any],
    ckey: str,
    value: Any,
) -> bool:
    """Update a single Tier 2 ESPHome control in `group`'s baseline; return True if the baseline changed."""
    if not is_behavior_esphome_control(ckey):
        return False
    esp_ctrls = dict(group.get("esphome_controls") or {})
    if ckey == "select:power_profile":
        prof_name = str(value).strip()
        esp_ctrls["select:power_profile"] = prof_name
        spec = POWER_PROFILE_SPECS.get(prof_name)
        if spec is not None:
            esp_ctrls.update(spec)
    else:
        esp_ctrls[ckey] = value
        cur_prof = str(esp_ctrls.get("select:power_profile") or "").strip()
        spec = POWER_PROFILE_SPECS.get(cur_prof)
        if spec is not None and ckey in spec and not _same_control_val(value, spec[ckey]):
            esp_ctrls["select:power_profile"] = "Custom"
    if esp_ctrls == (group.get("esphome_controls") or {}):
        return False
    group["esphome_controls"] = esp_ctrls
    return True


async def async_apply_group_baseline_to_coordinators(
    hass: HomeAssistant,
    group: dict[str, Any],
    targets: list[Any],
) -> dict[str, int]:
    """Apply a Device Group's Tier 2 Operational Baseline across one or more target coordinators."""
    dev_cfg = group.get("device_config") or {}
    esp_ctrls = group.get("esphome_controls") or {}
    updated_devices = 0
    updated_controls = 0

    for coord in targets:
        if getattr(coord, "is_ble_tag", False):
            continue
        cur_data: dict[str, Any] = dict(coord.device_data)
        is_roaming = bool(getattr(coord, "is_roaming_device", True))
        updates: dict[str, Any] = {}
        for k in GROUP_BEHAVIOR_DEVICE_KEYS:
            if k not in dev_cfg or dev_cfg[k] is None:
                continue
            if k in (CONF_SYNC_DEVICE_AREA, CONF_AREA_FOLLOW_DWELL_S) and not is_roaming:
                continue
            spec = DEVICE_PREF_SPEC_MAP.get(k)
            if spec is not None:
                if not coordinator_supports_pref(coord, spec):
                    continue
                if resolve_device_pref_value(cur_data, k) != dev_cfg[k] or k not in cur_data:
                    updates[k] = dev_cfg[k]
            elif cur_data.get(k) != dev_cfg[k]:
                updates[k] = dev_cfg[k]
        if updates:
            cleaned = clean_device_settings(updates, current=cur_data)
            merged = {**cur_data, **(cleaned or updates)}
            if merged != cur_data:
                coord.update_device_config(merged)
                await coord.async_apply_options()
        coord.async_notify_listeners()
        updated_devices += 1
        if isinstance(esp_ctrls, dict) and esp_ctrls:
            updated_controls += await apply_esphome_controls_to_device(
                hass, coord.esphome_device_id, esp_ctrls
            )

    if updated_controls > 0:
        await asyncio.sleep(0.2)
        for coord in targets:
            coord.async_notify_listeners()

    return {
        "updated_devices": updated_devices,
        "updated_controls": updated_controls,
    }


# ---------------------------------------------------------------------------
# Device Reset Policy & Execution
# ---------------------------------------------------------------------------

DEVICE_IDENTITY_KEYS: tuple[str, ...] = (
    "esphome_device_id",
    "mac",
    "device_slug",
    "ma_player_entity",
)

BLE_TAG_IDENTITY_KEYS: tuple[str, ...] = (
    "device_slug",
    "ble_target_address",
)

FACTORY_RESET_MIN_SDK_REV = 2026110261

_FLAG_ERRORS: dict[str, str] = {
    "reset_nothing_selected": "Select what to reset: the device settings, the Latter options, or both.",
    "reset_ble_tag_has_no_device_settings": "A BLE tag has no device settings to reset. Reset only its Latter options.",
}


def reset_flags_error(
    device_settings: bool, latter_options: bool, *, is_ble_tag: bool
) -> str | None:
    """Return the translation key of the reason a reset request is invalid, or None if it's valid."""
    if not device_settings and not latter_options:
        return "reset_nothing_selected"
    if device_settings and is_ble_tag:
        return "reset_ble_tag_has_no_device_settings"
    return None


def reset_subentry_data(
    current: Mapping[str, Any],
    defaults: Mapping[str, Any],
    identity_keys: tuple[str, ...],
) -> dict[str, Any]:
    """Return the subentry data after a reset: the defaults, plus the identity keys from `current`."""
    out = {k: v for k, v in defaults.items() if k not in identity_keys}
    for key in identity_keys:
        if key in current:
            out[key] = current[key]
    return out


async def async_reset_device(
    hass: HomeAssistant,
    coordinator: LatterCoordinator,
    *,
    device_settings: bool = True,
    latter_options: bool = True,
) -> None:
    """Reset a Latter Device."""
    from .config_flow import ble_tag_option_defaults, device_option_defaults

    error_key = reset_flags_error(
        device_settings, latter_options, is_ble_tag=coordinator.is_ble_tag
    )
    if error_key is not None:
        raise ServiceValidationError(
            _FLAG_ERRORS[error_key],
            translation_domain=DOMAIN,
            translation_key=error_key,
        )

    reset_action: str | None = None
    if device_settings:
        reset_action = esphome_service(
            hass, coordinator.esphome_device_id, "latter_factory_reset"
        )
        if reset_action is None:
            raise ServiceValidationError(
                f"{coordinator.device_title} doesn't offer Reset to defaults. Update its firmware "
                f"to Latter SDK rev {FACTORY_RESET_MIN_SDK_REV} or later.",
                translation_domain=DOMAIN,
                translation_key="factory_reset_unsupported",
                translation_placeholders={
                    "device": coordinator.device_title,
                    "sdk_rev": str(FACTORY_RESET_MIN_SDK_REV),
                },
            )

    if latter_options:
        current = coordinator.device_data
        if coordinator.is_ble_tag:
            defaults = ble_tag_option_defaults(
                coordinator.device_slug, str(current.get(CONF_BLE_TARGET_ADDRESS) or "")
            )
            identity_keys = BLE_TAG_IDENTITY_KEYS
        else:
            defaults = device_option_defaults(
                hass,
                get_bound_esphome_device(hass, coordinator.esphome_device_id),
                coordinator.hardware_manifest,
            )
            identity_keys = DEVICE_IDENTITY_KEYS
        coordinator.update_device_config(
            reset_subentry_data(current, defaults, identity_keys)
        )
        await coordinator.async_apply_options()
        coordinator._bind_wallpaper_cycle_timer()
        coordinator.async_notify_listeners()
        _LOGGER.info("Reset the Latter options of '%s' to defaults", coordinator.device_slug)

    elif device_settings and not coordinator.is_ble_tag:
        stripped = {
            k: v for k, v in coordinator.device_data.items() if k not in DEVICE_PREF_KEYS
        }
        if stripped != coordinator.device_data:
            coordinator.update_device_config(stripped)
            coordinator.async_notify_listeners()

    if reset_action is not None:
        try:
            await hass.services.async_call("esphome", reset_action, {}, blocking=True)
        except HomeAssistantError as err:
            raise HomeAssistantError(
                f"{coordinator.device_title} didn't accept Reset to defaults: {err}",
                translation_domain=DOMAIN,
                translation_key="factory_reset_failed",
                translation_placeholders={
                    "device": coordinator.device_title,
                    "error": str(err),
                },
            ) from err
        _LOGGER.info(
            "Sent latter_factory_reset to '%s'; the device erases its saved settings and restarts",
            coordinator.device_slug,
        )
