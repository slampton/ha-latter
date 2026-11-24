"""Targeted real-HA 2026.11 coverage tests for hub sync, feeds, wallpapers, groups, identity, backup, and sensors."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
import inspect
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from homeassistant.const import (
    EVENT_CORE_CONFIG_UPDATE,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_SERVICE_REGISTERED,
)
from homeassistant.core import CoreState, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from PIL import Image, ImageOps
import pytest

import custom_components.latter as latter_init
from custom_components.latter import (
    backup as backup_mod,
    binary_sensor as binary_sensor_mod,
    config_defaults,
    feeds as feeds_mod,
    hub_registry,
    hub_sync,
    identity as identity_mod,
    sensor as sensor_mod,
)
from custom_components.latter.const import (
    CONF_AREA_FOLLOW_DWELL_S,
    CONF_BLE_CATEGORY,
    CONF_BLE_REF_POWER,
    CONF_BLE_TARGET_ADDRESS,
    CONF_BROADCAST_SPEAKER_ENTITIES,
    CONF_CALENDAR_ENTITIES,
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_CUSTOM_COLOR,
    CONF_DEVICE_GROUP,
    CONF_DEVICE_GROUPS,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    CONF_IGNORED_DISCOVERED_DEVICES,
    CONF_MA_PLAYER_ENTITY,
    CONF_SCREENSAVER_CYCLE_MINUTES,
    CONF_SCREENSAVER_SHUFFLE,
    CONF_SITE_ID,
    CONF_SYSTEM_BLE_UUID,
    CONF_SYSTEM_CONFIG_REV,
    CONF_WALLPAPER_CYCLE_MINUTES,
    CONF_WALLPAPER_FAVORITES,
    CONF_WALLPAPER_SOURCE,
    CONF_WEATHER_ENTITY,
    DEFAULT_BLE_CATEGORY,
    DEFAULT_DEVICE_GROUP,
    DEFAULT_SCREENSAVER_CYCLE_MINUTES,
    DOMAIN,
    GLOBAL_STORAGE_KEY,
    STORAGE_VERSION,
    SUBENTRY_BLE_TAG,
    SUBENTRY_DEVICE,
)
from custom_components.latter.coordinator import runtime as coordinator_runtime
from custom_components.latter.groups import device_groups
from custom_components.latter.protocol_specs import DEVICE_PREF_SPECS, DevicePrefSpec
from custom_components.latter.studio.settings_cleaners import SettingsScopeError
from custom_components.latter.wallpapers import (
    media_import as wp_import,
    models as wp_models,
    pools as wp_pools,
    store as wp_store,
)
from tests.helpers.ble_and_ws import ensure_bluetooth_manager, make_jpeg_bytes
from tests.helpers.ha_setup import (
    add_mock_entry,
    ensure_area,
    flush_debouncers,
    get_test_manifest,
    make_subentry_dict,
    prepare_latter_dependencies,
    register_device,
    register_entity,
    seed_device_hello_manifest,
)
from tests.helpers.service_mocks import mock_service


async def test_hub_sync_helpers_rotation_listeners_and_fallbacks(
    hass: Any, setup_latter_hub: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover hub_sync helpers, HMAC rotation, sky/weather listeners, periodic timers, and error paths."""
    monkeypatch.setattr(hass.config, "config_dir", str(tmp_path))

    # Pure helper edge cases (lines 62, 65-66, 96, 98)
    assert hub_sync._safe_hour(True, 22) == 22
    assert hub_sync._safe_hour(None, 22) == 22
    assert hub_sync._safe_hour("bad_hour", 7) == 7
    assert hub_sync._safe_hour(object(), 7) == 7
    assert hub_sync._safe_hour(25, 7) == 1
    assert hub_sync._is_hour_in_bedtime_window(5, 8, 8) is False
    assert hub_sync._is_hour_in_bedtime_window(10, 8, 12) is True
    assert hub_sync._is_hour_in_bedtime_window(14, 8, 12) is False

    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)
    assert coord is not None
    rt = hub_sync._get_feed_runtime(sys_obj)

    # Lazy UrlSigner creation inside _get_feed_runtime when both _url_signer and factory are None (line 129)
    orig_factory = hub_registry._HUB_HOOKS.url_signer_factory
    try:
        sys_obj.url_signer = None
        hub_registry._HUB_HOOKS.url_signer_factory = None
        hub_sync._get_feed_runtime(sys_obj)
        assert sys_obj.url_signer is not None
    finally:
        hub_registry._HUB_HOOKS.url_signer_factory = orig_factory

    # Rotate hub HMAC secret (lines 144-158)
    old_secret = sys_obj.hmac_secret
    await hub_sync.async_rotate_hub_hmac_secret(sys_obj)
    assert sys_obj.hmac_secret != old_secret
    assert hub_registry.get_domain_data(hass).hmac_secret == sys_obj.hmac_secret
    assert sys_obj.config["hmac_secret_hex"] == sys_obj.hmac_secret.hex()

    # Seed bedtime trackers across display + BLE tag coordinators, then verify idempotent skip (lines 167-179)
    rt.bedtime_sched_trackers.clear()
    hub_sync._seed_bedtime_schedule_trackers(sys_obj, rt)
    assert coord.subentry_id in rt.bedtime_sched_trackers
    assert "sub_tag" not in rt.bedtime_sched_trackers
    seeded_snapshot = rt.bedtime_sched_trackers[coord.subentry_id]
    hub_sync._seed_bedtime_schedule_trackers(sys_obj, rt)
    assert rt.bedtime_sched_trackers[coord.subentry_id] == seeded_snapshot

    # Stale bedtime tracker pruning (line 363)
    rt.bedtime_sched_trackers["stale_removed_sub"] = (True, 22, 7, False)
    await hub_sync.async_evaluate_hub_bedtime_schedules(sys_obj)
    assert "stale_removed_sub" not in rt.bedtime_sched_trackers

    # Core config update event invalidates LAN URL caches (lines 189-192, 250)
    hass.bus.async_fire(EVENT_CORE_CONFIG_UPDATE, {})
    await hass.async_block_till_done()

    # Weather listener bind, state change trigger, and rebind/unsubscribe (lines 223-224, 230)
    sys_obj.config[CONF_WEATHER_ENTITY] = "weather.home"
    hub_sync.bind_hub_feed_listeners(sys_obj)
    assert rt.tracked_weather_entity == "weather.home"
    hass.states.async_set("weather.home", "cloudy", {"temperature": 66, "humidity": 55})
    await hass.async_block_till_done()
    assert sys_obj.weather_loaded is True

    # Sky state change with existing weather_snapshot: unchanged early return, then mutated fanout (lines 198-207)
    hub_sync._handle_sky_state_change(sys_obj)
    hass.states.async_set(
        "sun.sun",
        "below_horizon",
        {"elevation": -14.2, "azimuth": 265.0, "next_rising": "2026-11-24T14:00:00Z"},
    )
    await hass.async_block_till_done()
    assert sys_obj.weather_snapshot is not None
    assert sys_obj.weather_snapshot[1]["sun_state"] == "below_horizon"
    assert coord.weather_attributes["sun_state"] == "below_horizon"

    # Rebind to nonexistent weather entity -> unsubscribes previous listener (223-224),
    # then sky-only fallback when snap is None (383-401), then coalesce early return (379)
    sys_obj.config[CONF_WEATHER_ENTITY] = "weather.missing_station"
    hub_sync.bind_hub_feed_listeners(sys_obj)
    assert rt.tracked_weather_entity == "weather.missing_station"
    await hub_sync.async_refresh_hub_weather(sys_obj)
    assert sys_obj.weather_snapshot is not None
    assert sys_obj.weather_snapshot[1]["condition"] == ""
    assert coord.weather_attributes["weather_entity"] == ""
    await hub_sync.async_refresh_hub_weather(sys_obj, coalesce=True)

    # Calendar refresh error path restores calendar_last_fetch_mono and re-raises (lines 435-438)
    prev_cal_mono = 123.45
    rt.calendar_last_fetch_mono = prev_cal_mono

    async def _raise_cal(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("calendar fetch failure")

    with monkeypatch.context() as mp:
        mp.setattr(hub_sync, "async_fetch_raw_calendar_events", _raise_cal)
        with pytest.raises(RuntimeError, match="calendar fetch failure"):
            await hub_sync.async_refresh_hub_calendar(sys_obj, days=30, coalesce=False)
    assert rt.calendar_last_fetch_mono == prev_cal_mono

    # Empty updates short-circuit in async_save_and_broadcast_global_config (line 490)
    rev_before = hub_registry.get_system_config_rev(hass)
    same_cfg = await hub_sync.async_save_and_broadcast_global_config(hass, {})
    assert same_cfg is sys_obj.config
    assert hub_registry.get_system_config_rev(hass) == rev_before

    # Cleanup cancels in-flight hub background task (line 304)
    pending_coro = asyncio.sleep(60)
    hub_sync._spawn_hub_task(sys_obj, pending_coro, "latter_test_cancel_task")
    assert rt.background_tasks
    spawned_tasks = list(rt.background_tasks)
    hub_sync.async_cleanup_hub_feeds(sys_obj)
    await asyncio.sleep(0)
    assert all(t.cancelled() or t.done() for t in spawned_tasks)

    # Rebind while capturing periodic timer callbacks and execute all 3 coroutines (lines 268, 278, 288)
    captured_timers: list[Any] = []
    real_track_interval = hub_sync.async_track_time_interval

    def _capture_interval(h: Any, action: Any, interval: timedelta) -> Any:
        captured_timers.append(action)
        return real_track_interval(h, action, interval)

    with monkeypatch.context() as mp:
        mp.setattr(hub_sync, "async_track_time_interval", _capture_interval)
        hub_sync.bind_hub_feed_listeners(sys_obj)
    assert len(captured_timers) == 3
    now_dt = dt_util.utcnow()
    for cb in captured_timers:
        await cb(now_dt)

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_feeds_parsing_weather_calendar_and_coordinator_fallbacks(
    hass: Any, setup_latter_hub: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover feeds.py parsing edge cases, weather forecasts, calendar dedup/caps, and standalone fallbacks."""
    monkeypatch.setattr(hass.config, "config_dir", str(tmp_path))

    # _opt_float bad inputs (lines 62-63) & _resolve_hass_temp_unit None hass fallback (line 369)
    assert feeds_mod._opt_float("not-a-float") is None
    assert feeds_mod._opt_float(object()) is None
    assert feeds_mod._resolve_hass_temp_unit(None, "unknown_unit") == ""

    # Moon phase sensor state path (lines 82-83)
    hass.states.async_set("sensor.moon_phase", "full_moon")
    sky = feeds_mod.read_sun_and_moon_fields(hass)
    assert sky["moon_phase"] == "full_moon"

    # Timed & all-day event end calculations (lines 165, 175, 180-183)
    now_local = dt_util.now()
    tz = now_local.tzinfo
    start_dt = datetime(2026, 11, 23, 14, 30, tzinfo=tz)
    end_d, end_min = feeds_mod._compute_timed_event_end(start_dt, date(2026, 11, 23), 870, "invalid-end")
    assert (end_d, end_min) == (date(2026, 11, 23), 930)

    next_midnight = datetime(2026, 11, 24, 0, 0, 0, tzinfo=tz).isoformat()
    end_d2, end_min2 = feeds_mod._compute_timed_event_end(start_dt, date(2026, 11, 23), 870, next_midnight)
    assert (end_d2, end_min2) == (date(2026, 11, 23), 1440)

    assert feeds_mod._compute_all_day_event_end(date(2026, 11, 23), "2026-11-25") == date(2026, 11, 24)
    assert feeds_mod._compute_all_day_event_end(
        date(2026, 11, 23), datetime(2026, 11, 26, 0, 0, 0, tzinfo=tz).isoformat()
    ) == date(2026, 11, 25)
    assert feeds_mod._compute_all_day_event_end(date(2026, 11, 23), "") == date(2026, 11, 23)

    # _parse_event_dict missing start (192), unparseable start (200), all-day event (197-198, 206-207)
    assert feeds_mod._parse_event_dict({"summary": "No Start"}, "calendar.home", now_local) is None
    assert feeds_mod._parse_event_dict({"start": "not-a-date"}, "calendar.home", now_local) is None
    parsed_all_day = feeds_mod._parse_event_dict(
        {"start": "2026-11-24", "end": "2026-11-26", "summary": "Site Holiday"},
        "calendar.home",
        now_local,
    )
    assert parsed_all_day is not None
    assert parsed_all_day["all_day"] is True
    assert parsed_all_day["start_min"] == -1
    assert parsed_all_day["end_min"] == -1
    assert parsed_all_day["end_ymd"] == "2026-11-25"

    # Empty calendar window with no calendars (line 511)
    assert await feeds_mod.async_fetch_calendar_window(
        hass, ["calendar.nonexistent"], date(2026, 11, 23), date(2026, 11, 25)
    ) == []

    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    assert coord is not None

    # Missing weather entity -> None (line 413)
    assert await feeds_mod.async_fetch_weather_snapshot(hass, "weather.does_not_exist") is None

    # Live weather.get_forecasts returning datetime, date, invalid datetime, and non-dict rows (375-382, 429-433)
    mock_service(
        hass,
        "weather",
        "get_forecasts",
        lambda _call: {
            "weather.home": {
                "forecast": [
                    {
                        "datetime": "2026-11-23T12:00:00+00:00",
                        "condition": "sunny",
                        "temperature": 74.2,
                        "templow": 55.1,
                    },
                    {
                        "datetime": "2026-11-24",
                        "condition": "cloudy",
                        "temperature": 68,
                        "templow": 50,
                    },
                    {
                        "datetime": "bad-timestamp",
                        "condition": "rainy",
                        "temperature": 60,
                        "templow": 45,
                    },
                    "not-a-dict",
                ]
            }
        },
        supports_response=SupportsResponse.ONLY,
    )
    snap = await feeds_mod.async_fetch_weather_snapshot(hass, "weather.home")
    assert snap is not None
    fc_recs, w_fields = snap
    assert len(fc_recs) == 2
    assert w_fields["high"] == 74.2
    assert w_fields["low"] == 55.1

    # Calendar events with duplicate UIDs, duplicate no-UID summaries, and max_events break (297, 542, 545-548, 551-552)
    hass.states.async_set("calendar.site", "off", {"friendly_name": "Site Calendar"})
    t1 = (dt_util.utcnow() + timedelta(hours=2)).isoformat()
    t2 = (dt_util.utcnow() + timedelta(hours=4)).isoformat()
    t3 = (dt_util.utcnow() + timedelta(hours=6)).isoformat()
    mock_service(
        hass,
        "calendar",
        "get_events",
        lambda _call: {
            "calendar.site": {
                "events": [
                    {"summary": "Standup", "start": t1, "uid": "uid-1"},
                    {"summary": "Standup", "start": t1, "uid": "uid-1"},
                    {"summary": "Lunch", "start": t2},
                    {"summary": "Lunch", "start": t2},
                    {"summary": "Wrap Up", "start": t3, "uid": "uid-3"},
                ]
            }
        },
        supports_response=SupportsResponse.ONLY,
    )
    capped_recs, capped_rows = await feeds_mod.async_fetch_raw_calendar_events(
        hass, ["calendar.site"], days=7, max_events=1
    )
    assert len(capped_recs) == 1
    assert len(capped_rows) == 1

    win_events = await feeds_mod.async_fetch_calendar_window(
        hass, ["calendar.site"], dt_util.now().date(), dt_util.now().date() + timedelta(days=2), max_events=2
    )
    assert len(win_events) == 2
    assert [e["summary"] for e in win_events] == ["Standup", "Lunch"]

    # apply_coordinator_weather_snapshot early return when weather_ent set and snap is None (line 630)
    prev_attrs = dict(coord.weather_attributes)
    feeds_mod.apply_coordinator_weather_snapshot(coord, "weather.home", None)
    assert coord.weather_attributes == prev_attrs

    # Coordinator calendar/weather refresh when coordinator is not in sys_obj.coordinators (lines 491, 670)
    sys_obj.config[CONF_CALENDAR_ENTITIES] = ["calendar.site"]
    sys_obj.config[CONF_WEATHER_ENTITY] = "weather.home"
    popped = sys_obj.coordinators.pop(coord.subentry_id)
    try:
        await feeds_mod.async_refresh_coordinator_calendar(coord, days=30)
        assert len(coord.calendar_events) == 3
        await feeds_mod.async_refresh_coordinator_weather(coord)
        assert coord.weather_attributes["weather_entity"] == "weather.home"
    finally:
        sys_obj.coordinators[coord.subentry_id] = popped

    # Non-30-day calendar refresh bypasses hub feed (lines 493-498)
    await feeds_mod.async_refresh_coordinator_calendar(coord, days=7)
    assert len(coord.calendar_events) == 3

    # Weather refresh without system hub: empty weather_entity (672-675), then populated weather_entity (676-677)
    with monkeypatch.context() as mp:
        mp.setattr(feeds_mod, "get_latter_system", lambda _h: None)
        sys_obj.config[CONF_WEATHER_ENTITY] = ""
        await feeds_mod.async_refresh_coordinator_weather(coord)
        assert coord.weather_attributes["weather_entity"] == ""

        sys_obj.config[CONF_WEATHER_ENTITY] = "weather.home"
        await feeds_mod.async_refresh_coordinator_weather(coord)
        assert coord.weather_attributes["weather_entity"] == "weather.home"
        assert coord.weather_attributes["high"] == 74.2

    await flush_debouncers(hass)
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_wallpapers_store_models_and_pools_edge_cases(
    hass: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover wallpapers models, store parsing/errors/restore, and pool resolver edge cases in isolation."""
    monkeypatch.setattr(hass.config, "config_dir", str(tmp_path))
    orig_snap = wp_store._PHOTO_LIBRARY_SNAPSHOT
    orig_root = wp_store._LOADED_WALLPAPER_ROOT
    try:
        # wallpapers/models.py (lines 207, 210-211, 279, 429)
        crop_defaults = wp_models.normalize_crop(None, True, "not-a-float")
        assert crop_defaults == wp_models.PhotoCrop(0.5, 0.5, 1.0)
        assert wp_models._clamp_crop_float(object(), 0.25, 0.0, 1.0) == 0.25
        with pytest.raises(ValueError, match="invalid dimensions"):
            wp_models.compute_crop_box(0, 100, 200, 200)
        exact_preset = wp_models.render_builtin_preset_image("preset:forest_mountains", 720, 720)
        assert exact_preset.size == (720, 720)

        # _parse_raw_collections edge cases (lines 99, 103-104, 108)
        raw_cols: list[Any] = [
            "not_a_mapping",
            {"id": "bad_id", "name": "Bad"},
            {"id": "col_aaaa", "name": "First"},
            {"id": "col_aaaa", "name": "Duplicate"},
            *[{"id": f"col_{i:04d}", "name": f"Col {i}"} for i in range(wp_models.MAX_COLLECTIONS + 5)],
        ]
        parsed_cols, valid_cids, col_changed = wp_store._parse_raw_collections(raw_cols)
        assert col_changed is True
        assert len(parsed_cols) == wp_models.MAX_COLLECTIONS
        assert "col_aaaa" in valid_cids

        # _parse_indexed_photo_entry (lines 132, 150-151, 154-159, 162) & _adopt_orphan_original (185-186)
        root = wp_models.get_wallpaper_root(hass)
        orig_dir = wp_store.originals_dir(root)
        orig_dir.mkdir(parents=True, exist_ok=True)
        valid_jpg = orig_dir / "good_1234.jpg"
        valid_jpg.write_bytes(make_jpeg_bytes(120, 90))
        corrupt_jpg = orig_dir / "bad_5678.jpg"
        corrupt_jpg.write_bytes(b"corrupt-jpeg-data")

        rec_invalid_pid, changed_pid = wp_store._parse_indexed_photo_entry("bad_id", {}, valid_jpg, set())
        assert (rec_invalid_pid, changed_pid) == (None, True)

        rec_good, changed_good = wp_store._parse_indexed_photo_entry(
            "photo:good_1234",
            {"width": "bad", "height": "bad", "source_kind": "unsupported_kind"},
            valid_jpg,
            set(),
        )
        assert rec_good is not None
        assert changed_good is True
        assert (rec_good.width, rec_good.height) == (120, 90)
        assert rec_good.source_kind == "upload"

        rec_corrupt, changed_corrupt = wp_store._parse_indexed_photo_entry(
            "photo:bad_5678",
            {"width": "bad", "height": "bad"},
            corrupt_jpg,
            set(),
        )
        assert rec_corrupt is not None
        assert changed_corrupt is True
        assert (rec_corrupt.width, rec_corrupt.height) == (
            wp_store._DEFAULT_FALLBACK_DIM,
            wp_store._DEFAULT_FALLBACK_DIM,
        )
        assert wp_store._adopt_orphan_original("photo:bad_5678", corrupt_jpg) is None

        # _parse_preset_collections (lines 212-213)
        pcols, pchanged = wp_store._parse_preset_collections(
            {"preset:unknown_id": ["col_aaaa"], "preset:forest_mountains": "not_a_list"},
            {"col_aaaa"},
        )
        assert pcols == {}
        assert pchanged is True

        # _load_photo_library_sync malformed index.json (275-276) & write OSError (281-282)
        (root / wp_models.INDEX_FILENAME).write_text("{malformed-json", encoding="utf-8")
        with monkeypatch.context() as mp:
            def _raise_oserror(*_a: Any, **_kw: Any) -> None:
                raise OSError("read-only fs")

            mp.setattr(wp_store, "_write_index_atomic", _raise_oserror)
            loaded = wp_store._load_photo_library_sync(root)
            assert "photo:good_1234" in loaded.photos
            assert "photo:bad_5678" not in loaded.photos

        # ensure_loaded_locked reloads when switching to a different root (line 291)
        alt_root = tmp_path / "alt_wallpapers"
        alt_root.mkdir(parents=True, exist_ok=True)
        with wp_store.LIBRARY_LOCK:
            alt_snap = wp_store.ensure_loaded_locked(alt_root)
        assert alt_snap.photos == {}
        # Switch back to hass root
        wp_store._load_photo_library_sync(root)
        corrupt_jpg.unlink(missing_ok=True)
        valid_jpg.unlink(missing_ok=True)
        (root / wp_models.INDEX_FILENAME).unlink(missing_ok=True)
        wp_store._load_photo_library_sync(root)

        # encode_original_jpeg 0x0 image error (line 310)
        with monkeypatch.context() as mp:
            mp.setattr(ImageOps, "exif_transpose", lambda _im: Image.new("RGB", (0, 0)))
            with pytest.raises(ValueError, match="Invalid image dimensions"):
                wp_store.encode_original_jpeg(make_jpeg_bytes(40, 40))

        # mint_unique_photo_id collision loop (lines 332-333)
        tokens = iter(["deadbeef", "cafebabe1234"])
        with monkeypatch.context() as mp:
            mp.setattr(wp_store.secrets, "token_hex", lambda _n: next(tokens))
            pid_minted, fname_minted = wp_store.mint_unique_photo_id(
                "scene", {"photo:scene_deadbeef": object()}
            )
        assert pid_minted == "photo:img_cafebabe1234"
        assert fname_minted == "img_cafebabe1234.jpg"

        # create_collection blank name (384), collision retry (396), rename blank name (413)
        with pytest.raises(ValueError, match="Collection name is required"):
            wp_store.create_collection(hass, "   ")
        col1 = wp_store.create_collection(hass, "Nature")
        existing_hex = col1["id"].removeprefix("col_")
        col_tokens = iter([existing_hex, "1234abcd", "99887766"])
        with monkeypatch.context() as mp:
            mp.setattr(wp_store.secrets, "token_hex", lambda _n: next(col_tokens, "fallback"))
            col2 = wp_store.create_collection(hass, "City")
        assert col2["id"] == "col_1234abcd"
        with pytest.raises(ValueError, match="Collection name is required"):
            wp_store.rename_collection(hass, col1["id"], "   ")

        # save_uploaded_photo_bytes validation errors (lines 719, 721, 739)
        with pytest.raises(ValueError, match="Empty photo upload"):
            wp_store.save_uploaded_photo_bytes(hass, "a.jpg", b"")
        with pytest.raises(ValueError, match="15 MB"):
            wp_store.save_uploaded_photo_bytes(
                hass, "huge.jpg", b"x" * (wp_models.MAX_WALLPAPER_UPLOAD_BYTES + 1)
            )
        with pytest.raises(ValueError, match="Unknown collection"):
            wp_store.save_uploaded_photo_bytes(
                hass, "ok.jpg", make_jpeg_bytes(80, 60), collection_id="col_missing"
            )

        # Upload a real photo and exercise metadata & bulk edge cases (491, 493, 527, 548, 602-603, 628, 645, 658)
        uploaded = wp_store.save_uploaded_photo_bytes(
            hass, "harbor.jpg", make_jpeg_bytes(160, 120), collection_id=col1["id"]
        )
        pid = uploaded["id"]

        with pytest.raises(ValueError, match="Unknown collection"):
            wp_store.update_photo_metadata(hass, pid, collections=["", "col_nope"])
        with pytest.raises(ValueError, match="Photo name cannot be empty"):
            wp_store.update_photo_metadata(hass, pid, name="   ")

        # Preset collection add then clear (line 527)
        wp_store.update_photo_metadata(hass, "preset:forest_mountains", collections=[col1["id"]])
        cleared = wp_store.update_photo_metadata(hass, "preset:forest_mountains", collections=[])
        assert cleared["collections"] == []

        # Bulk empty ids (645), unknown remove_collection (658), remove from photo (602-603) & preset (628)
        assert wp_store.bulk_update_photos(hass, []) == {"updated": 0, "deleted_ids": []}
        with pytest.raises(ValueError, match="Unknown collection"):
            wp_store.bulk_update_photos(hass, [pid], remove_collection="col_nope")
        wp_store.update_photo_metadata(hass, "preset:ocean_waves", collections=[col1["id"]])
        bulk_rem = wp_store.bulk_update_photos(
            hass, [pid, "preset:ocean_waves"], remove_collection=col1["id"]
        )
        assert bulk_rem["updated"] == 2
        assert "preset:ocean_waves" not in wp_store.get_photo_library_snapshot().preset_collections

        # Restore metadata edge cases: unknown/bad entry (813), crop change LRU evict (832, 896),
        # non-list collections_in (870-871), non-mapping photo_metadata_in (848-852), non-mapping preset_collections_in (879)
        wp_store.update_photo_metadata(hass, pid, collections=[col1["id"]])
        wp_store.update_photo_metadata(hass, "preset:ocean_waves", collections=[col1["id"]])
        wp_store.restore_photo_library_metadata(
            hass,
            collections_in=None,
            photo_metadata_in={
                "photo:ghost_9999": {"name": "Ghost"},
                pid: {"name": "Harbor View", "crop": {"x": 0.2, "y": 0.8, "zoom": 2.0}},
            },
            preset_collections_in=None,
        )
        snap_after = wp_store.get_photo_library_snapshot()
        assert snap_after.photos[pid].crop == wp_models.PhotoCrop(0.2, 0.8, 2.0)
        assert snap_after.preset_collections["preset:ocean_waves"] == (col1["id"],)

        # Now drop all collections with photo_metadata_in=None -> filters tags off existing photos (848-852) & presets (879)
        wp_store.restore_photo_library_metadata(
            hass,
            collections_in=[],
            photo_metadata_in=None,
            preset_collections_in=None,
        )
        snap_pruned = wp_store.get_photo_library_snapshot()
        assert snap_pruned.photos[pid].collections == ()
        assert dict(snap_pruned.preset_collections) == {}

        # MAX_COLLECTIONS cap in create_collection (line 389)
        full_cols = tuple(
            wp_models.PhotoCollectionRecord(id=f"col_{i:04d}", name=f"Album {i}")
            for i in range(wp_models.MAX_COLLECTIONS)
        )
        with wp_store.LIBRARY_LOCK:
            wp_store.commit_snapshot_locked(root, wp_models.PhotoLibrarySnapshot(collections=full_cols))
        with pytest.raises(ValueError, match=f"At most {wp_models.MAX_COLLECTIONS}"):
            wp_store.create_collection(hass, "One Too Many")

        # wallpapers/pools.py edge cases (lines 149, 166, 195, 233)
        wp_store._PHOTO_LIBRARY_SNAPSHOT = wp_models.PhotoLibrarySnapshot(
            photo_order=("photo:missing_9999",)
        )
        catalog = wp_pools.list_wallpaper_catalog(hass, "pocket", "", [])
        assert all(item["id"] != "photo:missing_9999" for item in catalog)
        assert wp_pools.resolve_photo_pool("collection", "", "", [], include_dynamic=True) == []
        assert wp_pools.resolve_photo_pool("collection", "", "col_unknown", [], include_dynamic=True) == []
        assert wp_pools.resolve_photo_pool("bogus_mode", "", "", [], include_dynamic=True) == []
    finally:
        wp_store._PHOTO_LIBRARY_SNAPSHOT = orig_snap
        wp_store._LOADED_WALLPAPER_ROOT = orig_root


async def test_wallpapers_media_import_edge_cases(
    hass: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover media_import path normalization, symlink/stat/read errors, dedup re-tagging, and commit fallbacks."""
    monkeypatch.setattr(hass.config, "config_dir", str(tmp_path / "cfg"))
    orig_snap = wp_store._PHOTO_LIBRARY_SNAPSHOT
    orig_root = wp_store._LOADED_WALLPAPER_ROOT
    try:
        wp_root = wp_models.get_wallpaper_root(hass)
        wp_store._load_photo_library_sync(wp_root)

        # _normalize_media_relpath (lines 43, 47)
        assert wp_import._normalize_media_relpath("/etc/passwd") is None
        assert wp_import._normalize_media_relpath("a\x00b.jpg") is None
        assert wp_import._normalize_media_relpath("album//./shot.jpg") == "album/shot.jpg"

        media_dir = tmp_path / "media_local"
        media_dir.mkdir(parents=True)
        valid_bytes = make_jpeg_bytes(100, 80, (40, 180, 90))
        (media_dir / "valid.jpg").write_bytes(valid_bytes)
        (media_dir / "empty.jpg").write_bytes(b"")
        (media_dir / "corrupt.jpg").write_bytes(b"not-a-jpeg")
        (media_dir / "stat_fail.jpg").write_bytes(valid_bytes)
        (media_dir / "read_fail.jpg").write_bytes(valid_bytes)

        # Nonexistent target in resolve_media_path (lines 70-71)
        media_dirs = {"local": str(media_dir)}
        assert wp_import.resolve_media_path(media_dirs, "local", "does_not_exist.jpg") is None

        # Nonexistent root in _discover_valid_media_roots & empty valid_dirs return (lines 83-84, 139)
        empty_res = wp_import.list_media_folder_sync({"missing": str(tmp_path / "no_such_dir")})
        assert empty_res["roots"] == []
        assert empty_res["images"] == []

        # list_media_folder_sync with broken symlink (105-106) and stat OSError (115-116)
        symlink_ok = False
        try:
            os.symlink(tmp_path / "dangling_target.jpg", media_dir / "broken_link.jpg")
            symlink_ok = True
        except OSError:
            symlink_ok = False

        orig_stat = Path.stat
        orig_resolve = Path.resolve

        def _flaky_stat(self: Path, *args: Any, **kwargs: Any) -> Any:
            if self.name == "stat_fail.jpg":
                frame = inspect.currentframe()
                caller = frame.f_back.f_code.co_name if frame and frame.f_back else ""
                if caller == "_scan_media_directory_entries":
                    raise OSError("stat denied")
            return orig_stat(self, *args, **kwargs)

        def _flaky_resolve(self: Path, strict: bool = False) -> Path:
            if not symlink_ok and strict and self.name == "corrupt.jpg":
                raise OSError("broken link simulated")
            return orig_resolve(self, strict=strict)

        with monkeypatch.context() as mp:
            mp.setattr(Path, "stat", _flaky_stat)
            if not symlink_ok:
                mp.setattr(Path, "resolve", _flaky_resolve)
            listed = wp_import.list_media_folder_sync(media_dirs, "local", "")
        listed_names = [im["name"] for im in listed["images"]]
        assert "valid.jpg" in listed_names
        assert "stat_fail.jpg" not in listed_names
        assert "broken_link.jpg" not in listed_names

        # list_media_folder_sync pointing subpath to a file raises ValueError (line 158)
        with pytest.raises(ValueError, match="does not exist or is outside"):
            wp_import.list_media_folder_sync(media_dirs, "local", "valid.jpg")

        # _validate_media_import_source empty file & oversized file (line 190) & read_bytes OSError (192-193)
        val_empty, err_empty = wp_import._validate_media_import_source(media_dirs, "local", "empty.jpg")
        assert val_empty is None
        assert err_empty == "Empty file"

        with monkeypatch.context() as mp:
            mp.setattr(wp_import, "MAX_WALLPAPER_UPLOAD_BYTES", 10)
            val_big, err_big = wp_import._validate_media_import_source(media_dirs, "local", "valid.jpg")
        assert val_big is None
        assert err_big == "File exceeds 15 MB limit"

        orig_read_bytes = Path.read_bytes

        def _fail_read_bytes(self: Path) -> bytes:
            if self.name == "read_fail.jpg":
                raise OSError("disk read failed")
            return orig_read_bytes(self)

        with monkeypatch.context() as mp:
            mp.setattr(Path, "read_bytes", _fail_read_bytes)
            val_err, err_io = wp_import._validate_media_import_source(media_dirs, "local", "read_fail.jpg")
        assert val_err is None
        assert err_io == "disk read failed"

        # import_media_photos_sync edge cases: unknown root (334), empty paths (337), all-failed prepare (213-214, 366)
        with pytest.raises(ValueError, match="Unknown media folder root"):
            wp_import.import_media_photos_sync(hass, media_dirs, "bogus", ["valid.jpg"])
        assert wp_import.import_media_photos_sync(hass, media_dirs, "local", []) == {
            "imported": 0,
            "skipped": 0,
            "failed": [],
            "photos": [],
        }
        corrupt_res = wp_import.import_media_photos_sync(hass, media_dirs, "local", ["corrupt.jpg"])
        assert corrupt_res["imported"] == 0
        assert len(corrupt_res["failed"]) == 1
        assert corrupt_res["failed"][0]["error"].startswith("Invalid image:")

        # Import valid.jpg into col_a, then re-import with deduplicate=True into col_b -> appends col_b (lines 248-261)
        col_a = wp_store.create_collection(hass, "Season A")
        col_b = wp_store.create_collection(hass, "Season B")
        first_imp = wp_import.import_media_photos_sync(
            hass, media_dirs, "local", ["valid.jpg"], collection_id=col_a["id"], deduplicate=True
        )
        assert first_imp["imported"] == 1
        imported_pid = first_imp["photos"][0]["id"]

        second_imp = wp_import.import_media_photos_sync(
            hass, media_dirs, "local", ["valid.jpg"], collection_id=col_b["id"], deduplicate=True
        )
        assert second_imp["imported"] == 0
        assert second_imp["skipped"] == 1
        assert set(wp_store.get_photo_library_snapshot().photos[imported_pid].collections) == {
            col_a["id"],
            col_b["id"],
        }

        # _commit_prepared_media_batch unknown collection (236) and opt_triplet=None encode + error (265-269)
        with pytest.raises(ValueError, match="Unknown collection"):
            wp_import._commit_prepared_media_batch(wp_root, "local", "col_nope", True, [])

        fresh_bytes = make_jpeg_bytes(90, 90, (200, 60, 120))
        fresh_path = media_dir / "late_decode.jpg"
        fresh_path.write_bytes(fresh_bytes)
        corrupt_path = media_dir / "corrupt.jpg"
        imp_cnt, skip_cnt, commit_fails, created = wp_import._commit_prepared_media_batch(
            wp_root,
            "local",
            col_a["id"],
            True,
            [
                ("late_decode.jpg", "late_decode.jpg", fresh_path, "sha_fresh_1", None),
                ("corrupt.jpg", "corrupt.jpg", corrupt_path, "sha_corrupt_1", None),
            ],
        )
        assert imp_cnt == 1
        assert skip_cnt == 0
        assert len(created) == 1
        assert len(commit_fails) == 1
        assert commit_fails[0]["path"] == "corrupt.jpg"
    finally:
        wp_store._PHOTO_LIBRARY_SNAPSHOT = orig_snap
        wp_store._LOADED_WALLPAPER_ROOT = orig_root


async def test_device_groups_and_config_defaults_edge_cases(
    hass: Any, make_esphome_device: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover config_defaults and groups/device_groups hardware traits, matching, batch apply, and reset errors."""
    monkeypatch.setattr(hass.config, "config_dir", str(tmp_path))

    # config_defaults.py missed lines (168-169, 216, 268, 285, 290)
    hw_bad_int = config_defaults.compute_hardware_defaults(
        {"w": 466, "h": 466, "stationary": "not_an_int", "battery": 1, "shape": "circle"}
    )
    assert hw_bad_int[CONF_DEVICE_GROUP] == "pocket_carry"

    hw_slots = config_defaults.compute_hardware_defaults({}, has_native_slots=True)
    assert hw_slots[CONF_DEVICE_GROUP] == "handhelds"

    merged_ma = config_defaults.merge_device_option_defaults(
        hw_slots, None, (), default_speaker="media_player.spk", ma_player_entity="media_player.ma_spk"
    )
    assert merged_ma[CONF_MA_PLAYER_ENTITY] == "media_player.ma_spk"

    assert (
        config_defaults.build_ble_tag_data(
            {"name": "ESPHome   Device", CONF_BLE_TARGET_ADDRESS: "AA:BB:CC:DD:EE:10"}
        )
        is None
    )
    ble_norm = config_defaults.build_ble_tag_data(
        {
            "name": "Key Fob",
            CONF_BLE_TARGET_ADDRESS: "AA:BB:CC:DD:EE:10",
            CONF_BLE_CATEGORY: "unsupported_cat",
        }
    )
    assert ble_norm is not None
    assert ble_norm[CONF_BLE_CATEGORY] == DEFAULT_BLE_CATEGORY

    # Pure helper edge cases in device_groups.py (306, 313-314, 322-324, 357-358, 391, 403-404, 420, 431, 433, 482)
    assert device_groups._coerce_bool_field("yes") is True
    assert device_groups._coerce_bool_field("off") is False

    def _raising_norm(_raw: object) -> str:
        raise ValueError("bad csv")

    assert device_groups._safe_norm_csv("bad", _raising_norm, "fallback_csv") == "fallback_csv"
    assert device_groups.resolve_behavior_key_value(
        {CONF_BROADCAST_SPEAKER_ENTITIES: ["media_player.a", "light.b", "media_player.a", "media_player.c"]},
        CONF_BROADCAST_SPEAKER_ENTITIES,
    ) == ["media_player.a", "media_player.c"]
    assert device_groups.resolve_behavior_key_value(
        {CONF_WALLPAPER_CYCLE_MINUTES: "bad"}, CONF_WALLPAPER_CYCLE_MINUTES
    ) == 0
    assert device_groups.resolve_behavior_key_value(
        {CONF_SCREENSAVER_CYCLE_MINUTES: "bad"}, CONF_SCREENSAVER_CYCLE_MINUTES
    ) == DEFAULT_SCREENSAVER_CYCLE_MINUTES
    assert device_groups.resolve_behavior_key_value(
        {CONF_SCREENSAVER_SHUFFLE: "true"}, CONF_SCREENSAVER_SHUFFLE
    ) is True
    assert device_groups.resolve_behavior_key_value(
        {CONF_AREA_FOLLOW_DWELL_S: "bad"}, CONF_AREA_FOLLOW_DWELL_S
    ) == 10
    assert device_groups.resolve_behavior_key_value({"custom_extra": 99}, "custom_extra") == 99
    assert device_groups._same_control_val("on", True) is True
    assert device_groups._same_control_val("off", False) is True

    # Set up one real Latter hub with 4 real subentries: round pocket, square panel, headless node, BLE tag
    await prepare_latter_dependencies(hass)
    await ensure_bluetooth_manager(hass)
    ensure_area(hass, "Living Room", area_id="living_room")

    esp_pocket, mac_pocket = make_esphome_device(
        hass, slug="pocket_dev", mac="aa:bb:cc:dd:ee:01", name="Pocket Dev", shape="circle"
    )
    esp_square, mac_square = make_esphome_device(
        hass, slug="square_panel", mac="aa:bb:cc:dd:ee:02", name="Square Panel", shape="square", stationary=1
    )
    esp_headless, mac_headless = make_esphome_device(
        hass, slug="headless_node", mac="aa:bb:cc:dd:ee:03", name="Headless Node", display=0, stationary=1
    )

    entry = add_mock_entry(
        hass,
        entry_id="entry_groups_cov",
        domain=DOMAIN,
        title="Latter",
        unique_id=DOMAIN,
        subentries_data=[
            make_subentry_dict(
                {
                    CONF_ESPHOME_DEVICE_ID: esp_pocket.id,
                    "mac": mac_pocket,
                    CONF_DEVICE_SLUG: "pocket_dev",
                    CONF_DEFAULT_AREA: "living_room",
                    CONF_DEFAULT_SPEAKER: "media_player.pocket_dev_music",
                    CONF_WALLPAPER_SOURCE: "preset:forest_mountains",
                    CONF_DEVICE_CUSTOM_COLOR: "#112233",
                },
                subentry_type=SUBENTRY_DEVICE,
                title="Pocket Dev",
                unique_id=f"{DOMAIN}_{mac_pocket}",
                subentry_id="sub_pocket",
            ),
            make_subentry_dict(
                {
                    CONF_ESPHOME_DEVICE_ID: esp_square.id,
                    "mac": mac_square,
                    CONF_DEVICE_SLUG: "square_panel",
                    CONF_DEFAULT_AREA: "living_room",
                    CONF_DEFAULT_SPEAKER: "media_player.square_panel_music",
                    "clock_face": "Minimal Digital",
                },
                subentry_type=SUBENTRY_DEVICE,
                title="Square Panel",
                unique_id=f"{DOMAIN}_{mac_square}",
                subentry_id="sub_square",
            ),
            make_subentry_dict(
                {
                    CONF_ESPHOME_DEVICE_ID: esp_headless.id,
                    "mac": mac_headless,
                    CONF_DEVICE_SLUG: "headless_node",
                    CONF_DEFAULT_AREA: "living_room",
                    CONF_DEFAULT_SPEAKER: "media_player.headless_node_music",
                },
                subentry_type=SUBENTRY_DEVICE,
                title="Headless Node",
                unique_id=f"{DOMAIN}_{mac_headless}",
                subentry_id="sub_headless",
            ),
            make_subentry_dict(
                {
                    CONF_DEVICE_SLUG: "keys_tag",
                    CONF_BLE_TARGET_ADDRESS: "11:22:33:44:55:66",
                },
                subentry_type=SUBENTRY_BLE_TAG,
                title="Keys Tag",
                unique_id="tag_keys",
                subentry_id="sub_tag",
            ),
        ],
    )
    await seed_device_hello_manifest(hass, "sub_pocket", get_test_manifest(hass, esp_pocket.id))
    await seed_device_hello_manifest(hass, "sub_square", get_test_manifest(hass, esp_square.id))
    await seed_device_hello_manifest(hass, "sub_headless", get_test_manifest(hass, esp_headless.id))
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await flush_debouncers(hass)

    sys_obj = entry.runtime_data
    pocket_coord = sys_obj.coordinators["sub_pocket"]
    square_coord = sys_obj.coordinators["sub_square"]
    headless_coord = sys_obj.coordinators["sub_headless"]
    tag_coord = sys_obj.coordinators["sub_tag"]

    # Capability checks: BLE tag returns False (217, 237), unknown capability returns True (220)
    assert device_groups.coordinator_supports_pref(tag_coord, DEVICE_PREF_SPECS[0]) is False
    assert device_groups.coordinator_supports_group_key(tag_coord, "alert_volume") is False
    future_spec = DevicePrefSpec(
        key="future_pref",
        label="Future",
        domain="switch",
        default=False,
        section="general",
        capability=cast(Any, "unmapped_cap"),
        group_tier="behavior",
    )
    assert device_groups.coordinator_supports_pref(pocket_coord, future_spec) is True

    # get_device_groups skips non-dict, empty/'custom' id, and retired builtin id (533, 536, 538)
    sys_obj.config[CONF_DEVICE_GROUPS] = [
        "corrupt_item",
        {"id": DEFAULT_DEVICE_GROUP, "name": "Custom"},
        {"id": "retired_builtin", "builtin": True, "name": "Retired"},
        {"id": "custom_alpha", "name": "Alpha", "device_config": {"alert_volume": 50}},
    ]
    groups_loaded = device_groups.get_device_groups(hass)
    group_ids = [g["id"] for g in groups_loaded]
    assert "retired_builtin" not in group_ids
    assert "custom_alpha" in group_ids

    # seed_group_baseline_from_coordinator captures wallpaper_source (671) & custom color (676)
    seeded_sq: dict[str, Any] = {
        "id": "sq_display_grp",
        "name": "Square Display",
        "include_display": True,
        "include_interface": True,
        "device_config": {},
    }
    device_groups.seed_group_baseline_from_coordinator(hass, seeded_sq, square_coord)
    seeded_pk: dict[str, Any] = {
        "id": "pk_display_grp",
        "name": "Pocket Display",
        "include_display": True,
        "include_interface": False,
        "device_config": {},
    }
    device_groups.seed_group_baseline_from_coordinator(hass, seeded_pk, pocket_coord)
    assert seeded_pk["device_config"][CONF_WALLPAPER_SOURCE] == "preset:forest_mountains"
    assert seeded_pk["device_config"][CONF_DEVICE_CUSTOM_COLOR] == "#112233"

    # Matching square display rewrites Modern Analog -> Minimal Digital (562) and reads runtime wallpaper (565)
    seeded_sq["device_config"]["clock_face"] = "Modern Analog"
    assert (
        device_groups.device_matches_group_baseline(
            hass, square_coord, groups=[seeded_sq], group_id="sq_display_grp"
        )
        is True
    )
    assert device_groups.device_matches_group_baseline(hass, tag_coord) is False  # line 584
    assert device_groups.device_matches_group_baseline(hass, pocket_coord, group_id="custom") is False  # line 600
    assert device_groups.device_matches_group_baseline(hass, pocket_coord, group_id="missing_grp") is False  # line 605

    # Headless device cannot join display-only built-in groups (line 636)
    assert (
        device_groups.resolve_effective_device_group(
            hass, headless_coord, candidate_data={"device_group": "handhelds"}
        )
        == DEFAULT_DEVICE_GROUP
    )

    # _collect_coordinator_group_updates rewrites Modern Analog -> Minimal Digital on square display (line 699)
    sq_updates = device_groups._collect_coordinator_group_updates(
        square_coord,
        {**square_coord.device_data, "clock_face": "Hybrid Digital"},
        {"clock_face": "Modern Analog"},
        ("clock_face",),
    )
    assert sq_updates["clock_face"] == "Minimal Digital"

    # _apply_wallpaper_override_and_timers fallback attribute assignment (line 715)
    plain_target = SimpleNamespace(current_wallpaper="", configured_wallpaper_source="")
    device_groups._apply_wallpaper_override_and_timers(
        plain_target, {CONF_WALLPAPER_SOURCE: "preset:ocean_waves"}, wp_override=True
    )
    assert plain_target.configured_wallpaper_source == "preset:ocean_waves"

    # async_apply_group_baseline_to_coordinators skips BLE tag (771) and raises if cleaner drops all settings (734)
    apply_res = await device_groups.async_apply_group_baseline_to_coordinators(
        hass, seeded_pk, [tag_coord, pocket_coord]
    )
    assert apply_res["updated_devices"] == 1

    with monkeypatch.context() as mp:
        mp.setattr(device_groups, "clean_device_settings", lambda *_a, **_kw: {})
        bad_grp = {**seeded_pk, "device_config": {**seeded_pk["device_config"], "alert_volume": 45}}
        with pytest.raises(ValueError, match="no valid device settings"):
            await device_groups.async_apply_group_baseline_to_coordinators(hass, bad_grp, [pocket_coord])

    # async_reset_device edge cases:
    # 1) BLE tag options-only reset (lines 898-901)
    await device_groups.async_reset_device(hass, tag_coord, device_settings=False, latter_options=True)
    assert tag_coord.device_slug == "keys_tag"

    # 2) Missing factory reset action raises ServiceValidationError (line 884)
    hass.services.async_remove("esphome", "pocket_dev_latter_factory_reset")
    with pytest.raises(ServiceValidationError):
        await device_groups.async_reset_device(hass, pocket_coord, device_settings=True, latter_options=False)

    # 3) Device-settings-only reset strips DEVICE_PREF_KEYS (lines 915-921)
    reset_calls = mock_service(hass, "esphome", "pocket_dev_latter_factory_reset")
    pocket_coord.update_device_config({**pocket_coord.device_data, "alert_volume": 75})
    assert "alert_volume" in pocket_coord.device_data
    await device_groups.async_reset_device(hass, pocket_coord, device_settings=True, latter_options=False)
    assert "alert_volume" not in pocket_coord.device_data
    assert len(reset_calls) == 1

    # 4) Factory reset service raising HomeAssistantError wraps translated error (lines 926-927)
    def _fail_reset(_call: Any) -> None:
        raise HomeAssistantError("device offline")

    mock_service(hass, "esphome", "pocket_dev_latter_factory_reset", _fail_reset)
    with pytest.raises(HomeAssistantError, match="didn't accept Reset to defaults"):
        await device_groups.async_reset_device(hass, pocket_coord, device_settings=True, latter_options=False)

    await flush_debouncers(hass)
    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_hub_registry_and_identity_edge_cases(
    hass: Any, setup_latter_hub: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover hub_registry AreaStateIndex/LatterSystemHub edge cases and identity manifest/device lookups."""
    monkeypatch.setattr(hass.config, "config_dir", str(tmp_path))

    # Before domain data exists: async_stop_area_state_index early return (line 401)
    hub_registry.async_stop_area_state_index(hass)

    # Pure helpers in hub_registry (lines 90, 94-95, 130, 464-469)
    assert hub_registry._iter_registry_entities(cast(Any, SimpleNamespace(entities=None))) == ()
    assert list(hub_registry._iter_registry_entities(cast(Any, SimpleNamespace(entities=["e1"])))) == ["e1"]
    assert (
        hub_registry._is_irrelevant_registry_update(
            "unrelated_registry_event", {"action": "update", "changes": {"name": "X"}}
        )
        is False
    )
    assert hub_registry.safe_hour(True, 22) == 22
    assert hub_registry.safe_hour(None, 22) == 22
    assert hub_registry.safe_hour("25", 7) == 1
    assert hub_registry.safe_hour("bad", 7) == 7

    # Pure helpers in identity (lines 126, 186, 220-221)
    assert identity_mod.manifest_flag({"w": True}, "w") is None
    assert identity_mod.manifest_flag({"w": [1]}, "w") is None
    assert identity_mod.manifest_is_round({"display": 0, "shape": "circle"}) is False
    headless_vc = identity_mod.manifest_video_caps({"display": 0, "w": 466, "h": 466})
    assert (headless_vc["max_w"], headless_vc["max_h"]) == (0, 0)

    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True)
    assert coord is not None

    # AreaStateIndex edge cases (lines 158, 255, 287, 290, 354, 357)
    idx = hub_registry.get_area_state_index(hass)
    idx._dirty_registry = True
    idx.start()
    assert idx._dirty_registry is False
    affected = idx._affected_areas_for_event(ar.EVENT_AREA_REGISTRY_UPDATED, {}, {"living_room": set()})
    assert "living_room" in affected
    idx._on_state_changed(SimpleNamespace(data="not-a-mapping"))
    idx._on_state_changed(SimpleNamespace(data={"entity_id": "missing_dot"}))
    assert idx.entities_in_area("") == []
    _all_in_lr = idx.entities_in_area("living_room", domains=None)
    assert isinstance(_all_in_lr, list)

    # LatterSystemHub lazy getters/setters & config edge cases (lines 522, 529, 538, 543, 563-564, 796-797)
    sys_obj.url_signer = None
    assert sys_obj.url_signer is not None
    sys_obj.rpc_dispatcher = None
    assert sys_obj.rpc_dispatcher is not None

    sys_obj.config[CONF_CALENDAR_ENTITIES] = ["calendar.site", "  "]
    assert sys_obj.calendar_entities == ["calendar.site"]
    sys_obj.config[CONF_CALENDAR_ENTITIES] = "not-a-list"
    assert sys_obj.calendar_entities == []
    sys_obj.config[CONF_SYSTEM_CONFIG_REV] = "corrupt_rev"
    assert hub_registry.get_system_config_rev(hass) == 1

    # Unhooked fallback paths on LatterSystemHub (lines 602-621, 641)
    unsub_calls: list[str] = []
    orig_cleanup_hook = hub_registry._HUB_HOOKS.cleanup_feeds
    orig_cal_hook = hub_registry._HUB_HOOKS.refresh_calendar
    try:
        hub_registry._HUB_HOOKS.refresh_calendar = None
        cal_recs, cal_rows = await sys_obj.async_refresh_calendar_agenda()
        assert cal_recs == sys_obj.calendar_records
        assert cal_rows == sys_obj.calendar_raw_rows

        hub_registry._HUB_HOOKS.cleanup_feeds = None
        sys_obj._unsub_weather_state = lambda: unsub_calls.append("w")
        sys_obj._unsub_sky_state = lambda: unsub_calls.append("s")
        sys_obj._unsub_forecast_timer = lambda: unsub_calls.append("f")
        sys_obj._unsub_calendar_timer = lambda: unsub_calls.append("c")
        sys_obj._unsub_bedtime_timer = lambda: unsub_calls.append("b")
        sys_obj._unsub_core_config = lambda: unsub_calls.append("cfg")
        sys_obj.async_cleanup_feeds()
        assert len(unsub_calls) == 6
        assert sys_obj.weather_loaded is False
        assert sys_obj.calendar_loaded is False
    finally:
        hub_registry._HUB_HOOKS.cleanup_feeds = orig_cleanup_hook
        hub_registry._HUB_HOOKS.refresh_calendar = orig_cal_hook

    # identity.py registry & discovery helpers (lines 52, 303-304, 317, 357, 361, 380, 393-399, 447-448, 476)
    ent_reg = er.async_get(hass)
    assert list(identity_mod.iter_entities(ent_reg))

    esp_dev = dr.async_get(hass).async_get(coord.esphome_device_id)
    assert esp_dev is not None

    # Child Latter device following via_device_id back to ESPHome device (303-304)
    latter_child = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "child_via_test")},
        name="Pocket Child",
        via_device_id=esp_dev.id,
    )
    resolved_via = identity_mod.get_bound_esphome_device(hass, latter_child)
    assert resolved_via is not None and resolved_via.id == esp_dev.id

    # Non-ESPHome device returns empty node name (line 317)
    mqtt_dev = register_device(
        hass,
        config_entry_id="mqtt_entry_1",
        identifiers={("mqtt", "sensor_1")},
        name="MQTT Sensor",
        entry_domain="mqtt",
    )
    assert identity_mod.esphome_node_name(hass, mqtt_dev) == ""

    # Entity matching by original_name (357) and unique_id suffix (361)
    register_entity(
        hass,
        "sensor.custom_alias_entity",
        platform="esphome",
        config_entry_id="esp_entry_pocket_assistant",
        device_id=esp_dev.id,
        original_name="Special Display Metric",
        unique_id="esp_node/custom_metric_suffix",
    )
    assert (
        identity_mod.find_device_entity_by_suffix(
            hass,
            esp_dev.id,
            "sensor",
            ("_no_matching_suffix",),
            original_names=("Special Display Metric",),
        )
        == "sensor.custom_alias_entity"
    )
    assert (
        identity_mod.find_device_entity_by_suffix(
            hass,
            esp_dev.id,
            "sensor",
            ("_no_matching_suffix",),
            unique_id_suffixes=("/custom_metric_suffix",),
        )
        == "sensor.custom_alias_entity"
    )

    # Model-only compatible ESPHome device without registered contract services (line 380)
    model_only_dev = register_device(
        hass,
        config_entry_id="esp_entry_model_only",
        identifiers={("esphome", "aa:bb:cc:dd:ff:99")},
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ff:99")},
        name="Model Only",
        model="Latter Prototype Display",
        entry_domain="esphome",
    )
    assert identity_mod.is_latter_compatible_esphome_device(hass, model_only_dev) is True

    # find_esphome_device_by_mac hit and miss (lines 393-399)
    found_by_mac = identity_mod.find_esphome_device_by_mac(hass, "aa:bb:cc:dd:ee:01")
    assert found_by_mac is not None and found_by_mac.id == esp_dev.id
    assert identity_mod.find_esphome_device_by_mac(hass, "ff:ee:dd:cc:bb:aa") is None

    # Missing or invalid cached hardware manifest returns {}
    assert identity_mod.read_device_hardware_manifest(hass, esp_dev.id) == {}
    assert (
        identity_mod.read_device_hardware_manifest(
            hass, esp_dev.id, cached_manifest={"bad": 1}
        )
        == {}
    )

    # Manifest beacon dict detection (line 476)
    assert (
        identity_mod._has_ble_beacon_entity_or_manifest(hass, esp_dev, {"beacon": {"uuid": "abc"}})
        is True
    )

    assert await hass.config_entries.async_unload(entry.entry_id) is True


async def test_init_lifecycle_discovery_and_rollback_edge_cases(
    hass: Any, make_esphome_device: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover __init__.py store repair, discovery guards, not-running startup, rollback, and non-device subentries."""
    monkeypatch.setattr(hass.config, "config_dir", str(tmp_path))
    await prepare_latter_dependencies(hass)
    await ensure_bluetooth_manager(hass)
    ensure_area(hass, "Living Room", area_id="living_room")

    # 1) _async_ensure_global_store loads existing dict, repairs invalid hex & UUID (lines 174, 192-196, 201-202)
    seed_store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, GLOBAL_STORAGE_KEY)
    await seed_store.async_save(
        {
            "hmac_secret_hex": "z" * 64,
            CONF_SYSTEM_BLE_UUID: "not-a-valid-uuid",
            "extra_preserved": "ok",
        }
    )
    domain_data = hub_registry.get_domain_data(hass)
    domain_data.global_store = None
    repaired_cfg = await latter_init._async_ensure_global_store(hass)
    assert repaired_cfg["extra_preserved"] == "ok"
    assert len(domain_data.hmac_secret) == 32
    assert repaired_cfg[CONF_SYSTEM_BLE_UUID] != "not-a-valid-uuid"

    # 2) Discovery flow scan skips empty flow_id (227) and aborts crashed flow with step_id=None (229-230)
    aborted_ids: list[str] = []
    with monkeypatch.context() as mp:
        mp.setattr(
            hass.config_entries.flow,
            "async_progress_by_handler",
            lambda _domain: [
                {"flow_id": ""},
                {"flow_id": "flow_crashed", "step_id": None},
            ],
        )
        mp.setattr(hass.config_entries.flow, "async_abort", aborted_ids.append)
        latter_init._async_scan_all_esphome_devices_for_discovery(hass)
    assert aborted_ids == ["flow_crashed"]

    # 3) _async_check_esphome_device_for_discovery ignores ignored IDs (250) and non-ESPHome devices (252)
    esp_dev, mac = make_esphome_device(hass, slug="init_test_dev", mac="aa:bb:cc:dd:ee:41")
    mqtt_dev = register_device(
        hass,
        config_entry_id="mqtt_init_1",
        identifiers={("mqtt", "node_1")},
        name="Non-ESPHome Node",
        entry_domain="mqtt",
    )
    domain_data.global_config[CONF_IGNORED_DISCOVERED_DEVICES] = [esp_dev.id]
    latter_init._async_check_esphome_device_for_discovery(hass, esp_dev)
    latter_init._async_check_esphome_device_for_discovery(hass, mqtt_dev)
    domain_data.global_config.pop(CONF_IGNORED_DISCOVERED_DEVICES, None)

    # 4) async_setup while not_running registers EVENT_HOMEASSISTANT_STARTED (433-434),
    # firing it runs _on_ha_started (428-429); duplicate listener bind hits early return (300);
    # missing device update hits (324); stopping state blocks delayed scan (388);
    # leaving unsub_started_scan active lets teardown _on_ha_stop cancel it (412).
    orig_state = hass.state
    try:
        hass.state = CoreState.not_running
        assert await latter_init.async_setup(hass, {}) is True
        assert domain_data.unsub_started_scan is not None

        # Duplicate _register_domain_bus_listeners returns immediately (line 300)
        latter_init._register_domain_bus_listeners(hass, domain_data, lambda _d: None)

        # Fire EVENT_HOMEASSISTANT_STARTED (lines 428-429)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED, {})
        await hass.async_block_till_done()
        assert domain_data.unsub_started_scan is None

        # Fire device registry update for nonexistent device_id (line 324)
        hass.bus.async_fire(
            dr.EVENT_DEVICE_REGISTRY_UPDATED,
            {"action": "update", "device_id": "nonexistent_device_id"},
        )
        await hass.async_block_till_done()

        # Fire esphome contract service registration while stopping -> early return in scheduler (line 388)
        hass.state = CoreState.stopping
        hass.bus.async_fire(
            EVENT_SERVICE_REGISTERED,
            {"domain": "esphome", "service": "init_test_dev_latter_ping"},
        )
        await hass.async_block_till_done()

        # Re-register unsub_started_scan so fixture teardown's EVENT_HOMEASSISTANT_STOP exercises line 412
        hass.state = CoreState.not_running
        assert await latter_init.async_setup(hass, {}) is True
        assert callable(domain_data.unsub_started_scan)
    finally:
        hass.state = orig_state

    # 5) async_setup_entry returns False when get_latter_system returns None (line 500)
    esp_dev2, mac2 = make_esphome_device(hass, slug="init_test_dev2", mac="aa:bb:cc:dd:ee:42")
    entry = add_mock_entry(
        hass,
        entry_id="entry_init_cov",
        domain=DOMAIN,
        title="Latter",
        unique_id=DOMAIN,
        subentries_data=[
            make_subentry_dict(
                {
                    CONF_ESPHOME_DEVICE_ID: esp_dev.id,
                    "mac": mac,
                    CONF_DEVICE_SLUG: "init_test_dev",
                },
                subentry_type=SUBENTRY_DEVICE,
                title="Init Dev 1",
                unique_id=f"{DOMAIN}_{mac}",
                subentry_id="sub_init_1",
            ),
            make_subentry_dict(
                {
                    CONF_ESPHOME_DEVICE_ID: esp_dev2.id,
                    "mac": mac2,
                    CONF_DEVICE_SLUG: "init_test_dev2",
                },
                subentry_type=SUBENTRY_DEVICE,
                title="Init Dev 2",
                unique_id=f"{DOMAIN}_{mac2}",
                subentry_id="sub_init_2",
            ),
            make_subentry_dict(
                {"label": "Auxiliary"},
                subentry_type="aux_non_device",
                title="Aux Entry",
                unique_id="aux_1",
                subentry_id="sub_aux",
            ),
        ],
    )
    with monkeypatch.context() as mp:
        mp.setattr(latter_init, "get_latter_system", lambda _h: None)
        assert await latter_init.async_setup_entry(hass, entry) is False

    # 6) _async_init_entry_coordinators: fallback LatterRpcReceiver attach (461) & rollback on 2nd coord error (468-471, 480-485)
    sys_obj = hub_registry.get_latter_system(hass)
    assert sys_obj is not None
    real_coord_setup = latter_init.LatterCoordinator.async_setup
    setup_count = 0

    async def _fail_on_second_setup(self: Any) -> None:
        nonlocal setup_count
        setup_count += 1
        if setup_count == 2:
            raise RuntimeError("boom on second subentry")
        await real_coord_setup(self)

    with monkeypatch.context() as mp:
        mp.setattr(coordinator_runtime, "_RPC_RECEIVER_FACTORY", None)
        mp.setattr(latter_init.LatterCoordinator, "async_setup", _fail_on_second_setup)
        with pytest.raises(RuntimeError, match="boom on second subentry"):
            await latter_init._async_init_entry_coordinators(
                hass, entry, sys_obj, domain_data.hmac_secret
            )
    assert sys_obj.coordinators == {}

    # 7) async_remove_config_entry_device skips non-device subentry types (line 648)
    orphan_dev = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "orphan_init_dev")},
        name="Orphan Dev",
    )
    assert await latter_init.async_remove_config_entry_device(hass, entry, orphan_dev) is True
    latter_init._cancel_delayed_discovery_scan(domain_data)


