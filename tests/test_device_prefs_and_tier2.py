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
    compute_device_group_sync_status,
    get_device_groups,
)
from custom_components.latter.services import async_dispatch_bound_rpc
from custom_components.latter.studio.commands import STUDIO_REV


def _register_wifi_sensor(hass: Any, coord: Any, state: str = "-52") -> str:
    ent_reg = er.async_get(hass)
    eid = f"sensor.{coord.device_slug}_wifi_signal"
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
        contract=3,
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
        contract=3,
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
        contract=3,
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
    """Verify `set_device_prefs` bound RPC updates subentry, cascades PowerProfile, and updates `sensor.<slug>_device_prefs`."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    _register_wifi_sensor(hass, coord, "-50")

    await async_dispatch_bound_rpc(
        hass,
        coord,
        "set_device_prefs",
        {
            "base_seq": 1,
            "changes": "\x1e".join(["power_profile=Tabletop Dock", "alert_volume=70"]),
        },
    )
    assert coord.prefs_seq >= 2
    assert coord.get_device_pref("power_profile") == "Tabletop Dock"
    assert coord.get_device_pref("tap_to_wake") == "Docked Only"
    assert coord.get_device_pref("pickup_to_wake") == "Disabled"
    assert coord.get_device_pref("alert_volume") == 70

    # Diverging a subkey flips `power_profile` to `Custom`
    await async_dispatch_bound_rpc(
        hass,
        coord,
        "set_device_prefs",
        {"base_seq": coord.prefs_seq, "changes": "tap_to_wake=Disabled"},
    )
    assert coord.get_device_pref("tap_to_wake") == "Disabled"
    assert coord.get_device_pref("power_profile") == "Custom"

    prefs_st = hass.states.get(f"sensor.{coord.device_slug}_device_prefs")
    assert prefs_st is not None
    assert int(prefs_st.state) == coord.prefs_seq
    assert prefs_st.attributes["rev"] >= 1

    _seq, payload_attrs = coord.get_device_prefs_payload()
    assert payload_attrs["power_profile"] == "Custom"
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
    await coord.async_handle_device_hello(3, "fresh_boot_99", manifest_raw)
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
    assert hass.states.get("select.keys_tag_wake_word_mode") is None
    assert hass.states.get("number.keys_tag_alert_volume") is None
    assert hass.states.get("button.keys_tag_find_my_device") is None

    # Sleep-safe select & number succeed while ESPHome Wi-Fi is `unavailable`
    power_sel = _find_entity(hass, "select", f"select.{slug}_power_profile")
    ww_sel = _find_entity(hass, "select", f"select.{slug}_wake_word_mode")
    vol_num = _find_entity(hass, "number", f"number.{slug}_alert_volume")
    find_btn = _find_entity(hass, "button", f"button.{slug}_find_my_device")
    ss_btn = _find_entity(hass, "button", f"button.{slug}_activate_screensaver")

    await power_sel.async_select_option("Wearable Watch")
    assert hass.states.get(f"select.{slug}_power_profile").state == "Wearable Watch"
    assert coord.get_device_pref("battery_screen_timeout") == "15s"

    await ww_sel.async_select_option("Always On")
    assert hass.states.get(f"select.{slug}_wake_word_mode").state == "Always On"
    assert hass.states.get(f"select.{slug}_power_profile").state == "Custom"

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

    coord.update_device_config({**coord.device_data, "device_group": "handhelds"})
    await _call_ws(
        hass,
        conn,
        2,
        "latter/system/command",
        studio_rev=STUDIO_REV,
        command="sync_device_group",
        payload={"group_id": "handhelds"},
    )
    assert conn.errors == []
    assert compute_device_group_sync_status(hass, coord) == "in_sync"

    # Update a group preference while Device is offline -> pushes into subentry immediately
    await _call_ws(
        hass,
        conn,
        3,
        "latter/system/command",
        studio_rev=STUDIO_REV,
        command="set_group_device_setting",
        payload={"group_id": "handhelds", "config": {"alert_volume": 60}},
    )
    assert conn.errors == []
    assert coord.get_device_pref("alert_volume") == 60
    assert compute_device_group_sync_status(hass, coord) == "in_sync"

    # Customize one preference on the sleeping Device -> group status reports `customized`
    await coord.async_update_device_prefs({"alert_volume": 95})
    assert compute_device_group_sync_status(hass, coord) == "customized"

    # Seed group baseline from sleeping Device -> captures all subentry preferences cleanly
    await _call_ws(
        hass,
        conn,
        4,
        "latter/system/command",
        studio_rev=STUDIO_REV,
        command="seed_group_baseline",
        payload={"group_id": "handhelds", "subentry_id": coord.subentry_id},
    )
    assert conn.errors == []
    groups = get_device_groups(hass)
    handhelds = next(g for g in groups if g["id"] == "handhelds")
    assert handhelds["device_config"]["alert_volume"] == 95
    assert compute_device_group_sync_status(hass, coord) == "in_sync"

    assert await async_unload_entry(hass, entry) is True
