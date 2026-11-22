/**
 * JavaScript / TypeScript Module Lexer, Import Resolver, & Raw Specifier Scanner (`L4`).
 *
 * Handles formatted TypeScript output, raw TypeScript (`import type` / `export type`),
 * and single-line minified vendor JS without external parser dependencies.
 */

import fs from "node:fs";
import path from "node:path";

export function collectSourceModules(dir) {
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

export function collectBuildModules(frontendDir) {
  const out = [path.join(frontendDir, "build.mjs")];
  const buildDir = path.join(frontendDir, "build");
  if (fs.existsSync(buildDir)) {
    for (const ent of fs.readdirSync(buildDir, { withFileTypes: true })) {
      if (ent.isFile() && (ent.name.endsWith(".mjs") || ent.name.endsWith(".js"))) {
        out.push(path.join(buildDir, ent.name));
      }
    }
  }
  return out.sort((a, b) => a.localeCompare(b));
}

export function resolveImportTarget(frontendDir, fromFile, specifier) {
  if (!specifier.startsWith(".")) {
    throw new Error(
      `External bare import "${specifier}" in ${path.relative(frontendDir, fromFile)} is not allowed in zero-runtime-dep bundle`,
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
    rawTarget + ".mjs",
    path.join(rawTarget, "index.ts"),
    path.join(rawTarget, "index.js"),
    path.join(rawTarget, "index.mjs"),
  );
  for (const c of candidates) {
    if (fs.existsSync(c) && fs.statSync(c).isFile() && !c.endsWith(".d.ts")) {
      return c;
    }
  }
  throw new Error(
    `Cannot resolve import "${specifier}" from ${path.relative(frontendDir, fromFile)}`,
  );
}

export function isIdentStart(ch) {
  return (
    (ch >= "A" && ch <= "Z") ||
    (ch >= "a" && ch <= "z") ||
    ch === "_" ||
    ch === "$"
  );
}

export function isIdentPart(ch) {
  return isIdentStart(ch) || (ch >= "0" && ch <= "9");
}

export function skipJsTrivia(code, idx) {
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

export function tryReadJsRegexEnd(code, slashIdx) {
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

export function readJsStringLiteral(code, quoteIdx) {
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

export function consumeBalanced(code, openIdx) {
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
    const cleaned = rawPart
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/\/\/.*$/gm, "")
      .trim()
      .replace(/^type\s+(?=[A-Za-z_$])/, "");
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
export function analyzeAndTransformModule(code) {
  const cleanCode = code.replace(/^\/\/#\s*sourceURL=.*$/gm, "");
  const imports = [];
  const reexports = [];
  const localExports = [];
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

    const prevCh = i > 0 ? cleanCode[i - 1] : "";
    if (depth === 0 && !isIdentPart(prevCh) && prevCh !== ".") {
      if (cleanCode.startsWith("import", i) && !isIdentPart(cleanCode[i + 6] || "")) {
        const afterKw = skipJsTrivia(cleanCode, i + 6);
        const cAfter = cleanCode[afterKw] || "";
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

/**
 * Lexer-aware raw specifier scanner for DAG verification (`import`, `import type`,
 * `export ... from`, `export type ... from`, and dynamic `import("...")`).
 * Ignores comments, string literals, regex literals, and template text.
 */
export function scanRawSpecifiers(code) {
  const out = [];
  let i = 0;
  let depth = 0;
  const tplStack = [];

  while (i < code.length) {
    const ch = code[i];
    const next = i + 1 < code.length ? code[i + 1] : "";

    if (tplStack.length > 0 && tplStack[tplStack.length - 1] === "template") {
      if (ch === "\\") {
        i += 2;
        continue;
      }
      if (ch === "`") {
        tplStack.pop();
        i += 1;
        continue;
      }
      if (ch === "$" && next === "{") {
        tplStack.push("tpl_expr");
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
      i = readJsStringLiteral(code, i).end;
      continue;
    }
    if (ch === "`") {
      tplStack.push("template");
      i += 1;
      continue;
    }
    if (ch === "{") {
      depth += 1;
      if (tplStack.length > 0) tplStack.push("brace");
      i += 1;
      continue;
    }
    if (ch === "}") {
      if (depth > 0) depth -= 1;
      if (tplStack.length > 0) tplStack.pop();
      i += 1;
      continue;
    }

    const prevCh = i > 0 ? code[i - 1] : "";
    if (!isIdentPart(prevCh) && prevCh !== ".") {
      if (code.startsWith("import", i) && !isIdentPart(code[i + 6] || "")) {
        let cur = skipJsTrivia(code, i + 6);
        const cAfter = code[cur] || "";
        if (cAfter === "(") {
          const argIdx = skipJsTrivia(code, cur + 1);
          if (code[argIdx] === "'" || code[argIdx] === '"') {
            const specRes = readJsStringLiteral(code, argIdx);
            out.push({ specifier: specRes.value, kind: "dynamic" });
          }
          i = cur + 1;
          continue;
        }
        if (cAfter !== "." && depth === 0) {
          let kind = "value";
          if (code.startsWith("type", cur) && !isIdentPart(code[cur + 4] || "")) {
            const afterType = skipJsTrivia(code, cur + 4);
            if (code[afterType] === "{" || code[afterType] === "*" || isIdentStart(code[afterType] || "")) {
              kind = "type";
              cur = afterType;
            }
          }
          if (code[cur] === "'" || code[cur] === '"') {
            const specRes = readJsStringLiteral(code, cur);
            out.push({ specifier: specRes.value, kind });
            i = specRes.end;
            continue;
          }
          while (cur < code.length) {
            if (code[cur] === "{") {
              cur = consumeBalanced(code, cur);
              continue;
            }
            if (code.startsWith("from", cur) && !isIdentPart(code[cur - 1] || "") && !isIdentPart(code[cur + 4] || "")) {
              const qIdx = skipJsTrivia(code, cur + 4);
              if (code[qIdx] === "'" || code[qIdx] === '"') {
                const specRes = readJsStringLiteral(code, qIdx);
                out.push({ specifier: specRes.value, kind });
                cur = specRes.end;
              }
              break;
            }
            if (code[cur] === ";") break;
            cur += 1;
          }
          i = cur;
          continue;
        }
      }

      if (depth === 0 && code.startsWith("export", i) && !isIdentPart(code[i + 6] || "")) {
        let cur = skipJsTrivia(code, i + 6);
        let kind = "value";
        if (code.startsWith("type", cur) && !isIdentPart(code[cur + 4] || "")) {
          const afterType = skipJsTrivia(code, cur + 4);
          if (code[afterType] === "{" || code[afterType] === "*") {
            kind = "type";
            cur = afterType;
          }
        }
        if (code[cur] === "*" || code[cur] === "{") {
          if (code[cur] === "{") {
            cur = consumeBalanced(code, cur);
          } else {
            cur += 1;
            const afterStar = skipJsTrivia(code, cur);
            if (code.startsWith("as", afterStar) && !isIdentPart(code[afterStar + 2] || "")) {
              cur = skipJsTrivia(code, afterStar + 2);
              while (cur < code.length && isIdentPart(code[cur])) cur += 1;
            }
          }
          cur = skipJsTrivia(code, cur);
          if (code.startsWith("from", cur) && !isIdentPart(code[cur + 4] || "")) {
            const qIdx = skipJsTrivia(code, cur + 4);
            if (code[qIdx] === "'" || code[qIdx] === '"') {
              const specRes = readJsStringLiteral(code, qIdx);
              out.push({ specifier: specRes.value, kind });
              i = specRes.end;
              continue;
            }
          }
        }
      }
    }

    i += 1;
  }

  return out;
}
