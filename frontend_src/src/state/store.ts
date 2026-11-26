/**
 * Encapsulated Reactive Store Facade for Latter Studio (`StudioStore`, `D-023`, `D-062`, `D-064`).
 *
 * Composes state controllers (`EntityController`, `GroupsController`, `ToolsController`,
 * `SubscriptionController`, & `routing.ts`) over the `StudioStoreContext` contract.
 */

import { StudioWsClient } from "../api/ws-client.js";
import { VIRTUAL_COLLECTION_ALL } from "../constants.js";
import {
  type StudioTranslationKey,
  t,
  tPrefLabel,
  tPrefOption,
  VIEW_TITLE_KEYS,
} from "../i18n/index.js";
import type { ReactiveController, ReactiveControllerHost } from "../lib/lit.js";
import type { MdiIconStyleFilter } from "../mdi-catalog.js";
import type {
  BleSurveyDeltaEvent,
  BleSurveyRow,
  ConfigurableAppId,
  DeviceViewId,
  DiscoveredBleCandidate,
  HassRoute,
  HomeAssistant,
  ShortcutAccent,
  ShortcutBadgeStyle,
  StudioScope,
  StudioStatePayload,
  StudioViewId,
  SystemViewId,
} from "../types.js";
import { navigateHaPath } from "../utils/format.js";
import { EntityController } from "./entity-actions-controller.js";
import {
  isCatalogItemSupported,
  overlayDevicePrefsOnSections,
  overlayPendingEntityStates,
} from "./group-overlay.js";
import { GroupsController } from "./groups-controller.js";
import { clearPhotoImageCache, revokeAllStagedPhotoUploads } from "./photo-ops.js";
import {
  applyRouteOp,
  applySectionHandoffOp,
  deviceHasView,
  hostUpdatedDomOp,
  onActiveDeviceChangedOp,
  onMainFocusInOp,
  openDeviceInHaOp,
  openDevicesLandingOp,
  openDiscoveredDevicesOp,
  redirectInvalidDeviceRouteOp,
  type RoutingRuntime,
  setScopeOp,
  storeDeviceHasView,
  switchSystemDeviceOp,
  switchViewOp,
  syncUrlOp,
} from "./routing.js";
import {
  isProtectedNativeDockItem,
  normalizeShortcutAccent,
  normalizeShortcutBadgeStyle,
  shortcutBadgeClass,
} from "./shortcuts-ops.js";
import {
  type BatchPillState,
  type ConfirmModalState,
  type DevicePendingBucket,
  emptyConfirmModalState,
  emptyMediaImportModalState,
  emptyPhotoEditModalState,
  emptyPhotoPickerModalState,
  emptyPhotoUploadModalState,
  type MediaImportModalState,
  type OpenConfirmOptions,
  type PendingDomRevert,
  type PendingEntityEntry,
  type PhotoEditModalState,
  type PhotoPickerModalState,
  type PhotoUploadModalState,
  type StagedUploadPhoto,
  type StringListKey,
  type StudioStoreContext,
  type TokenListKey,
  type TokenListOps,
} from "./store-types.js";
import { SubscriptionController } from "./subscription.js";
import { ToolsController } from "./tools-controller.js";

