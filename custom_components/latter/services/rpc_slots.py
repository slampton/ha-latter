"""Shared RPC parameter parsers, slot push pagination, calendar window push, and intercom broadcast (`D-074`)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime, timedelta
import logging
import math
import re
import time
from typing import TypedDict, Unpack

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util
import probatio as vol

from ..areas.catalogs import get_area_available_domains, get_area_entities
from ..areas.registry import resolve_person_area_and_distance
from ..const import (
    CONF_BROADCAST_SPEAKERS,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    target_kind,
)
from ..coordinator import LatterCoordinator, resolve_coordinator
from ..feeds import async_fetch_calendar_window, discover_calendars
from ..hub_registry import iter_coordinators
from ..identity import esphome_service
from ..media.linking import resolve_ma_counterpart_entity
from ..media.tts_queue import async_announce_on_targets
from ..presence.ble_fabric import get_ble_fabric
from ..protocol_codec import pack_calendar_window_chunks, utf8_safe_truncate
from ..repairs_keys import slot_push_failing_issue_id

_LOGGER = logging.getLogger(__name__)

BASE_TARGET_FIELDS: dict[vol.Marker, object] = {
    vol.Optional("target_device"): cv.string,
}

_SLOT_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]+")
_SLOT_PUSH_WARN_INTERVAL_S = 600.0
_SLOT_PUSH_REPAIR_THRESHOLD = 5
_LONG_TEXT_CAP = 512
_SHORT_TEXT_CAP = 120
_DEFAULT_BYTE_CAP = 255
_MAX_CALENDAR_WINDOW_DAYS = 180
_DEFAULT_PAST_CALENDAR_DAYS = 35
_MIN_FUTURE_CALENDAR_DAYS = 62
_DEFAULT_CALENDAR_WINDOW_DAYS = 30
_UNAVAIL_STATES = ("unavailable", "unknown")


class BrowseSlotOptions(TypedDict, total=False):
    """Keyword options for `async_push_browse_slots`."""

    page_size: int
    items: list[dict[str, object]]
    is_area_slots: bool
    req_id: int
    total_items_override: int | None
    items_offset: int


class CalendarWindowOptions(TypedDict, total=False):
    """Keyword options for `async_push_calendar_window`."""

    days: int
    start_date_raw: str
    end_date_raw: str


class IntercomBroadcastResult(TypedDict):
    """Return payload for `async_execute_intercom_broadcast`."""

    delivered: bool
    targets: list[str]


class IntercomBroadcastSkippedResult(IntercomBroadcastResult):
    """Return payload when `async_execute_intercom_broadcast` skips delivery."""

    reason: str


def _clean_slot_text(raw: object, max_chars: int, max_bytes: int | None = None) -> str:
    """Strip wire delimiters/control characters, cap character count, and truncate safely on UTF-8 boundaries."""
    cleaned = _SLOT_CONTROL_CHARS_RE.sub(" ", str(raw or ""))[:max_chars]
    byte_cap = max_bytes if max_bytes is not None else max(max_chars * 2, _DEFAULT_BYTE_CAP)
    return utf8_safe_truncate(cleaned, byte_cap)


def parse_bool(val: object, default: bool = False) -> bool:
    """Safely parse booleans or YAML string booleans ('true', 'false', '1', '0') from RPC/service calls."""
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


def parse_int(val: object, default: int = 0) -> int:
    """Safely parse integer parameters without crashing on malformed strings."""
    if val is None or isinstance(val, bool):
        return default
    s = str(val).strip()
    if not s:
        return default
    try:
        parsed = float(s)
        return int(parsed) if math.isfinite(parsed) else default
    except (TypeError, ValueError, OverflowError):
        return default


def parse_opt_float(val: object) -> float | None:
    """Safely parse an optional finite float."""
    if val is None or isinstance(val, bool):
        return None
    s = str(val).strip()
    if not s:
        return None
    try:
        parsed = float(s)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def resolve_coordinator_by_target(
    hass: HomeAssistant, raw_target: object
) -> LatterCoordinator:
    """Resolve the target LatterCoordinator strictly by target_device (or single-device default)."""
    target_str = str(raw_target).strip() if raw_target is not None else ""
    coord = resolve_coordinator(hass, target_str or None)
    if coord is None:
        raise ServiceValidationError(
            f"Target Latter device '{target_str or 'unspecified'}' could not be resolved.",
            translation_domain=DOMAIN,
            translation_key="unknown_target",
            translation_placeholders={"target_device": target_str or "unspecified"},
        )
    return coord


def resolve_coordinator_from_call(
    hass: HomeAssistant, call: ServiceCall
) -> LatterCoordinator:
    """Resolve the target LatterCoordinator from a Home Assistant ServiceCall."""
    return resolve_coordinator_by_target(hass, call.data.get("target_device"))


async def require_admin_if_user_call(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Reject non-admin Home Assistant user invocations of configuration-mutating services."""
    user_id = call.context.user_id if call.context else None
    if not user_id:
        return
    user = await hass.auth.async_get_user(user_id)
    if user is not None and not user.is_admin:
        raise Unauthorized(context=call.context, user_id=user_id, permission="admin")


