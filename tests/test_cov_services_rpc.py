"""Coverage tests for services/rpc_slots.py, rpc_dispatcher.py, rpc_receiver.py, and public_actions.py."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import logging
from typing import Any
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import Context, Event, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.util import dt as dt_util
import pytest

from custom_components.latter.const import (
    ALL_RPC_METHODS,
    CONF_ALARM_ENTITY,
    CONF_BROADCAST_SPEAKERS,
    CONF_CALENDAR_ENTITIES,
    CONF_CUSTOM_PALETTES,
    CONF_REMOTES_LIST,
    DOMAIN,
    RPC_AREA_ACTION,
    RPC_AREA_BROWSE,
    RPC_CALENDAR_FETCH,
    RPC_DEVICE_HELLO,
    RPC_MEDIA_VOLUME,
    RPC_MUSIC_BROWSE,
    RPC_REMOTE_ACTION,
    RPC_SAVE_CUSTOM_COLOR,
    RPC_SET_ACTIVE_SPEAKER,
    SERVICE_INTERCOM_BROADCAST,
    SERVICE_NOTIFY,
    SERVICE_RESET_DEVICE,
    SERVICE_SET_ACTIVE_AREA,
)
from custom_components.latter.hub_registry import get_domain_data, get_global_config
from custom_components.latter.media.browse import clear_browse_cache
from custom_components.latter.media.linking import (
    async_set_ma_player_link,
    clear_ma_counterpart_cache,
    resolve_ma_counterpart_entity,
)
from custom_components.latter.presence.ble_fabric import get_ble_fabric
from custom_components.latter.repairs_keys import slot_push_failing_issue_id
from custom_components.latter.services import rpc_dispatcher as rpc_dispatcher_mod
from custom_components.latter.services.rpc_dispatcher import (
    LatterRpcDispatcher,
    _get_system_pin_lockout,
    async_enforce_perimeter_security_policy,
    get_rpc_dispatcher,
)
from custom_components.latter.services.rpc_receiver import (
    DEDUP_HISTORY_LIMIT,
    PARTIAL_TTL_SECONDS,
    RpcReassembler,
    parse_rpc_frame,
)
from custom_components.latter.services.rpc_slots import (
    _is_calendar_deletable,
    _is_calendar_writable,
    _match_occupied_area_speakers,
    _pack_browse_slot_rows,
    _parse_calendar_event_window,
    _parse_speaker_list,
    _speaker_matches_coord,
    async_execute_calendar_create_event,
    async_execute_calendar_delete_event,
    async_execute_intercom_broadcast,
    async_push_browse_slots,
    async_push_calendar_window,
    parse_bool,
    parse_int,
    parse_opt_float,
    resolve_occupied_area_ids,
)
from tests.helpers import (
    add_mock_entry,
    ensure_area,
    get_service_calls,
    mock_service,
    register_device,
    register_entity,
)


def test_rpc_slots_parsers_and_receiver_frame_reassembler_edge_cases() -> None:
    """Exercise rpc_slots scalar/window parsers and rpc_receiver header/envelope/TTL/dedup edges."""
    # 1. parse_bool across string literals, numerics, None, and unrecognized fallback
    assert parse_bool(None, default=True) is True
    assert parse_bool(None, default=False) is False
    assert parse_bool(True) is True
    assert parse_bool(0) is False
    assert parse_bool(2.5) is True
    for truthy in ("true", "TRUE", "1", "yes", "on", " Yes "):
        assert parse_bool(truthy, default=False) is True
    for falsy in ("false", "0", "no", "off", "", "   "):
        assert parse_bool(falsy, default=True) is False
    assert parse_bool("unrecognized", default=True) is True
    assert parse_bool("unrecognized", default=False) is False

    # 2. parse_int across blank strings, floats, non-finite values, and invalid strings
    assert parse_int(None, 4) == 4
    assert parse_int(True, 4) == 4
    assert parse_int("   ", 7) == 7
    assert parse_int("42", 0) == 42
    assert parse_int("3.9", 0) == 3
    assert parse_int("inf", 5) == 5
    assert parse_int("nan", 5) == 5
    assert parse_int("not-a-number", 9) == 9

    # 3. parse_opt_float across blank strings, invalid strings, non-finite values, and valid numbers
    assert parse_opt_float(None) is None
    assert parse_opt_float(False) is None
    assert parse_opt_float("   ") is None
    assert parse_opt_float("not-a-float") is None
    assert parse_opt_float("nan") is None
    assert parse_opt_float("inf") is None
    assert parse_opt_float("12.5") == 12.5

    # 4. _parse_speaker_list for collections, comma-separated strings, and empty input
    assert _parse_speaker_list([" media_player.a ", "", "media_player.b"]) == [
        "media_player.a",
        "media_player.b",
    ]
    assert _parse_speaker_list(("media_player.x", " ")) == ["media_player.x"]
    assert _parse_speaker_list("media_player.one, , media_player.two ") == [
        "media_player.one",
        "media_player.two",
    ]
    assert _parse_speaker_list(None) == []

    # 5. _parse_calendar_event_window clamping for all-day and timed inverted ranges
    all_day_flag, sd, ed = _parse_calendar_event_window(
        {"all_day": True, "start_date": "2026-11-20", "end_date": "2026-11-20"}
    )
    assert all_day_flag is True
    assert sd == date(2026, 11, 20)
    assert ed == date(2026, 11, 21)

    timed_flag, start_dt, end_dt = _parse_calendar_event_window(
        {
            "all_day": False,
            "start_date_time": "2026-11-20 14:00:00",
            "end_date_time": "2026-11-20 13:00:00",
        }
    )
    assert timed_flag is False
    assert isinstance(start_dt, datetime)
    assert isinstance(end_dt, datetime)
    assert end_dt - start_dt == timedelta(minutes=60)

    # 6. _pack_browse_slot_rows with queue metadata fields
    rows = _pack_browse_slot_rows(
        [
            {
                "name": "Track One",
                "id": "library://track/1",
                "type": "track",
                "active": True,
                "queue_item_id": "qi_1",
                "is_current": True,
            }
        ],
        "active_queue",
        include_levels=False,
    )
    assert rows == ["Track One\x1flibrary://track/1\x1ftrack\x1f1\x1f-1\x1fqi_1\x1f1"]

    # 7. rpc_receiver header & envelope validation
    assert parse_rpc_frame("onlytwo:1|{}") is None
    assert parse_rpc_frame("a1b2:notint:1/1|{}") is None
    assert parse_rpc_frame("a1b2:1:x/1|{}") is None
    assert parse_rpc_frame("a1b2:1:1/y|{}") is None
    assert parse_rpc_frame("a1b2:0:1/1|{}") is None

    reassembler = RpcReassembler()
    assert reassembler.feed("a1b2:1:1/1|{bad_json", now_mono=10.0) is None
    assert reassembler.feed("a1b2:2:1/1|[1,2,3]", now_mono=10.0) is None
    assert reassembler.feed('a1b2:3:1/1|{"s":""}', now_mono=10.0) is None
    assert reassembler.feed('a1b2:4:1/1|{"s":"caf\u00e9"}', now_mono=10.0) is None
    assert reassembler.feed('a1b2:5:1/1|{"s":"latter.device_hello"}', now_mono=10.0) == (
        "device_hello",
        {},
    )
    assert reassembler.feed('a1b2:6:1/1|{"s":"device_hello","d":["bad"]}', now_mono=10.0) is None

    # 8. Inflight partial TTL pruning (_prune)
    assert reassembler.feed('a1b2:7:1/2|{"s":"device', now_mono=20.0) is None
    assert ("a1b2", 7) in reassembler._inflight
    assert (
        reassembler.feed(
            'a1b2:8:1/1|{"s":"device_hello"}',
            now_mono=20.0 + PARTIAL_TTL_SECONDS + 2.0,
        )
        == ("device_hello", {})
    )
    assert ("a1b2", 7) not in reassembler._inflight

    # 9. seed_silent across a boot_id rollover clears inflight & completed history
    assert reassembler.feed('a1b2:9:1/2|{"s":"part', now_mono=50.0) is None
    assert ("a1b2", 9) in reassembler._inflight
    reassembler.seed_silent('c0de:1:1/1|{"s":"device_hello"}')
    assert reassembler._last_boot_id == "c0de"
    assert reassembler._inflight == {}
    assert list(reassembler._completed.keys()) == [("c0de", 1)]

    # 10. Completed dedup history eviction beyond DEDUP_HISTORY_LIMIT
    for seq in range(2, DEDUP_HISTORY_LIMIT + 6):
        res = reassembler.feed(
            f'c0de:{seq}:1/1|{{"s":"device_hello"}}',
            now_mono=100.0 + seq,
        )
        assert res == ("device_hello", {})
    assert len(reassembler._completed) == DEDUP_HISTORY_LIMIT
    assert ("c0de", 1) not in reassembler._completed
    assert ("c0de", DEDUP_HISTORY_LIMIT + 5) in reassembler._completed


async def test_rpc_dispatcher_standalone_singletons_and_calendar_feature_defaults(
    hass: Any,
) -> None:
    """Verify domain-level fallback singletons without a hub and calendar feature defaults."""
    lockout_a = _get_system_pin_lockout(hass)
    lockout_b = _get_system_pin_lockout(hass)
    assert lockout_a is lockout_b
    assert get_domain_data(hass).pin_lockout is lockout_a

    disp_a = get_rpc_dispatcher(hass)
    disp_b = get_rpc_dispatcher(hass)
    assert isinstance(disp_a, LatterRpcDispatcher)
    assert disp_a is disp_b
    assert get_domain_data(hass).rpc_dispatcher is disp_a

    # Calendar entities lacking `supported_features` attribute (or absent state) default to True
    hass.states.async_set("calendar.unadorned", "off", {"friendly_name": "Unadorned"})
    assert _is_calendar_writable(hass, "calendar.unadorned") is True
    assert _is_calendar_deletable(hass, "calendar.unadorned") is True
    assert _is_calendar_writable(hass, "calendar.nonexistent") is True
    assert _is_calendar_deletable(hass, "calendar.nonexistent") is True


async def test_rpc_slots_push_failures_recovery_and_headless_skip(
    hass: Any, setup_latter_hub: Any, caplog: Any
) -> None:
    """Verify slot-push failure counting, rate-limited warnings, Repairs creation/cleanup, and missing service skip."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    issue_reg = ir.async_get(hass)
    issue_id = slot_push_failing_issue_id(coord.subentry_id)

    def _fail_slots(_call: Any) -> None:
        raise RuntimeError("esphome transport disconnected")

    mock_service(hass, "esphome", "pocket_assistant_latter_set_slots", _fail_slots)

    with caplog.at_level(logging.WARNING):
        for attempt in range(1, 6):
            await async_push_browse_slots(
                hass,
                coord,
                "albums",
                page=1,
                items=[{"name": "Blue Train", "id": "library://album/1", "type": "album"}],
            )
            assert get_domain_data(hass).slot_push_failures[coord.subentry_id] == attempt

    # Warning was rate-limited to once within the 600s window; 5th failure created the Repairs issue
    warn_msgs = [
        rec.message
        for rec in caplog.records
        if "Failed to push pocket_assistant_latter_set_slots slots" in rec.message
    ]
    assert len(warn_msgs) == 1
    assert (DOMAIN, issue_id) in issue_reg.issues

    # Recovering the service clears the failure counter and deletes the Repairs issue
    pushed_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        "pocket_assistant_latter_set_slots",
        lambda call: pushed_calls.append(dict(call.data)),
    )
    await async_push_browse_slots(
        hass,
        coord,
        "albums",
        page=1,
        items=[{"name": "Blue Train", "id": "library://album/1", "type": "album"}],
    )
    assert coord.subentry_id not in get_domain_data(hass).slot_push_failures
    assert (DOMAIN, issue_id) not in issue_reg.issues
    assert len(pushed_calls) == 1

    # When the ESPHome slot service is absent, async_push_browse_slots returns cleanly without error
    hass.services.async_remove("esphome", "pocket_assistant_latter_set_slots")
    await async_push_browse_slots(
        hass,
        coord,
        "albums",
        page=1,
        items=[{"name": "Blue Train", "id": "library://album/1", "type": "album"}],
    )
    assert len(pushed_calls) == 1
    mock_service(hass, "esphome", "pocket_assistant_latter_set_slots")

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_rpc_slots_calendar_window_and_crud_edge_cases(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise calendar window clamping, missing/failing calendar view pushes, and CRUD fallbacks."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    today = dt_util.now().date()

    # 1. Window date defaults, far-future end_d clamp, and 180-day ceiling
    cal_view_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        "pocket_assistant_latter_set_calendar_view",
        lambda call: cal_view_calls.append(dict(call.data)),
    )
    await async_push_calendar_window(hass, coord, req_id=1)
    assert coord.last_cal_window is not None
    assert coord.last_cal_window[0] == today - timedelta(days=35)
    assert coord.last_cal_window[1] == today + timedelta(days=62)

    far_start = today + timedelta(days=200)
    await async_push_calendar_window(
        hass, coord, req_id=2, start_date_raw=far_start.isoformat(), end_date_raw=""
    )
    assert coord.last_cal_window == (far_start, far_start + timedelta(days=62))

    await async_push_calendar_window(
        hass, coord, req_id=3, start_date_raw="2026-01-01", end_date_raw="2027-01-01"
    )
    assert coord.last_cal_window == (
        date(2026, 1, 1),
        date(2026, 1, 1) + timedelta(days=180),
    )
    assert len(cal_view_calls) >= 3

    # 2. Failing calendar view push catches and breaks cleanly
    def _fail_cal_view(_call: Any) -> None:
        raise RuntimeError("calendar view push failed")

    mock_service(hass, "esphome", "pocket_assistant_latter_set_calendar_view", _fail_cal_view)
    await async_push_calendar_window(hass, coord, req_id=4)

    # 3. Missing calendar view service returns early cleanly
    hass.services.async_remove("esphome", "pocket_assistant_latter_set_calendar_view")
    await async_push_calendar_window(hass, coord, req_id=5)
    mock_service(hass, "esphome", "pocket_assistant_latter_set_calendar_view")

    # 4. Calendar CRUD: read-only rejection and no-writable-calendar early return
    hass.states.async_set(
        "calendar.readonly_feed",
        "off",
        {"friendly_name": "Readonly", "supported_features": 0},
    )
    get_global_config(hass)[CONF_CALENDAR_ENTITIES] = ["calendar.readonly_feed"]

    with pytest.raises(ServiceValidationError) as exc_ro:
        await async_execute_calendar_create_event(
            hass,
            coord,
            {"calendar_entity": "calendar.readonly_feed", "summary": "Blocked"},
        )
    assert exc_ro.value.translation_key == "not_supported"

    # Empty calendar_entity with only read-only calendars logs warning and returns cleanly
    await async_execute_calendar_create_event(hass, coord, {"summary": "Skipped"})

    # 5. Add writable/deletable calendar and exercise service-call create, rrule validation, entity create, and delete fallback
    hass.states.async_set(
        "calendar.site_schedule",
        "off",
        {"friendly_name": "Site Schedule", "supported_features": 3},
    )
    get_global_config(hass)[CONF_CALENDAR_ENTITIES] = [
        "calendar.readonly_feed",
        "calendar.site_schedule",
    ]
    mock_service(
        hass,
        "calendar",
        "get_events",
        lambda _call: {"calendar.site_schedule": {"events": []}},
        supports_response=SupportsResponse.ONLY,
    )
    created_svc_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "calendar",
        "create_event",
        lambda call: created_svc_calls.append(dict(call.data)),
    )

    # Auto-resolve first writable calendar and execute timed service-call create with location & description
    await async_execute_calendar_create_event(
        hass,
        coord,
        {
            "summary": "Quarterly Sync",
            "start_date_time": "2026-11-22 10:00:00",
            "end_date_time": "2026-11-22 11:00:00",
            "location": "Main Hall",
            "description": "Review Site milestones",
        },
    )
    assert len(created_svc_calls) == 1
    assert created_svc_calls[0]["entity_id"] == "calendar.site_schedule"
    assert created_svc_calls[0]["start_date_time"] == "2026-11-22 10:00:00"
    assert created_svc_calls[0]["end_date_time"] == "2026-11-22 11:00:00"
    assert created_svc_calls[0]["location"] == "Main Hall"
    assert created_svc_calls[0]["description"] == "Review Site milestones"

    # Invalid rrule raises ServiceValidationError
    with pytest.raises(ServiceValidationError) as exc_rr:
        await async_execute_calendar_create_event(
            hass,
            coord,
            {
                "calendar_entity": "calendar.site_schedule",
                "summary": "Bad Recurrence",
                "rrule": "EVERY_TUESDAY",
            },
        )
    assert exc_rr.value.translation_key == "not_supported"

    # Valid rrule with entity-level async_create_event forwards description
    entity_created: list[dict[str, Any]] = []

    class _CalEntityStub:
        async def async_create_event(self, **kwargs: Any) -> None:
            entity_created.append(kwargs)

    class _CalComponentStub:
        def get_entity(self, eid: str) -> Any:
            return _CalEntityStub() if eid == "calendar.site_schedule" else None

    hass.data["calendar"] = _CalComponentStub()
    await async_execute_calendar_create_event(
        hass,
        coord,
        {
            "calendar_entity": "calendar.site_schedule",
            "summary": "Weekly Standup",
            "rrule": "FREQ=WEEKLY",
            "description": "Bring status updates",
            "start_date_time": "2026-11-23 09:00:00",
            "end_date_time": "2026-11-23 09:30:00",
        },
    )
    assert len(entity_created) == 1
    assert entity_created[0]["description"] == "Bring status updates"

    # Delete validation error (missing uid or non-deletable calendar)
    hass.data.pop("calendar", None)
    with pytest.raises(ServiceValidationError) as exc_del_bad:
        await async_execute_calendar_delete_event(
            hass,
            coord,
            {"calendar_entity": "calendar.readonly_feed", "uid": "evt-1"},
        )
    assert exc_del_bad.value.translation_key == "not_supported"

    with pytest.raises(ServiceValidationError) as exc_del_empty:
        await async_execute_calendar_delete_event(
            hass,
            coord,
            {"calendar_entity": "calendar.site_schedule", "uid": ""},
        )
    assert exc_del_empty.value.translation_key == "not_supported"

    # Delete via calendar.delete_event service fallback when entity method is absent
    deleted_svc_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "calendar",
        "delete_event",
        lambda call: deleted_svc_calls.append(dict(call.data)),
    )
    await async_execute_calendar_delete_event(
        hass,
        coord,
        {
            "calendar_entity": "calendar.site_schedule",
            "uid": "evt-99",
            "recurrence_id": "20261123T090000Z",
            "recurrence_range": "THISANDFUTURE",
        },
    )
    assert deleted_svc_calls == [
        {
            "entity_id": "calendar.site_schedule",
            "uid": "evt-99",
            "recurrence_id": "20261123T090000Z",
            "recurrence_range": "THISANDFUTURE",
        }
    ]

    # Without entity delete method AND without calendar.delete_event service, raises not_supported
    hass.services.async_remove("calendar", "delete_event")
    with pytest.raises(ServiceValidationError) as exc_del_nosvc:
        await async_execute_calendar_delete_event(
            hass,
            coord,
            {"calendar_entity": "calendar.site_schedule", "uid": "evt-99"},
        )
    assert exc_del_nosvc.value.translation_key == "not_supported"

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_intercom_broadcast_speaker_matching_and_public_actions_edge_cases(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise speaker matching, broadcast empty/skipped reasons, and public action edge paths."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    ent_reg = er.async_get(hass)

    # 1. _speaker_matches_coord: empty entity_id and sibling ESPHome entity resolving to same MA player
    assert _speaker_matches_coord(hass, ent_reg, "", coord) is False

    ma_entry = add_mock_entry(
        hass,
        domain="music_assistant",
        title="Music Assistant",
        entry_id="ma_match_entry",
        data={},
    )
    ma_dev = register_device(
        hass,
        config_entry_id=ma_entry.entry_id,
        entry_domain="music_assistant",
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:01")},
        identifiers={("music_assistant", "aa:bb:cc:dd:ee:01")},
        name="Pocket Sendspin",
        manufacturer="Latter",
    )
    ma_ent = register_entity(
        hass,
        "media_player.pocket_sendspin",
        platform="music_assistant",
        unique_id="ma_pocket_match",
        device_id=ma_dev.id,
        config_entry=ma_entry,
        area_id="living_room",
    )
    hass.states.async_set(ma_ent.entity_id, "idle", {"friendly_name": "Pocket Sendspin"})
    async_set_ma_player_link(hass, coord, ma_ent.entity_id)

    # Register a second ESPHome media_player on the same MAC/device so entity_id != local_speaker
    aux_ent = register_entity(
        hass,
        "media_player.pocket_assistant_aux",
        platform="esphome",
        unique_id="aux_pocket_spk",
        config_entry=hass.config_entries.async_get_entry("esp_entry_pocket_assistant"),
        device_id=coord.esphome_device_id,
        area_id="living_room",
    )
    hass.states.async_set(aux_ent.entity_id, "idle", {"friendly_name": "Pocket Aux"})
    clear_ma_counterpart_cache(hass)
    assert coord.local_ma_speaker == ma_ent.entity_id
    assert resolve_ma_counterpart_entity(hass, aux_ent.entity_id) == ma_ent.entity_id
    assert _speaker_matches_coord(hass, ent_reg, aux_ent.entity_id, coord) is True

    # 2. _match_occupied_area_speakers: empty occupied_areas and offline speaker skipping
    assert _match_occupied_area_speakers(hass, [ma_ent.entity_id], set()) == []
    offline_ent = register_entity(
        hass,
        "media_player.kitchen_offline",
        platform="music_assistant",
        unique_id="ma_kitchen_off",
        config_entry=ma_entry,
        area_id="kitchen",
    )
    hass.states.async_set(offline_ent.entity_id, "unavailable", {"friendly_name": "Kitchen Offline"})
    assert (
        _match_occupied_area_speakers(
            hass, [offline_ent.entity_id, ma_ent.entity_id], {"living_room", "kitchen"}
        )
        == [ma_ent.entity_id]
    )

    # 3. Scoped broadcast with empty pool raises no_broadcast_speakers
    get_global_config(hass)[CONF_BROADCAST_SPEAKERS] = []
    with pytest.raises(ServiceValidationError) as exc_pool:
        await async_execute_intercom_broadcast(
            hass, {"target_device": "occupied_areas", "message": "Hello"}
        )
    assert exc_pool.value.translation_key == "no_broadcast_speakers"

    # 4. Zero occupied areas: notify skips cleanly and intercom_broadcast returns reason="no_occupied_areas"
    fabric = get_ble_fabric(hass)
    assert coord._ble_tracker is not None
    coord._ble_tracker.current_area_id = None
    coord._ble_tracker.is_away = True
    fabric.notify_occupancy_listeners()
    assert resolve_occupied_area_ids(hass, "occupied_areas", "occupied_areas") == set()

    get_global_config(hass)[CONF_BROADCAST_SPEAKERS] = [ma_ent.entity_id]
    resp_no_occ = await hass.services.async_call(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        {"target_device": "occupied_areas", "message": "Anyone home?"},
        blocking=True,
        return_response=True,
    )
    assert resp_no_occ == {
        "delivered": False,
        "targets": [],
        "reason": "no_occupied_areas",
    }

    # Non-scoped broadcast with only offline pool speakers returns reason="no_targets"
    get_global_config(hass)[CONF_BROADCAST_SPEAKERS] = [offline_ent.entity_id]
    resp_no_targets = await hass.services.async_call(
        DOMAIN,
        SERVICE_INTERCOM_BROADCAST,
        {"target_device": "all", "message": "Check offline"},
        blocking=True,
        return_response=True,
    )
    assert resp_no_targets == {
        "delivered": False,
        "targets": [],
        "reason": "no_targets",
    }

    # 5. public_actions: notify with zero targets returns cleanly without dispatching
    notify_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        "pocket_assistant_latter_show_notification",
        lambda call: notify_calls.append(dict(call.data)),
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFY,
        {"target_device": "occupied_areas", "title": "Empty", "message": "Skip me"},
        blocking=True,
    )
    assert notify_calls == []

    # public_actions: notify catches failing direct esphome show_notification cleanly
    def _fail_notify(_call: Any) -> None:
        raise RuntimeError("display asleep")

    mock_service(hass, "esphome", "pocket_assistant_latter_show_notification", _fail_notify)
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NOTIFY,
        {"target_device": coord.device_slug, "title": "Alert", "message": "Door open"},
        blocking=True,
    )
    assert coord.alert_title == "Alert"
    assert coord.alert_message == "Door open"

    # public_actions: set_active_area updates active_area_id and ignores whitespace-only area_id
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ACTIVE_AREA,
        {"target_device": coord.device_slug, "area_id": "kitchen"},
        blocking=True,
    )
    assert coord.active_area_id == "kitchen"
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_ACTIVE_AREA,
        {"target_device": coord.device_slug, "area_id": "   "},
        blocking=True,
    )
    assert coord.active_area_id == "kitchen"

    # require_admin_if_user_call with no user_id (internal/automation Context) succeeds cleanly
    reset_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        "pocket_assistant_latter_factory_reset",
        lambda call: reset_calls.append(dict(call.data)),
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_RESET_DEVICE,
        {
            "target_device": coord.device_slug,
            "device_settings": True,
            "latter_options": False,
        },
        blocking=True,
        context=Context(),
    )
    assert len(reset_calls) == 1

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_rpc_dispatcher_perimeter_media_browse_area_and_palette_edges(
    hass: Any, setup_latter_hub: Any, caplog: Any
) -> None:
    """Exercise all remaining rpc_dispatcher branches across security, media, browse, area, calendar, and palettes."""
    clear_browse_cache()
    entry, sys_obj, coord = await setup_latter_hub(hass)
    dispatcher = sys_obj.rpc_dispatcher

    # 1. Perimeter alarm policy: home_hub.alarm alias, code_arm_required, invalid native format, and invalid entity
    get_global_config(hass)[CONF_ALARM_ENTITY] = "alarm_control_panel.main"
    hass.states.async_set(
        "alarm_control_panel.main",
        "disarmed",
        {"code_format": "number", "code_arm_required": True},
    )
    with pytest.raises(ServiceValidationError) as exc_arm_pin:
        await async_enforce_perimeter_security_policy(
            coord, "home_hub.alarm", "arm_away", provided_code=None
        )
    assert exc_arm_pin.value.translation_key == "security_pin_required"

    with pytest.raises(ServiceValidationError) as exc_bad_fmt:
        await async_enforce_perimeter_security_policy(
            coord, "alarm_control_panel.main", "disarm", provided_code="abcd"
        )
    assert exc_bad_fmt.value.translation_key == "security_pin_invalid"
    coord.pin_lockout.reset()
    sys_obj.pin_lockout.reset()

    # Non-dotted entity or unset alarm_entity returns early cleanly
    await async_enforce_perimeter_security_policy(coord, "nodot", "unlock")
    get_global_config(hass)[CONF_ALARM_ENTITY] = ""
    await async_enforce_perimeter_security_policy(coord, "home_hub.alarm", "disarm")

    # 2. device_hello contract version warning
    with caplog.at_level(logging.WARNING):
        await dispatcher.async_dispatch(
            coord,
            RPC_DEVICE_HELLO,
            {"contract": 2, "boot_id": "boot_v2", "manifest": "{}"},
        )
    assert "unsupported Protocol contract 2" in caplog.text

    # 3. set_active_speaker RPC (non-empty and empty entity_id)
    hass.states.async_set("media_player.office_speaker", "idle", {"friendly_name": "Office Speaker"})
    await dispatcher.async_dispatch(
        coord,
        RPC_SET_ACTIVE_SPEAKER,
        {"entity_id": "media_player.office_speaker", "transfer_queue": "false"},
    )
    assert coord.active_speaker == "media_player.office_speaker"
    await dispatcher.async_dispatch(coord, RPC_SET_ACTIVE_SPEAKER, {"entity_id": ""})
    assert coord.active_speaker == "media_player.office_speaker"

    # 4. remote_action hold_secs clamping (> 5.0 -> 5.0)
    remote_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "remote",
        "send_command",
        lambda call: remote_calls.append(dict(call.data)),
    )
    rem_ent = register_entity(
        hass,
        "remote.studio_tv",
        platform="androidtv_remote",
        area_id="living_room",
    )
    hass.states.async_set(rem_ent.entity_id, "on", {"friendly_name": "Studio TV"})
    get_global_config(hass)[CONF_REMOTES_LIST] = [rem_ent.entity_id]
    coord.async_set_active_area("living_room")
    await dispatcher.async_dispatch(
        coord,
        RPC_REMOTE_ACTION,
        {"slot": 1, "action": "long_press", "command": "select", "hold_secs": 12.0},
    )
    await hass.async_block_till_done()
    assert {
        "entity_id": rem_ent.entity_id,
        "command": "DPAD_CENTER",
        "hold_secs": 5.0,
    } in remote_calls

    # 5. media_volume: empty active_speaker returns early; negative volume_level normalizes to None
    prev_spk = coord.active_speaker
    coord.active_speaker = ""
    await dispatcher.async_dispatch(coord, RPC_MEDIA_VOLUME, {"action": "up"})
    coord.active_speaker = prev_spk
    vol_up_calls: list[dict[str, Any]] = []
    mock_service(
        hass,
        "media_player",
        "volume_up",
        lambda call: vol_up_calls.append(dict(call.data)),
    )
    hass.states.async_set(
        coord.active_speaker,
        "playing",
        {"volume_level": 0.4, "supported_features": 1024},
    )
    await dispatcher.async_dispatch(
        coord, RPC_MEDIA_VOLUME, {"action": "up", "volume_level": -10}
    )
    await hass.async_block_till_done()
    assert len(vol_up_calls) == 1

    # 6. music_browse: _resolve_active_queue_total edges, active_queue offset fallback, and lyrics mode
    assert dispatcher._resolve_active_queue_total("", []) is None
    assert dispatcher._resolve_active_queue_total("media_player.unlinked", [{"id": "1"}]) is None

    ma_entry = add_mock_entry(
        hass,
        domain="music_assistant",
        title="Music Assistant",
        entry_id="ma_q_entry",
        data={},
    )
    if hasattr(ma_entry, "mock_state"):
        ma_entry.mock_state(hass, ConfigEntryState.LOADED)

    class _FakeQueues:
        def get(self, _qid: str) -> None:
            return None

        async def fetch_player_queue_items(
            self, _qid: str, *, limit: int = 50, offset: int = 0
        ) -> list[dict[str, Any]]:
            _ = limit
            if offset > 0:
                return []
            return [
                {
                    "queue_item_id": f"qi_{idx}",
                    "media_item": {"name": f"Track {idx}", "uri": f"library://track/{idx}"},
                }
                for idx in (1, 2, 3)
            ]

    class _FakeMass:
        player_queues = _FakeQueues()

    ma_entry.runtime_data = _FakeMass()
    ma_q_ent = register_entity(
        hass,
        "media_player.pocket_ma_queue",
        platform="music_assistant",
        unique_id="ma_q_uid",
        config_entry=ma_entry,
    )
    hass.states.async_set(ma_q_ent.entity_id, "playing", {"friendly_name": "Pocket MA"})
    async_set_ma_player_link(hass, coord, ma_q_ent.entity_id)
    coord.active_speaker = coord.local_speaker
    clear_ma_counterpart_cache(hass)

    # Non-qualifying queue count (1 item with stored count 10 > len(items)) returns None
    get_domain_data(hass).ma_queue_counts[ma_q_ent.entity_id] = 10
    assert dispatcher._resolve_active_queue_total(coord.local_speaker, [{"id": "t1"}]) is None

    slot_pushes: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        "pocket_assistant_latter_set_slots",
        lambda call: slot_pushes.append(dict(call.data)),
    )
    # page=11 with page_size=5 computes queue_offset=50 -> empty -> retries offset=0!
    await dispatcher.async_dispatch(
        coord,
        RPC_MUSIC_BROWSE,
        {"req_id": 7, "mode": "active_queue", "page": 11, "page_size": 5},
    )
    assert any(
        p.get("mode") == "active_queue" and "Track 1" in str(p.get("slots", ""))
        for p in slot_pushes
    )

    # mode="lyrics" triggers async_fetch_and_push_music_lyrics
    lyric_pushes: list[dict[str, Any]] = []
    mock_service(
        hass,
        "esphome",
        "pocket_assistant_latter_set_music_lyrics",
        lambda call: lyric_pushes.append(dict(call.data)),
    )
    await dispatcher.async_dispatch(
        coord, RPC_MUSIC_BROWSE, {"mode": "lyrics", "search": "Blue Train"}
    )
    assert coord.lyrics_watch_active is True
    assert len(lyric_pushes) >= 1

    # 7. area_browse on an empty Area emits mode="area_empty"
    ensure_area(hass, "Patio", area_id="patio")
    slot_pushes.clear()
    await dispatcher.async_dispatch(
        coord, RPC_AREA_BROWSE, {"mode": "entities", "area_id": "patio"}
    )
    assert any(p.get("mode") == "area_empty" for p in slot_pushes)

    # 8. area_action: switching active_area_id and empty entity_id early return
    light_ent = register_entity(hass, "light.kitchen_spot", platform="hue", area_id="kitchen")
    hass.states.async_set(light_ent.entity_id, "off", {"friendly_name": "Kitchen Spot"})
    coord.async_set_active_area("living_room")
    await dispatcher.async_dispatch(
        coord,
        RPC_AREA_ACTION,
        {"area_id": "kitchen", "entity_id": light_ent.entity_id, "action": "toggle"},
    )
    assert coord.active_area_id == "kitchen"

    await hass.async_block_till_done()
    calls_before_empty = len(get_service_calls(hass))
    await dispatcher.async_dispatch(
        coord, RPC_AREA_ACTION, {"entity_id": "", "action": "toggle"}
    )
    assert not any(
        c.domain == "light" for c in get_service_calls(hass)[calls_before_empty:]
    )

    # 9. calendar_fetch fallback when get_latter_system returns None
    with (
        patch.object(rpc_dispatcher_mod, "get_latter_system", return_value=None),
        patch.object(
            coord,
            "async_refresh_calendar_agenda",
            wraps=coord.async_refresh_calendar_agenda,
        ) as refresh_spy,
    ):
        await dispatcher.async_dispatch(coord, RPC_CALENDAR_FETCH, {"req_id": 12, "days": 14})
        refresh_spy.assert_awaited_once_with(days=30)

    # 10. save_custom_color updates an existing palette entry's name in place without duplicating
    await dispatcher.async_dispatch(
        coord, RPC_SAVE_CUSTOM_COLOR, {"hex_color": "#445566", "name": "Slate"}
    )
    await dispatcher.async_dispatch(
        coord, RPC_SAVE_CUSTOM_COLOR, {"hex_color": "#445566", "name": "Storm Slate"}
    )
    await dispatcher.async_dispatch(coord, RPC_SAVE_CUSTOM_COLOR, {"hex_color": "#445566"})
    palettes = get_global_config(hass).get(CONF_CUSTOM_PALETTES)
    assert isinstance(palettes, list)
    matching = [p for p in palettes if p.get("hex") == "#445566"]
    assert matching == [{"name": "Storm Slate", "hex": "#445566"}]

    # 11. get_rpc_dispatcher recreates dispatcher on sys_obj if missing/invalid
    sys_obj.rpc_dispatcher = "corrupted"
    recreated = get_rpc_dispatcher(hass)
    assert isinstance(recreated, LatterRpcDispatcher)
    assert sys_obj.rpc_dispatcher is recreated

    # 12. Defensive async_dispatch fallback when an allowlisted method has no handler branch
    with patch.object(
        rpc_dispatcher_mod,
        "ALL_RPC_METHODS",
        (*ALL_RPC_METHODS, "synthetic_unhandled"),
    ):
        assert await recreated.async_dispatch(coord, "synthetic_unhandled", {}) is None

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_rpc_receiver_registry_remove_state_remove_and_dispatch_error(
    hass: Any, setup_latter_hub: Any, caplog: Any
) -> None:
    """Exercise rpc_receiver dispatch error logging, state removal, unknown registry action, and entity removal."""
    entry, _sys_obj, coord = await setup_latter_hub(hass)
    receiver = coord._rpc_receiver
    assert receiver is not None
    rpc_eid = receiver.tracked_entity_id
    assert rpc_eid is not None

    # 1. Dispatch error inside _async_safe_dispatch logs warning cleanly
    bad_color_env = json.dumps(
        {"s": "save_custom_color", "d": {"hex_color": "#ZZZZZZ"}},
        separators=(",", ":"),
    )
    with caplog.at_level(logging.WARNING):
        hass.states.async_set(rpc_eid, f"d00d:1:1/1|{bad_color_env}")
        await hass.async_block_till_done()
    assert "Bound RPC 'save_custom_color' from device 'pocket_assistant' failed:" in caplog.text

    # 2. Removing the state fires state_changed with new_state=None and returns cleanly
    hass.states.async_remove(rpc_eid)
    await hass.async_block_till_done()
    assert receiver.tracked_entity_id == rpc_eid

    # 3. Unknown entity-registry event action returns early
    receiver._async_on_entity_registry_updated(
        Event(er.EVENT_ENTITY_REGISTRY_UPDATED, {"action": "noop", "entity_id": rpc_eid})
    )
    assert receiver.tracked_entity_id == rpc_eid

    # 4. Removing the outbox entity from EntityRegistry triggers rebind() -> ent_id is None
    ent_reg = er.async_get(hass)
    ent_reg.async_remove(rpc_eid)
    await hass.async_block_till_done()
    assert receiver.tracked_entity_id is None
    assert receiver.is_device_unavailable() is False

    assert await hass.config_entries.async_unload(entry.entry_id) is True
