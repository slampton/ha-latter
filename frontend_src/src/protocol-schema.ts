// AUTO-GENERATED FROM protocol/latter_v3.json BY tools/gen_protocol.py — DO NOT EDIT MANUALLY.

export const PROTOCOL_CONTRACT_VERSION = 3;
export const STUDIO_REV = 42;

export const ALLOWED_DEVICE_ACTIONS: ReadonlyArray<string> = [
  "restart",
  "find_my",
  "activate_screensaver",
  "trigger_va",
  "log_memory_report",
  "dismiss_ringing",
  "cancel_timer",
  "reset_stopwatch",
];

export const SYSTEM_WS_COMMANDS: ReadonlySet<string> = new Set([
  "set_ble_scanner_offset",
  "set_area_fusion",
  "capture_ble_area_signature",
  "clear_ble_area_signature",
  "system_entity_action",
  "send_announcement",
  "check_system_updates",
  "clear_internal_logs",
  "remove_device",
  "add_latter_device",
  "ignore_discovered_device",
  "unignore_discovered_device",
  "add_ble_device",
  "create_device_group",
  "delete_device_group",
  "update_group_baseline",
  "apply_batch_device_setting",
  "test_doorbell_speaker",
  "mint_camera_preview_url",
  "delete_photo",
  "create_photo_collection",
  "rename_photo_collection",
  "delete_photo_collection",
  "update_photo_metadata",
  "bulk_update_photos",
  "browse_media_folder",
  "import_media_photos",
  "save_system_config",
  "rotate_signing_key",
  "set_security_pin",
]);

export const DEVICE_WS_COMMANDS: ReadonlySet<string> = new Set([
  "esphome_entity_action",
  "device_action",
  "set_device_photo_pool",
  "save_device_config",
]);

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
  {token: "app:cameras", label: "Cameras", group: "Apps"},
  {token: "app:area", label: "Area Control", group: "Apps"},
  {token: "app:remote", label: "Remote", group: "Apps"},
  {token: "app:weather", label: "Sky & Weather", group: "Apps"},
  {token: "app:time", label: "Time", group: "Apps"},
  {token: "app:calendar", label: "Calendar", group: "Apps"},
  {token: "app:tools", label: "Tools", group: "Apps"},
  {token: "app:games", label: "Games", group: "Apps"},
  {token: "app:clock", label: "Clock Face", group: "Apps"},
  {token: "home_hub:alarm", label: "Security Alarm", group: "Home Hub"},
  {token: "home_hub:intercom", label: "Broadcast", group: "Home Hub"},
  {token: "home_hub:thermostat", label: "Thermostat", group: "Home Hub"},
  {token: "home_hub:entry", label: "Entry & Garage", group: "Home Hub"},
  {token: "home_hub:vacuum", label: "Robot Vacuum", group: "Home Hub"},
  {token: "cameras:grid", label: "Cameras: Grid", group: "Cameras"},
  {token: "cameras:single", label: "Cameras: Live", group: "Cameras"},
  {token: "cameras:carousel", label: "Cameras: Carousel", group: "Cameras"},
  {token: "cameras:settings", label: "Cameras: Settings", group: "Cameras"},
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
  {token: "calendar:overview", label: "Upcoming Events", group: "Calendar"},
  {token: "calendar:day", label: "Day View", group: "Calendar"},
  {token: "calendar:week", label: "Week View", group: "Calendar"},
  {token: "calendar:month", label: "Month View", group: "Calendar"},
  {token: "music:speakers", label: "Speakers", group: "Music"},
  {token: "music:library", label: "Music Library", group: "Music"},
  {token: "music:favorites", label: "Favorites", group: "Music"},
  {token: "music:playlists", label: "Playlists", group: "Music"},
  {token: "music:queue", label: "Playback Queue", group: "Music"},
  {token: "music:album_tracks", label: "Album Tracks", group: "Music"},
  {token: "music:lyrics", label: "Music Lyrics", group: "Music"},
  {token: "music:info", label: "Track Info", group: "Music"},
  {token: "remote:devices", label: "Remote Devices", group: "Remote"},
  {token: "tools:stopwatch", label: "Analog Chronograph", group: "Tools", capability: "round"},
  {token: "tools:level", label: "Bubble Level", group: "Tools", capability: "imu"},
  {token: "tools:flashlight", label: "Flashlight", group: "Tools"},
  {token: "tools:calculator", label: "Calculator", group: "Tools"},
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
  {token: "intercom", label: "Broadcast"},
  {token: "thermostat", label: "Thermostat"},
  {token: "entry", label: "Entry & Garage"},
  {token: "vacuum", label: "Robot Vacuum"},
];

