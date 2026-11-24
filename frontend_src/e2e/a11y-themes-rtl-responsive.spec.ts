/**
 * WCAG 2.2 AA Accessibility (`@axe-core/playwright`), Light & Dark HA Themes,
 * Desktop (`1440×900`) & Mobile (`360×800`) Responsive Viewports, and LTR / RTL (`dir="rtl"`)
 * Zero-Overflow Verification Suite.
 */

import { expect, test } from "@playwright/test";
import {
  expectZeroAxeViolations,
  expectZeroHorizontalOverflow,
  mountStudio,
} from "./studio-harness.js";

const CORE_ROUTES: ReadonlyArray<{ label: string; path: string; openDrawers?: boolean }> = [
  { label: "Managed devices", path: "/latter/devices" },
  { label: "Discovered devices", path: "/latter/devices/discovered" },
  { label: "System -> Overview", path: "/latter/system/overview" },
  { label: "System -> Shared entities", path: "/latter/system/shared" },
  { label: "System -> Photos", path: "/latter/system/photos" },
  { label: "System -> Media & remotes", path: "/latter/system/remotes" },
  { label: "System -> Device groups", path: "/latter/system/groups", openDrawers: true },
  { label: "System -> BLE & Area presence", path: "/latter/system/presence", openDrawers: true },
  { label: "System -> Tools", path: "/latter/system/tools", openDrawers: true },
  { label: "Device -> Overview", path: "/latter/devices/sub_desk/overview" },
  { label: "Device -> Overview (Sleeping)", path: "/latter/devices/sub_pocket/overview" },
  { label: "Device -> Display", path: "/latter/devices/sub_desk/display" },
  { label: "Device -> Interface", path: "/latter/devices/sub_desk/interface" },
  { label: "Device -> Audio", path: "/latter/devices/sub_desk/audio" },
  { label: "Device -> Power", path: "/latter/devices/sub_desk/power" },
  { label: "Device -> Presence", path: "/latter/devices/sub_pocket/presence" },
  { label: "Device -> Tools", path: "/latter/devices/sub_desk/tools", openDrawers: true },
];

