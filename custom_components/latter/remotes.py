"""Unified TV/AV Remote slot discovery, `remote_config` Protocol v3 builder, and command maps (`L1b`)."""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Any, Final

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .hub_registry import get_area_state_index
from .protocol_codec import V3Records, ha_value, remote_slot_records

if TYPE_CHECKING:
    from .coordinator import LatterCoordinator

CANONICAL_NAV_INTENT: Final[dict[str, str]] = {
    "up": "up", "dpad_up": "up", "cursor_up": "up",
    "down": "down", "dpad_down": "down", "cursor_down": "down",
    "left": "left", "dpad_left": "left", "cursor_left": "left",
    "right": "right", "dpad_right": "right", "cursor_right": "right",
    "select": "select", "enter": "select", "ok": "select", "dpad_center": "select", "key_enter": "select",
    "back": "back", "return": "back", "key_return": "back",
    "home": "home", "top_menu": "home", "key_home": "home",
    "menu": "menu",
    "info": "info",
    "option": "option",
    "exit": "exit",
    "play": "play",
    "pause": "pause",
    "play_pause": "play_pause", "media_play_pause": "play_pause",
}

ANDROIDTV_COMMAND_MAP: Final[dict[str, str]] = {
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
    "play_pause": "MEDIA_PLAY_PAUSE",
}

STANDARD_REMOTE_COMMAND_MAP: Final[dict[str, str]] = {
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "select": "select",
    "back": "back",
    "home": "home",
    "menu": "menu",
    "info": "info",
    "play": "play",
    "pause": "pause",
    "play_pause": "play_pause",
}

DENONAVR_COMMAND_MAP: Final[dict[str, str]] = {
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

WEBOSTV_BUTTON_MAP: Final[dict[str, str]] = {
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
    "play_pause": "PLAY",
}

ADB_KEYCODE_MAP: Final[dict[str, int]] = {
    "up": 19,
    "down": 20,
    "left": 21,
    "right": 22,
    "select": 23,
    "back": 4,
    "home": 3,
    "menu": 82,
    "info": 165,
    "play": 126,
    "pause": 127,
    "play_pause": 85,
}

DEFAULT_ANDROIDTV_HOLD_SECS: Final = 0.6
MIN_APPLETV_HOLD_SECS: Final = 1.0
_MAX_SLOTS: Final = 10
_REMOTE_LABEL_MAX: Final = 32
_PAYLOAD_CACHE_TTL_S: Final = 0.15
_MP_PLAY_PAUSE_MASK: Final = 1 | 4096 | 16384
_MP_VOLUME_MUTE_FLAG: Final = 8
_MP_VOLUME_STEP_FLAG: Final = 1024
_VOL_STEP_FRAC: Final = 0.05
_ANDROID_TV_PLATFORMS: Final[frozenset[str]] = frozenset(
    {"androidtv_remote", "androidtv", "braviatv", "firetv"}
)


def resolve_remote_slot_pair(hass: HomeAssistant, configured_entity_id: str | None) -> dict[str, str]:
    """Given a `remote.*` or `media_player.*` entity, auto-resolve its sibling on the same HA device."""
    empty = {
        "name": "Unassigned",
        "remote_entity": "",
        "media_player_entity": "",
        "area_id": "",
        "state": "off",
        "platform": "",
    }
    if not configured_entity_id:
        return empty

    ent_id = configured_entity_id.strip()
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)
    entry = ent_reg.async_get(ent_id)
    state_obj = hass.states.get(ent_id)
    if state_obj is None and entry is None:
        return empty

    ent_domain = state_obj.domain if state_obj else ent_id.split(".", 1)[0]
    remote_ent = ent_id if ent_domain == "remote" else ""
    mp_ent = ent_id if ent_domain == "media_player" else ""
    platform = str(entry.platform or "") if entry else ""

    if entry and entry.device_id:
        for sib in sorted(
            er.async_entries_for_device(ent_reg, entry.device_id),
            key=lambda s: s.entity_id,
        ):
            if sib.disabled_by:
                continue
            if sib.domain == "remote" and not remote_ent:
                remote_ent = sib.entity_id
                platform = platform or str(sib.platform or "")
            elif sib.domain == "media_player" and not mp_ent:
                mp_ent = sib.entity_id
                platform = platform or str(sib.platform or "")

    primary_state = hass.states.get(mp_ent) or state_obj
    dev_name = ""
    if entry and entry.device_id and (dev := dev_reg.async_get(entry.device_id)) is not None:
        dev_name = str(dev.name_by_user or dev.name or "")
    friendly = str(
        (primary_state.attributes.get("friendly_name") if primary_state else None)
        or (state_obj.attributes.get("friendly_name") if state_obj else None)
        or (entry.name if entry else None)
        or (entry.original_name if entry else None)
        or dev_name
        or ent_id
    )
    area_id = get_area_state_index(hass).resolve_entity_area_id(ent_id) or ""
    return {
        "name": friendly[:_REMOTE_LABEL_MAX],
        "remote_entity": remote_ent or mp_ent,
        "media_player_entity": mp_ent or remote_ent,
        "area_id": area_id,
        "state": ha_value(primary_state.state) if primary_state else "",
        "platform": platform,
    }


