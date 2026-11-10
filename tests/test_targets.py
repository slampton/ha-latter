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
        helper_body = self.SRC.split("def _resolve_occupied_area_ids(", 1)[1].split("\nasync def ", 1)[0]
        self.assertIn("resolve_person_area_and_distance(hass, target_low)", helper_body)
        body = self.SRC.split("async def _handle_intercom_broadcast", 1)[1].split("\n    async def ", 1)[0]
        self.assertRegex(body, r'if kind == "device":\s+#[^\n]*\n\s+_resolve_coordinator_from_call\(hass, call\)')
        self.assertIn('scoped_mode = kind in ("occupied_areas", "person")', body)
        self.assertIn("_resolve_occupied_area_ids(", body)

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

    def test_no_retired_external_presence_entity(self) -> None:
        retired_key = "presence" + "_entity"
        retired_cat = "presence" + "_sensors"
        roots = [LATTER_DIR, REPO_ROOT / "docs", REPO_ROOT / "README.md"]
        hits: list[str] = []
        for root in roots:
            files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
            for path in files:
                if path.suffix not in (".py", ".js", ".yaml", ".json", ".md") or "__pycache__" in path.parts:
                    continue
                txt = path.read_text(encoding="utf-8")
                if retired_key in txt or retired_cat in txt:
                    hits.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(hits, [], "retired external presence references: " + ", ".join(hits))


class BleDeviceTrackerAndPersonTests(unittest.TestCase):
    def test_device_tracker_platform_is_registered(self) -> None:
        const_src = (LATTER_DIR / "const.py").read_text(encoding="utf-8")
        self.assertIn("Platform.DEVICE_TRACKER", const_src)
        dt_src = (LATTER_DIR / "device_tracker.py").read_text(encoding="utf-8")
        self.assertIn("from homeassistant.components.device_tracker import SourceType, TrackerEntity", dt_src)
        self.assertNotIn("device_tracker.config_entry", dt_src)
        self.assertIn("class LatterBleDeviceTracker(TrackerEntity):", dt_src)
        self.assertIn("SourceType.BLUETOOTH_LE", dt_src)
        self.assertIn("def in_zones(self) -> list[str] | None:", dt_src)
        self.assertIn('return ["zone.home"]', dt_src)
        self.assertNotIn("def location_name", dt_src)
        self.assertNotIn("device_entry", dt_src)

    def test_person_sensors_subscribe_across_fabric_and_coordinators(self) -> None:
        sensor_src = (LATTER_DIR / "sensor.py").read_text(encoding="utf-8")
        self.assertIn("class _BaseLatterPersonSensor(SensorEntity):", sensor_src)
        self.assertIn("fabric.register_occupancy_listener(self._handle_person_update)", sensor_src)
        self.assertIn("resolve_person_area_and_distance(self.hass, self._person_entity)", sensor_src)

    def test_ble_tag_skips_display_sensors_and_listeners(self) -> None:
        sensor_src = (LATTER_DIR / "sensor.py").read_text(encoding="utf-8")
        ble_branch = sensor_src.split("if coordinator.is_ble_tag:", 1)[1].split("else:", 1)[0]
        self.assertIn("LatterCurrentAreaSensor(coordinator)", ble_branch)
        self.assertIn("LatterBleDistanceSensor(coordinator)", ble_branch)
        self.assertNotIn("LatterAreaContextSensor", ble_branch)

        coord_src = (LATTER_DIR / "coordinator.py").read_text(encoding="utf-8")
        self.assertNotIn("def _notify_listeners", coord_src)
        self.assertNotIn("self._notify_listeners()", coord_src)
        self.assertNotIn("_cached_hw_manifest", coord_src)
        self.assertNotIn("active_camera_index", coord_src)
        self.assertIn("def _bind_all_listeners(self) -> None:", coord_src)
        self.assertIn("self._doorbell_reply_task.cancel()", coord_src)
        area_body = coord_src.split("def async_set_active_area(", 1)[1].split("\n    @property", 1)[0]
        self.assertIn("self._bind_remotes_listener()", area_body)

    def test_coordinator_pass2_hot_path_hygiene(self) -> None:
        coord_src = (LATTER_DIR / "coordinator.py").read_text(encoding="utf-8")
        for legacy in ("ble_scanners_map", "entities_summary", "presence_state", "slot_{idx}_name", "get_all_scanners_diagnostic_map"):
            self.assertNotIn(legacy, coord_src)
        area_ctx_body = coord_src.split("def get_area_context_payload(", 1)[1].split("\n    @callback", 1)[0]
        self.assertIn("entities=entities", area_ctx_body)
        self.assertNotIn("find_area_media_entities", area_ctx_body)
        media_body = coord_src.split("def get_active_media_payload(", 1)[1].split("\n    @callback", 1)[0]
        self.assertNotIn("self._schedule_persist_runtime_state()", media_body)
        self.assertNotIn("self.last_media_title =", media_body)
        spk_body = coord_src.split("def _async_on_speaker_state_change(", 1)[1].split("\n    def ", 1)[0]
        self.assertIn("self._sync_active_speaker_media_snapshot()", spk_body)
        studio_payload_src = (LATTER_DIR / "studio" / "payload.py").read_text(encoding="utf-8")
        self.assertNotIn("get_area_context_payload", studio_payload_src)
        self.assertIn(".active_area_name", studio_payload_src)

    def test_coordinator_pass3_shared_site_feeds(self) -> None:
        coord_src = (LATTER_DIR / "coordinator.py").read_text(encoding="utf-8")
        for per_device_feed in (
            "_unsub_weather_state",
            "_unsub_forecast_timer",
            "_unsub_calendar_timer",
            "_bind_weather_listener",
            "_async_periodic_weather_refresh",
            "_async_periodic_calendar_refresh",
        ):
            self.assertNotIn(per_device_feed, coord_src)
        self.assertIn("def apply_weather_snapshot(", coord_src)
        self.assertIn("def apply_calendar_snapshot(", coord_src)

        sys_src = (LATTER_DIR / "system.py").read_text(encoding="utf-8")
        self.assertIn("def bind_feed_listeners(self) -> None:", sys_src)
        self.assertIn("def async_cleanup_feeds(self) -> None:", sys_src)
        self.assertIn("async def async_refresh_weather_forecast(", sys_src)
        self.assertIn("async def async_refresh_calendar_agenda(", sys_src)

        init_src = (LATTER_DIR / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("sys_obj.bind_feed_listeners()", init_src)
        self.assertIn("sys_obj.async_cleanup_feeds()", init_src)

    def test_browse_media_services_audit(self) -> None:
        browse_src = (LATTER_DIR / "browse_engine.py").read_text(encoding="utf-8")
        self.assertIn("def _resolve_speaker_playing_metadata(", browse_src)
        self.assertIn("asyncio.gather(", browse_src)
        self.assertNotIn("HomeAssistant-Latter/2.0", browse_src)

        media_ctrl_src = (LATTER_DIR / "media_controller.py").read_text(encoding="utf-8")
        self.assertIn("async def async_execute_volume_action(", media_ctrl_src)
        self.assertIn("await async_play_media_with_ma_fallback(", media_ctrl_src)

        services_src = (LATTER_DIR / "services.py").read_text(encoding="utf-8")
        self.assertIn("def _resolve_occupied_area_ids(", services_src)
        self.assertIn("await async_execute_volume_action(", services_src)
        self.assertIn("await async_save_and_broadcast_global_config(", services_src)
        self.assertNotIn("occupant_names", services_src)
        self.assertNotIn("coord.on_area_changed_push_slots = None", services_src)


if __name__ == "__main__":
    unittest.main()
