"""Voice Follows Me bound ESPHome Device Registry `area_id` synchronization."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from ..const import DOMAIN
from ..presence.ble_registry import get_ble_proxy_area_ids, get_ble_signature_area_ids
from .telemetry import bind_coordinator_area_listeners as bind_coordinator_area_listeners

__all__ = [
    "bind_coordinator_area_listeners",
    "sync_esphome_device_area",
]

_LOGGER = logging.getLogger(__name__)


def sync_esphome_device_area(
    hass: HomeAssistant,
    esphome_device_id: str,
    area_id: str | None,
    require_ble_proxy_area: bool = True,
    *,
    allow_clear: bool = False,
) -> dict[str, Any] | None:
    """Update the bound ESPHome device's (and child Latter device's) `area_id` in HA Device Registry."""
    norm_area: str | None = str(area_id or "").strip() or None
    if not esphome_device_id or (norm_area is None and not allow_clear):
        return None

    if require_ble_proxy_area and norm_area is not None:
        ble_areas = get_ble_proxy_area_ids(hass) | get_ble_signature_area_ids(hass)
        if ble_areas and norm_area not in ble_areas:
            _LOGGER.debug(
                "Skipping Device Registry area sync to '%s' because that area has no BLE proxy or signature.",
                norm_area,
            )
            return None

    dev_reg = dr.async_get(hass)
    dev = dev_reg.async_get(esphome_device_id)
    domain_data = hass.data.setdefault(DOMAIN, {})
    own_writes: dict[str, tuple[str, float]] = domain_data.setdefault(
        "_own_area_writes", {}
    )
    now_mono = time.monotonic()
    record: dict[str, Any] | None = None

    esp_mac: str | None = None
    if isinstance(dev, dr.DeviceEntry):
        for ctype, cval in dev.connections:
            if ctype == dr.CONNECTION_NETWORK_MAC and cval:
                esp_mac = dr.format_mac(str(cval))
                break
        if dev.area_id != norm_area:
            prev_area = str(dev.area_id or "")
            own_writes[esphome_device_id] = (norm_area or "", now_mono)
            dev_reg.async_update_device(esphome_device_id, area_id=norm_area)
            record = {
                "timestamp": dt_util.now().isoformat(timespec="seconds"),
                "from_area": prev_area,
                "to_area": norm_area or "",
                "device_id": esphome_device_id,
            }
            _LOGGER.debug(
                "Synced bound ESPHome device id=%s to area_id='%s'",
                esphome_device_id,
                norm_area or "",
            )

    for entry in hass.config_entries.async_entries(DOMAIN):
        for child in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            if (DOMAIN, "system") in child.identifiers:
                continue
            if (
                child.via_device_id == esphome_device_id
                or (esp_mac and (DOMAIN, esp_mac) in child.identifiers)
            ) and child.area_id != norm_area:
                prev_child = str(child.area_id or "")
                own_writes[child.id] = (norm_area or "", now_mono)
                dev_reg.async_update_device(child.id, area_id=norm_area)
                if record is None:
                    record = {
                        "timestamp": dt_util.now().isoformat(timespec="seconds"),
                        "from_area": prev_child,
                        "to_area": norm_area or "",
                        "device_id": esphome_device_id,
                    }
    return record
