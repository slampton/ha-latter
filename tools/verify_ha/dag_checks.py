"""AST import graph extraction, Tarjan SCC cycle detection, and coarse architectural boundary enforcement."""

from __future__ import annotations

import ast
from typing import Final

FORBIDDEN_NON_STDLIB_ROOTS: Final[frozenset[str]] = frozenset(
    {"homeassistant", "aiohttp", "voluptuous", "PIL"}
)

# Boundary (a): Pure stdlib leaves importing zero Home Assistant / aiohttp / voluptuous / PIL.
STDLIB_LEAF_MODULES: Final[frozenset[str]] = frozenset(
    {
        "const.py",
        "config_defaults.py",
        "repairs_keys.py",
        "protocol_specs.py",
        "protocol_codec.py",
        "protocol_policy.py",
        "presence/ble_math.py",
        "studio/settings_cleaners.py",
    }
)

# Boundary (b): Integration root & 8 Home Assistant entity platforms.
ENTITY_PLATFORMS: Final[frozenset[str]] = frozenset(
    {
        "binary_sensor.py",
        "button.py",
        "device_tracker.py",
        "light.py",
        "number.py",
        "select.py",
        "sensor.py",
        "switch.py",
    }
)

INTEGRATION_ROOT_AND_PLATFORMS: Final[frozenset[str]] = ENTITY_PLATFORMS | frozenset(
    {"__init__.py", "config_flow.py"}
)

# Boundary (c): Domain/registry tier never imports orchestration/API tier.
DOMAIN_TIER_EXACT: Final[frozenset[str]] = frozenset(
    {
        "hub_registry.py",
        "identity.py",
        "feeds.py",
        "remotes.py",
        "doorbell.py",
        "backup.py",
        "media_cache.py",
        "http/signing.py",
        "studio/state_gates.py",
    }
)

DOMAIN_TIER_PREFIXES: Final[tuple[str, ...]] = (
    "areas/",
    "presence/",
    "cameras/",
    "wallpapers/",
    "media/",
    "groups/",
)

ORCHESTRATION_TIER_EXACT: Final[frozenset[str]] = frozenset(
    {
        "hub_sync.py",
        "repairs.py",
        "diagnostics.py",
        "studio/panel.py",
        "studio/payload.py",
        "studio/commands.py",
        "studio/system_commands.py",
        "studio/device_commands.py",
    }
)

ORCHESTRATION_TIER_PREFIXES: Final[tuple[str, ...]] = (
    "coordinator/",
    "services/",
)

LATTER_PKG_PREFIX: Final = "custom_components.latter"
LATTER_REL_PREFIX: Final = "custom_components/latter/"


def _is_domain_tier(short_rel: str) -> bool:
    return short_rel in DOMAIN_TIER_EXACT or short_rel.startswith(DOMAIN_TIER_PREFIXES)


def _is_orchestration_tier(short_rel: str) -> bool:
    return (
        short_rel in ORCHESTRATION_TIER_EXACT
        or short_rel.startswith(ORCHESTRATION_TIER_PREFIXES)
        or (short_rel.startswith("http/") and short_rel.endswith("_views.py"))
    )


def _is_type_checking_guard(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute) and isinstance(test.value, ast.Name):
        return test.value.id == "typing" and test.attr == "TYPE_CHECKING"
    return False


def _iter_runtime_nodes(stmts: list[ast.stmt]) -> list[ast.AST]:
    """Collect all AST nodes executed at runtime (skipping `if TYPE_CHECKING:` bodies)."""
    collected: list[ast.AST] = []
    stack: list[ast.AST] = list(reversed(stmts))
    while stack:
        node = stack.pop()
        if isinstance(node, ast.If) and _is_type_checking_guard(node.test):
            stack.extend(reversed(node.orelse))
            continue
        collected.append(node)
        stack.extend(reversed(list(ast.iter_child_nodes(node))))
    return collected


