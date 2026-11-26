/**
 * Multi-File Photo Upload & Interactive Crop Staging Modal (`#latter-photo-upload-modal`)
 * and Photo Editor & Non-Destructive Crop Modal (`#latter-photo-edit-modal`) (`D-072`).
 * - Native `<dialog>`, Pointer Events pan capture, zoom `1.0x-3.0x`, Square+Circle / Round / Widescreen switcher
 * - Zero non-`--*` inline styles; canvas image cache scoped to WeakMap / bounded Map
 */

import { focusSafe, html, live, nothing, repeat, type TemplateResult } from "../../lib/lit.js";
import { isPhotoUploaded, registerPhotoImageEvictor } from "../../state/photo-ops.js";
import type { StudioStore } from "../../state/store.js";
import type { CropPreviewAspect, PhotoCrop } from "../../types.js";
import {
  applyCanvasPanDelta,
  computeCropSourceRect,
  cropPreviewCanvasSize,
  DEFAULT_PHOTO_CROP,
  normalizePhotoCrop,
} from "../../utils/crop-math.js";
import { fmtNumber } from "../../utils/format.js";
import {
  createDialogBackdropHandlers,
  handleRadioGroupArrowKey,
  isImeSafeEnter,
} from "../controls/aria-helpers.js";

export const MAX_PREVIEW_EDGE_PX = 1024;
const MAX_CACHED_CROP_IMAGES = 16;

type DrawablePhotoPreview = ImageBitmap | HTMLCanvasElement | HTMLImageElement;

export interface CachedPhotoPreview {
  source: DrawablePhotoPreview | null;
  naturalWidth: number;
  naturalHeight: number;
  previewWidth: number;
  previewHeight: number;
  loadingImg: HTMLImageElement | null;
  listeners: Set<() => void>;
  disposed: boolean;
}

const loadedImageCache = new Map<string, CachedPhotoPreview>();
const lastCanvasPaintSig = new WeakMap<HTMLCanvasElement, string>();
const pendingCropRafs = new Map<
  StudioStore,
  { rafId: number; activeOnly: boolean; root: ShadowRoot }
>();

export function computeBoundedPreviewDims(
  naturalWidth: number,
  naturalHeight: number,
  maxEdge = MAX_PREVIEW_EDGE_PX,
): { width: number; height: number; downscaled: boolean } {
  if (naturalWidth <= 0 || naturalHeight <= 0) {
    return { width: 0, height: 0, downscaled: false };
  }
  const longest = Math.max(naturalWidth, naturalHeight);
  if (longest <= maxEdge) {
    return { width: naturalWidth, height: naturalHeight, downscaled: false };
  }
  const scale = maxEdge / longest;
  return {
    width: Math.max(1, Math.round(naturalWidth * scale)),
    height: Math.max(1, Math.round(naturalHeight * scale)),
    downscaled: true,
  };
}

function releaseHtmlImage(img: HTMLImageElement): void {
  img.onload = null;
  img.onerror = null;
  img.src = "";
}

function disposeCachedPreview(entry: CachedPhotoPreview): void {
  entry.disposed = true;
  entry.listeners.clear();
  if (entry.loadingImg) {
    releaseHtmlImage(entry.loadingImg);
    entry.loadingImg = null;
  }
  const src = entry.source;
  entry.source = null;
  if (!src) return;
  if (typeof (src as { close?: unknown }).close === "function") {
    try {
      (src as { close: () => void }).close();
    } catch {
      // Ignore bitmap close errors.
    }
    return;
  }
  if (typeof HTMLCanvasElement !== "undefined" && src instanceof HTMLCanvasElement) {
    src.width = 0;
    src.height = 0;
    return;
  }
  if ("src" in src) {
    releaseHtmlImage(src as HTMLImageElement);
  }
}

export function evictLoadedPhotoImage(url: string): void {
  if (!url) return;
  const entry = loadedImageCache.get(url);
  if (!entry) return;
  loadedImageCache.delete(url);
  disposeCachedPreview(entry);
}

