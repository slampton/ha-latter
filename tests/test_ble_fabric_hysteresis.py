"""Integration tests for BLE Presence Fabric, 3.0 dBm Hysteresis, Cross-Floor Attenuation, Sensor Fusion, and Voice Follows Me."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any
import uuid

from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
import pytest

from custom_components.latter import async_unload_entry
from custom_components.latter.const import (
    CONF_AREA_FUSION_CONFIG,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
)
from custom_components.latter.presence import (
    APPLE_COMPANY_ID,
    AWAY_TIMEOUT_SECONDS,
    CROSS_FLOOR_ATTENUATION_DB,
    IBEACON_PREFIX,
    RSSI_HYSTERESIS_DEADBAND_DBM,
    count_area_ble_proxies,
    get_all_areas_presence_summary,
    get_all_scanners_diagnostic_map,
    get_ble_fabric,
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
    assert matcher_dict == {}
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


@pytest.mark.asyncio
async def test_static_ibeacon_roaming_wake_sticky_hot_swap_and_ble_sleep_hold(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify static-payload BLE roaming via raw address callbacks, custom UUID preservation, sticky wake hot-swap, and BLE sleep hold."""
    from custom_components.latter.areas import build_area_context_payload
    from custom_components.latter.const import (
        CONF_SYSTEM_BLE_UUID,
        DEFAULT_BLE_BEACON_UUID,
        MIN_FIRMWARE_SDK_REV,
    )
    from custom_components.latter.presence import WAKE_GAP_SECONDS

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
    coord._sync_ble_tracker()

    tracker = coord._ble_tracker
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
    coord._runtime.hello_manifest = None
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

    # Whereas actively advertising unseen (ble_radio_active == "on") marks Away cleanly
    hass.states.async_set("sensor.pocket_assistant_wi_fi_signal", "-60")
    hass.states.async_set("sensor.pocket_assistant_system_link_report", "ok")
    hass.states.async_set("binary_sensor.pocket_assistant_ble_radio_active", "on")
    await hass.async_block_till_done()
    tracker.check_away_timeout(t_hold + 120.0)
    assert tracker.is_away is True
    assert coord.is_device_away() is True
    assert coord.get_current_area_and_distance()[0] == "Away"

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_static_assigned_area_startup_healing_live_reassignment_and_two_way_sync(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify D-032 static Area startup healing, live HA Device Registry reassignment, and Studio two-way sync."""
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry

    from custom_components.latter import async_setup, async_setup_entry
    from custom_components.latter.areas import resolve_active_area_entry
    from custom_components.latter.const import (
        CONF_BLE_AUTO_SWITCH,
        CONF_DEFAULT_AREA,
        CONF_DEVICE_SLUG,
        CONF_ESPHOME_DEVICE_ID,
        CONF_NATIVE_BLE_TRACKING,
        CONF_SYNC_DEVICE_AREA,
        STORAGE_KEY_PREFIX,
        SUBENTRY_DEVICE,
    )
    from custom_components.latter.groups import coordinator_supports_pref
    from custom_components.latter.studio.payload import build_studio_state_payload
    from custom_components.latter.studio.settings import (
        DEVICE_PREF_SPEC_MAP,
        clean_device_settings,
    )

    area_reg = ar.async_get(hass)
    area_reg.async_create("Garage", area_id="garage", floor_id="floor_1")
    area_reg.async_create("Living Area", area_id="living_room", floor_id="floor_1")
    area_reg.async_create("Kitchen", area_id="kitchen", floor_id="floor_1")

    # ESPHome Device was reassigned in HA from Garage -> Living Area while Latter still held Garage in subentry & runtime
    esp_dev, mac = make_esphome_device(
        hass,
        slug="desk_assistant",
        mac="aa:bb:cc:dd:ee:99",
        name="Desk Assistant",
        area_id="living_room",
        stationary=1,
    )
    dev_reg = dr.async_get(hass)
    child_latter_dev = dev_reg.async_get_or_create(
        config_entry_id="entry_latter_hub",
        identifiers={(DOMAIN, dr.format_mac(mac))},
        via_device_id=esp_dev.id,
        name="Desk Assistant",
        area_id="garage",
    )
    hass._storage_mem[f"{STORAGE_KEY_PREFIX}_sub_desk"] = {
        "active_area_id": "garage",
    }

    await async_setup(hass, {})
    entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="entry_latter_hub",
            domain=DOMAIN,
            title="Latter",
            data={},
            subentries_data=[
                ConfigSubentry(
                    data={
                        CONF_ESPHOME_DEVICE_ID: esp_dev.id,
                        "mac": mac,
                        CONF_DEVICE_SLUG: "desk_assistant",
                        CONF_DEFAULT_AREA: "garage",
                        CONF_NATIVE_BLE_TRACKING: False,
                        CONF_BLE_AUTO_SWITCH: False,
                        CONF_SYNC_DEVICE_AREA: False,
                    },
                    subentry_type=SUBENTRY_DEVICE,
                    title="Desk Assistant",
                    unique_id=mac,
                    subentry_id="sub_desk",
                )
            ],
            unique_id=DOMAIN,
        )
    )
    assert await async_setup_entry(hass, entry) is True
    await hass.async_block_till_done()

    coord = entry.runtime_data.coordinators["sub_desk"]

    # 1) Startup heals active_area_id, CONF_DEFAULT_AREA, child Latter device, and Current Area from esp_dev.area_id
    assert coord.active_area_id == "living_room"
    assert coord.get_opt(CONF_DEFAULT_AREA) == "living_room"
    assert child_latter_dev.area_id == "living_room"
    active_entry = resolve_active_area_entry(coord)
    assert active_entry is not None and active_entry.id == "living_room"
    assert hass.states.get("sensor.desk_assistant_current_area").state == "Living Area"

    # Non-battery panel hides battery-only ble_beacon_mode preference
    assert (
        coordinator_supports_pref(coord, DEVICE_PREF_SPEC_MAP["ble_beacon_mode"])
        is False
    )

    # 2) Live HA Device Registry reassignment on ESPHome Device updates active Area + child Latter device immediately
    dev_reg.async_update_device(esp_dev.id, area_id="kitchen")
    await hass.async_block_till_done()
    assert coord.active_area_id == "kitchen"
    assert coord.get_opt(CONF_DEFAULT_AREA) == "kitchen"
    assert child_latter_dev.area_id == "kitchen"
    assert hass.states.get("sensor.desk_assistant_current_area").state == "Kitchen"

    # Reassigning child Latter Device in HA mirrors back to parent ESPHome Device and active Area
    dev_reg.async_update_device(child_latter_dev.id, area_id="garage")
    await hass.async_block_till_done()
    assert esp_dev.area_id == "garage"
    assert coord.active_area_id == "garage"
    assert coord.get_opt(CONF_DEFAULT_AREA) == "garage"

    # Unrelated Device Registry update (e.g., rename without area_id change) leaves active Area intact
    dev_reg.async_update_device(esp_dev.id, name_by_user="Desk Assistant Pro")
    await hass.async_block_till_done()
    assert coord.active_area_id == "garage"

    # 3) Two-way Studio Static Assigned Area update & clearing (Unassigned)
    cleaned_assign = clean_device_settings(
        {"default_area": "living_room"}, coord.device_data
    )
    coord.update_device_config({**coord.device_data, **cleaned_assign})
    await coord.async_apply_options()
    await hass.async_block_till_done()
    assert esp_dev.area_id == "living_room"
    assert child_latter_dev.area_id == "living_room"
    assert coord.active_area_id == "living_room"
    assert hass.states.get("sensor.desk_assistant_current_area").state == "Living Area"

    studio_state = build_studio_state_payload(hass, coord)
    dev_row = next(
        d for d in studio_state["system_devices"] if d["subentry_id"] == "sub_desk"
    )
    assert dev_row["has_assigned_area"] is True
    assert dev_row["area_label"] == "Living Area"
    assert studio_state["config"]["default_area"] == "living_room"

    cleaned_clear = clean_device_settings({"default_area": ""}, coord.device_data)
    coord.update_device_config({**coord.device_data, **cleaned_clear})
    await coord.async_apply_options()
    await hass.async_block_till_done()
    assert esp_dev.area_id is None
    assert child_latter_dev.area_id is None
    assert coord.active_area_id is None
    assert hass.states.get("sensor.desk_assistant_current_area").state == "Unassigned"

    # 4) Switching Static -> BLE Roaming auto-enables ble_auto_switch; switching back pins current active Area
    cleaned_roam = clean_device_settings(
        {"native_ble_tracking": True}, coord.device_data
    )
    assert cleaned_roam["ble_auto_switch"] is True
    coord.update_device_config({**coord.device_data, **cleaned_roam})
    await coord.async_apply_options()
    coord.async_set_active_area("kitchen", sync_device_registry=False)
    assert coord.active_area_id == "kitchen"

    cleaned_pin = clean_device_settings(
        {"native_ble_tracking": False}, coord.device_data
    )
    coord.update_device_config({**coord.device_data, **cleaned_pin})
    await coord.async_apply_options()
    assert coord.get_opt(CONF_DEFAULT_AREA) == "kitchen"
    assert esp_dev.area_id == "kitchen"
    assert child_latter_dev.area_id == "kitchen"

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_coprocessor_ble_mac_persists_across_sleep_and_ble_radio_wake_grace(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify ESP32-P4+C6 co-processor BLE MAC seeding (>180s stale scanner cache), sleep retention, and BLE wake grace."""
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry

    from custom_components.latter import async_setup, async_setup_entry
    from custom_components.latter.areas import build_area_context_payload
    from custom_components.latter.const import (
        CONF_DEVICE_SLUG,
        CONF_ESPHOME_DEVICE_ID,
        CONF_NATIVE_BLE_TRACKING,
        CONF_SYSTEM_BLE_UUID,
        MIN_FIRMWARE_SDK_REV,
        SUBENTRY_DEVICE,
    )
    from custom_components.latter.presence import SURVEY_RETENTION_SECONDS

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
    coord._ble_tracker.async_stop()
    coord._ble_tracker = None
    coord._sync_ble_tracker()

    tracker = coord._ble_tracker
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
    tracker = coord._ble_tracker
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


@pytest.mark.asyncio
async def test_rayleigh_multipath_spike_fast_override_gate_and_velocity_clamping(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify 3-sample median, >=2 packet FAST_OVERRIDE_DB gate, and max_velocity_mps damp multipath & body fades."""
    _seed_ble_proxies(hass)
    entry, _sys_obj, coord = await setup_latter_hub(hass, stationary=0)
    tracker = coord._ble_tracker
    assert tracker is not None
    tracker.update_manifest_beacon({"uuid": tracker.beacon_uuid, "major": 1, "minor": 1})

    t0 = time.monotonic()
    for step in range(3):
        tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:11", -55, t0 + step * 0.4, "Living Room Proxy"
        )
    assert tracker.current_area_id == "living_room"

    # Stationary device: living_room suffers a 1-packet deep body/channel fade (-88 dBm after 0.2s -> ~97 m/s!)
    # while kitchen gets a single-packet multipath spike (-46 dBm).
    tracker._ingest_proxy_observation(
        "AA:BB:CC:00:00:11", -88, t0 + 1.0, "Living Room Proxy"
    )
    lr_state = tracker._scanner_states["AA:BB:CC:00:00:11"]
    # 3-sample median over [-55, -55, -88] is -55.0! Even a 2nd fade [-55, -88, -88] is velocity-clamped!
    assert lr_state.x_dbm > -57.0

    tracker._ingest_proxy_observation(
        "AA:BB:CC:00:00:11", -88, t0 + 1.15, "Living Room Proxy"
    )
    # Velocity gate clamps sudden recession (3.5 m/s * 0.15s = +0.525m max recession from ~1.5m -> ~2.0m = -65.7 dBm)
    assert lr_state.x_dbm > -64.0

    # Single-packet multipath spike on a cold scanner (bedroom at -38 dBm, packet_count == 1) CANNOT trigger FAST_OVERRIDE_DB!
    tracker._ingest_proxy_observation(
        "AA:BB:CC:00:00:33", -38, t0 + 1.2, "Bedroom Proxy"
    )
    assert tracker.current_area_id == "living_room"

    # Stationary baseline in kitchen (-76 dBm x 2), followed by a single-packet channel-hop spike (-45 dBm):
    # 3-sample median over [-76, -76, -45] is -76.0 -> ZERO spike leakage into Kalman filter!
    tracker._ingest_proxy_observation(
        "AA:BB:CC:00:00:22", -76, t0 + 1.5, "Kitchen Proxy"
    )
    tracker._ingest_proxy_observation(
        "AA:BB:CC:00:00:22", -76, t0 + 1.8, "Kitchen Proxy"
    )
    tracker._ingest_proxy_observation(
        "AA:BB:CC:00:00:22", -45, t0 + 2.1, "Kitchen Proxy"
    )
    kit_state = tracker._scanner_states["AA:BB:CC:00:00:22"]
    assert abs(kit_state.x_dbm - (-76.0)) < 0.5
    assert tracker.current_area_id == "living_room"

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_multi_scanner_same_area_aggregation_never_averages_down(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify two scanners in the same Area track separately, take max + corroboration bonus, and never average down."""
    from custom_components.latter.presence import CORROBORATION_BONUS_DB

    _seed_ble_proxies(hass)
    # Add a 2nd scanner in living_room (Living Room South)
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id="esp_lr_south",
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:00:00:19")},
        identifiers={("esphome", "aa:bb:cc:00:00:19")},
        name="Living Room South",
        area_id="living_room",
    )
    hass.data["_bt_scanners"].append(
        SimpleNamespace(
            source="AA:BB:CC:00:00:19",
            name="Living Room South",
            details={"source": "aa:bb:cc:00:00:19"},
        )
    )

    entry, _sys_obj, coord = await setup_latter_hub(hass, stationary=0)
    tracker = coord._ble_tracker
    assert tracker is not None

    t0 = time.monotonic()
    # Alternate North (-50 dBm) and South (-84 dBm -> >12m / weak) while Kitchen sits at -60 dBm after hold
    tracker._last_switch_monotonic = t0 - 15.0
    for idx in range(6):
        tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:11", -50, t0 + idx * 0.4, "Living Room Proxy"
        )
        tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:19", -84, t0 + idx * 0.4 + 0.15, "Living Room South"
        )
        tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:22", -60, t0 + idx * 0.4 + 0.25, "Kitchen Proxy"
        )

    assert tracker.current_area_id == "living_room"
    assert tracker.winning_rssi is not None and -52 <= tracker.winning_rssi <= -49
    assert abs(tracker._scanner_states["AA:BB:CC:00:00:11"].x_dbm - (-50.0)) < 1.5
    assert abs(tracker._scanner_states["AA:BB:CC:00:00:19"].x_dbm - (-84.0)) < 1.5

    # Corroboration bonus (+1.5 dB): when South also reads -76 dBm (>= -82 dBm, within 12m),
    # Living Room (-54 + 1.5 = -52.5 dBm) beats Kitchen (-53 dBm) even past hold!
    assert CORROBORATION_BONUS_DB == 1.5
    t1 = t0 + 20.0
    tracker._scanner_states.clear()
    for idx in range(3):
        tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:11", -54, t1 + idx * 0.3, "Living Room Proxy"
        )
        tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:19", -76, t1 + idx * 0.3 + 0.1, "Living Room South"
        )
    assert tracker.current_area_id == "living_room"
    tracker._last_switch_monotonic = t1 - 10.0
    for idx in range(3):
        tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:22", -48, t1 + 1.2 + idx * 0.3, "Kitchen Proxy"
        )
    # -48 - (-54 + 1.5) = +4.5 dB < 5.0 dB HYSTERESIS_DB because of the +1.5 dB 2-scanner corroboration bonus!
    assert tracker.current_area_id == "living_room"

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_multi_scanner_vector_signature_trilateration_and_proxyless_area(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify multi-scanner signature capture & cross-device ref_power normalization in a proxy-less Area."""
    from homeassistant.components import websocket_api

    from custom_components.latter.presence import get_area_signatures_summary
    from custom_components.latter.studio.commands import STUDIO_REV

    _seed_ble_proxies(hass)
    # Create a proxy-less Area (`guest_bath`) surrounded by living_room, kitchen, and bedroom proxies
    ar.async_get(hass).async_create("Guest Bath", area_id="guest_bath", floor_id="floor_1")
    assert "guest_bath" not in get_ble_proxy_area_ids(hass)

    entry, sys_obj, coord = await setup_latter_hub(
        hass,
        with_ble_tag=True,
        stationary=0,
    )
    tag_coord = sys_obj.coordinators["sub_tag"]
    assert coord._ble_tracker is not None
    assert tag_coord._ble_tracker is not None

    # 1) Stand in `guest_bath` with handheld (`ble_ref_power` default -59 dBm @ 1m) and collect 3-scanner vector
    t0 = time.monotonic()
    for step in range(5):
        ts = t0 + step * 0.3
        coord._ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:11", -68, ts, "Living Room Proxy")
        coord._ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:22", -66, ts + 0.05, "Kitchen Proxy")
        coord._ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:33", -74, ts + 0.10, "Bedroom Proxy")

    # Capture signature via Studio WebSocket command
    conn = websocket_api.ActiveConnection()
    ws_handler = hass._ws_commands["latter/system/command"]
    await ws_handler(
        hass,
        conn,
        {
            "id": 1,
            "type": "latter/system/command",
            "command": "capture_ble_area_signature",
            "payload": {"area_id": "guest_bath", "survey_subentry_id": coord.subentry_id},
            "studio_rev": STUDIO_REV,
        },
    )
    assert not conn.errors
    sig_summary = get_area_signatures_summary(hass)
    gb_row = next(s for s in sig_summary if s["area_id"] == "guest_bath")
    assert gb_row["has_ble_proxy"] is False
    assert gb_row["has_signature"] is True
    assert gb_row["scanner_count"] == 3
    assert gb_row["sample_count"] >= 15

    # 2) Configure 2nd device (`keys_tag`) as a louder phone/tag with `ble_ref_power = -49` dBm (+10 dB vs -59 dBm)
    tag_coord.update_device_config({**tag_coord.device_data, "ble_ref_power": -49})
    await tag_coord.async_apply_options()
    assert tag_coord._ble_tracker.effective_ref_power_dbm == -49.0

    # Feed raw RSSI +10 dB louder at the exact same physical spot in `guest_bath`:
    # (-58, -56, -64 raw -> normalized to -68, -66, -74 @ -59 dBm!)
    t1 = time.monotonic() + 1.0
    for step in range(4):
        ts = t1 + step * 0.3
        tag_coord._ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:11", -58, ts, "Living Room Proxy")
        tag_coord._ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:22", -56, ts + 0.05, "Kitchen Proxy")
        tag_coord._ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:33", -64, ts + 0.10, "Bedroom Proxy")

    assert tag_coord._ble_tracker.current_area_id == "guest_bath"
    assert tag_coord._ble_tracker.match_method == "signature"
    assert tag_coord.active_area_id == "guest_bath"
    await hass.async_block_till_done()
    tag_area_st = hass.states.get("sensor.keys_tag_current_area")
    assert tag_area_st is not None
    assert tag_area_st.state == "Guest Bath"
    assert tag_area_st.attributes["match_method"] == "signature"

    # 3) Walk right up to Living Room proxy (-36 dBm raw -> -46 dBm normalized) -> distance model wins cleanly!
    tag_coord._ble_tracker._last_switch_monotonic = t1 - 20.0
    t2 = t1 + 5.0
    for step in range(4):
        ts = t2 + step * 0.3
        tag_coord._ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:11", -36, ts, "Living Room Proxy")
        tag_coord._ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:22", -66, ts + 0.05, "Kitchen Proxy")
        tag_coord._ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:33", -74, ts + 0.10, "Bedroom Proxy")

    assert tag_coord._ble_tracker.current_area_id == "living_room"
    assert tag_coord._ble_tracker.match_method == "distance"

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_zero_ms_private_ble_rpa_rotation_connectable_and_eddystone_uid(
    hass: Any,
) -> None:
    """Verify 0 ms state_changed Private BLE RPA rotation, stale RPA eviction, connectable advs, and Eddystone-UID."""
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry

    from custom_components.latter import async_setup, async_setup_entry
    from custom_components.latter.const import (
        CONF_ASSIGNED_PERSON,
        CONF_BLE_TARGET_ADDRESS,
        CONF_DEVICE_SLUG,
        CONF_NATIVE_BLE_TRACKING,
        SUBENTRY_BLE_TAG,
    )

    area_reg = ar.async_get(hass)
    area_reg.async_create("Living Room", area_id="living_room", floor_id="floor_1")
    area_reg.async_create("Kitchen", area_id="kitchen", floor_id="floor_1")
    _seed_ble_proxies(hass)
    hass.states.async_set("person.sean", "home", {"friendly_name": "Sean"})

    # Seed `private_ble_device` entity with initial RPA
    rpa_1 = "54:AA:11:22:33:01"
    rpa_2 = "67:BB:44:55:66:02"
    hass.states.async_set(
        "device_tracker.phone_ble",
        "home",
        {"current_address": rpa_1, "friendly_name": "Sean iPhone BLE"},
    )
    eddystone_uid_hex = "00112233445566778899aabbccddeeff"

    await async_setup(hass, {})
    entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="entry_latter_rpa",
            domain=DOMAIN,
            title="Latter",
            data={},
            subentries_data=[
                ConfigSubentry(
                    subentry_id="sub_phone_ble",
                    subentry_type=SUBENTRY_BLE_TAG,
                    title="Sean Phone",
                    unique_id="tag_phone_ble",
                    data={
                        CONF_DEVICE_SLUG: "sean_phone",
                        CONF_BLE_TARGET_ADDRESS: "device_tracker.phone_ble",
                        CONF_ASSIGNED_PERSON: "person.sean",
                        CONF_NATIVE_BLE_TRACKING: True,
                    },
                ),
                ConfigSubentry(
                    subentry_id="sub_eddy_tag",
                    subentry_type=SUBENTRY_BLE_TAG,
                    title="Luggage Eddystone",
                    unique_id="tag_eddy",
                    data={
                        CONF_DEVICE_SLUG: "luggage_eddy",
                        CONF_BLE_TARGET_ADDRESS: f"eddystone:{eddystone_uid_hex}",
                        CONF_NATIVE_BLE_TRACKING: True,
                    },
                ),
            ],
            unique_id=DOMAIN,
        )
    )
    assert await async_setup_entry(hass, entry) is True
    await hass.async_block_till_done()

    fabric = get_ble_fabric(hass)
    phone_tracker = entry.runtime_data.coordinators["sub_phone_ble"]._ble_tracker
    eddy_tracker = entry.runtime_data.coordinators["sub_eddy_tag"]._ble_tracker
    assert phone_tracker is not None and eddy_tracker is not None

    # 1) Initial RPA subscribed in O(1)
    assert rpa_1 in fabric._adv_unsubs
    assert phone_tracker.matched_ble_addresses == [rpa_1]

    # 2) Rotate RPA via state_changed -> updates in 0 ms and evicts stale rpa_1 from _adv_unsubs!
    hass.states.async_set(
        "device_tracker.phone_ble",
        "home",
        {"current_address": rpa_2, "friendly_name": "Sean iPhone BLE"},
    )
    assert rpa_2 in fabric._adv_unsubs
    assert rpa_1 not in fabric._adv_unsubs
    assert phone_tracker.matched_ble_addresses == [rpa_2]
    assert not any(addr == rpa_1 for _cb, addr in hass.data.get("_bt_adv_callbacks", []))

    # 3) Connectable BLE advertisement (`connectable=True`, empty mfg_data) on rpa_2 matches passively!
    shared_cb, matcher_dict, _mode = hass.data["_bt_callbacks"][0]
    assert matcher_dict == {}
    t0 = time.monotonic()
    conn_adv = SimpleNamespace(
        address=rpa_2,
        rssi=-54,
        source="AA:BB:CC:00:00:11",
        time=t0,
        connectable=True,
        manufacturer_data={},
        service_data={},
        tx_power=-10,
    )
    shared_cb(conn_adv, "adv")
    assert phone_tracker.current_area_id == "living_room"
    # tx_power = -10 dBm -> 1m ref power = -10 - 59 = -69.0 dBm
    assert phone_tracker.detected_ref_power_dbm == -69.0

    # 4) Eddystone-UID (`0000feaa-0000-1000-8000-00805f9b34fb`) frame matching & 0m->1m ref power (-18 - 41 = -59 dBm)
    eddy_payload = bytes([0x00, (-18) & 0xFF]) + bytes.fromhex(eddystone_uid_hex) + b"\x00\x00"
    eddy_adv = SimpleNamespace(
        address="7C:DD:EE:FF:00:99",
        rssi=-57,
        source="AA:BB:CC:00:00:22",
        time=t0 + 0.2,
        connectable=False,
        manufacturer_data={},
        service_data={"0000feaa-0000-1000-8000-00805f9b34fb": eddy_payload},
    )
    shared_cb(eddy_adv, "adv")
    assert eddy_tracker.current_area_id == "kitchen"
    assert eddy_tracker.detected_ref_power_dbm == -59.0

    assert await async_unload_entry(hass, entry) is True
    assert phone_tracker._unsub_target_entity is None
    assert fabric._adv_unsubs == {}


@pytest.mark.asyncio
async def test_first_class_floor_entities_gated_on_configured_floors(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify current_floor entities omit bloat when zero Floors exist, auto-create dynamically, and track Floor + Away."""
    from homeassistant.config_entries import ConfigEntry, ConfigSubentry
    from homeassistant.helpers import floor_registry as fr

    from custom_components.latter import async_setup, async_setup_entry
    from custom_components.latter.const import (
        CONF_ASSIGNED_PERSON,
        CONF_BLE_TARGET_ADDRESS,
        CONF_DEFAULT_AREA,
        CONF_DEVICE_SLUG,
        CONF_ESPHOME_DEVICE_ID,
        CONF_NATIVE_BLE_TRACKING,
        SUBENTRY_BLE_TAG,
        SUBENTRY_DEVICE,
    )
    from custom_components.latter.presence import has_configured_floors

    # 1) Create Areas WITHOUT any floor_id and keep FloorRegistry empty
    area_reg = ar.async_get(hass)
    area_reg.async_create("Living Room", area_id="living_room", floor_id=None)
    area_reg.async_create("Bedroom", area_id="bedroom", floor_id=None)
    _seed_ble_proxies(hass)
    hass.states.async_set("person.sean", "home", {"friendly_name": "Sean"})
    assert has_configured_floors(hass) is False

    esp_dev, mac = make_esphome_device(
        hass,
        slug="pocket_assistant",
        mac="aa:bb:cc:dd:ee:01",
        name="Pocket Assistant",
        area_id="living_room",
        stationary=0,
    )
    await async_setup(hass, {})
    entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="entry_latter_floors",
            domain=DOMAIN,
            title="Latter",
            data={},
            subentries_data=[
                ConfigSubentry(
                    subentry_id="sub_pocket",
                    subentry_type=SUBENTRY_DEVICE,
                    title="Pocket Assistant",
                    unique_id=mac,
                    data={
                        CONF_ESPHOME_DEVICE_ID: esp_dev.id,
                        "mac": mac,
                        CONF_DEVICE_SLUG: "pocket_assistant",
                        CONF_DEFAULT_AREA: "living_room",
                        CONF_ASSIGNED_PERSON: "person.sean",
                        CONF_NATIVE_BLE_TRACKING: True,
                        "ble_auto_switch": True,
                    },
                ),
                ConfigSubentry(
                    subentry_id="sub_watch",
                    subentry_type=SUBENTRY_BLE_TAG,
                    title="Sean Watch",
                    unique_id="tag_watch",
                    data={
                        CONF_DEVICE_SLUG: "sean_watch",
                        CONF_BLE_TARGET_ADDRESS: "33:44:55:66:77:88",
                        CONF_ASSIGNED_PERSON: "person.sean",
                        CONF_NATIVE_BLE_TRACKING: True,
                    },
                ),
            ],
            unique_id=DOMAIN,
        )
    )
    assert await async_setup_entry(hass, entry) is True
    await hass.async_block_till_done()

    # Zero Floors -> zero `current_floor` entity bloat!
    assert hass.states.get("sensor.pocket_assistant_current_area") is not None
    assert hass.states.get("sensor.pocket_assistant_current_floor") is None
    assert hass.states.get("sensor.sean_watch_current_floor") is None
    assert hass.states.get("sensor.sean_current_floor") is None

    # 2) Dynamically create Floors in FloorRegistry & map Areas -> floor sensors auto-create live!
    floor_reg = fr.async_get(hass)
    floor_reg.async_create("Ground Level", floor_id="floor_1", level=1)
    floor_reg.async_create("Upper Level", floor_id="floor_2", level=2)
    area_reg.async_update("living_room", floor_id="floor_1")
    area_reg.async_update("bedroom", floor_id="floor_2")
    await hass.async_block_till_done()

    assert has_configured_floors(hass) is True
    pocket_floor = hass.states.get("sensor.pocket_assistant_current_floor")
    watch_floor = hass.states.get("sensor.sean_watch_current_floor")
    person_floor = hass.states.get("sensor.sean_current_floor")
    assert pocket_floor is not None and pocket_floor.state == "Ground Level"
    assert pocket_floor.attributes["floor_id"] == "floor_1"
    assert watch_floor is not None and watch_floor.state == "Unassigned"
    assert person_floor is not None and person_floor.state == "Ground Level"

    # 3) Move watch to Upstairs `bedroom` via BLE -> watch & person floor sensors update to `Upper Level`!
    watch_coord = entry.runtime_data.coordinators["sub_watch"]
    assert watch_coord._ble_tracker is not None
    t0 = time.monotonic()
    for step in range(3):
        watch_coord._ble_tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:33", -54, t0 + step * 0.2, "Bedroom Proxy"
        )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.sean_watch_current_floor").state == "Upper Level"
    assert hass.states.get("sensor.sean_current_floor").state == "Upper Level"
    watch_dt = hass.states.get("device_tracker.sean_watch_ble_tracker") or hass.states.get(
        "device_tracker.sean_watch"
    )
    assert watch_dt is not None
    assert watch_dt.attributes["floor_id"] == "floor_2"
    assert watch_dt.attributes["floor_name"] == "Upper Level"

    # 4) Both devices transition to `Away` -> `current_floor` sensors report `Away`!
    pocket_coord = entry.runtime_data.coordinators["sub_pocket"]
    hass.states.async_set("binary_sensor.pocket_assistant_ble_radio_active", "on")
    assert pocket_coord._ble_tracker is not None
    pocket_coord._ble_tracker.check_away_timeout(t0 + AWAY_TIMEOUT_SECONDS + 30.0)
    watch_coord._ble_tracker.check_away_timeout(t0 + AWAY_TIMEOUT_SECONDS + 30.0)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.pocket_assistant_current_floor").state == "Away"
    assert hass.states.get("sensor.sean_watch_current_floor").state == "Away"
    assert hass.states.get("sensor.sean_current_floor").state == "Away"

    assert await async_unload_entry(hass, entry) is True
