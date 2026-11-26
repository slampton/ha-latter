"""Tests for Studio Device Groups lifecycle, backup export/import, multi-entity Home Hub settings, and preset migration."""

from __future__ import annotations

import json
from typing import Any

from custom_components.latter.const import (
    CONF_DEVICE_GROUPS,
    STUDIO_REV,
)
from custom_components.latter.groups.device_groups import (
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

    # Appearance batch update preserves group assignment (including tools_items, games_items, & shortcut styling)
    await _sys_cmd(
        "apply_batch_device_setting",
        {
            "target": "group:guest_suites",
            "config": {
                "area_categories": "light,scene,all",
                "tools_items": "flashlight,calculator,dice",
                "games_items": "blocks,chomp",
                "pinned_items": [
                    {
                        "kind": "route",
                        "target": "weather:moon",
                        "label": "Moon",
                        "badge_style": "inverted",
                        "accent": "gold",
                        "page": 0,
                        "col": 1,
                        "row": 0,
                        "col_span": 2,
                    },
                ],
                "pinned_page_titles": {"0": "Nightstand"},
            },
        },
    )
    assert coord.tools_items_csv == "flashlight,calculator,dice"
    assert coord.games_items_csv == "blocks,chomp"
    assert len(coord.pinned_items) == 1
    assert coord.pinned_items[0]["target"] == "weather:moon"
    assert coord.pinned_items[0]["badge_style"] == "inverted"
    assert coord.pinned_items[0]["accent"] == "gold"
    assert coord.pinned_items[0]["col_span"] == 2
    assert coord.pinned_page_titles == {"0": "Nightstand"}
    assert coord.device_group == "guest_suites"

    # Operational one-off batch tweak diverges from Guest Suites baseline -> auto-switches to 'custom'
    await _sys_cmd(
        "apply_batch_device_setting",
        {"target": "group:guest_suites", "config": {"alert_volume": 40}},
    )
    assert coord.device_group == "custom"

    # Save Custom Group (source_subentry_id + include_interface=True + assign_source=True) preserves shortcut styling
    saved_grp_state = await _sys_cmd(
        "create_device_group",
        {
            "name": "VIP Suites",
            "description": "Saved from custom device",
            "source_subentry_id": coord.subentry_id,
            "include_interface": True,
            "assign_source": True,
        },
    )
    assert coord.device_group == "vip_suites"
    vip_grp = next(
        g for g in saved_grp_state["device_groups"] if g["id"] == "vip_suites"
    )
    assert vip_grp["device_config"]["alert_volume"] == 40
    assert vip_grp["device_config"]["pinned_items"][0]["badge_style"] == "inverted"
    assert vip_grp["device_config"]["pinned_items"][0]["accent"] == "gold"
    assert vip_grp["device_config"]["pinned_items"][0]["col_span"] == 2
    assert vip_grp["device_config"]["pinned_page_titles"] == {"0": "Nightstand"}

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
    assert dev_bundle["device"]["device_config"]["games_items"] == "blocks,chomp"
    assert (
        dev_bundle["device"]["device_config"]["pinned_items"][0]["badge_style"]
        == "inverted"
    )
    assert dev_bundle["device"]["device_config"]["pinned_items"][0]["accent"] == "gold"
    assert dev_bundle["device"]["device_config"]["pinned_items"][0]["col_span"] == 2
    assert dev_bundle["device"]["device_config"]["pinned_page_titles"] == {"0": "Nightstand"}

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
    assert coord.pinned_items[0]["badge_style"] == "inverted"
    assert coord.pinned_items[0]["accent"] == "gold"
    assert coord.pinned_items[0]["col_span"] == 2
    assert coord.pinned_page_titles == {"0": "Nightstand"}

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


async def test_builtin_group_reset_preset_and_reload_normalization(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify `update_group_baseline(reset_to_default=True)` and clean group normalization without legacy preset_version shims."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, stationary=1)
    conn = make_ws_connection(hass)

    # Wall & Desk Panels default: `screensaver_mode == "Never"`, `docked_idle_timeout == "Never"`, `glass_style == "Auto"`
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
    assert coord.get_device_pref("glass_style") == "Auto"

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
            "config": {
                "screensaver_mode": "Always",
                "docked_idle_timeout": "5 min",
                "glass_style": "Dark",
            },
        },
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert coord.get_device_pref("screensaver_mode") == "Always"
    assert coord.get_device_pref("docked_idle_timeout") == "5 min"
    assert coord.get_device_pref("glass_style") == "Dark"

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

    # Reload with stored custom group + fresh builtin defaults (no preset_version shim!)
    global_cfg = get_global_config(hass)
    global_cfg[CONF_DEVICE_GROUPS] = [
        {
            "id": "nightstands",
            "name": "Nightstands",
            "builtin": False,
            "include_interface": True,
            "device_config": {
                "wake_word_mode": "Disabled",
                "dock_items": [
                    {
                        "kind": "route",
                        "target": "app:music",
                        "action": "",
                        "label": "",
                        "icon": "",
                        "confirm": False,
                    }
                ],
                "pinned_items": [
                    {
                        "kind": "route",
                        "target": "weather:moon",
                        "action": "",
                        "label": "Moon",
                        "icon": "",
                        "confirm": False,
                    }
                ],
            },
        },
    ]
    sub = next(iter(entry.subentries.values()))
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()
    assert "builtin_group_preset_version" not in global_cfg
    reloaded_groups = {g["id"]: g for g in get_device_groups(hass)}
    for grp in reloaded_groups.values():
        assert "preset_version" not in grp
    assert (
        reloaded_groups["handhelds"]["device_config"]["wake_word_mode"] == "Docked Only"
    )
    assert reloaded_groups["handhelds"]["device_config"]["day_brightness"] == 90
    assert reloaded_groups["handhelds"]["device_config"]["night_brightness"] == 35
    assert reloaded_groups["handhelds"]["device_config"]["bedtime_brightness"] == 15
    assert reloaded_groups["wearables"]["device_config"]["day_brightness"] == 80
    assert reloaded_groups["wearables"]["device_config"]["night_brightness"] == 25
    assert reloaded_groups["wearables"]["device_config"]["bedtime_brightness"] == 15
    assert (
        reloaded_groups["nightstands"]["device_config"]["wake_word_mode"] == "Disabled"
    )
    assert reloaded_groups["nightstands"]["device_config"]["dock_items"][0]["badge_style"] == ""
    assert reloaded_groups["nightstands"]["device_config"]["dock_items"][0]["accent"] == ""
    assert reloaded_groups["nightstands"]["device_config"]["pinned_items"][0]["badge_style"] == ""
    assert reloaded_groups["nightstands"]["device_config"]["pinned_items"][0]["accent"] == ""
    reloaded_coord = entry.runtime_data.coordinators[sub.subentry_id]
    assert reloaded_coord.device_group == "wall_panels"
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_group_baseline_reset_releases_system_lock_and_batch_setting_parallelizes(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any
) -> None:
    """Verify `reset_to_default=True` releases `system_config_lock` before awaiting coordinators and `apply_batch_device_setting` updates targets concurrently."""
    import asyncio
    from unittest.mock import patch

    from custom_components.latter.groups.device_groups import (
        async_apply_group_baseline_to_coordinators,
    )
    from custom_components.latter.hub_registry import get_system_config_lock
    from custom_components.latter.studio import system_commands as sys_cmds

    entry, _sys_obj, coord1 = await setup_latter_hub(hass)
    assert coord1 is not None
    conn = make_ws_connection(hass)

    # Assign `coord1` to `handhelds` so its effective `device_group` matches `handhelds`
    assign_res = await call_ws(
        hass,
        conn,
        79,
        "latter/device/command",
        command="save_device_config",
        subentry_id=coord1.subentry_id,
        payload={"config": {"device_group": "handhelds"}},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert assign_res is not None and assign_res["success"] is True
    assert coord1.device_group == "handhelds"

    # 1) `update_group_baseline(..., reset_to_default=True)` releases `system_config_lock` BEFORE awaiting coordinators
    lock_states: list[bool] = []

    async def _spy_apply_baseline(*args: Any, **kwargs: Any) -> Any:
        lock_states.append(get_system_config_lock(hass).locked())
        return await async_apply_group_baseline_to_coordinators(*args, **kwargs)

    with patch.object(
        sys_cmds, "async_apply_group_baseline_to_coordinators", side_effect=_spy_apply_baseline
    ):
        res_reset = await call_ws(
            hass,
            conn,
            80,
            "latter/system/command",
            command="update_group_baseline",
            payload={"group_id": "handhelds", "reset_to_default": True},
            studio_rev=STUDIO_REV,
        )
    assert not conn.errors
    assert res_reset is not None and res_reset["success"] is True
    assert lock_states == [False]

    # 2) Adopt a 2nd Device and verify `apply_batch_device_setting` runs target updates concurrently
    esp_dev2, _mac2 = make_esphome_device(
        hass,
        slug="kitchen_display",
        mac="aa:bb:cc:dd:ee:02",
        name="Kitchen Display",
    )
    add_res = await call_ws(
        hass,
        conn,
        81,
        "latter/system/command",
        command="add_latter_device",
        payload={"esphome_device_id": esp_dev2.id},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert add_res is not None and add_res["success"] is True
    # `add_latter_device` reloads the System config entry, replacing `entry.runtime_data`
    coord1 = entry.runtime_data.coordinators[coord1.subentry_id]
    coord2 = entry.runtime_data.coordinators[add_res["result"]["adopted_subentry_id"]]

    both_started = asyncio.Event()
    in_flight = 0
    orig_apply1 = coord1.async_apply_options
    orig_apply2 = coord2.async_apply_options

    async def _barrier_apply(orig: Any) -> Any:
        nonlocal in_flight
        in_flight += 1
        if in_flight >= 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=2.0)
        return await orig()

    async def _barrier1() -> Any:
        return await _barrier_apply(orig_apply1)

    async def _barrier2() -> Any:
        return await _barrier_apply(orig_apply2)

    with (
        patch.object(coord1, "async_apply_options", new=_barrier1),
        patch.object(coord2, "async_apply_options", new=_barrier2),
    ):
        batch_res = await call_ws(
            hass,
            conn,
            82,
            "latter/system/command",
            command="apply_batch_device_setting",
            payload={
                "target": "all",
                "config": {"glass_style": "Dark"},
            },
            studio_rev=STUDIO_REV,
        )
    assert not conn.errors
    assert batch_res is not None and batch_res["success"] is True
    assert in_flight == 2
    assert coord1.device_data.get("glass_style") == "Dark"
    assert coord2.device_data.get("glass_style") == "Dark"
    assert await hass.config_entries.async_unload(entry.entry_id) is True
