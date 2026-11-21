"""Device Groups, group baselines, Studio entity classification, and Device reset for Latter."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import logging
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
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUPS,
    CONF_DEVICE_REMOTE_GROUP,
    CONF_DOCK_ITEMS,
    CONF_GAMES_ITEMS,
    CONF_HOME_CATEGORIES,
    CONF_NATIVE_BLE_TRACKING,
    CONF_PINNED_ITEMS,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_SECURITY_PIN_POLICY,
    CONF_SYNC_DEVICE_AREA,
    CONF_TOOLS_ITEMS,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    DATA_GLOBAL_CONFIG,
    DEFAULT_ACTIVITY_CARD,
    DEFAULT_ACTIVITY_SOURCES,
    DEFAULT_AREA_CATEGORIES,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_DEVICE_REMOTE_GROUP,
    DEFAULT_GAMES_ITEMS,
    DEFAULT_HOME_CATEGORIES,
    DEFAULT_SCREENSAVER_CYCLE_MINUTES,
    DEFAULT_SCREENSAVER_PHOTO_COLLECTION,
    DEFAULT_SCREENSAVER_PHOTO_MODE,
    DEFAULT_SCREENSAVER_SHUFFLE,
    DEFAULT_TOOLS_ITEMS,
    DEFAULT_WALLPAPER_COLLECTION,
    DEFAULT_WALLPAPER_CYCLE_MINUTES,
    DEFAULT_WALLPAPER_MODE,
    DOMAIN,
)
from .identity import (
    device_entities,
    esphome_node_name,
    esphome_service,
    get_bound_esphome_device,
)
from .studio.settings import (
    DEVICE_PREF_KEYS,
    DEVICE_PREF_SPEC_MAP,
    DEVICE_PREF_SPECS,
    DevicePrefSpec,
    clean_device_settings,
    default_dock_items,
    normalize_activity_sources,
    normalize_area_categories,
    normalize_dock_items,
    normalize_games_items,
    normalize_home_categories,
    normalize_pinned_items,
    normalize_tools_items,
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
        "voice",
        "Voice assistant",
        "Wake word models, microphone mute, and voice detection sensitivity.",
    ),
    (
        "music",
        "Music & media",
        "Media player entity and library, artist, album, and podcast sorting options.",
    ),
    (
        "battery",
        "Battery & power",
        "Battery charge level, charging status, PMIC voltage, and internal temperature.",
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
        "actions",
        "Device actions",
        "One-tap restart, hibernate, refresh, and maintenance triggers.",
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
        return "actions", None

    if domain == "media_player":
        return "music", None

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
        "node_name": esphome_node_name(hass, target_device_id) or device_slug,
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
# Device Groups & Hardware Baselines
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
    if cap == "hw_jpeg":
        return bool(getattr(coordinator, "has_display", True)) and bool(
            getattr(coordinator, "supports_hw_jpeg", False)
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


# Operational Behavior keys synced automatically by every Device Group's baseline.
GROUP_BEHAVIOR_DEVICE_KEYS: tuple[str, ...] = (
    CONF_NATIVE_BLE_TRACKING,
    CONF_BLE_AUTO_SWITCH,
    CONF_SYNC_DEVICE_AREA,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_AREA_HANDOFF,
    CONF_SECURITY_PIN_POLICY,
    *tuple(s.key for s in DEVICE_PREF_SPECS if s.group_tier == "behavior"),
)

# Optional Display styling keys synced when a Group opts into `include_display`.
GROUP_DISPLAY_DEVICE_KEYS: tuple[str, ...] = (
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_DEVICE_CUSTOM_COLOR,
    *tuple(s.key for s in DEVICE_PREF_SPECS if s.group_tier == "display"),
)

GROUP_INTERFACE_NON_PREF_KEYS: tuple[str, ...] = (
    CONF_DOCK_ITEMS,
    CONF_PINNED_ITEMS,
    CONF_AREA_CATEGORIES,
    CONF_HOME_CATEGORIES,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_CAMERA_VISIBLE_ENTITIES,
    CONF_CAMERA_CAROUSEL_ENTITIES,
    CONF_TOOLS_ITEMS,
    CONF_GAMES_ITEMS,
    CONF_ACTIVITY_CARD,
    CONF_ACTIVITY_SOURCES,
    CONF_DEVICE_REMOTE_GROUP,
)

# Optional Interface & Shortcut keys synced when a Group opts into `include_interface`.
GROUP_INTERFACE_DEVICE_KEYS: tuple[str, ...] = (
    *GROUP_INTERFACE_NON_PREF_KEYS,
    *tuple(s.key for s in DEVICE_PREF_SPECS if s.group_tier == "interface"),
)

GROUP_APPEARANCE_DEVICE_KEYS: tuple[str, ...] = (
    *GROUP_DISPLAY_DEVICE_KEYS,
    *GROUP_INTERFACE_DEVICE_KEYS,
)

GROUP_ALL_DEVICE_KEYS: tuple[str, ...] = (
    *GROUP_BEHAVIOR_DEVICE_KEYS,
    *GROUP_DISPLAY_DEVICE_KEYS,
    *GROUP_INTERFACE_DEVICE_KEYS,
)

_DISPLAY_CAPABILITY_NON_PREF_KEYS: frozenset[str] = frozenset(
    {
        CONF_WALLPAPER_MODE,
        CONF_WALLPAPER_SOURCE,
        CONF_WALLPAPER_COLLECTION,
        CONF_WALLPAPER_CYCLE_MINUTES,
        CONF_SCREENSAVER_PHOTO_MODE,
        CONF_SCREENSAVER_PHOTO_SOURCE,
        CONF_SCREENSAVER_PHOTO_COLLECTION,
        CONF_SCREENSAVER_CYCLE_MINUTES,
        CONF_SCREENSAVER_SHUFFLE,
        CONF_DEVICE_CUSTOM_COLOR,
        *GROUP_INTERFACE_NON_PREF_KEYS,
    }
)


def active_group_keys(group: Mapping[str, Any]) -> tuple[str, ...]:
    """Return the baseline keys actively enforced by `group` based on its scope flags."""
    keys: list[str] = list(GROUP_BEHAVIOR_DEVICE_KEYS)
    if bool(group.get("include_display", False)):
        keys.extend(GROUP_DISPLAY_DEVICE_KEYS)
    if bool(group.get("include_interface", False)):
        keys.extend(GROUP_INTERFACE_DEVICE_KEYS)
    return tuple(keys)


def coordinator_supports_group_key(coordinator: Any, key: str) -> bool:
    """Return True when `coordinator`'s hardware supports group/batch setting `key`."""
    if getattr(coordinator, "is_ble_tag", False):
        return False
    if key in (CONF_SYNC_DEVICE_AREA, CONF_AREA_FOLLOW_DWELL_S) and not bool(
        getattr(coordinator, "is_roaming_device", True)
    ):
        return False
    if key in _DISPLAY_CAPABILITY_NON_PREF_KEYS:
        return bool(getattr(coordinator, "has_display", True))
    spec = DEVICE_PREF_SPEC_MAP.get(key)
    if spec is not None:
        return coordinator_supports_pref(coordinator, spec)
    return True


