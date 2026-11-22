/**
 * Pure Node TypeScript unit tests for non-destructive photo crop math (`crop-math.ts`),
 * alarm wire codecs (`domain/alarms.ts`), world-clock codecs (`domain/world-clocks.ts`),
 * 7,447-icon MDI catalog parity (`mdi-catalog.ts`), and combobox fuzzy ranking.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  HOME_CATEGORIES_CATALOG,
  NATIVE_DOCK_APP_TOKENS,
  NATIVE_DOCK_CONFIG_APP_MAP,
  START_SCREEN_CONFIG_APP_MAP,
  STUDIO_REV,
  SYSTEM_VIEW_SLUGS,
} from "../../src/constants.js";
import {
  DEFAULT_ALARM_SLOTS,
  formatClockDuration,
  parseAlarmsSummary,
  serializeAlarmsSummary,
} from "../../src/domain/alarms.js";
import {
  fallbackLabelForIana,
  isValidWorldClockZone,
  parseWorldClocksSpec,
  sanitizeClockLabel,
  serializeWorldClocksSpec,
} from "../../src/domain/world-clocks.js";
import {
  CURATED_MDI_ICONS,
  getAllMdiIcons,
  isKnownMdiIcon,
  isMdiCatalogLoaded,
  MDI_TOTAL_ICON_COUNT,
  normalizeMdiIconSlug,
  ROUTE_PREVIEW_ICONS,
  searchMdiIcons,
  shortcutActionLabel,
} from "../../src/mdi-catalog.js";
import { PACKED_MDI_CHUNKS } from "../../src/mdi-chunks.js";
import {
  applyCanvasPanDelta,
  clampNum,
  computeCropSourceRect,
  cropPreviewCanvasSize,
  normalizePhotoCrop,
} from "../../src/utils/crop-math.js";

describe("crop-math, alarms, world-clocks, MDI catalog & combobox ranking", () => {
  it("computes zero-bar focal crop rects and clamps pan deltas across all aspect ratios", () => {
    assert.equal(clampNum(Number.NaN, 1, 3), 1);
    assert.deepEqual(normalizePhotoCrop({ x: -2, y: 5, zoom: 9 }), { x: 0, y: 1, zoom: 3 });
    assert.deepEqual(normalizePhotoCrop(null), { x: 0.5, y: 0.5, zoom: 1 });
    assert.deepEqual(cropPreviewCanvasSize("square"), { width: 260, height: 260 });
    assert.deepEqual(cropPreviewCanvasSize("round"), { width: 260, height: 260 });
    assert.deepEqual(cropPreviewCanvasSize("widescreen"), { width: 320, height: 180 });

    // Wide 1600x900 photo into square 466x466 at zoom 1.0 -> sw=900, sh=900, sx=350, sy=0
    const sq = computeCropSourceRect(1600, 900, 466, 466, { x: 0.5, y: 0.5, zoom: 1 });
    assert.equal(Math.round(sq.sw), 900);
    assert.equal(Math.round(sq.sh), 900);
    assert.equal(Math.round(sq.sx), 350);
    assert.equal(Math.round(sq.sy), 0);

    // Extreme focal points never produce negative offsets or exceed source dimensions
    for (const [srcW, srcH, dstW, dstH] of [
      [1600, 900, 466, 466],
      [900, 1600, 1024, 600],
      [720, 720, 320, 480],
      [0, 0, 260, 260],
    ] as const) {
      for (const fx of [0, 0.25, 0.5, 0.99, 1]) {
        for (const fy of [0, 0.5, 1]) {
          for (const zoom of [1, 1.5, 3]) {
            const r = computeCropSourceRect(srcW, srcH, dstW, dstH, { x: fx, y: fy, zoom });
            const boundW = Math.max(1, srcW);
            const boundH = Math.max(1, srcH);
            assert.ok(r.sx >= 0 && r.sy >= 0);
            assert.ok(r.sw > 0 && r.sh > 0);
            assert.ok(r.sx + r.sw <= boundW + 1e-6);
            assert.ok(r.sy + r.sh <= boundH + 1e-6);
          }
        }
      }
    }

    // Dragging right reveals left side of image (decreases crop.x) and clamps cleanly
    const panned = applyCanvasPanDelta({ x: 0.5, y: 0.5, zoom: 1.5 }, 40, 0, 1600, 900, 260, 260);
    assert.ok(panned.x < 0.5);
    assert.equal(panned.y, 0.5);
    assert.equal(panned.zoom, 1.5);

    // Zero/invalid dimensions fall back to normalized crop without NaN
    const safeZero = applyCanvasPanDelta({ x: 0.4, y: 0.6, zoom: 2 }, 20, 20, 0, 900, 260, 260);
    assert.deepEqual(safeZero, { x: 0.4, y: 0.6, zoom: 2 });
  });

  it("parses and serializes 3-slot alarms and formats timer/stopwatch durations", () => {
    const parsed = parseAlarmsSummary("6:15|1|1;08:30|0|2;23:45|1|0");
    assert.deepEqual(parsed, [
      { time: "06:15", enabled: true, recurrence: 1 },
      { time: "08:30", enabled: false, recurrence: 2 },
      { time: "23:45", enabled: true, recurrence: 0 },
    ]);
    assert.equal(serializeAlarmsSummary(parsed), "06:15|1|1;08:30|0|2;23:45|1|0");

    // Corrupt or out-of-range segments fall back per-slot to DEFAULT_ALARM_SLOTS
    const fallbackParsed = parseAlarmsSummary("25:00|1|1;bad;09:05|1|3");
    assert.deepEqual(fallbackParsed[0], DEFAULT_ALARM_SLOTS[0]);
    assert.deepEqual(fallbackParsed[1], DEFAULT_ALARM_SLOTS[1]);
    assert.deepEqual(fallbackParsed[2], { time: "09:05", enabled: true, recurrence: 3 });

    assert.equal(formatClockDuration(0), "00:00");
    assert.equal(formatClockDuration(-15), "00:00");
    assert.equal(formatClockDuration(125), "02:05");
    assert.equal(formatClockDuration(3661), "01:01:01");
  });

  it("validates IANA world clock zones, strips wire delimiters, and enforces 4-slot cap", () => {
    assert.equal(isValidWorldClockZone("America/Los_Angeles"), true);
    assert.equal(isValidWorldClockZone("Asia/Tokyo"), true);
    assert.equal(isValidWorldClockZone("Etc/GMT+12"), true);
    assert.equal(isValidWorldClockZone("UTC"), false);
    assert.equal(isValidWorldClockZone("Etc/UTC"), false);
    assert.equal(isValidWorldClockZone("Etc/GMT+0"), false);
    assert.equal(isValidWorldClockZone("InvalidZone"), false);

    // Strips |, ;, \x1e, \x1f, newlines, and truncates to 32 UTF-8 bytes
    assert.equal(sanitizeClockLabel("  Harbor|Studio;\x1fWest\nWing  "), "Harbor Studio West Wing");
    assert.equal(Buffer.from(sanitizeClockLabel("東京オフィスビルディング東京オフィスビル"), "utf8").length <= 32, true);
    assert.equal(fallbackLabelForIana("America/New_York"), "New York");

    // Allows distinct labels on the same IANA zone while deduplicating identical label+zone pairs
    const spec = [
      "Tokyo HQ|Asia/Tokyo",
      "tokyo hq|Asia/Tokyo",
      "Kyoto Studio|Asia/Tokyo",
      "Pinned|UTC",
      "London|Europe/London",
      "Sydney|Australia/Sydney",
      "Extra Fifth|America/Chicago",
    ].join(";");
    const clocks = parseWorldClocksSpec(spec);
    assert.equal(clocks.length, 4);
    assert.deepEqual(clocks, [
      { label: "Tokyo HQ", iana: "Asia/Tokyo" },
      { label: "Kyoto Studio", iana: "Asia/Tokyo" },
      { label: "London", iana: "Europe/London" },
      { label: "Sydney", iana: "Australia/Sydney" },
    ]);
    assert.equal(
      serializeWorldClocksSpec(clocks),
      "Tokyo HQ|Asia/Tokyo;Kyoto Studio|Asia/Tokyo;London|Europe/London;Sydney|Australia/Sydney",
    );
  });

  it("maintains 7,447-icon MDI firmware parity, protocol route maps, and STUDIO_REV = 44", () => {
    assert.equal(STUDIO_REV, 44);
    assert.equal(SYSTEM_VIEW_SLUGS.photos, "photos");
    assert.ok(NATIVE_DOCK_APP_TOKENS.includes("app:cameras"));
    assert.ok(NATIVE_DOCK_APP_TOKENS.includes("app:calendar"));
    assert.equal(NATIVE_DOCK_CONFIG_APP_MAP["app:cameras"], "cameras");
    assert.equal(NATIVE_DOCK_CONFIG_APP_MAP["app:weather"], "weather");
    assert.equal(START_SCREEN_CONFIG_APP_MAP.Cameras, "cameras");
    assert.equal(START_SCREEN_CONFIG_APP_MAP.Weather, "weather");

    assert.deepEqual(
      HOME_CATEGORIES_CATALOG.map((c) => c.token),
      ["alarm", "intercom", "thermostat", "entry", "vacuum"],
    );
    const intercomCat = HOME_CATEGORIES_CATALOG.find((c) => c.token === "intercom");
    assert.equal(intercomCat?.label, "Broadcast");
    assert.equal(ROUTE_PREVIEW_ICONS["home_hub:intercom"], "mdi:bullhorn");
    assert.equal(ROUTE_PREVIEW_ICONS["home_hub:cameras"], undefined);
    assert.equal(ROUTE_PREVIEW_ICONS["app:cameras"], "mdi:cctv");

    assert.ok(PACKED_MDI_CHUNKS.length > 0);
    assert.equal(isMdiCatalogLoaded(), true);
    assert.equal(MDI_TOTAL_ICON_COUNT, 7447);
    const allIcons = getAllMdiIcons();
    assert.equal(allIcons.length, MDI_TOTAL_ICON_COUNT);

    for (const curated of CURATED_MDI_ICONS) {
      assert.equal(isKnownMdiIcon(curated), true, `Curated icon missing from pack: ${curated}`);
    }
    for (const [route, icon] of Object.entries(ROUTE_PREVIEW_ICONS)) {
      assert.equal(isKnownMdiIcon(icon), true, `Route ${route} preview icon missing: ${icon}`);
    }

    assert.equal(normalizeMdiIconSlug("mdi-lightbulb_on"), "mdi:lightbulb-on");
    assert.equal(normalizeMdiIconSlug("bullhorn"), "mdi:bullhorn");
    assert.equal(normalizeMdiIconSlug("not valid!!"), "");
    assert.equal(shortcutActionLabel("lock", "unlock"), "Unlock");

    const emptySearch = searchMdiIcons("", 50);
    assert.equal(emptySearch.items.length, 50);
    assert.equal(emptySearch.totalMatches, MDI_TOTAL_ICON_COUNT);

    const bullhornSearch = searchMdiIcons("bullhorn", 20);
    assert.equal(bullhornSearch.items[0], "mdi:bullhorn");
    assert.ok(bullhornSearch.totalMatches >= 2);
  });
});
