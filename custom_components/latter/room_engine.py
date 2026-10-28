"""Universal Area-Aware Room Discovery, Curated Entity Filtering, Telemetry, Alarm & ESPHome Inspector for Latter."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    EntityCategory,
    STATE_ON,
    STATE_OPEN,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from .ble_engine import _iter_devices, _iter_entities, get_ble_proxy_area_ids
from .browse_engine import is_music_assistant_player
from .const import normalize_device_slug

_LOGGER = logging.getLogger(__name__)

ROOM_CONTROL_DOMAINS: tuple[str, ...] = (
    "scene",
    "light",
    "cover",
    "fan",
    "switch",
    "input_boolean",
    "climate",
    "media_player",
)

SLIDER_CAPABLE_DOMAINS: set[str] = {
    "light",
    "cover",
    "fan",
}

WINDOW_COVER_CLASSES: set[str] = {
    "awning",
    "blind",
    "curtain",
    "drape",
    "shade",
    "shutter",
    "window",
    "",
}

UNIVERSAL_SECTION_META: tuple[tuple[str, str, str], ...] = (
    ("home", "Home Screen", "Clock face, weather background, home dock shortcuts, and home screen behavior."),
    ("display", "Display & Appearance", "Screen brightness, color profile, UI theme, and boot animations."),
    ("sleep", "Sleep & Wake", "Inactivity timeouts, screensaver, pickup-to-wake, tap-to-wake, and hibernate schedule."),
    ("voice", "Voice Assistant", "Wake word models, microphone mute, and voice detection sensitivity."),
    ("sound", "Sound & Alerts", "Onboard speaker chimes, alert volume, and volume step increments."),
    ("music", "Music & Media", "Media player entity and library, artist, album, and podcast sorting options."),
    ("room", "Room & BLE Presence", "BLE presence beacon toggle and automatic room handoff settings."),
    ("remote", "TV & Media Remote", "Active remote slot selection and on-device remote behavior."),
    ("battery", "Battery & Power", "Battery charge level, charging status, PMIC voltage, and internal temperature."),
    ("actions", "Device Actions", "One-tap restart, hibernate, refresh, and maintenance triggers."),
    ("network", "Network & Diagnostics", "Wi-Fi signal strength, IP/MAC address, uptime, memory, and firmware updates."),
    ("other", "General & Custom Entities", "Additional sensors, switches, and custom project entities."),
)


def classify_esphome_entity_section(
    entity_id: str,
    friendly_name: str,
    domain: str,
    device_class: str,
    entity_category: EntityCategory | None,
) -> tuple[str, str | None]:
    """Classify an ESPHome entity into a focused section; returns (section_id, custom_section_title_or_None)."""
    name_clean = friendly_name.strip()
    text = f"{entity_id} {name_clean}".lower()
    dev_cls = device_class.lower()

    # 1. Explicit "Prefix: Name" Convention (Highest Priority)
    if ":" in name_clean:
        prefix_raw = name_clean.split(":", 1)[0].strip()
        prefix_low = prefix_raw.lower()
        if prefix_low in ("home", "home screen", "clock"):
            return "home", None
        if prefix_low in ("display", "ui", "screen", "theme", "appearance", "weather"):
            return "display", None
        if prefix_low in ("sleep & wake", "sleep", "wake"):
            return "sleep", None
        if prefix_low in ("voice", "wake word", "assist", "mic", "microphone"):
            return "voice", None
        if prefix_low in ("sound", "audio", "chime", "alerts"):
            return "sound", None
        if prefix_low in ("music", "media", "player"):
            return "music", None
        if prefix_low in ("room", "ble", "area", "presence"):
            return "room", None
        if prefix_low in ("remote", "tv"):
            return "remote", None
        if prefix_low in ("battery", "power", "pmic"):
            return "battery", None
        if prefix_low in ("action", "actions"):
            return "actions", None
        if prefix_low in ("system", "network", "wifi", "diagnostics"):
            return "network", None
        if 2 <= len(prefix_raw) <= 24:
            sec_slug = "custom_" + re.sub(r"[^a-z0-9]+", "_", prefix_low).strip("_")
            return sec_slug, prefix_raw

    # 2. Semantic fallback classification (check clean friendly_name + entity suffix so device_slug words don't false-match)
    ent_suffix = entity_id.split(".", 1)[-1].lower()
    clean_low = name_clean.lower()

    if domain == "button" or dev_cls in ("restart", "identify"):
        return "actions", None

    if any(k in ent_suffix for k in ("timer_remaining", "timer_active", "alarm_ringing")):
        return "sleep", None

    if dev_cls in ("battery", "voltage", "current", "power", "energy") or any(
        k in clean_low or k in ent_suffix
        for k in ("battery", "charging", "charger", "vbus", "axp2101", "pmic", "voltage", "internal_temp", "die_temp", "imu_temp")
    ):
        return "battery", None

    # Check Network & System Diagnostics BEFORE generic words so Wi-Fi/IP/MAC/Uptime/Version/Diagnostic entities always land in "network"
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
        or (entity_category == EntityCategory.DIAGNOSTIC and domain in ("sensor", "binary_sensor", "text_sensor"))
    ):
        return "network", None

    if any(k in clean_low or k in ent_suffix for k in ("clock", "weather_background", "shortcut_", "dock", "home_")):
        return "home", None

    if any(k in clean_low or k in ent_suffix for k in ("sleep", "wake_on", "pickup_to_wake", "tap_to_wake", "screensaver", "hibernate", "stay_awake", "timeout")):
        return "sleep", None

    if any(k in clean_low or k in ent_suffix for k in ("display", "screen", "brightness", "backlight", "amoled", "theme", "color_profile", "boot")):
        return "display", None

    if any(k in clean_low or k in ent_suffix for k in ("voice", "wake_word", "micro_wake", "mic", "microphone", "sensitivity", "assist")):
        return "voice", None

    if any(k in clean_low or k in ent_suffix for k in ("sound", "chime", "beep", "ringtone", "alert_volume", "volume_step", "dac", "es8311")):
        return "sound", None

    if any(k in clean_low or k in ent_suffix for k in ("ble", "beacon", "ibeacon", "presence", "room", "area")):
        return "room", None

    if any(k in clean_low or k in ent_suffix for k in ("remote", "slot_1", "slot_2", "slot_3", "slot_4")):
        return "remote", None

    if domain == "media_player" or any(k in clean_low or k in ent_suffix for k in ("music", "album", "artist", "podcast", "queue", "playlist", "sort", "track", "speaker")):
        return "music", None

    if entity_category == EntityCategory.DIAGNOSTIC:
        return "network", None

    return "other", None


def resolve_entity_area_id(
    hass: HomeAssistant, entity_id: str
) -> str | None:
    """Resolve the Home Assistant area_id for an entity (directly or via device)."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    entry = ent_reg.async_get(entity_id)
    if entry is None:
        return None
    if entry.area_id:
        return entry.area_id
    if entry.device_id:
        device = dev_reg.async_get(entry.device_id)
        if device and device.area_id:
            return device.area_id
    return None


