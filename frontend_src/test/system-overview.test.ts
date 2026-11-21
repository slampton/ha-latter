/**
 * Frontend unit & DOM tests for streamlined System -> Overview (`D-076`):
 * - Two-column layout: Column 1 `#card-system-status`, Column 2 `#card-area-deployment`,
 *   with retired `#card-system-capabilities` omitted.
 * - Operational health distinction across Online, Sleeping (battery hibernate), Away / Scanning
 *   (phones & BLE tags), unexpectedly Offline hardware, and Low battery (`<= 20%`, not charging).
 * - Sleeping roaming Devices still surface inside their live BLE-tracked Area and Roaming rollup.
 */

import "./dom-shim.js";
import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";
import { render } from "../src/lib/lit.js";
import type { SystemDeviceEntry } from "../src/types.js";
import { renderSystemOverviewView } from "../src/views/system-overview-view.js";
import { resetDomBody, simDocument } from "./dom-shim.js";
import { makeFakeStore } from "./fake-store.js";

function makeDevice(overrides: Partial<SystemDeviceEntry>): SystemDeviceEntry {
  return {
    subentry_id: "sub_1",
    device_slug: "desk_panel",
    title: "Desk Assistant",
    model_label: "Desk Assistant 4.0\"",
    area_id: "office",
    has_assigned_area: true,
    area_label: "Office",
    status_code: "online",
    status_label: "Online",
    is_online: true,
    kind: "device",
    ble_category: "",
    has_display: true,
    has_battery: false,
    is_roaming: false,
    device_group: "wall_panels",
    device_remote_group: "area_auto",
    device_group_name: "Wall & Desk Panels",
    assigned_person: "",
    active_area_name: "Office",
    is_latter_native: true,
    battery_level: null,
    is_charging: false,
    is_usb_connected: true,
    wifi_rssi: -52,
    ip_address: "192.168.1.20",
    has_ble: true,
    ble_tracked: false,
    ble_survey_rows: [],
    ble_packets_seen: 0,
    is_current: false,
    ...overrides,
  };
}

