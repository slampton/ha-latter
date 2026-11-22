/**
 * System Photo Library View (`photos`, `/latter/system/photos`, `D-072`):
 * - Full-width Photo library card with Upload photos (`.btn-primary`), Import from Media (`.btn-secondary`),
 *   and New collection (`.btn-secondary`) header actions
 * - Collection filter strip (All, Defaults, My photos, Uncategorized + user collections with Rename/Delete)
 * - Live name search, pagination (36/page), Select bulk mode (assign/remove collection, confirmed batch delete),
 *   and click-to-edit Photo Editor & Crop Modal.
 */

import { renderCard } from "../components/controls.js";
import {
  PHOTO_LIBRARY_PAGE_SIZE,
  VIRTUAL_COLLECTION_ALL,
  VIRTUAL_COLLECTION_DEFAULTS,
  VIRTUAL_COLLECTION_UNCATEGORIZED,
  VIRTUAL_COLLECTION_UPLOADS,
} from "../constants.js";
import { focusSafe, html, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import {
  filterLibraryPhotos,
  isPhotoDynamic,
  isPhotoUploaded,
} from "../state/photo-ops.js";
import type { StudioStore } from "../state/store.js";
import { fmtNumber } from "../utils/format.js";

const ICON_EDIT =
  "M20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18,2.9 17.35,2.9 16.96,3.29L15.12,5.12L18.87,8.87M3,17.25V21H6.75L17.81,9.93L14.06,6.18L3,17.25Z";
const ICON_CLOSE =
  "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z";

export function renderSystemPhotosView(store: StudioStore): TemplateResult {
  const data = store.state;
  const allPhotos = data?.system_wallpapers || [];
  const collections = data?.photo_collections || [];
  const collectionNameMap = new Map(collections.map((c) => [c.id, c.name]));

  const defaultsCount = allPhotos.filter((p) => !isPhotoUploaded(p)).length;
  const uploadedCount = allPhotos.filter((p) => isPhotoUploaded(p)).length;
  const uncategorizedCount = allPhotos.filter((p) => (p.collections || []).length === 0).length;

  const activeFilter =
    store.photosFilterCollection === VIRTUAL_COLLECTION_ALL ||
    store.photosFilterCollection === VIRTUAL_COLLECTION_DEFAULTS ||
    store.photosFilterCollection === VIRTUAL_COLLECTION_UPLOADS ||
    store.photosFilterCollection === VIRTUAL_COLLECTION_UNCATEGORIZED ||
    collections.some((c) => c.id === store.photosFilterCollection)
      ? store.photosFilterCollection
      : VIRTUAL_COLLECTION_ALL;

  const filtered = filterLibraryPhotos(allPhotos, activeFilter, store.photosSearch);
  const totalFiltered = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalFiltered / PHOTO_LIBRARY_PAGE_SIZE));
  const currentPage = Math.min(Math.max(1, store.photosPage || 1), totalPages);
  const startIdx = (currentPage - 1) * PHOTO_LIBRARY_PAGE_SIZE;
  const pageItems = filtered.slice(startIdx, startIdx + PHOTO_LIBRARY_PAGE_SIZE);

  const selectedCount = store.photosSelectedIds.size;
  const deletableSelectedCount = Array.from(store.photosSelectedIds).filter((id) => {
    const item = allPhotos.find((p) => p.id === id);
    return item ? isPhotoUploaded(item) : false;
  }).length;

  const setFilter = (nextFilter: string): void => {
    store.photosFilterCollection = nextFilter;
    store.photosPage = 1;
    store.host.requestUpdate();
  };

  const toggleSelectPhoto = (photoId: string): void => {
    if (store.photosSelectedIds.has(photoId)) {
      store.photosSelectedIds.delete(photoId);
    } else {
      store.photosSelectedIds.add(photoId);
    }
    store.host.requestUpdate();
  };

  const virtualChips: ReadonlyArray<{ id: string; label: string; count: number }> = [
    { id: VIRTUAL_COLLECTION_ALL, label: store.t("photos.filter_all"), count: allPhotos.length },
    {
      id: VIRTUAL_COLLECTION_DEFAULTS,
      label: store.t("photos.filter_defaults"),
      count: defaultsCount,
    },
    {
      id: VIRTUAL_COLLECTION_UPLOADS,
      label: store.t("photos.filter_my_photos"),
      count: uploadedCount,
    },
    {
      id: VIRTUAL_COLLECTION_UNCATEGORIZED,
      label: store.t("photos.filter_uncategorized"),
      count: uncategorizedCount,
    },
  ];

  return html`<section id="view-photos" class="stack">
    ${renderCard({
      id: "card-photo-library",
      handoffActive: store.isHandoffTarget("card-photo-library"),
      title: store.t("card.photo_library"),
      subtitle: store.t("photos.subtitle"),
      headerActions: html`<button
          type="button"
          id="btn-photos-upload"
          @click=${() => store.entity.openPhotoUploadModal()}
          class="btn btn-primary btn-compact"
        >
          ${store.t("photos.upload_btn")}
        </button>
        <button
          type="button"
          id="btn-photos-import-media"
          @click=${() => store.entity.openMediaImportModal()}
          class="btn btn-secondary btn-compact"
        >
          ${store.t("photos.import_media_btn")}
        </button>
        <button
          type="button"
          id="btn-photos-new-collection"
          @click=${() => {
            store.photosNewCollectionOpen = !store.photosNewCollectionOpen;
            if (!store.photosNewCollectionOpen) store.photosNewCollectionName = "";
            store.host.requestUpdate();
          }}
          class="btn btn-secondary btn-compact"
        >
          ${store.t("photos.new_collection_btn")}
        </button>`,
      contentClass: "stack",
      body: html`${store.photosNewCollectionOpen
          ? html`<div id="photos-new-collection-bar" class="input-action-row">
              <input
                type="text"
                id="input-new-collection-name"
                aria-label=${store.t("photos.new_collection_btn")}
                placeholder=${store.t("photos.new_collection_placeholder")}
                .value=${focusSafe(store.photosNewCollectionName)}
                @input=${(ev: Event) => {
                  store.photosNewCollectionName = (ev.currentTarget as HTMLInputElement).value;
                }}
                @keydown=${(ev: KeyboardEvent) => {
                  if (ev.key === "Enter") {
                    ev.preventDefault();
                    void store.entity.createPhotoCollection(store.photosNewCollectionName);
                  } else if (ev.key === "Escape") {
                    store.photosNewCollectionOpen = false;
                    store.photosNewCollectionName = "";
                    store.host.requestUpdate();
                  }
                }}
              />
              <button
                type="button"
                id="btn-create-collection-submit"
                @click=${() => void store.entity.createPhotoCollection(store.photosNewCollectionName)}
                class="btn btn-primary btn-compact"
              >
                ${store.t("photos.create_collection")}
              </button>
              <button
                type="button"
                @click=${() => {
                  store.photosNewCollectionOpen = false;
                  store.photosNewCollectionName = "";
                  store.host.requestUpdate();
                }}
                class="btn btn-text btn-compact"
              >
                ${store.t("action.cancel")}
              </button>
            </div>`
          : nothing}

        <div id="photos-collection-strip" class="collection-strip" role="group" aria-label=${store.t("photo_edit.collections_label")}>
          ${virtualChips.map((chip) => {
            const isActive = activeFilter === chip.id;
            return html`<div class="collection-chip-wrap ${isActive ? "active" : ""}">
              <button
                type="button"
                data-collection-filter=${chip.id}
                aria-pressed=${isActive ? "true" : "false"}
                @click=${() => setFilter(chip.id)}
                class="collection-chip-btn"
              >
                <span>${chip.label}</span>
                <span>(${fmtNumber(chip.count, store.hass, 0)})</span>
              </button>
            </div>`;
          })}

          ${collections.map((col) => {
            const isActive = activeFilter === col.id;
            const isRenaming = store.photosRenamingCollectionId === col.id;
            if (isRenaming) {
              return html`<div class="input-action-row">
                <input
                  type="text"
                  id="input-rename-collection"
                  aria-label=${store.t("photos.rename_collection_aria", { name: col.name })}
                  placeholder=${store.t("photos.rename_collection_placeholder")}
                  .value=${focusSafe(store.photosRenamingCollectionName)}
                  @input=${(ev: Event) => {
                    store.photosRenamingCollectionName = (ev.currentTarget as HTMLInputElement).value;
                  }}
                  @keydown=${(ev: KeyboardEvent) => {
                    if (ev.key === "Enter") {
                      ev.preventDefault();
                      void store.entity.renamePhotoCollection(
                        col.id,
                        store.photosRenamingCollectionName,
                      );
                    } else if (ev.key === "Escape") {
                      store.photosRenamingCollectionId = "";
                      store.photosRenamingCollectionName = "";
                      store.host.requestUpdate();
                    }
                  }}
                />
                <button
                  type="button"
                  @click=${() =>
                    void store.entity.renamePhotoCollection(
                      col.id,
                      store.photosRenamingCollectionName,
                    )}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.t("action.save")}
                </button>
                <button
                  type="button"
                  @click=${() => {
                    store.photosRenamingCollectionId = "";
                    store.photosRenamingCollectionName = "";
                    store.host.requestUpdate();
                  }}
                  class="btn btn-text btn-compact"
                >
                  ${store.t("action.cancel")}
                </button>
              </div>`;
            }
            return html`<div class="collection-chip-wrap ${isActive ? "active" : ""}">
              <button
                type="button"
                data-collection-filter=${col.id}
                aria-pressed=${isActive ? "true" : "false"}
                @click=${() => setFilter(col.id)}
                class="collection-chip-btn"
              >
                <span>${col.name}</span>
                <span>(${fmtNumber(col.count, store.hass, 0)})</span>
              </button>
              <button
                type="button"
                aria-label=${store.t("photos.rename_collection_aria", { name: col.name })}
                @click=${() => {
                  store.photosRenamingCollectionId = col.id;
                  store.photosRenamingCollectionName = col.name;
                  store.host.requestUpdate();
                }}
                class="collection-chip-action"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d=${ICON_EDIT} /></svg>
              </button>
              <button
                type="button"
                aria-label=${store.t("photos.delete_collection_aria", { name: col.name })}
                @click=${() => store.entity.requestDeletePhotoCollection(col.id, col.name)}
                class="collection-chip-action"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d=${ICON_CLOSE} /></svg>
              </button>
            </div>`;
          })}
        </div>

        <div class="photo-toolbar">
          <div class="photo-toolbar-start">
            <input
              type="search"
              id="input-photos-search"
              aria-label=${store.t("photos.search_aria")}
              placeholder=${store.t("photos.search_placeholder")}
              .value=${focusSafe(store.photosSearch)}
              @input=${(ev: Event) => {
                store.photosSearch = (ev.currentTarget as HTMLInputElement).value;
                store.photosPage = 1;
                store.host.requestUpdate();
              }}
              class="photo-search-input"
            />
          </div>
          <div class="photo-toolbar-end">
            <button
              type="button"
              id="btn-photos-toggle-select"
              @click=${() => {
                store.photosSelectMode = !store.photosSelectMode;
                if (!store.photosSelectMode) {
                  store.photosSelectedIds.clear();
                }
                store.host.requestUpdate();
              }}
              class="btn btn-secondary btn-compact"
            >
              ${store.photosSelectMode
                ? store.t("photos.done_selecting_btn")
                : store.t("photos.select_mode_btn")}
            </button>
          </div>
        </div>

        ${store.photosSelectMode
          ? html`<div id="photos-bulk-bar" class="photo-bulk-bar">
              <div class="photo-toolbar-start">
                <span class="chip chip-primary">
                  ${selectedCount === 1
                    ? store.t("photos.selected_count_one")
                    : store.t("photos.selected_count_many", {
                        count: fmtNumber(selectedCount, store.hass, 0),
                      })}
                </span>
                <button
                  type="button"
                  id="btn-photos-select-page"
                  @click=${() => {
                    for (const p of pageItems) store.photosSelectedIds.add(p.id);
                    store.host.requestUpdate();
                  }}
                  class="btn btn-text btn-compact"
                >
                  ${store.t("photos.select_all_page")}
                </button>
                ${selectedCount > 0
                  ? html`<button
                      type="button"
                      id="btn-photos-clear-selection"
                      @click=${() => {
                        store.photosSelectedIds.clear();
                        store.host.requestUpdate();
                      }}
                      class="btn btn-text btn-compact"
                    >
                      ${store.t("photos.clear_selection")}
                    </button>`
                  : nothing}
              </div>

              <div class="photo-toolbar-end">
                ${collections.length > 0
                  ? html`<select
                        id="select-bulk-collection"
                        aria-label=${store.t("photos.bulk_collection_aria")}
                        .value=${store.photosBulkTargetCollectionId}
                        @change=${(ev: Event) => {
                          store.photosBulkTargetCollectionId = (
                            ev.currentTarget as HTMLSelectElement
                          ).value;
                          store.host.requestUpdate();
                        }}
                      >
                        <option value="" ?selected=${!store.photosBulkTargetCollectionId}>
                          ${store.t("photos.bulk_choose_collection")}
                        </option>
                        ${collections.map(
                          (col) => html`<option
                            value=${col.id}
                            ?selected=${store.photosBulkTargetCollectionId === col.id}
                          >
                            ${col.name}
                          </option>`,
                        )}
                      </select>
                      <button
                        type="button"
                        id="btn-bulk-add-collection"
                        ?disabled=${selectedCount === 0 || !store.photosBulkTargetCollectionId}
                        @click=${() =>
                          void store.entity.bulkUpdatePhotos({
                            addCollection: store.photosBulkTargetCollectionId,
                          })}
                        class="btn btn-secondary btn-compact"
                      >
                        ${store.t("photos.bulk_add_to_collection")}
                      </button>
                      <button
                        type="button"
                        id="btn-bulk-remove-collection"
                        ?disabled=${selectedCount === 0 || !store.photosBulkTargetCollectionId}
                        @click=${() =>
                          void store.entity.bulkUpdatePhotos({
                            removeCollection: store.photosBulkTargetCollectionId,
                          })}
                        class="btn btn-secondary btn-compact"
                      >
                        ${store.t("photos.bulk_remove_from_collection")}
                      </button>`
                  : nothing}
                <button
                  type="button"
                  id="btn-bulk-delete-photos"
                  ?disabled=${deletableSelectedCount === 0}
                  @click=${() => store.entity.requestBulkDeletePhotos()}
                  class="btn btn-danger btn-compact"
                >
                  ${store.t("photos.bulk_delete_btn")}
                </button>
              </div>
            </div>`
          : nothing}

        <div id="photos-grid" class="photo-grid">
          ${pageItems.length === 0
            ? html`<p class="empty-state">${store.t("photos.empty_library")}</p>`
            : repeat(
                pageItems,
                (p) => p.id,
                (photo) => {
                  const isSelected = store.photosSelectedIds.has(photo.id);
                  const isDynamic = isPhotoDynamic(photo);
                  const isUploaded = isPhotoUploaded(photo);
                  const thumbSrc = photo.thumb_url || photo.preview_url || "";
                  const photoCols = (photo.collections || [])
                    .map((cid) => collectionNameMap.get(cid))
                    .filter((n): n is string => Boolean(n));

                  const onTileClick = (): void => {
                    if (store.photosSelectMode) {
                      toggleSelectPhoto(photo.id);
                    } else {
                      store.entity.openPhotoEditModal(photo);
                    }
                  };

                    const badgeLabel = isDynamic
                      ? store.t("photos.badge_dynamic")
                      : !isUploaded
                        ? store.t("photos.badge_default")
                        : photo.source_kind === "media_import"
                          ? store.t("photos.badge_media")
                          : "";
                    const tileBaseAria = store.photosSelectMode
                      ? store.t("photos.select_photo_aria", { name: photo.name || photo.id })
                      : store.t("photos.edit_photo_aria", { name: photo.name || photo.id });
                    return html`<div
                    data-photo-id=${photo.id}
                    class="photo-tile ${isSelected ? "selected" : ""}"
                  >
                    ${store.photosSelectMode
                      ? html`<input
                          type="checkbox"
                          aria-label=${store.t("photos.select_photo_aria", {
                            name: photo.name || photo.id,
                          })}
                          .checked=${isSelected}
                          @change=${() => toggleSelectPhoto(photo.id)}
                          class="photo-tile-check"
                        />`
                      : nothing}
                    <button
                      type="button"
                      aria-label=${badgeLabel ? `${tileBaseAria}, ${badgeLabel}` : tileBaseAria}
                      @click=${onTileClick}
                      class="photo-tile-thumb-btn"
                    >
                      ${thumbSrc
                        ? html`<img
                            src=${thumbSrc}
                            alt=${photo.name || photo.id}
                            loading="lazy"
                            class="photo-tile-img"
                          />`
                        : nothing}
                      ${badgeLabel
                        ? html`<span class="photo-tile-badge">${badgeLabel}</span>`
                        : nothing}
                    </button>
                    <div class="photo-tile-meta">
                      <span class="photo-tile-name">${photo.name || photo.id}</span>
                      ${photoCols.length > 0
                        ? html`<div class="photo-tile-sub">
                            ${photoCols.slice(0, 2).map((cn) => html`<span class="chip">${cn}</span>`)}
                            ${photoCols.length > 2
                              ? html`<span class="chip">+${photoCols.length - 2}</span>`
                              : nothing}
                          </div>`
                        : nothing}
                    </div>
                  </div>`;
                },
              )}
        </div>

        ${totalFiltered > PHOTO_LIBRARY_PAGE_SIZE
          ? html`<div class="photo-pagination">
              <span class="row-description">
                ${store.t("photos.page_status", {
                  start: fmtNumber(startIdx + 1, store.hass, 0),
                  end: fmtNumber(Math.min(startIdx + pageItems.length, totalFiltered), store.hass, 0),
                  total: fmtNumber(totalFiltered, store.hass, 0),
                })}
              </span>
              <div class="photo-toolbar-end">
                <button
                  type="button"
                  id="btn-photos-prev-page"
                  ?disabled=${currentPage <= 1}
                  @click=${() => {
                    store.photosPage = Math.max(1, currentPage - 1);
                    store.host.requestUpdate();
                  }}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.t("photos.prev_page")}
                </button>
                <button
                  type="button"
                  id="btn-photos-next-page"
                  ?disabled=${currentPage >= totalPages}
                  @click=${() => {
                    store.photosPage = Math.min(totalPages, currentPage + 1);
                    store.host.requestUpdate();
                  }}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.t("photos.next_page")}
                </button>
              </div>
            </div>`
          : nothing}`,
    })}
  </section>`;
}
