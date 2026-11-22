#!/usr/bin/env node
/**
 * Latter Studio Build CLI (`D-024`, `D-061`, `D-062`, `D-078`).
 *
 * Orchestrates `tsc --noEmit`, stock `esbuild` bundling (`latter-studio.js` + lazy
 * `latter-studio-mdi.js`), deterministic `.gz`/`.br` precompression (`build/assets.mjs`),
 * native Node 24 TypeScript `studio/locales/en.json` emission, V8 ESM syntax verification,
 * and coarse Studio DAG/UI guardrails (`build/guardrails.mjs`):
 *
 *   node build.mjs              -> Build bundles + `.gz`/`.br` + `en.json` and run guardrails
 *   node build.mjs --typecheck  -> Run `tsc --noEmit` + in-memory esbuild + V8 syntax + guardrails
 *   node build.mjs --check      -> Run `--typecheck` + verify committed bundles, `.gz`/`.br`, and `en.json`
 */

import { spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import * as esbuild from "esbuild";
import {
  assertExactUtf8File,
  verifyCompressedAssets,
  writeCompressedAssets,
} from "./build/assets.mjs";
import { runStaticGuardrails } from "./build/guardrails.mjs";
import "./src/lib/node-ts-loader.mjs";

const __filename = fileURLToPath(import.meta.url);
const FRONTEND_DIR = path.dirname(__filename);

const FRONTEND_OUT_DIR = path.resolve(
  FRONTEND_DIR,
  "..",
  "custom_components",
  "latter",
  "frontend",
);
const OUT_FILE = path.join(FRONTEND_OUT_DIR, "latter-studio.js");
const OUT_MDI_FILE = path.join(FRONTEND_OUT_DIR, "latter-studio-mdi.js");
const OUT_EN_JSON_FILE = path.resolve(
  FRONTEND_DIR,
  "..",
  "custom_components",
  "latter",
  "studio",
  "locales",
  "en.json",
);

const AUTO_GEN_BANNER = "// AUTO-GENERATED FILE — DO NOT EDIT DIRECTLY.";

function normalizeFsPath(p) {
  const resolved = path.resolve(p);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

function runMandatoryTsc(frontendDir) {
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

function verifyEsmSyntax(code, label) {
  const parseRes = spawnSync(process.execPath, ["--input-type=module", "--check"], {
    input: code,
    encoding: "utf8",
  });
  if (parseRes.status !== 0) {
    process.stderr.write(parseRes.stderr || "");
    throw new Error(`Generated ESM bundle (${label}) failed V8 module syntax check`);
  }
}

async function buildEnLocaleJson(frontendDir) {
  const enI18nFile = path.join(frontendDir, "src", "i18n", "en.ts");
  if (!fs.existsSync(enI18nFile)) {
    throw new Error("Missing src/i18n/en.ts");
  }
  const mod = await import(pathToFileURL(enI18nFile).href);
  if (typeof mod.buildStudioEnLocaleCatalog !== "function") {
    throw new Error("src/i18n/en.ts does not export buildStudioEnLocaleCatalog()");
  }
  const catalog = mod.buildStudioEnLocaleCatalog();
  if (!catalog || typeof catalog !== "object") {
    throw new Error("buildStudioEnLocaleCatalog() did not return a valid catalog object");
  }
  return JSON.stringify(catalog, null, 2) + "\n";
}

async function buildBundles(frontendDir) {
  runMandatoryTsc(frontendDir);

  const mdiChunksFile = path.join(frontendDir, "src", "mdi-chunks.ts");
  const mdiCatalogFile = path.join(frontendDir, "src", "mdi-catalog.ts");
  const mdiChunksRaw = fs.readFileSync(mdiChunksFile, "utf8");
  const countMatch = /\bexport\s+const\s+MDI_TOTAL_ICON_COUNT\s*=\s*(\d+)\s*;/.exec(mdiChunksRaw);
  if (!countMatch) {
    throw new Error(
      "Could not locate `export const MDI_TOTAL_ICON_COUNT = <N>;` in src/mdi-chunks.ts",
    );
  }
  const mdiTotalIconCount = Number(countMatch[1]);

  // 1. Build lazy MDI catalog chunk (`latter-studio-mdi.js`)
  const mdiResult = await esbuild.build({
    absWorkingDir: frontendDir,
    entryPoints: ["src/mdi-chunks.ts"],
    bundle: true,
    write: false,
    format: "esm",
    target: "es2022",
    minify: true,
    banner: { js: AUTO_GEN_BANNER },
  });
  const mdiBundle = mdiResult.outputFiles[0]?.text;
  if (!mdiBundle) {
    throw new Error("esbuild produced empty output for src/mdi-chunks.ts");
  }
  const mdiBuf = Buffer.from(mdiBundle, "utf8");
  const mdiDigest = crypto.createHash("sha256").update(mdiBuf).digest("hex").slice(0, 16);
  const mdiChunkUrl = `./latter-studio-mdi.js?v=${mdiDigest}`;

  // 2. Build core Studio bundle (`latter-studio.js`) with stubbed lazy MDI chunk & hashed URL injection
  const mdiChunksNorm = normalizeFsPath(mdiChunksFile);
  const mdiCatalogNorm = normalizeFsPath(mdiCatalogFile);
  const lazyMdiPlugin = {
    name: "latter-lazy-mdi",
    setup(build) {
      build.onResolve({ filter: /^\.\/latter-studio-mdi\.js(?:\?.*)?$/ }, (args) => ({
        path: args.path,
        external: true,
      }));
      build.onLoad({ filter: /mdi-chunks\.ts$/ }, (args) => {
        if (normalizeFsPath(args.path) !== mdiChunksNorm) return null;
        return {
          contents: `export const MDI_TOTAL_ICON_COUNT = ${mdiTotalIconCount};\nexport const PACKED_MDI_CHUNKS = [];\n`,
          loader: "ts",
        };
      });
      build.onLoad({ filter: /mdi-catalog\.ts$/ }, (args) => {
        if (normalizeFsPath(args.path) !== mdiCatalogNorm) return null;
        const raw = fs.readFileSync(args.path, "utf8");
        const rewritten = raw.replace(
          /"__LATTER_MDI_CHUNK_URL__"/g,
          JSON.stringify(mdiChunkUrl),
        );
        if (!rewritten.includes(mdiChunkUrl)) {
          throw new Error("Failed to inject hashed MDI chunk URL into src/mdi-catalog.ts");
        }
        return {
          contents: rewritten,
          loader: "ts",
        };
      });
    },
  };

  const coreResult = await esbuild.build({
    absWorkingDir: frontendDir,
    entryPoints: ["src/latter-studio.ts"],
    bundle: true,
    write: false,
    format: "esm",
    target: "es2022",
    minify: true,
    metafile: true,
    banner: { js: AUTO_GEN_BANNER },
    plugins: [lazyMdiPlugin],
  });
  const bundle = coreResult.outputFiles[0]?.text;
  if (!bundle) {
    throw new Error("esbuild produced empty output for src/latter-studio.ts");
  }
  const bundleBuf = Buffer.from(bundle, "utf8");
  const metafile = coreResult.metafile;
  const srcModuleCount = Object.keys(metafile?.inputs || {}).filter((k) =>
    k.replace(/\\/g, "/").startsWith("src/"),
  ).length;

  // 3. Verify generated ESM syntax under V8 and emit `studio/locales/en.json`
  verifyEsmSyntax(bundle, "latter-studio.js");
  verifyEsmSyntax(mdiBundle, "latter-studio-mdi.js");
  const enLocaleJson = await buildEnLocaleJson(frontendDir);

  return {
    bundle,
    bundleBuf,
    mdiBundle,
    mdiBuf,
    mdiDigest,
    enLocaleJson,
    metafile,
    srcModuleCount,
  };
}

const args = new Set(process.argv.slice(2));
const modeCheck = args.has("--check");
const modeTypecheckOnly = args.has("--typecheck");

try {
  const {
    bundle,
    bundleBuf,
    mdiBundle,
    mdiBuf,
    mdiDigest,
    enLocaleJson,
    metafile,
    srcModuleCount,
  } = await buildBundles(FRONTEND_DIR);

  if (modeTypecheckOnly && !modeCheck) {
    runStaticGuardrails(FRONTEND_DIR, metafile, bundle, mdiBundle);
    process.stdout.write(
      `tsc --noEmit, zero-cycle DAG & guardrails verified (${srcModuleCount} src modules, ${bundleBuf.length} B core + ${mdiBuf.length} B lazy MDI [v=${mdiDigest}]).\n`,
    );
    process.exit(0);
  }

  if (modeCheck) {
    assertExactUtf8File(OUT_FILE, bundle, "custom_components/latter/frontend/latter-studio.js");
    assertExactUtf8File(
      OUT_MDI_FILE,
      mdiBundle,
      "custom_components/latter/frontend/latter-studio-mdi.js",
    );
    assertExactUtf8File(
      OUT_EN_JSON_FILE,
      enLocaleJson,
      "custom_components/latter/studio/locales/en.json",
    );
    verifyCompressedAssets(OUT_FILE, bundleBuf, "latter-studio.js");
    verifyCompressedAssets(OUT_MDI_FILE, mdiBuf, "latter-studio-mdi.js");
    runStaticGuardrails(FRONTEND_DIR, metafile, bundle, mdiBundle);
    process.stdout.write(
      `Studio check PASSED (${srcModuleCount} src modules, ${bundleBuf.length} B core + ${mdiBuf.length} B lazy MDI [v=${mdiDigest}], .gz/.br + locales/en.json in sync, 0 DAG/UI guardrail issues).\n`,
    );
    process.exit(0);
  }

  fs.mkdirSync(FRONTEND_OUT_DIR, { recursive: true });
  fs.mkdirSync(path.dirname(OUT_EN_JSON_FILE), { recursive: true });
  fs.writeFileSync(OUT_FILE, bundleBuf);
  fs.writeFileSync(OUT_MDI_FILE, mdiBuf);
  fs.writeFileSync(OUT_EN_JSON_FILE, Buffer.from(enLocaleJson, "utf8"));
  writeCompressedAssets(OUT_FILE, bundleBuf);
  writeCompressedAssets(OUT_MDI_FILE, mdiBuf);
  runStaticGuardrails(FRONTEND_DIR, metafile, bundle, mdiBundle);
  process.stdout.write(
    `Built Latter Studio (${srcModuleCount} src modules: ${bundleBuf.length} B core + ${mdiBuf.length} B lazy MDI [v=${mdiDigest}], .gz/.br + studio/locales/en.json synced).\n`,
  );
} catch (err) {
  process.stderr.write(
    `Studio build error: ${err instanceof Error ? err.message : String(err)}\n`,
  );
  process.exit(1);
}
