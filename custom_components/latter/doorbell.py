"""Doorbell ring auto-detection, camera popup reflex, listen stream trigger, and push-to-talk replies (`L2a`)."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any, Final

from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import DOMAIN, DOORBELL_NOISE_REDUCTION_LEVELS, normalize_noise_reduction
from .doorbell_targets import (
    resolve_doorbell_ring_entities as resolve_doorbell_ring_entities,
    resolve_doorbell_targets as resolve_doorbell_targets,
)
from .hub_registry import get_area_state_index
from .identity import esphome_service
from .media.announce import async_announce_on_targets
from .protocol_codec import utf8_safe_truncate

_LOGGER = logging.getLogger(__name__)

_MIN_DOOR_SPEAKER_VOL: Final = 0.25
_BOOSTED_DOOR_SPEAKER_VOL: Final = 0.80
_RING_COOLDOWN_S: Final = 15.0
_EVENT_FRESHNESS_S: Final = 15.0
_ALERT_TITLE_MAX_BYTES: Final = 48
_ALERT_MSG_MAX_BYTES: Final = 160
_ALERT_DURATION_S: Final = 20
_DEFAULT_QUICK_REPLY: Final = "Please leave the package at the door, thank you."


def _spawn_coordinator_task(
    hass: HomeAssistant, coordinator: Any, coro: Any, task_name: str
) -> asyncio.Task[Any]:
    create_fn = getattr(coordinator, "create_background_task", None)
    if callable(create_fn):
        task: asyncio.Task[Any] = create_fn(coro, task_name)
        return task
    entry = getattr(coordinator, "entry", None)
    if entry is not None and hasattr(entry, "async_create_background_task"):
        task = entry.async_create_background_task(hass, coro, task_name)
        return task
    fallback_task: asyncio.Task[Any] = hass.async_create_task(coro, task_name)
    return fallback_task


def _cancel_pending_reply(coordinator: Any) -> None:
    prev_task = coordinator.doorbell_reply_task
    if prev_task is not None and not prev_task.done():
        prev_task.cancel()
    coordinator.doorbell_reply_task = None
    coordinator.doorbell_reply_resume_listen = False


def _select_intercom_camera(
    coordinator: Any, camera_entity: str | None, camera_index: int | None
) -> str:
    cams = list(getattr(coordinator, "visible_camera_entities", coordinator.camera_entities) or ())
    explicit_cam = (camera_entity or "").strip()
    if explicit_cam and explicit_cam not in set(cams):
        raise ServiceValidationError(
            f"Camera '{explicit_cam}' is not configured as visible on {coordinator.device_title}.",
            translation_domain=DOMAIN,
            translation_key="not_supported",
        )
    if camera_index is not None and cams and not isinstance(camera_index, bool):
        try:
            idx = max(0, min(len(cams) - 1, int(camera_index)))
            coordinator.active_carousel_camera = cams[idx]
        except (TypeError, ValueError):
            pass

    cam_set = set(cams)
    active_cam = coordinator.active_carousel_camera if coordinator.active_carousel_camera in cam_set else ""
    default_cam = coordinator.camera_entity if coordinator.camera_entity in cam_set else ""
    cam_ent = explicit_cam or active_cam or default_cam or (cams[0] if cams else "")
    if cam_ent:
        coordinator.active_carousel_camera = cam_ent
    return cam_ent


async def _async_stop_local_speaker(hass: HomeAssistant, local_spk: str) -> None:
    if not local_spk:
        return
    try:
        await hass.services.async_call(
            "media_player", "media_stop", {ATTR_ENTITY_ID: local_spk}, blocking=False
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Doorbell media_stop on %s skipped: %s", local_spk, err)


async def _async_boost_door_speaker_if_quiet(hass: HomeAssistant, door_spk: str) -> None:
    mp_st = hass.states.get(door_spk)
    if mp_st is None:
        return
    cur_vol = mp_st.attributes.get("volume_level")
    if cur_vol is None or isinstance(cur_vol, bool):
        return
    try:
        f_vol = float(cur_vol)
    except (TypeError, ValueError):
        return
    if math.isfinite(f_vol) and f_vol < _MIN_DOOR_SPEAKER_VOL:
        try:
            await hass.services.async_call(
                "media_player",
                "volume_set",
                {ATTR_ENTITY_ID: door_spk, "volume_level": _BOOSTED_DOOR_SPEAKER_VOL},
                blocking=True,
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Doorbell speaker volume boost on %s skipped: %s", door_spk, err)


async def _async_handle_doorbell_talk(  # noqa: PLR0913
    hass: HomeAssistant,
    coordinator: Any,
    *,
    cam_ent: str,
    local_spk: str,
    target_info: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    async with coordinator.doorbell_talk_lock:
        spoken_text = (message or "").strip() or _DEFAULT_QUICK_REPLY
        prev_task = coordinator.doorbell_reply_task
        inherit_resume = False
        if prev_task is not None and not prev_task.done():
            prev_task.cancel()
            inherit_resume = coordinator.doorbell_reply_resume_listen
        was_listening = coordinator.doorbell_talk_state == "listening" or (
            coordinator.doorbell_talk_state == "talking" and inherit_resume
        )
        coordinator.doorbell_reply_resume_listen = was_listening
        coordinator.doorbell_talk_state = "talking"
        coordinator.async_notify_listeners()

        if local_spk and was_listening:
            await _async_stop_local_speaker(hass, local_spk)

        door_spk = target_info["door_speaker"]
        if door_spk:
            await _async_boost_door_speaker_if_quiet(hass, door_spk)
            tts_text = f"... {spoken_text}" if target_info["tts_lead_in"] else spoken_text
            tts_states = get_area_state_index(hass).states_for_domain("tts")
            tts_ent = tts_states[0].entity_id if tts_states else ""
            try:
                await async_announce_on_targets(
                    hass,
                    speakers=[door_spk],
                    message=tts_text,
                    tts_entity=tts_ent,
                    blocking=True,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Doorbell TTS announce to %s failed: %s", door_spk, err)

        est_duration = max(2.2, min(8.0, len(spoken_text) * 0.085 + 1.2))

        async def _post_reply_restore() -> None:
            await asyncio.sleep(est_duration)
            if coordinator.doorbell_talk_state != "talking":
                return
            if was_listening:
                await async_execute_doorbell_intercom(
                    hass, coordinator, action="listen_start", camera_entity=cam_ent
                )
            else:
                coordinator.doorbell_talk_state = "idle"
                coordinator.async_notify_listeners()

        coordinator.doorbell_reply_task = _spawn_coordinator_task(
            hass, coordinator, _post_reply_restore(), f"latter_doorbell_reply_{coordinator.device_slug}"
        )
        return target_info


async def _async_start_camera_audio_listen(
    hass: HomeAssistant, coordinator: Any, local_spk: str, cam_ent: str
) -> None:
    if not local_spk or not cam_ent:
        return
    _cancel_pending_reply(coordinator)
    coordinator.doorbell_talk_state = "listening"
    coordinator.async_notify_listeners()
    nr_norm = normalize_noise_reduction(coordinator.doorbell_noise_reduction)
    stream_url = coordinator.build_camera_audio_url(cam_ent, nr_norm, "flac")
    try:
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: local_spk,
                "media_content_id": stream_url,
                "media_content_type": "music",
                "announce": True,
            },
            blocking=False,
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Failed starting camera audio listen on %s: %s", local_spk, err)


async def async_execute_doorbell_intercom(  # noqa: PLR0913, PLR0917
    hass: HomeAssistant,
    coordinator: Any,
    action: str,
    camera_entity: str | None = None,
    message: str = "",
    noise_reduction: str | None = None,
    camera_index: int | None = None,
) -> dict[str, Any]:
    """Execute a doorbell listen, push-to-talk reply, noise-reduction, or camera carousel action."""
    act = (action or "listen_toggle").strip().lower()
    if noise_reduction and (nr_val := noise_reduction.strip().lower()) in DOORBELL_NOISE_REDUCTION_LEVELS:
        coordinator.doorbell_noise_reduction = nr_val

    cam_ent = _select_intercom_camera(coordinator, camera_entity, camera_index)
    target_info = resolve_doorbell_targets(hass, cam_ent, coordinator.volume_overrides)
    local_spk = coordinator.local_speaker

    if act == "select_camera" or (
        act == "set_noise_reduction"
        and not (coordinator.doorbell_talk_state == "listening" and local_spk and cam_ent)
    ):
        coordinator.async_notify_listeners()
        return target_info

    if act == "set_noise_reduction":
        act = "listen_start"
    elif act == "listen_toggle":
        act = "listen_stop" if coordinator.doorbell_talk_state == "listening" else "listen_start"

    if act == "listen_stop":
        _cancel_pending_reply(coordinator)
        coordinator.doorbell_talk_state = "idle"
        coordinator.async_notify_listeners()
        await _async_stop_local_speaker(hass, local_spk)
    elif act == "listen_start":
        await _async_start_camera_audio_listen(hass, coordinator, local_spk, cam_ent)
    elif act in ("talk_message", "quick_reply", "talk"):
        await _async_handle_doorbell_talk(
            hass,
            coordinator,
            cam_ent=cam_ent,
            local_spk=local_spk,
            target_info=target_info,
            message=message,
        )
    return target_info


def _is_valid_ring_transition(event: Event[EventStateChangedData]) -> str | None:
    entity_id = event.data.get("entity_id")
    old_state = event.data.get("old_state")
    new_state = event.data.get("new_state")
    if not entity_id or new_state is None or old_state is None:
        return None
    if old_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None
    if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, "off") or old_state.state == new_state.state:
        return None
    if entity_id.startswith("binary_sensor.") and new_state.state != "on":
        return None
    if entity_id.startswith("event."):
        ev_dt = dt_util.parse_datetime(new_state.state)
        if ev_dt is None or abs((dt_util.utcnow() - ev_dt).total_seconds()) > _EVENT_FRESHNESS_S:
            return None
    return str(entity_id)


@callback
def bind_coordinator_doorbell_listener(coordinator: Any) -> None:
    """Auto-detect sibling doorbell ring / visitor entities on configured cameras and subscribe."""
    coordinator.replace_doorbell_ring_unsub(None)
    if coordinator.is_ble_tag or not coordinator.has_display:
        return

    ring_map = resolve_doorbell_ring_entities(coordinator.hass, coordinator.camera_entities)
    coordinator.set_doorbell_ring_map(ring_map)
    if not ring_map:
        return

    @callback
    def _on_doorbell_ring(event: Event[EventStateChangedData]) -> None:
        entity_id = _is_valid_ring_transition(event)
        if not entity_id:
            return
        cam_ent = coordinator.doorbell_ring_map.get(entity_id) or coordinator.camera_entity
        if not cam_ent:
            return

        now_mono = time.monotonic()
        cooldowns = coordinator.doorbell_ring_cooldown_until
        if now_mono < cooldowns.get(cam_ent, 0.0):
            return
        cooldowns[cam_ent] = now_mono + _RING_COOLDOWN_S

        cam_st = coordinator.hass.states.get(cam_ent)
        cam_friendly = (
            str(cam_st.attributes.get("friendly_name") if cam_st else "")
            or cam_ent.split(".", 1)[-1].replace("_", " ").title()
        )
        title = "Doorbell Ringing"
        message = f"Visitor at {cam_friendly}"
        in_bedtime = bool(coordinator.get_device_pref("bedtime_active"))
        in_dnd = bool(getattr(coordinator, "do_not_disturb", False))
        chime_flag = not (in_bedtime or in_dnd)

        coordinator.async_dispatch_notification(
            title=title,
            message=message,
            priority="critical",
            duration=_ALERT_DURATION_S,
            chime=chime_flag,
            camera_entity=cam_ent,
        )

        esp_notify_svc = esphome_service(
            coordinator.hass, coordinator.esphome_device_id, "latter_show_notification"
        )
        if esp_notify_svc:
            payload = {
                "title": utf8_safe_truncate(title, _ALERT_TITLE_MAX_BYTES),
                "message": utf8_safe_truncate(message, _ALERT_MSG_MAX_BYTES),
                "priority": "critical",
                "duration": _ALERT_DURATION_S,
                "chime": chime_flag,
                "camera_url": coordinator.alert_camera_url,
                "camera_entity": coordinator.alert_camera_entity,
                "alert_id": coordinator.alert_id,
            }

            async def _async_push_doorbell_popup() -> None:
                try:
                    await coordinator.hass.services.async_call(
                        "esphome", esp_notify_svc, payload, blocking=True
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Doorbell esphome.%s push failed: %s", esp_notify_svc, err)

            _spawn_coordinator_task(
                coordinator.hass,
                coordinator,
                _async_push_doorbell_popup(),
                f"latter_doorbell_notify_{coordinator.device_slug}",
            )

    coordinator.replace_doorbell_ring_unsub(
        async_track_state_change_event(
            coordinator.hass,
            list(ring_map.keys()),
            _on_doorbell_ring,
        )
    )
