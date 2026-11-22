/**
 * Playwright E2E tests for Devices table & per-Device views (`M-P0-14`, `M-P3-06`, `D-071`–`D-077`):
 * - `Devices` list row click, Ctrl-click `_blank`, keyboard `Tab`/`Enter`/`Space`, & `Discovered` ignore/restore
 * - `Device -> Overview` (`Status` tiles, `Do not disturb` sleep-safe vs offline disabled quick actions)
 * - `Device -> Display` (`Ambient Light` live status, `Photo Frame` picker filtering `dynamic_preset`)
 * - `Device -> Interface` (24-item App Dock live switch sync, lazy `latter-studio-mdi.js` 7,447-icon load,
 *   `hw_jpeg` Cameras modal gate, Broadcast speakers subset, Single-App Mode, & `focusSafe` live-push safety)
 * - `Device -> Audio`, `Device -> Power` (`Bedtime mode`), & `Device -> Tools` (`device_telemetry` live metrics)
 */

import { expect, test } from "@playwright/test";
import { mountStudio } from "./studio-harness.js";

test.describe("Devices List & Per-Device Views E2E", () => {
  test("supports M-P3-06 row click, Ctrl-click new tab, keyboard Enter/Space, and Discovered ignore/restore", async ({
    page,
  }) => {
    const ctrl = await mountStudio(page, { path: "/latter" });
    await expect(page.locator("#unified-page-title")).toContainText("Managed devices");

    const deskRow = page.locator("table.data-table tbody tr", { hasText: "Desk Assistant" });
    await expect(deskRow).toContainText("Wall & Desk Panels");

    // Ctrl-click on row opens `_blank` without leaving Managed devices
    await deskRow.locator("td").nth(1).click({ modifiers: ["Control"] });
    const popups = await page.evaluate(
      () => (window as unknown as { __openedPopups: Array<{ url: string }> }).__openedPopups,
    );
    expect(popups[0]?.url).toBe("/latter/devices/sub_desk");
    await expect(page.locator("#view-select_device_prompt")).toBeVisible();

    // Plain row click on non-link cell opens Device -> Overview and updates URL via pushState
    await deskRow.locator("td").nth(2).click();
    await expect(page.locator("#view-dashboard")).toBeVisible();
    expect(new URL(page.url()).pathname).toBe("/latter/devices/sub_desk/overview");

    // Return to Managed via sidebar back link and navigate via keyboard Space on link
    await page.locator("#nav-scope-device .nav-back-btn").click();
    await expect(page.locator("#view-select_device_prompt")).toBeVisible();
    const pocketLink = page
      .locator("table.data-table tbody tr", { hasText: "Pocket Assistant" })
      .locator("a");
    await pocketLink.focus();
    await page.keyboard.press("Space");
    await expect(page.locator("#view-dashboard")).toBeVisible();
    await expect(page.locator("#unified-page-title")).toContainText("Pocket Assistant");

    // Sleeping battery Pocket Assistant renders `.offline-banner`, disables live Quick action tiles,
    // yet keeps sleep-safe `Do not disturb` switch ENABLED!
    await expect(page.locator(".offline-banner")).toBeVisible();
    const qaButtons = page.locator("#card-device-quick-actions .quick-action-btn");
    await expect(qaButtons.first()).toBeDisabled();
    const dndSwitch = page
      .locator("#card-device-quick-actions")
      .getByRole("switch", { name: "Do not disturb" });
    await expect(dndSwitch).toBeEnabled();

    // Discovered devices: Ignore and Restore unbound Latter hardware
    await page.locator("#nav-scope-device .nav-back-btn").click();
    await page.locator("a[data-view='discovered_devices']").click();
    await expect(page.locator("#view-discovered_devices")).toBeVisible();
    await expect(page.locator("#card-discovered-latter")).toContainText("Entryway Panel");
    await page.locator("#card-discovered-latter").getByRole("button", { name: "Ignore" }).click();
    expect(ctrl.wsCalls.some((m) => m.command === "ignore_discovered_device")).toBe(true);
    await page.locator("#card-discovered-latter summary").click();
    await page.locator("#card-discovered-latter").getByRole("button", { name: "Restore" }).click();
    expect(ctrl.wsCalls.some((m) => m.command === "unignore_discovered_device")).toBe(true);
  });

  test("renders Display Ambient Light status, filters dynamic_preset in Photo Frame picker, and hides Never rows", async ({
    page,
  }) => {
    const ctrl = await mountStudio(page, { path: "/latter/devices/sub_desk/display" });

    // D-075 Ambient Light subtitle + contextual Bright/Dark brightness slider labels
    const brtCard = page.locator("#card-brightness");
    await expect(brtCard).toContainText("Harbor Studio");
    await expect(brtCard).toContainText("18.5 lx (64% ambient)");
    await expect(brtCard).toContainText("Bright brightness");
    await expect(brtCard).toContainText("Dark brightness");

    // Wallpaper Photo Picker includes `Day & Night Sky`; Screensaver Photo Frame picker excludes it
    await page.locator("#btn-choose-wallpaper").click();
    const pickerModal = page.locator("#latter-photo-picker-modal");
    await expect(pickerModal).toBeVisible();
    await expect(pickerModal).toContainText("Day & Night Sky");
    await pickerModal.getByRole("button", { name: "Cancel" }).click();

    await page.locator("#btn-choose-ss-photos").click();
    await expect(pickerModal).toBeVisible();
    await page.locator("#btn-picker-mode-photos").click();
    await expect(pickerModal).not.toContainText("Day & Night Sky");
    await expect(pickerModal).toContainText("Harbor Sunset");
    await pickerModal.getByRole("button", { name: "Cancel" }).click();

    // Switching `screensaver_mode` to "Never" hides Photo Frame section & style select
    await page
      .locator("#card-screensaver select[aria-label='Screensaver mode']")
      .selectOption("Never");
    await expect(page.locator("#screensaver-photo-frame-section")).toHaveCount(0);
    await expect
      .poll(() => ctrl.wsCalls.some((m) => m.command === "save_device_config"))
      .toBe(true);
  });

  test("syncs Interface App Dock switches, lazy-loads 7,447 MDI icons, gates hw_jpeg Cameras, and protects focusSafe inputs", async ({
    page,
  }) => {
    const ctrl = await mountStudio(page, { path: "/latter/devices/sub_desk/interface" });

    // 1. App Dock & Hidden from dock switch sync (real Chromium DOM property sync from retired lit.test.ts)
    const hiddenContainer = page.locator("#dock-hidden-native-apps");
    await expect(hiddenContainer.locator('input[type="checkbox"]')).toHaveCount(4);
    await hiddenContainer.locator('input[type="checkbox"]').first().click();
    await expect(hiddenContainer.locator('input[type="checkbox"]')).toHaveCount(3);
    const remainingUnchecked = await hiddenContainer
      .locator('input[type="checkbox"]')
      .evaluateAll((els) => els.every((el) => !(el as HTMLInputElement).checked));
    expect(remainingUnchecked).toBe(true);

    // 2. P4 Desk Assistant (`hw_jpeg: true`) renders `#cfg-camera_doorbell_popup` inside Cameras modal
    await expect(page.locator("#card-app-dock")).toContainText("Grid • Uncropped • 3 cameras");
    await page
      .locator("#dock-shortcuts-container")
      .getByRole("button", { name: "Configure Cameras" })
      .click();
    const appModal = page.locator("#latter-app-config-modal");
    await expect(appModal).toBeVisible();
    await expect(page.locator("#cfg-camera_doorbell_popup")).toBeVisible();
    await appModal.getByRole("button", { name: "Done" }).click();

    // 3. Configure Home hub per-Device Broadcast speakers subset pills
    await page
      .locator("#dock-shortcuts-container")
      .getByRole("button", { name: "Configure Home hub" })
      .click();
    await expect(page.locator("#broadcast-speakers-pills")).toBeVisible();
    await page
      .locator("#broadcast-speakers-pills button", { hasText: "Studio Monitors" })
      .click();
    await appModal.getByRole("button", { name: "Done" }).click();

    // 4. Open Add Shortcut modal -> triggers real dynamic `import("./latter-studio-mdi.js?v=...")`
    //    and protects `#shortcut-label-input` via `focusSafe()` during live WebSocket pushes!
    await page.locator("#btn-add-dock-item").click();
    const scModal = page.locator("#latter-shortcut-modal");
    await expect(scModal).toBeVisible();

    const iconSearch = page.locator("#shortcut-icon-input");
    await iconSearch.fill("telescope");
    await expect(scModal.locator(".mdi-picker-btn[title='mdi:telescope']")).toBeVisible();

    const labelInput = page.locator("#shortcut-label-input");
    await labelInput.focus();
    await labelInput.fill("Night Sky ");
    // Push a live state update from hub while `#shortcut-label-input` is focused!
    await ctrl.pushLiveState("sub_desk");
    await expect(labelInput).toHaveValue("Night Sky ");
    await scModal.getByRole("button", { name: "Cancel" }).click();

    // 5. S3 Pocket Assistant (`hw_jpeg: false`) omits `#cfg-camera_doorbell_popup` and supports Single-App Configure
    await mountStudio(page, {
      path: "/latter/devices/sub_pocket/interface",
      customizeHub: (hub) => {
        hub.devices["sub_pocket"]!.config.home_screen_enabled = false;
        hub.devices["sub_pocket"]!.config.start_screen = "Cameras";
      },
    });
    await expect(page.locator("#card-app-dock")).toHaveCount(0);
    await page.locator("#btn-configure-start-screen").click();
    await expect(page.locator("#latter-app-config-modal")).toBeVisible();
    await expect(page.locator("#cfg-camera_default_view")).toBeVisible();
    await expect(page.locator("#cfg-camera_doorbell_popup")).toHaveCount(0);
  });

  test("renders Audio, Power Bedtime mode, and Tools Developer & telemetry live metrics", async ({
    page,
  }) => {
    const ctrl = await mountStudio(page, { path: "/latter/devices/sub_desk/audio" });
    // Stationary Desk Assistant (`native_ble_tracking: false`) hides roaming Voice Follows Me row
    await expect(page.locator("#cfg-sync_device_area")).toHaveCount(0);
    await expect(page.locator("#cfg-area_handoff")).toBeVisible();

    // Navigate to Power -> Bedtime mode card + Do not disturb
    await page.locator("#nav-btn-power").click();
    await expect(page.locator("#card-bedtime-mode")).toBeVisible();
    await expect(
      page.locator("#card-bedtime-mode").getByRole("slider", { name: "Bedtime brightness" }),
    ).toBeVisible();

    // Navigate to Tools -> expand Developer & telemetry drawer and verify live `device_telemetry` rows
    await page.locator("a[data-view='tools']").click();
    await expect(page.locator("#diag-sdk-rev")).toHaveText("2026112007");
    const devDrawer = page.locator("#card-device-diagnostics details.sub-collapsible");
    await devDrawer.locator("summary").click();
    await expect(devDrawer).toContainText("212 / 168 / 128 KB");
    await expect(devDrawer).toContainText("24,576 KB");
    await expect(devDrawer).toContainText("POWERON");

    await page.locator("#dev-telemetry-profiler").click();
    expect(
      ctrl.wsCalls.some(
        (m) =>
          m.command === "device_action" &&
          (m.payload as Record<string, unknown>)?.action === "set_profiler_on",
      ),
    ).toBe(true);

    await page.locator("#btn-refresh-telemetry").click();
    expect(
      ctrl.wsCalls.some(
        (m) =>
          m.command === "device_action" &&
          (m.payload as Record<string, unknown>)?.action === "request_telemetry",
      ),
    ).toBe(true);
  });
});
