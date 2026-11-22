"""Tests for Music Assistant enqueue modes, radio mode, queue manipulation, and 720x720 artwork proxy."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

from PIL import Image

from custom_components.latter.const import RPC_MEDIA_COMMAND
from custom_components.latter.http.proxy_views import LatterArtworkTranscoderView
from custom_components.latter.media.state_payload import build_active_media_payload


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
        await _sys_obj.rpc_dispatcher.async_dispatch(
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
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {
            "command": "queue_play",
            "queue_item_id": "qi_4",
        },
    )
    assert mass.player_queues.play_index_calls == [("ma_queue_pocket", "qi_4")]

    # queue_move supports Move Up (-1), Move Down (+1), and Play Next ("next" -> current_index + 1 - item_index)
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {
            "command": "queue_move",
            "queue_item_id": "qi_3",
            "pos_shift": -1,
        },
    )
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {
            "command": "queue_move",
            "queue_item_id": "qi_2",
            "pos_shift": "+1",
        },
    )
    # Item qi_4 is at index 4; current_index is 1 -> Play Next target index is 2 -> shift = (1 + 1) - 4 = -2
    await _sys_obj.rpc_dispatcher.async_dispatch(
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
    await _sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        RPC_MEDIA_COMMAND,
        {
            "command": "queue_delete",
            "queue_item_id": "qi_3",
        },
    )
    assert mass.player_queues.delete_item_calls == [("ma_queue_pocket", "qi_3")]


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
