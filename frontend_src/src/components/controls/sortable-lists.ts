/**
 * Pointer Drag-and-Drop (`≡`) + Focus-Preserving Keyboard Sortable Lists & Pills
 * (`components/controls/sortable-lists.ts`, `D-064`).
 */

import { t } from "../../i18n/index.js";
import { html, live, nothing, repeat, type TemplateResult } from "../../lib/lit.js";

interface ActiveDragSession {
  listId: string;
  pointerId: number;
  orientation: "vertical" | "horizontal";
  fromIndex: number;
  overIndex: number;
  insertAfter: boolean;
  onKeyCancel?: (ev: KeyboardEvent) => void;
}

let activeDrag: ActiveDragSession | null = null;
const SORTABLE_LIVE_STATUS = new Map<string, string>();

function detachDragKeyCancel(session: ActiveDragSession | null): void {
  if (session?.onKeyCancel && typeof globalThis.removeEventListener === "function") {
    globalThis.removeEventListener("keydown", session.onKeyCancel, true);
  }
}

function announceReorder(
  listId: string,
  itemLabel: string,
  toIndex: number,
  total: number,
  overlay: Readonly<Record<string, string>> | null | undefined,
  rootEl: Element | null,
): void {
  const msg = t(
    "common.reordered_status",
    { item: itemLabel, position: toIndex + 1, total },
    overlay,
  );
  SORTABLE_LIVE_STATUS.set(listId, msg);
  const liveEl = rootEl
    ?.closest("[data-sortable-list]")
    ?.querySelector("[data-sortable-live]") as HTMLElement | null;
  if (liveEl) {
    liveEl.textContent = msg;
  }
}

function clearDragDomClasses(listEl: Element | null): void {
  if (!listEl) return;
  for (const el of listEl.querySelectorAll(".dragging, .drag-over-before, .drag-over-after")) {
    el.classList.remove("dragging", "drag-over-before", "drag-over-after");
  }
}

function computeDropTargetIndex(
  fromIndex: number,
  overIndex: number,
  insertAfter: boolean,
  total: number,
): number {
  let target = insertAfter ? overIndex + 1 : overIndex;
  if (target > fromIndex) {
    target -= 1;
  }
  return Math.max(0, Math.min(total - 1, target));
}

