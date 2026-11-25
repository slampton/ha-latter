"""Tests for Music Assistant enqueue modes, radio mode, queue manipulation, and 720x720 artwork proxy."""

from __future__ import annotations

import io
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.helpers import (
    aiohttp_client as ha_aiohttp_client,
    device_registry as dr,
)
from PIL import Image
import pytest

from custom_components.latter.const import RPC_MEDIA_COMMAND
from custom_components.latter.http import proxy_views
from custom_components.latter.http.proxy_views import LatterArtworkTranscoderView
from custom_components.latter.media.state_payload import build_active_media_payload
from tests.helpers import (
    add_mock_entry,
    mock_clientsession_get,
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


async def test_enqueue_modes_radio_mode_and_queue_manipulation_commands(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify MA `enqueue` (`play|next|add|replace`), `radio_mode`, and `queue_play` / `queue_move` / `queue_delete`."""
    entry, sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None

    q_items = [
        {
            "queue_item_id": "qi_0",
            "media_item": {"name": "Them Bones", "uri": "library://track/1"},
        },
        {
            "queue_item_id": "qi_1",
            "media_item": {"name": "Dam That River", "uri": "library://track/2"},
        },
        {
            "queue_item_id": "qi_2",
            "media_item": {"name": "Rain When I Die", "uri": "library://track/3"},
        },
        {
            "queue_item_id": "qi_3",
            "media_item": {"name": "Down in a Hole", "uri": "library://track/4"},
        },
        {
            "queue_item_id": "qi_4",
            "media_item": {"name": "Would?", "uri": "library://track/5"},
        },
    ]
    _ma_entry, mass = _seed_music_assistant(hass, queue_items=q_items)
    assert mass is not None
    # current_index = 1 ("Dam That River")
    mass.player_queues.queue_state_obj.current_index = 1

    ma_play_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "music_assistant",
        "play_media",
        lambda call: ma_play_calls.append(dict(call.data)),
    )
    mock_service(
        hass,
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
        supports_response=SupportsResponse.ONLY,
    )

    for enq in ("play", "next", "add", "replace"):
        await sys_obj.rpc_dispatcher.async_dispatch(
            coord,
            RPC_MEDIA_COMMAND,
            {
                "command": "play_media",
                "media_id": "library://track/999",
                "media_type": "track",
                "enqueue": enq,
                "radio_mode": enq == "replace",
            },
        )
    assert [c["enqueue"] for c in ma_play_calls] == ["play", "next", "add", "replace"]
    assert "radio_mode" not in ma_play_calls[0]
    assert ma_play_calls[3]["radio_mode"] is True

    # queue_play jumps in-place via mass.player_queues.play_index
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {
            "command": "queue_play",
            "queue_item_id": "qi_4",
        },
    )
    assert mass.player_queues.play_index_calls == [("ma_queue_pocket", "qi_4")]

    # queue_move supports Move Up (-1), Move Down (+1), and Play Next ("next" -> current_index + 1 - item_index)
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {
            "command": "queue_move",
            "queue_item_id": "qi_3",
            "pos_shift": -1,
        },
    )
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {
            "command": "queue_move",
            "queue_item_id": "qi_2",
            "pos_shift": "+1",
        },
    )
    # Item qi_4 is at index 4; current_index is 1 -> Play Next target index is 2 -> shift = (1 + 1) - 4 = -2
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {
            "command": "queue_move",
            "queue_item_id": "qi_4",
            "pos_shift": "next",
        },
    )
    assert mass.player_queues.move_item_calls == [
        ("ma_queue_pocket", "qi_3", -1),
        ("ma_queue_pocket", "qi_2", 1),
        ("ma_queue_pocket", "qi_4", -2),
    ]

    # queue_delete removes item via mass.player_queues.delete_item(queue_id, item_id_or_index=...)
    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {
            "command": "queue_delete",
            "queue_item_id": "qi_3",
        },
    )
    assert mass.player_queues.delete_item_calls == [("ma_queue_pocket", "qi_3")]

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_desk_720x720_native_album_art_dimensions_and_http_proxy(
    hass: Any, setup_latter_hub: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """720x720 Desk panels get native 720x720 `art_dimensions` and 1:1 720x720 baseline JPEGs from `proxy_views`."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, stationary=1)
    assert coord is not None

    coord._runtime.hello_manifest = {
        "v": 2,
        "contract": 3,
        "board": "desk_p4_board",
        "w": 720,
        "h": 720,
        "shape": "square",
        "display": 1,
    }
    assert coord.art_dimensions == (720, 720)

    # High-res 1200x1200 and 1280x800 tablet manifests stay native under WALLPAPER_MAX_DIM=1280
    coord._runtime.hello_manifest = {
        "v": 2,
        "contract": 3,
        "w": 1200,
        "h": 1200,
        "shape": "square",
        "display": 1,
    }
    assert coord.art_dimensions == (1200, 1200)

    coord._runtime.hello_manifest = {
        "v": 2,
        "contract": 3,
        "w": 1280,
        "h": 800,
        "shape": "rect",
        "art_edge": 800,
        "display": 1,
    }
    assert coord.art_dimensions == (800, 800)
    assert coord.wallpaper_dimensions == (1280, 800)

    # 320x480 portrait Remote gets square 320x320 album art and 320x480 full wallpaper
    coord._runtime.hello_manifest = {
        "v": 2,
        "contract": 3,
        "w": 320,
        "h": 480,
        "shape": "rect",
        "art_edge": 320,
        "display": 1,
    }
    assert coord.art_dimensions == (320, 320)
    assert coord.wallpaper_dimensions == (320, 480)

    # Oversized 1920x1200 manifest scales wallpaper to 1280x800 and square album art to 800x800
    coord._runtime.hello_manifest = {
        "v": 2,
        "contract": 3,
        "w": 1920,
        "h": 1200,
        "shape": "rect",
        "display": 1,
    }
    assert coord.art_dimensions == (800, 800)
    assert coord.wallpaper_dimensions == (1280, 800)

    # Restore 720x720 Desk manifest and verify signed art_url + HTTP baseline JPEG output
    coord._runtime.hello_manifest = {
        "v": 2,
        "contract": 3,
        "w": 720,
        "h": 720,
        "shape": "square",
        "display": 1,
    }
    hass.states.async_set(
        "media_player.pocket_assistant_music",
        "playing",
        {
            "friendly_name": "Desk Speaker",
            "media_title": "Would?",
            "media_artist": "Alice In Chains",
            "entity_picture": "/api/media_player_proxy/media_player.pocket_assistant_music?token=desk_1000",
            "volume_level": 0.5,
        },
    )
    coord.cached_media_payload = None
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

    mock_clientsession_get(monkeypatch, lambda _url, **_kw: _ImgResp())
    monkeypatch.setattr(
        proxy_views,
        "async_get_clientsession",
        ha_aiohttp_client.async_get_clientsession,
    )

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

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_default_speaker_auto_open_persistence_listener_and_lyrics_push(
    hass: Any,
    setup_latter_hub: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """External `default_speaker` survives idle resets, auto-switches on play, sets `is_default_speaker`, and pushes lyrics."""
    from custom_components.latter.const import (
        CONF_DEFAULT_SPEAKER,
        CONF_MUSIC_AUTO_OPEN,
    )
    from custom_components.latter.groups.device_groups import GROUP_INTERFACE_DEVICE_KEYS
    from custom_components.latter.media import playback as media_playback
    from custom_components.latter.media.playback import (
        bind_coordinator_speaker_listener,
        enforce_local_speaker_if_remote_idle,
        is_default_speaker_entity,
        resolve_default_speaker_entity,
    )

    assert CONF_MUSIC_AUTO_OPEN in GROUP_INTERFACE_DEVICE_KEYS

    entry, _sys_obj, coord = await setup_latter_hub(hass, stationary=1)
    assert coord is not None
    desk_spk = "media_player.office_sonos"
    other_spk = "media_player.kitchen_speaker"

    hass.states.async_set(desk_spk, "idle", {"friendly_name": "Office Sonos"})
    hass.states.async_set(other_spk, "idle", {"friendly_name": "Kitchen Speaker"})

    # Configure external default_speaker + Lyrics auto-open mode
    coord.update_device_config(
        {
            **coord.device_data,
            CONF_DEFAULT_SPEAKER: desk_spk,
            CONF_MUSIC_AUTO_OPEN: "Lyrics",
        },
        preserve_group=True,
    )
    await coord.async_apply_options()
    await hass.async_block_till_done()

    assert resolve_default_speaker_entity(coord) == desk_spk
    assert coord.active_speaker == desk_spk
    assert is_default_speaker_entity(coord, desk_spk) is True
    assert is_default_speaker_entity(coord, other_spk) is False
    assert is_default_speaker_entity(coord, coord.local_speaker) is False
    with monkeypatch.context() as mp:
        mp.setattr(
            media_playback,
            "resolve_ma_counterpart_entity",
            lambda _hass, eid: "media_player.office_sonos_ma" if eid == desk_spk else None,
        )
        assert is_default_speaker_entity(coord, "media_player.office_sonos_ma") is True

    # 1. Idle external default_speaker MUST NOT be clobbered back to local_speaker on boot/reconnect
    enforce_local_speaker_if_remote_idle(coord, "ha_startup")
    assert coord.active_speaker == desk_spk

    # Payload exposes is_default_speaker=True (wire field 23 = "1") for desk_spk
    coord.cached_media_payload = None
    _st, attrs = build_active_media_payload(coord)
    assert attrs["is_default_speaker"] is True
    assert attrs["payload"].split("\x1f")[23] == "1"

    # 2. Idle non-default speaker resets back to configured default_speaker (not local_speaker)
    coord.active_speaker = other_spk
    enforce_local_speaker_if_remote_idle(coord, "device_reconnect")
    assert coord.active_speaker == desk_spk

    # 3. While active_speaker is an idle non-default speaker, starting playback on default_speaker
    #    switches active_speaker back to default_speaker and pushes lyrics proactively!
    pushed_lyrics: list[str] = []

    async def _fake_push_lyrics(
        _hass: Any, _coord: Any, *, req_id: int = 0, search: str = ""
    ) -> None:
        pushed_lyrics.append(f"{req_id}:{search}")

    monkeypatch.setattr(media_playback, "async_fetch_and_push_music_lyrics", _fake_push_lyrics)
    monkeypatch.setattr(coord, "is_rpc_outbox_unavailable", lambda: False)

    coord.active_speaker = other_spk
    bind_coordinator_speaker_listener(coord)
    coord.cached_media_payload = None
    _st2, attrs2 = build_active_media_payload(coord)
    assert attrs2["is_default_speaker"] is False
    assert attrs2["payload"].split("\x1f")[23] == "0"

    # Ephemeral TTS announcement on default speaker must NOT hijack active_speaker
    hass.states.async_set(
        desk_spk,
        "playing",
        {
            "friendly_name": "Office Sonos",
            "media_title": "Announcement",
            "media_content_id": "/api/tts_proxy/abc123.mp3",
        },
    )
    await hass.async_block_till_done()
    assert coord.active_speaker == other_spk

    # Real music starting on default speaker switches active_speaker -> desk_spk & pushes lyrics
    hass.states.async_set(desk_spk, "idle", {"friendly_name": "Office Sonos"})
    await hass.async_block_till_done()
    hass.states.async_set(
        desk_spk,
        "playing",
        {
            "friendly_name": "Office Sonos",
            "media_title": "Time",
            "media_artist": "Pink Floyd",
            "media_content_type": "music",
        },
    )
    await hass.async_block_till_done()
    assert coord.active_speaker == desk_spk
    assert pushed_lyrics == ["0:Time|Pink Floyd"]

    # 4. Track change on default speaker with music_auto_open == "Lyrics" pushes next track's lyrics
    #    while screen is awake or on screensaver (display_power_state != 2), but skips speech / dark / bedtime.
    hass.states.async_set(
        desk_spk,
        "playing",
        {
            "friendly_name": "Office Sonos",
            "media_title": "Money",
            "media_artist": "Pink Floyd",
            "media_content_type": "music",
        },
    )
    await hass.async_block_till_done()
    assert pushed_lyrics[-1] == "0:Money|Pink Floyd"

    # Same-track state updates do not double-push lyrics (both auto-open & explicit watch)
    count_same = len(pushed_lyrics)
    hass.states.async_set(
        desk_spk,
        "playing",
        {
            "friendly_name": "Office Sonos",
            "media_title": "Money",
            "media_artist": "Pink Floyd",
            "media_content_type": "music",
            "volume_level": 0.45,
        },
    )
    await hass.async_block_till_done()
    assert len(pushed_lyrics) == count_same

    coord.lyrics_watch_active = True
    hass.states.async_set(
        desk_spk,
        "playing",
        {
            "friendly_name": "Office Sonos",
            "media_title": "Money",
            "media_artist": "Pink Floyd",
            "media_content_type": "music",
            "volume_level": 0.50,
        },
    )
    await hass.async_block_till_done()
    assert len(pushed_lyrics) == count_same
    coord.lyrics_watch_active = False

    # Podcast skips proactive lyrics push
    count_before = len(pushed_lyrics)
    hass.states.async_set(
        desk_spk,
        "playing",
        {
            "friendly_name": "Office Sonos",
            "media_title": "Episode 42",
            "media_artist": "Tech Show",
            "media_content_type": "podcast",
        },
    )
    await hass.async_block_till_done()
    assert len(pushed_lyrics) == count_before

    # Screen Off (display_power_state == 2) skips proactive lyrics push
    coord.display_power_state = 2
    hass.states.async_set(
        desk_spk,
        "playing",
        {
            "friendly_name": "Office Sonos",
            "media_title": "Us and Them",
            "media_artist": "Pink Floyd",
            "media_content_type": "music",
        },
    )
    await hass.async_block_till_done()
    assert len(pushed_lyrics) == count_before

    # Bedtime active skips proactive lyrics push even if display_power_state == 1
    coord.display_power_state = 1
    await coord.async_update_device_prefs({"bedtime_active": True})
    hass.states.async_set(
        desk_spk,
        "playing",
        {
            "friendly_name": "Office Sonos",
            "media_title": "Eclipse",
            "media_artist": "Pink Floyd",
            "media_content_type": "music",
        },
    )
    await hass.async_block_till_done()
    assert len(pushed_lyrics) == count_before

    # 5. If active_speaker is actively playing, default_speaker starting does NOT steal active_speaker;
    #    and if music_auto_open == "Off", default_speaker starting does NOT steal active_speaker.
    await coord.async_update_device_prefs({"bedtime_active": False})
    coord.display_power_state = 0
    hass.states.async_set(desk_spk, "idle", {"friendly_name": "Office Sonos"})
    hass.states.async_set(other_spk, "playing", {"friendly_name": "Kitchen Speaker", "media_title": "Jazz"})
    coord.active_speaker = other_spk
    bind_coordinator_speaker_listener(coord)
    hass.states.async_set(
        desk_spk,
        "playing",
        {"friendly_name": "Office Sonos", "media_title": "Rock", "media_artist": "Band"},
    )
    await hass.async_block_till_done()
    assert coord.active_speaker == other_spk

    # Already-playing default_speaker updating track (playing -> playing) does not steal active_speaker
    hass.states.async_set(other_spk, "idle", {"friendly_name": "Kitchen Speaker"})
    hass.states.async_set(
        desk_spk,
        "playing",
        {"friendly_name": "Office Sonos", "media_title": "Rock 2", "media_artist": "Band"},
    )
    await hass.async_block_till_done()
    assert coord.active_speaker == other_spk

    # Unrelated device pref updates preserve active_speaker, and music_auto_open == "Off"
    # prevents idle other_spk from switching when default_speaker starts playing.
    await coord.async_update_device_prefs({CONF_MUSIC_AUTO_OPEN: "Off"})
    await hass.async_block_till_done()
    assert coord.active_speaker == other_spk
    hass.states.async_set(desk_spk, "idle", {"friendly_name": "Office Sonos"})
    await hass.async_block_till_done()
    hass.states.async_set(
        desk_spk,
        "playing",
        {"friendly_name": "Office Sonos", "media_title": "Jazz 2", "media_artist": "Trio"},
    )
    await hass.async_block_till_done()
    assert coord.active_speaker == other_spk

    assert await hass.config_entries.async_unload(entry.entry_id) is True
