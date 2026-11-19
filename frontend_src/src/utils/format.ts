/**
 * Locale-aware formatters (`hass.locale` number/time/date/weekday), cached `Intl` instances,
 * entity label humanizer, color helpers, and shadow-safe clipboard / download helpers.
 * Note: Avoid literal `#RRGGBB` color constants here so `[STUDIO TOKENS]` stays 100% pure.
 */

import { LABEL_ACRONYMS } from "../constants.js";
import { localizeRepairIssue } from "../i18n/index.js";
import type { HomeAssistant, IssueItem } from "../types.js";

export interface HassLocaleInfo {
  language?: string;
  number_format?: "language" | "system" | "comma_decimal" | "decimal_comma" | "space_comma" | "none" | string;
  time_format?: "language" | "system" | "am_pm" | "24" | string;
  date_format?: "language" | "system" | "DMY" | "MDY" | "YMD" | string;
  time_zone?: "local" | "server" | string;
  first_weekday?:
    | "language"
    | "monday"
    | "tuesday"
    | "wednesday"
    | "thursday"
    | "friday"
    | "saturday"
    | "sunday"
    | string;
}

type HassWithLocale = HomeAssistant & { locale?: HassLocaleInfo };

const MAX_FORMATTER_CACHE = 64;
const NUMBER_FMT_CACHE = new Map<string, Intl.NumberFormat>();
const REL_TIME_FMT_CACHE = new Map<string, Intl.RelativeTimeFormat>();
const DATE_TIME_FMT_CACHE = new Map<string, Intl.DateTimeFormat>();

function setBoundedCache<V>(cache: Map<string, V>, key: string, val: V): V {
  if (cache.size >= MAX_FORMATTER_CACHE) {
    const oldest = cache.keys().next().value;
    if (oldest !== undefined) {
      cache.delete(oldest);
    }
  }
  cache.set(key, val);
  return val;
}

function getLocaleObj(hass: HomeAssistant | null | undefined): HassLocaleInfo | undefined {
  return (hass as HassWithLocale | null | undefined)?.locale;
}

export function hassLanguage(hass: HomeAssistant | null | undefined): string {
  const navLang = typeof navigator !== "undefined" ? navigator.language : "";
  return String(getLocaleObj(hass)?.language || hass?.language || navLang || "en");
}

function resolveNumberLocaleAndGrouping(
  hass: HomeAssistant | null | undefined,
): { locale: string | undefined; useGrouping: boolean | undefined } {
  const nf = getLocaleObj(hass)?.number_format;
  switch (nf) {
    case "comma_decimal":
      return { locale: "en-US", useGrouping: true };
    case "decimal_comma":
      return { locale: "de-DE", useGrouping: true };
    case "space_comma":
      return { locale: "fr-FR", useGrouping: true };
    case "none":
      return { locale: hassLanguage(hass), useGrouping: false };
    case "system":
      return { locale: undefined, useGrouping: undefined };
    default:
      return { locale: hassLanguage(hass), useGrouping: undefined };
  }
}

function getNumberFormatter(
  locale: string | undefined,
  opts: Intl.NumberFormatOptions,
): Intl.NumberFormat {
  const key = `${locale || "sys"}|${opts.style || "decimal"}|${opts.unit || ""}|${opts.maximumFractionDigits ?? ""}|${String(opts.useGrouping ?? "")}`;
  const cached = NUMBER_FMT_CACHE.get(key);
  if (cached) return cached;
  return setBoundedCache(NUMBER_FMT_CACHE, key, new Intl.NumberFormat(locale, opts));
}

function getRelativeTimeFormatter(locale: string): Intl.RelativeTimeFormat {
  const cached = REL_TIME_FMT_CACHE.get(locale);
  if (cached) return cached;
  return setBoundedCache(
    REL_TIME_FMT_CACHE,
    locale,
    new Intl.RelativeTimeFormat(locale, { numeric: "auto" }),
  );
}

