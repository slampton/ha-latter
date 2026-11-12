"""Event-driven BLE Proxy Area Presence Fabric, scoring math, dwell gate, and sensor fusion for Latter."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
import time
from typing import Any, Literal

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)

from .const import DEFAULT_BLE_BEACON_UUID, DOMAIN, normalize_device_slug
from .identity import get_bound_esphome_device, read_device_hardware_manifest

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BLE Area Scoring Math
# ---------------------------------------------------------------------------

EMA_ALPHA = 0.50
HYSTERESIS_DB = 5.0
RSSI_HYSTERESIS_DEADBAND_DBM = 3.0
FAST_OVERRIDE_DB = 8.0
CROSS_FLOOR_ATTENUATION_DB = 6.0
STALE_PROXY_SECONDS = 12.0
SILENCE_GRACE_SECONDS = 2.0
SILENCE_DECAY_DB_PER_S = 1.5
MIN_HOLD_SECONDS = 4.0
MIN_WINNING_RSSI_DBM = -88.0
NO_SIGNAL_RSSI_DBM = -100.0
TX_POWER_1M_DBM = -59.0
PATH_LOSS_EXPONENT = 2.2


def within_rssi_deadband(
    prev_rssi: float | int | None, new_rssi: float | int
) -> bool:
    """Return True when `new_rssi` stays within the 3.0 dBm hysteresis deadband of `prev_rssi`."""
    if prev_rssi is None:
        return False
    return abs(float(new_rssi) - float(prev_rssi)) < RSSI_HYSTERESIS_DEADBAND_DBM


def smooth_rssi(
    prev: tuple[float, float] | None, raw_rssi: float, obs_time: float
) -> float:
    """Return the EMA of `raw_rssi` over `prev` = (ema, last_seen); restart when stale or missing."""
    if prev is None or (obs_time - prev[1]) > STALE_PROXY_SECONDS:
        return float(raw_rssi)
    return (EMA_ALPHA * float(raw_rssi)) + ((1.0 - EMA_ALPHA) * prev[0])


def score_areas(
    area_rssi: Mapping[str, tuple[float, float]],
    now: float,
    is_cross_floor: Callable[[str], bool],
) -> dict[str, float]:
    """Score fresh Areas: effective RSSI minus silence decay, minus the 6.0 dB cross-floor penalty."""
    scores: dict[str, float] = {}
    for area_id, (ema, last_seen) in area_rssi.items():
        age_s = max(0.0, now - last_seen)
        if age_s > STALE_PROXY_SECONDS:
            continue
        score = ema - SILENCE_DECAY_DB_PER_S * max(0.0, age_s - SILENCE_GRACE_SECONDS)
        if is_cross_floor(area_id):
            score -= CROSS_FLOOR_ATTENUATION_DB
        scores[area_id] = score
    return scores


@dataclass(frozen=True)
class AreaDecision:
    """Outcome of one Area evaluation."""

    best_area_id: str
    best_score: float
    current_score: float
    switch: bool


def decide_area(
    scores: Mapping[str, float],
    current_area_id: str | None,
    now: float,
    last_switch: float,
) -> AreaDecision | None:
    """Pick the best-scoring Area and decide whether the Device moves there."""
    if not scores:
        return None
    best_area_id, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score < MIN_WINNING_RSSI_DBM:
        return None
    if current_area_id is None:
        return AreaDecision(best_area_id, best_score, NO_SIGNAL_RSSI_DBM, True)
    if best_area_id == current_area_id:
        return AreaDecision(best_area_id, best_score, best_score, False)
    current_score = scores.get(current_area_id, NO_SIGNAL_RSSI_DBM)
    delta_db = best_score - current_score
    switch = delta_db >= FAST_OVERRIDE_DB or (
        (now - last_switch) >= MIN_HOLD_SECONDS and delta_db >= HYSTERESIS_DB
    )
    return AreaDecision(best_area_id, best_score, current_score, switch)


def rssi_to_distance_m(rssi_dbm: float) -> float:
    """Estimate distance in metres with a log-distance path-loss model (TX power -59 dBm at 1 m, n = 2.2)."""
    return round(
        max(
            0.2,
            min(
                50.0,
                10.0 ** ((TX_POWER_1M_DBM - rssi_dbm) / (10.0 * PATH_LOSS_EXPONENT)),
            ),
        ),
        1,
    )


# ---------------------------------------------------------------------------
# Voice Follows Me Dwell Gate & Beacon Policy
# ---------------------------------------------------------------------------

NON_AREA_STATES: frozenset[str] = frozenset(
    {"", "unknown", "unavailable", "none", "away", "not_home"}
)
_CLOCK_TOLERANCE_S = 0.25

Trigger = Literal["hello", "options"]
BeaconAction = Literal["turn_on", "turn_off"]


def is_area_id(value: str | None) -> bool:
    """Return True if `value` names an Area rather than an away/unknown placeholder."""
    return bool(value) and str(value).strip().lower() not in NON_AREA_STATES


class FollowAction(Enum):
    """What the controller should do with an Area update request."""

    IGNORE = "ignore"
    COMMIT = "commit"
    DWELL = "dwell"
    PENDING = "pending"


class AreaFollowDwell:
    """Dwell gate: BLE-driven moves must stay stable for `dwell_s`; explicit picks apply at once."""

    def __init__(self) -> None:
        """Start with no pending move."""
        self.pending_area_id: str | None = None
        self.due_at: float | None = None

    def cancel(self) -> None:
        """Drop any pending move."""
        self.pending_area_id = None
        self.due_at = None

    def request(
        self, target_area_id: str | None, *, ble_driven: bool, dwell_s: float, now: float
    ) -> FollowAction:
        """Register an Area update and return what to do now."""
        if not is_area_id(target_area_id):
            self.cancel()
            return FollowAction.IGNORE
        assert target_area_id is not None
        if ble_driven and dwell_s > 0:
            if self.pending_area_id == target_area_id and self.due_at is not None:
                return FollowAction.PENDING
            self.pending_area_id = target_area_id
            self.due_at = now + float(dwell_s)
            return FollowAction.DWELL
        self.cancel()
        return FollowAction.COMMIT

    def take_due(self, target_area_id: str, now: float) -> bool:
        """Return True, and clear the pending move, if `target_area_id` is still pending and its dwell has elapsed."""
        if (
            self.pending_area_id != target_area_id
            or self.due_at is None
            or now + _CLOCK_TOLERANCE_S < self.due_at
        ):
            return False
        self.cancel()
        return True


def decide_beacon_action(
    tracking_enabled: bool, switch_state: str | None, trigger: Trigger
) -> BeaconAction | None:
    """Return the BLE presence beacon switch action to take (`turn_on` / `turn_off`), or None."""
    if switch_state not in ("on", "off"):
        return None
    if tracking_enabled:
        return "turn_on" if switch_state == "off" else None
    if trigger == "options" and switch_state == "on":
        return "turn_off"
    return None


# ---------------------------------------------------------------------------
# Weighted Area BLE + Physical Sensor Fusion
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Shared BLE Scanner Fabric & Native BLE Tracker
# ---------------------------------------------------------------------------

APPLE_COMPANY_ID = 0x004C
IBEACON_PREFIX = b"\x02\x15"
_UNMAPPED = "__unmapped__"
SURVEY_RETENTION_SECONDS = 180.0
WAKE_GAP_SECONDS = 8.0
AWAY_CHECK_INTERVAL_SECONDS = 15.0
AWAY_TIMEOUT_SECONDS = 180.0


def _iter_devices(dev_reg: dr.DeviceRegistry) -> list[dr.DeviceEntry]:
    """Yield DeviceEntry objects across Home Assistant versions and test doubles."""
    out: list[dr.DeviceEntry] = []
    for item in dev_reg.devices:
        if isinstance(item, str):
            dev = dev_reg.async_get(item)
            if dev is not None:
                out.append(dev)
        else:
            out.append(item)
    return out


def _iter_entities(ent_reg: er.EntityRegistry) -> list[er.RegistryEntry]:
    """Yield RegistryEntry objects across Home Assistant versions and test doubles."""
    out: list[er.RegistryEntry] = []
    for item in ent_reg.entities:
        if isinstance(item, str):
            ent = ent_reg.async_get(item)
            if ent is not None:
                out.append(ent)
        else:
            out.append(item)
    return out


def _normalize_uuid_hex(uuid_str: str) -> str:
    """Normalize a UUID string to 32 lowercase hex chars without dashes."""
    return uuid_str.strip().lower().replace("-", "")


def _mac_to_int(mac_str: str) -> int | None:
    """Convert a 12-hex-char MAC address into an integer for ESP32 Wi-Fi/BLE +/-2 comparison."""
    clean = mac_str.strip().lower().replace(":", "").replace("-", "").replace("_", "")
    if len(clean) != 12:
        return None
    try:
        return int(clean, 16)
    except ValueError:
        return None


def _int_to_mac(mac_int: int) -> str:
    """Format a 48-bit integer as an uppercase colon-delimited MAC string."""
    hex_str = f"{mac_int:012X}"
    return ":".join(hex_str[i : i + 2] for i in range(0, 12, 2))


def _discover_target_device_macs(
    hass: HomeAssistant, esphome_device_id: str | None
) -> set[int]:
    """Find known Wi-Fi/BLE MAC address integers for the bound ESPHome device."""
    dev = get_bound_esphome_device(hass, esphome_device_id)
    if dev is None:
        return set()

    mac_ints: set[int] = set()
    for _conn_type, conn_val in dev.connections:
        m_int = _mac_to_int(str(conn_val))
        if m_int is not None:
            for offset in (-2, -1, 0, 1, 2):
                mac_ints.add(m_int + offset)
    for _domain, ident_val in dev.identifiers:
        m_int = _mac_to_int(str(ident_val))
        if m_int is not None:
            for offset in (-2, -1, 0, 1, 2):
                mac_ints.add(m_int + offset)
    return mac_ints


def _resolve_device_area_or_entity_area(
    dev: dr.DeviceEntry,
    ent_reg: er.EntityRegistry,
    area_reg: ar.AreaRegistry,
) -> str | None:
    """Return a device's area_id, or fallback to any entity's area_id or area name in device label."""
    if dev.area_id:
        return dev.area_id

    for entry in er.async_entries_for_device(ent_reg, dev.id):
        if entry.area_id:
            return entry.area_id

    for raw_label in (dev.name_by_user, dev.name):
        if not raw_label:
            continue
        dev_label = str(raw_label).lower().replace("-", " ").replace("_", " ")
        areas_sorted = sorted(
            area_reg.async_list_areas(),
            key=lambda a: len(a.name),
            reverse=True,
        )
        for area in areas_sorted:
            a_norm = area.name.lower().replace("-", " ").replace("_", " ").strip()
            if a_norm and a_norm in dev_label:
                return area.id

    return None


def _resolve_scanner_area_id_uncached(
    hass: HomeAssistant, scanner_source: str
) -> str | None:
    """Resolve an ESPHome BLE Proxy source (MAC or name) to its Home Assistant area_id."""
    if not scanner_source:
        return None

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    area_reg = ar.async_get(hass)
    src_low = scanner_source.strip().lower()
    src_int = _mac_to_int(src_low)

    scanner_name = ""
    try:
        from homeassistant.components import bluetooth

        scanner = bluetooth.async_scanner_by_source(hass, scanner_source)
        if scanner is not None:
            scanner_name = str(getattr(scanner, "name", "") or "").strip().lower()
            details = getattr(scanner, "details", None)
            if isinstance(details, dict) and details.get("source"):
                alt_src = str(details["source"]).lower()
                if alt_src != src_low and src_int is None:
                    src_int = _mac_to_int(alt_src)
    except Exception:  # noqa: BLE001
        pass

    all_devices = _iter_devices(dev_reg)

    for device in all_devices:
        for _conn_type, conn_val in device.connections:
            c_low = str(conn_val).lower()
            c_int = _mac_to_int(c_low)
            if c_low == src_low or (
                src_int is not None and c_int is not None and src_int == c_int
            ):
                resolved = _resolve_device_area_or_entity_area(device, ent_reg, area_reg)
                if resolved:
                    return resolved
        for _domain, ident_val in device.identifiers:
            i_low = str(ident_val).lower()
            i_int = _mac_to_int(i_low)
            if i_low == src_low or (
                src_int is not None and i_int is not None and src_int == i_int
            ):
                resolved = _resolve_device_area_or_entity_area(device, ent_reg, area_reg)
                if resolved:
                    return resolved

    if src_int is not None:
        for device in all_devices:
            for _conn_type, conn_val in device.connections:
                c_int = _mac_to_int(str(conn_val))
                if c_int is not None and 0 < abs(src_int - c_int) <= 2:
                    resolved = _resolve_device_area_or_entity_area(
                        device, ent_reg, area_reg
                    )
                    if resolved:
                        return resolved
            for _domain, ident_val in device.identifiers:
                i_int = _mac_to_int(str(ident_val))
                if i_int is not None and 0 < abs(src_int - i_int) <= 2:
                    resolved = _resolve_device_area_or_entity_area(
                        device, ent_reg, area_reg
                    )
                    if resolved:
                        return resolved

    for device in all_devices:
        for candidate_name in (device.name_by_user, device.name):
            if not candidate_name:
                continue
            d_low = str(candidate_name).strip().lower()
            d_slug = d_low.replace(" ", "-").replace("_", "-")
            for target_n in (src_low, scanner_name):
                if not target_n:
                    continue
                t_slug = target_n.replace(" ", "-").replace("_", "-")
                if d_low == target_n or d_slug == t_slug:
                    resolved = _resolve_device_area_or_entity_area(
                        device, ent_reg, area_reg
                    )
                    if resolved:
                        return resolved

    areas_sorted = sorted(
        area_reg.async_list_areas(),
        key=lambda a: len(a.name),
        reverse=True,
    )
    for raw_text in (scanner_name, src_low):
        if not raw_text:
            continue
        scan_norm = raw_text.replace("-", " ").replace("_", " ")
        for area in areas_sorted:
            a_norm = area.name.lower().replace("-", " ").replace("_", " ").strip()
            if a_norm and a_norm in scan_norm:
                return area.id

    return None


def _resolve_scanner_area_id(
    hass: HomeAssistant, scanner_source: str
) -> str | None:
    """Resolve an ESPHome BLE Proxy source to its Home Assistant area_id (cached when active)."""
    if not scanner_source:
        return None
    domain_data = hass.data.get(DOMAIN)
    fabric: LatterBleFabric | None = (
        domain_data.get("ble_fabric") if isinstance(domain_data, dict) else None
    )
    if fabric is not None and fabric._unsub_ble is not None:
        cached = fabric._scanner_area_cache.get(scanner_source)
        if cached is not None:
            return None if cached == _UNMAPPED else cached
        resolved = _resolve_scanner_area_id_uncached(hass, scanner_source)
        fabric._scanner_area_cache[scanner_source] = resolved if resolved else _UNMAPPED
        return resolved
    return _resolve_scanner_area_id_uncached(hass, scanner_source)


def get_ble_proxy_area_ids(hass: HomeAssistant) -> set[str]:
    """Return the set of Home Assistant area_ids that actually have a Bluetooth proxy/scanner."""
    proxy_areas: set[str] = set()
    try:
        from homeassistant.components import bluetooth

        for scanner in bluetooth.async_current_scanners(hass):
            source = str(getattr(scanner, "source", "") or "")
            if source:
                a_id = _resolve_scanner_area_id(hass, source)
                if a_id:
                    proxy_areas.add(a_id)
    except Exception:  # noqa: BLE001
        pass
    return proxy_areas


def count_area_ble_proxies(hass: HomeAssistant) -> int:
    """Return how many Bluetooth proxies/scanners resolve to a Home Assistant Area."""
    count = 0
    try:
        from homeassistant.components import bluetooth

        for scanner in bluetooth.async_current_scanners(hass):
            source = str(getattr(scanner, "source", "") or "")
            if source and _resolve_scanner_area_id(hass, source):
                count += 1
    except Exception:  # noqa: BLE001
        pass
    return count


def get_all_scanners_diagnostic_map(hass: HomeAssistant) -> dict[str, str]:
    """Return a diagnostic dictionary of all registered HA Bluetooth scanners -> resolved Area name."""
    out: dict[str, str] = {}
    area_reg = ar.async_get(hass)
    try:
        from homeassistant.components import bluetooth

        for scanner in bluetooth.async_current_scanners(hass):
            source = str(getattr(scanner, "source", "") or "")
            name = str(getattr(scanner, "name", "") or source)
            a_id = _resolve_scanner_area_id(hass, source) if source else None
            area_obj = area_reg.async_get_area(a_id) if a_id else None
            area_label = f"{area_obj.name} ({a_id})" if area_obj else "UNMAPPED"
            out[f"{name} [{source}]"] = area_label
    except Exception:  # noqa: BLE001
        pass
    return out


class LatterNativeBleTracker:
    """Tracks a mobile BLE iBeacon or tag across BLE Proxies with 3.0 dBm hysteresis deadband."""

    def __init__(
        self,
        hass: HomeAssistant,
        beacon_uuid: str,
        device_slug: str,
        on_area_detected: Callable[[str, str], None],
        area_offsets: dict[str, float] | None = None,
        target_address: str = "",
        esphome_device_id: str | None = None,
        manifest_beacon: dict[str, Any] | None = None,
        should_hold_during_ble_sleep: Callable[[], bool] | None = None,
    ) -> None:
        """Initialize the native BLE proxy area tracker."""
        self.hass = hass
        self.beacon_uuid = str(beacon_uuid or "").strip()
        self._target_uuid_hex = _normalize_uuid_hex(beacon_uuid)
        self._target_address = str(target_address or "").strip()
        self.target_address = self._target_address
        self._raw_slug = device_slug
        self._esphome_device_id: str | None = esphome_device_id
        self._manifest_beacon: dict[str, Any] = (
            dict(manifest_beacon) if isinstance(manifest_beacon, dict) else {}
        )
        self._should_hold_during_ble_sleep = should_hold_during_ble_sleep
        self._on_area_detected = on_area_detected
        self._area_offsets: dict[str, float] = {
            str(k): float(v) for k, v in (area_offsets or {}).items()
        }

        self._area_rssi: dict[str, tuple[float, float]] = {}
        self._area_raw_rssi: dict[str, tuple[float, float, str]] = {}
        self._unmapped_rssi: dict[str, tuple[int, float]] = {}
        self._scanner_area_cache: dict[str, str | None] = {}
        self._last_adv_ts_by_scanner: dict[str, float] = {}
        self._target_mac_ints: set[int] = set()
        self._last_mac_discovery_mono: float = 0.0
        self._matched_ble_addresses: dict[str, float] = {}
        self.current_area_id: str | None = None
        self._awaiting_fresh_wake_lock: bool = False
        self.closest_scanner: str = ""
        self.packets_seen: int = 0
        self.last_packet_monotonic: float = 0.0
        self._started_monotonic: float = time.monotonic()
        self._last_switch_monotonic: float = 0.0
        self.is_away: bool = False
        self.winning_rssi: int | None = None
        self.winning_distance_m: float | None = None
        self.winning_distance_ft: float | None = None
        self._seed_explicit_target_address()

    @callback
    def _record_matched_ble_address(self, addr: str) -> None:
        """Record a matched BLE address with a monotonic timestamp, bounding cache to 64 entries."""
        norm = str(addr or "").strip().upper()
        if not norm:
            return
        is_new = norm not in self._matched_ble_addresses
        self._matched_ble_addresses[norm] = time.monotonic()
        evicted = False
        if len(self._matched_ble_addresses) > 64:
            oldest = min(
                self._matched_ble_addresses,
                key=lambda k: self._matched_ble_addresses[k],
            )
            self._matched_ble_addresses.pop(oldest, None)
            evicted = True
        if is_new or evicted:
            get_ble_fabric(self.hass).sync_tracker_addresses()

    @callback
    def _seed_explicit_target_address(self) -> None:
        """Seed MAC, iBeacon UUID, or dynamic private_ble_device address from _target_address."""
        t_addr = self._target_address
        if not t_addr:
            return
        m_int = _mac_to_int(t_addr)
        if m_int is not None:
            self._target_mac_ints.add(m_int)
            self._record_matched_ble_address(_int_to_mac(m_int))
            return
        if "." in t_addr:
            st = self.hass.states.get(t_addr)
            if st is not None:
                cur_mac = str(
                    st.attributes.get("current_address")
                    or st.attributes.get("mac")
                    or st.attributes.get("address")
                    or ""
                ).strip()
                if cur_mac:
                    self._record_matched_ble_address(cur_mac.upper())
                    c_int = _mac_to_int(cur_mac)
                    if c_int is not None:
                        self._target_mac_ints.add(c_int)
                u_attr = str(st.attributes.get("uuid") or "").strip()
                if len(_normalize_uuid_hex(u_attr)) == 32:
                    self._target_uuid_hex = _normalize_uuid_hex(u_attr)
            return
        norm_u = _normalize_uuid_hex(t_addr.split(":", 1)[0])
        if len(norm_u) == 32:
            self._target_uuid_hex = norm_u

    @callback
    def check_away_timeout(self, now_mono: float) -> None:
        """Transition tracker to Away if no BLE packet has been received within AWAY_TIMEOUT_SECONDS."""
        stale_addrs = [
            a
            for a, ts in self._matched_ble_addresses.items()
            if (now_mono - ts) > SURVEY_RETENTION_SECONDS
        ]
        for a in stale_addrs:
            self._matched_ble_addresses.pop(a, None)
        if stale_addrs:
            get_ble_fabric(self.hass).sync_tracker_addresses()
        self._seed_explicit_target_address()
        ref_mono = (
            self.last_packet_monotonic
            if self.last_packet_monotonic > 0.0
            else self._started_monotonic
        )
        if (
            not self.is_away
            and ref_mono > 0.0
            and (now_mono - ref_mono) >= AWAY_TIMEOUT_SECONDS
        ):
            if (
                self._should_hold_during_ble_sleep is not None
                and self._should_hold_during_ble_sleep()
            ):
                return
            self.is_away = True
            self.current_area_id = None
            self._awaiting_fresh_wake_lock = False
            self.winning_rssi = None
            self.winning_distance_m = None
            self.winning_distance_ft = None
            self._on_area_detected("away", "")
            get_ble_fabric(self.hass).notify_occupancy_listeners()

    @callback
    def update_manifest_beacon(self, beacon: dict[str, Any] | None) -> None:
        """Update cached hardware manifest beacon metadata (uuid, major, minor) from device_hello."""
        if isinstance(beacon, dict):
            self._manifest_beacon = dict(beacon)
            u_raw = str(beacon.get("uuid") or "").strip()
            norm_u = _normalize_uuid_hex(u_raw)
            default_u = _normalize_uuid_hex(DEFAULT_BLE_BEACON_UUID)
            if (
                len(norm_u) == 32
                and not self._target_address
                and (not self._target_uuid_hex or norm_u != default_u)
            ):
                self._target_uuid_hex = norm_u

    def _resolve_beacon_major_minor(self) -> tuple[int | None, int | None]:
        """Return expected iBeacon (major, minor) IDs from the device's hardware manifest."""
        beacon_cfg = self._manifest_beacon
        if not beacon_cfg:
            hw = read_device_hardware_manifest(self.hass, self._esphome_device_id)
            if isinstance(hw.get("beacon"), dict):
                beacon_cfg = hw["beacon"]
                self._manifest_beacon = dict(beacon_cfg)
        major_val: int | None = None
        minor_val: int | None = None
        if isinstance(beacon_cfg, dict):
            if beacon_cfg.get("major") is not None:
                try:
                    major_val = int(beacon_cfg["major"])
                except (ValueError, TypeError):
                    major_val = None
            if beacon_cfg.get("minor") is not None:
                try:
                    minor_val = int(beacon_cfg["minor"])
                except (ValueError, TypeError):
                    minor_val = None
        return major_val, minor_val

    @property
    def target_macs_formatted(self) -> list[str]:
        """Return the list of candidate Wi-Fi/BLE MAC addresses for the target ESPHome device."""
        return sorted(_int_to_mac(m) for m in self._target_mac_ints)

    @callback
    def set_area_offsets(self, offsets: dict[str, float] | None) -> None:
        """Update per-area RSSI calibration offsets (dB bias) in real time and recompute effective RSSI."""
        self._area_offsets = {
            str(k): max(-25.0, min(25.0, float(v)))
            for k, v in (offsets or {}).items()
        }
        now = time.monotonic()
        for area_id, (raw_ema, ts, _scanner) in list(self._area_raw_rssi.items()):
            offset_db = float(self._area_offsets.get(area_id, 0.0))
            self._area_rssi[area_id] = (raw_ema + offset_db, ts)
        self._evaluate_best_area(now)

    @callback
    def reset_for_device_wake(self) -> None:
        """Clear stale RSSI history on wake while preserving sticky current_area_id until fresh BLE lock."""
        now = time.monotonic()
        if self.last_packet_monotonic > 0.0 and (now - self.last_packet_monotonic) < 6.0:
            return
        fabric = get_ble_fabric(self.hass)
        self._area_rssi.clear()
        self._area_raw_rssi.clear()
        self._unmapped_rssi.clear()
        self._scanner_area_cache.clear()
        fabric._scanner_area_cache.clear()
        self._last_adv_ts_by_scanner.clear()
        self._awaiting_fresh_wake_lock = True
        self._last_switch_monotonic = 0.0
        self._target_mac_ints = _discover_target_device_macs(
            self.hass, self._esphome_device_id
        )
        fabric.sync_tracker_addresses()

    @callback
    def async_start(self) -> None:
        """Register this tracker with the singleton LatterBleFabric."""
        self.async_stop()
        self._started_monotonic = time.monotonic()
        self._target_mac_ints = _discover_target_device_macs(
            self.hass, self._esphome_device_id
        )
        fabric = get_ble_fabric(self.hass)
        fabric.register_tracker(self)
        _LOGGER.info(
            "Latter Native BLE Area Tracker registered with shared BLE Fabric (device=%s, UUID=%s, macs=%s)",
            self._raw_slug,
            self._target_uuid_hex,
            self.target_macs_formatted,
        )

    @callback
    def async_stop(self) -> None:
        """Unregister this tracker from the singleton LatterBleFabric."""
        fabric = get_ble_fabric(self.hass)
        fabric.unregister_tracker(self)
        self._area_rssi.clear()
        self._area_raw_rssi.clear()
        self._unmapped_rssi.clear()
        self._scanner_area_cache.clear()
        self._last_adv_ts_by_scanner.clear()

    def get_area_calibration_telemetry(self) -> list[dict[str, Any]]:
        """Return rich per-area BLE site survey telemetry."""
        area_reg = ar.async_get(self.hass)
        now = time.monotonic()

        area_scanners: dict[str, list[str]] = {}
        try:
            from homeassistant.components import bluetooth

            for scanner in bluetooth.async_current_scanners(self.hass):
                source = str(getattr(scanner, "source", "") or "")
                name = str(getattr(scanner, "name", "") or source)
                if not source:
                    continue
                a_id = _resolve_scanner_area_id(self.hass, source)
                if a_id:
                    area_scanners.setdefault(a_id, []).append(name)
        except Exception:  # noqa: BLE001
            pass

        all_area_ids = (
            set(area_scanners.keys())
            | set(self._area_raw_rssi.keys())
            | set(self._area_offsets.keys())
        )

        rows: list[dict[str, Any]] = []
        for area_id in all_area_ids:
            area_obj = area_reg.async_get_area(area_id)
            area_name = area_obj.name if area_obj else area_id
            offset_db = round(float(self._area_offsets.get(area_id, 0.0)), 1)
            raw_tuple = self._area_raw_rssi.get(area_id)

            raw_dbm: int | None = None
            effective_dbm: int | None = None
            age_s: int | None = None
            is_fresh = False
            scanner_label = ", ".join(area_scanners.get(area_id, []))

            if raw_tuple is not None:
                raw_ema, ts, last_scan = raw_tuple
                elapsed = max(0.0, now - ts)
                if elapsed <= SURVEY_RETENTION_SECONDS:
                    raw_dbm = round(raw_ema)
                    effective_dbm = round(raw_ema + offset_db)
                    age_s = round(elapsed)
                    is_fresh = elapsed <= STALE_PROXY_SECONDS
                    if last_scan and not scanner_label:
                        scanner_label = last_scan

            dist_m: float | None = None
            dist_ft: float | None = None
            if effective_dbm is not None:
                dist_m = rssi_to_distance_m(effective_dbm)
                dist_ft = round(dist_m * 3.28084, 1)

            rows.append(
                {
                    "area_id": area_id,
                    "area_name": area_name,
                    "scanner": scanner_label or "BLE Proxy",
                    "raw_rssi": raw_dbm,
                    "offset_db": offset_db,
                    "effective_rssi": effective_dbm,
                    "distance_m": dist_m,
                    "distance_ft": dist_ft,
                    "age_seconds": age_s,
                    "is_fresh": is_fresh,
                    "is_winner": area_id == self.current_area_id,
                }
            )

        rows.sort(
            key=lambda r: (
                r["effective_rssi"] is None,
                -(r["effective_rssi"] if r["effective_rssi"] is not None else -999),
                r["area_name"].lower(),
            )
        )
        return rows

    def _matches_raw_adv(
        self,
        address: str,
        mfg_data: dict[int, bytes],
    ) -> bool:
        """Return True if raw advertisement fields match this device's MAC or iBeacon UUID."""
        adv_int = _mac_to_int(address) if address else None

        if address and address in self._matched_ble_addresses:
            return True
        if self._target_mac_ints and adv_int is not None and adv_int in self._target_mac_ints:
            return True

        apple_bytes = mfg_data.get(APPLE_COMPANY_ID)
        if apple_bytes and len(apple_bytes) >= 18:
            uuid_matched = False
            major_val: int | None = None
            minor_val: int | None = None
            if len(apple_bytes) >= 20 and apple_bytes[:2] == IBEACON_PREFIX:
                uuid_hex = apple_bytes[2:18].hex().lower()
                uuid_matched = uuid_hex == self._target_uuid_hex
                if len(apple_bytes) >= 20:
                    major_val = (apple_bytes[18] << 8) | apple_bytes[19]
                if len(apple_bytes) >= 22:
                    minor_val = (apple_bytes[20] << 8) | apple_bytes[21]
            elif self._target_uuid_hex in apple_bytes.hex().lower():
                uuid_matched = True
            if uuid_matched:
                expected_major, expected_minor = self._resolve_beacon_major_minor()
                if expected_major is not None and expected_major >= 1 and major_val != expected_major:
                    return False
                if expected_minor is not None and expected_minor >= 1:
                    return minor_val == expected_minor
                return not bool(self._esphome_device_id)

        return False

    def _matches_target_device(self, service_info: object) -> bool:
        """Return True if a BluetoothServiceInfoBleak object matches iBeacon UUID or MAC."""
        mfg_data: dict[int, bytes] = getattr(
            service_info, "manufacturer_data", {}
        ) or {}
        adv_address = str(getattr(service_info, "address", "") or "")
        matched = self._matches_raw_adv(adv_address, mfg_data)
        if matched and adv_address:
            self._record_matched_ble_address(adv_address)
        return matched

    @callback
    def _async_on_ble_advertisement(
        self, service_info: object, _change: object
    ) -> None:
        """Process incoming BLE advertisement callback from an ESPHome BLE proxy."""
        if not self._matches_target_device(service_info):
            return

        rssi = getattr(service_info, "rssi", None)
        source = str(getattr(service_info, "source", "") or "")
        if rssi is None or not source or int(rssi) <= -100:
            return

        adv_ts = getattr(service_info, "time", None)
        obs_mono = float(adv_ts) if adv_ts is not None else time.monotonic()
        self._ingest_proxy_observation(source, int(rssi), obs_mono, source)

    @callback
    def _ingest_proxy_observation(
        self,
        source: str,
        rssi: int,
        obs_time: float,
        scanner_name: str = "",
        *,
        from_poll: bool = False,
    ) -> None:
        """Ingest a (scanner_source, rssi) observation and evaluate area transitions."""
        now = time.monotonic()
        prev_adv_ts = self._last_adv_ts_by_scanner.get(source)
        if prev_adv_ts is not None:
            if from_poll and obs_time <= (prev_adv_ts + 1e-4):
                self._evaluate_best_area(now, "")
                return
            if not from_poll and abs(obs_time - prev_adv_ts) < 1e-6:
                return

        self._last_adv_ts_by_scanner[source] = obs_time
        just_woke_from_standby = (
            self.last_packet_monotonic > 0.0
            and (obs_time - self.last_packet_monotonic) >= WAKE_GAP_SECONDS
        )
        if obs_time > self.last_packet_monotonic:
            self.last_packet_monotonic = obs_time
        self.packets_seen += 1

        if not self._target_mac_ints and self.packets_seen <= 3:
            self._target_mac_ints = _discover_target_device_macs(
                self.hass, self._esphome_device_id
            )
            if self._target_mac_ints:
                get_ble_fabric(self.hass).sync_tracker_addresses()

        cached_area = self._scanner_area_cache.get(source)
        if cached_area is None:
            resolved_area = _resolve_scanner_area_id(self.hass, source)
            cached_area = resolved_area if resolved_area else _UNMAPPED
            self._scanner_area_cache[source] = cached_area

        area_id = None if cached_area == _UNMAPPED else cached_area
        if not area_id:
            self._unmapped_rssi[source] = (int(rssi), obs_time)
            return

        self._unmapped_rssi.pop(source, None)

        if just_woke_from_standby:
            self._area_rssi.clear()
            self._area_raw_rssi.clear()
            self._last_switch_monotonic = 0.0
            self._awaiting_fresh_wake_lock = True

        prev_raw = self._area_raw_rssi.get(area_id)
        raw_ema = smooth_rssi(
            (prev_raw[0], prev_raw[1]) if prev_raw is not None else None,
            float(rssi),
            obs_time,
        )
        self._area_raw_rssi[area_id] = (raw_ema, obs_time, scanner_name or source)

        offset_db = float(self._area_offsets.get(area_id, 0.0))
        eff_ema = raw_ema + offset_db
        self._area_rssi[area_id] = (eff_ema, obs_time)

        if (now - obs_time) <= STALE_PROXY_SECONDS:
            self._evaluate_best_area(now, source)

    @callback
    def _evaluate_best_area(self, now: float, latest_source: str = "") -> None:
        """Evaluate fresh effective RSSI scores with 6.0 dB floor penalty & 3.0 dBm deadband."""
        area_reg = ar.async_get(self.hass)
        prior_area_id = None if self._awaiting_fresh_wake_lock else self.current_area_id
        cur_floor_id: str | None = None
        if prior_area_id:
            cur_area_entry = area_reg.async_get_area(prior_area_id)
            if cur_area_entry:
                cur_floor_id = getattr(cur_area_entry, "floor_id", None)

        def _is_cross_floor(area_id: str) -> bool:
            if not cur_floor_id or area_id == prior_area_id:
                return False
            cand_entry = area_reg.async_get_area(area_id)
            cand_floor_id = getattr(cand_entry, "floor_id", None) if cand_entry else None
            return bool(cand_floor_id and cand_floor_id != cur_floor_id)

        scores = score_areas(self._area_rssi, now, _is_cross_floor)
        decision = decide_area(
            scores, prior_area_id, now, self._last_switch_monotonic
        )
        fabric = get_ble_fabric(self.hass)
        if decision is None:
            fabric.emit_survey_delta(self)
            return
        self._awaiting_fresh_wake_lock = False
        self.is_away = False
        best_area = decision.best_area_id

        def _update_winner_metrics(win_area: str) -> None:
            eff_entry = self._area_rssi.get(win_area)
            if eff_entry is not None:
                eff_dbm = eff_entry[0]
                self.winning_rssi = round(eff_dbm)
                d_m = rssi_to_distance_m(eff_dbm)
                self.winning_distance_m = d_m
                self.winning_distance_ft = round(d_m * 3.28084, 1)

        if best_area == self.current_area_id:
            eff_entry = self._area_rssi.get(best_area)
            eff_dbm = eff_entry[0] if eff_entry is not None else None
            if latest_source:
                self.closest_scanner = latest_source
            if eff_dbm is not None and within_rssi_deadband(self.winning_rssi, eff_dbm):
                fabric.emit_survey_delta(self)
                return
            prev_rssi = self.winning_rssi
            _update_winner_metrics(best_area)
            fabric.emit_survey_delta(self)
            if self.winning_rssi != prev_rssi:
                fabric.notify_occupancy_listeners()
            return

        _LOGGER.debug(
            "BLE area candidate (%s): area=%s score=%.1fdBm current=%s score=%.1fdBm switch=%s (deadband=%.1fdBm)",
            self._raw_slug,
            best_area,
            decision.best_score,
            self.current_area_id,
            decision.current_score,
            decision.switch,
            RSSI_HYSTERESIS_DEADBAND_DBM,
        )
        if not decision.switch:
            fabric.emit_survey_delta(self)
            return

        self.current_area_id = best_area
        _update_winner_metrics(best_area)
        if latest_source:
            self.closest_scanner = latest_source
        self._last_switch_monotonic = now
        self._on_area_detected(best_area, self.closest_scanner)
        fabric.emit_survey_delta(self)
        fabric.notify_occupancy_listeners()