def default_group_baseline_config(
    *,
    include_display: bool = False,
    include_interface: bool = False,
) -> dict[str, Any]:
    """Return the canonical baseline dictionary for a Device Group."""
    base: dict[str, Any] = {
        CONF_NATIVE_BLE_TRACKING: False,
        CONF_BLE_AUTO_SWITCH: False,
        CONF_SYNC_DEVICE_AREA: False,
        CONF_AREA_FOLLOW_DWELL_S: 10,
        CONF_AREA_HANDOFF: False,
        CONF_SECURITY_PIN_POLICY: "auto",
    }
    for spec in DEVICE_PREF_SPECS:
        if spec.group_tier == "behavior":
            base[spec.key] = spec.default
    if include_display:
        base[CONF_WALLPAPER_MODE] = DEFAULT_WALLPAPER_MODE
        base[CONF_WALLPAPER_SOURCE] = ""
        base[CONF_WALLPAPER_COLLECTION] = DEFAULT_WALLPAPER_COLLECTION
        base[CONF_WALLPAPER_CYCLE_MINUTES] = DEFAULT_WALLPAPER_CYCLE_MINUTES
        base[CONF_SCREENSAVER_PHOTO_MODE] = DEFAULT_SCREENSAVER_PHOTO_MODE
        base[CONF_SCREENSAVER_PHOTO_SOURCE] = ""
        base[CONF_SCREENSAVER_PHOTO_COLLECTION] = DEFAULT_SCREENSAVER_PHOTO_COLLECTION
        base[CONF_SCREENSAVER_CYCLE_MINUTES] = DEFAULT_SCREENSAVER_CYCLE_MINUTES
        base[CONF_SCREENSAVER_SHUFFLE] = DEFAULT_SCREENSAVER_SHUFFLE
        base[CONF_DEVICE_CUSTOM_COLOR] = "#3898FF"
        for spec in DEVICE_PREF_SPECS:
            if spec.group_tier == "display":
                base[spec.key] = spec.default
    if include_interface:
        base[CONF_DOCK_ITEMS] = default_dock_items()
        base[CONF_PINNED_ITEMS] = []
        base[CONF_AREA_CATEGORIES] = DEFAULT_AREA_CATEGORIES
        base[CONF_HOME_CATEGORIES] = DEFAULT_HOME_CATEGORIES
        base[CONF_BROADCAST_SPEAKER_ENTITIES] = []
        base[CONF_CAMERA_VISIBLE_ENTITIES] = []
        base[CONF_CAMERA_CAROUSEL_ENTITIES] = []
        base[CONF_TOOLS_ITEMS] = DEFAULT_TOOLS_ITEMS
        base[CONF_GAMES_ITEMS] = DEFAULT_GAMES_ITEMS
        base[CONF_ACTIVITY_CARD] = DEFAULT_ACTIVITY_CARD
        base[CONF_ACTIVITY_SOURCES] = DEFAULT_ACTIVITY_SOURCES
        base[CONF_DEVICE_REMOTE_GROUP] = DEFAULT_DEVICE_REMOTE_GROUP
        for spec in DEVICE_PREF_SPECS:
            if spec.group_tier == "interface":
                base[spec.key] = spec.default
    return base