export {
  type BatchPillState,
  type ConfirmModalState,
  type DevicePendingBucket,
  deviceHasView,
  EntityController,
  GroupsController,
  isCatalogItemSupported,
  isProtectedNativeDockItem,
  normalizeShortcutAccent,
  normalizeShortcutBadgeStyle,
  shortcutBadgeClass,
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

const INFO_TOAST_DURATION_MS = 3_500;

export class StudioStore implements ReactiveController, StudioStoreContext {
  readonly host: ReactiveControllerHost & HTMLElement;
  readonly ws: StudioWsClient;
  readonly entity: EntityController;
  readonly groups: GroupsController;
  readonly tools: ToolsController;
  private readonly sub: SubscriptionController;
  private readonly routingRt: RoutingRuntime = {
    routeApplying: false,
    scrollGen: 0,
    handoffArming: false,
  };

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

  // Live regions & toast feedback
  toastMessage = "";
  toastIsError = false;
  politeAnnouncement = "";
  assertiveAnnouncement = "";
  private politeSeq = 0;
  private assertiveSeq = 0;
  private toastTimer: ReturnType<typeof setTimeout> | null = null;

  // Local 1 Hz clock tick strictly for active Device Overview timer/stopwatch
  liveClockNowMs = Date.now();
  private liveClockTimer: ReturnType<typeof setInterval> | null = null;

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
  readonly discoveredBleSeenCache = new Map<
    string,
    { candidate: DiscoveredBleCandidate; lastSeenMs: number }
  >();

  // Device Security & Time UI draft state
  devicePinDraft = "";
  systemPinDraft = "";
  showDevicePin = false;
  showSystemPin = false;
  pinBusy = false;
  worldClockNewLabel = "";
  worldClockNewZone = "";
  worldClockRowKeys: string[] = [];
  worldClockRowSeq = 0;
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

  // System Device Groups & Staged Batch Controls UI state
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
    iconStyleFilter: "all" as MdiIconStyleFilter,
    badgeStyle: "" as ShortcutBadgeStyle,
    accent: "" as ShortcutAccent,
    confirm: false,
    tilePage: 0,
    tileCol: null as number | null,
    tileRow: null as number | null,
    tileColSpan: 1,
    tileRowSpan: 1,
  };
  appConfigModal: { open: boolean; app: ConfigurableAppId | null } = { open: false, app: null };
  pinnedActivePage = 0;
  pinnedExtraPages = 0;
  cameraConfigModal = {
    open: false,
    cameraId: "",
    label: "",
    showListen: false,
    showTalk: false,
    showReply: false,
    unlockEntity: "",
  };
  photoUploadModal: PhotoUploadModalState = emptyPhotoUploadModalState();
  photoEditModal: PhotoEditModalState = emptyPhotoEditModalState();
  mediaImportModal: MediaImportModalState = emptyMediaImportModalState();
  photoPickerModal: PhotoPickerModalState = emptyPhotoPickerModalState();
  returnToPinnedModal = false;

  pendingScrollCardId = "";
  readonly handoffTargetIds = new Set<string>();
  pendingDomRevert: PendingDomRevert | null = null;

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
    broadcast_speakers: 0,
    broadcast_phrases: 0,
  };
  readonly pendingDeviceBuckets = new Map<string, DevicePendingBucket>();
  readonly pendingEntityStates = new Map<string, PendingEntityEntry>();
  private readonly deviceConfigRevs = new Map<string, number>();

  constructor(host: ReactiveControllerHost & HTMLElement) {
    this.host = host;
    this.ws = new StudioWsClient(() => {
      this.handleStudioRevMismatch();
    });
    this.entity = new EntityController(this);
    this.groups = new GroupsController(this);
    this.tools = new ToolsController(this);
    this.sub = new SubscriptionController(this);
  }

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

  syncLiveClockTimer(): void {
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

  hostConnected(): void {
    this.sub.syncConnectionListener();
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
    this.sub.clearReconnectTimer();
    if (this.liveClockTimer !== null) {
      clearInterval(this.liveClockTimer);
      this.liveClockTimer = null;
    }
    if (this.photoUploadModal.files.length > 0) {
      revokeAllStagedPhotoUploads(this.photoUploadModal.files);
      this.photoUploadModal = emptyPhotoUploadModalState();
    }
    clearPhotoImageCache();
    this.sub.detachConnectionListener();
    void this.entity.flushAllPendingSettings();
    this.teardownSubscription();
  }

  hostUpdated(): void {
    hostUpdatedDomOp(this, this.routingRt);
  }

  mergeDomRevert(controlIds: Record<string, string | boolean>): void {
    this.pendingDomRevert = {
      controlIds: { ...(this.pendingDomRevert?.controlIds || {}), ...controlIds },
    };
  }

  isHandoffTarget(targetId: string): boolean {
    return Boolean(targetId) && this.handoffTargetIds.has(targetId);
  }

  clearHandoffTargets(): void {
    this.bleCalibrateHandoffActive = false;
    this.handoffTargetIds.clear();
    this.routingRt.handoffArming = false;
  }

  applySectionHandoff(scrollId = "", highlightIds?: readonly string[]): void {
    applySectionHandoffOp(this, this.routingRt, scrollId, highlightIds);
  }

  onMainFocusIn(ev: FocusEvent): void {
    onMainFocusInOp(this, this.routingRt, ev);
  }

  handleStudioRevMismatch(): void {
    this.studioRevMismatch = true;
    this.loading = false;
    this.deviceLoading = false;
    this.sub.clearReconnectTimer();
    this.teardownSubscription();
    this.host.requestUpdate();
  }

  setHass(hass: HomeAssistant | null): void {
    const prevConn = this.ws.hass?.connection ?? null;
    this.ws.setHass(hass);
    this.sub.syncConnectionListener();
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
      this.state?.config?.has_security_pin ?? this.state?.has_security_pin,
    );
  }

  deviceHasView(viewId: DeviceViewId): boolean {
    return storeDeviceHasView(this, viewId);
  }

  onActiveDeviceChanged(
    prevId: string,
    nextId: string,
    options?: { discardPrevPending?: boolean },
  ): void {
    onActiveDeviceChangedOp(this, prevId, nextId, options);
  }

  applyRoute(route: HassRoute | null | undefined): void {
    applyRouteOp(this, this.routingRt, route);
  }

  redirectInvalidDeviceRoute(invalidId?: string): void {
    redirectInvalidDeviceRouteOp(this, invalidId);
  }

  syncUrl(replace = false): void {
    syncUrlOp(this, this.routingRt, replace);
  }

  openDevicesLanding(): void {
    openDevicesLandingOp(this);
  }

  openDiscoveredDevices(cardId = ""): void {
    openDiscoveredDevicesOp(this, cardId);
  }

  openDevicesWithCategory(category: string): void {
    this.deviceCategoryFilter = category;
    this.openDevicesLanding();
  }

  setScope(scope: StudioScope, explicitViewId?: StudioViewId): void {
    setScopeOp(this, scope, explicitViewId);
  }

  switchView(viewId: StudioViewId): void {
    switchViewOp(this, viewId);
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
    await switchSystemDeviceOp(this, nextSubentryId, targetView);
  }

  openHaPage(path: string): void {
    navigateHaPath(path, false);
  }

  openDeviceInHa(preferLatterEntry = false): void {
    openDeviceInHaOp(this, preferLatterEntry);
  }

  toggleParentHaSidebar(): void {
    this.host.dispatchEvent(
      new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }),
    );
  }

  teardownSubscription(): void {
    this.sub.teardownSubscription();
  }
  desiredSubscriptionKey(): string {
    return this.sub.desiredSubscriptionKey();
  }
  async ensureSubscription(forceResubscribe = false): Promise<void> {
    await this.sub.ensureSubscription(forceResubscribe);
  }
  async refreshState(options?: { includeLogs?: boolean }): Promise<void> {
    await this.sub.refreshState(options);
  }
  applyBleSurveyDelta(delta: BleSurveyDeltaEvent): void {
    this.sub.applyBleSurveyDelta(delta);
  }
  ingestPayload(incoming: StudioStatePayload, logsWereRequested: boolean): void {
    this.sub.ingestPayload(incoming, logsWereRequested);
  }
  toggleDiscoveredBlePause(paused?: boolean): void {
    this.sub.toggleDiscoveredBlePause(paused);
  }
  evictAdoptedBleCandidate(targetAddress: string): void {
    this.sub.evictAdoptedBleCandidate(targetAddress);
  }
  ensureDefaultSurveyDevice(): void {
    this.sub.ensureDefaultSurveyDevice();
  }
  ensureDefaultDoorbellTester(): void {
    this.sub.ensureDefaultDoorbellTester();
  }
  ensureValidBatchTargetFilter(): void {
    this.sub.ensureValidBatchTargetFilter();
  }
}
