"""Standalone tests for Latter Studio: payload diet, Lit view architecture, and Activity Card."""

from __future__ import annotations

import itertools
import json
import re
from types import SimpleNamespace
import unittest

from custom_components.latter import (
    backup,
    const as latter_const,
    protocol_policy,
    protocol_specs,
)
from custom_components.latter.groups import (
    device_groups,
    esphome_inspector as entity_sections,
)
from custom_components.latter.studio import (
    settings_cleaners as settings,
    state_gates as scope,
)
from tests.conftest import LATTER_DIR, REPO_ROOT, read_py_tree

FRONTEND_SRC_DIR = REPO_ROOT / "frontend_src" / "src"

activity_policy = SimpleNamespace(**(vars(protocol_specs) | vars(protocol_policy)))
groups = SimpleNamespace(**(vars(device_groups) | vars(entity_sections)))
catalog_gate = scope


def _read_frontend_ts(*rel_paths: str) -> str:
    """Read canonical Studio TypeScript source files under `frontend_src/src/` (excluding `.d.ts`)."""
    targets = rel_paths or ("",)
    chunks: list[str] = []
    for rel in targets:
        target = FRONTEND_SRC_DIR / rel if rel else FRONTEND_SRC_DIR
        if target.is_file():
            chunks.append(target.read_text(encoding="utf-8"))
        elif target.is_dir():
            chunks.extend(
                path.read_text(encoding="utf-8")
                for path in sorted(target.rglob("*.ts"))
                if not path.name.endswith(".d.ts")
            )
    return "\n".join(chunks)


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
        payload_src = read_py_tree("studio/payload.py")
        self.assertIn('    if include_catalog:\n        base["catalog"]', payload_src)
        cmds = read_py_tree(
            "studio/commands.py",
            "studio/system_commands.py",
            "studio/device_commands.py",
        )
        self.assertIn("include_catalog=catalog_gate.take()", cmds)
        for event in ("EVENT_ENTITY_REGISTRY_UPDATED", "EVENT_DEVICE_REGISTRY_UPDATED", "EVENT_AREA_REGISTRY_UPDATED"):
            self.assertIn(event, cmds)
        self.assertGreaterEqual(cmds.count("include_catalog=False"), 3)
        self.assertIn("_track_coordinators()", cmds)
        self.assertIn("_track_device_states()", cmds)
        self.assertIn("_cmd_set_device_photo_pool(", cmds)
        views_src = read_py_tree("http")
        self.assertIn("esphome_inspector", payload_src)
        self.assertNotIn("LatterBrandIconView", views_src)
        studio_bundle = LATTER_DIR / "frontend" / "latter-studio.js"
        self.assertTrue(studio_bundle.is_file())
        self.assertGreater(studio_bundle.stat().st_size, 0)
        self.assertTrue(studio_bundle.with_name("latter-studio.js.gz").is_file())
        self.assertTrue((LATTER_DIR / "frontend" / "latter-studio-mdi.js").is_file())
        self.assertTrue((LATTER_DIR / "frontend" / "latter-studio-mdi.js.gz").is_file())
        ts_src = _read_frontend_ts()
        self.assertIn(".catalog", ts_src)

    def test_doorbell_detail_is_rendered(self) -> None:
        payload_src = read_py_tree("studio/payload.py")
        cmds_src = read_py_tree(
            "studio/commands.py",
            "studio/system_commands.py",
            "studio/device_commands.py",
        )
        self.assertNotIn("_build_doorbells", payload_src)
        self.assertNotIn('"preview_url":', payload_src)
        self.assertIn('"mint_camera_preview_url"', cmds_src)
        self.assertIn("resolve_camera_capabilities(", payload_src)
        ts_src = _read_frontend_ts()
        self.assertNotIn(".doorbells", ts_src)
        self.assertNotIn("doorbell-status-list", ts_src)
        self.assertIn("sortable-row-stacked", ts_src)
        # Stage 6 encapsulation: zero window.* globals!
        self.assertNotIn("window.fmtPercent", ts_src)
        self.assertNotIn("dialog-title danger", ts_src)
        self.assertNotIn("onAssignedPersonChanged", ts_src)

    def test_status_card_renders_its_fields(self) -> None:
        payload_src = read_py_tree("studio/payload.py")
        en_json = json.loads((LATTER_DIR / "studio" / "locales" / "en.json").read_text(encoding="utf-8"))
        self.assertIn('"core_rev": str(coordinator.hardware_manifest.get("core_rev") or ""),', payload_src)
        self.assertIn('"firmware_outdated": bool(coordinator.firmware_outdated),', payload_src)
        self.assertNotIn("_build_now_playing", payload_src)
        ts_src = _read_frontend_ts()
        self.assertEqual(en_json["card.status"], "Status")
        self.assertEqual(ts_src.count('store.t("card.status")'), 2)
        self.assertIn('id="diag-core-rev"', ts_src)
        self.assertIn('class="status-tiles"', ts_src)
        self.assertRegex(ts_src, r"@container\s*\(max-width:\s*420px\)")
        self.assertRegex(ts_src, r"@container\s*\(max-width:\s*260px\)")
        self.assertNotIn("status-assignments", ts_src)
        for gone in (
            'class="stat-grid"',
            'id="dash-sdk-rev"',
            'id="dash-node-name"',
            "<span>Now Playing</span>",
            '<h3 class="card-title">Now</h3>',
            '<h3 class="card-title">Device Status</h3>',
        ):
            self.assertNotIn(gone, ts_src)


