/**
 * Deterministic Module-Scoped TypeScript -> ESM Bundler, Lazy MDI Splitter,
 * & i18n Locale Catalog Emitter (`L4`).
 */

import { spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import path from "node:path";
import vm from "node:vm";
import { compactBundleCode } from "./compactor.mjs";
import {
  analyzeAndTransformModule,
  collectSourceModules,
  resolveImportTarget,
} from "./lexer.mjs";

export function runMandatoryTsc(frontendDir) {
  const tscBin = path.join(frontendDir, "node_modules", "typescript", "bin", "tsc");
  if (!fs.existsSync(tscBin)) {
    throw new Error(
      "Missing local TypeScript compiler (`node_modules/typescript/bin/tsc`) — run `npm --prefix frontend_src ci` first",
    );
  }
  const res = spawnSync(
    process.execPath,
    [tscBin, "--noEmit", "-p", path.join(frontendDir, "tsconfig.json")],
    { cwd: frontendDir, encoding: "utf8" },
  );
  if (res.status !== 0) {
    process.stderr.write(res.stdout || "");
    process.stderr.write(res.stderr || "");
    throw new Error("tsc --noEmit failed");
  }
}

export function extractMdiChunkBundle(mdiChunksStrippedJs, mdiCatalogStrippedJs) {
  const declRe = /(export\s+)?const\s+PACKED_MDI_CHUNKS\s*=\s*(\[[\s\S]*?\])\s*;/;
  const match = declRe.exec(mdiChunksStrippedJs);
  if (!match) {
    throw new Error(
      "Could not locate `export const PACKED_MDI_CHUNKS = [...]` in src/mdi-chunks.ts",
    );
  }
  const exportPrefix = match[1] || "";
  const arrayLiteral = match[2];
  const rawMdiModule = [
    "// AUTO-GENERATED FILE — DO NOT EDIT DIRECTLY.",
    "// Source: ha-latter/frontend_src/src/mdi-chunks.ts (build via `node ha-latter/frontend_src/build.mjs`).",
    `export const PACKED_MDI_CHUNKS = ${arrayLiteral};`,
    "//# sourceURL=latter-studio/latter-studio-mdi.js",
  ].join("\n");
  const mdiBundle = compactBundleCode(rawMdiModule);
  const mdiBuf = Buffer.from(mdiBundle, "utf8");
  const mdiDigest = crypto.createHash("sha256").update(mdiBuf).digest("hex").slice(0, 16);

  const rewrittenMdiChunksSource = mdiChunksStrippedJs.replace(
    declRe,
    `${exportPrefix}const PACKED_MDI_CHUNKS = [];`,
  );
  const rewrittenMdiCatalogSource = mdiCatalogStrippedJs.replace(
    /"__LATTER_MDI_CHUNK_URL__"/g,
    JSON.stringify(`./latter-studio-mdi.js?v=${mdiDigest}`),
  );

  if (!rewrittenMdiCatalogSource.includes(`./latter-studio-mdi.js?v=${mdiDigest}`)) {
    throw new Error("Failed to inject hashed MDI chunk URL into src/mdi-catalog.ts");
  }

  return {
    mdiBundle,
    mdiDigest,
    rewrittenMdiChunksSource,
    rewrittenMdiCatalogSource,
  };
}

export function buildEnLocaleJson(enI18nFile) {
  if (!fs.existsSync(enI18nFile)) {
    throw new Error("Missing src/i18n/en.ts");
  }
  const i18nDir = path.dirname(enI18nFile);
  const sandbox = vm.createContext(Object.create(null));
  for (const sliceName of ["en-common.ts", "en-system.ts", "en-devices.ts"]) {
    const slicePath = path.join(i18nDir, sliceName);
    if (!fs.existsSync(slicePath)) continue;
    const rawSlice = fs.readFileSync(slicePath, "utf8").replace(/\r\n/g, "\n");
    const strippedSlice = stripTypeScriptTypes(rawSlice, { mode: "strip" });
    const parsedSlice = analyzeAndTransformModule(strippedSlice);
    vm.runInContext(parsedSlice.body, sandbox, { filename: `src/i18n/${sliceName}` });
  }
  const rawTs = fs.readFileSync(enI18nFile, "utf8").replace(/\r\n/g, "\n");
  const stripped = stripTypeScriptTypes(rawTs, { mode: "strip" });
  const parsed = analyzeAndTransformModule(stripped);
  vm.runInContext(
    `${parsed.body}\n;globalThis.__catalog = buildStudioEnLocaleCatalog();`,
    sandbox,
    { filename: "src/i18n/en.ts" },
  );
  const catalog = sandbox.__catalog;
  if (!catalog || typeof catalog !== "object") {
    throw new Error("buildStudioEnLocaleCatalog() did not return a valid catalog object");
  }
  return JSON.stringify(catalog, null, 2) + "\n";
}

export function verifyEsmSyntax(code, label) {
  const parseRes = spawnSync(process.execPath, ["--input-type=module", "--check"], {
    input: code,
    encoding: "utf8",
  });
  if (parseRes.status !== 0) {
    process.stderr.write(parseRes.stderr || "");
    throw new Error(`Generated ESM bundle (${label}) failed V8 module syntax check`);
  }
}

export function buildBundles(frontendDir) {
  const srcDir = path.join(frontendDir, "src");
  const entryFile = path.join(srcDir, "latter-studio.ts");
  const mdiChunksFile = path.join(srcDir, "mdi-chunks.ts");
  const mdiCatalogFile = path.join(srcDir, "mdi-catalog.ts");
  const enI18nFile = path.join(srcDir, "i18n", "en.ts");

  runMandatoryTsc(frontendDir);

  const allSourceFiles = collectSourceModules(srcDir);
  const strippedByFile = new Map();
  for (const file of allSourceFiles) {
    const raw = fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n");
    const stripped = file.endsWith(".ts")
      ? stripTypeScriptTypes(raw, { mode: "strip" })
      : raw;
    strippedByFile.set(file, stripped);
  }

  const mdiChunksOriginal = strippedByFile.get(mdiChunksFile);
  if (mdiChunksOriginal === undefined) {
    throw new Error("Missing src/mdi-chunks.ts");
  }
  const mdiCatalogOriginal = strippedByFile.get(mdiCatalogFile);
  if (mdiCatalogOriginal === undefined) {
    throw new Error("Missing src/mdi-catalog.ts");
  }
  const {
    mdiBundle,
    mdiDigest,
    rewrittenMdiChunksSource,
    rewrittenMdiCatalogSource,
  } = extractMdiChunkBundle(mdiChunksOriginal, mdiCatalogOriginal);
  strippedByFile.set(mdiChunksFile, rewrittenMdiChunksSource);
  strippedByFile.set(mdiCatalogFile, rewrittenMdiCatalogSource);

  const parsedByFile = new Map();
  for (const [file, code] of strippedByFile.entries()) {
    parsedByFile.set(file, analyzeAndTransformModule(code));
  }

  const exportsCache = new Map();
  function getModuleExports(file, seen = new Set()) {
    if (exportsCache.has(file)) return exportsCache.get(file);
    if (seen.has(file)) return new Set();
    seen.add(file);
    const info = parsedByFile.get(file);
    if (!info) throw new Error(`Missing parsed module: ${file}`);
    const out = new Set();
    for (const le of info.localExports) {
      out.add(le.exported);
    }
    for (const re of info.reexports) {
      const target = resolveImportTarget(frontendDir, file, re.specifier);
      if (re.star) {
        if (re.starAs) {
          out.add(re.starAs);
        } else {
          for (const sym of getModuleExports(target, seen)) {
            if (sym !== "default") out.add(sym);
          }
        }
      } else {
        const targetExp = getModuleExports(target, seen);
        for (const item of re.named) {
          if (!targetExp.has(item.imported)) {
            const fromRel = path.relative(frontendDir, file).replace(/\\/g, "/");
            const toRel = path.relative(frontendDir, target).replace(/\\/g, "/");
            throw new Error(
              `Re-exported symbol "${item.imported}" in ${fromRel} is not a runtime export of ${toRel}`,
            );
          }
          out.add(item.exported);
        }
      }
    }
    exportsCache.set(file, out);
    return out;
  }

  const ordered = [];
  const state = new Map();

  function visit(file, stack) {
    const st = state.get(file);
    if (st === "done") return;
    if (st === "visiting") {
      const cycle = [...stack, file]
        .map((f) => path.relative(frontendDir, f).replace(/\\/g, "/"))
        .join(" -> ");
      throw new Error(`Circular runtime dependency detected: ${cycle}`);
    }
    state.set(file, "visiting");
    const info = parsedByFile.get(file);
    if (!info) {
      throw new Error(`Missing source module: ${file}`);
    }
    for (const imp of info.imports) {
      const target = resolveImportTarget(frontendDir, file, imp.specifier);
      visit(target, [...stack, file]);
      const targetExports = getModuleExports(target);
      for (const sym of imp.named) {
        if (!targetExports.has(sym.imported)) {
          const fromRel = path.relative(frontendDir, file).replace(/\\/g, "/");
          const toRel = path.relative(frontendDir, target).replace(/\\/g, "/");
          throw new Error(
            `Symbol "${sym.imported}" imported in ${fromRel} is not a runtime export of ${toRel} (use \`import type\` for types/interfaces)`,
          );
        }
      }
    }
    for (const re of info.reexports) {
      const target = resolveImportTarget(frontendDir, file, re.specifier);
      visit(target, [...stack, file]);
      getModuleExports(file);
    }
    state.set(file, "done");
    ordered.push(file);
  }

  visit(entryFile, []);

  const relIdOf = (file) => path.relative(frontendDir, file).replace(/\\/g, "/");

  const chunks = [
    "// AUTO-GENERATED FILE — DO NOT EDIT DIRECTLY.",
    "// Source: ha-latter/frontend_src/src/ (build via `node ha-latter/frontend_src/build.mjs`).",
    "const __latterMods = new Map();",
    "const __latterCache = new Map();",
    "function __latterDef(id, factory) { __latterMods.set(id, factory); }",
    "function __latterExp(target, getters) {",
    "  for (const k of Object.keys(getters)) {",
    "    Object.defineProperty(target, k, { enumerable: true, configurable: true, get: getters[k] });",
    "  }",
    "}",
    "function __latterStar(target, src) {",
    "  for (const k of Object.keys(src)) {",
    "    if (k !== \"default\" && !(k in target)) {",
    "      Object.defineProperty(target, k, { enumerable: true, configurable: true, get: () => src[k] });",
    "    }",
    "  }",
    "}",
    "function __latterReq(id) {",
    "  let exp = __latterCache.get(id);",
    "  if (exp !== undefined) return exp;",
    "  const factory = __latterMods.get(id);",
    "  if (!factory) throw new Error(`Missing Studio module: ${id}`);",
    "  exp = Object.create(null);",
    "  __latterCache.set(id, exp);",
    "  factory(exp, __latterReq);",
    "  return exp;",
    "}",
  ];

  for (const file of ordered) {
    const rel = relIdOf(file);
    const info = parsedByFile.get(file);
    const lines = [];
    let modSeq = 0;

    for (const imp of info.imports) {
      const targetRel = relIdOf(resolveImportTarget(frontendDir, file, imp.specifier));
      const reqExpr = `__req(${JSON.stringify(targetRel)})`;
      if (!imp.defaultIdent && !imp.namespaceIdent && imp.named.length === 0) {
        lines.push(`${reqExpr};`);
        continue;
      }
      if (imp.namespaceIdent && !imp.defaultIdent) {
        lines.push(`const ${imp.namespaceIdent} = ${reqExpr};`);
        continue;
      }
      if (!imp.defaultIdent && imp.named.length > 0) {
        const bindings = imp.named
          .map((n) => (n.imported === n.local ? n.imported : `${n.imported}: ${n.local}`))
          .join(", ");
        lines.push(`const { ${bindings} } = ${reqExpr};`);
        continue;
      }
      const tmp = `__m${modSeq++}`;
      lines.push(`const ${tmp} = ${reqExpr};`);
      if (imp.defaultIdent) {
        lines.push(`const ${imp.defaultIdent} = ${tmp}.default;`);
      }
      if (imp.namespaceIdent) {
        lines.push(`const ${imp.namespaceIdent} = ${tmp};`);
      }
      if (imp.named.length > 0) {
        const bindings = imp.named
          .map((n) => (n.imported === n.local ? n.imported : `${n.imported}: ${n.local}`))
          .join(", ");
        lines.push(`const { ${bindings} } = ${tmp};`);
      }
    }

    const exportGetterPairs = [];
    for (const re of info.reexports) {
      const targetRel = relIdOf(resolveImportTarget(frontendDir, file, re.specifier));
      const reqExpr = `__req(${JSON.stringify(targetRel)})`;
      if (re.star) {
        if (re.starAs) {
          const tmp = `__r${modSeq++}`;
          lines.push(`const ${tmp} = ${reqExpr};`);
          exportGetterPairs.push(`${re.starAs}: () => ${tmp}`);
        } else {
          lines.push(`__latterStar(__exports, ${reqExpr});`);
        }
      } else if (re.named.length > 0) {
        const tmp = `__r${modSeq++}`;
        lines.push(`const ${tmp} = ${reqExpr};`);
        for (const n of re.named) {
          exportGetterPairs.push(`${n.exported}: () => ${tmp}.${n.imported}`);
        }
      }
    }

    if (info.body) {
      lines.push(info.body);
    }

    for (const le of info.localExports) {
      exportGetterPairs.push(`${le.exported}: () => ${le.local}`);
    }

    if (exportGetterPairs.length > 0) {
      lines.push(`__latterExp(__exports, { ${exportGetterPairs.join(", ")} });`);
    }
    lines.push(`//# sourceURL=latter-studio/${rel}`);

    chunks.push(`__latterDef(${JSON.stringify(rel)}, (__exports, __req) => {\n${lines.join("\n")}\n});`);
  }

  const entryRel = relIdOf(entryFile);
  const entryExports = [...getModuleExports(entryFile)].sort();
  chunks.push(`const __latterEntry = __latterReq(${JSON.stringify(entryRel)});`);
  for (const sym of entryExports) {
    chunks.push(`export const ${sym} = __latterEntry.${sym};`);
  }

  const combined = compactBundleCode(chunks.join("\n"));

  verifyEsmSyntax(combined, "latter-studio.js");
  verifyEsmSyntax(mdiBundle, "latter-studio-mdi.js");

  const enLocaleJson = buildEnLocaleJson(enI18nFile);

  return {
    bundle: combined,
    mdiBundle,
    mdiDigest,
    enLocaleJson,
    moduleCount: ordered.length,
    totalSourceFiles: allSourceFiles.length,
  };
}
