#!/usr/bin/env python3
"""Cross-platform DAG, security, Studio, and HA Platinum compliance verifier for ha-latter.

Enforces Tarjan SCC zero-cycle DAG layering (`L0a`-`L4`), `<= 1,200` LOC hard ratchet
(`<= 1,000` LOC soft warning), AST bound-identity & service/RPC split invariants,
`pyproject.toml` / `manifest.json` / `base.yaml` `major.minor.patch` lockstep, and
Latter Studio WebSocket/XHR/CSS token guardrails.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from verify_ha.ast_security import check_ast_and_runtime_invariants
from verify_ha.dag_checks import check_dag_and_layers
from verify_ha.studio_and_meta import (
    check_repo_meta_and_studio,
    check_translations_and_quality,
    iter_repo_files,
    scan_files_and_loc,
)

ROOT = Path(__file__).resolve().parent.parent
LATTER_DIR = ROOT / "custom_components" / "latter"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Static DAG, security, and Studio verifier for ha-latter."
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Skip Node Studio bundle/unit test subprocesses (sets LATTER_VERIFY_FAST=1).",
    )
    args = parser.parse_args(argv)
    if args.fast:
        os.environ["LATTER_VERIFY_FAST"] = "1"

    warnings: list[str] = []
    failures: list[str] = []

    parsed_latter_trees = scan_files_and_loc(ROOT, warnings, failures)
    all_latter_py = [p for p in iter_repo_files(LATTER_DIR) if p.suffix == ".py"]

    check_dag_and_layers(parsed_latter_trees, failures)
    exception_keys, manifest = check_translations_and_quality(ROOT, failures)
    check_ast_and_runtime_invariants(
        ROOT,
        parsed_latter_trees,
        all_latter_py,
        exception_keys,
        failures,
    )
    check_repo_meta_and_studio(ROOT, manifest, failures)

    for warn in warnings:
        print(f"  [warn] {warn}")

    if failures:
        print(f"verify_ha.py FAILED ({len(failures)} issue(s)):")
        for item in failures:
            print(f"  - {item}")
        return 1

    print(f"verify_ha.py PASSED (0 issues, {len(warnings)} LOC warning(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
