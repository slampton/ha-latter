/**
 * Shared WAI-ARIA description wiring, SVG icon helpers, select option renderer,
 * table sort header, & Device 12/24h time helper (`components/controls/aria-helpers.ts`).
 */

import {
  Directive,
  directive,
  html,
  live,
  noChange,
  nothing,
  PartType,
  type ElementPart,
  type PartInfo,
  type TemplateResult,
} from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import type { CatalogChoice } from "../../types.js";
import { defaultLocaleTimeFormat } from "../../utils/format.js";

export function isDeviceTime24h(store: StudioStore): boolean {
  if (store.currentScope !== "system") {
    const raw =
      store.entity.getPref("time_format")?.value ??
      store.state?.config?.time_format;
    const trimmed = raw !== undefined && raw !== null ? String(raw).trim() : "";
    if (trimmed) {
      return trimmed.startsWith("24");
    }
  }
  return defaultLocaleTimeFormat(store.hass).startsWith("24");
}

function slugifyToken(raw: string): string {
  let hash = 0x811c9dc5;
  for (let i = 0; i < raw.length; i += 1) {
    hash ^= raw.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  const clean = raw
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 28);
  return clean ? `${clean}-${hash.toString(36)}` : `z${hash.toString(36)}`;
}

export function resolveDescriptionId(opts: {
  descId?: string;
  forId?: string;
  id?: string;
  label?: string;
  hasDescription: boolean;
}): string {
  if (!opts.hasDescription) return "";
  if (opts.descId) return opts.descId;
  if (opts.forId) return `${opts.forId}-desc`;
  if (opts.id) return `${opts.id}-desc`;
  return `row-desc-${slugifyToken(opts.label || "setting")}`;
}

class AutoDescribeDirective extends Directive {
  private wiredContainer: Element | null = null;
  private wiredTarget: Element | null = null;
  private wiredDescId = "";
  private microtaskPending = false;

  constructor(partInfo: PartInfo) {
    super(partInfo);
    if (partInfo.type !== PartType.ELEMENT) {
      throw new Error("autoWireDescribedBy() must be used as an element directive");
    }
  }

  render(_descId: string): typeof nothing {
    return nothing;
  }

  override update(part: ElementPart, [descId]: [string]): typeof noChange {
    const container = part.element;
    if (!descId || !container) {
      this.wiredContainer = null;
      this.wiredTarget = null;
      this.wiredDescId = "";
      return noChange;
    }

    // Fast path: once wired on a connected container/control with unchanged ID, skip DOM query & microtask.
    if (
      this.wiredContainer === container &&
      this.wiredDescId === descId &&
      this.wiredTarget &&
      this.wiredTarget.isConnected &&
      container.contains(this.wiredTarget) &&
      this.wiredTarget.hasAttribute("aria-describedby")
    ) {
      return noChange;
    }

    const apply = (): boolean => {
      const target = container.querySelector(
        "input:not([type='hidden']), select, textarea, [role='combobox']",
      );
      if (!target) return false;
      const existingAttr = target.getAttribute("aria-describedby");
      if (!existingAttr) {
        target.setAttribute("aria-describedby", descId);
      } else if (
        this.wiredTarget === target &&
        this.wiredDescId &&
        existingAttr === this.wiredDescId &&
        this.wiredDescId !== descId
      ) {
        target.setAttribute("aria-describedby", descId);
      }
      this.wiredContainer = container;
      this.wiredTarget = target;
      this.wiredDescId = descId;
      return true;
    };

    if (apply()) {
      return noChange;
    }

    if (!this.microtaskPending) {
      this.microtaskPending = true;
      queueMicrotask(() => {
        this.microtaskPending = false;
        if (container.isConnected) {
          apply();
        }
      });
    }
    return noChange;
  }
}

export const autoWireDescribedBy = directive(AutoDescribeDirective);

export function renderSelectOptions(
  choices: readonly CatalogChoice[] | undefined,
  selectedId: string | null | undefined,
  emptyOptionLabel = "None",
): TemplateResult[] {
  const cur = String(selectedId || "");
  const list = choices || [];
  const hasSelected = !cur || list.some((c) => c.id === cur);
  const out: TemplateResult[] = [
    html`<option value="" .selected=${live(cur === "")}>${emptyOptionLabel}</option>`,
  ];
  if (cur && !hasSelected) {
    out.push(html`<option value=${cur} .selected=${live(true)}>${cur} (missing)</option>`);
  }
  for (const item of list) {
    out.push(
      html`<option value=${item.id} .selected=${live(item.id === cur)}>${item.name || item.id}</option>`,
    );
  }
  return out;
}

export function renderSvgIcon(pathD: string): TemplateResult {
  return html`<svg viewBox="0 0 24 24" aria-hidden="true"><path d=${pathD}></path></svg>`;
}

export function renderTrashIconButton(ariaLabel: string, onRemove: () => void): TemplateResult {
  return html`<button
    type="button"
    aria-label=${ariaLabel}
    @click=${onRemove}
    class="btn-icon danger"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 3v1H4v2h1v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6h1V4h-5V3H9m0 5h2v9H9V8m4 0h2v9h-2V8Z" />
    </svg>
  </button>`;
}

