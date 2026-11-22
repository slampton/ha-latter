"""AST import graph extraction, Tarjan SCC cycle detection, and L0a-L4 layer enforcement."""

from __future__ import annotations

import ast
from typing import Final

LAYER_ORDER: Final[dict[str, int]] = {
    "L0a": 0,
    "L0b": 1,
    "L1a": 2,
    "L1b": 3,
    "L2a": 4,
    "L2b": 5,
    "L3": 6,
    "L4": 7,
}

MULTILAYER_SUBPACKAGES: Final[frozenset[str]] = frozenset(
    {
        "areas",
        "cameras",
        "groups",
        "http",
        "media",
        "presence",
        "services",
        "studio",
        "wallpapers",
    }
)

FORBIDDEN_NON_STDLIB_ROOTS: Final[frozenset[str]] = frozenset(
    {"homeassistant", "aiohttp", "voluptuous", "PIL"}
)

L4_PLATFORMS: Final[frozenset[str]] = frozenset(
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

# Canonical L0a-L4 classification for every .py module under custom_components/latter/
LAYER_MAP: Final[dict[str, str]] = {
    # L0a: Pure stdlib leaves & docstring-only multi-layer subpackage __init__.py markers
    "const.py": "L0a",
    "config_defaults.py": "L0a",
    "repairs_keys.py": "L0a",
    "protocol_specs.py": "L0a",
    "areas/__init__.py": "L0a",
    "cameras/__init__.py": "L0a",
    "groups/__init__.py": "L0a",
    "http/__init__.py": "L0a",
    "media/__init__.py": "L0a",
    "presence/__init__.py": "L0a",
    "services/__init__.py": "L0a",
    "studio/__init__.py": "L0a",
    "wallpapers/__init__.py": "L0a",
    # L0b: Pure stdlib codecs, math, and cleaners importing only L0a
    "protocol_codec.py": "L0b",
    "protocol_policy.py": "L0b",
    "presence/ble_math.py": "L0b",
    "studio/settings_cleaners.py": "L0b",
    # L1a: Foundational caches, hub registry, HMAC signing, and Studio state gates
    "media_cache.py": "L1a",
    "hub_registry.py": "L1a",
    "http/signing.py": "L1a",
    "studio/state_gates.py": "L1a",
    # L1b: Device identity, feeds, remotes, area/BLE registries, MA linking, lyrics, wallpapers
    "identity.py": "L1b",
    "feeds.py": "L1b",
    "remotes.py": "L1b",
    "doorbell_targets.py": "L1b",
    "areas/registry.py": "L1b",
    "areas/state_index.py": "L1b",
    "presence/ble_registry.py": "L1b",
    "presence/area_fusion.py": "L1b",
    "presence/ble_discovery.py": "L1b",
    "media/linking.py": "L1b",
    "media/lyrics.py": "L1b",
    "wallpapers/models.py": "L1b",
    "wallpapers/store.py": "L1b",
    "wallpapers/media_import.py": "L1b",
    "wallpapers/pools.py": "L1b",
    # L2a: Doorbell, camera stream hub, device groups, media browse/playback, BLE trackers
    "doorbell.py": "L2a",
    "cameras/transcode.py": "L2a",
    "cameras/stream_hub.py": "L2a",
    "cameras/capabilities.py": "L2a",
    "groups/esphome_inspector.py": "L2a",
    "groups/device_groups.py": "L2a",
    "groups/device_reset.py": "L2a",
    "media/browse.py": "L2a",
    "media/volume.py": "L2a",
    "media/announce.py": "L2a",
    "media/tts_queue.py": "L2a",
    "media/playback.py": "L2a",
    "media/state_payload.py": "L2a",
    "presence/ble_tracker_matcher.py": "L2a",
    "presence/ble_tracker_calibration.py": "L2a",
    # L2b: Area curation/actions/sync, BLE spatial fabric, and backup bundles
    "areas/sync.py": "L2b",
    "areas/telemetry.py": "L2b",
    "areas/curation.py": "L2b",
    "areas/actions.py": "L2b",
    "areas/catalogs.py": "L2b",
    "presence/ble_fabric.py": "L2b",
    "backup.py": "L2b",
    # L3: Coordinator, hub sync, RPC/public services, HTTP views, repairs, diagnostics, Studio WS
    "coordinator/__init__.py": "L3",
    "coordinator/runtime_store.py": "L3",
    "coordinator/device_traits.py": "L3",
    "coordinator/wallpaper_scheduler.py": "L3",
    "coordinator/area_follow_controller.py": "L3",
    "coordinator/ha_registry_sync.py": "L3",
    "coordinator/device_lifecycle.py": "L3",
    "coordinator/v3_transport.py": "L3",
    "coordinator/core.py": "L3",
    "hub_sync.py": "L3",
    "services/rpc_security.py": "L3",
    "services/rpc_slots.py": "L3",
    "services/rpc_receiver.py": "L3",
    "services/rpc_dispatcher.py": "L3",
    "services/public_actions.py": "L3",
    "http/proxy_views.py": "L3",
    "http/wallpaper_views.py": "L3",
    "http/camera_views.py": "L3",
    "http/views_register.py": "L3",
    "studio/panel.py": "L3",
    "studio/payload_shared.py": "L3",
    "studio/payload_sections.py": "L3",
    "studio/payload.py": "L3",
    "studio/cmd_presence_devices.py": "L3",
    "studio/cmd_photos_media.py": "L3",
    "studio/cmd_groups_security.py": "L3",
    "studio/commands.py": "L3",
    "repairs.py": "L3",
    "diagnostics.py": "L3",
    # L4: Integration setup, ConfigFlow/SubentryFlows, and Home Assistant entity platforms
    "__init__.py": "L4",
    "config_flow.py": "L4",
    "binary_sensor.py": "L4",
    "button.py": "L4",
    "device_tracker.py": "L4",
    "light.py": "L4",
    "number.py": "L4",
    "select.py": "L4",
    "sensor.py": "L4",
    "switch.py": "L4",
}

LATTER_PKG_PREFIX: Final = "custom_components.latter"
LATTER_REL_PREFIX: Final = "custom_components/latter/"


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
    if parts[-1] == "__init__.py":
        return parts[:-1]
    return parts[:-1]


def _resolve_dotted_to_files(
    dotted_parts: list[str],
    known_files: set[str],
) -> set[str]:
    """Map dotted parts inside `custom_components.latter` to target `.py` + parent `__init__.py`."""
    resolved: set[str] = set()
    if not dotted_parts:
        if "__init__.py" in known_files:
            resolved.add("__init__.py")
        return resolved

    # Python runtime rule: importing `pkg.mod` implicitly executes `pkg/__init__.py` first.
    for depth in range(1, len(dotted_parts)):
        pkg_init = "/".join((*dotted_parts[:depth], "__init__.py"))
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
                targets.update(_resolve_dotted_to_files([], known_files))
            elif alias.name.startswith(LATTER_PKG_PREFIX + "."):
                sub = alias.name[len(LATTER_PKG_PREFIX) + 1 :].split(".")
                targets.update(_resolve_dotted_to_files(sub, known_files))
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

    targets.update(_resolve_dotted_to_files(base_parts, known_files))
    for alias in node.names:
        if alias.name == "*":
            continue
        cand = [*base_parts, alias.name]
        targets.update(_resolve_dotted_to_files(cand, known_files))
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
                    # Importing `from .foo import bar` inside `pkg/__init__.py` triggers implicit
                    # parent lookup of `pkg/__init__.py`; only mark direct self-import if module
                    # is not a package `__init__.py` importing a child submodule.
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


def _check_multilayer_inits(
    short_trees: dict[str, ast.Module],
    failures: list[str],
) -> None:
    for pkg in sorted(MULTILAYER_SUBPACKAGES):
        init_rel = f"{pkg}/__init__.py"
        if LAYER_MAP.get(init_rel) != "L0a":
            failures.append(
                f"[DAG SUBPACKAGE INIT] {init_rel} must be classified at L0a in LAYER_MAP"
            )
        tree = short_trees.get(init_rel)
        if tree is None:
            failures.append(
                f"[DAG SUBPACKAGE INIT] Missing required multi-layer {LATTER_REL_PREFIX}{init_rel}"
            )
            continue
        failures.extend(
            f"[DAG SUBPACKAGE INIT] {LATTER_REL_PREFIX}{init_rel}:{node.lineno} "
            "must remain docstring-only with zero runtime/package imports"
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            or (isinstance(node, ast.ImportFrom) and node.module != "__future__")
        )


def _check_stdlib_leaves(
    short_trees: dict[str, ast.Module],
    failures: list[str],
) -> None:
    for short_rel, tree in sorted(short_trees.items()):
        layer = LAYER_MAP.get(short_rel)
        if layer not in {"L0a", "L0b"}:
            continue
        for node in ast.walk(tree):
            roots: list[str] = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".", 1)[0]]
            failures.extend(
                f"[DAG STDLIB LEAF] {LATTER_REL_PREFIX}{short_rel}:{node.lineno} "
                f"({layer}) imports forbidden package {root_pkg!r}"
                for root_pkg in roots
                if root_pkg in FORBIDDEN_NON_STDLIB_ROOTS
            )


