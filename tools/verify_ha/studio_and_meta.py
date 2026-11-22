"""Repository metadata, LOC ratchet, full version lockstep, Studio XHR/CSS, and clock checks."""

from __future__ import annotations

import ast
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
from typing import Final

SKIP_DIRS: Final[frozenset[str]] = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".hypothesis",
        ".esphome",
        "node_modules",
        ".coverage",
        "htmlcov",
        ".venv",
        "venv",
    }
)

TEXT_EXTS: Final[frozenset[str]] = frozenset(
    {".py", ".json", ".yaml", ".yml", ".js", ".ts", ".mjs", ".md", ".toml"}
)

LOC_SOFT_LIMIT: Final = 1000
LOC_HARD_LIMIT: Final = 1200
MIN_SDK_REV_FLOOR: Final = 2026112007
MIN_OPEN_ARGS: Final = 2

LOC_EXEMPT_REL_PATHS: Final[frozenset[str]] = frozenset(
    {
        "custom_components/latter/protocol_v3.json",
        "custom_components/latter/studio/locales/en.json",
        "frontend_src/src/protocol-schema.ts",
        "frontend_src/package-lock.json",
    }
)

BANNED_MOCK_SHIMS: Final[tuple[str, ...]] = (
    "tests/harness",
    "tests/harness/fake_ha_core.py",
    "frontend_src/test/dom-shim.ts",
    "frontend_src/test/fake-store.ts",
)

XHR_ALLOWED_REL_PATHS: Final[frozenset[str]] = frozenset(
    {
        "frontend_src/src/api/ws-client.ts",
        "custom_components/latter/frontend/latter-studio.js",
    }
)

BANNED_TERMS_RE: Final = re.compile(r"\b(household|households|fleet|fleets)\b", re.IGNORECASE)
SINGLE_QUOTED_PLACEHOLDER_RE: Final = re.compile(r"'\{[a-zA-Z0-9_]+\}'")
HASSFEST_TRANSLATION_KEY_RE: Final = re.compile(r"^(?!-|_)[a-z0-9-_]+(?<!-|_)$")


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


