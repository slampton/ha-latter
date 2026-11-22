"""Tests for BLE passive matcher hysteresis, cross-floor penalty, static iBeacon wake/sleep, C6 coprocessor MAC, and TCP race coalescing."""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any
import uuid

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
import pytest

from custom_components.latter import async_setup, async_setup_entry, async_unload_entry
from custom_components.latter.areas.telemetry import build_area_context_payload
from custom_components.latter.const import (
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    CONF_NATIVE_BLE_TRACKING,
    CONF_SYSTEM_BLE_UUID,
    DATA_GLOBAL_CONFIG,
    DEFAULT_BLE_BEACON_UUID,
    DOMAIN,
    MIN_FIRMWARE_SDK_REV,
    SUBENTRY_DEVICE,
)
from custom_components.latter.presence.ble_fabric import get_ble_fabric
from custom_components.latter.presence.ble_math import (
    CROSS_FLOOR_ATTENUATION_DB,
    RSSI_HYSTERESIS_DEADBAND_DBM,
)
from custom_components.latter.presence.ble_registry import (
    APPLE_COMPANY_ID,
    AWAY_TIMEOUT_SECONDS,
    IBEACON_PREFIX,
    SURVEY_RETENTION_SECONDS,
    WAKE_GAP_SECONDS,
    count_area_ble_proxies,
    get_all_scanners_diagnostic_map,
    get_ble_proxy_area_ids,
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
    tx_power_1m: int = -59,
) -> Any:
    u_bytes = uuid.UUID(beacon_uuid).bytes
    payload = (
        IBEACON_PREFIX
        + u_bytes
        + major.to_bytes(2, "big")
        + minor.to_bytes(2, "big")
        + bytes([tx_power_1m & 0xFF])
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


async def test_ble_passive_matcher_rssi_hysteresis_and_cross_floor_penalty(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify BluetoothCallbackMatcher() passive registration, 3.0 dBm deadband, and 6.0 dB cross-floor attenuation."""
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
    tracker = coord.ble_tracker
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
    now_cf = time.monotonic()
    for step in range(3):
        tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:11", -45, now_cf + step * 0.2, "Living Room Proxy"
        )
    for step in range(3):
        tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:33", -42, now_cf + 0.7 + step * 0.2, "Bedroom Proxy"
        )
    assert tracker.current_area_id == "living_room"

    # 4) Strong same-floor signal in kitchen (floor_1) switches area cleanly once past switch cooldown
    tracker._last_switch_monotonic = time.monotonic() - 20.0
    now_k = time.monotonic() + 2.0
    for i in range(4):
        tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:22", -36, now_k + i * 0.2, "Kitchen Proxy"
        )
    assert tracker.current_area_id == "kitchen"

    # Per-scanner calibration offset application & telemetry snapshot
    tracker.set_scanner_offsets({"aa:bb:cc:00:00:11": 8.0})
    cal_rows = tracker.get_scanner_calibration_telemetry()
    lr_cal = next(r for r in cal_rows if r["scanner_source"] == "AA:BB:CC:00:00:11")
    assert lr_cal["offset_db"] == 8.0
    assert any(
        r["area_id"] == "kitchen"
        and r["area_name"] == "Kitchen"
        and r["scanner_source"] == "AA:BB:CC:00:00:22"
        for r in cal_rows
    )

    unsub_occ()
    unsub_survey()
    assert await async_unload_entry(hass, entry) is True


async def test_static_ibeacon_roaming_wake_sticky_hot_swap_and_ble_sleep_hold(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify static-payload BLE roaming via raw address callbacks, custom UUID preservation, sticky wake hot-swap, and BLE sleep hold."""
    _seed_ble_proxies(hass)
    custom_uuid = "12345678-1234-5678-9ABC-DEF012345678"
    entry, _sys_obj, coord = await setup_latter_hub(
        hass,
        stationary=0,
        sync_device_area=True,
        extra_device_data={
            "area_follow_dwell_s": 0,
            "default_area": "",
        },
    )
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_SYSTEM_BLE_UUID] = custom_uuid
    await coord.async_on_global_config_updated({CONF_SYSTEM_BLE_UUID})
    coord.sync_ble_tracker()

    tracker = coord.ble_tracker
    assert tracker is not None
    assert tracker.beacon_uuid == custom_uuid

    # 1) device_hello with compile-time DEFAULT_BLE_BEACON_UUID MUST NOT clobber custom system_ble_uuid
    await coord.async_handle_device_hello(
        "42",
        '{"v":2,"contract":3,"board":"waveshare_s3_175c","w":466,"h":466,"shape":"circle",'
        '"display":1,"touch":1,"audio":1,"mic":1,"spk":1,"imu":1,"battery":1,"stationary":0,"wearable":0,'
        f'"beacon":{{"uuid":"{DEFAULT_BLE_BEACON_UUID}","major":1,"minor":1}},"sdk":{MIN_FIRMWARE_SDK_REV}}}',
    )
    assert tracker._target_uuid_hex == custom_uuid.replace("-", "").lower()

    # 2) Raw per-address advertisement callbacks registered for ESP32 BLE MAC (Wi-Fi MAC + 2 = AA:BB:CC:DD:EE:03)
    adv_cbs = dict(hass.data.get("_bt_adv_callbacks", []))
    raw_cb = next(
        (cb for cb, addr in hass.data.get("_bt_adv_callbacks", []) if addr == "AA:BB:CC:DD:EE:03"),
        None,
    )
    _ = adv_cbs
    assert raw_cb is not None
    shared_cb, _matcher, _mode = hass.data["_bt_callbacks"][0]

    # Simulate habluetooth: packet 1 in living_room fires BOTH shared_cb and raw_cb (deduped cleanly!)
    t0 = time.monotonic()
    pkt_lr = _make_ibeacon_adv(
        custom_uuid,
        rssi=-58,
        source="AA:BB:CC:00:00:11",
        obs_time=t0,
        address="AA:BB:CC:DD:EE:03",
    )
    raw_cb(pkt_lr)
    shared_cb(pkt_lr, "adv")
    assert tracker.packets_seen == 1
    assert tracker.current_area_id == "living_room"
    assert coord.active_area_id == "living_room"

    # Simulate static payload roam to kitchen: habluetooth suppresses shared_cb, ONLY raw_cb fires!
    tracker._last_switch_monotonic = t0 - 10.0
    for step in range(3):
        raw_cb(
            _make_ibeacon_adv(
                custom_uuid,
                rssi=-44,
                source="AA:BB:CC:00:00:22",
                obs_time=t0 + 1.0 + step * 0.3,
                address="AA:BB:CC:DD:EE:03",
            )
        )
    assert tracker.current_area_id == "kitchen"
    assert coord.active_area_id == "kitchen"

    # 3) Sticky Area across device wake + max_radius_m gate (>12m ignored) + single-packet hot-swap to bedroom (-78 dBm)
    tracker.last_packet_monotonic = t0 - 20.0
    tracker.reset_for_device_wake()
    assert tracker.current_area_id == "kitchen"  # Sticky before fresh BLE packet arrives!
    area_state, area_attrs = build_area_context_payload(coord)
    assert area_state == "Kitchen"
    assert area_attrs["area_id"] == "kitchen"

    t_wake = time.monotonic()
    raw_cb(
        _make_ibeacon_adv(
            custom_uuid,
            rssi=-86,
            source="AA:BB:CC:00:00:33",
            obs_time=t_wake + WAKE_GAP_SECONDS + 0.5,
            address="AA:BB:CC:DD:EE:03",
        )
    )
    assert tracker.current_area_id == "kitchen"  # -86 dBm (~16.9m) > 12.0m max_radius_m!

    tracker.last_packet_monotonic = t0 - 20.0
    tracker.reset_for_device_wake()
    t_wake2 = time.monotonic()
    raw_cb(
        _make_ibeacon_adv(
            custom_uuid,
            rssi=-78,
            source="AA:BB:CC:00:00:33",
            obs_time=t_wake2 + WAKE_GAP_SECONDS + 1.0,
            address="AA:BB:CC:DD:EE:03",
        )
    )
    assert tracker.current_area_id == "bedroom"
    assert coord.active_area_id == "bedroom"

    # 4) Persisted hello_manifest keeps is_roaming_device accurate across runtime snapshot restore
    snap = coord._build_persisted_snapshot()
    assert snap["hello_manifest"]["stationary"] == 0
    coord._runtime.hello_manifest = {}
    coord._apply_stored_runtime(snap)
    assert coord.is_roaming_device is True

    # 5) Intentional BLE sleep (screen-off on Wi-Fi -> ble_radio_active == "off") holds last Area past 180s
    ent_reg = er.async_get(hass)
    for eid, suffix, init_state in (
        ("sensor.pocket_assistant_wi_fi_signal", "Wi-Fi Signal", "-58"),
        ("binary_sensor.pocket_assistant_ble_radio_active", "BLE Radio Active", "off"),
        ("sensor.pocket_assistant_system_link_report", "System: Link Report", "ok"),
    ):
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=eid,
                platform="esphome",
                device_id=coord.esphome_device_id,
                original_name=suffix,
            )
        )
        hass.states.async_set(eid, init_state)
    coord._bind_link_report_listener()

    t_hold = tracker.last_packet_monotonic + AWAY_TIMEOUT_SECONDS + 60.0
    tracker.check_away_timeout(t_hold)
    assert tracker.is_away is False
    assert tracker.current_area_id == "bedroom"
    cur_name, _ = coord.get_current_area_and_distance()
    assert cur_name == "Bedroom"

    # Battery hibernation latch also holds Area when Wi-Fi goes unavailable after "hibernating" report
    hass.states.async_set("sensor.pocket_assistant_system_link_report", "hibernating")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.pocket_assistant_wi_fi_signal", "unavailable")
    tracker.check_away_timeout(t_hold + 60.0)
    assert tracker.is_away is False
    assert coord.get_current_area_and_distance()[0] == "Bedroom"

    # Whereas actively advertising unseen (ble_active == True via device_telemetry or ble_radio_active == "on") marks Away cleanly
    hass.states.async_set("sensor.pocket_assistant_wi_fi_signal", "-60")
    hass.states.async_set("sensor.pocket_assistant_system_link_report", "ok")
    coord.apply_device_telemetry({"ble_active": True, "int_ram_free_kb": 120})
    hass.states.async_set("binary_sensor.pocket_assistant_ble_radio_active", "on")
    await hass.async_block_till_done()
    tracker.check_away_timeout(t_hold + 120.0)
    assert tracker.is_away is True
    assert coord.is_device_away() is True
    assert coord.get_current_area_and_distance()[0] == "Away"

    assert await async_unload_entry(hass, entry) is True


