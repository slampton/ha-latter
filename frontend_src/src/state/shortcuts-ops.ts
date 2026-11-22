/**
 * Unified `createTokenListOps` CSV pill factory & Shortcut (`dock_items` / `pinned_items`)
 * normalization and modal operations.
 */

import {
  ACTIVITY_SOURCES_CATALOG,
  AREA_CATEGORIES_CATALOG,
  type CatalogItem,
  DEFAULT_ACTIVITY_SOURCES_TOKENS,
  DEFAULT_AREA_CATEGORIES_TOKENS,
  DEFAULT_DOCK_ROUTES_TOKENS,
  DEFAULT_GAMES_ITEMS_TOKENS,
  DEFAULT_HOME_CATEGORIES_TOKENS,
  DEFAULT_TOOLS_ITEMS_TOKENS,
  GAMES_ITEMS_CATALOG,
  HOME_CATEGORIES_CATALOG,
  MAX_DOCK_ITEMS,
  MAX_PINNED_ITEMS,
  NATIVE_DOCK_APP_TOKENS,
  SHORTCUT_LABEL_MAX,
  SHORTCUT_ROUTES_CATALOG,
  TOOLS_ITEMS_CATALOG,
} from "../constants.js";
import {
  ensureMdiCatalogLoaded,
  isKnownMdiIcon,
  normalizeMdiIconSlug,
  SHORTCUT_DOMAIN_ACTIONS,
} from "../mdi-catalog.js";
import type { ShortcutItem } from "../types.js";
import {
  isCatalogItemSupported,
  type StudioStoreContext,
  type TokenListKey,
  type TokenListOps,
} from "./store-types.js";

export interface TokenListSpec {
  readonly key: TokenListKey;
  readonly catalog: ReadonlyArray<CatalogItem>;
  readonly defaultTokens: ReadonlyArray<string>;
  readonly minRequired: number;
  readonly noun: string;
  readonly allowEmpty: boolean;
  readonly checkPrefFallback: boolean;
}

export const TOKEN_LIST_SPECS: Readonly<Record<TokenListKey, TokenListSpec>> = {
  area_categories: {
    key: "area_categories",
    catalog: AREA_CATEGORIES_CATALOG,
    defaultTokens: DEFAULT_AREA_CATEGORIES_TOKENS,
    minRequired: 1,
    noun: "Area category",
    allowEmpty: false,
    checkPrefFallback: false,
  },
  home_categories: {
    key: "home_categories",
    catalog: HOME_CATEGORIES_CATALOG,
    defaultTokens: DEFAULT_HOME_CATEGORIES_TOKENS,
    minRequired: 1,
    noun: "Home category",
    allowEmpty: false,
    checkPrefFallback: false,
  },
  tools_items: {
    key: "tools_items",
    catalog: TOOLS_ITEMS_CATALOG,
    defaultTokens: DEFAULT_TOOLS_ITEMS_TOKENS,
    minRequired: 1,
    noun: "tool",
    allowEmpty: false,
    checkPrefFallback: true,
  },
  games_items: {
    key: "games_items",
    catalog: GAMES_ITEMS_CATALOG,
    defaultTokens: DEFAULT_GAMES_ITEMS_TOKENS,
    minRequired: 1,
    noun: "game",
    allowEmpty: false,
    checkPrefFallback: true,
  },
  activity_sources: {
    key: "activity_sources",
    catalog: ACTIVITY_SOURCES_CATALOG,
    defaultTokens: DEFAULT_ACTIVITY_SOURCES_TOKENS,
    minRequired: 0,
    noun: "source",
    allowEmpty: true,
    checkPrefFallback: false,
  },
};

