"""Studio runtime behavior verified directly against TypeScript modules via Node's stdlib TS stripper."""

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
FRONTEND_SRC = REPO_ROOT / "frontend_src" / "src"
STUDIO_JS = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _strip_module_syntax(ts_text: str) -> str:
    """Strip ESM `import` lines and `export ` prefixes so concatenated TS modules execute in Node."""
    cleaned = re.sub(r"^\s*import\s+[\s\S]*?from\s+['\"][^'\"]+['\"];?\s*$", "", ts_text, flags=re.MULTILINE)
    return re.sub(r"^\s*export\s+(?=(?:async\s+)?(?:function|const|let|class|interface|type)\b)", "", cleaned, flags=re.MULTILINE)


def _run_node_ts(ts_sources: list[Path], runner_js: str) -> object:
    """Strip TypeScript types via Node's built-in `module.stripTypeScriptTypes` and evaluate `runner_js`."""
    combined_ts = "\n\n".join(_strip_module_syntax(p.read_text(encoding="utf-8")) for p in ts_sources)
    bootstrap = (
        "const { stripTypeScriptTypes } = require('node:module');\n"
        f"const tsSrc = {json.dumps(combined_ts)};\n"
        "const jsSrc = stripTypeScriptTypes(tsSrc);\n"
        f"const fn = new Function(jsSrc + '\\n' + {json.dumps(runner_js)});\n"
        "Promise.resolve(fn()).then((res) => process.stdout.write(JSON.stringify(res)));\n"
    )
    out = subprocess.run(
        [NODE, "-"],
        input=bootstrap,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return json.loads(out.stdout)


@unittest.skipUnless(NODE, "node is not installed")
class TestEntityLabels(unittest.TestCase):
    """D-013: labels from entity names (HA, ESPHome, firmware) are Title Case, acronyms and brand casing kept."""

    def test_entity_label_title_case(self) -> None:
        cases = {
            "Wake word": "Wake Word",
            "Wake word 2": "Wake Word 2",
            "Finished speaking detection": "Finished Speaking Detection",
            "Assist satellite": "Assist Satellite",
            "Assistant": "Assistant",
            "wifi signal": "Wi-Fi Signal",
            "Show all in category": "Show All in Category",
            "Wake Screen on Assist": "Wake Screen on Assist",
            "BLE presence beacon": "BLE Presence Beacon",
            "Sensitivity (okay nabu)": "Sensitivity (Okay Nabu)",
            "iBeacon uuid": "iBeacon UUID",
            "Front door": "Front Door",
            "Ram low water": "RAM Low Water",
            "Pickup to wake when docked": "Pickup to Wake When Docked",
            "Turn on": "Turn On",
        }
        got = _run_node_ts(
            [FRONTEND_SRC / "constants.ts", FRONTEND_SRC / "utils" / "format.ts"],
            f"return {json.dumps(list(cases))}.map(entityLabel);",
        )
        self.assertEqual(dict(zip(cases, got, strict=True)), cases)

    def test_every_entity_label_goes_through_it(self) -> None:
        controls_ts = (FRONTEND_SRC / "components" / "controls.ts").read_text(encoding="utf-8")
        shared_ts = (FRONTEND_SRC / "views" / "system-shared-view.ts").read_text(encoding="utf-8")
        self.assertIn("entityLabel(item.name || item.entity_id)", controls_ts)
        self.assertIn("entityLabel(b.camera_name || b.camera_entity)", shared_ts)
        self.assertIn("entityLabel(", STUDIO_JS)
        self.assertNotIn("window.entityLabel", STUDIO_JS)


@unittest.skipUnless(NODE, "node is not installed")
class TestLiveConditionalRows(unittest.TestCase):
    """A Device entity change shows at once and survives payloads that still carry the old state."""

    def test_pending_state_overlay(self) -> None:
        stub_helpers = "function formatWsError(e, f) { return f; }\n"
        runner = (
            stub_helpers
            + """
const payload = (state) => ({esphome: {sections: [{id: "voice", items: [{entity_id: "select.x_wake_word_mode", state}]}]}});
const out = {};
PENDING_ENTITY_STATES.set("select.x_wake_word_mode", {state: "Always On", expires: Date.now() + 5000});
let p = payload("Disabled"); overlayPendingEntityStates(p);
out.staleAnswer = p.esphome.sections[0].items[0].state;
out.stillPending = PENDING_ENTITY_STATES.size;
p = payload("Always On"); overlayPendingEntityStates(p);
out.confirmed = p.esphome.sections[0].items[0].state;
out.clearedAfterConfirm = PENDING_ENTITY_STATES.size;
PENDING_ENTITY_STATES.set("number.x_volume", {state: "70", expires: Date.now() + 5000});
p = {esphome: {sections: [{items: [{entity_id: "number.x_volume", state: "70.0"}]}]}}; overlayPendingEntityStates(p);
out.numericMatch = PENDING_ENTITY_STATES.size;
PENDING_ENTITY_STATES.set("select.x_wake_word_mode", {state: "Always On", expires: Date.now() - 1});
p = payload("Disabled"); overlayPendingEntityStates(p);
out.expired = [p.esphome.sections[0].items[0].state, PENDING_ENTITY_STATES.size];
return out;
"""
        )
        got = _run_node_ts(
            [
                FRONTEND_SRC / "constants.ts",
                FRONTEND_SRC / "utils" / "format.ts",
                FRONTEND_SRC / "state" / "entity-config-ops.ts",
            ],
            runner,
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
        self.assertIn("commitEntityChange(", STUDIO_JS)
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
        self.assertEqual(self.classify("select.desk_display_voice_visual_profile", "Voice: Visual Profile"), "voice")
        self.assertEqual(self.classify("select.desk_display_display_clock_face", "Display: Clock Face"), "display")

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
        self.assertEqual(set(sections), {"sleep"})
        self.assertEqual(entity_sections.present_section_ids(payload_sections), {"sleep"})
        self.assertEqual(entity_sections.present_section_ids([{"id": "sleep", "items": []}, "junk"]), set())
        payload_src = (LATTER_DIR / "studio" / "payload.py").read_text(encoding="utf-8")
        self.assertIn('sec_ids = present_section_ids(esphome_inspector.get("sections"))', payload_src)
        self.assertIn('"has_power": ("sleep" in sec_ids) or ("battery" in sec_ids),', payload_src)
        self.assertNotIn('s.get("count"', payload_src)

    def test_ha_wake_word_is_the_one_wake_word_control(self) -> None:
        self.assertNotIn("active_wake", STUDIO_JS)
        self.assertNotIn("active wake", STUDIO_JS)
        audio_ts = (FRONTEND_SRC / "views" / "device-audio-view.ts").read_text(encoding="utf-8")
        self.assertIn('it.key === "wake_word" || it.key === "wake_word_n"', audio_ts)

    def test_quick_action_buttons_always_classify_as_actions(self) -> None:
        cases = [
            ("button.desk_display_actions_find_my_device", "Actions: Find My Device"),
            ("button.desk_display_actions_trigger_voice_assistant", "Actions: Trigger Voice Assistant"),
            ("button.desk_display_actions_activate_screensaver", "Actions: Activate Screensaver"),
            ("button.desk_display_actions_hibernate_device", "Actions: Hibernate Device"),
            ("button.desk_display_actions_restart_device", "Actions: Restart Device"),
            # User-customized prefixes never scatter the quick actions across views
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
        # Developer & diagnostic entities route cleanly to developer / network, never Quick Actions or Sleep
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
            "area",
        )


@unittest.skipUnless(NODE, "node is not installed")
class TestQuickActionsControls(unittest.TestCase):
    """Stateless HA button entities (`state === 'unknown'`) render enabled and sort canonically at the top of Quick Actions."""

    def test_quick_action_ordering_and_unknown_state_enablement(self) -> None:
        stub_lit = """
const nothing = Symbol.for("latter.lit.nothing");
function html(strings, ...values) { return { _$litType$: 1, strings, values }; }
"""
        runner = (
            stub_lit
            + """
const shuffled = [
  { entity_id: "button.pocket_assistant_actions_restart_device", domain: "button", name: "Restart Device", state: "unknown" },
  { entity_id: "button.pocket_assistant_actions_hibernate_device", domain: "button", name: "Hibernate Device", state: "unknown" },
  { entity_id: "button.pocket_assistant_actions_activate_screensaver", domain: "button", name: "Activate Screensaver", state: "unavailable" },
  { entity_id: "button.pocket_assistant_actions_trigger_voice_assistant", domain: "button", name: "Trigger Voice Assistant", state: "unknown" },
  { entity_id: "button.pocket_assistant_actions_find_my_device", domain: "button", name: "Find My Device", state: "2026-11-12T18:00:00+00:00" },
];
const sorted = sortQuickActionButtons(shuffled);
const calls = [];
const fakeStore = {
  hass: null,
  espAction(eid, action, opt, toast) {
    calls.push({ eid, action, opt, toast });
    return Promise.resolve(true);
  },
};
const gridTpl = renderQuickActionGrid(fakeStore, shuffled);
const btnTemplates = gridTpl.values[0];
const gridStates = btnTemplates.map((tpl) => ({
  entityId: tpl.values[0],
  disabled: tpl.values[1],
  iconSvg: tpl.values[3].strings.join(""),
  label: tpl.values[4],
}));
btnTemplates[0].values[2]();
btnTemplates[2].values[2]();
btnTemplates[3].values[2]();
btnTemplates[4].values[2]();

const rowUnknown = renderNativeControlRow(fakeStore, {
  entity_id: "button.pocket_system_log_memory_report",
  domain: "button",
  name: "Log Memory Report",
  state: "unknown",
});
const rowUnavail = renderNativeControlRow(fakeStore, {
  entity_id: "button.pocket_system_log_memory_report",
  domain: "button",
  name: "Log Memory Report",
  state: "unavailable",
});
const swUnknown = renderNativeControlRow(fakeStore, {
  entity_id: "switch.pocket_home_sun",
  domain: "switch",
  name: "Sun",
  state: "unknown",
});

return {
  sortedIds: sorted.map((it) => it.entity_id),
  gridStates,
  calls,
  rowButtonUnknownDisabled: rowUnknown.values[4].values[0],
  rowButtonUnavailDisabled: rowUnavail.values[4].values[0],
  switchUnknownDisabled: swUnknown.values[4].values[1],
};
"""
        )
        got = _run_node_ts(
            [
                FRONTEND_SRC / "constants.ts",
                FRONTEND_SRC / "utils" / "format.ts",
                FRONTEND_SRC / "components" / "controls.ts",
            ],
            runner,
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
            [{k: v for k, v in st.items() if k != "iconSvg"} for st in got["gridStates"]],
            [
                {
                    "entityId": "button.pocket_assistant_actions_find_my_device",
                    "disabled": False,
                    "label": "Find My Device",
                },
                {
                    "entityId": "button.pocket_assistant_actions_trigger_voice_assistant",
                    "disabled": False,
                    "label": "Trigger Voice Assistant",
                },
                {
                    "entityId": "button.pocket_assistant_actions_activate_screensaver",
                    "disabled": True,
                    "label": "Activate Screensaver",
                },
                {
                    "entityId": "button.pocket_assistant_actions_hibernate_device",
                    "disabled": False,
                    "label": "Hibernate Device",
                },
                {
                    "entityId": "button.pocket_assistant_actions_restart_device",
                    "disabled": False,
                    "label": "Restart Device",
                },
            ],
        )
        # Every Quick Action button must render its own distinct icon even when the device slug contains "assistant"
        icon_svgs = [st["iconSvg"] for st in got["gridStates"]]
        self.assertEqual(len(set(icon_svgs)), 5)
        self.assertEqual(
            got["calls"],
            [
                {
                    "eid": "button.pocket_assistant_actions_find_my_device",
                    "action": "press",
                    "toast": 'Triggered "Find My Device"',
                },
                {
                    "eid": "button.pocket_assistant_actions_activate_screensaver",
                    "action": "press",
                    "toast": 'Triggered "Activate Screensaver"',
                },
                {
                    "eid": "button.pocket_assistant_actions_hibernate_device",
                    "action": "press",
                    "toast": "Hibernating Device…",
                },
                {
                    "eid": "button.pocket_assistant_actions_restart_device",
                    "action": "press",
                    "toast": "Restarting Device…",
                },
            ],
        )
        self.assertFalse(got["rowButtonUnknownDisabled"])
        self.assertTrue(got["rowButtonUnavailDisabled"])
        self.assertTrue(got["switchUnknownDisabled"])


@unittest.skipUnless(NODE, "node is not installed")
class TestDisplayViewControls(unittest.TestCase):
    """Display, Interface, and Media & Remotes views render split controls and read-only assignment shortcuts."""

    def test_sun_moon_pills_and_wallpaper_states(self) -> None:
        stub_lit = """
const nothing = Symbol.for("latter.lit.nothing");
function html(strings, ...values) { return { _$litType$: 1, strings, values }; }
function repeat(items, keyFn, tplFn) { return items.map((it, idx) => tplFn(it, idx)); }
function flattenHtml(node) {
  if (node === null || node === undefined || node === nothing || typeof node === "boolean") return "";
  if (Array.isArray(node)) return node.map(flattenHtml).join("");
  if (typeof node === "object" && node._$litType$ === 1) {
    let out = "";
    for (let i = 0; i < node.strings.length; i += 1) {
      out += node.strings[i];
      if (i < node.values.length) {
        const v = node.values[i];
        out += typeof v === "function" ? "[fn]" : flattenHtml(v);
      }
    }
    return out;
  }
  return String(node);
}
"""
        runner = (
            stub_lit
            + """
function makeStore({ weatherBgState = "Dynamic", cycleMins = 0, activeId = "", favIds = [], autoBrtState = "Disabled", remoteMode = "group:living_tv" }) {
  const favSet = new Set(favIds);
  const wallpapers = [
    { id: "preset:forest_mountains", name: "Forest Mountains", kind: "preset", active: activeId === "preset:forest_mountains", favorite: favSet.has("preset:forest_mountains"), deletable: false, thumb_url: "/thumb1" },
    { id: "preset:ocean_waves", name: "Ocean Waves", kind: "preset", active: activeId === "preset:ocean_waves", favorite: favSet.has("preset:ocean_waves"), deletable: false, thumb_url: "/thumb2" },
  ];
  const homeSection = [
    { entity_id: "switch.pocket_home_wake_greeting", domain: "switch", name: "Wake Greeting", state: "on" },
    { entity_id: "select.pocket_home_weather_background", domain: "select", name: "Weather Background", state: weatherBgState, options: ["off", "Dynamic"] },
    { entity_id: "switch.pocket_home_moon", domain: "switch", name: "Home: Moon", state: "off" },
    { entity_id: "switch.pocket_home_sun", domain: "switch", name: "Home: Sun", state: "on" },
  ];
  const displaySection = [
    { entity_id: "light.pocket_display_screen_backlight", domain: "light", name: "Display: Screen Backlight", state: "on" },
    { entity_id: "select.pocket_display_color_profile", domain: "select", name: "Display: Color Profile", state: "Default", options: ["Default", "Custom"] },
    { entity_id: "select.pocket_display_clock_face", domain: "select", name: "Display: Clock Face", state: "Modern", options: ["Modern", "Analog"] },
    { entity_id: "select.pocket_display_start_screen", domain: "select", name: "Display: Start Screen", state: "Home", options: ["Home", "Area"] },
    { entity_id: "select.pocket_display_auto_brightness_mode", domain: "select", name: "Display: Auto Brightness Mode", state: autoBrtState, options: ["Disabled", "Sun Synchronized", "Time Schedule"] },
    { entity_id: "number.pocket_display_manual_brightness", domain: "number", name: "Display: Manual Brightness", state: "80", min: 5, max: 100, step: 1, unit: "%" },
    { entity_id: "number.pocket_display_day_brightness", domain: "number", name: "Display: Day Brightness", state: "90", min: 5, max: 100, step: 1, unit: "%" },
    { entity_id: "number.pocket_display_night_brightness", domain: "number", name: "Display: Night Brightness", state: "25", min: 5, max: 100, step: 1, unit: "%" },
    { entity_id: "number.pocket_display_day_start_hour", domain: "number", name: "Display: Day Start Hour", state: "7", min: 0, max: 23, step: 1, unit: "h" },
    { entity_id: "number.pocket_display_night_start_hour", domain: "number", name: "Display: Night Start Hour", state: "22", min: 0, max: 23, step: 1, unit: "h" },
  ];
  const sleepSection = [
    { entity_id: "select.pocket_sleep_power_profile", domain: "select", name: "Power Profile", state: "Balanced", options: ["Balanced", "Low Power"] },
    { entity_id: "select.pocket_sleep_battery_screen_timeout", domain: "select", name: "Battery Screen Timeout", state: "30 s", options: ["15 s", "30 s"] },
    { entity_id: "switch.pocket_sleep_docked_screensaver", domain: "switch", name: "Docked Screensaver", state: "on" },
    { entity_id: "select.pocket_sleep_screensaver_style", domain: "select", name: "Screensaver Style", state: "Starfield", options: ["Clock", "Starfield"] },
    { entity_id: "select.pocket_sleep_docked_idle_timeout", domain: "select", name: "Docked Idle Timeout", state: "5 min", options: ["1 min", "5 min"] },
  ];
  const actionsSection = [
    { entity_id: "button.pocket_actions_activate_screensaver", domain: "button", name: "Activate Screensaver", state: "unknown" },
  ];
  const batterySection = [
    { entity_id: "sensor.pocket_battery_level", domain: "sensor", name: "Battery Level", state: "88", unit: "%" },
  ];
  const musicSection = [
    { entity_id: "media_player.pocket", domain: "media_player", name: "Player", state: "idle" },
    { entity_id: "switch.pocket_music_show_library_shortcut", domain: "switch", name: "Show Library Shortcut", state: "off" },
    { entity_id: "select.pocket_music_overlay_style", domain: "select", name: "Overlay Style", state: "Art + Metadata", options: ["Art Only", "Art + Metadata"] },
    { entity_id: "select.pocket_music_album_art_style", domain: "select", name: "Album Art Style", state: "Full Screen", options: ["Full Screen", "Standard"] },
    { entity_id: "switch.pocket_music_show_speaker_shortcut", domain: "switch", name: "Show Speaker Shortcut", state: "on" },
    { entity_id: "select.pocket_music_podcast_sort_order", domain: "select", name: "Podcast Sort Order", state: "Newest on Top", options: ["Newest on Top"] },
    { entity_id: "select.pocket_music_album_sort_order", domain: "select", name: "Album Sort Order", state: "Alphabetical", options: ["Alphabetical"] },
  ];
  const soundSection = [
    { entity_id: "number.pocket_sound_speaker_volume", domain: "number", name: "Speaker Volume", state: "60", min: 10, max: 100, step: 5, unit: "%" },
  ];
  const voiceSection = [
    { entity_id: "select.pocket_voice_wake_word_mode", domain: "select", name: "Voice: Wake Word Mode", state: "On Device", options: ["Disabled", "On Device"] },
    { entity_id: "select.pocket_voice_visual_profile", domain: "select", name: "Voice: Visual Profile", state: "Nebula", options: ["Nebula", "Solaris", "Rings", "Light Bar", "Dot Wave"] },
    { entity_id: "switch.pocket_voice_wake_screen_on_assist", domain: "switch", name: "Voice: Wake Screen on Assist", state: "on" },
  ];
  return {
    host: null,
    activeSubentryId: "sub_1",
    uploadBusy: false,
    uploadScope: null,
    uploadPercent: 0,
    state: {
      config: {
        device_slug: "desk_panel",
        activity_card: true,
        wallpaper_cycle_minutes: cycleMins,
        display_shape: "square",
        default_page_size: 3,
        device_remote_group: remoteMode,
      },
      capabilities: { is_roaming_device: true },
      live: { ma_link_matched: true },
      system_config: {
        custom_palettes: [],
        remotes_list: ["remote.living_tv"],
        volume_overrides: [],
        remote_groups: [{ id: "living_tv", name: "Living Area TV", area_id: "living", remotes: ["remote.living_tv"] }],
      },
      system_devices: [
        { subentry_id: "sub_1", title: "Desk Panel", kind: "device", has_display: true, active_area_name: "Office", device_remote_group: remoteMode },
      ],
      catalog: { remotes: [{ id: "remote.living_tv", name: "Living TV" }], areas: [], ma_speakers: [] },
      wallpapers,
    },
    getSectionItems(sec) {
      if (sec === "home") return homeSection;
      if (sec === "display") return displaySection;
      if (sec === "sleep") return sleepSection;
      if (sec === "actions") return actionsSection;
      if (sec === "battery") return batterySection;
      if (sec === "music") return musicSection;
      if (sec === "sound") return soundSection;
      if (sec === "voice") return voiceSection;
      return [];
    },
    getEnabledActivitySources() { return ["calendar"]; },
    getEnabledDockTokens() { return ["area", "music"]; },
  };
}

const offMarkup = flattenHtml(renderDeviceDisplayView(makeStore({ cycleMins: 0, activeId: "", autoBrtState: "Disabled" })));
const staticMarkup = flattenHtml(renderDeviceDisplayView(makeStore({ cycleMins: 0, activeId: "preset:ocean_waves", autoBrtState: "Sun Synchronized" })));
const rotatingMarkup = flattenHtml(renderDeviceDisplayView(makeStore({ cycleMins: 5, activeId: "preset:ocean_waves", favIds: ["preset:forest_mountains", "preset:ocean_waves"], autoBrtState: "Time Schedule" })));
const powerMarkup = flattenHtml(renderDevicePowerView(makeStore({})));
const audioMarkup = flattenHtml(renderDeviceAudioView(makeStore({})));
const ifaceWeatherOn = flattenHtml(renderDeviceInterfaceView(makeStore({ weatherBgState: "Dynamic" })));
const ifaceWeatherOff = flattenHtml(renderDeviceInterfaceView(makeStore({ weatherBgState: "off" })));
const sysRemotesMarkup = flattenHtml(renderSystemRemotesView(makeStore({ remoteMode: "group:living_tv" })));

return { offMarkup, staticMarkup, rotatingMarkup, powerMarkup, audioMarkup, ifaceWeatherOn, ifaceWeatherOff, sysRemotesMarkup };
"""
        )
        got = _run_node_ts(
            [
                FRONTEND_SRC / "constants.ts",
                FRONTEND_SRC / "utils" / "format.ts",
                FRONTEND_SRC / "components" / "controls.ts",
                FRONTEND_SRC / "components" / "wallpaper-gallery.ts",
                FRONTEND_SRC / "views" / "device-display-view.ts",
                FRONTEND_SRC / "views" / "device-power-view.ts",
                FRONTEND_SRC / "views" / "device-audio-view.ts",
                FRONTEND_SRC / "views" / "device-interface-view.ts",
                FRONTEND_SRC / "views" / "system-remotes-view.ts",
            ],
            runner,
        )
        # 1. Display view (D-027 / D-029): Column 1 Brightness -> Voice Assistant -> Screensavers; Column 2 Colors -> Wallpapers
        for card_title in ("Brightness", "Voice Assistant", "Screensavers", "Colors", "Wallpapers"):
            self.assertIn(f'<h3 class="card-title">{card_title}</h3>', got["offMarkup"])
        self.assertNotIn("Brightness & Theme", got["offMarkup"])
        self.assertLess(got["offMarkup"].index('<h3 class="card-title">Brightness</h3>'), got["offMarkup"].index('<h3 class="card-title">Voice Assistant</h3>'))
        self.assertLess(got["offMarkup"].index('<h3 class="card-title">Voice Assistant</h3>'), got["offMarkup"].index("Visual Profile"))
        self.assertLess(got["offMarkup"].index("Visual Profile"), got["offMarkup"].index('<h3 class="card-title">Screensavers</h3>'))
        self.assertLess(got["offMarkup"].index('<h3 class="card-title">Screensavers</h3>'), got["offMarkup"].index('<h3 class="card-title">Colors</h3>'))
        self.assertLess(got["offMarkup"].index('<h3 class="card-title">Colors</h3>'), got["offMarkup"].index("Color Profile"))
        self.assertLess(got["offMarkup"].index("Color Profile"), got["offMarkup"].index("Custom Color"))
        self.assertLess(got["offMarkup"].index("Custom Color"), got["offMarkup"].index('<h3 class="card-title">Wallpapers</h3>'))
        self.assertNotIn("Wake Screen on Assist", got["offMarkup"])
        self.assertIn("Wake Screen on Assist", got["audioMarkup"])
        self.assertNotIn("Visual Profile", got["audioMarkup"])
        for saver_label in ("Docked Screensaver", "Screensaver Style", "Docked Idle Timeout", "Activate Screensaver", "Preview"):
            self.assertIn(saver_label, got["offMarkup"])
        self.assertIn('id="btn-enable-wp-rotation"', got["offMarkup"])
        self.assertNotIn('id="btn-turn-off-wp"', got["offMarkup"])
        self.assertNotIn('id="btn-stop-wp-rotation"', got["offMarkup"])
        self.assertNotIn("Screen Backlight", got["offMarkup"])
        self.assertNotIn("Clock Face", got["offMarkup"])
        self.assertNotIn("Start Screen", got["offMarkup"])
        self.assertIn("Manual Brightness", got["offMarkup"])
        self.assertNotIn("Day Brightness", got["offMarkup"])
        self.assertNotIn("Day Start Hour", got["offMarkup"])

        # 1b. Power view (D-027): Sleep & Wake keeps power/battery timeouts and excludes screensavers
        self.assertIn("Power Profile", got["powerMarkup"])
        self.assertIn("Battery Screen Timeout", got["powerMarkup"])
        self.assertIn("Battery Level", got["powerMarkup"])
        for saver_label in ("Docked Screensaver", "Screensaver Style", "Docked Idle Timeout"):
            self.assertNotIn(saver_label, got["powerMarkup"])

        # 2. Interface view: Start Screen, Clock Face, Sun & Moon pills, Media Player UI, and Remote Control Group selector
        self.assertIn("Start Screen", got["ifaceWeatherOn"])
        self.assertIn("Clock Face", got["ifaceWeatherOn"])
        self.assertLess(got["ifaceWeatherOn"].index("Start Screen"), got["ifaceWeatherOn"].index("Clock Face"))
        self.assertIn("id=weather-celestial-bodies", got["ifaceWeatherOn"])
        self.assertIn("✓ Sun", got["ifaceWeatherOn"])
        self.assertIn("+ Moon", got["ifaceWeatherOn"])
        self.assertLess(got["ifaceWeatherOn"].index("✓ Sun"), got["ifaceWeatherOn"].index("+ Moon"))
        self.assertIn('<h3 class="card-title">Media Player</h3>', got["ifaceWeatherOn"])
        self.assertIn("id=media-player-shortcuts", got["ifaceWeatherOn"])
        self.assertIn("✓ Speaker", got["ifaceWeatherOn"])
        self.assertIn("+ Library", got["ifaceWeatherOn"])
        self.assertLess(got["ifaceWeatherOn"].index("✓ Speaker"), got["ifaceWeatherOn"].index("+ Library"))
        self.assertNotIn("Show Speaker Shortcut", got["ifaceWeatherOn"])
        self.assertNotIn("Show Library Shortcut", got["ifaceWeatherOn"])
        self.assertNotIn("Show Speaker Shortcut", got["audioMarkup"])
        self.assertNotIn("Show Library Shortcut", got["audioMarkup"])
        self.assertIn("<summary>Library Sorting</summary>", got["ifaceWeatherOn"])
        for media_ui_label in (
            "Album Art Style",
            "Overlay Style",
            "Shortcuts",
            "Album Sort Order",
            "Podcast Sort Order",
        ):
            self.assertIn(media_ui_label, got["ifaceWeatherOn"])
            self.assertNotIn(media_ui_label, got["audioMarkup"])
        self.assertLess(got["ifaceWeatherOn"].index("Album Art Style"), got["ifaceWeatherOn"].index("Overlay Style"))
        self.assertLess(got["ifaceWeatherOn"].index("Overlay Style"), got["ifaceWeatherOn"].index("id=media-player-shortcuts"))
        self.assertLess(got["ifaceWeatherOn"].index("id=media-player-shortcuts"), got["ifaceWeatherOn"].index("Album Sort Order"))
        self.assertLess(got["ifaceWeatherOn"].index("Album Sort Order"), got["ifaceWeatherOn"].index("Podcast Sort Order"))
        self.assertIn('<h3 class="card-title">Sound &amp; Playback</h3>', got["audioMarkup"])
        self.assertIn("Speaker Volume", got["audioMarkup"])
        self.assertIn("id=cfg-device_remote_group", got["ifaceWeatherOn"])
        self.assertIn("Group: Living Area TV", got["ifaceWeatherOn"])
        self.assertNotIn("id=weather-celestial-bodies", got["ifaceWeatherOff"])

        # 3. System -> Media & Remotes: read-only assignment chip + Configure shortcut
        self.assertIn('<span class="chip">Group: Living Area TV</span>', got["sysRemotesMarkup"])
        self.assertIn("Configure remotes for Desk Panel", got["sysRemotesMarkup"])

        # 4. Static wallpaper + Sun Synchronized: Day/Night Brightness shown, Manual Brightness & Start Hours hidden
        self.assertIn('id="btn-enable-wp-rotation"', got["staticMarkup"])
        self.assertIn('id="btn-turn-off-wp"', got["staticMarkup"])
        self.assertNotIn('id="btn-stop-wp-rotation"', got["staticMarkup"])
        self.assertIn('<span class="chip chip-primary">Active</span>', got["staticMarkup"])
        self.assertNotIn("Manual Brightness", got["staticMarkup"])
        self.assertIn("Day Brightness", got["staticMarkup"])
        self.assertIn("Night Brightness", got["staticMarkup"])
        self.assertNotIn("Day Start Hour", got["staticMarkup"])

        # 5. Rotating wallpaper + Time Schedule: Day/Night Brightness & Start Hours shown
        self.assertIn('id="btn-stop-wp-rotation"', got["rotatingMarkup"])
        self.assertIn('id="btn-turn-off-wp"', got["rotatingMarkup"])
        self.assertIn('id="btn-clear-stars-wp"', got["rotatingMarkup"])
        self.assertNotIn('id="btn-star-all-wp"', got["rotatingMarkup"])
        self.assertNotIn("Manual Brightness", got["rotatingMarkup"])
        self.assertIn("Day Brightness", got["rotatingMarkup"])
        self.assertIn("Day Start Hour", got["rotatingMarkup"])
        self.assertIn("Night Start Hour", got["rotatingMarkup"])


@unittest.skipUnless(NODE, "node is not installed")
class TestWallpaperUploadBearerAuth(unittest.TestCase):
    """D-025: POST /api/latter/wallpaper/upload uses live hass.auth Bearer token, never auth/sign_path."""

    def test_xhr_bearer_header_preflight_refresh_and_401_retry(self) -> None:
        runner = """
return (async () => {
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

  // 1. Live token on System scope: direct Bearer POST, zero auth/sign_path WS calls
  nextResponses = [{ status: 200, body: { ok: true, source_id: "upload:_system/crater_1a2b3c.jpg" } }];
  const sysRes = await client.uploadWallpaperMultipart({
    scope: "system",
    file,
    onProgress: (p) => progress.push(p),
  });

  // 2. Expired token on Device scope: pre-flight refresh before sending XHR
  auth.expired = true;
  nextResponses = [{ status: 200, body: { ok: true, source_id: "upload:desk/crater_1a2b3c.jpg" } }];
  const devRes = await client.uploadWallpaperMultipart({
    scope: "device",
    subentryId: "sub_desk",
    file,
  });

  // 3. Clock-skew 401 when auth.expired === false: refreshes once and retries cleanly
  nextResponses = [
    { status: 401, body: null },
    { status: 200, body: { ok: true, source_id: "upload:_system/retry_ok.jpg" } },
  ];
  const skewRes = await client.uploadWallpaperMultipart({ scope: "system", file });

  // 4. Persistent 401 after single refresh retry: rejects cleanly without looping
  nextResponses = [{ status: 401, body: null }, { status: 401, body: null }];
  let persistentErr = "";
  try {
    await client.uploadWallpaperMultipart({ scope: "system", file });
  } catch (err) {
    persistentErr = err.message;
  }

  return { wsCalls, refreshCalls, progress, sysRes, devRes, skewRes, persistentErr, xhrLog };
})();
"""
        got = _run_node_ts(
            [FRONTEND_SRC / "constants.ts", FRONTEND_SRC / "api" / "ws-client.ts"],
            runner,
        )
        self.assertEqual(got["wsCalls"], [])
        self.assertEqual(got["refreshCalls"], 3)
        self.assertEqual(got["progress"], [50, 100])
        self.assertEqual(got["sysRes"]["source_id"], "upload:_system/crater_1a2b3c.jpg")
        self.assertEqual(got["devRes"]["source_id"], "upload:desk/crater_1a2b3c.jpg")
        self.assertEqual(got["skewRes"]["source_id"], "upload:_system/retry_ok.jpg")
        self.assertEqual(got["persistentErr"], "Wallpaper upload failed (HTTP 401)")
        self.assertEqual(
            got["xhrLog"],
            [
                {
                    "method": "POST",
                    "url": "/api/latter/wallpaper/upload",
                    "auth": "Bearer tok_live",
                    "scope": "system",
                    "subentryId": None,
                },
                {
                    "method": "POST",
                    "url": "/api/latter/wallpaper/upload",
                    "auth": "Bearer tok_refreshed_1",
                    "scope": "device",
                    "subentryId": "sub_desk",
                },
                {
                    "method": "POST",
                    "url": "/api/latter/wallpaper/upload",
                    "auth": "Bearer tok_refreshed_1",
                    "scope": "system",
                    "subentryId": None,
                },
                {
                    "method": "POST",
                    "url": "/api/latter/wallpaper/upload",
                    "auth": "Bearer tok_refreshed_2",
                    "scope": "system",
                    "subentryId": None,
                },
                {
                    "method": "POST",
                    "url": "/api/latter/wallpaper/upload",
                    "auth": "Bearer tok_refreshed_2",
                    "scope": "system",
                    "subentryId": None,
                },
                {
                    "method": "POST",
                    "url": "/api/latter/wallpaper/upload",
                    "auth": "Bearer tok_refreshed_3",
                    "scope": "system",
                    "subentryId": None,
                },
            ],
        )


@unittest.skipUnless(NODE, "node is not installed")
class TestToolsDiagnosticsView(unittest.TestCase):
    """D-027: Device Tools renders curated Diagnostics + collapsed Developer & Telemetry drawer without raw outbox blobs or All Entities."""

    def test_standard_diagnostics_parsed_telemetry_and_ble_tag_mode(self) -> None:
        stub_lit = """
const nothing = Symbol.for("latter.lit.nothing");
function html(strings, ...values) { return { _$litType$: 1, strings, values }; }
function flattenHtml(node) {
  if (node === null || node === undefined || node === nothing || typeof node === "boolean") return "";
  if (Array.isArray(node)) return node.map(flattenHtml).join("");
  if (typeof node === "object" && node._$litType$ === 1) {
    let out = "";
    for (let i = 0; i < node.strings.length; i += 1) {
      out += node.strings[i];
      if (i < node.values.length) {
        const v = node.values[i];
        out += typeof v === "function" ? "[fn]" : flattenHtml(v);
      }
    }
    return out;
  }
  return String(node);
}
"""
        runner = (
            stub_lit
            + """
function makeToolsStore(isBle = false) {
  const networkSection = isBle ? [] : [
    { entity_id: "update.desk_panel_firmware", domain: "update", name: "Firmware", state: "off" },
    { entity_id: "sensor.desk_panel_wifi_signal", domain: "sensor", name: "Wi-Fi Signal", state: "-54", unit: "dBm" },
    { entity_id: "sensor.desk_panel_ip_address", domain: "sensor", name: "IP Address", state: "192.168.1.44" },
    { entity_id: "sensor.desk_panel_connected_ssid", domain: "sensor", name: "Connected SSID", state: "HomeLAN" },
    { entity_id: "sensor.desk_panel_system_rpc_outbox", domain: "sensor", name: "System: RPC Outbox", state: '{"v":3,"cmd":"media_play","seq":99}' },
    {
      entity_id: "sensor.desk_panel_system_link_report",
      domain: "sensor",
      name: "System: Link Report",
      state: "up=7320 rst=POWERON bto=1 disc=2 rsn=0 rssi=-55/-62 n=120 wlk=0.0 ls=45 slp=78.5 awk=21.5 api=3 ha=2 gap=14 down=0 nvs=5/0/3",
    },
    {
      entity_id: "sensor.desk_panel_system_hardware_manifest",
      domain: "sensor",
      name: "System: Hardware Manifest",
      state: '{"v":2,"contract":3,"board":"waveshare_s3_square_4_0","w":480,"h":480,"shape":"square","display":1,"touch":1,"audio":1,"mic":1,"spk":1,"imu":1,"battery":0,"stationary":1,"wearable":0,"ips":1,"chip":"ESP32-S3","psram_mb":8,"minor":4}',
    },
  ];
  const developerSection = isBle ? [] : [
    { entity_id: "switch.desk_panel_system_telemetry_profiler", domain: "switch", name: "Telemetry Profiler", state: "off" },
    { entity_id: "button.desk_panel_system_log_memory_report", domain: "button", name: "Log Memory Report", state: "unknown" },
    { entity_id: "sensor.desk_panel_system_internal_ram_low_water", domain: "sensor", name: "Internal RAM Low Water", state: "64", unit: "kB" },
  ];
  return {
    hass: null,
    host: null,
    activeSubentryId: "sub_1",
    devicePinDraft: "",
    pinBusy: false,
    hasConfiguredSecurityPin: true,
    state: {
      title: isBle ? "Keychain Tag" : "Desk Panel",
      config: isBle
        ? { kind: "ble_tag", ble_target_address: "AA:BB:CC:11:22:33" }
        : { kind: "device", device_slug: "desk_panel", security_pin_policy: "auto" },
      live: isBle
        ? {}
        : { device_sw_version: "3.0.0", sdk_rev: "2026111202", effective_security_pin_policy: "require_pin" },
      links: isBle
        ? { entry_id: "ent_1" }
        : { entry_id: "ent_1", esphome_device_id: "esp_dev_1", latter_device_id: "lat_dev_1" },
      esphome: isBle ? {} : { device: { mac: "10:20:30:40:50:60" } },
      system_devices: [
        isBle
          ? { subentry_id: "sub_1", kind: "ble_tag", ble_survey_rows: [{ is_winner: true, effective_rssi: -68 }] }
          : { subentry_id: "sub_1", kind: "device", model_label: "Latter Square 4.0", wifi_rssi: -54, ip_address: "192.168.1.44" },
      ],
    },
    getSectionItems(sec) {
      if (sec === "network") return networkSection;
      if (sec === "developer") return developerSection;
      return [];
    },
  };
}

function makeOverviewStore(mode) {
  if (mode === "ble") {
    return {
      hass: null,
      host: null,
      activeSubentryId: "sub_ble",
      state: {
        config: { kind: "ble_tag", ble_target_address: "AA:BB:CC:11:22:33" },
        capabilities: {},
        live: { active_area_name: "Entryway", ble_closest_proxy: "Entry Proxy" },
        links: { entry_id: "ent_1" },
        esphome: {},
        device_groups: [],
        system_config: { remote_groups: [] },
        system_devices: [
          {
            subentry_id: "sub_ble",
            kind: "ble_tag",
            status_label: "Detected",
            has_assigned_area: false,
            ble_survey_rows: [{ is_winner: true, effective_rssi: -64, distance_m: 1.8 }],
          },
        ],
      },
      getSectionItems() { return []; },
    };
  }
  const isBattery = mode === "battery";
  return {
    hass: null,
    host: null,
    activeSubentryId: "sub_1",
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
        has_ble_beacon: isBattery,
        is_roaming_device: isBattery,
      },
      live: {
        active_area_name: "Kitchen",
        ble_closest_proxy: isBattery ? "Kitchen Proxy" : "",
        device_sw_version: "3.0.0",
        fw_update_available: !isBattery,
        group_sync_status: isBattery ? "customized" : "in_sync",
      },
      links: { entry_id: "ent_1", esphome_device_id: "esp_1" },
      esphome: { device: { sw_version: "3.0.0", model: "Pocket" } },
      device_groups: [{ id: "handhelds", name: "Handhelds" }],
      system_config: {
        remote_groups: [{ id: "living_tv", name: "Living Area TV", area_id: "living", remotes: ["remote.tv"] }],
      },
      system_devices: [
        {
          subentry_id: "sub_1",
          kind: "device",
          is_online: true,
          has_display: true,
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
    getSectionItems() { return []; },
  };
}

return {
  espMarkup: flattenHtml(renderDeviceToolsView(makeToolsStore(false))),
  bleMarkup: flattenHtml(renderDeviceToolsView(makeToolsStore(true))),
  ovBattery: flattenHtml(renderDeviceOverviewView(makeOverviewStore("battery"))),
  ovMainsUpdate: flattenHtml(renderDeviceOverviewView(makeOverviewStore("mains"))),
  ovBle: flattenHtml(renderDeviceOverviewView(makeOverviewStore("ble"))),
};
"""
        )
        got = _run_node_ts(
            [
                FRONTEND_SRC / "constants.ts",
                FRONTEND_SRC / "utils" / "format.ts",
                FRONTEND_SRC / "components" / "controls.ts",
                FRONTEND_SRC / "views" / "device-tools-view.ts",
                FRONTEND_SRC / "views" / "device-overview-view.ts",
            ],
            runner,
        )
        esp = got["espMarkup"]
        ble = got["bleMarkup"]
        ov_bat = got["ovBattery"]
        ov_mains = got["ovMainsUpdate"]
        ov_ble = got["ovBle"]

        # Standard Diagnostics summary (including Model & ESPHome Node moved from Overview) + zero raw RPC Outbox / All Entities
        self.assertIn("Model", esp)
        self.assertIn("Latter Square 4.0", esp)
        self.assertIn('id="diag-node-name"', esp)
        self.assertIn("desk_panel", esp)
        self.assertIn('id="diag-sdk-rev"', esp)
        self.assertIn("Firmware Version", esp)
        self.assertIn("v3.0.0", esp)
        self.assertIn("2026111202", esp)
        self.assertIn("192.168.1.44", esp)
        self.assertIn("10:20:30:40:50:60", esp)
        self.assertIn("Connected SSID", esp)
        self.assertIn("HomeLAN", esp)
        self.assertIn("Download Diagnostics", esp)
        self.assertIn("Open in ESPHome", esp)
        self.assertNotIn("All Entities", esp)
        self.assertNotIn("media_play", esp)
        self.assertNotIn("RPC Outbox", esp)

        # Collapsed Developer & Telemetry drawer with parsed Link Report & Hardware Manifest
        self.assertIn('<details class="sub-collapsible">', esp)
        self.assertIn("<summary>Developer &amp; Telemetry</summary>", esp)
        for label in (
            "Telemetry Profiler",
            "Log Memory Report",
            "Internal RAM Low Water",
            "Session Uptime",
            "2h 2m",
            "Last Reset",
            "POWERON",
            "Wi-Fi Disconnects",
            "2 (1 beacon timeouts)",
            "Wi-Fi Avg / Min",
            "-55 / -62 dBm",
            "HA Sessions",
            "2 (max gap 14s)",
            "Light Sleep Duty",
            "78.5% (45 cycles)",
            "NVS Flash Writes",
            "5 writes (0 erases, 3 ms max)",
            "Hardware Board",
            "waveshare_s3_square_4_0",
            "Processor & PSRAM",
            "ESP32-S3 • 8 MB PSRAM",
            "Display Panel",
            "480\u00d7480 square IPS",
            "Hardware Traits",
            "Touch, Mic, Speaker, IMU, Stationary",
        ):
            self.assertIn(label, esp)

        # BLE Tag mode: shows BLE Signal & BLE Target, hides Developer & Telemetry and Open in ESPHome
        self.assertIn("BLE Signal", ble)
        self.assertIn("-68 dBm", ble)
        self.assertIn("AA:BB:CC:11:22:33", ble)
        self.assertNotIn("Developer &amp; Telemetry", ble)
        self.assertNotIn("Open in ESPHome", ble)

        # Overview -> Status (D-029): header status chip, 2x2 tonal tiles, assignment rows, and retired low-value rows
        self.assertIn('class="status-tiles"', ov_bat)
        for expected in (
            "Online",
            "Current Area",
            "Kitchen",
            "Roaming • Kitchen Proxy",
            "Battery",
            "82%",
            "Charging",
            "--signal-pct:82%",
            "Wi-Fi Signal",
            "-58 dBm",
            "Excellent",
            "Firmware",
            "v3.0.0",
            "Up to date",
            "Device Group",
            "Handhelds",
            "Customized",
            "Remote Group",
            "Living Area TV",
            "Open in ESPHome",
            "Download Backup",
        ):
            self.assertIn(expected, ov_bat)
        for retired in ("Now Playing", "IP Address", "192.168.1.44", "Latter SDK", "ESPHome Node", "roaming_pocket"):
            self.assertNotIn(retired, ov_bat)

        # Plugged-in stationary Device with available firmware update + weak Wi-Fi
        for expected in ("Update available", "Office", "Stationary", "Power", "Plugged in", "Weak", "signal-fill low", "Follow Area"):
            self.assertIn(expected, ov_mains)
        self.assertNotIn("Mains", ov_mains)

        # BLE Tag Overview Status tiles
        for expected in ("Detected", "Entryway", "Closest Proxy", "Entry Proxy", "BLE Signal", "-64 dBm", "BLE Target", "AA:BB:CC:11:22:33"):
            self.assertIn(expected, ov_ble)
        self.assertNotIn("status-assignments", ov_ble)

    def test_presence_view_static_assigned_area_vs_ble_roaming_modes(self) -> None:
        """D-032: Presence renders Assigned Area when Static and Auto-Switch + Fallback Area when BLE Roaming."""
        stub_lit = """
const nothing = Symbol.for("latter.lit.nothing");
function html(strings, ...values) { return { _$litType$: 1, strings, values }; }
function flattenHtml(node) {
  if (node === null || node === undefined || node === nothing || typeof node === "boolean") return "";
  if (Array.isArray(node)) return node.map(flattenHtml).join("");
  if (typeof node === "object" && node._$litType$ === 1) {
    let out = "";
    for (let i = 0; i < node.strings.length; i += 1) {
      out += node.strings[i];
      if (i < node.values.length) {
        const v = node.values[i];
        out += typeof v === "function" ? "[fn]" : flattenHtml(v);
      }
    }
    return out;
  }
  return String(node);
}
"""
        runner = (
            stub_lit
            + """
function makePresenceStore(bleTracking) {
  return {
    hass: null,
    host: null,
    activeSubentryId: "sub_1",
    state: {
      config: {
        kind: "device",
        native_ble_tracking: bleTracking,
        ble_auto_switch: bleTracking,
        default_area: "living_room",
        ble_target_address: "",
        ble_beacon_uuid: "E2C56DB5-DFFB-48D2-B060-D0F5A71096E1",
      },
      catalog: {
        areas: [
          { value: "living_room", label: "Living Area" },
          { value: "kitchen", label: "Kitchen" },
        ],
      },
    },
    getSectionItems() {
      return [
        {
          entity_id: "pref:ble_beacon_mode",
          pref_key: "ble_beacon_mode",
          domain: "select",
          name: "BLE Beacon Mode",
          state: "Handheld Only",
          options: ["Handheld Only", "Handheld + Screen Off", "Always"],
        },
      ];
    },
  };
}
return {
  staticMarkup: flattenHtml(renderDevicePresenceView(makePresenceStore(false))),
  roamingMarkup: flattenHtml(renderDevicePresenceView(makePresenceStore(true))),
};
"""
        )
        got = _run_node_ts(
            [
                FRONTEND_SRC / "constants.ts",
                FRONTEND_SRC / "utils" / "format.ts",
                FRONTEND_SRC / "components" / "controls.ts",
                FRONTEND_SRC / "views" / "device-presence-view.ts",
            ],
            runner,
        )
        static_html = got["staticMarkup"]
        roaming_html = got["roamingMarkup"]

        self.assertIn("Track the Area with BLE Proxies", static_html)
        self.assertIn("Assigned Area", static_html)
        self.assertIn("— Unassigned —", static_html)
        self.assertNotIn("Auto-Switch Active Area", static_html)
        self.assertNotIn("Fallback Area", static_html)
        self.assertNotIn("BLE Beacon Mode", static_html)

        self.assertIn("Track the Area with BLE Proxies", roaming_html)
        self.assertIn("Auto-Switch Active Area", roaming_html)
        self.assertIn("Fallback Area", roaming_html)
        self.assertIn("— Automatic (ESPHome Area) —", roaming_html)
        self.assertIn("BLE Beacon Mode", roaming_html)
        self.assertNotIn("Assigned Area", roaming_html)


if __name__ == "__main__":
    unittest.main()
