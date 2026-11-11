"""Media playback, volume override, Sendspin queue recovery, and active_media Protocol v3 builder."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from ..areas.state_index import get_area_state_index, is_media_position_only_tick
from ..const import DOMAIN, TRANSFER_HOLD_WINDOW_SECONDS
from ..core.hub import get_latter_system
from ..core.payloads import ha_value
from .browse import async_browse_media_items, is_music_assistant_player
from .ma_link import (
    async_refresh_ma_link,
    async_set_ma_player_link,
    clear_ma_counterpart_cache,
    ma_player_entities,
    resolve_esphome_local_speaker,
    resolve_ma_counterpart_entity,
    suggest_ma_player_for,
)

if TYPE_CHECKING:
    from ..core.device_coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)

VOLUME_FEATURE_FLAGS: int = 4 | 8 | 1024  # VOLUME_SET | VOLUME_MUTE | VOLUME_STEP

_KNOWN_URI_MEDIA_TYPES: frozenset[str] = frozenset(
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

__all__ = [
    "VOLUME_FEATURE_FLAGS",
    "async_announce_on_targets",
    "async_execute_ma_queue_transfer",
    "async_execute_volume_action",
    "async_find_queue_resume_item",
    "async_play_media_with_ma_fallback",
    "async_refresh_ma_link",
    "async_resume_idle_speaker_queue",
    "async_set_ma_player_link",
    "bind_coordinator_speaker_listener",
    "build_active_media_payload",
    "clear_ma_counterpart_cache",
    "enforce_local_speaker_if_remote_idle",
    "execute_coordinator_media_command",
    "interpolate_speaker_position",
    "ma_player_entities",
    "read_volume_from_target",
    "resolve_assist_satellite_entity",
    "resolve_esphome_local_speaker",
    "resolve_ma_counterpart_entity",
    "set_coordinator_active_speaker",
    "suggest_ma_player_for",
]


def _parse_media_uri_type(media_id: str) -> str:
    """Extract canonical media_type from a provider://type/id URI without substring guessing."""
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
    if type_segment in _KNOWN_URI_MEDIA_TYPES:
        return type_segment
    return ""


def interpolate_speaker_position(state_obj: Any) -> float:
    """Calculate the live interpolated playback position in seconds for a media_player state."""
    if state_obj is None:
        return 0.0
    attrs = state_obj.attributes
    duration = float(attrs.get("media_duration") or 0.0)
    base_pos = float(attrs.get("media_position") or 0.0)
    updated_at = attrs.get("media_position_updated_at")
    pos = base_pos
    if state_obj.state == STATE_PLAYING and isinstance(updated_at, datetime):
        elapsed = (dt_util.utcnow() - updated_at).total_seconds()
        if elapsed > 0:
            pos = base_pos + elapsed
            if duration > 0:
                pos = min(pos, duration)
    return max(0.0, pos)


def read_volume_from_target(
    hass: HomeAssistant, vol_target: str, fallback_attrs: dict[str, Any]
) -> float | None:
    """Read normalized 0.0..1.0 volume from media_player, number, or input_number, or None when unknown."""
    vol_state = hass.states.get(vol_target)
    if vol_state is not None and vol_state.state not in (
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ):
        if vol_state.domain in ("number", "input_number"):
            try:
                val = float(vol_state.state)
                min_v = float(vol_state.attributes.get("min", 0.0))
                max_v = float(vol_state.attributes.get("max", 100.0))
                if max_v > min_v:
                    return max(0.0, min(1.0, (val - min_v) / (max_v - min_v)))
            except ValueError:
                pass
        else:
            v_lvl = vol_state.attributes.get("volume_level")
            if v_lvl is not None:
                return float(v_lvl)

    if fallback_attrs.get("volume_level") is not None:
        return float(fallback_attrs["volume_level"])
    return None


