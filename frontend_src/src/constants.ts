/**
 * Canonical constants, route maps, and acronym dictionaries for Latter Studio (`D-061`, `D-063`).
 * Re-exports single-source-of-truth catalogs & contract constants from `protocol-schema.ts`.
 */

import type { StudioTranslationKey } from "./i18n/index.js";
import {
  ACTIVITY_SOURCES_CATALOG,
  ALLOWED_DEVICE_ACTIONS,
  AREA_CATEGORIES_CATALOG,
  type CatalogItem,
  DEFAULT_ACTIVITY_SOURCES,
  DEFAULT_ACTIVITY_SOURCES_TOKENS,
  DEFAULT_AREA_CATEGORIES,
  DEFAULT_AREA_CATEGORIES_TOKENS,
  DEFAULT_DOCK_ROUTES,
  DEFAULT_DOCK_ROUTES_TOKENS,
  DEFAULT_GAMES_ITEMS,
  DEFAULT_GAMES_ITEMS_TOKENS,
  DEFAULT_HOME_CATEGORIES,
  DEFAULT_HOME_CATEGORIES_TOKENS,
  DEFAULT_TOOLS_ITEMS,
  DEFAULT_TOOLS_ITEMS_TOKENS,
  DEVICE_PREF_SPECS_CATALOG,
  DEVICE_PREF_SPECS_MAP,
  type DevicePrefSpecItem,
  DEVICE_WS_COMMANDS,
  GAMES_ITEMS_CATALOG,
  HOME_CATEGORIES_CATALOG,
  SHORTCUT_ROUTES_CATALOG,
  STUDIO_REV,
  SYSTEM_WS_COMMANDS,
  TOOLS_ITEMS_CATALOG,
  WORLD_CLOCK_ZONES_CATALOG,
  type WorldClockZoneItem,
} from "./protocol-schema.js";
import type {
  ConfigurableAppId,
  DeviceViewId,
  SecurityPinPolicy,
  StudioViewId,
  SystemViewId,
} from "./types.js";

export {
  ACTIVITY_SOURCES_CATALOG,
  ALLOWED_DEVICE_ACTIONS,
  AREA_CATEGORIES_CATALOG,
  type CatalogItem,
  DEFAULT_ACTIVITY_SOURCES,
  DEFAULT_ACTIVITY_SOURCES_TOKENS,
  DEFAULT_AREA_CATEGORIES,
  DEFAULT_AREA_CATEGORIES_TOKENS,
  DEFAULT_DOCK_ROUTES,
  DEFAULT_DOCK_ROUTES_TOKENS,
  DEFAULT_GAMES_ITEMS,
  DEFAULT_GAMES_ITEMS_TOKENS,
  DEFAULT_HOME_CATEGORIES,
  DEFAULT_HOME_CATEGORIES_TOKENS,
  DEFAULT_TOOLS_ITEMS,
  DEFAULT_TOOLS_ITEMS_TOKENS,
  DEVICE_PREF_SPECS_CATALOG,
  DEVICE_PREF_SPECS_MAP,
  type DevicePrefSpecItem,
  DEVICE_WS_COMMANDS,
  GAMES_ITEMS_CATALOG,
  HOME_CATEGORIES_CATALOG,
  SHORTCUT_ROUTES_CATALOG,
  STUDIO_REV,
  SYSTEM_WS_COMMANDS,
  TOOLS_ITEMS_CATALOG,
  WORLD_CLOCK_ZONES_CATALOG,
  type WorldClockZoneItem,
};

export const MAX_DOCK_ITEMS = 24;
export const MAX_PINNED_ITEMS = 96;
export const SHORTCUT_LABEL_MAX = 24;

export const NATIVE_DOCK_APP_TOKENS: ReadonlyArray<string> = [
  "app:pinned",
  "app:music",
  "app:home_hub",
  "app:cameras",
  "app:area",
  "app:remote",
  "app:weather",
  "app:time",
  "app:calendar",
  "app:clock",
  "app:tools",
  "app:games",
];

export const NATIVE_DOCK_CONFIG_APP_MAP: Readonly<Partial<Record<string, ConfigurableAppId>>> = {
  "app:pinned": "pinned",
  "app:music": "music",
  "app:home_hub": "home_hub",
  "app:cameras": "cameras",
  "app:area": "area",
  "app:remote": "remote",
  "app:weather": "weather",
  "app:time": "time",
  "app:calendar": "calendar",
  "app:clock": "clock",
  "app:tools": "tools",
  "app:games": "games",
};

export const START_SCREEN_CONFIG_APP_MAP: Readonly<Partial<Record<string, ConfigurableAppId>>> = {
  Pinned: "pinned",
  Media: "music",
  "Home Hub": "home_hub",
  Cameras: "cameras",
  "Area Controls": "area",
  Remote: "remote",
  Weather: "weather",
  "Time App": "time",
  Calendar: "calendar",
  "Clock Face": "clock",
  Tools: "tools",
  Games: "games",
};

