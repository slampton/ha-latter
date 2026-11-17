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
  "Pocket Carry": {
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
    tap_to_wake: "Single Tap",
    pickup_to_wake: "Always On",
    battery_screen_timeout: "30s",
    docked_idle_timeout: "1 min",
    battery_hibernate_timeout: "30 min",
    docked_screensaver: true,
  },
  "Wearable Watch": {
    wake_word_mode: "Docked Only",
    tap_to_wake: "Double Tap",
    pickup_to_wake: "Always On",
    battery_screen_timeout: "15s",
    docked_idle_timeout: "1 min",
    battery_hibernate_timeout: "15 min",
    docked_screensaver: true,
  },
  "Always-On Wall / Desk": {
    wake_word_mode: "Always On",
    tap_to_wake: "Single Tap",
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
  group?: string;
  dockOnly?: boolean;
  capability?: string;
}

export const SHORTCUT_ROUTES_CATALOG: ReadonlyArray<CatalogItem> = [
  {token: "app:pinned", label: "Pinned", group: "Apps", dockOnly: true},
  {token: "app:music", label: "Music", group: "Apps"},
  {token: "app:home_hub", label: "Home Hub", group: "Apps"},
  {token: "app:area", label: "Area Control", group: "Apps"},
  {token: "app:remote", label: "Remote", group: "Apps"},
  {token: "app:weather", label: "Sky & Weather", group: "Apps"},
  {token: "app:time", label: "Time", group: "Apps"},
  {token: "app:tools", label: "Tools", group: "Apps"},
  {token: "app:games", label: "Games", group: "Apps"},
  {token: "app:clock", label: "Clock Face", group: "Apps"},
  {token: "home_hub:alarm", label: "Security Alarm", group: "Home Hub"},
  {token: "home_hub:cameras", label: "Cameras", group: "Home Hub"},
  {token: "home_hub:intercom", label: "Intercom", group: "Home Hub"},
  {token: "home_hub:thermostat", label: "Thermostat", group: "Home Hub"},
  {token: "home_hub:entry", label: "Entry & Garage", group: "Home Hub"},
  {token: "home_hub:vacuum", label: "Robot Vacuum", group: "Home Hub"},
  {token: "area:picker", label: "Switch Area", group: "Area Control"},
  {token: "area:scene", label: "Area: Scenes", group: "Area Control"},
  {token: "area:light", label: "Area: Lights", group: "Area Control"},
  {token: "area:cover", label: "Area: Blinds & Curtains", group: "Area Control"},
  {token: "area:fan", label: "Area: Fans", group: "Area Control"},
  {token: "area:switch", label: "Area: Switches", group: "Area Control"},
  {token: "area:climate", label: "Area: Climate", group: "Area Control"},
  {token: "area:media", label: "Area: Media", group: "Area Control"},
  {token: "area:all", label: "Area: All Devices", group: "Area Control"},
  {token: "weather:current", label: "Current Weather", group: "Sky & Weather"},
  {token: "weather:forecast", label: "5-Day Forecast", group: "Sky & Weather"},
  {token: "weather:sun", label: "Sun Path", group: "Sky & Weather"},
  {token: "weather:moon", label: "Moon Phase", group: "Sky & Weather"},
  {token: "time:clock", label: "World Clocks", group: "Time"},
  {token: "time:timers", label: "Timers", group: "Time"},
  {token: "time:alarms", label: "Alarms", group: "Time"},
  {token: "time:stopwatch", label: "Stopwatch", group: "Time"},
  {token: "music:speakers", label: "Speakers", group: "Music"},
  {token: "music:library", label: "Music Library", group: "Music"},
  {token: "music:favorites", label: "Favorites", group: "Music"},
  {token: "music:playlists", label: "Playlists", group: "Music"},
  {token: "music:queue", label: "Playback Queue", group: "Music"},
  {token: "remote:devices", label: "Remote Devices", group: "Remote"},
  {token: "tools:stopwatch", label: "Analog Chronograph", group: "Tools", capability: "round"},
  {token: "tools:level", label: "Bubble Level", group: "Tools", capability: "imu"},
  {token: "tools:flashlight", label: "Flashlight", group: "Tools"},
  {token: "tools:calculator", label: "Calculator", group: "Tools"},
  {token: "tools:calendar", label: "Calendar", group: "Tools"},
  {token: "tools:dice", label: "Dice Roll", group: "Tools"},
  {token: "tools:coin_flip", label: "Coin Flip", group: "Tools"},
  {token: "games:marbles", label: "Marbles", group: "Games"},
  {token: "games:archery", label: "Archery", group: "Games"},
  {token: "games:bricks", label: "Bricks", group: "Games"},
  {token: "games:chomp", label: "Chomp", group: "Games"},
  {token: "games:2048", label: "2048", group: "Games"},
  {token: "games:memory", label: "Memory Match", group: "Games"},
  {token: "settings:display", label: "Display Settings", group: "Settings"},
  {token: "settings:sleep", label: "Sleep & Wake", group: "Settings"},
  {token: "settings:sound", label: "Sound Settings", group: "Settings"},
  {token: "settings:voice", label: "Voice Settings", group: "Settings"},
  {token: "settings:music", label: "Music Settings", group: "Settings"},
  {token: "settings:home", label: "Home Settings", group: "Settings"},
  {token: "settings:actions", label: "Device Actions", group: "Settings"},
  {token: "settings:update", label: "Software Update", group: "Settings"},
  {token: "settings:info", label: "System Info", group: "Settings"},
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
  {token: "cameras", label: "Cameras"},
  {token: "intercom", label: "Intercom"},
  {token: "thermostat", label: "Thermostat"},
  {token: "entry", label: "Entry & Garage"},
  {token: "vacuum", label: "Robot Vacuum"},
];

export const DEFAULT_DOCK_ROUTES = "app:pinned,app:music,app:home_hub,app:area,app:remote,app:games,app:tools";
export const DEFAULT_DOCK_ROUTES_TOKENS: ReadonlyArray<string> = [
  "app:pinned",
  "app:music",
  "app:home_hub",
  "app:area",
  "app:remote",
  "app:games",
  "app:tools",
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

export const DEFAULT_HOME_CATEGORIES = "alarm,cameras,intercom,thermostat,entry,vacuum";
export const DEFAULT_HOME_CATEGORIES_TOKENS: ReadonlyArray<string> = [
  "alarm",
  "cameras",
  "intercom",
  "thermostat",
  "entry",
  "vacuum",
];
