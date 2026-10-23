"""Service registration for Latter (Universal ESPHome Pagination, Room Control, BLE Area Sync, TV Remote, Trigger Bindings, Calendar, Intercom)."""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall

from .browse_engine import async_browse_media_items
from .calendar_engine import async_fetch_calendar_agenda
from .const import (
    CONF_ALARM_ENTITY,
    DEFAULT_LOCAL_SPEAKER,
    DEFAULT_PAGE_SIZE,
    DOMAIN,
    SERVICE_CALENDAR_CREATE_EVENT,
    SERVICE_CALENDAR_FETCH,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_MEDIA_VOLUME,
    SERVICE_MUSIC_BROWSE,
    SERVICE_REMOTE_ACTION,
    SERVICE_ROOM_ACTION,
    SERVICE_ROOM_BROWSE,
    SERVICE_SET_ACTIVE_AREA,
    SERVICE_SET_ACTIVE_SPEAKER,
    SERVICE_TRIGGER_BINDING,
)
from .coordinator import LatterCoordinator
from .room_engine import (
    async_execute_room_action,
    get_area_entities,
    get_areas_summary,
    get_home_wide_entities,
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


def _resolve_esphome_action(
    hass: HomeAssistant, device_slug: str, suffix: str
) -> str | None:
    """Resolve the registered esphome.<node>_<suffix> service name with smart fallback."""
    esphome_services = hass.services.async_services().get("esphome", {})
    exact = f"{device_slug}_{suffix}"
    if exact in esphome_services:
        return exact

    for svc_name in esphome_services:
        if svc_name.endswith(f"_{suffix}") and device_slug in svc_name:
            return svc_name

    for svc_name in esphome_services:
        if svc_name.endswith(f"_{suffix}"):
            return svc_name

    return None


def _detect_esphome_slot_capacity(
    hass: HomeAssistant, esphome_action: str | None, default_slots: int = 5
) -> int:
    """Inspect the ESPHome service schema to see how many sN_name slots the firmware action accepts (supports 1..20)."""
    if not esphome_action:
        return default_slots
    try:
        esphome_services = hass.services.async_services().get("esphome", {})
        svc_obj = esphome_services.get(esphome_action)
        schema = getattr(svc_obj, "schema", None)
        if schema is not None and hasattr(schema, "schema") and isinstance(schema.schema, dict):
            keys = {str(k) for k in schema.schema}
            max_slot = 0
            for idx in range(1, 21):
                if f"s{idx}_name" in keys:
                    max_slot = idx
            if max_slot > 0:
                return max_slot
    except Exception:  # noqa: BLE001
        pass
    return default_slots


async def async_push_browse_slots(
    hass: HomeAssistant,
    device_slug: str,
    mode: str,
    page: int,
    page_size: int,
    items: list[dict[str, Any]],
    preferred_suffix: str = "set_browse_slots",
) -> None:
    """Paginate items for any GUI page_size (1..20) and push to esphome.<slug>_<suffix>."""
    esphome_action = _resolve_esphome_action(hass, device_slug, preferred_suffix)
    include_levels = preferred_suffix == "set_room_slots" and esphome_action is not None

    if esphome_action is None and preferred_suffix != "set_browse_slots":
        esphome_action = _resolve_esphome_action(
            hass, device_slug, "set_browse_slots"
        )

    slot_capacity = _detect_esphome_slot_capacity(hass, esphome_action, default_slots=5)
    eff_page_size = max(1, min(slot_capacity, int(page_size)))
    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / eff_page_size))
    page = max(1, min(int(page), total_pages))
    start_idx = (page - 1) * eff_page_size
    page_slice = items[start_idx : start_idx + eff_page_size]

    payload: dict[str, Any] = {
        "mode": str(mode),
        "page": int(page),
        "total_pages": int(total_pages),
        "has_prev": bool(page > 1),
        "has_next": bool(page < total_pages),
    }

    for idx in range(1, slot_capacity + 1):
        if idx <= len(page_slice):
            slot = page_slice[idx - 1]
            payload[f"s{idx}_name"] = str(slot.get("name", ""))[:64]
            payload[f"s{idx}_id"] = str(slot.get("id", ""))[:255]
            payload[f"s{idx}_type"] = str(slot.get("type", mode))[:32]
            payload[f"s{idx}_active"] = bool(slot.get("active", False))
            if include_levels:
                payload[f"s{idx}_level"] = int(slot.get("level", -1))
        else:
            payload[f"s{idx}_name"] = ""
            payload[f"s{idx}_id"] = ""
            payload[f"s{idx}_type"] = ""
            payload[f"s{idx}_active"] = False
            if include_levels:
                payload[f"s{idx}_level"] = -1

    if esphome_action is None:
        _LOGGER.warning(
            "No ESPHome service matching *_%s found (target slug '%s'); is the device online?",
            preferred_suffix,
            device_slug,
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

    async def _handle_trigger_binding(call: ServiceCall) -> None:
        """Execute a user-mapped hardware button/sensor trigger slot configured in the Web Companion."""
        data = call.data
        target_device = data.get("target_device")
        coord = _get_primary_coordinator(hass, target_device)
        if not coord:
            return

        slot_key = str(data.get("slot") or "").strip().lower()
        if not slot_key:
            return

        for binding in coord.custom_bindings:
            b_slot = str(binding.get("slot") or "").strip().lower()
            if b_slot == slot_key:
                ent_id = str(binding.get("entity_id") or "").strip()
                action = str(
                    data.get("action") or binding.get("action") or "toggle"
                ).strip()
                raw_lvl = data.get("level")
                lvl = int(raw_lvl) if raw_lvl is not None else None
                if ent_id:
                    await async_execute_room_action(
                        hass, entity_id=ent_id, action=action, level=lvl
                    )
                    coord._notify_listeners()
                return

        _LOGGER.debug(
            "No custom binding found for slot '%s' on device '%s'",
            slot_key,
            coord.device_slug,
        )

    async def _handle_media_volume(call: ServiceCall) -> None:
        """Control volume on the active speaker OR its mapped AVR/number volume override entity."""
        data = call.data
        target_device = data.get("target_device")
        coord = _get_primary_coordinator(hass, target_device)
        speaker = str(
            data.get("speaker")
            or (coord.active_speaker if coord else DEFAULT_LOCAL_SPEAKER)
        )
        vol_target = (
            coord.get_volume_target_entity(speaker) if coord else speaker
        )
        state_obj = hass.states.get(vol_target)
        target_domain = (
            state_obj.domain if state_obj else vol_target.split(".")[0]
        )
        action = str(data.get("action") or "set").strip().lower()

        if target_domain in ("number", "input_number"):
            cur_val = float(state_obj.state) if (state_obj and state_obj.state not in ("unavailable", "unknown")) else 50.0
            min_v = float(state_obj.attributes.get("min", 0.0)) if state_obj else 0.0
            max_v = float(state_obj.attributes.get("max", 100.0)) if state_obj else 100.0
            step = (max_v - min_v) * 0.05

            if action == "up":
                new_val = min(max_v, cur_val + step)
            elif action == "down":
                new_val = max(min_v, cur_val - step)
            elif data.get("volume_level") is not None:
                lvl = float(data["volume_level"])
                if lvl > 1.0:
                    lvl = lvl / 100.0
                new_val = min_v + max(0.0, min(1.0, lvl)) * (max_v - min_v)
            else:
                return

            await hass.services.async_call(
                target_domain,
                "set_value",
                {ATTR_ENTITY_ID: vol_target, "value": round(new_val, 1)},
                blocking=False,
            )
            return

        if action == "up":
            await hass.services.async_call(
                "media_player",
                "volume_up",
                {ATTR_ENTITY_ID: vol_target},
                blocking=False,
            )
        elif action == "down":
            await hass.services.async_call(
                "media_player",
                "volume_down",
                {ATTR_ENTITY_ID: vol_target},
                blocking=False,
            )
        elif action == "mute":
            is_muted = bool(
                state_obj.attributes.get("is_volume_muted", False)
            ) if state_obj else False
            await hass.services.async_call(
                "media_player",
                "volume_mute",
                {ATTR_ENTITY_ID: vol_target, "is_volume_muted": not is_muted},
                blocking=False,
            )
        elif data.get("volume_level") is not None:
            lvl = float(data["volume_level"])
            if lvl > 1.0:
                lvl = lvl / 100.0
            lvl = max(0.0, min(1.0, lvl))
            await hass.services.async_call(
                "media_player",
                "volume_set",
                {ATTR_ENTITY_ID: vol_target, "volume_level": round(lvl, 2)},
                blocking=False,
            )

    async def _handle_set_active_area(call: ServiceCall) -> None:
        """Directly set active room by area_id or room name (from BLE or UI)."""
        data = call.data
        target_device = data.get("target_device")
        coord = _get_primary_coordinator(hass, target_device)
        area_val = str(data.get("area") or data.get("area_id") or "").strip()
        if coord and area_val:
            coord.async_set_active_area(
                area_val,
                handoff_media=data.get("handoff_media"),
                sync_device_registry=True,
            )

    async def _handle_remote_action(call: ServiceCall) -> None:
        """Execute a TV / Media Remote command on one of the 4 configured remote slots."""
        data = call.data
        target_device = data.get("target_device")
        coord = _get_primary_coordinator(hass, target_device)
        if not coord:
            return

        slot_num = int(data.get("slot") or coord.active_remote_slot or 1)
        slot_num = max(1, min(4, slot_num))
        if slot_num != coord.active_remote_slot:
            coord.active_remote_slot = slot_num
            coord._notify_listeners()

        action = str(data.get("action") or "").strip().lower()
        if action in ("select_slot", ""):
            return

        slots = coord.get_remote_slots()
        slot_info = slots[slot_num - 1]
        remote_ent = slot_info["remote_entity"]
        mp_ent = slot_info["media_player_entity"]

        if action == "toggle" and (remote_ent or mp_ent):
            target = remote_ent or mp_ent
            domain = target.split(".")[0]
            await hass.services.async_call(
                domain, "toggle", {ATTR_ENTITY_ID: target}, blocking=False
            )
        elif action in ("volume_up", "volume_down", "volume_mute", "media_play_pause") and mp_ent:
            await hass.services.async_call(
                "media_player", action, {ATTR_ENTITY_ID: mp_ent}, blocking=False
            )
        elif remote_ent and remote_ent.startswith("remote."):
            cmd = str(data.get("command") or action)
            await hass.services.async_call(
                "remote",
                "send_command",
                {ATTR_ENTITY_ID: remote_ent, "command": cmd},
                blocking=False,
            )

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
        configured_ps = coord.default_page_size if coord else DEFAULT_PAGE_SIZE
        default_ps = 5 if mode == "areas" else configured_ps
        page_size = int(data.get("page_size") or default_ps)
        area_id = str(
            data.get("area_id")
            or (coord.active_area_id if coord else "")
            or ""
        )
        domain_filter = str(data.get("domain_filter") or "all")
        handoff_media = data.get("handoff_media")
        local_speaker = coord.local_speaker if coord else DEFAULT_LOCAL_SPEAKER

        if coord and area_id and area_id != coord.active_area_id:
            coord.async_set_active_area(
                area_id, handoff_media=handoff_media, sync_device_registry=False
            )

        if mode == "areas":
            items = get_areas_summary(
                hass,
                active_area_id=coord.active_area_id if coord else area_id,
                local_speaker=local_speaker,
                device_slug=device_slug,
            )
            slot_mode = "room_areas"
        elif mode == "home":
            items = get_home_wide_entities(
                hass,
                configured_alarm_entity=coord.get_opt(CONF_ALARM_ENTITY) if coord else None,
                custom_entities=coord.custom_entities if coord else None,
            )
            slot_mode = "room_home"
        else:
            items = get_area_entities(
                hass,
                area_id=area_id or (coord.active_area_id if coord else None),
                domain_filter=domain_filter,
                custom_entities=coord.custom_entities if coord else None,
                local_speaker=local_speaker,
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
                str(area_id),
                handoff_media=data.get("handoff_media"),
                sync_device_registry=False,
            )

        entity_id = str(data.get("entity_id") or "").strip()
        action = str(data.get("action") or "toggle").strip().lower()
        if not entity_id and coord and action in (
            "arm_home",
            "arm_away",
            "arm_night",
            "arm_vacation",
            "disarm",
        ):
            entity_id = coord.alarm_entity or ""

        if entity_id:
            raw_level = data.get("level")
            level = int(raw_level) if raw_level is not None else None
            code = str(data.get("code")) if data.get("code") is not None else None
            await async_execute_room_action(
                hass,
                entity_id=entity_id,
                action=action,
                level=level,
                code=code,
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
        DOMAIN, SERVICE_TRIGGER_BINDING, _handle_trigger_binding
    )
    hass.services.async_register(
        DOMAIN, SERVICE_MEDIA_VOLUME, _handle_media_volume
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_ACTIVE_AREA, _handle_set_active_area
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REMOTE_ACTION, _handle_remote_action
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