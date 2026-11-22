/**
 * `store.tools` Controller (`ToolsController`, `D-064` / `Q5`, `D-066`):
 * - Shared confirmation dialog orchestration (`confirmModal`, `openConfirm`, `closeConfirm`, `runConfirmedAction`)
 * - Security PIN, HMAC signing key rotation, System & Device diagnostics, & Support version copy
 * - Modals (`colorWheelModal.painted`, `removeModal`, `resetModal`, `addBleModal`)
 * - Discovered `adopt` (with post-adopt jump to `adopted_subentry_id` `E-10`) + `ignore` / `unignore`
 * - Announcements, strict v3 backup/restore, & timezone-formatted System/Device logs
 */

import { formatWsError } from "../api/ws-client.js";
import { STUDIO_REV } from "../constants.js";
import type { CustomPalette, StudioScope } from "../types.js";
import {
  copyTextToClipboard,
  defaultThemeHex,
  fmtDateTime,
  isValidHexColor,
  triggerJsonDownload,
} from "../utils/format.js";
import {
  type ConfirmModalState,
  emptyConfirmModalState,
  type OpenConfirmOptions,
  type StudioStoreContext,
  type ToolsControllerContract,
} from "./store-types.js";

export { type ConfirmModalState, emptyConfirmModalState, type OpenConfirmOptions };

export class ToolsController implements ToolsControllerContract {
  private readonly store: StudioStoreContext;

  constructor(store: StudioStoreContext) {
    this.store = store;
  }

  // ---------- Shared Confirmation Dialog (`Q5` / `D-064`) ----------

  openConfirm(opts: OpenConfirmOptions): void {
    this.store.confirmModal = {
      open: true,
      kind: opts.kind || "confirm",
      title: opts.title,
      consequence: opts.consequence,
      confirmLabel: opts.confirmLabel,
      cancelLabel: opts.cancelLabel || this.store.t("action.cancel"),
      danger: opts.danger !== false,
      blastRadiusCount: opts.blastRadiusCount ?? null,
      blastRadiusLabel: opts.blastRadiusLabel || "",
      busy: false,
      onConfirm: opts.onConfirm,
      onDownloadBackupFirst: opts.onDownloadBackupFirst ?? null,
    };
    this.store.host.requestUpdate();
  }

  closeConfirm(): void {
    if (this.store.confirmModal.busy) return;
    this.store.confirmModal = emptyConfirmModalState();
    this.store.host.requestUpdate();
  }

  async runConfirmedAction(): Promise<void> {
    const action = this.store.confirmModal.onConfirm;
    if (!action || this.store.confirmModal.busy) return;
    this.store.confirmModal = { ...this.store.confirmModal, busy: true };
    this.store.host.requestUpdate();
    try {
      await action();
      this.store.confirmModal = emptyConfirmModalState();
    } finally {
      if (this.store.confirmModal.busy) {
        this.store.confirmModal = { ...this.store.confirmModal, busy: false };
      }
      this.store.host.requestUpdate();
    }
  }

  // ---------- Security PIN & Signing Key Rotation ----------

