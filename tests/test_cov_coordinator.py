"""Comprehensive real-HA coverage tests for `coordinator.core`, `coordinator.area_follow`, and `coordinator.runtime`."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import json
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_CORE_CONFIG_UPDATE,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.util import dt as dt_util
import pytest

from custom_components.latter.const import (
    CONF_ACTIVITY_SOURCES,
    CONF_AREA_CATEGORIES,
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_BLE_AREA_SIGNATURES,
    CONF_BLE_ATTENUATION,
    CONF_BLE_AUTO_SWITCH,
    CONF_BLE_AWAY_TIMEOUT_S,
    CONF_BLE_MAX_RADIUS_M,
    CONF_BLE_MAX_VELOCITY_MPS,
    CONF_BLE_REF_POWER,
    CONF_BLE_SCANNER_OFFSETS,
    CONF_BROADCAST_PHRASES,
    CONF_CUSTOM_PALETTES,
    CONF_DEFAULT_AREA,
    CONF_DEVICE_GROUPS,
    CONF_GAMES_ITEMS,
    CONF_HOME_CATEGORIES,
    CONF_MA_PLAYER_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    CONF_REMOTE_GROUPS,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_PHOTO_COLLECTION,
    CONF_SCREENSAVER_PHOTO_MODE,
    CONF_SCREENSAVER_PHOTO_SOURCE,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_TOOLS_ITEMS,
    CONF_WALLPAPER_COLLECTION,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_MODE,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    DEFAULT_ACTIVITY_SOURCES,
    DEFAULT_AREA_CATEGORIES,
    DEFAULT_AREA_FOLLOW_DWELL_S,
    DEFAULT_ART_SIZE,
    DEFAULT_BLE_ATTENUATION,
    DEFAULT_BLE_AWAY_TIMEOUT_S,
    DEFAULT_BLE_MAX_RADIUS_M,
    DEFAULT_BLE_MAX_VELOCITY_MPS,
    DEFAULT_CARD_SLOT_COUNT,
    DEFAULT_GAMES_ITEMS,
    DEFAULT_HOME_CATEGORIES,
    DEFAULT_LIST_SLOT_COUNT,
    DEFAULT_SCREENSAVER_CYCLE_MINUTES,
    DEFAULT_TOOLS_ITEMS,
    DOMAIN,
    MIN_FIRMWARE_CORE_REV,
)
from custom_components.latter.coordinator.area_follow import LatterAreaFollowController
from custom_components.latter.coordinator.core import (
    LatterCoordinator,
    _normalize_hmac_secret,
    _parse_bool_flag,
    _parse_kb,
    match_coordinator_target,
)
from custom_components.latter.coordinator.runtime import LatterDeviceRuntime
from custom_components.latter.groups.device_groups import get_device_groups
from custom_components.latter.hub_registry import get_area_state_index, get_global_config
from custom_components.latter.hub_sync import async_save_and_broadcast_global_config
from custom_components.latter.identity import _esphome_entry_for_device
from custom_components.latter.repairs_keys import (
    ISSUE_CRASHED,
    ISSUE_ROLLED_BACK,
    device_health_issue_id,
)
from tests.helpers import (
    add_mock_entry,
    ensure_area,
    flush_debouncers,
    get_service_calls,
    mock_service,
    prepare_latter_dependencies,
    register_device,
    register_entity,
    seed_ble_proxies,
)


def _update_subentry_fields(
    hass: Any, entry: Any, coord: LatterCoordinator, updates: dict[str, Any]
) -> None:
    """Update raw subentry fields directly on HA ConfigEntries without triggering background reloads."""
    merged = {**coord.device_data, **updates}
    hass.config_entries.async_update_subentry(entry, coord._live_subentry(), data=merged)
    coord._applied_options_snapshot = coord._capture_options_snapshot()


async def test_area_follow_controller_dwell_pending_ignore_and_commit(
    hass: Any, make_esphome_device: Any
) -> None:
    """Exercise `LatterAreaFollowController` pending, ignore, dwell commit, and guard branches."""
    await prepare_latter_dependencies(hass)
    ensure_area(hass, "Living Area", area_id="living_room")
    ensure_area(hass, "Kitchen", area_id="kitchen")
    esp_dev, _mac = make_esphome_device(hass, area_id="living_room")

    ctrl = LatterAreaFollowController(hass)
    assert ctrl.pending_area_id is None

    scheduled: list[tuple[float, Callable[[datetime], None]]] = []
    unsub_calls: list[int] = []

    def _capture_call_later(
        _hass: Any, delay: float, action: Callable[[datetime], None]
    ) -> Callable[[], None]:
        idx = len(scheduled)
        scheduled.append((delay, action))
        return lambda: unsub_calls.append(idx)

    with patch(
        "custom_components.latter.coordinator.area_follow.async_call_later",
        side_effect=_capture_call_later,
    ):
        # 1) First BLE-driven move starts dwell timer (`DWELL`)
        ctrl.schedule_or_commit(
            esphome_device_id=esp_dev.id,
            target_area_id="kitchen",
            ble_driven=True,
            dwell_s=5,
            is_allowed_cb=lambda: True,
        )
        assert ctrl.pending_area_id == "kitchen"
        assert len(scheduled) == 1

        # 2) Repeat move for same pending Area returns early (`PENDING`) without rescheduling
        ctrl.schedule_or_commit(
            esphome_device_id=esp_dev.id,
            target_area_id="kitchen",
            ble_driven=True,
            dwell_s=5,
            is_allowed_cb=lambda: True,
        )
        assert len(scheduled) == 1
        assert ctrl.pending_area_id == "kitchen"

        # 3) Non-Area token (`away`) cancels dwell timer and returns early (`IGNORE`)
        ctrl.schedule_or_commit(
            esphome_device_id=esp_dev.id,
            target_area_id="away",
            ble_driven=True,
            dwell_s=5,
            is_allowed_cb=lambda: True,
        )
        assert ctrl.pending_area_id is None
        assert unsub_calls == [0]

        # 4) Schedule dwell to kitchen, advance due_at, and invoke `_commit_dwell_sync`
        ctrl.schedule_or_commit(
            esphome_device_id=esp_dev.id,
            target_area_id="kitchen",
            ble_driven=True,
            dwell_s=5,
            is_allowed_cb=lambda: True,
        )
        assert len(scheduled) == 2
        ctrl._dwell.due_at = time.monotonic() - 1.0
        scheduled[-1][1](dt_util.utcnow())

        updated_dev = dr.async_get(hass).async_get(esp_dev.id)
        assert updated_dev is not None
        assert updated_dev.area_id == "kitchen"
        assert ctrl.last_area_follow_write is not None
        assert ctrl.last_area_follow_write["to_area"] == "kitchen"
        assert ctrl.pending_area_id is None

        # 5) Dwell commit skipped cleanly when `is_allowed_cb` returns False
        prev_write = ctrl.last_area_follow_write
        ctrl.schedule_or_commit(
            esphome_device_id=esp_dev.id,
            target_area_id="living_room",
            ble_driven=True,
            dwell_s=5,
            is_allowed_cb=lambda: False,
        )
        assert ctrl.last_area_follow_write is prev_write


async def test_device_runtime_load_error_and_malformed_hello_manifest(hass: Any) -> None:
    """Exercise `LatterDeviceRuntime.async_load` failure fallback and invalid JSON hello manifest."""
    runtime = LatterDeviceRuntime(hass, "sub_cov_runtime")

    with patch.object(
        runtime.store,
        "async_load",
        new_callable=AsyncMock,
        side_effect=OSError("disk unreadable"),
    ):
        loaded = await runtime.async_load()
    assert loaded == {}

    is_new_boot, parsed = runtime.apply_device_hello("boot_hex_01", "{malformed json")
    assert is_new_boot is True
    assert parsed is None
    assert runtime.hello_manifest == {}
    assert runtime.last_boot_id == "boot_hex_01"

    # Re-sending same boot ID reports is_new_boot=False
    is_new_again, parsed_again = runtime.apply_device_hello("boot_hex_01", "")
    assert is_new_again is False
    assert parsed_again is None


async def test_core_pure_helpers_and_option_fallbacks(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise pure helpers, listener/task fallbacks, manifest/CSV/BLE option error branches."""
    # Pure module-level helpers
    assert _normalize_hmac_secret(b"\x01\x02") == b"\x01\x02"
    assert _normalize_hmac_secret("deadbeef") == b"\xde\xad\xbe\xef"
    assert _normalize_hmac_secret("not-valid-hex!") == b"not-valid-hex!"
    assert _parse_bool_flag(True) is True
    assert _parse_bool_flag("yes") is True
    assert _parse_bool_flag("on") is True
    assert _parse_bool_flag("0") is False
    assert _parse_kb("128.4") == 128
    assert _parse_kb(-10) is None
    assert _parse_kb("not_a_number") is None

    # `_compute_changed_pref_keys` invalid CSV fallbacks for tools_items & games_items
    changed_invalid = LatterCoordinator._compute_changed_pref_keys(
        {CONF_TOOLS_ITEMS: "invalid_tool", CONF_GAMES_ITEMS: "invalid_game"},
        {CONF_TOOLS_ITEMS: "also_invalid", CONF_GAMES_ITEMS: "still_invalid"},
    )
    assert CONF_TOOLS_ITEMS not in changed_invalid
    assert CONF_GAMES_ITEMS not in changed_invalid

    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)

    # `_initial_brightness_pct` invalid float fallback
    with patch(
        "custom_components.latter.coordinator.core.resolve_device_pref_value",
        return_value="not_a_number",
    ):
        assert coord._initial_brightness_pct() == 80

    # `create_background_task` fallback when `entry` lacks `async_create_background_task`
    orig_entry = coord.entry
    try:
        coord.entry = SimpleNamespace(entry_id=orig_entry.entry_id)  # type: ignore[assignment]
        fallback_task = coord.create_background_task(asyncio.sleep(0), "fallback_cov_task")
        await fallback_task
        assert fallback_task.done()
    finally:
        coord.entry = orig_entry

    # `replace_area_listener_unsubs` partial update & no-arg full clear
    unsub_log: list[str] = []
    coord.replace_area_listener_unsubs(alarm=lambda: unsub_log.append("alarm"))
    coord.replace_area_listener_unsubs()
    assert unsub_log == ["alarm"]

    # `replace_doorbell_ring_unsub` invokes previous callback on replacement
    ring_unsubs: list[str] = []
    coord.replace_doorbell_ring_unsub(lambda: ring_unsubs.append("first"))
    coord.replace_doorbell_ring_unsub(lambda: ring_unsubs.append("second"))
    coord.replace_doorbell_ring_unsub(None)
    assert ring_unsubs == ["first", "second"]

    # `url_signer`, `epoch`, `get_lan_base_url`
    assert coord.url_signer is coord._url_signer
    assert coord.epoch == coord._packer.epoch
    assert coord.get_lan_base_url().startswith("http")

    # `device_mac` fallback via bound ESPHome device connections when `mac` omitted in subentry
    orig_mac = coord.device_data.get("mac")
    _update_subentry_fields(hass, entry, coord, {"mac": ""})
    assert coord.device_mac == dr.format_mac("aa:bb:cc:dd:ee:01")
    _update_subentry_fields(hass, entry, coord, {"mac": orig_mac})

    # Manifest-backed slot capacity & media dimension fallbacks
    orig_hello = dict(coord._runtime.hello_manifest)
    coord._runtime.hello_manifest = {
        "w": 466,
        "h": 466,
        "slot_count": "bad_int",
        "card_slot_count": "bad_int",
    }
    assert coord.list_slot_capacity == DEFAULT_LIST_SLOT_COUNT
    assert coord.card_slot_capacity == DEFAULT_CARD_SLOT_COUNT

    coord._runtime.hello_manifest = {"w": "bad_w", "h": "bad_h"}
    assert coord.art_dimensions == (DEFAULT_ART_SIZE, DEFAULT_ART_SIZE)

    coord._runtime.hello_manifest = {"w": 32, "h": 32}
    assert coord.wallpaper_dimensions == (DEFAULT_ART_SIZE, DEFAULT_ART_SIZE)
    coord._runtime.hello_manifest = orig_hello

    # Invalid CSV option fallbacks
    _update_subentry_fields(
        hass,
        entry,
        coord,
        {
            CONF_AREA_CATEGORIES: "bogus_cat",
            CONF_HOME_CATEGORIES: "bogus_home",
            CONF_TOOLS_ITEMS: "bogus_tool",
            CONF_GAMES_ITEMS: "bogus_game",
            CONF_ACTIVITY_SOURCES: "bogus_activity",
            CONF_BLE_REF_POWER: "bad_ref",
            CONF_AREA_FOLLOW_DWELL_S: "bad_dwell",
        },
    )
    assert coord.area_categories_csv == DEFAULT_AREA_CATEGORIES
    assert coord.home_categories_csv == DEFAULT_HOME_CATEGORIES
    assert coord.tools_items_csv == DEFAULT_TOOLS_ITEMS
    assert coord.games_items_csv == DEFAULT_GAMES_ITEMS
    assert coord.activity_sources_csv == DEFAULT_ACTIVITY_SOURCES
    assert coord.ble_ref_power is None
    assert coord.area_follow_dwell_s == DEFAULT_AREA_FOLLOW_DWELL_S

    # Global config malformed values & weather_entity getter
    gcfg = get_global_config(hass)
    gcfg[CONF_CUSTOM_PALETTES] = "not_a_list"
    gcfg[CONF_BROADCAST_PHRASES] = "not_a_list"
    gcfg[CONF_REMOTE_GROUPS] = "not_a_list"
    gcfg[CONF_WEATHER_ENTITY] = "weather.home"
    gcfg[CONF_BLE_SCANNER_OFFSETS] = "not_a_dict"
    gcfg[CONF_BLE_AREA_SIGNATURES] = "not_a_dict"
    gcfg[CONF_BLE_ATTENUATION] = "bad"
    gcfg[CONF_BLE_MAX_RADIUS_M] = "bad"
    gcfg[CONF_BLE_MAX_VELOCITY_MPS] = "bad"
    gcfg[CONF_BLE_AWAY_TIMEOUT_S] = "bad"

    assert coord.custom_palettes == []
    assert coord.broadcast_phrases == []
    assert coord.remote_groups == []
    assert coord.weather_entity == "weather.home"
    assert coord.ble_scanner_offsets == {}
    assert coord.ble_area_signatures == {}
    assert coord.ble_attenuation == DEFAULT_BLE_ATTENUATION
    assert coord.ble_max_radius_m == DEFAULT_BLE_MAX_RADIUS_M
    assert coord.ble_max_velocity_mps == DEFAULT_BLE_MAX_VELOCITY_MPS
    assert coord.ble_away_timeout_s == DEFAULT_BLE_AWAY_TIMEOUT_S

    # `ble_scanner_offsets` blank key + invalid numeric value + valid offset
    gcfg[CONF_BLE_SCANNER_OFFSETS] = {
        "   ": 2.0,
        "AA:BB:CC:00:00:11": "not_a_float",
        "AA:BB:CC:00:00:22": 0.0,
        "AA:BB:CC:00:00:33": 4.5,
    }
    assert coord.ble_scanner_offsets == {"AA:BB:CC:00:00:33": 4.5}

    gcfg[CONF_WEATHER_ENTITY] = ""
    assert coord.weather_entity is None

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_wallpaper_and_screensaver_pools_timers_and_apply_options(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise wallpaper/screensaver pool fallbacks, rotation interval ticks, and `async_apply_options` pruning."""
    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)
    ble_coord = next(c for c in sys_obj.coordinators.values() if c.is_ble_tag)

    # `wallpaper_mode` fallback to `"single"` when mode empty and source configured
    _update_subentry_fields(
        hass,
        entry,
        coord,
        {
            CONF_WALLPAPER_MODE: "",
            CONF_WALLPAPER_SOURCE: "preset:forest_mountains",
            CONF_WALLPAPER_CYCLE_MINUTES: "bad_mins",
            CONF_SCREENSAVER_CYCLE_MINUTES: "bad_mins",
        },
    )
    assert coord.wallpaper_mode == "single"
    assert coord.wallpaper_cycle_minutes == 0
    assert coord.screensaver_cycle_minutes == DEFAULT_SCREENSAVER_CYCLE_MINUTES

    # `configured_wallpaper_source` property setter
    coord.configured_wallpaper_source = "preset:ocean_waves"
    assert coord._configured_wallpaper_source == "preset:ocean_waves"

    # `wallpaper_source` fallback to `cfg_src` then `pool[0]`
    _update_subentry_fields(
        hass,
        entry,
        coord,
        {
            CONF_WALLPAPER_MODE: "collection",
            CONF_WALLPAPER_COLLECTION: "__defaults__",
            CONF_WALLPAPER_SOURCE: "preset:ocean_waves",
        },
    )
    coord.current_wallpaper = "preset:stale_missing"
    assert coord.wallpaper_source == "preset:ocean_waves"

    _update_subentry_fields(hass, entry, coord, {CONF_WALLPAPER_SOURCE: "preset:nonexistent"})
    assert coord.wallpaper_source == coord.resolve_wallpaper_rotation_pool()[0]

    # `ensure_active_wallpaper_for_rotation` clears stale wallpaper when pool is empty
    _update_subentry_fields(hass, entry, coord, {CONF_WALLPAPER_MODE: "off"})
    coord.current_wallpaper = "preset:ocean_waves"
    assert coord.ensure_active_wallpaper_for_rotation() is False
    assert coord.current_wallpaper == ""

    # Screensaver photo source, URL, BLE tag guard, and stale pruning
    assert ble_coord.ensure_active_screensaver_photo() is False
    _update_subentry_fields(
        hass,
        entry,
        coord,
        {
            "screensaver_style": "Photo Frame",
            "screensaver_mode": "On Dock",
            CONF_SCREENSAVER_PHOTO_MODE: "off",
        },
    )
    assert coord.screensaver_photo_frame_active is True
    assert coord.build_screensaver_photo_url() == ""
    coord.current_screensaver_photo = "preset:stale_photo"
    assert coord.ensure_active_screensaver_photo() is False
    assert coord.current_screensaver_photo == ""

    _update_subentry_fields(
        hass,
        entry,
        coord,
        {
            CONF_SCREENSAVER_PHOTO_MODE: "collection",
            CONF_SCREENSAVER_PHOTO_COLLECTION: "__defaults__",
            CONF_SCREENSAVER_PHOTO_SOURCE: "preset:mars_crater",
        },
    )
    coord.current_screensaver_photo = ""
    assert coord.screensaver_photo_source == "preset:mars_crater"
    assert coord.ensure_active_screensaver_photo() is True
    assert coord.current_screensaver_photo == "preset:mars_crater"

    # `bind_screensaver_cycle_timer` inactive pruning & `mins <= 0` early return
    _update_subentry_fields(
        hass,
        entry,
        coord,
        {"screensaver_style": "Clock", CONF_SCREENSAVER_PHOTO_MODE: "off"},
    )
    coord.current_screensaver_photo = "preset:orphan"
    coord.bind_screensaver_cycle_timer()
    assert coord.current_screensaver_photo == ""

    _update_subentry_fields(
        hass,
        entry,
        coord,
        {
            "screensaver_style": "Photo Frame",
            CONF_SCREENSAVER_PHOTO_MODE: "collection",
            CONF_SCREENSAVER_PHOTO_COLLECTION: "__defaults__",
            CONF_SCREENSAVER_CYCLE_MINUTES: 0,
        },
    )
    coord.bind_screensaver_cycle_timer()
    assert coord._unsub_screensaver_timer is None

    # Capture & invoke `_on_wallpaper_tick` and `_on_screensaver_tick` deterministically
    wp_ticks: list[Callable[[datetime], None]] = []
    ss_ticks: list[Callable[[datetime], None]] = []

    def _capture_wp_interval(
        _hass: Any, action: Callable[[datetime], None], _delta: Any
    ) -> Callable[[], None]:
        wp_ticks.append(action)
        return lambda: None

    def _capture_ss_interval(
        _hass: Any, action: Callable[[datetime], None], _delta: Any
    ) -> Callable[[], None]:
        ss_ticks.append(action)
        return lambda: None

    _update_subentry_fields(
        hass,
        entry,
        coord,
        {
            CONF_WALLPAPER_MODE: "collection",
            CONF_WALLPAPER_COLLECTION: "__defaults__",
            CONF_WALLPAPER_CYCLE_MINUTES: 5,
        },
    )
    with patch(
        "custom_components.latter.coordinator.core.async_track_time_interval",
        side_effect=_capture_wp_interval,
    ):
        coord.bind_wallpaper_cycle_timer()
    assert len(wp_ticks) == 1
    first_wp = coord.current_wallpaper
    wp_ticks[0](dt_util.utcnow())
    assert coord.current_wallpaper != first_wp

    # Trigger `ValueError` branch in `_on_wallpaper_tick` when `cur` is absent from `tick_pool`
    with patch.object(
        coord,
        "resolve_wallpaper_rotation_pool",
        side_effect=[["preset:ocean_waves", "preset:mars_crater"], ["preset:wheat_field"]],
    ):
        coord.current_wallpaper = "preset:wheat_field"
        wp_ticks[0](dt_util.utcnow())
    assert coord.current_wallpaper == "preset:ocean_waves"

    # Trigger `len(tick_pool) < 2` early return in `_on_wallpaper_tick`
    _update_subentry_fields(hass, entry, coord, {CONF_WALLPAPER_MODE: "off"})
    wp_ticks[0](dt_util.utcnow())

    # Screensaver tick: shuffle=True, shuffle=False, ValueError fallback, small pool, inactive
    _update_subentry_fields(
        hass,
        entry,
        coord,
        {
            "screensaver_style": "Photo Frame",
            CONF_SCREENSAVER_PHOTO_MODE: "collection",
            CONF_SCREENSAVER_PHOTO_COLLECTION: "__defaults__",
            CONF_SCREENSAVER_CYCLE_MINUTES: 5,
            CONF_SCREENSAVER_SHUFFLE: True,
        },
    )
    with patch(
        "custom_components.latter.coordinator.core.async_track_time_interval",
        side_effect=_capture_ss_interval,
    ):
        coord.bind_screensaver_cycle_timer()
    assert len(ss_ticks) == 1
    before_shuffle = coord.current_screensaver_photo
    ss_ticks[0](dt_util.utcnow())
    assert coord.current_screensaver_photo != before_shuffle

    _update_subentry_fields(hass, entry, coord, {CONF_SCREENSAVER_SHUFFLE: False})
    before_seq = coord.current_screensaver_photo
    ss_ticks[0](dt_util.utcnow())
    assert coord.current_screensaver_photo != before_seq

    with patch.object(
        coord,
        "resolve_screensaver_photo_pool",
        side_effect=[["preset:ocean_waves", "preset:mars_crater"], ["preset:wheat_field"]],
    ):
        coord.current_screensaver_photo = "preset:wheat_field"
        ss_ticks[0](dt_util.utcnow())
    assert coord.current_screensaver_photo == "preset:ocean_waves"

    _update_subentry_fields(hass, entry, coord, {CONF_SCREENSAVER_PHOTO_MODE: "off"})
    ss_ticks[0](dt_util.utcnow())

    _update_subentry_fields(hass, entry, coord, {"screensaver_style": "Clock"})
    ss_ticks[0](dt_util.utcnow())

    # `async_apply_options` resets changed wallpaper source & stale screensaver photo
    _update_subentry_fields(
        hass,
        entry,
        coord,
        {
            CONF_WALLPAPER_MODE: "collection",
            CONF_WALLPAPER_COLLECTION: "__defaults__",
            CONF_WALLPAPER_SOURCE: "preset:sahara_dunes",
            CONF_SCREENSAVER_PHOTO_MODE: "collection",
            CONF_SCREENSAVER_PHOTO_COLLECTION: "__defaults__",
        },
    )
    coord._configured_wallpaper_source = "preset:forest_mountains"
    coord.current_screensaver_photo = "preset:deleted_photo"
    await coord.async_apply_options()
    assert coord.current_wallpaper == "preset:sahara_dunes"
    assert coord.current_screensaver_photo in coord.resolve_screensaver_photo_pool()

    await flush_debouncers(hass)
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_area_ble_registry_sync_rename_and_reconnect_flows(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise BLE auto-switch gate, Area media handoff, rename/Area sync, health issues, and reconnect."""
    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)
    ble_coord = next(c for c in sys_obj.coordinators.values() if c.is_ble_tag)

    # 1) `_async_on_native_ble_area_detected` when `ble_auto_switch_enabled=False`
    _update_subentry_fields(hass, entry, coord, {CONF_BLE_AUTO_SWITCH: False})
    prev_area = coord.active_area_id
    coord._async_on_native_ble_area_detected("kitchen", "AA:BB:CC:00:00:22")
    assert coord.active_area_id == prev_area
    _update_subentry_fields(hass, entry, coord, {CONF_BLE_AUTO_SWITCH: True})

    # 2) `async_set_active_area` unknown Area early return & Media handoff with transfer_queue=True
    coord.async_set_active_area("nonexistent_area_999")
    assert coord.active_area_id == prev_area

    ma_entry = add_mock_entry(
        hass, entry_id="ma_handoff_entry", domain="music_assistant", title="Music Assistant"
    )
    mock_service(hass, "music_assistant", "transfer_queue")
    register_entity(
        hass,
        "media_player.kitchen_ma_speaker",
        platform="music_assistant",
        config_entry=ma_entry,
        area_id="kitchen",
        original_name="Kitchen MA Speaker",
    )
    hass.states.async_set(
        "media_player.kitchen_ma_speaker",
        "idle",
        {"friendly_name": "Kitchen MA Speaker"},
    )
    register_entity(
        hass,
        "media_player.remote_playing_spk",
        platform="music_assistant",
        config_entry=ma_entry,
        area_id="living_room",
        original_name="Remote Playing Speaker",
    )
    hass.states.async_set(
        "media_player.remote_playing_spk",
        STATE_PLAYING,
        {
            "friendly_name": "Remote Playing Speaker",
            "media_title": "Track One",
            "media_artist": "Artist",
            "media_content_id": "library://track/1",
            "media_content_type": "music",
        },
    )
    await hass.async_block_till_done()
    coord.active_speaker = "media_player.remote_playing_spk"
    coord.async_set_active_area("kitchen", handoff_media=True, sync_device_registry=True)
    await hass.async_block_till_done()
    assert coord.active_area_id == "kitchen"
    assert coord.active_speaker == "media_player.kitchen_ma_speaker"

    # 3) `async_sync_ha_device_name` missing device & blank name early returns
    with patch(
        "custom_components.latter.coordinator.core.get_bound_esphome_device",
        return_value=None,
    ):
        assert coord.async_sync_ha_device_name() is False
    with patch(
        "custom_components.latter.coordinator.core.get_bound_esphome_device",
        return_value=SimpleNamespace(name_by_user=None, name="   "),
    ):
        assert coord.async_sync_ha_device_name() is False

    # 4) `async_on_ha_entity_renamed` early return, MA/active_speaker migration, & audit error catch
    assert ble_coord.async_on_ha_entity_renamed("media_player.a", "media_player.b") is False
    assert coord.async_on_ha_entity_renamed("media_player.same", "media_player.same") is False

    _update_subentry_fields(
        hass, entry, coord, {CONF_MA_PLAYER_ENTITY: "media_player.ma_old"}
    )
    with patch(
        "custom_components.latter.coordinator.core.async_audit_coordinator_health",
        side_effect=RuntimeError("audit boom"),
    ):
        migrated = coord.async_on_ha_entity_renamed(
            "media_player.ma_old", "media_player.ma_new"
        )
    assert migrated is True
    assert coord.get_opt(CONF_MA_PLAYER_ENTITY) == "media_player.ma_new"

    # Separate Area speaker rename exercises `active_speaker` runtime migration (2539-2541)
    coord.active_speaker = "media_player.area_sonos_old"
    assert coord.active_speaker == "media_player.area_sonos_old"
    assert coord.async_on_ha_entity_renamed(
        "media_player.area_sonos_old", "media_player.area_sonos_new"
    ) is True
    assert coord.active_speaker == "media_player.area_sonos_new"

    # 5) `async_on_ha_device_area_updated` BLE tag guard, unchanged guard, & no-lock dynamic fallback
    ble_coord.async_on_ha_device_area_updated("any_dev", "kitchen")
    coord._last_esp_area = "kitchen"
    coord.async_on_ha_device_area_updated(str(coord.esphome_device_id), "kitchen")

    _update_subentry_fields(
        hass,
        entry,
        coord,
        {CONF_DEFAULT_AREA: "", CONF_NATIVE_BLE_TRACKING: True},
    )
    if coord.ble_tracker is not None:
        coord.ble_tracker.current_area_id = None
    coord._last_esp_area = "kitchen"
    coord.async_on_ha_device_area_updated(str(coord.esphome_device_id), "bedroom")
    assert coord.active_area_id == "bedroom"
    coord.async_on_ha_device_area_updated(str(coord.esphome_device_id), "")
    assert coord.active_area_id is None

    # 6) `_resolve_rpc_outbox_entity_id` & `is_rpc_outbox_unavailable` fallback without `_rpc_receiver`
    orig_ble_recv = ble_coord._rpc_receiver
    orig_dev_recv = coord._rpc_receiver
    outbox_eid = f"sensor.{coord.device_slug}_system_rpc_outbox"
    try:
        ble_coord._rpc_receiver = None
        assert ble_coord.is_rpc_outbox_unavailable() is False

        coord._rpc_receiver = None
        hass.states.async_set(outbox_eid, STATE_UNAVAILABLE)
        assert coord.is_rpc_outbox_unavailable() is True
        hass.states.async_set(outbox_eid, "")
        assert coord.is_rpc_outbox_unavailable() is False
    finally:
        ble_coord._rpc_receiver = orig_ble_recv
        coord._rpc_receiver = orig_dev_recv

    # 7) `_apply_device_health` creates crash/rollback issues then clears them on clean boot
    iss_reg = ir.async_get(hass)
    coord._apply_device_health(
        {
            "w": 466,
            "h": 466,
            "core_rev": MIN_FIRMWARE_CORE_REV,
            "reset": "panic",
            "crash": 1,
            "rollback": 1,
        },
        "boot_panic_1",
    )
    crash_id = device_health_issue_id(ISSUE_CRASHED, coord.subentry_id)
    rollback_id = device_health_issue_id(ISSUE_ROLLED_BACK, coord.subentry_id)
    assert iss_reg.async_get_issue(DOMAIN, crash_id) is not None
    assert iss_reg.async_get_issue(DOMAIN, rollback_id) is not None

    coord._apply_device_health(
        {
            "w": 466,
            "h": 466,
            "core_rev": MIN_FIRMWARE_CORE_REV,
            "reset": "power-on",
            "crash": 0,
            "rollback": 0,
        },
        "boot_clean_2",
    )
    assert iss_reg.async_get_issue(DOMAIN, crash_id) is None
    assert iss_reg.async_get_issue(DOMAIN, rollback_id) is None

    # 8) `_async_handle_reconnect` & `_async_finish_reconnect_post_delay`
    post_delay_cbs: list[Callable[[datetime], None]] = []

    def _capture_reconnect_later(
        _hass: Any, _delay: float, action: Callable[[datetime], None]
    ) -> Callable[[], None]:
        post_delay_cbs.append(action)
        return lambda: None

    coord.active_area_id = "living_room"
    assert coord.ble_tracker is not None
    coord.ble_tracker.current_area_id = "kitchen"
    with patch(
        "custom_components.latter.coordinator.core.async_call_later",
        side_effect=_capture_reconnect_later,
    ):
        await coord._async_handle_reconnect()
    assert coord.active_area_id == "kitchen"
    assert len(post_delay_cbs) == 1

    push_slots_spy = AsyncMock()
    coord.on_area_changed_push_slots = push_slots_spy
    coord.ble_tracker.current_area_id = "bedroom"
    post_delay_cbs[0](dt_util.utcnow())
    await hass.async_block_till_done()
    assert coord.active_area_id == "bedroom"
    assert push_slots_spy.await_count >= 1

    await flush_debouncers(hass)
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_telemetry_prefs_timer_commands_v3_transport_and_target_matching(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Exercise PIN/display/telemetry/prefs/timer ticks, command failures, v3 abort paths, setup/listeners, and target matching."""
    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)
    ble_coord = next(c for c in sys_obj.coordinators.values() if c.is_ble_tag)
    slug = coord.device_slug
    outbox_eid = f"sensor.{slug}_system_rpc_outbox"
    manifest_raw = json.dumps(coord.hardware_manifest)

    # 1) PIN session key guard for BLE tag + grid capability trait resolution & shortcuts cache invalidation
    assert await ble_coord.async_provision_pin_session_key() is False
    assert (ble_coord.screen_width, ble_coord.screen_height) == (0, 0)
    assert (ble_coord.grid_cols, ble_coord.grid_rows) == (2, 3)

    orig_manifest = coord._runtime.hello_manifest
    try:
        coord._runtime.hello_manifest = {"w": 1280, "h": 800, "shape": "square", "grid_cols": 4, "grid_rows": 3}
        assert (coord.screen_width, coord.screen_height, coord.grid_cols, coord.grid_rows) == (1280, 800, 4, 3)
        coord._runtime.hello_manifest = {"w": 1024, "h": 600, "shape": "square"}
        assert (coord.grid_cols, coord.grid_rows) == (4, 3)
        coord._runtime.hello_manifest = {"w": 720, "h": 720, "shape": "square"}
        assert (coord.grid_cols, coord.grid_rows) == (3, 3)
        coord._runtime.hello_manifest = {"w": 466, "h": 466, "shape": "circle"}
        assert (coord.grid_cols, coord.grid_rows) == (2, 3)
        coord._runtime.hello_manifest = {"w": 410, "h": 502, "shape": "square"}
        assert (coord.grid_cols, coord.grid_rows) == (2, 3)
        coord._runtime.hello_manifest = None
        assert (coord.screen_width, coord.screen_height, coord.grid_cols, coord.grid_rows) == (0, 0, 2, 3)
    finally:
        coord._runtime.hello_manifest = orig_manifest

    rev_before, _ = coord.get_shortcuts_payload()
    coord.update_device_config({**coord.device_data, "pinned_page_titles": {"0": "Deck"}})
    assert coord.pinned_page_titles == {"0": "Deck"}
    rev_after, frames_after = coord.get_shortcuts_payload()
    assert rev_after == rev_before + 1
    assert frames_after[0].split("\x1f")[8] == "0|Deck"

    # 2) `apply_display_state` & `_resolve_next_display_power` edge inputs
    coord.display_power_state = 0
    coord.display_brightness_pct = 75
    coord.apply_display_state("not_numeric", "not_numeric")
    assert coord.display_power_state == 0
    assert coord.display_brightness_pct == 75
    coord.apply_display_state(None, 60, screensaver_active="true")
    assert coord.display_power_state == 1
    assert coord.display_brightness_pct == 60
    coord.apply_display_state(None, 55, screensaver_active="false")
    assert coord.display_power_state == 0
    coord.apply_display_state(0, 50, screensaver_active="1")
    assert coord.display_power_state == 1

    # 3) `apply_device_telemetry` malformed link JSON & hibernate enter/exit transitions
    coord.apply_device_telemetry({"link_json": "{not json", "int_ram_free_kb": "bad"})
    assert coord.device_telemetry["link"] == {}
    assert coord.device_telemetry["int_ram_free_kb"] is None

    coord.apply_device_telemetry({"link_json": json.dumps({"state": "hibernating"})})
    assert coord._entered_hibernate is True
    coord.apply_device_telemetry({"link": {"state": "connected"}})
    assert coord._entered_hibernate is False

    # 4) `_merge_hello_device_prefs` empty incoming_prefs with prefs_seq > 0 & `ble_beacon_enabled=0` flip
    coord.prefs_seq = 2
    coord.prefs_key_seq.clear()
    assert coord._merge_hello_device_prefs(5, {}) is False
    assert coord.prefs_seq == 5

    await coord.async_handle_device_hello(
        boot_id="boot_ble_flip",
        manifest_raw=manifest_raw,
        prefs_seq=6,
        dirty_prefs="ble_beacon_enabled=0",
    )
    assert coord.native_ble_tracking_enabled is False
    assert coord.ble_tracker is None

    # 5) `async_update_device_prefs` empty no-op, force_bump/min_next_seq, screensaver bind, BLE re-enable
    assert await coord.async_update_device_prefs({}, force_bump=False) == {}
    cur_vol = coord.get_device_pref("alert_volume")
    target_min_seq = coord.prefs_seq + 5
    await coord.async_update_device_prefs(
        {"alert_volume": cur_vol},
        min_next_seq=target_min_seq,
        force_bump=True,
    )
    assert coord.prefs_seq >= target_min_seq
    assert coord.prefs_key_seq["alert_volume"] == coord.prefs_seq

    await coord.async_update_device_prefs({"screensaver_style": "Photo Frame"})
    assert coord.get_device_pref("screensaver_style") == "Photo Frame"

    await coord.async_update_device_prefs({CONF_NATIVE_BLE_TRACKING: True})
    assert coord.native_ble_tracking_enabled is True
    assert coord.ble_tracker is not None

    # `async_handle_set_device_prefs` empty changes early return
    seq_before_empty = coord.prefs_seq
    await coord.async_handle_set_device_prefs(seq_before_empty, "")
    assert coord.prefs_seq == seq_before_empty
    await hass.async_block_till_done()

    # 6) Timestamp-based timer anchor (`timer_ends_at_dt`) without any 1 Hz HA timer tick
    assert not hasattr(coord, "_unsub_timer_tick")
    coord.handle_timer_alarm_state(True, False, 10, False)
    assert isinstance(coord.timer_ends_at_dt, datetime)
    assert coord.timer_ends_at_dt.tzinfo is not None
    assert coord.timer_ends_at_utc != ""

    coord._timer_anchor_mono = time.monotonic() - 25.0
    assert coord.current_timer_remaining_sec == 0

    coord.handle_timer_alarm_state(False, True, 8, False)
    assert coord.timer_ends_at_dt is None
    assert coord.timer_ends_at_utc == ""
    assert coord.current_timer_remaining_sec == 8

    coord.handle_timer_alarm_state(False, False, 0, False)
    assert coord.timer_ends_at_dt is None
    assert coord.current_timer_remaining_sec == 0

    # 7) `async_set_screen_light(turn_on=True, brightness_pct=None)` sends `wake_screen`
    calls = get_service_calls(hass)
    calls.clear()
    await coord.async_set_screen_light(turn_on=True, brightness_pct=None)
    assert any(
        c.domain == "esphome"
        and c.service == f"{slug}_latter_device_command"
        and c.data.get("command") == "wake_screen"
        for c in calls
    )

    # 8) `async_send_device_command`: BLE tag, failing ESPHome service, and `restart` button fallback
    assert await ble_coord.async_send_device_command("find_my", raise_if_offline=False) is False
    with pytest.raises(HomeAssistantError):
        await ble_coord.async_send_device_command("find_my", raise_if_offline=True)

    def _raise_cmd(_call: Any) -> None:
        raise RuntimeError("esphome api error")

    mock_service(hass, "esphome", f"{slug}_latter_device_command", handler=_raise_cmd)
    assert await coord.async_send_device_command("find_my", raise_if_offline=False) is False
    with pytest.raises(HomeAssistantError) as err_info:
        await coord.async_send_device_command("set_pin_key:kid:deadbeef", raise_if_offline=True)
    assert err_info.value.translation_placeholders is not None
    assert err_info.value.translation_placeholders["command"] == "set_pin_key"
    mock_service(hass, "esphome", f"{slug}_latter_device_command")

    rst_ent = register_entity(
        hass,
        f"button.{slug}_restart_device",
        platform="esphome",
        device_id=coord.esphome_device_id,
        config_entry_id=f"esp_entry_{slug}",
        original_name="Restart Device",
    ).entity_id
    hass.states.async_set(rst_ent, "unknown")
    press_calls = mock_service(hass, "button", "press")
    with patch("custom_components.latter.coordinator.core.esphome_service", return_value=None):
        assert await coord.async_send_device_command("restart") is True
    assert press_calls and press_calls[-1].data[ATTR_ENTITY_ID] == rst_ent

    # 9) `async_push_beacon_uuid` swallows service failure
    mock_service(hass, "esphome", f"{slug}_latter_set_beacon_uuid", handler=_raise_cmd)
    await coord.async_push_beacon_uuid()
    mock_service(hass, "esphome", f"{slug}_latter_set_beacon_uuid")

    # 10) `async_push_dirty_v3_domains` & `_async_push_shortcuts_frames` disconnect abort paths
    push_svc = f"{slug}_latter_push_v3"

    # Case A: outbox flips unavailable mid-domain loop (lines 3461-3462)
    def _disconnect_after_first(_call: Any) -> None:
        hass.states.async_set(outbox_eid, STATE_UNAVAILABLE)

    mock_service(hass, "esphome", push_svc, handler=_disconnect_after_first)
    hass.states.async_set(outbox_eid, "")
    coord.clear_last_pushed_v3()
    await coord.async_push_dirty_v3_domains()
    assert coord._last_pushed_v3 == {}

    # Case B: service raises while outbox is unavailable (lines 3474-3475)
    def _disconnect_and_raise(_call: Any) -> None:
        hass.states.async_set(outbox_eid, STATE_UNAVAILABLE)
        raise RuntimeError("socket closed")

    mock_service(hass, "esphome", push_svc, handler=_disconnect_and_raise)
    hass.states.async_set(outbox_eid, "")
    coord.clear_last_pushed_v3()
    await coord.async_push_dirty_v3_domains()
    assert coord._last_pushed_v3 == {}

    # Case C: shortcuts frames abort when outbox flips unavailable before 2nd frame (lines 3434-3435)
    mock_service(hass, "esphome", push_svc, handler=_disconnect_after_first)
    hass.states.async_set(outbox_eid, "")
    coord.clear_last_pushed_v3()
    await coord._async_push_shortcuts_frames(push_svc, ("frame_1", "frame_2"))
    assert coord._last_pushed_v3 == {}
    hass.states.async_set(outbox_eid, "")
    mock_service(hass, "esphome", push_svc)

    # 11) `get_shortcuts_payload()` cache hit
    coord._cached_shortcuts_payload = None
    first_sc = coord.get_shortcuts_payload()
    second_sc = coord.get_shortcuts_payload()
    assert second_sc is first_sc

    # 11b) `_resolve_shortcut_wire_items` keeps automation trigger stateless (-1) and toggle stateful (1)
    hass.states.async_set("automation.bear", "on", {"friendly_name": "Bear"})
    resolved_auto = coord._resolve_shortcut_wire_items(
        [
            {
                "kind": "entity",
                "target": "automation.bear",
                "action": "trigger",
                "icon": "mdi:teddy-bear",
                "confirm": True,
            },
            {
                "kind": "entity",
                "target": "automation.bear",
                "action": "toggle",
                "icon": "mdi:teddy-bear",
            },
        ],
        max_len=8,
    )
    assert resolved_auto[0]["state"] == -1
    assert resolved_auto[1]["state"] == 1

    # 12) `_apply_stored_runtime` restores area, wallpaper, & screensaver photo
    coord.active_area_id = None
    coord._apply_stored_runtime(
        {
            "active_area_id": "kitchen",
            "current_wallpaper": "preset:ocean_waves",
            "current_screensaver_photo": "preset:mars_crater",
        }
    )
    assert coord.active_area_id == "kitchen"
    assert coord.current_wallpaper == "preset:ocean_waves"
    assert coord.current_screensaver_photo == "preset:mars_crater"

    # 13) `_async_on_core_config_update` triggered via real HA core config event
    hass.bus.async_fire(EVENT_CORE_CONFIG_UPDATE)
    await hass.async_block_till_done()

    # 14) `_init_startup_speaker_and_area` clears unproxied stale area when proxies exist
    await seed_ble_proxies(hass)
    ensure_area(hass, "Garage", area_id="garage")
    _update_subentry_fields(
        hass,
        entry,
        coord,
        {CONF_DEFAULT_AREA: "", CONF_NATIVE_BLE_TRACKING: True},
    )
    coord.active_area_id = "garage"
    coord._init_startup_speaker_and_area()
    assert coord.active_area_id != "garage"

    # 15) `_async_sync_startup_feeds` fallback when `get_latter_system` returns None
    with (
        patch("custom_components.latter.coordinator.core.get_latter_system", return_value=None),
        patch.object(coord, "async_refresh_weather_forecast", new_callable=AsyncMock) as wx_mock,
        patch.object(coord, "async_refresh_calendar_agenda", new_callable=AsyncMock) as cal_mock,
    ):
        await coord._async_sync_startup_feeds()
    assert wx_mock.await_count == 1
    assert cal_mock.await_count == 1

    # 17) `_on_ble_address_matched` blank & duplicate head address early returns
    coord._on_ble_address_matched("   ")
    coord._on_ble_address_matched("aa:bb:cc:11:22:33")
    before_list = list(coord._matched_ble_addresses)
    coord._on_ble_address_matched("AA:BB:CC:11:22:33")
    assert coord._matched_ble_addresses == before_list

    # 19) `match_coordinator_target` empty target & child device `via_device_id` match
    assert match_coordinator_target(hass, [coord], None) is coord
    assert match_coordinator_target(hass, [coord, ble_coord], "") is None
    via_child = register_device(
        hass,
        config_entry_id=entry.entry_id,
        identifiers={("other_domain", "child_via_esp")},
        name="Child Via ESP",
        via_device_id=coord.esphome_device_id,
        entry_domain=DOMAIN,
    )
    assert match_coordinator_target(hass, [coord], via_child.id) is coord

    # 20) `async_cleanup` cancels in-flight `doorbell_reply_task`, then `async_setup` recreates `_rpc_receiver` & catches audit error
    reply_task = hass.async_create_task(asyncio.sleep(60), name="cov_doorbell_reply")
    coord.doorbell_reply_task = reply_task
    coord.async_cleanup()
    await hass.async_block_till_done()
    assert reply_task.cancelled()

    coord._rpc_receiver = None
    with patch(
        "custom_components.latter.coordinator.core.async_audit_coordinator_health",
        side_effect=RuntimeError("setup audit boom"),
    ):
        await coord.async_setup()
    assert coord.rpc_receiver is not None

    await flush_debouncers(hass)
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_coordinator_runtime_write_gating_options_race_and_caches(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify runtime snapshot write gating, options race fix, entity cache, hub_sync no-op, and device group cache."""
    entry, _sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    slug = coord.device_slug

    # 1) Runtime snapshot omits volatile `rev` and does not churn on live `last_media_position` ticks or `sun.sun` / weather refreshes
    snap_initial = coord._build_persisted_snapshot()
    assert "rev" not in snap_initial
    coord._runtime.seed_snapshot(snap_initial)
    with patch.object(coord._runtime.store, "async_delay_save") as delay_save_spy:
        coord.last_media_position = 42.0
        coord.apply_weather_snapshot(None, None)
        coord.async_notify_listeners()
        assert coord._build_persisted_snapshot()["last_media_position"] == snap_initial["last_media_position"]
        assert delay_save_spy.call_count == 0

        coord.sync_persisted_media_position()
        assert coord._build_persisted_snapshot()["last_media_position"] == 42.0
        coord.schedule_persist_runtime_state()
        assert delay_save_spy.call_count == 1

    # 2) `update_device_config` short-circuits identical writes without mutating subentry
    coord.update_device_config(dict(coord.device_data))
    await hass.async_block_till_done()
    with patch.object(
        hass.config_entries,
        "async_update_subentry",
        wraps=hass.config_entries.async_update_subentry,
    ) as sub_spy:
        coord.update_device_config(dict(coord.device_data))
        assert sub_spy.call_count == 0

    # 3) `async_update_device_prefs` refreshes `_applied_options_snapshot` so `_async_update_listener`
    # does not trigger a redundant full `async_apply_options()` rebind on non-structural prefs.
    with patch.object(
        coord, "async_apply_options", wraps=coord.async_apply_options
    ) as apply_spy:
        await coord.async_update_device_prefs({"bedtime_active": True})
        await hass.async_block_till_done()
        assert coord._applied_options_snapshot == coord._capture_options_snapshot()
        assert apply_spy.call_count == 0

    # 4) Bound ESPHome entity map caches across repeated lookups and invalidates on registry_rev bump
    idx = get_area_state_index(hass)
    coord.invalidate_bound_entity_cache()
    with patch.object(
        er, "async_entries_for_device", wraps=er.async_entries_for_device
    ) as er_spy:
        _ = coord.device_entity("sensor", "system_rpc_outbox")
        _ = coord.device_state("sensor", "system_rpc_outbox")
        _ = coord.is_device_online()
        assert er_spy.call_count == 1
        idx.rebuild()
        _ = coord.device_entity("sensor", "system_rpc_outbox")
        assert er_spy.call_count == 2

    # 5) `_esphome_entry_for_device` resolves bound ESPHome entry in O(1) without device-registry scans
    esp_dev = dr.async_get(hass).async_get(coord.esphome_device_id)
    assert esp_dev is not None
    with patch.object(
        dr, "async_entries_for_config_entry", wraps=dr.async_entries_for_config_entry
    ) as dr_spy:
        found_entry = _esphome_entry_for_device(hass, esp_dev)
        assert found_entry is not None
        assert found_entry.domain == "esphome"
        assert dr_spy.call_count == 0

    # 6) `async_save_and_broadcast_global_config` short-circuits when values are unchanged
    await async_save_and_broadcast_global_config(
        hass, {CONF_BROADCAST_PHRASES: ["Dinner is ready"]}
    )
    with patch.object(
        coord, "async_on_global_config_updated", new_callable=AsyncMock
    ) as broadcast_spy:
        await async_save_and_broadcast_global_config(
            hass, {CONF_BROADCAST_PHRASES: ["Dinner is ready"]}
        )
        assert broadcast_spy.await_count == 0

    # 7) `get_device_groups` caches normalized groups, isolates caller mutations, and tracks updates
    groups_a = get_device_groups(hass)
    assert groups_a
    first_id = groups_a[0]["id"]
    groups_a[0]["name"] = "Mutated In Caller"
    groups_b = get_device_groups(hass)
    assert groups_b[0]["id"] == first_id
    assert groups_b[0]["name"] != "Mutated In Caller"

    custom_group = {
        "id": "custom_bench",
        "name": "Custom Bench",
        "icon": "mdi:desktop-classic",
        "device_config": {},
    }
    await async_save_and_broadcast_global_config(
        hass, {CONF_DEVICE_GROUPS: [*groups_b, custom_group]}
    )
    groups_c = get_device_groups(hass)
    assert any(g["id"] == "custom_bench" for g in groups_c)

    # Confirm `slug` sensor identity stayed intact through all checks
    assert hass.states.get(f"sensor.{slug}_timer_ends") is not None
    assert await hass.config_entries.async_unload(entry.entry_id) is True
