"""Native Zero-Config ESPHome BLE Proxy Room Presence Engine for Latter."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import time
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

APPLE_COMPANY_ID = 0x004C
IBEACON_PREFIX = b"\x02\x15"
EMA_ALPHA = 0.50
HYSTERESIS_DB = 5.0
FAST_OVERRIDE_DB = 8.0
STALE_PROXY_SECONDS = 25.0
SURVEY_RETENTION_SECONDS = 180.0
WAKE_GAP_SECONDS = 8.0
MIN_HOLD_SECONDS = 4.0
SCANNER_POLL_INTERVAL_SECONDS = 2.0


def _iter_devices(dev_reg: dr.DeviceRegistry) -> list[dr.DeviceEntry]:
    """Yield DeviceEntry objects across all Home Assistant versions without triggering mapping deprecation warnings."""
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
    """Yield RegistryEntry objects across all Home Assistant versions without triggering mapping deprecation warnings."""
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
    hass: HomeAssistant, device_slug: str
) -> set[int]:
    """Find known Wi-Fi/BLE MAC address integers for the target ESPHome device."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    slug_norm = device_slug.strip().lower().replace("-", "_")

    target_dev_id: str | None = None
    for entry in _iter_entities(ent_reg):
        if entry.platform == "esphome" and slug_norm in entry.entity_id:
            if entry.device_id:
                target_dev_id = entry.device_id
                break

    mac_ints: set[int] = set()
    for dev in _iter_devices(dev_reg):
        dev_name = (
            str(dev.name_by_user or dev.name or "")
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        if dev.id == target_dev_id or (slug_norm and slug_norm in dev_name):
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
    """Return a device's area_id, or fallback to any entity's area_id on that device, or match area name in the device name."""
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


def _resolve_scanner_area_id(
    hass: HomeAssistant, scanner_source: str
) -> str | None:
    """Resolve an ESPHome BLE Proxy source (MAC or name) to its Home Assistant area_id with strict priority."""
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

    # Tier 1: Exact MAC / connection / identifier match (offset == 0)
    for device in all_devices:
        for _conn_type, conn_val in device.connections:
            c_low = str(conn_val).lower()
            c_int = _mac_to_int(c_low)
            if c_low == src_low or (src_int is not None and c_int is not None and src_int == c_int):
                resolved = _resolve_device_area_or_entity_area(device, ent_reg, area_reg)
                if resolved:
                    return resolved
        for _domain, ident_val in device.identifiers:
            i_low = str(ident_val).lower()
            i_int = _mac_to_int(i_low)
            if i_low == src_low or (src_int is not None and i_int is not None and src_int == i_int):
                resolved = _resolve_device_area_or_entity_area(device, ent_reg, area_reg)
                if resolved:
                    return resolved

    # Tier 2: ESP32 base-MAC +/-2 offset match
    if src_int is not None:
        for device in all_devices:
            for _conn_type, conn_val in device.connections:
                c_int = _mac_to_int(str(conn_val))
                if c_int is not None and 0 < abs(src_int - c_int) <= 2:
                    resolved = _resolve_device_area_or_entity_area(device, ent_reg, area_reg)
                    if resolved:
                        return resolved
            for _domain, ident_val in device.identifiers:
                i_int = _mac_to_int(str(ident_val))
                if i_int is not None and 0 < abs(src_int - i_int) <= 2:
                    resolved = _resolve_device_area_or_entity_area(device, ent_reg, area_reg)
                    if resolved:
                        return resolved

    # Tier 3: Exact device name match
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
                    resolved = _resolve_device_area_or_entity_area(device, ent_reg, area_reg)
                    if resolved:
                        return resolved

    # Tier 4: Match scanner_name directly against Home Assistant Area names (longest area name first)
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


def get_ble_proxy_area_ids(hass: HomeAssistant) -> set[str]:
    """Return the set of Home Assistant area_ids that actually have a Bluetooth proxy/scanner."""
    proxy_areas: set[str] = set()
    try:
        from homeassistant.components import bluetooth

        scanners = bluetooth.async_current_scanners(hass)
        for scanner in scanners:
            source = str(getattr(scanner, "source", "") or "")
            if source:
                a_id = _resolve_scanner_area_id(hass, source)
                if a_id:
                    proxy_areas.add(a_id)
    except Exception:  # noqa: BLE001
        pass
    return proxy_areas


def get_all_scanners_diagnostic_map(hass: HomeAssistant) -> dict[str, str]:
    """Return a diagnostic dictionary of all registered HA Bluetooth scanners -> resolved Area name."""
    out: dict[str, str] = {}
    area_reg = ar.async_get(hass)
    try:
        from homeassistant.components import bluetooth

        scanners = bluetooth.async_current_scanners(hass)
        for scanner in scanners:
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
    """Tracks a mobile ESPHome BLE iBeacon across ESPHome BLE Proxies to auto-detect the room."""

    def __init__(
        self,
        hass: HomeAssistant,
        beacon_uuid: str,
        device_slug: str,
        on_area_detected: Callable[[str, str], None],
        room_offsets: dict[str, float] | None = None,
    ) -> None:
        """Initialize the native BLE proxy room tracker."""
        self.hass = hass
        self._target_uuid_hex = _normalize_uuid_hex(beacon_uuid)
        self._device_slug = device_slug.lower().replace("_", "-")
        self._raw_slug = device_slug
        self._on_area_detected = on_area_detected
        self._room_offsets: dict[str, float] = {
            str(k): float(v) for k, v in (room_offsets or {}).items()
        }

        self._unsub_ble: Callable[[], None] | None = None
        self._unsub_poll: Callable[[], None] | None = None
        # area_id -> (ema_effective_rssi, last_seen_monotonic)
        self._area_rssi: dict[str, tuple[float, float]] = {}
        # area_id -> (ema_raw_rssi, last_seen_monotonic, scanner_name)
        self._area_raw_rssi: dict[str, tuple[float, float, str]] = {}
        # raw_source -> (rssi, last_seen_monotonic) for unmapped proxy diagnostics
        self._unmapped_rssi: dict[str, tuple[int, float]] = {}
        self._scanner_area_cache: dict[str, str | None] = {}
        self._target_mac_ints: set[int] = set()
        self._matched_ble_addresses: set[str] = set()
        self.current_area_id: str | None = None
        self.closest_scanner: str = ""
        self.packets_seen: int = 0
        self.last_packet_monotonic: float = 0.0
        self._last_switch_monotonic: float = 0.0

    @property
    def target_macs_formatted(self) -> list[str]:
        """Return the list of candidate Wi-Fi/BLE MAC addresses for the target ESPHome device."""
        return sorted(_int_to_mac(m) for m in self._target_mac_ints)

    @callback
    def set_room_offsets(self, offsets: dict[str, float] | None) -> None:
        """Update per-room RSSI calibration offsets (dB bias) in real time and recompute effective RSSI."""
        self._room_offsets = {
            str(k): max(-25.0, min(25.0, float(v)))
            for k, v in (offsets or {}).items()
        }
        now = time.monotonic()
        for area_id, (raw_ema, ts, _scanner) in list(self._area_raw_rssi.items()):
            offset_db = float(self._room_offsets.get(area_id, 0.0))
            self._area_rssi[area_id] = (raw_ema + offset_db, ts)
        self._evaluate_best_room(now)

    @callback
    def reset_for_device_wake(self) -> None:
        """Clear stale RSSI history only if no packet was received in the last 6 seconds."""
        now = time.monotonic()
        if self.last_packet_monotonic > 0.0 and (now - self.last_packet_monotonic) < 6.0:
            return
        self._area_rssi.clear()
        self._unmapped_rssi.clear()
        self._scanner_area_cache.clear()
        self.current_area_id = None
        self._last_switch_monotonic = 0.0
        self._target_mac_ints = _discover_target_device_macs(
            self.hass, self._raw_slug
        )

    @callback
    def async_start(self) -> None:
        """Register this tracker with the singleton LatterBleFabric."""
        self.async_stop()
        self._target_mac_ints = _discover_target_device_macs(
            self.hass, self._raw_slug
        )
        fabric = get_ble_fabric(self.hass)
        fabric.register_tracker(self)
        _LOGGER.info(
            "Latter Native BLE Room Tracker registered with shared BLE Fabric (device=%s, UUID=%s, macs=%s)",
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

    def get_live_rssi_summary(self) -> dict[str, int]:
        """Return a snapshot of area_name -> smoothed effective RSSI (dBm) for sensor attributes."""
        area_reg = ar.async_get(self.hass)
        now = time.monotonic()
        out: dict[str, int] = {}
        for area_id, (ema, ts) in self._area_rssi.items():
            if (now - ts) <= SURVEY_RETENTION_SECONDS:
                area_obj = area_reg.async_get_area(area_id)
                label = area_obj.name if area_obj else area_id
                out[label] = int(round(ema))
        for raw_src, (raw_rssi, ts) in self._unmapped_rssi.items():
            if (now - ts) <= SURVEY_RETENTION_SECONDS:
                out[f"unmapped:{raw_src}"] = int(raw_rssi)
        return out

    def get_room_calibration_telemetry(self) -> list[dict[str, Any]]:
        """Return rich per-room BLE site survey telemetry (all proxy rooms, raw dBm, offset dB, effective dBm, age, winner)."""
        area_reg = ar.async_get(self.hass)
        now = time.monotonic()

        # Discover all areas that have at least one registered Bluetooth scanner
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

        # Union of proxy areas, areas with recent RSSI, and areas with configured offsets
        all_area_ids = (
            set(area_scanners.keys())
            | set(self._area_raw_rssi.keys())
            | set(self._room_offsets.keys())
        )

        rows: list[dict[str, Any]] = []
        for area_id in all_area_ids:
            area_obj = area_reg.async_get_area(area_id)
            area_name = area_obj.name if area_obj else area_id
            offset_db = round(float(self._room_offsets.get(area_id, 0.0)), 1)
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
                    raw_dbm = int(round(raw_ema))
                    effective_dbm = int(round(raw_ema + offset_db))
                    age_s = int(round(elapsed))
                    is_fresh = elapsed <= STALE_PROXY_SECONDS
                    if last_scan and not scanner_label:
                        scanner_label = last_scan

            dist_m: float | None = None
            dist_ft: float | None = None
            if effective_dbm is not None:
                # Log-distance path-loss model (TxPower = -59 dBm @ 1m, indoor n = 2.2)
                dist_m = round(max(0.2, min(50.0, 10.0 ** ((-59.0 - effective_dbm) / (10.0 * 2.2)))), 1)
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
        name: str,
        mfg_data: dict[int, bytes],
    ) -> bool:
        """Return True if raw advertisement fields match this specific device's MAC/name or iBeacon UUID."""
        adv_int = _mac_to_int(address) if address else None

        # 1. Exact hardware Wi-Fi/BLE MAC range match (+/-2 offset from HA Device Registry)
        if address and address in self._matched_ble_addresses:
            return True
        if self._target_mac_ints and adv_int is not None and adv_int in self._target_mac_ints:
            return True

        # 2. Local BLE device name match
        adv_name = name.lower().replace("_", "-") if name else ""
        if adv_name and self._device_slug in adv_name:
            return True

        # 3. Apple iBeacon UUID match (if multiple Latter devices share the default UUID and this
        #    device's MAC range is known, require the advertisement MAC to match this device so
        #    multiple devices using latter-ble-beacon.yaml never cross-talk!)
        apple_bytes = mfg_data.get(APPLE_COMPANY_ID)
        if apple_bytes and len(apple_bytes) >= 18:
            uuid_matched = False
            if len(apple_bytes) >= 20 and apple_bytes[:2] == IBEACON_PREFIX:
                uuid_hex = apple_bytes[2:18].hex().lower()
                uuid_matched = uuid_hex == self._target_uuid_hex
            elif self._target_uuid_hex in apple_bytes.hex().lower():
                uuid_matched = True
            if uuid_matched:
                if self._target_mac_ints and adv_int is not None:
                    return adv_int in self._target_mac_ints
                return True

        return False

    def _matches_target_device(self, service_info: object) -> bool:
        """Return True if a BluetoothServiceInfoBleak object matches iBeacon UUID, MAC, or local name."""
        mfg_data: dict[int, bytes] = getattr(
            service_info, "manufacturer_data", {}
        ) or {}
        adv_address = str(getattr(service_info, "address", "") or "")
        adv_name = str(getattr(service_info, "name", "") or "")
        matched = self._matches_raw_adv(adv_address, adv_name, mfg_data)
        if matched and adv_address:
            self._matched_ble_addresses.add(adv_address)
        return matched

    @callback
    def _async_poll_scanner_tables(self, _now: datetime) -> None:
        """Poll each ESPHome BLE Proxy's live advertisement table to bypass habluetooth static-iBeacon deduplication."""
        if not self._target_mac_ints:
            self._target_mac_ints = _discover_target_device_macs(
                self.hass, self._raw_slug
            )

        try:
            from homeassistant.components import bluetooth

            now_mono = time.monotonic()
            scanners = bluetooth.async_current_scanners(self.hass)
            for scanner in scanners:
                source = str(getattr(scanner, "source", "") or "")
                scanner_name = str(getattr(scanner, "name", "") or source)
                if not source:
                    continue

                timestamps: dict[str, float] = getattr(
                    scanner, "_previous_seen_timestamps", {}
                ) or getattr(scanner, "timestamps", {}) or {}

                dev_adv_map: dict[str, tuple[Any, Any]] = getattr(
                    scanner, "discovered_devices_and_advertisement_data", {}
                ) or {}

                for addr, pair in dev_adv_map.items():
                    if not isinstance(pair, tuple) or len(pair) != 2:
                        continue
                    ble_dev, adv_data = pair
                    last_ts = timestamps.get(addr)
                    obs_mono = float(last_ts) if last_ts is not None else now_mono
                    if last_ts is not None and (now_mono - obs_mono) > SURVEY_RETENTION_SECONDS:
                        continue

                    mfg_data = getattr(adv_data, "manufacturer_data", {}) or {}
                    local_name = str(
                        getattr(adv_data, "local_name", "")
                        or getattr(ble_dev, "name", "")
                        or ""
                    )
                    if not self._matches_raw_adv(str(addr), local_name, mfg_data):
                        continue

                    self._matched_ble_addresses.add(str(addr))
                    rssi = getattr(adv_data, "rssi", None)
                    if rssi is None:
                        rssi = getattr(ble_dev, "rssi", None)
                    if rssi is not None and int(rssi) > -100:
                        self._ingest_proxy_observation(
                            source, int(rssi), obs_mono, scanner_name
                        )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("BLE scanner table poll error: %s", err)

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

        self._ingest_proxy_observation(source, int(rssi), time.monotonic(), source)

    @callback
    def _ingest_proxy_observation(
        self, source: str, rssi: int, obs_time: float, scanner_name: str = ""
    ) -> None:
        """Ingest a (scanner_source, rssi) observation and evaluate room transitions."""
        now = time.monotonic()
        just_woke_from_standby = (
            self.last_packet_monotonic > 0.0
            and (now - self.last_packet_monotonic) >= WAKE_GAP_SECONDS
        )
        self.last_packet_monotonic = now
        self.packets_seen += 1

        if not self._target_mac_ints and self.packets_seen <= 3:
            self._target_mac_ints = _discover_target_device_macs(
                self.hass, self._raw_slug
            )

        if self._scanner_area_cache.get(source) is None:
            resolved_area = _resolve_scanner_area_id(self.hass, source)
            self._scanner_area_cache[source] = resolved_area

        area_id = self._scanner_area_cache.get(source)
        if not area_id:
            self._unmapped_rssi[source] = (int(rssi), obs_time)
            return

        self._unmapped_rssi.pop(source, None)

        if just_woke_from_standby:
            self._area_rssi.clear()
            self._area_raw_rssi.clear()
            self.current_area_id = None

        raw_f = float(rssi)
        prev_raw = self._area_raw_rssi.get(area_id)
        if prev_raw is None or (now - prev_raw[1]) > STALE_PROXY_SECONDS:
            raw_ema = raw_f
        else:
            raw_ema = (EMA_ALPHA * raw_f) + ((1.0 - EMA_ALPHA) * prev_raw[0])
        self._area_raw_rssi[area_id] = (raw_ema, obs_time, scanner_name or source)

        offset_db = float(self._room_offsets.get(area_id, 0.0))
        eff_ema = raw_ema + offset_db
        self._area_rssi[area_id] = (eff_ema, obs_time)

        if (now - obs_time) <= STALE_PROXY_SECONDS:
            self._evaluate_best_room(now, source)

    @callback
    def _evaluate_best_room(self, now: float, latest_source: str = "") -> None:
        """Evaluate fresh effective RSSI scores across all rooms and trigger room switch if needed."""
        fresh_areas = {
            k: (val, ts)
            for k, (val, ts) in self._area_rssi.items()
            if (now - ts) <= STALE_PROXY_SECONDS
        }
        if not fresh_areas:
            return

        best_area, (best_ema, _) = max(
            fresh_areas.items(), key=lambda item: item[1][0]
        )

        if self.current_area_id is None:
            if best_ema >= -82.0 or len(fresh_areas) >= 2:
                self.current_area_id = best_area
                if latest_source:
                    self.closest_scanner = latest_source
                self._last_switch_monotonic = now
                self._on_area_detected(best_area, self.closest_scanner)
            return

        if best_area == self.current_area_id:
            if latest_source:
                self.closest_scanner = latest_source
            return

        cur_entry = fresh_areas.get(self.current_area_id)
        cur_ema = cur_entry[0] if cur_entry is not None else -100.0
        delta_db = best_ema - cur_ema

        if delta_db >= FAST_OVERRIDE_DB:
            self.current_area_id = best_area
            if latest_source:
                self.closest_scanner = latest_source
            self._last_switch_monotonic = now
            self._on_area_detected(best_area, self.closest_scanner)
            return

        if (now - self._last_switch_monotonic) < MIN_HOLD_SECONDS:
            return

        if delta_db >= HYSTERESIS_DB:
            self.current_area_id = best_area
            if latest_source:
                self.closest_scanner = latest_source
            self._last_switch_monotonic = now
            self._on_area_detected(best_area, self.closest_scanner)

class LatterBleFabric:
    """Domain-level singleton Bluetooth scanner fabric shared across all Latter & generic BLE trackers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the shared BLE scanner fabric."""
        self.hass = hass
        self._trackers: list[LatterNativeBleTracker] = []
        self._unsub_ble: Callable[[], None] | None = None
        self._unsub_poll: Callable[[], None] | None = None

    @callback
    def register_tracker(self, tracker: LatterNativeBleTracker) -> None:
        """Register a BLE tracker and start the shared scanner loop if needed."""
        if tracker not in self._trackers:
            self._trackers.append(tracker)
        if len(self._trackers) == 1 and self._unsub_poll is None:
            self._async_start_fabric()
        else:
            tracker._async_poll_scanner_tables(datetime.now())

    @callback
    def unregister_tracker(self, tracker: LatterNativeBleTracker) -> None:
        """Unregister a BLE tracker and stop the shared scanner loop when empty."""
        if tracker in self._trackers:
            self._trackers.remove(tracker)
        if not self._trackers:
            self._async_stop_fabric()

    @callback
    def _async_start_fabric(self) -> None:
        """Start the single shared Bluetooth advertisement callback and 2s scanner poll timer."""
        try:
            from homeassistant.components import bluetooth

            self._unsub_ble = bluetooth.async_register_callback(
                self.hass,
                self._async_on_shared_ble_advertisement,
                {},
                bluetooth.BluetoothScanningMode.ACTIVE,
            )
            self._unsub_poll = async_track_time_interval(
                self.hass,
                self._async_poll_all_scanners_once,
                timedelta(seconds=SCANNER_POLL_INTERVAL_SECONDS),
            )
            self._async_poll_all_scanners_once(datetime.now())
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Shared BLE Fabric startup skipped: %s", err)

    @callback
    def _async_stop_fabric(self) -> None:
        """Stop the shared Bluetooth callback and timer."""
        if self._unsub_ble is not None:
            self._unsub_ble()
            self._unsub_ble = None
        if self._unsub_poll is not None:
            self._unsub_poll()
            self._unsub_poll = None

    @callback
    def _async_on_shared_ble_advertisement(
        self, service_info: object, change: object
    ) -> None:
        """Fan out incoming BLE advertisements to all registered trackers."""
        for tracker in list(self._trackers):
            tracker._async_on_ble_advertisement(service_info, change)

    @callback
    def _async_poll_all_scanners_once(self, now_dt: datetime) -> None:
        """Scan all HA Bluetooth proxy tables in a single pass for all registered trackers."""
        if not self._trackers:
            return
        for tracker in list(self._trackers):
            if not tracker._target_mac_ints:
                tracker._target_mac_ints = _discover_target_device_macs(
                    self.hass, tracker._raw_slug
                )
        try:
            from homeassistant.components import bluetooth

            now_mono = time.monotonic()
            scanners = bluetooth.async_current_scanners(self.hass)
            for scanner in scanners:
                source = str(getattr(scanner, "source", "") or "")
                scanner_name = str(getattr(scanner, "name", "") or source)
                if not source:
                    continue
                timestamps: dict[str, float] = (
                    getattr(scanner, "_previous_seen_timestamps", {})
                    or getattr(scanner, "timestamps", {})
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
                    local_name = str(
                        getattr(adv_data, "local_name", "")
                        or getattr(ble_dev, "name", "")
                        or ""
                    )
                    rssi = getattr(adv_data, "rssi", None)
                    if rssi is None:
                        rssi = getattr(ble_dev, "rssi", None)
                    if rssi is None or int(rssi) <= -100:
                        continue
                    addr_str = str(addr)
                    for tracker in list(self._trackers):
                        if tracker._matches_raw_adv(addr_str, local_name, mfg_data):
                            tracker._matched_ble_addresses.add(addr_str)
                            tracker._ingest_proxy_observation(
                                source, int(rssi), obs_mono, scanner_name
                            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Shared BLE Fabric scanner poll error: %s", err)


def get_ble_fabric(hass: HomeAssistant) -> LatterBleFabric:
    """Return or initialize the singleton LatterBleFabric instance."""
    domain_data = hass.data.setdefault("latter", {})
    if "ble_fabric" not in domain_data:
        domain_data["ble_fabric"] = LatterBleFabric(hass)
    return domain_data["ble_fabric"]
