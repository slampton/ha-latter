/**
 * `STUDIO_REV = 52` `StudioStatePayload` Builder for Playwright E2E.
 *
 * Separated from `studio-fixtures.ts` to keep fixture definitions and payload assembly modular.
 */

import {
  DEVICE_PREF_SPECS_CATALOG,
  WORLD_CLOCK_ZONES_CATALOG,
} from "../src/protocol-schema.js";
import type {
  SharedControlItem,
  StudioStatePayload,
} from "../src/types.js";
import {
  buildDevicePrefsForRecord,
  type MockDeviceRecord,
  type MockHubState,
} from "./studio-fixtures.js";

function buildSystemControls(hub: MockHubState): SharedControlItem[] {
  const hwDevices = hub.deviceOrder
    .map((id) => hub.devices[id])
    .filter((d): d is MockDeviceRecord => Boolean(d && d.entry.kind !== "ble_tag"));

  const makeTargets = (prefKey: string) =>
    hwDevices.map((d) => {
      const raw = d.config[prefKey];
      const state = typeof raw === "boolean" ? (raw ? "on" : "off") : String(raw ?? "");
      return {
        subentry_id: d.entry.subentry_id,
        device_slug: d.entry.device_slug,
        device_group: d.entry.device_group,
        is_online: d.entry.is_online,
        is_roaming: d.entry.is_roaming,
        pref_key: prefKey,
        state,
      };
    });

  return [
    {
      key: "power:switch:do_not_disturb",
      pref_key: "do_not_disturb",
      tier: "behavior",
      section: "power",
      section_title: "Power",
      name: "Do not disturb",
      domain: "switch",
      state: "off",
      targets: makeTargets("do_not_disturb"),
    },
    {
      key: "voice:select:wake_word_mode",
      pref_key: "wake_word_mode",
      tier: "behavior",
      section: "audio",
      section_title: "Audio",
      name: "Wake word mode",
      domain: "select",
      options: ["Always On", "Docked Only", "Disabled"],
      targets: makeTargets("wake_word_mode"),
    },
    {
      key: "display:select:auto_brightness_mode",
      pref_key: "auto_brightness_mode",
      tier: "behavior",
      section: "display",
      section_title: "Display",
      name: "Auto brightness mode",
      domain: "select",
      options: ["Disabled", "Sun Synchronized", "Time Schedule", "Ambient Light"],
      targets: makeTargets("auto_brightness_mode"),
    },
    {
      key: "display:select:glass_style",
      pref_key: "glass_style",
      tier: "display",
      section: "display",
      section_title: "Display",
      name: "Glass Style",
      domain: "select",
      options: ["Auto", "Clear", "Dark"],
      targets: makeTargets("glass_style"),
    },
    {
      key: "interface:pills:area_categories",
      pref_key: "area_categories",
      tier: "interface",
      section: "interface",
      section_title: "Interface",
      name: "Area control categories",
      domain: "pills",
      min: 1,
      options: ["scene", "light", "cover", "climate", "media", "all"],
      option_labels: {
        scene: "Scenes",
        light: "Lights",
        cover: "Shades",
        climate: "Climate",
        media: "Media",
        all: "All entities",
      },
      targets: makeTargets("area_categories"),
    },
  ];
}

