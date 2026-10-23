"""Service registration for Latter (Music, Room Control, Calendar, and Intercom)."""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall

from .browse_engine import async_browse_media_items
from .calendar_engine import async_fetch_calendar_agenda
from .const import (
    DEFAULT_LOCAL_SPEAKER,
    DOMAIN,
    SERVICE_CALENDAR_CREATE_EVENT,
    SERVICE_CALENDAR_FETCH,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_MUSIC_BROWSE,
    SERVICE_ROOM_ACTION,
    SERVICE_ROOM_BROWSE,
    SERVICE_SET_ACTIVE_SPEAKER,
)
from .coordinator import LatterCoordinator
from .room_engine import (
    async_execute_room_action,
    get_area_entities,
    get_areas_summary,
)

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
    preferred_suffix: str = "set_browse_slots",
) -> None:
    """Paginate items into 5 slots and call esphome.<device_slug>_<preferred_suffix>."""
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

    include_levels = preferred_suffix == "set_room_slots" and hass.services.has_service(
        "esphome", f"{device_slug}_set_room_slots"
    )

    for idx in range(1, 6):
        if idx <= len(page_slice):
            slot = page_slice[idx - 1]
            payload[f"s{idx}_name"] = str(slot.get("name", ""))[:64]
            payload[f"s{idx}_id"] = str(slot.get("id", ""))[:255]
            payload[f"s{idx}_type"] = str(slot.get("type", mode))[:32]
            payload[f"s{idx}_active"] = bool(slot.get("active", False))
            if include_levels:
                payload[f"s{idx}_level"] = int(slot.get("level", 0))
        else:
            payload[f"s{idx}_name"] = ""
            payload[f"s{idx}_id"] = ""
            payload[f"s{idx}_type"] = ""
            payload[f"s{idx}_active"] = False
            if include_levels:
                payload[f"s{idx}_level"] = 0

    esphome_action = f"{device_slug}_{preferred_suffix}"
    if not hass.services.has_service("esphome", esphome_action):
        esphome_action = f"{device_slug}_set_browse_slots"

    if not hass.services.has_service("esphome", esphome_action):
        _LOGGER.warning(
            "ESPHome service esphome.%s not found; is the ESPHome device online?",
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
            or (coord.active_speaker if coord else DEFAULT_LOCAL_SPEAKER)
        )
        last_speaker = str(
            data.get("last_speaker")
            or (coord.last_speaker if coord else speaker)
        )
        local_speaker = (
            coord.local_speaker if coord else DEFAULT_LOCAL_SPEAKER
        )
        search = str(data.get("search") or "")
        album_sort = str(data.get("album_sort") or "name")
        artist_album_sort = str(data.get("artist_album_sort") or "year")
        podcast_sort = str(data.get("podcast_sort") or "newest")

        if coord and speaker and speaker != coord.active_speaker:
            coord.async_set_active_speaker(speaker)

        items = await async_browse_media_items(
            hass=hass,
            mode=mode,
            speaker=speaker,
            last_speaker=last_speaker,
            local_speaker=local_speaker,
            search=search,
            album_sort=album_sort,
            artist_album_sort=artist_album_sort,
            podcast_sort=podcast_sort,
        )

        await async_push_browse_slots(
            hass=hass,
            device_slug=device_slug,
            mode=mode,
            page=page,
            page_size=page_size,
            items=items,
        )

    async def _handle_room_browse(call: ServiceCall) -> None:
        data = call.data
        target_device = str(data.get("target_device") or "pocket-assistant")
        coord = _get_primary_coordinator(hass, target_device)
        device_slug = (
            coord.device_slug
            if coord
            else target_device.strip().lower().replace("-", "_")
        )

        mode = str(data.get("mode") or "entities").strip().lower()
        page = int(data.get("page") or 1)
        page_size = int(data.get("page_size") or 5)
        area_id = str(
            data.get("area_id")
            or (coord.active_area_id if coord else "")
            or ""
        )
        domain_filter = str(data.get("domain_filter") or "all")
        handoff_media = data.get("handoff_media")

        if coord and area_id and area_id != coord.active_area_id:
            coord.async_set_active_area(area_id, handoff_media=handoff_media)

        if mode == "areas":
            items = get_areas_summary(
                hass, active_area_id=coord.active_area_id if coord else area_id
            )
            slot_mode = "room_areas"
        else:
            items = get_area_entities(
                hass,
                area_id=area_id or (coord.active_area_id if coord else None),
                domain_filter=domain_filter,
                custom_entities=coord.custom_entities if coord else None,
            )
            slot_mode = f"room_{domain_filter}"

        await async_push_browse_slots(
            hass=hass,
            device_slug=device_slug,
            mode=slot_mode,
            page=page,
            page_size=page_size,
            items=items,
            preferred_suffix="set_room_slots",
        )

    async def _handle_room_action(call: ServiceCall) -> None:
        data = call.data
        target_device = str(data.get("target_device") or "pocket-assistant")
        coord = _get_primary_coordinator(hass, target_device)

        area_id = data.get("area_id")
        if coord and area_id:
            coord.async_set_active_area(
                str(area_id), handoff_media=data.get("handoff_media")
            )

        entity_id = str(data.get("entity_id") or "").strip()
        if entity_id:
            action = str(data.get("action") or "toggle")
            raw_level = data.get("level")
            level = int(raw_level) if raw_level is not None else None
            await async_execute_room_action(
                hass, entity_id=entity_id, action=action, level=level
            )
            if coord:
                coord._notify_listeners()

    async def _handle_calendar_fetch(call: ServiceCall) -> None:
        data = call.data
        target_device = str(data.get("target_device") or "pocket-assistant")
        coord = _get_primary_coordinator(hass, target_device)
        device_slug = (
            coord.device_slug
            if coord
            else target_device.strip().lower().replace("-", "_")
        )

        days = int(data.get("days") or 7)
        page = int(data.get("page") or 1)
        page_size = int(data.get("page_size") or 5)

        if coord:
            await coord.async_refresh_calendar_agenda()
            items = coord.calendar_events
        else:
            _, items = await async_fetch_calendar_agenda(hass, [], days=days)

        await async_push_browse_slots(
            hass=hass,
            device_slug=device_slug,
            mode="calendar_agenda",
            page=page,
            page_size=page_size,
            items=items,
        )

    async def _handle_calendar_create_event(call: ServiceCall) -> None:
        data = call.data
        target_device = str(data.get("target_device") or "pocket-assistant")
        coord = _get_primary_coordinator(hass, target_device)

        cal_entity = str(data.get("calendar_entity") or "").strip()
        if not cal_entity and coord and coord.calendar_entities:
            cal_entity = coord.calendar_entities[0]
        if not cal_entity:
            states = hass.states.async_all("calendar")
            if states:
                cal_entity = states[0].entity_id

        if not cal_entity or not hass.services.has_service("calendar", "create_event"):
            _LOGGER.warning("No writable calendar entity found for calendar_create_event.")
            return

        payload: dict[str, Any] = {
            ATTR_ENTITY_ID: cal_entity,
            "summary": str(data.get("summary") or "Reminder"),
            "start_date_time": str(data.get("start_date_time") or ""),
            "end_date_time": str(data.get("end_date_time") or ""),
        }
        if data.get("description"):
            payload["description"] = str(data["description"])

        await hass.services.async_call(
            "calendar", "create_event", payload, blocking=True
        )
        if coord:
            await coord.async_refresh_calendar_agenda()

    async def _handle_intercom_broadcast(call: ServiceCall) -> None:
        data = call.data
        message = str(data.get("message") or "").strip()
        media_url = str(data.get("media_url") or "").strip()
        target_speakers = data.get("target_speakers")
        tts_entity = str(data.get("tts_entity") or "").strip()

        if isinstance(target_speakers, str):
            speakers = [target_speakers]
        elif isinstance(target_speakers, list) and target_speakers:
            speakers = [str(s) for s in target_speakers]
        else:
            speakers = [
                s.entity_id
                for s in hass.states.async_all("media_player")
                if s.state not in ("unavailable", "unknown")
            ]

        if not speakers:
            return

        if media_url:
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    ATTR_ENTITY_ID: speakers,
                    "media_content_id": media_url,
                    "media_content_type": "music",
                    "announce": True,
                },
                blocking=False,
            )
            return

        if message:
            if not tts_entity:
                tts_states = hass.states.async_all("tts")
                if tts_states:
                    tts_entity = tts_states[0].entity_id

            if tts_entity and hass.services.has_service("tts", "speak"):
                await hass.services.async_call(
                    "tts",
                    "speak",
                    {
                        ATTR_ENTITY_ID: tts_entity,
                        "media_player_entity_id": speakers,
                        "message": message,
                        "cache": False,
                    },
                    blocking=False,
                )
            elif hass.services.has_service("tts", "cloud_say"):
                await hass.services.async_call(
                    "tts",
                    "cloud_say",
                    {ATTR_ENTITY_ID: speakers, "message": message},
                    blocking=False,
                )

    hass.services.async_register(
        DOMAIN, SERVICE_SET_ACTIVE_SPEAKER, _handle_set_active_speaker
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MUSIC_BROWSE, _handle_music_browse
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ROOM_BROWSE, _handle_room_browse
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ROOM_ACTION, _handle_room_action
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CALENDAR_FETCH, _handle_calendar_fetch
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CALENDAR_CREATE_EVENT, _handle_calendar_create_event
    )
    hass.services.async_register(
        DOMAIN, SERVICE_INTERCOM_BROADCAST, _handle_intercom_broadcast
    )