export function clearLoadedPhotoImages(): void {
  for (const entry of loadedImageCache.values()) {
    disposeCachedPreview(entry);
  }
  loadedImageCache.clear();
  for (const pending of pendingCropRafs.values()) {
    if (typeof cancelAnimationFrame === "function") {
      cancelAnimationFrame(pending.rafId);
    }
  }
  pendingCropRafs.clear();
}

export function getLoadedPhotoImageCacheSize(): number {
  return loadedImageCache.size;
}

registerPhotoImageEvictor({
  evict: evictLoadedPhotoImage,
  clear: clearLoadedPhotoImages,
});

function notifyPreviewListeners(entry: CachedPhotoPreview): void {
  const callbacks = Array.from(entry.listeners);
  entry.listeners.clear();
  for (const cb of callbacks) {
    cb();
  }
}

function finalizeDownscaleFallback(
  url: string,
  entry: CachedPhotoPreview,
  img: HTMLImageElement,
  natW: number,
  natH: number,
  dstW: number,
  dstH: number,
): void {
  if (entry.disposed || loadedImageCache.get(url) !== entry) {
    releaseHtmlImage(img);
    entry.loadingImg = null;
    return;
  }
  if (typeof document !== "undefined") {
    const offscreen = document.createElement("canvas");
    offscreen.width = dstW;
    offscreen.height = dstH;
    const ctx = offscreen.getContext("2d");
    if (ctx) {
      ctx.drawImage(img, 0, 0, dstW, dstH);
      releaseHtmlImage(img);
      entry.loadingImg = null;
      entry.source = offscreen;
      entry.naturalWidth = natW;
      entry.naturalHeight = natH;
      entry.previewWidth = dstW;
      entry.previewHeight = dstH;
      notifyPreviewListeners(entry);
      return;
    }
  }
  // Headless / no-2d-context fallback: keep loaded image element bounded by eviction.
  entry.loadingImg = null;
  entry.source = img;
  entry.naturalWidth = natW;
  entry.naturalHeight = natH;
  entry.previewWidth = natW;
  entry.previewHeight = natH;
  notifyPreviewListeners(entry);
}

export function getOrLoadPhotoPreview(
  url: string,
  onLoad: () => void,
): CachedPhotoPreview | null {
  if (!url || typeof Image === "undefined") return null;
  const existing = loadedImageCache.get(url);
  if (existing) {
    if (existing.source && existing.previewWidth > 0 && existing.previewHeight > 0) {
      return existing;
    }
    if (!existing.disposed) {
      existing.listeners.add(onLoad);
    }
    return null;
  }
  if (loadedImageCache.size >= MAX_CACHED_CROP_IMAGES) {
    const firstKey = loadedImageCache.keys().next().value;
    if (firstKey) {
      evictLoadedPhotoImage(firstKey);
    }
  }
  const entry: CachedPhotoPreview = {
    source: null,
    naturalWidth: 0,
    naturalHeight: 0,
    previewWidth: 0,
    previewHeight: 0,
    loadingImg: null,
    listeners: new Set([onLoad]),
    disposed: false,
  };
  loadedImageCache.set(url, entry);

  const img = new Image();
  img.crossOrigin = "anonymous";
  img.decoding = "async";
  entry.loadingImg = img;

  let handled = false;
  const handleLoaded = (): void => {
    if (handled) return;
    handled = true;
    img.onload = null;
    if (entry.disposed || loadedImageCache.get(url) !== entry) {
      releaseHtmlImage(img);
      entry.loadingImg = null;
      return;
    }
    const natW = img.naturalWidth;
    const natH = img.naturalHeight;
    if (natW <= 0 || natH <= 0) {
      releaseHtmlImage(img);
      entry.loadingImg = null;
      return;
    }
    const dims = computeBoundedPreviewDims(natW, natH, MAX_PREVIEW_EDGE_PX);
    if (!dims.downscaled) {
      entry.loadingImg = null;
      entry.source = img;
      entry.naturalWidth = natW;
      entry.naturalHeight = natH;
      entry.previewWidth = natW;
      entry.previewHeight = natH;
      notifyPreviewListeners(entry);
      return;
    }

    if (typeof createImageBitmap === "function") {
      void createImageBitmap(img, {
        resizeWidth: dims.width,
        resizeHeight: dims.height,
        resizeQuality: "medium",
      })
        .then((bitmap) => {
          releaseHtmlImage(img);
          entry.loadingImg = null;
          if (entry.disposed || loadedImageCache.get(url) !== entry) {
            try {
              bitmap.close?.();
            } catch {
              // Ignore bitmap close errors.
            }
            return;
          }
          entry.source = bitmap;
          entry.naturalWidth = natW;
          entry.naturalHeight = natH;
          entry.previewWidth = bitmap.width || dims.width;
          entry.previewHeight = bitmap.height || dims.height;
          notifyPreviewListeners(entry);
        })
        .catch(() => {
          finalizeDownscaleFallback(url, entry, img, natW, natH, dims.width, dims.height);
        });
      return;
    }

    finalizeDownscaleFallback(url, entry, img, natW, natH, dims.width, dims.height);
  };

  img.onload = handleLoaded;
  img.onerror = () => {
    if (loadedImageCache.get(url) === entry) {
      evictLoadedPhotoImage(url);
    } else {
      releaseHtmlImage(img);
    }
  };
  img.src = url;
  if (img.complete && img.naturalWidth > 0) {
    handleLoaded();
  }
  return entry.source && entry.previewWidth > 0 ? entry : null;
}

