"""Integration tests for LatterConfigFlow (including 0-display hub setup), LatterDeviceSubentryFlow, and LatterBleTagSubentryFlow."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.helpers import device_registry as dr

from custom_components.latter.config_flow import (
    LatterBleTagSubentryFlow,
    LatterConfigFlow,
    LatterDeviceSubentryFlow,
    ble_tag_option_defaults,
    device_option_defaults,
)
from custom_components.latter.const import (
    CONF_ASSIGNED_PERSON,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    CONF_NATIVE_BLE_TRACKING,
    DOMAIN,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
)


async def test_zero_display_standalone_hub_onboarding(hass: Any) -> None:
    """Verify D-060 0-display standalone hub creation (`async_step_user({})` -> `subentries=[]`) and retired hub OptionsFlow/Reconfigure."""
    hass.states.async_set("weather.home", "sunny", {})
    hass.states.async_set("alarm_control_panel.home_alarm", "armed_home", {})

    flow = LatterConfigFlow()
    flow.hass = hass
    form = await flow.async_step_user()
    assert form["type"] == "form"
    assert form["step_id"] == "user"

    hub_only = await flow.async_step_user({})
    assert hub_only["type"] == "create_entry"
    assert hub_only["title"] == "Latter"
    assert hub_only["data"] == {}
    assert hub_only["subentries"] == []

    # D-060: Duplicate 2-field OptionsFlow & hub Reconfigure are retired in favor of `config_panel_domain=DOMAIN`
    assert not hasattr(LatterConfigFlow, "async_step_reconfigure")
    assert "async_get_options_flow" not in LatterConfigFlow.__dict__


async def test_hub_config_flow_user_discovery_and_single_instance(
    hass: Any, make_esphome_device: Any
) -> None:
    """Test initial hub onboarding, non-Latter rejection, discovery, and single-instance enforcement."""
    hass.states.async_set("weather.home", "sunny", {})
    hass.states.async_set("alarm_control_panel.home_alarm", "armed_home", {})

    dev, mac = make_esphome_device(hass, slug="wall_panel", mac="aa:bb:cc:00:11:22", stationary=1)
    # Also create a plain non-Latter ESPHome device (no manifest or contract services)
    esp_plain = hass.config_entries.add_entry(
        ConfigEntry(entry_id="esp_plain", domain="esphome", title="Plain Plug")
    )
    plain_dev = dr.async_get(hass).async_get_or_create(
        config_entry_id=esp_plain.entry_id,
        identifiers={("esphome", "plain_1")},
        name="Plain Plug",
    )

    # Discovery flow shows user form pre-populated with discovered device
    disc_flow = LatterConfigFlow()
    disc_flow.hass = hass
    disc_res = await disc_flow.async_step_integration_discovery({CONF_ESPHOME_DEVICE_ID: dev.id})
    assert disc_res["type"] == "form"
    assert disc_res["step_id"] == "user"

    # Invalid discovery device aborts cleanly
    bad_disc = LatterConfigFlow()
    bad_disc.hass = hass
    assert (await bad_disc.async_step_integration_discovery({CONF_ESPHOME_DEVICE_ID: "missing"}))["reason"] == "not_supported"

    # User flow rejects non-Latter ESPHome device
    flow = LatterConfigFlow()
    flow.hass = hass
    form = await flow.async_step_user()
    assert form["type"] == "form"

    bad = await flow.async_step_user(
        {
            CONF_ESPHOME_DEVICE_ID: plain_dev.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: False,
        }
    )
    assert bad["errors"][CONF_ESPHOME_DEVICE_ID] == "not_latter_device"

    # Valid submission creates Latter hub + first device subentry
    ok = await flow.async_step_user(
        {
            CONF_ESPHOME_DEVICE_ID: dev.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: False,
        }
    )
    assert ok["type"] == "create_entry"
    assert ok["title"] == "Latter"
    assert len(ok["subentries"]) == 1
    assert ok["subentries"][0]["data"][CONF_ESPHOME_DEVICE_ID] == dev.id
    assert ok["subentries"][0]["data"]["mac"] == mac
    assert ok["subentries"][0]["data"][CONF_DEVICE_GROUP] == "wall_panels"

    # Once hub entry exists, second user flow and discovery flow abort
    entry = hass.config_entries.add_entry(
        ConfigEntry(
            entry_id="entry_latter_hub",
            domain=DOMAIN,
            title="Latter",
            unique_id=DOMAIN,
            subentries_data=[
                ConfigSubentry(
                    data=ok["subentries"][0]["data"],
                    subentry_type=SUBENTRY_DEVICE,
                    title="Wall Panel",
                    unique_id=ok["subentries"][0]["unique_id"],
                    subentry_id="sub_wall",
                )
            ],
        )
    )
    second = LatterConfigFlow()
    second.hass = hass
    assert (await second.async_step_user())["reason"] == "single_instance_allowed"
    assert (
        await second.async_step_integration_discovery({CONF_ESPHOME_DEVICE_ID: dev.id})
    )["reason"] == "already_configured"
    assert set(LatterConfigFlow.async_get_supported_subentry_types(entry)) == {
        SUBENTRY_DEVICE,
        SUBENTRY_BLE_TAG,
    }


async def test_device_and_ble_tag_subentry_flows_and_hardware_replacement(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any
) -> None:
    """Exercise adding a second display, duplicate prevention, in-place hardware MAC swap, and BLE tag flows."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    dev_reg = dr.async_get(hass)
    # Ensure Latter device exists in registry with old MAC identifier
    latter_dev = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers=coord.get_device_info()["identifiers"],
        name="Pocket Assistant",
    )

    dev2, _mac2 = make_esphome_device(
        hass, slug="watch_assistant", mac="aa:bb:cc:dd:ee:02", name="Watch Assistant", wearable=1
    )

    # Add second device via LatterDeviceSubentryFlow
    sub_flow = LatterDeviceSubentryFlow()
    sub_flow.hass = hass
    sub_flow._entry = entry
    assert (await sub_flow.async_step_user())["type"] == "form"

    # Reject already-bound first device
    dup = await sub_flow.async_step_user(
        {
            CONF_ESPHOME_DEVICE_ID: coord.esphome_device_id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: True,
        }
    )
    assert dup["reason"] == "already_configured"

    # Onboard second wearable device
    created = await sub_flow.async_step_user(
        {
            CONF_ESPHOME_DEVICE_ID: dev2.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: True,
        }
    )
    assert created["type"] == "create_entry"
    assert created["data"][CONF_DEVICE_GROUP] == "wearables"

    # Reconfigure sub_pocket with replacement hardware dev3 -> migrates Latter DeviceEntry MAC identifier in-place
    dev3, mac3 = make_esphome_device(
        hass, slug="pocket_v2", mac="aa:bb:cc:dd:ee:03", name="Pocket Assistant V2"
    )
    reconf_sub = LatterDeviceSubentryFlow()
    reconf_sub.hass = hass
    reconf_sub._entry = entry
    reconf_sub._subentry = entry.subentries["sub_pocket"]
    assert (await reconf_sub.async_step_reconfigure())["type"] == "form"
    replaced = await reconf_sub.async_step_reconfigure(
        {
            CONF_ESPHOME_DEVICE_ID: dev3.id,
            CONF_DEVICE_GROUP: "handhelds",
            CONF_NATIVE_BLE_TRACKING: True,
        }
    )
    assert replaced["reason"] == "reconfigure_successful"
    assert (DOMAIN, dr.format_mac(mac3)) in latter_dev.identifiers
    assert entry.subentries["sub_pocket"].data[CONF_ESPHOME_DEVICE_ID] == dev3.id

    # BLE Tag Subentry Flow: validation + creation + duplicate guard
    tag_flow = LatterBleTagSubentryFlow()
    tag_flow.hass = hass
    tag_flow._entry = entry
    assert (await tag_flow.async_step_user())["type"] == "form"
    inc = await tag_flow.async_step_user({"name": "Keys", CONF_BLE_TARGET_ADDRESS: ""})
    assert inc["errors"]["base"] == "ble_tag_incomplete"

    tag_ok = await tag_flow.async_step_user(
        {"name": "Backpack Tag", CONF_BLE_TARGET_ADDRESS: "AA:11:22:33:44:55", "assigned_person": "person.sam"}
    )
    assert tag_ok["type"] == "create_entry"
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=tag_ok["data"],
            subentry_type=SUBENTRY_BLE_TAG,
            title=tag_ok["title"],
            unique_id=tag_ok["unique_id"],
            subentry_id="sub_backpack",
        ),
    )
    dup_tag = await tag_flow.async_step_user(
        {"name": "Backpack Tag", CONF_BLE_TARGET_ADDRESS: "AA:11:22:33:44:55"}
    )
    assert dup_tag["reason"] == "already_configured"

    # Add second BLE tag so duplicate check during BLE tag reconfigure can be verified
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=ble_tag_option_defaults("Keys Tag", "BB:22:33:44:55:66"),
            subentry_type=SUBENTRY_BLE_TAG,
            title="Keys Tag",
            unique_id="latter_ble_keys_tag",
            subentry_id="sub_keys",
        ),
    )

    # BLE Tag Subentry Reconfigure (`D-060`): preserves `device_slug` while updating title, target address & person
    reconf_tag = LatterBleTagSubentryFlow()
    reconf_tag.hass = hass
    reconf_tag._entry = entry
    reconf_tag._subentry = entry.subentries["sub_backpack"]
    reconf_tag_form = await reconf_tag.async_step_reconfigure()
    assert reconf_tag_form["type"] == "form"
    assert reconf_tag_form["step_id"] == "reconfigure"

    inc_reconf = await reconf_tag.async_step_reconfigure(
        {"name": "Backpack Tag", CONF_BLE_TARGET_ADDRESS: ""}
    )
    assert inc_reconf["errors"]["base"] == "ble_tag_incomplete"

    dup_reconf = await reconf_tag.async_step_reconfigure(
        {"name": "Backpack Tag", CONF_BLE_TARGET_ADDRESS: "BB:22:33:44:55:66"}
    )
    assert dup_reconf["reason"] == "already_configured"

    ok_reconf = await reconf_tag.async_step_reconfigure(
        {
            "name": "Travel Backpack",
            CONF_BLE_TARGET_ADDRESS: "CC:33:44:55:66:77",
            CONF_ASSIGNED_PERSON: "person.alex",
        }
    )
    assert ok_reconf["reason"] == "reconfigure_successful"
    updated_tag_sub = entry.subentries["sub_backpack"]
    assert updated_tag_sub.title == "Travel Backpack"
    assert updated_tag_sub.data[CONF_DEVICE_SLUG] == "backpack_tag"
    assert updated_tag_sub.data[CONF_BLE_TARGET_ADDRESS] == "CC:33:44:55:66:77"
    assert updated_tag_sub.data[CONF_ASSIGNED_PERSON] == "person.alex"

    # Pure option default helpers
    assert device_option_defaults(hass, dev2, {"w": 466, "h": 466, "wearable": 1})[CONF_DEVICE_GROUP] == "wearables"
    assert ble_tag_option_defaults("Wallet", "11:22:33:44:55:99")[CONF_BLE_TARGET_ADDRESS] == "11:22:33:44:55:99"


