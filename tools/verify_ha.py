#!/usr/bin/env python3
"""Cross-platform static architecture, security, Studio, and HA compliance verifier for ha-latter.

Runs in <1 second with Python 3.11+ standard library only (zero third-party dependencies),
enforcing the 28-module topology, AST security/identity invariants, pyproject/manifest parity,
and Latter Studio guardrails identically in local development and GitHub Actions CI.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = ROOT / "custom_components" / "latter"
STUDIO_DIR = LATTER_DIR / "studio"
STUDIO_JS = LATTER_DIR / "frontend" / "latter-studio.js"
STUDIO_DOC = ROOT / "docs" / "studio-design.md"

SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".esphome",
    "node_modules",
    ".coverage",
    "htmlcov",
    ".venv",
    "venv",
}
TEXT_EXTS = {".py", ".json", ".yaml", ".yml", ".js", ".ts", ".md", ".toml"}

BANNED_TERMS_RE = re.compile(r"\b(household|households)\b", re.IGNORECASE)
SINGLE_QUOTED_PLACEHOLDER_RE = re.compile(r"'\{[a-zA-Z0-9_]+\}'")

EXPECTED_ROOT_MODULES: frozenset[str] = frozenset(
    {
        "__init__.py",
        "areas.py",
        "backup.py",
        "binary_sensor.py",
        "config_flow.py",
        "const.py",
        "coordinator.py",
        "device_tracker.py",
        "diagnostics.py",
        "doorbell.py",
        "feeds.py",
        "groups.py",
        "http.py",
        "hub.py",
        "identity.py",
        "media.py",
        "media_browse.py",
        "presence.py",
        "protocol.py",
        "remotes.py",
        "repairs.py",
        "sensor.py",
        "services.py",
        "wallpapers.py",
    }
)

EXPECTED_STUDIO_MODULES: frozenset[str] = frozenset(
    {
        "__init__.py",
        "commands.py",
        "payload.py",
        "settings.py",
    }
)

STDLIB_ONLY_MODULES: tuple[str, ...] = (
    "protocol.py",
    "studio/settings.py",
)

FORBIDDEN_NON_STDLIB_ROOTS: frozenset[str] = frozenset(
    {"homeassistant", "aiohttp", "voluptuous", "PIL"}
)

REQUIRED_REDACTED_KEYS: frozenset[str] = frozenset(
    {
        "ble_beacon_uuid",
        "ble_target_address",
        "hmac_secret_hex",
        "mac",
        "payload",
        "security_pin",
        "security_pin_hash",
        "system_ble_uuid",
    }
)

MIN_SDK_REV_FLOOR = 2026111039


def iter_repo_files(base: Path) -> list[Path]:
    files: list[Path] = []
    if not base.is_dir():
        return files
    for p in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            files.append(p)
    return files


def extract_css_blocks(source: str) -> list[str]:
    """Extract CSS stylesheets embedded in Studio JS/TS source."""
    blocks: list[str] = []
    for m in re.finditer(r"(?:style\.textContent\s*=\s*`|\bcss`)([\s\S]*?)`", source):
        blocks.append(m.group(1))
    return blocks


def strip_host_block(css_text: str) -> str:
    """Remove :host { ... } token blocks so component rules can be checked for raw literals."""
    out: list[str] = []
    i = 0
    n = len(css_text)
    while i < n:
        m = re.search(r":host(?:\([^)]*\))?\s*\{", css_text[i:])
        if not m:
            out.append(css_text[i:])
            break
        start = i + m.start()
        out.append(css_text[i:start])
        brace_pos = i + m.end() - 1
        depth = 0
        j = brace_pos
        while j < n:
            if css_text[j] == "{":
                depth += 1
            elif css_text[j] == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        i = j
    return "".join(out)


def _call_attr_chain(node: ast.AST) -> str:
    """Flatten `a.b.c` attribute chains for AST call inspection."""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _check_ast_security_and_identity(
    parsed_trees: dict[str, ast.Module],
    failures: list[str],
) -> None:
    """Enforce AST semantic guardrails across custom_components/latter."""
    # [NO UNBOUND SERVICE]
    id_tree = parsed_trees.get("custom_components/latter/identity.py")
    has_esphome_service_helper = id_tree is not None and any(
        isinstance(n, ast.FunctionDef) and n.name == "esphome_service"
        for n in id_tree.body
    )
    if not has_esphome_service_helper:
        failures.append(
            "[NO UNBOUND SERVICE] custom_components/latter/identity.py must define esphome_service()"
        )

    for rel, tree in sorted(parsed_trees.items()):
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                exc_t = node.type
                if isinstance(exc_t, ast.Name) and exc_t.id in {"ImportError", "ModuleNotFoundError"}:
                    failures.append(
                        f"[28-MODULE TOPOLOGY] {rel}:{node.lineno} contains forbidden try/except {exc_t.id} shim"
                    )

            if not isinstance(node, ast.Call):
                continue

            chain = _call_attr_chain(node.func)
            func_tail = chain.rsplit(".", 1)[-1]

            # Check esphome service calls: never concatenate/f-string unbound slugs
            if func_tail in {"async_call", "has_service"} and len(node.args) >= 2:
                dom_arg, svc_arg = node.args[0], node.args[1]
                if isinstance(dom_arg, ast.Constant) and dom_arg.value == "esphome":
                    if isinstance(svc_arg, (ast.JoinedStr, ast.BinOp)):
                        failures.append(
                            f"[NO UNBOUND SERVICE] {rel}:{node.lineno} constructs unbound esphome service string "
                            "(must resolve via esphome_service())"
                        )
                    elif (
                        isinstance(svc_arg, ast.Call)
                        and isinstance(svc_arg.func, ast.Attribute)
                        and svc_arg.func.attr == "format"
                    ):
                        failures.append(
                            f"[NO UNBOUND SERVICE] {rel}:{node.lineno} formats unbound esphome service string"
                        )

                # [SECURITY VERBS]: lock and alarm_control_panel never call toggle
                if (
                    isinstance(dom_arg, ast.Constant)
                    and dom_arg.value in {"lock", "alarm_control_panel"}
                    and isinstance(svc_arg, ast.Constant)
                    and svc_arg.value == "toggle"
                ):
                    failures.append(
                        f"[SECURITY VERBS] {rel}:{node.lineno} dispatches forbidden 'toggle' on {dom_arg.value}"
                    )

            # [VOICE FOLLOWS ME]: zero entity_registry mutations, and area_id device updates only in areas.py
            if func_tail == "async_update_entity":
                failures.append(
                    f"[VOICE FOLLOWS ME] {rel}:{node.lineno} calls async_update_entity() (foreign entity mutation forbidden)"
                )

    # Track enclosing function for async_update_device(..., area_id=...)
    area_sync_sites: list[str] = []
    for rel, tree in sorted(parsed_trees.items()):
        for top in ast.walk(tree):
            if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for sub in ast.walk(top):
                    if not isinstance(sub, ast.Call):
                        continue
                    tail = _call_attr_chain(sub.func).rsplit(".", 1)[-1]
                    if tail == "async_update_device":
                        kw_names = {kw.arg for kw in sub.keywords if kw.arg}
                        if "area_id" in kw_names:
                            site = f"{rel}:{top.name}"
                            area_sync_sites.append(site)
                            if rel != "custom_components/latter/areas.py" or top.name != "sync_esphome_device_area":
                                failures.append(
                                    f"[VOICE FOLLOWS ME] {rel}:{sub.lineno} updates device area_id outside "
                                    "areas.py:sync_esphome_device_area"
                                )
    if not area_sync_sites:
        failures.append(
            "[VOICE FOLLOWS ME] sync_esphome_device_area() in areas.py not found or missing area_id update"
        )

    # Verify areas.py lock & alarm explicit verb guards
    areas_txt = (LATTER_DIR / "areas.py").read_text(encoding="utf-8") if (LATTER_DIR / "areas.py").is_file() else ""
    if (
        '"alarm_control_panel"' not in areas_txt
        or '"lock"' not in areas_txt
        or "explicit_action_required" not in areas_txt
    ):
        failures.append(
            "[SECURITY VERBS] areas.py must enforce explicit_action_required on lock and alarm_control_panel"
        )

    # [DIAGNOSTICS REDACT]
    diag_rel = "custom_components/latter/diagnostics.py"
    diag_tree = parsed_trees.get(diag_rel)
    if diag_tree is None:
        failures.append("[DIAGNOSTICS REDACT] custom_components/latter/diagnostics.py is missing")
    else:
        redacted_keys: set[str] = set()
        diag_funcs: dict[str, ast.AsyncFunctionDef] = {}
        for node in diag_tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == "REDACTED_FIELD_KEYS" for t in targets) and node.value:
                    for sub in ast.walk(node.value):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                            redacted_keys.add(sub.value)
            elif isinstance(node, ast.AsyncFunctionDef):
                diag_funcs[node.name] = node

        missing_redact = REQUIRED_REDACTED_KEYS - redacted_keys
        if missing_redact:
            failures.append(
                f"[DIAGNOSTICS REDACT] diagnostics.py REDACTED_FIELD_KEYS missing {sorted(missing_redact)}"
            )
        for fn_name in ("async_get_config_entry_diagnostics", "async_get_device_diagnostics"):
            fn_node = diag_funcs.get(fn_name)
            if fn_node is None:
                failures.append(f"[DIAGNOSTICS REDACT] diagnostics.py missing {fn_name}()")
                continue
            called_names = {
                _call_attr_chain(c.func).rsplit(".", 1)[-1]
                for c in ast.walk(fn_node)
                if isinstance(c, ast.Call)
            }
            if not {"async_redact_data", "sanitize_diagnostics_payload"}.issubset(called_names):
                failures.append(
                    f"[DIAGNOSTICS REDACT] diagnostics.py:{fn_name}() must call both async_redact_data and sanitize_diagnostics_payload"
                )


def main() -> int:
    failures: list[str] = []
    parsed_latter_trees: dict[str, ast.Module] = {}

    # 1. UTF-8 no-BOM, Python AST compile, JSON/TOML validity, and terminology
    for path in iter_repo_files(ROOT):
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        raw = path.read_bytes()
        rel = path.relative_to(ROOT).as_posix()
        if raw.startswith(b"\xef\xbb\xbf"):
            failures.append(f"[UTF8 NO-BOM] {rel} starts with a UTF-8 BOM")
        try:
            txt = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            failures.append(f"[UTF8] {rel} is not valid UTF-8: {exc}")
            continue

        if path.suffix == ".py":
            try:
                tree = ast.parse(txt, filename=rel)
                if rel.startswith("custom_components/latter/"):
                    parsed_latter_trees[rel] = tree
            except SyntaxError as exc:
                failures.append(f"[PYTHON AST] {rel}:{exc.lineno}: {exc.msg}")
        elif path.suffix == ".json":
            try:
                json.loads(txt)
            except ValueError as exc:
                failures.append(f"[JSON] {rel} failed JSON parse: {exc}")
        elif path.suffix == ".toml":
            try:
                tomllib.loads(txt)
            except tomllib.TOMLDecodeError as exc:
                failures.append(f"[TOML] {rel} failed TOML parse: {exc}")

        if rel.startswith(("custom_components/", "frontend_src/")):
            m = BANNED_TERMS_RE.search(txt)
            if m:
                failures.append(f"[TERMINOLOGY] {rel} contains banned term {m.group(0)!r}")

    # 2. [28-MODULE TOPOLOGY] & pure-stdlib leaf enforcement
    actual_root_py = {p.name for p in LATTER_DIR.glob("*.py")}
    actual_studio_py = {p.name for p in STUDIO_DIR.glob("*.py")} if STUDIO_DIR.is_dir() else set()
    all_latter_py = [p for p in iter_repo_files(LATTER_DIR) if p.suffix == ".py"]

    missing_root = EXPECTED_ROOT_MODULES - actual_root_py
    extra_root = actual_root_py - EXPECTED_ROOT_MODULES
    missing_studio = EXPECTED_STUDIO_MODULES - actual_studio_py
    extra_studio = actual_studio_py - EXPECTED_STUDIO_MODULES

    if missing_root:
        failures.append(f"[28-MODULE TOPOLOGY] Missing root module(s): {sorted(missing_root)}")
    if extra_root:
        failures.append(f"[28-MODULE TOPOLOGY] Unexpected root module(s): {sorted(extra_root)}")
    if missing_studio:
        failures.append(f"[28-MODULE TOPOLOGY] Missing studio/ module(s): {sorted(missing_studio)}")
    if extra_studio:
        failures.append(f"[28-MODULE TOPOLOGY] Unexpected studio/ module(s): {sorted(extra_studio)}")

    unexpected_nested = [
        p.relative_to(LATTER_DIR).as_posix()
        for p in all_latter_py
        if p.parent not in {LATTER_DIR, STUDIO_DIR}
    ]
    if unexpected_nested:
        failures.append(
            f"[28-MODULE TOPOLOGY] Legacy nested subpackage file(s) present: {sorted(unexpected_nested)}"
        )
    if len(all_latter_py) != 28:
        failures.append(
            f"[28-MODULE TOPOLOGY] Expected exact 28 .py modules in custom_components/latter, found {len(all_latter_py)}"
        )

    for std_rel in STDLIB_ONLY_MODULES:
        full_rel = f"custom_components/latter/{std_rel}"
        stree = parsed_latter_trees.get(full_rel)
        if stree is None:
            continue
        for node in ast.walk(stree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_pkg = alias.name.split(".", 1)[0]
                    if root_pkg in FORBIDDEN_NON_STDLIB_ROOTS:
                        failures.append(
                            f"[28-MODULE TOPOLOGY] {full_rel}:{node.lineno} imports non-stdlib package {root_pkg!r}"
                        )
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                root_pkg = node.module.split(".", 1)[0]
                if root_pkg in FORBIDDEN_NON_STDLIB_ROOTS:
                    failures.append(
                        f"[28-MODULE TOPOLOGY] {full_rel}:{node.lineno} imports non-stdlib package {root_pkg!r}"
                    )

    # 3. Translations parity, [HA QUALITY], and services.yaml parity
    strings_path = LATTER_DIR / "strings.json"
    en_path = LATTER_DIR / "translations" / "en.json"
    if not strings_path.is_file() or not en_path.is_file():
        failures.append("[HA QUALITY] strings.json or translations/en.json missing")
    else:
        s_bytes = strings_path.read_bytes()
        e_bytes = en_path.read_bytes()
        if s_bytes != e_bytes:
            failures.append("[HA QUALITY] strings.json and translations/en.json must be byte-identical")
        s_txt = s_bytes.decode("utf-8", errors="replace")
        m_sq = SINGLE_QUOTED_PLACEHOLDER_RE.search(s_txt)
        if m_sq:
            failures.append(f"[HA QUALITY] strings.json contains single-quoted placeholder {m_sq.group(0)}")

    manifest = json.loads((LATTER_DIR / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("integration_type") != "hub"
        or manifest.get("iot_class") != "local_push"
        or manifest.get("single_config_entry") is not True
        or manifest.get("config_flow") is not True
    ):
        failures.append("[HA QUALITY] manifest.json must declare hub, local_push, single_config_entry, config_flow")

    qscale_path = LATTER_DIR / "quality_scale.yaml"
    if not qscale_path.is_file():
        failures.append("[HA QUALITY] custom_components/latter/quality_scale.yaml is missing")
    else:
        qtxt = qscale_path.read_text(encoding="utf-8")
        for req_rule in ("action-setup:", "common-modules:", "config-flow:", "diagnostics:", "repair-issues:", "runtime-data:"):
            if req_rule not in qtxt:
                failures.append(f"[HA QUALITY] quality_scale.yaml missing rule {req_rule[:-1]!r}")

    services_yaml_path = LATTER_DIR / "services.yaml"
    const_txt = (LATTER_DIR / "const.py").read_text(encoding="utf-8") if (LATTER_DIR / "const.py").is_file() else ""
    if not services_yaml_path.is_file():
        failures.append("[HA QUALITY] custom_components/latter/services.yaml is missing")
    else:
        yaml_services = set(
            re.findall(r"(?m)^([a-z][a-z0-9_]*):\s*$", services_yaml_path.read_text(encoding="utf-8"))
        )
        const_services = set(
            re.findall(r'(?m)^SERVICE_[A-Z0-9_]+(?:\s*:\s*[^=\r\n]+)?\s*=\s*"([a-z0-9_]+)"', const_txt)
        )
        if yaml_services != const_services:
            failures.append(
                f"[HA QUALITY] services.yaml keys != const.py SERVICE_* values "
                f"(yaml_only={sorted(yaml_services - const_services)}, const_only={sorted(const_services - yaml_services)})"
            )

    # 4. [PYPROJECT PARITY] & [VERSION LOCKSTEP]
    ha_ver = str(manifest.get("version", ""))
    m_const_ver = re.search(r'INTEGRATION_VERSION(?:\s*:\s*[^=]+)?\s*=\s*"([^"]+)"', const_txt)
    const_ver = m_const_ver.group(1) if m_const_ver else None
    if const_ver != ha_ver:
        failures.append(f"[VERSION LOCKSTEP] manifest.json ({ha_ver}) != INTEGRATION_VERSION ({const_ver})")

    pyproject_path = ROOT / "pyproject.toml"
    if not pyproject_path.is_file():
        failures.append("[PYPROJECT PARITY] pyproject.toml is missing")
    else:
        pdata = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        proj = pdata.get("project", {})
        pyproj_ver = str(proj.get("version", ""))
        lic = proj.get("license")
        lic_text = lic.get("text") if isinstance(lic, dict) else str(lic or "")
        if pyproj_ver != ha_ver:
            failures.append(f"[PYPROJECT PARITY] pyproject.toml version ({pyproj_ver}) != manifest.json ({ha_ver})")
        if lic_text != "Apache-2.0":
            failures.append(f"[PYPROJECT PARITY] pyproject.toml license is {lic_text!r} (expected 'Apache-2.0')")

    m_sdk = re.search(r"(?m)^\s*MIN_FIRMWARE_SDK_REV(?:\s*:\s*[^=\r\n]+)?\s*=\s*(\d+)\b", const_txt)
    if not m_sdk:
        failures.append("[VERSION LOCKSTEP] const.py missing MIN_FIRMWARE_SDK_REV")
    else:
        ha_sdk_rev = int(m_sdk.group(1))
        if ha_sdk_rev < MIN_SDK_REV_FLOOR:
            failures.append(
                f"[VERSION LOCKSTEP] MIN_FIRMWARE_SDK_REV ({ha_sdk_rev}) < floor ({MIN_SDK_REV_FLOOR})"
            )
        sibling_core_inc = ROOT.parent / "esphome-latter-core" / "include"
        if sibling_core_inc.is_dir():
            core_revs = [
                int(m_core_rev.group(1))
                for hfile in sorted(sibling_core_inc.glob("*.h"))
                for m_core_rev in re.finditer(
                    r"(?m)^\s*#\s*define\s+LATTER_SDK_REV\s+(\d+)L?\b",
                    hfile.read_text(encoding="utf-8", errors="replace"),
                )
            ]
            if core_revs and max(core_revs) != ha_sdk_rev:
                failures.append(
                    f"[VERSION LOCKSTEP] MIN_FIRMWARE_SDK_REV ({ha_sdk_rev}) != "
                    f"esphome-latter-core LATTER_SDK_REV ({max(core_revs)})"
                )

    sibling_base = ROOT.parent / "esphome-latter-core" / "modules" / "base.yaml"
    if sibling_base.is_file():
        m_core = re.search(r'(?m)^\s*version:\s*"([^"]+)"', sibling_base.read_text(encoding="utf-8"))
        if m_core:
            ha_mm = ".".join(ha_ver.split(".")[:2])
            core_mm = ".".join(m_core.group(1).split(".")[:2])
            if ha_mm != core_mm:
                failures.append(
                    f"[VERSION LOCKSTEP] ha-latter ({ha_ver}) major.minor != esphome-latter-core ({m_core.group(1)})"
                )

    # 5. Dev gate check on validate.yml
    val_yml = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    if "\n  promote:" not in val_yml or "refs/heads/main" not in val_yml:
        failures.append("[DEV GATE] .github/workflows/validate.yml must fast-forward main from promote job")

    # 6. AST & Python runtime invariants
    _check_ast_security_and_identity(parsed_latter_trees, failures)

    http_path = LATTER_DIR / "http.py"
    if not http_path.is_file():
        failures.append("[SECURITY] custom_components/latter/http.py is missing")
    else:
        http_txt = http_path.read_text(encoding="utf-8")
        if re.search(r"\bsocket\.socket\s*\(", http_txt):
            failures.append("[EVENT LOOP] http.py opens a raw socket; use async HA network helpers")
        if "verify_resource(" not in http_txt or "camera_audio:" not in http_txt:
            failures.append("[SECURITY] http.py must verify HMAC resource signatures including camera_audio params")

    for pf in all_latter_py:
        ptxt = pf.read_text(encoding="utf-8")
        rel = pf.relative_to(ROOT).as_posix()
        if re.search(r"\bself\.device_entry\s*=", ptxt):
            failures.append(f"[DEVICE REGISTRY] {rel} assigns self.device_entry directly (forbidden)")
        if re.search(r"\.states\.async_all\s*\(", ptxt):
            failures.append(f"[AREA STATE INDEX] {rel} calls hass.states.async_all() (use AreaStateIndex)")
        if re.search(r"\bDataUpdateCoordinator\b", ptxt):
            failures.append(f"[PUSH COORDINATOR] {rel} references DataUpdateCoordinator (use pure push coordinator)")

    # 7. [STUDIO NO REST], [STUDIO DESIGN DOC], and CSS token invariants
    if not STUDIO_DOC.is_file():
        failures.append("[STUDIO DESIGN DOC] docs/studio-design.md is missing")
    else:
        doc_txt = STUDIO_DOC.read_text(encoding="utf-8")
        for marker in ("[STUDIO TOKENS]", "[STUDIO INLINE STYLES]", "## Decision log", "D-001"):
            if marker not in doc_txt:
                failures.append(f"[STUDIO DESIGN DOC] docs/studio-design.md missing required section/marker {marker!r}")

    for s_py in STUDIO_DIR.glob("*.py") if STUDIO_DIR.is_dir() else ():
        s_py_txt = s_py.read_text(encoding="utf-8")
        if "HomeAssistantView" in s_py_txt:
            failures.append(
                f"[STUDIO NO REST] studio/{s_py.name} defines a HomeAssistantView (Studio uses websocket_api only)"
            )
    studio_init = STUDIO_DIR / "__init__.py"
    if studio_init.is_file():
        s_init_txt = studio_init.read_text(encoding="utf-8")
        if "/latter_static" in s_init_txt or re.search(r"StaticPathConfig\(\s*STATIC_URL_PREFIX\s*,", s_init_txt):
            failures.append(
                "[STUDIO NO REST] studio/__init__.py must mount only versioned static prefix (/latter_ui_<ver>)"
            )

    studio_sources = [STUDIO_JS] if STUDIO_JS.is_file() else []
    frontend_src_dir = ROOT / "frontend_src"
    if frontend_src_dir.is_dir():
        studio_sources.extend(p for p in iter_repo_files(frontend_src_dir) if p.suffix in {".ts", ".js"})

    if not STUDIO_JS.is_file():
        failures.append("[STUDIO] custom_components/latter/frontend/latter-studio.js is missing")

    for sf in studio_sources:
        stxt = sf.read_text(encoding="utf-8")
        rel = sf.relative_to(ROOT).as_posix()
        if re.search(r"\bfetch\s*\(", stxt):
            failures.append(f"[STUDIO NO REST] {rel} calls fetch(); Studio must use websocket_api (hass.callWS)")
        for xhr_m in re.finditer(r"\.open\s*\(\s*['\"]([A-Z]+)['\"]\s*,\s*([^,\)]+)", stxt):
            method, arg_expr = xhr_m.group(1), xhr_m.group(2).strip()
            if method != "POST" or "/api/latter/wallpaper/upload" not in stxt:
                failures.append(
                    f"[STUDIO NO REST] {rel} opens XHR ({method} {arg_expr}) outside "
                    "POST /api/latter/wallpaper/upload"
                )
        if "hassTokens" in stxt or "hass-subpage" in stxt or "shadowRoot.querySelector" in stxt:
            failures.append(f"[STUDIO INTERNALS] {rel} accesses forbidden HA frontend internals")
        for bad_style in re.finditer(r'\bstyle="(?!\s*--|\s*\$\{)[^"]+"', stxt):
            failures.append(f"[STUDIO INLINE STYLES] {rel} uses non-token inline style: {bad_style.group(0)[:60]}")
        for css_block in extract_css_blocks(stxt):
            css_no_comments = re.sub(r"/\*[\s\S]*?\*/", "", css_block)
            body_css = strip_host_block(css_no_comments)
            if re.search(r"\bfont-size\s*:\s*(?!var\(|inherit\b|100%\b)", body_css):
                failures.append(f"[STUDIO TOKENS] {rel} uses literal font-size outside :host")
            if re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(", body_css):
                failures.append(f"[STUDIO TOKENS] {rel} uses color literal outside :host")

    if failures:
        print(f"verify_ha.py FAILED ({len(failures)} issue(s)):")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("verify_ha.py PASSED (0 issues)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