function paintPreviewCropCanvas(
  canvas: HTMLCanvasElement,
  url: string,
  preview: CachedPhotoPreview | null,
  crop: PhotoCrop,
  aspect: CropPreviewAspect,
  showGuides: boolean,
): boolean {
  const w = canvas.width;
  const h = canvas.height;
  const sig = `${url}|${preview?.previewWidth ?? 0}x${preview?.previewHeight ?? 0}|${crop.x},${crop.y},${crop.zoom}|${aspect}|${showGuides ? 1 : 0}|${w}x${h}`;
  if (lastCanvasPaintSig.get(canvas) === sig) {
    return false;
  }
  const ctx = canvas.getContext("2d");
  if (!ctx) return false;
  lastCanvasPaintSig.set(canvas, sig);

  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#111111";
  ctx.fillRect(0, 0, w, h);

  if (preview?.source && preview.previewWidth > 0 && preview.previewHeight > 0) {
    const rect = computeCropSourceRect(preview.previewWidth, preview.previewHeight, w, h, crop);
    ctx.save();
    if (aspect === "round") {
      ctx.beginPath();
      ctx.arc(w / 2, h / 2, Math.min(w, h) / 2, 0, Math.PI * 2);
      ctx.clip();
    }
    ctx.drawImage(preview.source, rect.sx, rect.sy, rect.sw, rect.sh, 0, 0, w, h);
    ctx.restore();
  }

  if (!showGuides) return true;

  ctx.save();
  if (aspect === "square") {
    ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(w / 3, 0);
    ctx.lineTo(w / 3, h);
    ctx.moveTo((2 * w) / 3, 0);
    ctx.lineTo((2 * w) / 3, h);
    ctx.moveTo(0, h / 3);
    ctx.lineTo(w, h / 3);
    ctx.moveTo(0, (2 * h) / 3);
    ctx.lineTo(w, (2 * h) / 3);
    ctx.stroke();

    ctx.strokeStyle = "rgba(255, 255, 255, 0.65)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, Math.min(w, h) / 2 - 2, 0, Math.PI * 2);
    ctx.stroke();
  } else if (aspect === "round") {
    ctx.strokeStyle = "rgba(255, 255, 255, 0.72)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, Math.min(w, h) / 2 - 1, 0, Math.PI * 2);
    ctx.stroke();
  } else {
    ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(w / 3, 0);
    ctx.lineTo(w / 3, h);
    ctx.moveTo((2 * w) / 3, 0);
    ctx.lineTo((2 * w) / 3, h);
    ctx.moveTo(0, h / 3);
    ctx.lineTo(w, h / 3);
    ctx.moveTo(0, (2 * h) / 3);
    ctx.lineTo(w, (2 * h) / 3);
    ctx.stroke();
  }
  ctx.restore();
  return true;
}

