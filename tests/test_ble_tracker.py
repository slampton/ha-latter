"""Tests for Companion App BLE transmitter discovery, IRK fingerprinting, local BLE tags, and EID exclusion."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.setup import async_setup_component

from custom_components.latter.const import (
    CONF_ASSIGNED_PERSON,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEVICE_SLUG,
    CONF_NATIVE_BLE_TRACKING,
    DOMAIN,
    SUBENTRY_BLE_TAG,
)
from custom_components.latter.presence.ble_discovery import (
    describe_ble_target_model,
    get_discovered_ble_candidates,
)
from custom_components.latter.presence.ble_registry import parse_ibeacon_identity
from custom_components.latter.studio.payload import build_studio_state_payload
from tests.helpers import (
    add_mock_entry,
    ensure_area,
    ensure_floor,
    inject_ble_adv,
    make_ibeacon_service_info,
    make_subentry_dict,
    prepare_latter_dependencies,
    register_device,
    register_entity,
    seed_ble_proxies,
)


async def test_companion_app_ble_transmitter_discovery_dedupe_and_major_minor_isolation(
    hass: Any,
) -> None:
    """Verify HA Companion App 1-click phone discovery, 6x iBeacon dedupe, ref_power seed, Major:Minor isolation, and 0 ms sync."""
    await prepare_latter_dependencies(hass)
    f1 = ensure_floor(hass, "Ground Level", floor_id="floor_1", level=1)
    ensure_area(hass, "Living Room", area_id="living_room", floor_id=f1.floor_id)
    ensure_area(hass, "Kitchen", area_id="kitchen", floor_id=f1.floor_id)
    await seed_ble_proxies(
        hass,
        [
            ("lr_proxy", "aa:bb:cc:00:00:11", "Living Room Proxy", "living_room"),
            ("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen"),
        ],
    )

    # Seed live iBeacon advertisement in Kitchen scanner cache
    phone_uuid = "008fd71e-a43a-4ab4-8e02-f969133f8380"
    t0 = time.monotonic()
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            phone_uuid,
            rssi=-53,
            source="AA:BB:CC:00:00:22",
            obs_time=t0,
            address="5C:11:22:33:A1:B2",
            major=100,
            minor=1,
            tx_power_1m=-56,
        ),
    )

    # 1) Register Android HA Companion App device + `sensor.alexs_pixel_9_ble_transmitter`
    phone_dev = register_device(
        hass,
        config_entry_id="mobile_app_pixel9",
        entry_domain="mobile_app",
        identifiers={("mobile_app", "pixel_9_pro_alex")},
        name="Alex's Pixel 9",
        manufacturer="Latter",
        model="Pixel 9 Pro",
    )
    emitter_eid = "sensor.alexs_pixel_9_ble_transmitter"
    register_entity(
        hass,
        emitter_eid,
        platform="mobile_app",
        config_entry_id="mobile_app_pixel9",
        device_id=phone_dev.id,
        unique_id="pixel_9_pro_alex_ble_emitter",
        original_name="BLE Transmitter",
    )
    hass.states.async_set(
        emitter_eid,
        "Transmitting",
        {
            "friendly_name": "Alex's Pixel 9 BLE Transmitter",
            "id": f"{phone_uuid}-100-1",
            "Measured power": -56,
        },
    )

    # Register 3 unconsolidated rotating-MAC `ibeacon` devices (device_tracker + estimated_distance = 6 entities)
    for idx, rot_hex in enumerate(("A1B2", "C3D4", "E5F6"), start=1):
        ib_dev = register_device(
            hass,
            config_entry_id="entry_ibeacon",
            entry_domain="ibeacon",
            identifiers={("ibeacon", f"{phone_uuid}_100_1_{rot_hex}")},
            name=f"Beacon {rot_hex}",
            manufacturer="Latter",
        )
        dt_eid = f"device_tracker.beacon_{rot_hex.lower()}"
        dist_eid = f"sensor.beacon_{rot_hex.lower()}_estimated_distance"
        register_entity(
            hass,
            dt_eid,
            platform="ibeacon",
            config_entry_id="entry_ibeacon",
            device_id=ib_dev.id,
            unique_id=f"{phone_uuid}_100_1_{rot_hex}_tracker",
            original_name=f"Beacon {rot_hex}",
        )
        register_entity(
            hass,
            dist_eid,
            platform="ibeacon",
            config_entry_id="entry_ibeacon",
            device_id=ib_dev.id,
            unique_id=f"{phone_uuid}_100_1_{rot_hex}_distance",
            original_name=f"Beacon {rot_hex} Estimated Distance",
        )
        hass.states.async_set(
            dt_eid,
            "home",
            {
                "friendly_name": f"Beacon {rot_hex}",
                "uuid": phone_uuid,
                "major": 100,
                "minor": 1,
                "rssi": -60 - idx,
                "source": "AA:BB:CC:00:00:22",
            },
        )
        hass.states.async_set(
            dist_eid,
            "1.4",
            {
                "friendly_name": f"Beacon {rot_hex} Estimated Distance",
                "uuid": phone_uuid,
                "major": 100,
                "minor": 1,
            },
        )

    # All 7 entities (+ live scanner advertisement) collapse into 1 single Companion App candidate!
    discovered = get_discovered_ble_candidates(hass, set(), set())
    assert len(discovered) == 1
    cand = discovered[0]
    assert cand["title"] == "Alex's Pixel 9"
    assert cand["target_address"] == emitter_eid
    assert "HA Companion App" in cand["kind"]
    assert phone_uuid in cand["kind"]
    assert "100:1" in cand["kind"]
    assert cand["rssi"] == -53
    assert cand["area_name"] == "Kitchen"
    assert cand["scanner"] == "Kitchen Proxy (AA:BB:CC:00:00:22)"

    # Also verify standalone 3x2 rotating-MAC `ibeacon` dedupe when NOT covered by a Companion App phone
    tag_uuid = "e2c56db5-dffb-48d2-b060-d0f5a71096e1"
    for rot_hex, rssi_v in (("1A2B", -68), ("3C4D", -59)):
        s_dev = register_device(
            hass,
            config_entry_id="entry_ibeacon",
            entry_domain="ibeacon",
            identifiers={("ibeacon", f"{tag_uuid}_1_9_{rot_hex}")},
            name=f"Blue Charm Keys {rot_hex}",
            manufacturer="Latter",
        )
        for dom, sfx in (("device_tracker", ""), ("sensor", "_estimated_distance")):
            s_eid = f"{dom}.blue_charm_keys_{rot_hex.lower()}{sfx}"
            register_entity(
                hass,
                s_eid,
                platform="ibeacon",
                config_entry_id="entry_ibeacon",
                device_id=s_dev.id,
                unique_id=f"{tag_uuid}_1_9_{rot_hex}{sfx}",
            )
            hass.states.async_set(
                s_eid,
                "home" if dom == "device_tracker" else "1.2",
                {
                    "friendly_name": f"Blue Charm Keys {rot_hex}"
                    + (" Estimated Distance" if sfx else ""),
                    "uuid": tag_uuid,
                    "major": 1,
                    "minor": 9,
                    "rssi": rssi_v,
                },
            )

    disc_with_tag = get_discovered_ble_candidates(hass, set(), {emitter_eid})
    assert len(disc_with_tag) == 1
    assert disc_with_tag[0]["title"] == "Blue Charm Keys"
    assert disc_with_tag[0]["target_address"].startswith("device_tracker.")
    assert "iBeacon Tag" in disc_with_tag[0]["kind"]

    # 2) Adopt `sensor.alexs_pixel_9_ble_transmitter` as a BLE tag & verify model label, ref_power, and Major:Minor isolation
    hass.states.async_set("person.alex", "home", {"friendly_name": "Alex"})
    assert await async_setup_component(hass, DOMAIN, {}) is True
    entry = add_mock_entry(
        hass,
        entry_id="entry_latter_comp",
        domain=DOMAIN,
        title="Latter",
        data={},
        subentries_data=[
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "alexs_pixel_9",
                    CONF_BLE_TARGET_ADDRESS: emitter_eid,
                    CONF_ASSIGNED_PERSON: "person.alex",
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_pixel9",
                subentry_type=SUBENTRY_BLE_TAG,
                title="Alex's Pixel 9",
                unique_id=f"tag_{emitter_eid}",
            )
        ],
        unique_id=DOMAIN,
    )
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    assert describe_ble_target_model(hass, emitter_eid) == "Pixel 9 Pro (HA Companion App)"
    coord = entry.runtime_data.coordinators["sub_pixel9"]
    studio_payload = build_studio_state_payload(hass, coord)
    sys_dev_row = next(
        d for d in studio_payload["system_devices"] if d["subentry_id"] == "sub_pixel9"
    )
    assert sys_dev_row["model_label"] == "Pixel 9 Pro (HA Companion App)"

    tracker = coord.ble_tracker
    assert tracker is not None
    assert tracker.detected_ref_power_dbm == -56.0
    assert tracker.effective_ref_power_dbm == -56.0
    assert tracker.current_area_id == "kitchen"

    # Packet from ANOTHER person's phone sharing the same UUID (`major=100, minor=2`) in Living Room MUST be REJECTED!
    t1 = t0 + 6.0
    tracker._last_switch_monotonic = t0 - 20.0
    for step in range(4):
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                phone_uuid,
                rssi=-38,
                source="AA:BB:CC:00:00:11",
                obs_time=t1 + step * 0.3,
                address="6E:AA:BB:CC:DD:02",
                major=100,
                minor=2,
            ),
        )
    hass.bus.async_fire(
        "esphome.ibeacon_seen",
        {
            "source": "AA:BB:CC:00:00:11",
            "uuid": phone_uuid,
            "major": 100,
            "minor": 2,
            "rssi": -36,
            "address": "6E:AA:BB:CC:DD:02",
        },
    )
    await hass.async_block_till_done()
    assert tracker.current_area_id == "kitchen"

    # Packet matching Alex's `UUID + major=100 + minor=1` in Living Room switches cleanly!
    for step in range(4):
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                phone_uuid,
                rssi=-42,
                source="AA:BB:CC:00:00:11",
                obs_time=t1 + 2.0 + step * 0.3,
                address="7A:11:22:33:44:01",
                major=100,
                minor=1,
                tx_power_1m=-56,
            ),
        )
    assert tracker.current_area_id == "living_room"
    assert tracker.detected_ref_power_dbm == -56.0

    # 3) `major=0, minor=0` works when configured AND updates in 0 ms via `state_changed`!
    assert parse_ibeacon_identity(f"{phone_uuid}-0-0") == (
        phone_uuid.replace("-", ""),
        0,
        0,
    )
    hass.states.async_set(
        emitter_eid,
        "Transmitting",
        {
            "friendly_name": "Alex's Pixel 9 BLE Transmitter",
            "id": f"{phone_uuid}-0-0",
            "Measured power": -54,
        },
    )
    await hass.async_block_till_done()
    assert tracker._resolve_beacon_major_minor() == (0, 0)
    assert tracker.detected_ref_power_dbm == -54.0

    # Old `100:1` or another `0:1` phone in Kitchen is now REJECTED immediately
    tracker._last_switch_monotonic = t0 - 30.0
    t2 = t1 + 10.0
    for idx_m, (bad_maj, bad_min) in enumerate(((100, 1), (0, 1))):
        for step in range(3):
            inject_ble_adv(
                hass,
                make_ibeacon_service_info(
                    phone_uuid,
                    rssi=-37,
                    source="AA:BB:CC:00:00:22",
                    obs_time=t2 + idx_m * 1.0 + step * 0.2,
                    address="7B:99:88:77:66:55",
                    major=bad_maj,
                    minor=bad_min,
                    tx_power_1m=-54,
                ),
            )
    assert tracker.current_area_id == "living_room"

    # Matching `major=0, minor=0` in Kitchen switches cleanly!
    for step in range(4):
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                phone_uuid,
                rssi=-40,
                source="AA:BB:CC:00:00:22",
                obs_time=t2 + 3.0 + step * 0.3,
                address="7C:55:44:33:22:11",
                major=0,
                minor=0,
                tx_power_1m=-54,
            ),
        )
    assert tracker.current_area_id == "kitchen"

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_private_ble_device_irk_vendor_and_device_type_fingerprinting(
    hass: Any,
) -> None:
    """Verify Private BLE Device (IRK) live vendor/device-type classification and device_id deduplication."""
    await prepare_latter_dependencies(hass)
    ensure_area(hass, "Living Room", area_id="living_room")
    await seed_ble_proxies(
        hass,
        [("lr_proxy", "aa:bb:cc:00:00:11", "Living Room Proxy", "living_room")],
    )

    irk_cases: list[
        tuple[str, str, str, dict[int, bytes], dict[str, bytes], tuple[str, ...], int, str]
    ] = [
        (
            "sam_iphone",
            "Sam's iPhone",
            "51:AA:BB:CC:DD:01",
            {0x004C: bytes([0x10, 0x05, 0x0B, 0x1C, 0xAA])},
            {},
            (),
            -52,
            "Apple iPhone, Watch, or iPad (Private BLE)",
        ),
        (
            "alex_airpods",
            "Alex AirPods Pro",
            "52:AA:BB:CC:DD:02",
            {0x004C: bytes([0x07, 0x19, 0x01, 0x0E, 0x20])},
            {},
            (),
            -61,
            "Apple AirPods or Beats (Private BLE)",
        ),
        (
            "galaxy_watch",
            "Galaxy Watch",
            "53:AA:BB:CC:DD:03",
            {0x0075: bytes([0x42, 0x04, 0x01, 0x80])},
            {},
            (),
            -58,
            "Samsung Galaxy Phone or Watch (Private BLE)",
        ),
        (
            "guest_pixel",
            "Guest Pixel",
            "54:AA:BB:CC:DD:04",
            {0x00E0: bytes([0x01, 0x02, 0x03])},
            {},
            (),
            -64,
            "Android / Pixel Phone (Private BLE)",
        ),
        (
            "fastpair_phone",
            "FastPair Android",
            "55:AA:BB:CC:DD:05",
            {},
            {"0000fe2c-0000-1000-8000-00805f9b34fb": b"\x00\x11\x22"},
            ("0000fe2c-0000-1000-8000-00805f9b34fb",),
            -66,
            "Android / Pixel Phone (Private BLE)",
        ),
    ]

    for slug, title, rpa_mac, mfg_data, svc_data, svc_uuids, rssi_val, _expected in irk_cases:
        p_dev = register_device(
            hass,
            config_entry_id=f"pble_{slug}",
            entry_domain="private_ble_device",
            identifiers={("private_ble_device", f"irk_{slug}")},
            name=title,
            manufacturer="Latter",
        )
        dt_eid = f"device_tracker.{slug}"
        dist_eid = f"sensor.{slug}_estimated_distance"
        register_entity(
            hass,
            dt_eid,
            platform="private_ble_device",
            config_entry_id=f"pble_{slug}",
            device_id=p_dev.id,
            unique_id=f"irk_{slug}_tracker",
            original_name=title,
        )
        # Register companion estimated_distance sensor on same device_id to verify 2->1 dedupe
        register_entity(
            hass,
            dist_eid,
            platform="private_ble_device",
            config_entry_id=f"pble_{slug}",
            device_id=p_dev.id,
            unique_id=f"irk_{slug}_estimated_distance",
            original_name=f"{title} Estimated Distance",
        )
        hass.states.async_set(
            dt_eid,
            "home",
            {"friendly_name": title, "current_address": rpa_mac},
        )
        hass.states.async_set(
            dist_eid,
            "1.8",
            {"friendly_name": f"{title} Estimated Distance"},
        )
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                "",
                rssi=rssi_val,
                source="AA:BB:CC:00:00:11",
                address=rpa_mac,
                service_data=svc_data,
                service_uuids=list(svc_uuids),
                extra_mfg=mfg_data,
            ),
        )

    candidates = get_discovered_ble_candidates(hass, set(), set())
    assert len(candidates) == len(irk_cases)
    by_target = {c["target_address"]: c for c in candidates}

    for slug, title, _rpa_mac, _mfg, _svc, _uuids, rssi_val, expected_kind in irk_cases:
        dt_eid = f"device_tracker.{slug}"
        assert dt_eid in by_target
        row = by_target[dt_eid]
        assert row["title"] == title
        assert row["kind"] == expected_kind
        assert row["rssi"] == rssi_val
        assert row["area_name"] == "Living Room"
        assert describe_ble_target_model(hass, dt_eid) == expected_kind


async def test_local_ble_tag_fingerprinting_and_cloud_rolling_eid_exclusion(
    hass: Any,
) -> None:
    """Verify Tile, iTag, Shelly BLU, and RuuviTag classification while excluding Google FMDN & Apple Find My rolling EIDs."""
    await prepare_latter_dependencies(hass)
    ensure_area(hass, "Kitchen", area_id="kitchen")
    await seed_ble_proxies(
        hass,
        [("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen")],
    )

    ambient_packets: list[
        tuple[str, int, str, dict[int, bytes], dict[str, bytes], list[str]]
    ] = [
        # Supported local BLE tags (including unnamed Tile, Shelly BLU, and RuuviTag)
        (
            "DC:11:22:33:E4:12",
            -55,
            "",
            {},
            {"0000feed-0000-1000-8000-00805f9b34fb": b"\x02\x00\xaa\xbb"},
            ["0000feed-0000-1000-8000-00805f9b34fb"],
        ),
        (
            "FF:EE:DD:CC:BB:09",
            -62,
            "iTAG   ",
            {},
            {},
            ["0000ffe0-0000-1000-8000-00805f9b34fb"],
        ),
        (
            "38:39:8F:AA:BB:77",
            -58,
            "SBBT-002C",
            {0x0B9A: b"\x01\x00"},
            {"0000fcd2-0000-1000-8000-00805f9b34fb": b"\x40\x01\x64\x3a\x01"},
            [],
        ),
        (
            "CB:B8:33:4C:88:4F",
            -65,
            "",
            {0x0499: b"\x05\x12\xfc\x53\x94\xc3\x7c"},
            {},
            [],
        ),
        # Excluded cloud Find-network rolling-EID tags:
        # 1) Google FMDN / Find Hub rolling EID (`0xFEAA` frame `0x40` — Moto Tag / Pebblebee FMDN / Chipolo ONE Point)
        (
            "4A:91:00:E1:D2:40",
            -47,
            "",
            {},
            {"0000feaa-0000-1000-8000-00805f9b34fb": bytes([0x40]) + b"\xab" * 20},
            ["0000feaa-0000-1000-8000-00805f9b34fb"],
        ),
        # 2) Separated Apple Find My / AirTag (`0x004C` type `0x12`, unnamed)
        (
            "7E:22:44:66:88:12",
            -45,
            "",
            {0x004C: bytes([0x12, 0x19, 0x10]) + b"\xcd" * 24},
            {},
            [],
        ),
    ]
    for addr, rssi_val, name_val, mfg_val, svc_val, uuids_val in ambient_packets:
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                "",
                rssi=rssi_val,
                source="AA:BB:CC:00:00:22",
                address=addr,
                local_name=name_val,
                service_data=svc_val,
                service_uuids=uuids_val,
                extra_mfg=mfg_val,
            ),
        )

    candidates = get_discovered_ble_candidates(hass, set(), set())
    by_addr = {c["target_address"]: c for c in candidates}

    # Cloud rolling-EID frames MUST NOT appear in Studio discovery
    assert "4A:91:00:E1:D2:40" not in by_addr
    assert "7E:22:44:66:88:12" not in by_addr
    assert len(candidates) == 4

    # Local tags classified with friendly kinds and fallback titles
    tile_row = by_addr["DC:11:22:33:E4:12"]
    assert tile_row["kind"] == "Tile Tracker"
    assert tile_row["title"] == "Tile Tracker E4:12"
    assert tile_row["area_name"] == "Kitchen"
    assert describe_ble_target_model(hass, "DC:11:22:33:E4:12") == "Tile Tracker"

    itag_row = by_addr["FF:EE:DD:CC:BB:09"]
    assert itag_row["kind"] == "iTag Keychain Tag"
    assert itag_row["title"] == "iTAG"
    assert describe_ble_target_model(hass, "FF:EE:DD:CC:BB:09") == "iTag Keychain Tag"

    shelly_row = by_addr["38:39:8F:AA:BB:77"]
    assert shelly_row["kind"] == "Shelly BLU Tag (BTHome v2)"
    assert shelly_row["title"] == "SBBT-002C"
    assert describe_ble_target_model(hass, "38:39:8F:AA:BB:77") == "Shelly BLU Tag (BTHome v2)"

    ruuvi_row = by_addr["CB:B8:33:4C:88:4F"]
    assert ruuvi_row["kind"] == "RuuviTag Beacon"
    assert ruuvi_row["title"] == "RuuviTag 88:4F"
    assert describe_ble_target_model(hass, "CB:B8:33:4C:88:4F") == "RuuviTag Beacon"
