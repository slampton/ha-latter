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
entity_sections = _load("entity_sections")


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
        self.assertIn("        _track_coordinators()\n        _track_device_states()\n        _schedule_push()", cmds)
        self.assertIn("_apply_wallpaper_config(", cmds)
        self.assertIn("inspector_by_subentry", payload_src)
        self.assertIn("self._cached_bytes", payload_src)
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn("if (!data.catalog && STATE?.catalog) data.catalog = STATE.catalog;", js)

    def test_doorbell_detail_is_rendered(self) -> None:
        # Every payload field is read by Studio (studio-design.md section 2).
        payload_src = (LATTER_DIR / "studio" / "payload.py").read_text(encoding="utf-8")
        self.assertIn('"doorbells": _build_doorbells(', payload_src)
        for field in ("camera_name", "preview_url", "ring_entity", "ring_name", "ring_state", "ring_at", "talk"):
            self.assertIn(f'"{field}":', payload_src)
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn("const bells = STATE?.doorbells || [];", js)
        for field in ("camera_name", "ring_entity", "ring_name", "ring_state", "ring_at", "talk"):
            self.assertIn(f"b.{field}", js)
        self.assertIn("const previewUrl = dbObj?.preview_url || camObj?.preview_url || \"\";", js)
        self.assertIn("bustCache ? `${previewUrl}&_ts=${Date.now()}` : previewUrl", js)
        self.assertIn("window.fmtPercent = fmtPercent;", js)
        self.assertIn('window.removeEventListener("mousemove", onCwWindowMove);', js)
        self.assertNotIn("dialog-title danger", js)
        self.assertNotIn("onAssignedPersonChanged", js)

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
        # D-020: each scope's last view is Tools, and both scopes call BLE presence the same.
        self.assertEqual(names.count("Tools"), 2)
        self.assertEqual(names.count("BLE & Area Presence"), 2)
        self.assertNotIn("Settings", names)
        for name in names:
            self.assertFalse(name.startswith(("System ", "Device ")), name)
        self.assertNotRegex(js, r"<span>(System|Device) (Overview|Settings)</span>")

    def test_information_architecture(self) -> None:
        # D-020: Tools pages, BLE & Area Presence for a Device, identity on the Overview, no count badges on pages.
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn('const DEVICE_VIEW_SLUGS = {dashboard: "overview", home_display: "display", audio_voice: "audio", power: "power", presence: "presence", tools: "tools"};', js)
        self.assertIn('system_sync: "groups", area_tracking: "presence", system_tools: "tools"};', js)
        self.assertNotIn('"settings"', js[js.index("const DEVICE_VIEW_SLUGS"):js.index("const slugToView")])
        nav = js[js.index('<nav class="nav-list hidden" id="nav-scope-device"'):js.index("</nav>", js.index('id="nav-scope-device"'))]
        self.assertEqual(
            re.findall(r'data-view="(\w+)"', nav), ["dashboard", "home_display", "audio_voice", "power", "presence", "tools"]
        )
        self.assertNotIn("nav-esp-badge", js)
        self.assertEqual(js.count('class="nav-badge"'), 1)  # All Devices: the number of Devices it lists

        def section(view: str) -> str:
            start = js.index(f'<section id="view-{view}"')
            return js[start:js.index("</section>", start)]

        tools, sys_tools, groups, overview = section("tools"), section("system_tools"), section("system_sync"), section("dashboard")
        for title in ("Diagnostics", "Replace Hardware", "Danger Zone"):
            self.assertIn(f'<h3 class="card-title">{title}</h3>', tools)
        for title in ("Notifications &amp; Announcements", "Backup &amp; Restore", "System &amp; Device Logs"):
            self.assertIn(f'<h3 class="card-title">{title}</h3>', sys_tools)
        self.assertNotIn("Export Settings", js)
        self.assertNotIn("Restore From File", js)
        self.assertIn("Custom Color Library", groups)
        self.assertNotIn("Custom Color Library", sys_tools)
        self.assertIn('id="dash-node-name"', overview)
        self.assertIn('id="cfg-device_group"', overview)
        self.assertIn('id="btn-open-in-ha"', overview)
        self.assertIn('id="cfg-ble_target_address"', section("presence"))
        for gone in ("In Home Assistant</h3>", "Location &amp; BLE</h3>", 'id="cfg-device_slug"', 'id="st-group"'):
            self.assertNotIn(gone, js)
        # The entity-count badge's data is gone from the payload too.
        self.assertNotIn('"count": len(', (LATTER_DIR / "area_engine.py").read_text(encoding="utf-8"))

    def test_entity_only_cards_hide_when_empty(self) -> None:
        # A card that only lists the Device's entities hides when there are none (Desk has no battery entities).
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        start = js.index('<section id="view-power"')
        power = js[start:js.index("</section>", start)]
        self.assertEqual(power.count('<div class="card" data-entity-card>'), 2)
        self.assertIn('card.classList.toggle("hidden", !card.querySelector(".settings-row"));', js)
        render = js[js.index("function renderCohesiveDeviceSections()"):]
        self.assertIn("  syncEntityCards();\n}", render[: render.index("\n}\n") + 3])

    def test_home_sun_and_moon_switches_in_home_section(self) -> None:
        self.assertEqual(
            entity_sections.classify_esphome_entity_section(
                "switch.pocket_home_sun", "Home: Sun", "switch", "", "config"
            ),
            ("home", None),
        )
        self.assertEqual(
            entity_sections.classify_esphome_entity_section(
                "switch.pocket_home_moon", "Home: Moon", "switch", "", "config"
            ),
            ("home", None),
        )
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn(
            '["wake greeting", "weather background", "sun", "moon"]',
            js,
        )
        self.assertIn(
            '["default category", "show all category"]',
            js,
        )
        start = js.index('<section id="view-home_display"')
        view = js[start:js.index("</section>", start)]
        self.assertIn('<h3 class="card-title">Home Screen</h3>', view)
        self.assertIn('<h3 class="card-title">Area Controls</h3>', view)
        self.assertIn('id="embedded-area-ui"', view)
        self.assertLess(view.index('id="dock-pills-container"'), view.index('id="embedded-home"'))

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
        for view in ("system_overview", "shared_entities", "remotes", "system_sync", "area_tracking", "system_tools",
                     "dashboard", "home_display", "audio_voice", "power", "presence", "tools"):
            start = js.index(f'<section id="view-{view}"')
            body = js[start:js.index("</section>", start)]
            self.assertEqual(body.count('<div class="columns">'), 1, view)
            self.assertEqual(body.count('<div class="column">'), 2, view)


