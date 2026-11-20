/**
 * `store.entity` Controller (`EntityController`, `D-062`, `D-064`, `D-065`):
 * - Serialized System & per-Device `saveChain` queues with `inFlight` patch overlays (`B-08`)
 * - Monotonic per-key edit ownership so failed saves never clobber newer pending/in-flight edits (`B-09`)
 * - `expected_config_rev` optimistic concurrency with automatic `"conflict"` state resync (`D-064`)
 * - Optimistic ESPHome entity actions, unified `tokenListOps`, shortcuts, wallpapers, & 600 s camera signing (`D-065`)
 */

import { formatWsError, isConflictError } from "../api/ws-client.js";
import {
  ALLOWED_DEVICE_ACTIONS,
  DEVICE_PREF_SPECS_MAP,
  type DevicePrefSpecItem,
  GROUP_BEHAVIOR_NON_PREF_KEYS,
  GROUP_DISPLAY_NON_PREF_KEYS,
  GROUP_INTERFACE_NON_PREF_KEYS,
  MAX_DOCK_ITEMS,
  NATIVE_DOCK_APP_TOKENS,
} from "../constants.js";
import type {
  ConfigurableAppId,
  CustomPalette,
  DeviceCapabilities,
  DeviceConfig,
  DevicePrefItem,
  EspHomeEntityItem,
  PhotoItem,
  PhotoPoolMode,
  PhotoPoolTarget,
  ShortcutItem,
  StudioStatePayload,
  SystemConfig,
} from "../types.js";
import { isValidHexColor } from "../utils/format.js";
import {
  applyPhotoPickerModalOp,
  browseMediaFolderOp,
  bulkUpdatePhotosOp,
  closeMediaImportModalOp,
  closePhotoEditModalOp,
  closePhotoPickerModalOp,
  closePhotoUploadModalOp,
  createPhotoCollectionOp,
  createUploadCollectionOp,
  deletePhotoOp,
  importSelectedMediaOp,
  openMediaImportModalOp,
  openPhotoEditModalOp,
  openPhotoPickerModalOp,
  openPhotoUploadModalOp,
  removeStagedUploadOp,
  renamePhotoCollectionOp,
  requestBulkDeletePhotosOp,
  requestDeletePhotoCollectionOp,
  requestDeletePhotoOp,
  savePhotoEditModalOp,
  setDevicePhotoPoolOp,
  stageUploadFilesOp,
  uploadAllStagedPhotosOp,
} from "./photo-ops.js";
import {
  addRemoteGroupRowOp,
  addStringListRowOp,
  addVolumeOverrideRowOp,
  cleanPersistedStringList,
  createTokenListOps,
  defaultDockShortcutItems,
  isCatalogItemSupported,
  isProtectedNativeDockItem,
  isStringListKey,
  normalizeShortcutArray,
  openShortcutModalOp,
  overlayPendingBlankListSlots,
  removeRemoteGroupRowOp,
  removeStringListRowOp,
  removeVolumeOverrideRowOp,
  reorderStringListRowsOp,
  saveShortcutModalOp,
  STRING_LIST_MAX_ITEMS,
  type StringListKey,
  TOKEN_LIST_SPECS,
  type TokenListKey,
  type TokenListOps,
  toggleRemoteInGroupOp,
  updateRemoteGroupFieldOp,
  updateStringListRowOp,
  updateVolumeOverrideRowOp,
} from "./shortcuts-lists-ops.js";
import type { StudioStore } from "./store.js";

export {
  isCatalogItemSupported,
  isProtectedNativeDockItem,
  overlayPendingBlankListSlots,
  type StringListKey,
  type TokenListKey,
  type TokenListOps,
};

const SAVE_DEBOUNCE_MS = 220;
const ENTITY_OPTIMISTIC_TTL_MS = 8000;

export interface DevicePendingBucket {
  targetSubentryId: string;
  targetTitle: string;
  patch: Record<string, unknown>;
  previousValues: Record<string, unknown>;
  keySeqs: Record<string, number>;
  timer: ReturnType<typeof setTimeout> | null;
}

export interface PendingEntityEntry {
  state: string;
  previousValue?: string;
  expires: number;
}

const BEHAVIOR_NON_PREF_KEY_SET = new Set<string>(GROUP_BEHAVIOR_NON_PREF_KEYS);
const DISPLAY_NON_PREF_KEY_SET = new Set<string>(GROUP_DISPLAY_NON_PREF_KEYS);
const INTERFACE_NON_PREF_KEY_SET = new Set<string>(GROUP_INTERFACE_NON_PREF_KEYS);
const ALLOWED_DEVICE_ACTION_SET = new Set<string>(ALLOWED_DEVICE_ACTIONS);