function resolveDateTimeLocale(hass: HomeAssistant | null | undefined): string | undefined {
  const df = getLocaleObj(hass)?.date_format;
  switch (df) {
    case "DMY":
      return "en-GB";
    case "MDY":
      return "en-US";
    case "YMD":
      return "sv-SE";
    case "system":
      return undefined;
    default:
      return hassLanguage(hass);
  }
}

function resolveHour12(hass: HomeAssistant | null | undefined): boolean | undefined {
  const tf = getLocaleObj(hass)?.time_format;
  if (tf === "am_pm") return true;
  if (tf === "24") return false;
  return undefined;
}

function getDateTimeFormatter(
  locale: string | undefined,
  opts: Intl.DateTimeFormatOptions,
): Intl.DateTimeFormat {
  const key = `${locale || "sys"}|${opts.timeZone || "local"}|${String(opts.hour12 ?? "auto")}`;
  const cached = DATE_TIME_FMT_CACHE.get(key);
  if (cached) return cached;
  return setBoundedCache(DATE_TIME_FMT_CACHE, key, new Intl.DateTimeFormat(locale, opts));
}

export function hassFirstWeekday(hass?: HomeAssistant | null): "Sunday" | "Monday" {
  const fw = String(getLocaleObj(hass)?.first_weekday || "language").toLowerCase();
  if (fw === "monday") return "Monday";
  if (fw === "sunday") return "Sunday";
  try {
    const loc = new Intl.Locale(hassLanguage(hass)) as Intl.Locale & {
      getWeekInfo?: () => { firstDay?: number };
      weekInfo?: { firstDay?: number };
    };
    const firstDay = loc.getWeekInfo?.()?.firstDay ?? loc.weekInfo?.firstDay;
    if (firstDay === 1) return "Monday";
  } catch {
    // Default to Sunday when Intl.Locale weekInfo is unavailable.
  }
  return "Sunday";
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
    const { locale, useGrouping } = resolveNumberLocaleAndGrouping(hass);
    return getNumberFormatter(locale, { maximumFractionDigits, useGrouping }).format(num);
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
    const { locale, useGrouping } = resolveNumberLocaleAndGrouping(hass);
    return getNumberFormatter(locale, {
      style: "percent",
      maximumFractionDigits: 0,
      useGrouping,
    }).format(num / 100);
  } catch {
    return `${Math.round(num)}%`;
  }
}

