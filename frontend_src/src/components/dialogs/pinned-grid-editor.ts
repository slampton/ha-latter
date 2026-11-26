/**
 * Visual Tile-Grid Page Editor for Pinned App (`#latter-app-config-modal`, `D-047`, `D-053`, `D-086`).
 *
 * - Adaptive 2×3 / 3×3 / 4×3 CSS Grid positioned strictly via `--grid-*` custom properties
 * - Per-page tabs, optional custom page titles (`<= 24` chars), `+ Add page`, & confirmed `Delete page`
 * - Cross-device reflow notice with 1-click `Pack to this grid`
 * - Pointer drag-to-move / swap (with click vs. drag threshold) and bottom-end corner drag-to-resize
 * - Full keyboard navigation (`Arrow*` move, `Shift+Arrow*` resize, `Enter` edit, `Delete` remove)
 */

import {
  MAX_PINNED_GRID_PAGES,
  MAX_PINNED_ITEMS,
  PINNED_PAGE_TITLE_MAX,
  SHORTCUT_ROUTES_CATALOG,
} from "../../constants.js";
import { focusSafe, html, nothing, repeat, type TemplateResult } from "../../lib/lit.js";
import { ROUTE_PREVIEW_ICONS, shortcutActionLabel } from "../../mdi-catalog.js";
import { shortcutBadgeClass, type StudioStore } from "../../state/store.js";
import type { ShortcutItem } from "../../types.js";
import { fmtNumber } from "../../utils/format.js";
import {
  canPlaceTile,
  moveOrSwapTile,
  packLayoutToGrid,
  type ResolvedGridTile,
  type ResolvedTileGridLayout,
  resizeTile,
  resolveDeviceGridDims,
  resolveTileGridLayout,
  sanitizePinnedPageTitle,
} from "../../utils/tile-grid.js";
import { isImeSafeEnter } from "../controls/aria-helpers.js";

interface PinnedGridDragSession {
  mode: "move" | "resize";
  pointerId: number;
  itemIndex: number;
  page: number;
  startX: number;
  startY: number;
  originCol: number;
  originRow: number;
  colSpan: number;
  rowSpan: number;
  grabOffsetCols: number;
  grabOffsetRows: number;
  targetCol: number;
  targetRow: number;
  targetColSpan: number;
  targetRowSpan: number;
  valid: boolean;
  active: boolean;
  dragEl: HTMLElement | null;
  rafId: number | null;
  pendingDx: number;
  pendingDy: number;
}

const DRAG_THRESHOLD_PX = 6;
const activeDragSessions = new WeakMap<StudioStore, PinnedGridDragSession>();
const suppressClickUntil = new WeakMap<StudioStore, number>();

export function shouldRequestGridDragUpdate(
  prev: { targetCol: number; targetRow: number; valid: boolean },
  next: { targetCol: number; targetRow: number; valid: boolean },
  justActivated: boolean,
): boolean {
  return (
    justActivated ||
    next.targetCol !== prev.targetCol ||
    next.targetRow !== prev.targetRow ||
    next.valid !== prev.valid
  );
}

function clearDragSession(store: StudioStore): PinnedGridDragSession | null {
  const session = activeDragSessions.get(store) ?? null;
  if (!session) return null;
  activeDragSessions.delete(store);
  if (session.rafId !== null && typeof cancelAnimationFrame === "function") {
    cancelAnimationFrame(session.rafId);
  }
  session.rafId = null;
  if (session.dragEl?.style) {
    session.dragEl.style.setProperty("--drag-x", "0px");
    session.dragEl.style.setProperty("--drag-y", "0px");
  }
  session.dragEl = null;
  return session;
}

function clampInt(val: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, val));
}

function resolveTilePresentation(
  item: ShortcutItem,
  routeSpecMap: ReadonlyMap<string, (typeof SHORTCUT_ROUTES_CATALOG)[number]>,
  shortcutEntityMap: ReadonlyMap<string, { id: string; name: string; icon: string }>,
): { displayTitle: string; shortMeta: string; iconSlug: string } {
  if (item.kind === "route") {
    const spec = routeSpecMap.get(item.target);
    return {
      displayTitle: item.label || spec?.label || item.target,
      shortMeta: spec?.group || item.target,
      iconSlug: item.icon || ROUTE_PREVIEW_ICONS[item.target] || "mdi:apps",
    };
  }
  const ent = shortcutEntityMap.get(item.target);
  const dom = item.target.split(".", 1)[0] || "";
  const actLbl = shortcutActionLabel(dom, item.action);
  return {
    displayTitle: item.label || ent?.name || item.target,
    shortMeta: actLbl,
    iconSlug: item.icon || ent?.icon || "mdi:flash",
  };
}

