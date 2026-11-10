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


async def async_execute_volume_action(
    hass: HomeAssistant,
    vol_target: str,
    action: str,
    volume_level: float | None = None,
) -> bool:
    """Execute a volume action ('set', 'up', 'down', 'mute', 'volume_up', 'volume_down', 'volume_mute') on a media_player, number, or input_number."""
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
            if (state_obj and state_obj.state not in ("unavailable", "unknown"))
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
            "media_player",
            "volume_up",
            {ATTR_ENTITY_ID: vol_target},
            blocking=False,
        )
        return True
    if norm_action == "down":
        await hass.services.async_call(
            "media_player",
            "volume_down",
            {ATTR_ENTITY_ID: vol_target},
            blocking=False,
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
            if cur_state is not None and cur_state.state in (STATE_PLAYING, STATE_BUFFERING):
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
