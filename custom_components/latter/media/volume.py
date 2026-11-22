"""Canonical 0.0..1.0 vs 0..100% media volume reader and executor (`L2a`, `M-P1-38`)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State

from .linking import safe_float, safe_opt_float

VOLUME_SET_FLAG: Final[int] = 4
VOLUME_MUTE_FLAG: Final[int] = 8
VOLUME_STEP_FLAG: Final[int] = 1024
VOLUME_FEATURE_FLAGS: Final[int] = VOLUME_SET_FLAG | VOLUME_MUTE_FLAG | VOLUME_STEP_FLAG

_DEFAULT_NUMBER_MIDPOINT: Final[float] = 50.0
_DEFAULT_NUMBER_MAX: Final[float] = 100.0
_DEFAULT_STEP_FRACTION: Final[float] = 0.05
_PERCENT_DIVISOR: Final[float] = 100.0


def read_volume_from_target(
    hass: HomeAssistant, vol_target: str, fallback_attrs: Mapping[str, Any]
) -> float | None:
    """Read normalized `0.0..1.0` volume from `media_player`, `number`, or `input_number`, or `None`."""
    vol_state = hass.states.get(vol_target)
    if vol_state is not None and vol_state.state not in (
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        if vol_state.domain in ("number", "input_number"):
            val = safe_opt_float(vol_state.state)
            min_v = safe_float(vol_state.attributes.get("min"), 0.0)
            max_v = safe_float(vol_state.attributes.get("max"), _DEFAULT_NUMBER_MAX)
            if val is not None and max_v > min_v:
                return max(0.0, min(1.0, (val - min_v) / (max_v - min_v)))
        else:
            parsed_lvl = safe_opt_float(vol_state.attributes.get("volume_level"))
            if parsed_lvl is not None:
                return max(0.0, min(1.0, parsed_lvl))

    fb_lvl = safe_opt_float(fallback_attrs.get("volume_level"))
    if fb_lvl is not None:
        return max(0.0, min(1.0, fb_lvl))
    return None


def resolve_canonical_volume(
    volume_level: float | None, volume_pct: float | int | None
) -> float | None:
    """Resolve explicit `volume_pct` (`0..100`) or canonical `volume_level` (`0.0..1.0`) without discontinuity (`M-P1-38`)."""
    if volume_pct is not None:
        pct = safe_opt_float(volume_pct)
        if pct is None:
            return None
        return max(0.0, min(1.0, pct / _PERCENT_DIVISOR))
    if volume_level is not None:
        lvl = safe_opt_float(volume_level)
        if lvl is None:
            return None
        return max(0.0, min(1.0, lvl))
    return None


_resolve_canonical_volume = resolve_canonical_volume


def _normalize_volume_action_token(action: str) -> str:
    norm_action = action.strip().lower()
    if norm_action == "volume_up":
        return "up"
    if norm_action == "volume_down":
        return "down"
    if norm_action == "volume_mute":
        return "mute"
    return norm_action


async def _async_execute_number_volume(
    hass: HomeAssistant,
    vol_target: str,
    state_obj: State | None,
    norm_action: str,
    resolved_lvl: float | None,
) -> bool:
    target_domain = state_obj.domain if state_obj else vol_target.split(".", 1)[0]
    cur_val = (
        safe_float(state_obj.state, _DEFAULT_NUMBER_MIDPOINT)
        if (state_obj and state_obj.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN))
        else _DEFAULT_NUMBER_MIDPOINT
    )
    min_v = safe_float(state_obj.attributes.get("min"), 0.0) if state_obj else 0.0
    max_v = (
        safe_float(state_obj.attributes.get("max"), _DEFAULT_NUMBER_MAX)
        if state_obj
        else _DEFAULT_NUMBER_MAX
    )
    native_step = (
        safe_opt_float(state_obj.attributes.get("step")) if state_obj else None
    )
    step = (
        native_step
        if (native_step is not None and native_step > 0)
        else max(1.0, (max_v - min_v) * _DEFAULT_STEP_FRACTION)
    )

    if norm_action == "up":
        new_val = min(max_v, cur_val + step)
    elif norm_action == "down":
        new_val = max(min_v, cur_val - step)
    elif resolved_lvl is not None:
        new_val = min_v + resolved_lvl * (max_v - min_v)
    else:
        return False

    await hass.services.async_call(
        target_domain,
        "set_value",
        {ATTR_ENTITY_ID: vol_target, "value": round(new_val, 2)},
        blocking=False,
    )
    return True


def _parse_volume_feature_flags(state_obj: State | None) -> tuple[bool, bool, bool]:
    raw_sf = state_obj.attributes.get("supported_features") if state_obj else None
    sf: int | None = None
    if raw_sf is not None and not isinstance(raw_sf, bool):
        try:
            sf = int(raw_sf)
        except (ValueError, TypeError):
            sf = None
    if sf is None:
        return True, True, True
    return (
        (sf & VOLUME_SET_FLAG) != 0,
        (sf & VOLUME_MUTE_FLAG) != 0,
        (sf & VOLUME_STEP_FLAG) != 0,
    )


async def _async_execute_media_player_volume(
    hass: HomeAssistant,
    vol_target: str,
    state_obj: State | None,
    norm_action: str,
    resolved_lvl: float | None,
) -> bool:
    can_set, can_mute, can_step = _parse_volume_feature_flags(state_obj)
    supports_vol_set = bool(
        can_set
        and state_obj is not None
        and safe_opt_float(state_obj.attributes.get("volume_level")) is not None
    )
    svc_name = ""
    svc_data: dict[str, Any] = {ATTR_ENTITY_ID: vol_target}
    if norm_action in ("up", "down") and resolved_lvl is not None and supports_vol_set:
        svc_name = "volume_set"
        svc_data["volume_level"] = round(resolved_lvl, 2)
    elif norm_action in ("up", "down"):
        if can_step:
            svc_name = "volume_up" if norm_action == "up" else "volume_down"
    elif norm_action == "mute":
        if can_mute:
            is_muted = bool(state_obj.attributes.get("is_volume_muted", False)) if state_obj else False
            svc_name = "volume_mute"
            svc_data["is_volume_muted"] = not is_muted
    elif resolved_lvl is not None and can_set:
        svc_name = "volume_set"
        svc_data["volume_level"] = round(resolved_lvl, 2)

    if not svc_name:
        return False
    await hass.services.async_call("media_player", svc_name, svc_data, blocking=False)
    return True


async def async_execute_volume_action(
    hass: HomeAssistant,
    vol_target: str,
    action: str,
    volume_level: float | None = None,
    *,
    volume_pct: float | int | None = None,
) -> bool:
    """Execute a volume action (`'set'`, `'up'`, `'down'`, `'mute'`) on `media_player`, `number`, or `input_number`."""
    if not vol_target:
        return False
    state_obj = hass.states.get(vol_target)
    target_domain = state_obj.domain if state_obj else vol_target.split(".", 1)[0]
    norm_action = _normalize_volume_action_token(action)
    resolved_lvl = resolve_canonical_volume(volume_level, volume_pct)

    if target_domain in ("number", "input_number"):
        return await _async_execute_number_volume(
            hass, vol_target, state_obj, norm_action, resolved_lvl
        )
    if target_domain == "media_player":
        return await _async_execute_media_player_volume(
            hass, vol_target, state_obj, norm_action, resolved_lvl
        )
    return False
