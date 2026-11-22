/**
 * Home Assistant `/media` Folder Import Modal (`#latter-media-import-modal`, `D-072`).
 * - Calls `browse_media_folder` to navigate `media_dirs` roots & NAS subdirectories with breadcrumbs
 * - Lazy thumbnail grid with checkboxes, Select all in folder, 1-click "New collection from folder name",
 *   and batch `import_media_photos` with summary toast.
 */

import { focusSafe, html, live, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import { fmtNumber } from "../../utils/format.js";
import { renderSvgIcon } from "../controls.js";

const ICON_FOLDER =
  "M10,4H4C2.89,4 2,4.89 2,6V18A2,2 0 0,0 4,20H20A2,2 0 0,0 22,18V8C22,6.89 21.1,6 20,6H12L10,4Z";

export function renderMediaImportDialog(store: StudioStore): TemplateResult {
  const modal = store.mediaImportModal;
  const close = (): void => store.entity.closeMediaImportModal();
  const onBackdropClick = (ev: Event): void => {
    if (ev.target === ev.currentTarget && !modal.importing) {
      close();
    }
  };

  if (!modal.open) {
    return html`<dialog
      id="latter-media-import-modal"
      aria-labelledby="latter-media-import-title"
      @cancel=${(ev: Event) => {
        if (modal.importing) ev.preventDefault();
        else close();
      }}
      @click=${onBackdropClick}
      class="studio-dialog photo-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  const collections = store.state?.photo_collections || [];
  const selectableImages = modal.images.filter((img) => !img.too_large);
  const selectedSet = new Set(modal.selectedPaths);
  const allFolderSelected =
    selectableImages.length > 0 && selectableImages.every((img) => selectedSet.has(img.relpath));

  const crumbs = modal.subpath ? modal.subpath.split("/").filter(Boolean) : [];
  const currentFolderName = (crumbs.length > 0 ? crumbs[crumbs.length - 1] : undefined) ?? (modal.root || "Media");

  const toggleImagePath = (relpath: string): void => {
    const next = selectedSet.has(relpath)
      ? modal.selectedPaths.filter((p) => p !== relpath)
      : [...modal.selectedPaths, relpath];
    store.mediaImportModal = { ...store.mediaImportModal, selectedPaths: next };
    store.host.requestUpdate();
  };

  const toggleSelectAllFolder = (): void => {
    const next = allFolderSelected ? [] : selectableImages.map((img) => img.relpath);
    store.mediaImportModal = { ...store.mediaImportModal, selectedPaths: next };
    store.host.requestUpdate();
  };

  const importBtnLabel = modal.importing
    ? store.t("media_import.importing_btn")
    : modal.selectedPaths.length === 1
      ? store.t("media_import.import_btn_one")
      : store.t("media_import.import_btn_many", {
          count: fmtNumber(modal.selectedPaths.length, store.hass, 0),
        });

  return html`<dialog
    id="latter-media-import-modal"
    aria-labelledby="latter-media-import-title"
    @cancel=${(ev: Event) => {
      if (modal.importing) ev.preventDefault();
      else close();
    }}
    @click=${onBackdropClick}
    class="studio-dialog photo-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-media-import-title" class="dialog-title">
          ${store.t("media_import.title")}
        </h3>
        ${modal.roots.length > 1
          ? html`<select
              id="media-import-root-select"
              aria-label=${store.t("media_import.root_label")}
              ?disabled=${modal.loading || modal.importing}
              .value=${live(modal.root)}
              @change=${(ev: Event) =>
                void store.entity.browseMediaFolder(
                  (ev.currentTarget as HTMLSelectElement).value,
                  "",
                )}
            >
              ${modal.roots.map(
                (r) => html`<option value=${r.id} .selected=${live(r.id === modal.root)}>
                  ${r.name}
                </option>`,
              )}
            </select>`
          : nothing}
      </div>

      <p class="dialog-text">${store.t("media_import.subtitle")}</p>

      ${modal.error
        ? html`<div role="alert" class="alert alert-error">
            <span>${modal.error}</span>
          </div>`
        : nothing}

      ${modal.roots.length > 0
        ? html`<div class="media-breadcrumbs" aria-label=${store.t("media_import.root_label")}>
            ${modal.parentSubpath !== null
              ? html`<button
                  type="button"
                  id="btn-media-up"
                  ?disabled=${modal.loading || modal.importing}
                  @click=${() =>
                    void store.entity.browseMediaFolder(modal.root, modal.parentSubpath || "")}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.t("media_import.up_folder")}
                </button>`
              : nothing}
            <button
              type="button"
              ?disabled=${modal.loading || modal.importing || !modal.subpath}
              @click=${() => void store.entity.browseMediaFolder(modal.root, "")}
              class="btn btn-text btn-compact"
            >
              ${modal.roots.find((r) => r.id === modal.root)?.name || modal.root}
            </button>
            ${crumbs.map((seg, idx) => {
              const targetSub = crumbs.slice(0, idx + 1).join("/");
              const isLast = idx === crumbs.length - 1;
              return html`<span aria-hidden="true">/</span>
                <button
                  type="button"
                  ?disabled=${modal.loading || modal.importing || isLast}
                  @click=${() => void store.entity.browseMediaFolder(modal.root, targetSub)}
                  class="btn btn-text btn-compact"
                >
                  ${seg}
                </button>`;
            })}
            ${selectableImages.length > 0
              ? html`<button
                  type="button"
                  id="btn-media-select-all"
                  ?disabled=${modal.loading || modal.importing}
                  @click=${toggleSelectAllFolder}
                  class="btn btn-secondary btn-compact"
                >
                  ${allFolderSelected
                    ? store.t("media_import.clear_folder_selection")
                    : store.t("media_import.select_all_folder")}
                </button>`
              : nothing}
          </div>`
        : nothing}

      <div class="media-scroll-area">
        ${modal.loading
          ? html`<div role="status" class="loading-state">${store.t("common.loading")}</div>`
          : modal.roots.length === 0 && !modal.error
            ? html`<p class="empty-state">${store.t("media_import.empty_roots")}</p>`
            : modal.folders.length === 0 && modal.images.length === 0
              ? html`<p class="empty-state">${store.t("media_import.empty_folder")}</p>`
              : html`${modal.folders.length > 0
                    ? html`<div class="media-folder-list">
                        ${modal.folders.map(
                          (f) => html`<button
                            type="button"
                            ?disabled=${modal.importing}
                            @click=${() =>
                              void store.entity.browseMediaFolder(modal.root, f.subpath)}
                            class="media-folder-btn"
                          >
                            ${renderSvgIcon(ICON_FOLDER)}
                            <span>${f.name}</span>
                          </button>`,
                        )}
                      </div>`
                    : nothing}
                  ${modal.images.length > 0
                    ? html`<div class="photo-grid">
                        ${modal.images.map((img) => {
                          const isSelected = selectedSet.has(img.relpath);
                          return html`<div class="photo-tile ${isSelected ? "selected" : ""}">
                            <input
                              type="checkbox"
                              aria-label=${img.name}
                              ?disabled=${img.too_large || modal.importing}
                              .checked=${live(isSelected)}
                              @change=${() => toggleImagePath(img.relpath)}
                              class="photo-tile-check"
                            />
                            <button
                              type="button"
                              ?disabled=${img.too_large || modal.importing}
                              @click=${() => toggleImagePath(img.relpath)}
                              class="photo-tile-thumb-btn"
                            >
                              ${img.thumb_url
                                ? html`<img
                                    src=${img.thumb_url}
                                    alt=${img.name}
                                    loading="lazy"
                                    class="photo-tile-img"
                                  />`
                                : nothing}
                              ${img.too_large
                                ? html`<span class="photo-tile-badge">
                                    ${store.t("media_import.too_large")}
                                  </span>`
                                : img.already_imported
                                  ? html`<span class="photo-tile-badge">
                                      ${store.t("media_import.already_imported")}
                                    </span>`
                                  : nothing}
                            </button>
                            <div class="photo-tile-meta">
                              <span class="photo-tile-name">${img.name}</span>
                            </div>
                          </div>`;
                        })}
                      </div>`
                    : nothing}`}
      </div>

      ${modal.images.length > 0
        ? html`<div class="stack">
            <div class="input-action-row">
              <select
                id="media-import-collection"
                aria-label=${store.t("media_import.collection_label")}
                ?disabled=${modal.importing || modal.useNewFolderCollection}
                .value=${live(modal.collectionId)}
                @change=${(ev: Event) => {
                  store.mediaImportModal = {
                    ...store.mediaImportModal,
                    collectionId: (ev.currentTarget as HTMLSelectElement).value,
                  };
                  store.host.requestUpdate();
                }}
              >
                <option value="" .selected=${live(!modal.collectionId)}>
                  ${store.t("photo_upload.no_collection")}
                </option>
                ${collections.map(
                  (col) => html`<option value=${col.id} .selected=${live(modal.collectionId === col.id)}>
                    ${col.name}
                  </option>`,
                )}
              </select>
              <button
                type="button"
                id="btn-media-new-col-from-folder"
                ?disabled=${modal.importing}
                @click=${() => {
                  const nextOn = !modal.useNewFolderCollection;
                  store.mediaImportModal = {
                    ...store.mediaImportModal,
                    useNewFolderCollection: nextOn,
                    newCollectionName: nextOn ? currentFolderName : "",
                  };
                  store.host.requestUpdate();
                }}
                class="btn ${modal.useNewFolderCollection ? "btn-primary" : "btn-secondary"} btn-compact"
              >
                ${store.t("media_import.new_from_folder")}
              </button>
            </div>
            ${modal.useNewFolderCollection
              ? html`<div class="stacked-field">
                  <label for="media-import-new-col-name">
                    ${store.t("media_import.new_collection_name")}
                  </label>
                  <input
                    type="text"
                    id="media-import-new-col-name"
                    ?disabled=${modal.importing}
                    .value=${focusSafe(modal.newCollectionName)}
                    @input=${(ev: Event) => {
                      store.mediaImportModal = {
                        ...store.mediaImportModal,
                        newCollectionName: (ev.currentTarget as HTMLInputElement).value,
                      };
                    }}
                  />
                </div>`
              : nothing}
          </div>`
        : nothing}

      <div class="dialog-actions">
        <button
          type="button"
          ?disabled=${modal.importing}
          @click=${close}
          class="btn btn-secondary"
        >
          ${store.t("action.cancel")}
        </button>
        <button
          type="button"
          id="btn-media-import-confirm"
          ?disabled=${modal.importing || modal.selectedPaths.length === 0}
          @click=${() => void store.entity.importSelectedMedia()}
          class="btn btn-primary"
        >
          ${importBtnLabel}
        </button>
      </div>
    </div>
  </dialog>`;
}
