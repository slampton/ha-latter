#!/usr/bin/env node
/**
 * Deterministic TypeScript -> Single-File ESM Bundler & Verifier for Latter Studio (`D-024`).
 *
 * Modes:
 *   node build.mjs              -> Run mandatory `tsc --noEmit`, type-strip, compact, verify, and write latter-studio.js
 *   node build.mjs --typecheck  -> Run mandatory `tsc --noEmit` + TS strip + ESM graph & V8 module parse check
 *   node build.mjs --check      -> Run `--typecheck` + verify committed `latter-studio.js` is byte-identical + Studio guardrails
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const FRONTEND_DIR = path.dirname(__filename);
const SRC_DIR = path.join(FRONTEND_DIR, "src");
const ENTRY_FILE = path.join(SRC_DIR, "latter-studio.ts");
const OUT_FILE = path.resolve(
  FRONTEND_DIR,
  "..",
  "custom_components",
  "latter",
  "frontend",
  "latter-studio.js",
);

const args = new Set(process.argv.slice(2));
const modeCheck = args.has("--check");
const modeTypecheckOnly = args.has("--typecheck");

function collectTsFiles(dir) {
  const out = [];
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      out.push(...collectTsFiles(full));
    } else if (ent.isFile() && ent.name.endsWith(".ts")) {
      out.push(full);
    }
  }
  return out.sort((a, b) => a.localeCompare(b));
}

function runMandatoryTsc() {
  const tscBin = path.join(FRONTEND_DIR, "node_modules", "typescript", "bin", "tsc");
  if (!fs.existsSync(tscBin)) {
    throw new Error(
      "Missing local TypeScript compiler (`node_modules/typescript/bin/tsc`) — install local devDependencies before building",
    );
  }
  const res = spawnSync(
    process.execPath,
    [tscBin, "--noEmit", "-p", path.join(FRONTEND_DIR, "tsconfig.json")],
    { cwd: FRONTEND_DIR, encoding: "utf8" },
  );
  if (res.status !== 0) {
    process.stderr.write(res.stdout || "");
    process.stderr.write(res.stderr || "");
    throw new Error("tsc --noEmit failed");
  }
}

function resolveImportTarget(fromFile, specifier) {
  if (!specifier.startsWith(".")) {
    throw new Error(
      `External bare import "${specifier}" in ${path.relative(FRONTEND_DIR, fromFile)} is not allowed in zero-runtime-dep bundle`,
    );
  }
  const baseDir = path.dirname(fromFile);
  const rawTarget = path.resolve(baseDir, specifier);
  const candidates = [];
  if (rawTarget.endsWith(".js")) {
    candidates.push(rawTarget.slice(0, -3) + ".ts");
  }
  candidates.push(rawTarget, rawTarget + ".ts", path.join(rawTarget, "index.ts"));
  for (const c of candidates) {
    if (fs.existsSync(c) && fs.statSync(c).isFile()) {
      return c;
    }
  }
  throw new Error(
    `Cannot resolve import "${specifier}" from ${path.relative(FRONTEND_DIR, fromFile)}`,
  );
}

function parseRuntimeImports(jsCode) {
  const imports = [];
  const importRe = /^\s*import\s+([\s\S]*?)\s+from\s+["']([^"']+)["']\s*;?/gm;
  let m;
  while ((m = importRe.exec(jsCode)) !== null) {
    const clause = m[1].trim();
    const specifier = m[2].trim();
    const named = [];
    const braceMatch = clause.match(/\{([\s\S]*?)\}/);
    if (braceMatch) {
      for (const part of braceMatch[1].split(",")) {
        const cleaned = part.trim();
        if (!cleaned) continue;
        const [orig] = cleaned.split(/\s+as\s+/);
        if (orig && orig.trim()) named.push(orig.trim());
      }
    }
    imports.push({ specifier, named });
  }
  const sideEffectRe = /^\s*import\s+["']([^"']+)["']\s*;?/gm;
  while ((m = sideEffectRe.exec(jsCode)) !== null) {
    imports.push({ specifier: m[1].trim(), named: [] });
  }
  return imports;
}

function parseRuntimeExports(jsCode) {
  const exported = new Set();
  const declRe =
    /^\s*export\s+(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)/gm;
  let m;
  while ((m = declRe.exec(jsCode)) !== null) {
    exported.add(m[1]);
  }
  const listRe = /^\s*export\s*\{([\s\S]*?)\}\s*;?/gm;
  while ((m = listRe.exec(jsCode)) !== null) {
    for (const part of m[1].split(",")) {
      const cleaned = part.trim();
      if (!cleaned) continue;
      const segments = cleaned.split(/\s+as\s+/);
      exported.add((segments[1] || segments[0]).trim());
    }
  }
  return exported;
}

function transformModuleBody(jsCode) {
  let out = jsCode;
  out = out.replace(/^\/\/#\s*sourceURL=.*$/gm, "");
  // Remove multi-line and single-line ES module import declarations
  out = out.replace(/^\s*import\s+[\s\S]*?\s+from\s+["'][^"']+["']\s*;?[ \t]*$/gm, "");
  out = out.replace(/^\s*import\s*\{\s*\}\s*from\s*["'][^"']+["']\s*;?[ \t]*$/gm, "");
  out = out.replace(/^\s*import\s+["'][^"']+["']\s*;?[ \t]*$/gm, "");
  // Remove standalone `export {};` / `export { a, b };`
  out = out.replace(/^\s*export\s*\{[\s\S]*?\}\s*;?[ \t]*$/gm, "");
  // Unwrap `export` keyword on top-level declarations
  out = out.replace(
    /^(\s*)export\s+(async\s+function|function|class|const|let|var)\b/gm,
    "$1$2",
  );
  return out.trim();
}

function compactCodeSegment(seg, isLineStart) {
  if (!seg) return seg;
  let indent = "";
  let rest = seg;
  if (isLineStart) {
    const m = seg.match(/^[ \t]+/);
    if (m) {
      indent = m[0];
      rest = seg.slice(indent.length);
    }
  }
  rest = rest
    .replace(/[ \t]{2,}/g, " ")
    .replace(/ ([),;])/g, "$1")
    .replace(/([A-Za-z0-9_$]) \(\)/g, "$1()");
  return indent + rest;
}

/**
 * Lexer-aware compactor that strips `stripTypeScriptTypes` whitespace/blank "type hole" lines
 * and inline type-erasure space runs outside literals/comments while preserving template literals verbatim.
 */