def match_area_by_name_or_id(
    hass: HomeAssistant, raw_value: str
) -> str | None:
    """Match a BLE presence sensor state (room name, slug, or area_id) to a valid HA area_id."""
    val = raw_value.strip()
    if not val or val.lower() in (
        "unknown",
        "unavailable",
        "not_home",
        "away",
        "none",
        "",
    ):
        return None

    area_reg = ar.async_get(hass)
    if area_reg.async_get_area(val) is not None:
        return val

    val_low = val.lower()
    val_norm = val_low.replace("_", " ").replace("-", " ").strip()

    for area in area_reg.async_list_areas():
        a_low = area.name.lower()
        a_norm = a_low.replace("_", " ").replace("-", " ").strip()
        if val_low == a_low or val_norm == a_norm or val_low == area.id.lower():
            return area.id

    for area in area_reg.async_list_areas():
        a_norm = area.name.lower().replace("_", " ").replace("-", " ").strip()
        if a_norm and (a_norm in val_norm or val_norm in a_norm):
            return area.id

    return None


def find_esphome_device_id(
    hass: HomeAssistant, device_slug: str
) -> str | None:
    """Find the Home Assistant device_id for the target ESPHome node."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    slug_norm = normalize_device_slug(device_slug)

    for entry in _iter_entities(ent_reg):
        if entry.platform == "esphome" and slug_norm in entry.entity_id:
            if entry.device_id:
                return entry.device_id

    for dev in _iter_devices(dev_reg):
        dev_name = (
            str(dev.name_by_user or dev.name or "")
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        if slug_norm and slug_norm in dev_name:
            return dev.id

    return None


def inject_esphome_visit_link(
    hass: HomeAssistant, device_slug: str, companion_url: str
) -> None:
    """Set configuration_url on the native ESPHome device entry so its 'Visit' button opens Latter Studio."""
    target_device_id = find_esphome_device_id(hass, device_slug)
    if not target_device_id:
        return
    dev_reg = dr.async_get(hass)
    dev = dev_reg.async_get(target_device_id)
    if dev and dev.configuration_url != companion_url:
        dev_reg.async_update_device(
            target_device_id, configuration_url=companion_url
        )
        _LOGGER.info(
            "Linked ESPHome device '%s' 'Visit' button to Latter Web Companion Studio",
            device_slug,
        )


def inject_hacs_update_brand_icon(hass: HomeAssistant) -> None:
    """Ensure any HACS update.*latter* entity uses the local /api/latter/brand/icon.png instead of brands.home-assistant.io."""
    target_pic = "/api/latter/brand/icon.png"
    for state_obj in hass.states.async_all("update"):
        ent_id = state_obj.entity_id.lower()
        friendly = str(state_obj.attributes.get("friendly_name") or "").lower()
        if "latter" not in ent_id and "latter" not in friendly:
            continue
        pic = str(state_obj.attributes.get("entity_picture") or "")
        if pic != target_pic:
            new_attrs = dict(state_obj.attributes)
            new_attrs["entity_picture"] = target_pic
            hass.states.async_set(
                state_obj.entity_id,
                state_obj.state,
                new_attrs,
            )


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
        return int(round(raw_val))
    return round(raw_val, prec)


def get_esphome_device_entities(
    hass: HomeAssistant, device_slug: str
) -> dict[str, Any]:
    """Inspect and semantically group all entities belonging to any ESPHome device."""
    target_device_id = find_esphome_device_id(hass, device_slug)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

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

    entries: list[er.RegistryEntry] = []
    if target_device_id:
        entries = er.async_entries_for_device(
            ent_reg, target_device_id, include_disabled_entities=False
        )
    else:
        slug_norm = normalize_device_slug(device_slug)
        entries = [
            e
            for e in _iter_entities(ent_reg)
            if e.platform == "esphome" and slug_norm in e.entity_id and not e.disabled_by
        ]

    dev_prefix = dev_meta["name"].strip()
    slug_words = device_slug.strip().replace("_", " ").replace("-", " ")

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
            entry.entity_id, clean_name, entry.domain, dev_class, cat
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
                "count": len(sec_items),
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
                "count": len(sec_items),
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
                "title": "General & Custom Entities",
                "description": "Additional sensors, switches, and custom project entities (spillover).",
                "count": len(other_items),
                "items": other_items,
            }
        )

    return {
        "device": dev_meta,
        "sections": sections_list,
    }


INTERNAL_DEVICE_CONTROL_KEYWORDS: tuple[str, ...] = (
    "backlight",
    "display",
    "screen",
    "lcd",
    "oled",
    "amoled",
    "status_led",
    "indicator",
    "onboard_led",
    "speaker_enable",
    "speaker_amp",
    "pa_enable",
    "mic_mute",
    "microphone",
    "wake_word",
    "ble_presence",
    "ble_beacon",
    "ibeacon",
    "bluetooth_proxy",
    "vpn_",
    "wireguard",
    "shortcut_",
    "sleep_",
    "screensaver",
    "stay_awake",
    "hold_crown",
    "game_sound",
    "area_media_handoff",
    "show_all_category",
    "wake_greeting",
    "weather_background",
    "speaker_shortcut",
    "library_shortcut",
    "engineering_mode",
    "ld2410",
    "ld2420",
    "ld2450",
    "mmwave",
    "radar_",
    "buzzer",
    "beeper",
    "child_lock",
    "restart",
    "reboot",
    "safe_mode",
)


def _is_internal_device_control_entity(
    entity_id: str, friendly_name: str, is_companion_display: bool = False
) -> bool:
    """Return True if a light or switch is an internal ESPHome hardware/UI control rather than a room load."""
    if is_companion_display:
        return True
    ent_suffix = entity_id.split(".", 1)[-1].lower()
    haystack = f"{ent_suffix} {friendly_name.lower()}"
    if ":" in friendly_name:
        prefix = friendly_name.split(":", 1)[0].strip().lower()
        if prefix in (
            "home",
            "display",
            "sleep & wake",
            "sleep",
            "wake",
            "voice",
            "sound",
            "music",
            "room",
            "remote",
            "system",
            "actions",
        ):
            return True
    return any(k in haystack for k in INTERNAL_DEVICE_CONTROL_KEYWORDS)


def _unexpose_entity_from_voice_assistants(
    hass: HomeAssistant, entity_id: str
) -> None:
    """Unexpose an internal device backlight or hardware switch from Assist/Alexa/Google room commands."""
    try:
        from homeassistant.components.homeassistant.exposed_entities import (
            async_expose_entity,
        )

        for assistant in ("conversation", "cloud.alexa", "cloud.google_assistant"):
            try:
                async_expose_entity(hass, assistant, entity_id, False)
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass


def protect_handheld_sensors_from_area_dashboards(
    hass: HomeAssistant, device_slug: str, device_profile: str = "mobile_display"
) -> None:
    """Shield internal device backlights, hardware switches, and mobile sensors from Area dashboards and Assist room commands."""
    target_device_id = find_esphome_device_id(hass, device_slug)
    if not target_device_id:
        return

    ent_reg = er.async_get(hass)
    esphome_svcs = hass.services.async_services().get("esphome", {})
    slug_norm = normalize_device_slug(device_slug)
    is_companion_display = (
        device_profile in ("mobile_display", "stationary_display")
        or any(
            (s.endswith("_set_browse_slots") or s.endswith("_set_room_slots"))
            and slug_norm in s
            for s in esphome_svcs
        )
    )

    for entry in er.async_entries_for_device(ent_reg, target_device_id):
        state_obj = hass.states.get(entry.entity_id)
        friendly = str(
            (state_obj.attributes.get("friendly_name") if state_obj else None)
            or entry.name
            or entry.original_name
            or entry.entity_id
        )

        # 1. On mobile displays, mark onboard temperature/humidity sensors as DIAGNOSTIC
        if entry.domain == "sensor" and device_profile == "mobile_display":
            dev_class = (
                str(state_obj.attributes.get("device_class") or "").lower()
                if state_obj
                else str(entry.original_device_class or "").lower()
            )
            if dev_class in ("temperature", "humidity") and entry.entity_category is None:
                ent_reg.async_update_entity(
                    entry.entity_id,
                    entity_category=EntityCategory.DIAGNOSTIC,
                )
            continue

        # 2. On ANY onboarded ESPHome device (native display or bridged node), shield internal
        #    backlights (light.*) and internal hardware/config switches (switch.*) from Area
        #    room commands ("Turn off all lights" / "Turn off everything") and Area cards
        if entry.domain in ("light", "switch"):
            if _is_internal_device_control_entity(
                entry.entity_id, friendly, is_companion_display=is_companion_display
            ):
                updates: dict[str, Any] = {}
                if entry.entity_category is None:
                    updates["entity_category"] = EntityCategory.CONFIG
                if entry.hidden_by is None:
                    updates["hidden_by"] = er.RegistryEntryHider.INTEGRATION
                if updates:
                    ent_reg.async_update_entity(entry.entity_id, **updates)
                    _LOGGER.info(
                        "Shielded internal device entity '%s' (CONFIG + Hidden from Area/Room controls)",
                        entry.entity_id,
                    )
                _unexpose_entity_from_voice_assistants(hass, entry.entity_id)


def sync_esphome_device_area(
    hass: HomeAssistant,
    device_slug: str,
    area_id: str,
    require_ble_proxy_area: bool = True,
) -> None:
    """Update the ESPHome device's area_id in HA Device Registry ONLY for valid rooms."""
    if not area_id:
        return

    if require_ble_proxy_area:
        proxy_areas = get_ble_proxy_area_ids(hass)
        if proxy_areas and area_id not in proxy_areas:
            _LOGGER.debug(
                "Skipping Device Registry area sync to '%s' because that area has no BLE proxy.",
                area_id,
            )
            return

    protect_handheld_sensors_from_area_dashboards(hass, device_slug)

    target_device_id = find_esphome_device_id(hass, device_slug)
    if target_device_id:
        dev_reg = dr.async_get(hass)
        dev = dev_reg.async_get(target_device_id)
        if dev and dev.area_id != area_id:
            dev_reg.async_update_device(target_device_id, area_id=area_id)
            _LOGGER.debug(
                "Synced ESPHome device '%s' (id=%s) to area_id='%s' for room-aware Voice Assistant",
                device_slug,
                target_device_id,
                area_id,
            )


