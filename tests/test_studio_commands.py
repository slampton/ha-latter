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
    assert STUDIO_REV == 27
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
    delta_events = [m["event"] for m in conn.messages if m["event"].get("type") == "ble_survey_delta"]
    assert len(delta_events) >= 1
    assert "ble_survey_rows" in delta_events[-1]
    assert "ble_area_signatures" in delta_events[-1]

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
                "dock_items": [
                    {"kind": "route", "target": "app:pinned"},
                    {"kind": "route", "target": "app:music"},
                    {"kind": "entity", "target": "scene.movie_night", "action": "turn_on", "label": "Movie", "confirm": True},
                ],
                "pinned_items": [
                    {"kind": "route", "target": "weather:moon", "label": "Moon"},
                    {"kind": "entity", "target": "script.baby_help", "action": "turn_on", "label": "Baby Help", "confirm": False},
                ],
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
    assert len(state_after_pin["config"]["dock_items"]) == 3
    assert len(state_after_pin["config"]["pinned_items"]) == 2
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

    import time

    assert coord._ble_tracker is not None
    coord._ble_tracker._ingest_proxy_observation(
        "AA:BB:CC:00:00:11", -56, time.monotonic(), "Living Room Proxy"
    )
    st_offset = await _sys_cmd(
        "set_ble_scanner_offset",
        {"scanner_source": "aa:bb:cc:00:00:11", "offset_db": 4.5},
    )
    assert any(
        r["scanner_source"] == "AA:BB:CC:00:00:11" and r["offset_db"] == 4.5
        for d in st_offset["system_devices"]
        if d["subentry_id"] == coord.subentry_id
        for r in d["ble_survey_rows"]
    )
    await _sys_cmd(
        "set_ble_scanner_offset",
        {"scanner_source": "AA:BB:CC:00:00:11", "offset_db": 0.0},
    )
    await _sys_cmd("set_area_fusion", {"area_id": "living_room", "mode": "weighted", "threshold_pct": 60})
    st_sig = await _sys_cmd(
        "capture_ble_area_signature",
        {"area_id": "living_room", "survey_subentry_id": coord.subentry_id},
    )
    lr_sig = next(
        s for s in st_sig["ble_area_signatures"] if s["area_id"] == "living_room"
    )
    assert lr_sig["has_signature"] is True
    assert lr_sig["scanner_count"] >= 1
    st_sig_cleared = await _sys_cmd(
        "clear_ble_area_signature",
        {"area_id": "living_room"},
    )
    lr_sig_after = next(
        s for s in st_sig_cleared["ble_area_signatures"] if s["area_id"] == "living_room"
    )
    assert lr_sig_after["has_signature"] is False
    st_spatial = await _sys_cmd(
        "save_system_config",
        {
            "config": {
                "weather_entity": "weather.home",
                "ble_attenuation": 2.6,
                "ble_max_radius_m": 14.5,
                "ble_max_velocity_mps": 4.0,
                "ble_away_timeout_s": 240,
            }
        },
    )
    assert st_spatial["system_config"]["ble_attenuation"] == 2.6
    assert st_spatial["system_config"]["ble_max_radius_m"] == 14.5
    assert st_spatial["system_config"]["ble_max_velocity_mps"] == 4.0
    assert st_spatial["system_config"]["ble_away_timeout_s"] == 240
    st_ref = await _dev_cmd(
        "save_device_config",
        {"config": {"ble_ref_power": -52}},
    )
    assert st_ref["config"]["ble_ref_power"] == -52
    assert st_ref["live"]["ble_detected_ref_power"] == -52
    st_ref_auto = await _dev_cmd(
        "save_device_config",
        {"config": {"ble_ref_power": None}},
    )
    assert st_ref_auto["config"]["ble_ref_power"] is None
    await _sys_cmd(
        "save_system_config",
        {
            "config": {
                "remote_groups": [
                    {"id": "living_tv", "name": "Living Area TV", "area_id": "living_room", "remotes": []}
                ]
            }
        },
    )
    rg_saved = await _dev_cmd(
        "save_device_config",
        {"config": {"device_remote_group": "group:living_tv"}},
    )
    assert coord.device_remote_group == "group:living_tv"
    assert rg_saved["config"]["device_remote_group"] == "group:living_tv"

    # Unknown remote group in save_device_config and retired set_device_remote_group must fail
    msg_seq += 1
    await _call_ws(
        hass,
        conn,
        msg_seq,
        "latter/device/command",
        command="save_device_config",
        subentry_id=coord.subentry_id,
        payload={"config": {"device_remote_group": "group:missing"}},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "not_found"
    conn.errors.clear()

    msg_seq += 1
    await _call_ws(
        hass,
        conn,
        msg_seq,
        "latter/system/command",
        command="set_device_remote_group",
        payload={"subentry_id": coord.subentry_id, "device_remote_group": "all"},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "unknown_command"
    conn.errors.clear()

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

    # Device Groups lifecycle: create -> update_group_baseline -> apply_batch_device_setting -> Save Custom Group -> delete
    await _sys_cmd("create_device_group", {"name": "Guest Suites", "description": "Guest displays"})
    await _dev_cmd("save_device_config", {"config": {"device_group": "guest_suites"}})
    assert coord.device_group == "guest_suites"
    await _sys_cmd(
        "update_group_baseline",
        {"group_id": "guest_suites", "source_subentry_id": coord.subentry_id},
    )
    assert coord.device_group == "guest_suites"
    baseline_state = await _sys_cmd(
        "update_group_baseline",
        {"group_id": "guest_suites", "config": {"alert_volume": 65, "area_handoff": True}},
    )
    assert coord.device_group == "guest_suites"
    sys_ctrl_by_pref = {
        c["pref_key"]: c for c in baseline_state["system_controls"] if c.get("pref_key")
    }
    for op_key in (
        "native_ble_tracking",
        "ble_auto_switch",
        "sync_device_area",
        "area_handoff",
        "tools_items",
        "games_items",
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
    vip_grp = next(g for g in saved_grp_state["device_groups"] if g["id"] == "vip_suites")
    assert vip_grp["device_config"]["alert_volume"] == 40

    # Built-in groups cannot be deleted; deleting custom group resets members to 'custom'
    msg_seq += 1
    await _call_ws(
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
    assert dev_bundle["device"]["device_config"]["tools_items"] == "flashlight,calculator,dice"
    assert dev_bundle["device"]["device_config"]["games_items"] == "2048,chomp"

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


@pytest.mark.asyncio
async def test_discovered_latter_devices_and_add_latter_device_command(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any
) -> None:
    """Verify unbound ESPHome Latter discovery in Studio payload and one-click `add_latter_device` validation."""
    import sys

    from homeassistant.helpers import device_registry as dr

    entry, _sys_obj, coord = await setup_latter_hub(hass)
    # 1) Seed an unbound Latter ESPHome display + a non-Latter ESPHome plug
    unbound_dev, _mac = make_esphome_device(
        hass,
        slug="kitchen_panel",
        mac="aa:bb:cc:dd:ee:09",
        name="Kitchen Panel",
        area_id="kitchen",
        stationary=1,
        w=480,
        h=480,
        shape="square",
    )
    plain_esp_entry = hass.config_entries.add_entry(
        sys.modules["homeassistant.config_entries"].ConfigEntry(
            entry_id="esp_entry_plain_plug",
            domain="esphome",
            title="Plain Plug",
            data={"device_name": "plain_plug"},
        )
    )
    plain_dev = dr.async_get(hass).async_get_or_create(
        config_entry_id=plain_esp_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:99")},
        identifiers={("esphome", "aa:bb:cc:dd:ee:99")},
        name="Plain Plug",
        manufacturer="espressif",
        model="smart-plug",
    )

    conn = websocket_api.ActiveConnection()
    await _call_ws(hass, conn, 1, "latter/system/get_state", studio_rev=STUDIO_REV)
    st = conn.results[-1][1]
    discovered = st["discovered_latter_devices"]
    assert len(discovered) == 1
    assert discovered[0] == {
        "esphome_device_id": unbound_dev.id,
        "node_name": "kitchen_panel",
        "title": "Kitchen Panel",
        "model_label": "kitchen_panel-board (480x480)",
        "area_name": "Kitchen",
        "default_group": "wall_panels",
    }

    # 2) Validation checks: missing id, non-Latter ESPHome device, already-managed device, unknown group, unknown person
    bad_cases = [
        ({}, "invalid_format"),
        ({"esphome_device_id": plain_dev.id}, "not_latter_device"),
        ({"esphome_device_id": coord.esphome_device_id}, "already_configured"),
        ({"esphome_device_id": unbound_dev.id, "device_group": "bogus_grp"}, "not_found"),
        ({"esphome_device_id": unbound_dev.id, "assigned_person": "person.nobody"}, "not_found"),
    ]
    for idx, (bad_payload, expected_code) in enumerate(bad_cases, start=10):
        await _call_ws(
            hass,
            conn,
            idx,
            "latter/system/command",
            command="add_latter_device",
            payload=bad_payload,
            studio_rev=STUDIO_REV,
        )
        assert conn.errors[-1][1] == expected_code
        conn.errors.clear()

    # 3) Valid one-click Studio adoption dispatches subentries.async_init for SUBENTRY_DEVICE
    from types import SimpleNamespace

    recorded_inits: list[tuple[Any, Any, Any]] = []
    orig_subentries = getattr(hass.config_entries, "subentries", None)
    orig_init = getattr(orig_subentries, "async_init", None)

    async def _spy_subentry_init(
        handler: Any, *, context: Any = None, data: Any = None
    ) -> Any:
        recorded_inits.append((handler, context, data))
        if callable(orig_init):
            return await orig_init(handler, context=context, data=data)
        return {"type": "create_entry"}

    if orig_subentries is not None:
        orig_subentries.async_init = _spy_subentry_init
    else:
        hass.config_entries.subentries = SimpleNamespace(async_init=_spy_subentry_init)
    await _call_ws(
        hass,
        conn,
        30,
        "latter/system/command",
        command="add_latter_device",
        payload={
            "esphome_device_id": unbound_dev.id,
            "device_group": "auto",
            "assigned_person": "person.sean",
        },
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert len(recorded_inits) == 1
    assert recorded_inits[0][0] == (entry.entry_id, "device")
    assert recorded_inits[0][2] == {
        "esphome_device_id": unbound_dev.id,
        "device_group": "auto",
        "assigned_person": "person.sean",
    }

    assert await async_unload_entry(hass, entry) is True