const activeDragMap = new WeakMap<
  HTMLCanvasElement,
  { pointerId: number; lastX: number; lastY: number }
>();

function cancelCropPaintRaf(store: StudioStore): void {
  const pending = pendingCropRafs.get(store);
  if (!pending) return;
  pendingCropRafs.delete(store);
  if (typeof cancelAnimationFrame === "function") {
    cancelAnimationFrame(pending.rafId);
  }
}

function paintStudioCropCanvasesNow(
  renderRoot: ShadowRoot,
  store: StudioStore,
  activeOnly: boolean,
): void {
  // 1. Upload staging main crop canvas + filmstrip thumbs
  if (store.photoUploadModal.open && store.photoUploadModal.files.length > 0) {
    const modal = store.photoUploadModal;
    const active = modal.files[modal.activeIndex] || modal.files[0];
    const onImageReady = (): void => {
      if (store.photoUploadModal.open && store.host.isConnected) {
        scheduleCropCanvasPaint(renderRoot, store, false);
      }
    };
    const mainCanvas = renderRoot.getElementById(
      "latter-upload-crop-canvas",
    ) as HTMLCanvasElement | null;
    if (mainCanvas && active) {
      const preview = getOrLoadPhotoPreview(active.objectUrl, onImageReady);
      if (
        preview &&
        (active.width !== preview.naturalWidth || active.height !== preview.naturalHeight)
      ) {
        active.width = preview.naturalWidth;
        active.height = preview.naturalHeight;
      }
      paintPreviewCropCanvas(
        mainCanvas,
        active.objectUrl,
        preview,
        active.crop,
        modal.previewAspect,
        true,
      );
    }

    if (activeOnly && active) {
      const activeThumb = renderRoot.getElementById(
        `latter-upload-thumb-${active.id}`,
      ) as HTMLCanvasElement | null;
      if (activeThumb) {
        const preview = getOrLoadPhotoPreview(active.objectUrl, onImageReady);
        paintPreviewCropCanvas(activeThumb, active.objectUrl, preview, active.crop, "square", false);
      }
    } else {
      for (let i = 0; i < modal.files.length; i += 1) {
        const staged = modal.files[i];
        if (!staged) continue;
        const thumbCanvas = renderRoot.getElementById(
          `latter-upload-thumb-${staged.id}`,
        ) as HTMLCanvasElement | null;
        if (!thumbCanvas) continue;
        const preview = getOrLoadPhotoPreview(staged.objectUrl, onImageReady);
        paintPreviewCropCanvas(thumbCanvas, staged.objectUrl, preview, staged.crop, "square", false);
      }
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
      const preview = getOrLoadPhotoPreview(srcUrl, () => {
        if (store.photoEditModal.open && store.host.isConnected) {
          scheduleCropCanvasPaint(renderRoot, store, true);
        }
      });
      paintPreviewCropCanvas(editCanvas, srcUrl, preview, modal.crop, modal.previewAspect, true);
    }
  }
}

function scheduleCropCanvasPaint(
  renderRoot: ShadowRoot,
  store: StudioStore,
  activeOnly: boolean,
): void {
  const existing = pendingCropRafs.get(store);
  if (existing) {
    existing.root = renderRoot;
    if (!activeOnly) existing.activeOnly = false;
    return;
  }
  if (typeof requestAnimationFrame !== "function") {
    paintStudioCropCanvasesNow(renderRoot, store, activeOnly);
    return;
  }
  const entry = {
    rafId: 0,
    activeOnly,
    root: renderRoot,
  };
  entry.rafId = requestAnimationFrame(() => {
    pendingCropRafs.delete(store);
    paintStudioCropCanvasesNow(entry.root, store, entry.activeOnly);
  });
  pendingCropRafs.set(store, entry);
}

