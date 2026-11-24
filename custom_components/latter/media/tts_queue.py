"""Sendspin/Music Assistant queue handoff, cold resume, container playback fallback, and Assist Satellite / TTS announcements."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
import logging
from typing import Any, Final

from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from ..const import DOMAIN
from ..hub_registry import get_area_state_index, iter_coordinators, peek_domain_data
from .browse import async_browse_media_items, async_lookup_ma_track_uri, extract_item_dict
from .linking import (
    get_ma_mass_client,
    is_music_assistant_player,
    resolve_ma_counterpart_entity,
    resolve_ma_queue_id_sync,
    safe_float,
)

_LOGGER = logging.getLogger(__name__)

VALID_MA_ENQUEUE_MODES: Final[frozenset[str]] = frozenset(
    {"play", "next", "add", "replace", "replace_next"}
)

_KNOWN_URI_MEDIA_TYPES: Final[frozenset[str]] = frozenset(
    {
        "artist",
        "album",
        "playlist",
        "track",
        "radio",
        "podcast",
        "audiobook",
        "podcast_episode",
    }
)
_MIN_SEEK_RESUME_POS_S: Final[float] = 5.0
_SEEK_DRIFT_TOLERANCE_S: Final[float] = 4.0
_HANDOFF_TIMEOUT_S: Final[float] = 4.5
_SETTLE_WAIT_S: Final[float] = 1.2
_NATIVE_PLAY_WAIT_S: Final[float] = 2.5
_COUNTERPART_PLAY_WAIT_S: Final[float] = 1.5


def is_ephemeral_announcement_uri(uri: str) -> bool:
    """Return True for one-shot TTS, chime, or signed Latter URLs that must not overwrite media history."""
    low = str(uri or "").strip().lower()
    if not low:
        return False
    return (
        "/api/tts_proxy/" in low
        or low.startswith("media-source://tts")
        or "/api/latter/" in low
        or "/local/sounds/" in low
    )


def parse_media_uri_type(media_id: str) -> str:
    """Extract canonical `media_type` from a `provider://type/id` URI without substring guessing."""
    raw = str(media_id or "").strip()
    if "://" not in raw:
        return ""
    scheme, rest = raw.split("://", 1)
    if scheme.lower() in ("http", "https", "rtsp", "rtsps", "media-source"):
        return ""
    type_segment = rest.split("/", 1)[0].strip().lower()
    if type_segment.endswith("s") and type_segment[:-1] in _KNOWN_URI_MEDIA_TYPES:
        type_segment = type_segment[:-1]
    if type_segment == "podcast_episode":
        return "track"
    return type_segment if type_segment in _KNOWN_URI_MEDIA_TYPES else ""


def _extract_queue_entry_uri(entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    media_item = entry.get("media_item")
    if isinstance(media_item, dict) and media_item.get("uri"):
        cand = str(media_item["uri"]).strip()
        if not is_ephemeral_announcement_uri(cand):
            return cand
    cand = str(entry.get("uri") or entry.get("media_content_id") or "").strip()
    return "" if is_ephemeral_announcement_uri(cand) else cand


def _extract_queue_entry_album_ref(entry: Any) -> str:
    if not isinstance(entry, dict):
        return ""
    media_item = entry.get("media_item")
    if isinstance(media_item, dict):
        album = media_item.get("album")
        if isinstance(album, dict):
            return str(album.get("uri") or album.get("name") or "").strip()
        if isinstance(album, str) and album.strip():
            return album.strip()
    return str(entry.get("media_album_name") or "").strip()


async def _async_query_ma_queue_for_resume(
    hass: HomeAssistant, ma_entity: str | None, last_media_position: float
) -> tuple[list[str], str, str, str, float]:
    ma_st = hass.states.get(ma_entity) if ma_entity else None
    ma_usable = bool(
        ma_entity
        and (ma_st is None or ma_st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN))
    )
    pos = last_media_position
    if not ma_entity or not ma_usable or not hass.services.has_service("music_assistant", "get_queue"):
        return [], "", "", "", pos

    try:
        resp = await hass.services.async_call(
            "music_assistant",
            "get_queue",
            {ATTR_ENTITY_ID: ma_entity},
            blocking=True,
            return_response=True,
        )
        q_data = (resp.get(ma_entity) or resp) if isinstance(resp, dict) else None
        if not isinstance(q_data, dict):
            return [], "", "", "", pos
        cur_item = q_data.get("current_item") or q_data.get("next_item") or {}
        cur_uri = _extract_queue_entry_uri(cur_item)
        next_uri = (
            _extract_queue_entry_uri(q_data.get("next_item"))
            if q_data.get("current_item") and isinstance(q_data.get("next_item"), dict)
            else ""
        )
        album_ref = _extract_queue_entry_album_ref(cur_item)
        pos = safe_float(q_data.get("elapsed_time"), safe_float(last_media_position, 0.0))
        items_cand = q_data.get("items") or q_data.get("queue_items")
        if isinstance(items_cand, list):
            list_uris = [u for u in (_extract_queue_entry_uri(x) for x in items_cand) if u]
            if len(list_uris) > 1:
                cur_idx = q_data.get("current_index")
                if isinstance(cur_idx, int) and 0 <= cur_idx < len(list_uris):
                    start_idx = cur_idx
                elif cur_uri and cur_uri in list_uris:
                    start_idx = list_uris.index(cur_uri)
                else:
                    start_idx = 0
                return list_uris[start_idx:], cur_uri, next_uri, album_ref, pos
        return [], cur_uri, next_uri, album_ref, pos
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("music_assistant.get_queue resume lookup failed: %s", err)
        return [], "", "", "", pos


async def _async_expand_album_tail_uris(
    hass: HomeAssistant,
    speaker_entity_id: str,
    cur_uri: str,
    eff_album_ref: str,
    fallbacks: tuple[str, str, str],
) -> list[str]:
    last_title, last_artist, last_album = fallbacks
    try:
        raw_tracks = await async_browse_media_items(
            hass,
            "album_tracks",
            speaker_entity_id,
            speaker_entity_id,
            speaker_entity_id,
            search=eff_album_ref,
            fallback_title=last_title,
            fallback_artist=last_artist,
            fallback_album=last_album,
        )
        track_slots = [
            s
            for s in (raw_tracks or [])
            if isinstance(s, dict) and s.get("type") == "track" and s.get("id")
        ]
        if len(track_slots) <= 1:
            return []
        track_uris = [str(s["id"]) for s in track_slots]
        if cur_uri in track_uris:
            return track_uris[track_uris.index(cur_uri) :]
        active_indices = [i for i, s in enumerate(track_slots) if s.get("active")]
        if active_indices:
            return track_uris[active_indices[0] :]
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Album tail expansion on resume for '%s' failed: %s", eff_album_ref, err)
    return []


async def async_find_queue_resume_items(
    hass: HomeAssistant,
    speaker_entity_id: str,
    last_media_uri: str,
    last_media_position: float,
    *,
    last_media_title: str = "",
    last_media_artist: str = "",
    last_media_album: str = "",
) -> tuple[list[str], float]:
    """Query Music Assistant queue or album context to preserve upcoming tracks on cold resume."""
    ma_entity = resolve_ma_counterpart_entity(hass, speaker_entity_id)
    direct_uris, cur_uri, next_uri, album_ref, pos = await _async_query_ma_queue_for_resume(
        hass, ma_entity, last_media_position
    )
    if direct_uris:
        return direct_uris, pos

    if not cur_uri and last_media_uri and not is_ephemeral_announcement_uri(last_media_uri):
        cur_uri = last_media_uri
        pos = last_media_position

    if not cur_uri and last_media_title:
        looked_up_uri = await async_lookup_ma_track_uri(hass, last_media_title, last_media_artist)
        if looked_up_uri:
            cur_uri = looked_up_uri
            pos = last_media_position

    if not cur_uri:
        return [], last_media_position

    eff_album_ref = album_ref or last_media_album.strip()
    if eff_album_ref and parse_media_uri_type(cur_uri) in ("", "track"):
        expanded = await _async_expand_album_tail_uris(
            hass,
            speaker_entity_id,
            cur_uri,
            eff_album_ref,
            (last_media_title, last_media_artist, last_media_album),
        )
        if expanded:
            return expanded, pos

    if next_uri and next_uri != cur_uri:
        return [cur_uri, next_uri], pos
    return [cur_uri], pos


async def _async_expand_and_play_container(
    hass: HomeAssistant,
    target_spk: str,
    ma_target: str,
    container: tuple[str, str, str],
    *,
    radio_mode: bool,
) -> bool:
    media_id, eff_type, norm_enqueue = container
    try:
        alb_uri = media_id
        if eff_type == "artist":
            album_slots = await async_browse_media_items(
                hass, "artist_albums", target_spk, target_spk, target_spk, search=media_id
            )
            if not album_slots or not album_slots[0].get("id"):
                return False
            alb_uri = str(album_slots[0]["id"])
        raw_tracks = await async_browse_media_items(
            hass, "album_tracks", target_spk, target_spk, target_spk, search=alb_uri
        )
        track_uris = [str(s["id"]) for s in (raw_tracks or []) if s.get("id")]
        if not track_uris:
            return False
        fb_payload: dict[str, Any] = {
            ATTR_ENTITY_ID: ma_target,
            "media_id": track_uris[0] if radio_mode else track_uris,
            "media_type": "track",
            "enqueue": norm_enqueue or "replace",
        }
        if radio_mode:
            fb_payload["radio_mode"] = True
        await hass.services.async_call("music_assistant", "play_media", fb_payload, blocking=True)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug(
            "Fallback container track expansion for %s (%s) failed: %s", media_id, eff_type, err
        )
        return False


async def _async_try_ma_play_media(
    hass: HomeAssistant,
    target_spk: str,
    ma_target: str | None,
    req: tuple[str | list[str], str, str],
    *,
    radio_mode: bool,
) -> bool:
    media_id, eff_type, norm_enqueue = req
    if not ma_target or not hass.services.has_service("music_assistant", "play_media"):
        return False
    ma_st = hass.states.get(ma_target)
    if ma_st is not None and ma_st.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return False
    payload: dict[str, Any] = {
        ATTR_ENTITY_ID: ma_target,
        "media_id": media_id,
        **({"media_type": eff_type} if eff_type else {}),
        **({"enqueue": norm_enqueue} if norm_enqueue else {}),
        **({"radio_mode": True} if radio_mode else {}),
    }
    try:
        await hass.services.async_call("music_assistant", "play_media", payload, blocking=True)
        return True
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug(
            "music_assistant.play_media(%s, %s) on %s failed: %s",
            media_id,
            eff_type,
            ma_target,
            err,
        )
        return bool(
            isinstance(media_id, str)
            and eff_type in ("artist", "album")
            and await _async_expand_and_play_container(
                hass,
                target_spk,
                ma_target,
                (media_id, eff_type, norm_enqueue),
                radio_mode=radio_mode,
            )
        )


async def async_play_media_with_ma_fallback(
    hass: HomeAssistant,
    target_spk: str,
    media_id: str | list[str],
    media_type: str | None = None,
    enqueue: str | None = None,
    radio_mode: bool = False,
) -> None:
    """Play media via Music Assistant, expanding full artist/album containers without track caps."""
    if isinstance(media_id, list):
        cleaned_ids = [str(x).strip() for x in media_id if str(x or "").strip()]
        if not cleaned_ids:
            return
        media_id = cleaned_ids[0] if len(cleaned_ids) == 1 else cleaned_ids

    first_uri = media_id[0] if isinstance(media_id, list) else media_id
    ma_target = resolve_ma_counterpart_entity(hass, target_spk)
    spk_entry = er.async_get(hass).async_get(target_spk) if target_spk else None
    is_esphome_sendspin = bool(spk_entry and spk_entry.platform == "esphome")

    eff_type = (media_type or "").strip().lower()
    if isinstance(media_id, list):
        eff_type = "track"
    elif not eff_type or eff_type == "music":
        eff_type = parse_media_uri_type(first_uri) or eff_type

    raw_enq = (enqueue or "").strip().lower()
    norm_enqueue = raw_enq if raw_enq in VALID_MA_ENQUEUE_MODES else ""

    if await _async_try_ma_play_media(
        hass, target_spk, ma_target, (media_id, eff_type, norm_enqueue), radio_mode=radio_mode
    ):
        return
    if is_esphome_sendspin:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="ma_counterpart_required",
            translation_placeholders={"speaker": target_spk},
        )

    ha_play_payload: dict[str, Any] = {
        ATTR_ENTITY_ID: target_spk,
        "media_content_id": first_uri,
        "media_content_type": eff_type or "music",
        **({"enqueue": norm_enqueue} if norm_enqueue in ("play", "next", "add", "replace") else {}),
    }
    await hass.services.async_call("media_player", "play_media", ha_play_payload, blocking=False)


async def _async_wait_entities_playing(
    hass: HomeAssistant, watched_entities: list[str], timeout_s: float
) -> bool:
    """Wait reactively via `async_track_state_change_event` (zero sleep polling)."""

    def _is_playing() -> bool:
        return any(
            (st := hass.states.get(ent_id)) is not None
            and st.state in (STATE_PLAYING, STATE_BUFFERING)
            for ent_id in watched_entities
        )

    if _is_playing():
        return True
    if not watched_entities:
        return False
    woke = asyncio.Event()

    @callback
    def _on_watched_change(_event: Event[EventStateChangedData]) -> None:
        if _is_playing():
            woke.set()

    unsub = async_track_state_change_event(hass, watched_entities, _on_watched_change)
    try:
        if _is_playing():
            return True
        try:
            await asyncio.wait_for(woke.wait(), timeout=timeout_s)
            return True
        except TimeoutError:
            return _is_playing()
    finally:
        unsub()


async def _async_verify_transfer_position_and_state(
    hass: HomeAssistant,
    cmd_target: str,
    target_speaker: str,
    handoff_position: float,
    *,
    was_playing: bool,
) -> None:
    watched = [e for e in dict.fromkeys((cmd_target, target_speaker)) if e]
    try:
        async with asyncio.timeout(_HANDOFF_TIMEOUT_S):
            await _async_wait_entities_playing(hass, watched, _SETTLE_WAIT_S)
            updated_tgt = hass.states.get(cmd_target) or hass.states.get(target_speaker)
            if updated_tgt is None:
                return
            if was_playing and updated_tgt.state in (STATE_PAUSED, STATE_IDLE):
                try:
                    await hass.services.async_call(
                        "media_player",
                        "media_play",
                        {ATTR_ENTITY_ID: cmd_target},
                        blocking=False,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Queue transfer media_play on %s skipped: %s", cmd_target, err)

            tgt_pos = safe_float(updated_tgt.attributes.get("media_position"), 0.0)
            if (
                handoff_position > _MIN_SEEK_RESUME_POS_S
                and abs(tgt_pos - handoff_position) > _SEEK_DRIFT_TOLERANCE_S
            ):
                try:
                    await hass.services.async_call(
                        "media_player",
                        "media_seek",
                        {ATTR_ENTITY_ID: cmd_target, "seek_position": round(handoff_position, 1)},
                        blocking=False,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Position handoff media_seek failed: %s", err)
    except TimeoutError:
        _LOGGER.debug("Queue transfer handoff timed out for %s", target_speaker)


async def async_execute_ma_queue_transfer(
    hass: HomeAssistant,
    local_speaker: str,
    source_speaker: str,
    target_speaker: str,
    was_playing: bool,
    handoff_position: float,
    media_content_id: str,
    media_content_type: str,
) -> None:
    """Execute Music Assistant queue transfer, quiesce local Sendspin speaker, and verify position handoff."""
    src_ma = resolve_ma_counterpart_entity(hass, source_speaker)
    tgt_ma = resolve_ma_counterpart_entity(hass, target_speaker)
    local_ma = resolve_ma_counterpart_entity(hass, local_speaker) if local_speaker else None
    cmd_target = tgt_ma or target_speaker
    is_from_local = bool(
        local_speaker
        and (
            source_speaker == local_speaker
            or (local_ma and local_ma in (source_speaker, src_ma))
        )
    )

    transferred_via_ma = False
    if (
        src_ma
        and tgt_ma
        and src_ma != tgt_ma
        and hass.services.has_service("music_assistant", "transfer_queue")
    ):
        try:
            await hass.services.async_call(
                "music_assistant",
                "transfer_queue",
                {
                    ATTR_ENTITY_ID: tgt_ma,
                    "source_player": src_ma,
                    "auto_play": bool(was_playing),
                },
                blocking=True,
            )
            transferred_via_ma = True
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.transfer_queue failed: %s", err)

    if (
        is_from_local
        and target_speaker not in (source_speaker, local_speaker)
        and (not local_ma or tgt_ma != local_ma)
    ):
        try:
            await hass.services.async_call(
                "media_player", "media_pause", {ATTR_ENTITY_ID: local_speaker}, blocking=False
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed quiescing local speaker %s: %s", local_speaker, err)

    if not transferred_via_ma and media_content_id:
        try:
            if not is_from_local:
                await hass.services.async_call(
                    "media_player",
                    "media_pause",
                    {ATTR_ENTITY_ID: src_ma or source_speaker},
                    blocking=False,
                )
            await async_play_media_with_ma_fallback(
                hass,
                target_speaker,
                media_content_id,
                media_type=media_content_type or "music",
                enqueue="replace",
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Fallback play_media handoff failed: %s", err)

    await _async_verify_transfer_position_and_state(
        hass, cmd_target, target_speaker, handoff_position, was_playing=was_playing
    )


async def _async_try_counterpart_native_play(
    hass: HomeAssistant,
    speaker_entity_id: str,
    ma_entity: str | None,
    watched_entities: list[str],
    *,
    already_tried_ma: bool,
) -> bool:
    if await _async_wait_entities_playing(hass, watched_entities, _NATIVE_PLAY_WAIT_S):
        return True
    if not ma_entity or ma_entity == speaker_entity_id or already_tried_ma:
        return False
    try:
        await hass.services.async_call(
            "media_player", "media_play", {ATTR_ENTITY_ID: ma_entity}, blocking=True
        )
        return await _async_wait_entities_playing(hass, watched_entities, _COUNTERPART_PLAY_WAIT_S)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Idle speaker MA counterpart media_play on %s failed: %s", ma_entity, err)
        return False


async def async_resume_idle_speaker_queue(
    hass: HomeAssistant,
    speaker_entity_id: str,
    last_media_uri: str,
    last_media_position: float,
    last_media_type: str,
    *,
    last_media_title: str = "",
    last_media_artist: str = "",
    last_media_album: str = "",
    immediate: bool = False,
    already_tried_ma: bool = False,
) -> bool:
    """Resume playback on an idle speaker reactively without blocking sleep loops."""
    ma_entity = resolve_ma_counterpart_entity(hass, speaker_entity_id)
    watched_entities = [
        ent_id for ent_id in dict.fromkeys((speaker_entity_id, ma_entity)) if ent_id
    ]
    if not immediate and await _async_try_counterpart_native_play(
        hass,
        speaker_entity_id,
        ma_entity,
        watched_entities,
        already_tried_ma=already_tried_ma,
    ):
        return True

    cur_state = hass.states.get(speaker_entity_id)
    resume_uris, resume_pos = await async_find_queue_resume_items(
        hass,
        speaker_entity_id,
        last_media_uri,
        last_media_position,
        last_media_title=last_media_title,
        last_media_artist=last_media_artist,
        last_media_album=last_media_album,
    )
    if not resume_uris:
        _LOGGER.debug("No resumable queue URI found for idle speaker '%s'", speaker_entity_id)
        return False

    play_payload: str | list[str] = resume_uris[0] if len(resume_uris) == 1 else resume_uris
    eff_media_type = "track" if len(resume_uris) > 1 else (last_media_type or "music")
    play_target = ma_entity or speaker_entity_id
    try:
        if hass.services.has_service("music_assistant", "play_media") and (
            ma_entity or (is_music_assistant_player(hass, cur_state) if cur_state else False)
        ):
            await async_play_media_with_ma_fallback(
                hass,
                play_target,
                play_payload,
                media_type=eff_media_type,
                enqueue="replace" if len(resume_uris) > 1 else None,
            )
        else:
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    ATTR_ENTITY_ID: play_target,
                    "media_content_id": resume_uris[0],
                    "media_content_type": last_media_type or "music",
                },
                blocking=True,
            )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Post-reboot play_media failed on %s: %s", play_target, err)
        return False

    if resume_pos > _MIN_SEEK_RESUME_POS_S:
        await _async_wait_entities_playing(hass, watched_entities, _SETTLE_WAIT_S)
        try:
            await hass.services.async_call(
                "media_player",
                "media_seek",
                {ATTR_ENTITY_ID: play_target, "seek_position": round(resume_pos, 1)},
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Post-resume media_seek on %s skipped: %s", play_target, err)
    return True


_QUEUE_PAGE_LIMIT: Final[int] = 100
_QUEUE_MAX_SCAN: Final[int] = 500


async def _async_resolve_ma_queue_context(
    hass: HomeAssistant, ma_target: str
) -> tuple[Any | None, str, dict[str, Any]]:
    mass = get_ma_mass_client(hass)
    q_data: dict[str, Any] = {}
    queue_id = ""
    if ma_target and hass.services.has_service("music_assistant", "get_queue"):
        try:
            resp = await hass.services.async_call(
                "music_assistant",
                "get_queue",
                {ATTR_ENTITY_ID: ma_target},
                blocking=True,
                return_response=True,
            )
            cand = (resp.get(ma_target) or resp) if isinstance(resp, dict) else None
            if isinstance(cand, dict):
                q_data = cand
                queue_id = str(q_data.get("queue_id") or "").strip()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.get_queue context lookup failed: %s", err)
    queue_id = queue_id or resolve_ma_queue_id_sync(hass, ma_target, mass) or ma_target
    return mass, queue_id, q_data


async def _async_resolve_queue_next_shift(
    pqs: Any, queue_id: str, q_data: dict[str, Any], clean_qid: str
) -> int:
    cur_raw = q_data.get("current_item")
    cur_qid = (
        str(extract_item_dict(cur_raw).get("queue_item_id") or "").strip()
        if cur_raw is not None
        else ""
    )
    items_list: list[dict[str, Any]] = []
    if hasattr(pqs, "fetch_player_queue_items"):
        for page_offset in range(0, _QUEUE_MAX_SCAN, _QUEUE_PAGE_LIMIT):
            fetched = await pqs.fetch_player_queue_items(
                queue_id, limit=_QUEUE_PAGE_LIMIT, offset=page_offset
            )
            if not (isinstance(fetched, Sequence) and not isinstance(fetched, (str, bytes))):
                break
            batch = [extract_item_dict(x) for x in fetched]
            items_list.extend(batch)
            found_target = any(
                str(it.get("queue_item_id") or "").strip() == clean_qid for it in items_list
            )
            found_cur = (
                not cur_qid
                or isinstance(q_data.get("current_index"), int)
                or any(str(it.get("queue_item_id") or "").strip() == cur_qid for it in items_list)
            )
            if (found_target and found_cur) or len(batch) < _QUEUE_PAGE_LIMIT:
                break
    if not items_list:
        for list_key in ("queue_items", "items"):
            if isinstance(cand_l := q_data.get(list_key), list):
                items_list = [extract_item_dict(x) for x in cand_l]
                break
    item_index = next(
        (idx for idx, it in enumerate(items_list) if str(it.get("queue_item_id") or "").strip() == clean_qid),
        -1,
    )
    if item_index < 0:
        return 0

    current_index: int | None = None
    raw_cur_idx = q_data.get("current_index")
    if isinstance(raw_cur_idx, int) and not isinstance(raw_cur_idx, bool):
        current_index = raw_cur_idx
    elif hasattr(pqs, "get") and (q_obj := pqs.get(queue_id)) is not None:
        cand_idx = getattr(q_obj, "current_index", None)
        if isinstance(cand_idx, int) and not isinstance(cand_idx, bool):
            current_index = cand_idx
    if current_index is None:
        current_index = next(
            (idx for idx, it in enumerate(items_list) if cur_qid and str(it.get("queue_item_id") or "").strip() == cur_qid),
            0,
        )
    return (current_index - item_index) if item_index < current_index else ((current_index + 1) - item_index)


async def async_handle_queue_mutation_command(
    hass: HomeAssistant,
    cmd: str,
    ma_target: str | None,
    queue_item_id: str | None,
    pos_shift: int | str | None,
) -> tuple[bool, bool]:
    """Handle `queue_play`, `queue_move`, and `queue_delete`; return `(handled, should_notify)`."""
    if cmd not in ("queue_play", "queue_move", "queue_delete"):
        return False, False
    clean_qid = str(queue_item_id or "").strip()
    if not clean_qid or not ma_target:
        return True, False
    mass, queue_id, q_data = await _async_resolve_ma_queue_context(hass, ma_target)
    pqs = getattr(mass, "player_queues", None) if mass is not None else None
    if pqs is None or not queue_id:
        return True, False

    notified = False
    if cmd == "queue_play":
        await pqs.play_index(queue_id, clean_qid)
        notified = True
    elif cmd == "queue_delete":
        await pqs.delete_item(queue_id, item_id_or_index=clean_qid)
        if (domain_data := peek_domain_data(hass)) is not None:
            q_counts = domain_data.ma_queue_counts
            if q_counts.get(ma_target, 0) > 0:
                q_counts[ma_target] = q_counts[ma_target] - 1
        notified = True
    elif pos_shift is not None:
        raw_shift_str = str(pos_shift).strip().lower()
        shift_int = (
            await _async_resolve_queue_next_shift(pqs, queue_id, q_data, clean_qid)
            if raw_shift_str == "next"
            else 0
        )
        if raw_shift_str != "next":
            try:
                shift_int = int(raw_shift_str)
            except ValueError:
                shift_int = 0
        if shift_int != 0:
            await pqs.move_item(queue_id, clean_qid, pos_shift=shift_int)
            notified = True
    return True, notified


def _collect_candidate_device_ids(
    hass: HomeAssistant,
    ent_reg: er.EntityRegistry,
    target: str,
    coordinator: Any,
) -> list[str]:
    cand_dev_ids: list[str] = []
    if coordinator is not None and (esp_dev_id := getattr(coordinator, "esphome_device_id", None)):
        cand_dev_ids.append(str(esp_dev_id))

    if target.startswith("media_player."):
        reg_ent = ent_reg.async_get(target)
        if reg_ent and reg_ent.device_id and reg_ent.device_id not in cand_dev_ids:
            cand_dev_ids.append(reg_ent.device_id)
        for val in iter_coordinators(hass):
            local_spk = getattr(val, "local_speaker", None)
            matches_coord = (
                local_spk == target
                or getattr(val, "active_speaker", None) == target
                or bool(local_spk and resolve_ma_counterpart_entity(hass, str(local_spk)) == target)
            )
            if (
                matches_coord
                and (c_dev_id := getattr(val, "esphome_device_id", None))
                and str(c_dev_id) not in cand_dev_ids
            ):
                cand_dev_ids.append(str(c_dev_id))
    elif target and "." not in target and target not in cand_dev_ids:
        cand_dev_ids.append(target)
    return cand_dev_ids


def resolve_assist_satellite_entity(
    hass: HomeAssistant,
    speaker_or_device_id: str | None = None,
    coordinator: Any = None,
) -> str | None:
    """Resolve an `assist_satellite.*` entity for a speaker entity, HA `device_id`, or coordinator."""
    target = str(speaker_or_device_id or "").strip()
    if target.startswith("assist_satellite."):
        st = hass.states.get(target)
        if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return target

    ent_reg = er.async_get(hass)
    for dev_id in _collect_candidate_device_ids(hass, ent_reg, target, coordinator):
        for entry in er.async_entries_for_device(ent_reg, dev_id):
            if entry.domain == "assist_satellite" and not entry.disabled_by:
                st = hass.states.get(entry.entity_id)
                if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                    return str(entry.entity_id)
    return None


def _partition_announce_targets(
    hass: HomeAssistant, speakers: list[str], *, has_sat_announce: bool
) -> tuple[list[str], list[str]]:
    ent_reg = er.async_get(hass)
    satellites: list[str] = []
    fallback_speakers: list[str] = []
    seen_device_ids: set[str] = set()

    for spk in speakers:
        if not spk:
            continue
        sat_ent = resolve_assist_satellite_entity(hass, spk) if has_sat_announce else None
        if sat_ent:
            sat_reg = ent_reg.async_get(sat_ent)
            sat_dev_id = sat_reg.device_id if sat_reg and sat_reg.device_id else sat_ent
            if sat_dev_id in seen_device_ids:
                continue
            seen_device_ids.add(sat_dev_id)
            if (spk_reg := ent_reg.async_get(spk)) and spk_reg.device_id:
                seen_device_ids.add(spk_reg.device_id)
            if sat_ent not in satellites:
                satellites.append(sat_ent)
            continue

        spk_reg = ent_reg.async_get(spk)
        spk_dev_id = spk_reg.device_id if spk_reg and spk_reg.device_id else spk
        if spk_dev_id in seen_device_ids:
            continue
        seen_device_ids.add(spk_dev_id)
        if spk not in fallback_speakers:
            fallback_speakers.append(spk)
    return satellites, fallback_speakers


async def _async_announce_media_url_on_fallbacks(
    hass: HomeAssistant, fallback_speakers: list[str], media_url: str, *, blocking: bool
) -> None:
    ma_speakers = [
        s
        for s in fallback_speakers
        if (st := hass.states.get(s)) is not None and is_music_assistant_player(hass, st)
    ]
    other_speakers = [s for s in fallback_speakers if s not in ma_speakers]

    if ma_speakers and hass.services.has_service("music_assistant", "play_announcement"):
        await hass.services.async_call(
            "music_assistant",
            "play_announcement",
            {ATTR_ENTITY_ID: ma_speakers, "url": media_url},
            blocking=blocking,
        )
    else:
        other_speakers = fallback_speakers

    if other_speakers:
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: other_speakers,
                "media_content_id": media_url,
                "media_content_type": "music",
                "announce": True,
            },
            blocking=blocking,
        )


async def _async_speak_tts_on_fallbacks(
    hass: HomeAssistant,
    fallback_speakers: list[str],
    message: str,
    tts_entity: str,
    *,
    blocking: bool,
) -> None:
    eff_tts = tts_entity
    if not eff_tts:
        tts_states = get_area_state_index(hass).states_for_domain("tts")
        if tts_states:
            eff_tts = tts_states[0].entity_id
    if eff_tts and hass.services.has_service("tts", "speak"):
        await hass.services.async_call(
            "tts",
            "speak",
            {
                ATTR_ENTITY_ID: eff_tts,
                "media_player_entity_id": fallback_speakers,
                "message": message,
                "cache": False,
            },
            blocking=blocking,
        )


async def async_announce_on_targets(
    hass: HomeAssistant,
    speakers: list[str],
    message: str = "",
    media_url: str = "",
    tts_entity: str = "",
    blocking: bool = False,
) -> None:
    """Route announcements through `assist_satellite.announce` first, deduplicating by `device_id`."""
    if not speakers or (not message and not media_url):
        return

    has_sat_announce = hass.services.has_service("assist_satellite", "announce")
    satellites, fallback_speakers = _partition_announce_targets(
        hass, speakers, has_sat_announce=has_sat_announce
    )

    if satellites and has_sat_announce:
        sat_payload: dict[str, Any] = {
            ATTR_ENTITY_ID: satellites,
            **({"media_id": media_url} if media_url else {"message": message}),
        }
        try:
            await hass.services.async_call(
                "assist_satellite", "announce", sat_payload, blocking=blocking
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug(
                "assist_satellite.announce failed on %s, falling back: %s", satellites, err
            )
            fallback_speakers.extend(
                spk
                for spk in speakers
                if spk and not spk.startswith("assist_satellite.") and spk not in fallback_speakers
            )

    if not fallback_speakers:
        return
    if media_url:
        await _async_announce_media_url_on_fallbacks(
            hass, fallback_speakers, media_url, blocking=blocking
        )
    elif message:
        await _async_speak_tts_on_fallbacks(
            hass, fallback_speakers, message, tts_entity, blocking=blocking
        )