async def async_execute_volume_action(
    hass: HomeAssistant,
    vol_target: str,
    action: str,
    volume_level: float | None = None,
) -> bool:
    """Execute a volume action ('set', 'up', 'down', 'mute') on a media_player, number, or input_number."""
    if not vol_target:
        return False
    state_obj = hass.states.get(vol_target)
    target_domain = state_obj.domain if state_obj else vol_target.split(".", 1)[0]
    norm_action = action.strip().lower()
    if norm_action == "volume_up":
        norm_action = "up"
    elif norm_action == "volume_down":
        norm_action = "down"
    elif norm_action == "volume_mute":
        norm_action = "mute"

    if target_domain in ("number", "input_number"):
        cur_val = (
            float(state_obj.state)
            if (state_obj and state_obj.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN))
            else 50.0
        )
        min_v = float(state_obj.attributes.get("min", 0.0)) if state_obj else 0.0
        max_v = float(state_obj.attributes.get("max", 100.0)) if state_obj else 100.0
        native_step = state_obj.attributes.get("step") if state_obj else None
        step = float(native_step) if native_step else max(1.0, (max_v - min_v) * 0.05)

        if norm_action == "up":
            new_val = min(max_v, cur_val + step)
        elif norm_action == "down":
            new_val = max(min_v, cur_val - step)
        elif volume_level is not None:
            lvl = volume_level / 100.0 if volume_level > 1.0 else volume_level
            new_val = min_v + max(0.0, min(1.0, lvl)) * (max_v - min_v)
        else:
            return False

        await hass.services.async_call(
            target_domain,
            "set_value",
            {ATTR_ENTITY_ID: vol_target, "value": round(new_val, 2)},
            blocking=False,
        )
        return True

    if target_domain != "media_player":
        return False

    supports_vol_set = bool(
        state_obj is not None and state_obj.attributes.get("volume_level") is not None
    )
    if norm_action in ("up", "down") and volume_level is not None and supports_vol_set:
        lvl = volume_level / 100.0 if volume_level > 1.0 else volume_level
        lvl = max(0.0, min(1.0, lvl))
        await hass.services.async_call(
            "media_player",
            "volume_set",
            {ATTR_ENTITY_ID: vol_target, "volume_level": round(lvl, 2)},
            blocking=False,
        )
        return True
    if norm_action == "up":
        await hass.services.async_call(
            "media_player", "volume_up", {ATTR_ENTITY_ID: vol_target}, blocking=False
        )
        return True
    if norm_action == "down":
        await hass.services.async_call(
            "media_player", "volume_down", {ATTR_ENTITY_ID: vol_target}, blocking=False
        )
        return True
    if norm_action == "mute":
        is_muted = (
            bool(state_obj.attributes.get("is_volume_muted", False))
            if state_obj
            else False
        )
        await hass.services.async_call(
            "media_player",
            "volume_mute",
            {ATTR_ENTITY_ID: vol_target, "is_volume_muted": not is_muted},
            blocking=False,
        )
        return True
    if volume_level is not None:
        lvl = volume_level / 100.0 if volume_level > 1.0 else volume_level
        lvl = max(0.0, min(1.0, lvl))
        await hass.services.async_call(
            "media_player",
            "volume_set",
            {ATTR_ENTITY_ID: vol_target, "volume_level": round(lvl, 2)},
            blocking=False,
        )
        return True
    return False


async def async_find_queue_resume_item(
    hass: HomeAssistant,
    speaker_entity_id: str,
    last_media_uri: str,
    last_media_position: float,
) -> tuple[str, float]:
    """Query Music Assistant get_queue for the current queue item URI and position, falling back to persisted store."""
    ma_entity = resolve_ma_counterpart_entity(hass, speaker_entity_id)
    if ma_entity and hass.services.has_service("music_assistant", "get_queue"):
        try:
            resp = await hass.services.async_call(
                "music_assistant",
                "get_queue",
                {ATTR_ENTITY_ID: ma_entity},
                blocking=True,
                return_response=True,
            )
            if isinstance(resp, dict):
                q_data = resp.get(ma_entity) or resp
                if isinstance(q_data, dict):
                    cur_item = (
                        q_data.get("current_item") or q_data.get("next_item") or {}
                    )
                    if isinstance(cur_item, dict):
                        media_item = cur_item.get("media_item") or {}
                        uri = str(
                            (
                                media_item.get("uri")
                                if isinstance(media_item, dict)
                                else ""
                            )
                            or cur_item.get("uri")
                            or cur_item.get("media_content_id")
                            or ""
                        )
                        pos = float(
                            q_data.get("elapsed_time") or last_media_position or 0.0
                        )
                        if uri:
                            return uri, pos
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("music_assistant.get_queue resume lookup failed: %s", err)

    return last_media_uri, last_media_position


async def async_play_media_with_ma_fallback(
    hass: HomeAssistant,
    target_spk: str,
    media_id: str,
    media_type: str | None = None,
    enqueue: str | None = None,
) -> None:
    """Play media via Music Assistant (expanding artist/album containers into tracks when needed)."""
    ma_target = resolve_ma_counterpart_entity(hass, target_spk)
    ent_reg = er.async_get(hass)
    spk_entry = ent_reg.async_get(target_spk) if target_spk else None
    is_esphome_sendspin = bool(spk_entry and spk_entry.platform == "esphome")

    eff_type = (media_type or "").strip().lower()
    if not eff_type or eff_type == "music":
        parsed_uri_type = _parse_media_uri_type(media_id)
        if parsed_uri_type:
            eff_type = parsed_uri_type

    if ma_target and hass.services.has_service("music_assistant", "play_media"):
        payload: dict[str, Any] = {
            ATTR_ENTITY_ID: ma_target,
            "media_id": media_id,
        }
        if eff_type:
            payload["media_type"] = eff_type
        if enqueue:
            payload["enqueue"] = enqueue
        try:
            await hass.services.async_call(
                "music_assistant", "play_media", payload, blocking=True
            )
            return
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug(
                "music_assistant.play_media(%s, %s) on %s failed: %s",
                media_id,
                eff_type,
                ma_target,
                err,
            )
            if eff_type in ("artist", "album"):
                try:
                    resolved_id = ""
                    resolved_type = "track"
                    if eff_type == "artist":
                        album_slots = await async_browse_media_items(
                            hass,
                            "artist_albums",
                            target_spk,
                            target_spk,
                            target_spk,
                            search=media_id,
                        )
                        if album_slots and album_slots[0].get("id"):
                            resolved_id = str(album_slots[0]["id"])
                            resolved_type = "album"
                    if eff_type == "album" or resolved_type == "album":
                        alb_uri = resolved_id or media_id
                        raw_tracks = await async_browse_media_items(
                            hass,
                            "album_tracks",
                            target_spk,
                            target_spk,
                            target_spk,
                            search=alb_uri,
                        )
                        track_slots = [
                            s for s in (raw_tracks or [])[:25] if s.get("id")
                        ]
                        if track_slots:
                            track_uris = [str(s["id"]) for s in track_slots]
                            await hass.services.async_call(
                                "music_assistant",
                                "play_media",
                                {
                                    ATTR_ENTITY_ID: ma_target,
                                    "media_id": track_uris,
                                    "media_type": "track",
                                    "enqueue": enqueue or "replace",
                                },
                                blocking=True,
                            )
                            return
                except Exception as inner_err:  # noqa: BLE001
                    _LOGGER.debug(
                        "Fallback container track expansion for %s (%s) failed: %s",
                        media_id,
                        eff_type,
                        inner_err,
                    )

    if (is_esphome_sendspin or not ma_target) and is_esphome_sendspin:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="ma_counterpart_required",
            translation_placeholders={"speaker": target_spk},
        )

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: target_spk,
            "media_content_id": media_id,
            "media_content_type": eff_type or "music",
        },
        blocking=False,
    )


