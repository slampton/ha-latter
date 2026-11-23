"""AST security, bound-identity, public-services vs RPC, redaction, and Zero-WAN checks."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
from typing import Final

MIN_SERVICE_CALL_ARGS: Final = 2
EXPECTED_PUBLIC_SERVICES: Final[frozenset[str]] = frozenset(
    {
        "notify",
        "intercom_broadcast",
        "set_active_area",
        "set_active_speaker",
        "reset_device",
    }
)

REQUIRED_REDACTED_KEYS: Final[frozenset[str]] = frozenset(
    {
        "ble_beacon_uuid",
        "ble_target_address",
        "camera_snapshot_url",
        "camera_stream_url",
        "hmac_secret_hex",
        "mac",
        "payload",
        "screensaver_photo_url",
        "security_pin",
        "security_pin_hash",
        "system_ble_uuid",
    }
)

ZERO_WAN_RE: Final = re.compile(
    r"(?:lrclib\.net|wikipedia\.org|openstreetmap\.org|nominatim|https://[a-zA-Z0-9])",
    re.IGNORECASE,
)


def call_attr_chain(node: ast.AST) -> str:
    """Flatten `a.b.c` attribute chains for AST call inspection."""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _check_call_node(
    rel: str,
    node: ast.Call,
    exception_keys: set[str],
    failures: list[str],
) -> None:
    chain = call_attr_chain(node.func)
    func_tail = chain.rsplit(".", 1)[-1]

    if func_tail in {"ServiceValidationError", "HomeAssistantError"}:
        tk_kw = next((kw for kw in node.keywords if kw.arg == "translation_key"), None)
        if tk_kw is None:
            failures.append(
                f"[EXCEPTION TRANSLATIONS] {rel}:{node.lineno} calls {func_tail}() "
                "without translation_key= (must translate via strings.json['exceptions'])"
            )
        elif (
            isinstance(tk_kw.value, ast.Constant)
            and isinstance(tk_kw.value.value, str)
            and tk_kw.value.value not in exception_keys
        ):
            failures.append(
                f"[EXCEPTION TRANSLATIONS] {rel}:{node.lineno} passes unknown "
                f"translation_key={tk_kw.value.value!r} to {func_tail}() "
                "(missing from strings.json['exceptions'])"
            )

    if func_tail in {"async_call", "has_service"} and len(node.args) >= MIN_SERVICE_CALL_ARGS:
        dom_arg, svc_arg = node.args[0], node.args[1]
        if isinstance(dom_arg, ast.Constant) and dom_arg.value == "esphome":
            if isinstance(svc_arg, (ast.JoinedStr, ast.BinOp)):
                failures.append(
                    f"[NO UNBOUND SERVICE] {rel}:{node.lineno} constructs unbound "
                    "esphome service string (must resolve via esphome_service())"
                )
            elif (
                isinstance(svc_arg, ast.Call)
                and isinstance(svc_arg.func, ast.Attribute)
                and svc_arg.func.attr == "format"
            ):
                failures.append(
                    f"[NO UNBOUND SERVICE] {rel}:{node.lineno} formats unbound "
                    "esphome service string"
                )

        if (
            isinstance(dom_arg, ast.Constant)
            and dom_arg.value in {"lock", "alarm_control_panel"}
            and isinstance(svc_arg, ast.Constant)
            and svc_arg.value == "toggle"
        ):
            failures.append(
                f"[SECURITY VERBS] {rel}:{node.lineno} dispatches forbidden "
                f"'toggle' on {dom_arg.value}"
            )

    if func_tail == "async_update_entity":
        kw_map = {kw.arg: kw.value for kw in node.keywords if kw.arg}
        has_unpacked_kw = any(kw.arg is None for kw in node.keywords)
        is_outbox_autohide = (
            rel == "custom_components/latter/services/rpc_receiver.py"
            and not has_unpacked_kw
            and set(kw_map.keys()) == {"hidden_by"}
            and call_attr_chain(kw_map["hidden_by"]) == "er.RegistryEntryHider.INTEGRATION"
        )
        if not is_outbox_autohide:
            failures.append(
                f"[VOICE FOLLOWS ME] {rel}:{node.lineno} calls async_update_entity() "
                "(foreign entity mutation forbidden; area_id= strictly banned)"
            )


def _check_area_sync_and_verbs(
    latter_dir: Path,
    parsed_trees: dict[str, ast.Module],
    failures: list[str],
) -> None:
    area_sync_sites: list[str] = []
    allowed_sync_rel = "custom_components/latter/areas/sync.py"
    for rel, tree in sorted(parsed_trees.items()):
        for top in ast.walk(tree):
            if not isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for sub in ast.walk(top):
                if not isinstance(sub, ast.Call):
                    continue
                tail = call_attr_chain(sub.func).rsplit(".", 1)[-1]
                if tail != "async_update_device":
                    continue
                kw_names = {kw.arg for kw in sub.keywords if kw.arg}
                if "area_id" in kw_names:
                    area_sync_sites.append(f"{rel}:{top.name}")
                    if rel != allowed_sync_rel or top.name != "sync_esphome_device_area":
                        failures.append(
                            f"[VOICE FOLLOWS ME] {rel}:{sub.lineno} updates device area_id "
                            f"outside {allowed_sync_rel}:sync_esphome_device_area"
                        )
    if not area_sync_sites:
        failures.append(
            f"[VOICE FOLLOWS ME] sync_esphome_device_area() in {allowed_sync_rel} "
            "not found or missing area_id update"
        )

    actions_path = latter_dir / "areas" / "actions.py"
    actions_txt = actions_path.read_text(encoding="utf-8") if actions_path.is_file() else ""
    if (
        '"alarm_control_panel"' not in actions_txt
        or '"lock"' not in actions_txt
        or "explicit_action_required" not in actions_txt
    ):
        failures.append(
            "[SECURITY VERBS] areas/actions.py must enforce explicit_action_required "
            "on lock and alarm_control_panel"
        )


def _check_diagnostics_redaction(
    parsed_trees: dict[str, ast.Module],
    failures: list[str],
) -> None:
    diag_rel = "custom_components/latter/diagnostics.py"
    diag_tree = parsed_trees.get(diag_rel)
    if diag_tree is None:
        failures.append(f"[DIAGNOSTICS REDACT] {diag_rel} is missing")
        return

    redacted_keys: set[str] = set()
    diag_funcs: dict[str, ast.AsyncFunctionDef] = {}
    for node in diag_tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            is_redact_const = any(
                isinstance(t, ast.Name) and t.id == "REDACTED_FIELD_KEYS" for t in targets
            )
            if is_redact_const and node.value:
                redacted_keys.update(
                    sub.value
                    for sub in ast.walk(node.value)
                    if isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                )
        elif isinstance(node, ast.AsyncFunctionDef):
            diag_funcs[node.name] = node

    missing_redact = REQUIRED_REDACTED_KEYS - redacted_keys
    if missing_redact:
        failures.append(
            "[DIAGNOSTICS REDACT] diagnostics.py REDACTED_FIELD_KEYS missing "
            f"{sorted(missing_redact)}"
        )
    for fn_name in ("async_get_config_entry_diagnostics", "async_get_device_diagnostics"):
        fn_node = diag_funcs.get(fn_name)
        if fn_node is None:
            failures.append(f"[DIAGNOSTICS REDACT] diagnostics.py missing {fn_name}()")
            continue
        called_names = {
            call_attr_chain(c.func).rsplit(".", 1)[-1]
            for c in ast.walk(fn_node)
            if isinstance(c, ast.Call)
        }
        if not {"async_redact_data", "sanitize_diagnostics_payload"}.issubset(called_names):
            failures.append(
                f"[DIAGNOSTICS REDACT] diagnostics.py:{fn_name}() must call both "
                "async_redact_data and sanitize_diagnostics_payload"
            )


def _extract_string_tuple_assign(tree: ast.Module, name: str) -> set[str]:
    values: set[str] = set()
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            for elt in ast.walk(node.value):
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    values.add(elt.value)
    return values


def _check_service_schema_parity(latter_dir: Path, failures: list[str]) -> None:
    services_yaml = latter_dir / "services.yaml"
    const_path = latter_dir / "const.py"
    proto_path = latter_dir / "protocol_v3.json"

    if not services_yaml.is_file():
        failures.append("[HA QUALITY] custom_components/latter/services.yaml is missing")
    else:
        yaml_services = set(
            re.findall(r"(?m)^([a-z][a-z0-9_]*):\s*$", services_yaml.read_text(encoding="utf-8"))
        )
        if yaml_services != EXPECTED_PUBLIC_SERVICES:
            failures.append(
                f"[PUBLIC SERVICES] services.yaml keys ({sorted(yaml_services)}) != "
                f"canonical 5 PUBLIC_SERVICES ({sorted(EXPECTED_PUBLIC_SERVICES)})"
            )

    const_txt = const_path.read_text(encoding="utf-8") if const_path.is_file() else ""
    const_svcs = set(
        re.findall(
            r'(?m)^SERVICE_[A-Z0-9_]+(?:\s*:\s*[^=\r\n]+)?\s*=\s*"([a-z0-9_]+)"',
            const_txt,
        )
    )
    const_rpcs = set(
        re.findall(
            r'(?m)^RPC_[A-Z0-9_]+(?:\s*:\s*[^=\r\n]+)?\s*=\s*"([a-z0-9_]+)"',
            const_txt,
        )
    )
    if const_svcs != EXPECTED_PUBLIC_SERVICES:
        failures.append(
            f"[PUBLIC SERVICES] const.py SERVICE_* values ({sorted(const_svcs)}) != "
            f"canonical 5 PUBLIC_SERVICES ({sorted(EXPECTED_PUBLIC_SERVICES)})"
        )

    if proto_path.is_file():
        proto_data = json.loads(proto_path.read_text(encoding="utf-8"))
        proto_ha_svcs = set(proto_data.get("ha_services", {}).keys())
        proto_rpcs = set(proto_data.get("rpc_methods", {}).keys())
        if proto_ha_svcs != EXPECTED_PUBLIC_SERVICES:
            failures.append(
                f"[PUBLIC SERVICES] protocol_v3.json ha_services ({sorted(proto_ha_svcs)}) != "
                f"PUBLIC_SERVICES ({sorted(EXPECTED_PUBLIC_SERVICES)})"
            )
        if const_rpcs != proto_rpcs:
            failures.append(
                "[RPC DISPATCHER] const.py RPC_* constants != protocol_v3.json rpc_methods "
                f"(diff={sorted(const_rpcs ^ proto_rpcs)})"
            )


def _check_services_and_rpc_split(
    latter_dir: Path,
    parsed_trees: dict[str, ast.Module],
    failures: list[str],
) -> None:
    """Enforce exact 5 public services vs private 20-method LatterRpcDispatcher."""
    _check_service_schema_parity(latter_dir, failures)
    pub_rel = "custom_components/latter/services/public_actions.py"
    disp_rel = "custom_components/latter/services/rpc_dispatcher.py"
    reg_calls = 0
    for rel, tree in sorted(parsed_trees.items()):
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and call_attr_chain(node.func).endswith(
                "services.async_register"
            ):
                reg_calls += 1
                if rel != pub_rel:
                    failures.append(
                        f"[PUBLIC SERVICES] {rel}:{node.lineno} calls services.async_register "
                        f"outside {pub_rel}"
                    )
    if reg_calls != len(EXPECTED_PUBLIC_SERVICES):
        failures.append(
            f"[PUBLIC SERVICES] Expected {len(EXPECTED_PUBLIC_SERVICES)} "
            f"hass.services.async_register calls in {pub_rel}, found {reg_calls}"
        )

    disp_tree = parsed_trees.get(disp_rel)
    has_dispatcher = disp_tree is not None and any(
        isinstance(n, ast.ClassDef) and n.name == "LatterRpcDispatcher"
        for n in disp_tree.body
    )
    if not has_dispatcher:
        failures.append(
            f"[RPC DISPATCHER] {disp_rel} must define class LatterRpcDispatcher"
        )


def _check_http_and_runtime_sources(
    root: Path,
    latter_dir: Path,
    all_latter_py: list[Path],
    failures: list[str],
) -> None:
    http_dir = latter_dir / "http"
    signing_py = http_dir / "signing.py"
    if not signing_py.is_file():
        failures.append("[SECURITY] custom_components/latter/http/signing.py is missing")
    else:
        http_combined = "\n".join(
            p.read_text(encoding="utf-8") for p in sorted(http_dir.glob("*.py"))
        )
        if "verify_resource(" not in http_combined or "camera_audio:" not in http_combined:
            failures.append(
                "[SECURITY] custom_components/latter/http/ must verify HMAC resource "
                "signatures including camera_audio params"
            )

    for pf in all_latter_py:
        ptxt = pf.read_text(encoding="utf-8")
        rel = pf.relative_to(root).as_posix()
        if re.search(r"\bsocket\.socket\s*\(", ptxt):
            failures.append(
                f"[EVENT LOOP] {rel} opens a raw socket; use async HA network helpers"
            )
        if re.search(r"\bself\.device_entry\s*=", ptxt):
            failures.append(
                f"[DEVICE REGISTRY] {rel} assigns self.device_entry directly (forbidden)"
            )
        if re.search(r"\.states\.async_all\s*\(", ptxt):
            failures.append(
                f"[AREA STATE INDEX] {rel} calls hass.states.async_all() (use AreaStateIndex)"
            )
        if re.search(r"\bDataUpdateCoordinator\b", ptxt):
            failures.append(
                f"[PUSH COORDINATOR] {rel} references DataUpdateCoordinator "
                "(use pure push coordinator)"
            )
        m_wan = ZERO_WAN_RE.search(ptxt)
        if m_wan:
            failures.append(
                f"[ZERO WAN] {rel} contains forbidden cloud/WAN endpoint "
                f"reference {m_wan.group(0)!r}"
            )


_PLATFORM_RELS: Final[frozenset[str]] = frozenset(
    {
        "custom_components/latter/binary_sensor.py",
        "custom_components/latter/button.py",
        "custom_components/latter/device_tracker.py",
        "custom_components/latter/light.py",
        "custom_components/latter/number.py",
        "custom_components/latter/select.py",
        "custom_components/latter/sensor.py",
        "custom_components/latter/switch.py",
    }
)


def _is_raw_domain_key(node: ast.AST) -> bool:
    return (isinstance(node, ast.Name) and node.id == "DOMAIN") or (
        isinstance(node, ast.Constant) and node.value == "latter"
    )


def _check_hass_data_and_entity_naming(
    parsed_trees: dict[str, ast.Module],
    failures: list[str],
) -> None:
    """Enforce typed `HassKey` / `entry.runtime_data` and native HA 2026.11 entity naming."""
    for rel, tree in sorted(parsed_trees.items()):
        is_platform = rel in _PLATFORM_RELS
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Attribute)
                and node.value.attr == "data"
                and _is_raw_domain_key(node.slice)
            ):
                failures.append(
                    f"[NO UNTYPED HASS DATA] {rel}:{node.lineno} indexes untyped "
                    "hass.data[DOMAIN] (use entry.runtime_data or get_domain_data())"
                )
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"get", "setdefault", "pop"}
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "data"
                and node.args
                and _is_raw_domain_key(node.args[0])
            ):
                failures.append(
                    f"[NO UNTYPED HASS DATA] {rel}:{node.lineno} calls untyped "
                    f"hass.data.{node.func.attr}(DOMAIN) (use entry.runtime_data or get_domain_data())"
                )
            elif is_platform and isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                failures.extend(
                    f"[NO MANUAL ENTITY ID] {rel}:{node.lineno} assigns self.entity_id "
                    "(rely on _attr_has_entity_name + translation_key)"
                    for target in targets
                    if isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                    and target.attr == "entity_id"
                )


def check_ast_and_runtime_invariants(
    root: Path,
    parsed_trees: dict[str, ast.Module],
    all_latter_py: list[Path],
    exception_keys: set[str],
    failures: list[str],
) -> None:
    """Run all AST security, bound-identity, service/RPC, redaction, and Zero-WAN checks."""
    latter_dir = root / "custom_components" / "latter"
    id_tree = parsed_trees.get("custom_components/latter/identity.py")
    has_esphome_service_helper = id_tree is not None and any(
        isinstance(n, ast.FunctionDef) and n.name == "esphome_service"
        for n in id_tree.body
    )
    if not has_esphome_service_helper:
        failures.append(
            "[NO UNBOUND SERVICE] custom_components/latter/identity.py must define "
            "esphome_service()"
        )

    for rel, tree in sorted(parsed_trees.items()):
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                exc_t = node.type
                if isinstance(exc_t, ast.Name) and exc_t.id in {
                    "ImportError",
                    "ModuleNotFoundError",
                }:
                    failures.append(
                        f"[DAG NO SHIMS] {rel}:{node.lineno} contains forbidden "
                        f"try/except {exc_t.id} compatibility shim"
                    )
            elif isinstance(node, ast.Call):
                _check_call_node(rel, node, exception_keys, failures)

    _check_hass_data_and_entity_naming(parsed_trees, failures)
    _check_area_sync_and_verbs(latter_dir, parsed_trees, failures)
    _check_diagnostics_redaction(parsed_trees, failures)
    _check_services_and_rpc_split(latter_dir, parsed_trees, failures)
    _check_http_and_runtime_sources(root, latter_dir, all_latter_py, failures)
