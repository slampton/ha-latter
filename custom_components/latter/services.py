"""Latter service actions: device handshake, music and Area browsing, Area and media control, remotes, calendar, notifications, intercom and doorbell."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import math
import re
import time
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    Context,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .areas import (
    async_execute_area_action,
    get_area_available_domains,
    get_area_entities,
    get_areas_summary,
    get_home_wide_entities,
    get_whole_home_summary,
    resolve_person_area_and_distance,
)
from .const import (
    CONF_ALARM_ENTITY,
    CONF_CUSTOM_PALETTES,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DOCK_APPS,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    DOORBELL_NOISE_REDUCTION_LEVELS,
    SERVICE_AREA_ACTION,
    SERVICE_AREA_BROWSE,
    SERVICE_CALENDAR_CREATE_EVENT,
    SERVICE_CALENDAR_FETCH,
    SERVICE_DEVICE_HELLO,
    SERVICE_DOORBELL_INTERCOM,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_MEDIA_COMMAND,
    SERVICE_MEDIA_VOLUME,
    SERVICE_MUSIC_BROWSE,
    SERVICE_NOTIFY,
    SERVICE_REMOTE_ACTION,
    SERVICE_RESET_DEVICE,
    SERVICE_SAVE_CUSTOM_COLOR,
    SERVICE_SET_ACTIVE_AREA,
    SERVICE_SET_ACTIVE_SPEAKER,
    SERVICE_SET_DEVICE_PREFS,
    SERVICE_SET_DOCK_APPS,
    SERVICE_TIMER_ALARM_STATE,
    target_kind,
)
from .coordinator import LatterCoordinator, resolve_coordinator
from .doorbell import async_execute_doorbell_intercom
from .feeds import async_fetch_calendar_snapshot
from .groups import async_reset_device
from .hub import (
    async_save_and_broadcast_global_config,
    get_area_state_index,
    get_latter_system,
    iter_coordinators,
)
from .identity import device_entities, esphome_service
from .media import (
    async_announce_on_targets,
    async_execute_volume_action,
    resolve_assist_satellite_entity,
)
from .media_browse import async_browse_media_items, is_music_assistant_player
from .presence import get_ble_fabric
from .protocol import (
    check_perimeter_action_allowed,
    is_sensitive_perimeter_action,
    normalize_dock_apps,
)
from .remotes import async_execute_remote_action
from .repairs import slot_push_failing_issue_id

_LOGGER = logging.getLogger(__name__)

BASE_TARGET_FIELDS: dict[Any, Any] = {
    vol.Optional("target_device"): cv.string,
}


def _parse_bool(val: Any, default: bool = False) -> bool:
    """Safely parse booleans or YAML string booleans ('true', 'false', '1', '0') from ESPHome service calls."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in ("true", "1", "yes", "on"):
        return True
    if s in ("false", "0", "no", "off", ""):
        return False
    return default


def _resolve_coordinator_from_call(
    hass: HomeAssistant, call: ServiceCall
) -> LatterCoordinator:
    """Resolve the target LatterCoordinator strictly by target_device (or single-device default), raising ServiceValidationError on ambiguity."""
    raw_target = call.data.get("target_device")
    target_str = str(raw_target).strip() if raw_target is not None else ""
    coord = resolve_coordinator(hass, target_str or None)
    if coord is None:
        raise ServiceValidationError(
            f"Target Latter device '{target_str or 'unspecified'}' could not be resolved.",
            translation_domain=DOMAIN,
            translation_key="unknown_target",
            translation_placeholders={
                "target_device": target_str or "unspecified"
            },
        )
    return coord


