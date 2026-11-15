// AUTO-GENERATED FROM protocol/latter_v3.json BY tools/gen_protocol.py — DO NOT EDIT MANUALLY.

export const PROTOCOL_CONTRACT_VERSION = 3;

export const POWER_PROFILE_SUBKEYS = [
  "wake_word_mode",
  "tap_to_wake",
  "pickup_to_wake",
  "battery_screen_timeout",
  "docked_idle_timeout",
  "battery_hibernate_timeout",
  "docked_screensaver",
] as const;

export type PowerProfileSubkey = (typeof POWER_PROFILE_SUBKEYS)[number];

export interface PowerProfileSettings {
  wake_word_mode: string;
  tap_to_wake: string;
  pickup_to_wake: string;
  battery_screen_timeout: string;
  docked_idle_timeout: string;
  battery_hibernate_timeout: string;
  docked_screensaver: boolean;
}

export const POWER_PROFILE_PREFS: Record<string, PowerProfileSettings> = {
  "Portable Carry": {
    wake_word_mode: "Docked Only",
    tap_to_wake: "Docked Only",
    pickup_to_wake: "Docked Only",
    battery_screen_timeout: "30s",
    docked_idle_timeout: "1 min",
    battery_hibernate_timeout: "15 min",
    docked_screensaver: true,
  },
  "Handheld Roaming": {
    wake_word_mode: "Docked Only",
    tap_to_wake: "Always On",
    pickup_to_wake: "Always On",
    battery_screen_timeout: "30s",
    docked_idle_timeout: "1 min",
    battery_hibernate_timeout: "30 min",
    docked_screensaver: true,
  },
  "Wearable Watch": {
    wake_word_mode: "Docked Only",
    tap_to_wake: "Always On",
    pickup_to_wake: "Always On",
    battery_screen_timeout: "15s",
    docked_idle_timeout: "1 min",
    battery_hibernate_timeout: "15 min",
    docked_screensaver: true,
  },
  "Tabletop Dock": {
    wake_word_mode: "Docked Only",
    tap_to_wake: "Docked Only",
    pickup_to_wake: "Disabled",
    battery_screen_timeout: "30s",
    docked_idle_timeout: "5 min",
    battery_hibernate_timeout: "15 min",
    docked_screensaver: true,
  },
  "Always-On Wall / Desk": {
    wake_word_mode: "Always On",
    tap_to_wake: "Always On",
    pickup_to_wake: "Disabled",
    battery_screen_timeout: "Never",
    docked_idle_timeout: "5 min",
    battery_hibernate_timeout: "Disabled",
    docked_screensaver: true,
  },
};

export interface CatalogItem {
  token: string;
  label: string;
}

export const DOCK_APPS_CATALOG: ReadonlyArray<CatalogItem> = [
  {token: "music", label: "Music"},
  {token: "home_hub", label: "Home Hub"},
  {token: "area", label: "Area"},
  {token: "remote", label: "Remote"},
  {token: "weather", label: "Weather"},
  {token: "time", label: "Time"},
  {token: "camera", label: "Cameras"},
  {token: "games", label: "Games"},
  {token: "tools", label: "Tools"},
];

export const ACTIVITY_SOURCES_CATALOG: ReadonlyArray<CatalogItem> = [
  {token: "calendar", label: "Calendar"},
  {token: "music_queue", label: "Music Queue"},
  {token: "stopwatch", label: "Stopwatch"},
  {token: "alarms", label: "Alarms"},
  {token: "timers", label: "Timers"},
];

export const AREA_CATEGORIES_CATALOG: ReadonlyArray<CatalogItem> = [
  {token: "scene", label: "Scenes"},
  {token: "light", label: "Lights"},
  {token: "cover", label: "Blinds & Curtains"},
  {token: "fan", label: "Fans"},
  {token: "switch", label: "Switches"},
  {token: "climate", label: "Climate"},
  {token: "media", label: "Media"},
  {token: "all", label: "All Devices"},
];

export const HOME_CATEGORIES_CATALOG: ReadonlyArray<CatalogItem> = [
  {token: "alarm", label: "Security Alarm"},
  {token: "thermostat", label: "Thermostat"},
  {token: "entry", label: "Entry & Garage"},
  {token: "vacuum", label: "Robot Vacuum"},
];

export const DEFAULT_DOCK_APPS = "music,home_hub,area,remote,games,tools";
export const DEFAULT_DOCK_APPS_TOKENS: ReadonlyArray<string> = [
  "music",
  "home_hub",
  "area",
  "remote",
  "games",
  "tools",
];

export const DEFAULT_ACTIVITY_CARD = "1";
export const DEFAULT_ACTIVITY_CARD_TOKENS: ReadonlyArray<string> = [
  "1",
];

export const DEFAULT_ACTIVITY_SOURCES = "calendar,music_queue,stopwatch,alarms,timers";
export const DEFAULT_ACTIVITY_SOURCES_TOKENS: ReadonlyArray<string> = [
  "calendar",
  "music_queue",
  "stopwatch",
  "alarms",
  "timers",
];

export const DEFAULT_AREA_CATEGORIES = "scene,light,cover,fan,switch,climate,media";
export const DEFAULT_AREA_CATEGORIES_TOKENS: ReadonlyArray<string> = [
  "scene",
  "light",
  "cover",
  "fan",
  "switch",
  "climate",
  "media",
];

export const DEFAULT_HOME_CATEGORIES = "alarm,thermostat,entry,vacuum";
export const DEFAULT_HOME_CATEGORIES_TOKENS: ReadonlyArray<string> = [
  "alarm",
  "thermostat",
  "entry",
  "vacuum",
];
