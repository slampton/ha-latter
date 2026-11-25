"""Tests for Studio logs gating, BLE survey stream, security PIN secrecy, presence calibration, and subscribe diet."""

from __future__ import annotations

from datetime import timedelta
import json
import time
from typing import Any

from homeassistant.util import dt as dt_util
from pytest_homeassistant.common import async_fire_time_changed

from custom_components.latter.const import CONF_SECURITY_PIN_HASH, STUDIO_REV
from custom_components.latter.presence.ble_fabric import get_ble_fabric
from custom_components.latter.studio.payload import log_studio_event
from tests.helpers import (
    call_ws,
    ensure_area,
    get_service_calls,
    make_ws_connection,
    register_entity,
    seed_ble_proxies,
)


async def test_studio_zero_device_state_wallpaper_signing(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify zero-device hub get_state signs system wallpaper previews cleanly."""
    entry0, _sys0, _coord0 = await setup_latter_hub(hass, with_device=False)
    conn0 = make_ws_connection(hass)
    await call_ws(hass, conn0, 1, "latter/system/get_state", studio_rev=STUDIO_REV)
    assert len(conn0.results) == 1
    st0 = conn0.results[0][1]
    assert st0["studio_rev"] == STUDIO_REV
    assert (
        st0["system_wallpapers"]
        and "/api/latter/wallpaper/system" in st0["system_wallpapers"][0]["thumb_url"]
    )
    assert await hass.config_entries.async_unload(entry0.entry_id) is True


async def test_studio_logs_gating_and_ble_survey_delta_stream(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify include_logs=False/True gating and live ble_survey_delta WS events."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    log_studio_event(hass, "INFO", "system", "Test diagnostic log line")

    conn = make_ws_connection(hass)
    await call_ws(
        hass, conn, 10, "latter/system/get_state", include_logs=False, studio_rev=STUDIO_REV
    )
    res_no_logs = conn.results[-1][1]
    assert res_no_logs.get("internal_logs", []) == []

    await call_ws(
        hass, conn, 11, "latter/system/get_state", include_logs=True, studio_rev=STUDIO_REV
    )
    res_with_logs = conn.results[-1][1]
    assert len(res_with_logs.get("internal_logs", [])) >= 1

    # Subscribe with survey_subentry_id -> emit_survey_delta coalesces and pushes compact ble_survey_delta!
    await call_ws(
        hass,
        conn,
        12,
        "latter/system/subscribe",
        subentry_id=coord.subentry_id,
        survey_subentry_id=coord.subentry_id,
        include_logs=False,
        studio_rev=STUDIO_REV,
    )
    assert 12 in conn.subscriptions
    fabric = get_ble_fabric(hass)
    assert coord._ble_tracker is not None
    conn.messages.clear()
    fabric.emit_survey_delta(coord._ble_tracker)
    assert conn.messages == []
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=0.5))
    await hass.async_block_till_done()
    delta_events = [
        m["event"]
        for m in conn.messages
        if m["event"].get("type") == "ble_survey_delta"
    ]
    assert len(delta_events) == 1
    assert delta_events[-1]["subentry_id"] == coord.subentry_id
    assert delta_events[-1]["device_slug"] == coord.device_slug
    assert "ble_survey_rows" in delta_events[-1]
    assert "ble_packets_seen" in delta_events[-1]
    assert "ble_closest_proxy" in delta_events[-1]
    assert "ble_area_signatures" not in delta_events[-1]
    assert "area_presence_grid" not in delta_events[-1]

    # Unsubscribe cleans up listeners
    conn.subscriptions.pop(12)()
    conn.messages.clear()
    fabric.emit_survey_delta(coord._ble_tracker)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert conn.messages == []

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_studio_commands_security_pin_secrecy_and_presence_calibration(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise Studio write-only security_pin secrecy, presence/BLE calibration, and system commands."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    ensure_area(hass, "Living Room", area_id="living_room")
    await seed_ble_proxies(hass)
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

    try:
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
                        {
                            "kind": "entity",
                            "target": "scene.movie_night",
                            "action": "turn_on",
                            "label": "Movie",
                            "confirm": True,
                            "badge_style": "inverted",
                            "accent": "gold",
                        },
                    ],
                    "pinned_items": [
                        {
                            "kind": "route",
                            "target": "weather:moon",
                            "label": "Moon",
                            "badge_style": "inverted",
                            "accent": "primary",
                            "page": 0,
                            "col": 0,
                            "row": 0,
                            "col_span": 2,
                            "row_span": 1,
                        },
                        {
                            "kind": "route",
                            "target": "music:lyrics",
                            "badge_style": "glass",
                            "accent": "default",
                        },
                        {
                            "kind": "entity",
                            "target": "script.baby_help",
                            "action": "turn_on",
                            "label": "Baby Help",
                            "confirm": False,
                            "accent": "red",
                            "page": 1,
                            "col": 1,
                            "row": 1,
                            "col_span": 1,
                            "row_span": 2,
                        },
                    ],
                    "pinned_page_titles": {
                        "1": "Scenes & Scripts",
                        "0": "Favorites",
                    },
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
        assert state_after_pin["config"]["dock_items"][2]["badge_style"] == "inverted"
        assert state_after_pin["config"]["dock_items"][2]["accent"] == "gold"
        assert state_after_pin["config"]["pinned_items"][0]["badge_style"] == "inverted"
        assert state_after_pin["config"]["pinned_items"][0]["accent"] == "primary"
        assert state_after_pin["config"]["pinned_items"][0]["page"] == 0
        assert state_after_pin["config"]["pinned_items"][0]["col"] == 0
        assert state_after_pin["config"]["pinned_items"][0]["row"] == 0
        assert state_after_pin["config"]["pinned_items"][0]["col_span"] == 2
        assert "row_span" not in state_after_pin["config"]["pinned_items"][0]
        assert state_after_pin["config"]["pinned_items"][1]["badge_style"] == ""
        assert state_after_pin["config"]["pinned_items"][1]["accent"] == ""
        assert state_after_pin["config"]["pinned_items"][2]["badge_style"] == ""
        assert state_after_pin["config"]["pinned_items"][2]["accent"] == "red"
        assert state_after_pin["config"]["pinned_items"][2]["row_span"] == 2
        assert state_after_pin["config"]["pinned_page_titles"] == {
            "0": "Favorites",
            "1": "Scenes & Scripts",
        }
        caps = state_after_pin["capabilities"]
        assert caps["screen_w"] == coord.screen_width
        assert caps["screen_h"] == coord.screen_height
        assert caps["grid_cols"] == coord.grid_cols
        assert caps["grid_rows"] == coord.grid_rows

        # Coordinator Protocol v3 shortcuts frame emits 14-column wire records + pinned_page_titles
        _sc_rev, sc_frames = coord.get_shortcuts_payload()
        sc_parts = sc_frames[0].split("\x1f")
        assert len(sc_parts) == 9
        dock_wire = sc_parts[5].split("\x1e")
        pinned_wire = sc_parts[7].split("\x1e")
        assert all(len(row.split("|")) == 14 for row in dock_wire)
        assert all(len(row.split("|")) == 14 for row in pinned_wire)
        assert dock_wire[0] == "route|app:pinned||||0|-1|||||||"
        assert (
            dock_wire[2]
            == "entity|scene.movie_night|turn_on|Movie|mdi:palette|1|2|inverted|gold|||||"
        )
        assert pinned_wire[0] == "route|weather:moon||Moon||0|-1|inverted|primary|0|0|0|2|"
        assert pinned_wire[1] == "route|music:lyrics||||0|-1|||||||"
        assert (
            pinned_wire[2]
            == "entity|script.baby_help|turn_on|Baby Help|mdi:script-text-play|0|2||red|1|1|1||2"
        )
        assert sc_parts[8] == "0|Favorites\x1e1|Scenes & Scripts"

        # Invalid badge_style, accent, grid coordinates, or page titles rejected via WS `invalid_format`
        for bad_sc in (
            {"dock_items": [{"kind": "route", "target": "weather:moon", "badge_style": "neon"}]},
            {"pinned_items": [{"kind": "route", "target": "weather:moon", "accent": "cyan"}]},
            {"pinned_items": [{"kind": "route", "target": "weather:moon", "page": 0, "col": 1}]},
            {"pinned_page_titles": {"99": "Invalid Page"}},
        ):
            msg_seq += 1
            await call_ws(
                hass,
                conn,
                msg_seq,
                "latter/device/command",
                command="save_device_config",
                subentry_id=coord.subentry_id,
                payload={"config": bad_sc},
                studio_rev=STUDIO_REV,
            )
            assert conn.errors[-1][1] == "invalid_format"
            conn.errors.clear()
        for retired_music_key in ("show_speaker_shortcut", "show_library_shortcut"):
            assert retired_music_key not in state_after_pin["config"]
            msg_seq += 1
            await call_ws(
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
        await _sys_cmd(
            "set_security_pin", {"subentry_id": coord.subentry_id, "clear": True}
        )
        state_cleared = await _dev_cmd(
            "save_device_config",
            {"config": {"security_pin_policy": "auto"}},
        )
        assert state_cleared["config"]["has_security_pin"] is False

        # 2) Quick Action button press ('unknown' stateless HA button) + BLE/System/Wallpapers/Device Groups
        for btn_id, btn_name in (
            ("button.pocket_actions_find_my_device", "Actions: Find My Device"),
            (
                "button.pocket_actions_trigger_voice_assistant",
                "Actions: Trigger Voice Assistant",
            ),
            (
                "button.pocket_actions_activate_screensaver",
                "Actions: Activate Screensaver",
            ),
            ("button.pocket_actions_hibernate_device", "Actions: Hibernate Device"),
            ("button.pocket_actions_restart_device", "Actions: Restart Device"),
        ):
            register_entity(
                hass,
                btn_id,
                platform="esphome",
                config_entry_id=f"esp_entry_{coord.device_slug}",
                device_id=coord.esphome_device_id,
                original_name=btn_name,
                has_entity_name=True,
            )
            hass.states.async_set(btn_id, "unknown", {"friendly_name": btn_name})

        calls = get_service_calls(hass)
        calls.clear()
        st_with_actions = await _dev_cmd(
            "esphome_entity_action",
            {"entity_id": "button.pocket_actions_find_my_device", "action": "press"},
        )
        assert [
            c.data.get("entity_id")
            for c in calls
            if c.domain == "button" and c.service == "press"
        ] == ["button.pocket_actions_find_my_device"]
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
        await _sys_cmd(
            "set_area_fusion",
            {"area_id": "living_room", "mode": "weighted", "threshold_pct": 60},
        )
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
            s
            for s in st_sig_cleared["ble_area_signatures"]
            if s["area_id"] == "living_room"
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
                        {
                            "id": "living_tv",
                            "name": "Living Area TV",
                            "area_id": "living_room",
                            "remotes": [],
                        }
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
        await call_ws(
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
        await call_ws(
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
    finally:
        for unsub in hass.data.pop("_latter_test_bt_unsubs", []):
            unsub()

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_on_demand_camera_preview_minting_zero_device(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify 0-display hub `mint_camera_preview_url` (600 s TTL) and zero `preview_url` on catalog cameras."""
    hass.states.async_set("camera.front_door", "idle", {"friendly_name": "Front Door"})
    entry0, _sys0, _coord0 = await setup_latter_hub(hass, with_device=False)
    conn0 = make_ws_connection(hass)

    await call_ws(hass, conn0, 1, "latter/system/get_state", studio_rev=STUDIO_REV)
    st0 = conn0.results[-1][1]
    assert st0["catalog"]["cameras"]
    assert all("preview_url" not in c for c in st0["catalog"]["cameras"])

    await call_ws(
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
    assert await hass.config_entries.async_unload(entry0.entry_id) is True


async def test_v3_subscribe_diet_and_optimistic_concurrency(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify D-064/D-065 event-first subscribe, section-hash omit, 250 ms survey delta, isolated timer tick, and config_rev concurrency."""
    hass.states.async_set("camera.porch", "idle", {"friendly_name": "Porch"})
    entry, sys_obj, coord = await setup_latter_hub(
        hass, with_device=True, with_ble_tag=True
    )
    tag_coord = sys_obj.coordinators["sub_tag"]

    conn = make_ws_connection(hass)
    await call_ws(
        hass,
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
    fabric = get_ble_fabric(hass)
    conn.messages.clear()
    fabric.emit_survey_delta(coord._ble_tracker)
    assert [
        m for m in conn.messages if m["event"].get("type") == "ble_survey_delta"
    ] == []

    # Subsequent live state push omits catalog AND omits unchanged heavy hashed sections!
    coord.async_update_listeners()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    state_pushes = [
        m["event"] for m in conn.messages if m["event"].get("type") == "state"
    ]
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
        "wallpapers",
        "system_controls",
        "discovered_latter_devices",
        "ignored_latter_devices",
        "locale_strings",
    ):
        assert omitted_key not in push_evt

    # Irrelevant entity registry updates (e.g., icon-only change) are ignored and do NOT trigger push/catalog rebuild
    from homeassistant.helpers import entity_registry as er

    conn.messages.clear()
    hass.bus.async_fire(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        {"action": "update", "entity_id": "sensor.unrelated", "changes": {"icon": "mdi:old"}},
    )
    await hass.async_block_till_done()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()
    assert conn.messages == []

    # Timestamp-based `LatterTimerEndsSensor` updates timer state cleanly with NO 1 Hz `_unsub_timer_tick` loop!
    coord.handle_timer_alarm_state(
        timer_running=True,
        timer_paused=False,
        remaining_sec=45,
        ringing=False,
    )
    await hass.async_block_till_done()
    assert coord.timer_running is True
    assert bool(coord.timer_ends_at_utc)
    assert getattr(coord, "_unsub_timer_tick", None) is None
    conn.messages.clear()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()
    # One debounced push from the initial timer start is allowed; verify steady-state produces zero 1 Hz ticks
    conn.messages.clear()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert conn.messages == []
    coord.handle_timer_alarm_state(
        timer_running=False,
        timer_paused=False,
        remaining_sec=0,
        ringing=False,
    )
    conn.subscriptions.pop(10)()
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=1))
    await hass.async_block_till_done()

    # Scoped `survey_subentry_id` filters out other trackers and coalesces bursty deltas at 250 ms
    conn_survey = make_ws_connection(hass)
    await call_ws(
        hass,
        conn_survey,
        20,
        "latter/system/subscribe",
        subentry_id=coord.subentry_id,
        survey_subentry_id=coord.subentry_id,
        studio_rev=STUDIO_REV,
    )
    conn_survey.messages.clear()
    # Foreign tracker delta is ignored (even after timer window)
    assert tag_coord._ble_tracker is not None
    fabric.emit_survey_delta(tag_coord._ble_tracker)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=0.5))
    await hass.async_block_till_done()
    assert [
        m for m in conn_survey.messages if m["event"].get("type") == "ble_survey_delta"
    ] == []

    # Rapid burst does zero pre-coalesce work and emits a single compact `ble_survey_delta` after 250 ms
    conn_survey.messages.clear()
    fabric.emit_survey_delta(coord._ble_tracker)
    fabric.emit_survey_delta(coord._ble_tracker)
    assert conn_survey.messages == []
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=0.5))
    await hass.async_block_till_done()
    deltas_now = [
        m["event"]
        for m in conn_survey.messages
        if m["event"].get("type") == "ble_survey_delta"
    ]
    assert len(deltas_now) == 1
    assert "ble_survey_rows" in deltas_now[0]
    assert "ble_area_signatures" not in deltas_now[0]
    assert "area_presence_grid" not in deltas_now[0]
    conn_survey.subscriptions.pop(20)()

    # Optimistic concurrency (`expected_config_rev`) on System and Device saves
    sys_rev = initial_evt["system_config_rev"]
    dev_rev = initial_evt["device_config_rev"]
    assert sys_rev >= 1
    assert dev_rev >= 1

    await call_ws(
        hass,
        conn,
        30,
        "latter/system/command",
        command="save_system_config",
        payload={
            "config": {"ble_away_timeout_s": 210},
            "expected_config_rev": sys_rev + 99,
        },
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "conflict"
    conn.errors.clear()

    await call_ws(
        hass,
        conn,
        31,
        "latter/system/command",
        command="save_system_config",
        payload={"config": {"ble_away_timeout_s": 210}, "expected_config_rev": sys_rev},
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert conn.results[-1][1]["system_config_rev"] == sys_rev + 1

    await call_ws(
        hass,
        conn,
        32,
        "latter/device/command",
        subentry_id=coord.subentry_id,
        command="save_device_config",
        payload={
            "config": {"area_handoff": False},
            "expected_config_rev": dev_rev + 99,
        },
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "conflict"
    conn.errors.clear()

    await call_ws(
        hass,
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

    assert await hass.config_entries.async_unload(entry.entry_id) is True
