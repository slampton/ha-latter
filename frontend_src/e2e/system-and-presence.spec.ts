/**
 * Playwright E2E tests for System views (`M-P0-14`, `D-072`, `D-073`, `D-074`, `D-075`, `D-076`):
 * - `System -> Overview` two-card layout (`Status` + Column 2 `Area deployment`), `Sleeping` vs
 *   `Away` vs unexpected `Offline` vs `<= 20%` discharging `Low battery` health badges
 * - `System -> BLE & Area presence` (`D-075` Area-Aware `Ambient Light` & 7-day Recorder
 *   auto-calibration, occupancy fusion controls, Walk-Around BLE calibration handoff)
 * - `System -> Shared entities` (`D-074` Broadcast speakers & phrases, native `<select>`,
 *   `D-073` Camera options modal) & `System -> Photos` (`D-072` pagination, crop, XHR upload, import)
 */

import { expect, test } from "@playwright/test";
import { PHOTO_LIBRARY_PAGE_SIZE } from "../src/constants.js";
import { mountStudio } from "./studio-harness.js";

test.describe("System Overview, Presence, Shared Entities & Photos E2E", () => {
  test("renders D-076 two-card System -> Overview and distinguishes Sleeping, Away, Offline & Low battery", async ({
    page,
  }) => {
    // 1. Default hub has Wrist Assist at 16% discharging -> warns "1 low battery" while Pocket Assistant (Sleeping) & Alex's Phone (Away) stay non-offline
    await mountStudio(page, { path: "/latter/system/overview" });

    const col1Status = page.locator(".columns > .column").nth(0).locator("#card-system-status");
    const col2Deploy = page.locator(".columns > .column").nth(1).locator("#card-area-deployment");
    await expect(col1Status).toBeVisible();
    await expect(col2Deploy).toBeVisible();
    await expect(page.locator("#card-system-capabilities")).toHaveCount(0);

    await expect(page.locator("#sys-status-chip")).toContainText("1 low battery");
    await expect(page.locator("#sys-tile-devices .status-tile-meta")).toContainText(
      "1 low battery • 1 sleeping • 1 away",
    );
    // Sleeping roaming Pocket Assistant still surfaces in Roaming rollup & Kitchen deployment box
    await expect(page.locator("#sys-deploy-roaming")).toContainText("Pocket Assistant (Kitchen)");
    await expect(col2Deploy).toContainText("Here: Pocket Assistant");

    // 2. When Wrist Assist is charging (16% charging), system reports "Healthy" (chip-success)
    await mountStudio(page, {
      path: "/latter/system/overview",
      customizeHub: (hub) => {
        hub.devices["sub_wrist"]!.entry.is_charging = true;
        hub.devices["sub_wrist"]!.entry.is_usb_connected = true;
      },
    });
    await expect(page.locator("#sys-status-chip")).toContainText("Healthy");
    await expect(page.locator("#sys-status-chip")).toHaveClass(/chip-success/);

    // 3. Unexpected hardware disconnect on Desk Assistant flags "1 offline" warning
    await mountStudio(page, {
      path: "/latter/system/overview",
      customizeHub: (hub) => {
        hub.devices["sub_wrist"]!.entry.battery_level = 85;
        hub.devices["sub_desk"]!.entry.is_online = false;
        hub.devices["sub_desk"]!.entry.status_code = "offline";
        hub.devices["sub_desk"]!.entry.status_label = "Offline";
      },
    });
    await expect(page.locator("#sys-status-chip")).toContainText("1 offline");
    await expect(page.locator("#sys-status-chip")).toHaveClass(/chip-warning/);
  });

  test("manages D-075 Area-Aware Ambient Light, 7-day Recorder auto-calibration, occupancy mode & BLE handoff", async ({
    page,
  }) => {
    const ctrl = await mountStudio(page, { path: "/latter/system/presence" });

    const studioBox = page.locator("#area-box-harbor_studio");
    await expect(studioBox).toBeVisible();
    await expect(studioBox).toContainText("18.5 lx (64%)");

    // Change occupancy fusion mode on Harbor Studio -> sends `set_area_fusion`
    const modeSelect = studioBox.locator('select[aria-label*="Harbor Studio"]').first();
    await modeSelect.selectOption("ble_and_sensor");
    expect(
      ctrl.wsCalls.some(
        (m) =>
          m.command === "set_area_fusion" &&
          (m.payload as Record<string, unknown>)?.area_id === "harbor_studio" &&
          (m.payload as Record<string, unknown>)?.mode === "ble_and_sensor",
      ),
    ).toBe(true);

    // Open Sensor & threshold settings drawer and test D-075 Ambient Light bounds + 7-day calibration
    await studioBox.locator("details.sub-collapsible > summary").click();
    const darkInput = studioBox.locator('input.lux-number-input').nth(0);
    const brightInput = studioBox.locator('input.lux-number-input').nth(1);
    await expect(darkInput).toHaveValue("0.8");
    await expect(brightInput).toHaveValue("45");

    // Guard: dark_lux >= bright_lux shows error toast and reverts input
    await darkInput.fill("60");
    await darkInput.dispatchEvent("change");
    await expect(page.locator(".toast.error")).toBeVisible();
    await expect(darkInput).toHaveValue("0.8");
    await page.locator(".toast.error button").click();

    // Per-Area 7-day Recorder auto-calibration updates bounds (0.6 / 52.4)
    await studioBox.getByRole("button", { name: "Auto-calibrate" }).click();
    expect(
      ctrl.wsCalls.some(
        (m) =>
          m.command === "calibrate_area_illuminance" &&
          (m.payload as Record<string, unknown>)?.area_id === "harbor_studio",
      ),
    ).toBe(true);
    await expect(darkInput).toHaveValue("0.6");
    await expect(brightInput).toHaveValue("52.4");

    // Header 1-click "Auto-calibrate lux" calibrates all Areas
    await page.locator("#card-area-presence .card-header-actions button").click();
    expect(
      ctrl.wsCalls.some(
        (m) =>
          m.command === "calibrate_area_illuminance" &&
          !(m.payload as Record<string, unknown>)?.area_id,
      ),
    ).toBe(true);

    // Clicking "Calibrate" on Harbor Studio highlights `#ble-calibrate-target-box.handoff-active`
    await studioBox.getByRole("button", { name: "Calibrate", exact: true }).click();
    await expect(page.locator("#ble-calibrate-target-box")).toHaveClass(/handoff-active/);
    await expect(page.locator("#ble-calibrate-area-select")).toHaveValue("harbor_studio");
  });

  test("configures D-074 Broadcast speakers & phrases and D-073 Camera options modal in Shared entities", async ({
    page,
  }) => {
    const ctrl = await mountStudio(page, {
      path: "/latter/system/shared",
      customizeHub: (hub) => {
        // Populate >10 speakers & cameras in catalog via default + verify native <select> (never combobox)
        hub.systemConfig.broadcast_speakers = [
          "media_player.kitchen_speaker",
          "media_player.studio_monitors",
        ];
      },
    });

    const speakerDomain = page.locator("#hub-domain-broadcast_speakers");
    const phraseDomain = page.locator("#hub-domain-broadcast_phrases");
    const camerasList = page.locator("#cameras-list");

    await expect(speakerDomain).toContainText("Kitchen");
    await expect(phraseDomain.locator("input[type='text']").first()).toHaveValue("Dinner is ready");
    await expect(page.locator("#view-shared_entities input[role='combobox']")).toHaveCount(0);
    await expect(speakerDomain.locator("select").first()).toBeVisible();
    await expect(camerasList.locator("select").first()).toBeVisible();

    // Declarative camera capability chips (`RTSP`, `MJPEG`, `Snapshot`, `Doorbell`, `Label: Courtyard`)
    await expect(camerasList).toContainText("RTSP");
    await expect(camerasList).toContainText("MJPEG");
    await expect(camerasList).toContainText("Snapshot");
    await expect(camerasList).toContainText("Doorbell");
    await expect(camerasList).toContainText("Label: Courtyard");

    // Open Camera Options modal for Courtyard (`camera.courtyard`, index 1), edit label + bind Front Entry Lock
    await camerasList.getByRole("button", { name: "Configure" }).nth(1).click();
    const camModal = page.locator("#latter-camera-config-modal");
    await expect(camModal).toBeVisible();
    await expect(page.locator("#cam-cfg-label")).toHaveValue("Courtyard");

    await page.locator("#cam-cfg-label").fill("Courtyard Gate");
    await page.locator("#cam-cfg-unlock").selectOption("lock.front_entry");
    await page.locator("#cam-cfg-save").click();
    await expect(camModal).toBeHidden();

    await expect
      .poll(() =>
        ctrl.wsCalls.some(
          (m) =>
            m.command === "save_system_config" &&
            Boolean(
              (
                ((m.payload as Record<string, unknown>)?.config as Record<string, unknown>)
                  ?.camera_configs as Record<string, { label?: string; unlock_entity?: string }>
              )?.["camera.courtyard"]?.unlock_entity === "lock.front_entry",
            ),
        ),
      )
      .toBe(true);
    await expect(camerasList).toContainText("Label: Courtyard Gate");
  });

  test("renders D-072 Photo library pagination, crop editor, multipart XHR upload, and HA Media import", async ({
    page,
  }) => {
    const ctrl = await mountStudio(page, {
      path: "/latter/system/photos",
      customizeHub: (hub) => {
        for (let i = 0; i < PHOTO_LIBRARY_PAGE_SIZE; i += 1) {
          hub.photos.push({
            id: `photo:extra_${i}`,
            name: `Gallery Shot ${i + 1}`,
            kind: "uploaded",
            source_kind: "upload",
            deletable: true,
            thumb_url: "http://studio.local/thumb/extra.png",
            collections: [],
          });
        }
      },
    });

    await expect(page.locator(".photo-tile")).toHaveCount(PHOTO_LIBRARY_PAGE_SIZE);
    await expect(page.locator("#btn-photos-next-page")).toBeVisible();

    // Filter to Coastal collection -> shows Forest Mountains + Harbor Sunset
    await page.locator("[data-collection-filter='col_coastal']").click();
    await expect(page.locator(".photo-tile")).toHaveCount(2);

    // Click Harbor Sunset -> opens Photo Editor & Crop modal with real <canvas>
    await page.locator(".photo-tile-thumb-btn").nth(1).click();
    const editModal = page.locator("#latter-photo-edit-modal");
    await expect(editModal).toBeVisible();
    await expect(page.locator("#latter-edit-crop-canvas")).toBeVisible();
    await editModal.getByRole("button", { name: "Save" }).click();
    expect(ctrl.wsCalls.some((m) => m.command === "update_photo_metadata")).toBe(true);

    // Open Upload modal, stage a PNG file, create an inline collection, and upload via Bearer XHR
    await page.getByRole("button", { name: "Upload photos" }).click();
    const uploadModal = page.locator("#latter-photo-upload-modal");
    await expect(uploadModal).toBeVisible();
    await uploadModal.locator("input[type='file']").setInputFiles([
      {
        name: "bay_sunrise.png",
        mimeType: "image/png",
        buffer: Buffer.from(
          "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
          "base64",
        ),
      },
      {
        name: "harbor_dusk.png",
        mimeType: "image/png",
        buffer: Buffer.from(
          "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
          "base64",
        ),
      },
    ]);
    await expect(page.locator("#latter-upload-crop-canvas")).toBeVisible();
    await uploadModal.getByRole("button", { name: /Upload all/ }).click();
    await expect(uploadModal).toBeHidden();
    expect(ctrl.uploadedForms).toHaveLength(2);
    expect(ctrl.uploadedForms[0]?.authHeader).toBe("Bearer e2e-admin-bearer-token");

    // Open Import from Media modal, navigate into CoastalTrips, select all, and import
    await page.getByRole("button", { name: "Import from Media" }).click();
    const importModal = page.locator("#latter-media-import-modal");
    await expect(importModal).toBeVisible();
    await importModal.getByRole("button", { name: /CoastalTrips/ }).click();
    await page.locator("#btn-media-select-all").click();
    await page.locator("#btn-media-new-col-from-folder").click();
    await page.locator("#btn-media-import-confirm").click();
    await expect(importModal).toBeHidden();
    expect(ctrl.wsCalls.some((m) => m.command === "import_media_photos")).toBe(true);
  });
});
