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

export const STUDIO_REV = 12;

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

export const WORLD_CLOCK_ZONES_CATALOG: ReadonlyArray<{ iana: string; label: string }> = [
  { iana: "Etc/GMT+12", label: "UTC-12:00 — International Date Line West" },
  { iana: "Pacific/Pago_Pago", label: "UTC-11:00 — Samoa Standard Time (SST)" },
  { iana: "Pacific/Honolulu", label: "UTC-10:00 — Hawaii-Aleutian Standard Time (HST)" },
  { iana: "Pacific/Marquesas", label: "UTC-09:30 — Marquesas Time (MART)" },
  { iana: "America/Anchorage", label: "UTC-09:00 — Alaska Time (AKST/AKDT)" },
  { iana: "America/Los_Angeles", label: "UTC-08:00 — Pacific Time (PST/PDT)" },
  { iana: "Etc/GMT+8", label: "UTC-08:00 — Coordinated Universal Time-08 (No DST)" },
  { iana: "America/Denver", label: "UTC-07:00 — Mountain Time (MST/MDT)" },
  { iana: "America/Phoenix", label: "UTC-07:00 — Mountain Standard Time (MST, No DST)" },
  { iana: "America/Chicago", label: "UTC-06:00 — Central Time (CST/CDT)" },
  { iana: "America/Regina", label: "UTC-06:00 — Central Standard Time (CST, No DST)" },
  { iana: "America/New_York", label: "UTC-05:00 — Eastern Time (EST/EDT)" },
  { iana: "America/Lima", label: "UTC-05:00 — Eastern Standard Time (EST, No DST)" },
  { iana: "America/Halifax", label: "UTC-04:00 — Atlantic Time (AST/ADT)" },
  { iana: "America/Puerto_Rico", label: "UTC-04:00 — Atlantic Standard Time (AST, No DST)" },
  { iana: "America/St_Johns", label: "UTC-03:30 — Newfoundland Time (NST/NDT)" },
  { iana: "America/Sao_Paulo", label: "UTC-03:00 — South America Eastern Time (BRT/ART)" },
  { iana: "Etc/GMT+2", label: "UTC-02:00 — Coordinated Universal Time-02" },
  { iana: "Atlantic/Azores", label: "UTC-01:00 — Azores Time (AZOT/AZOST)" },
  { iana: "Atlantic/Cape_Verde", label: "UTC-01:00 — Cape Verde Time (CVT, No DST)" },
  { iana: "Atlantic/Reykjavik", label: "UTC+00:00 — Greenwich Mean Time (GMT, No DST)" },
  { iana: "Europe/London", label: "UTC+00:00 — Western European Time (GMT/BST)" },
  { iana: "Europe/Berlin", label: "UTC+01:00 — Central European Time (CET/CEST)" },
  { iana: "Africa/Lagos", label: "UTC+01:00 — West Africa Time (WAT, No DST)" },
  { iana: "Europe/Athens", label: "UTC+02:00 — Eastern European Time (EET/EEST)" },
  { iana: "Africa/Johannesburg", label: "UTC+02:00 — Central / South Africa Time (CAT/SAST)" },
  { iana: "Asia/Riyadh", label: "UTC+03:00 — Arabia / East Africa Time (AST/EAT)" },
  { iana: "Asia/Tehran", label: "UTC+03:30 — Iran Standard Time (IRST)" },
  { iana: "Asia/Dubai", label: "UTC+04:00 — Gulf Standard Time (GST)" },
  { iana: "Asia/Kabul", label: "UTC+04:30 — Afghanistan Time (AFT)" },
  { iana: "Asia/Karachi", label: "UTC+05:00 — Pakistan / West Asia Time (PKT)" },
  { iana: "Asia/Kolkata", label: "UTC+05:30 — India / Sri Lanka Standard Time (IST)" },
  { iana: "Asia/Kathmandu", label: "UTC+05:45 — Nepal Time (NPT)" },
  { iana: "Asia/Dhaka", label: "UTC+06:00 — Bangladesh / Central Asia Time (BST)" },
  { iana: "Asia/Yangon", label: "UTC+06:30 — Myanmar Time (MMT)" },
  { iana: "Asia/Bangkok", label: "UTC+07:00 — Indochina Time (ICT)" },
  { iana: "Asia/Singapore", label: "UTC+08:00 — China / Singapore / AWST (CST/SGT/AWST)" },
  { iana: "Australia/Eucla", label: "UTC+08:45 — Australian Central Western Time (ACWST)" },
  { iana: "Asia/Tokyo", label: "UTC+09:00 — Japan / Korea Standard Time (JST/KST)" },
  { iana: "Australia/Adelaide", label: "UTC+09:30 — Australian Central Time (ACST/ACDT)" },
  { iana: "Australia/Darwin", label: "UTC+09:30 — Australian Central Standard Time (ACST, No DST)" },
  { iana: "Australia/Sydney", label: "UTC+10:00 — Australian Eastern Time (AEST/AEDT)" },
  { iana: "Australia/Brisbane", label: "UTC+10:00 — Australian Eastern Standard Time (AEST, No DST)" },
  { iana: "Australia/Lord_Howe", label: "UTC+10:30 — Lord Howe Time (LHST/LHDT)" },
  { iana: "Pacific/Guadalcanal", label: "UTC+11:00 — Solomon Islands / New Caledonia Time (SBT)" },
  { iana: "Pacific/Auckland", label: "UTC+12:00 — New Zealand Time (NZST/NZDT)" },
  { iana: "Etc/GMT-12", label: "UTC+12:00 — Coordinated Universal Time+12 (No DST)" },
  { iana: "Pacific/Chatham", label: "UTC+12:45 — Chatham Islands Time (CHAST/CHADT)" },
  { iana: "Pacific/Tongatapu", label: "UTC+13:00 — Tonga / Phoenix Islands Time (TOT)" },
  { iana: "Pacific/Kiritimati", label: "UTC+14:00 — Line Islands Time (LINT)" },
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
