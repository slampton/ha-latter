/**
 * Pure Node TypeScript unit tests for `group-overlay.ts`, `routing.ts`, `StudioStore`,
 * `BatchController`, and `StudioWsClient` payload construction with ZERO fake DOM.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { ReactiveController, ReactiveControllerHost } from "../../src/lib/lit.js";
import { DEVICE_PREF_SPECS_CATALOG, STUDIO_REV } from "../../src/protocol-schema.js";
import {
  isCatalogItemSupported,
  mergePersistedWithBlankSlots,
  overlayDevicePrefsOnSections,
  overlayPendingBlankListSlots,
  overlayPendingEntityStates,
} from "../../src/state/group-overlay.js";
import { deviceHasView } from "../../src/state/routing.js";
import { StudioStore } from "../../src/state/store.js";
import type {
  DeviceGroup,
  HomeAssistant,
  SharedControlItem,
  StudioStatePayload,
} from "../../src/types.js";

interface HeadlessStoreHarness {
  store: StudioStore;
  wsLog: Array<Record<string, unknown>>;
  updateCount: () => number;
}

function createHeadlessStore(initialPayload?: Partial<StudioStatePayload>): HeadlessStoreHarness {
  let updates = 0;
  const controllers = new Set<ReactiveController>();
  const host: ReactiveControllerHost = {
    addController(c) {
      controllers.add(c);
    },
    removeController(c) {
      controllers.delete(c);
    },
    requestUpdate() {
      updates += 1;
    },
    updateComplete: Promise.resolve(true),
  };

  const wsLog: Array<Record<string, unknown>> = [];
  const store = new StudioStore(host as ReactiveControllerHost & HTMLElement);
  const hass: HomeAssistant = {
    locale: { language: "en", time_format: "am_pm" },
    config: { unit_system: { length: "km" }, time_zone: "UTC", version: "2026.11.2" },
    themes: { darkMode: false },
    states: {},
    connection: {
      subscribeMessage: async () => () => {},
    },
    callWS: async <T = unknown>(msg: Record<string, unknown>): Promise<T> => {
      wsLog.push(structuredClone(msg));
      if (msg.type === "latter/device/command" && msg.command === "save_device_config") {
        const nextRev = (store.state?.device_config_rev ?? 1) + 1;
        return structuredClone({
          ...(store.state || {}),
          subentry_id: String(msg.subentry_id || ""),
          device_config_rev: nextRev,
        }) as T;
      }
      if (msg.type === "latter/system/command" && msg.command === "save_system_config") {
        const nextSysRev = (store.state?.system_config_rev ?? 1) + 1;
        return structuredClone({
          ...(store.state || {}),
          system_config_rev: nextSysRev,
        }) as T;
      }
      return structuredClone(store.state) as T;
    },
  };
  store.setHass(hass);

  const defaultGroups: DeviceGroup[] = [
    {
      id: "wall_panels",
      name: "Wall & Desk Panels",
      description: "Stationary panels",
      builtin: true,
      include_display: false,
      include_interface: false,
      device_config: {
        wake_word_mode: "Always On",
        auto_brightness_mode: "Ambient Light",
        day_brightness: 90,
        night_brightness: 35,
        bedtime_brightness: 15,
      },
    },
    {
      id: "pocket_carry",
      name: "Pocket Carry",
      description: "Pocket carry",
      builtin: true,
      include_display: false,
      include_interface: false,
      device_config: {
        wake_word_mode: "Docked Only",
        tap_to_wake: "Docked Only",
        pickup_to_wake: "Disabled",
      },
    },
  ];

  const basePayload: StudioStatePayload = {
    subentry_id: "sub_desk",
    title: "Desk Assistant",
    version: "3.0.0",
    studio_rev: STUDIO_REV,
    system_config_rev: 3,
    device_config_rev: 7,
    internal_logs: [],
    system_devices: [
      {
        subentry_id: "sub_desk",
        device_slug: "desk_assistant",
        title: "Desk Assistant",
        model_label: "Desk Assistant 4.0\"",
        area_id: "harbor_studio",
        has_assigned_area: true,
        area_label: "Harbor Studio",
        status_code: "online",
        status_label: "Online",
        is_online: true,
        kind: "device",
        has_display: true,
        has_battery: false,
        hw_jpeg: true,
        is_roaming: false,
        device_group: "wall_panels",
        device_remote_group: "area_auto",
        device_group_name: "Wall & Desk Panels",
        assigned_person: "",
        active_area_name: "Harbor Studio",
        is_latter_native: true,
        battery_level: null,
        is_charging: false,
        is_usb_connected: true,
        wifi_rssi: -49,
        ip_address: "192.168.10.24",
        has_ble: true,
        ble_tracked: false,
        ble_survey_rows: [],
        ble_packets_seen: 0,
        is_current: true,
      },
      {
        subentry_id: "sub_pocket",
        device_slug: "pocket_assistant",
        title: "Pocket Assistant",
        model_label: "Pocket Assistant 1.75\"",
        area_id: "kitchen",
        has_assigned_area: false,
        area_label: "Kitchen (Roaming)",
        status_code: "offline",
        status_label: "Sleeping",
        is_online: false,
        kind: "device",
        has_display: true,
        has_battery: true,
        hw_jpeg: false,
        is_roaming: true,
        device_group: "pocket_carry",
        device_remote_group: "area_auto",
        device_group_name: "Pocket Carry",
        assigned_person: "person.alex",
        active_area_name: "Kitchen",
        is_latter_native: true,
        battery_level: 82,
        is_charging: false,
        is_usb_connected: false,
        wifi_rssi: null,
        ip_address: "192.168.10.31",
        has_ble: true,
        ble_tracked: true,
        ble_survey_rows: [],
        ble_packets_seen: 12,
        is_current: false,
      },
      {
        subentry_id: "sub_tag",
        device_slug: "alex_phone",
        title: "Alex's Phone",
        model_label: "Pixel 9 Pro (HA Companion App)",
        area_id: "kitchen",
        has_assigned_area: false,
        area_label: "Kitchen (Roaming)",
        status_code: "online",
        status_label: "Online",
        is_online: true,
        kind: "ble_tag",
        ble_category: "phone",
        has_display: false,
        has_battery: false,
        is_roaming: true,
        device_group: "",
        device_remote_group: "",
        device_group_name: "Phones",
        assigned_person: "person.alex",
        active_area_name: "Kitchen",
        is_latter_native: false,
        battery_level: null,
        is_charging: false,
        is_usb_connected: false,
        wifi_rssi: null,
        ip_address: "",
        has_ble: true,
        ble_tracked: true,
        ble_survey_rows: [],
        ble_packets_seen: 42,
        is_current: false,
      },
    ],
    issues: [],
    ble_proxy_count: 2,
    discovered_ble_devices: [],
    system_controls: [],
    device_groups: defaultGroups,
    system_config: {
      weather_entity: "weather.harbor",
      alarm_entity: "",
      thermostat_entities: [],
      lock_entities: [],
      garage_entities: [],
      vacuum_entities: [],
      broadcast_speakers: ["media_player.kitchen_speaker"],
      broadcast_phrases: ["Dinner is ready"],
      camera_entities: ["camera.front_entry"],
      remotes_list: [],
      remote_groups: [],
      volume_overrides: [],
      calendar_entities: [],
      custom_palettes: [],
      doorbell_noise_reduction: "strong",
    },
    system_wallpapers: [],
    pref_specs: [...DEVICE_PREF_SPECS_CATALOG],
    capabilities: { has_display: true, has_audio: true, has_voice: true, has_power: true, hw_jpeg: true },
    config: {
      device_slug: "desk_assistant",
      kind: "device",
      is_roaming: false,
      device_group: "wall_panels",
      wake_word_mode: "Always On",
      do_not_disturb: false,
      bedtime_active: false,
      start_screen: "Home",
      home_screen_enabled: true,
    },
    device_prefs: [
      {
        key: "do_not_disturb",
        label: "Do not disturb",
        section: "power",
        group_tier: null,
        domain: "switch",
        value: false,
      },
      {
        key: "bedtime_active",
        label: "Bedtime mode",
        section: "power",
        group_tier: null,
        domain: "switch",
        value: false,
      },
      {
        key: "wake_word_mode",
        label: "Wake word mode",
        section: "voice",
        group_tier: "behavior",
        domain: "select",
        value: "Always On",
        options: ["Always On", "Docked Only", "Disabled"],
      },
      {
        key: "clock_face",
        label: "Clock face",
        section: "interface",
        group_tier: "interface",
        domain: "select",
        value: "Minimal Digital",
      },
    ],
    esphome: { sections: [] },
    wallpapers: [],
    live: {},
    ...initialPayload,
  };

  store.ingestPayload(basePayload, false);
  return { store, wsLog, updateCount: () => updates };
}

describe("group-overlay, URL routing, StudioStore & BatchController pure state", () => {
  it("never detaches a Device to Custom on group_tier=null keys (do_not_disturb, bedtime_active) while detaching on enforced keys", () => {
    const { store } = createHeadlessStore();
    const payload = structuredClone(store.state!);

    // 1. Toggling `do_not_disturb` (`group_tier: null`) keeps `device_group === "wall_panels"`
    overlayDevicePrefsOnSections(payload, { do_not_disturb: true });
    assert.equal(payload.config.do_not_disturb, true);
    assert.equal(payload.config.device_group, "wall_panels");

    // 2. Toggling `bedtime_active` (`group_tier: null`) ALSO keeps `device_group === "wall_panels"`
    overlayDevicePrefsOnSections(payload, { bedtime_active: true });
    assert.equal(payload.config.bedtime_active, true);
    assert.equal(payload.config.device_group, "wall_panels");

    // 3. Editing `clock_face` (`group_tier: "interface"`) when `include_interface: false` keeps group
    overlayDevicePrefsOnSections(payload, { clock_face: "Hybrid Digital" });
    assert.equal(payload.config.device_group, "wall_panels");

    // 4. Editing `wake_word_mode` (`group_tier: "behavior"`) away from baseline detaches to `"custom"`
    overlayDevicePrefsOnSections(payload, { wake_word_mode: "Disabled" });
    assert.equal(payload.config.device_group, "custom");
    assert.equal(
      payload.system_devices.find((d) => d.subentry_id === "sub_desk")?.device_group,
      "custom",
    );

    // 5. Reassigning `device_group: "wall_panels"` overlays enforced baseline values back onto config
    overlayDevicePrefsOnSections(payload, { device_group: "wall_panels" });
    assert.equal(payload.config.device_group, "wall_panels");
    assert.equal(payload.config.wake_word_mode, "Always On");

    // 6. Single-App Mode (`home_screen_enabled: false`) coerces `start_screen: "Home"` -> `"Time App"`
    overlayDevicePrefsOnSections(payload, { home_screen_enabled: false });
    assert.equal(payload.config.start_screen, "Time App");
  });

  it("overlays pending entity states, blank draft slots, and capability gates accurately", () => {
    assert.equal(isCatalogItemSupported({ capability: "hw_jpeg" }, { hw_jpeg: false }), false);
    assert.equal(isCatalogItemSupported({ capability: "hw_jpeg" }, { hw_jpeg: true }), true);
    assert.equal(isCatalogItemSupported({ capability: "round" }, { is_round: false }), false);
    assert.equal(isCatalogItemSupported({ capability: "round" }, undefined), true);

    const merged = mergePersistedWithBlankSlots(
      ["camera.front_entry"],
      2,
      4,
      ["", "camera.front_entry", ""],
    );
    assert.deepEqual(merged, {
      uiList: ["", "camera.front_entry", ""],
      clampedBlankCount: 2,
    });

    const { store } = createHeadlessStore();
    store.pendingBlankListSlots.camera_entities = 1;
    const snap = structuredClone(store.state!);
    overlayPendingBlankListSlots(store, snap);
    assert.deepEqual(snap.system_config.camera_entities, ["camera.front_entry", ""]);

    snap.esphome = {
      sections: [
        {
          id: "sound",
          title: "Sound",
          items: [{ entity_id: "number.desk_vol", domain: "number", name: "Vol", state: "50.0" }],
        },
      ],
    };
    const pendingMap = new Map([
      ["number.desk_vol", { state: "50", expires: Date.now() + 5000 }],
      ["switch.expired", { state: "on", expires: Date.now() - 10 }],
    ]);
    overlayPendingEntityStates(snap, pendingMap);
    assert.equal(pendingMap.size, 0, "Matching numeric state and expired entry must clear");
  });

  it("parses Studio URLs across Devices, Discovered, Device tabs, and System tabs", () => {
    const { store } = createHeadlessStore();

    assert.equal(deviceHasView("display", { has_display: true }, "device"), true);
    assert.equal(deviceHasView("display", { has_display: true }, "ble_tag"), false);
    assert.equal(deviceHasView("presence", { has_display: false }, "ble_tag"), true);

    store.applyRoute({ prefix: "/latter", path: "" });
    assert.equal(store.currentScope, "device");
    assert.equal(store.currentViewId, "select_device_prompt");

    store.applyRoute({ prefix: "/latter", path: "devices/discovered" });
    assert.equal(store.currentScope, "device");
    assert.equal(store.currentViewId, "discovered_devices");

    store.applyRoute({ prefix: "/latter", path: "devices/sub_desk/interface" });
    assert.equal(store.currentScope, "device");
    assert.equal(store.activeSubentryId, "sub_desk");
    assert.equal(store.currentViewId, "interface");

    store.applyRoute({ prefix: "/latter", path: "system/presence" });
    assert.equal(store.currentScope, "system");
    assert.equal(store.currentViewId, "area_tracking");
    assert.equal(store.activeSubentryId, "");
    // `sub_desk` has `ble_tracked: false`, so default survey device picks `sub_pocket` (`ble_tracked: true`)!
    assert.equal(store.bleSurveySubentryId, "sub_pocket");

    store.applyRoute({ prefix: "/latter", path: "system/photos" });
    assert.equal(store.currentScope, "system");
    assert.equal(store.currentViewId, "photos");
  });

  it("constructs STUDIO_REV=44 WS payloads with snapshot-isolated saves and expected_config_rev", async () => {
    const { store, wsLog } = createHeadlessStore();
    store.applyRoute({ prefix: "/latter", path: "devices/sub_desk/overview" });

    // Stage setting on `sub_desk` and switch to `sub_pocket` -> flushes strictly to `sub_desk`!
    store.entity.stageDeviceSetting("do_not_disturb", true, undefined, 60_000);
    store.applyRoute({ prefix: "/latter", path: "devices/sub_pocket/overview" });
    await new Promise<void>((r) => setTimeout(r, 0));

    assert.equal(wsLog.length, 1);
    assert.deepEqual(wsLog[0], {
      type: "latter/device/command",
      command: "save_device_config",
      subentry_id: "sub_desk",
      payload: {
        config: { do_not_disturb: true },
        expected_config_rev: 7,
      },
      studio_rev: 44,
    });

    // System setting save on System scope sends `subentry_id: null` + `expected_config_rev` + `studio_rev: 44`
    wsLog.length = 0;
    store.applyRoute({ prefix: "/latter", path: "system/presence" });
    store.entity.stageSystemSetting("ble_away_timeout_s", 240, undefined, 60_000);
    await store.entity.flushSystemSettings();
    assert.equal(wsLog.length, 1);
    assert.deepEqual(wsLog[0], {
      type: "latter/system/command",
      command: "save_system_config",
      subentry_id: null,
      payload: {
        config: { ble_away_timeout_s: 240 },
        expected_config_rev: 3,
      },
      studio_rev: 44,
    });

    // `version_mismatch` sets `studioRevMismatch = true`
    store.ws.setHass({
      callWS: async () => {
        const err = new Error("Outdated Studio");
        (err as Error & { code?: string }).code = "version_mismatch";
        throw err;
      },
    } as unknown as HomeAssistant);
    await assert.rejects(() => store.ws.getState({}));
    assert.equal(store.studioRevMismatch, true);
  });

  it("preserves Mixed per-Device tokens in BatchController and exempts do_not_disturb from detachment count", async () => {
    const areaPillsCtrl: SharedControlItem = {
      key: "interface:pills:area control categories",
      pref_key: "area_categories",
      tier: "interface",
      section: "interface",
      section_title: "Interface",
      name: "Area Control Categories",
      domain: "pills",
      state: "",
      options: ["scene", "light", "climate", "media"],
      min: 1,
      targets: [
        {
          subentry_id: "sub_desk",
          device_slug: "desk_assistant",
          device_group: "wall_panels",
          is_online: true,
          is_roaming: false,
          pref_key: "area_categories",
          state: "scene,light",
        },
        {
          subentry_id: "sub_pocket",
          device_slug: "pocket_assistant",
          device_group: "pocket_carry",
          is_online: false,
          is_roaming: true,
          pref_key: "area_categories",
          state: "light,climate",
        },
      ],
    };

    const { store, wsLog } = createHeadlessStore({ system_controls: [areaPillsCtrl] });

    // `do_not_disturb` (`group_tier === null`) has 0 detachment preview count!
    store.groups.stageBatchSetting("do_not_disturb", true);
    assert.equal(store.groups.previewBatchDetachmentCount(), 0);

    // `wake_word_mode` (`group_tier === "behavior"`) previews 2 detaching group members
    store.groups.stageBatchSetting("wake_word_mode", "Disabled");
    assert.equal(store.groups.previewBatchDetachmentCount(), 2);
    store.groups.resetBatchDraft();

    // Mixed-safe pill toggle preserves `scene` on `sub_desk` and `climate` on `sub_pocket`
    store.groups.stageBatchPillToggle(areaPillsCtrl, "media");
    await store.groups.applyBatchDraft();
    assert.equal(wsLog.length, 2);
    assert.deepEqual(wsLog[0]?.payload, {
      config: { area_categories: "scene,light,media" },
      expected_config_rev: 7,
    });
    assert.deepEqual(wsLog[1]?.payload, {
      config: { area_categories: "light,climate,media" },
    });
  });
});
