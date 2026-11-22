/**
 * Serialized System & Per-Device Settings Save Controller (`SettingsSaveController`, `D-062`, `D-064`).
 *
 * - Serialized `systemSaveChain` & per-Device `deviceSaveChains` with `inFlight` patch overlays.
 * - Monotonic per-key edit ownership so failed saves never clobber newer pending/in-flight edits.
 * - `expected_config_rev` optimistic concurrency with automatic `"conflict"` state resync.
 */

import { formatWsError, isConflictError } from "../api/ws-client.js";
import type { DeviceConfig, StudioStatePayload, SystemConfig } from "../types.js";
import {
  cleanPersistedStringList,
  isStringListKey,
  overlayDevicePrefsOnSections,
  overlayPendingBlankListSlots,
  STRING_LIST_MAX_ITEMS,
} from "./group-overlay.js";
import type { StudioStoreContext } from "./store-types.js";

export const SAVE_DEBOUNCE_MS = 220;

export class SettingsSaveController {
  private readonly store: StudioStoreContext;

  private editSeqCounter = 0;
  private systemSaveChain: Promise<void> = Promise.resolve();
  private readonly inFlightSystemPatch: Record<string, unknown> = {};
  private readonly systemKeySeqs = new Map<string, number>();
  private pendingSystemKeySeqs: Record<string, number> = {};

  private readonly deviceSaveChains = new Map<string, Promise<void>>();
  private readonly inFlightDevicePatches = new Map<string, Record<string, unknown>>();
  private readonly deviceKeySeqs = new Map<string, Map<string, number>>();

  constructor(store: StudioStoreContext) {
    this.store = store;
  }

  getEffectiveSystemPatch(): Record<string, unknown> {
    return {
      ...this.inFlightSystemPatch,
      ...this.store.pendingSystemPatch,
    };
  }

  getEffectiveDevicePatch(subentryId: string): Record<string, unknown> {
    const inFlight = this.inFlightDevicePatches.get(subentryId) || {};
    const pending = this.store.pendingDeviceBuckets.get(subentryId)?.patch || {};
    return { ...inFlight, ...pending };
  }

  discardDeviceBucket(subentryId: string): void {
    const bucket = this.store.pendingDeviceBuckets.get(subentryId);
    if (bucket?.timer) {
      clearTimeout(bucket.timer);
      bucket.timer = null;
    }
    this.store.pendingDeviceBuckets.delete(subentryId);
    this.inFlightDevicePatches.delete(subentryId);
  }

  private getDeviceKeySeqMap(subentryId: string): Map<string, number> {
    let map = this.deviceKeySeqs.get(subentryId);
    if (!map) {
      map = new Map<string, number>();
      this.deviceKeySeqs.set(subentryId, map);
    }
    return map;
  }

  stageDeviceSetting(
    key: string,
    value: unknown,
    controlDomId?: string,
    debounceMs = SAVE_DEBOUNCE_MS,
  ): void {
    const targetSubentryId = this.store.activeSubentryId;
    if (!targetSubentryId || this.store.deviceLoading) return;

    let bucket = this.store.pendingDeviceBuckets.get(targetSubentryId);
    const activeDevEntry = this.store.state?.system_devices?.find(
      (d) => d.subentry_id === targetSubentryId,
    );
    const targetTitle =
      (this.store.state?.subentry_id === targetSubentryId ? this.store.state.title : "") ||
      activeDevEntry?.title ||
      targetSubentryId;

    if (!bucket) {
      bucket = {
        targetSubentryId,
        targetTitle,
        patch: {},
        previousValues: {},
        keySeqs: {},
        timer: null,
      };
      this.store.pendingDeviceBuckets.set(targetSubentryId, bucket);
    }

    const curCfg =
      this.store.state && this.store.state.subentry_id === targetSubentryId
        ? ((this.store.state.config || {}) as Record<string, unknown>)
        : {};
    const targetBucket = bucket;
    const snapshotKey = (k: string): void => {
      if (!(k in targetBucket.previousValues)) {
        targetBucket.previousValues[k] = curCfg[k];
      }
    };
    snapshotKey(key);
    snapshotKey("device_group");
    if (key === "home_screen_enabled") {
      snapshotKey("start_screen");
    }
    if (controlDomId && !(`__dom:${controlDomId}` in targetBucket.previousValues)) {
      targetBucket.previousValues[`__dom:${controlDomId}`] = targetBucket.previousValues[key];
    }

    const seq = ++this.editSeqCounter;
    const seqMap = this.getDeviceKeySeqMap(targetSubentryId);
    seqMap.set(key, seq);
    targetBucket.keySeqs[key] = seq;
    if (controlDomId) {
      seqMap.set(`__dom:${controlDomId}`, seq);
      targetBucket.keySeqs[`__dom:${controlDomId}`] = seq;
    }

    targetBucket.patch[key] = value;
    if (this.store.state) {
      const nextSystemDevices =
        key === "device_remote_group" && Array.isArray(this.store.state.system_devices)
          ? this.store.state.system_devices.map((d) =>
              d.subentry_id === targetSubentryId
                ? { ...d, device_remote_group: String(value || "area_auto") }
                : d,
            )
          : this.store.state.system_devices;
      if (this.store.state.subentry_id === targetSubentryId) {
        const nextPayload: StudioStatePayload = {
          ...this.store.state,
          system_devices: nextSystemDevices,
          config: { ...this.store.state.config },
        };
        overlayDevicePrefsOnSections(nextPayload, { [key]: value });
        this.store.state = nextPayload;
      } else if (nextSystemDevices !== this.store.state.system_devices) {
        this.store.state = {
          ...this.store.state,
          system_devices: nextSystemDevices,
        };
      }
    }

    if (targetBucket.timer) clearTimeout(targetBucket.timer);
    targetBucket.timer = setTimeout(() => {
      void this.flushDeviceBucket(targetSubentryId);
    }, Math.max(0, debounceMs));
    this.store.host.requestUpdate();
  }