def _pack_browse_slot_rows(
    page_slice: list[dict[str, object]], mode: str, *, include_levels: bool
) -> list[str]:
    """Encode paginated slot dictionaries into `\x1f`-delimited wire rows."""
    mode_low = str(mode).strip().lower()
    name_cap = _LONG_TEXT_CAP if mode_low in ("bio", "track_info", "lyrics") else _SHORT_TEXT_CAP
    byte_cap = _LONG_TEXT_CAP if name_cap >= _LONG_TEXT_CAP else _DEFAULT_BYTE_CAP
    packed_rows: list[str] = []
    for slot in page_slice:
        s_name = _clean_slot_text(slot.get("name", ""), name_cap, byte_cap)
        s_id = _clean_slot_text(slot.get("id", ""), _DEFAULT_BYTE_CAP, _DEFAULT_BYTE_CAP)
        s_type = _clean_slot_text(slot.get("type", mode), 32, 64)
        s_act = 1 if bool(slot.get("active", False)) else 0
        s_lvl = parse_int(slot.get("level"), -1) if include_levels else -1
        raw_qid = slot.get("queue_item_id")
        if raw_qid is not None or "is_current" in slot:
            s_qid = _clean_slot_text(raw_qid or "", 128, 128)
            s_cur = 1 if bool(slot.get("is_current", False)) else 0
            packed_rows.append(
                f"{s_name}\x1f{s_id}\x1f{s_type}\x1f{s_act}\x1f{s_lvl}\x1f{s_qid}\x1f{s_cur}"
            )
        else:
            packed_rows.append(f"{s_name}\x1f{s_id}\x1f{s_type}\x1f{s_act}\x1f{s_lvl}")
    return packed_rows


