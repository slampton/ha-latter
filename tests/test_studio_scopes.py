"""Standalone tests for Latter Studio shortcut policy, issue attribution, cache-buster, and save scopes."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import tempfile
import unittest

from custom_components.latter import (
    backup,
    protocol_specs,
    repairs_keys as issue_ids,
)
from custom_components.latter.groups import device_groups
from custom_components.latter.studio import (
    panel as assets,
    settings_cleaners as settings,
    state_gates as scope,
)
from tests.conftest import LATTER_DIR, read_py_tree, read_ts_tree

groups = device_groups
reset_policy = device_groups


class TestShortcutPolicy(unittest.TestCase):
    """dock_items and pinned_items share one Universal Shortcut Engine across Protocol v3, HA, and Studio."""

    def test_normalize_dock_and_pinned_lists(self) -> None:
        dock_out = settings.normalize_dock_items(
            [
                {"kind": "route", "target": "app:pinned"},
                {
                    "kind": "route",
                    "target": "weather:moon",
                    "label": "Moon Phase",
                    "badge_style": "inverted",
                    "accent": "primary",
                },
                {"kind": "route", "target": "settings:root"},
                {
                    "kind": "entity",
                    "target": "scene.evening",
                    "action": "turn_on",
                    "badge_style": "glass",
                    "accent": "gold",
                },
            ]
        )
        self.assertEqual(
            [it["target"] for it in dock_out],
            ["app:pinned", "weather:moon", "scene.evening"],
        )
        self.assertEqual((dock_out[0]["badge_style"], dock_out[0]["accent"]), ("", ""))
        self.assertEqual((dock_out[1]["badge_style"], dock_out[1]["accent"]), ("inverted", "primary"))
        self.assertEqual((dock_out[2]["badge_style"], dock_out[2]["accent"]), ("", "gold"))
        self.assertTrue(dock_out[2]["confirm"])

        pinned_out = settings.normalize_pinned_items(
            [
                {"kind": "route", "target": "time:stopwatch"},
                {"kind": "route", "target": "music:album_tracks"},
                {"kind": "route", "target": "music:lyrics"},
                {"kind": "route", "target": "music:info"},
                {
                    "kind": "entity",
                    "target": "script.baby_help",
                    "action": "turn_on",
                    "label": "Baby Help",
                    "badge_style": "inverted",
                    "accent": "red",
                },
            ]
        )
        self.assertEqual(
            [it["target"] for it in pinned_out],
            [
                "time:stopwatch",
                "music:album_tracks",
                "music:lyrics",
                "music:info",
                "script.baby_help",
            ],
        )
        self.assertFalse(pinned_out[-1]["confirm"])
        self.assertEqual((pinned_out[-1]["badge_style"], pinned_out[-1]["accent"]), ("inverted", "red"))

        for bad_pinned in (
            [{"kind": "route", "target": "app:pinned"}],
            [{"kind": "route", "target": "not:a_route"}],
            [{"kind": "entity", "target": "lock.front", "action": "toggle"}],
            [{"kind": "route", "target": "weather:moon", "badge_style": "solid"}],
            [{"kind": "entity", "target": "light.desk", "action": "toggle", "accent": "magenta"}],
        ):
            with self.assertRaises(ValueError):
                settings.normalize_pinned_items(bad_pinned, strict=True)
            with self.assertRaises(settings.SettingsScopeError):
                settings.clean_device_settings({"pinned_items": bad_pinned})

    def test_one_default_and_route_catalog_in_both_repos(self) -> None:
        protocol_json = json.loads((LATTER_DIR / "protocol_v3.json").read_text(encoding="utf-8"))
        default_routes = protocol_json["defaults"]["dock_routes"]
        self.assertEqual(settings.DEFAULT_DOCK_ROUTES, default_routes)
        const_src = (LATTER_DIR / "const.py").read_text(encoding="utf-8")
        self.assertIn(f'DEFAULT_DOCK_ROUTES: Final = "{default_routes}"\n', const_src)
        protocol_ts = read_ts_tree("protocol-schema.ts")
        bundle_js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        for route in protocol_json["catalogs"]["shortcut_routes"]:
            self.assertIn(f'token: "{route["token"]}"', protocol_ts)
            self.assertIn(f'"{route["token"]}"', bundle_js)
        for style_item in protocol_json["catalogs"]["shortcut_badge_styles"]:
            self.assertIn(style_item["token"], settings.SHORTCUT_BADGE_STYLE_TOKENS)
            self.assertIn(f'token: "{style_item["token"]}"', protocol_ts)
        for accent_item in protocol_json["catalogs"]["shortcut_accents"]:
            self.assertIn(accent_item["token"], settings.SHORTCUT_ACCENT_TOKENS)
            self.assertIn(f'token: "{accent_item["token"]}"', protocol_ts)
        for music_tok, music_lbl in (
            ("music:album_tracks", "Album Tracks"),
            ("music:lyrics", "Music Lyrics"),
            ("music:info", "Track Info"),
        ):
            self.assertEqual(settings.SHORTCUT_ROUTE_MAP[music_tok]["label"], music_lbl)
            self.assertIn(f'token: "{music_tok}", label: "{music_lbl}"', protocol_ts)
            self.assertIn(f'"{music_tok}"', bundle_js)
        studio_contract = json.loads((LATTER_DIR / "studio_contract.json").read_text(encoding="utf-8"))
        self.assertNotIn("shortcut_action", studio_contract["ha_services"])
        self.assertEqual(
            protocol_json["rpc_methods"]["shortcut_action"]["fields"],
            ["entity_id", "action", "code"],
        )
        for key in ("dock_items", "pinned_items", "pinned_page_titles"):
            self.assertIn(key, settings.DEVICE_SETTING_KEYS)
            self.assertIn(key, groups.GROUP_APPEARANCE_DEVICE_KEYS)
            self.assertIn(key, backup.DEVICE_CONFIG_EXPORT_KEYS)
        self.assertNotIn("dock_apps", read_py_tree("coordinator"))
        self.assertNotIn("set_dock_apps", read_py_tree("services"))

    def test_grid_dims_multi_span_pinned_items_and_page_titles(self) -> None:
        # Trait-derived adaptive tile grid dimensions match firmware identically
        self.assertEqual(protocol_specs.tile_grid_dims_for_screen(466, 466, is_round=True), (2, 3))
        self.assertEqual(protocol_specs.tile_grid_dims_for_screen(800, 800, is_round=True), (2, 3))
        self.assertEqual(protocol_specs.tile_grid_dims_for_screen(1280, 800, is_round=False), (4, 3))
        self.assertEqual(protocol_specs.tile_grid_dims_for_screen(1024, 600, is_round=False), (4, 3))
        self.assertEqual(protocol_specs.tile_grid_dims_for_screen(800, 520, is_round=False), (4, 3))
        self.assertEqual(protocol_specs.tile_grid_dims_for_screen(720, 720, is_round=False), (3, 3))
        self.assertEqual(protocol_specs.tile_grid_dims_for_screen(600, 600, is_round=False), (3, 3))
        self.assertEqual(protocol_specs.tile_grid_dims_for_screen(410, 502, is_round=False), (2, 3))

        # Dock items never emit grid placement or span fields
        dock_with_grid = settings.normalize_dock_items(
            [{"kind": "route", "target": "app:music", "page": 0, "col": 0, "row": 0, "col_span": 2, "row_span": 2}],
            strict=True,
        )
        for gkey in ("page", "col", "row", "col_span", "row_span"):
            self.assertNotIn(gkey, dock_with_grid[0])

        # Pinned items preserve valid placement & >1 spans while omitting 1x1 spans
        pinned = settings.normalize_pinned_items(
            [
                {
                    "kind": "route",
                    "target": "app:music",
                    "page": 0,
                    "col": 1,
                    "row": 2,
                    "col_span": 2,
                    "row_span": 1,
                },
                {
                    "kind": "entity",
                    "target": "light.desk",
                    "action": "toggle",
                    "col_span": 1,
                    "row_span": 3,
                },
            ],
            strict=True,
        )
        self.assertEqual((pinned[0]["page"], pinned[0]["col"], pinned[0]["row"]), (0, 1, 2))
        self.assertEqual(pinned[0]["col_span"], 2)
        self.assertNotIn("row_span", pinned[0])
        self.assertNotIn("page", pinned[1])
        self.assertNotIn("col_span", pinned[1])
        self.assertEqual(pinned[1]["row_span"], 3)

        # Strict mode rejects partial coordinates, booleans, and out-of-range values
        for bad_item in (
            {"kind": "route", "target": "app:music", "page": 0, "col": 1},
            {"kind": "route", "target": "app:music", "page": True, "col": 0, "row": 0},
            {"kind": "route", "target": "app:music", "page": 32, "col": 0, "row": 0},
            {"kind": "route", "target": "app:music", "page": 0, "col": 4, "row": 0},
            {"kind": "route", "target": "app:music", "page": 0, "col": 0, "row": 3},
            {"kind": "route", "target": "app:music", "col_span": 0},
            {"kind": "route", "target": "app:music", "col_span": 5},
            {"kind": "route", "target": "app:music", "col_span": True},
            {"kind": "route", "target": "app:music", "row_span": 4},
        ):
            with self.assertRaises(ValueError):
                settings.normalize_pinned_items([bad_item], strict=True)
            with self.assertRaises(settings.SettingsScopeError):
                settings.clean_device_settings({"pinned_items": [bad_item]})

        # Non-strict mode drops partial/invalid placement and clamps spans
        relaxed = settings.normalize_pinned_items(
            [
                {"kind": "route", "target": "app:music", "page": 0, "col": 1, "col_span": 9, "row_span": 0},
                {"kind": "route", "target": "app:weather", "page": 99, "col": 0, "row": 0, "col_span": "bad"},
            ],
            strict=False,
        )
        self.assertNotIn("page", relaxed[0])
        self.assertEqual(relaxed[0]["col_span"], 4)
        self.assertNotIn("row_span", relaxed[0])
        self.assertNotIn("page", relaxed[1])
        self.assertNotIn("col_span", relaxed[1])

        # Pinned page titles: sorting, sanitization, truncation, empty drops, and strict errors
        self.assertEqual(settings.normalize_pinned_page_titles(None, strict=True), {})
        cleaned_titles = settings.clean_device_settings(
            {
                "pinned_page_titles": {
                    "10": "Media\x1f|Wall\n",
                    "2": "  Lighting  ",
                    "0": "X" * 30,
                    "1": "   ",
                    "3": None,
                }
            }
        )["pinned_page_titles"]
        self.assertEqual(
            list(cleaned_titles.items()),
            [("0", "X" * 24), ("2", "Lighting"), ("10", "Media Wall")],
        )
        for bad_titles in ("not_a_dict", {"32": "Too High"}, {"-1": "Neg"}, {True: "Bool"}, {"0": 123}):
            with self.assertRaises(ValueError):
                settings.normalize_pinned_page_titles(bad_titles, strict=True)
            with self.assertRaises(settings.SettingsScopeError):
                settings.clean_device_settings({"pinned_page_titles": bad_titles})
        self.assertEqual(
            settings.normalize_pinned_page_titles(
                {"bad": "Skip", "99": "Skip", "1": 123, "0": "Valid"}, strict=False
            ),
            {"0": "Valid"},
        )
        self.assertEqual(settings.normalize_pinned_page_titles("not_a_dict", strict=False), {})

    def test_media_handoff_is_one_latter_setting(self) -> None:
        protocol_json = json.loads((LATTER_DIR / "protocol_v3.json").read_text(encoding="utf-8"))
        studio_contract = json.loads((LATTER_DIR / "studio_contract.json").read_text(encoding="utf-8"))
        self.assertNotIn(
            "handoff_media", studio_contract["ha_services"]["set_active_area"]["fields"]
        )
        for rpc in ("set_active_area", "area_browse"):
            self.assertNotIn("handoff_media", protocol_json["rpc_methods"][rpc]["fields"])
        services_src = read_py_tree("services")
        self.assertNotIn('"handoff_media"', services_src)
        self.assertIn("area_handoff", settings.DEVICE_SETTING_KEYS)


class TestIssueAttribution(unittest.TestCase):
    """Studio's health banner and Issues card attribute each Latter repair to its Device."""

    def test_every_device_issue_parses_back_to_its_device(self) -> None:
        subs = {"01JABC", "01JXYZ"}
        for issue_id in issue_ids.device_issue_ids("01JABC"):
            parsed = issue_ids.parse_device_issue_id(issue_id, subs)
            self.assertIsNotNone(parsed, issue_id)
            self.assertEqual(parsed[1], "01JABC")
            self.assertEqual(f"{parsed[0]}_01JABC", issue_id)
        self.assertEqual(
            issue_ids.parse_device_issue_id("device_crashed_01JXYZ", subs),
            ("device_crashed", "01JXYZ"),
        )
        self.assertIsNone(issue_ids.parse_device_issue_id("device_crashed_01JGONE", subs))
        self.assertIsNone(issue_ids.parse_device_issue_id("something_else", subs))

    def test_kinds_match_the_repair_translations(self) -> None:
        strings = json.loads((LATTER_DIR / "strings.json").read_text(encoding="utf-8"))
        en_json = json.loads(
            (LATTER_DIR / "studio" / "locales" / "en.json").read_text(encoding="utf-8")
        )
        self.assertTrue(set(issue_ids.DEVICE_ISSUE_KINDS) <= set(strings["issues"]))
        self.assertIn("localizeRepairIssue", read_ts_tree("i18n", "utils"))
        for kind in issue_ids.DEVICE_ISSUE_KINDS:
            self.assertIn(f"issue.{kind}", en_json, f"Studio locale catalog missing issue.{kind}")


