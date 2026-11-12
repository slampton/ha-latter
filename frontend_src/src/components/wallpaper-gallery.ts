/**
 * Wallpaper Gallery & Multipart XHR Upload Component (Device & System scopes).
 */

import { html, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { StudioScope, WallpaperItem } from "../types.js";
import { renderTrashIconButton } from "./controls.js";

function renderStarIcon(filled: boolean): TemplateResult {
  if (filled) {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.62L12 2 9.19 8.62 2 9.24l5.45 4.73L5.82 21 12 17.27Z"
      />
    </svg>`;
  }
  return html`<svg viewBox="0 0 24 24" aria-hidden="true">
    <path
      d="M12 15.39l-3.76 2.27.99-4.28-3.32-2.88 4.38-.38L12 6.09l1.71 4.03 4.38.38-3.32 2.88.99 4.28L12 15.39M22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.45 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24Z"
    />
  </svg>`;
}

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
      const label = wp.name || wp.id;
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

      const thumbImg = thumbSrc
        ? html`<img src=${thumbSrc} alt=${label} loading="lazy" class="wp-thumb ${shapeClass}" />`
        : html`<div class="wp-thumb ${shapeClass}"></div>`;

      return html`<div class=${activeCls}>
        ${scope === "device" && !isActive
          ? html`<button
              type="button"
              aria-label=${`Use wallpaper ${label}`}
              @click=${onUse}
              class="wp-thumb-btn ${shapeClass}"
            >
              ${thumbImg}
            </button>`
          : thumbImg}
        <div class="wp-title">${label}</div>
        <div class="wp-actions">
          ${scope === "device"
            ? html`${isActive
                  ? html`<span class="chip chip-primary">Active</span>`
                  : html`<button type="button" @click=${onUse} class="btn btn-secondary btn-compact">
                      Use
                    </button>`}
                <button
                  type="button"
                  aria-label=${isFav ? `Remove ${label} from favorites` : `Star ${label} for rotation`}
                  aria-pressed=${String(isFav)}
                  title=${isFav ? "Starred for rotation" : "Star for rotation"}
                  @click=${onFav}
                  class="btn-icon wp-star-btn${isFav ? " starred" : ""}"
                >
                  ${renderStarIcon(isFav)}
                </button>
                ${canDelete ? renderTrashIconButton(`Delete wallpaper ${label}`, onDel) : nothing}`
            : canDelete
              ? html`<span class="chip chip-primary">Uploaded</span>
                  ${renderTrashIconButton(`Delete wallpaper ${label}`, onDel)}`
              : html`<span class="chip">Built-in</span>`}
        </div>
      </div>`;
    },
  )}`;
}

export function renderWallpaperUploadTrigger(
  store: StudioStore,
  scope: StudioScope,
): TemplateResult {
  const isUploadingThisScope = store.uploadBusy && store.uploadScope === scope;
  const inputId = scope === "device" ? "input-upload-wp" : "input-upload-sys-wp";
  const btnId = scope === "device" ? "btn-upload-wp" : "btn-upload-sys-wp";

  const onFilePick = (ev: Event): void => {
    const input = ev.currentTarget as HTMLInputElement;
    const f = input.files && input.files[0] ? input.files[0] : null;
    if (scope === "device") {
      store.selectedDeviceWallpaperFile = f;
    } else {
      store.selectedSystemWallpaperFile = f;
    }
    if (f) {
      void store.uploadWallpaper(scope);
    } else {
      store.host.requestUpdate();
    }
  };

  const onTriggerPick = (ev: Event): void => {
    const btn = ev.currentTarget as HTMLElement | null;
    const fileInput = btn?.parentElement?.querySelector("input[type='file']") as
      | HTMLInputElement
      | null;
    fileInput?.click();
  };

  return html`<span class="wp-upload-trigger">
    <input
      type="file"
      id=${inputId}
      accept="image/*"
      aria-label="Wallpaper image (up to 15 MB)"
      @change=${onFilePick}
      class="offscreen"
    />
    <button
      type="button"
      id=${btnId}
      ?disabled=${store.uploadBusy}
      @click=${onTriggerPick}
      class="btn btn-secondary btn-compact"
    >
      ${isUploadingThisScope ? "Uploading…" : "Upload Photo"}
    </button>
  </span>`;
}

export function renderWallpaperUploadProgress(
  store: StudioStore,
  scope: StudioScope,
): TemplateResult | typeof nothing {
  const isUploadingThisScope = store.uploadBusy && store.uploadScope === scope;
  if (!isUploadingThisScope) return nothing;
  const pctStyle = `--upload-pct:${store.uploadPercent}%`;

  return html`<div class="stack">
    <div class="wp-upload-status">
      <span>Uploading photo…</span>
      <span class="chip chip-primary">${store.uploadPercent}%</span>
    </div>
    <div
      class="upload-progress"
      role="progressbar"
      aria-valuenow=${String(store.uploadPercent)}
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div class="upload-progress-fill" style=${pctStyle}></div>
    </div>
  </div>`;
}
