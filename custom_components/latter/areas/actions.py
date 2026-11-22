"""Normalized Area, Home Hub, perimeter security, and light color/kelvin action executor (`L2b`)."""

from __future__ import annotations

import logging
import math
from typing import Any, Final

from homeassistant.components.lock.const import LockEntityFeature
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_ON,
    STATE_OPEN,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from ..const import CONF_ALARM_ENTITY, DATA_GLOBAL_CONFIG, DOMAIN
from ..media.playback import async_execute_volume_action
from ..protocol_policy import is_valid_pin_digits
from .curation import get_entity_level, get_home_alarm_summary

_LOGGER = logging.getLogger(__name__)

_MIN_KELVIN: Final = 2000
_MAX_KELVIN: Final = 6500
_MIN_CLIMATE_STEP_TEMP: Final = 5
_DEFAULT_CLIMATE_BASE_TEMP: Final = 20
_LEVEL_STEP: Final = 10

_ALARM_ACTION_ALIASES: Final[dict[str, str]] = {
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

_ALARM_SERVICE_MAP: Final[dict[str, str]] = {
    "arm_home": "alarm_arm_home",
    "arm_away": "alarm_arm_away",
    "arm_night": "alarm_arm_night",
    "arm_vacation": "alarm_arm_vacation",
    "disarm": "alarm_disarm",
}

_CLIMATE_HVAC_MAP: Final[dict[str, str]] = {
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

_GENERIC_TOGGLE_DOMAINS: Final[frozenset[str]] = frozenset(
    {
        "light",
        "switch",
        "input_boolean",
        "fan",
        "cover",
        "media_player",
        "humidifier",
        "water_heater",
        "siren",
        "remote",
    }
)


def _resolve_target_state(
    hass: HomeAssistant, entity_id: str, action: str
) -> tuple[str, State | None]:
    if not entity_id and action in _ALARM_SERVICE_MAP:
        entity_id = "home_hub.alarm"
    state_obj = hass.states.get(entity_id)
    if state_obj is None and entity_id == "home_hub.alarm":
        global_cfg = (hass.data.get(DOMAIN) or {}).get(DATA_GLOBAL_CONFIG) or {}
        mapped_id = get_home_alarm_summary(
            hass, global_cfg.get(CONF_ALARM_ENTITY)
        )["entity_id"]
        if mapped_id:
            entity_id = mapped_id
            state_obj = hass.states.get(entity_id)
    return entity_id, state_obj


async def _execute_alarm_action(
    hass: HomeAssistant, state_obj: State, action: str, code: str | None
) -> None:
    svc = _ALARM_SERVICE_MAP.get(action)
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
        if code_fmt == "number" and not is_valid_pin_digits(clean_code):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="security_pin_invalid",
            )
    payload: dict[str, Any] = {ATTR_ENTITY_ID: state_obj.entity_id}
    if clean_code:
        payload["code"] = clean_code
    await hass.services.async_call("alarm_control_panel", svc, payload, blocking=True)


async def _execute_lock_action(
    hass: HomeAssistant, state_obj: State, action: str
) -> None:
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
        "lock", action, {ATTR_ENTITY_ID: state_obj.entity_id}, blocking=True
    )


def _compute_climate_step_level(state_obj: State, action: str) -> int:
    c_attrs = state_obj.attributes
    raw_t = c_attrs.get("temperature")
    if (
        raw_t is None
        and c_attrs.get("target_temp_low") is not None
        and c_attrs.get("target_temp_high") is not None
    ):
        try:
            raw_t = (
                float(c_attrs["target_temp_low"]) + float(c_attrs["target_temp_high"])
            ) / 2.0
        except (TypeError, ValueError):
            raw_t = None
    if raw_t is None:
        raw_t = c_attrs.get("target_temp_low") or c_attrs.get("current_temperature")
    try:
        base_t = (
            round(float(raw_t))
            if raw_t is not None and math.isfinite(float(raw_t))
            else _DEFAULT_CLIMATE_BASE_TEMP
        )
    except (TypeError, ValueError):
        base_t = _DEFAULT_CLIMATE_BASE_TEMP
    delta = 1 if action == "step_up" else -1
    return max(_MIN_CLIMATE_STEP_TEMP, min(100, base_t + delta))


