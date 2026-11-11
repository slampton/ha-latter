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
import {
  ACTIVITY_SOURCES_CATALOG,
  DEVICE_VIEW_SLUGS,
  DOCK_APPS_CATALOG,
  SYSTEM_VIEW_SLUGS,
  VIEW_TITLES,
} from "../constants.js";
import type { ReactiveController, ReactiveControllerHost } from "../lib/lit.js";
import type {
  AreaPresenceRow,
  BleSurveyDeltaEvent,
  BleSurveyRow,
  CustomPalette,
  DeviceConfig,
  DeviceViewId,
  EspHomeEntityItem,
  HassRoute,
  HomeAssistant,
  RemoteGroup,
  SharedControlItem,
  StudioScope,
  StudioStatePayload,
  StudioViewId,
  SystemConfig,
  SystemDeviceEntry,
  SystemViewId,
  VolumeOverride,
} from "../types.js";
import {
  copyTextToClipboard,
  defaultThemeHex,
  isValidHexColor,
  navigateHaPath,
  triggerJsonDownload,
} from "../utils/format.js";

interface DevicePendingBucket {
  targetSubentryId: string;
  patch: Record<string, unknown>;
  previousValues: Record<string, unknown>;
  timer: ReturnType<typeof setTimeout> | null;
}

export interface PendingEntityEntry {
  state: string;
  previousValue?: string;
  expires: number;
}

interface PendingDomRevert {
  controlIds: Record<string, string | boolean>;
}

const SAVE_DEBOUNCE_MS = 220;
const ENTITY_OPTIMISTIC_TTL_MS = 8000;

export const PENDING_ENTITY_STATES = new Map<string, PendingEntityEntry>();

export function overlayPendingEntityStates(
  payload: StudioStatePayload,
  pendingMap: Map<string, PendingEntityEntry> = PENDING_ENTITY_STATES,
): void {
  const now = Date.now();
  for (const [eid, entry] of pendingMap.entries()) {
    if (entry.expires <= now) {
      pendingMap.delete(eid);
    }
  }
  const sections = payload?.esphome?.sections;
  if (!sections || pendingMap.size === 0) return;
  payload.esphome = {
    ...payload.esphome,
    sections: sections.map((sec) => ({
      ...sec,
      items: (sec.items || []).map((item) => {
        const pending = pendingMap.get(item.entity_id);
        if (!pending) return item;
        const curState = String(item.state ?? "");
        const sameNumeric =
          curState !== "" &&
          pending.state !== "" &&
          Number.isFinite(Number(curState)) &&
          Number.isFinite(Number(pending.state)) &&
          Number(curState) === Number(pending.state);
        if (curState === pending.state || sameNumeric) {
          pendingMap.delete(item.entity_id);
          return item;
        }
        return { ...item, state: pending.state };
      }),
    })),
  };
}

