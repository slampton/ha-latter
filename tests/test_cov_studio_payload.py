"""Coverage tests for Studio settings cleaners and Studio state payload builders."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import (
    device_registry as dr,
    issue_registry as ir,
)
import pytest

from custom_components.latter.const import (
    CONF_DEFAULT_AREA,
    CONF_DEFAULT_SPEAKER,
    CONF_DEVICE_SLUG,
    CONF_ESPHOME_DEVICE_ID,
    CONF_MA_PLAYER_ENTITY,
    CONF_NATIVE_BLE_TRACKING,
    DOMAIN,
    SUBENTRY_DEVICE,
)
from custom_components.latter.hub_registry import (
    get_area_state_index,
    get_domain_data,
    get_global_config,
)
from custom_components.latter.studio import (
    payload as payload_mod,
    settings_cleaners as cleaners,
)
from tests.helpers.ble_and_ws import ensure_bluetooth_manager
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


def test_settings_cleaners_system_and_view_edge_cases() -> None:
    """Cover strict and non-strict System cleaner branches across phrases, cameras, remotes, palettes, ignored IDs, and BLE."""
    # Broadcast phrases: None, strict non-list error, and non-strict view fallback
    assert cleaners.clean_system_settings({"broadcast_phrases": None}) == {
        "broadcast_phrases": []
    }
    with pytest.raises(cleaners.SettingsScopeError, match="broadcast_phrases must be a list"):
        cleaners.clean_system_settings({"broadcast_phrases": "Dinner"})
    non_strict_view = cleaners.system_settings_view(
        {
            "broadcast_phrases": "not_a_list",
            "camera_configs": "not_a_mapping",
            "remote_groups": [
                "not_a_mapping",
                {"id": "bad id!"},
                {"id": "rg_a", "name": "Alpha", "remotes": ["remote.tv"]},
                {"id": "rg_a", "name": "Duplicate"},
            ],
            "ble_attenuation": True,
            "ble_max_radius_m": "unparseable",
            "ble_max_velocity_mps": float("inf"),
            "ble_away_timeout_s": False,
        }
    )
    assert non_strict_view["broadcast_phrases"] == []
    assert non_strict_view["camera_configs"] == {}
    assert non_strict_view["remote_groups"] == [
        {"id": "rg_a", "name": "Alpha", "area_id": "", "remotes": ["remote.tv"]}
    ]
    assert non_strict_view["ble_attenuation"] == cleaners.DEFAULT_BLE_ATTENUATION
    assert non_strict_view["ble_max_radius_m"] == cleaners.DEFAULT_BLE_MAX_RADIUS_M
    assert non_strict_view["ble_max_velocity_mps"] == cleaners.DEFAULT_BLE_MAX_VELOCITY_MPS
    assert non_strict_view["ble_away_timeout_s"] == cleaners.DEFAULT_BLE_AWAY_TIMEOUT_S

    # Non-strict _ble_int string ValueError & non-finite branches + non-strict camera_configs filters
    view_ble_and_cams = cleaners.system_settings_view(
        {
            "ble_away_timeout_s": "never",
            "camera_configs": {
                "light.porch": {"label": "Skip"},
                "camera.bad_entry": "not_a_dict",
                "camera.front": {
                    "label": "Front | Gate",
                    "unlock_entity": "switch.relay",
                    "show_listen": "yes",
                    "show_talk": True,
                    "show_reply": False,
                },
            },
            "remote_groups": [{"id": f"g_{i}"} for i in range(cleaners.MAX_REMOTE_GROUPS + 3)],
        }
    )
    assert view_ble_and_cams["ble_away_timeout_s"] == cleaners.DEFAULT_BLE_AWAY_TIMEOUT_S
    assert view_ble_and_cams["camera_configs"] == {
        "camera.front": {"label": "Front   Gate", "show_talk": True, "show_reply": False}
    }
    assert len(view_ble_and_cams["remote_groups"]) == cleaners.MAX_REMOTE_GROUPS
    assert (
        cleaners.system_settings_view({"ble_away_timeout_s": float("nan")})["ble_away_timeout_s"]
        == cleaners.DEFAULT_BLE_AWAY_TIMEOUT_S
    )

    # Strict camera_configs errors (outer type, key prefix, entry type, unlock_entity prefix, flag type)
    for bad_cam_cfg in (
        ["not_a_mapping"],
        {"light.entry": {"label": "Entry"}},
        {"camera.front": "not_a_mapping"},
        {"camera.front": {"unlock_entity": "switch.gate"}},
        {"camera.front": {"show_talk": "yes"}},
    ):
        with pytest.raises(cleaners.SettingsScopeError):
            cleaners.clean_system_settings({"camera_configs": bad_cam_cfg})

    # Strict remote_groups errors (type, max count, non-mapping item, invalid id, duplicate id) and exact cap
    for bad_rg in (
        "not_a_list",
        [{"id": f"g{i}"} for i in range(cleaners.MAX_REMOTE_GROUPS + 1)],
        ["not_a_dict"],
        [{"id": "invalid id!"}],
        [{"id": "dup_1"}, {"id": "dup_1"}],
    ):
        with pytest.raises(cleaners.SettingsScopeError):
            cleaners.clean_system_settings({"remote_groups": bad_rg})
    capped_rgs = cleaners.clean_system_settings(
        {"remote_groups": [{"id": f"g{i}"} for i in range(cleaners.MAX_REMOTE_GROUPS)]}
    )
    assert len(capped_rgs["remote_groups"]) == cleaners.MAX_REMOTE_GROUPS

    # Non-mapping palette entry skipped, remotes_list normalized, ignored_discovered_devices strict + cap
    sys_misc = cleaners.clean_system_settings(
        {
            "custom_palettes": ["bad_item", {"name": "Ocean", "hex": "#112233"}],
            "remotes_list": ["remote.den_tv", "media_player.avr", "remote.den_tv"],
            "ignored_discovered_devices": [
                f"dev_{i}" for i in range(cleaners.MAX_IGNORED_DISCOVERED + 5)
            ],
        }
    )
    assert sys_misc["custom_palettes"] == [{"name": "Ocean", "hex": "#112233"}]
    assert sys_misc["remotes_list"] == ["remote.den_tv", "media_player.avr"]
    assert len(sys_misc["ignored_discovered_devices"]) == cleaners.MAX_IGNORED_DISCOVERED

    with pytest.raises(cleaners.SettingsScopeError, match="ignored_discovered_devices must be a list"):
        cleaners.clean_system_settings({"ignored_discovered_devices": "dev_1"})

    # Strict BLE float/int bool, non-numeric type, and non-finite rejections
    for bad_ble in (
        {"ble_attenuation": True},
        {"ble_attenuation": [2.2]},
        {"ble_attenuation": float("nan")},
        {"ble_max_radius_m": float("inf")},
        {"ble_away_timeout_s": False},
        {"ble_away_timeout_s": {"s": 60}},
        {"ble_away_timeout_s": float("-inf")},
    ):
        with pytest.raises(cleaners.SettingsScopeError):
            cleaners.clean_system_settings(bad_ble)

    # _domain_entity_list non-list and single-entity wrong domain prefix
    for bad_ent in (
        {"camera_entities": "camera.front"},
        {"weather_entity": "sensor.outside_temp"},
        {"alarm_entity": "lock.front_door"},
    ):
        with pytest.raises(cleaners.SettingsScopeError):
            cleaners.clean_system_settings(bad_ent)


def test_settings_cleaners_area_device_and_announcement_edge_cases() -> None:
    """Cover Area fusion/illuminance, Device scalars/pools/prefs/traits, and announcement length guards."""
    # Area fusion bool and non-numeric threshold rejections
    for bad_pct in (True, None, [50]):
        with pytest.raises(cleaners.SettingsScopeError, match="whole percent"):
            cleaners.clean_area_fusion({}, {"threshold_pct": bad_pct}, set())

    # Area illuminance: malformed existing lux ignored, invalid update string, out-of-bounds, and min-gap clamp
    assert (
        cleaners.clean_area_illuminance(
            {"dark_lux": "corrupt", "bright_lux": "bad"}, {}, set()
        )
        == {}
    )
    for bad_lux in (
        {"dark_lux": "abc"},
        {"bright_lux": "xyz"},
        {"dark_lux": -1.0},
        {"bright_lux": 200000.0},
    ):
        with pytest.raises(cleaners.SettingsScopeError):
            cleaners.clean_area_illuminance({}, bad_lux, set())

    clamped = cleaners.clean_area_illuminance(
        {}, {"dark_lux": 10.0, "bright_lux": 10.4}, set()
    )
    assert clamped == {"dark_lux": 10.0, "bright_lux": 11.0}

    # Device string boolean coercion + _require_int bool/non-numeric rejections
    coerced = cleaners.clean_device_settings(
        {
            "area_handoff": "YES",
            "activity_card": "false",
            "screensaver_shuffle": " 1 ",
            "home_screen_enabled": "off",
        }
    )
    assert coerced == {
        "area_handoff": True,
        "activity_card": False,
        "screensaver_shuffle": True,
        "home_screen_enabled": False,
        "start_screen": "Time App",
    }
    for bad_int in (
        {"wallpaper_cycle_minutes": True},
        {"area_follow_dwell_s": None},
    ):
        with pytest.raises(cleaners.SettingsScopeError):
            cleaners.clean_device_settings(bad_int)

    # Device ble_ref_power bool, non-numeric, and non-finite rejections
    for bad_ref in (True, [-59], float("nan"), float("inf")):
        with pytest.raises(cleaners.SettingsScopeError):
            cleaners.clean_device_settings({"ble_ref_power": bad_ref})

    # Device photo pool modes & ID lists (invalid mode, non-list IDs, dedupe, and MAX_PHOTO_POOL_IDS cap)
    for bad_pool in (
        {"wallpaper_mode": "invalid_mode"},
        {"screensaver_photo_mode": ""},
        {"wallpaper_favorites": "photo_1"},
    ):
        with pytest.raises(cleaners.SettingsScopeError):
            cleaners.clean_device_settings(bad_pool)
    cleaned_pools = cleaners.clean_device_settings(
        {
            "wallpaper_mode": "CUSTOM",
            "wallpaper_favorites": ["p1", "p1", "", "p2"],
            "screensaver_photo_ids": [f"img_{i}" for i in range(cleaners.MAX_PHOTO_POOL_IDS + 5)],
        }
    )
    assert cleaned_pools["wallpaper_mode"] == "custom"
    assert cleaned_pools["wallpaper_favorites"] == ["p1", "p2"]
    assert len(cleaned_pools["screensaver_photo_ids"]) == cleaners.MAX_PHOTO_POOL_IDS

    # Generic text pref fallback, invalid select option, invalid security_pin_policy
    assert cleaners._clean_text_pref_spec("generic_text_pref", "  trimmed  ") == "trimmed"
    with pytest.raises(cleaners.SettingsScopeError, match="Unknown option for time_format"):
        cleaners.clean_device_settings({"time_format": "99-Hour"})
    with pytest.raises(cleaners.SettingsScopeError, match="Unknown security PIN policy"):
        cleaners.clean_device_settings({"security_pin_policy": "always_open"})

    # Hardware trait guards: strict raise and non-strict fallback for clock_face and camera_doorbell_popup
    with pytest.raises(cleaners.SettingsScopeError, match="Modern Analog"):
        cleaners.clean_device_settings(
            {"clock_face": "Modern Analog"},
            is_round_display=False,
            strict_traits=True,
        )
    assert cleaners.clean_device_settings(
        {"clock_face": "Modern Analog"},
        is_round_display=False,
        strict_traits=False,
    ) == {"clock_face": "Minimal Digital"}
    assert cleaners.clean_device_settings(
        {"camera_doorbell_popup": "Live Video"},
        supports_hw_jpeg=False,
        strict_traits=False,
    ) == {"camera_doorbell_popup": "Snapshot"}

    # Announcement message and title length guards
    with pytest.raises(cleaners.SettingsScopeError, match="at most 500"):
        cleaners.clean_announcement(
            {"mode": "broadcast", "target_device": "all", "message": "m" * 501},
            {"kitchen"},
        )
    with pytest.raises(cleaners.SettingsScopeError, match="at most 64"):
        cleaners.clean_announcement(
            {
                "mode": "notify",
                "target_device": "kitchen",
                "title": "t" * 65,
                "message": "Alert",
            },
            {"kitchen"},
        )


async def test_payload_locale_overlays_and_preload_paths(
    hass: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cover Studio locale overlay sync loading, executor preload, loop task fallback, and language resolution."""
    locales_dir = tmp_path / "locales"
    locales_dir.mkdir()
    (locales_dir / "en.json").write_text('{"ignored": "English"}', encoding="utf-8")
    (locales_dir / "fr.json").write_text(
        '{"hello": "Bonjour", "non_str": 42}', encoding="utf-8"
    )
    (locales_dir / "pt_BR.json").write_text('{"save": "Salvar"}', encoding="utf-8")
    (locales_dir / "bad.json").write_text("{malformed json", encoding="utf-8")
    (locales_dir / "list.json").write_text('["not_a_dict"]', encoding="utf-8")

    orig_lang = hass.config.language
    orig_cache = dict(payload_mod._LOCALE_OVERLAYS_CACHE)
    orig_loaded = payload_mod._LOCALES_LOADED
    orig_scheduled = payload_mod._LOCALES_PRELOAD_SCHEDULED
    monkeypatch.setattr(payload_mod, "__file__", str(tmp_path / "payload.py"))

    try:
        # 1. Direct sync load parses valid non-English dicts, skips en.json, malformed JSON, and non-dict JSON
        loaded = payload_mod.load_studio_locales_sync()
        assert loaded == {"fr": {"hello": "Bonjour"}, "pt-br": {"save": "Salvar"}}

        # 2. Worker-thread call (no running event loop) loads synchronously via except RuntimeError branch
        payload_mod._LOCALE_OVERLAYS_CACHE.clear()
        payload_mod._LOCALES_LOADED = False
        payload_mod._LOCALES_PRELOAD_SCHEDULED = False
        await hass.async_add_executor_job(
            payload_mod._schedule_locale_preload_if_needed, hass
        )
        assert payload_mod._LOCALES_LOADED is True
        assert payload_mod._LOCALE_OVERLAYS_CACHE["fr"] == {"hello": "Bonjour"}

        # 3. Event-loop resolve when unloaded schedules via hass.async_create_task and coalesces re-entry
        payload_mod._LOCALE_OVERLAYS_CACHE.clear()
        payload_mod._LOCALES_LOADED = False
        payload_mod._LOCALES_PRELOAD_SCHEDULED = False
        hass.config.language = "fr"
        preload_gate = asyncio.Event()
        orig_exec = hass.async_add_executor_job

        async def _gated_exec(target: Any, *args: Any) -> Any:
            await preload_gate.wait()
            return await orig_exec(target, *args)

        with monkeypatch.context() as mp_gate:
            mp_gate.setattr(hass, "async_add_executor_job", _gated_exec)
            assert payload_mod.resolve_studio_locale_strings(hass) == {}
            assert payload_mod._LOCALES_PRELOAD_SCHEDULED is True
            # Re-entry while preload is already scheduled returns early
            payload_mod._schedule_locale_preload_if_needed(hass)
            preload_gate.set()
            await hass.async_block_till_done()
        assert payload_mod._LOCALES_LOADED is True
        assert payload_mod._LOCALES_PRELOAD_SCHEDULED is False

        # 4. Exact language match, base language fallback, unknown language miss, and English short-circuit
        hass.config.language = "pt-BR"
        assert payload_mod.resolve_studio_locale_strings(hass) == {"save": "Salvar"}
        hass.config.language = "fr-CA"
        assert payload_mod.resolve_studio_locale_strings(hass) == {"hello": "Bonjour"}
        hass.config.language = "de"
        assert payload_mod.resolve_studio_locale_strings(hass) == {}
        hass.config.language = "en-US"
        assert payload_mod.resolve_studio_locale_strings(hass) == {}

        # 5. Executor preload exception handling resets _LOCALES_PRELOAD_SCHEDULED cleanly
        payload_mod._LOCALES_PRELOAD_SCHEDULED = True
        with patch.object(
            payload_mod, "load_studio_locales_sync", side_effect=RuntimeError("disk error")
        ):
            await payload_mod._async_preload_studio_locales(hass)
        assert payload_mod._LOCALES_PRELOAD_SCHEDULED is False

        # 6. Event-loop fallback when hass lacks async_create_task schedules on running_loop
        payload_mod._LOCALES_LOADED = False
        payload_mod._LOCALES_PRELOAD_SCHEDULED = False
        with patch.object(payload_mod, "hasattr", create=True, return_value=False):
            payload_mod._schedule_locale_preload_if_needed(hass)
        pending = list(payload_mod._LOCALES_PRELOAD_TASKS)
        assert len(pending) == 1
        await asyncio.gather(*pending)
        await hass.async_block_till_done()
        assert payload_mod._LOCALES_LOADED is True
        assert not payload_mod._LOCALES_PRELOAD_TASKS
    finally:
        hass.config.language = orig_lang
        payload_mod._LOCALE_OVERLAYS_CACHE.clear()
        payload_mod._LOCALE_OVERLAYS_CACHE.update(orig_cache)
        payload_mod._LOCALES_LOADED = orig_loaded
        payload_mod._LOCALES_PRELOAD_SCHEDULED = orig_scheduled