class TestViewLayout(unittest.TestCase):
    """D-014 & D-061: every view is two independent column stacks with HA Sentence-case titles."""

    def test_view_names_are_unqualified(self) -> None:
        ts_src = _read_frontend_ts()
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
        self.assertNotRegex(ts_src, r"<span>(System|Device) (Overview|Settings)</span>")

    def test_information_architecture(self) -> None:
        ts_src = _read_frontend_ts()
        views_ts = _read_frontend_ts("views")
        en_json = json.loads((LATTER_DIR / "studio" / "locales" / "en.json").read_text(encoding="utf-8"))
        self.assertIn('dashboard: "overview"', ts_src)
        self.assertIn('display: "display"', ts_src)
        self.assertIn('interface: "interface"', ts_src)
        self.assertIn('system_sync: "groups"', ts_src)
        self.assertIn('area_tracking: "presence"', ts_src)
        self.assertIn('system_tools: "tools"', ts_src)
        self.assertNotIn("nav-esp-badge", ts_src)
        self.assertNotIn("set_device_remote_group", ts_src)
        self.assertNotIn("assignDeviceRemoteGroup", ts_src)
        self.assertEqual(ts_src.count('class="nav-badge"'), 2)
        self.assertIn('href="/latter/devices"', ts_src)
        self.assertIn('href="/latter/devices/discovered"', ts_src)
        self.assertEqual(en_json["nav.managed"], "Managed")
        self.assertEqual(en_json["nav.discovered"], "Discovered")
        self.assertEqual(en_json["nav.back_managed"], "← Managed")
        self.assertNotIn("<span>&larr; All Devices</span>", ts_src)

        view_fns: dict[str, str] = {}
        for path in sorted((FRONTEND_SRC_DIR / "views").rglob("*.ts")):
            if path.name.endswith(".d.ts"):
                continue
            src = path.read_text(encoding="utf-8")
            for m in re.finditer(
                r"(?:^|\n)(?:export\s+)?function (render\w+)\([\s\S]*?\n\}(?=\n|\Z)",
                src,
            ):
                view_fns[m.group(1)] = m.group(0)
            for m in re.finditer(
                r"(?:^|\n)  const (render\w+) = \([\s\S]*?\n  \};(?=\n|\Z)",
                src,
            ):
                view_fns.setdefault(m.group(1), m.group(0))

        def section(view: str) -> str:
            start = views_ts.index(f'<section id="view-{view}"')
            out = views_ts[start:views_ts.index("</section>", start)]
            expanded: set[str] = set()
            for _ in range(3):
                out = re.sub(
                    r"\b(render\w+)\b",
                    lambda m: (
                        f"{view_fns[m.group(1)]}\n{m.group(0)}"
                        if m.group(1) in view_fns and m.group(1) not in expanded and (expanded.add(m.group(1)) or True)
                        else m.group(0)
                    ),
                    out,
                )
            return out

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
        self.assertIn("c.is_tracker", ts_src)
        self.assertNotIn("TRACKER_KIND_TOKENS", ts_src)
        self.assertIn("ignoreDiscoveredDevice", discovered_view)
        self.assertIn("unignoreDiscoveredDevice", discovered_view)
        self.assertEqual(latter_const.STUDIO_REV, 52)
        self.assertNotIn("hold_crown_power_off", ts_src)
        self.assertIn(f"const STUDIO_REV = {latter_const.STUDIO_REV};", ts_src)
        self.assertIn(".card.handoff-active", ts_src)
        self.assertIn(".area-presence-box.handoff-active", ts_src)
        self.assertIn(".calibrate-target-box.handoff-active", ts_src)
        self.assertNotIn("border:2px solid var(--studio-warning)", ts_src)
        self.assertIn("cfg-home_show_time", ts_src)
        self.assertIn("cfg-home_show_date", ts_src)
        self.assertIn("cfg-home_show_weather", ts_src)
        self.assertIn("cfg-home_weather_tap_action", ts_src)
        self.assertIn("cfg-home_show_battery", ts_src)
        self.assertIn("cfg-home_date_tap_action", ts_src)
        self.assertIn("cfg-calendar_lookahead_days", ts_src)
        self.assertIn("cfg-calendar_week_start", ts_src)
        self.assertNotIn("tools:calendar", ts_src)
        self.assertNotIn("Power Profile", ts_src)
        self.assertNotIn("fusion-area", ts_src)
        self.assertNotIn("d.has_ble ||", ts_src)
        self.assertNotIn(".area-presence-box.occupied", ts_src)
        self.assertNotIn('? " occupied"', area_tracking_view)
        self.assertNotIn('id="ble-proxy-trim-drawer"', ts_src)
        self.assertNotIn("proxyTrimOpen", ts_src)
        self.assertGreaterEqual(ts_src.count('d.ble_tracked || d.kind === "ble_tag"'), 2)
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
        self.assertIn('id="diag-core-rev"', tools)
        self.assertIn('store.t("card.developer_telemetry")', tools)
        self.assertIn('id="btn-tools-open-in-ha"', tools)
        self.assertEqual(en_json["action.open_in_ha"], "Open in Home Assistant")
        self.assertNotIn("All Entities", ts_src)
        self.assertNotIn("entitySearchQuery", ts_src)
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
        self.assertIn('id="latter-app-config-modal"', ts_src)
        self.assertIn('id: "home-categories-pills"', ts_src)
        self.assertIn('id: "area-categories-pills"', ts_src)
        self.assertIn('id: "tools-items-pills"', ts_src)
        self.assertIn('id: "games-items-pills"', ts_src)
        for retired_music_pref in (
            'id: "media-player-shortcuts"',
            "show_speaker_shortcut",
            "show_library_shortcut",
        ):
            self.assertNotIn(retired_music_pref, ts_src)
        self.assertIn('id: "cfg-device_remote_group"', ts_src)
        audio_view = section("audio_voice")
        self.assertIn('store.t("dev_audio.card_sound_playback")', audio_view)
        for key in ("card.remote_controls", "card.volume_overrides", "card.remote_groups"):
            self.assertIn(f'store.t("{key}")', remotes_view)
        self.assertNotIn('id="device-remote-assignments-list"', remotes_view)
        self.assertIn('id: "card-device-groups"', groups_sec)
        self.assertIn('id="btn-open-create-group"', groups_sec)
        self.assertIn('id="create-group-form"', groups_sec)
        self.assertIn('id="group-box-custom"', groups_sec)
        self.assertIn('id="btn-batch-reset"', ts_src)
        self.assertIn('id="btn-batch-apply"', ts_src)
        self.assertIn('id="latter-save-group-modal"', ts_src)
        for retired_group_ui in (
            "batch-latter-behavior-list",
            "group_sync_status",
            "Portable Carry",
            "Tabletop Dock",
            "trait:roaming",
            "trait:stationary",
        ):
            self.assertNotIn(retired_group_ui, ts_src)
        self.assertIn('"pocket_carry"', ts_src)
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
        self.assertNotIn('id: "card-system-capabilities"', sys_overview)
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
        ):
            self.assertIn(sys_ov_snippet, sys_overview)
        presence_view = section("presence")
        self.assertIn('id="cfg-ble_target_address"', presence_view)
        self.assertIn('id="cfg-ble_ref_power"', presence_view)
        self.assertIn('id="ble-companion-power-tip"', presence_view)
        for gone in ("In Home Assistant</h3>", "Location &amp; BLE</h3>", 'id="cfg-device_slug"', 'id="st-group"'):
            self.assertNotIn(gone, ts_src)
        self.assertNotIn('"count": len(', read_py_tree("areas"))

    def test_entity_only_cards_hide_when_empty(self) -> None:
        power_src = _read_frontend_ts("views/device-power-view.ts")
        start = power_src.index('<section id="view-power"')
        power = power_src[start:power_src.index("</section>", start)]
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
        ts_src = _read_frontend_ts()
        self.assertIn('"weather_background"', ts_src)
        self.assertIn('"home_sun"', ts_src)
        self.assertIn('"home_moon"', ts_src)
        self.assertNotIn("Area Cards Per Page", ts_src)
        self.assertNotIn("cfg-default_page_size", ts_src)
        disp_src = _read_frontend_ts("views/device-display-view.ts")
        disp_fn_start = disp_src.index("function renderDeviceDisplayView(")
        disp_view = disp_src[disp_fn_start:disp_src.index("</section>", disp_fn_start)]
        self.assertNotIn("weather-celestial-bodies", disp_view)
        self.assertIn('id="wp-weather-override-note"', disp_view)
        iface_src = _read_frontend_ts("views/device-interface-view.ts")
        start = iface_src.index('<section id="view-interface"')
        view = iface_src[start:iface_src.index("</section>", start)]
        self.assertIn('store.t("card.home_screen")', view)
        self.assertIn('store.t("card.app_dock")', view)
        self.assertIn('id: "weather-celestial-bodies"', view)
        self.assertIn('id: "weather-celestial-pills"', view)
        self.assertIn('id="dock-shortcuts-container"', view)
        self.assertIn('id="dock-hidden-native-apps"', view)
        self.assertIn('id="pinned-grid-canvas"', ts_src)
        self.assertIn('id: "area-categories-pills"', ts_src)
        self.assertNotIn('id="embedded-area-ui"', view)
        self.assertNotIn('id="embedded-home"', view)

    def test_sidebar_icon_module(self) -> None:
        panel_src = read_py_tree("studio/panel.py")
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
        self.assertNotIn("brand-logo", _read_frontend_ts())
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
        ts_src = _read_frontend_ts()
        self.assertIn('this.toggleAttribute("dark",', ts_src)
        self.assertRegex(ts_src, r"color-scheme:\s*light")
        self.assertIn(":host([dark])", ts_src)
        self.assertRegex(ts_src, r"background-color:\s*var\(--studio-popup-bg\);\s*color:\s*var\(--studio-text\)")

    def test_columns_everywhere(self) -> None:
        ts_src = _read_frontend_ts()
        views_ts = _read_frontend_ts("views")
        self.assertNotIn("grid-2", ts_src)
        for view in (
            "system_overview", "shared_entities", "remotes", "system_sync", "area_tracking", "system_tools",
            "dashboard", "display", "interface", "audio_voice", "power", "presence", "tools",
        ):
            start = views_ts.index(f'<section id="view-{view}"')
            body = views_ts[start:views_ts.index("</section>", start)]
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
        ctx_src = read_py_tree("areas")
        self.assertIn("*activity_payload(", ctx_src)
        self.assertIn("coordinator.activity_card_enabled, coordinator.activity_sources_csv", ctx_src)

    def test_studio_rows(self) -> None:
        ts_src = _read_frontend_ts()
        iface_src = _read_frontend_ts("views/device-interface-view.ts")
        fn_start = iface_src.index("function renderDeviceInterfaceView(")
        view = iface_src[iface_src.index('<section id="view-interface"', fn_start):iface_src.index("</section>", fn_start)]
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
            self.assertIn(f'label: "{label}"', ts_src)


