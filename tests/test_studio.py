"""Standalone tests for Latter Studio: System and Device save scopes, Lit view architecture, and entity-action restrictions."""

from __future__ import annotations

import ast
import itertools
import json
from pathlib import Path
import tempfile
import unittest

from custom_components.latter import (
    backup,
    const as latter_const,
    groups,
    protocol,
    repairs,
    studio as studio_init,
)
from custom_components.latter.studio import settings

activity_policy = protocol
dock_policy = protocol
entity_sections = groups
issue_ids = repairs
reset_policy = groups
assets = studio_init
catalog_gate = settings
scope = settings

REPO_ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"


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
        self.assertIn('    if include_catalog:\n        base["catalog"]', payload_src)
        cmds = (LATTER_DIR / "studio" / "commands.py").read_text(encoding="utf-8")
        self.assertIn("include_catalog=catalog_gate.take()", cmds)
        for event in ("EVENT_ENTITY_REGISTRY_UPDATED", "EVENT_DEVICE_REGISTRY_UPDATED", "EVENT_AREA_REGISTRY_UPDATED"):
            self.assertIn(event, cmds)
        self.assertGreaterEqual(cmds.count("include_catalog=False"), 3)
        self.assertIn("_track_coordinators()", cmds)
        self.assertIn("_track_device_states()", cmds)
        self.assertIn("_cmd_set_device_photo_pool(", cmds)
        views_src = (LATTER_DIR / "http.py").read_text(encoding="utf-8")
        self.assertIn("esphome_inspector", payload_src)
        self.assertIn("self._cached_bytes", views_src)
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn(".catalog", js)

    def test_doorbell_detail_is_rendered(self) -> None:
        payload_src = (LATTER_DIR / "studio" / "payload.py").read_text(encoding="utf-8")
        cmds_src = (LATTER_DIR / "studio" / "commands.py").read_text(encoding="utf-8")
        self.assertIn('"doorbells": _build_doorbells(', payload_src)
        self.assertNotIn('"preview_url":', payload_src)
        self.assertIn('"mint_camera_preview_url"', cmds_src)
        for field in ("camera_name", "ring_entity", "ring_name", "ring_state", "ring_at", "talk"):
            self.assertIn(f'"{field}":', payload_src)
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn(".doorbells", js)
        self.assertIn(".ring_entity", js)
        self.assertNotIn("doorbell-status-list", js)
        self.assertIn("sortable-row-stacked", js)
        # Stage 6 encapsulation: zero window.* globals!
        self.assertNotIn("window.fmtPercent", js)
        self.assertNotIn("dialog-title danger", js)
        self.assertNotIn("onAssignedPersonChanged", js)

    def test_status_card_renders_its_fields(self) -> None:
        payload_src = (LATTER_DIR / "studio" / "payload.py").read_text(encoding="utf-8")
        en_json = json.loads((LATTER_DIR / "studio" / "locales" / "en.json").read_text(encoding="utf-8"))
        self.assertIn('"sdk_rev": str(coordinator.hardware_manifest.get("sdk") or ""),', payload_src)
        self.assertNotIn("_build_now_playing", payload_src)
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertEqual(en_json["card.status"], "Status")
        self.assertEqual(js.count('store.t("card.status")'), 2)
        self.assertIn('id="diag-sdk-rev"', js)
        self.assertIn('class="status-tiles"', js)
        self.assertRegex(js, r"@container\s*\(max-width:\s*420px\)")
        self.assertRegex(js, r"@container\s*\(max-width:\s*260px\)")
        self.assertNotIn("status-assignments", js)
        for gone in (
            'class="stat-grid"',
            'id="dash-sdk-rev"',
            'id="dash-node-name"',
            "<span>Now Playing</span>",
            '<h3 class="card-title">Now</h3>',
            '<h3 class="card-title">Device Status</h3>',
        ):
            self.assertNotIn(gone, js)


