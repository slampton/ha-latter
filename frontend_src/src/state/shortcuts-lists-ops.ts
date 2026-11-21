/**
 * Unified trait-driven catalog gate, shared `createTokenListOps` CSV pill factory (`A-14`),
 * shortcut normalization & modal helpers, and System string-list / remote / volume list editors.
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
import type {
  DeviceCapabilities,
  RemoteGroup,
  ShortcutItem,
  StudioStatePayload,
  SystemConfig,
  VolumeOverride,
} from "../types.js";
import type { StudioStore } from "./store.js";

/**
 * Single canonical trait-driven capability gate (`A-14`).
 * Never hides or rejects items when `caps` or an individual trait is `undefined` (unknown).
 */
export function isCatalogItemSupported(
  item: { capability?: string },
  caps?: DeviceCapabilities,
): boolean {
  const cap = item.capability;
  if (!cap || !caps) return true;
  switch (cap) {
    case "round":
      return caps.is_round !== false;
    case "imu":
      return caps.has_imu !== false;
    case "display_imu":
      return caps.has_display !== false && caps.has_imu !== false;
    case "display":
      return caps.has_display !== false;
    case "battery":
      return caps.has_battery !== false;
    case "display_battery":
      return caps.has_display !== false && caps.has_battery !== false;
    case "beacon_battery":
      return caps.has_ble_beacon !== false && caps.has_battery !== false;
    case "mic":
      return caps.has_voice !== false;
    case "speaker":
      return caps.has_audio !== false;
    case "hw_jpeg":
      return caps.hw_jpeg === true;
    default:
      return true;
  }
}

export type TokenListKey =
  | "area_categories"
  | "home_categories"
  | "tools_items"
  | "games_items"
  | "activity_sources";

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

export interface TokenListOps {
  getEnabled(): string[];
  toggle(token: string, forceEnabled?: boolean): void;
  move(token: string, delta: -1 | 1): void;
  reorder(fromEnabledIndex: number, toEnabledIndex: number): void;
}

