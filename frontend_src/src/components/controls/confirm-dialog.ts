/**
 * Shared Confirmation `<dialog>` Builder & Modal Lifecycle Sync (`components/controls/confirm-dialog.ts`, `Q5` / `D-064`).
 */

import { t } from "../../i18n/index.js";
import { html, nothing, type TemplateResult } from "../../lib/lit.js";

export interface ConfirmDialogOptions {
  id: string;
  open?: boolean;
  title: string;
  consequence: string | TemplateResult;
  blastRadiusCount?: number | null;
  blastRadiusLabel?: string;
  extraBody?: TemplateResult | typeof nothing;
  confirmLabel: string;
  cancelLabel?: string;
  danger?: boolean;
  busy?: boolean;
  confirmDisabled?: boolean;
  confirmButtonId?: string;
  onConfirm: () => void;
  onCancel: () => void;
  onDownloadBackupFirst?: (() => void) | null;
  downloadBackupLabel?: string;
  overlay?: Readonly<Record<string, string>> | null;
}

export function syncDialogElement(
  dlg: HTMLDialogElement | null | undefined,
  wantOpen: boolean,
): void {
  if (!dlg) return;
  if (!wantOpen) {
    if (dlg.open) {
      try {
        dlg.close();
      } catch {
        dlg.removeAttribute("open");
      }
    }
    return;
  }
  if (!dlg.open) {
    try {
      dlg.showModal();
    } catch {
      dlg.setAttribute("open", "");
    }
  }
}

export function renderConfirmDialog(opts: ConfirmDialogOptions): TemplateResult {
  const titleId = `${opts.id}-title`;
  const descId = `${opts.id}-desc`;
  const isDanger = opts.danger !== false;
  const count = opts.blastRadiusCount;
  const blastText =
    opts.blastRadiusLabel ||
    (count !== undefined && count !== null && count > 0
      ? count === 1
        ? t("confirm.blast_radius_one", undefined, opts.overlay)
        : t("confirm.blast_radius_many", { count }, opts.overlay)
      : "");

  const isBusy = Boolean(opts.busy);

  const onBackdropClick = (ev: Event): void => {
    if (ev.target === ev.currentTarget && !isBusy) {
      opts.onCancel();
    }
  };

  return html`<dialog
    id=${opts.id}
    aria-labelledby=${titleId}
    aria-describedby=${descId}
    @cancel=${(ev: Event) => {
      ev.preventDefault();
      if (!isBusy) {
        opts.onCancel();
      }
    }}
    @click=${onBackdropClick}
    class="studio-dialog confirm-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id=${titleId} class="dialog-title">${opts.title}</h3>
        ${blastText
          ? html`<span class="chip ${isDanger ? "chip-warning" : "chip-primary"} confirm-blast-badge">
              ${blastText}
            </span>`
          : nothing}
      </div>
      ${opts.extraBody && opts.extraBody !== nothing ? opts.extraBody : nothing}
      <p id=${descId} class="dialog-text">${opts.consequence}</p>
      <div class="dialog-actions${opts.onDownloadBackupFirst ? " with-secondary" : ""}">
        ${opts.onDownloadBackupFirst
          ? html`<button
              type="button"
              ?disabled=${isBusy}
              @click=${opts.onDownloadBackupFirst}
              class="btn btn-text btn-compact"
            >
              ${opts.downloadBackupLabel ||
              t("action.download_backup_first", undefined, opts.overlay)}
            </button>`
          : nothing}
        <div class="dialog-actions-end">
          <button
            type="button"
            ?disabled=${isBusy}
            @click=${opts.onCancel}
            class="btn btn-secondary"
          >
            ${opts.cancelLabel || t("action.cancel", undefined, opts.overlay)}
          </button>
          <button
            type="button"
            id=${opts.confirmButtonId || nothing}
            ?disabled=${Boolean(opts.busy || opts.confirmDisabled)}
            @click=${opts.onConfirm}
            class="btn ${isDanger ? "btn-danger-filled" : "btn-primary"}"
          >
            ${opts.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  </dialog>`;
}
