"""Kalman velocity-gated RSSI filter, vector signature scorer, and BLE target/RPA matcher (`L2a`)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import math
import re
import time
from typing import Any, Final, Protocol

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from ..const import DEFAULT_BLE_BEACON_UUID, DOMAIN
from ..identity import get_bound_esphome_device, read_device_hardware_manifest
from .ble_math import (
    CROSS_FLOOR_ATTENUATION_DB,
    EDDYSTONE_UUID_PREFIX,
    KALMAN_MEASUREMENT_VAR,
    SIGNATURE_CAPTURE_WINDOW_SECONDS,
    SIGNATURE_PEAK_SCORE_DBM,
    SIGNATURE_RING_MAX_SAMPLES,
    SILENCE_DECAY_DB_PER_S,
    SILENCE_GRACE_SECONDS,
    STALE_PROXY_SECONDS,
    ScannerObservationState,
    continuous_distance_m,
    distance_m_to_norm_dbm,
    resolve_companion_tx_ref_power_dbm,
)
from .ble_registry import (
    APPLE_COMPANY_ID,
    IBEACON_PREFIX,
    MATCHED_BLE_ADDRESS_TTL_SECONDS,
    coerce_uint16,
    extract_adv_ref_power_dbm,
    extract_ibeacon_entity_identity,
    int_to_mac,
    mac_to_int,
    normalize_uuid_hex,
    parse_ibeacon_identity,
)

_MAX_MATCHED_ADDRESSES: Final = 64
_PERSISTED_MATCHED_ADDRESSES: Final = 8
_UUID_HEX_LEN: Final = 32
_EDDYSTONE_NS_HEX_LEN: Final = 20
_IBEACON_MIN_BYTES: Final = 20
_IBEACON_FULL_BYTES: Final = 22
_EDDYSTONE_MIN_SVC_BYTES: Final = 12
_EDDYSTONE_UID_MIN_BYTES: Final = 18
_EDDYSTONE_FRAME_MASK: Final = 0xF0
_MIN_REF_DBM: Final = -90.0
_MAX_REF_DBM: Final = -30.0
_MEDIAN_WINDOW_LEN: Final = 3
_TWO_SAMPLES: Final = 2
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


class BleFabricPort(Protocol):
    """Downward `L2a` port implemented by `L2b` `LatterBleFabric` (zero upward import)."""

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
    """Register the `LatterBleFabric` singleton accessor from `L2b` `ble_fabric.py`."""
    global _FABRIC_GETTER
    _FABRIC_GETTER = getter


def get_active_ble_fabric(
    hass: HomeAssistant, *, create: bool = False
) -> BleFabricPort | None:
    """Return the active `LatterBleFabric` (creating it via registered getter when `create=True`)."""
    domain_data = hass.data.get(DOMAIN)
    if isinstance(domain_data, dict):
        existing = domain_data.get("ble_fabric")
        if existing is not None:
            fabric_existing: BleFabricPort = existing
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


_discover_target_device_macs = discover_target_device_macs


def _median_of_recent(vals: list[float]) -> float:
    if len(vals) == 1:
        return vals[0]
    if len(vals) == _TWO_SAMPLES:
        return 0.5 * (vals[0] + vals[1])
    return sorted(vals)[1]


def _apply_symmetric_velocity_gate(  # noqa: PLR0913
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


def update_scanner_kalman_state(  # noqa: PLR0913
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


def score_signature_vector(  # noqa: PLR0913
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


class BleTargetMatcherMixin:
    """Advertisement identity, iBeacon (`major=0`/`minor=0` safe), Eddystone, and RPA TTL matcher."""

    hass: HomeAssistant
    beacon_uuid: str
    _target_uuid_hex: str
    _explicit_major: int | None
    _explicit_minor: int | None
    _target_eddystone_namespace_hex: str
    _target_address: str
    target_address: str
    _esphome_device_id: str | None
    _manifest_beacon: dict[str, Any]
    _on_address_matched: Callable[[str], None] | None
    _entity_ref_power_dbm: float | None
    detected_ref_power_dbm: float | None
    _scanner_states: dict[str, ScannerObservationState]
    _target_mac_ints: set[int]
    _dynamic_target_mac_int: int | None
    _dynamic_target_mac_str: str
    _matched_ble_addresses: dict[str, float]

    def _evaluate_best_area(self, now: float, latest_source: str = "") -> None:
        raise NotImplementedError

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
        if dev_entry is None:
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
