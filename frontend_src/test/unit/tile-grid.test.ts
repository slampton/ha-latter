/**
 * Pure Node TypeScript unit tests for the 2D Pinned Tile-Grid Solver (`utils/tile-grid.ts`)
 * and Studio Pinned Visual Grid state operations (`shortcuts-ops.ts`, `EntityController`).
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderPinnedGridEditor } from "../../src/components/dialogs/pinned-grid-editor.js";
import { renderShortcutDialog } from "../../src/components/dialogs/shortcut-modal.js";
import type { ReactiveController, ReactiveControllerHost } from "../../src/lib/lit.js";
import { STUDIO_REV } from "../../src/protocol-schema.js";
import { normalizeShortcutArray } from "../../src/state/shortcuts-ops.js";
import { StudioStore } from "../../src/state/store.js";
import type { HomeAssistant, ShortcutItem, StudioStatePayload } from "../../src/types.js";
import {
  canPlaceTile,
  deletePageAndShift,
  findFirstOpenSlot,
  maxSpanAt,
  moveOrSwapTile,
  normalizePinnedPageTitles,
  packLayoutToGrid,
  resizeTile,
  resolveDeviceGridDims,
  resolveTileGridLayout,
  sanitizePinnedPageTitle,
  withExplicitLayout,
} from "../../src/utils/tile-grid.js";

function makeTile(
  label: string,
  extra: Partial<ShortcutItem> = {},
): ShortcutItem {
  return {
    kind: "entity",
    target: `light.${label.toLowerCase().replace(/[^a-z0-9]+/g, "_")}`,
    action: "toggle",
    label,
    icon: "mdi:lightbulb",
    confirm: false,
    badge_style: "",
    accent: "",
    ...extra,
  };
}

function createPinnedStoreHarness() {
  const controllers = new Set<ReactiveController>();
  const host: ReactiveControllerHost = {
    addController(c) {
      controllers.add(c);
    },
    removeController(c) {
      controllers.delete(c);
    },
    requestUpdate() {},
    updateComplete: Promise.resolve(true),
  };

  const wsLog: Array<Record<string, unknown>> = [];
  const store = new StudioStore(host as ReactiveControllerHost & HTMLElement);
  const hass: HomeAssistant = {
    locale: { language: "en", time_format: "am_pm" },
    config: { unit_system: { length: "mi" } },
    callWS: async <T = unknown>(msg: Record<string, unknown>): Promise<T> => {
      wsLog.push(msg);
      return undefined as T;
    },
  };
  store.setHass(hass);

  const basePayload: StudioStatePayload = {
    type: "state",
    subentry_id: "sub_desk",
    title: "Desk Assistant",
    version: "3.0.0",
    studio_rev: STUDIO_REV,
    system_config_rev: 1,
    device_config_rev: 1,
    internal_logs: [],
    issues: [],
    ble_proxy_count: 0,
    discovered_ble_devices: [],
    system_wallpapers: [],
    esphome: {},
    wallpapers: [],
    system_devices: [
      {
        subentry_id: "sub_desk",
        device_slug: "desk_assistant",
        title: "Desk Assistant",
        model_label: 'Desk Assistant 4.0"',
        area_id: "harbor_studio",
        has_assigned_area: true,
        area_label: "Harbor Studio",
        status_code: "online",
        status_label: "Online",
        is_online: true,
        kind: "device",
        has_display: true,
        has_battery: false,
        has_imu: false,
        is_roaming: false,
        device_group: "wall_panels",
        device_remote_group: "area_auto",
        device_group_name: "Wall & Desk Panels",
        assigned_person: "",
        active_area_name: "Harbor Studio",
        is_latter_native: true,
        battery_level: null,
        is_charging: false,
        is_usb_connected: true,
        wifi_rssi: -50,
        ip_address: "192.168.10.20",
        has_ble: true,
        ble_tracked: false,
        ble_survey_rows: [],
        ble_packets_seen: 0,
        is_current: true,
      },
    ],
    system_controls: [],
    device_groups: [],
    system_config: {} as StudioStatePayload["system_config"],
    catalog: {
      shortcut_entities: [
        {
          id: "light.harbor_lamp",
          name: "Harbor Lamp",
          domain: "light",
          device_class: "",
          icon: "mdi:lamp",
          area_name: "Harbor Studio",
        },
        {
          id: "scene.evening_focus",
          name: "Evening Focus",
          domain: "scene",
          device_class: "",
          icon: "mdi:shimmer",
          area_name: "Harbor Studio",
        },
      ],
    },
    capabilities: {
      has_display: true,
      has_imu: false,
      is_round: false,
      screen_w: 720,
      screen_h: 720,
      grid_cols: 3,
      grid_rows: 3,
    },
    config: {
      device_slug: "desk_assistant",
      kind: "device",
      pinned_items: [],
      pinned_page_titles: {},
    },
    device_prefs: [],
    quick_actions: [],
    live: {},
  };

  store.ingestPayload(basePayload, true);
  store.applyRoute({ prefix: "/latter", path: "devices/sub_desk/interface" });
  return { store, wsLog };
}

describe("2D Pinned Tile-Grid Solver (utils/tile-grid.ts)", () => {
  it("resolves adaptive Device grid dimensions from explicit caps and display trait fallbacks", () => {
    assert.deepEqual(resolveDeviceGridDims(undefined), { cols: 2, rows: 3 });
    assert.deepEqual(resolveDeviceGridDims({ grid_cols: 3, grid_rows: 3 }), { cols: 3, rows: 3 });
    assert.deepEqual(resolveDeviceGridDims({ grid_cols: 4, grid_rows: 3 }), { cols: 4, rows: 3 });
    assert.deepEqual(resolveDeviceGridDims({ grid_cols: 2, grid_rows: 3 }), { cols: 2, rows: 3 });
    // Trait fallbacks when explicit grid_cols/grid_rows absent
    assert.deepEqual(resolveDeviceGridDims({ is_round: true, screen_w: 720 }), { cols: 2, rows: 3 });
    assert.deepEqual(resolveDeviceGridDims({ is_round: false, screen_w: 410 }), { cols: 2, rows: 3 });
    assert.deepEqual(resolveDeviceGridDims({ is_round: false, screen_w: 720 }), { cols: 3, rows: 3 });
    assert.deepEqual(resolveDeviceGridDims({ is_round: false, screen_w: 1280 }), { cols: 4, rows: 3 });
    // Out-of-range explicit values fall back cleanly
    assert.deepEqual(resolveDeviceGridDims({ grid_cols: 9, grid_rows: 0, screen_w: 720 }), {
      cols: 3,
      rows: 3,
    });
  });

  it("sanitizes and normalizes per-page titles safely", () => {
    assert.equal(sanitizePinnedPageTitle("  Harbor  |  Studio \x1e\nLights  "), "Harbor Studio Lights");
    assert.equal(
      sanitizePinnedPageTitle("This Title Is Much Longer Than Twenty Four Characters"),
      "This Title Is Much Longe",
    );
    assert.deepEqual(
      normalizePinnedPageTitles({
        "0": "  Harbor Area  ",
        "1": "   ",
        "2": "Media | Night",
        "32": "Out of range",
        "-1": "Negative",
        "01": "Leading zero ignored",
        abc: "Non numeric",
      }),
      {
        "0": "Harbor Area",
        "2": "Media Night",
      },
    );
  });

  it("runs 2-pass bitmask solver across 2x3, 3x3, and 4x3 grids and flags reflow accurately", () => {
    // 1. Legacy unplaced items auto-flow row-major on 2x3 without flagging reflow
    const legacyItems = [
      makeTile("A"),
      makeTile("B"),
      makeTile("C"),
      makeTile("D"),
      makeTile("E"),
      makeTile("F"),
      makeTile("G"),
    ];
    const r2 = resolveTileGridLayout(legacyItems, 2, 3);
    assert.equal(r2.pageCount, 2);
    assert.equal(r2.hasReflow, false);
    assert.deepEqual(
      r2.tiles.map((t) => [t.item.label, t.page, t.col, t.row, t.colSpan, t.rowSpan]),
      [
        ["A", 0, 0, 0, 1, 1],
        ["B", 0, 1, 0, 1, 1],
        ["C", 0, 0, 1, 1, 1],
        ["D", 0, 1, 1, 1, 1],
        ["E", 0, 0, 2, 1, 1],
        ["F", 0, 1, 2, 1, 1],
        ["G", 1, 0, 0, 1, 1],
      ],
    );

    // 2. Explicit 4x3 layout with a 3x2 hero tile and right-edge tile at col=3
    const wideItems = [
      makeTile("Hero", { page: 0, col: 0, row: 0, col_span: 3, row_span: 2 }),
      makeTile("Side", { page: 0, col: 3, row: 0 }),
      makeTile("Bottom", { page: 0, col: 1, row: 2, col_span: 2 }),
    ];
    const r4 = resolveTileGridLayout(wideItems, 4, 3);
    assert.equal(r4.hasReflow, false);
    assert.equal(r4.pageCount, 1);
    assert.deepEqual(
      r4.tiles.map((t) => [t.item.label, t.col, t.row, t.colSpan, t.rowSpan, t.reflowed]),
      [
        ["Hero", 0, 0, 3, 2, false],
        ["Side", 3, 0, 1, 1, false],
        ["Bottom", 1, 2, 2, 1, false],
      ],
    );

    // 3. Same wideItems rendered on a narrower 2x3 Device: Hero clamps 3x2 -> 2x2 (reflowed),
    //    Side (col=3) and Bottom (col=1, col_span=2) go OOB -> Pass 2 auto-flow & hasReflow=true
    const rReflow = resolveTileGridLayout(wideItems, 2, 3);
    assert.equal(rReflow.hasReflow, true);
    assert.equal(rReflow.tiles[0]?.colSpan, 2);
    assert.equal(rReflow.tiles[0]?.rowSpan, 2);
    assert.equal(rReflow.tiles[0]?.reflowed, true);
    assert.equal(rReflow.tiles[1]?.page, 0);
    assert.equal(rReflow.tiles[1]?.col, 0);
    assert.equal(rReflow.tiles[1]?.row, 2);
    assert.equal(rReflow.tiles[1]?.reflowed, true);
    assert.equal(rReflow.tiles[2]?.page, 1);
    assert.equal(rReflow.tiles[2]?.col, 0);
    assert.equal(rReflow.tiles[2]?.row, 0);
    assert.equal(rReflow.tiles[2]?.colSpan, 2);
    assert.equal(rReflow.tiles[2]?.reflowed, true);

    // 4. Colliding explicit items: first wins Pass 1, second auto-flows in Pass 2
    const colliding = [
      makeTile("First", { page: 0, col: 0, row: 0, col_span: 2 }),
      makeTile("Second", { page: 0, col: 1, row: 0 }),
    ];
    const rCol = resolveTileGridLayout(colliding, 3, 3);
    assert.equal(rCol.hasReflow, true);
    assert.deepEqual(
      rCol.tiles.map((t) => [t.item.label, t.col, t.row, t.reflowed]),
      [
        ["First", 0, 0, false],
        ["Second", 2, 0, true],
      ],
    );
  });

  it("checks placement collisions and computes max contiguous spans", () => {
    const items = [
      makeTile("A", { page: 0, col: 0, row: 0 }),
      makeTile("B", { page: 0, col: 2, row: 0 }),
      makeTile("C", { page: 0, col: 0, row: 2 }),
    ];
    const resolved = resolveTileGridLayout(items, 3, 3);

    assert.equal(canPlaceTile(resolved, -1, 0, 1, 0, 1, 1, 3, 3), true);
    assert.equal(canPlaceTile(resolved, -1, 0, 1, 0, 2, 1, 3, 3), false); // hits B
    assert.equal(canPlaceTile(resolved, 0, 0, 0, 0, 2, 2, 3, 3), true); // excluding A
    assert.equal(canPlaceTile(resolved, 0, 0, 0, 0, 3, 1, 3, 3), false); // hits B
    assert.equal(canPlaceTile(resolved, -1, 0, 2, 2, 2, 1, 3, 3), false); // OOB

    assert.deepEqual(maxSpanAt(resolved, 0, 0, 0, 0, 3, 3), { maxColSpan: 2, maxRowSpan: 2 });
    assert.deepEqual(maxSpanAt(resolved, -1, 0, 0, 0, 3, 3), { maxColSpan: 0, maxRowSpan: 0 });
    assert.deepEqual(maxSpanAt(resolved, -1, 0, 1, 1, 3, 3), { maxColSpan: 2, maxRowSpan: 2 });
  });

  it("moves tiles to open slots, swaps cleanly with single blockers, and rejects multi-blocker or overlapping swaps", () => {
    const items = [
      makeTile("One", { page: 0, col: 0, row: 0 }),
      makeTile("Two", { page: 0, col: 1, row: 0 }),
      makeTile("Wide", { page: 0, col: 0, row: 1, col_span: 2 }),
      makeTile("Side", { page: 0, col: 2, row: 1 }),
    ];
    const resolved = resolveTileGridLayout(items, 3, 3);

    // Move to empty cell
    const moved = moveOrSwapTile(items, resolved, 0, 0, 2, 2, 3, 3);
    assert.ok(moved);
    assert.equal(moved[0]?.col, 2);
    assert.equal(moved[0]?.row, 2);

    // Same-size swap (One <-> Two)
    const swapped = moveOrSwapTile(items, resolved, 0, 0, 1, 0, 3, 3);
    assert.ok(swapped);
    assert.equal(swapped[0]?.col, 1);
    assert.equal(swapped[0]?.row, 0);
    assert.equal(swapped[1]?.col, 0);
    assert.equal(swapped[1]?.row, 0);

    // Asymmetric swap: move Wide (2x1 at 0,1) onto One (1x1 at 0,0) when Two is ALSO blocking (1,0) -> 2 blockers => rejected
    assert.equal(moveOrSwapTile(items, resolved, 2, 0, 0, 0, 3, 3), null);

    // Asymmetric swap with single blocker: move Side (1x1 at 2,1) onto One (1x1 at 0,0) succeeds
    const crossSwap = moveOrSwapTile(items, resolved, 3, 0, 0, 0, 3, 3);
    assert.ok(crossSwap);
    assert.equal(crossSwap[3]?.col, 0);
    assert.equal(crossSwap[3]?.row, 0);
    assert.equal(crossSwap[0]?.col, 2);
    assert.equal(crossSwap[0]?.row, 1);

    // Blocker too wide for vacated spot: Wide (2x1 at 0,1) cannot fit at Side's vacated col=2 on 3-col grid
    assert.equal(moveOrSwapTile(items, resolved, 3, 0, 1, 1, 3, 3), null);

    // Cross-page move
    const nextPageMove = moveOrSwapTile(items, resolved, 2, 1, 0, 0, 3, 3);
    assert.ok(nextPageMove);
    assert.equal(nextPageMove[2]?.page, 1);
    assert.equal(nextPageMove[2]?.col, 0);
    assert.equal(nextPageMove[2]?.row, 0);
    assert.equal(nextPageMove[2]?.col_span, 2);
  });

  it("resizes tiles in-place, shifts back from right/bottom edges when free, and rejects blocked resizes", () => {
    const items = [
      makeTile("Corner", { page: 0, col: 2, row: 2 }),
      makeTile("Blocker", { page: 0, col: 0, row: 1 }),
    ];
    const resolved = resolveTileGridLayout(items, 3, 3);

    // Corner at (2,2) expanding to 2x2 shifts back cleanly to (1,1)
    const shifted = resizeTile(items, resolved, 0, 2, 2, 3, 3);
    assert.ok(shifted);
    assert.equal(shifted[0]?.col, 1);
    assert.equal(shifted[0]?.row, 1);
    assert.equal(shifted[0]?.col_span, 2);
    assert.equal(shifted[0]?.row_span, 2);

    // Corner expanding to 3x2 would hit Blocker at (0,1) -> rejected
    assert.equal(resizeTile(items, resolved, 0, 3, 2, 3, 3), null);

    // Blocker at (0,1) expanding in-place to 2x1 succeeds without moving origin
    const inPlace = resizeTile(items, resolved, 1, 2, 1, 3, 3);
    assert.ok(inPlace);
    assert.equal(inPlace[1]?.col, 0);
    assert.equal(inPlace[1]?.row, 1);
    assert.equal(inPlace[1]?.col_span, 2);
    assert.equal(inPlace[1]?.row_span, undefined);

    // Shrinking back to 1x1 strips col_span/row_span cleanly
    const shrunkResolved = resolveTileGridLayout(shifted, 3, 3);
    const shrunk = resizeTile(shifted, shrunkResolved, 0, 1, 1, 3, 3);
    assert.ok(shrunk);
    assert.equal(shrunk[0]?.col_span, undefined);
    assert.equal(shrunk[0]?.row_span, undefined);
  });

  it("finds first open slot, deletes pages with clean title/page shifting, and packs reflowed layouts", () => {
    const items = [
      makeTile("P0A", { page: 0, col: 0, row: 0, col_span: 2, row_span: 2 }),
      makeTile("P1A", { page: 1, col: 0, row: 0 }),
      makeTile("P2A", { page: 2, col: 1, row: 1 }),
    ];
    const resolved = resolveTileGridLayout(items, 2, 3);

    // Page 0 has (0,2) and (1,2) open -> 2x1 fits at (0,2), 2x2 overflows to page 1 (0,1)
    assert.deepEqual(findFirstOpenSlot(resolved, 0, 2, 1, 2, 3), { page: 0, col: 0, row: 2 });
    assert.deepEqual(findFirstOpenSlot(resolved, 0, 2, 2, 2, 3), { page: 1, col: 0, row: 1 });

    // Deleting page 1 drops P1A and shifts P2A + page titles down by 1
    const afterDelete = deletePageAndShift(
      items,
      { "0": "Main", "1": "Temp", "2": "Media" },
      1,
      2,
      3,
    );
    assert.deepEqual(
      afterDelete.items.map((it) => [it.label, it.page, it.col, it.row]),
      [
        ["P0A", 0, 0, 0],
        ["P2A", 1, 1, 1],
      ],
    );
    assert.deepEqual(afterDelete.pageTitles, { "0": "Main", "1": "Media" });

    // Packing a reflowed 3x3 layout onto a 2x3 grid eliminates hasReflow
    const wide = [
      makeTile("Hero", { page: 0, col: 0, row: 0, col_span: 3 }),
      makeTile("Right", { page: 0, col: 2, row: 1 }),
    ];
    assert.equal(resolveTileGridLayout(wide, 2, 3).hasReflow, true);
    const packed = packLayoutToGrid(wide, 2, 3);
    assert.equal(resolveTileGridLayout(packed, 2, 3).hasReflow, false);
    assert.equal(packed[0]?.col_span, 2);
    assert.equal(packed[1]?.col, 0);
    assert.equal(packed[1]?.row, 1);

    // withExplicitLayout strips span=1
    const explicit = withExplicitLayout(makeTile("Solo"), 1, 2, 0, 1, 1);
    assert.equal(explicit.page, 1);
    assert.equal(explicit.col, 2);
    assert.equal(explicit.row, 0);
    assert.equal("col_span" in explicit, false);
    assert.equal("row_span" in explicit, false);
  });

  it("preserves layout fields on pinned_items while stripping them from dock_items", () => {
    const raw = [
      makeTile("Scene", { page: 1, col: 2, row: 0, col_span: 2, row_span: 1 }),
    ];
    const pinnedNorm = normalizeShortcutArray(raw, false);
    assert.equal(pinnedNorm[0]?.page, 1);
    assert.equal(pinnedNorm[0]?.col, 2);
    assert.equal(pinnedNorm[0]?.row, 0);
    assert.equal(pinnedNorm[0]?.col_span, 2);
    assert.equal("row_span" in (pinnedNorm[0] ?? {}), false);

    const dockNorm = normalizeShortcutArray(raw, true);
    assert.equal("page" in (dockNorm[0] ?? {}), false);
    assert.equal("col" in (dockNorm[0] ?? {}), false);
    assert.equal("row" in (dockNorm[0] ?? {}), false);
    assert.equal("col_span" in (dockNorm[0] ?? {}), false);
    assert.equal("row_span" in (dockNorm[0] ?? {}), false);
  });
});

describe("Studio Pinned Grid Controller Operations (shortcuts-ops.ts)", () => {
  it("places targeted cell tiles with multi-span, saves page titles, deletes pages, and renders Lit templates cleanly", async () => {
    const { store, wsLog } = createPinnedStoreHarness();

    // Click empty cell (page=0, col=1, row=1) -> save 2x1 tile
    store.entity.openShortcutModal("pinned_items", null, { page: 0, col: 1, row: 1 });
    assert.equal(store.shortcutModal.tilePage, 0);
    assert.equal(store.shortcutModal.tileCol, 1);
    assert.equal(store.shortcutModal.tileRow, 1);
    assert.equal(store.shortcutModal.tileColSpan, 1);
    assert.equal(store.shortcutModal.tileRowSpan, 1);

    store.shortcutModal = {
      ...store.shortcutModal,
      kind: "entity",
      entityTarget: "light.harbor_lamp",
      action: "toggle",
      label: "Harbor Lamp",
      icon: "mdi:lamp",
      tileColSpan: 2,
      tileRowSpan: 1,
    };
    store.entity.saveShortcutModal();
    await store.entity.flushDeviceBucket("sub_desk");

    const savedCfg1 = (wsLog.at(-1)?.payload as Record<string, unknown>)?.config as Record<
      string,
      unknown
    >;
    const savedPinned1 = savedCfg1?.pinned_items as ShortcutItem[];
    assert.equal(savedPinned1.length, 1);
    assert.equal(savedPinned1[0]?.page, 0);
    assert.equal(savedPinned1[0]?.col, 1);
    assert.equal(savedPinned1[0]?.row, 1);
    assert.equal(savedPinned1[0]?.col_span, 2);
    assert.equal("row_span" in (savedPinned1[0] ?? {}), false);

    // Add a custom page title for page 0 and page 1
    store.entity.savePinnedPageTitles({ "0": "Harbor Controls", "1": "Night Scenes" });
    await store.entity.flushDeviceBucket("sub_desk");
    assert.deepEqual(store.entity.getPinnedPageTitles(), {
      "0": "Harbor Controls",
      "1": "Night Scenes",
    });

    // Add a tile directly onto page 1
    store.pinnedExtraPages = 1;
    store.entity.openShortcutModal("pinned_items", null, { page: 1, col: 0, row: 0 });
    store.shortcutModal = {
      ...store.shortcutModal,
      kind: "entity",
      entityTarget: "scene.evening_focus",
      action: "turn_on",
      label: "Evening Focus",
      icon: "mdi:shimmer",
    };
    store.entity.saveShortcutModal();
    await store.entity.flushDeviceBucket("sub_desk");
    assert.equal(store.pinnedActivePage, 1);
    assert.equal(store.pinnedExtraPages, 0);

    // Smoke-render Visual Grid Editor & Shortcut Modal templates without throwing
    assert.ok(renderPinnedGridEditor(store));
    store.entity.openShortcutModal("pinned_items", 0);
    assert.ok(renderShortcutDialog(store));
    store.entity.closeShortcutModal();

    // Delete page 0 -> page 1 shifts down to page 0 along with its custom title
    store.entity.deletePinnedPage(0);
    await store.entity.flushDeviceBucket("sub_desk");
    assert.deepEqual(store.entity.getPinnedPageTitles(), { "0": "Night Scenes" });
    const remaining = store.entity.getPinnedItems();
    assert.equal(remaining.length, 1);
    assert.equal(remaining[0]?.label, "Evening Focus");
    assert.equal(remaining[0]?.page, 0);
  });
});
