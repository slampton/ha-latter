"""Weighted Area BLE + physical binary_sensor fusion engine."""

from __future__ import annotations

from typing import Any, Final

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from ..const import CONF_AREA_FUSION_CONFIG, DATA_GLOBAL_CONFIG, DOMAIN

FUSION_DEVICE_CLASSES: Final[frozenset[str]] = frozenset(
    {"occupancy", "presence", "motion", "moving", "door", "opening"}
)

_FUSION_INDEX_KEY: Final = "_area_fusion_index"
_UNAVAIL_STATES: Final[frozenset[str]] = frozenset({"unavailable", "unknown"})
_VALID_FUSION_MODES: Final[frozenset[str]] = frozenset(
    {"weighted", "any_or", "ble_only", "ble_and_sensor"}
)
_MIN_THRESHOLD_PCT: Final = 20
_MAX_THRESHOLD_PCT: Final = 95
_DEFAULT_THRESHOLD_PCT: Final = 50
_RSSI_STRONG_DBM: Final = -68
_RSSI_MEDIUM_DBM: Final = -80
_RSSI_WEAK_OCC_PENALTY_DBM: Final = -78
_BLE_ONLY_MIN_CONFIDENCE: Final = 85
_ANY_OR_LOW_CONFIDENCE: Final = 60
_ANY_OR_BOOSTED_CONFIDENCE: Final = 75
_PERCENT_SCALE: Final = 100


def invalidate_area_fusion_index(hass: HomeAssistant) -> None:
    """Invalidate the cached `area_id -> binary_sensor entity_id` index on registry updates."""
    domain_data = hass.data.get(DOMAIN)
    if isinstance(domain_data, dict):
        domain_data.pop(_FUSION_INDEX_KEY, None)


def _is_latter_own_area_sensor(
    entry: er.RegistryEntry | None,
    entity_id: str = "",
    state_obj: State | None = None,
) -> bool:
    """Return True when `entry`/`entity_id` belongs to Latter itself (never feed back into Area fusion)."""
    if entry is not None:
        return entry.platform == DOMAIN or bool(
            (entry.unique_id or "").startswith("latter_area_")
        )
    if state_obj is not None and "fusion_mode" in state_obj.attributes:
        return True
    return entity_id.endswith("_ble_occupancy")


def _is_eligible_area_binary_sensor(
    entry: er.RegistryEntry, seen_set: set[str]
) -> bool:
    return (
        not entry.disabled_by
        and entry.domain == "binary_sensor"
        and entry.platform != DOMAIN
        and not (entry.unique_id or "").startswith("latter_area_")
        and entry.entity_id not in seen_set
    )


