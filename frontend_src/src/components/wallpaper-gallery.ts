/**
 * Wallpaper Gallery & Multipart XHR Upload Component (Device & System scopes).
 */

import { html, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { StudioScope, WallpaperItem } from "../types.js";

export function renderWallpaperGalleryItems(
  store: StudioStore,
  scope: StudioScope,
  items: readonly WallpaperItem[],
  displayShape: string,
): TemplateResult {
  if (!items.length) {
    return html`<p class="empty-state">No wallpapers available yet.</p>`;
  }
  const shapeClass = displayShape === "circle" ? "circle" : "square";

  return html`${repeat(
    items,
    (wp) => wp.id,
    (wp) => {
      const isActive = Boolean(wp.active);
      const isFav = Boolean(wp.favorite);
      const canDelete = Boolean(wp.deletable ?? wp.kind === "upload");
      const thumbSrc = wp.thumb_url || wp.preview_url || "";
      const activeCls = isActive ? "wp-card active" : "wp-card";
      const onUse = (): void => {
        void store.selectWallpaperSource(wp.id);
      };
      const onFav = (): void => {
        void store.toggleWallpaperFav(wp.id);
      };
      const onDel = (): void => {
        void store.deleteWallpaper(scope, wp.id);
      };

      return html`<div class=${activeCls}>
        ${thumbSrc
          ? html`<img src=${thumbSrc} alt=${wp.name || wp.id} loading="lazy" class="wp-thumb ${shapeClass}" />`
          : html`<div class="wp-thumb ${shapeClass}"></div>`}
        <div class="wp-title">${wp.name || wp.id}</div>
        <div class="wp-actions">
          ${scope === "device"
            ? html`<button
                  type="button"
                  ?disabled=${isActive}
                  @click=${onUse}
                  class="btn ${isActive ? "btn-primary" : "btn-secondary"} btn-compact"
                >
                  ${isActive ? "Active" : "Use"}
                </button>
                <button
                  type="button"
                  aria-label=${isFav ? "Remove from Favorites" : "Add to Favorites"}
                  @click=${onFav}
                  class="btn btn-text btn-compact"
                >
                  ${isFav ? "Starred" : "Star"}
                </button>`
            : nothing}
          ${canDelete
            ? html`<button type="button" @click=${onDel} class="btn btn-danger btn-compact">Delete</button>`
            : nothing}
        </div>
      </div>`;
    },
  )}`;
}

export function renderWallpaperUploadBar(store: StudioStore, scope: StudioScope): TemplateResult {
  const selectedFile =
    scope === "device" ? store.selectedDeviceWallpaperFile : store.selectedSystemWallpaperFile;
  const isUploadingThisScope = store.uploadBusy && store.uploadScope === scope;
  const pctStyle = `--upload-pct:${store.uploadPercent}%`;

  const onFilePick = (ev: Event): void => {
    const input = ev.currentTarget as HTMLInputElement;
    const f = input.files && input.files[0] ? input.files[0] : null;
    if (scope === "device") {
      store.selectedDeviceWallpaperFile = f;
    } else {
      store.selectedSystemWallpaperFile = f;
    }
    store.host.requestUpdate();
  };

  const onUpload = (): void => {
    void store.uploadWallpaper(scope);
  };

  return html`<div class="stack">
    <div class="input-action-row">
      <input
        type="file"
        id=${scope === "device" ? "input-upload-wp" : "input-upload-sys-wp"}
        accept="image/*"
        aria-label="Wallpaper image (up to 15 MB)"
        @change=${onFilePick}
      />
      <button
        type="button"
        id=${scope === "device" ? "btn-upload-wp" : "btn-upload-sys-wp"}
        ?disabled=${!selectedFile || store.uploadBusy}
        @click=${onUpload}
        class="btn btn-primary"
      >
        ${isUploadingThisScope ? "Uploading…" : "Upload Photo"}
      </button>
      ${isUploadingThisScope
        ? html`<span class="chip chip-primary">${store.uploadPercent}%</span>`
        : nothing}
    </div>
    ${isUploadingThisScope
      ? html`<div class="upload-progress" role="progressbar" aria-valuenow=${String(store.uploadPercent)} aria-valuemin="0" aria-valuemax="100">
          <div class="upload-progress-fill" style=${pctStyle}></div>
        </div>`
      : nothing}
  </div>`;
}