async def test_onboarding_smart_area_and_roaming_defaults(
    hass: Any, make_esphome_device: Any
) -> None:
    """Verify D-032 trait + Area onboarding smart defaults and explicit user overrides."""
    from custom_components.latter.config_flow import (
        _apply_onboarding_profile_and_defaults,
        _detect_hardware_defaults,
    )
    from custom_components.latter.const import (
        CONF_BLE_AUTO_SWITCH,
        CONF_DEFAULT_AREA,
        CONF_SYNC_DEVICE_AREA,
    )

    # 1) Stationary device WITH an assigned ESPHome Area -> defaults to Static pinned to that Area
    desk_assigned, _ = make_esphome_device(
        hass,
        slug="desk_assigned",
        mac="aa:bb:cc:11:00:01",
        area_id="living_room",
        stationary=1,
    )
    defs_assigned = _detect_hardware_defaults(hass, desk_assigned)
    assert defs_assigned[CONF_DEVICE_GROUP] == "wall_panels"
    assert defs_assigned[CONF_NATIVE_BLE_TRACKING] is False
    assert defs_assigned[CONF_BLE_AUTO_SWITCH] is False
    assert defs_assigned[CONF_SYNC_DEVICE_AREA] is False
    assert defs_assigned[CONF_DEFAULT_AREA] == "living_room"

    # 2) Stationary device WITHOUT an ESPHome Area -> defaults to BLE Roaming (while keeping stationary VFM guard)
    desk_unassigned, _ = make_esphome_device(
        hass,
        slug="desk_unassigned",
        mac="aa:bb:cc:11:00:02",
        area_id=None,
        stationary=1,
    )
    defs_unassigned = _detect_hardware_defaults(hass, desk_unassigned)
    assert defs_unassigned[CONF_DEVICE_GROUP] == "wall_panels"
    assert defs_unassigned[CONF_NATIVE_BLE_TRACKING] is True
    assert defs_unassigned[CONF_BLE_AUTO_SWITCH] is True
    assert defs_unassigned[CONF_SYNC_DEVICE_AREA] is False
    assert defs_unassigned[CONF_DEFAULT_AREA] == ""

    merged_auto = _apply_onboarding_profile_and_defaults(
        hass,
        desk_unassigned,
        {CONF_ESPHOME_DEVICE_ID: desk_unassigned.id, CONF_DEVICE_GROUP: "auto"},
    )
    assert merged_auto[CONF_NATIVE_BLE_TRACKING] is True
    assert merged_auto[CONF_BLE_AUTO_SWITCH] is True
    assert merged_auto[CONF_SYNC_DEVICE_AREA] is False

    # 3) Roaming round battery display -> defaults to `pocket_carry` + BLE Roaming (empty CONF_DEFAULT_AREA)
    pocket_dev, _ = make_esphome_device(
        hass,
        slug="pocket_roam",
        mac="aa:bb:cc:11:00:03",
        area_id="garage",
        stationary=0,
    )
    defs_pocket = _detect_hardware_defaults(hass, pocket_dev)
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
    assert _detect_hardware_defaults(hass, mobile_dev)[CONF_DEVICE_GROUP] == "handhelds"
    wrist_dev, _ = make_esphome_device(
        hass,
        slug="wrist_roam",
        mac="aa:bb:cc:11:00:05",
        stationary=0,
        wearable=1,
        shape="square",
    )
    assert _detect_hardware_defaults(hass, wrist_dev)[CONF_DEVICE_GROUP] == "wearables"

    # 4) Explicit onboarding toggle override: pinning handheld to Static adopts ESPHome Area; enabling roaming on desk clears it
    pinned_pocket = _apply_onboarding_profile_and_defaults(
        hass,
        pocket_dev,
        {
            CONF_ESPHOME_DEVICE_ID: pocket_dev.id,
            CONF_DEVICE_GROUP: "auto",
            CONF_NATIVE_BLE_TRACKING: False,
        },
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
    )
    assert roaming_desk[CONF_NATIVE_BLE_TRACKING] is True
    assert roaming_desk[CONF_BLE_AUTO_SWITCH] is True
    assert roaming_desk[CONF_SYNC_DEVICE_AREA] is False
    assert roaming_desk[CONF_DEFAULT_AREA] == ""