export function createTokenListOps(store: StudioStoreContext, spec: TokenListSpec): TokenListOps {
  const knownByToken = new Map(spec.catalog.map((c) => [c.token, c]));

  const isTokenSupportedOnActive = (token: string): boolean => {
    const item = knownByToken.get(token);
    return item ? isCatalogItemSupported(item, store.state?.capabilities) : false;
  };

  const getEnabled = (): string[] => {
    const cfgVal = store.state?.config?.[spec.key];
    const prefVal = spec.checkPrefFallback ? store.entity.getPref(spec.key)?.value : undefined;
    const raw = cfgVal ?? prefVal;
    if (raw === undefined || raw === null) {
      return [...spec.defaultTokens];
    }
    const rawStr = String(raw);
    if (!rawStr.trim()) {
      return spec.allowEmpty ? [] : [...spec.defaultTokens];
    }
    const parsed = rawStr
      .split(",")
      .map((s) => s.trim().toLowerCase())
      .filter((s, i, arr) => Boolean(s) && knownByToken.has(s) && arr.indexOf(s) === i);
    if (parsed.length === 0 && !spec.allowEmpty) {
      return [...spec.defaultTokens];
    }
    return parsed;
  };

  const toggle = (rawToken: string, forceEnabled?: boolean): void => {
    const token = String(rawToken || "").trim().toLowerCase();
    if (!knownByToken.has(token)) return;
    const current = getEnabled();
    const idx = current.indexOf(token);
    const currentlyOn = idx >= 0;
    const wantOn = forceEnabled !== undefined ? Boolean(forceEnabled) : !currentlyOn;
    if (wantOn === currentlyOn) return;

    if (!wantOn) {
      if (spec.minRequired > 0) {
        const visibleEnabled = current.filter((t) => isTokenSupportedOnActive(t));
        if (
          current.length <= spec.minRequired ||
          (isTokenSupportedOnActive(token) && visibleEnabled.length <= spec.minRequired)
        ) {
          store.showToast(store.t("common.keep_one_enabled", { noun: spec.noun }), true);
          return;
        }
      }
      current.splice(idx, 1);
    } else {
      current.push(token);
    }
    store.entity.stageDeviceSetting(spec.key, current.join(","));
  };

  const move = (rawToken: string, delta: -1 | 1): void => {
    const token = String(rawToken || "").trim().toLowerCase();
    const current = getEnabled();
    const idx = current.indexOf(token);
    if (idx < 0) return;
    let swapIdx = idx + delta;
    while (swapIdx >= 0 && swapIdx < current.length) {
      const candidate = current[swapIdx];
      if (candidate !== undefined && isTokenSupportedOnActive(candidate)) {
        break;
      }
      swapIdx += delta;
    }
    if (swapIdx < 0 || swapIdx >= current.length) return;
    const curVal = current[idx];
    const swapVal = current[swapIdx];
    if (curVal === undefined || swapVal === undefined) return;
    current[idx] = swapVal;
    current[swapIdx] = curVal;
    store.entity.stageDeviceSetting(spec.key, current.join(","));
  };

  const reorder = (fromEnabledIndex: number, toEnabledIndex: number): void => {
    const current = getEnabled();
    const supportedIndices: number[] = [];
    for (let i = 0; i < current.length; i += 1) {
      const tok = current[i];
      if (tok !== undefined && isTokenSupportedOnActive(tok)) {
        supportedIndices.push(i);
      }
    }
    if (
      fromEnabledIndex < 0 ||
      toEnabledIndex < 0 ||
      fromEnabledIndex >= supportedIndices.length ||
      toEnabledIndex >= supportedIndices.length ||
      fromEnabledIndex === toEnabledIndex
    ) {
      return;
    }
    const visibleTokens = supportedIndices
      .map((idx) => current[idx])
      .filter((tok): tok is string => tok !== undefined);
    const [moved] = visibleTokens.splice(fromEnabledIndex, 1);
    if (moved === undefined) return;
    visibleTokens.splice(toEnabledIndex, 0, moved);
    for (let j = 0; j < supportedIndices.length; j += 1) {
      const targetIdx = supportedIndices[j];
      const nextTok = visibleTokens[j];
      if (targetIdx !== undefined && nextTok !== undefined) {
        current[targetIdx] = nextTok;
      }
    }
    store.entity.stageDeviceSetting(spec.key, current.join(","));
  };

  return { getEnabled, toggle, move, reorder };
}

