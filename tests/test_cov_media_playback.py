"""Real-HA 2026.11 coverage tests for media playback, linking, state payload, and image cache."""

from __future__ import annotations

from datetime import timedelta
import io
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_IDLE, STATE_PAUSED, STATE_PLAYING, STATE_UNAVAILABLE
from homeassistant.core import State
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util
from PIL import Image
import pytest

from custom_components.latter import media_cache
from custom_components.latter.hub_registry import get_domain_data, peek_domain_data
from custom_components.latter.media import linking as linking_mod
from custom_components.latter.media.linking import (
    _arm_ma_reconnect_grace,
    _candidate_identity,
    _collect_bound_peer_ma_links,
    _collect_device_target_identity,
    _collect_mass_device_info,
    _collect_sendspin_from_config_entries,
    _extract_esphome_sendspin_info,
    _extract_mass_player_identity,
    _lookup_mass_player,
    _record_protocol_or_entity,
    async_heal_coordinator_ma_links,
    clear_ma_counterpart_cache,
    get_ma_mass_client,
    interpolate_speaker_position,
    resolve_ma_counterpart_entity,
    resolve_ma_queue_id_sync,
    safe_float,
    safe_opt_float,
    suggest_ma_player,
    suggest_ma_player_for,
)
from custom_components.latter.media.lyrics import clear_lyrics_cache
from custom_components.latter.media.playback import (
    VOLUME_SET_FLAG,
    VOLUME_STEP_FLAG,
    _async_apply_mass_favorite_mutation,
    async_execute_volume_action,
    execute_coordinator_media_command,
    normalize_repeat_mode,
    read_live_ma_queue_state,
    read_volume_from_target,
    resolve_canonical_volume,
    resolve_effective_favorite,
    resolve_raw_source_favorite,
    resolve_speaker_media_snapshot,
    set_coordinator_active_speaker,
)
from custom_components.latter.media.state_payload import (
    MEDIA_CAP_DEFAULT_TRANSPORT,
    MEDIA_CAP_PAUSE,
    MEDIA_CAP_VOLUME_SET,
    _read_muted_from_targets,
    build_active_media_payload,
    compute_media_caps,
)
from tests.helpers import (
    add_mock_entry,
    flush_debouncers,
    mock_service,
    register_common_target_services,
    register_device,
    register_entity,
)


def _encode_png(img: Image.Image) -> bytes:
    """Serialize a PIL image to PNG bytes."""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _seed_ma_player(
    hass: Any,
    *,
    entry_id: str = "entry_ma_cov",
    ma_entity: str = "media_player.ma_pocket",
    queue_id: str = "ma_queue_pocket",
    mac: str = "aa:bb:cc:dd:ee:01",
    runtime_data: Any = None,
    state: str = STATE_PLAYING,
    extra_attrs: dict[str, Any] | None = None,
) -> Any:
    """Register a loaded Music Assistant entry, MAC-matched Device, entity, and live state."""
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
    if runtime_data is not None:
        ma_entry.runtime_data = runtime_data

    ma_dev = register_device(
        hass,
        config_entry_id=ma_entry.entry_id,
        entry_domain="music_assistant",
        connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        identifiers={("music_assistant", queue_id)},
        name=f"MA {queue_id}",
        manufacturer="Latter",
    )
    register_entity(
        hass,
        ma_entity,
        platform="music_assistant",
        device_id=ma_dev.id,
        config_entry=ma_entry,
        unique_id=queue_id,
        original_name=f"MA {queue_id}",
    )
    attrs: dict[str, Any] = {
        "friendly_name": f"MA {queue_id}",
        "active_queue": queue_id,
        "media_title": "Would?",
        "media_artist": "Alice In Chains",
        "media_album_name": "Dirt",
        "media_content_id": "library://track/843",
        "media_content_type": "music",
        "supported_features": 1 | 2 | 4 | 8 | 16 | 32 | 1024 | 16384 | 262144 | 524288,
    }
    if extra_attrs is not None:
        attrs.update(extra_attrs)
    hass.states.async_set(ma_entity, state, attrs)
    return ma_entry


def test_media_cache_validation_mask_eviction_and_transcode_transforms() -> None:
    """Cover image dimension validation, circular mask eviction, rotations, darken, and circular mask."""
    media_cache.clear_http_caches()
    try:
        # Dimension ceiling rejection (width > MAX_IMAGE_SIDE and zero-width)
        with pytest.raises(ValueError, match="safety ceiling"):
            media_cache.validate_pil_image_dimensions(
                Image.new("RGB", (media_cache.MAX_IMAGE_SIDE + 1, 1))
            )
        with pytest.raises(ValueError, match="safety ceiling"):
            media_cache.validate_pil_image_dimensions(Image.new("RGB", (0, 16)))
        media_cache.validate_pil_image_dimensions(Image.new("RGB", (16, 16)))

        # Fill circular mask cache to _MAX_MASK_CACHE_ENTRIES (16), confirm hit, then trigger clear
        first_surfaces = media_cache.get_circular_mask_surfaces(16, 16)
        for idx in range(1, 16):
            media_cache.get_circular_mask_surfaces(16 + idx, 16 + idx)
        cached_surfaces = media_cache.get_circular_mask_surfaces(16, 16)
        assert cached_surfaces[0] is first_surfaces[0]
        assert cached_surfaces[1] is first_surfaces[1]
        assert len(media_cache._CIRCULAR_MASK_CACHE) == 16

        # 17th unique size clears prior entries before inserting the new surface pair
        media_cache.get_circular_mask_surfaces(48, 48)
        assert len(media_cache._CIRCULAR_MASK_CACHE) == 1
        assert (48, 48) in media_cache._CIRCULAR_MASK_CACHE

        # Asymmetric 32x16 source: left half red (240, 20, 20), right half blue (20, 20, 240)
        asym = Image.new("RGB", (32, 16), (20, 20, 240))
        asym.paste(Image.new("RGB", (16, 16), (240, 20, 20)), (0, 0))
        asym_png = _encode_png(asym)

        # 90 deg CW: red moves to top half (y < 16), blue to bottom half (y >= 16)
        jpg_90 = media_cache.transcode_to_baseline_jpeg(asym_png, 16, 32, rotate_deg=90)
        with Image.open(io.BytesIO(jpg_90)) as img_90:
            assert img_90.size == (16, 32)
            assert img_90.info.get("progressive", 0) == 0
            top_px = img_90.getpixel((8, 4))
            bot_px = img_90.getpixel((8, 28))
            assert isinstance(top_px, tuple) and isinstance(bot_px, tuple)
            assert top_px[0] > top_px[2]
            assert bot_px[2] > bot_px[0]

        # 180 deg: left becomes blue, right becomes red
        jpg_180 = media_cache.transcode_to_baseline_jpeg(asym_png, 32, 16, rotate_deg=180)
        with Image.open(io.BytesIO(jpg_180)) as img_180:
            assert img_180.size == (32, 16)
            left_px = img_180.getpixel((4, 8))
            right_px = img_180.getpixel((28, 8))
            assert isinstance(left_px, tuple) and isinstance(right_px, tuple)
            assert left_px[2] > left_px[0]
            assert right_px[0] > right_px[2]

        # 270 deg CW: red moves to bottom half, blue to top half
        jpg_270 = media_cache.transcode_to_baseline_jpeg(asym_png, 16, 32, rotate_deg=270)
        with Image.open(io.BytesIO(jpg_270)) as img_270:
            assert img_270.size == (16, 32)
            top_px_270 = img_270.getpixel((8, 4))
            bot_px_270 = img_270.getpixel((8, 28))
            assert isinstance(top_px_270, tuple) and isinstance(bot_px_270, tuple)
            assert top_px_270[2] > top_px_270[0]
            assert bot_px_270[0] > bot_px_270[2]

        # Darkening + circular mask compositing on a bright uniform 48x48 source
        bright_png = _encode_png(Image.new("RGB", (48, 48), (220, 220, 220)))
        jpg_bright = media_cache.transcode_to_baseline_jpeg(bright_png, 48, 48, darken=1.0)
        jpg_dark_circle = media_cache.transcode_to_baseline_jpeg(
            bright_png, 48, 48, circular_mask=True, darken=0.4
        )
        with Image.open(io.BytesIO(jpg_bright)) as img_b, Image.open(
            io.BytesIO(jpg_dark_circle)
        ) as img_dc:
            center_b = img_b.getpixel((24, 24))
            center_dc = img_dc.getpixel((24, 24))
            corner_dc = img_dc.getpixel((0, 0))
            assert (
                isinstance(center_b, tuple)
                and isinstance(center_dc, tuple)
                and isinstance(corner_dc, tuple)
            )
            assert sum(center_dc) < sum(center_b) * 0.6
            assert sum(corner_dc) < 30
    finally:
        media_cache.clear_http_caches()