async def test_payload_combined_system_and_studio_logs(hass: Any) -> None:
    """Cover _extract_system_log_entry and get_combined_system_and_studio_logs across dict, list, and error stores."""
    payload_mod.log_studio_event(hass, "info", "studio", "Studio panel connected")

    latter_rec = MagicMock()
    latter_rec.to_dict.return_value = {
        "name": "custom_components.latter.rpc",
        "message": ["RPC push timeout"],
        "exception": "Traceback: timeout",
        "timestamp": 1700000000.0,
        "level": "error",
    }
    unrelated_rec = MagicMock()
    unrelated_rec.to_dict.return_value = {
        "name": "homeassistant.core",
        "message": ["Unrelated core message"],
        "exception": "",
        "timestamp": 1700000001.0,
        "level": "warning",
    }
    esphome_plain_rec = MagicMock()
    esphome_plain_rec.to_dict.return_value = {
        "name": "aioesphomeapi.connection",
        "message": "Disconnected from node",
        "exception": "",
        "timestamp": 0,
        "level": "WARNING",
    }

    orig_syslog = hass.data.get("system_log")
    try:
        # 1. Mapping-backed system_log.records (records.values() path)
        dict_handler = MagicMock()
        dict_handler.records = {
            "k1": latter_rec,
            "k2": unrelated_rec,
            "k3": esphome_plain_rec,
        }
        hass.data["system_log"] = dict_handler
        combined = payload_mod.get_combined_system_and_studio_logs(hass)
        sources = [entry["source"] for entry in combined]
        assert "studio" in sources
        assert "ha:custom_components.latter.rpc" in sources
        assert "ha:aioesphomeapi.connection" in sources
        assert "ha:homeassistant.core" not in sources
        rpc_entry = next(e for e in combined if e["source"] == "ha:custom_components.latter.rpc")
        assert rpc_entry["message"] == "RPC push timeout\nTraceback: timeout"
        assert rpc_entry["level"] == "ERROR"
        assert rpc_entry["ts"].startswith("2023-11-14T")
        plain_entry = next(e for e in combined if e["source"] == "ha:aioesphomeapi.connection")
        assert plain_entry["ts"] == ""

        # 2. Sequence-backed system_log.records (else list(records) path)
        list_handler = MagicMock()
        list_handler.records = [latter_rec, object()]
        hass.data["system_log"] = list_handler
        combined_list = payload_mod.get_combined_system_and_studio_logs(hass)
        assert any(e["source"] == "ha:custom_components.latter.rpc" for e in combined_list)

        # 3. Corrupt system_log handler raising on iteration is swallowed gracefully
        class _BrokenLogHandler:
            @property
            def records(self) -> Any:
                raise RuntimeError("corrupt log store")

        hass.data["system_log"] = _BrokenLogHandler()
        combined_fallback = payload_mod.get_combined_system_and_studio_logs(hass)
        assert len(combined_fallback) == 1
        assert combined_fallback[0]["source"] == "studio"
    finally:
        if orig_syslog is None:
            hass.data.pop("system_log", None)
        else:
            hass.data["system_log"] = orig_syslog


