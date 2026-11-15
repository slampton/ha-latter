/**
 * Canonical constants, route maps, issue messages, and Title Case dictionaries for Latter Studio.
 */

import type { DeviceViewId, IssueItem, SecurityPinPolicy, StudioViewId, SystemViewId } from "./types.js";
import {
  POWER_PROFILE_PREFS,
  POWER_PROFILE_SUBKEYS,
  DOCK_APPS_CATALOG,
  DEFAULT_DOCK_APPS_TOKENS,
  DEFAULT_DOCK_APPS,
  AREA_CATEGORIES_CATALOG,
  DEFAULT_AREA_CATEGORIES_TOKENS,
  HOME_CATEGORIES_CATALOG,
  DEFAULT_HOME_CATEGORIES_TOKENS,
  ACTIVITY_SOURCES_CATALOG,
} from "./protocol-schema.js";

export {
  POWER_PROFILE_PREFS,
  POWER_PROFILE_SUBKEYS,
  DOCK_APPS_CATALOG,
  DEFAULT_DOCK_APPS_TOKENS,
  DEFAULT_DOCK_APPS,
  AREA_CATEGORIES_CATALOG,
  DEFAULT_AREA_CATEGORIES_TOKENS,
  HOME_CATEGORIES_CATALOG,
  DEFAULT_HOME_CATEGORIES_TOKENS,
  ACTIVITY_SOURCES_CATALOG,
};

export const STUDIO_REV = 10;

export const MAX_WALLPAPER_UPLOAD_BYTES = 15 * 1024 * 1024;

export const DEVICE_VIEW_SLUGS = {
  dashboard: "overview",
  display: "display",
  interface: "interface",
  audio_voice: "audio",
  power: "power",
  presence: "presence",
  tools: "tools",
};

export const SYSTEM_VIEW_SLUGS = {system_overview: "overview", shared_entities: "shared", remotes: "remotes", system_sync: "groups", area_tracking: "presence", system_tools: "tools"};

export const VIEW_TITLES = {
  system_overview: "Overview",
  shared_entities: "Shared Entities",
  remotes: "Media & Remotes",
  system_sync: "Device Groups",
  area_tracking: "BLE & Area Presence",
  system_tools: "Tools",
  select_device_prompt: "All Devices",
  dashboard: "Overview",
  display: "Display",
  interface: "Interface",
  audio_voice: "Audio",
  power: "Power",
  presence: "Presence",
  tools: "Tools",
};

const _typecheckViewMaps: [
  Record<Exclude<DeviceViewId, "select_device_prompt">, string>,
  Record<SystemViewId, string>,
  Record<StudioViewId, string>,
] = [DEVICE_VIEW_SLUGS, SYSTEM_VIEW_SLUGS, VIEW_TITLES];
void _typecheckViewMaps;

// Messages for Latter's Home Assistant Repairs (kind = translation key in strings.json).
export const ISSUE_TEXT: Record<string, (issue: IssueItem) => string> = {
  link_ma_player: () => "Not linked to its Music Assistant player.",
  missing_mapped_entity: (i) =>
    `A chosen entity no longer exists${i.detail ? `: ${i.detail}` : ""}.`,
  ble_no_proxies: () =>
    "BLE Area tracking is on, but no Bluetooth proxy is assigned to an Area.",
  slot_push_failing: () =>
    "Latter can't send Area and browse pages to this Device.",
  device_crashed: (i) =>
    i.detail === "stall"
      ? "Restarted itself after its main loop stalled for 30 seconds."
      : `Restarted after a crash${i.detail ? ` (${i.detail})` : ""}.`,
  device_brownout: () => "Restarted after a power dip (brownout).",
  firmware_rolled_back: () =>
    "A firmware update failed to start; the previous firmware is running.",
};

export const START_SCREEN_OPTIONS: ReadonlyArray<string> = [
  "Home",
  "Time App",
  "Clock Face",
  "Media",
  "Home Hub",
  "Area Controls",
  "Remote",
  "Weather",
  "Cameras",
  "Games",
  "Tools",
];

export const HOME_CLOCK_TAP_OPTIONS: ReadonlyArray<string> = [
  "Time App",
  "Clock Face",
];

export const MAX_WORLD_CLOCKS = 4;
export const DEFAULT_ALARMS_SUMMARY = "07:00|0|1;08:30|0|2;09:00|0|2";

export const ALARM_RECURRENCE_OPTIONS: ReadonlyArray<{ value: number; label: string }> = [
  { value: 0, label: "Daily" },
  { value: 1, label: "Weekdays" },
  { value: 2, label: "Weekends" },
  { value: 3, label: "Once" },
];