export function syncPhotoCropCanvases(renderRoot: ShadowRoot, store: StudioStore): void {
  const hasOpenCropper =
    (store.photoUploadModal.open && store.photoUploadModal.files.length > 0) ||
    (store.photoEditModal.open && Boolean(store.photoEditModal.photoId));
  if (!hasOpenCropper) {
    cancelCropPaintRaf(store);
    return;
  }
  scheduleCropCanvasPaint(renderRoot, store, false);
}

function resolveElementShadowRoot(el: Element | null): ShadowRoot | null {
  const root = el?.getRootNode?.();
  return root && typeof (root as ShadowRoot).getElementById === "function"
    ? (root as ShadowRoot)
    : null;
}

function attachCropPointerHandlers(
  getCrop: () => PhotoCrop,
  getSourceDims: () => { width: number; height: number },
  onCropMove: (next: PhotoCrop, canvas: HTMLCanvasElement) => void,
  onCropCommit: (canvas: HTMLCanvasElement) => void,
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
      if (dx === 0 && dy === 0) return;
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
      onCropMove(next, canvas);
    },
    onPointerUp: (ev: Event) => {
      const pev = ev as PointerEvent;
      const canvas = pev.currentTarget as HTMLCanvasElement;
      const wasDragging = activeDragMap.delete(canvas);
      canvas.classList.remove("dragging");
      if (canvas.hasPointerCapture?.(pev.pointerId)) {
        canvas.releasePointerCapture(pev.pointerId);
      }
      if (wasDragging) {
        onCropCommit(canvas);
      }
    },
  };
}

