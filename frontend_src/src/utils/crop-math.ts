/**
 * Pure non-destructive focal-point crop math shared by Photo Upload, Photo Editor,
 * and preview thumbnails (`D-072`). Mirrors `wallpapers.py:crop_and_fit_image()`.
 */

export interface PhotoCrop {
  x: number;
  y: number;
  zoom: number;
}

export interface CropSourceRect {
  sx: number;
  sy: number;
  sw: number;
  sh: number;
}

export type CropPreviewAspect = "square" | "round" | "widescreen";

export const DEFAULT_PHOTO_CROP: Readonly<PhotoCrop> = {
  x: 0.5,
  y: 0.5,
  zoom: 1,
};

export function clampNum(val: number, min: number, max: number): number {
  if (!Number.isFinite(val)) return min;
  if (val < min) return min;
  if (val > max) return max;
  return val;
}

export function normalizePhotoCrop(raw?: Partial<PhotoCrop> | null): PhotoCrop {
  return {
    x: clampNum(Number(raw?.x ?? 0.5), 0, 1),
    y: clampNum(Number(raw?.y ?? 0.5), 0, 1),
    zoom: clampNum(Number(raw?.zoom ?? 1), 1, 3),
  };
}

/**
 * Computes the source rectangle `[sx, sy, sw, sh]` within `(srcW, srcH)` that
 * cover-fills `(dstW, dstH)` centered on `(crop.x, crop.y)` at `crop.zoom`,
 * clamped strictly inside the source bounds so zero black bars ever appear.
 */
export function computeCropSourceRect(
  srcW: number,
  srcH: number,
  dstW: number,
  dstH: number,
  crop: PhotoCrop,
): CropSourceRect {
  const safeSrcW = Math.max(1, srcW);
  const safeSrcH = Math.max(1, srcH);
  const safeDstW = Math.max(1, dstW);
  const safeDstH = Math.max(1, dstH);
  const zoom = clampNum(crop.zoom, 1, 3);

  const srcAspect = safeSrcW / safeSrcH;
  const dstAspect = safeDstW / safeDstH;

  let baseW: number;
  let baseH: number;
  if (srcAspect > dstAspect) {
    baseH = safeSrcH;
    baseW = safeSrcH * dstAspect;
  } else {
    baseW = safeSrcW;
    baseH = safeSrcW / dstAspect;
  }

  const sw = Math.min(safeSrcW, baseW / zoom);
  const sh = Math.min(safeSrcH, baseH / zoom);

  const cx = clampNum(crop.x, 0, 1) * safeSrcW;
  const cy = clampNum(crop.y, 0, 1) * safeSrcH;

  const sx = clampNum(cx - sw / 2, 0, Math.max(0, safeSrcW - sw));
  const sy = clampNum(cy - sh / 2, 0, Math.max(0, safeSrcH - sh));

  return { sx, sy, sw, sh };
}

/**
 * Applies a pointer drag delta `(dxPx, dyPx)` in canvas coordinates to the
 * normalized focal point `(crop.x, crop.y)`, clamping inside the reachable
 * pan window so dragging never accumulates dead-zone slack past image edges.
 */
export function applyCanvasPanDelta(
  crop: PhotoCrop,
  dxPx: number,
  dyPx: number,
  srcW: number,
  srcH: number,
  canvasW: number,
  canvasH: number,
): PhotoCrop {
  if (srcW <= 0 || srcH <= 0 || canvasW <= 0 || canvasH <= 0) {
    return normalizePhotoCrop(crop);
  }
  const rect = computeCropSourceRect(srcW, srcH, canvasW, canvasH, crop);
  const halfFracX = rect.sw / (2 * srcW);
  const halfFracY = rect.sh / (2 * srcH);

  const minX = Math.min(0.5, halfFracX);
  const maxX = Math.max(0.5, 1 - halfFracX);
  const minY = Math.min(0.5, halfFracY);
  const maxY = Math.max(0.5, 1 - halfFracY);

  const curCenterX = (rect.sx + rect.sw / 2) / srcW;
  const curCenterY = (rect.sy + rect.sh / 2) / srcH;

  const nextX = clampNum(curCenterX - (dxPx / canvasW) * (rect.sw / srcW), minX, maxX);
  const nextY = clampNum(curCenterY - (dyPx / canvasH) * (rect.sh / srcH), minY, maxY);

  return {
    x: Math.round(nextX * 1000) / 1000,
    y: Math.round(nextY * 1000) / 1000,
    zoom: clampNum(crop.zoom, 1, 3),
  };
}

/**
 * Returns canvas pixel dimensions for a crop preview aspect preset.
 */
export function cropPreviewCanvasSize(aspect: CropPreviewAspect): { width: number; height: number } {
  if (aspect === "widescreen") {
    return { width: 320, height: 180 };
  }
  return { width: 260, height: 260 };
}

/**
 * Paints an `HTMLImageElement` onto a `<canvas>` using `computeCropSourceRect`
 * plus subtle safe-zone guides matching square/round/widescreen Latter panels.
 */
export function paintCropCanvas(
  canvas: HTMLCanvasElement,
  img: HTMLImageElement | null,
  crop: PhotoCrop,
  aspect: CropPreviewAspect,
  options?: { showGuides?: boolean },
): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  ctx.fillStyle = "#111111";
  ctx.fillRect(0, 0, w, h);

  if (img && img.naturalWidth > 0 && img.naturalHeight > 0) {
    const rect = computeCropSourceRect(img.naturalWidth, img.naturalHeight, w, h, crop);
    ctx.save();
    if (aspect === "round") {
      ctx.beginPath();
      ctx.arc(w / 2, h / 2, Math.min(w, h) / 2, 0, Math.PI * 2);
      ctx.clip();
    }
    ctx.drawImage(img, rect.sx, rect.sy, rect.sw, rect.sh, 0, 0, w, h);
    ctx.restore();
  }

  if (options?.showGuides === false) return;

  ctx.save();
  if (aspect === "square") {
    // Subtle rule-of-thirds + inscribed circle safe-zone guide for round displays
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
}