def _top_domain_group(short_rel: str) -> str:
    return short_rel.split("/", 1)[0]


def _validate_same_layer_edge(
    src: str,
    dst: str,
    layer: str,
    failures: list[str],
) -> None:
    """Validate horizontal edges within the same layer (after Tarjan proves acyclicity)."""
    if layer == "L0b" and not (
        src.startswith("protocol_") and dst.startswith("protocol_")
    ):
        failures.append(
            f"[DAG LAYER VIOLATION] {src} (L0b) imports sibling L0b module {dst} "
            "(L0b leaves must import only L0a)"
        )
    elif layer == "L2b" and _top_domain_group(src) != _top_domain_group(dst):
        failures.append(
            f"[DAG LAYER VIOLATION] {src} (L2b) imports cross-domain L2b module {dst} "
            "(use L1b registries instead)"
        )
    elif layer == "L4":
        if src in L4_PLATFORMS:
            failures.append(
                f"[DAG LAYER VIOLATION] L4 platform {src} imports L4 module {dst} "
                "(platforms must import strictly < L4)"
            )
        elif src == "config_flow.py" and dst == "__init__.py":
            failures.append(
                "[DAG LAYER VIOLATION] config_flow.py (L4) must not import __init__.py (L4)"
            )


def check_dag_and_layers(
    parsed_latter_trees: dict[str, ast.Module],
    failures: list[str],
) -> None:
    """Enforce zero-cycle Tarjan SCC and strict downward L0a-L4 layer ordering."""
    short_trees = {
        rel[len(LATTER_REL_PREFIX) :]: tree
        for rel, tree in parsed_latter_trees.items()
        if rel.startswith(LATTER_REL_PREFIX)
    }

    unclassified = sorted(set(short_trees.keys()) - set(LAYER_MAP.keys()))
    failures.extend(
        f"[DAG UNCLASSIFIED] {LATTER_REL_PREFIX}{mod} is not classified in LAYER_MAP "
        "(rogue module or un-deleted monolith)"
        for mod in unclassified
    )

    _check_multilayer_inits(short_trees, failures)
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

    for src, targets in sorted(adj.items()):
        src_layer = LAYER_MAP.get(src)
        if src_layer is None:
            continue
        src_rank = LAYER_ORDER[src_layer]
        for dst in sorted(targets):
            dst_layer = LAYER_MAP.get(dst)
            if dst_layer is None:
                continue
            dst_rank = LAYER_ORDER[dst_layer]
            if dst_rank > src_rank:
                failures.append(
                    f"[DAG LAYER VIOLATION] {src} ({src_layer}) imports upward from "
                    f"{dst} ({dst_layer})"
                )
            elif dst_rank == src_rank:
                _validate_same_layer_edge(src, dst, src_layer, failures)
