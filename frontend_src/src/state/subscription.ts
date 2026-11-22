/**
 * Event-First `latter/system/subscribe` Manager, Reconnect Backoff, BLE Delta Stream,
 * & Cross-Device Payload Isolation (`SubscriptionController`, `D-064`, `D-065`, `M-P1-49`).
 */

import { formatWsError, isStudioRevMismatchError } from "../api/ws-client.js";
import type {
  AreaPresenceRow,
  BleAreaSignatureSummary,
  BleSurveyDeltaEvent,
  BleSurveyRow,
  DeviceViewId,
  DiscoveredBleCandidate,
  HassConnection,
  StudioStatePayload,
  SystemConfig,
} from "../types.js";
import {
  overlayDevicePrefsOnSections,
  overlayPendingBlankListSlots,
  overlayPendingEntityStates,
} from "./group-overlay.js";
import { deviceHasView } from "./routing.js";
import type { StudioStoreContext } from "./store-types.js";

const RECONNECT_BACKOFF_MS: ReadonlyArray<number> = [2_000, 5_000, 15_000, 60_000];

export class SubscriptionController {
  private readonly store: StudioStoreContext;

  private subGen = 0;
  private stateReqSeq = 0;
  private lastAppliedReqSeq = 0;
  private wsUnsub: (() => void) | null = null;
  private subscribedKey = "";
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private boundConnection: HassConnection | null = null;

  private readonly onConnectionReady = (): void => {
    if (this.store.studioRevMismatch || !this.store.host.isConnected) return;
    this.reconnectAttempt = 0;
    this.clearReconnectTimer();
    void this.store.ensureSubscription(true);
  };

  constructor(store: StudioStoreContext) {
    this.store = store;
  }

  clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  syncConnectionListener(): void {
    const nextConn = this.store.host.isConnected
      ? (this.store.ws.hass?.connection ?? null)
      : null;
    if (this.boundConnection === nextConn) return;
    this.detachConnectionListener();
    if (nextConn && typeof nextConn.addEventListener === "function") {
      nextConn.addEventListener("ready", this.onConnectionReady);
      this.boundConnection = nextConn;
    }
  }

