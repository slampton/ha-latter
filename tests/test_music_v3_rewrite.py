"""Comprehensive unit & integration tests for the Music App v3.0.0 backend rewrite."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

from PIL import Image
import pytest

from custom_components.latter import media_browse as ma_browse
from custom_components.latter.const import (
    CONF_VOLUME_OVERRIDES,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    SERVICE_MEDIA_COMMAND,
    SERVICE_MUSIC_BROWSE,
)
from custom_components.latter.http import LatterArtworkTranscoderView
from custom_components.latter.media import (
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
from custom_components.latter.protocol import _PROTOCOL_V3_DATA, FIELD_SEP, RECORD_SEP
from custom_components.latter.services import async_push_browse_slots


class _FakeResponse:
    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self) -> _FakeResponse:
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        return None

    async def json(self) -> Any:
        return self._payload


class _FakeHttpSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, params: dict[str, Any] | None = None, **_kw: Any) -> _FakeResponse:
        self.calls.append((url, dict(params or {})))
        if self._responses:
            return self._responses.pop(0)
        return _FakeResponse(404, [])


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
    from homeassistant.config_entries import ConfigEntry, ConfigEntryState
    from homeassistant.helpers import device_registry as dr, entity_registry as er

    ma_entry = ConfigEntry(
        entry_id="entry_ma_test",
        domain="music_assistant",
        title="Music Assistant",
        data={},
        state=ConfigEntryState.LOADED,
    )
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

        async def _remove_item_from_favorites(media_type: Any, library_item_id: Any) -> None:
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
            current_item=(q_list[1] if len(q_list) > 1 else (q_list[0] if q_list else None)),
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

    hass.config_entries.add_entry(ma_entry)

    dev_reg = dr.async_get(hass)
    ma_dev = dev_reg.async_get_or_create(
        config_entry_id=ma_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        identifiers={("music_assistant", queue_id)},
        name="Pocket Assistant MA",
    )
    ent_reg = er.async_get(hass)
    ent_reg.async_register(
        er.RegistryEntry(
            entity_id=ma_entity,
            platform="music_assistant",
            device_id=ma_dev.id,
            config_entry_id=ma_entry.entry_id,
            unique_id=queue_id,
            original_name="Pocket Assistant MA",
        )
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


@pytest.mark.asyncio
async def test_active_queue_fetches_player_queue_items_when_get_queue_items_is_int(
    hass: Any, setup_latter_hub: Any
) -> None:
    """`music_assistant.get_queue` returns `"items": 15` (int); `_browse_active_queue` must fetch real queue items."""
    _entry, _sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None

    pushed_slots: list[dict[str, Any]] = []
    hass.services.async_register(
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
    hass.services.async_register(
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

    # Verify 7-column latter_set_slots wire encoding via music_browse service
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MUSIC_BROWSE,
        {
            "target_device": coord.device_slug,
            "req_id": 42,
            "mode": "active_queue",
            "page": 1,
            "page_size": 5,
        },
        blocking=True,
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


@pytest.mark.asyncio
async def test_active_queue_graceful_fallback_and_offset_pagination(
    hass: Any, setup_latter_hub: Any
) -> None:
    """When `mass` runtime client is unreachable and `items` is an int, fallback returns current + next item."""
    _entry, _sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None

    _ma_entry, _ = _seed_music_assistant(hass, with_runtime_mass=False)
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
    hass.services.async_register(
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

    async def _fetch_75(qid: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        fetch_log.append((qid, limit, offset))
        return seventy_five[offset : offset + limit]

    _ma_entry.runtime_data = SimpleNamespace(
        mass=SimpleNamespace(
            player_queues=SimpleNamespace(fetch_player_queue_items=_fetch_75)
        )
    )
    hass.services.async_register(
        "music_assistant",
        "get_queue",
        lambda _call: {
            "media_player.ma_pocket": {
                "queue_id": "ma_queue_pocket",
                "items": 75,
                "current_item": seventy_five[0],
            }
        },
    )
    pushed_p12: list[dict[str, Any]] = []
    hass.services.async_register(
        "esphome",
        f"{coord.device_slug}_latter_set_slots",
        lambda call: pushed_p12.append(dict(call.data)),
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MUSIC_BROWSE,
        {
            "target_device": coord.device_slug,
            "req_id": 99,
            "mode": "active_queue",
            "page": 12,
            "page_size": 5,
        },
        blocking=True,
    )
    assert fetch_log == [("ma_queue_pocket", 50, 50)]
    assert pushed_p12[0]["page"] == 12
    assert pushed_p12[0]["total_pages"] == 15
    p12_names = [r.split(FIELD_SEP)[0] for r in pushed_p12[0]["slots"].split(RECORD_SEP)]
    assert p12_names == [f"Song {i} — Band" for i in range(55, 60)]


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
    synced, lines = ma_browse.parse_lrc_lyrics(raw_lrc)
    assert synced is True
    assert lines == [
        {"t_ms": 5000, "text": "Know me broken by my master"},
        {"t_ms": 12000, "text": "Into the flood again"},
        {"t_ms": 18250, "text": "Same old trip it was back then"},
        {"t_ms": 45500, "text": "Into the flood again"},
    ]

    # Cap at 128 lines
    many_lrc = "\n".join(f"[{i // 60:02d}:{i % 60:02d}.00]Line {i}" for i in range(160))
    synced_many, lines_many = ma_browse.parse_lrc_lyrics(many_lrc)
    assert synced_many is True
    assert len(lines_many) == 128
    assert lines_many[-1] == {"t_ms": 127000, "text": "Line 127"}

    # Plain lyrics: synced=False, t_ms=-1, NO width=32 hard wrapping!
    long_line = (
        "So I made a big mistake, try to see once my way — this line is well over thirty-two characters wide"
    )
    plain_synced, plain_lines = ma_browse.parse_lrc_lyrics(f"{long_line}\nSecond logical line")
    assert plain_synced is False
    assert plain_lines == [
        {"t_ms": -1, "text": long_line},
        {"t_ms": -1, "text": "Second logical line"},
    ]

    # _extract_meta_strings prefers lrc_lyrics over plain lyrics
    extracted_lyrics, extracted_bio = ma_browse._extract_meta_strings(
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
async def test_lyrics_fetch_lrclib_synced_preference_chunk_push_cache_and_unwrapped_bio(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`lyrics_fetch` prefers synced LRCLIB lyrics, pushes `latter_set_music_lyrics`, caches in LRU, and auto-pushes on track change."""
    ma_browse.clear_browse_cache()
    _entry, _sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None
    _seed_music_assistant(hass)

    pushed_lyrics: list[dict[str, Any]] = []
    pushed_slots: list[dict[str, Any]] = []
    hass.services.async_register(
        "esphome",
        f"{coord.device_slug}_latter_set_music_lyrics",
        lambda call: pushed_lyrics.append(dict(call.data)),
    )
    hass.services.async_register(
        "esphome",
        f"{coord.device_slug}_latter_set_slots",
        lambda call: pushed_slots.append(dict(call.data)),
    )

    # Mock MA get_library returning album metadata (year + long unwrapped bio) but no embedded lyrics,
    # so lyrics_fetch falls through to LRCLIB and prefers syncedLyrics over plainLyrics.
    long_album_bio = (
        "Dirt is the second studio album by the American rock band Alice in Chains, "
        "released on September 29, 1992, through Columbia Records with acclaim."
    )

    def _mock_get_library(call: Any) -> dict[str, Any]:
        mtype = call.data.get("media_type")
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
        return {"items": []}

    hass.services.async_register("music_assistant", "get_library", _mock_get_library)

    fake_http = _FakeHttpSession(
        [
            _FakeResponse(
                200,
                [
                    {
                        "plainLyrics": "Plain fallback line that should NOT win when syncedLyrics exists",
                        "syncedLyrics": "[00:08.50]Know me broken by my master\n[00:15.20]Teach thee on child of love hereafter",
                    }
                ],
            )
        ]
    )
    monkeypatch.setattr(
        "custom_components.latter.media_browse.async_get_clientsession",
        lambda _hass: fake_http,
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_MUSIC_BROWSE,
        {
            "target_device": coord.device_slug,
            "req_id": 7,
            "mode": "lyrics_fetch",
            "page": 1,
            "page_size": 128,
            "search": "Would?|Alice In Chains",
        },
        blocking=True,
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
    assert len(fake_http.calls) == 1

    # Second fetch hits the 64-entry LRU cache without calling LRCLIB again
    pushed_lyrics.clear()
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MUSIC_BROWSE,
        {
            "target_device": coord.device_slug,
            "req_id": 8,
            "mode": "lyrics_fetch",
            "search": "Would?|Alice In Chains",
        },
        blocking=True,
    )
    assert len(pushed_lyrics) == 1
    assert pushed_lyrics[0]["req_id"] == 8
    assert len(fake_http.calls) == 1  # Cached!

    # Track change while _lyrics_watch_active is True auto-pushes new lyrics (req_id=0)
    pushed_lyrics.clear()
    fake_http._responses.append(
        _FakeResponse(
            200,
            [{"plainLyrics": "Long unsynced plain lyric line preserved without thirty-two char wrapping", "syncedLyrics": None}],
        )
    )
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
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MUSIC_BROWSE,
        {
            "target_device": coord.device_slug,
            "req_id": 9,
            "mode": "bio",
            "page": 1,
            "page_size": 10,
            "search": "Would?|Alice In Chains|Dirt",
        },
        blocking=True,
    )
    assert len(pushed_slots) == 1
    bio_rows = [r.split(FIELD_SEP)[0] for r in pushed_slots[0]["slots"].split(RECORD_SEP)]
    assert "Artist: Alice In Chains" in bio_rows
    assert "Album: Dirt" in bio_rows
    assert "Release: 1992" in bio_rows
    assert long_album_bio in bio_rows  # Unwrapped (>130 chars, NOT truncated at 64 or wrapped at 32!)


