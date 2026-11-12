"""Curated Area Discovery, Entity Filtering, Telemetry, Actions & Area Context v3 Builder."""

from __future__ import annotations

from datetime import datetime
import logging
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
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ALARM_ENTITY,
    CONF_DEFAULT_AREA,
    CONF_ESPHOME_DEVICE_ID,
    DOMAIN,
    SUBENTRY_DEVICE,
    other_latter_devices,
)
from .groups import _apply_ha_display_precision
from .hub import get_area_state_index, is_media_position_only_tick, iter_coordinators
from .identity import resolve_bound_esphome_device_id
from .media_browse import is_music_assistant_player
from .presence import get_ble_proxy_area_ids
from .protocol import (
    CAMERAS_MAX_RECORDS,
    V3Records,
    activity_payload,
    camera_records,
    ha_value,
    intercom_target_records,
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
        return entry.area_id
    if entry.device_id:
        if dev_reg is None:
            dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(entry.device_id)
        if device and device.area_id:
            return device.area_id
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
            return area.id

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
    area_id: str,
    require_ble_proxy_area: bool = True,
) -> dict[str, Any] | None:
    """Update the bound ESPHome device's area_id in HA Device Registry ONLY for valid areas."""
    if not esphome_device_id or not area_id:
        return None

    if require_ble_proxy_area:
        proxy_areas = get_ble_proxy_area_ids(hass)
        if proxy_areas and area_id not in proxy_areas:
            _LOGGER.debug(
                "Skipping Device Registry area sync to '%s' because that area has no BLE proxy.",
                area_id,
            )
            return None

    dev_reg = dr.async_get(hass)
    dev = dev_reg.async_get(esphome_device_id)
    if dev and dev.area_id != area_id:
        prev_area = str(dev.area_id or "")
        domain_data = hass.data.setdefault(DOMAIN, {})
        own_writes: dict[str, tuple[str, float]] = domain_data.setdefault(
            "_own_area_writes", {}
        )
        own_writes[esphome_device_id] = (area_id, time.monotonic())
        dev_reg.async_update_device(esphome_device_id, area_id=area_id)
        record: dict[str, Any] = {
            "timestamp": dt_util.now().isoformat(timespec="seconds"),
            "from_area": prev_area,
            "to_area": area_id,
            "device_id": esphome_device_id,
        }
        _LOGGER.debug(
            "Synced bound ESPHome device id=%s to area_id='%s' for area-aware Voice Assistant",
            esphome_device_id,
            area_id,
        )
        return record
    return None


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


def get_home_alarm_summary(
    hass: HomeAssistant, configured_alarm_entity: str | None = None
) -> dict[str, Any]:
    """Return the configured (or auto-discovered) home security alarm_control_panel summary."""
    if configured_alarm_entity:
        state_obj = hass.states.get(configured_alarm_entity)
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
            }

    for state_obj in get_area_state_index(hass).states_for_domain(
        "alarm_control_panel"
    ):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
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
        }
    return {
        "entity_id": "",
        "state": "",
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
        "thermostat_state": "",
        "thermostat_temp": None,
        "thermostat_current_temp": None,
        "lock_entity": "",
        "lock_state": "",
        "garage_entity": "",
        "garage_state": "",
        "vacuum_entity": "",
        "vacuum_state": "",
    }
    idx = get_area_state_index(hass)

    t_st = hass.states.get(thermostat_entity) if thermostat_entity else None
    if t_st is None:
        for cand in idx.states_for_domain("climate"):
            if cand.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                t_st = cand
                break
    if t_st is not None:
        out["thermostat_entity"] = t_st.entity_id
        out["thermostat_state"] = ha_value(t_st.state)
        tgt_t = t_st.attributes.get("temperature")
        if tgt_t is None:
            tgt_t = t_st.attributes.get("target_temp_low")
        if tgt_t is not None:
            try:
                out["thermostat_temp"] = round(float(tgt_t))
            except (ValueError, TypeError):
                pass
        cur_t = t_st.attributes.get("current_temperature")
        if cur_t is not None:
            try:
                out["thermostat_current_temp"] = round(float(cur_t), 1)
            except (ValueError, TypeError):
                pass

    l_st = hass.states.get(lock_entity) if lock_entity else None
    if l_st is None:
        for cand in idx.states_for_domain("lock"):
            if cand.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                l_st = cand
                break
    if l_st is not None:
        out["lock_entity"] = l_st.entity_id
        out["lock_state"] = ha_value(l_st.state)

    g_st = hass.states.get(garage_entity) if garage_entity else None
    if g_st is None:
        for cand in idx.states_for_domain("cover"):
            if cand.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            d_cls = str(cand.attributes.get("device_class") or "").lower()
            if d_cls in ("garage", "gate", "door") or "garage" in cand.entity_id.lower():
                g_st = cand
                break
    if g_st is not None:
        out["garage_entity"] = g_st.entity_id
        out["garage_state"] = ha_value(g_st.state)

    v_st = hass.states.get(vacuum_entity) if vacuum_entity else None
    if v_st is None:
        for cand in idx.states_for_domain("vacuum"):
            if cand.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                v_st = cand
                break
    if v_st is not None:
        out["vacuum_entity"] = v_st.entity_id
        out["vacuum_state"] = ha_value(v_st.state)

    return out


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
) -> str:
    """Return comma-separated canonical area categories present in the active area."""
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


