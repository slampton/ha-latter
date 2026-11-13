/**
 * Canonical constants, route maps, issue messages, and Title Case dictionaries for Latter Studio.
 */

import type { DeviceViewId, IssueItem, SecurityPinPolicy, StudioViewId, SystemViewId } from "./types.js";

export const STUDIO_REV = 7;

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

// Canonical 7 Dock App tokens (`protocol.py` DOCK_APP_TOKENS).
export const DOCK_APPS_CATALOG = [
  {token: "music", label: "Music"},
  {token: "alarm", label: "Home Hub"},
  {token: "area", label: "Area"},
  {token: "remote", label: "Remote"},
  {token: "camera", label: "Cameras"},
  {token: "games", label: "Games"},
  {token: "tools", label: "Tools"},
];

// Canonical 8 Area Category tokens (`protocol.py` AREA_CATEGORY_TOKENS).
export const AREA_CATEGORIES_CATALOG: ReadonlyArray<{ token: string; label: string }> = [
  { token: "scene", label: "Scenes" },
  { token: "light", label: "Lights" },
  { token: "cover", label: "Blinds & Curtains" },
  { token: "fan", label: "Fans" },
  { token: "switch", label: "Switches" },
  { token: "climate", label: "Climate" },
  { token: "media", label: "Media" },
  { token: "all", label: "All Devices" },
];

export const DEFAULT_AREA_CATEGORIES_TOKENS: ReadonlyArray<string> = [
  "scene",
  "light",
  "cover",
  "fan",
  "switch",
  "climate",
  "media",
];

// Canonical 5 Activity Card source keys (`protocol.py` ACTIVITY_SOURCE_KEYS).
export const ACTIVITY_SOURCES_CATALOG: ReadonlyArray<{ id: string; label: string }> = [
  { id: "calendar", label: "Calendar" },
  { id: "music_queue", label: "Music Queue" },
  { id: "stopwatch", label: "Stopwatch" },
  { id: "alarms", label: "Alarms" },
  { id: "timers", label: "Timers" },
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