async def _require_admin_if_user_call(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Reject non-admin Home Assistant user invocations of configuration-mutating services."""
    user_id = call.context.user_id if call.context else None
    if not user_id:
        return
    user = await hass.auth.async_get_user(user_id)
    if user is not None and not user.is_admin:
        raise Unauthorized(context=call.context, user_id=user_id, permission="admin")


def _enforce_perimeter_security_policy(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    entity_id: str,
    action: str,
    *,
    level: int | None = None,
    provided_code: str | None = None,
) -> None:
    """Enforce the Device's Perimeter Security Policy on sensitive opening actions."""
    resolved_ent = entity_id.strip()
    if resolved_ent == "whole_home.lock":
        resolved_ent = coord.lock_entity or get_whole_home_summary(
            hass, lock_entity=coord.lock_entity
        )["lock_entity"]
    elif resolved_ent == "whole_home.garage":
        resolved_ent = coord.garage_entity or get_whole_home_summary(
            hass, garage_entity=coord.garage_entity
        )["garage_entity"]
    elif resolved_ent == "whole_home.alarm":
        resolved_ent = coord.alarm_entity or ""
    if not resolved_ent or "." not in resolved_ent:
        return

    dom = resolved_ent.split(".", 1)[0].lower()
    st = hass.states.get(resolved_ent)
    dclass = str(st.attributes.get("device_class") or "") if st is not None else ""
    if not is_sensitive_perimeter_action(
        dom,
        action,
        device_class=dclass,
        entity_id=resolved_ent,
        level=level,
    ):
        return

    stored_hash = coord.security_pin_hash or None
    alarm_passthrough = dom == "alarm_control_panel" and not stored_hash
    allowed, err_key = check_perimeter_action_allowed(
        coord.security_pin_policy,
        provided_code=provided_code,
        stored_pin_hash=stored_hash,
        alarm_accepts_passthrough_code=alarm_passthrough,
    )
    if not allowed:
        raise ServiceValidationError(
            f"Perimeter action '{action}' on '{resolved_ent}' denied ({err_key}).",
            translation_domain=DOMAIN,
            translation_key=err_key,
        )


_SLOT_PUSH_WARN_INTERVAL_S = 600.0
_SLOT_PUSH_REPAIR_THRESHOLD = 5


async def async_push_browse_slots(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    mode: str,
    page: int,
    page_size: int,
    items: list[dict[str, Any]],
    preferred_suffix: str = "set_browse_slots",
    req_id: int = 0,
) -> None:
    """Paginate items and push them to the Device's bound esphome.<node>_<suffix> action (Protocol v3 packed slots)."""
    device_slug = coord.device_slug
    esphome_action = esphome_service(hass, coord.esphome_device_id, preferred_suffix)
    include_levels = preferred_suffix == "set_area_slots" and esphome_action is not None

    if esphome_action is None and preferred_suffix != "set_browse_slots":
        esphome_action = esphome_service(
            hass, coord.esphome_device_id, "set_browse_slots"
        )

    slot_capacity = coord.card_slot_capacity if include_levels else coord.list_slot_capacity
    eff_page_size = max(1, min(slot_capacity, int(page_size)))
    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / eff_page_size))
    page = max(1, min(int(page), total_pages))
    start_idx = (page - 1) * eff_page_size
    page_slice = items[start_idx : start_idx + eff_page_size]

    packed_rows: list[str] = []
    for slot in page_slice:
        s_name = str(slot.get("name", ""))[:64].replace("\x1f", " ").replace("\x1e", " ")
        s_id = str(slot.get("id", ""))[:255].replace("\x1f", " ").replace("\x1e", " ")
        s_type = str(slot.get("type", mode))[:32].replace("\x1f", " ").replace("\x1e", " ")
        s_act = 1 if bool(slot.get("active", False)) else 0
        s_lvl = int(slot.get("level", -1)) if include_levels else -1
        packed_rows.append(f"{s_name}\x1f{s_id}\x1f{s_type}\x1f{s_act}\x1f{s_lvl}")

    payload: dict[str, Any] = {
        "contract": 3,
        "req_id": max(0, int(req_id)),
        "mode": str(mode),
        "page": int(page),
        "total_pages": int(total_pages),
        "slots": "\x1e".join(packed_rows),
    }

    if esphome_action is None:
        _LOGGER.debug(
            "No ESPHome service matching *_%s found (target slug '%s'); device is headless or offline.",
            preferred_suffix,
            device_slug,
        )
        return

    domain_data = hass.data.setdefault(DOMAIN, {})
    fail_counts: dict[str, int] = domain_data.setdefault("_slot_push_failures", {})
    last_warn_ts: dict[str, float] = domain_data.setdefault("_slot_push_last_warn", {})
    fail_key = coord.subentry_id
    issue_id = slot_push_failing_issue_id(fail_key)

    try:
        await hass.services.async_call(
            "esphome", esphome_action, payload, blocking=True
        )
        if fail_counts.pop(fail_key, 0) >= _SLOT_PUSH_REPAIR_THRESHOLD:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
    except Exception as err:  # noqa: BLE001
        count = fail_counts.get(fail_key, 0) + 1
        fail_counts[fail_key] = count
        now_m = time.monotonic()
        if now_m - last_warn_ts.get(fail_key, -_SLOT_PUSH_WARN_INTERVAL_S) >= _SLOT_PUSH_WARN_INTERVAL_S:
            last_warn_ts[fail_key] = now_m
            _LOGGER.warning(
                "Failed to push %s slots to '%s' (consecutive failures=%d): %s",
                esphome_action,
                device_slug,
                count,
                err,
            )
        if count >= _SLOT_PUSH_REPAIR_THRESHOLD:
            placeholders = {
                "device_slug": device_slug,
                "service_name": f"esphome.{esphome_action}",
                "error": str(err)[:160],
            }
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="slot_push_failing",
                translation_placeholders=placeholders,
                config_entry_id=coord.entry.entry_id,
            )


def _is_esphome_device_online(hass: HomeAssistant, coord: LatterCoordinator) -> bool:
    """Return True if the target ESPHome device supports slot callbacks and has an online entity."""
    if (
        esphome_service(hass, coord.esphome_device_id, "set_area_slots") is None
        and esphome_service(hass, coord.esphome_device_id, "set_browse_slots") is None
    ):
        return False
    local_spk = coord.local_speaker
    if local_spk:
        st = hass.states.get(local_spk)
        if st is not None:
            return st.state not in ("unavailable", "unknown")
    esp_dev_id = coord.esphome_device_id
    if esp_dev_id:
        for entry in device_entities(hass, esp_dev_id):
            if entry.platform == "esphome":
                st = hass.states.get(entry.entity_id)
                if st is not None and st.state not in ("unavailable", "unknown"):
                    return True
    return False


