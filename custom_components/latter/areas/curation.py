"""Curated Area entity filtering, capability bitmasks, slot naming, and media discovery."""

from __future__ import annotations

import math
from typing import Any, Final

from homeassistant.const import (
    STATE_ON,
    STATE_OPEN,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from ..const import DOMAIN
from ..media.linking import is_music_assistant_player
from ..protocol_codec import ha_value
from .registry import get_area_state_index, latter_bound_esphome_device_ids

AREA_CONTROL_DOMAINS: Final[tuple[str, ...]] = (
    "scene",
    "light",
    "cover",
    "fan",
    "switch",
    "input_boolean",
    "climate",
    "media_player",
)

SLIDER_CAPABLE_DOMAINS: Final[set[str]] = {
    "light",
    "cover",
    "fan",
}

WINDOW_COVER_CLASSES: Final[set[str]] = {
    "awning",
    "blind",
    "curtain",
    "drape",
    "shade",
    "shutter",
    "window",
    "",
}

_WINDOW_COVER_KEYWORDS: Final[tuple[str, ...]] = (
    "curtain",
    "drape",
    "sheer",
    "blind",
    "shade",
    "shutter",
    "window",
)


def _safe_finite_float(val: object) -> float | None:
    if val is None or isinstance(val, bool) or not isinstance(val, (int, float, str)):
        return None
    try:
        parsed = float(val)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def is_curated_area_entity(
    hass: HomeAssistant,
    state_obj: State,
    local_speaker: str = "",
    *,
    ent_reg: er.EntityRegistry | None = None,
    bound_device_ids: set[str] | None = None,
) -> bool:
    """Filter out config/diagnostic entities, Latter/ESPHome bound entities, and non-MA speakers."""
    if ent_reg is None:
        ent_reg = er.async_get(hass)
    entry = ent_reg.async_get(state_obj.entity_id)
    if entry is not None and (
        entry.platform == DOMAIN
        or bool(entry.disabled_by)
        or bool(entry.hidden_by)
        or entry.entity_category is not None
    ):
        return False

    if entry is not None and entry.device_id:
        if bound_device_ids is None:
            bound_device_ids = latter_bound_esphome_device_ids(hass)
        if entry.device_id in bound_device_ids:
            return False

    domain = state_obj.domain
    attrs = state_obj.attributes
    if domain in ("light", "scene", "fan", "climate", "switch", "input_boolean"):
        return True
    if domain == "cover":
        name_low = str(attrs.get("friendly_name") or state_obj.entity_id).lower()
        return (
            any(k in name_low for k in _WINDOW_COVER_KEYWORDS)
            or str(attrs.get("device_class") or "").lower() in WINDOW_COVER_CLASSES
        )
    return bool(
        domain == "media_player"
        and state_obj.entity_id != local_speaker
        and is_music_assistant_player(hass, state_obj)
    )


_is_curated_area_entity = is_curated_area_entity


def get_entity_level(state_obj: State) -> int:
    """Return `0..100` for slider-capable domains (`light`, `cover`, `fan`) or `-1` for others."""
    domain = state_obj.domain
    if domain not in SLIDER_CAPABLE_DOMAINS:
        return -1

    attrs = state_obj.attributes
    is_active = state_obj.state in (STATE_ON, STATE_OPEN)

    if domain == "cover":
        pos_f = _safe_finite_float(attrs.get("current_position"))
        return (
            max(0, min(100, round(pos_f)))
            if pos_f is not None
            else (100 if state_obj.state == STATE_OPEN else 0)
        )

    if not is_active:
        return 0
    if domain == "light":
        bri_f = _safe_finite_float(attrs.get("brightness"))
        return (
            max(1, min(100, round((bri_f / 255.0) * 100)))
            if bri_f is not None
            else 100
        )

    pct_f = _safe_finite_float(attrs.get("percentage"))
    return max(1, min(100, round(pct_f))) if pct_f is not None else 100


def format_entity_slot_name(state_obj: State, area_name: str = "") -> str:
    """Format a compact, informative slot label for ESPHome display cards."""
    friendly = str(state_obj.attributes.get("friendly_name") or state_obj.entity_id)
    if area_name and friendly.lower().startswith(area_name.lower() + " "):
        friendly = friendly[len(area_name) + 1 :].strip() or friendly

    domain = state_obj.domain
    level = get_entity_level(state_obj)

    if (
        (domain in ("light", "fan") and state_obj.state == STATE_ON and level >= 0)
        or (domain == "cover" and level >= 0)
    ):
        return f"{friendly} ({level}%)"
    if domain == "climate":
        temp_f = _safe_finite_float(state_obj.attributes.get("temperature"))
        if temp_f is None:
            temp_f = _safe_finite_float(state_obj.attributes.get("current_temperature"))
        return f"{friendly} ({round(temp_f)}°)" if temp_f is not None else friendly
    if domain == "media_player":
        return f"Speaker: {friendly}"
    if domain == "alarm_control_panel":
        return f"Alarm: {state_obj.state.replace('_', ' ').title()}"
    return friendly


def extract_climate_temps(state_obj: State) -> tuple[int | float | None, float | None]:
    """Extract target setpoint (or `target_temp_low`/`high` midpoint) and current temperature."""
    tgt_out: int | float | None = None
    cur_out: float | None = None
    tgt_f = _safe_finite_float(state_obj.attributes.get("temperature"))
    if tgt_f is not None:
        val_f = round(tgt_f, 1)
        tgt_out = int(val_f) if val_f.is_integer() else val_f
    else:
        low_f = _safe_finite_float(state_obj.attributes.get("target_temp_low"))
        high_f = _safe_finite_float(state_obj.attributes.get("target_temp_high"))
        if low_f is not None and high_f is not None:
            mid_f = round((low_f + high_f) / 2.0, 1)
            tgt_out = int(mid_f) if mid_f.is_integer() else mid_f
        elif low_f is not None:
            val_f = round(low_f, 1)
            tgt_out = int(val_f) if val_f.is_integer() else val_f
    cur_f = _safe_finite_float(state_obj.attributes.get("current_temperature"))
    if cur_f is not None:
        cur_out = round(cur_f, 1)
    return tgt_out, cur_out


_extract_climate_temps = extract_climate_temps


def compute_alarm_caps(state_obj: State | None) -> int:
    """Compute Protocol v3 `alarm_caps` u16 bitmask from an `alarm_control_panel` state."""
    if state_obj is None:
        return 0
    attrs = state_obj.attributes
    caps = 0
    if bool(attrs.get("code_format")):
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
    hvac_modes = {str(m).lower() for m in (attrs.get("hvac_modes") or ())}
    sf = int(attrs.get("supported_features", 0) or 0)
    caps = 0
    for mode_tok, flag in (
        ("off", 0x01),
        ("heat", 0x02),
        ("cool", 0x04),
        ("fan_only", 0x10),
        ("dry", 0x20),
    ):
        if mode_tok in hvac_modes:
            caps |= flag
    if "heat_cool" in hvac_modes or "auto" in hvac_modes:
        caps |= 0x08
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
    """Return the explicitly configured Home Hub `alarm_control_panel` summary."""
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


def find_area_media_entities(
    hass: HomeAssistant, area_id: str | None, local_speaker: str
) -> dict[str, str]:
    """Discover the primary Music Assistant speaker and TV/remote entity inside an Area."""
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
