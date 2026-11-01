"""Per-device media playback, volume override, and Music Assistant queue transfer controller."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_BUFFERING,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant

from .browse_engine import is_music_assistant_player
from .media_engine import (
    async_find_queue_resume_item,
    async_play_media_with_ma_fallback,
    resolve_ma_counterpart_entity,
)

_LOGGER = logging.getLogger(__name__)

VOLUME_FEATURE_FLAGS: int = 4 | 8 | 1024  # VOLUME_SET | VOLUME_MUTE | VOLUME_STEP


def read_volume_from_target(
    hass: HomeAssistant, vol_target: str, fallback_attrs: dict[str, Any]
) -> float | None:
    """Read normalized 0.0..1.0 volume from media_player, number, or input_number, or None when unknown."""
    vol_state = hass.states.get(vol_target)
    if vol_state is not None and vol_state.state not in ("unavailable", "unknown"):
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
    src_state = hass.states.get(source_speaker)
    tgt_state = hass.states.get(target_speaker)
    src_is_ma = bool(src_state and is_music_assistant_player(hass, src_state))
    tgt_is_ma = bool(tgt_state and is_music_assistant_player(hass, tgt_state))
    is_from_local = bool(local_speaker and source_speaker == local_speaker)

    transferred_via_ma = False
    if (
        src_is_ma
        and tgt_is_ma
        and hass.services.has_service("music_assistant", "transfer_queue")
    ):
        try:
            await hass.services.async_call(
                "music_assistant",
                "transfer_queue",
                {
                    ATTR_ENTITY_ID: target_speaker,
                    "source_player": source_speaker,
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
                    {ATTR_ENTITY_ID: source_speaker},
                    blocking=False,
                )
            if tgt_is_ma and hass.services.has_service("music_assistant", "play_media"):
                await hass.services.async_call(
                    "music_assistant",
                    "play_media",
                    {
                        ATTR_ENTITY_ID: target_speaker,
                        "media_id": media_content_id,
                        "enqueue": "replace",
                    },
                    blocking=True,
                )
            else:
                await hass.services.async_call(
                    "media_player",
                    "play_media",
                    {
                        ATTR_ENTITY_ID: target_speaker,
                        "media_content_id": media_content_id,
                        "media_content_type": media_content_type or "music",
                    },
                    blocking=True,
                )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Fallback play_media handoff failed: %s", err)

    try:
        async with asyncio.timeout(4.5):
            await asyncio.sleep(1.2)
            updated_tgt = hass.states.get(target_speaker)
            if updated_tgt is None:
                return

            if was_playing and updated_tgt.state in (STATE_PAUSED, STATE_IDLE):
                try:
                    await hass.services.async_call(
                        "media_player",
                        "media_play",
                        {ATTR_ENTITY_ID: target_speaker},
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
                            ATTR_ENTITY_ID: target_speaker,
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
    device_slug: str,
    last_media_uri: str,
    last_media_position: float,
    last_media_type: str,
) -> bool:
    """Resume playback on an idle speaker if native media_play does not start within 2.2s after cold boot."""
    await asyncio.sleep(2.2)
    cur_state = hass.states.get(speaker_entity_id)
    if cur_state is not None and cur_state.state in (STATE_PLAYING, STATE_BUFFERING):
        return True

    ma_entity = resolve_ma_counterpart_entity(hass, speaker_entity_id, device_slug)
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
            if cur_state is not None and cur_state.state in (STATE_PLAYING, STATE_BUFFERING):
                return True
        except Exception:  # noqa: BLE001
            pass

    resume_uri, resume_pos = await async_find_queue_resume_item(
        hass,
        speaker_entity_id,
        device_slug,
        last_media_uri,
        last_media_position,
    )
    if not resume_uri:
        _LOGGER.debug("No resumable queue URI found for idle speaker '%s'", speaker_entity_id)
        return False

    play_target = ma_entity or speaker_entity_id
    _LOGGER.info(
        "Re-streaming post-reboot queue URI '%s' (pos=%.1fs) to '%s'",
        resume_uri,
        resume_pos,
        play_target,
    )
    try:
        if hass.services.has_service("music_assistant", "play_media") and (
            ma_entity or (is_music_assistant_player(hass, cur_state) if cur_state else False)
        ):
            await async_play_media_with_ma_fallback(
                hass,
                play_target,
                device_slug,
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
                    ATTR_ENTITY_ID: speaker_entity_id,
                    "seek_position": round(resume_pos, 1),
                },
                blocking=False,
            )
        except Exception:  # noqa: BLE001
            pass
    return True
