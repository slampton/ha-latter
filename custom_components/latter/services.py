"""Latter public user actions (5) and private bound-device `LatterRpcDispatcher` (20 RPCs)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import date, timedelta
import logging
import math
import re
import time
from typing import Any, NoReturn

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
    resolve_person_area_and_distance,
)
from .const import (
    ALL_RPC_METHODS,
    CONF_ALARM_ENTITY,
    CONF_BROADCAST_SPEAKERS,
    CONF_CUSTOM_PALETTES,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    DATA_GLOBAL_CONFIG,
    DOMAIN,
    RPC_AREA_ACTION,
    RPC_AREA_BROWSE,
    RPC_CALENDAR_CREATE_EVENT,
    RPC_CALENDAR_DELETE_EVENT,
    RPC_CALENDAR_FETCH,
    RPC_DEVICE_HELLO,
    RPC_DEVICE_TELEMETRY,
    RPC_DISPLAY_STATE,
    RPC_DOORBELL_INTERCOM,
    RPC_INTERCOM_BROADCAST,
    RPC_MEDIA_COMMAND,
    RPC_MEDIA_VOLUME,
    RPC_MUSIC_BROWSE,
    RPC_REMOTE_ACTION,
    RPC_SAVE_CUSTOM_COLOR,
    RPC_SET_ACTIVE_AREA,
    RPC_SET_ACTIVE_SPEAKER,
    RPC_SET_DEVICE_PREFS,
    RPC_SHORTCUT_ACTION,
    RPC_TIMER_ALARM_STATE,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_NOTIFY,
    SERVICE_RESET_DEVICE,
    SERVICE_SET_ACTIVE_AREA,
    SERVICE_SET_ACTIVE_SPEAKER,
    target_kind,
)
from .coordinator import LatterCoordinator, resolve_coordinator
from .doorbell import async_execute_doorbell_intercom
from .feeds import _discover_calendars, async_fetch_calendar_window
from .groups import async_reset_device
from .hub import (
    async_save_and_broadcast_global_config,
    get_latter_system,
    get_system_config_lock,
    iter_coordinators,
)
from .identity import device_entities, esphome_service
from .media import (
    async_announce_on_targets,
    async_execute_volume_action,
    async_fetch_and_push_music_lyrics,
    resolve_assist_satellite_entity,
    resolve_ma_counterpart_entity,
)
from .media_browse import async_browse_media_items
from .presence import get_ble_fabric
from .protocol import (
    SHORTCUT_DOMAIN_ACTION_SETS,
    PinLockoutTracker,
    PinWrapError,
    check_perimeter_action_allowed,
    is_sensitive_perimeter_action,
    is_valid_pin_digits,
    is_wrapped_pin_code,
    pack_calendar_window_chunks,
    unwrap_pin_code,
    utf8_safe_truncate,
)
from .remotes import async_execute_remote_action
from .repairs import slot_push_failing_issue_id

_LOGGER = logging.getLogger(__name__)

BASE_TARGET_FIELDS: dict[Any, Any] = {
    vol.Optional("target_device"): cv.string,
}

_SLOT_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f\u2028\u2029]+")
_RRULE_RE = re.compile(
    r"^FREQ=(?:DAILY|WEEKLY|MONTHLY|YEARLY)(?:;[A-Z_]+=[A-Za-z0-9,+-]+)*$"
)


def _clean_slot_text(raw: Any, max_chars: int, max_bytes: int | None = None) -> str:
    """Strip wire delimiters/control characters, cap character count, and truncate safely on UTF-8 boundaries."""
    cleaned = _SLOT_CONTROL_CHARS_RE.sub(" ", str(raw or ""))[:max_chars]
    byte_cap = max_bytes if max_bytes is not None else max(max_chars * 2, 255)
    return utf8_safe_truncate(cleaned, byte_cap)


def _parse_bool(val: Any, default: bool = False) -> bool:
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


def _parse_int(val: Any, default: int = 0) -> int:
    """Safely parse integer parameters without crashing on malformed strings."""
    if val is None or isinstance(val, bool):
        return default
    s = str(val).strip()
    if not s:
        return default
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return default


def _parse_opt_float(val: Any) -> float | None:
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


def _resolve_coordinator_by_target(
    hass: HomeAssistant, raw_target: Any
) -> LatterCoordinator:
    """Resolve the target LatterCoordinator strictly by target_device (or single-device default)."""
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


def _resolve_coordinator_from_call(
    hass: HomeAssistant, call: ServiceCall
) -> LatterCoordinator:
    """Resolve the target LatterCoordinator from a Home Assistant ServiceCall."""
    return _resolve_coordinator_by_target(hass, call.data.get("target_device"))


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


# ---------------------------------------------------------------------------
# PIN Session-Key Unwrapping, Lockout & Perimeter Security Policy (`M-P0-01`)
# ---------------------------------------------------------------------------

_ALARM_ACTION_ALIASES: dict[str, str] = {
    "disarm": "disarm",
    "alarm_disarm": "disarm",
    "arm_home": "arm_home",
    "alarm_arm_home": "arm_home",
    "arm_away": "arm_away",
    "alarm_arm_away": "arm_away",
    "arm_night": "arm_night",
    "alarm_arm_night": "arm_night",
    "arm_vacation": "arm_vacation",
    "alarm_arm_vacation": "arm_vacation",
}


def _get_system_pin_lockout(hass: HomeAssistant) -> PinLockoutTracker:
    """Return the System-wide `PinLockoutTracker` singleton."""
    sys_obj = get_latter_system(hass)
    if sys_obj is not None:
        return sys_obj.pin_lockout
    domain_data = hass.data.setdefault(DOMAIN, {})
    tracker = domain_data.get("_pin_lockout")
    if not isinstance(tracker, PinLockoutTracker):
        tracker = PinLockoutTracker()
        domain_data["_pin_lockout"] = tracker
    return tracker


def _check_pin_not_locked_out(
    hass: HomeAssistant, coord: LatterCoordinator
) -> None:
    """Raise `security_pin_locked_out` when either the Device or System lockout cooldown is active."""
    now_m = time.monotonic()
    sys_lockout = _get_system_pin_lockout(hass)
    if coord.pin_lockout.is_locked_out(
        coord.subentry_id, now=now_m
    ) or sys_lockout.is_locked_out("system", now=now_m):
        raise ServiceValidationError(
            "Too many failed security PIN attempts; temporarily locked out.",
            translation_domain=DOMAIN,
            translation_key="security_pin_locked_out",
        )


def _record_pin_failure_and_raise(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    err_key: str,
    detail: str,
) -> NoReturn:
    """Record a failed PIN attempt on Device + System trackers and raise the appropriate validation error."""
    now_m = time.monotonic()
    dev_rem = coord.pin_lockout.record_failure(coord.subentry_id, now=now_m)
    sys_rem = _get_system_pin_lockout(hass).record_failure("system", now=now_m)
    final_key = (
        "security_pin_locked_out"
        if (dev_rem > 0.0 or sys_rem > 0.0)
        else err_key
    )
    raise ServiceValidationError(
        detail,
        translation_domain=DOMAIN,
        translation_key=final_key,
    )


def _record_pin_success(hass: HomeAssistant, coord: LatterCoordinator) -> None:
    """Clear failure streaks on the calling Device and System lockout trackers after valid PIN verification."""
    coord.pin_lockout.record_success(coord.subentry_id)
    _get_system_pin_lockout(hass).record_success("system")


def _unwrap_rpc_pin_code(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    raw_entity_id: str,
    raw_action: str,
    raw_code: Any,
) -> str | None:
    """Unwrap an authenticated `v1:...` RPC PIN envelope, rejecting plaintext or replayed PINs (`M-P0-01`)."""
    code_str = str(raw_code or "").strip()
    if not code_str:
        return None
    _check_pin_not_locked_out(hass, coord)
    if (
        not is_wrapped_pin_code(code_str)
        or not coord._pin_key_id
        or not coord._pin_key_bytes
    ):
        _record_pin_failure_and_raise(
            hass,
            coord,
            "security_pin_invalid",
            f"Rejected unwrapped or unprovisioned security PIN from '{coord.device_slug}'.",
        )
    try:
        pin_digits, nonce = unwrap_pin_code(
            coord._pin_key_id,
            coord._pin_key_bytes,
            coord._pin_last_nonce,
            raw_entity_id.strip(),
            raw_action.strip(),
            code_str,
        )
    except PinWrapError as err:
        _record_pin_failure_and_raise(
            hass,
            coord,
            "security_pin_invalid",
            f"Rejected wrapped security PIN from '{coord.device_slug}' ({err.reason}): {err}",
        )
    coord._pin_last_nonce = nonce
    return pin_digits


async def _async_enforce_perimeter_security_policy(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    entity_id: str,
    action: str,
    *,
    level: int | float | None = None,
    provided_code: str | None = None,
) -> None:
    """Enforce the Device's Perimeter Security Policy and PIN lockout on sensitive opening actions."""
    raw_act = action.strip().lower()
    act = _ALARM_ACTION_ALIASES.get(raw_act, raw_act)
    resolved_ent = entity_id.strip()
    if resolved_ent == "home_hub.alarm" or (
        not resolved_ent
        and act in ("arm_home", "arm_away", "arm_night", "arm_vacation", "disarm")
    ):
        resolved_ent = coord.alarm_entity or ""
    if not resolved_ent or "." not in resolved_ent:
        return

    dom = resolved_ent.split(".", 1)[0].lower()
    st = hass.states.get(resolved_ent)

    if dom == "alarm_control_panel":
        eff_policy = coord.security_pin_policy
        code_fmt = (
            str(st.attributes.get("code_format") or "").strip().lower()
            if st is not None
            else ""
        )
        code_arm_req = (
            bool(st.attributes.get("code_arm_required", False))
            if st is not None
            else False
        )
        clean_code = str(provided_code or "").strip()

        if act == "disarm":
            if eff_policy == "block":
                raise ServiceValidationError(
                    f"Perimeter action '{act}' on '{resolved_ent}' denied (security_action_blocked).",
                    translation_domain=DOMAIN,
                    translation_key="security_action_blocked",
                )
            _check_pin_not_locked_out(hass, coord)
            if code_fmt:
                if not clean_code:
                    raise ServiceValidationError(
                        f"Alarm PIN required for '{act}' on '{resolved_ent}'.",
                        translation_domain=DOMAIN,
                        translation_key="security_pin_required",
                    )
                if code_fmt == "number" and not is_valid_pin_digits(clean_code):
                    _record_pin_failure_and_raise(
                        hass,
                        coord,
                        "security_pin_invalid",
                        f"Invalid alarm PIN format for '{act}' on '{resolved_ent}'.",
                    )
                return
            stored_alarm_hash = coord.security_pin_hash or None
            allowed, err_key = await hass.async_add_executor_job(
                lambda: check_perimeter_action_allowed(
                    eff_policy,
                    provided_code=provided_code,
                    stored_pin_hash=stored_alarm_hash,
                )
            )
            if not allowed:
                if err_key == "security_pin_invalid":
                    _record_pin_failure_and_raise(
                        hass,
                        coord,
                        err_key,
                        f"Perimeter action '{act}' on '{resolved_ent}' denied ({err_key}).",
                    )
                raise ServiceValidationError(
                    f"Perimeter action '{act}' on '{resolved_ent}' denied ({err_key}).",
                    translation_domain=DOMAIN,
                    translation_key=err_key,
                )
            if clean_code and stored_alarm_hash:
                _record_pin_success(hass, coord)
            return

        if act in ("arm_home", "arm_away", "arm_night", "arm_vacation"):
            if code_fmt and code_arm_req:
                _check_pin_not_locked_out(hass, coord)
                if not clean_code:
                    raise ServiceValidationError(
                        f"Alarm PIN required for '{act}' on '{resolved_ent}'.",
                        translation_domain=DOMAIN,
                        translation_key="security_pin_required",
                    )
                if code_fmt == "number" and not is_valid_pin_digits(clean_code):
                    _record_pin_failure_and_raise(
                        hass,
                        coord,
                        "security_pin_invalid",
                        f"Invalid alarm PIN format for '{act}' on '{resolved_ent}'.",
                    )
            return
        return

    dclass = str(st.attributes.get("device_class") or "") if st is not None else ""
    if not is_sensitive_perimeter_action(
        dom,
        act,
        device_class=dclass,
        entity_id=resolved_ent,
        level=int(level) if level is not None else None,
    ):
        return

    eff_pol = coord.security_pin_policy
    if eff_pol != "block":
        _check_pin_not_locked_out(hass, coord)
    stored_hash = coord.security_pin_hash or None
    allowed, err_key = await hass.async_add_executor_job(
        lambda: check_perimeter_action_allowed(
            eff_pol,
            provided_code=provided_code,
            stored_pin_hash=stored_hash,
        )
    )
    if not allowed:
        if err_key == "security_pin_invalid":
            _record_pin_failure_and_raise(
                hass,
                coord,
                err_key,
                f"Perimeter action '{act}' on '{resolved_ent}' denied ({err_key}).",
            )
        raise ServiceValidationError(
            f"Perimeter action '{act}' on '{resolved_ent}' denied ({err_key}).",
            translation_domain=DOMAIN,
            translation_key=err_key,
        )
    if provided_code and stored_hash:
        _record_pin_success(hass, coord)