async def _execute_media_step(
    hass: HomeAssistant, state_obj: State, action: str
) -> None:
    raw_v = state_obj.attributes.get("volume_level")
    step_lvl: float | None = None
    if raw_v is not None:
        try:
            f_val = float(raw_v)
            if math.isfinite(f_val):
                base_v = round(f_val * 100)
                delta = _LEVEL_STEP if action == "step_up" else -_LEVEL_STEP
                step_lvl = float(max(0, min(100, base_v + delta)))
        except (TypeError, ValueError):
            step_lvl = None
    await async_execute_volume_action(
        hass,
        state_obj.entity_id,
        "up" if action == "step_up" else "down",
        volume_pct=step_lvl,
    )


async def _try_light_special_action(
    hass: HomeAssistant,
    entity_id: str,
    action: str,
    params: tuple[float | None, str | None],
    *,
    blocking: bool,
) -> bool:
    level, code = params
    if action == "set_color" and code:
        hex_s = code.strip().lstrip("#")
        if len(hex_s) == 6:
            try:
                rgb = [int(hex_s[0:2], 16), int(hex_s[2:4], 16), int(hex_s[4:6], 16)]
            except ValueError:
                return False
            payload_c: dict[str, Any] = {ATTR_ENTITY_ID: entity_id, "rgb_color": rgb}
            if level is not None and int(level) > 0:
                payload_c["brightness_pct"] = max(1, min(100, int(level)))
            await hass.services.async_call(
                "light", "turn_on", payload_c, blocking=blocking
            )
            return True
    if action == "set_kelvin" and level is not None:
        kelvin = max(_MIN_KELVIN, min(_MAX_KELVIN, int(level)))
        await hass.services.async_call(
            "light",
            "turn_on",
            {ATTR_ENTITY_ID: entity_id, "color_temp_kelvin": kelvin},
            blocking=blocking,
        )
        return True
    return False


async def _execute_climate_setpoint(
    hass: HomeAssistant, state_obj: State, level: float, *, blocking: bool
) -> None:
    entity_id = state_obj.entity_id
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
        except (TypeError, ValueError):
            _LOGGER.debug("Fallback to single setpoint for %s", entity_id)
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: entity_id, "temperature": float(level)},
        blocking=blocking,
    )


async def _execute_climate_toggle(
    hass: HomeAssistant,
    state_obj: State,
    hvac_modes_low: list[str],
    *,
    blocking: bool,
) -> None:
    entity_id = state_obj.entity_id
    if hass.services.has_service("climate", "toggle"):
        await hass.services.async_call(
            "climate", "toggle", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
    elif state_obj.state == "off":
        active_modes = [m for m in hvac_modes_low if m != "off"]
        if active_modes:
            await hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {ATTR_ENTITY_ID: entity_id, "hvac_mode": active_modes[0]},
                blocking=blocking,
            )
        else:
            await hass.services.async_call(
                "climate", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
            )
    elif "off" in hvac_modes_low:
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {ATTR_ENTITY_ID: entity_id, "hvac_mode": "off"},
            blocking=blocking,
        )
    else:
        await hass.services.async_call(
            "climate", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )


async def _try_climate_action(
    hass: HomeAssistant,
    state_obj: State,
    action: str,
    level: float | None,
    *,
    blocking: bool,
) -> bool:
    entity_id = state_obj.entity_id
    if action in _CLIMATE_HVAC_MAP:
        target_mode = _CLIMATE_HVAC_MAP[action]
        hvac_modes = [str(m) for m in (state_obj.attributes.get("hvac_modes") or ())]
        if target_mode == "heat_cool" and "heat_cool" not in hvac_modes and "auto" in hvac_modes:
            target_mode = "auto"
        elif target_mode == "auto" and "auto" not in hvac_modes and "heat_cool" in hvac_modes:
            target_mode = "heat_cool"
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {ATTR_ENTITY_ID: entity_id, "hvac_mode": target_mode},
            blocking=blocking,
        )
        return True

    if action in ("set_level", "set_temperature") and level is not None:
        await _execute_climate_setpoint(hass, state_obj, level, blocking=blocking)
        return True

    hvac_modes_low = [str(m).lower() for m in (state_obj.attributes.get("hvac_modes") or ())]
    if action == "turn_off":
        if "off" in hvac_modes_low:
            await hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {ATTR_ENTITY_ID: entity_id, "hvac_mode": "off"},
                blocking=blocking,
            )
        else:
            await hass.services.async_call(
                "climate", "turn_off", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
            )
        return True
    if action == "turn_on":
        active_modes = [m for m in hvac_modes_low if m != "off"]
        if active_modes and not hass.services.has_service("climate", "turn_on"):
            await hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {ATTR_ENTITY_ID: entity_id, "hvac_mode": active_modes[0]},
                blocking=blocking,
            )
        else:
            await hass.services.async_call(
                "climate", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
            )
        return True
    if action == "toggle":
        await _execute_climate_toggle(hass, state_obj, hvac_modes_low, blocking=blocking)
        return True
    return False