def _record_slot_push_failure(
    hass: HomeAssistant, coord: LatterCoordinator, esphome_action: str, err: Exception
) -> None:
    """Rate-limit slot push warnings and create a Repairs issue after persistent failures."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    fail_counts: dict[str, int] = domain_data.setdefault("_slot_push_failures", {})
    last_warn_ts: dict[str, float] = domain_data.setdefault("_slot_push_last_warn", {})
    fail_key = coord.subentry_id
    count = fail_counts.get(fail_key, 0) + 1
    fail_counts[fail_key] = count
    now_m = time.monotonic()
    if (
        now_m - last_warn_ts.get(fail_key, -_SLOT_PUSH_WARN_INTERVAL_S)
        >= _SLOT_PUSH_WARN_INTERVAL_S
    ):
        last_warn_ts[fail_key] = now_m
        _LOGGER.warning(
            "Failed to push %s slots to '%s' (consecutive failures=%d): %s",
            esphome_action,
            coord.device_slug,
            count,
            err,
        )
    if count >= _SLOT_PUSH_REPAIR_THRESHOLD:
        ir.async_create_issue(
            hass,
            DOMAIN,
            slot_push_failing_issue_id(fail_key),
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="slot_push_failing",
            translation_placeholders={
                "device_slug": coord.device_slug,
                "service_name": f"esphome.{esphome_action}",
                "error": utf8_safe_truncate(str(err), 160),
            },
        )


async def async_push_browse_slots(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    mode: str,
    page: int = 1,
    **opts: Unpack[BrowseSlotOptions],
) -> None:
    """Paginate items and push them to the Device's bound `esphome.<node>_latter_set_slots` action."""
    esphome_action = esphome_service(hass, coord.esphome_device_id, "latter_set_slots")
    is_area_slots = bool(opts.get("is_area_slots", False))
    include_levels = is_area_slots and esphome_action is not None

    slot_capacity = (
        coord.card_slot_capacity if include_levels else coord.list_slot_capacity
    )
    raw_ps = opts.get("page_size", slot_capacity)
    eff_page_size = max(1, min(slot_capacity, int(raw_ps)))
    eff_offset = max(0, int(opts.get("items_offset", 0)))
    items = list(opts.get("items") or [])
    total_override = opts.get("total_items_override")
    total_items = (
        max(eff_offset + len(items), int(total_override))
        if total_override is not None and items
        else (eff_offset + len(items))
    )
    total_pages = max(1, math.ceil(total_items / eff_page_size))
    clamped_page = max(1, min(int(page), total_pages))
    local_start = max(0, (clamped_page - 1) * eff_page_size - eff_offset)
    page_slice = items[local_start : local_start + eff_page_size]
    packed_rows = _pack_browse_slot_rows(
        page_slice, mode, include_levels=include_levels
    )

    if esphome_action is None:
        _LOGGER.debug(
            "No ESPHome service matching *_latter_set_slots found (target slug '%s'); device is headless or offline.",
            coord.device_slug,
        )
        return

    payload: dict[str, object] = {
        "is_area_slots": is_area_slots,
        "req_id": max(0, int(opts.get("req_id", 0))),
        "mode": str(mode),
        "page": clamped_page,
        "total_pages": total_pages,
        "slots": "\x1e".join(packed_rows),
    }
    fail_counts: dict[str, int] = hass.data.setdefault(DOMAIN, {}).setdefault(
        "_slot_push_failures", {}
    )
    fail_key = coord.subentry_id
    try:
        await hass.services.async_call(
            "esphome", esphome_action, payload, blocking=True
        )
        if fail_counts.pop(fail_key, 0) >= _SLOT_PUSH_REPAIR_THRESHOLD:
            ir.async_delete_issue(hass, DOMAIN, slot_push_failing_issue_id(fail_key))
    except Exception as err:  # noqa: BLE001
        _record_slot_push_failure(hass, coord, esphome_action, err)


def _parse_speaker_list(raw_target_speakers: object) -> list[str]:
    """Normalize `target_speakers` list, set, tuple, or comma-separated string."""
    if isinstance(raw_target_speakers, (list, tuple, set)):
        return [str(s).strip() for s in raw_target_speakers if str(s or "").strip()]
    if raw_target_speakers:
        return [s.strip() for s in str(raw_target_speakers).split(",") if s.strip()]
    return []


def _is_speaker_online(hass: HomeAssistant, entity_id: str) -> bool:
    st_obj = hass.states.get(entity_id)
    return st_obj is not None and st_obj.state not in _UNAVAIL_STATES


def _speaker_matches_coord(
    hass: HomeAssistant,
    ent_reg: er.EntityRegistry,
    entity_id: str,
    coord: LatterCoordinator,
) -> bool:
    """Return True when `entity_id` belongs to `coord` (local speaker, MA counterpart, or ESPHome device)."""
    if not entity_id:
        return False
    if entity_id in (coord.local_speaker, coord.local_ma_speaker):
        return True
    if coord.local_ma_speaker:
        ma_match = resolve_ma_counterpart_entity(hass, entity_id)
        if ma_match and ma_match == coord.local_ma_speaker:
            return True
    if coord.esphome_device_id:
        e_entry = ent_reg.async_get(entity_id)
        if e_entry and e_entry.device_id == coord.esphome_device_id:
            return True
    return False


def _match_occupied_area_speakers(
    hass: HomeAssistant, configured_pool: list[str], occupied_areas: set[str]
) -> list[str]:
    """Return online pool speakers in `occupied_areas`, deduplicated by `device_id`."""
    if not occupied_areas:
        return []
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    matched: list[str] = []
    seen_dev_ids: set[str] = set()
    for spk_id in configured_pool:
        if not _is_speaker_online(hass, spk_id):
            continue
        e_entry = ent_reg.async_get(spk_id)
        spk_area = e_entry.area_id if e_entry else None
        if not spk_area and e_entry and e_entry.device_id:
            d_entry = dev_reg.async_get(e_entry.device_id)
            if d_entry:
                spk_area = d_entry.area_id
        if spk_area in occupied_areas:
            dev_key = e_entry.device_id if e_entry and e_entry.device_id else spk_id
            if dev_key not in seen_dev_ids and spk_id not in matched:
                seen_dev_ids.add(dev_key)
                matched.append(spk_id)
    return matched