function tileVisualClass(item: ShortcutItem): string {
  const classes = ["pinned-grid-tile"];
  if (item.badge_style === "inverted") {
    classes.push("tile-inverted");
  }
  if (item.accent) {
    classes.push(`tile-accent-${item.accent}`);
  }
  return classes.join(" ");
}

function pointerCellFromEvent(
  ev: PointerEvent,
  canvasEl: HTMLElement,
  cols: number,
  rows: number,
): { col: number; row: number } {
  const rect = canvasEl.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    return { col: 0, row: 0 };
  }
  const isRtl =
    typeof getComputedStyle === "function" &&
    getComputedStyle(canvasEl).direction === "rtl";
  const relX = isRtl
    ? (rect.right - ev.clientX) / rect.width
    : (ev.clientX - rect.left) / rect.width;
  const relY = (ev.clientY - rect.top) / rect.height;
  return {
    col: clampInt(Math.floor(relX * cols), 0, cols - 1),
    row: clampInt(Math.floor(relY * rows), 0, rows - 1),
  };
}

function restoreTileFocus(rootEl: HTMLElement, tileKey: string): void {
  const root =
    typeof rootEl.getRootNode === "function"
      ? (rootEl.getRootNode() as Document | ShadowRoot)
      : document;
  if (typeof requestAnimationFrame !== "function") return;
  requestAnimationFrame(() => {
    if (!root || typeof root.querySelector !== "function") return;
    const selector = `[data-pinned-tile-key="${CSS.escape(tileKey)}"]`;
    const el = root.querySelector(selector) as HTMLElement | null;
    el?.focus({ preventScroll: true });
  });
}

function buildOccupiedCellSet(
  tilesOnPage: readonly ResolvedGridTile[],
  cols: number,
): Set<number> {
  const occupied = new Set<number>();
  for (const t of tilesOnPage) {
    for (let r = t.row; r < t.row + t.rowSpan; r += 1) {
      for (let c = t.col; c < t.col + t.colSpan; c += 1) {
        occupied.add(r * cols + c);
      }
    }
  }
  return occupied;
}