def resolve_remote_slot_pair(
    hass: HomeAssistant, configured_entity_id: str | None
) -> dict[str, str]:
    """Given a remote.* or media_player.* entity, auto-resolve its sibling on the same HA device."""
    empty = {
        "name": "Unassigned",
        "remote_entity": "",
        "media_player_entity": "",
        "area_id": "",
        "state": "off",
        "platform": "",
    }
    if not configured_entity_id:
        return empty

    ent_id = configured_entity_id.strip()
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    entry = ent_reg.async_get(ent_id)
    state_obj = hass.states.get(ent_id)
    if state_obj is None and entry is None:
        return empty

    ent_domain = state_obj.domain if state_obj else ent_id.split(".", 1)[0]
    remote_ent = ent_id if ent_domain == "remote" else ""
    mp_ent = ent_id if ent_domain == "media_player" else ""
    platform = str(entry.platform or "") if entry else ""

    if entry and entry.device_id:
        for sib in er.async_entries_for_device(ent_reg, entry.device_id):
            if sib.disabled_by:
                continue
            if sib.domain == "remote" and not remote_ent:
                remote_ent = sib.entity_id
                if not platform:
                    platform = str(sib.platform or "")
            elif sib.domain == "media_player" and not mp_ent:
                mp_ent = sib.entity_id
                if not platform:
                    platform = str(sib.platform or "")

    primary_state = hass.states.get(mp_ent) or state_obj
    dev_name = ""
    if entry and entry.device_id:
        dev = dev_reg.async_get(entry.device_id)
        if dev:
            dev_name = str(dev.name_by_user or dev.name or "")
    friendly = str(
        (primary_state.attributes.get("friendly_name") if primary_state else None)
        or (state_obj.attributes.get("friendly_name") if state_obj else None)
        or (entry.name if entry else None)
        or (entry.original_name if entry else None)
        or dev_name
        or ent_id
    )
    area_id = resolve_entity_area_id(hass, ent_id) or ""

    return {
        "name": friendly[:32],
        "remote_entity": remote_ent or mp_ent,
        "media_player_entity": mp_ent or remote_ent,
        "area_id": area_id,
        "state": primary_state.state if primary_state else "off",
        "platform": platform,
    }


