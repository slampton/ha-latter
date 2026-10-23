"""Native Zero-Config ESPHome BLE Proxy Room Presence Engine for Latter."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

_LOGGER = logging.getLogger(__name__)

APPLE_COMPANY_ID = 0x004C
IBEACON_PREFIX = b"\x02\x15"
EMA_ALPHA = 0.40
HYSTERESIS_DB = 5.0
STALE_PROXY_SECONDS = 25.0
MIN_HOLD_SECONDS = 6.0


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


def _discover_target_device_macs(
    hass: HomeAssistant, device_slug: str
) -> set[int]:
    """Find known Wi-Fi/BLE MAC address integers for the target Pocket Assistant ESPHome device."""
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    slug_norm = device_slug.strip().lower().replace("-", "_")

    target_dev_id: str | None = None
    for entry in ent_reg.entities.values():
        if entry.platform == "esphome" and slug_norm in entry.entity_id:
            if entry.device_id:
                target_dev_id = entry.device_id
                break

    mac_ints: set[int] = set()
    for dev in dev_reg.devices.values():
        dev_name = str(dev.name_by_user or dev.name or "").lower().replace("-", "_").replace(" ", "_")
        if dev.id == target_dev_id or (slug_norm and slug_norm in dev_name):
            for _conn_type, conn_val in dev.connections:
                m_int = _mac_to_int(str(conn_val))
                if m_int is not None:
                    # ESP32 BLE MAC is typically base Wi-Fi MAC +1 or +2
                    for offset in (-2, -1, 0, 1, 2):
                        mac_ints.add(m_int + offset)
            for _domain, ident_val in dev.identifiers:
                m_int = _mac_to_int(str(ident_val))
                if m_int is not None:
                    for offset in (-2, -1, 0, 1, 2):
                        mac_ints.add(m_int + offset)
    return mac_ints


def _resolve_scanner_area_id(
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

    # 1. Query Home Assistant's bluetooth manager for the scanner object (gives scanner.name / details)
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

    # 2. Match in Device Registry by exact MAC, ESP32 Wi-Fi/BLE +/-2 MAC offset, or scanner name
    for device in dev_reg.devices.values():
        if not device.area_id:
            continue
        for _conn_type, conn_val in device.connections:
            c_low = str(conn_val).lower()
            if c_low == src_low:
                return device.area_id
            c_int = _mac_to_int(c_low)
            if src_int is not None and c_int is not None and abs(src_int - c_int) <= 2:
                return device.area_id

        for _domain, ident_val in device.identifiers:
            i_low = str(ident_val).lower()
            if i_low == src_low:
                return device.area_id
            i_int = _mac_to_int(i_low)
            if src_int is not None and i_int is not None and abs(src_int - i_int) <= 2:
                return device.area_id

        for candidate_name in (device.name_by_user, device.name):
            if not candidate_name:
                continue
            d_low = str(candidate_name).strip().lower()
            d_slug = d_low.replace(" ", "-").replace("_", "-")
            for target_n in (src_low, scanner_name):
                if not target_n:
                    continue
                t_slug = target_n.replace(" ", "-").replace("_", "-")
                if d_low == target_n or d_slug == t_slug or (len(d_slug) > 4 and d_slug in t_slug):
                    return device.area_id

    # 3. Check if scanner_name contains an area name directly (e.g. "kitchen-ble-proxy" -> "Kitchen")
    if scanner_name:
        scan_norm = scanner_name.replace("-", " ").replace("_", " ")
        for area in area_reg.async_list_areas():
            a_norm = area.name.lower().replace("-", " ").replace("_", " ").strip()
            if a_norm and a_norm in scan_norm:
                return area.id

    # 4. Check Entity Registry for scanner entities matching source
    for entry in ent_reg.entities.values():
        if src_low in entry.entity_id or (scanner_name and scanner_name.replace("-", "_") in entry.entity_id):
            if entry.area_id:
                return entry.area_id
            if entry.device_id:
                dev = dev_reg.async_get(entry.device_id)
                if dev and dev.area_id:
                    return dev.area_id

    return None


class LatterNativeBleTracker:
    """Tracks a Pocket Assistant BLE iBeacon across ESPHome BLE Proxies to auto-detect the room."""

    def __init__(
        self,
        hass: HomeAssistant,
        beacon_uuid: str,
        device_slug: str,
        on_area_detected: Callable[[str, str], None],
    ) -> None:
        """Initialize the native BLE proxy room tracker."""
        self.hass = hass
        self._target_uuid_hex = _normalize_uuid_hex(beacon_uuid)
        self._device_slug = device_slug.lower().replace("_", "-")
        self._raw_slug = device_slug
        self._on_area_detected = on_area_detected

        self._unsub_ble: Callable[[], None] | None = None
        # area_id -> (ema_rssi, last_seen_monotonic)
        self._area_rssi: dict[str, tuple[float, float]] = {}
        self._scanner_area_cache: dict[str, str | None] = {}
        self._target_mac_ints: set[int] = set()
        self.current_area_id: str | None = None
        self.closest_scanner: str = ""
        self.packets_seen: int = 0
        self._last_switch_monotonic: float = 0.0

    @callback
    def async_start(self) -> None:
        """Subscribe to Home Assistant's internal Bluetooth advertisement stream."""
        self.async_stop()
        self._target_mac_ints = _discover_target_device_macs(
            self.hass, self._raw_slug
        )

        try:
            from homeassistant.components import bluetooth

            # Use empty matcher {} so BOTH connectable and non-connectable iBeacon frames are received!
            self._unsub_ble = bluetooth.async_register_callback(
                self.hass,
                self._async_on_ble_advertisement,
                {},
                bluetooth.BluetoothScanningMode.ACTIVE,
            )
            _LOGGER.info(
                "Latter Native BLE Room Tracker active (UUID=%s, known_macs=%d)",
                self._target_uuid_hex,
                len(self._target_mac_ints),
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug(
                "Home Assistant bluetooth integration not active for native BLE tracking: %s",
                err,
            )

    @callback
    def async_stop(self) -> None:
        """Unsubscribe from Bluetooth advertisements."""
        if self._unsub_ble is not None:
            self._unsub_ble()
            self._unsub_ble = None
        self._area_rssi.clear()
        self._scanner_area_cache.clear()

    def get_live_rssi_summary(self) -> dict[str, int]:
        """Return a snapshot of area_name -> smoothed RSSI (dBm) for diagnostics."""
        area_reg = ar.async_get(self.hass)
        now = time.monotonic()
        out: dict[str, int] = {}
        for area_id, (ema, ts) in self._area_rssi.items():
            if (now - ts) <= STALE_PROXY_SECONDS:
                area_obj = area_reg.async_get_area(area_id)
                label = area_obj.name if area_obj else area_id
                out[label] = int(round(ema))
        return out

    def _matches_target_device(self, service_info: object) -> bool:
        """Return True if advertisement matches Pocket Assistant iBeacon UUID, MAC, or local name."""
        # 1. Check iBeacon Manufacturer Data (0x004C)
        mfg_data: dict[int, bytes] = getattr(
            service_info, "manufacturer_data", {}
        )
        apple_bytes = mfg_data.get(APPLE_COMPANY_ID)
        if apple_bytes and len(apple_bytes) >= 18:
            # Standard iBeacon prefix is 0x02 0x15 followed by 16-byte UUID
            if len(apple_bytes) >= 20 and apple_bytes[:2] == IBEACON_PREFIX:
                uuid_hex = apple_bytes[2:18].hex().lower()
                if uuid_hex == self._target_uuid_hex:
                    return True
            elif self._target_uuid_hex in apple_bytes.hex().lower():
                return True

        # 2. Check BLE advertiser MAC against known Pocket Assistant ESP32 MAC (+/-2)
        adv_address = str(getattr(service_info, "address", "") or "")
        if adv_address and self._target_mac_ints:
            adv_int = _mac_to_int(adv_address)
            if adv_int is not None and adv_int in self._target_mac_ints:
                return True

        # 3. Check BLE local name
        adv_name = str(getattr(service_info, "name", "") or "").lower().replace("_", "-")
        if adv_name and self._device_slug in adv_name:
            return True

        return False

    @callback
    def _async_on_ble_advertisement(
        self, service_info: object, _change: object
    ) -> None:
        """Process incoming BLE advertisement from an ESPHome BLE proxy."""
        if not self._matches_target_device(service_info):
            return

        rssi = getattr(service_info, "rssi", None)
        source = str(getattr(service_info, "source", "") or "")
        if rssi is None or not source or int(rssi) <= -100:
            return

        self.packets_seen += 1

        # Refresh known MACs once if empty on startup
        if not self._target_mac_ints and self.packets_seen == 1:
            self._target_mac_ints = _discover_target_device_macs(
                self.hass, self._raw_slug
            )

        if source not in self._scanner_area_cache:
            resolved_area = _resolve_scanner_area_id(self.hass, source)
            self._scanner_area_cache[source] = resolved_area
            _LOGGER.debug(
                "BLE Proxy source '%s' resolved to area_id='%s' (RSSI=%s)",
                source,
                resolved_area,
                rssi,
            )

        area_id = self._scanner_area_cache[source]
        if not area_id:
            return

        now = time.monotonic()
        rssi_f = float(rssi)
        prev = self._area_rssi.get(area_id)
        if prev is None or (now - prev[1]) > STALE_PROXY_SECONDS:
            ema = rssi_f
        else:
            ema = (EMA_ALPHA * rssi_f) + ((1.0 - EMA_ALPHA) * prev[0])
        self._area_rssi[area_id] = (ema, now)

        stale_keys = [
            k
            for k, (_val, ts) in self._area_rssi.items()
            if (now - ts) > STALE_PROXY_SECONDS
        ]
        for k in stale_keys:
            self._area_rssi.pop(k, None)

        if not self._area_rssi:
            return

        best_area, (best_ema, _) = max(
            self._area_rssi.items(), key=lambda item: item[1][0]
        )

        if self.current_area_id is None:
            self.current_area_id = best_area
            self.closest_scanner = source
            self._last_switch_monotonic = now
            self._on_area_detected(best_area, source)
            return

        if best_area == self.current_area_id:
            self.closest_scanner = source
            return

        if (now - self._last_switch_monotonic) < MIN_HOLD_SECONDS:
            return

        cur_entry = self._area_rssi.get(self.current_area_id)
        cur_ema = cur_entry[0] if cur_entry is not None else -100.0
        if (best_ema - cur_ema) >= HYSTERESIS_DB:
            self.current_area_id = best_area
            self.closest_scanner = source
            self._last_switch_monotonic = now
            self._on_area_detected(best_area, source)