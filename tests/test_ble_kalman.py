"""Tests for Rayleigh multipath fast-override gate, multi-scanner corroboration, vector signatures, and ultraLow phone calibration."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.setup import async_setup_component

from custom_components.latter.const import (
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AREA_SIGNATURES,
    CONF_BLE_CATEGORY,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    CONF_NATIVE_BLE_TRACKING,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    STUDIO_REV,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
)
from custom_components.latter.presence.ble_discovery import (
    classify_ble_target_category,
    inspect_companion_ble_transmitter,
)
from custom_components.latter.presence.ble_fabric import get_ble_fabric
from custom_components.latter.presence.ble_math import (
    CORROBORATION_BONUS_DB,
    resolve_companion_tx_ref_power_dbm,
)
from custom_components.latter.presence.ble_registry import (
    APPLE_COMPANY_ID,
    get_area_signatures_summary,
    get_ble_proxy_area_ids,
)
from custom_components.latter.studio.payload import build_studio_state_payload
from tests.helpers import (
    add_mock_entry,
    call_ws,
    ensure_area,
    ensure_floor,
    flush_debouncers,
    inject_ble_adv,
    make_ibeacon_service_info,
    make_subentry_dict,
    make_ws_connection,
    prepare_latter_dependencies,
    register_device,
    register_entity,
    seed_ble_proxies,
)


async def test_rayleigh_multipath_spike_fast_override_gate_and_velocity_clamping(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify 3-sample median, >=2 packet FAST_OVERRIDE_DB gate, and max_velocity_mps damp multipath & body fades."""
    await seed_ble_proxies(hass)
    entry, _sys_obj, coord = await setup_latter_hub(hass, stationary=0)
    tracker = coord.ble_tracker
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

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_multi_scanner_same_area_aggregation_never_averages_down(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify two scanners in the same Area track separately, take max + corroboration bonus, and never average down."""
    await seed_ble_proxies(
        hass,
        [
            ("lr_proxy", "aa:bb:cc:00:00:11", "Living Room Proxy", "living_room"),
            ("lr_south", "aa:bb:cc:00:00:19", "Living Room South", "living_room"),
            ("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen"),
            ("bed_proxy", "aa:bb:cc:00:00:33", "Bedroom Proxy", "bedroom"),
        ],
    )

    entry, _sys_obj, coord = await setup_latter_hub(hass, stationary=0)
    tracker = coord.ble_tracker
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

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_multi_scanner_vector_signature_trilateration_and_proxyless_area(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify multi-scanner signature capture & cross-device ref_power normalization in a proxy-less Area."""
    await seed_ble_proxies(hass)
    f1 = ensure_floor(hass, "Ground Level", floor_id="floor_1", level=1)
    # Create a proxy-less Area (`guest_bath`) surrounded by living_room, kitchen, and bedroom proxies
    ensure_area(hass, "Guest Bath", area_id="guest_bath", floor_id=f1.floor_id)
    assert "guest_bath" not in get_ble_proxy_area_ids(hass)

    entry, sys_obj, coord = await setup_latter_hub(
        hass,
        with_ble_tag=True,
        stationary=0,
    )
    tag_coord = sys_obj.coordinators["sub_tag"]
    assert coord.ble_tracker is not None
    assert tag_coord.ble_tracker is not None

    # 1) Stand in `guest_bath` with handheld (`ble_ref_power` default -59 dBm @ 1m) and collect 3-scanner vector
    t0 = time.monotonic()
    for step in range(5):
        ts = t0 + step * 0.3
        coord.ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:11", -68, ts, "Living Room Proxy")
        coord.ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:22", -66, ts + 0.05, "Kitchen Proxy")
        coord.ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:33", -74, ts + 0.10, "Bedroom Proxy")

    # Capture signature via real Studio WebSocket command
    conn = make_ws_connection(hass)
    await call_ws(
        hass,
        conn,
        1,
        "latter/system/command",
        command="capture_ble_area_signature",
        payload={"area_id": "guest_bath", "survey_subentry_id": coord.subentry_id},
        studio_rev=STUDIO_REV,
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
    assert tag_coord.ble_tracker.effective_ref_power_dbm == -49.0

    # Feed raw RSSI +10 dB louder at the exact same physical spot in `guest_bath`:
    # (-58, -56, -64 raw -> normalized to -68, -66, -74 @ -59 dBm!)
    t1 = time.monotonic() + 1.0
    for step in range(4):
        ts = t1 + step * 0.3
        tag_coord.ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:11", -58, ts, "Living Room Proxy")
        tag_coord.ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:22", -56, ts + 0.05, "Kitchen Proxy")
        tag_coord.ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:33", -64, ts + 0.10, "Bedroom Proxy")

    assert tag_coord.ble_tracker.current_area_id == "guest_bath"
    assert tag_coord.ble_tracker.match_method == "signature"
    assert tag_coord.active_area_id == "guest_bath"
    await flush_debouncers(hass)
    tag_area_st = hass.states.get("sensor.keys_tag_current_area")
    assert tag_area_st is not None
    assert tag_area_st.state == "Guest Bath"
    assert tag_area_st.attributes["match_method"] == "signature"

    # 3) Walk right up to Living Room proxy (-36 dBm raw -> -46 dBm normalized) -> distance model wins cleanly!
    tag_coord.ble_tracker._last_switch_monotonic = t1 - 20.0
    t2 = t1 + 5.0
    for step in range(4):
        ts = t2 + step * 0.3
        tag_coord.ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:11", -36, ts, "Living Room Proxy")
        tag_coord.ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:22", -66, ts + 0.05, "Kitchen Proxy")
        tag_coord.ble_tracker._ingest_proxy_observation("AA:BB:CC:00:00:33", -74, ts + 0.10, "Bedroom Proxy")

    assert tag_coord.ble_tracker.current_area_id == "living_room"
    assert tag_coord.ble_tracker.match_method == "distance"

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_companion_app_ultralow_phone_nonconnectable_matcher_and_phone_category(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify connectable=False matcher, Companion App ultraLow (-81 dBm) compensation, single-scanner signature guard, and Phone category."""
    assert resolve_companion_tx_ref_power_dbm(-59, "ultraLow") == -81.0
    assert resolve_companion_tx_ref_power_dbm(None, "low") == -75.0
    assert resolve_companion_tx_ref_power_dbm(-59, "medium") == -67.0
    assert resolve_companion_tx_ref_power_dbm(-59, "high") == -59.0
    # Custom calibrated Measured power is preserved over tier defaults
    assert resolve_companion_tx_ref_power_dbm(-64, "ultraLow") == -64.0

    await prepare_latter_dependencies(hass)
    ensure_area(hass, "Garage", area_id="garage")
    ensure_area(hass, "Office", area_id="office")
    await seed_ble_proxies(
        hass,
        [
            ("garage_proxy", "a8:42:e3:21:af:e2", "garage-ep1", "garage"),
            ("office_proxy", "a8:42:e3:21:af:f9", "office-ep1", "office"),
        ],
    )

    phone_dev = register_device(
        hass,
        config_entry_id="mobile_app_pixel",
        entry_domain="mobile_app",
        identifiers={("mobile_app", "pixel_10_pro_xl")},
        name="Pixel 10 Pro XL",
        manufacturer="Latter",
        model="Pixel 10 Pro XL",
    )
    tx_entity = "sensor.pixel_10_pro_xl_ble_transmitter"
    register_entity(
        hass,
        tx_entity,
        platform="mobile_app",
        config_entry_id="mobile_app_pixel",
        device_id=phone_dev.id,
        unique_id="pixel_10_pro_xl_ble_emitter",
        original_name="BLE Transmitter",
    )
    phone_uuid = "1f8a61b7-424a-4df4-8527-14dd55ca0bb6"
    hass.states.async_set(
        tx_entity,
        "Transmitting",
        {
            "id": f"{phone_uuid}_100_40004",
            "Transmitting power": "ultraLow",
            "Advertise mode": "lowPower",
            "Measured power": -59,
        },
    )
    hass.states.async_set("person.alex", "home", {"friendly_name": "Alex"})

    # Private BLE classification checks (iPhone -> phone, AirPods -> ble_tag)
    register_entity(
        hass,
        "device_tracker.private_ble_iphone",
        platform="private_ble_device",
        config_entry_id="pble_iphone",
        unique_id="irk_iphone",
        original_name="Alex iPhone",
    )
    hass.states.async_set(
        "device_tracker.private_ble_iphone",
        "home",
        {"current_address": "51:AA:BB:CC:DD:01"},
    )
    register_entity(
        hass,
        "device_tracker.private_ble_airpods",
        platform="private_ble_device",
        config_entry_id="pble_airpods",
        unique_id="irk_airpods",
        original_name="AirPods Pro",
    )
    hass.states.async_set(
        "device_tracker.private_ble_airpods",
        "home",
        {"current_address": "52:AA:BB:CC:DD:02"},
    )
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            "",
            rssi=-61,
            source="A8:42:E3:21:AF:E2",
            address="51:AA:BB:CC:DD:01",
            extra_mfg={APPLE_COMPANY_ID: b"\x10\x05\x01\x18\xaa\xbb\xcc"},
        ),
    )
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            "",
            rssi=-58,
            source="A8:42:E3:21:AF:E2",
            address="52:AA:BB:CC:DD:02",
            extra_mfg={APPLE_COMPANY_ID: b"\x07\x19\x01\x0e\x20\x75\xaa\xb0"},
        ),
    )
    assert classify_ble_target_category(hass, tx_entity) == "phone"
    assert classify_ble_target_category(hass, "device_tracker.private_ble_iphone") == "phone"
    assert classify_ble_target_category(hass, "device_tracker.private_ble_airpods") == "ble_tag"
    assert classify_ble_target_category(hass, "DC:11:22:33:E4:12") == "ble_tag"
    assert classify_ble_target_category(hass, "DC:11:22:33:E4:12", "phone") == "phone"

    esp_dev, mac = make_esphome_device(
        hass, slug="desk_assistant", name="Desk Assistant", area_id="office", stationary=1
    )
    assert await async_setup_component(hass, DOMAIN, {}) is True
    entry = add_mock_entry(
        hass,
        entry_id="latter_hub_phone",
        domain=DOMAIN,
        title="Latter",
        data={},
        subentries_data=[
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "desk_assistant",
                    CONF_ESPHOME_DEVICE_ID: esp_dev.id,
                    "mac": mac,
                    CONF_NATIVE_BLE_TRACKING: False,
                },
                subentry_id="sub_desk",
                subentry_type=SUBENTRY_DEVICE,
                title="Desk Assistant",
                unique_id=mac,
            ),
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "pixel_10_pro_xl",
                    CONF_BLE_TARGET_ADDRESS: tx_entity,
                    CONF_BLE_CATEGORY: "auto",
                    CONF_ASSIGNED_PERSON: "person.alex",
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_pixel_phone",
                subentry_type=SUBENTRY_BLE_TAG,
                title="Pixel 10 Pro XL",
                unique_id="latter_ble_pixel_10_pro_xl",
            ),
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "keys_tile",
                    CONF_BLE_TARGET_ADDRESS: "DC:11:22:33:E4:12",
                    CONF_BLE_CATEGORY: "auto",
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_tile_keys",
                subentry_type=SUBENTRY_BLE_TAG,
                title="Keys Tile",
                unique_id="latter_ble_keys_tile",
            ),
        ],
        unique_id=DOMAIN,
    )
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    # 1) Shared Bluetooth callback matcher registered on real HomeAssistantBluetoothManager (`connectable=False`)
    assert get_ble_fabric(hass)._unsub_ble is not None

    # Configure a multi-scanner Area signature on Garage (where secondary scanners would be missing at ultraLow TX power)
    phone_coord = entry.runtime_data.coordinators["sub_pixel_phone"]
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_BLE_AREA_SIGNATURES] = {
        "garage": {
            "scanners": {
                "A8:42:E3:21:AF:E2": {"mean": -69.5, "std": 3.5, "n": 10},
                "A8:42:E3:21:AF:F9": {"mean": -72.0, "std": 3.5, "n": 10},
                "11:22:33:44:55:66": {"mean": -74.0, "std": 3.5, "n": 10},
            },
            "captured_at": "2026-11-17T20:00:00Z",
            "sample_count": 30,
        }
    }
    await phone_coord.async_on_global_config_updated({CONF_BLE_AREA_SIGNATURES})

    tracker = phone_coord.ble_tracker
    assert tracker is not None
    assert tracker.effective_ref_power_dbm == -81.0

    # 2) Rotating-MAC non-connectable iBeacon advertisement at -91 dBm raw with byte-22 = -59 arrives on Garage proxy
    t_now = time.monotonic()
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            phone_uuid,
            rssi=-91,
            source="A8:42:E3:21:AF:E2",
            obs_time=t_now,
            address="49:C9:FA:11:24:F1",
            major=100,
            minor=40004,
            tx_power_1m=-59,
            connectable=False,
        ),
    )

    # Byte-22 (-59) MUST NOT overwrite Companion App ultraLow (-81 dBm); -91 dBm raw normalizes to -69 dBm (~2.8 m) in Garage!
    assert tracker.effective_ref_power_dbm == -81.0
    assert tracker.packets_seen == 1
    assert tracker.current_area_id == "garage"
    assert tracker.winning_rssi == -69
    assert tracker.winning_raw_rssi == -91
    assert phone_coord.get_current_area_and_distance()[0] == "Garage"

    # 3) Studio payload exposes Phone vs. BLE Tag categories, "Garage (Roaming)", and Companion App transmitter telemetry
    state_payload = build_studio_state_payload(hass, phone_coord)
    by_sub = {d["subentry_id"]: d for d in state_payload["system_devices"]}
    pixel_entry = by_sub["sub_pixel_phone"]
    assert pixel_entry["ble_category"] == "phone"
    assert pixel_entry["device_group_name"] == "Phones"
    assert pixel_entry["area_label"] == "Garage (Roaming)"
    assert pixel_entry["status_label"] == "Online"
    assert pixel_entry["active_area_name"] == "Garage"

    tile_entry = by_sub["sub_tile_keys"]
    assert tile_entry["ble_category"] == "ble_tag"
    assert tile_entry["device_group_name"] == "BLE tags"
    assert tile_entry["area_label"] == "Roaming"
    assert tile_entry["status_label"] == "Scanning"

    assert state_payload["config"]["ble_category"] == "auto"
    assert state_payload["config"]["effective_ble_category"] == "phone"
    assert state_payload["live"]["ble_detected_ref_power"] == -81
    assert state_payload["live"]["ble_transmitter_status"] == {
        "state": "Transmitting",
        "tx_power": "ultraLow",
        "advertise_mode": "lowPower",
    }

    # 4) Turning Bluetooth off in Companion App surfaces immediately in inspect_companion_ble_transmitter
    hass.states.async_set(
        tx_entity,
        "Bluetooth is turned off",
        {"Transmitting power": "ultraLow", "Advertise mode": "lowPower"},
    )
    await hass.async_block_till_done()
    tx_off = inspect_companion_ble_transmitter(hass, tx_entity)
    assert tx_off is not None
    assert tx_off["state"] == "Bluetooth is turned off"

    # 5) Explicit Device Category override via save_device_config switches Phone <-> BLE Tag
    conn = make_ws_connection(hass)
    await call_ws(
        hass,
        conn,
        99,
        "latter/device/command",
        subentry_id="sub_pixel_phone",
        command="save_device_config",
        payload={"config": {"ble_category": "ble_tag"}},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert phone_coord.configured_ble_category == "ble_tag"
    assert phone_coord.effective_ble_category == "ble_tag"

    assert await hass.config_entries.async_unload(entry.entry_id) is True
