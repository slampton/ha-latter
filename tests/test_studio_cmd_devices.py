"""Tests for Studio rev-mismatch guards, discovered devices, offline ESPHome restore selects, and Phase 4 device actions."""

from __future__ import annotations

from typing import Any

from homeassistant.components import websocket_api
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest

from custom_components.latter import async_unload_entry
from custom_components.latter.const import STUDIO_REV
from custom_components.latter.studio.payload import build_studio_state_payload


async def _call_ws(
    hass: Any, conn: Any, msg_id: int, ws_type: str, **payload: Any
) -> None:
    handler = hass._ws_commands[ws_type]
    schema = getattr(handler, "_ws_schema", None)
    raw_msg = {"id": msg_id, "type": ws_type, **payload}
    validated = schema(raw_msg) if schema is not None else raw_msg
    await handler(hass, conn, validated)


async def test_studio_rev_mismatch_on_all_read_and_mutation_endpoints(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify mandatory studio_rev=44 schema validation and studio_rev_mismatch on all 9 WS endpoints."""
    import voluptuous as vol

    assert STUDIO_REV == 44
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


async def test_discovered_latter_devices_and_add_latter_device_command(
    hass: Any, setup_latter_hub: Any, make_esphome_device: Any
) -> None:
    """Verify unbound ESPHome Latter discovery in Studio payload and one-click `add_latter_device` validation."""
    import sys

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
            "assigned_person": "person.alex",
        },
        studio_rev=STUDIO_REV,
    )
    assert not conn.errors
    assert len(recorded_inits) == 1
    assert recorded_inits[0][0] == (entry.entry_id, "device")
    assert recorded_inits[0][2] == {
        "esphome_device_id": unbound_dev.id,
        "device_group": "auto",
        "assigned_person": "person.alex",
    }

    assert await async_unload_entry(hass, entry) is True


async def test_unplugged_esphome_device_with_restore_selects_is_offline_and_notifies_listeners(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Unplugged ESPHome nodes with active RestoreEntity `select.*` / `update.*` must report Offline (`D-067`)."""
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


async def test_phase4_device_actions_telemetry_and_dnd_entities(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify Phase 4 `device_action` verbs, `device_telemetry` -> Studio `live.telemetry`, and Screen/Screensaver/DND/Dismiss entities."""
    entry, sys_obj, coord = await setup_latter_hub(hass)
    ent_reg = er.async_get(hass)
    wifi_eid = f"sensor.{coord.device_slug}_system_wi_fi_signal"
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id=wifi_eid,
            platform="esphome",
            device_id=coord.esphome_device_id,
        )
    )
    hass.states.async_set(wifi_eid, "-46")
    assert coord.radio_connected is True

    conn = websocket_api.ActiveConnection()
    msg_id = 0

    for verb in (
        "deactivate_screensaver",
        "wake_screen",
        "screen_off",
        "set_profiler_on",
        "set_profiler_off",
        "request_telemetry",
    ):
        msg_id += 1
        await _call_ws(
            hass,
            conn,
            msg_id,
            "latter/device/command",
            command="device_action",
            subentry_id=coord.subentry_id,
            payload={"action": verb},
            studio_rev=STUDIO_REV,
        )
        assert not conn.errors, f"{verb} failed: {conn.errors}"

    # Retired `log_memory_report` and `system_entity_action` must fail cleanly
    msg_id += 1
    await _call_ws(
        hass,
        conn,
        msg_id,
        "latter/device/command",
        command="device_action",
        subentry_id=coord.subentry_id,
        payload={"action": "log_memory_report"},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "invalid_format"
    conn.errors.clear()

    msg_id += 1
    await _call_ws(
        hass,
        conn,
        msg_id,
        "latter/system/command",
        command="system_entity_action",
        payload={},
        studio_rev=STUDIO_REV,
    )
    assert conn.errors[-1][1] == "unknown_command"
    conn.errors.clear()

    # Dispatch `device_telemetry` RPC and verify Studio `live.telemetry`
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "device_telemetry",
        {
            "link_json": '{"state":"active","tx":12}',
            "int_ram_free_kb": 184,
            "int_ram_min_kb": 140,
            "int_ram_largest_kb": 112,
            "psram_min_kb": 6420,
            "ble_active": True,
            "profiler_on": True,
        },
    )
    msg_id += 1
    await _call_ws(
        hass,
        conn,
        msg_id,
        "latter/system/get_state",
        subentry_id=coord.subentry_id,
        studio_rev=STUDIO_REV,
    )
    st_telem = conn.results[-1][1]
    assert st_telem["live"]["telemetry"]["int_ram_free_kb"] == 184
    assert st_telem["live"]["telemetry"]["psram_min_kb"] == 6420
    assert st_telem["live"]["telemetry"]["ble_active"] is True
    assert st_telem["live"]["telemetry"]["profiler_on"] is True
    assert st_telem["config"]["do_not_disturb"] is False

    # Exercise `light.<slug>_screen`, `switch.<slug>_screensaver`, `switch.<slug>_do_not_disturb`, `button.<slug>_dismiss_alert`
    screen_light = next(
        e for e in hass.data["_test_entities"]["light"] if e.entity_id == f"light.{coord.device_slug}_screen"
    )
    ss_switch = next(
        e for e in hass.data["_test_entities"]["switch"] if e.entity_id == f"switch.{coord.device_slug}_screensaver"
    )
    dnd_switch = next(
        e for e in hass.data["_test_entities"]["switch"] if e.entity_id == f"switch.{coord.device_slug}_do_not_disturb"
    )
    dismiss_btn = next(
        e for e in hass.data["_test_entities"]["button"] if e.entity_id == f"button.{coord.device_slug}_dismiss_alert"
    )
    assert not any(
        e.entity_id.endswith("_activate_screensaver") for e in hass.data["_test_entities"]["button"]
    )

    await screen_light.async_turn_on(brightness=128)
    assert coord.display_power_state == 0
    await ss_switch.async_turn_on()
    assert coord.screensaver_active is True
    await screen_light.async_turn_off()
    assert coord.display_power_state == 2
    await dnd_switch.async_turn_on()
    assert coord.do_not_disturb is True
    coord.alarm_ringing = True
    await dismiss_btn.async_press()
    assert coord.alarm_ringing is False

    assert await async_unload_entry(hass, entry) is True
