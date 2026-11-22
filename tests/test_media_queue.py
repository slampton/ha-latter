"""Tests for Music Assistant active queue fetching, graceful fallback, and offset pagination."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.helpers import device_registry as dr
import pytest

from custom_components.latter.const import RPC_MUSIC_BROWSE
from custom_components.latter.media import browse as ma_browse
from custom_components.latter.protocol_codec import FIELD_SEP, RECORD_SEP
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


async def test_active_queue_fetches_player_queue_items_when_get_queue_items_is_int(
    hass: Any, setup_latter_hub: Any
) -> None:
    """`music_assistant.get_queue` returns `"items": 15` (int); `_browse_active_queue` must fetch real queue items."""
    entry, sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None

    pushed_slots: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        f"{coord.device_slug}_latter_set_slots",
        lambda call: pushed_slots.append(dict(call.data)),
    )

    fifteen_items = [
        {
            "queue_item_id": f"q_item_{idx}",
            "name": f"Track {idx}",
            "media_item": {
                "name": f"Track {idx}",
                "uri": f"library://track/{100 + idx}",
                "artists": [{"name": f"Artist {idx}"}],
            },
        }
        for idx in range(15)
    ]
    _ma_entry, mass = _seed_music_assistant(hass, queue_items=fifteen_items)
    assert mass is not None

    # Realistic MA 2.x get_queue payload where "items" is an integer count (15)!
    mock_service(
        hass,
        "music_assistant",
        "get_queue",
        lambda _call: {
            "media_player.ma_pocket": {
                "queue_id": "ma_queue_pocket",
                "items": 15,
                "current_index": 2,
                "current_item": fifteen_items[2],
                "next_item": fifteen_items[3],
            }
        },
        supports_response=SupportsResponse.ONLY,
    )

    slots = await ma_browse.async_browse_media_items(
        hass=hass,
        mode="active_queue",
        speaker="media_player.pocket_assistant_music",
        last_speaker="media_player.pocket_assistant_music",
        local_speaker="media_player.pocket_assistant_music",
    )
    assert len(slots) == 15
    assert mass.player_queues.fetch_calls == [("ma_queue_pocket", 50, 0)]
    assert slots[0] == {
        "name": "Track 0 — Artist 0",
        "id": "library://track/100",
        "type": "track",
        "queue_item_id": "q_item_0",
        "is_current": False,
        "active": False,
    }
    assert slots[2]["name"] == "Track 2 — Artist 2"
    assert slots[2]["queue_item_id"] == "q_item_2"
    assert slots[2]["is_current"] is True
    assert slots[2]["active"] is True
    assert sum(1 for s in slots if s["is_current"]) == 1

    # Verify 7-column latter_set_slots wire encoding via music_browse RPC
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MUSIC_BROWSE,
        {
            "req_id": 42,
            "mode": "active_queue",
            "page": 1,
            "page_size": 5,
        },
    )
    assert len(pushed_slots) == 1
    assert pushed_slots[0]["req_id"] == 42
    assert pushed_slots[0]["mode"] == "active_queue"
    assert pushed_slots[0]["page"] == 1
    assert pushed_slots[0]["total_pages"] == 3
    rows = pushed_slots[0]["slots"].split(RECORD_SEP)
    assert len(rows) == 5
    cols_0 = rows[0].split(FIELD_SEP)
    cols_2 = rows[2].split(FIELD_SEP)
    assert cols_0 == [
        "Track 0 — Artist 0",
        "library://track/100",
        "track",
        "0",
        "-1",
        "q_item_0",
        "0",
    ]
    assert cols_2 == [
        "Track 2 — Artist 2",
        "library://track/102",
        "track",
        "1",
        "-1",
        "q_item_2",
        "1",
    ]

    assert await hass.config_entries.async_unload(entry.entry_id) is True


@pytest.mark.asyncio
async def test_active_queue_graceful_fallback_and_offset_pagination(
    hass: Any, setup_latter_hub: Any
) -> None:
    """When `mass` runtime client is unreachable and `items` is an int, fallback returns current + next item."""
    entry, sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None

    ma_entry, _ = _seed_music_assistant(hass, with_runtime_mass=False)
    cur_item = {
        "queue_item_id": "qid_cur",
        "media_item": {
            "name": "Nutshell",
            "uri": "library://track/144",
            "artists": [{"name": "Alice In Chains"}],
        },
    }
    nxt_item = {
        "queue_item_id": "qid_next",
        "media_item": {
            "name": "I Stay Away",
            "uri": "library://track/145",
            "artists": [{"name": "Alice In Chains"}],
        },
    }
    mock_service(
        hass,
        "music_assistant",
        "get_queue",
        lambda _call: {
            "media_player.ma_pocket": {
                "queue_id": "ma_queue_pocket",
                "items": 15,  # int! Must not short-circuit fallback to []
                "current_item": cur_item,
                "next_item": nxt_item,
            }
        },
        supports_response=SupportsResponse.ONLY,
    )

    fallback_slots = await ma_browse.async_browse_media_items(
        hass=hass,
        mode="active_queue",
        speaker="media_player.pocket_assistant_music",
        last_speaker="media_player.pocket_assistant_music",
        local_speaker="media_player.pocket_assistant_music",
    )
    assert [s["name"] for s in fallback_slots] == [
        "Nutshell — Alice In Chains",
        "I Stay Away — Alice In Chains",
    ]
    assert [s["queue_item_id"] for s in fallback_slots] == ["qid_cur", "qid_next"]
    assert [s["is_current"] for s in fallback_slots] == [True, False]

    # Attach live mass client with 75 items and verify page 12 (offset=50) pagination
    seventy_five = [
        {
            "queue_item_id": f"q75_{i}",
            "media_item": {
                "name": f"Song {i}",
                "uri": f"library://track/{500 + i}",
                "artists": [{"name": "Band"}],
            },
        }
        for i in range(75)
    ]
    fetch_log: list[tuple[str, int, int]] = []

    async def _fetch_75(
        qid: str, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        fetch_log.append((qid, limit, offset))
        return seventy_five[offset : offset + limit]

    ma_entry.runtime_data = SimpleNamespace(
        mass=SimpleNamespace(
            player_queues=SimpleNamespace(fetch_player_queue_items=_fetch_75)
        )
    )
    mock_service(
        hass,
        "music_assistant",
        "get_queue",
        lambda _call: {
            "media_player.ma_pocket": {
                "queue_id": "ma_queue_pocket",
                "items": 75,
                "current_item": seventy_five[0],
            }
        },
        supports_response=SupportsResponse.ONLY,
    )
    pushed_p12: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        f"{coord.device_slug}_latter_set_slots",
        lambda call: pushed_p12.append(dict(call.data)),
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MUSIC_BROWSE,
        {
            "req_id": 99,
            "mode": "active_queue",
            "page": 12,
            "page_size": 5,
        },
    )
    assert fetch_log == [("ma_queue_pocket", 50, 50)]
    assert pushed_p12[0]["page"] == 12
    assert pushed_p12[0]["total_pages"] == 15
    p12_names = [
        r.split(FIELD_SEP)[0] for r in pushed_p12[0]["slots"].split(RECORD_SEP)
    ]
    assert p12_names == [f"Song {i} — Band" for i in range(55, 60)]

    assert await hass.config_entries.async_unload(entry.entry_id) is True