# ---------------------------------------------------------------------------
# Shared Slot Push, Calendar Window & Quiet-Mode / Broadcast Helpers
# ---------------------------------------------------------------------------

_SLOT_PUSH_WARN_INTERVAL_S = 600.0
_SLOT_PUSH_REPAIR_THRESHOLD = 5


async def async_push_browse_slots(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    mode: str,
    page: int,
    page_size: int,
    items: list[dict[str, Any]],
    is_area_slots: bool = False,
    req_id: int = 0,
    *,
    total_items_override: int | None = None,
    items_offset: int = 0,
) -> None:
    """Paginate items and push them to the Device's bound esphome.<node>_latter_set_slots action."""
    device_slug = coord.device_slug
    esphome_action = esphome_service(hass, coord.esphome_device_id, "latter_set_slots")
    include_levels = is_area_slots and esphome_action is not None

    slot_capacity = (
        coord.card_slot_capacity if include_levels else coord.list_slot_capacity
    )
    eff_page_size = max(1, min(slot_capacity, int(page_size)))
    eff_offset = max(0, int(items_offset))
    total_items = (
        max(eff_offset + len(items), int(total_items_override))
        if total_items_override is not None and items
        else (eff_offset + len(items))
    )
    total_pages = max(1, math.ceil(total_items / eff_page_size))
    page = max(1, min(int(page), total_pages))
    start_idx = (page - 1) * eff_page_size
    local_start = max(0, start_idx - eff_offset)
    page_slice = items[local_start : local_start + eff_page_size]

    mode_low = str(mode).strip().lower()
    name_cap = 512 if mode_low in ("bio", "track_info", "lyrics") else 120
    packed_rows: list[str] = []
    for slot in page_slice:
        s_name = _clean_slot_text(
            slot.get("name", ""),
            name_cap,
            512 if name_cap >= 512 else 255,
        )
        s_id = _clean_slot_text(slot.get("id", ""), 255, 255)
        s_type = _clean_slot_text(slot.get("type", mode), 32, 64)
        s_act = 1 if bool(slot.get("active", False)) else 0
        s_lvl = _parse_int(slot.get("level"), -1) if include_levels else -1
        raw_qid = slot.get("queue_item_id")
        if raw_qid is not None or "is_current" in slot:
            s_qid = _clean_slot_text(raw_qid or "", 128, 128)
            s_cur = 1 if bool(slot.get("is_current", False)) else 0
            packed_rows.append(
                f"{s_name}\x1f{s_id}\x1f{s_type}\x1f{s_act}\x1f{s_lvl}\x1f{s_qid}\x1f{s_cur}"
            )
        else:
            packed_rows.append(f"{s_name}\x1f{s_id}\x1f{s_type}\x1f{s_act}\x1f{s_lvl}")

    payload: dict[str, Any] = {
        "is_area_slots": bool(is_area_slots),
        "req_id": max(0, int(req_id)),
        "mode": str(mode),
        "page": int(page),
        "total_pages": int(total_pages),
        "slots": "\x1e".join(packed_rows),
    }

    if esphome_action is None:
        _LOGGER.debug(
            "No ESPHome service matching *_latter_set_slots found (target slug '%s'); device is headless or offline.",
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
        if (
            now_m - last_warn_ts.get(fail_key, -_SLOT_PUSH_WARN_INTERVAL_S)
            >= _SLOT_PUSH_WARN_INTERVAL_S
        ):
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
                "error": utf8_safe_truncate(str(err), 160),
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
    """Return True if the target ESPHome device supports slot callbacks and has an online connection."""
    if esphome_service(hass, coord.esphome_device_id, "latter_set_slots") is None:
        return False
    if coord.radio_connected:
        return True
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
    """Push the active area's entity slots to esphome.<slug>_latter_set_slots when the device is online."""
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
        is_area_slots=True,
    )


