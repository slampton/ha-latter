/**
 * Encapsulated Reactive Store for Latter Studio (`StudioStore`).
 *
 * Key invariants:
 * - Zero `window.*` globals: each `<latter-studio>` element owns its `StudioStore` controller.
 * - Snapshot-isolated pending edits: `stageDeviceSetting` captures `targetSubentryId` at input time,
 *   so switching Devices or routes flushes pending edits strictly to Device A (`previousSubentryId`)
 *   before loading Device B, and rolls back cleanly on error even if the input retains focus.
 * - Streams `ble_survey_delta` over the WebSocket subscription without 1.5s full-state polling.
 * - Requests `include_logs: true` ONLY when System -> Tools -> System & Device Logs is open.
 */

import { formatWsError, StudioWsClient } from "../api/ws-client.js";
import { DEVICE_VIEW_SLUGS, SYSTEM_VIEW_SLUGS, VIEW_TITLES } from "../constants.js";
import type { ReactiveController, ReactiveControllerHost } from "../lib/lit.js";
import type {
  AreaPresenceRow,
  BleSurveyDeltaEvent,
  BleSurveyRow,
  DeviceConfig,
  DeviceViewId,
  EspHomeEntityItem,
  HassRoute,
  HomeAssistant,
  SharedControlItem,
  StudioScope,
  StudioStatePayload,
  StudioViewId,
  SystemConfig,
  SystemDeviceEntry,
  SystemViewId,
} from "../types.js";
import { navigateHaPath } from "../utils/format.js";
import {
  checkSystemUpdatesOp,
  clearInternalLogsOp,
  clearSecurityPinOp,
  confirmAddBleModalOp,
  confirmRemoveDeviceOp,
  confirmResetDeviceOp,
  copyLogsToClipboardOp,
  downloadDeviceDiagnosticsOp,
  exportBackupOp,
  formatVisibleLogsOp,
  openColorWheelModalOp,
  quickAdoptBleCandidateOp,
  restoreFromUploadedFileOp,
  rotateSigningKeyOp,
  saveColorWheelSelectionOp,
  saveSecurityPinOp,
  selectBleCandidateInModalOp,
  sendAnnouncementOp,
} from "./dialogs-tools-ops.js";
import {
  addRemoteGroupRowOp,
  addStringListRowOp,
  addVolumeOverrideRowOp,
  applyDeviceCustomColorOp,
  assignDeviceRemoteGroupOp,
  commitEntityChange,
  deleteCustomPaletteOp,
  deleteWallpaperOp,
  type DevicePendingBucket,
  executeEntityActionOp,
  flushDeviceBucketOp,
  flushSystemSettingsOp,
  getEnabledActivitySourcesOp,
  getEnabledDockTokensOp,
  moveDockAppTokenOp,
  overlayPendingEntityStates,
  PENDING_ENTITY_STATES,
  type PendingEntityEntry,
  previewCameraOp,
  removeRemoteGroupRowOp,
  removeStringListRowOp,
  removeVolumeOverrideRowOp,
  selectWallpaperSourceOp,
  setAllWallpaperFavoritesOp,
  setWallpaperRotationOp,
  stageDeviceSettingOp,
  stageSystemSettingOp,
  testDoorbellSpeakerOp,
  toggleActivitySourceOp,
  toggleDockAppTokenOp,
  toggleRemoteInGroupOp,
  toggleWallpaperFavOp,
  updateRemoteGroupFieldOp,
  updateStringListRowOp,
  updateVolumeOverrideRowOp,
  uploadWallpaperOp,
} from "./entity-config-ops.js";
import {
  autoCalibrateHereOp,
  bulkNumberOp,
  bulkSelectOp,
  bulkToggleOp,
  createDeviceGroupOp,
  deleteDeviceGroupOp,
  filteredControlTargetsOp,
  getActiveSurveyDeviceOp,
  resolvedGroupCtrlIdOp,
  seedGroupBaselineFromDeviceOp,
  setAreaFusionOp,
  setBleOffsetOp,
  setGroupDeviceSettingOp,
  syncDeviceGroupOp,
} from "./groups-presence-ops.js";

export { commitEntityChange, overlayPendingEntityStates, PENDING_ENTITY_STATES, type PendingEntityEntry };

interface PendingDomRevert {
  controlIds: Record<string, string | boolean>;
}

function slugToView<T extends string>(map: Record<T, string>, slug: string): T | null {
  const cleaned = String(slug || "").trim().toLowerCase();
  for (const [viewId, s] of Object.entries(map) as Array<[T, string]>) {
    if (s === cleaned) return viewId;
  }
  return null;
}

export class StudioStore implements ReactiveController {
  readonly host: ReactiveControllerHost & HTMLElement;
  readonly ws: StudioWsClient;