async def async_execute_area_action(
    hass: HomeAssistant,
    entity_id: str,
    action: str = "toggle",
    level: int | None = None,
    code: str | None = None,
    option: str | None = None,
) -> None:
    """Execute a normalized area, whole-home (alarm/thermostat/garage/lock/vacuum), or light color/kelvin action."""
    state_obj = hass.states.get(entity_id)
    if state_obj is None and entity_id.startswith("whole_home."):
        wh_kind = entity_id.split(".", 1)[1].lower()
        global_cfg = hass.data.get(DOMAIN, {}).get("global_config") or {}
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
        if entity_id.startswith("button."):
            await hass.services.async_call(
                "button", "press", {ATTR_ENTITY_ID: entity_id}, blocking=False
            )
            return
        _LOGGER.debug("Action target entity not found: %s", entity_id)
        return

    domain = state_obj.domain
    action = action.strip().lower()
    if not action and domain not in ("alarm_control_panel", "lock"):
        action = "toggle"
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
            "disarm": "alarm_disarm",
        }
        svc = svc_map.get(action)
        if svc is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="explicit_action_required",
            )
        payload: dict[str, Any] = {ATTR_ENTITY_ID: entity_id}
        if code:
            payload["code"] = str(code)
        await hass.services.async_call(
            "alarm_control_panel", svc, payload, blocking=True
        )
        return

    if action in ("step_up", "step_down") and level is None:
        if domain == "climate":
            raw_t = (
                state_obj.attributes.get("temperature")
                or state_obj.attributes.get("target_temp_low")
                or state_obj.attributes.get("current_temperature")
            )
            try:
                base_t = round(float(raw_t)) if raw_t is not None else 20
            except (ValueError, TypeError):
                base_t = 20
            level = max(5, min(100, base_t + (1 if action == "step_up" else -1)))
        elif domain == "media_player":
            raw_v = state_obj.attributes.get("volume_level")
            try:
                base_v = round(float(raw_v) * 100) if raw_v is not None else 0
            except (ValueError, TypeError):
                base_v = 0
            level = max(0, min(100, base_v + (10 if action == "step_up" else -10)))
        else:
            level = max(0, min(100, cur_level + (10 if action == "step_up" else -10)))
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
                payload_c: dict[str, Any] = {
                    ATTR_ENTITY_ID: entity_id,
                    "rgb_color": rgb,
                }
                if level is not None and int(level) > 0:
                    payload_c["brightness_pct"] = max(1, min(100, int(level)))
                await hass.services.async_call(
                    "light", "turn_on", payload_c, blocking=False
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
        svc_v = (
            "return_to_base"
            if action in ("dock", "return_to_base")
            else ("pause" if action == "pause" else "start")
        )
        await hass.services.async_call(
            "vacuum", svc_v, {ATTR_ENTITY_ID: entity_id}, blocking=False
        )
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


def resolve_active_area_entry(coordinator: Any) -> ar.AreaEntry | None:
    """Resolve the current AreaEntry for `coordinator` from BLE lock, sticky active_area_id, or explicit default."""
    if coordinator.is_device_away():
        return None
    area_reg = ar.async_get(coordinator.hass)
    explicit_default = str(coordinator.get_opt(CONF_DEFAULT_AREA) or "").strip()
    ble_area_id = (
        coordinator._ble_tracker.current_area_id
        if (
            coordinator.native_ble_tracking_enabled
            and coordinator._ble_tracker is not None
        )
        else None
    )
    eff_id = ble_area_id or coordinator.active_area_id or explicit_default
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
            "is_home": False,
            "distance_ft": None,
            "distance_m": None,
            "closest_proxy": "",
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
        "is_home": r_attrs["is_home"],
        "distance_ft": r_attrs["distance_ft"],
        "distance_m": r_attrs["distance_m"],
        "closest_proxy": r_attrs["closest_proxy"],
        "source_device": best_c.device_slug,
    }