def _filter_broadcast_speakers(
    hass: HomeAssistant,
    speakers: list[str],
    caller_coord: LatterCoordinator | None,
    *,
    explicit: bool,
) -> list[str]:
    """Exclude caller anti-echo speaker and (unless explicit) quiet-mode Devices (`D-074`)."""
    quiet_coords = (
        []
        if explicit
        else [c for c in iter_coordinators(hass) if is_coord_in_quiet_mode(c)]
    )
    if caller_coord is None and not quiet_coords:
        return speakers
    ent_reg = er.async_get(hass)
    filtered: list[str] = []
    for spk_id in speakers:
        if caller_coord is not None and _speaker_matches_coord(
            hass, ent_reg, spk_id, caller_coord
        ):
            continue
        if any(_speaker_matches_coord(hass, ent_reg, spk_id, qc) for qc in quiet_coords):
            continue
        filtered.append(spk_id)
    return filtered


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
                    fabric.get_area_occupancy(area_entry.id).get("persons") or []
                )
            ]
            if target_low in occ_persons:
                occupied_areas.add(area_entry.id)
    else:
        for c in iter_coordinators(hass):
            if c.active_area_id and fabric.get_area_occupancy(c.active_area_id).get(
                "is_occupied"
            ):
                occupied_areas.add(c.active_area_id)
        for area_entry in area_reg.async_list_areas():
            if fabric.get_area_occupancy(area_entry.id).get("is_occupied"):
                occupied_areas.add(area_entry.id)
    return occupied_areas


async def async_push_active_area_entities(
    hass: HomeAssistant, coord: LatterCoordinator
) -> None:
    """Push the active area's entity slots to `esphome.<slug>_latter_set_slots` when the device is online."""
    if (
        not coord.is_online
        or esphome_service(hass, coord.esphome_device_id, "latter_set_slots") is None
    ):
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
        is_area_slots=True,
    )


async def _async_execute_intercom_broadcast(
    hass: HomeAssistant,
    data: Mapping[str, object],
    *,
    caller_subentry_id: str | None = None,
) -> IntercomBroadcastResult | IntercomBroadcastSkippedResult:
    """Execute an intercom broadcast enforcing `D-074` speaker pools, caller anti-echo, and quiet modes."""
    message = str(data.get("message") or "").strip()
    media_url = str(data.get("media_url") or "").strip()
    if media_url and not media_url.startswith(("media-source://", "/api/latter/")):
        raise ServiceValidationError(
            "Intercom media_url must be a Home Assistant media-source:// URI or local /api/latter/ resource.",
            translation_domain=DOMAIN,
            translation_key="invalid_intercom_media_url",
        )
    explicit_speakers = _parse_speaker_list(data.get("target_speakers"))
    tts_entity = str(data.get("tts_entity") or "").strip()
    raw_target = str(data.get("target_device") or "").strip()
    target_low = raw_target.lower()
    kind = target_kind(raw_target)

    caller_coord = (
        resolve_coordinator(hass, caller_subentry_id) if caller_subentry_id else None
    )
    if kind == "device":
        resolved_target_coord = _resolve_coordinator_by_target(hass, raw_target)
        if caller_coord is None:
            caller_coord = resolved_target_coord

    global_cfg = (hass.data.get(DOMAIN, {}) or {}).get(DATA_GLOBAL_CONFIG) or {}
    raw_sys_spks = global_cfg.get(CONF_BROADCAST_SPEAKERS) if isinstance(global_cfg, Mapping) else None
    system_broadcast_speakers = [
        str(s).strip()
        for s in (raw_sys_spks if isinstance(raw_sys_spks, (list, tuple)) else ())
        if str(s or "").strip().startswith("media_player.")
    ]
    configured_pool = (
        caller_coord.effective_broadcast_speakers
        if caller_coord is not None
        else system_broadcast_speakers
    )

    speakers = list(explicit_speakers)
    scoped_mode = kind in ("occupied_areas", "person")
    if scoped_mode and not explicit_speakers:
        if not configured_pool:
            raise ServiceValidationError(
                "No broadcast speakers are configured in Latter Studio.",
                translation_domain=DOMAIN,
                translation_key="no_broadcast_speakers",
            )
        occupied_areas = _resolve_occupied_area_ids(hass, kind, target_low)
        matched_speakers = _match_occupied_area_speakers(
            hass, configured_pool, occupied_areas
        )
        if not matched_speakers:
            return {"delivered": False, "reason": "no_occupied_areas", "targets": []}
        speakers = matched_speakers
    elif not speakers:
        if not configured_pool:
            raise ServiceValidationError(
                "No broadcast speakers are configured in Latter Studio.",
                translation_domain=DOMAIN,
                translation_key="no_broadcast_speakers",
            )
        speakers = [s for s in configured_pool if _is_speaker_online(hass, s)]

    speakers = _filter_broadcast_speakers(
        hass, speakers, caller_coord, explicit=bool(explicit_speakers)
    )
    if not speakers:
        return {"delivered": False, "reason": "no_targets", "targets": []}

    await async_announce_on_targets(
        hass,
        speakers=speakers,
        message=message,
        media_url=media_url,
        tts_entity=tts_entity,
        blocking=False,
    )
    return {"delivered": True, "targets": speakers}