def resolve_effective_remote_entities(
    hass: HomeAssistant,
    *,
    all_inventory: list[str],
    groups: list[dict[str, Any]],
    mode: str,
    cur_area: str,
) -> list[str]:
    """Resolve the ordered list of remote entities for a device (Static Group vs Active Area vs All)."""
    if mode.startswith("group:"):
        gid = mode.split(":", 1)[1].strip()
        matched_grp = next((g for g in groups if g["id"] == gid), None)
        return list(matched_grp.get("remotes") or [])[:_MAX_SLOTS] if matched_grp is not None else []

    if mode == "all":
        return all_inventory[:_MAX_SLOTS]

    if cur_area:
        area_group_remotes: list[str] = []
        for grp in groups:
            if grp.get("area_id") == cur_area:
                for rem_id in grp.get("remotes") or []:
                    if rem_id not in area_group_remotes:
                        area_group_remotes.append(rem_id)
        if area_group_remotes:
            return area_group_remotes[:_MAX_SLOTS]
        if groups:
            return []
        resolved_all = [resolve_remote_slot_pair(hass, eid) for eid in all_inventory]
        if any(bool(r.get("area_id")) for r in resolved_all):
            return [
                eid
                for eid, r in zip(all_inventory, resolved_all, strict=False)
                if r.get("area_id") == cur_area
            ][:_MAX_SLOTS]

    return all_inventory[:_MAX_SLOTS] if not groups else []


def build_remote_config_payload(
    coordinator: Any,
) -> tuple[str | None, dict[str, Any]]:
    """Compute state and attributes for `sensor.<device_slug>_remote_config`."""
    now_m = time.monotonic()
    cached = coordinator.cached_remote_payload
    if cached is not None and (now_m - cached[0]) < _PAYLOAD_CACHE_TTL_S:
        cached_res: tuple[str | None, dict[str, Any]] = cached[1]
        return cached_res
    slots = coordinator.get_remote_slots()
    slot_rows: list[dict[str, Any]] = []
    for idx, slot in enumerate(slots, start=1):
        ent = (
            slot["remote_entity"]
            if slot["remote_entity"].startswith("remote.")
            else slot["media_player_entity"]
        )
        if ent.startswith(("remote.", "media_player.")):
            slot_rows.append(
                {
                    "index": idx,
                    "label": slot["name"],
                    "entity_id": ent,
                    "area_id": slot["area_id"],
                    "state": ha_value(slot["state"]),
                }
            )
    populated_count = len(slot_rows)
    clamped_active = max(1, min(max(1, len(slots)), coordinator.active_remote_slot))
    active_slot = clamped_active if populated_count else None
    slots_summary = remote_slot_records(slot_rows) if populated_count else V3Records()
    state_str = (slots[clamped_active - 1]["name"] or None) if populated_count else None
    rem_rev, rem_payload = coordinator.pack_domain_payload(
        "remote_config", active_slot, populated_count, slots_summary
    )
    attrs: dict[str, Any] = {
        "active_slot": active_slot,
        "configured_count": populated_count,
        "slots_summary": slots_summary,
        "rev": rem_rev,
        "payload": rem_payload,
    }
    res = (state_str, attrs)
    coordinator.cached_remote_payload = (time.monotonic(), res)
    return res


async def _async_step_number_volume(hass: HomeAssistant, target: str, domain: str, action: str) -> bool:
    if action == "volume_mute":
        return False
    st = hass.states.get(target)
    if st is None:
        return False
    try:
        cur = float(st.state)
        lo = float(st.attributes.get("min", 0.0))
        hi = float(st.attributes.get("max", 100.0))
        step_raw = st.attributes.get("step")
        step = float(step_raw) if step_raw is not None else max(1.0, (hi - lo) * _VOL_STEP_FRAC)
    except (TypeError, ValueError):
        return False
    if not (math.isfinite(cur) and math.isfinite(lo) and math.isfinite(hi) and hi > lo):
        return False
    delta = step if action == "volume_up" else -step
    new_val = max(lo, min(hi, cur + delta))
    await hass.services.async_call(
        domain, "set_value", {ATTR_ENTITY_ID: target, "value": new_val}, blocking=False
    )
    return True


