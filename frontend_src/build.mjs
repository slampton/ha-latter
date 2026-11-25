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

const REGEX_PRECEDING_KEYWORDS = new Set([
  "return",
  "case",
  "throw",
  "in",
  "of",
  "typeof",
  "void",
  "delete",
  "await",
  "yield",
  "new",
  "else",
  "do",
  "instanceof",
]);

const RAW_HTML_TAGS = new Set(["pre", "code", "textarea", "script", "style"]);

function isIdentStart(ch) {
  const c = ch.charCodeAt(0);
  return (c >= 65 && c <= 90) || (c >= 97 && c <= 122) || c === 95 || c === 36;
}

function isIdentChar(ch) {
  const c = ch.charCodeAt(0);
  return isIdentStart(ch) || (c >= 48 && c <= 57);
}

function isAsciiWs(ch) {
  return ch === " " || ch === "\t" || ch === "\n" || ch === "\r" || ch === "\f";
}

/**
 * Minifies CSS template quasi chunks while preserving quoted CSS strings,
 * descendant `:pseudo` selectors, `@media ... and (...)` spacing, and `calc(...)` operators.
 */
export function minifyCssTemplateQuasis(quasis) {
  let inComment = false;
  let quote = "";
  const outQuasis = [];

  for (let qIdx = 0; qIdx < quasis.length; qIdx += 1) {
    const src = quasis[qIdx];
    const n = src.length;
    let out = "";
    let pendingWs = false;
    let i = 0;

    while (i < n) {
      const ch = src[i];
      if (inComment) {
        if (ch === "*" && src[i + 1] === "/") {
          inComment = false;
          i += 2;
        } else {
          i += 1;
        }
        continue;
      }

      if (quote) {
        out += ch;
        if (ch === "\\" && i + 1 < n) {
          out += src[i + 1];
          i += 2;
          continue;
        }
        if (ch === quote) {
          quote = "";
        }
        i += 1;
        continue;
      }

      if (ch === "/" && src[i + 1] === "*") {
        inComment = true;
        i += 2;
        continue;
      }

      if (ch === '"' || ch === "'") {
        if (pendingWs) {
          const prev = out.length > 0 ? out[out.length - 1] : "";
          if (prev && prev !== "{" && prev !== "}" && prev !== ";" && prev !== "," && prev !== ":" && prev !== "(") {
            out += " ";
          }
          pendingWs = false;
        }
        quote = ch;
        out += ch;
        i += 1;
        continue;
      }

      if (isAsciiWs(ch)) {
        pendingWs = true;
        i += 1;
        continue;
      }

      if (ch === "}") {
        if (out.endsWith(";")) {
          out = out.slice(0, -1);
        }
        pendingWs = false;
        out += "}";
        i += 1;
        continue;
      }

      if (ch === "{" || ch === ";" || ch === "," || ch === ")") {
        pendingWs = false;
        out += ch;
        i += 1;
        continue;
      }

      if (pendingWs) {
        const prev = out.length > 0 ? out[out.length - 1] : "";
        const atVeryStart = qIdx === 0 && out.length === 0;
        if (
          !atVeryStart &&
          prev !== "{" &&
          prev !== "}" &&
          prev !== ";" &&
          prev !== "," &&
          prev !== ":" &&
          prev !== "("
        ) {
          out += " ";
        }
        pendingWs = false;
      }

      out += ch;
      i += 1;
    }

    if (pendingWs && qIdx < quasis.length - 1) {
      const prev = out.length > 0 ? out[out.length - 1] : "";
      if (prev && prev !== "{" && prev !== "}" && prev !== ";" && prev !== "," && prev !== ":" && prev !== "(") {
        out += " ";
      }
    }

    outQuasis.push(out);
  }

  return outQuasis;
}

/**
 * Minifies HTML template quasi chunks while preserving quoted attributes, `<pre>`/`<code>`/
 * `<textarea>` content, HTML comments, inline text spacing across `${...}`, and unquoted `/>` safety.
 */
