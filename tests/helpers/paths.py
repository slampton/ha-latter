"""Pure-stdlib repository path and Node ESM test helpers."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LATTER_DIR = REPO_ROOT / "custom_components" / "latter"
FRONTEND_DIR = REPO_ROOT / "frontend_src"
FRONTEND_SRC = FRONTEND_DIR / "src"
NODE_BIN = shutil.which("node")


def read_py_tree(*rel_paths: str) -> str:
    """Concatenate UTF-8 Python source across files or subdirectories under `custom_components/latter`."""
    chunks: list[str] = []
    for rel in rel_paths:
        target = LATTER_DIR / rel
        if target.is_dir():
            chunks.extend(
                path.read_text(encoding="utf-8") for path in sorted(target.rglob("*.py"))
            )
        elif target.is_file():
            chunks.append(target.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def read_ts_tree(*rel_paths: str) -> str:
    """Concatenate UTF-8 TypeScript source across files or subdirectories under `frontend_src/src`."""
    chunks: list[str] = []
    for rel in rel_paths:
        target = FRONTEND_SRC / rel
        if target.is_dir():
            chunks.extend(
                path.read_text(encoding="utf-8") for path in sorted(target.rglob("*.ts"))
            )
        elif target.is_file():
            chunks.append(target.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def run_studio_node_esm(module_js: str) -> Any:
    """Execute a pure ESM snippet against TypeScript Studio modules via `node-ts-loader.mjs`."""
    if not NODE_BIN:
        raise RuntimeError("node is not installed")
    out = subprocess.run(  # noqa: S603
        [
            NODE_BIN,
            "--no-warnings",
            "--import",
            "./src/lib/node-ts-loader.mjs",
            "--input-type=module",
            "-",
        ],
        cwd=FRONTEND_DIR,
        input=module_js,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if out.returncode != 0:
        raise RuntimeError(
            f"Node ESM execution failed ({out.returncode}):\n{out.stderr}\n{out.stdout}"
        )
    return json.loads(out.stdout)
