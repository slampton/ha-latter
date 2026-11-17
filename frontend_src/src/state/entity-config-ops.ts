/**
 * Device & System configuration staging, optimistic ESPHome entity actions,
 * dock/activity/wallpaper/color mutations, and shared-entity list editors.
 */

import { formatWsError } from "../api/ws-client.js";
import {
  ACTIVITY_SOURCES_CATALOG,
  AREA_CATEGORIES_CATALOG,
  DEFAULT_AREA_CATEGORIES_TOKENS,
  DEFAULT_DOCK_ROUTES_TOKENS,
  DEFAULT_HOME_CATEGORIES_TOKENS,
  GROUP_BEHAVIOR_NON_PREF_KEYS,
  HOME_CATEGORIES_CATALOG,
  MAX_DOCK_ITEMS,
  MAX_PINNED_ITEMS,
  POWER_PROFILE_PREFS,
  POWER_PROFILE_SUBKEYS,
  SHORTCUT_LABEL_MAX,
  SHORTCUT_ROUTES_CATALOG,
} from "../constants.js";
import { normalizeMdiIconSlug, SHORTCUT_DOMAIN_ACTIONS } from "../mdi-catalog.js";
import type {
  CustomPalette,
  DeviceConfig,
  RemoteGroup,
  ShortcutItem,
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

export type StringListKey = "calendar_entities" | "camera_entities" | "remotes_list";

export const STRING_LIST_KEYS: readonly StringListKey[] = [
  "calendar_entities",
  "camera_entities",
  "remotes_list",
];

export const STRING_LIST_MAX_ITEMS: Record<StringListKey, number> = {
  camera_entities: 10,
  remotes_list: 10,
  calendar_entities: 50,
};

function isStringListKey(key: string): key is StringListKey {
  return (
    key === "calendar_entities" ||
    key === "camera_entities" ||
    key === "remotes_list"
  );
}

function cleanPersistedStringList(items: readonly unknown[], maxItems: number): string[] {
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

function mergePersistedWithBlankSlots(
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

const SAVE_DEBOUNCE_MS = 220;
const ENTITY_OPTIMISTIC_TTL_MS = 8000;

export const PENDING_ENTITY_STATES = new Map<string, PendingEntityEntry>();

const POWER_PROFILE_SUBKEY_SET = new Set<string>(POWER_PROFILE_SUBKEYS);
const BEHAVIOR_NON_PREF_KEY_SET = new Set<string>(GROUP_BEHAVIOR_NON_PREF_KEYS);

function expandDevicePrefPatch(
  currentCfg: Record<string, unknown>,
  rawPatch: Record<string, unknown>,
): Record<string, unknown> {
  const expanded: Record<string, unknown> = { ...rawPatch };
  if (typeof rawPatch.power_profile === "string" && rawPatch.power_profile in POWER_PROFILE_PREFS) {
    const preset = POWER_PROFILE_PREFS[rawPatch.power_profile];
    for (const [k, v] of Object.entries(preset)) {
      if (!(k in rawPatch)) {
        expanded[k] = v;
      }
    }
  } else if (
    !("power_profile" in rawPatch) &&
    Object.keys(rawPatch).some((k) => POWER_PROFILE_SUBKEY_SET.has(k))
  ) {
    const curProf = String(currentCfg.power_profile || "Portable Carry");
    const preset = POWER_PROFILE_PREFS[curProf];
    if (preset) {
      const merged = { ...currentCfg, ...rawPatch };
      for (const [k, want] of Object.entries(preset)) {
        const have = merged[k] !== undefined ? merged[k] : want;
        if (have !== want) {
          expanded.power_profile = "Custom";
          break;
        }
      }
    }
  }
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
  const supportedPrefKeys = new Set((payload.device_prefs || []).map((p) => p.key));
  const behaviorPrefKeys = new Set(
    (payload.device_prefs || []).filter((p) => p.group_tier === "behavior").map((p) => p.key),
  );
  const isRoaming = curCfg.is_roaming !== false;

  if ("device_group" in rawPatch) {
    const targetGrpId = String(rawPatch.device_group || "custom").trim() || "custom";
    expanded.device_group = targetGrpId;
    if (targetGrpId !== "custom") {
      const grp = groups.find((g) => g.id === targetGrpId);
      if (grp?.device_config) {
        for (const [gk, gv] of Object.entries(grp.device_config)) {
          if (gk in rawPatch || gv === undefined || gv === null) continue;
          if ((gk === "sync_device_area" || gk === "area_follow_dwell_s") && !isRoaming) continue;
          if (BEHAVIOR_NON_PREF_KEY_SET.has(gk) || supportedPrefKeys.has(gk)) {
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
        for (const [ek, ev] of Object.entries(expanded)) {
          if ((ek === "sync_device_area" || ek === "area_follow_dwell_s") && !isRoaming) continue;
          if (
            (BEHAVIOR_NON_PREF_KEY_SET.has(ek) || behaviorPrefKeys.has(ek)) &&
            grp.device_config[ek] !== undefined &&
            String(grp.device_config[ek]) !== String(ev)
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
      nextGrp === "custom"
        ? "Custom"
        : groups.find((g) => g.id === nextGrp)?.name || nextGrp;
    payload.system_devices = payload.system_devices.map((d) =>
      d.subentry_id === payload.subentry_id
        ? { ...d, device_group: nextGrp, device_group_name: nextGrpName }
        : d,
    );
  }
  if (payload.device_prefs) {
    payload.device_prefs = payload.device_prefs.map((p) => {
      if (p.key in expanded) {
        return { ...p, value: expanded[p.key] };
      }
      return p;
    });
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
  key: string,
  value: unknown,
  controlDomId?: string,
  debounceMs = SAVE_DEBOUNCE_MS,
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

  const curCfg =
    store.state && store.state.subentry_id === targetSubentryId
      ? ((store.state.config || {}) as Record<string, unknown>)
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
  if (key === "power_profile" || POWER_PROFILE_SUBKEY_SET.has(key)) {
    snapshotKey("power_profile");
    for (const sk of POWER_PROFILE_SUBKEYS) {
      snapshotKey(sk);
    }
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
    if (store.state.subentry_id === targetSubentryId) {
      const nextPayload: StudioStatePayload = {
        ...store.state,
        system_devices: nextSystemDevices,
        config: { ...store.state.config },
      };
      overlayDevicePrefsOnSections(nextPayload, { [key]: value });
      store.state = nextPayload;
    } else if (nextSystemDevices !== store.state.system_devices) {
      store.state = {
        ...store.state,
        system_devices: nextSystemDevices,
      };
    }
  }

  if (bucket.timer) clearTimeout(bucket.timer);
  bucket.timer = setTimeout(() => {
    void store.flushDeviceBucket(targetSubentryId);
  }, Math.max(0, debounceMs));
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
        const restoredPrefs: Record<string, unknown> = {};
        for (const [k, v] of Object.entries(previousValues)) {
          if (!k.startsWith("__dom:")) {
            restoredConfig[k] = v;
            if (v !== undefined) {
              restoredPrefs[k] = v;
            }
          }
        }
        const nextPayload: StudioStatePayload = {
          ...store.state,
          system_devices: nextSystemDevices,
          config: restoredConfig as DeviceConfig,
        };
        if (Object.keys(restoredPrefs).length > 0) {
          overlayDevicePrefsOnSections(nextPayload, restoredPrefs);
        }
        store.state = nextPayload;
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
    if (isStringListKey(key) && Array.isArray(prev)) {
      store.pendingSystemPrevious[key] = cleanPersistedStringList(prev, STRING_LIST_MAX_ITEMS[key]);
    } else {
      store.pendingSystemPrevious[key] = prev !== undefined ? structuredClone(prev) : undefined;
    }
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
      const prevUiSys = store.state.system_config;
      const restored: Record<string, unknown> = {
        ...(prevUiSys as unknown as Record<string, unknown>),
      };
      for (const [k, v] of Object.entries(previousValues)) {
        if (k.startsWith("__dom:")) {
          const domId = k.slice(6);
          controlRevert[domId] = typeof v === "boolean" ? v : String(v ?? "");
        } else if (v !== undefined) {
          restored[k] = v;
        }
      }
      const nextPayload: StudioStatePayload = {
        ...store.state,
        system_config: restored as unknown as SystemConfig,
      };
      overlayPendingBlankListSlots(store, nextPayload, prevUiSys);
      store.state = nextPayload;
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

export async function runDeviceActionOp(
  store: StudioStore,
  action: string,
  toastMessage?: string,
): Promise<boolean> {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId || !action) return false;
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "device_action", {
      action,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    if (toastMessage) {
      store.showToast(toastMessage);
    }
    return true;
  } catch (err) {
    store.showToast(formatWsError(err, "Device action failed"), true);
    return false;
  }
}

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

function normalizeShortcutArray(
  raw: unknown,
  isDock: boolean,
): ShortcutItem[] {
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
      out.push({
        kind: "route",
        target,
        action: "",
        label: sanitizeShortcutLabel(rec.label),
        icon: normalizeMdiIconSlug(rec.icon),
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

export function getDockItemsOp(store: StudioStore): ShortcutItem[] {
  const raw = store.state?.config?.dock_items;
  if (raw === undefined || raw === null) {
    return defaultDockShortcutItems();
  }
  return normalizeShortcutArray(raw, true);
}

export function getPinnedItemsOp(store: StudioStore): ShortcutItem[] {
  const raw = store.state?.config?.pinned_items;
  if (raw === undefined || raw === null) {
    return [];
  }
  return normalizeShortcutArray(raw, false);
}

export function moveShortcutItemOp(
  store: StudioStore,
  listKey: "dock_items" | "pinned_items",
  idx: number,
  delta: -1 | 1,
): void {
  const current = listKey === "dock_items" ? getDockItemsOp(store) : getPinnedItemsOp(store);
  const nextIdx = idx + delta;
  if (idx < 0 || nextIdx < 0 || idx >= current.length || nextIdx >= current.length) {
    return;
  }
  const next = current.map((it) => ({ ...it }));
  const [moved] = next.splice(idx, 1);
  next.splice(nextIdx, 0, moved);
  store.stageDeviceSetting(listKey, next);
}

export function removeShortcutItemOp(
  store: StudioStore,
  listKey: "dock_items" | "pinned_items",
  idx: number,
): void {
  const current = listKey === "dock_items" ? getDockItemsOp(store) : getPinnedItemsOp(store);
  if (idx < 0 || idx >= current.length) return;
  const next = current.filter((_, i) => i !== idx).map((it) => ({ ...it }));
  store.stageDeviceSetting(listKey, next);
}

export function resetDockItemsToDefaultOp(store: StudioStore): void {
  store.stageDeviceSetting("dock_items", defaultDockShortcutItems());
  store.showToast("Restored default App Dock");
}

export function openShortcutModalOp(
  store: StudioStore,
  listKey: "dock_items" | "pinned_items",
  editIndex: number | null = null,
): void {
  const isDock = listKey === "dock_items";
  const current = isDock ? getDockItemsOp(store) : getPinnedItemsOp(store);
  const caps = store.state?.capabilities || {};
  const compatibleRoutes = SHORTCUT_ROUTES_CATALOG.filter((r) => {
    if (!isDock && r.dockOnly) return false;
    if (isDock && r.token === "settings:root") return false;
    if (r.capability === "round" && caps.is_round === false) return false;
    if (r.capability === "imu" && caps.has_imu === false) return false;
    return true;
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
      kind: isDock ? "route" : (entities.length > 0 ? "entity" : "route"),
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
}

export function saveShortcutModalOp(store: StudioStore): void {
  const modal = store.shortcutModal;
  const isDock = modal.listKey === "dock_items";
  const maxItems = isDock ? MAX_DOCK_ITEMS : MAX_PINNED_ITEMS;
  const current = (isDock ? getDockItemsOp(store) : getPinnedItemsOp(store)).map((it) => ({
    ...it,
  }));

  if (modal.editIndex === null && current.length >= maxItems) {
    store.showToast(
      `${isDock ? "App Dock" : "Pinned App"} supports up to ${maxItems} shortcuts`,
      true,
    );
    return;
  }

  const rawIcon = modal.icon.trim();
  const cleanIcon = rawIcon ? normalizeMdiIconSlug(rawIcon) : "";
  if (rawIcon && !cleanIcon) {
    store.showToast("Enter a valid Material Design Icon name (e.g. mdi:bell-ring)", true);
    return;
  }
  const cleanLabel = sanitizeShortcutLabel(modal.label);

  let built: ShortcutItem;
  if (modal.kind === "route") {
    const routeTok = modal.routeTarget.trim().toLowerCase();
    const spec = SHORTCUT_ROUTES_CATALOG.find((r) => r.token === routeTok);
    if (!spec || (!isDock && spec.dockOnly) || (isDock && routeTok === "settings:root")) {
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
      : (validActs[0]?.action || "");
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

  store.shortcutModal = { ...store.shortcutModal, open: false };
  store.stageDeviceSetting(modal.listKey, current);
}

export function getEnabledAreaCategoriesOp(store: StudioStore): string[] {
  const raw = String(store.state?.config?.area_categories ?? "");
  if (!raw.trim()) {
    return [...DEFAULT_AREA_CATEGORIES_TOKENS];
  }
  const known = new Set(AREA_CATEGORIES_CATALOG.map((c) => c.token));
  const parsed = raw
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter((s, i, arr) => Boolean(s) && known.has(s) && arr.indexOf(s) === i);
  return parsed.length > 0 ? parsed : [...DEFAULT_AREA_CATEGORIES_TOKENS];
}

export function toggleAreaCategoryTokenOp(store: StudioStore, token: string): void {
  const current = getEnabledAreaCategoriesOp(store);
  const idx = current.indexOf(token);
  if (idx >= 0) {
    if (current.length <= 1) {
      store.showToast("Keep at least one Area category enabled", true);
      return;
    }
    current.splice(idx, 1);
  } else {
    current.push(token);
  }
  store.stageDeviceSetting("area_categories", current.join(","));
}

export function moveAreaCategoryTokenOp(store: StudioStore, token: string, delta: -1 | 1): void {
  const current = getEnabledAreaCategoriesOp(store);
  const idx = current.indexOf(token);
  const nextIdx = idx + delta;
  if (idx < 0 || nextIdx < 0 || nextIdx >= current.length) return;
  const [moved] = current.splice(idx, 1);
  current.splice(nextIdx, 0, moved);
  store.stageDeviceSetting("area_categories", current.join(","));
}

export function getEnabledHomeCategoriesOp(store: StudioStore): string[] {
  const raw = String(store.state?.config?.home_categories ?? "");
  if (!raw.trim()) {
    return [...DEFAULT_HOME_CATEGORIES_TOKENS];
  }
  const known = new Set(HOME_CATEGORIES_CATALOG.map((c) => c.token));
  const parsed = raw
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter((s, i, arr) => Boolean(s) && known.has(s) && arr.indexOf(s) === i);
  return parsed.length > 0 ? parsed : [...DEFAULT_HOME_CATEGORIES_TOKENS];
}

export function toggleHomeCategoryTokenOp(store: StudioStore, token: string): void {
  const current = getEnabledHomeCategoriesOp(store);
  const idx = current.indexOf(token);
  if (idx >= 0) {
    if (current.length <= 1) {
      store.showToast("Keep at least one Home category enabled", true);
      return;
    }
    current.splice(idx, 1);
  } else {
    current.push(token);
  }
  store.stageDeviceSetting("home_categories", current.join(","));
}

export function moveHomeCategoryTokenOp(store: StudioStore, token: string, delta: -1 | 1): void {
  const current = getEnabledHomeCategoriesOp(store);
  const idx = current.indexOf(token);
  const nextIdx = idx + delta;
  if (idx < 0 || nextIdx < 0 || nextIdx >= current.length) return;
  const [moved] = current.splice(idx, 1);
  current.splice(nextIdx, 0, moved);
  store.stageDeviceSetting("home_categories", current.join(","));
}

export function getEnabledActivitySourcesOp(store: StudioStore): string[] {
  const rawCfg = store.state?.config?.activity_sources;
  if (rawCfg === undefined || rawCfg === null) {
    return ACTIVITY_SOURCES_CATALOG.map((s) => s.token);
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
    store.stageDeviceSetting("color_profile", "Custom");
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
    store.stageSystemSetting(key, nextPersisted);
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
  store.stageSystemSetting(key, nextPersisted);
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
  store.stageSystemSetting(key, nextPersisted);
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
  const cams = (store.state?.system_config?.camera_entities || [])
    .map((c) => String(c || "").trim())
    .filter(Boolean);
  if (!cams[0]) {
    store.showToast("Add a camera in Shared Entities first", true);
    return;
  }
  if (!store.doorbellTestSubentryId) {
    store.showToast("Choose a Device to test from", true);
    return;
  }
  const message = store.doorbellTestReply.trim() || "Testing Latter doorbell audio.";
  await store.flushSystemSettings();
  try {
    const res = await store.ws.runSystemCommand(
      "test_doorbell_speaker",
      {
        subentry_id: store.doorbellTestSubentryId,
        camera_entity: cams[0],
        message,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Played test message on door speaker");
  } catch (err) {
    store.showToast(formatWsError(err, "Door speaker test failed"), true);
  }
}