def _is_coord_in_quiet_mode(coord: LatterCoordinator) -> bool:
    """Return True when a display Device is in Bedtime Mode or Do Not Disturb (`M-P1-22`)."""
    if coord.is_ble_tag or not coord.has_display:
        return False
    return bool(coord.get_device_pref("bedtime_active")) or coord.do_not_disturb


async def _async_execute_intercom_broadcast(
    hass: HomeAssistant,
    data: Mapping[str, Any],
    *,
    caller_subentry_id: str | None = None,
) -> dict[str, Any]:
    """Execute an intercom broadcast enforcing `D-074` speaker pools, caller anti-echo, and quiet modes (`M-P0-07`, `M-P1-22`)."""
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
    raw_target_speakers = data.get("target_speakers") or []
    explicit_speakers = (
        [str(s).strip() for s in raw_target_speakers if str(s or "").strip()]
        if isinstance(raw_target_speakers, (list, tuple, set))
        else (
            [s.strip() for s in str(raw_target_speakers).split(",") if s.strip()]
            if raw_target_speakers
            else []
        )
    )
    tts_entity = str(data.get("tts_entity") or "").strip()

    speakers = list(explicit_speakers)
    raw_target = str(data.get("target_device") or "").strip()
    target_low = raw_target.lower()
    kind = target_kind(raw_target)

    caller_coord: LatterCoordinator | None = None
    if caller_subentry_id:
        caller_coord = resolve_coordinator(hass, caller_subentry_id)
    if kind == "device":
        resolved_target_coord = _resolve_coordinator_by_target(hass, raw_target)
        if caller_coord is None:
            caller_coord = resolved_target_coord

    global_cfg = (hass.data.get(DOMAIN, {}) or {}).get(DATA_GLOBAL_CONFIG) or {}
    system_broadcast_speakers = [
        str(s).strip()
        for s in (global_cfg.get(CONF_BROADCAST_SPEAKERS) or [])
        if str(s or "").strip().startswith("media_player.")
    ]
    configured_pool = (
        caller_coord.effective_broadcast_speakers
        if caller_coord is not None
        else system_broadcast_speakers
    )

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    def _is_speaker_online(entity_id: str) -> bool:
        st_obj = hass.states.get(entity_id)
        return st_obj is not None and st_obj.state not in ("unavailable", "unknown")

    def _speaker_matches_coord(entity_id: str, coord: LatterCoordinator) -> bool:
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

    scoped_mode = kind in ("occupied_areas", "person")
    if scoped_mode and not explicit_speakers:
        if not configured_pool:
            raise ServiceValidationError(
                "No broadcast speakers are configured in Latter Studio.",
                translation_domain=DOMAIN,
                translation_key="no_broadcast_speakers",
            )
        occupied_areas = _resolve_occupied_area_ids(hass, kind, target_low)
        base_pool = [s for s in configured_pool if _is_speaker_online(s)]
        matched_speakers: list[str] = []
        seen_dev_ids: set[str] = set()
        if occupied_areas:
            for spk_id in base_pool:
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
    elif not speakers:
        if not configured_pool:
            raise ServiceValidationError(
                "No broadcast speakers are configured in Latter Studio.",
                translation_domain=DOMAIN,
                translation_key="no_broadcast_speakers",
            )
        speakers = [s for s in configured_pool if _is_speaker_online(s)]

    quiet_coords = [
        c for c in iter_coordinators(hass) if _is_coord_in_quiet_mode(c)
    ]
    if caller_coord is not None or (quiet_coords and not explicit_speakers):
        filtered_speakers: list[str] = []
        for spk_id in speakers:
            if caller_coord is not None and _speaker_matches_coord(
                spk_id, caller_coord
            ):
                continue
            if not explicit_speakers and any(
                _speaker_matches_coord(spk_id, qc) for qc in quiet_coords
            ):
                continue
            filtered_speakers.append(spk_id)
        speakers = filtered_speakers

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


