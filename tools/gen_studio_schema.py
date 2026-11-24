#!/usr/bin/env python3
"""Generate frontend_src/src/protocol-schema.ts from protocol_v3.json + studio_contract.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Final

_REQUIRED_STUDIO_TOP_KEYS: Final[frozenset[str]] = frozenset(
    {
        "studio_contract",
        "ha_services",
        "catalog_ui",
        "world_clock_zones",
        "world_clock_aliases",
        "device_pref_ui",
    }
)
_REQUIRED_PREF_UI_KEYS: Final[frozenset[str]] = frozenset(
    {"label", "section", "group_tier", "unit"}
)
_VALID_GROUP_TIERS: Final[frozenset[str | None]] = frozenset(
    {"behavior", "display", "interface", None}
)
_CSV_DEFAULT_KEYS: Final[frozenset[str]] = frozenset(
    {
        "dock_routes",
        "activity_sources",
        "area_categories",
        "home_categories",
        "tools_items",
        "games_items",
    }
)


def _ts_json(val: Any) -> str:
    return json.dumps(val, ensure_ascii=False)


def _validate_pref_ui_coverage(
    device_pref_specs: list[dict[str, Any]],
    device_pref_ui: dict[str, Any],
) -> None:
    if not isinstance(device_pref_specs, list) or not device_pref_specs:
        raise ValueError("protocol_v3.json['device_pref_specs'] must be a non-empty list")
    if not isinstance(device_pref_ui, dict) or not device_pref_ui:
        raise ValueError("studio_contract.json['device_pref_ui'] must be a non-empty object")

    spec_keys: list[str] = []
    seen: set[str] = set()
    for spec in device_pref_specs:
        key = str(spec.get("key") or "")
        if not key:
            raise ValueError("protocol_v3.json['device_pref_specs'] contains an entry with empty key")
        if key in seen:
            raise ValueError(f"Duplicate key {key!r} in protocol_v3.json['device_pref_specs']")
        seen.add(key)
        spec_keys.append(key)

    ui_key_set = set(device_pref_ui.keys())
    missing_ui = sorted(seen - ui_key_set)
    extra_ui = sorted(ui_key_set - seen)
    if missing_ui or extra_ui:
        raise ValueError(
            "1:1 key coverage mismatch between protocol_v3.json['device_pref_specs'] and "
            f"studio_contract.json['device_pref_ui'] (missing={missing_ui}, extra={extra_ui})"
        )

    for key in spec_keys:
        ui = device_pref_ui[key]
        if not isinstance(ui, dict):
            raise ValueError(f"studio_contract.json['device_pref_ui'][{key!r}] must be an object")
        ui_fields = set(ui.keys())
        if ui_fields != _REQUIRED_PREF_UI_KEYS:
            missing_f = sorted(_REQUIRED_PREF_UI_KEYS - ui_fields)
            extra_f = sorted(ui_fields - _REQUIRED_PREF_UI_KEYS)
            raise ValueError(
                f"studio_contract.json['device_pref_ui'][{key!r}] field mismatch "
                f"(missing={missing_f}, extra={extra_f})"
            )
        if not isinstance(ui["label"], str) or not ui["label"].strip():
            raise ValueError(f"device_pref_ui[{key!r}].label must be a non-empty string")
        if not isinstance(ui["section"], str) or not ui["section"].strip():
            raise ValueError(f"device_pref_ui[{key!r}].section must be a non-empty string")
        if ui["group_tier"] not in _VALID_GROUP_TIERS:
            raise ValueError(
                f"device_pref_ui[{key!r}].group_tier {ui['group_tier']!r} must be one of "
                "('behavior', 'display', 'interface', None)"
            )
        if not isinstance(ui["unit"], str):
            raise ValueError(f"device_pref_ui[{key!r}].unit must be a string")


def _validate_catalog_ui_coverage(
    protocol_catalogs: dict[str, Any],
    catalog_ui: dict[str, Any],
) -> None:
    if not isinstance(protocol_catalogs, dict) or "shortcut_routes" not in protocol_catalogs:
        raise ValueError("protocol_v3.json['catalogs'] must be an object containing 'shortcut_routes'")
    if not isinstance(catalog_ui, dict):
        raise ValueError("studio_contract.json['catalog_ui'] must be an object")

    route_groups = catalog_ui.get("shortcut_route_groups")
    if not isinstance(route_groups, dict):
        raise ValueError("studio_contract.json['catalog_ui']['shortcut_route_groups'] must be an object")
    route_tokens = {str(r["token"]) for r in protocol_catalogs["shortcut_routes"]}
    if set(route_groups.keys()) != route_tokens:
        missing = sorted(route_tokens - set(route_groups.keys()))
        extra = sorted(set(route_groups.keys()) - route_tokens)
        raise ValueError(
            "1:1 key mismatch between protocol_v3.json['catalogs']['shortcut_routes'] and "
            f"studio_contract.json['catalog_ui']['shortcut_route_groups'] (missing={missing}, extra={extra})"
        )
    for tok, grp in route_groups.items():
        if not isinstance(grp, str) or not grp.strip():
            raise ValueError(f"catalog_ui.shortcut_route_groups[{tok!r}] must be a non-empty string")

    catalog_labels = catalog_ui.get("catalog_labels")
    if not isinstance(catalog_labels, dict):
        raise ValueError("studio_contract.json['catalog_ui']['catalog_labels'] must be an object")
    non_fw_cats = set(protocol_catalogs.keys()) - {"shortcut_routes"}
    if set(catalog_labels.keys()) != non_fw_cats:
        missing_c = sorted(non_fw_cats - set(catalog_labels.keys()))
        extra_c = sorted(set(catalog_labels.keys()) - non_fw_cats)
        raise ValueError(
            "1:1 catalog mismatch between protocol_v3.json['catalogs'] and "
            f"studio_contract.json['catalog_ui']['catalog_labels'] (missing={missing_c}, extra={extra_c})"
        )
    for cat_name in sorted(non_fw_cats):
        labels_map = catalog_labels[cat_name]
        if not isinstance(labels_map, dict):
            raise ValueError(f"catalog_ui.catalog_labels[{cat_name!r}] must be an object")
        cat_tokens = {str(item["token"]) for item in protocol_catalogs[cat_name]}
        if set(labels_map.keys()) != cat_tokens:
            missing_t = sorted(cat_tokens - set(labels_map.keys()))
            extra_t = sorted(set(labels_map.keys()) - cat_tokens)
            raise ValueError(
                f"1:1 token mismatch for catalog {cat_name!r} "
                f"(missing={missing_t}, extra={extra_t})"
            )
        for tok, lbl in labels_map.items():
            if not isinstance(lbl, str) or not lbl.strip():
                raise ValueError(f"catalog_ui.catalog_labels[{cat_name!r}][{tok!r}] must be a non-empty string")


def validate_contracts(
    protocol_schema: dict[str, Any],
    studio_data: dict[str, Any],
) -> None:
    """Validate protocol_v3.json + studio_contract.json ownership split and 1:1 UI coverage."""
    leaked_keys = sorted(_REQUIRED_STUDIO_TOP_KEYS.intersection(protocol_schema.keys()))
    if leaked_keys:
        raise ValueError(
            f"protocol_v3.json must not contain Studio/HA-owned keys {leaked_keys}"
        )

    studio_top = set(studio_data.keys())
    if not _REQUIRED_STUDIO_TOP_KEYS.issubset(studio_top):
        missing = sorted(_REQUIRED_STUDIO_TOP_KEYS - studio_top)
        raise ValueError(f"studio_contract.json missing required top-level keys: {missing}")

    studio_contract = studio_data["studio_contract"]
    if not isinstance(studio_contract, dict) or not isinstance(studio_contract.get("studio_rev"), int):
        raise ValueError("studio_contract.json['studio_contract']['studio_rev'] must be an integer")
    for list_key in ("allowed_device_actions", "system_commands", "device_commands"):
        vals = studio_contract.get(list_key)
        if not isinstance(vals, list) or not vals or not all(isinstance(v, str) and v for v in vals):
            raise ValueError(f"studio_contract.json['studio_contract'][{list_key!r}] must be a non-empty string list")

    if not isinstance(studio_data["ha_services"], dict) or not studio_data["ha_services"]:
        raise ValueError("studio_contract.json['ha_services'] must be a non-empty object")
    if not isinstance(studio_data["world_clock_zones"], list) or not studio_data["world_clock_zones"]:
        raise ValueError("studio_contract.json['world_clock_zones'] must be a non-empty list")
    if not isinstance(studio_data["world_clock_aliases"], list):
        raise ValueError("studio_contract.json['world_clock_aliases'] must be a list")

    _validate_catalog_ui_coverage(
        protocol_schema.get("catalogs", {}),
        studio_data["catalog_ui"],
    )
    _validate_pref_ui_coverage(
        protocol_schema.get("device_pref_specs", []),
        studio_data["device_pref_ui"],
    )


def _append_catalogs_ts(
    lines: list[str],
    catalogs: dict[str, Any],
    catalog_ui: dict[str, Any],
) -> None:
    lines.extend(
        [
            "export interface CatalogItem {",
            "  token: string;",
            "  label: string;",
            "  group?: string;",
            "  dockOnly?: boolean;",
            "  capability?: string;",
            "}",
            "",
        ]
    )
    route_groups: dict[str, str] = catalog_ui["shortcut_route_groups"]
    catalog_labels: dict[str, dict[str, str]] = catalog_ui["catalog_labels"]

    for cat_name, cat_items in catalogs.items():
        const_name = f"{cat_name.upper()}_CATALOG"
        lines.append(f"export const {const_name}: ReadonlyArray<CatalogItem> = [")
        for item in cat_items:
            tok = str(item["token"])
            label = (
                str(item["label"])
                if cat_name == "shortcut_routes"
                else str(catalog_labels[cat_name][tok])
            )
            group = route_groups[tok] if cat_name == "shortcut_routes" else ""
            extras: list[str] = []
            if group:
                extras.append(f"group: {_ts_json(group)}")
            if item.get("dock_only"):
                extras.append("dockOnly: true")
            if item.get("capability"):
                extras.append(f"capability: {_ts_json(item['capability'])}")
            extra_str = (", " + ", ".join(extras)) if extras else ""
            lines.append(
                f"  {{token: {_ts_json(tok)}, label: {_ts_json(label)}{extra_str}}},"
            )
        lines.extend(["];", ""])


def _append_world_clocks_ts(lines: list[str], world_clock_zones: list[dict[str, Any]]) -> None:
    lines.extend(
        [
            "export interface WorldClockZoneItem {",
            "  iana: string;",
            "  city: string;",
            "  label: string;",
            "  std_off: number;",
            "  dst_off: number;",
            "  std_abbr: string;",
            "  dst_abbr: string;",
            "  rule: string;",
            "}",
            "",
            "export const WORLD_CLOCK_ZONES_CATALOG: ReadonlyArray<WorldClockZoneItem> = [",
        ]
    )
    lines.extend(
        f"  {{iana: {_ts_json(z['iana'])}, city: {_ts_json(z['city'])}, label: {_ts_json(z['label'])}, "
        f"std_off: {int(z['std_off'])}, dst_off: {int(z['dst_off'])}, "
        f"std_abbr: {_ts_json(z['std_abbr'])}, dst_abbr: {_ts_json(z['dst_abbr'])}, "
        f"rule: {_ts_json(z['rule'])} }},"
        for z in world_clock_zones
    )
    lines.extend(["];", ""])


def _append_device_pref_specs_ts(
    lines: list[str],
    device_pref_specs: list[dict[str, Any]],
    device_pref_ui: dict[str, dict[str, Any]],
) -> None:
    lines.extend(
        [
            "export interface DevicePrefSpecItem {",
            "  key: string;",
            "  label: string;",
            '  domain: "select" | "switch" | "number" | "text";',
            "  default: boolean | number | string;",
            "  section: string;",
            '  group_tier: "behavior" | "display" | "interface" | null;',
            "  options: ReadonlyArray<string>;",
            "  min: number | null;",
            "  max: number | null;",
            "  step: number | null;",
            "  unit: string;",
            "  capability: string;",
            "}",
            "",
            "export const DEVICE_PREF_SPECS_CATALOG: ReadonlyArray<DevicePrefSpecItem> = [",
        ]
    )
    for p in device_pref_specs:
        key = str(p["key"])
        ui = device_pref_ui[key]
        opts_ts = "[" + ", ".join(_ts_json(o) for o in (p.get("options") or [])) + "]"
        lines.append(
            f"  {{key: {_ts_json(key)}, label: {_ts_json(ui['label'])}, domain: {_ts_json(p['domain'])}, "
            f"default: {_ts_json(p['default'])}, section: {_ts_json(ui['section'])}, "
            f"group_tier: {_ts_json(ui['group_tier'])}, "
            f"options: {opts_ts}, min: {_ts_json(p.get('min'))}, max: {_ts_json(p.get('max'))}, "
            f"step: {_ts_json(p.get('step'))}, unit: {_ts_json(ui['unit'])}, "
            f"capability: {_ts_json(p['capability'])} }},"
        )
    lines.extend(
        [
            "];",
            "",
            "export const DEVICE_PREF_SPECS_MAP: Readonly<Record<string, DevicePrefSpecItem>> = "
            "Object.fromEntries(DEVICE_PREF_SPECS_CATALOG.map((s) => [s.key, s]));",
            "",
        ]
    )


def build_typescript_schema(
    protocol_schema: dict[str, Any],
    studio_data: dict[str, Any],
) -> str:
    """Render ha-latter/frontend_src/src/protocol-schema.ts from protocol_v3.json + studio_contract.json."""
    validate_contracts(protocol_schema, studio_data)

    studio_contract = studio_data["studio_contract"]
    catalogs = protocol_schema.get("catalogs", {})
    catalog_ui = studio_data["catalog_ui"]
    defaults = protocol_schema.get("defaults", {})
    world_clock_zones = studio_data["world_clock_zones"]
    device_pref_specs = protocol_schema["device_pref_specs"]
    device_pref_ui = studio_data["device_pref_ui"]

    lines: list[str] = [
        "// AUTO-GENERATED FROM protocol_v3.json + studio_contract.json BY tools/gen_studio_schema.py — DO NOT EDIT MANUALLY.",
        "",
        f"export const PROTOCOL_CONTRACT_VERSION = {int(protocol_schema['contract_version'])};",
        f"export const STUDIO_REV = {int(studio_contract['studio_rev'])};",
        "",
        "export const ALLOWED_DEVICE_ACTIONS: ReadonlyArray<string> = [",
        *(f"  {_ts_json(str(act))}," for act in studio_contract["allowed_device_actions"]),
        "];",
        "",
        "export const SYSTEM_WS_COMMANDS: ReadonlySet<string> = new Set([",
        *(f"  {_ts_json(str(cmd))}," for cmd in studio_contract["system_commands"]),
        "]);",
        "",
        "export const DEVICE_WS_COMMANDS: ReadonlySet<string> = new Set([",
        *(f"  {_ts_json(str(cmd))}," for cmd in studio_contract["device_commands"]),
        "]);",
        "",
    ]

    _append_catalogs_ts(lines, catalogs, catalog_ui)
    _append_world_clocks_ts(lines, world_clock_zones)
    _append_device_pref_specs_ts(lines, device_pref_specs, device_pref_ui)

    for key, val in defaults.items():
        const_name = f"DEFAULT_{key.upper()}"
        lines.append(f"export const {const_name} = {_ts_json(val)};")
        if key in _CSV_DEFAULT_KEYS:
            tokens = [t.strip() for t in str(val).split(",") if t.strip()]
            lines.append(f"export const DEFAULT_{key.upper()}_TOKENS: ReadonlyArray<string> = [")
            lines.extend(f"  {_ts_json(tok)}," for tok in tokens)
            lines.extend(["];", ""])
        else:
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for generating or checking frontend_src/src/protocol-schema.ts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify protocol-schema.ts matches protocol_v3.json + studio_contract.json without writing.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    comp_dir = repo_root / "custom_components" / "latter"
    protocol_path = comp_dir / "protocol_v3.json"
    studio_path = comp_dir / "studio_contract.json"
    ts_path = repo_root / "frontend_src" / "src" / "protocol-schema.ts"

    protocol_schema = json.loads(protocol_path.read_text(encoding="utf-8"))
    studio_data = json.loads(studio_path.read_text(encoding="utf-8"))
    expected_ts = build_typescript_schema(protocol_schema, studio_data)

    if args.check:
        if not ts_path.is_file() or ts_path.read_text(encoding="utf-8") != expected_ts:
            print(
                f"[STUDIO SCHEMA DRIFT] {ts_path} is out of date with {protocol_path.name} + {studio_path.name}",
                file=sys.stderr,
            )
            return 1
        return 0

    ts_path.parent.mkdir(parents=True, exist_ok=True)
    ts_path.write_text(expected_ts, encoding="utf-8", newline="\n")
    print(f"Generated {ts_path.name} from {protocol_path.name} + {studio_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
