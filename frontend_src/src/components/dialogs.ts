/**
 * Modular Native `<dialog>` Orchestrator for Latter Studio (`D-053`, `D-062`, `D-064`).
 * - Two-pass close-before-open orchestration so two modals are never open simultaneously
 * - Closed `<dialog>` shells render empty (`!modal.open` short-circuit)
 * - Uses native `showModal()` lifecycle and per-store `colorWheelModal.painted` state (no module globals)
 */

import { html, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import {
  renderAppConfigDialog,
  renderAppConfigModalBody,
} from "./dialogs/app-config.js";
import { renderCameraConfigDialog } from "./dialogs/camera-config-modal.js";
import {
  renderColorWheelDialog,
  syncColorWheelCanvas,
} from "./dialogs/color-wheel.js";
import {
  renderAddBleDialog,
  renderRemoveDeviceDialog,
  renderResetDeviceDialog,
  renderSaveGroupDialog,
} from "./dialogs/device-modals.js";
import { renderMediaImportDialog } from "./dialogs/media-import-modal.js";
import { renderPhotoPickerDialog } from "./dialogs/photo-picker-modal.js";
import {
  renderPhotoEditDialog,
  renderPhotoUploadDialog,
  syncPhotoCropCanvases,
} from "./dialogs/photo-upload-modal.js";
import { renderShortcutDialog } from "./dialogs/shortcut-modal.js";

export { renderAppConfigModalBody };

export function syncStudioDialogs(renderRoot: ShadowRoot, store: StudioStore): void {
  const pairs: Array<[string, boolean]> = [
    ["latter-rm-modal", store.removeModal.open],
    ["latter-reset-modal", store.resetModal.open],
    ["latter-add-dev-modal", store.addBleModal.open],
    ["latter-cw-modal", store.colorWheelModal.open],
    ["latter-save-group-modal", store.saveGroupModal.open],
    ["latter-app-config-modal", store.appConfigModal.open],
    ["latter-camera-config-modal", store.cameraConfigModal.open],
    ["latter-shortcut-modal", store.shortcutModal.open],
    ["latter-photo-upload-modal", store.photoUploadModal.open],
    ["latter-photo-edit-modal", store.photoEditModal.open],
    ["latter-media-import-modal", store.mediaImportModal.open],
    ["latter-photo-picker-modal", store.photoPickerModal.open],
  ];

  // Pass 1: close any open dialog that should now be closed BEFORE opening another modal.
  for (const [id, wantOpen] of pairs) {
    if (wantOpen) continue;
    const dlg = renderRoot.getElementById(id) as HTMLDialogElement | null;
    if (dlg && dlg.open && typeof dlg.close === "function") {
      dlg.close();
    }
  }

  // Pass 2: open the active dialog natively via `showModal()` (never > 1 open simultaneously).
  for (const [id, wantOpen] of pairs) {
    if (!wantOpen) continue;
    const dlg = renderRoot.getElementById(id) as HTMLDialogElement | null;
    if (dlg && !dlg.open && typeof dlg.showModal === "function") {
      dlg.showModal();
    }
  }

  syncColorWheelCanvas(renderRoot, store);
  syncPhotoCropCanvases(renderRoot, store);
}

export function renderStudioDialogs(store: StudioStore): TemplateResult {
  return html`
    ${renderRemoveDeviceDialog(store)}
    ${renderResetDeviceDialog(store)}
    ${renderAddBleDialog(store)}
    ${renderColorWheelDialog(store)}
    ${renderSaveGroupDialog(store)}
    ${renderAppConfigDialog(store)}
    ${renderCameraConfigDialog(store)}
    ${renderShortcutDialog(store)}
    ${renderPhotoUploadDialog(store)}
    ${renderPhotoEditDialog(store)}
    ${renderMediaImportDialog(store)}
    ${renderPhotoPickerDialog(store)}
  `;
}
