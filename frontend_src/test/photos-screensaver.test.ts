/**
 * Frontend unit & DOM tests for Photo Library, Photo Frame Screensaver, Day & Night Sky,
 * & Independent Weather Backdrops (`D-072`, `STUDIO_REV = 39`).
 */

import "./dom-shim.js";
import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";
import { renderAppConfigModalBody } from "../src/components/dialogs/app-config.js";
import { renderMediaImportDialog } from "../src/components/dialogs/media-import-modal.js";
import { renderPhotoPickerDialog } from "../src/components/dialogs/photo-picker-modal.js";
import {
  renderPhotoEditDialog,
  renderPhotoUploadDialog,
} from "../src/components/dialogs/photo-upload-modal.js";
import {
  NATIVE_DOCK_CONFIG_APP_MAP,
  PHOTO_LIBRARY_PAGE_SIZE,
  START_SCREEN_CONFIG_APP_MAP,
  STUDIO_REV,
  SYSTEM_VIEW_SLUGS,
} from "../src/constants.js";
import { tPrefLabel, tPrefOption } from "../src/i18n/index.js";
import { render } from "../src/lib/lit.js";
import { DIALOG_STYLES } from "../src/styles/dialogs.js";
import { DATA_STYLES } from "../src/styles/data.js";
import type { DeviceGroup, PhotoCollection, PhotoItem } from "../src/types.js";
import { applyCanvasPanDelta, computeCropSourceRect } from "../src/utils/crop-math.js";
import { renderDeviceDisplayView } from "../src/views/device-display-view.js";
import { renderDeviceInterfaceView } from "../src/views/device-interface-view.js";
import { renderGroupBaselineDrawer } from "../src/views/groups/group-baseline-drawer.js";
import { renderSystemOverviewView } from "../src/views/system-overview-view.js";
import { renderSystemPhotosView } from "../src/views/system-photos-view.js";
import { renderSystemSharedView } from "../src/views/system-shared-view.js";
import { resetDomBody, simDocument, SimEvent } from "./dom-shim.js";
import { makeFakeStore, renderToHtml } from "./fake-store.js";

function samplePhotos(): PhotoItem[] {
  return [
    {
      id: "preset:day_night_sky",
      name: "Day & Night Sky",
      kind: "dynamic_preset",
      source_kind: "dynamic_preset",
      deletable: false,
      thumb_url: "/thumb/day_night_sky",
      collections: [],
    },
    {
      id: "preset:forest_mountains",
      name: "Forest Mountains",
      kind: "preset",
      source_kind: "preset",
      deletable: false,
      thumb_url: "/thumb/forest",
      collections: ["col_nature"],
    },
    {
      id: "photo:beach_01",
      name: "Sunset Beach",
      kind: "uploaded",
      source_kind: "upload",
      deletable: true,
      width: 1600,
      height: 1200,
      crop: { x: 0.5, y: 0.4, zoom: 1.5 },
      thumb_url: "/thumb/beach",
      orig_url: "/orig/beach",
      collections: ["col_family"],
    },
    {
      id: "photo:dog_02",
      name: "Park Walk",
      kind: "uploaded",
      source_kind: "media_import",
      media_source_path: "local/photos/dog.jpg",
      deletable: true,
      width: 1200,
      height: 1600,
      crop: { x: 0.5, y: 0.5, zoom: 1.0 },
      thumb_url: "/thumb/dog",
      orig_url: "/orig/dog",
      collections: [],
    },
  ];
}

function sampleCollections(): PhotoCollection[] {
  return [
    { id: "col_family", name: "Family", count: 1 },
    { id: "col_nature", name: "Nature", count: 1 },
  ];
}

