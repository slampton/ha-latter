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
    await expect(wallBox).toContainText("Blocks");
    await expect(wallBox).not.toContainText("Archery");

    const pocketBox = page.locator("#group-box-pocket_carry");
    await pocketBox.locator("details.sub-collapsible > summary").first().click();
    await pocketBox.getByRole("switch", { name: /Include interface & shortcuts/ }).click();
    await expect(pocketBox).toContainText("Interface & shortcuts");
    await expect(pocketBox).not.toContainText("Doorbell ring popup");
    await expect(pocketBox).toContainText("Archery");
    await expect(pocketBox).not.toContainText("Blocks");

    const handheldBox = page.locator("#group-box-handhelds");
    await handheldBox.locator("details.sub-collapsible > summary").first().click();
    await handheldBox.getByRole("switch", { name: /Include interface & shortcuts/ }).click();
    await expect(handheldBox).toContainText("Blocks");
    await expect(handheldBox).toContainText("Archery");

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

  test("operates the Pinned Visual Tile-Grid Page Editor (cell placement, multi-span, page titles, keyboard move/resize, page delete) and passes axe WCAG 2.2 AA in light and dark themes", async ({
    page,
  }) => {
    for (const darkMode of [false, true]) {
      const themeLabel = darkMode ? "dark" : "light";
      const ctrl = await mountStudio(page, {
        path: "/latter/devices/sub_desk/interface",
        darkMode,
      });

      // 1. Open Configure Pinned from App Dock (sub_desk has 3×3 grid)
      const pinnedRow = page
        .locator("#dock-shortcuts-container .dock-row")
        .filter({ hasText: "Pinned" });
      await pinnedRow.getByRole("button", { name: "Configure" }).click();

      const appModal = page.locator("#latter-app-config-modal");
      await expect(appModal).toBeVisible();
      await expect(appModal).toHaveClass(/grid-editor-dialog/);
      await expect(appModal.locator(".pinned-grid-dims-chip")).toContainText("3 × 3");
      await expect(appModal.locator(".pinned-grid-empty-cell")).toHaveCount(9);

      // 2. Click empty cell (col=0, row=0) -> opens Shortcut Modal with Tile layout section
      await appModal.locator('.pinned-grid-empty-cell[data-grid-cell="0,0"]').click();
      const scModal = page.locator("#latter-shortcut-modal");
      await expect(scModal).toBeVisible();
      await expect(scModal.locator("#shortcut-span-matrix")).toBeVisible();
      await expect(scModal.locator("#shortcut-span-matrix .span-matrix-cell")).toHaveCount(9);

      // Choose Home Assistant entity, pick 2×1 span + inverted gold style, and save
      await scModal.locator("#shortcut-tab-entity").click();
      await scModal.locator("#shortcut-label-input").fill("Harbor Lights");
      await scModal.locator("#shortcut-badge-style-inverted").click();
      await scModal.locator("#shortcut-accent-gold").click();
      await scModal.locator('.span-matrix-cell[data-span-w="2"][data-span-h="1"]').click();
      await expect(scModal.locator("#shortcut-tile-size-badge")).toContainText("2 × 1");
      await scModal.locator("#shortcut-save-btn").click();

      // Reopens Pinned Visual Tile-Grid Editor with the placed 2×1 tile and 7 remaining empty cells
      await expect(scModal).toBeHidden();
      await expect(appModal).toBeVisible();
      const placedTile = appModal.locator(".pinned-grid-tile").first();
      await expect(placedTile).toBeVisible();
      await expect(placedTile).toContainText("Harbor Lights");
      await expect(placedTile.locator(".pinned-tile-span-badge")).toContainText("2×1");
      await expect(appModal.locator(".pinned-grid-empty-cell")).toHaveCount(7);

      // 3. Edit Page 1 custom title and persist pinned_page_titles
      const titleInput = appModal.locator("#pinned-page-title-input");
      await titleInput.fill("Harbor Area");
      await titleInput.press("Enter");
      await expect(appModal.locator("#pinned-page-tab-0")).toContainText("Harbor Area");

      // 4. Keyboard move (`ArrowRight`: col 0 -> 1) and resize (`Shift+ArrowDown`: 2×1 -> 2×2)
      await placedTile.focus();
      await placedTile.press("ArrowRight");
      await expect(placedTile).toHaveAttribute("aria-label", /row 1 column 2/i);
      await placedTile.press("Shift+ArrowDown");
      await expect(placedTile.locator(".pinned-tile-span-badge")).toContainText("2×2");
      await expect(appModal.locator(".pinned-grid-empty-cell")).toHaveCount(5);

      // Audit active Pinned Visual Tile-Grid Editor under axe-core WCAG 2.2 AA & overflow guard
      await expectZeroAxeViolations(
        page,
        `Pinned Visual Tile-Grid Editor (${themeLabel}, 2x2 inverted gold tile)`,
      );
      await expectZeroHorizontalOverflow(
        page,
        `Pinned Visual Tile-Grid Editor (${themeLabel})`,
      );

      // 5. Add Page 2, switch back to Page 1, and delete Page 1 via confirmation dialog
      await appModal.locator("#btn-pinned-add-page").click();
      await expect(appModal.locator("#pinned-page-tab-1")).toHaveAttribute(
        "aria-selected",
        "true",
      );
      await appModal.locator("#pinned-page-tab-0").click();
      await appModal.locator("#btn-pinned-delete-page").click();

      const confirmModal = page.locator("#latter-confirm-modal");
      await expect(confirmModal).toBeVisible();
      await confirmModal.locator("#btn-confirm-modal-accept").click();
      await expect(confirmModal).toBeHidden();
      await expect(appModal.locator(".pinned-grid-tile")).toHaveCount(0);

      await expect
        .poll(() =>
          ctrl.wsCalls.some((m) => {
            if (m.command !== "save_device_config") return false;
            const cfg = (m.payload as Record<string, unknown>)?.config as
              | Record<string, unknown>
              | undefined;
            return Boolean(cfg && "pinned_page_titles" in cfg);
          }),
        )
        .toBe(true);
    }
  });
});
