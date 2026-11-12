/**
 * Device & System configuration staging, optimistic ESPHome entity actions,
 * dock/activity/wallpaper/color mutations, and shared-entity list editors.
 */

import { formatWsError } from "../api/ws-client.js";
import { ACTIVITY_SOURCES_CATALOG, DOCK_APPS_CATALOG } from "../constants.js";
import type {
  CustomPalette,
  DeviceConfig,
  RemoteGroup,
  StudioScope,
  StudioStatePayload,
  SystemConfig,
  VolumeOverride,
} from "../types.js";
import { isValidHexColor } from "../utils/format.js";
import type { StudioStore } from "./store.js";

export interface DevicePendingBucket {
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
): Promise<boolean> {
  return store.executeEntityAction(entityId, optimisticState, body, errorPrefix);
}

export function stageDeviceSettingOp(
  store: StudioStore,
  key: keyof DeviceConfig,
  value: unknown,
  controlDomId?: string,
): void {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;

  let bucket = store.pendingDeviceBuckets.get(targetSubentryId);
  if (!bucket) {
    bucket = {
      targetSubentryId,
      patch: {},
      previousValues: {},
      timer: null,
    };
    store.pendingDeviceBuckets.set(targetSubentryId, bucket);
  }

  if (!(key in bucket.previousValues)) {
    const prev =
      store.state && store.state.subentry_id === targetSubentryId
        ? (store.state.config as Record<string, unknown>)?.[key]
        : undefined;
    bucket.previousValues[key] = prev;
  }
  if (controlDomId) {
    bucket.previousValues[`__dom:${controlDomId}`] = bucket.previousValues[key];
  }

  bucket.patch[key] = value;
  if (store.state) {
    const nextSystemDevices =
      key === "device_remote_group" && Array.isArray(store.state.system_devices)
        ? store.state.system_devices.map((d) =>
            d.subentry_id === targetSubentryId
              ? { ...d, device_remote_group: String(value || "area_auto") }
              : d,
          )
        : store.state.system_devices;
    store.state = {
      ...store.state,
      system_devices: nextSystemDevices,
      config:
        store.state.subentry_id === targetSubentryId
          ? {
              ...store.state.config,
              [key]: value,
            }
          : store.state.config,
    };
  }

  if (bucket.timer) clearTimeout(bucket.timer);
  bucket.timer = setTimeout(() => {
    void store.flushDeviceBucket(targetSubentryId);
  }, SAVE_DEBOUNCE_MS);
  store.host.requestUpdate();
}

export async function flushDeviceBucketOp(store: StudioStore, targetSubentryId: string): Promise<void> {
  const bucket = store.pendingDeviceBuckets.get(targetSubentryId);
  if (!bucket) return;
  if (bucket.timer) {
    clearTimeout(bucket.timer);
    bucket.timer = null;
  }
  const patch = { ...bucket.patch };
  const previousValues = { ...bucket.previousValues };
  store.pendingDeviceBuckets.delete(targetSubentryId);

  if (Object.keys(patch).length === 0) return;

  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "save_device_config", {
      config: patch,
    });
    if (res) {
      if (store.activeSubentryId === targetSubentryId) {
        store.ingestPayload(res, false);
      } else if (store.state && Array.isArray(res.system_devices)) {
        store.state = {
          ...store.state,
          system_devices: res.system_devices,
          issues: res.issues ?? store.state.issues,
        };
        store.host.requestUpdate();
      }
    }
    store.showToast("Saved");
  } catch (err) {
    const controlRevert: Record<string, string | boolean> = {};
    for (const [k, v] of Object.entries(previousValues)) {
      if (k.startsWith("__dom:")) {
        const domId = k.slice(6);
        if (typeof v === "boolean") controlRevert[domId] = v;
        else if (v !== undefined && v !== null) controlRevert[domId] = String(v);
        else controlRevert[domId] = "";
      }
    }
    if (store.state) {
      const nextSystemDevices =
        "device_remote_group" in previousValues && Array.isArray(store.state.system_devices)
          ? store.state.system_devices.map((d) =>
              d.subentry_id === targetSubentryId
                ? {
                    ...d,
                    device_remote_group: String(previousValues.device_remote_group || "area_auto"),
                  }
                : d,
            )
          : store.state.system_devices;
      if (store.state.subentry_id === targetSubentryId) {
        const restoredConfig: Record<string, unknown> = {
          ...(store.state.config as Record<string, unknown>),
        };
        for (const [k, v] of Object.entries(previousValues)) {
          if (!k.startsWith("__dom:")) {
            restoredConfig[k] = v;
          }
        }
        store.state = {
          ...store.state,
          system_devices: nextSystemDevices,
          config: restoredConfig as DeviceConfig,
        };
      } else if (nextSystemDevices !== store.state.system_devices) {
        store.state = {
          ...store.state,
          system_devices: nextSystemDevices,
        };
      }
    }
    if (Object.keys(controlRevert).length > 0) {
      store.pendingDomRevert = { controlIds: controlRevert };
    }
    store.showToast(formatWsError(err, "Could not save Device settings"), true);
    store.host.requestUpdate();
  }
}

