/**
 * Studio Static Guardrails, Zero-Cycle `L0`–`L4` DAG Validator (Tarjan SCC),
 * & Vendor Provenance Verifier (`L4`).
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import {
  collectBuildModules,
  collectSourceModules,
  resolveImportTarget,
  scanRawSpecifiers,
} from "./lexer.mjs";

const L2_MIDDLE_CONTROLLERS = new Set([
  "src/state/settings-save-controller.ts",
  "src/state/subscription.ts",
  "src/state/groups-controller.ts",
]);

/**
 * Classifies every file in `frontend_src/src/**` and `frontend_src/build/**` (+ `build.mjs`)
 * into a deterministic `[majorLayer, minorRank, label]` tuple (`L0` through `L4`).
 */
export function classifyStudioModuleLayer(rel) {
  // L0 — Pure types, generated schema, raw icon chunks, pure math, CSS sheets, vendored lit-html
  if (rel === "src/lib/vendor/lit-html.js") return [0, 0, "L0"];
  if (
    rel === "src/lib/vendor/directive.js" ||
    rel === "src/lib/vendor/directive-helpers.js"
  ) {
    return [0, 1, "L0"];
  }
  if (rel.startsWith("src/lib/vendor/")) return [0, 2, "L0"];
  if (
    rel === "src/lib/lit.ts" ||
    rel === "src/protocol-schema.ts" ||
    rel === "src/mdi-chunks.ts" ||
    rel === "src/utils/crop-math.ts"
  ) {
    return [0, 3, "L0"];
  }
  if (rel === "src/types.ts") return [0, 4, "L0"];
  if (rel === "src/constants.ts") return [0, 5, "L0"];
  if (rel === "src/styles/tokens.ts") return [0, 7, "L0"];
  if (rel.startsWith("src/styles/")) return [0, 6, "L0"];

  // L1 — i18n, MDI search/unpacker, WS transport, pure domain logic, StudioStoreContext contract
  if (rel === "src/i18n/en.ts") return [1, 0, "L1"];
  if (rel === "src/i18n/index.ts") return [1, 1, "L1"];
  if (rel === "src/mdi-catalog.ts" || rel.startsWith("src/api/")) return [1, 0, "L1"];
  if (rel.startsWith("src/utils/")) return [1, 3, "L1"];
  if (rel.startsWith("src/domain/") || rel === "src/state/store-types.ts") return [1, 4, "L1"];

  // L3 — Store facade (`store.ts`), UI controls, dialogs, & views
  if (rel === "src/state/store.ts") return [3, 0, "L3"];

  // L2 — Acyclic state controllers & domain operations (never import `store.ts`)
  if (rel === "src/state/entity-actions-controller.ts") return [2, 2, "L2"];
  if (L2_MIDDLE_CONTROLLERS.has(rel)) return [2, 1, "L2"];
  if (rel.startsWith("src/state/")) return [2, 0, "L2"];

  // L3 sub-layers — Controls -> Dialogs / Sub-views -> Views -> View router
  if (rel === "src/components/controls/aria-helpers.ts") return [3, 1, "L3"];
  if (rel === "src/components/controls/rows.ts") return [3, 3, "L3"];
  if (rel === "src/components/controls/entity-adapters.ts") return [3, 4, "L3"];
  if (rel === "src/components/controls/device-banners.ts") return [3, 5, "L3"];
  if (rel.startsWith("src/components/controls/")) return [3, 2, "L3"];
  if (rel === "src/components/controls.ts") return [3, 6, "L3"];

  if (
    rel === "src/components/dialogs/color-wheel.ts" ||
    rel === "src/components/dialogs/world-clocks.ts"
  ) {
    return [3, 7, "L3"];
  }
  if (rel === "src/components/dialogs/app-config.ts") return [3, 9, "L3"];
  if (rel.startsWith("src/components/dialogs/")) return [3, 8, "L3"];
  if (rel === "src/components/dialogs.ts") return [3, 10, "L3"];

  if (rel.startsWith("src/views/overview/") || rel.startsWith("src/views/groups/")) {
    return [3, 8, "L3"];
  }
  if (rel === "src/views/index.ts") return [3, 12, "L3"];
  if (rel.startsWith("src/views/")) return [3, 11, "L3"];

  // L4 — Custom element shell (`latter-studio.ts`) & build toolchain
  if (rel === "src/latter-studio.ts") return [4, 0, "L4"];
  if (rel === "build/lexer.mjs") return [4, 1, "L4"];
  if (rel === "build/compactor.mjs" || rel === "build/assets.mjs") return [4, 2, "L4"];
  if (rel === "build/bundler.mjs" || rel === "build/guardrails.mjs") return [4, 3, "L4"];
  if (rel === "build.mjs") return [4, 4, "L4"];

  return null;
}

