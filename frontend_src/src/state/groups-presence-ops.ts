/**
 * Device Groups, Batch Controls, BLE calibration, and Area sensor fusion operations.
 */

import { formatWsError } from "../api/ws-client.js";
import type { SharedControlItem, SystemDeviceEntry } from "../types.js";
import type { StudioStore } from "./store.js";

function slugifyGroupName(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export async function createDeviceGroupOp(store: StudioStore): Promise<void> {
  const name = store.newGroupName.trim();
  const description = store.newGroupDesc.trim();
  const sourceSubentryId = store.newGroupSourceSubentryId.trim();
  if (!name) {
    store.showToast("Enter a Device Group name", true);
    return;
  }
  try {
    const payload: Record<string, unknown> = { name, description };
    if (sourceSubentryId) {
      payload.source_subentry_id = sourceSubentryId;
    }
    if (store.newGroupIncludeDisplay) {
      payload.include_display = true;
    }
    if (store.newGroupIncludeInterface) {
      payload.include_interface = true;
    }
    const res = await store.ws.runSystemCommand(
      "create_device_group",
      payload,
      store.activeSubentryId || null,
    );
    const createdId = slugifyGroupName(name) || "group";
    store.newGroupFormOpen = false;
    store.newGroupName = "";
    store.newGroupDesc = "";
    store.newGroupSourceSubentryId = "";
    store.newGroupIncludeDisplay = false;
    store.newGroupIncludeInterface = false;
    store.openGroupIds.add(createdId);
    if (res) store.ingestPayload(res, false);
    store.showToast(`Created group "${name}"`);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not create Device Group"), true);
  }
}

export async function confirmSaveDeviceAsGroupOp(store: StudioStore): Promise<void> {
  const name = store.saveGroupModal.name.trim();
  const description = store.saveGroupModal.description.trim();
  const sourceSubentryId = store.saveGroupModal.subentryId || store.activeSubentryId;
  const includeDisplay = Boolean(store.saveGroupModal.includeDisplay);
  const includeInterface = Boolean(store.saveGroupModal.includeInterface);
  if (!name) {
    store.showToast("Enter a Device Group name", true);
    return;
  }
  if (!sourceSubentryId) {
    store.showToast("Choose a Device first", true);
    return;
  }
  store.saveGroupModal = { ...store.saveGroupModal, busy: true };
  store.host.requestUpdate();
  try {
    const payload: Record<string, unknown> = {
      name,
      description,
      source_subentry_id: sourceSubentryId,
      assign_source: true,
    };
    if (includeDisplay) payload.include_display = true;
    if (includeInterface) payload.include_interface = true;
    const res = await store.ws.runSystemCommand(
      "create_device_group",
      payload,
      store.activeSubentryId || null,
    );
    store.saveGroupModal = {
      open: false,
      subentryId: "",
      name: "",
      description: "",
      includeDisplay: false,
      includeInterface: false,
      busy: false,
    };
    if (res) store.ingestPayload(res, false);
    else store.host.requestUpdate();
    store.showToast(`Saved custom group "${name}"`);
  } catch (err) {
    store.saveGroupModal = { ...store.saveGroupModal, busy: false };
    store.host.requestUpdate();
    store.showToast(formatWsError(err, "Could not save custom Device Group"), true);
  }
}

export async function deleteDeviceGroupOp(store: StudioStore, groupId: string): Promise<void> {
  try {
    const res = await store.ws.runSystemCommand(
      "delete_device_group",
      { group_id: groupId },
      store.activeSubentryId || null,
    );
    store.openGroupIds.delete(groupId);
    store.groupCopySourceDrafts.delete(groupId);
    if (store.batchTargetFilter === `group:${groupId}`) {
      store.batchTargetFilter = "all";
    }
    if (res) store.ingestPayload(res, false);
    store.showToast("Deleted Device Group");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not delete Device Group"), true);
  }
}

export async function updateGroupBaselineOp(
  store: StudioStore,
  groupId: string,
  patch: Record<string, unknown>,
): Promise<void> {
  if (!groupId) return;
  try {
    const res = await store.ws.runSystemCommand(
      "update_group_baseline",
      {
        group_id: groupId,
        config: patch,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update group baseline"), true);
  }
}

export async function updateGroupScopeOp(
  store: StudioStore,
  groupId: string,
  scope: { include_display?: boolean; include_interface?: boolean },
): Promise<void> {
  if (!groupId) return;
  try {
    const res = await store.ws.runSystemCommand(
      "update_group_baseline",
      {
        group_id: groupId,
        ...scope,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update group scope"), true);
  }
}

export async function copyDeviceToGroupBaselineOp(
  store: StudioStore,
  groupId: string,
  sourceSubentryId: string,
  copyKeys?: string[],
): Promise<void> {
  if (!groupId || !sourceSubentryId) {
    store.showToast("Choose a Device to copy settings from", true);
    return;
  }
  try {
    const payload: Record<string, unknown> = {
      group_id: groupId,
      source_subentry_id: sourceSubentryId,
    };
    if (copyKeys && copyKeys.length) {
      payload.copy_keys = copyKeys;
    }
    const res = await store.ws.runSystemCommand(
      "update_group_baseline",
      payload,
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Copied Device settings into group baseline");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not copy Device settings"), true);
  }
}

export function resolvedBatchTargetIdOp(store: StudioStore): string {
  const filter = store.batchTargetFilter || "all";
  if (filter.startsWith("group:")) return filter.slice(6);
  return filter;
}

export async function applyBatchDeviceSettingOp(
  store: StudioStore,
  patch: Record<string, unknown>,
): Promise<void> {
  try {
    const res = await store.ws.runSystemCommand(
      "apply_batch_device_setting",
      {
        target: store.batchTargetFilter || "all",
        config: patch,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Applied batch setting");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not apply batch setting"), true);
  }
}

export async function applyBatchCopyFromDeviceOp(
  store: StudioStore,
  sourceSubentryId: string,
  copyKeys: string[],
): Promise<void> {
  if (!sourceSubentryId || !copyKeys.length) {
    store.showToast("Choose a template Device first", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "apply_batch_device_setting",
      {
        target: store.batchTargetFilter || "all",
        source_subentry_id: sourceSubentryId,
        copy_keys: copyKeys,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Pushed list from template Device");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not copy list across target Devices"), true);
  }
}

export function filteredControlTargetsOp(store: StudioStore, ctrl: SharedControlItem): string[] {
  const filter = store.batchTargetFilter || "all";
  return (ctrl.targets || [])
    .filter((t) => {
      if (filter === "all") return true;
      if (filter === "online") return Boolean(t.is_online);
      if (filter === "roaming") return Boolean(t.is_roaming);
      if (filter === "stationary") return !t.is_roaming;
      const grpId = filter.startsWith("group:") ? filter.slice(6) : filter;
      return (t.device_group || "custom") === grpId;
    })
    .map((t) => t.entity_id || "")
    .filter(Boolean);
}

export async function bulkColorOp(
  store: StudioStore,
  ctrl: SharedControlItem,
  hex: string,
): Promise<void> {
  const cleaned = String(hex || "").trim().toUpperCase();
  if (!ctrl.pref_key || !/^#[0-9A-F]{6}$/.test(cleaned)) return;
  await applyBatchDeviceSettingOp(store, { [ctrl.pref_key]: cleaned });
}

export async function bulkPillsToggleOp(
  store: StudioStore,
  ctrl: SharedControlItem,
  token: string,
  currentCsv: string,
): Promise<void> {
  if (!ctrl.pref_key) return;
  const order = ctrl.options || [];
  const activeSet = new Set(
    String(currentCsv || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );
  if (activeSet.has(token)) {
    const minRequired = ctrl.min ?? 0;
    if (activeSet.size <= minRequired) {
      const noun =
        ctrl.pref_key === "tools_items"
          ? "tool"
          : ctrl.pref_key === "games_items"
            ? "game"
            : "category";
      store.showToast(`Keep at least one ${noun} enabled`, true);
      return;
    }
    activeSet.delete(token);
  } else {
    activeSet.add(token);
  }
  const ordered = order.length
    ? order.filter((t) => activeSet.has(t))
    : Array.from(activeSet);
  await applyBatchDeviceSettingOp(store, { [ctrl.pref_key]: ordered.join(",") });
}

export async function bulkToggleOp(
  store: StudioStore,
  ctrl: SharedControlItem,
  turnOn: boolean,
): Promise<void> {
  if (ctrl.pref_key) {
    await applyBatchDeviceSettingOp(store, { [ctrl.pref_key]: turnOn });
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
        group_id: resolvedBatchTargetIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Batch switch update failed"), true);
  }
}

export async function bulkSelectOp(
  store: StudioStore,
  ctrl: SharedControlItem,
  option: string,
): Promise<void> {
  if (ctrl.pref_key) {
    await applyBatchDeviceSettingOp(store, { [ctrl.pref_key]: option });
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
        group_id: resolvedBatchTargetIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Batch option update failed"), true);
  }
}

export async function bulkNumberOp(
  store: StudioStore,
  ctrl: SharedControlItem,
  level: number,
): Promise<void> {
  if (!Number.isFinite(level)) return;
  if (ctrl.pref_key) {
    await applyBatchDeviceSettingOp(store, { [ctrl.pref_key]: level });
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
        group_id: resolvedBatchTargetIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Batch number update failed"), true);
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