def _parse_mp_volume_flags(st: Any) -> tuple[bool, bool]:
    raw_sf = st.attributes.get("supported_features") if st is not None else None
    if raw_sf is None or isinstance(raw_sf, bool):
        return True, True
    try:
        sf = int(raw_sf)
    except (TypeError, ValueError):
        return True, True
    return (sf & _MP_VOLUME_MUTE_FLAG) != 0, (sf & _MP_VOLUME_STEP_FLAG) != 0


async def _async_step_mp_volume(hass: HomeAssistant, target: str, st: Any, action: str) -> bool:
    can_mute, can_step = _parse_mp_volume_flags(st)
    if action == "volume_mute":
        if not can_mute:
            return False
        cur_muted = bool(st.attributes.get("is_volume_muted", False)) if st is not None else False
        await hass.services.async_call(
            "media_player",
            "volume_mute",
            {ATTR_ENTITY_ID: target, "is_volume_muted": not cur_muted},
            blocking=False,
        )
        return True
    if not can_step:
        return False
    await hass.services.async_call(
        "media_player", action, {ATTR_ENTITY_ID: target}, blocking=False
    )
    return True


async def _async_step_remote_volume_target(
    hass: HomeAssistant, target_entity_id: str, action: str
) -> bool:
    """Execute `volume_up`, `volume_down`, or `volume_mute` on a volume target without `L2a` imports."""
    target = (target_entity_id or "").strip()
    if not target or "." not in target:
        return False
    st = hass.states.get(target)
    domain = st.domain if st is not None else target.split(".", 1)[0]
    if domain in ("number", "input_number"):
        return await _async_step_number_volume(hass, target, domain, action)
    if domain != "media_player":
        return False
    return await _async_step_mp_volume(hass, target, st, action)


def _resolve_slot_platform(hass: HomeAssistant, slot_info: dict[str, str]) -> str:
    platform = str(slot_info.get("platform") or "").lower()
    if platform:
        return platform
    ent_reg = er.async_get(hass)
    for cand_ent in (slot_info["remote_entity"], slot_info["media_player_entity"]):
        if cand_ent and (reg_entry := ent_reg.async_get(cand_ent)) and reg_entry.platform:
            return str(reg_entry.platform).lower()
    return ""


async def _async_dispatch_media_or_volume_cmd(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    slot_info: dict[str, str],
    effective_media_cmd: str,
    *,
    is_android_tv: bool,
) -> bool:
    remote_ent = slot_info["remote_entity"]
    mp_ent = slot_info["media_player_entity"]
    if effective_media_cmd == "media_play_pause":
        if mp_ent and mp_ent.startswith("media_player."):
            mp_state = hass.states.get(mp_ent)
            mp_sf = int((mp_state.attributes.get("supported_features") if mp_state else 0) or 0)
            if mp_sf == 0 or bool(mp_sf & _MP_PLAY_PAUSE_MASK):
                await hass.services.async_call(
                    "media_player", "media_play_pause", {ATTR_ENTITY_ID: mp_ent}, blocking=False
                )
                return True
    else:
        vol_override = coord.volume_overrides.get(mp_ent) or coord.volume_overrides.get(remote_ent)
        eff_vol_target = vol_override or mp_ent
        if eff_vol_target and await _async_step_remote_volume_target(hass, eff_vol_target, effective_media_cmd):
            return True

    if remote_ent and remote_ent.startswith("remote."):
        if effective_media_cmd == "media_play_pause":
            rem_cmd = "MEDIA_PLAY_PAUSE" if is_android_tv else "play_pause"
        else:
            rem_cmd = effective_media_cmd.upper() if is_android_tv else effective_media_cmd
        await hass.services.async_call(
            "remote",
            "send_command",
            {ATTR_ENTITY_ID: remote_ent, "command": rem_cmd},
            blocking=False,
        )
        return True
    return False


