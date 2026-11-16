/**
 * Device Groups, bulk ESPHome control actions, BLE calibration, and Area sensor fusion operations.
 */

import { formatWsError } from "../api/ws-client.js";
import type { SharedControlItem, SystemDeviceEntry } from "../types.js";
import type { StudioStore } from "./store.js";

export async function createDeviceGroupOp(store: StudioStore): Promise<void> {
  const name = store.newGroupName.trim();
  const description = store.newGroupDesc.trim();
  if (!name) {
    store.showToast("Enter a Device Group name", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "create_device_group",
      { name, description },
      store.activeSubentryId || null,
    );
    store.newGroupName = "";
    store.newGroupDesc = "";
    if (res) store.ingestPayload(res, false);
    store.showToast(`Created group "${name}"`);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not create Device Group"), true);
  }
}

export async function deleteDeviceGroupOp(store: StudioStore, groupId: string): Promise<void> {
  try {
    const res = await store.ws.runSystemCommand(
      "delete_device_group",
      { group_id: groupId },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Deleted Device Group");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not delete Device Group"), true);
  }
}

export async function syncDeviceGroupOp(
  store: StudioStore,
  groupId: string,
  singleSubentryId?: string,
): Promise<void> {
  try {
    const payload: Record<string, unknown> = { group_id: groupId };
    if (singleSubentryId) payload.subentry_id = singleSubentryId;
    const res = await store.ws.runSystemCommand(
      "sync_device_group",
      payload,
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Synced to group baseline");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not sync Device Group"), true);
  }
}

export async function seedGroupBaselineFromDeviceOp(store: StudioStore): Promise<void> {
  if (!store.seedGroupTargetId || !store.seedSourceSubentryId) {
    store.showToast("Choose both a target group and a source Device", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "seed_group_baseline",
      {
        group_id: store.seedGroupTargetId,
        subentry_id: store.seedSourceSubentryId,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Saved group baseline from Device");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not seed group baseline"), true);
  }
}

export function resolvedGroupCtrlIdOp(store: StudioStore): string {
  const filter = store.groupCtrlFilter || "all";
  if (filter.startsWith("group:")) return filter.slice(6);
  if (filter === "trait:roaming") return "roaming";
  if (filter === "trait:stationary") return "stationary";
  return filter;
}

export async function setGroupDeviceSettingOp(
  store: StudioStore,
  patch: Record<string, unknown>,
): Promise<void> {
  try {
    const res = await store.ws.runSystemCommand(
      "set_group_device_setting",
      {
        group_id: resolvedGroupCtrlIdOp(store) || "all",
        config: patch,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Applied group setting");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not apply group setting"), true);
  }
}