/**
 * Deterministic Tarjan Strongly Connected Components (SCC) over a directed graph.
 */
function computeTarjanSccs(nodes, edgesByNode) {
  let index = 0;
  const indices = new Map();
  const lowlink = new Map();
  const onStack = new Set();
  const stack = [];
  const sccs = [];

  function strongConnect(v) {
    indices.set(v, index);
    lowlink.set(v, index);
    index += 1;
    stack.push(v);
    onStack.add(v);

    const neighbors = edgesByNode.get(v) || [];
    for (const w of neighbors) {
      if (!indices.has(w)) {
        strongConnect(w);
        lowlink.set(v, Math.min(lowlink.get(v), lowlink.get(w)));
      } else if (onStack.has(w)) {
        lowlink.set(v, Math.min(lowlink.get(v), indices.get(w)));
      }
    }

    if (lowlink.get(v) === indices.get(v)) {
      const component = [];
      while (stack.length > 0) {
        const w = stack.pop();
        onStack.delete(w);
        component.push(w);
        if (w === v) break;
      }
      sccs.push(component);
    }
  }

  for (const node of nodes) {
    if (!indices.has(node)) {
      strongConnect(node);
    }
  }
  return sccs;
}

function verifyVendorProvenance(frontendDir, errors) {
  const pkgPath = path.join(frontendDir, "package.json");
  if (!fs.existsSync(pkgPath)) {
    errors.push("[STUDIO VENDOR] Missing frontend_src/package.json");
    return;
  }
  const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
  const litProv = pkg?.vendorProvenance?.["lit-html"];
  if (!litProv || !litProv.version || !litProv.files || typeof litProv.files !== "object") {
    errors.push("[STUDIO VENDOR] Missing vendorProvenance['lit-html'] metadata in package.json");
    return;
  }

  const vendorRootRel = String(litProv.vendorRoot || "src/lib/vendor").replace(/\\/g, "/");
  const vendorDir = path.join(frontendDir, vendorRootRel);
  const diskFiles = [];
  function walkVendor(dir) {
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) walkVendor(full);
      else if (ent.isFile()) {
        diskFiles.push(path.relative(vendorDir, full).replace(/\\/g, "/"));
      }
    }
  }
  walkVendor(vendorDir);

  for (const relInVendor of diskFiles.sort()) {
    const rel = `${vendorRootRel}/${relInVendor}`;
    const meta = litProv.files[relInVendor] || litProv.files[rel];
    if (!meta || !meta.upstreamSha256Lf || !meta.vendoredSha256Lf) {
      errors.push(`[STUDIO VENDOR] Missing SHA-256 provenance entry in package.json for ${rel}`);
      continue;
    }
    const rawLf = fs.readFileSync(path.join(vendorDir, relInVendor), "utf8").replace(/\r\n/g, "\n");
    const actualSha = crypto.createHash("sha256").update(rawLf, "utf8").digest("hex");
    if (actualSha !== meta.vendoredSha256Lf) {
      errors.push(
        `[STUDIO VENDOR] SHA-256 mismatch for ${rel}: expected ${meta.vendoredSha256Lf}, got ${actualSha}`,
      );
    }
    if ((rel.endsWith(".js") || rel.endsWith(".d.ts")) && !rawLf.includes(meta.upstreamSha256Lf)) {
      errors.push(
        `[STUDIO VENDOR] ${rel} is missing upstream provenance header (${meta.upstreamSha256Lf})`,
      );
    }
  }
}