  flushDeviceBucket(targetSubentryId: string): Promise<void> {
    const bucket = this.store.pendingDeviceBuckets.get(targetSubentryId);
    const prevChain = this.deviceSaveChains.get(targetSubentryId) ?? Promise.resolve();
    if (!bucket) return prevChain;

    if (bucket.timer) {
      clearTimeout(bucket.timer);
      bucket.timer = null;
    }
    const patch = { ...bucket.patch };
    const previousValues = { ...bucket.previousValues };
    const batchKeySeqs = { ...bucket.keySeqs };
    const targetTitle = bucket.targetTitle;
    this.store.pendingDeviceBuckets.delete(targetSubentryId);

    if (Object.keys(patch).length === 0) return prevChain;

    const inFlight = this.inFlightDevicePatches.get(targetSubentryId) || {};
    Object.assign(inFlight, patch);
    this.inFlightDevicePatches.set(targetSubentryId, inFlight);

    const nextChain = prevChain.then(async () => {
      const seqMap = this.getDeviceKeySeqMap(targetSubentryId);
      const clearOwnedInFlight = (): void => {
        const curInFlight = this.inFlightDevicePatches.get(targetSubentryId);
        if (!curInFlight) return;
        for (const k of Object.keys(patch)) {
          if (seqMap.get(k) === batchKeySeqs[k]) {
            delete curInFlight[k];
          }
        }
        if (Object.keys(curInFlight).length === 0) {
          this.inFlightDevicePatches.delete(targetSubentryId);
        }
      };

      const expectedRev = this.store.getKnownDeviceConfigRev(targetSubentryId);
      const reqPayload: Record<string, unknown> = { config: patch };
      if (expectedRev > 0) {
        reqPayload.expected_config_rev = expectedRev;
      }

      try {
        const res = await this.store.ws.runDeviceCommand(
          targetSubentryId,
          "save_device_config",
          reqPayload,
        );
        clearOwnedInFlight();
        if (res) {
          if (res.subentry_id === targetSubentryId && res.device_config_rev > 0) {
            this.store.recordKnownDeviceConfigRev(targetSubentryId, res.device_config_rev);
          }
          if (this.store.activeSubentryId === targetSubentryId) {
            this.store.ingestPayload(res, false);
          } else if (this.store.state && Array.isArray(res.system_devices)) {
            this.store.state = {
              ...this.store.state,
              system_devices: res.system_devices,
              issues: res.issues ?? this.store.state.issues,
            };
            this.store.host.requestUpdate();
          }
        }
        this.store.announcePolite(this.store.t("shell.saved_status"));
      } catch (err) {
        clearOwnedInFlight();
        if (isConflictError(err)) {
          await this.store.refreshState();
          this.store.showToast(this.store.t("sync.conflict_reloaded"), true);
          return;
        }

        const controlRevert: Record<string, string | boolean> = {};
        for (const [k, v] of Object.entries(previousValues)) {
          if (k.startsWith("__dom:")) {
            if (seqMap.get(k) !== batchKeySeqs[k]) continue;
            const domId = k.slice(6);
            if (typeof v === "boolean") controlRevert[domId] = v;
            else if (v !== undefined && v !== null) controlRevert[domId] = String(v);
            else controlRevert[domId] = "";
          }
        }

        const remoteGroupOwned =
          "device_remote_group" in previousValues &&
          seqMap.get("device_remote_group") === batchKeySeqs.device_remote_group;

        if (this.store.state) {
          const nextSystemDevices =
            remoteGroupOwned && Array.isArray(this.store.state.system_devices)
              ? this.store.state.system_devices.map((d) =>
                  d.subentry_id === targetSubentryId
                    ? {
                        ...d,
                        device_remote_group: String(
                          previousValues.device_remote_group || "area_auto",
                        ),
                      }
                    : d,
                )
              : this.store.state.system_devices;
          if (this.store.state.subentry_id === targetSubentryId) {
            const restoredConfig: Record<string, unknown> = {
              ...(this.store.state.config as Record<string, unknown>),
            };
            const restoredPrefs: Record<string, unknown> = {};
            for (const [k, v] of Object.entries(previousValues)) {
              if (k.startsWith("__dom:")) continue;
              if (k in batchKeySeqs && seqMap.get(k) !== batchKeySeqs[k]) continue;
              if (v === undefined) {
                delete restoredConfig[k];
              } else {
                restoredConfig[k] = v;
                restoredPrefs[k] = v;
              }
            }
            const nextPayload: StudioStatePayload = {
              ...this.store.state,
              system_devices: nextSystemDevices,
              config: restoredConfig as DeviceConfig,
            };
            if (Object.keys(restoredPrefs).length > 0) {
              overlayDevicePrefsOnSections(nextPayload, restoredPrefs);
            }
            const newerPatch = this.getEffectiveDevicePatch(targetSubentryId);
            if (Object.keys(newerPatch).length > 0) {
              overlayDevicePrefsOnSections(nextPayload, newerPatch);
            }
            this.store.state = nextPayload;
          } else if (nextSystemDevices !== this.store.state.system_devices) {
            this.store.state = {
              ...this.store.state,
              system_devices: nextSystemDevices,
            };
          }
        }
        if (
          this.store.activeSubentryId === targetSubentryId &&
          Object.keys(controlRevert).length > 0
        ) {
          this.store.mergeDomRevert(controlRevert);
        }
        const rawReason = formatWsError(err, this.store.t("sync.save_device_failed"));
        const msg =
          this.store.activeSubentryId !== targetSubentryId && targetTitle
            ? this.store.t("sync.save_device_named_failed", {
                title: targetTitle,
                error: rawReason,
              })
            : rawReason;
        this.store.showToast(msg, true);
        this.store.host.requestUpdate();
      }
    });

    this.deviceSaveChains.set(targetSubentryId, nextChain);
    return nextChain;
  }