def resolve_behavior_key_value(data: Mapping[str, Any], key: str) -> Any:
    """Resolve the effective normalized value for any group/batch `key` from `data`."""
    spec = DEVICE_PREF_SPEC_MAP.get(key)
    if spec is not None:
        return resolve_device_pref_value(data, key)
    if key == CONF_NATIVE_BLE_TRACKING:
        return bool(data.get(CONF_NATIVE_BLE_TRACKING, False))
    if key == CONF_BLE_AUTO_SWITCH:
        return bool(
            data.get(
                CONF_BLE_AUTO_SWITCH,
                bool(data.get(CONF_NATIVE_BLE_TRACKING, False)),
            )
        )
    if key == CONF_SYNC_DEVICE_AREA:
        return bool(data.get(CONF_SYNC_DEVICE_AREA, False))
    if key == CONF_AREA_FOLLOW_DWELL_S:
        try:
            val = int(data.get(CONF_AREA_FOLLOW_DWELL_S, 10))
        except (TypeError, ValueError):
            val = 10
        return max(3, min(60, val))
    if key == CONF_AREA_HANDOFF:
        return bool(data.get(CONF_AREA_HANDOFF, False))
    if key == CONF_SECURITY_PIN_POLICY:
        pol = str(data.get(CONF_SECURITY_PIN_POLICY) or "auto").strip().lower()
        return pol if pol in ("auto", "allow", "require_pin", "block") else "auto"
    if key == CONF_WALLPAPER_MODE:
        raw_wm = str(data.get(CONF_WALLPAPER_MODE) or "").strip().lower()
        if raw_wm in ("off", "single", "collection", "custom"):
            return raw_wm
        return "single" if str(data.get(CONF_WALLPAPER_SOURCE) or "").strip() else DEFAULT_WALLPAPER_MODE
    if key == CONF_WALLPAPER_SOURCE:
        return str(data.get(CONF_WALLPAPER_SOURCE) or "").strip()
    if key == CONF_WALLPAPER_COLLECTION:
        return str(data.get(CONF_WALLPAPER_COLLECTION) or DEFAULT_WALLPAPER_COLLECTION).strip()
    if key == CONF_WALLPAPER_CYCLE_MINUTES:
        try:
            return max(
                0,
                int(
                    data.get(
                        CONF_WALLPAPER_CYCLE_MINUTES, DEFAULT_WALLPAPER_CYCLE_MINUTES
                    )
                    or 0
                ),
            )
        except (TypeError, ValueError):
            return 0
    if key == CONF_SCREENSAVER_PHOTO_MODE:
        raw_sm = str(data.get(CONF_SCREENSAVER_PHOTO_MODE) or "").strip().lower()
        return raw_sm if raw_sm in ("off", "single", "collection", "custom") else DEFAULT_SCREENSAVER_PHOTO_MODE
    if key == CONF_SCREENSAVER_PHOTO_SOURCE:
        return str(data.get(CONF_SCREENSAVER_PHOTO_SOURCE) or "").strip()
    if key == CONF_SCREENSAVER_PHOTO_COLLECTION:
        return str(
            data.get(CONF_SCREENSAVER_PHOTO_COLLECTION, DEFAULT_SCREENSAVER_PHOTO_COLLECTION)
            or DEFAULT_SCREENSAVER_PHOTO_COLLECTION
        ).strip()
    if key == CONF_SCREENSAVER_CYCLE_MINUTES:
        try:
            return max(
                0,
                int(
                    data.get(
                        CONF_SCREENSAVER_CYCLE_MINUTES, DEFAULT_SCREENSAVER_CYCLE_MINUTES
                    )
                ),
            )
        except (TypeError, ValueError):
            return DEFAULT_SCREENSAVER_CYCLE_MINUTES
    if key == CONF_SCREENSAVER_SHUFFLE:
        raw_sh = data.get(CONF_SCREENSAVER_SHUFFLE, DEFAULT_SCREENSAVER_SHUFFLE)
        if isinstance(raw_sh, str):
            return raw_sh.strip().lower() in ("1", "true", "on", "yes")
        return bool(raw_sh)
    if key == CONF_DEVICE_CUSTOM_COLOR:
        raw_c = str(data.get(CONF_DEVICE_CUSTOM_COLOR) or "").strip().upper()
        return raw_c if raw_c.startswith("#") and len(raw_c) == 7 else "#3898FF"
    if key == CONF_DOCK_ITEMS:
        return normalize_dock_items(data.get(CONF_DOCK_ITEMS), strict=False)
    if key == CONF_PINNED_ITEMS:
        return normalize_pinned_items(data.get(CONF_PINNED_ITEMS), strict=False)
    if key == CONF_AREA_CATEGORIES:
        try:
            return normalize_area_categories(
                data.get(CONF_AREA_CATEGORIES, DEFAULT_AREA_CATEGORIES)
            )
        except ValueError:
            return DEFAULT_AREA_CATEGORIES
    if key == CONF_HOME_CATEGORIES:
        try:
            return normalize_home_categories(
                data.get(CONF_HOME_CATEGORIES, DEFAULT_HOME_CATEGORIES)
            )
        except ValueError:
            return DEFAULT_HOME_CATEGORIES
    if key == CONF_BROADCAST_SPEAKER_ENTITIES:
        raw_spks = data.get(key)
        if not isinstance(raw_spks, (list, tuple)):
            return []
        cleaned_spks: list[str] = []
        for item in raw_spks:
            sid = str(item or "").strip()
            if sid.startswith("media_player.") and sid not in cleaned_spks:
                cleaned_spks.append(sid)
        return cleaned_spks[:32]
    if key in (CONF_CAMERA_VISIBLE_ENTITIES, CONF_CAMERA_CAROUSEL_ENTITIES):
        raw_cams = data.get(key)
        if not isinstance(raw_cams, (list, tuple)):
            return []
        cleaned_cams: list[str] = []
        for item in raw_cams:
            cid = str(item or "").strip()
            if cid.startswith("camera.") and cid not in cleaned_cams:
                cleaned_cams.append(cid)
        return cleaned_cams[:10]
    if key == CONF_TOOLS_ITEMS:
        try:
            return normalize_tools_items(
                data.get(CONF_TOOLS_ITEMS, DEFAULT_TOOLS_ITEMS)
            )
        except ValueError:
            return DEFAULT_TOOLS_ITEMS
    if key == CONF_GAMES_ITEMS:
        try:
            return normalize_games_items(
                data.get(CONF_GAMES_ITEMS, DEFAULT_GAMES_ITEMS)
            )
        except ValueError:
            return DEFAULT_GAMES_ITEMS
    if key == CONF_ACTIVITY_CARD:
        raw_ac = data.get(CONF_ACTIVITY_CARD, DEFAULT_ACTIVITY_CARD)
        if isinstance(raw_ac, str):
            return raw_ac.strip().lower() in ("1", "true", "on", "yes")
        return bool(raw_ac)
    if key == CONF_ACTIVITY_SOURCES:
        try:
            return normalize_activity_sources(
                data.get(CONF_ACTIVITY_SOURCES, DEFAULT_ACTIVITY_SOURCES)
            )
        except ValueError:
            return DEFAULT_ACTIVITY_SOURCES
    if key == CONF_DEVICE_REMOTE_GROUP:
        return (
            str(data.get(CONF_DEVICE_REMOTE_GROUP) or DEFAULT_DEVICE_REMOTE_GROUP).strip()
            or DEFAULT_DEVICE_REMOTE_GROUP
        )
    return data.get(key)