def _is_calendar_writable(hass: HomeAssistant, cal_id: str) -> bool:
    st = hass.states.get(cal_id)
    if st is not None and "supported_features" in st.attributes:
        return (_parse_int(st.attributes.get("supported_features"), 0) & 1) != 0
    return True


def _is_calendar_deletable(hass: HomeAssistant, cal_id: str) -> bool:
    st = hass.states.get(cal_id)
    if st is not None and "supported_features" in st.attributes:
        return (_parse_int(st.attributes.get("supported_features"), 0) & 2) != 0
    return True


def _get_calendar_entity_obj(hass: HomeAssistant, cal_id: str) -> Any | None:
    comp = hass.data.get("calendar")
    if comp is not None and hasattr(comp, "get_entity"):
        return comp.get_entity(cal_id)
    return None


async def _async_push_calendar_window(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    *,
    req_id: int = 0,
    days: int = 30,
    start_date_raw: str = "",
    end_date_raw: str = "",
) -> None:
    today = dt_util.now().date()
    start_d = dt_util.parse_date(start_date_raw) if start_date_raw else None
    end_d = dt_util.parse_date(end_date_raw) if end_date_raw else None
    if start_d is None:
        start_d = today - timedelta(days=35)
    if end_d is None or end_d < start_d:
        end_d = today + timedelta(days=max(62, int(days or 30) + 7))
        if end_d < start_d:
            end_d = start_d + timedelta(days=62)
    if (end_d - start_d).days > 180:
        end_d = start_d + timedelta(days=180)
    coord._last_cal_window = (start_d, end_d)

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


# ---------------------------------------------------------------------------
# Private Bound-Device `LatterRpcDispatcher` (`M-P1-28`, Never on `hass.services`)
# ---------------------------------------------------------------------------


