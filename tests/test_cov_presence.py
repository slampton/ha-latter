"""Targeted real-HA 2026.11 coverage tests for Latter BLE presence modules."""

from __future__ import annotations

from datetime import UTC, datetime
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.components import bluetooth
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from custom_components.latter.const import (
    CONF_AREA_FUSION_CONFIG,
    CONF_BLE_AREA_SIGNATURES,
    DEFAULT_BLE_BEACON_UUID,
)
from custom_components.latter.hub_registry import get_global_config
from custom_components.latter.presence.area_fusion import (
    discover_area_fusion_sensors,
    evaluate_area_sensor_fusion,
    get_tracked_fusion_entity_ids,
)
from custom_components.latter.presence.ble_discovery import (
    _consolidate_ibeacon_entities,
    _DiscoveryCtx,
    _index_live_ble_advertisements,
    _LiveBleIndex,
    describe_ble_target_model,
    get_discovered_ble_candidates,
    inspect_companion_ble_transmitter,
)
from custom_components.latter.presence.ble_fabric import get_ble_fabric
from custom_components.latter.presence.ble_math import (
    AreaDecision,
    resolve_companion_tx_ref_power_dbm,
    safe_rssi_int,
)
from custom_components.latter.presence.ble_registry import (
    APPLE_COMPANY_ID,
    GOOGLE_COMPANY_ID,
    IBEACON_PREFIX,
    MATCHED_BLE_ADDRESS_TTL_SECONDS,
    MICROSOFT_COMPANY_ID,
    SAMSUNG_COMPANY_ID,
    _get_floor_registry,
    _resolve_scanner_area_id_uncached,
    classify_ble_advertisement_kind,
    coerce_uint16,
    extract_adv_ref_power_dbm,
    extract_ibeacon_entity_identity,
    extract_uuid16,
    format_uuid_dashed,
    get_ble_signature_area_ids,
    has_configured_floors,
    mac_to_int,
    normalize_mfg_map,
    parse_ibeacon_identity,
    resolve_floor_info,
    resolve_scanner_area_id,
)
from custom_components.latter.presence.ble_tracker import (
    LatterNativeBleTracker,
    _clamp_float_param,
    _clean_area_signatures_map,
    _clean_scanner_offsets,
    _median_of_recent,
    discover_target_device_macs,
    score_signature_vector,
    update_scanner_kalman_state,
)
from tests.helpers import (
    ensure_area,
    ensure_bluetooth_manager,
    inject_ble_adv,
    make_ibeacon_service_info,
    prepare_latter_dependencies,
    register_device,
    register_entity,
    seed_ble_proxies,
)


def test_ble_math_edge_coercion_and_companion_tx_parsing() -> None:
    """Cover non-finite RSSI coercion, unparseable strings, and Companion TX fallback."""
    assert safe_rssi_int(None) is None
    assert safe_rssi_int(True) is None
    assert safe_rssi_int(float("nan")) is None
    assert safe_rssi_int(float("inf")) is None
    assert safe_rssi_int(float("-inf")) is None
    assert safe_rssi_int("nan") is None
    assert safe_rssi_int("inf") is None
    assert safe_rssi_int("-inf") is None
    assert safe_rssi_int("not-a-number") is None
    assert safe_rssi_int("") is None
    assert safe_rssi_int(-55.7) == -55
    assert safe_rssi_int("-62") == -62

    assert resolve_companion_tx_ref_power_dbm("bad_val", "ultraLow") == -81.0
    assert resolve_companion_tx_ref_power_dbm("bad_val", "unknown") is None
    assert resolve_companion_tx_ref_power_dbm(float("nan"), "low") == -75.0
    assert resolve_companion_tx_ref_power_dbm(-63, "ultraLow") == -63.0


