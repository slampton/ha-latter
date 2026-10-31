"""Service registration for Latter (Universal ESPHome Pagination, Area Control, BLE Area Sync, TV Remote, Trigger Bindings, Calendar, Intercom)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import math
from typing import Any
import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import dt as dt_util

from .browse_engine import async_browse_media_items, is_music_assistant_player
from .calendar_engine import async_fetch_calendar_agenda
from .const import (
    CONF_ALARM_ENTITY,
    DEFAULT_PAGE_SIZE,
    DOMAIN,
    SERVICE_CALENDAR_CREATE_EVENT,
    SERVICE_CALENDAR_FETCH,
    SERVICE_DOORBELL_INTERCOM,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_MEDIA_COMMAND,
    SERVICE_MEDIA_VOLUME,
    SERVICE_MUSIC_BROWSE,
    SERVICE_NOTIFY,
    SERVICE_NOTIFY_DEVICE,
    SERVICE_REMOTE_ACTION,
    CONF_CUSTOM_PALETTES,
    CONF_DEVICE_CUSTOM_COLOR,
    DATA_GLOBAL_CONFIG,
    DATA_GLOBAL_STORE,
    SERVICE_AREA_ACTION,
    SERVICE_AREA_BROWSE,
    SERVICE_SAVE_CUSTOM_COLOR,
    SERVICE_SET_ACTIVE_AREA,
    SERVICE_SET_ACTIVE_SPEAKER,
    SERVICE_TRIGGER_BINDING,
    normalize_device_slug,
)
from .coordinator import LatterCoordinator, resolve_coordinator
from .area_engine import (
    async_execute_area_action,
    get_area_entities,
    get_areas_summary,
    get_home_wide_entities,
)

_LOGGER = logging.getLogger(__name__)

CANONICAL_NAV_INTENT: dict[str, str] = {
    "up": "up",
    "dpad_up": "up",
    "cursor_up": "up",
    "down": "down",
    "dpad_down": "down",
    "cursor_down": "down",
    "left": "left",
    "dpad_left": "left",
    "cursor_left": "left",
    "right": "right",
    "dpad_right": "right",
    "cursor_right": "right",
    "select": "select",
    "enter": "select",
    "ok": "select",
    "dpad_center": "select",
    "key_enter": "select",
    "back": "back",
    "return": "back",
    "key_return": "back",
    "home": "home",
    "top_menu": "home",
    "key_home": "home",
    "menu": "menu",
    "info": "info",
    "option": "option",
    "exit": "exit",
    "play": "play",
    "pause": "pause",
}

ANDROIDTV_COMMAND_MAP: dict[str, str] = {
    "up": "DPAD_UP",
    "down": "DPAD_DOWN",
    "left": "DPAD_LEFT",
    "right": "DPAD_RIGHT",
    "select": "DPAD_CENTER",
    "back": "BACK",
    "home": "HOME",
    "menu": "MENU",
    "info": "INFO",
    "play": "MEDIA_PLAY",
    "pause": "MEDIA_PAUSE",
}

STANDARD_REMOTE_COMMAND_MAP: dict[str, str] = {
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "select": "select",
    "back": "back",
    "home": "home",
    "menu": "menu",
    "info": "info",
}

DENONAVR_COMMAND_MAP: dict[str, str] = {
    "up": "/goform/formiPhoneAppDirect.xml?MNCUP",
    "down": "/goform/formiPhoneAppDirect.xml?MNCDN",
    "left": "/goform/formiPhoneAppDirect.xml?MNCLT",
    "right": "/goform/formiPhoneAppDirect.xml?MNCRT",
    "select": "/goform/formiPhoneAppDirect.xml?MNENT",
    "back": "/goform/formiPhoneAppDirect.xml?MNRTN",
    "home": "/goform/formiPhoneAppDirect.xml?MNMEN%20ON",
    "menu": "/goform/formiPhoneAppDirect.xml?MNMEN%20ON",
    "info": "/goform/formiPhoneAppDirect.xml?MNINF",
    "option": "/goform/formiPhoneAppDirect.xml?MNOPT",
}

WEBOSTV_BUTTON_MAP: dict[str, str] = {
    "up": "UP",
    "down": "DOWN",
    "left": "LEFT",
    "right": "RIGHT",
    "select": "ENTER",
    "back": "BACK",
    "home": "HOME",
    "menu": "MENU",
    "info": "INFO",
    "exit": "EXIT",
    "play": "PLAY",
    "pause": "PAUSE",
}

BASE_TARGET_FIELDS: dict[Any, Any] = {
    vol.Optional("target_device"): cv.string,
    vol.Optional("device_slug"): cv.string,
    vol.Optional("device_id"): vol.Any(cv.string, [cv.string]),
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
) -> LatterCoordinator | None:
    """Resolve the target LatterCoordinator by target_device, device_slug, HA device_id, or single-instance fallback."""
    raw_slug = call.data.get("device_slug") or call.data.get("target_device")
    if raw_slug:
        matched = resolve_coordinator(hass, str(raw_slug), allow_fallback=False)
        if matched is not None:
            return matched

    raw_dev_id = call.data.get("device_id")
    if raw_dev_id:
        dev_id = raw_dev_id[0] if isinstance(raw_dev_id, list) else str(raw_dev_id)
        matched = resolve_coordinator(hass, dev_id, allow_fallback=False)
        if matched is not None:
            return matched
        dev = dr.async_get(hass).async_get(dev_id)
        if dev:
            for _dom, ident in dev.identifiers:
                matched = resolve_coordinator(hass, ident, allow_fallback=False)
                if matched is not None:
                    return matched
            dev_name = str(dev.name_by_user or dev.name or "")
            if dev_name:
                matched = resolve_coordinator(hass, dev_name, allow_fallback=False)
                if matched is not None:
                    return matched

    return resolve_coordinator(hass, None, allow_fallback=True)


def _resolve_esphome_action(
    hass: HomeAssistant, device_slug: str, suffix: str
) -> str | None:
    """Resolve the registered esphome.<device_slug>_<suffix> service name strictly for the target device."""
    esphome_services = hass.services.async_services().get("esphome", {})
    exact = f"{device_slug}_{suffix}"
    if exact in esphome_services:
        return exact

    for svc_name in esphome_services:
        if svc_name.endswith(f"_{suffix}") and device_slug in svc_name:
            return svc_name

    return None


def _detect_esphome_slot_capacity(
    hass: HomeAssistant, esphome_action: str | None, default_slots: int = 5
) -> tuple[int, bool]:
    """Inspect the ESPHome service schema and return (slot_capacity, is_contract_v3)."""
    if not esphome_action:
        return default_slots, False
    try:
        esphome_services = hass.services.async_services().get("esphome", {})
        svc_obj = esphome_services.get(esphome_action)
        schema = getattr(svc_obj, "schema", None)
        if schema is not None and hasattr(schema, "schema") and isinstance(schema.schema, dict):
            keys = {str(k) for k in schema.schema}
            if "slots" in keys:
                return default_slots, True
            max_slot = 0
            for idx in range(1, 21):
                if f"s{idx}_name" in keys:
                    max_slot = idx
            if max_slot > 0:
                return max_slot, False
    except Exception:  # noqa: BLE001
        pass
    return default_slots, False


async def async_push_browse_slots(
    hass: HomeAssistant,
    device_slug: str,
    mode: str,
    page: int,
    page_size: int,
    items: list[dict[str, Any]],
    preferred_suffix: str = "set_browse_slots",
) -> None:
    """Paginate items for any GUI page_size (1..20) and push to esphome.<slug>_<suffix> (Contract v3 or positional)."""
    esphome_action = _resolve_esphome_action(hass, device_slug, preferred_suffix)
    include_levels = preferred_suffix == "set_area_slots" and esphome_action is not None

    if esphome_action is None and preferred_suffix != "set_browse_slots":
        esphome_action = _resolve_esphome_action(
            hass, device_slug, "set_browse_slots"
        )

    coord = resolve_coordinator(hass, device_slug, allow_fallback=False)
    manifest_slots = 0
    if coord is not None:
        try:
            manifest_slots = int(coord.hardware_manifest.get("slot_count") or 0)
        except (ValueError, TypeError):
            manifest_slots = 0

    default_cap = manifest_slots if manifest_slots >= 1 else (3 if include_levels else 5)
    slot_capacity, is_contract_v3 = _detect_esphome_slot_capacity(
        hass, esphome_action, default_slots=default_cap
    )
    eff_page_size = max(1, min(slot_capacity, int(page_size)))
    total_items = len(items)
    total_pages = max(1, math.ceil(total_items / eff_page_size))
    page = max(1, min(int(page), total_pages))
    start_idx = (page - 1) * eff_page_size
    page_slice = items[start_idx : start_idx + eff_page_size]

    if is_contract_v3:
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
            "mode": str(mode),
            "page": int(page),
            "total": int(total_pages),
            "slots": "\x1e".join(packed_rows),
        }
    else:
        payload = {
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
        _LOGGER.debug(
            "No ESPHome service matching *_%s found (target slug '%s'); device is headless or offline.",
            preferred_suffix,
            device_slug,
        )
        return

    try:
        await hass.services.async_call(
            "esphome", esphome_action, payload, blocking=True
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug(
            "Skipped %s push for '%s' (device hibernating or handshaking): %s",
            esphome_action,
            device_slug,
            err,
        )


def _is_esphome_device_online(hass: HomeAssistant, coord: LatterCoordinator) -> bool:
    """Return True if the target ESPHome device supports slot callbacks and has an online entity."""
    if _resolve_esphome_action(hass, coord.device_slug, "set_area_slots") is None and _resolve_esphome_action(hass, coord.device_slug, "set_browse_slots") is None:
        return False
    local_spk = coord.local_speaker
    if local_spk:
        st = hass.states.get(local_spk)
        if st is not None:
            return st.state not in ("unavailable", "unknown")
    esp_dev_id = coord.esphome_device_id
    if esp_dev_id:
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        for entry in er.async_entries_for_device(ent_reg, esp_dev_id):
            if entry.platform == "esphome":
                st = hass.states.get(entry.entity_id)
                if st is not None and st.state not in ("unavailable", "unknown"):
                    return True
    return False


async def async_push_active_area_entities(
    hass: HomeAssistant, coord: LatterCoordinator
) -> None:
    """Push the active area's entity slots to esphome.<slug>_set_area_slots when the device is online."""
    if not _is_esphome_device_online(hass, coord):
        return
    items = get_area_entities(
        hass,
        area_id=coord.active_area_id,
        domain_filter=coord.last_area_filter or "all",
        custom_entities=coord.custom_entities,
        local_speaker=coord.local_speaker,
    )
    await async_push_browse_slots(
        hass=hass,
        device_slug=coord.device_slug,
        mode=f"area_{coord.last_area_filter or 'all'}",
        page=coord.last_area_page or 1,
        page_size=coord.default_page_size,
        items=items,
        preferred_suffix="set_area_slots",
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register Latter domain services with Voluptuous schema validation."""
    domain_data = hass.data.get(DOMAIN, {})
    for val in domain_data.values():
        if isinstance(val, LatterCoordinator):
            val.on_area_changed_push_slots = lambda c: async_push_active_area_entities(hass, c)

    if hass.services.has_service(DOMAIN, SERVICE_MUSIC_BROWSE):
        return

    async def _handle_set_active_speaker(call: ServiceCall) -> None:
        speaker = str(call.data.get("entity_id") or call.data.get("speaker") or "")
        transfer_queue = _parse_bool(call.data.get("transfer_queue"), default=True)
        coord = _resolve_coordinator_from_call(hass, call)
        if coord and speaker:
            coord.async_set_active_speaker(speaker, transfer_queue=transfer_queue)

    async def _handle_media_command(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        if not coord:
            return

        data = call.data
        command = str(data.get("command") or data.get("action") or "toggle")
        speaker = data.get("speaker") or data.get("entity_id")
        raw_seek = data.get("seek_position")
        seek_pos = float(raw_seek) if raw_seek is not None and str(raw_seek).strip() != "" else None
        media_id = str(data.get("media_id") or "").strip() or None
        media_type = str(data.get("media_type") or "").strip() or None
        enqueue = str(data.get("enqueue") or "").strip() or None

        await coord.async_execute_media_command(
            command=command,
            speaker=str(speaker) if speaker else None,
            seek_position=seek_pos,
            media_id=media_id,
            media_type=media_type,
            enqueue=enqueue,
        )

    async def _handle_trigger_binding(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        if not coord:
            return

        data = call.data
        slot_raw = str(data.get("slot") or "").strip()
        slot_key = slot_raw.lower()
        if not slot_key:
            return

        bindings = coord.custom_bindings
        matched: dict[str, Any] | None = None
        if "." in slot_raw and hass.states.get(slot_raw) is not None:
            matched = {"slot": slot_raw, "entity_id": slot_raw, "action": "toggle"}

        if matched is None:
            for binding in bindings:
                b_slot = str(binding.get("slot") or "").strip().lower()
                if b_slot == slot_key:
                    matched = binding
                    break

        if matched is None and slot_key.startswith("macro_"):
            try:
                idx = int(slot_key.split("_", 1)[1]) - 1
                if 0 <= idx < len(coord.custom_entities):
                    matched = {
                        "slot": slot_key,
                        "entity_id": coord.custom_entities[idx],
                        "action": "toggle",
                    }
                elif 0 <= idx < len(bindings):
                    matched = bindings[idx]
            except ValueError:
                pass

        if matched is not None:
            ent_id = str(matched.get("entity_id") or "").strip()
            action = str(
                data.get("action") or matched.get("action") or "toggle"
            ).strip()
            raw_lvl = data.get("level")
            lvl = int(float(raw_lvl)) if raw_lvl is not None else None
            if ent_id:
                await async_execute_area_action(
                    hass, entity_id=ent_id, action=action, level=lvl
                )
                coord.async_notify_listeners()
            return

        _LOGGER.debug(
            "No custom binding found for slot '%s' on device '%s'",
            slot_key,
            coord.device_slug,
        )

    async def _handle_media_volume(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data
        speaker = str(
            data.get("entity_id")
            or data.get("speaker")
            or (coord.active_speaker if coord else "")
        ).strip()
        if not speaker:
            return

        vol_target = (
            coord.get_volume_target_entity(speaker) if coord else speaker
        )
        state_obj = hass.states.get(vol_target)
        target_domain = (
            state_obj.domain if state_obj else vol_target.split(".")[0]
        )
        action = str(data.get("action") or "set").strip().lower()

        raw_lvl = data.get("volume_level")
        parsed_lvl: float | None = None
        if raw_lvl is not None and str(raw_lvl).strip() != "":
            try:
                parsed_lvl = float(str(raw_lvl).strip())
            except ValueError:
                parsed_lvl = None

        if target_domain in ("number", "input_number"):
            cur_val = float(state_obj.state) if (state_obj and state_obj.state not in ("unavailable", "unknown")) else 50.0
            min_v = float(state_obj.attributes.get("min", 0.0)) if state_obj else 0.0
            max_v = float(state_obj.attributes.get("max", 100.0)) if state_obj else 100.0
            native_step = state_obj.attributes.get("step") if state_obj else None
            step = float(native_step) if native_step else max(1.0, (max_v - min_v) * 0.05)

            if action == "up":
                new_val = min(max_v, cur_val + step)
            elif action == "down":
                new_val = max(min_v, cur_val - step)
            elif parsed_lvl is not None:
                lvl = parsed_lvl / 100.0 if parsed_lvl > 1.0 else parsed_lvl
                new_val = min_v + max(0.0, min(1.0, lvl)) * (max_v - min_v)
            else:
                return

            await hass.services.async_call(
                target_domain,
                "set_value",
                {ATTR_ENTITY_ID: vol_target, "value": round(new_val, 2)},
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
        elif parsed_lvl is not None:
            lvl = parsed_lvl / 100.0 if parsed_lvl > 1.0 else parsed_lvl
            lvl = max(0.0, min(1.0, lvl))
            await hass.services.async_call(
                "media_player",
                "volume_set",
                {ATTR_ENTITY_ID: vol_target, "volume_level": round(lvl, 2)},
                blocking=False,
            )

    async def _handle_set_active_area(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        area_val = str(call.data.get("area") or call.data.get("area_id") or "").strip()
        if coord and area_val:
            raw_handoff = call.data.get("handoff_media")
            handoff_val = (
                _parse_bool(raw_handoff, default=coord.area_handoff_enabled)
                if raw_handoff is not None
                else None
            )
            coord.async_set_active_area(
                area_val,
                handoff_media=handoff_val,
                sync_device_registry=True,
            )

    async def _handle_remote_action(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        if not coord:
            return

        data = call.data
        slots = coord.get_remote_slots()
        slot_num = int(data.get("slot") or coord.active_remote_slot or 1)
        slot_num = max(1, min(max(1, len(slots)), slot_num))
        if slot_num != coord.active_remote_slot:
            coord.active_remote_slot = slot_num
            coord._schedule_persist_runtime_state()
            coord.async_notify_listeners()

        action = str(data.get("action") or "").strip().lower()
        raw_cmd = str(data.get("command") or action).strip()
        cmd_low = raw_cmd.lower()
        if action in ("select_slot", ""):
            return

        slot_info = slots[slot_num - 1]
        remote_ent = slot_info["remote_entity"]
        mp_ent = slot_info["media_player_entity"]
        platform = str(slot_info.get("platform") or "").lower()
        combined_ident = f"{platform} {mp_ent} {remote_ent} {slot_info.get('name', '')}".lower()

        if action == "toggle" or cmd_low in ("toggle", "power"):
            target = mp_ent or remote_ent
            if target:
                domain = target.split(".")[0]
                await hass.services.async_call(
                    domain, "toggle", {ATTR_ENTITY_ID: target}, blocking=False
                )
            return

        effective_media_cmd = cmd_low if action == "command" else action
        if effective_media_cmd in ("volume_up", "volume_down", "volume_mute", "media_play_pause"):
            vol_override = (
                coord.volume_overrides.get(mp_ent)
                or coord.volume_overrides.get(remote_ent)
            )
            eff_mp = vol_override or mp_ent
            if eff_mp and eff_mp.startswith("media_player."):
                if effective_media_cmd == "volume_mute":
                    st = hass.states.get(eff_mp)
                    muted = bool(st.attributes.get("is_volume_muted", False)) if st else False
                    await hass.services.async_call(
                        "media_player",
                        "volume_mute",
                        {ATTR_ENTITY_ID: eff_mp, "is_volume_muted": not muted},
                        blocking=False,
                    )
                else:
                    await hass.services.async_call(
                        "media_player",
                        effective_media_cmd,
                        {ATTR_ENTITY_ID: eff_mp},
                        blocking=False,
                    )
                return
            if remote_ent and remote_ent.startswith("remote."):
                await hass.services.async_call(
                    "remote",
                    "send_command",
                    {
                        ATTR_ENTITY_ID: remote_ent,
                        "command": effective_media_cmd.upper() if "android" in combined_ident else effective_media_cmd,
                    },
                    blocking=False,
                )
                return

        if not raw_cmd:
            return

        intent = CANONICAL_NAV_INTENT.get(cmd_low)

        is_denon = platform == "denonavr" or any(
            k in combined_ident for k in ("denon", "marantz")
        )
        if is_denon and mp_ent and hass.services.has_service("denonavr", "get_command"):
            denon_path = DENONAVR_COMMAND_MAP.get(intent or cmd_low)
            if not denon_path and raw_cmd.startswith("/goform/"):
                denon_path = raw_cmd
            if denon_path:
                await hass.services.async_call(
                    "denonavr",
                    "get_command",
                    {ATTR_ENTITY_ID: mp_ent, "command": denon_path},
                    blocking=False,
                )
                return

        is_webos = platform == "webostv" or any(
            k in combined_ident for k in ("webos", "lg_tv", "lg_oled", "lg webos")
        )
        if is_webos and mp_ent and hass.services.has_service("webostv", "button"):
            webos_btn = WEBOSTV_BUTTON_MAP.get(intent or cmd_low, raw_cmd.upper())
            await hass.services.async_call(
                "webostv",
                "button",
                {ATTR_ENTITY_ID: mp_ent, "button": webos_btn},
                blocking=False,
            )
            return

        is_android_tv = platform in ("androidtv_remote", "androidtv", "braviatv", "firetv") or any(
            k in combined_ident
            for k in ("shield", "android", "google_tv", "chromecast", "bravia", "fire_tv", "onn")
        )
        if remote_ent and remote_ent.startswith("remote."):
            if is_android_tv:
                out_cmd = ANDROIDTV_COMMAND_MAP.get(intent or cmd_low, raw_cmd.upper())
            elif intent is not None:
                if platform == "apple_tv" and intent == "back":
                    out_cmd = "menu"
                else:
                    out_cmd = STANDARD_REMOTE_COMMAND_MAP.get(intent, raw_cmd)
            else:
                out_cmd = raw_cmd

            await hass.services.async_call(
                "remote",
                "send_command",
                {ATTR_ENTITY_ID: remote_ent, "command": out_cmd},
                blocking=False,
            )

    async def _handle_music_browse(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data
        raw_target = data.get("device_slug") or data.get("target_device")
        device_slug = (
            coord.device_slug
            if coord
            else normalize_device_slug(str(raw_target or "esphome_device"))
        )

        mode = str(data.get("mode") or "speakers")
        page = int(data.get("page") or 1)
        page_size = int(data.get("page_size") or 5)
        local_speaker = (
            coord.local_speaker if coord else f"media_player.{device_slug}"
        )
        speaker = str(
            data.get("speaker")
            or (coord.active_speaker if coord else local_speaker)
        )
        last_speaker = str(
            data.get("last_speaker")
            or (coord.last_speaker if coord else speaker)
        )
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
            device_slug=device_slug,
            mode=mode,
            page=page,
            page_size=page_size,
            items=items,
            preferred_suffix="set_browse_slots",
        )

    async def _handle_area_browse(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data
        raw_target = data.get("device_slug") or data.get("target_device")
        device_slug = (
            coord.device_slug
            if coord
            else normalize_device_slug(str(raw_target or "esphome_device"))
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
        local_speaker = (
            coord.local_speaker if coord else f"media_player.{device_slug}"
        )

        if coord:
            if mode == "entities":
                coord.last_area_filter = domain_filter
                coord.last_area_page = page
            if area_id and area_id != coord.active_area_id:
                coord.on_area_changed_push_slots = None
                coord.async_set_active_area(
                    area_id, handoff_media=False, sync_device_registry=False
                )
                coord.on_area_changed_push_slots = lambda c: async_push_active_area_entities(hass, c)

        if mode == "areas":
            items = get_areas_summary(
                hass,
                active_area_id=coord.active_area_id if coord else area_id,
                local_speaker=local_speaker,
                device_slug=device_slug,
            )
            slot_mode = "area_areas"
        elif mode == "home":
            items = get_home_wide_entities(
                hass,
                configured_alarm_entity=coord.get_opt(CONF_ALARM_ENTITY) if coord else None,
                custom_entities=coord.custom_entities if coord else None,
            )
            slot_mode = "area_home"
        else:
            items = get_area_entities(
                hass,
                area_id=area_id or (coord.active_area_id if coord else None),
                domain_filter=domain_filter,
                custom_entities=coord.custom_entities if coord else None,
                local_speaker=local_speaker,
            )
            slot_mode = f"area_{domain_filter}"

        target_suffix = "set_browse_slots" if mode == "areas" else "set_area_slots"
        await async_push_browse_slots(
            hass=hass,
            device_slug=device_slug,
            mode=slot_mode,
            page=page,
            page_size=page_size,
            items=items,
            preferred_suffix=target_suffix,
        )

    async def _handle_area_action(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data

        area_id = data.get("area_id")
        if coord and area_id and str(area_id) != coord.active_area_id:
            coord.async_set_active_area(
                str(area_id),
                handoff_media=False,
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
            level = int(float(raw_level)) if raw_level is not None and str(raw_level).strip() != "" else None
            code = str(data.get("code")) if data.get("code") is not None else None
            await async_execute_area_action(
                hass,
                entity_id=entity_id,
                action=action,
                level=level,
                code=code,
            )
            if coord:
                await asyncio.sleep(0.15)
                coord.async_notify_listeners()
                await async_push_active_area_entities(hass, coord)

    async def _handle_calendar_fetch(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data
        raw_target = data.get("device_slug") or data.get("target_device")
        device_slug = (
            coord.device_slug
            if coord
            else normalize_device_slug(str(raw_target or "esphome_device"))
        )

        days = int(data.get("days") or 30)
        page = int(data.get("page") or 1)
        page_size = int(data.get("page_size") or 5)

        if coord:
            await coord.async_refresh_calendar_agenda(days=days)
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
        coord = _resolve_coordinator_from_call(hass, call)
        data = call.data

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
            speakers = []

        follow_me_mode = (
            speakers in (["follow_me"], ["occupied"], ["occupied_areas"])
            or str(data.get("target_device") or "").strip().lower()
            in ("follow_me", "occupied", "occupied_areas")
        )
        if follow_me_mode or not speakers:
            all_online_speakers = [
                s.entity_id
                for s in hass.states.async_all("media_player")
                if s.state not in ("unavailable", "unknown")
                and is_music_assistant_player(hass, s)
            ]
            if follow_me_mode:
                from .ble_engine import get_ble_fabric
                from homeassistant.helpers import entity_registry as er

                fabric = get_ble_fabric(hass)
                ent_reg = er.async_get(hass)
                dev_reg = dr.async_get(hass)
                occupied_areas: set[str] = set()
                for c in hass.data.get(DOMAIN, {}).values():
                    if isinstance(c, LatterCoordinator) and c.active_area_id:
                        if fabric.get_area_occupancy(c.active_area_id).get("is_occupied"):
                            occupied_areas.add(c.active_area_id)
                for reg_e in ent_reg.entities.values():
                    a_id = reg_e.area_id or (
                        dev_reg.async_get(reg_e.device_id).area_id
                        if reg_e.device_id and dev_reg.async_get(reg_e.device_id)
                        else None
                    )
                    if a_id and fabric.get_area_occupancy(a_id).get("is_occupied"):
                        occupied_areas.add(a_id)

                matched_speakers: list[str] = []
                if occupied_areas:
                    for spk_id in all_online_speakers:
                        e_entry = ent_reg.async_get(spk_id)
                        spk_area = e_entry.area_id if e_entry else None
                        if not spk_area and e_entry and e_entry.device_id:
                            d_entry = dev_reg.async_get(e_entry.device_id)
                            if d_entry:
                                spk_area = d_entry.area_id
                        if spk_area in occupied_areas:
                            matched_speakers.append(spk_id)
                    for c in hass.data.get(DOMAIN, {}).values():
                        if (
                            isinstance(c, LatterCoordinator)
                            and c.active_area_id in occupied_areas
                        ):
                            for cand_spk in (c.active_speaker, c.local_speaker):
                                if cand_spk and cand_spk not in matched_speakers:
                                    st_s = hass.states.get(cand_spk)
                                    if st_s and st_s.state not in ("unavailable", "unknown"):
                                        matched_speakers.append(cand_spk)
                speakers = matched_speakers or all_online_speakers
            else:
                speakers = all_online_speakers

        if not speakers:
            return

        if media_url:
            ma_speakers = [
                s for s in speakers
                if hass.states.get(s) and is_music_assistant_player(hass, hass.states.get(s))
            ]
            other_speakers = [s for s in speakers if s not in ma_speakers]

            if ma_speakers and hass.services.has_service("music_assistant", "play_announcement"):
                await hass.services.async_call(
                    "music_assistant",
                    "play_announcement",
                    {
                        ATTR_ENTITY_ID: ma_speakers,
                        "url": media_url,
                    },
                    blocking=False,
                )
            else:
                other_speakers = speakers

            if other_speakers:
                await hass.services.async_call(
                    "media_player",
                    "play_media",
                    {
                        ATTR_ENTITY_ID: other_speakers,
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
        DOMAIN,
        SERVICE_SET_ACTIVE_SPEAKER,
        _handle_set_active_speaker,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("entity_id"): cv.string,
                vol.Optional("speaker"): cv.string,
                vol.Optional("transfer_queue", default=True): vol.Any(bool, cv.string),
            },
            extra=vol.ALLOW_EXTRA,
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
                vol.Optional("action"): cv.string,
                vol.Optional("speaker"): cv.string,
                vol.Optional("entity_id"): cv.string,
                vol.Optional("seek_position"): vol.Any(vol.Coerce(float), cv.string),
                vol.Optional("media_id"): cv.string,
                vol.Optional("media_type"): cv.string,
                vol.Optional("enqueue"): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_TRIGGER_BINDING,
        _handle_trigger_binding,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Required("slot"): cv.string,
                vol.Optional("action"): cv.string,
                vol.Optional("level"): vol.Any(vol.Coerce(float), cv.string),
            },
            extra=vol.ALLOW_EXTRA,
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
                vol.Optional("speaker"): cv.string,
                vol.Optional("action", default="set"): cv.string,
                vol.Optional("volume_level"): vol.Any(vol.Coerce(float), cv.string),
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ACTIVE_AREA,
        _handle_set_active_area,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("area"): cv.string,
                vol.Optional("area_id"): cv.string,
                vol.Optional("handoff_media"): vol.Any(bool, cv.string),
            },
            extra=vol.ALLOW_EXTRA,
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
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_MUSIC_BROWSE,
        _handle_music_browse,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("mode", default="speakers"): cv.string,
                vol.Optional("page", default=1): vol.Coerce(int),
                vol.Optional("page_size", default=5): vol.Coerce(int),
                vol.Optional("search", default=""): cv.string,
                vol.Optional("speaker"): cv.string,
                vol.Optional("last_speaker"): cv.string,
                vol.Optional("album_sort", default="name"): cv.string,
                vol.Optional("artist_album_sort", default="year"): cv.string,
                vol.Optional("podcast_sort", default="newest"): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_AREA_BROWSE,
        _handle_area_browse,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("mode", default="entities"): cv.string,
                vol.Optional("area_id"): cv.string,
                vol.Optional("domain_filter", default="all"): cv.string,
                vol.Optional("page", default=1): vol.Coerce(int),
                vol.Optional("page_size"): vol.Coerce(int),
                vol.Optional("handoff_media"): vol.Any(bool, cv.string),
            },
            extra=vol.ALLOW_EXTRA,
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
                vol.Optional("action", default="toggle"): cv.string,
                vol.Optional("level"): vol.Any(vol.Coerce(float), cv.string),
                vol.Optional("code"): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CALENDAR_FETCH,
        _handle_calendar_fetch,
        schema=vol.Schema(
            {
                **BASE_TARGET_FIELDS,
                vol.Optional("days", default=7): vol.Coerce(int),
                vol.Optional("page", default=1): vol.Coerce(int),
                vol.Optional("page_size", default=5): vol.Coerce(int),
            },
            extra=vol.ALLOW_EXTRA,
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
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
    async def _handle_notify_device(call: ServiceCall) -> None:
        """Dispatch a toast notification, chime, and optional live camera peephole snapshot to one, occupied ('follow_me'), or all Latter displays."""
        data = call.data
        raw_target = str(
            data.get("target_device")
            or data.get("device_slug")
            or data.get("person_entity")
            or ""
        ).strip()
        target_low = raw_target.lower()

        all_coords = [
            c
            for c in hass.data.get(DOMAIN, {}).values()
            if isinstance(c, LatterCoordinator)
            and c.device_profile not in ("ble_beacon", "headless_node")
        ]
        target_coords: list[LatterCoordinator] = []

        if target_low == "all":
            target_coords = list(all_coords)
        elif (
            target_low in ("follow_me", "occupied", "occupied_areas")
            or target_low.startswith("person.")
        ):
            from .ble_engine import get_ble_fabric

            fabric = get_ble_fabric(hass)
            person_area_name = ""
            if target_low.startswith("person."):
                p_slug = raw_target.split(".", 1)[-1].lower()
                p_st = hass.states.get(f"sensor.{p_slug}_current_area")
                if p_st and p_st.state not in ("unknown", "unavailable", "Away", ""):
                    person_area_name = p_st.state.strip().lower()

            for c in all_coords:
                if target_low.startswith("person."):
                    if c.assigned_person.lower() == target_low:
                        target_coords.append(c)
                        continue
                    if person_area_name and c.active_area_id:
                        occ = fabric.get_area_occupancy(c.active_area_id)
                        if (
                            c.active_area_id.lower() == person_area_name
                            or any(
                                person_area_name in str(n).lower()
                                for n in (occ.get("occupant_names") or [])
                            )
                        ):
                            target_coords.append(c)
                elif c.active_area_id:
                    occ = fabric.get_area_occupancy(c.active_area_id)
                    if occ.get("is_occupied"):
                        target_coords.append(c)

            if not target_coords:
                target_coords = list(all_coords)
        else:
            single = _resolve_coordinator_from_call(hass, call)
            if single:
                target_coords = [single]

        if not target_coords:
            return

        title = str(data.get("title") or "Alert").strip()
        message = str(data.get("message") or "").strip()
        priority = str(data.get("priority") or "normal").strip().lower()
        duration = int(data.get("duration") or 8)
        chime = _parse_bool(data.get("chime"), default=True)
        cam_ent = str(data.get("camera_entity") or "").strip() or None

        for coord in target_coords:
            coord.async_dispatch_notification(
                title=title,
                message=message,
                priority=priority,
                duration=duration,
                chime=chime,
                camera_entity=cam_ent,
            )

            esp_notify_svc = _resolve_esphome_action(
                hass, coord.device_slug, "show_notification"
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
                            "chime": chime,
                            "camera_url": coord.alert_camera_url,
                        },
                        blocking=True,
                    )
                except Exception as err:  # noqa: BLE001
                    _LOGGER.debug("Direct esphome.%s call skipped: %s", esp_notify_svc, err)

    hass.services.async_register(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        _handle_intercom_broadcast,
        schema=vol.Schema(
            {
                vol.Optional("message"): cv.string,
                vol.Optional("media_url"): cv.string,
                vol.Optional("target_speakers"): vol.Any(cv.string, [cv.string]),
                vol.Optional("tts_entity"): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        ),
    )
    notify_schema = vol.Schema(
        {
            **BASE_TARGET_FIELDS,
            vol.Optional("title", default="Notification"): cv.string,
            vol.Required("message"): cv.string,
            vol.Optional("priority", default="normal"): cv.string,
            vol.Optional("duration", default=8): vol.Coerce(int),
            vol.Optional("chime", default=True): vol.Any(bool, cv.string),
            vol.Optional("camera_entity"): cv.string,
        },
        extra=vol.ALLOW_EXTRA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_NOTIFY,
        _handle_notify_device,
        schema=notify_schema,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_NOTIFY_DEVICE,
        _handle_notify_device,
        schema=notify_schema,
    )

    async def _handle_save_custom_color(call: ServiceCall) -> None:
        coord = _resolve_coordinator_from_call(hass, call)
        raw_hex = str(call.data.get("hex_color") or "").strip().upper()
        if not raw_hex.startswith("#"):
            raw_hex = f"#{raw_hex}"
        if len(raw_hex) != 7:
            return
        name = str(call.data.get("name") or f"Custom ({raw_hex})").strip()

        domain_data = hass.data.setdefault(DOMAIN, {})
        global_cfg: dict[str, Any] = domain_data.setdefault(DATA_GLOBAL_CONFIG, {})
        palettes: list[dict[str, str]] = list(global_cfg.get(CONF_CUSTOM_PALETTES) or [])
        existing = next((p for p in palettes if str(p.get("hex", "")).upper() == raw_hex), None)
        if existing is not None:
            if call.data.get("name"):
                existing["name"] = name
        else:
            palettes.insert(0, {"name": name, "hex": raw_hex})
            palettes = palettes[:24]
        global_cfg[CONF_CUSTOM_PALETTES] = palettes
        store = domain_data.get(DATA_GLOBAL_STORE)
        if store is not None:
            await store.async_save(global_cfg)

        if coord is not None:
            merged = {
                **coord.entry.data,
                **(coord.entry.options or {}),
                CONF_CUSTOM_PALETTES: palettes,
                CONF_DEVICE_CUSTOM_COLOR: raw_hex,
            }
            hass.config_entries.async_update_entry(
                coord.entry, data=merged, options=merged
            )
            coord.async_notify_listeners()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_CUSTOM_COLOR,
        _handle_save_custom_color,
    )

    async def _handle_doorbell_intercom(call: ServiceCall) -> ServiceResponse:
        """Execute a two-way doorbell intercom or camera audio action and return target metadata."""
        from .doorbell_engine import async_execute_doorbell_intercom

        coord = _resolve_coordinator_from_call(hass, call)
        if not coord:
            return {"status": "error", "reason": "no_coordinator"}
        data = call.data
        action = str(data.get("action") or "listen_toggle").strip()
        cam_ent = str(data.get("camera_entity") or "").strip() or None
        msg = str(data.get("message") or "").strip()
        anc = str(data.get("anc_mode") or "").strip() or None
        raw_idx = data.get("camera_index")
        cam_idx = int(raw_idx) if raw_idx is not None and str(raw_idx).strip() != "" else None
        info = await async_execute_doorbell_intercom(
            hass=hass,
            coordinator=coord,
            action=action,
            camera_entity=cam_ent,
            message=msg,
            anc_mode=anc,
            camera_index=cam_idx,
        )
        return {
            "status": "ok",
            "device_slug": coord.device_slug,
            "action": action,
            "doorbell_talk_state": coord.doorbell_talk_state,
            "doorbell_anc_mode": coord.doorbell_anc_mode,
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
                vol.Optional("anc_mode"): cv.string,
            },
            extra=vol.ALLOW_EXTRA,
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
