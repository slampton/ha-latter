"""Real-HA coverage tests for `media/tts_queue.py`, `media/browse.py`, and `media/lyrics.py`."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
import pytest

from custom_components.latter.hub_registry import get_domain_data
from custom_components.latter.media import (
    browse as ma_browse,
    lyrics as ma_lyrics,
    tts_queue,
)
from custom_components.latter.media.linking import clear_ma_counterpart_cache
from custom_components.latter.protocol_codec import FIELD_SEP, RECORD_SEP
from tests.helpers import (
    add_mock_entry,
    mock_service,
    register_device,
    register_entity,
)


def _seed_ma_player(
    hass: Any,
    *,
    ma_entity: str = "media_player.ma_desk",
    queue_id: str = "ma_queue_desk",
    mac: str = "aa:bb:cc:dd:ee:11",
    entry_id: str = "entry_ma_cov",
    state: str = "playing",
    mass_client: Any = None,
    extra_attrs: dict[str, Any] | None = None,
) -> Any:
    """Register a loaded Music Assistant config entry, device, and `media_player` entity."""
    ma_entry = hass.config_entries.async_get_entry(entry_id)
    if ma_entry is None:
        ma_entry = add_mock_entry(
            hass,
            domain="music_assistant",
            title="Music Assistant",
            entry_id=entry_id,
            data={},
        )
        if hasattr(ma_entry, "mock_state"):
            ma_entry.mock_state(hass, ConfigEntryState.LOADED)
    if mass_client is not None:
        ma_entry.runtime_data = SimpleNamespace(mass=mass_client)

    ma_dev = register_device(
        hass,
        config_entry_id=ma_entry.entry_id,
        entry_domain="music_assistant",
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        identifiers={("music_assistant", queue_id)},
        name="Desk MA Player",
        manufacturer="Latter",
    )
    register_entity(
        hass,
        ma_entity,
        platform="music_assistant",
        device_id=ma_dev.id,
        config_entry=ma_entry,
        unique_id=queue_id,
        original_name="Desk MA Player",
    )
    attrs: dict[str, Any] = {
        "friendly_name": "Desk MA Player",
        "mass_player_type": "player",
        "active_queue": queue_id,
    }
    if extra_attrs:
        attrs.update(extra_attrs)
    hass.states.async_set(ma_entity, state, attrs)
    return ma_entry


def _seed_esphome_speaker(
    hass: Any,
    *,
    entity_id: str = "media_player.desk_speaker_music",
    mac: str = "aa:bb:cc:dd:ee:11",
    slug: str = "desk_speaker",
    device_name: str = "Desk Speaker",
    state: str = "idle",
) -> Any:
    """Register a bound ESPHome device and `media_player` entity."""
    entry_id = f"esp_entry_{slug}"
    esp_entry = hass.config_entries.async_get_entry(entry_id)
    if esp_entry is None:
        esp_entry = add_mock_entry(
            hass,
            domain="esphome",
            title=device_name,
            entry_id=entry_id,
            data={"device_name": slug},
            version=1,
        )
    esp_dev = register_device(
        hass,
        config_entry_id=esp_entry.entry_id,
        entry_domain="esphome",
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        identifiers={("esphome", mac)},
        name=device_name,
        manufacturer="Latter",
    )
    register_entity(
        hass,
        entity_id,
        platform="esphome",
        device_id=esp_dev.id,
        config_entry=esp_entry,
        unique_id=f"{slug}_music_uid",
        original_name="Music",
    )
    hass.states.async_set(
        entity_id,
        state,
        {"friendly_name": f"{device_name} Music", "volume_level": 0.5},
    )
    return esp_dev


# ---------------------------------------------------------------------------
# tts_queue.py coverage tests
# ---------------------------------------------------------------------------


def test_tts_queue_uri_and_entry_parsing_helpers() -> None:
    """Exercise `parse_media_uri_type`, `_extract_queue_entry_uri`, and `_extract_queue_entry_album_ref`."""
    assert tts_queue.parse_media_uri_type("plain_without_scheme") == ""
    assert tts_queue.parse_media_uri_type("") == ""
    assert tts_queue.parse_media_uri_type("https://cdn.example/audio.mp3") == ""
    assert tts_queue.parse_media_uri_type("http://cdn.example/audio.mp3") == ""
    assert tts_queue.parse_media_uri_type("rtsp://cam.local/stream") == ""
    assert tts_queue.parse_media_uri_type("media-source://tts/piper") == ""
    assert tts_queue.parse_media_uri_type("library://tracks/101") == "track"
    assert tts_queue.parse_media_uri_type("library://albums/67") == "album"
    assert tts_queue.parse_media_uri_type("library://podcast_episode/42") == "track"
    assert tts_queue.parse_media_uri_type("library://folder/9") == ""

    assert tts_queue._extract_queue_entry_uri("not_a_dict") == ""
    assert tts_queue._extract_queue_entry_uri(None) == ""
    assert (
        tts_queue._extract_queue_entry_uri(
            {
                "media_item": {"uri": "https://ha.local/api/tts_proxy/abc.mp3"},
                "uri": "library://track/7",
            }
        )
        == "library://track/7"
    )
    assert tts_queue._extract_queue_entry_uri({"uri": "/api/latter/chime.wav"}) == ""

    assert tts_queue._extract_queue_entry_album_ref(None) == ""
    assert tts_queue._extract_queue_entry_album_ref(["not_a_dict"]) == ""
    assert (
        tts_queue._extract_queue_entry_album_ref(
            {"media_item": {"album": {"uri": "library://album/67"}}}
        )
        == "library://album/67"
    )
    assert (
        tts_queue._extract_queue_entry_album_ref(
            {"media_item": {"album": "  Facelift  "}}
        )
        == "Facelift"
    )
    assert (
        tts_queue._extract_queue_entry_album_ref({"media_album_name": "Jar of Flies"})
        == "Jar of Flies"
    )


async def test_tts_queue_resume_queries_expansion_and_single_item(hass: Any) -> None:
    """Cover `_async_query_ma_queue_for_resume`, `_async_expand_album_tail_uris`, and resume item helpers."""
    try:
        spk = "media_player.desk_speaker_music"
        ma_ent = "media_player.ma_desk"
        _seed_esphome_speaker(hass, entity_id=spk)
        _seed_ma_player(hass, ma_entity=ma_ent)

        # 1. Non-dict q_data response
        mock_service(
            hass,
            "music_assistant",
            "get_queue",
            lambda _call: {ma_ent: "malformed_non_dict"},
            supports_response=SupportsResponse.ONLY,
        )
        assert await tts_queue._async_query_ma_queue_for_resume(hass, ma_ent, 12.0) == (
            [],
            "",
            "",
            "",
            12.0,
        )

        # 2. List `items` with valid `current_index` -> direct_uris slice returned by async_find_queue_resume_items
        mock_service(
            hass,
            "music_assistant",
            "get_queue",
            lambda _call: {
                ma_ent: {
                    "current_index": 1,
                    "elapsed_time": 34.5,
                    "items": [
                        {"media_item": {"uri": "library://track/1"}},
                        {"media_item": {"uri": "library://track/2"}},
                        {"media_item": {"uri": "library://track/3"}},
                    ],
                }
            },
            supports_response=SupportsResponse.ONLY,
        )
        uris, pos = await tts_queue.async_find_queue_resume_items(hass, spk, "", 0.0)
        assert uris == ["library://track/2", "library://track/3"]
        assert pos == 34.5

        # 3. List `queue_items` without `current_index`, matching `cur_uri`
        mock_service(
            hass,
            "music_assistant",
            "get_queue",
            lambda _call: {
                ma_ent: {
                    "current_item": {"media_item": {"uri": "library://track/20"}},
                    "queue_items": [
                        {"media_item": {"uri": "library://track/10"}},
                        {"media_item": {"uri": "library://track/20"}},
                        {"media_item": {"uri": "library://track/30"}},
                    ],
                }
            },
            supports_response=SupportsResponse.ONLY,
        )
        direct_uris, cur_u, _nxt, _alb, _p = (
            await tts_queue._async_query_ma_queue_for_resume(hass, ma_ent, 5.0)
        )
        assert cur_u == "library://track/20"
        assert direct_uris == ["library://track/20", "library://track/30"]

        # 4. List `items` where neither `current_index` nor `cur_uri` matches -> start_idx = 0
        mock_service(
            hass,
            "music_assistant",
            "get_queue",
            lambda _call: {
                ma_ent: {
                    "current_item": {"media_item": {"uri": "library://track/999"}},
                    "items": [
                        {"media_item": {"uri": "library://track/11"}},
                        {"media_item": {"uri": "library://track/12"}},
                    ],
                }
            },
            supports_response=SupportsResponse.ONLY,
        )
        direct_zero, *_ = await tts_queue._async_query_ma_queue_for_resume(
            hass, ma_ent, 8.0
        )
        assert direct_zero == ["library://track/11", "library://track/12"]

        # 5. `get_queue` raising an exception
        def _raise_queue(_call: Any) -> dict[str, Any]:
            raise RuntimeError("queue unavailable")

        mock_service(
            hass,
            "music_assistant",
            "get_queue",
            _raise_queue,
            supports_response=SupportsResponse.ONLY,
        )
        assert await tts_queue._async_query_ma_queue_for_resume(hass, ma_ent, 9.5) == (
            [],
            "",
            "",
            "",
            9.5,
        )

        # 6. `_async_expand_album_tail_uris`: <= 1 track, active-slot fallback, unmatched, and exception
        async def _browse_single(*_a: Any, **_kw: Any) -> list[dict[str, Any]]:
            return [{"type": "track", "id": "library://track/1", "active": True}]

        with patch.object(tts_queue, "async_browse_media_items", side_effect=_browse_single):
            assert (
                await tts_queue._async_expand_album_tail_uris(
                    hass, spk, "library://track/1", "Dirt", ("T", "A", "Dirt")
                )
                == []
            )

        async def _browse_active_match(*_a: Any, **_kw: Any) -> list[dict[str, Any]]:
            return [
                {"type": "track", "id": "library://track/10", "active": False},
                {"type": "track", "id": "library://track/11", "active": True},
                {"type": "track", "id": "library://track/12", "active": False},
            ]

        with patch.object(
            tts_queue, "async_browse_media_items", side_effect=_browse_active_match
        ):
            assert await tts_queue._async_expand_album_tail_uris(
                hass, spk, "library://track/other", "Dirt", ("T", "A", "Dirt")
            ) == ["library://track/11", "library://track/12"]

        async def _browse_no_match(*_a: Any, **_kw: Any) -> list[dict[str, Any]]:
            return [
                {"type": "track", "id": "library://track/10", "active": False},
                {"type": "track", "id": "library://track/11", "active": False},
            ]

        with patch.object(tts_queue, "async_browse_media_items", side_effect=_browse_no_match):
            assert (
                await tts_queue._async_expand_album_tail_uris(
                    hass, spk, "library://track/other", "Dirt", ("T", "A", "Dirt")
                )
                == []
            )

        async def _browse_err(*_a: Any, **_kw: Any) -> list[dict[str, Any]]:
            raise RuntimeError("browse failed")

        with patch.object(tts_queue, "async_browse_media_items", side_effect=_browse_err):
            assert (
                await tts_queue._async_expand_album_tail_uris(
                    hass, spk, "library://track/10", "Dirt", ("T", "A", "Dirt")
                )
                == []
            )

        # 7. No resumable URI -> `async_find_queue_resume_items` returns []
        empty_uris, empty_pos = await tts_queue.async_find_queue_resume_items(
            hass, spk, "/api/tts_proxy/ephemeral.mp3", 14.0
        )
        assert empty_uris == []
        assert empty_pos == 14.0

        # 8. `current_item` + distinct `next_item` fallback -> `[cur_uri, next_uri]`
        mock_service(
            hass,
            "music_assistant",
            "get_queue",
            lambda _call: {
                ma_ent: {
                    "elapsed_time": 21.0,
                    "current_item": {"media_item": {"uri": "library://track/50"}},
                    "next_item": {"media_item": {"uri": "library://track/51"}},
                }
            },
            supports_response=SupportsResponse.ONLY,
        )
        pair_uris, pair_pos = await tts_queue.async_find_queue_resume_items(
            hass, spk, "", 0.0
        )
        assert pair_uris == ["library://track/50", "library://track/51"]
        assert pair_pos == 21.0
    finally:
        clear_ma_counterpart_cache(hass)


async def test_tts_queue_play_media_container_expansion_and_validation(hass: Any) -> None:
    """Cover empty list guard, unavailable MA target, Sendspin validation error, and container expansion."""
    try:
        spk = "media_player.desk_speaker_music"
        ma_ent = "media_player.ma_desk"
        _seed_esphome_speaker(hass, entity_id=spk)
        _seed_ma_player(hass, ma_entity=ma_ent, state="unavailable")

        ma_calls: list[dict[str, Any]] = []
        ha_calls: list[dict[str, Any]] = []

        # 1. Empty cleaned media_id list returns immediately
        await tts_queue.async_play_media_with_ma_fallback(hass, spk, ["", "   "])
        assert ma_calls == []

        # 2. Unavailable MA player causes `_async_try_ma_play_media` -> False and raises ServiceValidationError on ESPHome
        mock_service(
            hass,
            "music_assistant",
            "play_media",
            lambda call: ma_calls.append(dict(call.data)),
        )
        with pytest.raises(ServiceValidationError):
            await tts_queue.async_play_media_with_ma_fallback(
                hass, spk, "library://track/1"
            )
        assert ma_calls == []

        # Bring MA player online
        hass.states.async_set(
            ma_ent,
            "idle",
            {
                "friendly_name": "Desk MA Player",
                "mass_player_type": "player",
                "active_queue": "ma_queue_desk",
            },
        )
        clear_ma_counterpart_cache(hass)

        # 3. Artist container failure triggers `_async_expand_and_play_container`
        def _fail_container_play(call: Any) -> None:
            ma_calls.append(dict(call.data))
            if call.data.get("media_type") in ("artist", "album"):
                raise RuntimeError("container play rejected")

        mock_service(hass, "music_assistant", "play_media", _fail_container_play)
        mock_service(
            hass,
            "media_player",
            "play_media",
            lambda call: ha_calls.append(dict(call.data)),
        )

        # 3a. Artist has no albums -> returns False -> ServiceValidationError on ESPHome
        async def _empty_browse(*_a: Any, **_kw: Any) -> list[dict[str, Any]]:
            return []

        with (
            patch.object(tts_queue, "async_browse_media_items", side_effect=_empty_browse),
            pytest.raises(ServiceValidationError),
        ):
            await tts_queue.async_play_media_with_ma_fallback(
                hass, spk, "library://artist/1", media_type="artist"
            )

        # 3b. Artist expands -> album -> tracks with radio_mode=True
        async def _expand_browse(
            _hass: Any, mode: str, *_a: Any, **_kw: Any
        ) -> list[dict[str, Any]]:
            if mode == "artist_albums":
                return [{"id": "library://album/67", "type": "album"}]
            return [
                {"id": "library://track/101", "type": "track"},
                {"id": "library://track/102", "type": "track"},
            ]

        ma_calls.clear()
        with patch.object(tts_queue, "async_browse_media_items", side_effect=_expand_browse):
            await tts_queue.async_play_media_with_ma_fallback(
                hass,
                spk,
                "library://artist/1",
                media_type="artist",
                radio_mode=True,
            )
        assert ma_calls[-1] == {
            "entity_id": ma_ent,
            "media_id": "library://track/101",
            "media_type": "track",
            "enqueue": "replace",
            "radio_mode": True,
        }

        # 3c. Artist expands -> album -> full track list with radio_mode=False & enqueue="next"
        ma_calls.clear()
        with patch.object(tts_queue, "async_browse_media_items", side_effect=_expand_browse):
            await tts_queue.async_play_media_with_ma_fallback(
                hass,
                spk,
                "library://artist/1",
                media_type="artist",
                enqueue="next",
                radio_mode=False,
            )
        assert ma_calls[-1] == {
            "entity_id": ma_ent,
            "media_id": ["library://track/101", "library://track/102"],
            "media_type": "track",
            "enqueue": "next",
        }

        # 3d. Album expansion raises during browse -> caught in `_async_expand_and_play_container`
        async def _raising_browse(*_a: Any, **_kw: Any) -> list[dict[str, Any]]:
            raise RuntimeError("browse crashed")

        with patch.object(tts_queue, "async_browse_media_items", side_effect=_raising_browse):
            await tts_queue.async_play_media_with_ma_fallback(
                hass, ma_ent, "library://album/67", media_type="album"
            )
        await hass.async_block_till_done()
        assert len(ha_calls) == 1
        assert ha_calls[0]["entity_id"] == ma_ent
        assert ha_calls[0]["media_content_id"] == "library://album/67"
    finally:
        clear_ma_counterpart_cache(hass)


async def test_tts_queue_wait_verify_transfer_and_idle_resume(hass: Any) -> None:
    """Cover reactive wait guards, transfer handoff/fallback/timeouts, and idle resume error paths."""
    try:
        local_spk = "media_player.local_desk_music"
        ma_local = "media_player.ma_local_desk"
        ma_target = "media_player.ma_kitchen"
        ma_other = "media_player.ma_patio"

        _seed_esphome_speaker(
            hass,
            entity_id=local_spk,
            mac="aa:bb:cc:dd:ee:21",
            slug="local_desk",
            device_name="Local Desk",
            state="idle",
        )
        _seed_ma_player(
            hass,
            ma_entity=ma_local,
            queue_id="ma_q_local",
            mac="aa:bb:cc:dd:ee:21",
            entry_id="entry_ma_xfer",
            state="playing",
        )
        _seed_ma_player(
            hass,
            ma_entity=ma_target,
            queue_id="ma_q_kitchen",
            mac="aa:bb:cc:dd:ee:22",
            entry_id="entry_ma_xfer",
            state="paused",
            extra_attrs={"media_position": 0.0},
        )
        _seed_ma_player(
            hass,
            ma_entity=ma_other,
            queue_id="ma_q_patio",
            mac="aa:bb:cc:dd:ee:23",
            entry_id="entry_ma_xfer",
            state="playing",
        )

        with (
            patch.object(tts_queue, "_SETTLE_WAIT_S", 0.01),
            patch.object(tts_queue, "_HANDOFF_TIMEOUT_S", 0.2),
            patch.object(tts_queue, "_NATIVE_PLAY_WAIT_S", 0.01),
            patch.object(tts_queue, "_COUNTERPART_PLAY_WAIT_S", 0.01),
        ):
            # 1. `_async_wait_entities_playing`: empty list & TOCTOU race guard
            assert await tts_queue._async_wait_entities_playing(hass, [], 0.01) is False

            def _flip_during_subscribe(
                _hass: Any, _entities: Any, _cb: Any
            ) -> Any:
                hass.states.async_set(local_spk, "playing", {})
                return lambda: None

            with patch.object(
                tts_queue, "async_track_state_change_event", side_effect=_flip_during_subscribe
            ):
                assert (
                    await tts_queue._async_wait_entities_playing(hass, [local_spk], 0.05)
                    is True
                )
            hass.states.async_set(local_spk, "idle", {})

            # 2. `_async_verify_transfer_position_and_state`: missing target entity -> early return
            await tts_queue._async_verify_transfer_position_and_state(
                hass,
                "media_player.nonexistent_a",
                "media_player.nonexistent_b",
                25.0,
                was_playing=True,
            )

            # 3. `_async_verify_transfer_position_and_state`: media_play & media_seek missing (ServiceNotFound caught)
            await tts_queue._async_verify_transfer_position_and_state(
                hass, ma_target, ma_target, 30.0, was_playing=True
            )

            # 4. `_async_verify_transfer_position_and_state`: outer asyncio.timeout caught
            async def _slow_wait(*_a: Any, **_kw: Any) -> bool:
                await asyncio.sleep(0.05)
                return False

            with (
                patch.object(tts_queue, "_HANDOFF_TIMEOUT_S", 0.001),
                patch.object(tts_queue, "_async_wait_entities_playing", side_effect=_slow_wait),
            ):
                await tts_queue._async_verify_transfer_position_and_state(
                    hass, ma_target, ma_target, 10.0, was_playing=True
                )

            # 5. `async_execute_ma_queue_transfer`: transfer_queue succeeds + local media_pause raises ServiceNotFound
            xfer_calls: list[dict[str, Any]] = []
            mock_service(
                hass,
                "music_assistant",
                "transfer_queue",
                lambda call: xfer_calls.append(dict(call.data)),
            )
            await tts_queue.async_execute_ma_queue_transfer(
                hass,
                local_speaker=local_spk,
                source_speaker=local_spk,
                target_speaker=ma_target,
                was_playing=True,
                handoff_position=0.0,
                media_content_id="library://track/1",
                media_content_type="track",
            )
            assert xfer_calls == [
                {
                    "entity_id": ma_target,
                    "source_player": ma_local,
                    "auto_play": True,
                }
            ]

            # 6. `transfer_queue` raises, `not is_from_local` -> pauses source + fallback play_media
            pause_calls: list[dict[str, Any]] = []
            ma_play_calls: list[dict[str, Any]] = []

            def _fail_xfer(_call: Any) -> None:
                raise RuntimeError("transfer_queue failed")

            mock_service(hass, "music_assistant", "transfer_queue", _fail_xfer)
            mock_service(
                hass,
                "media_player",
                "media_pause",
                lambda call: pause_calls.append(dict(call.data)),
            )
            mock_service(
                hass,
                "music_assistant",
                "play_media",
                lambda call: ma_play_calls.append(dict(call.data)),
            )
            await tts_queue.async_execute_ma_queue_transfer(
                hass,
                local_speaker=local_spk,
                source_speaker=ma_other,
                target_speaker=ma_target,
                was_playing=False,
                handoff_position=0.0,
                media_content_id="library://track/77",
                media_content_type="track",
            )
            await hass.async_block_till_done()
            assert {"entity_id": ma_other} in pause_calls
            assert ma_play_calls[-1]["entity_id"] == ma_target
            assert ma_play_calls[-1]["media_id"] == "library://track/77"

            # 7. Fallback play_media raises (unlinked ESPHome speaker) -> caught cleanly
            unlinked_esp = "media_player.unlinked_esp_music"
            _seed_esphome_speaker(
                hass,
                entity_id=unlinked_esp,
                mac="aa:bb:cc:dd:ee:29",
                slug="unlinked_esp",
                device_name="Unlinked ESP",
                state="idle",
            )
            await tts_queue.async_execute_ma_queue_transfer(
                hass,
                local_speaker=local_spk,
                source_speaker=ma_other,
                target_speaker=unlinked_esp,
                was_playing=False,
                handoff_position=0.0,
                media_content_id="library://track/88",
                media_content_type="track",
            )
            await hass.async_block_till_done()

            # 8. `_async_try_counterpart_native_play`: no MA / already tried, success, and exception
            hass.states.async_set(ma_local, "idle", {"active_queue": "ma_q_local"})
            assert (
                await tts_queue._async_try_counterpart_native_play(
                    hass, local_spk, None, [local_spk], already_tried_ma=False
                )
                is False
            )
            assert (
                await tts_queue._async_try_counterpart_native_play(
                    hass, local_spk, ma_local, [local_spk, ma_local], already_tried_ma=True
                )
                is False
            )

            def _play_sets_playing(call: Any) -> None:
                hass.states.async_set(call.data["entity_id"], "playing", {})

            mock_service(hass, "media_player", "media_play", _play_sets_playing)
            assert (
                await tts_queue._async_try_counterpart_native_play(
                    hass, local_spk, ma_local, [local_spk, ma_local], already_tried_ma=False
                )
                is True
            )

            hass.states.async_set(ma_local, "idle", {"active_queue": "ma_q_local"})

            def _play_raises(_call: Any) -> None:
                raise RuntimeError("media_play boom")

            mock_service(hass, "media_player", "media_play", _play_raises)
            assert (
                await tts_queue._async_try_counterpart_native_play(
                    hass, local_spk, ma_local, [local_spk, ma_local], already_tried_ma=False
                )
                is False
            )

            # 9. `async_resume_idle_speaker_queue`: no resumable URI, play_media error, and seek error
            generic_spk = "media_player.generic_sonos"
            hass.states.async_set(generic_spk, "idle", {"friendly_name": "Generic Sonos"})
            assert (
                await tts_queue.async_resume_idle_speaker_queue(
                    hass, generic_spk, "", 0.0, "music", immediate=True
                )
                is False
            )

            def _fail_ha_play(_call: Any) -> None:
                raise RuntimeError("play_media fail")

            mock_service(hass, "media_player", "play_media", _fail_ha_play)
            assert (
                await tts_queue.async_resume_idle_speaker_queue(
                    hass, generic_spk, "library://track/5", 20.0, "track", immediate=True
                )
                is False
            )

            ha_resume_calls: list[dict[str, Any]] = []
            mock_service(
                hass,
                "media_player",
                "play_media",
                lambda call: ha_resume_calls.append(dict(call.data)),
            )
            # `media_player.media_seek` is intentionally unregistered -> raises ServiceNotFound (caught)
            assert (
                await tts_queue.async_resume_idle_speaker_queue(
                    hass, generic_spk, "library://track/5", 25.0, "track", immediate=True
                )
                is True
            )
            assert len(ha_resume_calls) == 1
    finally:
        clear_ma_counterpart_cache(hass)


async def test_tts_queue_mutation_commands_and_next_shift(hass: Any) -> None:
    """Cover `async_handle_queue_mutation_command`, `_async_resolve_ma_queue_context`, and `_async_resolve_queue_next_shift`."""
    try:
        ma_ent = "media_player.ma_mut"
        # 1. Unhandled command & missing args & missing mass client
        assert await tts_queue.async_handle_queue_mutation_command(
            hass, "other_cmd", ma_ent, "q1", None
        ) == (False, False)
        assert await tts_queue.async_handle_queue_mutation_command(
            hass, "queue_play", None, "q1", None
        ) == (True, False)
        assert await tts_queue.async_handle_queue_mutation_command(
            hass, "queue_play", ma_ent, "", None
        ) == (True, False)
        assert await tts_queue.async_handle_queue_mutation_command(
            hass, "queue_play", ma_ent, "q1", None
        ) == (True, False)

        # 2. Seed MA entry with mass client and failing `music_assistant.get_queue`
        deleted: list[tuple[str, Any]] = []
        moved: list[tuple[str, str, int]] = []
        fetch_result: list[Any] = ["invalid_string_not_sequence_of_items"]
        mem_queue_obj: list[Any] = [SimpleNamespace(current_index=1)]

        async def _fetch_items(_qid: str, limit: int = 100, offset: int = 0) -> Any:
            _ = (limit, offset)
            return fetch_result[0]

        async def _delete_item(qid: str, item_id_or_index: Any) -> None:
            deleted.append((qid, item_id_or_index))

        async def _move_item(qid: str, queue_item_id: str, pos_shift: int = 1) -> None:
            moved.append((qid, queue_item_id, pos_shift))

        pqs = SimpleNamespace(
            fetch_player_queue_items=_fetch_items,
            delete_item=_delete_item,
            move_item=_move_item,
            get=lambda _qid: mem_queue_obj[0],
        )
        _seed_ma_player(
            hass,
            ma_entity=ma_ent,
            queue_id="ma_q_mut",
            mac="aa:bb:cc:dd:ee:31",
            entry_id="entry_ma_mut",
            mass_client=SimpleNamespace(player_queues=pqs),
        )

        def _raise_get_queue(_call: Any) -> dict[str, Any]:
            raise RuntimeError("get_queue offline")

        mock_service(
            hass,
            "music_assistant",
            "get_queue",
            _raise_get_queue,
            supports_response=SupportsResponse.ONLY,
        )

        # 3. `queue_delete` decrements cached `ma_queue_counts`
        get_domain_data(hass).ma_queue_counts[ma_ent] = 3
        assert await tts_queue.async_handle_queue_mutation_command(
            hass, "queue_delete", ma_ent, "qid_del", None
        ) == (True, True)
        assert deleted == [("ma_q_mut", "qid_del")]
        assert get_domain_data(hass).ma_queue_counts[ma_ent] == 2

        # 4. `queue_move` with invalid non-numeric `pos_shift` -> ValueError caught -> (True, False)
        assert await tts_queue.async_handle_queue_mutation_command(
            hass, "queue_move", ma_ent, "qid_x", "not_an_int"
        ) == (True, False)
        assert moved == []

        # 5. `_async_resolve_queue_next_shift`:
        # 5a. `fetch_player_queue_items` returns str -> breaks, falls back to `q_data["queue_items"]`, missing target -> 0
        q_items_data = {
            "queue_items": [
                {"queue_item_id": "q0"},
                {"queue_item_id": "q1"},
                {"queue_item_id": "q2"},
                {"queue_item_id": "q3"},
            ]
        }
        assert (
            await tts_queue._async_resolve_queue_next_shift(
                pqs, "ma_q_mut", q_items_data, "q_missing"
            )
            == 0
        )

        # 5b. `current_index` resolved from `pqs.get(queue_id)` (1); moving `q3` -> (1 + 1) - 3 = -1
        assert (
            await tts_queue._async_resolve_queue_next_shift(
                pqs, "ma_q_mut", q_items_data, "q3"
            )
            == -1
        )

        # 5c. `pqs.get` returns None -> scans `items_list` for `current_item.queue_item_id` ("q2" -> idx 2); moving `q0` -> 2
        mem_queue_obj[0] = None
        q_cur_scan = {
            "current_item": {"queue_item_id": "q2"},
            "items": q_items_data["queue_items"],
        }
        assert (
            await tts_queue._async_resolve_queue_next_shift(
                pqs, "ma_q_mut", q_cur_scan, "q0"
            )
            == 2
        )
    finally:
        clear_ma_counterpart_cache(hass)


async def test_tts_queue_assist_satellite_resolution_and_announcements(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Cover Assist Satellite lookup, device deduplication, announcement fallback, and MA media URL routing."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None

    # Register Assist Satellite on the hub's bound ESPHome device
    sat_pocket = "assist_satellite.pocket_assistant"
    register_entity(
        hass,
        sat_pocket,
        platform="esphome",
        device_id=coord.esphome_device_id,
        config_entry_id="esp_entry_pocket_assistant",
        unique_id="pocket_assist_sat",
        original_name="Assist Satellite",
    )
    hass.states.async_set(sat_pocket, "idle", {"friendly_name": "Pocket Satellite"})

    # Register MA counterpart matching Pocket Assistant's MAC (separate device_id!)
    ma_pocket = "media_player.ma_pocket"
    _seed_ma_player(
        hass,
        ma_entity=ma_pocket,
        queue_id="ma_q_pocket",
        mac="aa:bb:cc:dd:ee:01",
        entry_id="entry_ma_sat",
        state="idle",
    )

    # Register standalone device with 1 media_player + 1 assist_satellite
    extra_dev = register_device(
        hass,
        config_entry_id="esp_entry_extra_node",
        entry_domain="esphome",
        identifiers={("esphome", "bb:cc:dd:ee:ff:01")},
        name="Extra Node",
    )
    extra_spk = "media_player.extra_node_music"
    extra_sat = "assist_satellite.extra_node"
    register_entity(
        hass,
        extra_spk,
        platform="esphome",
        device_id=extra_dev.id,
        config_entry_id="esp_entry_extra_node",
        unique_id="extra_spk_uid",
    )
    register_entity(
        hass,
        extra_sat,
        platform="esphome",
        device_id=extra_dev.id,
        config_entry_id="esp_entry_extra_node",
        unique_id="extra_sat_uid",
    )
    hass.states.async_set(extra_spk, "idle", {})
    hass.states.async_set(extra_sat, "unavailable", {})

    # Register an MA-only speaker and a non-MA speaker (neither has an assist_satellite)
    ma_kitchen = "media_player.ma_kitchen"
    _seed_ma_player(
        hass,
        ma_entity=ma_kitchen,
        queue_id="ma_q_kitchen",
        mac="aa:bb:cc:dd:ee:55",
        entry_id="entry_ma_sat",
        state="idle",
    )
    generic_spk = "media_player.patio_amp"
    hass.states.async_set(generic_spk, "idle", {"friendly_name": "Patio Amp"})
    clear_ma_counterpart_cache(hass)

    # 1. `resolve_assist_satellite_entity`: direct satellite, unavailable satellite, device_id, MA counterpart via coordinator
    assert tts_queue.resolve_assist_satellite_entity(hass, sat_pocket) == sat_pocket
    assert tts_queue.resolve_assist_satellite_entity(hass, extra_sat) is None
    assert (
        tts_queue.resolve_assist_satellite_entity(hass, coord.esphome_device_id)
        == sat_pocket
    )
    assert tts_queue.resolve_assist_satellite_entity(hass, ma_pocket) == sat_pocket

    hass.states.async_set(extra_sat, "idle", {})
    assert tts_queue.resolve_assist_satellite_entity(hass, extra_spk) == extra_sat

    # 2. `async_announce_on_targets` early guards
    sat_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "assist_satellite",
        "announce",
        lambda call: sat_calls.append(dict(call.data)),
    )
    await tts_queue.async_announce_on_targets(hass, [], message="ignored")
    await tts_queue.async_announce_on_targets(hass, [coord.local_speaker])
    assert sat_calls == []

    # 3. Satellite announce succeeds, deduplicating empty strings & same-device MA counterpart, returning early (no fallbacks)
    await tts_queue.async_announce_on_targets(
        hass,
        ["", coord.local_speaker, ma_pocket],
        message="Dinner is ready",
        blocking=True,
    )
    assert sat_calls == [
        {"entity_id": [sat_pocket], "message": "Dinner is ready"}
    ]

    sat_calls.clear()
    await tts_queue.async_announce_on_targets(
        hass,
        [coord.local_speaker],
        media_url="https://ha.local/local/sounds/chime.mp3",
        blocking=True,
    )
    assert sat_calls == [
        {
            "entity_id": [sat_pocket],
            "media_id": "https://ha.local/local/sounds/chime.mp3",
        }
    ]

    # 4. Satellite announce raises -> falls back to MA `play_announcement` + HA `media_player.play_media(announce=True)`
    ma_ann_calls: list[dict[str, Any]] = []
    ha_play_calls: list[dict[str, Any]] = []

    def _fail_sat(_call: Any) -> None:
        raise RuntimeError("satellite unreachable")

    mock_service(hass, "assist_satellite", "announce", _fail_sat)
    mock_service(
        hass,
        "music_assistant",
        "play_announcement",
        lambda call: ma_ann_calls.append(dict(call.data)),
    )
    mock_service(
        hass,
        "media_player",
        "play_media",
        lambda call: ha_play_calls.append(dict(call.data)),
    )
    await tts_queue.async_announce_on_targets(
        hass,
        [coord.local_speaker, ma_kitchen, generic_spk, generic_spk],
        media_url="https://ha.local/local/sounds/doorbell.mp3",
        blocking=True,
    )
    assert ma_ann_calls == [
        {
            "entity_id": [ma_kitchen],
            "url": "https://ha.local/local/sounds/doorbell.mp3",
        }
    ]
    assert len(ha_play_calls) == 1
    assert set(ha_play_calls[0]["entity_id"]) == {generic_spk, coord.local_speaker}
    assert ha_play_calls[0]["announce"] is True

    # 5. Without `music_assistant.play_announcement`, MA speaker falls back to `media_player.play_media(announce=True)`
    hass.services.async_remove("music_assistant", "play_announcement")
    ha_play_calls.clear()
    await tts_queue.async_announce_on_targets(
        hass,
        [ma_kitchen],
        media_url="https://ha.local/local/sounds/bell.mp3",
        blocking=True,
    )
    assert ha_play_calls == [
        {
            "entity_id": [ma_kitchen],
            "media_content_id": "https://ha.local/local/sounds/bell.mp3",
            "media_content_type": "music",
            "announce": True,
        }
    ]

    # 6. Fallback TTS announcements enable HA TTS audio caching (`cache=True`)
    tts_calls: list[dict[str, Any]] = []
    mock_service(hass, "tts", "speak", lambda call: tts_calls.append(dict(call.data)))
    await tts_queue.async_announce_on_targets(
        hass,
        [generic_spk],
        message="Front door bell",
        tts_entity="tts.piper",
        blocking=True,
    )
    assert tts_calls == [
        {
            "entity_id": "tts.piper",
            "media_player_entity_id": [generic_spk],
            "message": "Front door bell",
            "cache": True,
        }
    ]

    assert await hass.config_entries.async_unload(entry.entry_id) is True


# ---------------------------------------------------------------------------
# browse.py coverage tests
# ---------------------------------------------------------------------------


async def test_browse_missing_ma_node_errors_track_lookup_and_speakers(hass: Any) -> None:
    """Cover no-MA guards, `_browse_ma_node` error, `async_lookup_ma_track_uri`, and `_browse_speakers`."""
    try:
        # 1. No Music Assistant integration loaded
        assert ma_browse._ma_browse_entity(hass, ["media_player.any"]) is None
        no_ma_tracks = await ma_browse.async_browse_media_items(
            hass, "album_tracks", "media_player.any", "", "", search="Dirt"
        )
        assert no_ma_tracks == ma_browse.text_slot(ma_browse.NO_MA_PLAYER_TEXT)
        assert (
            await ma_browse.async_browse_media_items(
                hass, "album", "media_player.any", "", ""
            )
            == []
        )
        assert await ma_browse.async_lookup_ma_track_uri(hass, "   ") == ""
        assert await ma_browse.async_lookup_ma_track_uri(hass, "Would?") == ""

        # 2. Seed MA player + test `_browse_ma_node` exception & `async_lookup_ma_track_uri` fallbacks
        ma_ent = "media_player.ma_browse_desk"
        _seed_ma_player(
            hass,
            ma_entity=ma_ent,
            queue_id="ma_q_browse",
            mac="aa:bb:cc:dd:ee:61",
            entry_id="entry_ma_browse",
        )

        def _raise_browse(_call: Any) -> dict[str, Any]:
            raise RuntimeError("browse timed out")

        mock_service(
            hass,
            "media_player",
            "browse_media",
            _raise_browse,
            supports_response=SupportsResponse.ONLY,
        )
        assert (
            await ma_browse._browse_ma_node(hass, ma_ent, "album", "library://album/1")
            is None
        )

        mock_service(
            hass,
            "music_assistant",
            "get_library",
            lambda _call: {
                "items": [
                    {"name": "Different Track", "uri": "library://track/1"},
                    {"name": "Would?", "uri": ""},
                    {
                        "name": "Would?",
                        "uri": "library://track/2",
                        "artists": [{"name": "Cover Band"}],
                    },
                ]
            },
            supports_response=SupportsResponse.ONLY,
        )
        assert (
            await ma_browse.async_lookup_ma_track_uri(
                hass, "Would?", artist="Alice In Chains"
            )
            == "library://track/2"
        )
        assert (
            await ma_browse.async_lookup_ma_track_uri(
                hass, "Would?", artist="Cover Band"
            )
            == "library://track/2"
        )

        # 3. `_browse_speakers` & `_format_local_speaker_name`
        hass.states.async_set(
            "media_player.local_music_suffix",
            "idle",
            {"friendly_name": "Kitchen Music"},
        )
        hass.states.async_set(
            "media_player.local_plain",
            "idle",
            {"friendly_name": "Patio Deck"},
        )
        hass.states.async_set("media_player.offline_spk", "unavailable", {})
        cast_ent = "media_player.non_ma_cast"
        register_entity(hass, cast_ent, platform="cast", unique_id="cast_uid_1")
        hass.states.async_set(cast_ent, "idle", {"friendly_name": "Cast TV"})

        slots_suffix = await ma_browse.async_browse_media_items(
            hass,
            "speakers",
            "media_player.local_music_suffix",
            "media_player.local_music_suffix",
            "media_player.local_music_suffix",
        )
        assert slots_suffix[0]["name"] == "Kitchen"
        assert slots_suffix[0]["active"] is True
        assert {s["id"] for s in slots_suffix} == {
            "media_player.local_music_suffix",
            ma_ent,
        }

        slots_plain = await ma_browse.async_browse_media_items(
            hass,
            "speakers",
            "media_player.local_plain",
            "media_player.local_plain",
            "media_player.local_plain",
        )
        assert slots_plain[0]["name"] == "Patio Deck"
    finally:
        clear_ma_counterpart_cache(hass)


async def test_browse_favorites_library_sort_artist_albums_album_tracks_and_podcasts(
    hass: Any,
) -> None:
    """Cover favorites, album sorting, artist albums, album tracks by name, podcast episodes, and unknown modes."""
    try:
        ma_ent = "media_player.ma_lib"
        _seed_ma_player(
            hass,
            ma_entity=ma_ent,
            queue_id="ma_q_lib",
            mac="aa:bb:cc:dd:ee:62",
            entry_id="entry_ma_lib",
        )

        # 1. Favorites & Library categories
        def _mock_get_library(call: Any) -> dict[str, Any]:
            mtype = call.data.get("media_type")
            fav = call.data.get("favorite")
            search = str(call.data.get("search") or "")
            if fav is True:
                if mtype == "playlist":
                    return {
                        "items": [
                            {"name": "Morning Mix", "uri": "library://playlist/1"},
                            {"name": "", "uri": "library://playlist/bad"},
                        ]
                    }
                if mtype == "track":
                    return {
                        "items": [
                            {
                                "name": "Nutshell",
                                "uri": "library://track/144",
                                "media_type": "track",
                            }
                        ]
                    }
                return {"items": []}

            if mtype == "album" and not search:
                return {
                    "items": [
                        {"name": "Beta", "uri": "library://album/2", "year": 1994},
                        {"name": "Alpha", "uri": "library://album/1", "year": 1992},
                        {"name": "Timeless", "uri": "library://album/3", "year": None},
                        {"name": "MissingUri", "uri": ""},
                    ]
                }
            if mtype == "artist":
                if search.lower() == "alice in chains":
                    return {
                        "items": [
                            {"name": "Alice In Chains", "uri": "library://artist/1"}
                        ]
                    }
                return {"items": []}
            if mtype == "album" and search.lower() == "alice in chains":
                return {
                    "items": [
                        {
                            "name": "Facelift",
                            "uri": "library://album/89",
                            "artists": [{"uri": "library://artist/1"}],
                        },
                        {
                            "name": "Dirt",
                            "uri": "library://album/67",
                            "artists": [{"uri": "library://artist/1"}],
                        },
                    ]
                }
            if mtype == "album" and search.lower() == "greatest hits":
                return {
                    "items": [
                        {
                            "name": "Greatest Hits",
                            "uri": "library://album/901",
                            "artists": [{"name": "Band A"}],
                        },
                        {
                            "name": "Greatest Hits",
                            "uri": "library://album/902",
                            "artists": [{"name": "Band B"}],
                        },
                    ]
                }
            if mtype == "podcast":
                if search.lower() == "tech talk":
                    return {
                        "items": [
                            {"name": "Tech Talk", "uri": "library://podcast/10"}
                        ]
                    }
                return {
                    "items": [
                        {"name": "Partial Match Pod", "uri": "library://podcast/20"}
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

        fav_slots = await ma_browse.async_browse_media_items(
            hass, "favorites", ma_ent, ma_ent, ma_ent
        )
        assert fav_slots == [
            {
                "name": "Morning Mix",
                "id": "library://playlist/1",
                "type": "playlist",
                "active": False,
            },
            {
                "name": "Nutshell",
                "id": "library://track/144",
                "type": "track",
                "active": False,
            },
        ]

        desc_albums = await ma_browse.async_browse_media_items(
            hass, "album", ma_ent, ma_ent, ma_ent, album_sort="year_desc"
        )
        assert [s["name"] for s in desc_albums] == [
            "Beta (1994)",
            "Alpha (1992)",
            "Timeless",
        ]

        asc_albums = await ma_browse.async_browse_media_items(
            hass, "album", ma_ent, ma_ent, ma_ent, album_sort="year"
        )
        assert [s["name"] for s in asc_albums] == [
            "Alpha (1992)",
            "Beta (1994)",
            "Timeless",
        ]

        name_albums = await ma_browse.async_browse_media_items(
            hass, "album", ma_ent, ma_ent, ma_ent, album_sort="name"
        )
        assert [s["name"] for s in name_albums] == [
            "Alpha (1992)",
            "Beta (1994)",
            "Timeless",
        ]

        # 2. Artist albums: empty search, not found, None node, and year-ordered children
        assert (
            await ma_browse.async_browse_media_items(
                hass, "artist_albums", ma_ent, ma_ent, ma_ent, search=""
            )
            == []
        )
        assert await ma_browse.async_browse_media_items(
            hass, "artist_albums", ma_ent, ma_ent, ma_ent, search="Nobody"
        ) == ma_browse.text_slot("Artist not found in the library")

        browse_payloads: dict[tuple[str, str], dict[str, Any]] = {}
        mock_service(
            hass,
            "media_player",
            "browse_media",
            lambda call: (
                {ma_ent: browse_payloads[key]}
                if (
                    key := (
                        str(call.data.get("media_content_type") or ""),
                        str(call.data.get("media_content_id") or ""),
                    )
                )
                in browse_payloads
                else {}
            ),
            supports_response=SupportsResponse.ONLY,
        )
        assert (
            await ma_browse.async_browse_media_items(
                hass, "artist_albums", ma_ent, ma_ent, ma_ent, search="Alice In Chains"
            )
            == []
        )

        browse_payloads[("artist", "library://artist/1")] = {
            "title": "Alice In Chains",
            "children": [
                {
                    "title": "Alice In Chains - Dirt",
                    "media_class": "album",
                    "media_content_id": "library://album/67",
                },
                {
                    "title": "Alice In Chains - Facelift",
                    "media_class": "album",
                    "media_content_id": "library://album/89",
                },
            ],
        }
        artist_albs = await ma_browse.async_browse_media_items(
            hass,
            "artist_albums",
            ma_ent,
            ma_ent,
            ma_ent,
            search="Alice In Chains",
            artist_album_sort="year",
        )
        assert [s["name"] for s in artist_albs] == ["Facelift", "Dirt"]

        # 3. Album tracks: empty search, not found, and artist disambiguation
        assert (
            await ma_browse.async_browse_media_items(
                hass, "album_tracks", ma_ent, ma_ent, ma_ent, search=""
            )
            == []
        )
        assert await ma_browse.async_browse_media_items(
            hass, "album_tracks", ma_ent, ma_ent, ma_ent, search="No Such Album"
        ) == ma_browse.text_slot("Album not found in the library")

        browse_payloads[("album", "library://album/902")] = {
            "title": "Greatest Hits",
            "children": [
                {
                    "title": "Band B - Hit One",
                    "media_content_id": "library://track/9021",
                }
            ],
        }
        disambig = await ma_browse.async_browse_media_items(
            hass,
            "album_tracks",
            ma_ent,
            ma_ent,
            ma_ent,
            search="Greatest Hits",
            fallback_artist="Band B",
        )
        assert [s["id"] for s in disambig] == ["library://track/9021"]

        # 4. Podcast episodes: empty search, positioned newest/oldest, unpositioned date-stripped oldest
        assert (
            await ma_browse.async_browse_media_items(
                hass, "podcast_episodes", ma_ent, ma_ent, ma_ent, search=""
            )
            == []
        )
        browse_payloads[("podcast", "library://podcast/10")] = {
            "title": "Tech Talk",
            "children": [
                {"name": "Ep 1", "uri": "library://ep/1", "position": 1},
                {"name": "Ep 3", "uri": "library://ep/3", "position": 3},
                {"name": "Ep 2", "uri": "library://ep/2", "position": 2},
            ],
        }
        pod_newest = await ma_browse.async_browse_media_items(
            hass,
            "podcast_episodes",
            ma_ent,
            ma_ent,
            ma_ent,
            search="Tech Talk",
            podcast_sort="newest",
        )
        assert [s["name"] for s in pod_newest] == ["Ep 3", "Ep 2", "Ep 1"]

        pod_oldest_pos = await ma_browse.async_browse_media_items(
            hass,
            "podcast_episodes",
            ma_ent,
            ma_ent,
            ma_ent,
            search="Tech Talk",
            podcast_sort="oldest",
        )
        assert [s["name"] for s in pod_oldest_pos] == ["Ep 1", "Ep 2", "Ep 3"]

        browse_payloads[("podcast", "library://podcast/20")] = {
            "title": "Partial Match Pod",
            "children": [
                {
                    "title": "2026-11-01 - First Ep",
                    "media_content_id": "library://ep/201",
                },
                {
                    "title": "2026-11-08: Second Ep",
                    "media_content_id": "library://ep/202",
                },
                {"title": "Empty Uri Ep", "media_content_id": ""},
            ],
        }
        pod_unpos = await ma_browse.async_browse_media_items(
            hass,
            "podcast_episodes",
            ma_ent,
            ma_ent,
            ma_ent,
            search="Partial",
            podcast_sort="oldest",
            fallback_title="2026-11-01 - First Ep",
        )
        assert pod_unpos == [
            {
                "name": "Second Ep",
                "id": "library://ep/202",
                "type": "podcast_episode",
                "active": False,
            },
            {
                "name": "First Ep",
                "id": "library://ep/201",
                "type": "podcast_episode",
                "active": True,
            },
        ]

        # 5. Unknown mode returns []
        assert (
            await ma_browse.async_browse_media_items(
                hass, "not_a_real_mode", ma_ent, ma_ent, ma_ent
            )
            == []
        )
    finally:
        clear_ma_counterpart_cache(hass)


async def test_browse_active_queue_error_and_fallback_branches(hass: Any) -> None:
    """Cover `_browse_active_queue`, `_fetch_ma_queue_metadata_and_items`, and `_fallback_queue_items_from_get_queue`."""
    try:
        # 1. No MA counterpart -> []
        assert (
            await ma_browse._browse_active_queue(hass, "media_player.unknown", "")
            == []
        )

        # 2. MA player registered, no get_queue service and no mass client -> []
        ma_ent = "media_player.ma_qerr"
        ma_entry = _seed_ma_player(
            hass,
            ma_entity=ma_ent,
            queue_id="ma_q_err",
            mac="aa:bb:cc:dd:ee:63",
            entry_id="entry_ma_qerr",
        )
        assert await ma_browse._browse_active_queue(hass, ma_ent, "") == []

        # 3. `get_queue` raises, `pqs.get` provides `current_item`, `fetch_player_queue_items` returns items incl. invalid
        async def _fetch_with_invalid(
            _qid: str, limit: int = 50, offset: int = 0
        ) -> list[dict[str, Any]]:
            _ = (limit, offset)
            return [
                {
                    "queue_item_id": "q1",
                    "media_item": {"name": "Song One", "uri": "library://track/1"},
                },
                {
                    "queue_item_id": "q2",
                    "media_item": {"name": "Song Two", "uri": "library://track/2"},
                },
                {"queue_item_id": "q_empty", "media_item": {"name": "", "uri": ""}},
            ]

        ma_entry.runtime_data = SimpleNamespace(
            mass=SimpleNamespace(
                player_queues=SimpleNamespace(
                    get=lambda _qid: SimpleNamespace(
                        current_item={"queue_item_id": "q2"}
                    ),
                    fetch_player_queue_items=_fetch_with_invalid,
                )
            )
        )

        def _raise_get_queue(_call: Any) -> dict[str, Any]:
            raise RuntimeError("get_queue down")

        mock_service(
            hass,
            "music_assistant",
            "get_queue",
            _raise_get_queue,
            supports_response=SupportsResponse.ONLY,
        )

        slots = await ma_browse._browse_active_queue(hass, ma_ent, "")
        assert [s["queue_item_id"] for s in slots] == ["q1", "q2"]
        assert [s["is_current"] for s in slots] == [False, True]
        assert get_domain_data(hass).ma_queue_counts[ma_ent] == 3

        # 4. `pqs.get` raises and `fetch_player_queue_items` raises -> fallback to `q_data["queue_items"]`
        def _raise_pqs_get(_qid: str) -> Any:
            raise RuntimeError("pqs.get boom")

        async def _raise_pqs_fetch(
            _qid: str, limit: int = 50, offset: int = 0
        ) -> list[dict[str, Any]]:
            _ = (limit, offset)
            raise RuntimeError("pqs.fetch boom")

        ma_entry.runtime_data = SimpleNamespace(
            mass=SimpleNamespace(
                player_queues=SimpleNamespace(
                    get=_raise_pqs_get,
                    fetch_player_queue_items=_raise_pqs_fetch,
                )
            )
        )
        mock_service(
            hass,
            "music_assistant",
            "get_queue",
            lambda _call: {
                ma_ent: {
                    "queue_id": "ma_q_err",
                    "queue_items": [
                        {
                            "queue_item_id": "fb1",
                            "media_item": {
                                "name": "Fallback Track",
                                "uri": "library://track/77",
                            },
                        }
                    ],
                }
            },
            supports_response=SupportsResponse.ONLY,
        )
        fb_slots = await ma_browse._browse_active_queue(
            hass, ma_ent, "Fallback Track"
        )
        assert len(fb_slots) == 1
        assert fb_slots[0]["id"] == "library://track/77"
        assert fb_slots[0]["is_current"] is True
        assert get_domain_data(hass).ma_queue_counts[ma_ent] == 1
    finally:
        clear_ma_counterpart_cache(hass)


# ---------------------------------------------------------------------------
# lyrics.py coverage tests
# ---------------------------------------------------------------------------


def test_lyrics_pure_parsers_extractors_and_bio_formatting() -> None:
    """Exercise `extract_item_dict`, `extract_artist_name`, LRC edge cases, meta/year extraction, and bio caching."""
    ma_lyrics.clear_lyrics_cache()
    try:
        class _AsDictObj:
            def as_dict(self) -> dict[str, Any]:
                return {"name": "FromAsDict"}

        class _ToDictObj:
            def as_dict(self) -> str:
                return "not_a_dict"

            def to_dict(self) -> dict[str, Any]:
                return {"name": "FromToDict"}

        class _BrokenToDictObj:
            name = "ReflectedName"
            media_type = SimpleNamespace(value="track")
            year = 1994

            def to_dict(self) -> dict[str, Any]:
                raise ValueError("cannot serialize")

        assert ma_lyrics.extract_item_dict(_AsDictObj()) == {"name": "FromAsDict"}
        assert ma_lyrics.extract_item_dict(_ToDictObj()) == {"name": "FromToDict"}
        assert ma_lyrics.extract_item_dict(_BrokenToDictObj()) == {
            "name": "ReflectedName",
            "media_type": "track",
            "year": 1994,
        }

        assert ma_lyrics.extract_artist_name({"artist": {"name": "Soundgarden"}}) == "Soundgarden"
        assert ma_lyrics.extract_artist_name({"artist": "Pearl Jam"}) == "Pearl Jam"
        assert ma_lyrics.extract_artist_name({}) == ""

        assert ma_lyrics._unwrap_logical_lines("[ti:Title]\n\n[ar:Band]\nReal line") == [
            "Real line"
        ]
        assert ma_lyrics.parse_lrc_lyrics("   ") == (False, [])
        assert ma_lyrics.parse_lrc_lyrics("[00:05.4]Tenths second") == (
            True,
            [{"t_ms": 5400, "text": "Tenths second"}],
        )
        assert ma_lyrics.parse_lrc_lyrics("[ti:OnlyMeta]\n[ar:Band]") == (False, [])

        class _MetaToDict:
            def to_dict(self) -> dict[str, Any]:
                return {"lyrics": "DictLyrics", "description": "DictDesc"}

        assert ma_lyrics._extract_meta_strings({"metadata": _MetaToDict()}) == (
            "DictLyrics",
            "DictDesc",
        )
        assert ma_lyrics._extract_meta_strings(
            {"metadata": SimpleNamespace(lyrics="NSLyrics", description="NSDesc")}
        ) == ("NSLyrics", "NSDesc")

        assert (
            ma_lyrics._extract_release_year({"year": True, "album": {"year": 1994}})
            == 1994
        )
        assert (
            ma_lyrics._extract_release_year({"year": 500, "album": {"year": None}})
            is None
        )

        # `_format_and_cache_bio_lines`: empty bio fallback + bonus lyrics caching
        lines = ma_lyrics._format_and_cache_bio_lines(
            "unknown_key",
            ("", "", "", ""),
            ("", "", None, "[00:02.00]Cached from bio"),
        )
        assert lines == ["Unknown Track by Unknown Artist"]
        cached = ma_lyrics.cache_get("unknown_key")
        assert cached is not None
        assert cached["bio_fallback"] == ["Unknown Track by Unknown Artist"]
        assert cached["bio_miss_until"] > 0
        assert cached["lyrics_payload"]["synced"] is True
        assert [row["text"] for row in cached["lyrics_payload"]["lines"]] == [
            "Cached from bio"
        ]
    finally:
        ma_lyrics.clear_lyrics_cache()


async def test_lyrics_ma_queue_controller_library_cache_and_bio(hass: Any) -> None:
    """Cover `call_ma_get_library`, queue item reading, MA controller lyrics, caching, and bio lookup."""
    ma_lyrics.clear_lyrics_cache()
    try:
        # 1. `call_ma_get_library` without service, then raising with `favorite=True`
        assert await ma_lyrics.call_ma_get_library(hass, "missing", "track") == []

        def _raise_lib(_call: Any) -> dict[str, Any]:
            raise RuntimeError("library error")

        mock_service(
            hass,
            "music_assistant",
            "get_library",
            _raise_lib,
            supports_response=SupportsResponse.ONLY,
        )
        assert (
            await ma_lyrics.call_ma_get_library(
                hass, "entry_x", "track", favorite=True
            )
            == []
        )

        # 2. `_read_current_queue_media_item`: unlinked speaker -> None
        assert (
            await ma_lyrics._read_current_queue_media_item(hass, "media_player.nope")
            is None
        )

        # 3. Seed MA player + controller metadata helper
        ctrl_response: list[Any] = [("plain fallback", "[00:10.00]Synced from controller")]
        ctrl_raise: list[bool] = [False]

        async def _get_track_lyrics(_item: Any) -> Any:
            if ctrl_raise[0]:
                raise RuntimeError("controller lyrics error")
            return ctrl_response[0]

        mem_q_state: list[Any] = [
            SimpleNamespace(
                current_item=SimpleNamespace(
                    media_item={"name": "InMemSong", "year": 1995}
                )
            )
        ]
        mem_q_raise: list[bool] = [False]

        def _pqs_get(_qid: str) -> Any:
            if mem_q_raise[0]:
                raise RuntimeError("in-memory queue error")
            return mem_q_state[0]

        ma_ent = "media_player.ma_lyrics_spk"
        ma_entry = _seed_ma_player(
            hass,
            ma_entity=ma_ent,
            queue_id="ma_q_lyrics",
            mac="aa:bb:cc:dd:ee:71",
            entry_id="entry_ma_lyrics",
            state="idle",
            mass_client=SimpleNamespace(
                player_queues=SimpleNamespace(get=_pqs_get),
                metadata=SimpleNamespace(get_track_lyrics=_get_track_lyrics),
            ),
        )

        # `_read_current_queue_media_item` via `music_assistant.get_queue`
        mock_service(
            hass,
            "music_assistant",
            "get_queue",
            lambda _call: {
                ma_ent: {
                    "current_item": {
                        "media_item": {
                            "name": "Black Hole Sun",
                            "year": 1994,
                            "metadata": {
                                "lyrics": "Plain embedded line",
                                "description": "Superunknown fourth studio album.",
                            },
                        }
                    }
                }
            },
            supports_response=SupportsResponse.ONLY,
        )
        got_item = await ma_lyrics._read_current_queue_media_item(hass, ma_ent)
        assert got_item is not None and got_item["name"] == "Black Hole Sun"

        # `_fetch_local_ma_controller_lyrics`: empty item, tuple LRC, tuple plain, str, and exception
        assert await ma_lyrics._fetch_local_ma_controller_lyrics(hass, None) == ""
        assert (
            await ma_lyrics._fetch_local_ma_controller_lyrics(hass, got_item)
            == "[00:10.00]Synced from controller"
        )
        ctrl_response[0] = ("plain only", "")
        assert (
            await ma_lyrics._fetch_local_ma_controller_lyrics(hass, got_item)
            == "plain only"
        )
        ctrl_response[0] = "  string lyric  "
        assert (
            await ma_lyrics._fetch_local_ma_controller_lyrics(hass, got_item)
            == "string lyric"
        )
        ctrl_raise[0] = True
        assert await ma_lyrics._fetch_local_ma_controller_lyrics(hass, got_item) == ""
        ctrl_raise[0] = False

        # `_search_library_track_lyrics`: early guards & skipping track without lyrics
        assert await ma_lyrics._search_library_track_lyrics(
            hass, None, "Song", "seed"
        ) == ("seed", None)
        assert await ma_lyrics._search_library_track_lyrics(
            hass, ma_entry.entry_id, "Song", "[00:01.00]Already synced"
        ) == ("[00:01.00]Already synced", None)

        mock_service(
            hass,
            "music_assistant",
            "get_library",
            lambda call: (
                {
                    "items": [
                        {"name": "Song", "metadata": {}},
                        {"name": "Song", "metadata": {"lyrics": "Found Plain"}},
                    ]
                }
                if call.data.get("media_type") == "track"
                else {"items": []}
            ),
            supports_response=SupportsResponse.ONLY,
        )
        found_plain, matched = await ma_lyrics._search_library_track_lyrics(
            hass, ma_entry.entry_id, "Song", ""
        )
        assert found_plain == "Found Plain"
        assert matched is not None

        # `async_fetch_track_lyrics`: empty clean_title -> returns empty
        assert await ma_lyrics.async_fetch_track_lyrics(hass, ma_ent, "") == (
            "",
            False,
            [],
        )

        # `async_fetch_track_lyrics`: queue media_item (year + album bio + plain lyrics) upgraded by controller LRC + bio cache seeded
        ctrl_response[0] = ("plain", "[00:12.00]In my eyes indisposed")
        tkey, synced, lines = await ma_lyrics.async_fetch_track_lyrics(
            hass, ma_ent, "Black Hole Sun|Soundgarden|Superunknown"
        )
        assert tkey == "Black Hole Sun|Soundgarden"
        assert synced is True
        assert lines == [{"t_ms": 12000, "text": "In my eyes indisposed"}]

        # Cached bio seeded by `async_fetch_track_lyrics` is served immediately by `browse_track_lyrics_or_bio`
        cached_bio_rows = await ma_lyrics.browse_track_lyrics_or_bio(
            hass,
            ma_entry.entry_id,
            ma_ent,
            "bio",
            "Black Hole Sun|Soundgarden|Superunknown",
            "",
        )
        cached_bio_texts = [r["name"] for r in cached_bio_rows]
        assert "Artist: Soundgarden" in cached_bio_texts
        assert "Album: Superunknown" in cached_bio_texts
        assert "Release: 1994" in cached_bio_texts
        assert "Album: Superunknown fourth studio album." in cached_bio_texts

        # `browse_track_lyrics_or_bio(mode="lyrics")` hit
        lyr_rows = await ma_lyrics.browse_track_lyrics_or_bio(
            hass,
            ma_entry.entry_id,
            ma_ent,
            "lyrics",
            "Black Hole Sun|Soundgarden|Superunknown",
            "",
        )
        assert lyr_rows == [
            {"name": "In my eyes indisposed", "id": "", "type": "text", "active": False}
        ]

        # Now make `get_queue` raise -> falls through to `pqs.get` in-memory media_item, then error
        def _raise_q(_call: Any) -> dict[str, Any]:
            raise RuntimeError("get_queue failed")

        mock_service(
            hass,
            "music_assistant",
            "get_queue",
            _raise_q,
            supports_response=SupportsResponse.ONLY,
        )
        mem_item = await ma_lyrics._read_current_queue_media_item(hass, ma_ent)
        assert mem_item == {"name": "InMemSong", "year": 1995}
        mem_q_raise[0] = True
        assert await ma_lyrics._read_current_queue_media_item(hass, ma_ent) is None
        mem_q_raise[0] = False

        # Negative lyrics cache (miss -> cached miss on second call) & `browse_track_lyrics_or_bio(mode="lyrics")` empty
        mock_service(
            hass,
            "music_assistant",
            "get_library",
            lambda _call: {"items": []},
            supports_response=SupportsResponse.ONLY,
        )
        ctrl_response[0] = ""
        mem_q_state[0] = None
        miss_rows = await ma_lyrics.browse_track_lyrics_or_bio(
            hass,
            ma_entry.entry_id,
            ma_ent,
            "lyrics",
            "Instrumental Track|NoBand|NoAlbum",
            "",
        )
        assert miss_rows == [
            {
                "name": "No lyrics found for this track.",
                "id": "",
                "type": "text",
                "active": False,
            }
        ]
        # Second call hits `lyrics_miss_until` negative cache
        assert await ma_lyrics.async_fetch_track_lyrics(
            hass, ma_ent, "Instrumental Track|NoBand|NoAlbum"
        ) == ("Instrumental Track|NoBand", False, [])

        # `_fetch_library_artist_album_bio`: None config_entry_id early return
        assert await ma_lyrics._fetch_library_artist_album_bio(
            hass, None, "Band", "Alb", ("seed_bio", 2000)
        ) == ("", "seed_bio", 2000)

        # `browse_track_lyrics_or_bio(mode="bio")`: reads queue item + artist library bio
        mem_q_state[0] = SimpleNamespace(
            current_item=SimpleNamespace(
                media_item={
                    "name": "Spoonman",
                    "year": 1994,
                    "metadata": {"lyrics": "Feel the rhythm"},
                }
            )
        )
        mock_service(
            hass,
            "music_assistant",
            "get_library",
            lambda call: (
                {
                    "items": [
                        {
                            "name": "Soundgarden",
                            "metadata": {"description": "Formed in Seattle in 1984."},
                        }
                    ]
                }
                if call.data.get("media_type") == "artist"
                else {"items": []}
            ),
            supports_response=SupportsResponse.ONLY,
        )
        artist_bio_rows = await ma_lyrics.browse_track_lyrics_or_bio(
            hass,
            ma_entry.entry_id,
            ma_ent,
            "bio",
            "Spoonman|Soundgarden|Superunknown",
            "",
        )
        assert "Formed in Seattle in 1984." in [r["name"] for r in artist_bio_rows]

        # `browse_track_lyrics_or_bio(mode="bio")`: negative bio fallback cache hit on 2nd call
        mem_q_state[0] = None
        mock_service(
            hass,
            "music_assistant",
            "get_library",
            lambda _call: {"items": []},
            supports_response=SupportsResponse.ONLY,
        )
        fb_1 = await ma_lyrics.browse_track_lyrics_or_bio(
            hass, ma_entry.entry_id, ma_ent, "bio", "Ghost|VoidArtist|VoidAlbum", ""
        )
        fb_2 = await ma_lyrics.browse_track_lyrics_or_bio(
            hass, ma_entry.entry_id, ma_ent, "bio", "Ghost|VoidArtist|VoidAlbum", ""
        )
        assert fb_1 == fb_2
        assert [r["name"] for r in fb_2] == ["Artist: VoidArtist", "Album: VoidAlbum"]
    finally:
        clear_ma_counterpart_cache(hass)
        ma_lyrics.clear_lyrics_cache()


async def test_lyrics_push_missing_service_failure_and_multichunk(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Cover `async_push_music_lyrics` missing ESPHome action, multi-chunk push, and service failure."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None

    # 1. Missing ESPHome device/action -> returns False
    orphan_coord = SimpleNamespace(
        esphome_device_id="missing_esphome_device_id",
        device_slug="orphan_node",
    )
    assert (
        await ma_lyrics.async_push_music_lyrics(
            hass,
            orphan_coord,
            req_id=1,
            track_key="Track|Artist",
            synced=True,
            lines=[{"t_ms": 1000, "text": "Hello"}],
        )
        is False
    )

    # 2. Multi-chunk push (> 32 lines -> 2 chunks)
    pushed: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        f"{coord.device_slug}_latter_set_music_lyrics",
        lambda call: pushed.append(dict(call.data)),
    )
    forty_lines = [{"t_ms": i * 1000, "text": f"Lyric line {i}"} for i in range(40)]
    assert (
        await ma_lyrics.async_push_music_lyrics(
            hass,
            coord,
            req_id=12,
            track_key="Track|Artist",
            synced=True,
            lines=forty_lines,
        )
        is True
    )
    assert len(pushed) == 2
    assert pushed[0]["chunk_index"] == 0
    assert pushed[0]["chunk_count"] == 2
    assert len(pushed[0]["lines"].split(RECORD_SEP)) == 32
    assert pushed[1]["chunk_index"] == 1
    assert pushed[1]["chunk_count"] == 2
    assert len(pushed[1]["lines"].split(RECORD_SEP)) == 8
    assert pushed[0]["lines"].split(RECORD_SEP)[0] == f"0{FIELD_SEP}Lyric line 0"

    # 3. ESPHome push service raises -> caught and returns False
    def _fail_push(_call: Any) -> None:
        raise RuntimeError("esphome node disconnected")

    mock_service(
        hass,
        "esphome",
        f"{coord.device_slug}_latter_set_music_lyrics",
        _fail_push,
    )
    assert (
        await ma_lyrics.async_push_music_lyrics(
            hass,
            coord,
            req_id=13,
            track_key="Track|Artist",
            synced=False,
            lines=[{"t_ms": -1, "text": "Line"}],
        )
        is False
    )

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_lyrics_schema_fallback_send_command_and_artist_disambiguation(
    hass: Any,
) -> None:
    """Cover `InvalidServerVersion` fallback, `send_command` item/track hydration, and artist matching."""
    ma_lyrics.clear_lyrics_cache()
    try:
        # 1. `InvalidServerVersion` (e.g. `require_schema=101`) falls back to `send_command`
        async def _raise_schema(_track: Any) -> Any:
            raise RuntimeError("require_schema=101 unsupported on schema 65")

        send_calls: list[tuple[str, dict[str, Any]]] = []

        async def _send_cmd(command: str, **kwargs: Any) -> Any:
            send_calls.append((command, kwargs))
            if command == "music/item_by_uri":
                return {
                    "item_id": "77",
                    "provider": "library",
                    "uri": kwargs["uri"],
                    "name": "Track Seventy Seven",
                    "provider_mappings": [
                        {"provider_instance": "tidal--1", "item_id": "t77", "priority": 20}
                    ],
                }
            if command == "music/tracks/get":
                return {
                    "item_id": kwargs["item_id"],
                    "provider": kwargs["provider_instance_id_or_domain"],
                    "name": "Track Seventy Seven",
                    "metadata": {"lrc_lyrics": "[00:08.00]From music/tracks/get"},
                }
            if command == "metadata/get_track_lyrics":
                return [None, None]
            return None

        async def _get_lib_tracks(search: str = "", limit: int = 10) -> list[dict[str, Any]]:
            _ = limit
            if search == "Same Name":
                return [
                    {
                        "item_id": "1",
                        "provider": "library",
                        "uri": "library://track/1",
                        "name": "Same Name",
                        "artists": [{"name": "Wrong Band"}],
                        "metadata": {"lrc_lyrics": "[00:01.00]Wrong lyrics"},
                    },
                    {
                        "item_id": "2",
                        "provider": "library",
                        "uri": "library://track/2",
                        "name": "Same Name",
                        "artists": [{"name": "Target Band"}],
                        "metadata": {"lrc_lyrics": "[00:02.00]Right lyrics"},
                    },
                ]
            if search == "Fallback Trigger":
                raise RuntimeError("get_library_tracks temporary failure")
            return []

        ma_ent = "media_player.ma_fallback_cov"
        ma_entry = _seed_ma_player(
            hass,
            ma_entity=ma_ent,
            queue_id="ma_q_fallback",
            mac="aa:bb:cc:dd:ee:72",
            entry_id="entry_ma_fallback",
            state="idle",
            mass_client=SimpleNamespace(
                player_queues=SimpleNamespace(get=lambda _qid: None),
                metadata=SimpleNamespace(get_track_lyrics=_raise_schema),
                music=SimpleNamespace(get_library_tracks=_get_lib_tracks),
                send_command=_send_cmd,
            ),
        )

        # `send_command` fallback for `music/item_by_uri`, `metadata/get_track_lyrics`, and `music/tracks/get`
        assert (
            await ma_lyrics._fetch_local_ma_controller_lyrics(
                hass, {"uri": "library://track/77", "name": "Track Seventy Seven"}
            )
            == "[00:08.00]From music/tracks/get"
        )
        assert [c[0] for c in send_calls] == [
            "music/item_by_uri",
            "metadata/get_track_lyrics",
            "music/tracks/get",
        ]

        # Artist disambiguation in `mass.music.get_library_tracks`
        lyr, matched = await ma_lyrics._search_library_track_lyrics(
            hass, ma_entry.entry_id, "Same Name", "", artist="Target Band"
        )
        assert lyr == "[00:02.00]Right lyrics"
        assert matched is not None and matched["item_id"] == "2"

        # `get_library_tracks` failure falls back cleanly to `music_assistant.get_library`
        mock_service(
            hass,
            "music_assistant",
            "get_library",
            lambda _call: {
                "items": [
                    {
                        "name": "Fallback Trigger",
                        "artists": [{"name": "Other"}],
                        "metadata": {},
                    },
                    {
                        "name": "Fallback Trigger",
                        "artists": [],
                        "metadata": {"lyrics": "Fallback plain"},
                    },
                ]
            },
            supports_response=SupportsResponse.ONLY,
        )
        fb_lyr, _ = await ma_lyrics._search_library_track_lyrics(
            hass, ma_entry.entry_id, "Fallback Trigger", "", artist="NoMatch"
        )
        assert fb_lyr == "Fallback plain"

        # Helper unit edge cases: `_parse_ma_lyrics_response`, `_extract_provider_track_ref`, `_pick_better_lyrics`
        assert ma_lyrics._parse_ma_lyrics_response(["plain", "[00:01.00]synced"]) == "[00:01.00]synced"
        assert ma_lyrics._parse_ma_lyrics_response(123) == ""
        assert ma_lyrics._extract_provider_track_ref({"provider_mappings": "bad"}) is None
        assert ma_lyrics._pick_better_lyrics("plain", "") == "plain"
        assert ma_lyrics._pick_better_lyrics("plain", "other plain") == "plain"
        assert ma_lyrics._pick_better_lyrics("plain", "[00:03.00]lrc") == "[00:03.00]lrc"
        assert await ma_lyrics._hydrate_ma_item_by_uri(None, "library://track/1") is None
        assert await ma_lyrics._hydrate_ma_item_by_uri(SimpleNamespace(), "library://track/1") is None
        assert await ma_lyrics._fetch_provider_track_dict(None, "tidal", "1") is None
        assert await ma_lyrics._fetch_provider_track_dict(SimpleNamespace(), "tidal", "1") is None
        assert await ma_lyrics._call_ma_get_track_lyrics(SimpleNamespace(), {}) == ""

        # Exception branches on `send_command` hydration / track fetch / lyrics call
        async def _always_fail(_command: str, **_kwargs: Any) -> Any:
            raise RuntimeError("ws error")

        fail_mass = SimpleNamespace(send_command=_always_fail)
        assert await ma_lyrics._hydrate_ma_item_by_uri(fail_mass, "library://track/1") is None
        assert await ma_lyrics._fetch_provider_track_dict(fail_mass, "tidal", "1") is None
        assert await ma_lyrics._call_ma_get_track_lyrics(fail_mass, {"item_id": "1", "provider": "tidal"}) == ""

        # `async_fetch_track_lyrics` distinct `matched_track` controller fallback when queue item fails
        ma_entry.runtime_data = SimpleNamespace(
            mass=SimpleNamespace(
                player_queues=SimpleNamespace(
                    get=lambda _qid: SimpleNamespace(
                        current_item=SimpleNamespace(
                            media_item={"name": "Distinct Song", "uri": "tidal://track/1"}
                        )
                    )
                ),
                music=SimpleNamespace(
                    get_library_tracks=lambda search="", limit=10: _async_return(
                        [
                            {
                                "item_id": "88",
                                "provider": "library",
                                "uri": "library://track/88",
                                "name": "Distinct Song",
                                "artists": [{"name": "Target Band"}],
                                "provider_mappings": [
                                    {"provider_instance": "tidal--1", "item_id": "t88", "priority": 10}
                                ],
                            }
                        ]
                    ),
                    get_track=lambda item_id, prov: _async_return(
                        {
                            "item_id": item_id,
                            "provider": prov,
                            "name": "Distinct Song",
                            "metadata": {"lrc_lyrics": "[00:09.00]Matched fallback"},
                        }
                    ),
                ),
                send_command=_always_fail,
            )
        )
        tkey_d, synced_d, lines_d = await ma_lyrics.async_fetch_track_lyrics(
            hass, ma_ent, "Distinct Song|Target Band"
        )
        assert tkey_d == "Distinct Song|Target Band"
        assert synced_d is True
        assert lines_d == [{"t_ms": 9000, "text": "Matched fallback"}]
    finally:
        clear_ma_counterpart_cache(hass)
        ma_lyrics.clear_lyrics_cache()


async def _async_return(val: Any) -> Any:
    return val