def _build_intercom_targets_summary(coordinator: Any) -> V3Records:
    """Build call_target records for all other Latter Devices."""
    others = other_latter_devices(
        iter_coordinators(coordinator.hass), coordinator.device_slug
    )
    others.sort(key=lambda c: (c.device_title.lower(), c.device_slug))
    targets: list[dict[str, str]] = (
        [{"target_id": "all", "label": "All Devices", "kind": "all"}] if others else []
    )
    targets += [
        {"target_id": c.device_slug, "label": c.device_title, "kind": "device"}
        for c in others
    ]
    return intercom_target_records(targets)


def _build_cameras_summary(coordinator: Any) -> V3Records:
    """Build camera records (entity_id, name, area_id, signed snapshot URL) for up to 10 cameras."""
    rows: list[dict[str, str]] = []
    for ent_id in coordinator.camera_entities[:CAMERAS_MAX_RECORDS]:
        st = coordinator.hass.states.get(ent_id)
        friendly = str(st.attributes.get("friendly_name") or "") if st else ""
        rows.append(
            {
                "entity_id": ent_id,
                "name": friendly or ent_id.split(".", 1)[-1].replace("_", " ").title(),
                "area_id": resolve_entity_area_id(coordinator.hass, ent_id) or "",
                "snapshot_url": coordinator.build_camera_snapshot_url(ent_id),
            }
        )
    return camera_records(rows)


