"""Area name/icon matching, AreaStateIndex helpers, `D-075` illuminance calibration, and active/person Area resolution."""

from __future__ import annotations

from collections.abc import Mapping
import math
import re
from typing import Any, Final

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from ..const import (
    AMBIENT_LIGHT_DEADBAND_PCT,
    CONF_AREA_ILLUMINANCE_CONFIG,
    CONF_DEFAULT_AREA,
    CONF_ESPHOME_DEVICE_ID,
    DEFAULT_AREA_BRIGHT_LUX,
    DEFAULT_AREA_DARK_LUX,
    DOMAIN,
    SUBENTRY_DEVICE,
)
from ..hub_registry import (
    INDEXED_DOMAINS as INDEXED_DOMAINS,
    AreaStateIndex as AreaStateIndex,
    async_stop_area_state_index as async_stop_area_state_index,
    get_area_state_index as get_area_state_index,
    is_media_position_only_tick as is_media_position_only_tick,
    iter_coordinators,
    peek_global_config,
)
from ..identity import resolve_bound_esphome_device_id

DEFAULT_UNMATCHED_AREA_ICON: Final = "mdi:map-marker"

_NON_AREA_LOOKUP_TOKENS: Final[frozenset[str]] = frozenset(
    {"unknown", "unavailable", "not_home", "away", "none", ""}
)
_MIN_REPORTED_LUX: Final = 0.05
_MAX_CLAMPED_LUX: Final = 100000.0
_DECIMAL_LUX_CEILING: Final = 10.0
_MAX_DARK_LUX: Final = 500.0
_MAX_BRIGHT_LUX: Final = 100000.0

_CAMEL_SPLIT_RE: Final = re.compile(r"([a-z0-9])([A-Z])")
_AREA_ARCHETYPE_PATTERNS: Final[tuple[tuple[re.Pattern[str], str], ...]] = tuple(
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
        (r"\b(?:gam(?:e|es|ing)|arcade)\b", "mdi:gamepad-variant"),
        (r"\b(?:gym\w*|fitness|workout|yoga|exercise)\b", "mdi:dumbbell"),
        (r"\b(?:garage|carport)\b", "mdi:garage"),
        (r"\b(?:workshop|tools?|craft\w*)\b", "mdi:tools"),
        (r"\b(?:closet|wardrobe|dressing)\b", "mdi:wardrobe"),
        (r"\b(?:pool\w*|spa|hot\s*tub|jacuzzi)\b", "mdi:pool"),
        (r"\b(?:patio|deck|porch|balcony|terrace|lanai|veranda)\b", "mdi:balcony"),
        (r"\b(?:garden\w*|yard|lawn|outdoor\w*|backyard|courtyard)\b", "mdi:tree"),
        (r"\b(?:attic|loft)\b", "mdi:home-roof"),
        (r"\b(?:basement|cellar)\b", "mdi:stairs-down"),
        (r"\b(?:stairs?|stairwell|staircase)\b", "mdi:stairs"),
        (r"\b(?:hall\w*|corridor|landing|passage\w*)\b", "mdi:transit-connection-horizontal"),
        (r"\b(?:entry\w*|entrance|foyer|vestibule|front)\b", "mdi:door-open"),
        (r"\b(?:studio|music)\b", "mdi:speaker"),
        (r"\b(?:living|family|great|den|lounge|parlor|sitting)\b", "mdi:sofa"),
        (r"\b(?:primary|master|guest|bed\w*|bunk|dorm\w*)\b", "mdi:bed-king"),
    )
)


def resolve_entity_area_id(
    hass: HomeAssistant,
    entity_id: str,
    *,
    ent_reg: er.EntityRegistry | None = None,
    dev_reg: dr.DeviceRegistry | None = None,
) -> str | None:
    """Resolve the Home Assistant `area_id` for an entity (directly or via its parent device)."""
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


def latter_bound_esphome_device_ids(hass: HomeAssistant) -> set[str]:
    """Return all Device Registry IDs belonging to Latter or its bound ESPHome devices."""
    out: set[str] = set()
    dev_reg = dr.async_get(hass)
    for entry in hass.config_entries.async_entries(DOMAIN):
        for child_dev in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            out.add(child_dev.id)
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


