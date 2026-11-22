"""Tests for Companion App BLE transmitter discovery, IRK fingerprinting, local BLE tags, and EID exclusion."""

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
from custom_components.latter.presence.ble_registry import (
    APPLE_COMPANY_ID,
    IBEACON_PREFIX,
    parse_ibeacon_identity,
)
from custom_components.latter.studio.payload import build_studio_state_payload


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


async def test_companion_app_ble_transmitter_discovery_dedupe_and_major_minor_isolation(
    hass: Any,
) -> None:
    """Verify HA Companion App 1-click phone discovery, 6x iBeacon dedupe, ref_power seed, Major:Minor isolation, and 0 ms sync."""


    area_reg = ar.async_get(hass)
    area_reg.async_create("Living Room", area_id="living_room", floor_id="floor_1")
    area_reg.async_create("Kitchen", area_id="kitchen", floor_id="floor_1")
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    # Seed Bluetooth proxies + live iBeacon advertisement in Kitchen scanner cache
    phone_uuid = "008fd71e-a43a-4ab4-8e02-f969133f8380"
    t0 = time.monotonic()
    live_phone_adv = _make_ibeacon_adv(
        phone_uuid,
        rssi=-53,
        source="AA:BB:CC:00:00:22",
        obs_time=t0,
        address="5C:11:22:33:A1:B2",
        major=100,
        minor=1,
        tx_power_1m=-56,
    )
    dev_reg.async_get_or_create(
        config_entry_id="esp_lr_proxy",
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:00:00:11")},
        identifiers={("esphome", "aa:bb:cc:00:00:11")},
        name="Living Room Proxy",
        area_id="living_room",
    )
    dev_reg.async_get_or_create(
        config_entry_id="esp_kit_proxy",
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:00:00:22")},
        identifiers={("esphome", "aa:bb:cc:00:00:22")},
        name="Kitchen Proxy",
        area_id="kitchen",
    )
    hass.data["_bt_scanners"] = [
        SimpleNamespace(
            source="AA:BB:CC:00:00:11",
            name="Living Room Proxy",
            details={"source": "aa:bb:cc:00:00:11"},
            discovered_device_timestamps={},
            discovered_devices_and_advertisement_data={},
        ),
        SimpleNamespace(
            source="AA:BB:CC:00:00:22",
            name="Kitchen Proxy",
            details={"source": "aa:bb:cc:00:00:22"},
            discovered_device_timestamps={"5C:11:22:33:A1:B2": t0},
            discovered_devices_and_advertisement_data={
                "5C:11:22:33:A1:B2": (
                    SimpleNamespace(rssi=-53, name=None),
                    live_phone_adv,
                )
            },
        ),
    ]

    # 1) Register Android HA Companion App device + `sensor.alexs_pixel_9_ble_transmitter`
    phone_dev = dev_reg.async_get_or_create(
        config_entry_id="mobile_app_pixel9",
        identifiers={("mobile_app", "pixel_9_pro_alex")},
        name="Alex's Pixel 9",
        manufacturer="Google",
        model="Pixel 9 Pro",
    )
    emitter_eid = "sensor.alexs_pixel_9_ble_transmitter"
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id=emitter_eid,
            platform="mobile_app",
            device_id=phone_dev.id,
            unique_id="pixel_9_pro_alex_ble_emitter",
            original_name="BLE Transmitter",
        )
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
        ib_dev = dev_reg.async_get_or_create(
            config_entry_id="entry_ibeacon",
            identifiers={("ibeacon", f"{phone_uuid}_100_1_{rot_hex}")},
            name=f"Beacon {rot_hex}",
        )
        dt_eid = f"device_tracker.beacon_{rot_hex.lower()}"
        dist_eid = f"sensor.beacon_{rot_hex.lower()}_estimated_distance"
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=dt_eid,
                platform="ibeacon",
                device_id=ib_dev.id,
                unique_id=f"{phone_uuid}_100_1_{rot_hex}_tracker",
                original_name=f"Beacon {rot_hex}",
            )
        )
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=dist_eid,
                platform="ibeacon",
                device_id=ib_dev.id,
                unique_id=f"{phone_uuid}_100_1_{rot_hex}_distance",
                original_name=f"Beacon {rot_hex} Estimated Distance",
            )
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
    assert cand["scanner"] == "Kitchen Proxy"

    # Also verify standalone 3x2 rotating-MAC `ibeacon` dedupe when NOT covered by a Companion App phone
    tag_uuid = "e2c56db5-dffb-48d2-b060-d0f5a71096e1"
    for rot_hex, rssi_v in (("1A2B", -68), ("3C4D", -59)):
        s_dev = dev_reg.async_get_or_create(
            config_entry_id="entry_ibeacon",
            identifiers={("ibeacon", f"{tag_uuid}_1_9_{rot_hex}")},
            name=f"Blue Charm Keys {rot_hex}",
        )
        for dom, sfx in (("device_tracker", ""), ("sensor", "_estimated_distance")):
            s_eid = f"{dom}.blue_charm_keys_{rot_hex.lower()}{sfx}"
            ent_reg.async_register(
                er.RegistryEntry(
                    entity_id=s_eid,
                    platform="ibeacon",
                    device_id=s_dev.id,
                    unique_id=f"{tag_uuid}_1_9_{rot_hex}{sfx}",
                )
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
    await async_setup(hass, {})
    entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="entry_latter_comp",
            domain=DOMAIN,
            title="Latter",
            data={},
            subentries_data=[
                ConfigSubentry(
                    subentry_id="sub_pixel9",
                    subentry_type=SUBENTRY_BLE_TAG,
                    title="Alex's Pixel 9",
                    unique_id=f"tag_{emitter_eid}",
                    data={
                        CONF_DEVICE_SLUG: "alexs_pixel_9",
                        CONF_BLE_TARGET_ADDRESS: emitter_eid,
                        CONF_ASSIGNED_PERSON: "person.alex",
                        CONF_NATIVE_BLE_TRACKING: True,
                    },
                )
            ],
            unique_id=DOMAIN,
        )
    )
    assert await async_setup_entry(hass, entry) is True
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
    shared_cb, _matcher, _mode = hass.data["_bt_callbacks"][0]

    # Packet from ANOTHER family member's phone sharing the same UUID (`major=100, minor=2`) in Living Room MUST be REJECTED!
    t1 = t0 + 6.0
    tracker._last_switch_monotonic = t0 - 20.0
    for step in range(4):
        shared_cb(
            _make_ibeacon_adv(
                phone_uuid,
                rssi=-38,
                source="AA:BB:CC:00:00:11",
                obs_time=t1 + step * 0.3,
                address="6E:AA:BB:CC:DD:02",
                major=100,
                minor=2,
            ),
            "adv",
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
        shared_cb(
            _make_ibeacon_adv(
                phone_uuid,
                rssi=-42,
                source="AA:BB:CC:00:00:11",
                obs_time=t1 + 2.0 + step * 0.3,
                address="7A:11:22:33:44:01",
                major=100,
                minor=1,
                tx_power_1m=-56,
            ),
            "adv",
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
    assert tracker._resolve_beacon_major_minor() == (0, 0)
    assert tracker.detected_ref_power_dbm == -54.0

    # Old `100:1` or another `0:1` phone in Kitchen is now REJECTED immediately
    tracker._last_switch_monotonic = t0 - 30.0
    t2 = t1 + 10.0
    for bad_maj, bad_min in ((100, 1), (0, 1)):
        for step in range(3):
            shared_cb(
                _make_ibeacon_adv(
                    phone_uuid,
                    rssi=-37,
                    source="AA:BB:CC:00:00:22",
                    obs_time=t2 + step * 0.2,
                    address="7B:99:88:77:66:55",
                    major=bad_maj,
                    minor=bad_min,
                    tx_power_1m=-54,
                ),
                "adv",
            )
    assert tracker.current_area_id == "living_room"

    # Matching `major=0, minor=0` in Kitchen switches cleanly!
    for step in range(4):
        shared_cb(
            _make_ibeacon_adv(
                phone_uuid,
                rssi=-40,
                source="AA:BB:CC:00:00:22",
                obs_time=t2 + 2.0 + step * 0.3,
                address="7C:55:44:33:22:11",
                major=0,
                minor=0,
                tx_power_1m=-54,
            ),
            "adv",
        )
    assert tracker.current_area_id == "kitchen"

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_private_ble_device_irk_vendor_and_device_type_fingerprinting(
    hass: Any,
) -> None:
    """Verify Private BLE Device (IRK) live vendor/device-type classification and device_id deduplication."""

    area_reg = ar.async_get(hass)
    area_reg.async_create("Living Room", area_id="living_room")
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    dev_reg.async_get_or_create(
        config_entry_id="esp_lr_proxy",
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:00:00:11")},
        identifiers={("esphome", "aa:bb:cc:00:00:11")},
        name="Living Room Proxy",
        area_id="living_room",
    )

    irk_cases = [
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

    adv_map: dict[str, tuple[Any, Any]] = {}
    for slug, title, rpa_mac, mfg_data, svc_data, svc_uuids, rssi_val, _expected in irk_cases:
        p_dev = dev_reg.async_get_or_create(
            config_entry_id=f"pble_{slug}",
            identifiers={("private_ble_device", f"irk_{slug}")},
            name=title,
        )
        dt_eid = f"device_tracker.{slug}"
        dist_eid = f"sensor.{slug}_estimated_distance"
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=dt_eid,
                platform="private_ble_device",
                device_id=p_dev.id,
                unique_id=f"irk_{slug}_tracker",
                original_name=title,
            )
        )
        # Register companion estimated_distance sensor on same device_id to verify 2->1 dedupe
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=dist_eid,
                platform="private_ble_device",
                device_id=p_dev.id,
                unique_id=f"irk_{slug}_estimated_distance",
                original_name=f"{title} Estimated Distance",
            )
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
        adv_map[rpa_mac] = (
            SimpleNamespace(rssi=rssi_val, name=None),
            SimpleNamespace(
                local_name="",
                manufacturer_data=mfg_data,
                service_data=svc_data,
                service_uuids=svc_uuids,
                rssi=rssi_val,
            ),
        )

    hass.data["_bt_scanners"] = [
        SimpleNamespace(
            source="AA:BB:CC:00:00:11",
            name="Living Room Proxy",
            details={"source": "aa:bb:cc:00:00:11"},
            discovered_devices_and_advertisement_data=adv_map,
        )
    ]

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


