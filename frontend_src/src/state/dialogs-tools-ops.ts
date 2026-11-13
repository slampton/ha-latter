/**
 * Security PIN, signing key rotation, diagnostics, modal dialogs (Remove/Reset/Add BLE/Color Wheel),
 * firmware update checks, announcements, backup/restore, and System & Device Logs operations.
 */

import { formatWsError } from "../api/ws-client.js";
import type { CustomPalette, StudioScope } from "../types.js";
import {
  copyTextToClipboard,
  defaultThemeHex,
  fmtDateTime,
  isValidHexColor,
  triggerJsonDownload,
} from "../utils/format.js";
import type { StudioStore } from "./store.js";

export async function saveSecurityPinOp(store: StudioStore, fromScope: StudioScope): Promise<void> {
  const rawPin = (fromScope === "device" ? store.devicePinDraft : store.systemPinDraft).trim();
  if (!/^\d{4,12}$/.test(rawPin)) {
    store.showToast("Security PIN must be 4 to 12 digits", true);
    return;
  }
  const targetSubentryId = fromScope === "device" ? store.activeSubentryId : "";
  store.pinBusy = true;
  store.host.requestUpdate();
  try {
    const payload: Record<string, unknown> = { pin: rawPin };
    if (targetSubentryId) payload.subentry_id = targetSubentryId;
    const res = await store.ws.runSystemCommand(
      "set_security_pin",
      payload,
      store.activeSubentryId || null,
    );
    store.devicePinDraft = "";
    store.systemPinDraft = "";
    if (res) store.ingestPayload(res, false);
    store.showToast("Saved Security PIN");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not save Security PIN"), true);
  } finally {
    store.pinBusy = false;
    store.host.requestUpdate();
  }
}

export async function clearSecurityPinOp(store: StudioStore, fromScope: StudioScope): Promise<void> {
  const targetSubentryId = fromScope === "device" ? store.activeSubentryId : "";
  store.pinBusy = true;
  store.host.requestUpdate();
  try {
    const payload: Record<string, unknown> = { clear: true };
    if (targetSubentryId) payload.subentry_id = targetSubentryId;
    const res = await store.ws.runSystemCommand(
      "set_security_pin",
      payload,
      store.activeSubentryId || null,
    );
    store.devicePinDraft = "";
    store.systemPinDraft = "";
    if (res) store.ingestPayload(res, false);
    store.showToast("Cleared Security PIN");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not clear Security PIN"), true);
  } finally {
    store.pinBusy = false;
    store.host.requestUpdate();
  }
}

export async function rotateSigningKeyOp(store: StudioStore): Promise<void> {
  try {
    const res = await store.ws.runSystemCommand(
      "rotate_signing_key",
      {},
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Rotated HTTP resource signing key");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not rotate signing key"), true);
  }
}

export async function downloadDeviceDiagnosticsOp(store: StudioStore): Promise<void> {
  const entryId = store.state?.links?.entry_id || "";
  const latterDeviceId = store.state?.links?.latter_device_id || "";
  if (!entryId) {
    store.showToast("Diagnostics entry ID is not available", true);
    return;
  }
  const rawPath = latterDeviceId
    ? `/api/diagnostics/config_entry/${encodeURIComponent(entryId)}/device/${encodeURIComponent(latterDeviceId)}`
    : `/api/diagnostics/config_entry/${encodeURIComponent(entryId)}`;
  try {
    const signedPath = await store.ws.signHaPath(rawPath, 300);
    const a = document.createElement("a");
    a.href = signedPath;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not download diagnostics"), true);
  }
}

export function openColorWheelModalOp(store: StudioStore, targetScope: StudioScope): void {
  const initial =
    targetScope === "device" && isValidHexColor(store.state?.config?.device_custom_color)
      ? String(store.state?.config?.device_custom_color).toUpperCase()
      : defaultThemeHex(store.host);
  store.colorWheelModal = {
    open: true,
    targetScope,
    hex: initial,
    name: "",
    busy: false,
  };
  store.host.requestUpdate();
}

export async function saveColorWheelSelectionOp(store: StudioStore): Promise<void> {
  const hex = store.colorWheelModal.hex.trim().toUpperCase();
  if (!isValidHexColor(hex)) {
    store.showToast("Enter a valid 6-digit hex color", true);
    return;
  }
  const name = store.colorWheelModal.name.trim() || hex;
  const existing: CustomPalette[] = [...(store.state?.system_config?.custom_palettes || [])];
  if (!existing.some((p) => p.hex.toUpperCase() === hex)) {
    existing.push({ name, hex });
    store.stageSystemSetting("custom_palettes", existing);
    await store.flushSystemSettings();
  }
  if (store.colorWheelModal.targetScope === "device" && store.activeSubentryId) {
    store.applyDeviceCustomColor(hex, true);
    await store.flushDeviceBucket(store.activeSubentryId);
  }
  store.closeColorWheelModal();
}

