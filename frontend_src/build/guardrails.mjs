/**
 * Studio Static Guardrails & Coarse Directory DAG Validator (Tarjan SCC over esbuild metafile, `D-078`).
 */

import fs from "node:fs";
import path from "node:path";

const LEAF_EXACT_MODULES = new Set([
  "src/types.ts",
  "src/constants.ts",
  "src/protocol-schema.ts",
  "src/mdi-chunks.ts",
]);

function isLeafModule(rel) {
  return LEAF_EXACT_MODULES.has(rel) || rel.startsWith("src/styles/") || rel.startsWith("src/lib/");
}

function isTopLevelView(rel) {
  return rel.startsWith("src/views/") && !rel.slice("src/views/".length).includes("/");
}

function collectTsSourceFiles(srcDir) {
  const out = [];
  function walk(dir) {
    for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, ent.name);
      if (ent.isDirectory()) {
        walk(full);
      } else if (ent.isFile() && ent.name.endsWith(".ts")) {
        out.push(full);
      }
    }
  }
  walk(srcDir);
  return out.sort();
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

/**
 * Validates Tarjan SCC 0-cycle DAG, 4 coarse Studio directory boundaries,
 * and external bare package allowlist (`lit`, `lit/*`) directly from esbuild `metafile.inputs`.
 */
export function runStudioDagGuardrails(metafile, errors) {
  const inputs = metafile?.inputs;
  if (!inputs || typeof inputs !== "object") {
    errors.push("[STUDIO DAG] Missing esbuild metafile.inputs");
    return;
  }

  const normalizedInputs = new Map();
  for (const [rawKey, info] of Object.entries(inputs)) {
    const rel = rawKey.replace(/\\/g, "/");
    if (rel.startsWith("src/")) {
      normalizedInputs.set(rel, info);
    }
  }

  const nodes = [...normalizedInputs.keys()].sort();
  const nodeSet = new Set(nodes);
  const edgesByNode = new Map(nodes.map((n) => [n, []]));

  for (const rel of nodes) {
    const info = normalizedInputs.get(rel);
    const seenTargets = new Set();

    for (const imp of info?.imports || []) {
      const orig = typeof imp.original === "string" ? imp.original : "";
      const target = typeof imp.path === "string" ? imp.path.replace(/\\/g, "/") : "";

      if (orig && !orig.startsWith(".")) {
        if (orig !== "lit" && !orig.startsWith("lit/")) {
          errors.push(
            `[STUDIO DAG] Forbidden external package import "${orig}" in ${rel} (only "lit" and "lit/*" allowed)`,
          );
        }
        continue;
      }

      if (imp.external) {
        if (!orig.startsWith("./latter-studio-mdi.js")) {
          errors.push(`[STUDIO DAG] Unexpected external import "${orig || target}" in ${rel}`);
        }
        continue;
      }

      if (!target || !nodeSet.has(target)) {
        continue;
      }

      if (target === rel) {
        errors.push(`[STUDIO DAG] Self-import detected in ${rel}`);
        continue;
      }

      if (!seenTargets.has(target)) {
        seenTargets.add(target);
        edgesByNode.get(rel).push(target);
      }

      // (a) Leaf modules never import state, api, components, views, or shell
      if (
        isLeafModule(rel) &&
        (target.startsWith("src/state/") ||
          target.startsWith("src/api/") ||
          target.startsWith("src/components/") ||
          target.startsWith("src/views/") ||
          target === "src/latter-studio.ts")
      ) {
        errors.push(`[STUDIO DAG] Leaf boundary violation: ${rel} -> ${target}`);
      }

      // (b) state/* never imports components, views, or shell; sub-controllers never import store.ts
      if (rel.startsWith("src/state/")) {
        if (
          target.startsWith("src/components/") ||
          target.startsWith("src/views/") ||
          target === "src/latter-studio.ts"
        ) {
          errors.push(`[STUDIO DAG] State boundary violation: ${rel} -> ${target}`);
        }
        if (rel !== "src/state/store.ts" && target === "src/state/store.ts") {
          errors.push(
            `[STUDIO DAG] State sub-controller must not import store.ts: ${rel} -> ${target}`,
          );
        }
      }

      // (c) components/* never imports views/* or shell
      if (
        rel.startsWith("src/components/") &&
        (target.startsWith("src/views/") || target === "src/latter-studio.ts")
      ) {
        errors.push(`[STUDIO DAG] Component boundary violation: ${rel} -> ${target}`);
      }

      // (d) views/* never imports shell; top-level views/*.ts (except index.ts) never import sibling top-level views/*.ts
      if (rel.startsWith("src/views/")) {
        if (target === "src/latter-studio.ts") {
          errors.push(`[STUDIO DAG] View boundary violation: ${rel} -> ${target}`);
        }
        if (rel !== "src/views/index.ts" && isTopLevelView(rel) && isTopLevelView(target)) {
          errors.push(
            `[STUDIO DAG] Sibling top-level view import forbidden: ${rel} -> ${target}`,
          );
        }
      }
    }
  }

  const sccs = computeTarjanSccs(nodes, edgesByNode);
  const cyclicSccs = sccs.filter((comp) => comp.length > 1);
  for (const comp of cyclicSccs) {
    errors.push(`[STUDIO DAG] Strongly connected cycle detected: ${comp.sort().join(" <-> ")}`);
  }
}

