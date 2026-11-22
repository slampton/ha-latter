/**
 * `store.groups` Controller (`GroupsController`, `D-050`, `D-064` / `Q6`, `D-075`):
 * - Device Groups CRUD, scope toggles (`include_display`, `include_interface`), & baseline updates
 * - Delegates staged `Batch controls` operations to `BatchController`
 * - Delegates Walk-Around BLE calibration & Area sensor/illuminance fusion to `ble-calibration-ops`
 */

import { formatWsError } from "../api/ws-client.js";
import type { SharedControlItem, SharedControlTarget, SystemDeviceEntry } from "../types.js";
import { BatchController } from "./batch-controller.js";
import {
  calibrateAreaIlluminanceOp,
  captureBleAreaSignatureOp,
  clearBleAreaSignatureOp,
  getActiveSurveyDeviceOp,
  type IlluminanceCalibrationState,
  isCalibratingIlluminanceOp,
  requestClearBleAreaSignatureOp,
  selectBleCalibrateAreaOp,
  selectBleSurveyDeviceOp,
  setAreaFusionOp,
  setAreaIlluminanceOp,
  setBleScannerOffsetOp,
  toggleBleLiveStreamOp,
} from "./ble-calibration-ops.js";
import type {
  BatchPillState,
  GroupsControllerContract,
  StudioStoreContext,
} from "./store-types.js";

export type { BatchPillState };