async def test_area_fusion_edge_branches_and_confidence_modes(hass: Any) -> None:
    """Cover Area fusion exclusion, disabled sensors, occ_off penalty, closed-door boost, and any_or floor."""
    ensure_area(hass, "Kitchen", area_id="kitchen")
    ent_reg = er.async_get(hass)

    register_entity(
        hass,
        "binary_sensor.kitchen_occ",
        platform="mqtt",
        config_entry_id="mqtt_kitchen",
        area_id="kitchen",
        original_device_class="occupancy",
    )
    hass.states.async_set(
        "binary_sensor.kitchen_occ",
        "off",
        {"device_class": "occupancy", "friendly_name": "Kitchen Occupancy"},
    )

    register_entity(
        hass,
        "binary_sensor.kitchen_door",
        platform="mqtt",
        config_entry_id="mqtt_kitchen",
        area_id="kitchen",
        original_device_class="door",
    )
    hass.states.async_set(
        "binary_sensor.kitchen_door",
        "off",
        {"device_class": "door", "friendly_name": "Kitchen Door"},
    )

    register_entity(
        hass,
        "binary_sensor.kitchen_disabled_pir",
        platform="mqtt",
        config_entry_id="mqtt_kitchen",
        area_id="kitchen",
        original_device_class="motion",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    hass.states.async_set(
        "binary_sensor.kitchen_disabled_pir",
        "on",
        {"device_class": "motion", "friendly_name": "Disabled PIR"},
    )

    # Unregistered own-style state (fusion_mode attr) + non-binary_sensor ignored entry
    hass.states.async_set(
        "binary_sensor.unreg_latter_own",
        "on",
        {"fusion_mode": "weighted", "device_class": "occupancy"},
    )

    # Cache a sensor in fusion_index, then remove from EntityRegistry so cached lookup sees fusion_mode attr
    register_entity(
        hass,
        "binary_sensor.temp_cached_occ",
        platform="mqtt",
        config_entry_id="mqtt_kitchen",
        area_id="kitchen",
        original_device_class="occupancy",
    )
    hass.states.async_set(
        "binary_sensor.temp_cached_occ",
        "off",
        {"device_class": "occupancy"},
    )
    discover_area_fusion_sensors(hass, "kitchen")
    ent_reg.async_remove("binary_sensor.temp_cached_occ")
    hass.states.async_set(
        "binary_sensor.temp_cached_occ",
        "on",
        {"fusion_mode": "weighted", "device_class": "occupancy"},
    )

    get_global_config(hass)[CONF_AREA_FUSION_CONFIG] = {
        "kitchen": {
            "mode": "weighted",
            "threshold_pct": 50,
            "sensors": [
                "sensor.not_binary_ignored",
                "binary_sensor.unreg_latter_own",
                "binary_sensor.kitchen_disabled_pir",
                "binary_sensor.kitchen_occ",
                "binary_sensor.kitchen_door",
            ],
        }
    }

    tracked = get_tracked_fusion_entity_ids(hass)
    assert "binary_sensor.kitchen_occ" in tracked
    assert "binary_sensor.kitchen_door" in tracked
    assert "sensor.not_binary_ignored" not in tracked
    assert "binary_sensor.unreg_latter_own" not in tracked
    assert "binary_sensor.temp_cached_occ" not in tracked

    occ_on, occ_off, motion_on, door_closed, available = discover_area_fusion_sensors(
        hass,
        "kitchen",
        get_global_config(hass)[CONF_AREA_FUSION_CONFIG]["kitchen"]["sensors"],
    )
    assert occ_on == []
    assert occ_off == ["binary_sensor.kitchen_occ"]
    assert motion_on == []
    assert door_closed == ["binary_sensor.kitchen_door"]
    assert all(item["entity_id"] != "binary_sensor.kitchen_disabled_pir" for item in available)

    # Weighted: weak BLE (-82 -> 0.54) - occ_off penalty (0.18) + door_closed boost (0.08) = 0.44 -> 44%
    weighted_res = evaluate_area_sensor_fusion(
        hass, "kitchen", ble_present=True, best_rssi=-82
    )
    assert weighted_res["confidence_pct"] == 44
    assert weighted_res["is_occupied"] is False

    # any_or: occupied with confidence < 60% boosts to 75%
    get_global_config(hass)[CONF_AREA_FUSION_CONFIG]["kitchen"]["mode"] = "any_or"
    any_or_res = evaluate_area_sensor_fusion(
        hass, "kitchen", ble_present=True, best_rssi=-82
    )
    assert any_or_res["is_occupied"] is True
    assert any_or_res["confidence_pct"] == 75


async def test_ble_registry_parsing_classification_and_scanner_resolution(
    hass: Any,
) -> None:
    """Cover BLE registry parsing, vendor classification, floor fallbacks, and scanner-to-Area matching."""
    await ensure_bluetooth_manager(hass)
    ensure_area(hass, "Kitchen", area_id="kitchen")
    ensure_area(hass, "Garage", area_id="garage")
    ensure_area(hass, "Hallway", area_id="hallway")

    # Parsing and coercion edge cases
    assert format_uuid_dashed("short") == "short"
    assert coerce_uint16(None) is None
    assert coerce_uint16(True) is None
    assert coerce_uint16("") is None
    assert coerce_uint16([]) is None
    assert coerce_uint16(12.5) is None
    assert coerce_uint16("abc") is None
    assert coerce_uint16(70000) is None
    assert coerce_uint16(42.0) == 42
    assert mac_to_int("ZZ:ZZ:ZZ:ZZ:ZZ:ZZ") is None

    sample_uuid = "008fd71e-a43a-4ab4-8e02-f969133f8380"
    sample_hex = sample_uuid.replace("-", "")
    assert parse_ibeacon_identity("") is None
    assert parse_ibeacon_identity("eddystone:001122") is None
    assert parse_ibeacon_identity("bthome:001122") is None
    assert parse_ibeacon_identity(f"ibeacon:{sample_uuid}-10-20") == (sample_hex, 10, 20)

    # extract_ibeacon_entity_identity direct unique_id & rotating suffix fallback
    direct_ent = register_entity(
        hass,
        "device_tracker.ib_direct_uid",
        platform="ibeacon",
        config_entry_id="entry_ib_reg",
        unique_id=f"{sample_uuid}_10_20",
    )
    assert extract_ibeacon_entity_identity(hass, direct_ent, None) == (sample_hex, 10, 20)

    pref_ent = register_entity(
        hass,
        "device_tracker.ib_prefix_uid",
        platform="ibeacon",
        config_entry_id="entry_ib_reg",
        unique_id=f"{sample_uuid}_10_20_A1B2",
    )
    assert extract_ibeacon_entity_identity(hass, pref_ent, None) == (sample_hex, 10, 20)

    assert extract_uuid16("0xFEAA") == "feaa"
    assert extract_uuid16("feed") == "feed"
    assert extract_uuid16("not-a-uuid") == ""

    mfg_norm = normalize_mfg_map(
        {
            APPLE_COMPANY_ID: "not-bytes",  # type: ignore[dict-item]
            "bad_key": b"\x01\x02",  # type: ignore[dict-item]
            "0x0075": bytearray(b"\x03\x04"),  # type: ignore[dict-item]
        }
    )
    assert mfg_norm == {SAMSUNG_COMPANY_ID: b"\x03\x04"}

    # Advertisement classification branches
    assert (
        classify_ble_advertisement_kind(
            "", {MICROSOFT_COMPANY_ID: b"\x01\x02"}, {}, (), is_private_ble=True
        )
        == "Windows PC or Surface (Private BLE)"
    )
    assert (
        classify_ble_advertisement_kind("", {}, {}, (), is_private_ble=True)
        == "Phone or Watch (Private BLE / IRK)"
    )
    ed_uid_payload = bytes([0x00, 0xEC]) + bytes.fromhex("aabbccddeeff00112233112233445566")
    assert (
        classify_ble_advertisement_kind(
            "", {}, {"0000feaa-0000-1000-8000-00805f9b34fb": ed_uid_payload}, ()
        )
        == "Eddystone-UID Beacon"
    )
    assert (
        classify_ble_advertisement_kind("My Mac", {APPLE_COMPANY_ID: b"\x10"}, {}, ())
        == "Named BLE device (Apple)"
    )
    assert (
        classify_ble_advertisement_kind("My Galaxy", {SAMSUNG_COMPANY_ID: b"\x01"}, {}, ())
        == "Named BLE device (Samsung)"
    )
    assert (
        classify_ble_advertisement_kind("My Surface", {MICROSOFT_COMPANY_ID: b"\x01"}, {}, ())
        == "Named BLE device (Windows PC)"
    )
    assert (
        classify_ble_advertisement_kind("My Pixel", {GOOGLE_COMPANY_ID: b"\x01"}, {}, ())
        == "Named BLE device (Google)"
    )
    assert (
        classify_ble_advertisement_kind("Generic Sensor", {}, {}, ())
        == "Named BLE device"
    )

    # extract_adv_ref_power_dbm TX power & fallback branches
    svc_tx_1m = MagicMock(tx_power=-62)
    assert extract_adv_ref_power_dbm(svc_tx_1m, {}, {}) == -62.0
    svc_tx_raw = MagicMock(tx_power=4)
    assert extract_adv_ref_power_dbm(svc_tx_raw, {}, {}) == -55.0
    svc_tx_oor = MagicMock(tx_power=99)
    assert extract_adv_ref_power_dbm(svc_tx_oor, {}, {}) is None
    assert extract_adv_ref_power_dbm(None, {}, {}) is None
    assert (
        extract_adv_ref_power_dbm(
            None, {}, {"0000feaa-0000-1000-8000-00805f9b34fb": ed_uid_payload}
        )
        == -61.0
    )

    # Floor registry helpers & error resilience
    assert resolve_floor_info(hass, "basement_west") == ("basement_west", "Basement West")
    with patch("homeassistant.helpers.floor_registry.async_get", side_effect=RuntimeError("boom")):
        assert _get_floor_registry(hass) is None

    broken_floor_reg = MagicMock()
    broken_floor_reg.async_list_floors.side_effect = RuntimeError("list fail")
    broken_floor_reg.async_get_floor.side_effect = RuntimeError("get fail")
    with patch(
        "custom_components.latter.presence.ble_registry._get_floor_registry",
        return_value=broken_floor_reg,
    ):
        assert has_configured_floors(hass) is False
        assert resolve_floor_info(hass, "upper_deck") == ("upper_deck", "Upper Deck")

    # Scanner-to-Area resolution paths
    assert resolve_scanner_area_id(hass, "") is None
    assert _resolve_scanner_area_id_uncached(hass, "") is None

    get_global_config(hass)[CONF_BLE_AREA_SIGNATURES] = "invalid-non-dict"
    assert get_ble_signature_area_ids(hass) == set()
    get_global_config(hass)[CONF_BLE_AREA_SIGNATURES] = {}

    # Device 1: no device area_id, but entity has area_id="kitchen" -> resolves exact & adjacent (+2) MAC
    dev_ent_area = register_device(
        hass,
        config_entry_id="esp_ent_area",
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:00:00:40")},
        identifiers={("esphome", "aa:bb:cc:00:00:40")},
        name="Relay Node",
        area_id=None,
    )
    register_entity(
        hass,
        "sensor.relay_node_rssi",
        platform="esphome",
        config_entry_id="esp_ent_area",
        device_id=dev_ent_area.id,
        area_id="kitchen",
    )
    assert resolve_scanner_area_id(hass, "AA:BB:CC:00:00:40") == "kitchen"
    assert resolve_scanner_area_id(hass, "AA:BB:CC:00:00:42") == "kitchen"

    # Device 2: no device or entity area_id, but name contains Area name "Hallway"
    register_device(
        hass,
        config_entry_id="esp_name_area",
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:00:00:50")},
        identifiers={("esphome", "aa:bb:cc:00:00:50")},
        name="Hallway Wall Proxy",
        area_id=None,
    )
    assert resolve_scanner_area_id(hass, "AA:BB:CC:00:00:50") == "hallway"

    # Device 3: no area anywhere and unrelated name -> returns None
    register_device(
        hass,
        config_entry_id="esp_unmapped_dev",
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:00:00:60")},
        identifiers={("esphome", "aa:bb:cc:00:00:60")},
        name="Mystery Box",
        area_id=None,
    )
    assert resolve_scanner_area_id(hass, "AA:BB:CC:00:00:60") is None

    # Device 4: non-MAC source matches device by slugified name
    register_device(
        hass,
        config_entry_id="esp_garage_name",
        identifiers={("esphome", "garage_sensor_id")},
        name="Garage Sensor",
        area_id="garage",
    )
    assert resolve_scanner_area_id(hass, "garage-sensor") == "garage"

    # Area name directly embedded in scanner source text
    assert resolve_scanner_area_id(hass, "proxy-kitchen-north") == "kitchen"

    # Scanner metadata lookup: alternate MAC in scanner.details["source"] and exception resilience
    alt_scanner = MagicMock()
    alt_scanner.name = "Kitchen Relay"
    alt_scanner.details = {"source": "AA:BB:CC:00:00:40"}
    with patch.object(bluetooth, "async_scanner_by_source", return_value=alt_scanner):
        assert resolve_scanner_area_id(hass, "relay_alias") == "kitchen"

    with patch.object(
        bluetooth, "async_scanner_by_source", side_effect=RuntimeError("bt down")
    ):
        assert resolve_scanner_area_id(hass, "proxy-garage-east") == "garage"


async def test_ble_discovery_eddystone_bthome_ibeacon_and_edge_paths(hass: Any) -> None:
    """Cover Eddystone-UID, multi-scanner backfill, BTHome/iBeacon/Private BLE target labels, and dedupe."""
    await prepare_latter_dependencies(hass)
    ensure_area(hass, "Kitchen", area_id="kitchen")
    ensure_area(hass, "Garage", area_id="garage")
    await seed_ble_proxies(
        hass,
        [
            ("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen"),
            ("gar_proxy", "aa:bb:cc:00:00:33", "Garage Proxy", "garage"),
        ],
    )

    t0 = time.monotonic()

    # 1) Live Eddystone-UID advertisement (18 bytes)
    ed_ns_inst = "aabbccddeeff00112233112233445566"
    ed_payload = bytes([0x00, 0xEC]) + bytes.fromhex(ed_ns_inst)
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            "",
            rssi=-58,
            source="AA:BB:CC:00:00:22",
            obs_time=t0,
            address="EE:DD:00:11:22:33",
            service_data={"0000feaa-0000-1000-8000-00805f9b34fb": ed_payload},
        ),
    )

    # 2) Same MAC heard by 2 scanners (both RSSI orderings to guarantee backfill elif branch)
    for addr_pair, r_kit, name_kit, r_gar, name_gar in (
        ("DE:AD:BE:EF:00:01", -50, "", -70, "Backfill Alpha"),
        ("DE:AD:BE:EF:00:02", -70, "Backfill Beta", -50, ""),
    ):
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                "",
                rssi=r_kit,
                source="AA:BB:CC:00:00:22",
                obs_time=t0,
                address=addr_pair,
                local_name=name_kit,
            ),
        )
        inject_ble_adv(
            hass,
            make_ibeacon_service_info(
                "",
                rssi=r_gar,
                source="AA:BB:CC:00:00:33",
                obs_time=t0,
                address=addr_pair,
                local_name=name_gar,
            ),
        )

    # 3) Local name equal to dashed MAC address is stripped to ""
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            "",
            rssi=-63,
            source="AA:BB:CC:00:00:22",
            obs_time=t0,
            address="AA:BB:CC:DD:EE:10",
            local_name="AA-BB-CC-DD-EE-10",
        ),
    )

    # 4) Live Shelly BLU BTHome v2, live iBeacon, and plain Apple advertisements
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            "",
            rssi=-54,
            source="AA:BB:CC:00:00:22",
            obs_time=t0,
            address="38:39:8F:AA:BB:77",
            local_name="SBBT-002C",
            service_data={"0000fcd2-0000-1000-8000-00805f9b34fb": b"\x40\x01\x64\x3a\x01"},
            extra_mfg={0x0B9A: b"\x01\x00"},
        ),
    )
    live_ib_uuid = "22222222-3333-4444-5555-666666666666"
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            live_ib_uuid,
            rssi=-57,
            source="AA:BB:CC:00:00:22",
            obs_time=t0,
            address="11:22:33:44:55:AA",
            major=5,
            minor=6,
        ),
    )
    inject_ble_adv(
        hass,
        make_ibeacon_service_info(
            "",
            rssi=-61,
            source="AA:BB:CC:00:00:22",
            obs_time=t0,
            address="11:22:33:44:55:BB",
            extra_mfg={APPLE_COMPANY_ID: b"\x10\x05\x01\x02"},
        ),
    )

    # describe_ble_target_model raw & MAC branches
    assert describe_ble_target_model(hass, "") == "BLE beacon or tag"
    assert describe_ble_target_model(hass, "bthome:abc") == "BTHome v2 Tag"
    assert describe_ble_target_model(hass, "eddystone:abc") == "Eddystone-UID Beacon"
    assert describe_ble_target_model(hass, "ibeacon:abc") == "iBeacon Tag"
    assert describe_ble_target_model(hass, ed_ns_inst.upper()) == "Eddystone-UID Beacon"
    assert describe_ble_target_model(hass, ed_ns_inst) == "Eddystone-UID Beacon"
    assert describe_ble_target_model(hass, "aabbccddeeff00112233") == "Eddystone-UID Beacon"
    assert describe_ble_target_model(hass, live_ib_uuid) == "iBeacon Tag"
    assert describe_ble_target_model(hass, f"{live_ib_uuid}-5-6") == "iBeacon Tag"
    assert describe_ble_target_model(hass, "not-a-valid-target") == "BLE beacon or tag"
    assert describe_ble_target_model(hass, "11:22:33:44:55:AA") == "iBeacon Tag"
    assert describe_ble_target_model(hass, "11:22:33:44:55:BB") == "BLE beacon or tag"
    assert inspect_companion_ble_transmitter(hass, "sensor.missing_ble_transmitter") is None

    # Entity-based model descriptions (BTHome, offline Private BLE, iBeacon, generic)
    register_entity(
        hass,
        "sensor.orphan_bthome_signal_strength",
        platform="bthome",
        config_entry_id="bthome_orphan",
        unique_id="orphan_bthome_rssi",
    )
    hass.states.async_set(
        "sensor.orphan_bthome_signal_strength",
        "-68",
        {"friendly_name": "Orphan Bthome Signal Strength"},
    )
    assert describe_ble_target_model(hass, "sensor.orphan_bthome_signal_strength") == "BTHome v2 Tag"

    shelly_live_dev = register_device(
        hass,
        config_entry_id="bthome_shelly_live",
        entry_domain="bthome",
        connections={(dr.CONNECTION_BLUETOOTH, "38:39:8f:aa:bb:77")},
        identifiers={("bthome", "38:39:8f:aa:bb:77")},
        name="Shelly BLU Button",
        manufacturer="Shelly",
    )
    dr.async_get(hass).async_update_device(shelly_live_dev.id, name_by_user="Custom Shelly Tag")
    register_entity(
        hass,
        "binary_sensor.shelly_blu_button",
        platform="bthome",
        config_entry_id="bthome_shelly_live",
        device_id=shelly_live_dev.id,
        unique_id="shelly_blu_btn",
    )
    hass.states.async_set("binary_sensor.shelly_blu_button", "off", {})
    assert (
        describe_ble_target_model(hass, "binary_sensor.shelly_blu_button")
        == "Shelly BLU Tag (BTHome v2)"
    )

    shelly_off_dev = register_device(
        hass,
        config_entry_id="bthome_shelly_off",
        entry_domain="bthome",
        connections={
            ("serial", "XYZ-99"),
            (dr.CONNECTION_BLUETOOTH, "38:39:8f:aa:bb:88"),
        },
        identifiers={("bthome", "38:39:8f:aa:bb:88")},
        name="Shelly Offline",
        manufacturer="Shelly",
    )
    register_entity(
        hass,
        "binary_sensor.shelly_off_motion",
        platform="bthome",
        config_entry_id="bthome_shelly_off",
        device_id=shelly_off_dev.id,
        unique_id="shelly_off_motion",
    )
    assert (
        describe_ble_target_model(hass, "binary_sensor.shelly_off_motion")
        == "Shelly BLU Tag (BTHome v2)"
    )

    generic_bt_dev = register_device(
        hass,
        config_entry_id="bthome_gen_off",
        entry_domain="bthome",
        connections={(dr.CONNECTION_BLUETOOTH, "38:39:8f:aa:bb:99")},
        identifiers={("bthome", "38:39:8f:aa:bb:99")},
        name="Generic BTHome",
        manufacturer="VendorX",
    )
    register_entity(
        hass,
        "sensor.generic_bthome_battery",
        platform="bthome",
        config_entry_id="bthome_gen_off",
        device_id=generic_bt_dev.id,
        unique_id="generic_bthome_batt",
    )
    assert describe_ble_target_model(hass, "sensor.generic_bthome_battery") == "BTHome v2 Tag"

    # Filtered-out BTHome & Private BLE domains/suffixes
    register_entity(
        hass,
        "switch.bthome_ignored_switch",
        platform="bthome",
        config_entry_id="bthome_gen_off",
        unique_id="bt_ignored_sw",
    )
    register_entity(
        hass,
        "sensor.bthome_temperature",
        platform="bthome",
        config_entry_id="bthome_gen_off",
        unique_id="bt_ignored_temp",
    )
    register_entity(
        hass,
        "sensor.pble_signal_ignored",
        platform="private_ble_device",
        config_entry_id="pble_misc",
        unique_id="pble_ignored_metric",
    )

    # Offline Private BLE device + already-onboarded Private BLE device group + onboarded-slug entity
    register_entity(
        hass,
        "device_tracker.offline_pble",
        platform="private_ble_device",
        config_entry_id="pble_offline",
        unique_id="pble_offline_irk",
    )
    hass.states.async_set(
        "device_tracker.offline_pble",
        "not_home",
        {"friendly_name": "Offline Phone", "current_address": "59:AA:BB:CC:DD:01"},
    )
    assert (
        describe_ble_target_model(hass, "device_tracker.offline_pble")
        == "Private BLE (phone or watch)"
    )

    onb_pble_dev = register_device(
        hass,
        config_entry_id="pble_onb",
        entry_domain="private_ble_device",
        identifiers={("private_ble_device", "irk_onb")},
        name="Onboarded Watch",
    )
    register_entity(
        hass,
        "device_tracker.onb_watch",
        platform="private_ble_device",
        config_entry_id="pble_onb",
        device_id=onb_pble_dev.id,
        unique_id="irk_onb_tracker",
    )
    register_entity(
        hass,
        "sensor.onb_watch_estimated_distance",
        platform="private_ble_device",
        config_entry_id="pble_onb",
        device_id=onb_pble_dev.id,
        unique_id="irk_onb_dist",
    )
    hass.states.async_set(
        "device_tracker.onb_watch",
        "home",
        {"current_address": "66:77:88:99:AA:BB"},
    )

    register_entity(
        hass,
        "device_tracker.slug_skip_pble",
        platform="private_ble_device",
        config_entry_id="pble_slug_skip",
        unique_id="irk_slug_skip",
    )
    hass.states.async_set(
        "device_tracker.slug_skip_pble",
        "home",
        {"friendly_name": "Already Tracked"},
    )

    # Generic non-BLE-platform entity fallback
    register_entity(
        hass,
        "device_tracker.generic_tracker",
        platform="esphome",
        config_entry_id="esp_gen_trk",
        unique_id="gen_trk_uid",
    )
    assert (
        describe_ble_target_model(hass, "device_tracker.generic_tracker")
        == "Private BLE (phone or watch)"
    )

    # Companion App entities: deviceless suffix-stripped, deviceless unsuffixed, inactive, and onboarded slug
    comp_uuid_a = "aaaaaaaa-1111-2222-3333-444444444444"
    comp_uuid_b = "bbbbbbbb-1111-2222-3333-444444444444"
    comp_uuid_c = "cccccccc-1111-2222-3333-444444444444"
    for eid, st_val, friendly, uid_attr in (
        ("sensor.sam_phone_ble_transmitter", "Transmitting", "Sam Phone BLE Transmitter", f"{comp_uuid_a}-1-1"),
        ("sensor.pat_watch_ble_transmitter", "Transmitting", "Pat Watch", f"{comp_uuid_b}-1-2"),
        ("sensor.off_phone_ble_transmitter", "disabled", "Off Phone BLE Transmitter", f"{comp_uuid_c}-1-3"),
        ("sensor.skip_slug_ble_transmitter", "Transmitting", "Onb Comp BLE Transmitter", f"{comp_uuid_c}-2-4"),
    ):
        register_entity(
            hass,
            eid,
            platform="mobile_app",
            config_entry_id="mobile_app_cov",
            unique_id=f"{eid}_ble_emitter",
        )
        hass.states.async_set(eid, st_val, {"friendly_name": friendly, "id": uid_attr})

    # iBeacon entities: one without parseable UUID, one matching live iBeacon ad without state rssi
    register_entity(
        hass,
        "device_tracker.mystery_ibeacon",
        platform="ibeacon",
        config_entry_id="entry_ib_cov",
        unique_id="no_uuid_here",
    )
    hass.states.async_set("device_tracker.mystery_ibeacon", "home", {"friendly_name": "Mystery Beacon"})
    assert describe_ble_target_model(hass, "device_tracker.mystery_ibeacon") == "iBeacon Tag"

    register_entity(
        hass,
        "device_tracker.live_ib_no_rssi",
        platform="ibeacon",
        config_entry_id="entry_ib_cov",
        unique_id=f"{live_ib_uuid}_5_6_ABCD",
    )
    hass.states.async_set("device_tracker.live_ib_no_rssi", "home", {"friendly_name": "Live Beacon"})

    raw_onb_uuid = "dddddddd-1111-2222-3333-444444444444"
    candidates = get_discovered_ble_candidates(
        hass,
        onboarded_slugs={"onb_comp", "already_tracked"},
        onboarded_addresses={"", "   ", "device_tracker.onb_watch", raw_onb_uuid},
    )
    by_target = {c["target_address"]: c for c in candidates}

    assert by_target["sensor.sam_phone_ble_transmitter"]["title"] == "Sam Phone"
    assert by_target["sensor.pat_watch_ble_transmitter"]["title"] == "Pat Watch"
    assert "sensor.off_phone_ble_transmitter" not in by_target
    assert "sensor.skip_slug_ble_transmitter" not in by_target
    assert "device_tracker.onb_watch" not in by_target
    assert "sensor.onb_watch_estimated_distance" not in by_target
    assert "device_tracker.slug_skip_pble" not in by_target

    assert by_target["binary_sensor.shelly_blu_button"]["title"] == "Custom Shelly Tag"
    assert by_target["binary_sensor.shelly_blu_button"]["kind"] == "Shelly BLU Tag (BTHome v2)"
    assert by_target["binary_sensor.shelly_blu_button"]["rssi"] == -54
    assert by_target["sensor.orphan_bthome_signal_strength"]["title"] == "Orphan Bthome"
    assert by_target["device_tracker.offline_pble"]["kind"] == "Phone or Watch (Private BLE / IRK)"
    assert by_target["device_tracker.mystery_ibeacon"]["kind"] == "iBeacon Tag"
    assert by_target["device_tracker.live_ib_no_rssi"]["rssi"] == -57
    assert by_target["device_tracker.live_ib_no_rssi"]["area_name"] == "Kitchen"
    assert ed_ns_inst.upper() in by_target
    assert by_target["DE:AD:BE:EF:00:01"]["title"] == "Backfill Alpha"
    assert by_target["DE:AD:BE:EF:00:02"]["title"] == "Backfill Beta"

    # Malformed scanner pairs, empty address key, and duplicate scanner source memo hit
    bad_scanner_1 = MagicMock()
    bad_scanner_1.source = "AA:BB:CC:00:00:22"
    bad_scanner_1.name = "Kitchen Proxy"
    bad_scanner_1.discovered_devices_and_advertisement_data = {
        "BAD:PAIR": ("only_one",),
        "": (MagicMock(), MagicMock()),
    }
    bad_scanner_2 = MagicMock()
    bad_scanner_2.source = "AA:BB:CC:00:00:22"
    bad_scanner_2.name = "Kitchen Proxy Dup"
    bad_scanner_2.discovered_devices_and_advertisement_data = {}
    with patch(
        "custom_components.latter.presence.ble_discovery.current_ble_scanners",
        return_value=[bad_scanner_1, bad_scanner_2],
    ):
        idx = _index_live_ble_advertisements(hass)
        assert idx.by_mac == {}

    # Defensive dedupe branch in _consolidate_ibeacon_entities when an entity in group is already in seen_targets
    ent_live_ib = er.async_get(hass).async_get("device_tracker.live_ib_no_rssi")
    assert ent_live_ib is not None
    ctx = _DiscoveryCtx(
        hass=hass,
        dev_reg=dr.async_get(hass),
        area_reg=ar.async_get(hass),
        live_index=_LiveBleIndex(),
        onboarded_slugs=set(),
        seen_targets={"device_tracker.live_ib_no_rssi"},
        onboarded_ibeacons=set(),
        onboarded_uuid_only=set(),
    )
    assert _consolidate_ibeacon_entities(ctx, [ent_live_ib]) == []


