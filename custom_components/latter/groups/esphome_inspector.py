"""ESPHome entity section classification and bound-device entity inspection for Latter Studio (`L2a`)."""

from __future__ import annotations

from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify

from ..areas.registry import apply_ha_display_precision
from ..identity import device_entities, esphome_node_name, get_bound_esphome_device

_apply_ha_display_precision = apply_ha_display_precision

ASSIST_SATELLITE_TRANSLATION_KEYS: Final[frozenset[str]] = frozenset(
    {"pipeline", "pipeline_n", "vad_sensitivity", "wake_word", "wake_word_n"}
)

DEVELOPER_ENTITY_KEYWORDS: Final[tuple[str, ...]] = (
    "telemetry_profiler",
    "log_memory",
    "memory_report",
    "ram_low_water",
    "ram_largest_block",
    "psram_low_water",
    "weather_sim",
    "weather_simulation",
)

_BATTERY_KEYWORDS: Final[tuple[str, ...]] = (
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

_NETWORK_KEYWORDS: Final[tuple[str, ...]] = (
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

UNIVERSAL_SECTION_META: Final[tuple[tuple[str, str, str], ...]] = (
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

_DOMAIN_SORT_ORDER: Final[dict[str, int]] = {
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
_DEFAULT_DOMAIN_RANK: Final = 50


def _classify_by_domain_and_keywords(
    domain: str,
    dev_cls: str,
    entity_category: str | None,
    clean_low: str,
    ent_suffix: str,
) -> str:
    if any(k in clean_low or k in ent_suffix for k in DEVELOPER_ENTITY_KEYWORDS):
        return "developer"
    if domain == "button" or dev_cls in ("restart", "identify"):
        return "actions"
    if domain == "media_player":
        return "music"
    if dev_cls in ("battery", "voltage", "current", "power", "energy") or any(
        k in clean_low or k in ent_suffix for k in _BATTERY_KEYWORDS
    ):
        return "battery"
    if (
        domain == "update"
        or dev_cls in ("signal_strength", "timestamp", "duration")
        or entity_category == "diagnostic"
        or any(k in clean_low or k in ent_suffix for k in _NETWORK_KEYWORDS)
    ):
        return "network"
    return "other"


def classify_esphome_entity_section(  # noqa: PLR0913, PLR0917
    entity_id: str,
    friendly_name: str,
    domain: str,
    device_class: str,
    entity_category: str | None,
    translation_key: str | None = None,
    device_object_prefixes: tuple[str, ...] = (),
) -> tuple[str, str | None]:
    """Classify an ESPHome entity into a focused section; returns `(section_id, None)`."""
    if domain == "assist_satellite" or (
        domain == "select" and (translation_key or "") in ASSIST_SATELLITE_TRANSLATION_KEYS
    ):
        return "voice", None

    ent_suffix = entity_id.split(".", 1)[-1].lower()
    for prefix in device_object_prefixes:
        if prefix and ent_suffix.startswith(prefix + "_"):
            ent_suffix = ent_suffix[len(prefix) + 1 :]
            break

    sec_id = _classify_by_domain_and_keywords(
        domain,
        device_class.lower(),
        entity_category,
        friendly_name.strip().lower(),
        ent_suffix,
    )
    return sec_id, None


def present_section_ids(sections: object) -> set[str]:
    """Return the IDs of the Device's entity sections that hold at least one entity."""
    if not isinstance(sections, (list, tuple)):
        return set()
    return {
        str(sec.get("id"))
        for sec in sections
        if isinstance(sec, dict) and sec.get("id") and sec.get("items")
    }


def _build_esphome_device_meta(
    hass: HomeAssistant, target_device_id: str | None, device_slug: str
) -> dict[str, str]:
    dev_meta: dict[str, str] = {
        "device_id": target_device_id or "",
        "name": device_slug,
        "node_name": esphome_node_name(hass, target_device_id) or device_slug,
        "model": "ESPHome Node",
        "manufacturer": "ESPHome",
        "sw_version": "",
        "mac": "",
    }
    if target_device_id and isinstance(
        dev := dr.async_get(hass).async_get(target_device_id), dr.DeviceEntry
    ):
        dev_meta["name"] = str(dev.name_by_user or dev.name or device_slug)
        dev_meta["model"] = str(dev.model or "ESPHome Node")
        dev_meta["manufacturer"] = str(dev.manufacturer or "ESPHome")
        dev_meta["sw_version"] = str(dev.sw_version or "")
        for _ctype, cval in dev.connections:
            dev_meta["mac"] = str(cval)
            break
    return dev_meta


def _format_entity_item(
    hass: HomeAssistant,
    entry: er.RegistryEntry,
    *,
    dev_prefix: str,
    slug_words: str,
    object_prefixes: tuple[str, ...],
) -> tuple[str, dict[str, Any]]:
    state_obj = hass.states.get(entry.entity_id)
    state_val = state_obj.state if state_obj else "unavailable"
    if entry.domain == "sensor" and state_val not in ("unavailable", "unknown", ""):
        try:
            state_val = str(apply_ha_display_precision(entry, float(state_val), default_precision=1))
        except ValueError:
            pass

    attrs = state_obj.attributes if state_obj else {}
    if getattr(entry, "has_entity_name", False) and (entry.name or entry.original_name):
        raw_friendly = str(entry.name or entry.original_name)
    else:
        raw_friendly = str(
            attrs.get("friendly_name") or entry.name or entry.original_name or entry.entity_id
        )
    clean_name = raw_friendly
    for candidate_prefix in (dev_prefix, slug_words):
        if candidate_prefix and clean_name.lower().startswith(candidate_prefix.lower() + " "):
            clean_name = clean_name[len(candidate_prefix) + 1 :].strip() or raw_friendly

    dev_class = str(attrs.get("device_class") or entry.original_device_class or "")
    cat = entry.entity_category
    sec_id, _ = classify_esphome_entity_section(
        entry.entity_id,
        clean_name,
        entry.domain,
        dev_class,
        cat,
        translation_key=entry.translation_key,
        device_object_prefixes=object_prefixes,
    )
    display_label = (
        clean_name.split(":", 1)[1].strip()
        if ":" in clean_name and clean_name.split(":", 1)[1].strip()
        else clean_name
    )
    return sec_id, {
        "entity_id": entry.entity_id,
        "name": display_label,
        "key": entry.translation_key or "",
        "domain": entry.domain,
        "state": state_val,
        "unit": str(attrs.get("unit_of_measurement") or ""),
        "device_class": dev_class,
        "category": str(cat.value if cat else "primary"),
        "options": list(attrs.get("options") or []),
        "min": attrs.get("min"),
        "max": attrs.get("max"),
        "step": attrs.get("step"),
        "_sort": (_DOMAIN_SORT_ORDER.get(entry.domain, _DEFAULT_DOMAIN_RANK), clean_name.lower()),
    }


def get_esphome_device_entities(
    hass: HomeAssistant,
    esphome_device_id: str | None,
    device_slug: str = "",
) -> dict[str, Any]:
    """Inspect and semantically group all enabled entities of the bound ESPHome device."""
    bound_dev = get_bound_esphome_device(hass, esphome_device_id)
    target_device_id = bound_dev.id if bound_dev is not None else None
    dev_meta = _build_esphome_device_meta(hass, target_device_id, device_slug)

    sections_map: dict[str, list[dict[str, Any]]] = {
        sec_id: [] for sec_id, _title, _desc in UNIVERSAL_SECTION_META
    }
    dev_prefix = dev_meta["name"].strip()
    slug_words = device_slug.strip().replace("_", " ").replace("-", " ")
    object_prefixes = tuple(
        sorted({p for p in (slugify(dev_prefix), slugify(device_slug)) if p}, key=len, reverse=True)
    )

    for entry in device_entities(hass, target_device_id, include_disabled=False):
        sec_id, item = _format_entity_item(
            hass,
            entry,
            dev_prefix=dev_prefix,
            slug_words=slug_words,
            object_prefixes=object_prefixes,
        )
        sections_map.setdefault(sec_id, []).append(item)

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
        sections_list.append({"id": sec_id, "title": sec_title, "description": sec_desc, "items": sec_items})

    if other_items := sections_map.get("other", []):
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
    return {"device": dev_meta, "sections": sections_list}