async def test_playback_volume_parsers_repeat_and_favorite_helpers(hass: Any) -> None:
    """Cover volume fallback, canonical parser, action aliases, feature parsing, repeat, and favorite helpers."""
    register_common_target_services(hass)
    num_calls = mock_service(hass, "number", "set_value")
    mp_mute_calls = mock_service(hass, "media_player", "volume_mute")
    mp_up_calls = mock_service(hass, "media_player", "volume_up")

    # read_volume_from_target fallback_attrs path when target entity is absent
    assert read_volume_from_target(hass, "media_player.missing_vol", {"volume_level": 0.42}) == 0.42
    assert read_volume_from_target(hass, "media_player.missing_vol", {"volume_level": 1.8}) == 1.0

    # resolve_canonical_volume rejects invalid volume_pct and volume_level inputs
    assert resolve_canonical_volume(None, "bad_pct") is None  # type: ignore[arg-type]
    assert resolve_canonical_volume("bad_lvl", None) is None  # type: ignore[arg-type]
    assert resolve_canonical_volume(float("nan"), None) is None
    assert resolve_canonical_volume(0.35, None) == 0.35
    assert resolve_canonical_volume(None, 80) == 0.8

    # async_execute_volume_action rejects empty target and non-audio domains
    assert await async_execute_volume_action(hass, "", "up") is False
    assert await async_execute_volume_action(hass, "light.hallway", "up") is False

    # Volume action token aliases (volume_up / volume_down / volume_mute) + number unsupported action
    hass.states.async_set("number.amp_vol", "50", {"min": 0, "max": 100, "step": 5})
    assert await async_execute_volume_action(hass, "number.amp_vol", "volume_up") is True
    assert await async_execute_volume_action(hass, "number.amp_vol", "volume_down") is True
    assert await async_execute_volume_action(hass, "number.amp_vol", "volume_mute") is False
    await hass.async_block_till_done()
    assert [c.data["value"] for c in num_calls] == [55.0, 45.0]

    # Non-integer supported_features falls back to allowing set/mute/step
    hass.states.async_set(
        "media_player.bad_sf_spk",
        STATE_PLAYING,
        {"supported_features": "not_an_int", "is_volume_muted": False},
    )
    assert await async_execute_volume_action(hass, "media_player.bad_sf_spk", "volume_mute") is True
    assert await async_execute_volume_action(hass, "media_player.bad_sf_spk", "volume_up") is True
    await hass.async_block_till_done()
    assert len(mp_mute_calls) == 1
    assert mp_mute_calls[0].data == {
        "entity_id": "media_player.bad_sf_spk",
        "is_volume_muted": True,
    }
    assert len(mp_up_calls) == 1
    assert mp_up_calls[0].data == {"entity_id": "media_player.bad_sf_spk"}

    # normalize_repeat_mode boolean inputs
    assert normalize_repeat_mode(True) == "all"
    assert normalize_repeat_mode(False) == "off"

    # resolve_raw_source_favorite bool and int/str values
    assert resolve_raw_source_favorite({}, {"favorite": True}, None) is True
    assert resolve_raw_source_favorite({"media_favorite": False}, {}, True) is False
    assert resolve_raw_source_favorite({"is_favorite": "1"}, {}, None) is True
    assert resolve_raw_source_favorite({}, {"favorite": "false"}, True) is False
    assert resolve_raw_source_favorite({"favorite": 0}, {}, True) is False

    # _async_apply_mass_favorite_mutation edge branches
    assert await _async_apply_mass_favorite_mutation(None, "library://track/1", target_fav=True) is False
    assert (
        await _async_apply_mass_favorite_mutation(SimpleNamespace(), "", target_fav=True) is False
    )

    # Non-library URI resolves item_id & media_type via get_item_by_uri
    rem_calls_2arg: list[tuple[str, Any]] = []

    async def _get_item_by_uri(_uri: str) -> dict[str, Any]:
        return {"item_id": "99", "media_type": "track"}

    async def _rem_2arg(media_type: str, item_id: Any) -> None:
        rem_calls_2arg.append((media_type, item_id))

    ctrl_lookup = SimpleNamespace(
        get_item_by_uri=_get_item_by_uri,
        remove_item_from_favorites=_rem_2arg,
    )
    assert (
        await _async_apply_mass_favorite_mutation(
            ctrl_lookup, "spotify://track/abc", target_fav=False
        )
        is True
    )
    assert rem_calls_2arg == [("track", "99")]

    # Non-library URI without get_item_by_uri falls back to rsplit("/", 1)[-1]
    rem_calls_fb: list[tuple[str, Any]] = []

    async def _rem_fb(media_type: str, item_id: Any) -> None:
        rem_calls_fb.append((media_type, item_id))

    ctrl_fb = SimpleNamespace(remove_item_from_favorites=_rem_fb)
    assert (
        await _async_apply_mass_favorite_mutation(
            ctrl_fb, "spotify://track/fallback42", target_fav=False
        )
        is True
    )
    assert rem_calls_fb == [("track", "fallback42")]

    # Single-parameter remove_item_from_favorites(item_uri)
    rem_calls_1arg: list[str] = []

    async def _rem_1arg(uri: str) -> None:
        rem_calls_1arg.append(uri)

    ctrl_1arg = SimpleNamespace(remove_item_from_favorites=_rem_1arg)
    assert (
        await _async_apply_mass_favorite_mutation(
            ctrl_1arg, "library://track/55", target_fav=False
        )
        is True
    )
    assert rem_calls_1arg == ["library://track/55"]

    # Exception in mass.music returns False gracefully
    async def _add_boom(_uri: str) -> None:
        raise RuntimeError("upstream unavailable")

    ctrl_boom = SimpleNamespace(add_item_to_favorites=_add_boom)
    assert (
        await _async_apply_mass_favorite_mutation(
            ctrl_boom, "library://track/1", target_fav=True
        )
        is False
    )