test.describe("WCAG 2.2 AA axe-core, Light/Dark Themes, Mobile 360x800 & RTL E2E", () => {
  for (const darkMode of [false, true]) {
    const themeLabel = darkMode ? "Dark theme" : "Light theme";

    test(`passes @axe-core/playwright WCAG 2.2 AA with 0 violations across all views & modals (${themeLabel})`, async ({
      page,
    }) => {
      await mountStudio(page, {
        path: "/latter/devices",
        darkMode,
        customizeHub: (hub) => {
          hub.issues = [
            {
              issue_id: "iss_1",
              kind: "outdated_firmware",
              severity: "warning",
              subentry_id: "sub_desk",
              device_title: "Desk Assistant",
              detail: "Core rev 2026112202 < 2026112303",
            },
          ];
        },
      });

      if (darkMode) {
        await expect(page.locator("latter-studio")).toHaveAttribute("dark", "");
      } else {
        await expect(page.locator("latter-studio")).not.toHaveAttribute("dark");
      }

      for (const route of CORE_ROUTES) {
        await page.evaluate((nextPath) => {
          window.history.pushState(null, "", nextPath);
          window.dispatchEvent(new Event("location-changed"));
        }, route.path);
        await page.waitForTimeout(30);

        if (route.openDrawers) {
          for (let i = 0; i < 3; i += 1) {
            const nextClosed = page
              .locator("latter-studio main details:not([open]) > summary")
              .and(page.locator(":visible"))
              .first();
            if ((await nextClosed.count()) === 0) break;
            await nextClosed.click();
          }
        }

        await expectZeroAxeViolations(page, `${themeLabel} :: ${route.label}`);
      }

      // Also audit open HTML5 <dialog> modals in top-layer (`Add shortcut` + `Confirm`)
      await page.evaluate(() => {
        window.history.pushState(null, "", "/latter/devices/sub_desk/interface");
        window.dispatchEvent(new Event("location-changed"));
      });
      await page.locator("#btn-add-dock-item").click();
      await expect(page.locator("#latter-shortcut-modal")).toBeVisible();
      await expectZeroAxeViolations(page, `${themeLabel} :: Shortcut modal`);
      await page.locator("#latter-shortcut-modal").getByRole("button", { name: "Cancel" }).click();

      await page.evaluate(() => {
        window.history.pushState(null, "", "/latter/devices/sub_desk/tools");
        window.dispatchEvent(new Event("location-changed"));
      });
      await page.getByRole("button", { name: "Clear PIN" }).click();
      await expect(page.locator("#latter-confirm-modal")).toBeVisible();
      await expectZeroAxeViolations(page, `${themeLabel} :: Confirm modal`);
      await page.locator("#latter-confirm-modal").getByRole("button", { name: "Cancel" }).click();
    });
  }

  test("adapts cleanly to Mobile 360x800 viewport with drawer menu toggle and zero horizontal overflow", async ({
    page,
  }) => {
    await mountStudio(page, {
      path: "/latter/system/overview",
      viewport: { width: 360, height: 800 },
    });

    await expect(page.locator("latter-studio")).toHaveAttribute("narrow", "");
    await expect(page.locator("latter-studio")).toHaveAttribute("show-menu", "");

    // Mobile hamburger button is visible and dispatches `hass-toggle-menu`
    const menuBtn = page.locator(".ha-menu-btn");
    await expect(menuBtn).toBeVisible();
    await menuBtn.click();
    const toggleCount = await page.evaluate(
      () => (window as unknown as { __toggledSidebarCount: number }).__toggledSidebarCount,
    );
    expect(toggleCount).toBe(1);

    // Columns stack vertically on 360px mobile and status tiles stay compact 2x2 without overflow
    for (const mobilePath of [
      "/latter/system/overview",
      "/latter/system/shared",
      "/latter/system/presence",
      "/latter/devices",
      "/latter/devices/sub_desk/overview",
      "/latter/devices/sub_desk/display",
      "/latter/devices/sub_desk/interface",
    ]) {
      await page.evaluate((p) => {
        window.history.pushState(null, "", p);
        window.dispatchEvent(new Event("location-changed"));
      }, mobilePath);
      await page.waitForTimeout(25);
      await expectZeroHorizontalOverflow(page, `Mobile 360x800 :: ${mobilePath}`);
    }
  });

  test("mirrors layout cleanly in RTL (dir='rtl') across Desktop 1440x900 and Mobile 360x800 with zero overflow", async ({
    page,
  }) => {
    await mountStudio(page, {
      path: "/latter/system/overview",
      viewport: { width: 1440, height: 900 },
      dir: "rtl",
      lang: "ar",
      darkMode: true,
    });

    // Verify logical CSS places `.sidebar` to the right of `.main-area` in RTL desktop
    const layoutBoxes = await page.evaluate(() => {
      const sr = document.querySelector("latter-studio")!.shadowRoot!;
      const sidebar = sr.querySelector("aside.sidebar")!.getBoundingClientRect();
      const main = sr.querySelector("main.main-area")!.getBoundingClientRect();
      return { sidebarLeft: sidebar.left, mainLeft: main.left, mainRight: main.right };
    });
    expect(layoutBoxes.sidebarLeft).toBeGreaterThanOrEqual(layoutBoxes.mainRight - 2);

    for (const rtlPath of [
      "/latter/system/overview",
      "/latter/system/presence",
      "/latter/devices",
      "/latter/devices/sub_desk/overview",
      "/latter/devices/sub_desk/interface",
    ]) {
      await page.evaluate((p) => {
        window.history.pushState(null, "", p);
        window.dispatchEvent(new Event("location-changed"));
      }, rtlPath);
      await page.waitForTimeout(25);
      await expectZeroHorizontalOverflow(page, `RTL 1440x900 :: ${rtlPath}`);
    }
    await expectZeroAxeViolations(page, "RTL Dark :: Device Interface");

    // Resize to Mobile 360x800 in RTL and verify zero horizontal overflow
    await page.setViewportSize({ width: 360, height: 800 });
    await page.waitForTimeout(25);
    await expectZeroHorizontalOverflow(page, "RTL 360x800 :: Device Interface");
  });
});
