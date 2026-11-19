/**
 * Frontend unit & DOM tests for i18n (`D-061`), reusable WAI-ARIA controls (`D-062`, `Q5`, `Q11`),
 * and staged `Batch controls` `Mixed`-safe per-Device pill toggling (`D-064`, `Q6`).
 */

import "./dom-shim.js";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { beforeEach, describe, it } from "node:test";
import { fileURLToPath } from "node:url";
import {
  matchComboboxOptions,
  renderConfirmDialog,
  renderEntityCombobox,
  renderPillList,
  renderRangeRow,
  renderSortableList,
  resetComboboxState,
  type ComboboxOptionItem,
} from "../src/components/controls.js";
import { EN_COMMON_STRINGS } from "../src/i18n/en-common.js";
import { EN_DEVICES_STRINGS } from "../src/i18n/en-devices.js";
import { EN_SYSTEM_STRINGS } from "../src/i18n/en-system.js";
import {
  buildStudioEnLocaleCatalog,
  EN_STRINGS,
  formatHaEntityState,
  localizeRepairIssue,
  t,
  tPrefLabel,
  tPrefOption,
} from "../src/i18n/index.js";
import { render } from "../src/lib/lit.js";
import { StudioStore } from "../src/state/store.js";
import type { HomeAssistant, SharedControlItem, StudioStatePayload } from "../src/types.js";
import { renderBatchControlsCard } from "../src/views/groups/batch-controls.js";
import {
  resetDomBody,
  simDocument,
  SimEvent,
  SimKeyboardEvent,
} from "./dom-shim.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const EN_LOCALE_JSON_PATH = path.resolve(
  __dirname,
  "..",
  "..",
  "custom_components",
  "latter",
  "studio",
  "locales",
  "en.json",
);