async def test_ble_fabric_ibeacon_events_matcher_fallbacks_and_away_tick(
    hass: Any, make_esphome_device: Any
) -> None:
    """Cover BleFabric matcher fallbacks, esphome.ibeacon_seen matching, away tick, and malformed scanner seed."""
    await prepare_latter_dependencies(hass)
    await ensure_bluetooth_manager(hass)
    ensure_area(hass, "Kitchen", area_id="kitchen")
    await seed_ble_proxies(
        hass,
        [("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen")],
    )

    fabric = get_ble_fabric(hass)
    # No occupancy listeners -> rebind returns early; no trackers -> away check returns early
    fabric.rebind_fusion_sensor_listener()
    fabric._async_check_away_timeouts(datetime.now(tz=UTC))

    # Targeted Apple iBeacon BluetoothCallbackMatcher TypeError fallback tiers
    # (manufacturer_id + manufacturer_data_start + connectable -> drop connectable -> manufacturer_id only)
    orig_matcher = bluetooth.BluetoothCallbackMatcher
    seen_matcher_kwargs: list[dict[str, Any]] = []

    def _no_connectable(*args: Any, **kwargs: Any) -> Any:
        seen_matcher_kwargs.append(dict(kwargs))
        if "connectable" in kwargs:
            raise TypeError("no connectable")
        return orig_matcher(*args, **kwargs)

    def _mfg_only(*args: Any, **kwargs: Any) -> Any:
        seen_matcher_kwargs.append(dict(kwargs))
        if "connectable" in kwargs or "manufacturer_data_start" in kwargs:
            raise TypeError("mfg only")
        return orig_matcher(*args, **kwargs)

    with patch.object(bluetooth, "BluetoothCallbackMatcher", side_effect=_no_connectable):
        fabric._async_start_fabric()
        assert fabric._unsub_ble is not None
        assert any(
            kw.get("manufacturer_id") == APPLE_COMPANY_ID
            and kw.get("manufacturer_data_start") == [0x02, 0x15]
            for kw in seen_matcher_kwargs
        )
        fabric._async_stop_fabric()

    seen_matcher_kwargs.clear()
    with patch.object(bluetooth, "BluetoothCallbackMatcher", side_effect=_mfg_only):
        fabric._async_start_fabric()
        assert fabric._unsub_ble is not None
        assert any(
            kw == {"manufacturer_id": APPLE_COMPANY_ID}
            for kw in seen_matcher_kwargs
        )
        orphan_sensor_unsub = MagicMock()
        fabric._unsub_sensor_events = orphan_sensor_unsub
        fabric._async_stop_fabric()
        orphan_sensor_unsub.assert_called_once()
        assert fabric._unsub_sensor_events is None

    # Fusion sensor listener ignores attribute-only updates where state string is unchanged
    register_entity(
        hass,
        "binary_sensor.kitchen_pir",
        platform="mqtt",
        config_entry_id="mqtt_pir",
        area_id="kitchen",
        original_device_class="motion",
    )
    hass.states.async_set(
        "binary_sensor.kitchen_pir",
        "on",
        {"device_class": "motion"},
    )
    occ_calls: list[int] = []
    unsub_occ = fabric.register_occupancy_listener(lambda: occ_calls.append(1))
    occ_calls.clear()
    hass.states.async_set(
        "binary_sensor.kitchen_pir",
        "on",
        {"device_class": "motion", "battery": 95},
    )
    await hass.async_block_till_done()
    assert occ_calls == []

    # Real ESPHome device + native BLE tracker for esphome.ibeacon_seen & periodic away check
    esp_dev, esp_mac = make_esphome_device(
        hass, slug="fabric_unit", mac="aa:bb:cc:dd:ee:01", area_id="kitchen"
    )
    detected_areas: list[tuple[str, str]] = []
    tracker = LatterNativeBleTracker(
        hass,
        beacon_uuid=DEFAULT_BLE_BEACON_UUID,
        device_slug="fabric_unit",
        on_area_detected=lambda area_id, src: detected_areas.append((area_id, src)),
        esphome_device_id=esp_dev.id,
        manifest_beacon={"uuid": DEFAULT_BLE_BEACON_UUID, "major": 1, "minor": 1},
    )
    tracker.async_start()
    try:
        # Invalid esphome.ibeacon_seen (missing source / rssi <= -100)
        hass.bus.async_fire("esphome.ibeacon_seen", {"source": "", "uuid": DEFAULT_BLE_BEACON_UUID, "rssi": -50})
        hass.bus.async_fire(
            "esphome.ibeacon_seen",
            {"source": "AA:BB:CC:00:00:22", "uuid": DEFAULT_BLE_BEACON_UUID, "rssi": -105},
        )
        # Non-matching UUID
        hass.bus.async_fire(
            "esphome.ibeacon_seen",
            {"source": "AA:BB:CC:00:00:22", "uuid": "11111111-1111-1111-1111-111111111111", "rssi": -55},
        )
        # Matching UUID + unknown MAC + wrong major
        hass.bus.async_fire(
            "esphome.ibeacon_seen",
            {
                "source": "AA:BB:CC:00:00:22",
                "uuid": DEFAULT_BLE_BEACON_UUID,
                "address": "99:88:77:66:55:44",
                "major": 99,
                "minor": 1,
                "rssi": -55,
            },
        )
        await hass.async_block_till_done()
        assert tracker.packets_seen == 0

        # Matching UUID + MAC in _target_mac_ints
        hass.bus.async_fire(
            "esphome.ibeacon_seen",
            {
                "source": "AA:BB:CC:00:00:22",
                "uuid": DEFAULT_BLE_BEACON_UUID,
                "address": esp_mac,
                "major": 77,
                "minor": 88,
                "rssi": -55,
            },
        )
        await hass.async_block_till_done()
        assert tracker.packets_seen == 1
        assert tracker.current_area_id == "kitchen"

        # Matching UUID + unknown MAC + matching major=1 & minor=1
        hass.bus.async_fire(
            "esphome.ibeacon_seen",
            {
                "source": "AA:BB:CC:00:00:22",
                "uuid": DEFAULT_BLE_BEACON_UUID,
                "address": "99:88:77:66:55:44",
                "major": 1,
                "minor": 1,
                "rssi": -52,
            },
        )
        await hass.async_block_till_done()
        assert tracker.packets_seen == 2

        # Away check tick re-seeds stale/zero tracker & discovers bound MACs
        tracker._target_mac_ints.clear()
        tracker._last_mac_discovery_mono = 0.0
        tracker.packets_seen = 0
        fabric._async_check_away_timeouts(datetime.now(tz=UTC))
        assert bool(tracker._target_mac_ints)

        # Malformed scanner seeding: empty source, bad tuple, adv_data.rssi=None fallback, weak <= -100 skip
        empty_src_scanner = SimpleNamespace(
            source="",
            name="Empty",
            discovered_device_timestamps={},
            discovered_devices_and_advertisement_data={},
        )

        ble_dev_ok = SimpleNamespace(rssi=-61)
        adv_no_rssi = SimpleNamespace(
            manufacturer_data={}, service_data={}, rssi=None, tx_power=None
        )
        ble_dev_weak = SimpleNamespace(rssi=-105)
        adv_no_rssi_weak = SimpleNamespace(
            manufacturer_data={}, service_data={}, rssi=None, tx_power=None
        )

        edge_scanner = SimpleNamespace(
            source="AA:BB:CC:00:00:22",
            name="Kitchen Proxy",
            discovered_device_timestamps={},
            discovered_devices_and_advertisement_data={
                "BAD:PAIR": ("only_one",),
                "AA:BB:CC:DD:EE:01": (ble_dev_ok, adv_no_rssi),
                "AA:BB:CC:DD:EE:03": (ble_dev_weak, adv_no_rssi_weak),
            },
        )
        before_pkts = tracker.packets_seen
        tracker._last_adv_ts_by_scanner.clear()
        with patch(
            "custom_components.latter.presence.ble_fabric.current_ble_scanners",
            return_value=[empty_src_scanner, edge_scanner],
        ):
            fabric.seed_tracker_from_scanners_once(tracker)
        assert tracker.packets_seen == before_pkts + 1
    finally:
        tracker.async_stop()
        unsub_occ()


