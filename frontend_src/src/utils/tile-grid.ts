/**
 * Pure 2D Pinned Tile-Grid Solver & Layout Mutation Utilities (`D-086`).
 *
 * Maintains 1:1 parity with the firmware and backend 2-pass bitmask solver:
 * - Adaptive 2×3, 3×3, and 4×3 page grids resolved from Device hardware capabilities
 * - Pass 1 places items with valid explicit `(page, col, row)` and clamped spans
 * - Pass 2 auto-flows unplaced, out-of-bounds, and colliding items row-major
 * - Flags `hasReflow` whenever any tile's stored coordinates or spans had to adjust
 */

import {
  MAX_PINNED_GRID_PAGES,
  PINNED_GRID_MAX_COLS,
  PINNED_GRID_MAX_ROWS,
  PINNED_PAGE_TITLE_MAX,
} from "../constants.js";
import type { DeviceCapabilities, ShortcutItem } from "../types.js";

export interface DeviceGridDims {
  cols: number;
  rows: number;
}

export interface ResolvedGridTile {
  index: number;
  item: ShortcutItem;
  page: number;
  col: number;
  row: number;
  colSpan: number;
  rowSpan: number;
  reflowed: boolean;
}

export interface ResolvedTileGridLayout {
  cols: number;
  rows: number;
  tiles: ResolvedGridTile[];
  pageCount: number;
  hasReflow: boolean;
}

function clampInt(val: number, lo: number, hi: number): number {
  if (!Number.isFinite(val)) return lo;
  return Math.max(lo, Math.min(hi, Math.trunc(val)));
}

function isWholeInRange(val: unknown, lo: number, hi: number): val is number {
  return (
    typeof val === "number" &&
    Number.isInteger(val) &&
    val >= lo &&
    val <= hi
  );
}

function normalizeSpan(raw: unknown, maxVal: number): number {
  if (typeof raw !== "number" || !Number.isFinite(raw)) return 1;
  return clampInt(Math.trunc(raw), 1, maxVal);
}

function hasExplicitPlacement(item: ShortcutItem): item is ShortcutItem & {
  page: number;
  col: number;
  row: number;
} {
  return (
    isWholeInRange(item.page, 0, MAX_PINNED_GRID_PAGES - 1) &&
    isWholeInRange(item.col, 0, PINNED_GRID_MAX_COLS - 1) &&
    isWholeInRange(item.row, 0, PINNED_GRID_MAX_ROWS - 1)
  );
}

function rectBitmask(
  col: number,
  row: number,
  colSpan: number,
  rowSpan: number,
  cols: number,
): number {
  let mask = 0;
  for (let r = row; r < row + rowSpan; r += 1) {
    for (let c = col; c < col + colSpan; c += 1) {
      mask |= 1 << (r * cols + c);
    }
  }
  return mask;
}

function rectsOverlap(
  aCol: number,
  aRow: number,
  aW: number,
  aH: number,
  bCol: number,
  bRow: number,
  bW: number,
  bH: number,
): boolean {
  return aCol < bCol + bW && aCol + aW > bCol && aRow < bRow + bH && aRow + aH > bRow;
}

/**
 * Resolve adaptive Pinned grid dimensions (`cols × rows`) from Device capabilities.
 * Prefers explicit `grid_cols`/`grid_rows`, else falls back on display shape & screen width,
 * defaulting to `2 × 3`.
 */
export function resolveDeviceGridDims(caps?: DeviceCapabilities): DeviceGridDims {
  const explicitCols =
    isWholeInRange(caps?.grid_cols, 2, PINNED_GRID_MAX_COLS) ? caps.grid_cols : null;
  const explicitRows =
    isWholeInRange(caps?.grid_rows, 2, PINNED_GRID_MAX_ROWS) ? caps.grid_rows : null;

  if (explicitCols !== null && explicitRows !== null) {
    return { cols: explicitCols, rows: explicitRows };
  }

  let fallbackCols = 2;
  const fallbackRows = 3;
  if (caps?.is_round === true) {
    fallbackCols = 2;
  } else if (typeof caps?.screen_w === "number" && Number.isFinite(caps.screen_w) && caps.screen_w > 0) {
    if (caps.screen_w >= 1000) {
      fallbackCols = 4;
    } else if (caps.screen_w >= 640) {
      fallbackCols = 3;
    } else {
      fallbackCols = 2;
    }
  }

  return {
    cols: explicitCols ?? fallbackCols,
    rows: explicitRows ?? fallbackRows,
  };
}

