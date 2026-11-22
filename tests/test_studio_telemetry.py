"""Studio diagnostics telemetry, BLE tag mode, presence views, managed/discovered lifecycle, and System overview."""

from __future__ import annotations

import re
import unittest

from tests.conftest import (
    NODE_BIN as NODE,
    run_studio_node_esm as _run_node_esm,
)


@unittest.skipUnless(NODE, "node is not installed")
class TestToolsDiagnosticsAndPresenceViews(unittest.TestCase):
    """Diagnostics telemetry, BLE tag mode, presence modes, lifecycle views, walk-around UX, and System overview."""

    def test_standard_diagnostics_parsed_telemetry_and_ble_tag_mode(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { renderDeviceOverviewView } from "./src/views/device-overview-view.js";
            import { renderDeviceToolsView } from "./src/views/device-tools-view.js";
            function buildTools(isBle = false) {
              return makeFakeStore({
                activeSubentryId: "sub_1",
                sections: isBle ? {} : {
                  network: [
                    { entity_id: "update.desk_panel_firmware", domain: "update", name: "Firmware", state: "off" },
                    { entity_id: "sensor.desk_panel_wifi_signal", domain: "sensor", name: "Wi-Fi signal", state: "-54", unit: "dBm" },
                    { entity_id: "sensor.desk_panel_ip_address", domain: "sensor", name: "IP address", state: "192.168.1.44" },
                    { entity_id: "sensor.desk_panel_connected_ssid", domain: "sensor", name: "Connected SSID", state: "HomeLAN" },
                    { entity_id: "sensor.desk_panel_system_rpc_outbox", domain: "sensor", name: "System: RPC Outbox", state: '{"v":3,"cmd":"media_play","seq":99}' },
                    { entity_id: "sensor.desk_panel_system_link_report", domain: "sensor", name: "System: Link Report", state: "up=7320 rst=POWERON bto=1 disc=2 rsn=0 rssi=-55/-62 n=120 wlk=0.0 ls=45 slp=78.5 awk=21.5 api=3 ha=2 gap=14 down=0 nvs=5/0/3" },
                    { entity_id: "sensor.desk_panel_system_hardware_manifest", domain: "sensor", name: "System: Hardware Manifest", state: '{"v":2,"contract":3,"board":"waveshare_s3_square_4_0","w":480,"h":480,"shape":"square","display":1,"touch":1,"audio":1,"mic":1,"spk":1,"imu":1,"battery":0,"stationary":1,"wearable":0,"ips":1,"chip":"ESP32-S3","psram_mb":8,"minor":4}' },
                  ],
                  developer: [
                    { entity_id: "switch.desk_panel_system_telemetry_profiler", domain: "switch", name: "Telemetry profiler", state: "off" },
                    { entity_id: "button.desk_panel_system_log_memory_report", domain: "button", name: "Log memory report", state: "unknown" },
                    { entity_id: "sensor.desk_panel_system_internal_ram_low_water", domain: "sensor", name: "Internal RAM low water", state: "64", unit: "kB" },
                  ],
                },
                state: {
                  title: isBle ? "Keychain Tag" : "Desk Panel",
                  config: isBle
                    ? { kind: "ble_tag", ble_target_address: "AA:BB:CC:11:22:33" }
                    : { kind: "device", device_slug: "desk_panel", security_pin_policy: "auto", has_security_pin: true },
                  live: isBle ? {} : { device_sw_version: "3.0.0", sdk_rev: "2026111801", effective_security_pin_policy: "require_pin" },
                  links: isBle ? { entry_id: "ent_1" } : { entry_id: "ent_1", esphome_device_id: "esp_dev_1", latter_device_id: "lat_dev_1" },
                  esphome: isBle ? {} : { device: { mac: "10:20:30:40:50:60" } },
                  system_devices: [
                    isBle
                      ? { subentry_id: "sub_1", kind: "ble_tag", is_online: true, ble_survey_rows: [{ is_winner: true, effective_rssi: -68 }] }
                      : { subentry_id: "sub_1", kind: "device", is_online: true, model_label: "Latter Square 4.0", wifi_rssi: -54, ip_address: "192.168.1.44" },
                  ],
                },
              }).store;
            }
            function buildOverview(mode) {
              if (mode === "ble") {
                return makeFakeStore({
                  activeSubentryId: "sub_ble",
                  state: {
                    config: { kind: "ble_tag", ble_target_address: "AA:BB:CC:11:22:33" },
                    capabilities: {},
                    live: { active_area_name: "Entryway", ble_closest_proxy: "Entry Proxy" },
                    links: { entry_id: "ent_1" },
                    system_devices: [
                      {
                        subentry_id: "sub_ble",
                        kind: "ble_tag",
                        status_code: "online",
                        status_label: "Detected",
                        has_assigned_area: false,
                        ble_survey_rows: [{ is_winner: true, effective_rssi: -64, distance_m: 1.8 }],
                      },
                    ],
                  },
                }).store;
              }
              const isBattery = mode === "battery";
              const isOffline = mode === "offline";
              return makeFakeStore({
                activeSubentryId: "sub_1",
                sections: isBattery
                  ? { network: [{ entity_id: "update.roaming_pocket_firmware", domain: "update", name: "Firmware", state: "off" }] }
                  : {},
                state: {
                  config: {
                    kind: "device",
                    device_slug: "roaming_pocket",
                    device_group: "handhelds",
                    device_remote_group: isBattery ? "group:living_tv" : "area_auto",
                    native_ble_tracking: isBattery,
                  },
                  capabilities: {
                    has_display: true,
                    has_power: true,
                    has_battery: isBattery,
                    has_ble_beacon: isBattery,
                    is_roaming_device: isBattery,
                  },
                  live: {
                    active_area_name: "Kitchen",
                    ble_closest_proxy: isBattery ? "Kitchen Proxy" : "",
                    device_sw_version: "3.0.0",
                    fw_update_available: mode === "mains",
                  },
                  links: { entry_id: "ent_1", esphome_device_id: "esp_1", latter_device_id: "lat_1" },
                  esphome: { device: { sw_version: "3.0.0", model: "Pocket" } },
                  device_groups: [{ id: "handhelds", name: "Handhelds" }],
                  system_config: {
                    remote_groups: [{ id: "living_tv", name: "Living Area TV", area_id: "living", remotes: ["remote.tv"] }],
                  },
                  system_devices: [
                    {
                      subentry_id: "sub_1",
                      kind: "device",
                      is_online: !isOffline,
                      status_code: isOffline ? "offline" : mode === "mains" ? "update" : "online",
                      status_label: isOffline ? "Offline" : mode === "mains" ? "Update available" : "Online",
                      has_display: true,
                      has_battery: isBattery,
                      has_assigned_area: !isBattery,
                      area_label: "Office",
                      battery_level: isBattery ? 82 : null,
                      is_charging: isBattery,
                      is_usb_connected: isBattery,
                      wifi_rssi: isBattery ? -58 : -84,
                      ip_address: "192.168.1.44",
                      ble_survey_rows: isBattery ? [{ is_winner: true, effective_rssi: -61, distance_m: 2.4 }] : [],
                    },
                  ],
                },
              }).store;
            }
            process.stdout.write(JSON.stringify({
              espMarkup: renderToHtml(renderDeviceToolsView(buildTools(false))),
              bleMarkup: renderToHtml(renderDeviceToolsView(buildTools(true))),
              ovBattery: renderToHtml(renderDeviceOverviewView(buildOverview("battery"))),
              ovMainsUpdate: renderToHtml(renderDeviceOverviewView(buildOverview("mains"))),
              ovOffline: renderToHtml(renderDeviceOverviewView(buildOverview("offline"))),
              ovBle: renderToHtml(renderDeviceOverviewView(buildOverview("ble"))),
            }));
            """
        )

        esp = got["espMarkup"]
        ble = got["bleMarkup"]
        ov_bat = got["ovBattery"]
        ov_mains = got["ovMainsUpdate"]
        ov_offline = got["ovOffline"]
        ov_ble = got["ovBle"]

        self.assertIn("Model", esp)
        self.assertIn("Latter Square 4.0", esp)
        self.assertIn('id="diag-node-name"', esp)
        self.assertIn("desk_panel", esp)
        self.assertIn('id="diag-sdk-rev"', esp)
        self.assertIn("v3.0.0", esp)
        self.assertIn("2026111801", esp)
        self.assertIn("192.168.1.44", esp)
        self.assertIn("10:20:30:40:50:60", esp)
        self.assertIn("HomeLAN", esp)
        self.assertIn("Open in Home Assistant", esp)
        self.assertIn("Reconfigure", esp)
        self.assertNotIn("All Entities", esp)
        self.assertNotIn("media_play", esp)
        self.assertIn("Developer &amp; telemetry", esp)
        self.assertIn("2h 2m", esp)
        self.assertIn("waveshare_s3_square_4_0", esp)
        self.assertIn("ESP32-S3 • 8 MB PSRAM", esp)

        # BLE tag hides Developer & telemetry
        self.assertIn("-68 dBm", ble)
        self.assertIn("AA:BB:CC:11:22:33", ble)
        self.assertNotIn("Developer &amp; telemetry", ble)

        # Overview: Battery (`has_battery=true`) + real `update.*` entity -> "Up to date" + "Open in Home Assistant" (`Q12`)
        for expected in (
            "Online",
            "Current Area",
            "Kitchen",
            "Battery",
            "82%",
            "Charging",
            "Wi-Fi signal",
            "-58 dBm",
            "Firmware",
            "v3.0.0",
            "Up to date",
            "Handhelds",
            "Living Area TV",
            "Open in Home Assistant",
        ):
            self.assertIn(expected, ov_bat)
        self.assertNotIn("Download backup", ov_bat)

        # Plugged-in (`has_battery=false`) shows Power / Plugged in
        for expected in ("Update available", "Office", "Power", "Plugged in", "Follow Area"):
            self.assertIn(expected, ov_mains)

        # Offline Device renders `.offline-banner` (`D-066` / `Q8`)
        self.assertIn("offline-banner", ov_offline)
        self.assertIn("Device is offline or hibernating", ov_offline)

        # BLE Tag Overview hides Quick actions
        for expected in ("Online", "Entryway", "-64 dBm", "AA:BB:CC:11:22:33"):
            self.assertIn(expected, ov_ble)
        self.assertNotIn("Quick actions", ov_ble)

    def test_presence_view_static_assigned_area_vs_ble_roaming_modes(self) -> None:
        """D-032 & D-066: Static mode hides BLE identity & Voice Follows Me while keeping area_handoff visible."""
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { renderDeviceAudioView } from "./src/views/device-audio-view.js";
            import { renderDevicePresenceView } from "./src/views/device-presence-view.js";
            function build(bleTracking) {
              return makeFakeStore({
                activeSubentryId: "sub_1",
                sections: {
                  presence: [
                    { entity_id: "pref:ble_beacon_mode", pref_key: "ble_beacon_mode", domain: "select", name: "BLE beacon mode", state: "Handheld Only", options: ["Handheld Only", "Always"] },
                  ],
                },
                state: {
                  config: {
                    kind: "device",
                    native_ble_tracking: bleTracking,
                    ble_auto_switch: bleTracking,
                    sync_device_area: bleTracking,
                    area_handoff: true,
                    default_area: "living_room",
                    ble_target_address: "",
                    ble_beacon_uuid: "E2C56DB5-DFFB-48D2-B060-D0F5A71096E1",
                  },
                  capabilities: { has_display: true, has_audio: true, is_roaming_device: true },
                  catalog: {
                    areas: [
                      { id: "living_room", name: "Living Room" },
                      { id: "kitchen", name: "Kitchen" },
                    ],
                  },
                },
              }).store;
            }
            const staticStore = build(false);
            const roamingStore = build(true);
            process.stdout.write(JSON.stringify({
              staticPresence: renderToHtml(renderDevicePresenceView(staticStore)),
              roamingPresence: renderToHtml(renderDevicePresenceView(roamingStore)),
              staticAudio: renderToHtml(renderDeviceAudioView(staticStore)),
              roamingAudio: renderToHtml(renderDeviceAudioView(roamingStore)),
            }));
            """
        )
        self.assertIn("Assigned Area", got["staticPresence"])
        self.assertNotIn("card-ble-identity", got["staticPresence"])
        self.assertNotIn("BLE beacon mode", got["staticPresence"])
        self.assertNotIn("Voice Follows Me", got["staticAudio"])
        self.assertIn('id="cfg-area_handoff"', got["staticAudio"])

        self.assertIn("card-ble-identity", got["roamingPresence"])
        self.assertIn("Fallback Area", got["roamingPresence"])
        self.assertNotIn("Assigned Area", got["roamingPresence"])
        self.assertIn("Voice Follows Me", got["roamingAudio"])
        self.assertIn('id="cfg-area_handoff"', got["roamingAudio"])

    def test_managed_and_discovered_lifecycle_views_and_badge(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { LatterStudio } from "./src/latter-studio.js";
            import { renderDevicesDiscoveredView } from "./src/views/devices-discovered-view.js";
            import { renderDevicesListView } from "./src/views/devices-list-view.js";
            function buildHost(overrides = {}, extraState = {}) {
              const { store } = makeFakeStore({
                currentScope: overrides.currentScope ?? "device",
                currentViewId: overrides.currentViewId ?? "select_device_prompt",
                deviceSelected: overrides.deviceSelected ?? false,
                activeSubentryId: overrides.activeSubentryId ?? "",
                state: {
                  title: "Desk Panel",
                  config: { kind: "device" },
                  device_groups: [
                    { id: "wall_panels", name: "Wall & Desk Panels" },
                    { id: "handhelds", name: "Handhelds" },
                  ],
                  catalog: { persons: [{ id: "person.alex", name: "Alex" }] },
                  system_devices: [
                    {
                      subentry_id: "sub_1",
                      title: "Desk Panel",
                      model_label: "Square 4.0 (480x480)",
                      area_label: "Office",
                      device_group: "wall_panels",
                      device_group_name: "Wall & Desk Panels",
                      status_code: "online",
                      status_label: "Online",
                      is_online: true,
                      is_latter_native: true,
                      has_display: true,
                      is_roaming: false,
                      ble_tracked: false,
                      assigned_person: "",
                      kind: "device",
                    },
                    {
                      subentry_id: "sub_2",
                      title: "Pocket Assistant",
                      model_label: "Pocket 2.06 (410x502)",
                      area_label: "Roaming",
                      device_group: "handhelds",
                      device_group_name: "Handhelds",
                      status_code: "online",
                      status_label: "Online",
                      is_online: true,
                      is_latter_native: true,
                      has_display: true,
                      is_roaming: true,
                      ble_tracked: true,
                      assigned_person: "person.alex",
                      kind: "device",
                    },
                  ],
                  discovered_latter_devices: [],
                  ignored_latter_devices: [],
                  discovered_ble_devices: [
                    {
                      title: "Zoe's Watch",
                      target_address: "device_tracker.watch_ble",
                      kind: "Private BLE (phone or watch)",
                      is_tracker: true,
                      rssi: -58,
                      area_name: "Office",
                    },
                    {
                      title: "Living TV BLE",
                      target_address: "11:22:33:44:55:66",
                      kind: "Named BLE device",
                      is_tracker: false,
                      rssi: -79,
                      area_name: "Living Room",
                    },
                  ],
                  ...extraState,
                },
              });
              if (overrides.deviceCategoryFilter) {
                store.deviceCategoryFilter = overrides.deviceCategoryFilter;
              }
              return { store, el: Object.assign(Object.create(LatterStudio.prototype), { store }) };
            }
            const zero = buildHost();
            const sidebarZeroLatter = renderToHtml(LatterStudio.prototype._renderSidebar.call(zero.el));
            const one = buildHost({}, {
              discovered_latter_devices: [
                {
                  esphome_device_id: "esp_new_1",
                  node_name: "kitchen_panel",
                  title: "Kitchen Panel",
                  model_label: "Square 4.0 (480x480)",
                  area_name: "Kitchen",
                  default_group: "wall_panels",
                },
              ],
              ignored_latter_devices: [
                {
                  esphome_device_id: "esp_ignored_1",
                  node_name: "test_bench",
                  title: "Test Bench",
                  model_label: "Pocket",
                  area_name: "",
                  default_group: "pocket_carry",
                },
              ],
            });
            const sidebarOneLatter = renderToHtml(LatterStudio.prototype._renderSidebar.call(one.el));
            const drilldown = buildHost({ deviceSelected: true, activeSubentryId: "sub_1", currentViewId: "dashboard" });
            const sidebarDrilldown = renderToHtml(LatterStudio.prototype._renderSidebar.call(drilldown.el));
            const managedRoaming = renderToHtml(renderDevicesListView(buildHost({ deviceCategoryFilter: "roaming" }).store));
            const discAll = renderToHtml(renderDevicesDiscoveredView(one.store));
            one.store.discoveredBleSort = "rssi";
            const discSortRssi = renderToHtml(renderDevicesDiscoveredView(one.store));
            one.store.discoveredBleSort = "name";
            one.store.discoveredBleKindFilter = "tracker";
            const discTrackersOnly = renderToHtml(renderDevicesDiscoveredView(one.store));
            process.stdout.write(JSON.stringify({
              sidebarZeroLatter,
              sidebarOneLatter,
              sidebarDrilldown,
              managedRoaming,
              discAll,
              discSortRssi,
              discTrackersOnly,
            }));
            """
        )
        self.assertIn('href="/latter/devices"', got["sidebarZeroLatter"])
        self.assertIn('href="/latter/devices/discovered"', got["sidebarZeroLatter"])
        self.assertIn('id="nav-system-count"', got["sidebarZeroLatter"])
        self.assertNotIn("nav-discovered-count", got["sidebarZeroLatter"])

        self.assertIn('id="nav-discovered-count"', got["sidebarOneLatter"])
        self.assertIn("← Managed", got["sidebarDrilldown"])

        self.assertNotIn(">Desk Panel<", got["managedRoaming"])
        self.assertIn('<a href="/latter/devices/sub_2">Pocket Assistant</a>', got["managedRoaming"])

        self.assertIn("Kitchen Panel", got["discAll"])
        self.assertIn("Ignore", got["discAll"])
        self.assertIn("Ignored (1)", got["discAll"])
        self.assertLess(got["discAll"].index("Living TV BLE"), got["discAll"].index("Zoe's Watch"))
        self.assertLess(got["discSortRssi"].index("Zoe's Watch"), got["discSortRssi"].index("Living TV BLE"))
        self.assertIn("Zoe's Watch", got["discTrackersOnly"])
        self.assertNotIn("Living TV BLE", got["discTrackersOnly"])

    def test_system_presence_walk_around_ux_and_ble_tracked_filter(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToContainer, renderToHtml } from "./test/fake-store.js";
            import { renderSystemPresenceView } from "./src/views/system-presence-view.js";
            globalThis.requestAnimationFrame = (cb) => { cb(0); return 1; };
            const deskUntracked = {
              subentry_id: "sub_desk",
              title: "Desk Assistant",
              has_ble: true,
              ble_tracked: false,
              kind: "device",
              active_area_name: "Office",
              ble_packets_seen: 0,
              ble_survey_rows: [],
            };
            const pocketTracked = {
              subentry_id: "sub_pocket",
              title: "Pocket Assistant",
              has_ble: true,
              ble_tracked: true,
              kind: "device",
              active_area_name: "Bedroom",
              ble_packets_seen: 14,
              ble_survey_rows: [
                {
                  area_id: "bedroom",
                  area_name: "Bedroom",
                  scanner_source: "AA:BB:CC:DD:EE:01",
                  scanner_name: "Bedroom Proxy",
                  raw_rssi: -58,
                  effective_rssi: -57,
                  offset_db: 1.0,
                  distance_m: 1.2,
                  age_seconds: 1,
                  is_fresh: true,
                  is_winner: true,
                },
                {
                  area_id: "",
                  area_name: "",
                  scanner_source: "AA:BB:CC:DD:EE:02",
                  scanner_name: "Hallway Plug",
                  raw_rssi: -76,
                  effective_rssi: -76,
                  offset_db: 0,
                  distance_m: 4.8,
                  age_seconds: 2,
                  is_fresh: true,
                  is_winner: false,
                },
              ],
            };
            const keyringTag = {
              subentry_id: "sub_tag",
              title: "Keyring Tag",
              has_ble: false,
              ble_tracked: false,
              kind: "ble_tag",
              active_area_name: "Kitchen",
              ble_packets_seen: 5,
              ble_survey_rows: [],
            };
            const { store, sysCalls, scrolled, focused } = makeFakeStore({
              activeSubentryId: "sub_desk",
              state: {
                system_config: {
                  ble_away_timeout_s: 180,
                  ble_max_radius_m: 12,
                  ble_max_velocity_mps: 3.5,
                  ble_attenuation: 2.2,
                },
                system_devices: [
                  structuredClone(deskUntracked),
                  structuredClone(pocketTracked),
                  structuredClone(keyringTag),
                ],
                ble_area_signatures: [
                  { area_id: "bedroom", area_name: "Bedroom", floor_id: "upstairs", has_ble_proxy: true, has_signature: true, scanner_count: 2, sample_count: 18, captured_at: "2026-11-16T20:00:00Z" },
                  { area_id: "office", area_name: "Office", floor_id: "downstairs", has_ble_proxy: false, has_signature: false, scanner_count: 0, sample_count: 0, captured_at: "" },
                ],
                live: {
                  area_presence_grid: [
                    { area_id: "bedroom", area_name: "Bedroom", floor_name: "Upstairs", is_occupied: true, confidence_pct: 84, occupant_names: ["Alex"], winning_rssi: -57, closest_distance_m: 1.2, match_method: "signature", fusion_mode: "weighted", fusion_threshold_pct: 50, fusion_sensors: [], fusion_sensor_choices: [] },
                  ],
                },
              },
            });
            const defaultSurveyAfterFilter = store.bleSurveySubentryId;
            const activeRendered = renderToHtml(renderSystemPresenceView(store));
            store.groups.selectBleCalibrateArea("office", true);
            const handoffActiveAfterSelect = store.bleCalibrateHandoffActive;
            const handoffDom = renderToContainer(renderSystemPresenceView(store));
            const afterBridgeRendered = handoffDom.innerHTML;
            await store.groups.captureBleAreaSignature("office");
            const handoffAfterCapture = store.bleCalibrateHandoffActive;
            store.groups.toggleBleLiveStream(false);
            const pausedRendered = renderToHtml(renderSystemPresenceView(store));
            store.applyBleSurveyDelta({
              type: "ble_survey_delta",
              subentry_id: "sub_pocket",
              ble_packets_seen: 99,
              ble_survey_rows: [{ area_id: "kitchen", area_name: "Kitchen", scanner_source: "AA:BB:CC:DD:EE:99", scanner_name: "Kitchen Proxy", raw_rssi: -42, effective_rssi: -42, offset_db: 0, distance_m: 0.5, age_seconds: 0, is_fresh: true, is_winner: true }],
            });
            const afterPausedDeltaDev = structuredClone(store.groups.getActiveSurveyDevice());
            store.groups.toggleBleLiveStream(true);
            store.applyBleSurveyDelta({
              type: "ble_survey_delta",
              subentry_id: "sub_pocket",
              ble_packets_seen: 42,
              ble_survey_rows: [{ area_id: "kitchen", area_name: "Kitchen", scanner_source: "AA:BB:CC:DD:EE:99", scanner_name: "Kitchen Proxy", raw_rssi: -44, effective_rssi: -44, offset_db: 0, distance_m: 0.6, age_seconds: 0, is_fresh: true, is_winner: true }],
            });
            const afterResumedDeltaDev = structuredClone(store.groups.getActiveSurveyDevice());
            process.stdout.write(JSON.stringify({
              defaultSurveyAfterFilter,
              activeRendered,
              scrolled,
              focused,
              sysCalls,
              handoffActiveAfterSelect,
              afterBridgeRendered,
              handoffAfterCapture,
              pausedRendered,
              afterPausedDeltaDev,
              afterResumedDeltaDev,
            }));
            """
        )
        self.assertEqual(got["defaultSurveyAfterFilter"], "sub_pocket")
        self.assertNotIn("Desk Assistant", got["activeRendered"])
        self.assertIn("Pocket Assistant (Bedroom)", got["activeRendered"])
        self.assertIn('<h4 class="area-box-title">Bedroom</h4>', got["activeRendered"])
        self.assertIn("Standing in Area", got["activeRendered"])
        self.assertIn("Pause stream", got["activeRendered"])
        self.assertIn("Resume stream", got["pausedRendered"])
        self.assertTrue(got["handoffActiveAfterSelect"])
        self.assertIn("ble-calibrate-handoff-banner", got["afterBridgeRendered"])
        self.assertFalse(got["handoffAfterCapture"])
        self.assertEqual(got["afterPausedDeltaDev"]["ble_packets_seen"], 14)
        self.assertEqual(got["afterResumedDeltaDev"]["ble_packets_seen"], 42)
        self.assertEqual(got["sysCalls"][0]["command"], "capture_ble_area_signature")

    def test_system_overview_visual_status_deployment_and_capabilities(self) -> None:
        got = _run_node_esm(
            """
            import "./test/dom-shim.js";
            import { makeFakeStore, renderToHtml } from "./test/fake-store.js";
            import { renderSystemOverviewView } from "./src/views/system-overview-view.js";
            function build(withAlerts) {
              return makeFakeStore({
                state: {
                  version: "3.0.0",
                  ble_proxy_count: 5,
                  has_security_pin: !withAlerts,
                  issues: withAlerts
                    ? [{ issue_id: "device_crashed_sub1", kind: "device_crashed", severity: "error", subentry_id: "sub_1", device_title: "Kitchen Panel" }]
                    : [],
                  discovered_latter_devices: withAlerts
                    ? [{ esphome_device_id: "esp_new", node_name: "office_dock", title: "Office Dock", model_label: "Latter 4.0", area_name: "Office", default_group: "wall_panels" }]
                    : [],
                  device_groups: [
                    { id: "pocket_carry", name: "Pocket Carry", description: "" },
                    { id: "wall_panels", name: "Wall & Desk Panels", description: "" },
                  ],
                  system_devices: [
                    {
                      subentry_id: "sub_1",
                      title: "Living Panel",
                      kind: "device",
                      is_online: true,
                      has_display: true,
                      is_roaming: false,
                      has_assigned_area: true,
                      area_id: "living",
                      area_label: "Living Area",
                      active_area_name: "Living Area",
                      device_group: "wall_panels",
                      assigned_person: "",
                      ble_tracked: false,
                      status_code: "online",
                      status_label: "Online",
                    },
                    {
                      subentry_id: "sub_2",
                      title: "Alex Pocket",
                      kind: "device",
                      is_online: true,
                      has_display: true,
                      is_roaming: true,
                      has_assigned_area: false,
                      area_id: "living",
                      area_label: "Roaming",
                      active_area_name: "Living Area",
                      device_group: "pocket_carry",
                      assigned_person: "person.alex",
                      ble_tracked: true,
                      status_code: "online",
                      status_label: "Online",
                    },
                  ],
                  live: {
                    area_presence_grid: [
                      { area_id: "living", area_name: "Living Area", floor_name: "Main Floor", is_occupied: true, occupant_names: ["Alex"], active_sensors: ["binary_sensor.living_mmwave"], fusion_sensors: ["binary_sensor.living_mmwave"] },
                      { area_id: "study", area_name: "Study", is_occupied: false, occupant_names: [], active_sensors: [], fusion_sensors: [] },
                    ],
                  },
                  ble_area_signatures: [
                    { area_id: "living", area_name: "Living Area", has_ble_proxy: true, has_signature: true, scanner_count: 3, sample_count: 15, captured_at: "" },
                    { area_id: "study", area_name: "Study", has_ble_proxy: false, has_signature: false, scanner_count: 0, sample_count: 0, captured_at: "" },
                  ],
                  system_config: {
                    weather_entity: "weather.home",
                    alarm_entity: "alarm_control_panel.home",
                    thermostat_entities: ["climate.main", "climate.upstairs"],
                    lock_entities: ["lock.front"],
                    garage_entities: [],
                    vacuum_entities: ["vacuum.robo"],
                    camera_entities: ["camera.front_door", "camera.patio"],
                    calendar_entities: ["calendar.family"],
                    remotes_list: ["remote.living_tv"],
                    remote_groups: [{ id: "rg_living", name: "Living TV", area_id: "living", remotes: ["remote.living_tv"] }],
                    volume_overrides: [{ speaker: "media_player.living", target: "media_player.avr" }],
                    custom_palettes: [{ name: "Ocean", hex: "#009ac7" }],
                    doorbell_noise_reduction: "strong",
                  },
                  system_wallpapers: [
                    { id: "preset:forest_mountains", name: "Forest Mountains", kind: "preset" },
                    { id: "upload:1", name: "Custom Photo", kind: "upload", deletable: true },
                  ],
                },
              }).store;
            }
            process.stdout.write(JSON.stringify({
              healthyHtml: renderToHtml(renderSystemOverviewView(build(false))),
              alertsHtml: renderToHtml(renderSystemOverviewView(build(true))),
            }));
            """
        )
        healthy = re.sub(r"\s+", " ", got["healthyHtml"])
        alerts = re.sub(r"\s+", " ", got["alertsHtml"])

        self.assertNotIn("sys-issues-banner", healthy)
        self.assertNotIn("card-system-capabilities", healthy)
        self.assertNotIn("System capabilities", healthy)
        for expected in (
            "All online",
            "2 / 2 online",
            "1 occupied",
            "2 Areas • 5 BLE proxies",
            "1 person assigned",
            "Area deployment",
            "Living Area",
            "Living Panel",
        ):
            self.assertIn(expected, healthy)

        for expected_alert in (
            "sys-issues-banner",
            'role="region"',
            "Kitchen Panel",
            "sys-discovered-banner",
            "Hardware ready to adopt",
            "Office Dock",
        ):
            self.assertIn(expected_alert, alerts)