export function buildPayloadFromHub(
  hub: MockHubState,
  requestedSubentryId?: string | null,
  includeLogs = false,
): StudioStatePayload {
  const activeId =
    requestedSubentryId && hub.devices[requestedSubentryId]
      ? requestedSubentryId
      : hub.deviceOrder[0] || "sub_desk";
  const rec = hub.devices[activeId]!;
  const systemDevices = hub.deviceOrder
    .map((id) => hub.devices[id])
    .filter((d): d is MockDeviceRecord => Boolean(d))
    .map((d) => ({
      ...structuredClone(d.entry),
      is_current: d.entry.subentry_id === activeId,
    }));

  return {
    type: "state",
    subentry_id: activeId,
    title: rec.entry.title,
    version: "3.0.0",
    studio_rev: hub.studioRev,
    system_config_rev: hub.systemConfigRev,
    device_config_rev: rec.deviceConfigRev,
    system_info: {
      ha_version: "2026.11.2",
      integration_version: "3.0.0",
      min_firmware_core_rev: 2026112402,
      studio_rev: hub.studioRev,
    },
    internal_logs: includeLogs
      ? [
          {
            timestamp: "2026-11-21T19:00:00Z",
            level: "INFO",
            source: "coordinator",
            message: "Synchronized Protocol v3 payload for desk_assistant",
          },
        ]
      : [],
    system_devices: systemDevices,
    issues: structuredClone(hub.issues),
    ble_proxy_count: 2,
    ble_area_signatures: structuredClone(hub.bleSignatures),
    discovered_latter_devices: structuredClone(hub.discoveredLatter),
    ignored_latter_devices: structuredClone(hub.ignoredLatter),
    discovered_ble_devices: [
      {
        target_address: "FE:ED:00:11:22:33",
        title: "Backpack Beacon",
        kind: "iBeacon",
        is_tracker: true,
        rssi: -64,
        area_name: "Entryway",
      },
    ],
    system_controls: buildSystemControls(hub),
    device_groups: structuredClone(hub.deviceGroups),
    system_config: structuredClone(hub.systemConfig),
    has_security_pin: hub.hasSecurityPin,
    photo_collections: structuredClone(hub.collections),
    system_wallpapers: structuredClone(hub.photos),
    catalog: {
      areas: [
        { id: "harbor_studio", name: "Harbor Studio" },
        { id: "kitchen", name: "Kitchen" },
        { id: "entryway", name: "Entryway" },
      ],
      persons: [
        { id: "person.alex", name: "Alex" },
        { id: "person.sam", name: "Sam" },
      ],
      ma_speakers: [
        { id: "media_player.kitchen_speaker", name: "Kitchen Speaker", area_name: "Kitchen" },
        { id: "media_player.studio_monitors", name: "Studio Monitors", area_name: "Harbor Studio" },
        { id: "media_player.patio_horn", name: "Patio Speaker", area_name: "Patio" },
      ],
      ma_players: [
        { id: "media_player.desk_assistant_ma", name: "Desk Assistant MA", area_name: "Harbor Studio" },
      ],
      remotes: [{ id: "remote.studio_display", name: "Studio Display", area_name: "Harbor Studio" }],
      volume_targets: [{ id: "media_player.studio_avr", name: "Studio AVR", area_name: "Harbor Studio" }],
      alarms: [{ id: "alarm_control_panel.perimeter", name: "Perimeter Alarm" }],
      cameras: [
        {
          id: "camera.front_entry",
          name: "Front Entry",
          area_name: "Entryway",
          stream_kind: "rtsp",
          has_audio: true,
          has_talkback: true,
          is_doorbell: true,
        },
        {
          id: "camera.courtyard",
          name: "Courtyard Wide Channel",
          area_name: "Entryway",
          stream_kind: "mjpeg",
          has_audio: true,
          is_doorbell: false,
        },
        {
          id: "camera.workshop",
          name: "Workshop Bench",
          area_name: "Harbor Studio",
          stream_kind: "snapshot",
        },
      ],
      climates: [{ id: "climate.main_zone", name: "Main Zone", area_name: "Harbor Studio" }],
      locks: [{ id: "lock.front_entry", name: "Front Entry Lock", area_name: "Entryway" }],
      garages: [{ id: "cover.main_garage", name: "Main Garage", area_name: "Entryway" }],
      vacuums: [{ id: "vacuum.studio_bot", name: "Studio Bot", area_name: "Harbor Studio" }],
      weathers: [{ id: "weather.harbor", name: "Harbor Weather" }],
      calendars: [{ id: "calendar.team_schedule", name: "Team Schedule" }],
      shortcut_entities: [
        {
          id: "light.kitchen_island",
          name: "Kitchen Island",
          domain: "light",
          device_class: "",
          icon: "mdi:ceiling-light",
          area_name: "Kitchen",
        },
        {
          id: "light.kitchen_pendant",
          name: "Kitchen Island Pendant",
          domain: "light",
          device_class: "",
          icon: "mdi:lamp",
          area_name: "Kitchen",
        },
        {
          id: "scene.evening_focus",
          name: "Evening Focus",
          domain: "scene",
          device_class: "",
          icon: "mdi:shimmer",
          area_name: "Harbor Studio",
        },
        {
          id: "lock.front_entry",
          name: "Front Entry Lock",
          domain: "lock",
          device_class: "",
          icon: "mdi:lock",
          area_name: "Entryway",
        },
      ],
    },
    pref_specs: [...DEVICE_PREF_SPECS_CATALOG],
    world_clock_zones: [...WORLD_CLOCK_ZONES_CATALOG],
    capabilities: structuredClone(rec.capabilities),
    config: structuredClone(rec.config),
    device_prefs: buildDevicePrefsForRecord(rec),
    quick_actions:
      rec.entry.kind === "ble_tag"
        ? []
        : [
            {
              key: "find_my",
              device_command: "find_my",
              label: "Find my Device",
              domain: "button",
              state: rec.entry.is_online ? "2026-11-21T18:00:00Z" : "unavailable",
            },
            {
              key: "trigger_va",
              device_command: "trigger_va",
              label: "Trigger voice assistant",
              domain: "button",
              state: rec.entry.is_online ? "unknown" : "unavailable",
            },
            {
              key: "activate_screensaver",
              device_command: "activate_screensaver",
              label: "Activate screensaver",
              domain: "button",
              state: rec.entry.is_online ? "unknown" : "unavailable",
            },
            {
              key: "restart",
              device_command: "restart",
              label: "Restart Device",
              domain: "button",
              state: rec.entry.is_online ? "unknown" : "unavailable",
              device_class: "restart",
            },
          ],
    speaker_volume:
      rec.entry.kind === "ble_tag"
        ? null
        : {
            entity_id: `number.${rec.entry.device_slug}_speaker_volume`,
            domain: "number",
            name: "Speaker volume",
            state: rec.entry.is_online ? "65" : "unavailable",
            min: 0,
            max: 100,
            step: 5,
            unit: "%",
          },
    esphome: {
      device: {
        id: `esp_${rec.nodeName}`,
        name: rec.entry.title,
        node_name: rec.nodeName,
        model: rec.entry.model_label,
        sw_version: rec.swVersion,
        mac: rec.mac,
      },
      sections:
        rec.entry.kind === "ble_tag"
          ? []
          : [
              {
                id: "network",
                title: "Network",
                items: [
                  {
                    entity_id: `update.${rec.nodeName}_firmware`,
                    domain: "update",
                    name: "Firmware",
                    state: "off",
                  },
                ],
              },
              {
                id: "voice",
                title: "Voice",
                items: [
                  {
                    entity_id: `select.${rec.nodeName}_wake_word`,
                    domain: "select",
                    key: "wake_word",
                    name: "Wake word",
                    state: "Okay Nabu",
                    options: ["Okay Nabu", "Hey Jarvis"],
                  },
                ],
              },
            ],
    },
    wallpapers: structuredClone(hub.photos),
    links: {
      entry_id: "entry_latter_hub",
      esphome_device_id: `esp_${rec.nodeName}`,
      latter_device_id: `latter_${rec.nodeName}`,
    },
    live: {
      ...structuredClone(rec.live),
      area_presence_grid: structuredClone(hub.areaPresence),
    },
  };
}