describe("i18n parity, WAI-ARIA combobox, confirm dialog & Mixed-safe Batch controls", () => {
  beforeEach(() => {
    resetDomBody();
    resetComboboxState();
  });

  it("keeps EN_STRINGS (en-common + en-system + en-devices) disjoint and in exact parity with studio/locales/en.json", () => {
    const commonKeys = Object.keys(EN_COMMON_STRINGS);
    const systemKeys = Object.keys(EN_SYSTEM_STRINGS);
    const deviceKeys = Object.keys(EN_DEVICES_STRINGS);

    const seen = new Set<string>();
    for (const k of [...commonKeys, ...systemKeys, ...deviceKeys]) {
      assert.equal(seen.has(k), false, `Duplicate translation key across en-*.ts slices: ${k}`);
      seen.add(k);
    }
    assert.equal(Object.keys(EN_STRINGS).length, seen.size);

    const expectedCatalog = buildStudioEnLocaleCatalog();
    const diskCatalog = JSON.parse(fs.readFileSync(EN_LOCALE_JSON_PATH, "utf8")) as Record<
      string,
      string
    >;
    assert.deepEqual(diskCatalog, expectedCatalog);
  });

  it("interpolates t(), tPrefLabel(), and tPrefOption() with runtime locale_strings overlays", () => {
    const frOverlay = {
      "action.cancel": "Annuler",
      "confirm.blast_radius_many": "Affecte {count} appareils",
      "pref.clock_face": "Cadran d'horloge",
      "pref_option.Minimal Digital": "Numérique minimal",
      "pref_option.clock_face.Minimal Digital": "Cadran numérique épuré",
    };

    assert.equal(t("action.cancel"), "Cancel");
    assert.equal(t("action.cancel", undefined, frOverlay), "Annuler");
    assert.equal(
      t("confirm.blast_radius_many", { count: 4 }, frOverlay),
      "Affecte 4 appareils",
    );

    assert.equal(tPrefLabel("clock_face"), "Clock face");
    assert.equal(tPrefLabel("clock_face", "Fallback", frOverlay), "Cadran d'horloge");
    assert.equal(tPrefLabel("custom_unknown_pref"), "Custom unknown pref");
    assert.equal(tPrefLabel("", "Fallback label"), "Fallback label");

    // Scoped `pref_option.<prefKey>.<opt>` wins over generic `pref_option.<opt>`
    assert.equal(
      tPrefOption("clock_face", "Minimal Digital", frOverlay),
      "Cadran numérique épuré",
    );
    assert.equal(
      tPrefOption("other_pref", "Minimal Digital", frOverlay),
      "Numérique minimal",
    );
    assert.equal(tPrefOption("clock_face", "Minimal Digital"), "Minimal digital");

    // Repairs & entity state formatting bridges
    const fakeHass = {
      states: {
        "lock.front_door": {
          entity_id: "lock.front_door",
          state: "locked",
          attributes: {},
        },
      },
      localize: (key: string) =>
        key === "component.latter.issues.ble_no_proxies.description"
          ? "Localized BLE proxy warning"
          : key,
      formatEntityState: () => "Verrouillé",
    } as unknown as HomeAssistant;

    assert.equal(localizeRepairIssue(fakeHass, "ble_no_proxies"), "Localized BLE proxy warning");
    assert.equal(formatHaEntityState(fakeHass, "lock.front_door"), "Verrouillé");
    assert.equal(formatHaEntityState(null, "lock.missing"), "—");
  });

  it("ranks matchComboboxOptions fuzzily, enforces the 80-item cap, and never mutates selection while typing", () => {
    const bulkOptions: ComboboxOptionItem[] = Array.from({ length: 120 }, (_, idx) => ({
      id: `light.area_lamp_${String(idx).padStart(3, "0")}`,
      name: `Area Lamp ${idx}`,
      domain: "light",
      area_name: idx % 2 === 0 ? "Living Room" : "Kitchen",
    }));
    bulkOptions.push(
      {
        id: "light.kitchen_island",
        name: "Kitchen Island",
        domain: "light",
        area_name: "Kitchen",
      },
      {
        id: "light.kitchen_island_pendant",
        name: "Kitchen Island Pendant",
        domain: "light",
        area_name: "Kitchen",
      },
      {
        id: "scene.ki_is_scene",
        name: "K-I Cozy",
        domain: "scene",
        area_name: "Bedroom",
      },
    );

    const allRes = matchComboboxOptions(bulkOptions, "");
    assert.equal(allRes.totalMatches, 123);
    assert.equal(allRes.items.length, 80);

    // Exact match ranks ahead of prefix match
    const exactVsPrefix = matchComboboxOptions(bulkOptions, "kitchen island");
    assert.equal(exactVsPrefix.items[0]?.id, "light.kitchen_island");
    assert.equal(exactVsPrefix.items[1]?.id, "light.kitchen_island_pendant");

    // Ordered-subsequence fuzzy match works when substring doesn't match directly
    const fuzzy = matchComboboxOptions(bulkOptions, "ktchnislnd");
    assert.ok(fuzzy.items.some((it) => it.id === "light.kitchen_island"));

    // Interactive DOM test: typing filters listbox and NEVER calls `onChange` until Enter/click
    const container = simDocument.createElement("div");
    let committedValue = "light.area_lamp_001";
    const changeCalls: string[] = [];

    const rerender = (): void => {
      render(
        renderEntityCombobox({
          id: "test-entity-cb",
          value: committedValue,
          options: bulkOptions,
          ariaLabel: "Choose entity",
          onChange: (nextId) => {
            changeCalls.push(nextId);
            committedValue = nextId;
          },
          onUiChange: () => rerender(),
        }),
        container,
      );
    };

    rerender();
    const input = container.querySelector("#test-entity-cb") as unknown as HTMLInputElement;
    assert.equal(input.getAttribute("role"), "combobox");
    assert.equal(input.getAttribute("aria-expanded"), "false");
    assert.equal(input.value, "Area Lamp 1");

    // Type a search query — must open listbox & filter without mutating `committedValue`!
    input.value = "kitchen island";
    input.dispatchEvent(new SimEvent("input", { bubbles: true }));
    assert.equal(changeCalls.length, 0);
    assert.equal(committedValue, "light.area_lamp_001");
    assert.equal(input.getAttribute("aria-expanded"), "true");

    const renderedOpts = container.querySelectorAll("[role='option']");
    assert.ok(renderedOpts.length >= 2);
    assert.ok(renderedOpts[0]?.textContent.includes("Kitchen Island"));

    // Escape closes without committing and restores closed display label
    input.dispatchEvent(
      new SimKeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true }),
    );
    assert.equal(changeCalls.length, 0);
    assert.equal(input.getAttribute("aria-expanded"), "false");
    assert.equal(input.value, "Area Lamp 1");

    // Re-filter and press Enter to commit active option
    input.value = "kitchen island";
    input.dispatchEvent(new SimEvent("input", { bubbles: true }));
    input.dispatchEvent(
      new SimKeyboardEvent("keydown", { key: "ArrowDown", bubbles: true, cancelable: true }),
    );
    input.dispatchEvent(
      new SimKeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }),
    );
    assert.deepEqual(changeCalls, ["light.kitchen_island_pendant"]);
    assert.equal(committedValue, "light.kitchen_island_pendant");
  });

  it("renders renderConfirmDialog with blast-radius chip, backup button, and cancel/confirm handlers (Q5)", () => {
    const container = simDocument.createElement("div");
    let confirmed = 0;
    let cancelled = 0;
    let backupClicked = 0;

    render(
      renderConfirmDialog({
        id: "dlg-reset",
        title: "Reset Desk Assistant to defaults?",
        consequence: "Custom shortcuts and Display preferences will be cleared.",
        blastRadiusCount: 3,
        confirmLabel: "Reset Device",
        confirmButtonId: "btn-confirm-reset",
        danger: true,
        onDownloadBackupFirst: () => {
          backupClicked += 1;
        },
        onConfirm: () => {
          confirmed += 1;
        },
        onCancel: () => {
          cancelled += 1;
        },
      }),
      container,
    );

    const dlg = container.querySelector("#dlg-reset")!;
    assert.equal(dlg.tagName, "DIALOG");
    assert.equal(dlg.getAttribute("aria-labelledby"), "dlg-reset-title");
    assert.equal(dlg.getAttribute("aria-describedby"), "dlg-reset-desc");
    assert.equal(container.querySelector("#dlg-reset-title")?.textContent, "Reset Desk Assistant to defaults?");
    assert.ok(container.querySelector(".confirm-blast-badge")?.textContent.includes("3 Devices"));

    const buttons = container.querySelectorAll("button");
    assert.equal(buttons.length, 3);
    assert.ok(buttons[0].textContent.includes("Download backup first"));
    buttons[0].click();
    assert.equal(backupClicked, 1);

    buttons[1].click();
    assert.equal(cancelled, 1);

    const confirmBtn = container.querySelector("#btn-confirm-reset")!;
    assert.equal(confirmBtn.classList.contains("btn-danger-filled"), true);
    confirmBtn.click();
    assert.equal(confirmed, 1);
  });

  it("preserves per-Device untouched tokens during Mixed Batch controls pill toggling (Q6 / D-064)", async () => {
    const fakeHost = {
      isConnected: true,
      requestUpdate() {},
      addController() {},
      removeController() {},
      updateComplete: Promise.resolve(true),
      renderRoot: simDocument.createDocumentFragment(),
    };

    const sysCalls: Array<{ command: string; payload: Record<string, unknown> }> = [];
    const devCalls: Array<{ subentryId: string; command: string; payload: Record<string, unknown> }> = [];
    const store = new StudioStore(fakeHost as unknown as ConstructorParameters<typeof StudioStore>[0]);
    store.ensureSubscription = async () => {};
    store.ws.runSystemCommand = async (command, payload) => {
      sysCalls.push({ command, payload: structuredClone(payload) });
      return structuredClone(store.state) as StudioStatePayload;
    };
    store.ws.runDeviceCommand = async (subentryId, command, payload) => {
      devCalls.push({ subentryId, command, payload: structuredClone(payload) });
      return structuredClone(store.state) as StudioStatePayload;
    };

    const areaPillsCtrl: SharedControlItem = {
      key: "interface:pills:area control categories",
      pref_key: "area_categories",
      tier: "interface",
      section: "interface",
      section_title: "Interface",
      name: "Area Control Categories",
      domain: "pills",
      state: "",
      options: ["scene", "light", "climate", "media", "all"],
      option_labels: {
        scene: "Scenes",
        light: "Lights",
        climate: "Climate",
        media: "Media",
        all: "All entities",
      },
      min: 1,
      targets: [
        {
          device_slug: "desk_panel",
          device_group: "wall_panels",
          is_online: true,
          is_roaming: false,
          pref_key: "area_categories",
          state: "scene,light",
        },
        {
          device_slug: "pocket_assistant",
          device_group: "pocket_carry",
          is_online: true,
          is_roaming: true,
          pref_key: "area_categories",
          state: "light,climate",
        },
      ],
    };

    store.ingestPayload(
      {
        studio_rev: 34,
        system_config_rev: 1,
        device_config_rev: 1,
        system_devices: [
          {
            subentry_id: "sub_desk",
            device_slug: "desk_panel",
            title: "Desk Panel",
            kind: "device",
            device_group: "wall_panels",
            is_online: true,
            is_roaming: false,
            has_display: true,
          },
          {
            subentry_id: "sub_pocket",
            device_slug: "pocket_assistant",
            title: "Pocket Assistant",
            kind: "device",
            device_group: "pocket_carry",
            is_online: true,
            is_roaming: true,
            has_display: true,
          },
        ],
        system_controls: [areaPillsCtrl],
      } as unknown as StudioStatePayload,
      false,
    );

    // Initial state: `scene` is mixed, `light` is on, `climate` is mixed, `media` is off
    const initialStates = Object.fromEntries(
      store.groups.getEffectiveBatchPillStates(areaPillsCtrl).map((p) => [p.token, p.state]),
    );
    assert.deepEqual(initialStates, {
      scene: "mixed",
      light: "on",
      climate: "mixed",
      media: "off",
      all: "off",
    });

    // Render Batch controls card into DOM and verify Reset/Apply footer buttons start disabled
    const cardRoot = simDocument.createElement("div");
    const devs = store.state!.system_devices;
    render(renderBatchControlsCard(store, [], devs, [areaPillsCtrl]), cardRoot);
    assert.equal((cardRoot.querySelector("#btn-batch-reset") as unknown as HTMLButtonElement).disabled, true);
    assert.equal((cardRoot.querySelector("#btn-batch-apply") as unknown as HTMLButtonElement).disabled, true);

    // Toggle `media` ON -> only `media` is staged; `scene` and `climate` stay `"mixed"`!
    store.groups.stageBatchPillToggle(areaPillsCtrl, "media");
    const afterMediaOn = Object.fromEntries(
      store.groups.getEffectiveBatchPillStates(areaPillsCtrl).map((p) => [p.token, p.state]),
    );
    assert.equal(afterMediaOn.media, "on");
    assert.equal(afterMediaOn.scene, "mixed");
    assert.equal(afterMediaOn.climate, "mixed");
    assert.equal(store.groups.hasBatchDraft, true);

    render(renderBatchControlsCard(store, [], devs, [areaPillsCtrl]), cardRoot);
    assert.equal((cardRoot.querySelector("#btn-batch-reset") as unknown as HTMLButtonElement).disabled, false);
    assert.equal((cardRoot.querySelector("#btn-batch-apply") as unknown as HTMLButtonElement).disabled, false);

    // Apply staged delta -> each Device receives ONLY the `+media` delta on top of its own CSV!
    await store.groups.applyBatchDraft();
    assert.equal(sysCalls.length, 0);
    assert.deepEqual(devCalls, [
      {
        subentryId: "sub_desk",
        command: "save_device_config",
        payload: {
          config: { area_categories: "scene,light,media" },
        },
      },
      {
        subentryId: "sub_pocket",
        command: "save_device_config",
        payload: {
          config: { area_categories: "light,climate,media" },
        },
      },
    ]);
    assert.equal(store.groups.hasBatchDraft, false);

    // Verify `min: 1` guard prevents leaving any Device with 0 categories
    store.groups.stageBatchPillToggle(areaPillsCtrl, "light", false);
    store.groups.stageBatchPillToggle(areaPillsCtrl, "scene", false);
    // `desk_panel` only had `scene,light`, so turning off `scene` after `light` is rejected!
    const statesAfterMinGuard = Object.fromEntries(
      store.groups.getEffectiveBatchPillStates(areaPillsCtrl).map((p) => [p.token, p.state]),
    );
    assert.equal(statesAfterMinGuard.scene, "mixed");
    store.groups.resetBatchDraft();
    assert.equal(store.groups.hasBatchDraft, false);
  });

  it("wires renderSortableList keyboard reordering, renderPillList toggles, and renderRangeRow live readout", async () => {
    const container = simDocument.createElement("div");
    simDocument.body.appendChild(container);
    let items = ["app:music", "app:area", "app:time"];

    const rerenderSortable = (): void => {
      render(
        renderSortableList({
          id: "dock-test",
          items,
          getKey: (it) => it,
          getLabel: (it) => it,
          renderContent: (it) => it,
          onReorder: (from, to) => {
            const copy = [...items];
            const [moved] = copy.splice(from, 1);
            copy.splice(to, 0, moved);
            items = copy;
            rerenderSortable();
          },
        }),
        container,
      );
    };

    rerenderSortable();
    assert.equal(container.querySelectorAll(".drag-handle").length, 3);
    const nextBtn0 = container.querySelector(
      "[data-sortable-key='app\\:music'] button[data-move-dir='next']",
    ) as unknown as HTMLButtonElement;
    nextBtn0.click();
    await new Promise<void>((r) => queueMicrotask(r));
    assert.deepEqual(items, ["app:area", "app:music", "app:time"]);

    // Pill list toggle + reorder
    const pillContainer = simDocument.createElement("div");
    const toggled: string[] = [];
    render(
      renderPillList({
        id: "pills-test",
        items: [
          { token: "scene", label: "Scenes", enabled: true },
          { token: "light", label: "Lights", enabled: true },
          { token: "media", label: "Media", enabled: false },
        ],
        onToggle: (tok) => toggled.push(tok),
        onReorder: () => {},
      }),
      pillContainer,
    );
    const inactivePill = pillContainer.querySelectorAll(".pill-toggle")[2]!;
    inactivePill.click();
    assert.deepEqual(toggled, ["media"]);

    // Range row live `@input` readout + `aria-describedby`
    const rangeContainer = simDocument.createElement("div");
    let committed = 0;
    render(
      renderRangeRow({
        id: "rng-dwell",
        label: "Area follow dwell",
        description: "Seconds before moving Device Area.",
        value: 10,
        min: 3,
        max: 60,
        step: 1,
        unit: "s",
        onCommit: (v) => {
          committed = v;
        },
      }),
      rangeContainer,
    );
    const rng = rangeContainer.querySelector("#rng-dwell") as unknown as HTMLInputElement;
    assert.equal(rng.getAttribute("aria-describedby"), "rng-dwell-desc");
    assert.equal(rng.getAttribute("aria-valuetext"), "10 s");
    rng.value = "25";
    rng.dispatchEvent(new SimEvent("input", { bubbles: true }));
    assert.equal(rng.getAttribute("aria-valuetext"), "25 s");
    assert.equal(rangeContainer.querySelector(".kv-value")?.textContent, "25 s");
    rng.dispatchEvent(new SimEvent("change", { bubbles: true }));
    assert.equal(committed, 25);
  });
});