def _get_companion_display_device_ids_and_slugs(
    hass: HomeAssistant, local_speaker: str = ""
) -> tuple[set[str], set[str]]:
    """Return (device_ids, slugs) of all Latter companion displays so their own backlights/switches never appear as room loads."""
    dev_ids: set[str] = set()
    slugs: set[str] = set()
    if local_speaker.startswith("media_player."):
        sp_slug = local_speaker.removeprefix("media_player.").removesuffix("_music")
        if sp_slug:
            slugs.add(sp_slug)
    domain_data = hass.data.get("latter", {})
    for val in domain_data.values():
        slug = getattr(val, "device_slug", "")
        prof = getattr(val, "device_profile", "")
        if slug and prof in ("mobile_display", "stationary_display"):
            slugs.add(slug)
            did = find_esphome_device_id(hass, slug)
            if did:
                dev_ids.add(did)
    return dev_ids, slugs


def _is_curated_room_entity(
    hass: HomeAssistant, state_obj: State, local_speaker: str = ""
) -> bool:
    """Strictly filter out config/diagnostic entities, companion display backlights/switches, and non-MA speakers."""
    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(state_obj.entity_id)
    if entry is not None:
        if entry.disabled_by or entry.hidden_by:
            return False
        if entry.entity_category is not None:
            return False

    domain = state_obj.domain
    attrs = state_obj.attributes
    friendly = str(attrs.get("friendly_name") or state_obj.entity_id)
    dev_class = str(attrs.get("device_class") or "").lower()

    # Never include a companion display's own backlight/switches or ESPHome internal hardware controls in Room Control
    if domain in ("light", "switch", "fan", "cover"):
        comp_dev_ids, comp_slugs = _get_companion_display_device_ids_and_slugs(
            hass, local_speaker
        )
        is_comp_dev = bool(
            (entry and entry.device_id and entry.device_id in comp_dev_ids)
            or any(
                state_obj.entity_id.startswith(f"{domain}.{s}_") for s in comp_slugs
            )
        )
        if domain in ("light", "switch") and _is_internal_device_control_entity(
            state_obj.entity_id, friendly, is_companion_display=is_comp_dev
        ):
            return False
        if is_comp_dev:
            return False

    if domain in ("light", "scene", "fan", "climate"):
        return True

    if domain == "cover":
        name_low = str(attrs.get("friendly_name") or state_obj.entity_id).lower()
        if any(k in name_low for k in ("curtain", "drape", "sheer", "blind", "shade", "shutter", "window")):
            return True
        return dev_class in WINDOW_COVER_CLASSES

    if domain in ("switch", "input_boolean"):
        return True

    if domain == "media_player":
        if state_obj.entity_id == local_speaker:
            return False
        return is_music_assistant_player(hass, state_obj)

    return False


def get_entity_level(state_obj: State) -> int:
    """Return 0..100 for slider-capable domains (light, cover, fan) or -1 for non-slider domains."""
    domain = state_obj.domain
    if domain not in SLIDER_CAPABLE_DOMAINS:
        return -1

    attrs = state_obj.attributes
    is_active = state_obj.state in (STATE_ON, STATE_OPEN)

    if domain == "light":
        if not is_active:
            return 0
        bri = attrs.get("brightness")
        if bri is not None:
            return max(1, min(100, int(round((float(bri) / 255.0) * 100))))
        return 100

    if domain == "cover":
        pos = attrs.get("current_position")
        if pos is not None:
            return max(0, min(100, int(round(float(pos)))))
        return 100 if state_obj.state == STATE_OPEN else 0

    if domain == "fan":
        if not is_active:
            return 0
        pct = attrs.get("percentage")
        if pct is not None:
            return max(0, min(100, int(round(float(pct)))))
        return 100

    return -1