def _package_parts_for_rel(short_rel: str) -> list[str]:
    parts = short_rel.split("/")
    return parts[:-1]


def _resolve_dotted_to_files(
    dotted_parts: list[str],
    known_files: set[str],
    importer_pkg_parts: list[str] | None = None,
) -> set[str]:
    """Map dotted parts inside `custom_components.latter` to target `.py` + parent `__init__.py`."""
    resolved: set[str] = set()
    if not dotted_parts:
        if "__init__.py" in known_files:
            resolved.add("__init__.py")
        return resolved

    # Python runtime rule: importing `pkg.mod` from outside `pkg` implicitly executes `pkg/__init__.py`
    # first. Sibling imports inside an already-executing package do not re-enter their ancestor
    # `__init__.py` (whereas explicit `from . import ...` still resolves `as_pkg` below).
    for depth in range(1, len(dotted_parts)):
        prefix = dotted_parts[:depth]
        if importer_pkg_parts is not None and importer_pkg_parts[:depth] == prefix:
            continue
        pkg_init = "/".join((*prefix, "__init__.py"))
        if pkg_init in known_files:
            resolved.add(pkg_init)

    as_mod = "/".join(dotted_parts) + ".py"
    as_pkg = "/".join((*dotted_parts, "__init__.py"))
    if as_mod in known_files:
        resolved.add(as_mod)
    elif as_pkg in known_files:
        resolved.add(as_pkg)
    return resolved


def _extract_node_targets(
    short_rel: str,
    node: ast.AST,
    known_files: set[str],
) -> set[str]:
    """Extract internal `custom_components/latter` file dependencies from an import AST node."""
    targets: set[str] = set()
    pkg_parts = _package_parts_for_rel(short_rel)

    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name == LATTER_PKG_PREFIX:
                targets.update(_resolve_dotted_to_files([], known_files, pkg_parts))
            elif alias.name.startswith(LATTER_PKG_PREFIX + "."):
                sub = alias.name[len(LATTER_PKG_PREFIX) + 1 :].split(".")
                targets.update(_resolve_dotted_to_files(sub, known_files, pkg_parts))
        return targets

    if not isinstance(node, ast.ImportFrom):
        return targets

    base_parts: list[str] | None = None
    if node.level > 0:
        up = node.level - 1
        if up <= len(pkg_parts):
            prefix = pkg_parts[: len(pkg_parts) - up]
            mod_parts = node.module.split(".") if node.module else []
            base_parts = [*prefix, *mod_parts]
    elif node.module == LATTER_PKG_PREFIX:
        base_parts = []
    elif node.module and node.module.startswith(LATTER_PKG_PREFIX + "."):
        base_parts = node.module[len(LATTER_PKG_PREFIX) + 1 :].split(".")

    if base_parts is None:
        return targets

    targets.update(_resolve_dotted_to_files(base_parts, known_files, pkg_parts))
    for alias in node.names:
        if alias.name == "*":
            continue
        cand = [*base_parts, alias.name]
        targets.update(_resolve_dotted_to_files(cand, known_files, pkg_parts))
    return targets


def build_runtime_import_graph(
    parsed_latter_trees: dict[str, ast.Module],
) -> tuple[dict[str, set[str]], set[str]]:
    """Return `(adjacency_map, self_loops)` keyed by path relative to `custom_components/latter/`."""
    short_trees = {
        rel[len(LATTER_REL_PREFIX) :]: tree
        for rel, tree in parsed_latter_trees.items()
        if rel.startswith(LATTER_REL_PREFIX)
    }
    known_files = set(short_trees.keys())
    adj: dict[str, set[str]] = {k: set() for k in sorted(known_files)}
    self_loops: set[str] = set()

    for short_rel, tree in sorted(short_trees.items()):
        for node in _iter_runtime_nodes(tree.body):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            for dst in _extract_node_targets(short_rel, node, known_files):
                if dst == short_rel:
                    if not short_rel.endswith("__init__.py"):
                        self_loops.add(short_rel)
                    continue
                adj[short_rel].add(dst)
    return adj, self_loops