export function createTokenListOps(store: StudioStore, spec: TokenListSpec): TokenListOps {
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
    while (
      swapIdx >= 0 &&
      swapIdx < current.length &&
      !isTokenSupportedOnActive(current[swapIdx])
    ) {
      swapIdx += delta;
    }
    if (swapIdx < 0 || swapIdx >= current.length) return;
    const tmp = current[idx];
    current[idx] = current[swapIdx];
    current[swapIdx] = tmp;
    store.entity.stageDeviceSetting(spec.key, current.join(","));
  };

  const reorder = (fromEnabledIndex: number, toEnabledIndex: number): void => {
    const current = getEnabled();
    const supportedIndices: number[] = [];
    for (let i = 0; i < current.length; i += 1) {
      if (isTokenSupportedOnActive(current[i])) {
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
    const visibleTokens = supportedIndices.map((idx) => current[idx]);
    const [moved] = visibleTokens.splice(fromEnabledIndex, 1);
    visibleTokens.splice(toEnabledIndex, 0, moved);
    for (let j = 0; j < supportedIndices.length; j += 1) {
      current[supportedIndices[j]] = visibleTokens[j];
    }
    store.entity.stageDeviceSetting(spec.key, current.join(","));
  };

  return { getEnabled, toggle, move, reorder };
}

// ---------------------------------------------------------------------------
// Shortcuts (`dock_items` & `pinned_items`)
// ---------------------------------------------------------------------------

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
      if (!validActions || validActions.length === 0) continue;
      const rawAct = String(rec.action || "").trim().toLowerCase();
      const action = validActions.some((a) => a.action === rawAct)
        ? rawAct
        : validActions[0].action;
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
  store: StudioStore,
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

  if (editIndex !== null && editIndex >= 0 && editIndex < current.length) {
    const existing = current[editIndex];
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

export function saveShortcutModalOp(store: StudioStore): void {
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

// ---------------------------------------------------------------------------
// System String-List Slots, Volume Overrides, & Remote Control Groups
// ---------------------------------------------------------------------------

export type StringListKey =
  | "calendar_entities"
  | "camera_entities"
  | "remotes_list"
  | "thermostat_entities"
  | "lock_entities"
  | "garage_entities"
  | "vacuum_entities"
  | "broadcast_speakers"
  | "broadcast_phrases";

export const STRING_LIST_KEYS: readonly StringListKey[] = [
  "calendar_entities",
  "camera_entities",
  "remotes_list",
  "thermostat_entities",
  "lock_entities",
  "garage_entities",
  "vacuum_entities",
  "broadcast_speakers",
  "broadcast_phrases",
];

export const STRING_LIST_MAX_ITEMS: Readonly<Record<StringListKey, number>> = {
  camera_entities: 10,
  remotes_list: 10,
  calendar_entities: 50,
  thermostat_entities: 8,
  lock_entities: 8,
  garage_entities: 6,
  vacuum_entities: 6,
  broadcast_speakers: 32,
  broadcast_phrases: 12,
};

export function isStringListKey(key: string): key is StringListKey {
  return (
    key === "calendar_entities" ||
    key === "camera_entities" ||
    key === "remotes_list" ||
    key === "thermostat_entities" ||
    key === "lock_entities" ||
    key === "garage_entities" ||
    key === "vacuum_entities" ||
    key === "broadcast_speakers" ||
    key === "broadcast_phrases"
  );
}

export function cleanPersistedStringList(items: readonly unknown[], maxItems: number): string[] {
  const out: string[] = [];
  for (const raw of items) {
    const ent = String(raw || "").trim();
    if (ent && !out.includes(ent)) {
      out.push(ent);
      if (out.length >= maxItems) break;
    }
  }
  return out;
}

export function mergePersistedWithBlankSlots(
  persisted: readonly string[],
  blankCount: number,
  maxItems: number,
  prevUiList?: readonly string[],
): { uiList: string[]; clampedBlankCount: number } {
  const cleaned = cleanPersistedStringList(persisted, maxItems);
  const clampedBlankCount = Math.max(0, Math.min(blankCount, maxItems - cleaned.length));
  if (clampedBlankCount === 0) {
    return { uiList: cleaned, clampedBlankCount: 0 };
  }
  if (prevUiList && prevUiList.some((v) => !String(v || "").trim())) {
    const uiList: string[] = [];
    let cleanIdx = 0;
    let blanksPlaced = 0;
    for (const slot of prevUiList) {
      if (uiList.length >= maxItems) break;
      if (!String(slot || "").trim()) {
        if (blanksPlaced < clampedBlankCount) {
          uiList.push("");
          blanksPlaced += 1;
        }
      } else if (cleanIdx < cleaned.length) {
        uiList.push(cleaned[cleanIdx]);
        cleanIdx += 1;
      }
    }
    while (cleanIdx < cleaned.length && uiList.length < maxItems) {
      uiList.push(cleaned[cleanIdx]);
      cleanIdx += 1;
    }
    while (blanksPlaced < clampedBlankCount && uiList.length < maxItems) {
      uiList.push("");
      blanksPlaced += 1;
    }
    return { uiList, clampedBlankCount: blanksPlaced };
  }
  return {
    uiList: [...cleaned, ...Array<string>(clampedBlankCount).fill("")],
    clampedBlankCount,
  };
}

export function overlayPendingBlankListSlots(
  store: StudioStore,
  payload: StudioStatePayload,
  prevSysConfig?: SystemConfig,
): void {
  if (!payload.system_config) return;
  let mutated = false;
  const nextSys: SystemConfig = { ...payload.system_config };
  for (const key of STRING_LIST_KEYS) {
    const wantBlanks = store.pendingBlankListSlots[key] || 0;
    if (wantBlanks <= 0) continue;
    const maxItems = STRING_LIST_MAX_ITEMS[key];
    const base = Array.isArray(nextSys[key]) ? nextSys[key] : [];
    const { uiList, clampedBlankCount } = mergePersistedWithBlankSlots(
      base,
      wantBlanks,
      maxItems,
      prevSysConfig?.[key],
    );
    store.pendingBlankListSlots[key] = clampedBlankCount;
    nextSys[key] = uiList;
    mutated = true;
  }
  if (mutated) {
    payload.system_config = nextSys;
  }
}

export function updateStringListRowOp(
  store: StudioStore,
  key: StringListKey,
  index: number,
  value: string,
): void {
  const maxItems = STRING_LIST_MAX_ITEMS[key];
  const prevUiList = [...(store.state?.system_config?.[key] || [])];
  if (index < 0 || index >= prevUiList.length) return;

  const prevPersisted = cleanPersistedStringList(prevUiList, maxItems);
  const nextRaw = [...prevUiList];
  nextRaw[index] = String(value || "").trim();

  const seen = new Set<string>();
  const nextUiList: string[] = [];
  for (const item of nextRaw) {
    const ent = String(item || "").trim();
    if (!ent) {
      nextUiList.push("");
    } else if (!seen.has(ent)) {
      seen.add(ent);
      nextUiList.push(ent);
    }
    if (nextUiList.length >= maxItems) break;
  }

  const nextPersisted = nextUiList.filter(Boolean);
  store.pendingBlankListSlots[key] = nextUiList.length - nextPersisted.length;

  const persistedChanged =
    prevPersisted.length !== nextPersisted.length ||
    prevPersisted.some((v, i) => v !== nextPersisted[i]);

  if (persistedChanged) {
    store.entity.stageSystemSetting(key, nextPersisted);
    if (store.state?.system_config && store.pendingBlankListSlots[key] > 0) {
      store.state = {
        ...store.state,
        system_config: {
          ...store.state.system_config,
          [key]: nextUiList,
        },
      };
      store.host.requestUpdate();
    }
  } else if (store.state?.system_config) {
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: nextUiList,
      },
    };
    store.host.requestUpdate();
  }
}

export function addStringListRowOp(
  store: StudioStore,
  key: StringListKey,
  defaultEntity = "",
  maxLen = STRING_LIST_MAX_ITEMS[key],
): void {
  const cap = Math.min(maxLen, STRING_LIST_MAX_ITEMS[key]);
  const list = [...(store.state?.system_config?.[key] || [])];
  if (list.length >= cap) {
    store.showToast(`Maximum of ${cap} entries reached`, true);
    return;
  }
  const cleanDefault = String(defaultEntity || "").trim();
  if (!cleanDefault) {
    list.push("");
    store.pendingBlankListSlots[key] = list.filter((s) => !String(s || "").trim()).length;
    if (store.state?.system_config) {
      store.state = {
        ...store.state,
        system_config: {
          ...store.state.system_config,
          [key]: list,
        },
      };
    }
    store.host.requestUpdate();
    return;
  }
  const nextPersisted = cleanPersistedStringList([...list, cleanDefault], cap);
  const wantBlanks = Math.max(
    0,
    Math.min(store.pendingBlankListSlots[key] || 0, cap - nextPersisted.length),
  );
  store.pendingBlankListSlots[key] = wantBlanks;
  store.entity.stageSystemSetting(key, nextPersisted);
  if (store.state?.system_config && wantBlanks > 0) {
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: [...nextPersisted, ...Array<string>(wantBlanks).fill("")],
      },
    };
    store.host.requestUpdate();
  }
}