async def test_ble_tracker_pure_math_cleaning_and_signature_edge_cases(hass: Any) -> None:
    """Cover tracker helper guards: empty device MACs, 1-sample median, ring trim, signature/param cleaners."""
    assert discover_target_device_macs(hass, "nonexistent_device_id") == set()
    assert _median_of_recent([-60.0]) == -60.0

    # Ring buffer trim beyond SIGNATURE_RING_MAX_SAMPLES (32)
    states: dict[str, Any] = {}
    t0 = time.monotonic()
    for idx in range(36):
        st = update_scanner_kalman_state(
            states,
            "AA:BB:CC:00:00:11",
            -58,
            t0 + idx * 0.2,
            "Proxy 1",
            offset_db=0.0,
            ref_shift=0.0,
            attenuation=2.4,
            max_velocity_mps=3.5,
        )
    assert len(st.ring_buffer) == 32

    # score_signature_vector edge cases
    assert (
        score_signature_vector(
            "kitchen",
            {"scanners": {}},
            fresh_norm={"AA:BB:CC:00:00:11": -60.0},
            fresh_ages={"AA:BB:CC:00:00:11": 0.5},
            resolve_scanner_area=lambda _s: "kitchen",
            is_cross_floor=lambda _a: False,
        )
        is None
    )
    assert (
        score_signature_vector(
            "kitchen",
            {"scanners": {"AA:BB:CC:00:00:99": {"mean": -60.0, "std": 3.5}}},
            fresh_norm={"AA:BB:CC:00:00:11": -60.0},
            fresh_ages={"AA:BB:CC:00:00:11": 0.5},
            resolve_scanner_area=lambda _s: "kitchen",
            is_cross_floor=lambda _a: False,
        )
        is None
    )
    assert (
        score_signature_vector(
            "kitchen",
            {"scanners": {"AA:BB:CC:00:00:11": "not-a-mapping"}},
            fresh_norm={"AA:BB:CC:00:00:11": -60.0},
            fresh_ages={"AA:BB:CC:00:00:11": 0.5},
            resolve_scanner_area=lambda _s: "kitchen",
            is_cross_floor=lambda _a: False,
        )
        is None
    )
    same_floor = score_signature_vector(
        "kitchen",
        {"scanners": {"AA:BB:CC:00:00:11": {"mean": -60.0, "std": 3.5}}},
        fresh_norm={"AA:BB:CC:00:00:11": -60.0},
        fresh_ages={"AA:BB:CC:00:00:11": 0.5},
        resolve_scanner_area=lambda _s: "kitchen",
        is_cross_floor=lambda _a: False,
    )
    cross_floor = score_signature_vector(
        "kitchen",
        {"scanners": {"AA:BB:CC:00:00:11": {"mean": -60.0, "std": 3.5}}},
        fresh_norm={"AA:BB:CC:00:00:11": -60.0},
        fresh_ages={"AA:BB:CC:00:00:11": 0.5},
        resolve_scanner_area=lambda _s: "kitchen",
        is_cross_floor=lambda _a: True,
    )
    assert same_floor is not None and cross_floor is not None
    assert abs((same_floor[0] - cross_floor[0]) - 6.0) < 1e-6

    # Offsets, signatures, and float clamp cleaners
    assert _clean_scanner_offsets(
        {"aa:bb:cc:00:00:11": "bad", "aa:bb:cc:00:00:22": 4.0}  # type: ignore[dict-item]
    ) == {"AA:BB:CC:00:00:22": 4.0}
    cleaned_sigs = _clean_area_signatures_map(
        {
            "empty_area": {"scanners": {}},
            "kitchen": {
                "scanners": {
                    "": {"mean": -60.0},
                    "AA:BB:CC:00:00:11": "bad-stats",
                    "AA:BB:CC:00:00:22": {"mean": "not-a-float"},
                    "AA:BB:CC:00:00:33": {"mean": -65.0, "std": 3.0, "n": 4},
                }
            },
        }
    )
    assert list(cleaned_sigs) == ["kitchen"]
    assert list(cleaned_sigs["kitchen"]["scanners"]) == ["AA:BB:CC:00:00:33"]

    assert _clamp_float_param(True, 1.0, 5.0, 2.5) == 2.5
    assert _clamp_float_param(None, 1.0, 5.0, 2.5) == 2.5
    assert _clamp_float_param("not-a-float", 1.0, 5.0, 2.5) == 2.5
    assert _clamp_float_param(10.0, 1.0, 5.0, 2.5) == 5.0


