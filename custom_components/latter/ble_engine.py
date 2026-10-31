"""Native Zero-Config ESPHome BLE Proxy Area Presence Engine for Latter."""

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

from .const import normalize_device_slug

_LOGGER = logging.getLogger(__name__)

APPLE_COMPANY_ID = 0x004C
IBEACON_PREFIX = b"\x02\x15"
EMA_ALPHA = 0.50
HYSTERESIS_DB = 5.0
FAST_OVERRIDE_DB = 8.0
CROSS_FLOOR_ATTENUATION_DB = 6.0
STALE_PROXY_SECONDS = 12.0
SILENCE_DECAY_DB_PER_S = 1.5
SURVEY_RETENTION_SECONDS = 180.0
WAKE_GAP_SECONDS = 8.0
MIN_HOLD_SECONDS = 4.0
SCANNER_POLL_INTERVAL_SECONDS = 2.0
AWAY_TIMEOUT_SECONDS = 180.0


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
    """Tracks a mobile ESPHome BLE iBeacon across ESPHome BLE Proxies to auto-detect the area."""

    def __init__(
        self,
        hass: HomeAssistant,
        beacon_uuid: str,
        device_slug: str,
        on_area_detected: Callable[[str, str], None],
        area_offsets: dict[str, float] | None = None,
        target_address: str = "",
    ) -> None:
        """Initialize the native BLE proxy area tracker."""
        self.hass = hass
        self._target_uuid_hex = _normalize_uuid_hex(beacon_uuid)
        self._target_address = str(target_address or "").strip()
        self._device_slug = device_slug.lower().replace("_", "-")
        self._raw_slug = device_slug
        self._on_area_detected = on_area_detected
        self._area_offsets: dict[str, float] = {
            str(k): float(v) for k, v in (area_offsets or {}).items()
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
        self._last_adv_ts_by_scanner: dict[str, float] = {}
        self._target_mac_ints: set[int] = set()
        self._last_mac_discovery_mono: float = 0.0
        self._matched_ble_addresses: dict[str, float] = {}
        self.current_area_id: str | None = None
        self.closest_scanner: str = ""
        self.packets_seen: int = 0
        self.last_packet_monotonic: float = 0.0
        self._last_switch_monotonic: float = 0.0
        self.is_away: bool = False
        self.winning_rssi: int | None = None
        self.winning_distance_m: float | None = None
        self.winning_distance_ft: float | None = None
        self._seed_explicit_target_address()

    @callback
    def _record_matched_ble_address(self, addr: str) -> None:
        """Record a matched BLE address with a monotonic timestamp, bounding cache size to 64 entries."""
        if not addr:
            return
        self._matched_ble_addresses[addr] = time.monotonic()
        if len(self._matched_ble_addresses) > 64:
            oldest = min(self._matched_ble_addresses, key=self._matched_ble_addresses.get)
            self._matched_ble_addresses.pop(oldest, None)

    @callback
    def _seed_explicit_target_address(self) -> None:
        """Seed MAC, iBeacon UUID, or dynamic private_ble_device address from _target_address."""
        t_addr = self._target_address
        if not t_addr:
            return
        # 1. Static MAC address (AA:BB:CC:DD:EE:FF)
        m_int = _mac_to_int(t_addr)
        if m_int is not None:
            self._target_mac_ints.add(m_int)
            self._record_matched_ble_address(_int_to_mac(m_int))
            return
        # 2. Home Assistant entity (private_ble_device or ibeacon tracker)
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
        # 3. Raw 32-hex iBeacon UUID
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
        self._seed_explicit_target_address()
        if (
            not self.is_away
            and self.last_packet_monotonic > 0.0
            and (now_mono - self.last_packet_monotonic) >= AWAY_TIMEOUT_SECONDS
        ):
            self.is_away = True
            self.current_area_id = None
            self.winning_rssi = None
            self.winning_distance_m = None
            self.winning_distance_ft = None
            self._on_area_detected("away", "")
            get_ble_fabric(self.hass).notify_occupancy_listeners()

    def _resolve_hardware_meta(self) -> str:
        """Return combined lowercase hardware model, sw_version, and slug metadata from HA Device Registry."""
        dev_reg = dr.async_get(self.hass)
        slug_norm = self._raw_slug.lower().replace("-", "_")
        for dev in _iter_devices(dev_reg):
            d_name = str(dev.name_by_user or dev.name or "").strip().lower().replace("-", "_").replace(" ", "_")
            if slug_norm and slug_norm in d_name:
                return f"{dev.model or ''} {dev.sw_version or ''} {d_name} {slug_norm}".lower()
        return slug_norm

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
        """Clear stale RSSI history only if no packet was received in the last 6 seconds."""
        now = time.monotonic()
        if self.last_packet_monotonic > 0.0 and (now - self.last_packet_monotonic) < 6.0:
            return
        self._area_rssi.clear()
        self._unmapped_rssi.clear()
        self._scanner_area_cache.clear()
        self._last_adv_ts_by_scanner.clear()
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

    def get_area_calibration_telemetry(self) -> list[dict[str, Any]]:
        """Return rich per-area BLE site survey telemetry (all proxy areas, raw dBm, offset dB, effective dBm, age, winner)."""
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

        # 3. Apple iBeacon UUID + Minor ID match (supports ESP32-P4 + ESP32-C6 where the C6 BLE MAC
        #    differs from the P4 host MAC in HA Device Registry)
        apple_bytes = mfg_data.get(APPLE_COMPANY_ID)
        if apple_bytes and len(apple_bytes) >= 18:
            uuid_matched = False
            minor_val: int | None = None
            if len(apple_bytes) >= 20 and apple_bytes[:2] == IBEACON_PREFIX:
                uuid_hex = apple_bytes[2:18].hex().lower()
                uuid_matched = uuid_hex == self._target_uuid_hex
                if len(apple_bytes) >= 22:
                    minor_val = (apple_bytes[20] << 8) | apple_bytes[21]
            elif self._target_uuid_hex in apple_bytes.hex().lower():
                uuid_matched = True
            if uuid_matched:
                hw_meta = self._resolve_hardware_meta()
                expected_minor = (
                    4 if any(k in hw_meta for k in ("p4_35", "p4-35", "320x480", "remote_assistant"))
                    else 3 if any(k in hw_meta for k in ("216", "480x480", "mobile_assistant"))
                    else 2 if any(k in hw_meta for k in ("206", "410x502", "s3_206"))
                    else 5 if any(k in hw_meta for k in ("p4_4b", "p4-4b", "4b", "720x720", "desk_assistant"))
                    else 1 if any(k in hw_meta for k in ("175", "466x466", "s3_175c"))
                    else None
                )
                if minor_val is not None and expected_minor is not None:
                    if minor_val == expected_minor and minor_val >= 2:
                        return True
                    if minor_val >= 2 and minor_val != expected_minor:
                        return False
                if any(k in hw_meta for k in ("p4", "esp32p4", "320x480", "720x720", "remote_assistant", "desk_assistant")):
                    # On ESP32-P4 + ESP32-C6 boards, the C6 co-processor has its own factory BLE MAC
                    return True
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
            self._record_matched_ble_address(adv_address)
        return matched

    @callback
    def _async_poll_scanner_tables(self, _now: datetime) -> None:
        """Poll each ESPHome BLE Proxy's live advertisement table to bypass habluetooth static-iBeacon deduplication."""
        now_mono = time.monotonic()
        if not self._target_mac_ints and (now_mono - self._last_mac_discovery_mono) >= 30.0:
            self._last_mac_discovery_mono = now_mono
            self._target_mac_ints = _discover_target_device_macs(
                self.hass, self._raw_slug
            )

        try:
            from homeassistant.components import bluetooth

            scanners = bluetooth.async_current_scanners(self.hass)
            for scanner in scanners:
                source = str(getattr(scanner, "source", "") or "")
                scanner_name = str(getattr(scanner, "name", "") or source)
                if not source:
                    continue

                timestamps: dict[str, float] = (
                    getattr(scanner, "discovered_device_timestamps", None)
                    or getattr(scanner, "_previous_seen_timestamps", None)
                    or getattr(scanner, "timestamps", None)
                    or {}
                )

                dev_adv_map: dict[str, tuple[Any, Any]] = getattr(
                    scanner, "discovered_devices_and_advertisement_data", {}
                ) or {}

                for addr, pair in dev_adv_map.items():
                    if not isinstance(pair, tuple) or len(pair) != 2:
                        continue
                    ble_dev, adv_data = pair
                    last_ts = timestamps.get(addr)
                    if last_ts is None:
                        svc_info = bluetooth.async_last_service_info(
                            self.hass, str(addr), connectable=False
                        )
                        if svc_info is not None:
                            last_ts = getattr(svc_info, "time", None)
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

                    self._record_matched_ble_address(str(addr))
                    rssi = getattr(adv_data, "rssi", None)
                    if rssi is None:
                        rssi = getattr(ble_dev, "rssi", None)
                    if rssi is not None and int(rssi) > -100:
                        self._ingest_proxy_observation(
                            source,
                            int(rssi),
                            obs_mono,
                            scanner_name,
                            from_poll=last_ts is not None,
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
        if from_poll and prev_adv_ts is not None and obs_time <= (prev_adv_ts + 1e-4):
            self._evaluate_best_area(now, "")
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
        if prev_raw is None or (obs_time - prev_raw[1]) > STALE_PROXY_SECONDS:
            raw_ema = raw_f
        else:
            raw_ema = (EMA_ALPHA * raw_f) + ((1.0 - EMA_ALPHA) * prev_raw[0])
        self._area_raw_rssi[area_id] = (raw_ema, obs_time, scanner_name or source)

        offset_db = float(self._area_offsets.get(area_id, 0.0))
        eff_ema = raw_ema + offset_db
        self._area_rssi[area_id] = (eff_ema, obs_time)

        if (now - obs_time) <= STALE_PROXY_SECONDS:
            self._evaluate_best_area(now, source)

    @callback
    def _evaluate_best_area(self, now: float, latest_source: str = "") -> None:
        """Evaluate fresh effective RSSI scores across all areas (with silence decay and multi-story floor attenuation)."""
        raw_fresh_areas = {
            k: (val, ts)
            for k, (val, ts) in self._area_rssi.items()
            if (now - ts) <= STALE_PROXY_SECONDS
        }
        if not raw_fresh_areas:
            return

        area_reg = ar.async_get(self.hass)
        cur_floor_id: str | None = None
        if self.current_area_id:
            cur_area_entry = area_reg.async_get_area(self.current_area_id)
            if cur_area_entry:
                cur_floor_id = getattr(cur_area_entry, "floor_id", None)

        fresh_areas: dict[str, tuple[float, float]] = {}
        for k, (val, ts) in raw_fresh_areas.items():
            age_s = max(0.0, now - ts)
            silence_penalty = SILENCE_DECAY_DB_PER_S * max(0.0, age_s - 2.0)
            adj_val = val - silence_penalty
            if cur_floor_id and k != self.current_area_id:
                cand_entry = area_reg.async_get_area(k)
                cand_floor_id = getattr(cand_entry, "floor_id", None) if cand_entry else None
                if cand_floor_id and cand_floor_id != cur_floor_id:
                    adj_val -= CROSS_FLOOR_ATTENUATION_DB
            fresh_areas[k] = (adj_val, ts)

        best_area, (best_ema, best_ts) = max(
            fresh_areas.items(), key=lambda item: item[1][0]
        )
        best_age_s = max(0.0, now - best_ts)
        if best_ema < -88.0:
            return
        self.is_away = False

        def _update_winner_metrics(win_area: str) -> None:
            eff_entry = raw_fresh_areas.get(win_area)
            if eff_entry is not None:
                eff_dbm = eff_entry[0]
                self.winning_rssi = int(round(eff_dbm))
                d_m = round(max(0.2, min(50.0, 10.0 ** ((-59.0 - eff_dbm) / (10.0 * 2.2)))), 1)
                self.winning_distance_m = d_m
                self.winning_distance_ft = round(d_m * 3.28084, 1)

        if self.current_area_id is None:
            self.current_area_id = best_area
            _update_winner_metrics(best_area)
            if latest_source:
                self.closest_scanner = latest_source
            self._last_switch_monotonic = now
            _LOGGER.debug(
                "BLE initial area lock (%s): area=%s best_ema=%.1fdBm age=%.1fs",
                self._raw_slug,
                best_area,
                best_ema,
                best_age_s,
            )
            self._on_area_detected(best_area, self.closest_scanner)
            get_ble_fabric(self.hass).notify_occupancy_listeners()
            return

        if best_area == self.current_area_id:
            _update_winner_metrics(best_area)
            if latest_source:
                self.closest_scanner = latest_source
            return

        cur_entry = fresh_areas.get(self.current_area_id)
        cur_ema = cur_entry[0] if cur_entry is not None else -100.0
        delta_db = best_ema - cur_ema
        _LOGGER.debug(
            "BLE area candidate (%s): area=%s best_ema=%.1fdBm runner_up_ema=%.1fdBm delta=%.1fdB age=%.1fs",
            self._raw_slug,
            best_area,
            best_ema,
            cur_ema,
            delta_db,
            best_age_s,
        )

        if delta_db >= FAST_OVERRIDE_DB:
            self.current_area_id = best_area
            _update_winner_metrics(best_area)
            if latest_source:
                self.closest_scanner = latest_source
            self._last_switch_monotonic = now
            self._on_area_detected(best_area, self.closest_scanner)
            get_ble_fabric(self.hass).notify_occupancy_listeners()
            return

        if (now - self._last_switch_monotonic) < MIN_HOLD_SECONDS:
            return

        if delta_db >= HYSTERESIS_DB:
            self.current_area_id = best_area
            _update_winner_metrics(best_area)
            if latest_source:
                self.closest_scanner = latest_source
            self._last_switch_monotonic = now
            self._on_area_detected(best_area, self.closest_scanner)
            get_ble_fabric(self.hass).notify_occupancy_listeners()

class LatterBleFabric:
    """Domain-level singleton Bluetooth scanner fabric shared across all Latter & generic BLE trackers."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the shared BLE scanner fabric."""
        self.hass = hass
        self._trackers: list[LatterNativeBleTracker] = []
        self._occupancy_listeners: list[Callable[[], None]] = []
        self._unsub_ble: Callable[[], None] | None = None
        self._unsub_poll: Callable[[], None] | None = None
        self._unsub_sensor_events: Callable[[], None] | None = None

    @callback
    def register_occupancy_listener(
        self, listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Register a listener for real-time per-area BLE & sensor-fused occupancy changes."""
        self._occupancy_listeners.append(listener)
        if self._unsub_sensor_events is None:
            self._unsub_sensor_events = self.hass.bus.async_listen(
                "state_changed", self._async_on_ha_state_changed
            )

        @callback
        def _unsub() -> None:
            if listener in self._occupancy_listeners:
                self._occupancy_listeners.remove(listener)
            if not self._occupancy_listeners and self._unsub_sensor_events is not None:
                self._unsub_sensor_events()
                self._unsub_sensor_events = None

        return _unsub

    @callback
    def _async_on_ha_state_changed(self, event: Any) -> None:
        """Trigger occupancy re-evaluation when a physical area binary_sensor changes state."""
        data = getattr(event, "data", {}) or {}
        ent_id = str(data.get("entity_id") or "")
        if not ent_id.startswith("binary_sensor.") or "ble_occupancy" in ent_id:
            return
        new_st = data.get("new_state")
        old_st = data.get("old_state")
        if new_st is None or (old_st is not None and new_st.state == old_st.state):
            return
        dclass = str(new_st.attributes.get("device_class") or "").lower()
        if dclass in ("occupancy", "presence", "motion", "moving", "door", "opening"):
            self.notify_occupancy_listeners()

    @callback
    def notify_occupancy_listeners(self) -> None:
        """Notify all registered per-area BLE occupancy and occupant sensors."""
        for listener in list(self._occupancy_listeners):
            listener()

    @callback
    def _discover_area_fusion_sensors(
        self, area_id: str, configured_sensors: list[str] | None = None
    ) -> tuple[list[str], list[str], list[str], list[str], list[dict[str, str]]]:
        """Return (occ_on, occ_off, motion_on, door_closed, available_sensors) for a Home Assistant Area."""
        ent_reg = er.async_get(self.hass)
        dev_reg = dr.async_get(self.hass)
        explicit_set = {
            str(s).strip()
            for s in (configured_sensors or [])
            if str(s or "").strip().startswith("binary_sensor.")
        }

        occ_on: list[str] = []
        occ_off: list[str] = []
        motion_on: list[str] = []
        door_closed: list[str] = []
        available: list[dict[str, str]] = []
        seen_eids: set[str] = set()

        for entry in _iter_entities(ent_reg):
            if entry.disabled_by or entry.domain != "binary_sensor":
                continue
            eid = entry.entity_id
            if "ble_occupancy" in eid or (
                entry.unique_id and str(entry.unique_id).startswith("latter_area_ble_occupancy_")
            ):
                continue

            ent_area = entry.area_id
            if not ent_area and entry.device_id:
                dev_obj = dev_reg.async_get(entry.device_id)
                if dev_obj is not None:
                    ent_area = dev_obj.area_id

            if ent_area != area_id and eid not in explicit_set:
                continue

            st = self.hass.states.get(eid)
            dclass = str(
                (st.attributes.get("device_class") if st else "")
                or entry.device_class
                or entry.original_device_class
                or ""
            ).lower()
            if dclass not in ("occupancy", "presence", "motion", "moving", "door", "opening") and eid not in explicit_set:
                continue

            seen_eids.add(eid)
            state_str = str(st.state if st else "unknown").lower()
            friendly = (
                str(st.attributes.get("friendly_name") if st else "")
                or entry.name
                or entry.original_name
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

            if dclass in ("occupancy", "presence") or (eid in explicit_set and dclass not in ("motion", "moving", "door", "opening")):
                if state_str == "on":
                    occ_on.append(eid)
                elif state_str == "off":
                    occ_off.append(eid)
            elif dclass in ("motion", "moving"):
                if state_str == "on":
                    motion_on.append(eid)
            elif dclass in ("door", "opening"):
                if state_str == "off":
                    door_closed.append(eid)

        return occ_on, occ_off, motion_on, door_closed, available

    @callback
    def get_area_occupancy(self, area_id: str) -> dict[str, Any]:
        """Return deterministic & Bayesian fused BLE + physical sensor occupancy telemetry for an Area."""
        area_reg = ar.async_get(self.hass)
        area_obj = area_reg.async_get_area(area_id)
        floor_id = getattr(area_obj, "floor_id", None) if area_obj else None

        domain_data = self.hass.data.get("latter", {})
        global_cfg = domain_data.get("global_config", {}) if isinstance(domain_data, dict) else {}
        fusion_map = global_cfg.get("area_fusion_config", {}) if isinstance(global_cfg, dict) else {}
        area_cfg = fusion_map.get(area_id, {}) if isinstance(fusion_map, dict) else {}
        if not isinstance(area_cfg, dict):
            area_cfg = {}

        fusion_mode = str(area_cfg.get("mode") or "auto_bayes").strip().lower()
        if fusion_mode not in ("auto_bayes", "any_or", "ble_only", "ble_and_sensor"):
            fusion_mode = "auto_bayes"
        threshold_pct = max(20, min(95, int(area_cfg.get("threshold_pct") or 50)))
        configured_sensors = area_cfg.get("sensors") if isinstance(area_cfg.get("sensors"), list) else None

        # Map device_slug -> coordinator for person & friendly-name resolution
        coord_by_slug: dict[str, Any] = {}
        if isinstance(domain_data, dict):
            for val in domain_data.values():
                c_slug = getattr(val, "device_slug", None)
                if isinstance(c_slug, str) and c_slug:
                    coord_by_slug[c_slug] = val

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
                p_ent = str(getattr(coord, "assigned_person", "") or "").strip() if coord else ""
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

        occ_on, occ_off, motion_on, door_closed, available_sensors = (
            self._discover_area_fusion_sensors(area_id, configured_sensors)
        )
        active_sensors = occ_on + motion_on
        ble_present = len(occupants) > 0
        sensor_present = len(active_sensors) > 0

        # Bayesian Posterior Occupancy Score (0..100%)
        prob = 0.0
        if ble_present:
            if best_rssi is not None and best_rssi >= -68:
                prob += 0.85
            elif best_rssi is not None and best_rssi >= -80:
                prob += 0.70
            else:
                prob += 0.54

        if occ_on:
            prob = max(prob, 0.78) + (0.18 if ble_present else 0.08)
        elif occ_off and not motion_on and ble_present and (best_rssi is not None and best_rssi < -78):
            # Dampen weak cross-wall BLE bleed-through when in-room mmWave explicitly reports clear
            prob = max(0.0, prob - 0.18)

        if motion_on:
            prob = max(prob, 0.68) + (0.15 if (ble_present or occ_on) else 0.05)

        if door_closed and (ble_present or sensor_present):
            prob += 0.08

        confidence_pct = int(round(max(0.0, min(1.0, prob)) * 100))

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
            # auto_bayes (default)
            is_occupied = confidence_pct >= threshold_pct

        return {
            "is_occupied": is_occupied,
            "ble_occupied": ble_present,
            "sensor_occupied": sensor_present,
            "fusion_mode": fusion_mode,
            "confidence_pct": confidence_pct,
            "tracker_count": len(occupants),
            "occupied_by": occupants,
            "occupant_names": occupant_names,
            "persons": persons,
            "active_sensors": active_sensors,
            "available_sensors": available_sensors,
            "closest_device": closest_dev,
            "winning_rssi": best_rssi,
            "closest_distance_m": closest_dist_m,
            "closest_distance_ft": closest_dist_ft,
            "floor_id": floor_id,
        }

    @callback
    def register_tracker(self, tracker: LatterNativeBleTracker) -> None:
        """Register a BLE tracker and start the shared scanner loop if needed."""
        if tracker not in self._trackers:
            self._trackers.append(tracker)
        if len(self._trackers) == 1 and self._unsub_poll is None:
            self._async_start_fabric()
        else:
            tracker._async_poll_scanner_tables(datetime.now())
        self.notify_occupancy_listeners()

    @callback
    def unregister_tracker(self, tracker: LatterNativeBleTracker) -> None:
        """Unregister a BLE tracker and stop the shared scanner loop when empty."""
        if tracker in self._trackers:
            self._trackers.remove(tracker)
        if not self._trackers:
            self._async_stop_fabric()
        self.notify_occupancy_listeners()

    @callback
    def _async_start_fabric(self) -> None:
        """Start the single shared passive Bluetooth advertisement callback, esphome.ibeacon_seen listener, and 2s scanner poll timer."""
        try:
            from homeassistant.components import bluetooth

            matcher = bluetooth.BluetoothCallbackMatcher()
            unsub_ibeacon_ble = bluetooth.async_register_callback(
                self.hass,
                self._async_on_shared_ble_advertisement,
                matcher,
                bluetooth.BluetoothScanningMode.PASSIVE,
            )
            unsub_bus = self.hass.bus.async_listen(
                "esphome.ibeacon_seen", self._async_on_esphome_ibeacon_event
            )

            @callback
            def _unsub_combined() -> None:
                unsub_ibeacon_ble()
                unsub_bus()

            self._unsub_ble = _unsub_combined
            self._unsub_poll = async_track_time_interval(
                self.hass,
                self._async_poll_all_scanners_once,
                timedelta(seconds=SCANNER_POLL_INTERVAL_SECONDS),
            )
            self._async_poll_all_scanners_once(datetime.now())
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Shared BLE Fabric startup skipped: %s", err)

    @callback
    def _async_on_esphome_ibeacon_event(self, event: Any) -> None:
        """Ingest custom esphome.ibeacon_seen bus events emitted by ESPHome BLE proxies."""
        data = getattr(event, "data", {}) or {}
        source = str(data.get("source") or data.get("scanner") or "").strip()
        uuid_raw = _normalize_uuid_hex(str(data.get("uuid") or ""))
        rssi = data.get("rssi")
        if not source or rssi is None or int(rssi) <= -100:
            return
        now_mono = time.monotonic()
        for tracker in list(self._trackers):
            if uuid_raw and uuid_raw == tracker._target_uuid_hex:
                tracker._ingest_proxy_observation(
                    source, int(rssi), now_mono, source
                )

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
        now_mono_check = time.monotonic()
        for tracker in list(self._trackers):
            tracker.check_away_timeout(now_mono_check)
            if (
                not tracker._target_mac_ints
                and (now_mono_check - tracker._last_mac_discovery_mono) >= 30.0
            ):
                tracker._last_mac_discovery_mono = now_mono_check
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
                    getattr(scanner, "discovered_device_timestamps", None)
                    or getattr(scanner, "_previous_seen_timestamps", None)
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
                    if last_ts is None:
                        svc_info = bluetooth.async_last_service_info(
                            self.hass, str(addr), connectable=False
                        )
                        if svc_info is not None:
                            last_ts = getattr(svc_info, "time", None)
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
                            tracker._record_matched_ble_address(addr_str)
                            tracker._ingest_proxy_observation(
                                source,
                                int(rssi),
                                obs_mono,
                                scanner_name,
                                from_poll=last_ts is not None,
                            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Shared BLE Fabric scanner poll error: %s", err)


def get_ble_fabric(hass: HomeAssistant) -> LatterBleFabric:
    """Return or initialize the singleton LatterBleFabric instance."""
    domain_data = hass.data.setdefault("latter", {})
    if "ble_fabric" not in domain_data:
        domain_data["ble_fabric"] = LatterBleFabric(hass)
    return domain_data["ble_fabric"]


def get_all_areas_presence_summary(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Build live per-area presence, occupant names, confidence score, and fusion status for Latter Studio."""
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
            }
        )

    rows.sort(
        key=lambda r: (
            not r["is_occupied"],
            -int(r["confidence_pct"] or 0),
            r["area_name"].lower(),
        )
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

    # 1. Check private_ble_device & ibeacon entities in Home Assistant
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
            if not cand_slug or cand_slug == "esphome_device" or cand_slug in onboarded_slugs or entry.entity_id.lower() in seen_targets:
                continue
            seen_targets.add(entry.entity_id.lower())
            kind_lbl = "Private BLE (Phone/Watch)" if entry.platform == "private_ble_device" else "iBeacon Tracker"
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

    # 2. Check live Bluetooth scanner tables for named BLE devices / iBeacons (picking strongest proxy per MAC)
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
                if not local_name or local_name.replace(":", "").replace("-", "").upper() == addr_str.replace(":", ""):
                    continue
                cand_slug = normalize_device_slug(local_name)
                if not cand_slug or cand_slug == "esphome_device" or cand_slug in onboarded_slugs:
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
                        "kind": "Named BLE Device",
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
