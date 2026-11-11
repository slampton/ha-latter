"""Integration tests for LatterConfigFlow, LatterDeviceSubentryFlow, LatterBleTagSubentryFlow, and OptionsFlow."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.helpers import device_registry as dr

from custom_components.latter.config_flow import (
    LatterBleTagSubentryFlow,
    LatterConfigFlow,
    LatterDeviceSubentryFlow,
    LatterOptionsFlowHandler,
    ble_tag_option_defaults,
    device_option_defaults,
)
from custom_components.latter.const import (
    CONF_ALARM_ENTITY,
    CONF_BLE_TARGET_ADDRESS,
    CONF_DEVICE_GROUP,
    CONF_ESPHOME_DEVICE_ID,
    CONF_NATIVE_BLE_TRACKING,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
)


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

    # Reconfigure & OptionsFlow update global weather/alarm entities
    reconf = LatterConfigFlow()
    reconf.hass = hass
    reconf.context = {"entry_id": entry.entry_id}
    assert (await reconf.async_step_reconfigure())["type"] == "form"
    reconf_done = await reconf.async_step_reconfigure(
        {CONF_WEATHER_ENTITY: "weather.home", CONF_ALARM_ENTITY: "alarm_control_panel.home_alarm"}
    )
    assert reconf_done["reason"] == "reconfigure_successful"

    opt_flow = LatterConfigFlow.async_get_options_flow(entry)
    assert isinstance(opt_flow, LatterOptionsFlowHandler)
    opt_flow.hass = hass
    opt_flow.config_entry = entry
    assert (await opt_flow.async_step_init())["type"] == "form"
    opt_done = await opt_flow.async_step_init({CONF_WEATHER_ENTITY: "weather.home"})
    assert opt_done["type"] == "create_entry"
    assert SUBENTRY_DEVICE in LatterConfigFlow.async_get_supported_subentry_types(entry)


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
        {"name": "Backpack Tag", CONF_BLE_TARGET_ADDRESS: "AA:11:22:33:44:55", "assigned_person": "person.sean"}
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

    # Pure option default helpers
    assert device_option_defaults(hass, dev2, {"w": 466, "h": 466, "wearable": 1})[CONF_DEVICE_GROUP] == "wearables"
    assert ble_tag_option_defaults("Wallet", "11:22:33:44:55:99")[CONF_BLE_TARGET_ADDRESS] == "11:22:33:44:55:99"
