"""Tests for Companion App BLE transmitter discovery, IRK fingerprinting, local BLE tags, and EID exclusion."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.setup import async_setup_component

from custom_components.latter.const import (
    CONF_ASSIGNED_PERSON,
    CONF_BLE_BEACON_UUID,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    CONF_NATIVE_BLE_TRACKING,
    CONF_SYSTEM_BLE_UUID,
    DEFAULT_BLE_BEACON_UUID,
    DOMAIN,
    MIN_FIRMWARE_CORE_REV,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
    derive_device_beacon_uuid,
)
from custom_components.latter.hub_registry import get_global_config
from custom_components.latter.presence.ble_discovery import (
    describe_ble_target_model,
    get_discovered_ble_candidates,
)
from custom_components.latter.presence.ble_fabric import get_ble_fabric
from custom_components.latter.presence.ble_registry import mac_to_int, parse_ibeacon_identity
from custom_components.latter.presence.ble_tracker import LatterNativeBleTracker
from custom_components.latter.studio.device_commands import _cmd_save_device_config
from custom_components.latter.studio.payload import build_studio_state_payload
from tests.helpers import (
    add_mock_entry,
    ensure_area,
    ensure_floor,
    inject_ble_adv,
    make_ibeacon_service_info,
    make_subentry_dict,
    mock_service,
    prepare_latter_dependencies,
    register_device,
    register_entity,
    seed_ble_proxies,
    seed_device_hello_manifest,
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


async def test_derive_device_beacon_uuid_rotation_and_override_precedence(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify deterministic per-Device UUIDv5 derivation, rotation, fallbacks, and explicit override precedence."""
    sys_uuid_a = "11111111-2222-4333-8444-555555555555"
    sys_uuid_b = "99999999-8888-4777-8666-555555555555"

    # Pure helper: determinism, case/whitespace normalization, distinctness, rotation, and fallbacks
    d1 = derive_device_beacon_uuid(sys_uuid_a, "AA:BB:CC:DD:EE:01")
    d1_again = derive_device_beacon_uuid(sys_uuid_a.lower(), "  aa:bb:cc:dd:ee:01 ")
    d2 = derive_device_beacon_uuid(sys_uuid_a, "AA:BB:CC:DD:EE:02")
    d1_rot = derive_device_beacon_uuid(sys_uuid_b, "AA:BB:CC:DD:EE:01")
    assert d1 == d1_again
    assert d1 == d1.upper()
    assert len(d1) == 36
    assert d1 != sys_uuid_a
    assert d1 != d2
    assert d1_rot != d1
    assert derive_device_beacon_uuid("", "aa:bb:cc:dd:ee:01") == DEFAULT_BLE_BEACON_UUID
    assert (
        derive_device_beacon_uuid(DEFAULT_BLE_BEACON_UUID, "aa:bb:cc:dd:ee:01")
        == DEFAULT_BLE_BEACON_UUID
    )
    assert (
        derive_device_beacon_uuid(
            DEFAULT_BLE_BEACON_UUID.lower().replace("-", ""), "aa:bb:cc:dd:ee:01"
        )
        == DEFAULT_BLE_BEACON_UUID
    )
    assert derive_device_beacon_uuid("not-a-valid-uuid", "aa:bb:cc:dd:ee:01") == "NOT-A-VALID-UUID"
    assert derive_device_beacon_uuid(sys_uuid_a, "   ") == sys_uuid_a.upper()

    # End-to-end hub with 2 identical Pocket Assistants + 1 explicit override + 1 BLE tag
    await prepare_latter_dependencies(hass)
    ensure_area(hass, "Living Room", area_id="living_room")
    esp_1, mac_1 = make_esphome_device(
        hass, slug="pocket_one", mac="aa:bb:cc:dd:ee:11", name="Pocket One", area_id="living_room"
    )
    esp_2, mac_2 = make_esphome_device(
        hass, slug="pocket_two", mac="aa:bb:cc:dd:ee:22", name="Pocket Two", area_id="living_room"
    )
    esp_3, mac_3 = make_esphome_device(
        hass,
        slug="pocket_custom",
        mac="aa:bb:cc:dd:ee:33",
        name="Pocket Custom",
        area_id="living_room",
    )
    explicit_override_uuid = "AAAAAAAA-BBBB-4CCC-8DDD-EEEEEEEEEEEE"

    assert await async_setup_component(hass, DOMAIN, {}) is True
    entry = add_mock_entry(
        hass,
        entry_id="entry_latter_uuid_derivation",
        domain=DOMAIN,
        title="Latter",
        data={},
        subentries_data=[
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "pocket_one",
                    CONF_ESPHOME_DEVICE_ID: esp_1.id,
                    "mac": mac_1,
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_p1",
                subentry_type=SUBENTRY_DEVICE,
                title="Pocket One",
                unique_id=mac_1,
            ),
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "pocket_two",
                    CONF_ESPHOME_DEVICE_ID: esp_2.id,
                    "mac": mac_2,
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_p2",
                subentry_type=SUBENTRY_DEVICE,
                title="Pocket Two",
                unique_id=mac_2,
            ),
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "pocket_custom",
                    CONF_ESPHOME_DEVICE_ID: esp_3.id,
                    "mac": mac_3,
                    CONF_BLE_BEACON_UUID: explicit_override_uuid.lower(),
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_p3",
                subentry_type=SUBENTRY_DEVICE,
                title="Pocket Custom",
                unique_id=mac_3,
            ),
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "keys_fob",
                    CONF_BLE_TARGET_ADDRESS: "11:22:33:44:55:66",
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_fob",
                subentry_type=SUBENTRY_BLE_TAG,
                title="Keys Fob",
                unique_id="tag_11:22:33:44:55:66",
            ),
        ],
        unique_id=DOMAIN,
    )
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    c1 = entry.runtime_data.coordinators["sub_p1"]
    c2 = entry.runtime_data.coordinators["sub_p2"]
    c3 = entry.runtime_data.coordinators["sub_p3"]
    c_tag = entry.runtime_data.coordinators["sub_fob"]

    calls_p1 = mock_service(hass, "esphome", "pocket_one_latter_set_beacon_uuid")
    calls_p2 = mock_service(hass, "esphome", "pocket_two_latter_set_beacon_uuid")

    get_global_config(hass)[CONF_SYSTEM_BLE_UUID] = sys_uuid_a
    await c1.async_on_global_config_updated({CONF_SYSTEM_BLE_UUID})
    await c2.async_on_global_config_updated({CONF_SYSTEM_BLE_UUID})
    await c3.async_on_global_config_updated({CONF_SYSTEM_BLE_UUID})

    assert c1.ble_beacon_uuid == derive_device_beacon_uuid(sys_uuid_a, mac_1)
    assert c2.ble_beacon_uuid == derive_device_beacon_uuid(sys_uuid_a, mac_2)
    assert c1.ble_beacon_uuid != c2.ble_beacon_uuid
    assert c3.ble_beacon_uuid == explicit_override_uuid
    assert c_tag.ble_beacon_uuid == sys_uuid_a
    assert c1.ble_tracker is not None and c1.ble_tracker.beacon_uuid == c1.ble_beacon_uuid
    assert c2.ble_tracker is not None and c2.ble_tracker.beacon_uuid == c2.ble_beacon_uuid
    assert calls_p1[-1].data["uuid"] == c1.ble_beacon_uuid
    assert calls_p2[-1].data["uuid"] == c2.ble_beacon_uuid

    # Pre-upgrade device_hello carrying stale shared system_ble_uuid MUST NOT clobber derived UUID
    await c1.async_handle_device_hello(
        "77",
        '{"v":2,"contract":3,"board":"waveshare_s3_175c","w":466,"h":466,"shape":"circle",'
        '"display":1,"touch":1,"audio":1,"mic":1,"spk":1,"imu":1,"battery":1,"stationary":0,"wearable":0,'
        f'"beacon":{{"uuid":"{sys_uuid_a}","major":1,"minor":1}},"core_rev":{MIN_FIRMWARE_CORE_REV}}}',
    )
    assert c1.ble_tracker._target_uuid_hex == c1.ble_beacon_uuid.replace("-", "").lower()

    # Whereas a tracker still on compile-time DEFAULT_BLE_BEACON_UUID adopts a non-default manifest UUID
    default_trk = LatterNativeBleTracker(
        hass,
        beacon_uuid=DEFAULT_BLE_BEACON_UUID,
        device_slug="default_manifest_probe",
        on_area_detected=lambda _a, _s: None,
    )
    default_trk.update_manifest_beacon({"uuid": sys_uuid_a, "major": 1, "minor": 1})
    assert default_trk._target_uuid_hex == sys_uuid_a.replace("-", "").lower()
    assert default_trk.owns_bound_mac_int(None) is False

    # Undashed compile-time DEFAULT_BLE_BEACON_UUID in subentry data MUST NOT bypass derivation
    c1.update_device_config(
        {**c1.device_data, CONF_BLE_BEACON_UUID: DEFAULT_BLE_BEACON_UUID.lower().replace("-", "")}
    )
    assert c1.ble_beacon_uuid == derive_device_beacon_uuid(sys_uuid_a, mac_1)

    # Studio saving back the displayed auto-derived UUID (or undashed default) keeps it unpinned ("")
    await _cmd_save_device_config(
        hass,
        c1,
        {"config": {CONF_BLE_BEACON_UUID: c1.ble_beacon_uuid.lower()}},
        get_global_config(hass),
        {},
    )
    assert c1.device_data.get(CONF_BLE_BEACON_UUID) == ""
    await _cmd_save_device_config(
        hass,
        c1,
        {"config": {CONF_BLE_BEACON_UUID: DEFAULT_BLE_BEACON_UUID.lower().replace("-", "")}},
        get_global_config(hass),
        {},
    )
    assert c1.device_data.get(CONF_BLE_BEACON_UUID) == ""
    # Genuine custom override via Studio save persists and takes precedence; clearing reverts to derived
    manual_uuid = "BBBBBBBB-CCCC-4DDD-8EEE-FFFFFFFFFFFF"
    await _cmd_save_device_config(
        hass,
        c1,
        {"config": {CONF_BLE_BEACON_UUID: manual_uuid}},
        get_global_config(hass),
        {},
    )
    assert c1.ble_beacon_uuid == manual_uuid
    await _cmd_save_device_config(
        hass,
        c1,
        {"config": {CONF_BLE_BEACON_UUID: ""}},
        get_global_config(hass),
        {},
    )
    assert c1.ble_beacon_uuid == derive_device_beacon_uuid(sys_uuid_a, mac_1)

    # Rotating CONF_SYSTEM_BLE_UUID rotates unpinned derived UUIDs & trackers while keeping explicit override untouched
    get_global_config(hass)[CONF_SYSTEM_BLE_UUID] = sys_uuid_b
    await c1.async_on_global_config_updated({CONF_SYSTEM_BLE_UUID})
    await c2.async_on_global_config_updated({CONF_SYSTEM_BLE_UUID})
    await c3.async_on_global_config_updated({CONF_SYSTEM_BLE_UUID})
    assert c1.ble_beacon_uuid == derive_device_beacon_uuid(sys_uuid_b, mac_1)
    assert c2.ble_beacon_uuid == derive_device_beacon_uuid(sys_uuid_b, mac_2)
    assert c1.ble_tracker is not None and c1.ble_tracker.beacon_uuid == c1.ble_beacon_uuid
    assert c3.ble_beacon_uuid == explicit_override_uuid

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_identical_s3_trackers_foreign_mac_exclusion_all_fabric_paths(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify two identical S3 devices sharing UUID+major+minor never cross-contaminate across all 3 fabric paths."""
    await prepare_latter_dependencies(hass)
    ensure_area(hass, "Living Room", area_id="living_room")
    ensure_area(hass, "Kitchen", area_id="kitchen")
    ensure_area(hass, "Bedroom", area_id="bedroom")
    await seed_ble_proxies(
        hass,
        [
            ("lr_proxy", "aa:bb:cc:00:00:11", "Living Room Proxy", "living_room"),
            ("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen"),
            ("bed_proxy", "aa:bb:cc:00:00:33", "Bedroom Proxy", "bedroom"),
        ],
    )

    shared_uuid = "12345678-1234-4678-8ABC-DEF012345678"
    esp_1, _ = make_esphome_device(
        hass, slug="pocket_alpha", mac="aa:bb:cc:dd:10:01", name="Pocket Alpha", area_id="living_room"
    )
    esp_2, _ = make_esphome_device(
        hass, slug="pocket_beta", mac="aa:bb:cc:dd:20:01", name="Pocket Beta", area_id="kitchen"
    )
    ble_mac_1 = "AA:BB:CC:DD:10:03"
    ble_mac_2 = "AA:BB:CC:DD:20:03"

    tracker_1 = LatterNativeBleTracker(
        hass,
        beacon_uuid=shared_uuid,
        device_slug="pocket_alpha",
        on_area_detected=lambda _a, _s: None,
        esphome_device_id=esp_1.id,
        manifest_beacon={"uuid": shared_uuid, "major": 1, "minor": 1},
    )
    tracker_2 = LatterNativeBleTracker(
        hass,
        beacon_uuid=shared_uuid,
        device_slug="pocket_beta",
        on_area_detected=lambda _a, _s: None,
        esphome_device_id=esp_2.id,
        manifest_beacon={"uuid": shared_uuid, "major": 1, "minor": 1},
    )
    # Standalone rotating-MAC phone/tag (empty _target_mac_ints) with its own UUID + major:minor
    phone_uuid = "87654321-4321-4765-8CBA-098765432100"
    phone_tracker = LatterNativeBleTracker(
        hass,
        beacon_uuid=phone_uuid,
        device_slug="roaming_phone",
        on_area_detected=lambda _a, _s: None,
        target_address=f"{phone_uuid}-100-1",
    )
    # Private BLE Device (dynamic RPA MAC) to verify _dynamic_target_mac_int foreign-MAC exclusion
    hass.states.async_set(
        "device_tracker.sam_watch",
        "home",
        {"friendly_name": "Sam Watch", "current_address": "51:AA:BB:CC:DD:99"},
    )
    rpa_tracker = LatterNativeBleTracker(
        hass,
        beacon_uuid="",
        device_slug="sam_watch",
        on_area_detected=lambda _a, _s: None,
        target_address="device_tracker.sam_watch",
    )

    fabric = get_ble_fabric(hass)
    tracker_1.async_start()
    tracker_2.async_start()
    phone_tracker.async_start()
    rpa_tracker.async_start()
    try:
        t0 = time.monotonic()

        # Path 1: _async_on_shared_ble_advertisement (passive + per-address raw callbacks)
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                shared_uuid,
                rssi=-48,
                source="AA:BB:CC:00:00:11",
                obs_time=t0,
                address=ble_mac_1,
                major=1,
                minor=1,
            ),
        )
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                shared_uuid,
                rssi=-49,
                source="AA:BB:CC:00:00:22",
                obs_time=t0 + 0.1,
                address=ble_mac_2,
                major=1,
                minor=1,
            ),
        )
        assert tracker_1.current_area_id == "living_room"
        assert tracker_1.packets_seen == 1
        assert ble_mac_2 not in tracker_1.matched_ble_addresses
        assert tracker_2.current_area_id == "kitchen"
        assert tracker_2.packets_seen == 1
        assert ble_mac_1 not in tracker_2.matched_ble_addresses

        # Foreign dynamic RPA MAC owned by rpa_tracker MUST NOT match tracker_1/tracker_2 via fallback
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                shared_uuid,
                rssi=-46,
                source="AA:BB:CC:00:00:33",
                obs_time=t0 + 0.15,
                address="51:AA:BB:CC:DD:99",
                major=1,
                minor=1,
            ),
        )
        assert rpa_tracker.packets_seen == 1
        assert rpa_tracker.current_area_id == "bedroom"
        assert tracker_1.packets_seen == 1
        assert tracker_2.packets_seen == 1

        # Standalone phone with unrelated rotating MAC still matches cleanly by (UUID, major, minor)!
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                phone_uuid,
                rssi=-52,
                source="AA:BB:CC:00:00:33",
                obs_time=t0 + 0.2,
                address="6E:44:55:66:77:88",
                major=100,
                minor=1,
            ),
        )
        assert phone_tracker.current_area_id == "bedroom"
        assert phone_tracker.packets_seen == 1
        assert tracker_1.packets_seen == 1
        assert tracker_2.packets_seen == 1

        # Strong burst from pocket_alpha in Living Room MUST NOT pull pocket_beta out of Kitchen
        tracker_2._last_switch_monotonic = t0 - 20.0
        for step in range(3):
            inject_ble_adv(
                hass,
                make_ibeacon_service_info(
                    shared_uuid,
                    rssi=-36,
                    source="AA:BB:CC:00:00:11",
                    obs_time=t0 + 1.0 + step * 0.3,
                    address=ble_mac_1,
                    major=1,
                    minor=1,
                ),
            )
        assert tracker_1.packets_seen == 4
        assert tracker_2.packets_seen == 1
        assert tracker_2.current_area_id == "kitchen"

        # Path 2: _async_on_esphome_ibeacon_event (`esphome.ibeacon_seen` bus events)
        hass.bus.async_fire(
            "esphome.ibeacon_seen",
            {
                "source": "AA:BB:CC:00:00:33",
                "uuid": shared_uuid,
                "address": ble_mac_1,
                "major": 1,
                "minor": 1,
                "rssi": -40,
            },
        )
        # Also verify phone_tracker still matches its own rotating MAC via esphome.ibeacon_seen
        hass.bus.async_fire(
            "esphome.ibeacon_seen",
            {
                "source": "AA:BB:CC:00:00:33",
                "uuid": phone_uuid,
                "address": "7A:11:22:33:44:55",
                "major": 100,
                "minor": 1,
                "rssi": -50,
            },
        )
        # Foreign bound MAC advertising phone_tracker's UUID+100:1 MUST NOT leak into phone_tracker
        hass.bus.async_fire(
            "esphome.ibeacon_seen",
            {
                "source": "AA:BB:CC:00:00:11",
                "uuid": phone_uuid,
                "address": ble_mac_1,
                "major": 100,
                "minor": 1,
                "rssi": -41,
            },
        )
        await hass.async_block_till_done()
        assert tracker_1.packets_seen == 5
        assert tracker_2.packets_seen == 1
        assert tracker_2.current_area_id == "kitchen"
        assert phone_tracker.packets_seen == 2

        # Path 3: seed_tracker_from_scanners_once (scanner cache polling/seeding)
        # Scanner caches hold BOTH ble_mac_1 (Living Room, -36 dBm) and ble_mac_2 (Kitchen, -49 dBm)
        tracker_2._scanner_states.clear()
        tracker_2._last_adv_ts_by_scanner.clear()
        tracker_2._matched_ble_addresses.clear()
        tracker_2.current_area_id = None
        tracker_2.packets_seen = 0
        fabric.seed_tracker_from_scanners_once(tracker_2)
        assert tracker_2.packets_seen == 1
        assert tracker_2.current_area_id == "kitchen"
        assert ble_mac_2 in tracker_2.matched_ble_addresses
        assert ble_mac_1 not in tracker_2.matched_ble_addresses
    finally:
        tracker_1.async_stop()
        tracker_2.async_stop()
        phone_tracker.async_stop()
        rpa_tracker.async_stop()


async def test_identical_p4_c6_devices_isolated_by_derived_uuid_and_suppressed_from_discovery(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify two identical ESP32-P4+C6 devices isolate via derived UUIDs and are suppressed in Studio BLE discovery."""
    await prepare_latter_dependencies(hass)
    ensure_area(hass, "Living Room", area_id="living_room")
    ensure_area(hass, "Kitchen", area_id="kitchen")
    await seed_ble_proxies(
        hass,
        [
            ("lr_proxy", "aa:bb:cc:00:00:11", "Living Room Proxy", "living_room"),
            ("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen"),
        ],
    )

    sys_uuid = "49BDD15E-2D6F-417C-B0C2-4E39EB0AF1DF"
    p4_mac_1, c6_mac_1 = "e8:f6:0a:e8:a4:01", "E8:3D:C1:D2:46:11"
    p4_mac_2, c6_mac_2 = "e8:f6:0a:e8:a4:02", "E8:3D:C1:D2:46:22"
    esp_1, _ = make_esphome_device(
        hass, slug="remote_one", mac=p4_mac_1, name="Remote One", area_id="living_room", stationary=0
    )
    esp_2, _ = make_esphome_device(
        hass, slug="remote_two", mac=p4_mac_2, name="Remote Two", area_id="kitchen", stationary=0
    )
    p4_manifest = {
        "v": 2,
        "contract": 3,
        "board": "waveshare_p4_35",
        "w": 320,
        "h": 480,
        "shape": "square",
        "display": 1,
        "touch": 1,
        "audio": 1,
        "mic": 1,
        "spk": 1,
        "imu": 0,
        "battery": 1,
        "stationary": 0,
        "wearable": 0,
        "ips": 1,
        "chip": "ESP32-P4",
        "psram_mb": 32,
        "minor": 4,
        "core_rev": MIN_FIRMWARE_CORE_REV,
    }
    for sub_id in ("sub_r1", "sub_r2"):
        await seed_device_hello_manifest(hass, sub_id, p4_manifest)

    assert await async_setup_component(hass, DOMAIN, {}) is True
    entry = add_mock_entry(
        hass,
        entry_id="entry_latter_p4_isolation",
        domain=DOMAIN,
        title="Latter",
        data={},
        subentries_data=[
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "remote_one",
                    CONF_ESPHOME_DEVICE_ID: esp_1.id,
                    "mac": p4_mac_1,
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_r1",
                subentry_type=SUBENTRY_DEVICE,
                title="Remote One",
                unique_id=p4_mac_1,
            ),
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "remote_two",
                    CONF_ESPHOME_DEVICE_ID: esp_2.id,
                    "mac": p4_mac_2,
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_r2",
                subentry_type=SUBENTRY_DEVICE,
                title="Remote Two",
                unique_id=p4_mac_2,
            ),
        ],
        unique_id=DOMAIN,
    )
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    c1 = entry.runtime_data.coordinators["sub_r1"]
    c2 = entry.runtime_data.coordinators["sub_r2"]
    get_global_config(hass)[CONF_SYSTEM_BLE_UUID] = sys_uuid
    await c1.async_on_global_config_updated({CONF_SYSTEM_BLE_UUID})
    await c2.async_on_global_config_updated({CONF_SYSTEM_BLE_UUID})

    uuid_1 = c1.ble_beacon_uuid
    uuid_2 = c2.ble_beacon_uuid
    assert uuid_1 == derive_device_beacon_uuid(sys_uuid, p4_mac_1)
    assert uuid_2 == derive_device_beacon_uuid(sys_uuid, p4_mac_2)
    assert uuid_1 != uuid_2

    t0 = time.monotonic()
    # Both C6 chips advertise unrelated BLE MACs with identical major=1, minor=4 and their own derived UUIDs
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            uuid_1,
            rssi=-47,
            source="AA:BB:CC:00:00:11",
            obs_time=t0,
            address=c6_mac_1,
            major=1,
            minor=4,
            local_name="Latter C6 Beacon One",
        ),
    )
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            uuid_2,
            rssi=-49,
            source="AA:BB:CC:00:00:22",
            obs_time=t0 + 0.1,
            address=c6_mac_2,
            major=1,
            minor=4,
            local_name="Latter C6 Beacon Two",
        ),
    )
    assert c1.ble_tracker is not None and c1.ble_tracker.current_area_id == "living_room"
    assert c1.ble_tracker.packets_seen == 1
    assert c1.ble_tracker.matched_ble_addresses == [c6_mac_1]
    assert c2.ble_tracker is not None and c2.ble_tracker.current_area_id == "kitchen"
    assert c2.ble_tracker.packets_seen == 1
    assert c2.ble_tracker.matched_ble_addresses == [c6_mac_2]

    # Add HA `ibeacon` entities for managed Latter UUIDs + default/system UUIDs + an unrelated unmanaged Tile tag
    for idx, (m_uuid, tag_slug) in enumerate(
        (
            (uuid_1, "latter_c6_1"),
            (uuid_2, "latter_c6_2"),
            (DEFAULT_BLE_BEACON_UUID, "latter_default_new"),
            (sys_uuid, "latter_pre_upgrade_sys"),
        ),
        start=1,
    ):
        ib_dev = register_device(
            hass,
            config_entry_id="entry_ibeacon_p4",
            entry_domain="ibeacon",
            identifiers={("ibeacon", f"{m_uuid.lower()}_1_4")},
            name=f"Managed C6 {idx}",
            manufacturer="Latter",
        )
        ib_eid = f"device_tracker.{tag_slug}"
        register_entity(
            hass,
            ib_eid,
            platform="ibeacon",
            config_entry_id="entry_ibeacon_p4",
            device_id=ib_dev.id,
            unique_id=f"{m_uuid.lower()}_1_4_tracker",
        )
        hass.states.async_set(
            ib_eid,
            "home",
            {"friendly_name": f"Managed C6 {idx}", "uuid": m_uuid, "major": 1, "minor": 4},
        )

    # Also emit raw live scanner advertisements for DEFAULT_BLE_BEACON_UUID and pre-upgrade sys_uuid
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            DEFAULT_BLE_BEACON_UUID,
            rssi=-51,
            source="AA:BB:CC:00:00:11",
            obs_time=t0 + 0.15,
            address="E8:3D:C1:D2:46:98",
            major=1,
            minor=1,
            local_name="Unprovisioned Latter Beacon",
        ),
    )
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            sys_uuid,
            rssi=-52,
            source="AA:BB:CC:00:00:22",
            obs_time=t0 + 0.18,
            address="E8:3D:C1:D2:46:99",
            major=1,
            minor=1,
            local_name="Sleeping Pre-Upgrade Beacon",
        ),
    )

    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            "",
            rssi=-56,
            source="AA:BB:CC:00:00:22",
            obs_time=t0 + 0.2,
            address="DC:22:33:44:55:66",
            service_data={"0000feed-0000-1000-8000-00805f9b34fb": b"\x02\x00\xaa\xbb"},
            service_uuids=["0000feed-0000-1000-8000-00805f9b34fb"],
        ),
    )

    payload = build_studio_state_payload(hass, c1)
    discovered_targets = {row["target_address"] for row in payload["discovered_ble_devices"]}
    assert "device_tracker.latter_c6_1" not in discovered_targets
    assert "device_tracker.latter_c6_2" not in discovered_targets
    assert "device_tracker.latter_default_new" not in discovered_targets
    assert "device_tracker.latter_pre_upgrade_sys" not in discovered_targets
    assert c6_mac_1 not in discovered_targets
    assert c6_mac_2 not in discovered_targets
    assert "E8:3D:C1:D2:46:98" not in discovered_targets
    assert "E8:3D:C1:D2:46:99" not in discovered_targets
    assert "DC:22:33:44:55:66" in discovered_targets

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_consecutive_4mac_esp32_batch_and_ambiguous_bound_mac_disambiguation(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify consecutive Espressif 4-MAC blocks (`:00` vs `:04`) stay disjoint and ambiguous bound MACs disambiguate by iBeacon UUID."""
    await prepare_latter_dependencies(hass)
    ensure_area(hass, "Living Room", area_id="living_room")
    ensure_area(hass, "Kitchen", area_id="kitchen")
    await seed_ble_proxies(
        hass,
        [
            ("lr_proxy", "aa:bb:cc:00:00:11", "Living Room Proxy", "living_room"),
            ("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen"),
        ],
    )

    sys_uuid = "55555555-6666-4777-8888-999999999999"
    mac_a, ble_a = "aa:bb:cc:dd:ee:00", "AA:BB:CC:DD:EE:02"
    mac_b, ble_b = "aa:bb:cc:dd:ee:04", "AA:BB:CC:DD:EE:06"
    uuid_a = derive_device_beacon_uuid(sys_uuid, mac_a)
    uuid_b = derive_device_beacon_uuid(sys_uuid, mac_b)

    esp_a, _ = make_esphome_device(
        hass, slug="batch_pocket_a", mac=mac_a, name="Batch Pocket A", area_id="living_room"
    )
    esp_b, _ = make_esphome_device(
        hass, slug="batch_pocket_b", mac=mac_b, name="Batch Pocket B", area_id="kitchen"
    )

    tracker_a = LatterNativeBleTracker(
        hass,
        beacon_uuid=uuid_a,
        device_slug="batch_pocket_a",
        on_area_detected=lambda _a, _s: None,
        esphome_device_id=esp_a.id,
        manifest_beacon={"uuid": uuid_a, "major": 1, "minor": 1},
    )
    tracker_b = LatterNativeBleTracker(
        hass,
        beacon_uuid=uuid_b,
        device_slug="batch_pocket_b",
        on_area_detected=lambda _a, _s: None,
        esphome_device_id=esp_b.id,
        manifest_beacon={"uuid": uuid_b, "major": 1, "minor": 1},
    )

    fabric = get_ble_fabric(hass)
    tracker_a.async_start()
    tracker_b.async_start()
    try:
        # 1) Consecutive 4-MAC blocks (`-1..+2`) MUST NOT overlap on Device A's BLE MAC `...:02`
        assert ble_a in tracker_a.target_macs_formatted
        assert ble_a not in tracker_b.target_macs_formatted
        assert ble_b in tracker_b.target_macs_formatted
        assert ble_b not in tracker_a.target_macs_formatted

        t0 = time.monotonic()
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                uuid_a,
                rssi=-47,
                source="AA:BB:CC:00:00:11",
                obs_time=t0,
                address=ble_a,
                major=1,
                minor=1,
            ),
        )
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                uuid_b,
                rssi=-49,
                source="AA:BB:CC:00:00:22",
                obs_time=t0 + 0.1,
                address=ble_b,
                major=1,
                minor=1,
            ),
        )
        assert tracker_a.current_area_id == "living_room"
        assert tracker_a.packets_seen == 1
        assert tracker_b.current_area_id == "kitchen"
        assert tracker_b.packets_seen == 1
        assert ble_a not in tracker_b.matched_ble_addresses

        # 2) Defense-in-depth: even if two trackers overlap on the SAME bound MAC (`len(owner_ids) > 1`),
        #    framed iBeacon advertisements disambiguate strictly by derived UUID across Paths 1 & 3!
        ble_a_int = mac_to_int(ble_a)
        assert ble_a_int is not None
        tracker_b._target_mac_ints.add(ble_a_int)

        # Path 1: live shared BLE callback on overlapping MAC with uuid_a -> ONLY tracker_a matches
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                uuid_a,
                rssi=-40,
                source="AA:BB:CC:00:00:11",
                obs_time=t0 + 1.0,
                address=ble_a,
                major=1,
                minor=1,
            ),
        )
        assert tracker_a.packets_seen == 2
        assert tracker_b.packets_seen == 1
        assert tracker_b.current_area_id == "kitchen"
        assert ble_a not in tracker_b.matched_ble_addresses

        # Path 3: scanner cache seeding on tracker_b rejects ble_a (uuid_a) and seeds ONLY ble_b (uuid_b)
        tracker_b._scanner_states.clear()
        tracker_b._last_adv_ts_by_scanner.clear()
        tracker_b._matched_ble_addresses.clear()
        tracker_b.current_area_id = None
        tracker_b.packets_seen = 0
        fabric.seed_tracker_from_scanners_once(tracker_b)
        assert tracker_b.packets_seen == 1
        assert tracker_b.current_area_id == "kitchen"
        assert tracker_b.matched_ble_addresses == [ble_b]
    finally:
        tracker_a.async_stop()
        tracker_b.async_stop()
