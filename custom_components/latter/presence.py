"""Event-driven BLE Proxy Area Presence Fabric, scoring math, dwell gate, and sensor fusion for Latter."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import math
import re
import time
from typing import Any

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)

from .const import (
    CONF_BLE_AREA_SIGNATURES,
    DATA_GLOBAL_CONFIG,
    DEFAULT_BLE_ATTENUATION,
    DEFAULT_BLE_AWAY_TIMEOUT_S,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_BLE_MAX_RADIUS_M,
    DEFAULT_BLE_MAX_VELOCITY_MPS,
    DOMAIN,
    normalize_device_slug,
)
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
CORROBORATION_BONUS_DB = 1.5
CORROBORATION_MIN_DBM = -82.0
SIGNATURE_PEAK_SCORE_DBM = -45.0
SIGNATURE_RING_WINDOW_SECONDS = 12.0
SIGNATURE_CAPTURE_WINDOW_SECONDS = 15.0
SIGNATURE_RING_MAX_SAMPLES = 32
WAKE_COALESCE_SECONDS = 0.35
KALMAN_MEASUREMENT_VAR = 9.0
EDDYSTONE_UUID_PREFIX = "0000feaa"
BTHOME_UUID_PREFIX = "0000fcd2"
COMPANION_TX_POWER_1M_DBM: dict[str, float] = {
    "ultralow": -81.0,
    "low": -75.0,
    "medium": -67.0,
    "high": -59.0,
}


def resolve_companion_tx_ref_power_dbm(
    measured_power: Any, tx_power_level: Any
) -> float | None:
    """Resolve 1 m reference power for a Home Assistant Companion App BLE Transmitter.

    Android's Companion App defaults `Transmitting power` to `ultraLow` (-21 dBm TX) while
    leaving `Measured power` at the uncalibrated `-59` default (both in entity attributes
    and iBeacon byte 22). When `Measured power` is unset or left at `-59`, compensate using
    the reported `Transmitting power` tier so 1 m path-loss and Area Signatures stay aligned.
    """
    mp_f: float | None = None
    if measured_power is not None and not isinstance(measured_power, bool):
        try:
            cand = float(measured_power)
            if -90.0 <= cand <= -30.0:
                mp_f = cand
        except (TypeError, ValueError):
            mp_f = None
    tx_key = re.sub(r"[^a-z]", "", str(tx_power_level or "").lower())
    if tx_key in COMPANION_TX_POWER_1M_DBM and (
        mp_f is None or abs(mp_f - TX_POWER_1M_DBM) < 0.5
    ):
        return COMPANION_TX_POWER_1M_DBM[tx_key]
    return mp_f


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
    *,
    challenger_packet_count: int = 2,
) -> AreaDecision | None:
    """Pick the best-scoring Area and decide whether the Device moves there."""
    if not scores:
        return None
    best_area_id, best_score = min(
        scores.items(),
        key=lambda item: (-round(item[1], 6), item[0] != current_area_id, item[0]),
    )
    if best_score < MIN_WINNING_RSSI_DBM:
        return None
    if current_area_id is None:
        return AreaDecision(best_area_id, best_score, NO_SIGNAL_RSSI_DBM, True)
    if best_area_id == current_area_id:
        return AreaDecision(best_area_id, best_score, best_score, False)
    current_score = scores.get(current_area_id, NO_SIGNAL_RSSI_DBM)
    delta_db = best_score - current_score
    fast_override_ok = delta_db >= FAST_OVERRIDE_DB and (
        challenger_packet_count >= 2 or current_area_id not in scores
    )
    switch = fast_override_ok or (
        (now - last_switch) >= MIN_HOLD_SECONDS and delta_db >= HYSTERESIS_DB
    )
    return AreaDecision(best_area_id, best_score, current_score, switch)


def rssi_to_distance_m(
    rssi_dbm: float,
    *,
    ref_power_dbm: float = TX_POWER_1M_DBM,
    attenuation: float = PATH_LOSS_EXPONENT,
) -> float:
    """Estimate distance in metres with a log-distance path-loss model (default TX power -59 dBm at 1 m, n = 2.2)."""
    eff_n = max(1.0, float(attenuation))
    return round(
        max(
            0.2,
            min(
                50.0,
                math.pow(10.0, (float(ref_power_dbm) - float(rssi_dbm)) / (10.0 * eff_n)),
            ),
        ),
        1,
    )


def _continuous_distance_m(norm_dbm: float, attenuation: float) -> float:
    """Unrounded distance in metres for continuous velocity gating."""
    eff_n = max(1.0, float(attenuation))
    return max(
        0.05,
        min(100.0, math.pow(10.0, (TX_POWER_1M_DBM - float(norm_dbm)) / (10.0 * eff_n))),
    )


def _distance_m_to_norm_dbm(dist_m: float, attenuation: float) -> float:
    """Analytical inverse of `_continuous_distance_m` returning normalized 1 m-equivalent dBm."""
    eff_n = max(1.0, float(attenuation))
    return TX_POWER_1M_DBM - (10.0 * eff_n * math.log10(max(0.05, float(dist_m))))


def _get_floor_registry(hass: HomeAssistant) -> Any | None:
    """Return Home Assistant's FloorRegistry when available."""
    try:
        from homeassistant.helpers import floor_registry as fr

        return fr.async_get(hass)
    except Exception:  # noqa: BLE001
        return None


def has_configured_floors(hass: HomeAssistant) -> bool:
    """Return True if Home Assistant has any configured Floor entries or Area floor assignments."""
    floor_reg = _get_floor_registry(hass)
    if floor_reg is not None and hasattr(floor_reg, "async_list_floors"):
        try:
            if list(floor_reg.async_list_floors()):
                return True
        except Exception:  # noqa: BLE001
            pass
    area_reg = ar.async_get(hass)
    return any(
        bool(str(getattr(area, "floor_id", "") or "").strip())
        for area in area_reg.async_list_areas()
    )


def resolve_floor_info(
    hass: HomeAssistant, floor_id: str | None
) -> tuple[str, str]:
    """Return `(clean_floor_id, floor_name)` for a Home Assistant Floor ID, or `("", "")` when unset."""
    clean_id = str(floor_id or "").strip()
    if not clean_id:
        return "", ""
    floor_reg = _get_floor_registry(hass)
    if floor_reg is not None and hasattr(floor_reg, "async_get_floor"):
        try:
            floor_entry = floor_reg.async_get_floor(clean_id)
            if floor_entry is not None:
                fname = str(getattr(floor_entry, "name", "") or "").strip()
                if fname:
                    return clean_id, fname
        except Exception:  # noqa: BLE001
            pass
    humanized = clean_id.replace("_", " ").replace("-", " ").strip().title()
    return clean_id, humanized or clean_id


@dataclass
class ScannerObservationState:
    """Per-scanner rolling 3-sample median, velocity-gated 1D Kalman filter, and signature ring buffer."""

    source: str
    scanner_name: str = ""
    raw_rssi: int = -100
    recent_raw: list[tuple[float, float]] = field(default_factory=list)
    x_dbm: float = -100.0
    p_var: float = KALMAN_MEASUREMENT_VAR
    last_obs_time: float = 0.0
    packet_count: int = 0
    ring_buffer: list[tuple[float, float]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Voice Follows Me Dwell Gate & Beacon Policy
# ---------------------------------------------------------------------------

NON_AREA_STATES: frozenset[str] = frozenset(
    {"", "unknown", "unavailable", "none", "away", "not_home"}
)
_CLOCK_TOLERANCE_S = 0.25

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


def _is_latter_own_area_sensor(
    entry: er.RegistryEntry | None,
    entity_id: str = "",
    state_obj: Any = None,
) -> bool:
    """Return True when `entry`/`entity_id` belongs to Latter itself (never feed back into Area sensor fusion)."""
    if entry is not None:
        return entry.platform == DOMAIN or bool(
            (entry.unique_id or "").startswith("latter_area_")
        )
    if state_obj is not None and "fusion_mode" in getattr(state_obj, "attributes", {}):
        return True
    return entity_id.endswith("_ble_occupancy")


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
                and entry.platform != DOMAIN
                and not (entry.unique_id or "").startswith("latter_area_")
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
                    and entry.platform != DOMAIN
                    and not (entry.unique_id or "").startswith("latter_area_")
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

    for eid in candidate_eids:
        entry = ent_reg.async_get(eid)
        st = hass.states.get(eid)
        if _is_latter_own_area_sensor(entry, eid, st):
            continue
        if entry is not None and (entry.disabled_by or entry.domain != "binary_sensor"):
            continue
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

    ent_reg = er.async_get(hass)
    explicit_eids = [
        str(s).strip()
        for s in (configured_sensors or [])
        if str(s or "").strip().startswith("binary_sensor.")
    ]
    unavailable_sensors: list[str] = []
    if explicit_eids:
        for eid in explicit_eids:
            entry = ent_reg.async_get(eid)
            st = hass.states.get(eid)
            if _is_latter_own_area_sensor(entry, eid, st):
                continue
            if (
                st is None
                or (entry is not None and bool(entry.disabled_by))
                or str(st.state).lower() in ("unavailable", "unknown")
            ) and eid not in unavailable_sensors:
                unavailable_sensors.append(eid)
    else:
        for item in available_sensors:
            eid = str(item.get("entity_id") or "")
            if (
                eid
                and str(item.get("state") or "").lower() in ("unavailable", "unknown")
                and eid not in unavailable_sensors
            ):
                unavailable_sensors.append(eid)

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


# ---------------------------------------------------------------------------
# Shared BLE Scanner Fabric & Native BLE Tracker
# ---------------------------------------------------------------------------

APPLE_COMPANY_ID = 0x004C
MICROSOFT_COMPANY_ID = 0x0006
SAMSUNG_COMPANY_ID = 0x0075
GOOGLE_COMPANY_ID = 0x00E0
RUUVI_COMPANY_ID = 0x0499
SHELLY_COMPANY_ID = 0x0B9A
IBEACON_PREFIX = b"\x02\x15"
_UNMAPPED = "__unmapped__"
SURVEY_RETENTION_SECONDS = 180.0
WAKE_GAP_SECONDS = 8.0
AWAY_CHECK_INTERVAL_SECONDS = 15.0
AWAY_TIMEOUT_SECONDS = 180.0
MATCHED_BLE_ADDRESS_TTL_SECONDS = 900.0


def _safe_rssi_int(val: Any) -> int | None:
    """Coerce raw RSSI to int, rejecting booleans, NaN/Inf, and non-numeric values."""
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, float) and not math.isfinite(val):
        return None
    try:
        return int(val)
    except (TypeError, ValueError, OverflowError):
        return None

_IBEACON_IDENTITY_RE = re.compile(
    r"^(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})"
    r"(?:[-:_](?P<major>\d{1,5})[-:_](?P<minor>\d{1,5}))?$",
    re.IGNORECASE,
)
_IBEACON_ENTITY_PREFIX_RE = re.compile(
    r"^(?P<uuid>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[0-9a-f]{32})"
    r"[-:_](?P<major>\d{1,5})[-:_](?P<minor>\d{1,5})(?:[-_].+)?$",
    re.IGNORECASE,
)
_TRAILING_ROTATING_HEX4_RE = re.compile(r"\s+[0-9A-Fa-f]{4}$")


def _format_uuid_dashed(uuid_hex: str) -> str:
    """Format a 32-char lowercase hex UUID as 8-4-4-4-12 dashed string."""
    clean = _normalize_uuid_hex(uuid_hex)
    if len(clean) != 32:
        return uuid_hex.strip()
    return f"{clean[0:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:32]}"


def _coerce_uint16(val: Any) -> int | None:
    """Return an integer in 0..65535 when `val` is a valid uint16, else None."""
    if val is None or isinstance(val, bool) or val == "":
        return None
    if isinstance(val, float) and not val.is_integer():
        return None
    try:
        parsed = int(val)
    except (TypeError, ValueError):
        return None
    return parsed if 0 <= parsed <= 65535 else None


def parse_ibeacon_identity(
    raw: str, major_attr: Any = None, minor_attr: Any = None
) -> tuple[str, int | None, int | None] | None:
    """Parse `<uuid>[-/:]<major>[-/:]<minor>` or `<uuid>` + optional major/minor attributes."""
    text = str(raw or "").strip()
    if not text:
        return None
    low = text.lower()
    if low.startswith(("eddystone:", "bthome:")):
        return None
    if low.startswith("ibeacon:"):
        text = text[8:].strip()
    match = _IBEACON_IDENTITY_RE.match(text)
    if match is None:
        return None
    uuid_hex = _normalize_uuid_hex(match.group("uuid"))
    if len(uuid_hex) != 32:
        return None
    maj_grp = match.group("major")
    min_grp = match.group("minor")
    if maj_grp is not None or min_grp is not None:
        maj = _coerce_uint16(maj_grp)
        min_ = _coerce_uint16(min_grp)
        if maj is None or min_ is None:
            return None
        return uuid_hex, maj, min_
    return uuid_hex, _coerce_uint16(major_attr), _coerce_uint16(minor_attr)


def _extract_uuid16(raw_uuid: str) -> str:
    """Extract lowercase 4-hex Bluetooth SIG 16-bit UUID from 16/32/128-bit representations."""
    u = str(raw_uuid or "").strip().lower()
    if u.startswith("0x"):
        u = u[2:]
    if len(u) == 4 and all(ch in "0123456789abcdef" for ch in u):
        return u
    if (
        len(u) >= 8
        and u.startswith("0000")
        and (len(u) == 8 or u[8] == "-")
        and all(ch in "0123456789abcdef" for ch in u[4:8])
    ):
        return u[4:8]
    return ""


def _normalize_mfg_map(mfg_data: Mapping[int, bytes] | None) -> dict[int, bytes]:
    """Normalize manufacturer_data dictionary keys to int and payloads to bytes."""
    out: dict[int, bytes] = {}
    for raw_k, raw_v in (mfg_data or {}).items():
        if not isinstance(raw_v, (bytes, bytearray)):
            continue
        try:
            cid = int(raw_k, 0) if isinstance(raw_k, str) else int(raw_k)
        except (TypeError, ValueError):
            continue
        out[cid] = bytes(raw_v)
    return out