async def test_ble_tracker_targets_matching_rpa_pruning_and_entity_fallbacks(
    hass: Any, make_esphome_device: Any
) -> None:
    """Cover target parsing, entity MAC fallbacks, RPA bounding/pruning, manifest beacon, and wake hooks."""
    await prepare_latter_dependencies(hass)
    await ensure_bluetooth_manager(hass)
    ensure_area(hass, "Kitchen", area_id="kitchen")

    sample_uuid = "008fd71e-a43a-4ab4-8e02-f969133f8380"
    sample_hex = sample_uuid.replace("-", "")
    ed_ns = "aabbccddeeff00112233"

    # Explicit target parsing variants: direct iBeacon, Eddystone 20-hex NS, colon-suffixed 32-hex & 20-hex
    trk_ib = LatterNativeBleTracker(
        hass,
        beacon_uuid="",
        device_slug="tag_ib",
        on_area_detected=lambda _a, _s: None,
        target_address=f"{sample_uuid}-42-7",
    )
    assert (trk_ib._target_uuid_hex, trk_ib._explicit_major, trk_ib._explicit_minor) == (
        sample_hex,
        42,
        7,
    )

    trk_ed_ns = LatterNativeBleTracker(
        hass,
        beacon_uuid="",
        device_slug="tag_ed_ns",
        on_area_detected=lambda _a, _s: None,
        target_address=f"eddystone:{ed_ns}",
    )
    assert trk_ed_ns._target_eddystone_namespace_hex == ed_ns
    ed_svc = {"0000feaa-0000-1000-8000-00805f9b34fb": bytes([0x00, 0xEC]) + bytes.fromhex(f"{ed_ns}112233445566")}
    assert trk_ed_ns._matches_raw_adv("00:11:22:33:44:55", {}, ed_svc) is True

    trk_colon_uuid = LatterNativeBleTracker(
        hass,
        beacon_uuid="",
        device_slug="tag_cu",
        on_area_detected=lambda _a, _s: None,
        target_address=f"eddystone:{sample_uuid}:dead",
    )
    assert trk_colon_uuid._target_uuid_hex == sample_hex

    trk_colon_ns = LatterNativeBleTracker(
        hass,
        beacon_uuid="",
        device_slug="tag_cn",
        on_area_detected=lambda _a, _s: None,
        target_address=f"eddystone:{ed_ns}:dead",
    )
    assert trk_colon_ns._target_eddystone_namespace_hex == ed_ns

    # Entity targets: ibeacon entity without state (unique_id fallback) & BTHome device MAC fallbacks
    register_entity(
        hass,
        "device_tracker.ib_stateless",
        platform="ibeacon",
        config_entry_id="ib_ent_cov",
        unique_id=f"{sample_uuid}_12_34_ABCD",
    )
    trk_ib_ent = LatterNativeBleTracker(
        hass,
        beacon_uuid="",
        device_slug="ib_stateless",
        on_area_detected=lambda _a, _s: None,
        target_address="device_tracker.ib_stateless",
    )
    assert (trk_ib_ent._target_uuid_hex, trk_ib_ent._explicit_major, trk_ib_ent._explicit_minor) == (
        sample_hex,
        12,
        34,
    )

    bt_conn_dev = register_device(
        hass,
        config_entry_id="bt_conn_cov",
        entry_domain="bthome",
        connections={(dr.CONNECTION_BLUETOOTH, "38:39:8f:aa:bb:11")},
        identifiers={("bthome", "non_mac_id_1")},
        name="BT Conn Tag",
    )
    register_entity(
        hass,
        "binary_sensor.bt_conn_btn",
        platform="bthome",
        config_entry_id="bt_conn_cov",
        device_id=bt_conn_dev.id,
        unique_id="bt_conn_btn",
    )
    trk_bt_conn = LatterNativeBleTracker(
        hass,
        beacon_uuid="",
        device_slug="bt_conn",
        on_area_detected=lambda _a, _s: None,
        target_address="binary_sensor.bt_conn_btn",
    )
    assert trk_bt_conn._dynamic_target_mac_str == "38:39:8F:AA:BB:11"

    bt_ident_dev = register_device(
        hass,
        config_entry_id="bt_ident_cov",
        entry_domain="bthome",
        identifiers={("bthome", "38:39:8f:aa:bb:22")},
        name="BT Ident Tag",
    )
    register_entity(
        hass,
        "binary_sensor.bt_ident_btn",
        platform="bthome",
        config_entry_id="bt_ident_cov",
        device_id=bt_ident_dev.id,
        unique_id="bt_ident_btn",
    )
    trk_bt_ident = LatterNativeBleTracker(
        hass,
        beacon_uuid="",
        device_slug="bt_ident",
        on_area_detected=lambda _a, _s: None,
        target_address="binary_sensor.bt_ident_btn",
    )
    assert trk_bt_ident._dynamic_target_mac_str == "38:39:8F:AA:BB:22"

    bt_nomac_dev = register_device(
        hass,
        config_entry_id="bt_nomac_cov",
        entry_domain="bthome",
        identifiers={("bthome", "just_a_slug")},
        name="BT NoMac Tag",
    )
    bt_nomac_ent = register_entity(
        hass,
        "binary_sensor.bt_nomac_btn",
        platform="bthome",
        config_entry_id="bt_nomac_cov",
        device_id=bt_nomac_dev.id,
        unique_id="bt_nomac_btn",
    )
    assert trk_bt_ident._fallback_device_mac_for_entity(None) == ""
    assert trk_bt_ident._fallback_device_mac_for_entity(bt_nomac_ent) == ""
    missing_dev_reg = MagicMock()
    missing_dev_reg.async_get.return_value = None
    with patch(
        "custom_components.latter.presence.ble_tracker.dr.async_get",
        return_value=missing_dev_reg,
    ):
        assert trk_bt_ident._fallback_device_mac_for_entity(bt_nomac_ent) == ""

    # Entity state removal triggers _async_on_target_entity_state_change early return (new_state is None)
    hass.states.async_set(
        "device_tracker.pble_rem",
        "home",
        {"current_address": "51:AA:BB:CC:DD:11"},
    )
    trk_ent_rem = LatterNativeBleTracker(
        hass,
        beacon_uuid="",
        device_slug="pble_rem",
        on_area_detected=lambda _a, _s: None,
        target_address="device_tracker.pble_rem",
    )
    trk_ent_rem.async_start()
    try:
        # Empty address ignored; non-matching dynamic RPA ignored; bad dynamic MAC ignored; stale address cleared
        trk_ent_rem._record_matched_ble_address("")
        trk_ent_rem._record_matched_ble_address("51:AA:BB:CC:DD:99")
        assert "51:AA:BB:CC:DD:99" not in trk_ent_rem._matched_ble_addresses

        trk_ent_rem._apply_dynamic_entity_mac("not-a-mac")
        trk_ent_rem._matched_ble_addresses["11:22:33:44:55:99"] = time.monotonic()
        trk_ent_rem._apply_dynamic_entity_mac("51:AA:BB:CC:DD:22")
        assert "11:22:33:44:55:99" not in trk_ent_rem._matched_ble_addresses
        assert trk_ent_rem._dynamic_target_mac_str == "51:AA:BB:CC:DD:22"

        # State removal hits new_state is None guard
        hass.states.async_remove("device_tracker.pble_rem")
        await hass.async_block_till_done()
    finally:
        trk_ent_rem.async_stop()

    # Matched address capacity eviction (> 64), TTL pruning, and explicit major-only + matched-address matching
    fabric = get_ble_fabric(hass)
    occ_hits: list[int] = []
    unsub_occ = fabric.register_occupancy_listener(lambda: occ_hits.append(1))
    trk_pool = LatterNativeBleTracker(
        hass,
        beacon_uuid="",
        device_slug="tag_pool",
        on_area_detected=lambda _a, _s: None,
    )
    trk_pool.async_start()
    try:
        for i in range(66):
            trk_pool._record_matched_ble_address(f"AA:BB:CC:00:01:{i:02X}", seed_scanners=False)
        assert len(trk_pool._matched_ble_addresses) == 64

        # Matched address without UUID/Eddystone matches raw adv
        kept_addr = next(iter(trk_pool._matched_ble_addresses))
        assert trk_pool._matches_raw_adv(kept_addr, {}, {}) is True

        # Prune expired RPAs while keeping dynamic MAC & static _target_mac_ints, then trigger sync via check_away_timeout
        now_m = time.monotonic()
        dyn_mac = "51:AA:BB:CC:DD:01"
        stat_mac = "51:AA:BB:CC:DD:02"
        exp_mac = "51:AA:BB:CC:DD:03"
        stat_int = mac_to_int(stat_mac)
        assert stat_int is not None
        trk_pool._matched_ble_addresses.clear()
        trk_pool._dynamic_target_mac_str = dyn_mac
        trk_pool._target_mac_ints.add(stat_int)
        old_ts = now_m - MATCHED_BLE_ADDRESS_TTL_SECONDS - 60.0
        trk_pool._matched_ble_addresses[dyn_mac] = old_ts
        trk_pool._matched_ble_addresses[stat_mac] = old_ts
        trk_pool._matched_ble_addresses[exp_mac] = old_ts
        trk_pool.check_away_timeout(now_m)
        assert dyn_mac in trk_pool._matched_ble_addresses
        assert stat_mac in trk_pool._matched_ble_addresses
        assert exp_mac not in trk_pool._matched_ble_addresses

        # Explicit major only (_explicit_minor is None) matches any minor
        trk_pool._target_uuid_hex = sample_hex
        trk_pool._explicit_major = 42
        trk_pool._explicit_minor = None
        payload = IBEACON_PREFIX + bytes.fromhex(sample_hex) + (42).to_bytes(2, "big") + (999).to_bytes(2, "big")
        assert trk_pool._matches_ibeacon_payload(payload) is True

        # Bad ref_power string, set_area_signatures, set_ref_power
        trk_pool.configure_spatial_engine(ref_power_dbm="invalid-ref", re_evaluate=False)
        assert trk_pool._configured_ref_power_dbm is None
        trk_pool.set_area_signatures({"kitchen": {"scanners": {"AA:BB:CC:00:00:22": {"mean": -60.0, "std": 3.5, "n": 3}}}})
        assert "kitchen" in trk_pool._area_signatures
        trk_pool.set_ref_power(-62.0)
        assert trk_pool._configured_ref_power_dbm == -62.0

        # note_ble_radio_active & reset_for_device_wake (recent packet) while is_away=True notify occupancy listeners
        occ_hits.clear()
        trk_pool.is_away = True
        trk_pool.note_ble_radio_active()
        assert trk_pool.is_away is False
        assert len(occ_hits) >= 1

        occ_hits.clear()
        trk_pool.is_away = True
        trk_pool.last_packet_monotonic = time.monotonic()
        trk_pool.reset_for_device_wake()
        assert trk_pool.is_away is False
        assert len(occ_hits) >= 1
    finally:
        trk_pool.async_stop()
        unsub_occ()

    # Manifest beacon loading (nested beacon dict + normalized major/minor) & maybe_discover_bound_macs
    esp_dev_a, _ = make_esphome_device(
        hass, slug="manifest_nested", mac="aa:bb:cc:dd:ee:21", area_id="kitchen"
    )
    trk_nested = LatterNativeBleTracker(
        hass,
        beacon_uuid=DEFAULT_BLE_BEACON_UUID,
        device_slug="manifest_nested",
        on_area_detected=lambda _a, _s: None,
        esphome_device_id=esp_dev_a.id,
        manifest_beacon={"major": 2, "minor": 9},
    )
    assert trk_nested._resolve_beacon_major_minor() == (2, 9)
    trk_nested.update_manifest_beacon({"major": 2, "minor": 9, "ref_power": -63})
    assert trk_nested.detected_ref_power_dbm == -63.0

    esp_dev_b, _ = make_esphome_device(
        hass, slug="manifest_flat", mac="aa:bb:cc:dd:ee:31", area_id="kitchen"
    )
    trk_flat = LatterNativeBleTracker(
        hass,
        beacon_uuid=DEFAULT_BLE_BEACON_UUID,
        device_slug="manifest_flat",
        on_area_detected=lambda _a, _s: None,
        esphome_device_id=esp_dev_b.id,
        manifest_beacon={"major": 1, "minor": 7},
    )
    assert trk_flat._resolve_beacon_major_minor() == (1, 7)

    # maybe_discover_bound_macs: False when interval not elapsed, True when elapsed, False when populated
    now_disc = time.monotonic()
    trk_flat._last_mac_discovery_mono = now_disc
    assert trk_flat.maybe_discover_bound_macs(now_disc + 5.0, 30.0) is False
    assert trk_flat.maybe_discover_bound_macs(now_disc + 40.0, 30.0) is True
    assert trk_flat.maybe_discover_bound_macs(now_disc + 80.0, 30.0) is False