def _resolve_occupied_area_ids(
    hass: HomeAssistant, kind: str, target_low: str
) -> set[str]:
    """Return the set of occupied area_ids for 'occupied_areas' or a 'person.*' target."""
    fabric = get_ble_fabric(hass)
    area_reg = ar.async_get(hass)
    occupied_areas: set[str] = set()
    if kind == "person":
        _, p_attrs = resolve_person_area_and_distance(hass, target_low)
        if p_attrs.get("is_home") and p_attrs.get("area_id"):
            occupied_areas.add(str(p_attrs["area_id"]))
        for area_entry in area_reg.async_list_areas():
            occ_persons = [
                str(p).lower()
                for p in (
                    fabric.get_area_occupancy(area_entry.id).get("persons")
                    or []
                )
            ]
            if target_low in occ_persons:
                occupied_areas.add(area_entry.id)
    else:
        for c in iter_coordinators(hass):
            if (
                c.active_area_id
                and fabric.get_area_occupancy(c.active_area_id).get("is_occupied")
            ):
                occupied_areas.add(c.active_area_id)
        for area_entry in area_reg.async_list_areas():
            if fabric.get_area_occupancy(area_entry.id).get("is_occupied"):
                occupied_areas.add(area_entry.id)
    return occupied_areas


async def async_push_active_area_entities(
    hass: HomeAssistant, coord: LatterCoordinator
) -> None:
    """Push the active area's entity slots to esphome.<slug>_set_area_slots when the device is online."""
    if not _is_esphome_device_online(hass, coord):
        return
    avail = get_area_available_domains(
        hass,
        area_id=coord.active_area_id,
        local_speaker=coord.local_speaker,
        area_categories=coord.area_categories_csv,
    )
    avail_tokens = [t for t in avail.split(",") if t]
    eff_filter = coord.last_area_filter
    if not eff_filter or eff_filter not in avail_tokens:
        eff_filter = avail_tokens[0] if avail_tokens else ""
        coord.last_area_filter = eff_filter
    items = (
        get_area_entities(
            hass,
            area_id=coord.active_area_id,
            domain_filter=eff_filter,
            local_speaker=coord.local_speaker,
        )
        if eff_filter
        else []
    )
    await async_push_browse_slots(
        hass=hass,
        coord=coord,
        mode=f"area_{eff_filter or 'empty'}",
        page=coord.last_area_page or 1,
        page_size=coord.card_slot_capacity,
        items=items,
        preferred_suffix="set_area_slots",
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Latter domain services with Voluptuous schema validation."""
    if hass.services.has_service(DOMAIN, SERVICE_MUSIC_BROWSE):
        return

    async def _handle_device_hello(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        contract = int(call.data.get("contract") or 3)
        boot_id = str(call.data.get("boot_id") or "").strip()
        manifest_raw = str(call.data.get("manifest") or "").strip()
        prefs_seq = int(call.data.get("prefs_seq") or 0)
        dirty_prefs = str(call.data.get("dirty_prefs") or "")
        await coord.async_handle_device_hello(
            contract=contract,
            boot_id=boot_id,
            manifest_raw=manifest_raw,
            prefs_seq=prefs_seq,
            dirty_prefs=dirty_prefs,
        )

    async def _handle_set_active_speaker(call: ServiceCall) -> None:
        speaker = str(call.data.get("entity_id") or "").strip()
        transfer_queue = _parse_bool(call.data.get("transfer_queue"), default=True)
        coord = _resolve_coordinator_from_call(hass, call)
        if speaker:
            coord.async_set_active_speaker(speaker, transfer_queue=transfer_queue)

    async def _handle_media_command(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data
        command = str(data.get("command") or "toggle")
        speaker = data.get("entity_id")
        raw_seek = data.get("seek_position")
        seek_pos = float(raw_seek) if raw_seek is not None and str(raw_seek).strip() != "" else None
        media_id = str(data.get("media_id") or "").strip() or None
        media_type = str(data.get("media_type") or "").strip() or None
        enqueue = str(data.get("enqueue") or "").strip() or None
        group_members = data.get("group_members")

        await coord.async_execute_media_command(
            command=command,
            speaker=str(speaker) if speaker else None,
            seek_position=seek_pos,
            media_id=media_id,
            media_type=media_type,
            enqueue=enqueue,
            group_members=group_members,
        )

    async def _handle_media_volume(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data
        speaker = str(data.get("entity_id") or coord.active_speaker).strip()
        if not speaker:
            return

        vol_target = coord.get_volume_target_entity(speaker)
        action = str(data.get("action") or "set").strip().lower()

        raw_lvl = data.get("volume_level")
        parsed_lvl: float | None = None
        if raw_lvl is not None and str(raw_lvl).strip() != "":
            try:
                parsed_lvl = float(str(raw_lvl).strip())
            except ValueError:
                parsed_lvl = None

        await async_execute_volume_action(hass, vol_target, action, parsed_lvl)

    async def _handle_set_active_area(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        area_val = str(call.data.get("area_id") or "").strip()
        if area_val:
            coord.async_set_active_area(area_val, sync_device_registry=True)

    async def _handle_remote_action(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        raw_slot = call.data.get("slot")
        slot_val = int(raw_slot) if raw_slot is not None else None
        await async_execute_remote_action(
            hass,
            coord,
            slot=slot_val,
            action=str(call.data.get("action") or ""),
            command=call.data.get("command"),
        )

    async def _handle_music_browse(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data

        req_id = int(data.get("req_id") or 0)
        mode = str(data.get("mode") or "speakers")
        page = int(data.get("page") or 1)
        page_size = int(data.get("page_size") or coord.list_slot_capacity)
        local_speaker = coord.local_speaker
        speaker = str(data.get("speaker") or coord.active_speaker or local_speaker)
        last_speaker = str(data.get("last_speaker") or coord.last_speaker or speaker)
        search = str(data.get("search") or "")
        album_sort = str(data.get("album_sort") or "name")
        artist_album_sort = str(data.get("artist_album_sort") or "year")
        podcast_sort = str(data.get("podcast_sort") or "newest")

        items = await async_browse_media_items(
            hass=hass,
            mode=mode,
            speaker=speaker,
            last_speaker=last_speaker,
            local_speaker=local_speaker,
            search=search,
            default_speaker=str(coord.get_opt(CONF_DEFAULT_SPEAKER) or ""),
            album_sort=album_sort,
            artist_album_sort=artist_album_sort,
            podcast_sort=podcast_sort,
        )
        if not items and mode != "speakers":
            items = [
                {
                    "name": "No items found",
                    "id": "",
                    "type": "text",
                    "active": False,
                }
            ]

        await async_push_browse_slots(
            hass=hass,
            coord=coord,
            mode=mode,
            page=page,
            page_size=page_size,
            items=items,
            preferred_suffix="set_browse_slots",
            req_id=req_id,
        )

    async def _handle_area_browse(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data

        req_id = int(data.get("req_id") or 0)
        mode = str(data.get("mode") or "entities").strip().lower()
        page = int(data.get("page") or 1)
        default_ps = coord.list_slot_capacity if mode == "areas" else coord.card_slot_capacity
        page_size = int(data.get("page_size") or default_ps)
        area_id = str(data.get("area_id") or coord.active_area_id or "")
        domain_filter = str(data.get("domain_filter") or "").strip()
        local_speaker = coord.local_speaker

        if area_id and area_id != coord.active_area_id:
            coord.async_set_active_area(
                area_id, handoff_media=False, sync_device_registry=False
            )

        eff_area_id = area_id or coord.active_area_id
        if mode == "entities" and not domain_filter:
            avail = get_area_available_domains(
                hass,
                area_id=eff_area_id,
                local_speaker=local_speaker,
                area_categories=coord.area_categories_csv,
            )
            avail_tokens = [t for t in avail.split(",") if t]
            domain_filter = avail_tokens[0] if avail_tokens else ""

        if mode == "entities":
            coord.last_area_filter = domain_filter
            coord.last_area_page = page

        if mode == "areas":
            items = get_areas_summary(
                hass,
                active_area_id=coord.active_area_id,
                local_speaker=local_speaker,
            )
            slot_mode = "area_areas"
        elif mode == "home":
            items = get_home_wide_entities(
                hass,
                configured_alarm_entity=coord.get_opt(CONF_ALARM_ENTITY),
            )
            slot_mode = "area_home"
        elif not domain_filter:
            items = []
            slot_mode = "area_empty"
        else:
            items = get_area_entities(
                hass,
                area_id=eff_area_id,
                domain_filter=domain_filter,
                local_speaker=local_speaker,
            )
            slot_mode = f"area_{domain_filter}"

        target_suffix = "set_browse_slots" if mode == "areas" else "set_area_slots"
        await async_push_browse_slots(
            hass=hass,
            coord=coord,
            mode=slot_mode,
            page=page,
            page_size=page_size,
            items=items,
            preferred_suffix=target_suffix,
            req_id=req_id,
        )

    async def _handle_area_action(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data

        area_id = data.get("area_id")
        if area_id and str(area_id) != coord.active_area_id:
            coord.async_set_active_area(
                str(area_id),
                handoff_media=False,
                sync_device_registry=False,
            )

        entity_id = str(data.get("entity_id") or "").strip()
        action = str(data.get("action") or "").strip().lower()
        if not entity_id and action in (
            "arm_home",
            "arm_away",
            "arm_night",
            "disarm",
        ):
            entity_id = coord.alarm_entity or ""

        if entity_id:
            raw_level = data.get("level")
            level = int(float(raw_level)) if raw_level is not None and str(raw_level).strip() != "" else None
            code = str(data.get("code")) if data.get("code") is not None else None
            _enforce_perimeter_security_policy(
                hass,
                coord,
                entity_id,
                action,
                level=level,
                provided_code=code,
            )
            await async_execute_area_action(
                hass,
                entity_id=entity_id,
                action=action,
                level=level,
                code=code,
            )
            await asyncio.sleep(0.15)
            if coord._unsub_area_debounce is not None:
                coord._unsub_area_debounce()
                coord._unsub_area_debounce = None
            coord.async_notify_listeners()
            await async_push_active_area_entities(hass, coord)

    async def _handle_calendar_fetch(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data

        req_id = int(data.get("req_id") or 0)
        days = int(data.get("days") or 30)
        page = int(data.get("page") or 1)
        page_size = int(data.get("page_size") or coord.list_slot_capacity)

        if days == 30:
            sys_obj = get_latter_system(hass)
            if page > 1 and coord.calendar_events:
                items = coord.calendar_events
            elif sys_obj is not None:
                await sys_obj.async_refresh_calendar_agenda(
                    days=30, coalesce=(page > 1)
                )
                items = coord.calendar_events
            else:
                await coord.async_refresh_calendar_agenda(days=30)
                items = coord.calendar_events
        else:
            _, items = await async_fetch_calendar_snapshot(
                hass,
                coord.calendar_entities,
                days=days,
                map_url_builder=coord.build_map_snapshot_url,
            )

        await async_push_browse_slots(
            hass=hass,
            coord=coord,
            mode="calendar_agenda",
            page=page,
            page_size=page_size,
            items=items,
            req_id=req_id,
        )

    async def _handle_calendar_create_event(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data

        cal_entity = str(data.get("calendar_entity") or "").strip()
        if not cal_entity and coord.calendar_entities:
            cal_entity = coord.calendar_entities[0]
        if not cal_entity:
            states = sorted(
                get_area_state_index(hass).states_for_domain("calendar"),
                key=lambda s: s.entity_id,
            )
            if states:
                cal_entity = states[0].entity_id

        if not cal_entity or not hass.services.has_service("calendar", "create_event"):
            _LOGGER.warning("No writable calendar entity found for calendar_create_event.")
            return

        start_str = str(data.get("start_date_time") or "").strip()
        end_str = str(data.get("end_date_time") or "").strip()
        if not start_str or not end_str:
            in_mins = max(1, int(float(data.get("in_minutes") or 15)))
            dur_mins = max(5, int(float(data.get("duration_minutes") or 30)))
            now_local = dt_util.now().replace(second=0, microsecond=0)
            start_dt = now_local + timedelta(minutes=in_mins)
            end_dt = start_dt + timedelta(minutes=dur_mins)
            start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
            end_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")

        payload: dict[str, Any] = {
            ATTR_ENTITY_ID: cal_entity,
            "summary": str(data.get("summary") or "Reminder"),
            "start_date_time": start_str,
            "end_date_time": end_str,
        }
        if data.get("description"):
            payload["description"] = str(data["description"])

        await hass.services.async_call(
            "calendar",
            "create_event",
            payload,
            blocking=True,
            context=call.context,
        )
        await coord.async_refresh_calendar_agenda()

    async def _handle_intercom_broadcast(call: ServiceCall) -> ServiceResponse:
        data = call.data
        message = str(data.get("message") or "").strip()
        media_url = str(data.get("media_url") or "").strip()
        if media_url and not (
            media_url.startswith("media-source://")
            or media_url.startswith("/api/latter/")
        ):
            raise ServiceValidationError(
                "Intercom media_url must be a Home Assistant media-source:// URI or local /api/latter/ resource.",
                translation_domain=DOMAIN,
                translation_key="invalid_intercom_media_url",
            )
        target_speakers = data.get("target_speakers") or []
        tts_entity = str(data.get("tts_entity") or "").strip()

        speakers = [str(s) for s in target_speakers]
        raw_target = str(data.get("target_device") or "").strip()
        target_low = raw_target.lower()
        kind = target_kind(raw_target)
        if kind == "device":
            _resolve_coordinator_from_call(hass, call)

        scoped_mode = kind in ("occupied_areas", "person")
        if scoped_mode or not speakers:
            all_online_speakers = [
                s.entity_id
                for s in sorted(
                    get_area_state_index(hass).states_for_domain("media_player"),
                    key=lambda st: st.entity_id,
                )
                if s.state not in ("unavailable", "unknown")
                and is_music_assistant_player(hass, s)
            ]
            if scoped_mode:
                ent_reg = er.async_get(hass)
                dev_reg = dr.async_get(hass)
                occupied_areas = _resolve_occupied_area_ids(
                    hass, kind, target_low
                )

                matched_speakers: list[str] = []
                seen_dev_ids: set[str] = set()
                if occupied_areas:
                    for c in iter_coordinators(hass):
                        if c.active_area_id in occupied_areas:
                            for cand_spk in (c.active_speaker, c.local_speaker):
                                if not cand_spk or cand_spk in matched_speakers:
                                    continue
                                st_s = hass.states.get(cand_spk)
                                if not st_s or st_s.state in ("unavailable", "unknown"):
                                    continue
                                e_entry = ent_reg.async_get(cand_spk)
                                dev_key = (
                                    e_entry.device_id
                                    if e_entry and e_entry.device_id
                                    else (c.esphome_device_id or cand_spk)
                                )
                                if dev_key in seen_dev_ids:
                                    continue
                                seen_dev_ids.add(dev_key)
                                matched_speakers.append(cand_spk)
                    for spk_id in all_online_speakers:
                        e_entry = ent_reg.async_get(spk_id)
                        spk_area = e_entry.area_id if e_entry else None
                        if not spk_area and e_entry and e_entry.device_id:
                            d_entry = dev_reg.async_get(e_entry.device_id)
                            if d_entry:
                                spk_area = d_entry.area_id
                        if spk_area in occupied_areas:
                            dev_key = (
                                e_entry.device_id
                                if e_entry and e_entry.device_id
                                else spk_id
                            )
                            if dev_key not in seen_dev_ids and spk_id not in matched_speakers:
                                seen_dev_ids.add(dev_key)
                                matched_speakers.append(spk_id)

                if not matched_speakers:
                    return {
                        "delivered": False,
                        "reason": "no_occupied_areas",
                        "targets": [],
                    }
                speakers = matched_speakers
            else:
                speakers = all_online_speakers

        if not speakers:
            return {
                "delivered": False,
                "reason": "no_targets",
                "targets": [],
            }

        await async_announce_on_targets(
            hass,
            speakers=speakers,
            message=message,
            media_url=media_url,
            tts_entity=tts_entity,
            blocking=False,
        )
        return {
            "delivered": True,
            "targets": speakers,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_DEVICE_HELLO,
        _handle_device_hello,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("contract", default=3): vol.Coerce(int),
                vol.Optional("boot_id", default=""): cv.string,
                vol.Optional("manifest", default=""): cv.string,
                vol.Optional("prefs_seq", default=0): vol.Coerce(int),
                vol.Optional("dirty_prefs", default=""): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ACTIVE_SPEAKER,
        _handle_set_active_speaker,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Required("entity_id"): cv.string,
                vol.Optional("transfer_queue", default=True): vol.Any(bool, cv.string),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MEDIA_COMMAND,
        _handle_media_command,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("command", default="toggle"): cv.string,
                vol.Optional("entity_id"): cv.string,
                vol.Optional("seek_position"): vol.Any(vol.Coerce(float), cv.string),
                vol.Optional("media_id"): cv.string,
                vol.Optional("media_type"): cv.string,
                vol.Optional("enqueue"): cv.string,
                vol.Optional("group_members"): vol.Any(cv.string, [cv.string]),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MEDIA_VOLUME,
        _handle_media_volume,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("entity_id"): cv.string,
                vol.Optional("action", default="set"): cv.string,
                vol.Optional("volume_level"): vol.Any(vol.Coerce(float), cv.string),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ACTIVE_AREA,
        _handle_set_active_area,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Required("area_id"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOTE_ACTION,
        _handle_remote_action,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("slot", default=1): vol.Coerce(int),
                vol.Optional("action", default="select_slot"): cv.string,
                vol.Optional("command"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MUSIC_BROWSE,
        _handle_music_browse,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("req_id", default=0): vol.Coerce(int),
                vol.Optional("mode", default="speakers"): cv.string,
                vol.Optional("page", default=1): vol.Coerce(int),
                vol.Optional("page_size"): vol.Coerce(int),
                vol.Optional("search", default=""): cv.string,
                vol.Optional("speaker"): cv.string,
                vol.Optional("last_speaker"): cv.string,
                vol.Optional("album_sort", default="name"): cv.string,
                vol.Optional("artist_album_sort", default="year"): cv.string,
                vol.Optional("podcast_sort", default="newest"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_AREA_BROWSE,
        _handle_area_browse,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("req_id", default=0): vol.Coerce(int),
                vol.Optional("mode", default="entities"): cv.string,
                vol.Optional("area_id"): cv.string,
                vol.Optional("domain_filter", default=""): cv.string,
                vol.Optional("page", default=1): vol.Coerce(int),
                vol.Optional("page_size"): vol.Coerce(int),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_AREA_ACTION,
        _handle_area_action,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("entity_id"): cv.string,
                vol.Optional("area_id"): cv.string,
                vol.Optional("action"): cv.string,
                vol.Optional("level"): vol.Any(vol.Coerce(float), cv.string),
                vol.Optional("code"): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CALENDAR_FETCH,
        _handle_calendar_fetch,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("req_id", default=0): vol.Coerce(int),
                vol.Optional("days", default=30): vol.Coerce(int),
                vol.Optional("page", default=1): vol.Coerce(int),
                vol.Optional("page_size"): vol.Coerce(int),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CALENDAR_CREATE_EVENT,
        _handle_calendar_create_event,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("calendar_entity"): cv.string,
                vol.Required("summary"): cv.string,
                vol.Optional("start_date_time"): cv.string,
                vol.Optional("end_date_time"): cv.string,
                vol.Optional("in_minutes", default=15): vol.Any(vol.Coerce(int), cv.string),
                vol.Optional("duration_minutes", default=30): vol.Any(vol.Coerce(int), cv.string),
                vol.Optional("description"): cv.string,
            }
        ),
    )

    async def _handle_notify(call: ServiceCall) -> None:
        """Dispatch a toast notification, chime, and optional camera snapshot to displays."""
        data = call.data
        raw_target = str(data.get("target_device") or "").strip()
        target_low = raw_target.lower()
        kind = target_kind(raw_target)

        all_coords = [
            c for c in iter_coordinators(hass) if not c.is_ble_tag and c.has_display
        ]
        target_coords: list[LatterCoordinator] = []

        if kind == "all":
            target_coords = list(all_coords)
        elif kind in ("occupied_areas", "person"):
            occupied_areas = _resolve_occupied_area_ids(hass, kind, target_low)
            for c in all_coords:
                if (
                    kind == "person"
                    and c.assigned_person.lower() == target_low
                    and not c.is_device_away()
                ) or (c.active_area_id and c.active_area_id in occupied_areas):
                    target_coords.append(c)

            if not target_coords:
                return
        else:
            single = _resolve_coordinator_from_call(hass, call)
            target_coords = [single]

        if not target_coords:
            return

        title = str(data.get("title") or "Alert").strip()
        message = str(data.get("message") or "").strip()
        priority = str(data.get("priority") or "normal").strip().lower()
        duration = int(data.get("duration") or 8)
        chime = _parse_bool(data.get("chime"), default=True)
        is_announce = _parse_bool(data.get("announce"), default=False)
        card_chime = False if is_announce else chime
        cam_ent = str(data.get("camera_entity") or "").strip() or None

        for coord in target_coords:
            coord.async_dispatch_notification(
                title=title,
                message=message,
                priority=priority,
                duration=duration,
                chime=card_chime,
                camera_entity=cam_ent,
            )

            esp_notify_svc = esphome_service(
                hass, coord.esphome_device_id, "show_notification"
            )
            if esp_notify_svc:
                try:
                    await hass.services.async_call(
                        "esphome",
                        esp_notify_svc,
                        {
                            "title": title[:48],
                            "message": message[:160],
                            "priority": priority,
                            "duration": duration,
                            "chime": card_chime,
                            "camera_url": coord.alert_camera_url,
                            "alert_id": coord.alert_id,
                        },
                        blocking=True,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Direct esphome.%s call skipped: %s", esp_notify_svc, err)

            if is_announce and message:
                sat_ent = resolve_assist_satellite_entity(hass, coord.local_speaker, coord)
                target_list = [sat_ent] if sat_ent else ([coord.local_speaker] if coord.local_speaker else [])
                if target_list:
                    await async_announce_on_targets(
                        hass,
                        speakers=target_list,
                        message=message,
                        blocking=False,
                    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        _handle_intercom_broadcast,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("message"): cv.string,
                vol.Optional("media_url"): cv.string,
                vol.Optional("target_speakers"): vol.All(
                    cv.entity_ids, [cv.entity_domain("media_player")]
                ),
                vol.Optional("tts_entity"): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    notify_schema = vol.Schema(
        {
            **BASE_TARGET_FIELDS,
            vol.Optional("title", default="Notification"): cv.string,
            vol.Required("message"): cv.string,
            vol.Optional("priority", default="normal"): cv.string,
            vol.Optional("duration", default=8): vol.Coerce(int),
            vol.Optional("chime", default=True): vol.Any(bool, cv.string),
            vol.Optional("announce", default=False): vol.Any(bool, cv.string),
            vol.Optional("camera_entity"): cv.string,
        }
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_NOTIFY,
        _handle_notify,
        schema=notify_schema,
    )

    async def _handle_save_custom_color(call: ServiceCall) -> None:
        await _require_admin_if_user_call(hass, call)
        coord = _resolve_coordinator_from_call(hass, call)
        raw_hex = str(call.data.get("hex_color") or "").strip().upper()
        if not raw_hex.startswith("#"):
            raw_hex = f"#{raw_hex}"
        if not re.fullmatch(r"#[0-9A-F]{6}", raw_hex):
            raise ServiceValidationError(
                f"Invalid hex color '{raw_hex}' (expected #RRGGBB).",
                translation_domain=DOMAIN,
                translation_key="invalid_hex_color",
                translation_placeholders={"hex_color": raw_hex},
            )
        name = str(call.data.get("name") or f"Custom ({raw_hex})").strip()

        domain_data = hass.data.setdefault(DOMAIN, {})
        global_cfg: dict[str, Any] = domain_data.setdefault(DATA_GLOBAL_CONFIG, {})
        palettes: list[dict[str, str]] = [
            dict(p) for p in (global_cfg.get(CONF_CUSTOM_PALETTES) or []) if isinstance(p, dict)
        ]
        existing = next((p for p in palettes if str(p.get("hex", "")).upper() == raw_hex), None)
        if existing is not None:
            if call.data.get("name"):
                existing["name"] = name
        else:
            palettes.insert(0, {"name": name, "hex": raw_hex})
            palettes = palettes[:24]

        coord.update_device_config(
            {
                **coord.device_data,
                CONF_DEVICE_CUSTOM_COLOR: raw_hex,
                "color_profile": "Custom",
            }
        )
        await async_save_and_broadcast_global_config(
            hass, {CONF_CUSTOM_PALETTES: palettes}
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_CUSTOM_COLOR,
        _handle_save_custom_color,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Required("hex_color"): cv.string,
                vol.Optional("name"): cv.string,
            }
        ),
    )

    async def _handle_set_dock_apps(call: ServiceCall) -> None:
        """Save the Home dock chosen on the device (Home settings) as the Device's dock_apps setting."""
        await _require_admin_if_user_call(hass, call)
        coord = _resolve_coordinator_from_call(hass, call)
        try:
            dock_csv = normalize_dock_apps(call.data.get("dock_apps"))
        except ValueError as err:
            raise ServiceValidationError(
                str(err),
                translation_domain=DOMAIN,
                translation_key="invalid_dock_apps",
                translation_placeholders={"error": str(err)},
            ) from err
        if dock_csv != coord.dock_apps_csv:
            coord.update_device_config({**coord.device_data, CONF_DOCK_APPS: dock_csv})
            await coord.async_apply_options()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DOCK_APPS,
        _handle_set_dock_apps,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Required("dock_apps"): cv.string,
            }
        ),
    )

    async def _handle_reset_device(call: ServiceCall) -> None:
        """Reset a Latter Device: the settings saved on the device and/or its Latter options."""
        await _require_admin_if_user_call(hass, call)
        coord = _resolve_coordinator_from_call(hass, call)
        await async_reset_device(
            hass,
            coord,
            device_settings=bool(call.data["device_settings"]),
            latter_options=bool(call.data["latter_options"]),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_DEVICE,
        _handle_reset_device,
        schema=vol.Schema(
            {
                vol.Required("target_device"): vol.All(cv.string, vol.Strip, vol.Length(min=1)),
                vol.Optional("device_settings", default=True): cv.boolean,
                vol.Optional("latter_options", default=True): cv.boolean,
            }
        ),
    )

    async def _handle_doorbell_intercom(call: ServiceCall) -> ServiceResponse:
        """Execute a doorbell listen, push-to-talk reply, unlock or call_target action and return target metadata."""
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data
        action = str(data.get("action") or "listen_toggle").strip()
        cam_ent = str(data.get("camera_entity") or "").strip() or None
        msg = str(data.get("message") or "").strip()
        nr_level = str(data.get("noise_reduction") or "").strip() or None
        raw_idx = data.get("camera_index")
        cam_idx = int(raw_idx) if raw_idx is not None and str(raw_idx).strip() != "" else None
        code = str(data.get("code") or "").strip() or None
        info = await async_execute_doorbell_intercom(
            hass=hass,
            coordinator=coord,
            action=action,
            camera_entity=cam_ent,
            message=msg,
            noise_reduction=nr_level,
            camera_index=cam_idx,
            code=code,
        )
        return {
            "status": "ok",
            "device_slug": coord.device_slug,
            "action": action,
            "doorbell_talk_state": coord.doorbell_talk_state,
            "doorbell_noise_reduction": coord.doorbell_noise_reduction,
            **info,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_DOORBELL_INTERCOM,
        _handle_doorbell_intercom,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("action", default="listen_toggle"): cv.string,
                vol.Optional("camera_entity"): cv.string,
                vol.Optional("camera_index"): vol.Any(vol.Coerce(int), cv.string),
                vol.Optional("message"): cv.string,
                vol.Optional("noise_reduction"): vol.Any(
                    vol.In(DOORBELL_NOISE_REDUCTION_LEVELS), ""
                ),
                vol.Optional("code"): cv.string,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def _handle_set_device_prefs(call: ServiceCall) -> None:
        """Apply on-device preference changes reported by a Latter Device or automation."""
        await _require_admin_if_user_call(hass, call)
        coord = _resolve_coordinator_from_call(hass, call)
        base_seq = int(call.data.get("base_seq") or 0)
        changes = str(call.data.get("changes") or "")
        await coord.async_handle_set_device_prefs(base_seq=base_seq, changes_raw=changes)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DEVICE_PREFS,
        _handle_set_device_prefs,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("base_seq", default=0): vol.Coerce(int),
                vol.Required("changes"): cv.string,
            }
        ),
    )

    async def _handle_timer_alarm_state(call: ServiceCall) -> None:
        """Apply event-driven timer and alarm state reported by a Latter Device."""
        coord = _resolve_coordinator_from_call(hass, call)
        coord.handle_timer_alarm_state(
            timer_running=_parse_bool(call.data.get("timer_running"), default=False),
            timer_paused=_parse_bool(call.data.get("timer_paused"), default=False),
            remaining_sec=int(call.data.get("remaining_sec") or 0),
            ringing=_parse_bool(call.data.get("ringing"), default=False),
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_TIMER_ALARM_STATE,
        _handle_timer_alarm_state,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("timer_running", default=False): vol.Any(bool, int, cv.string),
                vol.Optional("timer_paused", default=False): vol.Any(bool, int, cv.string),
                vol.Optional("remaining_sec", default=0): vol.Coerce(int),
                vol.Optional("ringing", default=False): vol.Any(bool, int, cv.string),
            }
        ),
    )