export function removeStringListRowOp(
  store: StudioStore,
  key: StringListKey,
  index: number,
): void {
  const maxItems = STRING_LIST_MAX_ITEMS[key];
  const list = [...(store.state?.system_config?.[key] || [])];
  if (index < 0 || index >= list.length) return;
  const [removed] = list.splice(index, 1);
  const wasBlank = !String(removed || "").trim();
  store.pendingBlankListSlots[key] = list.filter((s) => !String(s || "").trim()).length;

  if (wasBlank) {
    if (store.state?.system_config) {
      store.state = {
        ...store.state,
        system_config: {
          ...store.state.system_config,
          [key]: list,
        },
      };
    }
    store.host.requestUpdate();
    return;
  }

  const nextPersisted = cleanPersistedStringList(list, maxItems);
  store.entity.stageSystemSetting(key, nextPersisted);
  if (store.state?.system_config && store.pendingBlankListSlots[key] > 0) {
    const { uiList, clampedBlankCount } = mergePersistedWithBlankSlots(
      nextPersisted,
      store.pendingBlankListSlots[key],
      maxItems,
      list,
    );
    store.pendingBlankListSlots[key] = clampedBlankCount;
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: uiList,
      },
    };
    store.host.requestUpdate();
  }
}

export function reorderStringListRowsOp(
  store: StudioStore,
  key: StringListKey,
  fromIndex: number,
  toIndex: number,
): void {
  const maxItems = STRING_LIST_MAX_ITEMS[key];
  const list = [...(store.state?.system_config?.[key] || [])];
  if (
    fromIndex < 0 ||
    fromIndex >= list.length ||
    toIndex < 0 ||
    toIndex >= list.length ||
    fromIndex === toIndex
  ) {
    return;
  }
  const prevPersisted = cleanPersistedStringList(list, maxItems);
  const [moved] = list.splice(fromIndex, 1);
  list.splice(toIndex, 0, moved);
  const nextPersisted = cleanPersistedStringList(list, maxItems);
  store.pendingBlankListSlots[key] = list.filter((s) => !String(s || "").trim()).length;

  const persistedChanged =
    prevPersisted.length !== nextPersisted.length ||
    prevPersisted.some((v, i) => v !== nextPersisted[i]);

  if (persistedChanged) {
    store.entity.stageSystemSetting(key, nextPersisted);
    if (store.state?.system_config && store.pendingBlankListSlots[key] > 0) {
      store.state = {
        ...store.state,
        system_config: {
          ...store.state.system_config,
          [key]: list,
        },
      };
      store.host.requestUpdate();
    }
  } else if (store.state?.system_config) {
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: list,
      },
    };
    store.host.requestUpdate();
  }
}