export function renderPinnedGridEditor(store: StudioStore): TemplateResult {
  const data = store.state;
  const caps = data?.capabilities;
  const dims = resolveDeviceGridDims(caps);
  const { cols, rows } = dims;
  const isRound = caps?.is_round === true;

  const pinnedItems = store.entity.getPinnedItems();
  const pageTitles = store.entity.getPinnedPageTitles();
  const resolved: ResolvedTileGridLayout = resolveTileGridLayout(pinnedItems, cols, rows);

  const titleKeys = Object.keys(pageTitles);
  const maxTitlePage = titleKeys.reduce((m, k) => Math.max(m, Number(k) || 0), 0);
  const basePages = Math.max(
    1,
    resolved.pageCount,
    titleKeys.length > 0 ? maxTitlePage + 1 : 1,
  );
  const totalPages = Math.min(
    MAX_PINNED_GRID_PAGES,
    basePages + Math.max(0, store.pinnedExtraPages),
  );
  const activePage = clampInt(store.pinnedActivePage, 0, totalPages - 1);
  if (activePage !== store.pinnedActivePage) {
    store.pinnedActivePage = activePage;
  }

  const tilesOnPage = resolved.tiles.filter((t) => t.page === activePage);
  const occupiedCells = buildOccupiedCellSet(tilesOnPage, cols);
  const currentTitle = pageTitles[String(activePage)] || "";
  const activePageLabel =
    currentTitle || store.t("dialogs.pinned_page_slot", { page: activePage + 1 });

  const shortcutEntityMap = new Map(
    (data?.catalog?.shortcut_entities || []).map((e) => [e.id, e]),
  );
  const routeSpecMap = new Map(SHORTCUT_ROUTES_CATALOG.map((r) => [r.token, r]));

  const dragSession = activeDragSessions.get(store) ?? null;
  const activeGhost =
    dragSession && dragSession.active && dragSession.page === activePage ? dragSession : null;

  const selectPage = (nextPage: number, focusTabEl?: HTMLElement | null): void => {
    clearDragSession(store);
    store.pinnedActivePage = clampInt(nextPage, 0, totalPages - 1);
    store.host.requestUpdate();
    if (focusTabEl) {
      requestAnimationFrame(() => {
        focusTabEl.focus();
      });
    }
  };

  const addPage = (): void => {
    if (totalPages >= MAX_PINNED_GRID_PAGES) return;
    clearDragSession(store);
    store.pinnedExtraPages = Math.max(0, store.pinnedExtraPages) + 1;
    store.pinnedActivePage = totalPages;
    store.host.requestUpdate();
  };

  const commitPageTitle = (rawValue: string): void => {
    const clean = sanitizePinnedPageTitle(rawValue);
    const prev = pageTitles[String(activePage)] || "";
    if (clean === prev) return;
    const nextTitles = { ...pageTitles };
    if (clean) {
      nextTitles[String(activePage)] = clean;
    } else {
      delete nextTitles[String(activePage)];
    }
    store.entity.savePinnedPageTitles(nextTitles);
  };

  const requestDeleteActivePage = (): void => {
    if (totalPages <= 1) return;
    const countOnPage = tilesOnPage.length;
    if (countOnPage === 0) {
      store.entity.deletePinnedPage(activePage);
      return;
    }
    store.openConfirm({
      kind: "delete_pinned_page",
      title: store.t("confirm.delete_pinned_page.title", { page: activePageLabel }),
      consequence:
        countOnPage === 1
          ? store.t("confirm.delete_pinned_page.body_one")
          : store.t("confirm.delete_pinned_page.body_many", {
              count: fmtNumber(countOnPage, store.hass, 0),
            }),
      confirmLabel: store.t("confirm.delete_pinned_page.confirm"),
      danger: true,
      onConfirm: () => {
        store.entity.deletePinnedPage(activePage);
      },
    });
  };

  const removeTile = (tileIdx: number, title: string): void => {
    clearDragSession(store);
    const packed = packLayoutToGrid(pinnedItems, cols, rows);
    const next = packed.filter((_, i) => i !== tileIdx);
    store.entity.savePinnedGridState(next);
    store.announcePolite(store.t("dialogs.pinned_removed_status", { item: title }));
  };

  const onPageTabKeyDown = (ev: KeyboardEvent, pIdx: number): void => {
    if (
      ev.key !== "ArrowLeft" &&
      ev.key !== "ArrowRight" &&
      ev.key !== "Home" &&
      ev.key !== "End"
    ) {
      return;
    }
    ev.preventDefault();
    let nextP = pIdx;
    if (ev.key === "Home") nextP = 0;
    else if (ev.key === "End") nextP = totalPages - 1;
    else if (ev.key === "ArrowLeft") nextP = (pIdx - 1 + totalPages) % totalPages;
    else nextP = (pIdx + 1) % totalPages;
    const tablist = (ev.currentTarget as HTMLElement).parentElement;
    const targetTab = tablist?.querySelector(`#pinned-page-tab-${nextP}`) as HTMLElement | null;
    selectPage(nextP, targetTab);
  };

  const onTilePointerDown = (ev: PointerEvent, tile: ResolvedGridTile): void => {
    if (ev.button !== 0) return;
    const targetEl = ev.target as HTMLElement | null;
    if (targetEl?.closest("button, .pinned-tile-resize-handle")) return;
    const tileEl = ev.currentTarget as HTMLElement;
    const canvasEl = tileEl.closest(".pinned-grid-canvas") as HTMLElement | null;
    if (!canvasEl) return;

    const pCell = pointerCellFromEvent(ev, canvasEl, cols, rows);
    const grabOffsetCols = clampInt(pCell.col - tile.col, 0, tile.colSpan - 1);
    const grabOffsetRows = clampInt(pCell.row - tile.row, 0, tile.rowSpan - 1);

    try {
      tileEl.setPointerCapture(ev.pointerId);
    } catch {
      // Headless environments may omit pointer capture.
    }

    clearDragSession(store);
    activeDragSessions.set(store, {
      mode: "move",
      pointerId: ev.pointerId,
      itemIndex: tile.index,
      page: activePage,
      startX: ev.clientX,
      startY: ev.clientY,
      originCol: tile.col,
      originRow: tile.row,
      colSpan: tile.colSpan,
      rowSpan: tile.rowSpan,
      grabOffsetCols,
      grabOffsetRows,
      targetCol: tile.col,
      targetRow: tile.row,
      targetColSpan: tile.colSpan,
      targetRowSpan: tile.rowSpan,
      valid: true,
      active: false,
      dragEl: tileEl,
      rafId: null,
      pendingDx: 0,
      pendingDy: 0,
    });
  };

  const onTilePointerMove = (ev: PointerEvent): void => {
    const session = activeDragSessions.get(store);
    if (!session || session.mode !== "move" || session.pointerId !== ev.pointerId) return;
    const tileEl = ev.currentTarget as HTMLElement;
    const canvasEl = tileEl.closest(".pinned-grid-canvas") as HTMLElement | null;
    if (!canvasEl) return;

    let justActivated = false;
    if (!session.active) {
      if (Math.hypot(ev.clientX - session.startX, ev.clientY - session.startY) < DRAG_THRESHOLD_PX) {
        return;
      }
      session.active = true;
      justActivated = true;
    }

    session.dragEl = tileEl;
    session.pendingDx = ev.clientX - session.startX;
    session.pendingDy = ev.clientY - session.startY;
    if (session.rafId === null) {
      const applyDragOffset = (): void => {
        session.rafId = null;
        if (!session.active || !session.dragEl?.style) return;
        session.dragEl.style.setProperty("--drag-x", `${session.pendingDx}px`);
        session.dragEl.style.setProperty("--drag-y", `${session.pendingDy}px`);
      };
      if (typeof requestAnimationFrame === "function") {
        session.rafId = requestAnimationFrame(applyDragOffset);
      } else {
        applyDragOffset();
      }
    }

    const pCell = pointerCellFromEvent(ev, canvasEl, cols, rows);
    const nextCol = clampInt(pCell.col - session.grabOffsetCols, 0, cols - session.colSpan);
    const nextRow = clampInt(pCell.row - session.grabOffsetRows, 0, rows - session.rowSpan);
    if (!justActivated && nextCol === session.targetCol && nextRow === session.targetRow) {
      return;
    }

    const sameSpot = nextCol === session.originCol && nextRow === session.originRow;
    const nextValid =
      sameSpot ||
      moveOrSwapTile(
        pinnedItems,
        resolved,
        session.itemIndex,
        session.page,
        nextCol,
        nextRow,
        cols,
        rows,
      ) !== null;

    if (
      shouldRequestGridDragUpdate(
        session,
        { targetCol: nextCol, targetRow: nextRow, valid: nextValid },
        justActivated,
      )
    ) {
      session.targetCol = nextCol;
      session.targetRow = nextRow;
      session.valid = nextValid;
      store.host.requestUpdate();
    }
  };

  const finishMovePointer = (
    ev: PointerEvent,
    cancelled: boolean,
    displayTitle: string,
  ): void => {
    const existing = activeDragSessions.get(store);
    if (!existing || existing.mode !== "move" || existing.pointerId !== ev.pointerId) return;
    const session = clearDragSession(store);
    if (!session) return;
    const tileEl = ev.currentTarget as HTMLElement;
    try {
      if (
        typeof tileEl.hasPointerCapture === "function" &&
        tileEl.hasPointerCapture(ev.pointerId)
      ) {
        tileEl.releasePointerCapture(ev.pointerId);
      }
    } catch {
      // Ignore release errors.
    }
    if (!session.active) return;
    suppressClickUntil.set(store, Date.now() + 250);
    if (
      !cancelled &&
      session.valid &&
      (session.targetCol !== session.originCol || session.targetRow !== session.originRow)
    ) {
      const nextItems = moveOrSwapTile(
        pinnedItems,
        resolved,
        session.itemIndex,
        session.page,
        session.targetCol,
        session.targetRow,
        cols,
        rows,
      );
      if (nextItems) {
        store.entity.savePinnedGridState(nextItems);
        store.announcePolite(
          store.t("dialogs.pinned_moved_status", {
            item: displayTitle,
            row: session.targetRow + 1,
            col: session.targetCol + 1,
          }),
        );
        return;
      }
    }
    store.host.requestUpdate();
  };

  const onResizePointerDown = (ev: PointerEvent, tile: ResolvedGridTile): void => {
    if (ev.button !== 0) return;
    ev.stopPropagation();
    ev.preventDefault();
    const handleEl = ev.currentTarget as HTMLElement;
    try {
      handleEl.setPointerCapture(ev.pointerId);
    } catch {
      // Headless environments may omit pointer capture.
    }
    clearDragSession(store);
    activeDragSessions.set(store, {
      mode: "resize",
      pointerId: ev.pointerId,
      itemIndex: tile.index,
      page: activePage,
      startX: ev.clientX,
      startY: ev.clientY,
      originCol: tile.col,
      originRow: tile.row,
      colSpan: tile.colSpan,
      rowSpan: tile.rowSpan,
      grabOffsetCols: 0,
      grabOffsetRows: 0,
      targetCol: tile.col,
      targetRow: tile.row,
      targetColSpan: tile.colSpan,
      targetRowSpan: tile.rowSpan,
      valid: true,
      active: true,
      dragEl: null,
      rafId: null,
      pendingDx: 0,
      pendingDy: 0,
    });
    store.host.requestUpdate();
  };

  const onResizePointerMove = (ev: PointerEvent): void => {
    const session = activeDragSessions.get(store);
    if (!session || session.mode !== "resize" || session.pointerId !== ev.pointerId) return;
    const handleEl = ev.currentTarget as HTMLElement;
    const canvasEl = handleEl.closest(".pinned-grid-canvas") as HTMLElement | null;
    if (!canvasEl) return;

    const pCell = pointerCellFromEvent(ev, canvasEl, cols, rows);
    const nextCs = clampInt(pCell.col - session.originCol + 1, 1, cols - session.originCol);
    const nextRs = clampInt(pCell.row - session.originRow + 1, 1, rows - session.originRow);
    if (nextCs === session.targetColSpan && nextRs === session.targetRowSpan) {
      return;
    }

    const unchanged = nextCs === session.colSpan && nextRs === session.rowSpan;
    const nextValid =
      unchanged ||
      canPlaceTile(
        resolved,
        session.itemIndex,
        session.page,
        session.originCol,
        session.originRow,
        nextCs,
        nextRs,
        cols,
        rows,
      );

    if (
      nextCs !== session.targetColSpan ||
      nextRs !== session.targetRowSpan ||
      nextValid !== session.valid
    ) {
      session.targetColSpan = nextCs;
      session.targetRowSpan = nextRs;
      session.valid = nextValid;
      store.host.requestUpdate();
    }
  };

  const finishResizePointer = (
    ev: PointerEvent,
    cancelled: boolean,
    displayTitle: string,
  ): void => {
    const existing = activeDragSessions.get(store);
    if (!existing || existing.mode !== "resize" || existing.pointerId !== ev.pointerId) return;
    const session = clearDragSession(store);
    if (!session) return;
    const handleEl = ev.currentTarget as HTMLElement;
    try {
      if (
        typeof handleEl.hasPointerCapture === "function" &&
        handleEl.hasPointerCapture(ev.pointerId)
      ) {
        handleEl.releasePointerCapture(ev.pointerId);
      }
    } catch {
      // Ignore release errors.
    }
    suppressClickUntil.set(store, Date.now() + 250);
    if (
      !cancelled &&
      session.valid &&
      (session.targetColSpan !== session.colSpan || session.targetRowSpan !== session.rowSpan)
    ) {
      const nextItems = resizeTile(
        pinnedItems,
        resolved,
        session.itemIndex,
        session.targetColSpan,
        session.targetRowSpan,
        cols,
        rows,
      );
      if (nextItems) {
        store.entity.savePinnedGridState(nextItems);
        store.announcePolite(
          store.t("dialogs.pinned_resized_status", {
            item: displayTitle,
            colSpan: session.targetColSpan,
            rowSpan: session.targetRowSpan,
          }),
        );
        return;
      }
    }
    store.host.requestUpdate();
  };

  const applyTileResizeDelta = (
    el: HTMLElement,
    tile: ResolvedGridTile,
    tileKey: string,
    displayTitle: string,
    dCol: number,
    dRow: number,
  ): void => {
    const nextCs = clampInt(tile.colSpan + dCol, 1, cols);
    const nextRs = clampInt(tile.rowSpan + dRow, 1, rows);
    if (nextCs === tile.colSpan && nextRs === tile.rowSpan) return;
    const nextItems = resizeTile(pinnedItems, resolved, tile.index, nextCs, nextRs, cols, rows);
    if (!nextItems) return;
    store.entity.savePinnedGridState(nextItems);
    store.announcePolite(
      store.t("dialogs.pinned_resized_status", {
        item: displayTitle,
        colSpan: nextCs,
        rowSpan: nextRs,
      }),
    );
    restoreTileFocus(el, tileKey);
  };

  const onTileKeyDown = (
    ev: KeyboardEvent,
    tile: ResolvedGridTile,
    tileKey: string,
    displayTitle: string,
  ): void => {
    const tileEl = ev.currentTarget as HTMLElement;
    if (ev.target !== tileEl) return;

    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      store.entity.openShortcutModal("pinned_items", tile.index);
      return;
    }
    if (ev.key === "Delete" || ev.key === "Backspace") {
      ev.preventDefault();
      removeTile(tile.index, displayTitle);
      return;
    }
    if (
      ev.key !== "ArrowUp" &&
      ev.key !== "ArrowDown" &&
      ev.key !== "ArrowLeft" &&
      ev.key !== "ArrowRight"
    ) {
      return;
    }
    ev.preventDefault();
    const isRtl =
      typeof getComputedStyle === "function" &&
      getComputedStyle(tileEl).direction === "rtl";
    const horizSign = isRtl ? -1 : 1;
    const dCol =
      ev.key === "ArrowRight" ? horizSign : ev.key === "ArrowLeft" ? -horizSign : 0;
    const dRow = ev.key === "ArrowDown" ? 1 : ev.key === "ArrowUp" ? -1 : 0;

    if (ev.shiftKey) {
      applyTileResizeDelta(tileEl, tile, tileKey, displayTitle, dCol, dRow);
      return;
    }

    const nextCol = clampInt(tile.col + dCol, 0, cols - tile.colSpan);
    const nextRow = clampInt(tile.row + dRow, 0, rows - tile.rowSpan);
    if (nextCol === tile.col && nextRow === tile.row) return;
    const nextItems = moveOrSwapTile(
      pinnedItems,
      resolved,
      tile.index,
      tile.page,
      nextCol,
      nextRow,
      cols,
      rows,
    );
    if (!nextItems) return;
    store.entity.savePinnedGridState(nextItems);
    store.announcePolite(
      store.t("dialogs.pinned_moved_status", {
        item: displayTitle,
        row: nextRow + 1,
        col: nextCol + 1,
      }),
    );
    restoreTileFocus(tileEl, tileKey);
  };

  const onResizeHandleKeyDown = (
    ev: KeyboardEvent,
    tile: ResolvedGridTile,
    tileKey: string,
    displayTitle: string,
  ): void => {
    if (
      ev.key !== "ArrowUp" &&
      ev.key !== "ArrowDown" &&
      ev.key !== "ArrowLeft" &&
      ev.key !== "ArrowRight"
    ) {
      return;
    }
    ev.preventDefault();
    ev.stopPropagation();
    const handleEl = ev.currentTarget as HTMLElement;
    const isRtl =
      typeof getComputedStyle === "function" &&
      getComputedStyle(handleEl).direction === "rtl";
    const horizSign = isRtl ? -1 : 1;
    const dCol =
      ev.key === "ArrowRight" ? horizSign : ev.key === "ArrowLeft" ? -horizSign : 0;
    const dRow = ev.key === "ArrowDown" ? 1 : ev.key === "ArrowUp" ? -1 : 0;
    applyTileResizeDelta(handleEl, tile, tileKey, displayTitle, dCol, dRow);
  };

  const pageIndices = Array.from({ length: totalPages }, (_, i) => i);
  const allCells: Array<{ col: number; row: number }> = [];
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      allCells.push({ col: c, row: r });
    }
  }

  return html`<div
    class="pinned-grid-editor"
    @keydown=${(ev: KeyboardEvent) => {
      if (ev.key === "Escape" && activeDragSessions.has(store)) {
        ev.preventDefault();
        ev.stopPropagation();
        clearDragSession(store);
        store.host.requestUpdate();
      }
    }}
  >
    <p class="row-description">${store.t("dialogs.pinned_desc")}</p>

    <div class="pinned-page-bar">
      <div
        role="tablist"
        aria-label=${store.t("dialogs.pinned_pages_aria")}
        class="pinned-page-tabs"
      >
        ${pageIndices.map((pIdx) => {
          const isSelected = pIdx === activePage;
          const tabLabel =
            pageTitles[String(pIdx)] || store.t("dialogs.pinned_page_slot", { page: pIdx + 1 });
          return html`<button
            type="button"
            id=${`pinned-page-tab-${pIdx}`}
            role="tab"
            aria-selected=${isSelected ? "true" : "false"}
            aria-controls="pinned-grid-tabpanel"
            tabindex=${isSelected ? "0" : "-1"}
            @click=${() => selectPage(pIdx)}
            @keydown=${(ev: KeyboardEvent) => onPageTabKeyDown(ev, pIdx)}
            class="pinned-page-tab ${isSelected ? "active" : ""}"
          >
            ${tabLabel}
          </button>`;
        })}
      </div>
      <div class="pinned-page-bar-end">
        <button
          type="button"
          id="btn-pinned-add-page"
          ?disabled=${totalPages >= MAX_PINNED_GRID_PAGES}
          @click=${addPage}
          class="btn btn-secondary btn-compact"
        >
          ${store.t("dialogs.pinned_add_page")}
        </button>
        <span class="chip pinned-grid-dims-chip">
          ${store.t("dialogs.pinned_grid_dims", { cols, rows })}
        </span>
      </div>
    </div>

    <div
      id="pinned-grid-tabpanel"
      role="tabpanel"
      aria-labelledby=${`pinned-page-tab-${activePage}`}
    >
      <div class="pinned-page-controls">
        <div class="stacked-field pinned-page-title-field">
          <label for="pinned-page-title-input">
            ${store.t("dialogs.pinned_page_title_label")}
          </label>
          <input
            type="text"
            id="pinned-page-title-input"
            maxlength=${String(PINNED_PAGE_TITLE_MAX)}
            placeholder=${store.t("dialogs.pinned_page_title_placeholder")}
            .value=${focusSafe(currentTitle)}
            @change=${(ev: Event) => commitPageTitle((ev.currentTarget as HTMLInputElement).value)}
            @keydown=${(ev: KeyboardEvent) => {
              if (isImeSafeEnter(ev)) {
                ev.preventDefault();
                commitPageTitle((ev.currentTarget as HTMLInputElement).value);
              }
            }}
          />
        </div>
        ${totalPages > 1
          ? html`<button
              type="button"
              id="btn-pinned-delete-page"
              @click=${requestDeleteActivePage}
              class="btn btn-danger btn-compact"
            >
              ${store.t("dialogs.pinned_delete_page")}
            </button>`
          : nothing}
      </div>

      ${resolved.hasReflow
        ? html`<div id="pinned-reflow-banner" role="status" class="alert alert-info pinned-reflow-banner">
            <div class="alert-body">
              <span>${store.t("dialogs.pinned_reflow_notice", { cols, rows })}</span>
            </div>
            <button
              type="button"
              id="btn-pinned-pack-grid"
              @click=${() => {
                const packed = packLayoutToGrid(pinnedItems, cols, rows);
                store.entity.savePinnedGridState(packed);
                store.announcePolite(store.t("dialogs.pinned_packed_status"));
              }}
              class="btn btn-secondary btn-compact"
            >
              ${store.t("dialogs.pinned_pack_to_grid")}
            </button>
          </div>`
        : nothing}

      <div
        id="pinned-grid-canvas"
        role="region"
        aria-label=${store.t("dialogs.pinned_grid_aria", { page: activePageLabel })}
        style="--grid-cols: ${cols}; --grid-rows: ${rows};"
        class="pinned-grid-canvas ${isRound ? "is-round" : ""}"
      >
      ${allCells.map(
        (cell) => html`<div
          aria-hidden="true"
          style="--grid-col: ${cell.col + 1}; --grid-row: ${cell.row + 1};"
          class="pinned-grid-slot-guide"
        ></div>`,
      )}

      ${allCells.map((cell) => {
        if (occupiedCells.has(cell.row * cols + cell.col)) return nothing;
        const canAdd = pinnedItems.length < MAX_PINNED_ITEMS;
        return html`<button
          type="button"
          ?disabled=${!canAdd}
          data-grid-cell="${cell.col},${cell.row}"
          aria-label=${store.t("dialogs.pinned_add_cell_aria", {
            row: cell.row + 1,
            col: cell.col + 1,
          })}
          style="--grid-col: ${cell.col + 1}; --grid-row: ${cell.row + 1};"
          @click=${() =>
            store.entity.openShortcutModal("pinned_items", null, {
              page: activePage,
              col: cell.col,
              row: cell.row,
            })}
          class="pinned-grid-empty-cell"
        >
          <ha-icon .icon=${"mdi:plus"} aria-hidden="true"></ha-icon>
        </button>`;
      })}

      ${repeat(
        tilesOnPage,
        (tile) => `${tile.item.kind}|${tile.item.target}|${tile.item.action}`,
        (tile) => {
          const tileKey = `${tile.item.kind}|${tile.item.target}|${tile.item.action}`;
          const info = resolveTilePresentation(
            tile.item,
            routeSpecMap,
            shortcutEntityMap,
          );
          const isBeingDragged = Boolean(
            activeGhost && activeGhost.itemIndex === tile.index,
          );
          const showSpan = tile.colSpan > 1 || tile.rowSpan > 1;
          const tileAria = store.t("dialogs.pinned_tile_aria", {
            title: info.displayTitle,
            row: tile.row + 1,
            col: tile.col + 1,
            colSpan: tile.colSpan,
            rowSpan: tile.rowSpan,
          });
          return html`<div
            role="group"
            tabindex="0"
            aria-label=${tileAria}
            data-pinned-tile-key=${tileKey}
            data-pinned-tile-index=${String(tile.index)}
            style="--grid-col: ${tile.col + 1}; --grid-row: ${tile.row + 1}; --grid-w: ${tile.colSpan}; --grid-h: ${tile.rowSpan};"
            @pointerdown=${(ev: PointerEvent) => onTilePointerDown(ev, tile)}
            @pointermove=${onTilePointerMove}
            @pointerup=${(ev: PointerEvent) => finishMovePointer(ev, false, info.displayTitle)}
            @pointercancel=${(ev: PointerEvent) => finishMovePointer(ev, true, info.displayTitle)}
            @lostpointercapture=${(ev: PointerEvent) =>
              finishMovePointer(ev, true, info.displayTitle)}
            @click=${(ev: MouseEvent) => {
              const targetEl = ev.target as HTMLElement | null;
              if (targetEl?.closest("button, .pinned-tile-resize-handle")) return;
              if (Date.now() < (suppressClickUntil.get(store) ?? 0)) return;
              store.entity.openShortcutModal("pinned_items", tile.index);
            }}
            @keydown=${(ev: KeyboardEvent) =>
              onTileKeyDown(ev, tile, tileKey, info.displayTitle)}
            class="${tileVisualClass(tile.item)}${isBeingDragged ? " is-dragging" : ""}${showSpan ? " is-multi-span" : ""}"
          >
            <div class="pinned-tile-top-bar">
              <div class="pinned-tile-meta-badges">
                ${showSpan
                  ? html`<span class="pinned-tile-span-badge">
                      ${tile.colSpan}×${tile.rowSpan}
                    </span>`
                  : nothing}
                ${tile.item.confirm
                  ? html`<span
                      title=${store.t("dialogs.pinned_confirm_badge_title")}
                      class="pinned-tile-confirm-badge"
                    >
                      <ha-icon .icon=${"mdi:shield-check"} aria-hidden="true"></ha-icon>
                      <span class="sr-only">${store.t("dialogs.pinned_confirm_required")}</span>
                    </span>`
                  : nothing}
              </div>
              <div class="pinned-tile-actions">
                <button
                  type="button"
                  aria-label=${store.t("action.edit_item", { item: info.displayTitle })}
                  @click=${(ev: Event) => {
                    ev.stopPropagation();
                    store.entity.openShortcutModal("pinned_items", tile.index);
                  }}
                  class="pinned-tile-action-btn"
                >
                  <ha-icon .icon=${"mdi:pencil"} aria-hidden="true"></ha-icon>
                </button>
                <button
                  type="button"
                  aria-label=${store.t("action.remove_item", { item: info.displayTitle })}
                  @click=${(ev: Event) => {
                    ev.stopPropagation();
                    removeTile(tile.index, info.displayTitle);
                  }}
                  class="pinned-tile-action-btn danger"
                >
                  <ha-icon .icon=${"mdi:delete-outline"} aria-hidden="true"></ha-icon>
                </button>
              </div>
            </div>

            <div class="pinned-tile-content">
              <span
                class=${shortcutBadgeClass(tile.item.badge_style, tile.item.accent)}
                aria-hidden="true"
              >
                <ha-icon .icon=${info.iconSlug}></ha-icon>
              </span>
              <span class="pinned-tile-label">${info.displayTitle}</span>
              ${showSpan
                ? html`<span class="pinned-tile-sub">${info.shortMeta}</span>`
                : nothing}
            </div>

            <button
              type="button"
              aria-label=${store.t("dialogs.pinned_resize_tile")}
              title=${store.t("dialogs.pinned_resize_tile")}
              @pointerdown=${(ev: PointerEvent) => onResizePointerDown(ev, tile)}
              @pointermove=${onResizePointerMove}
              @pointerup=${(ev: PointerEvent) => finishResizePointer(ev, false, info.displayTitle)}
              @pointercancel=${(ev: PointerEvent) =>
                finishResizePointer(ev, true, info.displayTitle)}
              @lostpointercapture=${(ev: PointerEvent) =>
                finishResizePointer(ev, true, info.displayTitle)}
              @click=${(ev: Event) => ev.stopPropagation()}
              @keydown=${(ev: KeyboardEvent) =>
                onResizeHandleKeyDown(ev, tile, tileKey, info.displayTitle)}
              class="pinned-tile-resize-handle"
            ></button>
          </div>`;
        },
      )}

      ${activeGhost
        ? html`<div
            aria-hidden="true"
            style="--grid-col: ${activeGhost.targetCol + 1}; --grid-row: ${activeGhost.targetRow + 1}; --grid-w: ${activeGhost.targetColSpan}; --grid-h: ${activeGhost.targetRowSpan};"
            class="pinned-grid-ghost ${activeGhost.valid ? "valid" : "invalid"}"
          ></div>`
        : nothing}
    </div>
    </div>

    ${pinnedItems.length === 0
      ? html`<p class="empty-state">${store.t("dialogs.pinned_empty")}</p>`
      : nothing}

    <div class="pinned-grid-footer">
      <button
        type="button"
        id="btn-add-pinned-item"
        ?disabled=${pinnedItems.length >= MAX_PINNED_ITEMS}
        @click=${() => store.entity.openShortcutModal("pinned_items", null)}
        class="btn btn-primary"
      >
        ${store.t("dialogs.pinned_add_tile")}
      </button>
      <span class="row-description pinned-grid-count">
        ${store.t("dialogs.pinned_tile_count", {
          count: fmtNumber(pinnedItems.length, store.hass, 0),
          max: fmtNumber(MAX_PINNED_ITEMS, store.hass, 0),
        })}
      </span>
    </div>
  </div>`;
}
