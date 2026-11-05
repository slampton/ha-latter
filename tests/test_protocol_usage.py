"""Protocol v3 usage: ha-latter's side of the device <-> Home Assistant contract matches protocol_v3.json.

- services.yaml documents every field the firmware may send to each latter.* service.
- Every esphome device-action call built from a literal dict sends exactly the protocol's variables
  (Home Assistant's ESPHome integration requires all of a user-defined action's arguments).
The firmware side is checked by esphome-latter-core/tools/check_protocol_usage.py.
Standard library only.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import unittest

COMP = Path(__file__).resolve().parent.parent / "custom_components" / "latter"
SCHEMA = json.loads((COMP / "protocol_v3.json").read_text(encoding="utf-8"))


def _services_yaml_fields() -> dict[str, set[str]]:
    """Return {service: {field, ...}} from services.yaml (two-space indented, no anchors)."""
    fields: dict[str, set[str]] = {}
    service = ""
    in_fields = False
    for line in (COMP / "services.yaml").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([a-z_][a-z0-9_]*):\s*$", line)
        if m:
            service, in_fields = m.group(1), False
            fields[service] = set()
            continue
        if re.match(r"^  fields:\s*$", line):
            in_fields = True
            continue
        if re.match(r"^  \S", line):
            in_fields = False
            continue
        m = re.match(r"^    ([a-z_][a-z0-9_]*):", line)
        if in_fields and m and service:
            fields[service].add(m.group(1))
    return fields


def _esphome_literal_calls() -> list[tuple[str, str, set[str]]]:
    """Find hass.services.async_call("esphome", <svc>, {literal}) and the device action it targets.

    The action is the nearest preceding device-action name string in the same function (the suffix
    passed to the esphome service resolver).
    """
    names = set(SCHEMA["device_actions"])
    found: list[tuple[str, str, set[str]]] = []
    for path in sorted(COMP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            marks = sorted(
                (n.lineno, n.value)
                for n in ast.walk(func)
                if isinstance(n, ast.Constant) and n.value in names
            )
            for call in ast.walk(func):
                if not (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "async_call"
                    and len(call.args) >= 3
                    and isinstance(call.args[0], ast.Constant)
                    and call.args[0].value == "esphome"
                    and isinstance(call.args[2], ast.Dict)
                    and all(isinstance(k, ast.Constant) for k in call.args[2].keys)
                ):
                    continue
                before = [v for ln, v in marks if ln <= call.lineno]
                if not before:
                    continue
                keys = {k.value for k in call.args[2].keys}
                found.append((f"{path.name}:{call.lineno}", before[-1], keys))
    return found


def _registered_schema_keys() -> dict[str, set[str]]:
    """Return {service: {key, ...}} accepted by each hass.services.async_register(..., schema=vol.Schema({...})).

    Service names come from const.py SERVICE_* constants; `**BASE_TARGET_FIELDS` contributes target_device.
    """
    consts: dict[str, str] = {}
    for node in ast.parse((COMP / "const.py").read_text(encoding="utf-8")).body:
        if (
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and isinstance(getattr(node, "value", None), ast.Constant)
            and isinstance(node.value.value, str)
        ):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name) and t.id.startswith("SERVICE_"):
                    consts[t.id] = node.value.value
    keys: dict[str, set[str]] = {}
    for call in ast.walk(ast.parse((COMP / "services.py").read_text(encoding="utf-8"))):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "async_register"):
            continue
        if len(call.args) < 2:
            continue
        name_node = call.args[1]
        name = consts.get(name_node.id, "") if isinstance(name_node, ast.Name) else (
            name_node.value if isinstance(name_node, ast.Constant) else ""
        )
        schema = next((kw.value for kw in call.keywords if kw.arg == "schema"), None)
        if not name or not isinstance(schema, ast.Call) or not schema.args or not isinstance(schema.args[0], ast.Dict):
            continue
        accepted: set[str] = set()
        for k in schema.args[0].keys:
            if k is None:
                accepted.add("target_device")  # **BASE_TARGET_FIELDS
            elif isinstance(k, ast.Call) and k.args and isinstance(k.args[0], ast.Constant):
                accepted.add(str(k.args[0].value))
        keys[name] = accepted
    return keys


class TestProtocolUsage(unittest.TestCase):
    def test_service_schemas_accept_every_protocol_field(self) -> None:
        registered = _registered_schema_keys()
        for svc, spec in SCHEMA["services"].items():
            with self.subTest(service=svc):
                self.assertIn(svc, registered, f"latter.{svc}: no vol.Schema registration found in services.py")
                missing = set(spec.get("fields", [])) - registered[svc]
                self.assertFalse(missing, f"latter.{svc}: the service schema rejects {sorted(missing)}")

    def test_services_yaml_documents_every_protocol_field(self) -> None:
        documented = _services_yaml_fields()
        for svc, spec in SCHEMA["services"].items():
            with self.subTest(service=svc):
                self.assertIn(svc, documented, f"latter.{svc} missing from services.yaml")
                missing = set(spec.get("fields", [])) - documented[svc]
                self.assertFalse(missing, f"latter.{svc}: services.yaml lacks {sorted(missing)}")

    def test_device_action_calls_send_exactly_the_protocol_variables(self) -> None:
        calls = _esphome_literal_calls()
        self.assertGreaterEqual(len(calls), 2, "expected the show_notification calls to be found")
        for where, action, keys in calls:
            with self.subTest(call=where):
                want = set(SCHEMA["device_actions"][action].get("variables", {}))
                self.assertEqual(keys, want, f"{where}: esphome {action} args differ from the protocol")


if __name__ == "__main__":
    unittest.main()