export function isImeSafeEnter(ev: KeyboardEvent): boolean {
  return ev.key === "Enter" && !ev.isComposing && ev.keyCode !== 229;
}

export function handleRadioGroupArrowKey<T extends string>(
  ev: KeyboardEvent,
  values: readonly T[],
  current: T,
  onSelect: (next: T) => void,
  focusSelector?: (next: T) => string,
): void {
  if (
    ev.key !== "ArrowLeft" &&
    ev.key !== "ArrowRight" &&
    ev.key !== "ArrowUp" &&
    ev.key !== "ArrowDown" &&
    ev.key !== "Home" &&
    ev.key !== "End"
  ) {
    return;
  }
  if (values.length === 0) return;
  ev.preventDefault();

  const curTarget = ev.currentTarget as HTMLElement | null;
  const isRtl =
    (ev.key === "ArrowLeft" || ev.key === "ArrowRight") &&
    curTarget &&
    typeof getComputedStyle === "function" &&
    getComputedStyle(curTarget).direction === "rtl";

  const curIdx = Math.max(0, values.indexOf(current));
  let nextIdx = curIdx;
  if (ev.key === "Home") {
    nextIdx = 0;
  } else if (ev.key === "End") {
    nextIdx = values.length - 1;
  } else {
    const moveBack =
      ev.key === "ArrowUp" ||
      (!isRtl && ev.key === "ArrowLeft") ||
      (isRtl && ev.key === "ArrowRight");
    nextIdx = moveBack
      ? (curIdx - 1 + values.length) % values.length
      : (curIdx + 1) % values.length;
  }

  const nextVal = values[nextIdx];
  if (nextVal === undefined) return;
  onSelect(nextVal);
  const groupEl = curTarget?.closest('[role="radiogroup"]') ?? curTarget?.parentElement;
  if (!groupEl) return;
  const selector = focusSelector ? focusSelector(nextVal) : "";
  requestAnimationFrame(() => {
    const nextBtn = (
      selector
        ? groupEl.querySelector(selector)
        : groupEl.querySelectorAll<HTMLElement>('[role="radio"]')[nextIdx]
    ) as HTMLElement | null;
    nextBtn?.focus();
  });
}

const dialogPointerDownOutside = new WeakMap<HTMLDialogElement, boolean>();

function isPointOutsideDialog(dlg: HTMLDialogElement, x: number, y: number): boolean {
  const rect = dlg.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) return false;
  return x < rect.left || x > rect.right || y < rect.top || y > rect.bottom;
}

export function createDialogBackdropHandlers(
  onClose: () => void,
  isBusy?: () => boolean,
): {
  onPointerDown: (ev: Event) => void;
  onClick: (ev: Event) => void;
} {
  return {
    onPointerDown: (ev: Event) => {
      const dlg = ev.currentTarget as HTMLDialogElement | null;
      const pev = ev as PointerEvent;
      if (!dlg) return;
      dialogPointerDownOutside.set(
        dlg,
        ev.target === dlg && isPointOutsideDialog(dlg, pev.clientX, pev.clientY),
      );
    },
    onClick: (ev: Event) => {
      const dlg = ev.currentTarget as HTMLDialogElement | null;
      if (!dlg || isBusy?.()) return;
      const mev = ev as MouseEvent;
      const startedOutside = dialogPointerDownOutside.has(dlg)
        ? dialogPointerDownOutside.get(dlg) === true
        : true;
      dialogPointerDownOutside.delete(dlg);
      if (
        startedOutside &&
        ev.target === dlg &&
        isPointOutsideDialog(dlg, mev.clientX, mev.clientY)
      ) {
        onClose();
      }
    },
  };
}

export function renderExternalLinkHint(srLabel: string): TemplateResult {
  return html`<svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      class="external-link-icon"
    >
      <path d="M14,3V5H17.59L7.76,14.83L9.17,16.24L19,6.41V10H21V3M19,19H5V5H12V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V12H19V19Z" />
    </svg><span class="sr-only"> (${srLabel})</span>`;
}

export function renderSortHeader(
  store: StudioStore,
  field: "title" | "model" | "area" | "group" | "status",
  label: string,
): TemplateResult {
  const isActive = store.deviceSortField === field;
  const ariaSort = isActive ? (store.deviceSortAsc ? "ascending" : "descending") : nothing;
  const indicator = isActive ? (store.deviceSortAsc ? " ▲" : " ▼") : "";
  const onSort = (): void => {
    if (store.deviceSortField === field) {
      store.deviceSortAsc = !store.deviceSortAsc;
    } else {
      store.deviceSortField = field;
      store.deviceSortAsc = true;
    }
    store.host.requestUpdate();
  };
  return html`<th scope="col" aria-sort=${ariaSort}>
    <button type="button" @click=${onSort} class="sort-btn">${label}<span aria-hidden="true">${indicator}</span></button>
  </th>`;
}
