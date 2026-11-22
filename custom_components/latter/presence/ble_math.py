"""Pure-stdlib BLE spatial scoring math, path-loss distance, and Voice Follows Me dwell gate (`L0b`)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
import math
import re
from typing import Final

from ..const import DEFAULT_BLE_ATTENUATION

HYSTERESIS_DB: Final = 5.0
RSSI_HYSTERESIS_DEADBAND_DBM: Final = 3.0
FAST_OVERRIDE_DB: Final = 8.0
CROSS_FLOOR_ATTENUATION_DB: Final = 6.0
STALE_PROXY_SECONDS: Final = 12.0
SILENCE_GRACE_SECONDS: Final = 2.0
SILENCE_DECAY_DB_PER_S: Final = 1.5
MIN_HOLD_SECONDS: Final = 4.0
MIN_WINNING_RSSI_DBM: Final = -88.0
NO_SIGNAL_RSSI_DBM: Final = -100.0
TX_POWER_1M_DBM: Final = -59.0
PATH_LOSS_EXPONENT: Final = DEFAULT_BLE_ATTENUATION
CORROBORATION_BONUS_DB: Final = 1.5
CORROBORATION_MIN_DBM: Final = -82.0
SIGNATURE_PEAK_SCORE_DBM: Final = -45.0
SIGNATURE_RING_WINDOW_SECONDS: Final = 12.0
SIGNATURE_CAPTURE_WINDOW_SECONDS: Final = 15.0
SIGNATURE_RING_MAX_SAMPLES: Final = 32
WAKE_COALESCE_SECONDS: Final = 0.35
KALMAN_MEASUREMENT_VAR: Final = 9.0
EDDYSTONE_UUID_PREFIX: Final = "0000feaa"
BTHOME_UUID_PREFIX: Final = "0000fcd2"
COMPANION_TX_POWER_1M_DBM: Final[dict[str, float]] = {
    "ultralow": -81.0,
    "low": -75.0,
    "medium": -67.0,
    "high": -59.0,
}

NON_AREA_STATES: Final[frozenset[str]] = frozenset(
    {"", "unknown", "unavailable", "none", "away", "not_home"}
)

_MIN_REF_POWER_DBM: Final = -90.0
_MAX_REF_POWER_DBM: Final = -30.0
_DEFAULT_TX_TOLERANCE_DB: Final = 0.5
_MIN_CORROBORATED_PACKETS: Final = 2
_SCORE_ROUND_DIGITS: Final = 6
_PATH_LOSS_SCALE: Final = 10.0
_MIN_REPORTED_DIST_M: Final = 0.2
_MAX_REPORTED_DIST_M: Final = 50.0
_MIN_CONTINUOUS_DIST_M: Final = 0.05
_MAX_CONTINUOUS_DIST_M: Final = 100.0
_CLOCK_TOLERANCE_S: Final = 0.25


def safe_rssi_int(val: object) -> int | None:
    """Coerce raw RSSI to `int`, rejecting booleans, `NaN`/`Inf`, and non-numeric values."""
    if val is None or isinstance(val, bool) or not isinstance(val, (int, float, str)):
        return None
    if isinstance(val, float) and not math.isfinite(val):
        return None
    try:
        parsed = float(val)
        if not math.isfinite(parsed):
            return None
        return int(parsed)
    except (TypeError, ValueError, OverflowError):
        return None


_safe_rssi_int = safe_rssi_int


def resolve_companion_tx_ref_power_dbm(
    measured_power: object, tx_power_level: object
) -> float | None:
    """Resolve 1 m reference power for a Home Assistant Companion App BLE Transmitter.

    Android's Companion App defaults `Transmitting power` to `ultraLow` (-21 dBm TX) while
    leaving `Measured power` at the uncalibrated `-59` default (both in entity attributes
    and iBeacon byte 22). When `Measured power` is unset or left at `-59`, compensate using
    the reported `Transmitting power` tier so 1 m path-loss and Area Signatures stay aligned.
    """
    mp_f: float | None = None
    if (
        measured_power is not None
        and not isinstance(measured_power, bool)
        and isinstance(measured_power, (int, float, str))
    ):
        try:
            cand = float(measured_power)
            if math.isfinite(cand) and _MIN_REF_POWER_DBM <= cand <= _MAX_REF_POWER_DBM:
                mp_f = cand
        except (TypeError, ValueError):
            mp_f = None
    tx_key = re.sub(r"[^a-z]", "", str(tx_power_level or "").lower())
    if tx_key in COMPANION_TX_POWER_1M_DBM and (
        mp_f is None or abs(mp_f - TX_POWER_1M_DBM) < _DEFAULT_TX_TOLERANCE_DB
    ):
        return COMPANION_TX_POWER_1M_DBM[tx_key]
    return mp_f


def within_rssi_deadband(prev_rssi: float | None, new_rssi: float) -> bool:
    """Return True when `new_rssi` stays within the 3.0 dBm hysteresis deadband of `prev_rssi`."""
    if prev_rssi is None:
        return False
    return abs(float(new_rssi) - float(prev_rssi)) < RSSI_HYSTERESIS_DEADBAND_DBM


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
    challenger_packet_count: int = _MIN_CORROBORATED_PACKETS,
) -> AreaDecision | None:
    """Pick the best-scoring Area and decide whether the Device moves there."""
    if not scores:
        return None
    best_area_id, best_score = min(
        scores.items(),
        key=lambda item: (
            -round(item[1], _SCORE_ROUND_DIGITS),
            item[0] != current_area_id,
            item[0],
        ),
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
        challenger_packet_count >= _MIN_CORROBORATED_PACKETS
        or current_area_id not in scores
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
    """Estimate distance in meters with a log-distance path-loss model."""
    eff_n = max(1.0, float(attenuation))
    raw_dist = math.pow(
        10.0,
        (float(ref_power_dbm) - float(rssi_dbm)) / (_PATH_LOSS_SCALE * eff_n),
    )
    return round(max(_MIN_REPORTED_DIST_M, min(_MAX_REPORTED_DIST_M, raw_dist)), 1)


def continuous_distance_m(norm_dbm: float, attenuation: float) -> float:
    """Return unrounded distance in meters for continuous velocity gating."""
    eff_n = max(1.0, float(attenuation))
    raw_dist = math.pow(
        10.0,
        (TX_POWER_1M_DBM - float(norm_dbm)) / (_PATH_LOSS_SCALE * eff_n),
    )
    return max(_MIN_CONTINUOUS_DIST_M, min(_MAX_CONTINUOUS_DIST_M, raw_dist))


_continuous_distance_m = continuous_distance_m


def distance_m_to_norm_dbm(dist_m: float, attenuation: float) -> float:
    """Return the analytical inverse of `continuous_distance_m` in normalized 1 m-equivalent dBm."""
    eff_n = max(1.0, float(attenuation))
    return TX_POWER_1M_DBM - (
        _PATH_LOSS_SCALE * eff_n * math.log10(max(_MIN_CONTINUOUS_DIST_M, float(dist_m)))
    )


_distance_m_to_norm_dbm = distance_m_to_norm_dbm


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
        self,
        target_area_id: str | None,
        *,
        ble_driven: bool,
        dwell_s: float,
        now: float,
    ) -> FollowAction:
        """Register an Area update and return what to do now."""
        if target_area_id is None or not is_area_id(target_area_id):
            self.cancel()
            return FollowAction.IGNORE
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
