"""Standalone tests for device_ping.py: Latter asks bound Devices to resend device_hello.

They run without Home Assistant installed; device_ping.py is standard-library only and loaded by path.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"latter_ping_test_{name}", LATTER_DIR / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


device_ping = _load("device_ping")


def _drive(coro):
    """Run a coroutine whose awaits never suspend (the fakes below), without an event loop."""
    try:
        coro.send(None)
    except StopIteration as stop:
        return stop.value
    coro.close()
    raise AssertionError("coroutine suspended; the fakes must complete synchronously")


class TestPingBoundDevices(unittest.TestCase):
    """After setup, every bound Device with a registered latter_ping action is pinged once."""

    def _run(self, device_ids, registered, failing=()):
        calls: list[str] = []
        errors: list[str] = []

        def resolve(dev_id: str, action: str) -> str | None:
            self.assertEqual(action, "latter_ping")
            node = registered.get(dev_id)
            return f"{node}_{action}" if node else None

        async def call(service: str) -> None:
            calls.append(service)
            if service in failing:
                raise RuntimeError("device dropped")

        pinged = _drive(
            device_ping.async_ping_bound_devices(
                device_ids, resolve, call, lambda service, err: errors.append(service)
            )
        )
        return pinged, calls, errors

    def test_pings_each_online_device(self) -> None:
        pinged, calls, errors = self._run(["dev_a", "dev_b"], {"dev_a": "pocket", "dev_b": "desk"})
        self.assertEqual(pinged, ["pocket_latter_ping", "desk_latter_ping"])
        self.assertEqual(calls, pinged)
        self.assertEqual(errors, [])

    def test_skips_offline_unbound_and_duplicate_devices(self) -> None:
        pinged, calls, _ = self._run(["dev_a", None, "", "dev_offline", "dev_a"], {"dev_a": "pocket"})
        self.assertEqual(pinged, ["pocket_latter_ping"])
        self.assertEqual(calls, ["pocket_latter_ping"])

    def test_one_failure_does_not_stop_the_rest(self) -> None:
        pinged, calls, errors = self._run(
            ["dev_a", "dev_b"], {"dev_a": "pocket", "dev_b": "desk"}, failing={"pocket_latter_ping"}
        )
        self.assertEqual(calls, ["pocket_latter_ping", "desk_latter_ping"])
        self.assertEqual(pinged, ["desk_latter_ping"])
        self.assertEqual(errors, ["pocket_latter_ping"])

    def test_no_devices(self) -> None:
        pinged, calls, errors = self._run([], {})
        self.assertEqual((pinged, calls, errors), ([], [], []))

    def test_action_matches_firmware(self) -> None:
        """The firmware's latter_ping action (id latter_ping_action) is what answers with a hello."""
        self.assertEqual(device_ping.PING_ACTION, "latter_ping")
        core = REPO_ROOT.parent / "esphome-latter-core" / "modules" / "features" / "core_system.yaml"
        if core.exists():
            text = core.read_text(encoding="utf-8")
            block = text.split("- action: latter_ping", 1)[1].split("- action:", 1)[0]
            self.assertIn("script.execute: send_device_hello", block)


if __name__ == "__main__":
    unittest.main()
