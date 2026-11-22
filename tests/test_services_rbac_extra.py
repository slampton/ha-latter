"""Integration tests for Latter remote, calendar, notify, intercom, doorbell, and volume feature gating."""

from __future__ import annotations

from typing import Any

from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
import pytest

from custom_components.latter.areas.actions import async_execute_area_action
from custom_components.latter.const import (
    CONF_BROADCAST_SPEAKERS,
    CONF_CAMERA_ENTITIES,
    CONF_REMOTES_LIST,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    RPC_CALENDAR_CREATE_EVENT,
    RPC_CALENDAR_DELETE_EVENT,
    RPC_CALENDAR_FETCH,
    RPC_DOORBELL_INTERCOM,
    RPC_REMOTE_ACTION,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_NOTIFY,
)
from custom_components.latter.media.volume import (
    VOLUME_MUTE_FLAG,
    VOLUME_STEP_FLAG,
    async_execute_volume_action,
)
from custom_components.latter.presence.ble_fabric import get_ble_fabric
from tests.helpers import (
    add_mock_entry,
    mock_service,
    register_device,
    register_entity,
)


@pytest.mark.asyncio
async def test_remote_calendar_notify_intercom_and_doorbell_services(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise remote_action, calendar CRUD/fetch, notify, intercom_broadcast, and doorbell_intercom."""
    entry, sys_obj, coord = await setup_latter_hub(hass)

    calls_log: list[tuple[str, str, dict[str, Any]]] = []
    for dom, svcs in {
        "remote": ("send_command", "toggle"),
        "calendar": ("create_event",),
        "tts": ("speak",),
    }.items():
        for s in svcs:
            mock_service(
                hass,
                dom,
                s,
                lambda call, d=dom, sv=s: calls_log.append((d, sv, dict(call.data))),
            )

    # 1) remote_action (Android TV short + long_press, Apple TV InputAction.Hold >= 1.0s, and ADB fallback)
    mock_service(
        hass,
        "androidtv",
        "adb_command",
        lambda call: calls_log.append(("androidtv", "adb_command", dict(call.data))),
    )
    register_entity(
        hass, "remote.shield_tv", platform="androidtv_remote", area_id="kitchen"
    )
    register_entity(hass, "remote.lounge_atv", platform="apple_tv", area_id="kitchen")
    register_entity(
        hass, "media_player.bedroom_fire_tv", platform="firetv", area_id="kitchen"
    )
    hass.states.async_set("remote.shield_tv", "on", {"friendly_name": "Shield TV"})
    hass.states.async_set("remote.lounge_atv", "on", {"friendly_name": "Apple TV"})
    hass.states.async_set(
        "media_player.bedroom_fire_tv", "on", {"friendly_name": "Fire TV"}
    )
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_REMOTES_LIST] = [
        "remote.shield_tv",
        "remote.lounge_atv",
        "media_player.bedroom_fire_tv",
    ]
    coord.async_set_active_area("kitchen")
    for rem_act, rem_cmd in (
        ("command", "up"),
        ("command", "select"),
        ("long_press", "select"),
        ("toggle", "power"),
    ):
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_REMOTE_ACTION,
            {"slot": 1, "action": rem_act, "command": rem_cmd},
        )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_REMOTE_ACTION,
        {"slot": 2, "action": "long_press", "command": "select"},
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_REMOTE_ACTION,
        {"slot": 2, "action": "long_press", "command": "back"},
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_REMOTE_ACTION,
        {"slot": 3, "action": "long_press", "command": "select"},
    )
    await hass.async_block_till_done()
    remote_send_calls = [
        d for dom, svc, d in calls_log if (dom, svc) == ("remote", "send_command")
    ]
    assert {
        "entity_id": "remote.shield_tv",
        "command": "DPAD_CENTER",
    } in remote_send_calls
    assert {
        "entity_id": "remote.shield_tv",
        "command": "DPAD_CENTER",
        "hold_secs": 0.6,
    } in remote_send_calls
    assert {
        "entity_id": "remote.lounge_atv",
        "command": "select",
        "hold_secs": 1.0,
    } in remote_send_calls
    assert {
        "entity_id": "remote.lounge_atv",
        "command": "menu",
        "hold_secs": 1.0,
    } in remote_send_calls
    adb_calls = [
        d for dom, svc, d in calls_log if (dom, svc) == ("androidtv", "adb_command")
    ]
    assert {
        "entity_id": "media_player.bedroom_fire_tv",
        "command": "input keyevent --longpress 23",
    } in adb_calls

    # 2) calendar_fetch, calendar_create_event & calendar_delete_event
    hass.states.async_set(
        "calendar.work",
        "off",
        {"friendly_name": "Work", "supported_features": 3},
    )
    created_rrule_events: list[dict[str, Any]] = []
    deleted_events: list[tuple[str, Any, Any]] = []

    class _FakeCalEntity:
        async def async_create_event(self, **kwargs: Any) -> None:
            created_rrule_events.append(kwargs)

        async def async_delete_event(
            self,
            uid: str,
            recurrence_id: str | None = None,
            recurrence_range: str | None = None,
        ) -> None:
            deleted_events.append((uid, recurrence_id, recurrence_range))

    class _FakeCalComp:
        def get_entity(self, eid: str) -> Any:
            return _FakeCalEntity() if eid == "calendar.work" else None

    hass.data["calendar"] = _FakeCalComp()
    mock_service(
        hass,
        "calendar",
        "get_events",
        lambda _c: {
            "calendar.work": {
                "events": [
                    {
                        "summary": "Standup",
                        "start": "2026-11-18T09:00:00-08:00",
                        "end": "2026-11-18T09:30:00-08:00",
                        "location": "Downtown HQ",
                        "uid": "evt-1",
                    }
                ]
            }
        },
        supports_response=SupportsResponse.ONLY,
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_CALENDAR_FETCH,
        {
            "mode": "window",
            "start_date": "2026-11-01",
            "end_date": "2026-11-30",
            "days": 30,
        },
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_CALENDAR_CREATE_EVENT,
        {
            "calendar_entity": "calendar.work",
            "summary": "Standup",
            "location": "Downtown HQ",
            "start_date_time": "2026-11-18 09:00:00",
            "end_date_time": "2026-11-18 09:30:00",
            "rrule": "FREQ=WEEKLY",
        },
    )
    assert len(created_rrule_events) == 1
    assert created_rrule_events[0]["rrule"] == "FREQ=WEEKLY"

    hass.states.async_set(
        "calendar.personal",
        "off",
        {"friendly_name": "Personal", "supported_features": 1},
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_CALENDAR_CREATE_EVENT,
        {
            "calendar_entity": "calendar.personal",
            "summary": "Trip",
            "all_day": True,
            "start_date": "2026-11-20",
            "end_date": "2026-11-21",
        },
    )

    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_CALENDAR_DELETE_EVENT,
        {
            "calendar_entity": "calendar.work",
            "uid": "evt-1",
            "recurrence_id": "20261118T170000Z",
        },
    )
    assert deleted_events == [("evt-1", "20261118T170000Z", None)]

    # 3) notify & intercom_broadcast ('all', 'occupied_areas', 'person.alex', invalid media_url check)
    coord.async_set_active_area("living_room")
    ma_entry = add_mock_entry(
        hass,
        domain="music_assistant",
        title="Music Assistant",
        entry_id="ma_bc_entry",
        data={},
    )
    register_entity(
        hass,
        "media_player.pocket_sendspin",
        platform="music_assistant",
        config_entry=ma_entry,
        area_id="living_room",
    )
    hass.states.async_set(
        "media_player.pocket_sendspin",
        "idle",
        {"mass_player_type": "player", "friendly_name": "Pocket Sendspin"},
    )
    fabric = get_ble_fabric(hass)
    assert coord._ble_tracker is not None
    coord._ble_tracker.current_area_id = "living_room"
    coord._ble_tracker.is_away = False
    coord.active_area_id = "living_room"
    fabric.notify_occupancy_listeners()
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_BROADCAST_SPEAKERS] = [
        "media_player.pocket_sendspin"
    ]
    hass.states.async_set("tts.piper", "unknown", {})

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFY,
        {
            "target_device": "occupied_areas",
            "title": "Dinner",
            "message": "Ready",
            "announce": True,
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFY,
        {
            "target_device": "person.alex",
            "title": "Note",
            "message": "Package arrived",
        },
        blocking=True,
    )

    resp_ic = await hass.services.async_call(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        {"target_device": "occupied_areas", "message": "Testing intercom"},
        blocking=True,
        return_response=True,
    )
    assert resp_ic["delivered"] is True

    with pytest.raises(ServiceValidationError) as exc_ic:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INTERCOM_BROADCAST,
            {"message": "Bad URL", "media_url": "http://evil.example.com/clip.mp3"},
            blocking=True,
        )
    assert exc_ic.value.translation_key == "invalid_intercom_media_url"

    # 4) doorbell_intercom (listen_start, set_noise_reduction, talk_message, listen_stop)
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_CAMERA_ENTITIES] = ["camera.front"]
    hass.states.async_set("camera.front", "streaming", {"friendly_name": "Front"})
    hass.states.async_set("media_player.front_speaker", "idle", {"volume_level": 0.2})
    for db_act in ("listen_start", "set_noise_reduction", "talk_message", "listen_stop"):
        res_db = await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_DOORBELL_INTERCOM,
            {
                "action": db_act,
                "camera_entity": "camera.front",
                "noise_reduction": "light",
                "message": "Leave it on the mat",
            },
        )
        assert res_db["status"] == "ok"

    assert ("remote", "send_command") in {(d, s) for d, s, _ in calls_log}
    assert ("calendar", "create_event") in {(d, s) for d, s, _ in calls_log}
    assert await hass.config_entries.async_unload(entry.entry_id) is True


@pytest.mark.asyncio
async def test_volume_supported_features_and_remote_fallback(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify HA 2026.10+ VOLUME_SET/VOLUME_STEP/VOLUME_MUTE gating (webostv ARC, Spotify, remote fallback)."""
    entry, sys_obj, coord = await setup_latter_hub(hass)
    coord.active_area_id = "living_room"

    calls_log: list[tuple[str, str, dict[str, Any]]] = []
    for dom, svcs in (
        ("media_player", ("volume_set", "volume_up", "volume_down", "volume_mute")),
        ("remote", ("send_command",)),
    ):
        for s in svcs:
            mock_service(
                hass,
                dom,
                s,
                lambda call, d=dom, sv=s: calls_log.append((d, sv, dict(call.data))),
            )

    # 1) LG webOS ARC soundbar: exposes numeric volume_level, supports STEP + MUTE, omits VOLUME_SET
    hass.states.async_set(
        "media_player.lg_arc_tv",
        "on",
        {
            "friendly_name": "LG OLED TV",
            "volume_level": 0.31,
            "is_volume_muted": False,
            "supported_features": VOLUME_MUTE_FLAG | VOLUME_STEP_FLAG,
        },
    )
    assert (
        await async_execute_volume_action(
            hass, "media_player.lg_arc_tv", "up", volume_level=41
        )
        is True
    )
    await async_execute_area_action(hass, "media_player.lg_arc_tv", "step_down")
    assert (
        await async_execute_volume_action(
            hass, "media_player.lg_arc_tv", "set", volume_level=50
        )
        is False
    )
    await async_execute_area_action(
        hass, "media_player.lg_arc_tv", "set_level", level=50
    )
    await hass.async_block_till_done()

    assert calls_log == [
        ("media_player", "volume_up", {"entity_id": "media_player.lg_arc_tv"}),
        ("media_player", "volume_down", {"entity_id": "media_player.lg_arc_tv"}),
    ]
    calls_log.clear()

    # 2) Spotify / fixed line-out device: exposes volume_level=1.0 with zero volume flags
    hass.states.async_set(
        "media_player.spotify_fixed",
        "playing",
        {
            "friendly_name": "Spotify Fixed",
            "volume_level": 1.0,
            "supported_features": 0,
        },
    )
    for act, lvl in (("set", 60.0), ("up", 70.0), ("down", 50.0), ("mute", None)):
        assert (
            await async_execute_volume_action(
                hass, "media_player.spotify_fixed", act, volume_level=lvl
            )
            is False
        )
    await hass.async_block_till_done()
    assert calls_log == []

    # 3) Paired TV remote + line-out media_player on the same DeviceEntry falls back to remote.send_command
    tv_dev = register_device(
        hass,
        config_entry_id=entry.entry_id,
        entry_domain=DOMAIN,
        identifiers={("androidtv_remote", "shield_lineout")},
        name="Living Room Shield",
        manufacturer="Latter",
        area_id="living_room",
    )
    register_entity(
        hass,
        "media_player.shield_lineout",
        platform="androidtv_remote",
        device_id=tv_dev.id,
        area_id="living_room",
    )
    register_entity(
        hass,
        "remote.shield_lineout",
        platform="androidtv_remote",
        device_id=tv_dev.id,
        area_id="living_room",
    )
    hass.states.async_set(
        "media_player.shield_lineout",
        "playing",
        {
            "friendly_name": "Living Room Shield",
            "volume_level": 1.0,
            "supported_features": 0,
        },
    )
    hass.states.async_set(
        "remote.shield_lineout", "on", {"friendly_name": "Living Room Shield"}
    )
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_REMOTES_LIST] = [
        "media_player.shield_lineout"
    ]

    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_REMOTE_ACTION,
        {"slot": 1, "action": "volume_up"},
    )
    await hass.async_block_till_done()
    assert calls_log == [
        (
            "remote",
            "send_command",
            {"entity_id": "remote.shield_lineout", "command": "VOLUME_UP"},
        )
    ]

    assert await hass.config_entries.async_unload(entry.entry_id) is True