async def test_ble_tracker_scoring_calibration_and_commit_edge_cases(
    hass: Any, make_esphome_device: Any
) -> None:
    """Cover advertisement guards, early MAC discovery, unmapped signatures, calibration names, and weak scores."""
    await prepare_latter_dependencies(hass)
    await ensure_bluetooth_manager(hass)
    ensure_area(hass, "Kitchen", area_id="kitchen")
    ensure_area(hass, "Garage", area_id="garage")
    ensure_area(hass, "Patio", area_id="patio")
    await seed_ble_proxies(
        hass,
        [("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen")],
    )

    # Register an unregistered-as-scanner HA device for adjacent-MAC display name lookup
    register_device(
        hass,
        config_entry_id="esp_basement_proxy",
        connections={(dr.CONNECTION_NETWORK_MAC, "bb:cc:dd:00:00:10")},
        identifiers={("esphome", "bb:cc:dd:00:00:10")},
        name="Basement Proxy",
        area_id=None,
    )

    esp_dev, _ = make_esphome_device(
        hass, slug="score_unit", mac="aa:bb:cc:dd:ee:41", area_id="kitchen"
    )
    fabric = get_ble_fabric(hass)
    survey_events: list[Any] = []
    unsub_survey = fabric.register_survey_listener(lambda t: survey_events.append(t))

    detected: list[tuple[str, str]] = []
    tracker = LatterNativeBleTracker(
        hass,
        beacon_uuid=DEFAULT_BLE_BEACON_UUID,
        device_slug="score_unit",
        on_area_detected=lambda area_id, src: detected.append((area_id, src)),
        esphome_device_id=esp_dev.id,
        manifest_beacon={"uuid": DEFAULT_BLE_BEACON_UUID, "major": 1, "minor": 1},
        max_radius_m=50.0,
    )
    tracker.async_start()
    try:
        now = time.monotonic()

        # Advertisement guard: matching packet with rssi <= -100 is ignored
        bad_adv = make_ibeacon_service_info(
            DEFAULT_BLE_BEACON_UUID,
            rssi=-105,
            source="AA:BB:CC:00:00:22",
            obs_time=now,
            address="AA:BB:CC:DD:EE:41",
        )
        tracker._async_on_ble_advertisement(bad_adv, None)
        assert tracker.packets_seen == 0

        # Empty source ignored
        tracker._ingest_proxy_observation("", -55, now)
        assert tracker.packets_seen == 0

        # Early MAC discovery when _target_mac_ints was empty on first packet
        tracker._target_mac_ints.clear()
        tracker.set_area_signatures(
            {
                "patio": {"scanners": {"99:88:77:66:55:44": {"mean": -62.0, "std": 3.5, "n": 5}}},
                "garage": {"scanners": {"77:77:77:77:77:77": {"mean": -60.0, "std": 3.5, "n": 5}}},
            }
        )
        # Unmapped scanner observation triggers signature evaluation & early MAC discovery
        tracker._ingest_proxy_observation("99:88:77:66:55:44", -62, now, "Patio Relay")
        assert bool(tracker._target_mac_ints)
        assert "99:88:77:66:55:44" in tracker._unmapped_rssi
        assert tracker.current_area_id == "patio"
        assert tracker.match_method == "signature"

        # Calibration telemetry: unregistered scanner_states display name, adjacent-MAC device name, and _unmapped_rssi fallback
        tracker._unmapped_rssi["BB:CC:DD:00:00:12"] = (-68, now)
        cal_rows = tracker.get_scanner_calibration_telemetry()
        by_src = {r["scanner_source"]: r for r in cal_rows}
        assert by_src["99:88:77:66:55:44"]["scanner_name"] == "Patio Relay"
        assert by_src["BB:CC:DD:00:00:12"]["scanner_name"] == "Basement Proxy"
        assert by_src["BB:CC:DD:00:00:12"]["raw_rssi"] == -68

        # Stale scanner (> 15s) skipped in capture_area_signature and _collect_area_scores
        tracker._scanner_states["99:88:77:66:55:44"].last_obs_time = now - 30.0
        assert tracker.capture_area_signature() == {}
        tracker._evaluate_best_area(now)

        # _apply_winner_metrics missing key, and _commit_area_decision fallback to latest_source
        tracker._apply_winner_metrics("unknown_area", {})
        tracker.current_area_id = "kitchen"
        tracker.closest_scanner = ""
        tracker._commit_area_decision(
            now,
            "AA:BB:CC:00:00:22",
            AreaDecision("kitchen", -55.0, -55.0, False),
            {},
        )
        assert tracker.closest_scanner == "AA:BB:CC:00:00:22"

        tracker.closest_scanner = ""
        tracker._commit_area_decision(
            now,
            "AA:BB:CC:00:00:33",
            AreaDecision("garage", -50.0, -70.0, True),
            {},
        )
        assert tracker.current_area_id == "garage"
        assert tracker.closest_scanner == "AA:BB:CC:00:00:33"

        # Weak decayed score (< MIN_WINNING_RSSI_DBM = -88.0) -> decide_area returns None -> survey delta emitted
        tracker.set_area_signatures({})
        tracker._scanner_states.clear()
        tracker.current_area_id = None
        survey_events.clear()
        t_weak = time.monotonic()
        update_scanner_kalman_state(
            tracker._scanner_states,
            "AA:BB:CC:00:00:22",
            -86,
            t_weak - 6.0,
            "Kitchen Proxy",
            offset_db=0.0,
            ref_shift=0.0,
            attenuation=tracker._attenuation,
            max_velocity_mps=tracker._max_velocity_mps,
        )
        tracker._evaluate_best_area(t_weak)
        assert tracker.current_area_id is None
        assert len(survey_events) >= 1
        assert survey_events[-1] is tracker
    finally:
        tracker.async_stop()
        unsub_survey()


