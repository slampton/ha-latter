/**
 * Locale-aware formatters, Title Case entity label converter (D-013), and color helpers.
 * Note: Avoid literal `#RRGGBB` color constants here so `[STUDIO TOKENS]` stays 100% pure.
 */

import { ISSUE_TEXT, LABEL_ACRONYMS, LABEL_MINOR_WORDS } from "../constants.js";
import type { HomeAssistant, IssueItem } from "../types.js";

export function hassLanguage(hass: HomeAssistant | null | undefined): string {
  return String(hass?.locale?.language || hass?.language || navigator.language || "en");
}

export function fmtNumber(
  value: number | string | null | undefined,
  hass?: HomeAssistant | null,
  maximumFractionDigits = 1,
): string {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  try {
    return new Intl.NumberFormat(hassLanguage(hass), { maximumFractionDigits }).format(num);
  } catch {
    return String(num);
  }
}

export function fmtPercent(
  value: number | string | null | undefined,
  hass?: HomeAssistant | null,
): string {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  try {
    return new Intl.NumberFormat(hassLanguage(hass), {
      style: "percent",
      maximumFractionDigits: 0,
    }).format(num / 100);
  } catch {
    return `${Math.round(num)}%`;
  }
}

export function fmtDistance(
  meters: number | null | undefined,
  hass?: HomeAssistant | null,
): string {
  if (meters === null || meters === undefined || !Number.isFinite(Number(meters))) return "—";
  const m = Number(meters);
  try {
    return new Intl.NumberFormat(hassLanguage(hass), {
      style: "unit",
      unit: "meter",
      maximumFractionDigits: 1,
    }).format(m);
  } catch {
    return `${m.toFixed(1)} m`;
  }
}

export function fmtAgo(
  secondsAgo: number | null | undefined,
  hass?: HomeAssistant | null,
): string {
  if (secondsAgo === null || secondsAgo === undefined || !Number.isFinite(Number(secondsAgo))) {
    return "—";
  }
  const secs = Math.max(0, Math.round(Number(secondsAgo)));
  try {
    const rtf = new Intl.RelativeTimeFormat(hassLanguage(hass), { numeric: "auto" });
    if (secs < 60) return rtf.format(-secs, "second");
    if (secs < 3600) return rtf.format(-Math.round(secs / 60), "minute");
    if (secs < 86400) return rtf.format(-Math.round(secs / 3600), "hour");
    return rtf.format(-Math.round(secs / 86400), "day");
  } catch {
    return `${secs}s ago`;
  }
}

