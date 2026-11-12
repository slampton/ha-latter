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
        "process.stdout.write(JSON.stringify(fn()));\n"
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


if __name__ == "__main__":
    unittest.main()