def tarjan_scc(adj: dict[str, set[str]]) -> list[list[str]]:
    """Compute Strongly Connected Components in topological order using Tarjan's algorithm."""
    index_counter = 0
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    sccs: list[list[str]] = []

    def strongconnect(v: str) -> None:
        nonlocal index_counter
        indices[v] = index_counter
        lowlink[v] = index_counter
        index_counter += 1
        stack.append(v)
        on_stack.add(v)

        for w in sorted(adj.get(v, ())):
            if w not in indices:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], indices[w])

        if lowlink[v] == indices[v]:
            comp: list[str] = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                comp.append(w)
                if w == v:
                    break
            sccs.append(sorted(comp))

    for node in sorted(adj.keys()):
        if node not in indices:
            strongconnect(node)
    return sccs


def _check_stdlib_leaves(
    short_trees: dict[str, ast.Module],
    failures: list[str],
) -> None:
    for short_rel in sorted(STDLIB_LEAF_MODULES):
        tree = short_trees.get(short_rel)
        if tree is None:
            failures.append(
                f"[DAG STDLIB LEAF] Missing expected leaf module {LATTER_REL_PREFIX}{short_rel}"
            )
            continue
        for node in ast.walk(tree):
            roots: list[str] = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".", 1)[0]]
            failures.extend(
                f"[DAG STDLIB LEAF] {LATTER_REL_PREFIX}{short_rel}:{node.lineno} "
                f"imports forbidden package {root_pkg!r}"
                for root_pkg in roots
                if root_pkg in FORBIDDEN_NON_STDLIB_ROOTS
            )


def _check_coarse_boundaries(
    adj: dict[str, set[str]],
    failures: list[str],
) -> None:
    """Enforce integration-root/platform isolation and domain -> orchestration directionality."""
    for src, targets in sorted(adj.items()):
        for dst in sorted(targets):
            if dst in INTEGRATION_ROOT_AND_PLATFORMS:
                if src not in INTEGRATION_ROOT_AND_PLATFORMS:
                    failures.append(
                        f"[DAG BOUNDARY] {src} imports upward from integration root/platform {dst}"
                    )
                elif src in ENTITY_PLATFORMS:
                    failures.append(
                        f"[DAG BOUNDARY] Entity platform {src} must not import {dst}"
                    )
                elif src == "config_flow.py" and dst == "__init__.py":
                    failures.append(
                        "[DAG BOUNDARY] config_flow.py must not import __init__.py"
                    )
            if _is_domain_tier(src) and _is_orchestration_tier(dst):
                failures.append(
                    f"[DAG BOUNDARY] Domain/registry module {src} must not import "
                    f"orchestration/API module {dst}"
                )


def check_dag_and_layers(
    parsed_latter_trees: dict[str, ast.Module],
    failures: list[str],
) -> None:
    """Enforce zero-cycle Tarjan SCC and the 3 coarse architectural boundaries."""
    short_trees = {
        rel[len(LATTER_REL_PREFIX) :]: tree
        for rel, tree in parsed_latter_trees.items()
        if rel.startswith(LATTER_REL_PREFIX)
    }

    _check_stdlib_leaves(short_trees, failures)

    adj, self_loops = build_runtime_import_graph(parsed_latter_trees)
    failures.extend(
        f"[DAG CYCLE] Self-import loop in {LATTER_REL_PREFIX}{loop_mod}"
        for loop_mod in sorted(self_loops)
    )
    failures.extend(
        f"[DAG CYCLE] Circular import SCC ({len(scc)} modules): {' <-> '.join(scc)}"
        for scc in tarjan_scc(adj)
        if len(scc) > 1
    )

    _check_coarse_boundaries(adj, failures)