def format_entity_slot_name(state_obj: State, area_name: str = "") -> str:
    """Format a compact, informative slot label for ESPHome display cards."""
    friendly = str(state_obj.attributes.get("friendly_name") or state_obj.entity_id)
    if area_name and friendly.lower().startswith(area_name.lower() + " "):
        friendly = friendly[len(area_name) + 1 :].strip() or friendly

    domain = state_obj.domain
    level = get_entity_level(state_obj)

    if domain == "light" and state_obj.state == STATE_ON and level >= 0:
        return f"{friendly} ({level}%)"
    if domain == "cover" and level >= 0:
        return f"{friendly} ({level}%)"
    if domain == "climate":
        cur = state_obj.attributes.get("current_temperature")
        tgt = state_obj.attributes.get("temperature")
        if tgt is not None:
            return f"{friendly} ({int(round(float(tgt)))}°)"
        if cur is not None:
            return f"{friendly} ({int(round(float(cur)))}°)"
    if domain == "fan" and state_obj.state == STATE_ON and level >= 0:
        return f"{friendly} ({level}%)"
    if domain == "media_player":
        return f"Speaker: {friendly}"
    if domain == "alarm_control_panel":
        return f"Alarm: {state_obj.state.replace('_', ' ').title()}"
    return friendly


def get_area_climate_telemetry(
    hass: HomeAssistant, area_id: str | None, device_slug: str = ""
) -> dict[str, Any]:
    """Discover ambient room temperature and humidity assigned to an area."""
    result: dict[str, Any] = {
        "temperature": None,
        "temperature_unit": "",
        "humidity": None,
    }
    if not area_id:
        return result

    ent_reg = er.async_get(hass)
    handheld_dev_id = (
        find_esphome_device_id(hass, device_slug) if device_slug else None
    )
    slug_norm = normalize_device_slug(device_slug) if device_slug else ""

    for state_obj in hass.states.async_all("sensor"):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        if slug_norm and slug_norm in state_obj.entity_id:
            continue

        entry = ent_reg.async_get(state_obj.entity_id)
        if entry is not None:
            if entry.disabled_by or entry.hidden_by:
                continue
            if entry.entity_category is not None:
                continue
            if handheld_dev_id and entry.device_id == handheld_dev_id:
                continue

        if resolve_entity_area_id(hass, state_obj.entity_id) != area_id:
            continue

        dev_class = str(state_obj.attributes.get("device_class") or "").lower()
        if dev_class == "temperature" and result["temperature"] is None:
            try:
                result["temperature"] = _apply_ha_display_precision(
                    entry, float(state_obj.state), default_precision=0
                )
                result["temperature_unit"] = str(
                    state_obj.attributes.get("unit_of_measurement") or "°"
                )
            except ValueError:
                pass
        elif dev_class == "humidity" and result["humidity"] is None:
            try:
                result["humidity"] = _apply_ha_display_precision(
                    entry, float(state_obj.state), default_precision=0
                )
            except ValueError:
                pass

    if result["temperature"] is None or result["humidity"] is None:
        for state_obj in hass.states.async_all("climate"):
            if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            if resolve_entity_area_id(hass, state_obj.entity_id) != area_id:
                continue
            attrs = state_obj.attributes
            if result["temperature"] is None and attrs.get("current_temperature") is not None:
                try:
                    result["temperature"] = round(float(attrs["current_temperature"]), 1)
                except ValueError:
                    pass
            if result["humidity"] is None and attrs.get("current_humidity") is not None:
                try:
                    result["humidity"] = round(float(attrs["current_humidity"]), 1)
                except ValueError:
                    pass

    return result


def get_home_alarm_summary(
    hass: HomeAssistant, configured_alarm_entity: str | None = None
) -> dict[str, Any]:
    """Return the configured (or auto-discovered) home security alarm_control_panel summary."""
    if configured_alarm_entity:
        state_obj = hass.states.get(configured_alarm_entity)
        if state_obj is not None:
            return {
                "entity_id": state_obj.entity_id,
                "state": state_obj.state,
                "name": str(
                    state_obj.attributes.get("friendly_name") or "Home Alarm"
                ),
                "supported_features": int(
                    state_obj.attributes.get("supported_features") or 0
                ),
                "code_arm_required": bool(
                    state_obj.attributes.get("code_arm_required", False)
                ),
            }

    for state_obj in hass.states.async_all("alarm_control_panel"):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        return {
            "entity_id": state_obj.entity_id,
            "state": state_obj.state,
            "name": str(
                state_obj.attributes.get("friendly_name") or "Home Alarm"
            ),
            "supported_features": int(
                state_obj.attributes.get("supported_features") or 0
            ),
            "code_arm_required": bool(
                state_obj.attributes.get("code_arm_required", False)
            ),
        }
    return {
        "entity_id": "",
        "state": "none",
        "name": "",
        "supported_features": 0,
        "code_arm_required": False,
    }