def _area_candidate_binary_sensors(hass: HomeAssistant, area_id: str) -> list[str]:
    """Return cached physical `binary_sensor` `entity_ids` assigned to `area_id`."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    domain_data = hass.data.setdefault(DOMAIN, {})
    idx: dict[str, list[str]] = domain_data.setdefault(_FUSION_INDEX_KEY, {})

    if area_id not in idx:
        seen_area_eids: list[str] = []
        seen_set: set[str] = set()
        for entry in er.async_entries_for_area(ent_reg, area_id):
            if _is_eligible_area_binary_sensor(entry, seen_set):
                seen_set.add(entry.entity_id)
                seen_area_eids.append(entry.entity_id)

        for dev in dr.async_entries_for_area(dev_reg, area_id):
            for entry in er.async_entries_for_device(ent_reg, dev.id):
                if not entry.area_id and _is_eligible_area_binary_sensor(entry, seen_set):
                    seen_set.add(entry.entity_id)
                    seen_area_eids.append(entry.entity_id)
        idx[area_id] = seen_area_eids

    return idx[area_id]


def _resolve_sensor_device_class(
    entry: er.RegistryEntry | None, st: State | None
) -> str:
    return str(
        (st.attributes.get("device_class") if st else "")
        or (entry.device_class if entry else "")
        or (entry.original_device_class if entry else "")
        or ""
    ).lower()


def get_tracked_fusion_entity_ids(hass: HomeAssistant) -> set[str]:
    """Return the exact set of physical `binary_sensor` `entity_ids` used across all Area fusion configs."""
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    tracked: set[str] = set()

    domain_data = hass.data.get(DOMAIN, {})
    global_cfg = (
        domain_data.get(DATA_GLOBAL_CONFIG, {}) if isinstance(domain_data, dict) else {}
    )
    fusion_map = (
        global_cfg.get(CONF_AREA_FUSION_CONFIG, {})
        if isinstance(global_cfg, dict)
        else {}
    )

    if isinstance(fusion_map, dict):
        for cfg in fusion_map.values():
            if not isinstance(cfg, dict) or not isinstance(cfg.get("sensors"), list):
                continue
            for raw_s in cfg["sensors"]:
                eid = str(raw_s or "").strip()
                if not eid.startswith("binary_sensor."):
                    continue
                entry = ent_reg.async_get(eid)
                st = hass.states.get(eid)
                if not _is_latter_own_area_sensor(entry, eid, st):
                    tracked.add(eid)

    for area in area_reg.async_list_areas():
        for eid in _area_candidate_binary_sensors(hass, area.id):
            entry = ent_reg.async_get(eid)
            st = hass.states.get(eid)
            if _is_latter_own_area_sensor(entry, eid, st):
                continue
            if _resolve_sensor_device_class(entry, st) in FUSION_DEVICE_CLASSES:
                tracked.add(eid)

    return tracked


def _classify_active_fusion_sensor(
    eid: str,
    dclass: str,
    state_str: str,
    explicit_set: set[str],
    buckets: tuple[list[str], list[str], list[str], list[str]],
) -> None:
    occ_on, occ_off, motion_on, door_closed = buckets
    if dclass in ("occupancy", "presence") or (
        eid in explicit_set and dclass not in ("motion", "moving", "door", "opening")
    ):
        if state_str == "on":
            occ_on.append(eid)
        elif state_str == "off":
            occ_off.append(eid)
    elif dclass in ("motion", "moving"):
        if state_str == "on":
            motion_on.append(eid)
    elif dclass in ("door", "opening") and state_str == "off":
        door_closed.append(eid)


def discover_area_fusion_sensors(
    hass: HomeAssistant,
    area_id: str,
    configured_sensors: list[str] | None = None,
) -> tuple[list[str], list[str], list[str], list[str], list[dict[str, str]]]:
    """Return `(occ_on, occ_off, motion_on, door_closed, available_sensors)` for a Home Assistant Area."""
    ent_reg = er.async_get(hass)
    explicit_list = [
        str(s).strip()
        for s in (configured_sensors or [])
        if str(s or "").strip().startswith("binary_sensor.")
    ]
    explicit_set = set(explicit_list)

    candidate_eids = list(_area_candidate_binary_sensors(hass, area_id))
    for eid in explicit_list:
        if eid not in candidate_eids:
            candidate_eids.append(eid)

    occ_on: list[str] = []
    occ_off: list[str] = []
    motion_on: list[str] = []
    door_closed: list[str] = []
    available: list[dict[str, str]] = []
    buckets = (occ_on, occ_off, motion_on, door_closed)

    for eid in candidate_eids:
        entry = ent_reg.async_get(eid)
        st = hass.states.get(eid)
        if _is_latter_own_area_sensor(entry, eid, st):
            continue
        if entry is not None and (entry.disabled_by or entry.domain != "binary_sensor"):
            continue
        dclass = _resolve_sensor_device_class(entry, st)
        if dclass not in FUSION_DEVICE_CLASSES and eid not in explicit_set:
            continue

        state_str = str(st.state if st else "unknown").lower()
        friendly = (
            str(st.attributes.get("friendly_name") if st else "")
            or (entry.name if entry else "")
            or (entry.original_name if entry else "")
            or eid
        ).strip()
        available.append(
            {
                "entity_id": eid,
                "name": friendly,
                "device_class": dclass or "occupancy",
                "state": state_str,
            }
        )
        if explicit_set and eid not in explicit_set:
            continue
        _classify_active_fusion_sensor(eid, dclass, state_str, explicit_set, buckets)

    return occ_on, occ_off, motion_on, door_closed, available


def area_fusion_sensor_choices(
    hass: HomeAssistant, area_id: str
) -> list[dict[str, str]]:
    """Return the occupancy, motion, and door sensors an Area has."""
    return discover_area_fusion_sensors(hass, area_id)[4]


def area_fusion_settings(hass: HomeAssistant, area_id: str) -> dict[str, Any]:
    """Return one Area's stored fusion settings (`area_fusion_config[<area_id>]`), or `{}`."""
    domain_data = hass.data.get(DOMAIN, {})
    global_cfg = (
        domain_data.get(DATA_GLOBAL_CONFIG, {}) if isinstance(domain_data, dict) else {}
    )
    fusion_map = (
        global_cfg.get(CONF_AREA_FUSION_CONFIG, {})
        if isinstance(global_cfg, dict)
        else {}
    )
    area_cfg = fusion_map.get(area_id, {}) if isinstance(fusion_map, dict) else {}
    return area_cfg if isinstance(area_cfg, dict) else {}