class TestPanelCacheBuster(unittest.TestCase):
    """The panel module URL's ?v= follows the JS content, with cache_headers=True and config_panel_domain=DOMAIN."""

    def test_digest_follows_content(self) -> None:
        js = LATTER_DIR / "frontend" / "latter-studio.js"
        self.assertEqual(assets.content_digest(js), assets.content_digest(js))
        self.assertRegex(assets.content_digest(js), r"^[0-9a-f]{16}$")
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.js"
            f.write_text("one", encoding="utf-8")
            first = assets.content_digest(f)
            f.write_text("two", encoding="utf-8")
            self.assertNotEqual(first, assets.content_digest(f))
        panel_src = read_py_tree("studio/panel.py")
        self.assertIn('latter-studio.js?v={js_digest}"', panel_src)
        self.assertIn("def content_digest(", panel_src)
        self.assertIn("cache_headers=True,", panel_src)
        self.assertIn("config_panel_domain=DOMAIN,", panel_src)
        self.assertIn("domain_data.registered_panel_url = None", panel_src)
        self.assertNotIn("_studio_js_digest", panel_src)


def _const_tables() -> tuple[dict[str, str], tuple[str, ...]]:
    """Return ({CONST_NAME: value}, GLOBAL_CONFIG_KEYS values) read from const.py by AST."""
    tree = ast.parse((LATTER_DIR / "const.py").read_text(encoding="utf-8"))
    names: dict[str, str] = {}
    global_names: list[str] = []
    for node in tree.body:
        target = value = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0].id, node.value
        if target is None:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            names[target] = value.value
        elif target == "GLOBAL_CONFIG_KEYS" and isinstance(value, ast.Tuple):
            global_names = [elt.id for elt in value.elts if isinstance(elt, ast.Name)]
    return names, tuple(names[n] for n in global_names)