  stageSystemSetting<K extends keyof SystemConfig>(
    key: K,
    value: SystemConfig[K],
    controlDomId?: string,
    debounceMs = SAVE_DEBOUNCE_MS,
  ): void {
    const keyStr = String(key);
    if (!(keyStr in this.store.pendingSystemPrevious)) {
      const prev = (this.store.state?.system_config as unknown as Record<string, unknown>)?.[
        keyStr
      ];
      if (isStringListKey(keyStr) && Array.isArray(prev)) {
        this.store.pendingSystemPrevious[keyStr] = cleanPersistedStringList(
          prev,
          STRING_LIST_MAX_ITEMS[keyStr],
        );
      } else {
        this.store.pendingSystemPrevious[keyStr] =
          prev !== undefined ? structuredClone(prev) : undefined;
      }
    }
    if (controlDomId && !(`__dom:${controlDomId}` in this.store.pendingSystemPrevious)) {
      const prevScalar = this.store.pendingSystemPrevious[keyStr];
      if (
        typeof prevScalar === "string" ||
        typeof prevScalar === "number" ||
        typeof prevScalar === "boolean"
      ) {
        this.store.pendingSystemPrevious[`__dom:${controlDomId}`] = prevScalar;
      }
    }

    const seq = ++this.editSeqCounter;
    this.systemKeySeqs.set(keyStr, seq);
    this.pendingSystemKeySeqs[keyStr] = seq;
    if (controlDomId) {
      this.systemKeySeqs.set(`__dom:${controlDomId}`, seq);
      this.pendingSystemKeySeqs[`__dom:${controlDomId}`] = seq;
    }

    this.store.pendingSystemPatch[keyStr] = value;
    if (this.store.state?.system_config) {
      this.store.state = {
        ...this.store.state,
        system_config: {
          ...this.store.state.system_config,
          [keyStr]: value,
        },
      };
    }

    if (this.store.systemSaveTimer) clearTimeout(this.store.systemSaveTimer);
    this.store.systemSaveTimer = setTimeout(() => {
      void this.flushSystemSettings();
    }, Math.max(0, debounceMs));
    this.store.host.requestUpdate();
  }

