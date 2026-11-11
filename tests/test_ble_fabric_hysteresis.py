"""Integration tests for BLE Presence Fabric, 3.0 dBm Hysteresis, Cross-Floor Attenuation, Sensor Fusion, and Voice Follows Me."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any
import uuid

from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest

from custom_components.latter import async_unload_entry
from custom_components.latter.const import (
    CONF_AREA_FUSION_CONFIG,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
)
from custom_components.latter.presence.ble_fabric import (
    APPLE_COMPANY_ID,
    AWAY_TIMEOUT_SECONDS,
    IBEACON_PREFIX,
    count_area_ble_proxies,
    get_all_areas_presence_summary,
    get_all_scanners_diagnostic_map,
    get_ble_fabric,
    get_ble_proxy_area_ids,
)
from custom_components.latter.presence.ble_math import (
    CROSS_FLOOR_ATTENUATION_DB,
    RSSI_HYSTERESIS_DEADBAND_DBM,
)


def _make_ibeacon_adv(
    beacon_uuid: str,
    *,
    rssi: int,
    source: str,
    obs_time: float,
    address: str = "AA:BB:CC:DD:EE:03",
    major: int = 1,
    minor: int = 1,
) -> Any:
    u_bytes = uuid.UUID(beacon_uuid).bytes
    payload = (
        IBEACON_PREFIX
        + u_bytes
        + major.to_bytes(2, "big")
        + minor.to_bytes(2, "big")
        + bytes([0xC5])
    )
    return SimpleNamespace(
        address=address,
        rssi=rssi,
        source=source,
        time=obs_time,
        manufacturer_data={APPLE_COMPANY_ID: payload},
    )


def _seed_ble_proxies(hass: Any) -> None:
    dev_reg = dr.async_get(hass)
    proxies = [
        ("lr_proxy", "aa:bb:cc:00:00:11", "Living Room Proxy", "living_room"),
        ("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen"),
        ("bed_proxy", "aa:bb:cc:00:00:33", "Bedroom Proxy", "bedroom"),
    ]
    scanners = []
    for slug, mac, title, area_id in proxies:
        dev_reg.async_get_or_create(
            config_entry_id=f"esp_{slug}",
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            identifiers={("esphome", mac)},
            name=title,
            area_id=area_id,
        )
        scanners.append(SimpleNamespace(source=mac.upper(), name=title, details={"source": mac}))
    hass.data["_bt_scanners"] = scanners


@pytest.mark.asyncio
async def test_ble_passive_matcher_rssi_hysteresis_and_cross_floor_penalty(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify BluetoothCallbackMatcher(connectable=False), 3.0 dBm deadband, and 6.0 dB cross-floor attenuation."""
    assert RSSI_HYSTERESIS_DEADBAND_DBM == 3.0
    assert CROSS_FLOOR_ATTENUATION_DB == 6.0

    _seed_ble_proxies(hass)
    entry, _sys_obj, coord = await setup_latter_hub(
        hass,
        with_ble_tag=True,
        extra_device_data={"area_follow_dwell_s": 5},
    )

    bt_callbacks = hass.data.get("_bt_callbacks", [])
    assert len(bt_callbacks) >= 1
    _cb_fn, matcher_dict, scan_mode = bt_callbacks[0]
    assert matcher_dict == {"connectable": False}
    assert str(scan_mode) == "passive"

    assert get_ble_proxy_area_ids(hass) == {"living_room", "kitchen", "bedroom"}
    assert count_area_ble_proxies(hass) == 3
    diag_map = get_all_scanners_diagnostic_map(hass)
    assert len(diag_map) == 3

    fabric = get_ble_fabric(hass)
    tracker = coord._ble_tracker
    assert tracker is not None
    tracker.update_manifest_beacon({"uuid": tracker.beacon_uuid, "major": 1, "minor": 1})

    occupancy_fires: list[int] = []
    survey_deltas: list[dict[str, Any]] = []
    unsub_occ = fabric.register_occupancy_listener(lambda: occupancy_fires.append(1))
    unsub_survey = fabric.register_survey_listener(lambda d: survey_deltas.append(d))

    t0 = time.monotonic()
    # 1) Initial lock in living_room (floor_1) at -55 dBm
    adv_lr = _make_ibeacon_adv(
        tracker.beacon_uuid, rssi=-55, source="AA:BB:CC:00:00:11", obs_time=t0
    )
    tracker._async_on_ble_advertisement(adv_lr, "adv")
    assert tracker.current_area_id == "living_room"
    assert tracker.winning_rssi == -55
    initial_fires = len(occupancy_fires)
    assert initial_fires >= 1
    assert len(survey_deltas) >= 1

    # 2) Sub-3.0 dBm RSSI jitter (-56 dBm, -54 dBm) in same confirmed_area -> ZERO occupancy callbacks!
    occupancy_fires.clear()
    survey_deltas.clear()
    tracker._async_on_ble_advertisement(
        _make_ibeacon_adv(
            tracker.beacon_uuid,
            rssi=-56,
            source="AA:BB:CC:00:00:11",
            obs_time=t0 + 0.5,
        ),
        "adv",
    )
    tracker._async_on_ble_advertisement(
        _make_ibeacon_adv(
            tracker.beacon_uuid,
            rssi=-54,
            source="AA:BB:CC:00:00:11",
            obs_time=t0 + 1.0,
        ),
        "adv",
    )
    assert occupancy_fires == []
    assert len(survey_deltas) == 2  # Survey listeners still receive live telemetry

    # >= 3.0 dBm shift in same area updates metrics
    for step in range(4):
        tracker._async_on_ble_advertisement(
            _make_ibeacon_adv(
                tracker.beacon_uuid,
                rssi=-42,
                source="AA:BB:CC:00:00:11",
                obs_time=t0 + 1.5 + step * 0.3,
            ),
            "adv",
        )
    assert len(occupancy_fires) >= 1

    # 3) Cross-floor 6.0 dB vertical attenuation penalty:
    # Bedroom is on floor_2. Even at -41 dBm raw, the -6.0 dB cross-floor penalty drops its score below living_room!
    tracker._area_raw_rssi["living_room"] = (-46.0, time.monotonic(), "AA:BB:CC:00:00:11")
    tracker._area_rssi["living_room"] = (-46.0, time.monotonic())
    tracker._ingest_proxy_observation(
        "AA:BB:CC:00:00:33", -43, time.monotonic(), "Bedroom Proxy"
    )
    assert tracker.current_area_id == "living_room"

    # 4) Strong same-floor signal in kitchen (floor_1) switches area cleanly once past switch cooldown
    tracker._last_switch_monotonic = time.monotonic() - 20.0
    now_k = time.monotonic()
    for i in range(4):
        tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:22", -36, now_k + i * 0.2, "Kitchen Proxy"
        )
    assert tracker.current_area_id == "kitchen"

    # Calibration offset application & telemetry snapshot
    tracker.set_area_offsets({"living_room": 8.0})
    cal_rows = tracker.get_area_calibration_telemetry()
    assert any(r["area_id"] == "kitchen" for r in cal_rows)
    rssi_summary = tracker.get_live_rssi_summary()
    assert "Kitchen" in rssi_summary

    unsub_occ()
    unsub_survey()
    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_sensor_fusion_modes_and_voice_follows_me_invariant(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify honest 'weighted' / boolean fusion modes, targeted sensor listeners, and Voice Follows Me stationary guard."""
    _seed_ble_proxies(hass)
    ent_reg = er.async_get(hass)
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="binary_sensor.kitchen_pir",
            platform="zwave_js",
            area_id="kitchen",
            original_device_class="motion",
        )
    )
    hass.states.async_set(
        "binary_sensor.kitchen_pir",
        "off",
        {"device_class": "motion", "friendly_name": "Kitchen PIR"},
    )
    hass.states.async_set("sensor.unrelated_power", "120", {})

    entry, _sys_obj, coord = await setup_latter_hub(
        hass,
        stationary=0,
        sync_device_area=True,
        extra_device_data={"area_follow_dwell_s": 0},
    )
    fabric = get_ble_fabric(hass)
    dev_reg = dr.async_get(hass)

    # Configure weighted fusion on kitchen
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_AREA_FUSION_CONFIG] = {
        "kitchen": {
            "mode": "weighted",
            "threshold_pct": 55,
            "sensors": ["binary_sensor.kitchen_pir"],
        }
    }
    fabric._invalidate_caches()
    occ_events: list[int] = []
    unsub = fabric.register_occupancy_listener(lambda: occ_events.append(1))
    fabric.rebind_fusion_sensor_listener()

    # Unrelated sensor state change MUST NOT trigger fusion listener
    occ_events.clear()
    hass.states.async_set("sensor.unrelated_power", "240", {})
    await hass.async_block_till_done()
    assert occ_events == []

    # Tracked PIR sensor turning on triggers fusion listener & raises weighted confidence
    hass.states.async_set(
        "binary_sensor.kitchen_pir",
        "on",
        {"device_class": "motion", "friendly_name": "Kitchen PIR"},
    )
    await hass.async_block_till_done()
    assert len(occ_events) >= 1
    occ_w = fabric.get_area_occupancy("kitchen")
    assert occ_w["fusion_mode"] == "weighted"
    assert occ_w["sensor_occupied"] is True

    # Test any_or, ble_only, ble_and_sensor modes
    for mode, expected_occ in (
        ("any_or", True),
        ("ble_only", False),
        ("ble_and_sensor", False),
    ):
        hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_AREA_FUSION_CONFIG]["kitchen"]["mode"] = mode
        res = fabric.get_area_occupancy("kitchen")
        assert res["fusion_mode"] == mode
        assert res["is_occupied"] is expected_occ

    summary_rows = get_all_areas_presence_summary(hass)
    assert any(r["area_id"] == "kitchen" for r in summary_rows)

    # Voice Follows Me: Roaming device (stationary == 0) updates its own bound ESPHome device area_id on explicit pick
    esp_dev = dev_reg.async_get(coord.esphome_device_id)
    assert esp_dev is not None
    coord.async_set_active_area("kitchen", sync_device_registry=True)
    assert esp_dev.area_id == "kitchen"

    # Away timeout MUST NOT clear ESPHome device area_id
    tracker = coord._ble_tracker
    assert tracker is not None
    tracker.check_away_timeout(time.monotonic() + AWAY_TIMEOUT_SECONDS + 30.0)
    assert tracker.is_away is True
    assert esp_dev.area_id == "kitchen"

    unsub()
    assert await async_unload_entry(hass, entry) is True

    # Stationary device (stationary == 1) MUST NEVER mutate ESPHome device area_id
    hass_stat = type(hass)(config_dir=hass.config.config_dir)
    _seed_ble_proxies(hass_stat)
    entry_s, _sys_s, coord_s = await setup_latter_hub(
        hass_stat,
        stationary=1,
        sync_device_area=True,
    )
    esp_stat = dr.async_get(hass_stat).async_get(coord_s.esphome_device_id)
    assert esp_stat is not None and esp_stat.area_id == "living_room"
    coord_s.async_set_active_area("kitchen", sync_device_registry=True)
    await asyncio.sleep(0)
    assert esp_stat.area_id == "living_room"
    assert await async_unload_entry(hass_stat, entry_s) is True