export function filteredControlTargetsOp(store: StudioStore, ctrl: SharedControlItem): string[] {
  const grpId = resolvedGroupCtrlIdOp(store);
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

export async function bulkToggleOp(
  store: StudioStore,
  ctrl: SharedControlItem,
  turnOn: boolean,
): Promise<void> {
  if (ctrl.pref_key) {
    await setGroupDeviceSettingOp(store, { [ctrl.pref_key]: turnOn });
    return;
  }
  const entityIds = filteredControlTargetsOp(store, ctrl);
  if (!entityIds.length) return;
  try {
    const res = await store.ws.runSystemCommand(
      "system_entity_action",
      {
        entity_ids: entityIds,
        action: turnOn ? "turn_on" : "turn_off",
        group_id: resolvedGroupCtrlIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Bulk switch update failed"), true);
  }
}

export async function bulkSelectOp(
  store: StudioStore,
  ctrl: SharedControlItem,
  option: string,
): Promise<void> {
  if (ctrl.pref_key) {
    await setGroupDeviceSettingOp(store, { [ctrl.pref_key]: option });
    return;
  }
  const entityIds = filteredControlTargetsOp(store, ctrl);
  if (!entityIds.length) return;
  try {
    const res = await store.ws.runSystemCommand(
      "system_entity_action",
      {
        entity_ids: entityIds,
        option,
        group_id: resolvedGroupCtrlIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Bulk option update failed"), true);
  }
}

export async function bulkNumberOp(
  store: StudioStore,
  ctrl: SharedControlItem,
  level: number,
): Promise<void> {
  if (!Number.isFinite(level)) return;
  if (ctrl.pref_key) {
    await setGroupDeviceSettingOp(store, { [ctrl.pref_key]: level });
    return;
  }
  const entityIds = filteredControlTargetsOp(store, ctrl);
  if (!entityIds.length) return;
  try {
    const res = await store.ws.runSystemCommand(
      "system_entity_action",
      {
        entity_ids: entityIds,
        level,
        group_id: resolvedGroupCtrlIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Bulk number update failed"), true);
  }
}

export function getActiveSurveyDeviceOp(store: StudioStore): SystemDeviceEntry | undefined {
  const devs = store.state?.system_devices || [];
  const bleDevs = devs.filter((d) => d.ble_tracked || d.kind === "ble_tag");
  return bleDevs.find((d) => d.subentry_id === store.bleSurveySubentryId);
}

export async function setBleScannerOffsetOp(
  store: StudioStore,
  scannerSource: string,
  offsetDb: number,
): Promise<void> {
  const source = String(scannerSource || "").trim();
  if (!source) {
    store.showToast("Missing BLE scanner source", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "set_ble_scanner_offset",
      { scanner_source: source, offset_db: offsetDb },
      store.activeSubentryId || null,
    );
    if (res) {
      if (!store.bleLiveStreamActive && Array.isArray(res.system_devices) && store.bleSurveyFrozen) {
        const sourceNorm = source.toLowerCase();
        for (const incomingDev of res.system_devices) {
          if (!incomingDev.subentry_id) continue;
          const frozen = store.bleSurveyFrozen.get(incomingDev.subentry_id);
          if (!frozen) continue;
          const incomingRow = (incomingDev.ble_survey_rows || []).find(
            (r) => String(r.scanner_source || "").trim().toLowerCase() === sourceNorm,
          );
          if (!incomingRow) continue;
          frozen.rows = frozen.rows.map((r) => {
            if (String(r.scanner_source || "").trim().toLowerCase() !== sourceNorm) {
              return r;
            }
            return {
              ...r,
              offset_db: incomingRow.offset_db,
              effective_rssi: incomingRow.effective_rssi,
            };
          });
        }
      }
      store.ingestPayload(res, false);
    }
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update BLE scanner offset"), true);
  }
}

export async function captureBleAreaSignatureOp(
  store: StudioStore,
  areaId: string,
): Promise<void> {
  const sysDevs = store.state?.system_devices;
  const activeDev = Array.isArray(sysDevs)
    ? getActiveSurveyDeviceOp(store) || sysDevs.find((d) => d.ble_tracked || d.kind === "ble_tag")
    : undefined;
  const surveySubentryId = Array.isArray(sysDevs)
    ? activeDev?.subentry_id || ""
    : store.bleSurveySubentryId;
  if (!surveySubentryId) {
    store.showToast("Select a calibration Device first", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "capture_ble_area_signature",
      { area_id: areaId, survey_subentry_id: surveySubentryId },
      store.activeSubentryId || null,
    );
    store.bleCalibrateHandoffActive = false;
    if (res) store.ingestPayload(res, false);
    else store.host?.requestUpdate?.();
    store.showToast("Captured Area signature");
  } catch (err) {
    store.showToast(formatWsError(err, "Signature capture failed"), true);
  }
}

export async function clearBleAreaSignatureOp(
  store: StudioStore,
  areaId: string,
): Promise<void> {
  try {
    const res = await store.ws.runSystemCommand(
      "clear_ble_area_signature",
      { area_id: areaId },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Cleared Area signature");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not clear Area signature"), true);
  }
}

export async function setAreaFusionOp(
  store: StudioStore,
  areaId: string,
  update: { mode?: string; threshold_pct?: number; sensors?: string[] },
): Promise<void> {
  try {
    const res = await store.ws.runSystemCommand(
      "set_area_fusion",
      { area_id: areaId, ...update },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update Area fusion"), true);
  }
}