  flushSystemSettings(): Promise<void> {
    if (this.store.systemSaveTimer) {
      clearTimeout(this.store.systemSaveTimer);
      this.store.systemSaveTimer = null;
    }
    const patch = { ...this.store.pendingSystemPatch };
    const previousValues = { ...this.store.pendingSystemPrevious };
    const batchKeySeqs = { ...this.pendingSystemKeySeqs };
    this.store.pendingSystemPatch = {};
    this.store.pendingSystemPrevious = {};
    this.pendingSystemKeySeqs = {};

    if (Object.keys(patch).length === 0) return this.systemSaveChain;

    Object.assign(this.inFlightSystemPatch, patch);

    this.systemSaveChain = this.systemSaveChain.then(async () => {
      const clearOwnedInFlight = (): void => {
        for (const k of Object.keys(patch)) {
          if (this.systemKeySeqs.get(k) === batchKeySeqs[k]) {
            delete this.inFlightSystemPatch[k];
          }
        }
      };

      const expectedRev = this.store.state?.system_config_rev ?? 0;
      const reqPayload: Record<string, unknown> = { config: patch };
      if (expectedRev > 0) {
        reqPayload.expected_config_rev = expectedRev;
      }

      try {
        const res = await this.store.ws.runSystemCommand(
          "save_system_config",
          reqPayload,
          this.store.activeSubentryId || null,
        );
        clearOwnedInFlight();
        if (res) {
          this.store.ingestPayload(res, false);
        }
        this.store.announcePolite(this.store.t("shell.saved_status"));
      } catch (err) {
        clearOwnedInFlight();
        if (isConflictError(err)) {
          await this.store.refreshState();
          this.store.showToast(this.store.t("sync.conflict_reloaded"), true);
          return;
        }

        const controlRevert: Record<string, string | boolean> = {};
        if (this.store.state?.system_config) {
          const prevUiSys = this.store.state.system_config;
          const restored: Record<string, unknown> = {
            ...(prevUiSys as unknown as Record<string, unknown>),
          };
          for (const [k, v] of Object.entries(previousValues)) {
            if (k in batchKeySeqs && this.systemKeySeqs.get(k) !== batchKeySeqs[k]) continue;
            if (k.startsWith("__dom:")) {
              const domId = k.slice(6);
              controlRevert[domId] = typeof v === "boolean" ? v : String(v ?? "");
            } else if (v === undefined) {
              delete restored[k];
            } else {
              restored[k] = v;
            }
          }
          const newerSys = this.getEffectiveSystemPatch();
          Object.assign(restored, newerSys);
          const nextPayload: StudioStatePayload = {
            ...this.store.state,
            system_config: restored as unknown as SystemConfig,
          };
          overlayPendingBlankListSlots(this.store, nextPayload, prevUiSys);
          this.store.state = nextPayload;
        }
        if (Object.keys(controlRevert).length > 0) {
          this.store.mergeDomRevert(controlRevert);
        }
        this.store.showToast(
          formatWsError(err, this.store.t("sync.save_system_failed")),
          true,
        );
        this.store.host.requestUpdate();
      }
    });

    return this.systemSaveChain;
  }

  async flushAllPendingSettings(): Promise<void> {
    const tasks: Array<Promise<void>> = [];
    if (Object.keys(this.store.pendingSystemPatch).length > 0) {
      tasks.push(this.flushSystemSettings());
    }
    for (const subId of Array.from(this.store.pendingDeviceBuckets.keys())) {
      tasks.push(this.flushDeviceBucket(subId));
    }
    await Promise.allSettled(tasks);
  }
}