export const MAX_WALLPAPER_UPLOAD_BYTES = 15 * 1024 * 1024;
export const PHOTO_LIBRARY_PAGE_SIZE = 36;

export const VIRTUAL_COLLECTION_ALL = "__all__";
export const VIRTUAL_COLLECTION_DEFAULTS = "__defaults__";
export const VIRTUAL_COLLECTION_UPLOADS = "__uploads__";
export const VIRTUAL_COLLECTION_UNCATEGORIZED = "__uncategorized__";

export const DEVICE_VIEW_SLUGS: Readonly<
  Record<Exclude<DeviceViewId, "select_device_prompt" | "discovered_devices">, string>
> = {
  dashboard: "overview",
  display: "display",
  interface: "interface",
  audio_voice: "audio",
  power: "power",
  presence: "presence",
  tools: "tools",
};

export const SYSTEM_VIEW_SLUGS: Readonly<Record<SystemViewId, string>> = {
  system_overview: "overview",
  shared_entities: "shared",
  photos: "photos",
  remotes: "remotes",
  system_sync: "groups",
  area_tracking: "presence",
  system_tools: "tools",
};

export const VIEW_TITLE_KEYS: Readonly<Record<StudioViewId, StudioTranslationKey>> = {
  system_overview: "view.system_overview",
  shared_entities: "view.shared_entities",
  photos: "view.photos",
  remotes: "view.remotes",
  system_sync: "view.system_sync",
  area_tracking: "view.area_tracking",
  system_tools: "view.system_tools",
  select_device_prompt: "view.select_device_prompt",
  discovered_devices: "view.discovered_devices",
  dashboard: "view.dashboard",
  display: "view.display",
  interface: "view.interface",
  audio_voice: "view.audio_voice",
  power: "view.power",
  presence: "view.presence",
  tools: "view.tools",
};

export const START_SCREEN_OPTIONS: ReadonlyArray<string> =
  DEVICE_PREF_SPECS_MAP.start_screen?.options ?? [];

export const HOME_CLOCK_TAP_OPTIONS: ReadonlyArray<string> =
  DEVICE_PREF_SPECS_MAP.home_clock_tap_action?.options ?? [];

export const HOME_DATE_TAP_OPTIONS: ReadonlyArray<string> =
  DEVICE_PREF_SPECS_MAP.home_date_tap_action?.options ?? [];

export const CALENDAR_LOOKAHEAD_OPTIONS: ReadonlyArray<{ value: number; label: string }> = [
  { value: 7, label: "7 days" },
  { value: 14, label: "14 days" },
  { value: 30, label: "30 days" },
  { value: 60, label: "60 days" },
];

export const CALENDAR_WEEK_START_OPTIONS: ReadonlyArray<string> =
  DEVICE_PREF_SPECS_MAP.calendar_week_start?.options ?? [];

export const MAX_WORLD_CLOCKS = 4;
export const DEFAULT_ALARMS_SUMMARY = "07:00|0|1;08:30|0|2;09:00|0|2";

export const RETURN_TO_HOME_TIMEOUT_OPTIONS: ReadonlyArray<string> =
  DEVICE_PREF_SPECS_MAP.return_to_home_timeout?.options ?? [];

export const SECURITY_PIN_POLICY_OPTIONS: ReadonlyArray<{ value: SecurityPinPolicy; label: string }> = [
  { value: "auto", label: "Auto (recommended)" },
  { value: "allow", label: "Allow without PIN" },
  { value: "require_pin", label: "Require PIN" },
  { value: "block", label: "Block unlock & disarm" },
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
  "pocket_carry",
  "handhelds",
  "wearables",
  "wall_panels",
]);

export const GROUP_BEHAVIOR_NON_PREF_KEYS: ReadonlyArray<string> = [
  "native_ble_tracking",
  "ble_auto_switch",
  "sync_device_area",
  "area_follow_dwell_s",
  "area_handoff",
  "security_pin_policy",
];

export const GROUP_DISPLAY_NON_PREF_KEYS: ReadonlyArray<string> = [
  "wallpaper_mode",
  "wallpaper_source",
  "wallpaper_collection",
  "wallpaper_favorites",
  "wallpaper_cycle_minutes",
  "screensaver_photo_mode",
  "screensaver_photo_source",
  "screensaver_photo_collection",
  "screensaver_photo_ids",
  "screensaver_cycle_minutes",
  "screensaver_shuffle",
  "device_custom_color",
];

export const GROUP_INTERFACE_NON_PREF_KEYS: ReadonlyArray<string> = [
  "dock_items",
  "pinned_items",
  "area_categories",
  "home_categories",
  "tools_items",
  "games_items",
  "activity_card",
  "activity_sources",
  "device_remote_group",
  "camera_visible_entities",
  "camera_carousel_entities",
];

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
  mjpeg: "MJPEG",
  ota: "OTA",
  pin: "PIN",
  pmu: "PMU",
  psram: "PSRAM",
  ram: "RAM",
  rgb: "RGB",
  rssi: "RSSI",
  rtsp: "RTSP",
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
