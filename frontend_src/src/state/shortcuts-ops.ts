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
  MAX_PINNED_GRID_PAGES,
  MAX_PINNED_ITEMS,
  NATIVE_DOCK_APP_TOKENS,
  PINNED_GRID_MAX_COLS,
  PINNED_GRID_MAX_ROWS,
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
import type { ShortcutAccent, ShortcutBadgeStyle, ShortcutItem } from "../types.js";
import {
  canPlaceTile,
  deletePageAndShift,
  findFirstOpenSlot,
  normalizePinnedPageTitles,
  resolveDeviceGridDims,
  resolveTileGridLayout,
  withExplicitLayout,
} from "../utils/tile-grid.js";
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

const VALID_SHORTCUT_ACCENTS = new Set<ShortcutAccent>([
  "primary",
  "gold",
  "green",
  "red",
  "orange",
]);

export function normalizeShortcutBadgeStyle(raw: unknown): ShortcutBadgeStyle {
  const clean = String(raw ?? "").trim().toLowerCase();
  return clean === "inverted" ? "inverted" : "";
}

export function normalizeShortcutAccent(raw: unknown): ShortcutAccent {
  const clean = String(raw ?? "").trim().toLowerCase();
  if (!clean || clean === "default") return "";
  return VALID_SHORTCUT_ACCENTS.has(clean as ShortcutAccent)
    ? (clean as ShortcutAccent)
    : "";
}

export function shortcutBadgeClass(
  badgeStyle?: ShortcutBadgeStyle,
  accent?: ShortcutAccent,
): string {
  const classes = ["shortcut-icon-badge"];
  if (normalizeShortcutBadgeStyle(badgeStyle) === "inverted") {
    classes.push("badge-inverted");
  }
  const cleanAccent = normalizeShortcutAccent(accent);
  if (cleanAccent) {
    classes.push(`accent-${cleanAccent}`);
  }
  return classes.join(" ");
}

export function isProtectedNativeDockItem(item: ShortcutItem): boolean {
  return (
    item.kind === "route" &&
    NATIVE_DOCK_APP_TOKENS.includes(item.target) &&
    !item.label &&
    !item.icon &&
    !normalizeShortcutBadgeStyle(item.badge_style) &&
    !normalizeShortcutAccent(item.accent)
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
    badge_style: "",
    accent: "",
  }));
}

function applyNormalizedPinnedLayout(
  rec: Record<string, unknown>,
  target: ShortcutItem,
): void {
  const page = rec.page;
  const col = rec.col;
  const row = rec.row;
  if (
    typeof page === "number" &&
    Number.isInteger(page) &&
    page >= 0 &&
    page < MAX_PINNED_GRID_PAGES &&
    typeof col === "number" &&
    Number.isInteger(col) &&
    col >= 0 &&
    col < PINNED_GRID_MAX_COLS &&
    typeof row === "number" &&
    Number.isInteger(row) &&
    row >= 0 &&
    row < PINNED_GRID_MAX_ROWS
  ) {
    target.page = page;
    target.col = col;
    target.row = row;
  }
  const colSpan = rec.col_span;
  if (
    typeof colSpan === "number" &&
    Number.isInteger(colSpan) &&
    colSpan >= 2 &&
    colSpan <= PINNED_GRID_MAX_COLS
  ) {
    target.col_span = colSpan;
  }
  const rowSpan = rec.row_span;
  if (
    typeof rowSpan === "number" &&
    Number.isInteger(rowSpan) &&
    rowSpan >= 2 &&
    rowSpan <= PINNED_GRID_MAX_ROWS
  ) {
    target.row_span = rowSpan;
  }
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
      const built: ShortcutItem = {
        kind: "route",
        target,
        action: "",
        label: isNativeDockApp ? "" : sanitizeShortcutLabel(rec.label),
        icon: isNativeDockApp ? "" : normalizeMdiIconSlug(rec.icon),
        confirm: false,
        badge_style: isNativeDockApp ? "" : normalizeShortcutBadgeStyle(rec.badge_style),
        accent: isNativeDockApp ? "" : normalizeShortcutAccent(rec.accent),
      };
      if (!isDock) {
        applyNormalizedPinnedLayout(rec, built);
      }
      out.push(built);
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
      const built: ShortcutItem = {
        kind: "entity",
        target,
        action,
        label: sanitizeShortcutLabel(rec.label),
        icon: normalizeMdiIconSlug(rec.icon),
        confirm: rec.confirm === undefined ? isDock : Boolean(rec.confirm),
        badge_style: normalizeShortcutBadgeStyle(rec.badge_style),
        accent: normalizeShortcutAccent(rec.accent),
      };
      if (!isDock) {
        applyNormalizedPinnedLayout(rec, built);
      }
      out.push(built);
    }
    if (out.length >= maxItems) break;
  }
  return out;
}