def _collect_unavailable_fusion_sensors(
    hass: HomeAssistant,
    explicit_eids: list[str],
    available_sensors: list[dict[str, str]],
) -> list[str]:
    ent_reg = er.async_get(hass)
    unavailable: list[str] = []
    if explicit_eids:
        for eid in explicit_eids:
            entry = ent_reg.async_get(eid)
            st = hass.states.get(eid)
            if _is_latter_own_area_sensor(entry, eid, st):
                continue
            if (
                st is None
                or (entry is not None and bool(entry.disabled_by))
                or str(st.state).lower() in _UNAVAIL_STATES
            ) and eid not in unavailable:
                unavailable.append(eid)
        return unavailable

    for item in available_sensors:
        eid = str(item.get("entity_id") or "")
        if (
            eid
            and str(item.get("state") or "").lower() in _UNAVAIL_STATES
            and eid not in unavailable
        ):
            unavailable.append(eid)
    return unavailable


def _compute_fusion_confidence_pct(
    *,
    ble_present: bool,
    best_rssi: int | None,
    buckets: tuple[list[str], list[str], list[str], list[str]],
) -> int:
    occ_on, occ_off, motion_on, door_closed = buckets
    sensor_present = bool(occ_on or motion_on)
    score = 0.0
    if ble_present:
        if best_rssi is not None and best_rssi >= _RSSI_STRONG_DBM:
            score += 0.85
        elif best_rssi is not None and best_rssi >= _RSSI_MEDIUM_DBM:
            score += 0.70
        else:
            score += 0.54

    if occ_on:
        score = max(score, 0.78) + (0.18 if ble_present else 0.08)
    elif (
        occ_off
        and not motion_on
        and ble_present
        and (best_rssi is not None and best_rssi < _RSSI_WEAK_OCC_PENALTY_DBM)
    ):
        score = max(0.0, score - 0.18)

    if motion_on:
        score = max(score, 0.68) + (0.15 if (ble_present or occ_on) else 0.05)

    if door_closed and (ble_present or sensor_present):
        score += 0.08

    return round(max(0.0, min(1.0, score)) * _PERCENT_SCALE)


def evaluate_area_sensor_fusion(
    hass: HomeAssistant,
    area_id: str,
    *,
    ble_present: bool,
    best_rssi: int | None,
) -> dict[str, Any]:
    """Evaluate honest weighted BLE + physical sensor fusion for a Home Assistant Area."""
    area_cfg = area_fusion_settings(hass, area_id)
    raw_mode = str(area_cfg.get("mode") or "weighted").strip().lower()
    fusion_mode = raw_mode if raw_mode in _VALID_FUSION_MODES else "weighted"
    threshold_pct = max(
        _MIN_THRESHOLD_PCT,
        min(_MAX_THRESHOLD_PCT, int(area_cfg.get("threshold_pct") or _DEFAULT_THRESHOLD_PCT)),
    )
    configured_sensors: list[str] | None = (
        area_cfg["sensors"] if isinstance(area_cfg.get("sensors"), list) else None
    )

    occ_on, occ_off, motion_on, door_closed, available_sensors = (
        discover_area_fusion_sensors(hass, area_id, configured_sensors)
    )
    active_sensors = occ_on + motion_on
    sensor_present = len(active_sensors) > 0

    explicit_eids = [
        str(s).strip()
        for s in (configured_sensors or [])
        if str(s or "").strip().startswith("binary_sensor.")
    ]
    unavailable_sensors = _collect_unavailable_fusion_sensors(
        hass, explicit_eids, available_sensors
    )
    confidence_pct = _compute_fusion_confidence_pct(
        ble_present=ble_present,
        best_rssi=best_rssi,
        buckets=(occ_on, occ_off, motion_on, door_closed),
    )

    if fusion_mode == "ble_only":
        is_occupied = ble_present
        confidence_pct = (
            max(confidence_pct, _BLE_ONLY_MIN_CONFIDENCE) if ble_present else 0
        )
    elif fusion_mode == "any_or":
        is_occupied = ble_present or sensor_present
        if is_occupied and confidence_pct < _ANY_OR_LOW_CONFIDENCE:
            confidence_pct = _ANY_OR_BOOSTED_CONFIDENCE
    elif fusion_mode == "ble_and_sensor":
        if explicit_eids and unavailable_sensors:
            is_occupied = False
            confidence_pct = 0
        elif ble_present and sensor_present:
            is_occupied = True
        else:
            is_occupied = False
            confidence_pct = 0
    else:
        is_occupied = confidence_pct >= threshold_pct

    return {
        "is_occupied": is_occupied,
        "ble_occupied": ble_present,
        "sensor_occupied": sensor_present,
        "fusion_mode": fusion_mode,
        "confidence_pct": confidence_pct,
        "active_sensors": active_sensors,
        "available_sensors": available_sensors,
        "unavailable_sensors": unavailable_sensors,
    }