/**
 * Sanitize an optional per-page Pinned header title (`<= 24` chars, wire-delimiter-safe).
 */
export function sanitizePinnedPageTitle(raw: unknown): string {
  const str = String(raw ?? "");
  let collapsed = "";
  let prevSpace = true;
  for (const ch of str) {
    const code = ch.charCodeAt(0);
    if (
      code < 0x20 ||
      code === 0x7f ||
      ch === "|" ||
      ch === "\x1e" ||
      ch === "\x1f" ||
      ch === " " ||
      ch === "\t" ||
      ch === "\r" ||
      ch === "\n"
    ) {
      if (!prevSpace) {
        collapsed += " ";
        prevSpace = true;
      }
      continue;
    }
    collapsed += ch;
    prevSpace = false;
  }
  const trimmed = collapsed.trim();
  return trimmed.length > PINNED_PAGE_TITLE_MAX
    ? trimmed.slice(0, PINNED_PAGE_TITLE_MAX).trimEnd()
    : trimmed;
}

/**
 * Normalize a sparse `pinned_page_titles` map (`"0".."31"` -> trimmed non-empty title `<= 24` chars).
 */
export function normalizePinnedPageTitles(raw: unknown): Record<string, string> {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return {};
  }
  const out: Record<string, string> = {};
  for (const [key, val] of Object.entries(raw as Record<string, unknown>)) {
    if (!/^(?:0|[1-9]\d?)$/.test(key)) continue;
    const pageNum = Number(key);
    if (!Number.isInteger(pageNum) || pageNum < 0 || pageNum >= MAX_PINNED_GRID_PAGES) {
      continue;
    }
    const clean = sanitizePinnedPageTitle(val);
    if (clean) {
      out[String(pageNum)] = clean;
    }
  }
  return out;
}

/**
 * Return a shallow copy of `item` with explicit `(page, col, row)` and non-default spans
 * (`col_span` / `row_span` omitted when equal to `1`).
 */
export function withExplicitLayout(
  item: ShortcutItem,
  page: number,
  col: number,
  row: number,
  colSpan = 1,
  rowSpan = 1,
): ShortcutItem {
  const copy: ShortcutItem = {
    kind: item.kind,
    target: item.target,
    action: item.action,
    label: item.label,
    icon: item.icon,
    confirm: item.confirm,
    badge_style: item.badge_style ?? "",
    accent: item.accent ?? "",
    page: clampInt(page, 0, MAX_PINNED_GRID_PAGES - 1),
    col: clampInt(col, 0, PINNED_GRID_MAX_COLS - 1),
    row: clampInt(row, 0, PINNED_GRID_MAX_ROWS - 1),
  };
  const cleanCs = clampInt(colSpan, 1, PINNED_GRID_MAX_COLS);
  const cleanRs = clampInt(rowSpan, 1, PINNED_GRID_MAX_ROWS);
  if (cleanCs > 1) {
    copy.col_span = cleanCs;
  }
  if (cleanRs > 1) {
    copy.row_span = cleanRs;
  }
  return copy;
}

/**
 * Deterministic 2-pass bitmask layout solver for Pinned tiles on a `cols × rows` grid.
 */
