"""Standalone tests for Latter Studio: System and Device save scopes, and entity-action restrictions.

They run without Home Assistant installed. The production modules under test (studio/settings.py,
studio/scope.py) are standard-library only and loaded by file path.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
from types import ModuleType
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"latter_studio_test_{name.replace('/', '_')}", LATTER_DIR / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


settings = _load("studio/settings")
scope = _load("studio/scope")
assets = _load("studio/assets")
issue_ids = _load("issue_ids")
dock_policy = _load("dock_policy")
catalog_gate = _load("studio/catalog_gate")


class TestPayloadDiet(unittest.TestCase):
    """The entity catalog travels only with get_state, the first subscription answer, and after a registry change."""

    def test_gate_opens_once_per_registry_change(self) -> None:
        gate = catalog_gate.CatalogGate()
        self.assertFalse(gate.take())
        gate.mark_dirty()
        gate.mark_dirty()
        self.assertTrue(gate.take())
        self.assertFalse(gate.take())

    def test_only_get_state_and_registry_changes_carry_the_catalog(self) -> None:
        payload_src = (LATTER_DIR / "studio" / "payload.py").read_text(encoding="utf-8")
        self.assertIn("    if include_catalog:\n        base[\"catalog\"]", payload_src)
        cmds = (LATTER_DIR / "studio" / "commands.py").read_text(encoding="utf-8")
        self.assertIn("build_studio_state_payload(hass, coord, include_catalog=catalog_gate.take())", cmds)
        for event in ("EVENT_ENTITY_REGISTRY_UPDATED", "EVENT_DEVICE_REGISTRY_UPDATED", "EVENT_AREA_REGISTRY_UPDATED"):
            self.assertIn(event, cmds)
        # Every other answer that isn't get_state or the subscription's first answer leaves it out.
        self.assertEqual(cmds.count("include_catalog=False"), 3)
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn("if (!data.catalog && STATE?.catalog) data.catalog = STATE.catalog;", js)

    def test_doorbell_detail_is_rendered(self) -> None:
        # Every payload field is read by Studio (studio-design.md section 2).
        payload_src = (LATTER_DIR / "studio" / "payload.py").read_text(encoding="utf-8")
        self.assertIn('"doorbells": _build_doorbells(', payload_src)
        for field in ("camera_name", "ring_entity", "ring_name", "ring_state", "ring_at", "talk"):
            self.assertIn(f'"{field}":', payload_src)
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn("const bells = STATE?.doorbells || [];", js)
        for field in ("camera_name", "ring_entity", "ring_name", "ring_state", "ring_at", "talk"):
            self.assertIn(f"b.{field}", js)

    def test_status_card_renders_its_fields(self) -> None:
        # One Status card on a Device's Overview; the SDK revision comes from the hardware manifest.
        payload_src = (LATTER_DIR / "studio" / "payload.py").read_text(encoding="utf-8")
        self.assertIn('"sdk_rev": str(coordinator.hardware_manifest.get("sdk") or ""),', payload_src)
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn('doc.getElementById("dash-sdk-rev").textContent = live.sdk_rev || "—";', js)
        self.assertEqual(js.count('<h3 class="card-title">Status</h3>'), 1)
        for gone in ('class="stat-grid"', '<h3 class="card-title">Now</h3>', '<h3 class="card-title">Device Status</h3>'):
            self.assertNotIn(gone, js)


class TestViewLayout(unittest.TestCase):
    """D-014: every view is two independent column stacks; no auto-placing grid."""

    def test_view_names_are_unqualified(self) -> None:
        # D-018: the scope switcher shows Devices or System, so view names don't repeat it.
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        titles = js[js.index("const VIEW_TITLES = {"):js.index("};", js.index("const VIEW_TITLES = {"))]
        names = re.findall(r': "([^"]+)"', titles)
        self.assertIn("Overview", names)
        self.assertEqual(names.count("Settings"), 2)
        for name in names:
            self.assertFalse(name.startswith(("System ", "Device ")), name)
        self.assertNotRegex(js, r"<span>(System|Device) (Overview|Settings)</span>")

    def test_sidebar_icon_module(self) -> None:
        # D-017: the panel's sidebar icon is "latter:logo", registered by a tiny static frontend module.
        init_src = (LATTER_DIR / "studio" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('SIDEBAR_ICON = "latter:logo"', init_src)
        self.assertIn('SIDEBAR_ICON_FALLBACK = "mdi:ladder"', init_src)
        self.assertIn("sidebar_icon=sidebar_icon,", init_src)
        self.assertIn('ICONS_MODULE = "latter-icons.js"', init_src)
        self.assertIn('icon_url = f"{versioned_prefix}/{ICONS_MODULE}?v={icon_digest}"', init_src)
        self.assertIn("frontend.add_extra_js_url(hass, icon_url)", init_src)
        self.assertIn("frontend.remove_extra_js_url(hass, icon_url)", init_src)
        # Served from the panel's static directory, so it needs no Latter HTTP view.
        self.assertIn("str(frontend_dir),", init_src)
        module = LATTER_DIR / "frontend" / "latter-icons.js"
        src = module.read_text(encoding="utf-8")
        self.assertLess(len(src.encode("utf-8")), 1500)
        self.assertIn("window.customIcons.latter = {", src)
        self.assertIn('getIcon: async () => ({ path: LATTER_LOGO_PATH, viewBox: "0 0 24 24" }),', src)
        self.assertNotIn("import ", src)
        self.assertNotIn("fetch(", src)
        # One single-color glyph: one path string, no secondary path, no fill or color.
        self.assertNotIn("secondaryPath", src)
        self.assertNotRegex(src, r"#[0-9a-fA-F]{3,6}\b|rgb\(|fill")
        for gone in ("LatterSidebarIconJsView", "sidebar_icon.js", "API_SIDEBAR_ICON_JS_PATH"):
            for path in LATTER_DIR.rglob("*.py"):
                self.assertNotIn(gone, path.read_text(encoding="utf-8"), f"{gone} in {path.name}")
        studio_js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertNotIn("brand-logo", studio_js)

    def test_brand_images_are_valid_png(self) -> None:
        # A text round-trip once replaced their high bytes with U+FFFD; HA and HACS show these files.
        sizes = {}
        for name in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png"):
            data = (LATTER_DIR / "brand" / name).read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"), name)
            self.assertNotIn(b"\xef\xbf\xbd", data[:64], name)
            sizes[name] = int.from_bytes(data[16:20], "big")
        self.assertEqual((sizes["icon.png"], sizes["icon@2x.png"]), (256, 512))

    def test_native_popups_follow_ha_dark_mode(self) -> None:
        # D-015: color-scheme follows hass.themes.darkMode, and select options get an opaque background.
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn('this.toggleAttribute("dark", Boolean(h?.themes?.darkMode ?? h?.selectedTheme?.dark));', js)
        self.assertIn("    color-scheme: light;\n", js)
        self.assertIn(":host([dark]) { color-scheme: dark; }", js)
        self.assertIn("select option, select optgroup { background-color: var(--studio-popup-bg); color: var(--studio-text); }", js)

    def test_columns_everywhere(self) -> None:
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertNotIn("grid-2", js)
        for view in ("system_overview", "shared_entities", "remotes", "system_sync", "area_tracking", "system_admin",
                     "dashboard", "home_display", "audio_voice", "power", "system"):
            start = js.index(f'<section id="view-{view}"')
            body = js[start:js.index("</section>", start)]
            self.assertEqual(body.count('<div class="columns">'), 1, view)
            self.assertEqual(body.count('<div class="column">'), 2, view)


class TestDockPolicy(unittest.TestCase):
    """dock_apps is the one source for the Home dock: the firmware shows exactly the listed apps."""

    def test_normalize_and_parse(self) -> None:
        self.assertEqual(dock_policy.normalize_dock_apps(" Music,area,music ,camera"), "music,area,camera")
        for bad in ("", " , ", "music,spotify", "settings"):
            with self.assertRaises(ValueError):
                dock_policy.normalize_dock_apps(bad)
        self.assertEqual(dock_policy.parse_dock_apps("tools, games,alarm,junk"), ["tools", "games", "alarm"])

    def test_one_default_and_one_token_set_in_both_repos(self) -> None:
        protocol = json.loads((LATTER_DIR / "protocol_v3.json").read_text(encoding="utf-8"))
        default = protocol["defaults"]["dock_apps"]
        self.assertEqual(dock_policy.normalize_dock_apps(default), default)
        const_src = (LATTER_DIR / "const.py").read_text(encoding="utf-8")
        self.assertIn(f'DEFAULT_DOCK_APPS: Final = "{default}"\n', const_src)
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        for tok in dock_policy.DOCK_APP_TOKENS:
            self.assertIn(f'{{token: "{tok}",', js)
        # The device's Home settings save through latter.set_dock_apps (protocol service, services.py).
        self.assertEqual(protocol["services"]["set_dock_apps"]["fields"], ["target_device", "dock_apps"])
        self.assertNotIn("dock_switch", (LATTER_DIR / "coordinator.py").read_text(encoding="utf-8"))

    def test_media_handoff_is_one_latter_setting(self) -> None:
        # D-008: no per-call override from the device; the Device's area_handoff decides.
        protocol = json.loads((LATTER_DIR / "protocol_v3.json").read_text(encoding="utf-8"))
        for svc in ("set_active_area", "area_browse"):
            self.assertNotIn("handoff_media", protocol["services"][svc]["fields"])
        services_src = (LATTER_DIR / "services.py").read_text(encoding="utf-8")
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
            issue_ids.parse_device_issue_id("device_crashed_01JXYZ", subs), ("device_crashed", "01JXYZ")
        )
        # Unknown Devices and non-Device repairs aren't attributed.
        self.assertIsNone(issue_ids.parse_device_issue_id("device_crashed_01JGONE", subs))
        self.assertIsNone(issue_ids.parse_device_issue_id("something_else", subs))

    def test_kinds_match_the_repair_translations(self) -> None:
        strings = json.loads((LATTER_DIR / "strings.json").read_text(encoding="utf-8"))
        self.assertTrue(set(issue_ids.DEVICE_ISSUE_KINDS) <= set(strings["issues"]))
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        for kind in issue_ids.DEVICE_ISSUE_KINDS:
            self.assertIn(f"  {kind}: ", js, f"Studio has no message for the {kind} repair")


class TestPanelCacheBuster(unittest.TestCase):
    """The panel module URL's ?v= follows the JS content, so a changed Studio never loads from cache."""

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
        init_src = (LATTER_DIR / "studio" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('latter-studio.js?v={js_digest}"', init_src)
        self.assertIn("content_digest,", init_src)


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
        self.assertTrue(set(settings.DEVICE_SETTING_KEYS) <= conf_values)
        self.assertTrue(set(settings.SYSTEM_SETTING_KEYS) <= set(self.GLOBAL_KEYS))
        self.assertFalse(set(settings.DEVICE_SETTING_KEYS) & set(self.GLOBAL_KEYS))
        self.assertNotIn("companion_base_url", self.GLOBAL_KEYS)

    def test_each_save_rejects_the_other_scope(self) -> None:
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_system_settings({"weather_entity": "weather.home", "device_group": "x"})
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"default_area": "kitchen", "weather_entity": "weather.home"})
        # The primary camera is derived from the camera list, never sent; retired keys are rejected.
        for key in ("camera_entity", "companion_base_url", "display_shape", "art_size", "vol_speaker_1", "remote_1"):
            with self.assertRaises(settings.SettingsScopeError):
                settings.clean_system_settings({key: "x"})
            with self.assertRaises(settings.SettingsScopeError):
                settings.clean_device_settings({key: "x"})

    def test_system_save_normalizes_and_is_partial(self) -> None:
        cams = [f"camera.c{i}" for i in range(12)] + ["camera.c1", ""]
        out = settings.clean_system_settings(
            {
                "camera_entities": cams,
                "volume_overrides": [{"speaker": "media_player.a", "target": "number.b"}, {"speaker": "x"}, "junk"],
                "doorbell_noise_reduction": "loud",
                "custom_palettes": [{"name": "", "hex": "#00ff88"}, {"hex": "blue"}, {"hex": "#00FF88"}],
                "remote_groups": [{"id": "rg_1", "remotes": ["remote.tv", "remote.tv"]}, {"name": "no id"}],
            }
        )
        self.assertEqual(out["camera_entities"], [f"camera.c{i}" for i in range(10)])
        self.assertEqual(out["camera_entity"], "camera.c0")
        self.assertEqual(out["volume_overrides"], [{"speaker": "media_player.a", "target": "number.b"}])
        self.assertEqual(out["doorbell_noise_reduction"], "strong")
        self.assertEqual(out["custom_palettes"], [{"name": "#00FF88", "hex": "#00FF88"}])
        self.assertEqual(out["remote_groups"], [{"id": "rg_1", "name": "rg_1", "area_id": "", "remotes": ["remote.tv"]}])
        # A partial save (the color library) writes only what it names.
        self.assertEqual(
            settings.clean_system_settings({"custom_palettes": []}), {"custom_palettes": []}
        )
        self.assertEqual(
            settings.clean_system_settings({"camera_entities": []}), {"camera_entities": [], "camera_entity": ""}
        )

    def test_device_save_normalizes_and_validates(self) -> None:
        out = settings.clean_device_settings(
            {"default_page_size": "50", "wallpaper_cycle_minutes": -5, "area_handoff": 1, "assigned_person": " person.a "}
        )
        self.assertEqual(
            out,
            {"default_page_size": 20, "wallpaper_cycle_minutes": 0, "area_handoff": True, "assigned_person": "person.a"},
        )
        self.assertEqual(settings.clean_device_settings({"device_custom_color": "#3898ff"}), {"device_custom_color": "#3898FF"})
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"device_custom_color": "red"})
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"default_page_size": "many"})

    def test_voice_follows_me_dwell_is_a_device_setting(self) -> None:
        # One home: each Device's subentry (the System options flow no longer has it).
        self.assertIn("area_follow_dwell_s", settings.DEVICE_SETTING_KEYS)
        self.assertNotIn("area_follow_dwell_s", self.GLOBAL_KEYS)
        for raw, want in ((1, 3), (25, 25), ("100", 60)):
            self.assertEqual(settings.clean_device_settings({"area_follow_dwell_s": raw}), {"area_follow_dwell_s": want})
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"area_follow_dwell_s": "soon"})
        # The startup migration's tolerant clamp, and the default matches const.py.
        self.assertEqual(settings.clean_dwell_s("7.9"), 7)
        self.assertEqual(settings.clean_dwell_s(None), settings.DEFAULT_DWELL_S)
        const_src = (LATTER_DIR / "const.py").read_text(encoding="utf-8")
        self.assertIn(f"DEFAULT_AREA_FOLLOW_DWELL_S: Final = {settings.DEFAULT_DWELL_S}\n", const_src)
        flow_src = (LATTER_DIR / "config_flow.py").read_text(encoding="utf-8")
        self.assertNotIn("AREA_FOLLOW_DWELL", flow_src)

    def test_area_fusion_validates_against_the_areas_sensors(self) -> None:
        allowed = {"binary_sensor.kitchen_motion", "binary_sensor.kitchen_mmwave"}
        cur = {"mode": "weighted", "threshold_pct": 50, "sensors": []}
        out = settings.clean_area_fusion(
            cur, {"threshold_pct": 99, "sensors": ["binary_sensor.kitchen_mmwave", "binary_sensor.kitchen_mmwave"]}, allowed
        )
        self.assertEqual(out, {"mode": "weighted", "threshold_pct": 95, "sensors": ["binary_sensor.kitchen_mmwave"]})
        self.assertEqual(settings.clean_area_fusion(cur, {"threshold_pct": 5}, allowed)["threshold_pct"], 20)
        self.assertEqual(settings.clean_area_fusion({}, {"mode": "BLE_ONLY"}, allowed), {"mode": "ble_only"})
        # An empty list means every sensor in the Area counts.
        self.assertEqual(settings.clean_area_fusion(cur, {"sensors": []}, allowed)["sensors"], [])
        for bad in (
            {"sensors": ["binary_sensor.front_door"]},  # another Area's sensor
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
            {"mode": "notify", "target_device": "kitchen", "title": " Door ", "message": "Hi", "include_camera": 1}, slugs
        )
        self.assertEqual(notify["service"], "notify")
        self.assertEqual(notify["data"], {"target_device": "kitchen", "title": "Door", "message": "Hi", "priority": "normal", "chime": True})
        self.assertTrue(notify["include_camera"])
        occupied = settings.clean_announcement({"mode": "broadcast", "target_device": "occupied_areas", "message": "Dinner"}, slugs)
        self.assertEqual(occupied, {"service": "intercom_broadcast", "data": {"message": "Dinner", "target_device": "occupied_areas"}, "include_camera": False})
        everyone = settings.clean_announcement({"mode": "broadcast", "target_device": "all", "message": "Dinner"}, slugs)
        self.assertEqual(everyone["data"], {"message": "Dinner"})
        for bad in (
            {"mode": "notify", "target_device": "garage", "title": "t", "message": "m"},  # unknown Device
            {"mode": "notify", "target_device": "kitchen", "title": "", "message": "m"},
            {"mode": "notify", "target_device": "kitchen", "title": "t", "message": "m", "priority": "urgent"},
            {"mode": "broadcast", "target_device": "kitchen", "message": "m"},
            {"mode": "broadcast", "target_device": "all", "message": " "},
            {"mode": "sms", "target_device": "all", "message": "m"},
        ):
            with self.assertRaises(settings.SettingsScopeError):
                settings.clean_announcement(bad, slugs)

    def test_system_view_reads_without_a_device(self) -> None:
        view = settings.system_settings_view({"camera_entity": "camera.door", "weather_entity": "weather.home"})
        self.assertEqual(view["camera_entities"], ["camera.door"])
        self.assertEqual(view["weather_entity"], "weather.home")
        self.assertEqual(view["alarm_entity"], "")
        self.assertEqual(view["doorbell_noise_reduction"], "strong")
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
        for bad in (["lock.front_door"], ["select.kitchen_clock_face", "lock.front_door"], [], [None], ["  "]):
            with self.assertRaises(scope.TargetNotAllowed):
                scope.allowed_entity_targets(bad, allowed, "an entity of Kitchen")
        with self.assertRaisesRegex(scope.TargetNotAllowed, "lock.front_door"):
            scope.allowed_entity_targets(["lock.front_door"], allowed, "an entity of Kitchen")

    def test_verbs(self) -> None:
        for verb in ("press", "install", "check", "toggle", "turn_on", "turn_off"):
            self.assertEqual(scope.checked_entity_verb({"action": verb}, scope.DEVICE_ENTITY_VERBS), verb)
        for bad in ({"action": "unlock"}, {"action": "disarm"}, {}, {"action": ""}):
            with self.assertRaises(scope.TargetNotAllowed):
                scope.checked_entity_verb(bad, scope.DEVICE_ENTITY_VERBS)
        # Bulk System controls only switch on or off, select an option, or set a level.
        with self.assertRaises(scope.TargetNotAllowed):
            scope.checked_entity_verb({"action": "toggle"}, scope.SYSTEM_ENTITY_VERBS)
        self.assertEqual(scope.checked_entity_verb({"option": "Analog"}, scope.SYSTEM_ENTITY_VERBS), "")
        self.assertEqual(scope.checked_entity_verb({"level": 40}, scope.SYSTEM_ENTITY_VERBS), "")


if __name__ == "__main__":
    unittest.main()