  detachConnectionListener(): void {
    if (this.boundConnection && typeof this.boundConnection.removeEventListener === "function") {
      try {
        this.boundConnection.removeEventListener("ready", this.onConnectionReady);
      } catch {
        // Ignore teardown errors on closed sockets.
      }
    }
    this.boundConnection = null;
  }

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
    const sub = this.store.deviceSelected ? this.store.activeSubentryId || "" : "";
    const survey =
      this.store.currentScope === "system" &&
      this.store.currentViewId === "area_tracking" &&
      this.store.bleLiveStreamActive
        ? this.store.bleSurveySubentryId || ""
        : "";
    const logs = this.store.shouldIncludeLogs() ? "1" : "0";
    return `${sub}|${survey}|${logs}`;
  }

  async ensureSubscription(forceResubscribe = false): Promise<void> {
    if (this.store.studioRevMismatch || !this.store.ws.hass?.connection) return;
    const nextKey = this.store.desiredSubscriptionKey();
    if (!forceResubscribe && this.wsUnsub && this.subscribedKey === nextKey) {
      return;
    }
    this.clearReconnectTimer();
    this.store.teardownSubscription();
    const myGen = ++this.subGen;
    const targetSubId = this.store.deviceSelected ? this.store.activeSubentryId || null : null;
    const surveyId =
      this.store.currentScope === "system" &&
      this.store.currentViewId === "area_tracking" &&
      this.store.bleLiveStreamActive
        ? this.store.bleSurveySubentryId || null
        : null;
    const includeLogs = this.store.shouldIncludeLogs();

    try {
      const unsub = await this.store.ws.subscribe(
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
      if (isStudioRevMismatchError(err) || this.store.studioRevMismatch) {
        this.store.handleStudioRevMismatch();
        return;
      }
      if (!this.store.state) {
        this.store.loading = false;
        this.store.deviceLoading = false;
        this.store.loadError = formatWsError(err, "Latter Studio could not connect.");
        this.store.host.requestUpdate();
      } else if (this.store.deviceLoading) {
        this.store.deviceLoading = false;
        this.store.loadError = formatWsError(err, "Latter Studio could not connect.");
        this.store.host.requestUpdate();
      }
      const delay =
        RECONNECT_BACKOFF_MS[
          Math.min(this.reconnectAttempt, RECONNECT_BACKOFF_MS.length - 1)
        ] ?? 60_000;
      this.reconnectAttempt += 1;
      this.clearReconnectTimer();
      this.reconnectTimer = setTimeout(() => {
        this.reconnectTimer = null;
        if (this.store.host.isConnected && !this.store.studioRevMismatch) {
          void this.store.ensureSubscription(true);
        }
      }, delay);
    }
  }

  async refreshState(options?: { includeLogs?: boolean }): Promise<void> {
    if (this.store.studioRevMismatch || !this.store.ws.hass) return;
    const reqSeq = ++this.stateReqSeq;
    const targetSubId = this.store.deviceSelected ? this.store.activeSubentryId || null : null;
    const includeLogs = options?.includeLogs ?? this.store.shouldIncludeLogs();
    try {
      const payload = await this.store.ws.getState({
        subentryId: targetSubId,
        includeLogs,
      });
      if (reqSeq < this.lastAppliedReqSeq) return;
      this.lastAppliedReqSeq = reqSeq;
      this.store.loadError = "";
      this.store.loading = false;
      this.store.ingestPayload(payload, includeLogs);
      if (!this.wsUnsub && this.store.host.isConnected && !this.store.studioRevMismatch) {
        void this.store.ensureSubscription(false);
      }
    } catch (err) {
      if (isStudioRevMismatchError(err) || this.store.studioRevMismatch) {
        this.store.handleStudioRevMismatch();
        return;
      }
      if (reqSeq < this.lastAppliedReqSeq) return;
      this.store.loading = false;
      this.store.deviceLoading = false;
      this.store.loadError = formatWsError(err, "Latter Studio could not load.");
      this.store.host.requestUpdate();
    }
  }

  private handleSubscriptionEvent(raw: unknown, subscribedWithLogs: boolean): void {
    if (!raw || typeof raw !== "object") return;
    const rec = raw as Record<string, unknown>;
    if (rec.type === "ble_survey_delta") {
      this.store.applyBleSurveyDelta(rec as unknown as BleSurveyDeltaEvent);
      return;
    }

    const payload = raw as StudioStatePayload;
    this.store.loading = false;
    this.store.loadError = "";
    this.store.ingestPayload(payload, subscribedWithLogs);
  }

  applyBleSurveyDelta(delta: BleSurveyDeltaEvent): void {
    if (!this.store.state) return;
    if (!this.store.bleLiveStreamActive) {
      let updated = false;
      if (Array.isArray(delta.ble_area_signatures)) {
        this.store.state = {
          ...this.store.state,
          ble_area_signatures: delta.ble_area_signatures as BleAreaSignatureSummary[],
        };
        updated = true;
      }
      if (Array.isArray(delta.area_presence_grid) && this.store.state.live) {
        this.store.state = {
          ...this.store.state,
          live: {
            ...this.store.state.live,
            area_presence_grid: delta.area_presence_grid as AreaPresenceRow[],
          },
        };
        updated = true;
      }
      if (updated) {
        this.store.host.requestUpdate();
      }
      return;
    }

    const targetId = String(
      delta.subentry_id || this.store.bleSurveySubentryId || this.store.state.subentry_id || "",
    );
    let nextDevices = this.store.state.system_devices;
    let nextLive = this.store.state.live;
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
        this.store.state.subentry_id === targetId &&
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
    this.store.state = {
      ...this.store.state,
      system_devices: nextDevices,
      ble_area_signatures: Array.isArray(delta.ble_area_signatures)
        ? (delta.ble_area_signatures as BleAreaSignatureSummary[])
        : this.store.state.ble_area_signatures,
      live: nextLive,
    };
    this.store.host.requestUpdate();
  }

  private mergeFrozenBleRows(
    devices: StudioStatePayload["system_devices"],
  ): StudioStatePayload["system_devices"] {
    if (this.store.bleLiveStreamActive || !Array.isArray(devices)) return devices;
    return devices.map((dev) => {
      if (!dev.subentry_id) return dev;
      const frozen = this.store.bleSurveyFrozen.get(dev.subentry_id);
      if (frozen) {
        return {
          ...dev,
          ble_survey_rows: frozen.rows.map((r) => ({ ...r })),
          ble_packets_seen: frozen.packetsSeen,
          active_area_name: frozen.activeAreaName,
        };
      }
      this.store.bleSurveyFrozen.set(dev.subentry_id, {
        rows: (dev.ble_survey_rows || []).map((r) => ({ ...r })),
        packetsSeen: dev.ble_packets_seen ?? 0,
        activeAreaName: dev.active_area_name || "",
      });
      return dev;
    });
  }

  ingestPayload(incoming: StudioStatePayload, logsWereRequested: boolean): void {
    const prev = this.store.state;
    const prevSysConfig = prev?.system_config;

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
        ? this.stabilizeDiscoveredBle(incoming.discovered_ble_devices, incoming.system_devices)
        : prev?.discovered_ble_devices ?? [];
    const mergedLogs =
      logsWereRequested ||
      (Array.isArray(incoming.internal_logs) && incoming.internal_logs.length > 0)
        ? incoming.internal_logs || []
        : prev?.internal_logs || [];
    const mergedSystemDevices = this.mergeFrozenBleRows(incoming.system_devices);

    if (incoming.subentry_id && incoming.device_config_rev > 0) {
      this.store.recordKnownDeviceConfigRev(incoming.subentry_id, incoming.device_config_rev);
    }

    if (
      this.store.deviceSelected &&
      this.store.activeSubentryId &&
      Array.isArray(mergedSystemDevices) &&
      !mergedSystemDevices.some((d) => d.subentry_id === this.store.activeSubentryId)
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
      const effSysPatch = this.store.entity.getEffectiveSystemPatch();
      if (Object.keys(effSysPatch).length > 0 && sysOnly.system_config) {
        sysOnly.system_config = {
          ...sysOnly.system_config,
          ...(effSysPatch as Partial<SystemConfig>),
        };
      }
      overlayPendingBlankListSlots(this.store, sysOnly, prevSysConfig);
      this.store.state = sysOnly;
      this.store.redirectInvalidDeviceRoute(this.store.activeSubentryId);
      return;
    }

    if (
      this.store.deviceSelected &&
      this.store.activeSubentryId &&
      incoming.subentry_id !== this.store.activeSubentryId
    ) {
      const keepPrevDevice = prev && prev.subentry_id === this.store.activeSubentryId;
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
        catalog: mergedCatalog,
        pref_specs: mergedPrefSpecs,
        world_clock_zones: mergedWorldClockZones,
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

      const effSysPatch = this.store.entity.getEffectiveSystemPatch();
      if (Object.keys(effSysPatch).length > 0 && sysMerged.system_config) {
        sysMerged.system_config = {
          ...sysMerged.system_config,
          ...(effSysPatch as Partial<SystemConfig>),
        };
      }
      overlayPendingBlankListSlots(this.store, sysMerged, prevSysConfig);

      this.store.deviceLoading = !keepPrevDevice;
      this.store.state = sysMerged;
      this.store.ensureDefaultSurveyDevice();
      this.store.ensureDefaultDoorbellTester();
      this.store.ensureValidBatchTargetFilter();
      this.store.syncLiveClockTimer();
      this.store.host.requestUpdate();
      if (
        !keepPrevDevice &&
        this.store.host.isConnected &&
        this.store.ws.hass &&
        !this.store.studioRevMismatch
      ) {
        void this.store.ensureSubscription(false);
      }
      return;
    }

    this.store.deviceLoading = false;
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

    const effSysPatch = this.store.entity.getEffectiveSystemPatch();
    if (Object.keys(effSysPatch).length > 0 && merged.system_config) {
      merged.system_config = {
        ...merged.system_config,
        ...(effSysPatch as Partial<SystemConfig>),
      };
    }
    overlayPendingBlankListSlots(this.store, merged, prevSysConfig);

    if (merged.subentry_id) {
      const effDevPatch = this.store.entity.getEffectiveDevicePatch(merged.subentry_id);
      if (Object.keys(effDevPatch).length > 0 && merged.config) {
        overlayDevicePrefsOnSections(merged, effDevPatch);
      }
    }

    overlayPendingEntityStates(merged, this.store.pendingEntityStates);

    if (
      this.store.currentScope === "device" &&
      this.store.deviceSelected &&
      merged.subentry_id === this.store.activeSubentryId &&
      !deviceHasView(
        this.store.currentViewId as DeviceViewId,
        merged.capabilities,
        merged.config?.kind,
      )
    ) {
      this.store.currentViewId = "dashboard";
      this.store.syncUrl(true);
    }

    this.store.state = merged;
    this.store.ensureDefaultSurveyDevice();
    this.store.ensureDefaultDoorbellTester();
    this.store.ensureValidBatchTargetFilter();
    this.store.syncLiveClockTimer();
    this.store.host.requestUpdate();
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
    for (const [addrKey, entry] of this.store.discoveredBleSeenCache.entries()) {
      const candSlug = String((entry.candidate as unknown as { slug?: string }).slug || "")
        .trim()
        .toLowerCase();
      if (
        now - entry.lastSeenMs > RETENTION_MS ||
        (candSlug && onboardedSlugs.has(candSlug))
      ) {
        this.store.discoveredBleSeenCache.delete(addrKey);
      }
    }
    const extraNoKey: DiscoveredBleCandidate[] = [];
    for (const c of candidates) {
      const addrKey = String(c.target_address || "").trim().toLowerCase();
      if (addrKey) {
        this.store.discoveredBleSeenCache.set(addrKey, { candidate: c, lastSeenMs: now });
      } else {
        extraNoKey.push(c);
      }
    }
    return [
      ...Array.from(this.store.discoveredBleSeenCache.values(), (entry) => entry.candidate),
      ...extraNoKey,
    ];
  }

  toggleDiscoveredBlePause(paused?: boolean): void {
    const next = paused ?? !this.store.discoveredBlePaused;
    this.store.discoveredBlePaused = next;
    if (next) {
      this.store.discoveredBleFrozenSnapshot = [
        ...(this.store.state?.discovered_ble_devices || []),
      ];
    } else {
      this.store.discoveredBleFrozenSnapshot = null;
    }
    this.store.host.requestUpdate();
  }

  evictAdoptedBleCandidate(targetAddress: string): void {
    const addrKey = String(targetAddress || "").trim().toLowerCase();
    if (!addrKey) return;
    this.store.discoveredBleSeenCache.delete(addrKey);
    this.store.discoveredBlePersonDrafts.delete(addrKey);
    if (this.store.discoveredBleFrozenSnapshot) {
      this.store.discoveredBleFrozenSnapshot = this.store.discoveredBleFrozenSnapshot.filter(
        (c) => String(c.target_address || "").trim().toLowerCase() !== addrKey,
      );
    }
  }

  ensureDefaultSurveyDevice(): void {
    const devs = this.store.state?.system_devices || [];
    const bleDevs = devs.filter((d) => d.ble_tracked || d.kind === "ble_tag");
    if (
      this.store.bleSurveySubentryId &&
      bleDevs.some((d) => d.subentry_id === this.store.bleSurveySubentryId)
    ) {
      return;
    }
    const current = bleDevs.find((d) => d.subentry_id === this.store.activeSubentryId);
    this.store.bleSurveySubentryId = current?.subentry_id || bleDevs[0]?.subentry_id || "";
  }

  ensureDefaultDoorbellTester(): void {
    const devs = (this.store.state?.system_devices || []).filter((d) => d.kind !== "ble_tag");
    if (
      this.store.doorbellTestSubentryId &&
      devs.some((d) => d.subentry_id === this.store.doorbellTestSubentryId)
    ) {
      return;
    }
    this.store.doorbellTestSubentryId = devs[0]?.subentry_id || "";
  }

  ensureValidBatchTargetFilter(): void {
    if (!this.store.batchTargetFilter.startsWith("group:")) return;
    const gid = this.store.batchTargetFilter.slice(6);
    if (gid === "custom") return;
    const groups = this.store.state?.device_groups || [];
    if (!groups.some((g) => g.id === gid)) {
      this.store.batchTargetFilter = "all";
      this.store.groups.resetBatchDraft();
    }
  }
}