def classify_ble_advertisement_kind(
    local_name: str,
    mfg_data: Mapping[int, bytes],
    service_data: Mapping[str, bytes],
    service_uuids: Iterable[str],
    *,
    is_private_ble: bool = False,
) -> str:
    """Classify a BLE advertisement into a friendly vendor/device-type or local tag label."""
    mfg_map = _normalize_mfg_map(mfg_data)
    svc_data_keys = [str(k or "").strip().lower() for k in (service_data or {})]
    svc_uuid_list = [str(u or "").strip().lower() for u in (service_uuids or ())]
    svc_all_16 = {
        u16
        for raw_u in (*svc_data_keys, *svc_uuid_list)
        if (u16 := _extract_uuid16(raw_u))
    }

    if is_private_ble:
        if APPLE_COMPANY_ID in mfg_map:
            apple_payload = mfg_map[APPLE_COMPANY_ID]
            if len(apple_payload) >= 1 and apple_payload[0] == 0x07:
                return "Apple AirPods or Beats (Private BLE)"
            return "Apple iPhone, Watch, or iPad (Private BLE)"
        if SAMSUNG_COMPANY_ID in mfg_map:
            return "Samsung Galaxy Phone or Watch (Private BLE)"
        if (
            GOOGLE_COMPANY_ID in mfg_map
            or "fe2c" in svc_all_16
            or any("fe2c" in raw_u for raw_u in (*svc_data_keys, *svc_uuid_list))
        ):
            return "Android / Pixel Phone (Private BLE)"
        if MICROSOFT_COMPANY_ID in mfg_map:
            return "Windows PC or Surface (Private BLE)"
        return "Phone or Watch (Private BLE / IRK)"

    name_low = str(local_name or "").strip().lower()
    if "feed" in svc_all_16 or name_low.startswith("tile"):
        return "Tile Tracker"
    if name_low.startswith("itag") or ("ffe0" in svc_all_16 and "tag" in name_low):
        return "iTag Keychain Tag"
    if "fcd2" in svc_all_16:
        if SHELLY_COMPANY_ID in mfg_map or name_low.startswith(
            ("shelly", "sbbt", "sbdw", "sbmv", "sbht")
        ):
            return "Shelly BLU Tag (BTHome v2)"
        return "BTHome v2 Tag"
    if RUUVI_COMPANY_ID in mfg_map or name_low.startswith("ruuvi"):
        return "RuuviTag Beacon"
    for raw_k, raw_v in (service_data or {}).items():
        if (
            _extract_uuid16(str(raw_k)) == "feaa"
            and isinstance(raw_v, (bytes, bytearray))
            and len(raw_v) >= 1
            and (raw_v[0] & 0xF0) == 0x00
        ):
            return "Eddystone-UID Beacon"

    if APPLE_COMPANY_ID in mfg_map:
        return "Named BLE device (Apple)"
    if SAMSUNG_COMPANY_ID in mfg_map:
        return "Named BLE device (Samsung)"
    if MICROSOFT_COMPANY_ID in mfg_map:
        return "Named BLE device (Windows PC)"
    if GOOGLE_COMPANY_ID in mfg_map:
        return "Named BLE device (Google)"
    return "Named BLE device"


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
        return str(dev.area_id)

    for entry in er.async_entries_for_device(ent_reg, dev.id):
        if entry.area_id:
            return str(entry.area_id)

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
                return str(area.id)

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

        scanner = bluetooth.async_scanner_by_source(
            hass, scanner_source
        ) or bluetooth.async_scanner_by_source(hass, scanner_source.upper())
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
                return str(area.id)

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


def get_ble_signature_area_ids(hass: HomeAssistant) -> set[str]:
    """Return Home Assistant area_ids that have a learned multi-scanner BLE signature."""
    domain_data = hass.data.get(DOMAIN, {})
    global_cfg = (
        domain_data.get(DATA_GLOBAL_CONFIG, {}) if isinstance(domain_data, dict) else {}
    )
    raw_sigs = (
        global_cfg.get(CONF_BLE_AREA_SIGNATURES, {})
        if isinstance(global_cfg, dict)
        else {}
    )
    if not isinstance(raw_sigs, dict):
        return set()
    return {
        str(area_id)
        for area_id, sig in raw_sigs.items()
        if area_id
        and isinstance(sig, dict)
        and isinstance(sig.get("scanners"), dict)
        and bool(sig["scanners"])
    }