_BOUND_DEVICE_RPC_SERVICES: frozenset[str] = frozenset(
    {
        SERVICE_DEVICE_HELLO,
        SERVICE_MUSIC_BROWSE,
        SERVICE_SET_ACTIVE_SPEAKER,
        SERVICE_MEDIA_COMMAND,
        SERVICE_MEDIA_VOLUME,
        SERVICE_AREA_BROWSE,
        SERVICE_AREA_ACTION,
        SERVICE_SET_ACTIVE_AREA,
        SERVICE_REMOTE_ACTION,
        SERVICE_CALENDAR_FETCH,
        SERVICE_CALENDAR_CREATE_EVENT,
        SERVICE_INTERCOM_BROADCAST,
        SERVICE_NOTIFY,
        SERVICE_SAVE_CUSTOM_COLOR,
        SERVICE_SET_DOCK_APPS,
        SERVICE_SET_DEVICE_PREFS,
        SERVICE_TIMER_ALARM_STATE,
        SERVICE_DOORBELL_INTERCOM,
    }
)


async def async_dispatch_bound_rpc(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    service_name: str,
    data: dict[str, Any],
) -> None:
    """Dispatch a reassembled RPC from `coord`'s bound `System: RPC Outbox` entity."""
    svc = str(service_name or "").strip()
    if svc not in _BOUND_DEVICE_RPC_SERVICES:
        _LOGGER.warning(
            "Rejected unsupported RPC '%s' from device '%s'", svc, coord.device_slug
        )
        return

    sanitized: dict[str, Any] = dict(data or {})
    if svc in (SERVICE_INTERCOM_BROADCAST, SERVICE_NOTIFY):
        raw_t = str(sanitized.get("target_device") or "").strip()
        raw_low = raw_t.lower()
        if raw_low in ("all", "occupied_areas") or raw_low.startswith("person."):
            sanitized["target_device"] = raw_t
        else:
            sanitized["target_device"] = coord.subentry_id
    else:
        sanitized["target_device"] = coord.subentry_id

    await hass.services.async_call(
        DOMAIN,
        svc,
        sanitized,
        blocking=True,
        context=Context(),
    )
