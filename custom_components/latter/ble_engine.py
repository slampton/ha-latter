"""Native Zero-Config ESPHome BLE Proxy Room Presence Engine for Latter."""

from __future__ import annotations

import logging
import time
from typing import Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er

_LOGGER = logging.getLogger(__name__)

 APPLE_COMPANY_ID = 0x004C
IBEACON_PREFIX = b"\x02\x15"
EMA_ALPHA = 0.35
HYSTERESIS_DB = 6.0
STALE_PROXY_SECONDS = 25.0
MIN_HOLD_SECONDS = 8.0


def _normalize_uuid_hex(uuid_str: str) -> str:
    """Normalize a UUID string to 32 lowercase hex chars without dashes."""
    return uuid_str.strip().lower().replace("-", "")


def _resolve_scanner_area_id(
    hass: HomeAssistant, scanner_source: str
) -> str | None:
    """Resolve a Bluetooth scanner source (MAC or name) to its Home Assistant area_id."""
    if not scanner_source:
        return None

    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    src_low = scanner_source.strip().lower()
    src_clean = src_low.replace(":", "").replace("-", "").replace("_", "")

    # 1. Check Device Registry connections (MAC addresses) and identifiers
    for device in dev_reg.devices.values():
        if not device.area_id:
            continue
        for _conn_type, conn_val in device.connections:
            c_low = str(conn_val).lower()
            c_clean = c_low.replace(":", "").replace("-", "")
            if c_low == src_low or (c_clean and c_clean == src_clean):
                return device.area_id
        for _domain, ident_val in device.identifiers:
            i_low = str(ident_val).lower()
            i_clean = i_low.replace(":", "").replace("-", "")
            if i_low == src_low or (i_clean and i_clean == src_clean):
                return device.area_id
        dev_name = str(device.name_by_user or device.name or "").lower()
        if dev_name and (dev_name == src_low or dev_name.replace(" ", "_") == src_low):
            return device.area_id

    # 2. Check Entity Registry for scanner entities matching source
    for entry in ent_reg.entities.values():
        if src_low in entry.entity_id or src_low in str(entry.unique_id).lower():
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
        self._on_area_detected = on_area_detected

        self._unsub_ble: Callable[[], None] | None = None
        # area_id -> (ema_rssi, last_seen_monotonic)
        self._area_rssi: dict[str, tuple[float, float]] = {}
        self._scanner_area_cache: dict[str, str | None] = {}
        self.current_area_id: str | None = None
        self.closest_scanner: str = ""
        self._last_switch_monotonic: float = 0.0

    @callback
    def async_start(self) -> None:
        """Subscribe to Home Assistant's internal Bluetooth advertisement stream."""
        self.async_stop()
        if len(self._target_uuid_hex) != 32:
            _LOGGER.debug(
                "Invalid BLE iBeacon UUID '%s'; skipping native BLE tracking.",
                self._target_uuid_hex,
            )
            return

        try:
            from homeassistant.components import bluetooth

            self._unsub_ble = bluetooth.async_register_callback(
                self.hass,
                self._async_on_ble_advertisement,
                {"connectable": False},
                bluetooth.BluetoothScanningMode.ACTIVE,
            )
            _LOGGER.info(
                "Latter Native BLE Room Tracker listening for iBeacon UUID %s across ESPHome proxies",
                self._target_uuid_hex,
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

    def _matches_target_device(self, service_info: object) -> bool:
        """Return True if advertisement matches Pocket Assistant iBeacon UUID or local name."""
        mfg_data: dict[int, bytes] = getattr(
            service_info, "manufacturer_data", {}
        )
        apple_bytes = mfg_data.get(APPLE_COMPANY_ID)
        if apple_bytes and len(apple_bytes) >= 20 and apple_bytes[:2] == IBEACON_PREFIX:
            uuid_hex = apple_bytes[2:18].hex().lower()
            if uuid_hex == self._target_uuid_hex:
                return True

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

        if source not in self._scanner_area_cache:
            self._scanner_area_cache[source] = _resolve_scanner_area_id(
                self.hass, source
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

        # Prune stale proxies
        stale_keys = [
            k
            for k, (_val, ts) in self._area_rssi.items()
            if (now - ts) > STALE_PROXY_SECONDS
        ]
        for k in stale_keys:
            self._area_rssi.pop(k, None)

        if not self._area_rssi:
            return

        # Find strongest room area
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

        # Enforce minimum hold time and hysteresis dB margin before switching rooms
        if (now - self._last_switch_monotonic) < MIN_HOLD_SECONDS:
            return

        cur_entry = self._area_rssi.get(self.current_area_id)
        cur_ema = cur_entry[0] if cur_entry is not None else -100.0
        if (best_ema - cur_ema) >= HYSTERESIS_DB:
            self.current_area_id = best_area
            self.closest_scanner = source
            self._last_switch_monotonic = now
            self._on_area_detected(best_area, source)