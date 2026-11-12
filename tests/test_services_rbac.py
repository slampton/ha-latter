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
from custom_components.latter.const import (
    CONF_CAMERA_ENTITIES,
    CONF_REMOTES_LIST,
    CONF_VOLUME_OVERRIDES,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    MIN_FIRMWARE_SDK_REV,
    SERVICE_AREA_ACTION,
    SERVICE_AREA_BROWSE,
    SERVICE_CALENDAR_CREATE_EVENT,
    SERVICE_CALENDAR_FETCH,
    SERVICE_DEVICE_HELLO,
    SERVICE_DOORBELL_INTERCOM,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_MEDIA_COMMAND,
    SERVICE_MEDIA_VOLUME,
    SERVICE_MUSIC_BROWSE,
    SERVICE_NOTIFY,
    SERVICE_REMOTE_ACTION,
    SERVICE_RESET_DEVICE,
    SERVICE_SAVE_CUSTOM_COLOR,
    SERVICE_SET_ACTIVE_AREA,
    SERVICE_SET_ACTIVE_SPEAKER,
    SERVICE_SET_DOCK_APPS,
)
from custom_components.latter.media import (
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


@pytest.mark.asyncio
async def test_services_rbac_and_validation_errors(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify non-admin HA users are blocked on mutating config services while admin & internal contexts succeed."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)

    non_admin_ctx = Context(user_id="regular_user")
    admin_ctx = Context(user_id="admin_user")

    for svc_name, payload in (
        (SERVICE_SAVE_CUSTOM_COLOR, {"target_device": coord.device_slug, "hex_color": "#112233"}),
        (SERVICE_SET_DOCK_APPS, {"target_device": coord.device_slug, "dock_apps": "music,alarm,area,remote"}),
        (SERVICE_RESET_DEVICE, {"target_device": coord.device_slug, "device_settings": False, "latter_options": True}),
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN, svc_name, payload, blocking=True, context=non_admin_ctx
            )

    # Admin user succeeds & validation errors carry translation_domain + translation_key
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SAVE_CUSTOM_COLOR,
        {"target_device": coord.device_slug, "hex_color": "33AAFF", "name": "Ocean"},
        blocking=True,
        context=admin_ctx,
    )
    assert coord.device_data.get("device_custom_color") == "#33AAFF"

    with pytest.raises(ServiceValidationError) as exc_hex:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SAVE_CUSTOM_COLOR,
            {"target_device": coord.device_slug, "hex_color": "#ZZZZZZ"},
            blocking=True,
            context=admin_ctx,
        )
    assert exc_hex.value.translation_domain == DOMAIN
    assert exc_hex.value.translation_key == "invalid_hex_color"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_DOCK_APPS,
        {"target_device": coord.device_slug, "dock_apps": "music,alarm,area,remote,games"},
        blocking=True,
        context=admin_ctx,
    )
    assert "games" in coord.dock_apps_csv

    with pytest.raises(ServiceValidationError) as exc_dock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_DOCK_APPS,
            {"target_device": coord.device_slug, "dock_apps": "not_an_app"},
            blocking=True,
            context=admin_ctx,
        )
    assert exc_dock.value.translation_key == "invalid_dock_apps"

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
    await hass.services.async_call(
        DOMAIN,
        SERVICE_DEVICE_HELLO,
        {"target_device": coord.device_slug, "contract": 3, "boot_id": "boot_abc", "manifest": manifest},
        blocking=True,
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
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MEDIA_COMMAND,
            {"target_device": coord.device_slug, **cmd_extra},
            blocking=True,
        )

    hass.states.async_set("number.avr_volume", "40", {"min": 0, "max": 100, "step": 5})
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_VOLUME_OVERRIDES] = {
        "media_player.pocket_sendspin": "number.avr_volume"
    }
    for vol_act in ("up", "down", "set", "mute"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MEDIA_VOLUME,
            {"target_device": coord.device_slug, "action": vol_act, "volume_level": 60},
            blocking=True,
        )

    # 4) music_browse & area_browse & area_action
    for browse_mode in ("speakers", "playlists", "albums", "artists", "tracks", "radio", "search"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MUSIC_BROWSE,
            {"target_device": coord.device_slug, "mode": browse_mode, "search": "Coltrane"},
            blocking=True,
        )

    hass.states.async_set("light.kitchen_island", "on", {"brightness": 200})
    ent_reg.async_register(
        er.RegistryEntry(entity_id="light.kitchen_island", platform="hue", area_id="kitchen")
    )
    for area_mode in ("areas", "home", "entities"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_AREA_BROWSE,
            {"target_device": coord.device_slug, "mode": area_mode, "area_id": "kitchen"},
            blocking=True,
        )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_AREA_ACTION,
        {"target_device": coord.device_slug, "entity_id": "light.kitchen_island", "action": "set_level", "level": 50},
        blocking=True,
    )

    # 5) remote_action (Android TV nav + power toggle)
    ent_reg.async_register(
        er.RegistryEntry(entity_id="remote.shield_tv", platform="androidtv_remote", area_id="kitchen")
    )
    hass.states.async_set("remote.shield_tv", "on", {"friendly_name": "Shield TV"})
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_REMOTES_LIST] = ["remote.shield_tv"]
    for rem_act, rem_cmd in (("command", "up"), ("command", "select"), ("toggle", "power")):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOTE_ACTION,
            {"target_device": coord.device_slug, "slot": 1, "action": rem_act, "command": rem_cmd},
            blocking=True,
        )

    # 6) calendar_fetch & calendar_create_event
    hass.states.async_set("calendar.work", "off", {"friendly_name": "Work"})
    hass.services.async_register("calendar", "get_events", lambda _c: {"calendar.work": {"events": []}})
    await hass.services.async_call(
        DOMAIN, SERVICE_CALENDAR_FETCH, {"target_device": coord.device_slug, "days": 30}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_CALENDAR_CREATE_EVENT,
        {"target_device": coord.device_slug, "summary": "Standup", "in_minutes": 10, "duration_minutes": 20},
        blocking=True,
    )

    # 7) notify & intercom_broadcast ('all', 'occupied_areas', 'person.sean', invalid media_url check)
    fabric = get_ble_fabric(hass)
    assert coord._ble_tracker is not None
    coord._ble_tracker.current_area_id = "living_room"
    coord._ble_tracker.is_away = False
    coord.active_area_id = "living_room"
    fabric.notify_occupancy_listeners()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFY,
        {"target_device": "occupied_areas", "title": "Dinner", "message": "Ready", "announce": True},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFY,
        {"target_device": "person.sean", "title": "Note", "message": "Package arrived"},
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
    hass.states.async_set("tts.piper", "unknown", {})
    for db_act in ("listen_start", "set_noise_reduction", "talk_message", "listen_stop"):
        res_db = await hass.services.async_call(
            DOMAIN,
            SERVICE_DOORBELL_INTERCOM,
            {
                "target_device": coord.device_slug,
                "action": db_act,
                "camera_entity": "camera.front",
                "noise_reduction": "light",
                "message": "Leave it on the mat",
            },
            blocking=True,
            return_response=True,
        )
        assert res_db["status"] == "ok"

    assert ("remote", "send_command") in {(d, s) for d, s, _ in calls_log}
    assert ("calendar", "create_event") in {(d, s) for d, s, _ in calls_log}
    assert await async_unload_entry(hass, entry) is True