def build_area_context_payload(coordinator: Any) -> tuple[str, dict[str, Any]]:
    """Compute state and attributes for `sensor.<device_slug>_area_context`."""
    now_m = time.monotonic()
    if (
        coordinator._cached_area_payload is not None
        and (now_m - coordinator._cached_area_payload[0]) < 0.05
    ):
        return coordinator._cached_area_payload[1]
    area_entry = resolve_active_area_entry(coordinator)
    area_name = area_entry.name if area_entry else "Unassigned"
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
    )
    lights_on = sum(1 for e in entities if e["type"] == "light" and e["active"])
    covers_open = sum(1 for e in entities if e["type"] == "cover" and e["active"])
    climate_telemetry = get_area_climate_telemetry(
        coordinator.hass, eff_area_id or None
    )
    alarm_info = get_home_alarm_summary(
        coordinator.hass, coordinator.get_opt(CONF_ALARM_ENTITY)
    )
    wh_info = get_whole_home_summary(
        coordinator.hass,
        thermostat_entity=coordinator.thermostat_entity,
        lock_entity=coordinator.lock_entity,
        garage_entity=coordinator.garage_entity,
        vacuum_entity=coordinator.vacuum_entity,
    )
    active_cam = coordinator.active_carousel_camera or coordinator.camera_entity
    camera_snapshot_url = (
        coordinator.build_camera_snapshot_url(active_cam) if active_cam else ""
    )

    eff_pin_policy = coordinator.security_pin_policy
    area_attrs: dict[str, Any] = {
        "site_id": coordinator.site_id,
        "area_id": eff_area_id,
        "area_name": area_name,
        "ble_closest_proxy": (
            coordinator._ble_tracker.closest_scanner if coordinator._ble_tracker else ""
        ),
        "dock_apps": coordinator.dock_apps_csv,
        "activity_card": coordinator.activity_card_enabled,
        "activity_sources": coordinator.activity_sources_csv,
        "security_pin_policy": eff_pin_policy,
        "wallpaper_url": coordinator.build_wallpaper_url(),
        "theme_color_hex": coordinator.device_custom_color,
        "available_domains": avail_domains,
        "area_temp": climate_telemetry["temperature"],
        "area_humidity": climate_telemetry["humidity"],
        "lights_on": lights_on,
        "covers_open": covers_open,
        "alarm_entity": alarm_info["entity_id"],
        "alarm_state": alarm_info["state"],
        "thermostat_entity": wh_info["thermostat_entity"],
        "thermostat_state": wh_info["thermostat_state"],
        "thermostat_temp": wh_info["thermostat_temp"],
        "thermostat_current_temp": wh_info["thermostat_current_temp"],
        "lock_entity": wh_info["lock_entity"],
        "lock_state": wh_info["lock_state"],
        "garage_entity": wh_info["garage_entity"],
        "garage_state": wh_info["garage_state"],
        "vacuum_entity": wh_info["vacuum_entity"],
        "vacuum_state": wh_info["vacuum_state"],
        "camera_snapshot_url": camera_snapshot_url,
        "cameras_summary": _build_cameras_summary(coordinator),
        "doorbell_talk_state": coordinator.doorbell_talk_state,
        "intercom_targets_summary": _build_intercom_targets_summary(coordinator),
        "alert_id": coordinator.alert_id,
        "alert_title": coordinator.alert_title,
        "alert_message": coordinator.alert_message,
        "alert_priority": coordinator.alert_priority,
        "alert_duration": coordinator.alert_duration,
        "alert_chime": coordinator.alert_chime,
        "alert_camera_url": coordinator.alert_camera_url,
    }
    area_rev, area_payload = coordinator._pack_domain_payload(
        "area_context",
        area_attrs["area_id"],
        area_entry.name if area_entry else "",
        area_attrs["site_id"],
        area_attrs["ble_closest_proxy"],
        area_attrs["dock_apps"],
        area_attrs["wallpaper_url"],
        area_attrs["theme_color_hex"],
        area_attrs["available_domains"],
        area_attrs["area_temp"],
        area_attrs["area_humidity"],
        lights_on,
        covers_open,
        area_attrs["alarm_entity"],
        area_attrs["alarm_state"],
        area_attrs["thermostat_entity"],
        area_attrs["thermostat_state"],
        area_attrs["thermostat_temp"],
        area_attrs["thermostat_current_temp"],
        area_attrs["lock_entity"],
        area_attrs["lock_state"],
        area_attrs["garage_entity"],
        area_attrs["garage_state"],
        area_attrs["vacuum_entity"],
        area_attrs["vacuum_state"],
        area_attrs["camera_snapshot_url"],
        area_attrs["cameras_summary"],
        area_attrs["doorbell_talk_state"],
        area_attrs["intercom_targets_summary"],
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
    )
    area_attrs["rev"] = area_rev
    area_attrs["payload"] = area_payload
    res = (area_name, area_attrs)
    coordinator._cached_area_payload = (now_m, res)
    return res


@callback
def bind_coordinator_area_listeners(coordinator: Any) -> None:
    """Bind active Area, Whole-Home, and Remote Slot state listeners on `coordinator`."""
    for attr in (
        "_unsub_area_entities_state",
        "_unsub_alarm_state",
        "_unsub_remotes_state",
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
    if coordinator.active_area_id:
        if idx.started:
            unsubs_area.append(
                idx.register_area_listener(
                    coordinator.active_area_id, lambda _eid: _schedule_area_push()
                )
            )
        else:
            area_items = get_area_entities(
                coordinator.hass,
                area_id=coordinator.active_area_id,
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

    wh_info = get_whole_home_summary(
        coordinator.hass,
        thermostat_entity=coordinator.thermostat_entity,
        lock_entity=coordinator.lock_entity,
        garage_entity=coordinator.garage_entity,
        vacuum_entity=coordinator.vacuum_entity,
    )
    tracked_wh: list[str] = []
    for cand in (
        coordinator.alarm_entity,
        wh_info["thermostat_entity"],
        wh_info["lock_entity"],
        wh_info["garage_entity"],
        wh_info["vacuum_entity"],
    ):
        if cand and cand not in tracked_wh:
            tracked_wh.append(cand)
    if tracked_wh:
        coordinator._unsub_alarm_state = async_track_state_change_event(
            coordinator.hass,
            tracked_wh,
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
