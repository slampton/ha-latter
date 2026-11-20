/**
 * Shared Photo Pool Picker Modal (`#latter-photo-picker-modal`, `D-072`).
 * Reused by both `Device -> Display -> Wallpaper` and `Device -> Display -> Screensaver (Photo Frame)`:
 * - Modes: Single photo, Collection, Custom selection
 * - Quick Upload photos trigger (re-opens/updates picker cleanly)
 * - Filters `dynamic_preset` (such as `Day & Night Sky`) out of Photo Frame pickers
 */

import {
  VIRTUAL_COLLECTION_ALL,
  VIRTUAL_COLLECTION_DEFAULTS,
  VIRTUAL_COLLECTION_UNCATEGORIZED,
  VIRTUAL_COLLECTION_UPLOADS,
} from "../../constants.js";
import { focusSafe, html, nothing, type TemplateResult } from "../../lib/lit.js";
import {
  filterEligiblePhotoIds,
  filterLibraryPhotos,
  isPhotoDynamic,
  resolveCollectionDisplayName,
} from "../../state/photo-ops.js";
import type { StudioStore } from "../../state/store.js";
import { fmtNumber } from "../../utils/format.js";

export function renderPhotoPickerDialog(store: StudioStore): TemplateResult {
  const modal = store.photoPickerModal;
  const close = (): void => store.entity.closePhotoPickerModal();
  const onBackdropClick = (ev: Event): void => {
    if (ev.target === ev.currentTarget && !modal.busy) {
      close();
    }
  };

  if (!modal.open) {
    return html`<dialog
      id="latter-photo-picker-modal"
      aria-labelledby="latter-photo-picker-title"
      @cancel=${close}
      @click=${onBackdropClick}
      class="studio-dialog photo-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  const isScreensaver = modal.target === "screensaver";
  const shapeClass =
    String(store.state?.config?.display_shape || "square") === "circle" ? "circle" : "";
  const allPhotos =
    (store.state?.wallpapers && store.state.wallpapers.length > 0
      ? store.state.wallpapers
      : store.state?.system_wallpapers) || [];
  const collections = store.state?.photo_collections || [];

  const filteredPhotos = filterLibraryPhotos(allPhotos, modal.filterCollection, modal.search, {
    excludeDynamic: isScreensaver,
  });

  const collectionPreviewPhotos = filterLibraryPhotos(
    allPhotos,
    modal.collectionId || VIRTUAL_COLLECTION_ALL,
    "",
    { excludeDynamic: isScreensaver },
  );

  const validCustomIds = filterEligiblePhotoIds(modal.customIds, allPhotos, isScreensaver);
  const customSet = new Set(validCustomIds);

  const toggleCustomPhoto = (photoId: string): void => {
    const next = customSet.has(photoId)
      ? validCustomIds.filter((id) => id !== photoId)
      : [...validCustomIds, photoId];
    store.photoPickerModal = { ...store.photoPickerModal, customIds: next };
    store.host.requestUpdate();
  };

  const canApply =
    !modal.busy &&
    (modal.mode === "single"
      ? Boolean(modal.singleSource)
      : modal.mode === "collection"
        ? Boolean(modal.collectionId)
        : validCustomIds.length > 0);

  const title = isScreensaver
    ? store.t("photo_picker.title_screensaver")
    : store.t("photo_picker.title_wallpaper");

  const virtualCollectionOptions: ReadonlyArray<{ id: string; label: string }> = [
    { id: VIRTUAL_COLLECTION_ALL, label: store.t("photos.filter_all") },
    { id: VIRTUAL_COLLECTION_DEFAULTS, label: store.t("photos.filter_defaults") },
    { id: VIRTUAL_COLLECTION_UPLOADS, label: store.t("photos.filter_my_photos") },
    { id: VIRTUAL_COLLECTION_UNCATEGORIZED, label: store.t("photos.filter_uncategorized") },
  ];

  const onQuickUpload = (): void => {
    const resumeTarget = modal.target;
    const resumeMode = modal.mode;
    const resumeCustom = [...modal.customIds];
    const resumeCollection = modal.collectionId;
    close();
    store.entity.openPhotoUploadModal({
      defaultCollectionId: resumeCollection.startsWith("col_") ? resumeCollection : "",
      onComplete: (uploadedIds) => {
        store.entity.openPhotoPickerModal(resumeTarget);
        if (uploadedIds.length > 0) {
          if (resumeMode === "single" && uploadedIds.length === 1) {
            store.photoPickerModal = {
              ...store.photoPickerModal,
              mode: "single",
              singleSource: uploadedIds[0],
            };
          } else if (resumeMode === "custom") {
            store.photoPickerModal = {
              ...store.photoPickerModal,
              mode: "custom",
              customIds: Array.from(new Set([...resumeCustom, ...uploadedIds])),
            };
          }
          store.host.requestUpdate();
        }
      },
    });
  };

  return html`<dialog
    id="latter-photo-picker-modal"
    aria-labelledby="latter-photo-picker-title"
    @cancel=${close}
    @click=${onBackdropClick}
    class="studio-dialog photo-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-photo-picker-title" class="dialog-title">${title}</h3>
        <button
          type="button"
          id="btn-picker-quick-upload"
          ?disabled=${modal.busy}
          @click=${onQuickUpload}
          class="btn btn-secondary btn-compact"
        >
          ${store.t("photos.upload_btn")}
        </button>
      </div>

      <div
        role="radiogroup"
        aria-label=${store.t("photo_picker.mode_aria")}
        class="segmented"
      >
        <button
          type="button"
          id="btn-picker-mode-single"
          role="radio"
          aria-checked=${modal.mode === "single" ? "true" : "false"}
          @click=${() => {
            store.photoPickerModal = { ...store.photoPickerModal, mode: "single" };
            store.host.requestUpdate();
          }}
          class=${modal.mode === "single" ? "active" : ""}
        >
          ${store.t("photo_picker.mode_single")}
        </button>
        <button
          type="button"
          id="btn-picker-mode-collection"
          role="radio"
          aria-checked=${modal.mode === "collection" ? "true" : "false"}
          @click=${() => {
            store.photoPickerModal = { ...store.photoPickerModal, mode: "collection" };
            store.host.requestUpdate();
          }}
          class=${modal.mode === "collection" ? "active" : ""}
        >
          ${store.t("photo_picker.mode_collection")}
        </button>
        <button
          type="button"
          id="btn-picker-mode-custom"
          role="radio"
          aria-checked=${modal.mode === "custom" ? "true" : "false"}
          @click=${() => {
            store.photoPickerModal = { ...store.photoPickerModal, mode: "custom" };
            store.host.requestUpdate();
          }}
          class=${modal.mode === "custom" ? "active" : ""}
        >
          ${store.t("photo_picker.mode_custom")}
        </button>
      </div>

      ${modal.mode === "collection"
        ? html`<div class="stack">
            <div class="stacked-field">
              <label for="photo-picker-collection-select">
                ${store.t("photo_picker.collection_label")}
              </label>
              <select
                id="photo-picker-collection-select"
                .value=${modal.collectionId}
                @change=${(ev: Event) => {
                  store.photoPickerModal = {
                    ...store.photoPickerModal,
                    collectionId: (ev.currentTarget as HTMLSelectElement).value,
                  };
                  store.host.requestUpdate();
                }}
              >
                ${virtualCollectionOptions.map(
                  (v) => html`<option value=${v.id} ?selected=${modal.collectionId === v.id}>
                    ${v.label}
                  </option>`,
                )}
                ${collections.map(
                  (col) => html`<option value=${col.id} ?selected=${modal.collectionId === col.id}>
                    ${col.name} (${fmtNumber(col.count, store.hass, 0)})
                  </option>`,
                )}
              </select>
            </div>
            <div class="photo-pool-preview">
              ${collectionPreviewPhotos.length > 0
                ? html`<div class="photo-pool-thumbs">
                    ${collectionPreviewPhotos.slice(0, 5).map(
                      (p) => html`<img
                        src=${p.thumb_url || p.preview_url || ""}
                        alt=${p.name || p.id}
                        loading="lazy"
                        class="photo-pool-thumb ${shapeClass}"
                      />`,
                    )}
                  </div>`
                : nothing}
              <div class="photo-pool-info">
                <span class="photo-pool-title">
                  ${resolveCollectionDisplayName(store, modal.collectionId)}
                </span>
                <span class="photo-pool-meta">
                  ${collectionPreviewPhotos.length === 1
                    ? store.t("sys_overview.photos_count_one")
                    : store.t("sys_overview.photos_count_many", {
                        count: fmtNumber(collectionPreviewPhotos.length, store.hass, 0),
                      })}
                </span>
              </div>
            </div>
          </div>`
        : html`<div class="stack">
            <div class="photo-toolbar">
              <input
                type="search"
                id="photo-picker-search"
                aria-label=${store.t("photos.search_aria")}
                placeholder=${store.t("photos.search_placeholder")}
                .value=${focusSafe(modal.search)}
                @input=${(ev: Event) => {
                  store.photoPickerModal = {
                    ...store.photoPickerModal,
                    search: (ev.currentTarget as HTMLInputElement).value,
                  };
                  store.host.requestUpdate();
                }}
                class="photo-search-input"
              />
              <select
                id="photo-picker-filter-col"
                aria-label=${store.t("photo_picker.collection_label")}
                .value=${modal.filterCollection}
                @change=${(ev: Event) => {
                  store.photoPickerModal = {
                    ...store.photoPickerModal,
                    filterCollection: (ev.currentTarget as HTMLSelectElement).value,
                  };
                  store.host.requestUpdate();
                }}
              >
                ${virtualCollectionOptions.map(
                  (v) => html`<option value=${v.id} ?selected=${modal.filterCollection === v.id}>
                    ${v.label}
                  </option>`,
                )}
                ${collections.map(
                  (col) => html`<option
                    value=${col.id}
                    ?selected=${modal.filterCollection === col.id}
                  >
                    ${col.name}
                  </option>`,
                )}
              </select>
            </div>

            ${modal.mode === "custom"
              ? html`<div class="photo-toolbar">
                  <span class="row-description">${store.t("photo_picker.custom_hint")}</span>
                  <span class="chip chip-primary">
                    ${validCustomIds.length === 1
                      ? store.t("photo_picker.custom_selected_one")
                      : store.t("photo_picker.custom_selected_many", {
                          count: fmtNumber(validCustomIds.length, store.hass, 0),
                        })}
                  </span>
                  ${validCustomIds.length > 0
                    ? html`<button
                        type="button"
                        id="btn-picker-clear-custom"
                        ?disabled=${modal.busy}
                        @click=${() => {
                          store.photoPickerModal = { ...store.photoPickerModal, customIds: [] };
                          store.host.requestUpdate();
                        }}
                        class="btn btn-text btn-compact"
                      >
                        ${store.t("photos.clear_selection")}
                      </button>`
                    : nothing}
                </div>`
              : nothing}

            ${filteredPhotos.length === 0
              ? html`<p class="empty-state">${store.t("photo_picker.empty")}</p>`
              : html`<div class="photo-picker-grid">
                  ${filteredPhotos.map((photo) => {
                    const isSelected =
                      modal.mode === "single"
                        ? modal.singleSource === photo.id
                        : customSet.has(photo.id);
                    const thumbSrc = photo.thumb_url || photo.preview_url || "";
                    const onPick = (): void => {
                      if (modal.mode === "single") {
                        store.photoPickerModal = {
                          ...store.photoPickerModal,
                          singleSource: photo.id,
                        };
                        store.host.requestUpdate();
                      } else {
                        toggleCustomPhoto(photo.id);
                      }
                    };
                    return html`<button
                      type="button"
                      data-photo-id=${photo.id}
                      aria-pressed=${isSelected ? "true" : "false"}
                      @click=${onPick}
                      class="photo-picker-item ${isSelected ? "selected" : ""}"
                    >
                      ${thumbSrc
                        ? html`<img
                            src=${thumbSrc}
                            alt=${photo.name || photo.id}
                            loading="lazy"
                            class="photo-picker-thumb ${shapeClass}"
                          />`
                        : html`<div class="photo-picker-thumb ${shapeClass}" aria-hidden="true"></div>`}
                      <span class="photo-picker-name">${photo.name || photo.id}</span>
                      ${isPhotoDynamic(photo)
                        ? html`<span class="chip chip-primary">
                            ${store.t("photos.badge_dynamic")}
                          </span>`
                        : nothing}
                    </button>`;
                  })}
                </div>`}
          </div>`}

      <div class="dialog-actions">
        <button
          type="button"
          ?disabled=${modal.busy}
          @click=${close}
          class="btn btn-secondary"
        >
          ${store.t("action.cancel")}
        </button>
        <button
          type="button"
          id="btn-picker-apply"
          ?disabled=${!canApply}
          @click=${() => void store.entity.applyPhotoPickerModal()}
          class="btn btn-primary"
        >
          ${store.t("photo_picker.apply_btn")}
        </button>
      </div>
    </div>
  </dialog>`;
}
