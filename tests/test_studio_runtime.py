"""Studio runtime behavior verified directly against TypeScript modules via Node's stdlib TS stripper."""

from __future__ import annotations

import itertools
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
    cleaned = re.sub(r"^\s*export\s*\{[\s\S]*?\};?\s*$", "", cleaned, flags=re.MULTILINE)
    return re.sub(r"^\s*export\s+(?=(?:async\s+)?(?:function|const|let|class|interface|type)\b)", "", cleaned, flags=re.MULTILINE)


def _run_node_ts(ts_sources: list[Path], runner_js: str, preamble_js: str = "") -> object:
    """Strip TypeScript types via Node's built-in `module.stripTypeScriptTypes` and evaluate `runner_js`."""
    sources = list(ts_sources)
    mdi_catalog = FRONTEND_SRC / "mdi-catalog.ts"
    if mdi_catalog.exists() and mdi_catalog not in sources:
        sources.insert(0, mdi_catalog)
    proto_schema = FRONTEND_SRC / "protocol-schema.ts"
    if proto_schema.exists() and proto_schema not in sources:
        sources.insert(0, proto_schema)
    combined_ts = "\n\n".join(_strip_module_syntax(p.read_text(encoding="utf-8")) for p in sources)
    bootstrap = (
        "const { stripTypeScriptTypes } = require('node:module');\n"
        f"const tsSrc = {json.dumps(combined_ts)};\n"
        "const jsSrc = stripTypeScriptTypes(tsSrc);\n"
        f"const fn = new Function({json.dumps(preamble_js)} + '\\n' + jsSrc + '\\n' + {json.dumps(runner_js)});\n"
        "Promise.resolve(fn()).then((res) => process.stdout.write(JSON.stringify(res)));\n"
    )
    out = subprocess.run(
        [NODE, "-"],
        input=bootstrap,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if out.returncode != 0:
        raise RuntimeError(f"Node execution failed ({out.returncode}):\n{out.stderr}\n{out.stdout}")
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
            "other",
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
    { entity_id: "select.pocket_display_time_format", domain: "select", name: "Display: Time Format", state: "12-Hour (AM/PM)", options: ["12-Hour (AM/PM)", "24-Hour"] },
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
        area_categories: "scene,light",
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
    getPref(key) {
      if (this.state && Array.isArray(this.state.device_prefs)) {
        const found = this.state.device_prefs.find((p) => p.key === key);
        if (found) return found;
      }
      const all = [
        ...homeSection,
        ...displaySection,
        ...sleepSection,
        ...actionsSection,
        ...batterySection,
        ...musicSection,
        ...soundSection,
        ...voiceSection,
      ];
      const altKey = key.replace(/^va_/, "voice_").replace(/^music_/, "");
      for (const it of all) {
        if (
          it.pref_key === key ||
          it.key === key ||
          (it.entity_id && (
            it.entity_id.endsWith("_" + key) ||
            it.entity_id.endsWith("_" + altKey) ||
            it.entity_id.endsWith("_" + key.replace(/^va_/, ""))
          ))
        ) {
          return {
            key,
            label: it.name ? it.name.replace(/^Voice:\\s*/, "").replace(/^Display:\\s*/, "").replace(/^Home:\\s*/, "") : key,
            section: "",
            domain: it.domain,
            value: it.domain === "switch" ? it.state === "on" : it.state,
            options: it.options,
            min: it.min,
            max: it.max,
            step: it.step,
            unit: it.unit,
          };
        }
      }
      return undefined;
    },
    getPrefs(keys) {
      return (keys || []).map((k) => this.getPref(k)).filter(Boolean);
    },
    getEnabledActivitySources() { return ["calendar"]; },
    getDockItems() {
      return [
        { kind: "route", target: "app:area", action: "", label: "", icon: "", confirm: false },
        { kind: "route", target: "app:music", action: "", label: "", icon: "", confirm: false },
      ];
    },
    getPinnedItems() { return []; },
    getEnabledAreaCategories() { return ["scene", "light"]; },
    getEnabledHomeCategories() { return ["alarm", "thermostat", "entry", "vacuum"]; },
  };
}

const offMarkup = flattenHtml(renderDeviceDisplayView(makeStore({ cycleMins: 0, activeId: "", autoBrtState: "Disabled" })));
const dispWeatherOff = flattenHtml(renderDeviceDisplayView(makeStore({ weatherBgState: "off", cycleMins: 0, activeId: "", autoBrtState: "Disabled" })));
const staticMarkup = flattenHtml(renderDeviceDisplayView(makeStore({ cycleMins: 0, activeId: "preset:ocean_waves", autoBrtState: "Sun Synchronized" })));
const rotatingMarkup = flattenHtml(renderDeviceDisplayView(makeStore({ cycleMins: 5, activeId: "preset:ocean_waves", favIds: ["preset:forest_mountains", "preset:ocean_waves"], autoBrtState: "Time Schedule" })));
const powerMarkup = flattenHtml(renderDevicePowerView(makeStore({})));
const audioMarkup = flattenHtml(renderDeviceAudioView(makeStore({})));
const ifaceMarkup = flattenHtml(renderDeviceInterfaceView(makeStore({ weatherBgState: "Dynamic" })));
const sysRemotesMarkup = flattenHtml(renderSystemRemotesView(makeStore({ remoteMode: "group:living_tv" })));

