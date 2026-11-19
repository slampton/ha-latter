/**
 * Custom HSV Color Wheel Modal (`#latter-cw-modal`, `A-24`).
 * - Short-circuits closed `<dialog>` body
 * - Uses per-store `store.colorWheelModal.painted` flag (zero module-global state)
 * - Uses component-scoped pointer capture on `<canvas>` and `focusSafe` text inputs
 */

import { focusSafe, html, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import { hsvToHex, hsvToRgbJS, isValidHexColor } from "../../utils/format.js";

function paintHsvColorWheel(canvas: HTMLCanvasElement): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const size = canvas.width;
  const radius = size / 2;
  const img = ctx.createImageData(size, size);
  const data = img.data;
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const dx = x - radius;
      const dy = y - radius;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const idx = (y * size + x) * 4;
      if (dist > radius) {
        data[idx + 3] = 0;
        continue;
      }
      const sat = Math.min(1, dist / radius);
      const angle = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
      const [r, g, b] = hsvToRgbJS(angle, sat, 1);
      data[idx] = r;
      data[idx + 1] = g;
      data[idx + 2] = b;
      data[idx + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
}

function pickWheelHexFromEvent(canvas: HTMLCanvasElement, ev: PointerEvent): string | null {
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  const dx = ev.clientX - rect.left - cx;
  const dy = ev.clientY - rect.top - cy;
  const radius = Math.min(cx, cy);
  const sat = Math.min(1, Math.sqrt(dx * dx + dy * dy) / radius);
  const angle = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
  return hsvToHex(angle, sat, 1);
}

export function syncColorWheelCanvas(renderRoot: ShadowRoot, store: StudioStore): void {
  if (store.colorWheelModal.open && !store.colorWheelModal.painted) {
    const canvas = renderRoot.getElementById("latter-cw-canvas") as HTMLCanvasElement | null;
    if (canvas) {
      paintHsvColorWheel(canvas);
      store.colorWheelModal.painted = true;
    }
  } else if (!store.colorWheelModal.open && store.colorWheelModal.painted) {
    store.colorWheelModal.painted = false;
  }
}

export function renderColorWheelDialog(store: StudioStore): TemplateResult {
  const modal = store.colorWheelModal;

  const onBackdropClick = (ev: Event): void => {
    if (ev.target === ev.currentTarget) {
      store.tools.closeColorWheelModal();
    }
  };

  if (!modal.open) {
    return html`<dialog
      id="latter-cw-modal"
      aria-labelledby="latter-cw-title"
      @cancel=${() => store.tools.closeColorWheelModal()}
      @click=${onBackdropClick}
      class="studio-dialog"
    >
      ${nothing}
    </dialog>`;
  }

  const onCwPointerDown = (ev: Event): void => {
    const pev = ev as PointerEvent;
    const canvas = pev.currentTarget as HTMLCanvasElement;
    canvas.setPointerCapture?.(pev.pointerId);
    const hex = pickWheelHexFromEvent(canvas, pev);
    if (hex) {
      store.colorWheelModal = { ...store.colorWheelModal, hex };
      store.host.requestUpdate();
    }
  };

  const onCwPointerMove = (ev: Event): void => {
    const pev = ev as PointerEvent;
    if (pev.buttons === 0) return;
    const canvas = pev.currentTarget as HTMLCanvasElement;
    const hex = pickWheelHexFromEvent(canvas, pev);
    if (hex) {
      store.colorWheelModal = { ...store.colorWheelModal, hex };
      store.host.requestUpdate();
    }
  };

  const onCwPointerUp = (ev: Event): void => {
    const pev = ev as PointerEvent;
    const canvas = pev.currentTarget as HTMLCanvasElement;
    if (canvas.hasPointerCapture?.(pev.pointerId)) {
      canvas.releasePointerCapture(pev.pointerId);
    }
  };

  const onCwHexInput = (ev: Event): void => {
    const raw = (ev.currentTarget as HTMLInputElement).value;
    store.colorWheelModal = { ...store.colorWheelModal, hex: raw.toUpperCase() };
    store.host.requestUpdate();
  };

  const onCwNameInput = (ev: Event): void => {
    store.colorWheelModal = {
      ...store.colorWheelModal,
      name: (ev.currentTarget as HTMLInputElement).value,
    };
  };

  const cwValidHex = isValidHexColor(modal.hex) ? modal.hex : "#3898FF";

  return html`<dialog
    id="latter-cw-modal"
    aria-labelledby="latter-cw-title"
    @cancel=${() => store.tools.closeColorWheelModal()}
    @click=${onBackdropClick}
    class="studio-dialog"
  >
    <div class="dialog-body">
      <h3 id="latter-cw-title" class="dialog-title">${store.t("dialogs.cw_title")}</h3>
      <div class="color-wheel" aria-hidden="true">
        <canvas
          id="latter-cw-canvas"
          width="220"
          height="220"
          @pointerdown=${onCwPointerDown}
          @pointermove=${onCwPointerMove}
          @pointerup=${onCwPointerUp}
        ></canvas>
      </div>
      <div class="color-hex-row">
        <input
          type="color"
          id="latter-cw-native"
          aria-label=${store.t("dialogs.cw_color_aria")}
          .value=${cwValidHex}
          @input=${onCwHexInput}
        />
        <input
          type="text"
          id="latter-cw-hex"
          aria-label=${store.t("dialogs.cw_hex_aria")}
          placeholder="#RRGGBB"
          maxlength="7"
          .value=${focusSafe(modal.hex)}
          @input=${onCwHexInput}
        />
      </div>
      <div class="stacked-field">
        <label for="latter-cw-name">${store.t("dialogs.cw_name_label")}</label>
        <input
          type="text"
          id="latter-cw-name"
          placeholder=${store.t("dialogs.cw_name_placeholder")}
          .value=${focusSafe(modal.name)}
          @input=${onCwNameInput}
        />
      </div>
      <div class="dialog-actions">
        <button
          type="button"
          @click=${() => store.tools.closeColorWheelModal()}
          class="btn btn-secondary"
        >
          ${store.t("action.cancel")}
        </button>
        <button
          type="button"
          ?disabled=${modal.busy}
          @click=${() => void store.tools.saveColorWheelSelection()}
          class="btn btn-primary"
        >
          ${store.t("action.save_color")}
        </button>
      </div>
    </div>
  </dialog>`;
}
