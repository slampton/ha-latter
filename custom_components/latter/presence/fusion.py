"""Weighted Area BLE + physical occupancy/motion/door sensor fusion for Latter."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from ..const import DOMAIN

FUSION_DEVICE_CLASSES: frozenset[str] = frozenset(
    {"occupancy", "presence", "motion", "moving", "door", "opening"}
)


def invalidate_area_fusion_index(hass: HomeAssistant) -> None:
    """Invalidate the cached area_id -> binary_sensor entity_id index on registry updates."""
    domain_data = hass.data.get(DOMAIN)
    if isinstance(domain_data, dict):
        domain_data.pop("_area_fusion_index", None)


def _area_candidate_binary_sensors(hass: HomeAssistant, area_id: str) -> list[str]:
    """Return cached physical binary_sensor entity_ids assigned to `area_id`."""
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    domain_data = hass.data.setdefault(DOMAIN, {})
    idx: dict[str, list[str]] = domain_data.setdefault("_area_fusion_index", {})

    if area_id not in idx:
        seen_area_eids: list[str] = []
        seen_set: set[str] = set()
        for entry in er.async_entries_for_area(ent_reg, area_id):
            if (
                not entry.disabled_by
                and entry.domain == "binary_sensor"
                and "ble_occupancy" not in entry.entity_id
                and not (
                    entry.unique_id
                    and str(entry.unique_id).startswith("latter_area_ble_occupancy_")
                )
                and entry.entity_id not in seen_set
            ):
                seen_set.add(entry.entity_id)
                seen_area_eids.append(entry.entity_id)

        for dev in dr.async_entries_for_area(dev_reg, area_id):
            for entry in er.async_entries_for_device(ent_reg, dev.id):
                if (
                    not entry.area_id
                    and not entry.disabled_by
                    and entry.domain == "binary_sensor"
                    and "ble_occupancy" not in entry.entity_id
                    and not (
                        entry.unique_id
                        and str(entry.unique_id).startswith(
                            "latter_area_ble_occupancy_"
                        )
                    )
                    and entry.entity_id not in seen_set
                ):
                    seen_set.add(entry.entity_id)
                    seen_area_eids.append(entry.entity_id)
        idx[area_id] = seen_area_eids

    return idx[area_id]


def get_tracked_fusion_entity_ids(hass: HomeAssistant) -> set[str]:
    """Return the exact set of physical binary_sensor entity_ids used across all Area fusion configs."""
    area_reg = ar.async_get(hass)
    ent_reg = er.async_get(hass)
    tracked: set[str] = set()

    domain_data = hass.data.get(DOMAIN, {})
    global_cfg = domain_data.get("global_config", {}) if isinstance(domain_data, dict) else {}
    fusion_map = global_cfg.get("area_fusion_config", {}) if isinstance(global_cfg, dict) else {}

    if isinstance(fusion_map, dict):
        for cfg in fusion_map.values():
            if isinstance(cfg, dict) and isinstance(cfg.get("sensors"), list):
                for s in cfg["sensors"]:
                    eid = str(s or "").strip()
                    if eid.startswith("binary_sensor.") and "ble_occupancy" not in eid:
                        tracked.add(eid)

    for area in area_reg.async_list_areas():
        for eid in _area_candidate_binary_sensors(hass, area.id):
            entry = ent_reg.async_get(eid)
            st = hass.states.get(eid)
            dclass = str(
                (st.attributes.get("device_class") if st else "")
                or (entry.device_class if entry else "")
                or (entry.original_device_class if entry else "")
                or ""
            ).lower()
            if dclass in FUSION_DEVICE_CLASSES:
                tracked.add(eid)

    return tracked


def discover_area_fusion_sensors(
    hass: HomeAssistant,
    area_id: str,
    configured_sensors: list[str] | None = None,
) -> tuple[list[str], list[str], list[str], list[str], list[dict[str, str]]]:
    """Return (occ_on, occ_off, motion_on, door_closed, available_sensors) for a Home Assistant Area."""
    ent_reg = er.async_get(hass)
    explicit_set = {
        str(s).strip()
        for s in (configured_sensors or [])
        if str(s or "").strip().startswith("binary_sensor.")
    }

    candidate_eids = list(_area_candidate_binary_sensors(hass, area_id))
    for eid in explicit_set:
        if eid not in candidate_eids:
            candidate_eids.append(eid)

    occ_on: list[str] = []
    occ_off: list[str] = []
    motion_on: list[str] = []
    door_closed: list[str] = []
    available: list[dict[str, str]] = []

    for eid in candidate_eids:
        if "ble_occupancy" in eid:
            continue
        entry = ent_reg.async_get(eid)
        if entry is not None and (entry.disabled_by or entry.domain != "binary_sensor"):
            continue
        st = hass.states.get(eid)
        dclass = str(
            (st.attributes.get("device_class") if st else "")
            or (entry.device_class if entry else "")
            or (entry.original_device_class if entry else "")
            or ""
        ).lower()
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

        if dclass in ("occupancy", "presence") or (
            eid in explicit_set
            and dclass not in ("motion", "moving", "door", "opening")
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

    return occ_on, occ_off, motion_on, door_closed, available


def area_fusion_sensor_choices(hass: HomeAssistant, area_id: str) -> list[dict[str, str]]:
    """Return the occupancy, motion and door sensors an Area has."""
    return discover_area_fusion_sensors(hass, area_id)[4]


def area_fusion_settings(hass: HomeAssistant, area_id: str) -> dict[str, Any]:
    """Return one Area's stored fusion settings (`area_fusion_config[<area_id>]`), or {}."""
    domain_data = hass.data.get(DOMAIN, {})
    global_cfg = domain_data.get("global_config", {}) if isinstance(domain_data, dict) else {}
    fusion_map = global_cfg.get("area_fusion_config", {}) if isinstance(global_cfg, dict) else {}
    area_cfg = fusion_map.get(area_id, {}) if isinstance(fusion_map, dict) else {}
    return area_cfg if isinstance(area_cfg, dict) else {}


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
    fusion_mode = (
        raw_mode
        if raw_mode in ("weighted", "any_or", "ble_only", "ble_and_sensor")
        else "weighted"
    )
    threshold_pct = max(20, min(95, int(area_cfg.get("threshold_pct") or 50)))
    configured_sensors = (
        area_cfg.get("sensors") if isinstance(area_cfg.get("sensors"), list) else None
    )

    occ_on, occ_off, motion_on, door_closed, available_sensors = (
        discover_area_fusion_sensors(hass, area_id, configured_sensors)
    )
    active_sensors = occ_on + motion_on
    sensor_present = len(active_sensors) > 0

    score = 0.0
    if ble_present:
        if best_rssi is not None and best_rssi >= -68:
            score += 0.85
        elif best_rssi is not None and best_rssi >= -80:
            score += 0.70
        else:
            score += 0.54

    if occ_on:
        score = max(score, 0.78) + (0.18 if ble_present else 0.08)
    elif (
        occ_off
        and not motion_on
        and ble_present
        and (best_rssi is not None and best_rssi < -78)
    ):
        score = max(0.0, score - 0.18)

    if motion_on:
        score = max(score, 0.68) + (0.15 if (ble_present or occ_on) else 0.05)

    if door_closed and (ble_present or sensor_present):
        score += 0.08

    confidence_pct = round(max(0.0, min(1.0, score)) * 100)

    if fusion_mode == "ble_only":
        is_occupied = ble_present
        confidence_pct = max(confidence_pct, 85) if ble_present else 0
    elif fusion_mode == "any_or":
        is_occupied = ble_present or sensor_present
        if is_occupied and confidence_pct < 60:
            confidence_pct = 75
    elif fusion_mode == "ble_and_sensor":
        has_local_sensors = bool(occ_on or occ_off or motion_on)
        is_occupied = ble_present and (sensor_present if has_local_sensors else True)
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
    }