export function stageSystemSettingOp(
  store: StudioStore,
  key: keyof SystemConfig,
  value: unknown,
  controlDomId?: string,
): void {
  if (!(key in store.pendingSystemPrevious)) {
    const prev = (store.state?.system_config as unknown as Record<string, unknown>)?.[key];
    store.pendingSystemPrevious[key] = prev !== undefined ? structuredClone(prev) : undefined;
  }
  if (controlDomId && !(`__dom:${controlDomId}` in store.pendingSystemPrevious)) {
    const prevScalar = store.pendingSystemPrevious[key];
    if (typeof prevScalar === "string" || typeof prevScalar === "number" || typeof prevScalar === "boolean") {
      store.pendingSystemPrevious[`__dom:${controlDomId}`] = prevScalar;
    }
  }

  store.pendingSystemPatch[key] = value;
  if (store.state?.system_config) {
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: value,
      },
    };
  }

  if (store.systemSaveTimer) clearTimeout(store.systemSaveTimer);
  store.systemSaveTimer = setTimeout(() => {
    void store.flushSystemSettings();
  }, SAVE_DEBOUNCE_MS);
  store.host.requestUpdate();
}

export async function flushSystemSettingsOp(store: StudioStore): Promise<void> {
  if (store.systemSaveTimer) {
    clearTimeout(store.systemSaveTimer);
    store.systemSaveTimer = null;
  }
  const patch = { ...store.pendingSystemPatch };
  const previousValues = { ...store.pendingSystemPrevious };
  store.pendingSystemPatch = {};
  store.pendingSystemPrevious = {};

  if (Object.keys(patch).length === 0) return;

  try {
    const res = await store.ws.runSystemCommand(
      "save_system_config",
      { config: patch },
      store.activeSubentryId || null,
    );
    if (res) {
      store.ingestPayload(res, false);
    }
    store.showToast("Saved System settings");
  } catch (err) {
    const controlRevert: Record<string, string | boolean> = {};
    if (store.state?.system_config) {
      const restored: Record<string, unknown> = {
        ...(store.state.system_config as unknown as Record<string, unknown>),
      };
      for (const [k, v] of Object.entries(previousValues)) {
        if (k.startsWith("__dom:")) {
          const domId = k.slice(6);
          controlRevert[domId] = typeof v === "boolean" ? v : String(v ?? "");
        } else if (v !== undefined) {
          restored[k] = v;
        }
      }
      store.state = {
        ...store.state,
        system_config: restored as unknown as SystemConfig,
      };
    }
    if (Object.keys(controlRevert).length > 0) {
      store.pendingDomRevert = { controlIds: controlRevert };
    }
    store.showToast(formatWsError(err, "Could not save System settings"), true);
    store.host.requestUpdate();
  }
}

function currentEntityState(store: StudioStore, entityId: string): string {
  for (const sec of store.state?.esphome?.sections || []) {
    for (const it of sec.items || []) {
      if (it.entity_id === entityId) return it.state;
    }
  }
  return "";
}

function applyOptimisticEntity(store: StudioStore, entityId: string, nextState: string): string {
  const prev = currentEntityState(store, entityId);
  store.pendingEntityStates.set(entityId, {
    state: nextState,
    previousValue: prev,
    expires: Date.now() + ENTITY_OPTIMISTIC_TTL_MS,
  });
  if (store.state?.esphome?.sections) {
    const nextPayload: StudioStatePayload = { ...store.state };
    overlayPendingEntityStates(nextPayload, store.pendingEntityStates);
    store.state = nextPayload;
    store.host.requestUpdate();
  }
  return prev;
}

function rollbackOptimisticEntity(store: StudioStore, entityId: string, prev: string): void {
  store.pendingEntityStates.delete(entityId);
  if (store.state?.esphome?.sections) {
    store.state = {
      ...store.state,
      esphome: {
        ...store.state.esphome,
        sections: store.state.esphome.sections.map((sec) => ({
          ...sec,
          items: (sec.items || []).map((it) => (it.entity_id === entityId ? { ...it, state: prev } : it)),
        })),
      },
    };
  }
  store.host.requestUpdate();
}

