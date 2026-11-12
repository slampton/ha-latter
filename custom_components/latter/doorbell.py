"""Doorbell ring auto-detection, camera popup reflex, listen stream trigger, and push-to-talk replies.

Listen: the camera's RTSP audio runs through an FFmpeg noise-reduction filter (served by
`LatterCameraAudioStreamView` in `http.py`) and streams to the device as FLAC. Talk: push-to-talk
relay; the device transcribes speech and sends the text (`talk_message`), and Home Assistant speaks
it with TTS on the camera's exact sibling `media_player`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SECURITY_PIN_HASH,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    DOORBELL_NOISE_REDUCTION_LEVELS,
    call_target_slugs,
    normalize_noise_reduction,
)
from .hub import _iter_registry_entities, get_area_state_index, iter_coordinators
from .identity import esphome_service
from .media import async_announce_on_targets
from .protocol import check_perimeter_action_allowed

_LOGGER = logging.getLogger(__name__)


def resolve_doorbell_targets(
    hass: HomeAssistant,
    camera_entity_id: str | None,
    volume_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve the door speaker media_player and lock for a camera strictly by explicit override or exact device_id."""
    info: dict[str, Any] = {
        "camera_entity": "",
        "friendly_name": "Camera",
        "door_speaker": "",
        "platform": "",
        "tts_lead_in": False,
        "area_id": "",
        "lock_entity": "",
    }
    if not camera_entity_id:
        return info

    cam_ent = camera_entity_id.strip()
    info["camera_entity"] = cam_ent
    cam_state = hass.states.get(cam_ent)
    if cam_state is not None:
        info["friendly_name"] = str(
            cam_state.attributes.get("friendly_name") or cam_ent
        )

    if volume_overrides and cam_ent in volume_overrides:
        mapped_spk = str(volume_overrides[cam_ent]).strip()
        if mapped_spk.startswith("media_player."):
            info["door_speaker"] = mapped_spk

    ent_reg = er.async_get(hass)
    cam_entry = ent_reg.async_get(cam_ent)

    if cam_entry is not None:
        info["platform"] = str(cam_entry.platform or "")

        if cam_entry.device_id:
            for sib in er.async_entries_for_device(ent_reg, cam_entry.device_id):
                if sib.disabled_by:
                    continue
                if sib.domain == "media_player" and not info["door_speaker"]:
                    info["door_speaker"] = sib.entity_id
                elif sib.domain == "lock" and not info["lock_entity"]:
                    info["lock_entity"] = sib.entity_id

    spk_entry = (
        ent_reg.async_get(info["door_speaker"]) if info["door_speaker"] else None
    )
    info["tts_lead_in"] = info["platform"] == "unifiprotect" or bool(
        spk_entry is not None and spk_entry.platform == "unifiprotect"
    )

    info["area_id"] = (
        get_area_state_index(hass).resolve_entity_area_id(cam_ent) or ""
    )
    return info