describe("System -> Overview streamlined 2-card layout & health semantics (D-076)", () => {
  beforeEach(() => {
    resetDomBody();
  });

  it("renders Status in Column 1, Area deployment in Column 2, and omits System capabilities", () => {
    const harness = makeFakeStore({
      currentScope: "system",
      currentViewId: "system_overview",
      state: {
        system_devices: [
          makeDevice({ subentry_id: "sub_desk", title: "Desk Assistant", area_id: "office" }),
          makeDevice({
            subentry_id: "sub_phone",
            title: "Alex's Phone",
            kind: "ble_tag",
            ble_category: "phone",
            has_display: false,
            has_assigned_area: false,
            is_roaming: true,
            ble_tracked: true,
            area_id: "kitchen",
            active_area_name: "Kitchen",
            assigned_person: "person.alex",
          }),
        ],
        live: {
          area_presence_grid: [
            { area_id: "office", area_name: "Office", is_occupied: false },
            { area_id: "kitchen", area_name: "Kitchen", is_occupied: true },
          ],
        },
      },
    });

    const container = simDocument.createElement("div");
    render(renderSystemOverviewView(harness.store), container);

    const colsWrap = container.querySelector(".columns");
    assert.ok(colsWrap);
    const cols = colsWrap.querySelectorAll(".column");
    assert.equal(cols.length, 2);
    assert.ok(cols[0].querySelector("#card-system-status"));
    assert.equal(cols[0].querySelector("#card-area-deployment"), null);
    assert.ok(cols[1].querySelector("#card-area-deployment"));
    assert.equal(container.querySelector("#card-system-capabilities"), null);

    const chip = container.querySelector("#sys-status-chip");
    assert.ok(chip?.className.includes("chip-success"));
    assert.ok(chip?.textContent?.includes("All online"));

    const devMeta = container.querySelector("#sys-tile-devices .status-tile-meta")?.textContent;
    assert.equal(devMeta, "1 display • 1 phone");
  });

  it("treats Sleeping battery Devices and Away phones as Healthy without triggering Offline", () => {
    const harness = makeFakeStore({
      currentScope: "system",
      currentViewId: "system_overview",
      state: {
        system_devices: [
          makeDevice({ subentry_id: "sub_desk", title: "Desk Assistant", area_id: "office" }),
          makeDevice({
            subentry_id: "sub_pocket",
            title: "Pocket Assistant",
            has_battery: true,
            battery_level: 78,
            is_charging: false,
            is_usb_connected: false,
            has_assigned_area: false,
            is_roaming: true,
            ble_tracked: true,
            is_online: false,
            status_code: "offline",
            status_label: "Sleeping",
            area_id: "kitchen",
            active_area_name: "Kitchen",
          }),
          makeDevice({
            subentry_id: "sub_phone",
            title: "Sam's Phone",
            kind: "ble_tag",
            ble_category: "phone",
            has_display: false,
            has_assigned_area: false,
            is_roaming: true,
            ble_tracked: true,
            is_online: false,
            status_code: "away",
            status_label: "Away",
            area_id: "",
            active_area_name: "Away",
          }),
        ],
        live: {
          area_presence_grid: [
            { area_id: "kitchen", area_name: "Kitchen", is_occupied: true },
            { area_id: "office", area_name: "Office", is_occupied: false },
          ],
        },
      },
    });

    const container = simDocument.createElement("div");
    render(renderSystemOverviewView(harness.store), container);

    const chip = container.querySelector("#sys-status-chip");
    assert.ok(chip?.className.includes("chip-success"));
    assert.ok(chip?.textContent?.includes("Healthy"));

    const tileVal = container.querySelector("#sys-tile-devices .status-tile-value")?.textContent?.trim();
    assert.equal(tileVal, "1 / 3 online");

    const tileMeta = container.querySelector("#sys-tile-devices .status-tile-meta")?.textContent?.trim();
    assert.equal(tileMeta, "1 sleeping • 1 away");

    // Sleeping roaming Device still appears in Roaming Devices rollup and Kitchen Area box
    const roamingBox = container.querySelector("#sys-deploy-roaming")?.textContent || "";
    assert.ok(roamingBox.includes("1 / 2 active"));
    assert.ok(roamingBox.includes("Pocket Assistant (Kitchen)"));
    assert.equal(roamingBox.includes("Sam's Phone (Away)"), false);

    const deployHtml = container.querySelector("#card-area-deployment")?.innerHTML || "";
    assert.ok(deployHtml.includes("Here: Pocket Assistant"));
  });

  it("flags unexpectedly Offline hardware and Low battery while ignoring charging battery Devices", () => {
    const harness = makeFakeStore({
      currentScope: "system",
      currentViewId: "system_overview",
      state: {
        system_devices: [
          makeDevice({
            subentry_id: "sub_desk_offline",
            title: "Hallway Panel",
            is_online: false,
            status_code: "offline",
            status_label: "Offline",
          }),
          makeDevice({
            subentry_id: "sub_wrist_low",
            title: "Wrist Assist",
            has_battery: true,
            battery_level: 14,
            is_charging: false,
            is_usb_connected: false,
            is_online: true,
            status_code: "online",
            status_label: "Online",
          }),
          makeDevice({
            subentry_id: "sub_pocket_charging",
            title: "Pocket Assistant",
            has_battery: true,
            battery_level: 12,
            is_charging: true,
            is_usb_connected: true,
            is_online: true,
            status_code: "online",
            status_label: "Online",
          }),
        ],
      },
    });

    const container = simDocument.createElement("div");
    render(renderSystemOverviewView(harness.store), container);

    const chip = container.querySelector("#sys-status-chip");
    assert.ok(chip?.className.includes("chip-warning"));
    assert.ok(chip?.textContent?.includes("1 offline"));

    const tileMeta = container.querySelector("#sys-tile-devices .status-tile-meta")?.textContent?.trim();
    assert.equal(tileMeta, "1 offline • 1 low battery");

    // When all online but one discharging battery Device <= 20%, header chip warns low battery
    const lowBatHarness = makeFakeStore({
      currentScope: "system",
      currentViewId: "system_overview",
      state: {
        system_devices: [
          makeDevice({
            subentry_id: "sub_wrist_low",
            title: "Wrist Assist",
            has_battery: true,
            battery_level: 18,
            is_charging: false,
            is_online: true,
          }),
        ],
      },
    });
    const lowBatContainer = simDocument.createElement("div");
    render(renderSystemOverviewView(lowBatHarness.store), lowBatContainer);
    const lowBatChip = lowBatContainer.querySelector("#sys-status-chip");
    assert.ok(lowBatChip?.className.includes("chip-warning"));
    assert.ok(lowBatChip?.textContent?.includes("1 low battery"));
    assert.equal(
      lowBatContainer.querySelector("#sys-tile-devices .status-tile-meta")?.textContent?.trim(),
      "1 low battery • 1 display",
    );
  });

  it("only marks progress fill .low when unexpected offline leaves 0 online (never when all sleeping)", () => {
    const allSleepHarness = makeFakeStore({
      currentScope: "system",
      currentViewId: "system_overview",
      state: {
        system_devices: [
          makeDevice({
            subentry_id: "sub_p1",
            has_battery: true,
            battery_level: 80,
            is_online: false,
            status_code: "offline",
            status_label: "Sleeping",
          }),
        ],
      },
    });
    const sleepContainer = simDocument.createElement("div");
    render(renderSystemOverviewView(allSleepHarness.store), sleepContainer);
    assert.equal(sleepContainer.querySelector("#sys-tile-devices .signal-fill.low"), null);
    assert.ok(sleepContainer.querySelector("#sys-status-chip")?.textContent?.includes("Healthy"));

    const allOfflineHarness = makeFakeStore({
      currentScope: "system",
      currentViewId: "system_overview",
      state: {
        system_devices: [
          makeDevice({
            subentry_id: "sub_d1",
            is_online: false,
            status_code: "offline",
            status_label: "Offline",
          }),
        ],
      },
    });
    const offlineContainer = simDocument.createElement("div");
    render(renderSystemOverviewView(allOfflineHarness.store), offlineContainer);
    assert.ok(offlineContainer.querySelector("#sys-tile-devices .signal-fill.low"));
    assert.ok(offlineContainer.querySelector("#sys-status-chip")?.textContent?.includes("Offline"));
  });
});
