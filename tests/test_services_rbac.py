"""Integration tests for Latter domain services, RBAC admin enforcement, Media/MA linking, Browse LRU cache, and Reset."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.core import Context, SupportsResponse
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import device_registry as dr, issue_registry as ir
import pytest

from custom_components.latter.const import (
    CONF_PINNED_ITEMS,
    CONF_SECURITY_PIN_HASH,
    CONF_SECURITY_PIN_POLICY,
    CONF_VOLUME_OVERRIDES,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    MIN_FIRMWARE_SDK_REV,
    PUBLIC_SERVICES,
    RPC_AREA_ACTION,
    RPC_AREA_BROWSE,
    RPC_DEVICE_HELLO,
    RPC_MEDIA_COMMAND,
    RPC_MEDIA_VOLUME,
    RPC_MUSIC_BROWSE,
    RPC_SAVE_CUSTOM_COLOR,
    RPC_SHORTCUT_ACTION,
    SERVICE_RESET_DEVICE,
    SERVICE_SET_ACTIVE_AREA,
    SERVICE_SET_ACTIVE_SPEAKER,
)
from custom_components.latter.media import browse as _browse_mod, lyrics as _lyrics_mod
from custom_components.latter.media.browse import (
    MAX_BROWSE_CACHE_ENTRIES,
    clear_browse_cache,
)
from custom_components.latter.media.linking import (
    clear_ma_counterpart_cache,
    resolve_ma_counterpart_entity,
)
from custom_components.latter.protocol_policy import hash_security_pin, wrap_pin_code
from tests.helpers import (
    add_mock_entry,
    mock_service,
    register_device,
    register_entity,
)


@pytest.mark.asyncio
async def test_services_rbac_and_validation_errors(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify non-admin HA users are blocked on mutating config services while admin & internal contexts succeed."""
    entry, sys_obj, coord = await setup_latter_hub(hass)

    # First user created in Home Assistant Auth becomes owner (`is_owner=True`),
    # so create `admin_user` first and `regular_user` second (`is_admin == False`).
    admin_user = await hass.auth.async_create_user(
        "Admin User", group_ids=["system-admin"]
    )
    regular_user = await hass.auth.async_create_user(
        "Regular User", group_ids=["system-users"]
    )
    assert regular_user.is_admin is False
    non_admin_ctx = Context(user_id=regular_user.id)
    admin_ctx = Context(user_id=admin_user.id)

    # Only the 5 public actions are registered on hass.services
    assert set(hass.services.async_services_for_domain(DOMAIN).keys()) == set(
        PUBLIC_SERVICES
    )

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_DEVICE,
            {
                "target_device": coord.device_slug,
                "device_settings": False,
                "latter_options": True,
            },
            blocking=True,
            context=non_admin_ctx,
        )

    # Bound RPC save_custom_color succeeds & validation errors carry translation_domain + translation_key
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_SAVE_CUSTOM_COLOR,
        {"hex_color": "33AAFF", "name": "Ocean"},
    )
    assert coord.device_data.get("device_custom_color") == "#33AAFF"

    with pytest.raises(ServiceValidationError) as exc_hex:
        await sys_obj.rpc_dispatcher.async_dispatch(
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

    mock_service(hass, "script", "turn_on", _rec_shortcut_svc)
    mock_service(hass, "lock", "unlock", _rec_shortcut_svc)
    hass.states.async_set("script.baby_help", "off", {"friendly_name": "Baby Help"})
    hass.states.async_set("lock.front_door", "locked", {"friendly_name": "Front Door"})

    with pytest.raises(ServiceValidationError) as exc_unconf:
        await sys_obj.rpc_dispatcher.async_dispatch(
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
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_SHORTCUT_ACTION,
        {"entity_id": "script.baby_help", "action": "turn_on"},
    )
    assert ("script", "turn_on") in {(d, s) for d, s, _ in dispatched_shortcuts}

    # Wrong verb on configured entity is still rejected by allowlist
    with pytest.raises(ServiceValidationError) as exc_wrong_verb:
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_SHORTCUT_ACTION,
            {"entity_id": "script.baby_help", "action": "turn_off"},
        )
    assert exc_wrong_verb.value.translation_key == "shortcut_not_configured"

    # Configured perimeter shortcut requires wrapped PIN when policy == require_pin
    with pytest.raises(ServiceValidationError) as exc_pin_req:
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_SHORTCUT_ACTION,
            {"entity_id": "lock.front_door", "action": "unlock"},
        )
    assert exc_pin_req.value.translation_key == "security_pin_required"

    wrapped_sc_pin = wrap_pin_code(
        coord.pin_session_key_id,
        coord.pin_session_key_bytes,
        1,
        "lock.front_door",
        "unlock",
        "4826",
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
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
        {
            "target_device": coord.device_slug,
            "device_settings": True,
            "latter_options": True,
        },
        blocking=True,
        context=admin_ctx,
    )
    assert await hass.config_entries.async_unload(entry.entry_id) is True


