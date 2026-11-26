/**
 * URL Routing, Active-Device Lifecycle Transitions, & Section Handoff Scrolling.
 *
 * Imports strictly leaf constants/types (`constants.ts`, `types.ts`), `utils/format.ts`, and `store-types.ts`.
 */

import { DEVICE_VIEW_SLUGS, SYSTEM_VIEW_SLUGS } from "../constants.js";
import type {
  DeviceCapabilities,
  DeviceViewId,
  HassRoute,
  StudioScope,
  StudioViewId,
  SystemViewId,
} from "../types.js";
import { navigateHaPath } from "../utils/format.js";
import { emptyPhotoPickerModalState, type StudioStoreContext } from "./store-types.js";

export interface RoutingRuntime {
  routeApplying: boolean;
  scrollGen: number;
  handoffArming: boolean;
}

function slugToView<T extends string>(map: Readonly<Record<T, string>>, slug: string): T | null {
  const cleaned = String(slug || "").trim().toLowerCase();
  for (const [viewId, s] of Object.entries(map) as Array<[T, string]>) {
    if (s === cleaned) return viewId;
  }
  return null;
}

/**
 * Shared capability predicate used by both sidebar navigation and payload capability redirects.
 * Never redirects or hides a tab when capability flags are `undefined` (not yet loaded).
 */
export function deviceHasView(
  viewId: DeviceViewId,
  caps?: DeviceCapabilities,
  kind?: string,
): boolean {
  if (
    viewId === "select_device_prompt" ||
    viewId === "discovered_devices" ||
    viewId === "dashboard" ||
    viewId === "presence" ||
    viewId === "tools"
  ) {
    return true;
  }
  if (kind === "ble_tag") return false;
  if (!caps) return true;
  if (viewId === "display" || viewId === "interface") {
    return caps.has_display !== false;
  }
  if (viewId === "audio_voice") {
    return !(caps.has_audio === false && caps.has_voice === false);
  }
  if (viewId === "power") {
    return caps.has_power !== false;
  }
  return true;
}

export function storeDeviceHasView(store: StudioStoreContext, viewId: DeviceViewId): boolean {
  if (store.state?.subentry_id !== store.activeSubentryId) {
    const entry = store.state?.system_devices?.find(
      (d) => d.subentry_id === store.activeSubentryId,
    );
    if (entry?.kind === "ble_tag") {
      return deviceHasView(viewId, undefined, "ble_tag");
    }
    return deviceHasView(viewId, undefined, undefined);
  }
  return deviceHasView(viewId, store.state?.capabilities, store.state?.config?.kind);
}

function scrollIntoViewAsync(
  element: HTMLElement,
  options: ScrollIntoViewOptions,
): Promise<void> {
  const result = element.scrollIntoView(options) as unknown;
  if (result instanceof Promise) {
    return result as Promise<void>;
  }
  const scroller = globalThis.window;
  if (!scroller || typeof scroller.addEventListener !== "function") {
    return Promise.resolve();
  }
  return new Promise<void>((resolve) => {
    let timeoutId: ReturnType<typeof setTimeout>;
    const finish = (): void => {
      clearTimeout(timeoutId);
      scroller.removeEventListener("scrollend", finish);
      scroller.removeEventListener("scroll", onScroll);
      resolve();
    };
    const onScroll = (): void => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(finish, 100);
    };
    scroller.addEventListener("scrollend", finish, { once: true });
    scroller.addEventListener("scroll", onScroll, { passive: true });
    timeoutId = setTimeout(finish, 100);
  });
}

export function hostUpdatedDomOp(store: StudioStoreContext, rt: RoutingRuntime): void {
  if (store.pendingDomRevert) {
    const rev = store.pendingDomRevert;
    store.pendingDomRevert = null;
    const root = (store.host as unknown as { renderRoot?: ShadowRoot }).renderRoot;
    if (root) {
      for (const [id, val] of Object.entries(rev.controlIds)) {
        const el = root.getElementById(id) as HTMLInputElement | HTMLSelectElement | null;
        if (!el) continue;
        if (typeof val === "boolean" && "checked" in el) {
          (el as HTMLInputElement).checked = val;
        } else {
          el.value = String(val);
        }
      }
    }
  }
  if (store.pendingScrollCardId) {
    const cardId = store.pendingScrollCardId;
    store.pendingScrollCardId = "";
    const root =
      (store.host as unknown as { renderRoot?: ShadowRoot }).renderRoot ||
      store.host.shadowRoot;
    const target = root?.getElementById(cardId) as HTMLElement | null;
    if (target && typeof target.scrollIntoView === "function") {
      const myGen = ++rt.scrollGen;
      const reducedMotion = Boolean(
        typeof globalThis.matchMedia === "function" &&
          globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches,
      );
      void scrollIntoViewAsync(target, {
        behavior: reducedMotion ? "auto" : "smooth",
        block: "start",
      }).then(() => {
        if (myGen !== rt.scrollGen || !store.handoffTargetIds.has(cardId)) return;
        if (typeof target.focus === "function") {
          if (typeof target.hasAttribute === "function" && !target.hasAttribute("tabindex")) {
            target.setAttribute?.("tabindex", "-1");
          }
          try {
            target.focus({ preventScroll: true });
          } catch {
            target.focus();
          }
        }
      });
    }
  }
  rt.handoffArming = false;
}

