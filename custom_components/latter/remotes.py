"""Unified TV/AV Remote slot discovery, remote_config Protocol v3 builder, and remote_action command maps."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .hub import get_area_state_index
from .media import async_execute_volume_action
from .protocol import V3Records, ha_value, remote_slot_records

if TYPE_CHECKING:
    from .coordinator import LatterCoordinator

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


def resolve_remote_slot_pair(
    hass: HomeAssistant, configured_entity_id: str | None
) -> dict[str, str]:
    """Given a remote.* or media_player.* entity, auto-resolve its sibling on the same HA device."""
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
        for sib in er.async_entries_for_device(ent_reg, entry.device_id):
            if sib.disabled_by:
                continue
            if sib.domain == "remote" and not remote_ent:
                remote_ent = sib.entity_id
                if not platform:
                    platform = str(sib.platform or "")
            elif sib.domain == "media_player" and not mp_ent:
                mp_ent = sib.entity_id
                if not platform:
                    platform = str(sib.platform or "")

    primary_state = hass.states.get(mp_ent) or state_obj
    dev_name = ""
    if entry and entry.device_id:
        dev = dev_reg.async_get(entry.device_id)
        if dev:
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
        "name": friendly[:32],
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
        if matched_grp is not None:
            return list(matched_grp.get("remotes") or [])[:10]
        return []

    if mode == "all":
        return all_inventory[:10]

    if cur_area:
        area_group_remotes: list[str] = []
        for grp in groups:
            if grp.get("area_id") == cur_area:
                for rem_id in grp.get("remotes") or []:
                    if rem_id not in area_group_remotes:
                        area_group_remotes.append(rem_id)
        if area_group_remotes:
            return area_group_remotes[:10]

        if groups:
            return []

        resolved_all = [resolve_remote_slot_pair(hass, eid) for eid in all_inventory]
        any_has_area = any(bool(r.get("area_id")) for r in resolved_all)
        if any_has_area:
            return [
                eid
                for eid, r in zip(all_inventory, resolved_all, strict=False)
                if r.get("area_id") == cur_area
            ][:10]

    if not groups:
        return all_inventory[:10]
    return []


def build_remote_config_payload(
    coordinator: LatterCoordinator,
) -> tuple[str | None, dict[str, Any]]:
    """Compute state and attributes for `sensor.<device_slug>_remote_config`."""
    now_m = time.monotonic()
    if (
        coordinator._cached_remote_payload is not None
        and (now_m - coordinator._cached_remote_payload[0]) < 0.05
    ):
        return coordinator._cached_remote_payload[1]
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
    rem_rev, rem_payload = coordinator._pack_domain_payload(
        "remote_config",
        active_slot,
        populated_count,
        slots_summary,
    )
    attrs: dict[str, Any] = {
        "active_slot": active_slot,
        "configured_count": populated_count,
        "slots_summary": slots_summary,
        "rev": rem_rev,
        "payload": rem_payload,
    }
    res = (state_str, attrs)
    coordinator._cached_remote_payload = (now_m, res)
    return res


async def async_execute_remote_action(
    hass: HomeAssistant,
    coord: LatterCoordinator,
    *,
    slot: int | None = None,
    action: str = "",
    command: str | None = None,
) -> None:
    """Execute a unified TV/AV remote slot switch, power, volume, or navigation command."""
    slots = coord.get_remote_slots()
    slot_num = int(slot or coord.active_remote_slot or 1)
    slot_num = max(1, min(max(1, len(slots)), slot_num))
    if slot_num != coord.active_remote_slot:
        coord.active_remote_slot = slot_num
        coord._schedule_persist_runtime_state()
        coord.async_notify_listeners()

    norm_action = str(action or "").strip().lower()
    raw_cmd = str(command or norm_action).strip()
    cmd_low = raw_cmd.lower()
    if norm_action in ("select_slot", "") or not slots:
        return

    slot_info = slots[slot_num - 1]
    remote_ent = slot_info["remote_entity"]
    mp_ent = slot_info["media_player_entity"]
    platform = str(slot_info.get("platform") or "").lower()
    combined_ident = f"{platform} {mp_ent} {remote_ent} {slot_info.get('name', '')}".lower()

    if norm_action == "toggle" or cmd_low in ("toggle", "power"):
        target = mp_ent or remote_ent
        if target:
            domain = target.split(".")[0]
            await hass.services.async_call(
                domain, "toggle", {ATTR_ENTITY_ID: target}, blocking=False
            )
        return

    effective_media_cmd = cmd_low if norm_action == "command" else norm_action
    if effective_media_cmd in (
        "volume_up",
        "volume_down",
        "volume_mute",
        "media_play_pause",
    ):
        if effective_media_cmd == "media_play_pause":
            if mp_ent and mp_ent.startswith("media_player."):
                await hass.services.async_call(
                    "media_player",
                    "media_play_pause",
                    {ATTR_ENTITY_ID: mp_ent},
                    blocking=False,
                )
                return
        else:
            vol_override = coord.volume_overrides.get(
                mp_ent
            ) or coord.volume_overrides.get(remote_ent)
            eff_vol_target = vol_override or mp_ent
            if eff_vol_target and await async_execute_volume_action(
                hass, eff_vol_target, effective_media_cmd
            ):
                return
        if remote_ent and remote_ent.startswith("remote."):
            await hass.services.async_call(
                "remote",
                "send_command",
                {
                    ATTR_ENTITY_ID: remote_ent,
                    "command": (
                        effective_media_cmd.upper()
                        if "android" in combined_ident
                        else effective_media_cmd
                    ),
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

    is_android_tv = platform in (
        "androidtv_remote",
        "androidtv",
        "braviatv",
        "firetv",
    ) or any(
        k in combined_ident
        for k in (
            "shield",
            "android",
            "google_tv",
            "chromecast",
            "bravia",
            "fire_tv",
            "onn",
        )
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
