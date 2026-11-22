/**
 * Optimistic Device-Group Baseline & Pending-Entity Payload Overlays.
 *
 * Imports strictly leaf constants/types (`constants.ts`, `types.ts`) and `store-types.ts`.
 */

import {
  GROUP_BEHAVIOR_NON_PREF_KEYS,
  GROUP_DISPLAY_NON_PREF_KEYS,
  GROUP_INTERFACE_NON_PREF_KEYS,
} from "../constants.js";
import type { StudioStatePayload, SystemConfig } from "../types.js";
import {
  cleanPersistedStringList,
  isCatalogItemSupported,
  isStringListKey,
  mergePersistedWithBlankSlots,
  type PendingEntityEntry,
  STRING_LIST_KEYS,
  STRING_LIST_MAX_ITEMS,
  type StringListKey,
  type StudioStoreContext,
} from "./store-types.js";

export {
  cleanPersistedStringList,
  isCatalogItemSupported,
  isStringListKey,
  mergePersistedWithBlankSlots,
  STRING_LIST_KEYS,
  STRING_LIST_MAX_ITEMS,
  type StringListKey,
};

const BEHAVIOR_NON_PREF_KEY_SET = new Set<string>(GROUP_BEHAVIOR_NON_PREF_KEYS);
const DISPLAY_NON_PREF_KEY_SET = new Set<string>(GROUP_DISPLAY_NON_PREF_KEYS);
const INTERFACE_NON_PREF_KEY_SET = new Set<string>(GROUP_INTERFACE_NON_PREF_KEYS);

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

export function overlayPendingBlankListSlots(
  store: Pick<StudioStoreContext, "pendingBlankListSlots">,
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