async def _async_dispatch_platform_nav_cmd(  # noqa: PLR0913
    hass: HomeAssistant,
    *,
    raw_cmd: str,
    cmd_low: str,
    intent: str | None,
    remote_ent: str,
    mp_ent: str,
    platform: str,
    is_long_press: bool,
    parsed_hold: float,
) -> None:
    is_android_tv = platform in _ANDROID_TV_PLATFORMS
    if platform == "denonavr" and mp_ent and hass.services.has_service("denonavr", "get_command"):
        denon_path = DENONAVR_COMMAND_MAP.get(intent or cmd_low) or (
            raw_cmd if raw_cmd.startswith("/goform/") else ""
        )
        if denon_path:
            await hass.services.async_call(
                "denonavr", "get_command", {ATTR_ENTITY_ID: mp_ent, "command": denon_path}, blocking=False
            )
            return

    if platform == "webostv" and mp_ent and hass.services.has_service("webostv", "button"):
        webos_btn = WEBOSTV_BUTTON_MAP.get(intent or cmd_low, raw_cmd.upper())
        await hass.services.async_call(
            "webostv", "button", {ATTR_ENTITY_ID: mp_ent, "button": webos_btn}, blocking=False
        )
        return

    if remote_ent and remote_ent.startswith("remote."):
        if is_android_tv:
            out_cmd = ANDROIDTV_COMMAND_MAP.get(intent or cmd_low, raw_cmd.upper())
        elif intent is not None:
            out_cmd = (
                "menu"
                if platform == "apple_tv" and intent == "back"
                else STANDARD_REMOTE_COMMAND_MAP.get(intent, raw_cmd)
            )
        else:
            out_cmd = raw_cmd

        svc_data: dict[str, Any] = {ATTR_ENTITY_ID: remote_ent, "command": out_cmd}
        if is_long_press:
            if platform == "apple_tv":
                svc_data["hold_secs"] = max(
                    MIN_APPLETV_HOLD_SECS, parsed_hold if parsed_hold > 0.0 else MIN_APPLETV_HOLD_SECS
                )
            else:
                svc_data["hold_secs"] = parsed_hold if parsed_hold > 0.0 else DEFAULT_ANDROIDTV_HOLD_SECS
        await hass.services.async_call("remote", "send_command", svc_data, blocking=False)
        return

    if (
        is_long_press
        and is_android_tv
        and mp_ent
        and hass.services.has_service("androidtv", "adb_command")
        and (keycode := ADB_KEYCODE_MAP.get(intent or cmd_low)) is not None
    ):
        await hass.services.async_call(
            "androidtv",
            "adb_command",
            {ATTR_ENTITY_ID: mp_ent, "command": f"input keyevent --longpress {keycode}"},
            blocking=False,
        )


async def async_execute_remote_action(  # noqa: PLR0913
    hass: HomeAssistant,
    coord: LatterCoordinator,
    *,
    slot: int | None = None,
    action: str = "",
    command: str | None = None,
    hold_secs: float | None = None,
) -> None:
    """Execute a unified TV/AV remote slot switch, power, volume, navigation, or long-press command."""
    slots = coord.get_remote_slots()
    if not slots:
        return
    slot_num = max(1, min(len(slots), int(slot or coord.active_remote_slot or 1)))
    if slot_num != coord.active_remote_slot:
        coord.active_remote_slot = slot_num
        coord.schedule_persist_runtime_state()
        coord.async_notify_listeners()

    norm_action = str(action or "").strip().lower()
    if norm_action in ("select_slot", ""):
        return

    raw_cmd = str(command or ("" if norm_action == "long_press" else norm_action)).strip()
    cmd_low = raw_cmd.lower()
    slot_info = slots[slot_num - 1]
    remote_ent = slot_info["remote_entity"]
    mp_ent = slot_info["media_player_entity"]

    if norm_action == "toggle" or cmd_low in ("toggle", "power"):
        if target := (mp_ent or remote_ent):
            await hass.services.async_call(
                target.split(".")[0], "toggle", {ATTR_ENTITY_ID: target}, blocking=False
            )
        return

    platform = _resolve_slot_platform(hass, slot_info)
    effective_media_cmd = cmd_low if norm_action == "command" else norm_action
    if effective_media_cmd in ("volume_up", "volume_down", "volume_mute", "media_play_pause") and (
        await _async_dispatch_media_or_volume_cmd(
            hass,
            coord,
            slot_info,
            effective_media_cmd,
            is_android_tv=platform in _ANDROID_TV_PLATFORMS,
        )
    ):
        return

    if not raw_cmd:
        return
    parsed_hold = float(hold_secs) if hold_secs is not None else 0.0
    await _async_dispatch_platform_nav_cmd(
        hass,
        raw_cmd=raw_cmd,
        cmd_low=cmd_low,
        intent=CANONICAL_NAV_INTENT.get(cmd_low),
        remote_ent=remote_ent,
        mp_ent=mp_ent,
        platform=platform,
        is_long_press=norm_action == "long_press" or parsed_hold > 0.0,
        parsed_hold=parsed_hold,
    )
