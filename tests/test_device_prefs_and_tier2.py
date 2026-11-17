"""Integration tests for the 3-Tier Device Preferences architecture (`D-031`), Tier 2 entities, two-way sync, and sleep-safe Device Groups."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.latter import async_unload_entry
from custom_components.latter.groups import (
    device_matches_group_baseline,
    get_device_groups,
    resolve_effective_device_group,
)
from custom_components.latter.services import async_dispatch_bound_rpc
from custom_components.latter.studio.commands import STUDIO_REV


def _register_wifi_sensor(hass: Any, coord: Any, state: str = "-52") -> str:
    ent_reg = er.async_get(hass)
    eid = f"sensor.{coord.device_slug}_wi_fi_signal"
    if ent_reg.async_get(eid) is None:
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=eid,
                platform="esphome",
                device_id=coord.esphome_device_id,
                config_entry_id=f"esp_entry_{coord.device_slug}",
                original_name="Wi-Fi Signal",
            )
        )
    hass.states.async_set(eid, state)
    return eid


def _find_entity(hass: Any, platform: str, entity_id: str) -> Any:
    for ent in hass.data.get("_test_entities", {}).get(platform, []):
        if ent.entity_id == entity_id:
            return ent
    raise AssertionError(f"Entity {entity_id} not found in platform {platform}")


async def _call_ws(
    hass: Any, conn: Any, msg_id: int, ws_type: str, **payload: Any
) -> None:
    handler = hass._ws_commands[ws_type]
    schema = getattr(handler, "_ws_schema", None)
    raw_msg = {"id": msg_id, "type": ws_type, **payload}
    validated = schema(raw_msg) if schema is not None else raw_msg
    await handler(hass, conn, validated)


@pytest.mark.asyncio
async def test_device_hello_cases_a_b_and_c(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify Case A (initial adoption seed), Case B (wiped ESP32 replacement), and Case C (offline per-key merge)."""
    orig_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda _d: orig_sleep(0))

    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    _register_wifi_sensor(hass, coord, "-48")
    manifest_raw = hass.states.get(f"sensor.{coord.device_slug}_system_hardware_manifest").state

    # Case A: Initial adoption (`coord.prefs_seq == 0`) seeds untouched keys while preserving onboarding `native_ble_tracking=True`
    assert coord.prefs_seq == 0
    await coord.async_handle_device_hello(
        boot_id="boot_a",
        manifest_raw=manifest_raw,
        prefs_seq=0,
        dirty_prefs="\x1e".join(["alert_volume=65", "ble_beacon_enabled=0", "screensaver_style=Starfield"]),
    )
    assert coord.prefs_seq >= 1
    assert coord.get_device_pref("alert_volume") == 65
    assert coord.get_device_pref("screensaver_style") == "Starfield"
    # Pre-configured onboarding key (`native_ble_tracking=True`) is preserved over uncommissioned `ble_beacon_enabled=0`
    assert coord.native_ble_tracking_enabled is True

    # Edit `wake_word_mode` and `alert_volume` in HA while device is at `seq_after_adopt`
    seq_after_adopt = coord.prefs_seq
    await coord.async_update_device_prefs({"wake_word_mode": "Always On"})
    ha_seq = coord.prefs_seq
    assert ha_seq > seq_after_adopt
    assert coord.prefs_key_seq["wake_word_mode"] == ha_seq

    # Case C: Offline touchscreen edit at `base_seq = seq_after_adopt`:
    # - `color_profile` was NOT edited in HA after `seq_after_adopt` (`prefs_key_seq <= dev_seq`) -> touchscreen wins!
    # - `wake_word_mode` WAS edited in HA after `seq_after_adopt` (`prefs_key_seq > dev_seq`) -> HA sleep-safe edit wins!
    await coord.async_handle_device_hello(
        boot_id="boot_a",
        manifest_raw=manifest_raw,
        prefs_seq=seq_after_adopt,
        dirty_prefs="\x1e".join(["color_profile=Pink", "wake_word_mode=Disabled"]),
    )
    assert coord.prefs_seq == max(ha_seq, seq_after_adopt) + 1
    assert coord.get_device_pref("color_profile") == "Pink"
    assert coord.get_device_pref("wake_word_mode") == "Always On"

    # Case B: Replace Hardware / wiped ESP32 (`coord.prefs_seq > 0`, replacement board boots with `prefs_seq=0`)
    seq_before_replace = coord.prefs_seq
    hass.services.calls.clear()
    await coord.async_handle_device_hello(
        boot_id="boot_replacement",
        manifest_raw=manifest_raw,
        prefs_seq=0,
        dirty_prefs="color_profile=Green",
    )
    assert coord.prefs_seq == seq_before_replace
    assert coord.get_device_pref("color_profile") == "Pink"
    assert coord.get_device_pref("alert_volume") == 65
    pushed_domains = [
        c.data.get("domain")
        for c in hass.services.calls
        if c.domain == "esphome" and c.service == f"{coord.device_slug}_latter_push_v3"
    ]
    assert "device_prefs" in pushed_domains

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_online_set_device_prefs_rpc_and_diagnostic_sensor(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify `set_device_prefs` bound RPC updates subentry, auto-switches `device_group` to `custom` on behavior drift, and updates `sensor.<slug>_device_prefs`."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    _register_wifi_sensor(hass, coord, "-50")

    # Join Pocket Carry group baseline first
    group_sel = _find_entity(hass, "select", f"select.{coord.device_slug}_device_group")
    await group_sel.async_select_option("Pocket Carry")
    assert coord.device_group == "pocket_carry"
    assert coord.get_device_pref("tap_to_wake") == "Docked Only"
    assert coord.get_device_pref("pickup_to_wake") == "Docked Only"

    # Changing a personal Display preference (`clock_face`) preserves `pocket_carry`!
    await async_dispatch_bound_rpc(
        hass,
        coord,
        "set_device_prefs",
        {
            "base_seq": coord.prefs_seq,
            "changes": "clock_face=Hybrid Digital",
        },
    )
    assert coord.get_device_pref("clock_face") == "Hybrid Digital"
    assert coord.device_group == "pocket_carry"

    # Diverging an operational key (`tap_to_wake` or `alert_volume`) flips `device_group` to `custom`
    await async_dispatch_bound_rpc(
        hass,
        coord,
        "set_device_prefs",
        {
            "base_seq": coord.prefs_seq,
            "changes": "\x1e".join(["tap_to_wake=Disabled", "alert_volume=70"]),
        },
    )
    assert coord.get_device_pref("tap_to_wake") == "Disabled"
    assert coord.get_device_pref("alert_volume") == 70
    assert coord.device_group == "custom"

    prefs_st = hass.states.get(f"sensor.{coord.device_slug}_device_prefs")
    assert prefs_st is not None
    assert int(prefs_st.state) == coord.prefs_seq
    assert prefs_st.attributes["rev"] >= 1

    _seq, payload_attrs = coord.get_device_prefs_payload()
    assert payload_attrs["device_group"] == "custom"
    assert payload_attrs["alert_volume"] == 70
    assert payload_attrs["payload"].startswith("v3\x1f")

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_timer_alarm_state_event_driven_and_boot_reset(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `timer_alarm_state` RPC drives Tier 2 timer/alarm entities without polling and resets on cold boot."""
    orig_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda _d: orig_sleep(0))

    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    slug = coord.device_slug

    assert hass.states.get(f"binary_sensor.{slug}_timer_active").state == "off"
    assert hass.states.get(f"binary_sensor.{slug}_alarm_ringing").state == "off"
    assert int(hass.states.get(f"sensor.{slug}_timer_remaining").state) == 0

    anchor = 1000.0
    monkeypatch.setattr(time, "monotonic", lambda: anchor)

    await async_dispatch_bound_rpc(
        hass,
        coord,
        "timer_alarm_state",
        {"timer_running": 1, "timer_paused": 0, "remaining_sec": 120, "ringing": 0},
    )
    assert hass.states.get(f"binary_sensor.{slug}_timer_active").state == "on"
    assert int(hass.states.get(f"sensor.{slug}_timer_remaining").state) == 120

    # Advance monotonic clock by 35s -> computed locally with zero Wi-Fi polling
    monkeypatch.setattr(time, "monotonic", lambda: anchor + 35.0)
    coord.async_update_listeners()
    assert int(hass.states.get(f"sensor.{slug}_timer_remaining").state) == 85

    # Pause freezes countdown, ringing sets alarm_ringing on
    await async_dispatch_bound_rpc(
        hass,
        coord,
        "timer_alarm_state",
        {"timer_running": 0, "timer_paused": 1, "remaining_sec": 85, "ringing": 1},
    )
    monkeypatch.setattr(time, "monotonic", lambda: anchor + 60.0)
    coord.async_update_listeners()
    assert hass.states.get(f"binary_sensor.{slug}_timer_active").state == "off"
    assert hass.states.get(f"binary_sensor.{slug}_alarm_ringing").state == "on"
    assert int(hass.states.get(f"sensor.{slug}_timer_remaining").state) == 85

    # Reboot (`is_new_boot`) clears stale timer and ringing state
    manifest_raw = hass.states.get(f"sensor.{slug}_system_hardware_manifest").state
    await coord.async_handle_device_hello("fresh_boot_99", manifest_raw)
    assert hass.states.get(f"binary_sensor.{slug}_timer_active").state == "off"
    assert hass.states.get(f"binary_sensor.{slug}_alarm_ringing").state == "off"
    assert int(hass.states.get(f"sensor.{slug}_timer_remaining").state) == 0

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_tier2_select_number_sleep_safe_and_buttons_online_vs_offline(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify Tier 2 `select`/`number` persist while Device is sleeping, while action `button`s require online Wi-Fi."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)
    slug = coord.device_slug
    wifi_eid = _register_wifi_sensor(hass, coord, "unavailable")
    hass.states.async_set(f"sensor.{slug}_system_rpc_outbox", "unavailable")

    # BLE tags do not create Tier 2 display/audio controls
    assert hass.states.get("select.keys_tag_device_group") is None
    assert hass.states.get("select.keys_tag_wake_word_mode") is None
    assert hass.states.get("number.keys_tag_alert_volume") is None
    assert hass.states.get("button.keys_tag_find_my_device") is None

    # Sleep-safe select & number succeed while ESPHome Wi-Fi is `unavailable`
    assert hass.states.get(f"select.{slug}_power_profile") is None
    group_sel = _find_entity(hass, "select", f"select.{slug}_device_group")
    ww_sel = _find_entity(hass, "select", f"select.{slug}_wake_word_mode")
    vol_num = _find_entity(hass, "number", f"number.{slug}_alert_volume")
    find_btn = _find_entity(hass, "button", f"button.{slug}_find_my_device")
    ss_btn = _find_entity(hass, "button", f"button.{slug}_activate_screensaver")

    assert group_sel.options == [
        "Pocket Carry",
        "Handhelds",
        "Wearables",
        "Wall & Desk Panels",
        "Custom",
    ]
    await group_sel.async_select_option("Wearables")
    assert hass.states.get(f"select.{slug}_device_group").state == "Wearables"
    assert coord.get_device_pref("battery_screen_timeout") == "15s"
    assert coord.get_device_pref("tap_to_wake") == "Double Tap"

    await ww_sel.async_select_option("Always On")
    assert hass.states.get(f"select.{slug}_wake_word_mode").state == "Always On"
    assert hass.states.get(f"select.{slug}_device_group").state == "Custom"

    await vol_num.async_set_native_value(55)
    assert float(hass.states.get(f"number.{slug}_alert_volume").state) == 55.0
    assert coord.get_device_pref("alert_volume") == 55

    # Action buttons raise HomeAssistantError while sleeping
    with pytest.raises(HomeAssistantError):
        await find_btn.async_press()
    with pytest.raises(HomeAssistantError):
        await ss_btn.async_press()

    # Bring Device online -> action buttons dispatch `esphome.<slug>_latter_device_command`
    hass.states.async_set(wifi_eid, "-49")
    hass.states.async_set(f"sensor.{slug}_system_rpc_outbox", "")
    hass.services.calls.clear()

    await find_btn.async_press()
    await ss_btn.async_press()
    cmds = [
        c.data.get("command")
        for c in hass.services.calls
        if c.domain == "esphome" and c.service == f"{slug}_latter_device_command"
    ]
    assert cmds == ["find_my", "activate_screensaver"]

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_studio_device_action_and_sleep_safe_device_groups(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify Studio `device_action` WS command and 100% sleep-safe Device Groups (`sync`, `seed`, `set_group_device_setting`)."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    slug = coord.device_slug
    wifi_eid = _register_wifi_sensor(hass, coord, "-51")

    conn = websocket_api.ActiveConnection()
    hass.services.calls.clear()
    await _call_ws(
        hass,
        conn,
        1,
        "latter/device/command",
        studio_rev=STUDIO_REV,
        subentry_id=coord.subentry_id,
        command="device_action",
        payload={"action": "trigger_va"},
    )
    assert conn.errors == []
    assert any(
        c.domain == "esphome"
        and c.service == f"{slug}_latter_device_command"
        and c.data.get("command") == "trigger_va"
        for c in hass.services.calls
    )

    # Put Device to sleep (`unavailable`) and verify Device Groups still sync & detect drift via subentries!
    hass.states.async_set(wifi_eid, "unavailable")
    hass.states.async_set(f"sensor.{slug}_system_rpc_outbox", "unavailable")

    await _call_ws(
        hass,
        conn,
        2,
        "latter/device/command",
        studio_rev=STUDIO_REV,
        subentry_id=coord.subentry_id,
        command="save_device_config",
        payload={"config": {"device_group": "handhelds"}},
    )
    assert conn.errors == []
    assert resolve_effective_device_group(hass, coord) == "handhelds"

    # Update a group preference while Device is offline -> pushes into subentry immediately
    await _call_ws(
        hass,
        conn,
        3,
        "latter/system/command",
        studio_rev=STUDIO_REV,
        command="update_group_baseline",
        payload={"group_id": "handhelds", "config": {"alert_volume": 60}},
    )
    assert conn.errors == []
    assert coord.get_device_pref("alert_volume") == 60
    assert resolve_effective_device_group(hass, coord) == "handhelds"

    # Customize one preference on the sleeping Device -> effective group switches to `custom`
    await coord.async_update_device_prefs({"alert_volume": 95})
    assert resolve_effective_device_group(hass, coord) == "custom"

    # Update group baseline from sleeping Device -> captures all subentry preferences cleanly
    await _call_ws(
        hass,
        conn,
        4,
        "latter/system/command",
        studio_rev=STUDIO_REV,
        command="update_group_baseline",
        payload={"group_id": "handhelds", "source_subentry_id": coord.subentry_id},
    )
    assert conn.errors == []
    groups = get_device_groups(hass)
    assert [g["id"] for g in groups] == [
        "pocket_carry",
        "handhelds",
        "wearables",
        "wall_panels",
    ]
    handhelds = next(g for g in groups if g["id"] == "handhelds")
    assert handhelds["device_config"]["alert_volume"] == 95
    assert device_matches_group_baseline(hass, coord, groups, group_id="handhelds") is True

    # Re-assign `coord` back to `handhelds`, then opt `handhelds` into `include_display: True`
    group_sel = _find_entity(hass, "select", f"select.{slug}_device_group")
    await group_sel.async_select_option("Handhelds")
    assert resolve_effective_device_group(hass, coord) == "handhelds"

    await _call_ws(
        hass,
        conn,
        5,
        "latter/system/command",
        studio_rev=STUDIO_REV,
        command="update_group_baseline",
        payload={
            "group_id": "handhelds",
            "include_display": True,
            "config": {"clock_face": "Hybrid Digital"},
        },
    )
    assert conn.errors == []
    assert coord.get_device_pref("clock_face") == "Hybrid Digital"
    assert resolve_effective_device_group(hass, coord) == "handhelds"
    await coord.async_update_device_prefs({"clock_face": "Minimal Digital"})
    assert resolve_effective_device_group(hass, coord) == "custom"

    # Batch Controls target `roaming` pushes settings across roaming Devices without altering group baselines
    await _call_ws(
        hass,
        conn,
        6,
        "latter/system/command",
        studio_rev=STUDIO_REV,
        command="apply_batch_device_setting",
        payload={
            "target": "roaming",
            "config": {
                "weather_background": False,
                "activity_sources": "calendar,timers",
                "world_clocks": "London|Europe/London",
            },
        },
    )
    assert conn.errors == []
    assert coord.get_device_pref("weather_background") is False
    assert coord.activity_sources_csv == "calendar,timers"
    assert coord.get_device_pref("world_clocks") == "London|Europe/London"

    # Opt `pocket_carry` into `include_interface: True` and copy `world_clocks` via `copy_keys`
    await _call_ws(
        hass,
        conn,
        7,
        "latter/system/command",
        studio_rev=STUDIO_REV,
        command="update_group_baseline",
        payload={
            "group_id": "pocket_carry",
            "include_interface": True,
            "source_subentry_id": coord.subentry_id,
            "copy_keys": ["world_clocks"],
        },
    )
    assert conn.errors == []
    pocket_grp = next(g for g in get_device_groups(hass) if g["id"] == "pocket_carry")
    assert pocket_grp["include_interface"] is True
    assert pocket_grp["device_config"]["world_clocks"] == "London|Europe/London"

    # Explicit switch to Custom and invalid option validation on `select.<slug>_device_group`
    await group_sel.async_select_option("Pocket Carry")
    assert hass.states.get(f"select.{slug}_device_group").state == "Pocket Carry"
    await group_sel.async_select_option("Custom")
    assert hass.states.get(f"select.{slug}_device_group").state == "Custom"
    with pytest.raises(HomeAssistantError):
        await group_sel.async_select_option("Nonexistent Group")

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_tools_games_prefs_and_stopwatch_live_device_actions(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify `tools_items`/`games_items` two-way sync + group baseline, stopwatch 1 Hz ticking + `live` payload, and `dismiss_ringing`/`cancel_timer`/`reset_stopwatch` commands."""
    orig_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda _d: orig_sleep(0))

    entry, sys_obj, coord = await setup_latter_hub(
        hass, with_device=True, with_ble_tag=True
    )
    slug = coord.device_slug
    _register_wifi_sensor(hass, coord, "-49")
    ble_coord = next(c for c in sys_obj.coordinators.values() if c.is_ble_tag)
    conn = websocket_api.ActiveConnection()

    # 1) Save `tools_items` & `games_items` via Studio `save_device_config` -> bumps prefs_seq & packs v3 indices 55..56
    seq_before = coord.prefs_seq
    await _call_ws(
        hass,
        conn,
        1,
        "latter/device/command",
        studio_rev=STUDIO_REV,
        subentry_id=coord.subentry_id,
        command="save_device_config",
        payload={
            "config": {
                "tools_items": "dice,flashlight,coin_flip",
                "games_items": "2048,memory",
            }
        },
    )
    assert conn.errors == []
    st_after_save = conn.results[-1][1]
    assert st_after_save["config"]["tools_items"] == "dice,flashlight,coin_flip"
    assert st_after_save["config"]["games_items"] == "2048,memory"
    assert coord.prefs_seq > seq_before
    _eff_seq, prefs_payload = coord.get_device_prefs_payload()
    wire_tokens = prefs_payload["payload"].split("\x1f")
    assert wire_tokens[55] == "dice,flashlight,coin_flip"
    assert wire_tokens[56] == "2048,memory"

    # Reject empty tools_items or games_items
    await _call_ws(
        hass,
        conn,
        2,
        "latter/device/command",
        studio_rev=STUDIO_REV,
        subentry_id=coord.subentry_id,
        command="save_device_config",
        payload={"config": {"tools_items": ""}},
    )
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    # On-device `set_device_prefs` RPC updates `tools_items` and `games_items`
    await async_dispatch_bound_rpc(
        hass,
        coord,
        "set_device_prefs",
        {
            "base_seq": coord.prefs_seq,
            "changes": "\x1e".join(
                ["tools_items=stopwatch,calculator", "games_items=marbles,chomp"]
            ),
        },
    )
    assert coord.tools_items_csv == "stopwatch,calculator"
    assert coord.games_items_csv == "marbles,chomp"

    # Device Group with `include_interface: True` enforces `tools_items` & `games_items`
    await _call_ws(
        hass,
        conn,
        3,
        "latter/system/command",
        studio_rev=STUDIO_REV,
        command="create_device_group",
        payload={
            "name": "Arcade Stations",
            "include_interface": True,
            "source_subentry_id": coord.subentry_id,
            "assign_source": True,
        },
    )
    assert conn.errors == []
    assert coord.device_group == "arcade_stations"
    await _call_ws(
        hass,
        conn,
        4,
        "latter/system/command",
        studio_rev=STUDIO_REV,
        command="update_group_baseline",
        payload={
            "group_id": "arcade_stations",
            "config": {
                "tools_items": "flashlight,dice",
                "games_items": "archery,bricks,2048",
            },
        },
    )
    assert conn.errors == []
    assert coord.tools_items_csv == "flashlight,dice"
    assert coord.games_items_csv == "archery,bricks,2048"
    assert coord.device_group == "arcade_stations"

    # 2) Stopwatch + Timer + Ringing live telemetry & 1 Hz local monotonic elapsed counter
    anchor = 5000.0
    monkeypatch.setattr(time, "monotonic", lambda: anchor)

    await hass.services.async_call(
        "latter",
        "timer_alarm_state",
        {
            "target_device": coord.subentry_id,
            "timer_running": True,
            "timer_paused": False,
            "remaining_sec": 90,
            "ringing": True,
            "stopwatch_running": True,
            "stopwatch_paused": False,
            "stopwatch_elapsed_sec": 15,
        },
        blocking=True,
    )
    assert coord._unsub_timer_tick is not None

    monkeypatch.setattr(time, "monotonic", lambda: anchor + 22.8)
    await _call_ws(
        hass,
        conn,
        5,
        "latter/system/get_state",
        studio_rev=STUDIO_REV,
        subentry_id=coord.subentry_id,
    )
    dev_state = conn.results[-1][1]
    live = dev_state["live"]
    assert live["timer_running"] is True
    assert live["timer_paused"] is False
    assert live["timer_remaining_sec"] == 67
    assert live["stopwatch_running"] is True
    assert live["stopwatch_paused"] is False
    assert live["stopwatch_elapsed_sec"] == 37
    assert live["alarm_ringing"] is True
    # Quick Actions grid stays strictly at the 4 core actions
    assert [a["key"] for a in dev_state["quick_actions"]] == [
        "find_my",
        "trigger_va",
        "activate_screensaver",
        "restart",
    ]

    # BLE tag payload omits display timer/stopwatch/ringing live keys
    await _call_ws(
        hass,
        conn,
        6,
        "latter/system/get_state",
        studio_rev=STUDIO_REV,
        subentry_id=ble_coord.subentry_id,
    )
    ble_live = conn.results[-1][1]["live"]
    for display_live_key in (
        "timer_running",
        "timer_paused",
        "timer_remaining_sec",
        "stopwatch_running",
        "stopwatch_paused",
        "stopwatch_elapsed_sec",
        "alarm_ringing",
    ):
        assert display_live_key not in ble_live

    # Pause stopwatch while timer stops -> 1 Hz tick unsubscribes and paused elapsed stays frozen
    await async_dispatch_bound_rpc(
        hass,
        coord,
        "timer_alarm_state",
        {
            "timer_running": 0,
            "timer_paused": 1,
            "remaining_sec": 67,
            "ringing": 1,
            "stopwatch_running": 0,
            "stopwatch_paused": 1,
            "stopwatch_elapsed_sec": 37,
        },
    )
    assert coord._unsub_timer_tick is None
    monkeypatch.setattr(time, "monotonic", lambda: anchor + 100.0)
    assert coord.current_stopwatch_elapsed_sec == 37
    assert coord.current_timer_remaining_sec == 67

    # Stopwatch running alone keeps 1 Hz `_unsub_timer_tick` active even when countdown timer is idle!
    await async_dispatch_bound_rpc(
        hass,
        coord,
        "timer_alarm_state",
        {
            "timer_running": 0,
            "timer_paused": 1,
            "remaining_sec": 67,
            "ringing": 1,
            "stopwatch_running": 1,
            "stopwatch_paused": 0,
            "stopwatch_elapsed_sec": 37,
        },
    )
    assert coord._unsub_timer_tick is not None

    # 3) Contextual `device_action` commands: `dismiss_ringing`, `cancel_timer`, `reset_stopwatch`
    hass.services.calls.clear()
    await _call_ws(
        hass,
        conn,
        7,
        "latter/device/command",
        studio_rev=STUDIO_REV,
        subentry_id=coord.subentry_id,
        command="device_action",
        payload={"action": "dismiss_ringing"},
    )
    assert conn.errors == []
    assert coord.alarm_ringing is False
    assert conn.results[-1][1]["live"]["alarm_ringing"] is False
    assert hass.states.get(f"binary_sensor.{slug}_alarm_ringing").state == "off"

    await _call_ws(
        hass,
        conn,
        8,
        "latter/device/command",
        studio_rev=STUDIO_REV,
        subentry_id=coord.subentry_id,
        command="device_action",
        payload={"action": "cancel_timer"},
    )
    assert conn.errors == []
    assert coord.timer_running is False
    assert coord.timer_paused is False
    assert coord.current_timer_remaining_sec == 0
    assert conn.results[-1][1]["live"]["timer_remaining_sec"] == 0
    # Stopwatch is still running, so 1 Hz tick remains active until reset_stopwatch!
    assert coord._unsub_timer_tick is not None

    await _call_ws(
        hass,
        conn,
        9,
        "latter/device/command",
        studio_rev=STUDIO_REV,
        subentry_id=coord.subentry_id,
        command="device_action",
        payload={"action": "reset_stopwatch"},
    )
    assert conn.errors == []
    assert coord.stopwatch_running is False
    assert coord.stopwatch_paused is False
    assert coord.current_stopwatch_elapsed_sec == 0
    assert conn.results[-1][1]["live"]["stopwatch_elapsed_sec"] == 0
    assert coord._unsub_timer_tick is None

    sent_cmds = [
        c.data.get("command")
        for c in hass.services.calls
        if c.domain == "esphome" and c.service == f"{slug}_latter_device_command"
    ]
    assert sent_cmds == ["dismiss_ringing", "cancel_timer", "reset_stopwatch"]

    assert await async_unload_entry(hass, entry) is True
