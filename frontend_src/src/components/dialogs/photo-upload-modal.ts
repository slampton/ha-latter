/**
 * Multi-File Photo Upload & Interactive Crop Staging Modal (`#latter-photo-upload-modal`)
 * and Photo Editor & Non-Destructive Crop Modal (`#latter-photo-edit-modal`) (`D-072`).
 * - Native `<dialog>`, Pointer Events pan capture, zoom `1.0x-3.0x`, Square+Circle / Round / Widescreen switcher
 * - Zero non-`--*` inline styles; canvas image cache scoped to WeakMap / bounded Map
 */

import { focusSafe, html, nothing, type TemplateResult } from "../../lib/lit.js";
import { isPhotoUploaded } from "../../state/photo-ops.js";
import type { StudioStore } from "../../state/store.js";
import type { CropPreviewAspect, PhotoCrop } from "../../types.js";
import {
  applyCanvasPanDelta,
  cropPreviewCanvasSize,
  DEFAULT_PHOTO_CROP,
  normalizePhotoCrop,
  paintCropCanvas,
} from "../../utils/crop-math.js";
import { fmtNumber } from "../../utils/format.js";

const loadedImageCache = new Map<string, HTMLImageElement>();
const MAX_CACHED_CROP_IMAGES = 32;

function getOrLoadImage(url: string, onLoad: () => void): HTMLImageElement | null {
  if (!url || typeof Image === "undefined") return null;
  const existing = loadedImageCache.get(url);
  if (existing) {
    if (existing.complete && existing.naturalWidth > 0) {
      return existing;
    }
    return null;
  }
  if (loadedImageCache.size >= MAX_CACHED_CROP_IMAGES) {
    const firstKey = loadedImageCache.keys().next().value;
    if (firstKey) loadedImageCache.delete(firstKey);
  }
  const img = new Image();
  img.crossOrigin = "anonymous";
  img.onload = () => {
    onLoad();
  };
  img.src = url;
  loadedImageCache.set(url, img);
  return img.complete && img.naturalWidth > 0 ? img : null;
}

const activeDragMap = new WeakMap<
  HTMLCanvasElement,
  { pointerId: number; lastX: number; lastY: number }
>();

export function syncPhotoCropCanvases(renderRoot: ShadowRoot, store: StudioStore): void {
  // 1. Upload staging main crop canvas + filmstrip thumbs
  if (store.photoUploadModal.open && store.photoUploadModal.files.length > 0) {
    const modal = store.photoUploadModal;
    const active = modal.files[modal.activeIndex] || modal.files[0];
    const mainCanvas = renderRoot.getElementById(
      "latter-upload-crop-canvas",
    ) as HTMLCanvasElement | null;
    if (mainCanvas && active) {
      const img = getOrLoadImage(active.objectUrl, () => store.host.requestUpdate());
      if (img && (active.width !== img.naturalWidth || active.height !== img.naturalHeight)) {
        active.width = img.naturalWidth;
        active.height = img.naturalHeight;
      }
      paintCropCanvas(mainCanvas, img, active.crop, modal.previewAspect, { showGuides: true });
    }

    for (let i = 0; i < modal.files.length; i += 1) {
      const staged = modal.files[i];
      const thumbCanvas = renderRoot.getElementById(
        `latter-upload-thumb-${staged.id}`,
      ) as HTMLCanvasElement | null;
      if (!thumbCanvas) continue;
      const img = getOrLoadImage(staged.objectUrl, () => store.host.requestUpdate());
      paintCropCanvas(thumbCanvas, img, staged.crop, "square", { showGuides: false });
    }
  }

  // 2. Photo Editor crop canvas
  if (store.photoEditModal.open && store.photoEditModal.photoId) {
    const modal = store.photoEditModal;
    const photo = (store.state?.system_wallpapers || []).find((p) => p.id === modal.photoId);
    const editCanvas = renderRoot.getElementById(
      "latter-edit-crop-canvas",
    ) as HTMLCanvasElement | null;
    if (editCanvas && photo) {
      const srcUrl = photo.orig_url || photo.thumb_url || photo.preview_url || "";
      const img = getOrLoadImage(srcUrl, () => store.host.requestUpdate());
      paintCropCanvas(editCanvas, img, modal.crop, modal.previewAspect, { showGuides: true });
    }
  }
}

