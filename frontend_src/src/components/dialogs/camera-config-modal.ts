/**
 * Per-Camera Options Modal (`#latter-camera-config-modal`, `D-073`):
 * - Custom display label override (blank uses Home Assistant friendly name)
 * - Independent on-device action button toggles: Listen, Talk, Quick Reply
 * - Explicit Unlock / Open Lock or Garage Door entity binding (`None` hides button)
 */

import { focusSafe, html, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import type { CameraConfig, CatalogChoice } from "../../types.js";
import { entityLabel } from "../../utils/format.js";
import { renderSettingsRow, renderSwitchRow } from "../controls.js";

function bindBackdropClose(ev: Event, closeFn: () => void): void {
  if (ev.target === ev.currentTarget) {
    closeFn();
  }
}

export function resolveEffectiveCameraConfig(
  store: StudioStore,
  cameraId: string,
): {
  label: string;
  showListen: boolean;
  showTalk: boolean;
  showReply: boolean;
  unlockEntity: string;
  meta: CatalogChoice | undefined;
} {
  const catCams = store.state?.catalog?.cameras || [];
  const meta = catCams.find((c) => c.id === cameraId);
  const stored = (store.state?.system_config?.camera_configs || {})[cameraId] || {};
  const isDoorbell = Boolean(meta?.is_doorbell);
  const hwAudio = Boolean(meta?.has_audio);
  const hwTalk = Boolean(meta?.has_talkback);

  return {
    label: String(stored.label || "").trim(),
    showListen:
      typeof stored.show_listen === "boolean" ? stored.show_listen : isDoorbell && hwAudio,
    showTalk: typeof stored.show_talk === "boolean" ? stored.show_talk : isDoorbell && hwTalk,
    showReply: typeof stored.show_reply === "boolean" ? stored.show_reply : isDoorbell && hwTalk,
    unlockEntity: String(stored.unlock_entity || "").trim(),
    meta,
  };
}

export function openCameraConfigModal(store: StudioStore, cameraId: string): void {
  const cleanId = String(cameraId || "").trim();
  if (!cleanId) return;
  const eff = resolveEffectiveCameraConfig(store, cleanId);
  store.cameraConfigModal = {
    open: true,
    cameraId: cleanId,
    label: eff.label,
    showListen: eff.showListen,
    showTalk: eff.showTalk,
    showReply: eff.showReply,
    unlockEntity: eff.unlockEntity,
  };
  store.host.requestUpdate();
}

export function closeCameraConfigModal(store: StudioStore): void {
  if (!store.cameraConfigModal.open) return;
  store.cameraConfigModal = { ...store.cameraConfigModal, open: false };
  store.host.requestUpdate();
}

export function saveCameraConfigModal(store: StudioStore): void {
  const m = store.cameraConfigModal;
  const camId = String(m.cameraId || "").trim();
  if (!camId) {
    closeCameraConfigModal(store);
    return;
  }
  const existing = { ...(store.state?.system_config?.camera_configs || {}) };
  const nextEntry: CameraConfig = {
    show_listen: Boolean(m.showListen),
    show_talk: Boolean(m.showTalk),
    show_reply: Boolean(m.showReply),
  };
  const cleanLabel = String(m.label || "")
    .replace(/[|\x1e\x1f\r\n]/g, " ")
    .trim()
    .slice(0, 32);
  if (cleanLabel) {
    nextEntry.label = cleanLabel;
  }
  const cleanUnlock = String(m.unlockEntity || "").trim();
  if (cleanUnlock.startsWith("lock.") || cleanUnlock.startsWith("cover.")) {
    nextEntry.unlock_entity = cleanUnlock;
  }
  existing[camId] = nextEntry;
  store.entity.stageSystemSetting("camera_configs", existing);
  closeCameraConfigModal(store);
}

export function renderCameraConfigDialog(store: StudioStore): TemplateResult {
  const m = store.cameraConfigModal;
  const close = (): void => closeCameraConfigModal(store);

  if (!m.open || !m.cameraId) {
    return html`<dialog
      id="latter-camera-config-modal"
      aria-labelledby="latter-cam-cfg-title"
      @cancel=${close}
      @click=${(ev: Event) => bindBackdropClose(ev, close)}
      class="studio-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  const cat = store.state?.catalog || {};
  const meta = (cat.cameras || []).find((c) => c.id === m.cameraId);
  const haName = meta?.name ? entityLabel(meta.name) : m.cameraId;
  const locks = cat.locks || [];
  const garages = cat.garages || [];
  const hasUnlockChoice =
    !m.unlockEntity ||
    locks.some((l) => l.id === m.unlockEntity) ||
    garages.some((g) => g.id === m.unlockEntity);

  return html`<dialog
    id="latter-camera-config-modal"
    aria-labelledby="latter-cam-cfg-title"
    @cancel=${close}
    @click=${(ev: Event) => bindBackdropClose(ev, close)}
    class="studio-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-cam-cfg-title" class="dialog-title">
          ${store.t("shared.cam_cfg_title")}
        </h3>
      </div>
      <p class="dialog-text">${haName} (${m.cameraId})</p>

      <div class="settings-list">
        ${renderSettingsRow({
          label: store.t("shared.cam_cfg_label"),
          description: store.t("shared.cam_cfg_label_desc"),
          forId: "cam-cfg-label",
          control: html`<input
            id="cam-cfg-label"
            type="text"
            maxlength="32"
            placeholder=${haName}
            .value=${focusSafe(m.label)}
            @input=${(ev: Event) => {
              store.cameraConfigModal = {
                ...store.cameraConfigModal,
                label: (ev.currentTarget as HTMLInputElement).value,
              };
            }}
          />`,
        })}

        ${renderSwitchRow({
          id: "cam-cfg-listen",
          label: store.t("shared.cam_cfg_listen"),
          description: store.t("shared.cam_cfg_listen_desc"),
          checked: m.showListen,
          onChange: (checked) => {
            store.cameraConfigModal = { ...store.cameraConfigModal, showListen: checked };
            store.host.requestUpdate();
          },
        })}

        ${renderSwitchRow({
          id: "cam-cfg-talk",
          label: store.t("shared.cam_cfg_talk"),
          description: meta?.has_talkback
            ? store.t("shared.cam_cfg_talk_desc")
            : store.t("shared.cam_cfg_talk_no_speaker_desc"),
          checked: m.showTalk,
          onChange: (checked) => {
            store.cameraConfigModal = { ...store.cameraConfigModal, showTalk: checked };
            store.host.requestUpdate();
          },
        })}

        ${renderSwitchRow({
          id: "cam-cfg-reply",
          label: store.t("shared.cam_cfg_reply"),
          description: store.t("shared.cam_cfg_reply_desc"),
          checked: m.showReply,
          onChange: (checked) => {
            store.cameraConfigModal = { ...store.cameraConfigModal, showReply: checked };
            store.host.requestUpdate();
          },
        })}

        ${renderSettingsRow({
          label: store.t("shared.cam_cfg_unlock"),
          description: store.t("shared.cam_cfg_unlock_desc"),
          forId: "cam-cfg-unlock",
          control: html`<select
            id="cam-cfg-unlock"
            .value=${m.unlockEntity}
            @change=${(ev: Event) => {
              store.cameraConfigModal = {
                ...store.cameraConfigModal,
                unlockEntity: (ev.currentTarget as HTMLSelectElement).value,
              };
              store.host.requestUpdate();
            }}
          >
            <option value="" ?selected=${!m.unlockEntity}>
              ${store.t("shared.cam_cfg_unlock_none")}
            </option>
            ${!hasUnlockChoice && m.unlockEntity
              ? html`<option value=${m.unlockEntity} selected>${m.unlockEntity}</option>`
              : nothing}
            ${locks.length
              ? html`<optgroup label=${store.t("shared.door_locks")}>
                  ${locks.map(
                    (l) => html`<option value=${l.id} ?selected=${m.unlockEntity === l.id}>
                      ${entityLabel(l.name)}
                    </option>`,
                  )}
                </optgroup>`
              : nothing}
            ${garages.length
              ? html`<optgroup label=${store.t("shared.garage_doors")}>
                  ${garages.map(
                    (g) => html`<option value=${g.id} ?selected=${m.unlockEntity === g.id}>
                      ${entityLabel(g.name)}
                    </option>`,
                  )}
                </optgroup>`
              : nothing}
          </select>`,
        })}
      </div>

      <div class="dialog-actions">
        <button type="button" @click=${close} class="btn btn-secondary">
          ${store.t("action.cancel")}
        </button>
        <button
          id="cam-cfg-save"
          type="button"
          @click=${() => saveCameraConfigModal(store)}
          class="btn btn-primary"
        >
          ${store.t("action.save")}
        </button>
      </div>
    </div>
  </dialog>`;
}