function compactBundleOutsideTemplates(code) {
  const stack = [{ kind: "code", braces: 0 }];
  const outLines = [];
  let lineBuf = "";
  let codeSeg = "";
  let lineTouchedTemplate = false;

  const top = () => stack[stack.length - 1];
  const flushCodeSeg = () => {
    if (codeSeg) {
      lineBuf += compactCodeSegment(codeSeg, lineBuf.length === 0);
      codeSeg = "";
    }
  };

  for (let i = 0; i < code.length; i += 1) {
    const ch = code[i];
    const next = i + 1 < code.length ? code[i + 1] : "";
    const cur = top();

    if (ch === "\n") {
      flushCodeSeg();
      if (lineTouchedTemplate) {
        outLines.push({ text: lineBuf, rawTemplate: true });
      } else {
        const trimmed = lineBuf.replace(/[ \t]+$/, "");
        if (trimmed.length > 0) {
          outLines.push({ text: trimmed, rawTemplate: false });
        }
      }
      lineBuf = "";
      lineTouchedTemplate = top().kind === "template";
      continue;
    }

    if (cur.kind === "template") {
      lineTouchedTemplate = true;
      if (ch === "\\") {
        lineBuf += ch;
        if (next && next !== "\n") {
          lineBuf += next;
          i += 1;
        }
        continue;
      }
      if (ch === "`") {
        lineBuf += ch;
        stack.pop();
        continue;
      }
      if (ch === "$" && next === "{") {
        lineBuf += "${";
        i += 1;
        stack.push({ kind: "code", braces: 0 });
        continue;
      }
      lineBuf += ch;
      continue;
    }

    if (cur.kind === "block_comment") {
      lineBuf += ch;
      if (ch === "*" && next === "/") {
        lineBuf += "/";
        i += 1;
        stack.pop();
      }
      continue;
    }

    if (ch === "/" && next === "/") {
      flushCodeSeg();
      const nlIdx = code.indexOf("\n", i);
      if (nlIdx === -1) {
        lineBuf += code.slice(i);
        i = code.length - 1;
      } else {
        lineBuf += code.slice(i, nlIdx);
        i = nlIdx - 1;
      }
      continue;
    }
    if (ch === "/" && next === "*") {
      flushCodeSeg();
      lineBuf += "/*";
      i += 1;
      stack.push({ kind: "block_comment" });
      continue;
    }
    if (ch === "'" || ch === '"') {
      flushCodeSeg();
      const quote = ch;
      lineBuf += ch;
      i += 1;
      while (i < code.length && code[i] !== "\n") {
        const c = code[i];
        lineBuf += c;
        if (c === "\\" && i + 1 < code.length && code[i + 1] !== "\n") {
          i += 1;
          lineBuf += code[i];
        } else if (c === quote) {
          break;
        }
        i += 1;
      }
      if (i < code.length && code[i] === "\n") {
        i -= 1;
      }
      continue;
    }
    if (ch === "`") {
      flushCodeSeg();
      lineBuf += ch;
      lineTouchedTemplate = true;
      stack.push({ kind: "template" });
      continue;
    }
    if (ch === "{") {
      cur.braces += 1;
      codeSeg += ch;
      continue;
    }
    if (ch === "}") {
      if (cur.braces === 0 && stack.length > 1 && stack[stack.length - 2].kind === "template") {
        flushCodeSeg();
        stack.pop();
        lineTouchedTemplate = true;
        lineBuf += ch;
      } else {
        if (cur.braces > 0) cur.braces -= 1;
        codeSeg += ch;
      }
      continue;
    }
    codeSeg += ch;
  }

  flushCodeSeg();
  if (lineBuf.length > 0 || lineTouchedTemplate) {
    const finalText = lineTouchedTemplate ? lineBuf : lineBuf.replace(/[ \t]+$/, "");
    if (lineTouchedTemplate || finalText.length > 0) {
      outLines.push({ text: finalText, rawTemplate: lineTouchedTemplate });
    }
  }

  const rendered = [];
  for (const entry of outLines) {
    if (!entry.rawTemplate && entry.text.startsWith("// --- src/") && rendered.length > 0) {
      rendered.push("");
    }
    rendered.push(entry.text);
  }
  return rendered.join("\n").trim() + "\n";
}