export function resolveTileGridLayout(
  items: readonly ShortcutItem[],
  rawCols: number,
  rawRows: number,
): ResolvedTileGridLayout {
  const cols = clampInt(rawCols, 2, PINNED_GRID_MAX_COLS);
  const rows = clampInt(rawRows, 1, PINNED_GRID_MAX_ROWS);
  const pageMasks = new Map<number, number>();
  const placed: Array<ResolvedGridTile | null> = new Array(items.length).fill(null);
  const unplaced: number[] = [];

  // Pass 1: honor valid explicit (page, col, row) with clamped spans if in bounds & free.
  for (let i = 0; i < items.length; i += 1) {
    const item = items[i];
    if (!item) continue;
    const storedCs = normalizeSpan(item.col_span, PINNED_GRID_MAX_COLS);
    const storedRs = normalizeSpan(item.row_span, PINNED_GRID_MAX_ROWS);
    const effCs = Math.min(storedCs, cols);
    const effRs = Math.min(storedRs, rows);

    if (hasExplicitPlacement(item)) {
      const { page, col, row } = item;
      const inBounds = col + effCs <= cols && row + effRs <= rows;
      if (inBounds) {
        const mask = rectBitmask(col, row, effCs, effRs, cols);
        const occ = pageMasks.get(page) ?? 0;
        if ((occ & mask) === 0) {
          pageMasks.set(page, occ | mask);
          placed[i] = {
            index: i,
            item,
            page,
            col,
            row,
            colSpan: effCs,
            rowSpan: effRs,
            reflowed: effCs !== storedCs || effRs !== storedRs,
          };
          continue;
        }
      }
    }
    unplaced.push(i);
  }

  // Pass 2: row-major auto-flow for unplaced, out-of-bounds, and colliding items.
  for (const idx of unplaced) {
    const item = items[idx];
    if (!item) continue;
    const hadExplicit = hasExplicitPlacement(item);
    const storedCs = normalizeSpan(item.col_span, PINNED_GRID_MAX_COLS);
    const storedRs = normalizeSpan(item.row_span, PINNED_GRID_MAX_ROWS);
    const effCs = Math.min(storedCs, cols);
    const effRs = Math.min(storedRs, rows);
    const spanClamped = effCs !== storedCs || effRs !== storedRs;

    let done = false;
    for (let p = 0; p < MAX_PINNED_GRID_PAGES && !done; p += 1) {
      const occ = pageMasks.get(p) ?? 0;
      for (let r = 0; r <= rows - effRs && !done; r += 1) {
        for (let c = 0; c <= cols - effCs && !done; c += 1) {
          const mask = rectBitmask(c, r, effCs, effRs, cols);
          if ((occ & mask) === 0) {
            pageMasks.set(p, occ | mask);
            const moved =
              hadExplicit && (p !== item.page || c !== item.col || r !== item.row);
            placed[idx] = {
              index: idx,
              item,
              page: p,
              col: c,
              row: r,
              colSpan: effCs,
              rowSpan: effRs,
              reflowed: moved || spanClamped,
            };
            done = true;
          }
        }
      }
    }

    if (!done) {
      const fallbackPage = MAX_PINNED_GRID_PAGES - 1;
      placed[idx] = {
        index: idx,
        item,
        page: fallbackPage,
        col: 0,
        row: 0,
        colSpan: effCs,
        rowSpan: effRs,
        reflowed: true,
      };
    }
  }

  const tiles = placed.filter((t): t is ResolvedGridTile => t !== null);
  let maxPage = 0;
  let hasReflow = false;
  for (const t of tiles) {
    if (t.page > maxPage) maxPage = t.page;
    if (t.reflowed) hasReflow = true;
  }

  return {
    cols,
    rows,
    tiles,
    pageCount: tiles.length === 0 ? 1 : maxPage + 1,
    hasReflow,
  };
}

/**
 * Return `true` when `(col, row, colSpan, rowSpan)` fits within `cols × rows` on `page`
 * without overlapping any resolved tile other than `excludeIdx`.
 */