function handleCropCanvasKeyDown(
  ev: KeyboardEvent,
  getCrop: () => PhotoCrop,
  getDims: () => { width: number; height: number },
  updateLive: (nextCrop: PhotoCrop, sourceEl: Element) => void,
  commit: (sourceEl: Element) => void,
  announceReset: () => void,
  announcePan: () => void,
  disabled: boolean,
): void {
  if (disabled) return;
  const canvas = ev.currentTarget as HTMLCanvasElement;
  if (ev.key === "Home" || ev.key === "0") {
    ev.preventDefault();
    const cur = getCrop();
    updateLive({ ...DEFAULT_PHOTO_CROP, zoom: cur.zoom }, canvas);
    commit(canvas);
    announceReset();
    return;
  }
  const step = ev.shiftKey ? 24 : 8;
  let dx = 0;
  let dy = 0;
  if (ev.key === "ArrowLeft") dx = step;
  else if (ev.key === "ArrowRight") dx = -step;
  else if (ev.key === "ArrowUp") dy = step;
  else if (ev.key === "ArrowDown") dy = -step;
  else return;
  ev.preventDefault();
  const cur = getCrop();
  const dims = getDims();
  const next = applyCanvasPanDelta(
    cur,
    dx,
    dy,
    dims.width,
    dims.height,
    canvas.width,
    canvas.height,
  );
  updateLive(next, canvas);
  commit(canvas);
  announcePan();
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
    @keydown=${(ev: KeyboardEvent) =>
      handleRadioGroupArrowKey(
        ev,
        options.map((o) => o.id),
        aspect,
        onSelect,
      )}
    class="segmented"
  >
    ${options.map(
      (opt) => html`<button
        type="button"
        role="radio"
        aria-checked=${aspect === opt.id ? "true" : "false"}
        tabindex=${aspect === opt.id ? "0" : "-1"}
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
  const uploadBusy = Boolean(modal.uploading || modal.creatingCollection);
  const close = (): void => {
    if (
      store.photoUploadModal.open &&
      !store.photoUploadModal.uploading &&
      !store.photoUploadModal.creatingCollection
    ) {
      store.entity.closePhotoUploadModal();
    }
  };
  const backdrop = createDialogBackdropHandlers(close, () =>
    Boolean(store.photoUploadModal.uploading || store.photoUploadModal.creatingCollection),
  );

  if (!modal.open) {
    return html`<dialog
      id="latter-photo-upload-modal"
      aria-labelledby="latter-photo-upload-title"
      closedby=${uploadBusy ? "none" : "any"}
      @cancel=${(ev: Event) => {
        if (uploadBusy) ev.preventDefault();
        else close();
      }}
      @close=${close}
      @pointerdown=${backdrop.onPointerDown}
      @click=${backdrop.onClick}
      class="studio-dialog photo-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  const collections = store.state?.photo_collections || [];
  const active = modal.files[modal.activeIndex] || modal.files[0] || null;
  const canvasSize = cropPreviewCanvasSize(modal.previewAspect);

  const updateActiveItem = (patch: Partial<{ name: string; crop: PhotoCrop }>): void => {
    if (!active) return;
    const nextFiles = store.photoUploadModal.files.map((item, idx) =>
      idx === store.photoUploadModal.activeIndex ? { ...item, ...patch } : item,
    );
    store.photoUploadModal = { ...store.photoUploadModal, files: nextFiles };
    store.host.requestUpdate();
  };

  const updateActiveCropLive = (nextCrop: PhotoCrop, sourceEl: Element | null): void => {
    const curFiles = store.photoUploadModal.files;
    const curActive = curFiles[store.photoUploadModal.activeIndex] || curFiles[0];
    if (!curActive) return;
    curActive.crop = nextCrop;
    const root = resolveElementShadowRoot(sourceEl);
    if (root) {
      scheduleCropCanvasPaint(root, store, true);
    } else {
      updateActiveItem({ crop: nextCrop });
    }
  };

  const commitActiveCrop = (sourceEl: Element | null): void => {
    const curFiles = store.photoUploadModal.files;
    const curActive = curFiles[store.photoUploadModal.activeIndex] || curFiles[0];
    if (!curActive) return;
    const root = resolveElementShadowRoot(sourceEl);
    if (root) {
      cancelCropPaintRaf(store);
      paintStudioCropCanvasesNow(root, store, true);
    }
    updateActiveItem({ crop: { ...curActive.crop } });
  };

  const ptr = attachCropPointerHandlers(
    () => {
      const curActive =
        store.photoUploadModal.files[store.photoUploadModal.activeIndex] ||
        store.photoUploadModal.files[0];
      return curActive?.crop || { ...DEFAULT_PHOTO_CROP };
    },
    () => {
      const curActive =
        store.photoUploadModal.files[store.photoUploadModal.activeIndex] ||
        store.photoUploadModal.files[0];
      const cached = curActive?.objectUrl ? loadedImageCache.get(curActive.objectUrl) : null;
      return {
        width: cached?.naturalWidth || curActive?.width || canvasSize.width,
        height: cached?.naturalHeight || curActive?.height || canvasSize.height,
      };
    },
    (nextCrop, canvas) => updateActiveCropLive(nextCrop, canvas),
    (canvas) => commitActiveCrop(canvas),
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
    closedby=${uploadBusy ? "none" : "any"}
    @cancel=${(ev: Event) => {
      if (uploadBusy) ev.preventDefault();
      else close();
    }}
    @close=${close}
    @pointerdown=${backdrop.onPointerDown}
    @click=${backdrop.onClick}
    class="studio-dialog photo-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h1 id="latter-photo-upload-title" class="dialog-title">
          ${store.t("photo_upload.title")}
        </h1>
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
        ? html`<button
            type="button"
            id="photo-upload-dropzone"
            @click=${onTriggerFilePicker}
            @dragover=${onDragOver}
            @dragleave=${onDragLeave}
            @drop=${onDrop}
            class="crop-dropzone ${modal.draggingFiles ? "dragging" : ""}"
          >
            <strong>${store.t("photo_upload.dropzone_title")}</strong>
            <span class="row-description">${store.t("photo_upload.dropzone_hint")}</span>
            <span class="btn btn-primary btn-compact">${store.t("photo_upload.choose_files")}</span>
          </button>`
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
              tabindex="0"
              aria-label=${store.t("photo_edit.crop_canvas_aria")}
              width=${String(canvasSize.width)}
              height=${String(canvasSize.height)}
              @pointerdown=${ptr.onPointerDown}
              @pointermove=${ptr.onPointerMove}
              @pointerup=${ptr.onPointerUp}
              @pointercancel=${ptr.onPointerUp}
              @keydown=${(ev: KeyboardEvent) =>
                handleCropCanvasKeyDown(
                  ev,
                  () => {
                    const curActive =
                      store.photoUploadModal.files[store.photoUploadModal.activeIndex] ||
                      store.photoUploadModal.files[0];
                    return curActive?.crop || { ...DEFAULT_PHOTO_CROP };
                  },
                  () => {
                    const curActive =
                      store.photoUploadModal.files[store.photoUploadModal.activeIndex] ||
                      store.photoUploadModal.files[0];
                    const cached = curActive?.objectUrl
                      ? loadedImageCache.get(curActive.objectUrl)
                      : null;
                    return {
                      width: cached?.naturalWidth || curActive?.width || canvasSize.width,
                      height: cached?.naturalHeight || curActive?.height || canvasSize.height,
                    };
                  },
                  updateActiveCropLive,
                  commitActiveCrop,
                  () => store.announcePolite(store.t("photo_edit.crop_centered")),
                  () => store.announcePolite(store.t("photo_edit.crop_panned")),
                  modal.uploading,
                )}
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
                  aria-valuetext=${`${(active?.crop.zoom ?? 1).toFixed(2)}×`}
                  ?disabled=${modal.uploading}
                  .value=${live(String(active?.crop.zoom ?? 1))}
                  @input=${(ev: Event) => {
                    const inputEl = ev.currentTarget as HTMLInputElement;
                    const z = Number(inputEl.value) || 1;
                    const curActive =
                      store.photoUploadModal.files[store.photoUploadModal.activeIndex] ||
                      store.photoUploadModal.files[0];
                    const nextCrop = normalizePhotoCrop({
                      ...(curActive?.crop || DEFAULT_PHOTO_CROP),
                      zoom: z,
                    });
                    const readout = inputEl.parentElement?.querySelector(".kv-value");
                    if (readout) {
                      readout.textContent = `${nextCrop.zoom.toFixed(2)}×`;
                    }
                    updateActiveCropLive(nextCrop, inputEl);
                  }}
                  @change=${(ev: Event) => commitActiveCrop(ev.currentTarget as Element)}
                />
                <span
                  class="kv-value"
                  .textContent=${live(`${(active?.crop.zoom ?? 1).toFixed(2)}×`)}
                ></span>
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
                ${repeat(
                  modal.files,
                  (item) => item.id,
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
                      class="crop-filmstrip-btn"
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
                .value=${live(modal.collectionId)}
                @change=${(ev: Event) => {
                  store.photoUploadModal = {
                    ...store.photoUploadModal,
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
                      if (isImeSafeEnter(ev)) {
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
                <div class="photo-upload-status">
                  <span>
                    ${store.t("photo_upload.uploading_progress", {
                      current: fmtNumber(modal.currentIndex, store.hass, 0),
                      total: fmtNumber(modal.files.length, store.hass, 0),
                      percent: fmtNumber(modal.currentPercent, store.hass, 0),
                    })}
                  </span>
                </div>
                <progress
                  aria-label=${store.t("wp_gallery.upload_progress_aria")}
                  max="100"
                  value=${String(modal.currentPercent)}
                  class="upload-progress"
                ></progress>
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
  const close = (): void => {
    if (store.photoEditModal.open && !store.photoEditModal.busy) {
      store.entity.closePhotoEditModal();
    }
  };
  const backdrop = createDialogBackdropHandlers(close, () => store.photoEditModal.busy);

  const onCancel = (ev: Event): void => {
    if (modal.busy) {
      ev.preventDefault();
    } else {
      close();
    }
  };

  if (!modal.open || !modal.photoId) {
    return html`<dialog
      id="latter-photo-edit-modal"
      aria-labelledby="latter-photo-edit-title"
      closedby=${modal.busy ? "none" : "any"}
      @cancel=${onCancel}
      @close=${close}
      @pointerdown=${backdrop.onPointerDown}
      @click=${backdrop.onClick}
      class="studio-dialog photo-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  const photo = (store.state?.system_wallpapers || []).find((p) => p.id === modal.photoId);
  const uploaded = photo ? isPhotoUploaded(photo) : false;
  const collections = store.state?.photo_collections || [];
  const canvasSize = cropPreviewCanvasSize(modal.previewAspect);

  const updateEditCropLive = (nextCrop: PhotoCrop, sourceEl: Element | null): void => {
    store.photoEditModal = { ...store.photoEditModal, crop: nextCrop };
    const root = resolveElementShadowRoot(sourceEl);
    if (root) {
      scheduleCropCanvasPaint(root, store, true);
    } else {
      store.host.requestUpdate();
    }
  };

  const commitEditCrop = (sourceEl: Element | null): void => {
    const root = resolveElementShadowRoot(sourceEl);
    if (root) {
      cancelCropPaintRaf(store);
      paintStudioCropCanvasesNow(root, store, true);
    }
    store.host.requestUpdate();
  };

  const ptr = attachCropPointerHandlers(
    () => store.photoEditModal.crop,
    () => {
      const srcUrl = photo?.orig_url || photo?.thumb_url || photo?.preview_url || "";
      const cached = srcUrl ? loadedImageCache.get(srcUrl) : null;
      return {
        width: cached?.naturalWidth || photo?.width || canvasSize.width,
        height: cached?.naturalHeight || photo?.height || canvasSize.height,
      };
    },
    (nextCrop, canvas) => updateEditCropLive(nextCrop, canvas),
    (canvas) => commitEditCrop(canvas),
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
    closedby=${modal.busy ? "none" : "any"}
    @cancel=${onCancel}
    @close=${close}
    @pointerdown=${backdrop.onPointerDown}
    @click=${backdrop.onClick}
    class="studio-dialog photo-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h1 id="latter-photo-edit-title" class="dialog-title">
          ${store.t("photo_edit.title")}
        </h1>
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
                tabindex="0"
                aria-label=${store.t("photo_edit.crop_canvas_aria")}
                width=${String(canvasSize.width)}
                height=${String(canvasSize.height)}
                @pointerdown=${ptr.onPointerDown}
                @pointermove=${ptr.onPointerMove}
                @pointerup=${ptr.onPointerUp}
                @pointercancel=${ptr.onPointerUp}
                @keydown=${(ev: KeyboardEvent) =>
                  handleCropCanvasKeyDown(
                    ev,
                    () => store.photoEditModal.crop,
                    () => {
                      const srcUrl = photo?.orig_url || photo?.thumb_url || photo?.preview_url || "";
                      const cached = srcUrl ? loadedImageCache.get(srcUrl) : null;
                      return {
                        width: cached?.naturalWidth || photo?.width || canvasSize.width,
                        height: cached?.naturalHeight || photo?.height || canvasSize.height,
                      };
                    },
                    updateEditCropLive,
                    commitEditCrop,
                    () => store.announcePolite(store.t("photo_edit.crop_centered")),
                    () => store.announcePolite(store.t("photo_edit.crop_panned")),
                    modal.busy || !uploaded,
                  )}
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
                    aria-valuetext=${`${modal.crop.zoom.toFixed(2)}×`}
                    ?disabled=${modal.busy}
                    .value=${live(String(modal.crop.zoom))}
                    @input=${(ev: Event) => {
                      const inputEl = ev.currentTarget as HTMLInputElement;
                      const z = Number(inputEl.value) || 1;
                      const nextCrop = normalizePhotoCrop({ ...store.photoEditModal.crop, zoom: z });
                      const readout = inputEl.parentElement?.querySelector(".kv-value");
                      if (readout) {
                        readout.textContent = `${nextCrop.zoom.toFixed(2)}×`;
                      }
                      updateEditCropLive(nextCrop, inputEl);
                    }}
                    @change=${(ev: Event) => commitEditCrop(ev.currentTarget as Element)}
                  />
                  <span
                    class="kv-value"
                    .textContent=${live(`${modal.crop.zoom.toFixed(2)}×`)}
                  ></span>
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