  // Core navigation & lifecycle state (D-001: starts on Devices landing list)
  currentScope: StudioScope = "device";
  currentViewId: StudioViewId = "select_device_prompt";
  activeSubentryId = "";
  deviceSelected = false;

  state: StudioStatePayload | null = null;
  loading = true;
  loadError = "";
  studioRevMismatch = false;

  // Toast feedback
  toastMessage = "";
  toastIsError = false;
  private toastTimer: ReturnType<typeof setTimeout> | null = null;

  // Upload state (`XMLHttpRequest` multipart <= 15 MB)
  uploadScope: StudioScope | null = null;
  uploadBusy = false;
  uploadPercent = 0;
  selectedDeviceWallpaperFile: File | null = null;
  selectedSystemWallpaperFile: File | null = null;
  selectedBackupFile: File | null = null;

  // Devices table UI state
  deviceSortField: "title" | "model" | "area" | "group" | "status" = "title";
  deviceSortAsc = true;
  deviceCategoryFilter = "all";

  // Device Tools & Security state
  entitySearchQuery = "";
  devicePinDraft = "";
  systemPinDraft = "";
  pinBusy = false;

  // System Shared Entities UI state
  doorbellTestSubentryId = "";
  activeCameraPreviewEntity = "";
  cameraPreviewUrl = "";

  // System Device Groups UI state
  newGroupName = "";
  newGroupDesc = "";
  seedGroupTargetId = "";
  seedSourceSubentryId = "";
  groupCtrlFilter = "all";
  groupCtrlCategoryFilter = "all";

  // System BLE & Area Presence UI state
  bleSurveySubentryId = "";
  bleLiveStreamActive = true;
  readonly openFusionAreas = new Set<string>();

  // System Tools UI state
  announceMode: "notify" | "broadcast" = "notify";
  announceTarget = "all";
  announceTitle = "";
  announceMessage = "";
  announcePriority: "normal" | "warning" | "critical" = "normal";
  announceIncludeCamera = false;
  backupExportScope = "system";
  backupRestoreSubentryId = "";
  backupRestoreEsp = true;
  logsOpen = false;
  logFilter = "all";

  // Modal states
  removeModal = { open: false, subentryId: "", title: "", busy: false };
  resetModal = { open: false, deviceSettings: true, latterOptions: true, busy: false };
  addBleModal = {
    open: false,
    candidateAddr: "",
    name: "",
    address: "",
    assignedPerson: "",
    busy: false,
  };
  colorWheelModal = {
    open: false,
    targetScope: "system" as StudioScope,
    hex: "",
    name: "",
    busy: false,
  };

  pendingScrollCardId = "";
  pendingDomRevert: PendingDomRevert | null = null;

  // Snapshot-isolated pending settings queues (shared with `state/*-ops.ts`)
  pendingSystemPatch: Record<string, unknown> = {};
  pendingSystemPrevious: Record<string, unknown> = {};
  systemSaveTimer: ReturnType<typeof setTimeout> | null = null;
  readonly pendingDeviceBuckets = new Map<string, DevicePendingBucket>();
  readonly pendingEntityStates = new Map<string, PendingEntityEntry>();

  // Subscription management
  private subGen = 0;
  private wsUnsub: (() => void) | null = null;
  private subscribedKey = "";
  private fallbackPollTimer: ReturnType<typeof setTimeout> | null = null;
  private routeApplying = false;

  constructor(host: ReactiveControllerHost & HTMLElement) {
    this.host = host;
    this.ws = new StudioWsClient(() => {
      this.studioRevMismatch = true;
      this.host.requestUpdate();
    });
  }

  hostConnected(): void {
    if (this.ws.hass) {
      void this.ensureSubscription(true);
    }
  }

  hostDisconnected(): void {
    if (this.toastTimer) {
      clearTimeout(this.toastTimer);
      this.toastTimer = null;
    }
    if (this.fallbackPollTimer) {
      clearTimeout(this.fallbackPollTimer);
      this.fallbackPollTimer = null;
    }
    void this.flushAllPendingSettings();
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
      const root = (this.host as unknown as { renderRoot?: ShadowRoot }).renderRoot;
      const target = root?.getElementById(cardId);
      if (target && typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }

  setHass(hass: HomeAssistant | null): void {
    const firstHass = !this.ws.hass && Boolean(hass);
    this.ws.setHass(hass);
    if (firstHass && this.host.isConnected) {
      void this.ensureSubscription(true);
    }
  }

  get hass(): HomeAssistant | null {
    return this.ws.hass;
  }

  reloadPage(): void {
    globalThis.location.reload();
  }

  showToast(message: string, isError = false): void {
    this.toastMessage = String(message || "");
    this.toastIsError = isError;
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => {
      this.toastMessage = "";
      this.host.requestUpdate();
    }, isError ? 5000 : 3000);
    this.host.requestUpdate();
  }

