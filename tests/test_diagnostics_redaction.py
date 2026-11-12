"""Integration tests for Latter diagnostics redaction and PII/secret sanitization."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.helpers import device_registry as dr

from custom_components.latter.const import (
    CONF_SECURITY_PIN_HASH,
    CONF_SYSTEM_BLE_UUID,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
)
from custom_components.latter.diagnostics import (
    async_get_config_entry_diagnostics,
    async_get_device_diagnostics,
)
from custom_components.latter.protocol import hash_security_pin


async def test_diagnostics_redacts_secrets_pins_ble_uuids_macs_and_signed_urls(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Ensure zero leakage of HMAC keys, PIN hashes, BLE UUIDs, MAC addresses, or signed URLs."""
    pin_hash = hash_security_pin("4321")
    entry, _sys_obj, coord = await setup_latter_hub(
        hass,
        with_device=True,
        with_ble_tag=True,
        extra_device_data={CONF_SECURITY_PIN_HASH: pin_hash},
    )
    global_cfg = hass.data[DOMAIN][DATA_GLOBAL_CONFIG]
    secret_hex = global_cfg["hmac_secret_hex"]
    ble_uuid = global_cfg[CONF_SYSTEM_BLE_UUID]
    global_cfg[CONF_SECURITY_PIN_HASH] = pin_hash
    global_cfg["leaked_preview"] = "http://192.168.1.50:8123/api/latter/art?src=abc&sig=deadbeefcafebabe&exp=999"

    # Seed calendar PII on coordinator to confirm calendar records/descriptions never leak
    coord.calendar_events = [{"summary": "Private Doctor Visit", "location": "123 Secret St"}]
    coord.calendar_records = [("Private Doctor Visit", "10:00", "123 Secret St")]

    entry_diag = await async_get_config_entry_diagnostics(hass, entry)
    serialized = json.dumps(entry_diag)

    assert secret_hex not in serialized
    assert pin_hash not in serialized
    assert "4321" not in serialized
    assert ble_uuid not in serialized
    assert "E2C56DB5-DFFB-48D2-B060-D0F5A71096E1" not in serialized
    assert "11:22:33:44:55:66" not in serialized
    assert "aa:bb:cc:dd:ee:01" not in serialized
    assert "deadbeefcafebabe" not in serialized

    # Verify per-device diagnostics for both bound display device and System service device
    dev_reg = dr.async_get(hass)
    latter_dev = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=coord.get_device_info()["identifiers"],
        name="Pocket Assistant",
    )
    dev_diag = await async_get_device_diagnostics(hass, entry, latter_dev)
    dev_serialized = json.dumps(dev_diag)
    assert pin_hash not in dev_serialized
    assert "aa:bb:cc:dd:ee:01" not in dev_serialized
    assert dev_diag["runtime"]["has_security_pin"] is True

    sys_dev = dev_reg.async_get_device({(DOMAIN, "system")})
    assert sys_dev is not None
    sys_diag = await async_get_device_diagnostics(hass, entry, sys_dev)
    assert "devices" in sys_diag
