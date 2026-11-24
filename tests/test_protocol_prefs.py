"""Unit tests for device reset policy, Protocol v3 `device_prefs` packing/dirty_prefs, and Universal Shortcut Engine."""

from __future__ import annotations

import ast
import json
from types import SimpleNamespace
from typing import Any, ClassVar
import unittest

from custom_components.latter import protocol_codec, protocol_policy, protocol_specs
from custom_components.latter.groups import device_groups as reset_policy
from custom_components.latter.studio import settings_cleaners as studio_scope
from tests.conftest import LATTER_DIR

HA_PROTO_JSON = LATTER_DIR / "protocol_v3.json"
DomainPayloadPacker = protocol_codec.DomainPayloadPacker
_PAYLOADS_MOD = SimpleNamespace(
    **(vars(protocol_specs) | vars(protocol_codec) | vars(protocol_policy))
)


def _const_conf_values() -> set[str]:
    """Return every CONF_* string value defined in const.py."""
    values: set[str] = set()
    for node in ast.parse((LATTER_DIR / "const.py").read_text(encoding="utf-8")).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(getattr(node, "value", None), ast.Constant):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id.startswith("CONF_") for t in targets):
                values.add(str(node.value.value))
    return values


class TestResetPolicy(unittest.TestCase):
    """Reset to defaults: keep/reset decision and flag validation, exercised through `reset_policy.py`."""

    CURRENT: ClassVar[dict[str, Any]] = {
        "esphome_device_id": "dev123",
        "mac": "aa:bb:cc:dd:ee:ff",
        "device_slug": "desk_assistant",
        "ma_player_entity": "media_player.desk_assistant",
        "dock_items": [{"kind": "route", "target": "app:music", "action": "", "label": "", "icon": "", "confirm": False}],
        "pinned_items": [{"kind": "entity", "target": "script.baby_help", "action": "turn_on", "label": "Baby Help", "icon": "mdi:baby-face-outline", "confirm": False}],
        "wallpaper_source": "upload:desk/beach.jpg",
        "wallpaper_favorites": ["a", "b"],
        "device_custom_color": "#FF0000",
        "default_area": "kitchen",
        "native_ble_tracking": True,
        "custom_palettes": [{"name": "x", "hex": "#000000"}],
    }
    DEFAULTS: ClassVar[dict[str, Any]] = {
        "device_group": "wall_panels",
        "area_categories": "scene,light,cover,fan,switch,climate,media",
        "native_ble_tracking": False,
        "ble_auto_switch": False,
        "sync_device_area": False,
        "area_handoff": False,
        "default_area": "office",
        "dock_items": studio_scope.default_dock_items(),
        "pinned_items": [],
        "default_speaker": "media_player.desk_assistant_music",
        "esphome_device_id": "must_not_win",
    }

    def test_device_reset_keeps_identity_and_link_and_restores_defaults(self) -> None:
        out = reset_policy.reset_subentry_data(
            self.CURRENT, self.DEFAULTS, reset_policy.DEVICE_IDENTITY_KEYS
        )
        for key in ("esphome_device_id", "mac", "device_slug", "ma_player_entity"):
            self.assertEqual(out[key], self.CURRENT[key], key)
        self.assertEqual(out["dock_items"], self.DEFAULTS["dock_items"])
        self.assertEqual(out["pinned_items"], [])
        self.assertEqual(out["default_area"], "office")
        self.assertFalse(out["native_ble_tracking"])
        for dropped in ("wallpaper_source", "wallpaper_favorites", "device_custom_color", "custom_palettes"):
            self.assertNotIn(dropped, out)

    def test_ble_tag_reset_keeps_name_and_address(self) -> None:
        current = {"device_slug": "alexs_phone", "ble_target_address": "AA:BB:CC:DD:EE:FF", "assigned_person": "person.alex"}
        defaults = {"device_slug": "x", "ble_target_address": "y", "assigned_person": "", "native_ble_tracking": True}
        out = reset_policy.reset_subentry_data(current, defaults, reset_policy.BLE_TAG_IDENTITY_KEYS)
        self.assertEqual(out["device_slug"], "alexs_phone")
        self.assertEqual(out["ble_target_address"], "AA:BB:CC:DD:EE:FF")
        self.assertEqual(out["assigned_person"], "")
        self.assertTrue(out["native_ble_tracking"])

    def test_missing_identity_keys_are_not_invented(self) -> None:
        out = reset_policy.reset_subentry_data({"device_slug": "x"}, {}, reset_policy.DEVICE_IDENTITY_KEYS)
        self.assertEqual(out, {"device_slug": "x"})

    def test_flag_validation(self) -> None:
        err = reset_policy.reset_flags_error
        self.assertIsNone(err(True, True, is_ble_tag=False))
        self.assertIsNone(err(True, False, is_ble_tag=False))
        self.assertIsNone(err(False, True, is_ble_tag=False))
        self.assertIsNone(err(False, True, is_ble_tag=True))
        self.assertEqual(err(False, False, is_ble_tag=False), "reset_nothing_selected")
        self.assertEqual(err(False, False, is_ble_tag=True), "reset_nothing_selected")
        self.assertEqual(err(True, True, is_ble_tag=True), "reset_ble_tag_has_no_device_settings")

    def test_field_lists_name_real_subentry_keys(self) -> None:
        """Every enumerated key is a real config key (const.py CONF_* value), and identity lists only share device_slug."""
        conf_values = _const_conf_values() | {"mac"}
        keys = reset_policy.DEVICE_IDENTITY_KEYS + reset_policy.BLE_TAG_IDENTITY_KEYS
        self.assertFalse(set(keys) - conf_values, sorted(set(keys) - conf_values))
        self.assertEqual(set(reset_policy.DEVICE_IDENTITY_KEYS) & set(reset_policy.BLE_TAG_IDENTITY_KEYS), {"device_slug"})

    def test_reset_error_keys_are_translated(self) -> None:
        strings = json.loads((LATTER_DIR / "strings.json").read_text(encoding="utf-8"))
        for key in ("reset_nothing_selected", "reset_ble_tag_has_no_device_settings", "factory_reset_unsupported", "factory_reset_failed"):
            self.assertIn(key, strings["exceptions"], key)


