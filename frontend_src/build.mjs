#!/usr/bin/env node
/**
 * Latter Studio Build CLI (`L4`, `D-024`, `D-061`, `D-062`).
 *
 * Orchestrates `frontend_src/build/{lexer,compactor,bundler,assets,guardrails}.mjs`:
 *   node build.mjs              -> Run `tsc --noEmit`, bundle `latter-studio.js` + `latter-studio-mdi.js`
 *                                  + `.gz`/`.br` + `studio/locales/en.json`, and run Studio DAG/UI guardrails
 *   node build.mjs --typecheck  -> Run `tsc --noEmit` + TS strip + module-scoped ESM graph + DAG/UI guardrails
 *   node build.mjs --check      -> Run `--typecheck` + verify committed bundles, `.gz`/`.br`, and `en.json`
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  assertExactUtf8File,
  verifyCompressedAssets,
  writeCompressedAssets,
} from "./build/assets.mjs";
import { buildBundles } from "./build/bundler.mjs";
import { runStaticGuardrails } from "./build/guardrails.mjs";

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

const args = new Set(process.argv.slice(2));
const modeCheck = args.has("--check");
const modeTypecheckOnly = args.has("--typecheck");

try {
  const { bundle, mdiBundle, mdiDigest, enLocaleJson, moduleCount, totalSourceFiles } =
    buildBundles(FRONTEND_DIR);
  const lineCount = bundle.split("\n").length - 1;
  const bundleBuf = Buffer.from(bundle, "utf8");
  const mdiBuf = Buffer.from(mdiBundle, "utf8");

  if (modeTypecheckOnly && !modeCheck) {
    runStaticGuardrails(FRONTEND_DIR, bundle, mdiBundle);
    process.stdout.write(
      `tsc --noEmit, zero-cycle L0-L4 DAG & guardrails verified (${moduleCount}/${totalSourceFiles} modules, ${lineCount} JS lines, MDI chunk v=${mdiDigest}).\n`,
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
    runStaticGuardrails(FRONTEND_DIR, bundle, mdiBundle);
    process.stdout.write(
      `Studio check PASSED (${moduleCount} modules, ${bundleBuf.length} B core + ${mdiBuf.length} B lazy MDI [v=${mdiDigest}], .gz/.br + locales/en.json in sync, 0 DAG/UI guardrail issues).\n`,
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
  runStaticGuardrails(FRONTEND_DIR, bundle, mdiBundle);
  process.stdout.write(
    `Built Latter Studio (${moduleCount} modules: ${bundleBuf.length} B core + ${mdiBuf.length} B lazy MDI [v=${mdiDigest}], .gz/.br + studio/locales/en.json synced).\n`,
  );
} catch (err) {
  process.stderr.write(
    `Studio build error: ${err instanceof Error ? err.message : String(err)}\n`,
  );
  process.exit(1);
}