export function runStudioDagGuardrails(frontendDir, errors) {
  const srcDir = path.join(frontendDir, "src");
  const srcFiles = collectSourceModules(srcDir);
  const buildFiles = collectBuildModules(frontendDir);
  const allModules = [...srcFiles, ...buildFiles];

  const relOf = (f) => path.relative(frontendDir, f).replace(/\\/g, "/");
  const nodes = allModules.map(relOf).sort();
  const nodeSet = new Set(nodes);
  const edgesByNode = new Map(nodes.map((n) => [n, []]));

  for (const absFile of allModules) {
    const rel = relOf(absFile);
    const rawText = fs.readFileSync(absFile, "utf8");

    const srcLayer = classifyStudioModuleLayer(rel);
    if (!srcLayer) {
      errors.push(`[STUDIO DAG] Unclassified Studio module ${rel} — assign a layer in guardrails.mjs`);
      continue;
    }

    const specs = scanRawSpecifiers(rawText);
    const seenTargets = new Set();

    for (const item of specs) {
      const spec = item.specifier;
      if (rel.startsWith("build") && spec.startsWith("node:")) {
        continue;
      }
      if (!spec.startsWith(".")) {
        errors.push(`[STUDIO DAG] Forbidden non-relative import "${spec}" in ${rel}`);
        continue;
      }
      let targetAbs;
      try {
        targetAbs = resolveImportTarget(frontendDir, absFile, spec);
      } catch (err) {
        errors.push(`[STUDIO DAG] ${err instanceof Error ? err.message : String(err)}`);
        continue;
      }
      const targetRel = relOf(targetAbs);
      if (!nodeSet.has(targetRel)) {
        continue;
      }
      if (targetRel === rel) {
        errors.push(`[STUDIO DAG] Self-import detected in ${rel}`);
        continue;
      }
      if (!seenTargets.has(targetRel)) {
        seenTargets.add(targetRel);
        edgesByNode.get(rel).push(targetRel);
      }

      const dstLayer = classifyStudioModuleLayer(targetRel);
      if (!dstLayer) continue;

      const [srcMaj, srcMin, srcLabel] = srcLayer;
      const [dstMaj, dstMin, dstLabel] = dstLayer;

      const strictlyDownward = dstMaj < srcMaj || (dstMaj === srcMaj && dstMin < srcMin);
      if (!strictlyDownward) {
        errors.push(
          `[STUDIO DAG] Layer violation (${item.kind} import): ${rel} (${srcLabel}.${srcMin}) -> ${targetRel} (${dstLabel}.${dstMin})`,
        );
      }
    }
  }

  const sccs = computeTarjanSccs(nodes, edgesByNode);
  const cyclicSccs = sccs.filter((comp) => comp.length > 1);
  for (const comp of cyclicSccs) {
    errors.push(`[STUDIO DAG] Strongly connected cycle detected: ${comp.sort().join(" <-> ")}`);
  }

  verifyVendorProvenance(frontendDir, errors);
}