class LatterBleFabric:
    """Domain-level singleton Bluetooth scanner fabric shared across all Latter & generic BLE trackers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the shared BLE scanner fabric."""
        self.hass = hass
        self._trackers: list[LatterNativeBleTracker] = []
        self._occupancy_listeners: list[Callable[[], None]] = []
        self._survey_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._scanner_area_cache: dict[str, str | None] = {}
        self._unsub_ble: Callable[[], None] | None = None
        self._adv_unsubs: dict[str, Callable[[], None]] = {}
        self._unsub_away_timer: Callable[[], None] | None = None
        self._unsub_sensor_events: Callable[[], None] | None = None

    @callback
    def _invalidate_caches(self, _event: Any = None) -> None:
        """Invalidate scanner-to-area caches, fusion index, and targeted fusion listeners."""
        self._scanner_area_cache.clear()
        for tracker in self._trackers:
            tracker._scanner_area_cache.clear()
            if tracker._esphome_device_id:
                tracker._target_mac_ints = _discover_target_device_macs(
                    self.hass, tracker._esphome_device_id
                )
        self.sync_tracker_addresses()
        invalidate_area_fusion_index(self.hass)
        if self._occupancy_listeners:
            self.rebind_fusion_sensor_listener()

    @callback
    def rebind_fusion_sensor_listener(self) -> None:
        """Subscribe ONLY to tracked Area fusion binary_sensors (never global state_changed)."""
        if self._unsub_sensor_events is not None:
            self._unsub_sensor_events()
            self._unsub_sensor_events = None
        if not self._occupancy_listeners:
            return
        tracked_ids = sorted(get_tracked_fusion_entity_ids(self.hass))
        if not tracked_ids:
            return
        self._unsub_sensor_events = async_track_state_change_event(
            self.hass,
            tracked_ids,
            self._async_on_fusion_sensor_changed,
        )

    @callback
    def register_occupancy_listener(
        self, listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a listener for real-time per-area BLE & sensor-fused occupancy changes."""
        if listener not in self._occupancy_listeners:
            self._occupancy_listeners.append(listener)
        if self._unsub_sensor_events is None:
            self.rebind_fusion_sensor_listener()

        @callback
        def _unsub() -> None:
            if listener in self._occupancy_listeners:
                self._occupancy_listeners.remove(listener)
            if not self._occupancy_listeners and self._unsub_sensor_events is not None:
                self._unsub_sensor_events()
                self._unsub_sensor_events = None

        return _unsub

    @callback
    def register_survey_listener(
        self, listener: Callable[[dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Register a Studio WebSocket listener for live `ble_survey_delta` telemetry."""
        if listener not in self._survey_listeners:
            self._survey_listeners.append(listener)

        @callback
        def _unsub() -> None:
            if listener in self._survey_listeners:
                self._survey_listeners.remove(listener)

        return _unsub

    @callback
    def emit_survey_delta(self, tracker: LatterNativeBleTracker) -> None:
        """Push a compact `ble_survey_delta` payload to active Studio site survey subscribers."""
        if not self._survey_listeners:
            return
        payload = {
            "device_slug": tracker._raw_slug,
            "current_area_id": tracker.current_area_id or "",
            "winning_rssi": tracker.winning_rssi,
            "closest_scanner": tracker.closest_scanner,
            "calibration": tracker.get_area_calibration_telemetry(),
        }
        for cb in list(self._survey_listeners):
            cb(payload)

    @callback
    def _async_on_fusion_sensor_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Trigger occupancy re-evaluation when a tracked Area fusion sensor changes state."""
        new_st = event.data.get("new_state")
        old_st = event.data.get("old_state")
        if new_st is None or (old_st is not None and new_st.state == old_st.state):
            return
        self.notify_occupancy_listeners()

    @callback
    def notify_occupancy_listeners(self) -> None:
        """Notify all registered per-area BLE occupancy and occupant sensors."""
        for listener in list(self._occupancy_listeners):
            listener()

    @callback
    def get_area_occupancy(self, area_id: str) -> dict[str, Any]:
        """Return deterministic & weighted fused BLE + physical sensor occupancy telemetry for an Area."""
        from .hub import iter_coordinators

        area_reg = ar.async_get(self.hass)
        area_obj = area_reg.async_get(area_id) if hasattr(area_reg, "async_get") else None
        if area_obj is None:
            area_obj = area_reg.async_get_area(area_id)
        floor_id = getattr(area_obj, "floor_id", None) if area_obj else None

        coord_by_slug: dict[str, Any] = {
            coord.device_slug: coord
            for coord in iter_coordinators(self.hass)
            if coord.device_slug
        }

        occupants: list[str] = []
        occupant_names: list[str] = []
        persons: list[str] = []
        best_rssi: int | None = None
        closest_dev: str | None = None
        closest_dist_m: float | None = None
        closest_dist_ft: float | None = None

        for tracker in self._trackers:
            if not tracker.is_away and tracker.current_area_id == area_id:
                slug = tracker._raw_slug
                occupants.append(slug)
                coord = coord_by_slug.get(slug)
                p_ent = (
                    str(getattr(coord, "assigned_person", "") or "").strip()
                    if coord
                    else ""
                )
                if p_ent and p_ent.startswith("person."):
                    if p_ent not in persons:
                        persons.append(p_ent)
                    p_st = self.hass.states.get(p_ent)
                    p_name = (
                        str(p_st.attributes.get("friendly_name") or "").strip()
                        if p_st
                        else ""
                    ) or p_ent.split(".", 1)[-1].replace("_", " ").title()
                    if p_name not in occupant_names:
                        occupant_names.append(p_name)
                else:
                    d_label = slug.replace("_", " ").replace("-", " ").title()
                    if d_label not in occupant_names:
                        occupant_names.append(d_label)

                if tracker.winning_rssi is not None and (
                    best_rssi is None or tracker.winning_rssi > best_rssi
                ):
                    best_rssi = tracker.winning_rssi
                    closest_dev = slug
                    closest_dist_m = tracker.winning_distance_m
                    closest_dist_ft = tracker.winning_distance_ft

        ble_present = len(occupants) > 0
        fused = evaluate_area_sensor_fusion(
            self.hass,
            area_id,
            ble_present=ble_present,
            best_rssi=best_rssi,
        )

        return {
            "is_occupied": fused["is_occupied"],
            "ble_occupied": fused["ble_occupied"],
            "sensor_occupied": fused["sensor_occupied"],
            "fusion_mode": fused["fusion_mode"],
            "confidence_pct": fused["confidence_pct"],
            "tracker_count": len(occupants),
            "occupied_by": occupants,
            "occupant_names": occupant_names,
            "persons": persons,
            "active_sensors": fused["active_sensors"],
            "available_sensors": fused["available_sensors"],
            "closest_device": closest_dev,
            "winning_rssi": best_rssi,
            "closest_distance_m": closest_dist_m,
            "closest_distance_ft": closest_dist_ft,
            "floor_id": floor_id,
        }

    @callback
    def sync_tracker_addresses(self) -> None:
        """Subscribe directly to every advertisement for known tracker MACs (bypassing static-payload dedupe)."""
        if self._unsub_ble is None:
            return
        wanted: set[str] = set()
        for tracker in self._trackers:
            for mac in tracker.target_macs_formatted:
                if mac:
                    wanted.add(mac.upper())
            for matched in tracker._matched_ble_addresses:
                if matched:
                    wanted.add(matched.upper())

        for stale_addr in list(self._adv_unsubs):
            if stale_addr not in wanted:
                unsub = self._adv_unsubs.pop(stale_addr, None)
                if unsub is not None:
                    unsub()

        missing = sorted(wanted - set(self._adv_unsubs))
        if not missing:
            return
        try:
            from homeassistant.components import bluetooth

            reg_adv_cb = getattr(bluetooth, "async_register_advertisement_callback", None)
            if callable(reg_adv_cb):
                for addr in missing:
                    self._adv_unsubs[addr] = reg_adv_cb(
                        self.hass,
                        self._async_on_raw_ble_advertisement,
                        addr,
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Raw BLE advertisement callback sync skipped: %s", err)

    @callback
    def register_tracker(self, tracker: LatterNativeBleTracker) -> None:
        """Register a BLE tracker and start the shared passive callback fabric if needed."""
        if tracker not in self._trackers:
            self._trackers.append(tracker)
        if len(self._trackers) == 1 and self._unsub_ble is None:
            self._async_start_fabric()
        self.sync_tracker_addresses()
        self._async_seed_tracker_from_scanners_once(tracker)
        self.notify_occupancy_listeners()

    @callback
    def unregister_tracker(self, tracker: LatterNativeBleTracker) -> None:
        """Unregister a BLE tracker and stop the shared fabric when empty."""
        if tracker in self._trackers:
            self._trackers.remove(tracker)
        if not self._trackers:
            self._async_stop_fabric()
        else:
            self.sync_tracker_addresses()
        self.notify_occupancy_listeners()

    @callback
    def _async_start_fabric(self) -> None:
        """Start the shared passive Bluetooth callback (`connectable=False`) and away timer."""
        unsubs: list[Callable[[], None]] = []
        try:
            from homeassistant.components import bluetooth

            try:
                matcher = bluetooth.BluetoothCallbackMatcher(connectable=False)
            except TypeError:
                matcher = bluetooth.BluetoothCallbackMatcher(
                    manufacturer_id=APPLE_COMPANY_ID,
                    manufacturer_data_start=[0x02, 0x15],
                )
            unsubs.append(
                bluetooth.async_register_callback(
                    self.hass,
                    self._async_on_shared_ble_advertisement,
                    matcher,
                    bluetooth.BluetoothScanningMode.PASSIVE,
                )
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Passive Bluetooth callback registration skipped: %s", err)

        unsubs.extend(
            [
                self.hass.bus.async_listen(
                    "esphome.ibeacon_seen", self._async_on_esphome_ibeacon_event
                ),
                self.hass.bus.async_listen(
                    dr.EVENT_DEVICE_REGISTRY_UPDATED, self._invalidate_caches
                ),
                self.hass.bus.async_listen(
                    er.EVENT_ENTITY_REGISTRY_UPDATED, self._invalidate_caches
                ),
                self.hass.bus.async_listen(
                    ar.EVENT_AREA_REGISTRY_UPDATED, self._invalidate_caches
                ),
            ]
        )

        @callback
        def _unsub_combined() -> None:
            for u in unsubs:
                u()

        self._unsub_ble = _unsub_combined
        self._unsub_away_timer = async_track_time_interval(
            self.hass,
            self._async_check_away_timeouts,
            timedelta(seconds=AWAY_CHECK_INTERVAL_SECONDS),
        )

    @callback
    def _async_stop_fabric(self) -> None:
        """Stop the shared Bluetooth callback, per-address raw callbacks, and away-timeout timer."""
        self._scanner_area_cache.clear()
        for unsub_adv in list(self._adv_unsubs.values()):
            unsub_adv()
        self._adv_unsubs.clear()
        if self._unsub_ble is not None:
            self._unsub_ble()
            self._unsub_ble = None
        if self._unsub_away_timer is not None:
            self._unsub_away_timer()
            self._unsub_away_timer = None
        if self._unsub_sensor_events is not None:
            self._unsub_sensor_events()
            self._unsub_sensor_events = None

    @callback
    def _async_on_esphome_ibeacon_event(self, event: Any) -> None:
        """Ingest custom esphome.ibeacon_seen bus events emitted by ESPHome BLE proxies."""
        data = getattr(event, "data", {}) or {}
        source = str(data.get("source") or data.get("scanner") or "").strip()
        uuid_raw = _normalize_uuid_hex(str(data.get("uuid") or ""))
        rssi = data.get("rssi")
        if not source or rssi is None or int(rssi) <= -100:
            return
        adv_addr = str(data.get("address") or data.get("mac") or "").strip().upper()
        adv_int = _mac_to_int(adv_addr) if adv_addr else None
        raw_major = data.get("major")
        raw_minor = data.get("minor")
        ev_major = (
            int(raw_major)
            if isinstance(raw_major, (int, float))
            or (isinstance(raw_major, str) and raw_major.isdigit())
            else None
        )
        ev_minor = (
            int(raw_minor)
            if isinstance(raw_minor, (int, float))
            or (isinstance(raw_minor, str) and raw_minor.isdigit())
            else None
        )
        now_mono = time.monotonic()
        for tracker in list(self._trackers):
            if not (uuid_raw and uuid_raw == tracker._target_uuid_hex):
                continue
            mac_ok = bool(
                (adv_addr and adv_addr in tracker._matched_ble_addresses)
                or (
                    tracker._target_mac_ints
                    and adv_int is not None
                    and adv_int in tracker._target_mac_ints
                )
            )
            if not mac_ok:
                expected_major, expected_minor = tracker._resolve_beacon_major_minor()
                if (
                    expected_major is not None
                    and expected_major >= 1
                    and ev_major != expected_major
                ):
                    continue
                if expected_minor is not None and expected_minor >= 1:
                    if ev_minor != expected_minor:
                        continue
                elif tracker._esphome_device_id:
                    continue
            tracker._ingest_proxy_observation(source, int(rssi), now_mono, source)

    @callback
    def _async_on_raw_ble_advertisement(self, service_info: object) -> None:
        """Fan out per-address raw advertisements (including static payloads) to all registered trackers."""
        self._async_on_shared_ble_advertisement(service_info, None)

    @callback
    def _async_on_shared_ble_advertisement(
        self, service_info: object, change: object
    ) -> None:
        """Fan out incoming passive BLE advertisements to all registered trackers."""
        for tracker in list(self._trackers):
            tracker._async_on_ble_advertisement(service_info, change)

    @callback
    def _async_check_away_timeouts(self, _now_dt: datetime) -> None:
        """Lightweight away-timeout & deferred MAC discovery check (no scanner-table walk)."""
        if not self._trackers:
            return
        now_mono = time.monotonic()
        discovered_any = False
        for tracker in list(self._trackers):
            tracker.check_away_timeout(now_mono)
            if (
                not tracker._target_mac_ints
                and (now_mono - tracker._last_mac_discovery_mono) >= 30.0
            ):
                tracker._last_mac_discovery_mono = now_mono
                tracker._target_mac_ints = _discover_target_device_macs(
                    self.hass, tracker._esphome_device_id
                )
                if tracker._target_mac_ints:
                    discovered_any = True
        if discovered_any:
            self.sync_tracker_addresses()

    @callback
    def _async_seed_tracker_from_scanners_once(
        self, tracker: LatterNativeBleTracker
    ) -> None:
        """Seed one newly registered tracker from current Bluetooth scanner state once."""
        try:
            from homeassistant.components import bluetooth

            now_mono = time.monotonic()
            for scanner in bluetooth.async_current_scanners(self.hass):
                source = str(getattr(scanner, "source", "") or "")
                scanner_name = str(getattr(scanner, "name", "") or source)
                if not source:
                    continue
                timestamps: dict[str, float] = (
                    getattr(scanner, "discovered_device_timestamps", None)
                    or getattr(scanner, "timestamps", None)
                    or {}
                )
                dev_adv_map: dict[str, tuple[Any, Any]] = (
                    getattr(scanner, "discovered_devices_and_advertisement_data", {})
                    or {}
                )
                for addr, pair in dev_adv_map.items():
                    if not isinstance(pair, tuple) or len(pair) != 2:
                        continue
                    ble_dev, adv_data = pair
                    last_ts = timestamps.get(addr)
                    obs_mono = float(last_ts) if last_ts is not None else now_mono
                    if last_ts is not None and (now_mono - obs_mono) > SURVEY_RETENTION_SECONDS:
                        continue
                    mfg_data = getattr(adv_data, "manufacturer_data", {}) or {}
                    rssi = getattr(adv_data, "rssi", None)
                    if rssi is None:
                        rssi = getattr(ble_dev, "rssi", None)
                    if rssi is None or int(rssi) <= -100:
                        continue
                    addr_str = str(addr)
                    if tracker._matches_raw_adv(addr_str, mfg_data):
                        tracker._record_matched_ble_address(addr_str)
                        tracker._ingest_proxy_observation(
                            source,
                            int(rssi),
                            obs_mono,
                            scanner_name,
                            from_poll=last_ts is not None,
                        )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Initial BLE scanner seed skipped: %s", err)


def get_ble_fabric(hass: HomeAssistant) -> LatterBleFabric:
    """Return or initialize the singleton LatterBleFabric instance."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "ble_fabric" not in domain_data:
        domain_data["ble_fabric"] = LatterBleFabric(hass)
    return domain_data["ble_fabric"]


def get_all_areas_presence_summary(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Build live per-area presence, occupant names, confidence score, and fusion settings."""
    area_reg = ar.async_get(hass)
    fabric = get_ble_fabric(hass)
    proxy_areas = get_ble_proxy_area_ids(hass)

    rows: list[dict[str, Any]] = []
    for area_entry in sorted(area_reg.async_list_areas(), key=lambda a: a.name.lower()):
        occ = fabric.get_area_occupancy(area_entry.id)
        has_proxy = area_entry.id in proxy_areas
        has_sensors = len(occ["available_sensors"]) > 0
        if not has_proxy and not has_sensors and not occ["is_occupied"]:
            continue
        fusion_cfg = area_fusion_settings(hass, area_entry.id)
        rows.append(
            {
                "area_id": area_entry.id,
                "area_name": area_entry.name,
                "floor_id": getattr(area_entry, "floor_id", None) or "",
                "has_ble_proxy": has_proxy,
                "is_occupied": occ["is_occupied"],
                "ble_occupied": occ["ble_occupied"],
                "sensor_occupied": occ["sensor_occupied"],
                "fusion_mode": occ["fusion_mode"],
                "confidence_pct": occ["confidence_pct"],
                "tracker_count": occ["tracker_count"],
                "occupied_by": occ["occupied_by"],
                "occupant_names": occ["occupant_names"],
                "persons": occ["persons"],
                "active_sensors": occ["active_sensors"],
                "available_sensors": occ["available_sensors"],
                "closest_device": occ["closest_device"] or "",
                "winning_rssi": occ["winning_rssi"],
                "closest_distance_m": occ["closest_distance_m"],
                "closest_distance_ft": occ["closest_distance_ft"],
                "fusion_threshold_pct": int(fusion_cfg.get("threshold_pct") or 50),
                "fusion_sensors": [
                    str(s) for s in (fusion_cfg.get("sensors") or []) if isinstance(s, str)
                ],
                "fusion_sensor_choices": area_fusion_sensor_choices(hass, area_entry.id),
            }
        )
    return rows


def get_discovered_ble_candidates(
    hass: HomeAssistant, onboarded_slugs: set[str], onboarded_addresses: set[str]
) -> list[dict[str, Any]]:
    """Discover non-ESPHome BLE devices (private_ble_device, ibeacon, active BLE tags) available to track."""
    candidates: list[dict[str, Any]] = []
    seen_targets: set[str] = {a.lower() for a in onboarded_addresses if a}
    ent_reg = er.async_get(hass)
    area_reg = ar.async_get(hass)

    for entry in _iter_entities(ent_reg):
        if entry.disabled_by:
            continue
        if entry.platform in ("private_ble_device", "ibeacon") and entry.domain in (
            "device_tracker",
            "sensor",
        ):
            if entry.domain == "sensor" and not entry.entity_id.endswith("estimated_distance"):
                continue
            st = hass.states.get(entry.entity_id)
            friendly = (
                str(st.attributes.get("friendly_name") if st else "")
                or entry.name
                or entry.original_name
                or entry.entity_id
            ).strip()
            for suffix in (" Estimated Distance", "Signal Strength"):
                if friendly.endswith(suffix):
                    friendly = friendly[: -len(suffix)].strip()
            cand_slug = normalize_device_slug(friendly)
            if (
                not cand_slug
                or cand_slug == "esphome_device"
                or cand_slug in onboarded_slugs
                or entry.entity_id.lower() in seen_targets
            ):
                continue
            seen_targets.add(entry.entity_id.lower())
            kind_lbl = (
                "Private BLE (phone or watch)"
                if entry.platform == "private_ble_device"
                else "iBeacon tracker"
            )
            rssi_val = st.attributes.get("rssi") if st else None
            src_scanner = str(st.attributes.get("source") or "") if st else ""
            a_id = _resolve_scanner_area_id(hass, src_scanner) if src_scanner else None
            a_obj = area_reg.async_get_area(a_id) if a_id else None
            candidates.append(
                {
                    "slug": cand_slug,
                    "title": friendly,
                    "target_address": entry.entity_id,
                    "kind": kind_lbl,
                    "rssi": int(rssi_val) if isinstance(rssi_val, (int, float)) else None,
                    "area_name": a_obj.name if a_obj else "",
                    "scanner": src_scanner,
                    "label": f"{friendly} [{kind_lbl}]",
                }
            )

    best_by_addr: dict[str, dict[str, Any]] = {}
    try:
        from homeassistant.components import bluetooth

        for scanner in bluetooth.async_current_scanners(hass):
            source = str(getattr(scanner, "source", "") or "")
            scanner_name = str(getattr(scanner, "name", "") or source)
            a_id = _resolve_scanner_area_id(hass, source) if source else None
            a_obj = area_reg.async_get_area(a_id) if a_id else None
            area_name = a_obj.name if a_obj else ""

            dev_adv_map: dict[str, tuple[Any, Any]] = (
                getattr(scanner, "discovered_devices_and_advertisement_data", {})
                or {}
            )
            for addr, pair in dev_adv_map.items():
                if not isinstance(pair, tuple) or len(pair) != 2:
                    continue
                ble_dev, adv_data = pair
                addr_str = str(addr).upper()
                if addr_str.lower() in seen_targets:
                    continue
                local_name = str(
                    getattr(adv_data, "local_name", "")
                    or getattr(ble_dev, "name", "")
                    or ""
                ).strip()
                if (
                    not local_name
                    or local_name.replace(":", "").replace("-", "").upper()
                    == addr_str.replace(":", "")
                ):
                    continue
                cand_slug = normalize_device_slug(local_name)
                if (
                    not cand_slug
                    or cand_slug == "esphome_device"
                    or cand_slug in onboarded_slugs
                ):
                    continue
                rssi = getattr(adv_data, "rssi", None)
                if rssi is None:
                    rssi = getattr(ble_dev, "rssi", None)
                rssi_int = int(rssi) if rssi is not None else None
                prev = best_by_addr.get(addr_str)
                if prev is None or (
                    rssi_int is not None
                    and (prev["rssi"] is None or rssi_int > prev["rssi"])
                ):
                    rssi_str = f" ({rssi_int} dBm)" if rssi_int is not None else ""
                    area_str = f" • {area_name}" if area_name else ""
                    best_by_addr[addr_str] = {
                        "slug": cand_slug,
                        "title": local_name,
                        "target_address": addr_str,
                        "kind": "Named BLE device",
                        "rssi": rssi_int,
                        "area_name": area_name,
                        "scanner": scanner_name,
                        "label": f"{local_name} [{addr_str}]{rssi_str}{area_str}",
                    }
    except Exception:  # noqa: BLE001
        pass

    for addr_str, item in best_by_addr.items():
        seen_targets.add(addr_str.lower())
        candidates.append(item)

    candidates.sort(
        key=lambda x: (
            x.get("rssi") is None,
            -(x.get("rssi") if x.get("rssi") is not None else -999),
            str(x.get("title") or "").lower(),
        )
    )
    return candidates[:40]