async def test_coprocessor_ble_mac_persists_across_sleep_and_ble_radio_wake_grace(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify ESP32-P4+C6 co-processor BLE MAC seeding (>180s stale scanner cache), sleep retention, and BLE wake grace."""

    area_reg = ar.async_get(hass)
    area_reg.async_create("Garage", area_id="garage")
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id="esp_garage_proxy",
        connections={(dr.CONNECTION_NETWORK_MAC, "a8:42:e3:21:af:e2")},
        identifiers={("esphome", "a8:42:e3:21:af:e2")},
        name="garage-ep1",
        area_id="garage",
    )

    custom_uuid = "49BDD15E-2D6F-417C-B0C2-4E39EB0AF1DF"
    c6_ble_mac = "E8:3D:C1:D2:46:AA"
    p4_host_mac = "e8:f6:0a:e8:a4:a9"
    t0 = time.monotonic()
    stale_ts = t0 - SURVEY_RETENTION_SECONDS - 120.0
    stale_adv = _make_ibeacon_adv(
        custom_uuid,
        rssi=-53,
        source="A8:42:E3:21:AF:E2",
        obs_time=stale_ts,
        address=c6_ble_mac,
        major=1,
        minor=4,
    )
    hass.data["_bt_scanners"] = [
        SimpleNamespace(
            source="A8:42:E3:21:AF:E2",
            name="garage-ep1",
            details={"source": "a8:42:e3:21:af:e2"},
            discovered_device_timestamps={c6_ble_mac: stale_ts},
            discovered_devices_and_advertisement_data={
                c6_ble_mac: (SimpleNamespace(rssi=-53, name=None), stale_adv)
            },
        )
    ]

    esp_dev, mac = make_esphome_device(
        hass,
        slug="remote_assistant",
        mac=p4_host_mac,
        name="Remote Assistant",
        area_id="garage",
        stationary=0,
    )
    # Compact 255-char System: Hardware Manifest has top-level `minor` (no nested `beacon` dict)
    hass.states.async_set(
        "sensor.remote_assistant_system_hardware_manifest",
        '{"v":2,"contract":3,"board":"waveshare_p4_35","w":320,"h":480,"shape":"square",'
        '"display":1,"touch":1,"audio":1,"mic":1,"spk":1,"imu":0,"battery":1,'
        '"stationary":0,"wearable":0,"ips":1,"chip":"ESP32-P4","psram_mb":32,"minor":4}',
    )
    ent_reg = er.async_get(hass)
    if ent_reg.async_get("sensor.remote_assistant_wi_fi_signal") is None:
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id="sensor.remote_assistant_wi_fi_signal",
                platform="esphome",
                device_id=esp_dev.id,
                original_name="Wi-Fi Signal",
            )
        )
    hass.states.async_set("sensor.remote_assistant_wi_fi_signal", "-62")
    hass.states.async_set("binary_sensor.remote_assistant_ble_radio_active", "off")

    await async_setup(hass, {})
    entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="latter_hub_p4",
            domain=DOMAIN,
            title="Latter",
            data={},
            subentries_data=[
                ConfigSubentry(
                    subentry_id="sub_remote_p4",
                    subentry_type=SUBENTRY_DEVICE,
                    title="Remote Assistant",
                    unique_id=mac,
                    data={
                        CONF_DEVICE_SLUG: "remote_assistant",
                        CONF_ESPHOME_DEVICE_ID: esp_dev.id,
                        "mac": mac,
                        CONF_NATIVE_BLE_TRACKING: True,
                        "ble_auto_switch": True,
                        "sync_device_area": True,
                    },
                )
            ],
            unique_id=DOMAIN,
        )
    )
    assert await async_setup_entry(hass, entry) is True
    await hass.async_block_till_done()
    coord = entry.runtime_data.coordinators["sub_remote_p4"]
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_SYSTEM_BLE_UUID] = custom_uuid
    await coord.async_on_global_config_updated({CONF_SYSTEM_BLE_UUID})
    coord.ble_tracker.async_stop()
    coord._ble_tracker = None
    coord.sync_ble_tracker()

    tracker = coord.ble_tracker
    assert tracker is not None

    # 1) Stale (>180s) scanner cache still seeds C6 BLE MAC for raw callback without scoring stale RSSI
    assert c6_ble_mac in tracker.matched_ble_addresses
    assert tracker.packets_seen == 0
    raw_cb = next(
        (cb for cb, addr in hass.data.get("_bt_adv_callbacks", []) if addr == c6_ble_mac),
        None,
    )
    assert raw_cb is not None
    snap = coord._build_persisted_snapshot()
    assert snap["matched_ble_addresses"] == [c6_ble_mac]

    # 2) Screen-off BLE sleep > 180s MUST NOT evict C6 BLE MAC or unsubscribe raw_cb
    tracker.check_away_timeout(t0 + AWAY_TIMEOUT_SECONDS + 90.0)
    assert tracker.is_away is False
    assert any(addr == c6_ble_mac for _cb, addr in hass.data.get("_bt_adv_callbacks", []))

    # 3) Even if tracker was previously Away, reboot (`device_hello`) + `BLE Radio Active -> on` 4s later
    #    holds sticky Garage instead of flipping to Away / Unassigned before BLE packets arrive
    tracker.is_away = True
    await coord.async_handle_device_hello(
        "2053920193",
        '{"v":2,"contract":3,"board":"waveshare_p4_35","w":320,"h":480,"shape":"square",'
        '"display":1,"touch":1,"audio":1,"mic":1,"spk":1,"imu":0,"battery":1,"stationary":0,"wearable":0,'
        f'"beacon":{{"uuid":"4C415454-4552-434F-5245-000000000220","major":1,"minor":4}},"sdk":{MIN_FIRMWARE_SDK_REV}}}',
    )
    hass.states.async_set("binary_sensor.remote_assistant_ble_radio_active", "on")
    await hass.async_block_till_done()
    assert tracker.is_away is False
    assert coord.is_device_away() is False
    area_name, area_attrs = build_area_context_payload(coord)
    assert area_name == "Garage"
    assert area_attrs["area_id"] == "garage"

    # Immediate away-check tick 5s after BLE Radio Active -> on still grants full 180s window
    tracker.check_away_timeout(time.monotonic() + 5.0)
    assert tracker.is_away is False
    assert coord.is_device_away() is False

    # 4) Static iBeacon packet on C6 BLE MAC arrives via raw_cb (habluetooth suppresses shared_cb)
    raw_cb(
        _make_ibeacon_adv(
            custom_uuid,
            rssi=-53,
            source="A8:42:E3:21:AF:E2",
            obs_time=time.monotonic() + 1.0,
            address=c6_ble_mac,
            major=1,
            minor=4,
        )
    )
    assert tracker.packets_seen == 1
    assert tracker.current_area_id == "garage"
    assert tracker.winning_rssi == -53
    assert coord.get_current_area_and_distance()[0] == "Garage"

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_wake_and_gap_multi_proxy_tcp_race_coalescing(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify post-wake 0.35s multi-proxy coalescing blocks 20ms TCP race jumps while allowing genuine moves."""
    _seed_ble_proxies(hass)
    entry, _sys_obj, coord = await setup_latter_hub(
        hass,
        stationary=0,
        sync_device_area=True,
        extra_device_data={"area_follow_dwell_s": 0},
    )
    tracker = coord.ble_tracker
    assert tracker is not None
    tracker.update_manifest_beacon({"uuid": tracker.beacon_uuid, "major": 1, "minor": 1})

    area_changes: list[str] = []
    unsub_ev = hass.bus.async_listen(
        "latter_event",
        lambda ev: area_changes.append(str(ev.data.get("area_id")))
        if ev.data.get("type") == "area_changed"
        else None,
    )

    t0 = time.monotonic()
    tracker._async_on_ble_advertisement(
        _make_ibeacon_adv(
            tracker.beacon_uuid, rssi=-52, source="AA:BB:CC:00:00:11", obs_time=t0
        ),
        "adv",
    )
    assert tracker.current_area_id == "living_room"
    area_changes.clear()

    # 1) Wake TCP race: distant bedroom proxy (-78 dBm) delivers Packet #1 20ms BEFORE local living_room proxy (-52 dBm)
    tracker.last_packet_monotonic = t0 - 20.0
    tracker.reset_for_device_wake()
    t_wake = time.monotonic()

    tracker._async_on_ble_advertisement(
        _make_ibeacon_adv(
            tracker.beacon_uuid,
            rssi=-78,
            source="AA:BB:CC:00:00:33",
            obs_time=t_wake + 0.01,
        ),
        "adv",
    )
    assert tracker.current_area_id == "living_room"
    assert coord.active_area_id == "living_room"
    assert tracker._unsub_wake_coalesce is not None
    assert area_changes == []

    # 20ms later local living_room proxy packet arrives -> cancels coalesce timer, zero transient jump!
    tracker._async_on_ble_advertisement(
        _make_ibeacon_adv(
            tracker.beacon_uuid,
            rssi=-52,
            source="AA:BB:CC:00:00:11",
            obs_time=t_wake + 0.03,
        ),
        "adv",
    )
    assert tracker._unsub_wake_coalesce is None
    assert tracker.current_area_id == "living_room"
    assert coord.active_area_id == "living_room"
    assert area_changes == []

    # 2) Genuine move on wake where living_room hears nothing: commits cleanly when ~0.35s settlement timer fires
    tracker.last_packet_monotonic = time.monotonic() - 25.0
    tracker.reset_for_device_wake()
    t_wake2 = time.monotonic()
    tracker._async_on_ble_advertisement(
        _make_ibeacon_adv(
            tracker.beacon_uuid,
            rssi=-64,
            source="AA:BB:CC:00:00:33",
            obs_time=t_wake2 + 0.01,
        ),
        "adv",
    )
    assert tracker.current_area_id == "living_room"
    assert tracker._unsub_wake_coalesce is not None
    coalesce_cbs = [
        cb for delay, cb in hass._timers if isinstance(delay, float) and abs(delay - 0.35) < 0.01
    ]
    assert len(coalesce_cbs) == 1
    coalesce_cbs[0](None)
    assert tracker._unsub_wake_coalesce is None
    assert tracker.current_area_id == "bedroom"
    assert coord.active_area_id == "bedroom"
    assert area_changes == ["bedroom"]

    # 3) Genuine move on wake commits immediately on 2nd challenger packet without waiting for timer
    area_changes.clear()
    tracker.last_packet_monotonic = time.monotonic() - 25.0
    tracker.reset_for_device_wake()
    t_wake3 = time.monotonic()
    tracker._async_on_ble_advertisement(
        _make_ibeacon_adv(
            tracker.beacon_uuid,
            rssi=-60,
            source="AA:BB:CC:00:00:22",
            obs_time=t_wake3 + 0.01,
        ),
        "adv",
    )
    assert tracker.current_area_id == "bedroom"
    assert tracker._unsub_wake_coalesce is not None
    tracker._async_on_ble_advertisement(
        _make_ibeacon_adv(
            tracker.beacon_uuid,
            rssi=-59,
            source="AA:BB:CC:00:00:22",
            obs_time=t_wake3 + 0.12,
        ),
        "adv",
    )
    assert tracker._unsub_wake_coalesce is None
    assert tracker.current_area_id == "kitchen"
    assert coord.active_area_id == "kitchen"
    assert area_changes == ["kitchen"]

    unsub_ev()
    assert await async_unload_entry(hass, entry) is True