async def test_playback_queue_state_listeners_and_coordinator_commands(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Cover snapshot normalization, position ticks, queue reads, shuffle/favorite fallbacks, join, clear, toggle, and lyrics."""
    entry, sys_obj, coord = await setup_latter_hub(hass, with_ble_tag=True)
    assert coord is not None
    tag_coord = sys_obj.coordinators["sub_tag"]

    pause_calls = mock_service(hass, "media_player", "media_pause")
    play_calls = mock_service(hass, "media_player", "media_play")
    shuffle_calls = mock_service(hass, "media_player", "shuffle_set")
    mute_calls = mock_service(hass, "media_player", "volume_mute")
    join_calls = mock_service(hass, "media_player", "join")
    clear_calls = mock_service(hass, "media_player", "clear_playlist")
    fav_add_svc_calls = mock_service(hass, "music_assistant", "add_to_favorites")
    fav_rem_svc_calls = mock_service(hass, "music_assistant", "remove_from_favorites")
    lyrics_push_calls = mock_service(
        hass, "esphome", f"{coord.device_slug}_latter_set_music_lyrics"
    )

    try:
        # 1. Empty target_spk (BLE tag coordinator) ignores non-lyrics commands
        await execute_coordinator_media_command(tag_coord, "pause")
        await hass.async_block_till_done()
        assert pause_calls == []

        # 2. Blank active speaker is ignored without mutating coordinator.active_speaker
        orig_spk = coord.active_speaker
        set_coordinator_active_speaker(coord, "   ")
        assert coord.active_speaker == orig_spk

        # 2b. Switching active speaker with transfer_queue=False never leaks previous speaker's
        #     playing track onto the newly selected idle speaker via transfer_hold_*
        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PLAYING,
            {
                "friendly_name": "Pocket Assistant",
                "media_title": "Local Track",
                "media_artist": "Local Artist",
                "media_album_name": "Local Album",
                "media_duration": 200,
                "media_position": 42,
            },
        )
        hass.states.async_set(
            "media_player.living_room_tv",
            STATE_IDLE,
            {"friendly_name": "Living Room TV", "volume_level": 0.4},
        )
        coord.transfer_hold_until = time.monotonic() + 15.0
        coord.transfer_hold_spinup_until = time.monotonic() + 15.0
        set_coordinator_active_speaker(
            coord, "media_player.living_room_tv", transfer_queue=False
        )
        assert coord.active_speaker == "media_player.living_room_tv"
        assert coord.last_speaker == "media_player.pocket_assistant_music"
        assert coord.transfer_hold_until == 0.0
        assert coord.transfer_hold_spinup_until == 0.0
        st_tv, attrs_tv = build_active_media_payload(coord)
        assert st_tv == STATE_IDLE
        assert attrs_tv["active_speaker"] == "media_player.living_room_tv"
        assert attrs_tv["speaker_name"] == "Living Room TV"
        assert attrs_tv["title"] == ""
        set_coordinator_active_speaker(
            coord, "media_player.pocket_assistant_music", transfer_queue=False
        )

        # 3. resolve_speaker_media_snapshot unusual state + podcast & audiobook media types
        hass.states.async_set(
            "media_player.pocket_assistant_music",
            "standby",
            {"media_title": "Ep 1", "media_content_type": "podcast_episode"},
        )
        snap_pod = resolve_speaker_media_snapshot(coord)
        assert snap_pod.state == STATE_IDLE
        assert snap_pod.media_type == "podcast"

        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PLAYING,
            {"media_title": "Chapter 1", "media_content_type": "audiobook"},
        )
        snap_book = resolve_speaker_media_snapshot(coord)
        assert snap_book.media_type == "audiobook"

        # 4. Position-only state tick clears cached payload and uses debounced notify only
        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PLAYING,
            {"media_title": "Tick Song", "media_position": 10, "volume_level": 0.5},
        )
        await flush_debouncers(hass)
        build_active_media_payload(coord)
        assert coord.cached_media_payload is not None
        with (
            patch.object(
                coord, "schedule_debounced_notify", wraps=coord.schedule_debounced_notify
            ) as mock_debounced,
            patch.object(
                coord, "async_notify_listeners", wraps=coord.async_notify_listeners
            ) as mock_full_notify,
        ):
            hass.states.async_set(
                "media_player.pocket_assistant_music",
                STATE_PLAYING,
                {"media_title": "Tick Song", "media_position": 15, "volume_level": 0.5},
            )
            await hass.async_block_till_done()
            assert mock_debounced.call_count == 1
            assert mock_full_notify.call_count == 0
            assert coord.cached_media_payload is None
        await flush_debouncers(hass)

        # 5. resolve_effective_favorite clears BOTH media_uri and title|artist keys once source updates,
        # and favorite overrides stay bounded at <= 32 entries (FIFO); offline MA TTL is 120s.
        assert linking_mod._MA_OFFLINE_CACHE_TTL_SECONDS == 120.0
        coord.media_favorite_overrides["library://track/77"] = (True, False)
        coord.media_favorite_overrides["song|artist"] = (True, False)
        assert (
            resolve_effective_favorite(coord, "Song", "Artist", "library://track/77", True)
            is True
        )
        assert "library://track/77" not in coord.media_favorite_overrides
        assert "song|artist" not in coord.media_favorite_overrides

        coord.media_favorite_overrides.clear()
        for idx in range(40):
            coord.media_favorite_overrides[f"library://track/old_{idx}"] = (True, False)
        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PLAYING,
            {
                "media_title": "Cap Song",
                "media_artist": "Cap Artist",
                "media_content_id": "library://track/cap_new",
            },
        )
        coord.active_speaker = "media_player.pocket_assistant_music"
        await execute_coordinator_media_command(coord, "favorite_toggle")
        assert len(coord.media_favorite_overrides) <= 32
        assert "library://track/old_0" not in coord.media_favorite_overrides
        assert "library://track/cap_new" in coord.media_favorite_overrides
        fav_add_svc_calls.clear()
        fav_rem_svc_calls.clear()

        # Pause command syncs persisted media position cleanly
        coord.last_media_position = 51.0
        await execute_coordinator_media_command(coord, "pause")
        assert coord._build_persisted_snapshot()["last_media_position"] == 51.0
        pause_calls.clear()

        # 6. read_live_ma_queue_state: raising pqs.get -> fallback tuple; list items + top-level favorite
        def _boom_get(_qid: str) -> Any:
            raise RuntimeError("queue offline")

        mass_boom = SimpleNamespace(
            player_queues=SimpleNamespace(get=_boom_get),
            players=SimpleNamespace(get=lambda _uid: None),
        )
        ma_entry = _seed_ma_player(
            hass,
            runtime_data=SimpleNamespace(mass=mass_boom),
            extra_attrs={
                "media_title": "Fav Song",
                "media_artist": "Fav Artist",
                "media_content_id": "library://track/321",
            },
        )
        await hass.async_block_till_done()
        get_domain_data(hass).ma_counterpart_cache.clear()
        assert read_live_ma_queue_state(hass, "media_player.ma_pocket") == (
            None,
            "",
            None,
            None,
            "",
            False,
        )

        live_queue_dict: dict[str, Any] = {
            "shuffle_enabled": True,
            "repeat_mode": "one",
            "items": [{"queue_item_id": "q1"}, {"queue_item_id": "q2"}, {"queue_item_id": "q3"}],
            "current_item": {
                "favorite": True,
                "uri": "library://track/500",
                "media_item": {"name": "Track 500"},
            },
            "is_dynamic": False,
        }
        mass_live = SimpleNamespace(
            player_queues=SimpleNamespace(
                get=lambda qid: live_queue_dict if qid == "ma_queue_pocket" else None
            ),
            players=SimpleNamespace(get=lambda _uid: None),
        )
        ma_entry.runtime_data = SimpleNamespace(mass=mass_live)
        assert read_live_ma_queue_state(hass, "media_player.ma_pocket") == (
            True,
            "one",
            True,
            3,
            "library://track/500",
            False,
        )

        # 7. shuffle_toggle falls back to s_attrs["shuffle"] then live_shuf when m_attrs omits shuffle
        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PLAYING,
            {"media_title": "Fav Song", "shuffle": True, "volume_level": 0.5},
        )
        await execute_coordinator_media_command(coord, "shuffle_toggle")
        await hass.async_block_till_done()
        assert len(shuffle_calls) == 1
        assert shuffle_calls[-1].data == {
            "entity_id": "media_player.ma_pocket",
            "shuffle": False,
        }

        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PLAYING,
            {"media_title": "Fav Song", "volume_level": 0.5},
        )
        await execute_coordinator_media_command(coord, "shuffle_toggle")
        await hass.async_block_till_done()
        assert len(shuffle_calls) == 2
        assert shuffle_calls[-1].data == {
            "entity_id": "media_player.ma_pocket",
            "shuffle": False,
        }

        # 8. favorite_toggle falls back to music_assistant.add_to_favorites / remove_from_favorites
        ma_entry.runtime_data = None
        await execute_coordinator_media_command(coord, "favorite_toggle")
        assert len(fav_add_svc_calls) == 1
        assert fav_add_svc_calls[0].data == {
            "entity_id": "media_player.ma_pocket",
            "media_id": "library://track/321",
        }
        await execute_coordinator_media_command(coord, "favorite_toggle")
        assert len(fav_rem_svc_calls) == 1
        assert fav_rem_svc_calls[0].data == {
            "entity_id": "media_player.ma_pocket",
            "media_id": "library://track/321",
        }

        # 9. play respects resuming_guard_until early return
        coord.resuming_guard_until = time.monotonic() + 60.0
        await execute_coordinator_media_command(coord, "play")
        await hass.async_block_till_done()
        assert play_calls == []
        coord.resuming_guard_until = 0.0

        # 10. toggle dispatches pause when playing and play when paused
        await execute_coordinator_media_command(coord, "toggle")
        await hass.async_block_till_done()
        assert len(pause_calls) == 1
        assert pause_calls[0].data == {"entity_id": "media_player.ma_pocket"}

        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PAUSED,
            {"media_title": "Fav Song", "volume_level": 0.5},
        )
        ma_st_cur = hass.states.get("media_player.ma_pocket")
        assert ma_st_cur is not None
        hass.states.async_set(
            "media_player.ma_pocket",
            STATE_PAUSED,
            dict(ma_st_cur.attributes),
        )
        await execute_coordinator_media_command(coord, "toggle")
        await hass.async_block_till_done()
        assert len(play_calls) == 1
        assert play_calls[0].data == {"entity_id": "media_player.ma_pocket"}

        # 11. mute_toggle falls back to ma_target when local speaker is unavailable
        hass.states.async_set("media_player.pocket_assistant_music", STATE_UNAVAILABLE)
        ma_st_mute = hass.states.get("media_player.ma_pocket")
        assert ma_st_mute is not None
        hass.states.async_set(
            "media_player.ma_pocket",
            STATE_PLAYING,
            {
                **dict(ma_st_mute.attributes),
                "is_volume_muted": False,
            },
        )
        await execute_coordinator_media_command(coord, "mute_toggle")
        await hass.async_block_till_done()
        assert len(mute_calls) == 1
        assert mute_calls[0].data == {
            "entity_id": "media_player.ma_pocket",
            "is_volume_muted": True,
        }
        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PLAYING,
            {"media_title": "Fav Song", "volume_level": 0.5},
        )

        # 12. join handles string and list group_members, MA translation, invalid prefix, self/dup skip
        kitchen_dev = register_device(
            hass,
            config_entry_id="esp_entry_kitchen",
            entry_domain="esphome",
            connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:02")},
            identifiers={("esphome", "aa:bb:cc:dd:ee:02")},
            name="Kitchen Speaker",
        )
        register_entity(
            hass,
            "media_player.kitchen_spk",
            platform="esphome",
            device_id=kitchen_dev.id,
            config_entry_id="esp_entry_kitchen",
        )
        hass.states.async_set("media_player.kitchen_spk", STATE_IDLE)
        _seed_ma_player(
            hass,
            entry_id="entry_ma_cov",
            ma_entity="media_player.ma_kitchen",
            queue_id="ma_queue_kitchen",
            mac="aa:bb:cc:dd:ee:02",
            state=STATE_IDLE,
        )
        await hass.async_block_till_done()
        get_domain_data(hass).ma_counterpart_cache.clear()

        await execute_coordinator_media_command(
            coord, "join", group_members="media_player.kitchen_spk"
        )
        await execute_coordinator_media_command(
            coord,
            "join",
            group_members=[
                "sensor.ignore_me",
                "media_player.ma_pocket",
                "media_player.kitchen_spk",
                "media_player.kitchen_spk",
                "media_player.unlinked_spk",
            ],
        )
        await execute_coordinator_media_command(coord, "join", group_members=["sensor.only_bad"])
        await hass.async_block_till_done()
        assert len(join_calls) == 2
        assert join_calls[0].data == {
            "entity_id": "media_player.ma_pocket",
            "group_members": ["media_player.ma_kitchen"],
        }
        assert join_calls[1].data == {
            "entity_id": "media_player.ma_pocket",
            "group_members": ["media_player.ma_kitchen", "media_player.unlinked_spk"],
        }

        # 13. clear_queue resets spinup guard, zeroes cached MA queue count, and calls clear_playlist
        coord.transfer_hold_spinup_until = time.monotonic() + 10.0
        get_domain_data(hass).ma_queue_counts["media_player.ma_pocket"] = 9
        await execute_coordinator_media_command(coord, "clear_queue")
        await hass.async_block_till_done()
        assert coord.transfer_hold_spinup_until == 0.0
        assert get_domain_data(hass).ma_queue_counts["media_player.ma_pocket"] == 0
        assert len(clear_calls) == 1
        assert clear_calls[0].data == {"entity_id": "media_player.ma_pocket"}

        # 14. lyrics_fetch invokes async_fetch_and_push_music_lyrics and pushes to ESPHome action
        await execute_coordinator_media_command(
            coord, "lyrics_fetch", media_id="Fav Song|Fav Artist"
        )
        assert coord.lyrics_watch_active is True
        assert len(lyrics_push_calls) >= 1
    finally:
        clear_lyrics_cache()
        clear_ma_counterpart_cache(hass)
        await flush_debouncers(hass)
        assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_state_payload_caps_fallbacks_artwork_and_queue_count(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Cover state_payload caps edge cases, mute fallbacks, spinup clear, idle restore, art retention, queue counts, and timestamps."""
    # Direct capability & mute helper checks
    hass.states.async_set("media_player.vol_unavail", STATE_UNAVAILABLE)
    hass.states.async_set("sensor.vol_dummy", "40")
    hass.states.async_set("number.vol_slider", "50", {"min": 0, "max": 100})

    bad_sf_state = State("media_player.bad_sf", STATE_PLAYING, {"supported_features": "bad"})
    assert (
        compute_media_caps(hass, bad_sf_state, None, None, "media_player.vol_unavail")
        == MEDIA_CAP_DEFAULT_TRANSPORT
    )
    pause_only_state = State("media_player.pause_only", STATE_PLAYING, {"supported_features": 1})
    assert compute_media_caps(hass, pause_only_state, None, None, "sensor.vol_dummy") == MEDIA_CAP_PAUSE
    assert compute_media_caps(hass, None, None, None, "number.vol_slider") == MEDIA_CAP_VOLUME_SET

    assert _read_muted_from_targets(hass, "", {"is_volume_muted": True}, {}) is True
    assert _read_muted_from_targets(hass, "", {}, {"is_volume_muted": True}) is True
    assert _read_muted_from_targets(hass, "", {}, {}) is False

    entry, _sys_obj, coord = await setup_latter_hub(hass)
    assert coord is not None
    try:
        # 1. Spinup guard clears on playing; int queue_count, datetime position_updated_at, speaker shuffle, art cache
        updated_dt = dt_util.utcnow()
        coord.transfer_hold_spinup_until = time.monotonic() + 15.0
        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PLAYING,
            {
                "friendly_name": "Pocket Speaker",
                "media_title": "Art Track",
                "media_artist": "Art Artist",
                "media_album_name": "Art Album",
                "media_duration": 180,
                "media_position": 25,
                "media_position_updated_at": updated_dt,
                "entity_picture": "/api/media_player_proxy/media_player.pocket_assistant_music?token=t1",
                "volume_level": 0.55,
                "shuffle": True,
                "queue_count": 7,
                "is_volume_muted": True,
            },
        )
        coord.cached_media_payload = None
        st1, attrs1 = build_active_media_payload(coord)
        assert st1 == STATE_PLAYING
        assert coord.transfer_hold_spinup_until == 0.0
        assert attrs1["queue_count"] == 7
        assert attrs1["position_updated_at"] == int(updated_dt.timestamp())
        assert attrs1["shuffle"] is True
        assert attrs1["muted"] is True
        first_art_url = attrs1["art_url"]
        assert first_art_url

        # 2. Missing entity_picture on same track retains cached art_url; list items count; ISO & invalid timestamps
        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PLAYING,
            {
                "friendly_name": "Pocket Speaker",
                "media_title": "Art Track",
                "media_artist": "Art Artist",
                "media_album_name": "Art Album",
                "media_duration": 180,
                "media_position": 30,
                "media_position_updated_at": "2026-11-22T12:00:00+00:00",
                "volume_level": 0.55,
                "items": ["q1", "q2", "q3"],
            },
        )
        coord.cached_media_payload = None
        _st2, attrs2 = build_active_media_payload(coord)
        assert attrs2["art_url"] == first_art_url
        assert attrs2["queue_count"] == 3
        assert attrs2["position_updated_at"] > 0

        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PLAYING,
            {
                "friendly_name": "Pocket Speaker",
                "media_title": "Art Track",
                "media_artist": "Art Artist",
                "media_album_name": "Art Album",
                "media_position_updated_at": "not-a-datetime",
                "volume_level": 0.55,
            },
        )
        coord.cached_media_payload = None
        _st2b, attrs2b = build_active_media_payload(coord)
        assert attrs2b["position_updated_at"] == 0

        # 3. Idle local speaker without title restores last_media_* snapshot fields
        coord.transfer_hold_until = 0.0
        coord.last_media_title = "Remembered Song"
        coord.last_media_artist = "Remembered Artist"
        coord.last_media_album = "Remembered Album"
        coord.last_media_duration = 215.0
        coord.last_media_position = 64.0
        coord.last_media_type = "podcast"
        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_IDLE,
            {"volume_level": 0.5},
        )
        coord.cached_media_payload = None
        st3, attrs3 = build_active_media_payload(coord)
        assert st3 == STATE_IDLE
        assert attrs3["title"] == "Remembered Song"
        assert attrs3["artist"] == "Remembered Artist"
        assert attrs3["album"] == "Remembered Album"
        assert attrs3["duration"] == 215.0
        assert attrs3["position"] == 64.0
        assert attrs3["media_type"] == "podcast"

        # 4. Volume & mute fall back to MA counterpart attributes when local speaker omits them
        _seed_ma_player(
            hass,
            entry_id="entry_ma_state_payload",
            ma_entity="media_player.ma_pocket",
            queue_id="ma_queue_pocket",
            mac="aa:bb:cc:dd:ee:01",
            extra_attrs={
                "volume_level": 0.37,
                "is_volume_muted": True,
                "media_title": "MA Volume Track",
            },
        )
        hass.states.async_set(
            "media_player.pocket_assistant_music",
            STATE_PLAYING,
            {"media_title": "MA Volume Track"},
        )
        await hass.async_block_till_done()
        get_domain_data(hass).ma_counterpart_cache.clear()
        coord.cached_media_payload = None
        _st4, attrs4 = build_active_media_payload(coord)
        assert attrs4["volume"] == 0.37
        assert attrs4["muted"] is True
    finally:
        clear_ma_counterpart_cache(hass)
        await flush_debouncers(hass)
        assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_linking_helpers_sendspin_mass_identity_and_grace_timer(hass: Any) -> None:
    """Cover linking parsers, direct runtime mass lookup, Sendspin/protocol extraction, via_device, and grace expiry."""
    # 1. clear_ma_counterpart_cache is a safe no-op before domain data exists
    assert peek_domain_data(hass) is None
    clear_ma_counterpart_cache(hass)
    assert peek_domain_data(hass) is None

    # 2. Numeric & position interpolation & suggest_ma_player edge cases
    assert safe_opt_float("not_a_float") is None
    assert safe_opt_float(object()) is None
    assert safe_float("bad", 3.5) == 3.5

    assert interpolate_speaker_position(None) == 0.0
    st_clamped = State(
        "media_player.interp_clamped",
        STATE_PLAYING,
        {
            "media_duration": 100.0,
            "media_position": 20.0,
            "media_position_updated_at": dt_util.utcnow() - timedelta(seconds=120),
        },
    )
    assert interpolate_speaker_position(st_clamped) == 100.0
    st_unbounded = State(
        "media_player.interp_open",
        STATE_PLAYING,
        {
            "media_duration": 0.0,
            "media_position": 10.0,
            "media_position_updated_at": dt_util.utcnow() - timedelta(seconds=15),
        },
    )
    assert interpolate_speaker_position(st_unbounded) >= 24.0

    assert suggest_ma_player((None, "BoardX"), [("media_player.a", "Latter", "BoardX")]) is None
    assert suggest_ma_player(("Latter", ""), [("media_player.a", "Latter", "BoardX")]) is None

    # 3. _lookup_mass_player error handling and iterable list fallback
    class _BoomPlayers:
        def get(self, _pid: str) -> Any:
            raise RuntimeError("lookup failed")

    assert _lookup_mass_player(SimpleNamespace(players=_BoomPlayers()), "p1") is None
    iter_mass = SimpleNamespace(
        players=[{"player_id": "p0"}, {"player_id": "p2", "name": "Found"}]
    )
    assert _lookup_mass_player(iter_mass, "p2") == {"player_id": "p2", "name": "Found"}
    assert _lookup_mass_player(iter_mass, "missing") is None

    # 4. get_ma_mass_client direct runtime_data (no .mass wrapper) & resolve_ma_queue_id_sync
    direct_runtime = SimpleNamespace(
        player_queues=SimpleNamespace(
            get=lambda qid: {"queue_id": qid} if qid == "grp_queue_9" else None
        ),
        players=SimpleNamespace(
            get=lambda uid: SimpleNamespace(active_source="grp_queue_9")
            if uid == "uid_player_9"
            else None
        ),
    )
    ma_entry = add_mock_entry(
        hass,
        domain="music_assistant",
        title="Music Assistant Direct",
        entry_id="entry_ma_direct",
        data={},
    )
    if hasattr(ma_entry, "mock_state"):
        ma_entry.mock_state(hass, ConfigEntryState.LOADED)
    ma_entry.runtime_data = direct_runtime
    assert get_ma_mass_client(hass) is direct_runtime

    assert resolve_ma_queue_id_sync(hass, "") == ""
    ma_ent = register_entity(
        hass,
        "media_player.ma_uid_only",
        platform="music_assistant",
        config_entry=ma_entry,
        unique_id="uid_player_9",
    )
    assert resolve_ma_queue_id_sync(hass, "media_player.ma_uid_only", direct_runtime) == "grp_queue_9"

    err_mass = SimpleNamespace(players=_BoomPlayers(), player_queues=SimpleNamespace(get=lambda _: None))
    assert resolve_ma_queue_id_sync(hass, "media_player.ma_uid_only", err_mass) == "uid_player_9"

    # 5. Sendspin collection from config entries, hass.data["esphome"] map, and missing device ID
    esp_ss = add_mock_entry(
        hass,
        domain="esphome",
        title="Sendspin Node",
        entry_id="esp_sendspin_1",
        data={"device_name": "sendspin_node"},
        version=1,
    )
    esp_ss.runtime_data = SimpleNamespace(
        device_capabilities={"sendspin": {"client_id": "", "feature_flags": 7}}
    )
    blank_esp = SimpleNamespace(domain="esphome", entry_id="")
    cids, pending = _collect_sendspin_from_config_entries(
        hass, [None, ma_entry, blank_esp, esp_ss, esp_ss]
    )
    assert cids == set()
    assert pending is True

    hass.data["esphome"] = SimpleNamespace(sendspin_client_ids={"ss_client_42": esp_ss.entry_id})
    try:
        cids_mapped, pending_mapped = _collect_sendspin_from_config_entries(hass, [esp_ss])
        assert cids_mapped == {"ss_client_42"}
        assert pending_mapped is False
    finally:
        hass.data.pop("esphome", None)

    assert _extract_esphome_sendspin_info(hass, ["missing_device_id"]) == (set(), False)

    # 6. Protocol/device-info helpers & full _extract_mass_player_identity + known_protocols fallback
    buckets: tuple[set[str], set[str], set[str]] = (set(), set(), set())
    _record_protocol_or_entity("", "sendspin", buckets)
    _record_protocol_or_entity("native", "sendspin", buckets)
    assert buckets == (set(), set(), set())
    _record_protocol_or_entity("media_player.esp_1", "hass_players", buckets)
    _record_protocol_or_entity("aa:bb:cc:dd:ee:88", "sendspin", buckets)
    assert buckets[0] == {"aa:bb:cc:dd:ee:88"}
    assert buckets[1] == {"media_player.esp_1"}
    assert buckets[2] == {"aa:bb:cc:dd:ee:88"}

    info_macs: set[str] = set()
    info_protos: set[str] = set()
    _collect_mass_device_info(None, info_macs, info_protos)
    assert info_macs == set() and info_protos == set()
    _collect_mass_device_info(
        {"mac_address": "11:22:33:44:55:66", "identifiers": ["not_a_mapping"]},
        info_macs,
        info_protos,
    )
    assert info_macs == {"11:22:33:44:55:66"}
    _collect_mass_device_info(
        {"identifiers": {"blank": "", "device_uuid": "uuid-abc-123", "mac": "aa:bb:cc:dd:ee:77"}},
        info_macs,
        info_protos,
    )
    assert "aa:bb:cc:dd:ee:77" in info_macs
    assert info_protos == {"uuid-abc-123"}

    assert _extract_mass_player_identity(hass, None) == (set(), set(), set())
    rich_player = {
        "player_id": "aa:bb:cc:dd:ee:44",
        "provider": "sendspin",
        "device_info": {
            "mac_address": "aa:bb:cc:dd:ee:45",
            "identifiers": {"empty": "", "uuid": "dev-uuid-9"},
        },
        "protocols": [
            {"protocol_id": "native", "domain": "sendspin"},
            {"protocol_id": "media_player.esp_linked", "domain": "hass_players"},
            {"protocol_id": "aa:bb:cc:dd:ee:46", "domain": "sendspin"},
        ],
        "output_protocols": [
            {
                "output_protocol_id": "out_proto_9",
                "protocol_domain": "sendspin",
                "derived_from": "aa:bb:cc:dd:ee:47",
            }
        ],
    }
    ma_entry.runtime_data = SimpleNamespace(
        player_queues=SimpleNamespace(get=lambda _qid: None),
        players=SimpleNamespace(get=lambda uid: rich_player if uid == "uid_player_9" else None),
    )
    macs, ha_ents, protos = _extract_mass_player_identity(hass, ma_ent)
    assert {"aa:bb:cc:dd:ee:44", "aa:bb:cc:dd:ee:45", "aa:bb:cc:dd:ee:46", "aa:bb:cc:dd:ee:47"} <= macs
    assert ha_ents == {"media_player.esp_linked"}
    assert {"dev-uuid-9", "out_proto_9", "aa:bb:cc:dd:ee:44", "aa:bb:cc:dd:ee:47"} <= protos

    # First _candidate_identity call caches ma_known_protocols; second recovers them after runtime vanishes
    _c_macs1, _c_ha1, c_protos1 = _candidate_identity(hass, ma_ent, None)
    assert "out_proto_9" in c_protos1
    ma_entry.runtime_data = None
    _c_macs2, _c_ha2, c_protos2 = _candidate_identity(hass, ma_ent, None)
    assert "out_proto_9" in c_protos2

    # 7. _collect_device_target_identity propagates via_device_id into target.dev_ids
    parent_dev = register_device(
        hass,
        config_entry_id=esp_ss.entry_id,
        identifiers={("esphome", "parent_bridge")},
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:10")},
        name="Parent Bridge",
    )
    child_dev = register_device(
        hass,
        config_entry_id=esp_ss.entry_id,
        identifiers={("esphome", "child_node")},
        via_device_id=parent_dev.id,
        name="Child Node",
    )
    target_ident = _collect_device_target_identity(hass, esphome_device_id=child_dev.id)
    assert parent_dev.id in target_ident.dev_ids

    # 8. _arm_ma_reconnect_grace ignores empty entity_id and runs _on_grace_expired cleanup
    _arm_ma_reconnect_grace(hass, "")
    captured: list[Any] = []
    domain_data = get_domain_data(hass)
    with patch.object(
        linking_mod,
        "async_call_later",
        side_effect=lambda _hass, _delay, cb: (captured.append(cb), lambda: None)[1],
    ):
        _arm_ma_reconnect_grace(hass, "media_player.ma_uid_only")
        assert len(captured) == 1
        domain_data.ma_reconnect_until["media_player.ma_uid_only"] = time.monotonic() - 1.0
        domain_data.ma_counterpart_cache["media_player.stale"] = (None, False, time.monotonic())
        captured[0](dt_util.utcnow())
        assert domain_data.ma_reconnect_timer is None
        assert "media_player.ma_uid_only" not in domain_data.ma_reconnect_until
        assert domain_data.ma_counterpart_cache == {}

    clear_ma_counterpart_cache(hass)