BUILTIN_GROUP_PRESET_VERSION = 4
CONF_BUILTIN_GROUP_PRESET_VERSION = "builtin_group_preset_version"

DEFAULT_DEVICE_GROUPS: list[dict[str, Any]] = [
    {
        "id": "pocket_carry",
        "name": "Pocket Carry",
        "description": "Compact pocket-carried displays with docked-only tap/wake-word, pickup wake disabled, and 15 min battery hibernate",
        "builtin": True,
        "preset_version": BUILTIN_GROUP_PRESET_VERSION,
        "include_display": False,
        "include_interface": False,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "tap_to_wake": "Docked Only",
            "pickup_to_wake": "Disabled",
            "battery_screen_timeout": "30s",
            "docked_idle_timeout": "1 min",
            "battery_hibernate_timeout": "15 min",
            "screensaver_mode": "Docked Only",
            "wake_word_mode": "Docked Only",
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": 90,
            "night_brightness": 35,
            "bedtime_brightness": 15,
            "ble_beacon_mode": "Handheld + Screen Off",
        },
    },
    {
        "id": "handhelds",
        "name": "Handhelds",
        "description": "Battery-powered roaming displays with pickup and single-tap wake",
        "builtin": True,
        "preset_version": BUILTIN_GROUP_PRESET_VERSION,
        "include_display": False,
        "include_interface": False,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "tap_to_wake": "Single Tap",
            "pickup_to_wake": "Always On",
            "battery_screen_timeout": "30s",
            "docked_idle_timeout": "1 min",
            "battery_hibernate_timeout": "30 min",
            "screensaver_mode": "Docked Only",
            "wake_word_mode": "Docked Only",
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": 90,
            "night_brightness": 35,
            "bedtime_brightness": 15,
            "ble_beacon_mode": "Handheld + Screen Off",
        },
    },
    {
        "id": "wearables",
        "name": "Wearables",
        "description": "Compact wearable displays with double-tap wake on battery and 15s screen timeout",
        "builtin": True,
        "preset_version": BUILTIN_GROUP_PRESET_VERSION,
        "include_display": False,
        "include_interface": False,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: True,
            CONF_BLE_AUTO_SWITCH: True,
            CONF_SYNC_DEVICE_AREA: True,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "tap_to_wake": "Double Tap",
            "pickup_to_wake": "Always On",
            "battery_screen_timeout": "15s",
            "docked_idle_timeout": "1 min",
            "battery_hibernate_timeout": "15 min",
            "screensaver_mode": "Docked Only",
            "wake_word_mode": "Docked Only",
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": 80,
            "night_brightness": 25,
            "bedtime_brightness": 15,
            "ble_beacon_mode": "Handheld + Screen Off",
        },
    },
    {
        "id": "wall_panels",
        "name": "Wall & Desk Panels",
        "description": "Stationary mains-powered panels with always-on Home screen, Always-On wake word, and no battery hibernate",
        "builtin": True,
        "preset_version": BUILTIN_GROUP_PRESET_VERSION,
        "include_display": False,
        "include_interface": False,
        "device_config": {
            CONF_NATIVE_BLE_TRACKING: False,
            CONF_BLE_AUTO_SWITCH: False,
            CONF_SYNC_DEVICE_AREA: False,
            CONF_AREA_FOLLOW_DWELL_S: 10,
            CONF_AREA_HANDOFF: False,
            "tap_to_wake": "Single Tap",
            "pickup_to_wake": "Disabled",
            "battery_screen_timeout": "Never",
            "docked_idle_timeout": "Never",
            "battery_hibernate_timeout": "Disabled",
            "screensaver_mode": "Never",
            "wake_word_mode": "Always On",
            "auto_brightness_mode": "Sun Synchronized",
            "day_brightness": 90,
            "night_brightness": 35,
            "bedtime_brightness": 15,
            "ble_beacon_mode": "Handheld Only",
        },
    },
]