export async function commitEntityChange(
  store: StudioStore,
  entityId: string,
  optimisticState: string | undefined,
  body: Record<string, unknown>,
  errorPrefix: string,
): Promise<void> {
  await store.executeEntityAction(entityId, optimisticState, body, errorPrefix);
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
  revertEpoch = 0;
  pendingDomRevert: PendingDomRevert | null = null;

  // Snapshot-isolated pending settings queues
  private pendingSystemPatch: Record<string, unknown> = {};
  private pendingSystemPrevious: Record<string, unknown> = {};
  private systemSaveTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly pendingDeviceBuckets = new Map<string, DevicePendingBucket>();
  private readonly pendingEntityStates = new Map<string, PendingEntityEntry>();

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
          // Flush pending edits strictly to previousSubentryId BEFORE switching to nextSubId!
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

  private syncUrlFromState(replace = false): void {
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
    this.syncUrlFromState();
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
    this.syncUrlFromState();
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
    this.syncUrlFromState();
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
      // Flush Device A strictly using snapshotted `prevSubId` before loading Device B!
      await this.flushDeviceBucket(prevSubId);
    }
    this.activeSubentryId = cleanNext;
    this.deviceSelected = true;
    this.currentScope = "device";
    this.currentViewId = targetView === "select_device_prompt" ? "dashboard" : targetView;
    this.entitySearchQuery = "";
    this.devicePinDraft = "";
    this.syncUrlFromState();
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
        this.ingestStatePayload(payload, includeLogs);
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
    this.ingestStatePayload(payload, false);
  }

  private applyBleSurveyDelta(delta: BleSurveyDeltaEvent): void {
    if (!this.state) return;
    const targetId = String(delta.subentry_id || this.bleSurveySubentryId || this.state.subentry_id || "");
    if (Array.isArray(delta.ble_survey_rows)) {
      const nextRows: BleSurveyRow[] = delta.ble_survey_rows;
      if (Array.isArray(this.state.system_devices) && targetId) {
        this.state.system_devices = this.state.system_devices.map((dev) => {
          if (dev.subentry_id !== targetId) return dev;
          return {
            ...dev,
            ble_survey_rows: nextRows,
            ble_packets_seen:
              typeof delta.ble_packets_seen === "number" ? delta.ble_packets_seen : dev.ble_packets_seen,
          };
        });
      }
      if (this.state.subentry_id === targetId && this.state.live) {
        this.state.live = {
          ...this.state.live,
          ble_survey_rows: nextRows,
          ble_packets_seen:
            typeof delta.ble_packets_seen === "number"
              ? delta.ble_packets_seen
              : this.state.live.ble_packets_seen,
          ble_closest_proxy:
            typeof delta.ble_closest_proxy === "string"
              ? delta.ble_closest_proxy
              : this.state.live.ble_closest_proxy,
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

  private ingestStatePayload(incoming: StudioStatePayload, logsWereRequested: boolean): void {
    const prevCatalog = this.state?.catalog;
    const prevLogs = this.state?.internal_logs;

    // Validate deep-linked `/latter/devices/<unknown_id>` against known `system_devices`
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

    // Preserve optimistic System edits not yet flushed
    if (Object.keys(this.pendingSystemPatch).length > 0 && merged.system_config) {
      merged.system_config = {
        ...merged.system_config,
        ...(this.pendingSystemPatch as Partial<SystemConfig>),
      };
    }

    // Preserve optimistic Device edits for the matching Device
    const devBucket = merged.subentry_id ? this.pendingDeviceBuckets.get(merged.subentry_id) : undefined;
    if (devBucket && merged.config) {
      merged.config = {
        ...merged.config,
        ...(devBucket.patch as Partial<DeviceConfig>),
      };
    }

    // Overlay optimistic ESPHome entity states within TTL
    overlayPendingEntityStates(merged, this.pendingEntityStates);

    // Redirect Device-only hidden capability tab back to dashboard if device lacks that capability
    if (this.currentScope === "device" && this.deviceSelected && merged.subentry_id === this.activeSubentryId) {
      const caps = merged.capabilities || {};
      const isBleTag = merged.config?.kind === "ble_tag";
      if (
        (this.currentViewId === "home_display" && (isBleTag || !caps.has_display)) ||
        (this.currentViewId === "audio_voice" && (isBleTag || (!caps.has_audio && !caps.has_voice))) ||
        (this.currentViewId === "power" && (isBleTag || !caps.has_power))
      ) {
        this.currentViewId = "dashboard";
        this.syncUrlFromState(true);
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

  // ---------- Snapshot-Isolated Settings Staging & Flushing (Fixes P1 Cross-Device Save Race) ----------

  stageDeviceSetting(key: keyof DeviceConfig, value: unknown, controlDomId?: string): void {
    const targetSubentryId = this.activeSubentryId;
    if (!targetSubentryId) return;

    let bucket = this.pendingDeviceBuckets.get(targetSubentryId);
    if (!bucket) {
      bucket = {
        targetSubentryId,
        patch: {},
        previousValues: {},
        timer: null,
      };
      this.pendingDeviceBuckets.set(targetSubentryId, bucket);
    }

    if (!(key in bucket.previousValues)) {
      const prev =
        this.state && this.state.subentry_id === targetSubentryId
          ? (this.state.config as Record<string, unknown>)?.[key]
          : undefined;
      bucket.previousValues[key] = prev;
    }
    if (controlDomId) {
      bucket.previousValues[`__dom:${controlDomId}`] = bucket.previousValues[key];
    }

    bucket.patch[key] = value;
    if (this.state && this.state.subentry_id === targetSubentryId) {
      this.state = {
        ...this.state,
        config: {
          ...this.state.config,
          [key]: value,
        },
      };
    }

    if (bucket.timer) clearTimeout(bucket.timer);
    bucket.timer = setTimeout(() => {
      void this.flushDeviceBucket(targetSubentryId);
    }, SAVE_DEBOUNCE_MS);
    this.host.requestUpdate();
  }

  async flushDeviceBucket(targetSubentryId: string): Promise<void> {
    const bucket = this.pendingDeviceBuckets.get(targetSubentryId);
    if (!bucket) return;
    if (bucket.timer) {
      clearTimeout(bucket.timer);
      bucket.timer = null;
    }
    const patch = { ...bucket.patch };
    const previousValues = { ...bucket.previousValues };
    this.pendingDeviceBuckets.delete(targetSubentryId);

    if (Object.keys(patch).length === 0) return;

    try {
      const res = await this.ws.runDeviceCommand(targetSubentryId, "save_device_config", {
        config: patch,
      });
      if (res) {
        if (this.activeSubentryId === targetSubentryId) {
          this.ingestStatePayload(res, false);
        } else if (this.state && Array.isArray(res.system_devices)) {
          // User already switched to Device B: refresh summary list only, never overwrite Device B!
          this.state = {
            ...this.state,
            system_devices: res.system_devices,
            issues: res.issues ?? this.state.issues,
          };
          this.host.requestUpdate();
        }
      }
      this.showToast("Saved");
    } catch (err) {
      // Revert optimistic values cleanly even if an input still retains focus!
      const controlRevert: Record<string, string | boolean> = {};
      for (const [k, v] of Object.entries(previousValues)) {
        if (k.startsWith("__dom:")) {
          const domId = k.slice(6);
          if (typeof v === "boolean") controlRevert[domId] = v;
          else if (v !== undefined && v !== null) controlRevert[domId] = String(v);
          else controlRevert[domId] = "";
        }
      }
      if (this.state && this.state.subentry_id === targetSubentryId) {
        const restoredConfig: Record<string, unknown> = { ...(this.state.config as Record<string, unknown>) };
        for (const [k, v] of Object.entries(previousValues)) {
          if (!k.startsWith("__dom:")) {
            restoredConfig[k] = v;
          }
        }
        this.state = {
          ...this.state,
          config: restoredConfig as DeviceConfig,
        };
      }
      this.revertEpoch += 1;
      if (Object.keys(controlRevert).length > 0) {
        this.pendingDomRevert = { controlIds: controlRevert };
      }
      this.showToast(formatWsError(err, "Could not save Device settings"), true);
      this.host.requestUpdate();
    }
  }

  stageSystemSetting(key: keyof SystemConfig, value: unknown, controlDomId?: string): void {
    if (!(key in this.pendingSystemPrevious)) {
      const prev = (this.state?.system_config as unknown as Record<string, unknown>)?.[key];
      this.pendingSystemPrevious[key] = prev !== undefined ? structuredClone(prev) : undefined;
    }
    if (controlDomId && !(`__dom:${controlDomId}` in this.pendingSystemPrevious)) {
      const prevScalar = this.pendingSystemPrevious[key];
      if (typeof prevScalar === "string" || typeof prevScalar === "number" || typeof prevScalar === "boolean") {
        this.pendingSystemPrevious[`__dom:${controlDomId}`] = prevScalar;
      }
    }

    this.pendingSystemPatch[key] = value;
    if (this.state?.system_config) {
      this.state = {
        ...this.state,
        system_config: {
          ...this.state.system_config,
          [key]: value,
        },
      };
    }

    if (this.systemSaveTimer) clearTimeout(this.systemSaveTimer);
    this.systemSaveTimer = setTimeout(() => {
      void this.flushSystemSettings();
    }, SAVE_DEBOUNCE_MS);
    this.host.requestUpdate();
  }

  async flushSystemSettings(): Promise<void> {
    if (this.systemSaveTimer) {
      clearTimeout(this.systemSaveTimer);
      this.systemSaveTimer = null;
    }
    const patch = { ...this.pendingSystemPatch };
    const previousValues = { ...this.pendingSystemPrevious };
    this.pendingSystemPatch = {};
    this.pendingSystemPrevious = {};

    if (Object.keys(patch).length === 0) return;

    try {
      const res = await this.ws.runSystemCommand(
        "save_system_config",
        { config: patch },
        this.activeSubentryId || null,
      );
      if (res) {
        this.ingestStatePayload(res, false);
      }
      this.showToast("Saved System settings");
    } catch (err) {
      const controlRevert: Record<string, string | boolean> = {};
      if (this.state?.system_config) {
        const restored: Record<string, unknown> = {
          ...(this.state.system_config as unknown as Record<string, unknown>),
        };
        for (const [k, v] of Object.entries(previousValues)) {
          if (k.startsWith("__dom:")) {
            const domId = k.slice(6);
            controlRevert[domId] = typeof v === "boolean" ? v : String(v ?? "");
          } else if (v !== undefined) {
            restored[k] = v;
          }
        }
        this.state = {
          ...this.state,
          system_config: restored as unknown as SystemConfig,
        };
      }
      this.revertEpoch += 1;
      if (Object.keys(controlRevert).length > 0) {
        this.pendingDomRevert = { controlIds: controlRevert };
      }
      this.showToast(formatWsError(err, "Could not save System settings"), true);
      this.host.requestUpdate();
    }
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

  // ---------- ESPHome Entity Actions (Optimistic + Scoped to Snapshot Device) ----------

  getSectionItems(sectionId: string): EspHomeEntityItem[] {
    const sec = (this.state?.esphome?.sections || []).find((s) => s.id === sectionId);
    return sec?.items || [];
  }

  private currentEntityState(entityId: string): string {
    for (const sec of this.state?.esphome?.sections || []) {
      for (const it of sec.items || []) {
        if (it.entity_id === entityId) return it.state;
      }
    }
    return "";
  }

  private applyOptimisticEntity(entityId: string, nextState: string): string {
    const prev = this.currentEntityState(entityId);
    this.pendingEntityStates.set(entityId, {
      state: nextState,
      previousValue: prev,
      expires: Date.now() + ENTITY_OPTIMISTIC_TTL_MS,
    });
    if (this.state?.esphome?.sections) {
      const nextPayload: StudioStatePayload = { ...this.state };
      overlayPendingEntityStates(nextPayload, this.pendingEntityStates);
      this.state = nextPayload;
      this.host.requestUpdate();
    }
    return prev;
  }

  private rollbackOptimisticEntity(entityId: string, prev: string): void {
    this.pendingEntityStates.delete(entityId);
    if (this.state?.esphome?.sections) {
      this.state = {
        ...this.state,
        esphome: {
          ...this.state.esphome,
          sections: this.state.esphome.sections.map((sec) => ({
            ...sec,
            items: (sec.items || []).map((it) =>
              it.entity_id === entityId ? { ...it, state: prev } : it,
            ),
          })),
        },
      };
    }
    this.revertEpoch += 1;
    this.host.requestUpdate();
  }

  async executeEntityAction(
    entityId: string,
    optimisticState: string | undefined,
    body: Record<string, unknown>,
    errorPrefix: string,
  ): Promise<void> {
    const targetSubentryId = this.activeSubentryId;
    if (!targetSubentryId || !entityId) return;
    const prev =
      optimisticState !== undefined ? this.applyOptimisticEntity(entityId, optimisticState) : "";
    try {
      const res = await this.ws.runDeviceCommand(targetSubentryId, "esphome_entity_action", {
        entity_id: entityId,
        ...body,
      });
      if (res && this.activeSubentryId === targetSubentryId) {
        this.ingestStatePayload(res, false);
      }
    } catch (err) {
      if (optimisticState !== undefined) this.rollbackOptimisticEntity(entityId, prev);
      this.showToast(formatWsError(err, errorPrefix), true);
    }
  }

  async espAction(entityId: string, action: string, optimisticState?: string): Promise<void> {
    await commitEntityChange(this, entityId, optimisticState, { action }, "Device action failed");
  }

  async espSelect(entityId: string, option: string): Promise<void> {
    await commitEntityChange(this, entityId, option, { option }, "Could not update option");
  }

  async espNumber(entityId: string, level: number): Promise<void> {
    if (!Number.isFinite(level)) return;
    await commitEntityChange(
      this,
      entityId,
      String(level),
      { level },
      "Could not update level",
    );
  }

  async triggerHeaderFirmwareUpdate(): Promise<void> {
    const updEntity = this.state?.live?.fw_update_entity || "";
    if (!updEntity) return;
    await this.espAction(updEntity, "install");
    this.showToast("Firmware update started");
  }

  // ---------- Dock Apps, Activity Sources, Custom Colors & Wallpapers ----------

  getEnabledDockTokens(): string[] {
    const raw = String(this.state?.config?.dock_apps ?? "");
    if (!raw.trim()) {
      return DOCK_APPS_CATALOG.map((a) => a.token);
    }
    return raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  toggleDockAppToken(appId: string): void {
    const current = this.getEnabledDockTokens();
    const idx = current.indexOf(appId);
    if (idx >= 0) {
      if (current.length <= 1) {
        this.showToast("Keep at least one Dock app enabled", true);
        return;
      }
      current.splice(idx, 1);
    } else {
      current.push(appId);
    }
    this.stageDeviceSetting("dock_apps", current.join(","));
  }

  moveDockAppToken(appId: string, delta: -1 | 1): void {
    const current = this.getEnabledDockTokens();
    const idx = current.indexOf(appId);
    const nextIdx = idx + delta;
    if (idx < 0 || nextIdx < 0 || nextIdx >= current.length) return;
    const [moved] = current.splice(idx, 1);
    current.splice(nextIdx, 0, moved);
    this.stageDeviceSetting("dock_apps", current.join(","));
  }

  getEnabledActivitySources(): string[] {
    const rawCfg = this.state?.config?.activity_sources;
    if (rawCfg === undefined || rawCfg === null) {
      return ACTIVITY_SOURCES_CATALOG.map((s) => s.id);
    }
    return String(rawCfg)
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  toggleActivitySource(sourceId: string): void {
    const current = this.getEnabledActivitySources();
    const idx = current.indexOf(sourceId);
    if (idx >= 0) {
      current.splice(idx, 1);
    } else {
      current.push(sourceId);
    }
    this.stageDeviceSetting("activity_sources", current.join(","));
  }

  applyDeviceCustomColor(hex: string, switchColorProfile = true): void {
    if (!isValidHexColor(hex)) return;
    this.stageDeviceSetting("device_custom_color", hex.toUpperCase());
    if (switchColorProfile) {
      for (const sec of this.state?.esphome?.sections || []) {
        for (const it of sec.items || []) {
          if (
            it.domain === "select" &&
            (it.name || "").toLowerCase().includes("color profile") &&
            (it.options || []).includes("Custom") &&
            it.state !== "Custom"
          ) {
            void this.espSelect(it.entity_id, "Custom");
          }
        }
      }
    }
  }

  openColorWheelModal(targetScope: StudioScope): void {
    const initial =
      targetScope === "device" && isValidHexColor(this.state?.config?.device_custom_color)
        ? String(this.state?.config?.device_custom_color).toUpperCase()
        : defaultThemeHex(this.host);
    this.colorWheelModal = {
      open: true,
      targetScope,
      hex: initial,
      name: "",
      busy: false,
    };
    this.host.requestUpdate();
  }

  closeColorWheelModal(): void {
    this.colorWheelModal = { ...this.colorWheelModal, open: false, busy: false };
    this.host.requestUpdate();
  }

  async saveColorWheelSelection(): Promise<void> {
    const hex = this.colorWheelModal.hex.trim().toUpperCase();
    if (!isValidHexColor(hex)) {
      this.showToast("Enter a valid 6-digit hex color", true);
      return;
    }
    const name = this.colorWheelModal.name.trim() || hex;
    const existing: CustomPalette[] = [...(this.state?.system_config?.custom_palettes || [])];
    if (!existing.some((p) => p.hex.toUpperCase() === hex)) {
      existing.push({ name, hex });
      this.stageSystemSetting("custom_palettes", existing);
      await this.flushSystemSettings();
    }
    if (this.colorWheelModal.targetScope === "device" && this.activeSubentryId) {
      this.stageDeviceSetting("device_custom_color", hex);
      await this.flushDeviceBucket(this.activeSubentryId);
    }
    this.closeColorWheelModal();
  }

  deleteCustomPalette(hex: string): void {
    const target = hex.toUpperCase();
    const next = (this.state?.system_config?.custom_palettes || []).filter(
      (p) => p.hex.toUpperCase() !== target,
    );
    this.stageSystemSetting("custom_palettes", next);
  }

  async uploadWallpaper(scope: StudioScope): Promise<void> {
    const file = scope === "device" ? this.selectedDeviceWallpaperFile : this.selectedSystemWallpaperFile;
    if (!file) {
      this.showToast("Choose an image file first", true);
      return;
    }
    const targetSubentryId = scope === "device" ? this.activeSubentryId : undefined;
    if (scope === "device" && !targetSubentryId) {
      this.showToast("Choose a Device first", true);
      return;
    }

    this.uploadScope = scope;
    this.uploadBusy = true;
    this.uploadPercent = 0;
    this.host.requestUpdate();

    try {
      const result = await this.ws.uploadWallpaperMultipart({
        scope,
        subentryId: targetSubentryId,
        file,
        onProgress: (pct) => {
          this.uploadPercent = pct;
          this.host.requestUpdate();
        },
      });
      if (scope === "device") {
        this.selectedDeviceWallpaperFile = null;
      } else {
        this.selectedSystemWallpaperFile = null;
      }
      if (this.state) {
        if (result.wallpapers && scope === "device" && this.activeSubentryId === targetSubentryId) {
          this.state = { ...this.state, wallpapers: result.wallpapers };
        }
        if (result.system_wallpapers) {
          this.state = { ...this.state, system_wallpapers: result.system_wallpapers };
        }
      }
      await this.refreshState();
      this.showToast("Uploaded wallpaper");
    } catch (err) {
      this.showToast(formatWsError(err, "Wallpaper upload failed"), true);
    } finally {
      this.uploadBusy = false;
      this.uploadScope = null;
      this.uploadPercent = 0;
      this.host.requestUpdate();
    }
  }

  async selectWallpaperSource(sourceId: string): Promise<void> {
    const targetSubentryId = this.activeSubentryId;
    if (!targetSubentryId) return;
    try {
      const res = await this.ws.runDeviceCommand(targetSubentryId, "select_wallpaper", {
        source_id: sourceId,
      });
      if (res && this.activeSubentryId === targetSubentryId) {
        this.ingestStatePayload(res, false);
      }
      this.showToast(sourceId ? "Wallpaper applied" : "Wallpaper turned off");
    } catch (err) {
      this.showToast(formatWsError(err, "Could not select wallpaper"), true);
    }
  }

  async toggleWallpaperFav(sourceId: string): Promise<void> {
    const targetSubentryId = this.activeSubentryId;
    if (!targetSubentryId) return;
    try {
      const res = await this.ws.runDeviceCommand(targetSubentryId, "toggle_wallpaper_favorite", {
        source_id: sourceId,
      });
      if (res && this.activeSubentryId === targetSubentryId) {
        this.ingestStatePayload(res, false);
      }
    } catch (err) {
      this.showToast(formatWsError(err, "Could not update favorite"), true);
    }
  }

  async deleteWallpaper(scope: StudioScope, sourceId: string): Promise<void> {
    try {
      if (scope === "device") {
        const targetSubentryId = this.activeSubentryId;
        if (!targetSubentryId) return;
        const res = await this.ws.runDeviceCommand(targetSubentryId, "delete_wallpaper", {
          source_id: sourceId,
        });
        if (res && this.activeSubentryId === targetSubentryId) {
          this.ingestStatePayload(res, false);
        }
      } else {
        const res = await this.ws.runSystemCommand(
          "delete_system_wallpaper",
          { source_id: sourceId },
          this.activeSubentryId || null,
        );
        if (res) this.ingestStatePayload(res, false);
      }
      this.showToast("Deleted wallpaper");
    } catch (err) {
      this.showToast(formatWsError(err, "Could not delete wallpaper"), true);
    }
  }

  // ---------- Security PIN, Signing Key, Diagnostics & Device Lifecycle ----------

  get hasConfiguredSecurityPin(): boolean {
    return Boolean(
      this.state?.config?.has_security_pin ??
        this.state?.live?.has_security_pin ??
        this.state?.has_security_pin,
    );
  }

  async saveSecurityPin(fromScope: StudioScope): Promise<void> {
    const rawPin = (fromScope === "device" ? this.devicePinDraft : this.systemPinDraft).trim();
    if (!/^\d{4,12}$/.test(rawPin)) {
      this.showToast("Security PIN must be 4 to 12 digits", true);
      return;
    }
    const targetSubentryId = fromScope === "device" ? this.activeSubentryId : "";
    this.pinBusy = true;
    this.host.requestUpdate();
    try {
      const payload: Record<string, unknown> = { pin: rawPin };
      if (targetSubentryId) payload.subentry_id = targetSubentryId;
      const res = await this.ws.runSystemCommand(
        "set_security_pin",
        payload,
        this.activeSubentryId || null,
      );
      this.devicePinDraft = "";
      this.systemPinDraft = "";
      if (res) this.ingestStatePayload(res, false);
      this.showToast("Saved Security PIN");
    } catch (err) {
      this.showToast(formatWsError(err, "Could not save Security PIN"), true);
    } finally {
      this.pinBusy = false;
      this.host.requestUpdate();
    }
  }

  async clearSecurityPin(fromScope: StudioScope): Promise<void> {
    const targetSubentryId = fromScope === "device" ? this.activeSubentryId : "";
    this.pinBusy = true;
    this.host.requestUpdate();
    try {
      const payload: Record<string, unknown> = { clear: true };
      if (targetSubentryId) payload.subentry_id = targetSubentryId;
      const res = await this.ws.runSystemCommand(
        "set_security_pin",
        payload,
        this.activeSubentryId || null,
      );
      this.devicePinDraft = "";
      this.systemPinDraft = "";
      if (res) this.ingestStatePayload(res, false);
      this.showToast("Cleared Security PIN");
    } catch (err) {
      this.showToast(formatWsError(err, "Could not clear Security PIN"), true);
    } finally {
      this.pinBusy = false;
      this.host.requestUpdate();
    }
  }

  async rotateSigningKey(): Promise<void> {
    try {
      const res = await this.ws.runSystemCommand(
        "rotate_signing_key",
        {},
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
      this.showToast("Rotated HTTP resource signing key");
    } catch (err) {
      this.showToast(formatWsError(err, "Could not rotate signing key"), true);
    }
  }

  async downloadDeviceDiagnostics(): Promise<void> {
    const entryId = this.state?.links?.entry_id || "";
    const latterDeviceId = this.state?.links?.latter_device_id || "";
    if (!entryId) {
      this.showToast("Diagnostics entry ID is not available", true);
      return;
    }
    const rawPath = latterDeviceId
      ? `/api/diagnostics/config_entry/${encodeURIComponent(entryId)}/device/${encodeURIComponent(latterDeviceId)}`
      : `/api/diagnostics/config_entry/${encodeURIComponent(entryId)}`;
    try {
      const signedPath = await this.ws.signHaPath(rawPath, 300);
      const a = document.createElement("a");
      a.href = signedPath;
      a.download = "";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err) {
      this.showToast(formatWsError(err, "Could not download diagnostics"), true);
    }
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
    const subId = this.removeModal.subentryId;
    if (!subId) return;
    this.removeModal = { ...this.removeModal, busy: true };
    this.host.requestUpdate();
    try {
      const res = await this.ws.runSystemCommand(
        "remove_device",
        { subentry_id: subId },
        this.activeSubentryId || null,
      );
      this.closeRemoveDeviceModal();
      if (this.activeSubentryId === subId) {
        this.activeSubentryId = "";
        this.deviceSelected = false;
        this.currentScope = "device";
        this.currentViewId = "select_device_prompt";
        this.syncUrlFromState(true);
      }
      if (res) this.ingestStatePayload(res, false);
      this.showToast("Removed Device from Latter");
    } catch (err) {
      this.removeModal = { ...this.removeModal, busy: false };
      this.showToast(formatWsError(err, "Could not remove Device"), true);
      this.host.requestUpdate();
    }
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
    const targetSubentryId = this.activeSubentryId;
    if (!targetSubentryId) return;
    if (!this.resetModal.deviceSettings && !this.resetModal.latterOptions) return;
    this.resetModal = { ...this.resetModal, busy: true };
    this.host.requestUpdate();
    try {
      const res = await this.ws.resetDevice({
        subentryId: targetSubentryId,
        deviceSettings: this.resetModal.deviceSettings,
        latterOptions: this.resetModal.latterOptions,
      });
      this.closeResetDeviceModal();
      if (res && this.activeSubentryId === targetSubentryId) {
        this.ingestStatePayload(res, false);
      }
      this.showToast("Reset Device to defaults");
    } catch (err) {
      this.resetModal = { ...this.resetModal, busy: false };
      this.showToast(formatWsError(err, "Could not reset Device"), true);
      this.host.requestUpdate();
    }
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
    const cand = (this.state?.discovered_ble_devices || []).find(
      (c) => (c.target_address || c.address) === addr,
    );
    const candAddr = cand ? cand.target_address || cand.address || addr : addr;
    const candTitle = cand ? cand.title || cand.name || "" : "";
    this.addBleModal = {
      ...this.addBleModal,
      candidateAddr: addr,
      address: cand ? candAddr : this.addBleModal.address,
      name: candTitle || this.addBleModal.name,
    };
    this.host.requestUpdate();
  }

  async quickAdoptBleCandidate(
    title: string,
    targetAddress: string,
    assignedPerson = "",
  ): Promise<void> {
    if (!title || !targetAddress) return;
    try {
      const res = await this.ws.runSystemCommand(
        "add_ble_device",
        {
          name: title,
          target_address: targetAddress,
          assigned_person: assignedPerson,
        },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
      this.showToast(`Added BLE tag "${title}"`);
    } catch (err) {
      this.showToast(formatWsError(err, "Could not add BLE tag"), true);
    }
  }

  async confirmAddBleModal(): Promise<void> {
    const name = this.addBleModal.name.trim();
    const targetAddress = this.addBleModal.address.trim();
    if (!name || !targetAddress) {
      this.showToast("Enter both a name and a Bluetooth address or entity", true);
      return;
    }
    this.addBleModal = { ...this.addBleModal, busy: true };
    this.host.requestUpdate();
    try {
      const res = await this.ws.runSystemCommand(
        "add_ble_device",
        {
          name,
          target_address: targetAddress,
          assigned_person: this.addBleModal.assignedPerson,
        },
        this.activeSubentryId || null,
      );
      this.closeAddBleModal();
      if (res) this.ingestStatePayload(res, false);
      this.showToast(`Added BLE tag "${name}"`);
    } catch (err) {
      this.addBleModal = { ...this.addBleModal, busy: false };
      this.showToast(formatWsError(err, "Could not add BLE tag"), true);
      this.host.requestUpdate();
    }
  }

  // ---------- System Shared Entities, Remotes, Groups, BLE & Tools Actions ----------

  async checkSystemUpdates(): Promise<void> {
    this.showToast("Checking firmware updates…");
    try {
      const res = await this.ws.runSystemCommand(
        "check_system_updates",
        {},
        this.activeSubentryId || null,
      );
      if (res) {
        this.ingestStatePayload(res, false);
        const info = res.update_check;
        if (info) {
          this.showToast(
            info.available > 0
              ? `${info.available} firmware update(s) available across ${info.checked} checked Device(s)`
              : `Checked ${info.checked} Device(s) — all firmware is up to date`,
          );
          return;
        }
      }
      this.showToast("Firmware update check finished");
    } catch (err) {
      this.showToast(formatWsError(err, "Firmware update check failed"), true);
    }
  }

  updateStringListRow(
    key: "calendar_entities" | "camera_entities" | "remotes_list",
    index: number,
    value: string,
  ): void {
    const list = [...(this.state?.system_config?.[key] || [])];
    list[index] = value;
    this.stageSystemSetting(key, list);
  }

  addStringListRow(
    key: "calendar_entities" | "camera_entities" | "remotes_list",
    defaultEntity = "",
    maxLen = 10,
  ): void {
    const list = [...(this.state?.system_config?.[key] || [])];
    if (list.length >= maxLen) {
      this.showToast(`Maximum of ${maxLen} entries reached`, true);
      return;
    }
    list.push(defaultEntity);
    this.stageSystemSetting(key, list);
  }

  removeStringListRow(key: "calendar_entities" | "camera_entities" | "remotes_list", index: number): void {
    const list = [...(this.state?.system_config?.[key] || [])];
    list.splice(index, 1);
    this.stageSystemSetting(key, list);
  }

  addVolumeOverrideRow(): void {
    const list: VolumeOverride[] = [...(this.state?.system_config?.volume_overrides || [])];
    if (list.length >= 10) {
      this.showToast("Maximum of 10 volume overrides reached", true);
      return;
    }
    const speakers = this.state?.catalog?.ma_speakers || this.state?.catalog?.speakers || [];
    const targets = this.state?.catalog?.volume_targets || this.state?.catalog?.remotes || [];
    list.push({
      speaker: speakers[0]?.id || "",
      target: targets[0]?.id || speakers[0]?.id || "",
    });
    this.stageSystemSetting("volume_overrides", list);
  }

  updateVolumeOverrideRow(index: number, field: "speaker" | "target", value: string): void {
    const list: VolumeOverride[] = (this.state?.system_config?.volume_overrides || []).map((v) => ({
      ...v,
    }));
    if (!list[index]) return;
    list[index][field] = value;
    this.stageSystemSetting("volume_overrides", list);
  }

  removeVolumeOverrideRow(index: number): void {
    const list: VolumeOverride[] = [...(this.state?.system_config?.volume_overrides || [])];
    list.splice(index, 1);
    this.stageSystemSetting("volume_overrides", list);
  }

  addRemoteGroupRow(): void {
    const groups: RemoteGroup[] = (this.state?.system_config?.remote_groups || []).map((g) => ({
      ...g,
      remotes: [...(g.remotes || [])],
    }));
    const id = `group_${Date.now().toString(36)}`;
    groups.push({ id, name: "New Remote Group", area_id: "", remotes: [] });
    this.stageSystemSetting("remote_groups", groups);
  }

  updateRemoteGroupField(groupId: string, field: "name" | "area_id", value: string): void {
    const groups: RemoteGroup[] = (this.state?.system_config?.remote_groups || []).map((g) =>
      g.id === groupId ? { ...g, [field]: value } : { ...g, remotes: [...(g.remotes || [])] },
    );
    this.stageSystemSetting("remote_groups", groups);
  }

  toggleRemoteInGroup(groupId: string, remoteEntity: string): void {
    const groups: RemoteGroup[] = (this.state?.system_config?.remote_groups || []).map((g) => {
      if (g.id !== groupId) return { ...g, remotes: [...(g.remotes || [])] };
      const remotes = [...(g.remotes || [])];
      const idx = remotes.indexOf(remoteEntity);
      if (idx >= 0) remotes.splice(idx, 1);
      else remotes.push(remoteEntity);
      return { ...g, remotes };
    });
    this.stageSystemSetting("remote_groups", groups);
  }

  removeRemoteGroupRow(groupId: string): void {
    const groups = (this.state?.system_config?.remote_groups || []).filter((g) => g.id !== groupId);
    this.stageSystemSetting("remote_groups", groups);
  }

  async assignDeviceRemoteGroup(subentryId: string, remoteGroup: string): Promise<void> {
    try {
      await this.flushSystemSettings();
      const res = await this.ws.runSystemCommand(
        "set_device_remote_group",
        { subentry_id: subentryId, device_remote_group: remoteGroup },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
      this.showToast("Updated remote group assignment");
    } catch (err) {
      this.showToast(formatWsError(err, "Could not assign remote group"), true);
    }
  }

  async previewCamera(cameraEntity: string, bustCache = false): Promise<void> {
    if (!cameraEntity) {
      this.closeCameraPreview();
      return;
    }
    const dbObj = (this.state?.doorbells || []).find((b) => b.camera_entity === cameraEntity);
    const camObj = (this.state?.catalog?.cameras || []).find((c) => c.id === cameraEntity);
    const existingSigned = dbObj?.preview_url || camObj?.preview_url || "";
    if (existingSigned) {
      const sep = existingSigned.includes("?") ? "&" : "?";
      this.activeCameraPreviewEntity = cameraEntity;
      this.cameraPreviewUrl = bustCache ? `${existingSigned}${sep}_ts=${Date.now()}` : existingSigned;
      this.host.requestUpdate();
      return;
    }
    try {
      const signed = await this.ws.signHaPath(
        `/api/camera_proxy/${encodeURIComponent(cameraEntity)}`,
        300,
      );
      const sep = signed.includes("?") ? "&" : "?";
      this.activeCameraPreviewEntity = cameraEntity;
      this.cameraPreviewUrl = `${signed}${sep}_ts=${Date.now()}`;
      this.host.requestUpdate();
    } catch (err) {
      this.showToast(formatWsError(err, "Add a Latter Device to preview cameras"), true);
    }
  }

  closeCameraPreview(): void {
    this.activeCameraPreviewEntity = "";
    this.cameraPreviewUrl = "";
    this.host.requestUpdate();
  }

  async testDoorbellSpeaker(): Promise<void> {
    const cams = this.state?.system_config?.camera_entities || [];
    if (!cams[0]) {
      this.showToast("Add a camera in Shared Entities first", true);
      return;
    }
    if (!this.doorbellTestSubentryId) {
      this.showToast("Choose a Device to test from", true);
      return;
    }
    await this.flushSystemSettings();
    try {
      const res = await this.ws.runSystemCommand(
        "test_doorbell_speaker",
        {
          subentry_id: this.doorbellTestSubentryId,
          camera_entity: cams[0],
          message: "Testing Latter doorbell audio.",
        },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
      this.showToast("Played test message on door speaker");
    } catch (err) {
      this.showToast(formatWsError(err, "Door speaker test failed"), true);
    }
  }

  // ---------- Device Groups & Bulk Controls ----------

  async createDeviceGroup(): Promise<void> {
    const name = this.newGroupName.trim();
    const description = this.newGroupDesc.trim();
    if (!name) {
      this.showToast("Enter a Device Group name", true);
      return;
    }
    try {
      const res = await this.ws.runSystemCommand(
        "create_device_group",
        { name, description },
        this.activeSubentryId || null,
      );
      this.newGroupName = "";
      this.newGroupDesc = "";
      if (res) this.ingestStatePayload(res, false);
      this.showToast(`Created group "${name}"`);
    } catch (err) {
      this.showToast(formatWsError(err, "Could not create Device Group"), true);
    }
  }

  async deleteDeviceGroup(groupId: string): Promise<void> {
    try {
      const res = await this.ws.runSystemCommand(
        "delete_device_group",
        { group_id: groupId },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
      this.showToast("Deleted Device Group");
    } catch (err) {
      this.showToast(formatWsError(err, "Could not delete Device Group"), true);
    }
  }

  async syncDeviceGroup(groupId: string, singleSubentryId?: string): Promise<void> {
    try {
      const payload: Record<string, unknown> = { group_id: groupId };
      if (singleSubentryId) payload.subentry_id = singleSubentryId;
      const res = await this.ws.runSystemCommand(
        "sync_device_group",
        payload,
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
      this.showToast("Synced to group baseline");
    } catch (err) {
      this.showToast(formatWsError(err, "Could not sync Device Group"), true);
    }
  }

  async seedGroupBaselineFromDevice(): Promise<void> {
    if (!this.seedGroupTargetId || !this.seedSourceSubentryId) {
      this.showToast("Choose both a target group and a source Device", true);
      return;
    }
    try {
      const res = await this.ws.runSystemCommand(
        "seed_group_baseline",
        {
          group_id: this.seedGroupTargetId,
          subentry_id: this.seedSourceSubentryId,
        },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
      this.showToast("Saved group baseline from Device");
    } catch (err) {
      this.showToast(formatWsError(err, "Could not seed group baseline"), true);
    }
  }

  resolvedGroupCtrlId(): string {
    const filter = this.groupCtrlFilter || "all";
    if (filter.startsWith("group:")) return filter.slice(6);
    if (filter === "trait:roaming") return "roaming";
    if (filter === "trait:stationary") return "stationary";
    return filter;
  }

  async setGroupDeviceSetting(patch: Record<string, unknown>): Promise<void> {
    try {
      const res = await this.ws.runSystemCommand(
        "set_group_device_setting",
        {
          group_id: this.resolvedGroupCtrlId() || "all",
          config: patch,
        },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
      this.showToast("Applied group setting");
    } catch (err) {
      this.showToast(formatWsError(err, "Could not apply group setting"), true);
    }
  }

  filteredControlTargets(ctrl: SharedControlItem): string[] {
    const grpId = this.resolvedGroupCtrlId();
    return (ctrl.targets || [])
      .filter((t) => {
        if (grpId === "all") return true;
        if (grpId === "roaming") return Boolean(t.is_roaming);
        if (grpId === "stationary") return !t.is_roaming;
        return t.device_group === grpId;
      })
      .map((t) => t.entity_id)
      .filter(Boolean);
  }

  async bulkToggle(ctrl: SharedControlItem, turnOn: boolean): Promise<void> {
    const entityIds = this.filteredControlTargets(ctrl);
    if (!entityIds.length) return;
    try {
      const res = await this.ws.runSystemCommand(
        "system_entity_action",
        {
          entity_ids: entityIds,
          action: turnOn ? "turn_on" : "turn_off",
          group_id: this.resolvedGroupCtrlId() || "all",
          canonical_key: ctrl.canonical_key,
        },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
    } catch (err) {
      this.showToast(formatWsError(err, "Bulk switch update failed"), true);
    }
  }

  async bulkSelect(ctrl: SharedControlItem, option: string): Promise<void> {
    const entityIds = this.filteredControlTargets(ctrl);
    if (!entityIds.length) return;
    try {
      const res = await this.ws.runSystemCommand(
        "system_entity_action",
        {
          entity_ids: entityIds,
          option,
          group_id: this.resolvedGroupCtrlId() || "all",
          canonical_key: ctrl.canonical_key,
        },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
    } catch (err) {
      this.showToast(formatWsError(err, "Bulk option update failed"), true);
    }
  }

  async bulkNumber(ctrl: SharedControlItem, level: number): Promise<void> {
    const entityIds = this.filteredControlTargets(ctrl);
    if (!entityIds.length || !Number.isFinite(level)) return;
    try {
      const res = await this.ws.runSystemCommand(
        "system_entity_action",
        {
          entity_ids: entityIds,
          level,
          group_id: this.resolvedGroupCtrlId() || "all",
          canonical_key: ctrl.canonical_key,
        },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
    } catch (err) {
      this.showToast(formatWsError(err, "Bulk number update failed"), true);
    }
  }

  // ---------- BLE Calibration & Sensor Fusion ----------

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
    const devs = this.state?.system_devices || [];
    return devs.find((d) => d.subentry_id === this.bleSurveySubentryId);
  }

  async setBleOffset(areaId: string, offsetDb: number): Promise<void> {
    try {
      const res = await this.ws.runSystemCommand(
        "set_ble_area_offset",
        { area_id: areaId, offset_db: offsetDb },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
    } catch (err) {
      this.showToast(formatWsError(err, "Could not update BLE offset"), true);
    }
  }

  async autoCalibrateHere(areaId: string): Promise<void> {
    if (!this.bleSurveySubentryId) {
      this.showToast("Select a calibration Device first", true);
      return;
    }
    try {
      const res = await this.ws.runSystemCommand(
        "auto_calibrate_here",
        { area_id: areaId, survey_subentry_id: this.bleSurveySubentryId },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
      this.showToast("Calibrated Area offset");
    } catch (err) {
      this.showToast(formatWsError(err, "Calibration failed"), true);
    }
  }

  async setAreaFusion(
    areaId: string,
    update: { mode?: string; threshold_pct?: number; sensors?: string[] },
  ): Promise<void> {
    try {
      const res = await this.ws.runSystemCommand(
        "set_area_fusion",
        { area_id: areaId, ...update },
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
    } catch (err) {
      this.showToast(formatWsError(err, "Could not update Area fusion"), true);
    }
  }

  // ---------- Announcements, Backups & Logs ----------

  async sendAnnouncement(): Promise<void> {
    const message = this.announceMessage.trim();
    if (!message) {
      this.showToast("Enter a message", true);
      return;
    }
    const payload: Record<string, unknown> = {
      mode: this.announceMode,
      target_device: this.announceTarget || "all",
      message,
    };
    if (this.announceMode === "notify") {
      const title = this.announceTitle.trim();
      if (!title) {
        this.showToast("Enter a notification title", true);
        return;
      }
      payload.title = title;
      payload.priority = this.announcePriority;
      payload.include_camera = this.announceIncludeCamera;
    }
    try {
      const res = await this.ws.runSystemCommand(
        "send_announcement",
        payload,
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, false);
      this.showToast(
        this.announceMode === "notify" ? "Sent notification" : "Broadcast announcement sent",
      );
    } catch (err) {
      this.showToast(formatWsError(err, "Could not send announcement"), true);
    }
  }

  async exportBackup(explicitSubentryId?: string): Promise<void> {
    try {
      const dateStr = new Date().toISOString().slice(0, 10);
      if (explicitSubentryId) {
        const { bundle } = await this.ws.exportBackup("device", explicitSubentryId);
        const slug = String(bundle.target_device || this.state?.config?.device_slug || "esphome");
        triggerJsonDownload(`latter-device-${slug}-backup-${dateStr}.json`, bundle);
        this.showToast("Downloaded the Device backup");
        return;
      }
      const choice = this.backupExportScope || "system";
      const deviceId = choice.startsWith("device:") ? choice.slice(7) : choice !== "system" ? choice : "";
      if (!deviceId) {
        const { bundle } = await this.ws.exportBackup("system");
        triggerJsonDownload(`latter-system-backup-${dateStr}.json`, bundle);
        this.showToast("Downloaded the System backup");
      } else {
        const { bundle } = await this.ws.exportBackup("device", deviceId);
        const slug = String(bundle.target_device || deviceId);
        triggerJsonDownload(`latter-device-${slug}-backup-${dateStr}.json`, bundle);
        this.showToast("Downloaded the Device backup");
      }
    } catch (err) {
      this.showToast(formatWsError(err, "Backup export failed"), true);
    }
  }

  async restoreFromUploadedFile(): Promise<void> {
    if (!this.selectedBackupFile) {
      this.showToast("Choose a JSON backup file first", true);
      return;
    }
    try {
      const text = await this.selectedBackupFile.text();
      const raw = JSON.parse(text) as Record<string, unknown>;
      const bundle =
        raw.bundle && typeof raw.bundle === "object"
          ? (raw.bundle as Record<string, unknown>)
          : raw;
      const scope: StudioScope = String(bundle.scope || "") === "device" ? "device" : "system";
      const targetId = scope === "device" ? this.backupRestoreSubentryId || "" : "";
      if (scope === "device" && !targetId) {
        this.showToast("Choose the Device to restore this Device backup onto", true);
        return;
      }
      const res = await this.ws.importBackup({
        scope,
        bundle,
        targetSubentryId: targetId || null,
        selectedSubentryId: this.activeSubentryId || null,
        restoreEspHomeEntities: this.backupRestoreEsp,
      });
      this.selectedBackupFile = null;
      if (res) this.ingestStatePayload(res, false);
      this.showToast(scope === "device" ? "Restored the Device backup" : "Restored the System backup");
    } catch (err) {
      this.showToast(formatWsError(err, "Backup restore failed"), true);
    }
  }

  onToggleLogsDetails(open: boolean): void {
    this.logsOpen = open;
    this.host.requestUpdate();
    if (open) {
      void this.refreshState({ includeLogs: true });
    }
  }

  formatVisibleLogs(): string {
    const entries = this.state?.internal_logs || [];
    const filter = this.logFilter || "all";
    const filtered = entries.filter((e) => {
      const lvl = String(e.level || "").toUpperCase();
      const src = String(e.source || "").toLowerCase();
      if (filter === "latter") return src === "studio" || src === "system" || src.includes("latter");
      if (filter === "errors") return lvl === "WARNING" || lvl === "WARN" || lvl === "ERROR" || lvl === "CRITICAL";
      if (filter.startsWith("device:") || filter.startsWith("dev:")) {
        const slug = (filter.startsWith("device:") ? filter.slice(7) : filter.slice(4)).toLowerCase();
        return src === slug || String(e.message || "").toLowerCase().includes(slug);
      }
      return true;
    });
    if (!filtered.length) return "No events logged yet.";
    return filtered
      .map((e) => {
        const rawTs = e.timestamp || (typeof e.ts === "number" ? new Date(e.ts * 1000).toISOString() : String(e.ts || ""));
        const lvl = String(e.level || "INFO").toUpperCase();
        const src = String(e.source || "latter");
        return `${rawTs ? `[${rawTs}] ` : ""}${lvl} (${src}): ${String(e.message || "")}`;
      })
      .join("\n");
  }

  async copyLogsToClipboard(): Promise<void> {
    const ok = await copyTextToClipboard(this.formatVisibleLogs());
    this.showToast(ok ? "Copied logs to clipboard" : "Could not copy logs", !ok);
  }

  async clearInternalLogs(): Promise<void> {
    try {
      const res = await this.ws.runSystemCommand(
        "clear_internal_logs",
        {},
        this.activeSubentryId || null,
      );
      if (res) this.ingestStatePayload(res, true);
      this.showToast("Cleared internal logs");
    } catch (err) {
      this.showToast(formatWsError(err, "Could not clear logs"), true);
    }
  }
}