export function savePinnedPageTitlesOp(
  store: StudioStoreContext,
  nextTitles: Record<string, string>,
): void {
  const cleanTitles = normalizePinnedPageTitles(nextTitles);
  store.entity.stageDeviceSetting("pinned_page_titles", cleanTitles);
}

export function savePinnedGridStateOp(
  store: StudioStoreContext,
  nextItems: ShortcutItem[],
  nextTitles?: Record<string, string>,
): void {
  const cleanItems = normalizeShortcutArray(nextItems, false);
  store.entity.stageDeviceSetting("pinned_items", cleanItems);
  if (nextTitles !== undefined) {
    store.entity.stageDeviceSetting(
      "pinned_page_titles",
      normalizePinnedPageTitles(nextTitles),
    );
  }
}

export function deletePinnedPageOp(store: StudioStoreContext, pageIdx: number): void {
  const dims = resolveDeviceGridDims(store.state?.capabilities);
  const pinnedItems = store.entity.getPinnedItems();
  const pageTitles = store.entity.getPinnedPageTitles();
  const prevResolved = resolveTileGridLayout(pinnedItems, dims.cols, dims.rows);
  const titleKeys = Object.keys(pageTitles);
  const prevMaxTitlePage = titleKeys.reduce((m, k) => Math.max(m, Number(k) || 0), 0);
  const prevBasePages = Math.max(
    1,
    prevResolved.pageCount,
    titleKeys.length > 0 ? prevMaxTitlePage + 1 : 1,
  );
  const prevTotalPages = Math.min(
    MAX_PINNED_GRID_PAGES,
    prevBasePages + Math.max(0, store.pinnedExtraPages),
  );
  if (prevTotalPages <= 1) return;

  const { items: nextItems, pageTitles: nextTitles } = deletePageAndShift(
    pinnedItems,
    pageTitles,
    pageIdx,
    dims.cols,
    dims.rows,
  );
  const nextResolved = resolveTileGridLayout(nextItems, dims.cols, dims.rows);
  const nextTitleKeys = Object.keys(nextTitles);
  const nextMaxTitlePage = nextTitleKeys.reduce((m, k) => Math.max(m, Number(k) || 0), 0);
  const nextBasePages = Math.max(
    1,
    nextResolved.pageCount,
    nextTitleKeys.length > 0 ? nextMaxTitlePage + 1 : 1,
  );
  const targetTotalPages = Math.max(1, prevTotalPages - 1);
  store.pinnedExtraPages = Math.max(0, targetTotalPages - nextBasePages);
  store.pinnedActivePage = Math.max(
    0,
    Math.min(store.pinnedActivePage, targetTotalPages - 1),
  );
  savePinnedGridStateOp(store, nextItems, nextTitles);
}