def get_whole_home_summary(
    hass: HomeAssistant,
    thermostat_entity: str | None = None,
    lock_entity: str | None = None,
    garage_entity: str | None = None,
    vacuum_entity: str | None = None,
) -> dict[str, Any]:
    """Resolve configured (or primary auto-discovered) Whole-Home Thermostat, Lock, Garage, and Vacuum states."""
    out: dict[str, Any] = {
        "thermostat_entity": "",
        "thermostat_state": "off",
        "thermostat_temp": 71,
        "thermostat_current_temp": None,
        "lock_entity": "",
        "lock_state": "locked",
        "garage_entity": "",
        "garage_state": "closed",
        "vacuum_entity": "",
        "vacuum_state": "docked",
    }

    # 1. Thermostat (climate.*)
    t_st = hass.states.get(thermostat_entity) if thermostat_entity else None
    if t_st is None:
        for cand in hass.states.async_all("climate"):
            if cand.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                t_st = cand
                break
    if t_st is not None:
        out["thermostat_entity"] = t_st.entity_id
        out["thermostat_state"] = t_st.state
        tgt_t = (
            t_st.attributes.get("temperature")
            or t_st.attributes.get("target_temp_low")
            or t_st.attributes.get("current_temperature")
        )
        if tgt_t is not None:
            try:
                out["thermostat_temp"] = int(round(float(tgt_t)))
            except (ValueError, TypeError):
                pass
        cur_t = t_st.attributes.get("current_temperature")
        if cur_t is not None:
            try:
                out["thermostat_current_temp"] = round(float(cur_t), 1)
            except (ValueError, TypeError):
                pass

    # 2. Entry Lock (lock.*)
    l_st = hass.states.get(lock_entity) if lock_entity else None
    if l_st is None:
        for cand in hass.states.async_all("lock"):
            if cand.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                l_st = cand
                break
    if l_st is not None:
        out["lock_entity"] = l_st.entity_id
        out["lock_state"] = l_st.state

    # 3. Garage Door (cover.*)
    g_st = hass.states.get(garage_entity) if garage_entity else None
    if g_st is None:
        for cand in hass.states.async_all("cover"):
            if cand.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            d_cls = str(cand.attributes.get("device_class") or "").lower()
            if d_cls in ("garage", "gate", "door") or "garage" in cand.entity_id.lower():
                g_st = cand
                break
    if g_st is not None:
        out["garage_entity"] = g_st.entity_id
        out["garage_state"] = g_st.state

    # 4. Robot Vacuum (vacuum.*)
    v_st = hass.states.get(vacuum_entity) if vacuum_entity else None
    if v_st is None:
        for cand in hass.states.async_all("vacuum"):
            if cand.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                v_st = cand
                break
    if v_st is not None:
        out["vacuum_entity"] = v_st.entity_id
        out["vacuum_state"] = v_st.state

    return out


