"""Multi-scanner `LatterNativeBleTracker`, Kalman velocity-gated RSSI filter, vector signature scorer, and target/RPA matcher."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import logging
import math
import re
import time
from typing import Any, Final, Protocol

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from ..const import (
    DEFAULT_BLE_ATTENUATION,
    DEFAULT_BLE_AWAY_TIMEOUT_S,
    DEFAULT_BLE_BEACON_UUID,
    DEFAULT_BLE_MAX_RADIUS_M,
    DEFAULT_BLE_MAX_VELOCITY_MPS,
)
from ..hub_registry import peek_domain_data
from ..identity import get_bound_esphome_device, read_device_hardware_manifest
from .ble_math import (
    CORROBORATION_BONUS_DB,
    CORROBORATION_MIN_DBM,
    CROSS_FLOOR_ATTENUATION_DB,
    EDDYSTONE_UUID_PREFIX,
    KALMAN_MEASUREMENT_VAR,
    RSSI_HYSTERESIS_DEADBAND_DBM,
    SIGNATURE_CAPTURE_WINDOW_SECONDS,
    SIGNATURE_PEAK_SCORE_DBM,
    SIGNATURE_RING_MAX_SAMPLES,
    SIGNATURE_RING_WINDOW_SECONDS,
    SILENCE_DECAY_DB_PER_S,
    SILENCE_GRACE_SECONDS,
    STALE_PROXY_SECONDS,
    TX_POWER_1M_DBM,
    WAKE_COALESCE_SECONDS,
    AreaDecision,
    ScannerObservationState,
    continuous_distance_m,
    decide_area,
    distance_m_to_norm_dbm,
    resolve_companion_tx_ref_power_dbm,
    rssi_to_distance_m,
    safe_rssi_int,
    within_rssi_deadband,
)
from .ble_registry import (
    APPLE_COMPANY_ID,
    IBEACON_PREFIX,
    MATCHED_BLE_ADDRESS_TTL_SECONDS,
    SURVEY_RETENTION_SECONDS,
    WAKE_GAP_SECONDS,
    clear_scanner_area_cache,
    coerce_uint16,
    current_ble_scanners,
    extract_adv_ref_power_dbm,
    extract_ibeacon_entity_identity,
    get_ble_proxy_area_ids,
    int_to_mac,
    iter_devices,
    mac_to_int,
    normalize_uuid_hex,
    parse_ibeacon_identity,
    resolve_scanner_area_id,
)

_LOGGER = logging.getLogger(__name__)
_UNMAPPED: Final = "__unmapped__"
_MAX_MATCHED_ADDRESSES: Final = 64
_PERSISTED_MATCHED_ADDRESSES: Final = 8
_UUID_HEX_LEN: Final = 32
_EDDYSTONE_NS_HEX_LEN: Final = 20
_IBEACON_MIN_BYTES: Final = 20
_IBEACON_FULL_BYTES: Final = 22
_EDDYSTONE_MIN_SVC_BYTES: Final = 12
_EDDYSTONE_UID_MIN_BYTES: Final = 18
_EDDYSTONE_FRAME_MASK: Final = 0xF0
_MAX_OFFSET_DB: Final = 25.0
_MIN_REF_DBM: Final = -90.0
_MAX_REF_DBM: Final = -30.0
_MIN_ATTENUATION: Final = 1.5
_MAX_ATTENUATION: Final = 4.5
_MIN_RADIUS_M: Final = 2.0
_MAX_RADIUS_M: Final = 50.0
_MIN_VELOCITY_MPS: Final = 0.5
_MAX_VELOCITY_MPS: Final = 15.0
_MIN_AWAY_TIMEOUT_S: Final = 30.0
_MAX_AWAY_TIMEOUT_S: Final = 900.0
_MEDIAN_WINDOW_LEN: Final = 3
_INITIAL_KALMAN_VAR: Final = 6.0
_MIN_OBS_DT_S: Final = 0.05
_CLOCK_SKEW_RESET_S: Final = -1.0
_SPIKE_THRESHOLD_DB: Final = 6.0
_MAX_SPIKE_Q_VAR: Final = 36.0
_MIN_CONT_DIST_M: Final = 0.05
_MIN_PAIR_SCANNERS: Final = 2
_SIG_MISSING_MIN_MU_DBM: Final = -78.0
_SIG_UNEXPECTED_MIN_DBM: Final = -75.0
_SCORE_ROUND_DIGITS: Final = 6
_ESP_MAC_OFFSETS: Final[tuple[int, ...]] = (-2, -1, 0, 1, 2)
_RECENT_WAKE_PACKET_S: Final = 6.0
_ESP_ADJACENT_MAC_DELTA: Final = 2
_MISSING_RSSI_SENTINEL: Final = -999
_MIN_VALID_RSSI_DBM: Final = -100
_MAX_FUTURE_SKEW_S: Final = 60.0
_POLL_DEDUPE_EPS_S: Final = 1e-4
_ADV_DEDUPE_EPS_S: Final = 1e-6
_EARLY_MAC_DISCOVERY_PKTS: Final = 3
_MIN_CORROBORATED_SCANNERS: Final = 2


class BleFabricPort(Protocol):
    """Port implemented by `LatterBleFabric` without introducing a tracker -> fabric import cycle."""

    def has_tracker(self, tracker: Any) -> bool:
        """Return True if `tracker` is currently registered on the fabric."""

    def register_tracker(self, tracker: Any) -> None:
        """Register `tracker` with the shared passive BLE scanner fabric."""

    def unregister_tracker(self, tracker: Any) -> None:
        """Unregister `tracker` from the shared BLE scanner fabric."""

    def sync_tracker_addresses(self) -> None:
        """Refresh per-MAC advertisement subscriptions across active trackers."""

    def seed_tracker_from_scanners_once(
        self, tracker: Any, *, only_address: str = ""
    ) -> None:
        """Seed `tracker` from live Home Assistant Bluetooth scanner state."""

    def notify_occupancy_listeners(self) -> None:
        """Notify subscribed Area and person occupancy entities."""

    def emit_survey_delta(self, tracker: Any) -> None:
        """Push live survey telemetry for `tracker` to active Studio subscribers."""


_FABRIC_GETTER: Callable[[HomeAssistant], BleFabricPort] | None = None


def register_ble_fabric_getter(
    getter: Callable[[HomeAssistant], BleFabricPort],
) -> None:
    """Register the `LatterBleFabric` singleton accessor from `ble_fabric.py`."""
    global _FABRIC_GETTER
    _FABRIC_GETTER = getter


def get_active_ble_fabric(
    hass: HomeAssistant, *, create: bool = False
) -> BleFabricPort | None:
    """Return the active `LatterBleFabric` (creating it via registered getter when `create=True`)."""
    domain_data = peek_domain_data(hass)
    if domain_data is not None and domain_data.ble_fabric is not None:
        fabric_existing: BleFabricPort = domain_data.ble_fabric
        return fabric_existing
    if create and _FABRIC_GETTER is not None:
        return _FABRIC_GETTER(hass)
    return None


def discover_target_device_macs(
    hass: HomeAssistant, esphome_device_id: str | None
) -> set[int]:
    """Find known Wi-Fi/BLE MAC address integers (`+/-2`) for the bound ESPHome device."""
    dev = get_bound_esphome_device(hass, esphome_device_id)
    if dev is None:
        return set()

    mac_ints: set[int] = set()
    for _conn_type, conn_val in dev.connections:
        m_int = mac_to_int(str(conn_val))
        if m_int is not None:
            for offset in _ESP_MAC_OFFSETS:
                mac_ints.add(m_int + offset)
    for _domain, ident_val in dev.identifiers:
        m_int = mac_to_int(str(ident_val))
        if m_int is not None:
            for offset in _ESP_MAC_OFFSETS:
                mac_ints.add(m_int + offset)
    return mac_ints


def _median_of_recent(vals: list[float]) -> float:
    if len(vals) == 1:
        return vals[0]
    if len(vals) == 2:
        return 0.5 * (vals[0] + vals[1])
    return sorted(vals)[1]


def _apply_symmetric_velocity_gate(
    *,
    prev_x_dbm: float,
    pre_dbm: float,
    offset_db: float,
    ref_shift: float,
    attenuation: float,
    max_step_m: float,
) -> float:
    prev_norm = prev_x_dbm + offset_db - ref_shift
    cand_norm = pre_dbm + offset_db - ref_shift
    prev_dist = continuous_distance_m(prev_norm, attenuation)
    cand_dist = continuous_distance_m(cand_norm, attenuation)
    if pre_dbm < prev_x_dbm:
        max_allowed_dist = prev_dist + max_step_m
        if cand_dist > max_allowed_dist:
            return distance_m_to_norm_dbm(max_allowed_dist, attenuation) - offset_db + ref_shift
        return pre_dbm
    if pre_dbm > prev_x_dbm:
        min_allowed_dist = max(_MIN_CONT_DIST_M, prev_dist - max_step_m)
        if cand_dist < min_allowed_dist:
            return distance_m_to_norm_dbm(min_allowed_dist, attenuation) - offset_db + ref_shift
        return pre_dbm
    return pre_dbm


def update_scanner_kalman_state(
    scanner_states: dict[str, ScannerObservationState],
    norm_source: str,
    raw_rssi: int,
    obs_time: float,
    scanner_name: str,
    *,
    offset_db: float,
    ref_shift: float,
    attenuation: float,
    max_velocity_mps: float,
) -> ScannerObservationState:
    """Update per-scanner 3-sample median, symmetric velocity-gated Kalman filter, and ring buffer."""
    st = scanner_states.get(norm_source)
    raw_f = float(raw_rssi)
    if st is None:
        st = ScannerObservationState(
            source=norm_source,
            scanner_name=scanner_name or norm_source,
            raw_rssi=int(raw_rssi),
            recent_raw=[(obs_time, raw_f)],
            x_dbm=raw_f,
            p_var=_INITIAL_KALMAN_VAR,
            last_obs_time=obs_time,
            packet_count=1,
            ring_buffer=[(obs_time, raw_f)],
        )
        scanner_states[norm_source] = st
        return st

    if scanner_name and scanner_name.upper() != norm_source:
        st.scanner_name = scanner_name
    st.raw_rssi = int(raw_rssi)
    dt_raw = obs_time - st.last_obs_time

    if st.packet_count <= 0 or dt_raw > STALE_PROXY_SECONDS or dt_raw < _CLOCK_SKEW_RESET_S:
        st.recent_raw = [(obs_time, raw_f)]
        st.x_dbm = raw_f
        st.p_var = _INITIAL_KALMAN_VAR
        st.last_obs_time = obs_time
        st.packet_count = 1
    else:
        dt = max(_MIN_OBS_DT_S, dt_raw)
        st.recent_raw = [
            (ts, val)
            for ts, val in st.recent_raw
            if (obs_time - ts) <= STALE_PROXY_SECONDS
        ]
        st.recent_raw.append((obs_time, raw_f))
        if len(st.recent_raw) > _MEDIAN_WINDOW_LEN:
            st.recent_raw = st.recent_raw[-_MEDIAN_WINDOW_LEN:]

        pre_dbm = _median_of_recent([val for _ts, val in st.recent_raw])
        gated_dbm = _apply_symmetric_velocity_gate(
            prev_x_dbm=st.x_dbm,
            pre_dbm=pre_dbm,
            offset_db=offset_db,
            ref_shift=ref_shift,
            attenuation=attenuation,
            max_step_m=max_velocity_mps * dt,
        )

        q_var = 2.5 * dt
        delta_gated = abs(gated_dbm - st.x_dbm)
        if delta_gated > _SPIKE_THRESHOLD_DB:
            q_var += min(_MAX_SPIKE_Q_VAR, 0.25 * (delta_gated**2))
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


def _compute_pairwise_diff_rmse(
    src_meta: list[tuple[str, float, float, float]],
    fresh_norm: Mapping[str, float],
    fallback_rmse: float,
) -> float:
    pair_sq_err = 0.0
    pair_weight = 0.0
    for idx_a, (src_a, mu_a, sig_a, w_a) in enumerate(src_meta):
        for src_b, mu_b, sig_b, w_b in src_meta[idx_a + 1 :]:
            pw = math.sqrt(w_a * w_b)
            obs_delta = fresh_norm[src_a] - fresh_norm[src_b]
            sig_delta = mu_a - mu_b
            sigma_pair = math.hypot(sig_a, sig_b)
            p_err = abs(obs_delta - sig_delta) * (4.24264 / sigma_pair)
            pair_sq_err += pw * (p_err**2)
            pair_weight += pw
    return math.sqrt(pair_sq_err / pair_weight) if pair_weight > 0.0 else fallback_rmse


def score_signature_vector(
    area_id: str,
    sig: Mapping[str, Any],
    *,
    fresh_norm: Mapping[str, float],
    fresh_ages: Mapping[str, float],
    resolve_scanner_area: Callable[[str], str | None],
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
    src_meta: list[tuple[str, float, float, float]] = []

    for src, stats in sig_scanners.items():
        if not isinstance(stats, Mapping):
            continue
        mu = float(stats.get("mean", -75.0))
        sigma = max(2.5, float(stats.get("std", 3.5)))
        w = max(0.25, min(2.0, (mu - (-95.0)) / 25.0))
        if src in fresh_norm:
            diff = fresh_norm[src] - mu
            if diff > 0.0 and resolve_scanner_area(src) == area_id:
                diff *= 0.15
            eff_err = abs(diff) * (3.0 / sigma)
            weighted_sq_err += w * (eff_err**2)
            total_weight += w
            src_meta.append((src, mu, sigma, w))
        elif mu >= _SIG_MISSING_MIN_MU_DBM:
            missing_penalty += 6.0 + 0.65 * (mu - _SIG_MISSING_MIN_MU_DBM)

    if total_weight <= 0.0 or not src_meta:
        return None

    unexpected_penalty = sum(
        0.75 * (obs_val - _SIG_MISSING_MIN_MU_DBM)
        for obs_src, obs_val in fresh_norm.items()
        if obs_src not in sig_scanners and obs_val >= _SIG_UNEXPECTED_MIN_DBM
    )
    abs_rmse_db = math.sqrt(weighted_sq_err / total_weight)

    if len(src_meta) >= _MIN_PAIR_SCANNERS:
        diff_rmse_db = _compute_pairwise_diff_rmse(src_meta, fresh_norm, abs_rmse_db)
        combined_err_db = (
            0.45 * abs_rmse_db
            + 0.55 * diff_rmse_db
            + missing_penalty
            + unexpected_penalty
        )
    else:
        single_pen = 3.0 if len(sig_scanners) >= _MIN_PAIR_SCANNERS else 0.0
        combined_err_db = (
            abs_rmse_db + missing_penalty + unexpected_penalty + single_pen
        )

    min_age_s = min(fresh_ages[s] for s in matched_srcs)
    decay_db = SILENCE_DECAY_DB_PER_S * max(0.0, min_age_s - SILENCE_GRACE_SECONDS)
    score = SIGNATURE_PEAK_SCORE_DBM - (1.35 * combined_err_db) - decay_db
    if is_cross_floor(area_id):
        score -= CROSS_FLOOR_ATTENUATION_DB

    best_src = min(
        matched_srcs,
        key=lambda s: (-round(fresh_norm[s], _SCORE_ROUND_DIGITS), s),
    )
    return score, best_src


def _clean_scanner_offsets(offsets: Mapping[str, float]) -> dict[str, float]:
    cleaned: dict[str, float] = {}
    for k, v in offsets.items():
        if src_key := str(k or "").strip().upper():
            try:
                cleaned[src_key] = max(-_MAX_OFFSET_DB, min(_MAX_OFFSET_DB, float(v)))
            except (TypeError, ValueError):
                continue
    return cleaned


def _clean_area_signatures_map(
    area_signatures: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    cleaned: dict[str, dict[str, Any]] = {}
    for area_id, sig in area_signatures.items():
        raw_sc = sig.get("scanners") if (area_id and isinstance(sig, Mapping)) else None
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
                continue
        if norm_sc and isinstance(sig, Mapping):
            cleaned[str(area_id)] = {
                "scanners": norm_sc,
                "captured_at": str(sig.get("captured_at") or ""),
                "sample_count": int(sig.get("sample_count") or len(norm_sc)),
            }
    return cleaned


def _clamp_float_param(val: object, low: float, high: float, default: float) -> float:
    if isinstance(val, bool) or not isinstance(val, (int, float, str)):
        return default
    try:
        parsed = float(val)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, parsed)) if math.isfinite(parsed) else default


class LatterNativeBleTracker:
    """Multi-scanner BLE spatial positioning tracker with Kalman filter, vector Area signatures, and RPA matching."""

    def __init__(
        self,
        hass: HomeAssistant,
        beacon_uuid: str,
        device_slug: str,
        on_area_detected: Callable[[str, str], None],
        scanner_offsets: Mapping[str, float] | None = None,
        area_signatures: Mapping[str, Mapping[str, Any]] | None = None,
        ref_power_dbm: float | str | None = None,
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
        self._target_uuid_hex = normalize_uuid_hex(beacon_uuid)
        self._explicit_major: int | None = None
        self._explicit_minor: int | None = None
        self._target_eddystone_namespace_hex = ""
        self._target_address = str(target_address or "").strip()
        self.target_address = self._target_address
        self._raw_slug = device_slug
        self._esphome_device_id = esphome_device_id
        self._manifest_beacon: dict[str, Any] = (
            dict(manifest_beacon) if isinstance(manifest_beacon, dict) else {}
        )
        self._should_hold_during_ble_sleep = should_hold_during_ble_sleep
        self._on_address_matched = on_address_matched
        self._on_area_detected = on_area_detected
        self._init_runtime_and_rf_state(initial_matched_addresses)
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

    def _init_runtime_and_rf_state(self, initial_matched_addresses: Iterable[str] | None) -> None:
        now_init = time.monotonic()
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
        self._unmapped_rssi: dict[str, tuple[int, float]] = {}
        self._scanner_area_cache: dict[str, str] = {}
        self._last_adv_ts_by_scanner: dict[str, float] = {}
        self._target_mac_ints: set[int] = set()
        self._dynamic_target_mac_int: int | None = None
        self._dynamic_target_mac_str: str = ""
        self._last_mac_discovery_mono: float = 0.0
        self._matched_ble_addresses: dict[str, float] = {}
        if not ("." in self._target_address and not self._esphome_device_id):
            for raw_addr in initial_matched_addresses or ():
                norm_init = str(raw_addr or "").strip().upper()
                if mac_to_int(norm_init) is not None and len(self._matched_ble_addresses) < _MAX_MATCHED_ADDRESSES:
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

    @property
    def raw_slug(self) -> str:
        """Return the normalized `device_slug` owned by this tracker."""
        return self._raw_slug

    @property
    def effective_ref_power_dbm(self) -> float:
        """Return configured 1 m reference power, entity TX power, advertisement power, or `-59.0` dBm."""
        for candidate in (self._configured_ref_power_dbm, self._entity_ref_power_dbm, self.detected_ref_power_dbm):
            if candidate is not None:
                return float(candidate)
        return TX_POWER_1M_DBM

    @property
    def matched_ble_addresses(self) -> list[str]:
        """Return up to 8 most-recently matched BLE addresses for runtime persistence."""
        return sorted(
            self._matched_ble_addresses,
            key=lambda k: self._matched_ble_addresses[k],
            reverse=True,
        )[:_PERSISTED_MATCHED_ADDRESSES]

    @property
    def target_macs_formatted(self) -> list[str]:
        """Return candidate Wi-Fi/BLE MAC addresses for the target ESPHome device or dynamic RPA."""
        macs = {int_to_mac(m) for m in self._target_mac_ints}
        if self._dynamic_target_mac_int is not None:
            macs.add(int_to_mac(self._dynamic_target_mac_int))
        return sorted(macs)

    def _get_scanner_offset(self, scanner_source: str) -> float:
        return float(self._scanner_offsets.get(scanner_source.strip().upper(), 0.0))

    @callback
    def _record_matched_ble_address(
        self, addr: str, *, seed_scanners: bool = True
    ) -> None:
        """Record a matched BLE address with monotonic timestamp, bounded to 64 entries."""
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
        if len(self._matched_ble_addresses) > _MAX_MATCHED_ADDRESSES:
            oldest = min(
                self._matched_ble_addresses,
                key=lambda k: self._matched_ble_addresses[k],
            )
            self._matched_ble_addresses.pop(oldest, None)
            evicted = True
        if is_new and self._on_address_matched is not None:
            self._on_address_matched(norm)
        if is_new or evicted:
            fabric = get_active_ble_fabric(self.hass)
            if fabric is not None:
                fabric.sync_tracker_addresses()
                if is_new and seed_scanners and fabric.has_tracker(self):
                    fabric.seed_tracker_from_scanners_once(self, only_address=norm)

    @callback
    def _prune_expired_matched_ble_addresses(self, now_mono: float) -> bool:
        """Evict expired rotating BLE addresses (RPAs) after TTL while keeping static MACs."""
        if self._esphome_device_id or not self._matched_ble_addresses:
            return False
        evicted = False
        for addr, ts in list(self._matched_ble_addresses.items()):
            if (now_mono - ts) <= MATCHED_BLE_ADDRESS_TTL_SECONDS:
                continue
            if self._dynamic_target_mac_str and addr == self._dynamic_target_mac_str:
                continue
            addr_int = mac_to_int(addr)
            if addr_int is not None and addr_int in self._target_mac_ints:
                continue
            self._matched_ble_addresses.pop(addr, None)
            evicted = True
        return evicted

    @callback
    def _apply_dynamic_entity_mac(
        self, raw_mac: str, *, sync_fabric: bool = True
    ) -> None:
        """Update `_dynamic_target_mac_int` and evict rotated RPAs in `O(1)`."""
        c_int = mac_to_int(raw_mac)
        if c_int is None:
            return
        formatted = int_to_mac(c_int)
        prev_str = self._dynamic_target_mac_str
        changed = (
            self._dynamic_target_mac_int != c_int
            or formatted not in self._matched_ble_addresses
        )
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
            fabric = get_active_ble_fabric(self.hass)
            if fabric is not None and fabric.has_tracker(self):
                fabric.sync_tracker_addresses()
                fabric.seed_tracker_from_scanners_once(self)

    @callback
    def _async_on_target_entity_state_change(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """React immediately when a tracked `private_ble_device`, `mobile_app`, or `ibeacon` entity updates."""
        if event.data.get("new_state") is None:
            return
        self._seed_explicit_target_address(sync_fabric=True)

    def _extract_entity_target_metadata(
        self, st: Any, ent_entry: er.RegistryEntry | None
    ) -> tuple[str, tuple[str, int | None, int | None] | None]:
        parsed_ib: tuple[str, int | None, int | None] | None = None
        cur_mac = ""
        if st is not None:
            cur_mac = str(
                st.attributes.get("current_address")
                or st.attributes.get("mac")
                or st.attributes.get("address")
                or ""
            ).strip()
            raw_id = str(st.attributes.get("id") or st.attributes.get("uuid") or "").strip()
            if raw_id:
                parsed_ib = parse_ibeacon_identity(
                    raw_id, st.attributes.get("major"), st.attributes.get("minor")
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
            parsed_ib = extract_ibeacon_entity_identity(self.hass, ent_entry, st)
        return cur_mac, parsed_ib

    def _fallback_device_mac_for_entity(
        self, ent_entry: er.RegistryEntry | None
    ) -> str:
        if ent_entry is None or not ent_entry.device_id:
            return ""
        dev_entry = dr.async_get(self.hass).async_get(ent_entry.device_id)
        if not isinstance(dev_entry, dr.DeviceEntry):
            return ""
        for _ct, cv in dev_entry.connections:
            if mac_to_int(str(cv)) is not None:
                return str(cv)
        for _dom, iv in dev_entry.identifiers:
            if mac_to_int(str(iv)) is not None:
                return str(iv)
        return ""

    @callback
    def _seed_entity_target_address(
        self, t_addr: str, *, sync_fabric: bool
    ) -> None:
        st = self.hass.states.get(t_addr)
        ent_entry = er.async_get(self.hass).async_get(t_addr)
        prev_ib = (self._target_uuid_hex, self._explicit_major, self._explicit_minor)
        prev_ent_ref = self._entity_ref_power_dbm
        cur_mac, parsed_ib = self._extract_entity_target_metadata(st, ent_entry)
        if parsed_ib is not None:
            self._target_uuid_hex, self._explicit_major, self._explicit_minor = parsed_ib

        is_beacon_entity = parsed_ib is not None or (
            ent_entry is not None and ent_entry.platform in ("mobile_app", "ibeacon")
        )
        if not cur_mac and not is_beacon_entity:
            cur_mac = self._fallback_device_mac_for_entity(ent_entry)

        if cur_mac:
            self._apply_dynamic_entity_mac(cur_mac, sync_fabric=sync_fabric)
        elif (
            not self._esphome_device_id
            and (self._target_uuid_hex, self._explicit_major, self._explicit_minor) != prev_ib
        ):
            self._matched_ble_addresses.clear()
            if sync_fabric:
                fabric = get_active_ble_fabric(self.hass)
                if fabric is not None and fabric.has_tracker(self):
                    fabric.sync_tracker_addresses()
                    fabric.seed_tracker_from_scanners_once(self)
        if (
            sync_fabric
            and self._entity_ref_power_dbm != prev_ent_ref
            and self._scanner_states
        ):
            self._evaluate_best_area(time.monotonic())

    @callback
    def _seed_explicit_target_address(self, *, sync_fabric: bool = True) -> None:
        """Seed MAC, iBeacon/Eddystone UID, Companion App UUID-Major-Minor, or dynamic RPA."""
        t_addr = self._target_address
        if not t_addr:
            return
        m_int = mac_to_int(t_addr)
        if m_int is not None:
            self._target_mac_ints.add(m_int)
            self._record_matched_ble_address(int_to_mac(m_int), seed_scanners=sync_fabric)
            return
        if "." in t_addr:
            self._seed_entity_target_address(t_addr, sync_fabric=sync_fabric)
            return

        stripped = t_addr.strip()
        if not stripped.lower().startswith(("eddystone:", "bthome:")):
            parsed_direct = parse_ibeacon_identity(stripped)
            if parsed_direct is not None:
                self._target_uuid_hex, self._explicit_major, self._explicit_minor = (
                    parsed_direct
                )
                return
        for prefix in ("eddystone:", "ibeacon:", "bthome:"):
            if stripped.lower().startswith(prefix):
                stripped = stripped[len(prefix) :].strip()
                break
        hex_only = re.sub(r"[^0-9a-f]", "", stripped.lower())
        if len(hex_only) == _UUID_HEX_LEN:
            self._target_uuid_hex = hex_only
            return
        if len(hex_only) == _EDDYSTONE_NS_HEX_LEN:
            self._target_eddystone_namespace_hex = hex_only
            return
        norm_u = normalize_uuid_hex(stripped.split(":", 1)[0])
        if len(norm_u) == _UUID_HEX_LEN:
            self._target_uuid_hex = norm_u
        elif len(norm_u) == _EDDYSTONE_NS_HEX_LEN:
            self._target_eddystone_namespace_hex = norm_u

    @callback
    def update_manifest_beacon(self, beacon: dict[str, Any] | None) -> None:
        """Update cached hardware manifest beacon metadata (`uuid`, `major`, `minor`, `ref_power`)."""
        if not isinstance(beacon, dict):
            return
        prev_beacon = dict(self._manifest_beacon)
        prev_uuid = self._target_uuid_hex
        self._manifest_beacon = dict(beacon)
        for p_key in ("ref_power", "tx_power_1m", "measured_power"):
            raw_rp = beacon.get(p_key)
            if (
                isinstance(raw_rp, (int, float))
                and not isinstance(raw_rp, bool)
                and _MIN_REF_DBM <= float(raw_rp) <= _MAX_REF_DBM
            ):
                self.detected_ref_power_dbm = float(raw_rp)
                break
        norm_u = normalize_uuid_hex(str(beacon.get("uuid") or "").strip())
        default_u = normalize_uuid_hex(DEFAULT_BLE_BEACON_UUID)
        if (
            len(norm_u) == _UUID_HEX_LEN
            and not self._target_address
            and (not self._target_uuid_hex or norm_u != default_u)
        ):
            self._target_uuid_hex = norm_u
        if (
            self._manifest_beacon != prev_beacon
            or self._target_uuid_hex != prev_uuid
            or not self._matched_ble_addresses
        ):
            fabric = get_active_ble_fabric(self.hass)
            if fabric is not None and fabric.has_tracker(self):
                fabric.seed_tracker_from_scanners_once(self)

    def _resolve_beacon_major_minor(self) -> tuple[int | None, int | None]:
        """Return expected iBeacon `(major, minor)` IDs from explicit target config or hardware manifest."""
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
        major_val = coerce_uint16(beacon_cfg.get("major")) if isinstance(beacon_cfg, dict) else None
        minor_val = coerce_uint16(beacon_cfg.get("minor")) if isinstance(beacon_cfg, dict) else None
        return major_val, minor_val

    def _matches_ibeacon_payload(self, apple_bytes: bytes) -> bool:
        if apple_bytes[2:18].hex().lower() != self._target_uuid_hex:
            return False
        major_val = (apple_bytes[18] << 8) | apple_bytes[19]
        minor_val: int | None = (
            (apple_bytes[20] << 8) | apple_bytes[21]
            if len(apple_bytes) >= _IBEACON_FULL_BYTES
            else None
        )
        expected_major, expected_minor = self._resolve_beacon_major_minor()
        major_mismatch = (
            major_val != expected_major
            if self._explicit_major is not None
            else (
                expected_major is not None
                and expected_major >= 0
                and major_val != expected_major
            )
        )
        if major_mismatch:
            return False
        if self._explicit_minor is not None:
            return minor_val == expected_minor
        if self._explicit_major is not None:
            return True
        return (
            minor_val == expected_minor
            if (expected_minor is not None and expected_minor >= 0)
            else not bool(self._esphome_device_id)
        )

    def _matches_eddystone_service_data(
        self, service_data: Mapping[str, bytes]
    ) -> bool:
        for svc_uuid, svc_bytes in service_data.items():
            u_low = str(svc_uuid).lower()
            if (
                (u_low.startswith(EDDYSTONE_UUID_PREFIX) or u_low == "feaa")
                and isinstance(svc_bytes, (bytes, bytearray))
                and len(svc_bytes) >= _EDDYSTONE_MIN_SVC_BYTES
            ):
                raw_b = bytes(svc_bytes)
                if len(raw_b) >= _EDDYSTONE_UID_MIN_BYTES and (raw_b[0] & _EDDYSTONE_FRAME_MASK) == 0x00:
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

    def _matches_raw_adv(
        self,
        address: str,
        mfg_data: Mapping[int, bytes],
        service_data: Mapping[str, bytes] | None = None,
    ) -> bool:
        """Return True if advertisement matches static/dynamic MAC, framed iBeacon, or Eddystone-UID."""
        norm_addr = str(address or "").strip().upper()
        adv_int = mac_to_int(norm_addr) if norm_addr else None

        if self._dynamic_target_mac_int is not None and adv_int == self._dynamic_target_mac_int:
            return True
        if self._target_mac_ints and adv_int is not None and adv_int in self._target_mac_ints:
            return True

        apple_bytes = mfg_data.get(APPLE_COMPANY_ID)
        has_ibeacon_frame = bool(
            apple_bytes
            and len(apple_bytes) >= _IBEACON_MIN_BYTES
            and apple_bytes[:2] == IBEACON_PREFIX
        )
        if (
            norm_addr
            and norm_addr in self._matched_ble_addresses
            and not self._target_uuid_hex
            and not self._target_eddystone_namespace_hex
        ):
            return True

        if (
            has_ibeacon_frame
            and apple_bytes is not None
            and self._target_uuid_hex
            and self._matches_ibeacon_payload(apple_bytes)
        ):
            return True

        return bool(service_data and self._matches_eddystone_service_data(service_data))

    def _matches_target_device(self, service_info: object) -> bool:
        """Return True if a `BluetoothServiceInfoBleak` object matches this tracker and extract ref power."""
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
            detected = extract_adv_ref_power_dbm(service_info, mfg_data, service_data)
            if detected is not None:
                self.detected_ref_power_dbm = detected
        return matched

    @callback
    def invalidate_scanner_cache(self) -> None:
        """Clear per-tracker scanner-to-Area cache and refresh bound ESPHome MACs."""
        self._scanner_area_cache.clear()
        if self._esphome_device_id:
            self._target_mac_ints = discover_target_device_macs(self.hass, self._esphome_device_id)

    @callback
    def maybe_discover_bound_macs(self, now_mono: float, interval_s: float) -> bool:
        """Retry bound ESPHome MAC discovery periodically until populated."""
        if (
            self._target_mac_ints
            or not self._esphome_device_id
            or (now_mono - self._last_mac_discovery_mono) < interval_s
        ):
            return False
        self._last_mac_discovery_mono = now_mono
        self._target_mac_ints = discover_target_device_macs(self.hass, self._esphome_device_id)
        return bool(self._target_mac_ints)

    @callback
    def configure_spatial_engine(
        self,
        *,
        scanner_offsets: Mapping[str, float] | None = None,
        area_signatures: Mapping[str, Mapping[str, Any]] | None = None,
        ref_power_dbm: float | str | None = None,
        attenuation: float = DEFAULT_BLE_ATTENUATION,
        max_radius_m: float = DEFAULT_BLE_MAX_RADIUS_M,
        max_velocity_mps: float = DEFAULT_BLE_MAX_VELOCITY_MPS,
        away_timeout_s: float = float(DEFAULT_BLE_AWAY_TIMEOUT_S),
        re_evaluate: bool = True,
    ) -> None:
        """Update per-scanner offsets, vector signatures, reference power, and System RF parameters live."""
        if scanner_offsets is not None:
            self._scanner_offsets = _clean_scanner_offsets(scanner_offsets)
        if area_signatures is not None:
            self._area_signatures = _clean_area_signatures_map(area_signatures)

        self._configured_ref_power_dbm = None
        if ref_power_dbm is not None and ref_power_dbm != "" and not isinstance(ref_power_dbm, bool):
            try:
                parsed_ref = float(ref_power_dbm)
                if math.isfinite(parsed_ref):
                    self._configured_ref_power_dbm = max(_MIN_REF_DBM, min(_MAX_REF_DBM, parsed_ref))
            except (TypeError, ValueError):
                pass

        for param, val in (
            ("_attenuation", (attenuation, _MIN_ATTENUATION, _MAX_ATTENUATION, float(DEFAULT_BLE_ATTENUATION))),
            ("_max_radius_m", (max_radius_m, _MIN_RADIUS_M, _MAX_RADIUS_M, float(DEFAULT_BLE_MAX_RADIUS_M))),
            ("_max_velocity_mps", (max_velocity_mps, _MIN_VELOCITY_MPS, _MAX_VELOCITY_MPS, float(DEFAULT_BLE_MAX_VELOCITY_MPS))),
            ("_away_timeout_s", (away_timeout_s, _MIN_AWAY_TIMEOUT_S, _MAX_AWAY_TIMEOUT_S, float(DEFAULT_BLE_AWAY_TIMEOUT_S))),
        ):
            setattr(self, param, _clamp_float_param(*val))
        if re_evaluate and self._scanner_states:
            self._evaluate_best_area(time.monotonic())

    def _reconfigure_with(self, **overrides: Any) -> None:
        params: dict[str, Any] = {
            "scanner_offsets": self._scanner_offsets,
            "area_signatures": self._area_signatures,
            "ref_power_dbm": self._configured_ref_power_dbm,
            "attenuation": self._attenuation,
            "max_radius_m": self._max_radius_m,
            "max_velocity_mps": self._max_velocity_mps,
            "away_timeout_s": self._away_timeout_s,
            "re_evaluate": True,
        }
        params.update(overrides)
        self.configure_spatial_engine(**params)

    @callback
    def set_scanner_offsets(self, offsets: Mapping[str, float] | None) -> None:
        """Update per-scanner RSSI calibration offsets (dB bias) in real time and re-evaluate."""
        self._reconfigure_with(scanner_offsets=offsets or {})

    @callback
    def set_area_signatures(self, signatures: Mapping[str, Mapping[str, Any]] | None) -> None:
        """Update multi-scanner Area signatures in real time and re-evaluate."""
        self._reconfigure_with(area_signatures=signatures or {})

    @callback
    def set_ref_power(self, ref_power_dbm: float | None) -> None:
        """Update configured 1 m reference power (`None` = auto-detect) and re-evaluate."""
        self._reconfigure_with(ref_power_dbm=ref_power_dbm)

    @callback
    def _cancel_wake_coalesce_timer(self) -> None:
        if self._unsub_wake_coalesce is not None:
            self._unsub_wake_coalesce()
            self._unsub_wake_coalesce = None

    @callback
    def _async_on_wake_coalesce_timer(self, _now: Any = None) -> None:
        self._unsub_wake_coalesce = None
        self._wake_coalesce_until = 0.0
        self._evaluate_best_area(max(time.monotonic(), self.last_packet_monotonic))

    def _area_has_registered_scanner(self, area_id: str | None) -> bool:
        return bool(area_id and area_id in get_ble_proxy_area_ids(self.hass))

    @callback
    def check_away_timeout(self, now_mono: float) -> None:
        """Transition tracker to Away if no BLE packet arrived within `_away_timeout_s`."""
        self._seed_explicit_target_address()
        fabric = get_active_ble_fabric(self.hass)
        if self._prune_expired_matched_ble_addresses(now_mono) and fabric is not None:
            fabric.sync_tracker_addresses()
        ref_mono = max(
            self.last_packet_monotonic if self.last_packet_monotonic > 0.0 else self._started_monotonic,
            self._ble_wake_monotonic,
        )
        if self.is_away or ref_mono <= 0.0 or (now_mono - ref_mono) < self._away_timeout_s:
            return
        if self._should_hold_during_ble_sleep is not None and self._should_hold_during_ble_sleep():
            return
        self._cancel_wake_coalesce_timer()
        self.is_away = True
        self.current_area_id = None
        self.match_method = ""
        self._awaiting_fresh_wake_lock = False
        self.winning_rssi = None
        self.winning_raw_rssi = None
        self.winning_distance_m = None
        self._on_area_detected("away", "")
        if fabric is not None:
            fabric.notify_occupancy_listeners()

    @callback
    def note_ble_radio_active(self, now_mono: float | None = None) -> None:
        """Grant a fresh away-timeout window and re-seed scanner addresses when BLE resumes."""
        self._ble_wake_monotonic = now_mono if now_mono is not None else time.monotonic()
        was_away = self.is_away
        self.is_away = False
        if (fabric := get_active_ble_fabric(self.hass)) is not None:
            if not self._matched_ble_addresses:
                fabric.seed_tracker_from_scanners_once(self)
            fabric.sync_tracker_addresses()
            if was_away:
                fabric.notify_occupancy_listeners()

    @callback
    def reset_for_device_wake(self) -> None:
        """Clear stale RSSI history on wake while preserving sticky `current_area_id` until fresh BLE lock."""
        now = time.monotonic()
        self._ble_wake_monotonic = now
        was_away = self.is_away
        self.is_away = False
        fabric = get_active_ble_fabric(self.hass)
        if self.last_packet_monotonic > 0.0 and (now - self.last_packet_monotonic) < _RECENT_WAKE_PACKET_S:
            if was_away and fabric is not None:
                fabric.notify_occupancy_listeners()
            return
        self._cancel_wake_coalesce_timer()
        self._scanner_states.clear()
        self._unmapped_rssi.clear()
        self._scanner_area_cache.clear()
        clear_scanner_area_cache(self.hass)
        self._last_adv_ts_by_scanner.clear()
        self._awaiting_fresh_wake_lock = True
        self._wake_coalesce_until = now + WAKE_COALESCE_SECONDS if self.current_area_id else 0.0
        self._last_switch_monotonic = 0.0
        if self._esphome_device_id:
            self._target_mac_ints = discover_target_device_macs(self.hass, self._esphome_device_id)
        self._seed_explicit_target_address(sync_fabric=False)
        if fabric is not None:
            if not self._matched_ble_addresses:
                fabric.seed_tracker_from_scanners_once(self)
            fabric.sync_tracker_addresses()
            if was_away:
                fabric.notify_occupancy_listeners()

    @callback
    def async_start(self) -> None:
        """Register this tracker with `LatterBleFabric` and bind dynamic RPA state listener."""
        self.async_stop()
        self._started_monotonic = time.monotonic()
        if self._esphome_device_id:
            self._target_mac_ints = discover_target_device_macs(self.hass, self._esphome_device_id)
        self._seed_explicit_target_address(sync_fabric=False)
        if "." in self._target_address:
            self._unsub_target_entity = async_track_state_change_event(
                self.hass, [self._target_address], self._async_on_target_entity_state_change
            )
        if (fabric := get_active_ble_fabric(self.hass, create=True)) is not None:
            fabric.register_tracker(self)
        _LOGGER.info(
            "Latter Native BLE Area Tracker registered with shared BLE Fabric (device=%s, UUID=%s, macs=%s)",
            self._raw_slug,
            self._target_uuid_hex,
            self.target_macs_formatted,
        )

    @callback
    def async_stop(self) -> None:
        """Unregister this tracker from `LatterBleFabric` and cancel all timers/listeners."""
        self._cancel_wake_coalesce_timer()
        if self._unsub_target_entity is not None:
            self._unsub_target_entity()
            self._unsub_target_entity = None
        if (fabric := get_active_ble_fabric(self.hass)) is not None:
            fabric.unregister_tracker(self)
        self._scanner_states.clear()
        self._unmapped_rssi.clear()
        self._scanner_area_cache.clear()
        self._last_adv_ts_by_scanner.clear()

    def _resolve_scanner_display_name(
        self, scanner_source: str, registered_names: Mapping[str, str]
    ) -> str:
        norm = scanner_source.strip().upper()
        if registered_names.get(norm):
            return registered_names[norm]
        st = self._scanner_states.get(norm)
        if st is not None and st.scanner_name and st.scanner_name.upper() != norm:
            return st.scanner_name
        if (src_int := mac_to_int(norm)) is not None:
            for dev in iter_devices(dr.async_get(self.hass)):
                for _ct, cv in dev.connections:
                    c_int = mac_to_int(str(cv))
                    if (
                        c_int is not None
                        and abs(src_int - c_int) <= _ESP_ADJACENT_MAC_DELTA
                        and (lbl := str(dev.name_by_user or dev.name or "").strip())
                    ):
                        return lbl
        return norm

    def _build_scanner_calibration_row(
        self, src: str, now: float, registered_names: Mapping[str, str], area_reg: ar.AreaRegistry
    ) -> dict[str, Any]:
        ref_shift = self.effective_ref_power_dbm - TX_POWER_1M_DBM
        winner_src = self.closest_scanner.strip().upper() if self.closest_scanner else ""
        area_id = resolve_scanner_area_id(self.hass, src) or ""
        area_obj = area_reg.async_get_area(area_id) if area_id else None
        offset_db = round(self._get_scanner_offset(src), 1)
        st = self._scanner_states.get(src)

        obs_sample: tuple[int, float, float] | None = None
        if st is not None and st.packet_count > 0:
            obs_sample = (int(st.raw_rssi), st.x_dbm, max(0.0, now - st.last_obs_time))
        elif src in self._unmapped_rssi:
            un_raw, un_ts = self._unmapped_rssi[src]
            obs_sample = (int(un_raw), float(un_raw), max(0.0, now - un_ts))

        raw_rssi: int | None = None
        filtered_rssi: float | None = None
        effective_rssi: int | None = None
        dist_m: float | None = None
        age_s: int | None = None
        is_fresh = False
        if obs_sample is not None and obs_sample[2] <= SURVEY_RETENTION_SECONDS:
            raw_rssi, x_val, elapsed = obs_sample
            filtered_rssi = round(x_val, 1)
            norm_dbm = x_val + offset_db - ref_shift
            effective_rssi = round(norm_dbm)
            dist_m = rssi_to_distance_m(norm_dbm, attenuation=self._attenuation)
            age_s = round(elapsed)
            is_fresh = elapsed <= STALE_PROXY_SECONDS

        return {
            "scanner_source": src,
            "scanner_name": self._resolve_scanner_display_name(src, registered_names),
            "area_id": area_id,
            "area_name": area_obj.name if area_obj else "",
            "raw_rssi": raw_rssi,
            "filtered_rssi": filtered_rssi,
            "offset_db": offset_db,
            "effective_rssi": effective_rssi,
            "distance_m": dist_m,
            "age_seconds": age_s,
            "is_fresh": is_fresh,
            "is_winner": bool(is_fresh and self.current_area_id and src == winner_src),
        }

    def get_scanner_calibration_telemetry(self) -> list[dict[str, Any]]:
        """Return per-scanner BLE calibration and site survey telemetry in canonical meters."""
        area_reg = ar.async_get(self.hass)
        now = time.monotonic()
        registered_names = {
            raw_src.upper(): str(getattr(sc, "name", "") or raw_src).strip()
            for sc in current_ble_scanners(self.hass)
            if (raw_src := str(getattr(sc, "source", "") or "").strip())
        }
        all_sources = (
            set(registered_names)
            | set(self._scanner_states)
            | set(self._unmapped_rssi)
            | set(self._scanner_offsets)
        )
        rows = [
            self._build_scanner_calibration_row(src, now, registered_names, area_reg)
            for src in all_sources
            if src
        ]
        rows.sort(
            key=lambda r: (
                r["effective_rssi"] is None,
                -(r["effective_rssi"] if r["effective_rssi"] is not None else _MISSING_RSSI_SENTINEL),
                (r["area_name"] or "~").lower(),
                r["scanner_name"].lower(),
            )
        )
        return rows

    get_area_calibration_telemetry = get_scanner_calibration_telemetry

    def capture_area_signature(self) -> dict[str, dict[str, float | int]]:
        """Capture normalized 1 m-equivalent multi-scanner RSSI vector across recent scanners (`<= 15 s`)."""
        now = time.monotonic()
        ref_shift = self.effective_ref_power_dbm - TX_POWER_1M_DBM
        captured: dict[str, dict[str, float | int]] = {}
        for src, st in self._scanner_states.items():
            if st.packet_count <= 0 or (now - st.last_obs_time) > SIGNATURE_CAPTURE_WINDOW_SECONDS:
                continue
            shift = self._get_scanner_offset(src) - ref_shift
            samples = (
                [f + shift for ts, f in st.ring_buffer if (now - ts) <= SIGNATURE_RING_WINDOW_SECONDS]
                or [f + shift for ts, f in st.ring_buffer if (now - ts) <= SIGNATURE_CAPTURE_WINDOW_SECONDS]
                or [st.x_dbm + shift]
            )
            n_cnt = len(samples)
            mean_val = sum(samples) / float(n_cnt)
            variance = sum((v - mean_val) ** 2 for v in samples) / float(n_cnt) if n_cnt > 1 else 0.0
            captured[src] = {"mean": round(mean_val, 1), "std": round(max(2.5, math.sqrt(variance)), 1), "n": n_cnt}
        return captured

    @callback
    def _async_on_ble_advertisement(self, service_info: object, _change: object) -> None:
        """Process incoming BLE advertisement callback from an ESPHome BLE proxy."""
        if not self._matches_target_device(service_info):
            return
        rssi_int = safe_rssi_int(getattr(service_info, "rssi", None))
        source = str(getattr(service_info, "source", "") or "")
        if rssi_int is None or not source or rssi_int <= _MIN_VALID_RSSI_DBM:
            return
        adv_ts = getattr(service_info, "time", None)
        now_mono = time.monotonic()
        obs_mono = float(adv_ts) if adv_ts is not None else now_mono
        if adv_ts is not None and (now_mono - obs_mono) > SURVEY_RETENTION_SECONDS:
            return
        self._ingest_proxy_observation(source, rssi_int, obs_mono, source)

    def _resolve_cached_scanner_area(self, norm_source: str) -> str | None:
        cached_area = self._scanner_area_cache.get(norm_source)
        if cached_area is None:
            cached_area = resolve_scanner_area_id(self.hass, norm_source) or _UNMAPPED
            self._scanner_area_cache[norm_source] = cached_area
        return None if cached_area == _UNMAPPED else cached_area

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
        eval_now = max(now, obs_time) if (obs_time - now) <= _MAX_FUTURE_SKEW_S else now

        prev_adv_ts = self._last_adv_ts_by_scanner.get(norm_source)
        if prev_adv_ts is not None:
            if from_poll and obs_time <= (prev_adv_ts + _POLL_DEDUPE_EPS_S):
                self._evaluate_best_area(eval_now, "")
                return
            if not from_poll and abs(obs_time - prev_adv_ts) < _ADV_DEDUPE_EPS_S:
                return

        self._last_adv_ts_by_scanner[norm_source] = obs_time
        just_woke = (
            not from_poll
            and not self._awaiting_fresh_wake_lock
            and self.last_packet_monotonic > 0.0
            and (obs_time - self.last_packet_monotonic) >= WAKE_GAP_SECONDS
        )
        self.last_packet_monotonic = max(self.last_packet_monotonic, obs_time)
        self.packets_seen += 1

        if self._esphome_device_id and not self._target_mac_ints and self.packets_seen <= _EARLY_MAC_DISCOVERY_PKTS:
            self._target_mac_ints = discover_target_device_macs(self.hass, self._esphome_device_id)
            if self._target_mac_ints and (fabric := get_active_ble_fabric(self.hass)) is not None:
                fabric.sync_tracker_addresses()

        if just_woke:
            self._cancel_wake_coalesce_timer()
            self._scanner_states.clear()
            self._last_switch_monotonic = 0.0
            self._awaiting_fresh_wake_lock = True
            self._wake_coalesce_until = obs_time + WAKE_COALESCE_SECONDS if self.current_area_id else 0.0

        update_scanner_kalman_state(
            self._scanner_states,
            norm_source,
            int(rssi),
            obs_time,
            scanner_name,
            offset_db=self._get_scanner_offset(norm_source),
            ref_shift=self.effective_ref_power_dbm - TX_POWER_1M_DBM,
            attenuation=self._attenuation,
            max_velocity_mps=self._max_velocity_mps,
        )
        area_id = self._resolve_cached_scanner_area(norm_source)
        if not area_id:
            self._unmapped_rssi[norm_source] = (int(rssi), obs_time)
            if self._area_signatures and (eval_now - obs_time) <= STALE_PROXY_SECONDS:
                self._evaluate_best_area(eval_now, norm_source)
            return

        self._unmapped_rssi.pop(norm_source, None)
        if (eval_now - obs_time) <= STALE_PROXY_SECONDS:
            self._evaluate_best_area(eval_now, norm_source)

    def _collect_area_scores(
        self, now: float, is_cross_floor: Callable[[str], bool]
    ) -> tuple[dict[str, float], dict[str, tuple[str, float, int, str]], dict[str, int]]:
        ref_shift = self.effective_ref_power_dbm - TX_POWER_1M_DBM
        fresh_norm: dict[str, float] = {}
        fresh_ages: dict[str, float] = {}
        area_candidates: dict[str, list[tuple[float, float, ScannerObservationState, str]]] = {}

        for src, st in self._scanner_states.items():
            if st.packet_count <= 0 or (age_s := max(0.0, now - st.last_obs_time)) > STALE_PROXY_SECONDS:
                continue
            norm_dbm = st.x_dbm + self._get_scanner_offset(src) - ref_shift
            fresh_norm[src] = norm_dbm
            fresh_ages[src] = age_s
            a_id = self._resolve_cached_scanner_area(src)
            if not a_id or rssi_to_distance_m(norm_dbm, attenuation=self._attenuation) > self._max_radius_m:
                continue
            decayed = norm_dbm - SILENCE_DECAY_DB_PER_S * max(0.0, age_s - SILENCE_GRACE_SECONDS)
            area_candidates.setdefault(a_id, []).append((decayed, norm_dbm, st, src))

        scores: dict[str, float] = {}
        area_winner_meta: dict[str, tuple[str, float, int, str]] = {}
        area_packet_counts: dict[str, int] = {}

        for a_id, cand_list in area_candidates.items():
            best_decayed, best_norm, best_st, best_src = min(
                cand_list,
                key=lambda item: (-round(item[0], _SCORE_ROUND_DIGITS), -round(item[1], _SCORE_ROUND_DIGITS), item[3]),
            )
            corroborating = sum(1 for _dec, n_dbm, _s, _src in cand_list if n_dbm >= CORROBORATION_MIN_DBM)
            score = best_decayed + (CORROBORATION_BONUS_DB if corroborating >= _MIN_CORROBORATED_SCANNERS else 0.0)
            scores[a_id] = score - (CROSS_FLOOR_ATTENUATION_DB if is_cross_floor(a_id) else 0.0)
            area_winner_meta[a_id] = (best_src, best_norm, best_st.raw_rssi, "distance")
            area_packet_counts[a_id] = sum(item[2].packet_count for item in cand_list)

        for sig_area_id, sig in self._area_signatures.items():
            sig_res = score_signature_vector(
                sig_area_id,
                sig,
                fresh_norm=fresh_norm,
                fresh_ages=fresh_ages,
                resolve_scanner_area=self._resolve_cached_scanner_area,
                is_cross_floor=is_cross_floor,
            )
            if sig_res is None:
                continue
            sig_score, sig_best_src = sig_res
            sig_scanners = sig.get("scanners", {})
            if (
                sig_area_id in scores
                and len(fresh_norm) < _MIN_CORROBORATED_SCANNERS
                and len(sig_scanners) >= _MIN_CORROBORATED_SCANNERS
                and sig_score < scores[sig_area_id]
            ):
                continue
            sig_st = self._scanner_states.get(sig_best_src)
            sig_norm = fresh_norm.get(sig_best_src, sig_score)
            scores[sig_area_id] = sig_score
            area_winner_meta[sig_area_id] = (
                sig_best_src,
                sig_norm,
                sig_st.raw_rssi if sig_st is not None else round(sig_norm),
                "signature",
            )
            area_packet_counts[sig_area_id] = max(
                1, sum(self._scanner_states[s].packet_count for s in sig_scanners if s in self._scanner_states)
            )
        return scores, area_winner_meta, area_packet_counts

    def _apply_winner_metrics(
        self, win_area: str, area_winner_meta: Mapping[str, tuple[str, float, int, str]]
    ) -> None:
        if (meta := area_winner_meta.get(win_area)) is None:
            return
        win_src, win_norm_dbm, win_raw_dbm, win_method = meta
        if win_src:
            self.closest_scanner = win_src
        self.winning_rssi = round(win_norm_dbm)
        self.winning_raw_rssi = int(win_raw_dbm)
        self.winning_distance_m = rssi_to_distance_m(win_norm_dbm, attenuation=self._attenuation)
        self.match_method = win_method

    def _commit_area_decision(
        self,
        now: float,
        latest_source: str,
        decision: AreaDecision,
        area_winner_meta: Mapping[str, tuple[str, float, int, str]],
    ) -> None:
        fabric = get_active_ble_fabric(self.hass)
        best_area = decision.best_area_id
        if best_area == self.current_area_id:
            meta = area_winner_meta.get(best_area)
            if meta is not None and meta[0]:
                self.closest_scanner, self.match_method = meta[0], meta[3]
            elif latest_source:
                self.closest_scanner = latest_source
            if meta is not None and within_rssi_deadband(self.winning_rssi, meta[1]):
                if fabric is not None:
                    fabric.emit_survey_delta(self)
                return
            prev_rssi = self.winning_rssi
            self._apply_winner_metrics(best_area, area_winner_meta)
            if fabric is not None:
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
            if fabric is not None:
                fabric.emit_survey_delta(self)
            return

        self.current_area_id = best_area
        self._apply_winner_metrics(best_area, area_winner_meta)
        if not self.closest_scanner and latest_source:
            self.closest_scanner = latest_source
        self._last_switch_monotonic = now
        self._on_area_detected(best_area, self.closest_scanner)
        if fabric is not None:
            fabric.emit_survey_delta(self)
            fabric.notify_occupancy_listeners()

    @callback
    def _evaluate_best_area(self, now: float, latest_source: str = "") -> None:
        """Evaluate multi-scanner path-loss + vector signature scores with wake coalescing and deadband."""
        area_reg = ar.async_get(self.hass)
        prior_area_id = None if self._awaiting_fresh_wake_lock else self.current_area_id
        anchor_floor_area_id = self.current_area_id
        cur_area_entry = area_reg.async_get_area(anchor_floor_area_id) if anchor_floor_area_id else None
        cur_floor_id = getattr(cur_area_entry, "floor_id", None) if cur_area_entry else None

        def _is_cross_floor(area_id: str) -> bool:
            if not cur_floor_id or area_id == anchor_floor_area_id:
                return False
            cand_entry = area_reg.async_get_area(area_id)
            cand_floor_id = getattr(cand_entry, "floor_id", None) if cand_entry else None
            return bool(cand_floor_id and cand_floor_id != cur_floor_id)

        scores, area_winner_meta, area_packet_counts = self._collect_area_scores(now, _is_cross_floor)
        fabric = get_active_ble_fabric(self.hass)
        if not scores:
            if fabric is not None:
                fabric.emit_survey_delta(self)
            return

        top_area_id = min(
            scores.items(),
            key=lambda item: (-round(item[1], _SCORE_ROUND_DIGITS), item[0] != prior_area_id, item[0]),
        )[0]
        challenger_pkts = area_packet_counts.get(top_area_id, 1)
        decision = decide_area(
            scores, prior_area_id, now, self._last_switch_monotonic, challenger_packet_count=challenger_pkts
        )
        if decision is None:
            if fabric is not None:
                fabric.emit_survey_delta(self)
            return

        if (
            self._awaiting_fresh_wake_lock
            and self.current_area_id is not None
            and decision.best_area_id != self.current_area_id
            and now < self._wake_coalesce_until
            and challenger_pkts < _MIN_CORROBORATED_SCANNERS
            and self._area_has_registered_scanner(self.current_area_id)
        ):
            if self._unsub_wake_coalesce is None:
                self._unsub_wake_coalesce = async_call_later(
                    self.hass, WAKE_COALESCE_SECONDS, self._async_on_wake_coalesce_timer
                )
            if fabric is not None:
                fabric.emit_survey_delta(self)
            return

        self._cancel_wake_coalesce_timer()
        self._wake_coalesce_until = 0.0
        self._awaiting_fresh_wake_lock = False
        self.is_away = False
        self._commit_area_decision(now, latest_source, decision, area_winner_meta)