export async function confirmRemoveDeviceOp(store: StudioStore): Promise<void> {
  const subId = store.removeModal.subentryId;
  if (!subId) return;
  store.removeModal = { ...store.removeModal, busy: true };
  store.host.requestUpdate();
  try {
    const res = await store.ws.runSystemCommand(
      "remove_device",
      { subentry_id: subId },
      store.activeSubentryId || null,
    );
    store.closeRemoveDeviceModal();
    if (store.activeSubentryId === subId) {
      store.activeSubentryId = "";
      store.deviceSelected = false;
      store.currentScope = "device";
      store.currentViewId = "select_device_prompt";
      store.syncUrl(true);
    }
    if (res) store.ingestPayload(res, false);
    store.showToast("Removed Device from Latter");
  } catch (err) {
    store.removeModal = { ...store.removeModal, busy: false };
    store.showToast(formatWsError(err, "Could not remove Device"), true);
    store.host.requestUpdate();
  }
}

export async function confirmResetDeviceOp(store: StudioStore): Promise<void> {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  if (!store.resetModal.deviceSettings && !store.resetModal.latterOptions) return;
  store.resetModal = { ...store.resetModal, busy: true };
  store.host.requestUpdate();
  try {
    const res = await store.ws.resetDevice({
      subentryId: targetSubentryId,
      deviceSettings: store.resetModal.deviceSettings,
      latterOptions: store.resetModal.latterOptions,
    });
    store.closeResetDeviceModal();
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast("Reset Device to defaults");
  } catch (err) {
    store.resetModal = { ...store.resetModal, busy: false };
    store.showToast(formatWsError(err, "Could not reset Device"), true);
    store.host.requestUpdate();
  }
}

export function selectBleCandidateInModalOp(store: StudioStore, addr: string): void {
  const cand = (store.state?.discovered_ble_devices || []).find(
    (c) => (c.target_address || c.address) === addr,
  );
  const candAddr = cand ? cand.target_address || cand.address || addr : addr;
  const candTitle = cand ? cand.title || cand.name || "" : "";
  store.addBleModal = {
    ...store.addBleModal,
    candidateAddr: addr,
    address: cand ? candAddr : store.addBleModal.address,
    name: candTitle || store.addBleModal.name,
  };
  store.host.requestUpdate();
}