async def _execute_vacuum_action(
    hass: HomeAssistant, state_obj: State, action: str, *, blocking: bool
) -> None:
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
        "vacuum", svc_v, {ATTR_ENTITY_ID: state_obj.entity_id}, blocking=blocking
    )


async def _try_set_level_action(
    hass: HomeAssistant, state_obj: State, level: float, *, blocking: bool
) -> bool:
    domain = state_obj.domain
    entity_id = state_obj.entity_id
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
        return True
    if domain == "cover":
        await hass.services.async_call(
            "cover",
            "set_cover_position",
            {ATTR_ENTITY_ID: entity_id, "position": lvl},
            blocking=blocking,
        )
        return True
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
        return True
    if domain == "media_player":
        await async_execute_volume_action(hass, entity_id, "set", volume_pct=float(lvl))
        return True
    return False


async def _try_stateless_or_helper_domain(
    hass: HomeAssistant,
    state_obj: State,
    action: str,
    *,
    level: float | None,
    option: str | None,
    blocking: bool,
    raise_on_missing: bool,
) -> bool:
    domain = state_obj.domain
    entity_id = state_obj.entity_id
    if domain in ("button", "input_button"):
        await hass.services.async_call(
            domain, "press", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return True
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
        return True
    if domain in ("select", "input_select"):
        if option is not None:
            await hass.services.async_call(
                domain,
                "select_option",
                {ATTR_ENTITY_ID: entity_id, "option": str(option)},
                blocking=blocking,
            )
        elif action in ("select_next", "select_previous"):
            await hass.services.async_call(
                domain, action, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
            )
        elif raise_on_missing:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="explicit_action_required",
            )
        return True
    if domain in ("number", "input_number"):
        if level is not None:
            await hass.services.async_call(
                domain,
                "set_value",
                {ATTR_ENTITY_ID: entity_id, "value": float(level)},
                blocking=blocking,
            )
        elif raise_on_missing:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="explicit_action_required",
            )
        return True
    return False