export const TOOLS_ITEMS_CATALOG: ReadonlyArray<CatalogItem> = [
  {token: "stopwatch", label: "Analog Chronograph", capability: "round"},
  {token: "level", label: "Bubble Level", capability: "imu"},
  {token: "flashlight", label: "Flashlight"},
  {token: "calculator", label: "Calculator"},
  {token: "dice", label: "Dice Roll"},
  {token: "coin_flip", label: "Coin Flip"},
];

export const GAMES_ITEMS_CATALOG: ReadonlyArray<CatalogItem> = [
  {token: "marbles", label: "Marbles"},
  {token: "archery", label: "Archery"},
  {token: "bricks", label: "Bricks"},
  {token: "chomp", label: "Chomp"},
  {token: "2048", label: "2048"},
  {token: "memory", label: "Memory Match"},
];

export interface WorldClockZoneItem {
  iana: string;
  city: string;
  label: string;
  std_off: number;
  dst_off: number;
  std_abbr: string;
  dst_abbr: string;
  rule: string;
}

export const WORLD_CLOCK_ZONES_CATALOG: ReadonlyArray<WorldClockZoneItem> = [
  {iana: "Etc/GMT+12", city: "UTC-12", label: "UTC-12:00 — International Date Line West", std_off: -720, dst_off: -720, std_abbr: "UTC-12", dst_abbr: "UTC-12", rule: "none" },
  {iana: "Pacific/Pago_Pago", city: "Pago Pago", label: "UTC-11:00 — Samoa Standard Time (SST)", std_off: -660, dst_off: -660, std_abbr: "SST", dst_abbr: "SST", rule: "none" },
  {iana: "Pacific/Honolulu", city: "Honolulu", label: "UTC-10:00 — Hawaii-Aleutian Standard Time (HST)", std_off: -600, dst_off: -600, std_abbr: "HST", dst_abbr: "HST", rule: "none" },
  {iana: "Pacific/Marquesas", city: "Marquesas", label: "UTC-09:30 — Marquesas Time (MART)", std_off: -570, dst_off: -570, std_abbr: "MART", dst_abbr: "MART", rule: "none" },
  {iana: "America/Anchorage", city: "Anchorage", label: "UTC-09:00 — Alaska Time (AKST/AKDT)", std_off: -540, dst_off: -480, std_abbr: "AKST", dst_abbr: "AKDT", rule: "us" },
  {iana: "America/Los_Angeles", city: "Los Angeles", label: "UTC-08:00 — Pacific Time (PST/PDT)", std_off: -480, dst_off: -420, std_abbr: "PST", dst_abbr: "PDT", rule: "us" },
  {iana: "Etc/GMT+8", city: "UTC-8", label: "UTC-08:00 — Coordinated Universal Time-08 (No DST)", std_off: -480, dst_off: -480, std_abbr: "UTC-8", dst_abbr: "UTC-8", rule: "none" },
  {iana: "America/Denver", city: "Denver", label: "UTC-07:00 — Mountain Time (MST/MDT)", std_off: -420, dst_off: -360, std_abbr: "MST", dst_abbr: "MDT", rule: "us" },
  {iana: "America/Phoenix", city: "Phoenix", label: "UTC-07:00 — Mountain Standard Time (MST, No DST)", std_off: -420, dst_off: -420, std_abbr: "MST", dst_abbr: "MST", rule: "none" },
  {iana: "America/Chicago", city: "Chicago", label: "UTC-06:00 — Central Time (CST/CDT)", std_off: -360, dst_off: -300, std_abbr: "CST", dst_abbr: "CDT", rule: "us" },
  {iana: "America/Regina", city: "Regina", label: "UTC-06:00 — Central Standard Time (CST, No DST)", std_off: -360, dst_off: -360, std_abbr: "CST", dst_abbr: "CST", rule: "none" },
  {iana: "America/New_York", city: "New York", label: "UTC-05:00 — Eastern Time (EST/EDT)", std_off: -300, dst_off: -240, std_abbr: "EST", dst_abbr: "EDT", rule: "us" },
  {iana: "America/Lima", city: "Lima", label: "UTC-05:00 — Eastern Standard Time (EST, No DST)", std_off: -300, dst_off: -300, std_abbr: "EST", dst_abbr: "EST", rule: "none" },
  {iana: "America/Halifax", city: "Halifax", label: "UTC-04:00 — Atlantic Time (AST/ADT)", std_off: -240, dst_off: -180, std_abbr: "AST", dst_abbr: "ADT", rule: "us" },
  {iana: "America/Puerto_Rico", city: "Puerto Rico", label: "UTC-04:00 — Atlantic Standard Time (AST, No DST)", std_off: -240, dst_off: -240, std_abbr: "AST", dst_abbr: "AST", rule: "none" },
  {iana: "America/St_Johns", city: "St. John's", label: "UTC-03:30 — Newfoundland Time (NST/NDT)", std_off: -210, dst_off: -150, std_abbr: "NST", dst_abbr: "NDT", rule: "us" },
  {iana: "America/Sao_Paulo", city: "Sao Paulo", label: "UTC-03:00 — South America Eastern Time (BRT/ART)", std_off: -180, dst_off: -180, std_abbr: "BRT", dst_abbr: "BRT", rule: "none" },
  {iana: "Etc/GMT+2", city: "UTC-2", label: "UTC-02:00 — Coordinated Universal Time-02", std_off: -120, dst_off: -120, std_abbr: "UTC-2", dst_abbr: "UTC-2", rule: "none" },
  {iana: "Atlantic/Azores", city: "Azores", label: "UTC-01:00 — Azores Time (AZOT/AZOST)", std_off: -60, dst_off: 0, std_abbr: "AZOT", dst_abbr: "AZOST", rule: "eu" },
  {iana: "Atlantic/Cape_Verde", city: "Cape Verde", label: "UTC-01:00 — Cape Verde Time (CVT, No DST)", std_off: -60, dst_off: -60, std_abbr: "CVT", dst_abbr: "CVT", rule: "none" },
  {iana: "Atlantic/Reykjavik", city: "Reykjavik", label: "UTC+00:00 — Greenwich Mean Time (GMT, No DST)", std_off: 0, dst_off: 0, std_abbr: "GMT", dst_abbr: "GMT", rule: "none" },
  {iana: "Europe/London", city: "London", label: "UTC+00:00 — Western European Time (GMT/BST)", std_off: 0, dst_off: 60, std_abbr: "GMT", dst_abbr: "BST", rule: "eu" },
  {iana: "Europe/Berlin", city: "Berlin", label: "UTC+01:00 — Central European Time (CET/CEST)", std_off: 60, dst_off: 120, std_abbr: "CET", dst_abbr: "CEST", rule: "eu" },
  {iana: "Africa/Lagos", city: "Lagos", label: "UTC+01:00 — West Africa Time (WAT, No DST)", std_off: 60, dst_off: 60, std_abbr: "WAT", dst_abbr: "WAT", rule: "none" },
  {iana: "Europe/Athens", city: "Athens", label: "UTC+02:00 — Eastern European Time (EET/EEST)", std_off: 120, dst_off: 180, std_abbr: "EET", dst_abbr: "EEST", rule: "eu" },
  {iana: "Africa/Johannesburg", city: "Johannesburg", label: "UTC+02:00 — Central / South Africa Time (CAT/SAST)", std_off: 120, dst_off: 120, std_abbr: "SAST", dst_abbr: "SAST", rule: "none" },
  {iana: "Asia/Riyadh", city: "Riyadh", label: "UTC+03:00 — Arabia / East Africa Time (AST/EAT)", std_off: 180, dst_off: 180, std_abbr: "AST", dst_abbr: "AST", rule: "none" },
  {iana: "Asia/Tehran", city: "Tehran", label: "UTC+03:30 — Iran Standard Time (IRST)", std_off: 210, dst_off: 210, std_abbr: "IRST", dst_abbr: "IRST", rule: "none" },
  {iana: "Asia/Dubai", city: "Dubai", label: "UTC+04:00 — Gulf Standard Time (GST)", std_off: 240, dst_off: 240, std_abbr: "GST", dst_abbr: "GST", rule: "none" },
  {iana: "Asia/Kabul", city: "Kabul", label: "UTC+04:30 — Afghanistan Time (AFT)", std_off: 270, dst_off: 270, std_abbr: "AFT", dst_abbr: "AFT", rule: "none" },
  {iana: "Asia/Karachi", city: "Karachi", label: "UTC+05:00 — Pakistan / West Asia Time (PKT)", std_off: 300, dst_off: 300, std_abbr: "PKT", dst_abbr: "PKT", rule: "none" },
  {iana: "Asia/Kolkata", city: "Kolkata", label: "UTC+05:30 — India / Sri Lanka Standard Time (IST)", std_off: 330, dst_off: 330, std_abbr: "IST", dst_abbr: "IST", rule: "none" },
  {iana: "Asia/Kathmandu", city: "Kathmandu", label: "UTC+05:45 — Nepal Time (NPT)", std_off: 345, dst_off: 345, std_abbr: "NPT", dst_abbr: "NPT", rule: "none" },
  {iana: "Asia/Dhaka", city: "Dhaka", label: "UTC+06:00 — Bangladesh / Central Asia Time (BST)", std_off: 360, dst_off: 360, std_abbr: "BST", dst_abbr: "BST", rule: "none" },
  {iana: "Asia/Yangon", city: "Yangon", label: "UTC+06:30 — Myanmar Time (MMT)", std_off: 390, dst_off: 390, std_abbr: "MMT", dst_abbr: "MMT", rule: "none" },
  {iana: "Asia/Bangkok", city: "Bangkok", label: "UTC+07:00 — Indochina Time (ICT)", std_off: 420, dst_off: 420, std_abbr: "ICT", dst_abbr: "ICT", rule: "none" },
  {iana: "Asia/Singapore", city: "Singapore", label: "UTC+08:00 — China / Singapore / AWST (CST/SGT/AWST)", std_off: 480, dst_off: 480, std_abbr: "SGT", dst_abbr: "SGT", rule: "none" },
  {iana: "Australia/Eucla", city: "Eucla", label: "UTC+08:45 — Australian Central Western Time (ACWST)", std_off: 525, dst_off: 525, std_abbr: "ACWST", dst_abbr: "ACWST", rule: "none" },
  {iana: "Asia/Tokyo", city: "Tokyo", label: "UTC+09:00 — Japan / Korea Standard Time (JST/KST)", std_off: 540, dst_off: 540, std_abbr: "JST", dst_abbr: "JST", rule: "none" },
  {iana: "Australia/Adelaide", city: "Adelaide", label: "UTC+09:30 — Australian Central Time (ACST/ACDT)", std_off: 570, dst_off: 630, std_abbr: "ACST", dst_abbr: "ACDT", rule: "au" },
  {iana: "Australia/Darwin", city: "Darwin", label: "UTC+09:30 — Australian Central Standard Time (ACST, No DST)", std_off: 570, dst_off: 570, std_abbr: "ACST", dst_abbr: "ACST", rule: "none" },
  {iana: "Australia/Sydney", city: "Sydney", label: "UTC+10:00 — Australian Eastern Time (AEST/AEDT)", std_off: 600, dst_off: 660, std_abbr: "AEST", dst_abbr: "AEDT", rule: "au" },
  {iana: "Australia/Brisbane", city: "Brisbane", label: "UTC+10:00 — Australian Eastern Standard Time (AEST, No DST)", std_off: 600, dst_off: 600, std_abbr: "AEST", dst_abbr: "AEST", rule: "none" },
  {iana: "Australia/Lord_Howe", city: "Lord Howe", label: "UTC+10:30 — Lord Howe Time (LHST/LHDT)", std_off: 630, dst_off: 660, std_abbr: "LHST", dst_abbr: "LHDT", rule: "au30" },
  {iana: "Pacific/Guadalcanal", city: "Guadalcanal", label: "UTC+11:00 — Solomon Islands / New Caledonia Time (SBT)", std_off: 660, dst_off: 660, std_abbr: "SBT", dst_abbr: "SBT", rule: "none" },
  {iana: "Pacific/Auckland", city: "Auckland", label: "UTC+12:00 — New Zealand Time (NZST/NZDT)", std_off: 720, dst_off: 780, std_abbr: "NZST", dst_abbr: "NZDT", rule: "nz" },
  {iana: "Etc/GMT-12", city: "UTC+12", label: "UTC+12:00 — Coordinated Universal Time+12 (No DST)", std_off: 720, dst_off: 720, std_abbr: "UTC+12", dst_abbr: "UTC+12", rule: "none" },
  {iana: "Pacific/Chatham", city: "Chatham", label: "UTC+12:45 — Chatham Islands Time (CHAST/CHADT)", std_off: 765, dst_off: 825, std_abbr: "CHAST", dst_abbr: "CHADT", rule: "nz" },
  {iana: "Pacific/Tongatapu", city: "Tongatapu", label: "UTC+13:00 — Tonga / Phoenix Islands Time (TOT)", std_off: 780, dst_off: 780, std_abbr: "TOT", dst_abbr: "TOT", rule: "none" },
  {iana: "Pacific/Kiritimati", city: "Kiritimati", label: "UTC+14:00 — Line Islands Time (LINT)", std_off: 840, dst_off: 840, std_abbr: "LINT", dst_abbr: "LINT", rule: "none" },
];

