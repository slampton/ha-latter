/**
 * Encapsulated Reactive Store for Latter Studio (`StudioStore`, `D-023`, `D-062`, `D-064`, `D-065`).
 *
 * Architecture:
 * - Zero `window.*` globals and zero 1-line pass-through wrappers (`A-15` / `Q10`).
 * - Namespaced domain controllers: `store.entity`, `store.groups`, `store.tools`.
 * - Event-first `latter/system/subscribe` bootstrap (`STUDIO_REV = 34`), section-hash preservation,
 *   `"ready"` reconnect resync, exponential backoff (`2s -> 5s -> 15s -> 60s`), and `subentry_id`
 *   payload isolation (`deviceLoading` guard).
 * - Isolated local 1 Hz `liveClockNowMs` interval active strictly on `Device -> Overview` when a
 *   timer or stopwatch is running (`F-01`, `B-17`).
 */

import {
  formatWsError,
  isStudioRevMismatchError,
  StudioWsClient,
} from "../api/ws-client.js";
import {
  DEVICE_VIEW_SLUGS,
  SYSTEM_VIEW_SLUGS,
  VIEW_TITLE_KEYS,
  VIRTUAL_COLLECTION_ALL,
} from "../constants.js";
import {
  type StudioTranslationKey,
  t,
  tPrefLabel,
  tPrefOption,
} from "../i18n/index.js";
import type { ReactiveController, ReactiveControllerHost } from "../lib/lit.js";
import type {
  AreaPresenceRow,
  BleAreaSignatureSummary,
  BleSurveyDeltaEvent,
  BleSurveyRow,
  ConfigurableAppId,
  DeviceCapabilities,
  DeviceViewId,
  DiscoveredBleCandidate,
  HassConnection,
  HassRoute,
  HomeAssistant,
  StudioScope,
  StudioStatePayload,
  StudioViewId,
  SystemConfig,
  SystemViewId,
} from "../types.js";
import { navigateHaPath } from "../utils/format.js";
import {
  type DevicePendingBucket,
  EntityController,
  isCatalogItemSupported,
  isProtectedNativeDockItem,
  overlayDevicePrefsOnSections,
  overlayPendingBlankListSlots,
  overlayPendingEntityStates,
  type PendingEntityEntry,
  type StringListKey,
  type TokenListKey,
  type TokenListOps,
} from "./entity-controller.js";
import { type BatchPillState, GroupsController } from "./groups-controller.js";
import {
  emptyMediaImportModalState,
  emptyPhotoEditModalState,
  emptyPhotoPickerModalState,
  emptyPhotoUploadModalState,
  type MediaImportModalState,
  type PhotoEditModalState,
  type PhotoPickerModalState,
  type PhotoUploadModalState,
  type StagedUploadPhoto,
} from "./photo-ops.js";
import {
  type ConfirmModalState,
  emptyConfirmModalState,
  type OpenConfirmOptions,
  ToolsController,
} from "./tools-controller.js";

export {
  type BatchPillState,
  type ConfirmModalState,
  type DevicePendingBucket,
  EntityController,
  GroupsController,
  isCatalogItemSupported,
  isProtectedNativeDockItem,
  type MediaImportModalState,
  type OpenConfirmOptions,
  overlayDevicePrefsOnSections,
  overlayPendingEntityStates,
  type PendingEntityEntry,
  type PhotoEditModalState,
  type PhotoPickerModalState,
  type PhotoUploadModalState,
  type StagedUploadPhoto,
  type StringListKey,
  type TokenListKey,
  type TokenListOps,
  ToolsController,
};

const RECONNECT_BACKOFF_MS: ReadonlyArray<number> = [2_000, 5_000, 15_000, 60_000];
const INFO_TOAST_DURATION_MS = 3_500;

interface PendingDomRevert {
  controlIds: Record<string, string | boolean>;
}

function slugToView<T extends string>(map: Readonly<Record<T, string>>, slug: string): T | null {
  const cleaned = String(slug || "").trim().toLowerCase();
  for (const [viewId, s] of Object.entries(map) as Array<[T, string]>) {
    if (s === cleaned) return viewId;
  }
  return null;
}

