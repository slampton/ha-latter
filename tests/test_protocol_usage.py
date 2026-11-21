"""Protocol v3 usage: ha-latter's side of the device <-> Home Assistant contract matches protocol_v3.json.

- `SCHEMA["ha_services"]` (5 public user actions) matches `services.yaml`, `PUBLIC_SERVICES`, and `hass.services`.
- `SCHEMA["rpc_methods"]` (20 private bound-device RPC methods) matches `ALL_RPC_METHODS` and `LatterRpcDispatcher`.
- Every esphome device-action call built from a literal dict sends exactly the protocol's variables
  (Home Assistant's ESPHome integration requires all of a user-defined action's arguments).
The firmware side is checked by esphome-latter-core/tools/check_protocol_usage.py.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
from typing import Any
import unittest

COMP = Path(__file__).resolve().parent.parent / "custom_components" / "latter"
SCHEMA = json.loads((COMP / "protocol_v3.json").read_text(encoding="utf-8"))

EXPECTED_PUBLIC_SERVICES = {
    "notify",
    "intercom_broadcast",
    "set_active_area",
    "set_active_speaker",
    "reset_device",
}


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


def _const_string_map(prefix: str) -> dict[str, str]:
    """Return {CONST_NAME: str_value} from const.py for constants starting with `prefix`."""
    consts: dict[str, str] = {}
    for node in ast.parse((COMP / "const.py").read_text(encoding="utf-8")).body:
        if (
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and isinstance(getattr(node, "value", None), ast.Constant)
            and isinstance(node.value.value, str)
        ):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name) and t.id.startswith(prefix):
                    consts[t.id] = node.value.value
    return consts


def _const_tuple_values(tuple_name: str, consts: dict[str, str]) -> set[str]:
    """Resolve a tuple of constant names in const.py to its string values."""
    for node in ast.parse((COMP / "const.py").read_text(encoding="utf-8")).body:
        target_id = ""
        val = None
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_id, val = node.target.id, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_id, val = node.targets[0].id, node.value
        if target_id == tuple_name and isinstance(val, ast.Tuple):
            out: set[str] = set()
            for elt in val.elts:
                if isinstance(elt, ast.Name) and elt.id in consts:
                    out.add(consts[elt.id])
                elif isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    out.add(elt.value)
            return out
    return set()


def _registered_schema_keys() -> dict[str, set[str]]:
    """Return {service: {key, ...}} accepted by each hass.services.async_register(..., schema=vol.Schema({...})).

    Service names come from const.py SERVICE_* constants; `**BASE_TARGET_FIELDS` contributes target_device.
    """
    consts = _const_string_map("SERVICE_")
    keys: dict[str, set[str]] = {}
    tree = ast.parse((COMP / "services.py").read_text(encoding="utf-8"))
    assigned_schemas: dict[str, ast.Call] = {}
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
        ):
            assigned_schemas[node.targets[0].id] = node.value
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "async_register"):
            continue
        if len(call.args) < 2:
            continue
        name_node = call.args[1]
        name = consts.get(name_node.id, "") if isinstance(name_node, ast.Name) else (
            name_node.value if isinstance(name_node, ast.Constant) else ""
        )
        schema = next((kw.value for kw in call.keywords if kw.arg == "schema"), None)
        if isinstance(schema, ast.Name) and schema.id in assigned_schemas:
            schema = assigned_schemas[schema.id]
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


def _rpc_dispatcher_dispatched_methods_and_fields() -> tuple[set[str], set[str]]:
    """Return (dispatched_rpc_methods, string_keys_read) across LatterRpcDispatcher and its coordinator helpers."""
    rpc_consts = _const_string_map("RPC_")
    services_tree = ast.parse((COMP / "services.py").read_text(encoding="utf-8"))
    coord_tree = ast.parse((COMP / "coordinator.py").read_text(encoding="utf-8"))

    dispatched: set[str] = set()
    for cls in services_tree.body:
        if isinstance(cls, ast.ClassDef) and cls.name == "LatterRpcDispatcher":
            for item in cls.body:
                if isinstance(item, ast.AsyncFunctionDef) and item.name == "async_dispatch":
                    for cmp in ast.walk(item):
                        if isinstance(cmp, ast.Compare):
                            for operand in [cmp.left, *cmp.comparators]:
                                if isinstance(operand, ast.Name) and operand.id in rpc_consts:
                                    dispatched.add(rpc_consts[operand.id])
                                elif (
                                    isinstance(operand, ast.Constant)
                                    and isinstance(operand.value, str)
                                    and operand.value in SCHEMA["rpc_methods"]
                                ):
                                    dispatched.add(operand.value)

    read_strings: set[str] = set()
    for tree in (services_tree, coord_tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                read_strings.add(node.value)
    return dispatched, read_strings


class TestProtocolUsage(unittest.TestCase):
    def test_public_ha_services_exact_five_parity(self) -> None:
        svc_consts = _const_string_map("SERVICE_")
        public_tuple = _const_tuple_values("PUBLIC_SERVICES", svc_consts)
        registered = _registered_schema_keys()
        documented = _services_yaml_fields()

        self.assertEqual(set(SCHEMA["ha_services"]), EXPECTED_PUBLIC_SERVICES)
        self.assertEqual(public_tuple, EXPECTED_PUBLIC_SERVICES)
        self.assertEqual(set(registered), EXPECTED_PUBLIC_SERVICES)
        self.assertEqual(set(documented), EXPECTED_PUBLIC_SERVICES)

        for svc, spec in SCHEMA["ha_services"].items():
            with self.subTest(service=svc):
                want_fields = set(spec.get("fields", []))
                self.assertEqual(want_fields - registered[svc], set())
                self.assertEqual(want_fields - documented[svc], set())

    def test_rpc_methods_twenty_internal_dispatcher_parity(self) -> None:
        rpc_consts = _const_string_map("RPC_")
        all_rpc_tuple = _const_tuple_values("ALL_RPC_METHODS", rpc_consts)
        dispatched, read_strings = _rpc_dispatcher_dispatched_methods_and_fields()

        self.assertEqual(len(SCHEMA["rpc_methods"]), 20)
        self.assertEqual(all_rpc_tuple, set(SCHEMA["rpc_methods"]))
        self.assertEqual(dispatched, set(SCHEMA["rpc_methods"]))

        # Internal-only RPC methods must NEVER leak onto public services.yaml or hass.services
        private_only = set(SCHEMA["rpc_methods"]) - EXPECTED_PUBLIC_SERVICES
        self.assertEqual(len(private_only), 17)
        self.assertFalse(private_only & set(_services_yaml_fields()))
        self.assertFalse(private_only & set(_registered_schema_keys()))

        for rpc_name, spec in SCHEMA["rpc_methods"].items():
            with self.subTest(rpc_method=rpc_name):
                missing = set(spec.get("fields", [])) - read_strings
                self.assertFalse(missing, f"LatterRpcDispatcher.{rpc_name} never reads {sorted(missing)}")

    def test_device_action_calls_send_exactly_the_protocol_variables(self) -> None:
        calls = _esphome_literal_calls()
        self.assertGreaterEqual(len(calls), 2, "expected the show_notification calls to be found")
        for where, action, keys in calls:
            with self.subTest(call=where):
                want = set(SCHEMA["device_actions"][action].get("variables", {}))
                self.assertEqual(keys, want, f"{where}: esphome {action} args differ from the protocol")


async def test_live_hub_registers_only_five_public_services_and_private_rpc_dispatcher(
    hass: Any, setup_latter_hub: Any
) -> None:
    """Verify runtime `hass.services` exposes ONLY the 5 public actions while `hub.rpc_dispatcher` handles all 20 RPCs."""
    from custom_components.latter import async_unload_entry
    from custom_components.latter.const import ALL_RPC_METHODS, DOMAIN, PUBLIC_SERVICES
    from custom_components.latter.services import LatterRpcDispatcher

    entry, sys_obj, coord = await setup_latter_hub(hass)
    live_services = set(hass.services.async_services_for_domain(DOMAIN))
    assert live_services == set(PUBLIC_SERVICES) == EXPECTED_PUBLIC_SERVICES
    assert len(ALL_RPC_METHODS) == 20
    assert isinstance(sys_obj.rpc_dispatcher, LatterRpcDispatcher)
    for internal_rpc in set(ALL_RPC_METHODS) - set(PUBLIC_SERVICES):
        assert not hass.services.has_service(DOMAIN, internal_rpc)

    await sys_obj.rpc_dispatcher.async_dispatch(
        coord,
        "display_state",
        {"power_state": 1, "brightness_pct": 45, "screensaver_active": True},
    )
    assert coord.screensaver_active is True
    assert coord.display_brightness_pct == 45
    assert await async_unload_entry(hass, entry) is True


if __name__ == "__main__":
    unittest.main()