function attachDragHandleHandlers(opts: {
  listId: string;
  orientation: "vertical" | "horizontal";
  idx: number;
  total: number;
  itemLabel: string;
  overlay?: Readonly<Record<string, string>> | null;
  onReorder: (fromIndex: number, toIndex: number) => void;
}) {
  const cancelSession = (handleEl: HTMLElement | null, pointerId: number): void => {
    if (!activeDrag || activeDrag.listId !== opts.listId || activeDrag.pointerId !== pointerId) {
      return;
    }
    const session = activeDrag;
    activeDrag = null;
    detachDragKeyCancel(session);
    const listEl = handleEl?.closest("[data-sortable-list]") as HTMLElement | null;
    if (handleEl) {
      try {
        if (typeof handleEl.hasPointerCapture === "function" && handleEl.hasPointerCapture(pointerId)) {
          handleEl.releasePointerCapture(pointerId);
        }
      } catch {
        // Ignore release errors.
      }
    }
    clearDragDomClasses(listEl);
  };

  const onPointerDown = (ev: PointerEvent): void => {
    if (ev.button !== 0 || opts.total <= 1) return;
    const handle = ev.currentTarget as HTMLElement;
    const rowEl = handle.closest("[data-sortable-index]") as HTMLElement | null;
    const listEl = handle.closest("[data-sortable-list]") as HTMLElement | null;
    if (!rowEl || !listEl) return;
    ev.preventDefault();
    if (activeDrag) {
      detachDragKeyCancel(activeDrag);
    }
    try {
      handle.setPointerCapture(ev.pointerId);
    } catch {
      // Headless test environments may omit setPointerCapture.
    }
    const onKeyCancel = (kev: KeyboardEvent): void => {
      if (kev.key === "Escape") {
        kev.preventDefault();
        kev.stopPropagation();
        cancelSession(handle, ev.pointerId);
      }
    };
    if (typeof globalThis.addEventListener === "function") {
      globalThis.addEventListener("keydown", onKeyCancel, true);
    }
    activeDrag = {
      listId: opts.listId,
      pointerId: ev.pointerId,
      orientation: opts.orientation,
      fromIndex: opts.idx,
      overIndex: opts.idx,
      insertAfter: false,
      onKeyCancel,
    };
    clearDragDomClasses(listEl);
    rowEl.classList.add("dragging");
  };

  const onPointerMove = (ev: PointerEvent): void => {
    if (!activeDrag || activeDrag.listId !== opts.listId || activeDrag.pointerId !== ev.pointerId) {
      return;
    }
    const handle = ev.currentTarget as HTMLElement;
    const listEl = handle.closest("[data-sortable-list]") as HTMLElement | null;
    if (!listEl) return;

    const rows = Array.from(listEl.querySelectorAll<HTMLElement>(":scope > [data-sortable-index]"));
    if (!rows.length) return;

    const isRtl =
      opts.orientation === "horizontal" &&
      typeof getComputedStyle === "function" &&
      getComputedStyle(listEl).direction === "rtl";

    let bestRow: HTMLElement | null = null;
    let bestIdx = activeDrag.fromIndex;
    let bestDist = Infinity;
    let bestAfter = false;

    for (const r of rows) {
      const rIdx = Number(r.dataset.sortableIndex);
      if (!Number.isFinite(rIdx)) continue;
      const rect = r.getBoundingClientRect();
      if (!rect.width && !rect.height) continue;
      if (opts.orientation === "vertical") {
        const midY = rect.top + rect.height / 2;
        const dist = Math.abs(ev.clientY - midY);
        if (dist < bestDist) {
          bestDist = dist;
          bestRow = r;
          bestIdx = rIdx;
          bestAfter = ev.clientY > midY;
        }
      } else {
        const midX = rect.left + rect.width / 2;
        const midY = rect.top + rect.height / 2;
        const dist = Math.hypot(ev.clientX - midX, (ev.clientY - midY) * 1.5);
        if (dist < bestDist) {
          bestDist = dist;
          bestRow = r;
          bestIdx = rIdx;
          bestAfter = isRtl ? ev.clientX < midX : ev.clientX > midX;
        }
      }
    }

    activeDrag.overIndex = bestIdx;
    activeDrag.insertAfter = bestAfter;
    for (const r of rows) {
      r.classList.remove("drag-over-before", "drag-over-after");
    }
    if (bestRow && bestIdx !== activeDrag.fromIndex) {
      bestRow.classList.add(bestAfter ? "drag-over-after" : "drag-over-before");
    }
  };

  const finishDrag = (ev: PointerEvent, cancelled: boolean): void => {
    if (!activeDrag || activeDrag.listId !== opts.listId || activeDrag.pointerId !== ev.pointerId) {
      return;
    }
    const session = activeDrag;
    activeDrag = null;
    detachDragKeyCancel(session);
    const handle = ev.currentTarget as HTMLElement;
    const listEl = handle.closest("[data-sortable-list]") as HTMLElement | null;
    try {
      if (typeof handle.hasPointerCapture === "function" && handle.hasPointerCapture(ev.pointerId)) {
        handle.releasePointerCapture(ev.pointerId);
      }
    } catch {
      // Ignore release errors.
    }
    clearDragDomClasses(listEl);
    if (cancelled) return;
    const toIndex = computeDropTargetIndex(
      session.fromIndex,
      session.overIndex,
      session.insertAfter,
      opts.total,
    );
    if (toIndex !== session.fromIndex) {
      opts.onReorder(session.fromIndex, toIndex);
      announceReorder(opts.listId, opts.itemLabel, toIndex, opts.total, opts.overlay, handle);
    }
  };

  return {
    onPointerDown,
    onPointerMove,
    onPointerUp: (ev: PointerEvent) => finishDrag(ev, false),
    onPointerCancel: (ev: PointerEvent) => finishDrag(ev, true),
  };
}