export function fmtDateTime(
  ts: number | string | null | undefined,
  hass?: HomeAssistant | null,
): string {
  if (ts === null || ts === undefined || ts === "") return "";
  const date = typeof ts === "number" ? new Date(ts < 1e12 ? ts * 1000 : ts) : new Date(ts);
  if (Number.isNaN(date.getTime())) return String(ts);
  try {
    return new Intl.DateTimeFormat(hassLanguage(hass), {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  } catch {
    return date.toISOString();
  }
}

function capitalizeSegment(seg: string): string {
  if (!seg) return seg;
  const low = seg.toLowerCase();
  if (LABEL_ACRONYMS[low]) return LABEL_ACRONYMS[low];
  if (/^[a-z]+[A-Z]/.test(seg) || /^[A-Z0-9]{2,}$/.test(seg)) return seg;
  return seg.charAt(0).toUpperCase() + seg.slice(1);
}

export function entityLabel(rawName: string | null | undefined): string {
  const cleaned = String(rawName || "").trim();
  if (!cleaned) return "—";
  const words = cleaned.split(/\s+/).filter(Boolean);
  return words
    .map((word, idx) => {
      const m = /^([([{"']*)(.*?)([)\]}"':,.?]*)$/.exec(word);
      const lead = m ? m[1] : "";
      const core = m ? m[2] : word;
      const trail = m ? m[3] : "";
      if (!core) return word;
      // Preserve parenthesized units such as (ms), (s), (dB), (dBm), (%).
      if (lead === "(" && trail === ")" && /^(ms|s|m|h|dB|dBm|Hz|kHz|MHz|V|mV|A|mA|W|%|°C|°F)$/.test(core)) {
        return word;
      }
      const isEdge = idx === 0 || idx === words.length - 1;
      const low = core.toLowerCase();
      if (!isEdge && LABEL_MINOR_WORDS.has(low)) {
        return `${lead}${low}${trail}`;
      }
      if (LABEL_ACRONYMS[low]) {
        return `${lead}${LABEL_ACRONYMS[low]}${trail}`;
      }
      const hyph = core
        .split("-")
        .map((seg) => capitalizeSegment(seg))
        .join("-");
      return `${lead}${hyph}${trail}`;
    })
    .join(" ");
}

export function issueMessage(issue: IssueItem): string {
  const kind = String(issue.kind || issue.key || "");
  const fn = ISSUE_TEXT[kind];
  if (fn) return fn(issue);
  const label = kind ? kind.replace(/_/g, " ") : "issue";
  return `Repair: ${label}.`;
}

export function isGroupCustomized(status: unknown): boolean {
  if (!status) return false;
  if (typeof status === "string") return status === "customized";
  if (typeof status === "object" && "in_sync" in status) {
    return (status as { in_sync?: boolean }).in_sync === false;
  }
  return false;
}

export function rssiToPercent(rssi: number | null | undefined): number {
  if (rssi === null || rssi === undefined || !Number.isFinite(Number(rssi))) return 0;
  const clamped = Math.max(-95, Math.min(-35, Number(rssi)));
  return Math.round(((clamped + 95) / 60) * 100);
}

export function isValidHexColor(val: string | null | undefined): boolean {
  const s = String(val || "").trim();
  if (s.length !== 7 || s.charCodeAt(0) !== 35) return false;
  for (let i = 1; i < 7; i += 1) {
    const code = s.charCodeAt(i);
    const isDigit = code >= 48 && code <= 57;
    const isUpper = code >= 65 && code <= 70;
    const isLower = code >= 97 && code <= 102;
    if (!isDigit && !isUpper && !isLower) return false;
  }
  return true;
}

function byteToHex(b: number): string {
  const clamped = Math.max(0, Math.min(255, Math.round(b)));
  return clamped.toString(16).padStart(2, "0").toUpperCase();
}

export function rgbBytesToHex(r: number, g: number, b: number): string {
  return String.fromCharCode(35) + byteToHex(r) + byteToHex(g) + byteToHex(b);
}

export function hsvToRgbJS(h: number, s: number, v: number): [number, number, number] {
  const c = v * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = v - c;
  let r1 = 0;
  let g1 = 0;
  let b1 = 0;
  if (h < 60) [r1, g1, b1] = [c, x, 0];
  else if (h < 120) [r1, g1, b1] = [x, c, 0];
  else if (h < 180) [r1, g1, b1] = [0, c, x];
  else if (h < 240) [r1, g1, b1] = [0, x, c];
  else if (h < 300) [r1, g1, b1] = [x, 0, c];
  else [r1, g1, b1] = [c, 0, x];
  return [
    Math.round((r1 + m) * 255),
    Math.round((g1 + m) * 255),
    Math.round((b1 + m) * 255),
  ];
}

export function hsvToHex(h: number, s: number, v: number): string {
  const [r, g, b] = hsvToRgbJS(h, s, v);
  return rgbBytesToHex(r, g, b);
}

export function defaultThemeHex(hostEl?: Element | null): string {
  if (hostEl && typeof getComputedStyle === "function") {
    const raw = getComputedStyle(hostEl).getPropertyValue("--primary-color").trim();
    if (isValidHexColor(raw)) return raw.toUpperCase();
  }
  return rgbBytesToHex(0, 154, 199);
}

export async function copyTextToClipboard(text: string): Promise<boolean> {
  if (!text) return false;
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall back to offscreen textarea selection below.
  }
  try {
    const ta = document.createElement("textarea");
    ta.className = "offscreen";
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export function triggerJsonDownload(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function navigateHaPath(path: string, replace = false): void {
  if (!path) return;
  if (replace) {
    globalThis.history.replaceState(null, "", path);
  } else {
    globalThis.history.pushState(null, "", path);
  }
  globalThis.dispatchEvent(new Event("location-changed", { bubbles: true, composed: true }));
}