_BUILTIN_GROUPS_BY_ID: dict[str, dict[str, Any]] = {
    g["id"]: g for g in DEFAULT_DEVICE_GROUPS
}


def _same_control_val(a: Any, b: Any) -> bool:
    """Compare two control values, treating structured lists, numeric strings, and booleans consistently."""
    if isinstance(a, (list, dict)) or isinstance(b, (list, dict)):
        return a == b
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


def _normalize_group_entry(raw: Mapping[str, Any] | dict[str, Any]) -> dict[str, Any]:
    """Normalize a single Device Group entry onto a complete baseline dictionary."""
    gid = str(raw.get("id") or "").strip()
    builtin_def = _BUILTIN_GROUPS_BY_ID.get(gid)
    include_display = bool(
        raw.get(
            "include_display",
            builtin_def.get("include_display", False) if builtin_def else False,
        )
    )
    include_interface = bool(
        raw.get(
            "include_interface",
            builtin_def.get("include_interface", False) if builtin_def else False,
        )
    )
    base_dev = default_group_baseline_config(
        include_display=include_display,
        include_interface=include_interface,
    )
    if builtin_def and isinstance(builtin_def.get("device_config"), dict):
        base_dev.update(builtin_def["device_config"])
    if isinstance(raw.get("device_config"), dict):
        for k, v in raw["device_config"].items():
            if k in GROUP_ALL_DEVICE_KEYS and v is not None:
                base_dev[k] = v
    out_entry: dict[str, Any] = {
        "id": gid,
        "name": str((builtin_def["name"] if builtin_def else raw.get("name")) or gid),
        "description": str(
            (builtin_def["description"] if builtin_def else raw.get("description")) or ""
        ),
        "builtin": gid in _BUILTIN_GROUPS_BY_ID,
        "include_display": include_display,
        "include_interface": include_interface,
        "device_config": base_dev,
    }
    if builtin_def is not None:
        out_entry["preset_version"] = BUILTIN_GROUP_PRESET_VERSION
    return out_entry