def get_home_wide_entities(
    hass: HomeAssistant,
    configured_alarm_entity: str | None = None,
    custom_entities: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return home-wide security alarm, scenes, and user-pinned entities (`mode='home'`)."""
    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    alarm_info = get_home_alarm_summary(hass, configured_alarm_entity)
    if alarm_info["entity_id"]:
        state_obj = hass.states.get(alarm_info["entity_id"])
        if state_obj is not None:
            is_armed = state_obj.state != "disarmed"
            items.append(
                {
                    "name": format_entity_slot_name(state_obj),
                    "id": state_obj.entity_id,
                    "type": "alarm_control_panel",
                    "active": is_armed,
                    "level": -1,
                }
            )
            seen_ids.add(state_obj.entity_id)

    for ent_id in custom_entities or []:
        if ent_id in seen_ids:
            continue
        state_obj = hass.states.get(ent_id)
        if state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        is_active = state_obj.state in (STATE_ON, STATE_OPEN, STATE_PLAYING)
        items.append(
            {
                "name": format_entity_slot_name(state_obj),
                "id": ent_id,
                "type": state_obj.domain,
                "active": is_active,
                "level": get_entity_level(state_obj),
            }
        )
        seen_ids.add(ent_id)

    return items


def get_areas_summary(
    hass: HomeAssistant,
    active_area_id: str | None = None,
    local_speaker: str = "",
    device_slug: str = "",
) -> list[dict[str, Any]]:
    """Return a sorted list of Home Assistant areas that contain curated controllable entities."""
    area_reg = ar.async_get(hass)

    area_counts: dict[str, dict[str, int]] = {}
    for state_obj in hass.states.async_all():
        if state_obj.domain not in ROOM_CONTROL_DOMAINS:
            continue
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        if not _is_curated_room_entity(hass, state_obj, local_speaker):
            continue

        a_id = resolve_entity_area_id(hass, state_obj.entity_id)
        if not a_id:
            continue

        counts = area_counts.setdefault(a_id, {"total": 0, "lights_on": 0})
        counts["total"] += 1
        if state_obj.domain == "light" and state_obj.state == STATE_ON:
            counts["lights_on"] += 1

    items: list[dict[str, Any]] = []
    for area in area_reg.async_list_areas():
        counts = area_counts.get(area.id)
        if not counts or counts["total"] == 0:
            continue
        lights_on = counts["lights_on"]
        climate_info = get_area_climate_telemetry(hass, area.id, device_slug)
        temp_val = climate_info.get("temperature")

        suffix_parts: list[str] = []
        if temp_val is not None:
            suffix_parts.append(f"{int(round(temp_val))}°")
        if lights_on > 0:
            suffix_parts.append(f"{lights_on} on")

        label = (
            f"{area.name} ({', '.join(suffix_parts)})"
            if suffix_parts
            else area.name
        )
        items.append(
            {
                "name": label,
                "id": area.id,
                "type": "area",
                "active": area.id == active_area_id,
                "level": -1,
                "_raw_name": area.name,
            }
        )

    items.sort(key=lambda x: (not x["active"], x["_raw_name"].lower()))
    return items


def _parse_domain_filter(domain_filter: str) -> tuple[str, ...]:
    """Parse a single domain, comma-separated domain list, or alias into allowed domains (cover and fan are strictly separate!)."""
    raw = domain_filter.strip().lower()
    if not raw or raw == "all":
        return ROOM_CONTROL_DOMAINS
    if raw in ("scene", "scenes"):
        return ("scene",)
    if raw in ("light", "lights"):
        return ("light",)
    if raw in ("cover", "covers", "shades", "blinds", "curtains"):
        return ("cover",)
    if raw in ("fan", "fans"):
        return ("fan",)
    if raw in ("switch", "switches", "outlet", "outlets", "helper", "helpers"):
        return ("switch", "input_boolean")
    if raw in ("media", "media_player", "speaker", "speakers"):
        return ("media_player",)
    if "," in raw:
        parts = [
            p.strip()
            for p in raw.split(",")
            if p.strip() in ROOM_CONTROL_DOMAINS
        ]
        if parts:
            return tuple(parts)
    if raw in ROOM_CONTROL_DOMAINS:
        return (raw,)
    return ROOM_CONTROL_DOMAINS


def get_area_available_domains(
    hass: HomeAssistant,
    area_id: str | None,
    custom_entities: list[str] | None = None,
    local_speaker: str = "",
) -> str:
    """Return comma-separated canonical room categories ('scene,light,cover,fan,switch') present in the active area."""
    all_items = get_area_entities(
        hass,
        area_id=area_id,
        domain_filter="all",
        custom_entities=custom_entities,
        local_speaker=local_speaker,
    )
    present_types = {str(it.get("type") or "") for it in all_items}
    ordered: list[str] = []
    if "scene" in present_types or "script" in present_types:
        ordered.append("scene")
    if "light" in present_types:
        ordered.append("light")
    if "cover" in present_types:
        ordered.append("cover")
    if "fan" in present_types:
        ordered.append("fan")
    if "switch" in present_types or "input_boolean" in present_types:
        ordered.append("switch")
    if "media_player" in present_types:
        ordered.append("media")
    if "climate" in present_types:
        ordered.append("climate")
    return ",".join(ordered)


def get_area_entities(
    hass: HomeAssistant,
    area_id: str | None,
    domain_filter: str = "all",
    custom_entities: list[str] | None = None,
    local_speaker: str = "",
) -> list[dict[str, Any]]:
    """Return curated controllable entities for a specific area (supports single or comma-separated domain_filter)."""
    area_reg = ar.async_get(hass)
    area_entry = area_reg.async_get_area(area_id) if area_id else None
    area_name = area_entry.name if area_entry else ""

    allowed_domains = _parse_domain_filter(domain_filter)
    is_all_filter = domain_filter.strip().lower() in ("", "all")

    pinned_set = set(custom_entities or [])
    items: list[dict[str, Any]] = []

    domain_priority = {
        "light": 1,
        "cover": 2,
        "fan": 3,
        "scene": 4,
        "climate": 5,
        "switch": 6,
        "media_player": 7,
    }

    for state_obj in hass.states.async_all():
        ent_id = state_obj.entity_id
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue

        is_pinned = ent_id in pinned_set
        ent_area = resolve_entity_area_id(hass, ent_id)

        if area_id and ent_area != area_id and not is_pinned:
            continue

        if not is_pinned:
            if state_obj.domain not in allowed_domains:
                continue
            if not _is_curated_room_entity(hass, state_obj, local_speaker):
                continue
        elif not is_all_filter and state_obj.domain not in allowed_domains:
            continue

        is_active = state_obj.state in (
            STATE_ON,
            STATE_OPEN,
            STATE_PLAYING,
            "heat",
            "cool",
            "heat_cool",
            "auto",
        )
        level = get_entity_level(state_obj)
        items.append(
            {
                "name": format_entity_slot_name(state_obj, area_name),
                "id": ent_id,
                "type": state_obj.domain,
                "active": is_active,
                "level": level,
                "_prio": 0 if is_pinned else domain_priority.get(state_obj.domain, 99),
            }
        )

    items.sort(key=lambda x: (x["_prio"], not x["active"], x["name"].lower()))
    return items


def find_area_media_entities(
    hass: HomeAssistant, area_id: str | None, local_speaker: str
) -> dict[str, str]:
    """Discover the primary Music Assistant speaker and TV/remote entity inside an area."""
    result = {"speaker": "", "remote": ""}
    if not area_id:
        return result

    for state_obj in hass.states.async_all("media_player"):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        if state_obj.entity_id == local_speaker:
            continue
        if resolve_entity_area_id(hass, state_obj.entity_id) == area_id:
            if is_music_assistant_player(hass, state_obj) and not result["speaker"]:
                result["speaker"] = state_obj.entity_id
            dev_class = str(state_obj.attributes.get("device_class") or "").lower()
            if dev_class == "tv" and not result["remote"]:
                result["remote"] = state_obj.entity_id

    for state_obj in hass.states.async_all("remote"):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        if resolve_entity_area_id(hass, state_obj.entity_id) == area_id:
            result["remote"] = state_obj.entity_id
            break

    return result


async def async_execute_room_action(
    hass: HomeAssistant,
    entity_id: str,
    action: str = "toggle",
    level: int | None = None,
    code: str | None = None,
    option: str | None = None,
) -> None:
    """Execute a normalized room, whole-home (alarm/thermostat/garage/lock/vacuum), or light color/kelvin action."""
    state_obj = hass.states.get(entity_id)
    if state_obj is None and entity_id.startswith("whole_home."):
        wh_kind = entity_id.split(".", 1)[1].lower()
        global_cfg = hass.data.get("latter", {}).get("global_config") or {}
        wh_summary = get_whole_home_summary(
            hass,
            thermostat_entity=global_cfg.get("thermostat_entity"),
            lock_entity=global_cfg.get("lock_entity"),
            garage_entity=global_cfg.get("garage_entity"),
            vacuum_entity=global_cfg.get("vacuum_entity"),
        )
        mapped_id = {
            "thermostat": wh_summary["thermostat_entity"],
            "climate": wh_summary["thermostat_entity"],
            "lock": wh_summary["lock_entity"],
            "garage": wh_summary["garage_entity"],
            "vacuum": wh_summary["vacuum_entity"],
        }.get(wh_kind, "")
        if mapped_id:
            entity_id = mapped_id
            state_obj = hass.states.get(entity_id)
    if state_obj is None:
        _LOGGER.debug("Action target entity not found (or running in on-device demo mode): %s", entity_id)
        return

    domain = state_obj.domain
    action = action.strip().lower()
    cur_level = max(0, get_entity_level(state_obj))

    if domain == "button":
        await hass.services.async_call(
            "button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=False
        )
        return

    if domain == "update":
        if action in ("install", "update") and state_obj.state == STATE_ON:
            await hass.services.async_call(
                "update", "install", {ATTR_ENTITY_ID: entity_id}, blocking=False
            )
        elif hass.services.has_service("homeassistant", "update_entity"):
            await hass.services.async_call(
                "homeassistant",
                "update_entity",
                {ATTR_ENTITY_ID: entity_id},
                blocking=False,
            )
        return

    if domain in ("select", "input_select") and option is not None:
        await hass.services.async_call(
            domain,
            "select_option",
            {ATTR_ENTITY_ID: entity_id, "option": str(option)},
            blocking=False,
        )
        return

    if domain in ("number", "input_number") and level is not None:
        await hass.services.async_call(
            domain,
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": float(level)},
            blocking=False,
        )
        return

    if domain == "alarm_control_panel":
        svc_map = {
            "arm_home": "alarm_arm_home",
            "arm_away": "alarm_arm_away",
            "arm_night": "alarm_arm_night",
            "arm_vacation": "alarm_arm_vacation",
            "disarm": "alarm_disarm",
            "turn_on": "alarm_arm_home",
            "turn_off": "alarm_disarm",
        }
        if action == "toggle":
            svc = (
                "alarm_disarm"
                if state_obj.state != "disarmed"
                else "alarm_arm_home"
            )
        else:
            svc = svc_map.get(action, "alarm_arm_home")
        payload: dict[str, Any] = {ATTR_ENTITY_ID: entity_id}
        if code:
            payload["code"] = str(code)
        await hass.services.async_call(
            "alarm_control_panel", svc, payload, blocking=False
        )
        return

    if action in ("step_up", "step_down") and level is None:
        step = 10 if domain != "climate" else 1
        level = max(0, min(100, cur_level + (step if action == "step_up" else -step)))
        action = "set_level"

    if domain in ("scene", "script"):
        await hass.services.async_call(
            domain, "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=False
        )
        return

    if domain == "light" and action == "set_color" and code:
        hex_s = code.strip().lstrip("#")
        if len(hex_s) == 6:
            try:
                rgb = [int(hex_s[0:2], 16), int(hex_s[2:4], 16), int(hex_s[4:6], 16)]
                payload_c: dict[str, Any] = {ATTR_ENTITY_ID: entity_id, "rgb_color": rgb}
                if level is not None and int(level) > 0:
                    payload_c["brightness_pct"] = max(1, min(100, int(level)))
                await hass.services.async_call("light", "turn_on", payload_c, blocking=False)
                return
            except ValueError:
                pass

    if domain == "light" and action == "set_kelvin" and level is not None:
        kelvin = max(2000, min(6500, int(level)))
        await hass.services.async_call(
            "light",
            "turn_on",
            {ATTR_ENTITY_ID: entity_id, "color_temp_kelvin": kelvin},
            blocking=False,
        )
        return

    if domain == "climate" and action in ("heat", "cool", "heat_cool", "auto", "off"):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {ATTR_ENTITY_ID: entity_id, "hvac_mode": action},
            blocking=False,
        )
        return

    if domain == "lock":
        svc_l = "unlock" if (action == "unlock" or (action == "toggle" and state_obj.state == "locked")) else "lock"
        await hass.services.async_call("lock", svc_l, {ATTR_ENTITY_ID: entity_id}, blocking=False)
        return

    if domain == "vacuum":
        svc_v = "return_to_base" if action in ("dock", "return_to_base") else ("pause" if action == "pause" else "start")
        await hass.services.async_call("vacuum", svc_v, {ATTR_ENTITY_ID: entity_id}, blocking=False)
        return

    if action == "set_level" and level is not None:
        lvl = max(0, min(100, int(level)))
        if domain == "light":
            if lvl == 0:
                await hass.services.async_call(
                    "light", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=False
                )
            else:
                await hass.services.async_call(
                    "light",
                    "turn_on",
                    {ATTR_ENTITY_ID: entity_id, "brightness_pct": lvl},
                    blocking=False,
                )
            return
        if domain == "cover":
            await hass.services.async_call(
                "cover",
                "set_cover_position",
                {ATTR_ENTITY_ID: entity_id, "position": lvl},
                blocking=False,
            )
            return
        if domain == "fan":
            if lvl == 0:
                await hass.services.async_call(
                    "fan", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=False
                )
            else:
                await hass.services.async_call(
                    "fan",
                    "set_percentage",
                    {ATTR_ENTITY_ID: entity_id, "percentage": lvl},
                    blocking=False,
                )
            return
        if domain == "climate":
            await hass.services.async_call(
                "climate",
                "set_temperature",
                {ATTR_ENTITY_ID: entity_id, "temperature": float(lvl)},
                blocking=False,
            )
            return
        if domain == "media_player":
            await hass.services.async_call(
                "media_player",
                "volume_set",
                {ATTR_ENTITY_ID: entity_id, "volume_level": round(lvl / 100.0, 2)},
                blocking=False,
            )
            return

    if action == "turn_on":
        svc = "open_cover" if domain == "cover" else "turn_on"
        await hass.services.async_call(
            domain, svc, {ATTR_ENTITY_ID: entity_id}, blocking=False
        )
    elif action == "turn_off":
        svc = "close_cover" if domain == "cover" else "turn_off"
        await hass.services.async_call(
            domain, svc, {ATTR_ENTITY_ID: entity_id}, blocking=False
        )
    else:
        svc = "media_play_pause" if domain == "media_player" else "toggle"
        if domain == "cover":
            svc = (
                "close_cover"
                if state_obj.state == STATE_OPEN
                else "open_cover"
            )
        await hass.services.async_call(
            domain, svc, {ATTR_ENTITY_ID: entity_id}, blocking=False
        )