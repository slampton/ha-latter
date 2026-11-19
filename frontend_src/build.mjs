#!/usr/bin/env node
/**
 * Deterministic Module-Scoped TypeScript -> ESM Bundler, Lazy MDI Splitter,
 * i18n Locale Sync, & Verifier for Latter Studio (`D-024`, `D-061`, `D-062`).
 *
 * Modes:
 *   node build.mjs              -> Run `tsc --noEmit`, bundle `latter-studio.js` + `latter-studio-mdi.js`
 *                                  + `.gz`/`.br` + `studio/locales/en.json`, and run Studio guardrails
 *   node build.mjs --typecheck  -> Run `tsc --noEmit` + TS strip + module-scoped ESM graph & V8 parse check
 *   node build.mjs --check      -> Run `--typecheck` + verify committed bundles, `.gz`/`.br`, and `en.json`
 */

import { spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import zlib from "node:zlib";

const __filename = fileURLToPath(import.meta.url);
const FRONTEND_DIR = path.dirname(__filename);
const SRC_DIR = path.join(FRONTEND_DIR, "src");
const ENTRY_FILE = path.join(SRC_DIR, "latter-studio.ts");
const MDI_CATALOG_FILE = path.join(SRC_DIR, "mdi-catalog.ts");
const EN_I18N_FILE = path.join(SRC_DIR, "i18n", "en.ts");

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

function collectSourceModules(dir) {
  const out = [];
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) {
      out.push(...collectSourceModules(full));
    } else if (
      ent.isFile() &&
      ((ent.name.endsWith(".ts") && !ent.name.endsWith(".d.ts")) || ent.name.endsWith(".js"))
    ) {
      out.push(full);
    }
  }
  return out.sort((a, b) => a.localeCompare(b));
}