function triggerKeyboardMoveWithFocusRestore(opts: {
  btnEl: HTMLElement;
  listId: string;
  itemKey: string;
  itemLabel: string;
  preferredDir: "prev" | "next";
  fromIndex: number;
  toIndex: number;
  total: number;
  overlay?: Readonly<Record<string, string>> | null;
  onReorder: (fromIndex: number, toIndex: number) => void;
}): void {
  const root =
    typeof opts.btnEl.getRootNode === "function"
      ? (opts.btnEl.getRootNode() as Document | ShadowRoot)
      : document;
  opts.onReorder(opts.fromIndex, opts.toIndex);
  announceReorder(opts.listId, opts.itemLabel, opts.toIndex, opts.total, opts.overlay, opts.btnEl);

  requestAnimationFrame(() => {
    if (!root || typeof root.querySelector !== "function") return;
    const listEl = root.querySelector(`[data-sortable-list="${CSS.escape(opts.listId)}"]`);
    if (!listEl) return;
    const itemEl = listEl.querySelector(
      `[data-sortable-key="${CSS.escape(opts.itemKey)}"]`,
    ) as HTMLElement | null;
    if (!itemEl) return;
    const sameBtn = itemEl.querySelector(
      `button[data-move-dir="${opts.preferredDir}"]:not(:disabled)`,
    ) as HTMLButtonElement | null;
    if (sameBtn) {
      sameBtn.focus({ preventScroll: true });
      return;
    }
    const altBtn = itemEl.querySelector(
      "button[data-move-dir]:not(:disabled), button:not(:disabled)",
    ) as HTMLButtonElement | null;
    altBtn?.focus({ preventScroll: true });
  });
}

export interface SortableListOptions<T> {
  id: string;
  items: readonly T[];
  getKey: (item: T, index: number) => string;
  getLabel: (item: T, index: number) => string;
  renderHeader?: (item: T, index: number) => unknown;
  renderContent: (item: T, index: number) => unknown;
  renderActions?: (item: T, index: number) => unknown;
  onReorder: (fromIndex: number, toIndex: number) => void;
  ariaLabel?: string;
  rowClass?: string | ((item: T, index: number) => string);
  canMoveItem?: (item: T, index: number) => boolean;
  emptyState?: TemplateResult | string;
  overlay?: Readonly<Record<string, string>> | null;
}