export function openShortcutModalOp(
  store: StudioStoreContext,
  listKey: "dock_items" | "pinned_items",
  editIndex: number | null = null,
  targetCell: { page: number; col: number; row: number } | null = null,
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
  const dims = resolveDeviceGridDims(caps);
  const resolvedPinned = !isDock
    ? resolveTileGridLayout(current, dims.cols, dims.rows)
    : null;
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
    const existingBadgeStyle = normalizeShortcutBadgeStyle(existing.badge_style);
    const existingAccent = normalizeShortcutAccent(existing.accent);
    const resTile = resolvedPinned?.tiles.find((t) => t.index === editIndex);
    const tilePage = !isDock ? (resTile?.page ?? Math.max(0, store.pinnedActivePage)) : 0;
    const tileCol = !isDock && resTile ? resTile.col : null;
    const tileRow = !isDock && resTile ? resTile.row : null;
    const tileColSpan = !isDock ? (resTile?.colSpan ?? 1) : 1;
    const tileRowSpan = !isDock ? (resTile?.rowSpan ?? 1) : 1;

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
        iconStyleFilter: "all",
        badgeStyle: existingBadgeStyle,
        accent: existingAccent,
        confirm: Boolean(existing.confirm),
        tilePage,
        tileCol,
        tileRow,
        tileColSpan,
        tileRowSpan,
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
        iconStyleFilter: "all",
        badgeStyle: existingBadgeStyle,
        accent: existingAccent,
        confirm: isDock,
        tilePage,
        tileCol,
        tileRow,
        tileColSpan,
        tileRowSpan,
      };
    }
  } else {
    const initPage = !isDock
      ? targetCell
        ? Math.max(0, Math.min(MAX_PINNED_GRID_PAGES - 1, Math.trunc(targetCell.page)))
        : Math.max(0, store.pinnedActivePage)
      : 0;
    const initCol = !isDock && targetCell ? Math.max(0, Math.min(dims.cols - 1, targetCell.col)) : null;
    const initRow = !isDock && targetCell ? Math.max(0, Math.min(dims.rows - 1, targetCell.row)) : null;

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
      iconStyleFilter: "all",
      badgeStyle: "",
      accent: "",
      confirm: isDock,
      tilePage: initPage,
      tileCol: initCol,
      tileRow: initRow,
      tileColSpan: 1,
      tileRowSpan: 1,
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
  const cleanBadgeStyle = normalizeShortcutBadgeStyle(modal.badgeStyle);
  const cleanAccent = normalizeShortcutAccent(modal.accent);

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
      badge_style: cleanBadgeStyle,
      accent: cleanAccent,
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
      badge_style: cleanBadgeStyle,
      accent: cleanAccent,
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

  if (!isDock) {
    const dims = resolveDeviceGridDims(store.state?.capabilities);
    const resolved = resolveTileGridLayout(current, dims.cols, dims.rows);
    const prevBasePages = resolved.pageCount;
    const wantCs = Math.max(1, Math.min(dims.cols, Math.trunc(modal.tileColSpan || 1)));
    const wantRs = Math.max(1, Math.min(dims.rows, Math.trunc(modal.tileRowSpan || 1)));
    const wantPage = Math.max(
      0,
      Math.min(MAX_PINNED_GRID_PAGES - 1, Math.trunc(modal.tilePage || 0)),
    );
    const excludeIdx = modal.editIndex !== null ? modal.editIndex : -1;

    let placed: { page: number; col: number; row: number } | null = null;
    if (modal.tileCol !== null && modal.tileRow !== null) {
      if (
        canPlaceTile(
          resolved,
          excludeIdx,
          wantPage,
          modal.tileCol,
          modal.tileRow,
          wantCs,
          wantRs,
          dims.cols,
          dims.rows,
        )
      ) {
        placed = { page: wantPage, col: modal.tileCol, row: modal.tileRow };
      } else {
        const shiftedCol = Math.min(modal.tileCol, dims.cols - wantCs);
        const shiftedRow = Math.min(modal.tileRow, dims.rows - wantRs);
        if (
          canPlaceTile(
            resolved,
            excludeIdx,
            wantPage,
            shiftedCol,
            shiftedRow,
            wantCs,
            wantRs,
            dims.cols,
            dims.rows,
          )
        ) {
          placed = { page: wantPage, col: shiftedCol, row: shiftedRow };
        }
      }
    }
    if (!placed) {
      placed = findFirstOpenSlot(
        resolved,
        wantPage,
        wantCs,
        wantRs,
        dims.cols,
        dims.rows,
        excludeIdx,
      );
    }

    built = withExplicitLayout(built, placed.page, placed.col, placed.row, wantCs, wantRs);

    if (modal.editIndex !== null && modal.editIndex >= 0 && modal.editIndex < current.length) {
      current[modal.editIndex] = built;
    } else {
      current.push(built);
    }

    store.pinnedActivePage = placed.page;
    const nextResolved = resolveTileGridLayout(current, dims.cols, dims.rows);
    if (nextResolved.pageCount > prevBasePages) {
      store.pinnedExtraPages = Math.max(
        0,
        store.pinnedExtraPages - (nextResolved.pageCount - prevBasePages),
      );
    }
  } else if (modal.editIndex !== null && modal.editIndex >= 0 && modal.editIndex < current.length) {
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