export async function quickAdoptBleCandidateOp(
  store: StudioStore,
  title: string,
  targetAddress: string,
  assignedPerson = "",
): Promise<void> {
  if (!title || !targetAddress) return;
  try {
    const res = await store.ws.runSystemCommand(
      "add_ble_device",
      {
        name: title,
        target_address: targetAddress,
        assigned_person: assignedPerson,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast(`Added BLE tag "${title}"`);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not add BLE tag"), true);
  }
}

export async function confirmAddBleModalOp(store: StudioStore): Promise<void> {
  const name = store.addBleModal.name.trim();
  const targetAddress = store.addBleModal.address.trim();
  if (!name || !targetAddress) {
    store.showToast("Enter both a name and a Bluetooth address or entity", true);
    return;
  }
  store.addBleModal = { ...store.addBleModal, busy: true };
  store.host.requestUpdate();
  try {
    const res = await store.ws.runSystemCommand(
      "add_ble_device",
      {
        name,
        target_address: targetAddress,
        assigned_person: store.addBleModal.assignedPerson,
      },
      store.activeSubentryId || null,
    );
    store.closeAddBleModal();
    if (res) store.ingestPayload(res, false);
    store.showToast(`Added BLE tag "${name}"`);
  } catch (err) {
    store.addBleModal = { ...store.addBleModal, busy: false };
    store.showToast(formatWsError(err, "Could not add BLE tag"), true);
    store.host.requestUpdate();
  }
}

export async function checkSystemUpdatesOp(store: StudioStore): Promise<void> {
  store.showToast("Checking firmware updates…");
  try {
    const res = await store.ws.runSystemCommand(
      "check_system_updates",
      {},
      store.activeSubentryId || null,
    );
    if (res) {
      store.ingestPayload(res, false);
      const info = res.update_check;
      if (info) {
        store.showToast(
          info.available > 0
            ? `${info.available} firmware update(s) available across ${info.checked} checked Device(s)`
            : `Checked ${info.checked} Device(s) — all firmware is up to date`,
        );
        return;
      }
    }
    store.showToast("Firmware update check finished");
  } catch (err) {
    store.showToast(formatWsError(err, "Firmware update check failed"), true);
  }
}

export async function sendAnnouncementOp(store: StudioStore): Promise<void> {
  const message = store.announceMessage.trim();
  if (!message) {
    store.showToast("Enter a message", true);
    return;
  }
  const payload: Record<string, unknown> = {
    mode: store.announceMode,
    target_device: store.announceTarget || "all",
    message,
  };
  if (store.announceMode === "notify") {
    const title = store.announceTitle.trim();
    if (!title) {
      store.showToast("Enter a notification title", true);
      return;
    }
    payload.title = title;
    payload.priority = store.announcePriority;
    payload.include_camera = store.announceIncludeCamera;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "send_announcement",
      payload,
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast(
      store.announceMode === "notify" ? "Sent notification" : "Broadcast announcement sent",
    );
  } catch (err) {
    store.showToast(formatWsError(err, "Could not send announcement"), true);
  }
}

export async function exportBackupOp(store: StudioStore, explicitSubentryId?: string): Promise<void> {
  try {
    const dateStr = new Date().toISOString().slice(0, 10);
    if (explicitSubentryId) {
      const { bundle } = await store.ws.exportBackup("device", explicitSubentryId);
      const slug = String(bundle.target_device || store.state?.config?.device_slug || "esphome");
      triggerJsonDownload(`latter-device-${slug}-backup-${dateStr}.json`, bundle);
      store.showToast("Downloaded the Device backup");
      return;
    }
    const choice = store.backupExportScope || "system";
    const deviceId = choice.startsWith("device:") ? choice.slice(7) : choice !== "system" ? choice : "";
    if (!deviceId) {
      const { bundle } = await store.ws.exportBackup("system");
      triggerJsonDownload(`latter-system-backup-${dateStr}.json`, bundle);
      store.showToast("Downloaded the System backup");
    } else {
      const { bundle } = await store.ws.exportBackup("device", deviceId);
      const slug = String(bundle.target_device || deviceId);
      triggerJsonDownload(`latter-device-${slug}-backup-${dateStr}.json`, bundle);
      store.showToast("Downloaded the Device backup");
    }
  } catch (err) {
    store.showToast(formatWsError(err, "Backup export failed"), true);
  }
}

export async function restoreFromUploadedFileOp(store: StudioStore): Promise<void> {
  if (!store.selectedBackupFile) {
    store.showToast("Choose a JSON backup file first", true);
    return;
  }
  try {
    const text = await store.selectedBackupFile.text();
    const raw = JSON.parse(text) as Record<string, unknown>;
    const bundle =
      raw.bundle && typeof raw.bundle === "object" ? (raw.bundle as Record<string, unknown>) : raw;
    const scope: StudioScope = String(bundle.scope || "") === "device" ? "device" : "system";
    const targetId = scope === "device" ? store.backupRestoreSubentryId || "" : "";
    if (scope === "device" && !targetId) {
      store.showToast("Choose the Device to restore this Device backup onto", true);
      return;
    }
    const res = await store.ws.importBackup({
      scope,
      bundle,
      targetSubentryId: targetId || null,
      selectedSubentryId: store.activeSubentryId || null,
      restoreEspHomeEntities: store.backupRestoreEsp,
    });
    store.selectedBackupFile = null;
    if (res) store.ingestPayload(res, false);
    store.showToast(scope === "device" ? "Restored the Device backup" : "Restored the System backup");
  } catch (err) {
    store.showToast(formatWsError(err, "Backup restore failed"), true);
  }
}

export function formatVisibleLogsOp(store: StudioStore): string {
  const entries = store.state?.internal_logs || [];
  const filter = store.logFilter || "all";
  const filtered = entries.filter((e) => {
    const lvl = String(e.level || "").toUpperCase();
    const src = String(e.source || "").toLowerCase();
    if (filter === "latter") return src === "studio" || src === "system" || src.includes("latter");
    if (filter === "errors") return lvl === "WARNING" || lvl === "WARN" || lvl === "ERROR" || lvl === "CRITICAL";
    if (filter.startsWith("device:") || filter.startsWith("dev:")) {
      const slug = (filter.startsWith("device:") ? filter.slice(7) : filter.slice(4)).toLowerCase();
      return src === slug || String(e.message || "").toLowerCase().includes(slug);
    }
    return true;
  });
  if (!filtered.length) return "No events logged yet.";
  return filtered
    .map((e) => {
      const rawTs = e.timestamp ?? e.ts ?? "";
      const formattedTs = rawTs !== "" ? fmtDateTime(rawTs, store.hass) : "";
      const lvl = String(e.level || "INFO").toUpperCase();
      const src = String(e.source || "latter");
      return `${formattedTs ? `[${formattedTs}] ` : ""}${lvl} (${src}): ${String(e.message || "")}`;
    })
    .join("\n");
}

export async function copyLogsToClipboardOp(store: StudioStore): Promise<void> {
  const ok = await copyTextToClipboard(formatVisibleLogsOp(store));
  store.showToast(ok ? "Copied logs to clipboard" : "Could not copy logs", !ok);
}

export async function clearInternalLogsOp(store: StudioStore): Promise<void> {
  try {
    const res = await store.ws.runSystemCommand(
      "clear_internal_logs",
      {},
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, true);
    store.showToast("Cleared internal logs");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not clear logs"), true);
  }
}