class TestViewLayout(unittest.TestCase):
    """D-014 & D-061: every view is two independent column stacks with HA Sentence-case titles."""

    def test_view_names_are_unqualified(self) -> None:
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        en_json = json.loads((LATTER_DIR / "studio" / "locales" / "en.json").read_text(encoding="utf-8"))
        names = [
            v for k, v in en_json.items() if k.startswith("view.")
        ]
        self.assertEqual(names.count("Overview"), 2)
        self.assertEqual(names.count("Tools"), 2)
        self.assertEqual(names.count("BLE & Area presence"), 1)
        for short_dev_title in ("Display", "Interface", "Audio", "Power", "Presence"):
            self.assertIn(short_dev_title, names)
        self.assertNotIn("Display & Home", names)
        self.assertNotIn("Audio & Voice", names)
        self.assertNotIn("Power & Battery", names)
        self.assertNotIn("Settings", names)
        self.assertIn("Device groups", names)
        self.assertIn("Managed devices", names)
        self.assertIn("Discovered devices", names)
        self.assertNotIn("All Devices", names)
        for name in names:
            self.assertFalse(name.startswith("System "), name)
            if name != "Device groups":
                self.assertFalse(name.startswith("Device "), name)
        self.assertNotRegex(js, r"<span>(System|Device) (Overview|Settings)</span>")

    def test_information_architecture(self) -> None:
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        en_json = json.loads((LATTER_DIR / "studio" / "locales" / "en.json").read_text(encoding="utf-8"))
        self.assertIn('dashboard: "overview"', js)
        self.assertIn('display: "display"', js)
        self.assertIn('interface: "interface"', js)
        self.assertIn('system_sync: "groups"', js)
        self.assertIn('area_tracking: "presence"', js)
        self.assertIn('system_tools: "tools"', js)
        self.assertNotIn("nav-esp-badge", js)
        self.assertNotIn("set_device_remote_group", js)
        self.assertNotIn("assignDeviceRemoteGroup", js)
        self.assertEqual(js.count('class="nav-badge"'), 2)
        self.assertIn('href="/latter/devices"', js)
        self.assertIn('href="/latter/devices/discovered"', js)
        self.assertEqual(en_json["nav.managed"], "Managed")
        self.assertEqual(en_json["nav.discovered"], "Discovered")
        self.assertEqual(en_json["nav.back_managed"], "← Managed")
        self.assertNotIn("<span>&larr; All Devices</span>", js)

        def section(view: str) -> str:
            start = js.index(f'<section id="view-{view}"')
            return js[start:js.index("</section>", start)]

        discovered_view = section("discovered_devices")
        area_tracking_view = section("area_tracking")
        self.assertIn('id: "card-discovered-latter"', discovered_view)
        self.assertIn('id: "card-discovered-ble"', discovered_view)
        self.assertLess(
            discovered_view.index('id: "card-discovered-latter"'),
            discovered_view.index('id: "card-discovered-ble"'),
        )
        self.assertIn('id="latter-adopt-table-box"', discovered_view)
        self.assertIn('id="ble-adopt-table-box"', discovered_view)
        self.assertIn("c.is_tracker", js)
        self.assertNotIn("TRACKER_KIND_TOKENS", js)
        self.assertIn("ignoreDiscoveredDevice", discovered_view)
        self.assertIn("unignoreDiscoveredDevice", discovered_view)
        self.assertEqual(latter_const.STUDIO_REV, 40)
        self.assertIn("STUDIO_REV = 39", js)
        self.assertIn(".card.handoff-active", js)
        self.assertIn(".area-presence-box.handoff-active", js)
        self.assertIn(".calibrate-target-box.handoff-active", js)
        self.assertNotIn("border:2px solid var(--studio-warning)", js)
        self.assertIn("cfg-home_date_tap_action", js)
        self.assertIn("cfg-calendar_lookahead_days", js)
        self.assertIn("cfg-calendar_week_start", js)
        self.assertNotIn("tools:calendar", js)
        self.assertNotIn("Power Profile", js)
        self.assertNotIn("fusion-area", js)
        self.assertNotIn("d.has_ble ||", js)
        self.assertNotIn(".area-presence-box.occupied", js)
        self.assertNotIn('? " occupied"', area_tracking_view)
        self.assertNotIn('id="ble-proxy-trim-drawer"', js)
        self.assertNotIn("proxyTrimOpen", js)
        self.assertGreaterEqual(js.count('d.ble_tracked || d.kind === "ble_tag"'), 2)
        self.assertNotIn("Discovered Bluetooth Devices", area_tracking_view)
        self.assertNotIn('id="ble-adopt-table-box"', area_tracking_view)
        self.assertNotIn("d.has_ble", area_tracking_view)
        for expected_snippet in (
            'id: "card-area-presence"',
            'store.t("card.area_presence_sensors")',
            "area-presence-box",
            'class="area-box-title"',
            'class="area-box-badges"',
            'id: "card-ble-calibration"',
            'store.t("card.ble_calibration")',
            'id="ble-calibrate-target-box"',
            "calibrate-target-box",
            "handoff-active",
            'id="ble-calibrate-handoff-banner"',
            'id="ble-survey-device-picker"',
            'id="ble-calibrate-area-select"',
            'id="btn-capture-area-signature"',
            "proxy-trim-details",
            'id="card-advanced-ble-settings"',
            'store.t("card.advanced_ble")',
        ):
            self.assertIn(expected_snippet, area_tracking_view)
        self.assertEqual(en_json["card.area_presence_sensors"], "Area presence & sensors")
        self.assertEqual(en_json["card.ble_calibration"], "Walk-around BLE calibration")
        self.assertLess(
            area_tracking_view.index('class="area-box-head"'),
            area_tracking_view.index('class="area-box-badges"'),
        )
        self.assertLess(
            area_tracking_view.index('class="area-box-actions"'),
            area_tracking_view.index('class="area-box-badges"'),
        )
        adv_ble_order = (
            "sys-ble_away_timeout_s",
            "sys-ble_max_radius_m",
            "sys-ble_max_velocity_mps",
            "sys-ble_attenuation",
        )
        for sys_ble_id in adv_ble_order:
            self.assertIn(sys_ble_id, area_tracking_view)
        self.assertLess(
            area_tracking_view.index('id: "card-ble-calibration"'),
            area_tracking_view.index('id="card-advanced-ble-settings"'),
        )
        area_cols = area_tracking_view.split('<div class="column">')
        self.assertEqual(len(area_cols), 3)
        area_col_1, area_col_2 = area_cols[1], area_cols[2]
        self.assertIn('id: "card-area-presence"', area_col_1)
        self.assertNotIn('id="card-advanced-ble-settings"', area_col_1)
        self.assertIn('id: "card-ble-calibration"', area_col_2)
        self.assertIn('id="card-advanced-ble-settings"', area_col_2)
        for earlier_id, later_id in itertools.pairwise(adv_ble_order):
            self.assertLess(
                area_tracking_view.index(f'id="{earlier_id}"'),
                area_tracking_view.index(f'id="{later_id}"'),
            )

        tools, sys_tools, groups_sec, overview, display_view, interface_view, remotes_view, shared_entities = (
            section("tools"),
            section("system_tools"),
            section("system_sync"),
            section("dashboard"),
            section("display"),
            section("interface"),
            section("remotes"),
            section("shared_entities"),
        )
        for key in ("card.diagnostics", "card.replace_hardware", "card.danger_zone"):
            self.assertIn(f'store.t("{key}")', tools)
        self.assertIn('id="diag-node-name"', tools)
        self.assertIn('id="diag-sdk-rev"', tools)
        self.assertIn('store.t("card.developer_telemetry")', tools)
        self.assertIn('id="btn-tools-open-in-ha"', tools)
        self.assertEqual(en_json["action.open_in_ha"], "Open in Home Assistant")
        self.assertNotIn("All Entities", js)
        self.assertNotIn("entitySearchQuery", js)
        for key in (
            "card.notifications_announcements",
            "card.backup_restore",
            "card.system_device_logs",
            "card.support_diagnostics",
        ):
            self.assertIn(f'store.t("{key}")', sys_tools)
        self.assertIn('id: "card-support-diagnostics"', sys_tools)
        for key in (
            "card.home_hub_weather",
            "card.calendars",
            "card.cameras_doorbell",
            "card.custom_colors",
        ):
            self.assertIn(f'store.t("{key}")', shared_entities)
        self.assertNotIn("card-system-wallpapers", shared_entities)
        photos_view = section("photos")
        self.assertIn('id: "card-photo-library"', photos_view)
        self.assertIn('store.t("card.photo_library")', photos_view)
        self.assertIn('id="btn-photos-upload"', photos_view)
        self.assertIn('id="btn-photos-import-media"', photos_view)
        self.assertIn('class="hub-domain-box"', shared_entities)
        display_key_order = (
            'store.t("card.screensaver")',
            'store.t("dev_display.card_voice_assistant")',
            'store.t("card.brightness")',
            'store.t("card.colors")',
            'store.t("card.wallpapers")',
        )
        for snippet in display_key_order:
            self.assertIn(snippet, display_view)
        for earlier, later in itertools.pairwise(display_key_order):
            self.assertLess(display_view.index(earlier), display_view.index(later))
        for retired_display_card in (
            "card.home_screen_appearance",
            "card.music_appearance",
            "card.clock",
        ):
            self.assertNotIn(retired_display_card, display_view)
            self.assertNotIn(retired_display_card, en_json)
        self.assertIn('id="wp-weather-override-note"', display_view)
        self.assertIn('store.t("dev_display.bedtime_brightness_override_note")', display_view)
        self.assertIn('store.t("card.home_screen")', interface_view)
        self.assertIn('store.t("card.app_dock")', interface_view)
        self.assertNotIn("card-single-app-mode", interface_view)
        self.assertNotIn("btn-configure-locked-app", interface_view)
        self.assertIn('id="dock-shortcuts-container"', interface_view)
        self.assertIn('id="dock-hidden-native-apps"', interface_view)
        self.assertIn('id="btn-configure-start-screen"', interface_view)
        self.assertIn('id="latter-app-config-modal"', js)
        self.assertIn('id: "home-categories-pills"', js)
        self.assertIn('id: "area-categories-pills"', js)
        self.assertIn('id: "tools-items-pills"', js)
        self.assertIn('id: "games-items-pills"', js)
        for retired_music_pref in (
            'id: "media-player-shortcuts"',
            "show_speaker_shortcut",
            "show_library_shortcut",
        ):
            self.assertNotIn(retired_music_pref, js)
        self.assertIn('id: "cfg-device_remote_group"', js)
        audio_view = section("audio_voice")
        self.assertIn('store.t("dev_audio.card_sound_playback")', audio_view)
        for key in ("card.remote_controls", "card.volume_overrides", "card.remote_groups"):
            self.assertIn(f'store.t("{key}")', remotes_view)
        self.assertNotIn('id="device-remote-assignments-list"', remotes_view)
        self.assertIn('id: "card-device-groups"', groups_sec)
        self.assertIn('id="btn-open-create-group"', groups_sec)
        self.assertIn('id="create-group-form"', groups_sec)
        self.assertIn('id="group-box-custom"', groups_sec)
        self.assertIn('id="btn-batch-reset"', js)
        self.assertIn('id="btn-batch-apply"', js)
        self.assertIn('id="latter-save-group-modal"', js)
        for retired_group_ui in (
            "batch-latter-behavior-list",
            "group_sync_status",
            "Portable Carry",
            "Tabletop Dock",
            "trait:roaming",
            "trait:stationary",
        ):
            self.assertNotIn(retired_group_ui, js)
        self.assertIn('"pocket_carry"', js)
        self.assertIn('id="btn-choose-wallpaper"', display_view)
        self.assertIn('id="btn-manage-photo-library"', display_view)
        self.assertIn('id="btn-photos-upload"', photos_view)
        self.assertIn('id="st-status-chip"', overview)
        self.assertIn('class="status-tiles"', overview)
        self.assertIn('id: "card-device-assignments"', overview)
        self.assertIn('id="btn-configure-remote-group"', overview)
        self.assertIn("renderQuickActionGrid(", overview)
        self.assertIn('id="cfg-device_group"', overview)
        overview_cols = overview.split('<div class="column">')
        self.assertEqual(len(overview_cols), 3)
        overview_col_1, overview_col_2 = overview_cols[1], overview_cols[2]
        self.assertIn('id="st-status-chip"', overview_col_1)
        self.assertIn("renderQuickActionGrid(", overview_col_1)
        self.assertNotIn('id: "card-device-assignments"', overview_col_1)
        self.assertIn('id: "card-device-assignments"', overview_col_2)
        self.assertIn('id: "card-device-timers-alarms"', overview_col_2)
        self.assertIn('id="overview-ringing-alert"', overview_col_2)
        self.assertIn('id="btn-dismiss-ringing"', overview_col_2)
        self.assertIn('id="btn-cancel-timer"', overview_col_2)
        self.assertIn('id="btn-reset-stopwatch"', overview_col_2)
        self.assertIn('id="overview-alarms-drawer"', overview_col_2)
        self.assertIn('id="overview-alarms"', overview_col_2)
        self.assertNotIn("renderQuickActionGrid(", overview_col_2)
        self.assertLess(
            overview.index('id="cfg-device_group"'),
            overview.index('id: "cfg-assigned_person"'),
        )
        self.assertIn('id="cfg-ble_category"', overview)
        self.assertLess(
            overview.index('id="cfg-ble_category"'),
            overview.index('id: "cfg-assigned_person"'),
        )
        self.assertIn('id="ble-transmitter-off-banner"', overview)
        self.assertIn('id="btn-save-custom-group"', overview)
        self.assertIn('id="btn-manage-groups"', overview)
        self.assertIn('id="btn-open-in-ha"', overview)
        self.assertLess(
            overview.index('id: "card-device-status"'),
            overview.index('id: "card-device-quick-actions"'),
        )
        self.assertLess(
            overview.index('id: "card-device-quick-actions"'),
            overview.rindex('id="btn-open-in-ha"'),
        )

        sys_overview = section("system_overview")
        self.assertNotIn("Configured Items", sys_overview)
        for sys_ov_snippet in (
            'id="sys-issues-banner"',
            'id="sys-discovered-banner"',
            'id: "card-system-status"',
            'id="sys-status-chip"',
            'id="sys-tile-devices"',
            'id="sys-tile-areas"',
            'id="sys-tile-roaming"',
            'id="sys-tile-release"',
            'id: "card-area-deployment"',
            'id: "card-system-capabilities"',
            'id="cap-home-hub"',
            'id="cap-cameras-calendars"',
            'id="cap-media-remotes"',
            'id="cap-device-groups"',
            'id="cap-photo-library"',
            'id="cap-custom-colors"',
            'id="cap-perimeter-security"',
        ):
            self.assertIn(sys_ov_snippet, sys_overview)
        presence_view = section("presence")
        self.assertIn('id="cfg-ble_target_address"', presence_view)
        self.assertIn('id="cfg-ble_ref_power"', presence_view)
        self.assertIn('id="ble-companion-power-tip"', presence_view)
        for gone in ("In Home Assistant</h3>", "Location &amp; BLE</h3>", 'id="cfg-device_slug"', 'id="st-group"'):
            self.assertNotIn(gone, js)
        self.assertNotIn('"count": len(', (LATTER_DIR / "areas.py").read_text(encoding="utf-8"))

    def test_entity_only_cards_hide_when_empty(self) -> None:
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        start = js.index('<section id="view-power"')
        power = js[start:js.index("</section>", start)]
        self.assertEqual(power.count('<div class="card" data-entity-card>'), 2)
        self.assertIn("sleepItems.length", power)
        self.assertIn("batteryItems.length", power)

    def test_home_sun_and_moon_switches_in_home_section(self) -> None:
        self.assertEqual(
            entity_sections.classify_esphome_entity_section(
                "switch.pocket_home_sun", "Home: Sun", "switch", "", "config"
            ),
            ("other", None),
        )
        self.assertEqual(
            entity_sections.classify_esphome_entity_section(
                "switch.pocket_home_moon", "Home: Moon", "switch", "", "config"
            ),
            ("other", None),
        )
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn('"weather_background"', js)
        self.assertIn('"home_sun"', js)
        self.assertIn('"home_moon"', js)
        self.assertNotIn("Area Cards Per Page", js)
        self.assertNotIn("cfg-default_page_size", js)
        disp_fn_start = js.index("function renderDeviceDisplayView(")
        disp_view = js[disp_fn_start:js.index("</section>", disp_fn_start)]
        self.assertNotIn("weather-celestial-bodies", disp_view)
        self.assertIn('id="wp-weather-override-note"', disp_view)
        start = js.index('<section id="view-interface"')
        view = js[start:js.index("</section>", start)]
        self.assertIn('store.t("card.home_screen")', view)
        self.assertIn('store.t("card.app_dock")', view)
        self.assertIn('id: "weather-celestial-bodies"', view)
        self.assertIn('id: "weather-celestial-pills"', view)
        self.assertIn('id="dock-shortcuts-container"', view)
        self.assertIn('id="dock-hidden-native-apps"', view)
        self.assertIn('id: "pinned-shortcuts-container"', js)
        self.assertIn('id: "area-categories-pills"', js)
        self.assertNotIn('id="embedded-area-ui"', view)
        self.assertNotIn('id="embedded-home"', view)

    def test_sidebar_icon_module(self) -> None:
        panel_src = (LATTER_DIR / "studio" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('SIDEBAR_ICON = "latter:logo"', panel_src)
        self.assertIn('SIDEBAR_ICON_FALLBACK = "mdi:ladder"', panel_src)
        self.assertIn("sidebar_icon=sidebar_icon,", panel_src)
        self.assertIn('ICONS_MODULE = "latter-icons.js"', panel_src)
        self.assertIn('icon_url = f"{versioned_prefix}/{ICONS_MODULE}?v={icon_digest}"', panel_src)
        self.assertIn("frontend.add_extra_js_url(hass, icon_url)", panel_src)
        self.assertIn("frontend.remove_extra_js_url(hass, icon_url)", panel_src)
        self.assertIn("str(frontend_dir),", panel_src)
        self.assertNotIn("/latter_static", panel_src)
        module = LATTER_DIR / "frontend" / "latter-icons.js"
        src = module.read_text(encoding="utf-8")
        self.assertLess(len(src.encode("utf-8")), 1500)
        self.assertIn("window.customIcons.latter = {", src)
        self.assertIn('getIcon: async () => ({ path: LATTER_LOGO_PATH, viewBox: "0 0 24 24" }),', src)
        self.assertNotIn("import ", src)
        self.assertNotIn("fetch(", src)
        self.assertNotIn("secondaryPath", src)
        self.assertNotRegex(src, r"#[0-9a-fA-F]{3,6}\b|rgb\(|fill")
        for gone in ("LatterSidebarIconJsView", "sidebar_icon.js", "API_SIDEBAR_ICON_JS_PATH"):
            for path in LATTER_DIR.rglob("*.py"):
                self.assertNotIn(gone, path.read_text(encoding="utf-8"), f"{gone} in {path.name}")
        studio_js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertNotIn("brand-logo", studio_js)

    def test_brand_images_are_valid_png(self) -> None:
        sizes = {}
        for name in (
            "icon.png",
            "icon@2x.png",
            "dark_icon.png",
            "dark_icon@2x.png",
            "logo.png",
            "logo@2x.png",
            "dark_logo.png",
            "dark_logo@2x.png",
        ):
            data = (LATTER_DIR / "brand" / name).read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"), name)
            self.assertNotIn(b"\xef\xbf\xbd", data[:64], name)
            self.assertEqual(data[25], 6, f"{name} must be RGBA (color type 6) with transparent background")
            sizes[name] = int.from_bytes(data[16:20], "big")
        self.assertEqual((sizes["icon.png"], sizes["icon@2x.png"]), (256, 512))
        self.assertEqual((sizes["dark_icon.png"], sizes["dark_icon@2x.png"]), (256, 512))
        self.assertEqual((sizes["logo.png"], sizes["logo@2x.png"]), (256, 512))
        self.assertEqual((sizes["dark_logo.png"], sizes["dark_logo@2x.png"]), (256, 512))

    def test_native_popups_follow_ha_dark_mode(self) -> None:
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn('this.toggleAttribute("dark",', js)
        self.assertRegex(js, r"color-scheme:\s*light")
        self.assertIn(":host([dark])", js)
        self.assertRegex(js, r"background-color:\s*var\(--studio-popup-bg\);\s*color:\s*var\(--studio-text\)")

    def test_columns_everywhere(self) -> None:
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertNotIn("grid-2", js)
        for view in (
            "system_overview", "shared_entities", "remotes", "system_sync", "area_tracking", "system_tools",
            "dashboard", "display", "interface", "audio_voice", "power", "presence", "tools",
        ):
            start = js.index(f'<section id="view-{view}"')
            body = js[start:js.index("</section>", start)]
            self.assertEqual(body.count('<div class="columns">'), 1, view)
            self.assertEqual(body.count('<div class="column">'), 2, view)


class TestActivityCard(unittest.TestCase):
    """The Home Activity Card: a Device setting, carried as area_context.activity_card / activity_sources."""

    def setUp(self) -> None:
        self.policy = activity_policy

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
        self.assertEqual((fields["activity_card"]["index"], fields["activity_card"]["type"]), (31, "bool"))
        self.assertEqual((fields["activity_sources"]["index"], fields["activity_sources"]["type"]), (32, "csv"))
        self.assertIn("activity_card", settings.DEVICE_BOOL_KEYS)
        self.assertIn("activity_sources", settings.DEVICE_TEXT_KEYS)
        self.assertNotIn(
            "activity_card",
            groups.reset_subentry_data({"activity_card": False}, {}, groups.DEVICE_IDENTITY_KEYS),
        )
        self.assertIn("activity_card", backup.DEVICE_CONFIG_EXPORT_KEYS)
        self.assertIn("activity_sources", backup.DEVICE_CONFIG_EXPORT_KEYS)
        self.assertIn("activity_sources", groups.GROUP_APPEARANCE_DEVICE_KEYS)
        ctx_src = (LATTER_DIR / "areas.py").read_text(encoding="utf-8")
        self.assertIn("*activity_payload(", ctx_src)
        self.assertIn("coordinator.activity_card_enabled, coordinator.activity_sources_csv", ctx_src)

    def test_studio_rows(self) -> None:
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        fn_start = js.index("function renderDeviceInterfaceView(")
        view = js[js.index('<section id="view-interface"', fn_start):js.index("</section>", fn_start)]
        self.assertNotIn('<h3 class="card-title">Activity Card</h3>', view)
        self.assertLess(
            view.index('store.t("card.home_screen")'),
            view.index('id: "cfg-activity_card"'),
        )
        self.assertLess(
            view.index('id: "cfg-activity_card"'),
            view.index('store.t("card.app_dock")'),
        )
        self.assertIn('id: "activity-sources-pills"', view)
        self.assertIn("store.entity.toggleActivitySource(", view)
        self.assertIn("store.entity.reorderActivitySources(", view)
        for label in ("Calendar", "Music Queue", "Stopwatch", "Alarms", "Timers"):
            self.assertIn(f'label: "{label}"', js)


class TestShortcutPolicy(unittest.TestCase):
    """dock_items and pinned_items share one Universal Shortcut Engine across Protocol v3, HA, and Studio."""

    def test_normalize_dock_and_pinned_lists(self) -> None:
        dock_out = settings.normalize_dock_items(
            [
                {"kind": "route", "target": "app:pinned"},
                {"kind": "route", "target": "weather:moon", "label": "Moon Phase"},
                {"kind": "route", "target": "settings:root"},
                {"kind": "entity", "target": "scene.evening", "action": "turn_on"},
            ]
        )
        self.assertEqual([it["target"] for it in dock_out], ["app:pinned", "weather:moon", "scene.evening"])
        self.assertTrue(dock_out[2]["confirm"])

        pinned_out = settings.normalize_pinned_items(
            [
                {"kind": "route", "target": "time:stopwatch"},
                {"kind": "route", "target": "music:album_tracks"},
                {"kind": "route", "target": "music:lyrics"},
                {"kind": "route", "target": "music:info"},
                {"kind": "entity", "target": "script.baby_help", "action": "turn_on", "label": "Baby Help"},
            ]
        )
        self.assertEqual(
            [it["target"] for it in pinned_out],
            ["time:stopwatch", "music:album_tracks", "music:lyrics", "music:info", "script.baby_help"],
        )
        self.assertFalse(pinned_out[-1]["confirm"])

        for bad_pinned in (
            [{"kind": "route", "target": "app:pinned"}],
            [{"kind": "route", "target": "not:a_route"}],
            [{"kind": "entity", "target": "lock.front", "action": "toggle"}],
        ):
            with self.assertRaises(ValueError):
                settings.normalize_pinned_items(bad_pinned, strict=True)

    def test_one_default_and_route_catalog_in_both_repos(self) -> None:
        protocol_json = json.loads((LATTER_DIR / "protocol_v3.json").read_text(encoding="utf-8"))
        default_routes = protocol_json["defaults"]["dock_routes"]
        self.assertEqual(settings.DEFAULT_DOCK_ROUTES, default_routes)
        const_src = (LATTER_DIR / "const.py").read_text(encoding="utf-8")
        self.assertIn(f'DEFAULT_DOCK_ROUTES: Final = "{default_routes}"\n', const_src)
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        for route in protocol_json["catalogs"]["shortcut_routes"]:
            self.assertIn(f'token: "{route["token"]}"', js)
        for music_tok, music_lbl in (
            ("music:album_tracks", "Album Tracks"),
            ("music:lyrics", "Music Lyrics"),
            ("music:info", "Track Info"),
        ):
            self.assertEqual(settings.SHORTCUT_ROUTE_MAP[music_tok]["label"], music_lbl)
            self.assertIn(f'token: "{music_tok}", label: "{music_lbl}"', js)
        self.assertEqual(
            protocol_json["ha_services"]["shortcut_action"]["fields"],
            ["target_device", "entity_id", "action", "code"],
        )
        for key in ("dock_items", "pinned_items"):
            self.assertIn(key, settings.DEVICE_SETTING_KEYS)
            self.assertIn(key, groups.GROUP_APPEARANCE_DEVICE_KEYS)
            self.assertIn(key, backup.DEVICE_CONFIG_EXPORT_KEYS)
        self.assertNotIn("dock_apps", (LATTER_DIR / "coordinator.py").read_text(encoding="utf-8"))
        self.assertNotIn("set_dock_apps", (LATTER_DIR / "services.py").read_text(encoding="utf-8"))

    def test_media_handoff_is_one_latter_setting(self) -> None:
        protocol_json = json.loads((LATTER_DIR / "protocol_v3.json").read_text(encoding="utf-8"))
        for svc in ("set_active_area", "area_browse"):
            self.assertNotIn("handoff_media", protocol_json["ha_services"][svc]["fields"])
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
        self.assertIsNone(issue_ids.parse_device_issue_id("device_crashed_01JGONE", subs))
        self.assertIsNone(issue_ids.parse_device_issue_id("something_else", subs))

    def test_kinds_match_the_repair_translations(self) -> None:
        strings = json.loads((LATTER_DIR / "strings.json").read_text(encoding="utf-8"))
        en_json = json.loads((LATTER_DIR / "studio" / "locales" / "en.json").read_text(encoding="utf-8"))
        self.assertTrue(set(issue_ids.DEVICE_ISSUE_KINDS) <= set(strings["issues"]))
        js = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
        self.assertIn("localizeRepairIssue", js)
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
        panel_src = (LATTER_DIR / "studio" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn('latter-studio.js?v={js_digest}"', panel_src)
        self.assertIn("def content_digest(", panel_src)
        self.assertIn("cache_headers=True,", panel_src)
        self.assertIn("config_panel_domain=DOMAIN,", panel_src)
        self.assertIn('domain_data.pop("_registered_panel_url", None)', panel_src)
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
        self.assertTrue(set(settings.DEVICE_SETTING_KEYS) <= conf_values)
        self.assertTrue(set(settings.SYSTEM_SETTING_KEYS) <= set(self.GLOBAL_KEYS))
        self.assertFalse(set(settings.DEVICE_SETTING_KEYS) & set(self.GLOBAL_KEYS))
        self.assertNotIn("companion_base_url", self.GLOBAL_KEYS)
        seeded = dict.fromkeys(settings.DEVICE_SETTING_KEYS, "custom")
        after_reset = reset_policy.reset_subentry_data(seeded, {}, reset_policy.DEVICE_IDENTITY_KEYS)
        self.assertTrue(set(after_reset) <= set(reset_policy.DEVICE_IDENTITY_KEYS))

    def test_each_save_rejects_the_other_scope(self) -> None:
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_system_settings({"weather_entity": "weather.home", "device_group": "x"})
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"default_area": "kitchen", "weather_entity": "weather.home"})
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
        self.assertNotIn("camera_entity", out)
        self.assertEqual(out["volume_overrides"], [{"speaker": "media_player.a", "target": "number.b"}])
        self.assertEqual(out["doorbell_noise_reduction"], "strong")
        self.assertEqual(out["custom_palettes"], [{"name": "#00FF88", "hex": "#00FF88"}])
        self.assertEqual(out["remote_groups"], [{"id": "rg_1", "name": "rg_1", "area_id": "", "remotes": ["remote.tv"]}])
        self.assertEqual(settings.clean_system_settings({"custom_palettes": []}), {"custom_palettes": []})
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
        self.assertEqual(settings.clean_device_settings({"device_custom_color": "#3898ff"}), {"device_custom_color": "#3898FF"})
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
        self.assertEqual(settings.clean_device_settings({"ble_ref_power": ""}), {"ble_ref_power": None})
        self.assertEqual(settings.clean_device_settings({"ble_ref_power": None}), {"ble_ref_power": None})
        self.assertEqual(settings.clean_device_settings({"ble_ref_power": -95}), {"ble_ref_power": -90})
        self.assertEqual(settings.clean_device_settings({"ble_ref_power": -20}), {"ble_ref_power": -30})
        self.assertEqual(settings.clean_device_settings({"ble_ref_power": "-51"}), {"ble_ref_power": -51})
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"ble_ref_power": "loud"})
        self.assertEqual(settings.clean_device_settings({"ble_category": ""}), {"ble_category": "auto"})
        self.assertEqual(settings.clean_device_settings({"ble_category": " Phone "}), {"ble_category": "phone"})
        self.assertEqual(settings.clean_device_settings({"ble_category": "BLE_TAG"}), {"ble_category": "ble_tag"})
        self.assertIn("ble_category", backup.DEVICE_CONFIG_EXPORT_KEYS)
        with self.assertRaises(settings.SettingsScopeError):
            settings.clean_device_settings({"ble_category": "laptop"})

    def test_voice_follows_me_dwell_is_a_device_setting(self) -> None:
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
        view = settings.system_settings_view({"camera_entities": ["camera.door"], "weather_entity": "weather.home"})
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
        with self.assertRaises(scope.TargetNotAllowed):
            scope.checked_entity_verb({"action": "toggle"}, scope.SYSTEM_ENTITY_VERBS)
        self.assertEqual(scope.checked_entity_verb({"option": "Analog"}, scope.SYSTEM_ENTITY_VERBS), "")
        self.assertEqual(scope.checked_entity_verb({"level": 40}, scope.SYSTEM_ENTITY_VERBS), "")


if __name__ == "__main__":
    unittest.main()
