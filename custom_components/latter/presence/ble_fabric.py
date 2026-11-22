"""Shared `LatterBleFabric` singleton and per-Area presence summary builder (`L2b`, `M-P2-19`)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
import logging
import time
from typing import Any, Final

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

from ..areas.registry import (
    area_illuminance_sensor_choices,
    resolve_area_ambient_light,
)
from ..const import DOMAIN
from ..hub_registry import iter_coordinators
from .area_fusion import (
    area_fusion_sensor_choices,
    area_fusion_settings,
    evaluate_area_sensor_fusion,
    get_tracked_fusion_entity_ids,
    invalidate_area_fusion_index,
)
from .ble_math import STALE_PROXY_SECONDS, safe_rssi_int
from .ble_registry import (
    APPLE_COMPANY_ID,
    AWAY_CHECK_INTERVAL_SECONDS,
    SURVEY_RETENTION_SECONDS,
    clear_scanner_area_cache,
    coerce_uint16,
    current_ble_scanners,
    extract_adv_ref_power_dbm,
    get_area_signatures_summary,
    get_ble_proxy_area_ids,
    get_ble_signature_area_ids,
    mac_to_int,
    normalize_uuid_hex,
    resolve_floor_info,
    set_scanner_area_cache_active,
)
from .ble_tracker_calibration import LatterNativeBleTracker
from .ble_tracker_matcher import register_ble_fabric_getter

_LOGGER = logging.getLogger(__name__)

_MIN_VALID_RSSI_DBM: Final = -100
_MAC_DISCOVERY_RETRY_S: Final = 30.0
_PAIR_TUPLE_LEN: Final = 2
_DEFAULT_FUSION_THRESHOLD_PCT: Final = 50


def _ibeacon_event_matches_tracker(
    tracker: LatterNativeBleTracker,
    uuid_raw: str,
    adv_int: int | None,
    ev_major: int | None,
    ev_minor: int | None,
) -> bool:
    if not (uuid_raw and uuid_raw == tracker._target_uuid_hex):
        return False
    expected_major, expected_minor = tracker._resolve_beacon_major_minor()
    if tracker._explicit_major is not None or tracker._explicit_minor is not None:
        maj_ok = tracker._explicit_major is None or ev_major == expected_major
        min_ok = tracker._explicit_minor is None or ev_minor == expected_minor
        return maj_ok and min_ok

    if (
        tracker._target_mac_ints
        and adv_int is not None
        and adv_int in tracker._target_mac_ints
    ):
        return True
    if expected_major is not None and expected_major >= 0 and ev_major != expected_major:
        return False
    return (
        ev_minor == expected_minor
        if (expected_minor is not None and expected_minor >= 0)
        else not bool(tracker._esphome_device_id)
    )


def _collect_area_tracker_occupants(
    hass: HomeAssistant,
    trackers: list[LatterNativeBleTracker],
    area_id: str,
    resolved_coords: Mapping[str, Any],
) -> tuple[
    list[str],
    list[str],
    list[str],
    int | None,
    str | None,
    float | None,
    str,
]:
    occupants: list[str] = []
    occupant_names: list[str] = []
    persons: list[str] = []
    best_rssi: int | None = None
    closest_dev: str | None = None
    closest_dist_m: float | None = None
    closest_match_method = ""

    for tracker in trackers:
        if tracker.is_away or tracker.current_area_id != area_id:
            continue
        slug = tracker.raw_slug
        occupants.append(slug)
        coord = resolved_coords.get(slug)
        p_ent = (
            str(getattr(coord, "assigned_person", "") or "").strip() if coord else ""
        )
        if p_ent and p_ent.startswith("person."):
            if p_ent not in persons:
                persons.append(p_ent)
            p_st = hass.states.get(p_ent)
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
            closest_match_method = tracker.match_method or "distance"

    return (
        occupants,
        occupant_names,
        persons,
        best_rssi,
        closest_dev,
        closest_dist_m,
        closest_match_method,
    )


class LatterBleFabric:
    """Domain-level singleton Bluetooth scanner fabric shared across all Latter & BLE Tag trackers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the shared BLE scanner fabric."""
        self.hass = hass
        self._trackers: list[LatterNativeBleTracker] = []
        self._occupancy_listeners: list[Callable[[], None]] = []
        self._survey_listeners: list[Callable[[dict[str, Any]], None]] = []
        self._unsub_ble: Callable[[], None] | None = None
        self._unsub_registry_events: Callable[[], None] | None = None
        self._adv_unsubs: dict[str, Callable[[], None]] = {}
        self._unsub_away_timer: Callable[[], None] | None = None
        self._unsub_sensor_events: Callable[[], None] | None = None
        self._batch_coord_map: dict[str, Any] | None = None
        self._batch_occ_cache: dict[str, dict[str, Any]] | None = None

    def has_tracker(self, tracker: Any) -> bool:
        """Return True if `tracker` is registered on this fabric."""
        return tracker in self._trackers

    @callback
    def _ensure_registry_listeners(self) -> None:
        """Keep Area/Device/Entity/Floor registry cache invalidation active while needed."""
        if self._unsub_registry_events is not None:
            return
        set_scanner_area_cache_active(self.hass, True)
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
            set_scanner_area_cache_active(self.hass, False)

    @callback
    def _invalidate_caches(self, _event: Any = None) -> None:
        """Invalidate scanner-to-Area caches, fusion index, and targeted fusion listeners."""
        clear_scanner_area_cache(self.hass)
        for tracker in self._trackers:
            tracker.invalidate_scanner_cache()
        self.sync_tracker_addresses()
        invalidate_area_fusion_index(self.hass)
        if self._occupancy_listeners:
            self.rebind_fusion_sensor_listener()
            self.notify_occupancy_listeners()

    @callback
    def rebind_fusion_sensor_listener(self) -> None:
        """Subscribe ONLY to tracked Area fusion `binary_sensors` (never global `state_changed`)."""
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
        """Register a listener for real-time per-Area BLE & sensor-fused occupancy changes."""
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
    def emit_survey_delta(self, tracker: Any) -> None:
        """Push a compact `ble_survey_delta` payload to active Studio site survey subscribers."""
        if not self._survey_listeners:
            return
        payload = {
            "device_slug": tracker.raw_slug,
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
        """Notify all registered occupancy listeners with single-pass coordinator/Area batching (`M-P2-19`)."""
        if not self._occupancy_listeners:
            return
        was_outer = self._batch_occ_cache is None
        if was_outer:
            self._batch_coord_map = {
                coord.device_slug: coord
                for coord in iter_coordinators(self.hass)
                if coord.device_slug
            }
            self._batch_occ_cache = {}
        try:
            for listener in list(self._occupancy_listeners):
                listener()
        finally:
            if was_outer:
                self._batch_coord_map = None
                self._batch_occ_cache = None

    @callback
    def get_area_occupancy(
        self,
        area_id: str,
        *,
        coord_by_slug: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return deterministic & weighted fused BLE + physical sensor occupancy telemetry for an Area."""
        if (
            coord_by_slug is None
            and self._batch_occ_cache is not None
            and area_id in self._batch_occ_cache
        ):
            return self._batch_occ_cache[area_id]

        area_reg = ar.async_get(self.hass)
        area_obj = (
            area_reg.async_get(area_id) if hasattr(area_reg, "async_get") else None
        )
        if area_obj is None:
            area_obj = area_reg.async_get_area(area_id)
        floor_id = getattr(area_obj, "floor_id", None) if area_obj else None

        resolved_coords: Mapping[str, Any]
        if coord_by_slug is not None:
            resolved_coords = coord_by_slug
        elif self._batch_coord_map is not None:
            resolved_coords = self._batch_coord_map
        else:
            resolved_coords = {
                coord.device_slug: coord
                for coord in iter_coordinators(self.hass)
                if coord.device_slug
            }

        (
            occupants,
            occupant_names,
            persons,
            best_rssi,
            closest_dev,
            closest_dist_m,
            closest_match_method,
        ) = _collect_area_tracker_occupants(
            self.hass, self._trackers, area_id, resolved_coords
        )

        fused = evaluate_area_sensor_fusion(
            self.hass,
            area_id,
            ble_present=len(occupants) > 0,
            best_rssi=best_rssi,
        )
        clean_floor_id, floor_name = resolve_floor_info(self.hass, floor_id)

        result: dict[str, Any] = {
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
            "match_method": closest_match_method,
            "floor_id": floor_id,
            "floor_name": floor_name if clean_floor_id else "",
        }
        if coord_by_slug is None and self._batch_occ_cache is not None:
            self._batch_occ_cache[area_id] = result
        return result

    @callback
    def sync_tracker_addresses(self) -> None:
        """Subscribe directly to every advertisement for known tracker MACs."""
        if self._unsub_ble is None:
            return
        wanted: set[str] = set()
        for tracker in self._trackers:
            wanted.update(mac.upper() for mac in tracker.target_macs_formatted if mac)
            wanted.update(
                matched.upper() for matched in tracker._matched_ble_addresses if matched
            )

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
    def register_tracker(self, tracker: Any) -> None:
        """Register a BLE tracker and start the shared passive callback fabric if needed."""
        if tracker not in self._trackers:
            self._trackers.append(tracker)
        if len(self._trackers) == 1 and self._unsub_ble is None:
            self._async_start_fabric()
        self.sync_tracker_addresses()
        self.seed_tracker_from_scanners_once(tracker)
        self.notify_occupancy_listeners()

    @callback
    def unregister_tracker(self, tracker: Any) -> None:
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
        """Start the shared passive Bluetooth callback and away-timeout timer."""
        self._ensure_registry_listeners()
        set_scanner_area_cache_active(self.hass, True)
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
        clear_scanner_area_cache(self.hass)
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
        """Ingest custom `esphome.ibeacon_seen` bus events emitted by ESPHome BLE proxies."""
        data = getattr(event, "data", {}) or {}
        source = str(data.get("source") or data.get("scanner") or "").strip()
        uuid_raw = normalize_uuid_hex(str(data.get("uuid") or ""))
        rssi_int = safe_rssi_int(data.get("rssi"))
        if not source or rssi_int is None or rssi_int <= _MIN_VALID_RSSI_DBM:
            return
        adv_addr = str(data.get("address") or data.get("mac") or "").strip().upper()
        adv_int = mac_to_int(adv_addr) if adv_addr else None
        ev_major = coerce_uint16(data.get("major"))
        ev_minor = coerce_uint16(data.get("minor"))
        now_mono = time.monotonic()
        for tracker in list(self._trackers):
            if _ibeacon_event_matches_tracker(
                tracker, uuid_raw, adv_int, ev_major, ev_minor
            ):
                tracker._ingest_proxy_observation(source, rssi_int, now_mono, source)

    @callback
    def _async_on_raw_ble_advertisement(self, service_info: object) -> None:
        self._async_on_shared_ble_advertisement(service_info, None)

    @callback
    def _async_on_shared_ble_advertisement(
        self, service_info: object, change: object
    ) -> None:
        for tracker in list(self._trackers):
            tracker._async_on_ble_advertisement(service_info, change)

    @callback
    def _async_check_away_timeouts(self, _now_dt: datetime) -> None:
        if not self._trackers:
            return
        now_mono = time.monotonic()
        discovered_any = False
        for tracker in list(self._trackers):
            if (
                tracker.packets_seen == 0
                or (now_mono - tracker.last_packet_monotonic) > STALE_PROXY_SECONDS
            ):
                self.seed_tracker_from_scanners_once(tracker)
            tracker.check_away_timeout(now_mono)
            if tracker.maybe_discover_bound_macs(now_mono, _MAC_DISCOVERY_RETRY_S):
                discovered_any = True
        if discovered_any:
            self.sync_tracker_addresses()

    @callback
    def seed_tracker_from_scanners_once(
        self, tracker: Any, *, only_address: str = ""
    ) -> None:
        """Seed `tracker` from current Bluetooth scanner state (optionally restricted to `only_address`)."""
        only_norm = only_address.strip().upper()
        now_mono = time.monotonic()
        for scanner in current_ble_scanners(self.hass):
            source = str(getattr(scanner, "source", "") or "")
            if not source:
                continue
            scanner_name = str(getattr(scanner, "name", "") or source)
            timestamps: dict[str, float] = (
                getattr(scanner, "discovered_device_timestamps", None)
                or getattr(scanner, "timestamps", None)
                or {}
            )
            dev_adv_map: dict[str, tuple[Any, Any]] = (
                getattr(scanner, "discovered_devices_and_advertisement_data", None)
                or {}
            )
            for addr, pair in dev_adv_map.items():
                if not isinstance(pair, tuple) or len(pair) != _PAIR_TUPLE_LEN:
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
                det_rp = extract_adv_ref_power_dbm(adv_data, mfg_data, svc_data)
                if det_rp is not None:
                    tracker.detected_ref_power_dbm = det_rp
                last_ts = timestamps.get(addr)
                obs_mono = float(last_ts) if last_ts is not None else now_mono
                if (
                    last_ts is not None
                    and (now_mono - obs_mono) > SURVEY_RETENTION_SECONDS
                ):
                    continue
                raw_rssi = getattr(adv_data, "rssi", None)
                if raw_rssi is None:
                    raw_rssi = getattr(ble_dev, "rssi", None)
                rssi_int = safe_rssi_int(raw_rssi)
                if rssi_int is None or rssi_int <= _MIN_VALID_RSSI_DBM:
                    continue
                tracker._ingest_proxy_observation(
                    source,
                    rssi_int,
                    obs_mono,
                    scanner_name,
                    from_poll=last_ts is not None,
                )

    _async_seed_tracker_from_scanners_once = seed_tracker_from_scanners_once