export function runStaticGuardrails(frontendDir, metafile, bundleText, mdiBundleText) {
  const errors = [];
  const srcDir = path.join(frontendDir, "src");

  runStudioDagGuardrails(metafile, errors);

  const allSourceFiles = collectTsSourceFiles(srcDir);
  const sourceEntries = allSourceFiles.map((absFile) => ({
    absFile,
    relFromFrontend: path.relative(frontendDir, absFile).replace(/\\/g, "/"),
    label: path.relative(path.resolve(frontendDir, ".."), absFile).replace(/\\/g, "/"),
    text: fs.readFileSync(absFile, "utf8"),
  }));

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

  for (const item of sourceEntries) {
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

    if (/<h[3-6][^>]*class="[^"]*card-title/.test(item.text)) {
      errors.push(
        `[STUDIO HEADINGS] ${item.label} uses <h3..h6 class="card-title">; use <h2 class="card-title">`,
      );
    }

    if (/<summary\b[^>]*>(?:(?!<\/summary>)[\s\S])*?<h[1-6]\b/.test(item.text)) {
      errors.push(
        `[STUDIO HEADINGS] ${item.label} nests a heading element inside <summary>; use <span class="card-title">`,
      );
    }

    if (
      item.relFromFrontend.startsWith("src/components/dialogs/") &&
      /\btarget\s*===\s*[A-Za-z_$][\w$.]*currentTarget\b/.test(item.text)
    ) {
      errors.push(
        `[STUDIO DIALOGS] ${item.label} uses target === currentTarget for dialog dismissal; use createDialogBackdropHandlers()`,
      );
    }
  }

  // Minified-safe runtime checks on built bundles
  const bannedRuntimeRe = new RegExp(
    "hass" + "Tokens|hass-" + "subpage|\\bfe" + "tch\\s*\\(",
  );
  for (const built of [
    { label: "custom_components/latter/frontend/latter-studio.js", text: bundleText },
    { label: "custom_components/latter/frontend/latter-studio-mdi.js", text: mdiBundleText },
  ]) {
    const mRuntime = built.text.match(bannedRuntimeRe);
    if (mRuntime) {
      errors.push(`[STUDIO BUNDLE] ${built.label} matched forbidden runtime pattern: ${mRuntime[0]}`);
    }
    const mWin = built.text.match(bannedWindowAssignRe);
    if (mWin) {
      errors.push(`[STUDIO BUNDLE] ${built.label} assigns global property: ${mWin[0]}`);
    }
  }

  // Shell & default navigation checks against canonical source
  const shellText =
    sourceEntries.find((e) => e.relFromFrontend === "src/latter-studio.ts")?.text ?? "";
  const storeText =
    sourceEntries.find((e) => e.relFromFrontend === "src/state/store.ts")?.text ?? "";

  const tabDevPos = shellText.indexOf('id="tab-scope-device"');
  const tabSysPos = shellText.indexOf('id="tab-scope-system"');
  if (!(tabDevPos >= 0 && tabSysPos > tabDevPos)) {
    errors.push("[STUDIO DEFAULT VIEW] tab-scope-device must appear before tab-scope-system");
  }
  if (!/currentScope(?:\s*:\s*[^=]+)?\s*=\s*"device"/.test(storeText)) {
    errors.push('[STUDIO DEFAULT VIEW] Default scope must initialize to "device"');
  }
  if (!/currentViewId(?:\s*:\s*[^=]+)?\s*=\s*"select_device_prompt"/.test(storeText)) {
    errors.push('[STUDIO DEFAULT VIEW] Default view must initialize to "select_device_prompt"');
  }
  if (!/(?:_applyRoute|applyRoute)\s*\(/.test(shellText)) {
    errors.push("[STUDIO DEFAULT VIEW] Shell must invoke _applyRoute / applyRoute");
  }

  // D-014 two-column layout verification across all 13 two-column views in canonical source
  const allViewsText = sourceEntries
    .filter((e) => e.relFromFrontend.startsWith("src/views/"))
    .map((e) => e.text)
    .join("\n");

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
    const secMatch = allViewsText.match(secRe);
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

  if (errors.length > 0) {
    for (const e of errors) {
      process.stderr.write(`  - ${e}\n`);
    }
    throw new Error(`Studio guardrail verification failed with ${errors.length} issue(s)`);
  }
}
