/**
 * Playwright E2E tests for Device Groups, Staged Batch Controls, Non-Detaching `Do Not Disturb`
 * (`group_tier = null`), WAI-ARIA Entity Combobox, and Shared Confirmation Dialogs.
 */

import { expect, test } from "@playwright/test";
import {
  expectZeroAxeViolations,
  expectZeroHorizontalOverflow,
  mountStudio,
} from "./studio-harness.js";

test.describe("Device Groups, Non-Detaching DND & WAI-ARIA Modals E2E", () => {
  test("gates Group Baseline Drawer capabilities and preserves Device Group when toggling Do Not Disturb", async ({
    page,
  }) => {
    // 1. On Device -> Overview, toggling `Do not disturb` (`group_tier = null`) NEVER detaches `wall_panels` -> `Custom`!
    const ctrl = await mountStudio(page, { path: "/latter/devices/sub_desk/overview" });
    const groupSelect = page.locator("#cfg-device_group");
    await expect(groupSelect).toHaveValue("wall_panels");

    await page
      .locator("#card-device-quick-actions")
      .getByRole("switch", { name: "Do not disturb" })
      .click();
    await expect
      .poll(() =>
        ctrl.wsCalls.some(
          (m) =>
            m.command === "save_device_config" &&
            ((m.payload as Record<string, unknown>)?.config as Record<string, unknown>)
              ?.do_not_disturb === true,
        ),
      )
      .toBe(true);
    await expect(groupSelect).toHaveValue("wall_panels");

    // 2. System -> Device groups: Group Baseline Drawer `hw_jpeg` gating (`wall_panels` vs `pocket_carry`)
    await page.locator("#tab-scope-system").click();
    await page.locator("a[data-view='system_sync']").click();
    await expect(page.locator("#view-system_sync")).toBeVisible();

    const wallBox = page.locator("#group-box-wall_panels");
    await wallBox.locator("details.sub-collapsible > summary").first().click();
    await wallBox.getByRole("switch", { name: /Include interface & shortcuts/ }).click();
    await expect(wallBox).toContainText("Doorbell ring popup");

    const pocketBox = page.locator("#group-box-pocket_carry");
    await pocketBox.locator("details.sub-collapsible > summary").first().click();
    await pocketBox.getByRole("switch", { name: /Include interface & shortcuts/ }).click();
    await expect(pocketBox).toContainText("Interface & shortcuts");
    await expect(pocketBox).not.toContainText("Doorbell ring popup");

    // 3. Staged Batch controls: staging `Do not disturb` across All Devices shows confirmation dialog
    //    with blast radius ("3 Devices") and applies WITHOUT detaching any Device to `Custom`!
    const batchCard = page.locator("#card-batch-controls");
    await expect(page.locator("#btn-batch-apply")).toBeDisabled();
    await batchCard.locator("summary", { hasText: "Power" }).click();
    await batchCard
      .locator(".settings-row", { hasText: "Do not disturb" })
      .locator('input[type="checkbox"]')
      .click();
    await expect(page.locator("#btn-batch-apply")).toBeEnabled();

    await page.locator("#btn-batch-apply").click();
    const confirmModal = page.locator("#latter-confirm-modal");
    await expect(confirmModal).toBeVisible();
    await expect(confirmModal.locator(".confirm-blast-badge")).toContainText("3 Devices");
    await page.locator("#btn-confirm-modal-accept").click();
    await expect(confirmModal).toBeHidden();

    expect(ctrl.wsCalls.some((m) => m.command === "apply_batch_device_setting")).toBe(true);
    await expect(page.locator("#group-box-custom")).toContainText("0 Devices");
  });

  test("operates WAI-ARIA Entity Combobox keyboard filtering/Escape/Enter and Sortable List reordering", async ({
    page,
  }) => {
    const ctrl = await mountStudio(page, { path: "/latter/devices/sub_desk/interface" });

    // 1. WAI-ARIA 1.2 Entity Combobox inside Add Shortcut modal
    await page.locator("#btn-add-dock-item").click();
    const scModal = page.locator("#latter-shortcut-modal");
    await expect(scModal).toBeVisible();

    await page.locator("#shortcut-tab-entity").click();
    const cbInput = page.locator("#shortcut-entity-select");
    await expect(cbInput).toHaveAttribute("role", "combobox");
    await expect(cbInput).toHaveAttribute("aria-expanded", "false");

    const initialDisplayValue = await cbInput.inputValue();

    // Typing filters listbox without mutating committed entity; Escape restores display label
    await cbInput.fill("kitchen island");
    await expect(cbInput).toHaveAttribute("aria-expanded", "true");
    await expect(scModal.locator("[role='option']")).toHaveCount(2);

    await cbInput.press("Escape");
    await expect(cbInput).toHaveAttribute("aria-expanded", "false");
    await expect(cbInput).toHaveValue(initialDisplayValue);

    // Re-filter, ArrowDown to second match ("Kitchen Island Pendant"), and press Enter to commit
    await cbInput.fill("kitchen island");
    await cbInput.press("ArrowDown");
    await cbInput.press("Enter");
    await expect(cbInput).toHaveAttribute("aria-expanded", "false");
    await expect(cbInput).toHaveValue("Kitchen Island Pendant");
    await scModal.getByRole("button", { name: "Cancel" }).click();
    await expect(scModal).toBeHidden();

    // 2. Sortable App Dock keyboard move (`next`) reorders items cleanly and persists via WS
    const dockContainer = page.locator("#dock-shortcuts-container");
    const firstTitleBefore = await dockContainer
      .locator("[data-sortable-index] .shortcut-item-title")
      .nth(0)
      .textContent();
    await dockContainer.locator("button[data-move-dir='next']").first().click();
    await expect(
      dockContainer.locator("[data-sortable-index] .shortcut-item-title").nth(1),
    ).toHaveText(firstTitleBefore!);
    await expect
      .poll(() => ctrl.wsCalls.some((m) => m.command === "save_device_config"))
      .toBe(true);
  });

  test("filters MDI icons by weight, searches smart-home synonyms, styles shortcut badges, and passes axe WCAG 2.2 AA in light and dark themes", async ({
    page,
  }) => {
    for (const darkMode of [false, true]) {
      const themeLabel = darkMode ? "dark" : "light";
      const ctrl = await mountStudio(page, {
        path: "/latter/devices/sub_desk/interface",
        darkMode,
      });

      // Open Add custom dock shortcut modal
      await page.locator("#btn-add-dock-item").click();
      const scModal = page.locator("#latter-shortcut-modal");
      await expect(scModal).toBeVisible();

      // 1. Style filter (`All` | `Solid` | `Outline`) updates picker grid & counts
      const styleFilter = scModal.locator("#shortcut-icon-style-filter");
      await expect(styleFilter).toHaveAttribute("role", "radiogroup");
      await expect(scModal.locator("#shortcut-icon-style-all")).toHaveAttribute(
        "aria-checked",
        "true",
      );

      // Wait for lazy MDI chunk so outline + synonym search operate across full 7,447 catalog
      const iconInput = scModal.locator("#shortcut-icon-input");
      await iconInput.fill("goodnight");
      await expect(
        scModal.locator(".mdi-picker-btn[title='mdi:weather-night']"),
      ).toBeVisible();

      // Switch to Outline filter -> every rendered icon button must end in `-outline`
      await scModal.locator("#shortcut-icon-style-outline").click();
      await expect(scModal.locator("#shortcut-icon-style-outline")).toHaveAttribute(
        "aria-checked",
        "true",
      );
      const outlineTitles = await scModal
        .locator(".mdi-picker-btn")
        .evaluateAll((els) => els.map((el) => el.getAttribute("title") || ""));
      expect(outlineTitles.length).toBeGreaterThan(0);
      expect(outlineTitles.every((t) => t.endsWith("-outline"))).toBe(true);

      // Switch to Solid filter -> zero `-outline` icons and `ac` synonym surfaces `mdi:air-conditioner`
      await scModal.locator("#shortcut-icon-style-solid").click();
      await iconInput.fill("ac");
      await expect(
        scModal.locator(".mdi-picker-btn[title='mdi:air-conditioner']"),
      ).toBeVisible();
      const solidAcTitles = await scModal
        .locator(".mdi-picker-btn")
        .evaluateAll((els) => els.map((el) => el.getAttribute("title") || ""));
      expect(solidAcTitles.every((t) => !t.endsWith("-outline"))).toBe(true);

      // Search `lamp` -> direct `mdi:lamp` comes first AND synonym `mdi:lightbulb` appears
      await iconInput.fill("lamp");
      await expect(scModal.locator(".mdi-picker-btn").first()).toHaveAttribute(
        "title",
        "mdi:lamp",
      );
      const lightbulbBtn = scModal.locator(".mdi-picker-btn[title='mdi:lightbulb']");
      await expect(lightbulbBtn).toBeVisible();
      await lightbulbBtn.click();
      await expect(lightbulbBtn).toHaveAttribute("aria-pressed", "true");

      // 2. Icon style (`Frosted glass` | `Inverted badge`) & Accent color live-update preview badge
      const previewBadge = scModal.locator("#shortcut-icon-preview");
      await expect(previewBadge).toHaveClass(/shortcut-icon-badge/);
      await expect(previewBadge).not.toHaveClass(/badge-inverted/);

      await scModal.locator("#shortcut-badge-style-inverted").click();
      await expect(scModal.locator("#shortcut-badge-style-inverted")).toHaveAttribute(
        "aria-checked",
        "true",
      );
      await scModal.locator("#shortcut-accent-gold").click();
      await expect(scModal.locator("#shortcut-accent-gold")).toHaveAttribute(
        "aria-checked",
        "true",
      );
      await expect(previewBadge).toHaveClass(/shortcut-icon-badge/);
      await expect(previewBadge).toHaveClass(/badge-inverted/);
      await expect(previewBadge).toHaveClass(/accent-gold/);
      expect(await previewBadge.getAttribute("style")).toBeNull();

      // Audit active Shortcut Modal with style filter, inverted badge, and accent under axe-core
      await expectZeroAxeViolations(
        page,
        `Upgraded Shortcut modal (${themeLabel}, inverted + gold)`,
      );
      await expectZeroHorizontalOverflow(page, `Upgraded Shortcut modal (${themeLabel})`);

      // 3. Save custom shortcut and verify WS payload + live styled badge in App Dock
      await scModal.locator("#shortcut-label-input").fill("Warm Glow");
      await scModal.locator("#shortcut-save-btn").click();
      await expect(scModal).toBeHidden();

      const customDockRow = page
        .locator("#dock-shortcuts-container .dock-row")
        .filter({ hasText: "Warm Glow" });
      await expect(customDockRow).toBeVisible();
      await expect(customDockRow.locator(".shortcut-icon-badge")).toHaveClass(
        /badge-inverted.*accent-gold|accent-gold.*badge-inverted/,
      );

      await expect
        .poll(() =>
          ctrl.wsCalls.some((m) => {
            if (m.command !== "save_device_config") return false;
            const cfg = (m.payload as Record<string, unknown>)?.config as
              | Record<string, unknown>
              | undefined;
            const items = cfg?.dock_items as Array<Record<string, unknown>> | undefined;
            return Boolean(
              items?.some(
                (it) =>
                  it.label === "Warm Glow" &&
                  it.icon === "mdi:lightbulb" &&
                  it.badge_style === "inverted" &&
                  it.accent === "gold",
              ),
            );
          }),
        )
        .toBe(true);
    }
  });
});