@pytest.mark.asyncio
async def test_enqueue_modes_radio_mode_and_queue_manipulation_commands(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify MA `enqueue` (`play|next|add|replace`), `radio_mode`, and `queue_play` / `queue_move` / `queue_delete`."""
    _entry, _sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None

    q_items = [
        {"queue_item_id": "qi_0", "media_item": {"name": "Them Bones", "uri": "library://track/1"}},
        {"queue_item_id": "qi_1", "media_item": {"name": "Dam That River", "uri": "library://track/2"}},
        {"queue_item_id": "qi_2", "media_item": {"name": "Rain When I Die", "uri": "library://track/3"}},
        {"queue_item_id": "qi_3", "media_item": {"name": "Down in a Hole", "uri": "library://track/4"}},
        {"queue_item_id": "qi_4", "media_item": {"name": "Would?", "uri": "library://track/5"}},
    ]
    _ma_entry, mass = _seed_music_assistant(hass, queue_items=q_items)
    assert mass is not None
    # current_index = 1 ("Dam That River")
    mass.player_queues.queue_state_obj.current_index = 1

    ma_play_calls: list[dict[str, Any]] = []
    hass.services.async_register(
        "music_assistant",
        "play_media",
        lambda call: ma_play_calls.append(dict(call.data)),
    )
    hass.services.async_register(
        "music_assistant",
        "get_queue",
        lambda _call: {
            "media_player.ma_pocket": {
                "queue_id": "ma_queue_pocket",
                "items": 5,
                "current_index": 1,
                "current_item": q_items[1],
            }
        },
    )

    for enq in ("play", "next", "add", "replace"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MEDIA_COMMAND,
            {
                "target_device": coord.device_slug,
                "command": "play_media",
                "media_id": "library://track/999",
                "media_type": "track",
                "enqueue": enq,
                "radio_mode": enq == "replace",
            },
            blocking=True,
        )
    assert [c["enqueue"] for c in ma_play_calls] == ["play", "next", "add", "replace"]
    assert "radio_mode" not in ma_play_calls[0]
    assert ma_play_calls[3]["radio_mode"] is True

    # queue_play jumps in-place via mass.player_queues.play_index
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {
            "target_device": coord.device_slug,
            "command": "queue_play",
            "queue_item_id": "qi_4",
        },
        blocking=True,
    )
    assert mass.player_queues.play_index_calls == [("ma_queue_pocket", "qi_4")]

    # queue_move supports Move Up (-1), Move Down (+1), and Play Next ("next" -> current_index + 1 - item_index)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {
            "target_device": coord.device_slug,
            "command": "queue_move",
            "queue_item_id": "qi_3",
            "pos_shift": -1,
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {
            "target_device": coord.device_slug,
            "command": "queue_move",
            "queue_item_id": "qi_2",
            "pos_shift": "+1",
        },
        blocking=True,
    )
    # Item qi_4 is at index 4; current_index is 1 -> Play Next target index is 2 -> shift = (1 + 1) - 4 = -2
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {
            "target_device": coord.device_slug,
            "command": "queue_move",
            "queue_item_id": "qi_4",
            "pos_shift": "next",
        },
        blocking=True,
    )
    assert mass.player_queues.move_item_calls == [
        ("ma_queue_pocket", "qi_3", -1),
        ("ma_queue_pocket", "qi_2", 1),
        ("ma_queue_pocket", "qi_4", -2),
    ]

    # queue_delete removes item via mass.player_queues.delete_item(queue_id, item_id_or_index=...)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {
            "target_device": coord.device_slug,
            "command": "queue_delete",
            "queue_item_id": "qi_3",
        },
        blocking=True,
    )
    assert mass.player_queues.delete_item_calls == [("ma_queue_pocket", "qi_3")]


@pytest.mark.asyncio
async def test_active_media_21_fields_and_mute_shuffle_repeat_favorite_commands(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify `active_media` 21-field sync (`shuffle`, `repeat`, `muted`, `favorite`, `queue_count`, `media_caps`) and toggles."""
    _entry, _sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None
    hass.data.setdefault(DOMAIN, {}).setdefault(DATA_GLOBAL_CONFIG, {})[
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
    hass.services.async_register(
        "media_player", "volume_mute", lambda call: mute_calls.append(dict(call.data))
    )
    hass.services.async_register(
        "media_player", "shuffle_set", lambda call: shuffle_calls.append(dict(call.data))
    )
    hass.services.async_register(
        "media_player", "repeat_set", lambda call: repeat_calls.append(dict(call.data))
    )

    await hass.async_block_till_done()
    coord._cached_media_payload = None
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
    assert len(wire_fields) == 3 + len(_PROTOCOL_V3_DATA["domains"]["active_media"]["fields"]) == 24
    assert wire_fields[18] == "0"  # shuffle
    assert wire_fields[19] == "off"  # repeat
    assert wire_fields[20] == "1"  # muted (from volume_override AVR!)
    assert wire_fields[21] == "0"  # favorite
    assert wire_fields[22] == "15"  # queue_count
    assert wire_fields[23] == str(expected_caps)  # media_caps

    # 1. mute_toggle targets the configured volume_override entity (living_room_avr)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {"target_device": coord.device_slug, "command": "mute_toggle"},
        blocking=True,
    )
    assert mute_calls == [
        {"entity_id": "media_player.living_room_avr", "is_volume_muted": False}
    ]

    # 2. shuffle_toggle toggles False -> True on MA player
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {"target_device": coord.device_slug, "command": "shuffle_toggle"},
        blocking=True,
    )
    assert shuffle_calls == [{"entity_id": "media_player.ma_pocket", "shuffle": True}]

    # 3. repeat_cycle steps off -> all -> one -> off
    for cur_rep, next_rep in (("off", "all"), ("all", "one"), ("one", "off")):
        repeat_calls.clear()
        mass.player_queues.queue_state_obj.repeat_mode = SimpleNamespace(value=cur_rep)
        hass.states.async_set(
            "media_player.ma_pocket",
            "playing",
            {**dict(hass.states.get("media_player.ma_pocket").attributes), "repeat": cur_rep},
        )
        await hass.services.async_call(
            DOMAIN,
            SERVICE_MEDIA_COMMAND,
            {"target_device": coord.device_slug, "command": "repeat_cycle"},
            blocking=True,
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
    coord._cached_media_payload = None
    _dyn_st, dyn_attrs = build_active_media_payload(coord)
    assert dyn_attrs["media_caps"] == (
        expected_caps & ~(MEDIA_CAP_SHUFFLE_SET | MEDIA_CAP_REPEAT_SET)
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {"target_device": coord.device_slug, "command": "shuffle_toggle"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {"target_device": coord.device_slug, "command": "repeat_cycle"},
        blocking=True,
    )
    assert shuffle_calls == []
    assert repeat_calls == []
    mass.player_queues.queue_state_obj.is_dynamic = False
    mass.player_queues.queue_state_obj.shuffle_enabled = False
    coord._cached_media_payload = None
    _restored_st, restored_attrs = build_active_media_payload(coord)
    assert restored_attrs["media_caps"] == expected_caps

    # 4. favorite_toggle with media_id="" and plain non-URI media_id="Track Title" resolves real URI
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {"target_device": coord.device_slug, "command": "favorite_toggle", "media_id": ""},
        blocking=True,
    )
    assert mass.music.fav_add_calls == ["library://track/843"]
    coord._cached_media_payload = None
    _st2, attrs2 = build_active_media_payload(coord)
    assert attrs2["favorite"] is True

    # Passing a plain track title (non-URI without "://") must NOT pass raw title to add/remove_item_to_favorites
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {
            "target_device": coord.device_slug,
            "command": "favorite_toggle",
            "media_id": "Would?",
        },
        blocking=True,
    )
    assert mass.music.fav_remove_calls == [("track", "843")]
    coord._cached_media_payload = None
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
    hass.services.async_register(
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
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        {
            "target_device": coord.device_slug,
            "command": "favorite_toggle",
            "media_id": "Track Title",
        },
        blocking=True,
    )
    assert mass.music.fav_add_calls == ["library://track/901"]


