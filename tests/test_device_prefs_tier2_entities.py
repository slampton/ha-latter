"""Integration tests for Tier 2 sleep-safe/online entities, event-driven timer/stopwatch telemetry, and contextual device actions."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.latter.const import STUDIO_REV
from custom_components.latter.services.rpc_dispatcher import async_dispatch_bound_rpc
from tests.helpers import (
    call_ws,
    find_entity_instance,
    get_service_calls,
    make_ws_connection,
    register_entity,
)


def _register_wifi_sensor(hass: Any, coord: Any, state: str = "-52") -> str:
    eid = f"sensor.{coord.device_slug}_wi_fi_signal"
    register_entity(
        hass,
        eid,
        platform="esphome",
        device_id=coord.esphome_device_id,
        config_entry_id=f"esp_entry_{coord.device_slug}",
        original_name="Wi-Fi Signal",
    )
    hass.states.async_set(eid, state)
    return eid


async def test_timer_alarm_state_event_driven_and_boot_reset(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify `timer_alarm_state` RPC drives Tier 2 timer/alarm entities without polling and resets on cold boot."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    slug = coord.device_slug

    assert hass.states.get(f"binary_sensor.{slug}_timer_active").state == "off"
    assert hass.states.get(f"binary_sensor.{slug}_alarm_ringing").state == "off"
    assert int(hass.states.get(f"sensor.{slug}_timer_remaining").state) == 0

    await async_dispatch_bound_rpc(
        hass,
        coord,
        "timer_alarm_state",
        {"timer_running": 1, "timer_paused": 0, "remaining_sec": 120, "ringing": 0},
    )
    assert hass.states.get(f"binary_sensor.{slug}_timer_active").state == "on"
    assert int(hass.states.get(f"sensor.{slug}_timer_remaining").state) == 120

    # Simulate 35s elapsed via per-instance anchor -> computed locally with zero Wi-Fi polling
    coord._timer_anchor_mono = time.monotonic() - 35.0
    coord.async_update_listeners()
    assert int(hass.states.get(f"sensor.{slug}_timer_remaining").state) == 85

    # Pause freezes countdown, ringing sets alarm_ringing on
    await async_dispatch_bound_rpc(
        hass,
        coord,
        "timer_alarm_state",
        {"timer_running": 0, "timer_paused": 1, "remaining_sec": 85, "ringing": 1},
    )
    coord._timer_anchor_mono = time.monotonic() - 60.0
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

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_tier2_select_number_sleep_safe_and_buttons_online_vs_offline(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify Tier 2 `select`/`number` persist while Device is sleeping, while action `button`s require online Wi-Fi."""
    entry, _sys_obj, coord = await setup_latter_hub(
        hass, with_device=True, with_ble_tag=True
    )
    slug = coord.device_slug
    wifi_eid = _register_wifi_sensor(hass, coord, "unavailable")
    hass.states.async_set(f"sensor.{slug}_system_rpc_outbox", "unavailable")

    # BLE tags do not create Tier 2 display/audio controls
    assert hass.states.get("select.keys_tag_device_group") is None
    assert hass.states.get("select.keys_tag_wake_word_mode") is None
    assert hass.states.get("number.keys_tag_alert_volume") is None
    assert hass.states.get("button.keys_tag_find_my_device") is None
    assert hass.states.get("light.keys_tag_screen") is None
    assert hass.states.get("switch.keys_tag_screensaver") is None
    assert hass.states.get("switch.keys_tag_do_not_disturb") is None

    # Sleep-safe select, number & DND switch succeed while ESPHome Wi-Fi is `unavailable`
    assert hass.states.get(f"select.{slug}_power_profile") is None
    assert hass.states.get(f"button.{slug}_activate_screensaver") is None
    group_sel = find_entity_instance(hass, "select", f"select.{slug}_device_group")
    ww_sel = find_entity_instance(hass, "select", f"select.{slug}_wake_word_mode")
    vol_num = find_entity_instance(hass, "number", f"number.{slug}_alert_volume")
    find_btn = find_entity_instance(hass, "button", f"button.{slug}_find_my_device")
    dismiss_btn = find_entity_instance(hass, "button", f"button.{slug}_dismiss_alert")
    screen_light = find_entity_instance(hass, "light", f"light.{slug}_screen")
    ss_sw = find_entity_instance(hass, "switch", f"switch.{slug}_screensaver")
    dnd_sw = find_entity_instance(hass, "switch", f"switch.{slug}_do_not_disturb")

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

    assert dnd_sw.available is True
    await dnd_sw.async_turn_on()
    assert coord.do_not_disturb is True
    assert hass.states.get(f"switch.{slug}_do_not_disturb").state == "on"
    await dnd_sw.async_turn_off()
    assert coord.do_not_disturb is False

    # Radio-dependent controls report unavailable while sleeping; Find My raises HomeAssistantError
    assert find_btn.available is False
    assert dismiss_btn.available is False
    assert screen_light.available is False
    assert ss_sw.available is False
    with pytest.raises(HomeAssistantError):
        await find_btn.async_press()

    # Bring Device online -> buttons, screen light, and screensaver switch dispatch `esphome.<slug>_latter_device_command`
    hass.states.async_set(wifi_eid, "-49")
    hass.states.async_set(f"sensor.{slug}_system_rpc_outbox", "")
    coord.async_update_listeners()
    assert find_btn.available is True
    assert dismiss_btn.available is True
    assert screen_light.available is True
    assert ss_sw.available is True
    calls = get_service_calls(hass)
    calls.clear()

    await find_btn.async_press()
    await dismiss_btn.async_press()
    await ss_sw.async_turn_on()
    assert ss_sw.is_on is True
    await ss_sw.async_turn_off()
    assert ss_sw.is_on is False
    await screen_light.async_turn_on(brightness=128)
    assert screen_light.is_on is True
    await screen_light.async_turn_off()
    assert screen_light.is_on is False
    cmds = [
        c.data.get("command")
        for c in calls
        if c.domain == "esphome" and c.service == f"{slug}_latter_device_command"
    ]
    assert cmds == [
        "find_my",
        "dismiss_ringing",
        "activate_screensaver",
        "deactivate_screensaver",
        "set_screen_bri:50",
        "screen_off",
    ]

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_tools_games_prefs_and_stopwatch_live_device_actions(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify `tools_items`/`games_items` two-way sync + group baseline, stopwatch 1 Hz ticking + `live` payload, and `dismiss_ringing`/`cancel_timer`/`reset_stopwatch` commands."""
    entry, sys_obj, coord = await setup_latter_hub(
        hass, with_device=True, with_ble_tag=True
    )
    slug = coord.device_slug
    _register_wifi_sensor(hass, coord, "-49")
    ble_coord = next(c for c in sys_obj.coordinators.values() if c.is_ble_tag)
    conn = make_ws_connection(hass)

    # 1) Save `tools_items` & `games_items` via Studio `save_device_config` -> bumps prefs_seq & packs v3 indices 52..53
    seq_before = coord.prefs_seq
    await call_ws(
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
    assert wire_tokens[52] == "dice,flashlight,coin_flip"
    assert wire_tokens[53] == "2048,memory"

    # Reject empty tools_items or games_items
    await call_ws(
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
    await call_ws(
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
    await call_ws(
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
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "timer_alarm_state",
        {
            "timer_running": True,
            "timer_paused": False,
            "remaining_sec": 90,
            "ringing": True,
            "stopwatch_running": True,
            "stopwatch_paused": False,
            "stopwatch_elapsed_sec": 15,
        },
    )
    assert coord._unsub_timer_tick is not None

    shifted_anchor = time.monotonic() - 22.8
    coord._timer_anchor_mono = shifted_anchor
    coord._stopwatch_anchor_mono = shifted_anchor
    await call_ws(
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
    await call_ws(
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
    paused_anchor = time.monotonic() - 100.0
    coord._timer_anchor_mono = paused_anchor
    coord._stopwatch_anchor_mono = paused_anchor
    assert coord.current_stopwatch_elapsed_sec == 37
    assert coord.current_timer_remaining_sec == 67

    # Stopwatch running alone uses `stopwatch_started_at` UTC ISO anchor for local Studio ticking without a 1 Hz HA timer tick (`D-065`)!
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
    assert coord._unsub_timer_tick is None
    assert coord.stopwatch_started_at_utc != ""
    assert coord.timer_ends_at_utc == ""

    # 3) Contextual `device_action` commands: `dismiss_ringing`, `cancel_timer`, `reset_stopwatch`
    calls = get_service_calls(hass)
    calls.clear()
    await call_ws(
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

    await call_ws(
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
    assert coord._unsub_timer_tick is None

    await call_ws(
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
    assert conn.results[-1][1]["live"]["stopwatch_started_at"] == ""
    assert coord._unsub_timer_tick is None

    sent_cmds = [
        c.data.get("command")
        for c in calls
        if c.domain == "esphome" and c.service == f"{slug}_latter_device_command"
    ]
    assert sent_cmds == ["dismiss_ringing", "cancel_timer", "reset_stopwatch"]

    assert await hass.config_entries.async_unload(entry.entry_id) is True