function buildBundle() {
  runMandatoryTsc();

  const allTsFiles = collectTsFiles(SRC_DIR);
  const strippedByFile = new Map();
  for (const file of allTsFiles) {
    const raw = fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n");
    const stripped = stripTypeScriptTypes(raw, { mode: "strip" });
    strippedByFile.set(file, stripped);
  }

  // Topological sort from ENTRY_FILE with cycle detection & named-export validation
  const ordered = [];
  const state = new Map(); // "visiting" | "done"
  const exportsCache = new Map();

  function getExports(file) {
    if (!exportsCache.has(file)) {
      exportsCache.set(file, parseRuntimeExports(strippedByFile.get(file) || ""));
    }
    return exportsCache.get(file);
  }

  function visit(file, stack) {
    const st = state.get(file);
    if (st === "done") return;
    if (st === "visiting") {
      const cycle = [...stack, file]
        .map((f) => path.relative(FRONTEND_DIR, f).replace(/\\/g, "/"))
        .join(" -> ");
      throw new Error(`Circular runtime dependency detected: ${cycle}`);
    }
    state.set(file, "visiting");
    const jsCode = strippedByFile.get(file);
    if (jsCode === undefined) {
      throw new Error(`Missing TypeScript module: ${file}`);
    }
    const imports = parseRuntimeImports(jsCode);
    for (const imp of imports) {
      const target = resolveImportTarget(file, imp.specifier);
      visit(target, [...stack, file]);
      const targetExports = getExports(target);
      for (const sym of imp.named) {
        if (!targetExports.has(sym)) {
          const fromRel = path.relative(FRONTEND_DIR, file).replace(/\\/g, "/");
          const toRel = path.relative(FRONTEND_DIR, target).replace(/\\/g, "/");
          throw new Error(
            `Symbol "${sym}" imported in ${fromRel} is not a runtime export of ${toRel} (use \`import type\` for types/interfaces)`,
          );
        }
      }
    }
    state.set(file, "done");
    ordered.push(file);
  }

  visit(ENTRY_FILE, []);

  const chunks = [
    "// AUTO-GENERATED FILE — DO NOT EDIT DIRECTLY.",
    "// Source: ha-latter/frontend_src/src/ (build via `node ha-latter/frontend_src/build.mjs`).",
  ];

  for (const file of ordered) {
    const rel = path.relative(FRONTEND_DIR, file).replace(/\\/g, "/");
    const body = transformModuleBody(strippedByFile.get(file) || "");
    if (!body) continue;
    chunks.push(`// --- ${rel} ---\n${body}`);
  }

  const combined = compactBundleOutsideTemplates(chunks.join("\n"));

  // Verify the entire generated bundle parses cleanly with V8's ES Module parser
  const parseRes = spawnSync(
    process.execPath,
    ["--input-type=module", "--check"],
    { input: combined, encoding: "utf8" },
  );
  if (parseRes.status !== 0) {
    process.stderr.write(parseRes.stderr || "");
    throw new Error("Generated ESM bundle failed V8 module syntax/collision check");
  }

  return { bundle: combined, moduleCount: ordered.length, totalTsFiles: allTsFiles.length };
}