export interface DevicePrefSpecItem {
  key: string;
  label: string;
  domain: "select" | "switch" | "number" | "text";
  default: boolean | number | string;
  section: string;
  esphome_section: string;
  group_tier: "behavior" | "display" | "interface" | null;
  options: ReadonlyArray<string>;
  min: number | null;
  max: number | null;
  step: number | null;
  unit: string;
  capability: string;
}

export const DEVICE_PREF_SPECS_CATALOG: ReadonlyArray<DevicePrefSpecItem> = [
  {key: "wake_word_mode", label: "Wake Word Mode", domain: "select", default: "Docked Only", section: "audio", esphome_section: "voice", group_tier: "behavior", options: ["Docked Only", "Always On", "Disabled"], min: null, max: null, step: null, unit: "", capability: "mic" },
  {key: "tap_to_wake", label: "Tap to Wake", domain: "select", default: "Docked Only", section: "power", esphome_section: "sleep", group_tier: "behavior", options: ["Single Tap", "Double Tap", "Docked Only", "Disabled"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "pickup_to_wake", label: "Pickup to Wake", domain: "select", default: "Docked Only", section: "power", esphome_section: "sleep", group_tier: "behavior", options: ["Always On", "Docked Only", "Disabled"], min: null, max: null, step: null, unit: "", capability: "display_imu" },
  {key: "battery_screen_timeout", label: "Battery Screen Timeout", domain: "select", default: "30s", section: "power", esphome_section: "sleep", group_tier: "behavior", options: ["10s", "15s", "30s", "1 min", "2 min", "Never"], min: null, max: null, step: null, unit: "", capability: "display_battery" },
  {key: "docked_idle_timeout", label: "Docked Idle Timeout", domain: "select", default: "1 min", section: "display", esphome_section: "display", group_tier: "behavior", options: ["10s", "15s", "30s", "1 min", "2 min", "5 min", "Never"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "battery_hibernate_timeout", label: "Battery Hibernate Timeout", domain: "select", default: "15 min", section: "power", esphome_section: "sleep", group_tier: "behavior", options: ["5 min", "10 min", "15 min", "30 min", "Disabled"], min: null, max: null, step: null, unit: "", capability: "display_battery" },
  {key: "screensaver_mode", label: "Screensaver mode", domain: "select", default: "Docked Only", section: "display", esphome_section: "display", group_tier: "behavior", options: ["Docked Only", "Always", "Never"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "screensaver_style", label: "Screensaver Style", domain: "select", default: "Ambient Clock", section: "display", esphome_section: "display", group_tier: "display", options: ["Ambient Clock", "Photo Frame", "Aurora", "Starfield", "Digital Rain", "Fireworks"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "auto_brightness_mode", label: "Auto Brightness Mode", domain: "select", default: "Sun Synchronized", section: "display", esphome_section: "display", group_tier: "behavior", options: ["Disabled", "Sun Synchronized", "Time Schedule"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "manual_brightness", label: "Manual Brightness", domain: "number", default: 80, section: "display", esphome_section: "display", group_tier: "behavior", options: [], min: 1, max: 100, step: 1, unit: "%", capability: "display" },
  {key: "day_brightness", label: "Day Brightness", domain: "number", default: 90, section: "display", esphome_section: "display", group_tier: "behavior", options: [], min: 1, max: 100, step: 1, unit: "%", capability: "display" },
  {key: "night_brightness", label: "Night Brightness", domain: "number", default: 35, section: "display", esphome_section: "display", group_tier: "behavior", options: [], min: 1, max: 100, step: 1, unit: "%", capability: "display" },
  {key: "day_start_hour", label: "Day Start Hour", domain: "number", default: 7, section: "display", esphome_section: "display", group_tier: "behavior", options: [], min: 0, max: 23, step: 1, unit: ":00", capability: "display" },
  {key: "night_start_hour", label: "Night Start Hour", domain: "number", default: 20, section: "display", esphome_section: "display", group_tier: "behavior", options: [], min: 0, max: 23, step: 1, unit: ":00", capability: "display" },
  {key: "color_profile", label: "Color Profile", domain: "select", default: "Steel Blue", section: "display", esphome_section: "display", group_tier: "display", options: ["Steel Blue", "Pink", "Blue", "Green", "Custom"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "va_visual_profile", label: "Visual Profile", domain: "select", default: "Nebula", section: "display", esphome_section: "display", group_tier: "display", options: ["Nebula", "Solaris", "Rings", "Light Bar", "Dot Wave"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "home_screen_enabled", label: "Enable Home Screen", domain: "switch", default: true, section: "interface", esphome_section: "home", group_tier: "interface", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "start_screen", label: "Start Screen", domain: "select", default: "Home", section: "interface", esphome_section: "home", group_tier: "interface", options: ["Home", "Pinned", "Time App", "Calendar", "Clock Face", "Media", "Home Hub", "Area Controls", "Remote", "Weather", "Cameras", "Games", "Tools"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "return_to_home_timeout", label: "Return to Home Timeout", domain: "select", default: "2 min", section: "interface", esphome_section: "home", group_tier: "interface", options: ["15s", "30s", "1 min", "2 min", "5 min", "10 min", "Never"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "clock_face", label: "Clock Face", domain: "select", default: "Minimal Digital", section: "interface", esphome_section: "display", group_tier: "interface", options: ["Minimal Digital", "Modern Analog", "Hybrid Digital"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "time_format", label: "Time Format", domain: "select", default: "12-Hour (AM/PM)", section: "interface", esphome_section: "display", group_tier: "interface", options: ["12-Hour (AM/PM)", "24-Hour"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "weather_background", label: "Weather Background", domain: "switch", default: true, section: "interface", esphome_section: "display", group_tier: "interface", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "home_sun", label: "Sun", domain: "switch", default: true, section: "interface", esphome_section: "display", group_tier: "interface", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "home_moon", label: "Moon", domain: "switch", default: true, section: "interface", esphome_section: "display", group_tier: "interface", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "wake_greeting", label: "Wake Greeting", domain: "switch", default: true, section: "interface", esphome_section: "display", group_tier: "interface", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "album_art_style", label: "Album Art Style", domain: "select", default: "Full Screen", section: "interface", esphome_section: "music", group_tier: "interface", options: ["Full Screen", "Letterbox", "Standard", "None"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "music_overlay_style", label: "Overlay Style", domain: "select", default: "Art + Metadata", section: "interface", esphome_section: "music", group_tier: "interface", options: ["Art Only", "Art + Metadata", "Always Visible"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "album_sort_order", label: "Album Sort Order", domain: "select", default: "Alphabetical", section: "interface", esphome_section: "music", group_tier: "interface", options: ["Alphabetical", "Newest on Top", "Oldest on Top"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "artist_album_sort_order", label: "Artist Album Sort Order", domain: "select", default: "Oldest on Top", section: "interface", esphome_section: "music", group_tier: "interface", options: ["Oldest on Top", "Newest on Top", "Alphabetical"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "podcast_sort_order", label: "Podcast Sort Order", domain: "select", default: "Newest on Top", section: "interface", esphome_section: "music", group_tier: "interface", options: ["Newest on Top", "Oldest on Top"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "ww_sens_okay_nabu", label: "Okay Nabu Sensitivity", domain: "select", default: "Moderately sensitive", section: "audio", esphome_section: "voice", group_tier: "behavior", options: ["Slightly sensitive", "Moderately sensitive", "Very sensitive"], min: null, max: null, step: null, unit: "", capability: "mic" },
  {key: "ww_sens_hey_luna", label: "Hey Luna Sensitivity", domain: "select", default: "Moderately sensitive", section: "audio", esphome_section: "voice", group_tier: "behavior", options: ["Slightly sensitive", "Moderately sensitive", "Very sensitive"], min: null, max: null, step: null, unit: "", capability: "mic" },
  {key: "ww_sens_hey_jarvis", label: "Hey Jarvis Sensitivity", domain: "select", default: "Moderately sensitive", section: "audio", esphome_section: "voice", group_tier: "behavior", options: ["Slightly sensitive", "Moderately sensitive", "Very sensitive"], min: null, max: null, step: null, unit: "", capability: "mic" },
  {key: "ww_sens_hey_mycroft", label: "Hey Mycroft Sensitivity", domain: "select", default: "Moderately sensitive", section: "audio", esphome_section: "voice", group_tier: "behavior", options: ["Slightly sensitive", "Moderately sensitive", "Very sensitive"], min: null, max: null, step: null, unit: "", capability: "mic" },
  {key: "ww_sens_alexa", label: "Alexa Sensitivity", domain: "select", default: "Moderately sensitive", section: "audio", esphome_section: "voice", group_tier: "behavior", options: ["Slightly sensitive", "Moderately sensitive", "Very sensitive"], min: null, max: null, step: null, unit: "", capability: "mic" },
  {key: "wake_screen_on_assist", label: "Wake Screen on Assist", domain: "switch", default: true, section: "audio", esphome_section: "voice", group_tier: "behavior", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "alert_volume", label: "Alert Volume", domain: "number", default: 80, section: "audio", esphome_section: "sound", group_tier: "behavior", options: [], min: 20, max: 100, step: 5, unit: "%", capability: "speaker" },
  {key: "volume_step_size", label: "Volume Step Size", domain: "number", default: 5, section: "audio", esphome_section: "sound", group_tier: "behavior", options: [], min: 1, max: 10, step: 1, unit: "%", capability: "speaker" },
  {key: "game_sound_effects", label: "Game Sound Effects", domain: "switch", default: true, section: "audio", esphome_section: "sound", group_tier: "behavior", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "ble_beacon_mode", label: "BLE Beacon Mode", domain: "select", default: "Handheld Only", section: "presence", esphome_section: "presence", group_tier: "behavior", options: ["Handheld Only", "Handheld + Screen Off", "Always"], min: null, max: null, step: null, unit: "", capability: "beacon_battery" },
  {key: "weather_sim_condition", label: "Weather Simulation", domain: "select", default: "Live (Home Assistant)", section: "developer", esphome_section: "developer", group_tier: null, options: ["Live (Home Assistant)", "Clear Night", "Sunny / Clear Day", "Partly Cloudy (Day)", "Partly Cloudy (Night)", "Cloudy / Overcast (Day)", "Cloudy / Overcast (Night)", "Fog / Mist (Day)", "Fog / Mist (Night)", "Rainy (Day)", "Rainy (Night)", "Pouring / Heavy Rain", "Snow (Day)", "Snow (Night)", "Thunderstorm (Day)", "Thunderstorm (Night)", "Windy"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "home_clock_tap_action", label: "Home Time Tap", domain: "select", default: "Time App", section: "interface", esphome_section: "home", group_tier: "interface", options: ["Time App", "Clock Face"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "home_date_tap_action", label: "Home Date Tap", domain: "select", default: "Overview", section: "interface", esphome_section: "home", group_tier: "interface", options: ["Day View", "Overview"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "local_clock_label", label: "Local Clock Label", domain: "text", default: "", section: "time", esphome_section: "time", group_tier: null, options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "show_utc_clock", label: "Show UTC Clock", domain: "switch", default: false, section: "interface", esphome_section: "home", group_tier: "interface", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "world_clocks", label: "World Clocks", domain: "text", default: "", section: "interface", esphome_section: "home", group_tier: "interface", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "alarms_summary", label: "Alarms", domain: "text", default: "07:00|0|1;08:30|0|2;09:00|0|2", section: "time", esphome_section: "time", group_tier: null, options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "calendar_lookahead_days", label: "Overview Lookahead", domain: "number", default: 30, section: "interface", esphome_section: "home", group_tier: "interface", options: [], min: 7, max: 60, step: 1, unit: "d", capability: "display" },
  {key: "calendar_week_start", label: "Start Week On", domain: "select", default: "Sunday", section: "interface", esphome_section: "home", group_tier: "interface", options: ["Sunday", "Monday"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "bedtime_active", label: "Bedtime Mode", domain: "switch", default: false, section: "power", esphome_section: "sleep", group_tier: null, options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "bedtime_display", label: "Idle Display in Bedtime", domain: "select", default: "Screen Off", section: "power", esphome_section: "sleep", group_tier: "behavior", options: ["Screen Off", "Ambient Clock"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "bedtime_schedule", label: "Bedtime Schedule", domain: "switch", default: false, section: "power", esphome_section: "sleep", group_tier: "behavior", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "bedtime_start_hour", label: "Bedtime Starts", domain: "number", default: 22, section: "power", esphome_section: "sleep", group_tier: "behavior", options: [], min: 0, max: 23, step: 1, unit: ":00", capability: "display" },
  {key: "bedtime_end_hour", label: "Bedtime Ends", domain: "number", default: 7, section: "power", esphome_section: "sleep", group_tier: "behavior", options: [], min: 0, max: 23, step: 1, unit: ":00", capability: "display" },
  {key: "bedtime_brightness", label: "Bedtime Brightness", domain: "number", default: 15, section: "power", esphome_section: "sleep", group_tier: "behavior", options: [], min: 1, max: 100, step: 1, unit: "%", capability: "display" },
  {key: "camera_default_view", label: "Default camera view", domain: "select", default: "Grid", section: "interface", esphome_section: "cameras", group_tier: "interface", options: ["Grid", "Single", "Carousel"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "camera_carousel_interval", label: "Carousel interval", domain: "select", default: "15s", section: "interface", esphome_section: "cameras", group_tier: "interface", options: ["10s", "15s", "30s", "60s"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "camera_framing", label: "Camera framing", domain: "select", default: "Uncropped", section: "interface", esphome_section: "cameras", group_tier: "interface", options: ["Uncropped", "Fill"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "camera_stream_mode", label: "Camera stream mode", domain: "select", default: "Auto", section: "interface", esphome_section: "cameras", group_tier: "interface", options: ["Auto", "Low Bandwidth", "Snapshots"], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "camera_doorbell_popup", label: "Doorbell ring popup", domain: "select", default: "Snapshot", section: "interface", esphome_section: "cameras", group_tier: "interface", options: ["Snapshot", "Live Video"], min: null, max: null, step: null, unit: "", capability: "hw_jpeg" },
  {key: "screensaver_photo_clock", label: "Show subtle clock", domain: "switch", default: false, section: "display", esphome_section: "display", group_tier: "display", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
  {key: "weather_app_background", label: "Weather app background", domain: "switch", default: true, section: "interface", esphome_section: "display", group_tier: "interface", options: [], min: null, max: null, step: null, unit: "", capability: "display" },
];

export const DEVICE_PREF_SPECS_MAP: Readonly<Record<string, DevicePrefSpecItem>> = Object.fromEntries(DEVICE_PREF_SPECS_CATALOG.map((s) => [s.key, s]));

export const DEFAULT_DOCK_ROUTES = "app:pinned,app:music,app:home_hub,app:cameras,app:area,app:remote,app:games,app:tools";
export const DEFAULT_DOCK_ROUTES_TOKENS: ReadonlyArray<string> = [
  "app:pinned",
  "app:music",
  "app:home_hub",
  "app:cameras",
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

export const DEFAULT_HOME_CATEGORIES = "alarm,intercom,thermostat,entry,vacuum";
export const DEFAULT_HOME_CATEGORIES_TOKENS: ReadonlyArray<string> = [
  "alarm",
  "intercom",
  "thermostat",
  "entry",
  "vacuum",
];

export const DEFAULT_TOOLS_ITEMS = "stopwatch,level,flashlight,calculator,dice,coin_flip";
export const DEFAULT_TOOLS_ITEMS_TOKENS: ReadonlyArray<string> = [
  "stopwatch",
  "level",
  "flashlight",
  "calculator",
  "dice",
  "coin_flip",
];

export const DEFAULT_GAMES_ITEMS = "marbles,archery,bricks,chomp,2048,memory";
export const DEFAULT_GAMES_ITEMS_TOKENS: ReadonlyArray<string> = [
  "marbles",
  "archery",
  "bricks",
  "chomp",
  "2048",
  "memory",
];