export async function executeEntityActionOp(
  store: StudioStore,
  entityId: string,
  optimisticState: string | undefined,
  body: Record<string, unknown>,
  errorPrefix: string,
): Promise<boolean> {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId || !entityId) return false;
  const prev = optimisticState !== undefined ? applyOptimisticEntity(store, entityId, optimisticState) : "";
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "esphome_entity_action", {
      entity_id: entityId,
      ...body,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    return true;
  } catch (err) {
    if (optimisticState !== undefined) rollbackOptimisticEntity(store, entityId, prev);
    store.showToast(formatWsError(err, errorPrefix), true);
    return false;
  }
}

export function getEnabledDockTokensOp(store: StudioStore): string[] {
  const raw = String(store.state?.config?.dock_apps ?? "");
  if (!raw.trim()) {
    return DOCK_APPS_CATALOG.map((a) => a.token);
  }
  return raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function toggleDockAppTokenOp(store: StudioStore, appId: string): void {
  const current = getEnabledDockTokensOp(store);
  const idx = current.indexOf(appId);
  if (idx >= 0) {
    if (current.length <= 1) {
      store.showToast("Keep at least one Dock app enabled", true);
      return;
    }
    current.splice(idx, 1);
  } else {
    current.push(appId);
  }
  store.stageDeviceSetting("dock_apps", current.join(","));
}

export function moveDockAppTokenOp(store: StudioStore, appId: string, delta: -1 | 1): void {
  const current = getEnabledDockTokensOp(store);
  const idx = current.indexOf(appId);
  const nextIdx = idx + delta;
  if (idx < 0 || nextIdx < 0 || nextIdx >= current.length) return;
  const [moved] = current.splice(idx, 1);
  current.splice(nextIdx, 0, moved);
  store.stageDeviceSetting("dock_apps", current.join(","));
}

export function getEnabledActivitySourcesOp(store: StudioStore): string[] {
  const rawCfg = store.state?.config?.activity_sources;
  if (rawCfg === undefined || rawCfg === null) {
    return ACTIVITY_SOURCES_CATALOG.map((s) => s.id);
  }
  return String(rawCfg)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

export function toggleActivitySourceOp(store: StudioStore, sourceId: string): void {
  const current = getEnabledActivitySourcesOp(store);
  const idx = current.indexOf(sourceId);
  if (idx >= 0) {
    current.splice(idx, 1);
  } else {
    current.push(sourceId);
  }
  store.stageDeviceSetting("activity_sources", current.join(","));
}

export function applyDeviceCustomColorOp(
  store: StudioStore,
  hex: string,
  switchColorProfile = true,
): void {
  if (!isValidHexColor(hex)) return;
  store.stageDeviceSetting("device_custom_color", hex.toUpperCase());
  if (switchColorProfile) {
    for (const sec of store.state?.esphome?.sections || []) {
      for (const it of sec.items || []) {
        if (
          it.domain === "select" &&
          (it.name || "").toLowerCase().includes("color profile") &&
          (it.options || []).includes("Custom") &&
          it.state !== "Custom"
        ) {
          void store.espSelect(it.entity_id, "Custom");
        }
      }
    }
  }
}

export function deleteCustomPaletteOp(store: StudioStore, hex: string): void {
  const target = hex.toUpperCase();
  const next: CustomPalette[] = (store.state?.system_config?.custom_palettes || []).filter(
    (p) => p.hex.toUpperCase() !== target,
  );
  store.stageSystemSetting("custom_palettes", next);
}

export async function uploadWallpaperOp(store: StudioStore, scope: StudioScope): Promise<void> {
  const file = scope === "device" ? store.selectedDeviceWallpaperFile : store.selectedSystemWallpaperFile;
  if (!file) {
    store.showToast("Choose an image file first", true);
    return;
  }
  const targetSubentryId = scope === "device" ? store.activeSubentryId : undefined;
  if (scope === "device" && !targetSubentryId) {
    store.showToast("Choose a Device first", true);
    return;
  }

  store.uploadScope = scope;
  store.uploadBusy = true;
  store.uploadPercent = 0;
  store.host.requestUpdate();

  try {
    const result = await store.ws.uploadWallpaperMultipart({
      scope,
      subentryId: targetSubentryId,
      file,
      onProgress: (pct) => {
        store.uploadPercent = pct;
        store.host.requestUpdate();
      },
    });
    if (scope === "device") {
      store.selectedDeviceWallpaperFile = null;
    } else {
      store.selectedSystemWallpaperFile = null;
    }
    const inputId = scope === "device" ? "input-upload-wp" : "input-upload-sys-wp";
    store.pendingDomRevert = {
      controlIds: { ...(store.pendingDomRevert?.controlIds || {}), [inputId]: "" },
    };
    if (store.state) {
      if (result.wallpapers && scope === "device" && store.activeSubentryId === targetSubentryId) {
        store.state = { ...store.state, wallpapers: result.wallpapers };
      }
      if (result.system_wallpapers) {
        store.state = { ...store.state, system_wallpapers: result.system_wallpapers };
      }
    }
    await store.refreshState();
    store.showToast("Uploaded wallpaper");
  } catch (err) {
    store.showToast(formatWsError(err, "Wallpaper upload failed"), true);
  } finally {
    store.uploadBusy = false;
    store.uploadScope = null;
    store.uploadPercent = 0;
    store.host.requestUpdate();
  }
}

function clearPendingWallpaperCycle(store: StudioStore, targetSubentryId: string): void {
  const bucket = store.pendingDeviceBuckets.get(targetSubentryId);
  if (!bucket || !("wallpaper_cycle_minutes" in bucket.patch)) return;
  delete bucket.patch.wallpaper_cycle_minutes;
  delete bucket.previousValues.wallpaper_cycle_minutes;
  delete bucket.previousValues["__dom:cfg-wallpaper_cycle_minutes"];
  if (Object.keys(bucket.patch).length === 0) {
    if (bucket.timer) clearTimeout(bucket.timer);
    store.pendingDeviceBuckets.delete(targetSubentryId);
  }
}

export async function selectWallpaperSourceOp(store: StudioStore, sourceId: string): Promise<void> {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  clearPendingWallpaperCycle(store, targetSubentryId);
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "select_wallpaper", {
      source_id: sourceId,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast(sourceId ? "Wallpaper applied" : "Wallpaper turned off");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not select wallpaper"), true);
  }
}

export async function setWallpaperRotationOp(store: StudioStore, minutes: number): Promise<void> {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  const cleanMins = Math.max(0, Math.round(Number(minutes) || 0));
  clearPendingWallpaperCycle(store, targetSubentryId);

  const prevMins =
    store.state && store.state.subentry_id === targetSubentryId
      ? Number(store.state.config?.wallpaper_cycle_minutes || 0)
      : 0;
  if (store.state && store.state.subentry_id === targetSubentryId) {
    store.state = {
      ...store.state,
      config: {
        ...store.state.config,
        wallpaper_cycle_minutes: cleanMins,
      },
    };
    store.host.requestUpdate();
  }

  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "save_device_config", {
      config: { wallpaper_cycle_minutes: cleanMins },
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast(cleanMins > 0 ? "Wallpaper rotation enabled" : "Wallpaper rotation stopped");
  } catch (err) {
    if (store.state && store.state.subentry_id === targetSubentryId) {
      store.state = {
        ...store.state,
        config: {
          ...store.state.config,
          wallpaper_cycle_minutes: prevMins,
        },
      };
      store.pendingDomRevert = {
        controlIds: {
          ...(store.pendingDomRevert?.controlIds || {}),
          "cfg-wallpaper_cycle_minutes": String(prevMins),
        },
      };
      store.host.requestUpdate();
    }
    store.showToast(formatWsError(err, "Could not update wallpaper rotation"), true);
  }
}

export async function toggleWallpaperFavOp(store: StudioStore, sourceId: string): Promise<void> {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "toggle_wallpaper_favorite", {
      source_id: sourceId,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update favorite"), true);
  }
}

export async function setAllWallpaperFavoritesOp(
  store: StudioStore,
  sourceIds: readonly string[],
): Promise<void> {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "toggle_wallpaper_favorite", {
      source_ids: [...sourceIds],
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast(
      sourceIds.length > 0 ? "Starred all wallpapers" : "Cleared starred wallpapers",
    );
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update favorites"), true);
  }
}

export async function deleteWallpaperOp(
  store: StudioStore,
  scope: StudioScope,
  sourceId: string,
): Promise<void> {
  try {
    if (scope === "device") {
      const targetSubentryId = store.activeSubentryId;
      if (!targetSubentryId) return;
      const res = await store.ws.runDeviceCommand(targetSubentryId, "delete_wallpaper", {
        source_id: sourceId,
      });
      if (res && store.activeSubentryId === targetSubentryId) {
        store.ingestPayload(res, false);
      }
    } else {
      const res = await store.ws.runSystemCommand(
        "delete_system_wallpaper",
        { source_id: sourceId },
        store.activeSubentryId || null,
      );
      if (res) store.ingestPayload(res, false);
    }
    store.showToast("Deleted wallpaper");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not delete wallpaper"), true);
  }
}

export function updateStringListRowOp(
  store: StudioStore,
  key: "calendar_entities" | "camera_entities" | "remotes_list",
  index: number,
  value: string,
): void {
  const list = [...(store.state?.system_config?.[key] || [])];
  list[index] = value;
  store.stageSystemSetting(key, list);
}

export function addStringListRowOp(
  store: StudioStore,
  key: "calendar_entities" | "camera_entities" | "remotes_list",
  defaultEntity = "",
  maxLen = 10,
): void {
  const list = [...(store.state?.system_config?.[key] || [])];
  if (list.length >= maxLen) {
    store.showToast(`Maximum of ${maxLen} entries reached`, true);
    return;
  }
  list.push(defaultEntity);
  store.stageSystemSetting(key, list);
}

export function removeStringListRowOp(
  store: StudioStore,
  key: "calendar_entities" | "camera_entities" | "remotes_list",
  index: number,
): void {
  const list = [...(store.state?.system_config?.[key] || [])];
  list.splice(index, 1);
  store.stageSystemSetting(key, list);
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
  store.stageSystemSetting("volume_overrides", list);
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
  store.stageSystemSetting("volume_overrides", list);
}

export function removeVolumeOverrideRowOp(store: StudioStore, index: number): void {
  const list: VolumeOverride[] = [...(store.state?.system_config?.volume_overrides || [])];
  list.splice(index, 1);
  store.stageSystemSetting("volume_overrides", list);
}

export function addRemoteGroupRowOp(store: StudioStore): void {
  const groups: RemoteGroup[] = (store.state?.system_config?.remote_groups || []).map((g) => ({
    ...g,
    remotes: [...(g.remotes || [])],
  }));
  const id = `group_${Date.now().toString(36)}`;
  groups.push({ id, name: "New Remote Group", area_id: "", remotes: [] });
  store.stageSystemSetting("remote_groups", groups);
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
  store.stageSystemSetting("remote_groups", groups);
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
  store.stageSystemSetting("remote_groups", groups);
}

export function removeRemoteGroupRowOp(store: StudioStore, groupId: string): void {
  const groups = (store.state?.system_config?.remote_groups || []).filter((g) => g.id !== groupId);
  store.stageSystemSetting("remote_groups", groups);
}

export async function previewCameraOp(
  store: StudioStore,
  cameraEntity: string,
  bustCache = false,
): Promise<void> {
  if (!cameraEntity) {
    store.closeCameraPreview();
    return;
  }
  const dbObj = (store.state?.doorbells || []).find((b) => b.camera_entity === cameraEntity);
  const camObj = (store.state?.catalog?.cameras || []).find((c) => c.id === cameraEntity);
  const existingSigned = dbObj?.preview_url || camObj?.preview_url || "";
  if (existingSigned) {
    const sep = existingSigned.includes("?") ? "&" : "?";
    store.activeCameraPreviewEntity = cameraEntity;
    store.cameraPreviewUrl = bustCache ? `${existingSigned}${sep}_ts=${Date.now()}` : existingSigned;
    store.host.requestUpdate();
    return;
  }
  try {
    const signed = await store.ws.signHaPath(
      `/api/camera_proxy/${encodeURIComponent(cameraEntity)}`,
      300,
    );
    const sep = signed.includes("?") ? "&" : "?";
    store.activeCameraPreviewEntity = cameraEntity;
    store.cameraPreviewUrl = `${signed}${sep}_ts=${Date.now()}`;
    store.host.requestUpdate();
  } catch (err) {
    store.showToast(formatWsError(err, "Add a Latter Device to preview cameras"), true);
  }
}

export async function testDoorbellSpeakerOp(store: StudioStore): Promise<void> {
  const cams = store.state?.system_config?.camera_entities || [];
  if (!cams[0]) {
    store.showToast("Add a camera in Shared Entities first", true);
    return;
  }
  if (!store.doorbellTestSubentryId) {
    store.showToast("Choose a Device to test from", true);
    return;
  }
  await store.flushSystemSettings();
  try {
    const res = await store.ws.runSystemCommand(
      "test_doorbell_speaker",
      {
        subentry_id: store.doorbellTestSubentryId,
        camera_entity: cams[0],
        message: "Testing Latter doorbell audio.",
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Played test message on door speaker");
  } catch (err) {
    store.showToast(formatWsError(err, "Door speaker test failed"), true);
  }
}
