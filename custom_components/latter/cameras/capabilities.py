"""Synchronous Protocol v3 camera capability bitmask and Studio metadata resolver (`L2a`, `M-P2-23`)."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ..doorbell_targets import resolve_doorbell_targets
from ..hub_registry import get_area_state_index
from .transcode import (
    CAMERA_CAP_HAS_AUDIO as CAMERA_CAP_HAS_AUDIO,
    CAMERA_CAP_HAS_TALKBACK as CAMERA_CAP_HAS_TALKBACK,
    CAMERA_CAP_IN_CAROUSEL as CAMERA_CAP_IN_CAROUSEL,
    CAMERA_CAP_IS_DOORBELL as CAMERA_CAP_IS_DOORBELL,
    CAMERA_CAP_SHOW_REPLY as CAMERA_CAP_SHOW_REPLY,
    CAMERA_CAP_SHOW_UNLOCK as CAMERA_CAP_SHOW_UNLOCK,
)

# Matches `CameraEntityFeature.STREAM` (bit 1 = 2); avoids eager import of optional `camera`/`stream`.
_CAMERA_FEATURE_STREAM: Final[int] = 2
_MAX_LABEL_LEN: Final[int] = 32
_AUDIO_TRUE_TOKENS: Final[frozenset[str]] = frozenset({"1", "true", "yes", "on"})


def _resolve_platform_and_stream_kind(
    hass: HomeAssistant,
    cam_ent: str,
    target_platform: str,
    attrs: Mapping[str, Any],
    stream_flags: tuple[bool, bool],
) -> str:
    has_stream, has_mjpeg_stream = stream_flags
    platform = target_platform.lower()
    if not platform and cam_ent:
        ent_entry = er.async_get(hass).async_get(cam_ent)
        if ent_entry is not None:
            platform = str(ent_entry.platform or "").lower()
    if has_stream:
        return "rtsp"
    if has_mjpeg_stream or platform == "mjpeg" or bool(attrs.get("mjpeg_url")):
        return "mjpeg"
    return "snapshot"


def _resolve_camera_has_audio(
    attrs: Mapping[str, Any],
    stream_kind: str,
    *,
    is_doorbell: bool,
    has_talkback: bool,
    raw_listen: object,
) -> bool:
    raw_has_audio = attrs.get("has_audio")
    if raw_has_audio is None:
        raw_has_audio = attrs.get("audio")
    if isinstance(raw_has_audio, bool):
        return raw_has_audio
    if raw_has_audio is not None:
        return str(raw_has_audio).strip().lower() in _AUDIO_TRUE_TOKENS
    return bool(
        stream_kind == "rtsp"
        and (is_doorbell or has_talkback or raw_listen is True)
    )


def _compute_camera_caps_bitmask(  # noqa: PLR0913
    *,
    show_listen: bool,
    show_talk: bool,
    is_doorbell: bool,
    in_carousel: bool,
    show_reply: bool,
    unlock_entity: str,
) -> int:
    caps = 0
    if show_listen:
        caps |= CAMERA_CAP_HAS_AUDIO
    if show_talk:
        caps |= CAMERA_CAP_HAS_TALKBACK
    if is_doorbell:
        caps |= CAMERA_CAP_IS_DOORBELL
    if in_carousel:
        caps |= CAMERA_CAP_IN_CAROUSEL
    if show_reply:
        caps |= CAMERA_CAP_SHOW_REPLY
    if unlock_entity:
        caps |= CAMERA_CAP_SHOW_UNLOCK
    return caps


def resolve_camera_capabilities(  # noqa: PLR0913
    hass: HomeAssistant,
    camera_entity_id: str,
    *,
    doorbell_ring_map: Mapping[str, str] | Collection[str] | None = None,
    carousel_entities: Collection[str] | None = None,
    volume_overrides: Mapping[str, str] | None = None,
    camera_config: Mapping[str, Any] | None = None,
    stream_source: str | None = None,
    has_mjpeg_stream: bool = False,
) -> dict[str, Any]:
    """Compute Protocol v3 camera `caps` bitmask and Studio capability metadata synchronously (`M-P2-23`)."""
    cam_ent = (camera_entity_id or "").strip()
    state = hass.states.get(cam_ent) if cam_ent else None
    attrs: Mapping[str, Any] = state.attributes if state is not None else {}

    target_info = resolve_doorbell_targets(hass, cam_ent, volume_overrides)
    door_speaker = str(target_info.get("door_speaker") or "")
    area_id = str(
        target_info.get("area_id")
        or (
            get_area_state_index(hass).resolve_entity_area_id(cam_ent)
            if cam_ent
            else ""
        )
        or ""
    )
    friendly_name = str(
        attrs.get("friendly_name")
        or target_info.get("friendly_name")
        or (cam_ent.split(".", 1)[-1].replace("_", " ").title() if cam_ent else "Camera")
    )

    try:
        supported_features = int(attrs.get("supported_features") or 0)
    except (TypeError, ValueError):
        supported_features = 0
    has_stream = bool(stream_source) or bool(supported_features & _CAMERA_FEATURE_STREAM)
    has_talkback = bool(door_speaker)

    doorbell_cams = (
        set(doorbell_ring_map.values())
        if isinstance(doorbell_ring_map, Mapping)
        else (set(doorbell_ring_map) if doorbell_ring_map is not None else set())
    )
    is_doorbell = bool(cam_ent and cam_ent in doorbell_cams)
    carousel_set = {
        str(e).strip() for e in (carousel_entities or ()) if str(e).strip()
    }
    in_carousel = bool(cam_ent and cam_ent in carousel_set)

    stream_kind = _resolve_platform_and_stream_kind(
        hass,
        cam_ent,
        str(target_info.get("platform") or ""),
        attrs,
        (has_stream, has_mjpeg_stream),
    )

    cfg = camera_config if isinstance(camera_config, Mapping) else {}
    custom_label = str(cfg.get("label") or "").strip()[:_MAX_LABEL_LEN]
    display_name = custom_label or friendly_name

    raw_listen = cfg.get("show_listen")
    has_audio = _resolve_camera_has_audio(
        attrs,
        stream_kind,
        is_doorbell=is_doorbell,
        has_talkback=has_talkback,
        raw_listen=raw_listen,
    )
    show_listen = (
        raw_listen if isinstance(raw_listen, bool) else bool(is_doorbell and has_audio)
    )
    raw_talk = cfg.get("show_talk")
    show_talk = (
        raw_talk if isinstance(raw_talk, bool) else bool(is_doorbell and has_talkback)
    )
    raw_reply = cfg.get("show_reply")
    show_reply = (
        raw_reply if isinstance(raw_reply, bool) else bool(is_doorbell and has_talkback)
    )
    raw_unlock = str(cfg.get("unlock_entity") or "").strip()
    unlock_entity = raw_unlock if raw_unlock.startswith(("lock.", "cover.")) else ""

    caps = _compute_camera_caps_bitmask(
        show_listen=show_listen,
        show_talk=show_talk,
        is_doorbell=is_doorbell,
        in_carousel=in_carousel,
        show_reply=show_reply,
        unlock_entity=unlock_entity,
    )
    return {
        "entity_id": cam_ent,
        "name": display_name,
        "friendly_name": friendly_name,
        "label": custom_label,
        "area_id": area_id,
        "caps": caps,
        "has_audio": has_audio,
        "has_talkback": has_talkback,
        "show_listen": show_listen,
        "show_talk": show_talk,
        "show_reply": show_reply,
        "unlock_entity": unlock_entity,
        "is_doorbell": is_doorbell,
        "in_carousel": in_carousel,
        "stream_kind": stream_kind,
        "door_speaker": door_speaker,
    }
