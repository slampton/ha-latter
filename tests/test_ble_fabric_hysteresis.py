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
    assert any(r["area_id"] == "kitchen" and r["area_name"] == "Kitchen" for r in cal_rows)

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
        3,
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

    # 3) Sticky Area across device wake + immediate single-packet hot-swap to cross-floor bedroom (-85 dBm)
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
            rssi=-85,
            source="AA:BB:CC:00:00:33",
            obs_time=t_wake + WAKE_GAP_SECONDS + 1.0,
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
        ("sensor.pocket_assistant_wifi_signal", "WiFi Signal", "-58"),
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
    hass.states.async_set("sensor.pocket_assistant_wifi_signal", "unavailable")
    tracker.check_away_timeout(t_hold + 60.0)
    assert tracker.is_away is False
    assert coord.get_current_area_and_distance()[0] == "Bedroom"

    # Whereas actively advertising unseen (ble_radio_active == "on") marks Away cleanly
    hass.states.async_set("sensor.pocket_assistant_wifi_signal", "-60")
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