export function minifyHtmlTemplateQuasis(quasis) {
  let inTag = false;
  let inComment = false;
  let attrQuote = "";
  let rawTagDepth = 0;
  let currentTagName = "";
  let currentTagClosing = false;
  let readingTagName = false;
  const outQuasis = [];

  for (let qIdx = 0; qIdx < quasis.length; qIdx += 1) {
    const src = quasis[qIdx];
    const n = src.length;
    let out = "";
    let i = 0;

    while (i < n) {
      if (inComment) {
        const endIdx = src.indexOf("-->", i);
        if (endIdx < 0) {
          out += src.slice(i);
          i = n;
        } else {
          out += src.slice(i, endIdx + 3);
          i = endIdx + 3;
          inComment = false;
        }
        continue;
      }

      if (inTag) {
        const ch = src[i];
        if (attrQuote) {
          out += ch;
          if (ch === attrQuote) {
            attrQuote = "";
          }
          i += 1;
          continue;
        }

        if (readingTagName) {
          if (ch === "/" && currentTagName.length === 0 && !currentTagClosing) {
            currentTagClosing = true;
            out += ch;
            i += 1;
            continue;
          }
          if ((ch >= "a" && ch <= "z") || (ch >= "A" && ch <= "Z") || (ch >= "0" && ch <= "9") || ch === "-") {
            currentTagName += ch.toLowerCase();
            out += ch;
            i += 1;
            continue;
          }
          readingTagName = false;
        }

        if (ch === '"' || ch === "'") {
          attrQuote = ch;
          out += ch;
          i += 1;
          continue;
        }

        if (isAsciiWs(ch)) {
          const wsStart = i;
          while (i < n && isAsciiWs(src[i])) i += 1;
          const nextCh = i < n ? src[i] : "";
          const prevCh = out.length > 0 ? out[out.length - 1] : "";
          // Strip whitespace directly before `>` (end of opening/closing tag).
          if (nextCh === ">") {
            continue;
          }
          // Strip whitespace before `/>` ONLY when safely preceded by a quote or non-expr token.
          if (
            nextCh === "/" &&
            src[i + 1] === ">" &&
            wsStart > 0 &&
            (prevCh === '"' || prevCh === "'")
          ) {
            continue;
          }
          if (prevCh === "=" || prevCh === "<") {
            continue;
          }
          out += " ";
          continue;
        }

        if (ch === ">") {
          const selfClosing = out.endsWith("/");
          out += ">";
          inTag = false;
          if (RAW_HTML_TAGS.has(currentTagName)) {
            if (currentTagClosing) {
              rawTagDepth = Math.max(0, rawTagDepth - 1);
            } else if (!selfClosing) {
              rawTagDepth += 1;
            }
          }
          currentTagName = "";
          currentTagClosing = false;
          i += 1;
          continue;
        }

        out += ch;
        i += 1;
        continue;
      }

      // Outside tags (text / raw content)
      if (src.startsWith("<!--", i)) {
        inComment = true;
        out += "<!--";
        i += 4;
        continue;
      }

      const ch = src[i];
      if (ch === "<") {
        const next = src[i + 1] || "";
        if (
          (next >= "a" && next <= "z") ||
          (next >= "A" && next <= "Z") ||
          next === "/" ||
          next === "!"
        ) {
          inTag = true;
          readingTagName = next !== "!";
          currentTagName = "";
          currentTagClosing = false;
          out += "<";
          i += 1;
          continue;
        }
      }

      if (rawTagDepth > 0) {
        out += ch;
        i += 1;
        continue;
      }

      if (isAsciiWs(ch)) {
        const wsStart = i;
        let hasNewline = false;
        while (i < n && isAsciiWs(src[i])) {
          if (src[i] === "\n" || src[i] === "\r") hasNewline = true;
          i += 1;
        }
        const atFirstQuasiStart = qIdx === 0 && wsStart === 0;
        const atLastQuasiEnd = qIdx === quasis.length - 1 && i === n;
        if (atFirstQuasiStart || atLastQuasiEnd) {
          continue;
        }
        const prevCh = out.length > 0 ? out[out.length - 1] : "";
        const nextCh = i < n ? src[i] : "";
        // Strip multi-line indentation strictly between two adjacent HTML tags (`>\n  <`).
        if (hasNewline && prevCh === ">" && nextCh === "<") {
          continue;
        }
        out += " ";
        continue;
      }

      out += ch;
      i += 1;
    }

    outQuasis.push(out);
  }

  return outQuasis;
}

