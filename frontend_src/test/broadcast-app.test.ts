/**
 * Frontend unit & DOM tests for Home Hub Broadcast Configuration (`D-074`, `STUDIO_REV = 41`):
 * - `Broadcast` category label & `mdi:bullhorn` icon parity in `HOME_CATEGORIES_CATALOG` and `ROUTE_PREVIEW_ICONS`
 * - `System -> Shared entities` Broadcast speakers (with Area chips) & Quick broadcast phrases editors
 * - `#latter-app-config-modal("home_hub")` per-Device Broadcast speakers pill list & empty-state hint
 */

import "./dom-shim.js";
import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";
import { renderAppConfigModalBody } from "../src/components/dialogs/app-config.js";
import { HOME_CATEGORIES_CATALOG, STUDIO_REV } from "../src/constants.js";
import { ROUTE_PREVIEW_ICONS } from "../src/mdi-catalog.js";
import { renderSystemSharedView } from "../src/views/system-shared-view.js";
import { resetDomBody, simDocument } from "./dom-shim.js";
import { makeFakeStore, render, renderToHtml } from "./fake-store.js";

describe("Home Hub Broadcast App (D-074 / STUDIO_REV 41)", () => {
  beforeEach(() => {
    resetDomBody();
  });

  it("uses Broadcast naming, mdi:bullhorn icon, and STUDIO_REV >= 41", () => {
    assert.ok(STUDIO_REV >= 41);
    const intercomCat = HOME_CATEGORIES_CATALOG.find((c) => c.token === "intercom");
    assert.ok(intercomCat);
    assert.equal(intercomCat.label, "Broadcast");
    assert.equal(ROUTE_PREVIEW_ICONS["home_hub:intercom"], "mdi:bullhorn");
  });

  it("renders Broadcast speakers with Area chips and Quick broadcast phrases in System -> Shared entities", () => {
    const harness = makeFakeStore({
      currentScope: "system",
      currentViewId: "shared_entities",
      state: {
        system_config: {
          broadcast_speakers: ["media_player.kitchen_sonos", "media_player.office_speaker"],
          broadcast_phrases: ["Dinner is ready", "Time to leave"],
        },
        catalog: {
          ma_speakers: [
            { id: "media_player.kitchen_sonos", name: "Kitchen Sonos", area_name: "Kitchen" },
            { id: "media_player.office_speaker", name: "Office Speaker", area_name: "Office" },
          ],
        },
      },
    });

    const sharedHtml = renderToHtml(renderSystemSharedView(harness.store));
    assert.ok(sharedHtml.includes("id=\"hub-domain-broadcast_speakers\""));
    assert.ok(sharedHtml.includes("id=\"hub-domain-broadcast_phrases\""));
    assert.ok(sharedHtml.includes("id=\"hub-list-broadcast_phrases\""));
    assert.ok(sharedHtml.includes("Kitchen Sonos"));
    assert.ok(sharedHtml.includes("Kitchen"));
    assert.ok(sharedHtml.includes("Dinner is ready"));
    assert.ok(sharedHtml.includes("Time to leave"));
  });

  it("always renders standard native <select> dropdowns (never combobox) for Broadcast speakers and Cameras even with > 8 options", () => {
    const manySpeakers = Array.from({ length: 14 }, (_, i) => ({
      id: `media_player.speaker_${i + 1}`,
      name: `Very Long Speaker Name Number ${i + 1}`,
      area_name: `Area ${i + 1}`,
    }));
    const manyCameras = Array.from({ length: 12 }, (_, i) => ({
      id: `camera.cam_${i + 1}`,
      name: `Outdoor Perimeter Camera Channel ${i + 1}`,
    }));
    const harness = makeFakeStore({
      currentScope: "system",
      currentViewId: "shared_entities",
      state: {
        system_config: {
          broadcast_speakers: ["media_player.speaker_1"],
          camera_entities: ["camera.cam_1"],
        },
        catalog: {
          ma_speakers: manySpeakers,
          cameras: manyCameras,
        },
      },
    });

    const container = simDocument.createElement("div");
    render(renderSystemSharedView(harness.store), container);
    assert.equal(
      container.querySelectorAll("input[role='combobox']").length,
      0,
      "Shared entities speaker and camera pickers must use native <select>, never combobox",
    );
    const speakerRow = container.querySelector("#hub-domain-broadcast_speakers");
    const camRow = container.querySelector("#cameras-list");
    assert.ok(speakerRow?.querySelector("select"), "Expected native <select> for Broadcast speakers");
    assert.ok(camRow?.querySelector("select"), "Expected native <select> for Cameras");
  });

  it("renders Broadcast speakers pill list inside Configure Home hub and toggles per-Device subset", () => {
    const emptyHarness = makeFakeStore({
      currentScope: "device",
      currentViewId: "interface",
      activeSubentryId: "sub_hub_empty",
      deviceSelected: true,
      state: {
        system_config: { broadcast_speakers: [] },
        config: {},
      },
    });
    emptyHarness.store.entity.openAppConfigModal("home_hub");
    const emptyHtml = renderToHtml(renderAppConfigModalBody(emptyHarness.store));
    assert.ok(emptyHtml.includes("id=\"home-broadcast-speakers-row\""));
    assert.ok(emptyHtml.includes(emptyHarness.store.t("dialogs.broadcast_speakers_empty_system")));

    const harness = makeFakeStore({
      currentScope: "device",
      currentViewId: "interface",
      activeSubentryId: "sub_hub_1",
      deviceSelected: true,
      state: {
        system_config: {
          broadcast_speakers: ["media_player.kitchen_sonos", "media_player.office_speaker"],
        },
        catalog: {
          ma_speakers: [
            { id: "media_player.kitchen_sonos", name: "Kitchen Sonos", area_name: "Kitchen" },
            { id: "media_player.office_speaker", name: "Office Speaker", area_name: "Office" },
          ],
        },
        config: {},
      },
    });
    harness.store.entity.openAppConfigModal("home_hub");
    const container = simDocument.createElement("div");
    render(renderAppConfigModalBody(harness.store), container);
    assert.ok(container.querySelector("#broadcast-speakers-pills"));

    // Toggle Office Speaker off -> stages [kitchen_sonos]
    harness.store.entity.toggleBroadcastSpeaker("media_player.office_speaker", false);
    assert.deepEqual(harness.store.state?.config?.broadcast_speaker_entities, [
      "media_player.kitchen_sonos",
    ]);

    // Toggle Office Speaker back on -> restores all System speakers ([])
    harness.store.entity.toggleBroadcastSpeaker("media_player.office_speaker", true);
    assert.deepEqual(harness.store.state?.config?.broadcast_speaker_entities, []);
  });
});