def _run_trusted_cmd(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603, RUF100
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _check_hassfest_keys(
    obj: object,
    rel: str,
    path_prefix: str,
    failures: list[str],
) -> None:
    if isinstance(obj, dict):
        for key, val in obj.items():
            dotted = f"{path_prefix}.{key}" if path_prefix else str(key)
            if not isinstance(key, str) or not HASSFEST_TRANSLATION_KEY_RE.match(key):
                failures.append(
                    f"[HASSFEST ICONS] {rel} has invalid translation key {key!r} at "
                    f"{dotted!r} (must match ^(?!-|_)[a-z0-9-_]+(?<!-|_)$)"
                )
            _check_hassfest_keys(val, rel, dotted, failures)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _check_hassfest_keys(item, rel, f"{path_prefix}[{idx}]", failures)


def _parse_structured_file(
    rel: str,
    suffix: str,
    txt: str,
    parsed_latter_trees: dict[str, ast.Module],
    failures: list[str],
) -> None:
    if suffix == ".py":
        try:
            tree = ast.parse(txt, filename=rel)
            if rel.startswith("custom_components/latter/"):
                parsed_latter_trees[rel] = tree
        except SyntaxError as exc:
            failures.append(f"[PYTHON AST] {rel}:{exc.lineno}: {exc.msg}")
    elif suffix == ".json":
        try:
            json.loads(txt)
        except ValueError as exc:
            failures.append(f"[JSON] {rel} failed JSON parse: {exc}")
    elif suffix == ".toml":
        try:
            tomllib.loads(txt)
        except tomllib.TOMLDecodeError as exc:
            failures.append(f"[TOML] {rel} failed TOML parse: {exc}")


def scan_files_and_loc(
    root: Path,
    warnings: list[str],
    failures: list[str],
) -> dict[str, ast.Module]:
    """Validate UTF-8, Python/JSON/TOML syntax, terminology, and `<= 1,200` LOC ratchet."""
    parsed_latter_trees: dict[str, ast.Module] = {}
    for path in iter_repo_files(root):
        suffix = path.suffix.lower()
        if suffix not in TEXT_EXTS:
            continue
        raw = path.read_bytes()
        rel = path.relative_to(root).as_posix()
        if raw.startswith(b"\xef\xbb\xbf"):
            failures.append(f"[UTF8 NO-BOM] {rel} starts with a UTF-8 BOM")
        try:
            txt = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            failures.append(f"[UTF8] {rel} is not valid UTF-8: {exc}")
            continue

        if not rel.startswith("custom_components/latter/frontend/") and rel not in LOC_EXEMPT_REL_PATHS:
            loc = len(txt.splitlines())
            if loc > LOC_HARD_LIMIT:
                failures.append(
                    f"[LOC RATCHET] {rel} is {loc} LOC (exceeds hard limit {LOC_HARD_LIMIT} LOC)"
                )
            elif loc > LOC_SOFT_LIMIT:
                warnings.append(
                    f"[LOC WARNING] {rel} is {loc} LOC (exceeds soft target {LOC_SOFT_LIMIT} LOC)"
                )

        _parse_structured_file(rel, suffix, txt, parsed_latter_trees, failures)
        if rel.startswith(("custom_components/", "frontend_src/src/")):
            m_term = BANNED_TERMS_RE.search(txt)
            if m_term:
                failures.append(
                    f"[TERMINOLOGY] {rel} contains banned term {m_term.group(0)!r}"
                )
    return parsed_latter_trees


def _check_icons_json(icons_path: Path, failures: list[str]) -> None:
    if not icons_path.is_file():
        failures.append("[HASSFEST ICONS] custom_components/latter/icons.json is missing")
        return
    try:
        icons_data = json.loads(icons_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        failures.append(f"[HASSFEST ICONS] icons.json failed JSON parse: {exc}")
        return
    if not isinstance(icons_data, dict):
        failures.append("[HASSFEST ICONS] icons.json root must be a JSON object")
    else:
        _check_hassfest_keys(
            icons_data, "custom_components/latter/icons.json", "", failures
        )


def _check_strings_and_icons(latter_dir: Path, failures: list[str]) -> set[str]:
    exception_keys: set[str] = set()
    strings_path = latter_dir / "strings.json"
    en_path = latter_dir / "translations" / "en.json"
    if not strings_path.is_file() or not en_path.is_file():
        failures.append("[HA QUALITY] strings.json or translations/en.json missing")
    else:
        s_bytes = strings_path.read_bytes()
        e_bytes = en_path.read_bytes()
        if s_bytes != e_bytes:
            failures.append(
                "[HA QUALITY] strings.json and translations/en.json must be byte-identical"
            )
        s_txt = s_bytes.decode("utf-8", errors="replace")
        m_sq = SINGLE_QUOTED_PLACEHOLDER_RE.search(s_txt)
        if m_sq:
            failures.append(
                f"[HA QUALITY] strings.json contains single-quoted placeholder {m_sq.group(0)}"
            )
        try:
            strings_data = json.loads(s_txt)
        except ValueError:
            strings_data = None
        if isinstance(strings_data, dict):
            exc_dict = strings_data.get("exceptions")
            if isinstance(exc_dict, dict):
                exception_keys = set(exc_dict.keys())
            _check_hassfest_keys(
                strings_data, "custom_components/latter/strings.json", "", failures
            )

    _check_icons_json(latter_dir / "icons.json", failures)
    return exception_keys


def check_translations_and_quality(
    root: Path,
    failures: list[str],
) -> tuple[set[str], dict[str, object]]:
    """Check `strings.json`/`en.json`, `icons.json`, `manifest.json`, and `quality_scale.yaml`."""
    latter_dir = root / "custom_components" / "latter"
    exception_keys = _check_strings_and_icons(latter_dir, failures)

    manifest_path = latter_dir / "manifest.json"
    manifest: dict[str, object] = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else {}
    )
    if (
        manifest.get("integration_type") != "hub"
        or manifest.get("iot_class") != "local_push"
        or manifest.get("single_config_entry") is not True
        or manifest.get("config_flow") is not True
    ):
        failures.append(
            "[HA QUALITY] manifest.json must declare hub, local_push, "
            "single_config_entry, config_flow"
        )

    qscale_path = latter_dir / "quality_scale.yaml"
    if not qscale_path.is_file():
        failures.append("[HA QUALITY] custom_components/latter/quality_scale.yaml is missing")
    else:
        qtxt = qscale_path.read_text(encoding="utf-8")
        req_rules = (
            "action-setup:",
            "common-modules:",
            "config-flow:",
            "diagnostics:",
            "repair-issues:",
            "runtime-data:",
            "strict-typing: done",
        )
        failures.extend(
            f"[HA QUALITY] quality_scale.yaml missing rule {req_rule!r}"
            for req_rule in req_rules
            if req_rule not in qtxt
        )
    if not (latter_dir / "py.typed").is_file():
        failures.append("[HA QUALITY] custom_components/latter/py.typed marker is missing")
    return exception_keys, manifest


def _check_sibling_core_lockstep(
    sibling_core: Path,
    ha_ver: str,
    ha_sdk_rev: int,
    failures: list[str],
) -> None:
    sibling_inc = sibling_core / "include"
    if sibling_inc.is_dir():
        core_revs = [
            int(m_rev.group(1))
            for hfile in sorted(sibling_inc.rglob("*.h"))
            for m_rev in re.finditer(
                r"(?m)^\s*#\s*define\s+LATTER_SDK_REV\s+(\d+)L?\b",
                hfile.read_text(encoding="utf-8", errors="replace"),
            )
        ]
        if core_revs and set(core_revs) != {ha_sdk_rev}:
            failures.append(
                f"[VERSION LOCKSTEP] MIN_FIRMWARE_SDK_REV ({ha_sdk_rev}) != "
                f"esphome-latter-core LATTER_SDK_REV ({sorted(set(core_revs))})"
            )

    sibling_base = sibling_core / "modules" / "base.yaml"
    if sibling_base.is_file():
        m_core = re.search(
            r'(?m)^\s*version:\s*"([^"]+)"',
            sibling_base.read_text(encoding="utf-8"),
        )
        if m_core and m_core.group(1) != ha_ver:
            failures.append(
                f"[VERSION LOCKSTEP] ha-latter ({ha_ver}) != "
                f"esphome-latter-core base.yaml ({m_core.group(1)})"
            )

    devices_dir = sibling_core / "devices"
    if devices_dir.is_dir():
        for dev_yaml in sorted(devices_dir.glob("*.yaml")):
            m_dev = re.search(
                r'(?m)^\s*version:\s*"([^"$]+)"',
                dev_yaml.read_text(encoding="utf-8"),
            )
            if m_dev and m_dev.group(1) != ha_ver:
                failures.append(
                    f"[VERSION LOCKSTEP] ha-latter ({ha_ver}) != "
                    f"devices/{dev_yaml.name} ({m_dev.group(1)})"
                )


def _check_version_and_sdk_lockstep(
    root: Path,
    manifest: dict[str, object],
    failures: list[str],
) -> None:
    const_path = root / "custom_components" / "latter" / "const.py"
    const_txt = const_path.read_text(encoding="utf-8") if const_path.is_file() else ""
    ha_ver = str(manifest.get("version", ""))

    m_const_ver = re.search(r'INTEGRATION_VERSION(?:\s*:\s*[^=]+)?\s*=\s*"([^"]+)"', const_txt)
    const_ver = m_const_ver.group(1) if m_const_ver else None
    if const_ver != ha_ver:
        failures.append(
            f"[VERSION LOCKSTEP] manifest.json ({ha_ver}) != INTEGRATION_VERSION ({const_ver})"
        )

    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.is_file():
        failures.append("[PYPROJECT PARITY] pyproject.toml is missing")
    else:
        pyproj_raw = pyproject_path.read_text(encoding="utf-8")
        if "[tool.mypy]" not in pyproj_raw or "strict = true" not in pyproj_raw:
            failures.append(
                "[HA QUALITY] pyproject.toml missing [tool.mypy] strict = true"
            )
        pdata = tomllib.loads(pyproj_raw)
        proj = pdata.get("project", {})
        pyproj_ver = str(proj.get("version", ""))
        lic = proj.get("license")
        lic_text = lic.get("text") if isinstance(lic, dict) else str(lic or "")
        if pyproj_ver != ha_ver:
            failures.append(
                f"[PYPROJECT PARITY] pyproject.toml ({pyproj_ver}) != manifest.json ({ha_ver})"
            )
        if lic_text != "Apache-2.0":
            failures.append(
                f"[PYPROJECT PARITY] pyproject.toml license is {lic_text!r} "
                "(expected 'Apache-2.0')"
            )

    m_sdk = re.search(
        r"(?m)^\s*MIN_FIRMWARE_SDK_REV(?:\s*:\s*[^=\r\n]+)?\s*=\s*(\d+)\b", const_txt
    )
    if not m_sdk:
        failures.append("[VERSION LOCKSTEP] const.py missing MIN_FIRMWARE_SDK_REV")
        return

    ha_sdk_rev = int(m_sdk.group(1))
    if ha_sdk_rev < MIN_SDK_REV_FLOOR:
        failures.append(
            f"[VERSION LOCKSTEP] MIN_FIRMWARE_SDK_REV ({ha_sdk_rev}) < "
            f"floor ({MIN_SDK_REV_FLOOR})"
        )
    _check_sibling_core_lockstep(root.parent / "esphome-latter-core", ha_ver, ha_sdk_rev, failures)


def _extract_css_blocks(source: str) -> list[str]:
    return [
        m.group(1)
        for m in re.finditer(r"(?:style\.textContent\s*=\s*`|\bcss`)([\s\S]*?)`", source)
    ]


def _strip_host_block(css_text: str) -> str:
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
        depth = 0
        j = i + m.end() - 1
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


def _check_xhr_in_file(rel: str, stxt: str, failures: list[str]) -> None:
    if rel not in XHR_ALLOWED_REL_PATHS:
        failures.append(
            f"[STUDIO NO REST] {rel} references XMLHttpRequest outside "
            "frontend_src/src/api/ws-client.ts"
        )
        return

    xhr_news = len(re.findall(r"\bnew\s+XMLHttpRequest\s*\(", stxt))
    open_calls = re.findall(r"\b[a-zA-Z_$][\w$]*\.open\s*\(([^)]*)\)", stxt)
    if xhr_news > 1 or not open_calls:
        failures.append(
            f"[STUDIO NO REST] {rel} must have exactly 1 XMLHttpRequest "
            "bound to POST /api/latter/wallpaper/upload"
        )
    for args_raw in open_calls:
        parts = [p.strip() for p in args_raw.split(",")]
        method_ok = bool(parts) and parts[0] in {'"POST"', "'POST'"}
        url_ok = len(parts) >= MIN_OPEN_ARGS and (
            parts[1] in {'"/api/latter/wallpaper/upload"', "'/api/latter/wallpaper/upload'"}
            or (parts[1] == "UPLOAD_PATH" and '"/api/latter/wallpaper/upload"' in stxt)
        )
        if not (method_ok and url_ok):
            failures.append(
                f"[STUDIO NO REST] {rel} opens XHR ({args_raw}) outside "
                "POST /api/latter/wallpaper/upload"
            )


def _check_studio_xhr_and_css(
    root: Path,
    studio_sources: list[Path],
    failures: list[str],
) -> None:
    for sf in studio_sources:
        stxt = sf.read_text(encoding="utf-8")
        rel = sf.relative_to(root).as_posix()
        if re.search(r"\bfetch\s*\(|\bsendBeacon\s*\(|\bnew\s+EventSource\s*\(", stxt):
            failures.append(
                f"[STUDIO NO REST] {rel} uses forbidden fetch/sendBeacon/EventSource; "
                "Studio must use websocket_api (hass.callWS)"
            )
        if "XMLHttpRequest" in stxt:
            _check_xhr_in_file(rel, stxt, failures)
        if "hassTokens" in stxt or "hass-subpage" in stxt or "shadowRoot.querySelector" in stxt:
            failures.append(
                f"[STUDIO INTERNALS] {rel} accesses forbidden HA frontend internals"
            )
        failures.extend(
            f"[STUDIO INLINE STYLES] {rel} uses non-token inline style: "
            f"{bad_style.group(0)[:60]}"
            for bad_style in re.finditer(r'\bstyle="(?!\s*--|\s*\$\{)[^"]+"', stxt)
        )
        for css_block in _extract_css_blocks(stxt):
            css_no_comments = re.sub(r"/\*[\s\S]*?\*/", "", css_block)
            body_css = _strip_host_block(css_no_comments)
            if re.search(r"\bfont-size\s*:\s*(?!var\(|inherit\b|100%\b)", body_css):
                failures.append(f"[STUDIO TOKENS] {rel} uses literal font-size outside :host")
            if re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(", body_css):
                failures.append(f"[STUDIO TOKENS] {rel} uses color literal outside :host")


def _check_studio_bundles_and_gzip(
    root: Path,
    studio_js: Path,
    studio_mdi_js: Path,
    studio_en_json: Path,
    failures: list[str],
) -> None:
    if not studio_js.is_file():
        failures.append("[STUDIO] custom_components/latter/frontend/latter-studio.js missing")
    if not studio_mdi_js.is_file() or studio_mdi_js.stat().st_size == 0:
        failures.append(
            "[STUDIO] custom_components/latter/frontend/latter-studio-mdi.js missing or empty"
        )
    if not studio_en_json.is_file():
        failures.append("[STUDIO I18N] studio/locales/en.json is missing")
    else:
        en_locale = json.loads(studio_en_json.read_text(encoding="utf-8"))
        if not isinstance(en_locale, dict) or not en_locale:
            failures.append("[STUDIO I18N] studio/locales/en.json must be a non-empty object")

    for js_bundle in (studio_js, studio_mdi_js):
        if not js_bundle.is_file():
            continue
        gz_sibling = js_bundle.with_name(f"{js_bundle.name}.gz")
        rel_gz = gz_sibling.relative_to(root).as_posix()
        if not gz_sibling.is_file():
            failures.append(f"[STUDIO GZIP] {rel_gz} is missing")
            continue
        try:
            decompressed = gzip.decompress(gz_sibling.read_bytes())
        except OSError as exc:
            failures.append(f"[STUDIO GZIP] {rel_gz} invalid gzip archive: {exc}")
        else:
            if decompressed != js_bundle.read_bytes():
                failures.append(
                    f"[STUDIO GZIP] {rel_gz} does not match {js_bundle.name} byte-for-byte"
                )


def _check_studio_artifacts(root: Path, failures: list[str]) -> None:
    latter_dir = root / "custom_components" / "latter"
    studio_dir = latter_dir / "studio"
    studio_doc = root / "docs" / "studio-design.md"
    studio_js = latter_dir / "frontend" / "latter-studio.js"
    studio_mdi_js = latter_dir / "frontend" / "latter-studio-mdi.js"
    studio_en_json = studio_dir / "locales" / "en.json"

    if not studio_doc.is_file():
        failures.append("[STUDIO DESIGN DOC] docs/studio-design.md is missing")
    else:
        doc_txt = studio_doc.read_text(encoding="utf-8")
        markers = ("[STUDIO TOKENS]", "[STUDIO INLINE STYLES]", "## Decision log", "D-001")
        failures.extend(
            f"[STUDIO DESIGN DOC] docs/studio-design.md missing {marker!r}"
            for marker in markers
            if marker not in doc_txt
        )

    py_files = sorted(studio_dir.glob("*.py")) if studio_dir.is_dir() else []
    failures.extend(
        f"[STUDIO NO REST] studio/{s_py.name} defines HomeAssistantView "
        "(Studio uses websocket_api only)"
        for s_py in py_files
        if "HomeAssistantView" in s_py.read_text(encoding="utf-8")
    )

    panel_py = studio_dir / "panel.py"
    if not panel_py.is_file():
        failures.append("[STUDIO] custom_components/latter/studio/panel.py is missing")
    else:
        p_txt = panel_py.read_text(encoding="utf-8")
        if "/latter_static" in p_txt or re.search(
            r"StaticPathConfig\(\s*STATIC_URL_PREFIX\s*,", p_txt
        ):
            failures.append(
                "[STUDIO NO REST] studio/panel.py must mount only versioned "
                "static prefix (/latter_ui_<ver>)"
            )

    _check_studio_bundles_and_gzip(root, studio_js, studio_mdi_js, studio_en_json, failures)

    studio_sources = [p for p in (studio_js, studio_mdi_js) if p.is_file()]
    frontend_src_dir = root / "frontend_src" / "src"
    if frontend_src_dir.is_dir():
        studio_sources.extend(
            p for p in iter_repo_files(frontend_src_dir) if p.suffix in {".ts", ".js"}
        )
    _check_studio_xhr_and_css(root, studio_sources, failures)


def _check_tests_and_frontend_build(root: Path, failures: list[str]) -> None:
    failures.extend(
        f"[ZERO MOCK SHIMS] Retired mock shim must never return: {shim}"
        for shim in BANNED_MOCK_SHIMS
        if (root / shim).exists()
    )
    tests_dir = root / "tests"
    if tests_dir.is_dir():
        for tf in sorted(tests_dir.rglob("*.py")):
            if any(part in SKIP_DIRS for part in tf.parts):
                continue
            ttxt = tf.read_text(encoding="utf-8")
            trel = tf.relative_to(root).as_posix()
            if re.search(r"monkeypatch\.setattr\(\s*['\"][^'\"]*\.time\.monotonic['\"]", ttxt):
                failures.append(
                    f"[TEST CLOCK SAFETY] {trel} patches module.time.monotonic; "
                    "inject a per-instance clock instead"
                )
            if re.search(
                r"anchor\s*=\s*\d+(?:\.\d+)?\s*\n\s*monkeypatch\.setattr\(\s*time\s*,\s*['\"]monotonic['\"]",
                ttxt,
            ):
                failures.append(
                    f"[TEST CLOCK SAFETY] {trel} rewinds time.monotonic to a fixed literal; "
                    "anchor from real time.monotonic()"
                )

    frontend_src_dir = root / "frontend_src"
    if os.environ.get("LATTER_VERIFY_FAST") == "1" or not (frontend_src_dir / "build.mjs").is_file():
        return

    node_bin = shutil.which("node")
    npm_bin = shutil.which("npm")
    if not node_bin:
        failures.append("[STUDIO BUILD] 'node' binary not found in PATH")
    else:
        build_proc = _run_trusted_cmd(
            [node_bin, "--no-warnings", "frontend_src/build.mjs", "--check", "--typecheck"],
            root,
        )
        if build_proc.returncode != 0:
            detail = "\n    ".join(
                p.strip() for p in (build_proc.stdout, build_proc.stderr) if p and p.strip()
            )
            failures.append(f"[STUDIO BUILD] frontend_src/build.mjs --check failed:\n    {detail}")

    if not npm_bin:
        failures.append("[STUDIO TESTS] 'npm' binary not found in PATH")
    else:
        test_proc = _run_trusted_cmd([npm_bin, "--prefix", "frontend_src", "test"], root)
        if test_proc.returncode != 0:
            detail = "\n    ".join(
                p.strip() for p in (test_proc.stdout, test_proc.stderr) if p and p.strip()
            )
            failures.append(
                f"[STUDIO TESTS] npm --prefix frontend_src test failed:\n    {detail}"
            )


def check_repo_meta_and_studio(
    root: Path,
    manifest: dict[str, object],
    failures: list[str],
) -> None:
    """Run lockstep, workflow gate, Studio, test-clock, and frontend build checks."""
    _check_version_and_sdk_lockstep(root, manifest, failures)
    val_yml_path = root / ".github" / "workflows" / "validate.yml"
    val_yml = val_yml_path.read_text(encoding="utf-8") if val_yml_path.is_file() else ""
    if "\n  promote:" not in val_yml or "refs/heads/main" not in val_yml:
        failures.append(
            "[DEV GATE] .github/workflows/validate.yml must fast-forward main from promote job"
        )
    _check_studio_artifacts(root, failures)
    _check_tests_and_frontend_build(root, failures)
