"""Shared `LatterBleFabric` singleton and per-Area presence summary builder."""

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
    latter_bound_esphome_device_ids,
    resolve_area_ambient_light,
)
from ..hub_registry import (
    _is_irrelevant_registry_update,
    get_domain_data,
    iter_coordinators,
)
from .area_fusion import (
    area_fusion_sensor_choices,
    area_fusion_settings,
    evaluate_area_sensor_fusion,
    get_tracked_fusion_entity_ids,
    invalidate_area_fusion_index,
)
from .ble_math import EDDYSTONE_UUID_PREFIX, STALE_PROXY_SECONDS, safe_rssi_int
from .ble_registry import (
    APPLE_COMPANY_ID,
    AWAY_CHECK_INTERVAL_SECONDS,
    IBEACON_PREFIX,
    SURVEY_RETENTION_SECONDS,
    clear_scanner_area_cache,
    coerce_uint16,
    current_ble_scanners,
    extract_adv_ref_power_dbm,
    get_ble_proxy_area_ids,
    get_ble_signature_area_ids,
    mac_to_int,
    normalize_uuid_hex,
    resolve_floor_info,
    set_scanner_area_cache_active,
)
from .ble_tracker import LatterNativeBleTracker, register_ble_fabric_getter

__all__ = [
    "EDDYSTONE_SERVICE_DATA_UUID",
    "LatterBleFabric",
    "build_survey_delta_payload",
    "get_all_areas_presence_summary",
    "get_ble_fabric",
]

_LOGGER = logging.getLogger(__name__)

EDDYSTONE_SERVICE_DATA_UUID: Final = "0000feaa-0000-1000-8000-00805f9b34fb"
_MIN_VALID_RSSI_DBM: Final = -100
_MAC_DISCOVERY_RETRY_S: Final = 30.0
_PAIR_TUPLE_LEN: Final = 2
_DEFAULT_FUSION_THRESHOLD_PCT: Final = 50
_IBEACON_MIN_BYTES: Final = 20
_EDDYSTONE_UID_MIN_BYTES: Final = 18
_EDDYSTONE_FRAME_MASK: Final = 0xF0


def build_survey_delta_payload(
    tracker: Any, *, subentry_id: str = ""
) -> dict[str, Any]:
    """Build an on-demand `ble_survey_delta` payload for a single BLE tracker."""
    resolved_sub = str(
        subentry_id or getattr(tracker, "subentry_id", "") or ""
    ).strip()
    return {
        "type": "ble_survey_delta",
        "subentry_id": resolved_sub,
        "device_slug": str(getattr(tracker, "raw_slug", "") or ""),
        "ble_survey_rows": tracker.get_scanner_calibration_telemetry(),
        "ble_packets_seen": int(getattr(tracker, "packets_seen", 0) or 0),
        "ble_closest_proxy": str(getattr(tracker, "closest_scanner", "") or ""),
    }


def _extract_adv_keys(
    address: str,
    mfg_data: Mapping[int, bytes],
    service_data: Mapping[str, bytes],
) -> tuple[int | None, str, str, str]:
    """Parse `(mac_int, ibeacon_uuid_hex, eddystone_uid_hex, eddystone_ns_hex)` once."""
    adv_int = mac_to_int(address) if address else None
    ibeacon_uuid = ""
    apple_bytes = mfg_data.get(APPLE_COMPANY_ID)
    if (
        apple_bytes
        and len(apple_bytes) >= _IBEACON_MIN_BYTES
        and apple_bytes[:2] == IBEACON_PREFIX
    ):
        ibeacon_uuid = apple_bytes[2:18].hex().lower()

    eddystone_uid = ""
    eddystone_ns = ""
    for svc_uuid, svc_bytes in service_data.items():
        u_low = str(svc_uuid).lower()
        if (
            (u_low.startswith(EDDYSTONE_UUID_PREFIX) or u_low == "feaa")
            and isinstance(svc_bytes, (bytes, bytearray))
            and len(svc_bytes) >= _EDDYSTONE_UID_MIN_BYTES
            and (svc_bytes[0] & _EDDYSTONE_FRAME_MASK) == 0x00
        ):
            raw_b = bytes(svc_bytes)
            eddystone_uid = raw_b[2:18].hex().lower()
            eddystone_ns = raw_b[2:12].hex().lower()
            break
    return adv_int, ibeacon_uuid, eddystone_uid, eddystone_ns


