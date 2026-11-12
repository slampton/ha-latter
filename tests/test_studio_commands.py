"""Integration tests for Latter Studio WebSocket API (`studio_rev`, `include_logs`, `ble_survey_delta`, PIN secrecy, groups, backup/restore)."""

from __future__ import annotations

import io
import json
from typing import Any

from homeassistant.components import websocket_api
from PIL import Image
import pytest

from custom_components.latter import async_unload_entry
from custom_components.latter.const import CONF_SECURITY_PIN_HASH
from custom_components.latter.presence import get_ble_fabric
from custom_components.latter.studio.commands import STUDIO_REV
from custom_components.latter.studio.payload import log_studio_event
from custom_components.latter.wallpapers import save_uploaded_wallpaper_bytes


def _make_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (80, 120, 200)).save(buf, format="JPEG", progressive=False)
    return buf.getvalue()


async def _call_ws(
    hass: Any, conn: Any, msg_id: int, ws_type: str, **payload: Any
) -> None:
    handler = hass._ws_commands[ws_type]
    schema = getattr(handler, "_ws_schema", None)
    raw_msg = {"id": msg_id, "type": ws_type, **payload}
    validated = schema(raw_msg) if schema is not None else raw_msg
    await handler(hass, conn, validated)


@pytest.mark.asyncio
async def test_studio_rev_mismatch_on_all_read_and_mutation_endpoints(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify studio_rev mismatch rejects BOTH read (get_state, subscribe) and mutation WS commands."""
    assert STUDIO_REV == 3
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    from homeassistant.helpers import area_registry as ar

    ar.async_get(hass).areas["living_room"] = ar.AreaEntry("living_room", "Living Room")
    conn = websocket_api.ActiveConnection()

    endpoints = [
        ("latter/system/get_state", {"studio_rev": 999}),
        ("latter/system/subscribe", {"studio_rev": 999}),
        ("latter/system/command", {"command": "clear_internal_logs", "studio_rev": 999}),
        ("latter/device/command", {"command": "save_device_config", "subentry_id": coord.subentry_id, "studio_rev": 999}),
        ("latter/system/export", {"studio_rev": 999}),
        ("latter/device/export", {"subentry_id": coord.subentry_id, "studio_rev": 999}),
        ("latter/system/import", {"bundle": {"scope": "system"}, "studio_rev": 999}),
        ("latter/device/import", {"subentry_id": coord.subentry_id, "bundle": {"scope": "device"}, "studio_rev": 999}),
        ("latter/device/reset", {"subentry_id": coord.subentry_id, "studio_rev": 999}),
    ]
    for idx, (ws_type, extra) in enumerate(endpoints, start=1):
        await _call_ws(hass, conn, idx, ws_type, **extra)

    assert conn.results == []
    assert len(conn.errors) == len(endpoints)
    assert all(code == "studio_rev_mismatch" for _id, code, _msg in conn.errors)

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_studio_logs_gating_zero_device_state_and_ble_survey_delta_stream(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify zero-device state signing, include_logs=False/True gating, and live ble_survey_delta WS events."""
    # 1) Zero-device hub get_state signs system wallpaper previews cleanly
    entry0, _sys0, _coord0 = await setup_latter_hub(hass, with_device=False)
    conn0 = websocket_api.ActiveConnection()
    await _call_ws(hass, conn0, 1, "latter/system/get_state", studio_rev=STUDIO_REV)
    assert len(conn0.results) == 1
    st0 = conn0.results[0][1]
    assert st0["studio_rev"] == STUDIO_REV
    assert st0["system_wallpapers"] and "/api/latter/wallpaper/system" in st0["system_wallpapers"][0]["thumb_url"]
    assert await async_unload_entry(hass, entry0) is True

    # 2) include_logs gating & ble_survey_delta live subscription streaming
    hass2 = type(hass)(config_dir=hass.config.config_dir)
    entry, _sys_obj, coord = await setup_latter_hub(hass2, with_device=True)
    log_studio_event(hass2, "INFO", "system", "Test diagnostic log line")

    conn = websocket_api.ActiveConnection()
    await _call_ws(hass2, conn, 10, "latter/system/get_state", include_logs=False, studio_rev=STUDIO_REV)
    res_no_logs = conn.results[-1][1]
    assert res_no_logs.get("internal_logs", []) == []

    await _call_ws(hass2, conn, 11, "latter/system/get_state", include_logs=True, studio_rev=STUDIO_REV)
    res_with_logs = conn.results[-1][1]
    assert len(res_with_logs.get("internal_logs", [])) >= 1

    # Subscribe with survey_subentry_id -> emit_survey_delta pushes ble_survey_delta event!
    await _call_ws(
        hass2,
        conn,
        12,
        "latter/system/subscribe",
        subentry_id=coord.subentry_id,
        survey_subentry_id=coord.subentry_id,
        include_logs=False,
        studio_rev=STUDIO_REV,
    )
    assert 12 in conn.subscriptions
    fabric = get_ble_fabric(hass2)
    assert coord._ble_tracker is not None
    conn.messages.clear()
    fabric.emit_survey_delta(coord._ble_tracker)
    assert any(m["event"].get("type") == "ble_survey_delta" for m in conn.messages)

    # Unsubscribe cleans up listeners
    conn.subscriptions.pop(12)()
    conn.messages.clear()
    fabric.emit_survey_delta(coord._ble_tracker)
    assert conn.messages == []

    assert await async_unload_entry(hass2, entry) is True


@pytest.mark.asyncio
async def test_studio_commands_security_pin_secrecy_groups_and_backup_restore(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise Studio system/device commands, write-only security_pin secrecy, Device Groups, and Export/Import."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    from homeassistant.helpers import area_registry as ar

    ar.async_get(hass).areas["living_room"] = ar.AreaEntry("living_room", "Living Room")
    conn = websocket_api.ActiveConnection()
    msg_seq = 100

    async def _sys_cmd(command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal msg_seq
        msg_seq += 1
        await _call_ws(
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

    async def _dev_cmd(command: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        nonlocal msg_seq
        msg_seq += 1
        await _call_ws(
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

    # 1) Write-only security_pin & security_pin_policy: NEVER leak raw PIN or hash in Studio payload!
    secret_pin = "846291"
    await _dev_cmd(
        "save_device_config",
        {
            "config": {
                "security_pin_policy": "require_pin",
                "dock_apps": "music,alarm,area,remote",
            }
        },
    )
    state_after_pin = await _sys_cmd(
        "set_security_pin",
        {"subentry_id": coord.subentry_id, "pin": secret_pin},
    )
    serialized = json.dumps(state_after_pin)
    assert secret_pin not in serialized
    assert coord.device_data[CONF_SECURITY_PIN_HASH] not in serialized
    assert "security_pin" not in coord.device_data
    assert state_after_pin["config"]["security_pin_policy"] == "require_pin"
    assert state_after_pin["config"]["has_security_pin"] is True
    assert state_after_pin["live"]["has_security_pin"] is True

    # System set_security_pin + rotate_signing_key
    await _sys_cmd("set_security_pin", {"pin": "1357"})
    await _sys_cmd("set_security_pin", {"clear": True})
    await _sys_cmd("rotate_signing_key", {})

    # Clear device PIN via canonical set_security_pin + reset policy to auto
    await _sys_cmd("set_security_pin", {"subentry_id": coord.subentry_id, "clear": True})
    state_cleared = await _dev_cmd(
        "save_device_config",
        {"config": {"security_pin_policy": "auto"}},
    )
    assert state_cleared["config"]["has_security_pin"] is False

    # 2) Quick Action button press ('unknown' stateless HA button) + BLE/System/Wallpapers/Device Groups
    from homeassistant.helpers import entity_registry as er

    ent_reg = er.async_get(hass)
    pressed_entities: list[str] = []

    async def _handle_button_press(call: Any) -> None:
        ent = call.data.get("entity_id")
        if isinstance(ent, str):
            pressed_entities.append(ent)

    hass.services.async_register("button", "press", _handle_button_press)
    for btn_id, btn_name in (
        ("button.pocket_actions_find_my_device", "Actions: Find My Device"),
        ("button.pocket_actions_trigger_voice_assistant", "Actions: Trigger Voice Assistant"),
        ("button.pocket_actions_activate_screensaver", "Actions: Activate Screensaver"),
        ("button.pocket_actions_hibernate_device", "Actions: Hibernate Device"),
        ("button.pocket_actions_restart_device", "Actions: Restart Device"),
    ):
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=btn_id,
                platform="esphome",
                device_id=coord.esphome_device_id,
                original_name=btn_name,
                has_entity_name=True,
            )
        )
        hass.states.async_set(btn_id, "unknown", {"friendly_name": btn_name})

    st_with_actions = await _dev_cmd(
        "esphome_entity_action",
        {"entity_id": "button.pocket_actions_find_my_device", "action": "press"},
    )
    assert pressed_entities == ["button.pocket_actions_find_my_device"]
    actions_sec = next(
        s for s in st_with_actions["esphome"]["sections"] if s["id"] == "actions"
    )
    assert {it["entity_id"] for it in actions_sec["items"]} >= {
        "button.pocket_actions_find_my_device",
        "button.pocket_actions_trigger_voice_assistant",
        "button.pocket_actions_activate_screensaver",
        "button.pocket_actions_hibernate_device",
        "button.pocket_actions_restart_device",
    }

    await _sys_cmd("set_ble_area_offset", {"area_id": "living_room", "offset_db": 4.5})
    await _sys_cmd("set_area_fusion", {"area_id": "living_room", "mode": "weighted", "threshold_pct": 60})
    await _sys_cmd(
        "auto_calibrate_here",
        {"area_id": "living_room", "survey_subentry_id": coord.subentry_id},
    )
    await _sys_cmd("save_system_config", {"config": {"weather_entity": "weather.home"}})
    await _sys_cmd("check_system_updates", {})
    await _sys_cmd("clear_internal_logs", {})

    # Retired base64 WS wallpaper upload commands must be rejected as unknown_command
    msg_seq += 1
    await _call_ws(
        hass,
        conn,
        msg_seq,
        "latter/device/command",
        command="upload_wallpaper",
        subentry_id=coord.subentry_id,
        payload={"filename": "dev_bg.jpg", "data_b64": ""},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "unknown_command"
    conn.errors.clear()

    dev_wp_id, _ = save_uploaded_wallpaper_bytes(hass, coord.device_slug, "dev_bg.jpg", _make_jpeg_bytes())
    assert dev_wp_id.startswith("upload:")
    await _dev_cmd("select_wallpaper", {"source_id": dev_wp_id})
    assert coord.wallpaper_source == dev_wp_id
    await _dev_cmd("toggle_wallpaper_favorite", {"source_id": "preset:forest_mountains"})
    await _dev_cmd("select_wallpaper", {"source_id": "preset:forest_mountains"})
    await _dev_cmd("delete_wallpaper", {"source_id": dev_wp_id})

    # Wallpaper rotation state machine: Off -> bulk star -> enable rotation seeds active photo -> Turn Off resets both
    off_state = await _dev_cmd("select_wallpaper", {"source_id": ""})
    assert coord.wallpaper_source == ""
    assert coord.wallpaper_cycle_minutes == 0
    assert coord._unsub_wallpaper_timer is None
    assert not any(w["active"] for w in off_state["wallpapers"])

    starred_state = await _dev_cmd(
        "toggle_wallpaper_favorite",
        {"source_ids": ["preset:ocean_waves", "preset:mars_crater"]},
    )
    assert coord.wallpaper_favorites == ["preset:ocean_waves", "preset:mars_crater"]
    assert coord.wallpaper_source == ""
    assert [w["id"] for w in starred_state["wallpapers"] if w["favorite"]] == [
        "preset:ocean_waves",
        "preset:mars_crater",
    ]

    rot_state = await _dev_cmd(
        "save_device_config",
        {"config": {"wallpaper_cycle_minutes": 5}},
    )
    assert coord.wallpaper_cycle_minutes == 5
    assert coord.wallpaper_source == "preset:ocean_waves"
    assert coord._unsub_wallpaper_timer is not None
    assert [w["id"] for w in rot_state["wallpapers"] if w["active"]] == [
        "preset:ocean_waves"
    ]

    # Selecting an unstarred photo explicitly pauses starred rotation so that photo stays displayed
    unstarred_state = await _dev_cmd(
        "select_wallpaper",
        {"source_id": "preset:sahara_dunes"},
    )
    assert coord.wallpaper_source == "preset:sahara_dunes"
    assert coord.wallpaper_cycle_minutes == 0
    assert coord._unsub_wallpaper_timer is None
    assert unstarred_state["config"]["wallpaper_cycle_minutes"] == 0

    # Enabling rotation with zero starred photos rotates through all gallery items starting at first preset
    await _dev_cmd("toggle_wallpaper_favorite", {"source_ids": []})
    await _dev_cmd("select_wallpaper", {"source_id": ""})
    all_rot_state = await _dev_cmd(
        "save_device_config",
        {"config": {"wallpaper_cycle_minutes": 15}},
    )
    assert coord.wallpaper_favorites == []
    assert coord.wallpaper_cycle_minutes == 15
    assert coord.wallpaper_source == "preset:forest_mountains"
    assert coord._unsub_wallpaper_timer is not None
    assert [w["id"] for w in all_rot_state["wallpapers"] if w["active"]] == [
        "preset:forest_mountains"
    ]

    # Turn Off Wallpaper resets both active source and rotation interval
    final_off = await _dev_cmd("select_wallpaper", {"source_id": ""})
    assert coord.wallpaper_source == ""
    assert coord.wallpaper_cycle_minutes == 0
    assert coord._unsub_wallpaper_timer is None
    assert final_off["config"]["wallpaper_cycle_minutes"] == 0

    # Device Groups lifecycle: create -> seed -> set_group_device_setting -> sync -> delete
    await _sys_cmd("create_device_group", {"name": "Guest Suites", "description": "Guest displays"})
    await _sys_cmd(
        "seed_group_baseline",
        {"group_id": "guest_suites", "subentry_id": coord.subentry_id},
    )
    await _sys_cmd(
        "set_group_device_setting",
        {"group_id": "guest_suites", "config": {"default_page_size": 4}},
    )
    await _sys_cmd(
        "sync_device_group",
        {"group_id": "guest_suites", "subentry_id": coord.subentry_id},
    )
    await _sys_cmd("delete_device_group", {"group_id": "guest_suites"})

    # Wrong scope error check ('save_device_config' sent to system scope)
    msg_seq += 1
    await _call_ws(
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
    await _call_ws(hass, conn, msg_seq, "latter/system/export", studio_rev=STUDIO_REV)
    sys_bundle = conn.results[-1][1]["bundle"]
    assert sys_bundle["scope"] == "system"
    assert secret_pin not in json.dumps(sys_bundle)

    msg_seq += 1
    await _call_ws(
        hass, conn, msg_seq, "latter/system/import", bundle=sys_bundle, studio_rev=STUDIO_REV
    )
    assert not conn.errors

    msg_seq += 1
    await _call_ws(
        hass,
        conn,
        msg_seq,
        "latter/device/export",
        subentry_id=coord.subentry_id,
        studio_rev=STUDIO_REV,
    )
    dev_bundle = conn.results[-1][1]["bundle"]
    assert dev_bundle["scope"] == "device"

    msg_seq += 1
    await _call_ws(
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
    await _call_ws(
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

    assert await async_unload_entry(hass, entry) is True
