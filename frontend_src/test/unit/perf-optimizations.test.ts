/**
 * Pure Node TypeScript unit tests for Phase 3 Latter Studio frontend performance optimizations:
 * - `subscription.ts` gated section retention & compact 4 Hz `ble_survey_delta`
 * - `photo-upload-modal.ts` / `photo-ops.ts` / `store.ts` bounded downscaling & bitmap eviction
 * - `pinned-grid-editor.ts` discrete drag-update guard
 * - `shortcut-modal.ts` entity option memoization & 120 ms MDI search debounce
 * - `combobox.ts` closed-state lazy listbox rendering
 * - `devices-discovered-view.ts` stable repeat keys & BLE pagination cap
 * - `system-presence-view.ts` lazy `<details>` drawers & `available_sensors` fallback
 * - `build.mjs` safe `html`/`css` template-literal whitespace minifier
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderEntityCombobox } from "../../src/components/controls/combobox.js";
import {
  clearLoadedPhotoImages,
  computeBoundedPreviewDims,
  evictLoadedPhotoImage,
  getLoadedPhotoImageCacheSize,
  getOrLoadPhotoPreview,
  MAX_PREVIEW_EDGE_PX,
} from "../../src/components/dialogs/photo-upload-modal.js";
import { shouldRequestGridDragUpdate } from "../../src/components/dialogs/pinned-grid-editor.js";
import {
  cancelShortcutIconSearchDebounce,
  clearShortcutEntityOptionsCache,
  getMemoizedShortcutEntityOptions,
  scheduleShortcutIconSearchDebounce,
  type ShortcutEntityCatalogEntry,
} from "../../src/components/dialogs/shortcut-modal.js";
import {
  nothing,
  type ReactiveController,
  type ReactiveControllerHost,
  type TemplateResult,
} from "../../src/lib/lit.js";
import { STUDIO_REV } from "../../src/protocol-schema.js";
import { StudioStore } from "../../src/state/store.js";
import type {
  AreaPresenceRow,
  BleAreaSignatureSummary,
  DiscoveredBleCandidate,
  HomeAssistant,
  StudioStatePayload,
} from "../../src/types.js";
import {
  DISCOVERED_BLE_PAGE_SIZE,
  discoveredBleCandidateKey,
  discoveredLatterDeviceKey,
  renderDevicesDiscoveredView,
} from "../../src/views/devices-discovered-view.js";
import { renderSystemPresenceView } from "../../src/views/system-presence-view.js";

function flattenTemplateStrings(value: unknown): string {
  if (value === null || value === undefined || value === nothing) return "";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map(flattenTemplateStrings).join("");
  }
  if (typeof value === "object") {
    const rec = value as Record<string, unknown>;
    if (Array.isArray(rec.strings) && Array.isArray(rec.values)) {
      const strs = rec.strings as readonly string[];
      const vals = rec.values as readonly unknown[];
      let out = "";
      for (let i = 0; i < strs.length; i += 1) {
        out += strs[i] ?? "";
        if (i < vals.length) out += flattenTemplateStrings(vals[i]);
      }
      return out;
    }
    if (Array.isArray(rec.values)) {
      if ("_$litDirective$" in rec) {
        const vals = rec.values as readonly unknown[];
        // Lit `guard(deps, valueFn)` directive
        if (vals.length === 2 && Array.isArray(vals[0]) && typeof vals[1] === "function") {
          return flattenTemplateStrings((vals[1] as () => unknown)());
        }
        // Lit `repeat(items, keyFn, itemTemplate)` directive
        if (
          vals.length === 3 &&
          Array.isArray(vals[0]) &&
          typeof vals[2] === "function"
        ) {
          const itemTpl = vals[2] as (item: unknown, idx: number) => unknown;
          return vals[0].map((item, idx) => flattenTemplateStrings(itemTpl(item, idx))).join("");
        }
      }
      return flattenTemplateStrings(rec.values);
    }
  }
  return "";
}

function createHarness(initialPayload?: Partial<StudioStatePayload>): {
  store: StudioStore;
  updateCount: () => number;
  resetUpdates: () => void;
} {
  let updates = 0;
  const controllers = new Set<ReactiveController>();
  const host: ReactiveControllerHost & { isConnected: boolean } = {
    isConnected: true,
    addController(c) {
      controllers.add(c);
    },
    removeController(c) {
      controllers.delete(c);
    },
    requestUpdate() {
      updates += 1;
    },
    updateComplete: Promise.resolve(true),
  };

  const store = new StudioStore(host as unknown as ReactiveControllerHost & HTMLElement);
  const hass: HomeAssistant = {
    locale: { language: "en", time_format: "am_pm" },
    config: { unit_system: { length: "km" }, time_zone: "UTC", version: "2026.11.2" },
    themes: { darkMode: false },
    states: {},
    connection: {
      subscribeMessage: async () => () => {},
    },
    callWS: async <T = unknown>() => structuredClone(store.state) as T,
  };
  store.setHass(hass);

  const areaPresence: AreaPresenceRow[] = [
    {
      area_id: "kitchen",
      area_name: "Kitchen",
      is_occupied: true,
      confidence_pct: 92,
      occupant_names: ["Alex"],
      available_sensors: ["binary_sensor.kitchen_motion", "binary_sensor.kitchen_mmwave"],
      fusion_mode: "weighted",
      fusion_threshold_pct: 50,
      fusion_sensors: ["binary_sensor.kitchen_motion"],
    },
  ];
  const bleSigs: BleAreaSignatureSummary[] = [
    {
      area_id: "kitchen",
      area_name: "Kitchen",
      has_ble_proxy: true,
      has_signature: true,
      scanner_count: 2,
      sample_count: 20,
      captured_at: "2026-11-24T12:00:00Z",
    },
  ];

  const basePayload: StudioStatePayload = {
    subentry_id: "sub_desk",
    title: "Desk Assistant",
    version: "3.0.0",
    studio_rev: STUDIO_REV,
    system_config_rev: 4,
    device_config_rev: 8,
    locale_strings: { "action.cancel": "Annuler" },
    internal_logs: [],
    system_devices: [
      {
        subentry_id: "sub_desk",
        device_slug: "desk_assistant",
        title: "Desk Assistant",
        model_label: "Desk Assistant",
        area_id: "kitchen",
        has_assigned_area: true,
        area_label: "Kitchen",
        status_code: "online",
        status_label: "Online",
        is_online: true,
        kind: "device",
        has_display: true,
        has_battery: false,
        has_imu: false,
        hw_jpeg: true,
        is_roaming: false,
        device_group: "wall_panels",
        device_remote_group: "area_auto",
        device_group_name: "Wall & Desk Panels",
        assigned_person: "",
        active_area_name: "Kitchen",
        is_latter_native: true,
        battery_level: null,
        is_charging: false,
        is_usb_connected: true,
        wifi_rssi: -48,
        ip_address: "192.168.1.24",
        has_ble: true,
        ble_tracked: true,
        ble_survey_rows: [
          {
            scanner_source: "proxy_kitchen",
            scanner_name: "Kitchen Proxy",
            area_id: "kitchen",
            area_name: "Kitchen",
            raw_rssi: -52,
            offset_db: 0,
            effective_rssi: -52,
            distance_m: 1.4,
            age_seconds: 1,
            is_fresh: true,
            is_winner: true,
          },
        ],
        ble_packets_seen: 10,
        is_current: true,
      },
      {
        subentry_id: "sub_pocket",
        device_slug: "pocket_assistant",
        title: "Pocket Assistant",
        model_label: "Pocket Assistant",
        area_id: "kitchen",
        has_assigned_area: false,
        area_label: "Kitchen",
        status_code: "online",
        status_label: "Online",
        is_online: true,
        kind: "device",
        has_display: true,
        has_battery: true,
        has_imu: true,
        hw_jpeg: false,
        is_roaming: true,
        device_group: "pocket_carry",
        device_remote_group: "area_auto",
        device_group_name: "Pocket Carry",
        assigned_person: "",
        active_area_name: "Kitchen",
        is_latter_native: true,
        battery_level: 88,
        is_charging: false,
        is_usb_connected: false,
        wifi_rssi: -61,
        ip_address: "192.168.1.31",
        has_ble: true,
        ble_tracked: true,
        ble_survey_rows: [],
        ble_packets_seen: 0,
        is_current: false,
      },
    ],
    issues: [],
    ble_proxy_count: 1,
    ble_area_signatures: bleSigs,
    discovered_latter_devices: [
      {
        esphome_device_id: "esp_entry",
        node_name: "latter_entry",
        title: "Entry Panel",
        model_label: "Wall Panel",
        area_name: "Entryway",
        default_group: "wall_panels",
      },
    ],
    ignored_latter_devices: [
      {
        esphome_device_id: "esp_bench",
        node_name: "latter_bench",
        title: "Bench Node",
        model_label: "Bench Node",
        area_name: "Office",
        default_group: "wall_panels",
      },
    ],
    discovered_ble_devices: [],
    system_controls: [
      {
        key: "do_not_disturb",
        pref_key: "do_not_disturb",
        section: "power",
        section_title: "Power",
        name: "Do not disturb",
        domain: "switch",
        state: "off",
        targets: [],
      },
    ],
    device_groups: [],
    system_config: {
      weather_entity: "",
      alarm_entity: "",
      thermostat_entities: [],
      lock_entities: [],
      garage_entities: [],
      vacuum_entities: [],
      broadcast_speakers: [],
      broadcast_phrases: [],
      camera_entities: [],
      remotes_list: [],
      remote_groups: [],
      volume_overrides: [],
      calendar_entities: [],
      custom_palettes: [],
      doorbell_noise_reduction: "strong",
    },
    photo_collections: [],
    system_wallpapers: [],
    capabilities: { has_display: true, grid_cols: 3, grid_rows: 3 },
    config: { kind: "device" },
    device_prefs: [],
    esphome: { device: {}, sections: [] },
    wallpapers: [{ id: "photo:desk_1", name: "Desk Sunset", kind: "uploaded" }],
    live: { area_presence_grid: areaPresence },
    ...initialPayload,
  };

  store.deviceSelected = true;
  store.activeSubentryId = "sub_desk";
  store.ingestPayload(basePayload, false);
  updates = 0;

  return {
    store,
    updateCount: () => updates,
    resetUpdates: () => {
      updates = 0;
    },
  };
}

describe("Phase 3 Latter Studio frontend performance optimizations", () => {
  it("retains backend-gated sections across incremental state frames and handles compact 4 Hz ble_survey_delta", () => {
    const { store, updateCount, resetUpdates } = createHarness();

    // 1. Incremental state push for same Device omits all 5 newly gated sections
    const compactSameDevice = {
      ...structuredClone(store.state!),
      locale_strings: undefined,
      system_controls: undefined,
      discovered_latter_devices: undefined,
      ignored_latter_devices: undefined,
      wallpapers: undefined,
    } as unknown as StudioStatePayload;
    store.ingestPayload(compactSameDevice, false);

    assert.deepEqual(store.state?.locale_strings, { "action.cancel": "Annuler" });
    assert.equal(store.state?.system_controls.length, 1);
    assert.equal(store.state?.discovered_latter_devices?.[0]?.esphome_device_id, "esp_entry");
    assert.equal(store.state?.ignored_latter_devices?.[0]?.esphome_device_id, "esp_bench");
    assert.equal(store.state?.wallpapers[0]?.id, "photo:desk_1");

    // 2. Mismatched Device push keeps active Device wallpapers AND system-wide gated sections
    const mismatchedPush = {
      ...structuredClone(store.state!),
      subentry_id: "sub_pocket",
      locale_strings: undefined,
      system_controls: undefined,
      discovered_latter_devices: undefined,
      ignored_latter_devices: undefined,
      wallpapers: undefined,
    } as unknown as StudioStatePayload;
    store.ingestPayload(mismatchedPush, false);

    assert.equal(store.state?.subentry_id, "sub_desk");
    assert.equal(store.state?.wallpapers[0]?.id, "photo:desk_1");
    assert.equal(store.state?.system_controls.length, 1);
    assert.equal(store.state?.discovered_latter_devices?.[0]?.esphome_device_id, "esp_entry");
    assert.equal(store.state?.ignored_latter_devices?.[0]?.esphome_device_id, "esp_bench");

    // 3. Switching active Device to sub_pocket with omitted wallpapers does NOT leak sub_desk wallpapers
    store.activeSubentryId = "sub_pocket";
    const switchedPush = {
      ...structuredClone(store.state!),
      subentry_id: "sub_pocket",
      wallpapers: undefined,
      locale_strings: undefined,
      system_controls: undefined,
      discovered_latter_devices: undefined,
      ignored_latter_devices: undefined,
    } as unknown as StudioStatePayload;
    store.ingestPayload(switchedPush, false);

    assert.equal(store.state?.subentry_id, "sub_pocket");
    assert.deepEqual(store.state?.wallpapers, []);
    assert.deepEqual(store.state?.locale_strings, { "action.cancel": "Annuler" });
    assert.equal(store.state?.system_controls.length, 1);

    // 4. Compact 4 Hz ble_survey_delta omits area_presence_grid and ble_area_signatures cleanly
    const preDeltaPresenceGrid = store.state?.live.area_presence_grid;
    const preDeltaSignatures = store.state?.ble_area_signatures;
    store.bleSurveySubentryId = "sub_desk";
    store.bleLiveStreamActive = true;
    resetUpdates();
    store.applyBleSurveyDelta({
      type: "ble_survey_delta",
      subentry_id: "sub_desk",
      ble_packets_seen: 42,
      ble_survey_rows: [
        {
          scanner_source: "proxy_kitchen",
          scanner_name: "Kitchen Proxy",
          area_id: "kitchen",
          area_name: "Kitchen",
          raw_rssi: -46,
          offset_db: 0,
          effective_rssi: -46,
          distance_m: 0.9,
          age_seconds: 0,
          is_fresh: true,
          is_winner: true,
        },
      ],
    });

    assert.equal(updateCount(), 1);
    const deskDev = store.state?.system_devices.find((d) => d.subentry_id === "sub_desk");
    assert.equal(deskDev?.ble_packets_seen, 42);
    assert.equal(deskDev?.ble_survey_rows[0]?.effective_rssi, -46);
    assert.equal(store.state?.live.area_presence_grid, preDeltaPresenceGrid);
    assert.equal(store.state?.ble_area_signatures, preDeltaSignatures);

    // 5. Paused BLE stream ignores compact delta with zero redundant host updates
    store.bleLiveStreamActive = false;
    resetUpdates();
    store.applyBleSurveyDelta({
      type: "ble_survey_delta",
      subentry_id: "sub_desk",
      ble_packets_seen: 99,
      ble_survey_rows: [],
    });
    assert.equal(updateCount(), 0);
  });

  it("downscales high-res crop previews to <= 1024 px and evicts bitmaps on revoke and hostDisconnected()", async () => {
    assert.deepEqual(computeBoundedPreviewDims(800, 600), {
      width: 800,
      height: 600,
      downscaled: false,
    });
    assert.deepEqual(computeBoundedPreviewDims(4032, 3024, MAX_PREVIEW_EDGE_PX), {
      width: 1024,
      height: 768,
      downscaled: true,
    });
    assert.deepEqual(computeBoundedPreviewDims(3000, 6000, MAX_PREVIEW_EDGE_PX), {
      width: 512,
      height: 1024,
      downscaled: true,
    });

    const origImage = globalThis.Image;
    const origCreateBitmap = globalThis.createImageBitmap;
    const origCreateObjectUrl = URL.createObjectURL;
    const origRevokeObjectUrl = URL.revokeObjectURL;

    const createdImgs: Array<{
      src: string;
      naturalWidth: number;
      naturalHeight: number;
      complete: boolean;
      onload: (() => void) | null;
      onerror: (() => void) | null;
      crossOrigin: string;
      decoding: string;
    }> = [];
    const createdBitmaps: Array<{ width: number; height: number; closed: boolean; close(): void }> =
      [];
    const revokedUrls: string[] = [];
    let urlSeq = 0;

    class MockImage {
      crossOrigin = "";
      decoding = "";
      naturalWidth = 4032;
      naturalHeight = 3024;
      complete = false;
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      private _src = "";

      constructor() {
        createdImgs.push(this);
      }

      get src(): string {
        return this._src;
      }

      set src(val: string) {
        this._src = val;
        if (val) {
          this.complete = true;
          this.onload?.();
        }
      }
    }

    try {
      clearLoadedPhotoImages();
      (globalThis as unknown as { Image: typeof MockImage }).Image = MockImage;
      (globalThis as unknown as { createImageBitmap: unknown }).createImageBitmap = async (
        _img: unknown,
        opts?: { resizeWidth?: number; resizeHeight?: number },
      ) => {
        const bm = {
          width: opts?.resizeWidth ?? 1024,
          height: opts?.resizeHeight ?? 768,
          closed: false,
          close() {
            this.closed = true;
          },
        };
        createdBitmaps.push(bm);
        return bm;
      };
      URL.createObjectURL = () => `blob:test-photo-${++urlSeq}`;
      URL.revokeObjectURL = (u: string) => {
        revokedUrls.push(u);
      };

      const { store } = createHarness();
      const f1 = new File([new Uint8Array(16)], "phone_48mp_a.jpg", { type: "image/jpeg" });
      const f2 = new File([new Uint8Array(16)], "phone_48mp_b.jpg", { type: "image/jpeg" });
      store.entity.stageUploadFiles([f1, f2]);
      assert.equal(store.photoUploadModal.files.length, 2);

      const url1 = store.photoUploadModal.files[0]!.objectUrl;
      const url2 = store.photoUploadModal.files[1]!.objectUrl;

      let loadEvents = 0;
      getOrLoadPhotoPreview(url1, () => {
        loadEvents += 1;
      });
      getOrLoadPhotoPreview(url2, () => {
        loadEvents += 1;
      });
      await new Promise((r) => setTimeout(r, 10));

      assert.equal(loadEvents, 2);
      assert.equal(getLoadedPhotoImageCacheSize(), 2);
      assert.equal(createdBitmaps.length, 2);
      assert.equal(createdBitmaps[0]?.width, 1024);
      assert.equal(createdBitmaps[0]?.height, 768);
      // Full-res HTMLImageElement src must have been cleared right after bitmap downscale!
      assert.equal(createdImgs[0]?.src, "");
      assert.equal(createdImgs[1]?.src, "");

      // Removing staged photo #0 revokes blob URL and closes its ImageBitmap
      store.entity.removeStagedUpload(0);
      assert.deepEqual(revokedUrls, [url1]);
      assert.equal(createdBitmaps[0]?.closed, true);
      assert.equal(createdBitmaps[1]?.closed, false);
      assert.equal(getLoadedPhotoImageCacheSize(), 1);

      // hostDisconnected() revokes remaining staged blob URLs and clears cache
      store.hostDisconnected();
      assert.deepEqual(revokedUrls, [url1, url2]);
      assert.equal(createdBitmaps[1]?.closed, true);
      assert.equal(getLoadedPhotoImageCacheSize(), 0);
      assert.equal(store.photoUploadModal.files.length, 0);

      // Direct eviction helper handles missing URLs safely
      evictLoadedPhotoImage("blob:nonexistent");
      assert.equal(getLoadedPhotoImageCacheSize(), 0);
    } finally {
      clearLoadedPhotoImages();
      globalThis.Image = origImage;
      globalThis.createImageBitmap = origCreateBitmap;
      URL.createObjectURL = origCreateObjectUrl;
      URL.revokeObjectURL = origRevokeObjectUrl;
    }
  });

  it("gates pinned grid drag re-renders strictly on activation or target/validity transitions", () => {
    const prev = { targetCol: 1, targetRow: 0, valid: true };
    // Staying in the same cell while active must NEVER trigger a re-render!
    assert.equal(
      shouldRequestGridDragUpdate(prev, { targetCol: 1, targetRow: 0, valid: true }, false),
      false,
    );
    // Initial threshold activation must trigger once
    assert.equal(
      shouldRequestGridDragUpdate(prev, { targetCol: 1, targetRow: 0, valid: true }, true),
      true,
    );
    // Moving to a new col, row, or changing drop validity triggers update
    assert.equal(
      shouldRequestGridDragUpdate(prev, { targetCol: 2, targetRow: 0, valid: true }, false),
      true,
    );
    assert.equal(
      shouldRequestGridDragUpdate(prev, { targetCol: 1, targetRow: 1, valid: true }, false),
      true,
    );
    assert.equal(
      shouldRequestGridDragUpdate(prev, { targetCol: 1, targetRow: 0, valid: false }, false),
      true,
    );
  });

  it("memoizes shortcut entity options by (catalogRef, domainFilter) and debounces MDI icon search", async () => {
    clearShortcutEntityOptionsCache();
    const catalogA: ShortcutEntityCatalogEntry[] = [
      { id: "light.kitchen", name: "Kitchen", domain: "light", area_name: "Kitchen" },
      { id: "switch.fan", name: "Fan", domain: "switch", area_name: "Office" },
    ];
    let formatCalls = 0;
    const fmt = (id: string): string => {
      formatCalls += 1;
      return `state:${id}`;
    };

    const first = getMemoizedShortcutEntityOptions(catalogA, "all", fmt);
    const second = getMemoizedShortcutEntityOptions(catalogA, "all", fmt);
    assert.equal(first, second);
    assert.equal(formatCalls, 2);

    const lightsOnly = getMemoizedShortcutEntityOptions(catalogA, "light", fmt);
    assert.equal(lightsOnly.length, 1);
    assert.equal(lightsOnly[0]?.id, "light.kitchen");
    assert.equal(formatCalls, 3);

    // Repeating same (catalogA, "light") hits memo cache
    assert.equal(getMemoizedShortcutEntityOptions(catalogA, "light", fmt), lightsOnly);
    assert.equal(formatCalls, 3);

    // New catalog reference invalidates cache
    const catalogB = [...catalogA];
    const refreshed = getMemoizedShortcutEntityOptions(catalogB, "light", fmt);
    assert.notEqual(refreshed, lightsOnly);
    assert.equal(formatCalls, 4);
    clearShortcutEntityOptionsCache();

    // Debounced icon search coalesces rapid keystrokes into 1 update and cancels cleanly on close
    const { store, updateCount, resetUpdates } = createHarness();
    store.shortcutModal = { ...store.shortcutModal, open: true, iconSearch: "" };
    resetUpdates();

    scheduleShortcutIconSearchDebounce(store, "l", 25);
    scheduleShortcutIconSearchDebounce(store, "la", 25);
    scheduleShortcutIconSearchDebounce(store, "lamp", 25);
    assert.equal(store.shortcutModal.iconSearch, "lamp");
    assert.equal(updateCount(), 0);

    await new Promise((r) => setTimeout(r, 45));
    assert.equal(updateCount(), 1);

    // Cancelling before debounce elapses prevents stale update
    resetUpdates();
    scheduleShortcutIconSearchDebounce(store, "sun", 25);
    cancelShortcutIconSearchDebounce(store);
    await new Promise((r) => setTimeout(r, 45));
    assert.equal(updateCount(), 0);
  });

  it("mounts combobox options lazily only when open, uses stable discovered keys with BLE pagination, and renders collapsed presence drawers lazily", () => {
    const closedTpl = renderEntityCombobox({
      id: "test-cb-closed",
      value: "light.kitchen",
      options: [
        { id: "light.kitchen", name: "Kitchen Light", domain: "light" },
        { id: "light.desk", name: "Desk Lamp", domain: "light" },
      ],
      onChange: () => {},
    });
    const closedHtml = flattenTemplateStrings(closedTpl);
    assert.match(closedHtml, /role="combobox"/);
    assert.match(closedHtml, /aria-controls=/);
    assert.match(closedHtml, /aria-expanded=/);
    // Zero <li> options rendered while popup is closed!
    assert.equal(closedHtml.includes('role="option"'), false);
    assert.equal(closedHtml.includes("Desk Lamp"), false);

    // Stable keys without ::idx + BLE pagination cap at DISCOVERED_BLE_PAGE_SIZE (30)
    const manyBle: DiscoveredBleCandidate[] = Array.from({ length: 45 }, (_, i) => ({
      target_address: `AA:BB:CC:DD:00:${i.toString(16).padStart(2, "0").toUpperCase()}`,
      title: `Beacon ${String(i + 1).padStart(2, "0")}`,
      is_tracker: true,
      rssi: -50 - i,
      area_name: "Kitchen",
    }));
    const { store } = createHarness({ discovered_ble_devices: manyBle });
    assert.equal(discoveredBleCandidateKey(store, manyBle[0]!), "aa:bb:cc:dd:00:00");
    assert.equal(discoveredBleCandidateKey(store, manyBle[0]!).includes("::0"), false);
    assert.equal(
      discoveredLatterDeviceKey(store.state!.discovered_latter_devices![0]!),
      "esp_entry",
    );

    const discHtml = flattenTemplateStrings(renderDevicesDiscoveredView(store));
    assert.equal(discHtml.includes("Beacon 01"), true);
    assert.equal(discHtml.includes(`Beacon ${String(DISCOVERED_BLE_PAGE_SIZE).padStart(2, "0")}`), true);
    assert.equal(discHtml.includes(`Beacon ${String(DISCOVERED_BLE_PAGE_SIZE + 1).padStart(2, "0")}`), false);
    assert.equal(discHtml.includes("btn-discovered-ble-show-more"), true);

    // System presence view skips collapsed <details> bodies and supports available_sensors fallback
    store.openFusionAreas.clear();
    store.openProxyTrims.clear();
    store.advancedBleOpen = false;
    const collapsedPresence = flattenTemplateStrings(renderSystemPresenceView(store));
    assert.equal(collapsedPresence.includes("fusion-threshold-kitchen"), false);
    assert.equal(collapsedPresence.includes("sys-ble_away_timeout_s"), false);
    assert.equal(collapsedPresence.includes("proxy-trim-body"), false);

    // Opening fusion drawer mounts threshold & falls back cleanly to available_sensors
    store.openFusionAreas.add("kitchen");
    store.openProxyTrims.add("proxy_kitchen");
    store.advancedBleOpen = true;
    const expandedPresence = flattenTemplateStrings(
      renderSystemPresenceView(store) as TemplateResult,
    );
    assert.equal(expandedPresence.includes("fusion-threshold-kitchen"), true);
    assert.equal(expandedPresence.includes("binary_sensor.kitchen_motion"), true);
    assert.equal(expandedPresence.includes("sys-ble_away_timeout_s"), true);
    assert.equal(expandedPresence.includes("proxy-trim-body"), true);
  });

  it("minifies html/css template literals safely in build.mjs while preserving calc(), <pre>/<code>, strings, and inline spacing", async () => {
    const buildModPath = "../../build.mjs";
    const buildMod = (await import(buildModPath)) as {
      minifyLitTemplatesInSource(source: string): string;
    };

    const sample = `
      const note = "html\`   <div>  keep string  </div>   \`";
      const re = /\\s+\\//g;
      const styles = css\`
        /* Header comment */
        :host {
          inline-size: min(460px, calc(100vw - 32px));
          padding-inline-end: calc(100% + var(--studio-space-1));
        }
        .foo :hover {
          content: "a   b";
          display: flex;
        }
        @media (hover: none) and (max-width: 760px) {
          .bar { opacity: 1; }
        }
      \`;
      const view = (x: string) => html\`
        <div
          class="wrap"
          data-x="\${x}"
        >
          <strong>Title:</strong>
          \${x}
          <pre>  keep   spaces\n  here  </pre>
          <code>  x  +  y  </code>
          <input .value=\${x} />
          \${x ? html\`
            <span>
              \${x}
              •
              \${x}
            </span>
          \` : nothing}
        </div>
      \`;
    `;

    const out = buildMod.minifyLitTemplatesInSource(sample);
    // Regular JS string & regex stay untouched
    assert.equal(out.includes('"html`   <div>  keep string  </div>   `"'), true);
    assert.equal(out.includes("/\\s+\\//g"), true);
    // CSS comments removed, calc() & @media spacing & descendant :hover & CSS string preserved
    assert.equal(out.includes("Header comment"), false);
    assert.equal(out.includes("calc(100vw - 32px)"), true);
    assert.equal(out.includes("calc(100% + var(--studio-space-1))"), true);
    assert.equal(out.includes(".foo :hover{"), true);
    assert.equal(out.includes('content:"a   b"'), true);
    assert.equal(out.includes("@media (hover:none) and (max-width:760px){"), true);
    assert.equal(out.includes(".bar{opacity:1}"), true);
    // HTML preserves <pre>/<code>, inline spacing after </strong>, bullet spacing, and unquoted ` />`
    assert.equal(out.includes("<pre>  keep   spaces\n  here  </pre>"), true);
    assert.equal(out.includes("<code>  x  +  y  </code>"), true);
    assert.equal(out.includes("<strong>Title:</strong> ${x}"), true);
    assert.equal(out.includes("<input .value=${x} />"), true);
    assert.equal(out.includes("${x} • ${x}"), true);
    assert.equal(out.includes('<div class="wrap" data-x="${x}">'), true);
    assert.equal(out.includes("</div>\n"), false);
  });
});
