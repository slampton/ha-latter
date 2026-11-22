"""Multi-scanner `LatterNativeBleTracker`, site survey calibration, and signature capture (`L2a`)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
import logging
import math
import time
from typing import Any, Final

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import area_registry as ar, device_registry as dr
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from ..const import (
    DEFAULT_BLE_ATTENUATION,
    DEFAULT_BLE_AWAY_TIMEOUT_S,
    DEFAULT_BLE_MAX_RADIUS_M,
    DEFAULT_BLE_MAX_VELOCITY_MPS,
)
from .ble_math import (
    CORROBORATION_BONUS_DB,
    CORROBORATION_MIN_DBM,
    CROSS_FLOOR_ATTENUATION_DB,
    RSSI_HYSTERESIS_DEADBAND_DBM,
    SIGNATURE_CAPTURE_WINDOW_SECONDS,
    SIGNATURE_RING_WINDOW_SECONDS,
    SILENCE_DECAY_DB_PER_S,
    SILENCE_GRACE_SECONDS,
    STALE_PROXY_SECONDS,
    TX_POWER_1M_DBM,
    WAKE_COALESCE_SECONDS,
    AreaDecision,
    ScannerObservationState,
    decide_area,
    rssi_to_distance_m,
    safe_rssi_int,
    within_rssi_deadband,
)
from .ble_registry import (
    SURVEY_RETENTION_SECONDS,
    WAKE_GAP_SECONDS,
    clear_scanner_area_cache,
    current_ble_scanners,
    get_ble_proxy_area_ids,
    iter_devices,
    mac_to_int,
    normalize_uuid_hex,
    resolve_scanner_area_id,
)
from .ble_tracker_matcher import (
    BleTargetMatcherMixin,
    discover_target_device_macs,
    get_active_ble_fabric,
    score_signature_vector,
    update_scanner_kalman_state,
)

_LOGGER = logging.getLogger(__name__)
_UNMAPPED: Final = "__unmapped__"
_MAX_MATCHED_ADDRESSES: Final = 64
_MAX_OFFSET_DB: Final = 25.0
_MIN_REF_DBM, _MAX_REF_DBM = -90.0, -30.0
_MIN_ATTENUATION, _MAX_ATTENUATION = 1.5, 4.5
_MIN_RADIUS_M, _MAX_RADIUS_M = 2.0, 50.0
_MIN_VELOCITY_MPS, _MAX_VELOCITY_MPS = 0.5, 15.0
_MIN_AWAY_TIMEOUT_S, _MAX_AWAY_TIMEOUT_S = 30.0, 900.0
_RECENT_WAKE_PACKET_S: Final = 6.0
_ESP_ADJACENT_MAC_DELTA: Final = 2
_MISSING_RSSI_SENTINEL: Final = -999
_MIN_VALID_RSSI_DBM: Final = -100
_MAX_FUTURE_SKEW_S: Final = 60.0
_POLL_DEDUPE_EPS_S: Final = 1e-4
_ADV_DEDUPE_EPS_S: Final = 1e-6
_EARLY_MAC_DISCOVERY_PKTS: Final = 3
_SCORE_ROUND_DIGITS: Final = 6
_MIN_CORROBORATED_SCANNERS: Final = 2


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


class LatterNativeBleTracker(BleTargetMatcherMixin):
    """Multi-scanner BLE spatial positioning tracker with Kalman filter and vector Area signatures."""

    def __init__(  # noqa: PLR0913, PLR0917
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
        self._explicit_major = None
        self._explicit_minor = None
        self._target_eddystone_namespace_hex = ""
        self._target_address = str(target_address or "").strip()
        self.target_address = self._target_address
        self._raw_slug = device_slug
        self._esphome_device_id = esphome_device_id
        self._manifest_beacon = dict(manifest_beacon) if isinstance(manifest_beacon, dict) else {}
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
        self._entity_ref_power_dbm = None
        self.detected_ref_power_dbm = None
        self._attenuation: float = float(DEFAULT_BLE_ATTENUATION)
        self._max_radius_m: float = float(DEFAULT_BLE_MAX_RADIUS_M)
        self._max_velocity_mps: float = float(DEFAULT_BLE_MAX_VELOCITY_MPS)
        self._away_timeout_s: float = float(DEFAULT_BLE_AWAY_TIMEOUT_S)
        self._scanner_states: dict[str, ScannerObservationState] = {}
        self._unmapped_rssi: dict[str, tuple[int, float]] = {}
        self._scanner_area_cache: dict[str, str] = {}
        self._last_adv_ts_by_scanner: dict[str, float] = {}
        self._target_mac_ints = set()
        self._dynamic_target_mac_int = None
        self._dynamic_target_mac_str = ""
        self._last_mac_discovery_mono: float = 0.0
        self._matched_ble_addresses = {}
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

    def _get_scanner_offset(self, scanner_source: str) -> float:
        return float(self._scanner_offsets.get(scanner_source.strip().upper(), 0.0))

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
    def configure_spatial_engine(  # noqa: PLR0913
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
        self._ingest_proxy_observation(
            source, rssi_int, float(adv_ts) if adv_ts is not None else time.monotonic(), source
        )

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