export function renderSortableList<T>(opts: SortableListOptions<T>): TemplateResult {
  const total = opts.items.length;
  const liveMsg = SORTABLE_LIVE_STATUS.get(opts.id) || "";

  if (total === 0) {
    return html`<div id=${opts.id} data-sortable-list=${opts.id} class="sortable-list">
      ${typeof opts.emptyState === "string"
        ? html`<p class="empty-state">${opts.emptyState}</p>`
        : opts.emptyState || nothing}
      <span
      data-sortable-live
      role="status"
      aria-live="polite"
      class="sr-only"
      .textContent=${live(liveMsg)}
    ></span>
    </div>`;
  }

  const seenKeys = new Map<string, number>();
  const uniqueKeys = opts.items.map((item, idx) => {
    const raw = String(opts.getKey(item, idx));
    const prevCount = seenKeys.get(raw) ?? 0;
    seenKeys.set(raw, prevCount + 1);
    return prevCount === 0 ? raw : `${raw}__dup_${prevCount}`;
  });

  return html`<div
    id=${opts.id}
    data-sortable-list=${opts.id}
    role="group"
    aria-label=${opts.ariaLabel || nothing}
    class="sortable-list"
  >
    ${repeat(
      opts.items,
      (_item, idx) => uniqueKeys[idx] ?? String(idx),
      (item, idx) => {
        const key = uniqueKeys[idx] ?? String(idx);
        const label = opts.getLabel(item, idx);
        const movable = opts.canMoveItem ? opts.canMoveItem(item, idx) : true;
        const extraCls =
          typeof opts.rowClass === "function"
            ? opts.rowClass(item, idx)
            : opts.rowClass || "";
        const drag = attachDragHandleHandlers({
          listId: opts.id,
          orientation: "vertical",
          idx,
          total,
          itemLabel: label,
          overlay: opts.overlay,
          onReorder: opts.onReorder,
        });

        const dragBtn =
          movable && total > 1
            ? html`<button
                type="button"
                tabindex="-1"
                aria-hidden="true"
                @pointerdown=${drag.onPointerDown}
                @pointermove=${drag.onPointerMove}
                @pointerup=${drag.onPointerUp}
                @pointercancel=${drag.onPointerCancel}
                @lostpointercapture=${drag.onPointerCancel}
                class="drag-handle"
              >
                ≡
              </button>`
            : nothing;

        const actionsEl = html`<div class="sortable-row-actions">
          ${movable && total > 1
            ? html`<button
                  type="button"
                  data-move-dir="prev"
                  aria-label=${t("action.move_up", { item: label }, opts.overlay)}
                  ?disabled=${idx === 0}
                  @click=${(ev: Event) =>
                    triggerKeyboardMoveWithFocusRestore({
                      btnEl: ev.currentTarget as HTMLElement,
                      listId: opts.id,
                      itemKey: key,
                      itemLabel: label,
                      preferredDir: "prev",
                      fromIndex: idx,
                      toIndex: idx - 1,
                      total,
                      overlay: opts.overlay,
                      onReorder: opts.onReorder,
                    })}
                  class="btn-icon"
                >
                  ↑
                </button>
                <button
                  type="button"
                  data-move-dir="next"
                  aria-label=${t("action.move_down", { item: label }, opts.overlay)}
                  ?disabled=${idx === total - 1}
                  @click=${(ev: Event) =>
                    triggerKeyboardMoveWithFocusRestore({
                      btnEl: ev.currentTarget as HTMLElement,
                      listId: opts.id,
                      itemKey: key,
                      itemLabel: label,
                      preferredDir: "next",
                      fromIndex: idx,
                      toIndex: idx + 1,
                      total,
                      overlay: opts.overlay,
                      onReorder: opts.onReorder,
                    })}
                  class="btn-icon"
                >
                  ↓
                </button>`
            : nothing}
          ${opts.renderActions ? opts.renderActions(item, idx) : nothing}
        </div>`;

        if (opts.renderHeader) {
          return html`<div
            data-sortable-key=${key}
            data-sortable-index=${String(idx)}
            class="sortable-row sortable-row-stacked${extraCls ? ` ${extraCls}` : ""}"
          >
            <div class="sortable-row-head">
              ${dragBtn}
              <div class="sortable-row-title">${opts.renderHeader(item, idx)}</div>
              ${actionsEl}
            </div>
            <div class="sortable-row-content">${opts.renderContent(item, idx)}</div>
          </div>`;
        }

        return html`<div
          data-sortable-key=${key}
          data-sortable-index=${String(idx)}
          class="sortable-row${extraCls ? ` ${extraCls}` : ""}"
        >
          ${dragBtn}
          <div class="sortable-row-content">${opts.renderContent(item, idx)}</div>
          ${actionsEl}
        </div>`;
      },
    )}
    <span
      data-sortable-live
      role="status"
      aria-live="polite"
      class="sr-only"
      .textContent=${live(liveMsg)}
    ></span>
  </div>`;
}

export interface PillListItem {
  token: string;
  label: string;
  enabled: boolean;
  disabled?: boolean;
}

export interface PillListOptions {
  id: string;
  ariaLabel?: string;
  items: readonly PillListItem[];
  onToggle: (token: string, nextEnabled: boolean) => void;
  onReorder?: (fromEnabledIndex: number, toEnabledIndex: number) => void;
  overlay?: Readonly<Record<string, string>> | null;
}