async def test_linking_hub_peers_pending_sendspin_cache_and_healing(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Cover peer exclusion, BLE-tag skip, pending Sendspin grace arming, malformed cache eviction, re-entrancy guard, and heal rebind."""
    entry, sys_obj, coord = await setup_latter_hub(hass, with_ble_tag=True)
    assert coord is not None
    tag_coord = sys_obj.coordinators["sub_tag"]
    domain_data = get_domain_data(hass)

    try:
        # 1. suggest_ma_player_for returns None when coordinator has no bound ESPHome device
        assert suggest_ma_player_for(hass, tag_coord) is None

        # 2. _collect_bound_peer_ma_links skips matching exclude_esp_id and non-Device subentries
        claimed, bound_ids = _collect_bound_peer_ma_links(
            hass, coord.esphome_device_id, set(), exclude_coord=None
        )
        assert claimed == set()
        assert bound_ids == set()

        # 3. resolve_ma_counterpart_entity arms reconnect grace when pending_sendspin is True
        esp_entry = hass.config_entries.async_get_entry("esp_entry_pocket_assistant")
        assert esp_entry is not None
        esp_entry.runtime_data = SimpleNamespace(
            device_capabilities={"sendspin": {"client_id": "", "feature_flags": 1}}
        )
        domain_data.ma_counterpart_cache.clear()
        assert resolve_ma_counterpart_entity(hass, "media_player.pocket_assistant_music") is None
        assert "media_player.pocket_assistant_music" in domain_data.ma_reconnect_until
        esp_entry.runtime_data = None
        clear_ma_counterpart_cache(hass)

        # 4. Malformed cache entry (wrong tuple length) is evicted and cleanly re-resolved
        domain_data.ma_counterpart_cache["media_player.pocket_assistant_music"] = (
            "bad_len",  # type: ignore[assignment]
            True,
        )
        assert resolve_ma_counterpart_entity(hass, "media_player.pocket_assistant_music") is None
        repaired = domain_data.ma_counterpart_cache["media_player.pocket_assistant_music"]
        assert isinstance(repaired, tuple) and len(repaired) == 3

        # 5. async_heal_coordinator_ma_links re-entrancy guard returns early when flag is set
        domain_data.healing_ma_links = True
        async_heal_coordinator_ma_links(hass)
        assert domain_data.healing_ma_links is True
        domain_data.healing_ma_links = False

        # 6. Seed MA player, verify exact suggestion and heal rebind + notify when tracked_ma_counterpart changes
        _seed_ma_player(
            hass,
            entry_id="entry_ma_heal",
            ma_entity="media_player.ma_pocket",
            queue_id="ma_queue_pocket",
            mac="aa:bb:cc:dd:ee:01",
            state=STATE_PLAYING,
        )
        assert suggest_ma_player_for(hass, coord) == "media_player.ma_pocket"

        coord.tracked_ma_counterpart = None
        with patch.object(
            coord, "async_notify_listeners", wraps=coord.async_notify_listeners
        ) as mock_notify:
            async_heal_coordinator_ma_links(hass)
            assert coord.tracked_ma_counterpart == "media_player.ma_pocket"
            assert mock_notify.call_count >= 1
        await flush_debouncers(hass)
    finally:
        clear_ma_counterpart_cache(hass)
        assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_playback_volume_step_prefers_native_over_set(hass: Any) -> None:
    """Verify up/down prefer native volume_up/volume_down and fall back to volume_set only when step is unsupported."""
    mp_up_calls = mock_service(hass, "media_player", "volume_up")
    mp_down_calls = mock_service(hass, "media_player", "volume_down")
    mp_set_calls = mock_service(hass, "media_player", "volume_set")

    # AVR / MA speaker supporting both VOLUME_SET and VOLUME_STEP: up/down must use native step
    hass.states.async_set(
        "media_player.marantz_avr",
        STATE_PLAYING,
        {
            "volume_level": 0.40,
            "supported_features": VOLUME_SET_FLAG | VOLUME_STEP_FLAG,
        },
    )
    assert await async_execute_volume_action(hass, "media_player.marantz_avr", "up") is True
    assert (
        await async_execute_volume_action(
            hass, "media_player.marantz_avr", "up", volume_pct=45
        )
        is True
    )
    assert await async_execute_volume_action(hass, "media_player.marantz_avr", "down") is True
    assert (
        await async_execute_volume_action(
            hass, "media_player.marantz_avr", "set", volume_pct=52
        )
        is True
    )
    await hass.async_block_till_done()
    assert len(mp_up_calls) == 2
    assert len(mp_down_calls) == 1
    assert [c.data for c in mp_set_calls] == [
        {"entity_id": "media_player.marantz_avr", "volume_level": 0.52}
    ]

    mp_up_calls.clear()
    mp_down_calls.clear()
    mp_set_calls.clear()

    # VOLUME_SET-only speaker omitting VOLUME_STEP: up/down fall back to +/-5% or explicit volume_pct
    hass.states.async_set(
        "media_player.set_only_spk",
        STATE_PLAYING,
        {
            "volume_level": 0.40,
            "supported_features": VOLUME_SET_FLAG,
        },
    )
    assert await async_execute_volume_action(hass, "media_player.set_only_spk", "up") is True
    assert await async_execute_volume_action(hass, "media_player.set_only_spk", "down") is True
    assert (
        await async_execute_volume_action(
            hass, "media_player.set_only_spk", "up", volume_pct=65
        )
        is True
    )
    await hass.async_block_till_done()
    assert mp_up_calls == []
    assert mp_down_calls == []
    assert [c.data for c in mp_set_calls] == [
        {"entity_id": "media_player.set_only_spk", "volume_level": 0.45},
        {"entity_id": "media_player.set_only_spk", "volume_level": 0.35},
        {"entity_id": "media_player.set_only_spk", "volume_level": 0.65},
    ]


async def test_playback_podcast_start_item_respects_sort_pref(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify podcast container playback passes `start_item='latest'` unless Oldest on Top."""
    entry, _sys, coord = await setup_latter_hub(hass)
    assert coord is not None
    ma_calls: list[dict[str, Any]] = []
    try:
        _seed_ma_player(
            hass,
            entry_id="entry_ma_pod_start",
            ma_entity="media_player.ma_pocket",
            queue_id="ma_queue_pocket",
            mac="aa:bb:cc:dd:ee:01",
            state=STATE_IDLE,
        )
        clear_ma_counterpart_cache(hass)
        mock_service(
            hass,
            "music_assistant",
            "play_media",
            lambda call: ma_calls.append(dict(call.data)),
        )

        # Default Newest on Top: explicit podcast and URI-inferred podcast start at latest
        await execute_coordinator_media_command(
            coord,
            "play_media",
            media_id="library://podcast/10",
            media_type="podcast",
            enqueue="play",
        )
        await execute_coordinator_media_command(
            coord,
            "play_media",
            media_id="library://podcast/10",
            media_type=None,
            enqueue="replace",
        )
        # Radio mode or individual episode omits start_item
        await execute_coordinator_media_command(
            coord,
            "play_media",
            media_id="library://podcast/10",
            media_type="podcast",
            radio_mode=True,
        )
        await execute_coordinator_media_command(
            coord,
            "play_media",
            media_id="library://podcast_episode/42",
            media_type="podcast_episode",
            enqueue="play",
        )

        # Oldest on Top: omits start_item so Music Assistant plays chronologically
        hass.config_entries.async_update_subentry(
            entry,
            coord.subentry,
            data={**coord.subentry.data, "podcast_sort_order": "Oldest on Top"},
        )
        await execute_coordinator_media_command(
            coord,
            "play_media",
            media_id="library://podcast/10",
            media_type="podcast",
            enqueue="play",
        )
        await hass.async_block_till_done()

        assert ma_calls == [
            {
                "entity_id": "media_player.ma_pocket",
                "media_id": "library://podcast/10",
                "media_type": "podcast",
                "enqueue": "play",
                "start_item": "latest",
            },
            {
                "entity_id": "media_player.ma_pocket",
                "media_id": "library://podcast/10",
                "media_type": "podcast",
                "enqueue": "replace",
                "start_item": "latest",
            },
            {
                "entity_id": "media_player.ma_pocket",
                "media_id": "library://podcast/10",
                "media_type": "podcast",
                "radio_mode": True,
            },
            {
                "entity_id": "media_player.ma_pocket",
                "media_id": "library://podcast_episode/42",
                "media_type": "podcast_episode",
                "enqueue": "play",
            },
            {
                "entity_id": "media_player.ma_pocket",
                "media_id": "library://podcast/10",
                "media_type": "podcast",
                "enqueue": "play",
            },
        ]
    finally:
        clear_ma_counterpart_cache(hass)
        await flush_debouncers(hass)
        assert await hass.config_entries.async_unload(entry.entry_id) is True