class TestSaveScopes(unittest.TestCase):
    """A System save writes only System settings; a Device save writes only Device settings (D-007)."""

    CONST, GLOBAL_KEYS = _const_tables()

    def test_key_lists_match_const_and_scopes_are_disjoint(self) -> None:
        conf_values = {v for k, v in self.CONST.items() if k.startswith("CONF_")}
        self.assertTrue(set(settings.SYSTEM_SETTING_KEYS) <= conf_values)
        self.assertTrue(
            set(settings.DEVICE_SETTING_KEYS)
            <= conf_values | set(protocol_specs.DEVICE_PREF_KEYS)
        )
        self.assertTrue(set(settings.SYSTEM_SETTING_KEYS) <= set(self.GLOBAL_KEYS))
        self.assertFalse(set(settings.DEVICE_SETTING_KEYS) & set(self.GLOBAL_KEYS))
        self.assertNotIn("companion_base_url", self.GLOBAL_KEYS)
        seeded = dict.fromkeys(settings.DEVICE_SETTING_KEYS, "custom")
        after_reset = reset_policy.reset_subentry_data(
            seeded, {}, reset_policy.DEVICE_IDENTITY_KEYS
        )
        self.assertTrue(set(after_reset) <= set(reset_policy.DEVICE_IDENTITY_KEYS))

    def test_each_save_rejects_the_other_scope(self) -> None:
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_system_settings({"weather_entity": "weather.home", "device_group": "x"})
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings(
                {"default_area": "kitchen", "weather_entity": "weather.home"}
            )
        for key in (
            "camera_entity",
            "companion_base_url",
            "display_shape",
            "art_size",
            "vol_speaker_1",
            "remote_1",
        ):
            with self.assertRaises(settings.SettingsScopeError):
                settings.clean_system_settings({key: "x"})
            with self.assertRaises(settings.SettingsScopeError):
                settings.clean_device_settings({key: "x"})

    def test_system_save_normalizes_and_is_partial(self) -> None:
        cams = [f"camera.c{i}" for i in range(12)] + ["camera.c1", ""]
        out = settings.clean_system_settings(
            {
                "camera_entities": cams,
                "volume_overrides": [
                    {"speaker": "media_player.a", "target": "number.b"},
                    {"speaker": "x"},
                    "junk",
                ],
                "doorbell_noise_reduction": "loud",
                "custom_palettes": [
                    {"name": "", "hex": "#00ff88"},
                    {"hex": "blue"},
                    {"hex": "#00FF88"},
                ],
                "remote_groups": [
                    {"id": "rg_1", "remotes": ["remote.tv", "remote.tv"]},
                    {"name": "no id"},
                ],
            }
        )
        self.assertEqual(out["camera_entities"], [f"camera.c{i}" for i in range(10)])
        self.assertNotIn("camera_entity", out)
        self.assertEqual(
            out["volume_overrides"], [{"speaker": "media_player.a", "target": "number.b"}]
        )
        self.assertEqual(out["doorbell_noise_reduction"], "strong")
        self.assertEqual(out["custom_palettes"], [{"name": "#00FF88", "hex": "#00FF88"}])
        self.assertEqual(
            out["remote_groups"],
            [{"id": "rg_1", "name": "rg_1", "area_id": "", "remotes": ["remote.tv"]}],
        )
        self.assertEqual(
            settings.clean_system_settings({"custom_palettes": []}), {"custom_palettes": []}
        )
        self.assertEqual(
            settings.clean_system_settings({"camera_entities": []}), {"camera_entities": []}
        )
        ble_sys = settings.clean_system_settings(
            {
                "ble_attenuation": 0.8,
                "ble_max_radius_m": 80.0,
                "ble_max_velocity_mps": 3.46,
                "ble_away_timeout_s": 10,
            }
        )
        self.assertEqual(
            ble_sys,
            {
                "ble_attenuation": 1.5,
                "ble_max_radius_m": 50.0,
                "ble_max_velocity_mps": 3.5,
                "ble_away_timeout_s": 30,
            },
        )
        for bad_sys in (
            {"ble_attenuation": "fast"},
            {"ble_max_radius_m": "far"},
            {"ble_max_velocity_mps": "sprint"},
            {"ble_away_timeout_s": "never"},
        ):
            with self.assertRaises(settings.SettingsScopeError):
                settings.clean_system_settings(bad_sys)

    def test_device_save_normalizes_and_validates(self) -> None:
        out = settings.clean_device_settings(
            {
                "area_categories": " Media , light , media , ALL ",
                "wallpaper_cycle_minutes": -5,
                "area_handoff": 1,
                "assigned_person": " person.a ",
            }
        )
        self.assertEqual(
            out,
            {
                "area_categories": "media,light,all",
                "wallpaper_cycle_minutes": 0,
                "area_handoff": True,
                "assigned_person": "person.a",
            },
        )
        self.assertEqual(
            settings.clean_device_settings({"device_custom_color": "#3898ff"}),
            {"device_custom_color": "#3898FF"},
        )
        self.assertEqual(
            settings.clean_device_settings({"device_remote_group": " group:living_tv "}),
            {"device_remote_group": "group:living_tv"},
        )
        self.assertEqual(
            settings.clean_device_settings({"device_remote_group": ""}),
            {"device_remote_group": "area_auto"},
        )
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"device_remote_group": "bogus"})
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"device_custom_color": "red"})
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"area_categories": ""})
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"area_categories": "bogus"})
        self.assertEqual(
            settings.clean_device_settings({"ble_ref_power": ""}), {"ble_ref_power": None}
        )
        self.assertEqual(
            settings.clean_device_settings({"ble_ref_power": None}), {"ble_ref_power": None}
        )
        self.assertEqual(
            settings.clean_device_settings({"ble_ref_power": -95}), {"ble_ref_power": -90}
        )
        self.assertEqual(
            settings.clean_device_settings({"ble_ref_power": -20}), {"ble_ref_power": -30}
        )
        self.assertEqual(
            settings.clean_device_settings({"ble_ref_power": "-51"}), {"ble_ref_power": -51}
        )
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"ble_ref_power": "loud"})
        self.assertEqual(
            settings.clean_device_settings({"ble_category": ""}), {"ble_category": "auto"}
        )
        self.assertEqual(
            settings.clean_device_settings({"ble_category": " Phone "}), {"ble_category": "phone"}
        )
        self.assertEqual(
            settings.clean_device_settings({"ble_category": "BLE_TAG"}),
            {"ble_category": "ble_tag"},
        )
        self.assertIn("ble_category", backup.DEVICE_CONFIG_EXPORT_KEYS)
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"ble_category": "laptop"})

    def test_voice_follows_me_dwell_is_a_device_setting(self) -> None:
        self.assertIn("area_follow_dwell_s", settings.DEVICE_SETTING_KEYS)
        self.assertNotIn("area_follow_dwell_s", self.GLOBAL_KEYS)
        for raw, want in ((1, 3), (25, 25), ("100", 60)):
            self.assertEqual(
                settings.clean_device_settings({"area_follow_dwell_s": raw}),
                {"area_follow_dwell_s": want},
            )
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"area_follow_dwell_s": "soon"})
        flow_src = (LATTER_DIR / "config_flow.py").read_text(encoding="utf-8")
        self.assertNotIn("AREA_FOLLOW_DWELL", flow_src)

    def test_area_fusion_validates_against_the_areas_sensors(self) -> None:
        allowed = {"binary_sensor.kitchen_motion", "binary_sensor.kitchen_mmwave"}
        cur = {"mode": "weighted", "threshold_pct": 50, "sensors": []}
        out = settings.clean_area_fusion(
            cur,
            {
                "threshold_pct": 99,
                "sensors": ["binary_sensor.kitchen_mmwave", "binary_sensor.kitchen_mmwave"],
            },
            allowed,
        )
        self.assertEqual(
            out,
            {"mode": "weighted", "threshold_pct": 95, "sensors": ["binary_sensor.kitchen_mmwave"]},
        )
        self.assertEqual(
            settings.clean_area_fusion(cur, {"threshold_pct": 5}, allowed)["threshold_pct"], 20
        )
        self.assertEqual(
            settings.clean_area_fusion({}, {"mode": "BLE_ONLY"}, allowed), {"mode": "ble_only"}
        )
        self.assertEqual(settings.clean_area_fusion(cur, {"sensors": []}, allowed)["sensors"], [])
        for bad in (
            {"sensors": ["binary_sensor.front_door"]},
            {"sensors": ["lock.front_door"]},
            {"sensors": "binary_sensor.kitchen_motion"},
            {"mode": "bayesian"},
            {"threshold_pct": "high"},
        ):
            with self.assertRaises(settings.SettingsScopeError):
                settings.clean_area_fusion(cur, bad, allowed)

    def test_announcements_validate_mode_and_target(self) -> None:
        slugs = {"kitchen", "desk"}
        notify = settings.clean_announcement(
            {
                "mode": "notify",
                "target_device": "kitchen",
                "title": " Door ",
                "message": "Hi",
                "include_camera": 1,
            },
            slugs,
        )
        self.assertEqual(notify["service"], "notify")
        self.assertEqual(
            notify["data"],
            {
                "target_device": "kitchen",
                "title": "Door",
                "message": "Hi",
                "priority": "normal",
                "chime": True,
            },
        )
        self.assertTrue(notify["include_camera"])
        occupied = settings.clean_announcement(
            {"mode": "broadcast", "target_device": "occupied_areas", "message": "Dinner"}, slugs
        )
        self.assertEqual(
            occupied,
            {
                "service": "intercom_broadcast",
                "data": {"message": "Dinner", "target_device": "occupied_areas"},
                "include_camera": False,
            },
        )
        everyone = settings.clean_announcement(
            {"mode": "broadcast", "target_device": "all", "message": "Dinner"}, slugs
        )
        self.assertEqual(everyone["data"], {"message": "Dinner"})
        for bad in (
            {"mode": "notify", "target_device": "garage", "title": "t", "message": "m"},
            {"mode": "notify", "target_device": "kitchen", "title": "", "message": "m"},
            {"mode": "notify", "target_device": "kitchen", "title": "t", "message": "m", "priority": "urgent"},
            {"mode": "broadcast", "target_device": "kitchen", "message": "m"},
            {"mode": "broadcast", "target_device": "all", "message": " "},
            {"mode": "sms", "target_device": "all", "message": "m"},
        ):
            with self.assertRaises(settings.SettingsScopeError):
                settings.clean_announcement(bad, slugs)

    def test_system_view_reads_without_a_device(self) -> None:
        view = settings.system_settings_view(
            {"camera_entities": ["camera.door"], "weather_entity": "weather.home"}
        )
        self.assertEqual(view["camera_entities"], ["camera.door"])
        self.assertEqual(view["weather_entity"], "weather.home")
        self.assertEqual(view["alarm_entity"], "")
        self.assertEqual(view["doorbell_noise_reduction"], "strong")
        self.assertEqual(view["ble_attenuation"], 2.2)
        self.assertEqual(view["ble_max_radius_m"], 12.0)
        self.assertEqual(view["ble_max_velocity_mps"], 3.5)
        self.assertEqual(view["ble_away_timeout_s"], 180)
        self.assertEqual(set(view), set(settings.SYSTEM_SETTING_KEYS))