export function canPlaceTile(
  resolved: ResolvedTileGridLayout,
  excludeIdx: number,
  page: number,
  col: number,
  row: number,
  colSpan: number,
  rowSpan: number,
  cols: number,
  rows: number,
): boolean {
  if (
    !Number.isInteger(page) ||
    page < 0 ||
    page >= MAX_PINNED_GRID_PAGES ||
    !Number.isInteger(col) ||
    !Number.isInteger(row) ||
    !Number.isInteger(colSpan) ||
    !Number.isInteger(rowSpan) ||
    col < 0 ||
    row < 0 ||
    colSpan < 1 ||
    rowSpan < 1 ||
    col + colSpan > cols ||
    row + rowSpan > rows
  ) {
    return false;
  }
  let occ = 0;
  for (const t of resolved.tiles) {
    if (t.index === excludeIdx || t.page !== page) continue;
    occ |= rectBitmask(t.col, t.row, t.colSpan, t.rowSpan, cols);
  }
  const candMask = rectBitmask(col, row, colSpan, rowSpan, cols);
  return (occ & candMask) === 0;
}

/**
 * Return the largest contiguous horizontal (`maxColSpan`) and vertical (`maxRowSpan`)
 * spans available from `(col, row)` on `page` excluding `excludeIdx`.
 */
export function maxSpanAt(
  resolved: ResolvedTileGridLayout,
  excludeIdx: number,
  page: number,
  col: number,
  row: number,
  cols: number,
  rows: number,
): { maxColSpan: number; maxRowSpan: number } {
  if (!canPlaceTile(resolved, excludeIdx, page, col, row, 1, 1, cols, rows)) {
    return { maxColSpan: 0, maxRowSpan: 0 };
  }
  let maxColSpan = 1;
  for (let w = 2; w <= cols - col; w += 1) {
    if (canPlaceTile(resolved, excludeIdx, page, col, row, w, 1, cols, rows)) {
      maxColSpan = w;
    } else {
      break;
    }
  }
  let maxRowSpan = 1;
  for (let h = 2; h <= rows - row; h += 1) {
    if (canPlaceTile(resolved, excludeIdx, page, col, row, 1, h, cols, rows)) {
      maxRowSpan = h;
    } else {
      break;
    }
  }
  return { maxColSpan, maxRowSpan };
}

function materializeResolvedItems(
  items: readonly ShortcutItem[],
  resolved: ResolvedTileGridLayout,
): ShortcutItem[] {
  const out = items.map((it) => ({ ...it }));
  for (const t of resolved.tiles) {
    const base = out[t.index];
    if (!base) continue;
    out[t.index] = withExplicitLayout(base, t.page, t.col, t.row, t.colSpan, t.rowSpan);
  }
  return out;
}

/**
 * Move tile `itemIdx` to `(targetPage, targetCol, targetRow)` if free, OR swap cleanly with
 * a single blocking tile when that blocker fits into `itemIdx`'s vacated rect.
 * Materializes explicit coordinates on all resolved tiles so unrelated items never jump.
 */
