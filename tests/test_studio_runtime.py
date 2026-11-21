"""Studio runtime behavior verified directly against TypeScript ESM modules via Node 24's native TS loader."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import unittest

from custom_components.latter import groups as entity_sections

REPO_ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"
FRONTEND_DIR = REPO_ROOT / "frontend_src"
FRONTEND_SRC = FRONTEND_DIR / "src"
STUDIO_JS = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _run_node_esm(module_js: str) -> object:
    """Execute an ESM snippet against real TypeScript Studio modules via `node-ts-loader.mjs`."""
    out = subprocess.run(
        [
            NODE,
            "--no-warnings",
            "--import",
            "./src/lib/node-ts-loader.mjs",
            "--input-type=module",
            "-",
        ],
        cwd=FRONTEND_DIR,
        input=module_js,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if out.returncode != 0:
        raise RuntimeError(f"Node ESM execution failed ({out.returncode}):\n{out.stderr}\n{out.stdout}")
    return json.loads(out.stdout)


@unittest.skipUnless(NODE, "node is not installed")
class TestEntityLabels(unittest.TestCase):
    """D-061: labels from entity names use HA Sentence case while preserving acronyms & parenthesized units."""

    def test_entity_label_sentence_case(self) -> None:
        cases = {
            "Wake word": "Wake word",
            "Wake word 2": "Wake word 2",
            "Finished speaking detection": "Finished speaking detection",
            "Assist satellite": "Assist satellite",
            "wifi signal": "Wi-Fi signal",
            "BLE presence beacon": "BLE presence beacon",
            "iBeacon uuid": "iBeacon UUID",
            "Ram low water": "RAM low water",
            "Latency (ms)": "Latency (ms)",
            "Signal (dBm)": "Signal (dBm)",
            "ESPHome node": "ESPHome node",
            "security pin": "Security PIN",
        }
        got = _run_node_esm(
            f"""
            import {{ entityLabel }} from "./src/utils/format.js";
            const inputs = {json.dumps(list(cases))};
            process.stdout.write(JSON.stringify(inputs.map(entityLabel)));
            """
        )
        self.assertEqual(dict(zip(cases, got, strict=True)), cases)

    def test_every_entity_label_goes_through_it(self) -> None:
        controls_ts = (FRONTEND_SRC / "components" / "controls.ts").read_text(encoding="utf-8")
        shared_ts = (FRONTEND_SRC / "views" / "system-shared-view.ts").read_text(encoding="utf-8")
        self.assertIn("entityLabel(", controls_ts)
        self.assertIn("entityLabel(", shared_ts)
        self.assertIn("entityLabel(", STUDIO_JS)
        self.assertNotIn("window.entityLabel", STUDIO_JS)


@unittest.skipUnless(NODE, "node is not installed")
class TestLiveConditionalRows(unittest.TestCase):
    """A Device entity change shows at once and survives payloads that still carry the old state."""

    def test_pending_state_overlay(self) -> None:
        got = _run_node_esm(
            """
            import { overlayPendingEntityStates } from "./src/state/entity-controller.js";

            const pending = new Map();
            const payload = (state) => ({
              esphome: { sections: [{ id: "voice", title: "voice", items: [{ entity_id: "select.x_wake_word_mode", domain: "select", name: "Wake word mode", state }] }] },
            });
            const out = {};
            pending.set("select.x_wake_word_mode", { state: "Always On", expires: Date.now() + 5000 });
            let p = payload("Disabled");
            overlayPendingEntityStates(p, pending);
            out.staleAnswer = p.esphome.sections[0].items[0].state;
            out.stillPending = pending.size;

            p = payload("Always On");
            overlayPendingEntityStates(p, pending);
            out.confirmed = p.esphome.sections[0].items[0].state;
            out.clearedAfterConfirm = pending.size;

            pending.set("number.x_volume", { state: "70", expires: Date.now() + 5000 });
            p = { esphome: { sections: [{ id: "sound", title: "sound", items: [{ entity_id: "number.x_volume", domain: "number", name: "Volume", state: "70.0" }] }] } };
            overlayPendingEntityStates(p, pending);
            out.numericMatch = pending.size;

            pending.set("select.x_wake_word_mode", { state: "Always On", expires: Date.now() - 1 });
            p = payload("Disabled");
            overlayPendingEntityStates(p, pending);
            out.expired = [p.esphome.sections[0].items[0].state, pending.size];

            process.stdout.write(JSON.stringify(out));
            """
        )
        self.assertEqual(
            got,
            {
                "staleAnswer": "Always On",
                "stillPending": 1,
                "confirmed": "Always On",
                "clearedAfterConfirm": 0,
                "numericMatch": 0,
                "expired": ["Disabled", 0],
            },
        )

    def test_wiring(self) -> None:
        self.assertIn("overlayPendingEntityStates(", STUDIO_JS)
        self.assertIn("executeEntityAction(", STUDIO_JS)
        cmds = (LATTER_DIR / "studio" / "commands.py").read_text(encoding="utf-8")
        self.assertRegex(
            cmds,
            r"async_track_state_change_event\(\s*hass,\s*entity_ids,\s*_entity_changed\s*\)",
        )
        self.assertIn("_track_device_states()", cmds)


class TestEntitySections(unittest.TestCase):
    """Which Studio section a Device entity lands in."""

    def classify(self, entity_id: str, name: str, domain: str = "select", key: str | None = None) -> str:
        return entity_sections.classify_esphome_entity_section(
            entity_id,
            name,
            domain,
            "",
            "config",
            translation_key=key,
            device_object_prefixes=("latter_desk_display", "desk_display"),
        )[0]

    def test_assist_satellite_entities_are_voice(self) -> None:
        self.assertEqual(self.classify("select.desk_display_assistant", "Assistant", key="pipeline"), "voice")
        self.assertEqual(
            self.classify(
                "select.desk_display_finished_speaking_detection",
                "Finished speaking detection",
                key="vad_sensitivity",
            ),
            "voice",
        )
        self.assertEqual(self.classify("select.desk_display_wake_word", "Wake word", key="wake_word"), "voice")
        self.assertEqual(self.classify("select.desk_display_wake_word_2", "Wake word 2", key="wake_word_n"), "voice")
        self.assertEqual(
            self.classify(
                "assist_satellite.desk_display_assist_satellite",
                "Assist satellite",
                domain="assist_satellite",
            ),
            "voice",
        )

    def test_device_prefix_never_decides(self) -> None:
        self.assertEqual(self.classify("switch.desk_display_mute", "Mute", domain="switch"), "other")
        self.assertEqual(self.classify("select.desk_display_voice_visual_profile", "Voice: Visual Profile"), "other")
        self.assertEqual(self.classify("select.desk_display_display_clock_face", "Display: Clock Face"), "other")

    def test_desk_power_and_battery_page_regression(self) -> None:
        desk = [
            ("select.desk_assistant_sleep_wake_battery_screen_timeout", "Sleep & Wake: Battery Screen Timeout"),
            ("select.desk_assistant_sleep_wake_docked_idle_timeout", "Sleep & Wake: Docked Idle Timeout"),
            ("select.desk_assistant_sleep_wake_pickup_to_wake", "Sleep & Wake: Pickup to Wake"),
            ("select.desk_assistant_sleep_wake_power_profile", "Sleep & Wake: Power Profile"),
            ("select.desk_assistant_sleep_wake_screensaver_style", "Sleep & Wake: Screensaver Style"),
            ("switch.desk_assistant_sleep_wake_docked_screensaver", "Sleep & Wake: Docked Screensaver"),
        ]
        sections: dict[str, list[dict]] = {}
        for ent, name in desk:
            sec = entity_sections.classify_esphome_entity_section(
                ent, name, ent.split(".")[0], "", "config", device_object_prefixes=("desk_assistant",)
            )[0]
            sections.setdefault(sec, []).append({"entity_id": ent})
        payload_sections = [{"id": sid, "title": sid, "items": items} for sid, items in sections.items()]
        self.assertEqual(set(sections), {"other", "battery"})
        self.assertEqual(entity_sections.present_section_ids(payload_sections), {"other", "battery"})
        self.assertEqual(entity_sections.present_section_ids([{"id": "battery", "items": []}, "junk"]), set())
        payload_src = (LATTER_DIR / "studio" / "payload.py").read_text(encoding="utf-8")
        self.assertIn('sec_ids = present_section_ids(esphome_inspector.get("sections"))', payload_src)
        self.assertIn('"has_power": ("sleep" in sec_ids) or ("battery" in sec_ids),', payload_src)
        self.assertNotIn('s.get("count"', payload_src)

    def test_ha_wake_word_is_the_one_wake_word_control(self) -> None:
        self.assertNotIn("active_wake", STUDIO_JS)
        self.assertNotIn("active wake", STUDIO_JS)
        audio_ts = (FRONTEND_SRC / "views" / "device-audio-view.ts").read_text(encoding="utf-8")
        self.assertIn('it.key === "wake_word"', audio_ts)
        self.assertIn('it.key === "wake_word_n"', audio_ts)

    def test_quick_action_buttons_always_classify_as_actions(self) -> None:
        cases = [
            ("button.desk_display_actions_find_my_device", "Actions: Find My Device"),
            ("button.desk_display_actions_trigger_voice_assistant", "Actions: Trigger Voice Assistant"),
            ("button.desk_display_actions_activate_screensaver", "Actions: Activate Screensaver"),
            ("button.desk_display_actions_hibernate_device", "Actions: Hibernate Device"),
            ("button.desk_display_actions_restart_device", "Actions: Restart Device"),
            ("button.desk_display_ble_find_my_device", "BLE: Find My Device"),
            ("button.desk_display_voice_trigger_voice_assistant", "Voice: Trigger Voice Assistant"),
            ("button.desk_display_sleep_wake_activate_screensaver", "Sleep & Wake: Activate Screensaver"),
            ("button.desk_display_sleep_wake_hibernate_device", "Sleep & Wake: Hibernate Device"),
            ("button.desk_display_system_restart_device", "System: Restart Device"),
            ("button.desk_display_find_my_device", "Find My Device"),
            ("button.desk_display_restart", "Restart"),
        ]
        for ent_id, friendly in cases:
            with self.subTest(entity_id=ent_id, friendly=friendly):
                self.assertEqual(self.classify(ent_id, friendly, domain="button"), "actions")
        self.assertEqual(
            entity_sections.classify_esphome_entity_section(
                "button.desk_display_system_log_memory_report",
                "System: Log Memory Report",
                "button",
                "",
                "diagnostic",
                device_object_prefixes=("desk_display",),
            )[0],
            "developer",
        )
        self.assertEqual(
            self.classify("select.desk_display_developer_weather_simulation", "Developer: Weather Simulation"),
            "developer",
        )
        self.assertEqual(
            self.classify("switch.desk_display_system_telemetry_profiler", "System: Telemetry Profiler", domain="switch"),
            "developer",
        )
        self.assertEqual(
            entity_sections.classify_esphome_entity_section(
                "sensor.desk_display_system_internal_ram_low_water",
                "System: Internal RAM Low Water",
                "sensor",
                "",
                "diagnostic",
                device_object_prefixes=("desk_display",),
            )[0],
            "developer",
        )
        self.assertEqual(
            entity_sections.classify_esphome_entity_section(
                "sensor.desk_display_timer_remaining",
                "Timer Remaining",
                "sensor",
                "",
                "diagnostic",
                device_object_prefixes=("desk_display",),
            )[0],
            "network",
        )
        self.assertEqual(
            self.classify("select.desk_display_area_ble_presence_beacon_mode", "Area: BLE Presence Beacon Mode"),
            "other",
        )


@unittest.skipUnless(NODE, "node is not installed")
class TestQuickActionsControls(unittest.TestCase):
    """Stateless HA button entities (`state === 'unknown'`) render enabled unless offline (`forceDisabled`)."""

    def test_quick_action_ordering_unknown_state_and_offline_disable(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToContainer } from "./test/fake-store.js";
            import {
              renderNativeControlRow,
              renderQuickActionGrid,
              sortQuickActionButtons,
            } from "./src/components/controls.js";

            const shuffled = [
              { entity_id: "button.pocket_assistant_actions_restart_device", domain: "button", name: "Restart Device", state: "unknown" },
              { entity_id: "button.pocket_assistant_actions_hibernate_device", domain: "button", name: "Hibernate Device", state: "unknown" },
              { entity_id: "button.pocket_assistant_actions_activate_screensaver", domain: "button", name: "Activate Screensaver", state: "unavailable" },
              { entity_id: "button.pocket_assistant_actions_trigger_voice_assistant", domain: "button", name: "Trigger Voice Assistant", state: "unknown" },
              { entity_id: "button.pocket_assistant_actions_find_my_device", domain: "button", name: "Find My Device", state: "2026-11-12T18:00:00+00:00" },
            ];
            const sorted = sortQuickActionButtons(shuffled);
            const { store } = makeFakeStore();
            const calls = [];
            store.entity.espAction = async (eid, action, _opt, toast) => {
              calls.push({ eid, action, toast });
              return true;
            };

            const gridEl = renderToContainer(renderQuickActionGrid(store, shuffled));
            const btns = gridEl.querySelectorAll("button");
            const gridStates = btns.map((b) => ({
              disabled: b.disabled,
              svgHtml: b.querySelector("svg")?.outerHTML || "",
              label: b.textContent.trim(),
            }));
            btns[0].click();
            btns[2].click(); // disabled -> no-op
            btns[3].click();
            btns[4].click();

            const offlineGridEl = renderToContainer(renderQuickActionGrid(store, shuffled, true));
            const allDisabledOffline = offlineGridEl.querySelectorAll("button").every((b) => b.disabled);

            const rowUnknown = renderToContainer(renderNativeControlRow(store, {
              entity_id: "button.pocket_system_log_memory_report",
              domain: "button",
              name: "Log Memory Report",
              state: "unknown",
            }));
            const rowUnavail = renderToContainer(renderNativeControlRow(store, {
              entity_id: "button.pocket_system_log_memory_report",
              domain: "button",
              name: "Log Memory Report",
              state: "unavailable",
            }));
            const swUnknown = renderToContainer(renderNativeControlRow(store, {
              entity_id: "switch.pocket_home_sun",
              domain: "switch",
              name: "Sun",
              state: "unknown",
            }));

            process.stdout.write(JSON.stringify({
              sortedIds: sorted.map((it) => it.entity_id),
              gridStates,
              calls,
              allDisabledOffline,
              rowButtonUnknownDisabled: rowUnknown.querySelector("button")?.disabled,
              rowButtonUnavailDisabled: rowUnavail.querySelector("button")?.disabled,
              switchUnknownDisabled: swUnknown.querySelector("input")?.disabled,
            }));
            """
        )
        self.assertEqual(
            got["sortedIds"],
            [
                "button.pocket_assistant_actions_find_my_device",
                "button.pocket_assistant_actions_trigger_voice_assistant",
                "button.pocket_assistant_actions_activate_screensaver",
                "button.pocket_assistant_actions_hibernate_device",
                "button.pocket_assistant_actions_restart_device",
            ],
        )
        self.assertEqual(
            [st["disabled"] for st in got["gridStates"]],
            [False, False, True, False, False],
        )
        self.assertEqual(len({st["svgHtml"] for st in got["gridStates"]}), 5)
        self.assertEqual(len(got["calls"]), 3)
        self.assertEqual(
            [c["eid"] for c in got["calls"]],
            [
                "button.pocket_assistant_actions_find_my_device",
                "button.pocket_assistant_actions_hibernate_device",
                "button.pocket_assistant_actions_restart_device",
            ],
        )
        self.assertTrue(got["allDisabledOffline"])
        self.assertFalse(got["rowButtonUnknownDisabled"])
        self.assertTrue(got["rowButtonUnavailDisabled"])
        self.assertTrue(got["switchUnknownDisabled"])