/**
 * Lexer-safe scanner that minifies ONLY `html\`...\`` and `css\`...\`` tagged template
 * literals in TypeScript/JavaScript source while leaving strings, comments, regexes,
 * untagged template literals, and `${...}` expressions intact.
 */
export function minifyLitTemplatesInSource(source) {
  const n = source.length;

  function scanRange(startIdx, stopOnClosingBrace) {
    let i = startIdx;
    let out = "";
    let braceDepth = 0;
    let lastSigType = "other"; // "expr_end" | "other"
    let lastWord = "";
    let lastSigChar = "";

    while (i < n) {
      const ch = source[i];

      if (stopOnClosingBrace && ch === "}" && braceDepth === 0) {
        return { text: out, nextIdx: i };
      }

      // Line comment
      if (ch === "/" && source[i + 1] === "/") {
        const nl = source.indexOf("\n", i + 2);
        const end = nl < 0 ? n : nl + 1;
        out += source.slice(i, end);
        i = end;
        continue;
      }

      // Block comment
      if (ch === "/" && source[i + 1] === "*") {
        const endIdx = source.indexOf("*/", i + 2);
        const end = endIdx < 0 ? n : endIdx + 2;
        out += source.slice(i, end);
        i = end;
        continue;
      }

      // Single or double quoted string
      if (ch === "'" || ch === '"') {
        const quote = ch;
        let j = i + 1;
        while (j < n) {
          if (source[j] === "\\") {
            j += 2;
            continue;
          }
          if (source[j] === quote) {
            j += 1;
            break;
          }
          j += 1;
        }
        out += source.slice(i, j);
        i = j;
        lastSigType = "expr_end";
        lastWord = "";
        lastSigChar = quote;
        continue;
      }

      // Regex literal vs division
      if (ch === "/") {
        const canBeRegex =
          lastSigType !== "expr_end" || REGEX_PRECEDING_KEYWORDS.has(lastWord);
        if (canBeRegex) {
          let j = i + 1;
          let inClass = false;
          while (j < n) {
            const rc = source[j];
            if (rc === "\\") {
              j += 2;
              continue;
            }
            if (rc === "[") {
              inClass = true;
              j += 1;
              continue;
            }
            if (rc === "]") {
              inClass = false;
              j += 1;
              continue;
            }
            if (!inClass && rc === "/") {
              j += 1;
              while (j < n && isIdentChar(source[j])) j += 1;
              break;
            }
            if (rc === "\n" || rc === "\r") {
              break;
            }
            j += 1;
          }
          out += source.slice(i, j);
          i = j;
          lastSigType = "expr_end";
          lastWord = "";
          lastSigChar = "/";
          continue;
        }
        out += "/";
        i += 1;
        lastSigType = "other";
        lastWord = "";
        lastSigChar = "/";
        continue;
      }

      // Identifier (detect `html` / `css` tag immediately before backtick)
      if (isIdentStart(ch)) {
        let j = i + 1;
        while (j < n && isIdentChar(source[j])) j += 1;
        const ident = source.slice(i, j);
        const isLitTag =
          (ident === "html" || ident === "css") &&
          lastSigChar !== "." &&
          source[j] === "`";
        out += ident;
        i = j;
        if (isLitTag) {
          const tpl = scanTemplate(j, ident);
          out += tpl.text;
          i = tpl.nextIdx;
          lastSigType = "expr_end";
          lastWord = "";
          lastSigChar = "`";
        } else {
          lastSigType = "expr_end";
          lastWord = ident;
          lastSigChar = ident[ident.length - 1] || "";
        }
        continue;
      }

      // Untagged or other template literal
      if (ch === "`") {
        const tpl = scanTemplate(i, null);
        out += tpl.text;
        i = tpl.nextIdx;
        lastSigType = "expr_end";
        lastWord = "";
        lastSigChar = "`";
        continue;
      }

      if (ch === "{") {
        braceDepth += 1;
        out += ch;
        i += 1;
        lastSigType = "other";
        lastWord = "";
        lastSigChar = ch;
        continue;
      }

      if (ch === "}") {
        braceDepth = Math.max(0, braceDepth - 1);
        out += ch;
        i += 1;
        lastSigType = "expr_end";
        lastWord = "";
        lastSigChar = ch;
        continue;
      }

      if (isAsciiWs(ch)) {
        out += ch;
        i += 1;
        continue;
      }

      if (ch >= "0" && ch <= "9") {
        let j = i + 1;
        while (j < n && (isIdentChar(source[j]) || source[j] === ".")) j += 1;
        out += source.slice(i, j);
        i = j;
        lastSigType = "expr_end";
        lastWord = "";
        lastSigChar = "0";
        continue;
      }

      out += ch;
      i += 1;
      lastWord = "";
      lastSigChar = ch;
      lastSigType = ch === ")" || ch === "]" ? "expr_end" : "other";
    }

    return { text: out, nextIdx: i };
  }

  function scanTemplate(backtickIdx, tagName) {
    const quasis = [];
    const exprs = [];
    let i = backtickIdx + 1;
    let quasiStart = i;

    while (i < n) {
      const ch = source[i];
      if (ch === "\\") {
        i += 2;
        continue;
      }
      if (ch === "`") {
        quasis.push(source.slice(quasiStart, i));
        i += 1;
        break;
      }
      if (ch === "$" && source[i + 1] === "{") {
        quasis.push(source.slice(quasiStart, i));
        const expr = scanRange(i + 2, true);
        exprs.push(expr.text);
        i = expr.nextIdx < n && source[expr.nextIdx] === "}" ? expr.nextIdx + 1 : expr.nextIdx;
        quasiStart = i;
        continue;
      }
      i += 1;
    }

    const finalQuasis =
      tagName === "css"
        ? minifyCssTemplateQuasis(quasis)
        : tagName === "html"
          ? minifyHtmlTemplateQuasis(quasis)
          : quasis;

    let rebuilt = "`";
    for (let k = 0; k < finalQuasis.length; k += 1) {
      rebuilt += finalQuasis[k];
      if (k < exprs.length) {
        rebuilt += `\${${exprs[k]}}`;
      }
    }
    rebuilt += "`";
    return { text: rebuilt, nextIdx: i };
  }

  return scanRange(0, false).text;
}

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
          contents: `export const MDI_TOTAL_ICON_COUNT = ${mdiTotalIconCount};\nexport const PACKED_MDI_CHUNKS = [];\nexport const MDI_SEARCH_SYNONYMS = {};\n`,
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

  const srcDirNorm = normalizeFsPath(path.join(frontendDir, "src"));
  const litTemplateMinifyPlugin = {
    name: "latter-minify-lit-templates",
    setup(build) {
      build.onLoad({ filter: /\.ts$/ }, (args) => {
        const norm = normalizeFsPath(args.path);
        if (!norm.startsWith(srcDirNorm)) return null;
        if (norm === mdiChunksNorm || norm === mdiCatalogNorm) return null;
        const raw = fs.readFileSync(args.path, "utf8");
        if (!raw.includes("html`") && !raw.includes("css`")) {
          return null;
        }
        return {
          contents: minifyLitTemplatesInSource(raw),
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
    plugins: [lazyMdiPlugin, litTemplateMinifyPlugin],
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

const isMainCli =
  Boolean(process.argv[1]) && normalizeFsPath(process.argv[1]) === normalizeFsPath(__filename);

if (isMainCli) {
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
}