export function moveOrSwapTile(
  items: readonly ShortcutItem[],
  resolved: ResolvedTileGridLayout,
  itemIdx: number,
  targetPage: number,
  targetCol: number,
  targetRow: number,
  cols: number,
  rows: number,
): ShortcutItem[] | null {
  const moving = resolved.tiles.find((t) => t.index === itemIdx);
  if (!moving) return null;
  if (
    !Number.isInteger(targetPage) ||
    targetPage < 0 ||
    targetPage >= MAX_PINNED_GRID_PAGES ||
    !Number.isInteger(targetCol) ||
    !Number.isInteger(targetRow) ||
    targetCol < 0 ||
    targetRow < 0 ||
    targetCol + moving.colSpan > cols ||
    targetRow + moving.rowSpan > rows
  ) {
    return null;
  }
  if (
    targetPage === moving.page &&
    targetCol === moving.col &&
    targetRow === moving.row
  ) {
    return null;
  }

  const blockers = resolved.tiles.filter(
    (t) =>
      t.index !== itemIdx &&
      t.page === targetPage &&
      rectsOverlap(
        targetCol,
        targetRow,
        moving.colSpan,
        moving.rowSpan,
        t.col,
        t.row,
        t.colSpan,
        t.rowSpan,
      ),
  );

  if (blockers.length === 0) {
    const next = materializeResolvedItems(items, resolved);
    const cur = next[itemIdx];
    if (!cur) return null;
    next[itemIdx] = withExplicitLayout(
      cur,
      targetPage,
      targetCol,
      targetRow,
      moving.colSpan,
      moving.rowSpan,
    );
    return next;
  }

  if (blockers.length === 1) {
    const blocker = blockers[0]!;
    // Blocker must fit within grid bounds when placed at moving's vacated origin.
    if (
      moving.col + blocker.colSpan > cols ||
      moving.row + blocker.rowSpan > rows
    ) {
      return null;
    }
    // Moving's destination rect and blocker's swapped rect must not overlap on the same page.
    if (
      moving.page === targetPage &&
      rectsOverlap(
        targetCol,
        targetRow,
        moving.colSpan,
        moving.rowSpan,
        moving.col,
        moving.row,
        blocker.colSpan,
        blocker.rowSpan,
      )
    ) {
      return null;
    }
    // Blocker's swapped rect must not collide with any third tile on moving.page.
    let occOriginPage = 0;
    for (const t of resolved.tiles) {
      if (t.index === itemIdx || t.index === blocker.index || t.page !== moving.page) {
        continue;
      }
      occOriginPage |= rectBitmask(t.col, t.row, t.colSpan, t.rowSpan, cols);
    }
    const blockerNewMask = rectBitmask(
      moving.col,
      moving.row,
      blocker.colSpan,
      blocker.rowSpan,
      cols,
    );
    if ((occOriginPage & blockerNewMask) !== 0) {
      return null;
    }

    const next = materializeResolvedItems(items, resolved);
    const movingBase = next[itemIdx];
    const blockerBase = next[blocker.index];
    if (!movingBase || !blockerBase) return null;
    next[itemIdx] = withExplicitLayout(
      movingBase,
      targetPage,
      targetCol,
      targetRow,
      moving.colSpan,
      moving.rowSpan,
    );
    next[blocker.index] = withExplicitLayout(
      blockerBase,
      moving.page,
      moving.col,
      moving.row,
      blocker.colSpan,
      blocker.rowSpan,
    );
    return next;
  }

  return null;
}

/**
 * Resize tile `itemIdx` to `nextColSpan × nextRowSpan`.
 * Expands in-place when possible; if hitting the right/bottom grid edge, shifts `col`/`row`
 * back to `cols - nextColSpan` / `rows - nextRowSpan` when collision-free; else returns `null`.
 */
export function resizeTile(
  items: readonly ShortcutItem[],
  resolved: ResolvedTileGridLayout,
  itemIdx: number,
  nextColSpan: number,
  nextRowSpan: number,
  cols: number,
  rows: number,
): ShortcutItem[] | null {
  const tile = resolved.tiles.find((t) => t.index === itemIdx);
  if (!tile) return null;
  if (
    !Number.isInteger(nextColSpan) ||
    !Number.isInteger(nextRowSpan) ||
    nextColSpan < 1 ||
    nextColSpan > cols ||
    nextRowSpan < 1 ||
    nextRowSpan > rows
  ) {
    return null;
  }
  if (nextColSpan === tile.colSpan && nextRowSpan === tile.rowSpan) {
    return null;
  }

  let finalCol: number | null = null;
  let finalRow: number | null = null;

  if (
    canPlaceTile(
      resolved,
      itemIdx,
      tile.page,
      tile.col,
      tile.row,
      nextColSpan,
      nextRowSpan,
      cols,
      rows,
    )
  ) {
    finalCol = tile.col;
    finalRow = tile.row;
  } else {
    const shiftedCol = Math.min(tile.col, cols - nextColSpan);
    const shiftedRow = Math.min(tile.row, rows - nextRowSpan);
    if (
      canPlaceTile(
        resolved,
        itemIdx,
        tile.page,
        shiftedCol,
        shiftedRow,
        nextColSpan,
        nextRowSpan,
        cols,
        rows,
      )
    ) {
      finalCol = shiftedCol;
      finalRow = shiftedRow;
    }
  }

  if (finalCol === null || finalRow === null) {
    return null;
  }

  const next = materializeResolvedItems(items, resolved);
  const cur = next[itemIdx];
  if (!cur) return null;
  next[itemIdx] = withExplicitLayout(
    cur,
    tile.page,
    finalCol,
    finalRow,
    nextColSpan,
    nextRowSpan,
  );
  return next;
}

