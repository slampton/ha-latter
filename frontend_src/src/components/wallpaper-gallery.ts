/**
 * Wallpaper Gallery & Multipart XHR Upload Component (Device & System scopes, `D-25`, `Q5`, `Q9a`).
 */

import { html, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { StudioScope, WallpaperItem } from "../types.js";
import { fmtNumber } from "../utils/format.js";
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
    return html`<p class="empty-state">${store.t("wp_gallery.empty")}</p>`;
  }
  const shapeClass = displayShape === "circle" ? "circle" : "square";

  return html`${repeat(
    items,
    (wp, idx) => `${wp.id}::${idx}`,
    (wp) => {
      const label = wp.name || wp.id;
      const isActive = Boolean(wp.active);
      const isFav = Boolean(wp.favorite);
      const canDelete = Boolean(wp.deletable ?? wp.kind === "upload");
      const thumbSrc = wp.thumb_url || wp.preview_url || "";
      const activeCls = isActive ? "wp-card active" : "wp-card";
      const onUse = (): void => {
        void store.entity.selectWallpaperSource(wp.id);
      };
      const onFav = (): void => {
        void store.entity.toggleWallpaperFav(wp.id);
      };
      const onDel = (): void => {
        store.entity.requestDeleteWallpaper(wp.id, label);
      };

      const clickableThumb = scope === "device" && !isActive;
      const thumbImg = thumbSrc
        ? html`<img
            src=${thumbSrc}
            alt=${clickableThumb ? "" : label}
            loading="lazy"
            class="wp-thumb ${shapeClass}"
          />`
        : html`<div class="wp-thumb ${shapeClass}" aria-hidden="true"></div>`;

      return html`<div class=${activeCls}>
        ${clickableThumb
          ? html`<button
              type="button"
              tabindex="-1"
              aria-hidden="true"
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
                  ? html`<span class="chip chip-primary">${store.t("common.active")}</span>`
                  : html`<button
                      type="button"
                      aria-label=${store.t("wp_gallery.use_aria", { name: label })}
                      @click=${onUse}
                      class="btn btn-secondary btn-compact"
                    >
                      ${store.t("action.use")}
                    </button>`}
                <button
                  type="button"
                  aria-label=${isFav
                    ? store.t("wp_gallery.star_remove_aria", { name: label })
                    : store.t("wp_gallery.star_add_aria", { name: label })}
                  aria-pressed=${String(isFav)}
                  title=${isFav
                    ? store.t("wp_gallery.star_active_title")
                    : store.t("wp_gallery.star_inactive_title")}
                  @click=${onFav}
                  class="btn-icon wp-star-btn${isFav ? " starred" : ""}"
                >
                  ${renderStarIcon(isFav)}
                </button>
                ${canDelete
                  ? renderTrashIconButton(
                      store.t("wp_gallery.delete_aria", { name: label }),
                      onDel,
                    )
                  : nothing}`
            : canDelete
              ? html`<span class="chip chip-primary">${store.t("wp_gallery.uploaded")}</span>
                  ${renderTrashIconButton(
                    store.t("wp_gallery.delete_aria", { name: label }),
                    onDel,
                  )}`
              : html`<span class="chip">${store.t("wp_gallery.builtin")}</span>`}
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
      void store.entity.uploadWallpaper(scope);
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
      aria-label=${store.t("wp_gallery.file_aria")}
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
      ${isUploadingThisScope ? store.t("wp_gallery.uploading") : store.t("wp_gallery.upload_photo")}
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
      <span>${store.t("wp_gallery.uploading_photo")}</span>
      <span class="chip chip-primary">${fmtNumber(store.uploadPercent, store.hass, 0)}%</span>
    </div>
    <div
      role="progressbar"
      aria-label=${store.t("wp_gallery.upload_progress_aria")}
      aria-valuenow=${String(store.uploadPercent)}
      aria-valuemin="0"
      aria-valuemax="100"
      class="upload-progress"
    >
      <div class="upload-progress-fill" style=${pctStyle}></div>
    </div>
  </div>`;
}