export function applySectionHandoffOp(
  store: StudioStoreContext,
  rt: RoutingRuntime,
  scrollId = "",
  highlightIds?: readonly string[],
): void {
  const cleanScroll = String(scrollId || "").trim();
  store.pendingScrollCardId = cleanScroll;
  const ids =
    highlightIds && highlightIds.length > 0
      ? highlightIds
      : cleanScroll
        ? [cleanScroll]
        : [];
  for (const rawId of ids) {
    const id = String(rawId || "").trim();
    if (id) store.handoffTargetIds.add(id);
  }
  if (store.handoffTargetIds.size > 0) {
    rt.handoffArming = true;
    store.host.requestUpdate();
  }
}

export function onMainFocusInOp(
  store: StudioStoreContext,
  rt: RoutingRuntime,
  ev: FocusEvent,
): void {
  if (rt.handoffArming || store.handoffTargetIds.size === 0) return;
  const path = typeof ev.composedPath === "function" ? ev.composedPath() : [];
  const target = (path[0] ?? ev.target) as Element | null;
  if (!target || typeof target.tagName !== "string") return;
  const tag = target.tagName.toUpperCase();
  if (
    tag !== "BUTTON" &&
    tag !== "INPUT" &&
    tag !== "SELECT" &&
    tag !== "TEXTAREA" &&
    tag !== "SUMMARY" &&
    tag !== "A"
  ) {
    return;
  }
  let cur: Element | null = target;
  while (cur) {
    if (cur.id && store.handoffTargetIds.has(cur.id)) {
      return;
    }
    cur = cur.parentElement;
  }
  store.handoffTargetIds.clear();
  store.host.requestUpdate();
}

export function onActiveDeviceChangedOp(
  store: StudioStoreContext,
  prevId: string,
  nextId: string,
  options?: { discardPrevPending?: boolean },
): void {
  const cleanPrev = String(prevId || "").trim();
  const cleanNext = String(nextId || "").trim();

  if (cleanPrev && cleanPrev !== cleanNext) {
    if (options?.discardPrevPending) {
      store.entity.discardDeviceBucket(cleanPrev);
    } else {
      void store.entity.flushDeviceBucket(cleanPrev);
    }
  }

  if (cleanPrev !== cleanNext) {
    store.devicePinDraft = "";
    store.showDevicePin = false;
    store.showSystemPin = false;
    store.worldClockNewLabel = "";
    store.worldClockNewZone = "";
    store.worldClockRowKeys = [];
    store.overviewAlarmsOpen = false;
    store.appConfigModal = { open: false, app: null };
    store.pinnedActivePage = 0;
    store.pinnedExtraPages = 0;
    store.cameraConfigModal = { ...store.cameraConfigModal, open: false };
    store.photoPickerModal = emptyPhotoPickerModalState();
    store.shortcutModal = { ...store.shortcutModal, open: false };
    store.saveGroupModal = { ...store.saveGroupModal, open: false, busy: false };
    store.resetModal = { ...store.resetModal, open: false, busy: false };
    store.returnToPinnedModal = false;
    store.clearHandoffTargets();
  }

  store.activeSubentryId = cleanNext;
  store.deviceSelected = Boolean(cleanNext);
  store.deviceLoading = Boolean(cleanNext && store.state?.subentry_id !== cleanNext);
  store.syncLiveClockTimer();
}