class TestSectionTokenGateAndMemo(unittest.TestCase):
    """Pure-Python unit tests for O(1) SectionTokenGate, slim command skips, and SharedSystemMemo."""

    def _make_snap(self, **overrides: object) -> catalog_gate.SubscriptionTokenSnapshot:
        base: dict[str, object] = {
            "wallpaper_token": 1,
            "hmac_secret": b"secret_a",
            "utc_day": 20000,
            "system_config_rev": 3,
            "subentry_id": "sub_a",
            "device_config_rev": 5,
            "active_wallpaper_id": "preset:ocean_waves",
            "display_shape": "circle",
            "language": "en",
            "locales_loaded": True,
            "registry_rev": 0,
            "ble_dirty_rev": 0,
            "coordinator_ids": ("sub_a",),
            "controls_signature": (("sub_a", 5, True, True, True, "preset:ocean_waves"),),
        }
        base.update(overrides)
        return catalog_gate.SubscriptionTokenSnapshot(**base)  # type: ignore[arg-type]

    def test_section_token_gate_invalidation_and_skip_matrix(self) -> None:
        gate = catalog_gate.SectionTokenGate()
        snap0 = self._make_snap()
        init_payload: dict[str, list[object]] = {
            k: [] for k in catalog_gate.HEAVY_SUBSCRIPTION_SECTIONS
        }
        gate.record_initial(snap0, init_payload)

        # Unchanged snapshot skips every heavy section before build
        self.assertEqual(
            gate.compute_skip_sections(snap0),
            set(catalog_gate.HEAVY_SUBSCRIPTION_SECTIONS),
        )

        # UTC day rollover & HMAC rotation invalidate only signed wallpaper catalogs
        for changed in (self._make_snap(utc_day=20001), self._make_snap(hmac_secret=b"secret_b")):
            skip = gate.compute_skip_sections(changed)
            self.assertNotIn("system_wallpapers", skip)
            self.assertNotIn("wallpapers", skip)
            self.assertIn("photo_collections", skip)
            self.assertIn("locale_strings", skip)
            self.assertIn("pref_specs", skip)
            self.assertIn("world_clock_zones", skip)

        # Wallpaper snapshot token invalidates photo/wallpaper/controls only
        wp_skip = gate.compute_skip_sections(self._make_snap(wallpaper_token=2))
        for dirty in ("photo_collections", "system_wallpapers", "wallpapers", "system_controls"):
            self.assertNotIn(dirty, wp_skip)
        for clean in ("discovered_ble_devices", "ble_area_signatures", "locale_strings"):
            self.assertIn(clean, wp_skip)

        # Selected subentry / device rev / active wallpaper / shape changes invalidate wallpapers
        for changed in (
            self._make_snap(subentry_id="sub_b"),
            self._make_snap(device_config_rev=6),
            self._make_snap(active_wallpaper_id="preset:mars_crater"),
            self._make_snap(display_shape="square"),
        ):
            self.assertNotIn("wallpapers", gate.compute_skip_sections(changed))

        # Language or locale load flip invalidates locale_strings only
        lang_skip = gate.compute_skip_sections(self._make_snap(language="es"))
        self.assertNotIn("locale_strings", lang_skip)
        self.assertIn("wallpapers", lang_skip)

        # Commit records newly built sections so subsequent identical push skips them again
        gate.commit(self._make_snap(language="es"), lang_skip, payload_keys=("locale_strings",))
        self.assertIn("locale_strings", gate.compute_skip_sections(self._make_snap(language="es")))

        # mark_dirty clears selective and all tokens
        gate.mark_dirty("system_controls")
        self.assertFalse(gate.has_sent("system_controls"))
        self.assertTrue(gate.has_sent("locale_strings"))
        gate.mark_dirty()
        self.assertEqual(gate.compute_skip_sections(snap0), set())

    def test_command_response_skip_sections_and_shared_memo(self) -> None:
        from custom_components.latter.studio import commands as studio_cmds

        # Non-wallpaper device config save skips wallpapers + unrelated heavy sections, keeps system_controls
        skip_plain = studio_cmds._command_response_skip_sections(
            "save_device_config", {"config": {"backlight": 80}}
        )
        self.assertNotIn("system_controls", skip_plain)
        self.assertIn("wallpapers", skip_plain)
        self.assertIn("system_wallpapers", skip_plain)
        self.assertIn("discovered_ble_devices", skip_plain)
        self.assertIn("locale_strings", skip_plain)

        # Wallpaper or group device config save keeps wallpapers + system_controls
        for key in ("wallpaper_source", "device_group", "wallpaper_favorites"):
            skip_wp = studio_cmds._command_response_skip_sections(
                "save_device_config", {"config": {key: "val"}}
            )
            self.assertNotIn("wallpapers", skip_wp)
            self.assertNotIn("system_controls", skip_wp)

        # Signature & photo commands keep only their mutated sections
        self.assertNotIn(
            "ble_area_signatures",
            studio_cmds._command_response_skip_sections("capture_ble_area_signature", {}),
        )
        del_skip = studio_cmds._command_response_skip_sections("delete_photo", {})
        for kept in ("photo_collections", "system_wallpapers", "wallpapers", "system_controls"):
            self.assertNotIn(kept, del_skip)
        self.assertIn("discovered_ble_devices", del_skip)

        # SharedSystemMemo deduplicates identical event objects across concurrent tabs and respects TTL
        memo = studio_cmds._SharedSystemMemo()
        ev = object()
        memo.record_registry_event(ev)
        memo.record_registry_event(ev)
        self.assertEqual(memo.registry_rev, 1)
        self.assertEqual(memo.ble_dirty_rev, 1)

        studio_cmds._memo_put(memo.system_cache, ("k",), 100.0, {"ok": True})
        hit = studio_cmds._memo_get(memo.system_cache, ("k",), 100.02)
        self.assertEqual(hit, {"ok": True})
        self.assertIsNone(studio_cmds._memo_get(memo.system_cache, ("k",), 100.10))
        memo.invalidate_if_populated()
        self.assertEqual(memo.system_cache, {})
        self.assertGreaterEqual(memo.generation, 2)


if __name__ == "__main__":
    unittest.main()