@unittest.skipUnless(NODE, "node is not installed")
class TestDisplayViewControls(unittest.TestCase):
    """Display, Interface, Audio, Power, Modals, and Remotes render Sentence-case controls & disambiguated headings."""

    def test_sun_moon_pills_disambiguated_headings_and_wallpaper_states(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { renderAppConfigModalBody } from "./src/components/dialogs.js";
            import { renderDeviceAudioView } from "./src/views/device-audio-view.js";
            import { renderDeviceDisplayView } from "./src/views/device-display-view.js";
            import { renderDeviceInterfaceView } from "./src/views/device-interface-view.js";
            import { renderDevicePowerView } from "./src/views/device-power-view.js";
            import { renderSystemRemotesView } from "./src/views/system-remotes-view.js";

            function buildStore({
              weatherBgState = "Dynamic",
              cycleMins = 0,
              activeId = "",
              favIds = [],
              autoBrtState = "Disabled",
              remoteMode = "group:living_tv",
            } = {}) {
              const favSet = new Set(favIds);
              const wallpapers = [
                { id: "preset:forest_mountains", name: "Forest Mountains", kind: "preset", active: activeId === "preset:forest_mountains", favorite: favSet.has("preset:forest_mountains"), deletable: false, thumb_url: "/thumb1" },
                { id: "preset:ocean_waves", name: "Ocean Waves", kind: "preset", active: activeId === "preset:ocean_waves", favorite: favSet.has("preset:ocean_waves"), deletable: false, thumb_url: "/thumb2" },
              ];
              return makeFakeStore({
                activeSubentryId: "sub_1",
                sections: {
                  home: [
                    { entity_id: "switch.pocket_home_wake_greeting", pref_key: "wake_greeting", domain: "switch", name: "Wake greeting", state: "on" },
                    { entity_id: "select.pocket_home_weather_background", pref_key: "weather_background", domain: "select", name: "Weather background", state: weatherBgState, options: ["Disabled", "Dynamic"] },
                    { entity_id: "switch.pocket_home_sun", pref_key: "home_sun", domain: "switch", name: "Sun", state: "on" },
                    { entity_id: "switch.pocket_home_moon", pref_key: "home_moon", domain: "switch", name: "Moon", state: "off" },
                  ],
                  display: [
                    { entity_id: "select.pocket_display_color_profile", pref_key: "color_profile", domain: "select", name: "Color profile", state: "Default", options: ["Default", "Custom"] },
                    { entity_id: "select.pocket_display_clock_face", pref_key: "clock_face", domain: "select", name: "Clock face", state: "Minimal Digital", options: ["Minimal Digital", "Modern Analog"] },
                    { entity_id: "select.pocket_display_time_format", pref_key: "time_format", domain: "select", name: "Time format", state: "12-Hour (AM/PM)", options: ["12-Hour (AM/PM)", "24-Hour"] },
                    { entity_id: "select.pocket_display_start_screen", pref_key: "start_screen", domain: "select", name: "Start screen", state: "Home", options: ["Home", "Area Controls", "Time App"] },
                    { entity_id: "select.pocket_display_auto_brightness_mode", pref_key: "auto_brightness_mode", domain: "select", name: "Auto-brightness", state: autoBrtState, options: ["Disabled", "Sun Synchronized", "Time Schedule"] },
                    { entity_id: "number.pocket_display_manual_brightness", pref_key: "manual_brightness", domain: "number", name: "Manual brightness", state: "80", min: 5, max: 100, step: 1, unit: "%" },
                    { entity_id: "number.pocket_display_day_brightness", pref_key: "day_brightness", domain: "number", name: "Day brightness", state: "90", min: 5, max: 100, step: 1, unit: "%" },
                    { entity_id: "number.pocket_display_night_brightness", pref_key: "night_brightness", domain: "number", name: "Night brightness", state: "25", min: 5, max: 100, step: 1, unit: "%" },
                    { entity_id: "number.pocket_display_day_start_hour", pref_key: "day_start_hour", domain: "number", name: "Day start hour", state: "7", min: 0, max: 23, step: 1, unit: "h" },
                    { entity_id: "number.pocket_display_night_start_hour", pref_key: "night_start_hour", domain: "number", name: "Night start hour", state: "22", min: 0, max: 23, step: 1, unit: "h" },
                  ],
                  sleep: [
                    { entity_id: "select.pocket_sleep_battery_screen_timeout", pref_key: "battery_screen_timeout", domain: "select", name: "Battery screen timeout", state: "30s", options: ["15s", "30s"] },
                    { entity_id: "select.pocket_sleep_screensaver_mode", pref_key: "screensaver_mode", domain: "select", name: "Screensaver mode", state: "Docked Only", options: ["Docked Only", "Always", "Never"] },
                    { entity_id: "select.pocket_sleep_screensaver_style", pref_key: "screensaver_style", domain: "select", name: "Screensaver style", state: "Starfield", options: ["Clock", "Starfield", "Photo Frame"] },
                    { entity_id: "select.pocket_sleep_docked_idle_timeout", pref_key: "docked_idle_timeout", domain: "select", name: "Docked idle timeout", state: "5 min", options: ["1 min", "5 min"] },
                  ],
                  actions: [
                    { entity_id: "button.pocket_actions_activate_screensaver", device_command: "activate_screensaver", domain: "button", name: "Activate screensaver", state: "unknown" },
                  ],
                  battery: [
                    { entity_id: "sensor.pocket_battery_level", domain: "sensor", name: "Battery level", state: "88", unit: "%" },
                  ],
                  music: [
                    { entity_id: "select.pocket_music_overlay_style", pref_key: "music_overlay_style", domain: "select", name: "Overlay style", state: "Art + Metadata", options: ["Art Only", "Art + Metadata"] },
                    { entity_id: "select.pocket_music_album_art_style", pref_key: "music_album_art_style", domain: "select", name: "Album art style", state: "Full Screen", options: ["Full Screen", "Standard"] },
                    { entity_id: "select.pocket_music_album_sort_order", pref_key: "album_sort_order", domain: "select", name: "Album sort order", state: "Alphabetical", options: ["Alphabetical"] },
                    { entity_id: "select.pocket_music_artist_album_sort_order", pref_key: "artist_album_sort_order", domain: "select", name: "Artist album sort order", state: "Oldest on Top", options: ["Oldest on Top", "Newest on Top"] },
                    { entity_id: "select.pocket_music_podcast_sort_order", pref_key: "podcast_sort_order", domain: "select", name: "Podcast sort order", state: "Newest on Top", options: ["Newest on Top"] },
                  ],
                  sound: [
                    { entity_id: "number.pocket_sound_alert_volume", pref_key: "alert_volume", domain: "number", name: "Alert volume", state: "60", min: 0, max: 100, step: 5, unit: "%" },
                  ],
                  voice: [
                    { entity_id: "select.pocket_voice_wake_word_mode", pref_key: "wake_word_mode", domain: "select", name: "Wake word mode", state: "On Device", options: ["Disabled", "On Device"] },
                    { entity_id: "select.pocket_voice_visual_profile", pref_key: "va_visual_profile", domain: "select", name: "Visual profile", state: "Nebula", options: ["Nebula", "Solaris"] },
                    { entity_id: "switch.pocket_voice_wake_screen_on_assist", pref_key: "wake_screen_on_assist", domain: "switch", name: "Wake screen on Assist", state: "on" },
                  ],
                },
                state: {
                  config: {
                    kind: "device",
                    device_slug: "desk_panel",
                    home_screen_enabled: true,
                    activity_card: true,
                    activity_sources: "calendar",
                    wallpaper_mode: activeId ? (cycleMins > 0 && favIds.length > 0 ? "custom" : "single") : "off",
                    wallpaper_source: activeId,
                    wallpaper_favorites: favIds,
                    wallpaper_cycle_minutes: cycleMins,
                    weather_app_background: weatherBgState !== "Disabled",
                    display_shape: "square",
                    area_categories: "scene,light",
                    home_categories: "alarm,thermostat,entry,vacuum",
                    tools_items: "stopwatch,level,flashlight,calculator,dice,coin_flip",
                    games_items: "marbles,archery,bricks,chomp,2048,memory",
                    device_remote_group: remoteMode,
                    native_ble_tracking: true,
                    dock_items: [
                      { kind: "route", target: "app:area", action: "", label: "", icon: "", confirm: false },
                      { kind: "route", target: "app:music", action: "", label: "", icon: "", confirm: false },
                    ],
                    pinned_items: [],
                  },
                  capabilities: { has_display: true, has_audio: true, has_power: true, is_round: true, has_imu: true, is_roaming_device: true },
                  live: { ma_link_matched: true },
                  speaker_volume: { entity_id: "media_player.desk_panel", name: "Speaker volume", domain: "number", volume_pct: 60, state: "60", min: 0, max: 100, step: 5, unit: "%" },
                  system_config: {
                    custom_palettes: [],
                    remotes_list: ["remote.living_tv"],
                    volume_overrides: [],
                    remote_groups: [{ id: "living_tv", name: "Living Area TV", area_id: "living", remotes: ["remote.living_tv"] }],
                  },
                  system_devices: [
                    { subentry_id: "sub_1", title: "Desk Panel", kind: "device", is_online: true, has_display: true, active_area_name: "Office", device_remote_group: remoteMode },
                  ],
                  catalog: { remotes: [{ id: "remote.living_tv", name: "Living TV" }], areas: [], ma_speakers: [] },
                  wallpapers,
                },
              }).store;
            }

            function renderModalApp(app, opts = {}) {
              const s = buildStore(opts);
              s.appConfigModal = { open: true, app };
              return renderToHtml(renderAppConfigModalBody(s));
            }

            process.stdout.write(JSON.stringify({
              offMarkup: renderToHtml(renderDeviceDisplayView(buildStore({ cycleMins: 0, activeId: "", autoBrtState: "Disabled" }))),
              dispWeatherOffStatic: renderToHtml(renderDeviceDisplayView(buildStore({ weatherBgState: "Disabled", cycleMins: 0, activeId: "preset:ocean_waves", autoBrtState: "Disabled" }))),
              staticMarkup: renderToHtml(renderDeviceDisplayView(buildStore({ cycleMins: 0, activeId: "preset:ocean_waves", autoBrtState: "Sun Synchronized" }))),
              rotatingMarkup: renderToHtml(renderDeviceDisplayView(buildStore({ cycleMins: 5, activeId: "preset:ocean_waves", favIds: ["preset:forest_mountains", "preset:ocean_waves"], autoBrtState: "Time Schedule" }))),
              powerMarkup: renderToHtml(renderDevicePowerView(buildStore())),
              audioMarkup: renderToHtml(renderDeviceAudioView(buildStore())),
              ifaceMarkup: renderToHtml(renderDeviceInterfaceView(buildStore())),
              ifaceWeatherOff: renderToHtml(renderDeviceInterfaceView(buildStore({ weatherBgState: "Disabled" }))),
              modalPinnedMarkup: renderModalApp("pinned"),
              modalAreaMarkup: renderModalApp("area"),
              modalTimeMarkup: renderModalApp("time"),
              modalClockMarkup: renderModalApp("clock"),
              modalMusicMarkup: renderModalApp("music"),
              modalRemoteMarkup: renderModalApp("remote", { remoteMode: "group:living_tv" }),
              modalToolsMarkup: renderModalApp("tools"),
              modalGamesMarkup: renderModalApp("games"),
              sysRemotesMarkup: renderToHtml(renderSystemRemotesView(buildStore({ remoteMode: "group:living_tv" }))),
            }));
            """
        )

        # 1. Consolidated Display view headings (`D-069` Sentence case — hardware & surface aesthetics only)
        card_titles = [
            m.strip()
            for m in re.findall(r'<h3 class="card-title">([\s\S]*?)</h3>', got["offMarkup"])
        ]
        self.assertEqual(
            card_titles,
            [
                "Screensaver",
                "Voice assistant",
                "Brightness",
                "Colors",
                "Wallpapers",
            ],
        )

        self.assertNotIn('id="weather-celestial-bodies"', got["offMarkup"])
        self.assertIn("Manual brightness", got["offMarkup"])
        self.assertNotIn("Day brightness", got["offMarkup"])
        self.assertNotIn("Day start hour", got["offMarkup"])

        # Cross-tab Weather background note on Display -> Wallpapers (`D-069` / `D-072`)
        self.assertIn('id="wp-weather-override-note"', got["staticMarkup"])
        self.assertIn("Live weather background is active on Home and Sky &amp; weather", got["staticMarkup"])
        self.assertNotIn('id="wp-weather-override-note"', got["dispWeatherOffStatic"])
        self.assertNotIn('id="wp-weather-override-note"', got["offMarkup"])

        # Power view keeps battery/sleep timeouts and excludes screensavers
        self.assertIn("Battery screen timeout", got["powerMarkup"])
        self.assertNotIn("Screensaver mode", got["powerMarkup"])

        # Interface view: Home screen (with consolidated Home appearance + Time format) + App Dock
        self.assertIn("Home screen", got["ifaceMarkup"])
        self.assertIn("App Dock", got["ifaceMarkup"])
        self.assertIn('id="cfg-time_format"', got["ifaceMarkup"])
        self.assertIn('id="cfg-wake_greeting"', got["ifaceMarkup"])
        self.assertIn('id="cfg-weather_background"', got["ifaceMarkup"])
        self.assertIn('id="weather-celestial-bodies"', got["ifaceMarkup"])
        self.assertNotIn('id="weather-celestial-bodies"', got["ifaceWeatherOff"])
        self.assertIn('id="dock-shortcuts-container"', got["ifaceMarkup"])
        self.assertIn('id="dock-hidden-native-apps"', got["ifaceMarkup"])
        self.assertIn("drag-handle", got["ifaceMarkup"])
        self.assertIn("Add custom shortcut", got["ifaceMarkup"])

        # App config modals (`pinned`, `area`, `time`, `clock`, `music`, `remote`, `tools`, `games`)
        self.assertIn('id="pinned-shortcuts-container"', got["modalPinnedMarkup"])
        self.assertIn('id="area-categories-pills"', got["modalAreaMarkup"])
        self.assertIn('id="cfg-time_format"', got["modalTimeMarkup"])
        self.assertIn('id="cfg-local_clock_label"', got["modalTimeMarkup"])
        self.assertLess(
            got["modalTimeMarkup"].index('id="cfg-time_format"'),
            got["modalTimeMarkup"].index('id="cfg-local_clock_label"'),
        )
        self.assertIn("UTC-12:00", got["modalTimeMarkup"])
        self.assertIn("UTC+14:00", got["modalTimeMarkup"])
        self.assertIn("Clock face", got["modalClockMarkup"])
        self.assertIn('id="cfg-time_format"', got["modalClockMarkup"])
        for music_id in (
            'id="cfg-album_art_style"',
            'id="cfg-music_overlay_style"',
            'id="cfg-album_sort_order"',
            'id="cfg-artist_album_sort_order"',
            'id="cfg-podcast_sort_order"',
        ):
            self.assertIn(music_id, got["modalMusicMarkup"])
        self.assertNotIn("Album sort order", got["audioMarkup"])
        self.assertIn("Sound &amp; playback", got["audioMarkup"])
        self.assertIn("cfg-device_remote_group", got["modalRemoteMarkup"])
        self.assertIn('id="tools-items-pills"', got["modalToolsMarkup"])
        self.assertIn('id="games-items-pills"', got["modalGamesMarkup"])

        # System -> Media & remotes
        for rem_card in ("Remote controls", "Speaker volume overrides", "Remote control groups"):
            self.assertIn(rem_card, got["sysRemotesMarkup"])

        # Static vs rotating wallpaper + Sun Synchronized / Time Schedule brightness
        self.assertIn('id="btn-choose-wallpaper"', got["staticMarkup"])
        self.assertIn('id="btn-turn-off-wp"', got["staticMarkup"])
        self.assertIn('id="btn-manage-photo-library"', got["staticMarkup"])
        self.assertNotIn("Manual brightness", got["staticMarkup"])
        self.assertIn("Day brightness", got["staticMarkup"])
        self.assertNotIn("Day start hour", got["staticMarkup"])

        self.assertIn('id="cfg-wallpaper_cycle_minutes"', got["rotatingMarkup"])
        self.assertIn("Day start hour", got["rotatingMarkup"])
        self.assertIn("Night start hour", got["rotatingMarkup"])


@unittest.skipUnless(NODE, "node is not installed")
class TestWallpaperUploadBearerAuth(unittest.TestCase):
    """D-025: POST /api/latter/wallpaper/upload uses live hass.auth Bearer token, never auth/sign_path."""

    def test_xhr_bearer_header_preflight_refresh_and_401_retry(self) -> None:
        got = _run_node_esm(
            """
            import { StudioWsClient } from "./src/api/ws-client.js";

            const wsCalls = [];
            const xhrLog = [];
            let nextResponses = [];

            globalThis.XMLHttpRequest = class MockXHR {
              constructor() {
                this.headers = {};
                this.upload = {};
                this.status = 0;
                this.response = null;
                this.responseType = "";
              }
              open(method, url) {
                this.method = method;
                this.url = url;
              }
              setRequestHeader(k, v) {
                this.headers[k] = v;
              }
              send(form) {
                const step = nextResponses.shift() || { status: 200, body: { ok: true } };
                xhrLog.push({
                  method: this.method,
                  url: this.url,
                  auth: this.headers.Authorization || "",
                  scope: form.get("scope"),
                  subentryId: form.get("subentry_id"),
                });
                if (this.upload && this.upload.onprogress) {
                  this.upload.onprogress({ lengthComputable: true, loaded: 50, total: 100 });
                }
                this.status = step.status;
                this.response = step.body;
                this.onload();
              }
            };

            let refreshCalls = 0;
            const auth = {
              data: { access_token: "tok_live" },
              expired: false,
              async refreshAccessToken() {
                refreshCalls += 1;
                auth.expired = false;
                auth.data.access_token = `tok_refreshed_${refreshCalls}`;
              },
            };
            const client = new StudioWsClient(() => {});
            client.setHass({
              auth,
              async callWS(msg) {
                wsCalls.push(msg.type);
                throw new Error(`Unexpected WS call: ${msg.type}`);
              },
            });

            const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], "crater.png", { type: "image/png" });
            const progress = [];

            nextResponses = [{ status: 200, body: { ok: true, source_id: "upload:_system/crater_1a2b3c.jpg" } }];
            const sysRes = await client.uploadWallpaperMultipart({
              scope: "system",
              file,
              onProgress: (p) => progress.push(p),
            });

            auth.expired = true;
            nextResponses = [{ status: 200, body: { ok: true, source_id: "upload:desk/crater_1a2b3c.jpg" } }];
            const devRes = await client.uploadWallpaperMultipart({
              scope: "device",
              subentryId: "sub_desk",
              file,
            });

            nextResponses = [
              { status: 401, body: null },
              { status: 200, body: { ok: true, source_id: "upload:_system/retry_ok.jpg" } },
            ];
            const skewRes = await client.uploadWallpaperMultipart({ scope: "system", file });

            nextResponses = [{ status: 401, body: null }, { status: 401, body: null }];
            let persistentErr = "";
            try {
              await client.uploadWallpaperMultipart({ scope: "system", file });
            } catch (err) {
              persistentErr = err.message;
            }

            process.stdout.write(JSON.stringify({
              wsCalls, refreshCalls, progress, sysRes, devRes, skewRes, persistentErr, xhrLog,
            }));
            """
        )
        self.assertEqual(got["wsCalls"], [])
        self.assertEqual(got["refreshCalls"], 3)
        self.assertEqual(got["progress"], [50, 100])
        self.assertEqual(got["sysRes"]["source_id"], "upload:_system/crater_1a2b3c.jpg")
        self.assertEqual(got["devRes"]["source_id"], "upload:desk/crater_1a2b3c.jpg")
        self.assertEqual(got["skewRes"]["source_id"], "upload:_system/retry_ok.jpg")
        self.assertEqual(got["persistentErr"], "Wallpaper upload failed (HTTP 401)")
        self.assertEqual(len(got["xhrLog"]), 6)


@unittest.skipUnless(NODE, "node is not installed")
class TestToolsDiagnosticsView(unittest.TestCase):
    """Device Tools, Overview, Presence, Interface, Discovered, & System Presence views (`D-061`-`D-066`)."""

    def test_standard_diagnostics_parsed_telemetry_and_ble_tag_mode(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { renderDeviceOverviewView } from "./src/views/device-overview-view.js";
            import { renderDeviceToolsView } from "./src/views/device-tools-view.js";

            function buildTools(isBle = false) {
              return makeFakeStore({
                activeSubentryId: "sub_1",
                sections: isBle ? {} : {
                  network: [
                    { entity_id: "update.desk_panel_firmware", domain: "update", name: "Firmware", state: "off" },
                    { entity_id: "sensor.desk_panel_wifi_signal", domain: "sensor", name: "Wi-Fi signal", state: "-54", unit: "dBm" },
                    { entity_id: "sensor.desk_panel_ip_address", domain: "sensor", name: "IP address", state: "192.168.1.44" },
                    { entity_id: "sensor.desk_panel_connected_ssid", domain: "sensor", name: "Connected SSID", state: "HomeLAN" },
                    { entity_id: "sensor.desk_panel_system_rpc_outbox", domain: "sensor", name: "System: RPC Outbox", state: '{"v":3,"cmd":"media_play","seq":99}' },
                    { entity_id: "sensor.desk_panel_system_link_report", domain: "sensor", name: "System: Link Report", state: "up=7320 rst=POWERON bto=1 disc=2 rsn=0 rssi=-55/-62 n=120 wlk=0.0 ls=45 slp=78.5 awk=21.5 api=3 ha=2 gap=14 down=0 nvs=5/0/3" },
                    { entity_id: "sensor.desk_panel_system_hardware_manifest", domain: "sensor", name: "System: Hardware Manifest", state: '{"v":2,"contract":3,"board":"waveshare_s3_square_4_0","w":480,"h":480,"shape":"square","display":1,"touch":1,"audio":1,"mic":1,"spk":1,"imu":1,"battery":0,"stationary":1,"wearable":0,"ips":1,"chip":"ESP32-S3","psram_mb":8,"minor":4}' },
                  ],
                  developer: [
                    { entity_id: "switch.desk_panel_system_telemetry_profiler", domain: "switch", name: "Telemetry profiler", state: "off" },
                    { entity_id: "button.desk_panel_system_log_memory_report", domain: "button", name: "Log memory report", state: "unknown" },
                    { entity_id: "sensor.desk_panel_system_internal_ram_low_water", domain: "sensor", name: "Internal RAM low water", state: "64", unit: "kB" },
                  ],
                },
                state: {
                  title: isBle ? "Keychain Tag" : "Desk Panel",
                  config: isBle
                    ? { kind: "ble_tag", ble_target_address: "AA:BB:CC:11:22:33" }
                    : { kind: "device", device_slug: "desk_panel", security_pin_policy: "auto", has_security_pin: true },
                  live: isBle ? {} : { device_sw_version: "3.0.0", sdk_rev: "2026111801", effective_security_pin_policy: "require_pin" },
                  links: isBle ? { entry_id: "ent_1" } : { entry_id: "ent_1", esphome_device_id: "esp_dev_1", latter_device_id: "lat_dev_1" },
                  esphome: isBle ? {} : { device: { mac: "10:20:30:40:50:60" } },
                  system_devices: [
                    isBle
                      ? { subentry_id: "sub_1", kind: "ble_tag", is_online: true, ble_survey_rows: [{ is_winner: true, effective_rssi: -68 }] }
                      : { subentry_id: "sub_1", kind: "device", is_online: true, model_label: "Latter Square 4.0", wifi_rssi: -54, ip_address: "192.168.1.44" },
                  ],
                },
              }).store;
            }

            function buildOverview(mode) {
              if (mode === "ble") {
                return makeFakeStore({
                  activeSubentryId: "sub_ble",
                  state: {
                    config: { kind: "ble_tag", ble_target_address: "AA:BB:CC:11:22:33" },
                    capabilities: {},
                    live: { active_area_name: "Entryway", ble_closest_proxy: "Entry Proxy" },
                    links: { entry_id: "ent_1" },
                    system_devices: [
                      {
                        subentry_id: "sub_ble",
                        kind: "ble_tag",
                        status_code: "online",
                        status_label: "Detected",
                        has_assigned_area: false,
                        ble_survey_rows: [{ is_winner: true, effective_rssi: -64, distance_m: 1.8 }],
                      },
                    ],
                  },
                }).store;
              }
              const isBattery = mode === "battery";
              const isOffline = mode === "offline";
              return makeFakeStore({
                activeSubentryId: "sub_1",
                sections: isBattery
                  ? { network: [{ entity_id: "update.roaming_pocket_firmware", domain: "update", name: "Firmware", state: "off" }] }
                  : {},
                state: {
                  config: {
                    kind: "device",
                    device_slug: "roaming_pocket",
                    device_group: "handhelds",
                    device_remote_group: isBattery ? "group:living_tv" : "area_auto",
                    native_ble_tracking: isBattery,
                  },
                  capabilities: {
                    has_display: true,
                    has_power: true,
                    has_battery: isBattery,
                    has_ble_beacon: isBattery,
                    is_roaming_device: isBattery,
                  },
                  live: {
                    active_area_name: "Kitchen",
                    ble_closest_proxy: isBattery ? "Kitchen Proxy" : "",
                    device_sw_version: "3.0.0",
                    fw_update_available: mode === "mains",
                  },
                  links: { entry_id: "ent_1", esphome_device_id: "esp_1", latter_device_id: "lat_1" },
                  esphome: { device: { sw_version: "3.0.0", model: "Pocket" } },
                  device_groups: [{ id: "handhelds", name: "Handhelds" }],
                  system_config: {
                    remote_groups: [{ id: "living_tv", name: "Living Area TV", area_id: "living", remotes: ["remote.tv"] }],
                  },
                  system_devices: [
                    {
                      subentry_id: "sub_1",
                      kind: "device",
                      is_online: !isOffline,
                      status_code: isOffline ? "offline" : mode === "mains" ? "update" : "online",
                      status_label: isOffline ? "Offline" : mode === "mains" ? "Update available" : "Online",
                      has_display: true,
                      has_battery: isBattery,
                      has_assigned_area: !isBattery,
                      area_label: "Office",
                      battery_level: isBattery ? 82 : null,
                      is_charging: isBattery,
                      is_usb_connected: isBattery,
                      wifi_rssi: isBattery ? -58 : -84,
                      ip_address: "192.168.1.44",
                      ble_survey_rows: isBattery ? [{ is_winner: true, effective_rssi: -61, distance_m: 2.4 }] : [],
                    },
                  ],
                },
              }).store;
            }

            process.stdout.write(JSON.stringify({
              espMarkup: renderToHtml(renderDeviceToolsView(buildTools(false))),
              bleMarkup: renderToHtml(renderDeviceToolsView(buildTools(true))),
              ovBattery: renderToHtml(renderDeviceOverviewView(buildOverview("battery"))),
              ovMainsUpdate: renderToHtml(renderDeviceOverviewView(buildOverview("mains"))),
              ovOffline: renderToHtml(renderDeviceOverviewView(buildOverview("offline"))),
              ovBle: renderToHtml(renderDeviceOverviewView(buildOverview("ble"))),
            }));
            """
        )

        esp = got["espMarkup"]
        ble = got["bleMarkup"]
        ov_bat = got["ovBattery"]
        ov_mains = got["ovMainsUpdate"]
        ov_offline = got["ovOffline"]
        ov_ble = got["ovBle"]

        self.assertIn("Model", esp)
        self.assertIn("Latter Square 4.0", esp)
        self.assertIn('id="diag-node-name"', esp)
        self.assertIn("desk_panel", esp)
        self.assertIn('id="diag-sdk-rev"', esp)
        self.assertIn("v3.0.0", esp)
        self.assertIn("2026111801", esp)
        self.assertIn("192.168.1.44", esp)
        self.assertIn("10:20:30:40:50:60", esp)
        self.assertIn("HomeLAN", esp)
        self.assertIn("Open in Home Assistant", esp)
        self.assertIn("Reconfigure", esp)
        self.assertNotIn("All Entities", esp)
        self.assertNotIn("media_play", esp)
        self.assertIn("Developer &amp; telemetry", esp)
        self.assertIn("2h 2m", esp)
        self.assertIn("waveshare_s3_square_4_0", esp)
        self.assertIn("ESP32-S3 • 8 MB PSRAM", esp)

        # BLE tag hides Developer & telemetry
        self.assertIn("-68 dBm", ble)
        self.assertIn("AA:BB:CC:11:22:33", ble)
        self.assertNotIn("Developer &amp; telemetry", ble)

        # Overview: Battery (`has_battery=true`) + real `update.*` entity -> "Up to date" + "Open in Home Assistant" (`Q12`)
        for expected in (
            "Online",
            "Current Area",
            "Kitchen",
            "Battery",
            "82%",
            "Charging",
            "Wi-Fi signal",
            "-58 dBm",
            "Firmware",
            "v3.0.0",
            "Up to date",
            "Handhelds",
            "Living Area TV",
            "Open in Home Assistant",
        ):
            self.assertIn(expected, ov_bat)
        self.assertNotIn("Download backup", ov_bat)

        # Plugged-in (`has_battery=false`) shows Power / Plugged in
        for expected in ("Update available", "Office", "Power", "Plugged in", "Follow Area"):
            self.assertIn(expected, ov_mains)

        # Offline Device renders `.offline-banner` (`D-066` / `Q8`)
        self.assertIn("offline-banner", ov_offline)
        self.assertIn("Device is offline or hibernating", ov_offline)

        # BLE Tag Overview hides Quick actions
        for expected in ("Online", "Entryway", "-64 dBm", "AA:BB:CC:11:22:33"):
            self.assertIn(expected, ov_ble)
        self.assertNotIn("Quick actions", ov_ble)

    def test_presence_view_static_assigned_area_vs_ble_roaming_modes(self) -> None:
        """D-032 & D-066: Static mode hides BLE identity & Voice Follows Me while keeping area_handoff visible."""
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { renderDeviceAudioView } from "./src/views/device-audio-view.js";
            import { renderDevicePresenceView } from "./src/views/device-presence-view.js";

            function build(bleTracking) {
              return makeFakeStore({
                activeSubentryId: "sub_1",
                sections: {
                  presence: [
                    { entity_id: "pref:ble_beacon_mode", pref_key: "ble_beacon_mode", domain: "select", name: "BLE beacon mode", state: "Handheld Only", options: ["Handheld Only", "Always"] },
                  ],
                },
                state: {
                  config: {
                    kind: "device",
                    native_ble_tracking: bleTracking,
                    ble_auto_switch: bleTracking,
                    sync_device_area: bleTracking,
                    area_handoff: true,
                    default_area: "living_room",
                    ble_target_address: "",
                    ble_beacon_uuid: "E2C56DB5-DFFB-48D2-B060-D0F5A71096E1",
                  },
                  capabilities: { has_display: true, has_audio: true, is_roaming_device: true },
                  catalog: {
                    areas: [
                      { id: "living_room", name: "Living Room" },
                      { id: "kitchen", name: "Kitchen" },
                    ],
                  },
                },
              }).store;
            }

            const staticStore = build(false);
            const roamingStore = build(true);
            process.stdout.write(JSON.stringify({
              staticPresence: renderToHtml(renderDevicePresenceView(staticStore)),
              roamingPresence: renderToHtml(renderDevicePresenceView(roamingStore)),
              staticAudio: renderToHtml(renderDeviceAudioView(staticStore)),
              roamingAudio: renderToHtml(renderDeviceAudioView(roamingStore)),
            }));
            """
        )
        self.assertIn("Assigned Area", got["staticPresence"])
        self.assertNotIn("card-ble-identity", got["staticPresence"])
        self.assertNotIn("BLE beacon mode", got["staticPresence"])
        self.assertNotIn("Voice Follows Me", got["staticAudio"])
        self.assertIn('id="cfg-area_handoff"', got["staticAudio"])

        self.assertIn("card-ble-identity", got["roamingPresence"])
        self.assertIn("Fallback Area", got["roamingPresence"])
        self.assertNotIn("Assigned Area", got["roamingPresence"])
        self.assertIn("Voice Follows Me", got["roamingAudio"])
        self.assertIn('id="cfg-area_handoff"', got["roamingAudio"])

    def test_interface_view_home_screen_toggle_single_app_and_home_controls(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { START_SCREEN_OPTIONS, RETURN_TO_HOME_TIMEOUT_OPTIONS } from "./src/constants.js";
            import { renderAppConfigModalBody } from "./src/components/dialogs.js";
            import { renderDeviceInterfaceView } from "./src/views/device-interface-view.js";

            function build(homeEnabled, caps = { has_display: true, is_round: true, has_imu: true }, extraCfg = {}) {
              const startVal = extraCfg.start_screen || (homeEnabled ? "Home" : "Time App");
              const clockTapVal = extraCfg.home_clock_tap_action || "Time App";
              return makeFakeStore({
                activeSubentryId: "sub_1",
                devicePrefs: [
                  { key: "home_screen_enabled", label: "Home screen", section: "interface", domain: "switch", value: homeEnabled },
                  { key: "start_screen", label: "Start screen", section: "interface", domain: "select", value: startVal, options: START_SCREEN_OPTIONS },
                  { key: "home_clock_tap_action", label: "Home time tap", section: "interface", domain: "select", value: clockTapVal, options: ["Time App", "Clock Face"] },
                  { key: "return_to_home_timeout", label: "Return to Home timeout", section: "interface", domain: "select", value: "2 min", options: RETURN_TO_HOME_TIMEOUT_OPTIONS },
                ],
                state: {
                  config: {
                    kind: "device",
                    home_screen_enabled: homeEnabled,
                    start_screen: startVal,
                    home_clock_tap_action: clockTapVal,
                    return_to_home_timeout: "2 min",
                    activity_card: true,
                    activity_sources: "calendar,timers",
                    dock_items: [
                      { kind: "route", target: "app:pinned", action: "", label: "", icon: "", confirm: false },
                      { kind: "route", target: "app:music", action: "", label: "", icon: "", confirm: false },
                      { kind: "route", target: "weather:moon", action: "", label: "Moon Phase", icon: "", confirm: false },
                    ],
                    pinned_items: [
                      { kind: "entity", target: "script.baby_help", action: "turn_on", label: "Baby Help", icon: "mdi:baby-face-outline", confirm: false },
                    ],
                    local_clock_label: "Oakland",
                    world_clocks: "Westminster|Europe/London;Kyoto|Asia/Tokyo",
                    home_categories: "alarm,thermostat,entry",
                    area_categories: "scene,light",
                    tools_items: "stopwatch,level,flashlight,calculator,dice,coin_flip",
                    games_items: "marbles,archery,bricks,chomp,2048,memory",
                    device_remote_group: "area_auto",
                    ...extraCfg,
                  },
                  capabilities: caps,
                  system_config: { remote_groups: [] },
                  system_devices: [{ subentry_id: "sub_1", kind: "device", is_online: true, device_remote_group: "area_auto" }],
                },
              }).store;
            }

            function modalHtml(app, caps) {
              const s = build(true, caps);
              s.appConfigModal = { open: true, app };
              return renderToHtml(renderAppConfigModalBody(s));
            }

            process.stdout.write(JSON.stringify({
              enabledMarkup: renderToHtml(renderDeviceInterfaceView(build(true))),
              clockTapFaceRoundMarkup: renderToHtml(renderDeviceInterfaceView(build(true, { has_display: true, is_round: true, has_imu: true }, { home_clock_tap_action: "Clock Face" }))),
              clockTapFaceRectMarkup: renderToHtml(renderDeviceInterfaceView(build(true, { has_display: true, is_round: false, has_imu: false }, { home_clock_tap_action: "Clock Face" }))),
              singleAppMarkup: renderToHtml(renderDeviceInterfaceView(build(false))),
              singleAppClockMarkup: renderToHtml(renderDeviceInterfaceView(build(false, { has_display: true, is_round: true, has_imu: true }, { start_screen: "Clock Face" }))),
              pinnedModalMarkup: modalHtml("pinned"),
              homeHubModalMarkup: modalHtml("home_hub"),
              timeModalMarkup: modalHtml("time"),
              rectWallToolsModalMarkup: modalHtml("tools", { has_display: true, is_round: false, has_imu: false }),
            }));
            """
        )
        self.assertIn("App Dock", got["enabledMarkup"])
        self.assertIn("Moon Phase", got["enabledMarkup"])
        self.assertIn('id="dock-hidden-native-apps"', got["enabledMarkup"])
        self.assertNotIn('id="cfg-clock_face"', got["enabledMarkup"])
        self.assertIn('id="cfg-clock_face"', got["clockTapFaceRoundMarkup"])
        self.assertIn("Modern analog", got["clockTapFaceRoundMarkup"])
        self.assertIn('id="cfg-clock_face"', got["clockTapFaceRectMarkup"])
        self.assertNotIn("Modern analog", got["clockTapFaceRectMarkup"])
        self.assertIn("Baby Help", got["pinnedModalMarkup"])
        self.assertIn('id="world-clocks-list"', got["timeModalMarkup"])
        self.assertNotIn("Analog Chronograph", got["rectWallToolsModalMarkup"])
        self.assertNotIn("Bubble Level", got["rectWallToolsModalMarkup"])
        self.assertIn("Flashlight", got["rectWallToolsModalMarkup"])

        self.assertNotIn("card-single-app-mode", got["singleAppMarkup"])
        self.assertNotIn('id="btn-configure-locked-app"', got["singleAppMarkup"])
        self.assertIn('id="btn-configure-start-screen"', got["singleAppMarkup"])
        self.assertIn('id="cfg-time_format"', got["singleAppMarkup"])
        self.assertNotIn('id="cfg-clock_face"', got["singleAppMarkup"])
        self.assertIn('id="cfg-clock_face"', got["singleAppClockMarkup"])
        self.assertNotIn('id="dock-shortcuts-container"', got["singleAppMarkup"])

    def test_time_card_focus_safe_typing_and_manual_world_clock_add(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { SimEvent } from "./test/dom-shim.js";
            import { makeFakeStore, renderToContainer } from "./test/fake-store.js";
            import { WORLD_CLOCK_ZONES_CATALOG } from "./src/constants.js";
            import { renderAppConfigModalBody } from "./src/components/dialogs.js";
            import { focusSafe, html, render } from "./src/lib/lit.js";
            import { LatterStudio } from "./src/latter-studio.js";

            // 1. focusSafe() preserves focused text input across background updates
            const tplInput = (val) => html`<input id="t" type="text" .value=${focusSafe(val)} />`;
            const box = renderToContainer(tplInput("Init"));
            document.body.appendChild(box);
            const inp = box.querySelector("#t");
            inp.focus();
            inp.value = "M";
            render(tplInput(""), box);
            const preservedWhileFocused = inp.value;
            inp.blur();
            render(tplInput("Synced"), box);
            const updatedAfterBlur = inp.value;

            // 2. ShadowRoot keydown isolation stops HA single-key shortcuts on INPUT
            function runKeyDown(key, opts = {}) {
              let stopped = false;
              const fakeInner = { tagName: opts.tagName || "INPUT" };
              const ev = {
                key,
                ctrlKey: Boolean(opts.ctrlKey),
                metaKey: Boolean(opts.metaKey),
                altKey: Boolean(opts.altKey),
                composedPath: () => [fakeInner],
                stopPropagation() { stopped = true; },
              };
              LatterStudio.prototype._onRootKeyDown.call({}, ev);
              return stopped;
            }

            // 3. World clock manual city label flow
            const { store, toasts } = makeFakeStore({
              activeSubentryId: "sub_1",
              state: {
                config: {
                  kind: "device",
                  local_clock_label: "",
                  world_clocks: "Westminster|Europe/London",
                },
              },
            });
            store.appConfigModal = { open: true, app: "time" };
            const stagedCalls = [];
            store.entity.stageDeviceSetting = (key, val, domId, debounceMs) => {
              stagedCalls.push({ key, val, domId, debounceMs });
              store.state.config[key] = val;
            };

            const modalRoot = renderToContainer(renderAppConfigModalBody(store));
            store.host.renderRoot = modalRoot;

            const localInput = modalRoot.querySelector("#cfg-local_clock_label");
            localInput.value = "Main ";
            localInput.dispatchEvent(new SimEvent("input", { bubbles: true }));
            const localDomDuringTyping = localInput.value;

            const zoneSelect = modalRoot.querySelector("#cfg-world_clocks_add");
            zoneSelect.value = "America/New_York";
            zoneSelect.dispatchEvent(new SimEvent("change", { bubbles: true }));
            const labelAfterZonePick = store.worldClockNewLabel;
            const stagedWorldClocksAfterPick = stagedCalls.filter((c) => c.key === "world_clocks").length;

            modalRoot.querySelector("#btn-world_clock_add").click();
            const toastOnMissingCity = toasts[toasts.length - 1]?.msg || "";

            const newCityInput = modalRoot.querySelector("#cfg-world_clock_new_label");
            newCityInput.value = "Akron, OH";
            newCityInput.dispatchEvent(new SimEvent("input", { bubbles: true }));
            modalRoot.querySelector("#btn-world_clock_add").click();

            process.stdout.write(JSON.stringify({
              preservedWhileFocused,
              updatedAfterBlur,
              stopLetterA: runKeyDown("a"),
              stopLetterC: runKeyDown("c"),
              allowEscape: !runKeyDown("Escape"),
              allowTab: !runKeyDown("Tab"),
              allowCtrlC: !runKeyDown("c", { ctrlKey: true }),
              allowButtonKey: !runKeyDown("c", { tagName: "BUTTON" }),
              firstCatalogZone: WORLD_CLOCK_ZONES_CATALOG[0],
              lastCatalogZone: WORLD_CLOCK_ZONES_CATALOG[WORLD_CLOCK_ZONES_CATALOG.length - 1],
              localDomDuringTyping,
              localStagedCall: stagedCalls[0],
              labelAfterZonePick,
              stagedWorldClocksAfterPick,
              toastOnMissingCity,
              finalWorldClocks: store.state.config.world_clocks,
              clearedDraftLabel: store.worldClockNewLabel,
              clearedDraftZone: store.worldClockNewZone,
            }));
            """
        )
        self.assertEqual(got["preservedWhileFocused"], "M")
        self.assertEqual(got["updatedAfterBlur"], "Synced")
        self.assertTrue(got["stopLetterA"])
        self.assertTrue(got["stopLetterC"])
        self.assertTrue(got["allowEscape"])
        self.assertTrue(got["allowTab"])
        self.assertTrue(got["allowCtrlC"])
        self.assertTrue(got["allowButtonKey"])
        self.assertEqual(got["firstCatalogZone"]["iana"], "Etc/GMT+12")
        self.assertEqual(got["lastCatalogZone"]["iana"], "Pacific/Kiritimati")
        self.assertEqual(got["localDomDuringTyping"], "Main ")
        self.assertEqual(got["localStagedCall"]["key"], "local_clock_label")
        self.assertEqual(got["localStagedCall"]["val"], "Main")
        self.assertEqual(got["labelAfterZonePick"], "")
        self.assertEqual(got["stagedWorldClocksAfterPick"], 0)
        self.assertTrue(got["toastOnMissingCity"])
        self.assertEqual(
            got["finalWorldClocks"],
            "Westminster|Europe/London;Akron, OH|America/New_York",
        )
        self.assertEqual(got["clearedDraftLabel"], "")
        self.assertEqual(got["clearedDraftZone"], "")

    def test_managed_and_discovered_lifecycle_views_and_badge(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { LatterStudio } from "./src/latter-studio.js";
            import { renderDevicesDiscoveredView } from "./src/views/devices-discovered-view.js";
            import { renderDevicesListView } from "./src/views/devices-list-view.js";

            function buildHost(overrides = {}, extraState = {}) {
              const { store } = makeFakeStore({
                currentScope: overrides.currentScope ?? "device",
                currentViewId: overrides.currentViewId ?? "select_device_prompt",
                deviceSelected: overrides.deviceSelected ?? false,
                activeSubentryId: overrides.activeSubentryId ?? "",
                state: {
                  title: "Desk Panel",
                  config: { kind: "device" },
                  device_groups: [
                    { id: "wall_panels", name: "Wall & Desk Panels" },
                    { id: "handhelds", name: "Handhelds" },
                  ],
                  catalog: { persons: [{ id: "person.alex", name: "Alex" }] },
                  system_devices: [
                    {
                      subentry_id: "sub_1",
                      title: "Desk Panel",
                      model_label: "Square 4.0 (480x480)",
                      area_label: "Office",
                      device_group: "wall_panels",
                      device_group_name: "Wall & Desk Panels",
                      status_code: "online",
                      status_label: "Online",
                      is_online: true,
                      is_latter_native: true,
                      has_display: true,
                      is_roaming: false,
                      ble_tracked: false,
                      assigned_person: "",
                      kind: "device",
                    },
                    {
                      subentry_id: "sub_2",
                      title: "Pocket Assistant",
                      model_label: "Pocket 2.06 (410x502)",
                      area_label: "Roaming",
                      device_group: "handhelds",
                      device_group_name: "Handhelds",
                      status_code: "online",
                      status_label: "Online",
                      is_online: true,
                      is_latter_native: true,
                      has_display: true,
                      is_roaming: true,
                      ble_tracked: true,
                      assigned_person: "person.alex",
                      kind: "device",
                    },
                  ],
                  discovered_latter_devices: [],
                  ignored_latter_devices: [],
                  discovered_ble_devices: [
                    {
                      title: "Zoe's Watch",
                      target_address: "device_tracker.watch_ble",
                      kind: "Private BLE (phone or watch)",
                      is_tracker: true,
                      rssi: -58,
                      area_name: "Office",
                    },
                    {
                      title: "Living TV BLE",
                      target_address: "11:22:33:44:55:66",
                      kind: "Named BLE device",
                      is_tracker: false,
                      rssi: -79,
                      area_name: "Living Room",
                    },
                  ],
                  ...extraState,
                },
              });
              if (overrides.deviceCategoryFilter) {
                store.deviceCategoryFilter = overrides.deviceCategoryFilter;
              }
              return { store, el: Object.assign(Object.create(LatterStudio.prototype), { store }) };
            }

            const zero = buildHost();
            const sidebarZeroLatter = renderToHtml(LatterStudio.prototype._renderSidebar.call(zero.el));

            const one = buildHost({}, {
              discovered_latter_devices: [
                {
                  esphome_device_id: "esp_new_1",
                  node_name: "kitchen_panel",
                  title: "Kitchen Panel",
                  model_label: "Square 4.0 (480x480)",
                  area_name: "Kitchen",
                  default_group: "wall_panels",
                },
              ],
              ignored_latter_devices: [
                {
                  esphome_device_id: "esp_ignored_1",
                  node_name: "test_bench",
                  title: "Test Bench",
                  model_label: "Pocket",
                  area_name: "",
                  default_group: "pocket_carry",
                },
              ],
            });
            const sidebarOneLatter = renderToHtml(LatterStudio.prototype._renderSidebar.call(one.el));
            const drilldown = buildHost({ deviceSelected: true, activeSubentryId: "sub_1", currentViewId: "dashboard" });
            const sidebarDrilldown = renderToHtml(LatterStudio.prototype._renderSidebar.call(drilldown.el));

            const managedRoaming = renderToHtml(renderDevicesListView(buildHost({ deviceCategoryFilter: "roaming" }).store));

            const discAll = renderToHtml(renderDevicesDiscoveredView(one.store));
            one.store.discoveredBleSort = "rssi";
            const discSortRssi = renderToHtml(renderDevicesDiscoveredView(one.store));
            one.store.discoveredBleSort = "name";
            one.store.discoveredBleKindFilter = "tracker";
            const discTrackersOnly = renderToHtml(renderDevicesDiscoveredView(one.store));

            process.stdout.write(JSON.stringify({
              sidebarZeroLatter,
              sidebarOneLatter,
              sidebarDrilldown,
              managedRoaming,
              discAll,
              discSortRssi,
              discTrackersOnly,
            }));
            """
        )
        self.assertIn('href="/latter/devices"', got["sidebarZeroLatter"])
        self.assertIn('href="/latter/devices/discovered"', got["sidebarZeroLatter"])
        self.assertIn('id="nav-system-count"', got["sidebarZeroLatter"])
        self.assertNotIn("nav-discovered-count", got["sidebarZeroLatter"])

        self.assertIn('id="nav-discovered-count"', got["sidebarOneLatter"])
        self.assertIn("← Managed", got["sidebarDrilldown"])

        self.assertNotIn(">Desk Panel<", got["managedRoaming"])
        self.assertIn('<a href="/latter/devices/sub_2">Pocket Assistant</a>', got["managedRoaming"])

        self.assertIn("Kitchen Panel", got["discAll"])
        self.assertIn("Ignore", got["discAll"])
        self.assertIn("Ignored (1)", got["discAll"])
        self.assertLess(got["discAll"].index("Living TV BLE"), got["discAll"].index("Zoe's Watch"))
        self.assertLess(got["discSortRssi"].index("Zoe's Watch"), got["discSortRssi"].index("Living TV BLE"))
        self.assertIn("Zoe's Watch", got["discTrackersOnly"])
        self.assertNotIn("Living TV BLE", got["discTrackersOnly"])

    def test_system_presence_walk_around_ux_and_ble_tracked_filter(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToContainer, renderToHtml } from "./test/fake-store.js";
            import { renderSystemPresenceView } from "./src/views/system-presence-view.js";

            globalThis.requestAnimationFrame = (cb) => { cb(0); return 1; };

            const deskUntracked = {
              subentry_id: "sub_desk",
              title: "Desk Assistant",
              has_ble: true,
              ble_tracked: false,
              kind: "device",
              active_area_name: "Office",
              ble_packets_seen: 0,
              ble_survey_rows: [],
            };
            const pocketTracked = {
              subentry_id: "sub_pocket",
              title: "Pocket Assistant",
              has_ble: true,
              ble_tracked: true,
              kind: "device",
              active_area_name: "Bedroom",
              ble_packets_seen: 14,
              ble_survey_rows: [
                {
                  area_id: "bedroom",
                  area_name: "Bedroom",
                  scanner_source: "AA:BB:CC:DD:EE:01",
                  scanner_name: "Bedroom Proxy",
                  raw_rssi: -58,
                  effective_rssi: -57,
                  offset_db: 1.0,
                  distance_m: 1.2,
                  age_seconds: 1,
                  is_fresh: true,
                  is_winner: true,
                },
                {
                  area_id: "",
                  area_name: "",
                  scanner_source: "AA:BB:CC:DD:EE:02",
                  scanner_name: "Hallway Plug",
                  raw_rssi: -76,
                  effective_rssi: -76,
                  offset_db: 0,
                  distance_m: 4.8,
                  age_seconds: 2,
                  is_fresh: true,
                  is_winner: false,
                },
              ],
            };
            const keyringTag = {
              subentry_id: "sub_tag",
              title: "Keyring Tag",
              has_ble: false,
              ble_tracked: false,
              kind: "ble_tag",
              active_area_name: "Kitchen",
              ble_packets_seen: 5,
              ble_survey_rows: [],
            };

            const { store, sysCalls, scrolled, focused } = makeFakeStore({
              activeSubentryId: "sub_desk",
              state: {
                system_config: {
                  ble_away_timeout_s: 180,
                  ble_max_radius_m: 12,
                  ble_max_velocity_mps: 3.5,
                  ble_attenuation: 2.2,
                },
                system_devices: [
                  structuredClone(deskUntracked),
                  structuredClone(pocketTracked),
                  structuredClone(keyringTag),
                ],
                ble_area_signatures: [
                  { area_id: "bedroom", area_name: "Bedroom", floor_id: "upstairs", has_ble_proxy: true, has_signature: true, scanner_count: 2, sample_count: 18, captured_at: "2026-11-16T20:00:00Z" },
                  { area_id: "office", area_name: "Office", floor_id: "downstairs", has_ble_proxy: false, has_signature: false, scanner_count: 0, sample_count: 0, captured_at: "" },
                ],
                live: {
                  area_presence_grid: [
                    { area_id: "bedroom", area_name: "Bedroom", floor_name: "Upstairs", is_occupied: true, confidence_pct: 84, occupant_names: ["Alex"], winning_rssi: -57, closest_distance_m: 1.2, match_method: "signature", fusion_mode: "weighted", fusion_threshold_pct: 50, fusion_sensors: [], fusion_sensor_choices: [] },
                  ],
                },
              },
            });

            const defaultSurveyAfterFilter = store.bleSurveySubentryId;
            const activeRendered = renderToHtml(renderSystemPresenceView(store));

            store.groups.selectBleCalibrateArea("office", true);
            const handoffActiveAfterSelect = store.bleCalibrateHandoffActive;
            const handoffDom = renderToContainer(renderSystemPresenceView(store));
            const afterBridgeRendered = handoffDom.innerHTML;

            await store.groups.captureBleAreaSignature("office");
            const handoffAfterCapture = store.bleCalibrateHandoffActive;

            store.groups.toggleBleLiveStream(false);
            const pausedRendered = renderToHtml(renderSystemPresenceView(store));
            store.applyBleSurveyDelta({
              type: "ble_survey_delta",
              subentry_id: "sub_pocket",
              ble_packets_seen: 99,
              ble_survey_rows: [{ area_id: "kitchen", area_name: "Kitchen", scanner_source: "AA:BB:CC:DD:EE:99", scanner_name: "Kitchen Proxy", raw_rssi: -42, effective_rssi: -42, offset_db: 0, distance_m: 0.5, age_seconds: 0, is_fresh: true, is_winner: true }],
            });
            const afterPausedDeltaDev = structuredClone(store.groups.getActiveSurveyDevice());

            store.groups.toggleBleLiveStream(true);
            store.applyBleSurveyDelta({
              type: "ble_survey_delta",
              subentry_id: "sub_pocket",
              ble_packets_seen: 42,
              ble_survey_rows: [{ area_id: "kitchen", area_name: "Kitchen", scanner_source: "AA:BB:CC:DD:EE:99", scanner_name: "Kitchen Proxy", raw_rssi: -44, effective_rssi: -44, offset_db: 0, distance_m: 0.6, age_seconds: 0, is_fresh: true, is_winner: true }],
            });
            const afterResumedDeltaDev = structuredClone(store.groups.getActiveSurveyDevice());

            process.stdout.write(JSON.stringify({
              defaultSurveyAfterFilter,
              activeRendered,
              scrolled,
              focused,
              sysCalls,
              handoffActiveAfterSelect,
              afterBridgeRendered,
              handoffAfterCapture,
              pausedRendered,
              afterPausedDeltaDev,
              afterResumedDeltaDev,
            }));
            """
        )
        self.assertEqual(got["defaultSurveyAfterFilter"], "sub_pocket")
        self.assertNotIn("Desk Assistant", got["activeRendered"])
        self.assertIn("Pocket Assistant (Bedroom)", got["activeRendered"])
        self.assertIn('<h4 class="area-box-title">Bedroom</h4>', got["activeRendered"])
        self.assertIn("Standing in Area", got["activeRendered"])
        self.assertIn("Pause stream", got["activeRendered"])
        self.assertIn("Resume stream", got["pausedRendered"])
        self.assertTrue(got["handoffActiveAfterSelect"])
        self.assertIn("ble-calibrate-handoff-banner", got["afterBridgeRendered"])
        self.assertFalse(got["handoffAfterCapture"])
        self.assertEqual(got["afterPausedDeltaDev"]["ble_packets_seen"], 14)
        self.assertEqual(got["afterResumedDeltaDev"]["ble_packets_seen"], 42)
        self.assertEqual(got["sysCalls"][0]["command"], "capture_ble_area_signature")


@unittest.skipUnless(NODE, "node is not installed")
class TestDeviceGroupsAndCustomFlow(unittest.TestCase):
    """Device groups, staged Batch controls, System overview, Support card, 7,447 MDI icons, & handoff highlights."""

    def test_groups_boxes_staged_batch_controls_and_save_custom_modal(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { renderDeviceOverviewView } from "./src/views/device-overview-view.js";
            import { renderSystemGroupsView } from "./src/views/system-groups-view.js";
            import { renderSystemToolsView } from "./src/views/system-tools-view.js";

            const { store, sysCalls } = makeFakeStore({
              activeSubentryId: "sub_mobile",
              state: {
                title: "Mobile Assistant",
                system_info: { ha_version: "2026.11.0", integration_version: "3.0.0", min_firmware_sdk_rev: 2026111801, studio_rev: 34 },
                config: {
                  kind: "device",
                  device_slug: "mobile_assistant",
                  device_group: "custom",
                  assigned_person: "person.alex",
                  device_remote_group: "area_auto",
                  native_ble_tracking: true,
                },
                capabilities: { has_display: true, has_battery: true, is_roaming_device: true },
                live: { active_area_name: "Office" },
                device_groups: [
                  { id: "pocket_carry", name: "Pocket Carry", description: "Compact displays", builtin: true, include_display: false, include_interface: false, device_config: { tap_to_wake: "Docked Only", native_ble_tracking: true } },
                  { id: "handhelds", name: "Handhelds", description: "Battery displays", builtin: true, include_display: false, include_interface: false, device_config: { tap_to_wake: "Single Tap", native_ble_tracking: true } },
                  { id: "guest_suites", name: "Guest Suites", description: "Guest displays", builtin: false, include_display: true, include_interface: true, device_config: { clock_face: "Hybrid Digital" } },
                ],
                system_devices: [
                  { subentry_id: "sub_mobile", title: "Mobile Assistant", device_slug: "mobile_assistant", kind: "device", has_display: true, has_battery: true, is_online: true, is_roaming: true, ble_tracked: true, device_group: "custom", device_group_name: "Custom", status_code: "online", status_label: "Online" },
                  { subentry_id: "sub_pocket", title: "Pocket Assistant", device_slug: "pocket_assistant", kind: "device", has_display: true, has_battery: true, is_online: true, is_roaming: true, ble_tracked: true, device_group: "pocket_carry", device_group_name: "Pocket Carry", status_code: "online", status_label: "Online" },
                ],
                system_controls: [
                  {
                    key: "audio:switch:voice follows me",
                    pref_key: "sync_device_area",
                    tier: "behavior",
                    section: "audio",
                    section_title: "Audio",
                    name: "Voice Follows Me",
                    domain: "switch",
                    state: "off",
                    options: [],
                    targets: [
                      { device_slug: "mobile_assistant", device_group: "custom", is_online: true, is_roaming: true, pref_key: "sync_device_area", state: "on" },
                      { device_slug: "pocket_assistant", device_group: "pocket_carry", is_online: true, is_roaming: true, pref_key: "sync_device_area", state: "off" },
                    ],
                  },
                ],
              },
            });

            const groupsHtml = renderToHtml(renderSystemGroupsView(store));
            store.groups.requestResetDeviceGroup("pocket_carry", "Pocket Carry", 1);
            await store.tools.runConfirmedAction();
            store.groups.toggleNewGroupForm(true);
            const groupsCreateOpenHtml = renderToHtml(renderSystemGroupsView(store));
            store.newGroupName = "Patio Panels";
            await store.groups.createDeviceGroup();

            // Stage a Batch control change and apply it
            store.groups.stageBatchSetting("sync_device_area", true);
            await store.groups.applyBatchDraft();

            store.groups.openSaveGroupModal();
            store.saveGroupModal = { ...store.saveGroupModal, name: " Alex Carry ", description: "Personal handheld" };
            await store.groups.confirmSaveGroupModal();

            const overviewCustomHtml = renderToHtml(renderDeviceOverviewView(store));
            const sysToolsHtml = renderToHtml(renderSystemToolsView(store));

            // Active timer & stopwatch via UTC ISO anchors (`timer_ends_at`, `stopwatch_started_at`)
            store.liveClockNowMs = Date.parse("2026-11-19T00:00:00Z");
            store.state.config.device_group = "handhelds";
            store.state.live = {
              ...store.state.live,
              timer_running: true,
              timer_paused: false,
              timer_remaining_sec: 125,
              timer_ends_at: "2026-11-19T00:02:05Z",
              stopwatch_running: true,
              stopwatch_paused: false,
              stopwatch_elapsed_sec: 3665,
              stopwatch_started_at: "2026-11-18T22:58:55Z",
              alarm_ringing: true,
            };
            const overviewGroupHtml = renderToHtml(renderDeviceOverviewView(store));

            process.stdout.write(JSON.stringify({
              groupsHtml,
              groupsCreateOpenHtml,
              overviewCustomHtml,
              overviewGroupHtml,
              sysToolsHtml,
              sysCalls,
            }));
            """
        )
        self.assertIn('id="btn-open-create-group"', got["groupsHtml"])
        self.assertIn('id="group-box-pocket_carry"', got["groupsHtml"])
        self.assertIn('id="btn-reset-group-pocket_carry"', got["groupsHtml"])
        self.assertNotIn('id="btn-reset-group-guest_suites"', got["groupsHtml"])
        self.assertIn('id="group-box-custom"', got["groupsHtml"])
        self.assertIn('id="btn-batch-reset"', got["groupsHtml"])
        self.assertIn('id="btn-batch-apply"', got["groupsHtml"])
        self.assertIn('id="create-group-form"', got["groupsCreateOpenHtml"])
        self.assertIn('id="btn-save-custom-group"', got["overviewCustomHtml"])
        self.assertNotIn('id="btn-save-custom-group"', got["overviewGroupHtml"])
        self.assertIn('id="overview-ringing-alert"', got["overviewGroupHtml"])
        self.assertIn("02:05", got["overviewGroupHtml"])
        self.assertIn("01:01:05", got["overviewGroupHtml"])
        self.assertIn('id="card-support-diagnostics"', got["sysToolsHtml"])
        self.assertIn('id="btn-download-system-diagnostics"', got["sysToolsHtml"])
        self.assertIn('id="btn-copy-system-info"', got["sysToolsHtml"])
        self.assertEqual(
            [c["command"] for c in got["sysCalls"]],
            [
                "update_group_baseline",
                "create_device_group",
                "apply_batch_device_setting",
                "create_device_group",
            ],
        )
        self.assertEqual(
            got["sysCalls"][0]["payload"],
            {"group_id": "pocket_carry", "reset_to_default": True},
        )

    def test_full_7447_mdi_catalog_and_ranked_search(self) -> None:
        """Lazy `latter-studio-mdi.js` chunk unpacks all 7,447 icons in 1:1 parity with firmware."""
        got = _run_node_esm(
            """
            import { PACKED_MDI_CHUNKS } from "../custom_components/latter/frontend/latter-studio-mdi.js";
            import { SHORTCUT_ROUTES_CATALOG } from "./src/constants.js";
            import {
              getAllMdiIcons,
              isKnownMdiIcon,
              isMdiCatalogLoaded,
              registerPackedMdiChunks,
              ROUTE_PREVIEW_ICONS,
              searchMdiIcons,
            } from "./src/mdi-catalog.js";

            const beforeLoaded = isMdiCatalogLoaded();
            registerPackedMdiChunks(PACKED_MDI_CHUNKS);
            const afterLoaded = isMdiCatalogLoaded();
            const all = getAllMdiIcons();
            const teddy = searchMdiIcons("teddy-bear");
            const multiWord = searchMdiIcons("teddy bear");
            const empty = searchMdiIcons("");
            const missingRouteIcons = SHORTCUT_ROUTES_CATALOG
              .map((r) => r.token)
              .filter((tok) => !ROUTE_PREVIEW_ICONS[tok] || !isKnownMdiIcon(ROUTE_PREVIEW_ICONS[tok]));

            process.stdout.write(JSON.stringify({
              beforeLoaded,
              afterLoaded,
              count: all.length,
              hasTeddyBear: isKnownMdiIcon("mdi:teddy-bear"),
              hasBareTeddy: isKnownMdiIcon("teddy-bear"),
              unknownFake: isKnownMdiIcon("mdi:definitely-not-an-icon-xyz"),
              teddyTop: teddy.items[0],
              multiWordTop: multiWord.items[0],
              emptyTotal: empty.totalMatches,
              missingRouteIcons,
            }));
            """
        )
        self.assertTrue(got["beforeLoaded"])
        self.assertTrue(got["afterLoaded"])
        self.assertEqual(got["count"], 7447)
        self.assertEqual(got["missingRouteIcons"], [])
        self.assertTrue(got["hasTeddyBear"])
        self.assertTrue(got["hasBareTeddy"])
        self.assertFalse(got["unknownFake"])
        self.assertEqual(got["teddyTop"], "mdi:teddy-bear")
        self.assertEqual(got["multiWordTop"], "mdi:teddy-bear")
        self.assertEqual(got["emptyTotal"], 7447)

    def test_system_overview_visual_status_deployment_and_capabilities(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { renderSystemOverviewView } from "./src/views/system-overview-view.js";

            function build(withAlerts) {
              return makeFakeStore({
                state: {
                  version: "3.0.0",
                  ble_proxy_count: 5,
                  has_security_pin: !withAlerts,
                  issues: withAlerts
                    ? [{ issue_id: "device_crashed_sub1", kind: "device_crashed", severity: "error", subentry_id: "sub_1", device_title: "Kitchen Panel" }]
                    : [],
                  discovered_latter_devices: withAlerts
                    ? [{ esphome_device_id: "esp_new", node_name: "office_dock", title: "Office Dock", model_label: "Latter 4.0", area_name: "Office", default_group: "wall_panels" }]
                    : [],
                  device_groups: [
                    { id: "pocket_carry", name: "Pocket Carry", description: "" },
                    { id: "wall_panels", name: "Wall & Desk Panels", description: "" },
                  ],
                  system_devices: [
                    {
                      subentry_id: "sub_1",
                      title: "Living Panel",
                      kind: "device",
                      is_online: true,
                      has_display: true,
                      is_roaming: false,
                      has_assigned_area: true,
                      area_id: "living",
                      area_label: "Living Area",
                      active_area_name: "Living Area",
                      device_group: "wall_panels",
                      assigned_person: "",
                      ble_tracked: false,
                      status_code: "online",
                      status_label: "Online",
                    },
                    {
                      subentry_id: "sub_2",
                      title: "Alex Pocket",
                      kind: "device",
                      is_online: true,
                      has_display: true,
                      is_roaming: true,
                      has_assigned_area: false,
                      area_id: "living",
                      area_label: "Roaming",
                      active_area_name: "Living Area",
                      device_group: "pocket_carry",
                      assigned_person: "person.alex",
                      ble_tracked: true,
                      status_code: "online",
                      status_label: "Online",
                    },
                  ],
                  live: {
                    area_presence_grid: [
                      { area_id: "living", area_name: "Living Area", floor_name: "Main Floor", is_occupied: true, occupant_names: ["Alex"], active_sensors: ["binary_sensor.living_mmwave"], fusion_sensors: ["binary_sensor.living_mmwave"] },
                      { area_id: "study", area_name: "Study", is_occupied: false, occupant_names: [], active_sensors: [], fusion_sensors: [] },
                    ],
                  },
                  ble_area_signatures: [
                    { area_id: "living", area_name: "Living Area", has_ble_proxy: true, has_signature: true, scanner_count: 3, sample_count: 15, captured_at: "" },
                    { area_id: "study", area_name: "Study", has_ble_proxy: false, has_signature: false, scanner_count: 0, sample_count: 0, captured_at: "" },
                  ],
                  system_config: {
                    weather_entity: "weather.home",
                    alarm_entity: "alarm_control_panel.home",
                    thermostat_entities: ["climate.main", "climate.upstairs"],
                    lock_entities: ["lock.front"],
                    garage_entities: [],
                    vacuum_entities: ["vacuum.robo"],
                    camera_entities: ["camera.front_door", "camera.patio"],
                    calendar_entities: ["calendar.family"],
                    remotes_list: ["remote.living_tv"],
                    remote_groups: [{ id: "rg_living", name: "Living TV", area_id: "living", remotes: ["remote.living_tv"] }],
                    volume_overrides: [{ speaker: "media_player.living", target: "media_player.avr" }],
                    custom_palettes: [{ name: "Ocean", hex: "#009ac7" }],
                    doorbell_noise_reduction: "strong",
                  },
                  system_wallpapers: [
                    { id: "preset:forest_mountains", name: "Forest Mountains", kind: "preset" },
                    { id: "upload:1", name: "Custom Photo", kind: "upload", deletable: true },
                  ],
                },
              }).store;
            }

            process.stdout.write(JSON.stringify({
              healthyHtml: renderToHtml(renderSystemOverviewView(build(false))),
              alertsHtml: renderToHtml(renderSystemOverviewView(build(true))),
            }));
            """
        )
        healthy = re.sub(r"\s+", " ", got["healthyHtml"])
        alerts = re.sub(r"\s+", " ", got["alertsHtml"])

        self.assertNotIn("sys-issues-banner", healthy)
        self.assertNotIn("card-system-capabilities", healthy)
        self.assertNotIn("System capabilities", healthy)
        for expected in (
            "All online",
            "2 / 2 online",
            "1 occupied",
            "2 Areas • 5 BLE proxies",
            "1 person assigned",
            "Area deployment",
            "Living Area",
            "Living Panel",
        ):
            self.assertIn(expected, healthy)

        for expected_alert in (
            "sys-issues-banner",
            'role="region"',
            "Kitchen Panel",
            "sys-discovered-banner",
            "Hardware ready to adopt",
            "Office Dock",
        ):
            self.assertIn(expected_alert, alerts)

    def test_section_handoff_blue_highlights_vs_whole_page_navigation(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { STUDIO_STYLES } from "./src/styles/tokens.js";
            import { renderDeviceToolsView } from "./src/views/device-tools-view.js";
            import { renderSystemGroupsView } from "./src/views/system-groups-view.js";
            import { renderSystemPresenceView } from "./src/views/system-presence-view.js";
            import { renderSystemRemotesView } from "./src/views/system-remotes-view.js";
            import { renderSystemSharedView } from "./src/views/system-shared-view.js";

            globalThis.history = { pushState() {}, replaceState() {} };
            globalThis.requestAnimationFrame = (cb) => { cb(0); return 1; };

            const { store, scrolled } = makeFakeStore({
              activeSubentryId: "sub_1",
              deviceSelected: true,
              state: {
                device_groups: [{ id: "handhelds", name: "Handhelds", description: "Portable", builtin: true, device_config: {} }],
                system_devices: [{ subentry_id: "sub_1", title: "Alex Pocket", kind: "device", is_online: true, has_display: true, is_roaming: true, ble_tracked: true, active_area_name: "Living Room", device_group: "handhelds" }],
                live: { area_presence_grid: [{ area_id: "living", area_name: "Living Room", is_occupied: true, confidence_pct: 90, occupant_names: ["Alex"] }] },
                ble_area_signatures: [{ area_id: "living", area_name: "Living Room", has_ble_proxy: true, has_signature: false, scanner_count: 1, sample_count: 0, captured_at: "" }],
                system_config: { camera_entities: ["camera.front"], calendar_entities: ["calendar.home"], remotes_list: ["remote.tv"], remote_groups: [{ id: "rg1", name: "Living TV", area_id: "living", remotes: ["remote.tv"] }] },
                config: { kind: "device", device_slug: "alex_pocket", device_group: "handhelds" },
              },
            });

            store.openSystemSection("area_tracking", "area-box-living");
            store.applyRoute({ prefix: "/latter", path: "/system/presence" });
            store.hostUpdated();
            await Promise.resolve();
            const presenceHtml = renderToHtml(renderSystemPresenceView(store));

            store.openSystemSection("shared_entities", "card-cameras-doorbell", ["card-cameras-doorbell", "card-calendars"]);
            const sharedCamCalHtml = renderToHtml(renderSystemSharedView(store));

            store.openSystemSection("remotes");
            const remotesWholePageHtml = renderToHtml(renderSystemRemotesView(store));

            store.openManageGroups("handhelds");
            const groupsTargetedHtml = renderToHtml(renderSystemGroupsView(store));

            store.openDeviceSection("tools", "card-device-diagnostics");
            const devToolsHtml = renderToHtml(renderDeviceToolsView(store));
            store.hostUpdated();

            store.onMainFocusIn({
              target: { tagName: "BUTTON", id: "other-btn", parentElement: { id: "card-replace-hardware", parentElement: null } },
            });
            const devToolsClearedHtml = renderToHtml(renderDeviceToolsView(store));

            process.stdout.write(JSON.stringify({
              cssText: Array.isArray(STUDIO_STYLES) ? STUDIO_STYLES.map((s) => s.styleSheetText).join("\\n") : STUDIO_STYLES.styleSheetText,
              scrolled,
              presenceHtml,
              sharedCamCalHtml,
              remotesWholePageHtml,
              groupsTargetedHtml,
              devToolsHtml,
              devToolsClearedHtml,
            }));
            """
        )
        self.assertIn("--studio-handoff-surface:", got["cssText"])
        self.assertIn('id="area-box-living" class="area-presence-box handoff-active"', got["presenceHtml"])
        self.assertEqual(
            got["scrolled"][0],
            {"id": "area-box-living", "opts": {"behavior": "smooth", "block": "start"}},
        )
        self.assertEqual(got["sharedCamCalHtml"].count("handoff-active"), 2)
        self.assertNotIn("handoff-active", got["remotesWholePageHtml"])
        self.assertIn('id="group-box-handhelds" class="area-presence-box handoff-active"', got["groupsTargetedHtml"])
        self.assertIn('id="card-device-diagnostics" class="card handoff-active"', got["devToolsHtml"])
        self.assertNotIn("handoff-active", got["devToolsClearedHtml"])

    def test_device_power_bedtime_card_and_non_detaching_batch_preview(self) -> None:
        """Verify D-068: #card-bedtime-mode hides schedule hours until enabled and staging bedtime_active does not warn of group detachment."""
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { renderDevicePowerView } from "./src/views/device-power-view.js";

            function buildPower(schedOn) {
              return makeFakeStore({
                activeSubentryId: "sub_1",
                state: {
                  device_prefs: [
                    { key: "tap_to_wake", label: "Tap to wake", section: "power", group_tier: "behavior", domain: "select", value: "Single Tap", options: ["Single Tap", "Disabled"] },
                    { key: "bedtime_active", label: "Bedtime mode", section: "power", group_tier: null, domain: "switch", value: false, options: [] },
                    { key: "bedtime_display", label: "Idle display in bedtime", section: "power", group_tier: "behavior", domain: "select", value: "Screen Off", options: ["Screen Off", "Ambient Clock"] },
                    { key: "bedtime_schedule", label: "Bedtime schedule", section: "power", group_tier: "behavior", domain: "switch", value: schedOn, options: [] },
                    { key: "bedtime_start_hour", label: "Bedtime starts", section: "power", group_tier: "behavior", domain: "number", value: 22, options: [], min: 0, max: 23, step: 1, unit: ":00" },
                    { key: "bedtime_end_hour", label: "Bedtime ends", section: "power", group_tier: "behavior", domain: "number", value: 7, options: [], min: 0, max: 23, step: 1, unit: ":00" },
                  ],
                  pref_specs: [
                    { key: "bedtime_active", label: "Bedtime mode", section: "power", group_tier: null, domain: "switch", default: false, options: [] },
                    { key: "bedtime_display", label: "Idle display in bedtime", section: "power", group_tier: "behavior", domain: "select", default: "Screen Off", options: ["Screen Off", "Ambient Clock"] },
                  ],
                  system_devices: [
                    { subentry_id: "sub_1", title: "Bedroom Desk", kind: "device", is_online: true, has_display: true, device_group: "wall_panels" },
                  ],
                },
              }).store;
            }

            const sOff = buildPower(false);
            const sOn = buildPower(true);

            sOn.groups.stageBatchSetting("bedtime_active", true);
            const detachBedtimeOnly = sOn.groups.previewBatchDetachmentCount();
            sOn.groups.stageBatchSetting("bedtime_display", "Ambient Clock");
            const detachWithPolicy = sOn.groups.previewBatchDetachmentCount();

            process.stdout.write(JSON.stringify({
              offHtml: renderToHtml(renderDevicePowerView(sOff)),
              onHtml: renderToHtml(renderDevicePowerView(sOn)),
              detachBedtimeOnly,
              detachWithPolicy,
            }));
            """
        )
        self.assertIn('id="card-bedtime-mode"', got["offHtml"])
        self.assertIn("Idle display in bedtime", got["offHtml"])
        self.assertIn("Screen off", got["offHtml"])
        self.assertNotIn("Bedtime starts", got["offHtml"])
        self.assertIn("Bedtime starts", got["onHtml"])
        self.assertIn("Bedtime ends", got["onHtml"])
        self.assertEqual(got["detachBedtimeOnly"], 0)
        self.assertEqual(got["detachWithPolicy"], 1)

    def test_universal_12h_vs_24h_time_format_across_overview_and_hour_selects(self) -> None:
        """D-069 / D-070: Overview alarm summary chip, 24-hour `:00` `<select>` pickers, and `1..100%` brightness sliders (including `bedtime_brightness`)."""
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { SimEvent } from "./test/dom-shim.js";
            import { makeFakeStore, renderToContainer, renderToHtml } from "./test/fake-store.js";
            import { renderDeviceOverviewView } from "./src/views/device-overview-view.js";
            import { renderDeviceDisplayView } from "./src/views/device-display-view.js";
            import { renderDevicePowerView } from "./src/views/device-power-view.js";
            import { renderGroupBaselineDrawer } from "./src/views/groups/group-baseline-drawer.js";

            function buildDevStore(timeFormat, bedtimeActive = false) {
              return makeFakeStore({
                activeSubentryId: "sub_1",
                currentScope: "devices",
                hass: { locale: { language: "en", time_format: "24" }, config: { unit_system: { length: "km" } }, states: {} },
                state: {
                  config: {
                    kind: "device",
                    time_format: timeFormat,
                    alarms_summary: "19:30|1|0;08:30|0|2;09:00|0|2",
                    bedtime_active: bedtimeActive,
                    bedtime_brightness: 15,
                    bedtime_schedule: true,
                    bedtime_start_hour: 22,
                    bedtime_end_hour: 7,
                    auto_brightness_mode: "Time Schedule",
                    day_brightness: 90,
                    night_brightness: 35,
                    day_start_hour: 7,
                    night_start_hour: 20,
                  },
                  capabilities: { has_display: true, has_power: true },
                  device_prefs: [
                    { key: "time_format", label: "Time format", section: "interface", domain: "select", value: timeFormat, options: ["12-Hour (AM/PM)", "24-Hour"] },
                    { key: "auto_brightness_mode", label: "Auto brightness mode", section: "display", domain: "select", value: "Time Schedule", options: ["Disabled", "Sun Synchronized", "Time Schedule"] },
                    { key: "manual_brightness", label: "Manual brightness", section: "display", domain: "number", value: 80, min: 1, max: 100, step: 1, unit: "%" },
                    { key: "day_brightness", label: "Day brightness", section: "display", domain: "number", value: 90, min: 1, max: 100, step: 1, unit: "%" },
                    { key: "night_brightness", label: "Night brightness", section: "display", domain: "number", value: 35, min: 1, max: 100, step: 1, unit: "%" },
                    { key: "day_start_hour", label: "Day start hour", section: "display", domain: "number", value: 7, min: 0, max: 23, step: 1, unit: ":00" },
                    { key: "night_start_hour", label: "Night start hour", section: "display", domain: "number", value: 20, min: 0, max: 23, step: 1, unit: ":00" },
                    { key: "bedtime_active", label: "Bedtime mode", section: "power", domain: "switch", value: bedtimeActive },
                    { key: "bedtime_display", label: "Idle display in bedtime", section: "power", domain: "select", value: "Screen Off", options: ["Screen Off", "Ambient Clock"] },
                    { key: "bedtime_brightness", label: "Bedtime brightness", section: "power", domain: "number", value: 15, min: 1, max: 100, step: 1, unit: "%" },
                    { key: "bedtime_schedule", label: "Bedtime schedule", section: "power", domain: "switch", value: true },
                    { key: "bedtime_start_hour", label: "Bedtime starts", section: "power", domain: "number", value: 22, min: 0, max: 23, step: 1, unit: ":00" },
                    { key: "bedtime_end_hour", label: "Bedtime ends", section: "power", domain: "number", value: 7, min: 0, max: 23, step: 1, unit: ":00" },
                  ],
                  system_devices: [{ subentry_id: "sub_1", title: "Desk Panel", kind: "device", is_online: true, has_display: true }],
                },
              }).store;
            }

            const dev12 = buildDevStore("12-Hour (AM/PM)", true);
            const dev24 = buildDevStore("24-Hour", false);

            const power12Box = renderToContainer(renderDevicePowerView(dev12));
            const powerRanges12 = Array.from(power12Box.querySelectorAll("input[type='range']"));
            const bedtimeBriAria = powerRanges12[0]?.getAttribute("aria-valuetext");
            const powerSelects12 = Array.from(power12Box.querySelectorAll("select"));
            const startSelect12 = powerSelects12.find((s) => s.getAttribute("aria-label") === "Bedtime starts");
            const startOptCount12 = startSelect12 ? startSelect12.querySelectorAll("option").length : 0;
            const startFirstOpt12 = startSelect12 ? startSelect12.querySelectorAll("option")[0]?.textContent?.trim() : "";

            const disp12Box = renderToContainer(renderDeviceDisplayView(dev12));
            const dispRanges12 = Array.from(disp12Box.querySelectorAll("input[type='range']")).map((r) => r.getAttribute("aria-valuetext"));
            const dispHourSelects12 = Array.from(disp12Box.querySelectorAll("select")).filter((s) => s.querySelectorAll("option").length === 24).length;

            function renderSysGroup(localeTf) {
              const s = makeFakeStore({
                currentScope: "system",
                hass: { locale: { language: "en", time_format: localeTf }, config: { unit_system: { length: "km" } }, states: {} },
              }).store;
              s.openGroupIds.add("wall_panels");
              const grp = {
                id: "wall_panels",
                name: "Wall & Desk Panels",
                description: "Stationary panels",
                builtin: true,
                include_display: false,
                include_interface: false,
                device_config: {
                  auto_brightness_mode: "Time Schedule",
                  day_brightness: 90,
                  night_brightness: 35,
                  day_start_hour: 7,
                  night_start_hour: 20,
                  bedtime_brightness: 15,
                  bedtime_schedule: true,
                  bedtime_start_hour: 22,
                  bedtime_end_hour: 6,
                },
              };
              const box = renderToContainer(renderGroupBaselineDrawer(s, grp, [], []));
              const hourSelectCount = Array.from(box.querySelectorAll("select")).filter((el) => el.querySelectorAll("option").length === 24).length;
              const briRanges = Array.from(box.querySelectorAll("input[type='range']")).map((el) => el.getAttribute("aria-valuetext"));
              return { html: renderToHtml(renderGroupBaselineDrawer(s, grp, [], [])), hourSelectCount, briRanges };
            }

            const sys12 = renderSysGroup("am_pm");
            const sys24 = renderSysGroup("24");

            process.stdout.write(JSON.stringify({
              ov12: renderToHtml(renderDeviceOverviewView(dev12)),
              ov24: renderToHtml(renderDeviceOverviewView(dev24)),
              pw12: renderToHtml(renderDevicePowerView(dev12)),
              pw24: renderToHtml(renderDevicePowerView(dev24)),
              disp12: renderToHtml(renderDeviceDisplayView(dev12)),
              powerRangeCount12: powerRanges12.length,
              bedtimeBriAria,
              startOptCount12,
              startFirstOpt12,
              dispRanges12,
              dispHourSelects12,
              sys12,
              sys24,
            }));
            """
        )
        self.assertIn("1 enabled • 7:30 PM", got["ov12"])
        self.assertIn("1 enabled • 19:30", got["ov24"])
        self.assertEqual(got["powerRangeCount12"], 1)
        self.assertEqual(got["bedtimeBriAria"], "15%")
        self.assertEqual(got["startOptCount12"], 24)
        self.assertEqual(got["startFirstOpt12"], "12:00 AM")
        self.assertIn("Bedtime brightness", got["pw12"])
        self.assertIn("10:00 PM", got["pw12"])
        self.assertIn("7:00 AM", got["pw12"])
        self.assertIn("22:00", got["pw24"])
        self.assertIn("07:00", got["pw24"])
        self.assertEqual(got["dispRanges12"], ["90%", "35%"])
        self.assertEqual(got["dispHourSelects12"], 2)
        self.assertIn("Bedtime mode is currently active", got["disp12"])
        self.assertEqual(got["sys12"]["hourSelectCount"], 4)
        self.assertEqual(got["sys24"]["hourSelectCount"], 4)
        self.assertIn("90%", got["sys12"]["briRanges"])
        self.assertIn("35%", got["sys12"]["briRanges"])
        self.assertIn("15%", got["sys12"]["briRanges"])
        self.assertIn("10:00 PM", got["sys12"]["html"])
        self.assertIn("6:00 AM", got["sys12"]["html"])
        self.assertIn("22:00", got["sys24"]["html"])
        self.assertIn("06:00", got["sys24"]["html"])


if __name__ == "__main__":
    unittest.main()