export function applyRouteOp(
  store: StudioStoreContext,
  rt: RoutingRuntime,
  route: HassRoute | null | undefined,
): void {
  let rawPath = String(route?.path ?? "");
  if (!rawPath && !route && typeof globalThis.location?.pathname === "string") {
    const locPath = globalThis.location.pathname;
    if (locPath.startsWith("/latter/")) {
      rawPath = locPath.slice("/latter/".length);
    }
  }
  const parts = rawPath
    .split("/")
    .filter(Boolean)
    .map((seg) => {
      try {
        return decodeURIComponent(seg);
      } catch {
        return seg;
      }
    });

  const prevScope = store.currentScope;
  const prevViewId = store.currentViewId;
  const prevSubId = store.activeSubentryId;
  const seg0 = parts[0];
  const seg1 = parts[1];
  const seg2 = parts[2];

  rt.routeApplying = true;
  try {
    if (seg0 === "devices" && seg1?.toLowerCase() === "discovered") {
      if (prevScope === "system") {
        void store.entity.flushSystemSettings();
      }
      store.onActiveDeviceChanged(prevSubId, "");
      if (prevScope !== "device" || prevViewId !== "discovered_devices") {
        store.clearHandoffTargets();
      }
      store.currentScope = "device";
      store.currentViewId = "discovered_devices";
    } else if (seg0 === "devices" && seg1) {
      const nextSubId = seg1;
      if (
        store.state &&
        Array.isArray(store.state.system_devices) &&
        !store.state.system_devices.some((d) => d.subentry_id === nextSubId)
      ) {
        if (prevScope === "system") {
          void store.entity.flushSystemSettings();
        }
        store.redirectInvalidDeviceRoute(nextSubId);
        return;
      }
      if (prevScope === "system") {
        void store.entity.flushSystemSettings();
      }
      const requestedView = slugToView(DEVICE_VIEW_SLUGS, seg2 || "overview") || "dashboard";
      store.onActiveDeviceChanged(prevSubId, nextSubId);
      const validView = store.deviceHasView(requestedView) ? requestedView : "dashboard";
      if (prevScope !== "device" || prevViewId !== validView || prevSubId !== nextSubId) {
        store.clearHandoffTargets();
      }
      store.currentScope = "device";
      store.currentViewId = validView;
      if (validView !== requestedView) {
        navigateHaPath(
          `/latter/devices/${encodeURIComponent(nextSubId)}/${DEVICE_VIEW_SLUGS[validView]}`,
          true,
        );
      }
    } else if (seg0 === "system") {
      store.onActiveDeviceChanged(prevSubId, "");
      const viewId = slugToView(SYSTEM_VIEW_SLUGS, seg1 || "overview") || "system_overview";
      if (prevScope !== "system" || prevViewId !== viewId) {
        store.clearHandoffTargets();
      } else if (viewId !== "area_tracking") {
        store.bleCalibrateHandoffActive = false;
      }
      store.currentScope = "system";
      store.currentViewId = viewId;
      if (viewId === "area_tracking") {
        store.ensureDefaultSurveyDevice();
      }
    } else {
      if (prevScope === "system") {
        void store.entity.flushSystemSettings();
      }
      store.onActiveDeviceChanged(prevSubId, "");
      if (prevScope !== "device" || prevViewId !== "select_device_prompt") {
        store.clearHandoffTargets();
      }
      store.currentScope = "device";
      store.currentViewId = "select_device_prompt";
    }
    store.syncLiveClockTimer();
    store.host.requestUpdate();
  } finally {
    rt.routeApplying = false;
  }

  if (store.host.isConnected && store.ws.hass && !store.studioRevMismatch) {
    void store.ensureSubscription(false);
  }
}

export function redirectInvalidDeviceRouteOp(
  store: StudioStoreContext,
  invalidId?: string,
): void {
  const dropId = invalidId ?? store.activeSubentryId;
  store.onActiveDeviceChanged(dropId, "", { discardPrevPending: true });
  store.currentScope = "device";
  store.currentViewId = "select_device_prompt";
  navigateHaPath("/latter/devices", true);
  if (dropId) {
    store.showToast(store.t("sync.device_not_found"), false);
  }
  store.host.requestUpdate();
  if (store.host.isConnected && store.ws.hass && !store.studioRevMismatch) {
    void store.ensureSubscription(false);
  }
}

export function syncUrlOp(
  store: StudioStoreContext,
  rt: RoutingRuntime,
  replace = false,
): void {
  if (rt.routeApplying) return;
  let targetPath = "/latter/devices";
  if (store.currentScope === "system") {
    const slug = SYSTEM_VIEW_SLUGS[store.currentViewId as SystemViewId] || "overview";
    targetPath = `/latter/system/${slug}`;
  } else if (store.currentViewId === "discovered_devices") {
    targetPath = "/latter/devices/discovered";
  } else if (
    store.deviceSelected &&
    store.activeSubentryId &&
    store.currentViewId !== "select_device_prompt"
  ) {
    const slug =
      DEVICE_VIEW_SLUGS[
        store.currentViewId as Exclude<
          DeviceViewId,
          "select_device_prompt" | "discovered_devices"
        >
      ] || "overview";
    targetPath = `/latter/devices/${encodeURIComponent(store.activeSubentryId)}/${slug}`;
  }
  if (globalThis.location?.pathname !== targetPath) {
    navigateHaPath(targetPath, replace);
  }
}