def apply_ha_display_precision(
    entry: er.RegistryEntry | None, raw_val: float, default_precision: int = 0
) -> int | float:
    """Format a numeric sensor value using Home Assistant's Entity Registry `display_precision`."""
    prec: int | None = None
    if entry is not None and isinstance(entry.options, Mapping):
        sensor_opts = entry.options.get("sensor")
        if isinstance(sensor_opts, Mapping):
            if sensor_opts.get("display_precision") is not None:
                prec = int(sensor_opts["display_precision"])
            elif sensor_opts.get("suggested_display_precision") is not None:
                prec = int(sensor_opts["suggested_display_precision"])
    if prec is None:
        prec = default_precision
    if prec <= 0:
        return round(raw_val)
    return round(raw_val, prec)


_apply_ha_display_precision = apply_ha_display_precision


def match_area_by_name_or_id(hass: HomeAssistant, raw_value: str) -> str | None:
    """Match an Area name, slug, or `area_id` to a valid HA `area_id` (exact match only)."""
    val = raw_value.strip()
    if val.lower() in _NON_AREA_LOOKUP_TOKENS:
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
    """Return explicit Home Assistant `AreaEntry` icon or inferred archetype icon; empty when unassigned."""
    if area_entry is None:
        return ""
    explicit_icon = getattr(area_entry, "icon", None)
    if isinstance(explicit_icon, str) and explicit_icon.strip():
        return explicit_icon.strip()
    return infer_area_icon_from_name(getattr(area_entry, "name", "") or "")


def normalize_ambient_lux(
    lux: float,
    dark_lux: float = DEFAULT_AREA_DARK_LUX,
    bright_lux: float = DEFAULT_AREA_BRIGHT_LUX,
) -> int:
    """Map an illuminance reading (`lx`) onto a perceptual `0..100` level between `dark_lux` and `bright_lux`."""
    if not math.isfinite(lux):
        return 0
    lo = max(0.0, float(dark_lux)) if math.isfinite(dark_lux) else DEFAULT_AREA_DARK_LUX
    hi = (
        max(lo + 1.0, float(bright_lux))
        if math.isfinite(bright_lux)
        else max(lo + 1.0, DEFAULT_AREA_BRIGHT_LUX)
    )
    above = max(0.0, float(lux) - lo)
    span = max(1.0, hi - lo)
    norm = math.log1p(above) / math.log1p(span)
    return max(0, min(100, round(norm * 100.0)))


def format_ambient_lux(lux: float) -> str:
    """Format a lux reading compactly for Protocol v3 and Studio (`0`, `5.6`, `42`)."""
    if not math.isfinite(lux) or lux < _MIN_REPORTED_LUX:
        return "0"
    clamped = min(_MAX_CLAMPED_LUX, float(lux))
    if clamped < _DECIMAL_LUX_CEILING:
        formatted = f"{clamped:.1f}".rstrip("0").rstrip(".")
        return formatted or "0"
    return str(round(clamped))


def _coerce_finite_lux(raw: object) -> float | None:
    if raw is None or isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        return None
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def area_illuminance_settings(
    hass: HomeAssistant, area_id: str | None
) -> dict[str, Any]:
    """Return effective ambient light calibration settings for one Area (`D-075`)."""
    entity_id = "auto"
    dark_lux = float(DEFAULT_AREA_DARK_LUX)
    bright_lux = float(DEFAULT_AREA_BRIGHT_LUX)
    if area_id:
        global_cfg = peek_global_config(hass)
        raw_map = (
            global_cfg.get(CONF_AREA_ILLUMINANCE_CONFIG)
            if isinstance(global_cfg, Mapping)
            else None
        )
        entry = raw_map.get(area_id) if isinstance(raw_map, Mapping) else None
        if isinstance(entry, Mapping):
            raw_ent = str(entry.get("entity_id") or "").strip()
            if raw_ent:
                entity_id = raw_ent
            cand_dark = _coerce_finite_lux(entry.get("dark_lux"))
            if cand_dark is not None:
                dark_lux = max(0.0, min(_MAX_DARK_LUX, cand_dark))
            cand_bright = _coerce_finite_lux(entry.get("bright_lux"))
            if cand_bright is not None:
                bright_lux = max(dark_lux + 1.0, min(_MAX_BRIGHT_LUX, cand_bright))
    bright_lux = max(bright_lux, dark_lux + 1.0)
    return {
        "entity_id": entity_id,
        "dark_lux": round(dark_lux, 2),
        "bright_lux": round(bright_lux, 1),
    }


