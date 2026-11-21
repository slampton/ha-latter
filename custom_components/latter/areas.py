"""Curated Area Discovery, Entity Filtering, Telemetry, Actions & Area Context v3 Builder."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
import logging
import math
import re
import time
from typing import Any

from homeassistant.components.lock import LockEntityFeature
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_ON,
    STATE_OPEN,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.util import dt as dt_util

from .cameras import resolve_camera_capabilities
from .const import (
    AMBIENT_LIGHT_DEADBAND_PCT,
    CONF_ALARM_ENTITY,
    CONF_AREA_ILLUMINANCE_CONFIG,
    CONF_BROADCAST_SPEAKERS,
    CONF_DEFAULT_AREA,
    CONF_ESPHOME_DEVICE_ID,
    DATA_GLOBAL_CONFIG,
    DEFAULT_AREA_BRIGHT_LUX,
    DEFAULT_AREA_DARK_LUX,
    DEFAULT_BROADCAST_PHRASES,
    DOMAIN,
    SUBENTRY_DEVICE,
)
from .groups import _apply_ha_display_precision
from .hub import get_area_state_index, is_media_position_only_tick, iter_coordinators
from .identity import resolve_bound_esphome_device_id
from .media import async_execute_volume_action
from .media_browse import is_music_assistant_player
from .presence import get_ble_proxy_area_ids, get_ble_signature_area_ids
from .protocol import (
    AREA_CLIMATES_MAX_RECORDS,
    CAMERAS_MAX_RECORDS,
    DEFAULT_AREA_CATEGORIES,
    DEFAULT_HOME_CATEGORIES,
    GARAGES_MAX_RECORDS,
    LOCKS_MAX_RECORDS,
    THERMOSTATS_MAX_RECORDS,
    VACUUMS_MAX_RECORDS,
    V3Records,
    activity_payload,
    area_climate_records,
    broadcast_phrase_records,
    build_time_zone_payloads,
    camera_records,
    entry_records,
    ha_value,
    parse_area_categories,
    parse_home_categories,
    thermostat_records,
    vacuum_records,
)

_LOGGER = logging.getLogger(__name__)

AREA_CONTROL_DOMAINS: tuple[str, ...] = (
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


def resolve_entity_area_id(
    hass: HomeAssistant,
    entity_id: str,
    *,
    ent_reg: er.EntityRegistry | None = None,
    dev_reg: dr.DeviceRegistry | None = None,
) -> str | None:
    """Resolve the Home Assistant area_id for an entity (directly or via device)."""
    if ent_reg is None and dev_reg is None:
        return get_area_state_index(hass).resolve_entity_area_id(entity_id)
    if ent_reg is None:
        ent_reg = er.async_get(hass)

    entry = ent_reg.async_get(entity_id)
    if entry is None:
        return None
    if entry.area_id:
        return str(entry.area_id)
    if entry.device_id:
        if dev_reg is None:
            dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(entry.device_id)
        if device and device.area_id:
            return str(device.area_id)
    return None


def match_area_by_name_or_id(
    hass: HomeAssistant, raw_value: str
) -> str | None:
    """Match an Area name, slug, or area_id to a valid HA area_id (exact match only; no substring guessing)."""
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
            return str(area.id)

    return None


def latter_bound_esphome_device_ids(hass: HomeAssistant) -> set[str]:
    """Return the ESPHome device IDs bound to Latter Devices (each Device subentry's stored device ID / MAC)."""
    out: set[str] = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        for sub in entry.subentries.values():
            if sub.subentry_type != SUBENTRY_DEVICE:
                continue
            dev_id = resolve_bound_esphome_device_id(
                hass,
                str(sub.data.get(CONF_ESPHOME_DEVICE_ID) or "") or None,
                str(sub.data.get("mac") or "") or None,
            )
            if dev_id:
                out.add(dev_id)
    return out


def sync_esphome_device_area(
    hass: HomeAssistant,
    esphome_device_id: str,
    area_id: str | None,
    require_ble_proxy_area: bool = True,
    *,
    allow_clear: bool = False,
) -> dict[str, Any] | None:
    """Update the bound ESPHome device's (and child Latter device's) area_id in HA Device Registry."""
    norm_area: str | None = str(area_id or "").strip() or None
    if not esphome_device_id or (norm_area is None and not allow_clear):
        return None

    if require_ble_proxy_area and norm_area is not None:
        ble_areas = get_ble_proxy_area_ids(hass) | get_ble_signature_area_ids(hass)
        if ble_areas and norm_area not in ble_areas:
            _LOGGER.debug(
                "Skipping Device Registry area sync to '%s' because that area has no BLE proxy or signature.",
                norm_area,
            )
            return None

    dev_reg = dr.async_get(hass)
    dev = dev_reg.async_get(esphome_device_id)
    domain_data = hass.data.setdefault(DOMAIN, {})
    own_writes: dict[str, tuple[str, float]] = domain_data.setdefault(
        "_own_area_writes", {}
    )
    now_mono = time.monotonic()
    record: dict[str, Any] | None = None

    esp_mac: str | None = None
    if dev is not None:
        for ctype, cval in dev.connections:
            if ctype == dr.CONNECTION_NETWORK_MAC and cval:
                esp_mac = dr.format_mac(str(cval))
                break
        if dev.area_id != norm_area:
            prev_area = str(dev.area_id or "")
            own_writes[esphome_device_id] = (norm_area or "", now_mono)
            dev_reg.async_update_device(esphome_device_id, area_id=norm_area)
            record = {
                "timestamp": dt_util.now().isoformat(timespec="seconds"),
                "from_area": prev_area,
                "to_area": norm_area or "",
                "device_id": esphome_device_id,
            }
            _LOGGER.debug(
                "Synced bound ESPHome device id=%s to area_id='%s'",
                esphome_device_id,
                norm_area or "",
            )

    for entry in hass.config_entries.async_entries(DOMAIN):
        for child in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            if (DOMAIN, "system") in child.identifiers:
                continue
            if (
                child.via_device_id == esphome_device_id
                or (esp_mac and (DOMAIN, esp_mac) in child.identifiers)
            ) and child.area_id != norm_area:
                prev_child = str(child.area_id or "")
                own_writes[child.id] = (norm_area or "", now_mono)
                dev_reg.async_update_device(child.id, area_id=norm_area)
                if record is None:
                    record = {
                        "timestamp": dt_util.now().isoformat(timespec="seconds"),
                        "from_area": prev_child,
                        "to_area": norm_area or "",
                        "device_id": esphome_device_id,
                    }
    return record


def _is_curated_area_entity(
    hass: HomeAssistant,
    state_obj: State,
    local_speaker: str = "",
    *,
    ent_reg: er.EntityRegistry | None = None,
    bound_device_ids: set[str] | None = None,
) -> bool:
    """Filter out config/diagnostic entities, companion display backlights/switches, and non-MA speakers."""
    if ent_reg is None:
        ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(state_obj.entity_id)
    if entry is not None:
        if entry.disabled_by or entry.hidden_by:
            return False
        if entry.entity_category is not None:
            return False

    domain = state_obj.domain
    attrs = state_obj.attributes
    dev_class = str(attrs.get("device_class") or "").lower()

    if entry is not None and entry.device_id:
        if bound_device_ids is None:
            bound_device_ids = latter_bound_esphome_device_ids(hass)
        if entry.device_id in bound_device_ids:
            return False

    if domain in ("light", "scene", "fan", "climate"):
        return True

    if domain == "cover":
        name_low = str(attrs.get("friendly_name") or state_obj.entity_id).lower()
        if any(
            k in name_low
            for k in (
                "curtain",
                "drape",
                "sheer",
                "blind",
                "shade",
                "shutter",
                "window",
            )
        ):
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
            return max(1, min(100, round((float(bri) / 255.0) * 100)))
        return 100

    if domain == "cover":
        pos = attrs.get("current_position")
        if pos is not None:
            return max(0, min(100, round(float(pos))))
        return 100 if state_obj.state == STATE_OPEN else 0

    if domain == "fan":
        if not is_active:
            return 0
        pct = attrs.get("percentage")
        if pct is not None:
            return max(0, min(100, round(float(pct))))
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
            return f"{friendly} ({round(float(tgt))}°)"
        if cur is not None:
            return f"{friendly} ({round(float(cur))}°)"
    if domain == "fan" and state_obj.state == STATE_ON and level >= 0:
        return f"{friendly} ({level}%)"
    if domain == "media_player":
        return f"Speaker: {friendly}"
    if domain == "alarm_control_panel":
        return f"Alarm: {state_obj.state.replace('_', ' ').title()}"
    return friendly


def get_area_climate_telemetry(
    hass: HomeAssistant, area_id: str | None
) -> dict[str, Any]:
    """Discover ambient area temperature and humidity assigned to an area via AreaStateIndex."""
    result: dict[str, Any] = {
        "temperature": None,
        "temperature_unit": "",
        "humidity": None,
    }
    if not area_id:
        return result

    idx = get_area_state_index(hass)
    ent_reg = er.async_get(hass)
    latter_dev_ids = latter_bound_esphome_device_ids(hass)

    for state_obj in sorted(
        idx.entities_in_area(area_id, ("sensor",)), key=lambda s: s.entity_id
    ):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue

        entry = ent_reg.async_get(state_obj.entity_id)
        if entry is not None:
            if entry.disabled_by or entry.hidden_by:
                continue
            if entry.entity_category is not None:
                continue
            if entry.device_id and entry.device_id in latter_dev_ids:
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
        if result["temperature"] is not None and result["humidity"] is not None:
            break

    if result["temperature"] is None or result["humidity"] is None:
        for state_obj in sorted(
            idx.entities_in_area(area_id, ("climate",)), key=lambda s: s.entity_id
        ):
            if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            attrs = state_obj.attributes
            if (
                result["temperature"] is None
                and attrs.get("current_temperature") is not None
            ):
                try:
                    result["temperature"] = round(
                        float(attrs["current_temperature"]), 1
                    )
                except ValueError:
                    pass
            if (
                result["humidity"] is None
                and attrs.get("current_humidity") is not None
            ):
                try:
                    result["humidity"] = round(float(attrs["current_humidity"]), 1)
                except ValueError:
                    pass
            if result["temperature"] is not None and result["humidity"] is not None:
                break

    return result


def normalize_ambient_lux(
    lux: float,
    dark_lux: float = DEFAULT_AREA_DARK_LUX,
    bright_lux: float = DEFAULT_AREA_BRIGHT_LUX,
) -> int:
    """Map an illuminance reading (`lx`) onto a perceptual `0..100` level between `dark_lux` and `bright_lux`."""
    if not math.isfinite(lux):
        return 0
    lo = max(0.0, float(dark_lux)) if math.isfinite(dark_lux) else DEFAULT_AREA_DARK_LUX
    hi = max(lo + 1.0, float(bright_lux)) if math.isfinite(bright_lux) else max(lo + 1.0, DEFAULT_AREA_BRIGHT_LUX)
    above = max(0.0, float(lux) - lo)
    span = max(1.0, hi - lo)
    norm = math.log1p(above) / math.log1p(span)
    return max(0, min(100, round(norm * 100.0)))


def format_ambient_lux(lux: float) -> str:
    """Format a lux reading compactly for Protocol v3 and Studio (`0`, `5.6`, `42`)."""
    if not math.isfinite(lux) or lux < 0.05:
        return "0"
    clamped = min(100000.0, float(lux))
    if clamped < 10.0:
        formatted = f"{clamped:.1f}".rstrip("0").rstrip(".")
        return formatted or "0"
    return str(round(clamped))


def area_illuminance_settings(
    hass: HomeAssistant, area_id: str | None
) -> dict[str, Any]:
    """Return effective ambient light calibration settings for one Area."""
    entity_id = "auto"
    dark_lux = float(DEFAULT_AREA_DARK_LUX)
    bright_lux = float(DEFAULT_AREA_BRIGHT_LUX)
    if area_id:
        global_cfg = (hass.data.get(DOMAIN) or {}).get(DATA_GLOBAL_CONFIG) or {}
        raw_map = global_cfg.get(CONF_AREA_ILLUMINANCE_CONFIG)
        if isinstance(raw_map, Mapping):
            entry = raw_map.get(area_id)
            if isinstance(entry, Mapping):
                raw_ent = str(entry.get("entity_id") or "").strip()
                if raw_ent:
                    entity_id = raw_ent
                try:
                    if entry.get("dark_lux") is not None:
                        dark_lux = max(0.0, min(500.0, float(entry["dark_lux"])))
                except (TypeError, ValueError):
                    pass
                try:
                    if entry.get("bright_lux") is not None:
                        bright_lux = max(dark_lux + 1.0, min(100000.0, float(entry["bright_lux"])))
                except (TypeError, ValueError):
                    pass
    if bright_lux < dark_lux + 1.0:
        bright_lux = dark_lux + 1.0
    return {
        "entity_id": entity_id,
        "dark_lux": round(dark_lux, 2),
        "bright_lux": round(bright_lux, 1),
    }


def _parse_illuminance_state(state_obj: State | None) -> float | None:
    """Parse a finite non-negative numeric illuminance value from `state_obj`, or None."""
    if state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
        return None
    try:
        val = float(state_obj.state)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(val) or val < 0.0:
        return None
    return val


def area_illuminance_sensor_choices(
    hass: HomeAssistant, area_id: str | None
) -> list[dict[str, Any]]:
    """Return illuminance (`lx`) sensor choices assigned to `area_id`."""
    if not area_id:
        return []
    idx = get_area_state_index(hass)
    ent_reg = er.async_get(hass)
    latter_dev_ids = latter_bound_esphome_device_ids(hass)
    choices: list[dict[str, Any]] = []
    for state_obj in sorted(
        idx.entities_in_area(area_id, ("sensor",)), key=lambda s: s.entity_id
    ):
        entry = ent_reg.async_get(state_obj.entity_id)
        if entry is not None:
            if entry.disabled_by or entry.hidden_by:
                continue
            if entry.entity_category is not None:
                continue
            if entry.device_id and entry.device_id in latter_dev_ids:
                continue
        attrs = state_obj.attributes
        dev_class = str(attrs.get("device_class") or "").lower()
        unit = str(attrs.get("unit_of_measurement") or "").strip().lower()
        if dev_class != "illuminance" and unit not in ("lx", "lux"):
            continue
        lux_val = _parse_illuminance_state(state_obj)
        choices.append(
            {
                "entity_id": state_obj.entity_id,
                "name": str(attrs.get("friendly_name") or state_obj.entity_id),
                "lux": lux_val,
                "lux_display": format_ambient_lux(lux_val) if lux_val is not None else "",
                "available": lux_val is not None,
            }
        )
    return choices


def resolve_area_ambient_light(
    hass: HomeAssistant, area_id: str | None
) -> dict[str, Any]:
    """Resolve active Area illuminance reading and calibrated Protocol v3 `area_ambient_light` payload."""
    cfg = area_illuminance_settings(hass, area_id)
    dark_lux = float(cfg["dark_lux"])
    bright_lux = float(cfg["bright_lux"])
    configured_ent = str(cfg["entity_id"] or "auto")
    out: dict[str, Any] = {
        "configured_entity": configured_ent,
        "resolved_entity": "",
        "resolved_name": "",
        "lux": None,
        "lux_display": "",
        "ambient_pct": None,
        "dark_lux": dark_lux,
        "bright_lux": bright_lux,
        "wire": "",
    }
    if not area_id or configured_ent == "disabled":
        return out

    chosen_state: State | None = None
    chosen_eid = ""
    if configured_ent != "auto":
        st = hass.states.get(configured_ent)
        lux_val = _parse_illuminance_state(st)
        if st is not None:
            chosen_eid = configured_ent
            out["resolved_entity"] = configured_ent
            out["resolved_name"] = str(st.attributes.get("friendly_name") or configured_ent)
            if lux_val is not None:
                chosen_state = st
    else:
        choices = area_illuminance_sensor_choices(hass, area_id)
        for item in choices:
            if item["available"]:
                chosen_eid = str(item["entity_id"])
                chosen_state = hass.states.get(chosen_eid)
                out["resolved_entity"] = chosen_eid
                out["resolved_name"] = str(item["name"])
                break
        if not chosen_eid and choices:
            out["resolved_entity"] = str(choices[0]["entity_id"])
            out["resolved_name"] = str(choices[0]["name"])

    lux_val = _parse_illuminance_state(chosen_state)
    if lux_val is None:
        return out

    ambient_pct = normalize_ambient_lux(lux_val, dark_lux, bright_lux)
    lux_disp = format_ambient_lux(lux_val)
    out["lux"] = lux_val
    out["lux_display"] = lux_disp
    out["ambient_pct"] = ambient_pct
    out["wire"] = f"{ambient_pct}|{lux_disp}"
    return out


def apply_ambient_light_deadband(
    prev: tuple[str, int | None, str],
    area_id: str,
    ambient_pct: int | None,
    wire: str,
    *,
    deadband_pct: int = AMBIENT_LIGHT_DEADBAND_PCT,
) -> tuple[str, int | None, str]:
    """Suppress minor ambient-lux jitter within the same Area to keep Protocol v3 quiet."""
    prev_area, prev_pct, _prev_wire = prev
    if (
        area_id != prev_area
        or (prev_pct is None) != (ambient_pct is None)
        or ambient_pct is None
        or prev_pct is None
    ):
        return (area_id, ambient_pct, wire)
    if ambient_pct in (0, 100) and ambient_pct != prev_pct:
        return (area_id, ambient_pct, wire)
    if abs(ambient_pct - prev_pct) >= max(1, int(deadband_pct)):
        return (area_id, ambient_pct, wire)
    return prev


def compute_alarm_caps(state_obj: State | None) -> int:
    """Compute Protocol v3 `alarm_caps` u16 bitmask from an `alarm_control_panel` state."""
    if state_obj is None:
        return 0
    attrs = state_obj.attributes
    has_code_format = bool(attrs.get("code_format"))
    caps = 0
    if has_code_format:
        caps |= 0x01
        if bool(attrs.get("code_arm_required", False)):
            caps |= 0x02
    sf = int(attrs.get("supported_features", 0) or 0)
    if bool(sf & 1) or sf == 0:
        caps |= 0x04
    if bool(sf & 2) or sf == 0:
        caps |= 0x08
    if bool(sf & 4):
        caps |= 0x10
    if bool(sf & 32):
        caps |= 0x20
    return caps


def compute_climate_caps(state_obj: State | None) -> int:
    """Compute Protocol v3 `climate_caps` u16 bitmask from a `climate` state."""
    if state_obj is None:
        return 0
    attrs = state_obj.attributes
    hvac_modes = [str(m).lower() for m in (attrs.get("hvac_modes") or [])]
    sf = int(attrs.get("supported_features", 0) or 0)
    caps = 0
    if "off" in hvac_modes:
        caps |= 0x01
    if "heat" in hvac_modes:
        caps |= 0x02
    if "cool" in hvac_modes:
        caps |= 0x04
    if "heat_cool" in hvac_modes or "auto" in hvac_modes:
        caps |= 0x08
    if "fan_only" in hvac_modes:
        caps |= 0x10
    if "dry" in hvac_modes:
        caps |= 0x20
    if (
        bool(sf & 1)
        or bool(sf & 2)
        or attrs.get("temperature") is not None
        or attrs.get("target_temp_low") is not None
    ):
        caps |= 0x40
    if str(attrs.get("temperature_unit") or "").upper().endswith("C"):
        caps |= 0x80
    return caps


def compute_vacuum_caps(state_obj: State | None) -> int:
    """Compute Protocol v3 `vacuum_caps` u16 bitmask from a `vacuum` state."""
    if state_obj is None:
        return 0
    sf = int(state_obj.attributes.get("supported_features", 0) or 0)
    if sf == 0:
        return 0x0B
    caps = 0
    if bool(sf & 8192) or bool(sf & 1):
        caps |= 0x01
    if bool(sf & 4):
        caps |= 0x02
    if bool(sf & 8) or bool(sf & 2):
        caps |= 0x04
    if bool(sf & 16):
        caps |= 0x08
    if bool(sf & 1024):
        caps |= 0x10
    if bool(sf & 512):
        caps |= 0x20
    return caps


def get_home_alarm_summary(
    hass: HomeAssistant, configured_alarm_entity: str | None = None
) -> dict[str, Any]:
    """Return the explicitly configured home security alarm_control_panel summary."""
    clean_alarm = str(configured_alarm_entity or "").strip()
    if clean_alarm:
        state_obj = hass.states.get(clean_alarm)
        if state_obj is not None:
            return {
                "entity_id": state_obj.entity_id,
                "state": ha_value(state_obj.state),
                "name": str(
                    state_obj.attributes.get("friendly_name") or "Home Alarm"
                ),
                "supported_features": int(
                    state_obj.attributes.get("supported_features") or 0
                ),
                "code_arm_required": bool(
                    state_obj.attributes.get("code_arm_required", False)
                ),
                "alarm_caps": compute_alarm_caps(state_obj),
            }
    return {
        "entity_id": "",
        "state": "",
        "name": "",
        "supported_features": 0,
        "code_arm_required": False,
        "alarm_caps": 0,
    }


def _extract_climate_temps(state_obj: State) -> tuple[int | float | None, float | None]:
    """Extract target setpoint (or target_temp_low/high midpoint) and current temperature."""
    tgt_out: int | float | None = None
    cur_out: float | None = None
    tgt_t = state_obj.attributes.get("temperature")
    if tgt_t is not None:
        try:
            val_f = round(float(tgt_t), 1)
            tgt_out = int(val_f) if val_f.is_integer() else val_f
        except (ValueError, TypeError):
            pass
    else:
        low_t = state_obj.attributes.get("target_temp_low")
        high_t = state_obj.attributes.get("target_temp_high")
        if low_t is not None and high_t is not None:
            try:
                mid_f = round((float(low_t) + float(high_t)) / 2.0, 1)
                tgt_out = int(mid_f) if mid_f.is_integer() else mid_f
            except (ValueError, TypeError):
                pass
        elif low_t is not None:
            try:
                val_f = round(float(low_t), 1)
                tgt_out = int(val_f) if val_f.is_integer() else val_f
            except (ValueError, TypeError):
                pass
    cur_t = state_obj.attributes.get("current_temperature")
    if cur_t is not None:
        try:
            cur_out = round(float(cur_t), 1)
        except (ValueError, TypeError):
            pass
    return tgt_out, cur_out


def _clean_configured_ids(raw: Iterable[str] | None, limit: int) -> list[str]:
    if not raw or isinstance(raw, (str, bytes)):
        return []
    out: list[str] = []
    for item in raw:
        s = str(item or "").strip()
        if s and s not in out:
            out.append(s)
    return out[:limit]


def get_home_hub_summary(
    hass: HomeAssistant,
    thermostat_entities: Iterable[str] | None = None,
    lock_entities: Iterable[str] | None = None,
    garage_entities: Iterable[str] | None = None,
    vacuum_entities: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Resolve explicitly configured multi-entity Home Hub Thermostats, Locks, Garage Doors, and Vacuums."""
    idx = get_area_state_index(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    def _area_of(ent_id: str) -> str:
        if idx.started:
            return idx.resolve_entity_area_id(ent_id) or ""
        return (
            resolve_entity_area_id(
                hass, ent_id, ent_reg=ent_reg, dev_reg=dev_reg
            )
            or ""
        )

    thermostats: list[dict[str, Any]] = []
    for ent_id in _clean_configured_ids(thermostat_entities, THERMOSTATS_MAX_RECORDS):
        t_st = hass.states.get(ent_id)
        if t_st is None:
            continue
        tgt_temp, cur_temp = _extract_climate_temps(t_st)
        thermostats.append(
            {
                "entity_id": t_st.entity_id,
                "name": str(t_st.attributes.get("friendly_name") or t_st.entity_id),
                "area_id": _area_of(t_st.entity_id),
                "state": ha_value(t_st.state),
                "target_temp": tgt_temp,
                "current_temp": cur_temp,
                "caps": compute_climate_caps(t_st),
            }
        )

    locks: list[dict[str, Any]] = []
    for ent_id in _clean_configured_ids(lock_entities, LOCKS_MAX_RECORDS):
        l_st = hass.states.get(ent_id)
        if l_st is None:
            continue
        locks.append(
            {
                "entity_id": l_st.entity_id,
                "name": str(l_st.attributes.get("friendly_name") or l_st.entity_id),
                "area_id": _area_of(l_st.entity_id),
                "state": ha_value(l_st.state),
            }
        )

    garages: list[dict[str, Any]] = []
    for ent_id in _clean_configured_ids(garage_entities, GARAGES_MAX_RECORDS):
        g_st = hass.states.get(ent_id)
        if g_st is None:
            continue
        garages.append(
            {
                "entity_id": g_st.entity_id,
                "name": str(g_st.attributes.get("friendly_name") or g_st.entity_id),
                "area_id": _area_of(g_st.entity_id),
                "state": ha_value(g_st.state),
            }
        )

    vacuums: list[dict[str, Any]] = []
    for ent_id in _clean_configured_ids(vacuum_entities, VACUUMS_MAX_RECORDS):
        v_st = hass.states.get(ent_id)
        if v_st is None:
            continue
        vacuums.append(
            {
                "entity_id": v_st.entity_id,
                "name": str(v_st.attributes.get("friendly_name") or v_st.entity_id),
                "area_id": _area_of(v_st.entity_id),
                "state": ha_value(v_st.state),
                "caps": compute_vacuum_caps(v_st),
            }
        )

    return {
        "thermostats": thermostats,
        "thermostats_summary": thermostat_records(thermostats),
        "locks": locks,
        "locks_summary": entry_records(locks, LOCKS_MAX_RECORDS),
        "garages": garages,
        "garages_summary": entry_records(garages, GARAGES_MAX_RECORDS),
        "vacuums": vacuums,
        "vacuums_summary": vacuum_records(vacuums),
    }


def get_home_wide_entities(
    hass: HomeAssistant,
    configured_alarm_entity: str | None = None,
) -> list[dict[str, Any]]:
    """Return home-wide security alarm entities (`mode='home'`)."""
    items: list[dict[str, Any]] = []

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

    return items


def get_areas_summary(
    hass: HomeAssistant,
    active_area_id: str | None = None,
    local_speaker: str = "",
) -> list[dict[str, Any]]:
    """Return a sorted list of Home Assistant areas that contain curated controllable entities."""
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    idx = get_area_state_index(hass)
    bound_device_ids = latter_bound_esphome_device_ids(hass)

    items: list[dict[str, Any]] = []
    for area in area_reg.async_list_areas():
        total = 0
        lights_on = 0
        area_temp: int | float | None = None
        climate_fallback: float | None = None

        for state_obj in sorted(
            idx.entities_in_area(area.id, ("sensor",)), key=lambda s: s.entity_id
        ):
            if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            if (
                str(state_obj.attributes.get("device_class") or "").lower()
                != "temperature"
            ):
                continue
            entry = ent_reg.async_get(state_obj.entity_id)
            if entry is not None:
                if (
                    entry.disabled_by
                    or entry.hidden_by
                    or entry.entity_category is not None
                ):
                    continue
                if entry.device_id and entry.device_id in bound_device_ids:
                    continue
            try:
                area_temp = _apply_ha_display_precision(
                    entry, float(state_obj.state), default_precision=0
                )
                break
            except ValueError:
                pass

        for state_obj in idx.entities_in_area(area.id, AREA_CONTROL_DOMAINS):
            if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            if not _is_curated_area_entity(
                hass,
                state_obj,
                local_speaker,
                ent_reg=ent_reg,
                bound_device_ids=bound_device_ids,
            ):
                continue
            total += 1
            if state_obj.domain == "light" and state_obj.state == STATE_ON:
                lights_on += 1
            elif (
                state_obj.domain == "climate"
                and climate_fallback is None
                and state_obj.attributes.get("current_temperature") is not None
            ):
                try:
                    climate_fallback = round(
                        float(state_obj.attributes["current_temperature"]), 1
                    )
                except ValueError:
                    pass

        if total == 0:
            continue
        temp_val = area_temp if area_temp is not None else climate_fallback
        suffix_parts: list[str] = []
        if temp_val is not None:
            suffix_parts.append(f"{round(temp_val)}°")
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
    """Parse a single domain, comma-separated domain list, or alias into allowed domains."""
    raw = domain_filter.strip().lower()
    if not raw or raw == "all":
        return AREA_CONTROL_DOMAINS
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
            if p.strip() in AREA_CONTROL_DOMAINS
        ]
        if parts:
            return tuple(parts)
    if raw in AREA_CONTROL_DOMAINS:
        return (raw,)
    return AREA_CONTROL_DOMAINS


def get_area_available_domains(
    hass: HomeAssistant,
    area_id: str | None,
    local_speaker: str = "",
    entities: list[dict[str, Any]] | None = None,
    area_categories: str | None = None,
) -> str:
    """Return comma-separated enabled Area categories present in the active Area, in configured order."""
    all_items = (
        entities
        if entities is not None
        else get_area_entities(
            hass,
            area_id=area_id,
            domain_filter="all",
            local_speaker=local_speaker,
        )
    )
    if not all_items:
        return ""
    configured = parse_area_categories(area_categories) or list(
        parse_area_categories(DEFAULT_AREA_CATEGORIES)
    )
    present_types = {str(it.get("type") or "") for it in all_items}
    ordered: list[str] = []
    for tok in configured:
        if tok == "scene" and ("scene" in present_types or "script" in present_types):
            ordered.append("scene")
        elif tok in ("light", "cover", "fan", "climate") and tok in present_types:
            ordered.append(tok)
        elif tok == "switch" and (
            "switch" in present_types or "input_boolean" in present_types
        ):
            ordered.append("switch")
        elif tok == "media" and "media_player" in present_types:
            ordered.append("media")
        elif tok == "all":
            ordered.append("all")
    return ",".join(ordered)


def _is_intercom_available(
    hass: HomeAssistant | None,
    coordinator: Any,
    hub_info: Mapping[str, Any],
) -> bool:
    """Return True when Broadcast has at least one configured speaker for this Device."""
    if hub_info.get("intercom_available"):
        return True
    if coordinator is not None:
        eff_speakers = getattr(coordinator, "effective_broadcast_speakers", None)
        if isinstance(eff_speakers, (list, tuple)):
            return bool(eff_speakers)
    hass_obj = hass or (
        getattr(coordinator, "hass", None) if coordinator is not None else None
    )
    if hass_obj is not None:
        domain_data = getattr(hass_obj, "data", {}).get(DOMAIN)
        if isinstance(domain_data, Mapping):
            global_cfg = domain_data.get("global_config")
            if isinstance(global_cfg, Mapping):
                raw_spks = global_cfg.get(CONF_BROADCAST_SPEAKERS)
                if isinstance(raw_spks, (list, tuple)) and any(
                    str(s or "").strip().startswith("media_player.") for s in raw_spks
                ):
                    return True
    return False


def get_available_home_categories(
    alarm_info: Mapping[str, Any],
    hub_info: Mapping[str, Any],
    home_categories: str | None = None,
    *,
    coordinator: Any = None,
    hass: HomeAssistant | None = None,
    has_intercom: bool | None = None,
) -> str:
    """Return comma-separated enabled Home Hub categories that have at least one configured/discovered entity."""
    configured = parse_home_categories(home_categories) or list(
        parse_home_categories(DEFAULT_HOME_CATEGORIES)
    )
    intercom_ok = (
        has_intercom
        if has_intercom is not None
        else _is_intercom_available(hass, coordinator, hub_info)
    )
    ordered: list[str] = []
    for tok in configured:
        if tok == "alarm" and alarm_info.get("entity_id"):
            ordered.append("alarm")
        elif tok == "intercom" and intercom_ok:
            ordered.append("intercom")
        elif tok == "thermostat" and hub_info.get("thermostats"):
            ordered.append("thermostat")
        elif tok == "entry" and (
            hub_info.get("locks") or hub_info.get("garages")
        ):
            ordered.append("entry")
        elif tok == "vacuum" and hub_info.get("vacuums"):
            ordered.append("vacuum")
    return ",".join(ordered)


def get_area_entities(
    hass: HomeAssistant,
    area_id: str | None,
    domain_filter: str = "all",
    local_speaker: str = "",
) -> list[dict[str, Any]]:
    """Return curated controllable entities for a specific area via AreaStateIndex."""
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    idx = get_area_state_index(hass)
    bound_device_ids = latter_bound_esphome_device_ids(hass)
    area_entry = area_reg.async_get_area(area_id) if area_id else None
    area_name = area_entry.name if area_entry else ""

    allowed_domains = _parse_domain_filter(domain_filter)
    items: list[dict[str, Any]] = []

    domain_priority = {
        "light": 1,
        "cover": 2,
        "fan": 3,
        "scene": 4,
        "climate": 5,
        "switch": 6,
        "input_boolean": 6,
        "media_player": 7,
    }

    if area_id:
        candidate_states = idx.entities_in_area(area_id, allowed_domains)
    else:
        candidate_states = []
        for dom in allowed_domains:
            candidate_states.extend(idx.states_for_domain(dom))

    for state_obj in candidate_states:
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue

        if not _is_curated_area_entity(
            hass,
            state_obj,
            local_speaker,
            ent_reg=ent_reg,
            bound_device_ids=bound_device_ids,
        ):
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
        if state_obj.domain == "climate" and level < 0:
            tgt_val, _ = _extract_climate_temps(state_obj)
            if tgt_val is not None:
                level = round(float(tgt_val))
        items.append(
            {
                "name": format_entity_slot_name(state_obj, area_name),
                "id": state_obj.entity_id,
                "type": state_obj.domain,
                "active": is_active,
                "level": level,
                "_prio": domain_priority.get(state_obj.domain, 99),
            }
        )

    items.sort(key=lambda x: (x["_prio"], not x["active"], x["name"].lower()))
    return items


def get_area_climates_summary(
    hass: HomeAssistant,
    area_id: str | None,
    local_speaker: str = "",
) -> V3Records:
    """Return `area_climate_records` for curated `climate.*` entities in `area_id`."""
    if not area_id:
        return area_climate_records(())
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    idx = get_area_state_index(hass)
    bound_device_ids = latter_bound_esphome_device_ids(hass)
    area_entry = area_reg.async_get_area(area_id)
    area_name = area_entry.name if area_entry else ""

    rows: list[dict[str, Any]] = []
    for state_obj in sorted(
        idx.entities_in_area(area_id, ("climate",)), key=lambda s: s.entity_id
    ):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        if not _is_curated_area_entity(
            hass,
            state_obj,
            local_speaker,
            ent_reg=ent_reg,
            bound_device_ids=bound_device_ids,
        ):
            continue
        tgt_temp, cur_temp = _extract_climate_temps(state_obj)
        friendly = str(state_obj.attributes.get("friendly_name") or state_obj.entity_id)
        if area_name and friendly.lower().startswith(area_name.lower() + " "):
            friendly = friendly[len(area_name) + 1 :].strip() or friendly
        rows.append(
            {
                "entity_id": state_obj.entity_id,
                "name": friendly,
                "state": ha_value(state_obj.state),
                "target_temp": tgt_temp,
                "current_temp": cur_temp,
                "caps": compute_climate_caps(state_obj),
            }
        )
        if len(rows) >= AREA_CLIMATES_MAX_RECORDS:
            break
    return area_climate_records(rows)


def find_area_media_entities(
    hass: HomeAssistant, area_id: str | None, local_speaker: str
) -> dict[str, str]:
    """Discover the primary Music Assistant speaker and TV/remote entity inside an area."""
    result = {"speaker": "", "remote": ""}
    if not area_id:
        return result

    idx = get_area_state_index(hass)
    for state_obj in sorted(
        idx.entities_in_area(area_id, ("media_player",)), key=lambda s: s.entity_id
    ):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        if state_obj.entity_id == local_speaker:
            continue
        if is_music_assistant_player(hass, state_obj) and not result["speaker"]:
            result["speaker"] = state_obj.entity_id
        dev_class = str(state_obj.attributes.get("device_class") or "").lower()
        if dev_class == "tv" and not result["remote"]:
            result["remote"] = state_obj.entity_id

    for state_obj in sorted(
        idx.entities_in_area(area_id, ("remote",)), key=lambda s: s.entity_id
    ):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        result["remote"] = state_obj.entity_id
        break

    return result


_ALARM_ACTION_ALIASES: dict[str, str] = {
    "disarm": "disarm",
    "alarm_disarm": "disarm",
    "arm_home": "arm_home",
    "alarm_arm_home": "arm_home",
    "arm_away": "arm_away",
    "alarm_arm_away": "arm_away",
    "arm_night": "arm_night",
    "alarm_arm_night": "arm_night",
    "arm_vacation": "arm_vacation",
    "alarm_arm_vacation": "arm_vacation",
}

_CLIMATE_HVAC_MAP: dict[str, str] = {
    "heat": "heat",
    "hvac_heat": "heat",
    "cool": "cool",
    "hvac_cool": "cool",
    "heat_cool": "heat_cool",
    "hvac_heat_cool": "heat_cool",
    "auto": "auto",
    "hvac_auto": "auto",
    "fan_only": "fan_only",
    "hvac_fan_only": "fan_only",
    "dry": "dry",
    "hvac_dry": "dry",
    "off": "off",
    "hvac_off": "off",
}


async def async_execute_area_action(
    hass: HomeAssistant,
    entity_id: str,
    action: str = "toggle",
    level: int | float | None = None,
    code: str | None = None,
    option: str | None = None,
    *,
    blocking: bool = False,
    raise_on_missing: bool = False,
) -> None:
    """Execute a normalized area, whole-home (alarm/thermostat/garage/lock/vacuum), or light color/kelvin action."""
    raw_action = action.strip().lower()
    action = _ALARM_ACTION_ALIASES.get(raw_action, raw_action)
    entity_id = entity_id.strip()
    if not entity_id and action in (
        "arm_home",
        "arm_away",
        "arm_night",
        "arm_vacation",
        "disarm",
    ):
        entity_id = "home_hub.alarm"

    state_obj = hass.states.get(entity_id)
    if state_obj is None and entity_id == "home_hub.alarm":
        global_cfg = hass.data.get(DOMAIN, {}).get("global_config") or {}
        mapped_id = get_home_alarm_summary(
            hass, global_cfg.get("alarm_entity")
        )["entity_id"]
        if mapped_id:
            entity_id = mapped_id
            state_obj = hass.states.get(entity_id)
    if state_obj is None:
        if entity_id.startswith("button.") and not raise_on_missing:
            await hass.services.async_call(
                "button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
            )
            return
        if raise_on_missing:
            raise HomeAssistantError(f"Entity '{entity_id}' was not found")
        _LOGGER.debug("Action target entity not found: %s", entity_id)
        return
    if raise_on_missing and state_obj.state == STATE_UNAVAILABLE:
        raise HomeAssistantError(f"Entity '{entity_id}' is currently unavailable")

    domain = state_obj.domain
    if not action and domain not in ("alarm_control_panel", "lock"):
        action = "toggle"
    cur_level = max(0, get_entity_level(state_obj))

    if domain in ("button", "input_button"):
        await hass.services.async_call(
            domain, "press", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return

    if domain == "update":
        if action in ("install", "update") and state_obj.state == STATE_ON:
            await hass.services.async_call(
                "update", "install", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
            )
        elif hass.services.has_service("homeassistant", "update_entity"):
            await hass.services.async_call(
                "homeassistant",
                "update_entity",
                {ATTR_ENTITY_ID: entity_id},
                blocking=blocking,
            )
        return

    if domain in ("select", "input_select"):
        if option is not None:
            await hass.services.async_call(
                domain,
                "select_option",
                {ATTR_ENTITY_ID: entity_id, "option": str(option)},
                blocking=blocking,
            )
            return
        if action in ("select_next", "select_previous"):
            await hass.services.async_call(
                domain, action, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
            )
            return

    if domain in ("number", "input_number") and level is not None:
        await hass.services.async_call(
            domain,
            "set_value",
            {ATTR_ENTITY_ID: entity_id, "value": float(level)},
            blocking=blocking,
        )
        return

    if domain == "media_player" and level is not None and not action:
        await async_execute_volume_action(
            hass, entity_id, "set", volume_level=float(level)
        )
        return

    if domain == "alarm_control_panel":
        svc_map = {
            "arm_home": "alarm_arm_home",
            "arm_away": "alarm_arm_away",
            "arm_night": "alarm_arm_night",
            "arm_vacation": "alarm_arm_vacation",
            "disarm": "alarm_disarm",
        }
        svc = svc_map.get(action)
        if svc is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="explicit_action_required",
            )
        code_fmt = str(state_obj.attributes.get("code_format") or "").strip().lower()
        code_arm_req = bool(state_obj.attributes.get("code_arm_required", False))
        clean_code = str(code or "").strip()
        if code_fmt and (action == "disarm" or code_arm_req):
            if not clean_code:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="security_pin_required",
                )
            if code_fmt == "number" and not (
                4 <= len(clean_code) <= 8
                and clean_code.isascii()
                and clean_code.isdigit()
            ):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="security_pin_invalid",
                )
        payload: dict[str, Any] = {ATTR_ENTITY_ID: entity_id}
        if clean_code:
            payload["code"] = clean_code
        await hass.services.async_call(
            "alarm_control_panel", svc, payload, blocking=True
        )
        return

    if action in ("step_up", "step_down") and level is None:
        if domain == "climate":
            c_attrs = state_obj.attributes
            raw_t = c_attrs.get("temperature")
            if (
                raw_t is None
                and c_attrs.get("target_temp_low") is not None
                and c_attrs.get("target_temp_high") is not None
            ):
                try:
                    raw_t = (
                        float(c_attrs["target_temp_low"])
                        + float(c_attrs["target_temp_high"])
                    ) / 2.0
                except (ValueError, TypeError):
                    raw_t = None
            if raw_t is None:
                raw_t = (
                    c_attrs.get("target_temp_low")
                    or c_attrs.get("current_temperature")
                )
            try:
                base_t = round(float(raw_t)) if raw_t is not None else 20
            except (ValueError, TypeError):
                base_t = 20
            level = max(5, min(100, base_t + (1 if action == "step_up" else -1)))
        elif domain == "media_player":
            raw_v = state_obj.attributes.get("volume_level")
            step_lvl: float | None = None
            if raw_v is not None:
                try:
                    base_v = round(float(raw_v) * 100)
                    step_lvl = float(
                        max(0, min(100, base_v + (10 if action == "step_up" else -10)))
                    )
                except (ValueError, TypeError):
                    step_lvl = None
            await async_execute_volume_action(
                hass,
                entity_id,
                "up" if action == "step_up" else "down",
                volume_level=step_lvl,
            )
            return
        else:
            level = max(0, min(100, cur_level + (10 if action == "step_up" else -10)))
        action = "set_level"

    if domain == "scene":
        await hass.services.async_call(
            "scene", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return

    if domain == "script":
        svc_script = "turn_off" if action == "turn_off" else "turn_on"
        await hass.services.async_call(
            "script", svc_script, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return

    if domain == "automation":
        svc_auto = (
            action if action in ("trigger", "toggle", "turn_on", "turn_off") else "trigger"
        )
        await hass.services.async_call(
            "automation", svc_auto, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return

    if domain == "valve":
        if action in ("open_valve", "open"):
            svc_valve = "open_valve"
        elif action in ("close_valve", "close"):
            svc_valve = "close_valve"
        elif action in ("stop_valve", "stop"):
            svc_valve = "stop_valve"
        else:
            svc_valve = "close_valve" if state_obj.state == STATE_OPEN else "open_valve"
        await hass.services.async_call(
            "valve", svc_valve, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return

    if domain == "lawn_mower":
        svc_mower = action if action in ("start_mowing", "pause", "dock") else "start_mowing"
        await hass.services.async_call(
            "lawn_mower", svc_mower, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return

    if domain == "media_player" and action in (
        "media_play_pause",
        "media_next_track",
        "media_previous_track",
    ):
        await hass.services.async_call(
            "media_player", action, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return

    if domain == "light" and action == "set_color" and code:
        hex_s = code.strip().lstrip("#")
        if len(hex_s) == 6:
            try:
                rgb = [int(hex_s[0:2], 16), int(hex_s[2:4], 16), int(hex_s[4:6], 16)]
                payload_c: dict[str, Any] = {
                    ATTR_ENTITY_ID: entity_id,
                    "rgb_color": rgb,
                }
                if level is not None and int(level) > 0:
                    payload_c["brightness_pct"] = max(1, min(100, int(level)))
                await hass.services.async_call(
                    "light", "turn_on", payload_c, blocking=blocking
                )
                return
            except ValueError:
                pass

    if domain == "light" and action == "set_kelvin" and level is not None:
        kelvin = max(2000, min(6500, int(level)))
        await hass.services.async_call(
            "light",
            "turn_on",
            {ATTR_ENTITY_ID: entity_id, "color_temp_kelvin": kelvin},
            blocking=blocking,
        )
        return

    if domain == "climate" and action in _CLIMATE_HVAC_MAP:
        target_mode = _CLIMATE_HVAC_MAP[action]
        hvac_modes = [str(m) for m in (state_obj.attributes.get("hvac_modes") or [])]
        if (
            target_mode == "heat_cool"
            and "heat_cool" not in hvac_modes
            and "auto" in hvac_modes
        ):
            target_mode = "auto"
        elif (
            target_mode == "auto"
            and "auto" not in hvac_modes
            and "heat_cool" in hvac_modes
        ):
            target_mode = "heat_cool"
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {ATTR_ENTITY_ID: entity_id, "hvac_mode": target_mode},
            blocking=blocking,
        )
        return

    if domain == "climate" and action in ("set_level", "set_temperature") and level is not None:
        c_attrs = state_obj.attributes
        if (
            c_attrs.get("temperature") is None
            and c_attrs.get("target_temp_low") is not None
            and c_attrs.get("target_temp_high") is not None
        ):
            try:
                low = float(c_attrs["target_temp_low"])
                high = float(c_attrs["target_temp_high"])
                half = max(1.0, (high - low) / 2.0)
                tgt = float(level)
                await hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        ATTR_ENTITY_ID: entity_id,
                        "target_temp_low": round(tgt - half, 1),
                        "target_temp_high": round(tgt + half, 1),
                    },
                    blocking=blocking,
                )
                return
            except (ValueError, TypeError):
                pass
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {ATTR_ENTITY_ID: entity_id, "temperature": float(level)},
            blocking=blocking,
        )
        return

    if domain == "cover" and action in (
        "open_cover",
        "open",
        "close_cover",
        "close",
        "stop_cover",
        "stop",
    ):
        svc_cover = (
            "open_cover"
            if action in ("open_cover", "open")
            else ("close_cover" if action in ("close_cover", "close") else "stop_cover")
        )
        await hass.services.async_call(
            "cover", svc_cover, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return

    if domain == "lock":
        if action not in ("lock", "unlock", "open"):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="explicit_action_required",
            )
        if action == "open":
            supported = int(state_obj.attributes.get("supported_features") or 0)
            if not (supported & LockEntityFeature.OPEN):
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="not_supported",
                )
        await hass.services.async_call(
            "lock", action, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        return

    if domain == "vacuum":
        sf = int(state_obj.attributes.get("supported_features", 0) or 0)
        if action in ("dock", "return_to_base"):
            svc_v = "return_to_base"
        elif action == "pause":
            svc_v = "pause"
        elif action in ("stop", "turn_off"):
            svc_v = "turn_off" if (not (sf & 8) and bool(sf & 2)) else "stop"
        elif action in ("clean_spot", "spot"):
            svc_v = "clean_spot"
        elif action == "locate":
            svc_v = "locate"
        elif action == "toggle":
            if state_obj.state == "cleaning":
                svc_v = (
                    "pause"
                    if (sf == 0 or bool(sf & 4))
                    else ("turn_off" if (not (sf & 8) and bool(sf & 2)) else "stop")
                )
            else:
                svc_v = "turn_on" if (not (sf & 8192) and bool(sf & 1)) else "start"
        else:
            svc_v = "turn_on" if (not (sf & 8192) and bool(sf & 1)) else "start"
        await hass.services.async_call(
            "vacuum", svc_v, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return

    if action == "set_level" and level is not None:
        lvl = max(0, min(100, int(level)))
        if domain == "light":
            if lvl == 0:
                await hass.services.async_call(
                    "light", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
                )
            else:
                await hass.services.async_call(
                    "light",
                    "turn_on",
                    {ATTR_ENTITY_ID: entity_id, "brightness_pct": lvl},
                    blocking=blocking,
                )
            return
        if domain == "cover":
            await hass.services.async_call(
                "cover",
                "set_cover_position",
                {ATTR_ENTITY_ID: entity_id, "position": lvl},
                blocking=blocking,
            )
            return
        if domain == "fan":
            if lvl == 0:
                await hass.services.async_call(
                    "fan", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
                )
            else:
                await hass.services.async_call(
                    "fan",
                    "set_percentage",
                    {ATTR_ENTITY_ID: entity_id, "percentage": lvl},
                    blocking=blocking,
                )
            return
        if domain == "climate":
            await hass.services.async_call(
                "climate",
                "set_temperature",
                {ATTR_ENTITY_ID: entity_id, "temperature": float(lvl)},
                blocking=blocking,
            )
            return
        if domain == "media_player":
            await async_execute_volume_action(
                hass, entity_id, "set", volume_level=float(lvl)
            )
            return

    if action == "turn_on":
        svc = "open_cover" if domain == "cover" else "turn_on"
        await hass.services.async_call(
            domain, svc, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
    elif action == "turn_off":
        svc = "close_cover" if domain == "cover" else "turn_off"
        await hass.services.async_call(
            domain, svc, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
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
            domain, svc, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )


def resolve_active_area_entry(coordinator: Any) -> ar.AreaEntry | None:
    """Resolve the current AreaEntry for `coordinator` from BLE lock, sticky active_area_id, explicit default, or ESPHome Area."""
    if coordinator.is_device_away():
        return None
    area_reg = ar.async_get(coordinator.hass)
    explicit_default = str(coordinator.get_opt(CONF_DEFAULT_AREA) or "").strip()
    esp_default = ""
    if not coordinator.is_ble_tag and coordinator.esphome_device_id:
        esp_dev = dr.async_get(coordinator.hass).async_get(
            coordinator.esphome_device_id
        )
        esp_default = str(esp_dev.area_id or "").strip() if esp_dev else ""
    ble_area_id = (
        coordinator._ble_tracker.current_area_id
        if (
            coordinator.native_ble_tracking_enabled
            and coordinator._ble_tracker is not None
        )
        else None
    )
    eff_id = (
        ble_area_id
        or coordinator.active_area_id
        or explicit_default
        or esp_default
    )
    return area_reg.async_get_area(eff_id) if eff_id else None


def resolve_person_area_and_distance(
    hass: HomeAssistant, person_entity: str
) -> tuple[str, dict[str, Any]]:
    """Resolve the freshest area and BLE distance across all Latter devices carried by a person."""
    target_low = str(person_entity or "").strip().lower()
    p_coords = [
        v
        for v in iter_coordinators(hass)
        if getattr(v, "assigned_person", "").lower() == target_low
    ]
    if not p_coords:
        return "Unassigned", {
            "person_entity": person_entity,
            "area_id": "",
            "area_name": "Unassigned",
            "floor_id": "",
            "floor_name": "Unassigned",
            "is_home": False,
            "distance_ft": None,
            "distance_m": None,
            "closest_proxy": "",
            "match_method": "",
            "source_device": "",
        }
    home_coords = [c for c in p_coords if not c.is_device_away()]
    pool = home_coords if home_coords else p_coords
    best_c = max(
        pool,
        key=lambda x: (
            x._ble_tracker.last_packet_monotonic
            if x._ble_tracker is not None
            else 0.0
        ),
    )
    area_name, r_attrs = best_c.get_current_area_and_distance()
    return area_name, {
        "person_entity": person_entity,
        "area_id": r_attrs["area_id"],
        "area_name": area_name,
        "floor_id": r_attrs["floor_id"],
        "floor_name": r_attrs["floor_name"],
        "is_home": r_attrs["is_home"],
        "distance_ft": r_attrs["distance_ft"],
        "distance_m": r_attrs["distance_m"],
        "closest_proxy": r_attrs["closest_proxy"],
        "match_method": r_attrs["match_method"],
        "source_device": best_c.device_slug,
    }


def _build_broadcast_phrases_summary(coordinator: Any) -> V3Records:
    """Build ordered Quick Broadcast phrases for `area_context.broadcast_phrases`."""
    phrases = getattr(coordinator, "broadcast_phrases", None)
    if not isinstance(phrases, (list, tuple)):
        phrases = DEFAULT_BROADCAST_PHRASES
    return broadcast_phrase_records(phrases)


def _build_cameras_summary(coordinator: Any) -> V3Records:
    """Build camera records (`entity_id|name|area_id|caps|unlock_entity`) for up to 10 visible cameras."""
    visible_cams = getattr(
        coordinator, "visible_camera_entities", coordinator.camera_entities
    )
    carousel_cams = getattr(coordinator, "carousel_camera_entities", visible_cams)
    ring_map = getattr(coordinator, "_doorbell_ring_map", None)
    vol_overrides = getattr(coordinator, "volume_overrides", None)
    cam_configs = getattr(coordinator, "camera_configs", None) or {}
    rows: list[dict[str, Any]] = []
    for ent_id in visible_cams[:CAMERAS_MAX_RECORDS]:
        meta = resolve_camera_capabilities(
            coordinator.hass,
            ent_id,
            doorbell_ring_map=ring_map,
            carousel_entities=carousel_cams,
            volume_overrides=vol_overrides,
            camera_config=cam_configs.get(ent_id),
        )
        rows.append(
            {
                "entity_id": meta["entity_id"],
                "name": meta["name"],
                "area_id": meta["area_id"],
                "caps": meta["caps"],
                "unlock_entity": meta["unlock_entity"],
            }
        )
    return camera_records(rows)


DEFAULT_UNMATCHED_AREA_ICON = "mdi:map-marker-outline"

_CAMEL_SPLIT_RE = re.compile(r"([a-z0-9])([A-Z])")
_AREA_ARCHETYPE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pat, re.IGNORECASE), icon)
    for pat, icon in (
        (r"\b(?:kitchen\w*|pantry|kitchenette)\b", "mdi:countertop"),
        (r"\b(?:dining|breakfast)\b", "mdi:silverware-fork-knife"),
        (r"\b(?:nursery|baby|crib)\b", "mdi:baby-carriage"),
        (r"\b(?:kids?|child\w*|play\w*)\b", "mdi:teddy-bear"),
        (r"\b(?:bath\w*|shower\w*|powder|rest\w*|lavatory|toilet|ensuite)\b", "mdi:shower"),
        (r"\b(?:laundry|utility|mud\w*)\b", "mdi:washing-machine"),
        (r"\b(?:office|study|library|desk\w*)\b", "mdi:desk"),
        (r"\b(?:media|theat(?:er|re)|cinema|tv)\b", "mdi:television"),
        (r"\b(?:gam(?:e|es|ing)|arcade)\b", "mdi:gamepad-variant-outline"),
        (r"\b(?:gym\w*|fitness|workout|yoga|exercise)\b", "mdi:dumbbell"),
        (r"\b(?:garage|carport)\b", "mdi:garage"),
        (r"\b(?:workshop|tools?|craft\w*)\b", "mdi:tools"),
        (r"\b(?:closet|wardrobe|dressing)\b", "mdi:wardrobe-outline"),
        (r"\b(?:pool\w*|spa|hot\s*tub|jacuzzi)\b", "mdi:pool"),
        (r"\b(?:patio|deck|porch|balcony|terrace|lanai|veranda)\b", "mdi:balcony"),
        (r"\b(?:garden\w*|yard|lawn|outdoor\w*|backyard|courtyard)\b", "mdi:tree-outline"),
        (r"\b(?:attic|loft)\b", "mdi:home-roof"),
        (r"\b(?:basement|cellar)\b", "mdi:stairs-down"),
        (r"\b(?:stairs?|stairwell|staircase)\b", "mdi:stairs"),
        (r"\b(?:hall\w*|corridor|landing|passage\w*)\b", "mdi:transit-connection-horizontal"),
        (r"\b(?:entry\w*|entrance|foyer|vestibule|front)\b", "mdi:door-open"),
        (r"\b(?:studio|music)\b", "mdi:speaker"),
        (r"\b(?:living|family|great|den|lounge|parlor|sitting)\b", "mdi:sofa"),
        (r"\b(?:primary|master|guest|bed\w*|bunk|dorm\w*)\b", "mdi:bed-king-outline"),
    )
)


def infer_area_icon_from_name(area_name: str) -> str:
    """Infer a canonical Material Design icon key from an Area display name."""
    cleaned = _CAMEL_SPLIT_RE.sub(r"\1 \2", str(area_name or ""))
    cleaned = cleaned.replace("_", " ").replace("-", " ").strip()
    if not cleaned:
        return DEFAULT_UNMATCHED_AREA_ICON
    for pat, icon in _AREA_ARCHETYPE_PATTERNS:
        if pat.search(cleaned):
            return icon
    return DEFAULT_UNMATCHED_AREA_ICON


def resolve_area_icon(area_entry: ar.AreaEntry | None) -> str:
    """Return explicit Home Assistant AreaEntry icon or inferred Area archetype icon; empty when unassigned."""
    if area_entry is None:
        return ""
    explicit_icon = getattr(area_entry, "icon", None)
    if isinstance(explicit_icon, str) and explicit_icon.strip():
        return explicit_icon.strip()
    return infer_area_icon_from_name(getattr(area_entry, "name", "") or "")


def build_area_context_payload(coordinator: Any) -> tuple[str, dict[str, Any]]:
    """Compute state and attributes for `sensor.<device_slug>_area_context`."""
    now_m = time.monotonic()
    if (
        coordinator._cached_area_payload is not None
        and (now_m - coordinator._cached_area_payload[0]) < 0.15
    ):
        cached_payload: tuple[str, dict[str, Any]] = coordinator._cached_area_payload[1]
        return cached_payload
    area_entry = resolve_active_area_entry(coordinator)
    area_name = area_entry.name if area_entry else "Unassigned"
    area_icon = resolve_area_icon(area_entry)
    eff_area_id = area_entry.id if area_entry else ("" if coordinator.is_device_away() else (coordinator.active_area_id or ""))

    entities = get_area_entities(
        coordinator.hass,
        area_id=eff_area_id or None,
        domain_filter="all",
        local_speaker=coordinator.local_speaker,
    )
    avail_domains = get_area_available_domains(
        coordinator.hass,
        area_id=eff_area_id or None,
        local_speaker=coordinator.local_speaker,
        entities=entities,
        area_categories=coordinator.area_categories_csv,
    )
    lights_on = sum(1 for e in entities if e["type"] == "light" and e["active"])
    covers_open = sum(1 for e in entities if e["type"] == "cover" and e["active"])
    climate_telemetry = get_area_climate_telemetry(
        coordinator.hass, eff_area_id or None
    )
    ambient_info = resolve_area_ambient_light(
        coordinator.hass, eff_area_id or None
    )
    prev_ambient = getattr(coordinator, "_last_ambient_light", ("", None, ""))
    eff_ambient = apply_ambient_light_deadband(
        prev_ambient,
        eff_area_id,
        ambient_info["ambient_pct"],
        ambient_info["wire"],
    )
    coordinator._last_ambient_light = eff_ambient
    area_ambient_wire = eff_ambient[2]
    alarm_info = get_home_alarm_summary(
        coordinator.hass, coordinator.get_opt(CONF_ALARM_ENTITY)
    )
    hub_info = get_home_hub_summary(
        coordinator.hass,
        thermostat_entities=coordinator.thermostat_entities,
        lock_entities=coordinator.lock_entities,
        garage_entities=coordinator.garage_entities,
        vacuum_entities=coordinator.vacuum_entities,
    )
    area_climates_summary = get_area_climates_summary(
        coordinator.hass, eff_area_id or None, coordinator.local_speaker
    )
    active_cam = coordinator.active_carousel_camera or coordinator.camera_entity
    camera_snapshot_url = (
        coordinator.build_camera_allowlist_snapshot_url(active_cam)
        if active_cam
        else ""
    )
    camera_stream_url = coordinator.build_camera_stream_url()
    alert_camera_entity = (
        coordinator.alert_camera_entity if coordinator.alert_id else ""
    )

    eff_pin_policy = coordinator.security_pin_policy
    alarm_caps = int(alarm_info.get("alarm_caps") or 0)
    avail_home_cats = get_available_home_categories(
        alarm_info,
        hub_info,
        home_categories=coordinator.home_categories_csv,
        coordinator=coordinator,
        hass=coordinator.hass,
    )
    local_tz_info, world_clocks_summary = build_time_zone_payloads(
        getattr(coordinator.hass.config, "time_zone", None),
        str(coordinator.get_opt("world_clocks", "") or ""),
    )
    area_attrs: dict[str, Any] = {
        "site_id": coordinator.site_id,
        "area_id": eff_area_id,
        "area_name": area_name,
        "area_icon": area_icon,
        "ble_closest_proxy": (
            coordinator._ble_tracker.closest_scanner if coordinator._ble_tracker else ""
        ),
        "activity_card": coordinator.activity_card_enabled,
        "activity_sources": coordinator.activity_sources_csv,
        "security_pin_policy": eff_pin_policy,
        "home_categories": avail_home_cats,
        "wallpaper_url": coordinator.build_wallpaper_url(),
        "available_domains": avail_domains,
        "area_temp": climate_telemetry["temperature"],
        "area_humidity": climate_telemetry["humidity"],
        "lights_on": lights_on,
        "covers_open": covers_open,
        "alarm_entity": alarm_info["entity_id"],
        "alarm_state": alarm_info["state"],
        "alarm_caps": alarm_caps,
        "thermostats": hub_info["thermostats"],
        "thermostats_summary": hub_info["thermostats_summary"],
        "locks": hub_info["locks"],
        "locks_summary": hub_info["locks_summary"],
        "garages": hub_info["garages"],
        "garages_summary": hub_info["garages_summary"],
        "vacuums": hub_info["vacuums"],
        "vacuums_summary": hub_info["vacuums_summary"],
        "area_climates_summary": area_climates_summary,
        "camera_snapshot_url": camera_snapshot_url,
        "camera_stream_url": camera_stream_url,
        "cameras_summary": _build_cameras_summary(coordinator),
        "doorbell_talk_state": coordinator.doorbell_talk_state,
        "broadcast_phrases": _build_broadcast_phrases_summary(coordinator),
        "alert_id": coordinator.alert_id,
        "alert_title": coordinator.alert_title,
        "alert_message": coordinator.alert_message,
        "alert_priority": coordinator.alert_priority,
        "alert_duration": coordinator.alert_duration,
        "alert_chime": coordinator.alert_chime,
        "alert_camera_url": coordinator.alert_camera_url,
        "alert_camera_entity": alert_camera_entity,
        "local_tz_info": local_tz_info,
        "world_clocks_summary": world_clocks_summary,
        "screensaver_photo_url": coordinator.build_screensaver_photo_url(),
        "area_ambient_light": area_ambient_wire,
        "area_lux": ambient_info["lux"],
        "area_lux_display": ambient_info["lux_display"],
        "area_ambient_pct": ambient_info["ambient_pct"],
        "area_illuminance_entity": ambient_info["resolved_entity"],
        "area_illuminance_name": ambient_info["resolved_name"],
    }
    area_rev, area_payload = coordinator._pack_domain_payload(
        "area_context",
        area_attrs["area_id"],
        area_entry.name if area_entry else "",
        area_attrs["site_id"],
        area_attrs["ble_closest_proxy"],
        area_attrs["wallpaper_url"],
        area_attrs["available_domains"],
        area_attrs["area_temp"],
        area_attrs["area_humidity"],
        lights_on,
        covers_open,
        area_attrs["alarm_entity"],
        area_attrs["alarm_state"],
        area_attrs["thermostats_summary"],
        area_attrs["locks_summary"],
        area_attrs["garages_summary"],
        area_attrs["vacuums_summary"],
        area_attrs["area_climates_summary"],
        area_attrs["camera_snapshot_url"],
        area_attrs["cameras_summary"],
        area_attrs["doorbell_talk_state"],
        area_attrs["broadcast_phrases"],
        *(
            (
                coordinator.alert_id,
                coordinator.alert_title,
                coordinator.alert_message,
                coordinator.alert_priority,
                coordinator.alert_duration,
                1 if coordinator.alert_chime else 0,
                coordinator.alert_camera_url,
            )
            if coordinator.alert_id
            else (0, "", "", "", None, None, "")
        ),
        *activity_payload(
            coordinator.activity_card_enabled, coordinator.activity_sources_csv
        ),
        eff_pin_policy,
        area_attrs["home_categories"],
        area_icon,
        local_tz_info,
        world_clocks_summary,
        alarm_caps,
        camera_stream_url,
        alert_camera_entity,
        area_attrs["screensaver_photo_url"],
        area_ambient_wire,
    )
    area_attrs["rev"] = area_rev
    area_attrs["payload"] = area_payload
    res = (area_name, area_attrs)
    coordinator._cached_area_payload = (time.monotonic(), res)
    return res


@callback
def bind_coordinator_area_listeners(coordinator: Any) -> None:
    """Bind active Area, Whole-Home, Remote Slot, and Shortcut entity state listeners on `coordinator`."""
    for attr in (
        "_unsub_area_entities_state",
        "_unsub_alarm_state",
        "_unsub_remotes_state",
        "_unsub_shortcuts_state",
    ):
        prev = getattr(coordinator, attr, None)
        if prev is not None:
            prev()
            setattr(coordinator, attr, None)

    @callback
    def _schedule_area_push() -> None:
        coordinator.async_notify_listeners()
        if coordinator._unsub_area_debounce is not None:
            coordinator._unsub_area_debounce()
            coordinator._unsub_area_debounce = None

        @callback
        def _push_area_update(_now: datetime) -> None:
            coordinator._unsub_area_debounce = None
            if coordinator.on_area_changed_push_slots is not None:
                coordinator.entry.async_create_background_task(
                    coordinator.hass,
                    coordinator.on_area_changed_push_slots(coordinator),
                    f"latter_area_slots_{coordinator.device_slug}",
                )

        coordinator._unsub_area_debounce = async_call_later(
            coordinator.hass, 0.25, _push_area_update
        )

    @callback
    def _on_area_entity_event(event: Event[EventStateChangedData]) -> None:
        old_st = event.data.get("old_state")
        new_st = event.data.get("new_state")
        if is_media_position_only_tick(old_st, new_st):
            return
        _schedule_area_push()

    idx = get_area_state_index(coordinator.hass)
    unsubs_area: list[Any] = []
    eff_area_entry = resolve_active_area_entry(coordinator)
    listen_area_id = (
        eff_area_entry.id
        if eff_area_entry is not None
        else (coordinator.active_area_id or "")
    )
    if listen_area_id:
        if idx.started:
            unsubs_area.append(
                idx.register_area_listener(
                    listen_area_id, lambda _eid: _schedule_area_push()
                )
            )
        else:
            area_items = get_area_entities(
                coordinator.hass,
                area_id=listen_area_id,
                domain_filter="all",
                local_speaker=coordinator.local_speaker,
            )
            tracked_ids = [str(it["id"]) for it in area_items if it.get("id")]
            if tracked_ids:
                unsubs_area.append(
                    async_track_state_change_event(
                        coordinator.hass, tracked_ids, _on_area_entity_event
                    )
                )
    if unsubs_area:

        @callback
        def _unsub_area_all() -> None:
            for u in unsubs_area:
                u()

        coordinator._unsub_area_entities_state = _unsub_area_all

    tracked_hub: list[str] = []
    for cand in (
        coordinator.alarm_entity,
        *coordinator.thermostat_entities,
        *coordinator.lock_entities,
        *coordinator.garage_entities,
        *coordinator.vacuum_entities,
    ):
        if cand and cand not in tracked_hub:
            tracked_hub.append(cand)
    if tracked_hub:
        coordinator._unsub_alarm_state = async_track_state_change_event(
            coordinator.hass,
            tracked_hub,
            lambda _ev: coordinator.async_notify_listeners(),
        )

    tracked_rem: list[str] = []
    for slot in coordinator.get_remote_slots():
        for key in ("remote_entity", "media_player_entity"):
            ent = slot.get(key)
            if ent and ent not in tracked_rem:
                tracked_rem.append(ent)
    if tracked_rem:
        coordinator._unsub_remotes_state = async_track_state_change_event(
            coordinator.hass,
            tracked_rem,
            lambda _ev: coordinator.async_notify_listeners(),
        )

    tracked_shortcuts: list[str] = []
    for sc_list in (coordinator.dock_items, coordinator.pinned_items):
        for sc in sc_list:
            if sc.get("kind") == "entity":
                ent = str(sc.get("target") or "").strip()
                if ent and ent not in tracked_shortcuts:
                    tracked_shortcuts.append(ent)
    if tracked_shortcuts:

        @callback
        def _on_shortcut_entity_event(event: Event[EventStateChangedData]) -> None:
            old_st = event.data.get("old_state")
            new_st = event.data.get("new_state")
            if is_media_position_only_tick(old_st, new_st):
                return
            if (
                old_st is not None
                and new_st is not None
                and old_st.state == new_st.state
                and old_st.attributes.get("icon") == new_st.attributes.get("icon")
                and old_st.attributes.get("friendly_name")
                == new_st.attributes.get("friendly_name")
            ):
                return
            coordinator.async_notify_listeners()

        coordinator._unsub_shortcuts_state = async_track_state_change_event(
            coordinator.hass,
            tracked_shortcuts,
            _on_shortcut_entity_event,
        )