function activeGroupKeySet(
  grp: { include_display?: boolean; include_interface?: boolean },
  devicePrefs: ReadonlyArray<{ key: string; group_tier?: string | null }>,
): Set<string> {
  const keys = new Set<string>(BEHAVIOR_NON_PREF_KEY_SET);
  for (const p of devicePrefs) {
    if (p.group_tier === "behavior") keys.add(p.key);
    else if (p.group_tier === "display" && grp.include_display) keys.add(p.key);
    else if (p.group_tier === "interface" && grp.include_interface) keys.add(p.key);
  }
  if (grp.include_display) {
    for (const k of DISPLAY_NON_PREF_KEY_SET) keys.add(k);
  }
  if (grp.include_interface) {
    for (const k of INTERFACE_NON_PREF_KEY_SET) keys.add(k);
  }
  return keys;
}

function sameGroupControlVal(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (
    Array.isArray(a) ||
    (a && typeof a === "object") ||
    Array.isArray(b) ||
    (b && typeof b === "object")
  ) {
    return JSON.stringify(a) === JSON.stringify(b);
  }
  return String(a) === String(b);
}

function expandDevicePrefPatch(
  currentCfg: Record<string, unknown>,
  rawPatch: Record<string, unknown>,
): Record<string, unknown> {
  const expanded: Record<string, unknown> = { ...rawPatch };
  if (rawPatch.home_screen_enabled === false) {
    const effStart = String(rawPatch.start_screen ?? currentCfg.start_screen ?? "Home");
    if (effStart === "Home") {
      expanded.start_screen = "Time App";
    }
  }
  return expanded;
}

export function overlayDevicePrefsOnSections(
  payload: StudioStatePayload,
  rawPatch: Record<string, unknown>,
): void {
  if (!rawPatch || Object.keys(rawPatch).length === 0) return;
  const curCfg = (payload.config || {}) as Record<string, unknown>;
  const expanded = expandDevicePrefPatch(curCfg, rawPatch);
  const groups = payload.device_groups || [];
  const devicePrefs = payload.device_prefs || [];
  const supportedPrefKeys = new Set(devicePrefs.map((p) => p.key));
  const isRoaming = curCfg.is_roaming !== false;

  if ("device_group" in rawPatch) {
    const targetGrpId = String(rawPatch.device_group || "custom").trim() || "custom";
    expanded.device_group = targetGrpId;
    if (targetGrpId !== "custom") {
      const grp = groups.find((g) => g.id === targetGrpId);
      if (grp?.device_config) {
        const enforcedKeys = activeGroupKeySet(grp, devicePrefs);
        for (const [gk, gv] of Object.entries(grp.device_config)) {
          if (gk in rawPatch || gv === undefined || gv === null) continue;
          if (!enforcedKeys.has(gk)) continue;
          if ((gk === "sync_device_area" || gk === "area_follow_dwell_s") && !isRoaming) continue;
          if (
            BEHAVIOR_NON_PREF_KEY_SET.has(gk) ||
            DISPLAY_NON_PREF_KEY_SET.has(gk) ||
            INTERFACE_NON_PREF_KEY_SET.has(gk) ||
            supportedPrefKeys.has(gk)
          ) {
            expanded[gk] = gv;
          }
        }
      }
    }
  } else {
    const curGrpId = String(curCfg.device_group || "custom").trim() || "custom";
    if (curGrpId !== "custom") {
      const grp = groups.find((g) => g.id === curGrpId);
      if (grp?.device_config) {
        const enforcedKeys = activeGroupKeySet(grp, devicePrefs);
        for (const [ek, ev] of Object.entries(expanded)) {
          if ((ek === "sync_device_area" || ek === "area_follow_dwell_s") && !isRoaming) continue;
          if (
            enforcedKeys.has(ek) &&
            grp.device_config[ek] !== undefined &&
            !sameGroupControlVal(grp.device_config[ek], ev)
          ) {
            expanded.device_group = "custom";
            break;
          }
        }
      }
    }
  }

  payload.config = {
    ...payload.config,
    ...expanded,
  };
  if ("device_group" in expanded && Array.isArray(payload.system_devices) && payload.subentry_id) {
    const nextGrp = String(expanded.device_group || "custom");
    const nextGrpName =
      nextGrp === "custom" ? "Custom" : groups.find((g) => g.id === nextGrp)?.name || nextGrp;
    payload.system_devices = payload.system_devices.map((d) =>
      d.subentry_id === payload.subentry_id
        ? { ...d, device_group: nextGrp, device_group_name: nextGrpName }
        : d,
    );
  }
  if (payload.device_prefs) {
    payload.device_prefs = payload.device_prefs.map((p) =>
      p.key in expanded ? { ...p, value: expanded[p.key] } : p,
    );
  }
  const sections = payload?.esphome?.sections;
  if (!sections) return;
  payload.esphome = {
    ...payload.esphome,
    sections: sections.map((sec) => ({
      ...sec,
      items: (sec.items || []).map((item) => {
        if (item.pref_key && item.pref_key in expanded) {
          const val = expanded[item.pref_key];
          const nextState = item.domain === "switch" ? (val ? "on" : "off") : String(val ?? "");
          return { ...item, state: nextState };
        }
        if (
          "volume_step_size" in expanded &&
          item.domain === "number" &&
          item.entity_id.startsWith("media_player.")
        ) {
          const stepNum = Number(expanded.volume_step_size);
          if (Number.isFinite(stepNum) && stepNum > 0) {
            return { ...item, step: stepNum };
          }
        }
        return item;
      }),
    })),
  };
}