def _parse_illuminance_state(state_obj: State | None) -> float | None:
    """Parse a finite non-negative numeric illuminance value from `state_obj`, or `None`."""
    if state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, ""):
        return None
    val = _coerce_finite_lux(state_obj.state)
    if val is None or val < 0.0:
        return None
    return val


def _build_lux_choice_item(state_obj: State) -> dict[str, Any]:
    lux_val = _parse_illuminance_state(state_obj)
    return {
        "entity_id": state_obj.entity_id,
        "name": str(state_obj.attributes.get("friendly_name") or state_obj.entity_id),
        "lux": lux_val,
        "lux_display": format_ambient_lux(lux_val) if lux_val is not None else "",
        "available": lux_val is not None,
    }


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
    seen_eids: set[str] = set()
    for state_obj in sorted(
        idx.entities_in_area(area_id, ("sensor",)), key=lambda s: s.entity_id
    ):
        entry = ent_reg.async_get(state_obj.entity_id)
        if entry is not None and (
            entry.platform == DOMAIN
            or entry.disabled_by
            or entry.hidden_by
            or entry.entity_category is not None
            or (entry.device_id and entry.device_id in latter_dev_ids)
        ):
            continue
        attrs = state_obj.attributes
        dev_class = str(attrs.get("device_class") or "").lower()
        unit = str(attrs.get("unit_of_measurement") or "").strip().lower()
        if dev_class != "illuminance" and unit not in ("lx", "lux"):
            continue
        seen_eids.add(state_obj.entity_id)
        choices.append(_build_lux_choice_item(state_obj))

    cfg_ent = str(area_illuminance_settings(hass, area_id)["entity_id"])
    if (
        cfg_ent != "auto"
        and cfg_ent.startswith("sensor.")
        and cfg_ent not in seen_eids
        and (cfg_st := hass.states.get(cfg_ent)) is not None
    ):
        choices.append(_build_lux_choice_item(cfg_st))
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
        if st is not None:
            chosen_eid = configured_ent
            out["resolved_entity"] = configured_ent
            out["resolved_name"] = str(
                st.attributes.get("friendly_name") or configured_ent
            )
            if _parse_illuminance_state(st) is not None:
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


def resolve_active_area_entry(coordinator: Any) -> ar.AreaEntry | None:
    """Resolve the current `AreaEntry` for `coordinator` from BLE lock, sticky Area, default, or ESPHome Area."""
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
    ble_tracker = coordinator.ble_tracker
    ble_area_id = (
        ble_tracker.current_area_id
        if (coordinator.native_ble_tracking_enabled and ble_tracker is not None)
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
    """Resolve the freshest Area and metric BLE distance across all Latter devices carried by a person."""
    target_low = str(person_entity or "").strip().lower()
    p_coords = [
        v
        for v in iter_coordinators(hass)
        if str(getattr(v, "assigned_person", "") or "").lower() == target_low
    ]
    if not p_coords:
        return "Unassigned", {
            "person_entity": person_entity,
            "area_id": "",
            "area_name": "Unassigned",
            "floor_id": "",
            "floor_name": "Unassigned",
            "is_home": False,
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
            x.ble_tracker.last_packet_monotonic
            if x.ble_tracker is not None
            else 0.0,
            bool(x.get_current_area_and_distance()[1]["area_id"]),
        ),
    )
    area_name, r_attrs = best_c.get_current_area_and_distance()
    return str(area_name), {
        "person_entity": person_entity,
        "area_id": r_attrs["area_id"],
        "area_name": area_name,
        "floor_id": r_attrs["floor_id"],
        "floor_name": r_attrs["floor_name"],
        "is_home": r_attrs["is_home"],
        "distance_m": r_attrs["distance_m"],
        "closest_proxy": r_attrs["closest_proxy"],
        "match_method": r_attrs["match_method"],
        "source_device": best_c.device_slug,
    }