def reset_builtin_group_entry(group_id: str) -> dict[str, Any] | None:
    """Return a freshly normalized default baseline for built-in `group_id`, or None if custom."""
    bdef = _BUILTIN_GROUPS_BY_ID.get(str(group_id or "").strip())
    if bdef is None:
        return None
    return _normalize_group_entry(bdef)


def upgrade_stored_builtin_groups(global_cfg: dict[str, Any]) -> bool:
    """Refresh stored built-in groups when `builtin_group_preset_version` advances; preserve custom groups."""
    if global_cfg.get(CONF_BUILTIN_GROUP_PRESET_VERSION) == BUILTIN_GROUP_PRESET_VERSION:
        return False
    raw_groups = global_cfg.get(CONF_DEVICE_GROUPS)
    if isinstance(raw_groups, list) and raw_groups:
        custom_entries: list[dict[str, Any]] = []
        seen_custom: set[str] = set()
        for item in raw_groups:
            if not isinstance(item, dict):
                continue
            gid = str(item.get("id") or "").strip()
            if not gid or gid == DEFAULT_DEVICE_GROUP or gid in _BUILTIN_GROUPS_BY_ID:
                continue
            if item.get("builtin") is True:
                continue
            if gid not in seen_custom:
                seen_custom.add(gid)
                custom_entries.append(_normalize_group_entry(item))
        global_cfg[CONF_DEVICE_GROUPS] = [
            _normalize_group_entry(g) for g in DEFAULT_DEVICE_GROUPS
        ] + custom_entries
    global_cfg[CONF_BUILTIN_GROUP_PRESET_VERSION] = BUILTIN_GROUP_PRESET_VERSION
    return True


