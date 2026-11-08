"""Studio runtime behavior that lives in latter-studio.js, run under Node when it's available.

The functions under test are copied out of the shipped file verbatim (by marker), so this exercises the exact code.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import ModuleType
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"
STUDIO_JS = (LATTER_DIR / "frontend" / "latter-studio.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"latter_runtime_test_{name}", LATTER_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


entity_sections = _load("entity_sections")


def _slice(start: str, end: str) -> str:
    a = STUDIO_JS.index(start)
    b = STUDIO_JS.index(end, a)
    return STUDIO_JS[a:b]


def _run_node(script: str) -> object:
    out = subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True, timeout=30)
    return json.loads(out.stdout)


@unittest.skipUnless(NODE, "node is not installed")
class TestEntityLabels(unittest.TestCase):
    """D-013: labels from entity names (HA, ESPHome, firmware) are Title Case, acronyms and brand casing kept."""

    def test_entity_label_title_case(self) -> None:
        code = _slice("const LABEL_MINOR_WORDS", "function renderNativeControlRow")
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
            "Stay awake when docked": "Stay Awake When Docked",
            "Turn on": "Turn On",
        }
        got = _run_node(code + f"\nprocess.stdout.write(JSON.stringify({json.dumps(list(cases))}.map(entityLabel)));")
        self.assertEqual(dict(zip(cases, got)), cases)

    def test_every_entity_label_goes_through_it(self) -> None:
        self.assertIn("const name = esc(entityLabel(item.name));", STUDIO_JS)
        self.assertIn("settingsRowHtml(esc(entityLabel(fc.name)), esc(desc), widget)", STUDIO_JS)
        self.assertIn("${esc(entityLabel(it.name))}</button>", STUDIO_JS)
        self.assertIn("<span>${esc(entityLabel(b.camera_name))}</span>", STUDIO_JS)
        for raw in ("const name = esc(item.name);", "settingsRowHtml(esc(fc.name)", ">${esc(it.name)}</button>"):
            self.assertNotIn(raw, STUDIO_JS)


@unittest.skipUnless(NODE, "node is not installed")
class TestLiveConditionalRows(unittest.TestCase):
    """A Device entity change shows at once and survives payloads that still carry the old state."""

    def test_pending_state_overlay(self) -> None:
        code = _slice("const PENDING_ENTITY_STATES", "async function commitEntityChange")
        script = code + """
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
process.stdout.write(JSON.stringify(out));
"""
        self.assertEqual(
            _run_node(script),
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
        # Every payload keeps pending local states; entity changes go through commitEntityChange; a re-render that
        # waits for focus to leave runs on focusout; the subscription pushes on the Device's entity state changes.
        self.assertIn("  overlayPendingEntityStates(data);\n  STATE = data;", STUDIO_JS)
        for fn in ("espSelect", "espNumber", "espAction"):
            body = _slice(f"async function {fn}(", "\n}\n")
            self.assertIn("commitEntityChange(", body, fn)
        self.assertIn('this.shadowRoot.addEventListener("focusout", onStudioFocusOut);', STUDIO_JS)
        self.assertIn("  renderEntitySectionsWhenIdle();\n", STUDIO_JS)
        self.assertNotIn('if (!activeEl || !["SELECT", "INPUT"].includes(activeEl.tagName)) {', STUDIO_JS)
        cmds = (LATTER_DIR / "studio" / "commands.py").read_text(encoding="utf-8")
        self.assertIn("async_track_state_change_event(hass, entity_ids, _entity_changed)", cmds)
        self.assertIn("        _track_device_states()\n        _schedule_push()", cmds)


class TestEntitySections(unittest.TestCase):
    """Which Studio section a Device entity lands in."""

    def classify(self, entity_id: str, name: str, domain: str = "select", key: str | None = None) -> str:
        return entity_sections.classify_esphome_entity_section(
            entity_id, name, domain, "", "config", translation_key=key,
            device_object_prefixes=("latter_desk_display", "desk_display"),
        )[0]

    def test_assist_satellite_entities_are_voice(self) -> None:
        # A device named "Desk Display" used to put HA's Assist selects in Display: "display" came from its ID.
        self.assertEqual(self.classify("select.desk_display_assistant", "Assistant", key="pipeline"), "voice")
        self.assertEqual(self.classify("select.desk_display_finished_speaking_detection", "Finished speaking detection", key="vad_sensitivity"), "voice")
        self.assertEqual(self.classify("select.desk_display_wake_word", "Wake word", key="wake_word"), "voice")
        self.assertEqual(self.classify("select.desk_display_wake_word_2", "Wake word 2", key="wake_word_n"), "voice")
        self.assertEqual(self.classify("assist_satellite.desk_display_assist_satellite", "Assist satellite", domain="assist_satellite"), "voice")

    def test_device_prefix_never_decides(self) -> None:
        self.assertEqual(self.classify("switch.desk_display_mute", "Mute", domain="switch"), "other")
        self.assertEqual(self.classify("select.desk_display_voice_visual_profile", "Voice: Visual Profile"), "voice")
        self.assertEqual(self.classify("select.desk_display_display_clock_face", "Display: Clock Face"), "display")


if __name__ == "__main__":
    unittest.main()