def get_area_signatures_summary(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return learned BLE signature status for every Area in Home Assistant sorted by Area name."""
    area_reg = ar.async_get(hass)
    proxy_areas = get_ble_proxy_area_ids(hass)
    domain_data = hass.data.get(DOMAIN, {})
    global_cfg = (
        domain_data.get(DATA_GLOBAL_CONFIG, {}) if isinstance(domain_data, dict) else {}
    )
    raw_sigs = (
        global_cfg.get(CONF_BLE_AREA_SIGNATURES, {})
        if isinstance(global_cfg, dict)
        else {}
    )
    sig_map = raw_sigs if isinstance(raw_sigs, dict) else {}

    rows: list[dict[str, Any]] = []
    for area in sorted(area_reg.async_list_areas(), key=lambda a: a.name.lower()):
        sig = sig_map.get(area.id)
        raw_scanners = sig.get("scanners") if isinstance(sig, dict) else None
        scanners_dict: dict[str, Any] = (
            raw_scanners if isinstance(raw_scanners, dict) else {}
        )
        has_sig = len(scanners_dict) > 0
        sample_count = (
            int(
                sig.get("sample_count")
                or sum(
                    int(v.get("n", 1))
                    for v in scanners_dict.values()
                    if isinstance(v, dict)
                )
            )
            if (has_sig and isinstance(sig, dict))
            else 0
        )
        captured_at = (
            str(sig.get("captured_at") or "")
            if (has_sig and isinstance(sig, dict))
            else ""
        )
        rows.append(
            {
                "area_id": area.id,
                "area_name": area.name,
                "floor_id": str(getattr(area, "floor_id", "") or ""),
                "has_ble_proxy": area.id in proxy_areas,
                "has_signature": has_sig,
                "scanner_count": len(scanners_dict) if has_sig else 0,
                "sample_count": sample_count,
                "captured_at": captured_at,
            }
        )
    return rows


def _extract_adv_ref_power_dbm(
    service_info: object | None,
    mfg_data: Mapping[int, bytes],
    service_data: Mapping[str, bytes],
) -> float | None:
    """Extract calibrated 1 m reference RSSI (dBm) from iBeacon, Eddystone, or advertisement TX power."""
    apple_bytes = mfg_data.get(APPLE_COMPANY_ID)
    if apple_bytes and len(apple_bytes) >= 23 and apple_bytes[:2] == IBEACON_PREFIX:
        raw_b = apple_bytes[22]
        val = raw_b - 256 if raw_b >= 128 else raw_b
        if -90 <= val <= -30:
            return float(val)

    for svc_key, payload in service_data.items():
        k_low = str(svc_key).lower()
        if (
            (k_low.startswith(EDDYSTONE_UUID_PREFIX) or k_low == "feaa")
            and isinstance(payload, (bytes, bytearray))
            and len(payload) >= 2
            and (payload[0] & 0xF0) in (0x00, 0x10, 0x30)
        ):
            raw_b = payload[1]
            tx_0m = raw_b - 256 if raw_b >= 128 else raw_b
            val_1m = tx_0m - 41
            if -90 <= val_1m <= -30:
                return float(val_1m)

    if service_info is not None:
        tx_p = getattr(service_info, "tx_power", None)
        if isinstance(tx_p, (int, float)) and not isinstance(tx_p, bool):
            tx_f = float(tx_p)
            if -90.0 <= tx_f <= -30.0:
                return tx_f
            if -20.0 <= tx_f <= 20.0:
                val_1m_f = tx_f - 59.0
                if -90.0 <= val_1m_f <= -30.0:
                    return val_1m_f
    return None


class LatterNativeBleTracker:
    """Multi-scanner BLE spatial positioning tracker with 3-sample median, velocity-gated Kalman filter, and vector signatures."""

    def __init__(
        self,
        hass: HomeAssistant,
        beacon_uuid: str,
        device_slug: str,
        on_area_detected: Callable[[str, str], None],
        scanner_offsets: Mapping[str, float] | None = None,
        area_signatures: Mapping[str, Mapping[str, Any]] | None = None,
        ref_power_dbm: int | float | str | None = None,
        attenuation: float = DEFAULT_BLE_ATTENUATION,
        max_radius_m: float = DEFAULT_BLE_MAX_RADIUS_M,
        max_velocity_mps: float = DEFAULT_BLE_MAX_VELOCITY_MPS,
        away_timeout_s: float = float(DEFAULT_BLE_AWAY_TIMEOUT_S),
        target_address: str = "",
        esphome_device_id: str | None = None,
        manifest_beacon: dict[str, Any] | None = None,
        should_hold_during_ble_sleep: Callable[[], bool] | None = None,
        initial_matched_addresses: Iterable[str] | None = None,
        on_address_matched: Callable[[str], None] | None = None,
    ) -> None:
        """Initialize the native BLE spatial positioning tracker."""
        self.hass = hass
        self.beacon_uuid = str(beacon_uuid or "").strip()
        self._target_uuid_hex = _normalize_uuid_hex(beacon_uuid)
        self._explicit_major: int | None = None
        self._explicit_minor: int | None = None
        self._target_eddystone_namespace_hex: str = ""
        self._target_address = str(target_address or "").strip()
        self.target_address = self._target_address
        self._raw_slug = device_slug
        self._esphome_device_id: str | None = esphome_device_id
        self._manifest_beacon: dict[str, Any] = (
            dict(manifest_beacon) if isinstance(manifest_beacon, dict) else {}
        )
        self._should_hold_during_ble_sleep = should_hold_during_ble_sleep
        self._on_address_matched = on_address_matched
        self._on_area_detected = on_area_detected

        self._scanner_offsets: dict[str, float] = {}
        self._area_signatures: dict[str, dict[str, Any]] = {}
        self._configured_ref_power_dbm: float | None = None
        self._entity_ref_power_dbm: float | None = None
        self.detected_ref_power_dbm: float | None = None
        self._attenuation: float = float(DEFAULT_BLE_ATTENUATION)
        self._max_radius_m: float = float(DEFAULT_BLE_MAX_RADIUS_M)
        self._max_velocity_mps: float = float(DEFAULT_BLE_MAX_VELOCITY_MPS)
        self._away_timeout_s: float = float(DEFAULT_BLE_AWAY_TIMEOUT_S)

        self._scanner_states: dict[str, ScannerObservationState] = {}
        self._area_rssi: dict[str, tuple[float, float]] = {}
        self._area_raw_rssi: dict[str, tuple[float, float, str]] = {}
        self._unmapped_rssi: dict[str, tuple[int, float]] = {}
        self._scanner_area_cache: dict[str, str | None] = {}
        self._last_adv_ts_by_scanner: dict[str, float] = {}
        self._target_mac_ints: set[int] = set()
        self._dynamic_target_mac_int: int | None = None
        self._dynamic_target_mac_str: str = ""
        self._last_mac_discovery_mono: float = 0.0
        self._matched_ble_addresses: dict[str, float] = {}
        now_init = time.monotonic()
        if not ("." in self._target_address and not self._esphome_device_id):
            for raw_addr in initial_matched_addresses or ():
                norm_init = str(raw_addr or "").strip().upper()
                if _mac_to_int(norm_init) is not None and len(self._matched_ble_addresses) < 64:
                    self._matched_ble_addresses[norm_init] = now_init
        self.current_area_id: str | None = None
        self._awaiting_fresh_wake_lock: bool = False
        self._wake_coalesce_until: float = 0.0
        self._unsub_wake_coalesce: Callable[[], None] | None = None
        self._unsub_target_entity: Callable[[], None] | None = None
        self.closest_scanner: str = ""
        self.match_method: str = ""
        self.packets_seen: int = 0
        self.last_packet_monotonic: float = 0.0
        self._started_monotonic: float = now_init
        self._ble_wake_monotonic: float = 0.0
        self._last_switch_monotonic: float = 0.0
        self.is_away: bool = False
        self.winning_rssi: int | None = None
        self.winning_raw_rssi: int | None = None
        self.winning_distance_m: float | None = None
        self.winning_distance_ft: float | None = None

        self.configure_spatial_engine(
            scanner_offsets=scanner_offsets,
            area_signatures=area_signatures,
            ref_power_dbm=ref_power_dbm,
            attenuation=attenuation,
            max_radius_m=max_radius_m,
            max_velocity_mps=max_velocity_mps,
            away_timeout_s=away_timeout_s,
            re_evaluate=False,
        )
        self._seed_explicit_target_address(sync_fabric=False)

    @property
    def effective_ref_power_dbm(self) -> float:
        """Return configured 1 m reference power, entity-derived TX power, advertisement power, or -59.0 dBm."""
        if self._configured_ref_power_dbm is not None:
            return float(self._configured_ref_power_dbm)
        if self._entity_ref_power_dbm is not None:
            return float(self._entity_ref_power_dbm)
        if self.detected_ref_power_dbm is not None:
            return float(self.detected_ref_power_dbm)
        return TX_POWER_1M_DBM

    def _get_scanner_offset(self, scanner_source: str) -> float:
        """Return calibrated dB offset for normalized `scanner_source`."""
        return float(self._scanner_offsets.get(scanner_source.strip().upper(), 0.0))

    @callback
    def configure_spatial_engine(
        self,
        *,
        scanner_offsets: Mapping[str, float] | None = None,
        area_signatures: Mapping[str, Mapping[str, Any]] | None = None,
        ref_power_dbm: int | float | str | None = None,
        attenuation: float = DEFAULT_BLE_ATTENUATION,
        max_radius_m: float = DEFAULT_BLE_MAX_RADIUS_M,
        max_velocity_mps: float = DEFAULT_BLE_MAX_VELOCITY_MPS,
        away_timeout_s: float = float(DEFAULT_BLE_AWAY_TIMEOUT_S),
        re_evaluate: bool = True,
    ) -> None:
        """Update per-scanner offsets, vector signatures, reference power, and System RF parameters live."""
        if scanner_offsets is not None:
            cleaned_offsets: dict[str, float] = {}
            for k, v in scanner_offsets.items():
                src_key = str(k or "").strip().upper()
                if not src_key:
                    continue
                try:
                    cleaned_offsets[src_key] = max(-25.0, min(25.0, float(v)))
                except (TypeError, ValueError):
                    pass
            self._scanner_offsets = cleaned_offsets

        if area_signatures is not None:
            cleaned_sigs: dict[str, dict[str, Any]] = {}
            for area_id, sig in area_signatures.items():
                if not area_id or not isinstance(sig, Mapping):
                    continue
                raw_sc = sig.get("scanners")
                if not isinstance(raw_sc, Mapping) or not raw_sc:
                    continue
                norm_sc: dict[str, dict[str, float | int]] = {}
                for src, stats in raw_sc.items():
                    s_key = str(src or "").strip().upper()
                    if not s_key or not isinstance(stats, Mapping):
                        continue
                    try:
                        norm_sc[s_key] = {
                            "mean": float(stats.get("mean", -75.0)),
                            "std": max(2.5, float(stats.get("std", 3.5))),
                            "n": max(1, int(stats.get("n", 1))),
                        }
                    except (TypeError, ValueError):
                        pass
                if norm_sc:
                    cleaned_sigs[str(area_id)] = {
                        "scanners": norm_sc,
                        "captured_at": str(sig.get("captured_at") or ""),
                        "sample_count": int(sig.get("sample_count") or len(norm_sc)),
                    }
            self._area_signatures = cleaned_sigs

        if ref_power_dbm is None or ref_power_dbm == "":
            self._configured_ref_power_dbm = None
        else:
            try:
                self._configured_ref_power_dbm = max(
                    -90.0, min(-30.0, float(ref_power_dbm))
                )
            except (TypeError, ValueError):
                self._configured_ref_power_dbm = None

        try:
            self._attenuation = max(1.5, min(4.5, float(attenuation)))
        except (TypeError, ValueError):
            self._attenuation = float(DEFAULT_BLE_ATTENUATION)
        try:
            self._max_radius_m = max(2.0, min(50.0, float(max_radius_m)))
        except (TypeError, ValueError):
            self._max_radius_m = float(DEFAULT_BLE_MAX_RADIUS_M)
        try:
            self._max_velocity_mps = max(0.5, min(15.0, float(max_velocity_mps)))
        except (TypeError, ValueError):
            self._max_velocity_mps = float(DEFAULT_BLE_MAX_VELOCITY_MPS)
        try:
            self._away_timeout_s = max(30.0, min(900.0, float(away_timeout_s)))
        except (TypeError, ValueError):
            self._away_timeout_s = float(DEFAULT_BLE_AWAY_TIMEOUT_S)

        if re_evaluate and self._scanner_states:
            self._evaluate_best_area(time.monotonic())

    @callback
    def set_scanner_offsets(self, offsets: Mapping[str, float] | None) -> None:
        """Update per-scanner RSSI calibration offsets (dB bias) in real time and re-evaluate."""
        self.configure_spatial_engine(
            scanner_offsets=offsets or {},
            area_signatures=self._area_signatures,
            ref_power_dbm=self._configured_ref_power_dbm,
            attenuation=self._attenuation,
            max_radius_m=self._max_radius_m,
            max_velocity_mps=self._max_velocity_mps,
            away_timeout_s=self._away_timeout_s,
            re_evaluate=True,
        )

    @callback
    def set_area_signatures(
        self, signatures: Mapping[str, Mapping[str, Any]] | None
    ) -> None:
        """Update multi-scanner Area signatures in real time and re-evaluate."""
        self.configure_spatial_engine(
            scanner_offsets=self._scanner_offsets,
            area_signatures=signatures or {},
            ref_power_dbm=self._configured_ref_power_dbm,
            attenuation=self._attenuation,
            max_radius_m=self._max_radius_m,
            max_velocity_mps=self._max_velocity_mps,
            away_timeout_s=self._away_timeout_s,
            re_evaluate=True,
        )

    @callback
    def set_ref_power(self, ref_power_dbm: int | float | None) -> None:
        """Update configured 1 m reference power (`None` = auto-detect) and re-evaluate."""
        self.configure_spatial_engine(
            scanner_offsets=self._scanner_offsets,
            area_signatures=self._area_signatures,
            ref_power_dbm=ref_power_dbm,
            attenuation=self._attenuation,
            max_radius_m=self._max_radius_m,
            max_velocity_mps=self._max_velocity_mps,
            away_timeout_s=self._away_timeout_s,
            re_evaluate=True,
        )

    @callback
    def _cancel_wake_coalesce_timer(self) -> None:
        """Cancel any pending post-wake multi-proxy settlement timer."""
        if self._unsub_wake_coalesce is not None:
            self._unsub_wake_coalesce()
            self._unsub_wake_coalesce = None

    @callback
    def _async_on_wake_coalesce_timer(self, _now: Any = None) -> None:
        """Commit deferred post-wake Area switch if no local proxy corroborated the sticky Area."""
        self._unsub_wake_coalesce = None
        self._wake_coalesce_until = 0.0
        eval_now = max(time.monotonic(), self.last_packet_monotonic)
        self._evaluate_best_area(eval_now)

    def _area_has_registered_scanner(self, area_id: str | None) -> bool:
        """Return True if `area_id` currently has at least one registered Bluetooth scanner in HA."""
        if not area_id:
            return False
        return area_id in get_ble_proxy_area_ids(self.hass)

    @callback
    def _record_matched_ble_address(
        self, addr: str, *, seed_scanners: bool = True
    ) -> None:
        """Record a matched BLE address with a monotonic timestamp, bounding cache to 64 entries."""
        norm = str(addr or "").strip().upper()
        if not norm:
            return
        if (
            "." in self._target_address
            and not self._esphome_device_id
            and self._dynamic_target_mac_str
            and norm != self._dynamic_target_mac_str
        ):
            return
        is_new = norm not in self._matched_ble_addresses
        now_mono = time.monotonic()
        self._matched_ble_addresses[norm] = now_mono
        evicted = self._prune_expired_matched_ble_addresses(now_mono)
        if len(self._matched_ble_addresses) > 64:
            oldest = min(
                self._matched_ble_addresses,
                key=lambda k: self._matched_ble_addresses[k],
            )
            self._matched_ble_addresses.pop(oldest, None)
            evicted = True
        if is_new and self._on_address_matched is not None:
            self._on_address_matched(norm)
        if is_new or evicted:
            fabric = get_ble_fabric(self.hass)
            fabric.sync_tracker_addresses()
            if is_new and seed_scanners and self in fabric._trackers:
                fabric._async_seed_tracker_from_scanners_once(
                    self, only_address=norm
                )

    @callback
    def _prune_expired_matched_ble_addresses(self, now_mono: float) -> bool:
        """Evict expired rotating BLE addresses (RPAs) after TTL while retaining bound ESPHome / static MACs."""
        if self._esphome_device_id or not self._matched_ble_addresses:
            return False
        evicted = False
        for addr, ts in list(self._matched_ble_addresses.items()):
            if (now_mono - ts) <= MATCHED_BLE_ADDRESS_TTL_SECONDS:
                continue
            if self._dynamic_target_mac_str and addr == self._dynamic_target_mac_str:
                continue
            addr_int = _mac_to_int(addr)
            if addr_int is not None and addr_int in self._target_mac_ints:
                continue
            self._matched_ble_addresses.pop(addr, None)
            evicted = True
        return evicted

    @property
    def matched_ble_addresses(self) -> list[str]:
        """Return up to 8 most-recently matched BLE addresses for runtime persistence."""
        return sorted(
            self._matched_ble_addresses,
            key=lambda k: self._matched_ble_addresses[k],
            reverse=True,
        )[:8]

    @callback
    def _apply_dynamic_entity_mac(
        self, raw_mac: str, *, sync_fabric: bool = True
    ) -> None:
        """Update `_dynamic_target_mac_int` and evict rotated RPAs in O(1)."""
        c_int = _mac_to_int(raw_mac)
        if c_int is None:
            return
        formatted = _int_to_mac(c_int)
        prev_str = self._dynamic_target_mac_str
        changed = self._dynamic_target_mac_int != c_int or formatted not in self._matched_ble_addresses
        self._dynamic_target_mac_int = c_int
        self._dynamic_target_mac_str = formatted
        if prev_str and prev_str != formatted:
            self._matched_ble_addresses.pop(prev_str, None)
        if not self._esphome_device_id:
            for stale_k in list(self._matched_ble_addresses):
                if stale_k != formatted:
                    self._matched_ble_addresses.pop(stale_k, None)
        self._matched_ble_addresses[formatted] = time.monotonic()
        if changed and self._on_address_matched is not None:
            self._on_address_matched(formatted)
        if sync_fabric and changed:
            fabric = get_ble_fabric(self.hass)
            if self in fabric._trackers:
                fabric.sync_tracker_addresses()
                fabric._async_seed_tracker_from_scanners_once(self)

    @callback
    def _async_on_target_entity_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """React in 0 ms when a tracked `private_ble_device`, `mobile_app`, or `ibeacon` entity updates."""
        new_st = event.data.get("new_state")
        if new_st is None:
            return
        self._seed_explicit_target_address(sync_fabric=True)

    @callback
    def _seed_explicit_target_address(self, *, sync_fabric: bool = True) -> None:
        """Seed MAC, iBeacon/Eddystone UID, Companion App UUID-Major-Minor, or dynamic RPA from `_target_address`."""
        t_addr = self._target_address
        if not t_addr:
            return
        m_int = _mac_to_int(t_addr)
        if m_int is not None:
            self._target_mac_ints.add(m_int)
            self._record_matched_ble_address(_int_to_mac(m_int), seed_scanners=sync_fabric)
            return
        if "." in t_addr:
            st = self.hass.states.get(t_addr)
            ent_entry = er.async_get(self.hass).async_get(t_addr)
            prev_ib = (
                self._target_uuid_hex,
                self._explicit_major,
                self._explicit_minor,
            )
            prev_ent_ref = self._entity_ref_power_dbm
            parsed_ib: tuple[str, int | None, int | None] | None = None
            cur_mac = ""
            if st is not None:
                cur_mac = str(
                    st.attributes.get("current_address")
                    or st.attributes.get("mac")
                    or st.attributes.get("address")
                    or ""
                ).strip()
                raw_id = str(
                    st.attributes.get("id") or st.attributes.get("uuid") or ""
                ).strip()
                if raw_id:
                    parsed_ib = parse_ibeacon_identity(
                        raw_id,
                        st.attributes.get("major"),
                        st.attributes.get("minor"),
                    )
                mp_raw = (
                    st.attributes.get("Measured power")
                    if st.attributes.get("Measured power") is not None
                    else st.attributes.get("measured_power")
                )
                tx_lvl = (
                    st.attributes.get("Transmitting power")
                    if st.attributes.get("Transmitting power") is not None
                    else st.attributes.get("transmitting_power")
                )
                ent_ref = resolve_companion_tx_ref_power_dbm(mp_raw, tx_lvl)
                if ent_ref is not None:
                    self._entity_ref_power_dbm = ent_ref
                    self.detected_ref_power_dbm = ent_ref
            if (
                parsed_ib is None
                and ent_entry is not None
                and ent_entry.platform == "ibeacon"
            ):
                parsed_ib = _extract_ibeacon_entity_identity(
                    self.hass, ent_entry, st
                )
            if parsed_ib is not None:
                (
                    self._target_uuid_hex,
                    self._explicit_major,
                    self._explicit_minor,
                ) = parsed_ib

            is_beacon_entity = parsed_ib is not None or (
                ent_entry is not None
                and ent_entry.platform in ("mobile_app", "ibeacon")
            )
            if (
                not cur_mac
                and not is_beacon_entity
                and ent_entry is not None
                and ent_entry.device_id
            ):
                dev_entry = dr.async_get(self.hass).async_get(ent_entry.device_id)
                if dev_entry is not None:
                    for _ct, cv in dev_entry.connections:
                        if _mac_to_int(str(cv)) is not None:
                            cur_mac = str(cv)
                            break
                    if not cur_mac:
                        for _dom, iv in dev_entry.identifiers:
                            if _mac_to_int(str(iv)) is not None:
                                cur_mac = str(iv)
                                break
            if cur_mac:
                self._apply_dynamic_entity_mac(cur_mac, sync_fabric=sync_fabric)
            elif (
                not self._esphome_device_id
                and (
                    self._target_uuid_hex,
                    self._explicit_major,
                    self._explicit_minor,
                )
                != prev_ib
            ):
                self._matched_ble_addresses.clear()
                if sync_fabric:
                    fabric = get_ble_fabric(self.hass)
                    if self in fabric._trackers:
                        fabric.sync_tracker_addresses()
                        fabric._async_seed_tracker_from_scanners_once(self)
            if (
                sync_fabric
                and self._entity_ref_power_dbm != prev_ent_ref
                and self._scanner_states
            ):
                self._evaluate_best_area(time.monotonic())
            return

        stripped = t_addr.strip()
        if not stripped.lower().startswith(("eddystone:", "bthome:")):
            parsed_direct = parse_ibeacon_identity(stripped)
            if parsed_direct is not None:
                (
                    self._target_uuid_hex,
                    self._explicit_major,
                    self._explicit_minor,
                ) = parsed_direct
                return
        for prefix in ("eddystone:", "ibeacon:", "bthome:"):
            if stripped.lower().startswith(prefix):
                stripped = stripped[len(prefix) :].strip()
                break
        hex_only = re.sub(r"[^0-9a-f]", "", stripped.lower())
        if len(hex_only) == 32:
            self._target_uuid_hex = hex_only
            return
        if len(hex_only) == 20:
            self._target_eddystone_namespace_hex = hex_only
            return
        norm_u = _normalize_uuid_hex(stripped.split(":", 1)[0])
        if len(norm_u) == 32:
            self._target_uuid_hex = norm_u
        elif len(norm_u) == 20:
            self._target_eddystone_namespace_hex = norm_u

    @callback
    def check_away_timeout(self, now_mono: float) -> None:
        """Transition tracker to Away if no BLE packet has been received within the configured away timeout."""
        self._seed_explicit_target_address()
        if self._prune_expired_matched_ble_addresses(now_mono):
            get_ble_fabric(self.hass).sync_tracker_addresses()
        ref_mono = max(
            self.last_packet_monotonic
            if self.last_packet_monotonic > 0.0
            else self._started_monotonic,
            self._ble_wake_monotonic,
        )
        if (
            not self.is_away
            and ref_mono > 0.0
            and (now_mono - ref_mono) >= self._away_timeout_s
        ):
            if (
                self._should_hold_during_ble_sleep is not None
                and self._should_hold_during_ble_sleep()
            ):
                return
            self._cancel_wake_coalesce_timer()
            self.is_away = True
            self.current_area_id = None
            self.match_method = ""
            self._awaiting_fresh_wake_lock = False
            self.winning_rssi = None
            self.winning_raw_rssi = None
            self.winning_distance_m = None
            self.winning_distance_ft = None
            self._on_area_detected("away", "")
            get_ble_fabric(self.hass).notify_occupancy_listeners()

    @callback
    def note_ble_radio_active(self, now_mono: float | None = None) -> None:
        """Grant a fresh away-timeout window and re-seed scanner addresses when BLE advertising resumes."""
        now = now_mono if now_mono is not None else time.monotonic()
        self._ble_wake_monotonic = now
        was_away = self.is_away
        if was_away:
            self.is_away = False
        fabric = get_ble_fabric(self.hass)
        if not self._matched_ble_addresses:
            fabric._async_seed_tracker_from_scanners_once(self)
        fabric.sync_tracker_addresses()
        if was_away:
            fabric.notify_occupancy_listeners()

    @callback
    def update_manifest_beacon(self, beacon: dict[str, Any] | None) -> None:
        """Update cached hardware manifest beacon metadata (uuid, major, minor, ref_power) from device_hello."""
        if isinstance(beacon, dict):
            prev_beacon = dict(self._manifest_beacon)
            prev_uuid = self._target_uuid_hex
            self._manifest_beacon = dict(beacon)
            for p_key in ("ref_power", "tx_power_1m", "measured_power"):
                raw_rp = beacon.get(p_key)
                if isinstance(raw_rp, (int, float)) and -90 <= float(raw_rp) <= -30:
                    self.detected_ref_power_dbm = float(raw_rp)
                    break
            u_raw = str(beacon.get("uuid") or "").strip()
            norm_u = _normalize_uuid_hex(u_raw)
            default_u = _normalize_uuid_hex(DEFAULT_BLE_BEACON_UUID)
            if (
                len(norm_u) == 32
                and not self._target_address
                and (not self._target_uuid_hex or norm_u != default_u)
            ):
                self._target_uuid_hex = norm_u
            if (
                self._manifest_beacon != prev_beacon
                or self._target_uuid_hex != prev_uuid
                or not self._matched_ble_addresses
            ):
                fabric = get_ble_fabric(self.hass)
                if self in fabric._trackers:
                    fabric._async_seed_tracker_from_scanners_once(self)

    def _resolve_beacon_major_minor(self) -> tuple[int | None, int | None]:
        """Return expected iBeacon (major, minor) IDs from explicit target config or hardware manifest."""
        if self._explicit_major is not None or self._explicit_minor is not None:
            return self._explicit_major, self._explicit_minor
        beacon_cfg = self._manifest_beacon
        if not beacon_cfg:
            hw = read_device_hardware_manifest(self.hass, self._esphome_device_id)
            if isinstance(hw.get("beacon"), dict):
                beacon_cfg = hw["beacon"]
                self._manifest_beacon = dict(beacon_cfg)
            elif hw.get("minor") is not None:
                beacon_cfg = {"major": hw.get("major", 1), "minor": hw["minor"]}
                self._manifest_beacon = dict(beacon_cfg)
        major_val: int | None = None
        minor_val: int | None = None
        if isinstance(beacon_cfg, dict):
            if beacon_cfg.get("major") is not None:
                major_val = _coerce_uint16(beacon_cfg["major"])
            if beacon_cfg.get("minor") is not None:
                minor_val = _coerce_uint16(beacon_cfg["minor"])
        return major_val, minor_val

    @property
    def target_macs_formatted(self) -> list[str]:
        """Return candidate Wi-Fi/BLE MAC addresses for the target ESPHome device or dynamic RPA."""
        macs = {_int_to_mac(m) for m in self._target_mac_ints}
        if self._dynamic_target_mac_int is not None:
            macs.add(_int_to_mac(self._dynamic_target_mac_int))
        return sorted(macs)

    @callback
    def reset_for_device_wake(self) -> None:
        """Clear stale RSSI history on wake while preserving sticky current_area_id until fresh BLE lock."""
        now = time.monotonic()
        self._ble_wake_monotonic = now
        was_away = self.is_away
        if was_away:
            self.is_away = False
        if self.last_packet_monotonic > 0.0 and (now - self.last_packet_monotonic) < 6.0:
            if was_away:
                get_ble_fabric(self.hass).notify_occupancy_listeners()
            return
        self._cancel_wake_coalesce_timer()
        fabric = get_ble_fabric(self.hass)
        self._scanner_states.clear()
        self._area_rssi.clear()
        self._area_raw_rssi.clear()
        self._unmapped_rssi.clear()
        self._scanner_area_cache.clear()
        fabric._scanner_area_cache.clear()
        self._last_adv_ts_by_scanner.clear()
        self._awaiting_fresh_wake_lock = True
        self._wake_coalesce_until = (
            now + WAKE_COALESCE_SECONDS if self.current_area_id else 0.0
        )
        self._last_switch_monotonic = 0.0
        if self._esphome_device_id:
            self._target_mac_ints = _discover_target_device_macs(
                self.hass, self._esphome_device_id
            )
        self._seed_explicit_target_address(sync_fabric=False)
        if not self._matched_ble_addresses:
            fabric._async_seed_tracker_from_scanners_once(self)
        fabric.sync_tracker_addresses()
        if was_away:
            fabric.notify_occupancy_listeners()

    @callback
    def async_start(self) -> None:
        """Register this tracker with the singleton LatterBleFabric and bind dynamic RPA state listener."""
        self.async_stop()
        self._started_monotonic = time.monotonic()
        if self._esphome_device_id:
            self._target_mac_ints = _discover_target_device_macs(
                self.hass, self._esphome_device_id
            )
        self._seed_explicit_target_address(sync_fabric=False)
        if "." in self._target_address:
            self._unsub_target_entity = async_track_state_change_event(
                self.hass,
                [self._target_address],
                self._async_on_target_entity_state_change,
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
        """Unregister this tracker from the singleton LatterBleFabric and cancel all timers/listeners."""
        self._cancel_wake_coalesce_timer()
        if self._unsub_target_entity is not None:
            self._unsub_target_entity()
            self._unsub_target_entity = None
        fabric = get_ble_fabric(self.hass)
        fabric.unregister_tracker(self)
        self._scanner_states.clear()
        self._area_rssi.clear()
        self._area_raw_rssi.clear()
        self._unmapped_rssi.clear()
        self._scanner_area_cache.clear()
        self._last_adv_ts_by_scanner.clear()

    def _resolve_scanner_display_name(
        self, scanner_source: str, registered_names: Mapping[str, str]
    ) -> str:
        """Resolve a human-readable Bluetooth proxy/scanner name."""
        norm = scanner_source.strip().upper()
        if registered_names.get(norm):
            return registered_names[norm]
        st = self._scanner_states.get(norm)
        if st is not None and st.scanner_name and st.scanner_name.upper() != norm:
            return st.scanner_name
        src_int = _mac_to_int(norm)
        if src_int is not None:
            for dev in _iter_devices(dr.async_get(self.hass)):
                for _ct, cv in dev.connections:
                    c_int = _mac_to_int(str(cv))
                    if c_int is not None and abs(src_int - c_int) <= 2:
                        lbl = str(dev.name_by_user or dev.name or "").strip()
                        if lbl:
                            return lbl
        return norm

    def get_scanner_calibration_telemetry(self) -> list[dict[str, Any]]:
        """Return per-scanner BLE calibration and site survey telemetry across all known proxies."""
        area_reg = ar.async_get(self.hass)
        now = time.monotonic()

        registered_names: dict[str, str] = {}
        try:
            from homeassistant.components import bluetooth

            for scanner in bluetooth.async_current_scanners(self.hass):
                raw_src = str(getattr(scanner, "source", "") or "").strip()
                if not raw_src:
                    continue
                norm_src = raw_src.upper()
                registered_names[norm_src] = str(
                    getattr(scanner, "name", "") or raw_src
                ).strip()
        except Exception:  # noqa: BLE001
            pass

        all_sources = (
            set(registered_names.keys())
            | set(self._scanner_states.keys())
            | set(self._unmapped_rssi.keys())
            | set(self._scanner_offsets.keys())
        )
        winner_src = self.closest_scanner.strip().upper() if self.closest_scanner else ""
        ref_shift = self.effective_ref_power_dbm - TX_POWER_1M_DBM

        rows: list[dict[str, Any]] = []
        for src in all_sources:
            if not src:
                continue
            scanner_name = self._resolve_scanner_display_name(src, registered_names)
            area_id = _resolve_scanner_area_id(self.hass, src) or ""
            area_obj = area_reg.async_get_area(area_id) if area_id else None
            area_name = area_obj.name if area_obj else ""
            offset_db = round(self._get_scanner_offset(src), 1)
            st = self._scanner_states.get(src)

            raw_rssi: int | None = None
            filtered_rssi: float | None = None
            effective_rssi: int | None = None
            dist_m: float | None = None
            dist_ft: float | None = None
            age_s: int | None = None
            is_fresh = False

            if st is not None and st.packet_count > 0:
                elapsed = max(0.0, now - st.last_obs_time)
                if elapsed <= SURVEY_RETENTION_SECONDS:
                    raw_rssi = int(st.raw_rssi)
                    filtered_rssi = round(st.x_dbm, 1)
                    norm_dbm = st.x_dbm + offset_db - ref_shift
                    effective_rssi = round(norm_dbm)
                    dist_m = rssi_to_distance_m(norm_dbm, attenuation=self._attenuation)
                    dist_ft = round(dist_m * 3.28084, 1)
                    age_s = round(elapsed)
                    is_fresh = elapsed <= STALE_PROXY_SECONDS
            elif src in self._unmapped_rssi:
                un_raw, un_ts = self._unmapped_rssi[src]
                elapsed = max(0.0, now - un_ts)
                if elapsed <= SURVEY_RETENTION_SECONDS:
                    raw_rssi = int(un_raw)
                    filtered_rssi = round(float(un_raw), 1)
                    norm_dbm = float(un_raw) + offset_db - ref_shift
                    effective_rssi = round(norm_dbm)
                    dist_m = rssi_to_distance_m(norm_dbm, attenuation=self._attenuation)
                    dist_ft = round(dist_m * 3.28084, 1)
                    age_s = round(elapsed)
                    is_fresh = elapsed <= STALE_PROXY_SECONDS

            rows.append(
                {
                    "scanner_source": src,
                    "scanner_name": scanner_name,
                    "area_id": area_id,
                    "area_name": area_name,
                    "raw_rssi": raw_rssi,
                    "filtered_rssi": filtered_rssi,
                    "offset_db": offset_db,
                    "effective_rssi": effective_rssi,
                    "distance_m": dist_m,
                    "distance_ft": dist_ft,
                    "age_seconds": age_s,
                    "is_fresh": is_fresh,
                    "is_winner": bool(
                        is_fresh and self.current_area_id and src == winner_src
                    ),
                }
            )

        rows.sort(
            key=lambda r: (
                r["effective_rssi"] is None,
                -(r["effective_rssi"] if r["effective_rssi"] is not None else -999),
                (r["area_name"] or "~").lower(),
                r["scanner_name"].lower(),
            )
        )
        return rows

    get_area_calibration_telemetry = get_scanner_calibration_telemetry

    def capture_area_signature(self) -> dict[str, dict[str, float | int]]:
        """Capture normalized 1 m-equivalent multi-scanner RSSI vector across fresh/recent scanners (<= 15 s)."""
        now = time.monotonic()
        ref_shift = self.effective_ref_power_dbm - TX_POWER_1M_DBM
        captured: dict[str, dict[str, float | int]] = {}

        for src, st in self._scanner_states.items():
            if st.packet_count <= 0:
                continue
            elapsed_last = now - st.last_obs_time
            if elapsed_last > SIGNATURE_CAPTURE_WINDOW_SECONDS:
                continue
            offset_db = self._get_scanner_offset(src)
            recent_12 = [
                filt + offset_db - ref_shift
                for ts, filt in st.ring_buffer
                if (now - ts) <= SIGNATURE_RING_WINDOW_SECONDS
            ]
            samples = recent_12
            if not samples:
                samples = [
                    filt + offset_db - ref_shift
                    for ts, filt in st.ring_buffer
                    if (now - ts) <= SIGNATURE_CAPTURE_WINDOW_SECONDS
                ]
            if not samples:
                samples = [st.x_dbm + offset_db - ref_shift]

            n_cnt = len(samples)
            mean_val = sum(samples) / float(n_cnt)
            variance = (
                sum((val - mean_val) ** 2 for val in samples) / float(n_cnt)
                if n_cnt > 1
                else 0.0
            )
            std_val = math.sqrt(variance)
            captured[src] = {
                "mean": round(mean_val, 1),
                "std": round(max(2.5, std_val), 1),
                "n": n_cnt,
            }
        return captured

    def _matches_raw_adv(
        self,
        address: str,
        mfg_data: Mapping[int, bytes],
        service_data: Mapping[str, bytes] | None = None,
    ) -> bool:
        """Return True if advertisement matches static/dynamic MAC, Apple iBeacon, Eddystone-UID, or BTHome v2."""
        norm_addr = str(address or "").strip().upper()
        adv_int = _mac_to_int(norm_addr) if norm_addr else None

        if self._dynamic_target_mac_int is not None and adv_int == self._dynamic_target_mac_int:
            return True
        if self._target_mac_ints and adv_int is not None and adv_int in self._target_mac_ints:
            return True

        apple_bytes = mfg_data.get(APPLE_COMPANY_ID)
        has_ibeacon_frame = bool(
            apple_bytes and len(apple_bytes) >= 20 and apple_bytes[:2] == IBEACON_PREFIX
        )
        if (
            norm_addr
            and norm_addr in self._matched_ble_addresses
            and not self._target_uuid_hex
            and not self._target_eddystone_namespace_hex
        ):
            return True

        if has_ibeacon_frame and apple_bytes and self._target_uuid_hex:
            uuid_hex = apple_bytes[2:18].hex().lower()
            if uuid_hex == self._target_uuid_hex:
                major_val: int | None = (
                    (apple_bytes[18] << 8) | apple_bytes[19]
                    if len(apple_bytes) >= 20
                    else None
                )
                minor_val: int | None = (
                    (apple_bytes[20] << 8) | apple_bytes[21]
                    if len(apple_bytes) >= 22
                    else None
                )
                expected_major, expected_minor = self._resolve_beacon_major_minor()
                if self._explicit_major is not None:
                    if major_val != expected_major:
                        return False
                elif (
                    expected_major is not None
                    and expected_major >= 0
                    and major_val != expected_major
                ):
                    return False

                if self._explicit_minor is not None:
                    return minor_val == expected_minor
                if self._explicit_major is not None:
                    return True
                if expected_minor is not None and expected_minor >= 0:
                    return minor_val == expected_minor
                return not bool(self._esphome_device_id)

        if service_data:
            for svc_uuid, svc_bytes in service_data.items():
                u_low = str(svc_uuid).lower()
                if (
                    (u_low.startswith(EDDYSTONE_UUID_PREFIX) or u_low == "feaa")
                    and isinstance(svc_bytes, (bytes, bytearray))
                    and len(svc_bytes) >= 12
                ):
                    raw_b = bytes(svc_bytes)
                    if len(raw_b) >= 18 and (raw_b[0] & 0xF0) == 0x00:
                        uid_32 = raw_b[2:18].hex().lower()
                        ns_20 = raw_b[2:12].hex().lower()
                        if self._target_uuid_hex and uid_32 == self._target_uuid_hex:
                            return True
                        if (
                            self._target_eddystone_namespace_hex
                            and ns_20 == self._target_eddystone_namespace_hex
                        ):
                            return True

        return False

    def _matches_target_device(self, service_info: object) -> bool:
        """Return True if a BluetoothServiceInfoBleak object matches this tracker and extract ref power."""
        mfg_data: Mapping[int, bytes] = getattr(
            service_info, "manufacturer_data", {}
        ) or {}
        service_data: Mapping[str, bytes] = getattr(
            service_info, "service_data", {}
        ) or {}
        adv_address = str(getattr(service_info, "address", "") or "")
        matched = self._matches_raw_adv(adv_address, mfg_data, service_data)
        if matched:
            if adv_address:
                self._record_matched_ble_address(adv_address)
            detected = _extract_adv_ref_power_dbm(service_info, mfg_data, service_data)
            if detected is not None:
                self.detected_ref_power_dbm = detected
        return matched

    @callback
    def _async_on_ble_advertisement(
        self, service_info: object, _change: object
    ) -> None:
        """Process incoming BLE advertisement callback from an ESPHome BLE proxy."""
        if not self._matches_target_device(service_info):
            return

        rssi_int = _safe_rssi_int(getattr(service_info, "rssi", None))
        source = str(getattr(service_info, "source", "") or "")
        if rssi_int is None or not source or rssi_int <= -100:
            return

        adv_ts = getattr(service_info, "time", None)
        obs_mono = float(adv_ts) if adv_ts is not None else time.monotonic()
        self._ingest_proxy_observation(source, rssi_int, obs_mono, source)

    def _resolve_cached_scanner_area(self, norm_source: str) -> str | None:
        """Resolve `norm_source` to a Home Assistant `area_id` using per-tracker cache."""
        cached_area = self._scanner_area_cache.get(norm_source)
        if cached_area is None:
            resolved_area = _resolve_scanner_area_id(self.hass, norm_source)
            cached_area = resolved_area if resolved_area else _UNMAPPED
            self._scanner_area_cache[norm_source] = cached_area
        return None if cached_area == _UNMAPPED else cached_area

    def _update_scanner_filter(
        self,
        norm_source: str,
        raw_rssi: int,
        obs_time: float,
        scanner_name: str,
    ) -> ScannerObservationState:
        """Update per-scanner 3-sample median, velocity-gated adaptive Kalman filter, and ring buffer."""
        st = self._scanner_states.get(norm_source)
        raw_f = float(raw_rssi)
        if st is None:
            st = ScannerObservationState(
                source=norm_source,
                scanner_name=scanner_name or norm_source,
                raw_rssi=int(raw_rssi),
                recent_raw=[(obs_time, raw_f)],
                x_dbm=raw_f,
                p_var=6.0,
                last_obs_time=obs_time,
                packet_count=1,
                ring_buffer=[(obs_time, raw_f)],
            )
            self._scanner_states[norm_source] = st
            return st

        if scanner_name and scanner_name.upper() != norm_source:
            st.scanner_name = scanner_name
        st.raw_rssi = int(raw_rssi)
        dt_raw = obs_time - st.last_obs_time

        if st.packet_count <= 0 or dt_raw > STALE_PROXY_SECONDS or dt_raw < -1.0:
            st.recent_raw = [(obs_time, raw_f)]
            st.x_dbm = raw_f
            st.p_var = 6.0
            st.last_obs_time = obs_time
            st.packet_count = 1
        else:
            dt = max(0.05, dt_raw)
            st.recent_raw = [
                (ts, val)
                for ts, val in st.recent_raw
                if (obs_time - ts) <= STALE_PROXY_SECONDS
            ]
            st.recent_raw.append((obs_time, raw_f))
            if len(st.recent_raw) > 3:
                st.recent_raw = st.recent_raw[-3:]

            vals = [val for _ts, val in st.recent_raw]
            if len(vals) == 1:
                pre_dbm = vals[0]
            elif len(vals) == 2:
                pre_dbm = 0.5 * (vals[0] + vals[1])
            else:
                pre_dbm = sorted(vals)[1]

            # Symmetric physical velocity gate: damp impossible recession/approach multipath jumps
            ref_shift = self.effective_ref_power_dbm - TX_POWER_1M_DBM
            offset_db = self._get_scanner_offset(norm_source)
            prev_norm = st.x_dbm + offset_db - ref_shift
            cand_norm = pre_dbm + offset_db - ref_shift
            prev_dist = _continuous_distance_m(prev_norm, self._attenuation)
            cand_dist = _continuous_distance_m(cand_norm, self._attenuation)
            max_step_m = self._max_velocity_mps * dt
            if pre_dbm < st.x_dbm:
                max_allowed_dist = prev_dist + max_step_m
                if cand_dist > max_allowed_dist:
                    clamped_norm = _distance_m_to_norm_dbm(
                        max_allowed_dist, self._attenuation
                    )
                    gated_dbm = clamped_norm - offset_db + ref_shift
                else:
                    gated_dbm = pre_dbm
            elif pre_dbm > st.x_dbm:
                min_allowed_dist = max(0.05, prev_dist - max_step_m)
                if cand_dist < min_allowed_dist:
                    clamped_norm = _distance_m_to_norm_dbm(
                        min_allowed_dist, self._attenuation
                    )
                    gated_dbm = clamped_norm - offset_db + ref_shift
                else:
                    gated_dbm = pre_dbm
            else:
                gated_dbm = pre_dbm

            # Symmetric bounded adaptive 1D Kalman filter
            q_var = 2.5 * dt
            delta_gated = abs(gated_dbm - st.x_dbm)
            if delta_gated > 6.0:
                q_var += min(36.0, 0.25 * (delta_gated ** 2))
            p_pred = st.p_var + q_var
            kalman_gain = p_pred / (p_pred + KALMAN_MEASUREMENT_VAR)
            st.x_dbm = st.x_dbm + kalman_gain * (gated_dbm - st.x_dbm)
            st.p_var = (1.0 - kalman_gain) * p_pred
            st.last_obs_time = max(st.last_obs_time, obs_time)
            st.packet_count += 1

        st.ring_buffer = [
            (ts, filt)
            for ts, filt in st.ring_buffer
            if (obs_time - ts) <= SIGNATURE_CAPTURE_WINDOW_SECONDS
        ]
        st.ring_buffer.append((obs_time, st.x_dbm))
        if len(st.ring_buffer) > SIGNATURE_RING_MAX_SAMPLES:
            st.ring_buffer = st.ring_buffer[-SIGNATURE_RING_MAX_SAMPLES:]
        return st

    def _score_signature_area(
        self,
        area_id: str,
        sig: Mapping[str, Any],
        fresh_norm: Mapping[str, float],
        fresh_ages: Mapping[str, float],
        is_cross_floor: Callable[[str], bool],
    ) -> tuple[float, str] | None:
        """Score `area_id` using joint multi-scanner Gaussian + pairwise-differential vector matching."""
        sig_scanners = sig.get("scanners")
        if not isinstance(sig_scanners, Mapping) or not sig_scanners or not fresh_norm:
            return None

        matched_srcs = [src for src in sig_scanners if src in fresh_norm]
        if not matched_srcs:
            return None

        weighted_sq_err = 0.0
        total_weight = 0.0
        missing_penalty = 0.0
        unexpected_penalty = 0.0

        src_meta: list[tuple[str, float, float, float]] = []
        for src, stats in sig_scanners.items():
            if not isinstance(stats, Mapping):
                continue
            mu = float(stats.get("mean", -75.0))
            sigma = max(2.5, float(stats.get("std", 3.5)))
            w = max(0.25, min(2.0, (mu - (-95.0)) / 25.0))
            if src in fresh_norm:
                obs = fresh_norm[src]
                diff = obs - mu
                if diff > 0.0 and self._resolve_cached_scanner_area(src) == area_id:
                    diff *= 0.15
                eff_err = abs(diff) * (3.0 / sigma)
                weighted_sq_err += w * (eff_err ** 2)
                total_weight += w
                src_meta.append((src, mu, sigma, w))
            elif mu >= -78.0:
                missing_penalty += 6.0 + 0.65 * (mu - (-78.0))

        if total_weight <= 0.0 or not src_meta:
            return None

        for obs_src, obs_val in fresh_norm.items():
            if obs_src not in sig_scanners and obs_val >= -75.0:
                unexpected_penalty += 0.75 * (obs_val - (-78.0))

        abs_rmse_db = math.sqrt(weighted_sq_err / total_weight)

        if len(src_meta) >= 2:
            pair_sq_err = 0.0
            pair_weight = 0.0
            for idx_a in range(len(src_meta)):
                src_a, mu_a, sig_a, w_a = src_meta[idx_a]
                for idx_b in range(idx_a + 1, len(src_meta)):
                    src_b, mu_b, sig_b, w_b = src_meta[idx_b]
                    pw = math.sqrt(w_a * w_b)
                    obs_delta = fresh_norm[src_a] - fresh_norm[src_b]
                    sig_delta = mu_a - mu_b
                    sigma_pair = math.hypot(sig_a, sig_b)
                    p_err = abs(obs_delta - sig_delta) * (4.24264 / sigma_pair)
                    pair_sq_err += pw * (p_err ** 2)
                    pair_weight += pw
            diff_rmse_db = (
                math.sqrt(pair_sq_err / pair_weight) if pair_weight > 0.0 else abs_rmse_db
            )
            combined_err_db = (
                0.45 * abs_rmse_db
                + 0.55 * diff_rmse_db
                + missing_penalty
                + unexpected_penalty
            )
        else:
            single_pen = 3.0 if len(sig_scanners) >= 2 else 0.0
            combined_err_db = (
                abs_rmse_db + missing_penalty + unexpected_penalty + single_pen
            )

        min_age_s = min(fresh_ages[s] for s in matched_srcs)
        decay_db = SILENCE_DECAY_DB_PER_S * max(0.0, min_age_s - SILENCE_GRACE_SECONDS)
        score = SIGNATURE_PEAK_SCORE_DBM - (1.35 * combined_err_db) - decay_db
        if is_cross_floor(area_id):
            score -= CROSS_FLOOR_ATTENUATION_DB

        best_src = min(matched_srcs, key=lambda s: (-round(fresh_norm[s], 6), s))
        return score, best_src

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
        """Ingest a `(scanner_source, rssi)` observation and evaluate spatial Area transitions."""
        norm_source = str(source or "").strip().upper()
        if not norm_source:
            return
        now = time.monotonic()
        eval_now = max(now, obs_time) if (obs_time - now) <= 60.0 else now

        prev_adv_ts = self._last_adv_ts_by_scanner.get(norm_source)
        if prev_adv_ts is not None:
            if from_poll and obs_time <= (prev_adv_ts + 1e-4):
                self._evaluate_best_area(eval_now, "")
                return
            if not from_poll and abs(obs_time - prev_adv_ts) < 1e-6:
                return

        self._last_adv_ts_by_scanner[norm_source] = obs_time
        just_woke_from_standby = (
            not from_poll
            and not self._awaiting_fresh_wake_lock
            and self.last_packet_monotonic > 0.0
            and (obs_time - self.last_packet_monotonic) >= WAKE_GAP_SECONDS
        )
        if obs_time > self.last_packet_monotonic:
            self.last_packet_monotonic = obs_time
        self.packets_seen += 1

        if (
            self._esphome_device_id
            and not self._target_mac_ints
            and self.packets_seen <= 3
        ):
            self._target_mac_ints = _discover_target_device_macs(
                self.hass, self._esphome_device_id
            )
            if self._target_mac_ints:
                get_ble_fabric(self.hass).sync_tracker_addresses()

        if just_woke_from_standby:
            self._cancel_wake_coalesce_timer()
            self._scanner_states.clear()
            self._area_rssi.clear()
            self._area_raw_rssi.clear()
            self._last_switch_monotonic = 0.0
            self._awaiting_fresh_wake_lock = True
            self._wake_coalesce_until = (
                obs_time + WAKE_COALESCE_SECONDS if self.current_area_id else 0.0
            )

        st = self._update_scanner_filter(norm_source, int(rssi), obs_time, scanner_name)
        area_id = self._resolve_cached_scanner_area(norm_source)
        if not area_id:
            self._unmapped_rssi[norm_source] = (int(rssi), obs_time)
            if self._area_signatures and (eval_now - obs_time) <= STALE_PROXY_SECONDS:
                self._evaluate_best_area(eval_now, norm_source)
            return

        self._unmapped_rssi.pop(norm_source, None)
        ref_shift = self.effective_ref_power_dbm - TX_POWER_1M_DBM
        norm_dbm = st.x_dbm + self._get_scanner_offset(norm_source) - ref_shift
        self._area_raw_rssi[area_id] = (st.x_dbm, obs_time, st.scanner_name or norm_source)
        self._area_rssi[area_id] = (norm_dbm, obs_time)

        if (eval_now - obs_time) <= STALE_PROXY_SECONDS:
            self._evaluate_best_area(eval_now, norm_source)

    @callback
    def _evaluate_best_area(self, now: float, latest_source: str = "") -> None:
        """Evaluate multi-scanner path-loss + vector signature scores with wake coalescing and 3.0 dBm deadband."""
        area_reg = ar.async_get(self.hass)
        prior_area_id = None if self._awaiting_fresh_wake_lock else self.current_area_id
        anchor_floor_area_id = self.current_area_id
        cur_floor_id: str | None = None
        if anchor_floor_area_id:
            cur_area_entry = area_reg.async_get_area(anchor_floor_area_id)
            if cur_area_entry:
                cur_floor_id = getattr(cur_area_entry, "floor_id", None)

        def _is_cross_floor(area_id: str) -> bool:
            if not cur_floor_id or area_id == anchor_floor_area_id:
                return False
            cand_entry = area_reg.async_get_area(area_id)
            cand_floor_id = getattr(cand_entry, "floor_id", None) if cand_entry else None
            return bool(cand_floor_id and cand_floor_id != cur_floor_id)

        ref_shift = self.effective_ref_power_dbm - TX_POWER_1M_DBM
        fresh_norm: dict[str, float] = {}
        fresh_ages: dict[str, float] = {}
        area_candidates: dict[str, list[tuple[float, float, ScannerObservationState, str]]] = {}

        for src, st in self._scanner_states.items():
            if st.packet_count <= 0:
                continue
            age_s = max(0.0, now - st.last_obs_time)
            if age_s > STALE_PROXY_SECONDS:
                continue
            norm_dbm = st.x_dbm + self._get_scanner_offset(src) - ref_shift
            fresh_norm[src] = norm_dbm
            fresh_ages[src] = age_s

            a_id = self._resolve_cached_scanner_area(src)
            if not a_id:
                continue
            dist_m = rssi_to_distance_m(norm_dbm, attenuation=self._attenuation)
            if dist_m > self._max_radius_m:
                continue
            decayed = norm_dbm - SILENCE_DECAY_DB_PER_S * max(
                0.0, age_s - SILENCE_GRACE_SECONDS
            )
            area_candidates.setdefault(a_id, []).append((decayed, norm_dbm, st, src))

        scores: dict[str, float] = {}
        area_winner_meta: dict[str, tuple[str, float, int, str]] = {}
        area_packet_counts: dict[str, int] = {}

        for a_id, cand_list in area_candidates.items():
            best_decayed, best_norm, best_st, best_src = min(
                cand_list,
                key=lambda item: (-round(item[0], 6), -round(item[1], 6), item[3]),
            )
            corroborating = sum(
                1 for _dec, n_dbm, _s, _src in cand_list if n_dbm >= CORROBORATION_MIN_DBM
            )
            score = best_decayed + (
                CORROBORATION_BONUS_DB if corroborating >= 2 else 0.0
            )
            if _is_cross_floor(a_id):
                score -= CROSS_FLOOR_ATTENUATION_DB
            scores[a_id] = score
            area_winner_meta[a_id] = (best_src, best_norm, best_st.raw_rssi, "distance")
            area_packet_counts[a_id] = sum(item[2].packet_count for item in cand_list)

        for sig_area_id, sig in self._area_signatures.items():
            sig_res = self._score_signature_area(
                sig_area_id, sig, fresh_norm, fresh_ages, _is_cross_floor
            )
            if sig_res is None:
                continue
            sig_score, sig_best_src = sig_res
            sig_scanners = sig.get("scanners", {})
            if (
                sig_area_id in scores
                and len(fresh_norm) < 2
                and len(sig_scanners) >= 2
                and sig_score < scores[sig_area_id]
            ):
                continue
            sig_st = self._scanner_states.get(sig_best_src)
            sig_norm = fresh_norm.get(sig_best_src, sig_score)
            sig_raw = sig_st.raw_rssi if sig_st is not None else round(sig_norm)
            scores[sig_area_id] = sig_score
            area_winner_meta[sig_area_id] = (
                sig_best_src,
                sig_norm,
                sig_raw,
                "signature",
            )
            area_packet_counts[sig_area_id] = max(
                1,
                sum(
                    self._scanner_states[s].packet_count
                    for s in sig_scanners
                    if s in self._scanner_states
                ),
            )

        # Fallback compatibility if a test seeded `_area_rssi` directly without `_scanner_states`
        if not scores and self._area_rssi and not self._scanner_states:
            scores = score_areas(self._area_rssi, now, _is_cross_floor)
            for a_id, (eff_v, _ts) in self._area_rssi.items():
                raw_tup = self._area_raw_rssi.get(a_id)
                raw_int = round(raw_tup[0]) if raw_tup else round(eff_v)
                src_s = raw_tup[2] if raw_tup else ""
                area_winner_meta[a_id] = (src_s, eff_v, raw_int, "distance")
                area_packet_counts[a_id] = 2

        fabric = get_ble_fabric(self.hass)
        if not scores:
            fabric.emit_survey_delta(self)
            return

        top_area_id = min(
            scores.items(),
            key=lambda item: (-round(item[1], 6), item[0] != prior_area_id, item[0]),
        )[0]
        challenger_pkts = area_packet_counts.get(top_area_id, 1)
        decision = decide_area(
            scores,
            prior_area_id,
            now,
            self._last_switch_monotonic,
            challenger_packet_count=challenger_pkts,
        )
        if decision is None:
            fabric.emit_survey_delta(self)
            return

        best_area = decision.best_area_id

        # Post-wake multi-proxy TCP race coalescing: hold sticky `current_area_id` briefly on single foreign packet
        if (
            self._awaiting_fresh_wake_lock
            and self.current_area_id is not None
            and best_area != self.current_area_id
            and now < self._wake_coalesce_until
            and challenger_pkts < 2
            and self._area_has_registered_scanner(self.current_area_id)
        ):
            if self._unsub_wake_coalesce is None:
                self._unsub_wake_coalesce = async_call_later(
                    self.hass,
                    WAKE_COALESCE_SECONDS,
                    self._async_on_wake_coalesce_timer,
                )
            fabric.emit_survey_delta(self)
            return

        self._cancel_wake_coalesce_timer()
        self._wake_coalesce_until = 0.0
        self._awaiting_fresh_wake_lock = False
        self.is_away = False

        def _update_winner_metrics(win_area: str) -> None:
            meta = area_winner_meta.get(win_area)
            if meta is not None:
                win_src, win_norm_dbm, win_raw_dbm, win_method = meta
                if win_src:
                    self.closest_scanner = win_src
                self.winning_rssi = round(win_norm_dbm)
                self.winning_raw_rssi = int(win_raw_dbm)
                d_m = rssi_to_distance_m(win_norm_dbm, attenuation=self._attenuation)
                self.winning_distance_m = d_m
                self.winning_distance_ft = round(d_m * 3.28084, 1)
                self.match_method = win_method

        if best_area == self.current_area_id:
            meta = area_winner_meta.get(best_area)
            eff_dbm = meta[1] if meta is not None else None
            if meta is not None and meta[0]:
                self.closest_scanner = meta[0]
                self.match_method = meta[3]
            elif latest_source:
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
        if not self.closest_scanner and latest_source:
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
        self._unsub_registry_events: Callable[[], None] | None = None
        self._adv_unsubs: dict[str, Callable[[], None]] = {}
        self._unsub_away_timer: Callable[[], None] | None = None
        self._unsub_sensor_events: Callable[[], None] | None = None

    @callback
    def _ensure_registry_listeners(self) -> None:
        """Keep Area/Device/Entity/Floor registry cache invalidation active whenever trackers or occupancy listeners exist."""
        if self._unsub_registry_events is not None:
            return
        reg_unsubs = [
            self.hass.bus.async_listen(
                dr.EVENT_DEVICE_REGISTRY_UPDATED, self._invalidate_caches
            ),
            self.hass.bus.async_listen(
                er.EVENT_ENTITY_REGISTRY_UPDATED, self._invalidate_caches
            ),
            self.hass.bus.async_listen(
                ar.EVENT_AREA_REGISTRY_UPDATED, self._invalidate_caches
            ),
            self.hass.bus.async_listen(
                "floor_registry_updated", self._invalidate_caches
            ),
        ]

        @callback
        def _unsub_regs() -> None:
            for u in reg_unsubs:
                u()

        self._unsub_registry_events = _unsub_regs

    @callback
    def _maybe_stop_registry_listeners(self) -> None:
        """Stop registry invalidation listeners when neither trackers nor occupancy listeners remain."""
        if (
            not self._trackers
            and not self._occupancy_listeners
            and self._unsub_registry_events is not None
        ):
            self._unsub_registry_events()
            self._unsub_registry_events = None

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
            self.notify_occupancy_listeners()

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
        self._ensure_registry_listeners()
        if self._unsub_sensor_events is None:
            self.rebind_fusion_sensor_listener()

        @callback
        def _unsub() -> None:
            if listener in self._occupancy_listeners:
                self._occupancy_listeners.remove(listener)
            if not self._occupancy_listeners and self._unsub_sensor_events is not None:
                self._unsub_sensor_events()
                self._unsub_sensor_events = None
            self._maybe_stop_registry_listeners()

        unsub: Callable[[], None] = _unsub
        return unsub

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

        unsub: Callable[[], None] = _unsub
        return unsub

    @callback
    def emit_survey_delta(self, tracker: LatterNativeBleTracker) -> None:
        """Push a compact `ble_survey_delta` payload to active Studio site survey subscribers."""
        if not self._survey_listeners:
            return
        payload = {
            "device_slug": tracker._raw_slug,
            "packets_seen": tracker.packets_seen,
            "current_area_id": tracker.current_area_id or "",
            "winning_rssi": tracker.winning_rssi,
            "closest_scanner": tracker.closest_scanner,
            "match_method": tracker.match_method,
            "calibration": tracker.get_scanner_calibration_telemetry(),
            "area_signatures": get_area_signatures_summary(self.hass),
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
        closest_match_method: str = ""

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
                    closest_match_method = tracker.match_method or "distance"

        ble_present = len(occupants) > 0
        fused = evaluate_area_sensor_fusion(
            self.hass,
            area_id,
            ble_present=ble_present,
            best_rssi=best_rssi,
        )
        clean_floor_id, floor_name = resolve_floor_info(self.hass, floor_id)

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
            "unavailable_sensors": fused["unavailable_sensors"],
            "closest_device": closest_dev,
            "winning_rssi": best_rssi,
            "closest_distance_m": closest_dist_m,
            "closest_distance_ft": closest_dist_ft,
            "match_method": closest_match_method,
            "floor_id": floor_id,
            "floor_name": floor_name if clean_floor_id else "",
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
        """Start the shared passive Bluetooth callback (both connectable & non-connectable) and away timer."""
        self._ensure_registry_listeners()
        unsubs: list[Callable[[], None]] = []
        try:
            from homeassistant.components import bluetooth

            try:
                matcher = bluetooth.BluetoothCallbackMatcher(connectable=False)
            except TypeError:
                try:
                    matcher = bluetooth.BluetoothCallbackMatcher()
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

        unsubs.append(
            self.hass.bus.async_listen(
                "esphome.ibeacon_seen", self._async_on_esphome_ibeacon_event
            )
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
        if not self._occupancy_listeners and self._unsub_sensor_events is not None:
            self._unsub_sensor_events()
            self._unsub_sensor_events = None
        self._maybe_stop_registry_listeners()

    @callback
    def _async_on_esphome_ibeacon_event(self, event: Any) -> None:
        """Ingest custom esphome.ibeacon_seen bus events emitted by ESPHome BLE proxies."""
        data = getattr(event, "data", {}) or {}
        source = str(data.get("source") or data.get("scanner") or "").strip()
        uuid_raw = _normalize_uuid_hex(str(data.get("uuid") or ""))
        rssi_int = _safe_rssi_int(data.get("rssi"))
        if not source or rssi_int is None or rssi_int <= -100:
            return
        adv_addr = str(data.get("address") or data.get("mac") or "").strip().upper()
        adv_int = _mac_to_int(adv_addr) if adv_addr else None
        raw_major = data.get("major")
        raw_minor = data.get("minor")
        ev_major = _coerce_uint16(raw_major)
        ev_minor = _coerce_uint16(raw_minor)
        now_mono = time.monotonic()
        for tracker in list(self._trackers):
            if not (uuid_raw and uuid_raw == tracker._target_uuid_hex):
                continue
            expected_major, expected_minor = tracker._resolve_beacon_major_minor()
            if (
                tracker._explicit_major is not None
                or tracker._explicit_minor is not None
            ):
                if (
                    tracker._explicit_major is not None
                    and ev_major != expected_major
                ):
                    continue
                if (
                    tracker._explicit_minor is not None
                    and ev_minor != expected_minor
                ):
                    continue
            else:
                static_mac_ok = bool(
                    tracker._target_mac_ints
                    and adv_int is not None
                    and adv_int in tracker._target_mac_ints
                )
                if not static_mac_ok:
                    if (
                        expected_major is not None
                        and expected_major >= 0
                        and ev_major != expected_major
                    ):
                        continue
                    if expected_minor is not None and expected_minor >= 0:
                        if ev_minor != expected_minor:
                            continue
                    elif tracker._esphome_device_id:
                        continue
            tracker._ingest_proxy_observation(source, rssi_int, now_mono, source)

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
        """Away-timeout, deferred MAC discovery, and rotating-MAC scanner fallback check."""
        if not self._trackers:
            return
        now_mono = time.monotonic()
        discovered_any = False
        for tracker in list(self._trackers):
            if (
                tracker.packets_seen == 0
                or (now_mono - tracker.last_packet_monotonic) > STALE_PROXY_SECONDS
            ):
                self._async_seed_tracker_from_scanners_once(tracker)
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
        self, tracker: LatterNativeBleTracker, *, only_address: str = ""
    ) -> None:
        """Seed a tracker from current Bluetooth scanner state (optionally restricted to `only_address`)."""
        try:
            from homeassistant.components import bluetooth

            only_norm = only_address.strip().upper()
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
                    addr_str = str(addr)
                    if only_norm and addr_str.strip().upper() != only_norm:
                        continue
                    ble_dev, adv_data = pair
                    mfg_data = getattr(adv_data, "manufacturer_data", {}) or {}
                    svc_data = getattr(adv_data, "service_data", {}) or {}
                    if not tracker._matches_raw_adv(addr_str, mfg_data, svc_data):
                        continue
                    tracker._record_matched_ble_address(addr_str, seed_scanners=False)
                    det_rp = _extract_adv_ref_power_dbm(adv_data, mfg_data, svc_data)
                    if det_rp is not None:
                        tracker.detected_ref_power_dbm = det_rp
                    last_ts = timestamps.get(addr)
                    obs_mono = float(last_ts) if last_ts is not None else now_mono
                    if last_ts is not None and (now_mono - obs_mono) > SURVEY_RETENTION_SECONDS:
                        continue
                    raw_rssi = getattr(adv_data, "rssi", None)
                    if raw_rssi is None:
                        raw_rssi = getattr(ble_dev, "rssi", None)
                    rssi_int = _safe_rssi_int(raw_rssi)
                    if rssi_int is None or rssi_int <= -100:
                        continue
                    tracker._ingest_proxy_observation(
                        source,
                        rssi_int,
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
    fabric: LatterBleFabric = domain_data["ble_fabric"]
    return fabric


def get_all_areas_presence_summary(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Build live per-area presence, occupant names, confidence score, and fusion settings."""
    area_reg = ar.async_get(hass)
    fabric = get_ble_fabric(hass)
    proxy_areas = get_ble_proxy_area_ids(hass)
    sig_areas = get_ble_signature_area_ids(hass)

    rows: list[dict[str, Any]] = []
    for area_entry in sorted(area_reg.async_list_areas(), key=lambda a: a.name.lower()):
        from .areas import (
            area_illuminance_sensor_choices,
            resolve_area_ambient_light,
        )

        occ = fabric.get_area_occupancy(area_entry.id)
        has_proxy = area_entry.id in proxy_areas
        has_sig = area_entry.id in sig_areas
        has_sensors = len(occ["available_sensors"]) > 0
        lux_choices = area_illuminance_sensor_choices(hass, area_entry.id)
        if (
            not has_proxy
            and not has_sig
            and not has_sensors
            and not lux_choices
            and not occ["is_occupied"]
        ):
            continue
        fusion_cfg = area_fusion_settings(hass, area_entry.id)
        ambient = resolve_area_ambient_light(hass, area_entry.id)
        rows.append(
            {
                "area_id": area_entry.id,
                "area_name": area_entry.name,
                "floor_id": getattr(area_entry, "floor_id", None) or "",
                "floor_name": occ["floor_name"],
                "has_ble_proxy": has_proxy,
                "match_method": occ["match_method"],
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
                "unavailable_sensors": occ["unavailable_sensors"],
                "closest_device": occ["closest_device"] or "",
                "winning_rssi": occ["winning_rssi"],
                "closest_distance_m": occ["closest_distance_m"],
                "closest_distance_ft": occ["closest_distance_ft"],
                "fusion_threshold_pct": int(fusion_cfg.get("threshold_pct") or 50),
                "fusion_sensors": [
                    str(s) for s in (fusion_cfg.get("sensors") or []) if isinstance(s, str)
                ],
                "fusion_sensor_choices": area_fusion_sensor_choices(hass, area_entry.id),
                "illuminance_entity": ambient["configured_entity"],
                "illuminance_resolved_entity": ambient["resolved_entity"],
                "illuminance_resolved_name": ambient["resolved_name"],
                "illuminance_lux": ambient["lux"],
                "illuminance_lux_display": ambient["lux_display"],
                "illuminance_ambient_pct": ambient["ambient_pct"],
                "illuminance_dark_lux": ambient["dark_lux"],
                "illuminance_bright_lux": ambient["bright_lux"],
                "illuminance_sensor_choices": lux_choices,
            }
        )
    return rows


def _extract_ibeacon_entity_identity(
    hass: HomeAssistant,
    entry: er.RegistryEntry | None,
    st: Any,
) -> tuple[str, int | None, int | None] | None:
    """Extract `(uuid_hex, major, minor)` from an entity's state attributes, `unique_id`, or parent device."""
    if st is not None:
        raw_attr = str(
            st.attributes.get("id") or st.attributes.get("uuid") or ""
        ).strip()
        if raw_attr:
            parsed = parse_ibeacon_identity(
                raw_attr,
                st.attributes.get("major"),
                st.attributes.get("minor"),
            )
            if parsed is not None:
                return parsed

    raw_candidates: list[str] = []
    if entry is not None:
        if entry.unique_id:
            raw_candidates.append(str(entry.unique_id).strip())
        if entry.device_id:
            dev_entry = dr.async_get(hass).async_get(entry.device_id)
            if dev_entry is not None:
                for _dom, ident_val in dev_entry.identifiers:
                    if ident_val:
                        raw_candidates.append(str(ident_val).strip())

    for cand in raw_candidates:
        direct = parse_ibeacon_identity(cand)
        if direct is not None:
            return direct
        m_pref = _IBEACON_ENTITY_PREFIX_RE.match(cand)
        if m_pref is not None:
            u_hex = _normalize_uuid_hex(m_pref.group("uuid"))
            maj = _coerce_uint16(m_pref.group("major"))
            min_ = _coerce_uint16(m_pref.group("minor"))
            if len(u_hex) == 32 and maj is not None and min_ is not None:
                return u_hex, maj, min_
    return None


def _is_excluded_cloud_find_adv(
    local_name: str,
    mfg_data: Mapping[int, bytes],
    service_data: Mapping[str, bytes],
) -> bool:
    """Return True for unresolvable rolling-EID cloud Find-network frames (Google FMDN 0x40, Apple Find My 0x12)."""
    for raw_k, raw_v in (service_data or {}).items():
        if (
            _extract_uuid16(str(raw_k)) == "feaa"
            and isinstance(raw_v, (bytes, bytearray))
            and len(raw_v) >= 1
            and (raw_v[0] & 0xF0) == 0x40
        ):
            return True

    mfg_map = _normalize_mfg_map(mfg_data)
    apple_payload = mfg_map.get(APPLE_COMPANY_ID)
    return bool(
        apple_payload is not None
        and len(apple_payload) >= 1
        and apple_payload[0] == 0x12
        and not local_name
    )


def _index_live_ble_advertisements(
    hass: HomeAssistant,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[tuple[str, int | None, int | None], dict[str, Any]],
]:
    """Scan HA Bluetooth scanners once to index strongest live advertisements by MAC and by iBeacon tuple."""
    by_mac: dict[str, dict[str, Any]] = {}
    by_ibeacon: dict[tuple[str, int | None, int | None], dict[str, Any]] = {}
    area_reg = ar.async_get(hass)
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
                addr_str = str(addr or "").strip().upper()
                if not addr_str:
                    continue
                local_name = str(
                    getattr(adv_data, "local_name", "")
                    or getattr(ble_dev, "name", "")
                    or ""
                ).strip()
                if (
                    local_name
                    and local_name.replace(":", "").replace("-", "").upper()
                    == addr_str.replace(":", "").replace("-", "")
                ):
                    local_name = ""

                mfg_map = _normalize_mfg_map(
                    getattr(adv_data, "manufacturer_data", None) or {}
                )
                raw_svc_data = getattr(adv_data, "service_data", None) or {}
                svc_data: dict[str, bytes] = {
                    str(k): bytes(v)
                    for k, v in raw_svc_data.items()
                    if isinstance(v, (bytes, bytearray))
                }
                raw_uuids = getattr(adv_data, "service_uuids", None) or ()
                svc_uuids = tuple(str(u) for u in raw_uuids if u)

                rssi_raw = getattr(adv_data, "rssi", None)
                if rssi_raw is None:
                    rssi_raw = getattr(ble_dev, "rssi", None)
                rssi_int = (
                    int(rssi_raw)
                    if isinstance(rssi_raw, (int, float))
                    and not isinstance(rssi_raw, bool)
                    else None
                )

                prev = by_mac.get(addr_str)
                better = prev is None or (
                    rssi_int is not None
                    and (prev["rssi"] is None or rssi_int > prev["rssi"])
                )
                if better:
                    by_mac[addr_str] = {
                        "mac": addr_str,
                        "local_name": local_name or (prev["local_name"] if prev else ""),
                        "mfg_data": mfg_map or (prev["mfg_data"] if prev else {}),
                        "service_data": svc_data or (prev["service_data"] if prev else {}),
                        "service_uuids": svc_uuids or (prev["service_uuids"] if prev else ()),
                        "rssi": rssi_int,
                        "area_name": area_name,
                        "scanner": scanner_name,
                        "source": source,
                    }
                elif prev is not None:
                    if local_name and not prev["local_name"]:
                        prev["local_name"] = local_name
                    if mfg_map and not prev["mfg_data"]:
                        prev["mfg_data"] = mfg_map
                    if svc_data and not prev["service_data"]:
                        prev["service_data"] = svc_data
                    if svc_uuids and not prev["service_uuids"]:
                        prev["service_uuids"] = svc_uuids

                apple_b = mfg_map.get(APPLE_COMPANY_ID)
                if (
                    apple_b is not None
                    and len(apple_b) >= 20
                    and apple_b[:2] == IBEACON_PREFIX
                ):
                    ib_uuid = apple_b[2:18].hex().lower()
                    ib_maj = (apple_b[18] << 8) | apple_b[19]
                    ib_min = (
                        ((apple_b[20] << 8) | apple_b[21])
                        if len(apple_b) >= 22
                        else None
                    )
                    ib_info = {
                        "rssi": rssi_int,
                        "area_name": area_name,
                        "scanner": scanner_name,
                        "mac": addr_str,
                    }
                    for ib_k in ((ib_uuid, ib_maj, ib_min), (ib_uuid, None, None)):
                        prev_ib = by_ibeacon.get(ib_k)
                        if prev_ib is None or (
                            rssi_int is not None
                            and (
                                prev_ib["rssi"] is None
                                or rssi_int > prev_ib["rssi"]
                            )
                        ):
                            by_ibeacon[ib_k] = ib_info
    except Exception:  # noqa: BLE001
        pass
    return by_mac, by_ibeacon


def _is_mobile_app_ble_emitter(entry: er.RegistryEntry) -> bool:
    """Return True if `entry` is a Home Assistant Companion App BLE Transmitter sensor."""
    if entry.platform != "mobile_app" or entry.domain != "sensor":
        return False
    uid = str(entry.unique_id or "").lower()
    eid = entry.entity_id.lower()
    return uid.endswith(("_ble_emitter", "_ble_transmitter")) or eid.endswith(
        ("_ble_transmitter", "_ble_emitter")
    )


def describe_ble_target_model(hass: HomeAssistant, target_address: str) -> str:
    """Return a human-friendly model / tag classification label for a managed BLE tag."""
    addr = str(target_address or "").strip()
    if not addr:
        return "BLE beacon or tag"

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    live_by_mac, _ = _index_live_ble_advertisements(hass)

    if "." in addr:
        ent_entry = ent_reg.async_get(addr)
        dev_entry = (
            dev_reg.async_get(ent_entry.device_id)
            if (ent_entry is not None and ent_entry.device_id)
            else None
        )
        st = hass.states.get(addr)

        if (
            (ent_entry is not None and ent_entry.platform == "mobile_app")
            or addr.lower().endswith(("_ble_transmitter", "_ble_emitter"))
            or (
                ent_entry is not None
                and ent_entry.unique_id
                and str(ent_entry.unique_id).lower().endswith("_ble_emitter")
            )
        ):
            model_str = str(dev_entry.model or "").strip() if dev_entry else ""
            return f"{model_str} (HA Companion App)" if model_str else "HA Companion App"

        if (
            (ent_entry is not None and ent_entry.platform == "private_ble_device")
            or "private_ble" in addr.lower()
            or (st is not None and st.attributes.get("current_address"))
        ):
            cur_mac = str(
                (st.attributes.get("current_address") if st else "") or ""
            ).strip().upper()
            live_adv = live_by_mac.get(cur_mac) if cur_mac else None
            if live_adv is not None:
                classified = classify_ble_advertisement_kind(
                    live_adv["local_name"],
                    live_adv["mfg_data"],
                    live_adv["service_data"],
                    live_adv["service_uuids"],
                    is_private_ble=True,
                )
                if classified != "Phone or Watch (Private BLE / IRK)":
                    return classified
            return "Private BLE (phone or watch)"

        if (ent_entry is not None and ent_entry.platform == "bthome") or (
            "bthome" in addr.lower()
        ):
            if dev_entry is not None:
                for _ct, cv in dev_entry.connections:
                    m_int = _mac_to_int(str(cv))
                    if m_int is not None:
                        live_adv = live_by_mac.get(_int_to_mac(m_int))
                        if live_adv is not None:
                            classified = classify_ble_advertisement_kind(
                                live_adv["local_name"],
                                live_adv["mfg_data"],
                                live_adv["service_data"],
                                live_adv["service_uuids"],
                                is_private_ble=False,
                            )
                            if classified in (
                                "Shelly BLU Tag (BTHome v2)",
                                "BTHome v2 Tag",
                            ):
                                return classified
                dev_text = " ".join(
                    str(x or "")
                    for x in (
                        dev_entry.manufacturer,
                        dev_entry.model,
                        dev_entry.name_by_user,
                        dev_entry.name,
                    )
                ).lower()
                if "shelly" in dev_text:
                    return "Shelly BLU Tag (BTHome v2)"
            return "BTHome v2 Tag"

        if (ent_entry is not None and ent_entry.platform == "ibeacon") or (
            _extract_ibeacon_entity_identity(hass, ent_entry, st) is not None
        ):
            return "iBeacon Tag"

        return "Private BLE (phone or watch)"

    low = addr.lower()
    if low.startswith("bthome:"):
        return "BTHome v2 Tag"
    if low.startswith("eddystone:"):
        return "Eddystone-UID Beacon"
    if low.startswith("ibeacon:"):
        return "iBeacon Tag"

    m_int = _mac_to_int(addr)
    if m_int is not None:
        live_adv = live_by_mac.get(_int_to_mac(m_int))
        if live_adv is not None:
            classified = classify_ble_advertisement_kind(
                live_adv["local_name"],
                live_adv["mfg_data"],
                live_adv["service_data"],
                live_adv["service_uuids"],
                is_private_ble=False,
            )
            if classified in (
                "Tile Tracker",
                "iTag Keychain Tag",
                "Shelly BLU Tag (BTHome v2)",
                "BTHome v2 Tag",
                "RuuviTag Beacon",
                "Eddystone-UID Beacon",
            ):
                return classified
            apple_b = live_adv["mfg_data"].get(APPLE_COMPANY_ID)
            if (
                apple_b is not None
                and len(apple_b) >= 20
                and apple_b[:2] == IBEACON_PREFIX
            ):
                return "iBeacon Tag"
        return "BLE beacon or tag"

    hex_clean = low.replace("-", "")
    if len(hex_clean) == 32 and all(ch in "0123456789abcdef" for ch in hex_clean):
        for adv_entry in live_by_mac.values():
            for k_svc, v_svc in adv_entry["service_data"].items():
                if (
                    _extract_uuid16(k_svc) == "feaa"
                    and len(v_svc) >= 18
                    and (v_svc[0] & 0xF0) == 0x00
                    and bytes(v_svc[2:18]).hex().lower() == hex_clean
                ):
                    return "Eddystone-UID Beacon"
        if "-" not in addr and ":" not in addr and "_" not in addr and addr == addr.upper():
            return "Eddystone-UID Beacon"
        return "iBeacon Tag"
    if len(hex_clean) == 20 and all(ch in "0123456789abcdef" for ch in hex_clean):
        return "Eddystone-UID Beacon"
    if parse_ibeacon_identity(addr) is not None:
        return "iBeacon Tag"
    return "BLE beacon or tag"


def inspect_companion_ble_transmitter(
    hass: HomeAssistant, target_address: str
) -> dict[str, str] | None:
    """Return live state, TX power, and advertise mode when `target_address` is a Companion App BLE Transmitter."""
    addr = str(target_address or "").strip()
    if "." not in addr:
        return None
    ent_entry = er.async_get(hass).async_get(addr)
    is_companion = (
        _is_mobile_app_ble_emitter(ent_entry)
        if ent_entry is not None
        else addr.lower().endswith(("_ble_transmitter", "_ble_emitter"))
    )
    if not is_companion:
        return None
    st = hass.states.get(addr)
    if st is None:
        return None
    return {
        "state": str(st.state or "").strip(),
        "tx_power": str(
            st.attributes.get("Transmitting power")
            or st.attributes.get("transmitting_power")
            or ""
        ).strip(),
        "advertise_mode": str(
            st.attributes.get("Advertise mode")
            or st.attributes.get("advertise_mode")
            or ""
        ).strip(),
    }


def classify_ble_target_category(
    hass: HomeAssistant, target_address: str, configured_category: str = "auto"
) -> str:
    """Resolve a managed BLE subentry's effective category (`phone` vs. `ble_tag`)."""
    cfg_norm = str(configured_category or "auto").strip().lower()
    if cfg_norm in ("phone", "ble_tag"):
        return cfg_norm

    addr = str(target_address or "").strip()
    if "." in addr:
        ent_entry = er.async_get(hass).async_get(addr)
        st = hass.states.get(addr)
        if (
            (ent_entry is not None and ent_entry.platform == "mobile_app")
            or addr.lower().endswith(("_ble_transmitter", "_ble_emitter"))
            or (
                ent_entry is not None
                and ent_entry.unique_id
                and str(ent_entry.unique_id).lower().endswith("_ble_emitter")
            )
        ):
            return "phone"
        if (
            (ent_entry is not None and ent_entry.platform == "private_ble_device")
            or "private_ble" in addr.lower()
            or (st is not None and st.attributes.get("current_address"))
        ):
            model_lbl = describe_ble_target_model(hass, addr)
            if "airpods" in model_lbl.lower():
                return "ble_tag"
            return "phone"
    return "ble_tag"


def get_discovered_ble_candidates(
    hass: HomeAssistant, onboarded_slugs: set[str], onboarded_addresses: set[str]
) -> list[dict[str, Any]]:
    """Discover phones and BLE tags (HA Companion App, Private BLE, iBeacon, BTHome, Tile, iTag, RuuviTag, Eddystone)."""
    candidates: list[dict[str, Any]] = []
    seen_targets: set[str] = {str(a).strip().lower() for a in onboarded_addresses if a and str(a).strip()}
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    area_reg = ar.async_get(hass)
    live_by_mac, live_ibeacons = _index_live_ble_advertisements(hass)

    onboarded_ibeacons: set[tuple[str, int | None, int | None]] = set()
    onboarded_uuid_only: set[str] = set()
    for raw_onb in onboarded_addresses:
        clean_onb = str(raw_onb or "").strip()
        if not clean_onb:
            continue
        if "." in clean_onb:
            st_onb = hass.states.get(clean_onb)
            ent_onb = ent_reg.async_get(clean_onb)
            ib_onb = _extract_ibeacon_entity_identity(hass, ent_onb, st_onb)
            if ib_onb is not None:
                onboarded_ibeacons.add(ib_onb)
            if st_onb is not None:
                cur_onb_mac = str(
                    st_onb.attributes.get("current_address")
                    or st_onb.attributes.get("mac")
                    or st_onb.attributes.get("address")
                    or ""
                ).strip()
                if cur_onb_mac:
                    seen_targets.add(cur_onb_mac.lower())
        else:
            ib_onb = parse_ibeacon_identity(clean_onb)
            if ib_onb is not None:
                onboarded_ibeacons.add(ib_onb)
                if ib_onb[1] is None and ib_onb[2] is None:
                    onboarded_uuid_only.add(ib_onb[0])

    all_entities = _iter_entities(ent_reg)
    companion_app_beacons: set[tuple[str, int | None, int | None]] = set()

    # 1. Direct 1-click Home Assistant Companion App BLE Transmitter discovery
    for entry in all_entities:
        if entry.disabled_by or not _is_mobile_app_ble_emitter(entry):
            continue
        st = hass.states.get(entry.entity_id)
        if st is None or str(st.state or "").strip().lower() in (
            "disabled",
            "stopped",
            "off",
            "unavailable",
        ):
            continue
        raw_id = str(
            st.attributes.get("id") or st.attributes.get("uuid") or ""
        ).strip()
        parsed_ib = (
            parse_ibeacon_identity(
                raw_id,
                st.attributes.get("major"),
                st.attributes.get("minor"),
            )
            if raw_id
            else None
        )
        if parsed_ib is None:
            continue
        uuid_hex, maj, min_ = parsed_ib
        companion_app_beacons.add((uuid_hex, maj, min_))

        live_hit = (
            live_ibeacons.get((uuid_hex, maj, min_))
            if (maj is not None or min_ is not None)
            else live_ibeacons.get((uuid_hex, None, None))
        )
        if live_hit is not None and live_hit.get("mac"):
            seen_targets.add(str(live_hit["mac"]).lower())

        uuid_dashed = _format_uuid_dashed(uuid_hex)
        if (
            entry.entity_id.lower() in seen_targets
            or uuid_hex in seen_targets
            or uuid_dashed.lower() in seen_targets
            or (uuid_hex, maj, min_) in onboarded_ibeacons
            or uuid_hex in onboarded_uuid_only
        ):
            seen_targets.add(entry.entity_id.lower())
            continue

        friendly = ""
        if entry.device_id:
            dev_entry = dev_reg.async_get(entry.device_id)
            if dev_entry is not None:
                friendly = str(dev_entry.name_by_user or dev_entry.name or "").strip()
        if not friendly:
            friendly = (
                str(st.attributes.get("friendly_name") or "")
                or entry.name
                or entry.original_name
                or entry.entity_id
            ).strip()
            for sfx in (" BLE Transmitter", " BLE Emitter"):
                if friendly.lower().endswith(sfx.lower()):
                    friendly = friendly[: -len(sfx)].strip()
                    break

        cand_slug = normalize_device_slug(friendly)
        if (
            not cand_slug
            or cand_slug == "esphome_device"
            or cand_slug in onboarded_slugs
        ):
            seen_targets.add(entry.entity_id.lower())
            continue

        seen_targets.add(entry.entity_id.lower())
        mm_suffix = (
            f" • {maj}:{min_}" if maj is not None and min_ is not None else ""
        )
        kind_lbl = f"HA Companion App ({uuid_dashed}{mm_suffix})"
        rssi_int = live_hit["rssi"] if live_hit is not None else None
        area_name = str(live_hit["area_name"]) if live_hit is not None else ""
        scanner_str = str(live_hit["scanner"]) if live_hit is not None else ""
        rssi_str = f" ({rssi_int} dBm)" if rssi_int is not None else ""
        area_str = f" • {area_name}" if area_name else ""
        candidates.append(
            {
                "slug": cand_slug,
                "title": friendly,
                "target_address": entry.entity_id,
                "kind": kind_lbl,
                "is_tracker": True,
                "rssi": rssi_int,
                "area_name": area_name,
                "scanner": scanner_str,
                "label": f"{friendly} [{kind_lbl}]{rssi_str}{area_str}",
            }
        )

    # 2. Deduplicate `private_ble_device`, `ibeacon`, and `bthome` by `device_id` (preferring `device_tracker`)
    raw_reg_entries: list[er.RegistryEntry] = []
    for entry in all_entities:
        if entry.disabled_by:
            continue
        if entry.platform not in ("private_ble_device", "ibeacon", "bthome"):
            continue
        if entry.domain not in ("device_tracker", "sensor", "binary_sensor"):
            continue
        if entry.platform != "bthome":
            if entry.domain == "binary_sensor":
                continue
            if entry.domain == "sensor" and not entry.entity_id.endswith(
                "estimated_distance"
            ):
                continue
        elif entry.domain in ("sensor", "binary_sensor") and not any(
            entry.entity_id.endswith(sfx)
            for sfx in ("signal_strength", "battery", "motion", "button")
        ):
            continue
        raw_reg_entries.append(entry)

    def _domain_rank(ent: er.RegistryEntry) -> int:
        if ent.domain == "device_tracker":
            return 0
        if ent.domain == "sensor":
            return 1
        return 2

    by_dev_id: dict[tuple[str, str], list[er.RegistryEntry]] = {}
    devless_entries: list[er.RegistryEntry] = []
    for entry in raw_reg_entries:
        if entry.device_id:
            by_dev_id.setdefault((entry.platform, entry.device_id), []).append(entry)
        else:
            devless_entries.append(entry)

    deduped_entries: list[er.RegistryEntry] = []
    for grp_entries in by_dev_id.values():
        if any(e.entity_id.lower() in seen_targets for e in grp_entries):
            for e in grp_entries:
                seen_targets.add(e.entity_id.lower())
            continue
        grp_entries.sort(
            key=lambda e: (
                _domain_rank(e),
                hass.states.get(e.entity_id) is None,
                e.entity_id,
            )
        )
        deduped_entries.append(grp_entries[0])
    deduped_entries.extend(devless_entries)

    def _clean_entity_friendly(ent: er.RegistryEntry, st_obj: Any) -> str:
        dev_entry = (
            dev_reg.async_get(ent.device_id) if ent.device_id else None
        )
        if dev_entry is not None and dev_entry.name_by_user:
            return str(dev_entry.name_by_user).strip()
        friendly_raw = (
            str(st_obj.attributes.get("friendly_name") if st_obj else "")
            or ent.name
            or ent.original_name
            or (str(dev_entry.name or "") if dev_entry else "")
            or ent.entity_id
        ).strip()
        for suffix in (
            " Estimated Distance",
            " Signal Strength",
            "Signal Strength",
            " Battery",
            " Motion",
            " Button",
        ):
            if friendly_raw.endswith(suffix):
                friendly_raw = friendly_raw[: -len(suffix)].strip()
        return friendly_raw

    # Consolidate rotating-MAC `ibeacon` duplicates sharing `(uuid_hex, major, minor)` & suppress Companion App overlaps
    ibeacon_groups: dict[
        tuple[str, int | None, int | None],
        list[tuple[er.RegistryEntry, Any, str, int | None]],
    ] = {}
    final_entity_items: list[tuple[er.RegistryEntry, bool]] = []

    for entry in deduped_entries:
        if entry.platform != "ibeacon":
            final_entity_items.append((entry, False))
            continue
        st = hass.states.get(entry.entity_id)
        ib_key = _extract_ibeacon_entity_identity(hass, entry, st)
        if ib_key is not None:
            u_hex, maj, min_ = ib_key
            u_dashed = _format_uuid_dashed(u_hex)
            covered_by_companion = (
                (u_hex, maj, min_) in companion_app_beacons
                or (u_hex, None, None) in companion_app_beacons
                or (
                    maj is None
                    and min_ is None
                    and any(cu == u_hex for cu, _cmaj, _cmin in companion_app_beacons)
                )
            )
            covered_by_onboarded = (
                (u_hex, maj, min_) in onboarded_ibeacons
                or u_hex in onboarded_uuid_only
                or u_hex in seen_targets
                or u_dashed.lower() in seen_targets
            )
            if covered_by_companion or covered_by_onboarded:
                seen_targets.add(entry.entity_id.lower())
                continue
            friendly_lbl = _clean_entity_friendly(entry, st)
            st_rssi = st.attributes.get("rssi") if st else None
            rssi_num = (
                int(st_rssi)
                if isinstance(st_rssi, (int, float)) and not isinstance(st_rssi, bool)
                else None
            )
            if rssi_num is None:
                live_ib = (
                    live_ibeacons.get((u_hex, maj, min_))
                    if (maj is not None or min_ is not None)
                    else live_ibeacons.get((u_hex, None, None))
                )
                if live_ib is not None:
                    rssi_num = live_ib["rssi"]
            ibeacon_groups.setdefault(ib_key, []).append(
                (entry, st, friendly_lbl, rssi_num)
            )
        else:
            final_entity_items.append((entry, False))

    for ib_items in ibeacon_groups.values():
        if any(it[0].entity_id.lower() in seen_targets for it in ib_items):
            for it in ib_items:
                seen_targets.add(it[0].entity_id.lower())
            continue
        ib_items.sort(
            key=lambda it: (
                _domain_rank(it[0]),
                1 if _TRAILING_ROTATING_HEX4_RE.search(it[2]) else 0,
                -(it[3] if it[3] is not None else -999),
                it[0].entity_id,
            )
        )
        final_entity_items.append((ib_items[0][0], len(ib_items) > 1))

    for entry, consolidated_dup in final_entity_items:
        st = hass.states.get(entry.entity_id)
        friendly = _clean_entity_friendly(entry, st)
        if consolidated_dup:
            friendly = _TRAILING_ROTATING_HEX4_RE.sub("", friendly).strip() or friendly
        cand_slug = normalize_device_slug(friendly)
        if (
            not cand_slug
            or cand_slug == "esphome_device"
            or cand_slug in onboarded_slugs
            or entry.entity_id.lower() in seen_targets
        ):
            continue
        seen_targets.add(entry.entity_id.lower())

        rssi_val = st.attributes.get("rssi") if st else None
        rssi_int = (
            int(rssi_val)
            if isinstance(rssi_val, (int, float)) and not isinstance(rssi_val, bool)
            else None
        )
        src_scanner = str(st.attributes.get("source") or "").strip() if st else ""
        a_id = _resolve_scanner_area_id(hass, src_scanner) if src_scanner else None
        a_obj = area_reg.async_get_area(a_id) if a_id else None
        area_name = a_obj.name if a_obj else ""

        if entry.platform == "private_ble_device":
            cur_mac = str(
                (st.attributes.get("current_address") if st else "") or ""
            ).strip().upper()
            if cur_mac:
                seen_targets.add(cur_mac.lower())
            live_adv = live_by_mac.get(cur_mac) if cur_mac else None
            if live_adv is not None:
                kind_lbl = classify_ble_advertisement_kind(
                    live_adv["local_name"],
                    live_adv["mfg_data"],
                    live_adv["service_data"],
                    live_adv["service_uuids"],
                    is_private_ble=True,
                )
                if rssi_int is None and live_adv["rssi"] is not None:
                    rssi_int = live_adv["rssi"]
                if not area_name and live_adv["area_name"]:
                    area_name = str(live_adv["area_name"])
                if not src_scanner and live_adv["scanner"]:
                    src_scanner = str(live_adv["scanner"])
            else:
                kind_lbl = classify_ble_advertisement_kind(
                    "", {}, {}, (), is_private_ble=True
                )
        elif entry.platform == "bthome":
            kind_lbl = "BTHome v2 Tag"
            dev_entry = (
                dev_reg.async_get(entry.device_id) if entry.device_id else None
            )
            if dev_entry is not None:
                for _ct, cv in dev_entry.connections:
                    m_int = _mac_to_int(str(cv))
                    if m_int is not None:
                        mac_fmt = _int_to_mac(m_int)
                        seen_targets.add(mac_fmt.lower())
                        live_adv = live_by_mac.get(mac_fmt)
                        if live_adv is not None:
                            classified_bt = classify_ble_advertisement_kind(
                                live_adv["local_name"],
                                live_adv["mfg_data"],
                                live_adv["service_data"],
                                live_adv["service_uuids"],
                                is_private_ble=False,
                            )
                            if classified_bt in (
                                "Shelly BLU Tag (BTHome v2)",
                                "BTHome v2 Tag",
                            ):
                                kind_lbl = classified_bt
                            if rssi_int is None and live_adv["rssi"] is not None:
                                rssi_int = live_adv["rssi"]
                            if not area_name and live_adv["area_name"]:
                                area_name = str(live_adv["area_name"])
                            if not src_scanner and live_adv["scanner"]:
                                src_scanner = str(live_adv["scanner"])
        else:
            ib_key = _extract_ibeacon_entity_identity(hass, entry, st)
            if ib_key is not None:
                u_hex, maj, min_ = ib_key
                live_ib = (
                    live_ibeacons.get((u_hex, maj, min_))
                    if (maj is not None or min_ is not None)
                    else live_ibeacons.get((u_hex, None, None))
                )
                if live_ib is not None:
                    if live_ib.get("mac"):
                        seen_targets.add(str(live_ib["mac"]).lower())
                    if rssi_int is None and live_ib["rssi"] is not None:
                        rssi_int = live_ib["rssi"]
                    if not area_name and live_ib["area_name"]:
                        area_name = str(live_ib["area_name"])
                    if not src_scanner and live_ib["scanner"]:
                        src_scanner = str(live_ib["scanner"])
                u_dashed = _format_uuid_dashed(u_hex)
                mm = (
                    f" • {maj}:{min_}"
                    if maj is not None and min_ is not None
                    else ""
                )
                kind_lbl = f"iBeacon Tag ({u_dashed}{mm})"
            else:
                kind_lbl = "iBeacon Tag"

        rssi_str = f" ({rssi_int} dBm)" if rssi_int is not None else ""
        area_str = f" • {area_name}" if area_name else ""
        candidates.append(
            {
                "slug": cand_slug,
                "title": friendly,
                "target_address": entry.entity_id,
                "kind": kind_lbl,
                "is_tracker": True,
                "rssi": rssi_int,
                "area_name": area_name,
                "scanner": src_scanner,
                "label": f"{friendly} [{kind_lbl}]{rssi_str}{area_str}",
            }
        )

    # 3. Ambient scanner-table discovery (excluding rolling-EID cloud Find frames)
    best_by_addr: dict[str, dict[str, Any]] = {}
    for addr_str, adv_entry in live_by_mac.items():
        local_name = str(adv_entry["local_name"] or "").strip()
        mfg_data: Mapping[int, bytes] = adv_entry["mfg_data"]
        svc_data: Mapping[str, bytes] = adv_entry["service_data"]
        svc_uuids: Iterable[str] = adv_entry["service_uuids"]

        if _is_excluded_cloud_find_adv(local_name, mfg_data, svc_data):
            continue

        apple_b = mfg_data.get(APPLE_COMPANY_ID)
        if (
            apple_b is not None
            and len(apple_b) >= 20
            and apple_b[:2] == IBEACON_PREFIX
        ):
            ib_u = apple_b[2:18].hex().lower()
            ib_maj = (apple_b[18] << 8) | apple_b[19]
            ib_min = (
                ((apple_b[20] << 8) | apple_b[21])
                if len(apple_b) >= 22
                else None
            )
            if (
                (ib_u, ib_maj, ib_min) in companion_app_beacons
                or (ib_u, ib_maj, ib_min) in onboarded_ibeacons
                or ib_u in onboarded_uuid_only
            ):
                continue

        eddystone_uid_target = ""
        for k_svc, v_svc in svc_data.items():
            if (
                _extract_uuid16(k_svc) == "feaa"
                and isinstance(v_svc, (bytes, bytearray))
                and len(v_svc) >= 18
                and (v_svc[0] & 0xF0) == 0x00
            ):
                eddystone_uid_target = bytes(v_svc[2:18]).hex().upper()
                break

        target_key = eddystone_uid_target or addr_str
        if target_key.lower() in seen_targets or addr_str.lower() in seen_targets:
            continue

        kind_lbl = classify_ble_advertisement_kind(
            local_name,
            mfg_data,
            svc_data,
            svc_uuids,
            is_private_ble=False,
        )
        title = local_name
        if not title:
            if kind_lbl == "Tile Tracker":
                title = f"Tile Tracker {addr_str[-5:]}"
            elif kind_lbl == "Shelly BLU Tag (BTHome v2)":
                title = f"Shelly BLU {addr_str[-5:]}"
            elif kind_lbl == "BTHome v2 Tag":
                title = f"BTHome {addr_str[-5:]}"
            elif kind_lbl == "RuuviTag Beacon":
                title = f"RuuviTag {addr_str[-5:]}"
            elif kind_lbl == "Eddystone-UID Beacon" and eddystone_uid_target:
                title = f"Eddystone {addr_str[-5:]}"
            elif kind_lbl == "iTag Keychain Tag":
                title = f"iTag {addr_str[-5:]}"
            else:
                continue

        cand_slug = normalize_device_slug(title)
        if (
            not cand_slug
            or cand_slug == "esphome_device"
            or cand_slug in onboarded_slugs
        ):
            continue

        rssi_int = adv_entry["rssi"]
        area_name = str(adv_entry["area_name"] or "")
        scanner_name = str(adv_entry["scanner"] or "")
        prev = best_by_addr.get(target_key)
        if prev is None or (
            rssi_int is not None
            and (prev["rssi"] is None or rssi_int > prev["rssi"])
        ):
            rssi_str = f" ({rssi_int} dBm)" if rssi_int is not None else ""
            area_str = f" • {area_name}" if area_name else ""
            best_by_addr[target_key] = {
                "slug": cand_slug,
                "title": title,
                "target_address": target_key,
                "kind": kind_lbl,
                "is_tracker": not kind_lbl.startswith("Named BLE"),
                "rssi": rssi_int,
                "area_name": area_name,
                "scanner": scanner_name,
                "label": f"{title} [{kind_lbl}]{rssi_str}{area_str}",
            }

    for addr_str, item in best_by_addr.items():
        seen_targets.add(addr_str.lower())
        candidates.append(item)

    candidates.sort(
        key=lambda x: (
            not bool(x.get("is_tracker", True)),
            x.get("rssi") is None,
            -(int(x["rssi"]) if x.get("rssi") is not None else -999),
            str(x.get("title") or "").lower(),
        )
    )
    return candidates[:60]