@pytest.mark.asyncio
async def test_local_ble_tag_fingerprinting_and_cloud_rolling_eid_exclusion(
    hass: Any,
) -> None:
    """Verify Tile, iTag, Shelly BLU, and RuuviTag classification while excluding Google FMDN & Apple Find My rolling EIDs."""

    area_reg = ar.async_get(hass)
    area_reg.async_create("Kitchen", area_id="kitchen")
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id="esp_kit_proxy",
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:00:00:22")},
        identifiers={("esphome", "aa:bb:cc:00:00:22")},
        name="Kitchen Proxy",
        area_id="kitchen",
    )

    adv_map = {
        # Supported local BLE tags (including unnamed Tile, Shelly BLU, and RuuviTag)
        "DC:11:22:33:E4:12": (
            SimpleNamespace(rssi=-55, name=None),
            SimpleNamespace(
                local_name="",
                manufacturer_data={},
                service_data={"0000feed-0000-1000-8000-00805f9b34fb": b"\x02\x00\xaa\xbb"},
                service_uuids=("0000feed-0000-1000-8000-00805f9b34fb",),
                rssi=-55,
            ),
        ),
        "FF:EE:DD:CC:BB:09": (
            SimpleNamespace(rssi=-62, name="iTAG   "),
            SimpleNamespace(
                local_name="iTAG   ",
                manufacturer_data={},
                service_data={},
                service_uuids=("0000ffe0-0000-1000-8000-00805f9b34fb",),
                rssi=-62,
            ),
        ),
        "38:39:8F:AA:BB:77": (
            SimpleNamespace(rssi=-58, name="SBBT-002C"),
            SimpleNamespace(
                local_name="SBBT-002C",
                manufacturer_data={0x0B9A: b"\x01\x00"},
                service_data={"0000fcd2-0000-1000-8000-00805f9b34fb": b"\x40\x01\x64\x3a\x01"},
                service_uuids=(),
                rssi=-58,
            ),
        ),
        "CB:B8:33:4C:88:4F": (
            SimpleNamespace(rssi=-65, name=None),
            SimpleNamespace(
                local_name="",
                manufacturer_data={0x0499: b"\x05\x12\xfc\x53\x94\xc3\x7c"},
                service_data={},
                service_uuids=(),
                rssi=-65,
            ),
        ),
        # Excluded cloud Find-network rolling-EID tags:
        # 1) Google FMDN / Find Hub rolling EID (`0xFEAA` frame `0x40` — Moto Tag / Pebblebee FMDN / Chipolo ONE Point)
        "4A:91:00:E1:D2:40": (
            SimpleNamespace(rssi=-47, name=None),
            SimpleNamespace(
                local_name="",
                manufacturer_data={},
                service_data={"0000feaa-0000-1000-8000-00805f9b34fb": bytes([0x40]) + b"\xab" * 20},
                service_uuids=("0000feaa-0000-1000-8000-00805f9b34fb",),
                rssi=-47,
            ),
        ),
        # 2) Separated Apple Find My / AirTag (`0x004C` type `0x12`, unnamed)
        "7E:22:44:66:88:12": (
            SimpleNamespace(rssi=-45, name=None),
            SimpleNamespace(
                local_name="",
                manufacturer_data={0x004C: bytes([0x12, 0x19, 0x10]) + b"\xcd" * 24},
                service_data={},
                service_uuids=(),
                rssi=-45,
            ),
        ),
    }

    hass.data["_bt_scanners"] = [
        SimpleNamespace(
            source="AA:BB:CC:00:00:22",
            name="Kitchen Proxy",
            details={"source": "aa:bb:cc:00:00:22"},
            discovered_devices_and_advertisement_data=adv_map,
        )
    ]

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
