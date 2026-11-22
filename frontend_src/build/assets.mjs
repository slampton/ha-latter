/**
 * Deterministic Gzip / Brotli Asset Emission & Exact UTF-8 Verification.
 */

import fs from "node:fs";
import zlib from "node:zlib";

export function gzipDeterministic(buf) {
  const gz = Buffer.from(zlib.gzipSync(buf, { level: 9 }));
  // RFC 1952 deterministic header: zero 4-byte MTIME (offset 4..7) & set OS = 3 (Unix, offset 9).
  gz.writeUInt32LE(0, 4);
  gz[9] = 0x03;
  return gz;
}

export function brotliDeterministic(buf) {
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

export function writeCompressedAssets(jsPath, rawBuf) {
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

export function verifyCompressedAssets(jsPath, expectedBuf, label) {
  const gzPath = `${jsPath}.gz`;
  const brPath = `${jsPath}.br`;
  if (!fs.existsSync(gzPath)) {
    throw new Error(
      `Missing precompressed gzip asset: ${gzPath} — run \`node ha-latter/frontend_src/build.mjs\``,
    );
  }
  const gzBuf = fs.readFileSync(gzPath);
  if (gzBuf.length < 10 || gzBuf[0] !== 0x1f || gzBuf[1] !== 0x8b || gzBuf[2] !== 0x08) {
    throw new Error(`Invalid gzip header in ${label}.gz`);
  }
  if (gzBuf.readUInt32LE(4) !== 0) {
    throw new Error(`${label}.gz must have deterministic mtime=0 in RFC 1952 header`);
  }
  if (!zlib.gunzipSync(gzBuf).equals(expectedBuf)) {
    throw new Error(
      `${label}.gz is out of sync with ${label} — run \`node ha-latter/frontend_src/build.mjs\``,
    );
  }

  if (!fs.existsSync(brPath)) {
    throw new Error(
      `Missing precompressed brotli asset: ${brPath} — run \`node ha-latter/frontend_src/build.mjs\``,
    );
  }
  const brBuf = fs.readFileSync(brPath);
  if (!zlib.brotliDecompressSync(brBuf).equals(expectedBuf)) {
    throw new Error(
      `${label}.br is out of sync with ${label} — run \`node ha-latter/frontend_src/build.mjs\``,
    );
  }
}

export function assertExactUtf8File(filePath, expectedText, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(
      `Missing generated artifact ${label} (${filePath}) — run \`node ha-latter/frontend_src/build.mjs\``,
    );
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
