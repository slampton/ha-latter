/**
 * Pure Node TypeScript unit tests for `group-overlay.ts`, `routing.ts`, `StudioStore`,
 * `BatchController`, and `StudioWsClient` payload construction with ZERO fake DOM.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { buildOrderedPillItems } from "../../src/components/dialogs/app-config.js";
import { GAMES_ITEMS_CATALOG } from "../../src/constants.js";
import type { ReactiveController, ReactiveControllerHost } from "../../src/lib/lit.js";
import {
  DEFAULT_GAMES_ITEMS,
  DEVICE_PREF_SPECS_CATALOG,
  STUDIO_REV,
} from "../../src/protocol-schema.js";
import {
  isCatalogItemSupported,
  mergePersistedWithBlankSlots,
  overlayDevicePrefsOnSections,
  overlayPendingBlankListSlots,
  overlayPendingEntityStates,
} from "../../src/state/group-overlay.js";
import { deviceHasView } from "../../src/state/routing.js";
import {
  isProtectedNativeDockItem,
  normalizeShortcutAccent,
  normalizeShortcutArray,
  normalizeShortcutBadgeStyle,
  shortcutBadgeClass,
} from "../../src/state/shortcuts-ops.js";
import { StudioStore } from "../../src/state/store.js";
import type {
  DeviceGroup,
  HomeAssistant,
  SharedControlItem,
  StudioStatePayload,
  SystemDeviceEntry,
} from "../../src/types.js";
import { deriveGroupCapabilities } from "../../src/views/groups/group-baseline-drawer.js";

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
        has_imu: false,
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
        has_imu: true,
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
    assert.equal(isCatalogItemSupported({ capability: "imu" }, { has_imu: true }), true);
    assert.equal(isCatalogItemSupported({ capability: "imu" }, { has_imu: false }), false);
    assert.equal(isCatalogItemSupported({ capability: "imu" }, { has_imu: undefined }), true);
    assert.equal(isCatalogItemSupported({ capability: "imu" }, undefined), true);
    assert.equal(isCatalogItemSupported({ capability: "no_imu" }, { has_imu: true }), false);
    assert.equal(isCatalogItemSupported({ capability: "no_imu" }, { has_imu: false }), true);
    assert.equal(isCatalogItemSupported({ capability: "no_imu" }, { has_imu: undefined }), true);
    assert.equal(isCatalogItemSupported({ capability: "no_imu" }, undefined), true);

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

  it("constructs STUDIO_REV=47 WS payloads with snapshot-isolated saves and expected_config_rev", async () => {
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
      studio_rev: 47,
    });

    // System setting save on System scope sends `subentry_id: null` + `expected_config_rev` + `studio_rev: 47`
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
      studio_rev: 47,
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

  it("normalizes per-shortcut badge_style & accent, protects native dock apps, and persists shortcut modal edits", async () => {
    assert.equal(normalizeShortcutBadgeStyle(""), "");
    assert.equal(normalizeShortcutBadgeStyle("glass"), "");
    assert.equal(normalizeShortcutBadgeStyle("INVERTED"), "inverted");
    assert.equal(normalizeShortcutBadgeStyle("unknown"), "");

    assert.equal(normalizeShortcutAccent(""), "");
    assert.equal(normalizeShortcutAccent("default"), "");
    assert.equal(normalizeShortcutAccent("primary"), "primary");
    assert.equal(normalizeShortcutAccent("GOLD"), "gold");
    assert.equal(normalizeShortcutAccent("green"), "green");
    assert.equal(normalizeShortcutAccent("red"), "red");
    assert.equal(normalizeShortcutAccent("orange"), "orange");
    assert.equal(normalizeShortcutAccent("purple"), "");

    assert.equal(shortcutBadgeClass("", ""), "shortcut-icon-badge");
    assert.equal(shortcutBadgeClass("inverted", ""), "shortcut-icon-badge badge-inverted");
    assert.equal(
      shortcutBadgeClass("inverted", "gold"),
      "shortcut-icon-badge badge-inverted accent-gold",
    );
    assert.equal(shortcutBadgeClass("", "red"), "shortcut-icon-badge accent-red");

    const normalizedDock = normalizeShortcutArray(
      [
        {
          kind: "route",
          target: "app:music",
          label: "Custom Music",
          icon: "mdi:speaker",
          badge_style: "inverted",
          accent: "gold",
        },
        {
          kind: "route",
          target: "weather:moon",
          label: "Moon",
          icon: "mdi:weather-night",
          badge_style: "inverted",
          accent: "primary",
        },
        {
          kind: "entity",
          target: "light.desk_lamp",
          action: "toggle",
          label: "Desk Lamp",
          icon: "mdi:desk-lamp",
          confirm: false,
          badge_style: "glass",
          accent: "orange",
        },
      ],
      true,
    );
    assert.equal(normalizedDock.length, 3);
    // Protected native dock app keeps empty label, icon, badge_style, and accent
    assert.deepEqual(normalizedDock[0], {
      kind: "route",
      target: "app:music",
      action: "",
      label: "",
      icon: "",
      confirm: false,
      badge_style: "",
      accent: "",
    });
    assert.equal(isProtectedNativeDockItem(normalizedDock[0]!), true);
    assert.deepEqual(normalizedDock[1], {
      kind: "route",
      target: "weather:moon",
      action: "",
      label: "Moon",
      icon: "mdi:weather-night",
      confirm: false,
      badge_style: "inverted",
      accent: "primary",
    });
    assert.deepEqual(normalizedDock[2], {
      kind: "entity",
      target: "light.desk_lamp",
      action: "toggle",
      label: "Desk Lamp",
      icon: "mdi:desk-lamp",
      confirm: false,
      badge_style: "",
      accent: "orange",
    });

    // Modal open -> configure badge_style & accent -> save -> reopen edit round-trip
    const { store, wsLog } = createHeadlessStore({
      catalog: {
        shortcut_entities: [
          {
            id: "scene.goodnight",
            name: "Goodnight",
            domain: "scene",
            device_class: "",
            icon: "mdi:weather-night",
            area_name: "Harbor Studio",
          },
        ],
      },
    });
    store.applyRoute({ prefix: "/latter", path: "devices/sub_desk/interface" });

    store.entity.openShortcutModal("pinned_items", null);
    assert.equal(store.shortcutModal.open, true);
    assert.equal(store.shortcutModal.iconStyleFilter, "all");
    assert.equal(store.shortcutModal.badgeStyle, "");
    assert.equal(store.shortcutModal.accent, "");

    store.shortcutModal = {
      ...store.shortcutModal,
      kind: "entity",
      entityTarget: "scene.goodnight",
      action: "turn_on",
      label: "Goodnight",
      icon: "mdi:weather-night",
      iconStyleFilter: "solid",
      badgeStyle: "inverted",
      accent: "gold",
      confirm: false,
    };
    store.entity.saveShortcutModal();
    await store.entity.flushDeviceBucket("sub_desk");

    assert.equal(store.shortcutModal.open, false);
    assert.equal(wsLog.length, 1);
    const savedPinned = (
      (wsLog[0]?.payload as Record<string, unknown>)?.config as Record<string, unknown>
    )?.pinned_items as Array<Record<string, unknown>>;
    assert.deepEqual(savedPinned, [
      {
        kind: "entity",
        target: "scene.goodnight",
        action: "turn_on",
        label: "Goodnight",
        icon: "mdi:weather-night",
        confirm: false,
        badge_style: "inverted",
        accent: "gold",
      },
    ]);

    // Reopening existing shortcut restores saved badge_style & accent and resets iconStyleFilter
    store.entity.openShortcutModal("pinned_items", 0);
    assert.equal(store.shortcutModal.badgeStyle, "inverted");
    assert.equal(store.shortcutModal.accent, "gold");
    assert.equal(store.shortcutModal.iconStyleFilter, "all");
  });

  it("filters Configure Games pills by has_imu, guards last supported game, and derives Handhelds/custom group capabilities", () => {
    const defaultTokens = DEFAULT_GAMES_ITEMS.split(",");
    assert.deepEqual(
      buildOrderedPillItems(GAMES_ITEMS_CATALOG, defaultTokens, { has_imu: false }).map((p) => p.token),
      ["blocks", "snake", "drop_four", "marbles"],
    );
    assert.deepEqual(
      buildOrderedPillItems(GAMES_ITEMS_CATALOG, defaultTokens, { has_imu: true }).map((p) => p.token),
      ["marbles", "archery", "bricks", "chomp"],
    );
    assert.deepEqual(
      buildOrderedPillItems(GAMES_ITEMS_CATALOG, defaultTokens, { has_imu: undefined }).map((p) => p.token),
      ["blocks", "snake", "drop_four", "marbles", "archery", "bricks", "chomp"],
    );

    // On a non-IMU device with all 7 default games stored, turning off the 4th visible game is blocked
    const { store: noImuStore } = createHeadlessStore({
      subentry_id: "sub_desk",
      capabilities: { has_display: true, has_imu: false, is_round: false },
      config: {
        device_slug: "desk_assistant",
        kind: "device",
        games_items: DEFAULT_GAMES_ITEMS,
      },
    });
    noImuStore.applyRoute({ prefix: "/latter", path: "devices/sub_desk/interface" });
    noImuStore.entity.toggleGameItemToken("blocks", false);
    noImuStore.entity.toggleGameItemToken("snake", false);
    noImuStore.entity.toggleGameItemToken("drop_four", false);
    assert.deepEqual(noImuStore.entity.getEnabledGamesItems(), [
      "marbles",
      "archery",
      "bricks",
      "chomp",
    ]);
    noImuStore.entity.toggleGameItemToken("marbles", false);
    assert.equal(noImuStore.toastIsError, true);
    assert.ok(noImuStore.entity.getEnabledGamesItems().includes("marbles"));
    noImuStore.entity.discardDeviceBucket("sub_desk");

    // Symmetric guard on an IMU device: turning off the last IMU-supported game is blocked
    const { store: imuStore } = createHeadlessStore({
      subentry_id: "sub_pocket",
      capabilities: { has_display: true, has_imu: true, is_round: true },
      config: {
        device_slug: "pocket_assistant",
        kind: "device",
        games_items: DEFAULT_GAMES_ITEMS,
      },
    });
    imuStore.applyRoute({ prefix: "/latter", path: "devices/sub_pocket/interface" });
    imuStore.entity.toggleGameItemToken("archery", false);
    imuStore.entity.toggleGameItemToken("bricks", false);
    imuStore.entity.toggleGameItemToken("chomp", false);
    assert.deepEqual(imuStore.entity.getEnabledGamesItems(), [
      "blocks",
      "snake",
      "drop_four",
      "marbles",
    ]);
    imuStore.entity.toggleGameItemToken("marbles", false);
    assert.equal(imuStore.toastIsError, true);
    assert.ok(imuStore.entity.getEnabledGamesItems().includes("marbles"));
    imuStore.entity.discardDeviceBucket("sub_pocket");

    // Group baseline capability derivation across built-in archetypes, Handhelds, and custom groups
    const imuMember = imuStore.state!.system_devices.find((d) => d.subentry_id === "sub_pocket")!;
    const noImuMember = imuStore.state!.system_devices.find((d) => d.subentry_id === "sub_desk")!;
    const makeGroup = (id: string): DeviceGroup => ({
      id,
      name: id,
      description: "",
      builtin: id !== "custom_mix",
      include_display: false,
      include_interface: true,
    });
    const unknownMember: SystemDeviceEntry = { ...noImuMember, has_imu: undefined };

    assert.equal(deriveGroupCapabilities(makeGroup("pocket_carry"), []).has_imu, true);
    assert.equal(deriveGroupCapabilities(makeGroup("wearables"), []).has_imu, true);
    assert.equal(deriveGroupCapabilities(makeGroup("wall_panels"), []).has_imu, false);

    // Handhelds spans IMU Mobile Assistant & non-IMU Remote Assistant
    assert.equal(deriveGroupCapabilities(makeGroup("handhelds"), []).has_imu, undefined);
    assert.equal(deriveGroupCapabilities(makeGroup("handhelds"), [imuMember]).has_imu, true);
    assert.equal(deriveGroupCapabilities(makeGroup("handhelds"), [noImuMember]).has_imu, false);
    assert.equal(
      deriveGroupCapabilities(makeGroup("handhelds"), [imuMember, noImuMember]).has_imu,
      undefined,
    );
    assert.equal(deriveGroupCapabilities(makeGroup("handhelds"), [unknownMember]).has_imu, undefined);

    // Custom groups match homogeneous IMU / non-IMU and open all games for mixed-IMU groups
    assert.equal(deriveGroupCapabilities(makeGroup("custom_mix"), []).has_imu, undefined);
    assert.equal(deriveGroupCapabilities(makeGroup("custom_mix"), [imuMember]).has_imu, true);
    assert.equal(deriveGroupCapabilities(makeGroup("custom_mix"), [noImuMember]).has_imu, false);
    assert.equal(
      deriveGroupCapabilities(makeGroup("custom_mix"), [imuMember, noImuMember]).has_imu,
      undefined,
    );

    // BatchController games_items pill lists filter cleanly for homogeneous targets and protect mixed targets
    const gamesCtrl: SharedControlItem = {
      key: "interface:pills:games",
      pref_key: "games_items",
      tier: "interface",
      section: "interface",
      section_title: "Interface",
      name: "Games",
      domain: "pills",
      state: "",
      options: GAMES_ITEMS_CATALOG.map((g) => g.token),
      option_labels: Object.fromEntries(GAMES_ITEMS_CATALOG.map((g) => [g.token, g.label])),
      min: 1,
      targets: [
        {
          subentry_id: "sub_desk",
          device_slug: "desk_assistant",
          device_group: "wall_panels",
          is_online: true,
          is_roaming: false,
          pref_key: "games_items",
          state: DEFAULT_GAMES_ITEMS,
        },
        {
          subentry_id: "sub_pocket",
          device_slug: "pocket_assistant",
          device_group: "pocket_carry",
          is_online: false,
          is_roaming: true,
          pref_key: "games_items",
          state: DEFAULT_GAMES_ITEMS,
        },
      ],
    };
    const { store: batchStore } = createHeadlessStore({ system_controls: [gamesCtrl] });

    // Mixed target ("all") exposes all 7 games
    assert.deepEqual(
      batchStore.groups.getEffectiveBatchPillStates(gamesCtrl).map((p) => p.token),
      ["blocks", "snake", "drop_four", "marbles", "archery", "bricks", "chomp"],
    );
    // Toggling off blocks/snake/drop_four is allowed, then toggling off marbles is blocked to protect non-IMU sub_desk
    batchStore.groups.stageBatchPillToggle(gamesCtrl, "blocks", false);
    batchStore.groups.stageBatchPillToggle(gamesCtrl, "snake", false);
    batchStore.groups.stageBatchPillToggle(gamesCtrl, "drop_four", false);
    batchStore.toastIsError = false;
    batchStore.groups.stageBatchPillToggle(gamesCtrl, "marbles", false);
    assert.equal(batchStore.toastIsError, true);
    assert.equal(
      batchStore.groups.getEffectiveBatchPillStates(gamesCtrl).find((p) => p.token === "marbles")
        ?.state,
      "on",
    );

    // Homogeneous non-IMU target ("group:wall_panels") shows only non-IMU + universal games
    batchStore.groups.setBatchTargetFilter("group:wall_panels");
    assert.deepEqual(
      batchStore.groups.getEffectiveBatchPillStates(gamesCtrl).map((p) => p.token),
      ["blocks", "snake", "drop_four", "marbles"],
    );

    // Homogeneous IMU target ("group:pocket_carry") shows only IMU + universal games
    batchStore.groups.setBatchTargetFilter("group:pocket_carry");
    assert.deepEqual(
      batchStore.groups.getEffectiveBatchPillStates(gamesCtrl).map((p) => p.token),
      ["marbles", "archery", "bricks", "chomp"],
    );
  });
});