class TestActivityCard(unittest.TestCase):
    """The Home Activity Card: a Device setting, carried as area_context.activity_card / activity_sources."""

    def setUp(self) -> None:
        self.policy = _load("activity_policy")

    def test_normalize_sources(self) -> None:
        n = self.policy.normalize_activity_sources
        self.assertEqual(n("timers, Calendar,timers"), "calendar,timers")
        self.assertEqual(n(["alarms", "music_queue"]), "music_queue,alarms")
        self.assertEqual(n(""), "")
        with self.assertRaises(ValueError):
            n("calendar,weather")

    def test_payload_never_sends_an_on_card_without_sources(self) -> None:
        p = self.policy.activity_payload
        self.assertEqual(p(True, "calendar,timers"), (1, "calendar,timers"))
        self.assertEqual(p(False, "calendar,timers"), (0, "calendar,timers"))
        self.assertEqual(p(True, ""), (0, ""))

    def test_defaults_match_the_protocol_and_the_setting_is_everywhere(self) -> None:
        protocol = json.loads((LATTER_DIR / "protocol_v3.json").read_text(encoding="utf-8"))
        self.assertEqual(protocol["defaults"]["activity_card"], "1")
        self.assertEqual(protocol["defaults"]["activity_sources"], ",".join(self.policy.ACTIVITY_SOURCE_KEYS))
        const_src = (LATTER_DIR / "const.py").read_text(encoding="utf-8")
        self.assertIn("DEFAULT_ACTIVITY_CARD: Final = True\n", const_src)
        self.assertIn(f'DEFAULT_ACTIVITY_SOURCES: Final = "{protocol["defaults"]["activity_sources"]}"\n', const_src)
        fields = {f["name"]: f for f in protocol["domains"]["area_context"]["fields"]}
        self.assertEqual((fields["activity_card"]["index"], fields["activity_card"]["type"]), (38, "bool"))
        self.assertEqual((fields["activity_sources"]["index"], fields["activity_sources"]["type"]), (39, "csv"))
        # A Device setting: Studio save, reset, backups and Configuration Profiles all carry it.
        self.assertIn("activity_card", settings.DEVICE_BOOL_KEYS)
        self.assertIn("activity_sources", settings.DEVICE_TEXT_KEYS)
        for name in ("reset_policy.py", "backup_engine.py"):
            src = (LATTER_DIR / name).read_text(encoding="utf-8")
            self.assertIn("activity_card" if name == "reset_policy.py" else "CONF_ACTIVITY_CARD", src, name)
        backup_src = (LATTER_DIR / "backup_engine.py").read_text(encoding="utf-8")
        profile_keys = backup_src[backup_src.index("PROFILE_DEVICE_KEYS"):backup_src.index("DEFAULT_DEVICE_GROUPS")]
        self.assertIn("CONF_ACTIVITY_SOURCES", profile_keys)
        coord_src = (LATTER_DIR / "coordinator.py").read_text(encoding="utf-8")
        self.assertIn("*activity_payload(self.activity_card_enabled, self.activity_sources_csv),", coord_src)

    def test_studio_rows(self) -> None:
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        start = js.index('<section id="view-home_display"')
        view = js[start:js.index("</section>", start)]
        self.assertIn('<h3 class="card-title">Activity Card</h3>', view)
        self.assertIn('id="cfg-activity_card"', view)
        self.assertIn(">Show the Activity Card</label>", view)
        for key in self.policy.ACTIVITY_SOURCE_KEYS:
            self.assertIn(f'data-src="{key}"', view)
        for label in ("Calendar", "Music Queue", "Stopwatch", "Alarms", "Timers"):
            self.assertIn(f'data-label="{label}"', view)
            self.assertIn(f">✓ {label}</button>", view)
        self.assertIn("window.onActivityCardChanged = onActivityCardChanged;", js)
        self.assertIn("window.toggleActivitySource = toggleActivitySource;", js)


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
        reset_policy = _load("reset_policy")
        reset_keys = set(reset_policy.DEVICE_OPTION_KEYS) | set(reset_policy.DEVICE_IDENTITY_KEYS)
        self.assertTrue(
            set(settings.DEVICE_SETTING_KEYS) <= reset_keys,
            f"Device settings missing from reset_policy.py: {set(settings.DEVICE_SETTING_KEYS) - reset_keys}",
        )

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
