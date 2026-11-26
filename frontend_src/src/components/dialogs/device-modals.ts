/**
 * Device & Group Lifecycle Modals (`#latter-reset-modal`,
 * `#latter-add-dev-modal`, `#latter-save-group-modal`).
 * - Short-circuits closed `<dialog>` shells
 * - Inline "Download backup first" + explicit consequence text on Remove & Reset
 * - `focusSafe` text inputs across BLE tag & Save custom group forms
 */

import { focusSafe, html, live, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import { renderSelectOptions, renderSwitchRow } from "../controls.js";
import { createDialogBackdropHandlers } from "../controls/aria-helpers.js";

function guardDialogCancel(ev: Event, closeFn: () => void, busy = false): void {
  if (busy) {
    ev.preventDefault();
  } else {
    closeFn();
  }
}

export function renderResetDeviceDialog(store: StudioStore): TemplateResult {
  const rs = store.resetModal;
  const close = (): void => {
    if (store.resetModal.open && !store.resetModal.busy) {
      store.tools.closeResetDeviceModal();
    }
  };
  const backdrop = createDialogBackdropHandlers(close, () => store.resetModal.busy);

  if (!rs.open) {
    return html`<dialog
      id="latter-reset-modal"
      aria-labelledby="latter-reset-title"
      closedby=${rs.busy ? "none" : "any"}
      @cancel=${(ev: Event) => guardDialogCancel(ev, close, rs.busy)}
      @close=${close}
      @pointerdown=${backdrop.onPointerDown}
      @click=${backdrop.onClick}
      class="studio-dialog confirm-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  return html`<dialog
    id="latter-reset-modal"
    aria-labelledby="latter-reset-title"
    aria-describedby="latter-reset-desc"
    closedby=${rs.busy ? "none" : "any"}
    @cancel=${(ev: Event) => guardDialogCancel(ev, close, rs.busy)}
    @close=${close}
    @pointerdown=${backdrop.onPointerDown}
    @click=${backdrop.onClick}
    class="studio-dialog confirm-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h1 id="latter-reset-title" class="dialog-title">
          ${store.t("confirm.reset_device.title")}
        </h1>
        <span class="chip chip-warning confirm-blast-badge">
          ${store.t("confirm.blast_radius_one")}
        </span>
      </div>
      <div class="settings-list">
        ${renderSwitchRow({
          id: "latter-reset-device-settings",
          label: store.t("confirm.reset_device.device_settings"),
          description: store.t("confirm.reset_device.device_settings_desc"),
          disabled: rs.busy,
          checked: rs.deviceSettings,
          onChange: (checked) => {
            store.resetModal = { ...store.resetModal, deviceSettings: checked };
            store.host.requestUpdate();
          },
        })}
        ${renderSwitchRow({
          id: "latter-reset-latter-options",
          label: store.t("confirm.reset_device.latter_options"),
          description: store.t("confirm.reset_device.latter_options_desc"),
          disabled: rs.busy,
          checked: rs.latterOptions,
          onChange: (checked) => {
            store.resetModal = { ...store.resetModal, latterOptions: checked };
            store.host.requestUpdate();
          },
        })}
      </div>
      <p id="latter-reset-desc" class="dialog-text">
        ${store.t("confirm.reset_device.body")}
      </p>
      <div class="dialog-actions with-secondary">
        <button
          type="button"
          ?disabled=${rs.busy || !store.activeSubentryId}
          @click=${() => void store.tools.exportBackup(store.activeSubentryId)}
          class="btn btn-text btn-compact"
        >
          ${store.t("action.download_backup_first")}
        </button>
        <div class="dialog-actions-end">
          <button
            type="button"
            autofocus
            ?disabled=${rs.busy}
            @click=${close}
            class="btn btn-secondary"
          >
            ${store.t("action.cancel")}
          </button>
          <button
            type="button"
            id="latter-reset-confirm-btn"
            ?disabled=${rs.busy || (!rs.deviceSettings && !rs.latterOptions)}
            @click=${() => void store.tools.confirmResetDevice()}
            class="btn btn-danger-filled"
          >
            ${store.t("confirm.reset_device.confirm")}
          </button>
        </div>
      </div>
    </div>
  </dialog>`;
}

export function renderAddBleDialog(store: StudioStore): TemplateResult {
  const modal = store.addBleModal;
  const close = (): void => {
    if (store.addBleModal.open && !store.addBleModal.busy) {
      store.tools.closeAddBleModal();
    }
  };
  const backdrop = createDialogBackdropHandlers(close, () => store.addBleModal.busy);

  if (!modal.open) {
    return html`<dialog
      id="latter-add-dev-modal"
      aria-labelledby="latter-add-dev-title"
      closedby=${modal.busy ? "none" : "any"}
      @cancel=${(ev: Event) => guardDialogCancel(ev, close, modal.busy)}
      @close=${close}
      @pointerdown=${backdrop.onPointerDown}
      @click=${backdrop.onClick}
      class="studio-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  const persons = store.state?.catalog?.persons || [];
  const candidates = store.state?.discovered_ble_devices || [];

  return html`<dialog
    id="latter-add-dev-modal"
    aria-labelledby="latter-add-dev-title"
    closedby=${modal.busy ? "none" : "any"}
    @cancel=${(ev: Event) => guardDialogCancel(ev, close, modal.busy)}
    @close=${close}
    @pointerdown=${backdrop.onPointerDown}
    @click=${backdrop.onClick}
    class="studio-dialog"
  >
    <div class="dialog-body">
      <h1 id="latter-add-dev-title" class="dialog-title">${store.t("dialogs.ble_title")}</h1>
      <p class="dialog-text">${store.t("dialogs.ble_body")}</p>
      <div class="stacked-field">
        <label for="ble-candidate-picker">${store.t("dialogs.ble_discovered_label")}</label>
        <select
          id="ble-candidate-picker"
          .value=${live(modal.candidateAddr)}
          @change=${(ev: Event) =>
            store.tools.selectBleCandidateInModal((ev.currentTarget as HTMLSelectElement).value)}
        >
          <option value="" .selected=${live(!modal.candidateAddr)}>
            ${store.t("dialogs.ble_enter_manually")}
          </option>
          ${candidates.map((c) => {
            const addr = c.target_address || "";
            const lbl =
              c.label ||
              `${c.title || addr}${c.area_name ? ` (${c.area_name})` : ""}`;
            return html`<option value=${addr} .selected=${live(addr === modal.candidateAddr)}>
              ${lbl}
            </option>`;
          })}
        </select>
      </div>
      <div class="stacked-field">
        <label for="ble-custom-name">${store.t("dialogs.ble_name_label")}</label>
        <input
          type="text"
          id="ble-custom-name"
          placeholder=${store.t("dialogs.ble_name_placeholder")}
          .value=${focusSafe(modal.name)}
          @input=${(ev: Event) => {
            store.addBleModal = {
              ...store.addBleModal,
              name: (ev.currentTarget as HTMLInputElement).value,
            };
          }}
        />
      </div>
      <div class="stacked-field">
        <label for="ble-custom-addr">${store.t("dialogs.ble_addr_label")}</label>
        <input
          type="text"
          id="ble-custom-addr"
          placeholder=${store.t("dialogs.ble_addr_placeholder")}
          spellcheck="false"
          autocorrect="off"
          autocapitalize="none"
          .value=${focusSafe(modal.address)}
          @input=${(ev: Event) => {
            store.addBleModal = {
              ...store.addBleModal,
              address: (ev.currentTarget as HTMLInputElement).value,
            };
          }}
          class="mono"
        />
        <span class="help-text">${store.t("dialogs.ble_addr_help")}</span>
      </div>
      <div class="stacked-field">
        <label for="ble-custom-person">${store.t("dialogs.ble_person_label")}</label>
        <select
          id="ble-custom-person"
          .value=${live(modal.assignedPerson)}
          @change=${(ev: Event) => {
            store.addBleModal = {
              ...store.addBleModal,
              assignedPerson: (ev.currentTarget as HTMLSelectElement).value,
            };
          }}
        >
          ${renderSelectOptions(persons, modal.assignedPerson, store.t("common.unassigned"))}
        </select>
      </div>
      <div class="dialog-actions">
        <button type="button" ?disabled=${modal.busy} @click=${close} class="btn btn-secondary">
          ${store.t("action.cancel")}
        </button>
        <button
          type="button"
          ?disabled=${modal.busy}
          @click=${() => void store.tools.confirmAddBleModal()}
          class="btn btn-primary"
        >
          ${store.t("action.add_ble_tag")}
        </button>
      </div>
    </div>
  </dialog>`;
}

export function renderSaveGroupDialog(store: StudioStore): TemplateResult {
  const modal = store.saveGroupModal;
  const close = (): void => {
    if (store.saveGroupModal.open && !store.saveGroupModal.busy) {
      store.groups.closeSaveGroupModal();
    }
  };
  const backdrop = createDialogBackdropHandlers(close, () => Boolean(store.saveGroupModal.busy));

  if (!modal.open) {
    return html`<dialog
      id="latter-save-group-modal"
      aria-labelledby="latter-save-group-title"
      closedby=${modal.busy ? "none" : "any"}
      @cancel=${(ev: Event) => guardDialogCancel(ev, close, Boolean(modal.busy))}
      @close=${close}
      @pointerdown=${backdrop.onPointerDown}
      @click=${backdrop.onClick}
      class="studio-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  return html`<dialog
    id="latter-save-group-modal"
    aria-labelledby="latter-save-group-title"
    closedby=${modal.busy ? "none" : "any"}
    @cancel=${(ev: Event) => guardDialogCancel(ev, close, Boolean(modal.busy))}
    @close=${close}
    @pointerdown=${backdrop.onPointerDown}
    @click=${backdrop.onClick}
    class="studio-dialog"
  >
    <div class="dialog-body">
      <h1 id="latter-save-group-title" class="dialog-title">
        ${store.t("dialogs.save_group_title")}
      </h1>
      <p class="dialog-text">${store.t("dialogs.save_group_body")}</p>
      <div class="stacked-field">
        <label for="save-group-name">${store.t("groups.group_name")}</label>
        <input
          type="text"
          id="save-group-name"
          placeholder=${store.t("dialogs.save_group_name_placeholder")}
          .value=${focusSafe(modal.name)}
          @input=${(ev: Event) => {
            store.saveGroupModal = {
              ...store.saveGroupModal,
              name: (ev.currentTarget as HTMLInputElement).value,
            };
          }}
        />
      </div>
      <div class="stacked-field">
        <label for="save-group-desc">${store.t("groups.description_optional")}</label>
        <input
          type="text"
          id="save-group-desc"
          placeholder=${store.t("dialogs.save_group_desc_placeholder")}
          .value=${focusSafe(modal.description)}
          @input=${(ev: Event) => {
            store.saveGroupModal = {
              ...store.saveGroupModal,
              description: (ev.currentTarget as HTMLInputElement).value,
            };
          }}
        />
      </div>
      <div class="settings-list">
        ${renderSwitchRow({
          id: "save-group-include-display",
          label: store.t("groups.include_display"),
          description: store.t("groups.include_display_desc"),
          checked: Boolean(modal.includeDisplay),
          onChange: (checked) => {
            store.saveGroupModal = {
              ...store.saveGroupModal,
              includeDisplay: checked,
            };
            store.host.requestUpdate();
          },
        })}
        ${renderSwitchRow({
          id: "save-group-include-interface",
          label: store.t("groups.include_interface"),
          description: store.t("groups.include_interface_desc"),
          checked: Boolean(modal.includeInterface),
          onChange: (checked) => {
            store.saveGroupModal = {
              ...store.saveGroupModal,
              includeInterface: checked,
            };
            store.host.requestUpdate();
          },
        })}
      </div>
      <div class="dialog-actions">
        <button type="button" ?disabled=${Boolean(modal.busy)} @click=${close} class="btn btn-secondary">
          ${store.t("action.cancel")}
        </button>
        <button
          type="button"
          id="latter-save-group-confirm-btn"
          ?disabled=${Boolean(modal.busy)}
          @click=${() => void store.groups.confirmSaveGroupModal()}
          class="btn btn-primary"
        >
          ${store.t("action.save_group")}
        </button>
      </div>
    </div>
  </dialog>`;
}