async def test_ble_fabric_targeted_matchers_conditional_eddystone_and_rpa_pruning(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify O(1) targeted Apple iBeacon + conditional Eddystone matchers and ESPHome RPA TTL pruning."""
    await prepare_latter_dependencies(hass)
    await ensure_bluetooth_manager(hass)
    ensure_area(hass, "Kitchen", area_id="kitchen")
    await seed_ble_proxies(
        hass,
        [("kit_proxy", "aa:bb:cc:00:00:22", "Kitchen Proxy", "kitchen")],
    )

    esp_dev, esp_mac = make_esphome_device(
        hass, slug="rpa_unit", mac="aa:bb:cc:dd:ee:77", area_id="kitchen"
    )
    fabric = get_ble_fabric(hass)

    ibeacon_tracker = LatterNativeBleTracker(
        hass,
        beacon_uuid=DEFAULT_BLE_BEACON_UUID,
        device_slug="rpa_unit",
        on_area_detected=lambda _a, _s: None,
        esphome_device_id=esp_dev.id,
        manifest_beacon={"uuid": DEFAULT_BLE_BEACON_UUID, "major": 1, "minor": 1},
        subentry_id="sub_rpa_unit",
    )
    eddy_uid = "00112233445566778899aabbccddeeff"
    eddy_tracker = LatterNativeBleTracker(
        hass,
        beacon_uuid="",
        device_slug="eddy_tag",
        on_area_detected=lambda _a, _s: None,
        target_address=f"eddystone:{eddy_uid}",
        subentry_id="sub_eddy_only",
    )

    ibeacon_tracker.async_start()
    try:
        # 1) Conditional Eddystone matcher stays unregistered while only iBeacon trackers run
        assert fabric._unsub_ble is not None
        assert fabric._unsub_eddystone is None
        assert ibeacon_tracker.wants_eddystone_matcher is False

        # Non-iBeacon Apple Continuity packet (prefix 0x10 0x05) is filtered out before fabric callback
        from custom_components.latter.presence import ble_fabric as ble_fabric_mod

        t0 = time.monotonic()
        with patch.object(
            ble_fabric_mod,
            "_extract_adv_keys",
            wraps=ble_fabric_mod._extract_adv_keys,
        ) as parse_spy:
            continuity_adv = make_ibeacon_service_info(
                "",
                rssi=-55,
                source="AA:BB:CC:00:00:22",
                obs_time=t0,
                address="66:77:88:99:AA:BB",
                connectable=False,
                extra_mfg={APPLE_COMPANY_ID: b"\x10\x05\x01\x02\x03\x04"},
            )
            inject_ble_adv(hass, continuity_adv)
            assert parse_spy.call_count == 0

            # Real Apple iBeacon frame matches targeted matcher & dispatches in O(1)
            inject_ble_adv(
                hass,
                make_ibeacon_service_info(
                    DEFAULT_BLE_BEACON_UUID,
                    rssi=-55,
                    source="AA:BB:CC:00:00:22",
                    obs_time=t0 + 0.1,
                    address=esp_mac.upper(),
                    major=1,
                    minor=1,
                ),
            )
            assert parse_spy.call_count >= 1
            assert ibeacon_tracker.packets_seen >= 1
            assert ibeacon_tracker.packets_seen == 1

        # 2) Starting an Eddystone tracker registers the conditional Eddystone matcher; stopping removes it
        assert eddy_tracker.wants_eddystone_matcher is True
        eddy_tracker.async_start()
        try:
            assert fabric._unsub_eddystone is not None
        finally:
            eddy_tracker.async_stop()
        assert fabric._unsub_eddystone is None

        # 3) `_prune_expired_matched_ble_addresses` prunes stale RPAs on ESPHome devices while keeping bound MACs
        bound_mac = esp_mac.upper()
        stale_rpa = "55:44:33:22:11:00"
        ibeacon_tracker._matched_ble_addresses = {
            bound_mac: t0 - MATCHED_BLE_ADDRESS_TTL_SECONDS - 60.0,
            stale_rpa: t0 - MATCHED_BLE_ADDRESS_TTL_SECONDS - 120.0,
        }
        ibeacon_tracker._prune_expired_matched_ble_addresses(t0)
        assert bound_mac in ibeacon_tracker._matched_ble_addresses
        assert stale_rpa not in ibeacon_tracker._matched_ble_addresses
    finally:
        ibeacon_tracker.async_stop()