function runStaticGuardrails(bundleText) {
  const errors = [];
  const allTsFiles = collectTsFiles(SRC_DIR);
  const scanTargets = [
    { label: "custom_components/latter/frontend/latter-studio.js", text: bundleText },
    ...allTsFiles.map((f) => ({
      label: path.relative(path.resolve(FRONTEND_DIR, ".."), f).replace(/\\/g, "/"),
      text: fs.readFileSync(f, "utf8"),
    })),
  ];

  const bannedApiRe = new RegExp(
    "hass" + "Tokens|hass-" + "subpage|CONF_WEB_THEME|renderYamlGenerator|\\b(?:fe" + "tch|call" + "Api)\\s*\\(",
  );
  const bannedTermRe = /\b(household|households|fleet|rooms?)\b/i;
  const bannedWindowAssignRe = new RegExp("\\bwin" + "dow\\.[A-Za-z0-9_]+\\s*=(?!=)");
  const bannedInlineHandlerRe = new RegExp(
    "\\bon" + "click\\s*=|\\bon(?:change|input|keydown|toggle)\\s*=\\s*[\"']",
  );
  const bannedInlineStyleRe = /style="(?!\s*--|\s*\$\{)|\.style\.(?!setProperty\(["']--)|\bstyle\.cssText\b/;

  for (const item of scanTargets) {
    const mApi = item.text.match(bannedApiRe);
    if (mApi) errors.push(`[STUDIO INVARIANT] ${item.label} matched forbidden pattern: ${mApi[0]}`);

    const mTerm = item.text.match(bannedTermRe);
    if (mTerm) errors.push(`[STUDIO TERMINOLOGY] ${item.label} matched banned term: ${mTerm[0]}`);

    const mWin = item.text.match(bannedWindowAssignRe);
    if (mWin) errors.push(`[STUDIO HANDLER BINDINGS] ${item.label} assigns global property: ${mWin[0]}`);

    const mOn = item.text.match(bannedInlineHandlerRe);
    if (mOn) errors.push(`[STUDIO HANDLER BINDINGS] ${item.label} uses inline HTML event attribute: ${mOn[0]}`);

    const mStyle = item.text.match(bannedInlineStyleRe);
    if (mStyle) errors.push(`[STUDIO INLINE STYLES] ${item.label} uses non-token inline style: ${mStyle[0]}`);
  }

  // Default view & tab order checks on bundleText
  const tabDevPos = bundleText.indexOf('id="tab-scope-device"');
  const tabSysPos = bundleText.indexOf('id="tab-scope-system"');
  if (!(tabDevPos >= 0 && tabSysPos > tabDevPos)) {
    errors.push("[STUDIO DEFAULT VIEW] tab-scope-device must appear before tab-scope-system");
  }
  if (!/(?:CURRENT_SCOPE|currentScope|scope)\s*[:=]\s*"device"/.test(bundleText)) {
    errors.push('[STUDIO DEFAULT VIEW] Default scope must initialize to "device"');
  }
  if (!/(?:CURRENT_VIEW_ID|currentViewId|viewId|activeView)\s*[:=]\s*"select_device_prompt"/.test(bundleText)) {
    errors.push('[STUDIO DEFAULT VIEW] Default view must initialize to "select_device_prompt"');
  }
  if (!/(?:_applyRoute|applyRoute)\s*\(/.test(bundleText)) {
    errors.push("[STUDIO DEFAULT VIEW] Bundle must invoke _applyRoute / applyRoute");
  }

  // D-014 two-column layout & heading hierarchy checks across all 12 views
  const twoColumnViews = [
    "system_overview",
    "shared_entities",
    "remotes",
    "system_sync",
    "area_tracking",
    "system_tools",
    "dashboard",
    "home_display",
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

try {
  const { bundle, moduleCount, totalTsFiles } = buildBundle();
  const lineCount = bundle.split("\n").length - 1;

  if (modeTypecheckOnly) {
    process.stdout.write(
      `tsc --noEmit, type-strip & ESM graph verified (${moduleCount}/${totalTsFiles} TypeScript modules, ${lineCount} JS lines).\n`,
    );
    process.exit(0);
  }

  if (modeCheck) {
    if (!fs.existsSync(OUT_FILE)) {
      throw new Error(`Missing output bundle: ${OUT_FILE}`);
    }
    const committedBuf = fs.readFileSync(OUT_FILE);
    if (committedBuf.length >= 3 && committedBuf[0] === 0xef && committedBuf[1] === 0xbb && committedBuf[2] === 0xbf) {
      throw new Error("latter-studio.js must not start with UTF-8 BOM");
    }
    const committed = committedBuf.toString("utf8");
    if (committed !== bundle) {
      throw new Error(
        "custom_components/latter/frontend/latter-studio.js is out of sync with frontend_src/src/ — run `node ha-latter/frontend_src/build.mjs`",
      );
    }
    runStaticGuardrails(bundle);
    process.stdout.write(
      `Studio check PASSED (${moduleCount} modules, ${lineCount} lines, ${Buffer.byteLength(bundle, "utf8")} bytes, tsc --noEmit clean, bundle in sync, 0 guardrail issues).\n`,
    );
    process.exit(0);
  }

  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  fs.writeFileSync(OUT_FILE, Buffer.from(bundle, "utf8"));
  runStaticGuardrails(bundle);
  process.stdout.write(
    `Built custom_components/latter/frontend/latter-studio.js (${moduleCount} modules, ${lineCount} lines, ${Buffer.byteLength(bundle, "utf8")} bytes).\n`,
  );
} catch (err) {
  process.stderr.write(`Studio build error: ${err instanceof Error ? err.message : String(err)}\n`);
  process.exit(1);
}