export function addVolumeOverrideRowOp(store: StudioStore): void {
  const list: VolumeOverride[] = [...(store.state?.system_config?.volume_overrides || [])];
  if (list.length >= 10) {
    store.showToast("Maximum of 10 volume overrides reached", true);
    return;
  }
  const speakers = store.state?.catalog?.ma_speakers || [];
  const targets = store.state?.catalog?.volume_targets || store.state?.catalog?.remotes || [];
  list.push({
    speaker: speakers[0]?.id || "",
    target: targets[0]?.id || speakers[0]?.id || "",
  });
  store.entity.stageSystemSetting("volume_overrides", list);
}

export function updateVolumeOverrideRowOp(
  store: StudioStore,
  index: number,
  field: "speaker" | "target",
  value: string,
): void {
  const list: VolumeOverride[] = (store.state?.system_config?.volume_overrides || []).map((v) => ({
    ...v,
  }));
  if (!list[index]) return;
  list[index][field] = value;
  store.entity.stageSystemSetting("volume_overrides", list);
}

export function removeVolumeOverrideRowOp(store: StudioStore, index: number): void {
  const list: VolumeOverride[] = [...(store.state?.system_config?.volume_overrides || [])];
  list.splice(index, 1);
  store.entity.stageSystemSetting("volume_overrides", list);
}

export function addRemoteGroupRowOp(store: StudioStore): void {
  const groups: RemoteGroup[] = (store.state?.system_config?.remote_groups || []).map((g) => ({
    ...g,
    remotes: [...(g.remotes || [])],
  }));
  const id = `group_${Date.now().toString(36)}`;
  groups.push({ id, name: "New remote group", area_id: "", remotes: [] });
  store.entity.stageSystemSetting("remote_groups", groups);
}

export function updateRemoteGroupFieldOp(
  store: StudioStore,
  groupId: string,
  field: "name" | "area_id",
  value: string,
): void {
  const groups: RemoteGroup[] = (store.state?.system_config?.remote_groups || []).map((g) =>
    g.id === groupId ? { ...g, [field]: value } : { ...g, remotes: [...(g.remotes || [])] },
  );
  store.entity.stageSystemSetting("remote_groups", groups);
}

export function toggleRemoteInGroupOp(
  store: StudioStore,
  groupId: string,
  remoteEntity: string,
): void {
  const groups: RemoteGroup[] = (store.state?.system_config?.remote_groups || []).map((g) => {
    if (g.id !== groupId) return { ...g, remotes: [...(g.remotes || [])] };
    const remotes = [...(g.remotes || [])];
    const idx = remotes.indexOf(remoteEntity);
    if (idx >= 0) remotes.splice(idx, 1);
    else remotes.push(remoteEntity);
    return { ...g, remotes };
  });
  store.entity.stageSystemSetting("remote_groups", groups);
}

export function removeRemoteGroupRowOp(store: StudioStore, groupId: string): void {
  const groups = (store.state?.system_config?.remote_groups || []).filter((g) => g.id !== groupId);
  store.entity.stageSystemSetting("remote_groups", groups);
}