export function fmtDistance(
  meters: number | null | undefined,
  hass?: HomeAssistant | null,
  feet?: number | null,
): string {
  const isImperial = hass?.config?.unit_system?.length === "mi";
  const { locale, useGrouping } = resolveNumberLocaleAndGrouping(hass);
  if (isImperial) {
    const hasFeet = feet !== null && feet !== undefined && Number.isFinite(Number(feet));
    const hasMeters = meters !== null && meters !== undefined && Number.isFinite(Number(meters));
    if (!hasFeet && !hasMeters) return "—";
    const ft = hasFeet ? Number(feet) : Number(meters) * 3.28084;
    try {
      return getNumberFormatter(locale, {
        style: "unit",
        unit: "foot",
        maximumFractionDigits: 1,
        useGrouping,
      }).format(ft);
    } catch {
      return `${ft.toFixed(1)} ft`;
    }
  }
  if (meters === null || meters === undefined || !Number.isFinite(Number(meters))) return "—";
  const m = Number(meters);
  try {
    return getNumberFormatter(locale, {
      style: "unit",
      unit: "meter",
      maximumFractionDigits: 1,
      useGrouping,
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
    const rtf = getRelativeTimeFormatter(hassLanguage(hass));
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
  const localeObj = getLocaleObj(hass);
  const useServerTz = localeObj?.time_zone === "server" && Boolean(hass?.config?.time_zone);
  const opts: Intl.DateTimeFormatOptions = {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  };
  const hour12 = resolveHour12(hass);
  if (hour12 !== undefined) {
    opts.hour12 = hour12;
  }
  if (useServerTz && hass?.config?.time_zone) {
    opts.timeZone = hass.config.time_zone;
  }
  try {
    return getDateTimeFormatter(resolveDateTimeLocale(hass), opts).format(date);
  } catch {
    return date.toISOString();
  }
}

function formatSentenceSegment(seg: string, isFirstWord: boolean): string {
  if (!seg) return seg;
  const low = seg.toLowerCase();
  if (LABEL_ACRONYMS[low]) return LABEL_ACRONYMS[low];
  if (/^[a-z]+[A-Z]/.test(seg) || /^[A-Z0-9]{2,}$/.test(seg)) return seg;
  if (isFirstWord) {
    return seg.charAt(0).toUpperCase() + seg.slice(1);
  }
  return seg;
}

/**
 * Formats an entity or setting label in Home Assistant Sentence case (`D-061`),
 * capitalizing the leading word while preserving acronyms (`BLE`, `Wi-Fi`, `ESPHome`, `PIN`)
 * and parenthesized units (`(ms)`, `(dBm)`, `(%)`).
 */
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
      if (
        lead === "(" &&
        trail === ")" &&
        /^(ms|s|m|h|d|dB|dBm|Hz|kHz|MHz|V|mV|A|mA|W|%|°C|°F)$/.test(core)
      ) {
        return word;
      }
      const low = core.toLowerCase();
      if (LABEL_ACRONYMS[low]) {
        return `${lead}${LABEL_ACRONYMS[low]}${trail}`;
      }
      const hyph = core
        .split("-")
        .map((seg, segIdx) => formatSentenceSegment(seg, idx === 0 && segIdx === 0))
        .join("-");
      return `${lead}${hyph}${trail}`;
    })
    .join(" ");
}

export function issueMessage(issue: IssueItem, hass?: HomeAssistant | null): string {
  const kind = String(issue.kind || issue.key || "");
  return localizeRepairIssue(
    hass,
    kind,
    issue.detail ? { detail: issue.detail } : undefined,
  );
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

function packRgbHex(r: number, g: number, b: number): string {
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
  return packRgbHex(r, g, b);
}

export function defaultThemeHex(hostEl?: Element | null): string {
  if (hostEl && typeof getComputedStyle === "function") {
    const raw = getComputedStyle(hostEl).getPropertyValue("--primary-color").trim();
    if (isValidHexColor(raw)) return raw.toUpperCase();
  }
  return packRgbHex(0, 154, 199);
}

export async function copyTextToClipboard(
  text: string,
  root?: ParentNode | null,
): Promise<boolean> {
  if (!text) return false;
  try {
    if (typeof navigator !== "undefined" && typeof navigator.clipboard?.writeText === "function") {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall back to shadow-safe offscreen textarea selection below.
  }
  if (typeof document === "undefined") return false;
  try {
    const shadow =
      (root && "querySelector" in root ? root : null) ??
      document.activeElement?.shadowRoot ??
      document.querySelector("latter-studio")?.shadowRoot ??
      null;
    const prevActive =
      (shadow && "activeElement" in shadow
        ? (shadow as ShadowRoot).activeElement
        : document.activeElement) as HTMLElement | null;
    const mountTarget: Node =
      shadow?.querySelector("dialog[open]") ?? shadow ?? document.body;

    const ta = document.createElement("textarea");
    ta.className = "offscreen";
    ta.setAttribute("aria-hidden", "true");
    ta.tabIndex = -1;
    ta.readOnly = true;
    ta.value = text;
    mountTarget.appendChild(ta);
    ta.focus({ preventScroll: true });
    ta.select();
    const ok = typeof document.execCommand === "function" && document.execCommand("copy");
    mountTarget.removeChild(ta);
    prevActive?.focus?.({ preventScroll: true });
    return Boolean(ok);
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