async def async_execute_doorbell_intercom(
    hass: HomeAssistant,
    coordinator: Any,
    action: str,
    camera_entity: str | None = None,
    message: str = "",
    noise_reduction: str | None = None,
    camera_index: int | None = None,
    code: str | None = None,
) -> dict[str, Any]:
    """Execute a doorbell listen / push-to-talk reply / unlock action, or ring other displays."""
    act = (action or "listen_toggle").strip().lower()

    if noise_reduction:
        nr_val = noise_reduction.strip().lower()
        if nr_val in DOORBELL_NOISE_REDUCTION_LEVELS:
            coordinator.doorbell_noise_reduction = nr_val

    cams = coordinator.camera_entities
    if camera_index is not None and cams:
        idx = max(0, min(len(cams) - 1, int(camera_index)))
        coordinator.active_carousel_camera = cams[idx]

    cam_ent = (
        (camera_entity or "").strip()
        or coordinator.active_carousel_camera
        or coordinator.camera_entity
        or (cams[0] if cams else "")
    )
    if cam_ent:
        coordinator.active_carousel_camera = cam_ent

    target_info = resolve_doorbell_targets(
        hass, cam_ent, coordinator.volume_overrides
    )
    local_spk = coordinator.local_speaker

    if act == "unlock_door":
        stored_hash = getattr(coordinator, "security_pin_hash", None)
        if not stored_hash:
            global_cfg = (hass.data.get(DOMAIN, {}) or {}).get(DATA_GLOBAL_CONFIG) or {}
            stored_hash = (
                str(global_cfg.get(CONF_SECURITY_PIN_HASH) or "").strip() or None
            )
        allowed, err_key = check_perimeter_action_allowed(
            getattr(coordinator, "security_pin_policy", "require_pin"),
            provided_code=code,
            stored_pin_hash=stored_hash,
        )
        if not allowed:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key=err_key,
            )
        lock_ent = target_info.get("lock_entity") or coordinator.lock_entity
        if lock_ent and hass.states.get(lock_ent) is not None:
            await hass.services.async_call(
                "lock", "unlock", {ATTR_ENTITY_ID: lock_ent}, blocking=True
            )
        return target_info

    if act == "call_target":
        slugs = call_target_slugs(
            iter_coordinators(hass), coordinator.device_slug, message
        )
        for slug in slugs:
            await hass.services.async_call(
                DOMAIN,
                "notify",
                {
                    "target_device": slug,
                    "title": f"Intercom: {coordinator.device_title}",
                    "message": "Tap to answer",
                    "priority": "critical",
                    "duration": 20,
                    "chime": True,
                },
                blocking=False,
            )
        return target_info

    if act == "select_camera":
        coordinator.async_notify_listeners()
        return target_info

    if act == "set_noise_reduction":
        if coordinator.doorbell_talk_state == "listening" and local_spk and cam_ent:
            act = "listen_start"
        else:
            coordinator.async_notify_listeners()
            return target_info

    if act == "listen_toggle":
        act = (
            "listen_stop"
            if coordinator.doorbell_talk_state == "listening"
            else "listen_start"
        )

    def _cancel_pending_reply() -> None:
        prev_task = coordinator._doorbell_reply_task
        if prev_task is not None and not prev_task.done():
            prev_task.cancel()
        coordinator._doorbell_reply_task = None
        coordinator._doorbell_reply_resume_listen = False

    if act == "listen_stop":
        _cancel_pending_reply()
        coordinator.doorbell_talk_state = "idle"
        coordinator.async_notify_listeners()
        if local_spk:
            try:
                await hass.services.async_call(
                    "media_player",
                    "media_stop",
                    {ATTR_ENTITY_ID: local_spk},
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                pass
        return target_info

    if act == "listen_start":
        if not local_spk or not cam_ent:
            return target_info
        _cancel_pending_reply()
        coordinator.doorbell_talk_state = "listening"
        coordinator.async_notify_listeners()
        nr_norm = normalize_noise_reduction(coordinator.doorbell_noise_reduction)
        if hasattr(coordinator, "build_camera_audio_url"):
            stream_url = coordinator.build_camera_audio_url(cam_ent, nr_norm, "flac")
        else:
            base_url = coordinator.get_lan_base_url()
            sig = coordinator.sign_on_demand_resource(
                f"camera_audio:{cam_ent}|{nr_norm}|flac"
            )
            stream_url = (
                f"{base_url}/api/latter/camera_audio/{coordinator.device_slug}"
                f"?entity_id={cam_ent}&nr={nr_norm}&fmt=flac"
                f"&v={int(time.time())}&sig={sig}"
            )
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
        return target_info

    if act in ("talk_message", "quick_reply", "talk"):
        spoken_text = (message or "").strip()
        if not spoken_text:
            spoken_text = "Please leave the package at the door, thank you."

        prev_task = coordinator._doorbell_reply_task
        inherit_resume = False
        if prev_task is not None and not prev_task.done():
            prev_task.cancel()
            inherit_resume = coordinator._doorbell_reply_resume_listen
        was_listening = coordinator.doorbell_talk_state == "listening" or (
            coordinator.doorbell_talk_state == "talking" and inherit_resume
        )
        coordinator._doorbell_reply_resume_listen = was_listening
        coordinator.doorbell_talk_state = "talking"
        coordinator.async_notify_listeners()

        if local_spk and was_listening:
            try:
                await hass.services.async_call(
                    "media_player",
                    "media_stop",
                    {ATTR_ENTITY_ID: local_spk},
                    blocking=False,
                )
            except Exception:  # noqa: BLE001
                pass

        door_spk = target_info["door_speaker"]
        if door_spk:
            mp_st = hass.states.get(door_spk)
            if mp_st is not None:
                cur_vol = mp_st.attributes.get("volume_level")
                if cur_vol is not None and float(cur_vol) < 0.25:
                    try:
                        await hass.services.async_call(
                            "media_player",
                            "volume_set",
                            {ATTR_ENTITY_ID: door_spk, "volume_level": 0.80},
                            blocking=True,
                        )
                    except Exception:  # noqa: BLE001
                        pass

            tts_text = (
                f"... {spoken_text}" if target_info["tts_lead_in"] else spoken_text
            )
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

        coordinator._doorbell_reply_task = (
            coordinator.entry.async_create_background_task(
                hass,
                _post_reply_restore(),
                f"latter_doorbell_reply_{coordinator.device_slug}",
            )
        )
        return target_info

    return target_info


def resolve_doorbell_ring_entities(
    hass: HomeAssistant, camera_entities: list[str]
) -> dict[str, str]:
    """Discover sibling doorbell ring / visitor binary_sensor or event entities for configured cameras."""
    if not camera_entities:
        return {}

    ent_reg = er.async_get(hass)
    ring_to_cam: dict[str, str] = {}

    ring_keywords = (
        "doorbell",
        "visitor",
        "ring",
        "ding",
        "chime_button",
        "button_press",
    )
    exclude_keywords = (
        "motion",
        "person",
        "package",
        "vehicle",
        "animal",
        "pet",
        "light",
        "dark",
        "battery",
        "tamper",
        "wifi",
        "signal",
        "volume",
        "status",
        "chime_duration",
        "chime_type",
    )

    candidate_entries = [
        reg_ent
        for reg_ent in _iter_registry_entities(ent_reg)
        if reg_ent.disabled_by is None and reg_ent.domain in ("binary_sensor", "event")
    ]

    for cam_ent in camera_entities:
        if not cam_ent or not cam_ent.startswith("camera."):
            continue
        cam_entry = ent_reg.async_get(cam_ent)
        cam_dev_id = cam_entry.device_id if cam_entry else None
        if not cam_dev_id:
            continue

        event_matches: list[str] = []
        binary_matches: list[str] = []

        for reg_ent in candidate_entries:
            if reg_ent.device_id != cam_dev_id:
                continue
            domain = reg_ent.domain
            eid_low = reg_ent.entity_id.lower()
            meta_low = " ".join(
                filter(
                    None,
                    [
                        eid_low,
                        str(reg_ent.translation_key or "").lower(),
                        str(reg_ent.original_device_class or "").lower(),
                        str(reg_ent.device_class or "").lower(),
                        str(reg_ent.original_name or "").lower(),
                    ],
                )
            )
            if any(k in meta_low for k in ring_keywords) and not any(
                ex in eid_low for ex in exclude_keywords
            ):
                if domain == "event":
                    event_matches.append(reg_ent.entity_id)
                else:
                    binary_matches.append(reg_ent.entity_id)

        chosen_entities = event_matches if event_matches else binary_matches
        for ent_id in chosen_entities:
            ring_to_cam[ent_id] = cam_ent

    return ring_to_cam


@callback
def bind_coordinator_doorbell_listener(coordinator: Any) -> None:
    """Auto-detect sibling doorbell ring / visitor entities on configured cameras and subscribe."""
    if coordinator._unsub_doorbell_ring_state is not None:
        coordinator._unsub_doorbell_ring_state()
        coordinator._unsub_doorbell_ring_state = None

    if coordinator.is_ble_tag or not coordinator.has_display:
        return

    coordinator._doorbell_ring_map = resolve_doorbell_ring_entities(
        coordinator.hass, coordinator.camera_entities
    )
    if not coordinator._doorbell_ring_map:
        return

    @callback
    def _on_doorbell_ring(event: Event[EventStateChangedData]) -> None:
        entity_id = event.data.get("entity_id")
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if not entity_id or new_state is None or old_state is None:
            return
        if old_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        if new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN, "off"):
            return
        if entity_id.startswith("binary_sensor.") and new_state.state != "on":
            return
        if old_state.state == new_state.state:
            return
        if entity_id.startswith("event."):
            ev_dt = dt_util.parse_datetime(new_state.state)
            if ev_dt is None or abs((dt_util.utcnow() - ev_dt).total_seconds()) > 15.0:
                return

        cam_ent = (
            coordinator._doorbell_ring_map.get(entity_id) or coordinator.camera_entity
        )
        if not cam_ent:
            return

        now_mono = time.monotonic()
        if now_mono < coordinator._doorbell_ring_cooldown_until.get(cam_ent, 0.0):
            return
        coordinator._doorbell_ring_cooldown_until[cam_ent] = now_mono + 15.0

        cam_st = coordinator.hass.states.get(cam_ent)
        cam_friendly = (
            str(cam_st.attributes.get("friendly_name") if cam_st else "")
            or cam_ent.split(".", 1)[-1].replace("_", " ").title()
        )
        title = "Doorbell Ringing"
        message = f"Visitor at {cam_friendly}"

        coordinator.async_dispatch_notification(
            title=title,
            message=message,
            priority="critical",
            duration=20,
            chime=True,
            camera_entity=cam_ent,
        )

        esp_notify_svc = esphome_service(
            coordinator.hass,
            coordinator.esphome_device_id,
            "show_notification",
        )
        if esp_notify_svc:
            coordinator.entry.async_create_background_task(
                coordinator.hass,
                coordinator.hass.services.async_call(
                    "esphome",
                    esp_notify_svc,
                    {
                        "title": title[:48],
                        "message": message[:160],
                        "priority": "critical",
                        "duration": 20,
                        "chime": True,
                        "camera_url": coordinator.alert_camera_url,
                        "alert_id": coordinator.alert_id,
                    },
                    blocking=False,
                ),
                f"latter_doorbell_notify_{coordinator.device_slug}",
            )

    coordinator._unsub_doorbell_ring_state = async_track_state_change_event(
        coordinator.hass,
        list(coordinator._doorbell_ring_map.keys()),
        _on_doorbell_ring,
    )