  shouldIncludeLogs(): boolean {
    return this.currentScope === "system" && this.currentViewId === "system_tools" && this.logsOpen;
  }

  get pageTitle(): string {
    return VIEW_TITLES[this.currentViewId] || "All Devices";
  }

  get pageSubtitle(): string {
    if (this.currentScope === "device" && this.deviceSelected && this.state?.title) {
      return this.state.title;
    }
    return "";
  }

  // ---------- Routing & Navigation ----------

  applyRoute(route: HassRoute | null | undefined): void {
    const rawPath = String(route?.path || "");
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

    this.routeApplying = true;
    try {
      if (parts[0] === "devices" && parts[1]) {
        const nextSubId = parts[1];
        if (
          this.state &&
          Array.isArray(this.state.system_devices) &&
          !this.state.system_devices.some((d) => d.subentry_id === nextSubId)
        ) {
          this.redirectInvalidDeviceRoute();
          return;
        }
        const viewId = slugToView(DEVICE_VIEW_SLUGS, parts[2] || "overview") || "dashboard";
        const prevSubId = this.activeSubentryId;
        const subChanged = prevSubId !== nextSubId;
        if (prevSubId && subChanged) {
          void this.flushDeviceBucket(prevSubId);
        }
        this.activeSubentryId = nextSubId;
        this.deviceSelected = true;
        this.currentScope = "device";
        this.currentViewId = viewId;
        this.host.requestUpdate();
        if (subChanged && this.ws.hass) {
          void this.ensureSubscription(true);
        }
      } else if (parts[0] === "system") {
        if (this.activeSubentryId) {
          void this.flushDeviceBucket(this.activeSubentryId);
        }
        const viewId = slugToView(SYSTEM_VIEW_SLUGS, parts[1] || "overview") || "system_overview";
        this.currentScope = "system";
        this.currentViewId = viewId;
        this.host.requestUpdate();
        if (this.ws.hass && this.shouldIncludeLogs()) {
          void this.refreshState({ includeLogs: true });
        }
      } else {
        if (this.activeSubentryId) {
          void this.flushDeviceBucket(this.activeSubentryId);
        }
        this.deviceSelected = false;
        this.currentScope = "device";
        this.currentViewId = "select_device_prompt";
        this.host.requestUpdate();
      }
    } finally {
      this.routeApplying = false;
    }
  }

  private redirectInvalidDeviceRoute(): void {
    const invalidId = this.activeSubentryId;
    this.activeSubentryId = "";
    this.deviceSelected = false;
    this.currentScope = "system";
    this.currentViewId = "system_overview";
    navigateHaPath("/latter/system/overview", true);
    if (invalidId) {
      this.showToast("Requested Device was not found; showing System Overview.", false);
    }
    this.host.requestUpdate();
    if (this.ws.hass) {
      void this.ensureSubscription(true);
    }
  }

  syncUrl(replace = false): void {
    if (this.routeApplying) return;
    let targetPath = "/latter";
    if (this.currentScope === "system") {
      const slug = SYSTEM_VIEW_SLUGS[this.currentViewId as SystemViewId] || "overview";
      targetPath = `/latter/system/${slug}`;
    } else if (this.deviceSelected && this.activeSubentryId && this.currentViewId !== "select_device_prompt") {
      const slug =
        DEVICE_VIEW_SLUGS[this.currentViewId as Exclude<DeviceViewId, "select_device_prompt">] ||
        "overview";
      targetPath = `/latter/devices/${encodeURIComponent(this.activeSubentryId)}/${slug}`;
    } else {
      targetPath = "/latter/devices";
    }
    if (globalThis.location?.pathname !== targetPath) {
      navigateHaPath(targetPath, replace);
    }
  }

  openDevicesLanding(): void {
    if (this.activeSubentryId) {
      void this.flushDeviceBucket(this.activeSubentryId);
    }
    this.deviceSelected = false;
    this.currentScope = "device";
    this.currentViewId = "select_device_prompt";
    this.syncUrl();
    this.host.requestUpdate();
  }

  openDevicesWithCategory(category: string): void {
    this.deviceCategoryFilter = category;
    this.openDevicesLanding();
  }

  setScope(scope: StudioScope, explicitViewId?: StudioViewId): void {
    if (scope === "device" && this.currentScope !== "device") {
      void this.flushSystemSettings();
    } else if (scope === "system" && this.activeSubentryId) {
      void this.flushDeviceBucket(this.activeSubentryId);
    }
    this.currentScope = scope;
    if (explicitViewId) {
      this.currentViewId = explicitViewId;
    } else if (scope === "system") {
      this.currentViewId = "system_overview";
    } else {
      this.currentViewId = this.deviceSelected && this.activeSubentryId ? "dashboard" : "select_device_prompt";
    }
    this.syncUrl();
    this.host.requestUpdate();
    if (this.shouldIncludeLogs()) {
      void this.refreshState({ includeLogs: true });
    }
  }

