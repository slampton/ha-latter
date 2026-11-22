"""Bound sibling doorbell speaker and ring-entity resolvers (`L1b`)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .hub_registry import get_area_state_index

_RING_KEYWORDS: Final[tuple[str, ...]] = (
    "doorbell",
    "visitor",
    "ring",
    "ding",
    "chime_button",
    "button_press",
)

_EXCLUDE_KEYWORDS: Final[tuple[str, ...]] = (
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


def resolve_doorbell_targets(
    hass: HomeAssistant,
    camera_entity_id: str | None,
    volume_overrides: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve the door speaker `media_player` for a camera strictly by explicit override or exact `device_id`."""
    info: dict[str, Any] = {
        "camera_entity": "",
        "friendly_name": "Camera",
        "door_speaker": "",
        "platform": "",
        "tts_lead_in": False,
        "area_id": "",
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
        if cam_entry.device_id and not info["door_speaker"]:
            for sib in er.async_entries_for_device(ent_reg, cam_entry.device_id):
                if not sib.disabled_by and sib.domain == "media_player":
                    info["door_speaker"] = sib.entity_id
                    break

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


def _entry_matches_ring_sensor(reg_ent: er.RegistryEntry) -> bool:
    if reg_ent.disabled_by is not None or reg_ent.domain not in (
        "binary_sensor",
        "event",
    ):
        return False
    meta_low = " ".join(
        filter(
            None,
            [
                reg_ent.entity_id.lower(),
                str(reg_ent.translation_key or "").lower(),
                str(reg_ent.original_device_class or "").lower(),
                str(reg_ent.device_class or "").lower(),
                str(reg_ent.original_name or "").lower(),
            ],
        )
    )
    return any(k in meta_low for k in _RING_KEYWORDS) and not any(
        ex in meta_low for ex in _EXCLUDE_KEYWORDS
    )


def resolve_doorbell_ring_entities(
    hass: HomeAssistant, camera_entities: list[str]
) -> dict[str, str]:
    """Discover sibling doorbell ring / visitor `binary_sensor` or `event` entities for configured cameras."""
    if not camera_entities:
        return {}

    ent_reg = er.async_get(hass)
    ring_to_cam: dict[str, str] = {}
    for cam_ent in camera_entities:
        if not cam_ent or not cam_ent.startswith("camera."):
            continue
        cam_entry = ent_reg.async_get(cam_ent)
        cam_dev_id = cam_entry.device_id if cam_entry else None
        if not cam_dev_id:
            continue

        event_matches: list[str] = []
        binary_matches: list[str] = []
        for reg_ent in er.async_entries_for_device(ent_reg, cam_dev_id):
            if not _entry_matches_ring_sensor(reg_ent):
                continue
            if reg_ent.domain == "event":
                event_matches.append(reg_ent.entity_id)
            else:
                binary_matches.append(reg_ent.entity_id)

        for ent_id in event_matches or binary_matches:
            ring_to_cam[ent_id] = cam_ent

    return ring_to_cam
