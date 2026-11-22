"""Studio entity labels, ESPHome entity section classifier, Display/Interface/Power views, and 12h/24h time format."""

from __future__ import annotations

import json
import re
import unittest

from custom_components.latter.groups import esphome_inspector as entity_sections
from tests.conftest import (
    FRONTEND_SRC,
    LATTER_DIR,
    NODE_BIN as NODE,
    read_py_tree,
    read_ts_tree,
    run_studio_node_esm as _run_node_esm,
)

STUDIO_JS = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")


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
        controls_ts = read_ts_tree("components/controls.ts", "components/controls")
        shared_ts = (FRONTEND_SRC / "views" / "system-shared-view.ts").read_text(encoding="utf-8")
        self.assertIn("entityLabel(", controls_ts)
        self.assertIn("entityLabel(", shared_ts)
        self.assertIn("entityLabel(", STUDIO_JS)
        self.assertNotIn("window.entityLabel", STUDIO_JS)




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
        payload_src = read_py_tree("studio/payload.py", "studio/payload_sections.py", "studio/payload_shared.py")
        self.assertIn('sec_ids = present_section_ids(esphome_inspector.get("sections"))', payload_src)
        self.assertIn('("sleep" in sec_ids)', payload_src)
        self.assertIn('("battery" in sec_ids)', payload_src)
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
class TestStudioDeviceViews(unittest.TestCase):
    """Interface home screen toggle and universal 12h/24h time formatting."""

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
                    local_clock_label: "Portland",
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