  switchView(viewId: StudioViewId): void {
    if (viewId === "select_device_prompt") {
      this.openDevicesLanding();
      return;
    }
    const isSys = Object.prototype.hasOwnProperty.call(SYSTEM_VIEW_SLUGS, viewId);
    this.currentScope = isSys ? "system" : "device";
    this.currentViewId = viewId;
    this.syncUrl();
    this.host.requestUpdate();
    if (viewId === "area_tracking") {
      this.ensureDefaultSurveyDevice();
      void this.ensureSubscription(false);
    } else if (this.shouldIncludeLogs()) {
      void this.refreshState({ includeLogs: true });
    }
  }

  openSystemSection(viewId: SystemViewId, cardId = ""): void {
    this.pendingScrollCardId = cardId;
    this.switchView(viewId);
  }

  async switchSystemDevice(nextSubentryId: string, targetView: DeviceViewId = "dashboard"): Promise<void> {
    const cleanNext = String(nextSubentryId || "").trim();
    if (!cleanNext) return;
    const prevSubId = this.activeSubentryId;
    if (prevSubId && prevSubId !== cleanNext) {
      await this.flushDeviceBucket(prevSubId);
    }
    this.activeSubentryId = cleanNext;
    this.deviceSelected = true;
    this.currentScope = "device";
    this.currentViewId = targetView === "select_device_prompt" ? "dashboard" : targetView;
    this.entitySearchQuery = "";
    this.devicePinDraft = "";
    this.syncUrl();
    this.host.requestUpdate();
    await this.ensureSubscription(true);
  }

  openHaPage(path: string): void {
    navigateHaPath(path, false);
  }

  openDeviceInHa(): void {
    const links = this.state?.links;
    const devId = links?.esphome_device_id || links?.latter_device_id || "";
    if (devId) {
      this.openHaPage(`/config/devices/device/${encodeURIComponent(devId)}`);
    } else {
      this.openHaPage("/config/integrations/integration/latter");
    }
  }

  toggleParentHaSidebar(): void {
    this.host.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
  }

  // ---------- Subscription & State Ingestion ----------

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

  private desiredSubscriptionKey(): string {
    const sub = this.activeSubentryId || "";
    const survey =
      this.currentScope === "system" && this.currentViewId === "area_tracking" && this.bleLiveStreamActive
        ? this.bleSurveySubentryId || ""
        : "";
    return `${sub}|${survey}`;
  }