@pytest.mark.asyncio
async def test_desk_720x720_native_album_art_dimensions_and_http_proxy(
    hass: Any, setup_latter_hub: Any
) -> None:
    """720x720 Desk panels get native 720x720 `art_dimensions` and 1:1 720x720 baseline JPEGs from `http.py`."""
    _entry, _sys_obj, coord = await setup_latter_hub(hass, stationary=1)
    assert coord is not None

    hass.states.async_set(
        f"sensor.{coord.device_slug}_system_hardware_manifest",
        json.dumps(
            {
                "v": 2,
                "contract": 3,
                "board": "waveshare_p4_desk",
                "w": 720,
                "h": 720,
                "shape": "square",
                "display": 1,
            }
        ),
    )
    assert coord.art_dimensions == (720, 720)

    # Oversized 1200x1200 manifest still clamps cleanly to 720x720
    hass.states.async_set(
        f"sensor.{coord.device_slug}_system_hardware_manifest",
        json.dumps({"v": 2, "contract": 3, "w": 1200, "h": 1200, "shape": "square", "display": 1}),
    )
    assert coord.art_dimensions == (720, 720)

    # Restore 720x720 Desk manifest and verify signed art_url + HTTP baseline JPEG output
    hass.states.async_set(
        f"sensor.{coord.device_slug}_system_hardware_manifest",
        json.dumps({"v": 2, "contract": 3, "w": 720, "h": 720, "shape": "square", "display": 1}),
    )
    hass.states.async_set(
        "media_player.pocket_assistant_music",
        "playing",
        {
            "friendly_name": "Desk Speaker",
            "media_title": "Would?",
            "media_artist": "Alice In Chains",
            "entity_picture": "http://93.184.216.34/cover_1000.png",
            "volume_level": 0.5,
        },
    )
    coord._cached_media_payload = None
    _st, attrs = build_active_media_payload(coord)
    art_url = attrs["art_url"]
    assert "w=720&h=720" in art_url

    src_buf = io.BytesIO()
    Image.new("RGB", (1000, 1000), (36, 92, 168)).save(src_buf, format="PNG")
    raw_png = src_buf.getvalue()

    class _StreamContent:
        async def iter_chunked(self, size: int = 65536) -> Any:
            for i in range(0, len(raw_png), size):
                yield raw_png[i : i + size]

    class _ImgResp:
        status = 200
        content_length = len(raw_png)
        content = _StreamContent()

        async def __aenter__(self) -> _ImgResp:
            return self

        async def __aexit__(self, *_exc: Any) -> None:
            return None

    hass.data["_mock_http_get"] = lambda _url, **_kw: _ImgResp()

    parsed = urlsplit(art_url)
    query_dict = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    req = SimpleNamespace(query=query_dict, headers={})
    resp = await LatterArtworkTranscoderView(hass).get(req, coord.device_slug)
    assert resp.status == 200
    assert resp.content_type == "image/jpeg"
    assert resp.body[:2] == b"\xff\xd8"
    with Image.open(io.BytesIO(resp.body)) as out_img:
        assert out_img.size == (720, 720)
        if hasattr(out_img, "info"):
            assert out_img.info.get("progressive", 0) == 0


@pytest.mark.asyncio
async def test_push_browse_slots_preserves_long_album_and_artist_names_up_to_120_chars(
    hass: Any, setup_latter_hub: Any
) -> None:
    """`async_push_browse_slots` preserves >64-char album/artist/queue names up to 120 chars (512 for bio/lyrics)."""
    _entry, _sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None

    pushed_slots: list[dict[str, Any]] = []
    hass.services.async_register(
        "esphome",
        f"{coord.device_slug}_latter_set_slots",
        lambda call: pushed_slots.append(dict(call.data)),
    )

    long_album_name = (
        "Jar of Flies / Sap (30th Anniversary Remastered Super Deluxe Edition) — Alice In Chains (1994)"
    )
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
            {"name": exact_120_artist_name, "id": "library://artist/302", "type": "artist"},
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