def resolve_assist_satellite_entity(
    hass: HomeAssistant,
    speaker_or_device_id: str | None = None,
    coordinator: Any = None,
) -> str | None:
    """Resolve an assist_satellite.* entity for a speaker entity, HA device_id, or LatterCoordinator."""
    ent_reg = er.async_get(hass)
    cand_dev_ids: list[str] = []

    if coordinator is not None:
        esp_dev_id = getattr(coordinator, "esphome_device_id", None)
        if esp_dev_id:
            cand_dev_ids.append(str(esp_dev_id))

    target = str(speaker_or_device_id or "").strip()
    if target.startswith("assist_satellite."):
        st = hass.states.get(target)
        if st is not None and st.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return target

    if target.startswith("media_player."):
        reg_ent = ent_reg.async_get(target)
        if reg_ent and reg_ent.device_id and reg_ent.device_id not in cand_dev_ids:
            cand_dev_ids.append(reg_ent.device_id)
        sys_obj = get_latter_system(hass)
        all_coords: list[Any] = (
            list(sys_obj.coordinators.values())
            if sys_obj and sys_obj.coordinators
            else [
                v
                for v in hass.data.get(DOMAIN, {}).values()
                if hasattr(v, "device_slug")
            ]
        )
        for val in all_coords:
            local_spk = getattr(val, "local_speaker", None)
            if (
                local_spk == target
                or getattr(val, "active_speaker", None) == target
                or (
                    local_spk
                    and resolve_ma_counterpart_entity(hass, str(local_spk)) == target
                )
            ):
                c_dev_id = getattr(val, "esphome_device_id", None)
                if c_dev_id and str(c_dev_id) not in cand_dev_ids:
                    cand_dev_ids.append(str(c_dev_id))
    elif target and "." not in target and target not in cand_dev_ids:
        cand_dev_ids.append(target)

    for dev_id in cand_dev_ids:
        for entry in er.async_entries_for_device(ent_reg, dev_id):
            if entry.domain == "assist_satellite" and not entry.disabled_by:
                st = hass.states.get(entry.entity_id)
                if st is not None and st.state not in (
                    STATE_UNAVAILABLE,
                    STATE_UNKNOWN,
                ):
                    return entry.entity_id
    return None


