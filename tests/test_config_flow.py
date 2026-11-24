"""Integration tests for LatterConfigFlow (including 0-display hub setup), LatterDeviceSubentryFlow, and LatterBleTagSubentryFlow."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from homeassistant.config_entries import (
    SOURCE_INTEGRATION_DISCOVERY,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store

from custom_components.latter.config_defaults import ble_tag_option_defaults
from custom_components.latter.config_flow import (
    LatterConfigFlow,
    _apply_onboarding_profile_and_defaults,
    _build_schema,
)
from custom_components.latter.const import (
    CONF_ASSIGNED_PERSON,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEFAULT_AREA,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    CONF_NATIVE_BLE_TRACKING,
    CONF_SYNC_DEVICE_AREA,
    DOMAIN,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
)
from custom_components.latter.groups.device_groups import (
    detect_hardware_defaults as _detect_hardware_defaults,
    device_option_defaults,
)
from custom_components.latter.hub_registry import get_domain_data
from tests.helpers.ha_setup import (
    add_mock_entry,
    get_test_manifest,
    make_subentry,
    prepare_latter_dependencies,
    register_device,
)


async def test_zero_display_standalone_hub_onboarding(hass: Any) -> None:
    """Verify D-060 0-display standalone hub creation (`async_step_user({})` -> `subentries=[]`) and retired hub OptionsFlow/Reconfigure."""
    await prepare_latter_dependencies(hass)
    hass.states.async_set("weather.home", "sunny", {})
    hass.states.async_set("alarm_control_panel.home_alarm", "armed_home", {})

    form = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert form["type"] == FlowResultType.FORM
    assert form["step_id"] == "user"

    hub_only = await hass.config_entries.flow.async_configure(form["flow_id"], {})
    await hass.async_block_till_done()
    assert hub_only["type"] == FlowResultType.CREATE_ENTRY
    assert hub_only["title"] == "Latter"
    assert hub_only["data"] == {}
    entry = hub_only["result"]
    assert list(entry.subentries) == []

    # D-060: Duplicate 2-field OptionsFlow & hub Reconfigure are retired in favor of `config_panel_domain=DOMAIN`
    assert not hasattr(LatterConfigFlow, "async_step_reconfigure")
    assert "async_get_options_flow" not in LatterConfigFlow.__dict__
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_hub_config_flow_user_discovery_and_single_instance(
    hass: Any, make_esphome_device: Any
) -> None:
    """Test initial hub onboarding, non-Latter rejection, discovery, and single-instance enforcement."""
    await prepare_latter_dependencies(hass)
    hass.states.async_set("weather.home", "sunny", {})
    hass.states.async_set("alarm_control_panel.home_alarm", "armed_home", {})

    dev, mac = make_esphome_device(hass, slug="wall_panel", mac="aa:bb:cc:00:11:22", stationary=1)
    # Plain non-Latter ESPHome device (no manifest or contract services)
    esp_plain = add_mock_entry(hass, entry_id="esp_plain", domain="esphome", title="Plain Plug")
    plain_dev = register_device(
        hass,
        config_entry_id=esp_plain.entry_id,
        identifiers={("esphome", "plain_1")},
        name="Plain Plug",
    )

    # Discovery flow shows user form pre-populated with discovered device
    disc_res = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_ESPHOME_DEVICE_ID: dev.id},
    )
    assert disc_res["type"] == FlowResultType.FORM
    assert disc_res["step_id"] == "user"

    # Invalid discovery device aborts cleanly
    bad_disc = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_ESPHOME_DEVICE_ID: "missing"},
    )
    assert bad_disc["type"] == FlowResultType.ABORT
    assert bad_disc["reason"] == "not_supported"

    # User flow rejects non-Latter ESPHome device
    form = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert form["type"] == FlowResultType.FORM

    bad = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {
            CONF_ESPHOME_DEVICE_ID: plain_dev.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: False,
        },
    )
    assert bad["type"] == FlowResultType.FORM
    assert bad["errors"][CONF_ESPHOME_DEVICE_ID] == "not_latter_device"

    # Valid submission creates Latter hub + first device subentry and aborts competing discovery flow
    ok = await hass.config_entries.flow.async_configure(
        bad["flow_id"],
        {
            CONF_ESPHOME_DEVICE_ID: dev.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: False,
        },
    )
    await hass.async_block_till_done()
    assert ok["type"] == FlowResultType.CREATE_ENTRY
    assert ok["title"] == "Latter"
    entry = ok["result"]
    subs = list(entry.subentries.values())
    assert len(subs) == 1
    assert subs[0].data[CONF_ESPHOME_DEVICE_ID] == dev.id
    assert subs[0].data["mac"] == mac
    # Pre-hello unbound device with explicit `native_ble_tracking=False` overrides default `handhelds` -> `custom`
    assert subs[0].data[CONF_DEVICE_GROUP] == "custom"

    # Once hub entry exists, second user flow and discovery flow abort
    second = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert second["type"] == FlowResultType.ABORT
    assert second["reason"] == "single_instance_allowed"

    second_disc = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_INTEGRATION_DISCOVERY},
        data={CONF_ESPHOME_DEVICE_ID: dev.id},
    )
    assert second_disc["type"] == FlowResultType.ABORT
    assert second_disc["reason"] == "single_instance_allowed"
    assert set(LatterConfigFlow.async_get_supported_subentry_types(entry)) == {
        SUBENTRY_DEVICE,
        SUBENTRY_BLE_TAG,
    }
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_device_and_ble_tag_subentry_flows_and_hardware_replacement(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any
) -> None:
    """Exercise adding a second display, duplicate prevention, in-place hardware MAC swap, and BLE tag flows."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    dev_reg = dr.async_get(hass)
    hass.states.async_set("person.alex", "home", {"friendly_name": "Alex"})
    hass.states.async_set("person.sam", "home", {"friendly_name": "Sam"})

    latter_dev = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=coord.get_device_info()["identifiers"],
        name="Pocket Assistant",
    )

    dev2, _mac2 = make_esphome_device(
        hass, slug="watch_assistant", mac="aa:bb:cc:dd:ee:02", name="Watch Assistant", wearable=1
    )

    # Reject already-bound first device
    dup_form = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_DEVICE), context={"source": SOURCE_USER}
    )
    assert dup_form["type"] == FlowResultType.FORM
    dup = await hass.config_entries.subentries.async_configure(
        dup_form["flow_id"],
        {
            CONF_ESPHOME_DEVICE_ID: coord.esphome_device_id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: True,
        },
    )
    assert dup["type"] == FlowResultType.ABORT
    assert dup["reason"] == "already_configured"

    # Onboard second wearable device
    add_form = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_DEVICE), context={"source": SOURCE_USER}
    )
    created = await hass.config_entries.subentries.async_configure(
        add_form["flow_id"],
        {
            CONF_ESPHOME_DEVICE_ID: dev2.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: True,
        },
    )
    await hass.async_block_till_done()
    assert created["type"] == FlowResultType.CREATE_ENTRY
    # Pre-hello unbound device with `latter_set_slots` defaults to `handhelds` until `device_hello` reports traits
    assert created["data"][CONF_DEVICE_GROUP] == "handhelds"

    # Reconfigure sub_pocket with replacement hardware dev3 -> migrates Latter DeviceEntry MAC identifier in-place
    dev3, mac3 = make_esphome_device(
        hass, slug="pocket_v2", mac="aa:bb:cc:dd:ee:03", name="Pocket Assistant V2"
    )
    reconf_form = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_DEVICE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "sub_pocket"},
    )
    assert reconf_form["type"] == FlowResultType.FORM
    replaced = await hass.config_entries.subentries.async_configure(
        reconf_form["flow_id"],
        {
            CONF_ESPHOME_DEVICE_ID: dev3.id,
            CONF_DEVICE_GROUP: "handhelds",
            CONF_NATIVE_BLE_TRACKING: True,
        },
    )
    await hass.async_block_till_done()
    assert replaced["type"] == FlowResultType.ABORT
    assert replaced["reason"] == "reconfigure_successful"
    updated_latter_dev = dev_reg.async_get(latter_dev.id)
    assert updated_latter_dev is not None
    assert (DOMAIN, dr.format_mac(mac3)) in updated_latter_dev.identifiers
    assert entry.subentries["sub_pocket"].data[CONF_ESPHOME_DEVICE_ID] == dev3.id

    # BLE Tag Subentry Flow: validation + creation + duplicate guard
    tag_form = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_BLE_TAG), context={"source": SOURCE_USER}
    )
    assert tag_form["type"] == FlowResultType.FORM
    inc = await hass.config_entries.subentries.async_configure(
        tag_form["flow_id"], {"name": "Keys", CONF_BLE_TARGET_ADDRESS: ""}
    )
    assert inc["type"] == FlowResultType.FORM
    assert inc["errors"]["base"] == "ble_tag_incomplete"

    tag_ok = await hass.config_entries.subentries.async_configure(
        inc["flow_id"],
        {
            "name": "Backpack Tag",
            CONF_BLE_TARGET_ADDRESS: "AA:11:22:33:44:55",
            CONF_ASSIGNED_PERSON: "person.sam",
        },
    )
    await hass.async_block_till_done()
    assert tag_ok["type"] == FlowResultType.CREATE_ENTRY
    backpack_sub = next(
        sub for sub in entry.subentries.values() if sub.title == "Backpack Tag"
    )

    dup_tag_form = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_BLE_TAG), context={"source": SOURCE_USER}
    )
    dup_tag = await hass.config_entries.subentries.async_configure(
        dup_tag_form["flow_id"],
        {"name": "Backpack Tag", CONF_BLE_TARGET_ADDRESS: "AA:11:22:33:44:55"},
    )
    assert dup_tag["type"] == FlowResultType.ABORT
    assert dup_tag["reason"] == "already_configured"

    # Add second BLE tag so duplicate check during BLE tag reconfigure can be verified
    hass.config_entries.async_add_subentry(
        entry,
        make_subentry(
            ble_tag_option_defaults("Keys Tag", "BB:22:33:44:55:66"),
            subentry_type=SUBENTRY_BLE_TAG,
            title="Keys Tag",
            unique_id="latter_ble_keys_tag",
            subentry_id="sub_keys",
        ),
    )
    await hass.async_block_till_done()

    # BLE Tag Subentry Reconfigure (`D-060`): preserves `device_slug` while updating title, target address & person
    reconf_tag_form = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_BLE_TAG),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": backpack_sub.subentry_id},
    )
    assert reconf_tag_form["type"] == FlowResultType.FORM
    assert reconf_tag_form["step_id"] == "reconfigure"

    inc_reconf = await hass.config_entries.subentries.async_configure(
        reconf_tag_form["flow_id"],
        {"name": "Backpack Tag", CONF_BLE_TARGET_ADDRESS: ""},
    )
    assert inc_reconf["type"] == FlowResultType.FORM
    assert inc_reconf["errors"]["base"] == "ble_tag_incomplete"

    dup_reconf = await hass.config_entries.subentries.async_configure(
        inc_reconf["flow_id"],
        {"name": "Backpack Tag", CONF_BLE_TARGET_ADDRESS: "BB:22:33:44:55:66"},
    )
    assert dup_reconf["type"] == FlowResultType.ABORT
    assert dup_reconf["reason"] == "already_configured"

    reconf_tag_form2 = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_BLE_TAG),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": backpack_sub.subentry_id},
    )
    ok_reconf = await hass.config_entries.subentries.async_configure(
        reconf_tag_form2["flow_id"],
        {
            "name": "Travel Backpack",
            CONF_BLE_TARGET_ADDRESS: "CC:33:44:55:66:77",
            CONF_ASSIGNED_PERSON: "person.alex",
        },
    )
    await hass.async_block_till_done()
    assert ok_reconf["type"] == FlowResultType.ABORT
    assert ok_reconf["reason"] == "reconfigure_successful"
    updated_tag_sub = entry.subentries[backpack_sub.subentry_id]
    assert updated_tag_sub.title == "Travel Backpack"
    assert updated_tag_sub.data[CONF_DEVICE_SLUG] == "backpack_tag"
    assert updated_tag_sub.data[CONF_BLE_TARGET_ADDRESS] == "CC:33:44:55:66:77"
    assert updated_tag_sub.data[CONF_ASSIGNED_PERSON] == "person.alex"

    # Pure option default helpers
    assert (
        device_option_defaults(hass, dev2, {"w": 466, "h": 466, "wearable": 1})[CONF_DEVICE_GROUP]
        == "wearables"
    )
    assert (
        ble_tag_option_defaults("Wallet", "11:22:33:44:55:99")[CONF_BLE_TARGET_ADDRESS]
        == "11:22:33:44:55:99"
    )
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_onboarding_smart_area_and_roaming_defaults(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify D-032 trait + Area onboarding smart defaults and explicit user overrides."""
    assert LatterConfigFlow.VERSION == 1

    # 1) Stationary device WITH an assigned ESPHome Area -> defaults to Static pinned to that Area
    desk_assigned, _ = make_esphome_device(
        hass,
        slug="desk_assigned",
        mac="aa:bb:cc:11:00:01",
        area_id="living_room",
        stationary=1,
    )
    desk_assigned_manifest = get_test_manifest(hass, desk_assigned.id)
    defs_assigned = _detect_hardware_defaults(hass, desk_assigned, desk_assigned_manifest)
    assert defs_assigned[CONF_DEVICE_GROUP] == "wall_panels"
    assert defs_assigned[CONF_NATIVE_BLE_TRACKING] is False
    assert defs_assigned[CONF_BLE_AUTO_SWITCH] is False
    assert defs_assigned[CONF_SYNC_DEVICE_AREA] is False
    assert defs_assigned[CONF_DEFAULT_AREA] == "living_room"

    # 2) Stationary device WITHOUT an ESPHome Area -> stays Static in `wall_panels` (never demoted to `custom`)
    desk_unassigned, _ = make_esphome_device(
        hass,
        slug="desk_unassigned",
        mac="aa:bb:cc:11:00:02",
        area_id=None,
        stationary=1,
    )
    desk_unassigned_manifest = get_test_manifest(hass, desk_unassigned.id)
    defs_unassigned = _detect_hardware_defaults(hass, desk_unassigned, desk_unassigned_manifest)
    assert defs_unassigned[CONF_DEVICE_GROUP] == "wall_panels"
    assert defs_unassigned[CONF_NATIVE_BLE_TRACKING] is False
    assert defs_unassigned[CONF_BLE_AUTO_SWITCH] is False
    assert defs_unassigned[CONF_SYNC_DEVICE_AREA] is False
    assert defs_unassigned[CONF_DEFAULT_AREA] == ""

    merged_auto = _apply_onboarding_profile_and_defaults(
        hass,
        desk_unassigned,
        {CONF_ESPHOME_DEVICE_ID: desk_unassigned.id, CONF_DEVICE_GROUP: "auto"},
        manifest=desk_unassigned_manifest,
    )
    assert merged_auto[CONF_DEVICE_GROUP] == "wall_panels"
    assert merged_auto[CONF_NATIVE_BLE_TRACKING] is False
    assert merged_auto[CONF_BLE_AUTO_SWITCH] is False
    assert merged_auto[CONF_SYNC_DEVICE_AREA] is False
    assert merged_auto[CONF_DEFAULT_AREA] == ""

    # 3) Roaming round battery display -> defaults to `pocket_carry` + BLE Roaming (empty CONF_DEFAULT_AREA)
    pocket_dev, _ = make_esphome_device(
        hass,
        slug="pocket_roam",
        mac="aa:bb:cc:11:00:03",
        area_id="garage",
        stationary=0,
    )
    pocket_manifest = get_test_manifest(hass, pocket_dev.id)
    defs_pocket = _detect_hardware_defaults(hass, pocket_dev, pocket_manifest)
    assert defs_pocket[CONF_DEVICE_GROUP] == "pocket_carry"
    assert defs_pocket[CONF_NATIVE_BLE_TRACKING] is True
    assert defs_pocket[CONF_BLE_AUTO_SWITCH] is True
    assert defs_pocket[CONF_SYNC_DEVICE_AREA] is True
    assert defs_pocket[CONF_DEFAULT_AREA] == ""

    # Square battery handheld -> defaults to `handhelds`; wearable -> defaults to `wearables`
    mobile_dev, _ = make_esphome_device(
        hass,
        slug="mobile_roam",
        mac="aa:bb:cc:11:00:04",
        stationary=0,
        shape="square",
        w=368,
        h=448,
    )
    assert (
        _detect_hardware_defaults(hass, mobile_dev, get_test_manifest(hass, mobile_dev.id))[
            CONF_DEVICE_GROUP
        ]
        == "handhelds"
    )
    wrist_dev, _ = make_esphome_device(
        hass,
        slug="wrist_roam",
        mac="aa:bb:cc:11:00:05",
        stationary=0,
        wearable=1,
        shape="square",
    )
    assert (
        _detect_hardware_defaults(hass, wrist_dev, get_test_manifest(hass, wrist_dev.id))[
            CONF_DEVICE_GROUP
        ]
        == "wearables"
    )

    # 4) Explicit onboarding toggle override: pinning handheld to Static adopts ESPHome Area; enabling roaming on desk clears it
    pinned_pocket = _apply_onboarding_profile_and_defaults(
        hass,
        pocket_dev,
        {
            CONF_ESPHOME_DEVICE_ID: pocket_dev.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: False,
        },
        manifest=pocket_manifest,
    )
    assert pinned_pocket[CONF_NATIVE_BLE_TRACKING] is False
    assert pinned_pocket[CONF_BLE_AUTO_SWITCH] is False
    assert pinned_pocket[CONF_SYNC_DEVICE_AREA] is False
    assert pinned_pocket[CONF_DEFAULT_AREA] == "garage"

    roaming_desk = _apply_onboarding_profile_and_defaults(
        hass,
        desk_assigned,
        {
            CONF_ESPHOME_DEVICE_ID: desk_assigned.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: True,
        },
        manifest=desk_assigned_manifest,
    )
    assert roaming_desk[CONF_NATIVE_BLE_TRACKING] is True
    assert roaming_desk[CONF_BLE_AUTO_SWITCH] is True
    assert roaming_desk[CONF_SYNC_DEVICE_AREA] is False
    assert roaming_desk[CONF_DEFAULT_AREA] == ""


async def test_config_flow_edge_cases_and_guards(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any
) -> None:
    """Cover remaining config_flow branches for 100% Platinum config_flow coverage."""
    # 1) 0-display onboarding when global_store already exists on domain_data (saves seeded defaults)
    await prepare_latter_dependencies(hass)
    hass.states.async_set("weather.home", "sunny", {})
    hass.states.async_set("alarm_control_panel.home_alarm", "armed_home", {})
    domain_data = get_domain_data(hass)
    domain_data.global_store = Store(hass, 1, "latter_global_test_seed")

    form0 = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    hub0 = await hass.config_entries.flow.async_configure(form0["flow_id"], {})
    await hass.async_block_till_done()
    assert hub0["type"] == FlowResultType.CREATE_ENTRY
    saved = await domain_data.global_store.async_load()
    assert isinstance(saved, dict)
    assert saved.get("weather_entity") == "weather.home"
    removed = await hass.config_entries.async_remove(hub0["result"].entry_id)
    assert removed["require_restart"] is False

    # 2) Set up full hub with one device + one additional device + one plain non-Latter ESPHome device
    entry, _sys_obj, _coord = await setup_latter_hub(hass)
    dev2, _mac2 = make_esphome_device(
        hass, slug="desk_second", mac="aa:bb:cc:dd:ee:44", name="Desk Second", stationary=1
    )
    esp_plain = add_mock_entry(hass, entry_id="esp_plain_cf", domain="esphome", title="Plain Node")
    plain_dev = register_device(
        hass,
        config_entry_id=esp_plain.entry_id,
        identifiers={("esphome", "plain_cf_1")},
        name="Plain Node",
    )

    # 3) Direct detect_hardware_defaults with manifest=None (pre-hello w/ slots -> handhelds) and with cached manifest + _build_schema fallback for stale group id
    assert _detect_hardware_defaults(hass, dev2)[CONF_DEVICE_GROUP] == "handhelds"
    hw_defs = _detect_hardware_defaults(hass, dev2, get_test_manifest(hass, dev2.id))
    assert hw_defs[CONF_DEVICE_GROUP] == "wall_panels"
    schema_stale = _build_schema(hass, {CONF_DEVICE_GROUP: "deleted_group_id"})
    assert schema_stale is not None

    # 4) Rebind to an ESPHome device without a MAC connection drops stale "mac" key
    no_mac_esp = add_mock_entry(hass, entry_id="esp_nomac", domain="esphome", title="No MAC Node")
    no_mac_dev = register_device(
        hass,
        config_entry_id=no_mac_esp.entry_id,
        identifiers={("esphome", "no_mac_node")},
        name="No MAC Node",
    )
    with patch(
        "custom_components.latter.config_flow.discover_ma_player_for_device",
        return_value="media_player.ma_nomac",
    ):
        merged_nomac = _apply_onboarding_profile_and_defaults(
            hass,
            no_mac_dev,
            {
                CONF_ESPHOME_DEVICE_ID: no_mac_dev.id,
                CONF_DEVICE_GROUP: "auto",
                CONF_ASSIGNED_PERSON: "person.alex",
            },
            existing={"mac": "aa:bb:cc:dd:ee:01"},
            rebind_hardware=True,
        )
    assert "mac" not in merged_nomac
    assert merged_nomac["ma_player_entity"] == "media_player.ma_nomac"
    assert merged_nomac[CONF_ASSIGNED_PERSON] == "person.alex"

    # 5) Defensive single-instance/discovery guards on LatterConfigFlow when invoked directly/concurrently
    direct_flow = LatterConfigFlow()
    direct_flow.hass = hass
    disc_abort = await direct_flow.async_step_integration_discovery({CONF_ESPHOME_DEVICE_ID: dev2.id})
    assert disc_abort["type"] == FlowResultType.ABORT
    assert disc_abort["reason"] == "already_configured"
    user_abort = await direct_flow.async_step_user()
    assert user_abort["type"] == FlowResultType.ABORT
    assert user_abort["reason"] == "single_instance_allowed"

    # 6) LatterDeviceSubentryFlow.async_step_user rejects missing/non-ESPHome and non-Latter devices
    add_form = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_DEVICE), context={"source": SOURCE_USER}
    )
    bad_missing = await hass.config_entries.subentries.async_configure(
        add_form["flow_id"],
        {
            CONF_ESPHOME_DEVICE_ID: "missing_device_id",
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: True,
        },
    )
    assert bad_missing["type"] == FlowResultType.FORM
    assert bad_missing["errors"][CONF_ESPHOME_DEVICE_ID] == "not_latter_device"

    bad_plain = await hass.config_entries.subentries.async_configure(
        bad_missing["flow_id"],
        {
            CONF_ESPHOME_DEVICE_ID: plain_dev.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: True,
        },
    )
    assert bad_plain["type"] == FlowResultType.FORM
    assert bad_plain["errors"][CONF_ESPHOME_DEVICE_ID] == "not_latter_device"

    # Bind dev2 cleanly so we can test duplicate replacement during reconfigure
    created_dev2 = await hass.config_entries.subentries.async_configure(
        bad_plain["flow_id"],
        {
            CONF_ESPHOME_DEVICE_ID: dev2.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: False,
        },
    )
    await hass.async_block_till_done()
    assert created_dev2["type"] == FlowResultType.CREATE_ENTRY

    # 7) LatterDeviceSubentryFlow.async_step_reconfigure rejects non-Latter replacement and already-bound replacement
    reconf_form = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_DEVICE),
        context={"source": SOURCE_RECONFIGURE, "subentry_id": "sub_pocket"},
    )
    bad_reconf = await hass.config_entries.subentries.async_configure(
        reconf_form["flow_id"],
        {
            CONF_ESPHOME_DEVICE_ID: plain_dev.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: True,
        },
    )
    assert bad_reconf["type"] == FlowResultType.FORM
    assert bad_reconf["errors"][CONF_ESPHOME_DEVICE_ID] == "not_latter_device"

    dup_reconf = await hass.config_entries.subentries.async_configure(
        bad_reconf["flow_id"],
        {
            CONF_ESPHOME_DEVICE_ID: dev2.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: False,
        },
    )
    assert dup_reconf["type"] == FlowResultType.ABORT
    assert dup_reconf["reason"] == "already_configured"
    assert await hass.config_entries.async_unload(entry.entry_id) is True