export const WORLD_CLOCK_ZONES_CATALOG: ReadonlyArray<{ iana: string; city: string; label: string }> = [
  { iana: "America/Los_Angeles", city: "Los Angeles", label: "Los Angeles (America/Los_Angeles)" },
  { iana: "America/Denver", city: "Denver", label: "Denver (America/Denver)" },
  { iana: "America/Chicago", city: "Chicago", label: "Chicago (America/Chicago)" },
  { iana: "America/New_York", city: "New York", label: "New York (America/New_York)" },
  { iana: "America/Toronto", city: "Toronto", label: "Toronto (America/Toronto)" },
  { iana: "America/Sao_Paulo", city: "Sao Paulo", label: "Sao Paulo (America/Sao_Paulo)" },
  { iana: "America/Argentina/Buenos_Aires", city: "Buenos Aires", label: "Buenos Aires (America/Argentina/Buenos_Aires)" },
  { iana: "Pacific/Honolulu", city: "Honolulu", label: "Honolulu (Pacific/Honolulu)" },
  { iana: "America/Anchorage", city: "Anchorage", label: "Anchorage (America/Anchorage)" },
  { iana: "Europe/London", city: "London", label: "London (Europe/London)" },
  { iana: "Europe/Paris", city: "Paris", label: "Paris (Europe/Paris)" },
  { iana: "Europe/Berlin", city: "Berlin", label: "Berlin (Europe/Berlin)" },
  { iana: "Europe/Zurich", city: "Zurich", label: "Zurich (Europe/Zurich)" },
  { iana: "Africa/Cairo", city: "Cairo", label: "Cairo (Africa/Cairo)" },
  { iana: "Africa/Johannesburg", city: "Johannesburg", label: "Johannesburg (Africa/Johannesburg)" },
  { iana: "Asia/Dubai", city: "Dubai", label: "Dubai (Asia/Dubai)" },
  { iana: "Asia/Kolkata", city: "Kolkata", label: "Kolkata (Asia/Kolkata)" },
  { iana: "Asia/Bangkok", city: "Bangkok", label: "Bangkok (Asia/Bangkok)" },
  { iana: "Asia/Singapore", city: "Singapore", label: "Singapore (Asia/Singapore)" },
  { iana: "Asia/Hong_Kong", city: "Hong Kong", label: "Hong Kong (Asia/Hong_Kong)" },
  { iana: "Asia/Shanghai", city: "Shanghai", label: "Shanghai (Asia/Shanghai)" },
  { iana: "Asia/Tokyo", city: "Tokyo", label: "Tokyo (Asia/Tokyo)" },
  { iana: "Asia/Seoul", city: "Seoul", label: "Seoul (Asia/Seoul)" },
  { iana: "Australia/Sydney", city: "Sydney", label: "Sydney (Australia/Sydney)" },
];

export const RETURN_TO_HOME_TIMEOUT_OPTIONS: ReadonlyArray<string> = [
  "15s",
  "30s",
  "1 min",
  "2 min",
  "5 min",
  "10 min",
  "Never",
];

export const SECURITY_PIN_POLICY_OPTIONS: ReadonlyArray<{ value: SecurityPinPolicy; label: string }> = [
  { value: "auto", label: "Auto (Recommended)" },
  { value: "allow", label: "Allow Without PIN" },
  { value: "require_pin", label: "Require PIN" },
  { value: "block", label: "Block Unlock & Disarm" },
];

export const WALLPAPER_ROTATION_OPTIONS: ReadonlyArray<{ value: number; label: string }> = [
  { value: 0, label: "Do not rotate" },
  { value: 5, label: "Every 5 minutes" },
  { value: 15, label: "Every 15 minutes" },
  { value: 30, label: "Every 30 minutes" },
  { value: 60, label: "Every hour" },
  { value: 360, label: "Every 6 hours" },
  { value: 1440, label: "Once a day" },
];

export const DEFAULT_DEVICE_GROUP_IDS = new Set([
  "unassigned",
  "handhelds",
  "wearables",
  "bedrooms",
  "common_areas",
  "wall_panels",
]);

export const LABEL_MINOR_WORDS = new Set([
  "a",
  "an",
  "the",
  "and",
  "or",
  "of",
  "to",
  "in",
  "on",
  "for",
  "with",
]);

export const LABEL_ACRONYMS: Record<string, string> = {
  ble: "BLE",
  cpu: "CPU",
  db: "dB",
  dbm: "dBm",
  dns: "DNS",
  esp: "ESP",
  esphome: "ESPHome",
  ha: "HA",
  http: "HTTP",
  id: "ID",
  imu: "IMU",
  ip: "IP",
  ips: "IPS",
  led: "LED",
  ma: "MA",
  mac: "MAC",
  mic: "Mic",
  ota: "OTA",
  pin: "PIN",
  pmu: "PMU",
  psram: "PSRAM",
  ram: "RAM",
  rgb: "RGB",
  rssi: "RSSI",
  sdk: "SDK",
  sram: "SRAM",
  ssid: "SSID",
  tts: "TTS",
  ui: "UI",
  url: "URL",
  usb: "USB",
  uuid: "UUID",
  va: "VA",
  wifi: "Wi-Fi",
  "wi-fi": "Wi-Fi",
};