def is_coord_in_quiet_mode(coord: LatterCoordinator) -> bool:
    """Return True when a display Device is in Bedtime Mode or Do Not Disturb."""
    if coord.is_ble_tag or not coord.has_display:
        return False
    return bool(coord.get_device_pref("bedtime_active")) or coord.do_not_disturb


async def async_push_calendar_window(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    *,
    req_id: int = 0,
    **opts: Unpack[CalendarWindowOptions],
) -> None:
    """Fetch a bounded date window of calendar events and push chunks to `latter_set_calendar_view`."""
    today = dt_util.now().date()
    start_raw = opts.get("start_date_raw", "")
    end_raw = opts.get("end_date_raw", "")
    days = opts.get("days", _DEFAULT_CALENDAR_WINDOW_DAYS)
    start_d = dt_util.parse_date(start_raw) if start_raw else None
    end_d = dt_util.parse_date(end_raw) if end_raw else None
    if start_d is None:
        start_d = today - timedelta(days=_DEFAULT_PAST_CALENDAR_DAYS)
    if end_d is None or end_d < start_d:
        end_d = today + timedelta(
            days=max(_MIN_FUTURE_CALENDAR_DAYS, int(days or _DEFAULT_CALENDAR_WINDOW_DAYS) + 7)
        )
        if end_d < start_d:
            end_d = start_d + timedelta(days=_MIN_FUTURE_CALENDAR_DAYS)
    if (end_d - start_d).days > _MAX_CALENDAR_WINDOW_DAYS:
        end_d = start_d + timedelta(days=_MAX_CALENDAR_WINDOW_DAYS)
    coord.last_cal_window = (start_d, end_d)

    window_events = await async_fetch_calendar_window(
        hass, coord.calendar_entities, start_d, end_d
    )
    esphome_action = esphome_service(
        hass, coord.esphome_device_id, "latter_set_calendar_view"
    )
    if esphome_action is None:
        return
    chunks = pack_calendar_window_chunks(
        window_events,
        start_d.isoformat(),
        end_d.isoformat(),
        req_id=req_id,
    )
    for chunk in chunks:
        try:
            await hass.services.async_call(
                "esphome", esphome_action, chunk, blocking=True
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("esphome.%s failed: %s", esphome_action, err)
            break


_RRULE_RE = re.compile(
    r"^FREQ=(?:DAILY|WEEKLY|MONTHLY|YEARLY)(?:;[A-Z_]+=[A-Za-z0-9,+-]+)*$"
)
_CAL_CREATE_FEATURE_BIT = 1
_CAL_DELETE_FEATURE_BIT = 2


def _is_calendar_writable(hass: HomeAssistant, cal_id: str) -> bool:
    st = hass.states.get(cal_id)
    if st is not None and "supported_features" in st.attributes:
        return (parse_int(st.attributes.get("supported_features"), 0) & _CAL_CREATE_FEATURE_BIT) != 0
    return True


def _is_calendar_deletable(hass: HomeAssistant, cal_id: str) -> bool:
    st = hass.states.get(cal_id)
    if st is not None and "supported_features" in st.attributes:
        return (parse_int(st.attributes.get("supported_features"), 0) & _CAL_DELETE_FEATURE_BIT) != 0
    return True


def _get_calendar_entity_obj(hass: HomeAssistant, cal_id: str) -> object | None:
    comp = hass.data.get("calendar")
    get_entity = getattr(comp, "get_entity", None)
    return get_entity(cal_id) if callable(get_entity) else None


def _parse_calendar_event_window(
    data: dict[str, object],
) -> tuple[bool, date | datetime, date | datetime]:
    """Parse `(is_all_day, dtstart, dtend)` for `calendar_create_event`."""
    is_all_day = parse_bool(data.get("all_day"), default=False) or (
        bool(str(data.get("start_date") or "").strip())
        and not bool(str(data.get("start_date_time") or "").strip())
    )
    now_local = dt_util.now().replace(second=0, microsecond=0)
    if is_all_day:
        sd = (
            dt_util.parse_date(str(data.get("start_date") or "").strip())
            or now_local.date()
        )
        ed = dt_util.parse_date(str(data.get("end_date") or "").strip())
        if ed is None or ed <= sd:
            ed = sd + timedelta(days=1)
        return True, sd, ed

    raw_sdt = str(data.get("start_date_time") or "").strip()
    raw_edt = str(data.get("end_date_time") or "").strip()
    parsed_s = dt_util.parse_datetime(raw_sdt) if raw_sdt else None
    parsed_e = dt_util.parse_datetime(raw_edt) if raw_edt else None
    start_dt = (
        (
            dt_util.as_local(parsed_s)
            if parsed_s.tzinfo is not None
            else parsed_s.replace(tzinfo=now_local.tzinfo)
        )
        if parsed_s is not None
        else now_local + timedelta(minutes=(15 - (now_local.minute % 15)))
    )
    end_dt = (
        (
            dt_util.as_local(parsed_e)
            if parsed_e.tzinfo is not None
            else parsed_e.replace(tzinfo=now_local.tzinfo)
        )
        if parsed_e is not None
        else start_dt + timedelta(minutes=60)
    )
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(minutes=60)
    return False, start_dt, end_dt


def _resolve_writable_calendar(
    hass: HomeAssistant, coord: LatterCoordinator, requested_cal: str
) -> str:
    """Resolve and validate the target writable calendar entity for `calendar_create_event`."""
    valid_cals = discover_calendars(hass, coord.calendar_entities)
    if requested_cal:
        if requested_cal not in valid_cals or not _is_calendar_writable(
            hass, requested_cal
        ):
            raise ServiceValidationError(
                f"Calendar '{requested_cal}' is not writable or not configured for this Site.",
                translation_domain=DOMAIN,
                translation_key="not_supported",
            )
        return requested_cal
    return next((c for c in valid_cals if _is_calendar_writable(hass, c)), "")


async def async_execute_calendar_create_event(
    hass: HomeAssistant, coord: LatterCoordinator, data: dict[str, object]
) -> None:
    """Create a calendar event and refresh `coord`'s agenda and calendar window."""
    requested_cal = str(data.get("calendar_entity") or "").strip()
    cal_entity = _resolve_writable_calendar(hass, coord, requested_cal)
    cal_ent_obj = _get_calendar_entity_obj(hass, cal_entity) if cal_entity else None
    if not cal_entity or (
        cal_ent_obj is None and not hass.services.has_service("calendar", "create_event")
    ):
        _LOGGER.warning("No writable calendar entity found for calendar_create_event.")
        return

    summary = str(data.get("summary") or "Reminder").strip() or "Reminder"
    location = str(data.get("location") or "").strip()
    description = str(data.get("description") or "").strip()
    rrule = str(data.get("rrule") or "").strip().upper()
    if rrule and not _RRULE_RE.fullmatch(rrule):
        raise ServiceValidationError(
            f"Invalid calendar recurrence rule '{rrule}'.",
            translation_domain=DOMAIN,
            translation_key="not_supported",
        )

    is_all_day, dtstart_val, dtend_val = _parse_calendar_event_window(data)
    create_fn = getattr(cal_ent_obj, "async_create_event", None)
    if rrule and callable(create_fn):
        rfc_kwargs: dict[str, object] = {
            "dtstart": dtstart_val,
            "dtend": dtend_val,
            "summary": summary,
            "rrule": rrule,
        }
        if location:
            rfc_kwargs["location"] = location
        if description:
            rfc_kwargs["description"] = description
        await create_fn(**rfc_kwargs)
    else:
        payload: dict[str, object] = {ATTR_ENTITY_ID: cal_entity, "summary": summary}
        if is_all_day:
            payload["start_date"] = dtstart_val.isoformat()
            payload["end_date"] = dtend_val.isoformat()
        elif isinstance(dtstart_val, datetime) and isinstance(dtend_val, datetime):
            payload["start_date_time"] = dtstart_val.strftime("%Y-%m-%d %H:%M:%S")
            payload["end_date_time"] = dtend_val.strftime("%Y-%m-%d %H:%M:%S")
        if location:
            payload["location"] = location
        if description:
            payload["description"] = description
        await hass.services.async_call(
            "calendar", "create_event", payload, blocking=True, context=Context()
        )

    await coord.async_refresh_calendar_agenda()
    prev_win = coord.last_cal_window
    await async_push_calendar_window(
        hass,
        coord,
        start_date_raw=prev_win[0].isoformat() if prev_win else "",
        end_date_raw=prev_win[1].isoformat() if prev_win else "",
    )


async def async_execute_calendar_delete_event(
    hass: HomeAssistant, coord: LatterCoordinator, data: dict[str, object]
) -> None:
    """Delete a calendar event and refresh `coord`'s agenda and calendar window."""
    cal_entity = str(data.get("calendar_entity") or "").strip()
    uid = str(data.get("uid") or "").strip()
    recurrence_id = str(data.get("recurrence_id") or "").strip()
    recurrence_range = str(data.get("recurrence_range") or "").strip()

    valid_cals = discover_calendars(hass, coord.calendar_entities)
    if (
        not cal_entity
        or not uid
        or cal_entity not in valid_cals
        or not _is_calendar_deletable(hass, cal_entity)
    ):
        raise ServiceValidationError(
            f"Calendar '{cal_entity or '(empty)'}' does not support deleting events.",
            translation_domain=DOMAIN,
            translation_key="not_supported",
        )

    cal_ent_obj = _get_calendar_entity_obj(hass, cal_entity)
    delete_fn = getattr(cal_ent_obj, "async_delete_event", None)
    if callable(delete_fn):
        await delete_fn(
            uid,
            recurrence_id=recurrence_id or None,
            recurrence_range=recurrence_range or None,
        )
    elif hass.services.has_service("calendar", "delete_event"):
        del_payload: dict[str, object] = {ATTR_ENTITY_ID: cal_entity, "uid": uid}
        if recurrence_id:
            del_payload["recurrence_id"] = recurrence_id
        if recurrence_range:
            del_payload["recurrence_range"] = recurrence_range
        await hass.services.async_call(
            "calendar", "delete_event", del_payload, blocking=True, context=Context()
        )
    else:
        raise ServiceValidationError(
            f"Calendar '{cal_entity}' does not support deleting events.",
            translation_domain=DOMAIN,
            translation_key="not_supported",
        )

    await coord.async_refresh_calendar_agenda()
    prev_win = coord.last_cal_window
    await async_push_calendar_window(
        hass,
        coord,
        start_date_raw=prev_win[0].isoformat() if prev_win else "",
        end_date_raw=prev_win[1].isoformat() if prev_win else "",
    )


_parse_bool = parse_bool
_parse_int = parse_int
_parse_opt_float = parse_opt_float
_resolve_coordinator_by_target = resolve_coordinator_by_target
_resolve_coordinator_from_call = resolve_coordinator_from_call
_require_admin_if_user_call = require_admin_if_user_call
resolve_occupied_area_ids = _resolve_occupied_area_ids
_is_coord_in_quiet_mode = is_coord_in_quiet_mode
async_execute_intercom_broadcast = _async_execute_intercom_broadcast
_async_push_calendar_window = async_push_calendar_window