/**
 * Shared capability predicate used by BOTH sidebar navigation and payload capability redirect (`B-06`, `E-14`).
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

export class StudioStore implements ReactiveController {
  readonly host: ReactiveControllerHost & HTMLElement;
  readonly ws: StudioWsClient;

  // Namespaced domain controllers (`Q10`)
  readonly entity: EntityController;
  readonly groups: GroupsController;
  readonly tools: ToolsController;

  // Core navigation & lifecycle state (`D-001`: starts on Devices landing list)
  currentScope: StudioScope = "device";
  currentViewId: StudioViewId = "select_device_prompt";
  activeSubentryId = "";
  deviceSelected = false;
  deviceLoading = false;

  state: StudioStatePayload | null = null;
  loading = true;
  loadError = "";
  studioRevMismatch = false;

  // Live regions & toast feedback (`D-01`, `D-02`)
  toastMessage = "";
  toastIsError = false;
  politeAnnouncement = "";
  assertiveAnnouncement = "";
  private politeSeq = 0;
  private assertiveSeq = 0;
  private toastTimer: ReturnType<typeof setTimeout> | null = null;

  // Local 1 Hz clock tick strictly for active Device Overview timer/stopwatch (`F-01`, `B-17`)
  liveClockNowMs = Date.now();
  private liveClockTimer: ReturnType<typeof setInterval> | null = null;

  // Selected backup file state
  selectedBackupFile: File | null = null;

  // Devices table & Discovered UI state
  deviceSortField: "title" | "model" | "area" | "group" | "status" = "title";
  deviceSortAsc = true;
  deviceCategoryFilter = "all";
  discoveredBleSearch = "";
  discoveredBleKindFilter: "all" | "tracker" | "named" = "all";
  discoveredBleSort: "name" | "rssi" | "area" = "name";
  discoveredBlePaused = false;
  discoveredBleFrozenSnapshot: DiscoveredBleCandidate[] | null = null;
  discoveredIgnoredOpen = false;
  readonly discoveredBlePersonDrafts = new Map<string, string>();
  readonly discoveredLatterGroupDrafts = new Map<string, string>();
  readonly discoveredLatterPersonDrafts = new Map<string, string>();
  private readonly discoveredBleSeenCache = new Map<
    string,
    { candidate: DiscoveredBleCandidate; lastSeenMs: number }
  >();

  // Device Security & Time UI draft state
  devicePinDraft = "";
  systemPinDraft = "";
  pinBusy = false;
  worldClockNewLabel = "";
  worldClockNewZone = "";
  overviewAlarmsOpen = false;

  // System Shared Entities & Photo Library UI state
  activeCameraPreviewEntity = "";
  cameraPreviewUrl = "";
  photosFilterCollection = VIRTUAL_COLLECTION_ALL;
  photosSearch = "";
  photosPage = 1;
  photosSelectMode = false;
  readonly photosSelectedIds = new Set<string>();
  photosNewCollectionOpen = false;
  photosNewCollectionName = "";
  photosRenamingCollectionId = "";
  photosRenamingCollectionName = "";
  photosBulkTargetCollectionId = "";

  // System Device Groups & Staged Batch Controls UI state (`Q6`)
  newGroupFormOpen = false;
  newGroupName = "";
  newGroupDesc = "";
  newGroupSourceSubentryId = "";
  newGroupIncludeDisplay = false;
  newGroupIncludeInterface = false;
  readonly openGroupIds = new Set<string>();
  readonly groupCopySourceDrafts = new Map<string, string>();
  batchTargetFilter = "all";
  batchCategoryFilter = "all";
  batchCopySourceSubentryId = "";
  readonly openBatchCategories = new Set<string>();
  readonly batchDraft = new Map<string, unknown>();

  // System BLE & Area Presence UI state
  bleSurveySubentryId = "";
  bleCalibrateAreaId = "";
  bleCalibrateHandoffActive = false;
  bleLiveStreamActive = true;
  readonly bleSurveyFrozen = new Map<
    string,
    { rows: BleSurveyRow[]; packetsSeen: number; activeAreaName: string }
  >();
  readonly openProxyTrims = new Set<string>();
  advancedBleOpen = false;
  readonly openFusionAreas = new Set<string>();

  // System Tools UI state
  announceMode: "notify" | "broadcast" = "notify";
  announceTarget = "all";
  announceTitle = "";
  announceMessage = "";
  announcePriority: "normal" | "warning" | "critical" = "normal";
  announceIncludeCamera = false;
  doorbellTestSubentryId = "";
  doorbellTestReply = "";
  backupExportScope = "system";
  backupRestoreSubentryId = "";
  logsOpen = false;
  logFilter = "all";

  // Modal states
  confirmModal: ConfirmModalState = emptyConfirmModalState();
  removeModal = { open: false, subentryId: "", title: "", busy: false };
  resetModal = { open: false, deviceSettings: true, latterOptions: true, busy: false };
  addBleModal = {
    open: false,
    candidateAddr: "",
    name: "",
    address: "",
    assignedPerson: "",
    bleCategory: "auto",
    busy: false,
  };
  colorWheelModal = {
    open: false,
    targetScope: "system" as StudioScope,
    hex: "",
    name: "",
    busy: false,
    painted: false,
  };
  saveGroupModal = {
    open: false,
    subentryId: "",
    name: "",
    description: "",
    includeDisplay: false,
    includeInterface: false,
    busy: false,
  };
  shortcutModal = {
    open: false,
    listKey: "pinned_items" as "dock_items" | "pinned_items",
    editIndex: null as number | null,
    kind: "route" as "route" | "entity",
    routeTarget: "weather:moon",
    entityDomainFilter: "all",
    entitySearch: "",
    entityTarget: "",
    action: "",
    label: "",
    icon: "",
    iconSearch: "",
    confirm: false,
  };
  appConfigModal: { open: boolean; app: ConfigurableAppId | null } = {
    open: false,
    app: null,
  };
  photoUploadModal: PhotoUploadModalState = emptyPhotoUploadModalState();
  photoEditModal: PhotoEditModalState = emptyPhotoEditModalState();
  mediaImportModal: MediaImportModalState = emptyMediaImportModalState();
  photoPickerModal: PhotoPickerModalState = emptyPhotoPickerModalState();
  returnToPinnedModal = false;

  pendingScrollCardId = "";
  readonly handoffTargetIds = new Set<string>();
  pendingDomRevert: PendingDomRevert | null = null;
  private scrollGen = 0;
  private handoffArming = false;

  // Snapshot-isolated pending settings queues & per-Device config_rev tracker
  pendingSystemPatch: Record<string, unknown> = {};
  pendingSystemPrevious: Record<string, unknown> = {};
  systemSaveTimer: ReturnType<typeof setTimeout> | null = null;
  readonly pendingBlankListSlots: Record<StringListKey, number> = {
    calendar_entities: 0,
    camera_entities: 0,
    remotes_list: 0,
    thermostat_entities: 0,
    lock_entities: 0,
    garage_entities: 0,
    vacuum_entities: 0,
  };
  readonly pendingDeviceBuckets = new Map<string, DevicePendingBucket>();
  readonly pendingEntityStates = new Map<string, PendingEntityEntry>();
  private readonly deviceConfigRevs = new Map<string, number>();

  // Subscription & reconnect state
  private subGen = 0;
  private stateReqSeq = 0;
  private lastAppliedReqSeq = 0;
  private wsUnsub: (() => void) | null = null;
  private subscribedKey = "";
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private boundConnection: HassConnection | null = null;
  private routeApplying = false;

  private readonly onConnectionReady = (): void => {
    if (this.studioRevMismatch || !this.host.isConnected) return;
    this.reconnectAttempt = 0;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    void this.ensureSubscription(true);
  };

  constructor(host: ReactiveControllerHost & HTMLElement) {
    this.host = host;
    this.ws = new StudioWsClient(() => {
      this.handleStudioRevMismatch();
    });
    this.entity = new EntityController(this);
    this.groups = new GroupsController(this);
    this.tools = new ToolsController(this);
  }

  // ---------- Convenience i18n & Confirm Shortcuts ----------

  get localeOverlay(): Readonly<Record<string, string>> | null {
    const raw = this.state?.locale_strings;
    return raw && typeof raw === "object" ? raw : null;
  }

  t(key: StudioTranslationKey, vars?: Readonly<Record<string, string | number>>): string {
    return t(key, vars, this.localeOverlay);
  }

  tPrefLabel(key: string, fallback?: string): string {
    return tPrefLabel(key, fallback, this.localeOverlay);
  }

  tPrefOption(prefKey: string, opt: string): string {
    return tPrefOption(prefKey, opt, this.localeOverlay);
  }

  openConfirm(opts: OpenConfirmOptions): void {
    this.tools.openConfirm(opts);
  }

  closeConfirm(): void {
    this.tools.closeConfirm();
  }

  async runConfirmedAction(): Promise<void> {
    await this.tools.runConfirmedAction();
  }

  // ---------- Config Revision & Live Clock Helpers ----------

  getKnownDeviceConfigRev(subentryId: string): number {
    if (this.state?.subentry_id === subentryId && this.state.device_config_rev > 0) {
      return this.state.device_config_rev;
    }
    return this.deviceConfigRevs.get(subentryId) ?? 0;
  }

  recordKnownDeviceConfigRev(subentryId: string, rev: number): void {
    if (subentryId && rev > 0) {
      this.deviceConfigRevs.set(subentryId, rev);
    }
  }

  activeTimerRemainingSec(): number {
    const live = this.state?.live;
    if (!live) return 0;
    if (live.timer_running && live.timer_ends_at) {
      const endsMs = Date.parse(live.timer_ends_at);
      if (Number.isFinite(endsMs)) {
        return Math.max(0, Math.ceil((endsMs - this.liveClockNowMs) / 1000));
      }
    }
    return Math.max(0, Math.round(Number(live.timer_remaining_sec || 0)));
  }

  activeStopwatchElapsedSec(): number {
    const live = this.state?.live;
    if (!live) return 0;
    if (live.stopwatch_running && live.stopwatch_started_at) {
      const startedMs = Date.parse(live.stopwatch_started_at);
      if (Number.isFinite(startedMs)) {
        return Math.max(0, Math.floor((this.liveClockNowMs - startedMs) / 1000));
      }
    }
    return Math.max(0, Math.round(Number(live.stopwatch_elapsed_sec || 0)));
  }

  private syncLiveClockTimer(): void {
    const live = this.state?.live;
    const shouldTick =
      this.host.isConnected &&
      this.currentScope === "device" &&
      this.deviceSelected &&
      !this.deviceLoading &&
      this.currentViewId === "dashboard" &&
      Boolean(
        (live?.timer_running && live.timer_ends_at) ||
          (live?.stopwatch_running && live.stopwatch_started_at),
      );

    if (shouldTick) {
      this.liveClockNowMs = Date.now();
      if (this.liveClockTimer === null) {
        this.liveClockTimer = setInterval(() => {
          this.liveClockNowMs = Date.now();
          this.host.requestUpdate();
        }, 1000);
      }
    } else if (this.liveClockTimer !== null) {
      clearInterval(this.liveClockTimer);
      this.liveClockTimer = null;
    }
  }

  // ---------- Controller Lifecycle ----------

  hostConnected(): void {
    this.syncConnectionListener();
    this.syncLiveClockTimer();
    if (this.ws.hass && !this.studioRevMismatch) {
      void this.ensureSubscription(false);
    }
  }

  hostDisconnected(): void {
    if (this.toastTimer) {
      clearTimeout(this.toastTimer);
      this.toastTimer = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.liveClockTimer !== null) {
      clearInterval(this.liveClockTimer);
      this.liveClockTimer = null;
    }
    this.detachConnectionListener();
    void this.entity.flushAllPendingSettings();
    this.teardownSubscription();
  }

  hostUpdated(): void {
    if (this.pendingDomRevert) {
      const rev = this.pendingDomRevert;
      this.pendingDomRevert = null;
      const root = (this.host as unknown as { renderRoot?: ShadowRoot }).renderRoot;
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
    if (this.pendingScrollCardId) {
      const cardId = this.pendingScrollCardId;
      this.pendingScrollCardId = "";
      const root =
        (this.host as unknown as { renderRoot?: ShadowRoot }).renderRoot ||
        this.host.shadowRoot;
      const target = root?.getElementById(cardId) as HTMLElement | null;
      if (target && typeof target.scrollIntoView === "function") {
        const myGen = ++this.scrollGen;
        const reducedMotion = Boolean(
          typeof globalThis.matchMedia === "function" &&
            globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches,
        );
        void this.scrollIntoViewAsync(target, {
          behavior: reducedMotion ? "auto" : "smooth",
          block: "start",
        }).then(() => {
          if (myGen !== this.scrollGen || !this.handoffTargetIds.has(cardId)) return;
          if (typeof target.focus === "function") {
            if (
              typeof target.hasAttribute === "function" &&
              !target.hasAttribute("tabindex")
            ) {
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
    this.handoffArming = false;
  }

  mergeDomRevert(controlIds: Record<string, string | boolean>): void {
    this.pendingDomRevert = {
      controlIds: {
        ...(this.pendingDomRevert?.controlIds || {}),
        ...controlIds,
      },
    };
  }

  private scrollIntoViewAsync(
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

  // ---------- Handoff Highlighting & Focus ----------

  isHandoffTarget(targetId: string): boolean {
    return Boolean(targetId) && this.handoffTargetIds.has(targetId);
  }

  clearHandoffTargets(): void {
    this.bleCalibrateHandoffActive = false;
    this.handoffTargetIds.clear();
    this.handoffArming = false;
  }

  private applySectionHandoff(scrollId = "", highlightIds?: readonly string[]): void {
    const cleanScroll = String(scrollId || "").trim();
    this.pendingScrollCardId = cleanScroll;
    const ids =
      highlightIds && highlightIds.length > 0
        ? highlightIds
        : cleanScroll
          ? [cleanScroll]
          : [];
    for (const rawId of ids) {
      const id = String(rawId || "").trim();
      if (id) this.handoffTargetIds.add(id);
    }
    if (this.handoffTargetIds.size > 0) {
      this.handoffArming = true;
      this.host.requestUpdate();
    }
  }

  onMainFocusIn(ev: FocusEvent): void {
    if (this.handoffArming || this.handoffTargetIds.size === 0) return;
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
      if (cur.id && this.handoffTargetIds.has(cur.id)) {
        return;
      }
      cur = cur.parentElement;
    }
    this.handoffTargetIds.clear();
    this.host.requestUpdate();
  }

  // ---------- Home Assistant Connection & Live Announcements ----------

  private syncConnectionListener(): void {
    const nextConn = this.host.isConnected ? (this.ws.hass?.connection ?? null) : null;
    if (this.boundConnection === nextConn) return;
    this.detachConnectionListener();
    if (nextConn && typeof nextConn.addEventListener === "function") {
      nextConn.addEventListener("ready", this.onConnectionReady);
      this.boundConnection = nextConn;
    }
  }

  private detachConnectionListener(): void {
    if (this.boundConnection && typeof this.boundConnection.removeEventListener === "function") {
      try {
        this.boundConnection.removeEventListener("ready", this.onConnectionReady);
      } catch {
        // Ignore teardown errors on closed sockets.
      }
    }
    this.boundConnection = null;
  }

  private handleStudioRevMismatch(): void {
    this.studioRevMismatch = true;
    this.loading = false;
    this.deviceLoading = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.teardownSubscription();
    this.host.requestUpdate();
  }

  setHass(hass: HomeAssistant | null): void {
    const prevConn = this.ws.hass?.connection ?? null;
    this.ws.setHass(hass);
    this.syncConnectionListener();
    const connChanged = Boolean(hass?.connection && hass.connection !== prevConn);
    if (connChanged && this.host.isConnected && !this.studioRevMismatch) {
      void this.ensureSubscription(false);
    }
  }

  get hass(): HomeAssistant | null {
    return this.ws.hass;
  }

  reloadPage(): void {
    globalThis.location.reload();
  }

  announcePolite(message: string): void {
    const clean = String(message || "").trim();
    if (!clean) return;
    this.politeSeq += 1;
    this.politeAnnouncement = this.politeSeq % 2 === 0 ? `${clean}\u200B` : clean;
    this.host.requestUpdate();
  }

  announceAssertive(message: string): void {
    const clean = String(message || "").trim();
    if (!clean) return;
    this.assertiveSeq += 1;
    this.assertiveAnnouncement = this.assertiveSeq % 2 === 0 ? `${clean}\u200B` : clean;
    this.host.requestUpdate();
  }

  showToast(message: string, isError = false): void {
    const clean = String(message || "");
    this.toastMessage = clean;
    this.toastIsError = isError;
    if (this.toastTimer) {
      clearTimeout(this.toastTimer);
      this.toastTimer = null;
    }
    if (isError) {
      this.announceAssertive(clean);
    } else {
      this.announcePolite(clean);
      this.toastTimer = setTimeout(() => {
        this.toastMessage = "";
        this.host.requestUpdate();
      }, INFO_TOAST_DURATION_MS);
    }
    this.host.requestUpdate();
  }

  dismissToast(): void {
    if (this.toastTimer) {
      clearTimeout(this.toastTimer);
      this.toastTimer = null;
    }
    this.toastMessage = "";
    this.toastIsError = false;
    this.host.requestUpdate();
  }

  shouldIncludeLogs(): boolean {
    return (
      this.currentScope === "system" &&
      this.currentViewId === "system_tools" &&
      this.logsOpen
    );
  }

  get pageTitle(): string {
    const key = VIEW_TITLE_KEYS[this.currentViewId] || "view.select_device_prompt";
    return this.t(key);
  }

  get pageSubtitle(): string {
    if (
      this.currentScope === "device" &&
      this.deviceSelected &&
      this.currentViewId !== "select_device_prompt" &&
      this.currentViewId !== "discovered_devices"
    ) {
      if (this.state?.subentry_id === this.activeSubentryId && this.state.title) {
        return this.state.title;
      }
      const entry = this.state?.system_devices?.find(
        (d) => d.subentry_id === this.activeSubentryId,
      );
      return entry?.title || "";
    }
    return "";
  }

  get hasConfiguredSecurityPin(): boolean {
    return Boolean(
      this.state?.config?.has_security_pin ??
        this.state?.live?.has_security_pin ??
        this.state?.has_security_pin,
    );
  }

  deviceHasView(viewId: DeviceViewId): boolean {
    if (this.state?.subentry_id !== this.activeSubentryId) {
      const entry = this.state?.system_devices?.find(
        (d) => d.subentry_id === this.activeSubentryId,
      );
      if (entry?.kind === "ble_tag") {
        return deviceHasView(viewId, undefined, "ble_tag");
      }
      return deviceHasView(viewId, undefined, undefined);
    }
    return deviceHasView(viewId, this.state?.capabilities, this.state?.config?.kind);
  }

  // ---------- Unified Active Device Transition & Routing ----------

  /**
   * Single transition helper clearing Device-scoped drafts/modals and flushing (or discarding)
   * pending edits across `applyRoute`, `switchSystemDevice`, and removal/invalid redirects (`B-07`, `B-24`).
   */
  onActiveDeviceChanged(
    prevId: string,
    nextId: string,
    options?: { discardPrevPending?: boolean },
  ): void {
    const cleanPrev = String(prevId || "").trim();
    const cleanNext = String(nextId || "").trim();

    if (cleanPrev && cleanPrev !== cleanNext) {
      if (options?.discardPrevPending) {
        this.entity.discardDeviceBucket(cleanPrev);
      } else {
        void this.entity.flushDeviceBucket(cleanPrev);
      }
    }

    if (cleanPrev !== cleanNext) {
      this.devicePinDraft = "";
      this.worldClockNewLabel = "";
      this.worldClockNewZone = "";
      this.overviewAlarmsOpen = false;
      this.appConfigModal = { open: false, app: null };
      this.photoPickerModal = emptyPhotoPickerModalState();
      this.shortcutModal = { ...this.shortcutModal, open: false };
      this.saveGroupModal = { ...this.saveGroupModal, open: false, busy: false };
      this.resetModal = { ...this.resetModal, open: false, busy: false };
      this.removeModal = { ...this.removeModal, open: false, busy: false };
      this.returnToPinnedModal = false;
      this.clearHandoffTargets();
    }

    this.activeSubentryId = cleanNext;
    this.deviceSelected = Boolean(cleanNext);
    this.deviceLoading = Boolean(cleanNext && this.state?.subentry_id !== cleanNext);
    this.syncLiveClockTimer();
  }

  applyRoute(route: HassRoute | null | undefined): void {
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

    const prevScope = this.currentScope;
    const prevViewId = this.currentViewId;
    const prevSubId = this.activeSubentryId;
    this.routeApplying = true;
    try {
      if (parts[0] === "devices" && parts[1]?.toLowerCase() === "discovered") {
        this.onActiveDeviceChanged(prevSubId, "");
        if (prevScope !== "device" || prevViewId !== "discovered_devices") {
          this.clearHandoffTargets();
        }
        this.currentScope = "device";
        this.currentViewId = "discovered_devices";
      } else if (parts[0] === "devices" && parts[1]) {
        const nextSubId = parts[1];
        if (
          this.state &&
          Array.isArray(this.state.system_devices) &&
          !this.state.system_devices.some((d) => d.subentry_id === nextSubId)
        ) {
          this.redirectInvalidDeviceRoute(nextSubId);
          return;
        }
        const requestedView = slugToView(DEVICE_VIEW_SLUGS, parts[2] || "overview") || "dashboard";
        this.onActiveDeviceChanged(prevSubId, nextSubId);
        const validView = this.deviceHasView(requestedView) ? requestedView : "dashboard";
        if (prevScope !== "device" || prevViewId !== validView || prevSubId !== nextSubId) {
          this.clearHandoffTargets();
        }
        this.currentScope = "device";
        this.currentViewId = validView;
        if (validView !== requestedView) {
          navigateHaPath(
            `/latter/devices/${encodeURIComponent(nextSubId)}/${DEVICE_VIEW_SLUGS[validView]}`,
            true,
          );
        }
      } else if (parts[0] === "system") {
        this.onActiveDeviceChanged(prevSubId, "");
        const viewId = slugToView(SYSTEM_VIEW_SLUGS, parts[1] || "overview") || "system_overview";
        if (prevScope !== "system" || prevViewId !== viewId) {
          this.clearHandoffTargets();
        } else if (viewId !== "area_tracking") {
          this.bleCalibrateHandoffActive = false;
        }
        this.currentScope = "system";
        this.currentViewId = viewId;
        if (viewId === "area_tracking") {
          this.ensureDefaultSurveyDevice();
        }
      } else {
        this.onActiveDeviceChanged(prevSubId, "");
        if (prevScope !== "device" || prevViewId !== "select_device_prompt") {
          this.clearHandoffTargets();
        }
        this.currentScope = "device";
        this.currentViewId = "select_device_prompt";
      }
      this.syncLiveClockTimer();
      this.host.requestUpdate();
    } finally {
      this.routeApplying = false;
    }

    if (this.host.isConnected && this.ws.hass && !this.studioRevMismatch) {
      void this.ensureSubscription(false);
    }
  }

  redirectInvalidDeviceRoute(invalidId?: string): void {
    const dropId = invalidId ?? this.activeSubentryId;
    this.onActiveDeviceChanged(dropId, "", { discardPrevPending: true });
    this.currentScope = "device";
    this.currentViewId = "select_device_prompt";
    navigateHaPath("/latter/devices", true);
    if (dropId) {
      this.showToast(this.t("sync.device_not_found"), false);
    }
    this.host.requestUpdate();
    if (this.host.isConnected && this.ws.hass && !this.studioRevMismatch) {
      void this.ensureSubscription(false);
    }
  }

  syncUrl(replace = false): void {
    if (this.routeApplying) return;
    let targetPath = "/latter/devices";
    if (this.currentScope === "system") {
      const slug = SYSTEM_VIEW_SLUGS[this.currentViewId as SystemViewId] || "overview";
      targetPath = `/latter/system/${slug}`;
    } else if (this.currentViewId === "discovered_devices") {
      targetPath = "/latter/devices/discovered";
    } else if (
      this.deviceSelected &&
      this.activeSubentryId &&
      this.currentViewId !== "select_device_prompt"
    ) {
      const slug =
        DEVICE_VIEW_SLUGS[
          this.currentViewId as Exclude<
            DeviceViewId,
            "select_device_prompt" | "discovered_devices"
          >
        ] || "overview";
      targetPath = `/latter/devices/${encodeURIComponent(this.activeSubentryId)}/${slug}`;
    }
    if (globalThis.location?.pathname !== targetPath) {
      navigateHaPath(targetPath, replace);
    }
  }

  openDevicesLanding(): void {
    this.onActiveDeviceChanged(this.activeSubentryId, "");
    this.clearHandoffTargets();
    this.currentScope = "device";
    this.currentViewId = "select_device_prompt";
    this.syncLiveClockTimer();
    this.syncUrl();
    this.host.requestUpdate();
    void this.ensureSubscription(false);
  }

  openDiscoveredDevices(cardId = ""): void {
    this.onActiveDeviceChanged(this.activeSubentryId, "");
    this.clearHandoffTargets();
    this.currentScope = "device";
    this.currentViewId = "discovered_devices";
    this.syncLiveClockTimer();
    this.syncUrl();
    this.host.requestUpdate();
    this.applySectionHandoff(cardId);
    void this.ensureSubscription(false);
  }

  openDevicesWithCategory(category: string): void {
    this.deviceCategoryFilter = category;
    this.openDevicesLanding();
  }

  setScope(scope: StudioScope, explicitViewId?: StudioViewId): void {
    if (scope === "device" && this.currentScope !== "device") {
      void this.entity.flushSystemSettings();
    } else if (scope === "system") {
      this.onActiveDeviceChanged(this.activeSubentryId, "");
    }
    this.clearHandoffTargets();
    this.currentScope = scope;
    if (explicitViewId) {
      this.currentViewId = explicitViewId;
    } else if (scope === "system") {
      this.currentViewId = "system_overview";
    } else {
      this.currentViewId =
        this.deviceSelected && this.activeSubentryId ? "dashboard" : "select_device_prompt";
    }
    if (this.currentViewId === "area_tracking") {
      this.ensureDefaultSurveyDevice();
    }
    this.syncLiveClockTimer();
    this.syncUrl();
    this.host.requestUpdate();
    void this.ensureSubscription(false);
  }

  switchView(viewId: StudioViewId): void {
    if (viewId === "select_device_prompt") {
      this.openDevicesLanding();
      return;
    }
    if (viewId === "discovered_devices") {
      this.openDiscoveredDevices();
      return;
    }
    this.clearHandoffTargets();
    const isSys = Object.prototype.hasOwnProperty.call(SYSTEM_VIEW_SLUGS, viewId);
    if (isSys) {
      this.onActiveDeviceChanged(this.activeSubentryId, "");
    }
    this.currentScope = isSys ? "system" : "device";
    this.currentViewId = viewId;
    if (viewId === "area_tracking") {
      this.ensureDefaultSurveyDevice();
    }
    this.syncLiveClockTimer();
    this.syncUrl();
    this.host.requestUpdate();
    void this.ensureSubscription(false);
  }

  openSystemSection(
    viewId: SystemViewId,
    cardId = "",
    highlightIds?: readonly string[],
  ): void {
    this.switchView(viewId);
    this.applySectionHandoff(cardId, highlightIds);
  }

  openDeviceSection(
    viewId: Exclude<DeviceViewId, "select_device_prompt" | "discovered_devices">,
    cardId = "",
    highlightIds?: readonly string[],
  ): void {
    this.switchView(viewId);
    this.applySectionHandoff(cardId, highlightIds);
  }

  openManageGroups(groupId = ""): void {
    const cleanId = String(groupId || "").trim();
    if (cleanId && cleanId !== "custom") {
      this.openGroupIds.add(cleanId);
      this.openSystemSection("system_sync", `group-box-${cleanId}`);
      return;
    }
    this.openSystemSection("system_sync");
  }

  async switchSystemDevice(
    nextSubentryId: string,
    targetView: DeviceViewId = "dashboard",
  ): Promise<void> {
    const cleanNext = String(nextSubentryId || "").trim();
    if (!cleanNext) return;
    this.onActiveDeviceChanged(this.activeSubentryId, cleanNext);
    this.currentScope = "device";
    const desired =
      targetView === "select_device_prompt" || targetView === "discovered_devices"
        ? "dashboard"
        : targetView;
    this.currentViewId = this.deviceHasView(desired) ? desired : "dashboard";
    this.syncLiveClockTimer();
    this.syncUrl();
    this.host.requestUpdate();
    await this.ensureSubscription(false);
  }

  openHaPage(path: string): void {
    navigateHaPath(path, false);
  }

  openDeviceInHa(preferLatterEntry = false): void {
    const links = this.state?.links;
    const devId = preferLatterEntry
      ? links?.latter_device_id || links?.esphome_device_id || ""
      : links?.esphome_device_id || links?.latter_device_id || "";
    if (devId) {
      this.openHaPage(`/config/devices/device/${encodeURIComponent(devId)}`);
    } else {
      this.openHaPage("/config/integrations/integration/latter");
    }
  }

  toggleParentHaSidebar(): void {
    this.host.dispatchEvent(
      new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }),
    );
  }

  // ---------- Subscription, Backoff & State Ingestion ----------

  teardownSubscription(): void {
    this.subGen += 1;
    if (typeof this.wsUnsub === "function") {
      try {
        this.wsUnsub();
      } catch {
        // Ignore stale unsubscribe errors on disconnect.
      }
    }
    this.wsUnsub = null;
    this.subscribedKey = "";
  }

  desiredSubscriptionKey(): string {
    const sub = this.deviceSelected ? this.activeSubentryId || "" : "";
    const survey =
      this.currentScope === "system" &&
      this.currentViewId === "area_tracking" &&
      this.bleLiveStreamActive
        ? this.bleSurveySubentryId || ""
        : "";
    const logs = this.shouldIncludeLogs() ? "1" : "0";
    return `${sub}|${survey}|${logs}`;
  }

  async ensureSubscription(forceResubscribe = false): Promise<void> {
    if (this.studioRevMismatch || !this.ws.hass?.connection) return;
    const nextKey = this.desiredSubscriptionKey();
    if (!forceResubscribe && this.wsUnsub && this.subscribedKey === nextKey) {
      return;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.teardownSubscription();
    const myGen = ++this.subGen;
    const targetSubId = this.deviceSelected ? this.activeSubentryId || null : null;
    const surveyId =
      this.currentScope === "system" &&
      this.currentViewId === "area_tracking" &&
      this.bleLiveStreamActive
        ? this.bleSurveySubentryId || null
        : null;
    const includeLogs = this.shouldIncludeLogs();

    try {
      const unsub = await this.ws.subscribe(
        {
          subentryId: targetSubId,
          surveySubentryId: surveyId,
          includeLogs,
        },
        (eventPayload) => {
          if (myGen !== this.subGen || !eventPayload) return;
          this.handleSubscriptionEvent(eventPayload, includeLogs);
        },
      );
      if (myGen !== this.subGen) {
        try {
          unsub();
        } catch {
          // Ignore stale teardown.
        }
        return;
      }
      this.wsUnsub = unsub;
      this.subscribedKey = nextKey;
      this.reconnectAttempt = 0;
    } catch (err) {
      if (isStudioRevMismatchError(err) || this.studioRevMismatch) {
        this.handleStudioRevMismatch();
        return;
      }
      if (!this.state) {
        this.loading = false;
        this.loadError = formatWsError(err, "Latter Studio could not connect.");
        this.host.requestUpdate();
      }
      const delay =
        RECONNECT_BACKOFF_MS[
          Math.min(this.reconnectAttempt, RECONNECT_BACKOFF_MS.length - 1)
        ];
      this.reconnectAttempt += 1;
      if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        if (this.host.isConnected && !this.studioRevMismatch) {
          void this.ensureSubscription(true);
        }
      }, delay);
    }
  }

  async refreshState(options?: { includeLogs?: boolean }): Promise<void> {
    if (this.studioRevMismatch || !this.ws.hass) return;
    const reqSeq = ++this.stateReqSeq;
    const targetSubId = this.deviceSelected ? this.activeSubentryId || null : null;
    const includeLogs = options?.includeLogs ?? this.shouldIncludeLogs();
    try {
      const payload = await this.ws.getState({
        subentryId: targetSubId,
        includeLogs,
      });
      if (reqSeq < this.lastAppliedReqSeq) return;
      this.lastAppliedReqSeq = reqSeq;
      this.loadError = "";
      this.loading = false;
      this.ingestPayload(payload, includeLogs);
      if (!this.wsUnsub && this.host.isConnected && !this.studioRevMismatch) {
        void this.ensureSubscription(false);
      }
    } catch (err) {
      if (isStudioRevMismatchError(err) || this.studioRevMismatch) {
        this.handleStudioRevMismatch();
        return;
      }
      if (reqSeq < this.lastAppliedReqSeq) return;
      this.loading = false;
      this.loadError = formatWsError(err, "Latter Studio could not load.");
      this.host.requestUpdate();
    }
  }

  private handleSubscriptionEvent(raw: unknown, subscribedWithLogs: boolean): void {
    if (!raw || typeof raw !== "object") return;
    const rec = raw as Record<string, unknown>;
    if (rec.type === "ble_survey_delta") {
      this.applyBleSurveyDelta(rec as unknown as BleSurveyDeltaEvent);
      return;
    }

    const payload = raw as StudioStatePayload;
    this.loading = false;
    this.loadError = "";
    this.ingestPayload(payload, subscribedWithLogs);
  }

  applyBleSurveyDelta(delta: BleSurveyDeltaEvent): void {
    if (!this.state) return;
    if (!this.bleLiveStreamActive) {
      let updated = false;
      if (Array.isArray(delta.ble_area_signatures)) {
        this.state = {
          ...this.state,
          ble_area_signatures: delta.ble_area_signatures as BleAreaSignatureSummary[],
        };
        updated = true;
      }
      if (Array.isArray(delta.area_presence_grid) && this.state.live) {
        this.state = {
          ...this.state,
          live: {
            ...this.state.live,
            area_presence_grid: delta.area_presence_grid as AreaPresenceRow[],
          },
        };
        updated = true;
      }
      if (updated) {
        this.host.requestUpdate();
      }
      return;
    }

    const targetId = String(
      delta.subentry_id || this.bleSurveySubentryId || this.state.subentry_id || "",
    );
    let nextDevices = this.state.system_devices;
    let nextLive = this.state.live;
    if (Array.isArray(delta.ble_survey_rows)) {
      const nextRows: BleSurveyRow[] = delta.ble_survey_rows;
      const winRow = nextRows.find((r) => r.is_winner);
      if (Array.isArray(nextDevices) && targetId) {
        nextDevices = nextDevices.map((dev) => {
          if (dev.subentry_id !== targetId) return dev;
          return {
            ...dev,
            ble_survey_rows: nextRows,
            ble_packets_seen:
              typeof delta.ble_packets_seen === "number"
                ? delta.ble_packets_seen
                : dev.ble_packets_seen,
            active_area_name: winRow?.area_name || dev.active_area_name,
          };
        });
      }
      if (
        this.state.subentry_id === targetId &&
        nextLive &&
        typeof delta.ble_closest_proxy === "string"
      ) {
        nextLive = {
          ...nextLive,
          ble_closest_proxy: delta.ble_closest_proxy,
        };
      }
    }
    if (Array.isArray(delta.area_presence_grid) && nextLive) {
      nextLive = {
        ...nextLive,
        area_presence_grid: delta.area_presence_grid as AreaPresenceRow[],
      };
    }
    this.state = {
      ...this.state,
      system_devices: nextDevices,
      ble_area_signatures: Array.isArray(delta.ble_area_signatures)
        ? (delta.ble_area_signatures as BleAreaSignatureSummary[])
        : this.state.ble_area_signatures,
      live: nextLive,
    };
    this.host.requestUpdate();
  }

  private mergeFrozenBleRows(
    devices: StudioStatePayload["system_devices"],
  ): StudioStatePayload["system_devices"] {
    if (this.bleLiveStreamActive || !Array.isArray(devices)) return devices;
    return devices.map((dev) => {
      if (!dev.subentry_id) return dev;
      const frozen = this.bleSurveyFrozen.get(dev.subentry_id);
      if (frozen) {
        return {
          ...dev,
          ble_survey_rows: frozen.rows.map((r) => ({ ...r })),
          ble_packets_seen: frozen.packetsSeen,
          active_area_name: frozen.activeAreaName,
        };
      }
      this.bleSurveyFrozen.set(dev.subentry_id, {
        rows: (dev.ble_survey_rows || []).map((r) => ({ ...r })),
        packetsSeen: dev.ble_packets_seen ?? 0,
        activeAreaName: dev.active_area_name || "",
      });
      return dev;
    });
  }

  ingestPayload(incoming: StudioStatePayload, logsWereRequested: boolean): void {
    const prev = this.state;
    const prevSysConfig = prev?.system_config;

    // Resolve section-hash omitted fields (`#10`)
    const mergedCatalog = incoming.catalog ?? prev?.catalog;
    const mergedPrefSpecs = incoming.pref_specs ?? prev?.pref_specs;
    const mergedWorldClockZones = incoming.world_clock_zones ?? prev?.world_clock_zones;
    const mergedSystemWallpapers =
      incoming.system_wallpapers ?? prev?.system_wallpapers ?? [];
    const mergedPhotoCollections =
      incoming.photo_collections ?? prev?.photo_collections ?? [];
    const mergedBleSignatures =
      incoming.ble_area_signatures ?? prev?.ble_area_signatures;
    const mergedDiscoveredBle =
      incoming.discovered_ble_devices !== undefined
        ? this.stabilizeDiscoveredBle(
            incoming.discovered_ble_devices,
            incoming.system_devices,
          )
        : prev?.discovered_ble_devices ?? [];
    const mergedLogs =
      logsWereRequested ||
      (Array.isArray(incoming.internal_logs) && incoming.internal_logs.length > 0)
        ? incoming.internal_logs || []
        : prev?.internal_logs || [];
    const mergedSystemDevices = this.mergeFrozenBleRows(incoming.system_devices);

    if (incoming.subentry_id && incoming.device_config_rev > 0) {
      this.recordKnownDeviceConfigRev(incoming.subentry_id, incoming.device_config_rev);
    }

    // Active Device missing from `system_devices` -> discard pending edits & redirect to `/latter/devices` (`B-19`, `B-24`)
    if (
      this.deviceSelected &&
      this.activeSubentryId &&
      Array.isArray(mergedSystemDevices) &&
      !mergedSystemDevices.some((d) => d.subentry_id === this.activeSubentryId)
    ) {
      const sysOnly: StudioStatePayload = {
        ...incoming,
        system_devices: mergedSystemDevices,
        discovered_ble_devices: mergedDiscoveredBle,
        photo_collections: mergedPhotoCollections,
        system_wallpapers: mergedSystemWallpapers,
        ble_area_signatures: mergedBleSignatures,
        catalog: mergedCatalog,
        pref_specs: mergedPrefSpecs,
        world_clock_zones: mergedWorldClockZones,
        internal_logs: mergedLogs,
        device_prefs: incoming.device_prefs || [],
      };
      const effSysPatch = this.entity.getEffectiveSystemPatch();
      if (Object.keys(effSysPatch).length > 0 && sysOnly.system_config) {
        sysOnly.system_config = {
          ...sysOnly.system_config,
          ...(effSysPatch as Partial<SystemConfig>),
        };
      }
      overlayPendingBlankListSlots(this, sysOnly, prevSysConfig);
      this.state = sysOnly;
      this.redirectInvalidDeviceRoute(this.activeSubentryId);
      return;
    }

    // Cross-Device payload guard (`B-01`, `B-02`, `R-2`):
    // When a Device is selected, never clobber Device-specific sections with a mismatched `subentry_id` payload.
    if (
      this.deviceSelected &&
      this.activeSubentryId &&
      incoming.subentry_id !== this.activeSubentryId
    ) {
      const keepPrevDevice = prev && prev.subentry_id === this.activeSubentryId;
      const sysMerged: StudioStatePayload = {
        ...(keepPrevDevice ? prev : incoming),
        version: incoming.version,
        studio_rev: incoming.studio_rev ?? prev?.studio_rev,
        system_config_rev: incoming.system_config_rev,
        system_info: incoming.system_info ?? prev?.system_info,
        locale_strings: incoming.locale_strings ?? prev?.locale_strings,
        internal_logs: mergedLogs,
        system_devices: mergedSystemDevices,
        issues: incoming.issues,
        ble_proxy_count: incoming.ble_proxy_count,
        ble_area_signatures: mergedBleSignatures,
        discovered_latter_devices: incoming.discovered_latter_devices,
        ignored_latter_devices:
          incoming.ignored_latter_devices ?? prev?.ignored_latter_devices,
        discovered_ble_devices: mergedDiscoveredBle,
        system_controls: incoming.system_controls,
        device_groups: incoming.device_groups,
        system_config: incoming.system_config,
        has_security_pin: incoming.has_security_pin,
        photo_collections: mergedPhotoCollections,
        system_wallpapers: mergedSystemWallpapers,
        doorbells: incoming.doorbells,
        catalog: mergedCatalog,
        pref_specs: mergedPrefSpecs,
        world_clock_zones: mergedWorldClockZones,
        // Preserve active Device fields if already loaded, else clean empty placeholders while `deviceLoading` stays true
        subentry_id: keepPrevDevice ? prev.subentry_id : "",
        title: keepPrevDevice ? prev.title : "",
        device_config_rev: keepPrevDevice ? prev.device_config_rev : 0,
        capabilities: keepPrevDevice ? prev.capabilities : {},
        config: keepPrevDevice ? prev.config : {},
        device_prefs: keepPrevDevice ? prev.device_prefs : [],
        quick_actions: keepPrevDevice ? prev.quick_actions : [],
        speaker_volume: keepPrevDevice ? prev.speaker_volume : null,
        esphome: keepPrevDevice ? prev.esphome : { device: {}, sections: [] },
        wallpapers: keepPrevDevice ? prev.wallpapers : [],
        links: keepPrevDevice ? prev.links : undefined,
        live: keepPrevDevice
          ? {
              ...prev.live,
              area_presence_grid:
                incoming.live?.area_presence_grid ?? prev.live.area_presence_grid,
            }
          : { area_presence_grid: incoming.live?.area_presence_grid },
      };

      const effSysPatch = this.entity.getEffectiveSystemPatch();
      if (Object.keys(effSysPatch).length > 0 && sysMerged.system_config) {
        sysMerged.system_config = {
          ...sysMerged.system_config,
          ...(effSysPatch as Partial<SystemConfig>),
        };
      }
      overlayPendingBlankListSlots(this, sysMerged, prevSysConfig);

      this.deviceLoading = !keepPrevDevice;
      this.state = sysMerged;
      this.ensureDefaultSurveyDevice();
      this.ensureDefaultDoorbellTester();
      this.ensureValidBatchTargetFilter();
      this.syncLiveClockTimer();
      this.host.requestUpdate();
      if (!keepPrevDevice && this.host.isConnected && this.ws.hass && !this.studioRevMismatch) {
        void this.ensureSubscription(false);
      }
      return;
    }

    // Matching payload (either System/list view or matching `activeSubentryId`)
    this.deviceLoading = false;
    const merged: StudioStatePayload = {
      ...incoming,
      system_devices: mergedSystemDevices,
      discovered_ble_devices: mergedDiscoveredBle,
      photo_collections: mergedPhotoCollections,
      system_wallpapers: mergedSystemWallpapers,
      ble_area_signatures: mergedBleSignatures,
      catalog: mergedCatalog,
      pref_specs: mergedPrefSpecs,
      world_clock_zones: mergedWorldClockZones,
      internal_logs: mergedLogs,
      device_prefs: incoming.device_prefs || [],
    };

    const effSysPatch = this.entity.getEffectiveSystemPatch();
    if (Object.keys(effSysPatch).length > 0 && merged.system_config) {
      merged.system_config = {
        ...merged.system_config,
        ...(effSysPatch as Partial<SystemConfig>),
      };
    }
    overlayPendingBlankListSlots(this, merged, prevSysConfig);

    if (merged.subentry_id) {
      const effDevPatch = this.entity.getEffectiveDevicePatch(merged.subentry_id);
      if (Object.keys(effDevPatch).length > 0 && merged.config) {
        overlayDevicePrefsOnSections(merged, effDevPatch);
      }
    }

    overlayPendingEntityStates(merged, this.pendingEntityStates);

    if (
      this.currentScope === "device" &&
      this.deviceSelected &&
      merged.subentry_id === this.activeSubentryId &&
      !deviceHasView(
        this.currentViewId as DeviceViewId,
        merged.capabilities,
        merged.config?.kind,
      )
    ) {
      this.currentViewId = "dashboard";
      this.syncUrl(true);
    }

    this.state = merged;
    this.ensureDefaultSurveyDevice();
    this.ensureDefaultDoorbellTester();
    this.ensureValidBatchTargetFilter();
    this.syncLiveClockTimer();
    this.host.requestUpdate();
  }

  private stabilizeDiscoveredBle(
    candidates: readonly DiscoveredBleCandidate[],
    systemDevices: StudioStatePayload["system_devices"],
  ): DiscoveredBleCandidate[] {
    const RETENTION_MS = 90_000;
    const now = Date.now();
    const onboardedSlugs = new Set(
      (systemDevices || [])
        .map((d) => String(d.device_slug || "").trim().toLowerCase())
        .filter(Boolean),
    );
    for (const [addrKey, entry] of this.discoveredBleSeenCache.entries()) {
      const candSlug = String(
        (entry.candidate as unknown as { slug?: string }).slug || "",
      )
        .trim()
        .toLowerCase();
      if (
        now - entry.lastSeenMs > RETENTION_MS ||
        (candSlug && onboardedSlugs.has(candSlug))
      ) {
        this.discoveredBleSeenCache.delete(addrKey);
      }
    }
    const extraNoKey: DiscoveredBleCandidate[] = [];
    for (const c of candidates) {
      const addrKey = String(c.target_address || "").trim().toLowerCase();
      if (addrKey) {
        this.discoveredBleSeenCache.set(addrKey, { candidate: c, lastSeenMs: now });
      } else {
        extraNoKey.push(c);
      }
    }
    return [
      ...Array.from(this.discoveredBleSeenCache.values(), (entry) => entry.candidate),
      ...extraNoKey,
    ];
  }

  toggleDiscoveredBlePause(paused?: boolean): void {
    const next = paused ?? !this.discoveredBlePaused;
    this.discoveredBlePaused = next;
    if (next) {
      this.discoveredBleFrozenSnapshot = [...(this.state?.discovered_ble_devices || [])];
    } else {
      this.discoveredBleFrozenSnapshot = null;
    }
    this.host.requestUpdate();
  }

  evictAdoptedBleCandidate(targetAddress: string): void {
    const addrKey = String(targetAddress || "").trim().toLowerCase();
    if (!addrKey) return;
    this.discoveredBleSeenCache.delete(addrKey);
    this.discoveredBlePersonDrafts.delete(addrKey);
    if (this.discoveredBleFrozenSnapshot) {
      this.discoveredBleFrozenSnapshot = this.discoveredBleFrozenSnapshot.filter(
        (c) => String(c.target_address || "").trim().toLowerCase() !== addrKey,
      );
    }
  }

  private ensureDefaultSurveyDevice(): void {
    const devs = this.state?.system_devices || [];
    const bleDevs = devs.filter((d) => d.ble_tracked || d.kind === "ble_tag");
    if (
      this.bleSurveySubentryId &&
      bleDevs.some((d) => d.subentry_id === this.bleSurveySubentryId)
    ) {
      return;
    }
    const current = bleDevs.find((d) => d.subentry_id === this.activeSubentryId);
    this.bleSurveySubentryId = current?.subentry_id || bleDevs[0]?.subentry_id || "";
  }

  private ensureDefaultDoorbellTester(): void {
    const devs = (this.state?.system_devices || []).filter((d) => d.kind !== "ble_tag");
    if (
      this.doorbellTestSubentryId &&
      devs.some((d) => d.subentry_id === this.doorbellTestSubentryId)
    ) {
      return;
    }
    this.doorbellTestSubentryId = devs[0]?.subentry_id || "";
  }

  private ensureValidBatchTargetFilter(): void {
    if (!this.batchTargetFilter.startsWith("group:")) return;
    const gid = this.batchTargetFilter.slice(6);
    if (gid === "custom") return;
    const groups = this.state?.device_groups || [];
    if (!groups.some((g) => g.id === gid)) {
      this.batchTargetFilter = "all";
      this.groups.resetBatchDraft();
    }
  }
}
