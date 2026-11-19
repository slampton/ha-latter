/**
 * Hybrid typed Studio i18n runtime (`D-061`):
 * - Compile-time typed `t()` lookup against `EN_STRINGS` with runtime `<lang>.json` overlay support
 * - Preference label & canonical wire option localization (`tPrefLabel`, `tPrefOption`)
 * - Home Assistant Repairs `hass.localize` bridge (`localizeRepairIssue`)
 * - Home Assistant entity state formatter bridge (`formatHaEntityState`)
 */

import type { HassEntityState, HomeAssistant } from "../types.js";
import {
  buildStudioEnLocaleCatalog,
  EN_STRINGS,
  PREF_LABELS,
  PREF_OPTION_LABELS,
  type StudioTranslationKey,
} from "./en.js";

export {
  buildStudioEnLocaleCatalog,
  EN_STRINGS,
  PREF_LABELS,
  PREF_OPTION_LABELS,
  type StudioTranslationKey,
};

type HassI18nCapable = HomeAssistant & {
  localize?: (key: string, placeholders?: Record<string, string | number>) => string;
  formatEntityState?: (stateObj: HassEntityState, state?: string) => string;
};

const PLACEHOLDER_RE = /\{([A-Za-z0-9_]+)\}/g;

function interpolate(
  template: string,
  vars?: Readonly<Record<string, string | number>>,
): string {
  if (!vars) return template;
  return template.replace(PLACEHOLDER_RE, (match, name: string) => {
    const val = vars[name];
    return val === undefined || val === null ? match : String(val);
  });
}

export function t(
  key: StudioTranslationKey,
  vars?: Readonly<Record<string, string | number>>,
  overlay?: Readonly<Record<string, string>> | null,
): string {
  const raw = (overlay && overlay[key]) || EN_STRINGS[key] || key;
  return interpolate(raw, vars);
}

export function tPrefLabel(
  key: string,
  fallback?: string,
  overlay?: Readonly<Record<string, string>> | null,
): string {
  const cleanKey = String(key || "").trim();
  if (!cleanKey) return fallback || "—";
  const overlayVal = overlay?.[`pref.${cleanKey}`];
  if (overlayVal) return overlayVal;
  const known = PREF_LABELS[cleanKey];
  if (known) return known;
  if (fallback && fallback.trim()) return fallback.trim();
  const humanized = cleanKey.replace(/_/g, " ").trim();
  return humanized ? humanized.charAt(0).toUpperCase() + humanized.slice(1) : "—";
}

export function tPrefOption(
  prefKey: string,
  rawOption: string,
  overlay?: Readonly<Record<string, string>> | null,
): string {
  const opt = String(rawOption ?? "");
  if (!opt) return "";
  if (overlay) {
    const scoped = prefKey ? overlay[`pref_option.${prefKey}.${opt}`] : undefined;
    if (scoped) return scoped;
    const generic = overlay[`pref_option.${opt}`];
    if (generic) return generic;
  }
  return PREF_OPTION_LABELS[opt] ?? opt;
}

export function localizeRepairIssue(
  hass: HomeAssistant | null | undefined,
  issueKey: string,
  placeholders?: Readonly<Record<string, string | number>>,
  fallback?: string,
): string {
  const cleanKey = String(issueKey || "").trim();
  const h = hass as HassI18nCapable | null | undefined;
  if (cleanKey && typeof h?.localize === "function") {
    const params = placeholders ? { ...placeholders } : undefined;
    for (const suffix of [".description", ".title", ""]) {
      const haKey = `component.latter.issues.${cleanKey}${suffix}`;
      try {
        const localized = h.localize(haKey, params);
        if (localized && localized !== haKey && !localized.startsWith("component.latter.")) {
          return localized;
        }
      } catch {
        // Fall through to Studio catalog / fallback string.
      }
    }
  }
  if (fallback) return fallback;
  if (!cleanKey) return t("issue.generic", { label: "issue" });
  const detail = placeholders?.detail !== undefined ? String(placeholders.detail) : "";
  if (cleanKey === "missing_mapped_entity") {
    return detail
      ? t("issue.missing_mapped_entity_detail", { detail })
      : t("issue.missing_mapped_entity");
  }
  if (cleanKey === "device_crashed") {
    if (detail === "stall") return t("issue.device_crashed_stall");
    return detail
      ? t("issue.device_crashed_detail", { detail })
      : t("issue.device_crashed");
  }
  const catalogKey = `issue.${cleanKey}` as StudioTranslationKey;
  if (catalogKey in EN_STRINGS) {
    return t(catalogKey, placeholders);
  }
  return t("issue.generic", { label: cleanKey.replace(/_/g, " ") });
}

export function formatHaEntityState(
  hass: HomeAssistant | null | undefined,
  entityId: string,
  option?: string,
): string {
  const cleanId = String(entityId || "").trim();
  const stateObj = cleanId ? hass?.states?.[cleanId] : undefined;
  const h = hass as HassI18nCapable | null | undefined;
  if (stateObj && typeof h?.formatEntityState === "function") {
    try {
      const formatted = h.formatEntityState(stateObj, option);
      if (formatted) return formatted;
    } catch {
      // Fall back to raw state string below.
    }
  }
  const raw = option ?? stateObj?.state ?? "";
  return raw || "—";
}
