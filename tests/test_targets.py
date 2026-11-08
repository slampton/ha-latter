"""Special service targets: one name, `occupied_areas`, for "the Devices or speakers in occupied Areas".

Runs without Home Assistant installed: targets.py and studio/settings.py are standard-library only and
loaded by file path; services.py is checked as source text.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
from types import ModuleType
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"latter_targets_test_{name.replace('/', '_')}", LATTER_DIR / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


targets = _load("targets")
settings = _load("studio/settings")

# Retired target names, built so this file never matches its own repo-wide guard.
RETIRED = ("follow" + "_me", "occu" + "pied")


class _Dev:
    def __init__(self, slug: str, ble_tag: bool = False) -> None:
        self.device_slug = slug
        self.is_ble_tag = ble_tag


class CallTargetTests(unittest.TestCase):
    """Doorbell call_target rings Latter Devices only: never the caller, never a BLE tag."""

    def setUp(self) -> None:
        self.pool = [
            _Dev("desk"),
            _Dev("kitchen"),
            _Dev("phone", ble_tag=True),
            _Dev("office"),
            object(),  # something else stored under the domain (the System, a store, ...)
        ]

    def test_all_rings_every_other_latter_device(self) -> None:
        for target in ("all", "ALL", "", None):
            self.assertEqual(targets.call_target_slugs(self.pool, "desk", target), ["kitchen", "office"], target)

    def test_named_target(self) -> None:
        self.assertEqual(targets.call_target_slugs(self.pool, "desk", "office"), ["office"])
        self.assertEqual(targets.call_target_slugs(self.pool, "desk", "phone"), [])
        self.assertEqual(targets.call_target_slugs(self.pool, "desk", "desk"), [])
        self.assertEqual(targets.call_target_slugs(self.pool, "desk", "nowhere"), [])

    def test_intercom_list_uses_the_same_rule(self) -> None:
        self.assertEqual(
            [d.device_slug for d in targets.other_latter_devices(self.pool, "kitchen")], ["desk", "office"]
        )
        doorbell = (LATTER_DIR / "doorbell_engine.py").read_text(encoding="utf-8")
        coordinator = (LATTER_DIR / "coordinator.py").read_text(encoding="utf-8")
        self.assertIn("call_target_slugs(", doorbell)
        self.assertIn("other_latter_devices(", coordinator)


class UnrecordedAttributesTests(unittest.TestCase):
    def test_only_attributes_the_sensors_expose(self) -> None:
        src = (LATTER_DIR / "sensor.py").read_text(encoding="utf-8")
        m = re.search(r"_unrecorded_attributes = frozenset\((\{[^}]*\})\)", src)
        self.assertIsNotNone(m)
        names = set(re.findall(r'"([a-z_]+)"', m.group(1)))
        self.assertEqual(names, {"payload", "rev"})
        for name in names:
            self.assertIn(f'"{name}": attrs.get("{name}"', src)


class TargetKindTests(unittest.TestCase):
    def test_special_targets(self) -> None:
        self.assertEqual(targets.target_kind("all"), "all")
        self.assertEqual(targets.target_kind(" ALL "), "all")
        self.assertEqual(targets.target_kind("occupied_areas"), "occupied_areas")
        self.assertEqual(targets.target_kind("Occupied_Areas"), "occupied_areas")
        self.assertEqual(targets.target_kind("person.alex"), "person")

    def test_no_target(self) -> None:
        self.assertEqual(targets.target_kind(None), "none")
        self.assertEqual(targets.target_kind("  "), "none")

    def test_retired_names_are_device_references(self) -> None:
        # A Device reference must resolve to a Latter Device or the call fails with unknown_target,
        # so the retired names are errors, never an occupied-Areas broadcast.
        for name in RETIRED:
            self.assertEqual(targets.target_kind(name), "device", name)
        self.assertEqual(targets.target_kind("pocket_assistant"), "device")

    def test_studio_targets_match(self) -> None:
        self.assertEqual(settings.NOTIFY_SPECIAL_TARGETS, (targets.TARGET_ALL, targets.TARGET_OCCUPIED_AREAS))
        self.assertEqual(settings.BROADCAST_TARGETS, (targets.TARGET_ALL, targets.TARGET_OCCUPIED_AREAS))


class ServiceSourceTests(unittest.TestCase):
    SRC = (LATTER_DIR / "services.py").read_text(encoding="utf-8")

    def test_handlers_classify_with_target_kind(self) -> None:
        self.assertIn("from .targets import target_kind", self.SRC)
        self.assertEqual(self.SRC.count("target_kind("), 2, "notify and intercom_broadcast both classify targets")

    def test_intercom_device_target_must_resolve(self) -> None:
        body = self.SRC.split("async def _handle_intercom_broadcast", 1)[1].split("\n    async def ", 1)[0]
        self.assertRegex(body, r'if kind in \("device", "person"\):\s+#[^\n]*\n\s+_resolve_coordinator_from_call\(hass, call\)')

    def test_target_speakers_schema_is_media_player_entities(self) -> None:
        self.assertRegex(
            self.SRC,
            r'vol\.Optional\("target_speakers"\): vol\.All\(\s*cv\.entity_ids, \[cv\.entity_domain\("media_player"\)\]\s*\)',
        )


class RetiredNamesGuard(unittest.TestCase):
    def test_no_retired_target_names(self) -> None:
        pattern = re.compile(
            rf"\b{RETIRED[0]}\b|['\"`]{RETIRED[1]}['\"`]|target_(?:device|speakers):\s*{RETIRED[1]}\b"
        )
        roots = [LATTER_DIR, REPO_ROOT / "docs", REPO_ROOT / "README.md"]
        hits: list[str] = []
        for root in roots:
            files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
            for path in files:
                if path.suffix not in (".py", ".js", ".yaml", ".json", ".md") or "__pycache__" in path.parts:
                    continue
                for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if pattern.search(line):
                        hits.append(f"{path.relative_to(REPO_ROOT)}:{num}: {line.strip()}")
        self.assertEqual(hits, [], "retired target names:\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