describe("Photo Library, Photo Frame Screensaver, & Weather Backdrops (D-072 / STUDIO_REV 39)", () => {
  beforeEach(() => {
    resetDomBody();
  });

  it("registers STUDIO_REV >= 39, photos System view, Weather app modal, and Sentence-case labels", () => {
    assert.ok(STUDIO_REV >= 39);
    assert.equal(SYSTEM_VIEW_SLUGS.photos, "photos");
    assert.equal(NATIVE_DOCK_CONFIG_APP_MAP["app:weather"], "weather");
    assert.equal(START_SCREEN_CONFIG_APP_MAP.Weather, "weather");

    assert.equal(tPrefLabel("screensaver_mode"), "Screensaver mode");
    assert.equal(tPrefLabel("screensaver_photo_clock"), "Show subtle clock");
    assert.equal(tPrefLabel("weather_background"), "Live weather background on Home");
    assert.equal(tPrefLabel("weather_app_background"), "Live weather background");
    assert.equal(tPrefOption("screensaver_style", "Photo Frame"), "Photo frame");
    assert.equal(tPrefOption("screensaver_mode", "Docked Only"), "Docked only");
    assert.equal(tPrefOption("screensaver_mode", "Always"), "Always");
    assert.equal(tPrefOption("screensaver_mode", "Never"), "Never");
  });

  it("computes zero-black-bar non-destructive crop rects and clamps pan deltas cleanly", () => {
    // Wide 1600x900 photo fitted into square 466x466 at zoom 1.0 -> sw=900, sh=900, sx=350
    const sq = computeCropSourceRect(1600, 900, 466, 466, { x: 0.5, y: 0.5, zoom: 1 });
    assert.equal(Math.round(sq.sw), 900);
    assert.equal(Math.round(sq.sh), 900);
    assert.equal(Math.round(sq.sx), 350);
    assert.equal(Math.round(sq.sy), 0);

    // Extreme focal point x=0.0 never produces negative sx
    const leftEdge = computeCropSourceRect(1600, 900, 466, 466, { x: 0, y: 0, zoom: 2 });
    assert.equal(leftEdge.sx, 0);
    assert.equal(leftEdge.sy, 0);
    assert.ok(leftEdge.sx + leftEdge.sw <= 1600);
    assert.ok(leftEdge.sy + leftEdge.sh <= 900);

    // Tall portrait 900x1600 fitted into widescreen 1024x600 at zoom 1.5 stays strictly in bounds
    const wide = computeCropSourceRect(900, 1600, 1024, 600, { x: 0.99, y: 0.99, zoom: 1.5 });
    assert.ok(wide.sx >= 0 && wide.sy >= 0);
    assert.ok(wide.sx + wide.sw <= 900.001);
    assert.ok(wide.sy + wide.sh <= 1600.001);

    // Dragging right reveals left side of image (decreases crop.x) and clamps cleanly
    const panned = applyCanvasPanDelta({ x: 0.5, y: 0.5, zoom: 1.5 }, 40, 0, 1600, 900, 260, 260);
    assert.ok(panned.x < 0.5);
    assert.equal(panned.y, 0.5);
    assert.equal(panned.zoom, 1.5);
  });

  it("renders System -> Photos with collection filters, pagination, bulk select, and click-to-edit modal", async () => {
    const manyPhotos: PhotoItem[] = [
      ...samplePhotos(),
      ...Array.from({ length: PHOTO_LIBRARY_PAGE_SIZE + 2 }, (_, idx) => ({
        id: `photo:extra_${idx}`,
        name: `Trip Photo ${idx + 1}`,
        kind: "uploaded",
        source_kind: "upload",
        deletable: true,
        thumb_url: `/thumb/extra_${idx}`,
        collections: [],
      })),
    ];

    const harness = makeFakeStore({
      currentScope: "system",
      currentViewId: "photos",
      state: {
        system_wallpapers: manyPhotos,
        photo_collections: sampleCollections(),
      },
    });
    const { store, sysCalls } = harness;

    const container = simDocument.createElement("div");
    render(renderSystemPhotosView(store), container);

    // Page 1 shows exactly 36 photos + pagination controls
    assert.equal(container.querySelectorAll(".photo-tile").length, PHOTO_LIBRARY_PAGE_SIZE);
    assert.ok(container.querySelector("#btn-photos-next-page"));

    // Filter to Family collection -> shows only Sunset Beach
    const familyBtn = container.querySelector(
      "[data-collection-filter='col_family']",
    ) as unknown as HTMLButtonElement;
    assert.ok(familyBtn);
    familyBtn.click();
    render(renderSystemPhotosView(store), container);
    assert.equal(container.querySelectorAll(".photo-tile").length, 1);
    assert.ok(container.innerHTML.includes("Sunset Beach"));

    // Clicking the photo opens Photo Editor & Crop modal
    const thumbBtn = container.querySelector(".photo-tile-thumb-btn") as unknown as HTMLButtonElement;
    thumbBtn.click();
    assert.equal(store.photoEditModal.open, true);
    assert.equal(store.photoEditModal.photoId, "photo:beach_01");
    assert.equal(store.photoEditModal.crop.zoom, 1.5);

    const editContainer = simDocument.createElement("div");
    render(renderPhotoEditDialog(store), editContainer);
    assert.ok(editContainer.querySelector("#latter-edit-crop-canvas"));
    assert.ok(editContainer.querySelector("#btn-edit-delete-photo"));

    // Save photo metadata calls update_photo_metadata
    await store.entity.savePhotoEditModal();
    assert.equal(sysCalls.length, 1);
    assert.equal(sysCalls[0].command, "update_photo_metadata");
    assert.equal(sysCalls[0].payload.photo_id, "photo:beach_01");

    // Toggle Select bulk mode & assign collection
    const toggleSel = container.querySelector("#btn-photos-toggle-select") as unknown as HTMLButtonElement;
    toggleSel.click();
    store.photosSelectedIds.add("photo:beach_01");
    await store.entity.bulkUpdatePhotos({ addCollection: "col_nature" });
    assert.equal(sysCalls[1].command, "bulk_update_photos");
    assert.deepEqual(sysCalls[1].payload, {
      photo_ids: ["photo:beach_01"],
      add_collection: "col_nature",
    });

    // Overview omits retired System capabilities card & Shared entities removed #card-system-wallpapers
    const overviewHtml = renderToHtml(renderSystemOverviewView(store));
    assert.equal(overviewHtml.includes("card-system-capabilities"), false);
    const sharedHtml = renderToHtml(renderSystemSharedView(store));
    assert.equal(sharedHtml.includes("card-system-wallpapers"), false);
  });

  it("supports multi-file Upload Staging modal and HA Media Folder Import modal", async () => {
    const harness = makeFakeStore({
      currentScope: "system",
      currentViewId: "photos",
      state: {
        system_wallpapers: samplePhotos(),
        photo_collections: sampleCollections(),
      },
    });
    const { store, sysCalls } = harness;

    // 1. Multi-file upload staging
    store.entity.openPhotoUploadModal();
    const f1 = new File([new Uint8Array([1, 2, 3])], "alps_morning.jpg", { type: "image/jpeg" });
    const f2 = new File([new Uint8Array([4, 5, 6])], "coast_sunset.png", { type: "image/png" });
    store.entity.stageUploadFiles([f1, f2]);
    assert.equal(store.photoUploadModal.files.length, 2);
    assert.equal(store.photoUploadModal.files[0].name, "alps morning");

    const uploadContainer = simDocument.createElement("div");
    render(renderPhotoUploadDialog(store), uploadContainer);
    assert.ok(uploadContainer.querySelector("#latter-upload-crop-canvas"));
    assert.ok(uploadContainer.innerHTML.includes("Upload all (2)"));

    // 2. HA Media Folder Import
    store.ws.browseMediaFolder = async (_root, subpath) => ({
      roots: [{ id: "local", name: "Local Media" }],
      root: "local",
      subpath: subpath || "",
      parent_subpath: subpath ? "" : null,
      folders: subpath ? [] : [{ name: "Vacation", subpath: "Vacation" }],
      images: subpath
        ? [
            {
              name: "IMG_001.jpg",
              relpath: "Vacation/IMG_001.jpg",
              size_bytes: 512000,
              too_large: false,
              already_imported: false,
              thumb_url: "/media/thumb/1",
            },
          ]
        : [],
    });

    store.entity.openMediaImportModal();
    await new Promise<void>((r) => setTimeout(r, 0));
    await store.entity.browseMediaFolder("local", "Vacation");

    const mediaContainer = simDocument.createElement("div");
    render(renderMediaImportDialog(store), mediaContainer);
    assert.ok(mediaContainer.innerHTML.includes("IMG_001.jpg"));

    const selectAllBtn = mediaContainer.querySelector("#btn-media-select-all") as unknown as HTMLButtonElement;
    selectAllBtn.click();
    assert.deepEqual(store.mediaImportModal.selectedPaths, ["Vacation/IMG_001.jpg"]);

    const newColBtn = mediaContainer.querySelector(
      "#btn-media-new-col-from-folder",
    ) as unknown as HTMLButtonElement;
    newColBtn.click();
    assert.equal(store.mediaImportModal.useNewFolderCollection, true);
    assert.equal(store.mediaImportModal.newCollectionName, "Vacation");

    await store.entity.importSelectedMedia();
    assert.equal(sysCalls.length, 1);
    assert.equal(sysCalls[0].command, "import_media_photos");
    assert.deepEqual(sysCalls[0].payload, {
      root: "local",
      paths: ["Vacation/IMG_001.jpg"],
      deduplicate: true,
      new_collection_name: "Vacation",
    });
  });

  it("filters dynamic_preset out of Photo Frame picker and renders streamlined Device Display & Interface", async () => {
    const harness = makeFakeStore({
      currentScope: "device",
      currentViewId: "display",
      activeSubentryId: "sub_1",
      deviceSelected: true,
      devicePrefs: [
        {
          key: "screensaver_mode",
          label: "Screensaver mode",
          section: "display",
          domain: "select",
          value: "Docked Only",
          options: ["Docked Only", "Always", "Never"],
        },
        {
          key: "screensaver_style",
          label: "Screensaver style",
          section: "display",
          domain: "select",
          value: "Photo Frame",
          options: ["Ambient Clock", "Photo Frame", "Aurora", "Starfield"],
        },
        {
          key: "docked_idle_timeout",
          label: "Docked idle timeout",
          section: "display",
          domain: "select",
          value: "2 min",
          options: ["1 min", "2 min", "5 min"],
        },
        {
          key: "screensaver_photo_clock",
          label: "Show subtle clock",
          section: "display",
          domain: "switch",
          value: true,
        },
        {
          key: "weather_background",
          label: "Live weather background on Home",
          section: "interface",
          domain: "switch",
          value: true,
        },
        {
          key: "weather_app_background",
          label: "Live weather background",
          section: "interface",
          domain: "switch",
          value: false,
        },
      ],
      state: {
        wallpapers: samplePhotos(),
        system_wallpapers: samplePhotos(),
        photo_collections: sampleCollections(),
        config: {
          display_shape: "circle",
          home_screen_enabled: true,
          wallpaper_mode: "single",
          wallpaper_source: "preset:day_night_sky",
          wallpaper_cycle_minutes: 0,
          screensaver_photo_mode: "collection",
          screensaver_photo_collection: "col_family",
          screensaver_cycle_minutes: 15,
          screensaver_shuffle: true,
          dock_items: [
            { kind: "route", target: "app:weather", action: "", label: "", icon: "", confirm: false },
          ],
        },
      },
    });
    const { store, devCalls } = harness;

    // 1. Device Display shows Photo Frame rows + Home-only override note
    const dispHtml = renderToHtml(renderDeviceDisplayView(store));
    assert.ok(dispHtml.includes('id="screensaver-photo-frame-section"'));
    assert.ok(dispHtml.includes('id="btn-choose-ss-photos"'));
    assert.ok(dispHtml.includes('id="btn-choose-wallpaper"'));
    assert.ok(dispHtml.includes('id="btn-manage-photo-library"'));
    assert.ok(dispHtml.includes("Weather background is enabled on Home"));
    assert.ok(dispHtml.includes('id="btn-wp-open-interface"'));

    // Switching screensaver_mode to Never hides Photo Frame section & style controls
    store.state!.device_prefs = store.state!.device_prefs.map((p) =>
      p.key === "screensaver_mode" ? { ...p, value: "Never" } : p,
    );
    const neverHtml = renderToHtml(renderDeviceDisplayView(store));
    assert.equal(neverHtml.includes("screensaver-photo-frame-section"), false);
    assert.equal(neverHtml.includes("Screensaver style"), false);

    // 2. Photo Picker filters dynamic_preset out of Photo Frame, keeps it for Wallpaper
    store.entity.openPhotoPickerModal("wallpaper");
    const wpPickerHtml = renderToHtml(renderPhotoPickerDialog(store));
    assert.ok(wpPickerHtml.includes("Day &amp; Night Sky"));

    store.entity.openPhotoPickerModal("screensaver");
    store.photoPickerModal = { ...store.photoPickerModal, mode: "photos" };
    const ssPickerHtml = renderToHtml(renderPhotoPickerDialog(store));
    assert.equal(ssPickerHtml.includes("Day &amp; Night Sky"), false);
    assert.ok(ssPickerHtml.includes("Sunset Beach"));

    store.photoPickerModal = {
      ...store.photoPickerModal,
      mode: "collection",
      collectionId: "col_family",
    };
    await store.entity.applyPhotoPickerModal();
    assert.equal(devCalls.length, 1);
    assert.equal(devCalls[0].command, "set_device_photo_pool");
    assert.equal(devCalls[0].payload.target, "screensaver");
    assert.equal(devCalls[0].payload.mode, "collection");
    assert.equal(devCalls[0].payload.collection_id, "col_family");

    // 3. Device Interface shows Uses device wallpaper for Sky & weather + Configure modal works
    const ifaceContainer = simDocument.createElement("div");
    render(renderDeviceInterfaceView(store), ifaceContainer);
    assert.ok(ifaceContainer.innerHTML.includes("Uses device wallpaper"));

    store.entity.openAppConfigModal("weather");
    const weatherModalContainer = simDocument.createElement("div");
    render(renderAppConfigModalBody(store), weatherModalContainer);
    const toggle = weatherModalContainer.querySelector(
      "#cfg-weather_app_background",
    ) as unknown as HTMLInputElement;
    assert.ok(toggle);
    assert.equal(toggle.checked, false);
    toggle.checked = true;
    toggle.dispatchEvent(new SimEvent("change", { bubbles: true }));
    store.entity.discardDeviceBucket("sub_1");

    const openSharedBtn = weatherModalContainer.querySelector(
      "#btn-weather-open-shared",
    ) as unknown as HTMLButtonElement;
    assert.ok(openSharedBtn);
    openSharedBtn.click();
    assert.equal(store.currentScope, "system");
    assert.equal(store.currentViewId, "shared_entities");
    assert.equal(store.isHandoffTarget("card-whole-home"), true);
  });

  it("renders screensaver_mode, screensaver_photo_clock, weather_app_background, and pool selectors in Group Baseline Drawer", () => {
    const { store } = makeFakeStore({
      currentScope: "system",
      currentViewId: "system_sync",
      state: {
        system_wallpapers: samplePhotos(),
        photo_collections: sampleCollections(),
      },
    });
    const grp: DeviceGroup = {
      id: "pocket_carry",
      name: "Pocket Carry",
      description: "Pocket carry",
      builtin: true,
      include_display: true,
      include_interface: true,
      device_config: {
        screensaver_mode: "Docked Only",
        screensaver_style: "Photo Frame",
        screensaver_photo_clock: true,
        weather_app_background: true,
      },
    };
    const drawerHtml = renderToHtml(renderGroupBaselineDrawer(store, grp, [], []));
    assert.ok(drawerHtml.includes("Screensaver mode"));
    assert.ok(drawerHtml.includes("Wallpaper source"));
    assert.ok(drawerHtml.includes("Photo frame source"));
    assert.ok(drawerHtml.includes("Show subtle clock"));
    assert.ok(drawerHtml.includes("Live weather background"));
    assert.equal(drawerHtml.includes("Docked screensaver"), false);
  });

  it("prunes stale photo IDs in Photo Picker custom mode, allows creating a collection in Upload modal, and isolates modal scroll", async () => {
    const harness = makeFakeStore({
      currentScope: "device",
      currentViewId: "display",
      activeSubentryId: "sub_1",
      deviceSelected: true,
      state: {
        system_devices: [
          {
            subentry_id: "sub_1",
            title: "Desk Display",
            subentry_type: "device",
            online: true,
          },
        ],
        wallpapers: samplePhotos(),
        system_wallpapers: samplePhotos(),
        photo_collections: sampleCollections(),
        config: {
          display_shape: "square",
          wallpaper_mode: "custom",
          wallpaper_favorites: [
            "upload:legacy/deleted_one.jpg",
            "upload:legacy/deleted_two.jpg",
            "photo:beach_01",
          ],
          wallpaper_cycle_minutes: 15,
        },
      },
    });
    const { store, sysCalls } = harness;

    // 1. Stale legacy IDs are filtered on open -> count is 1, not 3; Clear empties selection
    store.entity.openPhotoPickerModal("wallpaper");
    assert.equal(store.photoPickerModal.mode, "photos");
    assert.deepEqual(store.photoPickerModal.selectedIds, ["photo:beach_01"]);
    const pickerContainer = simDocument.createElement("div");
    render(renderPhotoPickerDialog(store), pickerContainer);
    assert.ok(pickerContainer.innerHTML.includes("1 photo selected"));
    assert.ok(pickerContainer.querySelector("#btn-picker-mode-photos"));
    assert.ok(pickerContainer.querySelector("#btn-picker-mode-collection"));

    // Applying 1 selected photo sends mode="single"; applying 2 sends mode="custom"
    await store.entity.applyPhotoPickerModal();
    assert.equal(harness.devCalls[0].payload.mode, "single");
    assert.equal(harness.devCalls[0].payload.source_id, "photo:beach_01");

    store.entity.openPhotoPickerModal("wallpaper");
    store.photoPickerModal = {
      ...store.photoPickerModal,
      selectedIds: ["photo:beach_01", "preset:forest_mountains"],
    };
    await store.entity.applyPhotoPickerModal();
    assert.equal(harness.devCalls[1].payload.mode, "custom");
    assert.deepEqual(harness.devCalls[1].payload.photo_ids, [
      "photo:beach_01",
      "preset:forest_mountains",
    ]);

    store.entity.openPhotoPickerModal("wallpaper");
    store.photoPickerModal = { ...store.photoPickerModal, selectedIds: ["photo:beach_01"] };
    render(renderPhotoPickerDialog(store), pickerContainer);
    const clearBtn = pickerContainer.querySelector("#btn-picker-clear-custom") as unknown as HTMLButtonElement;
    assert.ok(clearBtn);
    clearBtn.click();
    assert.deepEqual(store.photoPickerModal.selectedIds, []);
    render(renderPhotoPickerDialog(store), pickerContainer);
    assert.ok(pickerContainer.innerHTML.includes("0 photos selected"));

    // 2. Upload modal inline New collection creates and auto-selects without clearing staged files
    const origRunSys = store.ws.runSystemCommand.bind(store.ws);
    store.ws.runSystemCommand = async (command, payload, subentryId) => {
      await origRunSys(command, payload, subentryId);
      if (command === "create_photo_collection") {
        const nextCol = { id: "col_trips", name: String(payload?.name || "Trips"), count: 0 };
        store.state!.photo_collections = [...(store.state!.photo_collections || []), nextCol];
        return {
          ...store.state!,
          collection: { id: nextCol.id, name: nextCol.name },
        };
      }
      return store.state!;
    };

    store.entity.openPhotoUploadModal();
    const f1 = new File([new Uint8Array([1, 2, 3])], "trip_01.jpg", { type: "image/jpeg" });
    store.entity.stageUploadFiles([f1]);
    const uploadContainer = simDocument.createElement("div");
    render(renderPhotoUploadDialog(store), uploadContainer);
    const openNewColBtn = uploadContainer.querySelector(
      "#btn-upload-new-collection",
    ) as unknown as HTMLButtonElement;
    assert.ok(openNewColBtn);
    openNewColBtn.click();
    store.photoUploadModal = { ...store.photoUploadModal, newCollectionName: "Trips" };
    await store.entity.createUploadCollection();
    assert.equal(sysCalls.some((c) => c.command === "create_photo_collection"), true);
    assert.equal(store.photoUploadModal.collectionId, "col_trips");
    assert.equal(store.photoUploadModal.newCollectionOpen, false);
    assert.equal(store.photoUploadModal.files.length, 1);

    // 3. Dialog & photo picker grid prevent scroll chaining; photo-pool-preview wraps cleanly
    assert.ok(DIALOG_STYLES.styleSheetText.includes("overscroll-behavior: contain"));
    assert.ok(DATA_STYLES.styleSheetText.includes("flex: 1 1 160px"));
  });
});