function attachCropPointerHandlers(
  getCrop: () => PhotoCrop,
  getSourceDims: () => { width: number; height: number },
  onCropChange: (next: PhotoCrop) => void,
  disabled: boolean,
): {
  onPointerDown: (ev: Event) => void;
  onPointerMove: (ev: Event) => void;
  onPointerUp: (ev: Event) => void;
} {
  return {
    onPointerDown: (ev: Event) => {
      if (disabled) return;
      const pev = ev as PointerEvent;
      const canvas = pev.currentTarget as HTMLCanvasElement;
      canvas.setPointerCapture?.(pev.pointerId);
      canvas.classList.add("dragging");
      activeDragMap.set(canvas, {
        pointerId: pev.pointerId,
        lastX: pev.clientX,
        lastY: pev.clientY,
      });
    },
    onPointerMove: (ev: Event) => {
      if (disabled) return;
      const pev = ev as PointerEvent;
      const canvas = pev.currentTarget as HTMLCanvasElement;
      const drag = activeDragMap.get(canvas);
      if (!drag || drag.pointerId !== pev.pointerId) return;
      const dx = pev.clientX - drag.lastX;
      const dy = pev.clientY - drag.lastY;
      drag.lastX = pev.clientX;
      drag.lastY = pev.clientY;
      const rect = canvas.getBoundingClientRect();
      const scaleX = rect.width > 0 ? canvas.width / rect.width : 1;
      const scaleY = rect.height > 0 ? canvas.height / rect.height : 1;
      const dims = getSourceDims();
      const next = applyCanvasPanDelta(
        getCrop(),
        dx * scaleX,
        dy * scaleY,
        dims.width || canvas.width,
        dims.height || canvas.height,
        canvas.width,
        canvas.height,
      );
      onCropChange(next);
    },
    onPointerUp: (ev: Event) => {
      const pev = ev as PointerEvent;
      const canvas = pev.currentTarget as HTMLCanvasElement;
      activeDragMap.delete(canvas);
      canvas.classList.remove("dragging");
      if (canvas.hasPointerCapture?.(pev.pointerId)) {
        canvas.releasePointerCapture(pev.pointerId);
      }
    },
  };
}

function renderAspectSwitcher(
  store: StudioStore,
  aspect: CropPreviewAspect,
  onSelect: (next: CropPreviewAspect) => void,
): TemplateResult {
  const options: ReadonlyArray<{ id: CropPreviewAspect; label: string }> = [
    { id: "square", label: store.t("photo_edit.aspect_square") },
    { id: "round", label: store.t("photo_edit.aspect_round") },
    { id: "widescreen", label: store.t("photo_edit.aspect_widescreen") },
  ];
  return html`<div
    role="radiogroup"
    aria-label=${store.t("photo_edit.aspect_aria")}
    class="segmented"
  >
    ${options.map(
      (opt) => html`<button
        type="button"
        role="radio"
        aria-checked=${aspect === opt.id ? "true" : "false"}
        @click=${() => onSelect(opt.id)}
        class=${aspect === opt.id ? "active" : ""}
      >
        ${opt.label}
      </button>`,
    )}
  </div>`;
}