async def _try_utility_domain_action(
    hass: HomeAssistant, state_obj: State, action: str, *, blocking: bool
) -> bool:
    domain = state_obj.domain
    entity_id = state_obj.entity_id
    if domain == "scene":
        await hass.services.async_call(
            "scene", "turn_on", {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return True
    if domain == "script":
        svc_script = "turn_off" if action == "turn_off" else "turn_on"
        await hass.services.async_call(
            "script", svc_script, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return True
    if domain == "automation":
        svc_auto = (
            action if action in ("trigger", "toggle", "turn_on", "turn_off") else "trigger"
        )
        await hass.services.async_call(
            "automation", svc_auto, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return True
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
        return True
    if domain == "lawn_mower":
        svc_mower = action if action in ("start_mowing", "pause", "dock") else "start_mowing"
        await hass.services.async_call(
            "lawn_mower", svc_mower, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return True
    return False


async def _execute_generic_domain_action(
    hass: HomeAssistant,
    state_obj: State,
    action: str,
    *,
    blocking: bool,
    raise_on_missing: bool,
) -> None:
    domain = state_obj.domain
    entity_id = state_obj.entity_id
    if domain not in _GENERIC_TOGGLE_DOMAINS:
        if raise_on_missing:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="not_supported",
            )
        _LOGGER.debug("Unsupported area action '%s' for entity '%s'", action, entity_id)
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
    elif action == "toggle":
        if domain == "cover":
            svc = "close_cover" if state_obj.state == STATE_OPEN else "open_cover"
        elif domain == "media_player":
            svc = "media_play_pause"
        else:
            svc = "toggle"
        await hass.services.async_call(
            domain, svc, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
    elif raise_on_missing:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_supported",
        )


def _normalize_effective_action(
    domain: str, norm_action: str, level: float | None
) -> str:
    if norm_action:
        return norm_action
    if domain in ("alarm_control_panel", "lock"):
        return ""
    return "set_level" if level is not None else "toggle"


_MEDIA_TRANSPORT_ACTIONS: Final[frozenset[str]] = frozenset(
    {"media_play_pause", "media_next_track", "media_previous_track"}
)
_COVER_EXPLICIT_ACTIONS: Final[dict[str, str]] = {
    "open_cover": "open_cover",
    "open": "open_cover",
    "close_cover": "close_cover",
    "close": "close_cover",
    "stop_cover": "stop_cover",
    "stop": "stop_cover",
}


async def _try_domain_specific_action(
    hass: HomeAssistant,
    state_obj: State,
    eff_action: str,
    level: float | None,
    code: str | None,
    *,
    blocking: bool,
) -> bool:
    """Dispatch media transport, light color/kelvin, climate, explicit cover, vacuum, and slider levels."""
    domain = state_obj.domain
    entity_id = state_obj.entity_id
    if domain == "media_player" and eff_action in _MEDIA_TRANSPORT_ACTIONS:
        await hass.services.async_call(
            "media_player", eff_action, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return True
    if domain == "light" and await _try_light_special_action(
        hass, entity_id, eff_action, (level, code), blocking=blocking
    ):
        return True
    if domain == "climate" and await _try_climate_action(
        hass, state_obj, eff_action, level, blocking=blocking
    ):
        return True
    if domain == "cover" and (svc_cover := _COVER_EXPLICIT_ACTIONS.get(eff_action)):
        await hass.services.async_call(
            "cover", svc_cover, {ATTR_ENTITY_ID: entity_id}, blocking=blocking
        )
        return True
    if domain == "vacuum":
        await _execute_vacuum_action(hass, state_obj, eff_action, blocking=blocking)
        return True
    if eff_action == "set_level" and level is not None:
        return await _try_set_level_action(hass, state_obj, level, blocking=blocking)
    return False


def _compute_step_level(state_obj: State, eff_action: str) -> float:
    if state_obj.domain == "climate":
        return float(_compute_climate_step_level(state_obj, eff_action))
    cur_level = max(0, get_entity_level(state_obj))
    delta = _LEVEL_STEP if eff_action == "step_up" else -_LEVEL_STEP
    return float(max(0, min(100, cur_level + delta)))


async def async_execute_area_action(
    hass: HomeAssistant,
    entity_id: str,
    action: str = "toggle",
    level: float | None = None,
    code: str | None = None,
    option: str | None = None,
    *,
    blocking: bool = False,
    raise_on_missing: bool = False,
) -> None:
    """Execute a normalized Area, Home Hub, or light color/kelvin action (`M-P1-44`)."""
    raw_action = str(action or "").strip().lower()
    norm_action = _ALARM_ACTION_ALIASES.get(raw_action, raw_action)
    entity_id, state_obj = _resolve_target_state(hass, entity_id.strip(), norm_action)

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
    eff_action = _normalize_effective_action(domain, norm_action, level)

    if await _try_stateless_or_helper_domain(
        hass,
        state_obj,
        eff_action,
        level=level,
        option=option,
        blocking=blocking,
        raise_on_missing=raise_on_missing,
    ):
        return

    if domain == "media_player" and level is not None and eff_action in ("set_level", "set_volume"):
        await async_execute_volume_action(hass, entity_id, "set", volume_pct=float(level))
        return

    if domain == "alarm_control_panel":
        await _execute_alarm_action(hass, state_obj, eff_action, code)
        return
    if domain == "lock":
        await _execute_lock_action(hass, state_obj, eff_action)
        return

    if eff_action in ("step_up", "step_down") and level is None:
        if domain == "media_player":
            await _execute_media_step(hass, state_obj, eff_action)
            return
        level = _compute_step_level(state_obj, eff_action)
        eff_action = "set_level"

    if await _try_utility_domain_action(hass, state_obj, eff_action, blocking=blocking):
        return

    if await _try_domain_specific_action(
        hass, state_obj, eff_action, level, code, blocking=blocking
    ):
        return

    await _execute_generic_domain_action(
        hass,
        state_obj,
        eff_action,
        blocking=blocking,
        raise_on_missing=raise_on_missing,
    )
