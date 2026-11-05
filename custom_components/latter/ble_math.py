"""BLE Area scoring math for Latter's native BLE tracker.

Standard library only (no Home Assistant imports), so the unit tests exercise this exact code.
`ble_engine.LatterNativeBleTracker` feeds it per-Area smoothed RSSI and applies the result.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

EMA_ALPHA = 0.50
HYSTERESIS_DB = 5.0
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


def smooth_rssi(
    prev: tuple[float, float] | None, raw_rssi: float, obs_time: float
) -> float:
    """Return the EMA of `raw_rssi` over `prev` = (ema, last_seen); restart when `prev` is stale or missing."""
    if prev is None or (obs_time - prev[1]) > STALE_PROXY_SECONDS:
        return float(raw_rssi)
    return (EMA_ALPHA * float(raw_rssi)) + ((1.0 - EMA_ALPHA) * prev[0])


def score_areas(
    area_rssi: Mapping[str, tuple[float, float]],
    now: float,
    is_cross_floor: Callable[[str], bool],
) -> dict[str, float]:
    """Score fresh Areas: effective RSSI minus silence decay, minus the cross-floor penalty where it applies.

    `area_rssi` maps area_id -> (effective EMA RSSI, last_seen). Areas silent for longer than
    STALE_PROXY_SECONDS are dropped. After SILENCE_GRACE_SECONDS of silence an Area loses
    SILENCE_DECAY_DB_PER_S per second, so a newly entered Area can overtake one the Device left.
    """
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
    """Pick the best-scoring Area and decide whether the Device moves there.

    Returns None when no Area is fresh or the best one is weaker than MIN_WINNING_RSSI_DBM.
    With no current Area the best one is taken at once. Otherwise a challenger needs
    FAST_OVERRIDE_DB over the current Area, or HYSTERESIS_DB once MIN_HOLD_SECONDS have
    passed since the last switch.
    """
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
