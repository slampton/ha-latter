#!/usr/bin/env python3
"""Cross-platform static architecture, security, Studio, and HA compliance verifier for ha-latter.

Runs in <1 second with Python 3.11+ standard library only (zero third-party dependencies),
enforcing repository guardrails identically in local development and GitHub Actions CI.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = ROOT / "custom_components" / "latter"
STUDIO_JS = LATTER_DIR / "frontend" / "latter-studio.js"

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
}
TEXT_EXTS = {".py", ".json", ".yaml", ".yml", ".js", ".ts", ".md"}

BANNED_TERMS_RE = re.compile(r"\b(household|households)\b", re.IGNORECASE)
SINGLE_QUOTED_PLACEHOLDER_RE = re.compile(r"'\{[a-zA-Z0-9_]+\}'")


def iter_repo_files(base: Path) -> list[Path]:
    files: list[Path] = []
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


def main() -> int:
    failures: list[str] = []

    # 1. UTF-8 no-BOM, Python AST compile, and JSON validity
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
                ast.parse(txt, filename=rel)
            except SyntaxError as exc:
                failures.append(f"[PYTHON AST] {rel}:{exc.lineno}: {exc.msg}")
        elif path.suffix == ".json":
            try:
                json.loads(txt)
            except ValueError as exc:
                failures.append(f"[JSON] {rel} failed JSON parse: {exc}")

        if rel.startswith(("custom_components/", "frontend_src/")):
            m = BANNED_TERMS_RE.search(txt)
            if m:
                failures.append(f"[TERMINOLOGY] {rel} contains banned term {m.group(0)!r}")

    # 2. Translations parity & placeholder hygiene
    strings_path = LATTER_DIR / "strings.json"
    en_path = LATTER_DIR / "translations" / "en.json"
    if not strings_path.is_file() or not en_path.is_file():
        failures.append("[TRANSLATIONS] strings.json or translations/en.json missing")
    else:
        s_bytes = strings_path.read_bytes()
        e_bytes = en_path.read_bytes()
        if s_bytes != e_bytes:
            failures.append("[TRANSLATIONS] strings.json and translations/en.json must be byte-identical")
        s_txt = s_bytes.decode("utf-8", errors="replace")
        m_sq = SINGLE_QUOTED_PLACEHOLDER_RE.search(s_txt)
        if m_sq:
            failures.append(f"[TRANSLATIONS] strings.json contains single-quoted placeholder {m_sq.group(0)}")

    # 3. Version lockstep (manifest.json == const.py, and == sibling esphome-latter-core if present)
    manifest = json.loads((LATTER_DIR / "manifest.json").read_text(encoding="utf-8"))
    ha_ver = manifest.get("version", "")
    const_candidates = [LATTER_DIR / "const.py", LATTER_DIR / "core" / "const.py"]
    const_ver = None
    for cp in const_candidates:
        if cp.is_file():
            m = re.search(r'INTEGRATION_VERSION(?:\s*:\s*[^=]+)?\s*=\s*"([^"]+)"', cp.read_text(encoding="utf-8"))
            if m:
                const_ver = m.group(1)
                break
    if const_ver != ha_ver:
        failures.append(f"[VERSION LOCKSTEP] manifest.json ({ha_ver}) != INTEGRATION_VERSION ({const_ver})")

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

    # 4. Dev gate check on validate.yml
    val_yml = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
    if "\n  promote:" not in val_yml or "refs/heads/main" not in val_yml:
        failures.append("[DEV GATE] .github/workflows/validate.yml must fast-forward main from promote job")

    # 5. 6-package modular backend & Python security/performance invariants
    expected_subpackages = {"core", "presence", "areas", "media", "http", "studio"}
    allowed_top_py = {
        "__init__.py",
        "backup.py",
        "binary_sensor.py",
        "config_flow.py",
        "const.py",
        "device_tracker.py",
        "diagnostics.py",
        "repairs.py",
        "sensor.py",
        "services.py",
    }
    for subpkg in sorted(expected_subpackages):
        if not (LATTER_DIR / subpkg / "__init__.py").is_file():
            failures.append(f"[6-PACKAGE] custom_components/latter/{subpkg}/__init__.py is missing")
    for top_py in sorted(LATTER_DIR.glob("*.py")):
        if top_py.name not in allowed_top_py:
            failures.append(
                f"[6-PACKAGE] Unexpected flat module custom_components/latter/{top_py.name} (move into domain package)"
            )

    coord_path = LATTER_DIR / "core" / "device_coordinator.py"
    if not coord_path.is_file():
        failures.append("[PUSH COORDINATOR] custom_components/latter/core/device_coordinator.py is missing")
    else:
        coord_lines = len(coord_path.read_text(encoding="utf-8").splitlines())
        if coord_lines >= 450:
            failures.append(
                f"[PUSH COORDINATOR] core/device_coordinator.py has {coord_lines} lines (must be < 450)"
            )

    url_signer_path = LATTER_DIR / "http" / "url_signer.py"
    if url_signer_path.is_file():
        signer_txt = url_signer_path.read_text(encoding="utf-8")
        if re.search(r"\bsocket\.socket\s*\(", signer_txt):
            failures.append("[EVENT LOOP] http/url_signer.py opens a raw socket; use async HA network helpers")

    py_files = [p for p in iter_repo_files(LATTER_DIR) if p.suffix == ".py"]
    http_verified = False
    for pf in py_files:
        ptxt = pf.read_text(encoding="utf-8")
        rel = pf.relative_to(ROOT).as_posix()
        if re.search(r"\bself\.device_entry\s*=", ptxt):
            failures.append(f"[DEVICE REGISTRY] {rel} assigns self.device_entry directly (forbidden)")
        if re.search(r"\.states\.async_all\s*\(", ptxt):
            failures.append(f"[AREA STATE INDEX] {rel} calls hass.states.async_all() (use AreaStateIndex)")
        if re.search(r"\bDataUpdateCoordinator\b", ptxt):
            failures.append(f"[PUSH COORDINATOR] {rel} references DataUpdateCoordinator (use pure push coordinator)")
        if "verify_resource(" in ptxt or "resource_signing.verify(" in ptxt:
            http_verified = True
    if not http_verified:
        failures.append("[SECURITY] HTTP resource signature verification not found in custom_components/latter")

    # 6. Studio invariants (no fetch(), no hassTokens, CSS tokens in :host only, inline style hygiene)
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
            failures.append(f"[STUDIO WS ONLY] {rel} calls fetch(); Studio must use websocket_api only")
        if "hassTokens" in stxt or "hass-subpage" in stxt:
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