/**
 * Find the first collision-free slot for a `colSpan × rowSpan` tile, starting on `preferredPage`
 * row-major, then scanning subsequent pages before wrapping to earlier pages.
 */
export function findFirstOpenSlot(
  resolved: ResolvedTileGridLayout,
  preferredPage: number,
  colSpan: number,
  rowSpan: number,
  cols: number,
  rows: number,
  excludeIdx = -1,
): { page: number; col: number; row: number } {
  const effCols = clampInt(cols, 2, PINNED_GRID_MAX_COLS);
  const effRows = clampInt(rows, 1, PINNED_GRID_MAX_ROWS);
  const effCs = clampInt(colSpan, 1, effCols);
  const effRs = clampInt(rowSpan, 1, effRows);
  const startPage = clampInt(preferredPage, 0, MAX_PINNED_GRID_PAGES - 1);

  const scanPage = (p: number): { page: number; col: number; row: number } | null => {
    for (let r = 0; r <= effRows - effRs; r += 1) {
      for (let c = 0; c <= effCols - effCs; c += 1) {
        if (canPlaceTile(resolved, excludeIdx, p, c, r, effCs, effRs, effCols, effRows)) {
          return { page: p, col: c, row: r };
        }
      }
    }
    return null;
  };

  for (let p = startPage; p < MAX_PINNED_GRID_PAGES; p += 1) {
    const hit = scanPage(p);
    if (hit) return hit;
  }
  for (let p = 0; p < startPage; p += 1) {
    const hit = scanPage(p);
    if (hit) return hit;
  }
  return {
    page: Math.min(MAX_PINNED_GRID_PAGES - 1, Math.max(0, resolved.pageCount)),
    col: 0,
    row: 0,
  };
}

/**
 * Remove all tiles on `pageIdx`, shift subsequent pages (`page > pageIdx`) down by 1,
 * and shift `pageTitles` keys accordingly.
 */
export function deletePageAndShift(
  items: readonly ShortcutItem[],
  pageTitles: Readonly<Record<string, string>> | undefined,
  pageIdx: number,
  cols: number,
  rows: number,
): { items: ShortcutItem[]; pageTitles: Record<string, string> } {
  const cleanIdx = clampInt(pageIdx, 0, MAX_PINNED_GRID_PAGES - 1);
  const resolved = resolveTileGridLayout(items, cols, rows);

  const nextItems: ShortcutItem[] = [];
  for (const t of resolved.tiles) {
    if (t.page === cleanIdx) continue;
    const nextPage = t.page > cleanIdx ? t.page - 1 : t.page;
    nextItems.push(withExplicitLayout(t.item, nextPage, t.col, t.row, t.colSpan, t.rowSpan));
  }

  const normalizedTitles = normalizePinnedPageTitles(pageTitles);
  const nextTitles: Record<string, string> = {};
  for (const [k, v] of Object.entries(normalizedTitles)) {
    const p = Number(k);
    if (p === cleanIdx) continue;
    const shifted = p > cleanIdx ? p - 1 : p;
    nextTitles[String(shifted)] = v;
  }

  return { items: nextItems, pageTitles: nextTitles };
}

/**
 * Materialize the resolved `(page, col, row, col_span, row_span)` layout onto every item
 * for the active Device's `cols × rows` grid, eliminating cross-device reflow drift.
 */
export function packLayoutToGrid(
  items: readonly ShortcutItem[],
  cols: number,
  rows: number,
): ShortcutItem[] {
  const resolved = resolveTileGridLayout(items, cols, rows);
  return resolved.tiles.map((t) =>
    withExplicitLayout(t.item, t.page, t.col, t.row, t.colSpan, t.rowSpan),
  );
}