export function renderPillList(opts: PillListOptions): TemplateResult {
  const enabledItems = opts.items.filter((it) => it.enabled);
  const disabledItems = opts.items.filter((it) => !it.enabled);
  const enabledCount = enabledItems.length;
  const reorderFn = opts.onReorder;
  const canReorder = Boolean(reorderFn && enabledCount > 1);
  const liveMsg = SORTABLE_LIVE_STATUS.get(opts.id) || "";

  return html`<div
    id=${opts.id}
    data-sortable-list=${opts.id}
    role="group"
    aria-label=${opts.ariaLabel || nothing}
    class="pill-list"
  >
    ${repeat(
      enabledItems,
      (item) => item.token,
      (item, idx) => {
        const drag = reorderFn
          ? attachDragHandleHandlers({
              listId: opts.id,
              orientation: "horizontal",
              idx,
              total: enabledCount,
              itemLabel: item.label,
              overlay: opts.overlay,
              onReorder: reorderFn,
            })
          : null;

        return html`<span
          data-sortable-key=${item.token}
          data-sortable-index=${canReorder ? String(idx) : nothing}
          class="pill enabled"
        >
          ${canReorder && drag
            ? html`<button
                type="button"
                tabindex="-1"
                aria-hidden="true"
                @pointerdown=${drag.onPointerDown}
                @pointermove=${drag.onPointerMove}
                @pointerup=${drag.onPointerUp}
                @pointercancel=${drag.onPointerCancel}
                @lostpointercapture=${drag.onPointerCancel}
                class="drag-handle"
              >
                ≡
              </button>`
            : nothing}
          ${canReorder && reorderFn
            ? html`<button
                type="button"
                data-move-dir="prev"
                aria-label=${t("action.move_earlier", { item: item.label }, opts.overlay)}
                ?disabled=${idx === 0}
                @click=${(ev: Event) =>
                  triggerKeyboardMoveWithFocusRestore({
                    btnEl: ev.currentTarget as HTMLElement,
                    listId: opts.id,
                    itemKey: item.token,
                    itemLabel: item.label,
                    preferredDir: "prev",
                    fromIndex: idx,
                    toIndex: idx - 1,
                    total: enabledCount,
                    overlay: opts.overlay,
                    onReorder: reorderFn,
                  })}
                class="pill-move"
              >
                ‹
              </button>`
            : nothing}
          <button
            type="button"
            aria-pressed="true"
            ?disabled=${Boolean(item.disabled)}
            @click=${() => opts.onToggle(item.token, false)}
            class="pill-toggle"
          >
            ${item.label}
          </button>
          ${canReorder && reorderFn
            ? html`<button
                type="button"
                data-move-dir="next"
                aria-label=${t("action.move_later", { item: item.label }, opts.overlay)}
                ?disabled=${idx === enabledCount - 1}
                @click=${(ev: Event) =>
                  triggerKeyboardMoveWithFocusRestore({
                    btnEl: ev.currentTarget as HTMLElement,
                    listId: opts.id,
                    itemKey: item.token,
                    itemLabel: item.label,
                    preferredDir: "next",
                    fromIndex: idx,
                    toIndex: idx + 1,
                    total: enabledCount,
                    overlay: opts.overlay,
                    onReorder: reorderFn,
                  })}
                class="pill-move"
              >
                ›
              </button>`
            : nothing}
        </span>`;
      },
    )}
    ${repeat(
      disabledItems,
      (item) => `off:${item.token}`,
      (item) => html`<span class="pill">
        <button
          type="button"
          aria-pressed="false"
          ?disabled=${Boolean(item.disabled)}
          @click=${() => opts.onToggle(item.token, true)}
          class="pill-toggle"
        >
          ${item.label}
        </button>
      </span>`,
    )}
    <span
      data-sortable-live
      role="status"
      aria-live="polite"
      class="sr-only"
      .textContent=${live(liveMsg)}
    ></span>
  </div>`;
}
