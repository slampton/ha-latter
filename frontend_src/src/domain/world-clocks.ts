/**
 * Pure World Clocks wire parser, serializer, and UTF-8 byte-bounded label sanitizer (`D-038`).
 * Wire format: `<label>|<iana>;<label>|<iana>;...` (up to `MAX_WORLD_CLOCKS` zones, excluding pinned UTC).
 */

import { MAX_WORLD_CLOCKS } from "../constants.js";
import { truncateUtf8Bytes } from "../utils/format.js";

export interface WorldClockItemView {
  label: string;
  iana: string;
}

export const PINNED_UTC_ZONES: ReadonlySet<string> = new Set([
  "UTC",
  "Etc/UTC",
  "GMT",
  "Etc/GMT",
  "Etc/GMT+0",
  "Etc/GMT-0",
  "Etc/GMT0",
]);

export const IANA_ZONE_PATTERN = /^[A-Za-z0-9_+-]+(?:\/[A-Za-z0-9_+-]+)+$/;

export function isValidWorldClockZone(iana: string): boolean {
  const clean = String(iana || "").trim();
  return Boolean(clean && !PINNED_UTC_ZONES.has(clean) && IANA_ZONE_PATTERN.test(clean));
}

export function sanitizeClockLabel(
  raw: unknown,
  maxBytes = 32,
  trimEdges = true,
): string {
  const str = String(raw ?? "");
  let collapsed = "";
  let prevSpace = trimEdges;
  for (const ch of str) {
    const code = ch.charCodeAt(0);
    if (
      code < 0x20 ||
      code === 0x7f ||
      ch === "|" ||
      ch === ";" ||
      ch === "\x1e" ||
      ch === "\x1f" ||
      ch === " " ||
      ch === "\t" ||
      ch === "\r" ||
      ch === "\n"
    ) {
      if (!prevSpace) {
        collapsed += " ";
        prevSpace = true;
      }
      continue;
    }
    collapsed += ch;
    prevSpace = false;
  }
  const normalized = trimEdges ? collapsed.trim() : collapsed;
  const truncated = truncateUtf8Bytes(normalized, maxBytes);
  return trimEdges ? truncated.trimEnd() : truncated;
}

export function fallbackLabelForIana(iana: string): string {
  const tail = iana.split("/").pop() || iana;
  return sanitizeClockLabel(tail.replace(/_/g, " ")) || iana;
}

export function parseWorldClocksSpec(raw: unknown): WorldClockItemView[] {
  const out: WorldClockItemView[] = [];
  const seen = new Set<string>();
  for (const part of String(raw ?? "").split(";")) {
    const rec = part.trim();
    if (!rec) continue;
    const pipeIdx = rec.indexOf("|");
    if (pipeIdx < 0) continue;
    const rawLbl = rec.slice(0, pipeIdx);
    const iana = rec.slice(pipeIdx + 1).trim();
    if (!isValidWorldClockZone(iana)) {
      continue;
    }
    const label = sanitizeClockLabel(rawLbl) || fallbackLabelForIana(iana);
    const dedupKey = `${label.toLowerCase()}|${iana}`;
    if (seen.has(dedupKey)) continue;
    seen.add(dedupKey);
    out.push({ label, iana });
    if (out.length >= MAX_WORLD_CLOCKS) break;
  }
  return out;
}

export function serializeWorldClocksSpec(items: ReadonlyArray<WorldClockItemView>): string {
  return items
    .slice(0, MAX_WORLD_CLOCKS)
    .map((item) => {
      const cleaned = sanitizeClockLabel(item.label);
      return cleaned ? `${cleaned}|${item.iana}` : "";
    })
    .filter(Boolean)
    .join(";");
}
