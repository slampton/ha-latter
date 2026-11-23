"""Tests for 21-field active_media Protocol v3 payload and mute/shuffle/repeat/favorite commands."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.helpers import device_registry as dr

from custom_components.latter.const import (
    CONF_VOLUME_OVERRIDES,
    RPC_MEDIA_COMMAND,
)
from custom_components.latter.hub_registry import get_global_config
from custom_components.latter.media.state_payload import (
    MEDIA_CAP_FAVORITE,
    MEDIA_CAP_GROUPING,
    MEDIA_CAP_MUSIC_ASSISTANT,
    MEDIA_CAP_NEXT_TRACK,
    MEDIA_CAP_PAUSE,
    MEDIA_CAP_PREVIOUS_TRACK,
    MEDIA_CAP_REPEAT_SET,
    MEDIA_CAP_SEEK,
    MEDIA_CAP_SHUFFLE_SET,
    MEDIA_CAP_VOLUME_MUTE,
    MEDIA_CAP_VOLUME_SET,
    build_active_media_payload,
)
from custom_components.latter.protocol_codec import FIELD_SEP
from custom_components.latter.protocol_specs import PROTOCOL_V3_DATA
from tests.helpers import (
    add_mock_entry,
    mock_service,
    register_device,
    register_entity,
)


def _seed_music_assistant(
    hass: Any,
    *,
    local_speaker: str = "media_player.pocket_assistant_music",
    ma_entity: str = "media_player.ma_pocket",
    queue_id: str = "ma_queue_pocket",
    mac: str = "aa:bb:cc:dd:ee:01",
    with_runtime_mass: bool = True,
    queue_items: list[dict[str, Any]] | None = None,
    supported_features: int = (
        1 | 2 | 4 | 8 | 16 | 32 | 1024 | 16384 | 32768 | 262144 | 524288
    ),
) -> tuple[Any, SimpleNamespace | None]:
    """Register a loaded Music Assistant config entry, linked entity, and optional `mass` runtime client."""
    ma_entry = add_mock_entry(
        hass,
        domain="music_assistant",
        title="Music Assistant",
        entry_id="entry_ma_test",
        data={},
    )
    if hasattr(ma_entry, "mock_state"):
        ma_entry.mock_state(hass, ConfigEntryState.LOADED)

    mass_client: SimpleNamespace | None = None
    if with_runtime_mass:
        q_list = list(queue_items or [])
        fetch_calls: list[tuple[str, int, int]] = []
        play_index_calls: list[tuple[str, str]] = []
        move_item_calls: list[tuple[str, str, int]] = []
        delete_item_calls: list[tuple[str, Any]] = []
        fav_add_calls: list[Any] = []
        fav_remove_calls: list[tuple[str, Any]] = []

        async def _fetch_player_queue_items(
            qid: str, limit: int = 50, offset: int = 0
        ) -> list[dict[str, Any]]:
            fetch_calls.append((qid, limit, offset))
            return q_list[offset : offset + limit]

        async def _play_index(qid: str, index_or_id: str) -> None:
            play_index_calls.append((qid, index_or_id))

        async def _move_item(qid: str, queue_item_id: str, pos_shift: int = 1) -> None:
            move_item_calls.append((qid, queue_item_id, pos_shift))

        async def _delete_item(qid: str, item_id_or_index: Any) -> None:
            delete_item_calls.append((qid, item_id_or_index))

        async def _add_item_to_favorites(item: Any) -> None:
            fav_add_calls.append(item)

        async def _remove_item_from_favorites(
            media_type: Any, library_item_id: Any
        ) -> None:
            fav_remove_calls.append((str(media_type), library_item_id))

        async def _get_item_by_uri(uri: str) -> dict[str, Any]:
            return {
                "uri": uri,
                "item_id": "843",
                "media_type": "track",
                "favorite": False,
                "name": "Would?",
            }

        queue_state_obj = SimpleNamespace(
            queue_id=queue_id,
            items=len(q_list),
            current_index=1,
            shuffle_enabled=False,
            repeat_mode=SimpleNamespace(value="off"),
            current_item=(
                q_list[1] if len(q_list) > 1 else (q_list[0] if q_list else None)
            ),
        )
        player_queues = SimpleNamespace(
            fetch_player_queue_items=_fetch_player_queue_items,
            play_index=_play_index,
            move_item=_move_item,
            delete_item=_delete_item,
            get=lambda qid: queue_state_obj if qid == queue_id else None,
            fetch_calls=fetch_calls,
            play_index_calls=play_index_calls,
            move_item_calls=move_item_calls,
            delete_item_calls=delete_item_calls,
            queue_state_obj=queue_state_obj,
        )
        music_ctrl = SimpleNamespace(
            add_item_to_favorites=_add_item_to_favorites,
            remove_item_from_favorites=_remove_item_from_favorites,
            get_item_by_uri=_get_item_by_uri,
            fav_add_calls=fav_add_calls,
            fav_remove_calls=fav_remove_calls,
        )
        mass_client = SimpleNamespace(
            player_queues=player_queues,
            music=music_ctrl,
            players=SimpleNamespace(get=lambda _uid: None),
        )
        ma_entry.runtime_data = SimpleNamespace(mass=mass_client)

    ma_dev = register_device(
        hass,
        config_entry_id=ma_entry.entry_id,
        entry_domain="music_assistant",
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        identifiers={("music_assistant", queue_id)},
        name="Pocket Assistant MA",
        manufacturer="Latter",
    )
    register_entity(
        hass,
        ma_entity,
        platform="music_assistant",
        device_id=ma_dev.id,
        config_entry=ma_entry,
        unique_id=queue_id,
        original_name="Pocket Assistant MA",
    )
    hass.states.async_set(
        ma_entity,
        "playing",
        {
            "friendly_name": "Pocket Assistant MA",
            "mass_player_type": "player",
            "active_queue": queue_id,
            "media_title": "Would?",
            "media_artist": "Alice In Chains",
            "media_album_name": "Dirt",
            "media_content_id": "library://track/843",
            "media_content_type": "music",
            "media_duration": 208,
            "media_position": 42,
            "volume_level": 0.65,
            "is_volume_muted": False,
            "shuffle": False,
            "repeat": "off",
            "supported_features": supported_features,
        },
    )
    _ = local_speaker
    return ma_entry, mass_client


async def test_active_media_21_fields_and_mute_shuffle_repeat_favorite_commands(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify `active_media` 21-field sync (`shuffle`, `repeat`, `muted`, `favorite`, `queue_count`, `media_caps`) and toggles."""
    entry, sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None
    get_global_config(hass)[
        CONF_VOLUME_OVERRIDES
    ] = [
        {
            "speaker": "media_player.pocket_assistant_music",
            "target": "media_player.living_room_avr",
        }
    ]

    q_items = [
        {
            "queue_item_id": f"qi_{i}",
            "media_item": {
                "name": "Would?" if i == 1 else f"Song {i}",
                "uri": "library://track/843" if i == 1 else f"library://track/{i}",
                "favorite": False,
            },
        }
        for i in range(15)
    ]
    _ma_entry, mass = _seed_music_assistant(hass, queue_items=q_items)
    assert mass is not None

    hass.states.async_set(
        "media_player.living_room_avr",
        "on",
        {
            "volume_level": 0.40,
            "is_volume_muted": True,
            "supported_features": 4 | 8,  # VOLUME_SET | VOLUME_MUTE
        },
    )

    mute_calls: list[dict[str, Any]] = []
    shuffle_calls: list[dict[str, Any]] = []
    repeat_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "media_player",
        "volume_mute",
        lambda call: mute_calls.append(dict(call.data)),
    )
    mock_service(
        hass,
        "media_player",
        "shuffle_set",
        lambda call: shuffle_calls.append(dict(call.data)),
    )
    mock_service(
        hass,
        "media_player",
        "repeat_set",
        lambda call: repeat_calls.append(dict(call.data)),
    )

    await hass.async_block_till_done()
    coord.cached_media_payload = None
    state_str, attrs = build_active_media_payload(coord)
    assert state_str == "playing"
    assert attrs["muted"] is True
    assert attrs["shuffle"] is False
    assert attrs["repeat"] == "off"
    assert attrs["favorite"] is False
    assert attrs["queue_count"] == 15
    expected_caps = (
        MEDIA_CAP_PAUSE
        | MEDIA_CAP_SEEK
        | MEDIA_CAP_VOLUME_SET
        | MEDIA_CAP_VOLUME_MUTE
        | MEDIA_CAP_PREVIOUS_TRACK
        | MEDIA_CAP_NEXT_TRACK
        | MEDIA_CAP_SHUFFLE_SET
        | MEDIA_CAP_REPEAT_SET
        | MEDIA_CAP_GROUPING
        | MEDIA_CAP_MUSIC_ASSISTANT
        | MEDIA_CAP_FAVORITE
    )
    assert attrs["media_caps"] == expected_caps

    wire_fields = attrs["payload"].split(FIELD_SEP)
    assert (
        len(wire_fields)
        == 3 + len(PROTOCOL_V3_DATA["domains"]["active_media"]["fields"])
        == 24
    )
    assert wire_fields[17] == "0"  # shuffle
    assert wire_fields[18] == "off"  # repeat
    assert wire_fields[19] == "1"  # muted (from volume_override AVR!)
    assert wire_fields[20] == "0"  # favorite
    assert wire_fields[21] == "15"  # queue_count
    assert wire_fields[22] == str(expected_caps)  # media_caps
    assert wire_fields[23] in ("0", "1")  # is_default_speaker

    # 1. mute_toggle targets the configured volume_override entity (living_room_avr)
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {"command": "mute_toggle"},
    )
    assert mute_calls == [
        {"entity_id": "media_player.living_room_avr", "is_volume_muted": False}
    ]

    # 2. shuffle_toggle toggles False -> True on MA player
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {"command": "shuffle_toggle"},
    )
    assert shuffle_calls == [{"entity_id": "media_player.ma_pocket", "shuffle": True}]

    # 3. repeat_cycle steps off -> all -> one -> off
    for cur_rep, next_rep in (("off", "all"), ("all", "one"), ("one", "off")):
        repeat_calls.clear()
        mass.player_queues.queue_state_obj.repeat_mode = SimpleNamespace(value=cur_rep)
        hass.states.async_set(
            "media_player.ma_pocket",
            "playing",
            {
                **dict(hass.states.get("media_player.ma_pocket").attributes),
                "repeat": cur_rep,
            },
        )
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_MEDIA_COMMAND,
            {"command": "repeat_cycle"},
        )
        assert repeat_calls == [
            {"entity_id": "media_player.ma_pocket", "repeat": next_rep}
        ]

    # 3b. Dynamic / radio mode queue locks shuffle & repeat: mask capability bits and ignore toggles
    shuffle_calls.clear()
    repeat_calls.clear()
    mass.player_queues.queue_state_obj.is_dynamic = True
    mass.player_queues.queue_state_obj.shuffle_enabled = True
    mass.player_queues.queue_state_obj.repeat_mode = SimpleNamespace(value="off")
    coord.cached_media_payload = None
    _dyn_st, dyn_attrs = build_active_media_payload(coord)
    assert dyn_attrs["media_caps"] == (
        expected_caps & ~(MEDIA_CAP_SHUFFLE_SET | MEDIA_CAP_REPEAT_SET)
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {"command": "shuffle_toggle"},
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {"command": "repeat_cycle"},
    )
    assert shuffle_calls == []
    assert repeat_calls == []
    mass.player_queues.queue_state_obj.is_dynamic = False
    mass.player_queues.queue_state_obj.shuffle_enabled = False
    coord.cached_media_payload = None
    _restored_st, restored_attrs = build_active_media_payload(coord)
    assert restored_attrs["media_caps"] == expected_caps

    # 4. favorite_toggle with media_id="" and plain non-URI media_id="Track Title" resolves real URI
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {"command": "favorite_toggle", "media_id": ""},
    )
    assert mass.music.fav_add_calls == ["library://track/843"]
    coord.cached_media_payload = None
    _st2, attrs2 = build_active_media_payload(coord)
    assert attrs2["favorite"] is True

    # Passing a plain track title (non-URI without "://") must NOT pass raw title to add/remove_item_to_favorites
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {
            "command": "favorite_toggle",
            "media_id": "Would?",
        },
    )
    assert mass.music.fav_remove_calls == [("track", "843")]
    coord.cached_media_payload = None
    _st3, attrs3 = build_active_media_payload(coord)
    assert attrs3["favorite"] is False

    # When player has no URI or title, plain media_id="Track Title" acts as title fallback via async_lookup_ma_track_uri
    mass.music.fav_add_calls.clear()
    mass.player_queues.queue_state_obj.current_item = None
    coord.last_media_uri = ""
    coord.last_media_title = ""
    hass.states.async_set(
        "media_player.ma_pocket",
        "idle",
        {
            "friendly_name": "Pocket Assistant MA",
            "mass_player_type": "player",
            "active_queue": "ma_queue_pocket",
        },
    )
    mock_service(
        hass,
        "music_assistant",
        "get_library",
        lambda _call: {
            "items": [
                {
                    "name": "Track Title",
                    "uri": "library://track/901",
                    "artists": [{"name": "Alice In Chains"}],
                }
            ]
        },
        supports_response=SupportsResponse.ONLY,
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {
            "command": "favorite_toggle",
            "media_id": "Track Title",
        },
    )
    assert mass.music.fav_add_calls == ["library://track/901"]

    assert await hass.config_entries.async_unload(entry.entry_id) is True
