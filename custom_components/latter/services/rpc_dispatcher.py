"""Private bound-device `LatterRpcDispatcher` for all 20 authenticated RPC methods (`M-P1-28`, `M-P2-24`)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
import re

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from ..areas.actions import async_execute_area_action
from ..areas.catalogs import (
    get_area_available_domains,
    get_area_entities,
    get_areas_summary,
    get_home_wide_entities,
)
from ..const import (
    ALL_RPC_METHODS,
    CONF_ALARM_ENTITY,
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
)
from ..coordinator import LatterCoordinator
from ..doorbell import async_execute_doorbell_intercom
from ..hub_registry import get_latter_system, get_system_config_lock
from ..hub_sync import async_refresh_hub_calendar, async_save_and_broadcast_global_config
from ..media.browse import async_browse_media_items
from ..media.linking import resolve_ma_counterpart_entity
from ..media.lyrics import async_fetch_and_push_music_lyrics
from ..media.volume import async_execute_volume_action
from ..protocol_specs import SHORTCUT_DOMAIN_ACTION_SETS
from ..remotes import async_execute_remote_action
from .rpc_security import (
    _ALARM_ACTION_ALIASES,
    async_enforce_perimeter_security_policy,
    unwrap_rpc_pin_code,
)
from .rpc_slots import (
    async_execute_calendar_create_event,
    async_execute_calendar_delete_event,
    async_execute_intercom_broadcast,
    async_push_active_area_entities,
    async_push_browse_slots,
    async_push_calendar_window,
    parse_bool,
    parse_int,
    parse_opt_float,
)

_LOGGER = logging.getLogger(__name__)

_HEX_COLOR_RE = re.compile(r"#[0-9A-F]{6}")
_EXPECTED_PROTOCOL_CONTRACT = 3
_MIN_QUEUE_OVERRIDE_ITEMS = 2
_MAX_LYRIC_FETCH_LINES = 128
_QUEUE_PAGE_STRIDE = 50
_MAX_CUSTOM_PALETTE_ENTRIES = 24
_MAX_CALENDAR_FETCH_DAYS = 60
_DEFAULT_CALENDAR_FETCH_DAYS = 30
_ALARM_VERBS = ("arm_home", "arm_away", "arm_night", "arm_vacation", "disarm")


class LatterRpcDispatcher:
    """Private in-process dispatcher for all 20 authenticated bound-device RPC methods (`ALL_RPC_METHODS`)."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the private RPC dispatcher."""
        self.hass = hass

    async def async_dispatch(
        self,
        caller_coord: LatterCoordinator,
        rpc_method: str,
        raw_data: Mapping[str, object] | None,
    ) -> object:
        """Validate and execute a single bound-device RPC method directly against `caller_coord`."""
        method = str(rpc_method or "").strip().removeprefix("latter.")
        if method not in ALL_RPC_METHODS:
            _LOGGER.warning(
                "Rejected unsupported RPC '%s' from device '%s'",
                method,
                caller_coord.device_slug,
            )
            return None

        data: dict[str, object] = dict(raw_data) if isinstance(raw_data, Mapping) else {}
        for matched, handler in (
            (method == RPC_DEVICE_HELLO, self._rpc_device_hello),
            (method == RPC_DEVICE_TELEMETRY, self._rpc_device_telemetry),
            (method == RPC_DISPLAY_STATE, self._rpc_display_state),
            (method == RPC_MUSIC_BROWSE, self._rpc_music_browse),
            (method == RPC_SET_ACTIVE_SPEAKER, self._rpc_set_active_speaker),
            (method == RPC_MEDIA_COMMAND, self._rpc_media_command),
            (method == RPC_MEDIA_VOLUME, self._rpc_media_volume),
            (method == RPC_AREA_BROWSE, self._rpc_area_browse),
            (method == RPC_AREA_ACTION, self._rpc_area_action),
            (method == RPC_SET_ACTIVE_AREA, self._rpc_set_active_area),
            (method == RPC_REMOTE_ACTION, self._rpc_remote_action),
            (method == RPC_CALENDAR_FETCH, self._rpc_calendar_fetch),
            (method == RPC_CALENDAR_CREATE_EVENT, self._rpc_calendar_create_event),
            (method == RPC_CALENDAR_DELETE_EVENT, self._rpc_calendar_delete_event),
            (method == RPC_INTERCOM_BROADCAST, self._rpc_intercom_broadcast),
            (method == RPC_DOORBELL_INTERCOM, self._rpc_doorbell_intercom),
            (method == RPC_SAVE_CUSTOM_COLOR, self._rpc_save_custom_color),
            (method == RPC_SHORTCUT_ACTION, self._rpc_shortcut_action),
            (method == RPC_SET_DEVICE_PREFS, self._rpc_set_device_prefs),
            (method == RPC_TIMER_ALARM_STATE, self._rpc_timer_alarm_state),
        ):
            if matched:
                return await handler(caller_coord, data)
        return None

    async def _rpc_device_hello(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        contract = parse_int(data.get("contract"), _EXPECTED_PROTOCOL_CONTRACT)
        if contract != _EXPECTED_PROTOCOL_CONTRACT:
            _LOGGER.warning(
                "Device '%s' reported unsupported Protocol contract %d (expected %d)",
                coord.device_slug,
                contract,
                _EXPECTED_PROTOCOL_CONTRACT,
            )
        await coord.async_handle_device_hello(
            boot_id=str(data.get("boot_id") or "").strip(),
            manifest_raw=str(data.get("manifest") or "").strip(),
            prefs_seq=max(0, parse_int(data.get("prefs_seq"), 0)),
            dirty_prefs=str(data.get("dirty_prefs") or ""),
        )

    async def _rpc_device_telemetry(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        coord.apply_device_telemetry(data)

    async def _rpc_display_state(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        coord.apply_display_state(
            data.get("power_state"),
            data.get("brightness_pct"),
            data.get("screensaver_active"),
        )

    async def _rpc_set_active_speaker(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        speaker = str(data.get("entity_id") or "").strip()
        transfer_queue = parse_bool(data.get("transfer_queue"), default=True)
        if speaker:
            coord.async_set_active_speaker(speaker, transfer_queue=transfer_queue)

    async def _rpc_set_active_area(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        area_val = str(data.get("area_id") or "").strip()
        if area_val:
            coord.async_set_active_area(area_val, sync_device_registry=True)

    async def _rpc_remote_action(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        raw_slot = data.get("slot")
        slot_val = parse_int(raw_slot, 1) if raw_slot is not None else None
        hold_val = parse_opt_float(data.get("hold_secs"))
        if hold_val is not None:
            hold_val = max(0.0, min(5.0, hold_val))
        await async_execute_remote_action(
            self.hass,
            coord,
            slot=slot_val,
            action=str(data.get("action") or ""),
            command=str(data.get("command")) if data.get("command") is not None else None,
            hold_secs=hold_val,
        )

    async def _rpc_intercom_broadcast(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> object:
        return await async_execute_intercom_broadcast(
            self.hass,
            data,
            caller_subentry_id=coord.subentry_id,
        )

    async def _rpc_set_device_prefs(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        base_seq = max(0, parse_int(data.get("base_seq"), 0))
        changes = str(data.get("changes") or "")
        await coord.async_handle_set_device_prefs(
            base_seq=base_seq, changes_raw=changes
        )

    async def _rpc_timer_alarm_state(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        coord.handle_timer_alarm_state(
            timer_running=parse_bool(data.get("timer_running"), default=False),
            timer_paused=parse_bool(data.get("timer_paused"), default=False),
            remaining_sec=max(0, parse_int(data.get("remaining_sec"), 0)),
            ringing=parse_bool(data.get("ringing"), default=False),
            stopwatch_running=parse_bool(data.get("stopwatch_running"), default=False),
            stopwatch_paused=parse_bool(data.get("stopwatch_paused"), default=False),
            stopwatch_elapsed_sec=max(
                0, parse_int(data.get("stopwatch_elapsed_sec"), 0)
            ),
        )

    async def _rpc_media_command(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        command = str(data.get("command") or "toggle")
        speaker = data.get("entity_id")
        seek_pos = parse_opt_float(data.get("seek_position"))
        media_id = str(data.get("media_id") or "").strip() or None
        media_type = str(data.get("media_type") or "").strip() or None
        enqueue = str(data.get("enqueue") or "").strip() or None
        radio_mode = parse_bool(data.get("radio_mode"), default=False)
        queue_item_id = str(data.get("queue_item_id") or "").strip() or None
        raw_shift = data.get("pos_shift")
        pos_shift: int | str | None = (
            raw_shift
            if isinstance(raw_shift, (int, str)) and str(raw_shift).strip() != ""
            else None
        )
        raw_gm = data.get("group_members")
        group_members: list[str] | str | None = (
            [str(x) for x in raw_gm]
            if isinstance(raw_gm, list)
            else (raw_gm if isinstance(raw_gm, str) else None)
        )
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
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        speaker = str(data.get("entity_id") or coord.active_speaker).strip()
        if not speaker:
            return
        vol_target = coord.get_volume_target_entity(speaker)
        action = str(data.get("action") or "set").strip().lower()
        parsed_pct = parse_opt_float(data.get("volume_level"))
        if parsed_pct is not None and parsed_pct < 0.0:
            parsed_pct = None
        await async_execute_volume_action(
            self.hass, vol_target, action, volume_pct=parsed_pct
        )

    async def _fetch_music_browse_items(
        self,
        coord: LatterCoordinator,
        data: dict[str, object],
        mode: str,
        offset: int,
    ) -> list[dict[str, object]]:
        local_speaker = coord.local_speaker
        speaker = str(data.get("speaker") or coord.active_speaker or local_speaker)
        last_speaker = str(data.get("last_speaker") or coord.last_speaker or speaker)
        return await async_browse_media_items(
            hass=self.hass,
            mode=mode,
            speaker=speaker,
            last_speaker=last_speaker,
            local_speaker=local_speaker,
            search=str(data.get("search") or ""),
            default_speaker=str(coord.get_opt(CONF_DEFAULT_SPEAKER) or ""),
            album_sort=str(data.get("album_sort") or "name"),
            artist_album_sort=str(data.get("artist_album_sort") or "year"),
            podcast_sort=str(data.get("podcast_sort") or "newest"),
            fallback_title=coord.last_media_title,
            fallback_artist=coord.last_media_artist,
            fallback_album=coord.last_media_album,
            offset=offset,
        )

    def _resolve_active_queue_total(
        self, speaker: str, items: list[dict[str, object]]
    ) -> int | None:
        ma_target = (
            resolve_ma_counterpart_entity(self.hass, speaker) if speaker else None
        )
        if not ma_target or not items:
            return None
        q_counts = self.hass.data.get(DOMAIN, {}).get("_ma_queue_counts", {})
        raw_q_total = q_counts.get(ma_target) if isinstance(q_counts, Mapping) else None
        if (
            isinstance(raw_q_total, int)
            and raw_q_total > 0
            and (len(items) > _MIN_QUEUE_OVERRIDE_ITEMS or raw_q_total <= len(items))
        ):
            return raw_q_total
        return None

    def _sync_browsed_album_uris(
        self,
        coord: LatterCoordinator,
        mode_norm: str,
        items: list[dict[str, object]],
    ) -> None:
        if mode_norm in ("album_tracks", "current_album_tracks"):
            coord.browsed_album_track_uris = [
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
            coord.browsed_album_track_uris = []

    async def _rpc_music_browse(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        req_id = max(0, parse_int(data.get("req_id"), 0))
        mode = str(data.get("mode") or "speakers")
        page = max(1, parse_int(data.get("page"), 1))
        page_size = parse_int(data.get("page_size"), coord.list_slot_capacity)
        speaker = str(
            data.get("speaker") or coord.active_speaker or coord.local_speaker
        )
        search = str(data.get("search") or "")
        mode_norm = mode.strip().lower()

        if mode_norm == "lyrics_fetch":
            max_lines = max(
                1,
                min(
                    _MAX_LYRIC_FETCH_LINES,
                    parse_int(data.get("page_size"), _MAX_LYRIC_FETCH_LINES),
                ),
            )
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
            (((page - 1) * eff_ps) // _QUEUE_PAGE_STRIDE) * _QUEUE_PAGE_STRIDE
            if mode_norm == "active_queue"
            else 0
        )
        items = await self._fetch_music_browse_items(coord, data, mode, queue_offset)
        total_items_override: int | None = None
        if mode_norm == "active_queue":
            if queue_offset > 0 and not items:
                queue_offset = 0
                items = await self._fetch_music_browse_items(coord, data, mode, 0)
            total_items_override = self._resolve_active_queue_total(speaker, items)
        if mode_norm == "lyrics":
            await async_fetch_and_push_music_lyrics(
                self.hass, coord, req_id=0, speaker=speaker, search=search
            )
        self._sync_browsed_album_uris(coord, mode_norm, items)
        if not items and mode != "speakers":
            queue_offset = 0
            items = [{"name": "No items found", "id": "", "type": "text", "active": False}]

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
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        req_id = max(0, parse_int(data.get("req_id"), 0))
        mode = str(data.get("mode") or "entities").strip().lower()
        page = max(1, parse_int(data.get("page"), 1))
        default_ps = (
            coord.list_slot_capacity if mode == "areas" else coord.card_slot_capacity
        )
        page_size = parse_int(data.get("page_size"), default_ps)
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

        await async_push_browse_slots(
            hass=self.hass,
            coord=coord,
            mode=slot_mode,
            page=page,
            page_size=page_size,
            items=items,
            is_area_slots=(mode != "areas"),
            req_id=req_id,
        )

    async def _rpc_area_action(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        area_id = data.get("area_id")
        if area_id and str(area_id) != coord.active_area_id:
            coord.async_set_active_area(
                str(area_id), handoff_media=False, sync_device_registry=False
            )

        raw_entity_id = str(data.get("entity_id") or "").strip()
        raw_action_wire = str(data.get("action") or "").strip()
        raw_action = raw_action_wire.lower()
        action = _ALARM_ACTION_ALIASES.get(raw_action, raw_action)

        raw_code = data.get("code")
        code = (
            (str(raw_code).strip() or None if raw_code is not None else None)
            if raw_action == "set_color"
            else unwrap_rpc_pin_code(coord, raw_entity_id, raw_action_wire, raw_code)
        )

        entity_id = raw_entity_id
        if entity_id == "home_hub.alarm" or (
            not entity_id and action in _ALARM_VERBS
        ):
            entity_id = coord.alarm_entity or ""
        if not entity_id:
            return

        f_lvl = parse_opt_float(data.get("level"))
        level: int | float | None = None
        if f_lvl is not None:
            level = (
                f_lvl
                if (action == "set_temperature" or entity_id.startswith("climate."))
                else round(f_lvl)
            )

        await async_enforce_perimeter_security_policy(
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
        coord.replace_area_debounce_unsub(None)
        coord.async_notify_listeners()
        await async_push_active_area_entities(self.hass, coord)

    async def _rpc_calendar_fetch(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        req_id = max(0, parse_int(data.get("req_id"), 0))
        days = max(
            1,
            min(
                _MAX_CALENDAR_FETCH_DAYS,
                parse_int(data.get("days"), _DEFAULT_CALENDAR_FETCH_DAYS),
            ),
        )
        sys_obj = get_latter_system(self.hass)
        if sys_obj is not None:
            await async_refresh_hub_calendar(
                sys_obj, days=_DEFAULT_CALENDAR_FETCH_DAYS, coalesce=True
            )
        else:
            await coord.async_refresh_calendar_agenda(days=_DEFAULT_CALENDAR_FETCH_DAYS)

        await async_push_calendar_window(
            self.hass,
            coord,
            req_id=req_id,
            days=days,
            start_date_raw=str(data.get("start_date") or "").strip(),
            end_date_raw=str(data.get("end_date") or "").strip(),
        )

    async def _rpc_calendar_create_event(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        await async_execute_calendar_create_event(self.hass, coord, data)

    async def _rpc_calendar_delete_event(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        await async_execute_calendar_delete_event(self.hass, coord, data)

    async def _rpc_doorbell_intercom(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> dict[str, object]:
        action = str(data.get("action") or "listen_toggle").strip()
        cam_ent = str(data.get("camera_entity") or "").strip() or None
        msg = str(data.get("message") or "").strip()
        nr_level = str(data.get("noise_reduction") or "").strip() or None
        raw_idx = data.get("camera_index")
        cam_idx = (
            parse_int(raw_idx, 0)
            if raw_idx is not None and str(raw_idx).strip() != ""
            else None
        )
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
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        raw_hex = str(data.get("hex_color") or "").strip().upper()
        if not raw_hex.startswith("#"):
            raw_hex = f"#{raw_hex}"
        if not _HEX_COLOR_RE.fullmatch(raw_hex):
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
            global_cfg: dict[str, object] = domain_data.setdefault(
                DATA_GLOBAL_CONFIG, {}
            )
            raw_palettes = global_cfg.get(CONF_CUSTOM_PALETTES)
            palettes: list[dict[str, str]] = [
                {str(k): str(v) for k, v in p.items()}
                for p in (raw_palettes if isinstance(raw_palettes, list) else ())
                if isinstance(p, dict)
            ]
            existing = next(
                (p for p in palettes if str(p.get("hex", "")).upper() == raw_hex),
                None,
            )
            if existing is not None:
                if data.get("name"):
                    existing["name"] = name
            else:
                palettes.insert(0, {"name": name, "hex": raw_hex})
                palettes = palettes[:_MAX_CUSTOM_PALETTE_ENTRIES]
            await async_save_and_broadcast_global_config(
                self.hass, {CONF_CUSTOM_PALETTES: palettes}
            )

    async def _rpc_shortcut_action(
        self, coord: LatterCoordinator, data: dict[str, object]
    ) -> None:
        raw_entity_id = str(data.get("entity_id") or "").strip()
        raw_action_wire = str(data.get("action") or "").strip()
        entity_id = raw_entity_id.lower()
        action = raw_action_wire.lower()
        code = unwrap_rpc_pin_code(
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

        await async_enforce_perimeter_security_policy(
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
        existing = getattr(sys_obj, "rpc_dispatcher", None)
        if isinstance(existing, LatterRpcDispatcher):
            return existing
        created = LatterRpcDispatcher(hass)
        sys_obj.rpc_dispatcher = created
        return created
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
    data: Mapping[str, object] | None,
) -> object:
    """Dispatch a reassembled RPC from `coord`'s bound `System: RPC Outbox` entity via `LatterRpcDispatcher`."""
    return await get_rpc_dispatcher(hass).async_dispatch(coord, service_name, data)
