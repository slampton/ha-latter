"""Integration tests for Latter domain services, RBAC admin enforcement, Media/MA linking, Browse LRU cache, and Reset."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
import pytest

from custom_components.latter import async_unload_entry
from custom_components.latter.areas import async_execute_area_action
from custom_components.latter.const import (
    CONF_BROADCAST_SPEAKERS,
    CONF_CAMERA_ENTITIES,
    CONF_PINNED_ITEMS,
    CONF_REMOTES_LIST,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_VOLUME_OVERRIDES,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    MIN_FIRMWARE_SDK_REV,
    PUBLIC_SERVICES,
    RPC_AREA_ACTION,
    RPC_AREA_BROWSE,
    RPC_CALENDAR_CREATE_EVENT,
    RPC_CALENDAR_DELETE_EVENT,
    RPC_CALENDAR_FETCH,
    RPC_DEVICE_HELLO,
    RPC_DOORBELL_INTERCOM,
    RPC_MEDIA_COMMAND,
    RPC_MEDIA_VOLUME,
    RPC_MUSIC_BROWSE,
    RPC_REMOTE_ACTION,
    RPC_SAVE_CUSTOM_COLOR,
    RPC_SHORTCUT_ACTION,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_NOTIFY,
    SERVICE_RESET_DEVICE,
    SERVICE_SET_ACTIVE_AREA,
    SERVICE_SET_ACTIVE_SPEAKER,
)
from custom_components.latter.media import (
    VOLUME_MUTE_FLAG,
    VOLUME_STEP_FLAG,
    async_execute_volume_action,
    clear_ma_counterpart_cache,
    resolve_ma_counterpart_entity,
)
from custom_components.latter.media_browse import (
    _BROWSE_LYRICS_BIO_CACHE,
    MAX_BROWSE_CACHE_ENTRIES,
    _cache_put,
    clear_browse_cache,
)
from custom_components.latter.presence import get_ble_fabric
from custom_components.latter.protocol import hash_security_pin, wrap_pin_code


@pytest.mark.asyncio
async def test_services_rbac_and_validation_errors(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify non-admin HA users are blocked on mutating config services while admin & internal contexts succeed."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)

    non_admin_ctx = Context(user_id="regular_user")
    admin_ctx = Context(user_id="admin_user")

    # Only the 5 public actions are registered on hass.services
    assert set(hass.services.async_services_for_domain(DOMAIN).keys()) == set(PUBLIC_SERVICES)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_DEVICE,
            {"target_device": coord.device_slug, "device_settings": False, "latter_options": True},
            blocking=True,
            context=non_admin_ctx,
        )

    # Bound RPC save_custom_color succeeds & validation errors carry translation_domain + translation_key
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_SAVE_CUSTOM_COLOR,
        {"hex_color": "33AAFF", "name": "Ocean"},
    )
    assert coord.device_data.get("device_custom_color") == "#33AAFF"

    with pytest.raises(ServiceValidationError) as exc_hex:
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_SAVE_CUSTOM_COLOR,
            {"hex_color": "#ZZZZZZ"},
        )
    assert exc_hex.value.translation_domain == DOMAIN
    assert exc_hex.value.translation_key == "invalid_hex_color"

    # shortcut_action enforces per-Device configured (entity_id, action) allowlist + perimeter PIN policy
    dispatched_shortcuts: list[tuple[str, str, dict[str, Any]]] = []

    async def _rec_shortcut_svc(call: Any) -> None:
        dispatched_shortcuts.append((call.domain, call.service, dict(call.data)))

    hass.services.async_register("script", "turn_on", _rec_shortcut_svc)
    hass.services.async_register("lock", "unlock", _rec_shortcut_svc)
    hass.states.async_set("script.baby_help", "off", {"friendly_name": "Baby Help"})
    hass.states.async_set("lock.front_door", "locked", {"friendly_name": "Front Door"})

    with pytest.raises(ServiceValidationError) as exc_unconf:
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_SHORTCUT_ACTION,
            {"entity_id": "script.baby_help", "action": "turn_on"},
        )
    assert exc_unconf.value.translation_key == "shortcut_not_configured"

    coord.update_device_config(
        {
            **coord.device_data,
            CONF_PINNED_ITEMS: [
                {
                    "kind": "entity",
                    "target": "script.baby_help",
                    "action": "turn_on",
                    "label": "Baby Help",
                    "icon": "mdi:baby-face-outline",
                    "confirm": False,
                },
                {
                    "kind": "entity",
                    "target": "lock.front_door",
                    "action": "unlock",
                    "label": "Unlock Door",
                    "icon": "mdi:lock-open",
                    "confirm": True,
                },
            ],
            CONF_SECURITY_PIN_POLICY: "require_pin",
            CONF_SECURITY_PIN_HASH: hash_security_pin("4826"),
        }
    )

    # Configured non-perimeter shortcut executes directly
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_SHORTCUT_ACTION,
        {"entity_id": "script.baby_help", "action": "turn_on"},
    )
    assert ("script", "turn_on") in {(d, s) for d, s, _ in dispatched_shortcuts}

    # Wrong verb on configured entity is still rejected by allowlist
    with pytest.raises(ServiceValidationError) as exc_wrong_verb:
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_SHORTCUT_ACTION,
            {"entity_id": "script.baby_help", "action": "turn_off"},
        )
    assert exc_wrong_verb.value.translation_key == "shortcut_not_configured"

    # Configured perimeter shortcut requires wrapped PIN when policy == require_pin
    with pytest.raises(ServiceValidationError) as exc_pin_req:
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_SHORTCUT_ACTION,
            {"entity_id": "lock.front_door", "action": "unlock"},
        )
    assert exc_pin_req.value.translation_key == "security_pin_required"

    wrapped_sc_pin = wrap_pin_code(
        coord._pin_key_id,
        coord._pin_key_bytes,
        1,
        "lock.front_door",
        "unlock",
        "4826",
    )
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_SHORTCUT_ACTION,
        {"entity_id": "lock.front_door", "action": "unlock", "code": wrapped_sc_pin},
    )
    assert ("lock", "unlock") in {(d, s) for d, s, _ in dispatched_shortcuts}

    with pytest.raises(ServiceValidationError) as exc_target:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_ACTIVE_AREA,
            {"target_device": "nonexistent_node", "area_id": "kitchen"},
            blocking=True,
        )
    assert exc_target.value.translation_key == "unknown_target"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_RESET_DEVICE,
        {"target_device": coord.device_slug, "device_settings": True, "latter_options": True},
        blocking=True,
        context=admin_ctx,
    )
    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_all_domain_services_ma_link_and_browse_lru(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise device_hello, media/MA container fallback, volume override, browse, remote, calendar, notify, intercom, and doorbell services."""
    # Verify bounded 64-entry LRU cache on browse lyrics/bio
    clear_browse_cache()
    assert MAX_BROWSE_CACHE_ENTRIES == 64
    for i in range(80):
        _cache_put(f"song_{i}", {"lines": [f"Line {i}"]})
    assert len(_BROWSE_LYRICS_BIO_CACHE) == 64
    assert "song_0" not in _BROWSE_LYRICS_BIO_CACHE
    assert "song_79" in _BROWSE_LYRICS_BIO_CACHE

    entry, _sys_obj, coord = await setup_latter_hub(hass)
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    issue_reg = ir.async_get(hass)

    from homeassistant.config_entries import ConfigEntry

    hass.config_entries.add_entry(
        ConfigEntry(entry_id="ma_entry", domain="music_assistant", title="Music Assistant")
    )

    # 1) Music Assistant counterpart resolution: unlinked raises Repair; MAC-linked resolves cleanly!
    ma_unlinked_dev = dev_reg.async_get_or_create(
        config_entry_id="ma_entry",
        identifiers={("music_assistant", "other_spk")},
        name="Pocket Assistant",  # Same name/slug MUST NOT match!
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.pocket_assistant_ma_wrong",
            platform="music_assistant",
            device_id=ma_unlinked_dev.id,
            config_entry_id="ma_entry",
        )
    )
    hass.states.async_set(
        "media_player.pocket_assistant_ma_wrong",
        "idle",
        {"mass_player_type": "player", "friendly_name": "Wrong MA"},
    )
    clear_ma_counterpart_cache(hass)
    assert resolve_ma_counterpart_entity(hass, coord.local_speaker) is None
    assert any("link_ma_player" in k[1] for k in issue_reg.issues)

    # Now register a true MAC-matched MA player for AA:BB:CC:DD:EE:01
    ma_true_dev = dev_reg.async_get_or_create(
        config_entry_id="ma_entry",
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:01")},
        identifiers={("music_assistant", "aa:bb:cc:dd:ee:01")},
        name="Pocket Sendspin",
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.pocket_sendspin",
            platform="music_assistant",
            device_id=ma_true_dev.id,
            config_entry_id="ma_entry",
            area_id="living_room",
        )
    )
    hass.states.async_set(
        "media_player.pocket_sendspin",
        "playing",
        {
            "mass_player_type": "player",
            "volume_level": 0.4,
            "media_title": "Blue Train",
            "media_artist": "John Coltrane",
            "friendly_name": "Pocket Sendspin",
        },
    )
    clear_ma_counterpart_cache(hass)
    assert (
        resolve_ma_counterpart_entity(hass, coord.local_speaker)
        == "media_player.pocket_sendspin"
    )

    # Register service handlers for media, MA, remote, calendar, tts
    calls_log: list[tuple[str, str, dict[str, Any]]] = []
    for dom, svcs in {
        "media_player": (
            "media_play_pause",
            "media_play",
            "media_pause",
            "media_next_track",
            "media_previous_track",
            "media_seek",
            "volume_set",
            "volume_up",
            "volume_down",
            "volume_mute",
            "shuffle_set",
            "repeat_set",
            "play_media",
            "media_stop",
            "join",
            "unjoin",
            "toggle",
        ),
        "remote": ("send_command", "toggle"),
        "number": ("set_value",),
        "calendar": ("create_event",),
        "tts": ("speak",),
    }.items():
        for s in svcs:
            hass.services.async_register(
                dom, s, lambda call, d=dom, sv=s: calls_log.append((d, sv, dict(call.data)))
            )

    def _ma_play_media(call: Any) -> None:
        calls_log.append(("music_assistant", "play_media", dict(call.data)))
        # Simulate container URI failure so MA track expansion fallback runs!
        if call.data.get("media_id") == "library://album/42":
            raise RuntimeError("Container play failed")

    hass.services.async_register("music_assistant", "play_media", _ma_play_media)
    hass.services.async_register(
        "music_assistant",
        "transfer_queue",
        lambda call: calls_log.append(("music_assistant", "transfer_queue", dict(call.data))),
    )
    hass.services.async_register(
        "music_assistant",
        "get_library",
        lambda call: {
            "items": [
                {
                    "uri": "library://track/101",
                    "name": "Blue Train",
                    "artists": [{"name": "John Coltrane"}],
                    "media_type": str(call.data.get("media_type") or "track"),
                }
            ]
        },
    )
    hass.services.async_register(
        "music_assistant",
        "search",
        lambda _call: {
            "tracks": [{"uri": "library://track/202", "name": "Giant Steps", "artists": [{"name": "Coltrane"}]}]
        },
    )
    hass.services.async_register(
        "media_player",
        "browse_media",
        lambda _call: {
            "title": "Blue Train",
            "children": [
                {"title": "1. Blue Train", "media_content_id": "library://track/101", "media_content_type": "track"}
            ],
        },
    )

    # 2) device_hello with updated manifest
    manifest = json.dumps(
        {
            "v": 2,
            "contract": 3,
            "board": "pocket_board",
            "w": 466,
            "h": 466,
            "shape": "circle",
            "display": 1,
            "stationary": 0,
            "sdk": MIN_FIRMWARE_SDK_REV,
            "beacon": {"uuid": "E2C56DB5-DFFB-48D2-B060-D0F5A71096E1", "major": 1, "minor": 2},
        }
    )
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_DEVICE_HELLO,
        {"contract": 3, "boot_id": "boot_abc", "manifest": manifest},
    )

    # 3) set_active_speaker & media_command (including container fallback!) & media_volume with number override
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ACTIVE_SPEAKER,
        {"target_device": coord.device_slug, "entity_id": "media_player.pocket_sendspin", "transfer_queue": True},
        blocking=True,
    )
    for cmd_extra in (
        {"command": "play"},
        {"command": "pause"},
        {"command": "next"},
        {"command": "previous"},
        {"command": "seek", "seek_position": 42.5},
        {"command": "shuffle", "enqueue": "true"},
        {"command": "repeat", "enqueue": "all"},
        {"command": "play_media", "media_id": "library://album/42", "media_type": "album"},
    ):
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_MEDIA_COMMAND,
            cmd_extra,
        )

    hass.states.async_set("number.avr_volume", "40", {"min": 0, "max": 100, "step": 5})
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_VOLUME_OVERRIDES] = {
        "media_player.pocket_sendspin": "number.avr_volume"
    }
    for vol_act in ("up", "down", "set", "mute"):
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_MEDIA_VOLUME,
            {"action": vol_act, "volume_level": 60},
        )

    # 4) music_browse & area_browse & area_action
    for browse_mode in ("speakers", "playlists", "albums", "artists", "tracks", "radio", "search"):
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_MUSIC_BROWSE,
            {"mode": browse_mode, "search": "Coltrane"},
        )

    hass.states.async_set("light.kitchen_island", "on", {"brightness": 200})
    ent_reg.async_register(
        er.RegistryEntry(entity_id="light.kitchen_island", platform="hue", area_id="kitchen")
    )
    for area_mode in ("areas", "home", "entities"):
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_AREA_BROWSE,
            {"mode": area_mode, "area_id": "kitchen"},
        )

    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_AREA_ACTION,
        {"entity_id": "light.kitchen_island", "action": "set_level", "level": 50},
    )

    # 5) remote_action (Android TV short + long_press, Apple TV InputAction.Hold >= 1.0s, and ADB fallback)
    hass.services.async_register(
        "androidtv",
        "adb_command",
        lambda call: calls_log.append(("androidtv", "adb_command", dict(call.data))),
    )
    ent_reg.async_register(
        er.RegistryEntry(entity_id="remote.shield_tv", platform="androidtv_remote", area_id="kitchen")
    )
    ent_reg.async_register(
        er.RegistryEntry(entity_id="remote.lounge_atv", platform="apple_tv", area_id="kitchen")
    )
    ent_reg.async_register(
        er.RegistryEntry(entity_id="media_player.bedroom_fire_tv", platform="firetv", area_id="kitchen")
    )
    hass.states.async_set("remote.shield_tv", "on", {"friendly_name": "Shield TV"})
    hass.states.async_set("remote.lounge_atv", "on", {"friendly_name": "Apple TV"})
    hass.states.async_set("media_player.bedroom_fire_tv", "on", {"friendly_name": "Fire TV"})
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_REMOTES_LIST] = [
        "remote.shield_tv",
        "remote.lounge_atv",
        "media_player.bedroom_fire_tv",
    ]
    for rem_act, rem_cmd in (
        ("command", "up"),
        ("command", "select"),
        ("long_press", "select"),
        ("toggle", "power"),
    ):
        await _sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_REMOTE_ACTION,
            {"slot": 1, "action": rem_act, "command": rem_cmd},
        )
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_REMOTE_ACTION,
        {"slot": 2, "action": "long_press", "command": "select"},
    )
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_REMOTE_ACTION,
        {"slot": 2, "action": "long_press", "command": "back"},
    )
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_REMOTE_ACTION,
        {"slot": 3, "action": "long_press", "command": "select"},
    )
    await hass.async_block_till_done()
    remote_send_calls = [d for dom, svc, d in calls_log if (dom, svc) == ("remote", "send_command")]
    assert {"entity_id": "remote.shield_tv", "command": "DPAD_CENTER"} in remote_send_calls
    assert {"entity_id": "remote.shield_tv", "command": "DPAD_CENTER", "hold_secs": 0.6} in remote_send_calls
    assert {"entity_id": "remote.lounge_atv", "command": "select", "hold_secs": 1.0} in remote_send_calls
    assert {"entity_id": "remote.lounge_atv", "command": "menu", "hold_secs": 1.0} in remote_send_calls
    adb_calls = [d for dom, svc, d in calls_log if (dom, svc) == ("androidtv", "adb_command")]
    assert {
        "entity_id": "media_player.bedroom_fire_tv",
        "command": "input keyevent --longpress 23",
    } in adb_calls

    # 6) calendar_fetch, calendar_create_event & calendar_delete_event
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
    hass.services.async_register(
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
    )
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_CALENDAR_FETCH,
        {
            "mode": "window",
            "start_date": "2026-11-01",
            "end_date": "2026-11-30",
            "days": 30,
        },
    )
    await _sys_obj.rpc_dispatcher.async_dispatch(
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
    await _sys_obj.rpc_dispatcher.async_dispatch(
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

    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_CALENDAR_DELETE_EVENT,
        {
            "calendar_entity": "calendar.work",
            "uid": "evt-1",
            "recurrence_id": "20261118T170000Z",
        },
    )
    assert deleted_events == [("evt-1", "20261118T170000Z", None)]

    # 7) notify & intercom_broadcast ('all', 'occupied_areas', 'person.alex', invalid media_url check)
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
        {"target_device": "occupied_areas", "title": "Dinner", "message": "Ready", "announce": True},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFY,
        {"target_device": "person.alex", "title": "Note", "message": "Package arrived"},
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

    # 8) doorbell_intercom (listen_start, listen_stop, talk_message)
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_CAMERA_ENTITIES] = ["camera.front"]
    hass.states.async_set("camera.front", "streaming", {"friendly_name": "Front"})
    hass.states.async_set("media_player.front_speaker", "idle", {"volume_level": 0.2})
    for db_act in ("listen_start", "set_noise_reduction", "talk_message", "listen_stop"):
        res_db = await _sys_obj.rpc_dispatcher.async_dispatch(
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
    assert await async_unload_entry(hass, entry) is True


@pytest.mark.asyncio
async def test_volume_supported_features_and_remote_fallback(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify HA 2026.11.2 VOLUME_SET/VOLUME_STEP/VOLUME_MUTE gating (webostv ARC, Spotify, remote fallback)."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    coord.active_area_id = "living_room"

    calls_log: list[tuple[str, str, dict[str, Any]]] = []
    for dom, svcs in (
        ("media_player", ("volume_set", "volume_up", "volume_down", "volume_mute")),
        ("remote", ("send_command",)),
    ):
        for s in svcs:
            hass.services.async_register(
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
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)
    tv_dev = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("androidtv_remote", "shield_lineout")},
        name="Living Room Shield",
        area_id="living_room",
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="media_player.shield_lineout",
            platform="androidtv_remote",
            device_id=tv_dev.id,
            area_id="living_room",
        )
    )
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id="remote.shield_lineout",
            platform="androidtv_remote",
            device_id=tv_dev.id,
            area_id="living_room",
        )
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

    await _sys_obj.rpc_dispatcher.async_dispatch(
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

    assert await async_unload_entry(hass, entry) is True
