/**
 * Frontend unit & DOM tests for the Dedicated Cameras App (`D-071`, `STUDIO_REV = 38`):
 * - Protected Native App `app:cameras`, 5-tab `HOME_CATEGORIES_CATALOG`, & `ROUTE_PREVIEW_ICONS`
 * - `Device -> Interface -> App Dock` live Cameras summary & Single-App Mode Start screen -> Configure
 * - `#latter-app-config-modal("cameras")` (`hw_jpeg` capability gate, Visible & Carousel pill lists,
 *   and `#card-cameras-doorbell` Shared entities deep-link)
 * - Group Baseline Drawer `hw_jpeg` gating (`wall_panels` vs `pocket_carry`)
 * - `System -> Shared entities` declarative camera capability chips (`RTSP`/`MJPEG`/`Snapshot`, `Audio`, `Doorbell`)
 */

import "./dom-shim.js";
import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";
import { renderAppConfigModalBody } from "../src/components/dialogs/app-config.js";
import {
  HOME_CATEGORIES_CATALOG,
  NATIVE_DOCK_APP_TOKENS,
  NATIVE_DOCK_CONFIG_APP_MAP,
  START_SCREEN_CONFIG_APP_MAP,
} from "../src/constants.js";
import { tPrefLabel, tPrefOption } from "../src/i18n/index.js";
import { render } from "../src/lib/lit.js";
import { ROUTE_PREVIEW_ICONS } from "../src/mdi-catalog.js";
import type { DeviceGroup, SystemDeviceEntry } from "../src/types.js";
import { renderDeviceInterfaceView } from "../src/views/device-interface-view.js";
import { renderGroupBaselineDrawer } from "../src/views/groups/group-baseline-drawer.js";
import { renderSystemSharedView } from "../src/views/system-shared-view.js";
import { resetDomBody, simDocument } from "./dom-shim.js";
import { makeFakeStore, renderToHtml } from "./fake-store.js";

