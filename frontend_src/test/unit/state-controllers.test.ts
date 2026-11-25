/**
 * Pure Node TypeScript unit tests for `group-overlay.ts`, `routing.ts`, `StudioStore`,
 * `BatchController`, and `StudioWsClient` payload construction with ZERO fake DOM.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { renderFirmwareOutdatedBanner } from "../../src/components/controls/device-banners.js";
import { buildOrderedPillItems } from "../../src/components/dialogs/app-config.js";
import { DEVICE_PREF_SPECS_MAP, GAMES_ITEMS_CATALOG } from "../../src/constants.js";
import { nothing, type ReactiveController, type ReactiveControllerHost } from "../../src/lib/lit.js";
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
import { renderDeviceDisplayView } from "../../src/views/device-display-view.js";
import { renderDeviceInterfaceView } from "../../src/views/device-interface-view.js";
import { renderDeviceOverviewView } from "../../src/views/device-overview-view.js";
import {
  DEV_TELEMETRY_REFRESH_DEBOUNCE_MS,
  handleDeveloperTelemetryDrawerToggle,
  parseDeviceRuntimeTelemetryRows,
  renderDeviceToolsView,
} from "../../src/views/device-tools-view.js";
import {
  deriveGroupCapabilities,
  renderGroupBaselineDrawer,
} from "../../src/views/groups/group-baseline-drawer.js";
import { renderSystemOverviewView } from "../../src/views/system-overview-view.js";

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
    system_info: {
      ha_version: "2026.11.2",
      integration_version: "3.0.0",
      min_firmware_core_rev: 2026112402,
      studio_rev: STUDIO_REV,
    },
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

  it("constructs STUDIO_REV=52 WS payloads with snapshot-isolated saves and expected_config_rev", async () => {
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
      studio_rev: 52,
    });

    // System setting save on System scope sends `subentry_id: null` + `expected_config_rev` + `studio_rev: 52`
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
      studio_rev: 52,
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
        page: 0,
        col: 0,
        row: 0,
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
    assert.equal(deriveGroupCapabilities(makeGroup("pocket_carry"), []).grid_cols, 2);
    assert.equal(deriveGroupCapabilities(makeGroup("wearables"), []).has_imu, true);
    assert.equal(deriveGroupCapabilities(makeGroup("wearables"), []).grid_cols, 2);
    assert.equal(deriveGroupCapabilities(makeGroup("wall_panels"), []).has_imu, false);
    assert.equal(deriveGroupCapabilities(makeGroup("wall_panels"), []).grid_cols, 3);
    assert.equal(deriveGroupCapabilities(makeGroup("wall_panels"), []).grid_rows, 3);

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

  it("auto-refreshes Device runtime telemetry silently when Developer drawer opens with per-Device debounce", async () => {
    const { store, wsLog } = createHeadlessStore();
    store.applyRoute({ prefix: "/latter", path: "devices/sub_desk/tools" });

    // Closed toggle is a no-op
    assert.equal(handleDeveloperTelemetryDrawerToggle(store, false, false, 10_000), false);
    assert.equal(wsLog.length, 0);

    // Offline Device open is skipped and does NOT prime the debounce window
    assert.equal(handleDeveloperTelemetryDrawerToggle(store, true, true, 10_000), false);
    assert.equal(wsLog.length, 0);

    // Online Device open triggers a silent `request_telemetry` device_action (no toast)
    assert.equal(handleDeveloperTelemetryDrawerToggle(store, true, false, 10_500), true);
    await new Promise<void>((r) => setTimeout(r, 0));
    assert.equal(wsLog.length, 1);
    assert.deepEqual(wsLog[0], {
      type: "latter/device/command",
      command: "device_action",
      subentry_id: "sub_desk",
      payload: { action: "request_telemetry" },
      studio_rev: STUDIO_REV,
    });
    assert.equal(store.toastMessage, "");

    // Re-opening within the 10s debounce window is skipped
    assert.equal(
      handleDeveloperTelemetryDrawerToggle(
        store,
        true,
        false,
        10_500 + DEV_TELEMETRY_REFRESH_DEBOUNCE_MS - 1,
      ),
      false,
    );
    assert.equal(wsLog.length, 1);

    // Different subentry_id has its own independent debounce window
    store.activeSubentryId = "sub_pocket";
    assert.equal(handleDeveloperTelemetryDrawerToggle(store, true, false, 12_000), true);
    await new Promise<void>((r) => setTimeout(r, 0));
    assert.equal(wsLog.length, 2);
    assert.equal(wsLog[1]?.subentry_id, "sub_pocket");
    assert.equal(store.toastMessage, "");

    // Once >= 10s has elapsed for `sub_desk`, re-opening triggers again silently
    store.activeSubentryId = "sub_desk";
    assert.equal(
      handleDeveloperTelemetryDrawerToggle(
        store,
        true,
        false,
        10_500 + DEV_TELEMETRY_REFRESH_DEBOUNCE_MS,
      ),
      true,
    );
    await new Promise<void>((r) => setTimeout(r, 0));
    assert.equal(wsLog.length, 3);
    assert.equal(wsLog[2]?.subentry_id, "sub_desk");
    assert.equal(store.toastMessage, "");

    // Verify rendered `<details class="sub-collapsible">` wires `@toggle` accurately for online vs offline Devices
    const findDrawerToggle = (node: unknown): ((ev: Event) => void) | null => {
      if (!node || typeof node !== "object") return null;
      if (Array.isArray(node)) {
        for (const item of node) {
          const hit = findDrawerToggle(item);
          if (hit) return hit;
        }
        return null;
      }
      const tpl = node as { strings?: readonly string[]; values?: readonly unknown[] };
      if (Array.isArray(tpl.strings) && Array.isArray(tpl.values)) {
        for (let i = 0; i < tpl.strings.length; i += 1) {
          const s = tpl.strings[i] ?? "";
          if (s.includes("<details") && s.includes("@toggle=") && typeof tpl.values[i] === "function") {
            return tpl.values[i] as (ev: Event) => void;
          }
        }
        for (const v of tpl.values) {
          const hit = findDrawerToggle(v);
          if (hit) return hit;
        }
      }
      return null;
    };

    const { store: renderStore, wsLog: renderWs } = createHeadlessStore();
    renderStore.applyRoute({ prefix: "/latter", path: "devices/sub_desk/tools" });
    const onlineToggle = findDrawerToggle(renderDeviceToolsView(renderStore));
    assert.ok(onlineToggle, "Expected @toggle handler on Developer & telemetry <details>");
    onlineToggle({ currentTarget: { open: false } } as unknown as Event);
    assert.equal(renderWs.length, 0);
    onlineToggle({ currentTarget: { open: true } } as unknown as Event);
    await new Promise<void>((r) => setTimeout(r, 0));
    assert.equal(renderWs.length, 1);
    assert.equal(renderStore.toastMessage, "");
    // Immediate second open via DOM toggle is debounced
    onlineToggle({ currentTarget: { open: true } } as unknown as Event);
    assert.equal(renderWs.length, 1);

    // Offline `sub_pocket` (`is_online: false`) skips auto-refresh when its drawer opens
    renderStore.applyRoute({ prefix: "/latter", path: "devices/sub_pocket/tools" });
    const offlineToggle = findDrawerToggle(renderDeviceToolsView(renderStore));
    assert.ok(offlineToggle);
    offlineToggle({ currentTarget: { open: true } } as unknown as Event);
    await new Promise<void>((r) => setTimeout(r, 0));
    assert.equal(renderWs.length, 1);
    // Verify live RPC-backed `parseDeviceRuntimeTelemetryRows()` renders RAM, PSRAM, BLE & link stats cleanly
    assert.deepEqual(parseDeviceRuntimeTelemetryRows(null), []);
    const telemRows = parseDeviceRuntimeTelemetryRows(
      {
        int_ram_free_kb: 212,
        int_ram_min_kb: 168,
        int_ram_largest_kb: 128,
        psram_min_kb: 24576,
        ble_active: true,
        link: {
          up_s: 7320,
          rst: "POWERON",
          disc: 1,
          bto: 2,
          rssi_avg: -48,
          rssi_min: -53,
          ha: 3,
          gap_s: 90,
          nvs_w: 4,
          nvs_e: 1,
          nvs_max_ms: 8,
        },
      },
      renderStore.hass,
    );
    assert.equal(telemRows.length, 9);
    assert.deepEqual(telemRows[0], {
      label: "Internal RAM (free / min / largest)",
      value: "212 / 168 / 128 KB",
    });
    assert.deepEqual(telemRows[1], { label: "PSRAM low-water mark", value: "24,576 KB" });
    assert.deepEqual(telemRows[2], { label: "BLE beacon radio", value: "Active" });
    assert.deepEqual(telemRows[3], { label: "Session uptime", value: "2h 2m" });
    assert.deepEqual(telemRows[4], { label: "Last reset", value: "POWERON", code: true });
    assert.deepEqual(telemRows[5], { label: "Wi-Fi disconnects", value: "1 (2 beacon timeouts)" });
    assert.deepEqual(telemRows[6], { label: "Wi-Fi avg / min", value: "-48 / -53 dBm" });
    assert.deepEqual(telemRows[7], { label: "Home Assistant sessions", value: "3 (max gap 1m 30s)" });
    assert.deepEqual(telemRows[8], { label: "NVS flash writes", value: "4 writes (1 erases, 8 ms max)" });
  });

  it("renders core_rev, firmware_outdated warning banner/badges, and screenless System overview counts", () => {
    const flattenTemplate = (node: unknown): string => {
      if (node === null || node === undefined || node === nothing) return "";
      if (typeof node === "string" || typeof node === "number" || typeof node === "boolean") {
        return String(node);
      }
      if (Array.isArray(node)) {
        return node.map(flattenTemplate).join("");
      }
      if (typeof node === "object") {
        const tpl = node as { strings?: readonly string[]; values?: readonly unknown[] };
        if (Array.isArray(tpl.strings)) {
          let out = "";
          for (let i = 0; i < tpl.strings.length; i += 1) {
            out += tpl.strings[i] ?? "";
            if (Array.isArray(tpl.values) && i < tpl.values.length) {
              out += flattenTemplate(tpl.values[i]);
            }
          }
          return out;
        }
      }
      return "";
    };

    const { store: currentStore } = createHeadlessStore({
      live: { core_rev: "2026112402", firmware_outdated: false },
    });
    currentStore.applyRoute({ prefix: "/latter", path: "devices/sub_desk/overview" });
    const summaryText = currentStore.tools.formatSystemInfoSummary();
    assert.ok(summaryText.includes("Minimum firmware core: 2026112402"));
    assert.equal(summaryText.includes("SDK"), false);
    assert.equal(renderFirmwareOutdatedBanner(currentStore), nothing);
    const currentToolsHtml = flattenTemplate(renderDeviceToolsView(currentStore));
    assert.ok(currentToolsHtml.includes("diag-core-rev"));
    assert.ok(currentToolsHtml.includes("2026112402"));
    assert.equal(currentToolsHtml.includes("diag-firmware-outdated-badge"), false);

    // Outdated firmware renders warning banner on Overview & Tools and badge on Diagnostics & Status card
    const { store: outdatedStore } = createHeadlessStore({
      live: { core_rev: "2026112202", firmware_outdated: true },
    });
    outdatedStore.applyRoute({ prefix: "/latter", path: "devices/sub_desk/overview" });
    const bannerHtml = flattenTemplate(renderFirmwareOutdatedBanner(outdatedStore));
    assert.ok(bannerHtml.includes("device-firmware-outdated-banner"));
    assert.ok(bannerHtml.includes("alert-warning"));
    assert.ok(bannerHtml.includes("Firmware update required"));
    assert.ok(bannerHtml.includes("2026112202"));
    assert.ok(bannerHtml.includes("2026112402"));

    const overviewHtml = flattenTemplate(renderDeviceOverviewView(outdatedStore));
    assert.ok(overviewHtml.includes("device-firmware-outdated-banner"));
    assert.ok(overviewHtml.includes("Firmware update required"));

    const outdatedToolsHtml = flattenTemplate(renderDeviceToolsView(outdatedStore));
    assert.ok(outdatedToolsHtml.includes("device-firmware-outdated-banner"));
    assert.ok(outdatedToolsHtml.includes("diag-core-rev"));
    assert.ok(outdatedToolsHtml.includes("diag-firmware-outdated-badge"));
    assert.ok(outdatedToolsHtml.includes("2026112202"));

    // BLE tags never show firmware outdated banners
    const { store: bleStore } = createHeadlessStore({
      config: { kind: "ble_tag", device_slug: "alex_phone" },
      live: { firmware_outdated: true },
    });
    assert.equal(renderFirmwareOutdatedBanner(bleStore), nothing);

    // System overview reports screenless devices cleanly without hardcoding "audio"
    const { store: screenlessStore } = createHeadlessStore({
      system_devices: [
        {
          subentry_id: "sub_relay",
          device_slug: "hallway_node",
          title: "Hallway Node",
          model_label: "Latter Node",
          area_id: "hallway",
          has_assigned_area: true,
          area_label: "Hallway",
          status_code: "online",
          status_label: "Online",
          is_online: true,
          kind: "device",
          has_display: false,
          has_battery: false,
          is_roaming: false,
          device_group: "custom",
          device_remote_group: "area_auto",
          device_group_name: "Custom",
          assigned_person: "",
          active_area_name: "Hallway",
          is_latter_native: true,
          battery_level: null,
          is_charging: false,
          is_usb_connected: true,
          wifi_rssi: -52,
          ip_address: "192.168.10.40",
          has_ble: true,
          ble_tracked: false,
          ble_survey_rows: [],
          ble_packets_seen: 0,
          is_current: true,
        },
      ],
    });
    const sysOvHtml = flattenTemplate(renderSystemOverviewView(screenlessStore));
    assert.ok(sysOvHtml.includes("1 screenless"));
    assert.equal(sysOvHtml.includes("1 audio"), false);
  });

  it("wires 3-way glass_style across Display view, Group baselines, Batch controls, and capability gates", async () => {
    const flattenTemplate = (node: unknown): string => {
      if (node === null || node === undefined || node === nothing) return "";
      if (typeof node === "string" || typeof node === "number" || typeof node === "boolean") {
        return String(node);
      }
      if (Array.isArray(node)) {
        return node.map(flattenTemplate).join("");
      }
      if (typeof node === "object") {
        const tpl = node as { strings?: readonly string[]; values?: readonly unknown[] };
        if (Array.isArray(tpl.strings)) {
          let out = "";
          for (let i = 0; i < tpl.strings.length; i += 1) {
            out += tpl.strings[i] ?? "";
            if (Array.isArray(tpl.values) && i < tpl.values.length) {
              out += flattenTemplate(tpl.values[i]);
            }
          }
          return out;
        }
      }
      return "";
    };

    // Capability gating for `glass_style` (`display`) and `do_not_disturb` (`display_or_audio`)
    assert.equal(isCatalogItemSupported(DEVICE_PREF_SPECS_MAP.glass_style!, { has_display: true }), true);
    assert.equal(isCatalogItemSupported(DEVICE_PREF_SPECS_MAP.glass_style!, { has_display: false }), false);
    assert.equal(
      isCatalogItemSupported(DEVICE_PREF_SPECS_MAP.do_not_disturb!, {
        has_display: false,
        has_audio: true,
      }),
      true,
    );
    assert.equal(
      isCatalogItemSupported(DEVICE_PREF_SPECS_MAP.do_not_disturb!, {
        has_display: true,
        has_audio: false,
      }),
      true,
    );
    assert.equal(
      isCatalogItemSupported(DEVICE_PREF_SPECS_MAP.do_not_disturb!, {
        has_display: false,
        has_audio: false,
      }),
      false,
    );

    const glassPref = {
      key: "glass_style",
      label: "Glass Style",
      section: "display",
      group_tier: "display",
      domain: "select",
      value: "Auto",
      options: ["Auto", "Clear", "Dark"],
    };
    const glassBatchCtrl: SharedControlItem = {
      key: "display:select:glass_style",
      pref_key: "glass_style",
      tier: "display",
      section: "display",
      section_title: "Display",
      name: "Glass Style",
      domain: "select",
      options: ["Auto", "Clear", "Dark"],
      targets: [
        {
          subentry_id: "sub_desk",
          device_slug: "desk_assistant",
          device_group: "wall_panels",
          is_online: true,
          is_roaming: false,
          pref_key: "glass_style",
          state: "Auto",
        },
        {
          subentry_id: "sub_pocket",
          device_slug: "pocket_assistant",
          device_group: "pocket_carry",
          is_online: false,
          is_roaming: true,
          pref_key: "glass_style",
          state: "Clear",
        },
      ],
    };

    const { store, wsLog } = createHeadlessStore({
      config: {
        device_slug: "desk_assistant",
        kind: "device",
        is_roaming: false,
        device_group: "wall_panels",
        glass_style: "Auto",
      },
      device_prefs: [glassPref],
      system_controls: [glassBatchCtrl],
    });
    store.applyRoute({ prefix: "/latter", path: "devices/sub_desk/display" });

    // 1. Device -> Display renders `#cfg-glass_style` with Auto / Clear / Dark & description
    const displayHtml = flattenTemplate(renderDeviceDisplayView(store));
    assert.ok(displayHtml.includes("cfg-glass_style"));
    assert.ok(displayHtml.includes("Glass style"));
    assert.ok(displayHtml.includes("Auto adapts contrast over bright backdrops"));
    assert.ok(displayHtml.includes("Clear"));
    assert.ok(displayHtml.includes("Dark"));

    // Staging `glass_style` flushes cleanly via `save_device_config`
    store.entity.stageDeviceSetting("glass_style", "Dark", "cfg-glass_style", 60_000);
    await store.entity.flushDeviceBucket("sub_desk");
    assert.equal(wsLog.length, 1);
    assert.deepEqual((wsLog[0]?.payload as Record<string, unknown>)?.config, {
      glass_style: "Dark",
    });

    // Non-display capabilities omit `#cfg-glass_style`
    const { store: headlessStore } = createHeadlessStore({
      capabilities: { has_display: false, has_audio: true },
    });
    const headlessDisplayHtml = flattenTemplate(renderDeviceDisplayView(headlessStore));
    assert.equal(headlessDisplayHtml.includes("cfg-glass_style"), false);

    // 2. Group Baseline Drawer renders `Glass style` under Display tier when `include_display: true`
    const displayGroup: DeviceGroup = {
      id: "custom_display",
      name: "Bright Areas",
      description: "Display group",
      builtin: false,
      include_display: true,
      include_interface: false,
      device_config: { glass_style: "Clear", color_profile: "Steel Blue" },
    };
    store.openGroupIds.add("custom_display");
    const deskMember = store.state!.system_devices.find((d) => d.subentry_id === "sub_desk")!;
    const groupDrawerHtml = flattenTemplate(
      renderGroupBaselineDrawer(store, displayGroup, [deskMember], [deskMember]),
    );
    assert.ok(groupDrawerHtml.includes("Glass style"));
    assert.ok(groupDrawerHtml.includes("Glass style for Bright Areas"));

    // Screenless custom group omits `Glass style` in Display tier
    const screenlessMember: SystemDeviceEntry = { ...deskMember, has_display: false };
    const screenlessGroupHtml = flattenTemplate(
      renderGroupBaselineDrawer(store, displayGroup, [screenlessMember], [screenlessMember]),
    );
    assert.equal(screenlessGroupHtml.includes("Glass style"), false);

    // Group overlay respects `include_display` for `glass_style` (`group_tier: "display"`)
    const payloadWithDisplayGrp = structuredClone(store.state!);
    payloadWithDisplayGrp.device_groups = [displayGroup];
    payloadWithDisplayGrp.config.device_group = "custom_display";
    payloadWithDisplayGrp.config.glass_style = "Clear";
    overlayDevicePrefsOnSections(payloadWithDisplayGrp, { glass_style: "Dark" });
    assert.equal(payloadWithDisplayGrp.config.device_group, "custom");
    overlayDevicePrefsOnSections(payloadWithDisplayGrp, { device_group: "custom_display" });
    assert.equal(payloadWithDisplayGrp.config.glass_style, "Clear");

    // 3. BatchController detects Mixed `glass_style` values, stages `"Dark"`, and previews detachment
    const effBefore = store.groups.getEffectiveBatchValue(glassBatchCtrl);
    assert.equal(effBefore.mixed, true);
    store.groups.stageBatchSetting("glass_style", "Dark");
    const effAfter = store.groups.getEffectiveBatchValue(glassBatchCtrl);
    assert.equal(effAfter.staged, true);
    assert.equal(effAfter.value, "Dark");
    assert.equal(store.groups.previewBatchDetachmentCount(), 2);
  });

  it("renders grouped Home screen element toggles, conditional tap actions, and display_battery gating (D-085)", () => {
    const flattenTemplate = (node: unknown): string => {
      if (node === null || node === undefined || node === nothing) return "";
      if (typeof node === "string" || typeof node === "number" || typeof node === "boolean") {
        return String(node);
      }
      if (Array.isArray(node)) return node.map(flattenTemplate).join("");
      if (typeof node === "object") {
        const tpl = node as { strings?: readonly string[]; values?: readonly unknown[] };
        if (Array.isArray(tpl.strings)) {
          let out = "";
          for (let i = 0; i < tpl.strings.length; i += 1) {
            out += tpl.strings[i] ?? "";
            if (Array.isArray(tpl.values) && i < tpl.values.length) {
              out += flattenTemplate(tpl.values[i]);
            }
          }
          return out;
        }
      }
      return "";
    };

    // 1. Battery display shows all 5 new controls + Home elements / Background subsections + "None" option
    const { store: battStore } = createHeadlessStore({
      capabilities: { has_display: true, has_battery: true, is_round: true },
      config: {
        home_screen_enabled: true,
        home_show_time: true,
        home_show_date: true,
        home_show_weather: true,
        home_show_battery: true,
        home_clock_tap_action: "Time App",
        home_date_tap_action: "Overview",
        home_weather_tap_action: "Current Weather",
      },
    });
    const fullHtml = flattenTemplate(renderDeviceInterfaceView(battStore));
    assert.ok(fullHtml.includes("Home elements"));
    assert.ok(fullHtml.includes("Background"));
    assert.ok(fullHtml.includes("cfg-home_show_time"));
    assert.ok(fullHtml.includes("cfg-home_clock_tap_action"));
    assert.ok(fullHtml.includes("cfg-home_show_date"));
    assert.ok(fullHtml.includes("cfg-home_date_tap_action"));
    assert.ok(fullHtml.includes("cfg-home_show_weather"));
    assert.ok(fullHtml.includes("cfg-home_weather_tap_action"));
    assert.ok(fullHtml.includes("cfg-home_show_battery"));
    assert.ok(fullHtml.includes("5-day forecast"));
    assert.ok(fullHtml.includes("None"));

    // 2. Hiding Time / Date / Weather hides their paired tap selects; non-battery device hides Show battery
    const { store: wallStore } = createHeadlessStore({
      capabilities: { has_display: true, has_battery: false, is_round: false },
      config: {
        home_screen_enabled: true,
        start_screen: "Clock Face",
        home_show_time: false,
        home_show_date: false,
        home_show_weather: false,
      },
    });
    const hiddenHtml = flattenTemplate(renderDeviceInterfaceView(wallStore));
    assert.ok(hiddenHtml.includes("cfg-home_show_time"));
    assert.equal(hiddenHtml.includes("cfg-home_clock_tap_action"), false);
    assert.equal(hiddenHtml.includes("cfg-home_date_tap_action"), false);
    assert.equal(hiddenHtml.includes("cfg-home_weather_tap_action"), false);
    assert.equal(hiddenHtml.includes("cfg-home_show_battery"), false);
    // Start screen == Clock Face still shows Clock face selector cleanly when Home time is hidden
    assert.ok(hiddenHtml.includes("cfg-clock_face"));

    // 3. Group Baseline Drawer omits Show battery for wall_panels (has_battery: false) and includes it for pocket_carry
    const deskMember = wallStore.state!.system_devices.find((d) => d.subentry_id === "sub_desk")!;
    const wallGroup: DeviceGroup = {
      id: "wall_panels",
      name: "Wall & Desk Panels",
      description: "Stationary displays",
      builtin: true,
      include_display: false,
      include_interface: true,
      device_config: { home_show_time: true, home_show_date: false, home_show_weather: true },
    };
    wallStore.openGroupIds.add("wall_panels");
    const wallGrpHtml = flattenTemplate(
      renderGroupBaselineDrawer(wallStore, wallGroup, [deskMember], [deskMember]),
    );
    assert.ok(wallGrpHtml.includes("Home time tap"));
    assert.equal(wallGrpHtml.includes("Home date tap"), false);
    assert.ok(wallGrpHtml.includes("Home weather tap"));
    assert.equal(wallGrpHtml.includes("Show battery"), false);

    const pocketGroup: DeviceGroup = {
      id: "pocket_carry",
      name: "Pocket Carry",
      description: "Battery displays",
      builtin: true,
      include_display: false,
      include_interface: true,
      device_config: {},
    };
    battStore.openGroupIds.add("pocket_carry");
    const pocketGrpHtml = flattenTemplate(
      renderGroupBaselineDrawer(battStore, pocketGroup, [], [deskMember]),
    );
    assert.ok(pocketGrpHtml.includes("Show battery"));
  });
});