def get_ble_fabric(hass: HomeAssistant) -> LatterBleFabric:
    """Return or initialize the singleton `LatterBleFabric` instance."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    existing = domain_data.get("ble_fabric")
    if isinstance(existing, LatterBleFabric):
        return existing
    fabric = LatterBleFabric(hass)
    domain_data["ble_fabric"] = fabric
    return fabric


register_ble_fabric_getter(get_ble_fabric)


def get_all_areas_presence_summary(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Build live per-Area presence, occupant names, confidence score, and fusion/lux settings."""
    area_reg = ar.async_get(hass)
    fabric = get_ble_fabric(hass)
    proxy_areas = get_ble_proxy_area_ids(hass)
    sig_areas = get_ble_signature_area_ids(hass)
    coord_by_slug = {
        coord.device_slug: coord
        for coord in iter_coordinators(hass)
        if coord.device_slug
    }

    rows: list[dict[str, Any]] = []
    for area_entry in sorted(area_reg.async_list_areas(), key=lambda a: a.name.lower()):
        occ = fabric.get_area_occupancy(area_entry.id, coord_by_slug=coord_by_slug)
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
        raw_fusion_sensors = fusion_cfg.get("sensors")
        fusion_sensors = [
            str(s) for s in (raw_fusion_sensors or []) if isinstance(s, str)
        ]
        fusion_choices = (
            area_fusion_sensor_choices(hass, area_entry.id)
            if fusion_sensors
            else occ["available_sensors"]
        )
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
                "fusion_threshold_pct": int(
                    fusion_cfg.get("threshold_pct") or _DEFAULT_FUSION_THRESHOLD_PCT
                ),
                "fusion_sensors": fusion_sensors,
                "fusion_sensor_choices": fusion_choices,
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