export function runStaticGuardrails(frontendDir, bundleText, mdiBundleText) {
  const errors = [];
  const srcDir = path.join(frontendDir, "src");

  runStudioDagGuardrails(frontendDir, errors);

  const allSourceFiles = collectSourceModules(srcDir);
  const scanTargets = [
    { label: "custom_components/latter/frontend/latter-studio.js", text: bundleText },
    { label: "custom_components/latter/frontend/latter-studio-mdi.js", text: mdiBundleText },
    ...allSourceFiles.map((f) => ({
      label: path.relative(path.resolve(frontendDir, ".."), f).replace(/\\/g, "/"),
      text: fs.readFileSync(f, "utf8"),
    })),
  ];

  const bannedApiRe = new RegExp(
    "hass" +
      "Tokens|hass-" +
      "subpage|CONF_WEB_THEME|renderYamlGenerator|\\b(?:fe" +
      "tch|call" +
      "Api)\\s*\\(",
  );
  const bannedTermRe = /\b(household|households|fleet|rooms?)\b/i;
  const bannedWindowAssignRe = new RegExp("\\bwin" + "dow\\.[A-Za-z0-9_]+\\s*=(?!=)");
  const bannedInlineHandlerRe = new RegExp(
    "\\bon" + "click\\s*=|\\bon(?:change|input|keydown|toggle)\\s*=\\s*[\"']",
  );
  const bannedInlineStyleRe =
    /\bstyle=["'](?!\s*--|\s*\$\{)|\bstyle=["']\s*\$\{\s*["'`](?!\s*--)|\bstyle=\$\{\s*["'`](?!\s*--)|\.style\.(?!setProperty\(["']--)|\bstyle\.cssText\b/;

  for (const item of scanTargets) {
    const mApi = item.text.match(bannedApiRe);
    if (mApi) errors.push(`[STUDIO INVARIANT] ${item.label} matched forbidden pattern: ${mApi[0]}`);

    const mTerm = item.text.match(bannedTermRe);
    if (mTerm) errors.push(`[STUDIO TERMINOLOGY] ${item.label} matched banned term: ${mTerm[0]}`);

    const mWin = item.text.match(bannedWindowAssignRe);
    if (mWin) {
      errors.push(`[STUDIO HANDLER BINDINGS] ${item.label} assigns global property: ${mWin[0]}`);
    }

    const mOn = item.text.match(bannedInlineHandlerRe);
    if (mOn) {
      errors.push(
        `[STUDIO HANDLER BINDINGS] ${item.label} uses inline HTML event attribute: ${mOn[0]}`,
      );
    }

    const mStyle = item.text.match(bannedInlineStyleRe);
    if (mStyle) {
      errors.push(`[STUDIO INLINE STYLES] ${item.label} uses non-token inline style: ${mStyle[0]}`);
    }

    for (const mIdent of item.text.matchAll(/\bstyle=\$\{\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\}/g)) {
      const ident = mIdent[1];
      if (ident === "nothing") continue;
      const assignRe = new RegExp(`\\b${ident}\\s*=\\s*["'\`]\\s*--`);
      if (!assignRe.test(item.text)) {
        errors.push(
          `[STUDIO INLINE STYLES] ${item.label} binds style=\${${ident}} without a local \`--*\` custom property string`,
        );
      }
    }
  }

  const tabDevPos = bundleText.indexOf('id="tab-scope-device"');
  const tabSysPos = bundleText.indexOf('id="tab-scope-system"');
  if (!(tabDevPos >= 0 && tabSysPos > tabDevPos)) {
    errors.push("[STUDIO DEFAULT VIEW] tab-scope-device must appear before tab-scope-system");
  }
  if (!/(?:CURRENT_SCOPE|currentScope|scope)\s*[:=]\s*"device"/.test(bundleText)) {
    errors.push('[STUDIO DEFAULT VIEW] Default scope must initialize to "device"');
  }
  if (
    !/(?:CURRENT_VIEW_ID|currentViewId|viewId|activeView)\s*[:=]\s*"select_device_prompt"/.test(
      bundleText,
    )
  ) {
    errors.push('[STUDIO DEFAULT VIEW] Default view must initialize to "select_device_prompt"');
  }
  if (!/(?:_applyRoute|applyRoute)\s*\(/.test(bundleText)) {
    errors.push("[STUDIO DEFAULT VIEW] Bundle must invoke _applyRoute / applyRoute");
  }

  const twoColumnViews = [
    "system_overview",
    "shared_entities",
    "remotes",
    "system_sync",
    "area_tracking",
    "system_tools",
    "dashboard",
    "display",
    "interface",
    "audio_voice",
    "power",
    "presence",
    "tools",
  ];
  for (const vid of twoColumnViews) {
    const secRe = new RegExp(`<section id="view-${vid}"[\\s\\S]*?<\\/section>`);
    const secMatch = bundleText.match(secRe);
    if (!secMatch) {
      errors.push(`[STUDIO LAYOUT] Missing <section id="view-${vid}">`);
      continue;
    }
    const colsCnt = (secMatch[0].match(/<div class="columns">/g) || []).length;
    const colCnt = (secMatch[0].match(/<div class="column">/g) || []).length;
    if (colsCnt !== 1 || colCnt !== 2) {
      errors.push(
        `[STUDIO LAYOUT] D-014 violation in view-${vid}: expected 1 .columns and 2 .column, found ${colsCnt} .columns and ${colCnt} .column`,
      );
    }
  }
  if (/<h2[^>]*class="[^"]*card-title/.test(bundleText)) {
    errors.push('[STUDIO HEADINGS] Card titles must use <h3 class="card-title">, not <h2>');
  }

  if (errors.length > 0) {
    for (const e of errors) {
      process.stderr.write(`  - ${e}\n`);
    }
    throw new Error(`Studio guardrail verification failed with ${errors.length} issue(s)`);
  }
}