return { offMarkup, dispWeatherOff, staticMarkup, rotatingMarkup, powerMarkup, audioMarkup, ifaceMarkup, sysRemotesMarkup };
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
        # 1. Display view (D-034): Col 1 Home Screen -> Screensavers -> Voice Assistant -> Brightness -> Clock; Col 2 Colors -> Wallpapers -> Media Player
        display_cards = (
            "Home Screen",
            "Screensavers",
            "Voice Assistant",
            "Brightness",
            "Clock",
            "Colors",
            "Wallpapers",
            "Media Player",
        )
        for card_title in display_cards:
            self.assertIn(f'<h3 class="card-title">{card_title}</h3>', got["offMarkup"])
        for earlier, later in itertools.pairwise(display_cards):
            self.assertLess(
                got["offMarkup"].index(f'<h3 class="card-title">{earlier}</h3>'),
                got["offMarkup"].index(f'<h3 class="card-title">{later}</h3>'),
            )
        self.assertNotIn("Brightness & Theme", got["offMarkup"])
        self.assertLess(got["offMarkup"].index('<h3 class="card-title">Home Screen</h3>'), got["offMarkup"].index("Wake Greeting"))
        self.assertLess(got["offMarkup"].index("Wake Greeting"), got["offMarkup"].index("Weather Background"))
        self.assertLess(got["offMarkup"].index("Weather Background"), got["offMarkup"].index("id=weather-celestial-bodies"))
        self.assertIn("✓ Sun", got["offMarkup"])
        self.assertIn("+ Moon", got["offMarkup"])
        self.assertLess(got["offMarkup"].index("✓ Sun"), got["offMarkup"].index("+ Moon"))
        self.assertNotIn("id=weather-celestial-bodies", got["dispWeatherOff"])
        self.assertLess(got["offMarkup"].index("id=weather-celestial-bodies"), got["offMarkup"].index('<h3 class="card-title">Screensavers</h3>'))
        self.assertLess(got["offMarkup"].index('<h3 class="card-title">Screensavers</h3>'), got["offMarkup"].index('<h3 class="card-title">Voice Assistant</h3>'))
        self.assertLess(got["offMarkup"].index('<h3 class="card-title">Voice Assistant</h3>'), got["offMarkup"].index("Visual Profile"))
        self.assertLess(got["offMarkup"].index("Visual Profile"), got["offMarkup"].index('<h3 class="card-title">Brightness</h3>'))
        self.assertLess(got["offMarkup"].index('<h3 class="card-title">Brightness</h3>'), got["offMarkup"].index('<h3 class="card-title">Clock</h3>'))
        self.assertLess(got["offMarkup"].index('<h3 class="card-title">Clock</h3>'), got["offMarkup"].index("Clock Face"))
        self.assertLess(got["offMarkup"].index("Clock Face"), got["offMarkup"].index("Time Format"))
        self.assertLess(got["offMarkup"].index("Time Format"), got["offMarkup"].index('<h3 class="card-title">Colors</h3>'))
        self.assertLess(got["offMarkup"].index('<h3 class="card-title">Colors</h3>'), got["offMarkup"].index("Color Profile"))
        self.assertLess(got["offMarkup"].index("Color Profile"), got["offMarkup"].index("Custom Color"))
        self.assertLess(got["offMarkup"].index("Custom Color"), got["offMarkup"].index('<h3 class="card-title">Wallpapers</h3>'))
        self.assertLess(got["offMarkup"].index('<h3 class="card-title">Media Player</h3>'), got["offMarkup"].index("Album Art Style"))
        self.assertLess(got["offMarkup"].index("Album Art Style"), got["offMarkup"].index("Overlay Style"))
        self.assertNotIn("Wake Screen on Assist", got["offMarkup"])
        self.assertIn("Wake Screen on Assist", got["audioMarkup"])
        self.assertNotIn("Visual Profile", got["audioMarkup"])
        for saver_label in ("Docked Screensaver", "Screensaver Style", "Docked Idle Timeout", "Activate Screensaver", "Preview"):
            self.assertIn(saver_label, got["offMarkup"])
        self.assertIn('id="btn-enable-wp-rotation"', got["offMarkup"])
        self.assertNotIn('id="btn-turn-off-wp"', got["offMarkup"])
        self.assertNotIn('id="btn-stop-wp-rotation"', got["offMarkup"])
        self.assertNotIn("Screen Backlight", got["offMarkup"])
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

        # 2. Interface view (D-033/D-034/D-047): navigation & structure only (Start Screen, App Dock, Pinned App, Area Categories pills, uncollapsed Library Sorting, Remote Control Group)
        self.assertIn("Start Screen", got["ifaceMarkup"])
        self.assertIn('id="dock-shortcuts-container"', got["ifaceMarkup"])
        self.assertIn('id="pinned-shortcuts-container"', got["ifaceMarkup"])
        self.assertIn('id="area-categories-pills"', got["ifaceMarkup"])
        self.assertIn("✓ Scenes", got["ifaceMarkup"])
        self.assertIn("✓ Lights", got["ifaceMarkup"])
        self.assertIn("+ All Devices", got["ifaceMarkup"])
        self.assertIn("categories with no entities in the active Area are not displayed", got["ifaceMarkup"])
        self.assertNotIn("Area Cards Per Page", got["ifaceMarkup"])
        self.assertNotIn("cfg-default_page_size", got["ifaceMarkup"])
        self.assertNotIn("Default Category", got["ifaceMarkup"])
        self.assertNotIn("Show All Category", got["ifaceMarkup"])
        for display_only_label in (
            "for=cfg-clock_face",
            ">Clock Face</label>",
            "Time Format",
            "Wake Greeting",
            "Weather Background",
            "id=weather-celestial-bodies",
            "Album Art Style",
            "Overlay Style",
        ):
            self.assertNotIn(display_only_label, got["ifaceMarkup"])
        self.assertIn("Home Time Tap", got["ifaceMarkup"])
        self.assertIn("id=cfg-home_clock_tap_action", got["ifaceMarkup"])
        self.assertIn("+ Time", got["ifaceMarkup"])
        self.assertIn('<h3 class="card-title">Time</h3>', got["ifaceMarkup"])
        self.assertIn("Local Clock Label", got["ifaceMarkup"])
        self.assertIn('id="cfg-local_clock_label"', got["ifaceMarkup"])
        self.assertIn("Show UTC Clock", got["ifaceMarkup"])
        self.assertIn('id="cfg-world_clock_new_label"', got["ifaceMarkup"])
        self.assertIn('id="cfg-world_clocks_add"', got["ifaceMarkup"])
        self.assertIn('id="btn-world_clock_add"', got["ifaceMarkup"])
        self.assertIn("UTC-12:00 — International Date Line West", got["ifaceMarkup"])
        self.assertIn("UTC-05:00 — Eastern Time (EST/EDT)", got["ifaceMarkup"])
        self.assertIn("UTC+14:00 — Line Islands Time (LINT)", got["ifaceMarkup"])
        self.assertLess(
            got["ifaceMarkup"].index("UTC-12:00 — International Date Line West"),
            got["ifaceMarkup"].index("UTC-05:00 — Eastern Time (EST/EDT)"),
        )
        self.assertLess(
            got["ifaceMarkup"].index("UTC-05:00 — Eastern Time (EST/EDT)"),
            got["ifaceMarkup"].index("UTC+14:00 — Line Islands Time (LINT)"),
        )
        self.assertNotIn("Defaults to selected zone city", got["ifaceMarkup"])
        self.assertNotIn('label="All Time Zones"', got["ifaceMarkup"])
        self.assertIn("id=cfg-alarm_1_time", got["ifaceMarkup"])
        self.assertIn('step="60"', got["ifaceMarkup"])
        self.assertIn('<h3 class="card-title">Media Player</h3>', got["ifaceMarkup"])
        self.assertIn("id=media-player-shortcuts", got["ifaceMarkup"])
        self.assertIn("✓ Speaker", got["ifaceMarkup"])
        self.assertIn("+ Library", got["ifaceMarkup"])
        self.assertLess(got["ifaceMarkup"].index("✓ Speaker"), got["ifaceMarkup"].index("+ Library"))
        self.assertNotIn("Show Speaker Shortcut", got["ifaceMarkup"])
        self.assertNotIn("Show Library Shortcut", got["ifaceMarkup"])
        self.assertNotIn("Show Speaker Shortcut", got["audioMarkup"])
        self.assertNotIn("Show Library Shortcut", got["audioMarkup"])
        self.assertNotIn("<summary>Library Sorting</summary>", got["ifaceMarkup"])
        for media_nav_label in (
            "Shortcuts",
            "Album Sort Order",
            "Podcast Sort Order",
        ):
            self.assertIn(media_nav_label, got["ifaceMarkup"])
            self.assertNotIn(media_nav_label, got["audioMarkup"])
        self.assertNotIn("Album Art Style", got["audioMarkup"])
        self.assertNotIn("Overlay Style", got["audioMarkup"])
        self.assertLess(got["ifaceMarkup"].index("id=media-player-shortcuts"), got["ifaceMarkup"].index("Album Sort Order"))
        self.assertLess(got["ifaceMarkup"].index("Album Sort Order"), got["ifaceMarkup"].index("Podcast Sort Order"))
        self.assertIn('<h3 class="card-title">Sound &amp; Playback</h3>', got["audioMarkup"])
        self.assertIn("Speaker Volume", got["audioMarkup"])
        self.assertIn("id=cfg-device_remote_group", got["ifaceMarkup"])
        self.assertIn("Group: Living Area TV", got["ifaceMarkup"])

        # 3. System -> Media & Remotes (D-042): Remote Controls, Speaker Volume Overrides & Remote Control Groups only (no Device Assignments card)
        for rem_card in ("Remote Controls", "Speaker Volume Overrides", "Remote Control Groups"):
            self.assertIn(f'<h3 class="card-title">{rem_card}</h3>', got["sysRemotesMarkup"])
        self.assertNotIn("Device Assignments", got["sysRemotesMarkup"])
        self.assertNotIn("device-remote-assignments-list", got["sysRemotesMarkup"])
        self.assertNotIn("Configure remotes for Desk Panel", got["sysRemotesMarkup"])

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
    getPref(key) {
      return undefined;
    },
    getPrefs(keys) {
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
            "Custom",
            "Manage Groups",
            "Remote Control Group",
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
    getPref(key) {
      if (key === "ble_beacon_mode") {
        return {
          key: "ble_beacon_mode",
          label: "BLE Beacon Mode",
          section: "presence",
          domain: "select",
          value: "Handheld Only",
          options: ["Handheld Only", "Handheld + Screen Off", "Always"],
        };
      }
      return undefined;
    },
    getPrefs(keys) {
      return (keys || []).map((k) => this.getPref(k)).filter(Boolean);
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

    def test_interface_view_home_screen_toggle_single_app_and_home_controls(self) -> None:
        """D-035: Disabling Home Screen hides Dock Apps, Return Timeout, and Activity Card, and excludes Home from Start Screen."""
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
function makeInterfaceStore(homeEnabled) {
  return {
    hass: null,
    host: null,
    activeSubentryId: "sub_1",
    state: {
      config: {
        kind: "device",
        home_screen_enabled: homeEnabled,
        start_screen: homeEnabled ? "Home" : "Home",
        return_to_home_timeout: "2 min",
        activity_card: true,
        dock_items: [
          { kind: "route", target: "app:pinned", action: "", label: "", icon: "", confirm: false },
          { kind: "route", target: "app:music", action: "", label: "", icon: "", confirm: false },
        ],
        pinned_items: [
          { kind: "entity", target: "script.baby_help", action: "turn_on", label: "Baby Help", icon: "mdi:baby-face-outline", confirm: false },
        ],
        local_clock_label: "Oakland",
        world_clocks: "Westminster|Europe/London;Kyoto|Asia/Tokyo",
        alarms_summary: "06:45|1|1;08:30|0|2;09:00|0|3",
        home_categories: "alarm,thermostat,entry",
        area_categories: "scene,light",
        device_remote_group: "area_auto",
      },
      system_config: { remote_groups: [] },
      system_devices: [{ subentry_id: "sub_1", device_remote_group: "area_auto" }],
    },
    getSectionItems(sec) {
      if (sec === "display") {
        return [
          {
            entity_id: "pref:home_screen_enabled",
            pref_key: "home_screen_enabled",
            domain: "switch",
            name: "Enable Home Screen",
            state: homeEnabled ? "on" : "off",
          },
          {
            entity_id: "pref:start_screen",
            pref_key: "start_screen",
            domain: "select",
            name: "Start Screen",
            state: homeEnabled ? "Home" : "Time App",
            options: START_SCREEN_OPTIONS,
          },
          {
            entity_id: "pref:return_to_home_timeout",
            pref_key: "return_to_home_timeout",
            domain: "select",
            name: "Return to Home Timeout",
            state: "2 min",
            options: RETURN_TO_HOME_TIMEOUT_OPTIONS,
          },
        ];
      }
      return [];
    },
    getPref(key) {
      const items = this.getSectionItems("display");
      const it = items.find((p) => p.pref_key === key || p.key === key);
      if (it) {
        return {
          key,
          label: it.name || key,
          section: "interface",
          domain: it.domain,
          value: it.domain === "switch" ? it.state === "on" : it.state,
          options: it.options,
        };
      }
      return undefined;
    },
    getPrefs(keys) {
      return (keys || []).map((k) => this.getPref(k)).filter(Boolean);
    },
    getDockItems() {
      return [
        { kind: "route", target: "app:pinned", action: "", label: "", icon: "", confirm: false },
        { kind: "route", target: "app:music", action: "", label: "", icon: "", confirm: false },
        { kind: "route", target: "weather:moon", action: "", label: "Moon Phase", icon: "", confirm: false },
      ];
    },
    getPinnedItems() {
      return [
        { kind: "entity", target: "script.baby_help", action: "turn_on", label: "Baby Help", icon: "mdi:baby-face-outline", confirm: false },
      ];
    },
    getEnabledHomeCategories() {
      return ["alarm", "thermostat", "entry"];
    },
    getEnabledAreaCategories() {
      return ["scene", "light"];
    },
    getEnabledActivitySources() {
      return ["calendar", "timers"];
    },
  };
}
return {
  enabledMarkup: flattenHtml(renderDeviceInterfaceView(makeInterfaceStore(true))),
  singleAppMarkup: flattenHtml(renderDeviceInterfaceView(makeInterfaceStore(false))),
};
"""
        )
        got = _run_node_ts(
            [
                FRONTEND_SRC / "constants.ts",
                FRONTEND_SRC / "utils" / "format.ts",
                FRONTEND_SRC / "components" / "controls.ts",
                FRONTEND_SRC / "components" / "wallpaper-gallery.ts",
                FRONTEND_SRC / "views" / "device-display-view.ts",
                FRONTEND_SRC / "views" / "device-interface-view.ts",
            ],
            runner,
        )
        enabled_html = got["enabledMarkup"]
        single_html = got["singleAppMarkup"]

        for expected in (
            "Enable Home Screen",
            "Start Screen",
            ".value=Home",
            "<option value=Home ?selected=>Home</option>",
            "Home Time Tap",
            "Return to Home Timeout",
            "App Dock",
            "Add Dock Item",
            "Reset Default Dock",
            "Moon Phase",
            "Pinned App",
            "Add Pinned Item",
            "Baby Help",
            "Page 1",
            "Show the Activity Card",
            "Activity Card Sources",
            "Home Controls",
            "✓ Security Alarm",
            "✓ Thermostat",
            "✓ Entry & Garage",
            "+ Robot Vacuum",
            'id="cfg-local_clock_label"',
            ".value=Oakland",
            'id="world-clocks-list"',
            ".value=Westminster",
            ".value=Kyoto",
            ".value=06:45",
        ):
            self.assertIn(expected, enabled_html)

        self.assertIn("Enable Home Screen", single_html)
        self.assertIn("Start Screen", single_html)
        self.assertIn(".value=Time App", single_html)
        self.assertIn("<option value=Pinned ?selected=>Pinned</option>", single_html)
        self.assertIn("<option value=Time App ?selected=>Time App</option>", single_html)
        self.assertIn("<option value=Clock Face ?selected=>Clock Face</option>", single_html)
        self.assertIn("<option value=Home Hub ?selected=>Home Hub</option>", single_html)
        self.assertNotIn("<option value=Home ?selected=>Home</option>", single_html)
        self.assertNotIn("Home Time Tap", single_html)
        self.assertNotIn("Return to Home Timeout", single_html)
        self.assertNotIn('id="dock-shortcuts-container"', single_html)
        self.assertNotIn("Add Dock Item", single_html)
        self.assertNotIn("Show the Activity Card", single_html)
        self.assertNotIn("Activity Card Sources", single_html)
        self.assertIn('<h3 class="card-title">Pinned App</h3>', single_html)
        self.assertIn("Home Controls", single_html)
        self.assertIn('<h3 class="card-title">Time</h3>', single_html)

    def test_time_card_focus_safe_typing_and_manual_world_clock_add(self) -> None:
        """D-039: Focused text inputs survive live WS re-renders, stop HA shortcut bubbling, and require manual World Clock labels."""
        runner = """
// 1. Verify PropertyPart in lib/lit.ts skips overwriting focused text inputs
const shadow = { activeElement: null };
const textInput = {
  tagName: "INPUT",
  type: "text",
  value: "M",
  getRootNode() { return shadow; },
};
const rangeInput = {
  tagName: "INPUT",
  type: "range",
  value: "40",
  getRootNode() { return shadow; },
};
const textPropPart = new PropertyPart(textInput, "value", 0);
shadow.activeElement = textInput;
// Simulate live ble_survey_delta re-render trying to reset .value back to ""
textPropPart.update([""]);
const preservedWhileFocused = textInput.value;
// Once blurred, external updates sync normally
shadow.activeElement = null;
textPropPart.update(["Synced"]);
const updatedAfterBlur = textInput.value;
// Non-text inputs (e.g. range) still update even when focused
const rangePropPart = new PropertyPart(rangeInput, "value", 0);
shadow.activeElement = rangeInput;
rangePropPart.update(["75"]);
const rangeUpdatedWhileFocused = rangeInput.value;

// 2. Verify ShadowRoot keydown isolation stops HA single-key shortcuts ('a', 'c', 'd', 'e', 'm') on INPUT
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

// 3. Verify UTC-12..UTC+14 catalog & manual city label flow in renderDeviceInterfaceView
const stagedCalls = [];
const toasts = [];
const domEls = {
  "cfg-world_clock_new_label": { value: "", focused: false, focus() { this.focused = true; } },
  "cfg-world_clocks_add": { value: "", focused: false, focus() { this.focused = true; } },
};
const store = {
  activeSubentryId: "sub_1",
  worldClockNewLabel: "",
  worldClockNewZone: "",
  requestCount: 0,
  host: {
    renderRoot: {
      getElementById(id) { return domEls[id] || null; },
    },
    requestUpdate() { store.requestCount += 1; },
  },
  state: {
    config: {
      kind: "device",
      home_screen_enabled: true,
      start_screen: "Home",
      return_to_home_timeout: "2 min",
      activity_card: true,
      dock_items: [],
      pinned_items: [],
      local_clock_label: "",
      world_clocks: "Westminster|Europe/London",
      alarms_summary: "07:00|0|1;08:30|0|2;09:00|0|2",
    },
    system_config: { remote_groups: [] },
    system_devices: [{ subentry_id: "sub_1", device_remote_group: "area_auto" }],
  },
  getSectionItems() { return []; },
  getPref() { return undefined; },
  getPrefs() { return []; },
  getDockItems() { return []; },
  getPinnedItems() { return []; },
  getEnabledHomeCategories() { return []; },
  getEnabledAreaCategories() { return []; },
  getEnabledActivitySources() { return []; },
  stageDeviceSetting(key, val, domId, debounceMs) {
    stagedCalls.push({ key, val, domId, debounceMs });
    store.state.config[key] = val;
  },
  flushAllPendingSettings() { return Promise.resolve(); },
  showToast(msg, isErr) { toasts.push({ msg, isErr: Boolean(isErr) }); },
};

// Walk TemplateResult tree to extract event handlers by element id
function collectHandlers(node, out = {}) {
  if (!node || typeof node !== "object") return out;
  if (Array.isArray(node)) {
    for (const item of node) collectHandlers(item, out);
    return out;
  }
  if (node._$litType$ === 1 && Array.isArray(node.strings)) {
    let raw = "";
    for (let i = 0; i < node.strings.length; i++) {
      raw += node.strings[i];
      if (i < node.values.length) {
        const v = node.values[i];
        if (typeof v === "function") {
          const idMatch = /id=(?:"([^"]+)"|([A-Za-z0-9_-]+))(?![\\s\\S]*<)/.exec(raw);
          const attrMatch = /@([a-z]+)=\\s*$/.exec(raw);
          const curId = idMatch ? (idMatch[1] || idMatch[2]) : null;
          if (curId && attrMatch) {
            out[curId] = out[curId] || {};
            out[curId][attrMatch[1]] = v;
          }
          raw += "__FN__";
        } else if (v && typeof v === "object") {
          collectHandlers(v, out);
          raw += "__TPL__";
        } else {
          raw += String(v ?? "");
        }
      }
    }
  }
  return out;
}

const tpl = renderDeviceInterfaceView(store);
const handlers = collectHandlers(tpl);

// Type "Main " (with trailing space!) into Local Clock Label — DOM .value must NOT be trimmed mid-typing
const localEl = { value: "Main " };
handlers["cfg-local_clock_label"].input({ currentTarget: localEl });
const localDomDuringTyping = localEl.value;

// Pick UTC-05:00 Eastern Time in #cfg-world_clocks_add — must NOT auto-populate label or stage world_clocks
domEls["cfg-world_clocks_add"].value = "America/New_York";
handlers["cfg-world_clocks_add"].change({ currentTarget: domEls["cfg-world_clocks_add"] });
const labelAfterZonePick = store.worldClockNewLabel;
const stagedWorldClocksAfterPick = stagedCalls.filter((c) => c.key === "world_clocks").length;

// Clicking Add without a city label shows toast & focuses New City Label
handlers["btn-world_clock_add"].click({});
const toastOnMissingCity = toasts[toasts.length - 1]?.msg || "";
const focusedLabelOnMissing = domEls["cfg-world_clock_new_label"].focused;

// Enter manual city "Akron, OH" and click Add
domEls["cfg-world_clock_new_label"].value = "Akron, OH";
handlers["cfg-world_clock_new_label"].input({ currentTarget: domEls["cfg-world_clock_new_label"] });
handlers["btn-world_clock_add"].click({});

return {
  preservedWhileFocused,
  updatedAfterBlur,
  rangeUpdatedWhileFocused,
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
  focusedLabelOnMissing,
  finalWorldClocks: store.state.config.world_clocks,
  clearedDraftLabel: store.worldClockNewLabel,
  clearedDraftZone: store.worldClockNewZone,
};
"""
        stub_lit_dom = (
            "globalThis.HTMLElement = class { attachShadow() { return {}; } toggleAttribute() {} };\n"
            "globalThis.customElements = { get: () => true, define: () => {} };\n"
            "function renderStudioDialogs() { return nothing; }\n"
            "function syncStudioDialogs() {}\n"
            "function renderActiveView() { return nothing; }\n"
            "const STUDIO_STYLES = { styleSheetText: '' };\n"
            "class StudioStore { constructor() {} addController() {} }\n"
        )
        got = _run_node_ts(
            [
                FRONTEND_SRC / "lib" / "lit.ts",
                FRONTEND_SRC / "constants.ts",
                FRONTEND_SRC / "utils" / "format.ts",
                FRONTEND_SRC / "components" / "controls.ts",
                FRONTEND_SRC / "views" / "device-interface-view.ts",
                FRONTEND_SRC / "latter-studio.ts",
            ],
            runner,
            preamble_js=stub_lit_dom,
        )
        self.assertEqual(got["preservedWhileFocused"], "M")
        self.assertEqual(got["updatedAfterBlur"], "Synced")
        self.assertEqual(got["rangeUpdatedWhileFocused"], "75")
        self.assertTrue(got["stopLetterA"])
        self.assertTrue(got["stopLetterC"])
        self.assertTrue(got["allowEscape"])
        self.assertTrue(got["allowTab"])
        self.assertTrue(got["allowCtrlC"])
        self.assertTrue(got["allowButtonKey"])
        self.assertEqual(got["firstCatalogZone"]["iana"], "Etc/GMT+12")
        self.assertTrue(got["firstCatalogZone"]["label"].startswith("UTC-12:00"))
        self.assertEqual(got["lastCatalogZone"]["iana"], "Pacific/Kiritimati")
        self.assertTrue(got["lastCatalogZone"]["label"].startswith("UTC+14:00"))
        self.assertEqual(got["localDomDuringTyping"], "Main ")
        self.assertEqual(
            got["localStagedCall"],
            {"key": "local_clock_label", "val": "Main", "domId": "cfg-local_clock_label", "debounceMs": 600},
        )
        self.assertEqual(got["labelAfterZonePick"], "")
        self.assertEqual(got["stagedWorldClocksAfterPick"], 0)
        self.assertIn("Enter a city or label", got["toastOnMissingCity"])
        self.assertTrue(got["focusedLabelOnMissing"])
        self.assertEqual(
            got["finalWorldClocks"],
            "Westminster|Europe/London;Akron, OH|America/New_York",
        )
        self.assertEqual(got["clearedDraftLabel"], "")
        self.assertEqual(got["clearedDraftZone"], "")

    def test_managed_and_discovered_lifecycle_views_and_badge(self) -> None:
        """D-041: Managed vs. Discovered sidebar, Option C badge, dynamic Managed card header, and stacked Discovered cards."""
        stub_lit = """
function flattenHtml(node) {
  if (node === null || node === undefined || node === nothing || typeof node === "boolean") return "";
  if (Array.isArray(node)) return node.map(flattenHtml).join("");
  if (typeof node === "object" && node._$litKeyed$ === 1) return flattenHtml(node.templates);
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
function makeFakeHost(storeOverrides) {
  const store = Object.assign(
    {
      currentScope: "device",
      currentViewId: "select_device_prompt",
      deviceSelected: false,
      activeSubentryId: "",
      deviceSortField: "title",
      deviceSortAsc: true,
      deviceCategoryFilter: "all",
      discoveredBleSearch: "",
      discoveredBleKindFilter: "all",
      discoveredBleSort: "name",
      discoveredBlePaused: false,
      discoveredBleFrozenSnapshot: null,
      discoveredBlePersonDrafts: new Map(),
      discoveredLatterGroupDrafts: new Map(),
      discoveredLatterPersonDrafts: new Map(),
      hass: null,
      host: { requestUpdate() {} },
      state: {
        title: "Desk Panel",
        capabilities: { has_display: true, has_audio: true, has_power: true },
        config: { kind: "device" },
        device_groups: [
          { id: "wall_panels", name: "Wall & Desk Panels" },
          { id: "handhelds", name: "Handhelds" },
        ],
        catalog: { persons: [{ id: "person.sean", name: "Sean" }] },
        system_devices: [
          {
            subentry_id: "sub_1",
            title: "Desk Panel",
            model_label: "Square 4.0 (480x480)",
            area_label: "Office",
            device_group: "wall_panels",
            device_group_name: "Wall & Desk Panels",
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
            status_label: "Online",
            is_online: true,
            is_latter_native: true,
            has_display: true,
            is_roaming: true,
            ble_tracked: true,
            assigned_person: "person.sean",
            kind: "device",
          },
        ],
        discovered_latter_devices: [],
        discovered_ble_devices: [
          {
            title: "Sean's Watch",
            target_address: "device_tracker.watch_ble",
            kind: "Private BLE (phone or watch)",
            rssi: -58,
            area_name: "Office",
          },
          {
            title: "Living TV BLE",
            target_address: "11:22:33:44:55:66",
            kind: "Named BLE device",
            rssi: -79,
            area_name: "Living Area",
          },
        ],
      },
      openDevicesLanding() {},
      openDiscoveredDevices() {},
      setScope() {},
      switchView() {},
      switchSystemDevice() {},
      openHaPage() {},
      openAddBleModal() {},
      adoptLatterDevice() {},
      quickAdoptBleCandidate() {},
    },
    storeOverrides || {},
  );
  return Object.assign(Object.create(LatterStudio.prototype), { store });
}

// 1. Option C badge: 0 Latter devices + 2 BLE devices -> NO #nav-discovered-count badge!
const hostZeroLatter = makeFakeHost();
const sidebarZeroLatter = flattenHtml(LatterStudio.prototype._renderSidebar.call(hostZeroLatter));

// 2. 1 unbound Latter device waiting -> #nav-discovered-count badge shows "1"!
const hostOneLatter = makeFakeHost();
hostOneLatter.store.state = Object.assign({}, hostOneLatter.store.state, {
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
});
const sidebarOneLatter = flattenHtml(LatterStudio.prototype._renderSidebar.call(hostOneLatter));

// 3. Single Device drill-down back button says "← Managed"
const hostDrilldown = makeFakeHost({ deviceSelected: true, currentViewId: "dashboard" });
const sidebarDrilldown = flattenHtml(LatterStudio.prototype._renderSidebar.call(hostDrilldown));

// 4. Managed Devices dynamic card <h3> reflects dropdown filter
const managedDefault = flattenHtml(renderDevicesListView(makeFakeHost({ deviceCategoryFilter: "all" }).store));
const managedRoaming = flattenHtml(renderDevicesListView(makeFakeHost({ deviceCategoryFilter: "roaming" }).store));
const managedDisplays = flattenHtml(renderDevicesListView(makeFakeHost({ deviceCategoryFilter: "native" }).store));
const managedGroup = flattenHtml(renderDevicesListView(makeFakeHost({ deviceCategoryFilter: "group:wall_panels" }).store));

// 5. Discovered Devices stacked cards + stable Name sort vs Signal strength sort + Pause List freeze + BLE search & tracker filter
const discAll = flattenHtml(renderDevicesDiscoveredView(hostOneLatter.store));
hostOneLatter.store.discoveredBleSort = "rssi";
const discSortRssi = flattenHtml(renderDevicesDiscoveredView(hostOneLatter.store));
hostOneLatter.store.discoveredBleSort = "name";
hostOneLatter.store.discoveredBlePaused = true;
hostOneLatter.store.discoveredBleFrozenSnapshot = [hostOneLatter.store.state.discovered_ble_devices[0]];
// Mutate live state while paused — frozen snapshot must keep only Sean's Watch and ignore Stray Beacon!
hostOneLatter.store.state.discovered_ble_devices.push({
  title: "Stray Neighbor Beacon",
  target_address: "99:88:77:66:55:44",
  kind: "Named BLE device",
  rssi: -40,
  area_name: "Kitchen",
});
const discPaused = flattenHtml(renderDevicesDiscoveredView(hostOneLatter.store));
hostOneLatter.store.discoveredBlePaused = false;
hostOneLatter.store.discoveredBleFrozenSnapshot = null;
hostOneLatter.store.state.discovered_ble_devices.pop();

hostOneLatter.store.discoveredBleKindFilter = "tracker";
const discTrackersOnly = flattenHtml(renderDevicesDiscoveredView(hostOneLatter.store));
hostOneLatter.store.discoveredBleKindFilter = "all";
hostOneLatter.store.discoveredBleSearch = "living tv";
const discSearch = flattenHtml(renderDevicesDiscoveredView(hostOneLatter.store));

return {
  sidebarZeroLatter,
  sidebarOneLatter,
  sidebarDrilldown,
  managedDefault,
  managedRoaming,
  managedDisplays,
  managedGroup,
  discAll,
  discSortRssi,
  discPaused,
  discTrackersOnly,
  discSearch,
};
"""
        )
        stub_lit_dom = (
            "globalThis.HTMLElement = class { attachShadow() { return {}; } toggleAttribute() {} };\n"
            "globalThis.customElements = { get: () => true, define: () => {} };\n"
            "function renderStudioDialogs() { return nothing; }\n"
            "function syncStudioDialogs() {}\n"
            "function renderActiveView() { return nothing; }\n"
            "const STUDIO_STYLES = { styleSheetText: '' };\n"
            "class StudioStore { constructor() {} addController() {} }\n"
        )
        got = _run_node_ts(
            [
                FRONTEND_SRC / "lib" / "lit.ts",
                FRONTEND_SRC / "constants.ts",
                FRONTEND_SRC / "utils" / "format.ts",
                FRONTEND_SRC / "components" / "controls.ts",
                FRONTEND_SRC / "views" / "devices-list-view.ts",
                FRONTEND_SRC / "views" / "devices-discovered-view.ts",
                FRONTEND_SRC / "latter-studio.ts",
            ],
            runner,
            preamble_js=stub_lit_dom,
        )

        # Sidebar Option C badge & labels
        self.assertIn("<span>Managed</span>", got["sidebarZeroLatter"])
        self.assertIn('id="nav-system-count" class="nav-badge">2</span>', got["sidebarZeroLatter"])
        self.assertIn("<span>Discovered</span>", got["sidebarZeroLatter"])
        self.assertNotIn("nav-discovered-count", got["sidebarZeroLatter"])

        self.assertIn('id="nav-discovered-count" class="nav-badge">1</span>', got["sidebarOneLatter"])
        self.assertIn("<span>&larr; Managed</span>", got["sidebarDrilldown"])
        self.assertNotIn("All Devices", got["sidebarDrilldown"])

        # Dynamic Managed Devices card header
        self.assertIn('<h3 class="card-title">All Devices</h3>', got["managedDefault"])
        self.assertIn('<h3 class="card-title">Roaming Devices</h3>', got["managedRoaming"])
        self.assertNotIn('<td class="col-name">Desk Panel</td>', got["managedRoaming"])
        self.assertIn('<td class="col-name">Pocket Assistant</td>', got["managedRoaming"])
        self.assertIn('<h3 class="card-title">Latter Displays</h3>', got["managedDisplays"])
        self.assertIn('<h3 class="card-title">Group: Wall & Desk Panels</h3>', got["managedGroup"])

        # Discovered Devices two stacked cards + stable Name default sort vs Signal strength + Pause List + filtering
        self.assertIn('<h3 class="card-title">Latter Devices</h3>', got["discAll"])
        self.assertIn('<h3 class="card-title">Bluetooth Devices</h3>', got["discAll"])
        self.assertLess(
            got["discAll"].index('<h3 class="card-title">Latter Devices</h3>'),
            got["discAll"].index('<h3 class="card-title">Bluetooth Devices</h3>'),
        )
        self.assertIn("Kitchen Panel", got["discAll"])
        self.assertIn("Auto (Wall & Desk Panels)", got["discAll"])
        self.assertIn("Pause List", got["discAll"])
        # Default Sort = Name (A-Z): "Living TV BLE" (-79 dBm) renders BEFORE "Sean's Watch" (-58 dBm)
        self.assertLess(
            got["discAll"].index("Living TV BLE"),
            got["discAll"].index("Sean's Watch"),
        )
        # Sort = Signal strength: "Sean's Watch" (-58 dBm) renders BEFORE "Living TV BLE" (-79 dBm)
        self.assertLess(
            got["discSortRssi"].index("Sean's Watch"),
            got["discSortRssi"].index("Living TV BLE"),
        )
        # Paused snapshot ignores newly pushed live BLE items and shows Resume List
        self.assertIn("Resume List", got["discPaused"])
        self.assertIn("List updates paused", got["discPaused"])
        self.assertIn("Sean's Watch", got["discPaused"])
        self.assertNotIn("Stray Neighbor Beacon", got["discPaused"])
        self.assertNotIn("Living TV BLE", got["discPaused"])

        self.assertIn("Sean's Watch", got["discTrackersOnly"])
        self.assertNotIn("Living TV BLE", got["discTrackersOnly"])

        self.assertNotIn("Sean's Watch", got["discSearch"])
        self.assertIn("Living TV BLE", got["discSearch"])

    def test_system_presence_walk_around_ux_and_ble_tracked_filter(self) -> None:
        """D-044 / D-045: System -> BLE & Area Presence Area boxes, smooth-scroll handoff, stream freeze, and inline Antenna Trim."""
        runner = """
return (async () => {
function flattenHtml(val) {
  if (val == null || val === false || val === true || typeof val === "symbol") return "";
  if (Array.isArray(val)) return val.map(flattenHtml).join("");
  if (typeof val === "object") {
    if (Array.isArray(val.strings) && Array.isArray(val.values)) {
      let out = "";
      for (let i = 0; i < val.strings.length; i += 1) {
        out += val.strings[i];
        if (i < val.values.length) {
          const prev = val.strings[i];
          const v = val.values[i];
          if (typeof v === "boolean" && /\\?[a-zA-Z0-9_-]+=$/.test(prev)) {
            out += String(v);
          } else {
            out += flattenHtml(v);
          }
        }
      }
      return out;
    }
    if (val._$litKeyed$ === 1 && Array.isArray(val.templates)) {
      return val.templates.map(flattenHtml).join("");
    }
  }
  return String(val);
}

function findButtonClickByText(node, buttonText) {
  if (!node || typeof node !== "object") return null;
  if (Array.isArray(node)) {
    for (const item of node) {
      const found = findButtonClickByText(item, buttonText);
      if (found) return found;
    }
    return null;
  }
  if (node._$litKeyed$ === 1 && Array.isArray(node.templates)) {
    return findButtonClickByText(node.templates, buttonText);
  }
  if (Array.isArray(node.strings) && Array.isArray(node.values)) {
    for (let i = 0; i < node.values.length; i += 1) {
      const v = node.values[i];
      if (
        typeof v === "function" &&
        node.strings[i].includes("@click=") &&
        (node.strings[i + 1] || "").includes(buttonText)
      ) {
        return v;
      }
      const nested = findButtonClickByText(v, buttonText);
      if (nested) return nested;
    }
  }
  return null;
}

const scrolledCalls = [];
const focusedCalls = [];
globalThis.requestAnimationFrame = (cb) => cb();

const fakeHost = {
  isConnected: true,
  requestUpdate() {},
  addController() {},
  removeController() {},
  updateComplete: Promise.resolve(true),
  renderRoot: {
    getElementById(id) {
      return {
        id,
        scrollIntoView(opts) { scrolledCalls.push({ id, opts: opts || null }); },
        focus(opts) { focusedCalls.push({ id, opts: opts || null }); },
      };
    },
  },
};

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

const baseState = {
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
    {
      area_id: "bedroom",
      area_name: "Bedroom",
      floor_id: "upstairs",
      has_ble_proxy: true,
      has_signature: true,
      scanner_count: 2,
      sample_count: 18,
      captured_at: "2026-11-16T20:00:00Z",
    },
    {
      area_id: "office",
      area_name: "Office",
      floor_id: "downstairs",
      has_ble_proxy: false,
      has_signature: false,
      scanner_count: 0,
      sample_count: 0,
      captured_at: "",
    },
    {
      area_id: "guest_bath",
      area_name: "Guest Bath",
      floor_id: "downstairs",
      has_ble_proxy: false,
      has_signature: false,
      scanner_count: 0,
      sample_count: 0,
      captured_at: "",
    },
  ],
  live: {
    area_presence_grid: [
      {
        area_id: "bedroom",
        area_name: "Bedroom",
        floor_name: "Upstairs",
        is_occupied: true,
        confidence_pct: 84,
        occupant_names: ["Sean"],
        winning_rssi: -57,
        closest_distance_m: 1.2,
        match_method: "signature",
        fusion_mode: "weighted",
        fusion_threshold_pct: 50,
        fusion_sensors: [],
        fusion_sensor_choices: [],
      },
    ],
  },
};

const wsCalls = [];
const subCalls = [];
const store = new StudioStore(fakeHost);
store.ws.hass = { locale: { language: "en" }, config: { unit_system: { length: "km" } } };
store.ws.runSystemCommand = async (command, payload) => {
  wsCalls.push({ command, payload });
  if (command === "capture_ble_area_signature") {
    return {
      ...structuredClone(store.state),
      ble_area_signatures: store.state.ble_area_signatures.map((s) =>
        s.area_id === payload.area_id
          ? { ...s, has_signature: true, scanner_count: 2, sample_count: 10, captured_at: "2026-11-16T22:00:00Z" }
          : s,
      ),
    };
  }
  if (command === "set_ble_scanner_offset") {
    return {
      ...structuredClone(store.state),
      system_devices: [
        structuredClone(deskUntracked),
        {
          ...structuredClone(pocketTracked),
          ble_packets_seen: 300,
          active_area_name: "Garage",
          ble_survey_rows: [
            {
              ...structuredClone(pocketTracked.ble_survey_rows[0]),
              raw_rssi: -40,
              offset_db: payload.offset_db,
              effective_rssi: -58 + payload.offset_db,
            },
            structuredClone(pocketTracked.ble_survey_rows[1]),
          ],
        },
        structuredClone(keyringTag),
      ],
    };
  }
  return structuredClone(store.state);
};
store.ensureSubscription = async (force = false) => {
  subCalls.push(Boolean(force));
};
store.showToast = () => {};
store.activeSubentryId = "sub_desk";
store.bleSurveySubentryId = "sub_desk";
store.ingestPayload(structuredClone(baseState), false);

const defaultSurveyAfterFilter = store.bleSurveySubentryId;
const activeRendered = flattenHtml(renderSystemPresenceView(store));

// 1. Calibrate handoff: smooth scroll #card-ble-calibration + preventScroll focus + warning highlight + Dismiss & Capture clear
store.selectBleCalibrateArea("office", true);
const handoffActiveAfterSelect = store.bleCalibrateHandoffActive;
const handoffTpl = renderSystemPresenceView(store);
const afterBridgeRendered = flattenHtml(handoffTpl);
const dismissHandler = findButtonClickByText(handoffTpl, "Dismiss");
if (dismissHandler) dismissHandler();
const handoffAfterDismiss = store.bleCalibrateHandoffActive;
const afterDismissRendered = flattenHtml(renderSystemPresenceView(store));

store.selectBleCalibrateArea("office", true);
const handoffBeforeCapture = store.bleCalibrateHandoffActive;
await store.captureBleAreaSignature("office");
const handoffAfterCapture = store.bleCalibrateHandoffActive;

// 2. Inline per-proxy Antenna Trim scoped to a single proxy via openProxyTrims
store.openProxyTrims.add("AA:BB:CC:DD:EE:01");
const oneProxyTrimOpenRendered = flattenHtml(renderSystemPresenceView(store));
store.openProxyTrims.clear();

// 3. Stream pause freeze across applyBleSurveyDelta & ingestPayload + manual trim update + resume
subCalls.length = 0;
store.toggleBleLiveStream(false);
const pausedRendered = flattenHtml(renderSystemPresenceView(store));
const frozenSizeWhilePaused = store.bleSurveyFrozen.size;

store.applyBleSurveyDelta({
  type: "ble_survey_delta",
  subentry_id: "sub_pocket",
  ble_packets_seen: 99,
  ble_survey_rows: [
    {
      area_id: "kitchen",
      area_name: "Kitchen",
      scanner_source: "AA:BB:CC:DD:EE:99",
      scanner_name: "Kitchen Proxy",
      raw_rssi: -42,
      effective_rssi: -42,
      offset_db: 0,
      distance_m: 0.5,
      age_seconds: 0,
      is_fresh: true,
      is_winner: true,
    },
  ],
});
const afterPausedDeltaDev = structuredClone(store.getActiveSurveyDevice());

store.ingestPayload(
  {
    ...structuredClone(store.state),
    system_devices: [
      structuredClone(deskUntracked),
      {
        ...structuredClone(pocketTracked),
        ble_packets_seen: 250,
        active_area_name: "Garage",
        ble_survey_rows: [
          {
            area_id: "garage",
            area_name: "Garage",
            scanner_source: "AA:BB:CC:DD:EE:88",
            scanner_name: "Garage Proxy",
            raw_rssi: -49,
            effective_rssi: -49,
            offset_db: 0,
            distance_m: 0.8,
            age_seconds: 1,
            is_fresh: true,
            is_winner: true,
          },
        ],
      },
      structuredClone(keyringTag),
    ],
  },
  false,
);
const afterPausedIngestDev = structuredClone(store.getActiveSurveyDevice());

await store.setBleScannerOffset("AA:BB:CC:DD:EE:01", 3.0);
const afterPausedManualTrimDev = structuredClone(store.getActiveSurveyDevice());

subCalls.length = 0;
store.toggleBleLiveStream(true);
const frozenSizeAfterResume = store.bleSurveyFrozen.size;
const subCallsOnResume = [...subCalls];

store.applyBleSurveyDelta({
  type: "ble_survey_delta",
  subentry_id: "sub_pocket",
  ble_packets_seen: 42,
  ble_survey_rows: [
    {
      area_id: "kitchen",
      area_name: "Kitchen",
      scanner_source: "AA:BB:CC:DD:EE:99",
      scanner_name: "Kitchen Proxy",
      raw_rssi: -44,
      effective_rssi: -44,
      offset_db: 0,
      distance_m: 0.6,
      age_seconds: 0,
      is_fresh: true,
      is_winner: true,
    },
  ],
});
const afterResumedDeltaDev = structuredClone(store.getActiveSurveyDevice());

store.ingestPayload(
  {
    ...structuredClone(store.state),
    system_devices: [
      structuredClone(deskUntracked),
      {
        ...structuredClone(pocketTracked),
        ble_packets_seen: 55,
        active_area_name: "Office",
      },
      structuredClone(keyringTag),
    ],
  },
  false,
);
const afterResumedIngestDev = structuredClone(store.getActiveSurveyDevice());

// 4. Zero BLE-tracked devices -> empty state + Open Discovered Devices
const storeZeroBle = new StudioStore(fakeHost);
storeZeroBle.ws.hass = store.ws.hass;
storeZeroBle.ensureSubscription = async () => {};
storeZeroBle.ingestPayload(
  {
    ...structuredClone(baseState),
    system_devices: [structuredClone(deskUntracked)],
  },
  false,
);
const emptyBleRendered = flattenHtml(renderSystemPresenceView(storeZeroBle));

return {
  defaultSurveyAfterFilter,
  activeSurveyId: store.getActiveSurveyDevice()?.subentry_id || "",
  scrolledCalls,
  focusedCalls,
  wsCalls,
  bleCalibrateAreaId: store.bleCalibrateAreaId,
  handoffActiveAfterSelect,
  handoffAfterDismiss,
  handoffBeforeCapture,
  handoffAfterCapture,
  activeRendered,
  afterBridgeRendered,
  afterDismissRendered,
  oneProxyTrimOpenRendered,
  pausedRendered,
  frozenSizeWhilePaused,
  afterPausedDeltaDev,
  afterPausedIngestDev,
  afterPausedManualTrimDev,
  frozenSizeAfterResume,
  subCallsOnResume,
  afterResumedDeltaDev,
  afterResumedIngestDev,
  emptyBleSurveyId: storeZeroBle.bleSurveySubentryId,
  emptyBleRendered,
};
})();
"""
        stub_deps = (
            "globalThis.HTMLElement = class { attachShadow() { return {}; } toggleAttribute() {} };\n"
            "function navigateHaPath() {}\n"
            "class StudioWsClient {}\n"
            "function formatWsError(_e, f) { return f; }\n"
            + "".join(
                f"function {fn}() {{}}\n"
                for fn in (
                    "adoptLatterDeviceOp",
                    "checkSystemUpdatesOp",
                    "clearInternalLogsOp",
                    "clearSecurityPinOp",
                    "confirmAddBleModalOp",
                    "confirmRemoveDeviceOp",
                    "confirmResetDeviceOp",
                    "copyLogsToClipboardOp",
                    "downloadDeviceDiagnosticsOp",
                    "exportBackupOp",
                    "formatVisibleLogsOp",
                    "openColorWheelModalOp",
                    "quickAdoptBleCandidateOp",
                    "restoreFromUploadedFileOp",
                    "rotateSigningKeyOp",
                    "saveColorWheelSelectionOp",
                    "saveSecurityPinOp",
                    "selectBleCandidateInModalOp",
                    "sendAnnouncementOp",
                    "addRemoteGroupRowOp",
                    "addStringListRowOp",
                    "addVolumeOverrideRowOp",
                    "applyDeviceCustomColorOp",
                    "commitEntityChange",
                    "deleteCustomPaletteOp",
                    "deleteWallpaperOp",
                    "executeEntityActionOp",
                    "flushDeviceBucketOp",
                    "flushSystemSettingsOp",
                    "getDockItemsOp",
                    "getEnabledActivitySourcesOp",
                    "getEnabledAreaCategoriesOp",
                    "getEnabledHomeCategoriesOp",
                    "getPinnedItemsOp",
                    "moveAreaCategoryTokenOp",
                    "moveHomeCategoryTokenOp",
                    "moveShortcutItemOp",
                    "openShortcutModalOp",
                    "overlayDevicePrefsOnSections",
                    "overlayPendingBlankListSlots",
                    "overlayPendingEntityStates",
                    "previewCameraOp",
                    "removeRemoteGroupRowOp",
                    "removeShortcutItemOp",
                    "removeStringListRowOp",
                    "removeVolumeOverrideRowOp",
                    "resetDockItemsToDefaultOp",
                    "runDeviceActionOp",
                    "saveShortcutModalOp",
                    "selectWallpaperSourceOp",
                    "setAllWallpaperFavoritesOp",
                    "setWallpaperRotationOp",
                    "stageDeviceSettingOp",
                    "stageSystemSettingOp",
                    "testDoorbellSpeakerOp",
                    "toggleActivitySourceOp",
                    "toggleAreaCategoryTokenOp",
                    "toggleHomeCategoryTokenOp",
                    "toggleRemoteInGroupOp",
                    "toggleWallpaperFavOp",
                    "updateRemoteGroupFieldOp",
                    "updateStringListRowOp",
                    "updateVolumeOverrideRowOp",
                    "uploadWallpaperOp",
                )
            )
            + "const PENDING_ENTITY_STATES = new Map();\n"
        )
        got = _run_node_ts(
            [
                FRONTEND_SRC / "lib" / "lit.ts",
                FRONTEND_SRC / "constants.ts",
                FRONTEND_SRC / "utils" / "format.ts",
                FRONTEND_SRC / "components" / "controls.ts",
                FRONTEND_SRC / "state" / "groups-presence-ops.ts",
                FRONTEND_SRC / "state" / "store.ts",
                FRONTEND_SRC / "views" / "system-presence-view.ts",
            ],
            runner,
            preamble_js=stub_deps,
        )

        # Untracked stationary display (has_ble=true, ble_tracked=false) is excluded cleanly
        self.assertEqual(got["defaultSurveyAfterFilter"], "sub_pocket")
        self.assertEqual(got["activeSurveyId"], "sub_pocket")
        self.assertNotIn("Desk Assistant", got["activeRendered"])
        self.assertIn("Pocket Assistant (Bedroom)", got["activeRendered"])
        self.assertIn("Keyring Tag (Kitchen)", got["activeRendered"])

        # D-045 (1): Enclosed Area boxes use neutral border (no .area-presence-box.occupied blue outline)
        self.assertIn('class="area-presence-box"', got["activeRendered"])
        self.assertNotIn("area-presence-box occupied", got["activeRendered"])
        self.assertIn('<span class="area-box-title">Bedroom</span>', got["activeRendered"])
        self.assertIn("Occupied • 84%", got["activeRendered"])
        self.assertIn('<span class="chip">Upstairs</span>', got["activeRendered"])
        self.assertIn("Signature (2 Proxies)", got["activeRendered"])
        self.assertIn("Clear Signature", got["activeRendered"])
        self.assertIn('<span class="area-box-title">Guest Bath</span>', got["activeRendered"])
        self.assertIn('<span class="chip chip-warning">No BLE Proxy</span>', got["activeRendered"])
        self.assertIn("calibrate with a carried Device to detect BLE presence here", got["activeRendered"])

        # Area-first Nearby Bluetooth Proxies + Unassigned warning chip + Live signal banner
        self.assertIn("Live BLE signal active", got["activeRendered"])
        self.assertIn('<span class="row-label">Bedroom</span>', got["activeRendered"])
        self.assertIn('<span class="chip">Bedroom Proxy</span>', got["activeRendered"])
        self.assertIn('<span class="chip chip-primary">Active Winner</span>', got["activeRendered"])
        self.assertIn('<span class="row-label">Unassigned Proxy</span>', got["activeRendered"])
        self.assertIn('<span class="chip chip-warning">Assign Area in HA</span>', got["activeRendered"])

        # D-045 (2): Calibrate handoff sets bleCalibrateHandoffActive, smooth-scrolls #card-ble-calibration,
        # calls focus({ preventScroll: true }) on #ble-calibrate-area-select, renders warning banner, and clears on Dismiss / Capture
        self.assertEqual(got["bleCalibrateAreaId"], "office")
        self.assertTrue(got["handoffActiveAfterSelect"])
        self.assertEqual(
            got["scrolledCalls"][0],
            {"id": "card-ble-calibration", "opts": {"behavior": "smooth", "block": "start"}},
        )
        self.assertEqual(
            got["focusedCalls"][0],
            {"id": "ble-calibrate-area-select", "opts": {"preventScroll": True}},
        )
        self.assertNotIn("handoff-active", got["activeRendered"])
        self.assertNotIn("ble-calibrate-handoff-banner", got["activeRendered"])
        self.assertIn('class="calibrate-target-box handoff-active"', got["afterBridgeRendered"])
        self.assertIn('id="ble-calibrate-handoff-banner"', got["afterBridgeRendered"])
        self.assertIn(
            "Ready to calibrate Office — carry Pocket Assistant into Office and click Calibrate Area.",
            got["afterBridgeRendered"],
        )
        self.assertIn(
            "Captures readings from surrounding Bluetooth proxies so Office detects presence without a local proxy.",
            got["afterBridgeRendered"],
        )
        self.assertFalse(got["handoffAfterDismiss"])
        self.assertNotIn("handoff-active", got["afterDismissRendered"])
        self.assertNotIn("ble-calibrate-handoff-banner", got["afterDismissRendered"])
        self.assertTrue(got["handoffBeforeCapture"])
        self.assertFalse(got["handoffAfterCapture"])
        self.assertEqual(
            got["wsCalls"][0],
            {
                "command": "capture_ble_area_signature",
                "payload": {"area_id": "office", "survey_subentry_id": "sub_pocket"},
            },
        )

        # D-045 (3): toggleBleLiveStream(false) snapshots bleSurveyFrozen across delta & ingestPayload,
        # allows manual scanner trim feedback, and toggleBleLiveStream(true) clears freeze & resumes live updates
        self.assertIn("Stream Paused", got["pausedRendered"])
        self.assertGreaterEqual(got["frozenSizeWhilePaused"], 1)
        for frozen_dev in (got["afterPausedDeltaDev"], got["afterPausedIngestDev"]):
            self.assertEqual(frozen_dev["ble_packets_seen"], 14)
            self.assertEqual(frozen_dev["active_area_name"], "Bedroom")
            self.assertEqual(
                [r["scanner_name"] for r in frozen_dev["ble_survey_rows"]],
                ["Bedroom Proxy", "Hallway Plug"],
            )
            self.assertEqual(frozen_dev["ble_survey_rows"][0]["effective_rssi"], -57)
        # Manual trim while paused updates ONLY that scanner's offset_db & effective_rssi without unfreezing raw_rssi or packets_seen
        self.assertEqual(got["afterPausedManualTrimDev"]["ble_packets_seen"], 14)
        self.assertEqual(got["afterPausedManualTrimDev"]["active_area_name"], "Bedroom")
        self.assertEqual(got["afterPausedManualTrimDev"]["ble_survey_rows"][0]["offset_db"], 3.0)
        self.assertEqual(got["afterPausedManualTrimDev"]["ble_survey_rows"][0]["effective_rssi"], -55)
        self.assertEqual(got["afterPausedManualTrimDev"]["ble_survey_rows"][0]["raw_rssi"], -58)
        # Resuming live stream clears bleSurveyFrozen and accepts subsequent delta + ingestPayload updates
        self.assertEqual(got["frozenSizeAfterResume"], 0)
        self.assertEqual(got["subCallsOnResume"], [True])
        self.assertEqual(got["afterResumedDeltaDev"]["ble_packets_seen"], 42)
        self.assertEqual(got["afterResumedDeltaDev"]["active_area_name"], "Kitchen")
        self.assertEqual(
            [r["scanner_name"] for r in got["afterResumedDeltaDev"]["ble_survey_rows"]],
            ["Kitchen Proxy"],
        )
        self.assertEqual(got["afterResumedIngestDev"]["ble_packets_seen"], 55)
        self.assertEqual(got["afterResumedIngestDev"]["active_area_name"], "Office")

        # D-045 (4): Inline per-proxy Antenna Trim inside .signal-row with zero duplicate proxy list
        trim_markup = got["oneProxyTrimOpenRendered"]
        self.assertNotIn("ble-proxy-trim-drawer", trim_markup)
        self.assertNotIn("Proxy Antenna Trim", trim_markup)
        self.assertEqual(trim_markup.count("<summary>Antenna Trim</summary>"), 2)
        self.assertEqual(trim_markup.count('<span class="chip">Bedroom Proxy</span>'), 1)
        self.assertEqual(trim_markup.count('<span class="chip">Hallway Plug</span>'), 1)
        proxies_section = trim_markup[trim_markup.index("Nearby Bluetooth Proxies") :]
        open_flags = re.findall(r"<details\s+\?open=(true|false)", proxies_section)
        self.assertEqual(open_flags, ["true", "false"])

        # Zero BLE-tracked devices -> empty state + Open Discovered Devices
        self.assertEqual(got["emptyBleSurveyId"], "")
        self.assertIn(
            "No Devices currently have Bluetooth Area tracking enabled.",
            got["emptyBleRendered"],
        )
        self.assertIn("Open Discovered Devices", got["emptyBleRendered"])


@unittest.skipUnless(NODE, "node is not installed")
class TestDeviceGroupsAndCustomFlow(unittest.TestCase):
    """D-048: Enclosed Device Groups boxes, Batch Controls live state, Managed Devices filter diet, and Save Custom Group modal."""

    def test_groups_boxes_batch_controls_overview_assignments_and_save_custom_modal(self) -> None:
        runner = """
return (async () => {
function flattenHtml(val) {
  if (val === null || val === undefined || typeof val === "symbol") return "";
  if (Array.isArray(val)) return val.map(flattenHtml).join("");
  if (typeof val === "object") {
    if (Array.isArray(val.strings) && Array.isArray(val.values)) {
      let out = "";
      for (let i = 0; i < val.strings.length; i += 1) {
        out += val.strings[i];
        if (i < val.values.length) {
          const prev = val.strings[i];
          const v = val.values[i];
          if (typeof v === "boolean" && /\\?[a-zA-Z0-9_-]+=$/.test(prev)) {
            out += String(v);
          } else {
            out += flattenHtml(v);
          }
        }
      }
      return out;
    }
    if (val._$litKeyed$ === 1 && Array.isArray(val.templates)) {
      return val.templates.map(flattenHtml).join("");
    }
  }
  return String(val);
}

const fakeHost = {
  isConnected: true,
  requestUpdate() {},
  addController() {},
  removeController() {},
  updateComplete: Promise.resolve(true),
  renderRoot: { getElementById() { return null; } },
};

const wsCalls = [];
const store = new StudioStore(fakeHost);
store.ws.hass = { locale: { language: "en" }, config: { unit_system: { length: "km" } } };
store.ws.runSystemCommand = async (command, payload) => {
  wsCalls.push({ command, payload });
  return structuredClone(store.state);
};
store.ensureSubscription = async () => {};

store.ingestPayload(
  {
    studio_rev: STUDIO_REV,
    subentry_id: "sub_mobile",
    title: "Mobile Assistant",
    config: {
      kind: "device",
      device_slug: "mobile_assistant",
      device_group: "custom",
      assigned_person: "person.sean",
      device_remote_group: "area_auto",
      native_ble_tracking: true,
    },
    capabilities: {
      has_display: true,
      has_battery: true,
      is_roaming_device: true,
    },
    live: {
      device_online: true,
      device_group_name: "Custom",
      device_remote_group_name: "Area Automatic",
      active_area_name: "Office",
      battery_level: 88,
      wifi_rssi: -54,
      sw_version: "2026.11.0",
      issues: [],
    },
    esphome_inspector: { sections: [] },
    catalog: {
      people: [{ id: "person.sean", name: "Sean" }],
      areas: [{ id: "office", name: "Office" }],
    },
    device_groups: [
      {
        id: "pocket_carry",
        name: "Pocket Carry",
        description: "Compact pocket-carried displays",
        builtin: true,
        include_display: false,
        include_interface: false,
        device_config: { tap_to_wake: "Docked Only", native_ble_tracking: true },
      },
      {
        id: "handhelds",
        name: "Handhelds",
        description: "Battery-powered roaming displays",
        builtin: true,
        include_display: false,
        include_interface: false,
        device_config: { tap_to_wake: "Single Tap", native_ble_tracking: true },
      },
      {
        id: "wearables",
        name: "Wearables",
        description: "Compact wearable displays",
        builtin: true,
        include_display: false,
        include_interface: false,
        device_config: { tap_to_wake: "Double Tap", native_ble_tracking: true },
      },
      {
        id: "wall_panels",
        name: "Wall & Desk Panels",
        description: "Stationary mains-powered panels",
        builtin: true,
        include_display: false,
        include_interface: false,
        device_config: { tap_to_wake: "Single Tap", native_ble_tracking: false },
      },
      {
        id: "guest_suites",
        name: "Guest Suites",
        description: "Guest bedroom displays",
        builtin: false,
        include_display: true,
        include_interface: true,
        device_config: { tap_to_wake: "Docked Only", native_ble_tracking: false, clock_face: "Hybrid Digital" },
      },
    ],
    system_devices: [
      {
        subentry_id: "sub_mobile",
        title: "Mobile Assistant",
        device_slug: "mobile_assistant",
        kind: "device",
        has_display: true,
        is_online: true,
        is_roaming: true,
        ble_tracked: true,
        device_group: "custom",
        device_group_name: "Custom",
        assigned_person: "person.sean",
        assigned_person_name: "Sean",
        active_area_name: "Office",
        status_label: "Online",
      },
      {
        subentry_id: "sub_pocket",
        title: "Pocket Assistant",
        device_slug: "pocket_assistant",
        kind: "device",
        has_display: true,
        is_online: true,
        is_roaming: true,
        ble_tracked: true,
        device_group: "pocket_carry",
        device_group_name: "Pocket Carry",
        assigned_person: "",
        assigned_person_name: "",
        active_area_name: "Bedroom",
        status_label: "Online",
      },
      {
        subentry_id: "sub_tag",
        title: "Keyring Tag",
        device_slug: "keyring_tag",
        kind: "ble_tag",
        has_display: false,
        is_online: true,
        is_roaming: true,
        ble_tracked: true,
        device_group: "",
        device_group_name: "",
        assigned_person: "",
        assigned_person_name: "",
        active_area_name: "Kitchen",
        status_label: "Detected",
      },
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
  false,
);

const groupsHtml = flattenHtml(renderSystemGroupsView(store));
const managedHtml = flattenHtml(renderDevicesListView(store));
const overviewCustomHtml = flattenHtml(renderDeviceOverviewView(store));

store.activeSubentryId = "sub_mobile";
store.openSaveGroupModal();
store.saveGroupModal = { ...store.saveGroupModal, name: " Sean Carry ", description: "Personal handheld" };
await store.confirmSaveGroupModal();

// Switch active device to handhelds -> Save Custom Group button disappears
store.ingestPayload(
  {
    ...structuredClone(store.state),
    config: { ...structuredClone(store.state.config), device_group: "handhelds" },
    live: { ...structuredClone(store.state.live), device_group_name: "Handhelds" },
  },
  false,
);
const overviewGroupHtml = flattenHtml(renderDeviceOverviewView(store));

return {
  groupsHtml,
  managedHtml,
  overviewCustomHtml,
  overviewGroupHtml,
  wsCalls,
};
})();
"""
        stub_deps = (
            "globalThis.HTMLElement = class { attachShadow() { return {}; } toggleAttribute() {} };\n"
            "function navigateHaPath() {}\n"
            "class StudioWsClient {}\n"
            "function formatWsError(_e, f) { return f; }\n"
            + "".join(
                f"function {fn}() {{}}\n"
                for fn in (
                    "adoptLatterDeviceOp",
                    "checkSystemUpdatesOp",
                    "clearInternalLogsOp",
                    "clearSecurityPinOp",
                    "confirmAddBleModalOp",
                    "confirmRemoveDeviceOp",
                    "confirmResetDeviceOp",
                    "copyLogsToClipboardOp",
                    "downloadDeviceDiagnosticsOp",
                    "exportBackupOp",
                    "formatVisibleLogsOp",
                    "openColorWheelModalOp",
                    "quickAdoptBleCandidateOp",
                    "restoreFromUploadedFileOp",
                    "rotateSigningKeyOp",
                    "saveColorWheelSelectionOp",
                    "saveSecurityPinOp",
                    "selectBleCandidateInModalOp",
                    "sendAnnouncementOp",
                    "addRemoteGroupRowOp",
                    "addStringListRowOp",
                    "addVolumeOverrideRowOp",
                    "applyDeviceCustomColorOp",
                    "commitEntityChange",
                    "deleteCustomPaletteOp",
                    "deleteWallpaperOp",
                    "executeEntityActionOp",
                    "flushDeviceBucketOp",
                    "flushSystemSettingsOp",
                    "getDockItemsOp",
                    "getEnabledActivitySourcesOp",
                    "getEnabledAreaCategoriesOp",
                    "getEnabledHomeCategoriesOp",
                    "getPinnedItemsOp",
                    "moveAreaCategoryTokenOp",
                    "moveHomeCategoryTokenOp",
                    "moveShortcutItemOp",
                    "openShortcutModalOp",
                    "overlayDevicePrefsOnSections",
                    "overlayPendingBlankListSlots",
                    "overlayPendingEntityStates",
                    "previewCameraOp",
                    "removeRemoteGroupRowOp",
                    "removeShortcutItemOp",
                    "removeStringListRowOp",
                    "removeVolumeOverrideRowOp",
                    "resetDockItemsToDefaultOp",
                    "runDeviceActionOp",
                    "saveShortcutModalOp",
                    "selectWallpaperSourceOp",
                    "setAllWallpaperFavoritesOp",
                    "setWallpaperRotationOp",
                    "stageDeviceSettingOp",
                    "stageSystemSettingOp",
                    "testDoorbellSpeakerOp",
                    "toggleActivitySourceOp",
                    "toggleAreaCategoryTokenOp",
                    "toggleHomeCategoryTokenOp",
                    "toggleRemoteInGroupOp",
                    "toggleWallpaperFavOp",
                    "updateRemoteGroupFieldOp",
                    "updateStringListRowOp",
                    "updateVolumeOverrideRowOp",
                    "uploadWallpaperOp",
                )
            )
            + "const PENDING_ENTITY_STATES = new Map();\n"
        )
        got = _run_node_ts(
            [
                FRONTEND_SRC / "lib" / "lit.ts",
                FRONTEND_SRC / "protocol-schema.ts",
                FRONTEND_SRC / "constants.ts",
                FRONTEND_SRC / "utils" / "format.ts",
                FRONTEND_SRC / "components" / "controls.ts",
                FRONTEND_SRC / "state" / "groups-presence-ops.ts",
                FRONTEND_SRC / "state" / "store.ts",
                FRONTEND_SRC / "views" / "system-groups-view.ts",
                FRONTEND_SRC / "views" / "devices-list-view.ts",
                FRONTEND_SRC / "views" / "device-overview-view.ts",
            ],
            runner,
            preamble_js=stub_deps,
        )

        # Column 1 enclosed .area-presence-box containers + Column 2 Batch Controls listing traits + all Device Groups + Custom
        self.assertIn('id=group-box-pocket_carry class="area-presence-box"', got["groupsHtml"])
        self.assertIn('id=group-box-handhelds class="area-presence-box"', got["groupsHtml"])
        self.assertIn('id=group-box-guest_suites class="area-presence-box"', got["groupsHtml"])
        self.assertIn("<summary>Baseline Settings</summary>", got["groupsHtml"])
        self.assertIn("Include Display Settings", got["groupsHtml"])
        self.assertIn("Include Interface & Shortcuts", got["groupsHtml"])
        self.assertIn("<summary>Interface &amp; Shortcuts</summary>", got["groupsHtml"])
        self.assertIn("Pocket Carry", got["groupsHtml"])
        self.assertNotIn("Power Profile", got["groupsHtml"])
        self.assertNotIn("Portable Carry", got["groupsHtml"])
        self.assertNotIn("Tabletop Dock", got["groupsHtml"])
        self.assertIn("aria-label=Delete group Guest Suites", got["groupsHtml"])
        self.assertNotIn("aria-label=Delete group Pocket Carry", got["groupsHtml"])
        self.assertNotIn("aria-label=Delete group Handhelds", got["groupsHtml"])
        batch_select = got["groupsHtml"][
            got["groupsHtml"].index('id="batch-target-filter"') : got["groupsHtml"].index('id="batch-cat-filter"')
        ]
        for expected_opt in (
            "All Latter Devices",
            "Online Devices",
            "Roaming Devices",
            "Stationary Devices",
            "Pocket Carry",
            "Handhelds",
            "Wearables",
            "Wall & Desk Panels",
            "Guest Suites",
            "Custom",
        ):
            self.assertIn(expected_opt, batch_select)
        after_cat = got["groupsHtml"][got["groupsHtml"].index('id="batch-cat-filter"') :]
        cat_filter_select = after_cat[: after_cat.index("</select>")]
        for expected_cat in ("All Categories", "Display", "Interface", "Audio", "Power", "Presence", "Security"):
            self.assertIn(expected_cat, cat_filter_select)
        self.assertIn("Voice Follows Me", got["groupsHtml"])
        self.assertIn("Mixed values", got["groupsHtml"])

        # Managed Devices filter diet: populated groups (`Group: Pocket Carry`) + Custom + BLE Tags + Assigned to a Person shown; 0-member groups & Updates Available hidden
        cat_select = got["managedHtml"][
            got["managedHtml"].index('id="device-category-filter"') : got["managedHtml"].index("</select>")
        ]
        self.assertIn("Group: Pocket Carry", cat_select)
        self.assertIn("Group: Custom", cat_select)
        self.assertIn("BLE Tags", cat_select)
        self.assertIn("Assigned to a Person", cat_select)
        self.assertNotIn("Group: Handhelds", cat_select)
        self.assertNotIn("Group: Wearables", cat_select)
        self.assertNotIn("Group: Wall &amp; Desk Panels", cat_select)
        self.assertNotIn("Group: Guest Suites", cat_select)
        self.assertNotIn("Updates Available", cat_select)
        self.assertNotIn("Screenless Devices", cat_select)

        # Device Overview Assignments: Save Custom Group shown when Custom and hidden when on Handhelds
        self.assertIn("id=card-device-assignments", got["overviewCustomHtml"])
        self.assertIn('id="btn-save-custom-group"', got["overviewCustomHtml"])
        self.assertIn("Save Custom Group", got["overviewCustomHtml"])
        self.assertNotIn('id="btn-save-custom-group"', got["overviewGroupHtml"])
        self.assertEqual(
            got["wsCalls"][0],
            {
                "command": "create_device_group",
                "payload": {
                    "name": "Sean Carry",
                    "description": "Personal handheld",
                    "source_subentry_id": "sub_mobile",
                    "assign_source": True,
                },
            },
        )

    def test_full_7447_mdi_catalog_and_ranked_search(self) -> None:
        """All 7,447 @mdi/js v7.4.47 icons decode in 1:1 parity with firmware ui_mdi.cpp and rank exact searches first."""
        runner = """
const all = getAllMdiIcons();
const teddy = searchMdiIcons("teddy-bear");
const multiWord = searchMdiIcons("teddy bear");
const empty = searchMdiIcons("");
return {
  count: all.length,
  hasTeddyBear: isKnownMdiIcon("mdi:teddy-bear"),
  hasBareTeddy: isKnownMdiIcon("teddy-bear"),
  unknownFake: isKnownMdiIcon("mdi:definitely-not-an-icon-xyz"),
  teddyTop: teddy.items[0],
  teddyTotal: teddy.totalMatches,
  multiWordTop: multiWord.items[0],
  emptyTotal: empty.totalMatches,
  emptyLen: empty.items.length,
};
"""
        got = _run_node_ts([FRONTEND_SRC / "mdi-catalog.ts"], runner)
        self.assertEqual(got["count"], 7447)
        self.assertTrue(got["hasTeddyBear"])
        self.assertTrue(got["hasBareTeddy"])
        self.assertFalse(got["unknownFake"])
        self.assertEqual(got["teddyTop"], "mdi:teddy-bear")
        self.assertGreaterEqual(got["teddyTotal"], 1)
        self.assertEqual(got["multiWordTop"], "mdi:teddy-bear")
        self.assertEqual(got["emptyTotal"], 7447)
        self.assertGreater(got["emptyLen"], 100)


if __name__ == "__main__":
    unittest.main()