export function overlayPendingEntityStates(
  payload: StudioStatePayload,
  pendingMap: Map<string, PendingEntityEntry>,
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

export class EntityController {
  private readonly store: StudioStore;

  private editSeqCounter = 0;
  private systemSaveChain: Promise<void> = Promise.resolve();
  private readonly inFlightSystemPatch: Record<string, unknown> = {};
  private readonly systemKeySeqs = new Map<string, number>();
  private pendingSystemKeySeqs: Record<string, number> = {};

  private readonly deviceSaveChains = new Map<string, Promise<void>>();
  private readonly inFlightDevicePatches = new Map<string, Record<string, unknown>>();
  private readonly deviceKeySeqs = new Map<string, Map<string, number>>();
  private readonly cameraPreviewCache = new Map<string, { url: string; expiresAtMs: number }>();

  readonly tokenLists: Readonly<Record<TokenListKey, TokenListOps>>;

  constructor(store: StudioStore) {
    this.store = store;
    this.tokenLists = {
      area_categories: createTokenListOps(store, TOKEN_LIST_SPECS.area_categories),
      home_categories: createTokenListOps(store, TOKEN_LIST_SPECS.home_categories),
      tools_items: createTokenListOps(store, TOKEN_LIST_SPECS.tools_items),
      games_items: createTokenListOps(store, TOKEN_LIST_SPECS.games_items),
      activity_sources: createTokenListOps(store, TOKEN_LIST_SPECS.activity_sources),
    };
  }

  isCatalogItemSupported(item: { capability?: string }, caps?: DeviceCapabilities): boolean {
    return isCatalogItemSupported(item, caps ?? this.store.state?.capabilities);
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

  // ---------- Device & System Settings Staging + Serialized Flushing ----------

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
    const snapshotKey = (k: string): void => {
      if (!(k in bucket.previousValues)) {
        bucket.previousValues[k] = curCfg[k];
      }
    };
    snapshotKey(key);
    snapshotKey("device_group");
    if (key === "home_screen_enabled") {
      snapshotKey("start_screen");
    }
    if (controlDomId && !(`__dom:${controlDomId}` in bucket.previousValues)) {
      bucket.previousValues[`__dom:${controlDomId}`] = bucket.previousValues[key];
    }

    const seq = ++this.editSeqCounter;
    const seqMap = this.getDeviceKeySeqMap(targetSubentryId);
    seqMap.set(key, seq);
    bucket.keySeqs[key] = seq;
    if (controlDomId) {
      seqMap.set(`__dom:${controlDomId}`, seq);
      bucket.keySeqs[`__dom:${controlDomId}`] = seq;
    }

    bucket.patch[key] = value;
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

    if (bucket.timer) clearTimeout(bucket.timer);
    bucket.timer = setTimeout(() => {
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
          void this.store.refreshState();
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
              restoredConfig[k] = v;
              if (v !== undefined) {
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
        if (this.store.activeSubentryId === targetSubentryId && Object.keys(controlRevert).length > 0) {
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
      const prev = (this.store.state?.system_config as unknown as Record<string, unknown>)?.[keyStr];
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
          void this.store.refreshState();
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
            } else if (v !== undefined) {
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

  // ---------- Device Preferences & ESPHome Entity Actions ----------

  getPref(key: string): DevicePrefItem | undefined {
    return (this.store.state?.device_prefs || []).find((p) => p.key === key);
  }

  getPrefs(keys?: readonly string[]): DevicePrefItem[] {
    const all = this.store.state?.device_prefs || [];
    if (!keys || keys.length === 0) return all;
    const keySet = new Set(keys);
    return all.filter((p) => keySet.has(p.key));
  }

  getPrefSpec(key: string): DevicePrefSpecItem | undefined {
    const fromPayload = this.store.state?.pref_specs?.find((s) => s.key === key);
    return fromPayload ?? DEVICE_PREF_SPECS_MAP[key];
  }

  getSectionItems(sectionId: string): EspHomeEntityItem[] {
    const sec = (this.store.state?.esphome?.sections || []).find((s) => s.id === sectionId);
    return sec?.items || [];
  }

  private currentEntityState(entityId: string): string {
    for (const sec of this.store.state?.esphome?.sections || []) {
      for (const it of sec.items || []) {
        if (it.entity_id === entityId) return it.state;
      }
    }
    return "";
  }

  private applyOptimisticEntity(entityId: string, nextState: string): string {
    const prev = this.currentEntityState(entityId);
    this.store.pendingEntityStates.set(entityId, {
      state: nextState,
      previousValue: prev,
      expires: Date.now() + ENTITY_OPTIMISTIC_TTL_MS,
    });
    if (this.store.state?.esphome?.sections) {
      const nextPayload: StudioStatePayload = { ...this.store.state };
      overlayPendingEntityStates(nextPayload, this.store.pendingEntityStates);
      this.store.state = nextPayload;
      this.store.host.requestUpdate();
    }
    return prev;
  }

  private rollbackOptimisticEntity(entityId: string, prev: string): void {
    this.store.pendingEntityStates.delete(entityId);
    if (this.store.state?.esphome?.sections) {
      this.store.state = {
        ...this.store.state,
        esphome: {
          ...this.store.state.esphome,
          sections: this.store.state.esphome.sections.map((sec) => ({
            ...sec,
            items: (sec.items || []).map((it) =>
              it.entity_id === entityId ? { ...it, state: prev } : it,
            ),
          })),
        },
      };
    }
    this.store.host.requestUpdate();
  }

  async executeEntityAction(
    entityId: string,
    optimisticState: string | undefined,
    body: Record<string, unknown>,
    errorPrefix: string,
  ): Promise<boolean> {
    const targetSubentryId = this.store.activeSubentryId;
    if (!targetSubentryId || !entityId) return false;
    const prev =
      optimisticState !== undefined ? this.applyOptimisticEntity(entityId, optimisticState) : "";
    try {
      const res = await this.store.ws.runDeviceCommand(targetSubentryId, "esphome_entity_action", {
        entity_id: entityId,
        ...body,
      });
      if (res && this.store.activeSubentryId === targetSubentryId) {
        this.store.ingestPayload(res, false);
      }
      return true;
    } catch (err) {
      if (optimisticState !== undefined) this.rollbackOptimisticEntity(entityId, prev);
      this.store.showToast(formatWsError(err, errorPrefix), true);
      return false;
    }
  }

  async espAction(
    entityId: string,
    action: string,
    optimisticState?: string,
    toastMessage?: string,
  ): Promise<boolean> {
    const ok = await this.executeEntityAction(
      entityId,
      optimisticState,
      { action },
      "Device action failed",
    );
    if (ok && toastMessage) {
      this.store.showToast(toastMessage);
    }
    return ok;
  }

  async espSelect(entityId: string, option: string): Promise<void> {
    await this.executeEntityAction(entityId, option, { option }, "Could not update option");
  }

  async espNumber(entityId: string, level: number): Promise<void> {
    if (!Number.isFinite(level)) return;
    await this.executeEntityAction(
      entityId,
      String(level),
      { level },
      "Could not update level",
    );
  }

  async runDeviceAction(action: string, toastMessage?: string): Promise<boolean> {
    const targetSubentryId = this.store.activeSubentryId;
    const cleanAction = String(action || "").trim().toLowerCase();
    if (!targetSubentryId || !cleanAction) return false;
    if (!ALLOWED_DEVICE_ACTION_SET.has(cleanAction)) {
      this.store.showToast(`Unsupported Device action: ${cleanAction}`, true);
      return false;
    }
    try {
      const res = await this.store.ws.runDeviceCommand(targetSubentryId, "device_action", {
        action: cleanAction,
      });
      if (res && this.store.activeSubentryId === targetSubentryId) {
        this.store.ingestPayload(res, false);
      }
      if (toastMessage) {
        this.store.showToast(toastMessage);
      }
      return true;
    } catch (err) {
      this.store.showToast(formatWsError(err, "Device action failed"), true);
      return false;
    }
  }

  async triggerHeaderFirmwareUpdate(): Promise<void> {
    const updEntity = this.store.state?.live?.fw_update_entity || "";
    if (!updEntity) return;
    if (await this.espAction(updEntity, "install")) {
      this.store.showToast("Firmware update started");
    }
  }

  // ---------- Token Lists (Area, Home, Tools, Games, Activity Sources) ----------

  getEnabledAreaCategories(): string[] {
    return this.tokenLists.area_categories.getEnabled();
  }
  toggleAreaCategoryToken(token: string, forceEnabled?: boolean): void {
    this.tokenLists.area_categories.toggle(token, forceEnabled);
  }
  moveAreaCategoryToken(token: string, delta: -1 | 1): void {
    this.tokenLists.area_categories.move(token, delta);
  }
  reorderAreaCategories(fromIndex: number, toIndex: number): void {
    this.tokenLists.area_categories.reorder(fromIndex, toIndex);
  }

  getEnabledHomeCategories(): string[] {
    return this.tokenLists.home_categories.getEnabled();
  }
  toggleHomeCategoryToken(token: string, forceEnabled?: boolean): void {
    this.tokenLists.home_categories.toggle(token, forceEnabled);
  }
  moveHomeCategoryToken(token: string, delta: -1 | 1): void {
    this.tokenLists.home_categories.move(token, delta);
  }
  reorderHomeCategories(fromIndex: number, toIndex: number): void {
    this.tokenLists.home_categories.reorder(fromIndex, toIndex);
  }

  getEnabledToolsItems(): string[] {
    return this.tokenLists.tools_items.getEnabled();
  }
  toggleToolItemToken(token: string, forceEnabled?: boolean): void {
    this.tokenLists.tools_items.toggle(token, forceEnabled);
  }
  moveToolItemToken(token: string, delta: -1 | 1): void {
    this.tokenLists.tools_items.move(token, delta);
  }
  reorderToolsItems(fromIndex: number, toIndex: number): void {
    this.tokenLists.tools_items.reorder(fromIndex, toIndex);
  }

  getEnabledGamesItems(): string[] {
    return this.tokenLists.games_items.getEnabled();
  }
  toggleGameItemToken(token: string, forceEnabled?: boolean): void {
    this.tokenLists.games_items.toggle(token, forceEnabled);
  }
  moveGameItemToken(token: string, delta: -1 | 1): void {
    this.tokenLists.games_items.move(token, delta);
  }
  reorderGamesItems(fromIndex: number, toIndex: number): void {
    this.tokenLists.games_items.reorder(fromIndex, toIndex);
  }

  getEnabledActivitySources(): string[] {
    return this.tokenLists.activity_sources.getEnabled();
  }
  toggleActivitySource(sourceId: string, forceEnabled?: boolean): void {
    this.tokenLists.activity_sources.toggle(sourceId, forceEnabled);
  }
  reorderActivitySources(fromIndex: number, toIndex: number): void {
    this.tokenLists.activity_sources.reorder(fromIndex, toIndex);
  }

  // ---------- Per-Device Cameras Visibility & Carousel Lists ----------

  getSystemCameraEntities(): string[] {
    const out: string[] = [];
    for (const raw of this.store.state?.system_config?.camera_entities || []) {
      const id = String(raw || "").trim();
      if (id && !out.includes(id)) {
        out.push(id);
      }
    }
    return out;
  }

  getVisibleCameras(): string[] {
    const sys = this.getSystemCameraEntities();
    if (sys.length === 0) return [];
    const raw = this.store.state?.config?.camera_visible_entities;
    if (!Array.isArray(raw) || raw.length === 0) {
      return [...sys];
    }
    const filtered: string[] = [];
    for (const item of raw) {
      const id = String(item || "").trim();
      if (id && sys.includes(id) && !filtered.includes(id)) {
        filtered.push(id);
      }
    }
    return filtered.length > 0 ? filtered : [...sys];
  }

  toggleVisibleCamera(entityId: string, forceEnabled?: boolean): void {
    const cleanId = String(entityId || "").trim();
    const sys = this.getSystemCameraEntities();
    if (!cleanId || !sys.includes(cleanId)) return;
    const current = this.getVisibleCameras();
    const idx = current.indexOf(cleanId);
    const currentlyOn = idx >= 0;
    const wantOn = forceEnabled !== undefined ? Boolean(forceEnabled) : !currentlyOn;
    if (wantOn === currentlyOn) return;

    let next: string[];
    if (!wantOn) {
      if (current.length <= 1) {
        this.store.showToast(this.store.t("common.keep_one_enabled", { noun: "camera" }), true);
        return;
      }
      next = current.filter((id) => id !== cleanId);
    } else {
      next = [...current, cleanId];
    }
    const sameAsSys = next.length === sys.length && next.every((id, i) => id === sys[i]);
    this.stageDeviceSetting("camera_visible_entities", sameAsSys ? [] : next);

    if (!wantOn) {
      const rawCarousel = Array.isArray(this.store.state?.config?.camera_carousel_entities)
        ? this.store.state.config.camera_carousel_entities
            .map((c) => String(c || "").trim())
            .filter(Boolean)
        : [];
      if (rawCarousel.length > 0 && rawCarousel.includes(cleanId)) {
        const pruned = rawCarousel.filter((id) => next.includes(id));
        const sameAsVisible =
          pruned.length === next.length && pruned.every((id, i) => id === next[i]);
        this.stageDeviceSetting(
          "camera_carousel_entities",
          pruned.length === 0 || sameAsVisible ? [] : pruned,
        );
      }
    }
  }

  reorderVisibleCameras(fromIndex: number, toIndex: number): void {
    const sys = this.getSystemCameraEntities();
    const current = this.getVisibleCameras();
    if (
      fromIndex < 0 ||
      toIndex < 0 ||
      fromIndex >= current.length ||
      toIndex >= current.length ||
      fromIndex === toIndex
    ) {
      return;
    }
    const next = [...current];
    const [moved] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    const sameAsSys = next.length === sys.length && next.every((id, i) => id === sys[i]);
    this.stageDeviceSetting("camera_visible_entities", sameAsSys ? [] : next);
  }

  getCarouselCameras(): string[] {
    const visible = this.getVisibleCameras();
    if (visible.length === 0) return [];
    const raw = this.store.state?.config?.camera_carousel_entities;
    if (!Array.isArray(raw) || raw.length === 0) {
      return [...visible];
    }
    const filtered: string[] = [];
    for (const item of raw) {
      const id = String(item || "").trim();
      if (id && visible.includes(id) && !filtered.includes(id)) {
        filtered.push(id);
      }
    }
    return filtered.length > 0 ? filtered : [...visible];
  }

  toggleCarouselCamera(entityId: string, forceEnabled?: boolean): void {
    const cleanId = String(entityId || "").trim();
    const visible = this.getVisibleCameras();
    if (!cleanId || !visible.includes(cleanId)) return;
    const current = this.getCarouselCameras();
    const idx = current.indexOf(cleanId);
    const currentlyOn = idx >= 0;
    const wantOn = forceEnabled !== undefined ? Boolean(forceEnabled) : !currentlyOn;
    if (wantOn === currentlyOn) return;

    let next: string[];
    if (!wantOn) {
      if (current.length <= 1) {
        this.store.showToast(this.store.t("common.keep_one_enabled", { noun: "camera" }), true);
        return;
      }
      next = current.filter((id) => id !== cleanId);
    } else {
      next = [...current, cleanId];
    }
    const sameAsVisible =
      next.length === visible.length && next.every((id, i) => id === visible[i]);
    this.stageDeviceSetting("camera_carousel_entities", sameAsVisible ? [] : next);
  }

  reorderCarouselCameras(fromIndex: number, toIndex: number): void {
    const visible = this.getVisibleCameras();
    const current = this.getCarouselCameras();
    if (
      fromIndex < 0 ||
      toIndex < 0 ||
      fromIndex >= current.length ||
      toIndex >= current.length ||
      fromIndex === toIndex
    ) {
      return;
    }
    const next = [...current];
    const [moved] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    const sameAsVisible =
      next.length === visible.length && next.every((id, i) => id === visible[i]);
    this.stageDeviceSetting("camera_carousel_entities", sameAsVisible ? [] : next);
  }

  // ---------- Shortcuts (`dock_items` & `pinned_items`) + App Config Modal ----------

  getDockItems(): ShortcutItem[] {
    const raw = this.store.state?.config?.dock_items;
    if (raw === undefined || raw === null) {
      return defaultDockShortcutItems();
    }
    return normalizeShortcutArray(raw, true);
  }

  getPinnedItems(): ShortcutItem[] {
    const raw = this.store.state?.config?.pinned_items;
    if (raw === undefined || raw === null) {
      return [];
    }
    return normalizeShortcutArray(raw, false);
  }

  moveShortcutItem(listKey: "dock_items" | "pinned_items", idx: number, delta: -1 | 1): void {
    this.reorderShortcutItems(listKey, idx, idx + delta);
  }

  reorderShortcutItems(
    listKey: "dock_items" | "pinned_items",
    fromIndex: number,
    toIndex: number,
  ): void {
    const current = listKey === "dock_items" ? this.getDockItems() : this.getPinnedItems();
    if (
      fromIndex < 0 ||
      toIndex < 0 ||
      fromIndex >= current.length ||
      toIndex >= current.length ||
      fromIndex === toIndex
    ) {
      return;
    }
    const next = current.map((it) => ({ ...it }));
    const [moved] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, moved);
    this.stageDeviceSetting(listKey, next);
  }

  removeShortcutItem(listKey: "dock_items" | "pinned_items", idx: number): void {
    const current = listKey === "dock_items" ? this.getDockItems() : this.getPinnedItems();
    if (idx < 0 || idx >= current.length) return;
    const next = current.filter((_, i) => i !== idx).map((it) => ({ ...it }));
    this.stageDeviceSetting(listKey, next);
  }

  resetDockItemsToDefault(): void {
    this.stageDeviceSetting("dock_items", defaultDockShortcutItems());
    this.store.showToast("Restored default App Dock");
  }

  requestResetDockItems(): void {
    this.store.openConfirm({
      kind: "reset_dock",
      title: this.store.t("confirm.reset_dock.title"),
      consequence: this.store.t("confirm.reset_dock.body"),
      confirmLabel: this.store.t("confirm.reset_dock.confirm"),
      danger: true,
      blastRadiusCount: 1,
      onConfirm: () => {
        this.resetDockItemsToDefault();
      },
    });
  }

  toggleNativeDockApp(routeToken: string, enabled: boolean): void {
    const target = String(routeToken || "").trim().toLowerCase();
    if (!NATIVE_DOCK_APP_TOKENS.includes(target)) return;
    const current = this.getDockItems().map((it) => ({ ...it }));
    if (!enabled) {
      const next = current.filter((it) => !(it.kind === "route" && it.target === target));
      this.stageDeviceSetting("dock_items", next);
      return;
    }
    if (current.some((it) => it.kind === "route" && it.target === target)) {
      return;
    }
    if (current.length >= MAX_DOCK_ITEMS) {
      this.store.showToast(`App Dock supports up to ${MAX_DOCK_ITEMS} shortcuts`, true);
      return;
    }
    current.push({
      kind: "route",
      target,
      action: "",
      label: "",
      icon: "",
      confirm: false,
    });
    this.stageDeviceSetting("dock_items", current);
  }

  openAppConfigModal(app: ConfigurableAppId): void {
    this.store.returnToPinnedModal = false;
    if (this.store.shortcutModal.open) {
      this.store.shortcutModal = { ...this.store.shortcutModal, open: false };
    }
    this.store.appConfigModal = { open: true, app };
    this.store.host.requestUpdate();
  }

  closeAppConfigModal(): void {
    this.store.appConfigModal = { open: false, app: null };
    this.store.host.requestUpdate();
  }

  openShortcutModal(
    listKey: "dock_items" | "pinned_items",
    editIndex: number | null = null,
  ): void {
    openShortcutModalOp(this.store, listKey, editIndex);
  }

  closeShortcutModal(): void {
    const reopenPinned = this.store.returnToPinnedModal;
    this.store.returnToPinnedModal = false;
    this.store.shortcutModal = { ...this.store.shortcutModal, open: false };
    if (reopenPinned) {
      this.store.appConfigModal = { open: true, app: "pinned" };
    }
    this.store.host.requestUpdate();
  }

  saveShortcutModal(): void {
    saveShortcutModalOp(this.store);
  }

  // ---------- Colors, Photo Library, Media Import & Device Photo Pools ----------

  applyDeviceCustomColor(hex: string, switchColorProfile = true): void {
    if (!isValidHexColor(hex)) return;
    this.stageDeviceSetting("device_custom_color", hex.toUpperCase());
    if (switchColorProfile) {
      this.stageDeviceSetting("color_profile", "Custom");
    }
  }

  deleteCustomPalette(hex: string): void {
    const target = hex.toUpperCase();
    const next: CustomPalette[] = (this.store.state?.system_config?.custom_palettes || []).filter(
      (p) => p.hex.toUpperCase() !== target,
    );
    this.stageSystemSetting("custom_palettes", next);
  }

  openPhotoUploadModal(options?: {
    defaultCollectionId?: string;
    onComplete?: (uploadedIds: string[]) => void;
  }): void {
    openPhotoUploadModalOp(this.store, options);
  }

  closePhotoUploadModal(): void {
    closePhotoUploadModalOp(this.store);
  }

  stageUploadFiles(fileList: FileList | readonly File[]): void {
    stageUploadFilesOp(this.store, fileList);
  }

  removeStagedUpload(index: number): void {
    removeStagedUploadOp(this.store, index);
  }

  async uploadAllStagedPhotos(): Promise<void> {
    await uploadAllStagedPhotosOp(this.store);
  }

  openPhotoEditModal(photo: PhotoItem): void {
    openPhotoEditModalOp(this.store, photo);
  }

  closePhotoEditModal(): void {
    closePhotoEditModalOp(this.store);
  }

  async savePhotoEditModal(): Promise<void> {
    await savePhotoEditModalOp(this.store);
  }

  async createPhotoCollection(name: string): Promise<string | null> {
    return createPhotoCollectionOp(this.store, name);
  }

  async createUploadCollection(): Promise<string | null> {
    return createUploadCollectionOp(this.store);
  }

  async renamePhotoCollection(collectionId: string, name: string): Promise<void> {
    await renamePhotoCollectionOp(this.store, collectionId, name);
  }

  requestDeletePhotoCollection(collectionId: string, name: string): void {
    requestDeletePhotoCollectionOp(this.store, collectionId, name);
  }

  async deletePhoto(photoId: string): Promise<void> {
    await deletePhotoOp(this.store, photoId);
  }

  requestDeletePhoto(photoId: string, name?: string): void {
    requestDeletePhotoOp(this.store, photoId, name);
  }

  async bulkUpdatePhotos(options: {
    addCollection?: string;
    removeCollection?: string;
    deletePhotos?: boolean;
  }): Promise<void> {
    await bulkUpdatePhotosOp(this.store, options);
  }

  requestBulkDeletePhotos(): void {
    requestBulkDeletePhotosOp(this.store);
  }

  openMediaImportModal(): void {
    openMediaImportModalOp(this.store);
  }

  closeMediaImportModal(): void {
    closeMediaImportModalOp(this.store);
  }

  async browseMediaFolder(root?: string, subpath?: string): Promise<void> {
    await browseMediaFolderOp(this.store, root, subpath);
  }

  async importSelectedMedia(): Promise<void> {
    await importSelectedMediaOp(this.store);
  }

  openPhotoPickerModal(target: PhotoPoolTarget): void {
    openPhotoPickerModalOp(this.store, target);
  }

  closePhotoPickerModal(): void {
    closePhotoPickerModalOp(this.store);
  }

  async applyPhotoPickerModal(): Promise<void> {
    await applyPhotoPickerModalOp(this.store);
  }

  async setDevicePhotoPool(
    options: {
      target: PhotoPoolTarget;
      mode: PhotoPoolMode;
      sourceId?: string;
      collectionId?: string;
      photoIds?: readonly string[];
      cycleMinutes?: number;
      shuffle?: boolean;
    },
    toastMessage?: string,
  ): Promise<boolean> {
    return setDevicePhotoPoolOp(this.store, options, toastMessage);
  }

  async setWallpaperRotation(minutes: number): Promise<void> {
    const cfg = this.store.state?.config || {};
    const cleanMins = Math.max(0, Math.round(Number(minutes) || 0));
    const mode = String(cfg.wallpaper_mode || "off") as PhotoPoolMode;
    await setDevicePhotoPoolOp(this.store, {
      target: "wallpaper",
      mode,
      sourceId: String(cfg.wallpaper_source || ""),
      collectionId: String(cfg.wallpaper_collection || ""),
      photoIds: Array.isArray(cfg.wallpaper_favorites) ? cfg.wallpaper_favorites : [],
      cycleMinutes: cleanMins,
    });
  }

  async setScreensaverRotation(minutes: number, shuffle?: boolean): Promise<void> {
    const cfg = this.store.state?.config || {};
    const cleanMins = Math.max(0, Math.round(Number(minutes) || 0));
    const mode = String(cfg.screensaver_photo_mode || "off") as PhotoPoolMode;
    await setDevicePhotoPoolOp(this.store, {
      target: "screensaver",
      mode,
      sourceId: String(cfg.screensaver_photo_source || ""),
      collectionId: String(cfg.screensaver_photo_collection || ""),
      photoIds: Array.isArray(cfg.screensaver_photo_ids) ? cfg.screensaver_photo_ids : [],
      cycleMinutes: cleanMins,
      shuffle: shuffle !== undefined ? shuffle : Boolean(cfg.screensaver_shuffle),
    });
  }

  // ---------- System String Lists, Volume Overrides, Remote Groups & Camera Preview ----------

  updateStringListRow(key: StringListKey, index: number, value: string): void {
    updateStringListRowOp(this.store, key, index, value);
  }

  addStringListRow(key: StringListKey, defaultEntity = "", maxLen?: number): void {
    addStringListRowOp(this.store, key, defaultEntity, maxLen);
  }

  removeStringListRow(key: StringListKey, index: number): void {
    removeStringListRowOp(this.store, key, index);
  }

  moveStringListRow(key: StringListKey, index: number, direction: -1 | 1): void {
    reorderStringListRowsOp(this.store, key, index, index + direction);
  }

  reorderStringListRows(key: StringListKey, fromIndex: number, toIndex: number): void {
    reorderStringListRowsOp(this.store, key, fromIndex, toIndex);
  }

  addVolumeOverrideRow(): void {
    addVolumeOverrideRowOp(this.store);
  }

  updateVolumeOverrideRow(index: number, field: "speaker" | "target", value: string): void {
    updateVolumeOverrideRowOp(this.store, index, field, value);
  }

  removeVolumeOverrideRow(index: number): void {
    removeVolumeOverrideRowOp(this.store, index);
  }

  addRemoteGroupRow(): void {
    addRemoteGroupRowOp(this.store);
  }

  updateRemoteGroupField(groupId: string, field: "name" | "area_id", value: string): void {
    updateRemoteGroupFieldOp(this.store, groupId, field, value);
  }

  toggleRemoteInGroup(groupId: string, remoteEntity: string): void {
    toggleRemoteInGroupOp(this.store, groupId, remoteEntity);
  }

  removeRemoteGroupRow(groupId: string): void {
    removeRemoteGroupRowOp(this.store, groupId);
  }

  clearCameraPreviewCache(): void {
    this.cameraPreviewCache.clear();
  }

  async previewCamera(cameraEntity: string, bustCache = false): Promise<void> {
    const cleanEntity = String(cameraEntity || "").trim();
    if (!cleanEntity) {
      this.closeCameraPreview();
      return;
    }
    const now = Date.now();
    const cached = this.cameraPreviewCache.get(cleanEntity);
    if (!bustCache && cached && cached.expiresAtMs > now) {
      this.store.activeCameraPreviewEntity = cleanEntity;
      this.store.cameraPreviewUrl = cached.url;
      this.store.host.requestUpdate();
      return;
    }
    try {
      const minted = await this.store.ws.mintCameraPreviewUrl(cleanEntity);
      const ttlSec = Math.max(30, Number(minted.expires_in || 600) - 30);
      this.cameraPreviewCache.set(cleanEntity, {
        url: minted.preview_url,
        expiresAtMs: now + ttlSec * 1000,
      });
      const sep = minted.preview_url.includes("?") ? "&" : "?";
      this.store.activeCameraPreviewEntity = cleanEntity;
      this.store.cameraPreviewUrl = bustCache
        ? `${minted.preview_url}${sep}_ts=${now}`
        : minted.preview_url;
      this.store.host.requestUpdate();
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not load camera preview"), true);
    }
  }

  closeCameraPreview(): void {
    this.store.activeCameraPreviewEntity = "";
    this.store.cameraPreviewUrl = "";
    this.store.host.requestUpdate();
  }

  async testDoorbellSpeaker(): Promise<void> {
    const cams = (this.store.state?.system_config?.camera_entities || [])
      .map((c) => String(c || "").trim())
      .filter(Boolean);
    if (!cams[0]) {
      this.store.showToast("Add a camera in Shared entities first", true);
      return;
    }
    if (!this.store.doorbellTestSubentryId) {
      this.store.showToast("Choose a Device to test from", true);
      return;
    }
    const message = this.store.doorbellTestReply.trim() || "Testing Latter doorbell audio.";
    await this.flushSystemSettings();
    try {
      const res = await this.store.ws.runSystemCommand(
        "test_doorbell_speaker",
        {
          subentry_id: this.store.doorbellTestSubentryId,
          camera_entity: cams[0],
          message,
        },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Played test message on door speaker");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Door speaker test failed"), true);
    }
  }
}
