"""Tests for LRC lyrics parsing, local/MA lyrics fetch & chunk push, unwrapped bio, and 120-char browse slots."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.helpers import device_registry as dr
import pytest

from custom_components.latter.const import RPC_MUSIC_BROWSE
from custom_components.latter.media import browse as ma_browse, lyrics as ma_lyrics
from custom_components.latter.protocol_codec import FIELD_SEP, RECORD_SEP
from custom_components.latter.services.rpc_slots import async_push_browse_slots
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


def test_parse_lrc_lyrics_synced_multi_tag_and_plain_unwrapped() -> None:
    """LRC parser handles `[mm:ss.xx]`, `[mm:ss.xxx]`, `[mm:ss]`, multi-tag lines, 128-line cap, and unwrapped plain text."""
    raw_lrc = (
        "[ti:Would?]\n"
        "[ar:Alice In Chains]\n"
        "[00:12.00][00:45.50]Into the flood again\n"
        "[00:05]Know me broken by my master\n"
        "[00:18.250]Same old trip <00:19.10>it was back then\n"
        "[00:22.00]   \n"
        "[00:24.00]♪\n"
    )
    synced, lines = ma_lyrics.parse_lrc_lyrics(raw_lrc)
    assert synced is True
    assert lines == [
        {"t_ms": 5000, "text": "Know me broken by my master"},
        {"t_ms": 12000, "text": "Into the flood again"},
        {"t_ms": 18250, "text": "Same old trip it was back then"},
        {"t_ms": 45500, "text": "Into the flood again"},
    ]

    # Cap at 128 lines
    many_lrc = "\n".join(
        f"[{i // 60:02d}:{i % 60:02d}.00]Line {i}" for i in range(160)
    )
    synced_many, lines_many = ma_lyrics.parse_lrc_lyrics(many_lrc)
    assert synced_many is True
    assert len(lines_many) == 128
    assert lines_many[-1] == {"t_ms": 127000, "text": "Line 127"}

    # Plain lyrics: synced=False, t_ms=-1, NO width=32 hard wrapping!
    long_line = "So I made a big mistake, try to see once my way — this line is well over thirty-two characters wide"
    plain_synced, plain_lines = ma_lyrics.parse_lrc_lyrics(
        f"{long_line}\nSecond logical line"
    )
    assert plain_synced is False
    assert plain_lines == [
        {"t_ms": -1, "text": long_line},
        {"t_ms": -1, "text": "Second logical line"},
    ]

    # _extract_meta_strings prefers lrc_lyrics over plain lyrics
    extract_fn = (
        vars(ma_lyrics).get("extract_meta_strings") or ma_lyrics._extract_meta_strings
    )
    extracted_lyrics, extracted_bio = extract_fn(
        {
            "metadata": {
                "lyrics": "Plain lyrics without timestamps",
                "lrc_lyrics": "[00:10.00]Timestamped LRC line",
                "description": "Dirt is the second studio album by Alice In Chains, released in September 1992.",
            }
        }
    )
    assert extracted_lyrics == "[00:10.00]Timestamped LRC line"
    assert "September 1992" in extracted_bio


@pytest.mark.asyncio
async def test_lyrics_fetch_local_ma_synced_preference_chunk_push_cache_and_unwrapped_bio(
    hass: Any, setup_latter_hub: Any
) -> None:
    """`lyrics_fetch` resolves local MA synced LRC over plain lyrics (Zero-WAN), caches in LRU, and auto-pushes on track change."""
    ma_browse.clear_browse_cache()
    ma_lyrics.clear_lyrics_cache()
    entry, sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None
    _seed_music_assistant(hass)

    pushed_lyrics: list[dict[str, Any]] = []
    pushed_slots: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        f"{coord.device_slug}_latter_set_music_lyrics",
        lambda call: pushed_lyrics.append(dict(call.data)),
    )
    mock_service(
        hass,
        "esphome",
        f"{coord.device_slug}_latter_set_slots",
        lambda call: pushed_slots.append(dict(call.data)),
    )

    long_album_bio = (
        "Dirt is the second studio album by the American rock band Alice in Chains, "
        "released on September 29, 1992, through Columbia Records with acclaim."
    )
    lib_track_calls: list[str] = []

    def _mock_get_library(call: Any) -> dict[str, Any]:
        mtype = call.data.get("media_type")
        search_q = str(call.data.get("search") or "")
        if mtype == "album":
            return {
                "items": [
                    {
                        "name": "Dirt",
                        "uri": "library://album/67",
                        "year": 1992,
                        "metadata": {"description": long_album_bio},
                    }
                ]
            }
        if mtype == "track":
            lib_track_calls.append(search_q)
            if "Rooster" in search_q:
                return {
                    "items": [
                        {
                            "name": "Rooster",
                            "uri": "library://track/68",
                            "artists": [{"name": "Alice In Chains"}],
                            "metadata": {
                                "lyrics": "Long unsynced plain lyric line preserved without thirty-two char wrapping",
                            },
                        }
                    ]
                }
            return {
                "items": [
                    {
                        "name": "Would?",
                        "uri": "library://track/67",
                        "artists": [{"name": "Alice In Chains"}],
                        "metadata": {
                            "lyrics": "Plain fallback line that should NOT win when lrc_lyrics exists",
                        },
                    },
                    {
                        "name": "Would?",
                        "uri": "library://track/67b",
                        "artists": [{"name": "Alice In Chains"}],
                        "metadata": {
                            "lrc_lyrics": "[00:08.50]Know me broken by my master\n[00:15.20]Teach thee on child of love hereafter",
                        },
                    },
                ]
            }
        return {"items": []}

    mock_service(
        hass,
        "music_assistant",
        "get_library",
        _mock_get_library,
        supports_response=SupportsResponse.ONLY,
    )

    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MUSIC_BROWSE,
        {
            "req_id": 7,
            "mode": "lyrics_fetch",
            "page": 1,
            "page_size": 128,
            "search": "Would?|Alice In Chains",
        },
    )
    assert len(pushed_lyrics) == 1
    assert pushed_lyrics[0] == {
        "req_id": 7,
        "chunk_index": 0,
        "chunk_count": 1,
        "track_key": "Would?|Alice In Chains",
        "synced": True,
        "lines": (
            f"8500{FIELD_SEP}Know me broken by my master"
            f"{RECORD_SEP}"
            f"15200{FIELD_SEP}Teach thee on child of love hereafter"
        ),
    }
    assert len(lib_track_calls) == 1

    # Second fetch hits the 64-entry LRU cache without calling get_library(track) again
    pushed_lyrics.clear()
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MUSIC_BROWSE,
        {
            "req_id": 8,
            "mode": "lyrics_fetch",
            "search": "Would?|Alice In Chains",
        },
    )
    assert len(pushed_lyrics) == 1
    assert pushed_lyrics[0]["req_id"] == 8
    assert len(lib_track_calls) == 1  # Cached!

    # Track change while lyrics_watch_active is True auto-pushes new lyrics (req_id=0)
    pushed_lyrics.clear()
    hass.states.async_set(
        "media_player.ma_pocket",
        "playing",
        {
            **dict(hass.states.get("media_player.ma_pocket").attributes),
            "media_title": "Rooster",
            "media_artist": "Alice In Chains",
            "media_album_name": "Dirt",
        },
    )
    await hass.async_block_till_done()
    assert len(pushed_lyrics) == 1
    assert pushed_lyrics[0]["req_id"] == 0
    assert pushed_lyrics[0]["track_key"] == "Rooster|Alice In Chains"
    assert pushed_lyrics[0]["synced"] is False
    assert (
        pushed_lyrics[0]["lines"]
        == f"-1{FIELD_SEP}Long unsynced plain lyric line preserved without thirty-two char wrapping"
    )

    # Bio / track_info emits unwrapped logical metadata + full unwrapped paragraphs (>64 chars preserved!)
    pushed_slots.clear()
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MUSIC_BROWSE,
        {
            "req_id": 9,
            "mode": "bio",
            "page": 1,
            "page_size": 10,
            "search": "Would?|Alice In Chains|Dirt",
        },
    )
    assert len(pushed_slots) == 1
    bio_rows = [
        r.split(FIELD_SEP)[0] for r in pushed_slots[0]["slots"].split(RECORD_SEP)
    ]
    assert "Artist: Alice In Chains" in bio_rows
    assert "Album: Dirt" in bio_rows
    assert "Release: 1992" in bio_rows
    assert long_album_bio in bio_rows

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_push_browse_slots_preserves_long_album_and_artist_names_up_to_120_chars(
    hass: Any, setup_latter_hub: Any
) -> None:
    """`async_push_browse_slots` preserves >64-char album/artist/queue names up to 120 chars (512 for bio/lyrics)."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None

    pushed_slots: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        f"{coord.device_slug}_latter_set_slots",
        lambda call: pushed_slots.append(dict(call.data)),
    )

    long_album_name = "Jar of Flies / Sap (30th Anniversary Remastered Super Deluxe Edition) — Alice In Chains (1994)"
    assert 64 < len(long_album_name) <= 120
    exact_120_artist_name = (
        "King Gizzard & The Lizard Wizard with Mild High Club & The Melbourne Symphony Orchestra Live! [120]"
        + ("!" * 21)
    )
    assert len(exact_120_artist_name) == 120
    over_120_name = "X" * 145

    await async_push_browse_slots(
        hass,
        coord,
        mode="album",
        page=1,
        page_size=5,
        items=[
            {"name": long_album_name, "id": "library://album/301", "type": "album"},
            {
                "name": exact_120_artist_name,
                "id": "library://artist/302",
                "type": "artist",
            },
            {"name": over_120_name, "id": "library://album/303", "type": "album"},
        ],
        req_id=55,
    )
    assert len(pushed_slots) == 1
    rows = [r.split(FIELD_SEP)[0] for r in pushed_slots[0]["slots"].split(RECORD_SEP)]
    assert rows[0] == long_album_name
    assert rows[1] == exact_120_artist_name
    assert rows[2] == "X" * 120

    # Verify bio / track_info / lyrics retain the 512-char cap
    pushed_slots.clear()
    long_bio = "B" * 300
    await async_push_browse_slots(
        hass,
        coord,
        mode="bio",
        page=1,
        page_size=5,
        items=[{"name": long_bio, "id": "bio_0", "type": "bio"}],
        req_id=56,
    )
    assert len(pushed_slots) == 1
    assert pushed_slots[0]["slots"].split(RECORD_SEP)[0].split(FIELD_SEP)[0] == long_bio

    assert await hass.config_entries.async_unload(entry.entry_id) is True