class TestEntityActionRestrictions(unittest.TestCase):
    """Studio entity actions only reach entities the backend itself offers."""

    def test_targets_must_all_be_allowed(self) -> None:
        allowed = {"select.kitchen_clock_face", "switch.kitchen_dock_saver"}
        self.assertEqual(
            scope.allowed_entity_targets(
                [" select.kitchen_clock_face ", "select.kitchen_clock_face", ""], allowed, "x"
            ),
            ["select.kitchen_clock_face"],
        )
        for bad in (
            ["lock.front_door"],
            ["select.kitchen_clock_face", "lock.front_door"],
            [],
            [None],
            ["  "],
        ):
            with self.assertRaises(scope.TargetNotAllowed):
                scope.allowed_entity_targets(bad, allowed, "an entity of Kitchen")
        with self.assertRaisesRegex(scope.TargetNotAllowed, "lock.front_door"):
            scope.allowed_entity_targets(["lock.front_door"], allowed, "an entity of Kitchen")

    def test_verbs(self) -> None:
        for verb in ("press", "install", "check", "toggle", "turn_on", "turn_off"):
            self.assertEqual(
                scope.checked_entity_verb({"action": verb}, scope.DEVICE_ENTITY_VERBS), verb
            )
        for bad in ({"action": "unlock"}, {"action": "disarm"}, {}, {"action": ""}):
            with self.assertRaises(scope.TargetNotAllowed):
                scope.checked_entity_verb(bad, scope.DEVICE_ENTITY_VERBS)
        self.assertFalse(hasattr(scope, "SYSTEM_ENTITY_VERBS"))
        self.assertNotIn("system_entity_action", scope.SYSTEM_COMMANDS)
        self.assertEqual(
            scope.checked_entity_verb({"option": "Analog"}, scope.DEVICE_ENTITY_VERBS), ""
        )
        self.assertEqual(scope.checked_entity_verb({"level": 40}, scope.DEVICE_ENTITY_VERBS), "")
        with self.assertRaises(scope.TargetNotAllowed):
            scope.checked_entity_verb(
                {"option": "Analog", "action": "unlock"}, scope.DEVICE_ENTITY_VERBS
            )


if __name__ == "__main__":
    unittest.main()