  async ensureSubscription(forceRefresh = false): Promise<void> {
    if (!this.ws.hass?.connection) return;
    const nextKey = this.desiredSubscriptionKey();
    if (!forceRefresh && this.wsUnsub && this.subscribedKey === nextKey) {
      return;
    }
    this.teardownSubscription();
    const myGen = ++this.subGen;
    const targetSubId = this.activeSubentryId || null;
    const surveyId =
      this.currentScope === "system" && this.currentViewId === "area_tracking" && this.bleLiveStreamActive
        ? this.bleSurveySubentryId || null
        : null;

    if (forceRefresh || !this.state) {
      await this.refreshState({ includeLogs: this.shouldIncludeLogs() });
    }
    if (myGen !== this.subGen) return;

    try {
      const unsub = await this.ws.subscribe(
        {
          subentryId: targetSubId,
          surveySubentryId: surveyId,
          includeLogs: this.shouldIncludeLogs(),
        },
        (eventPayload) => {
          if (myGen !== this.subGen || !eventPayload) return;
          this.handleSubscriptionEvent(eventPayload);
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
    } catch {
      if (this.fallbackPollTimer) clearTimeout(this.fallbackPollTimer);
      this.fallbackPollTimer = setTimeout(() => {
        if (this.host.isConnected) {
          void this.ensureSubscription(true);
        }
      }, 10000);
    }
  }

  async refreshState(options?: { includeLogs?: boolean }): Promise<void> {
    if (!this.ws.hass) return;
    const targetSubId = this.activeSubentryId || null;
    const includeLogs = options?.includeLogs ?? this.shouldIncludeLogs();
    try {
      const payload = await this.ws.getState({
        subentryId: targetSubId,
        includeLogs,
      });
      if (payload) {
        this.loadError = "";
        this.loading = false;
        this.ingestPayload(payload, includeLogs);
      }
    } catch (err) {
      this.loading = false;
      this.loadError = formatWsError(err, "Latter Studio could not load.");
      this.host.requestUpdate();
    }
  }

  private handleSubscriptionEvent(raw: unknown): void {
    if (!raw || typeof raw !== "object") return;
    const rec = raw as Record<string, unknown>;
    const isBleDelta =
      rec.type === "ble_survey_delta" ||
      rec.event === "ble_survey_delta" ||
      (!("system_devices" in rec) &&
        ("ble_survey_rows" in rec || "ble_packets_seen" in rec || "area_presence_grid" in rec));

    if (isBleDelta) {
      this.applyBleSurveyDelta(rec as unknown as BleSurveyDeltaEvent);
      return;
    }

    const payload = raw as StudioStatePayload;
    if (
      this.activeSubentryId &&
      payload.subentry_id &&
      payload.subentry_id !== this.activeSubentryId
    ) {
      return;
    }
    this.loading = false;
    this.loadError = "";
    this.ingestPayload(payload, false);
  }

  private applyBleSurveyDelta(delta: BleSurveyDeltaEvent): void {
    if (!this.state) return;
    const targetId = String(delta.subentry_id || this.bleSurveySubentryId || this.state.subentry_id || "");
    if (Array.isArray(delta.ble_survey_rows)) {
      const nextRows: BleSurveyRow[] = delta.ble_survey_rows;
      const winRow = nextRows.find((r) => r.is_winner);
      if (Array.isArray(this.state.system_devices) && targetId) {
        this.state.system_devices = this.state.system_devices.map((dev) => {
          if (dev.subentry_id !== targetId) return dev;
          return {
            ...dev,
            ble_survey_rows: nextRows,
            ble_packets_seen:
              typeof delta.ble_packets_seen === "number" ? delta.ble_packets_seen : dev.ble_packets_seen,
            active_area_name: winRow?.area_name || dev.active_area_name,
          };
        });
      }
      if (this.state.subentry_id === targetId && this.state.live && typeof delta.ble_closest_proxy === "string") {
        this.state.live = {
          ...this.state.live,
          ble_closest_proxy: delta.ble_closest_proxy,
        };
      }
    }
    if (Array.isArray(delta.area_presence_grid) && this.state.live) {
      this.state.live = {
        ...this.state.live,
        area_presence_grid: delta.area_presence_grid as AreaPresenceRow[],
      };
    }
    this.host.requestUpdate();
  }

  ingestPayload(incoming: StudioStatePayload, logsWereRequested: boolean): void {
    const prevCatalog = this.state?.catalog;
    const prevLogs = this.state?.internal_logs;

    if (
      this.deviceSelected &&
      this.activeSubentryId &&
      Array.isArray(incoming.system_devices) &&
      !incoming.system_devices.some((d) => d.subentry_id === this.activeSubentryId)
    ) {
      this.state = {
        ...incoming,
        catalog: incoming.catalog ?? prevCatalog,
        internal_logs: logsWereRequested || incoming.internal_logs?.length ? incoming.internal_logs : prevLogs || [],
      };
      this.redirectInvalidDeviceRoute();
      return;
    }

    const merged: StudioStatePayload = {
      ...incoming,
      catalog: incoming.catalog ?? prevCatalog,
      internal_logs:
        logsWereRequested || (Array.isArray(incoming.internal_logs) && incoming.internal_logs.length > 0)
          ? incoming.internal_logs || []
          : prevLogs || [],
    };

    if (Object.keys(this.pendingSystemPatch).length > 0 && merged.system_config) {
      merged.system_config = {
        ...merged.system_config,
        ...(this.pendingSystemPatch as Partial<SystemConfig>),
      };
    }

    const devBucket = merged.subentry_id ? this.pendingDeviceBuckets.get(merged.subentry_id) : undefined;
    if (devBucket && merged.config) {
      merged.config = {
        ...merged.config,
        ...(devBucket.patch as Partial<DeviceConfig>),
      };
    }

    overlayPendingEntityStates(merged, this.pendingEntityStates);

    if (this.currentScope === "device" && this.deviceSelected && merged.subentry_id === this.activeSubentryId) {
      const caps = merged.capabilities || {};
      const isBleTag = merged.config?.kind === "ble_tag";
      if (
        (this.currentViewId === "home_display" && (isBleTag || !caps.has_display)) ||
        (this.currentViewId === "audio_voice" && (isBleTag || (!caps.has_audio && !caps.has_voice))) ||
        (this.currentViewId === "power" && (isBleTag || !caps.has_power))
      ) {
        this.currentViewId = "dashboard";
        this.syncUrl(true);
      }
    }

    this.state = merged;
    this.ensureDefaultSurveyDevice();
    this.ensureDefaultDoorbellTester();
    this.ensureDefaultSeedSelections();
    this.host.requestUpdate();
  }

  private ensureDefaultSurveyDevice(): void {
    const devs = this.state?.system_devices || [];
    const bleDevs = devs.filter((d) => d.has_ble || d.ble_tracked || d.kind === "ble_tag");
    if (this.bleSurveySubentryId && bleDevs.some((d) => d.subentry_id === this.bleSurveySubentryId)) {
      return;
    }
    const current = bleDevs.find((d) => d.subentry_id === this.activeSubentryId);
    this.bleSurveySubentryId = current?.subentry_id || bleDevs[0]?.subentry_id || "";
  }

  private ensureDefaultDoorbellTester(): void {
    const devs = (this.state?.system_devices || []).filter((d) => d.kind !== "ble_tag");
    if (this.doorbellTestSubentryId && devs.some((d) => d.subentry_id === this.doorbellTestSubentryId)) {
      return;
    }
    this.doorbellTestSubentryId = devs[0]?.subentry_id || "";
  }

  private ensureDefaultSeedSelections(): void {
    const groups = this.state?.device_groups || [];
    if (!this.seedGroupTargetId || !groups.some((g) => g.id === this.seedGroupTargetId)) {
      this.seedGroupTargetId = groups[0]?.id || "";
    }
    const devs = (this.state?.system_devices || []).filter((d) => d.kind !== "ble_tag");
    if (!this.seedSourceSubentryId || !devs.some((d) => d.subentry_id === this.seedSourceSubentryId)) {
      this.seedSourceSubentryId = this.activeSubentryId || devs[0]?.subentry_id || "";
    }
  }

  // ---------- Delegated Domain Operations ----------

  stageDeviceSetting(key: keyof DeviceConfig, value: unknown, controlDomId?: string): void {
    stageDeviceSettingOp(this, key, value, controlDomId);
  }

  async flushDeviceBucket(targetSubentryId: string): Promise<void> {
    await flushDeviceBucketOp(this, targetSubentryId);
  }

  stageSystemSetting(key: keyof SystemConfig, value: unknown, controlDomId?: string): void {
    stageSystemSettingOp(this, key, value, controlDomId);
  }

  async flushSystemSettings(): Promise<void> {
    await flushSystemSettingsOp(this);
  }

  async flushAllPendingSettings(): Promise<void> {
    const tasks: Array<Promise<void>> = [];
    if (Object.keys(this.pendingSystemPatch).length > 0) {
      tasks.push(this.flushSystemSettings());
    }
    for (const subId of Array.from(this.pendingDeviceBuckets.keys())) {
      tasks.push(this.flushDeviceBucket(subId));
    }
    await Promise.allSettled(tasks);
  }

  getSectionItems(sectionId: string): EspHomeEntityItem[] {
    const sec = (this.state?.esphome?.sections || []).find((s) => s.id === sectionId);
    return sec?.items || [];
  }

  async executeEntityAction(
    entityId: string,
    optimisticState: string | undefined,
    body: Record<string, unknown>,
    errorPrefix: string,
  ): Promise<boolean> {
    return executeEntityActionOp(this, entityId, optimisticState, body, errorPrefix);
  }

  async espAction(
    entityId: string,
    action: string,
    optimisticState?: string,
    toastMessage?: string,
  ): Promise<boolean> {
    const ok = await commitEntityChange(this, entityId, optimisticState, { action }, "Device action failed");
    if (ok && toastMessage) {
      this.showToast(toastMessage);
    }
    return ok;
  }

  async espSelect(entityId: string, option: string): Promise<void> {
    await commitEntityChange(this, entityId, option, { option }, "Could not update option");
  }

  async espNumber(entityId: string, level: number): Promise<void> {
    if (!Number.isFinite(level)) return;
    await commitEntityChange(this, entityId, String(level), { level }, "Could not update level");
  }

  async triggerHeaderFirmwareUpdate(): Promise<void> {
    const updEntity = this.state?.live?.fw_update_entity || "";
    if (!updEntity) return;
    if (await this.espAction(updEntity, "install")) {
      this.showToast("Firmware update started");
    }
  }

  getEnabledDockTokens(): string[] {
    return getEnabledDockTokensOp(this);
  }

  toggleDockAppToken(appId: string): void {
    toggleDockAppTokenOp(this, appId);
  }

  moveDockAppToken(appId: string, delta: -1 | 1): void {
    moveDockAppTokenOp(this, appId, delta);
  }

  getEnabledActivitySources(): string[] {
    return getEnabledActivitySourcesOp(this);
  }

  toggleActivitySource(sourceId: string): void {
    toggleActivitySourceOp(this, sourceId);
  }

  applyDeviceCustomColor(hex: string, switchColorProfile = true): void {
    applyDeviceCustomColorOp(this, hex, switchColorProfile);
  }

  openColorWheelModal(targetScope: StudioScope): void {
    openColorWheelModalOp(this, targetScope);
  }

  closeColorWheelModal(): void {
    this.colorWheelModal = { ...this.colorWheelModal, open: false, busy: false };
    this.host.requestUpdate();
  }

  async saveColorWheelSelection(): Promise<void> {
    await saveColorWheelSelectionOp(this);
  }

  deleteCustomPalette(hex: string): void {
    deleteCustomPaletteOp(this, hex);
  }

  async uploadWallpaper(scope: StudioScope): Promise<void> {
    await uploadWallpaperOp(this, scope);
  }

  async selectWallpaperSource(sourceId: string): Promise<void> {
    await selectWallpaperSourceOp(this, sourceId);
  }

  async setWallpaperRotation(minutes: number): Promise<void> {
    await setWallpaperRotationOp(this, minutes);
  }

  async toggleWallpaperFav(sourceId: string): Promise<void> {
    await toggleWallpaperFavOp(this, sourceId);
  }

  async setAllWallpaperFavorites(sourceIds: readonly string[]): Promise<void> {
    await setAllWallpaperFavoritesOp(this, sourceIds);
  }

  async deleteWallpaper(scope: StudioScope, sourceId: string): Promise<void> {
    await deleteWallpaperOp(this, scope, sourceId);
  }

  get hasConfiguredSecurityPin(): boolean {
    return Boolean(
      this.state?.config?.has_security_pin ??
        this.state?.live?.has_security_pin ??
        this.state?.has_security_pin,
    );
  }

  async saveSecurityPin(fromScope: StudioScope): Promise<void> {
    await saveSecurityPinOp(this, fromScope);
  }

  async clearSecurityPin(fromScope: StudioScope): Promise<void> {
    await clearSecurityPinOp(this, fromScope);
  }

  async rotateSigningKey(): Promise<void> {
    await rotateSigningKeyOp(this);
  }

  async downloadDeviceDiagnostics(): Promise<void> {
    await downloadDeviceDiagnosticsOp(this);
  }

  openRemoveDeviceModal(subentryId: string, title: string): void {
    if (!subentryId) return;
    this.removeModal = { open: true, subentryId, title: title || "Device", busy: false };
    this.host.requestUpdate();
  }

  closeRemoveDeviceModal(): void {
    this.removeModal = { ...this.removeModal, open: false, busy: false };
    this.host.requestUpdate();
  }

  async confirmRemoveDevice(): Promise<void> {
    await confirmRemoveDeviceOp(this);
  }

  openResetDeviceModal(): void {
    if (!this.activeSubentryId) return;
    const isBleTag = this.state?.config?.kind === "ble_tag";
    this.resetModal = {
      open: true,
      deviceSettings: !isBleTag,
      latterOptions: true,
      busy: false,
    };
    this.host.requestUpdate();
  }

  closeResetDeviceModal(): void {
    this.resetModal = { ...this.resetModal, open: false, busy: false };
    this.host.requestUpdate();
  }

  async confirmResetDevice(): Promise<void> {
    await confirmResetDeviceOp(this);
  }

  openAddBleModal(prefill?: { name?: string; address?: string }): void {
    this.addBleModal = {
      open: true,
      candidateAddr: prefill?.address || "",
      name: prefill?.name || "",
      address: prefill?.address || "",
      assignedPerson: "",
      busy: false,
    };
    this.host.requestUpdate();
  }

  closeAddBleModal(): void {
    this.addBleModal = { ...this.addBleModal, open: false, busy: false };
    this.host.requestUpdate();
  }

  selectBleCandidateInModal(addr: string): void {
    selectBleCandidateInModalOp(this, addr);
  }

  async quickAdoptBleCandidate(title: string, targetAddress: string, assignedPerson = ""): Promise<void> {
    await quickAdoptBleCandidateOp(this, title, targetAddress, assignedPerson);
  }

  async confirmAddBleModal(): Promise<void> {
    await confirmAddBleModalOp(this);
  }

  async checkSystemUpdates(): Promise<void> {
    await checkSystemUpdatesOp(this);
  }

  updateStringListRow(
    key: "calendar_entities" | "camera_entities" | "remotes_list",
    index: number,
    value: string,
  ): void {
    updateStringListRowOp(this, key, index, value);
  }

  addStringListRow(
    key: "calendar_entities" | "camera_entities" | "remotes_list",
    defaultEntity = "",
    maxLen = 10,
  ): void {
    addStringListRowOp(this, key, defaultEntity, maxLen);
  }

  removeStringListRow(key: "calendar_entities" | "camera_entities" | "remotes_list", index: number): void {
    removeStringListRowOp(this, key, index);
  }

  addVolumeOverrideRow(): void {
    addVolumeOverrideRowOp(this);
  }

  updateVolumeOverrideRow(index: number, field: "speaker" | "target", value: string): void {
    updateVolumeOverrideRowOp(this, index, field, value);
  }

  removeVolumeOverrideRow(index: number): void {
    removeVolumeOverrideRowOp(this, index);
  }

  addRemoteGroupRow(): void {
    addRemoteGroupRowOp(this);
  }

  updateRemoteGroupField(groupId: string, field: "name" | "area_id", value: string): void {
    updateRemoteGroupFieldOp(this, groupId, field, value);
  }

  toggleRemoteInGroup(groupId: string, remoteEntity: string): void {
    toggleRemoteInGroupOp(this, groupId, remoteEntity);
  }

  removeRemoteGroupRow(groupId: string): void {
    removeRemoteGroupRowOp(this, groupId);
  }

  async assignDeviceRemoteGroup(subentryId: string, remoteGroup: string): Promise<void> {
    await assignDeviceRemoteGroupOp(this, subentryId, remoteGroup);
  }

  async previewCamera(cameraEntity: string, bustCache = false): Promise<void> {
    await previewCameraOp(this, cameraEntity, bustCache);
  }

  closeCameraPreview(): void {
    this.activeCameraPreviewEntity = "";
    this.cameraPreviewUrl = "";
    this.host.requestUpdate();
  }

  async testDoorbellSpeaker(): Promise<void> {
    await testDoorbellSpeakerOp(this);
  }

  async createDeviceGroup(): Promise<void> {
    await createDeviceGroupOp(this);
  }

  async deleteDeviceGroup(groupId: string): Promise<void> {
    await deleteDeviceGroupOp(this, groupId);
  }

  async syncDeviceGroup(groupId: string, singleSubentryId?: string): Promise<void> {
    await syncDeviceGroupOp(this, groupId, singleSubentryId);
  }

  async seedGroupBaselineFromDevice(): Promise<void> {
    await seedGroupBaselineFromDeviceOp(this);
  }

  resolvedGroupCtrlId(): string {
    return resolvedGroupCtrlIdOp(this);
  }

  async setGroupDeviceSetting(patch: Record<string, unknown>): Promise<void> {
    await setGroupDeviceSettingOp(this, patch);
  }

  filteredControlTargets(ctrl: SharedControlItem): string[] {
    return filteredControlTargetsOp(this, ctrl);
  }

  async bulkToggle(ctrl: SharedControlItem, turnOn: boolean): Promise<void> {
    await bulkToggleOp(this, ctrl, turnOn);
  }

  async bulkSelect(ctrl: SharedControlItem, option: string): Promise<void> {
    await bulkSelectOp(this, ctrl, option);
  }

  async bulkNumber(ctrl: SharedControlItem, level: number): Promise<void> {
    await bulkNumberOp(this, ctrl, level);
  }

  selectBleSurveyDevice(subentryId: string): void {
    this.bleSurveySubentryId = subentryId;
    this.host.requestUpdate();
    void this.ensureSubscription(false);
  }

  toggleBleLiveStream(enabled: boolean): void {
    this.bleLiveStreamActive = enabled;
    this.host.requestUpdate();
    void this.ensureSubscription(false);
  }

  getActiveSurveyDevice(): SystemDeviceEntry | undefined {
    return getActiveSurveyDeviceOp(this);
  }

  async setBleOffset(areaId: string, offsetDb: number): Promise<void> {
    await setBleOffsetOp(this, areaId, offsetDb);
  }

  async autoCalibrateHere(areaId: string): Promise<void> {
    await autoCalibrateHereOp(this, areaId);
  }

  async setAreaFusion(
    areaId: string,
    update: { mode?: string; threshold_pct?: number; sensors?: string[] },
  ): Promise<void> {
    await setAreaFusionOp(this, areaId, update);
  }

  async sendAnnouncement(): Promise<void> {
    await sendAnnouncementOp(this);
  }

  async exportBackup(explicitSubentryId?: string): Promise<void> {
    await exportBackupOp(this, explicitSubentryId);
  }

  async restoreFromUploadedFile(): Promise<void> {
    await restoreFromUploadedFileOp(this);
  }

  onToggleLogsDetails(open: boolean): void {
    this.logsOpen = open;
    this.host.requestUpdate();
    if (open) {
      void this.refreshState({ includeLogs: true });
    }
  }

  formatVisibleLogs(): string {
    return formatVisibleLogsOp(this);
  }

  async copyLogsToClipboard(): Promise<void> {
    await copyLogsToClipboardOp(this);
  }

  async clearInternalLogs(): Promise<void> {
    await clearInternalLogsOp(this);
  }
}