async def async_sync_coordinators_to_builtin_presets(
    hass: HomeAssistant,
    coordinators: Iterable[Any],
) -> int:
    """Sync Devices currently assigned to built-in groups onto upgraded built-in baselines once on version bump."""
    groups_by_id = {
        g["id"]: g for g in get_device_groups(hass) if g.get("id") in _BUILTIN_GROUPS_BY_ID
    }
    synced_total = 0
    for gid, grp in groups_by_id.items():
        matching = [
            c
            for c in coordinators
            if not getattr(c, "is_ble_tag", False)
            and str((getattr(c, "device_data", {}) or {}).get("device_group") or "").strip()
            == gid
        ]
        if matching:
            res = await async_apply_group_baseline_to_coordinators(hass, grp, matching)
            synced_total += int(res.get("updated_devices", 0))
    return synced_total


def get_device_groups(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return the normalized named Device Groups list from Global System Config."""
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
        if not gid or gid == DEFAULT_DEVICE_GROUP:
            continue
        if item.get("builtin") is True and gid not in _BUILTIN_GROUPS_BY_ID:
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


def device_matches_group_baseline(
    hass: HomeAssistant,
    coordinator: Any,
    groups: list[dict[str, Any]] | None = None,
    *,
    group_id: str | None = None,
    candidate_data: Mapping[str, Any] | None = None,
) -> bool:
    """Return True when `coordinator` (or `candidate_data`) matches all active keys of `group_id`."""
    if getattr(coordinator, "is_ble_tag", False):
        return False
    dev_data: Mapping[str, Any] = (
        candidate_data
        if candidate_data is not None
        else (getattr(coordinator, "device_data", {}) or {})
    )
    grp_id = str(
        group_id
        if group_id is not None
        else (dev_data.get("device_group") or getattr(coordinator, "_raw_device_group", "") or DEFAULT_DEVICE_GROUP)
    ).strip()
    if not grp_id or grp_id == DEFAULT_DEVICE_GROUP:
        return False
    group_list = groups if groups is not None else get_device_groups(hass)
    grp = next((g for g in group_list if g.get("id") == grp_id), None)
    if grp is None:
        return False

    base_dev = grp.get("device_config") or {}
    if not base_dev:
        return False

    enforced_keys = set(active_group_keys(grp))
    is_round = bool(getattr(coordinator, "is_round_display", True))
    for k in enforced_keys:
        if k not in base_dev or base_dev[k] is None:
            continue
        if not coordinator_supports_group_key(coordinator, k):
            continue
        want_v = base_dev[k]
        if k == "clock_face" and want_v == "Modern Analog" and not is_round:
            want_v = "Minimal Digital"
        cur_v = resolve_behavior_key_value(dev_data, k)
        if k == CONF_WALLPAPER_SOURCE and candidate_data is None:
            cur_v = str(
                getattr(coordinator, "configured_wallpaper_source", cur_v) or ""
            ).strip()
        if isinstance(want_v, bool):
            if bool(cur_v) != want_v:
                return False
        elif not _same_control_val(cur_v, want_v):
            return False

    return True


def resolve_effective_device_group(
    hass: HomeAssistant,
    coordinator: Any,
    groups: list[dict[str, Any]] | None = None,
    *,
    candidate_data: Mapping[str, Any] | None = None,
) -> str:
    """Return the Device's effective group ID, switching to `'custom'` if unknown or diverged from baseline."""
    if getattr(coordinator, "is_ble_tag", False):
        return ""
    dev_data: Mapping[str, Any] = (
        candidate_data
        if candidate_data is not None
        else (getattr(coordinator, "device_data", {}) or {})
    )
    raw_grp = str(dev_data.get("device_group") or DEFAULT_DEVICE_GROUP).strip()
    if not raw_grp or raw_grp == DEFAULT_DEVICE_GROUP:
        return DEFAULT_DEVICE_GROUP
    if raw_grp in ("pocket_carry", "handhelds", "wearables") and not bool(
        getattr(coordinator, "has_display", True)
    ):
        return DEFAULT_DEVICE_GROUP
    group_list = groups if groups is not None else get_device_groups(hass)
    if not device_matches_group_baseline(
        hass,
        coordinator,
        group_list,
        group_id=raw_grp,
        candidate_data=dev_data,
    ):
        return DEFAULT_DEVICE_GROUP
    return raw_grp


def seed_group_baseline_from_coordinator(
    hass: HomeAssistant,
    group: dict[str, Any],
    coordinator: Any,
    *,
    only_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Capture a Device's settings into `group` as its baseline (all supported keys or `only_keys`)."""
    inc_disp = bool(group.get("include_display", False))
    inc_iface = bool(group.get("include_interface", False))
    dev_cfg = default_group_baseline_config(
        include_display=inc_disp,
        include_interface=inc_iface,
    )
    existing_cfg = group.get("device_config")
    if isinstance(existing_cfg, dict):
        for k, v in existing_cfg.items():
            if k in GROUP_ALL_DEVICE_KEYS and v is not None:
                dev_cfg[k] = v
    dev_data = getattr(coordinator, "device_data", {}) or {}
    keys_to_copy = (
        tuple(k for k in only_keys if k in GROUP_ALL_DEVICE_KEYS)
        if only_keys is not None
        else active_group_keys(group)
    )
    for k in keys_to_copy:
        if not coordinator_supports_group_key(coordinator, k):
            continue
        if k == CONF_WALLPAPER_SOURCE:
            dev_cfg[k] = str(
                getattr(
                    coordinator,
                    "configured_wallpaper_source",
                    resolve_behavior_key_value(dev_data, k),
                )
                or ""
            ).strip()
        elif k == CONF_DEVICE_CUSTOM_COLOR:
            dev_cfg[k] = str(
                getattr(
                    coordinator,
                    "device_custom_color",
                    resolve_behavior_key_value(dev_data, k),
                )
                or "#3898FF"
            ).strip().upper()
        else:
            dev_cfg[k] = resolve_behavior_key_value(dev_data, k)
    group["device_config"] = dev_cfg
    return group


async def async_apply_group_baseline_to_coordinators(
    hass: HomeAssistant,
    group: dict[str, Any],
    targets: list[Any],
) -> dict[str, int]:
    """Apply a Device Group's active baseline across one or more target coordinators."""
    dev_cfg = group.get("device_config") or {}
    grp_id = str(group.get("id") or "").strip()
    enforced_keys = active_group_keys(group)
    updated_devices = 0

    for coord in targets:
        if getattr(coord, "is_ble_tag", False):
            continue
        cur_data: dict[str, Any] = dict(coord.device_data)
        is_round = bool(getattr(coord, "is_round_display", True))
        updates: dict[str, Any] = {}
        for k in enforced_keys:
            if k not in dev_cfg or dev_cfg[k] is None:
                continue
            if not coordinator_supports_group_key(coord, k):
                continue
            want_v = dev_cfg[k]
            if k == "clock_face" and want_v == "Modern Analog" and not is_round:
                want_v = "Minimal Digital"
            cur_v = resolve_behavior_key_value(cur_data, k)
            if k == CONF_WALLPAPER_SOURCE:
                cur_v = str(
                    getattr(coord, "configured_wallpaper_source", cur_v) or ""
                ).strip()
            if not _same_control_val(cur_v, want_v) or k not in cur_data:
                updates[k] = want_v
        cleaned = (
            clean_device_settings(
                updates,
                current=cur_data,
                is_round_display=is_round,
                supports_hw_jpeg=bool(getattr(coord, "supports_hw_jpeg", False)),
            )
            if updates
            else {}
        )
        merged = {**cur_data, **(cleaned or updates)}
        if grp_id and grp_id != DEFAULT_DEVICE_GROUP:
            merged["device_group"] = grp_id
        wp_override = CONF_WALLPAPER_SOURCE in cleaned
        if merged != cur_data or wp_override:
            if wp_override:
                wp_val = str(merged.get(CONF_WALLPAPER_SOURCE) or "").strip()
                coord.current_wallpaper = wp_val
                coord._configured_wallpaper_source = wp_val
            coord.update_device_config(merged, preserve_group=True)
            await coord.async_apply_options()
            if hasattr(coord, "_bind_wallpaper_cycle_timer"):
                coord._bind_wallpaper_cycle_timer()
            if hasattr(coord, "_bind_screensaver_cycle_timer"):
                coord._bind_screensaver_cycle_timer()
        if hasattr(coord, "async_update_listeners"):
            coord.async_update_listeners()
        coord.async_notify_listeners()
        updated_devices += 1

    return {
        "updated_devices": updated_devices,
        "updated_controls": 0,
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
        coordinator._bind_screensaver_cycle_timer()
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