@pytest.mark.asyncio
async def test_all_domain_services_ma_link_and_browse_lru(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise device_hello, media/MA container fallback, volume override, music_browse, and area_browse/area_action."""
    # Verify bounded 64-entry LRU cache on browse lyrics/bio
    clear_browse_cache()
    assert MAX_BROWSE_CACHE_ENTRIES == 64
    cache_dict = (
        vars(_lyrics_mod).get("_BROWSE_LYRICS_BIO_CACHE")
        if "_BROWSE_LYRICS_BIO_CACHE" in vars(_lyrics_mod)
        else vars(_browse_mod)["_BROWSE_LYRICS_BIO_CACHE"]
    )
    cache_put = (
        vars(_lyrics_mod).get("_cache_put")
        or vars(_lyrics_mod).get("cache_put")
        or vars(_browse_mod).get("_cache_put")
        or vars(_browse_mod)["cache_put"]
    )
    for i in range(80):
        cache_put(f"song_{i}", {"lines": [f"Line {i}"]})
    assert len(cache_dict) == 64
    assert "song_0" not in cache_dict
    assert "song_79" in cache_dict

    entry, sys_obj, coord = await setup_latter_hub(hass)
    issue_reg = ir.async_get(hass)

    ma_entry = add_mock_entry(
        hass,
        domain="music_assistant",
        title="Music Assistant",
        entry_id="ma_entry",
        data={},
    )

    # 1) Music Assistant counterpart resolution: unlinked raises Repair; MAC-linked resolves cleanly!
    ma_unlinked_dev = register_device(
        hass,
        config_entry_id=ma_entry.entry_id,
        entry_domain="music_assistant",
        identifiers={("music_assistant", "other_spk")},
        name="Pocket Assistant",
        manufacturer="Latter",
    )
    register_entity(
        hass,
        "media_player.pocket_assistant_ma_wrong",
        platform="music_assistant",
        device_id=ma_unlinked_dev.id,
        config_entry=ma_entry,
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
    ma_true_dev = register_device(
        hass,
        config_entry_id=ma_entry.entry_id,
        entry_domain="music_assistant",
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:01")},
        identifiers={("music_assistant", "aa:bb:cc:dd:ee:01")},
        name="Pocket Sendspin",
        manufacturer="Latter",
    )
    register_entity(
        hass,
        "media_player.pocket_sendspin",
        platform="music_assistant",
        device_id=ma_true_dev.id,
        config_entry=ma_entry,
        area_id="living_room",
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

    # Register service handlers for media, MA, number
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
        "number": ("set_value",),
    }.items():
        for s in svcs:
            mock_service(
                hass,
                dom,
                s,
                lambda call, d=dom, sv=s: calls_log.append((d, sv, dict(call.data))),
            )

    def _ma_play_media(call: Any) -> None:
        calls_log.append(("music_assistant", "play_media", dict(call.data)))
        if call.data.get("media_id") == "library://album/42":
            raise RuntimeError("Container play failed")

    mock_service(hass, "music_assistant", "play_media", _ma_play_media)
    mock_service(
        hass,
        "music_assistant",
        "transfer_queue",
        lambda call: calls_log.append(
            ("music_assistant", "transfer_queue", dict(call.data))
        ),
    )
    mock_service(
        hass,
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
        supports_response=SupportsResponse.ONLY,
    )
    mock_service(
        hass,
        "music_assistant",
        "search",
        lambda _call: {
            "tracks": [
                {
                    "uri": "library://track/202",
                    "name": "Giant Steps",
                    "artists": [{"name": "Coltrane"}],
                }
            ]
        },
        supports_response=SupportsResponse.OPTIONAL,
    )
    mock_service(
        hass,
        "media_player",
        "browse_media",
        lambda _call: {
            "title": "Blue Train",
            "children": [
                {
                    "title": "1. Blue Train",
                    "media_content_id": "library://track/101",
                    "media_content_type": "track",
                }
            ],
        },
        supports_response=SupportsResponse.ONLY,
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
            "beacon": {
                "uuid": "E2C56DB5-DFFB-48D2-B060-D0F5A71096E1",
                "major": 1,
                "minor": 2,
            },
        }
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_DEVICE_HELLO,
        {"contract": 3, "boot_id": "boot_abc", "manifest": manifest},
    )

    # 3) set_active_speaker & media_command (including container fallback!) & media_volume with number override
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ACTIVE_SPEAKER,
        {
            "target_device": coord.device_slug,
            "entity_id": "media_player.pocket_sendspin",
            "transfer_queue": True,
        },
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
        {
            "command": "play_media",
            "media_id": "library://album/42",
            "media_type": "album",
        },
    ):
        await sys_obj.rpc_dispatcher.async_dispatch(coord, RPC_MEDIA_COMMAND, cmd_extra)
    await hass.async_block_till_done()

    hass.states.async_set("number.avr_volume", "40", {"min": 0, "max": 100, "step": 5})
    hass.data[DOMAIN][DATA_GLOBAL_CONFIG][CONF_VOLUME_OVERRIDES] = [
        {"speaker": coord.active_speaker, "target": "number.avr_volume"}
    ]
    for vol_act in ("up", "down", "set", "mute"):
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_MEDIA_VOLUME,
            {"action": vol_act, "volume_level": 60},
        )
    await hass.async_block_till_done()
    assert ("number", "set_value") in {(d, s) for d, s, _ in calls_log}

    # 4) music_browse & area_browse & area_action
    for browse_mode in (
        "speakers",
        "playlists",
        "albums",
        "artists",
        "tracks",
        "radio",
        "search",
    ):
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_MUSIC_BROWSE,
            {"mode": browse_mode, "search": "Coltrane"},
        )
    await hass.async_block_till_done()

    register_entity(hass, "light.kitchen_island", platform="hue", area_id="kitchen")
    hass.states.async_set("light.kitchen_island", "on", {"brightness": 200})
    for area_mode in ("areas", "home", "entities"):
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_AREA_BROWSE,
            {"mode": area_mode, "area_id": "kitchen"},
        )
    await hass.async_block_till_done()

    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_AREA_ACTION,
        {"entity_id": "light.kitchen_island", "action": "set_level", "level": 50},
    )
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id) is True
