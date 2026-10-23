"""Area-Aware Room Discovery, Control & Context Handoff Engine for Latter."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
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

_LOGGER = logging.getLogger(__name__)

ROOM_CONTROL_DOMAINS: tuple[str, ...] = (
    "light",
    "cover",
    "climate",
    "fan",
    "switch",
    "scene",
)


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


def get_entity_level(state_obj: State) -> int:
    """Compute a normalized 0..100 level for horizontal fill-slider UI cards."""
    domain = state_obj.domain
    attrs = state_obj.attributes
    is_active = state_obj.state in (STATE_ON, STATE_OPEN, STATE_PLAYING, "heat", "cool", "heat_cool", "auto")

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

    if domain == "climate":
        temp = attrs.get("temperature") or attrs.get("current_temperature")
        if temp is not None:
            return max(0, min(100, int(round(float(temp)))))
        return 0

    return 100 if is_active else 0


def format_entity_slot_name(state_obj: State, area_name: str = "") -> str:
    """Format a compact, informative slot label for ESPHome display cards."""
    friendly = str(state_obj.attributes.get("friendly_name") or state_obj.entity_id)
    if area_name and friendly.lower().startswith(area_name.lower() + " "):
        friendly = friendly[len(area_name) + 1 :].strip() or friendly

    domain = state_obj.domain
    level = get_entity_level(state_obj)

    if domain == "light" and state_obj.state == STATE_ON:
        return f"{friendly} ({level}%)"
    if domain == "cover":
        return f"{friendly} ({level}%)"
    if domain == "climate":
        cur = state_obj.attributes.get("current_temperature")
        tgt = state_obj.attributes.get("temperature")
        if tgt is not None:
            return f"{friendly} ({int(round(float(tgt)))}°)"
        if cur is not None:
            return f"{friendly} ({int(round(float(cur)))}°)"
    if domain == "fan" and state_obj.state == STATE_ON:
        return f"{friendly} ({level}%)"
    return friendly


def get_areas_summary(
    hass: HomeAssistant, active_area_id: str | None = None
) -> list[dict[str, Any]]:
    """Return a sorted list of Home Assistant areas that contain controllable entities."""
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)

    area_counts: dict[str, dict[str, int]] = {}
    for state_obj in hass.states.async_all():
        if state_obj.domain not in ROOM_CONTROL_DOMAINS and state_obj.domain != "media_player":
            continue
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        entry = ent_reg.async_get(state_obj.entity_id)
        if entry and (entry.disabled_by or entry.hidden_by):
            continue

        a_id = resolve_entity_area_id(hass, state_obj.entity_id)
        if not a_id:
            continue

        counts = area_counts.setdefault(a_id, {"total": 0, "lights_on": 0})
        if state_obj.domain in ROOM_CONTROL_DOMAINS:
            counts["total"] += 1
        if state_obj.domain == "light" and state_obj.state == STATE_ON:
            counts["lights_on"] += 1

    items: list[dict[str, Any]] = []
    for area in area_reg.async_list_areas():
        counts = area_counts.get(area.id)
        if not counts or counts["total"] == 0:
            continue
        lights_on = counts["lights_on"]
        label = f"{area.name} ({lights_on} on)" if lights_on > 0 else area.name
        items.append(
            {
                "name": label,
                "id": area.id,
                "type": "area",
                "active": area.id == active_area_id,
                "level": min(100, lights_on * 25),
                "_raw_name": area.name,
            }
        )

    items.sort(key=lambda x: (not x["active"], x["_raw_name"].lower()))
    return items


def get_area_entities(
    hass: HomeAssistant,
    area_id: str | None,
    domain_filter: str = "all",
    custom_entities: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return controllable entities for a specific area (plus any pinned custom entities)."""
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    area_entry = area_reg.async_get_area(area_id) if area_id else None
    area_name = area_entry.name if area_entry else ""

    domain_filter = domain_filter.strip().lower()
    allowed_domains = (
        (domain_filter,)
        if domain_filter in ROOM_CONTROL_DOMAINS
        else ROOM_CONTROL_DOMAINS
    )

    pinned_set = set(custom_entities or [])
    items: list[dict[str, Any]] = []

    domain_priority = {
        "light": 1,
        "climate": 2,
        "cover": 3,
        "fan": 4,
        "switch": 5,
        "scene": 6,
    }

    for state_obj in hass.states.async_all():
        ent_id = state_obj.entity_id
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue

        is_pinned = ent_id in pinned_set
        if not is_pinned:
            if state_obj.domain not in allowed_domains:
                continue
            entry = ent_reg.async_get(ent_id)
            if entry and (entry.disabled_by or entry.hidden_by):
                continue
            ent_area = resolve_entity_area_id(hass, ent_id)
            if area_id and ent_area != area_id:
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
    """Discover the primary speaker and TV/remote entity inside an area for Context Handoff."""
    result = {"speaker": "", "remote": ""}
    if not area_id:
        return result

    for state_obj in hass.states.async_all("media_player"):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        if state_obj.entity_id == local_speaker:
            continue
        if resolve_entity_area_id(hass, state_obj.entity_id) == area_id:
            dev_class = str(state_obj.attributes.get("device_class") or "").lower()
            if dev_class == "tv" and not result["remote"]:
                result["remote"] = state_obj.entity_id
            elif not result["speaker"]:
                result["speaker"] = state_obj.entity_id

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
) -> None:
    """Execute a normalized room control action across light, cover, climate, fan, switch, scene."""
    state_obj = hass.states.get(entity_id)
    if state_obj is None:
        _LOGGER.warning("Room action target entity not found: %s", entity_id)
        return

    domain = state_obj.domain
    action = action.strip().lower()
    cur_level = get_entity_level(state_obj)

    if action in ("step_up", "step_down") and level is None:
        step = 10 if domain != "climate" else 1
        level = max(0, min(100, cur_level + (step if action == "step_up" else -step)))
        action = "set_level"

    if domain == "scene":
        await hass.services.async_call(
            "scene", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=False
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
        svc = "toggle"
        if domain == "cover":
            svc = (
                "close_cover"
                if state_obj.state == STATE_OPEN
                else "open_cover"
            )
        await hass.services.async_call(
            domain, svc, {ATTR_ENTITY_ID: entity_id}, blocking=False
        )