async def test_payload_device_system_catalog_online_and_edge_branches(
    hass: Any, make_esphome_device: Any
) -> None:
    """Cover Studio payload device/system/catalog/online/issue/config edge branches on real HA."""
    await prepare_latter_dependencies(hass)
    await ensure_bluetooth_manager(hass)
    ensure_area(hass, "Office", area_id="office")
    ensure_area(hass, "Kitchen", area_id="kitchen")

    # Device 1: Square display with home_screen_enabled=False, start_screen=Home, clock_face=Modern Analog,
    # and a Music Assistant counterpart configured as default_speaker
    wall_dev, wall_mac = make_esphome_device(
        hass,
        slug="wall_panel",
        mac="aa:bb:cc:dd:ee:11",
        name="Wall Panel",
        area_id="office",
        stationary=0,
        shape="square",
        with_speaker=True,
    )
    ma_entry = add_mock_entry(
        hass,
        domain="music_assistant",
        title="Music Assistant",
        entry_id="entry_ma_test",
        version=1,
    )
    register_entity(
        hass,
        "media_player.wall_panel_ma",
        platform="music_assistant",
        config_entry=ma_entry,
        original_name="Wall Panel MA",
    )
    hass.states.async_set(
        "media_player.wall_panel_ma",
        "idle",
        {"friendly_name": "Wall Panel MA"},
    )
    register_entity(
        hass,
        "sensor.wall_panel_battery_level",
        platform="esphome",
        device_id=wall_dev.id,
        original_name="Battery Level",
    )
    hass.states.async_set("sensor.wall_panel_battery_level", "not_a_number")
    register_entity(
        hass,
        "update.wall_panel_project_firmware",
        platform="esphome",
        device_id=wall_dev.id,
        original_name="Project Firmware",
    )
    hass.states.async_set(
        "update.wall_panel_project_firmware",
        "on",
        {"installed_version": "3.0.0", "latest_version": "3.0.1"},
    )

    # Device 2: Stationary display without local speaker entity, no default_area, ESPHome device in kitchen
    stat_dev, stat_mac = make_esphome_device(
        hass,
        slug="kitchen_panel",
        mac="aa:bb:cc:dd:ee:22",
        name="Kitchen Panel",
        area_id="kitchen",
        stationary=1,
        with_speaker=False,
    )

    # Device 3: Minimal ESPHome device without Wi-Fi/IP sensors for fallback online probing
    probe_mac = "aa:bb:cc:dd:ee:33"
    probe_esp_entry = add_mock_entry(
        hass,
        domain="esphome",
        title="Probe Node",
        data={"device_name": "probe_node"},
        entry_id="esp_entry_probe_node",
        version=1,
    )
    probe_dev = register_device(
        hass,
        config_entry_id=probe_esp_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, probe_mac)},
        identifiers={("esphome", probe_mac)},
        name="Probe Node",
        manufacturer="Latter",
        model="probe-board",
        sw_version="3.0.0",
        area_id="office",
    )
    register_entity(
        hass,
        "sensor.probe_node_system_rpc_outbox",
        platform="esphome",
        config_entry=probe_esp_entry,
        device_id=probe_dev.id,
        original_name="System: RPC Outbox",
        unique_id=f"{probe_mac.upper()}/0/text_sensor/System: RPC Outbox",
    )
    hass.states.async_set("sensor.probe_node_system_rpc_outbox", "")
    register_entity(
        hass,
        "button.probe_node_restart",
        platform="esphome",
        config_entry=probe_esp_entry,
        device_id=probe_dev.id,
        original_name="Restart",
    )
    hass.states.async_set("button.probe_node_restart", "unknown")
    register_entity(
        hass,
        "sensor.probe_node_temp",
        platform="esphome",
        config_entry=probe_esp_entry,
        device_id=probe_dev.id,
        original_name="Temp",
    )
    hass.states.async_set("sensor.probe_node_temp", STATE_UNAVAILABLE)
    register_entity(
        hass,
        "binary_sensor.probe_node_status",
        platform="esphome",
        config_entry=probe_esp_entry,
        device_id=probe_dev.id,
        original_name="Status",
        original_device_class="connectivity",
    )
    hass.states.async_set(
        "binary_sensor.probe_node_status", "off", {"device_class": "connectivity"}
    )

    # Seed remote & calendar states for catalog buckets
    hass.states.async_set("remote.den_tv", "on", {"friendly_name": "Den TV Remote"})
    hass.states.async_set("calendar.main", "off", {"friendly_name": "Main Calendar"})

    entry = add_mock_entry(
        hass,
        entry_id="entry_latter_cov",
        domain=DOMAIN,
        title="Latter",
        data={},
        unique_id=DOMAIN,
        subentries_data=[
            make_subentry_dict(
                {
                    CONF_ESPHOME_DEVICE_ID: wall_dev.id,
                    "mac": wall_mac,
                    CONF_DEVICE_SLUG: "wall_panel",
                    CONF_DEFAULT_AREA: "office",
                    CONF_MA_PLAYER_ENTITY: "media_player.wall_panel_ma",
                    CONF_DEFAULT_SPEAKER: "media_player.wall_panel_ma",
                    CONF_NATIVE_BLE_TRACKING: True,
                    "home_screen_enabled": False,
                    "start_screen": "Home",
                    "clock_face": "Modern Analog",
                },
                subentry_type=SUBENTRY_DEVICE,
                title="Wall Panel",
                unique_id=wall_mac,
                subentry_id="sub_square",
            ),
            make_subentry_dict(
                {
                    CONF_ESPHOME_DEVICE_ID: stat_dev.id,
                    "mac": stat_mac,
                    CONF_DEVICE_SLUG: "kitchen_panel",
                    CONF_DEFAULT_AREA: "",
                    CONF_NATIVE_BLE_TRACKING: False,
                },
                subentry_type=SUBENTRY_DEVICE,
                title="Kitchen Panel",
                unique_id=stat_mac,
                subentry_id="sub_stationary",
            ),
            make_subentry_dict(
                {
                    CONF_ESPHOME_DEVICE_ID: probe_dev.id,
                    "mac": probe_mac,
                    CONF_DEVICE_SLUG: "probe_node",
                    CONF_DEFAULT_AREA: "office",
                    CONF_NATIVE_BLE_TRACKING: False,
                },
                subentry_type=SUBENTRY_DEVICE,
                title="Probe Node",
                unique_id=probe_mac,
                subentry_id="sub_probe",
            ),
        ],
    )
    await seed_device_hello_manifest(hass, "sub_square", get_test_manifest(hass, wall_dev.id))
    await seed_device_hello_manifest(hass, "sub_stationary", get_test_manifest(hass, stat_dev.id))
    assert await hass.config_entries.async_setup(entry.entry_id) is True
    await hass.async_block_till_done()
    await flush_debouncers(hass)

    sys_obj = entry.runtime_data
    wall_coord = sys_obj.coordinators["sub_square"]
    stat_coord = sys_obj.coordinators["sub_stationary"]
    probe_coord = sys_obj.coordinators["sub_probe"]

    # 1. Online fallback checks on probe_coord: skip button/unavailable, connectivity off -> False, on -> True,
    #    then unavailable Wi-Fi sensor -> False on early conn-sensor return
    assert payload_mod.is_coordinator_online_for_studio(hass, probe_coord) is False
    hass.states.async_set(
        "binary_sensor.probe_node_status", "on", {"device_class": "connectivity"}
    )
    assert payload_mod.is_coordinator_online_for_studio(hass, probe_coord) is True
    register_entity(
        hass,
        "sensor.probe_node_wi_fi_signal",
        platform="esphome",
        config_entry=probe_esp_entry,
        device_id=probe_dev.id,
        original_name="Wi-Fi Signal",
    )
    hass.states.async_set("sensor.probe_node_wi_fi_signal", STATE_UNAVAILABLE)
    assert payload_mod.is_coordinator_online_for_studio(hass, probe_coord) is False

    # 2. Repair issue filtering (non-Latter issue skipped, active Latter issue returned)
    ir.async_create_issue(
        hass,
        "other_domain",
        "unrelated_1",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="unrelated",
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"device_crashed_{wall_coord.subentry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="device_crashed",
        translation_placeholders={"reason": "watchdog"},
    )

    # 3. Volume overrides extraction (both list-of-dicts and legacy dict mapping)
    global_cfg = get_global_config(hass)
    global_cfg["volume_overrides"] = [
        {"speaker": "media_player.wall_panel_music", "target": "number.avr_vol"},
        {"speaker": "", "target": "number.ignored"},
        "invalid_entry",
    ]
    assert payload_mod._extract_volume_overrides_map(hass) == {
        "media_player.wall_panel_music": "number.avr_vol"
    }
    global_cfg["volume_overrides"] = {
        "media_player.wall_panel_music": "number.avr_vol",
        "": "number.skip",
    }
    assert payload_mod._extract_volume_overrides_map(hass) == {
        "media_player.wall_panel_music": "number.avr_vol"
    }

    # 4. Screensaver active quick action, square pref coercions, MA default_speaker canonicalization,
    #    malformed battery sensor int, project_firmware update check, and catalog remotes/calendars
    wall_coord.display_power_state = 1
    get_domain_data(hass).ma_counterpart_cache.clear()
    assert wall_coord.local_speaker == "media_player.wall_panel_music"
    assert wall_coord.local_ma_speaker == "media_player.wall_panel_ma"
    assert wall_coord.is_round_display is False

    wall_payload = payload_mod.build_studio_state_payload(hass, wall_coord, include_catalog=True)
    assert wall_payload["config"]["default_speaker"] == "media_player.wall_panel_music"
    assert wall_payload["config"]["start_screen"] == "Time App"

    prefs_by_key = {p["key"]: p for p in wall_payload["device_prefs"]}
    assert prefs_by_key["start_screen"]["value"] == "Time App"
    assert prefs_by_key["clock_face"]["value"] == "Minimal Digital"
    assert "Modern Analog" not in prefs_by_key["clock_face"]["options"]

    clock_shared = next(
        c for c in wall_payload["system_controls"] if c["pref_key"] == "clock_face"
    )
    wall_shared_target = next(
        t for t in clock_shared["targets"] if t["device_slug"] == "wall_panel"
    )
    assert wall_shared_target["state"] == "Minimal Digital"

    action_keys = [a["key"] for a in wall_payload["quick_actions"]]
    assert "deactivate_screensaver" in action_keys

    wall_sys_row = next(
        d for d in wall_payload["system_devices"] if d["subentry_id"] == "sub_square"
    )
    assert wall_sys_row["battery_level"] is None
    assert wall_sys_row["status_code"] == "update"

    issue_ids = [i["issue_id"] for i in wall_payload["issues"]]
    assert f"device_crashed_{wall_coord.subentry_id}" in issue_ids
    assert "unrelated_1" not in issue_ids

    assert any(r["id"] == "remote.den_tv" for r in wall_payload["catalog"]["remotes"])
    assert any(c["id"] == "calendar.main" for c in wall_payload["catalog"]["calendars"])

    # 5. Primary firmware update fallback when only a C6 co-processor update exists
    assert (
        payload_mod._select_primary_fw_update_entity(
            [{"entity_id": "update.p4_c6_co_processor_firmware"}]
        )
        == "update.p4_c6_co_processor_firmware"
    )

    # 6. Shortcut entity deduplication guard when AreaStateIndex yields a duplicate state
    hass.states.async_set("light.office_lamp", "on", {"friendly_name": "Office Lamp"})
    idx = get_area_state_index(hass)
    dup_state = hass.states.get("light.office_lamp")
    assert dup_state is not None
    orig_states_for_domain = idx.states_for_domain

    def _dup_states_for_domain(domain: str) -> list[Any]:
        if domain == "light":
            return [dup_state, dup_state]
        return list(orig_states_for_domain(domain))

    with patch.object(idx, "states_for_domain", side_effect=_dup_states_for_domain):
        shortcuts = payload_mod._build_shortcut_entities_catalog(idx, {"office": "Office"})
    assert sum(1 for item in shortcuts if item["id"] == "light.office_lamp") == 1

    # 7. Stationary device without local speaker (speaker_volume=None) + ESPHome device area inheritance
    # Live two-way Area sync keeps `CONF_DEFAULT_AREA` and `DeviceEntry.area_id` aligned, so verify
    # `_build_device_config_data`'s Device Registry fallback (`payload.py:1934`) when a subentry has no
    # stored `default_area` yet while its bound ESPHome device has `area_id="kitchen"`.
    dr.async_get(hass).async_update_device(stat_dev.id, area_id="kitchen")
    esp_after = dr.async_get(hass).async_get(stat_coord.esphome_device_id)
    assert esp_after is not None and esp_after.area_id == "kitchen"
    orig_stat_get_opt = stat_coord.get_opt
    with patch.object(
        stat_coord,
        "get_opt",
        side_effect=lambda k, d=None: "" if k == CONF_DEFAULT_AREA else orig_stat_get_opt(k, d),
    ):
        stat_payload = payload_mod.build_studio_state_payload(
            hass, stat_coord, include_catalog=False
        )
    assert stat_payload["speaker_volume"] is None
    assert stat_payload["config"]["default_area"] == "kitchen"

    # 8. Clear ESPHome device area on stationary device -> unassigned area tuple ("", "", False)
    dr.async_get(hass).async_update_device(stat_dev.id, area_id=None)
    await hass.async_block_till_done()
    sys_after_clear = payload_mod.build_system_section(hass, "sub_stationary")
    stat_row = next(
        d for d in sys_after_clear["system_devices"] if d["subentry_id"] == "sub_stationary"
    )
    assert stat_row["area_id"] == ""
    assert stat_row["area_label"] == ""
    assert stat_row["has_assigned_area"] is False

    assert await hass.config_entries.async_unload(entry.entry_id) is True