async def test_backup_sensor_and_binary_sensor_edge_cases(
    hass: Any, setup_latter_hub: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover backup.py validation/restore paths and sensor.py + binary_sensor.py registry/entity edge cases."""
    monkeypatch.setattr(hass.config, "config_dir", str(tmp_path))

    # Pre-backup before domain data exists returns cleanly (backup.py line 141)
    await backup_mod.async_pre_backup(hass)

    entry, sys_obj, coord = await setup_latter_hub(hass, with_device=True, with_ble_tag=True)
    assert coord is not None

    # backup.py: _serialize_device_snapshot tools/games fallback (168, 170) & device backup validation (225)
    dev_snap = backup_mod._serialize_device_snapshot(hass, coord)
    assert dev_snap["device_config"]["tools_items"] == coord.tools_items_csv
    assert dev_snap["device_config"]["games_items"] == coord.games_items_csv

    with pytest.raises(ValueError, match="needs a target Device"):
        backup_mod.build_backup_bundle(hass, "device", [coord], target_coordinator=None)

    # _build_restored_device_config: SettingsScopeError -> ValueError (260-261),
    # None ref_power pop (265), favorites restore (267), site_id sanitization (273-275)
    with monkeypatch.context() as mp:
        def _raise_dev_scope(*_a: Any, **_kw: Any) -> Any:
            raise SettingsScopeError("invalid device scope")

        mp.setattr(backup_mod, "clean_device_settings", _raise_dev_scope)
        with pytest.raises(ValueError, match="invalid device scope"):
            backup_mod._build_restored_device_config(
                coord, {"alert_volume": 55}, preserve_slug=True
            )

    coord.update_device_config({**coord.device_data, CONF_BLE_REF_POWER: -62})
    restored_cfg = backup_mod._build_restored_device_config(
        coord,
        {
            CONF_BLE_REF_POWER: None,
            CONF_WALLPAPER_FAVORITES: ["preset:ocean_waves", "  ", "preset:mars_crater"],
            CONF_SITE_ID: "North Wing #1!",
        },
        preserve_slug=True,
    )
    assert CONF_BLE_REF_POWER not in restored_cfg
    assert restored_cfg[CONF_WALLPAPER_FAVORITES] == ["preset:ocean_waves", "preset:mars_crater"]
    assert restored_cfg[CONF_SITE_ID] == "north_wing_1"

    # _async_restore_system_global_config: SettingsScopeError -> ValueError (321-322)
    with monkeypatch.context() as mp:
        def _raise_sys_scope(*_a: Any, **_kw: Any) -> Any:
            raise SettingsScopeError("invalid system scope")

        mp.setattr(backup_mod, "clean_system_settings", _raise_sys_scope)
        with pytest.raises(ValueError, match="invalid system scope"):
            await backup_mod._async_restore_system_global_config(
                hass, {CONF_WEATHER_ENTITY: "weather.home"}
            )

    # async_restore_backup_bundle system global_config keys & ignored devices (329, 332)
    sys_res = await backup_mod.async_restore_backup_bundle(
        hass,
        {
            "schema": "latter.backup.v3",
            "scope": "system",
            "global_config": {
                CONF_WEATHER_ENTITY: "weather.home",
                CONF_IGNORED_DISCOVERED_DEVICES: ["esp_ignored_1", "  ", 123],
            },
            "devices": {},
        },
        [coord],
    )
    assert sys_res["scope"] == "system"
    assert sys_obj.config[CONF_WEATHER_ENTITY] == "weather.home"
    assert sys_obj.config[CONF_IGNORED_DISCOVERED_DEVICES] == ["esp_ignored_1"]

    # async_restore_backup_bundle device scope errors (377, 379)
    with pytest.raises(ValueError, match="missing 'device' payload"):
        await backup_mod.async_restore_backup_bundle(
            hass, {"schema": "latter.backup.v3", "scope": "device"}, [coord], target_coordinator=coord
        )
    with pytest.raises(ValueError, match="selected Device"):
        await backup_mod.async_restore_backup_bundle(
            hass,
            {"schema": "latter.backup.v3", "scope": "device", "device": dev_snap},
            [coord],
            target_coordinator=None,
        )

    # sensor.py & binary_sensor.py: _entry_coordinators fallback when entry has no runtime_data (sensor 83-84, bs 38-39)
    bare_entry = add_mock_entry(hass, entry_id="entry_bare_ref", domain="other_domain", title="Bare")
    assert sensor_mod._entry_coordinators(hass, bare_entry) == list(sys_obj.coordinators.values())
    assert binary_sensor_mod._entry_coordinators(hass, bare_entry) == list(sys_obj.coordinators.values())

    # Fire area_registry_updated edge events hitting sensor.py (152, 156, 159) and binary_sensor.py (67, 70, 73)
    hass.bus.async_fire(ar.EVENT_AREA_REGISTRY_UPDATED, {"action": "create", "area_id": ""})
    hass.bus.async_fire(ar.EVENT_AREA_REGISTRY_UPDATED, {"action": "create", "area_id": "living_room"})
    hass.bus.async_fire(ar.EVENT_AREA_REGISTRY_UPDATED, {"action": "create", "area_id": "ghost_area_id"})
    await hass.async_block_till_done()

    # Initial area scan skips already-created and missing Area entries (sensor 130, 133; binary_sensor 130, 133)
    domain_data = hub_registry.get_domain_data(hass)
    tracking = sensor_mod._EntrySensorTracking(
        registered_persons=set(domain_data.registered_person_sensors),
        registered_subentry_floors=set(domain_data.registered_subentry_floors),
        registered_person_floors=set(domain_data.registered_person_floors),
        created_area_occupants=set(domain_data.created_area_occupants_ids),
    )
    with monkeypatch.context() as mp:
        mp.setattr(sensor_mod, "get_ble_proxy_area_ids", lambda _h: {"living_room", "ghost_area_id"})
        mp.setattr(sensor_mod, "get_ble_signature_area_ids", lambda _h: set())
        assert sensor_mod._create_initial_area_occupant_sensors(hass, tracking) == []

    added_bs: list[Any] = []
    with monkeypatch.context() as mp:
        mp.setattr(binary_sensor_mod, "get_ble_proxy_area_ids", lambda _h: {"living_room", "ghost_area_id"})
        mp.setattr(binary_sensor_mod, "get_ble_signature_area_ids", lambda _h: set())
        await binary_sensor_mod.async_setup_entry(
            hass,
            entry,
            lambda ents, **_kw: added_bs.extend(ents),
        )
    assert not any(isinstance(e, binary_sensor_mod.LatterAreaOccupancyBinarySensor) for e in added_bs)

    # Disabled-by-default distance sensors (sensor 415-417, 553-555, 560-561)
    dev_dist_sensor = sensor_mod.LatterBleDistanceSensor(coord)
    assert dev_dist_sensor.native_value is None
    with monkeypatch.context() as mp:
        mp.setattr(
            coord,
            "get_current_area_and_distance",
            lambda: ("Living Room", {"distance_m": 2.345, "area_id": "living_room"}),
        )
        assert dev_dist_sensor.native_value == 2.35
        assert dev_dist_sensor.extra_state_attributes["distance_m"] == 2.345

    person_dist_sensor = sensor_mod.LatterPersonBleDistanceSensor(hass, "person.alex")
    assert person_dist_sensor.native_value is None
    assert isinstance(person_dist_sensor.extra_state_attributes, dict)
    person_dist_sensor._cached_person = ("Living Room", {"distance_m": 1.678})
    assert person_dist_sensor.native_value == 1.68

    # Empty occupant names formatter (sensor line 570) & uncached _get_occ (sensor 626, binary_sensor 192)
    assert sensor_mod.format_bounded_occupant_names(["", "   "]) == ""
    uncached_occ_sensor = sensor_mod.LatterAreaOccupantsSensor(hass, "living_room", "Living Room")
    assert uncached_occ_sensor.native_value == "Empty"
    uncached_occ_bs = binary_sensor_mod.LatterAreaOccupancyBinarySensor(hass, "living_room", "Living Room")
    assert uncached_occ_bs.is_on is False

    await flush_debouncers(hass)
    assert await hass.config_entries.async_unload(entry.entry_id) is True
