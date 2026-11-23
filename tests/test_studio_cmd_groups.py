"""Tests for Studio Device Groups lifecycle, backup export/import, multi-entity Home Hub settings, and preset migration."""

from __future__ import annotations

import json
from typing import Any

from custom_components.latter.const import (
    CONF_DEVICE_GROUP,
    CONF_DEVICE_GROUPS,
    STUDIO_REV,
)
from custom_components.latter.groups.device_groups import (
    BUILTIN_GROUP_PRESET_VERSION,
    CONF_BUILTIN_GROUP_PRESET_VERSION,
    get_device_groups,
)
from custom_components.latter.hub_registry import get_global_config
from tests.helpers import call_ws, ensure_area, make_ws_connection


async def test_studio_commands_device_groups_and_backup_restore(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise Studio Device Groups lifecycle, Backup Export/Import, and Device Reset."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    ensure_area(hass, "Living Room", area_id="living_room")
    conn = make_ws_connection(hass)
    msg_seq = 100

    async def _sys_cmd(
        command: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        nonlocal msg_seq
        msg_seq += 1
        await call_ws(
            hass,
            conn,
            msg_seq,
            "latter/system/command",
            command=command,
            subentry_id=coord.subentry_id,
            payload=payload or {},
            studio_rev=STUDIO_REV,
        )
        assert not conn.errors, f"{command} failed: {conn.errors}"
        return conn.results[-1][1]

    async def _dev_cmd(
        command: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        nonlocal msg_seq
        msg_seq += 1
        await call_ws(
            hass,
            conn,
            msg_seq,
            "latter/device/command",
            command=command,
            subentry_id=coord.subentry_id,
            payload=payload or {},
            studio_rev=STUDIO_REV,
        )
        assert not conn.errors, f"{command} failed: {conn.errors}"
        return conn.results[-1][1]

    secret_pin = "846291"
    await _sys_cmd("set_security_pin", {"pin": secret_pin})
    await _sys_cmd(
        "set_security_pin", {"subentry_id": coord.subentry_id, "pin": secret_pin}
    )

    # Device Groups lifecycle: create -> update_group_baseline -> apply_batch_device_setting -> Save Custom Group -> delete
    await _sys_cmd(
        "create_device_group",
        {"name": "Guest Suites", "description": "Guest displays"},
    )
    await _dev_cmd("save_device_config", {"config": {"device_group": "guest_suites"}})
    assert coord.device_group == "guest_suites"
    await _sys_cmd(
        "update_group_baseline",
        {"group_id": "guest_suites", "source_subentry_id": coord.subentry_id},
    )
    assert coord.device_group == "guest_suites"
    baseline_state = await _sys_cmd(
        "update_group_baseline",
        {
            "group_id": "guest_suites",
            "config": {"alert_volume": 65, "area_handoff": True},
        },
    )
    assert coord.device_group == "guest_suites"
    sys_ctrl_by_pref = {
        c["pref_key"]: c
        for c in baseline_state["system_controls"]
        if c.get("pref_key")
    }
    for op_key in (
        "native_ble_tracking",
        "ble_auto_switch",
        "sync_device_area",
        "area_handoff",
        "tools_items",
        "games_items",
        "do_not_disturb",
    ):
        assert op_key in sys_ctrl_by_pref
    assert sys_ctrl_by_pref["tools_items"]["section"] == "interface"
    assert sys_ctrl_by_pref["tools_items"]["tier"] == "interface"
    assert sys_ctrl_by_pref["tools_items"]["domain"] == "pills"
    assert sys_ctrl_by_pref["games_items"]["section"] == "interface"
    assert sys_ctrl_by_pref["games_items"]["tier"] == "interface"
    assert sys_ctrl_by_pref["games_items"]["domain"] == "pills"
    assert any(
        t["device_slug"] == coord.device_slug and t["state"] == "on"
        for t in sys_ctrl_by_pref["area_handoff"]["targets"]
    )

    # Appearance batch update preserves group assignment (including tools_items & games_items)
    await _sys_cmd(
        "apply_batch_device_setting",
        {
            "target": "group:guest_suites",
            "config": {
                "area_categories": "light,scene,all",
                "tools_items": "flashlight,calculator,dice",
                "games_items": "2048,chomp",
                "pinned_items": [
                    {"kind": "route", "target": "weather:moon", "label": "Moon"},
                ],
            },
        },
    )
    assert coord.tools_items_csv == "flashlight,calculator,dice"
    assert coord.games_items_csv == "2048,chomp"
    assert len(coord.pinned_items) == 1
    assert coord.pinned_items[0]["target"] == "weather:moon"
    assert coord.device_group == "guest_suites"

    # Operational one-off batch tweak diverges from Guest Suites baseline -> auto-switches to 'custom'
    await _sys_cmd(
        "apply_batch_device_setting",
        {"target": "group:guest_suites", "config": {"alert_volume": 40}},
    )
    assert coord.device_group == "custom"

    # Save Custom Group (source_subentry_id + assign_source=True) creates group & assigns device
    saved_grp_state = await _sys_cmd(
        "create_device_group",
        {
            "name": "VIP Suites",
            "description": "Saved from custom device",
            "source_subentry_id": coord.subentry_id,
            "assign_source": True,
        },
    )
    assert coord.device_group == "vip_suites"
    vip_grp = next(
        g for g in saved_grp_state["device_groups"] if g["id"] == "vip_suites"
    )
    assert vip_grp["device_config"]["alert_volume"] == 40

    # Built-in groups cannot be deleted; deleting custom group resets members to 'custom'
    msg_seq += 1
    await call_ws(
        hass,
        conn,
        msg_seq,
        "latter/system/command",
        command="delete_device_group",
        payload={"group_id": "handhelds"},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "not_allowed"
    conn.errors.clear()

    await _sys_cmd("delete_device_group", {"group_id": "vip_suites"})
    assert coord.device_group == "custom"
    await _sys_cmd("delete_device_group", {"group_id": "guest_suites"})

    # Wrong scope error check ('save_device_config' sent to system scope)
    msg_seq += 1
    await call_ws(
        hass,
        conn,
        msg_seq,
        "latter/system/command",
        command="save_device_config",
        payload={},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "wrong_scope"
    conn.errors.clear()

    # 3) Backup Export & Import (System + Device scopes) & Device Reset
    msg_seq += 1
    await call_ws(hass, conn, msg_seq, "latter/system/export", studio_rev=STUDIO_REV)
    sys_bundle = conn.results[-1][1]["bundle"]
    assert sys_bundle["scope"] == "system"
    assert "photo_collections" in sys_bundle
    assert "photo_metadata" in sys_bundle
    assert secret_pin not in json.dumps(sys_bundle)

    msg_seq += 1
    await call_ws(
        hass,
        conn,
        msg_seq,
        "latter/system/import",
        bundle=sys_bundle,
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors

    msg_seq += 1
    await call_ws(
        hass,
        conn,
        msg_seq,
        "latter/device/export",
        subentry_id=coord.subentry_id,
        studio_rev=STUDIO_REV,
    )
    dev_bundle = conn.results[-1][1]["bundle"]
    assert dev_bundle["scope"] == "device"
    assert (
        dev_bundle["device"]["device_config"]["tools_items"]
        == "flashlight,calculator,dice"
    )
    assert dev_bundle["device"]["device_config"]["games_items"] == "2048,chomp"

    msg_seq += 1
    await call_ws(
        hass,
        conn,
        msg_seq,
        "latter/device/import",
        subentry_id=coord.subentry_id,
        bundle=dev_bundle,
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors

    msg_seq += 1
    await call_ws(
        hass,
        conn,
        msg_seq,
        "latter/device/reset",
        subentry_id=coord.subentry_id,
        device_settings=True,
        latter_options=True,
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_multi_entity_home_hub_settings_and_strict_garage_cover_filtering(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify D-059 multi-entity Home Hub lists, domain validation, and strict garage-only cover catalog filtering."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)

    hass.states.async_set(
        "cover.main_garage",
        "closed",
        {"device_class": "garage", "friendly_name": "Main Garage"},
    )
    hass.states.async_set(
        "cover.workshop_bay_garage",
        "open",
        {"friendly_name": "Workshop Garage Door"},
    )
    hass.states.async_set(
        "cover.living_blinds",
        "open",
        {"device_class": "blind", "friendly_name": "Living Blinds"},
    )
    hass.states.async_set(
        "cover.bedroom_curtains",
        "closed",
        {"device_class": "curtain", "friendly_name": "Bedroom Curtains"},
    )
    hass.states.async_set(
        "cover.driveway_gate",
        "closed",
        {"device_class": "gate", "friendly_name": "Driveway Gate"},
    )
    hass.states.async_set(
        "cover.untyped_shades",
        "closed",
        {"friendly_name": "Office Shades"},
    )
    hass.states.async_set(
        "climate.downstairs",
        "heat",
        {"friendly_name": "Downstairs", "temperature": 70},
    )
    hass.states.async_set(
        "climate.upstairs",
        "cool",
        {"friendly_name": "Upstairs", "temperature": 74},
    )
    await hass.async_block_till_done()

    conn = make_ws_connection(hass)
    await call_ws(hass, conn, 1, "latter/system/get_state", studio_rev=STUDIO_REV)
    assert not conn.errors
    st = conn.results[-1][1]
    garage_ids = [item["id"] for item in st["catalog"]["garages"]]
    assert garage_ids == ["cover.main_garage", "cover.workshop_bay_garage"]
    clim_meta = {item["id"]: item for item in st["catalog"]["climates"]}
    assert "state_label" not in clim_meta["climate.downstairs"]
    assert "state_tone" not in clim_meta["climate.downstairs"]

    await call_ws(
        hass,
        conn,
        2,
        "latter/system/command",
        command="save_system_config",
        payload={
            "config": {
                "thermostat_entities": ["climate.downstairs", "climate.upstairs"],
                "lock_entities": ["lock.front_door", "lock.back_door"],
                "garage_entities": ["cover.main_garage", "cover.workshop_bay_garage"],
                "vacuum_entities": ["vacuum.main_floor", "vacuum.upstairs"],
            }
        },
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    saved_sc = conn.results[-1][1]["system_config"]
    assert saved_sc["thermostat_entities"] == [
        "climate.downstairs",
        "climate.upstairs",
    ]
    assert saved_sc["lock_entities"] == ["lock.front_door", "lock.back_door"]
    assert saved_sc["garage_entities"] == [
        "cover.main_garage",
        "cover.workshop_bay_garage",
    ]
    assert saved_sc["vacuum_entities"] == ["vacuum.main_floor", "vacuum.upstairs"]
    assert coord.thermostat_entities == ["climate.downstairs", "climate.upstairs"]

    # Wrong domain inside thermostat_entities is rejected cleanly
    await call_ws(
        hass,
        conn,
        3,
        "latter/system/command",
        command="save_system_config",
        payload={"config": {"thermostat_entities": ["light.kitchen"]}},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors and conn.errors[-1][0] == 3

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_builtin_group_reset_preset_and_v2_preset_migration(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify `update_group_baseline(reset_to_default=True)` and one-time `BUILTIN_GROUP_PRESET_VERSION` sync (`D-067`)."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, stationary=1)
    conn = make_ws_connection(hass)

    # Wall & Desk Panels default: `screensaver_mode == "Never"`, `docked_idle_timeout == "Never"`
    await call_ws(
        hass,
        conn,
        1,
        "latter/device/command",
        subentry_id=coord.subentry_id,
        command="save_device_config",
        payload={"config": {"device_group": "wall_panels"}},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert coord.device_group == "wall_panels"
    assert coord.get_device_pref("screensaver_mode") == "Never"
    assert coord.get_device_pref("docked_idle_timeout") == "Never"

    # Mutate `wall_panels` baseline, then reset it via `reset_to_default: True`
    await call_ws(
        hass,
        conn,
        2,
        "latter/system/command",
        command="update_group_baseline",
        payload={
            "group_id": "wall_panels",
            "include_display": True,
            "config": {"screensaver_mode": "Always", "docked_idle_timeout": "5 min"},
        },
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert coord.get_device_pref("screensaver_mode") == "Always"
    assert coord.get_device_pref("docked_idle_timeout") == "5 min"

    await call_ws(
        hass,
        conn,
        3,
        "latter/system/command",
        command="update_group_baseline",
        payload={"group_id": "wall_panels", "reset_to_default": True},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert coord.device_group == "wall_panels"
    assert coord.get_device_pref("screensaver_mode") == "Never"
    assert coord.get_device_pref("docked_idle_timeout") == "Never"

    # Custom groups reject `reset_to_default: True` with `not_allowed`
    await call_ws(
        hass,
        conn,
        4,
        "latter/system/command",
        command="create_device_group",
        payload={"name": "Nightstands"},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    await call_ws(
        hass,
        conn,
        5,
        "latter/system/command",
        command="update_group_baseline",
        payload={"group_id": "nightstands", "reset_to_default": True},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "not_allowed"
    assert await hass.config_entries.async_unload(entry.entry_id) is True

    # Simulate an existing pre-v2 `.storage/latter.site` reload where `handhelds` had stale `wake_word_mode = "Always On"`
    global_cfg = get_global_config(hass)
    global_cfg.pop(CONF_BUILTIN_GROUP_PRESET_VERSION, None)
    global_cfg[CONF_DEVICE_GROUPS] = [
        {
            "id": "handhelds",
            "name": "Handhelds",
            "builtin": True,
            "device_config": {"wake_word_mode": "Always On"},
        },
        {
            "id": "nightstands",
            "name": "Nightstands",
            "builtin": False,
            "device_config": {"wake_word_mode": "Disabled"},
        },
    ]
    sub = next(iter(entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        entry,
        sub,
        data={
            **sub.data,
            CONF_DEVICE_GROUP: "handhelds",
            "wake_word_mode": "Always On",
        },
    )

    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()
    assert BUILTIN_GROUP_PRESET_VERSION == 4
    assert global_cfg[CONF_BUILTIN_GROUP_PRESET_VERSION] == BUILTIN_GROUP_PRESET_VERSION
    upgraded_groups = {g["id"]: g for g in get_device_groups(hass)}
    assert (
        upgraded_groups["handhelds"]["device_config"]["wake_word_mode"] == "Docked Only"
    )
    assert upgraded_groups["handhelds"]["device_config"]["day_brightness"] == 90
    assert upgraded_groups["handhelds"]["device_config"]["night_brightness"] == 35
    assert upgraded_groups["handhelds"]["device_config"]["bedtime_brightness"] == 15
    assert upgraded_groups["wearables"]["device_config"]["day_brightness"] == 80
    assert upgraded_groups["wearables"]["device_config"]["night_brightness"] == 25
    assert upgraded_groups["wearables"]["device_config"]["bedtime_brightness"] == 15
    assert (
        upgraded_groups["nightstands"]["device_config"]["wake_word_mode"] == "Disabled"
    )
    reloaded_coord = entry.runtime_data.coordinators[sub.subentry_id]
    assert reloaded_coord.get_device_pref("wake_word_mode") == "Docked Only"
    assert reloaded_coord.get_device_pref("night_brightness") == 35
    assert reloaded_coord.get_device_pref("bedtime_brightness") == 15
    assert reloaded_coord.device_group == "handhelds"
    assert await hass.config_entries.async_unload(entry.entry_id) is True