function runMandatoryTsc() {
  const tscBin = path.join(FRONTEND_DIR, "node_modules", "typescript", "bin", "tsc");
  if (!fs.existsSync(tscBin)) {
    throw new Error(
      "Missing local TypeScript compiler (`node_modules/typescript/bin/tsc`) — run `npm --prefix frontend_src ci` first",
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
  candidates.push(
    rawTarget,
    rawTarget + ".ts",
    rawTarget + ".js",
    path.join(rawTarget, "index.ts"),
    path.join(rawTarget, "index.js"),
  );
  for (const c of candidates) {
    if (fs.existsSync(c) && fs.statSync(c).isFile() && !c.endsWith(".d.ts")) {
      return c;
    }
  }
  throw new Error(
    `Cannot resolve import "${specifier}" from ${path.relative(FRONTEND_DIR, fromFile)}`,
  );
}

function isIdentStart(ch) {
  return (
    (ch >= "A" && ch <= "Z") ||
    (ch >= "a" && ch <= "z") ||
    ch === "_" ||
    ch === "$"
  );
}

function isIdentPart(ch) {
  return isIdentStart(ch) || (ch >= "0" && ch <= "9");
}

function skipJsTrivia(code, idx) {
  let i = idx;
  while (i < code.length) {
    const ch = code[i];
    const next = i + 1 < code.length ? code[i + 1] : "";
    if (ch === " " || ch === "\t" || ch === "\r" || ch === "\n") {
      i += 1;
      continue;
    }
    if (ch === "/" && next === "/") {
      const nl = code.indexOf("\n", i + 2);
      i = nl === -1 ? code.length : nl + 1;
      continue;
    }
    if (ch === "/" && next === "*") {
      const end = code.indexOf("*/", i + 2);
      i = end === -1 ? code.length : end + 2;
      continue;
    }
    break;
  }
  return i;
}

const REGEX_PRECEDING_KEYWORDS = new Set([
  "return",
  "typeof",
  "void",
  "delete",
  "throw",
  "case",
  "in",
  "instanceof",
  "of",
  "new",
  "yield",
  "await",
  "else",
]);

const REGEX_PRECEDING_PUNCT = new Set([
  "=",
  "(",
  "[",
  "{",
  ",",
  ";",
  ":",
  "!",
  "&",
  "|",
  "?",
  "+",
  "-",
  "*",
  "%",
  "^",
  "~",
  "<",
  ">",
]);

function tryReadJsRegexEnd(code, slashIdx) {
  if (code[slashIdx] !== "/") return -1;
  const next = code[slashIdx + 1] || "";
  if (next === "/" || next === "*" || next === "") return -1;

  let p = slashIdx - 1;
  while (p >= 0 && (code[p] === " " || code[p] === "\t" || code[p] === "\r" || code[p] === "\n")) {
    p -= 1;
  }
  let canStartRegex = false;
  if (p < 0) {
    canStartRegex = true;
  } else if (REGEX_PRECEDING_PUNCT.has(code[p])) {
    canStartRegex = true;
  } else if (isIdentPart(code[p])) {
    let wStart = p;
    while (wStart > 0 && isIdentPart(code[wStart - 1])) wStart -= 1;
    const word = code.slice(wStart, p + 1);
    canStartRegex = REGEX_PRECEDING_KEYWORDS.has(word);
  }
  if (!canStartRegex) return -1;

  let i = slashIdx + 1;
  let inCharClass = false;
  while (i < code.length) {
    const ch = code[i];
    if (ch === "\n" || ch === "\r") return -1;
    if (ch === "\\") {
      if (i + 1 >= code.length || code[i + 1] === "\n") return -1;
      i += 2;
      continue;
    }
    if (ch === "[") {
      inCharClass = true;
      i += 1;
      continue;
    }
    if (ch === "]" && inCharClass) {
      inCharClass = false;
      i += 1;
      continue;
    }
    if (ch === "/" && !inCharClass) {
      i += 1;
      while (i < code.length && isIdentPart(code[i])) i += 1;
      return i;
    }
    i += 1;
  }
  return -1;
}

function readJsStringLiteral(code, quoteIdx) {
  const quote = code[quoteIdx];
  let i = quoteIdx + 1;
  let val = "";
  while (i < code.length) {
    const ch = code[i];
    if (ch === "\\") {
      if (i + 1 < code.length) {
        val += code[i + 1];
        i += 2;
        continue;
      }
    }
    if (ch === quote) {
      return { value: val, end: i + 1 };
    }
    val += ch;
    i += 1;
  }
  throw new Error(`Unterminated string literal starting at index ${quoteIdx}`);
}

function consumeBalanced(code, openIdx) {
  const open = code[openIdx];
  const close = open === "{" ? "}" : open === "(" ? ")" : "]";
  let depth = 1;
  let i = openIdx + 1;
  const stack = [];
  while (i < code.length && depth > 0) {
    const ch = code[i];
    const next = i + 1 < code.length ? code[i + 1] : "";
    if (stack.length > 0 && stack[stack.length - 1] === "template") {
      if (ch === "\\") {
        i += 2;
        continue;
      }
      if (ch === "`") {
        stack.pop();
        i += 1;
        continue;
      }
      if (ch === "$" && next === "{") {
        stack.push("tpl_expr");
        depth += 1;
        i += 2;
        continue;
      }
      i += 1;
      continue;
    }
    if (ch === "/" && next === "/") {
      const nl = code.indexOf("\n", i + 2);
      i = nl === -1 ? code.length : nl + 1;
      continue;
    }
    if (ch === "/" && next === "*") {
      const end = code.indexOf("*/", i + 2);
      i = end === -1 ? code.length : end + 2;
      continue;
    }
    if (ch === "/") {
      const rxEnd = tryReadJsRegexEnd(code, i);
      if (rxEnd > i) {
        i = rxEnd;
        continue;
      }
    }
    if (ch === "'" || ch === '"') {
      const strRes = readJsStringLiteral(code, i);
      i = strRes.end;
      continue;
    }
    if (ch === "`") {
      stack.push("template");
      i += 1;
      continue;
    }
    if (ch === open || (stack.length > 0 && ch === "{")) {
      depth += 1;
      if (stack.length > 0 && ch === "{") stack.push("brace");
      i += 1;
      continue;
    }
    if (ch === close || (stack.length > 0 && ch === "}")) {
      depth -= 1;
      if (stack.length > 0 && ch === "}") {
        stack.pop();
      }
      i += 1;
      continue;
    }
    i += 1;
  }
  return i;
}

function parseNamedList(braceInner) {
  const items = [];
  for (const rawPart of braceInner.split(",")) {
    const cleaned = rawPart.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "").trim();
    if (!cleaned) continue;
    const m = /^([A-Za-z_$][A-Za-z0-9_$]*)(?:\s+as\s+([A-Za-z_$][A-Za-z0-9_$]*))?$/.exec(cleaned);
    if (!m) {
      throw new Error(`Unsupported import/export specifier "${cleaned}"`);
    }
    items.push({ imported: m[1], local: m[2] || m[1] });
  }
  return items;
}

function extractBindingIdentifiers(declHead) {
  const ids = [];
  let i = 0;
  while (i < declHead.length) {
    i = skipJsTrivia(declHead, i);
    if (i >= declHead.length) break;
    const ch = declHead[i];
    if (ch === "{") {
      const end = consumeBalanced(declHead, i);
      const inner = declHead.slice(i + 1, end - 1);
      for (const part of inner.split(",")) {
        const clean = part.split("=")[0].trim();
        if (!clean) continue;
        if (clean.startsWith("...")) {
          const restId = clean.slice(3).trim();
          if (restId) ids.push(restId);
        } else {
          const colonParts = clean.split(":");
          const local = (colonParts[1] || colonParts[0]).trim();
          if (local) ids.push(local);
        }
      }
      i = end;
    } else if (ch === "[") {
      const end = consumeBalanced(declHead, i);
      const inner = declHead.slice(i + 1, end - 1);
      for (const part of inner.split(",")) {
        const clean = part.split("=")[0].replace(/^\.\.\./, "").trim();
        if (clean) ids.push(clean);
      }
      i = end;
    } else if (isIdentStart(ch)) {
      let end = i + 1;
      while (end < declHead.length && isIdentPart(declHead[end])) end += 1;
      ids.push(declHead.slice(i, end));
      i = end;
    } else {
      i += 1;
    }

    // Skip initializer `= ...` up to top-level `,` or `;`
    while (i < declHead.length) {
      const c = declHead[i];
      const next = i + 1 < declHead.length ? declHead[i + 1] : "";
      if (c === "/" && next === "/") {
        const nl = declHead.indexOf("\n", i + 2);
        i = nl === -1 ? declHead.length : nl + 1;
        continue;
      }
      if (c === "/" && next === "*") {
        const end = declHead.indexOf("*/", i + 2);
        i = end === -1 ? declHead.length : end + 2;
        continue;
      }
      if (c === "/") {
        const rxEnd = tryReadJsRegexEnd(declHead, i);
        if (rxEnd > i) {
          i = rxEnd;
          continue;
        }
      }
      if (c === "'" || c === '"') {
        i = readJsStringLiteral(declHead, i).end;
        continue;
      }
      if (c === "`") {
        // Skip template literal
        let ti = i + 1;
        while (ti < declHead.length) {
          if (declHead[ti] === "\\") {
            ti += 2;
            continue;
          }
          if (declHead[ti] === "`") {
            ti += 1;
            break;
          }
          if (declHead[ti] === "$" && declHead[ti + 1] === "{") {
            ti = consumeBalanced(declHead, ti + 1);
            continue;
          }
          ti += 1;
        }
        i = ti;
        continue;
      }
      if (c === "(" || c === "{" || c === "[") {
        i = consumeBalanced(declHead, i);
        continue;
      }
      if (c === ",") {
        i += 1;
        break;
      }
      if (c === ";") {
        return ids;
      }
      i += 1;
    }
  }
  return ids;
}

function findVarStatementEnd(code, startIdx) {
  let i = startIdx;
  while (i < code.length) {
    const ch = code[i];
    const next = i + 1 < code.length ? code[i + 1] : "";
    if (ch === "/" && next === "/") {
      const nl = code.indexOf("\n", i + 2);
      i = nl === -1 ? code.length : nl + 1;
      continue;
    }
    if (ch === "/" && next === "*") {
      const end = code.indexOf("*/", i + 2);
      i = end === -1 ? code.length : end + 2;
      continue;
    }
    if (ch === "/") {
      const rxEnd = tryReadJsRegexEnd(code, i);
      if (rxEnd > i) {
        i = rxEnd;
        continue;
      }
    }
    if (ch === "'" || ch === '"') {
      i = readJsStringLiteral(code, i).end;
      continue;
    }
    if (ch === "`") {
      let ti = i + 1;
      while (ti < code.length) {
        if (code[ti] === "\\") {
          ti += 2;
          continue;
        }
        if (code[ti] === "`") {
          ti += 1;
          break;
        }
        if (code[ti] === "$" && code[ti + 1] === "{") {
          ti = consumeBalanced(code, ti + 1);
          continue;
        }
        ti += 1;
      }
      i = ti;
      continue;
    }
    if (ch === "(" || ch === "{" || ch === "[") {
      i = consumeBalanced(code, i);
      continue;
    }
    if (ch === ";") {
      return i + 1;
    }
    if (ch === "\n") {
      const afterNl = skipJsTrivia(code, i + 1);
      const nextCh = code[afterNl] || "";
      if (
        nextCh !== "," &&
        nextCh !== "." &&
        nextCh !== "?" &&
        nextCh !== ":" &&
        nextCh !== "+" &&
        nextCh !== "-" &&
        nextCh !== "="
      ) {
        return i;
      }
    }
    i += 1;
  }
  return code.length;
}

/**
 * Lexes top-level ES module `import` and `export` declarations accurately
 * across both formatted TypeScript output and single-line minified vendor JS.
 */
function analyzeAndTransformModule(code) {
  const cleanCode = code.replace(/^\/\/#\s*sourceURL=.*$/gm, "");
  const imports = []; // { specifier, defaultIdent, namespaceIdent, named: [{imported, local}] }
  const reexports = []; // { specifier, star: boolean, starAs: string|null, named: [{imported, exported}] }
  const localExports = []; // { local, exported }
  let bodyOut = "";

  let i = 0;
  let depth = 0;
  const tplStack = [];

  while (i < cleanCode.length) {
    const ch = cleanCode[i];
    const next = i + 1 < cleanCode.length ? cleanCode[i + 1] : "";

    if (tplStack.length > 0 && tplStack[tplStack.length - 1] === "template") {
      if (ch === "\\") {
        bodyOut += cleanCode.slice(i, i + 2);
        i += 2;
        continue;
      }
      if (ch === "`") {
        tplStack.pop();
        bodyOut += "`";
        i += 1;
        continue;
      }
      if (ch === "$" && next === "{") {
        tplStack.push("tpl_expr");
        depth += 1;
        bodyOut += "${";
        i += 2;
        continue;
      }
      bodyOut += ch;
      i += 1;
      continue;
    }

    if (ch === "/" && next === "/") {
      const nl = cleanCode.indexOf("\n", i + 2);
      const end = nl === -1 ? cleanCode.length : nl;
      bodyOut += cleanCode.slice(i, end);
      i = end;
      continue;
    }
    if (ch === "/" && next === "*") {
      const end = cleanCode.indexOf("*/", i + 2);
      const stop = end === -1 ? cleanCode.length : end + 2;
      bodyOut += cleanCode.slice(i, stop);
      i = stop;
      continue;
    }
    if (ch === "/") {
      const rxEnd = tryReadJsRegexEnd(cleanCode, i);
      if (rxEnd > i) {
        bodyOut += cleanCode.slice(i, rxEnd);
        i = rxEnd;
        continue;
      }
    }
    if (ch === "'" || ch === '"') {
      const strEnd = readJsStringLiteral(cleanCode, i).end;
      bodyOut += cleanCode.slice(i, strEnd);
      i = strEnd;
      continue;
    }
    if (ch === "`") {
      tplStack.push("template");
      bodyOut += "`";
      i += 1;
      continue;
    }
    if (ch === "{") {
      depth += 1;
      if (tplStack.length > 0) tplStack.push("brace");
      bodyOut += "{";
      i += 1;
      continue;
    }
    if (ch === "}") {
      if (depth > 0) depth -= 1;
      if (tplStack.length > 0) tplStack.pop();
      bodyOut += "}";
      i += 1;
      continue;
    }

    // Check top-level `import` or `export` keywords
    const prevCh = i > 0 ? cleanCode[i - 1] : "";
    if (depth === 0 && !isIdentPart(prevCh) && prevCh !== ".") {
      if (cleanCode.startsWith("import", i) && !isIdentPart(cleanCode[i + 6] || "")) {
        const afterKw = skipJsTrivia(cleanCode, i + 6);
        const cAfter = cleanCode[afterKw] || "";
        // Leave dynamic `import(...)` and `import.meta` untouched
        if (cAfter !== "(" && cAfter !== ".") {
          if (cAfter === "'" || cAfter === '"') {
            const specRes = readJsStringLiteral(cleanCode, afterKw);
            let stmtEnd = skipJsTrivia(cleanCode, specRes.end);
            if (cleanCode[stmtEnd] === ";") stmtEnd += 1;
            imports.push({
              specifier: specRes.value,
              defaultIdent: null,
              namespaceIdent: null,
              named: [],
            });
            i = stmtEnd;
            continue;
          }

          let cur = afterKw;
          let defaultIdent = null;
          let namespaceIdent = null;
          let named = [];

          if (isIdentStart(cAfter)) {
            let idEnd = cur + 1;
            while (idEnd < cleanCode.length && isIdentPart(cleanCode[idEnd])) idEnd += 1;
            defaultIdent = cleanCode.slice(cur, idEnd);
            cur = skipJsTrivia(cleanCode, idEnd);
            if (cleanCode[cur] === ",") {
              cur = skipJsTrivia(cleanCode, cur + 1);
            }
          }

          if (cleanCode[cur] === "*") {
            cur = skipJsTrivia(cleanCode, cur + 1);
            if (!cleanCode.startsWith("as", cur) || isIdentPart(cleanCode[cur + 2] || "")) {
              throw new Error(`Expected 'as' after 'import *' near index ${cur}`);
            }
            cur = skipJsTrivia(cleanCode, cur + 2);
            let nsEnd = cur;
            while (nsEnd < cleanCode.length && isIdentPart(cleanCode[nsEnd])) nsEnd += 1;
            namespaceIdent = cleanCode.slice(cur, nsEnd);
            cur = skipJsTrivia(cleanCode, nsEnd);
          } else if (cleanCode[cur] === "{") {
            const braceEnd = consumeBalanced(cleanCode, cur);
            named = parseNamedList(cleanCode.slice(cur + 1, braceEnd - 1));
            cur = skipJsTrivia(cleanCode, braceEnd);
          }

          if (!cleanCode.startsWith("from", cur) || isIdentPart(cleanCode[cur + 4] || "")) {
            throw new Error(`Expected 'from' in import declaration near index ${cur}`);
          }
          cur = skipJsTrivia(cleanCode, cur + 4);
          const specRes = readJsStringLiteral(cleanCode, cur);
          let stmtEnd = skipJsTrivia(cleanCode, specRes.end);
          if (cleanCode[stmtEnd] === ";") stmtEnd += 1;
          imports.push({
            specifier: specRes.value,
            defaultIdent,
            namespaceIdent,
            named,
          });
          i = stmtEnd;
          continue;
        }
      }

      if (cleanCode.startsWith("export", i) && !isIdentPart(cleanCode[i + 6] || "")) {
        const afterKw = skipJsTrivia(cleanCode, i + 6);
        const cAfter = cleanCode[afterKw] || "";

        if (cAfter === "*") {
          let cur = skipJsTrivia(cleanCode, afterKw + 1);
          let starAs = null;
          if (cleanCode.startsWith("as", cur) && !isIdentPart(cleanCode[cur + 2] || "")) {
            cur = skipJsTrivia(cleanCode, cur + 2);
            let nsEnd = cur;
            while (nsEnd < cleanCode.length && isIdentPart(cleanCode[nsEnd])) nsEnd += 1;
            starAs = cleanCode.slice(cur, nsEnd);
            cur = skipJsTrivia(cleanCode, nsEnd);
          }
          if (!cleanCode.startsWith("from", cur) || isIdentPart(cleanCode[cur + 4] || "")) {
            throw new Error(`Expected 'from' in 'export *' near index ${cur}`);
          }
          cur = skipJsTrivia(cleanCode, cur + 4);
          const specRes = readJsStringLiteral(cleanCode, cur);
          let stmtEnd = skipJsTrivia(cleanCode, specRes.end);
          if (cleanCode[stmtEnd] === ";") stmtEnd += 1;
          reexports.push({
            specifier: specRes.value,
            star: true,
            starAs,
            named: [],
          });
          i = stmtEnd;
          continue;
        }

        if (cAfter === "{") {
          const braceEnd = consumeBalanced(cleanCode, afterKw);
          const list = parseNamedList(cleanCode.slice(afterKw + 1, braceEnd - 1));
          let cur = skipJsTrivia(cleanCode, braceEnd);
          if (cleanCode.startsWith("from", cur) && !isIdentPart(cleanCode[cur + 4] || "")) {
            cur = skipJsTrivia(cleanCode, cur + 4);
            const specRes = readJsStringLiteral(cleanCode, cur);
            let stmtEnd = skipJsTrivia(cleanCode, specRes.end);
            if (cleanCode[stmtEnd] === ";") stmtEnd += 1;
            reexports.push({
              specifier: specRes.value,
              star: false,
              starAs: null,
              named: list.map((it) => ({ imported: it.imported, exported: it.local })),
            });
            i = stmtEnd;
            continue;
          }
          if (cleanCode[cur] === ";") cur += 1;
          for (const it of list) {
            localExports.push({ local: it.imported, exported: it.local });
          }
          i = cur;
          continue;
        }

        // `export [async] function|class|const|let|var ...`
        let declPos = afterKw;
        if (cleanCode.startsWith("async", declPos) && !isIdentPart(cleanCode[declPos + 5] || "")) {
          const afterAsync = skipJsTrivia(cleanCode, declPos + 5);
          if (cleanCode.startsWith("function", afterAsync) && !isIdentPart(cleanCode[afterAsync + 8] || "")) {
            let nameStart = skipJsTrivia(cleanCode, afterAsync + 8);
            if (cleanCode[nameStart] === "*") nameStart = skipJsTrivia(cleanCode, nameStart + 1);
            let nameEnd = nameStart;
            while (nameEnd < cleanCode.length && isIdentPart(cleanCode[nameEnd])) nameEnd += 1;
            const fnName = cleanCode.slice(nameStart, nameEnd);
            localExports.push({ local: fnName, exported: fnName });
            i = afterKw;
            continue;
          }
        }
        if (cleanCode.startsWith("function", declPos) && !isIdentPart(cleanCode[declPos + 8] || "")) {
          let nameStart = skipJsTrivia(cleanCode, declPos + 8);
          if (cleanCode[nameStart] === "*") nameStart = skipJsTrivia(cleanCode, nameStart + 1);
          let nameEnd = nameStart;
          while (nameEnd < cleanCode.length && isIdentPart(cleanCode[nameEnd])) nameEnd += 1;
          const fnName = cleanCode.slice(nameStart, nameEnd);
          localExports.push({ local: fnName, exported: fnName });
          i = afterKw;
          continue;
        }
        if (cleanCode.startsWith("class", declPos) && !isIdentPart(cleanCode[declPos + 5] || "")) {
          const nameStart = skipJsTrivia(cleanCode, declPos + 5);
          let nameEnd = nameStart;
          while (nameEnd < cleanCode.length && isIdentPart(cleanCode[nameEnd])) nameEnd += 1;
          const clsName = cleanCode.slice(nameStart, nameEnd);
          localExports.push({ local: clsName, exported: clsName });
          i = afterKw;
          continue;
        }
        for (const kw of ["const", "let", "var"]) {
          if (cleanCode.startsWith(kw, declPos) && !isIdentPart(cleanCode[declPos + kw.length] || "")) {
            const bindStart = skipJsTrivia(cleanCode, declPos + kw.length);
            const stmtEnd = findVarStatementEnd(cleanCode, bindStart);
            const ids = extractBindingIdentifiers(cleanCode.slice(bindStart, stmtEnd));
            for (const id of ids) {
              localExports.push({ local: id, exported: id });
            }
            i = afterKw;
            declPos = -1;
            break;
          }
        }
        if (declPos === -1) {
          continue;
        }
      }
    }

    bodyOut += ch;
    i += 1;
  }

  return {
    imports,
    reexports,
    localExports,
    body: bodyOut.trim(),
  };
}

function compactCssSegment(rawCss) {
  let out = "";
  let i = 0;
  let wsPending = false;

  const lastOutChar = () => (out.length > 0 ? out[out.length - 1] : "");

  while (i < rawCss.length) {
    const ch = rawCss[i];
    const next = i + 1 < rawCss.length ? rawCss[i + 1] : "";

    if (ch === "/" && next === "*") {
      const end = rawCss.indexOf("*/", i + 2);
      i = end === -1 ? rawCss.length : end + 2;
      continue;
    }

    if (ch === '"' || ch === "'") {
      if (wsPending) {
        const prev = lastOutChar();
        if (prev && prev !== ":" && prev !== "{" && prev !== ";" && prev !== ",") {
          out += " ";
        }
        wsPending = false;
      }
      const quote = ch;
      out += ch;
      i += 1;
      while (i < rawCss.length) {
        const c = rawCss[i];
        out += c;
        if (c === "\\" && i + 1 < rawCss.length) {
          i += 1;
          out += rawCss[i];
        } else if (c === quote) {
          i += 1;
          break;
        }
        i += 1;
      }
      continue;
    }

    if (ch === " " || ch === "\t" || ch === "\r" || ch === "\n") {
      wsPending = true;
      i += 1;
      continue;
    }

    if (ch === "{" || ch === "}" || ch === ";" || ch === "," || ch === ">") {
      wsPending = false;
      out += ch;
      i += 1;
      continue;
    }

    if (wsPending) {
      const prev = lastOutChar();
      if (
        prev &&
        prev !== "{" &&
        prev !== "}" &&
        prev !== ";" &&
        prev !== "," &&
        prev !== ">" &&
        prev !== ":"
      ) {
        out += " ";
      }
      wsPending = false;
    }

    out += ch;
    i += 1;
  }

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
 * Lexer-aware compactor:
 * - Strips type-erasure blank holes & space runs outside literals/comments
 * - Preserves `html` / general template literals 100% verbatim
 * - Compacts CSS comments & whitespace inside `css` tagged template literals
 */
function compactBundleCode(code) {
  const stack = [{ kind: "code", braces: 0 }];
  const outLines = [];
  let lineBuf = "";
  let codeSeg = "";
  let cssBuf = "";
  let lineTouchedTemplate = false;

  const top = () => stack[stack.length - 1];
  const flushCodeSeg = () => {
    if (codeSeg) {
      lineBuf += compactCodeSegment(codeSeg, lineBuf.length === 0);
      codeSeg = "";
    }
  };
  const flushCssSeg = () => {
    if (cssBuf) {
      lineBuf += compactCssSegment(cssBuf);
      cssBuf = "";
    }
  };

  for (let i = 0; i < code.length; i += 1) {
    const ch = code[i];
    const next = i + 1 < code.length ? code[i + 1] : "";
    const cur = top();

    if (cur.kind === "css_template") {
      if (ch === "\\") {
        cssBuf += ch;
        if (next) {
          cssBuf += next;
          i += 1;
        }
        continue;
      }
      if (ch === "`") {
        flushCssSeg();
        lineBuf += "`";
        stack.pop();
        continue;
      }
      if (ch === "$" && next === "{") {
        flushCssSeg();
        lineBuf += "${";
        i += 1;
        stack.push({ kind: "code", braces: 0 });
        continue;
      }
      cssBuf += ch;
      continue;
    }

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
    if (ch === "/") {
      const rxEnd = tryReadJsRegexEnd(code, i);
      if (rxEnd > i) {
        flushCodeSeg();
        lineBuf += code.slice(i, rxEnd);
        i = rxEnd - 1;
        continue;
      }
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
      const beforeTag = lineBuf.slice(-4);
      const isCssTag = /(?:^|[^A-Za-z0-9_$])css$/.test(beforeTag);
      lineBuf += "`";
      if (isCssTag) {
        stack.push({ kind: "css_template" });
      } else {
        lineTouchedTemplate = true;
        stack.push({ kind: "template" });
      }
      continue;
    }
    if (ch === "{") {
      cur.braces += 1;
      codeSeg += ch;
      continue;
    }
    if (ch === "}") {
      if (
        cur.braces === 0 &&
        stack.length > 1 &&
        (stack[stack.length - 2].kind === "template" ||
          stack[stack.length - 2].kind === "css_template")
      ) {
        flushCodeSeg();
        const parentKind = stack[stack.length - 2].kind;
        stack.pop();
        if (parentKind === "template") {
          lineTouchedTemplate = true;
        }
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
  flushCssSeg();
  if (lineBuf.length > 0 || lineTouchedTemplate) {
    const finalText = lineTouchedTemplate ? lineBuf : lineBuf.replace(/[ \t]+$/, "");
    if (lineTouchedTemplate || finalText.length > 0) {
      outLines.push({ text: finalText, rawTemplate: lineTouchedTemplate });
    }
  }

  return outLines.map((e) => e.text).join("\n").trim() + "\n";
}

function extractMdiChunkBundle(mdiStrippedJs) {
  const declRe = /const\s+PACKED_MDI_CHUNKS\s*=\s*(\[[\s\S]*?\])\s*;/;
  const match = declRe.exec(mdiStrippedJs);
  if (!match) {
    throw new Error("Could not locate `const PACKED_MDI_CHUNKS = [...]` in src/mdi-catalog.ts");
  }
  const arrayLiteral = match[1];
  const rawMdiModule = [
    "// AUTO-GENERATED FILE — DO NOT EDIT DIRECTLY.",
    "// Source: ha-latter/frontend_src/src/mdi-catalog.ts (build via `node ha-latter/frontend_src/build.mjs`).",
    `export const PACKED_MDI_CHUNKS = ${arrayLiteral};`,
    "//# sourceURL=latter-studio/latter-studio-mdi.js",
  ].join("\n");
  const mdiBundle = compactBundleCode(rawMdiModule);
  const mdiBuf = Buffer.from(mdiBundle, "utf8");
  const mdiDigest = crypto.createHash("sha256").update(mdiBuf).digest("hex").slice(0, 16);

  const rewrittenMdiSource = mdiStrippedJs
    .replace(declRe, "const PACKED_MDI_CHUNKS = [];")
    .replace(/"__LATTER_MDI_CHUNK_URL__"/g, JSON.stringify(`./latter-studio-mdi.js?v=${mdiDigest}`));

  if (!rewrittenMdiSource.includes(`./latter-studio-mdi.js?v=${mdiDigest}`)) {
    throw new Error("Failed to inject hashed MDI chunk URL into src/mdi-catalog.ts");
  }

  return { mdiBundle, mdiDigest, rewrittenMdiSource };
}

function buildEnLocaleJson() {
  if (!fs.existsSync(EN_I18N_FILE)) {
    throw new Error("Missing src/i18n/en.ts");
  }
  const i18nDir = path.dirname(EN_I18N_FILE);
  const sandbox = vm.createContext(Object.create(null));
  for (const sliceName of ["en-common.ts", "en-system.ts", "en-devices.ts"]) {
    const slicePath = path.join(i18nDir, sliceName);
    if (!fs.existsSync(slicePath)) continue;
    const rawSlice = fs.readFileSync(slicePath, "utf8").replace(/\r\n/g, "\n");
    const strippedSlice = stripTypeScriptTypes(rawSlice, { mode: "strip" });
    const parsedSlice = analyzeAndTransformModule(strippedSlice);
    vm.runInContext(parsedSlice.body, sandbox, { filename: `src/i18n/${sliceName}` });
  }
  const rawTs = fs.readFileSync(EN_I18N_FILE, "utf8").replace(/\r\n/g, "\n");
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

function buildBundles() {
  runMandatoryTsc();

  const allSourceFiles = collectSourceModules(SRC_DIR);
  const strippedByFile = new Map();
  for (const file of allSourceFiles) {
    const raw = fs.readFileSync(file, "utf8").replace(/\r\n/g, "\n");
    const stripped = file.endsWith(".ts")
      ? stripTypeScriptTypes(raw, { mode: "strip" })
      : raw;
    strippedByFile.set(file, stripped);
  }

  const mdiOriginal = strippedByFile.get(MDI_CATALOG_FILE);
  if (mdiOriginal === undefined) {
    throw new Error("Missing src/mdi-catalog.ts");
  }
  const { mdiBundle, mdiDigest, rewrittenMdiSource } = extractMdiChunkBundle(mdiOriginal);
  strippedByFile.set(MDI_CATALOG_FILE, rewrittenMdiSource);

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
      const target = resolveImportTarget(file, re.specifier);
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
            const fromRel = path.relative(FRONTEND_DIR, file).replace(/\\/g, "/");
            const toRel = path.relative(FRONTEND_DIR, target).replace(/\\/g, "/");
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

  // Topological sort from ENTRY_FILE with cycle detection & named-export validation
  const ordered = [];
  const state = new Map();

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
    const info = parsedByFile.get(file);
    if (!info) {
      throw new Error(`Missing source module: ${file}`);
    }
    for (const imp of info.imports) {
      const target = resolveImportTarget(file, imp.specifier);
      visit(target, [...stack, file]);
      const targetExports = getModuleExports(target);
      for (const sym of imp.named) {
        if (!targetExports.has(sym.imported)) {
          const fromRel = path.relative(FRONTEND_DIR, file).replace(/\\/g, "/");
          const toRel = path.relative(FRONTEND_DIR, target).replace(/\\/g, "/");
          throw new Error(
            `Symbol "${sym.imported}" imported in ${fromRel} is not a runtime export of ${toRel} (use \`import type\` for types/interfaces)`,
          );
        }
      }
    }
    for (const re of info.reexports) {
      const target = resolveImportTarget(file, re.specifier);
      visit(target, [...stack, file]);
      getModuleExports(file);
    }
    state.set(file, "done");
    ordered.push(file);
  }

  visit(ENTRY_FILE, []);

  const relIdOf = (file) => path.relative(FRONTEND_DIR, file).replace(/\\/g, "/");

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
      const targetRel = relIdOf(resolveImportTarget(file, imp.specifier));
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
      const targetRel = relIdOf(resolveImportTarget(file, re.specifier));
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

  const entryRel = relIdOf(ENTRY_FILE);
  const entryExports = [...getModuleExports(ENTRY_FILE)].sort();
  chunks.push(`const __latterEntry = __latterReq(${JSON.stringify(entryRel)});`);
  for (const sym of entryExports) {
    chunks.push(`export const ${sym} = __latterEntry.${sym};`);
  }

  const combined = compactBundleCode(chunks.join("\n"));

  verifyEsmSyntax(combined, "latter-studio.js");
  verifyEsmSyntax(mdiBundle, "latter-studio-mdi.js");

  const enLocaleJson = buildEnLocaleJson();

  return {
    bundle: combined,
    mdiBundle,
    mdiDigest,
    enLocaleJson,
    moduleCount: ordered.length,
    totalSourceFiles: allSourceFiles.length,
  };
}

function gzipDeterministic(buf) {
  const gz = Buffer.from(zlib.gzipSync(buf, { level: 9 }));
  // RFC 1952 deterministic header: zero 4-byte MTIME (offset 4..7) & set OS = 3 (Unix, offset 9).
  gz.writeUInt32LE(0, 4);
  gz[9] = 0x03;
  return gz;
}

function brotliDeterministic(buf) {
  return Buffer.from(
    zlib.brotliCompressSync(buf, {
      params: {
        [zlib.constants.BROTLI_PARAM_MODE]: zlib.constants.BROTLI_MODE_TEXT,
        [zlib.constants.BROTLI_PARAM_QUALITY]: 11,
        [zlib.constants.BROTLI_PARAM_SIZE_HINT]: buf.length,
      },
    }),
  );
}

function writeCompressedAssets(jsPath, rawBuf) {
  const gzPath = `${jsPath}.gz`;
  const brPath = `${jsPath}.br`;

  let reuseGz = false;
  if (fs.existsSync(gzPath)) {
    try {
      const existingGz = fs.readFileSync(gzPath);
      if (
        existingGz.length >= 10 &&
        existingGz[0] === 0x1f &&
        existingGz[1] === 0x8b &&
        existingGz[2] === 0x08 &&
        existingGz.readUInt32LE(4) === 0 &&
        existingGz[9] === 0x03 &&
        zlib.gunzipSync(existingGz).equals(rawBuf)
      ) {
        reuseGz = true;
      }
    } catch {
      reuseGz = false;
    }
  }
  if (!reuseGz) {
    fs.writeFileSync(gzPath, gzipDeterministic(rawBuf));
  }

  let reuseBr = false;
  if (fs.existsSync(brPath)) {
    try {
      const existingBr = fs.readFileSync(brPath);
      if (zlib.brotliDecompressSync(existingBr).equals(rawBuf)) {
        reuseBr = true;
      }
    } catch {
      reuseBr = false;
    }
  }
  if (!reuseBr) {
    fs.writeFileSync(brPath, brotliDeterministic(rawBuf));
  }
}

function verifyCompressedAssets(jsPath, expectedBuf, label) {
  const gzPath = `${jsPath}.gz`;
  const brPath = `${jsPath}.br`;
  if (!fs.existsSync(gzPath)) {
    throw new Error(`Missing precompressed gzip asset: ${gzPath} — run \`node ha-latter/frontend_src/build.mjs\``);
  }
  const gzBuf = fs.readFileSync(gzPath);
  if (gzBuf.length < 10 || gzBuf[0] !== 0x1f || gzBuf[1] !== 0x8b || gzBuf[2] !== 0x08) {
    throw new Error(`Invalid gzip header in ${label}.gz`);
  }
  if (gzBuf.readUInt32LE(4) !== 0) {
    throw new Error(`${label}.gz must have deterministic mtime=0 in RFC 1952 header`);
  }
  if (!zlib.gunzipSync(gzBuf).equals(expectedBuf)) {
    throw new Error(`${label}.gz is out of sync with ${label} — run \`node ha-latter/frontend_src/build.mjs\``);
  }

  if (!fs.existsSync(brPath)) {
    throw new Error(`Missing precompressed brotli asset: ${brPath} — run \`node ha-latter/frontend_src/build.mjs\``);
  }
  const brBuf = fs.readFileSync(brPath);
  if (!zlib.brotliDecompressSync(brBuf).equals(expectedBuf)) {
    throw new Error(`${label}.br is out of sync with ${label} — run \`node ha-latter/frontend_src/build.mjs\``);
  }
}

function assertExactUtf8File(filePath, expectedText, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing generated artifact ${label} (${filePath}) — run \`node ha-latter/frontend_src/build.mjs\``);
  }
  const buf = fs.readFileSync(filePath);
  if (buf.length >= 3 && buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf) {
    throw new Error(`${label} must not start with UTF-8 BOM`);
  }
  if (buf.toString("utf8") !== expectedText) {
    throw new Error(
      `${label} is out of sync with frontend_src/src/ — run \`node ha-latter/frontend_src/build.mjs\``,
    );
  }
}

function runStaticGuardrails(bundleText, mdiBundleText) {
  const errors = [];
  const allSourceFiles = collectSourceModules(SRC_DIR);
  const scanTargets = [
    { label: "custom_components/latter/frontend/latter-studio.js", text: bundleText },
    { label: "custom_components/latter/frontend/latter-studio-mdi.js", text: mdiBundleText },
    ...allSourceFiles.map((f) => ({
      label: path.relative(path.resolve(FRONTEND_DIR, ".."), f).replace(/\\/g, "/"),
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
  // Checks quoted style="...", unquoted style=${"..." / `...`} unless setting `--*` custom properties,
  // direct `.style.<prop>` mutations (except `.style.setProperty("--...")`), and `style.cssText`.
  const bannedInlineStyleRe =
    /\bstyle=["'](?!\s*--|\s*\$\{)|\bstyle=["']\s*\$\{\s*["'`](?!\s*--)|\bstyle=\$\{\s*["'`](?!\s*--)|\.style\.(?!setProperty\(["']--)|\bstyle\.cssText\b/;

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

    // Also verify unquoted identifier bindings `style=${ident}` resolve to a `--*` custom property assignment
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

  // D-014 two-column layout & heading hierarchy checks across all 13 two-column views
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

try {
  const { bundle, mdiBundle, mdiDigest, enLocaleJson, moduleCount, totalSourceFiles } =
    buildBundles();
  const lineCount = bundle.split("\n").length - 1;
  const bundleBuf = Buffer.from(bundle, "utf8");
  const mdiBuf = Buffer.from(mdiBundle, "utf8");

  if (modeTypecheckOnly) {
    runStaticGuardrails(bundle, mdiBundle);
    process.stdout.write(
      `tsc --noEmit, module-scoped ESM graph & guardrails verified (${moduleCount}/${totalSourceFiles} modules, ${lineCount} JS lines, MDI chunk v=${mdiDigest}).\n`,
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
    runStaticGuardrails(bundle, mdiBundle);
    process.stdout.write(
      `Studio check PASSED (${moduleCount} modules, ${bundleBuf.length} B core + ${mdiBuf.length} B lazy MDI [v=${mdiDigest}], .gz/.br + locales/en.json in sync, 0 guardrail issues).\n`,
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
  runStaticGuardrails(bundle, mdiBundle);
  process.stdout.write(
    `Built Latter Studio (${moduleCount} modules: ${bundleBuf.length} B core + ${mdiBuf.length} B lazy MDI [v=${mdiDigest}], .gz/.br + studio/locales/en.json synced).\n`,
  );
} catch (err) {
  process.stderr.write(
    `Studio build error: ${err instanceof Error ? err.message : String(err)}\n`,
  );
  process.exit(1);
}