  async saveSecurityPin(fromScope: StudioScope): Promise<void> {
    const rawPin = (
      fromScope === "device" ? this.store.devicePinDraft : this.store.systemPinDraft
    ).trim();
    if (!/^\d{4,12}$/.test(rawPin)) {
      this.store.showToast("Security PIN must be 4 to 12 digits", true);
      return;
    }
    const targetSubentryId = fromScope === "device" ? this.store.activeSubentryId : "";
    this.store.pinBusy = true;
    this.store.host.requestUpdate();
    try {
      const payload: Record<string, unknown> = { pin: rawPin };
      if (targetSubentryId) payload.subentry_id = targetSubentryId;
      const res = await this.store.ws.runSystemCommand(
        "set_security_pin",
        payload,
        this.store.activeSubentryId || null,
      );
      this.store.devicePinDraft = "";
      this.store.systemPinDraft = "";
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Saved security PIN");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not save security PIN"), true);
    } finally {
      this.store.pinBusy = false;
      this.store.host.requestUpdate();
    }
  }

  async clearSecurityPin(fromScope: StudioScope): Promise<void> {
    const targetSubentryId = fromScope === "device" ? this.store.activeSubentryId : "";
    this.store.pinBusy = true;
    this.store.host.requestUpdate();
    try {
      const payload: Record<string, unknown> = { clear: true };
      if (targetSubentryId) payload.subentry_id = targetSubentryId;
      const res = await this.store.ws.runSystemCommand(
        "set_security_pin",
        payload,
        this.store.activeSubentryId || null,
      );
      this.store.devicePinDraft = "";
      this.store.systemPinDraft = "";
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Cleared security PIN");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not clear security PIN"), true);
    } finally {
      this.store.pinBusy = false;
      this.store.host.requestUpdate();
    }
  }

  requestClearSecurityPin(fromScope: StudioScope): void {
    const displayCount =
      fromScope === "system"
        ? (this.store.state?.system_devices || []).filter((d) => d.kind !== "ble_tag").length
        : 1;
    this.openConfirm({
      kind: "clear_pin",
      title: this.store.t("confirm.clear_pin.title"),
      consequence: this.store.t("confirm.clear_pin.body"),
      confirmLabel: this.store.t("confirm.clear_pin.confirm"),
      danger: true,
      blastRadiusCount: displayCount > 0 ? displayCount : null,
      onConfirm: async () => {
        await this.clearSecurityPin(fromScope);
      },
    });
  }

  async rotateSigningKey(): Promise<void> {
    try {
      const res = await this.store.ws.runSystemCommand(
        "rotate_signing_key",
        {},
        this.store.activeSubentryId || null,
      );
      this.store.entity.clearCameraPreviewCache();
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Rotated HTTP resource signing key");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not rotate signing key"), true);
    }
  }

  requestRotateSigningKey(): void {
    const displayCount = (this.store.state?.system_devices || []).filter(
      (d) => d.kind !== "ble_tag",
    ).length;
    this.openConfirm({
      kind: "rotate_signing_key",
      title: this.store.t("confirm.rotate_signing_key.title"),
      consequence: this.store.t("confirm.rotate_signing_key.body"),
      confirmLabel: this.store.t("confirm.rotate_signing_key.confirm"),
      danger: true,
      blastRadiusCount: displayCount > 0 ? displayCount : null,
      onConfirm: async () => {
        await this.rotateSigningKey();
      },
    });
  }

  // ---------- Diagnostics & Support Card (`D-066`) ----------

  private async resolveConfigEntryId(): Promise<string> {
    const fromLinks = this.store.state?.links?.entry_id || "";
    if (fromLinks) return fromLinks;
    const hass = this.store.hass;
    if (!hass) return "";
    try {
      const entries = await hass.callWS<Array<{ entry_id?: string }>>({
        type: "config_entries/get",
        domain: "latter",
      });
      return String(entries?.[0]?.entry_id || "");
    } catch {
      return "";
    }
  }

  private async triggerSignedPathDownload(rawPath: string): Promise<void> {
    const signedPath = await this.store.ws.signHaPath(rawPath, 300);
    const a = document.createElement("a");
    a.href = signedPath;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  async downloadDeviceDiagnostics(): Promise<void> {
    const entryId = await this.resolveConfigEntryId();
    const latterDeviceId = this.store.state?.links?.latter_device_id || "";
    if (!entryId) {
      this.store.showToast("Diagnostics entry ID is not available", true);
      return;
    }
    const rawPath = latterDeviceId
      ? `/api/diagnostics/config_entry/${encodeURIComponent(entryId)}/device/${encodeURIComponent(latterDeviceId)}`
      : `/api/diagnostics/config_entry/${encodeURIComponent(entryId)}`;
    try {
      await this.triggerSignedPathDownload(rawPath);
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not download diagnostics"), true);
    }
  }

  async downloadSystemDiagnostics(): Promise<void> {
    const entryId = await this.resolveConfigEntryId();
    if (!entryId) {
      this.store.showToast("Diagnostics entry ID is not available", true);
      return;
    }
    const rawPath = `/api/diagnostics/config_entry/${encodeURIComponent(entryId)}`;
    try {
      await this.triggerSignedPathDownload(rawPath);
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not download System diagnostics"), true);
    }
  }

  formatSystemInfoSummary(): string {
    const info = this.store.state?.system_info;
    const haVer = info?.ha_version || this.store.hass?.config?.version || "—";
    const intVer = info?.integration_version || this.store.state?.version || "—";
    const sdkRev = info?.min_firmware_sdk_rev
      ? String(info.min_firmware_sdk_rev)
      : "—";
    const studioRev = String(info?.studio_rev ?? STUDIO_REV);
    const devs = this.store.state?.system_devices || [];
    const displayCount = devs.filter((d) => d.kind !== "ble_tag").length;
    const bleTagCount = devs.filter((d) => d.kind === "ble_tag").length;
    return [
      `Home Assistant: ${haVer}`,
      `Latter integration: v${intVer}`,
      `Minimum firmware SDK: ${sdkRev}`,
      `Studio contract: rev ${studioRev}`,
      `Managed Devices: ${devs.length} (${displayCount} displays, ${bleTagCount} BLE trackers)`,
    ].join("\n");
  }

  async copySystemInfoSummary(): Promise<void> {
    const root =
      (this.store.host as unknown as { renderRoot?: ShadowRoot }).renderRoot ||
      this.store.host.shadowRoot;
    const ok = await copyTextToClipboard(this.formatSystemInfoSummary(), root);
    this.store.showToast(
      ok ? this.store.t("support.copied_summary") : "Could not copy version summary",
      !ok,
    );
  }

  // ---------- Color Wheel Modal (`A-24`: per-store `painted` flag) ----------

  openColorWheelModal(targetScope: StudioScope): void {
    const initial =
      targetScope === "device" && isValidHexColor(this.store.state?.config?.device_custom_color)
        ? String(this.store.state?.config?.device_custom_color).toUpperCase()
        : defaultThemeHex(this.store.host);
    this.store.colorWheelModal = {
      open: true,
      targetScope,
      hex: initial,
      name: "",
      busy: false,
      painted: this.store.colorWheelModal.painted,
    };
    this.store.host.requestUpdate();
  }

  closeColorWheelModal(): void {
    this.store.colorWheelModal = {
      ...this.store.colorWheelModal,
      open: false,
      busy: false,
    };
    this.store.host.requestUpdate();
  }

  async saveColorWheelSelection(): Promise<void> {
    const hex = this.store.colorWheelModal.hex.trim().toUpperCase();
    if (!isValidHexColor(hex)) {
      this.store.showToast("Enter a valid 6-digit hex color", true);
      return;
    }
    this.store.colorWheelModal = { ...this.store.colorWheelModal, busy: true };
    this.store.host.requestUpdate();
    try {
      const name = this.store.colorWheelModal.name.trim() || hex;
      const existing: CustomPalette[] = [
        ...(this.store.state?.system_config?.custom_palettes || []),
      ];
      if (!existing.some((p) => p.hex.toUpperCase() === hex)) {
        existing.push({ name, hex });
        this.store.entity.stageSystemSetting("custom_palettes", existing);
        await this.store.entity.flushSystemSettings();
      }
      if (this.store.colorWheelModal.targetScope === "device" && this.store.activeSubentryId) {
        this.store.entity.applyDeviceCustomColor(hex, true);
        await this.store.entity.flushDeviceBucket(this.store.activeSubentryId);
      }
      this.closeColorWheelModal();
    } finally {
      if (this.store.colorWheelModal.busy) {
        this.store.colorWheelModal = { ...this.store.colorWheelModal, busy: false };
        this.store.host.requestUpdate();
      }
    }
  }

  // ---------- Remove & Reset Device Modals ----------

  openRemoveDeviceModal(subentryId: string, title: string): void {
    if (!subentryId) return;
    this.store.removeModal = {
      open: true,
      subentryId,
      title: title || "Device",
      busy: false,
    };
    this.store.host.requestUpdate();
  }

  closeRemoveDeviceModal(): void {
    this.store.removeModal = { ...this.store.removeModal, open: false, busy: false };
    this.store.host.requestUpdate();
  }

  async removeDeviceById(subentryId: string): Promise<void> {
    const subId = String(subentryId || "").trim();
    if (!subId) return;
    try {
      this.store.entity.discardDeviceBucket(subId);
      const res = await this.store.ws.runSystemCommand(
        "remove_device",
        { subentry_id: subId },
        this.store.activeSubentryId || null,
      );
      this.closeRemoveDeviceModal();
      if (this.store.activeSubentryId === subId) {
        this.store.onActiveDeviceChanged(subId, "", { discardPrevPending: true });
        this.store.currentScope = "device";
        this.store.currentViewId = "select_device_prompt";
        this.store.syncUrl(true);
      }
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast("Removed Device from Latter");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not remove Device"), true);
      throw err;
    }
  }

  async confirmRemoveDevice(): Promise<void> {
    const subId = this.store.removeModal.subentryId;
    if (!subId) return;
    this.store.removeModal = { ...this.store.removeModal, busy: true };
    this.store.host.requestUpdate();
    try {
      await this.removeDeviceById(subId);
    } catch {
      this.store.removeModal = { ...this.store.removeModal, busy: false };
      this.store.host.requestUpdate();
    }
  }

  requestRemoveDevice(subentryId: string, title: string): void {
    const subId = String(subentryId || "").trim();
    if (!subId) return;
    const cleanTitle = title || "Device";
    this.openConfirm({
      kind: "remove_device",
      title: this.store.t("confirm.remove_device.title", { title: cleanTitle }),
      consequence: this.store.t("confirm.remove_device.body", { title: cleanTitle }),
      confirmLabel: this.store.t("confirm.remove_device.confirm"),
      danger: true,
      blastRadiusCount: 1,
      onDownloadBackupFirst: () => {
        void this.exportBackup(subId);
      },
      onConfirm: async () => {
        await this.removeDeviceById(subId);
      },
    });
  }

  openResetDeviceModal(): void {
    if (!this.store.activeSubentryId) return;
    const isBleTag = this.store.state?.config?.kind === "ble_tag";
    this.store.resetModal = {
      open: true,
      deviceSettings: !isBleTag,
      latterOptions: true,
      busy: false,
    };
    this.store.host.requestUpdate();
  }

  closeResetDeviceModal(): void {
    this.store.resetModal = { ...this.store.resetModal, open: false, busy: false };
    this.store.host.requestUpdate();
  }

  async confirmResetDevice(): Promise<void> {
    const targetSubentryId = this.store.activeSubentryId;
    if (!targetSubentryId) return;
    if (!this.store.resetModal.deviceSettings && !this.store.resetModal.latterOptions) return;
    this.store.resetModal = { ...this.store.resetModal, busy: true };
    this.store.host.requestUpdate();
    try {
      this.store.entity.discardDeviceBucket(targetSubentryId);
      const res = await this.store.ws.resetDevice({
        subentryId: targetSubentryId,
        deviceSettings: this.store.resetModal.deviceSettings,
        latterOptions: this.store.resetModal.latterOptions,
      });
      this.closeResetDeviceModal();
      if (res && this.store.activeSubentryId === targetSubentryId) {
        this.store.ingestPayload(res, false);
      }
      this.store.showToast("Reset Device to defaults");
    } catch (err) {
      this.store.resetModal = { ...this.store.resetModal, busy: false };
      this.store.showToast(formatWsError(err, "Could not reset Device"), true);
      this.store.host.requestUpdate();
    }
  }

  // ---------- Discovered Devices: Adopt (`E-10`), Ignore, & Add BLE Tag ----------

  openAddBleModal(prefill?: { name?: string; address?: string }): void {
    this.store.addBleModal = {
      open: true,
      candidateAddr: prefill?.address || "",
      name: prefill?.name || "",
      address: prefill?.address || "",
      assignedPerson: "",
      bleCategory: "auto",
      busy: false,
    };
    this.store.host.requestUpdate();
  }

  closeAddBleModal(): void {
    this.store.addBleModal = { ...this.store.addBleModal, open: false, busy: false };
    this.store.host.requestUpdate();
  }

  selectBleCandidateInModal(addr: string): void {
    const cand = (this.store.state?.discovered_ble_devices || []).find(
      (c) => c.target_address === addr,
    );
    const candAddr = cand ? cand.target_address || addr : addr;
    const candTitle = cand ? cand.title || "" : "";
    this.store.addBleModal = {
      ...this.store.addBleModal,
      candidateAddr: addr,
      address: cand ? candAddr : this.store.addBleModal.address,
      name: candTitle || this.store.addBleModal.name,
    };
    this.store.host.requestUpdate();
  }

  async adoptLatterDevice(
    esphomeDeviceId: string,
    title: string,
    deviceGroup = "auto",
    assignedPerson = "",
  ): Promise<void> {
    if (!esphomeDeviceId) return;
    try {
      const res = await this.store.ws.runSystemCommand(
        "add_latter_device",
        {
          esphome_device_id: esphomeDeviceId,
          device_group: deviceGroup || "auto",
          assigned_person: assignedPerson,
        },
        this.store.activeSubentryId || null,
      );
      this.store.discoveredLatterGroupDrafts.delete(esphomeDeviceId);
      this.store.discoveredLatterPersonDrafts.delete(esphomeDeviceId);
      if (res) {
        this.store.ingestPayload(res, false);
        if (res.adopted_subentry_id) {
          await this.store.switchSystemDevice(res.adopted_subentry_id, "dashboard");
        }
      }
      this.store.showToast(
        this.store.t("discovered.adopted_toast", { title: title || "Device" }),
      );
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not adopt Latter Device"), true);
    }
  }

  async ignoreDiscoveredDevice(esphomeDeviceId: string, title?: string): Promise<void> {
    const cleanId = String(esphomeDeviceId || "").trim();
    if (!cleanId) return;
    try {
      const res = await this.store.ws.runSystemCommand(
        "ignore_discovered_device",
        { esphome_device_id: cleanId },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast(
        this.store.t("discovered.ignored_toast", { title: title || cleanId }),
      );
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not ignore discovered Device"), true);
    }
  }

  async unignoreDiscoveredDevice(esphomeDeviceId: string, title?: string): Promise<void> {
    const cleanId = String(esphomeDeviceId || "").trim();
    if (!cleanId) return;
    try {
      const res = await this.store.ws.runSystemCommand(
        "unignore_discovered_device",
        { esphome_device_id: cleanId },
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast(
        this.store.t("discovered.restored_toast", { title: title || cleanId }),
      );
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not restore discovered Device"), true);
    }
  }

  async quickAdoptBleCandidate(
    title: string,
    targetAddress: string,
    assignedPerson = "",
    bleCategory = "auto",
  ): Promise<void> {
    if (!title || !targetAddress) return;
    try {
      const res = await this.store.ws.runSystemCommand(
        "add_ble_device",
        {
          name: title,
          target_address: targetAddress,
          assigned_person: assignedPerson,
          ble_category: bleCategory || "auto",
        },
        this.store.activeSubentryId || null,
      );
      this.store.evictAdoptedBleCandidate(targetAddress);
      if (res) {
        this.store.ingestPayload(res, false);
        if (res.adopted_subentry_id) {
          await this.store.switchSystemDevice(res.adopted_subentry_id, "dashboard");
        }
      }
      this.store.showToast(this.store.t("discovered.adopted_toast", { title }));
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not add BLE tag"), true);
    }
  }

  async confirmAddBleModal(): Promise<void> {
    const name = this.store.addBleModal.name.trim();
    const targetAddress = this.store.addBleModal.address.trim();
    if (!name || !targetAddress) {
      this.store.showToast("Enter both a name and a Bluetooth address or entity", true);
      return;
    }
    this.store.addBleModal = { ...this.store.addBleModal, busy: true };
    this.store.host.requestUpdate();
    try {
      const res = await this.store.ws.runSystemCommand(
        "add_ble_device",
        {
          name,
          target_address: targetAddress,
          assigned_person: this.store.addBleModal.assignedPerson,
          ble_category: this.store.addBleModal.bleCategory || "auto",
        },
        this.store.activeSubentryId || null,
      );
      this.store.evictAdoptedBleCandidate(targetAddress);
      this.closeAddBleModal();
      if (res) {
        this.store.ingestPayload(res, false);
        if (res.adopted_subentry_id) {
          await this.store.switchSystemDevice(res.adopted_subentry_id, "dashboard");
        }
      }
      this.store.showToast(this.store.t("discovered.adopted_toast", { title: name }));
    } catch (err) {
      this.store.addBleModal = { ...this.store.addBleModal, busy: false };
      this.store.showToast(formatWsError(err, "Could not add BLE tag"), true);
      this.store.host.requestUpdate();
    }
  }

  // ---------- Firmware Updates, Announcements, Backup & Restore, & Logs ----------

  async checkSystemUpdates(): Promise<void> {
    this.store.showToast("Checking firmware updates…");
    try {
      const res = await this.store.ws.runSystemCommand(
        "check_system_updates",
        {},
        this.store.activeSubentryId || null,
      );
      if (res) {
        this.store.ingestPayload(res, false);
        const info = res.update_check;
        if (info) {
          this.store.showToast(
            info.available > 0
              ? `${info.available} firmware update(s) available across ${info.checked} checked Device(s)`
              : `Checked ${info.checked} Device(s) — all firmware is up to date`,
          );
          return;
        }
      }
      this.store.showToast("Firmware update check finished");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Firmware update check failed"), true);
    }
  }

  async sendAnnouncement(): Promise<void> {
    const message = this.store.announceMessage.trim();
    if (!message) {
      this.store.showToast("Enter a message", true);
      return;
    }
    const payload: Record<string, unknown> = {
      mode: this.store.announceMode,
      target_device: this.store.announceTarget || "all",
      message,
    };
    if (this.store.announceMode === "notify") {
      const title = this.store.announceTitle.trim();
      if (!title) {
        this.store.showToast("Enter a notification title", true);
        return;
      }
      payload.title = title;
      payload.priority = this.store.announcePriority;
      payload.include_camera = this.store.announceIncludeCamera;
    }
    try {
      const res = await this.store.ws.runSystemCommand(
        "send_announcement",
        payload,
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast(
        this.store.announceMode === "notify"
          ? "Sent notification"
          : "Broadcast announcement sent",
      );
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not send announcement"), true);
    }
  }

  async exportBackup(explicitSubentryId?: string): Promise<void> {
    try {
      const dateStr = new Date().toISOString().slice(0, 10);
      if (explicitSubentryId) {
        const { bundle } = await this.store.ws.exportBackup("device", explicitSubentryId);
        const slug = String(
          bundle.target_device || this.store.state?.config?.device_slug || "esphome",
        );
        triggerJsonDownload(`latter-device-${slug}-backup-${dateStr}.json`, bundle);
        this.store.showToast("Downloaded the Device backup");
        return;
      }
      const choice = this.store.backupExportScope || "system";
      const deviceId = choice.startsWith("device:")
        ? choice.slice(7)
        : choice !== "system"
          ? choice
          : "";
      if (!deviceId) {
        const { bundle } = await this.store.ws.exportBackup("system");
        triggerJsonDownload(`latter-system-backup-${dateStr}.json`, bundle);
        this.store.showToast("Downloaded the System backup");
      } else {
        const { bundle } = await this.store.ws.exportBackup("device", deviceId);
        const slug = String(bundle.target_device || deviceId);
        triggerJsonDownload(`latter-device-${slug}-backup-${dateStr}.json`, bundle);
        this.store.showToast("Downloaded the Device backup");
      }
    } catch (err) {
      this.store.showToast(formatWsError(err, "Backup export failed"), true);
    }
  }

  private async parseBackupBundleFile(): Promise<{
    bundle: Record<string, unknown>;
    scope: StudioScope;
    targetId: string;
  } | null> {
    if (!this.store.selectedBackupFile) {
      this.store.showToast("Choose a JSON backup file first", true);
      return null;
    }
    const text = await this.store.selectedBackupFile.text();
    const parsed = JSON.parse(text) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("Invalid backup JSON format");
    }
    const bundle = parsed as Record<string, unknown>;
    const rawScope = String(bundle.scope || "");
    if (rawScope !== "system" && rawScope !== "device") {
      throw new Error("Backup file is missing a valid 'system' or 'device' scope");
    }
    const scope: StudioScope = rawScope;
    const targetId = scope === "device" ? this.store.backupRestoreSubentryId || "" : "";
    if (scope === "device" && !targetId) {
      this.store.showToast("Choose the Device to restore this Device backup onto", true);
      return null;
    }
    return { bundle, scope, targetId };
  }

  async restoreFromUploadedFile(): Promise<void> {
    try {
      const parsed = await this.parseBackupBundleFile();
      if (!parsed) return;
      const { bundle, scope, targetId } = parsed;
      const res = await this.store.ws.importBackup({
        scope,
        bundle,
        targetSubentryId: targetId || null,
        selectedSubentryId: this.store.activeSubentryId || null,
      });
      this.store.selectedBackupFile = null;
      this.store.mergeDomRevert({ "input-restore-backup": "" });
      if (res) this.store.ingestPayload(res, false);
      this.store.showToast(
        scope === "device" ? "Restored the Device backup" : "Restored the System backup",
      );
    } catch (err) {
      this.store.showToast(formatWsError(err, "Backup restore failed"), true);
    }
  }

  async requestRestoreFromUploadedFile(): Promise<void> {
    try {
      const parsed = await this.parseBackupBundleFile();
      if (!parsed) return;
      const { scope, targetId } = parsed;
      const blastCount =
        scope === "device"
          ? 1
          : Math.max(1, (this.store.state?.system_devices || []).length);
      this.openConfirm({
        kind: "restore_backup",
        title: this.store.t("confirm.restore_backup.title"),
        consequence: this.store.t("confirm.restore_backup.body"),
        confirmLabel: this.store.t("confirm.restore_backup.confirm"),
        danger: true,
        blastRadiusCount: blastCount,
        onDownloadBackupFirst: () => {
          void this.exportBackup(scope === "device" ? targetId : undefined);
        },
        onConfirm: async () => {
          await this.restoreFromUploadedFile();
        },
      });
    } catch (err) {
      this.store.showToast(formatWsError(err, "Backup restore failed"), true);
    }
  }

  onToggleLogsDetails(open: boolean): void {
    if (this.store.logsOpen === open) return;
    this.store.logsOpen = open;
    this.store.host.requestUpdate();
    void this.store.ensureSubscription(false);
  }

  formatVisibleLogs(): string {
    const entries = this.store.state?.internal_logs || [];
    const filter = this.store.logFilter || "all";
    const filtered = entries.filter((e) => {
      const lvl = String(e.level || "").toUpperCase();
      const src = String(e.source || "").toLowerCase();
      if (filter === "latter") {
        return src === "studio" || src === "system" || src.includes("latter");
      }
      if (filter === "errors") {
        return lvl === "WARNING" || lvl === "WARN" || lvl === "ERROR" || lvl === "CRITICAL";
      }
      if (filter.startsWith("device:")) {
        const slug = filter.slice(7).toLowerCase();
        return src === slug || String(e.message || "").toLowerCase().includes(slug);
      }
      return true;
    });
    if (!filtered.length) return "No events logged yet.";
    return filtered
      .map((e) => {
        const rawTs = e.timestamp ?? e.ts ?? "";
        const formattedTs = rawTs !== "" ? fmtDateTime(rawTs, this.store.hass) : "";
        const lvl = String(e.level || "INFO").toUpperCase();
        const src = String(e.source || "latter");
        return `${formattedTs ? `[${formattedTs}] ` : ""}${lvl} (${src}): ${String(e.message || "")}`;
      })
      .join("\n");
  }

  async copyLogsToClipboard(): Promise<void> {
    const root =
      (this.store.host as unknown as { renderRoot?: ShadowRoot }).renderRoot ||
      this.store.host.shadowRoot;
    const ok = await copyTextToClipboard(this.formatVisibleLogs(), root);
    this.store.showToast(ok ? "Copied logs to clipboard" : "Could not copy logs", !ok);
  }

  async clearInternalLogs(): Promise<void> {
    try {
      const res = await this.store.ws.runSystemCommand(
        "clear_internal_logs",
        {},
        this.store.activeSubentryId || null,
      );
      if (res) this.store.ingestPayload(res, true);
      this.store.showToast("Cleared internal logs");
    } catch (err) {
      this.store.showToast(formatWsError(err, "Could not clear logs"), true);
    }
  }
}