export function renderPhotoUploadDialog(store: StudioStore): TemplateResult {
  const modal = store.photoUploadModal;
  const close = (): void => store.entity.closePhotoUploadModal();
  const onBackdropClick = (ev: Event): void => {
    if (ev.target === ev.currentTarget && !modal.uploading) {
      close();
    }
  };

  if (!modal.open) {
    return html`<dialog
      id="latter-photo-upload-modal"
      aria-labelledby="latter-photo-upload-title"
      @cancel=${(ev: Event) => {
        if (modal.uploading) ev.preventDefault();
        else close();
      }}
      @click=${onBackdropClick}
      class="studio-dialog photo-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  const collections = store.state?.photo_collections || [];
  const active = modal.files[modal.activeIndex] || modal.files[0] || null;
  const canvasSize = cropPreviewCanvasSize(modal.previewAspect);
  const pctStyle = `--upload-pct:${modal.currentPercent}%`;

  const updateActiveItem = (patch: Partial<{ name: string; crop: PhotoCrop }>): void => {
    if (!active) return;
    const nextFiles = modal.files.map((item, idx) =>
      idx === modal.activeIndex ? { ...item, ...patch } : item,
    );
    store.photoUploadModal = { ...store.photoUploadModal, files: nextFiles };
    store.host.requestUpdate();
  };

  const ptr = attachCropPointerHandlers(
    () => active?.crop || { ...DEFAULT_PHOTO_CROP },
    () => {
      const cached = active?.objectUrl ? loadedImageCache.get(active.objectUrl) : null;
      return {
        width: cached?.naturalWidth || active?.width || canvasSize.width,
        height: cached?.naturalHeight || active?.height || canvasSize.height,
      };
    },
    (nextCrop) => updateActiveItem({ crop: nextCrop }),
    modal.uploading,
  );

  const onFileInputChange = (ev: Event): void => {
    const input = ev.currentTarget as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      store.entity.stageUploadFiles(input.files);
      input.value = "";
    }
  };

  const onTriggerFilePicker = (ev: Event): void => {
    const root = (ev.currentTarget as HTMLElement | null)?.closest(".dialog-body");
    const fileInput = root?.querySelector("#input-photo-upload-files") as HTMLInputElement | null;
    fileInput?.click();
  };

  const onDragOver = (ev: Event): void => {
    ev.preventDefault();
    if (!store.photoUploadModal.draggingFiles) {
      store.photoUploadModal = { ...store.photoUploadModal, draggingFiles: true };
      store.host.requestUpdate();
    }
  };

  const onDragLeave = (): void => {
    if (store.photoUploadModal.draggingFiles) {
      store.photoUploadModal = { ...store.photoUploadModal, draggingFiles: false };
      store.host.requestUpdate();
    }
  };

  const onDrop = (ev: Event): void => {
    ev.preventDefault();
    const dev = ev as DragEvent;
    store.photoUploadModal = { ...store.photoUploadModal, draggingFiles: false };
    if (dev.dataTransfer?.files && dev.dataTransfer.files.length > 0) {
      store.entity.stageUploadFiles(dev.dataTransfer.files);
    } else {
      store.host.requestUpdate();
    }
  };

  const uploadBtnLabel =
    modal.files.length === 1
      ? store.t("photo_upload.upload_all_one")
      : store.t("photo_upload.upload_all_many", {
          count: fmtNumber(modal.files.length, store.hass, 0),
        });

  return html`<dialog
    id="latter-photo-upload-modal"
    aria-labelledby="latter-photo-upload-title"
    @cancel=${(ev: Event) => {
      if (modal.uploading) ev.preventDefault();
      else close();
    }}
    @click=${onBackdropClick}
    class="studio-dialog photo-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-photo-upload-title" class="dialog-title">
          ${store.t("photo_upload.title")}
        </h3>
        ${modal.files.length > 0 && !modal.uploading
          ? html`<button
              type="button"
              id="btn-upload-add-more"
              @click=${onTriggerFilePicker}
              class="btn btn-secondary btn-compact"
            >
              ${store.t("photo_upload.add_more")}
            </button>`
          : nothing}
      </div>

      <input
        type="file"
        id="input-photo-upload-files"
        accept="image/*"
        multiple
        aria-label=${store.t("photo_upload.choose_files")}
        @change=${onFileInputChange}
        class="offscreen"
      />

      ${modal.files.length === 0
        ? html`<div
            id="photo-upload-dropzone"
            role="button"
            tabindex="0"
            @click=${onTriggerFilePicker}
            @keydown=${(ev: KeyboardEvent) => {
              if (ev.key === "Enter" || ev.key === " ") {
                ev.preventDefault();
                onTriggerFilePicker(ev);
              }
            }}
            @dragover=${onDragOver}
            @dragleave=${onDragLeave}
            @drop=${onDrop}
            class="crop-dropzone ${modal.draggingFiles ? "dragging" : ""}"
          >
            <strong>${store.t("photo_upload.dropzone_title")}</strong>
            <span class="row-description">${store.t("photo_upload.dropzone_hint")}</span>
            <span class="btn btn-primary btn-compact">${store.t("photo_upload.choose_files")}</span>
          </div>`
        : html`<div
            class="crop-stage-wrap"
            @dragover=${onDragOver}
            @dragleave=${onDragLeave}
            @drop=${onDrop}
          >
            ${renderAspectSwitcher(store, modal.previewAspect, (nextAspect) => {
              store.photoUploadModal = { ...store.photoUploadModal, previewAspect: nextAspect };
              store.host.requestUpdate();
            })}

            <canvas
              id="latter-upload-crop-canvas"
              width=${String(canvasSize.width)}
              height=${String(canvasSize.height)}
              @pointerdown=${ptr.onPointerDown}
              @pointermove=${ptr.onPointerMove}
              @pointerup=${ptr.onPointerUp}
              @pointercancel=${ptr.onPointerUp}
              class="crop-canvas ${modal.previewAspect === "round" ? "round" : ""}"
            ></canvas>

            <p class="row-description">${store.t("photo_edit.crop_hint")}</p>

            <div class="crop-controls-row">
              <div class="crop-zoom-control">
                <label for="upload-crop-zoom">${store.t("photo_edit.zoom_label")}</label>
                <input
                  type="range"
                  id="upload-crop-zoom"
                  min="1"
                  max="3"
                  step="0.05"
                  ?disabled=${modal.uploading}
                  .value=${String(active?.crop.zoom ?? 1)}
                  @input=${(ev: Event) => {
                    const z = Number((ev.currentTarget as HTMLInputElement).value) || 1;
                    updateActiveItem({
                      crop: normalizePhotoCrop({ ...(active?.crop || DEFAULT_PHOTO_CROP), zoom: z }),
                    });
                  }}
                />
                <span class="kv-value">${(active?.crop.zoom ?? 1).toFixed(2)}×</span>
              </div>
              <button
                type="button"
                id="btn-upload-reset-crop"
                ?disabled=${modal.uploading}
                @click=${() => updateActiveItem({ crop: { ...DEFAULT_PHOTO_CROP } })}
                class="btn btn-text btn-compact"
              >
                ${store.t("photo_edit.reset_crop")}
              </button>
            </div>
          </div>

          <div class="stacked-field">
            <label for="upload-photo-name">${store.t("photo_edit.name_label")}</label>
            <input
              type="text"
              id="upload-photo-name"
              placeholder=${store.t("photo_edit.name_placeholder")}
              ?disabled=${modal.uploading}
              .value=${focusSafe(active?.name || "")}
              @input=${(ev: Event) =>
                updateActiveItem({ name: (ev.currentTarget as HTMLInputElement).value })}
            />
          </div>

          ${modal.files.length > 1
            ? html`<div class="crop-filmstrip" role="list">
                ${modal.files.map(
                  (item, idx) => html`<div
                    role="listitem"
                    class="crop-filmstrip-item ${idx === modal.activeIndex ? "active" : ""}"
                  >
                    <button
                      type="button"
                      aria-label=${store.t("photo_upload.select_staged_aria", {
                        name: item.name,
                      })}
                      ?disabled=${modal.uploading}
                      @click=${() => {
                        store.photoUploadModal = {
                          ...store.photoUploadModal,
                          activeIndex: idx,
                        };
                        store.host.requestUpdate();
                      }}
                      class="wp-thumb-btn"
                    >
                      <canvas
                        id=${`latter-upload-thumb-${item.id}`}
                        width="56"
                        height="56"
                        class="crop-filmstrip-thumb"
                      ></canvas>
                    </button>
                    ${!modal.uploading
                      ? html`<button
                          type="button"
                          aria-label=${store.t("photo_upload.remove_staged_aria", {
                            name: item.name,
                          })}
                          @click=${() => store.entity.removeStagedUpload(idx)}
                          class="crop-filmstrip-remove"
                        >
                          ×
                        </button>`
                      : nothing}
                  </div>`,
                )}
              </div>`
            : nothing}

          <div class="stacked-field">
            <label for="upload-photo-collection">${store.t("photo_upload.collection_label")}</label>
            <div class="input-action-row">
              <select
                id="upload-photo-collection"
                ?disabled=${modal.uploading || modal.creatingCollection}
                .value=${modal.collectionId}
                @change=${(ev: Event) => {
                  store.photoUploadModal = {
                    ...store.photoUploadModal,
                    collectionId: (ev.currentTarget as HTMLSelectElement).value,
                  };
                  store.host.requestUpdate();
                }}
              >
                <option value="" ?selected=${!modal.collectionId}>
                  ${store.t("photo_upload.no_collection")}
                </option>
                ${collections.map(
                  (col) => html`<option value=${col.id} ?selected=${modal.collectionId === col.id}>
                    ${col.name}
                  </option>`,
                )}
              </select>
              ${!modal.newCollectionOpen
                ? html`<button
                    type="button"
                    id="btn-upload-new-collection"
                    ?disabled=${modal.uploading || modal.creatingCollection}
                    @click=${() => {
                      store.photoUploadModal = {
                        ...store.photoUploadModal,
                        newCollectionOpen: true,
                        newCollectionName: "",
                      };
                      store.host.requestUpdate();
                    }}
                    class="btn btn-secondary btn-compact"
                  >
                    ${store.t("photos.new_collection_btn")}
                  </button>`
                : nothing}
            </div>
            ${modal.newCollectionOpen
              ? html`<div class="input-action-row">
                  <input
                    type="text"
                    id="input-upload-new-collection-name"
                    aria-label=${store.t("photos.new_collection_btn")}
                    placeholder=${store.t("photos.new_collection_placeholder")}
                    ?disabled=${modal.uploading || modal.creatingCollection}
                    .value=${focusSafe(modal.newCollectionName)}
                    @input=${(ev: Event) => {
                      store.photoUploadModal = {
                        ...store.photoUploadModal,
                        newCollectionName: (ev.currentTarget as HTMLInputElement).value,
                      };
                      store.host.requestUpdate();
                    }}
                    @keydown=${(ev: KeyboardEvent) => {
                      if (ev.key === "Enter") {
                        ev.preventDefault();
                        void store.entity.createUploadCollection();
                      } else if (ev.key === "Escape") {
                        ev.preventDefault();
                        ev.stopPropagation();
                        store.photoUploadModal = {
                          ...store.photoUploadModal,
                          newCollectionOpen: false,
                          newCollectionName: "",
                        };
                        store.host.requestUpdate();
                      }
                    }}
                  />
                  <button
                    type="button"
                    id="btn-upload-create-collection"
                    ?disabled=${modal.uploading ||
                    modal.creatingCollection ||
                    !modal.newCollectionName.trim()}
                    @click=${() => void store.entity.createUploadCollection()}
                    class="btn btn-secondary btn-compact"
                  >
                    ${store.t("photos.create_collection")}
                  </button>
                  <button
                    type="button"
                    id="btn-upload-cancel-collection"
                    ?disabled=${modal.uploading || modal.creatingCollection}
                    @click=${() => {
                      store.photoUploadModal = {
                        ...store.photoUploadModal,
                        newCollectionOpen: false,
                        newCollectionName: "",
                      };
                      store.host.requestUpdate();
                    }}
                    class="btn btn-text btn-compact"
                  >
                    ${store.t("action.cancel")}
                  </button>
                </div>`
              : nothing}
          </div>

          ${modal.uploading
            ? html`<div class="stack">
                <div class="wp-upload-status">
                  <span>
                    ${store.t("photo_upload.uploading_progress", {
                      current: fmtNumber(modal.currentIndex, store.hass, 0),
                      total: fmtNumber(modal.files.length, store.hass, 0),
                      percent: fmtNumber(modal.currentPercent, store.hass, 0),
                    })}
                  </span>
                </div>
                <div
                  role="progressbar"
                  aria-label=${store.t("wp_gallery.upload_progress_aria")}
                  aria-valuenow=${String(modal.currentPercent)}
                  aria-valuemin="0"
                  aria-valuemax="100"
                  class="upload-progress"
                >
                  <div class="upload-progress-fill" style=${pctStyle}></div>
                </div>
              </div>`
            : nothing}`}

      <div class="dialog-actions">
        <button
          type="button"
          ?disabled=${modal.uploading}
          @click=${close}
          class="btn btn-secondary"
        >
          ${store.t("action.cancel")}
        </button>
        <button
          type="button"
          id="btn-upload-submit-all"
          ?disabled=${modal.uploading || modal.files.length === 0}
          @click=${() => void store.entity.uploadAllStagedPhotos()}
          class="btn btn-primary"
        >
          ${modal.uploading ? store.t("wp_gallery.uploading") : uploadBtnLabel}
        </button>
      </div>
    </div>
  </dialog>`;
}

export function renderPhotoEditDialog(store: StudioStore): TemplateResult {
  const modal = store.photoEditModal;
  const close = (): void => store.entity.closePhotoEditModal();
  const onBackdropClick = (ev: Event): void => {
    if (ev.target === ev.currentTarget && !modal.busy) {
      close();
    }
  };

  if (!modal.open || !modal.photoId) {
    return html`<dialog
      id="latter-photo-edit-modal"
      aria-labelledby="latter-photo-edit-title"
      @cancel=${close}
      @click=${onBackdropClick}
      class="studio-dialog photo-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  const photo = (store.state?.system_wallpapers || []).find((p) => p.id === modal.photoId);
  const uploaded = photo ? isPhotoUploaded(photo) : false;
  const collections = store.state?.photo_collections || [];
  const canvasSize = cropPreviewCanvasSize(modal.previewAspect);

  const ptr = attachCropPointerHandlers(
    () => modal.crop,
    () => {
      const srcUrl = photo?.orig_url || photo?.thumb_url || photo?.preview_url || "";
      const cached = srcUrl ? loadedImageCache.get(srcUrl) : null;
      return {
        width: cached?.naturalWidth || photo?.width || canvasSize.width,
        height: cached?.naturalHeight || photo?.height || canvasSize.height,
      };
    },
    (nextCrop) => {
      store.photoEditModal = { ...store.photoEditModal, crop: nextCrop };
      store.host.requestUpdate();
    },
    modal.busy || !uploaded,
  );

  const toggleCollection = (colId: string): void => {
    const exists = modal.collections.includes(colId);
    const next = exists
      ? modal.collections.filter((id) => id !== colId)
      : [...modal.collections, colId];
    store.photoEditModal = { ...store.photoEditModal, collections: next };
    store.host.requestUpdate();
  };

  return html`<dialog
    id="latter-photo-edit-modal"
    aria-labelledby="latter-photo-edit-title"
    @cancel=${close}
    @click=${onBackdropClick}
    class="studio-dialog photo-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-photo-edit-title" class="dialog-title">
          ${store.t("photo_edit.title")}
        </h3>
        ${photo?.width && photo?.height
          ? html`<span class="chip">
              ${store.t("photo_edit.dimensions_meta", {
                width: fmtNumber(photo.width, store.hass, 0),
                height: fmtNumber(photo.height, store.hass, 0),
              })}
            </span>`
          : nothing}
      </div>

      ${uploaded
        ? html`<div class="crop-stage-wrap">
              ${renderAspectSwitcher(store, modal.previewAspect, (nextAspect) => {
                store.photoEditModal = { ...store.photoEditModal, previewAspect: nextAspect };
                store.host.requestUpdate();
              })}

              <canvas
                id="latter-edit-crop-canvas"
                width=${String(canvasSize.width)}
                height=${String(canvasSize.height)}
                @pointerdown=${ptr.onPointerDown}
                @pointermove=${ptr.onPointerMove}
                @pointerup=${ptr.onPointerUp}
                @pointercancel=${ptr.onPointerUp}
                class="crop-canvas ${modal.previewAspect === "round" ? "round" : ""}"
              ></canvas>

              <p class="row-description">${store.t("photo_edit.crop_hint")}</p>

              <div class="crop-controls-row">
                <div class="crop-zoom-control">
                  <label for="edit-crop-zoom">${store.t("photo_edit.zoom_label")}</label>
                  <input
                    type="range"
                    id="edit-crop-zoom"
                    min="1"
                    max="3"
                    step="0.05"
                    ?disabled=${modal.busy}
                    .value=${String(modal.crop.zoom)}
                    @input=${(ev: Event) => {
                      const z = Number((ev.currentTarget as HTMLInputElement).value) || 1;
                      store.photoEditModal = {
                        ...store.photoEditModal,
                        crop: normalizePhotoCrop({ ...modal.crop, zoom: z }),
                      };
                      store.host.requestUpdate();
                    }}
                  />
                  <span class="kv-value">${modal.crop.zoom.toFixed(2)}×</span>
                </div>
                <button
                  type="button"
                  id="btn-edit-reset-crop"
                  ?disabled=${modal.busy}
                  @click=${() => {
                    store.photoEditModal = {
                      ...store.photoEditModal,
                      crop: { ...DEFAULT_PHOTO_CROP },
                    };
                    store.host.requestUpdate();
                  }}
                  class="btn btn-text btn-compact"
                >
                  ${store.t("photo_edit.reset_crop")}
                </button>
              </div>
            </div>

            <div class="stacked-field">
              <label for="edit-photo-name">${store.t("photo_edit.name_label")}</label>
              <input
                type="text"
                id="edit-photo-name"
                placeholder=${store.t("photo_edit.name_placeholder")}
                ?disabled=${modal.busy}
                .value=${focusSafe(modal.name)}
                @input=${(ev: Event) => {
                  store.photoEditModal = {
                    ...store.photoEditModal,
                    name: (ev.currentTarget as HTMLInputElement).value,
                  };
                }}
              />
            </div>`
        : html`<div class="photo-pool-preview">
            ${photo?.thumb_url
              ? html`<img
                  src=${photo.thumb_url}
                  alt=${photo.name || photo.id}
                  class="photo-pool-thumb"
                />`
              : nothing}
            <div class="photo-pool-info">
              <span class="photo-pool-title">${photo?.name || modal.photoId}</span>
              <span class="photo-pool-meta">${store.t("wp_gallery.builtin")}</span>
            </div>
          </div>`}

      ${photo?.media_source_path
        ? html`<p class="help-text">
            ${store.t("photo_edit.source_media", { path: photo.media_source_path })}
          </p>`
        : nothing}

      <div class="stacked-field">
        <span class="field-label">${store.t("photo_edit.collections_label")}</span>
        ${collections.length > 0
          ? html`<div role="group" aria-label=${store.t("photo_edit.collections_label")} class="pill-list">
              ${collections.map((col) => {
                const on = modal.collections.includes(col.id);
                return html`<span class="pill ${on ? "enabled" : ""}">
                  <button
                    type="button"
                    aria-pressed=${on ? "true" : "false"}
                    ?disabled=${modal.busy}
                    @click=${() => toggleCollection(col.id)}
                    class="pill-toggle"
                  >
                    ${col.name}
                  </button>
                </span>`;
              })}
            </div>`
          : html`<p class="row-description">${store.t("photo_edit.collections_empty")}</p>`}
      </div>

      <div class="dialog-actions ${uploaded ? "with-secondary" : ""}">
        ${uploaded
          ? html`<button
              type="button"
              id="btn-edit-delete-photo"
              ?disabled=${modal.busy}
              @click=${() => {
                const pid = modal.photoId;
                const pname = modal.name || photo?.name || pid;
                close();
                store.entity.requestDeletePhoto(pid, pname);
              }}
              class="btn btn-danger"
            >
              ${store.t("action.delete")}
            </button>`
          : nothing}
        <div class="dialog-actions-end">
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
            id="btn-edit-save-photo"
            ?disabled=${modal.busy}
            @click=${() => void store.entity.savePhotoEditModal()}
            class="btn btn-primary"
          >
            ${store.t("action.save")}
          </button>
        </div>
      </div>
    </div>
  </dialog>`;
}