class LatterRpcDispatcher:
    """Private in-process dispatcher for all 20 authenticated bound-device RPC methods (`ALL_RPC_METHODS`)."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the private RPC dispatcher."""
        self.hass = hass

    async def async_dispatch(
        self,
        caller_coord: LatterCoordinator,
        rpc_method: str,
        raw_data: Mapping[str, Any] | None,
    ) -> Any:
        """Validate and execute a single bound-device RPC method directly against `caller_coord`."""
        method = str(rpc_method or "").strip()
        if method.startswith("latter."):
            method = method.split(".", 1)[1]
        if method not in ALL_RPC_METHODS:
            _LOGGER.warning(
                "Rejected unsupported RPC '%s' from device '%s'",
                method,
                caller_coord.device_slug,
            )
            return None

        data: dict[str, Any] = dict(raw_data) if isinstance(raw_data, Mapping) else {}

        if method == RPC_DEVICE_HELLO:
            return await self._rpc_device_hello(caller_coord, data)
        if method == RPC_DEVICE_TELEMETRY:
            caller_coord.apply_device_telemetry(data)
            return None
        if method == RPC_DISPLAY_STATE:
            caller_coord.apply_display_state(
                data.get("power_state"),
                data.get("brightness_pct"),
                data.get("screensaver_active"),
            )
            return None
        if method == RPC_MUSIC_BROWSE:
            return await self._rpc_music_browse(caller_coord, data)
        if method == RPC_SET_ACTIVE_SPEAKER:
            speaker = str(data.get("entity_id") or "").strip()
            transfer_queue = _parse_bool(data.get("transfer_queue"), default=True)
            if speaker:
                caller_coord.async_set_active_speaker(
                    speaker, transfer_queue=transfer_queue
                )
            return None
        if method == RPC_MEDIA_COMMAND:
            return await self._rpc_media_command(caller_coord, data)
        if method == RPC_MEDIA_VOLUME:
            return await self._rpc_media_volume(caller_coord, data)
        if method == RPC_AREA_BROWSE:
            return await self._rpc_area_browse(caller_coord, data)
        if method == RPC_AREA_ACTION:
            return await self._rpc_area_action(caller_coord, data)
        if method == RPC_SET_ACTIVE_AREA:
            area_val = str(data.get("area_id") or "").strip()
            if area_val:
                caller_coord.async_set_active_area(area_val, sync_device_registry=True)
            return None
        if method == RPC_REMOTE_ACTION:
            raw_slot = data.get("slot")
            slot_val = _parse_int(raw_slot, 1) if raw_slot is not None else None
            hold_val = _parse_opt_float(data.get("hold_secs"))
            if hold_val is not None:
                hold_val = max(0.0, min(5.0, hold_val))
            await async_execute_remote_action(
                self.hass,
                caller_coord,
                slot=slot_val,
                action=str(data.get("action") or ""),
                command=data.get("command"),
                hold_secs=hold_val,
            )
            return None
        if method == RPC_CALENDAR_FETCH:
            return await self._rpc_calendar_fetch(caller_coord, data)
        if method == RPC_CALENDAR_CREATE_EVENT:
            return await self._rpc_calendar_create_event(caller_coord, data)
        if method == RPC_CALENDAR_DELETE_EVENT:
            return await self._rpc_calendar_delete_event(caller_coord, data)
        if method == RPC_INTERCOM_BROADCAST:
            return await _async_execute_intercom_broadcast(
                self.hass,
                data,
                caller_subentry_id=caller_coord.subentry_id,
            )
        if method == RPC_DOORBELL_INTERCOM:
            return await self._rpc_doorbell_intercom(caller_coord, data)
        if method == RPC_SAVE_CUSTOM_COLOR:
            return await self._rpc_save_custom_color(caller_coord, data)
        if method == RPC_SHORTCUT_ACTION:
            return await self._rpc_shortcut_action(caller_coord, data)
        if method == RPC_SET_DEVICE_PREFS:
            base_seq = max(0, _parse_int(data.get("base_seq"), 0))
            changes = str(data.get("changes") or "")
            await caller_coord.async_handle_set_device_prefs(
                base_seq=base_seq, changes_raw=changes
            )
            return None
        if method == RPC_TIMER_ALARM_STATE:
            caller_coord.handle_timer_alarm_state(
                timer_running=_parse_bool(data.get("timer_running"), default=False),
                timer_paused=_parse_bool(data.get("timer_paused"), default=False),
                remaining_sec=max(0, _parse_int(data.get("remaining_sec"), 0)),
                ringing=_parse_bool(data.get("ringing"), default=False),
                stopwatch_running=_parse_bool(
                    data.get("stopwatch_running"), default=False
                ),
                stopwatch_paused=_parse_bool(
                    data.get("stopwatch_paused"), default=False
                ),
                stopwatch_elapsed_sec=max(
                    0, _parse_int(data.get("stopwatch_elapsed_sec"), 0)
                ),
            )
            return None
        return None

    async def _rpc_device_hello(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> None:
        contract = _parse_int(data.get("contract"), 3)
        if contract != 3:
            _LOGGER.warning(
                "Device '%s' reported unsupported Protocol contract %d (expected 3)",
                coord.device_slug,
                contract,
            )
        boot_id = str(data.get("boot_id") or "").strip()
        manifest_raw = str(data.get("manifest") or "").strip()
        prefs_seq = max(0, _parse_int(data.get("prefs_seq"), 0))
        dirty_prefs = str(data.get("dirty_prefs") or "")
        await coord.async_handle_device_hello(
            boot_id=boot_id,
            manifest_raw=manifest_raw,
            prefs_seq=prefs_seq,
            dirty_prefs=dirty_prefs,
        )

    async def _rpc_media_command(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> None:
        command = str(data.get("command") or "toggle")
        speaker = data.get("entity_id")
        seek_pos = _parse_opt_float(data.get("seek_position"))
        media_id = str(data.get("media_id") or "").strip() or None
        media_type = str(data.get("media_type") or "").strip() or None
        enqueue = str(data.get("enqueue") or "").strip() or None
        radio_mode = _parse_bool(data.get("radio_mode"), default=False)
        queue_item_id = str(data.get("queue_item_id") or "").strip() or None
        raw_shift = data.get("pos_shift")
        pos_shift: int | str | None = (
            raw_shift
            if raw_shift is not None and str(raw_shift).strip() != ""
            else None
        )
        group_members = data.get("group_members")

        await coord.async_execute_media_command(
            command=command,
            speaker=str(speaker) if speaker else None,
            seek_position=seek_pos,
            media_id=media_id,
            media_type=media_type,
            enqueue=enqueue,
            group_members=group_members,
            radio_mode=radio_mode,
            queue_item_id=queue_item_id,
            pos_shift=pos_shift,
        )

    async def _rpc_media_volume(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> None:
        speaker = str(data.get("entity_id") or coord.active_speaker).strip()
        if not speaker:
            return
        vol_target = coord.get_volume_target_entity(speaker)
        action = str(data.get("action") or "set").strip().lower()
        parsed_pct = _parse_opt_float(data.get("volume_level"))
        if parsed_pct is not None and parsed_pct < 0.0:
            parsed_pct = None
        await async_execute_volume_action(
            self.hass, vol_target, action, volume_pct=parsed_pct
        )

    async def _rpc_music_browse(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> None:
        req_id = max(0, _parse_int(data.get("req_id"), 0))
        mode = str(data.get("mode") or "speakers")
        page = max(1, _parse_int(data.get("page"), 1))
        page_size = _parse_int(data.get("page_size"), coord.list_slot_capacity)
        local_speaker = coord.local_speaker
        speaker = str(data.get("speaker") or coord.active_speaker or local_speaker)
        last_speaker = str(data.get("last_speaker") or coord.last_speaker or speaker)
        search = str(data.get("search") or "")
        album_sort = str(data.get("album_sort") or "name")
        artist_album_sort = str(data.get("artist_album_sort") or "year")
        podcast_sort = str(data.get("podcast_sort") or "newest")

        mode_norm = mode.strip().lower()
        if mode_norm == "lyrics_fetch":
            max_lines = max(1, min(128, _parse_int(data.get("page_size"), 128)))
            await async_fetch_and_push_music_lyrics(
                self.hass,
                coord,
                req_id=req_id,
                speaker=speaker,
                search=search,
                max_lines=max_lines,
            )
            return

        eff_ps = max(1, min(coord.list_slot_capacity, page_size))
        queue_offset = (
            ((max(1, page) - 1) * eff_ps // 50) * 50
            if mode_norm == "active_queue"
            else 0
        )
        items = await async_browse_media_items(
            hass=self.hass,
            mode=mode,
            speaker=speaker,
            last_speaker=last_speaker,
            local_speaker=local_speaker,
            search=search,
            default_speaker=str(coord.get_opt(CONF_DEFAULT_SPEAKER) or ""),
            album_sort=album_sort,
            artist_album_sort=artist_album_sort,
            podcast_sort=podcast_sort,
            fallback_title=coord.last_media_title,
            fallback_artist=coord.last_media_artist,
            fallback_album=coord.last_media_album,
            offset=queue_offset,
        )
        total_items_override: int | None = None
        if mode_norm == "active_queue":
            if queue_offset > 0 and not items:
                queue_offset = 0
                items = await async_browse_media_items(
                    hass=self.hass,
                    mode=mode,
                    speaker=speaker,
                    last_speaker=last_speaker,
                    local_speaker=local_speaker,
                    search=search,
                    default_speaker=str(coord.get_opt(CONF_DEFAULT_SPEAKER) or ""),
                    album_sort=album_sort,
                    artist_album_sort=artist_album_sort,
                    podcast_sort=podcast_sort,
                    fallback_title=coord.last_media_title,
                    fallback_artist=coord.last_media_artist,
                    fallback_album=coord.last_media_album,
                    offset=0,
                )
            ma_target = (
                resolve_ma_counterpart_entity(self.hass, speaker) if speaker else None
            )
            if ma_target and items:
                q_counts = self.hass.data.get(DOMAIN, {}).get("_ma_queue_counts", {})
                raw_q_total = q_counts.get(ma_target)
                if (
                    isinstance(raw_q_total, int)
                    and raw_q_total > 0
                    and (len(items) > 2 or raw_q_total <= len(items))
                ):
                    total_items_override = raw_q_total
        if mode_norm == "lyrics":
            await async_fetch_and_push_music_lyrics(
                self.hass,
                coord,
                req_id=0,
                speaker=speaker,
                search=search,
            )
        if mode_norm in ("album_tracks", "current_album_tracks"):
            coord._browsed_album_track_uris = [
                str(it["id"])
                for it in items
                if isinstance(it, dict) and it.get("type") == "track" and it.get("id")
            ]
        elif mode_norm not in (
            "speakers",
            "lyrics",
            "lyrics_fetch",
            "bio",
            "track_info",
        ):
            coord._browsed_album_track_uris = []
        if not items and mode != "speakers":
            queue_offset = 0
            items = [
                {
                    "name": "No items found",
                    "id": "",
                    "type": "text",
                    "active": False,
                }
            ]

        await async_push_browse_slots(
            hass=self.hass,
            coord=coord,
            mode=mode,
            page=page,
            page_size=page_size,
            items=items,
            is_area_slots=False,
            req_id=req_id,
            total_items_override=total_items_override,
            items_offset=queue_offset,
        )

    async def _rpc_area_browse(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> None:
        req_id = max(0, _parse_int(data.get("req_id"), 0))
        mode = str(data.get("mode") or "entities").strip().lower()
        page = max(1, _parse_int(data.get("page"), 1))
        default_ps = (
            coord.list_slot_capacity if mode == "areas" else coord.card_slot_capacity
        )
        page_size = _parse_int(data.get("page_size"), default_ps)
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
                self.hass,
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
                self.hass,
                active_area_id=coord.active_area_id,
                local_speaker=local_speaker,
            )
            slot_mode = "area_areas"
        elif mode == "home":
            items = get_home_wide_entities(
                self.hass,
                configured_alarm_entity=coord.get_opt(CONF_ALARM_ENTITY),
            )
            slot_mode = "area_home"
        elif not domain_filter:
            items = []
            slot_mode = "area_empty"
        else:
            items = get_area_entities(
                self.hass,
                area_id=eff_area_id,
                domain_filter=domain_filter,
                local_speaker=local_speaker,
            )
            slot_mode = f"area_{domain_filter}"

        is_area = mode != "areas"
        await async_push_browse_slots(
            hass=self.hass,
            coord=coord,
            mode=slot_mode,
            page=page,
            page_size=page_size,
            items=items,
            is_area_slots=is_area,
            req_id=req_id,
        )

    async def _rpc_area_action(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> None:
        area_id = data.get("area_id")
        if area_id and str(area_id) != coord.active_area_id:
            coord.async_set_active_area(
                str(area_id),
                handoff_media=False,
                sync_device_registry=False,
            )

        raw_entity_id = str(data.get("entity_id") or "").strip()
        raw_action_wire = str(data.get("action") or "").strip()
        raw_action = raw_action_wire.lower()
        action = _ALARM_ACTION_ALIASES.get(raw_action, raw_action)

        raw_code = data.get("code")
        code: str | None
        if raw_action == "set_color":
            code = (
                str(raw_code).strip() or None if raw_code is not None else None
            )
        else:
            code = _unwrap_rpc_pin_code(
                self.hass, coord, raw_entity_id, raw_action_wire, raw_code
            )

        entity_id = raw_entity_id
        if entity_id == "home_hub.alarm" or (
            not entity_id
            and action
            in ("arm_home", "arm_away", "arm_night", "arm_vacation", "disarm")
        ):
            entity_id = coord.alarm_entity or ""

        if not entity_id:
            return

        level: int | float | None = None
        f_lvl = _parse_opt_float(data.get("level"))
        if f_lvl is not None:
            if action == "set_temperature" or entity_id.startswith("climate."):
                level = f_lvl
            else:
                level = round(f_lvl)

        await _async_enforce_perimeter_security_policy(
            self.hass,
            coord,
            entity_id,
            action,
            level=level,
            provided_code=code,
        )
        await async_execute_area_action(
            self.hass,
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
        await async_push_active_area_entities(self.hass, coord)

    async def _rpc_calendar_fetch(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> None:
        req_id = max(0, _parse_int(data.get("req_id"), 0))
        days = max(1, min(60, _parse_int(data.get("days"), 30)))
        sys_obj = get_latter_system(self.hass)
        if sys_obj is not None:
            await sys_obj.async_refresh_calendar_agenda(days=30, coalesce=True)
        else:
            await coord.async_refresh_calendar_agenda(days=30)

        await _async_push_calendar_window(
            self.hass,
            coord,
            req_id=req_id,
            days=days,
            start_date_raw=str(data.get("start_date") or "").strip(),
            end_date_raw=str(data.get("end_date") or "").strip(),
        )

    async def _rpc_calendar_create_event(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> None:
        valid_cals = _discover_calendars(self.hass, coord.calendar_entities)
        requested_cal = str(data.get("calendar_entity") or "").strip()
        if requested_cal:
            if requested_cal not in valid_cals or not _is_calendar_writable(
                self.hass, requested_cal
            ):
                raise ServiceValidationError(
                    f"Calendar '{requested_cal}' is not writable or not configured for this Site.",
                    translation_domain=DOMAIN,
                    translation_key="not_supported",
                )
            cal_entity = requested_cal
        else:
            cal_entity = next(
                (c for c in valid_cals if _is_calendar_writable(self.hass, c)),
                "",
            )

        cal_ent_obj = (
            _get_calendar_entity_obj(self.hass, cal_entity) if cal_entity else None
        )
        if not cal_entity or (
            cal_ent_obj is None
            and not self.hass.services.has_service("calendar", "create_event")
        ):
            _LOGGER.warning(
                "No writable calendar entity found for calendar_create_event."
            )
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

        is_all_day = _parse_bool(data.get("all_day"), default=False) or (
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
            dtstart_val: Any = sd
            dtend_val: Any = ed
        else:
            raw_sdt = str(data.get("start_date_time") or "").strip()
            raw_edt = str(data.get("end_date_time") or "").strip()
            parsed_s = dt_util.parse_datetime(raw_sdt) if raw_sdt else None
            parsed_e = dt_util.parse_datetime(raw_edt) if raw_edt else None
            if parsed_s is not None:
                start_dt = (
                    dt_util.as_local(parsed_s)
                    if parsed_s.tzinfo is not None
                    else parsed_s.replace(tzinfo=now_local.tzinfo)
                )
            else:
                rem = 15 - (now_local.minute % 15)
                start_dt = now_local + timedelta(minutes=rem)
            if parsed_e is not None:
                end_dt = (
                    dt_util.as_local(parsed_e)
                    if parsed_e.tzinfo is not None
                    else parsed_e.replace(tzinfo=now_local.tzinfo)
                )
            else:
                end_dt = start_dt + timedelta(minutes=60)
            if end_dt <= start_dt:
                end_dt = start_dt + timedelta(minutes=60)
            dtstart_val = start_dt
            dtend_val = end_dt

        if (
            rrule
            and cal_ent_obj is not None
            and callable(getattr(cal_ent_obj, "async_create_event", None))
        ):
            rfc_kwargs: dict[str, Any] = {
                "dtstart": dtstart_val,
                "dtend": dtend_val,
                "summary": summary,
                "rrule": rrule,
            }
            if location:
                rfc_kwargs["location"] = location
            if description:
                rfc_kwargs["description"] = description
            await cal_ent_obj.async_create_event(**rfc_kwargs)
        else:
            payload: dict[str, Any] = {
                ATTR_ENTITY_ID: cal_entity,
                "summary": summary,
            }
            if is_all_day:
                payload["start_date"] = dtstart_val.isoformat()
                payload["end_date"] = dtend_val.isoformat()
            else:
                payload["start_date_time"] = dtstart_val.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                payload["end_date_time"] = dtend_val.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            if location:
                payload["location"] = location
            if description:
                payload["description"] = description
            await self.hass.services.async_call(
                "calendar",
                "create_event",
                payload,
                blocking=True,
                context=Context(),
            )

        await coord.async_refresh_calendar_agenda()
        prev_win: tuple[date, date] | None = getattr(
            coord, "_last_cal_window", None
        )
        await _async_push_calendar_window(
            self.hass,
            coord,
            start_date_raw=prev_win[0].isoformat() if prev_win else "",
            end_date_raw=prev_win[1].isoformat() if prev_win else "",
        )

    async def _rpc_calendar_delete_event(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> None:
        cal_entity = str(data.get("calendar_entity") or "").strip()
        uid = str(data.get("uid") or "").strip()
        recurrence_id = str(data.get("recurrence_id") or "").strip()
        recurrence_range = str(data.get("recurrence_range") or "").strip()

        valid_cals = _discover_calendars(self.hass, coord.calendar_entities)
        if (
            not cal_entity
            or not uid
            or cal_entity not in valid_cals
            or not _is_calendar_deletable(self.hass, cal_entity)
        ):
            raise ServiceValidationError(
                f"Calendar '{cal_entity or '(empty)'}' does not support deleting events.",
                translation_domain=DOMAIN,
                translation_key="not_supported",
            )

        cal_ent_obj = _get_calendar_entity_obj(self.hass, cal_entity)
        if cal_ent_obj is not None and callable(
            getattr(cal_ent_obj, "async_delete_event", None)
        ):
            await cal_ent_obj.async_delete_event(
                uid,
                recurrence_id=recurrence_id or None,
                recurrence_range=recurrence_range or None,
            )
        elif self.hass.services.has_service("calendar", "delete_event"):
            del_payload: dict[str, Any] = {
                ATTR_ENTITY_ID: cal_entity,
                "uid": uid,
            }
            if recurrence_id:
                del_payload["recurrence_id"] = recurrence_id
            if recurrence_range:
                del_payload["recurrence_range"] = recurrence_range
            await self.hass.services.async_call(
                "calendar",
                "delete_event",
                del_payload,
                blocking=True,
                context=Context(),
            )
        else:
            raise ServiceValidationError(
                f"Calendar '{cal_entity}' does not support deleting events.",
                translation_domain=DOMAIN,
                translation_key="not_supported",
            )

        await coord.async_refresh_calendar_agenda()
        prev_win: tuple[date, date] | None = getattr(
            coord, "_last_cal_window", None
        )
        await _async_push_calendar_window(
            self.hass,
            coord,
            start_date_raw=prev_win[0].isoformat() if prev_win else "",
            end_date_raw=prev_win[1].isoformat() if prev_win else "",
        )

    async def _rpc_doorbell_intercom(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> dict[str, Any]:
        action = str(data.get("action") or "listen_toggle").strip()
        cam_ent = str(data.get("camera_entity") or "").strip() or None
        msg = str(data.get("message") or "").strip()
        nr_level = str(data.get("noise_reduction") or "").strip() or None
        raw_idx = data.get("camera_index")
        cam_idx: int | None = None
        if raw_idx is not None and str(raw_idx).strip() != "":
            cam_idx = _parse_int(raw_idx, 0)
        info = await async_execute_doorbell_intercom(
            hass=self.hass,
            coordinator=coord,
            action=action,
            camera_entity=cam_ent,
            message=msg,
            noise_reduction=nr_level,
            camera_index=cam_idx,
        )
        return {
            "status": "ok",
            "device_slug": coord.device_slug,
            "action": action,
            "doorbell_talk_state": coord.doorbell_talk_state,
            "doorbell_noise_reduction": coord.doorbell_noise_reduction,
            **info,
        }

    async def _rpc_save_custom_color(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> None:
        raw_hex = str(data.get("hex_color") or "").strip().upper()
        if not raw_hex.startswith("#"):
            raw_hex = f"#{raw_hex}"
        if not re.fullmatch(r"#[0-9A-F]{6}", raw_hex):
            raise ServiceValidationError(
                f"Invalid hex color '{raw_hex}' (expected #RRGGBB).",
                translation_domain=DOMAIN,
                translation_key="invalid_hex_color",
                translation_placeholders={"hex_color": raw_hex},
            )
        name = str(data.get("name") or f"Custom ({raw_hex})").strip()

        coord.update_device_config(
            {
                **coord.device_data,
                CONF_DEVICE_CUSTOM_COLOR: raw_hex,
                "color_profile": "Custom",
            }
        )
        async with get_system_config_lock(self.hass):
            domain_data = self.hass.data.setdefault(DOMAIN, {})
            global_cfg: dict[str, Any] = domain_data.setdefault(
                DATA_GLOBAL_CONFIG, {}
            )
            palettes: list[dict[str, str]] = [
                dict(p)
                for p in (global_cfg.get(CONF_CUSTOM_PALETTES) or [])
                if isinstance(p, dict)
            ]
            existing = next(
                (
                    p
                    for p in palettes
                    if str(p.get("hex", "")).upper() == raw_hex
                ),
                None,
            )
            if existing is not None:
                if data.get("name"):
                    existing["name"] = name
            else:
                palettes.insert(0, {"name": name, "hex": raw_hex})
                palettes = palettes[:24]
            await async_save_and_broadcast_global_config(
                self.hass, {CONF_CUSTOM_PALETTES: palettes}
            )

    async def _rpc_shortcut_action(
        self, coord: LatterCoordinator, data: dict[str, Any]
    ) -> None:
        raw_entity_id = str(data.get("entity_id") or "").strip()
        raw_action_wire = str(data.get("action") or "").strip()
        entity_id = raw_entity_id.lower()
        action = raw_action_wire.lower()
        code = _unwrap_rpc_pin_code(
            self.hass,
            coord,
            raw_entity_id,
            raw_action_wire,
            data.get("code"),
        )

        allowed_pairs = {
            (str(sc.get("target") or "").lower(), str(sc.get("action") or "").lower())
            for sc_list in (coord.dock_items, coord.pinned_items)
            for sc in sc_list
            if sc.get("kind") == "entity"
        }
        domain = entity_id.split(".", 1)[0] if "." in entity_id else ""
        if (
            (entity_id, action) not in allowed_pairs
            or domain not in SHORTCUT_DOMAIN_ACTION_SETS
            or action not in SHORTCUT_DOMAIN_ACTION_SETS[domain]
        ):
            raise ServiceValidationError(
                f"Shortcut ({entity_id}, {action}) is not configured on {coord.device_title}.",
                translation_domain=DOMAIN,
                translation_key="shortcut_not_configured",
                translation_placeholders={
                    "entity_id": entity_id or "(empty)",
                    "action": action or "(empty)",
                },
            )

        await _async_enforce_perimeter_security_policy(
            self.hass,
            coord,
            entity_id=entity_id,
            action=action,
            provided_code=code,
        )
        await async_execute_area_action(
            self.hass,
            entity_id=entity_id,
            action=action,
            code=code,
        )


def get_rpc_dispatcher(hass: HomeAssistant) -> LatterRpcDispatcher:
    """Return the active `LatterRpcDispatcher` on `LatterSystemHub` (or a domain-level singleton in unit tests)."""
    sys_obj = get_latter_system(hass)
    if sys_obj is not None:
        return sys_obj.rpc_dispatcher
    domain_data = hass.data.setdefault(DOMAIN, {})
    dispatcher = domain_data.get("_rpc_dispatcher")
    if not isinstance(dispatcher, LatterRpcDispatcher):
        dispatcher = LatterRpcDispatcher(hass)
        domain_data["_rpc_dispatcher"] = dispatcher
    return dispatcher


async def async_dispatch_bound_rpc(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    service_name: str,
    data: Mapping[str, Any] | None,
) -> Any:
    """Dispatch a reassembled RPC from `coord`'s bound `System: RPC Outbox` entity via `LatterRpcDispatcher`."""
    return await get_rpc_dispatcher(hass).async_dispatch(
        coord, service_name, data
    )


# ---------------------------------------------------------------------------
# Public User Service Registration (`PUBLIC_SERVICES` — 5 Actions Only)
# ---------------------------------------------------------------------------


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register ONLY the 5 public Latter user actions on `hass.services` (`M-P1-28`)."""
    if hass.services.has_service(DOMAIN, SERVICE_NOTIFY):
        return

    async def _handle_set_active_speaker(call: ServiceCall) -> None:
        speaker = str(call.data.get("entity_id") or "").strip()
        transfer_queue = _parse_bool(call.data.get("transfer_queue"), default=True)
        coord = _resolve_coordinator_from_call(hass, call)
        if speaker:
            coord.async_set_active_speaker(speaker, transfer_queue=transfer_queue)

    async def _handle_set_active_area(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        area_val = str(call.data.get("area_id") or "").strip()
        if area_val:
            coord.async_set_active_area(area_val, sync_device_registry=True)

    async def _handle_intercom_broadcast(call: ServiceCall) -> ServiceResponse:
        return await _async_execute_intercom_broadcast(hass, call.data)

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

        title = str(data.get("title") or "Notification").strip() or "Notification"
        message = str(data.get("message") or "").strip()
        priority = str(data.get("priority") or "normal").strip().lower()
        duration = max(2, min(60, _parse_int(data.get("duration"), 8)))
        chime = _parse_bool(data.get("chime"), default=True)
        is_announce = _parse_bool(data.get("announce"), default=False)
        card_chime = False if is_announce else chime
        cam_ent = str(data.get("camera_entity") or "").strip() or None

        for coord in target_coords:
            in_bedtime = bool(
                not coord.is_ble_tag
                and coord.has_display
                and coord.get_device_pref("bedtime_active")
            )
            in_dnd = bool(
                not coord.is_ble_tag and coord.has_display and coord.do_not_disturb
            )
            if in_dnd and priority in ("normal", "warning"):
                continue

            suppress_quiet = (in_bedtime and priority != "critical") or (
                in_dnd and bool(cam_ent)
            )
            coord_chime = False if suppress_quiet else card_chime
            coord.async_dispatch_notification(
                title=title,
                message=message,
                priority=priority,
                duration=duration,
                chime=coord_chime,
                camera_entity=cam_ent,
            )

            esp_notify_svc = esphome_service(
                hass, coord.esphome_device_id, "latter_show_notification"
            )
            if esp_notify_svc:
                try:
                    await hass.services.async_call(
                        "esphome",
                        esp_notify_svc,
                        {
                            "title": utf8_safe_truncate(title, 48),
                            "message": utf8_safe_truncate(message, 160),
                            "priority": priority,
                            "duration": duration,
                            "chime": coord_chime,
                            "camera_url": coord.alert_camera_url,
                            "camera_entity": coord.alert_camera_entity,
                            "alert_id": coord.alert_id,
                        },
                        blocking=True,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug(
                        "Direct esphome.%s call skipped: %s", esp_notify_svc, err
                    )

            if is_announce and message and not suppress_quiet and not in_dnd:
                sat_ent = resolve_assist_satellite_entity(
                    hass, coord.local_speaker, coord
                )
                target_list = (
                    [sat_ent]
                    if sat_ent
                    else ([coord.local_speaker] if coord.local_speaker else [])
                )
                if target_list:
                    await async_announce_on_targets(
                        hass,
                        speakers=target_list,
                        message=message,
                        blocking=False,
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
        SERVICE_NOTIFY,
        _handle_notify,
        schema=vol.Schema(
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
        ),
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
        SERVICE_SET_ACTIVE_SPEAKER,
        _handle_set_active_speaker,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Required("entity_id"): cv.string,
                vol.Optional("transfer_queue", default=True): vol.Any(
                    bool, cv.string
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_DEVICE,
        _handle_reset_device,
        schema=vol.Schema(
            {
                vol.Required("target_device"): vol.All(
                    cv.string, vol.Strip, vol.Length(min=1)
                ),
                vol.Optional("device_settings", default=True): cv.boolean,
                vol.Optional("latter_options", default=True): cv.boolean,
            }
        ),
    )