class TestDevicePrefsProtocol(unittest.TestCase):
    """Protocol v3 `device_prefs` packing, offline `dirty_prefs` parsing, and `PowerProfile` cascade."""

    def test_pack_device_prefs_matches_schema_field_count_and_ble_consolidation(self) -> None:
        schema = json.loads(HA_PROTO_JSON.read_text(encoding="utf-8"))
        spec_fields = schema["domains"]["device_prefs"]["fields"]
        fields = _PAYLOADS_MOD.pack_device_prefs_fields(
            9,
            {
                "power_profile": "Handheld Roaming",
                "clock_face": "Modern Analog",
                "alert_volume": 75,
            },
            native_ble_tracking=True,
            custom_color_hex="#112233",
            is_round_display=False,
        )
        self.assertEqual(len(fields), len(spec_fields))
        self.assertEqual(fields[0], 9)
        idx_by_name = {f["name"]: i for i, f in enumerate(spec_fields)}
        # Rectangular display clamps "Modern Analog" to "Minimal Digital"
        self.assertEqual(fields[idx_by_name["clock_face"]], "Minimal Digital")
        self.assertIs(fields[idx_by_name["ble_beacon_enabled"]], True)
        self.assertEqual(fields[idx_by_name["theme_color_hex"]], "#112233")
        self.assertEqual(fields[idx_by_name["alert_volume"]], 75)

        round_fields = _PAYLOADS_MOD.pack_device_prefs_fields(
            9,
            {"clock_face": "Modern Analog"},
            native_ble_tracking=True,
            custom_color_hex="#112233",
            is_round_display=True,
        )
        self.assertEqual(round_fields[idx_by_name["clock_face"]], "Modern Analog")

        packer = _PAYLOADS_MOD.DomainPayloadPacker()
        _rev, wire = packer.pack("device_prefs", *fields)
        wire_parts = wire.split("\x1f")
        self.assertEqual(len(wire_parts), 3 + len(spec_fields))
        self.assertEqual(wire_parts[3 + idx_by_name["ble_beacon_enabled"]], "1")
        self.assertEqual(wire_parts[3 + idx_by_name["clock_face"]], "Minimal Digital")

    def test_parse_dirty_prefs_records_validates_and_maps_ble_beacon(self) -> None:
        raw = "\x1e".join(
            [
                "alert_volume=65",
                "ble_beacon_enabled=0",
                "screensaver_mode=Always",
                "screensaver_photo_clock=1",
                "weather_app_background=0",
                "color_profile=NotARealProfile",
                "clock_face=Hybrid Digital",
                "home_clock_tap_action=Clock Face",
                "local_clock_label=  Harbor Studio  ",
                "show_utc_clock=1",
                "do_not_disturb=1",
                "world_clocks=London|Europe/London;Kyoto|Asia/Tokyo",
                "alarms_summary=06:47|1|1;08:30|0|2;09:15|1|3",
                "tools_items=dice,flashlight,dice",
                "games_items=blocks,chomp",
                "invalid_empty_tools=",
            ]
        )
        parsed = _PAYLOADS_MOD.parse_dirty_prefs_records(raw)
        self.assertEqual(
            parsed,
            {
                "alert_volume": 65,
                "native_ble_tracking": False,
                "screensaver_mode": "Always",
                "screensaver_photo_clock": True,
                "weather_app_background": False,
                "clock_face": "Hybrid Digital",
                "home_clock_tap_action": "Clock Face",
                "local_clock_label": "Harbor Studio",
                "show_utc_clock": True,
                "do_not_disturb": True,
                "world_clocks": "London|Europe/London;Kyoto|Asia/Tokyo",
                "alarms_summary": "06:47|1|1;08:30|0|2;09:15|1|3",
                "tools_items": "dice,flashlight",
                "games_items": "blocks,chomp",
            },
        )
        bad_raw = "\x1e".join(["tools_items=", "games_items=not_a_game"])
        self.assertEqual(_PAYLOADS_MOD.parse_dirty_prefs_records(bad_raw), {})

    def test_power_profile_retired_and_activity_sources_in_scope(self) -> None:
        for retired_key in (
            "power_profile",
            "show_speaker_shortcut",
            "show_library_shortcut",
            "docked_screensaver",
            "hold_crown_power_off",
        ):
            self.assertNotIn(retired_key, studio_scope.DEVICE_PREF_KEYS)
            self.assertNotIn(retired_key, studio_scope.DEVICE_SETTING_KEYS)
            with self.assertRaises(studio_scope.SettingsScopeError):
                studio_scope.clean_device_settings({retired_key: "1"})
        self.assertEqual(len(studio_scope.DEVICE_PREF_SPECS), 70)
        self.assertEqual(
            studio_scope.DEVICE_PREF_SPEC_MAP["home_clock_tap_action"].options,
            ("Time App", "Clock Face", "None"),
        )
        self.assertEqual(
            studio_scope.DEVICE_PREF_SPEC_MAP["home_date_tap_action"].options,
            ("Day View", "Overview", "None"),
        )
        wt_spec = studio_scope.DEVICE_PREF_SPEC_MAP["home_weather_tap_action"]
        self.assertEqual(
            (wt_spec.domain, wt_spec.section, wt_spec.group_tier, wt_spec.default, wt_spec.options),
            ("select", "interface", "interface", "Current Weather", ("Current Weather", "5-Day Forecast", "None")),
        )
        batt_spec = studio_scope.DEVICE_PREF_SPEC_MAP["home_show_battery"]
        self.assertEqual(
            (batt_spec.domain, batt_spec.section, batt_spec.group_tier, batt_spec.default, batt_spec.capability),
            ("switch", "interface", "interface", True, "display_battery"),
        )
        for show_key in ("home_show_date", "home_show_time", "home_show_weather"):
            sp = studio_scope.DEVICE_PREF_SPEC_MAP[show_key]
            self.assertEqual((sp.domain, sp.section, sp.group_tier, sp.default, sp.capability),
                             ("switch", "interface", "interface", True, "display"))
        dnd_spec = studio_scope.DEVICE_PREF_SPEC_MAP["do_not_disturb"]
        self.assertEqual(
            (dnd_spec.domain, dnd_spec.section, dnd_spec.group_tier, dnd_spec.capability),
            ("switch", "power", None, "display_or_audio"),
        )
        glass_spec = studio_scope.DEVICE_PREF_SPEC_MAP["glass_style"]
        self.assertEqual(
            (glass_spec.domain, glass_spec.section, glass_spec.group_tier, glass_spec.default, glass_spec.options),
            ("select", "display", "display", "Auto", ("Auto", "Clear", "Dark")),
        )
        mao_spec = studio_scope.DEVICE_PREF_SPEC_MAP["music_auto_open"]
        self.assertEqual(
            (mao_spec.domain, mao_spec.section, mao_spec.group_tier, mao_spec.default),
            ("select", "interface", "interface", "Now Playing"),
        )
        raw_schema = json.loads(HA_PROTO_JSON.read_text(encoding="utf-8"))
        self.assertTrue(all("esphome_section" not in s for s in raw_schema["device_pref_specs"]))
        self.assertEqual(studio_scope.MAX_DOCK_ITEMS, 24)

        for key, default_val in (
            ("manual_brightness", 80),
            ("day_brightness", 90),
            ("night_brightness", 35),
            ("bedtime_brightness", 15),
        ):
            spec = studio_scope.DEVICE_PREF_SPEC_MAP[key]
            self.assertEqual(spec.domain, "number")
            self.assertEqual(spec.default, default_val)
            self.assertEqual(spec.min_val, 1)
            self.assertEqual(spec.max_val, 100)
            self.assertEqual(spec.step, 1)
            self.assertEqual(spec.unit, "%")

        cleaned_bri = studio_scope.clean_device_settings(
            {
                "manual_brightness": 42,
                "day_brightness": 100,
                "night_brightness": 1,
                "bedtime_brightness": 12,
            }
        )
        self.assertEqual(cleaned_bri["manual_brightness"], 42)
        self.assertEqual(cleaned_bri["day_brightness"], 100)
        self.assertEqual(cleaned_bri["night_brightness"], 1)
        self.assertEqual(cleaned_bri["bedtime_brightness"], 12)
        parsed_bri = _PAYLOADS_MOD.parse_dirty_prefs_records(
            "\x1e".join(["manual_brightness=55", "bedtime_brightness=8"])
        )
        self.assertEqual(parsed_bri, {"manual_brightness": 55, "bedtime_brightness": 8})

        cleaned = studio_scope.clean_device_settings(
            {
                "tap_to_wake": "Double Tap",
                "wallpaper_source": "preset:aurora",
                "activity_sources": ["timers", "calendar"],
                "home_date_tap_action": "Overview",
                "calendar_lookahead_days": 14,
                "calendar_week_start": "Monday",
            }
        )
        self.assertEqual(cleaned["tap_to_wake"], "Double Tap")
        self.assertEqual(cleaned["wallpaper_source"], "preset:aurora")
        self.assertEqual(cleaned["activity_sources"], "calendar,timers")
        self.assertEqual(cleaned["home_date_tap_action"], "Overview")
        self.assertEqual(cleaned["calendar_lookahead_days"], 14)
        self.assertEqual(cleaned["calendar_week_start"], "Monday")

        # Calendar sources, locations, and structured window chunk packing
        srcs = _PAYLOADS_MOD.calendar_sources_records(
            [
                {"entity_id": "calendar.family", "label": "Family | Shared", "color_idx": 0, "can_create": True, "can_delete": True},
                {"entity_id": "calendar.holidays", "label": "Holidays", "color_idx": 3, "can_create": False, "can_delete": False},
            ]
        )
        self.assertEqual(len(srcs), 2)
        self.assertEqual(srcs[0], ("calendar.family", "Family \\p Shared", "0", "1", "1"))
        self.assertEqual(srcs[1], ("calendar.holidays", "Holidays", "3", "0", "0"))

        locs = _PAYLOADS_MOD.calendar_locations_records(["Home", "Downtown HQ", "home", "", "  Gym  "])
        self.assertEqual(list(locs), [("Home",), ("Downtown HQ",), ("Gym",)])

        win_events = [
            {
                "start_ymd": "2026-11-17",
                "end_ymd": "2026-11-17",
                "start_min": 540 + i,
                "end_min": 600 + i,
                "all_day": False,
                "cal_idx": i % 2,
                "uid": f"uid_{i}",
                "recurrence_id": "",
                "summary": f"Sync | #{i}",
                "location": "Lab",
                "description": "Notes",
            }
            for i in range(15)
        ]
        chunks = _PAYLOADS_MOD.pack_calendar_window_chunks(
            win_events, "2026-10-15", "2027-01-20", req_id=9, chunk_size=12
        )
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["chunk_index"], 0)
        self.assertEqual(chunks[0]["chunk_count"], 2)
        self.assertNotIn("map_url", chunks[0])
        self.assertIn("Sync | #0", chunks[0]["events"])
        self.assertEqual(chunks[1]["chunk_index"], 1)
        self.assertEqual(len(chunks[1]["events"].split("\x1e")), 3)

    def test_area_categories_parse_and_normalize(self) -> None:
        self.assertEqual(_PAYLOADS_MOD.parse_area_categories(None), [])
        self.assertEqual(
            _PAYLOADS_MOD.parse_area_categories(_PAYLOADS_MOD.DEFAULT_AREA_CATEGORIES),
            ["scene", "light", "cover", "fan", "switch", "climate", "media"],
        )
        self.assertEqual(
            _PAYLOADS_MOD.parse_area_categories("media, light, bogus, media, all"),
            ["media", "light", "all"],
        )
        self.assertEqual(
            _PAYLOADS_MOD.normalize_area_categories(" Media , light , media , ALL "),
            "media,light,all",
        )
        for bad in ("", "   ", "bogus", "light,bogus"):
            with self.assertRaises(ValueError):
                _PAYLOADS_MOD.normalize_area_categories(bad)

    def test_home_categories_and_single_app_start_screen_coercion(self) -> None:
        self.assertEqual(_PAYLOADS_MOD.parse_home_categories(None), [])
        self.assertEqual(
            _PAYLOADS_MOD.parse_home_categories(_PAYLOADS_MOD.DEFAULT_HOME_CATEGORIES),
            ["alarm", "intercom", "thermostat", "entry", "vacuum"],
        )
        self.assertEqual(
            _PAYLOADS_MOD.parse_home_categories("entry, alarm, bogus, entry"),
            ["entry", "alarm"],
        )
        self.assertEqual(
            _PAYLOADS_MOD.normalize_home_categories(" Entry , alarm , entry "),
            "entry,alarm",
        )
        for bad in ("", "   ", "bogus", "entry,bogus"):
            with self.assertRaises(ValueError):
                _PAYLOADS_MOD.normalize_home_categories(bad)

        # Tools & Games CSV catalogs, parsers, normalizers, and Studio scope validation
        self.assertEqual(_PAYLOADS_MOD.parse_tools_items(None), [])
        self.assertEqual(
            _PAYLOADS_MOD.parse_tools_items(_PAYLOADS_MOD.DEFAULT_TOOLS_ITEMS),
            ["stopwatch", "level", "flashlight", "calculator", "dice", "coin_flip"],
        )
        self.assertEqual(
            _PAYLOADS_MOD.normalize_tools_items(" Dice , flashlight , dice , COIN_FLIP "),
            "dice,flashlight,coin_flip",
        )
        with self.assertRaisesRegex(ValueError, "Keep at least one Tool enabled"):
            _PAYLOADS_MOD.normalize_tools_items("  ,  ")
        with self.assertRaisesRegex(ValueError, "Unknown Tool: calendar"):
            _PAYLOADS_MOD.normalize_tools_items("flashlight,calendar")

        self.assertEqual(_PAYLOADS_MOD.parse_games_items(None), [])
        self.assertEqual(
            _PAYLOADS_MOD.parse_games_items(_PAYLOADS_MOD.DEFAULT_GAMES_ITEMS),
            ["blocks", "snake", "drop_four", "marbles", "archery", "bricks", "chomp"],
        )
        self.assertEqual(
            _PAYLOADS_MOD.normalize_games_items(" blocks , chomp , blocks , DROP_FOUR "),
            "blocks,chomp,drop_four",
        )
        with self.assertRaisesRegex(ValueError, "Keep at least one Game enabled"):
            _PAYLOADS_MOD.normalize_games_items("")
        with self.assertRaisesRegex(ValueError, "Unknown Game: tetris"):
            _PAYLOADS_MOD.normalize_games_items("blocks,tetris")
        with self.assertRaisesRegex(ValueError, "Unknown Game: 2048"):
            _PAYLOADS_MOD.normalize_games_items("2048")
        with self.assertRaisesRegex(ValueError, "Unknown Game: memory"):
            _PAYLOADS_MOD.normalize_games_items("memory")

        cleaned_tg = studio_scope.clean_device_settings(
            {"tools_items": " dice , calculator ", "games_items": ["drop_four", "blocks"]}
        )
        self.assertEqual(cleaned_tg["tools_items"], "dice,calculator")
        self.assertEqual(cleaned_tg["games_items"], "drop_four,blocks")
        with self.assertRaisesRegex(studio_scope.SettingsScopeError, "Keep at least one Tool enabled"):
            studio_scope.clean_device_settings({"tools_items": ""})
        with self.assertRaisesRegex(studio_scope.SettingsScopeError, "Keep at least one Game enabled"):
            studio_scope.clean_device_settings({"games_items": ""})

        coerced = studio_scope.clean_device_settings({"home_screen_enabled": False})
        self.assertFalse(coerced["home_screen_enabled"])
        self.assertEqual(coerced["start_screen"], "Time App")

        kept = studio_scope.clean_device_settings(
            {"home_screen_enabled": False, "start_screen": "Area Controls", "return_to_home_timeout": "5 min"}
        )
        self.assertEqual(kept["start_screen"], "Area Controls")
        self.assertEqual(kept["return_to_home_timeout"], "5 min")

        schema = json.loads(HA_PROTO_JSON.read_text(encoding="utf-8"))
        spec_fields = schema["domains"]["device_prefs"]["fields"]
        idx_by_name = {f["name"]: i for i, f in enumerate(spec_fields)}
        packed = _PAYLOADS_MOD.pack_device_prefs_fields(
            1,
            {"home_screen_enabled": False, "start_screen": "Home", "return_to_home_timeout": "1 min"},
            native_ble_tracking=False,
            custom_color_hex="",
        )
        self.assertIs(packed[idx_by_name["home_screen_enabled"]], False)
        self.assertEqual(packed[idx_by_name["start_screen"]], "Time App")
        self.assertEqual(packed[idx_by_name["return_to_home_timeout"]], "1 min")
        self.assertEqual(packed[idx_by_name["tools_items"]], _PAYLOADS_MOD.DEFAULT_TOOLS_ITEMS)
        self.assertEqual(packed[idx_by_name["games_items"]], _PAYLOADS_MOD.DEFAULT_GAMES_ITEMS)

    def test_time_app_world_clocks_alarms_and_tz_payloads(self) -> None:
        from datetime import UTC, datetime

        self.assertEqual(
            studio_scope.sanitize_clock_label("  San  Francisco | Bay ; Home  "),
            "San Francisco Bay Home",
        )
        self.assertEqual(
            studio_scope.sanitize_clock_label("1234567890123456789012345678901é"),
            "1234567890123456789012345678901",
        )
        cleaned_lbl = studio_scope.clean_device_settings({"local_clock_label": "  Harbor | Studio  "})
        self.assertEqual(cleaned_lbl["local_clock_label"], "Harbor Studio")

        self.assertEqual(
            studio_scope.normalize_world_clocks_spec(
                " Akron |America/New_York ; Kyoto|Asia/Tokyo ; akron|America/New_York ; "
                "Hanoi|Asia/Bangkok ; Bangkok|Asia/Bangkok ",
                strict=True,
            ),
            "Akron|America/New_York;Kyoto|Asia/Tokyo;Hanoi|Asia/Bangkok;Bangkok|Asia/Bangkok",
        )
        self.assertEqual(
            studio_scope.normalize_world_clocks_spec(
                "Baker Island|Etc/GMT+12;Kiritimati|Pacific/Kiritimati",
                strict=True,
            ),
            "Baker Island|Etc/GMT+12;Kiritimati|Pacific/Kiritimati",
        )
        self.assertEqual(studio_scope.normalize_world_clocks_spec("", strict=True), "")
        for bad_wc in (
            " |America/New_York",
            "|Europe/London",
            "UTC|UTC",
            "London|Etc/UTC",
            "London|Etc/GMT+0",
            "Europe/London",
            "City|Not/AZone",
            "London|Europe/London;Tokyo|Asia/Tokyo;Kolkata|Asia/Kolkata;Sydney|Australia/Sydney;NYC|America/New_York",
        ):
            with self.assertRaises(ValueError):
                studio_scope.normalize_world_clocks_spec(bad_wc, strict=True)
            with self.assertRaises(studio_scope.SettingsScopeError):
                studio_scope.clean_device_settings({"world_clocks": bad_wc})

        self.assertEqual(
            studio_scope.normalize_alarms_summary("6:07|1|0;08:30|0|2;23:59|1|3", strict=True),
            "06:07|1|0;08:30|0|2;23:59|1|3",
        )
        for bad_alarms in ("", "07:00|1|0", "25:00|1|0;08:30|0|2;09:00|0|2", "07:60|1|0;08:30|0|2;09:00|0|2", "07:00|1|9;08:30|0|2;09:00|0|2"):
            with self.assertRaises(ValueError):
                studio_scope.normalize_alarms_summary(bad_alarms, strict=True)
            with self.assertRaises(studio_scope.SettingsScopeError):
                studio_scope.clean_device_settings({"alarms_summary": bad_alarms})

        summer_utc = datetime(2026, 7, 15, 18, 0, 0, tzinfo=UTC)
        local_summer, wc_summer = _PAYLOADS_MOD.build_time_zone_payloads(
            "America/Los_Angeles",
            "Westminster|Europe/London;Bengaluru|Asia/Kolkata;Hanoi|Asia/Bangkok;Bangkok|Asia/Bangkok;UTC|UTC",
            now_utc=summer_utc,
        )
        self.assertEqual(local_summer, "America/Los_Angeles|Los Angeles|PDT|-420|1")
        self.assertEqual(
            wc_summer,
            ";".join(
                [
                    "Europe/London|Westminster|BST|60|1",
                    "Asia/Kolkata|Bengaluru|IST|330|0",
                    "Asia/Bangkok|Hanoi|ICT|420|0",
                    "Asia/Bangkok|Bangkok|ICT|420|0",
                ]
            ),
        )

        winter_utc = datetime(2026, 1, 15, 18, 0, 0, tzinfo=UTC)
        local_winter, wc_winter = _PAYLOADS_MOD.build_time_zone_payloads(
            "America/Los_Angeles",
            "|Australia/Sydney",
            now_utc=winter_utc,
        )
        self.assertEqual(local_winter, "America/Los_Angeles|Los Angeles|PST|-480|0")
        self.assertEqual(wc_winter, "Australia/Sydney|Sydney|AEDT|660|1")