export function sanitizeShortcutLabel(raw: unknown): string {
  const str = String(raw ?? "");
  let collapsed = "";
  let prevSpace = true;
  for (const ch of str) {
    const code = ch.charCodeAt(0);
    if (
      code < 0x20 ||
      code === 0x7f ||
      ch === "|" ||
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
  const trimmed = collapsed.trim();
  return trimmed.length > SHORTCUT_LABEL_MAX
    ? trimmed.slice(0, SHORTCUT_LABEL_MAX).trimEnd()
    : trimmed;
}

export function isProtectedNativeDockItem(item: ShortcutItem): boolean {
  return (
    item.kind === "route" &&
    NATIVE_DOCK_APP_TOKENS.includes(item.target) &&
    !item.label &&
    !item.icon
  );
}

export function defaultDockShortcutItems(): ShortcutItem[] {
  return DEFAULT_DOCK_ROUTES_TOKENS.map((tok) => ({
    kind: "route" as const,
    target: tok,
    action: "",
    label: "",
    icon: "",
    confirm: false,
  }));
}

export function normalizeShortcutArray(raw: unknown, isDock: boolean): ShortcutItem[] {
  if (!Array.isArray(raw)) {
    return isDock ? defaultDockShortcutItems() : [];
  }
  const knownRoutes = new Map(SHORTCUT_ROUTES_CATALOG.map((r) => [r.token, r]));
  const maxItems = isDock ? MAX_DOCK_ITEMS : MAX_PINNED_ITEMS;
  const out: ShortcutItem[] = [];
  const seen = new Set<string>();
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const rec = entry as Record<string, unknown>;
    const kind = String(rec.kind || "").trim().toLowerCase();
    if (kind === "route") {
      const target = String(rec.target || "").trim().toLowerCase();
      if (isDock && (target === "settings:root" || target === "app:settings")) {
        continue;
      }
      const spec = knownRoutes.get(target);
      if (!spec || (!isDock && spec.dockOnly)) continue;
      const dedupKey = `route|${target}|`;
      if (seen.has(dedupKey)) continue;
      seen.add(dedupKey);
      const isNativeDockApp = isDock && NATIVE_DOCK_APP_TOKENS.includes(target);
      out.push({
        kind: "route",
        target,
        action: "",
        label: isNativeDockApp ? "" : sanitizeShortcutLabel(rec.label),
        icon: isNativeDockApp ? "" : normalizeMdiIconSlug(rec.icon),
        confirm: false,
      });
    } else if (kind === "entity") {
      const target = String(rec.target || "").trim().toLowerCase();
      const dotIdx = target.indexOf(".");
      if (dotIdx <= 0) continue;
      const domain = target.slice(0, dotIdx);
      const validActions = SHORTCUT_DOMAIN_ACTIONS[domain];
      const defaultAct = validActions?.[0];
      if (!validActions || !defaultAct) continue;
      const rawAct = String(rec.action || "").trim().toLowerCase();
      const action = validActions.some((a) => a.action === rawAct)
        ? rawAct
        : defaultAct.action;
      const dedupKey = `entity|${target}|${action}`;
      if (seen.has(dedupKey)) continue;
      seen.add(dedupKey);
      out.push({
        kind: "entity",
        target,
        action,
        label: sanitizeShortcutLabel(rec.label),
        icon: normalizeMdiIconSlug(rec.icon),
        confirm: rec.confirm === undefined ? isDock : Boolean(rec.confirm),
      });
    }
    if (out.length >= maxItems) break;
  }
  return out;
}

export function openShortcutModalOp(
  store: StudioStoreContext,
  listKey: "dock_items" | "pinned_items",
  editIndex: number | null = null,
): void {
  const isDock = listKey === "dock_items";
  if (
    listKey === "pinned_items" &&
    store.appConfigModal?.open &&
    store.appConfigModal.app === "pinned"
  ) {
    store.returnToPinnedModal = true;
    store.appConfigModal = { open: false, app: null };
  } else {
    store.returnToPinnedModal = false;
  }
  const current = isDock ? store.entity.getDockItems() : store.entity.getPinnedItems();
  const caps = store.state?.capabilities;
  const compatibleRoutes = SHORTCUT_ROUTES_CATALOG.filter((r) => {
    if (!isDock && r.dockOnly) return false;
    if (isDock && (r.token === "settings:root" || NATIVE_DOCK_APP_TOKENS.includes(r.token))) {
      return false;
    }
    return isCatalogItemSupported(r, caps);
  });
  const firstRoute = compatibleRoutes[0]?.token || "weather:moon";
  const entities = store.state?.catalog?.shortcut_entities || [];
  const firstEnt = entities[0];
  const firstDomain = firstEnt ? firstEnt.domain : "light";
  const firstAction = SHORTCUT_DOMAIN_ACTIONS[firstDomain]?.[0]?.action || "toggle";

  const existing =
    editIndex !== null && editIndex >= 0 && editIndex < current.length
      ? current[editIndex]
      : undefined;
  if (existing && editIndex !== null) {
    if (existing.kind === "entity") {
      const dom = existing.target.split(".", 1)[0] || firstDomain;
      store.shortcutModal = {
        open: true,
        listKey,
        editIndex,
        kind: "entity",
        routeTarget: firstRoute,
        entityDomainFilter: "all",
        entitySearch: "",
        entityTarget: existing.target,
        action: existing.action || SHORTCUT_DOMAIN_ACTIONS[dom]?.[0]?.action || "toggle",
        label: existing.label,
        icon: existing.icon,
        iconSearch: "",
        confirm: Boolean(existing.confirm),
      };
    } else {
      store.shortcutModal = {
        open: true,
        listKey,
        editIndex,
        kind: "route",
        routeTarget: existing.target,
        entityDomainFilter: "all",
        entitySearch: "",
        entityTarget: firstEnt?.id || "",
        action: firstAction,
        label: existing.label,
        icon: existing.icon,
        iconSearch: "",
        confirm: isDock,
      };
    }
  } else {
    store.shortcutModal = {
      open: true,
      listKey,
      editIndex: null,
      kind: isDock ? "route" : entities.length > 0 ? "entity" : "route",
      routeTarget: firstRoute,
      entityDomainFilter: "all",
      entitySearch: "",
      entityTarget: firstEnt?.id || "",
      action: firstAction,
      label: "",
      icon: "",
      iconSearch: "",
      confirm: isDock,
    };
  }
  store.host.requestUpdate();
  void ensureMdiCatalogLoaded()
    .then(() => {
      if (store.shortcutModal.open) {
        store.host.requestUpdate();
      }
    })
    .catch(() => {
      // Curated icons remain synchronously available offline.
    });
}

export function saveShortcutModalOp(store: StudioStoreContext): void {
  const modal = store.shortcutModal;
  const isDock = modal.listKey === "dock_items";
  const maxItems = isDock ? MAX_DOCK_ITEMS : MAX_PINNED_ITEMS;
  const current = (isDock ? store.entity.getDockItems() : store.entity.getPinnedItems()).map(
    (it) => ({ ...it }),
  );

  if (modal.editIndex === null && current.length >= maxItems) {
    store.showToast(
      `${isDock ? "App Dock" : "Pinned app"} supports up to ${maxItems} shortcuts`,
      true,
    );
    return;
  }

  const rawSelectedIcon = modal.icon.trim();
  const rawTypedIcon = modal.iconSearch.trim();
  let cleanIcon = "";
  if (rawSelectedIcon) {
    const candidate = normalizeMdiIconSlug(rawSelectedIcon);
    if (!candidate || !isKnownMdiIcon(candidate)) {
      store.showToast("Select a supported Material Design Icon", true);
      return;
    }
    cleanIcon = candidate;
  } else if (rawTypedIcon) {
    const candidate = normalizeMdiIconSlug(rawTypedIcon);
    if (candidate && isKnownMdiIcon(candidate)) {
      cleanIcon = candidate;
    } else {
      store.showToast("Click one of the matching icons below (or clear the icon search)", true);
      return;
    }
  }
  const cleanLabel = sanitizeShortcutLabel(modal.label);

  let built: ShortcutItem;
  if (modal.kind === "route") {
    const routeTok = modal.routeTarget.trim().toLowerCase();
    const spec = SHORTCUT_ROUTES_CATALOG.find((r) => r.token === routeTok);
    if (
      !spec ||
      (!isDock && spec.dockOnly) ||
      (isDock && (routeTok === "settings:root" || NATIVE_DOCK_APP_TOKENS.includes(routeTok))) ||
      !isCatalogItemSupported(spec, store.state?.capabilities)
    ) {
      store.showToast("Select an app or page to pin", true);
      return;
    }
    built = {
      kind: "route",
      target: routeTok,
      action: "",
      label: cleanLabel,
      icon: cleanIcon,
      confirm: false,
    };
  } else {
    const entId = modal.entityTarget.trim().toLowerCase();
    const dotIdx = entId.indexOf(".");
    if (dotIdx <= 0) {
      store.showToast("Select a Home Assistant entity", true);
      return;
    }
    const dom = entId.slice(0, dotIdx);
    const validActs = SHORTCUT_DOMAIN_ACTIONS[dom] || [];
    const act = validActs.some((a) => a.action === modal.action)
      ? modal.action
      : validActs[0]?.action || "";
    if (!act) {
      store.showToast(`Unsupported entity domain '${dom}'`, true);
      return;
    }
    built = {
      kind: "entity",
      target: entId,
      action: act,
      label: cleanLabel,
      icon: cleanIcon,
      confirm: Boolean(modal.confirm),
    };
  }

  const dupIdx = current.findIndex(
    (it, idx) =>
      idx !== modal.editIndex &&
      it.kind === built.kind &&
      it.target === built.target &&
      it.action === built.action,
  );
  if (dupIdx >= 0) {
    store.showToast("That shortcut is already in this list", true);
    return;
  }

  if (modal.editIndex !== null && modal.editIndex >= 0 && modal.editIndex < current.length) {
    current[modal.editIndex] = built;
  } else {
    current.push(built);
  }

  const reopenPinned = Boolean(store.returnToPinnedModal);
  store.returnToPinnedModal = false;
  store.shortcutModal = { ...store.shortcutModal, open: false };
  if (reopenPinned) {
    store.appConfigModal = { open: true, app: "pinned" };
  }
  store.entity.stageDeviceSetting(modal.listKey, current);
}
