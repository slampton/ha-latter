"""Service registration for Latter (music_browse, set_active_speaker, v2.1 stubs)."""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    DOMAIN,
    SERVICE_MUSIC_BROWSE,
    SERVICE_SET_ACTIVE_SPEAKER,
)
from .coordinator import LatterCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_primary_coordinator(
    hass: HomeAssistant, target_device: str | None = None
) -> LatterCoordinator | None:
    """Resolve the matching LatterCoordinator for a service call."""
    domain_data = hass.data.get(DOMAIN, {})
    coordinators = [
        v for v in domain_data.values() if isinstance(v, LatterCoordinator)
    ]
    if not coordinators:
        return None
    if target_device:
        norm = target_device.strip().lower().replace("-", "_")
        for coord in coordinators:
            if coord.device_slug == norm:
                return coord
    return coordinators[0]


async def async_push_browse_slots(
    hass: HomeAssistant,
    device_slug: str,
    mode: str,
    page: int,
    page_size: int,
    items: list[dict[str, Any]],
) -> None:
    """Paginate items into 5 slots and call esphome.<device_slug>_set_browse_slots."""
    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / page_size))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_slice = items[start_idx : start_idx + 5]

    payload: dict[str, Any] = {
        "mode": str(mode),
        "page": int(page),
        "total_pages": int(total_pages),
        "has_prev": bool(page > 1),
        "has_next": bool(page < total_pages),
    }

    for idx in range(1, 6):
        if idx <= len(page_slice):
            slot = page_slice[idx - 1]
            payload[f"s{idx}_name"] = str(slot.get("name", ""))[:64]
            payload[f"s{idx}_id"] = str(slot.get("id", ""))[:255]
            payload[f"s{idx}_type"] = str(slot.get("type", mode))[:32]
            payload[f"s{idx}_active"] = bool(slot.get("active", False))
        else:
            payload[f"s{idx}_name"] = ""
            payload[f"s{idx}_id"] = ""
            payload[f"s{idx}_type"] = ""
            payload[f"s{idx}_active"] = False

    esphome_action = f"{device_slug}_set_browse_slots"
    if not hass.services.has_service("esphome", esphome_action):
        _LOGGER.warning(
            "ESPHome service esphome.%s not found; is the Pocket Assistant online?",
            esphome_action,
        )
        return

    await hass.services.async_call(
        "esphome", esphome_action, payload, blocking=False
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Latter domain services."""
    if hass.services.has_service(DOMAIN, SERVICE_MUSIC_BROWSE):
        return

    async def _handle_set_active_speaker(call: ServiceCall) -> None:
        speaker = str(call.data.get("entity_id") or call.data.get("speaker") or "")
        target_device = call.data.get("target_device")
        coord = _get_primary_coordinator(hass, target_device)
        if coord and speaker:
            coord.async_set_active_speaker(speaker)

    async def _handle_music_browse(call: ServiceCall) -> None:
        data = call.data
        target_device = str(data.get("target_device") or "pocket-assistant")
        coord = _get_primary_coordinator(hass, target_device)
        device_slug = (
            coord.device_slug
            if coord
            else target_device.strip().lower().replace("-", "_")
        )

        mode = str(data.get("mode") or "speakers")
        page = int(data.get("page") or 1)
        page_size = int(data.get("page_size") or 5)
        speaker = str(
            data.get("speaker")
            or (coord.active_speaker if coord else "media_player.pocket_assistant")
        )

        items: list[dict[str, Any]] = []

        # Built-in Mode 1: Speakers discovery
        if mode == "speakers":
            for state_obj in hass.states.async_all("media_player"):
                if state_obj.state == "unavailable":
                    continue
                friendly = state_obj.attributes.get(
                    "friendly_name", state_obj.entity_id
                )
                items.append(
                    {
                        "name": str(friendly),
                        "id": state_obj.entity_id,
                        "type": "speaker",
                        "active": state_obj.entity_id == speaker,
                    }
                )
            items.sort(key=lambda x: (not x["active"], x["name"].lower()))

        await async_push_browse_slots(
            hass,
            device_slug=device_slug,
            mode=mode,
            page=page,
            page_size=page_size,
            items=items,
        )

    hass.services.async_register(
        DOMAIN, SERVICE_SET_ACTIVE_SPEAKER, _handle_set_active_speaker
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MUSIC_BROWSE, _handle_music_browse
    )