class TestShortcutsProtocolAndPolicy(unittest.TestCase):
    """Universal Shortcut Engine: normalization, confirm defaults, explicit security verbs, live state, and multi-chunk packing."""

    def test_shortcut_item_normalization_and_confirm_defaults(self) -> None:
        # Badge style & accent catalogs stay in 1:1 parity with protocol_v3.json
        spec = json.loads(HA_PROTO_JSON.read_text(encoding="utf-8"))
        self.assertEqual(
            protocol_specs.SHORTCUT_BADGE_STYLE_TOKENS,
            tuple(item["token"] for item in spec["catalogs"]["shortcut_badge_styles"]),
        )
        self.assertEqual(
            protocol_specs.SHORTCUT_ACCENT_TOKENS,
            tuple(item["token"] for item in spec["catalogs"]["shortcut_accents"]),
        )
        for d_item in studio_scope.default_dock_items():
            self.assertEqual(d_item["badge_style"], "")
            self.assertEqual(d_item["accent"], "")

        # Entity on App Dock defaults confirm=True; entity in Pinned defaults confirm=False
        dock_ent = studio_scope.normalize_shortcut_item(
            {
                "kind": "entity",
                "target": "Script.Baby_Help",
                "action": "turn_on",
                "label": "  Baby | Help  ",
                "icon": "baby_face_outline",
                "badge_style": "inverted",
                "accent": "gold",
            },
            is_dock=True,
        )
        assert dock_ent is not None
        self.assertEqual(dock_ent["target"], "script.baby_help")
        self.assertEqual(dock_ent["label"], "Baby Help")
        self.assertEqual(dock_ent["icon"], "mdi:baby-face-outline")
        self.assertTrue(dock_ent["confirm"])
        self.assertEqual(dock_ent["badge_style"], "inverted")
        self.assertEqual(dock_ent["accent"], "gold")

        pinned_ent = studio_scope.normalize_shortcut_item(
            {
                "kind": "entity",
                "target": "light.nursery_lamp",
                "action": "toggle",
                "badge_style": "glass",
                "accent": "default",
            },
            is_dock=False,
        )
        assert pinned_ent is not None
        self.assertFalse(pinned_ent["confirm"])
        self.assertEqual(pinned_ent["badge_style"], "")
        self.assertEqual(pinned_ent["accent"], "")

        styled_route = studio_scope.normalize_shortcut_item(
            {
                "kind": "route",
                "target": "weather:moon",
                "label": "Moon",
                "badge_style": "inverted",
                "accent": "primary",
            },
            is_dock=False,
        )
        assert styled_route is not None
        self.assertEqual(styled_route["badge_style"], "inverted")
        self.assertEqual(styled_route["accent"], "primary")

        # Strict mode rejects unknown badge_style or accent on both route and entity items
        for bad_item in (
            {"kind": "route", "target": "weather:moon", "badge_style": "solid"},
            {"kind": "route", "target": "weather:moon", "accent": "purple"},
            {"kind": "entity", "target": "light.desk", "action": "toggle", "badge_style": "flat"},
            {"kind": "entity", "target": "light.desk", "action": "toggle", "accent": "teal"},
        ):
            with self.assertRaises(ValueError):
                studio_scope.normalize_shortcut_item(bad_item, is_dock=False, strict=True)
            lenient = studio_scope.normalize_shortcut_item(bad_item, is_dock=False, strict=False)
            assert lenient is not None
            self.assertEqual(lenient["badge_style"], "")
            self.assertEqual(lenient["accent"], "")

        # Settings route is stripped on dock (always rendered last by firmware)
        self.assertIsNone(
            studio_scope.normalize_shortcut_item({"kind": "route", "target": "settings:root"}, is_dock=True)
        )
        # app:pinned is dock_only — rejected inside Pinned App
        with self.assertRaises(ValueError):
            studio_scope.normalize_shortcut_item({"kind": "route", "target": "app:pinned"}, is_dock=False)

        # lock and alarm_control_panel NEVER allow toggle
        for bad_target in ("lock.front_door", "alarm_control_panel.home_alarm"):
            with self.assertRaises(ValueError):
                studio_scope.normalize_shortcut_item(
                    {"kind": "entity", "target": bad_target, "action": "toggle"},
                    is_dock=False,
                )

    def test_live_state_and_entity_icon_resolution(self) -> None:
        self.assertEqual(_PAYLOADS_MOD.resolve_shortcut_live_state("light", "on"), 1)
        self.assertEqual(_PAYLOADS_MOD.resolve_shortcut_live_state("light", "off"), 0)
        self.assertEqual(_PAYLOADS_MOD.resolve_shortcut_live_state("light", "unavailable"), 2)
        self.assertEqual(_PAYLOADS_MOD.resolve_shortcut_live_state("scene", "scening"), -1)
        self.assertEqual(_PAYLOADS_MOD.resolve_shortcut_live_state("lock", "unlocked"), 1)
        self.assertEqual(_PAYLOADS_MOD.resolve_shortcut_live_state("lock", "locked"), 0)
        self.assertEqual(_PAYLOADS_MOD.resolve_shortcut_live_state("cover", "open"), 1)
        self.assertEqual(_PAYLOADS_MOD.resolve_shortcut_live_state("cover", "closed"), 0)
        self.assertEqual(
            _PAYLOADS_MOD.resolve_shortcut_entity_icon("cover", device_class="garage", state="open"),
            "mdi:garage-open",
        )
        self.assertEqual(
            _PAYLOADS_MOD.resolve_shortcut_entity_icon("switch", entity_icon="mdi:coffee-maker"),
            "mdi:coffee-maker",
        )

    def test_multi_chunk_shortcuts_packing_shares_single_revision(self) -> None:
        packer = DomainPayloadPacker(epoch=777)
        dock_recs = _PAYLOADS_MOD.shortcut_records(
            [
                {"kind": "route", "target": "app:pinned", "action": "", "label": "", "icon": "", "confirm": False, "state": -1},
                {
                    "kind": "entity",
                    "target": "scene.movie_night",
                    "action": "turn_on",
                    "label": "Movie",
                    "icon": "mdi:movie-open",
                    "confirm": True,
                    "state": -1,
                    "badge_style": "inverted",
                    "accent": "gold",
                },
            ],
            max_records=studio_scope.MAX_DOCK_ITEMS,
        )
        pinned_items = [
            {
                "kind": "entity",
                "target": f"switch.zone_{idx}",
                "action": "toggle",
                "label": f"Zone {idx}",
                "icon": "mdi:toggle-switch",
                "confirm": False,
                "state": idx % 2,
                "badge_style": "inverted" if idx == 0 else "",
                "accent": "red" if idx == 0 else "",
                **({"page": 0, "col": 1, "row": 0, "col_span": 2, "row_span": 1} if idx == 1 else {}),
            }
            for idx in range(25)
        ]
        pinned_recs = _PAYLOADS_MOD.shortcut_records(pinned_items, max_records=studio_scope.MAX_PINNED_ITEMS)
        title_recs = _PAYLOADS_MOD.pinned_page_title_records({"2": "Office", "0": "Favorites"})
        rev1, frames1 = packer.pack_shortcuts(dock_recs, pinned_recs, pinned_page_titles=title_recs)
        self.assertEqual(rev1, 1)
        self.assertEqual(len(frames1), 2)

        # Chunk 0 carries dock_items + first 18 pinned items + pinned_page_titles; Chunk 1 carries empty dock_items + remaining 7 pinned items + empty titles
        parts0 = frames1[0].split("\x1f")
        parts1 = frames1[1].split("\x1f")
        self.assertEqual(len(parts0), 9)
        self.assertEqual(len(parts1), 9)
        self.assertEqual(parts0[:5], ["v3", "777", "1", "0", "2"])
        self.assertEqual(parts1[:5], ["v3", "777", "1", "1", "2"])
        dock_wire_rows = parts0[5].split("\x1e")
        self.assertEqual(dock_wire_rows[0], "route|app:pinned||||0|-1|||||||")
        self.assertEqual(
            dock_wire_rows[1],
            "entity|scene.movie_night|turn_on|Movie|mdi:movie-open|1|-1|inverted|gold|||||",
        )
        self.assertEqual(parts1[5], "")
        self.assertEqual(parts0[6], "25")
        self.assertEqual(parts1[6], "25")
        pinned_wire_rows0 = parts0[7].split("\x1e")
        self.assertEqual(len(pinned_wire_rows0), 18)
        self.assertEqual(
            pinned_wire_rows0[0],
            "entity|switch.zone_0|toggle|Zone 0|mdi:toggle-switch|0|0|inverted|red|||||",
        )
        self.assertEqual(
            pinned_wire_rows0[1],
            "entity|switch.zone_1|toggle|Zone 1|mdi:toggle-switch|0|1|||0|1|0|2|",
        )
        self.assertEqual(len(parts1[7].split("\x1e")), 7)
        self.assertEqual(parts0[8], "0|Favorites\x1e2|Office")
        self.assertEqual(parts1[8], "")

        # Identical snapshot preserves rev; mutated state, accent, or page title increments rev across all chunks
        rev_same, _ = packer.pack_shortcuts(dock_recs, pinned_recs, pinned_page_titles=title_recs)
        self.assertEqual(rev_same, 1)
        pinned_items[0]["state"] = 1
        rev2, frames2 = packer.pack_shortcuts(
            dock_recs,
            _PAYLOADS_MOD.shortcut_records(pinned_items, max_records=studio_scope.MAX_PINNED_ITEMS),
            pinned_page_titles=title_recs,
        )
        self.assertEqual(rev2, 2)
        self.assertTrue(all(f.startswith("v3\x1f777\x1f2\x1f") for f in frames2))

        pinned_items[0]["accent"] = "green"
        rev3, frames3 = packer.pack_shortcuts(
            dock_recs,
            _PAYLOADS_MOD.shortcut_records(pinned_items, max_records=studio_scope.MAX_PINNED_ITEMS),
            pinned_page_titles=title_recs,
        )
        self.assertEqual(rev3, 3)
        self.assertIn("|inverted|green", frames3[0])

        rev4, frames4 = packer.pack_shortcuts(
            dock_recs,
            _PAYLOADS_MOD.shortcut_records(pinned_items, max_records=studio_scope.MAX_PINNED_ITEMS),
            pinned_page_titles=_PAYLOADS_MOD.pinned_page_title_records({"0": "Media Wall"}),
        )
        self.assertEqual(rev4, 4)
        self.assertEqual(frames4[0].split("\x1f")[8], "0|Media Wall")
        self.assertEqual(frames4[1].split("\x1f")[8], "")
