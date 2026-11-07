"""Standalone tests for Latter Studio: System and Device save scopes, and entity-action restrictions.

They run without Home Assistant installed. The production modules under test (studio/settings.py,
studio/scope.py) are standard-library only and loaded by file path.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path
import sys
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
