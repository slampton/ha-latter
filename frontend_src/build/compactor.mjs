/**
 * Lexer-Aware Bundle & CSS Compactor (`L4`).
 *
 * - Strips type-erasure blank holes & space runs outside literals/comments
 * - Preserves `html` / general template literals 100% verbatim
 * - Compacts CSS comments & whitespace inside `css` tagged template literals
 */

import { tryReadJsRegexEnd } from "./lexer.mjs";

export function compactCssSegment(rawCss) {
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

export function compactCodeSegment(seg, isLineStart) {
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

export function compactBundleCode(code) {
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