function slugifyGroupName(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export class GroupsController implements GroupsControllerContract, IlluminanceCalibrationState {
  private readonly store: StudioStoreContext;
  private readonly batch: BatchController;

  calibratingAllIlluminance = false;
  readonly calibratingIlluminanceAreas = new Set<string>();

  constructor(store: StudioStoreContext) {
    this.store = store;
    this.batch = new BatchController(store);
  }

  get batchPillDrafts(): Map<string, Record<string, boolean>> {
    return this.batch.batchPillDrafts;
  }

  get batchBusy(): boolean {
    return this.batch.batchBusy;
  }

  set batchBusy(val: boolean) {
    this.batch.batchBusy = val;
  }

  get batchDraft(): Map<string, unknown> {
    return this.batch.batchDraft;
  }

  get batchDraftCount(): number {
    return this.batch.batchDraftCount;
  }

  get hasBatchDraft(): boolean {
    return this.batch.hasBatchDraft;
  }

  isCalibratingIlluminance(areaId?: string): boolean {
    return isCalibratingIlluminanceOp(this, areaId);
  }

  // ---------- Device Groups CRUD & Baseline Updates ----------

  toggleNewGroupForm(open?: boolean): void {
    const nextOpen = open !== undefined ? Boolean(open) : !this.store.newGroupFormOpen;
    this.store.newGroupFormOpen = nextOpen;
    if (!nextOpen) {
      this.store.newGroupName = "";
      this.store.newGroupDesc = "";
      this.store.newGroupSourceSubentryId = "";
      this.store.newGroupIncludeDisplay = false;
      this.store.newGroupIncludeInterface = false;
    }
    this.store.host.requestUpdate();
    if (nextOpen && typeof globalThis.requestAnimationFrame === "function") {
      globalThis.requestAnimationFrame(() => {
        const root =
          (this.store.host as unknown as { renderRoot?: ShadowRoot }).renderRoot ||
          this.store.host.shadowRoot;
        const inputEl = root?.getElementById("new-group-name") as HTMLInputElement | null;
        if (inputEl && typeof inputEl.focus === "function") {
          try {
            inputEl.focus({ preventScroll: true });
          } catch {
            inputEl.focus();
          }
        }
      });
    }
  }

  async createDeviceGroup(): Promise<void> {
    const name = this.store.newGroupName.trim();
    const description = this.store.newGroupDesc.trim();
    const sourceSubentryId = this.store.newGroupSourceSubentryId.trim();
    if (!name) {
      this.store.showToast("Enter a Device group name", true);
      return;
    }
    try {
      const payload: Record<string, unknown> = { name, description };
      if (sourceSubentryId) {
        payload.source_subentry_id = sourceSubentryId;
      }
      if (this.store.newGroupIncludeDisplay) {
        payload.include_display = true;
      }
      if (this.store.newGroupIncludeInterface) {
        payload.include_interface = true;
      }
      const res = await this.store.ws.runSystemCommand(
        "create_device_group",
        payload,
        this.store.activeSubentryId || null,
      );
      const createdId = slugifyGroupName(name) || "group";
      this.store.newGroupFormOpen = false;
      this.store.newGroupName = "";
      this.store.newGroupDesc = "";
      this.store.newGroupSourceSubentryId = "";
      this.store.newGroupIncludeDisplay = false;
      this.store.newGroupIncludeInterface = false;
      this.store.openGroupIds.add(createdId);
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast(`Created group "${name}"`);
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not create Device group"), true);
    }
  }

  openSaveGroupModal(): void {
    if (!this.store.activeSubentryId) return;
    const devTitle = this.store.state?.title || "";
    this.store.saveGroupModal = {
      open: true,
      subentryId: this.store.activeSubentryId,
      name: "",
      description: devTitle ? `Saved from ${devTitle}` : "",
      includeDisplay: false,
      includeInterface: false,
      busy: false,
    };
    this.store.host.requestUpdate();
  }

  closeSaveGroupModal(): void {
    this.store.saveGroupModal = { ...this.store.saveGroupModal, open: false, busy: false };
    this.store.host.requestUpdate();
  }

  async confirmSaveGroupModal(): Promise<void> {
    const name = this.store.saveGroupModal.name.trim();
    const description = this.store.saveGroupModal.description.trim();
    const sourceSubentryId = this.store.saveGroupModal.subentryId || this.store.activeSubentryId;
    const includeDisplay = Boolean(this.store.saveGroupModal.includeDisplay);
    const includeInterface = Boolean(this.store.saveGroupModal.includeInterface);
    if (!name) {
      this.store.showToast("Enter a Device group name", true);
      return;
    }
    if (!sourceSubentryId) {
      this.store.showToast("Choose a Device first", true);
      return;
    }
    this.store.saveGroupModal = { ...this.store.saveGroupModal, busy: true };
    this.store.host.requestUpdate();
    try {
      const payload: Record<string, unknown> = {
        name,
        description,
        source_subentry_id: sourceSubentryId,
        assign_source: true,
      };
      if (includeDisplay) payload.include_display = true;
      if (includeInterface) payload.include_interface = true;
      const res = await this.store.ws.runSystemCommand(
        "create_device_group",
        payload,
        this.store.activeSubentryId || null,
      );
      this.store.saveGroupModal = {
        open: false,
        subentryId: "",
        name: "",
        description: "",
        includeDisplay: false,
        includeInterface: false,
        busy: false,
      };
      if (res) this.store.ingestPayload(res, false);
      else this.store.host.requestUpdate();
      this.store.showToast(`Saved custom group "${name}"`);
    } catch (err) {
      this.store.saveGroupModal = { ...this.store.saveGroupModal, busy: false };
      this.store.host.requestUpdate();
      this.store.showToast(formatWsError(err, "Could not save custom Device group"), true);
    }
  }

  async deleteDeviceGroup(groupId: string): Promise<void> {
    const cleanId = String(groupId || "").trim();
    if (!cleanId) return;
    try {
      const res = await this.store.ws.runSystemCommand(
        "delete_device_group",
        { group_id: cleanId },
        this.store.activeSubentryId || null,
      );
      this.store.openGroupIds.delete(cleanId);
      this.store.groupCopySourceDrafts.delete(cleanId);
      if (this.store.batchTargetFilter === `group:${cleanId}`) {
        this.store.batchTargetFilter = "all";
        this.resetBatchDraft();
      }
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Deleted Device group");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not delete Device group"), true);
    }
  }

  requestDeleteDeviceGroup(groupId: string, groupName?: string, memberCount?: number): void {
    const cleanId = String(groupId || "").trim();
    if (!cleanId) return;
    const grp = this.store.state?.device_groups?.find((g) => g.id === cleanId);
    const name = groupName || grp?.name || cleanId;
    const count =
      memberCount ??
      (this.store.state?.system_devices || []).filter(
        (d) => d.kind !== "ble_tag" && d.device_group === cleanId,
      ).length;
    this.store.openConfirm({
      kind: "delete_group",
      title: this.store.t("confirm.delete_group.title", { name }),
      consequence: this.store.t("confirm.delete_group.body"),
      confirmLabel: this.store.t("confirm.delete_group.confirm"),
      danger: true,
      blastRadiusCount: count > 0 ? count : null,
      onConfirm: async () => {
        await this.deleteDeviceGroup(cleanId);
      },
    });
  }

  async resetDeviceGroupPreset(groupId: string, groupName?: string): Promise<void> {
    const cleanId = String(groupId || "").trim();
    if (!cleanId) return;
    const grp = this.store.state?.device_groups?.find((g) => g.id === cleanId);
    const name = groupName || grp?.name || cleanId;
    try {
      const res = await this.store.ws.runSystemCommand(
        "update_group_baseline",
        {
          group_id: cleanId,
          reset_to_default: true,
        },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast(this.store.t("groups.reset_preset_toast", { name }));
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not reset group preset"), true);
    }
  }

  requestResetDeviceGroup(groupId: string, groupName?: string, memberCount?: number): void {
    const cleanId = String(groupId || "").trim();
    if (!cleanId) return;
    const grp = this.store.state?.device_groups?.find((g) => g.id === cleanId);
    const name = groupName || grp?.name || cleanId;
    const count =
      memberCount ??
      (this.store.state?.system_devices || []).filter(
        (d) => d.kind !== "ble_tag" && d.device_group === cleanId,
      ).length;
    this.store.openConfirm({
      kind: "reset_group",
      title: this.store.t("confirm.reset_group.title", { name }),
      consequence: this.store.t("confirm.reset_group.body"),
      confirmLabel: this.store.t("confirm.reset_group.confirm"),
      danger: false,
      blastRadiusCount: count > 0 ? count : null,
      onConfirm: async () => {
        await this.resetDeviceGroupPreset(cleanId, name);
      },
    });
  }

  async updateGroupBaseline(groupId: string, patch: Record<string, unknown>): Promise<void> {
    if (!groupId) return;
    try {
      const res = await this.store.ws.runSystemCommand(
        "update_group_baseline",
        {
          group_id: groupId,
          config: patch,
        },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.announcePolite(this.store.t("shell.saved_status"));
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not update group baseline"), true);
    }
  }

  async updateGroupScope(
    groupId: string,
    scope: { include_display?: boolean; include_interface?: boolean },
  ): Promise<void> {
    if (!groupId) return;
    try {
      const res = await this.store.ws.runSystemCommand(
        "update_group_baseline",
        {
          group_id: groupId,
          ...scope,
        },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.announcePolite(this.store.t("shell.saved_status"));
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not update group scope"), true);
    }
  }

  async copyDeviceToGroupBaseline(
    groupId: string,
    sourceSubentryId: string,
    copyKeys?: string[],
  ): Promise<void> {
    if (!groupId || !sourceSubentryId) {
      this.store.showToast("Choose a Device to copy settings from", true);
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
      const res = await this.store.ws.runSystemCommand(
        "update_group_baseline",
        payload,
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Copied Device settings into group baseline");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not copy Device settings"), true);
    }
  }

  // ---------- Staged Batch Controls Delegation ----------

  resolvedBatchTargetId(): string {
    return this.batch.resolvedBatchTargetId();
  }
  setBatchTargetFilter(nextFilter: string): void {
    this.batch.setBatchTargetFilter(nextFilter);
  }
  matchingBatchDevices(): SystemDeviceEntry[] {
    return this.batch.matchingBatchDevices();
  }
  filteredControlTargets(ctrl: SharedControlItem): SharedControlTarget[] {
    return this.batch.filteredControlTargets(ctrl);
  }
  getEffectiveBatchValue(ctrl: SharedControlItem): {
    value: string;
    mixed: boolean;
    staged: boolean;
  } {
    return this.batch.getEffectiveBatchValue(ctrl);
  }
  getEffectiveBatchPillStates(ctrl: SharedControlItem): BatchPillState[] {
    return this.batch.getEffectiveBatchPillStates(ctrl);
  }
  stageBatchSetting(key: string, value: unknown): void {
    this.batch.stageBatchSetting(key, value);
  }
  stageBatchColor(ctrl: SharedControlItem, hex: string): void {
    this.batch.stageBatchColor(ctrl, hex);
  }
  stageBatchPillToggle(
    ctrl: SharedControlItem,
    rawToken: string,
    forceEnabled?: boolean,
  ): void {
    this.batch.stageBatchPillToggle(ctrl, rawToken, forceEnabled);
  }
  resetBatchDraft(): void {
    this.batch.resetBatchDraft();
  }
  previewBatchDetachmentCount(): number {
    return this.batch.previewBatchDetachmentCount();
  }
  requestApplyBatchDraft(): void {
    this.batch.requestApplyBatchDraft();
  }
  async applyBatchDraft(): Promise<void> {
    await this.batch.applyBatchDraft();
  }
  async applyBatchCopyFromDevice(sourceSubentryId: string, copyKeys: string[]): Promise<void> {
    await this.batch.applyBatchCopyFromDevice(sourceSubentryId, copyKeys);
  }

  // ---------- Walk-Around BLE Calibration & Area Fusion Delegation ----------

  selectBleSurveyDevice(subentryId: string): void {
    selectBleSurveyDeviceOp(this.store, subentryId);
  }
  selectBleCalibrateArea(areaId: string, fromAreaCard = false): void {
    selectBleCalibrateAreaOp(this.store, areaId, fromAreaCard);
  }
  toggleBleLiveStream(enabled: boolean): void {
    toggleBleLiveStreamOp(this.store, enabled);
  }
  getActiveSurveyDevice(): SystemDeviceEntry | undefined {
    return getActiveSurveyDeviceOp(this.store);
  }
  async setBleScannerOffset(scannerSource: string, offsetDb: number): Promise<void> {
    await setBleScannerOffsetOp(this.store, scannerSource, offsetDb);
  }
  async captureBleAreaSignature(areaId: string): Promise<void> {
    await captureBleAreaSignatureOp(this.store, areaId);
  }
  async clearBleAreaSignature(areaId: string): Promise<void> {
    await clearBleAreaSignatureOp(this.store, areaId);
  }
  requestClearBleAreaSignature(areaId: string, areaName?: string): void {
    requestClearBleAreaSignatureOp(this.store, areaId, areaName);
  }
  async setAreaFusion(
    areaId: string,
    update: { mode?: string; threshold_pct?: number; sensors?: string[] },
  ): Promise<void> {
    await setAreaFusionOp(this.store, areaId, update);
  }
  async setAreaIlluminance(
    areaId: string,
    update: { entity_id?: string; dark_lux?: number; bright_lux?: number },
  ): Promise<void> {
    await setAreaIlluminanceOp(this.store, areaId, update);
  }
  async calibrateAreaIlluminance(areaId?: string): Promise<void> {
    await calibrateAreaIlluminanceOp(this.store, this, areaId);
  }
}