async def async_announce_on_targets(
    hass: HomeAssistant,
    speakers: list[str],
    message: str = "",
    media_url: str = "",
    tts_entity: str = "",
    blocking: bool = False,
) -> None:
    """Route announcements through assist_satellite.announce first, deduplicating by physical device_id."""
    if not speakers or (not message and not media_url):
        return

    ent_reg = er.async_get(hass)
    satellites: list[str] = []
    fallback_speakers: list[str] = []
    seen_device_ids: set[str] = set()
    has_sat_announce = hass.services.has_service("assist_satellite", "announce")

    for spk in speakers:
        if not spk:
            continue
        sat_ent = (
            resolve_assist_satellite_entity(hass, spk) if has_sat_announce else None
        )
        if sat_ent:
            sat_reg = ent_reg.async_get(sat_ent)
            sat_dev_id = sat_reg.device_id if sat_reg and sat_reg.device_id else sat_ent
            if sat_dev_id in seen_device_ids:
                continue
            seen_device_ids.add(sat_dev_id)
            spk_reg = ent_reg.async_get(spk)
            if spk_reg and spk_reg.device_id:
                seen_device_ids.add(spk_reg.device_id)
            if sat_ent not in satellites:
                satellites.append(sat_ent)
        else:
            spk_reg = ent_reg.async_get(spk)
            spk_dev_id = spk_reg.device_id if spk_reg and spk_reg.device_id else spk
            if spk_dev_id in seen_device_ids:
                continue
            seen_device_ids.add(spk_dev_id)
            if spk not in fallback_speakers:
                fallback_speakers.append(spk)

    if satellites and has_sat_announce:
        sat_payload: dict[str, Any] = {ATTR_ENTITY_ID: satellites}
        if media_url:
            sat_payload["media_id"] = media_url
        else:
            sat_payload["message"] = message
        try:
            await hass.services.async_call(
                "assist_satellite",
                "announce",
                sat_payload,
                blocking=blocking,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug(
                "assist_satellite.announce failed on %s, falling back: %s",
                satellites,
                err,
            )
            for spk in speakers:
                if (
                    spk
                    and not spk.startswith("assist_satellite.")
                    and spk not in fallback_speakers
                ):
                    fallback_speakers.append(spk)

    if not fallback_speakers:
        return

    if media_url:
        ma_speakers = [
            s
            for s in fallback_speakers
            if (st := hass.states.get(s)) is not None
            and is_music_assistant_player(hass, st)
        ]
        other_speakers = [s for s in fallback_speakers if s not in ma_speakers]

        if ma_speakers and hass.services.has_service(
            "music_assistant", "play_announcement"
        ):
            await hass.services.async_call(
                "music_assistant",
                "play_announcement",
                {
                    ATTR_ENTITY_ID: ma_speakers,
                    "url": media_url,
                },
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
        return

    if message:
        if not tts_entity:
            tts_states = get_area_state_index(hass).states_for_domain("tts")
            if tts_states:
                tts_entity = tts_states[0].entity_id

        if tts_entity and hass.services.has_service("tts", "speak"):
            await hass.services.async_call(
                "tts",
                "speak",
                {
                    ATTR_ENTITY_ID: tts_entity,
                    "media_player_entity_id": fallback_speakers,
                    "message": message,
                    "cache": False,
                },
                blocking=blocking,
            )


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
    """Execute Music Assistant 2.10.8+ queue transfer, quiesce local Sendspin speaker, and verify position handoff."""
    src_ma = resolve_ma_counterpart_entity(hass, source_speaker)
    tgt_ma = resolve_ma_counterpart_entity(hass, target_speaker)
    cmd_target = tgt_ma or target_speaker
    is_from_local = bool(local_speaker and source_speaker == local_speaker)

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

    if is_from_local and source_speaker != target_speaker:
        try:
            await hass.services.async_call(
                "media_player",
                "media_pause",
                {ATTR_ENTITY_ID: source_speaker},
                blocking=False,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Failed quiescing local speaker %s: %s", source_speaker, err)

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

    try:
        async with asyncio.timeout(4.5):
            await asyncio.sleep(1.2)
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
                except Exception:  # noqa: BLE001
                    pass

            tgt_pos = float(updated_tgt.attributes.get("media_position") or 0.0)
            if handoff_position > 5.0 and abs(tgt_pos - handoff_position) > 4.0:
                try:
                    await hass.services.async_call(
                        "media_player",
                        "media_seek",
                        {
                            ATTR_ENTITY_ID: cmd_target,
                            "seek_position": round(handoff_position, 1),
                        },
                        blocking=False,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Position handoff media_seek failed: %s", err)
    except TimeoutError:
        _LOGGER.debug("Queue transfer handoff timed out for %s", target_speaker)


async def async_resume_idle_speaker_queue(
    hass: HomeAssistant,
    speaker_entity_id: str,
    last_media_uri: str,
    last_media_position: float,
    last_media_type: str,
) -> bool:
    """Resume playback on an idle speaker if native media_play does not start within 2.2s after cold boot."""
    await asyncio.sleep(2.2)
    cur_state = hass.states.get(speaker_entity_id)
    if cur_state is not None and cur_state.state in (STATE_PLAYING, STATE_BUFFERING):
        return True

    ma_entity = resolve_ma_counterpart_entity(hass, speaker_entity_id)
    if ma_entity and ma_entity != speaker_entity_id:
        try:
            await hass.services.async_call(
                "media_player",
                "media_play",
                {ATTR_ENTITY_ID: ma_entity},
                blocking=True,
            )
            await asyncio.sleep(1.0)
            cur_state = hass.states.get(speaker_entity_id)
            if cur_state is not None and cur_state.state in (
                STATE_PLAYING,
                STATE_BUFFERING,
            ):
                return True
        except Exception:  # noqa: BLE001
            pass

    resume_uri, resume_pos = await async_find_queue_resume_item(
        hass,
        speaker_entity_id,
        last_media_uri,
        last_media_position,
    )
    if not resume_uri:
        _LOGGER.debug(
            "No resumable queue URI found for idle speaker '%s'", speaker_entity_id
        )
        return False

    play_target = ma_entity or speaker_entity_id
    try:
        if hass.services.has_service("music_assistant", "play_media") and (
            ma_entity
            or (is_music_assistant_player(hass, cur_state) if cur_state else False)
        ):
            await async_play_media_with_ma_fallback(
                hass,
                play_target,
                resume_uri,
                media_type=last_media_type or "music",
            )
        else:
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    ATTR_ENTITY_ID: play_target,
                    "media_content_id": resume_uri,
                    "media_content_type": last_media_type or "music",
                },
                blocking=True,
            )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Post-reboot play_media failed on %s: %s", play_target, err)
        return False

    if resume_pos > 5.0:
        await asyncio.sleep(1.2)
        try:
            await hass.services.async_call(
                "media_player",
                "media_seek",
                {
                    ATTR_ENTITY_ID: play_target,
                    "seek_position": round(resume_pos, 1),
                },
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            pass
    return True


def _resolve_speaker_media_snapshot(
    coordinator: LatterCoordinator,
) -> tuple[
    State | None,
    State | None,
    str,
    dict[str, Any],
    dict[str, Any],
    str,
    str,
    str,
    float,
    float,
    str,
    int,
]:
    """Resolve live speaker state, counterpart attributes, and active track metadata without side effects."""
    hass = coordinator.hass
    state_obj = hass.states.get(coordinator.active_speaker)
    ma_counterpart = resolve_ma_counterpart_entity(hass, coordinator.active_speaker)
    ma_st = (
        hass.states.get(ma_counterpart)
        if ma_counterpart and ma_counterpart != coordinator.active_speaker
        else None
    )
    if (
        state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN)
    ) and ma_st is not None:
        state_obj = ma_st

    is_local_flag = (
        1 if coordinator.is_local_speaker_entity(coordinator.active_speaker) else 0
    )
    if state_obj is None or state_obj.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None, ma_st, "", {}, {}, "", "", "", 0.0, 0.0, "", is_local_flag

    state = state_obj.state
    if (
        state in (STATE_IDLE, STATE_OFF)
        and ma_st is not None
        and ma_st.state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
    ):
        state = ma_st.state
    if state not in (
        STATE_PLAYING,
        STATE_PAUSED,
        STATE_IDLE,
        STATE_BUFFERING,
        STATE_OFF,
    ):
        state = STATE_IDLE

    attrs: dict[str, Any] = dict(state_obj.attributes)
    m_attrs: dict[str, Any] = dict(ma_st.attributes) if ma_st is not None else {}

    title = str(attrs.get("media_title") or "")
    artist = str(
        attrs.get("media_artist")
        or attrs.get("media_series_title")
        or attrs.get("media_album_artist")
        or ""
    )
    album = str(attrs.get("media_album_name") or "")
    duration = float(attrs.get("media_duration") or 0.0)
    position = interpolate_speaker_position(state_obj)

    if not title and m_attrs.get("media_title"):
        title = str(m_attrs.get("media_title") or title)
        artist = str(
            m_attrs.get("media_artist")
            or m_attrs.get("media_series_title")
            or m_attrs.get("media_album_artist")
            or artist
        )
        album = str(m_attrs.get("media_album_name") or album)
    if duration <= 0 and m_attrs.get("media_duration"):
        duration = float(m_attrs.get("media_duration") or duration)
    if position <= 0 and ma_st is not None:
        position = interpolate_speaker_position(ma_st) or position

    if not title and bool(is_local_flag):
        t_st = coordinator.device_state("sensor", "_now_playing_title")
        a_st = coordinator.device_state("sensor", "_now_playing_artist")
        al_st = coordinator.device_state("sensor", "_now_playing_album")
        if t_st is not None and ha_value(t_st.state):
            title = str(t_st.state)
            if a_st is not None and ha_value(a_st.state):
                artist = str(a_st.state)
            if al_st is not None and ha_value(al_st.state):
                album = str(al_st.state)

    raw_type = str(
        attrs.get("media_content_type") or m_attrs.get("media_content_type") or ""
    ).lower()
    if not raw_type:
        media_type = ""
    elif "podcast" in raw_type:
        media_type = "podcast"
    elif "audiobook" in raw_type or "book" in raw_type:
        media_type = "audiobook"
    else:
        media_type = "music"

    return (
        state_obj,
        ma_st,
        state,
        attrs,
        m_attrs,
        title,
        artist,
        album,
        duration,
        position,
        media_type,
        is_local_flag,
    )


@callback
def _sync_active_speaker_media_snapshot(coordinator: LatterCoordinator) -> None:
    """Update persisted last_media_* fields when the active speaker is playing, paused, or buffering."""
    (
        state_obj,
        _ma_st,
        state,
        attrs,
        m_attrs,
        title,
        artist,
        album,
        duration,
        position,
        media_type,
        _is_local_flag,
    ) = _resolve_speaker_media_snapshot(coordinator)
    if state_obj is None or not title or state not in (
        STATE_PLAYING,
        STATE_PAUSED,
        STATE_BUFFERING,
    ):
        return
    cid = str(attrs.get("media_content_id") or m_attrs.get("media_content_id") or "")
    if cid:
        coordinator.last_media_uri = cid
    coordinator.last_media_type = media_type
    coordinator.last_media_title = title
    coordinator.last_media_artist = artist
    coordinator.last_media_album = album
    if duration > 0:
        coordinator.last_media_duration = duration
    if position > 0:
        coordinator.last_media_position = position


@callback
def bind_coordinator_speaker_listener(coordinator: LatterCoordinator) -> None:
    """Subscribe to state changes on the active media_player (and its volume override entity)."""
    if coordinator._unsub_speaker_state is not None:
        coordinator._unsub_speaker_state()
        coordinator._unsub_speaker_state = None

    if not coordinator.active_speaker:
        return

    tracked = [coordinator.active_speaker]
    vol_target = coordinator.get_volume_target_entity(coordinator.active_speaker)
    if vol_target and vol_target != coordinator.active_speaker:
        tracked.append(vol_target)
    ma_counterpart = resolve_ma_counterpart_entity(
        coordinator.hass, coordinator.active_speaker
    )
    if ma_counterpart and ma_counterpart not in tracked:
        tracked.append(ma_counterpart)
    if coordinator.is_local_speaker_entity(coordinator.active_speaker):
        np_title = coordinator.device_entity("sensor", "_now_playing_title")
        if np_title and np_title not in tracked:
            tracked.append(np_title)

    _sync_active_speaker_media_snapshot(coordinator)

    @callback
    def _on_speaker_state_change(event: Event[EventStateChangedData]) -> None:
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        coordinator._cached_media_anchor = None
        _sync_active_speaker_media_snapshot(coordinator)
        if is_media_position_only_tick(old_state, new_state):
            # Update active_media cache/listeners without invalidating Area payload cache
            coordinator._cached_media_payload = None
            coordinator._notify_debouncer.async_schedule_call()
            return
        coordinator.async_notify_listeners()

    coordinator._unsub_speaker_state = async_track_state_change_event(
        coordinator.hass,
        tracked,
        _on_speaker_state_change,
    )


@callback
def enforce_local_speaker_if_remote_idle(
    coordinator: LatterCoordinator, reason: str
) -> None:
    """Reset active_speaker to local_speaker on boot/wake unless the remote speaker is actively playing."""
    local_spk = coordinator.local_speaker
    if not local_spk:
        return
    if coordinator.is_local_speaker_entity(coordinator.active_speaker):
        if coordinator.active_speaker != local_spk:
            coordinator.active_speaker = local_spk
            bind_coordinator_speaker_listener(coordinator)
            coordinator._schedule_persist_runtime_state()
        return

    remote_state = coordinator.hass.states.get(coordinator.active_speaker)
    is_remote_playing = bool(
        remote_state and remote_state.state in (STATE_PLAYING, STATE_BUFFERING)
    )
    if not is_remote_playing:
        _LOGGER.info(
            "Resetting active_speaker from idle remote '%s' (state=%s) to local_speaker '%s' (%s)",
            coordinator.active_speaker,
            remote_state.state if remote_state else "missing",
            local_spk,
            reason,
        )
        coordinator.last_speaker = coordinator.active_speaker
        coordinator.active_speaker = local_spk
        bind_coordinator_speaker_listener(coordinator)
        coordinator._schedule_persist_runtime_state()


@callback
def set_coordinator_active_speaker(
    coordinator: LatterCoordinator, speaker_entity_id: str, transfer_queue: bool = True
) -> None:
    """Switch the active target speaker, persist to Store, and optionally transfer active queue."""
    speaker_entity_id = speaker_entity_id.strip()
    if not speaker_entity_id:
        return

    prev_speaker = coordinator.active_speaker
    if speaker_entity_id != prev_speaker:
        prev_state = coordinator.hass.states.get(prev_speaker)
        was_playing = bool(
            prev_state and prev_state.state in (STATE_PLAYING, STATE_BUFFERING)
        )
        was_active = bool(
            prev_state
            and prev_state.state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
        )
        handoff_pos = interpolate_speaker_position(prev_state)

        if was_active and prev_state is not None:
            p_attrs = prev_state.attributes
            coordinator._transfer_hold_until = (
                time.monotonic() + TRANSFER_HOLD_WINDOW_SECONDS
            )
            coordinator._transfer_hold_position = handoff_pos
            coordinator._transfer_hold_title = str(p_attrs.get("media_title") or "")
            coordinator._transfer_hold_artist = str(
                p_attrs.get("media_artist")
                or p_attrs.get("media_series_title")
                or p_attrs.get("media_album_artist")
                or ""
            )
            coordinator._transfer_hold_album = str(
                p_attrs.get("media_album_name") or ""
            )
            coordinator._transfer_hold_duration = float(
                p_attrs.get("media_duration") or 0.0
            )

            if transfer_queue:
                media_cid = str(
                    p_attrs.get("media_content_id") or coordinator.last_media_uri or ""
                )
                media_ctype = str(
                    p_attrs.get("media_content_type")
                    or coordinator.last_media_type
                    or "music"
                )

                async def _do_transfer() -> None:
                    await async_execute_ma_queue_transfer(
                        coordinator.hass,
                        coordinator.local_speaker,
                        prev_speaker,
                        speaker_entity_id,
                        was_playing,
                        handoff_pos,
                        media_cid,
                        media_ctype,
                    )
                    coordinator.async_notify_listeners()

                coordinator.entry.async_create_background_task(
                    coordinator.hass,
                    _do_transfer(),
                    f"latter_queue_transfer_{coordinator.device_slug}",
                )

        coordinator.last_speaker = prev_speaker
        coordinator.active_speaker = speaker_entity_id
        coordinator._schedule_persist_runtime_state()

    bind_coordinator_speaker_listener(coordinator)
    coordinator.async_notify_listeners()


async def execute_coordinator_media_command(
    coordinator: LatterCoordinator,
    command: str,
    speaker: str | None = None,
    seek_position: float | None = None,
    media_id: str | None = None,
    media_type: str | None = None,
    enqueue: str | None = None,
    group_members: list[str] | str | None = None,
) -> None:
    """Execute a unified media playback command with 2.5s play debounce and post-reboot Sendspin queue recovery."""
    hass = coordinator.hass
    target_spk = (
        speaker or coordinator.active_speaker or coordinator.local_speaker
    ).strip()
    if not target_spk:
        return

    cmd = command.strip().lower()
    ma_target = resolve_ma_counterpart_entity(hass, target_spk)
    cmd_target = ma_target or target_spk
    state_obj = hass.states.get(target_spk)
    ma_state_obj = (
        hass.states.get(ma_target)
        if ma_target and ma_target != target_spk
        else None
    )
    cur_state = state_obj.state if state_obj else STATE_IDLE
    if (
        cur_state in (STATE_IDLE, STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN)
        and ma_state_obj is not None
        and ma_state_obj.state in (STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING)
    ):
        cur_state = ma_state_obj.state

    if cmd == "toggle":
        cmd = "pause" if cur_state in (STATE_PLAYING, STATE_BUFFERING) else "play"

    if cmd == "play_media" and media_id:
        coordinator._local_needs_cold_resume = False
        await async_play_media_with_ma_fallback(
            hass,
            target_spk,
            media_id,
            media_type=media_type,
            enqueue=enqueue,
        )
        return

    if cmd == "play":
        now = time.monotonic()
        if now < coordinator._resuming_guard_until:
            return
        coordinator._resuming_guard_until = now + 2.5
        await hass.services.async_call(
            "media_player",
            "media_play",
            {ATTR_ENTITY_ID: cmd_target},
            blocking=False,
        )
        is_local = coordinator.is_local_speaker_entity(target_spk)
        if (
            is_local
            and coordinator._local_needs_cold_resume
            and cur_state in (STATE_IDLE, STATE_OFF, "stopped")
        ):
            coordinator._resuming_guard_until = time.monotonic() + 3.5
            resumed = await async_resume_idle_speaker_queue(
                hass,
                target_spk,
                coordinator.last_media_uri,
                coordinator.last_media_position,
                coordinator.last_media_type,
            )
            if resumed:
                coordinator._local_needs_cold_resume = False
                coordinator.async_notify_listeners()
        return

    if cmd == "pause":
        await hass.services.async_call(
            "media_player", "media_pause", {ATTR_ENTITY_ID: cmd_target}, blocking=False
        )
        return

    if cmd in ("next", "next_track", "media_next_track"):
        await hass.services.async_call(
            "media_player",
            "media_next_track",
            {ATTR_ENTITY_ID: cmd_target},
            blocking=False,
        )
        return

    if cmd in ("previous", "previous_track", "media_previous_track"):
        await hass.services.async_call(
            "media_player",
            "media_previous_track",
            {ATTR_ENTITY_ID: cmd_target},
            blocking=False,
        )
        return

    if cmd == "stop":
        await hass.services.async_call(
            "media_player", "media_stop", {ATTR_ENTITY_ID: cmd_target}, blocking=False
        )
        return

    if cmd == "clear_queue":
        await hass.services.async_call(
            "media_player",
            "clear_playlist",
            {ATTR_ENTITY_ID: cmd_target},
            blocking=False,
        )
        return

    if cmd == "seek" and seek_position is not None:
        await hass.services.async_call(
            "media_player",
            "media_seek",
            {
                ATTR_ENTITY_ID: cmd_target,
                "seek_position": round(float(seek_position), 1),
            },
            blocking=False,
        )
        return

    if cmd == "join":
        raw_members = (
            [group_members]
            if isinstance(group_members, str)
            else list(group_members or [])
        )
        resolved_members: list[str] = []
        for item in raw_members:
            cand = str(item or "").strip()
            if not cand or not cand.startswith("media_player."):
                continue
            if ma_target:
                cand = resolve_ma_counterpart_entity(hass, cand) or cand
            if cand != cmd_target and cand not in resolved_members:
                resolved_members.append(cand)
        if resolved_members:
            await hass.services.async_call(
                "media_player",
                "join",
                {
                    ATTR_ENTITY_ID: cmd_target,
                    "group_members": resolved_members,
                },
                blocking=False,
            )
        return

    if cmd == "unjoin":
        await hass.services.async_call(
            "media_player", "unjoin", {ATTR_ENTITY_ID: cmd_target}, blocking=False
        )


def build_active_media_payload(
    coordinator: LatterCoordinator,
) -> tuple[str | None, dict[str, Any]]:
    """Compute state and attributes for sensor.<device_slug>_active_media."""
    now_m = time.monotonic()
    if (
        coordinator._cached_media_payload is not None
        and (now_m - coordinator._cached_media_payload[0]) < 0.05
    ):
        return coordinator._cached_media_payload[1]
    (
        state_obj,
        _ma_st,
        state,
        attrs,
        m_attrs,
        title,
        artist,
        album,
        duration,
        position,
        media_type,
        is_local_flag,
    ) = _resolve_speaker_media_snapshot(coordinator)

    vol_target = coordinator.get_volume_target_entity(coordinator.active_speaker)
    fallback_spk_name = (
        coordinator.device_title
        if is_local_flag
        else (
            coordinator.active_speaker.split(".", 1)[-1].replace("_", " ").title()
            if coordinator.active_speaker
            else ""
        )
    )

    if state_obj is None:
        idle_title = coordinator.last_media_title
        idle_artist = coordinator.last_media_artist
        idle_album = coordinator.last_media_album
        idle_dur = (
            round(coordinator.last_media_duration, 1)
            if coordinator.last_media_duration > 0
            else None
        )
        idle_pos = round(coordinator.last_media_position, 1)
        idle_type = coordinator.last_media_type if coordinator.last_media_title else ""
        idle_vol = read_volume_from_target(coordinator.hass, vol_target, {})
        idle_vol_r = round(idle_vol, 2) if idle_vol is not None else None
        idle_vol_pct = (
            round(max(0.0, min(1.0, idle_vol)) * 100.0)
            if idle_vol is not None
            else None
        )
        med_rev, med_payload = coordinator._pack_domain_payload(
            "active_media",
            "",
            idle_title,
            idle_artist,
            idle_album,
            idle_dur,
            idle_pos,
            None,
            idle_vol_pct,
            idle_type,
            0,
            "",
            coordinator.active_speaker,
            fallback_spk_name,
            coordinator.last_speaker,
            coordinator.local_speaker,
            vol_target,
            is_local_flag,
        )
        res: tuple[str | None, dict[str, Any]] = (
            None,
            {
                "title": idle_title,
                "artist": idle_artist,
                "album": idle_album,
                "duration": idle_dur,
                "position": idle_pos,
                "position_updated_at": None,
                "volume": idle_vol_r,
                "media_type": idle_type,
                "supported_features": 0,
                "art_url": "",
                "active_speaker": coordinator.active_speaker,
                "speaker_name": fallback_spk_name,
                "last_speaker": coordinator.last_speaker,
                "local_speaker": coordinator.local_speaker,
                "volume_entity": vol_target,
                "is_local": bool(is_local_flag),
                "rev": med_rev,
                "payload": med_payload,
            },
        )
        coordinator._cached_media_payload = (now_m, res)
        return res

    in_transfer_window = time.monotonic() < coordinator._transfer_hold_until
    if in_transfer_window:
        if not title and coordinator._transfer_hold_title:
            title = coordinator._transfer_hold_title
            artist = coordinator._transfer_hold_artist or artist
            album = coordinator._transfer_hold_album or album
            duration = coordinator._transfer_hold_duration or duration
        if position < 1.0 and coordinator._transfer_hold_position > 1.0:
            position = coordinator._transfer_hold_position
    elif (
        not title
        and state == STATE_IDLE
        and coordinator.last_media_title
        and bool(is_local_flag)
    ):
        title = coordinator.last_media_title
        artist = coordinator.last_media_artist
        album = coordinator.last_media_album
        duration = coordinator.last_media_duration
        position = coordinator.last_media_position
        media_type = coordinator.last_media_type

    volume = read_volume_from_target(coordinator.hass, vol_target, attrs)
    if volume is None and m_attrs:
        volume = read_volume_from_target(coordinator.hass, vol_target, m_attrs)
    supported_features = int(attrs.get("supported_features") or 0)
    if vol_target != coordinator.active_speaker:
        vol_state = coordinator.hass.states.get(vol_target)
        if vol_state is not None:
            if vol_state.domain in ("number", "input_number"):
                supported_features |= VOLUME_FEATURE_FLAGS
            else:
                vol_feat = int(vol_state.attributes.get("supported_features") or 0)
                supported_features |= vol_feat & VOLUME_FEATURE_FLAGS

    raw_pic = str(
        attrs.get("entity_picture_local")
        or attrs.get("entity_picture")
        or attrs.get("media_image_url")
        or m_attrs.get("entity_picture_local")
        or m_attrs.get("entity_picture")
        or m_attrs.get("media_image_url")
        or ""
    )
    track_key = f"{title}|{artist}|{album}"

    if state == STATE_OFF or not title:
        art_url = ""
    elif raw_pic:
        coordinator.last_valid_raw_pic = raw_pic
        coordinator._last_art_track_key = track_key
        coordinator._last_art_proxy_url = coordinator.build_proxy_art_url(
            f"{track_key}|{raw_pic}"
        )
        art_url = coordinator._last_art_proxy_url
    elif (
        track_key == coordinator._last_art_track_key or in_transfer_window
    ) and coordinator._last_art_proxy_url:
        art_url = coordinator._last_art_proxy_url
    else:
        art_url = ""

    speaker_name = (
        coordinator.device_title
        if is_local_flag
        else str(attrs.get("friendly_name") or fallback_spk_name)
    )

    raw_updated_at = attrs.get("media_position_updated_at") or m_attrs.get(
        "media_position_updated_at"
    )
    if isinstance(raw_updated_at, datetime):
        pos_updated_at = int(raw_updated_at.timestamp())
    elif raw_updated_at:
        parsed_ua = dt_util.parse_datetime(str(raw_updated_at))
        pos_updated_at = int(parsed_ua.timestamp()) if parsed_ua else 0
    else:
        pos_updated_at = 0

    dur_r = round(duration, 1) if duration > 0 else None
    vol_r = round(volume, 2) if volume is not None else None
    vol_pct = (
        round(max(0.0, min(1.0, volume)) * 100.0)
        if volume is not None
        else None
    )
    raw_pos = float(attrs.get("media_position") or m_attrs.get("media_position") or 0.0)
    media_anchor = (
        state,
        title,
        artist,
        album,
        dur_r,
        round(raw_pos, 1),
        pos_updated_at,
        vol_pct,
        media_type,
        supported_features,
        art_url,
        coordinator.active_speaker,
        speaker_name,
        coordinator.last_speaker,
        coordinator.local_speaker,
        vol_target,
        is_local_flag,
    )
    if (
        coordinator._cached_media_anchor is not None
        and coordinator._cached_media_anchor[0] == media_anchor
    ):
        pos_r = coordinator._cached_media_anchor[1]
    else:
        pos_r = round(position, 1)
        coordinator._cached_media_anchor = (media_anchor, pos_r)

    med_rev, med_payload = coordinator._pack_domain_payload(
        "active_media",
        state,
        title,
        artist,
        album,
        dur_r,
        pos_r,
        pos_updated_at or None,
        vol_pct,
        media_type,
        supported_features,
        art_url,
        coordinator.active_speaker,
        speaker_name,
        coordinator.last_speaker,
        coordinator.local_speaker,
        vol_target,
        is_local_flag,
    )
    res = (
        state,
        {
            "title": title,
            "artist": artist,
            "album": album,
            "duration": dur_r,
            "position": pos_r,
            "position_updated_at": pos_updated_at,
            "volume": vol_r,
            "media_type": media_type,
            "supported_features": supported_features,
            "art_url": art_url,
            "active_speaker": coordinator.active_speaker,
            "speaker_name": speaker_name,
            "last_speaker": coordinator.last_speaker,
            "local_speaker": coordinator.local_speaker,
            "volume_entity": vol_target,
            "is_local": bool(is_local_flag),
            "rev": med_rev,
            "payload": med_payload,
        },
    )
    coordinator._cached_media_payload = (now_m, res)
    return res
