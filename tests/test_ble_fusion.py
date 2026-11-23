"""Tests for sensor fusion modes, Voice Follows Me invariant, static assigned Area two-way sync, RPA rotation, and floor entities."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.storage import Store
from homeassistant.setup import async_setup_component

from custom_components.latter.areas.registry import resolve_active_area_entry
from custom_components.latter.const import (
    CONF_AREA_FUSION_CONFIG,
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEFAULT_AREA,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    CONF_NATIVE_BLE_TRACKING,
    CONF_SYNC_DEVICE_AREA,
    DOMAIN,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
)
from custom_components.latter.groups.device_groups import coordinator_supports_pref
from custom_components.latter.hub_registry import get_global_config
from custom_components.latter.presence.ble_fabric import (
    get_all_areas_presence_summary,
    get_ble_fabric,
)
from custom_components.latter.presence.ble_registry import (
    AWAY_TIMEOUT_SECONDS,
    has_configured_floors,
)
from custom_components.latter.protocol_specs import DEVICE_PREF_SPEC_MAP
from custom_components.latter.studio.payload import build_studio_state_payload
from custom_components.latter.studio.settings_cleaners import clean_device_settings
from tests.helpers import (
    add_mock_entry,
    ensure_area,
    ensure_bluetooth_manager,
    ensure_floor,
    flush_debouncers,
    inject_ble_adv,
    make_ibeacon_service_info,
    make_subentry_dict,
    prepare_latter_dependencies,
    register_device,
    register_entity,
    seed_ble_proxies,
)


async def test_sensor_fusion_modes_and_voice_follows_me_invariant(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify honest 'weighted' / boolean fusion modes, targeted sensor listeners, and Voice Follows Me roaming sync."""
    await seed_ble_proxies(hass)
    ent_reg = er.async_get(hass)
    register_entity(
        hass,
        "binary_sensor.kitchen_pir",
        platform="zwave_js",
        config_entry_id="zwave_entry",
        area_id="kitchen",
        original_device_class="motion",
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
    get_global_config(hass)[CONF_AREA_FUSION_CONFIG] = {
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
        get_global_config(hass)[CONF_AREA_FUSION_CONFIG]["kitchen"]["mode"] = mode
        res = fabric.get_area_occupancy("kitchen")
        assert res["fusion_mode"] == mode
        assert res["is_occupied"] is expected_occ

    # ble_and_sensor fails closed when physical sensor is unavailable or unknown, even with BLE present
    assert coord.ble_tracker is not None
    t_ble = time.monotonic()
    for step in range(3):
        coord.ble_tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:22", -48, t_ble + step * 0.2, "Kitchen Proxy"
        )
    assert coord.ble_tracker.current_area_id == "kitchen"
    assert fabric.get_area_occupancy("kitchen")["is_occupied"] is True
    for bad_st in ("unavailable", "unknown"):
        hass.states.async_set(
            "binary_sensor.kitchen_pir",
            bad_st,
            {"device_class": "motion", "friendly_name": "Kitchen PIR"},
        )
        occ_closed = fabric.get_area_occupancy("kitchen")
        assert occ_closed["is_occupied"] is False
        assert occ_closed["confidence_pct"] == 0
        assert "binary_sensor.kitchen_pir" in occ_closed["unavailable_sensors"]

    # Area occupancy entity uses HA native `binary_sensor.latter_system_<area>_occupancy` and never self-feeds back into fusion
    kitchen_occ_eid = "binary_sensor.latter_system_kitchen_occupancy"
    assert hass.states.get(kitchen_occ_eid) is not None
    assert hass.states.get("binary_sensor.kitchen_ble_occupancy") is None
    if ent_reg.async_get(kitchen_occ_eid) is not None:
        ent_reg.async_update_entity(kitchen_occ_eid, area_id="kitchen")
    else:
        register_entity(
            hass,
            kitchen_occ_eid,
            platform=DOMAIN,
            config_entry=entry,
            area_id="kitchen",
            unique_id="latter_area_occupancy_kitchen",
            original_device_class="occupancy",
        )
    hass.states.async_set(
        kitchen_occ_eid,
        "on",
        {"device_class": "occupancy"},
    )
    get_global_config(hass)[CONF_AREA_FUSION_CONFIG]["kitchen"] = {
        "mode": "any_or",
        "threshold_pct": 50,
        "sensors": [kitchen_occ_eid],
    }
    fabric._invalidate_caches()
    coord.ble_tracker._ingest_proxy_observation(
        "AA:BB:CC:00:00:11", -35, t_ble + 20.0, "Living Room Proxy"
    )
    coord.ble_tracker._ingest_proxy_observation(
        "AA:BB:CC:00:00:11", -35, t_ble + 20.3, "Living Room Proxy"
    )
    coord.ble_tracker._ingest_proxy_observation(
        "AA:BB:CC:00:00:11", -35, t_ble + 20.6, "Living Room Proxy"
    )
    assert coord.ble_tracker.current_area_id == "living_room"
    assert fabric.get_area_occupancy("kitchen")["sensor_occupied"] is False

    # BLE distance sensor is disabled by default (Gold `entity-disabled-by-default`) and uses canonical meters (`m`, `distance_m`)
    dist_entry = ent_reg.async_get("sensor.pocket_assistant_ble_distance")
    assert dist_entry is not None
    assert dist_entry.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get("sensor.pocket_assistant_ble_distance") is None
    from custom_components.latter.sensor import LatterBleDistanceSensor

    dist_sensor = LatterBleDistanceSensor(coord)
    dist_attrs = dist_sensor.extra_state_attributes
    assert "distance_m" in dist_attrs
    assert "distance_ft" not in dist_attrs

    summary_rows = get_all_areas_presence_summary(hass)
    assert any(r["area_id"] == "kitchen" for r in summary_rows)

    # Voice Follows Me: Roaming device (stationary == 0) updates its own bound ESPHome device area_id on explicit pick
    coord.async_set_active_area("kitchen", sync_device_registry=True)
    await hass.async_block_till_done()
    esp_dev = dev_reg.async_get(coord.esphome_device_id)
    assert esp_dev is not None
    assert esp_dev.area_id == "kitchen"

    # Away timeout MUST NOT clear ESPHome device area_id
    tracker = coord.ble_tracker
    assert tracker is not None
    tracker.check_away_timeout(time.monotonic() + AWAY_TIMEOUT_SECONDS + 30.0)
    assert tracker.is_away is True
    esp_dev = dev_reg.async_get(coord.esphome_device_id)
    assert esp_dev is not None and esp_dev.area_id == "kitchen"

    unsub()
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_stationary_device_never_mutates_esphome_device_area(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify stationary devices (stationary == 1) never mutate their bound ESPHome device area_id."""
    await seed_ble_proxies(hass)
    entry_s, _sys_s, coord_s = await setup_latter_hub(
        hass,
        stationary=1,
        sync_device_area=True,
    )
    dev_reg = dr.async_get(hass)
    esp_stat = dev_reg.async_get(coord_s.esphome_device_id)
    assert esp_stat is not None and esp_stat.area_id == "living_room"
    coord_s.async_set_active_area("kitchen", sync_device_registry=True)
    await hass.async_block_till_done()
    esp_stat = dev_reg.async_get(coord_s.esphome_device_id)
    assert esp_stat is not None and esp_stat.area_id == "living_room"
    assert await hass.config_entries.async_unload(entry_s.entry_id) is True


async def test_static_assigned_area_startup_healing_live_reassignment_and_two_way_sync(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify D-032 static Area startup healing, live HA Device Registry reassignment, and Studio two-way sync."""
    await prepare_latter_dependencies(hass)
    await ensure_bluetooth_manager(hass)
    f1 = ensure_floor(hass, "Ground Level", floor_id="floor_1", level=1)
    ensure_area(hass, "Garage", area_id="garage", floor_id=f1.floor_id)
    ensure_area(hass, "Living Area", area_id="living_room", floor_id=f1.floor_id)
    ensure_area(hass, "Kitchen", area_id="kitchen", floor_id=f1.floor_id)

    # ESPHome Device was reassigned in HA from Garage -> Living Area while Latter still held Garage in subentry & runtime
    esp_dev, mac = make_esphome_device(
        hass,
        slug="desk_assistant",
        mac="aa:bb:cc:dd:ee:99",
        name="Desk Assistant",
        area_id="living_room",
        stationary=1,
    )
    await Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.sub_desk").async_save(
        {"active_area_id": "garage"}
    )

    assert await async_setup_component(hass, DOMAIN, {}) is True
    entry = add_mock_entry(
        hass,
        entry_id="entry_latter_hub",
        domain=DOMAIN,
        title="Latter",
        data={},
        subentries_data=[
            make_subentry_dict(
                {
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
    dev_reg = dr.async_get(hass)
    child_latter_dev = register_device(
        hass,
        config_entry_id=entry.entry_id,
        config_subentry_id="sub_desk",
        entry_domain=DOMAIN,
        identifiers={(DOMAIN, dr.format_mac(mac))},
        via_device_id=esp_dev.id,
        name="Desk Assistant",
        manufacturer="Latter",
        area_id="garage",
    )
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await flush_debouncers(hass)

    coord = entry.runtime_data.coordinators["sub_desk"]

    # 1) Startup heals active_area_id, CONF_DEFAULT_AREA, child Latter device, and Current Area from esp_dev.area_id
    ent_reg = er.async_get(hass)
    desk_area_eid = ent_reg.async_get_entity_id("sensor", DOMAIN, "sub_desk_current_area")
    assert desk_area_eid is not None
    assert coord.active_area_id == "living_room"
    assert coord.get_opt(CONF_DEFAULT_AREA) == "living_room"
    child_now = dev_reg.async_get(child_latter_dev.id)
    assert child_now is not None and child_now.area_id == "living_room"
    active_entry = resolve_active_area_entry(coord)
    assert active_entry is not None and active_entry.id == "living_room"
    assert hass.states.get(desk_area_eid).state == "Living Area"

    # Non-battery panel hides battery-only ble_beacon_mode preference
    assert (
        coordinator_supports_pref(coord, DEVICE_PREF_SPEC_MAP["ble_beacon_mode"])
        is False
    )

    # 2) Live HA Device Registry reassignment on ESPHome Device updates active Area + child Latter device immediately
    dev_reg.async_update_device(esp_dev.id, area_id="kitchen")
    await flush_debouncers(hass)
    assert coord.active_area_id == "kitchen"
    assert coord.get_opt(CONF_DEFAULT_AREA) == "kitchen"
    child_now = dev_reg.async_get(child_latter_dev.id)
    assert child_now is not None and child_now.area_id == "kitchen"
    assert hass.states.get(desk_area_eid).state == "Kitchen"

    # Reassigning child Latter Device in HA mirrors back to parent ESPHome Device and active Area
    dev_reg.async_update_device(child_latter_dev.id, area_id="garage")
    await flush_debouncers(hass)
    esp_now = dev_reg.async_get(esp_dev.id)
    assert esp_now is not None and esp_now.area_id == "garage"
    assert coord.active_area_id == "garage"
    assert coord.get_opt(CONF_DEFAULT_AREA) == "garage"

    # Unrelated Device Registry update (e.g., rename without area_id change) leaves active Area intact
    dev_reg.async_update_device(esp_dev.id, name_by_user="Desk Assistant Pro")
    await flush_debouncers(hass)
    assert coord.active_area_id == "garage"

    # 3) Two-way Studio Static Assigned Area update & clearing (Unassigned)
    cleaned_assign = clean_device_settings(
        {"default_area": "living_room"}, coord.device_data
    )
    coord.update_device_config({**coord.device_data, **cleaned_assign})
    await coord.async_apply_options()
    await flush_debouncers(hass)
    esp_now = dev_reg.async_get(esp_dev.id)
    child_now = dev_reg.async_get(child_latter_dev.id)
    assert esp_now is not None and esp_now.area_id == "living_room"
    assert child_now is not None and child_now.area_id == "living_room"
    assert coord.active_area_id == "living_room"
    assert hass.states.get(desk_area_eid).state == "Living Area"

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
    await flush_debouncers(hass)
    esp_now = dev_reg.async_get(esp_dev.id)
    child_now = dev_reg.async_get(child_latter_dev.id)
    assert esp_now is not None and esp_now.area_id is None
    assert child_now is not None and child_now.area_id is None
    assert coord.active_area_id is None
    assert hass.states.get(desk_area_eid).state == "Unassigned"

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
    await hass.async_block_till_done()
    esp_now = dev_reg.async_get(esp_dev.id)
    child_now = dev_reg.async_get(child_latter_dev.id)
    assert coord.get_opt(CONF_DEFAULT_AREA) == "kitchen"
    assert esp_now is not None and esp_now.area_id == "kitchen"
    assert child_now is not None and child_now.area_id == "kitchen"

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_zero_ms_private_ble_rpa_rotation_connectable_and_eddystone_uid(
    hass: Any,
) -> None:
    """Verify 0 ms state_changed Private BLE RPA rotation, stale RPA eviction, connectable advs, and Eddystone-UID."""
    await prepare_latter_dependencies(hass)
    f1 = ensure_floor(hass, "Ground Level", floor_id="floor_1", level=1)
    ensure_area(hass, "Living Room", area_id="living_room", floor_id=f1.floor_id)
    ensure_area(hass, "Kitchen", area_id="kitchen", floor_id=f1.floor_id)
    await seed_ble_proxies(hass)
    hass.states.async_set("person.alex", "home", {"friendly_name": "Alex"})

    # Seed `private_ble_device` entity with initial RPA
    rpa_1 = "54:AA:11:22:33:01"
    rpa_2 = "67:BB:44:55:66:02"
    hass.states.async_set(
        "device_tracker.phone_ble",
        "home",
        {"current_address": rpa_1, "friendly_name": "Alex iPhone BLE"},
    )
    eddystone_uid_hex = "00112233445566778899aabbccddeeff"

    assert await async_setup_component(hass, DOMAIN, {}) is True
    entry = add_mock_entry(
        hass,
        entry_id="entry_latter_rpa",
        domain=DOMAIN,
        title="Latter",
        data={},
        subentries_data=[
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "alex_phone",
                    CONF_BLE_TARGET_ADDRESS: "device_tracker.phone_ble",
                    CONF_ASSIGNED_PERSON: "person.alex",
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_phone_ble",
                subentry_type=SUBENTRY_BLE_TAG,
                title="Alex Phone",
                unique_id="tag_phone_ble",
            ),
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "luggage_eddy",
                    CONF_BLE_TARGET_ADDRESS: f"eddystone:{eddystone_uid_hex}",
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_eddy_tag",
                subentry_type=SUBENTRY_BLE_TAG,
                title="Luggage Eddystone",
                unique_id="tag_eddy",
            ),
        ],
        unique_id=DOMAIN,
    )
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    fabric = get_ble_fabric(hass)
    phone_tracker = entry.runtime_data.coordinators["sub_phone_ble"].ble_tracker
    eddy_tracker = entry.runtime_data.coordinators["sub_eddy_tag"].ble_tracker
    assert phone_tracker is not None and eddy_tracker is not None

    # 1) Initial RPA subscribed in O(1)
    assert rpa_1 in fabric._adv_unsubs
    assert phone_tracker.matched_ble_addresses == [rpa_1]

    # 2) Rotate RPA via state_changed -> updates in 0 ms and evicts stale rpa_1 from _adv_unsubs!
    hass.states.async_set(
        "device_tracker.phone_ble",
        "home",
        {"current_address": rpa_2, "friendly_name": "Alex iPhone BLE"},
    )
    await hass.async_block_till_done()
    assert rpa_2 in fabric._adv_unsubs
    assert rpa_1 not in fabric._adv_unsubs
    assert phone_tracker.matched_ble_addresses == [rpa_2]

    # 3) Connectable BLE advertisement (`connectable=True`, empty mfg_data) on rpa_2 matches passively!
    t0 = time.monotonic()
    conn_adv = make_ibeacon_service_info(
        "",
        rssi=-54,
        source="AA:BB:CC:00:00:11",
        obs_time=t0,
        address=rpa_2,
        connectable=True,
        tx_power_1m=-10,
    )
    inject_ble_adv(hass, conn_adv)
    assert phone_tracker.current_area_id == "living_room"
    # tx_power = -10 dBm -> 1m ref power = -10 - 59 = -69.0 dBm
    assert phone_tracker.detected_ref_power_dbm == -69.0

    # 4) Eddystone-UID (`0000feaa-0000-1000-8000-00805f9b34fb`) frame matching & 0m->1m ref power (-18 - 41 = -59 dBm)
    eddy_payload = bytes([0x00, (-18) & 0xFF]) + bytes.fromhex(eddystone_uid_hex) + b"\x00\x00"
    eddy_adv = make_ibeacon_service_info(
        "",
        rssi=-57,
        source="AA:BB:CC:00:00:22",
        obs_time=t0 + 0.2,
        address="7C:DD:EE:FF:00:99",
        connectable=False,
        service_data={"0000feaa-0000-1000-8000-00805f9b34fb": eddy_payload},
        service_uuids=["0000feaa-0000-1000-8000-00805f9b34fb"],
    )
    inject_ble_adv(hass, eddy_adv)
    assert eddy_tracker.current_area_id == "kitchen"
    assert eddy_tracker.detected_ref_power_dbm == -59.0

    assert await hass.config_entries.async_unload(entry.entry_id) is True
    assert phone_tracker._unsub_target_entity is None
    assert fabric._adv_unsubs == {}


async def test_first_class_floor_entities_gated_on_configured_floors(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify current_floor entities omit bloat when zero Floors exist, auto-create dynamically, and track Floor + Away."""
    await prepare_latter_dependencies(hass)
    area_reg = ar.async_get(hass)

    # 1) Create Areas WITHOUT any floor_id and keep FloorRegistry empty
    ensure_area(hass, "Living Room", area_id="living_room")
    ensure_area(hass, "Bedroom", area_id="bedroom")
    await seed_ble_proxies(
        hass,
        [
            ("lr_proxy", "aa:bb:cc:00:00:11", "Living Room Proxy", "living_room"),
            ("bed_proxy", "aa:bb:cc:00:00:33", "Bedroom Proxy", "bedroom"),
        ],
    )
    hass.states.async_set("person.alex", "home", {"friendly_name": "Alex"})
    assert has_configured_floors(hass) is False

    esp_dev, mac = make_esphome_device(
        hass,
        slug="pocket_assistant",
        mac="aa:bb:cc:dd:ee:01",
        name="Pocket Assistant",
        area_id="living_room",
        stationary=0,
    )
    assert await async_setup_component(hass, DOMAIN, {}) is True
    entry = add_mock_entry(
        hass,
        entry_id="entry_latter_floors",
        domain=DOMAIN,
        title="Latter",
        data={},
        subentries_data=[
            make_subentry_dict(
                {
                    CONF_ESPHOME_DEVICE_ID: esp_dev.id,
                    "mac": mac,
                    CONF_DEVICE_SLUG: "pocket_assistant",
                    CONF_DEFAULT_AREA: "living_room",
                    CONF_ASSIGNED_PERSON: "person.alex",
                    CONF_NATIVE_BLE_TRACKING: True,
                    "ble_auto_switch": True,
                },
                subentry_id="sub_pocket",
                subentry_type=SUBENTRY_DEVICE,
                title="Pocket Assistant",
                unique_id=mac,
            ),
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "alex_watch",
                    CONF_BLE_TARGET_ADDRESS: "33:44:55:66:77:88",
                    CONF_ASSIGNED_PERSON: "person.alex",
                    CONF_NATIVE_BLE_TRACKING: True,
                },
                subentry_id="sub_watch",
                subentry_type=SUBENTRY_BLE_TAG,
                title="Alex Watch",
                unique_id="tag_watch",
            ),
        ],
        unique_id=DOMAIN,
    )
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()

    # Zero Floors -> zero `current_floor` entity bloat!
    ent_reg = er.async_get(hass)
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, "sub_pocket_current_area") is not None
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, "sub_pocket_current_floor") is None
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, "sub_watch_current_floor") is None
    assert (
        ent_reg.async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_person_alex_current_floor")
        is None
    )

    # 2) Dynamically create Floors in FloorRegistry & map Areas -> floor sensors auto-create live!
    f1 = ensure_floor(hass, "Ground Level", floor_id="floor_1", level=1)
    f2 = ensure_floor(hass, "Upper Level", floor_id="floor_2", level=2)
    area_reg.async_update("living_room", floor_id=f1.floor_id)
    area_reg.async_update("bedroom", floor_id=f2.floor_id)
    await hass.async_block_till_done()

    assert has_configured_floors(hass) is True
    pocket_floor_eid = ent_reg.async_get_entity_id("sensor", DOMAIN, "sub_pocket_current_floor")
    watch_floor_eid = ent_reg.async_get_entity_id("sensor", DOMAIN, "sub_watch_current_floor")
    person_floor_eid = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_person_alex_current_floor"
    )
    assert pocket_floor_eid is not None
    assert watch_floor_eid is not None
    assert person_floor_eid is not None
    pocket_floor = hass.states.get(pocket_floor_eid)
    watch_floor = hass.states.get(watch_floor_eid)
    person_floor = hass.states.get(person_floor_eid)
    assert pocket_floor is not None and pocket_floor.state == "Ground Level"
    assert pocket_floor.attributes["floor_id"] == f1.floor_id
    assert watch_floor is not None and watch_floor.state == "Unassigned"
    assert person_floor is not None and person_floor.state == "Ground Level"

    # 3) Move watch to Upstairs `bedroom` via BLE -> watch & person floor sensors update to `Upper Level`!
    watch_coord = entry.runtime_data.coordinators["sub_watch"]
    assert watch_coord.ble_tracker is not None
    t0 = time.monotonic()
    for step in range(3):
        watch_coord.ble_tracker._ingest_proxy_observation(
            "AA:BB:CC:00:00:33", -54, t0 + step * 0.2, "Bedroom Proxy"
        )
    await flush_debouncers(hass)
    assert hass.states.get(watch_floor_eid).state == "Upper Level"
    assert hass.states.get(person_floor_eid).state == "Upper Level"
    watch_dt_eid = ent_reg.async_get_entity_id("device_tracker", DOMAIN, "sub_watch_ble_tracker")
    assert watch_dt_eid is not None
    watch_dt = hass.states.get(watch_dt_eid)
    assert watch_dt is not None
    assert watch_dt.attributes["floor_id"] == f2.floor_id
    assert watch_dt.attributes["floor_name"] == "Upper Level"

    # 4) Both devices transition to `Away` -> `current_floor` sensors report `Away`!
    pocket_coord = entry.runtime_data.coordinators["sub_pocket"]
    hass.states.async_set("binary_sensor.pocket_assistant_ble_radio_active", "on")
    assert pocket_coord.ble_tracker is not None
    pocket_coord.ble_tracker.check_away_timeout(t0 + AWAY_TIMEOUT_SECONDS + 30.0)
    watch_coord.ble_tracker.check_away_timeout(t0 + AWAY_TIMEOUT_SECONDS + 30.0)
    await flush_debouncers(hass)

    assert hass.states.get(pocket_floor_eid).state == "Away"
    assert hass.states.get(watch_floor_eid).state == "Away"
    assert hass.states.get(person_floor_eid).state == "Away"

    assert await hass.config_entries.async_unload(entry.entry_id) is True