def _ibeacon_event_matches_tracker(
    tracker: LatterNativeBleTracker,
    uuid_raw: str,
    adv_int: int | None,
    ev_major: int | None,
    ev_minor: int | None,
    *,
    allow_ibeacon_fallback: bool = True,
) -> bool:
    if not (uuid_raw and uuid_raw == tracker._target_uuid_hex):
        return False
    expected_major, expected_minor = tracker._resolve_beacon_major_minor()
    if tracker._explicit_major is not None or tracker._explicit_minor is not None:
        if not allow_ibeacon_fallback:
            return False
        maj_ok = tracker._explicit_major is None or ev_major == expected_major
        min_ok = tracker._explicit_minor is None or ev_minor == expected_minor
        return maj_ok and min_ok

    if tracker.owns_bound_mac_int(adv_int):
        return True
    if not allow_ibeacon_fallback:
        return False
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
        self._trackers_by_mac: dict[int, list[LatterNativeBleTracker]] = {}
        self._trackers_by_ibeacon_uuid: dict[str, list[LatterNativeBleTracker]] = {}
        self._trackers_by_eddystone: dict[str, list[LatterNativeBleTracker]] = {}
        self._fallback_trackers: list[LatterNativeBleTracker] = []
        self._occupancy_listeners: list[Callable[[], None]] = []
        self._survey_listeners: list[tuple[Callable[[Any], None], str | None]] = []
        self._unsub_ble: Callable[[], None] | None = None
        self._unsub_eddystone: Callable[[], None] | None = None
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
    def _invalidate_caches(self, event: Any = None) -> None:
        """Invalidate scanner-to-Area caches, fusion index, and targeted fusion listeners."""
        if event is not None and _is_irrelevant_registry_update(
            str(getattr(event, "event_type", "") or ""),
            getattr(event, "data", None),
        ):
            return
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
        self,
        cb: Callable[[Any], None],
        *,
        subentry_id: str | None = None,
    ) -> Callable[[], None]:
        """Register a Studio WebSocket listener for live survey tracker updates."""
        norm_sub = str(subentry_id).strip() if subentry_id else None
        entry = (cb, norm_sub)
        if entry not in self._survey_listeners:
            self._survey_listeners.append(entry)

        @callback
        def _unsub() -> None:
            if entry in self._survey_listeners:
                self._survey_listeners.remove(entry)

        unsub: Callable[[], None] = _unsub
        return unsub

    @callback
    def emit_survey_delta(self, tracker: Any) -> None:
        """Notify active Studio survey listeners matching `tracker` with zero heavy payload work."""
        if not self._survey_listeners:
            return
        tracker_sub = str(getattr(tracker, "subentry_id", "") or "").strip()
        for cb, filter_sub in list(self._survey_listeners):
            if filter_sub is not None and tracker_sub != filter_sub:
                continue
            cb(tracker)

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
        """Notify all registered occupancy listeners with single-pass coordinator/Area batching."""
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
    def _rebuild_tracker_index(self) -> None:
        """Rebuild O(1) lookup indices from active trackers."""
        by_mac: dict[int, list[LatterNativeBleTracker]] = {}
        by_uuid: dict[str, list[LatterNativeBleTracker]] = {}
        by_eddy: dict[str, list[LatterNativeBleTracker]] = {}
        fallback: list[LatterNativeBleTracker] = []

        for tracker in self._trackers:
            indexed = False
            mac_ints: set[int] = set(tracker._target_mac_ints)
            if tracker._dynamic_target_mac_int is not None:
                mac_ints.add(tracker._dynamic_target_mac_int)
            for matched_addr in tracker._matched_ble_addresses:
                if (m_int := mac_to_int(matched_addr)) is not None:
                    mac_ints.add(m_int)
            for m_int in mac_ints:
                by_mac.setdefault(m_int, []).append(tracker)
                indexed = True
            if tracker._target_uuid_hex:
                by_uuid.setdefault(tracker._target_uuid_hex, []).append(tracker)
                indexed = True
                if tracker.wants_eddystone_matcher:
                    by_eddy.setdefault(tracker._target_uuid_hex, []).append(tracker)
            if tracker._target_eddystone_namespace_hex:
                by_eddy.setdefault(
                    tracker._target_eddystone_namespace_hex, []
                ).append(tracker)
                indexed = True
            if not indexed:
                fallback.append(tracker)

        self._trackers_by_mac = by_mac
        self._trackers_by_ibeacon_uuid = by_uuid
        self._trackers_by_eddystone = by_eddy
        self._fallback_trackers = fallback

    @callback
    def _sync_eddystone_matcher(self) -> None:
        """Register the Eddystone-UID service-data matcher ONLY while an Eddystone tracker is active."""
        want_eddystone = self._unsub_ble is not None and any(
            t.wants_eddystone_matcher for t in self._trackers
        )
        if not want_eddystone:
            if self._unsub_eddystone is not None:
                self._unsub_eddystone()
                self._unsub_eddystone = None
            return
        if self._unsub_eddystone is not None:
            return
        try:
            from homeassistant.components import bluetooth

            try:
                ed_matcher = bluetooth.BluetoothCallbackMatcher(
                    service_data_uuid=EDDYSTONE_SERVICE_DATA_UUID,
                    connectable=False,
                )
            except TypeError:
                ed_matcher = bluetooth.BluetoothCallbackMatcher(
                    service_data_uuid=EDDYSTONE_SERVICE_DATA_UUID,
                )
            self._unsub_eddystone = bluetooth.async_register_callback(
                self.hass,
                self._async_on_shared_ble_advertisement,
                ed_matcher,
                bluetooth.BluetoothScanningMode.PASSIVE,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Eddystone Bluetooth callback registration skipped: %s", err)

    @callback
    def _subscribe_missing_macs(self, missing: list[str]) -> None:
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
                return
            for addr in missing:
                self._adv_unsubs[addr] = bluetooth.async_register_callback(
                    self.hass,
                    self._async_on_shared_ble_advertisement,
                    bluetooth.BluetoothCallbackMatcher(address=addr),
                    bluetooth.BluetoothScanningMode.PASSIVE,
                )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Raw BLE advertisement callback sync skipped: %s", err)

    @callback
    def sync_tracker_addresses(self) -> None:
        """Refresh O(1) tracker indices, Eddystone matcher, and per-MAC advertisement callbacks."""
        self._rebuild_tracker_index()
        self._sync_eddystone_matcher()
        if self._unsub_ble is None:
            return
        wanted: set[str] = {
            mac.upper()
            for tracker in self._trackers
            for mac in (*tracker.target_macs_formatted, *tracker._matched_ble_addresses)
            if mac
        }
        for stale_addr in list(self._adv_unsubs):
            if stale_addr not in wanted and (
                unsub := self._adv_unsubs.pop(stale_addr, None)
            ) is not None:
                unsub()
        missing = sorted(wanted - set(self._adv_unsubs))
        if missing:
            self._subscribe_missing_macs(missing)

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
        """Start targeted passive Bluetooth callbacks (Apple iBeacon + per-MAC + conditional Eddystone)."""
        self._ensure_registry_listeners()
        set_scanner_area_cache_active(self.hass, True)
        unsubs: list[Callable[[], None]] = []
        try:
            from homeassistant.components import bluetooth

            try:
                matcher = bluetooth.BluetoothCallbackMatcher(
                    manufacturer_id=APPLE_COMPANY_ID,
                    manufacturer_data_start=[0x02, 0x15],
                    connectable=False,
                )
            except TypeError:
                try:
                    matcher = bluetooth.BluetoothCallbackMatcher(
                        manufacturer_id=APPLE_COMPANY_ID,
                        manufacturer_data_start=[0x02, 0x15],
                    )
                except TypeError:
                    matcher = bluetooth.BluetoothCallbackMatcher(
                        manufacturer_id=APPLE_COMPANY_ID,
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
        self._sync_eddystone_matcher()
        self._unsub_away_timer = async_track_time_interval(
            self.hass,
            self._async_check_away_timeouts,
            timedelta(seconds=AWAY_CHECK_INTERVAL_SECONDS),
        )

    @callback
    def _async_stop_fabric(self) -> None:
        """Stop the shared Bluetooth callbacks, per-address raw callbacks, and away-timeout timer."""
        clear_scanner_area_cache(self.hass)
        for unsub_adv in list(self._adv_unsubs.values()):
            unsub_adv()
        self._adv_unsubs.clear()
        if self._unsub_eddystone is not None:
            self._unsub_eddystone()
            self._unsub_eddystone = None
        if self._unsub_ble is not None:
            self._unsub_ble()
            self._unsub_ble = None
        if self._unsub_away_timer is not None:
            self._unsub_away_timer()
            self._unsub_away_timer = None
        self._trackers_by_mac.clear()
        self._trackers_by_ibeacon_uuid.clear()
        self._trackers_by_eddystone.clear()
        self._fallback_trackers.clear()
        if not self._occupancy_listeners and self._unsub_sensor_events is not None:
            self._unsub_sensor_events()
            self._unsub_sensor_events = None
        self._maybe_stop_registry_listeners()

    def _candidate_trackers_for_keys(
        self,
        adv_int: int | None,
        ibeacon_uuid: str,
        eddystone_uid: str = "",
        eddystone_ns: str = "",
    ) -> list[LatterNativeBleTracker]:
        """Return deduplicated candidate trackers matching the parsed advertisement keys in O(1)."""
        buckets = [
            bucket
            for bucket in (
                self._trackers_by_mac.get(adv_int) if adv_int is not None else None,
                self._trackers_by_ibeacon_uuid.get(ibeacon_uuid) if ibeacon_uuid else None,
                self._trackers_by_eddystone.get(eddystone_uid) if eddystone_uid else None,
                self._trackers_by_eddystone.get(eddystone_ns) if eddystone_ns else None,
                self._fallback_trackers or None,
            )
            if bucket
        ]
        if not buckets:
            return []
        if len(buckets) == 1:
            return list(buckets[0])
        seen: set[int] = set()
        out: list[LatterNativeBleTracker] = []
        for bucket in buckets:
            for trk in bucket:
                if (tid := id(trk)) not in seen:
                    seen.add(tid)
                    out.append(trk)
        return out

    def _bound_mac_owner_ids(self, adv_int: int | None) -> set[int]:
        """Return object IDs of registered trackers owning `adv_int` via static or dynamic MAC."""
        if adv_int is None:
            return set()
        return {id(t) for t in self._trackers if t.owns_bound_mac_int(adv_int)}

    @staticmethod
    def _allow_fallback_for_tracker(
        tracker: Any, adv_int: int | None, owner_ids: set[int]
    ) -> bool:
        """Allow `(UUID, major, minor)` fallback unless another tracker explicitly owns `adv_int`."""
        return (
            not owner_ids
            or id(tracker) in owner_ids
            or bool(tracker.owns_bound_mac_int(adv_int))
        )

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
        candidates = self._candidate_trackers_for_keys(adv_int, uuid_raw)
        if not candidates:
            return
        ev_major = coerce_uint16(data.get("major"))
        ev_minor = coerce_uint16(data.get("minor"))
        now_mono = time.monotonic()
        owner_ids = self._bound_mac_owner_ids(adv_int)
        for tracker in candidates:
            allow_fallback = self._allow_fallback_for_tracker(tracker, adv_int, owner_ids)
            if _ibeacon_event_matches_tracker(
                tracker,
                uuid_raw,
                adv_int,
                ev_major,
                ev_minor,
                allow_ibeacon_fallback=allow_fallback,
            ):
                tracker._ingest_proxy_observation(source, rssi_int, now_mono, source)

    @callback
    def _async_on_raw_ble_advertisement(self, service_info: object) -> None:
        self._async_on_shared_ble_advertisement(service_info, None)

    @callback
    def _async_on_shared_ble_advertisement(
        self, service_info: object, change: object
    ) -> None:
        adv_addr = str(getattr(service_info, "address", "") or "").strip().upper()
        mfg_data: Mapping[int, bytes] = getattr(service_info, "manufacturer_data", {}) or {}
        svc_data: Mapping[str, bytes] = getattr(service_info, "service_data", {}) or {}
        adv_int, ib_uuid, ed_uid, ed_ns = _extract_adv_keys(adv_addr, mfg_data, svc_data)
        candidates = self._candidate_trackers_for_keys(adv_int, ib_uuid, ed_uid, ed_ns)
        if not candidates:
            return
        owner_ids = self._bound_mac_owner_ids(adv_int)
        ambiguous_mac = len(owner_ids) > 1
        for tracker in candidates:
            allow_fallback = self._allow_fallback_for_tracker(tracker, adv_int, owner_ids)
            tracker._async_on_ble_advertisement(
                service_info,
                change,
                allow_ibeacon_fallback=allow_fallback,
                ambiguous_bound_mac=ambiguous_mac,
            )

    @callback
    def _async_check_away_timeouts(self, _now_dt: datetime) -> None:
        if not self._trackers:
            return
        now_mono = time.monotonic()
        trackers = list(self._trackers)
        silent_trackers = [
            tracker
            for tracker in trackers
            if tracker.packets_seen == 0
            or (now_mono - tracker.last_packet_monotonic) > STALE_PROXY_SECONDS
        ]
        if silent_trackers:
            self._poll_missed_advertisements(silent_trackers, now_mono)
        discovered_any = False
        for tracker in trackers:
            tracker.check_away_timeout(now_mono)
            if tracker.maybe_discover_bound_macs(now_mono, _MAC_DISCOVERY_RETRY_S):
                discovered_any = True
        if discovered_any:
            self.sync_tracker_addresses()

    def _ingest_scanner_pair_for_candidates(
        self,
        candidates: list[LatterNativeBleTracker],
        addr_str: str,
        adv_int: int | None,
        pair: tuple[Any, Any],
        obs_ctx: tuple[str, str, float | None, float],
    ) -> None:
        source, scanner_name, last_ts, now_mono = obs_ctx
        obs_mono = float(last_ts) if last_ts is not None else now_mono
        is_stale = last_ts is not None and (now_mono - obs_mono) > SURVEY_RETENTION_SECONDS
        ble_dev, adv_data = pair
        mfg_data = getattr(adv_data, "manufacturer_data", {}) or {}
        svc_data = getattr(adv_data, "service_data", {}) or {}
        raw_rssi = getattr(adv_data, "rssi", None)
        if raw_rssi is None:
            raw_rssi = getattr(ble_dev, "rssi", None)
        rssi_int = safe_rssi_int(raw_rssi)
        owner_ids = self._bound_mac_owner_ids(adv_int)
        ambiguous_mac = len(owner_ids) > 1
        det_rp = extract_adv_ref_power_dbm(adv_data, mfg_data, svc_data)
        for tracker in candidates:
            allow_fallback = self._allow_fallback_for_tracker(tracker, adv_int, owner_ids)
            if not tracker._matches_raw_adv(
                addr_str,
                mfg_data,
                svc_data,
                allow_ibeacon_fallback=allow_fallback,
                ambiguous_bound_mac=ambiguous_mac,
            ):
                continue
            tracker._record_matched_ble_address(addr_str, seed_scanners=False)
            if is_stale or rssi_int is None or rssi_int <= _MIN_VALID_RSSI_DBM:
                continue
            if det_rp is not None:
                tracker.detected_ref_power_dbm = det_rp
            tracker._ingest_proxy_observation(
                source,
                rssi_int,
                obs_mono,
                scanner_name,
                from_poll=last_ts is not None,
            )

    @callback
    def _poll_missed_advertisements(
        self,
        silent_trackers: list[LatterNativeBleTracker],
        now_mono: float,
        *,
        only_address: str = "",
    ) -> None:
        """Scan active Bluetooth scanners in ONE pass, dispatching only to `silent_trackers` in O(1)."""
        if not silent_trackers:
            return
        only_norm = only_address.strip().upper()
        silent_ids = {id(t) for t in silent_trackers}
        unregistered = [t for t in silent_trackers if not self.has_tracker(t)]
        for scanner in current_ble_scanners(self.hass):
            source = str(getattr(scanner, "source", "") or "")
            if not source:
                continue
            scanner_name = str(getattr(scanner, "name", "") or source)
            timestamps: dict[str, float] = (
                getattr(scanner, "discovered_device_timestamps", None) or {}
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
                _ble_dev, adv_data = pair
                mfg_data = getattr(adv_data, "manufacturer_data", {}) or {}
                svc_data = getattr(adv_data, "service_data", {}) or {}
                adv_int, ib_uuid, ed_uid, ed_ns = _extract_adv_keys(
                    addr_str, mfg_data, svc_data
                )
                candidates = [
                    t
                    for t in self._candidate_trackers_for_keys(
                        adv_int, ib_uuid, ed_uid, ed_ns
                    )
                    if id(t) in silent_ids
                ]
                if unregistered:
                    candidates.extend(t for t in unregistered if t not in candidates)
                if not candidates:
                    continue
                self._ingest_scanner_pair_for_candidates(
                    candidates,
                    addr_str,
                    adv_int,
                    pair,
                    (source, scanner_name, timestamps.get(addr), now_mono),
                )

    @callback
    def seed_tracker_from_scanners_once(
        self, tracker: Any, *, only_address: str = ""
    ) -> None:
        """Seed `tracker` from current Bluetooth scanner state (optionally restricted to `only_address`)."""
        self._poll_missed_advertisements(
            [tracker], time.monotonic(), only_address=only_address
        )


def get_ble_fabric(hass: HomeAssistant) -> LatterBleFabric:
    """Return or initialize the singleton `LatterBleFabric` instance."""
    domain_data = get_domain_data(hass)
    existing = domain_data.ble_fabric
    if isinstance(existing, LatterBleFabric):
        return existing
    fabric = LatterBleFabric(hass)
    domain_data.ble_fabric = fabric
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
    latter_dev_ids = latter_bound_esphome_device_ids(hass)

    rows: list[dict[str, Any]] = []
    for area_entry in sorted(area_reg.async_list_areas(), key=lambda a: a.name.lower()):
        occ = fabric.get_area_occupancy(area_entry.id, coord_by_slug=coord_by_slug)
        has_proxy = area_entry.id in proxy_areas
        has_sig = area_entry.id in sig_areas
        has_sensors = len(occ["available_sensors"]) > 0
        lux_choices = area_illuminance_sensor_choices(
            hass, area_entry.id, latter_dev_ids=latter_dev_ids
        )
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
        ambient = resolve_area_ambient_light(
            hass,
            area_entry.id,
            latter_dev_ids=latter_dev_ids,
            lux_choices=lux_choices,
        )
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