describe("Dedicated Cameras App (D-071 / STUDIO_REV 38)", () => {
  beforeEach(() => {
    resetDomBody();
  });

  it("registers app:cameras as a Protected Native App, updates routes, and removes cameras from Home Hub", () => {
    assert.ok(NATIVE_DOCK_APP_TOKENS.includes("app:cameras"));
    assert.equal(NATIVE_DOCK_CONFIG_APP_MAP["app:cameras"], "cameras");
    assert.equal(START_SCREEN_CONFIG_APP_MAP.Cameras, "cameras");

    assert.deepEqual(
      HOME_CATEGORIES_CATALOG.map((c) => c.token),
      ["alarm", "intercom", "thermostat", "entry", "vacuum"],
    );

    assert.equal(ROUTE_PREVIEW_ICONS["home_hub:cameras"], undefined);
    assert.equal(ROUTE_PREVIEW_ICONS["app:cameras"], "mdi:cctv");
    assert.equal(ROUTE_PREVIEW_ICONS["cameras:grid"], "mdi:view-grid");
    assert.equal(ROUTE_PREVIEW_ICONS["cameras:single"], "mdi:video");
    assert.equal(ROUTE_PREVIEW_ICONS["cameras:carousel"], "mdi:view-carousel");
    assert.equal(ROUTE_PREVIEW_ICONS["cameras:settings"], "mdi:cog-outline");

    assert.equal(tPrefLabel("camera_default_view"), "Default view");
    assert.equal(tPrefLabel("camera_framing"), "Video framing");
    assert.equal(tPrefLabel("camera_carousel_interval"), "Carousel interval");
    assert.equal(tPrefLabel("camera_stream_mode"), "Stream mode");
    assert.equal(tPrefLabel("camera_doorbell_popup"), "Doorbell ring popup");
    assert.equal(tPrefOption("camera_stream_mode", "Low Bandwidth"), "Low bandwidth");
    assert.equal(tPrefOption("camera_doorbell_popup", "Live Video"), "Live video");
    assert.equal(tPrefOption("camera_carousel_interval", "60s"), "60 seconds");
  });

  it("renders live Cameras dock summary and opens Cameras modal from Single-App Mode Start screen", () => {
    const emptyHarness = makeFakeStore({
      currentScope: "device",
      currentViewId: "interface",
      activeSubentryId: "sub_cam_1",
      deviceSelected: true,
      state: {
        system_config: { camera_entities: [] },
        config: {},
      },
    });
    const emptyHtml = renderToHtml(renderDeviceInterfaceView(emptyHarness.store));
    assert.ok(emptyHtml.includes("No cameras configured"));

    const populatedHarness = makeFakeStore({
      currentScope: "device",
      currentViewId: "interface",
      activeSubentryId: "sub_cam_2",
      deviceSelected: true,
      state: {
        system_config: {
          camera_entities: ["camera.front_door", "camera.driveway", "camera.backyard"],
        },
        config: {
          camera_default_view: "Grid",
          camera_framing: "Uncropped",
        },
      },
    });
    const populatedHtml = renderToHtml(renderDeviceInterfaceView(populatedHarness.store));
    assert.ok(populatedHtml.includes("Grid • Uncropped • 3 cameras"));

    // Single-App Mode locked to Cameras -> Configure opens cameras modal
    const singleHarness = makeFakeStore({
      currentScope: "device",
      currentViewId: "interface",
      activeSubentryId: "sub_cam_3",
      deviceSelected: true,
      state: {
        system_config: { camera_entities: ["camera.front_door"] },
        config: {
          home_screen_enabled: false,
          start_screen: "Cameras",
        },
      },
    });
    const container = simDocument.createElement("div");
    render(renderDeviceInterfaceView(singleHarness.store), container);
    const cfgBtn = container.querySelector("#btn-configure-start-screen") as unknown as HTMLButtonElement;
    assert.ok(cfgBtn, "Expected #btn-configure-start-screen for Single-App Mode Cameras");
    cfgBtn.click();
    assert.equal(singleHarness.store.appConfigModal.open, true);
    assert.equal(singleHarness.store.appConfigModal.app, "cameras");
  });

  it("gates camera_doorbell_popup on hw_jpeg and manages Visible / Carousel camera pill lists", () => {
    const s3Harness = makeFakeStore({
      currentScope: "device",
      currentViewId: "interface",
      activeSubentryId: "sub_s3",
      deviceSelected: true,
      state: {
        capabilities: { has_display: true, hw_jpeg: false },
        system_config: {
          camera_entities: ["camera.front_door", "camera.driveway", "camera.backyard"],
        },
        catalog: {
          cameras: [
            { id: "camera.front_door", name: "Front Door" },
            { id: "camera.driveway", name: "Driveway" },
            { id: "camera.backyard", name: "Backyard" },
          ],
        },
        config: {},
      },
    });

    try {
      s3Harness.store.entity.openAppConfigModal("cameras");
      const s3Container = simDocument.createElement("div");
      render(renderAppConfigModalBody(s3Harness.store), s3Container);
      assert.ok(s3Container.querySelector("#cfg-camera_default_view"));
      assert.ok(s3Container.querySelector("#cfg-camera_framing"));
      assert.ok(s3Container.querySelector("#cfg-camera_carousel_interval"));
      assert.ok(s3Container.querySelector("#cfg-camera_stream_mode"));
      assert.equal(
        s3Container.querySelector("#cfg-camera_doorbell_popup"),
        null,
        "S3 without hw_jpeg must NOT render camera_doorbell_popup",
      );
      assert.ok(s3Container.querySelector("#camera-visible-pills"));
      assert.ok(s3Container.querySelector("#camera-carousel-pills"));

      // Toggle Backyard off in Visible cameras -> stages [front_door, driveway]
      s3Harness.store.entity.toggleVisibleCamera("camera.backyard", false);
      assert.deepEqual(s3Harness.store.state?.config?.camera_visible_entities, [
        "camera.front_door",
        "camera.driveway",
      ]);

      // Toggle Driveway off -> stages [front_door]; toggling last camera off is blocked
      s3Harness.store.entity.toggleVisibleCamera("camera.driveway", false);
      assert.deepEqual(s3Harness.store.state?.config?.camera_visible_entities, [
        "camera.front_door",
      ]);
      s3Harness.store.entity.toggleVisibleCamera("camera.front_door", false);
      assert.deepEqual(s3Harness.store.state?.config?.camera_visible_entities, [
        "camera.front_door",
      ]);
      assert.ok(s3Harness.toasts.some((t) => t.isError && t.msg.includes("camera")));

      // Re-enabling Driveway and Backyard in System order normalizes back to []
      s3Harness.store.entity.toggleVisibleCamera("camera.driveway", true);
      s3Harness.store.entity.toggleVisibleCamera("camera.backyard", true);
      assert.deepEqual(s3Harness.store.state?.config?.camera_visible_entities, []);

      // Carousel subset toggle & pruning when hidden from Visible cameras
      s3Harness.store.entity.toggleCarouselCamera("camera.backyard", false);
      assert.deepEqual(s3Harness.store.state?.config?.camera_carousel_entities, [
        "camera.front_door",
        "camera.driveway",
      ]);
      s3Harness.store.entity.toggleVisibleCamera("camera.driveway", false);
      assert.deepEqual(s3Harness.store.state?.config?.camera_carousel_entities, [
        "camera.front_door",
      ]);

      // Footer Open shared entities deep-links to #card-cameras-doorbell
      const sharedBtn = s3Container.querySelector(
        "#btn-cameras-open-shared",
      ) as unknown as HTMLButtonElement;
      assert.ok(sharedBtn);
      sharedBtn.click();
      assert.equal(s3Harness.store.appConfigModal.open, false);
      assert.equal(s3Harness.store.currentScope, "system");
      assert.equal(s3Harness.store.currentViewId, "shared_entities");
      assert.equal(s3Harness.store.isHandoffTarget("card-cameras-doorbell"), true);
    } finally {
      s3Harness.store.entity.discardDeviceBucket("sub_s3");
    }

    // P4 with hw_jpeg: true DOES render #cfg-camera_doorbell_popup
    const p4Harness = makeFakeStore({
      currentScope: "device",
      currentViewId: "interface",
      activeSubentryId: "sub_p4",
      deviceSelected: true,
      state: {
        capabilities: { has_display: true, hw_jpeg: true },
        system_config: { camera_entities: ["camera.front_door"] },
        config: {},
      },
    });
    p4Harness.store.entity.openAppConfigModal("cameras");
    const p4Container = simDocument.createElement("div");
    render(renderAppConfigModalBody(p4Harness.store), p4Container);
    assert.ok(
      p4Container.querySelector("#cfg-camera_doorbell_popup"),
      "P4 with hw_jpeg: true must render camera_doorbell_popup",
    );
  });

  it("gates camera_doorbell_popup by archetype capability in Group Baseline Drawers", () => {
    const { store } = makeFakeStore({
      currentScope: "system",
      currentViewId: "system_sync",
    });

    const wallGroup: DeviceGroup = {
      id: "wall_panels",
      name: "Wall & Desk Panels",
      description: "Stationary panels",
      builtin: true,
      include_interface: true,
      device_config: {},
    };
    const wallHtml = renderToHtml(renderGroupBaselineDrawer(store, wallGroup, [], []));
    assert.ok(wallHtml.includes("Default view"));
    assert.ok(wallHtml.includes("Video framing"));
    assert.ok(wallHtml.includes("Carousel interval"));
    assert.ok(wallHtml.includes("Stream mode"));
    assert.ok(wallHtml.includes("Doorbell ring popup"));

    const pocketGroup: DeviceGroup = {
      id: "pocket_carry",
      name: "Pocket Carry",
      description: "Pocket carry",
      builtin: true,
      include_interface: true,
      device_config: {},
    };
    const pocketHtml = renderToHtml(renderGroupBaselineDrawer(store, pocketGroup, [], []));
    assert.ok(pocketHtml.includes("Default view"));
    assert.ok(pocketHtml.includes("Video framing"));
    assert.ok(pocketHtml.includes("Carousel interval"));
    assert.ok(pocketHtml.includes("Stream mode"));
    assert.equal(
      pocketHtml.includes("Doorbell ring popup"),
      false,
      "Pocket Carry (S3 archetype) must hide Doorbell ring popup",
    );

    const handheldGroup: DeviceGroup = {
      id: "handhelds",
      name: "Handhelds",
      description: "Handhelds",
      builtin: true,
      include_interface: true,
      device_config: {},
    };
    const s3Member = {
      subentry_id: "sub_s3",
      has_display: true,
      has_battery: true,
      hw_jpeg: false,
    } as SystemDeviceEntry;
    const p4Member = {
      subentry_id: "sub_p4",
      has_display: true,
      has_battery: true,
      hw_jpeg: true,
    } as SystemDeviceEntry;
    const unknownMember = {
      subentry_id: "sub_unk",
      has_display: true,
      has_battery: true,
    } as SystemDeviceEntry;

    assert.equal(
      renderToHtml(renderGroupBaselineDrawer(store, handheldGroup, [s3Member], [])).includes(
        "Doorbell ring popup",
      ),
      false,
      "Handhelds with S3-only members must hide Doorbell ring popup",
    );
    assert.equal(
      renderToHtml(renderGroupBaselineDrawer(store, handheldGroup, [p4Member], [])).includes(
        "Doorbell ring popup",
      ),
      true,
      "Handhelds with P4 member must show Doorbell ring popup",
    );

    const customGroup: DeviceGroup = {
      id: "guest_suites",
      name: "Guest Panels",
      description: "Custom",
      builtin: false,
      include_interface: true,
      device_config: {},
    };
    assert.equal(
      renderToHtml(renderGroupBaselineDrawer(store, customGroup, [unknownMember], [])).includes(
        "Doorbell ring popup",
      ),
      false,
      "Custom group with undefined/S3-only hw_jpeg must hide Doorbell ring popup",
    );
    assert.equal(
      renderToHtml(renderGroupBaselineDrawer(store, customGroup, [p4Member], [])).includes(
        "Doorbell ring popup",
      ),
      true,
      "Custom group with P4 member must show Doorbell ring popup",
    );
  });

  it("renders declarative camera capability chips, Configure dialog, and custom labels (D-073)", async () => {
    const { openCameraConfigModal, renderCameraConfigDialog, saveCameraConfigModal } =
      await import("../src/components/dialogs/camera-config-modal.js");
    const { store } = makeFakeStore({
      currentScope: "system",
      currentViewId: "shared_entities",
      state: {
        system_config: {
          camera_entities: ["camera.front_door", "camera.driveway", "camera.nursery"],
          camera_configs: {
            "camera.driveway": {
              label: "Driveway",
              show_listen: false,
              show_talk: false,
              show_reply: false,
              unlock_entity: "cover.garage_door",
            },
          },
        },
        catalog: {
          cameras: [
            {
              id: "camera.front_door",
              name: "Front Door",
              stream_kind: "rtsp",
              has_audio: true,
              has_talkback: true,
              is_doorbell: true,
            },
            {
              id: "camera.driveway",
              name: "Driveway Camera Medium resolution channel",
              stream_kind: "mjpeg",
              has_audio: true,
              is_doorbell: false,
            },
            {
              id: "camera.nursery",
              name: "Nursery",
              stream_kind: "snapshot",
            },
          ],
          locks: [{ id: "lock.front_door", name: "Front Lock" }],
          garages: [{ id: "cover.garage_door", name: "Main Garage" }],
        },
      },
    });

    const htmlOut = renderToHtml(renderSystemSharedView(store));
    assert.ok(htmlOut.includes("sortable-row-stacked"));
    assert.ok(!htmlOut.includes("doorbell-status"));
    assert.ok(htmlOut.includes("RTSP"));
    assert.ok(htmlOut.includes("MJPEG"));
    assert.ok(htmlOut.includes("Snapshot"));
    assert.ok(htmlOut.includes("Doorbell"));
    assert.ok(htmlOut.includes("Listen"));
    assert.ok(htmlOut.includes("Talk"));
    assert.ok(htmlOut.includes("Reply"));
    assert.ok(htmlOut.includes("Label: Driveway"));
    assert.ok(htmlOut.includes("Unlock: Main Garage"));
    assert.ok(htmlOut.includes("Configure"));

    // Open Camera Options modal for Driveway, edit label + bind Front Lock, and save
    openCameraConfigModal(store, "camera.driveway");
    assert.equal(store.cameraConfigModal.open, true);
    assert.equal(store.cameraConfigModal.label, "Driveway");
    assert.equal(store.cameraConfigModal.unlockEntity, "cover.garage_door");
    const dlgHtml = renderToHtml(renderCameraConfigDialog(store));
    assert.ok(dlgHtml.includes("Camera options"));
    assert.ok(dlgHtml.includes("Front Lock"));
    assert.ok(dlgHtml.includes("Main Garage"));

    store.cameraConfigModal = {
      ...store.cameraConfigModal,
      label: "Driveway Cam",
      showListen: true,
      unlockEntity: "lock.front_door",
    };
    saveCameraConfigModal(store);
    assert.equal(store.cameraConfigModal.open, false);
    assert.equal(
      (store.state?.system_config?.camera_configs || {})["camera.driveway"]?.label,
      "Driveway Cam",
    );
    assert.equal(
      (store.state?.system_config?.camera_configs || {})["camera.driveway"]?.unlock_entity,
      "lock.front_door",
    );
  });
});
