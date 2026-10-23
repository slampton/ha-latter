"""Area-Aware Room Discovery, Curated Entity Filtering, Telemetry, Alarm & Remote Engine for Latter."""

from __future__ import annotations

import logging
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

from .ble_engine import get_ble_proxy_area_ids
from .browse_engine import is_music_assistant_player

_LOGGER = logging.getLogger(__name__)

ROOM_CONTROL_DOMAINS: tuple[str, ...] = (
    "light",
    "scene",
    "cover",
    "fan",
    "switch",
    "climate",
    "media_player",
)

WINDOW_COVER_CLASSES: set[str] = {
    "awning",
    "blind",
    "curtain",
    "shade",
    "shutter",
    "window",
    "",
}


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
    """Find the Home Assistant device_id for the target Pocket Assistant ESPHome node."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    slug_norm = device_slug.strip().lower().replace("-", "_")

    for entry in ent_reg.entities.values():
        if entry.platform == "esphome" and slug_norm in entry.entity_id:
            if entry.device_id:
                return entry.device_id

    for dev in dev_reg.devices.values():
        dev_name = str(dev.name_by_user or dev.name or "").lower().replace("-", "_")
        if slug_norm and slug_norm in dev_name:
            return dev.id

    return None


def protect_handheld_sensors_from_area_dashboards(
    hass: HomeAssistant, device_slug: str
) -> None:
    """Mark on-device temperature/humidity sensors on the handheld as DIAGNOSTIC so they never pollute room dashboards."""
    target_device_id = find_esphome_device_id(hass, device_slug)
    if not target_device_id:
        return

    ent_reg = er.async_get(hass)
    for entry in er.async_entries_for_device(ent_reg, target_device_id):
        if entry.domain != "sensor":
            continue
        state_obj = hass.states.get(entry.entity_id)
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
            _LOGGER.info(
                "Marked handheld sensor '%s' as DIAGNOSTIC so it will not override room Area temperatures",
                entry.entity_id,
            )


def sync_esphome_device_area(
    hass: HomeAssistant,
    device_slug: str,
    area_id: str,
    require_ble_proxy_area: bool = True,
) -> None:
    """Update the Pocket Assistant ESPHome device's area_id in HA Device Registry ONLY for valid rooms."""
    if not area_id:
        return

    # Safeguard: If require_ble_proxy_area is True and BLE proxies exist, never assign the device to a room with no BLE proxy!
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
    }
    if not configured_entity_id:
        return empty

    ent_id = configured_entity_id.strip()
    state_obj = hass.states.get(ent_id)
    if state_obj is None:
        return empty

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(ent_id)

    remote_ent = ent_id if state_obj.domain == "remote" else ""
    mp_ent = ent_id if state_obj.domain == "media_player" else ""

    if entry and entry.device_id:
        for sib in er.async_entries_for_device(ent_reg, entry.device_id):
            if sib.disabled_by:
                continue
            if sib.domain == "remote" and not remote_ent:
                remote_ent = sib.entity_id
            elif sib.domain == "media_player" and not mp_ent:
                mp_ent = sib.entity_id

    primary_state = hass.states.get(mp_ent) or state_obj
    friendly = str(
        primary_state.attributes.get("friendly_name")
        or state_obj.attributes.get("friendly_name")
        or ent_id
    )
    area_id = resolve_entity_area_id(hass, ent_id) or ""

    return {
        "name": friendly[:32],
        "remote_entity": remote_ent or mp_ent,
        "media_player_entity": mp_ent or remote_ent,
        "area_id": area_id,
        "state": primary_state.state,
    }


def _is_curated_room_entity(
    hass: HomeAssistant, state_obj: State, local_speaker: str = ""
) -> bool:
    """Strictly filter out config/diagnostic entities, non-outlet switches, and non-MA speakers."""
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

    if domain in ("light", "scene", "fan", "climate"):
        return True

    if domain == "cover":
        return dev_class in WINDOW_COVER_CLASSES

    if domain == "switch":
        if dev_class == "outlet":
            return True
        name_low = str(attrs.get("friendly_name") or state_obj.entity_id).lower()
        return any(k in name_low for k in ("outlet", "plug", "lamp", "socket"))

    if domain == "media_player":
        if state_obj.entity_id == local_speaker:
            return False
        return is_music_assistant_player(hass, state_obj)

    return False


def get_entity_level(state_obj: State) -> int:
    """Compute a normalized 0..100 level for horizontal fill-slider UI cards."""
    domain = state_obj.domain
    attrs = state_obj.attributes
    is_active = state_obj.state in (
        STATE_ON,
        STATE_OPEN,
        STATE_PLAYING,
        "heat",
        "cool",
        "heat_cool",
        "auto",
        "armed_home",
        "armed_away",
        "armed_night",
    )

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

    if domain == "media_player":
        vol = attrs.get("volume_level")
        if vol is not None:
            return max(0, min(100, int(round(float(vol) * 100))))
        return 50 if is_active else 0

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
    if domain == "media_player":
        return f"Speaker: {friendly}"
    if domain == "alarm_control_panel":
        return f"Alarm: {state_obj.state.replace('_', ' ').title()}"
    return friendly


def get_area_climate_telemetry(
    hass: HomeAssistant, area_id: str | None, device_slug: str = "pocket_assistant"
) -> dict[str, Any]:
    """Discover ambient room temperature and humidity assigned to an area (excluding the handheld itself!)."""
    result: dict[str, Any] = {
        "temperature": None,
        "temperature_unit": "",
        "humidity": None,
    }
    if not area_id:
        return result

    ent_reg = er.async_get(hass)
    handheld_dev_id = find_esphome_device_id(hass, device_slug)
    slug_norm = device_slug.strip().lower().replace("-", "_")

    for state_obj in hass.states.async_all("sensor"):
        if state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        # Never use the handheld's own internal battery/die temperature sensor as room temperature!
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
                result["temperature"] = round(float(state_obj.state), 1)
                result["temperature_unit"] = str(
                    state_obj.attributes.get("unit_of_measurement") or "°"
                )
            except ValueError:
                pass
        elif dev_class == "humidity" and result["humidity"] is None:
            try:
                result["humidity"] = round(float(state_obj.state), 1)
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
                    "level": 100 if is_armed else 0,
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
    device_slug: str = "pocket_assistant",
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
    local_speaker: str = "",
) -> list[dict[str, Any]]:
    """Return curated controllable entities for a specific area."""
    area_reg = ar.async_get(hass)
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
        "scene": 2,
        "cover": 3,
        "fan": 4,
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
) -> None:
    """Execute a normalized room or home-alarm action."""
    state_obj = hass.states.get(entity_id)
    if state_obj is None:
        _LOGGER.warning("Room action target entity not found: %s", entity_id)
        return

    domain = state_obj.domain
    action = action.strip().lower()
    cur_level = get_entity_level(state_obj)

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