export function openDevicesLandingOp(store: StudioStoreContext): void {
  if (store.currentScope === "system") {
    void store.entity.flushSystemSettings();
  }
  store.onActiveDeviceChanged(store.activeSubentryId, "");
  store.clearHandoffTargets();
  store.currentScope = "device";
  store.currentViewId = "select_device_prompt";
  store.syncLiveClockTimer();
  store.syncUrl();
  store.host.requestUpdate();
  void store.ensureSubscription(false);
}

export function openDiscoveredDevicesOp(store: StudioStoreContext, cardId = ""): void {
  if (store.currentScope === "system") {
    void store.entity.flushSystemSettings();
  }
  store.onActiveDeviceChanged(store.activeSubentryId, "");
  store.clearHandoffTargets();
  store.currentScope = "device";
  store.currentViewId = "discovered_devices";
  store.syncLiveClockTimer();
  store.syncUrl();
  store.host.requestUpdate();
  store.applySectionHandoff(cardId);
  void store.ensureSubscription(false);
}

export function setScopeOp(
  store: StudioStoreContext,
  scope: StudioScope,
  explicitViewId?: StudioViewId,
): void {
  if (scope === "device" && store.currentScope !== "device") {
    void store.entity.flushSystemSettings();
  } else if (scope === "system") {
    store.onActiveDeviceChanged(store.activeSubentryId, "");
  }
  store.clearHandoffTargets();
  store.currentScope = scope;
  if (explicitViewId) {
    store.currentViewId = explicitViewId;
  } else if (scope === "system") {
    store.currentViewId = "system_overview";
  } else {
    store.currentViewId =
      store.deviceSelected && store.activeSubentryId ? "dashboard" : "select_device_prompt";
  }
  if (store.currentViewId === "area_tracking") {
    store.ensureDefaultSurveyDevice();
  }
  store.syncLiveClockTimer();
  store.syncUrl();
  store.host.requestUpdate();
  void store.ensureSubscription(false);
}

export function switchViewOp(store: StudioStoreContext, viewId: StudioViewId): void {
  if (viewId === "select_device_prompt") {
    store.openDevicesLanding();
    return;
  }
  if (viewId === "discovered_devices") {
    store.openDiscoveredDevices();
    return;
  }
  store.clearHandoffTargets();
  const isSys = Object.prototype.hasOwnProperty.call(SYSTEM_VIEW_SLUGS, viewId);
  if (isSys) {
    store.onActiveDeviceChanged(store.activeSubentryId, "");
  } else if (store.currentScope === "system") {
    void store.entity.flushSystemSettings();
  }
  store.currentScope = isSys ? "system" : "device";
  store.currentViewId = viewId;
  if (viewId === "area_tracking") {
    store.ensureDefaultSurveyDevice();
  }
  store.syncLiveClockTimer();
  store.syncUrl();
  store.host.requestUpdate();
  void store.ensureSubscription(false);
}

export async function switchSystemDeviceOp(
  store: StudioStoreContext,
  nextSubentryId: string,
  targetView: DeviceViewId = "dashboard",
): Promise<void> {
  const cleanNext = String(nextSubentryId || "").trim();
  if (!cleanNext) return;
  if (store.currentScope === "system") {
    void store.entity.flushSystemSettings();
  }
  store.onActiveDeviceChanged(store.activeSubentryId, cleanNext);
  store.currentScope = "device";
  const desired =
    targetView === "select_device_prompt" || targetView === "discovered_devices"
      ? "dashboard"
      : targetView;
  store.currentViewId = store.deviceHasView(desired) ? desired : "dashboard";
  store.syncLiveClockTimer();
  store.syncUrl();
  store.host.requestUpdate();
  await store.ensureSubscription(false);
}

export function openDeviceInHaOp(store: StudioStoreContext, preferLatterEntry = false): void {
  const links = store.state?.links;
  const devId = preferLatterEntry
    ? links?.latter_device_id || links?.esphome_device_id || ""
    : links?.esphome_device_id || links?.latter_device_id || "";
  if (devId) {
    navigateHaPath(`/config/devices/device/${encodeURIComponent(devId)}`, false);
  } else {
    navigateHaPath("/config/integrations/integration/latter", false);
  }
}
