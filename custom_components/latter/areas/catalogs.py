"""Curated Area summaries, domain availability, and controllable entity catalogs (`L2b`)."""

from __future__ import annotations

import math
from typing import Any, Final

from homeassistant.const import (
    STATE_ON,
    STATE_OPEN,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar, entity_registry as er

from ..const import DOMAIN
from ..protocol_specs import DEFAULT_AREA_CATEGORIES, parse_area_categories
from .curation import (
    AREA_CONTROL_DOMAINS,
    extract_climate_temps,
    find_area_media_entities as find_area_media_entities,
    format_entity_slot_name,
    get_entity_level,
    get_home_alarm_summary,
    is_curated_area_entity,
)
from .registry import apply_ha_display_precision
from .state_index import get_area_state_index, latter_bound_esphome_device_ids

__all__ = [
    "find_area_media_entities",
    "get_area_available_domains",
    "get_area_entities",
    "get_areas_summary",
    "get_home_wide_entities",
]

_DOMAIN_PRIORITY: Final[dict[str, int]] = {
    "light": 1,
    "cover": 2,
    "fan": 3,
    "scene": 4,
    "climate": 5,
    "switch": 6,
    "input_boolean": 6,
    "media_player": 7,
}
_DEFAULT_DOMAIN_PRIORITY: Final = 99
_ACTIVE_ENTITY_STATES: Final[frozenset[str]] = frozenset(
    {
        STATE_ON,
        STATE_OPEN,
        STATE_PLAYING,
        "heat",
        "cool",
        "heat_cool",
        "auto",
    }
)
_DOMAIN_FILTER_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "scene": ("scene",),
    "scenes": ("scene",),
    "light": ("light",),
    "lights": ("light",),
    "cover": ("cover",),
    "covers": ("cover",),
    "shades": ("cover",),
    "blinds": ("cover",),
    "curtains": ("cover",),
    "fan": ("fan",),
    "fans": ("fan",),
    "switch": ("switch", "input_boolean"),
    "switches": ("switch", "input_boolean"),
    "outlet": ("switch", "input_boolean"),
    "outlets": ("switch", "input_boolean"),
    "helper": ("switch", "input_boolean"),
    "helpers": ("switch", "input_boolean"),
    "media": ("media_player",),
    "media_player": ("media_player",),
    "speaker": ("media_player",),
    "speakers": ("media_player",),
}


def get_home_wide_entities(
    hass: HomeAssistant,
    configured_alarm_entity: str | None = None,
) -> list[dict[str, Any]]:
    """Return home-wide security alarm entities (`mode='home'`)."""
    alarm_info = get_home_alarm_summary(hass, configured_alarm_entity)
    if not alarm_info["entity_id"]:
        return []
    state_obj = hass.states.get(alarm_info["entity_id"])
    if state_obj is None:
        return []
    return [
        {
            "name": format_entity_slot_name(state_obj),
            "id": state_obj.entity_id,
            "type": "alarm_control_panel",
            "active": state_obj.state != "disarmed",
            "level": -1,
        }
    ]


def _resolve_area_sensor_temp(
    sensor_states: list[State],
    ent_reg: er.EntityRegistry,
    bound_device_ids: set[str],
) -> int | float | None:
    for state_obj in sorted(sensor_states, key=lambda s: s.entity_id):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        if str(state_obj.attributes.get("device_class") or "").lower() != "temperature":
            continue
        entry = ent_reg.async_get(state_obj.entity_id)
        if entry is not None and (
            entry.platform == DOMAIN
            or bool(entry.disabled_by)
            or bool(entry.hidden_by)
            or entry.entity_category is not None
            or (entry.device_id and entry.device_id in bound_device_ids)
        ):
            continue
        try:
            raw_f = float(state_obj.state)
            if math.isfinite(raw_f):
                return apply_ha_display_precision(entry, raw_f, default_precision=0)
        except (TypeError, ValueError):
            continue
    return None


def get_areas_summary(
    hass: HomeAssistant,
    active_area_id: str | None = None,
    local_speaker: str = "",
) -> list[dict[str, Any]]:
    """Return a sorted list of Home Assistant Areas that contain curated controllable entities."""
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    idx = get_area_state_index(hass)
    bound_device_ids = latter_bound_esphome_device_ids(hass)

    items: list[dict[str, Any]] = []
    for area in area_reg.async_list_areas():
        area_temp = _resolve_area_sensor_temp(
            idx.entities_in_area(area.id, ("sensor",)), ent_reg, bound_device_ids
        )
        total = 0
        lights_on = 0
        climate_fallback: float | None = None

        for state_obj in idx.entities_in_area(area.id, AREA_CONTROL_DOMAINS):
            if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                continue
            if not is_curated_area_entity(
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
                    cand_t = float(state_obj.attributes["current_temperature"])
                    if math.isfinite(cand_t):
                        climate_fallback = round(cand_t, 1)
                except (TypeError, ValueError):
                    continue

        if total == 0:
            continue
        temp_val = area_temp if area_temp is not None else climate_fallback
        suffix_parts: list[str] = []
        if temp_val is not None:
            suffix_parts.append(f"{round(temp_val)}°")
        if lights_on > 0:
            suffix_parts.append(f"{lights_on} on")

        label = f"{area.name} ({', '.join(suffix_parts)})" if suffix_parts else area.name
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
    raw = domain_filter.strip().lower()
    if not raw or raw == "all":
        return AREA_CONTROL_DOMAINS
    if raw in _DOMAIN_FILTER_ALIASES:
        return _DOMAIN_FILTER_ALIASES[raw]
    if "," in raw:
        parts = [p.strip() for p in raw.split(",") if p.strip() in AREA_CONTROL_DOMAINS]
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


def get_area_entities(
    hass: HomeAssistant,
    area_id: str | None,
    domain_filter: str = "all",
    local_speaker: str = "",
) -> list[dict[str, Any]]:
    """Return curated controllable entities for a specific Area via `AreaStateIndex`."""
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    idx = get_area_state_index(hass)
    bound_device_ids = latter_bound_esphome_device_ids(hass)
    area_entry = area_reg.async_get_area(area_id) if area_id else None
    area_name = area_entry.name if area_entry else ""

    allowed_domains = _parse_domain_filter(domain_filter)
    if area_id:
        candidate_states = idx.entities_in_area(area_id, allowed_domains)
    else:
        candidate_states = []
        for dom in allowed_domains:
            candidate_states.extend(idx.states_for_domain(dom))

    items: list[dict[str, Any]] = []
    for state_obj in candidate_states:
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        if not is_curated_area_entity(
            hass,
            state_obj,
            local_speaker,
            ent_reg=ent_reg,
            bound_device_ids=bound_device_ids,
        ):
            continue

        level = get_entity_level(state_obj)
        if state_obj.domain == "climate" and level < 0:
            tgt_val, _ = extract_climate_temps(state_obj)
            if tgt_val is not None:
                level = round(float(tgt_val))
        items.append(
            {
                "name": format_entity_slot_name(state_obj, area_name),
                "id": state_obj.entity_id,
                "type": state_obj.domain,
                "active": state_obj.state in _ACTIVE_ENTITY_STATES,
                "level": level,
                "_prio": _DOMAIN_PRIORITY.get(
                    state_obj.domain, _DEFAULT_DOMAIN_PRIORITY
                ),
            }
        )

    items.sort(key=lambda x: (x["_prio"], not x["active"], x["name"].lower()))
    return items
