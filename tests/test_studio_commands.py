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
from custom_components.latter.wallpapers import (
    DAY_NIGHT_SKY_NATIVE_URL,
    DAY_NIGHT_SKY_PRESET_ID,
    save_uploaded_photo_bytes,
)


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
    """Verify mandatory studio_rev=40 schema validation and studio_rev_mismatch on all 9 WS endpoints."""
    import voluptuous as vol

    assert STUDIO_REV == 40
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
        # Missing mandatory `studio_rev` must be rejected by Voluptuous schema
        without_rev = {k: v for k, v in extra.items() if k != "studio_rev"}
        with pytest.raises(vol.Invalid):
            await _call_ws(hass, conn, idx + 100, ws_type, **without_rev)
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
                    {"kind": "route", "target": "music:lyrics"},
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
    assert len(state_after_pin["config"]["pinned_items"]) == 3
    for retired_music_key in ("show_speaker_shortcut", "show_library_shortcut"):
        assert retired_music_key not in state_after_pin["config"]
        msg_seq += 1
        await _call_ws(
            hass,
            conn,
            msg_seq,
            "latter/device/command",
            command="save_device_config",
            subentry_id=coord.subentry_id,
            payload={"config": {retired_music_key: True}},
            studio_rev=STUDIO_REV,
        )
        assert conn.errors[-1][1] == "invalid_format"
        conn.errors.clear()
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

    # Retired wallpaper WS commands must be rejected as unknown_command
    for retired_scope, retired_cmd in (
        ("device", "upload_wallpaper"),
        ("device", "select_wallpaper"),
        ("device", "toggle_wallpaper_favorite"),
        ("system", "delete_wallpaper"),
    ):
        msg_seq += 1
        await _call_ws(
            hass,
            conn,
            msg_seq,
            f"latter/{retired_scope}/command",
            command=retired_cmd,
            **({"subentry_id": coord.subentry_id} if retired_scope == "device" else {}),
            payload={},
            studio_rev=STUDIO_REV,
        )
        assert conn.errors[-1][1] == "unknown_command"
        conn.errors.clear()

    # Photo Library Collections + Metadata + Bulk + Device Photo Pool (`STUDIO_REV = 39`)
    col_created = await _sys_cmd("create_photo_collection", {"name": "Family"})
    col_id = col_created["collection"]["id"]
    assert any(c["id"] == col_id and c["name"] == "Family" for c in col_created["photo_collections"])
    col_renamed = await _sys_cmd(
        "rename_photo_collection", {"collection_id": col_id, "name": "Favorites"}
    )
    assert col_renamed["collection"]["name"] == "Favorites"

    dev_photo_rec = save_uploaded_photo_bytes(
        hass, "dev_bg.jpg", _make_jpeg_bytes(), collection_id=col_id
    )
    dev_wp_id = dev_photo_rec["id"]
    assert dev_wp_id.startswith("photo:")

    upd_meta = await _sys_cmd(
        "update_photo_metadata",
        {
            "photo_id": dev_wp_id,
            "name": "Living Wall",
            "crop": {"x": 0.4, "y": 0.6, "zoom": 1.4},
            "collections": [col_id],
        },
    )
    assert upd_meta["photo"]["name"] == "Living Wall"
    assert upd_meta["photo"]["crop"] == {"x": 0.4, "y": 0.6, "zoom": 1.4}

    # Select single uploaded photo on Device wallpaper pool
    await _dev_cmd(
        "set_device_photo_pool",
        {"target": "wallpaper", "mode": "single", "source_id": dev_wp_id},
    )
    assert coord.wallpaper_mode == "single"
    assert coord.wallpaper_source == dev_wp_id
    assert "mode=wallpaper" in coord.build_wallpaper_url()

    # Select Day & Night Sky -> native sentinel `latter://day_night_sky` pushed in `area_context`
    await _dev_cmd(
        "set_device_photo_pool",
        {
            "target": "wallpaper",
            "mode": "single",
            "source_id": DAY_NIGHT_SKY_PRESET_ID,
        },
    )
    assert coord.build_wallpaper_url() == DAY_NIGHT_SKY_NATIVE_URL
    _, area_attrs = coord.get_area_context_payload()
    assert area_attrs["wallpaper_url"] == DAY_NIGHT_SKY_NATIVE_URL
    assert area_attrs["screensaver_photo_url"] == ""

    # Screensaver Photo Frame pool + area_context field 41 (`screensaver_photo_url`)
    await _dev_cmd(
        "save_device_config",
        {
            "config": {
                "screensaver_mode": "Always",
                "screensaver_style": "Photo Frame",
                "screensaver_photo_clock": True,
                "weather_app_background": False,
            }
        },
    )
    ss_pool_state = await _dev_cmd(
        "set_device_photo_pool",
        {
            "target": "screensaver",
            "mode": "custom",
            "photo_ids": ["preset:ocean_waves", dev_wp_id],
            "cycle_minutes": 5,
            "shuffle": True,
        },
    )
    assert coord.screensaver_photo_mode == "custom"
    assert coord.screensaver_shuffle is True
    assert coord.screensaver_cycle_minutes == 5
    assert coord._unsub_screensaver_timer is not None
    assert ss_pool_state["live"]["screensaver_pool_count"] == 2
    _, area_attrs_ss = coord.get_area_context_payload()
    assert "mode=screensaver" in area_attrs_ss["screensaver_photo_url"]
    assert area_attrs_ss["payload"].split("\x1f")[41] == area_attrs_ss["screensaver_photo_url"]

    # Dynamic preset rejected on screensaver pool
    msg_seq += 1
    await _call_ws(
        hass,
        conn,
        msg_seq,
        "latter/device/command",
        command="set_device_photo_pool",
        subentry_id=coord.subentry_id,
        payload={
            "target": "screensaver",
            "mode": "single",
            "source_id": DAY_NIGHT_SKY_PRESET_ID,
        },
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "not_allowed"
    conn.errors.clear()

    # `delete_photo` is canonical on System scope; calling it on Device scope fails with `wrong_scope`
    msg_seq += 1
    await _call_ws(
        hass,
        conn,
        msg_seq,
        "latter/device/command",
        command="delete_photo",
        subentry_id=coord.subentry_id,
        payload={"photo_id": dev_wp_id},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "wrong_scope"
    conn.errors.clear()

    # Deleting `dev_wp_id` prunes it cleanly from the Device's screensaver custom pool
    await _sys_cmd("delete_photo", {"photo_id": dev_wp_id})
    assert dev_wp_id not in coord.screensaver_photo_ids
    assert coord.screensaver_photo_ids == ["preset:ocean_waves"]

    # Wallpaper pool rotation state machine: custom -> collection -> delete collection prunes -> off
    rot_state = await _dev_cmd(
        "set_device_photo_pool",
        {
            "target": "wallpaper",
            "mode": "custom",
            "photo_ids": ["preset:ocean_waves", "preset:mars_crater"],
            "cycle_minutes": 5,
        },
    )
    assert coord.wallpaper_cycle_minutes == 5
    assert coord.wallpaper_source == "preset:ocean_waves"
    assert coord._unsub_wallpaper_timer is not None
    assert rot_state["live"]["wallpaper_pool_count"] == 2

    await _sys_cmd(
        "bulk_update_photos",
        {"photo_ids": ["preset:forest_mountains", "preset:wheat_field"], "add_collection": col_id},
    )
    await _dev_cmd(
        "set_device_photo_pool",
        {
            "target": "wallpaper",
            "mode": "collection",
            "collection_id": col_id,
            "cycle_minutes": 15,
        },
    )
    assert coord.wallpaper_mode == "collection"
    assert coord.wallpaper_collection == col_id
    assert coord.wallpaper_source == "preset:forest_mountains"

    # Deleting the active collection cleanly resets wallpaper pool to off
    await _sys_cmd("delete_photo_collection", {"collection_id": col_id})
    assert coord.wallpaper_mode == "off"
    assert coord.wallpaper_collection == ""
    assert coord.wallpaper_source == ""

    # HA `/media` browse & import WS commands
    from pathlib import Path

    media_dir = Path(hass.config.config_dir) / "ws_media"
    (media_dir / "trip").mkdir(parents=True, exist_ok=True)
    (media_dir / "trip" / "a.jpg").write_bytes(_make_jpeg_bytes())
    hass.config.media_dirs = {"local": str(media_dir)}

    msg_seq += 1
    await _call_ws(
        hass,
        conn,
        msg_seq,
        "latter/system/command",
        command="browse_media_folder",
        payload={"root": "local", "subpath": "trip"},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    browse_res = conn.results[-1][1]
    assert browse_res["root"] == "local"
    assert len(browse_res["images"]) == 1
    assert browse_res["images"][0]["thumb_url"].startswith("/api/latter/wallpaper/system?")

    import_res = await _sys_cmd(
        "import_media_photos",
        {
            "root": "local",
            "paths": ["trip/a.jpg"],
            "new_collection_name": "Trip Import",
            "deduplicate": True,
        },
    )
    assert import_res["import_result"]["imported"] == 1
    assert import_res["import_result"]["collection_id"].startswith("col_")

    # Reset screensaver style back to default for downstream group tests
    await _dev_cmd(
        "save_device_config",
        {
            "config": {
                "screensaver_mode": "Docked Only",
                "screensaver_style": "Ambient Clock",
            }
        },
    )

    # Turn Off Wallpaper resets active source & rotation timer
    final_off = await _dev_cmd(
        "set_device_photo_pool", {"target": "wallpaper", "mode": "off"}
    )
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
    assert "photo_collections" in sys_bundle
    assert "photo_metadata" in sys_bundle
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
    assert discovered[0]["esphome_device_id"] == unbound_dev.id
    assert discovered[0]["node_name"] == "kitchen_panel"
    assert discovered[0]["title"] == "Kitchen Panel"
    assert "480" in discovered[0]["model_label"]
    assert "kitchen_panel-board" not in discovered[0]["model_label"]
    assert discovered[0]["area_name"] == "Kitchen"
    assert discovered[0]["default_group"] == "wall_panels"

    # Ignore / unignore discovered ESPHome Latter device (`D-066`)
    await _call_ws(
        hass,
        conn,
        2,
        "latter/system/command",
        command="ignore_discovered_device",
        payload={"esphome_device_id": unbound_dev.id},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    st_ignored = conn.results[-1][1]
    assert st_ignored["discovered_latter_devices"] == []
    assert [d["esphome_device_id"] for d in st_ignored["ignored_latter_devices"]] == [unbound_dev.id]
    assert unbound_dev.id in st_ignored["system_config"]["ignored_discovered_devices"]

    await _call_ws(
        hass,
        conn,
        3,
        "latter/system/command",
        command="unignore_discovered_device",
        payload={"esphome_device_id": unbound_dev.id},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    st_unignored = conn.results[-1][1]
    assert [d["esphome_device_id"] for d in st_unignored["discovered_latter_devices"]] == [unbound_dev.id]
    assert st_unignored["ignored_latter_devices"] == []

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



@pytest.mark.asyncio
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

    conn = websocket_api.ActiveConnection()
    await _call_ws(hass, conn, 1, "latter/system/get_state", studio_rev=STUDIO_REV)
    assert not conn.errors
    st = conn.results[-1][1]
    garage_ids = [item["id"] for item in st["catalog"]["garages"]]
    assert garage_ids == ["cover.main_garage", "cover.workshop_bay_garage"]
    clim_meta = {item["id"]: item for item in st["catalog"]["climates"]}
    assert "state_label" not in clim_meta["climate.downstairs"]
    assert "state_tone" not in clim_meta["climate.downstairs"]

    await _call_ws(
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
    assert saved_sc["thermostat_entities"] == ["climate.downstairs", "climate.upstairs"]
    assert saved_sc["lock_entities"] == ["lock.front_door", "lock.back_door"]
    assert saved_sc["garage_entities"] == ["cover.main_garage", "cover.workshop_bay_garage"]
    assert saved_sc["vacuum_entities"] == ["vacuum.main_floor", "vacuum.upstairs"]
    assert coord.thermostat_entities == ["climate.downstairs", "climate.upstairs"]

    # Wrong domain inside thermostat_entities is rejected cleanly
    await _call_ws(
        hass,
        conn,
        3,
        "latter/system/command",
        command="save_system_config",
        payload={"config": {"thermostat_entities": ["light.kitchen"]}},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors and conn.errors[-1][0] == 3

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_v3_subscribe_diet_concurrency_and_on_demand_camera_preview(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify D-064/D-065 event-first subscribe, section-hash omit, 250 ms survey delta, isolated timer tick, config_rev concurrency, and 600 s camera preview signing."""
    # 1) 0-display hub `mint_camera_preview_url` (600 s TTL) + zero `preview_url` on catalog cameras
    hass.states.async_set("camera.front_door", "idle", {"friendly_name": "Front Door"})
    entry0, _sys0, _coord0 = await setup_latter_hub(hass, with_device=False)
    conn0 = websocket_api.ActiveConnection()

    await _call_ws(hass, conn0, 1, "latter/system/get_state", studio_rev=STUDIO_REV)
    st0 = conn0.results[-1][1]
    assert st0["catalog"]["cameras"]
    assert all("preview_url" not in c for c in st0["catalog"]["cameras"])

    await _call_ws(
        hass,
        conn0,
        2,
        "latter/system/command",
        command="mint_camera_preview_url",
        payload={"camera_entity": "camera.front_door"},
        studio_rev=STUDIO_REV,
    )
    assert not conn0.errors
    minted = conn0.results[-1][1]
    assert minted["camera_entity"] == "camera.front_door"
    assert minted["expires_in"] == 600
    assert minted["preview_url"].startswith("/api/latter/camera/system?")
    assert await async_unload_entry(hass, entry0) is True

    # 2) Event-first `subscribe`, section-hash omission, scoped 250 ms survey delta, isolated timer tick & `expected_config_rev`
    hass2 = type(hass)(config_dir=hass.config.config_dir)
    hass2.states.async_set("camera.porch", "idle", {"friendly_name": "Porch"})
    entry, sys_obj, coord = await setup_latter_hub(hass2, with_device=True, with_ble_tag=True)
    tag_coord = sys_obj.coordinators["sub_tag"]

    conn = websocket_api.ActiveConnection()
    await _call_ws(
        hass2,
        conn,
        10,
        "latter/system/subscribe",
        subentry_id=coord.subentry_id,
        studio_rev=STUDIO_REV,
    )
    assert conn.results[-1] == (10, {"subscribed": True})
    assert len(conn.messages) == 1
    initial_evt = conn.messages[0]["event"]
    assert initial_evt["type"] == "state"
    assert "catalog" in initial_evt
    assert "pref_specs" in initial_evt
    assert "world_clock_zones" in initial_evt
    assert "system_wallpapers" in initial_evt
    assert "photo_collections" in initial_evt
    assert "ble_area_signatures" in initial_evt

    # Without `survey_subentry_id`, BLE survey deltas are NOT streamed on this subscription
    fabric = get_ble_fabric(hass2)
    conn.messages.clear()
    fabric.emit_survey_delta(coord._ble_tracker)
    assert [m for m in conn.messages if m["event"].get("type") == "ble_survey_delta"] == []

    # Subsequent live state push omits catalog AND omits unchanged heavy hashed sections!
    coord.async_update_listeners()
    for delay, cb in list(hass2._timers):
        if delay == 0.4:
            cb(None)
    await hass2.async_block_till_done()
    state_pushes = [m["event"] for m in conn.messages if m["event"].get("type") == "state"]
    assert len(state_pushes) >= 1
    push_evt = state_pushes[-1]
    for omitted_key in (
        "catalog",
        "pref_specs",
        "world_clock_zones",
        "discovered_ble_devices",
        "system_wallpapers",
        "photo_collections",
        "ble_area_signatures",
    ):
        assert omitted_key not in push_evt

    # Isolated 1 Hz `LatterTimerRemainingSensor` tick does NOT emit a Studio `type: "state"` push!
    coord.handle_timer_alarm_state(
        timer_running=True,
        timer_paused=False,
        remaining_sec=45,
        ringing=False,
    )
    await hass2.async_block_till_done()
    assert coord._unsub_timer_tick is not None
    conn.messages.clear()
    coord._notify_timer_tick_listeners()
    await hass2.async_block_till_done()
    assert conn.messages == []
    coord.handle_timer_alarm_state(
        timer_running=False,
        timer_paused=False,
        remaining_sec=0,
        ringing=False,
    )
    conn.subscriptions.pop(10)()

    # Scoped `survey_subentry_id` filters out other trackers and coalesces bursty deltas at 250 ms
    conn_survey = websocket_api.ActiveConnection()
    await _call_ws(
        hass2,
        conn_survey,
        20,
        "latter/system/subscribe",
        subentry_id=coord.subentry_id,
        survey_subentry_id=coord.subentry_id,
        studio_rev=STUDIO_REV,
    )
    conn_survey.messages.clear()
    # Foreign tracker delta is ignored
    assert tag_coord._ble_tracker is not None
    fabric.emit_survey_delta(tag_coord._ble_tracker)
    assert conn_survey.messages == []

    # Leading edge emits immediately; rapid follow-up within 250 ms coalesces without flooding
    fabric.emit_survey_delta(coord._ble_tracker)
    fabric.emit_survey_delta(coord._ble_tracker)
    deltas_now = [m["event"] for m in conn_survey.messages if m["event"].get("type") == "ble_survey_delta"]
    assert len(deltas_now) == 1
    conn_survey.subscriptions.pop(20)()

    # Optimistic concurrency (`expected_config_rev`) on System and Device saves
    sys_rev = initial_evt["system_config_rev"]
    dev_rev = initial_evt["device_config_rev"]
    assert sys_rev >= 1
    assert dev_rev >= 1

    await _call_ws(
        hass2,
        conn,
        30,
        "latter/system/command",
        command="save_system_config",
        payload={"config": {"ble_away_timeout_s": 210}, "expected_config_rev": sys_rev + 99},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "conflict"
    conn.errors.clear()

    await _call_ws(
        hass2,
        conn,
        31,
        "latter/system/command",
        command="save_system_config",
        payload={"config": {"ble_away_timeout_s": 210}, "expected_config_rev": sys_rev},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert conn.results[-1][1]["system_config_rev"] == sys_rev + 1

    await _call_ws(
        hass2,
        conn,
        32,
        "latter/device/command",
        subentry_id=coord.subentry_id,
        command="save_device_config",
        payload={"config": {"area_handoff": False}, "expected_config_rev": dev_rev + 99},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "conflict"
    conn.errors.clear()

    await _call_ws(
        hass2,
        conn,
        33,
        "latter/device/command",
        subentry_id=coord.subentry_id,
        command="save_device_config",
        payload={"config": {"area_handoff": False}, "expected_config_rev": dev_rev},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert conn.results[-1][1]["device_config_rev"] == dev_rev + 1

    assert await async_unload_entry(hass2, entry) is True


@pytest.mark.asyncio
async def test_unplugged_esphome_device_with_restore_selects_is_offline_and_notifies_listeners(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Unplugged ESPHome nodes with active RestoreEntity `select.*` / `update.*` must report Offline (`D-067`)."""
    from homeassistant.helpers import entity_registry as er

    from custom_components.latter.studio.payload import build_studio_state_payload

    entry, _sys_obj, coord = await setup_latter_hub(hass, stationary=1)
    slug = coord.device_slug
    ent_reg = er.async_get(hass)

    # Register realistic ESPHome Wi-Fi, IP, Assist RestoreEntity select, and HTTP firmware update entities
    for eid, _domain, name, init_st in (
        (f"sensor.{slug}_wi_fi_signal", "sensor", "Wi-Fi Signal", "-54"),
        (f"sensor.{slug}_ip_address", "sensor", "IP Address", "192.168.1.42"),
        (f"select.{slug}_assistant", "select", "Assistant", "Home Assistant"),
        (f"update.{slug}_project_firmware", "update", "Firmware", "off"),
    ):
        ent_reg.async_register(
            er.RegistryEntry(
                entity_id=eid,
                platform="esphome",
                device_id=coord.esphome_device_id,
                original_name=name,
            )
        )
        hass.states.async_set(eid, init_st)

    listener_hits = 0

    def _on_coord_update() -> None:
        nonlocal listener_hits
        listener_hits += 1

    unsub = coord.async_add_listener(_on_coord_update)
    try:
        st_online = build_studio_state_payload(hass, coord)
        dev_online = next(
            d for d in st_online["system_devices"] if d["subentry_id"] == coord.subentry_id
        )
        assert dev_online["is_online"] is True
        assert dev_online["status_code"] == "online"

        # Simulate unplugging: Wi-Fi, IP, and System: RPC Outbox go `unavailable`, while `select.*_assistant`
        # and `update.*_project_firmware` remain populated!
        hass.states.async_set(f"sensor.{slug}_wi_fi_signal", "unavailable")
        hass.states.async_set(f"sensor.{slug}_ip_address", "unavailable")
        hass.states.async_set(f"sensor.{slug}_system_rpc_outbox", "unavailable")
        await hass.async_block_till_done()

        assert listener_hits >= 1
        assert coord.is_device_online() is False
        st_offline = build_studio_state_payload(hass, coord)
        dev_offline = next(
            d for d in st_offline["system_devices"] if d["subentry_id"] == coord.subentry_id
        )
        assert dev_offline["is_online"] is False
        assert dev_offline["status_code"] == "offline"
        assert dev_offline["status_label"] == "Offline"
        assert all(qa["state"] == "unavailable" for qa in st_offline["quick_actions"])
    finally:
        unsub()

    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_builtin_group_reset_preset_and_v2_preset_migration(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any
) -> None:
    """Verify `update_group_baseline(reset_to_default=True)` and one-time `BUILTIN_GROUP_PRESET_VERSION = 2` sync (`D-067`)."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, stationary=1)
    conn = websocket_api.ActiveConnection()

    # Wall & Desk Panels default: `screensaver_mode == "Never"`, `docked_idle_timeout == "Never"`
    await _call_ws(
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
    await _call_ws(
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

    await _call_ws(
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
    await _call_ws(
        hass,
        conn,
        4,
        "latter/system/command",
        command="create_device_group",
        payload={"name": "Nightstands"},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    await _call_ws(
        hass,
        conn,
        5,
        "latter/system/command",
        command="update_group_baseline",
        payload={"group_id": "nightstands", "reset_to_default": True},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "not_allowed"
    assert await async_unload_entry(hass, entry) is True

    # Simulate an existing pre-v2 `.storage/latter.site` reload where `handhelds` had stale `wake_word_mode = "Always On"`
    from custom_components.latter import async_setup_entry
    from custom_components.latter.const import (
        CONF_DEVICE_GROUP,
        CONF_DEVICE_GROUPS,
        DATA_GLOBAL_CONFIG,
        DOMAIN,
    )
    from custom_components.latter.groups import (
        BUILTIN_GROUP_PRESET_VERSION,
        CONF_BUILTIN_GROUP_PRESET_VERSION,
        get_device_groups,
    )

    global_cfg = hass.data[DOMAIN][DATA_GLOBAL_CONFIG]
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
    sub.data = {
        **sub.data,
        CONF_DEVICE_GROUP: "handhelds",
        "wake_word_mode": "Always On",
    }

    assert await async_setup_entry(hass, entry) is True
    assert BUILTIN_GROUP_PRESET_VERSION == 4
    assert global_cfg[CONF_BUILTIN_GROUP_PRESET_VERSION] == BUILTIN_GROUP_PRESET_VERSION
    upgraded_groups = {g["id"]: g for g in get_device_groups(hass)}
    assert upgraded_groups["handhelds"]["device_config"]["wake_word_mode"] == "Docked Only"
    assert upgraded_groups["handhelds"]["device_config"]["day_brightness"] == 90
    assert upgraded_groups["handhelds"]["device_config"]["night_brightness"] == 35
    assert upgraded_groups["handhelds"]["device_config"]["bedtime_brightness"] == 15
    assert upgraded_groups["wearables"]["device_config"]["day_brightness"] == 80
    assert upgraded_groups["wearables"]["device_config"]["night_brightness"] == 25
    assert upgraded_groups["wearables"]["device_config"]["bedtime_brightness"] == 15
    assert upgraded_groups["nightstands"]["device_config"]["wake_word_mode"] == "Disabled"
    reloaded_coord = hass.data[DOMAIN][sub.subentry_id]
    assert reloaded_coord.get_device_pref("wake_word_mode") == "Docked Only"
    assert reloaded_coord.get_device_pref("night_brightness") == 35
    assert reloaded_coord.get_device_pref("bedtime_brightness") == 15
    assert reloaded_coord.device_group == "handhelds"
    assert await async_unload_entry(hass, entry) is True
