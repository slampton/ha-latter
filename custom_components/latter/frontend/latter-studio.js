// AUTO-GENERATED FILE — DO NOT EDIT DIRECTLY.
// Source: ha-latter/frontend_src/src/ (build via `node ha-latter/frontend_src/build.mjs`).

// --- src/protocol-schema.ts ---
// AUTO-GENERATED FROM protocol/latter_v3.json BY tools/gen_protocol.py — DO NOT EDIT MANUALLY.
const PROTOCOL_CONTRACT_VERSION = 3;
const SHORTCUT_ROUTES_CATALOG = [
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
const ACTIVITY_SOURCES_CATALOG = [
  {token: "calendar", label: "Calendar"},
  {token: "music_queue", label: "Music Queue"},
  {token: "stopwatch", label: "Stopwatch"},
  {token: "alarms", label: "Alarms"},
  {token: "timers", label: "Timers"},
];
const AREA_CATEGORIES_CATALOG = [
  {token: "scene", label: "Scenes"},
  {token: "light", label: "Lights"},
  {token: "cover", label: "Blinds & Curtains"},
  {token: "fan", label: "Fans"},
  {token: "switch", label: "Switches"},
  {token: "climate", label: "Climate"},
  {token: "media", label: "Media"},
  {token: "all", label: "All Devices"},
];
const HOME_CATEGORIES_CATALOG = [
  {token: "alarm", label: "Security Alarm"},
  {token: "cameras", label: "Cameras"},
  {token: "intercom", label: "Intercom"},
  {token: "thermostat", label: "Thermostat"},
  {token: "entry", label: "Entry & Garage"},
  {token: "vacuum", label: "Robot Vacuum"},
];
const DEFAULT_DOCK_ROUTES = "app:pinned,app:music,app:home_hub,app:area,app:remote,app:games,app:tools";
const DEFAULT_DOCK_ROUTES_TOKENS = [
  "app:pinned",
  "app:music",
  "app:home_hub",
  "app:area",
  "app:remote",
  "app:games",
  "app:tools",
];
const DEFAULT_ACTIVITY_CARD = "1";
const DEFAULT_ACTIVITY_CARD_TOKENS = [
  "1",
];
const DEFAULT_ACTIVITY_SOURCES = "calendar,music_queue,stopwatch,alarms,timers";
const DEFAULT_ACTIVITY_SOURCES_TOKENS = [
  "calendar",
  "music_queue",
  "stopwatch",
  "alarms",
  "timers",
];
const DEFAULT_AREA_CATEGORIES = "scene,light,cover,fan,switch,climate,media";
const DEFAULT_AREA_CATEGORIES_TOKENS = [
  "scene",
  "light",
  "cover",
  "fan",
  "switch",
  "climate",
  "media",
];
const DEFAULT_HOME_CATEGORIES = "alarm,cameras,intercom,thermostat,entry,vacuum";
const DEFAULT_HOME_CATEGORIES_TOKENS = [
  "alarm",
  "cameras",
  "intercom",
  "thermostat",
  "entry",
  "vacuum",
];

// --- src/constants.ts ---
/**
 * Canonical constants, route maps, issue messages, and Title Case dictionaries for Latter Studio.
 */
const STUDIO_REV = 24;
const MAX_DOCK_ITEMS = 24;
const MAX_PINNED_ITEMS = 96;
const SHORTCUT_LABEL_MAX = 24;
const MAX_WALLPAPER_UPLOAD_BYTES = 15 * 1024 * 1024;
const DEVICE_VIEW_SLUGS = {
  dashboard: "overview",
  display: "display",
  interface: "interface",
  audio_voice: "audio",
  power: "power",
  presence: "presence",
  tools: "tools",
};
const SYSTEM_VIEW_SLUGS = {system_overview: "overview", shared_entities: "shared", remotes: "remotes", system_sync: "groups", area_tracking: "presence", system_tools: "tools"};
const VIEW_TITLES = {
  system_overview: "Overview",
  shared_entities: "Shared Entities",
  remotes: "Media & Remotes",
  system_sync: "Device Groups",
  area_tracking: "BLE & Area Presence",
  system_tools: "Tools",
  select_device_prompt: "Managed Devices",
  discovered_devices: "Discovered Devices",
  dashboard: "Overview",
  display: "Display",
  interface: "Interface",
  audio_voice: "Audio",
  power: "Power",
  presence: "Presence",
  tools: "Tools",
};
const _typecheckViewMaps
  = [DEVICE_VIEW_SLUGS, SYSTEM_VIEW_SLUGS, VIEW_TITLES];
void _typecheckViewMaps;
// Messages for Latter's Home Assistant Repairs (kind = translation key in strings.json).
const ISSUE_TEXT = {
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
const START_SCREEN_OPTIONS = [
  "Home",
  "Pinned",
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
const HOME_CLOCK_TAP_OPTIONS = [
  "Time App",
  "Clock Face",
];
const MAX_WORLD_CLOCKS = 4;
const DEFAULT_ALARMS_SUMMARY = "07:00|0|1;08:30|0|2;09:00|0|2";
const ALARM_RECURRENCE_OPTIONS = [
  { value: 0, label: "Daily" },
  { value: 1, label: "Weekdays" },
  { value: 2, label: "Weekends" },
  { value: 3, label: "Once" },
];
const WORLD_CLOCK_ZONES_CATALOG = [
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
const RETURN_TO_HOME_TIMEOUT_OPTIONS = [
  "15s",
  "30s",
  "1 min",
  "2 min",
  "5 min",
  "10 min",
  "Never",
];
const SECURITY_PIN_POLICY_OPTIONS = [
  { value: "auto", label: "Auto (Recommended)" },
  { value: "allow", label: "Allow Without PIN" },
  { value: "require_pin", label: "Require PIN" },
  { value: "block", label: "Block Unlock & Disarm" },
];
const WALLPAPER_ROTATION_OPTIONS = [
  { value: 0, label: "Do not rotate" },
  { value: 5, label: "Every 5 minutes" },
  { value: 15, label: "Every 15 minutes" },
  { value: 30, label: "Every 30 minutes" },
  { value: 60, label: "Every hour" },
  { value: 360, label: "Every 6 hours" },
  { value: 1440, label: "Once a day" },
];
const DEFAULT_DEVICE_GROUP_IDS = new Set([
  "pocket_carry",
  "handhelds",
  "wearables",
  "wall_panels",
]);
const GROUP_BEHAVIOR_NON_PREF_KEYS = [
  "native_ble_tracking",
  "ble_auto_switch",
  "sync_device_area",
  "area_follow_dwell_s",
  "area_handoff",
  "security_pin_policy",
];
const GROUP_DISPLAY_NON_PREF_KEYS = [
  "wallpaper_source",
  "wallpaper_cycle_minutes",
  "device_custom_color",
];
const GROUP_INTERFACE_NON_PREF_KEYS = [
  "dock_items",
  "pinned_items",
  "area_categories",
  "home_categories",
  "activity_card",
  "activity_sources",
  "device_remote_group",
];
const LABEL_MINOR_WORDS = new Set([
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
const LABEL_ACRONYMS = {
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

// --- src/lib/lit.ts ---
/**
 * Lightweight, strictly typed Lit reactive element & `<template>` marker-part engine for Latter Studio.
 * Preserves live DOM nodes (focus, cursor selection, open selects/details/dialogs) across reactive updates.
 */
const nothing = Symbol.for("latter.lit.nothing");
function css(strings, ...values) {
  let out = "";
  for (let i = 0; i < strings.length; i += 1) {
    out += strings[i];
    if (i < values.length) {
      const v = values[i];
      if (v && typeof v === "object" && "styleSheetText" in (v)) {
        out += (v).styleSheetText;
      } else if (v !== undefined && v !== null) {
        out += String(v);
      }
    }
  }
  return { styleSheetText: out };
}
function html(strings, ...values) {
  return { _$litType$: 1, strings, values };
}
function repeat (
  items,
  keyFn,
  templateFn,
) {
  const keys = [];
  const templates = [];
  for (let i = 0; i < items.length; i += 1) {
    keys.push(keyFn(items[i], i));
    templates.push(templateFn(items[i], i));
  }
  return { _$litKeyed$: 1, keys, templates };
}
const TEMPLATE_CACHE = new WeakMap();
function compileTemplate(strings) {
  const cached = TEMPLATE_CACHE.get(strings);
  if (cached) return cached;
  const descriptors = [];
  let markup = "";
  let inTag = false;
  let quoteChar = "";
  let pendingAttrStart = -1;
  let pendingAttrPrefix = "";
  let pendingAttrName = "";
  let pendingAttrStatics = [];
  let pendingAttrParts = [];
  let attrMarkerSeq = 0;
  for (let i = 0; i < strings.length; i += 1) {
    const chunk = strings[i];
    for (let c = 0; c < chunk.length; c += 1) {
      const ch = chunk[c];
      if (!inTag) {
        if (ch === "<" && chunk.slice(c, c + 4) !== "<!--") {
          inTag = true;
          quoteChar = "";
        }
        markup += ch;
      } else if (quoteChar) {
        if (ch === quoteChar) {
          if (pendingAttrStart >= 0) {
            const tail = markup.slice(pendingAttrStart);
            pendingAttrStatics.push(tail);
            markup = markup.slice(0, pendingAttrStart);
            const markerAttr = `data-latter-b${attrMarkerSeq++}`;
            if (pendingAttrPrefix === "@") {
              descriptors.push({
                kind: "event",
                markerAttr,
                eventName: pendingAttrName,
                partIndex: pendingAttrParts[0],
              });
            } else if (pendingAttrPrefix === ".") {
              descriptors.push({
                kind: "prop",
                markerAttr,
                propName: pendingAttrName,
                partIndex: pendingAttrParts[0],
              });
            } else if (pendingAttrPrefix === "?") {
              descriptors.push({
                kind: "bool",
                markerAttr,
                attrName: pendingAttrName,
                partIndex: pendingAttrParts[0],
              });
            } else {
              descriptors.push({
                kind: "attr",
                markerAttr,
                attrName: pendingAttrName,
                statics: pendingAttrStatics,
                partIndices: pendingAttrParts,
              });
            }
            markup += `${markerAttr}=""`;
            pendingAttrStart = -1;
            pendingAttrPrefix = "";
            pendingAttrName = "";
            pendingAttrStatics = [];
            pendingAttrParts = [];
          } else {
            markup += ch;
          }
          quoteChar = "";
        } else {
          markup += ch;
        }
      } else {
        if (ch === '"' || ch === "'") {
          quoteChar = ch;
          markup += ch;
        } else if (ch === ">") {
          inTag = false;
          markup += ch;
        } else {
          markup += ch;
        }
      }
    }
    if (i === strings.length - 1) break;
    if (!inTag) {
      const commentText = `latter-p-${i}`;
      descriptors.push({ kind: "child", commentText, partIndex: i });
      markup += `<!--${commentText}-->`;
    } else if (quoteChar) {
      if (pendingAttrStart < 0) {
        const eqQuoteIdx = markup.lastIndexOf(`=${quoteChar}`);
        let nameStart = eqQuoteIdx - 1;
        while (nameStart >= 0 && /\s/.test(markup[nameStart])) nameStart -= 1;
        const nameEnd = nameStart + 1;
        while (nameStart > 0 && !/[\s<>"'=]/.test(markup[nameStart - 1])) nameStart -= 1;
        const rawAttr = markup.slice(nameStart, nameEnd);
        const firstStatic = markup.slice(eqQuoteIdx + 2);
        markup = markup.slice(0, nameStart);
        const pfx = rawAttr[0] === "@" || rawAttr[0] === "." || rawAttr[0] === "?" ? rawAttr[0] : "";
        pendingAttrPrefix = pfx;
        pendingAttrName = pfx ? rawAttr.slice(1) : rawAttr;
        pendingAttrStatics = [firstStatic];
        pendingAttrParts = [i];
        pendingAttrStart = markup.length;
      } else {
        const midStatic = markup.slice(pendingAttrStart);
        markup = markup.slice(0, pendingAttrStart);
        pendingAttrStatics.push(midStatic);
        pendingAttrParts.push(i);
      }
    } else {
      const mUnquoted = /([@.?]?[A-Za-z_:][A-Za-z0-9_.:-]*)\s*=\s*$/.exec(markup);
      if (!mUnquoted) {
        throw new Error(`Unsupported template expression inside tag near: ${markup.slice(-40)}`);
      }
      const rawAttr = mUnquoted[1];
      markup = markup.slice(0, mUnquoted.index);
      const pfx = rawAttr[0] === "@" || rawAttr[0] === "." || rawAttr[0] === "?" ? rawAttr[0] : "";
      const name = pfx ? rawAttr.slice(1) : rawAttr;
      const markerAttr = `data-latter-b${attrMarkerSeq++}`;
      if (pfx === "@") {
        descriptors.push({ kind: "event", markerAttr, eventName: name, partIndex: i });
      } else if (pfx === ".") {
        descriptors.push({ kind: "prop", markerAttr, propName: name, partIndex: i });
      } else if (pfx === "?") {
        descriptors.push({ kind: "bool", markerAttr, attrName: name, partIndex: i });
      } else {
        descriptors.push({
          kind: "attr",
          markerAttr,
          attrName: name,
          statics: ["", ""],
          partIndices: [i],
        });
      }
      markup += `${markerAttr}=""`;
    }
  }
  const templateEl = document.createElement("template");
  templateEl.innerHTML = markup;
  const compiled = { templateEl, descriptors };
  TEMPLATE_CACHE.set(strings, compiled);
  return compiled;
}
class EventPart {
           priority = 1;
          handler = null;
          bound = false;
                   wrapper = (ev) => {
    if (typeof this.handler === "function") {
      this.handler(ev);
    }
  };
                   el;
                   eventName;
                   partIndex;
  constructor(el, eventName, partIndex) {
    this.el = el;
    this.eventName = eventName;
    this.partIndex = partIndex;
  }
  update(values) {
    const next = values[this.partIndex];
    this.handler = typeof next === "function" ? (next) : null;
    if (this.handler && !this.bound) {
      this.el.addEventListener(this.eventName, this.wrapper);
      this.bound = true;
    } else if (!this.handler && this.bound) {
      this.el.removeEventListener(this.eventName, this.wrapper);
      this.bound = false;
    }
  }
}
class BoolAttrPart {
           priority = 1;
          prev = undefined;
                   el;
                   attrName;
                   partIndex;
  constructor(el, attrName, partIndex) {
    this.el = el;
    this.attrName = attrName;
    this.partIndex = partIndex;
  }
  update(values) {
    const next = Boolean(values[this.partIndex] && values[this.partIndex] !== nothing);
    if (next !== this.prev) {
      this.prev = next;
      this.el.toggleAttribute(this.attrName, next);
    }
  }
}
class AttrPart {
           priority = 1;
          prev = undefined;
                   el;
                   attrName;
                   statics;
                   partIndices;
  constructor(el, attrName, statics, partIndices) {
    this.el = el;
    this.attrName = attrName;
    this.statics = statics;
    this.partIndices = partIndices;
  }
  update(values) {
    if (
      this.partIndices.length === 1 &&
      this.statics[0] === "" &&
      this.statics[1] === ""
    ) {
      const raw = values[this.partIndices[0]];
      if (this.attrName.startsWith("aria-") && typeof raw === "boolean") {
        const str = raw ? "true" : "false";
        if (str !== this.prev) {
          this.prev = str;
          this.el.setAttribute(this.attrName, str);
        }
        return;
      }
      if (raw === nothing || raw === null || raw === undefined || raw === false) {
        if (this.prev !== nothing) {
          this.prev = nothing;
          this.el.removeAttribute(this.attrName);
        }
        return;
      }
      const str = String(raw);
      if (str !== this.prev) {
        this.prev = str;
        this.el.setAttribute(this.attrName, str);
      }
      return;
    }
    let out = this.statics[0];
    for (let i = 0; i < this.partIndices.length; i += 1) {
      const v = values[this.partIndices[i]];
      out += v === nothing || v === null || v === undefined ? "" : String(v);
      out += this.statics[i + 1];
    }
    if (out !== this.prev) {
      this.prev = out;
      this.el.setAttribute(this.attrName, out);
    }
  }
}
const NON_TEXT_INPUT_TYPES = new Set([
  "button",
  "checkbox",
  "color",
  "file",
  "hidden",
  "image",
  "radio",
  "range",
  "reset",
  "submit",
]);
function isActivelyFocusedTextControl(el) {
  const tag = el.tagName;
  if (tag !== "INPUT" && tag !== "TEXTAREA") return false;
  if (tag === "INPUT") {
    const inpType = ((el).type || "text").toLowerCase();
    if (NON_TEXT_INPUT_TYPES.has(inpType)) return false;
  }
  const root = typeof el.getRootNode === "function" ? el.getRootNode() : null;
  if (root && typeof root === "object" && "activeElement" in root) {
    return (root).activeElement === el;
  }
  return typeof document !== "undefined" && document.activeElement === el;
}
class PropertyPart {
  // Priority 2 runs AFTER ChildPart (priority 0) so <select> options exist before `.value` is assigned.
           priority = 2;
                   el;
                   propName;
                   partIndex;
  constructor(el, propName, partIndex) {
    this.el = el;
    this.propName = propName;
    this.partIndex = partIndex;
  }
  update(values) {
    const raw = values[this.partIndex];
    const next = raw === nothing || raw === null || raw === undefined ? "" : raw;
    const target = this.el;
    if (target[this.propName] !== next) {
      if (this.propName === "value" && isActivelyFocusedTextControl(this.el)) {
        return;
      }
      target[this.propName] = next;
    }
  }
}
function isTemplateResult(v) {
  return Boolean(v && typeof v === "object" && (v)._$litType$ === 1);
}
function isKeyedResult(v) {
  return Boolean(v && typeof v === "object" && (v)._$litKeyed$ === 1);
}
class TemplateInstance {
           strings;
           startMarker;
           endMarker;
                   parts;
  constructor(compiled) {
    this.strings = compiled.templateEl ? ([]) : ([]);
    const frag = compiled.templateEl.content.cloneNode(true);
    this.startMarker = document.createComment("latter-i-s");
    this.endMarker = document.createComment("latter-i-e");
    const commentMap = new Map();
    const walker = document.createTreeWalker(frag, NodeFilter.SHOW_COMMENT);
    let node = walker.nextNode();
    while (node) {
      const c = node;
      if (c.data.startsWith("latter-p-")) {
        commentMap.set(c.data, c);
      }
      node = walker.nextNode();
    }
    const parts = [];
    for (const d of compiled.descriptors) {
      if (d.kind === "child") {
        const startC = commentMap.get(d.commentText);
        if (startC && startC.parentNode) {
          const endC = document.createComment(`${d.commentText}-end`);
          startC.parentNode.insertBefore(endC, startC.nextSibling);
          parts.push(new ChildPart(startC, endC, d.partIndex));
        }
      } else {
        const el = frag.querySelector(`[${d.markerAttr}]`);
        if (el) {
          if (d.kind === "event") {
            parts.push(new EventPart(el, d.eventName, d.partIndex));
          } else if (d.kind === "prop") {
            parts.push(new PropertyPart(el, d.propName, d.partIndex));
          } else if (d.kind === "bool") {
            parts.push(new BoolAttrPart(el, d.attrName, d.partIndex));
          } else if (d.kind === "attr") {
            parts.push(new AttrPart(el, d.attrName, d.statics, d.partIndices));
          }
        }
      }
    }
    for (const d of compiled.descriptors) {
      if (d.kind !== "child") {
        const el = frag.querySelector(`[${d.markerAttr}]`);
        if (el) el.removeAttribute(d.markerAttr);
      }
    }
    parts.sort((a, b) => a.priority - b.priority);
    this.parts = parts;
    const wrapper = document.createDocumentFragment();
    wrapper.appendChild(this.startMarker);
    wrapper.appendChild(frag);
    wrapper.appendChild(this.endMarker);
    this._fragment = wrapper;
  }
          _fragment;
  mountBefore(parent, refNode) {
    if (this._fragment) {
      parent.insertBefore(this._fragment, refNode);
      this._fragment = null;
    }
  }
  moveBefore(parent, refNode) {
    let cur = this.startMarker;
    while (cur) {
      const next = cur === this.endMarker ? null : cur.nextSibling;
      parent.insertBefore(cur, refNode);
      cur = next;
    }
  }
  remove() {
    let cur = this.startMarker;
    while (cur) {
      const next = cur === this.endMarker ? null : cur.nextSibling;
      if (cur.parentNode) cur.parentNode.removeChild(cur);
      cur = next;
    }
  }
  update(values) {
    for (let i = 0; i < this.parts.length; i += 1) {
      this.parts[i].update(values);
    }
  }
}
function createInstance(res) {
  const compiled = compileTemplate(res.strings);
  const inst = new TemplateInstance(compiled);
  return { strings: res.strings, inst };
}
class ChildPart {
           priority = 0;
          mode = "empty";
          textNode = null;
          singleEntry = null;
          arrayEntries = [];
          keyedMap = new Map();
                   startMarker;
                   endMarker;
                   partIndex;
  constructor(startMarker, endMarker, partIndex) {
    this.startMarker = startMarker;
    this.endMarker = endMarker;
    this.partIndex = partIndex;
  }
          clearBetween() {
    let cur = this.startMarker.nextSibling;
    while (cur && cur !== this.endMarker) {
      const next = cur.nextSibling;
      cur.parentNode?.removeChild(cur);
      cur = next;
    }
    this.textNode = null;
    this.singleEntry = null;
    this.arrayEntries = [];
    this.keyedMap.clear();
    this.mode = "empty";
  }
  update(values) {
    const val = values[this.partIndex];
    const parent = this.endMarker.parentNode;
    if (!parent) return;
    if (val === nothing || val === null || val === undefined || val === false) {
      if (this.mode !== "empty") this.clearBetween();
      return;
    }
    if (isTemplateResult(val)) {
      if (this.mode === "template" && this.singleEntry && this.singleEntry.strings === val.strings) {
        this.singleEntry.inst.update(val.values);
        return;
      }
      this.clearBetween();
      const entry = createInstance(val);
      entry.inst.mountBefore(parent, this.endMarker);
      entry.inst.update(val.values);
      this.singleEntry = entry;
      this.mode = "template";
      return;
    }
    if (isKeyedResult(val)) {
      if (this.mode !== "keyed") {
        this.clearBetween();
        this.mode = "keyed";
      }
      const nextMap = new Map();
      const ordered = [];
      for (let i = 0; i < val.keys.length; i += 1) {
        const k = val.keys[i];
        const tpl = val.templates[i];
        const existing = this.keyedMap.get(k);
        if (existing && existing.strings === tpl.strings) {
          this.keyedMap.delete(k);
          existing.inst.update(tpl.values);
          nextMap.set(k, existing);
          ordered.push(existing);
        } else {
          if (existing) {
            existing.inst.remove();
            this.keyedMap.delete(k);
          }
          const created = createInstance(tpl);
          created.inst.mountBefore(parent, this.endMarker);
          created.inst.update(tpl.values);
          nextMap.set(k, created);
          ordered.push(created);
        }
      }
      for (const leftover of this.keyedMap.values()) {
        leftover.inst.remove();
      }
      // Ensure DOM order matches `ordered` without disturbing focused controls when already ordered.
      let cursor = this.endMarker;
      for (let i = ordered.length - 1; i >= 0; i -= 1) {
        const item = ordered[i].inst;
        if (item.endMarker.nextSibling !== cursor) {
          item.moveBefore(parent, cursor);
        }
        cursor = item.startMarker;
      }
      this.keyedMap = nextMap;
      return;
    }
    if (Array.isArray(val)) {
      const tpls = [];
      let allTemplates = true;
      for (let i = 0; i < val.length; i += 1) {
        const item = val[i];
        if (item === nothing || item === null || item === undefined || item === false) continue;
        if (isTemplateResult(item)) {
          tpls.push(item);
        } else {
          allTemplates = false;
          break;
        }
      }
      if (allTemplates) {
        if (this.mode !== "array") {
          this.clearBetween();
          this.mode = "array";
        }
        while (this.arrayEntries.length > tpls.length) {
          const popped = this.arrayEntries.pop();
          popped?.inst.remove();
        }
        for (let i = 0; i < tpls.length; i += 1) {
          const tpl = tpls[i];
          const existing = this.arrayEntries[i];
          if (existing && existing.strings === tpl.strings) {
            existing.inst.update(tpl.values);
          } else {
            const refNode = existing ? existing.inst.startMarker : this.endMarker;
            if (existing) existing.inst.remove();
            const created = createInstance(tpl);
            created.inst.mountBefore(parent, refNode);
            created.inst.update(tpl.values);
            this.arrayEntries[i] = created;
          }
        }
        return;
      }
      const joined = val
        .filter((x) => x !== nothing && x !== null && x !== undefined && x !== false)
        .map((x) => String(x))
        .join("");
      this.setText(parent, joined);
      return;
    }
    this.setText(parent, String(val));
  }
          setText(parent, str) {
    if (this.mode === "text" && this.textNode) {
      if (this.textNode.data !== str) {
        this.textNode.data = str;
      }
      return;
    }
    this.clearBetween();
    this.textNode = document.createTextNode(str);
    parent.insertBefore(this.textNode, this.endMarker);
    this.mode = "text";
  }
}
class LitElement extends HTMLElement {
  static styles;
           renderRoot;
                   _controllers = new Set();
          _updatePending = false;
          _hasUpdated = false;
          _resolveUpdate = null;
          _updatePromise = Promise.resolve(true);
          _rootEntry = null;
          _stylesAdopted = false;
  constructor() {
    super();
    this.renderRoot = this.attachShadow({ mode: "open" });
  }
  addController(controller) {
    this._controllers.add(controller);
    if (this.isConnected && controller.hostConnected) {
      controller.hostConnected();
    }
  }
  removeController(controller) {
    this._controllers.delete(controller);
  }
  connectedCallback() {
    this._adoptStylesOnce();
    for (const c of this._controllers) {
      c.hostConnected?.();
    }
    this.requestUpdate();
  }
  disconnectedCallback() {
    for (const c of this._controllers) {
      c.hostDisconnected?.();
    }
  }
  get updateComplete() {
    return this._updatePromise;
  }
  requestUpdate() {
    if (this._updatePending) return;
    this._updatePending = true;
    this._updatePromise = new Promise ((resolve) => {
      this._resolveUpdate = resolve;
    });
    queueMicrotask(() => this._performUpdate());
  }
          _adoptStylesOnce() {
    if (this._stylesAdopted) return;
    this._stylesAdopted = true;
    const ctor = this.constructor;
    if (!ctor.styles) return;
    const list = Array.isArray(ctor.styles) ? ctor.styles : [ctor.styles];
    if ("adoptedStyleSheets" in this.renderRoot && typeof CSSStyleSheet !== "undefined") {
      try {
        const sheets = list.map((s) => {
          const sheet = new CSSStyleSheet();
          sheet.replaceSync(s.styleSheetText);
          return sheet;
        });
        this.renderRoot.adoptedStyleSheets = sheets;
        return;
      } catch {
        // Fallback to <style> element below if constructable stylesheets are unavailable.
      }
    }
    for (const s of list) {
      const styleEl = document.createElement("style");
      styleEl.textContent = s.styleSheetText;
      this.renderRoot.appendChild(styleEl);
    }
  }
          _performUpdate() {
    this._updatePending = false;
    if (!this.isConnected) {
      this._resolveUpdate?.(false);
      this._resolveUpdate = null;
      return;
    }
    this._adoptStylesOnce();
    for (const c of this._controllers) {
      c.hostUpdate?.();
    }
    const rendered = this.render();
    if (isTemplateResult(rendered)) {
      if (this._rootEntry && this._rootEntry.strings === rendered.strings) {
        this._rootEntry.inst.update(rendered.values);
      } else {
        if (this._rootEntry) {
          this._rootEntry.inst.remove();
        }
        const entry = createInstance(rendered);
        entry.inst.mountBefore(this.renderRoot, null);
        entry.inst.update(rendered.values);
        this._rootEntry = entry;
      }
    }
    if (!this._hasUpdated) {
      this._hasUpdated = true;
      this.firstUpdated();
    }
    this.updated();
    for (const c of this._controllers) {
      c.hostUpdated?.();
    }
    this._resolveUpdate?.(true);
    this._resolveUpdate = null;
  }
            render() {
    return nothing;
  }
            firstUpdated() {}
            updated() {}
}

// --- src/mdi-catalog.ts ---
/**
 * Universal Shortcut Engine catalogs: domain action maps, route icon previews,
 * and firmware-verified Material Design Icons (`ui_mdi.cpp` 7,447-icon parity).
 */
const SHORTCUT_DOMAIN_ACTIONS
  = {
  light: [
    { action: "toggle", label: "Toggle" },
    { action: "turn_on", label: "Turn On" },
    { action: "turn_off", label: "Turn Off" },
  ],
  switch: [
    { action: "toggle", label: "Toggle" },
    { action: "turn_on", label: "Turn On" },
    { action: "turn_off", label: "Turn Off" },
  ],
  input_boolean: [
    { action: "toggle", label: "Toggle" },
    { action: "turn_on", label: "Turn On" },
    { action: "turn_off", label: "Turn Off" },
  ],
  fan: [
    { action: "toggle", label: "Toggle" },
    { action: "turn_on", label: "Turn On" },
    { action: "turn_off", label: "Turn Off" },
  ],
  cover: [
    { action: "toggle", label: "Toggle" },
    { action: "open_cover", label: "Open" },
    { action: "close_cover", label: "Close" },
    { action: "stop_cover", label: "Stop" },
  ],
  valve: [
    { action: "toggle", label: "Toggle" },
    { action: "open_valve", label: "Open" },
    { action: "close_valve", label: "Close" },
    { action: "stop_valve", label: "Stop" },
  ],
  scene: [{ action: "turn_on", label: "Activate" }],
  script: [
    { action: "turn_on", label: "Run" },
    { action: "turn_off", label: "Stop" },
  ],
  automation: [
    { action: "trigger", label: "Trigger" },
    { action: "toggle", label: "Toggle Enable" },
    { action: "turn_on", label: "Enable" },
    { action: "turn_off", label: "Disable" },
  ],
  button: [{ action: "press", label: "Press" }],
  input_button: [{ action: "press", label: "Press" }],
  lock: [
    { action: "lock", label: "Lock" },
    { action: "unlock", label: "Unlock" },
    { action: "open", label: "Unlatch" },
  ],
  alarm_control_panel: [
    { action: "disarm", label: "Disarm" },
    { action: "arm_home", label: "Arm Home" },
    { action: "arm_away", label: "Arm Away" },
    { action: "arm_night", label: "Arm Night" },
    { action: "arm_vacation", label: "Arm Vacation" },
  ],
  vacuum: [
    { action: "start", label: "Start" },
    { action: "pause", label: "Pause" },
    { action: "return_to_base", label: "Return To Base" },
    { action: "stop", label: "Stop" },
    { action: "clean_spot", label: "Spot Clean" },
    { action: "locate", label: "Locate" },
  ],
  lawn_mower: [
    { action: "start_mowing", label: "Start Mowing" },
    { action: "pause", label: "Pause" },
    { action: "dock", label: "Dock" },
  ],
  media_player: [
    { action: "media_play_pause", label: "Play / Pause" },
    { action: "turn_on", label: "Turn On" },
    { action: "turn_off", label: "Turn Off" },
    { action: "media_next_track", label: "Next Track" },
  ],
  climate: [
    { action: "turn_on", label: "Turn On" },
    { action: "turn_off", label: "Turn Off" },
  ],
  humidifier: [
    { action: "toggle", label: "Toggle" },
    { action: "turn_on", label: "Turn On" },
    { action: "turn_off", label: "Turn Off" },
  ],
  siren: [
    { action: "turn_on", label: "Turn On" },
    { action: "turn_off", label: "Turn Off" },
  ],
  water_heater: [
    { action: "turn_on", label: "Turn On" },
    { action: "turn_off", label: "Turn Off" },
  ],
  select: [
    { action: "select_next", label: "Next Option" },
    { action: "select_previous", label: "Previous Option" },
  ],
  input_select: [
    { action: "select_next", label: "Next Option" },
    { action: "select_previous", label: "Previous Option" },
  ],
};
const SHORTCUT_DOMAIN_LABELS = {
  alarm_control_panel: "Security Alarm",
  automation: "Automations",
  button: "Buttons",
  climate: "Climate",
  cover: "Covers & Blinds",
  fan: "Fans",
  humidifier: "Humidifiers",
  input_boolean: "Input Booleans",
  input_button: "Input Buttons",
  input_select: "Input Selects",
  lawn_mower: "Lawn Mowers",
  light: "Lights",
  lock: "Locks",
  media_player: "Media Players",
  scene: "Scenes",
  script: "Scripts",
  select: "Selects",
  siren: "Sirens",
  switch: "Switches",
  vacuum: "Vacuums",
  valve: "Valves",
  water_heater: "Water Heaters",
};
function shortcutActionLabel(domain, action) {
  const list = SHORTCUT_DOMAIN_ACTIONS[domain] || [];
  const found = list.find((it) => it.action === action);
  return found ? found.label : action;
}
const ROUTE_PREVIEW_ICONS = {
  "app:pinned": "mdi:pin",
  "app:music": "mdi:music",
  "music:speakers": "mdi:speaker-multiple",
  "music:library": "mdi:music-box-outline",
  "music:favorites": "mdi:heart",
  "music:playlists": "mdi:playlist-music",
  "music:queue": "mdi:playlist-play",
  "app:home_hub": "mdi:home",
  "home_hub:alarm": "mdi:shield-home",
  "home_hub:cameras": "mdi:cctv",
  "home_hub:intercom": "mdi:phone-in-talk",
  "home_hub:thermostat": "mdi:thermostat",
  "home_hub:entry": "mdi:lock",
  "home_hub:vacuum": "mdi:robot-vacuum",
  "app:area": "mdi:sofa",
  "area:picker": "mdi:floor-plan",
  "area:scene": "mdi:shimmer",
  "area:light": "mdi:lightbulb",
  "area:cover": "mdi:blinds-horizontal",
  "area:climate": "mdi:thermometer",
  "area:fan": "mdi:ceiling-fan",
  "area:switch": "mdi:toggle-switch",
  "area:media": "mdi:television-speaker",
  "area:all": "mdi:view-grid",
  "app:remote": "mdi:remote-tv",
  "remote:devices": "mdi:remote",
  "app:weather": "mdi:weather-partly-cloudy",
  "weather:current": "mdi:weather-partly-cloudy",
  "weather:forecast": "mdi:calendar-week",
  "weather:sun": "mdi:white-balance-sunny",
  "weather:moon": "mdi:moon-waning-crescent",
  "app:time": "mdi:clock-outline",
  "time:clock": "mdi:clock-outline",
  "time:timers": "mdi:timer-sand",
  "time:alarms": "mdi:alarm",
  "time:stopwatch": "mdi:timer-outline",
  "app:clock": "mdi:clock-outline",
  "app:tools": "mdi:apps",
  "tools:stopwatch": "mdi:timer-outline",
  "tools:level": "mdi:spirit-level",
  "tools:flashlight": "mdi:flashlight",
  "tools:calculator": "mdi:calculator-variant",
  "tools:calendar": "mdi:calendar",
  "tools:dice": "mdi:dice-5",
  "tools:coin_flip": "mdi:alpha-c-circle",
  "app:games": "mdi:gamepad-variant",
  "games:marbles": "mdi:billiards",
  "games:archery": "mdi:bullseye-arrow",
  "games:bricks": "mdi:wall",
  "games:chomp": "mdi:pac-man",
  "games:2048": "mdi:numeric-2-box-multiple",
  "games:memory": "mdi:cards",
  "settings:root": "mdi:cog",
  "settings:display": "mdi:brightness-6",
  "settings:sleep": "mdi:power-sleep",
  "settings:sound": "mdi:volume-high",
  "settings:voice": "mdi:microphone",
  "settings:music": "mdi:music-box-outline",
  "settings:home": "mdi:home-outline",
  "settings:actions": "mdi:gesture-tap-button",
  "settings:update": "mdi:cellphone-arrow-down",
  "settings:info": "mdi:information-outline",
};
const MDI_SLUG_PATTERN = /^mdi:[a-z0-9]+(?:-[a-z0-9]+)*$/;
const BARE_MDI_SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
function normalizeMdiIconSlug(raw) {
  let clean = String(raw ?? "").trim().toLowerCase().replace(/_/g, "-");
  if (!clean) return "";
  if (clean.startsWith("mdi-")) {
    clean = `mdi:${clean.slice(4)}`;
  } else if (!clean.startsWith("mdi:") && BARE_MDI_SLUG_PATTERN.test(clean)) {
    clean = `mdi:${clean}`;
  }
  return MDI_SLUG_PATTERN.test(clean) ? clean : "";
}
const CURATED_MDI_ICONS = [
  "mdi:pin",
  "mdi:pin-outline",
  "mdi:bell-ring",
  "mdi:bell",
  "mdi:bell-alert",
  "mdi:bullhorn",
  "mdi:lifebuoy",
  "mdi:alert-circle",
  "mdi:hand-wave",
  "mdi:baby-carriage",
  "mdi:baby-bottle-outline",
  "mdi:baby-face-outline",
  "mdi:cradle-outline",
  "mdi:human-male-female-child",
  "mdi:account-heart",
  "mdi:heart",
  "mdi:medical-bag",
  "mdi:phone-in-talk",
  "mdi:message-alert",
  "mdi:flash",
  "mdi:lightning-bolt",
  "mdi:star",
  "mdi:shimmer",
  "mdi:magic-staff",
  "mdi:check-circle",
  "mdi:lightbulb",
  "mdi:lightbulb-on",
  "mdi:lightbulb-outline",
  "mdi:lightbulb-group",
  "mdi:lamp",
  "mdi:desk-lamp",
  "mdi:floor-lamp",
  "mdi:ceiling-light",
  "mdi:chandelier",
  "mdi:coach-lamp",
  "mdi:outdoor-lamp",
  "mdi:wall-sconce",
  "mdi:led-strip-variant",
  "mdi:string-lights",
  "mdi:track-light",
  "mdi:lava-lamp",
  "mdi:candle",
  "mdi:fireplace",
  "mdi:brightness-6",
  "mdi:creation",
  "mdi:palette",
  "mdi:toggle-switch",
  "mdi:toggle-switch-off-outline",
  "mdi:power",
  "mdi:power-plug",
  "mdi:power-socket-us",
  "mdi:power-socket-eu",
  "mdi:light-switch",
  "mdi:battery-charging",
  "mdi:solar-power",
  "mdi:ev-station",
  "mdi:car-electric",
  "mdi:blinds-horizontal",
  "mdi:blinds-horizontal-closed",
  "mdi:blinds-open",
  "mdi:blinds-vertical",
  "mdi:curtains",
  "mdi:curtains-closed",
  "mdi:roller-shade",
  "mdi:roller-shade-closed",
  "mdi:window-shutter",
  "mdi:window-shutter-open",
  "mdi:window-open-variant",
  "mdi:window-closed-variant",
  "mdi:garage",
  "mdi:garage-open",
  "mdi:garage-variant",
  "mdi:garage-open-variant",
  "mdi:gate",
  "mdi:gate-open",
  "mdi:door",
  "mdi:door-open",
  "mdi:door-closed",
  "mdi:door-sliding",
  "mdi:awning-outline",
  "mdi:lock",
  "mdi:lock-open",
  "mdi:lock-smart",
  "mdi:key-variant",
  "mdi:shield-home",
  "mdi:shield-lock",
  "mdi:shield-check",
  "mdi:shield-moon",
  "mdi:shield-airplane",
  "mdi:security",
  "mdi:alarm-light",
  "mdi:cctv",
  "mdi:video",
  "mdi:webcam",
  "mdi:doorbell-video",
  "mdi:motion-sensor",
  "mdi:smoke-detector-variant",
  "mdi:thermostat",
  "mdi:thermometer",
  "mdi:fire",
  "mdi:snowflake",
  "mdi:sun-snowflake-variant",
  "mdi:fan",
  "mdi:ceiling-fan",
  "mdi:air-purifier",
  "mdi:air-humidifier",
  "mdi:water-percent",
  "mdi:water-boiler",
  "mdi:water",
  "mdi:water-pump",
  "mdi:pipe-valve",
  "mdi:sprinkler-variant",
  "mdi:faucet",
  "mdi:radiator",
  "mdi:hvac",
  "mdi:robot-vacuum",
  "mdi:robot-mower",
  "mdi:washing-machine",
  "mdi:tumble-dryer",
  "mdi:dishwasher",
  "mdi:fridge-outline",
  "mdi:stove",
  "mdi:coffee-maker",
  "mdi:kettle-steam",
  "mdi:music",
  "mdi:music-note",
  "mdi:playlist-music",
  "mdi:playlist-play",
  "mdi:radio",
  "mdi:podcast",
  "mdi:speaker",
  "mdi:speaker-multiple",
  "mdi:cast-audio",
  "mdi:television",
  "mdi:television-speaker",
  "mdi:remote",
  "mdi:remote-tv",
  "mdi:play-pause",
  "mdi:play",
  "mdi:pause",
  "mdi:skip-next",
  "mdi:volume-high",
  "mdi:volume-mute",
  "mdi:movie-open",
  "mdi:gamepad-variant",
  "mdi:headphones",
  "mdi:script-text-play",
  "mdi:script-text",
  "mdi:robot",
  "mdi:gesture-tap-button",
  "mdi:cog",
  "mdi:cog-play",
  "mdi:autorenew",
  "mdi:timer-play",
  "mdi:weather-night",
  "mdi:sleep",
  "mdi:bed",
  "mdi:coffee",
  "mdi:silverware-fork-knife",
  "mdi:party-popper",
  "mdi:airplane",
  "mdi:home-export-outline",
  "mdi:home-import-outline",
  "mdi:briefcase",
  "mdi:laptop",
  "mdi:book-open-variant",
  "mdi:meditation",
  "mdi:dumbbell",
  "mdi:home",
  "mdi:home-outline",
  "mdi:sofa",
  "mdi:bed-king-outline",
  "mdi:desk",
  "mdi:countertop-outline",
  "mdi:shower-head",
  "mdi:bathtub-outline",
  "mdi:stairs",
  "mdi:balcony",
  "mdi:flower",
  "mdi:tree",
  "mdi:pine-tree",
  "mdi:pool",
  "mdi:grill",
  "mdi:car",
  "mdi:bicycle",
  "mdi:dog",
  "mdi:cat",
  "mdi:paw",
  "mdi:weather-sunny",
  "mdi:weather-partly-cloudy",
  "mdi:weather-cloudy",
  "mdi:weather-rainy",
  "mdi:weather-pouring",
  "mdi:weather-snowy",
  "mdi:weather-lightning",
  "mdi:weather-windy",
  "mdi:white-balance-sunny",
  "mdi:moon-waning-crescent",
  "mdi:moon-full",
  "mdi:clock-outline",
  "mdi:alarm",
  "mdi:timer-sand",
  "mdi:timer-outline",
  "mdi:calendar",
  "mdi:calculator-variant",
  "mdi:flashlight",
  "mdi:spirit-level",
  "mdi:dice-5",
  "mdi:compass-outline",
  "mdi:map-marker",
  "mdi:apps",
  "mdi:view-grid",
  "mdi:form-select",
];
const MDI_TOTAL_ICON_COUNT = 7447;
// Front-coded Pictogrammers @mdi/js v7.4.47 catalog (exact 1:1 parity with firmware ui_mdi.cpp).
const PACKED_MDI_CHUNKS = [
  "0ab-testing|2acus|2jad-arabic|6hebrew|2ugida-devanagari|8thai|1ccess-point|c-check|dminus|dnetwork|k-off",
  "doff|dplus|dremove|3ount|7-alert|d-outline|9rrow-down|i-outline|eleft|i-outline|eright|j-outline|eup",
  "g-outline|8badge|d-outline|9ox|b-edit-outline|cminus-outline|dultiple|k-outline|coutline|cplus-outline",
  "8cancel|e-outline|ard|c-outline|ash|c-outline|9heck|d-outline|aild|d-circle|eoutline|9ircle|e-outline|9lock",
  "d-outline|9og|b-outline|anvert|f-outline|awboy-hat|i-outline|9redit-card|j-outline|8details|f-outline|8edit",
  "c-outline|9ye|b-outline|8file|c-outline|dtext|h-outline|bter|e-outline|8group|d-outline|8hard-hat|g-outline",
  "9eart|d-outline|8injury|e-outline|8key|b-outline|8lock|c-open|h-outline|eutline|8minus|d-outline|9ultiple",
  "g-check|m-outline|hminus|m-outline|houtline|hplus|l-outline|hremove|n-outline|asic|d-outline|8network|f-off",
  "j-outline|hutline|8off|b-outline|9utline|8plus|c-outline|8question|g-outline|8reactivate|i-outline|amove",
  "e-outline|8school|e-outline|9earch|e-outline|attings|g-outline|9tar|c-outline|9upervisor|i-circle|p-outline",
  "joutline|9witch|e-outline|9ync|c-outline|8tag|b-outline|9ie|b-hat|f-outline|coutline|cvoice|h-off|l-outline",
  "jutline|cwoman|8voice|d-off|8wrench|e-outline|1djust|2vertisements|e-off|1ir-conditioner|4filter|4horn",
  "5umidifier|e-off|4purifier|c-off|3bag|5lloon|a-outline|3plane|8-alert|9check|alock|aog|9edit|9landing",
  "9marker|ainus|9off|9plus|9remove|9search|bttings|9takeoff|4ort|1larm|5-bell|6check|6light|b-off|f-outline",
  "dutline|6multiple|6note|a-off|6off|6panel|b-outline|7lus|6snooze|2bum|2ert|5-box|9-outline|6circle|c-check",
  "i-outline|doutline|6decagram|e-outline|6minus|b-outline|6octagon|d-outline|bram|e-outline|7utline|6plus",
  "a-outline|6remove|c-outline|7hombus|d-outline|2ien|5-outline|3gn-horizontal-center|hdistribute|hleft|hright",
  "6vertical-bottom|fcenter|fdistribute|ftop|2l-inclusive|d-box|h-outline|3ergy|2pha|5-a|7-box|b-outline",
  "8circle|e-outline|6b|7-box|b-outline|8circle|e-outline|6c|7-box|b-outline|8circle|e-outline|6d|7-box",
  "b-outline|8circle|e-outline|6e|7-box|b-outline|8circle|e-outline|6f|7-box|b-outline|8circle|e-outline|6g",
  "7-box|b-outline|8circle|e-outline|6h|7-box|b-outline|8circle|e-outline|6i|7-box|b-outline|8circle|e-outline",
  "6j|7-box|b-outline|8circle|e-outline|6k|7-box|b-outline|8circle|e-outline|6l|7-box|b-outline|8circle",
  "e-outline|6m|7-box|b-outline|8circle|e-outline|6n|7-box|b-outline|8circle|e-outline|6o|7-box|b-outline",
  "8circle|e-outline|6p|7-box|b-outline|8circle|e-outline|6q|7-box|b-outline|8circle|e-outline|6r|7-box",
  "b-outline|8circle|e-outline|6s|7-box|b-outline|8circle|e-outline|6t|7-box|b-outline|8circle|e-outline|6u",
  "7-box|b-outline|8circle|e-outline|6v|7-box|b-outline|8circle|e-outline|6w|7-box|b-outline|8circle|e-outline",
  "6x|7-box|b-outline|8circle|e-outline|6y|7-box|b-outline|8circle|e-outline|6z|7-box|b-outline|8circle",
  "e-outline|5bet-aurebesh|9cyrillic|9greek|9latin|9piqad|9tengwar|8ical|c-off|dvariant|k-off|2timeter",
  "1mbulance|2munition|2persand|3lifier|9-off|1nchor|2droid|7-studio|2gle-acute|6obtuse|6right|3ular|7js",
  "2imation|9-outline|aplay|e-outline|2sible|2tenna|2vil|1pache-kafka|2i|3-off|2ple|5-finder|6icloud|7os",
  "6keyboard-caps|gommand|hntrol|foption|fshift|6safari|4ication|b-array|h-outline|cbraces|i-outline|gkets",
  "k-outline|ccog|f-outline|cedit|g-outline|dxport|cimport|coutline|cparentheses|n-outline|csettings|k-outline",
  "cvariable|k-outline|3roximately-equal|j-box|3s|4-box|1rch|4ive|7-alert|d-outline|9rrow-down|i-outline|eup",
  "g-outline|8cancel|e-outline|9heck|d-outline|9lock|d-outline|9og|b-outline|8edit|c-outline|9ye|b-outline",
  "8lock|c-open|h-outline|eutline|8marker|e-outline|9inus|d-outline|9usic|d-outline|8off|b-outline|9utline",
  "8plus|c-outline|8refresh|f-outline|amove|e-outline|8search|e-outline|attings|g-outline|9tar|c-outline|9ync",
  "c-outline|2m-flex|8-outline|2range-bring-forward|eto-front|8send-backward|dto-back|3ow-all|6bottom-left",
  "h-bold-box|q-outline|noutline|ithick|ln|m-circle-outline|dright|i-bold-box|r-outline|ooutline|jthick|mn",
  "n-circle-outline|6collapse|e-all|fdown|fhorizontal|fleft|fright|fup|fvertical|6decision|e-auto|j-outline",
  "foutline|7own|a-bold|f-box|j-outline|gcircle|m-outline|ghexagon-outline|goutline|dx|bcircle|h-outline",
  "bdrop-circle|m-outline|bleft|f-bold|bright|g-bold|bthick|en|f-circle-outline|6expand|c-all|ddown|dhorizontal",
  "dleft|dright|dup|dvertical|6horizontal-lock|6left|a-bold|f-box|j-outline|gcircle|m-outline|ghexagon-outline",
  "goutline|dttom|h-bold|dx|bcircle|h-outline|bdrop-circle|m-outline|bright|g-bold|l-outline|bthick|en",
  "f-circle-outline|cop|e-bold|6oscillating|h-off|6projectile|g-multiple|6right|b-bold|g-box|k-outline|hcircle",
  "n-outline|hhexagon-outline|houtline|ettom|i-bold|ex|ccircle|i-outline|cdrop-circle|n-outline|cthick|fn",
  "g-circle-outline|dop|f-bold|6split-horizontal|cvertical|6top-left|e-bold-box|n-outline|koutline|httom-right",
  "r-bold|fthick|in|j-circle-outline|aright|f-bold-box|o-outline|loutline|ittom-left|r-bold|gthick|jn",
  "k-circle-outline|6u-down-left|h-bold|dright|i-bold|8left-bottom|j-bold|dtop|g-bold|8right-bottom|k-bold|etop",
  "h-bold|8up-left|f-bold|bright|g-bold|7p|8-bold|d-box|h-outline|ecircle|k-outline|ehexagon-outline|eoutline",
  "bx|9circle|f-outline|9down|d-bold|i-outline|arop-circle|k-outline|9left|d-bold|9right|e-bold|9thick|cn",
  "d-circle-outline|6vertical-lock|2tboard|3station|1spect-ratio|2sistant|2terisk|8-circle-outline|1t|2lassian",
  "2m|2om|4-variant|2tachment|a-check|block|bminus|boff|bplus|bremove|2v|1udio-input-rca|cstereo-minijack|cxlr",
  "6video|b-off|2gmented-reality|2rora|2to-download|5fix|5mode|5upload|4renew|9-off|1v-timer|1wning|6-outline",
  "2s|1xe|3-battle|2is|4-arrow|a-info|block|5lock|5x-arrow|c-lock|7rotate-clockwise|founterclockwise",
  "7y-arrow-lock|5y-arrow|c-lock|7rotate-clockwise|founterclockwise|5z-arrow|c-lock|7rotate-clockwise",
  "founterclockwise|0babel|3y|4-bottle|b-outline|6uggy|a-off|5carriage|d-off|5face|9-outline|2ckburger|4space",
  "9-outline|areverse|h-outline|4up-restore|3teria|8-outline|2dge-account|d-alert|j-outline|ehorizontal",
  "o-outline|eoutline|3minton|2g-carry-on|c-check|doff|5hecked|4personal|c-off|g-outline|eutline|dplus",
  "h-outline|dtag|g-outline|4suitcase|c-off|g-outline|eutline|3uette|2lcony|3loon|5t|6-outline|7recount",
  "e-outline|2ndage|3k|4-check|6ircle|b-outline|5minus|5off|8-outline|6utline|5plus|5remove|5transfer|d-in|eout",
  "2rcode|7-off|8scan|3ley|6-off|3n|3rel|6-outline|2seball|8-bat|9diamond|g-outline|9outline|3h|3ket|6-check",
  "c-outline|7fill|7minus|c-outline|7off|a-outline|8utline|7plus|b-outline|7remove|d-outline|7unfill|6ball",
  "a-hoop|f-outline|2t|3htub|7-outline|3tery|7-10|a-bluetooth|820|a-bluetooth|830|a-bluetooth|840|a-bluetooth",
  "850|a-bluetooth|860|a-bluetooth|870|a-bluetooth|880|a-bluetooth|890|a-bluetooth|8alert|d-bluetooth|evariant",
  "l-outline|9rrow-down|i-outline|eup|g-outline|8bluetooth|h-variant|8charging|g-10|j0|h20|h30|h40|h50|h60|h70",
  "h80|h90|hhigh|hlow|hmedium|houtline|hwireless|p-10|q20|q30|q40|q50|q60|q70|q80|q90|qalert|qoutline|aeck",
  "d-outline|9lock|d-outline|8heart|d-outline|evariant|9igh|8lock|c-open|aw|8medium|9inus|d-outline|evariant",
  "8negative|8off|b-outline|9utline|8plus|c-outline|dvariant|9ositive|8remove|e-outline|8sync|c-outline",
  "8unknown|f-bluetooth|1each|3ker|6-alert|c-outline|7check|c-outline|7minus|c-outline|7outline|7plus|b-outline",
  "7question|f-outline|7remove|d-outline|2d|3-clock|4double|a-outline|4empty|4king|8-outline|4outline|4queen",
  "9-outline|4single|a-outline|2e|3-flower|3hive-off-outline|9utline|3keeper|3r|4-outline|2ll|4-alert|a-outline",
  "5badge|a-outline|5cancel|b-outline|6heck|a-outline|6ircle|b-outline|6og|8-outline|5minus|a-outline|5off",
  "8-outline|6utline|5plus|9-outline|5remove|b-outline|6ing|9-outline|5sleep|a-outline|2nch|5-back|2ta|4max",
  "1iathlon|2cycle|7-basket|8cargo|8electric|8penny-farthing|2ke|4-fast|5pedal|a-clipless|bmountain|2llboard",
  "4iards|9-rack|2noculars|2o|3hazard|2rd|2tbucket|3coin|1lack-mesa|2ender|7-outline|8software|2inds",
  "6-horizontal|h-closed|7open|7vertical|f-closed|2ock-helper|3od-bag|2uetooth|9-audio|aconnect|aoff|asettings",
  "atransfer|3r|4-linear|5off|5radial|1olt|2mb|4-off|2ne|4-off|2ok|4-account|c-outline|6lert|a-outline|7phabet",
  "6rrow-down|f-outline|bleft|f-outline|bright|g-outline|bup|d-outline|5cancel|b-outline|6heck|a-outline|6lock",
  "a-outline|6og|8-outline|6ross|5edit|9-outline|7ucation|e-outline|5heart|a-outline|5information-variant|5lock",
  "9-open|e-outline|butline|5marker|b-outline|6inus|a-multiple|j-outline|boutline|6ultiple|d-outline|7sic",
  "a-outline|5off|8-outline|6pen|9-blank-variant|n-outline|aoutline|apage-variant|m-outline|avariant|h-outline",
  "6utline|5play|9-outline|7us|9-multiple|i-outline|aoutline|5refresh|c-outline|7move|b-multiple|k-outline",
  "coutline|5search|b-outline|7ttings|d-outline|6ync|9-outline|5variant|4mark|8-box|c-multiple|l-outline",
  "doutline|9check|e-outline|9minus|e-outline|aultiple|h-outline|bsic|e-outline|9off|c-outline|autline|9plus",
  "d-outline|9remove|f-outline|4shelf|3m-gate|9-alert|f-outline|brrow-down|k-outline|gup|i-outline|aoutline|aup",
  "c-outline|4box|4erang|3tstrap|2rder-all|a-variant|7bottom|d-variant|7color|7horizontal|7inside|7left",
  "b-variant|7none|b-variant|7outside|7radius|8ight|c-variant|7style|7top|a-variant|7vertical|2ttle-soda",
  "b-classic|j-outline|coutline|7tonic|c-outline|dplus|h-outline|dskull|i-outline|7wine|b-outline|2w-arrow|4tie",
  "3l|4-mix|8-outline|5outline|4ing|2x|3-cutter|a-off|4shadow|3ing-glove|1raille|4n|2ead-slice|b-outline|2idge",
  "3efcase|9-account|h-outline|brrow-left-right|q-outline|gup-down|n-outline|acheck|f-outline|block|f-outline",
  "adownload|i-outline|aedit|e-outline|bye|d-outline|aminus|f-outline|aoff|d-outline|butline|aplus|e-outline",
  "aremove|g-outline|asearch|g-outline|aupload|g-outline|avariant|h-off|l-outline|jutline|3ghtness-1|b2|b3|b4",
  "b5|b6|b7|bauto|bpercent|2oadcast|9-off|3om|2ush|5-off|7utline|6variant|1ucket|6-outline|2ffet|2g|3-check",
  "9-outline|4outline|4pause|9-outline|5lay|8-outline|4stop|8-outline|3le|2lkhead-light|3ldozer|4et|6in-board",
  "4horn|8-outline|9variant|g-outline|4seye|8-arrow|3ma|2nk-bed|8-outline|2s|3-alert|5rticulated-end|gfront",
  "4clock|4double-decker|4electric|4marker|5ultiple|4school|5ide|6gn|5top|8-covered|9uncovered|4wrench|2tterfly",
  "9-outline|4on-cursor|7pointer|0cabin-a-frame|3le-data|2ched|3tus|2ke|4-layered|5variant|c-outline|2lculator",
  "a-variant|i-outline|3endar|8-account|g-outline|alert|e-outline|arrow-left|fright|9badge|e-outline|alank",
  "e-multiple|foutline|9check|e-outline|alock|e-outline|aollapse-horizontal|s-outline|aursor|f-outline|9edit",
  "d-outline|and|c-outline|axpand-horizontal|q-outline|cort|f-outline|9filter|f-outline|9heart|e-outline",
  "9import|f-outline|9lock|d-open|i-outline|futline|9minus|e-outline|aonth|e-outline|aultiple|h-check|eselect",
  "k-outline|9outline|9plus|d-outline|9question|h-outline|9range|e-outline|aefresh|g-outline|bmove|f-outline",
  "9search|f-outline|atar|d-four-points|eoutline|dt|e-outline|aync|d-outline|9text|d-outline|aoday|e-outline",
  "9week|d-begin|j-outline|eoutline|dend|g-outline|3l-made|6erge|6issed|5received|5split|2mcorder|9-off|3era",
  "6-account|7burst|7control|7document|f-off|7enhance|e-outline|7flip|b-outline|8ront|c-variant|7gopro|7image",
  "8ris|7lock|b-open|g-outline|dutline|7marker|d-outline|8etering-center|gmatrix|gpartial|gspot|7off|a-outline",
  "8utline|7party-mode|8lus|b-outline|7rear|b-variant|9take|d-outline|7switch|d-outline|7timer|7wireless",
  "f-outline|3pfire|2ncel|3delabra|a-fire|4le|4y|5-off|9-outline|7utline|5cane|3nabis|8-off|2ps-lock|2r",
  "3-2-plus|43-plus|4arrow-left|aright|4back|6ttery|5rake-abs|blert|afluid-level|ahold|alow-pressure|aparking",
  "aretarder|atemperature|aworn-linings|4child-seat|5lock|6utch|5og|6nnected|7vertible|6olant-level",
  "5ruise-control|4defrost-front|crear|5oor|8-lock|d-open|4electric|c-outline|5mergency|5sp|6tate|4hatchback",
  "4info|4key|4lifted-pickup|6ght-alert|adimmed|afog|ahigh|6mousine|4multiple|4off|5utline|4parking-lights",
  "5ickup|4search|a-outline|7t|8-cooler|9heater|6lect|6ttings|5hift-pattern|5ide|5peed-limiter|6orts",
  "4tire-alert|5raction-control|5urbocharger|4wash|5indshield|e-outline|6reless|5rench|3abiner|4van|3d",
  "4-account-details|k-outline|lstar|p-outline|dmail|h-outline|dphone|i-outline|5bulleted|d-off|h-outline",
  "futline|esettings|m-outline|5minus|a-outline|6ultiple|d-outline|5off|8-outline|6utline|5plus|9-outline",
  "5remove|b-outline|5search|b-outline|5text|9-outline|4s|5-club|a-outline|6diamond|d-outline|6heart|b-outline",
  "6outline|6playing|d-club|i-multiple|r-outline|joutline|ediamond|l-multiple|u-outline|moutline|eheart",
  "j-multiple|s-outline|koutline|eoutline|espade|j-multiple|s-outline|koutline|6spade|b-outline|6variant|3rot",
  "3t|4-arrow-down|bright|bup|5check|5heart|5minus|5off|6utline|5percent|6lus|5remove|5variant",
  "2se-sensitive-alt|3h|4-100|5check|6lock|5edit|5fast|5lock|9-open|5marker|6inus|6ultiple|5off|5plus|5refund",
  "7gister|7move|5sync|3sette|3t|4-audio|a-variant|5connected|5education|5off|5variant|4le|2t|1ctv|4-off",
  "1eiling-fan|b-light|8light|d-multiple|m-outline|eoutline|2llphone|9-arrow-down|k-variant|abasic|acharging",
  "ceck|bog|adock|ainformation|akey|alink|e-off|bock|amarker|bessage|h-off|anfc|d-off|aoff|aplay|aremove",
  "ascreenshot|bettings|bound|atext|awireless|2ntos|2rtificate|b-outline|1hair-rolling|6school|3ndelier|3rity",
  "7-search|4t-arc|8easpline|g-variant|6bar|9-stacked|7ell-curve|g-cumulative|7ox|9-multiple|i-outline|aoutline",
  "aplus-outline|7ubble|6donut|b-variant|6gantt|6histogram|6line|a-stacked|bvariant|6multiline|bple|6pie",
  "9-outline|7pf|6sankey|c-variant|7catter-plot|i-hexbin|6timeline|e-variant|m-shimmer|7ree|6waterfall|3t",
  "4-alert|a-outline|5minus|a-outline|5outline|5plus|9-outline|6rocessing|f-outline|5question|d-outline|5remove",
  "b-outline|5sleep|a-outline|2eck|5-all|6bold|6circle|c-outline|6decagram|e-outline|6network|d-outline",
  "6outline|6underline|f-circle|m-outline|5book|9-arrow-left|gright|7x-blank|e-badge|k-outline|fcircle",
  "l-outline|foff|i-outline|gutline|9intermediate|l-variant|9marked|f-circle|m-auto-outline|nminus-outline",
  "noutline|nplus-outline|goutline|aultiple-blank|n-circle|u-outline|ooutline|imarked|o-circle|v-outline",
  "poutline|ioutline|9outline|5erboard|c-minus|dplus|dremove|3ese|6-off|3f-hat|3mical-weapon|3ss-bishop|6king",
  "7night|6pawn|6queen|6rook|3vron-double-down|fleft|fright|fup|awn|c-box|g-outline|dcircle|j-outline|8left",
  "c-box|g-outline|dcircle|j-outline|8right|d-box|h-outline|ecircle|k-outline|8triple-down|fleft|fright|fup|8up",
  "a-box|e-outline|bcircle|h-outline|2ili-alert|b-outline|6hot|9-outline|6medium|c-outline|7ild|a-outline|6off",
  "9-outline|3p|2urch|6-outline|1igar|5-off|2rcle|6-box|a-outline|7double|7edit-outline|8xpand|7half|b-full",
  "7medium|8ultiple|f-outline|7off-outline|8pacity|8utline|7slice-1|d2|d3|d4|d5|d6|d7|d8|8mall|4ular-saw|2ty",
  "4-switch|5variant|c-outline|1lipboard|9-account|h-outline|blert|f-outline|brrow-down|k-outline|gleft",
  "k-outline|gright|l-outline|gup|i-outline|acheck|f-multiple|o-outline|goutline|block|f-outline|aedit",
  "e-outline|afile|e-outline|blow|e-outline|alist|e-outline|aminus|f-outline|bultiple|i-outline|aoff|d-outline",
  "butline|aplay|e-multiple|n-outline|foutline|cus|e-outline|bulse|f-outline|aremove|g-outline|asearch",
  "g-outline|atext|e-clock|k-outline|fmultiple|n-outline|foff|i-outline|gutline|fplay|j-outline|fsearch",
  "l-outline|4py|2ock|5-alert|b-outline|6check|b-outline|6digital|6edit|a-outline|7nd|6fast|6in|6minus",
  "b-outline|6out|9line|6plus|a-outline|6remove|c-outline|6star-four-points|m-outline|at|6time-eight|g-outline",
  "cleven|h-outline|bfive|f-outline|cour|f-outline|bnine|f-outline|bone|e-outline|bseven|g-outline|cix",
  "e-outline|bten|e-outline|chree|g-outline|cwelve|h-outline|do|e-outline|3se|5-box|9-multiple|i-outline",
  "aoutline|6circle|c-multiple|l-outline|doutline|6network|d-outline|6octagon|d-outline|7utline|6thick",
  "5d-caption|e-outline|3ud|5-alert|b-outline|7rrow-down|g-outline|cleft|g-outline|cright|h-outline|cup",
  "e-outline|6braces|6cancel|c-outline|7heck|b-outline|cvariant|j-outline|7ircle|c-outline|7lock|b-outline|7og",
  "9-outline|6download|e-outline|6key|9-outline|6lock|a-open|f-outline|cutline|6minus|b-outline|6off|9-outline",
  "7utline|6percent|d-outline|7lus|a-outline|7rint|b-outline|6question|e-outline|6refresh|d-outline|evariant",
  "l-outline|8move|c-outline|6search|c-outline|7ync|a-outline|6tags|6upload|c-outline|5s|3ver|6-outline",
  "1oach-lamp|a-variant|3t-rack|2de-array|5block-braces|fkets|bparentheses|btags|6races|b-box|9kets|5equal",
  "5greater-than|h-or-equal|5json|5less-than|e-or-equal|5not-equal|e-variant|5parentheses|g-box|5string|5tags",
  "9-check|4pen|2ffee|6-maker|c-check|i-outline|doutline|7off|a-outline|8utline|7to-go|c-outline|4in|2g|3-box",
  "4clockwise|5ounterclockwise|4off|7-outline|5utline|4pause|9-outline|5lay|8-outline|4refresh|b-outline|4stop",
  "8-outline|5ync|8-outline|4transfer|c-outline|3s|2llage|5pse-all|c-outline|3or-helper|2mma|5-box|9-outline",
  "6circle|c-outline|4ent|7-account|f-outline|9lert|d-outline|9rrow-left|i-outline|eright|j-outline|8bookmark",
  "g-outline|8check|d-outline|8edit|c-outline|9ye|b-outline|8flash|d-outline|8minus|d-outline|9ultiple",
  "g-outline|8off|b-outline|9utline|8plus|c-outline|9rocessing|i-outline|8question|g-outline|aote|d-outline",
  "8remove|e-outline|8search|e-outline|8text|c-multiple|l-outline|doutline|3pare|7-horizontal|8remove|8vertical",
  "5ss|7-off|b-outline|9utline|8rose|4ost|2ne|4-off|3nection|3sole|7-line|8network|f-outline|6idate",
  "3tactless-payment|j-circle|q-outline|7s|8-outline|5in|7-end|8start|4ent-copy|9ut|8duplicate|8paste|8save",
  "c-alert|i-outline|fl|g-outline|dcheck|i-outline|eog|g-outline|dedit|h-outline|dminus|i-outline|eove",
  "h-outline|doff|g-outline|eutline|dplus|h-outline|dsettings|l-outline|4rast|8-box|9circle|5oller|a-classic",
  "i-outline|boff|2okie|6-alert|c-outline|7check|c-outline|8lock|c-outline|8og|a-outline|7edit|b-outline|7lock",
  "b-outline|7minus|c-outline|7off|a-outline|8utline|7plus|b-outline|7refresh|e-outline|9move|d-outline",
  "7settings|f-outline|3lant-temperature|2pyleft|4right|2rdova|3n|4-off|2sine-wave|2unter|7top|a-outline|2w",
  "3-off|1pu-32-bit|464-bit|1radle|6-outline|3ne|2eation|8-outline|6ve-commons|3dit-card|b-check|h-outline|eip",
  "g-outline|dlock|h-outline|cedit|g-outline|cfast|g-outline|clock|g-outline|cmarker|i-outline|dinus|h-outline",
  "dultiple|k-outline|coff|f-outline|dutline|cplus|g-outline|crefresh|j-outline|fund|i-outline|emove|i-outline",
  "cscan|g-outline|dearch|i-outline|ettings|k-outline|dync|g-outline|cwireless|k-off|o-outline|mutline|2icket",
  "2op|4-free|5landscape|5portrait|5rotate|5square|3ss|5-bolnisi|6celtic|6outline|5hairs|a-gps|boff|bquestion",
  "3wd|4n|5-circle|c-outline|6outline|2yengine|3stal-ball|1ube|4-off|8-outline|6utline|5scan|6end|5unfolded|2p",
  "3-off|7-outline|5utline|4water|3board|8-outline|3cake|2rling|3rency-bdt|arl|atc|9cny|9eth|aur|c-off|9fra",
  "9gbp|9ils|anr|9jpy|9krw|azt|9mnt|9ngn|9php|9rial|aub|bpee|9sign|9thb|ary|awd|9uah|asd|c-off|6t-ac|8dc",
  "3sor-default|e-click|k-outline|fgesture|m-outline|foutline|7move|7pointer|7text|3tains|8-closed|1ylinder",
  "8-off|0dance-ballroom|6pole|2ta-matrix|b-edit|cminus|cplus|cremove|cscan|4base|8-alert|e-outline|arrow-down",
  "j-outline|fleft|j-outline|fright|k-outline|fup|h-outline|9check|e-outline|alock|e-outline|aog|c-outline",
  "9edit|d-outline|axport|f-outline|aye|c-off|g-outline|eutline|9import|f-outline|9lock|d-outline|9marker",
  "f-outline|ainus|e-outline|9off|c-outline|autline|9plus|d-outline|9refresh|g-outline|bmove|f-outline|9search",
  "f-outline|bttings|h-outline|aync|d-outline|1eath-star|a-variant|5ly-hallows|2bian|3ug-step-into|bout|cver",
  "2cagram|8-outline|3imal|7-comma|d-decrease|eincrease|8decrease|8increase|2lete|6-alert|c-outline|7circle",
  "d-outline|8lock|c-outline|7empty|c-outline|7forever|e-outline|7off|a-outline|8utline|7restore|7sweep",
  "c-outline|7variant|3ta|2sk|4-lamp|9-off|bn|4phone|4top-classic|8tower|d-monitor|2tails|2v-to|3eloper-board",
  "3iantart|4ces|1harmachakra|1iabetes|3lpad|3meter|8-outline|9variant|4ond|7-outline|8stone|3per-outline|2ce-1",
  "6-outline|52|6-outline|53|6-outline|54|6-outline|55|6-outline|56|6-outline|5d10|8-outline|72|8-outline|620",
  "8-outline|64|7-outline|66|7-outline|68|7-outline|5multiple|d-outline|2gital-ocean|2p-switch|2rections|a-fork",
  "2sc|4-alert|5player|3hwasher|a-alert|boff|3qus|3tribute-horizontal-center|mleft|mright|bvertical-bottom",
  "kcenter|ktop|2versify|3ing|6-flippers|7helmet|7scuba|c-flag|dmask|dtank|h-multiple|8norkel|4sion|8-box|1lna",
  "1na|2s|3-outline|1ock-bottom|5left|5right|5top|5window|4er|3tor|2g|3-service|5ide|8-off|2lby|3ly|3phin|2main",
  "6-off|7plus|7remove|7switch|3e-light|3ino-mask|2nkey|2or|4-closed|b-cancel|clock|5open|5sliding|c-lock|dopen",
  "4bell|8-video|2t-net|3s-circle|5grid|5hexagon|6orizontal|f-circle|m-outline|5square|5triangle|5vertical",
  "d-circle|k-outline|2wnload|8-box|c-outline|9circle|f-outline|9lock|d-outline|9multiple|h-outline|9network",
  "g-outline|9off|c-outline|autline|1rag|4-horizontal|f-variant|5variant|6ertical|d-variant|3ma-masks|3w|4-pen",
  "4ing|7-box|2esser|7-outline|2one|3pbox|2upal|1uck|2mbbell|3p-truck|0ear-hearing|b-loop|coff|3buds|7-off",
  "b-outline|9utline|3th|5-arrow-down|cleft|cright|cup|6box|9-minus|aoff|aplus|aremove|6minus|6off|6plus",
  "6remove|1gg|3-easter|4fried|4off|7-outline|5utline|1iffel-tower|2ght-track|1ject|5-circle|c-outline|6outline",
  "1lectric-switch|f-closed|6on-framework|3phant|3vation-decline|arise|6or|8-down|9passenger|i-off|m-outline",
  "kutline|9up|2lipse|7-outline|1mail|5-alert|b-outline|7rrow-left|g-outline|cright|h-outline|6box|6check",
  "b-outline|6edit|a-outline|6fast|a-outline|6heart-outline|6lock|a-outline|6mark-as-unread|7inus|b-outline",
  "7ultiple|e-outline|6newsletter|6off|9-outline|7pen|a-heart-outline|bmultiple|j-outline|boutline|7utline",
  "6plus|a-outline|6remove|c-outline|6seal|a-outline|9rch|c-outline|7ync|a-outline|6variant|2ber|3y|2oticon",
  "8-angry|e-outline|9confused|h-outline|bol|d-outline|ary|c-outline|9dead|d-outline|bvil|e-outline|9excited",
  "g-outline|9frown|e-outline|9happy|e-outline|9kiss|d-outline|9lol|c-outline|9minus|e-outline|9neutral",
  "g-outline|9outline|9plus|d-outline|aoop|d-outline|9remove|f-outline|9sad|c-outline|aick|d-outline|9tongue",
  "f-outline|9wink|d-outline|1ngine|6-off|a-outline|8utline|1psilon|1qual|5-box|5izer|9-outline|1raser",
  "6-variant|1scalator|9-box|adown|aup|2lint|1t|2hereum|5net|8-cable|e-off|9off|1v-plug-ccs-1|c2|9hademo|8tesla",
  "9ype-1|d2|3station|2ernote|1xcavator|3lamation|b-thick|2it-run|5to-app|2pand-all|a-outline|5sion-card",
  "e-variant|3onent|8-box|4rt|6-variant|1ye|3-arrow-left|e-outline|aright|f-outline|4check|9-outline|5ircle",
  "a-outline|5losed|4lock|8-open|d-outline|autline|4minus|9-outline|4off|7-outline|5utline|4plus|8-outline",
  "4refresh|b-outline|6move|a-outline|4settings|c-outline|3dropper|a-minus|boff|bplus|bremove|bvariant",
  "0face-agent|5man|8-outline|9profile|9shimmer|g-outline|7sk|9-outline|5recognition|5woman|a-outline|bprofile",
  "bshimmer|i-outline|4book|8-gaming|9messenger|9workplace|3tory|2mily-tree|2n|3-alert|5uto|4chevron-down|cup",
  "5lock|4minus|4off|4plus|4remove|4speed-1|a2|a3|2st-forward|c-10|e5|d30|d45|d5|d60|doutline|2ucet|6-variant",
  "2x|1eather|4ure-search|e-outline|2dora|2nce|5-electric|4ing|2rris-wheel|4y|1ile|4-account|c-outline|6lert",
  "a-outline|6rrow-left-right|l-outline|bup-down|i-outline|5cabinet|7d|8-box|7ncel|b-outline|6ertificate",
  "g-outline|6hart|a-check|g-outline|boutline|7eck|a-outline|6lock|a-outline|8ud|a-outline|6ode|9-outline|7g",
  "8-outline|7mpare|5delimited|e-outline|6ocument|d-alert|j-outline|frrow-right|p-outline|echeck|j-outline",
  "eedit|i-outline|eminus|j-outline|fultiple|m-outline|eoutline|eplus|i-outline|erefresh|l-outline|gmove",
  "k-outline|7wnload|d-outline|5edit|9-outline|6xcel|a-box|e-outline|boutline|7port|b-outline|6ye|8-outline",
  "5find|9-outline|5gif-box|5hidden|5image|a-marker|h-outline|cinus|g-outline|boutline|bplus|f-outline|bremove",
  "h-outline|7port|b-outline|5jpg-box|5key|8-outline|5link|9-outline|6ock|9-open|e-outline|butline|5marker",
  "b-outline|6inus|a-outline|6ove|9-outline|6ultiple|d-outline|7sic|a-outline|5outline|5pdf-box|6ercent",
  "c-outline|6hone|a-outline|6lus|9-outline|6ng-box|6owerpoint|f-box|j-outline|goutline|6resentation-box",
  "5question|d-outline|5refresh|c-outline|7move|b-outline|7place|c-outline|7store|c-outline|6otate-left",
  "g-outline|cright|h-outline|5search|b-outline|7nd|9-outline|7ttings|d-outline|6ign|6tar|9-four-points",
  "l-outline|aoutline|6wap|9-outline|6ync|9-outline|5table|a-box|e-multiple|n-outline|foutline|boutline|6ree",
  "9-outline|5undo|9-outline|6pload|b-outline|5video|a-outline|5word|9-box|d-outline|aoutline|5xml-box|3m",
  "4strip|9-box|d-multiple|aoff|3ter|6-check|c-outline|8og|a-outline|7menu|b-outline|8inus|c-outline|8ultiple",
  "f-outline|7off|a-outline|8utline|7plus|b-outline|7remove|d-outline|7settings|f-outline|7variant|e-minus",
  "fplus|fremove|2nance|3d-replace|3gerprint|b-off|2re|4-alert|5circle|5extinguisher|5hydrant|c-alert|doff|5off",
  "5station|5truck|4base|4fox|4place|9-off|4wire|5ork|8-off|2sh|4-off|4bowl|8-outline|2t-to-page|b-outline",
  "7screen|d-outline|1lag|4-checkered|5minus|a-outline|5off|8-outline|6utline|5plus|9-outline|5remove|b-outline",
  "5triangle|5variant|c-minus|i-outline|doff|g-outline|eutline|dplus|h-outline|dremove|j-outline|3re|3sh",
  "5-alert|b-outline|7uto|6off|9-outline|7utline|6red-eye|6triangle|e-outline|5light|a-off|4k|5-empty|b-minus",
  "h-outline|coff|f-outline|dutline|cplus|g-outline|cremove|i-outline|6minus|b-outline|6off|9-outline|7utline",
  "6plus|a-outline|6remove|c-outline|7ound-bottom|i-empty|o-outline|joutline|2eur-de-lis|2ip-horizontal",
  "5to-back|8front|5vertical|2oor-lamp|a-dual|f-outline|boutline|btorchiere|k-outline|lvariant|s-outline|6plan",
  "3ppy|6-variant|3wer|6-outline|7pollen|d-outline|9ppy|7tulip|c-outline|1ocus-auto|6field|b-horizontal",
  "cvertical|2lder|6-account|e-outline|8lert|c-outline|8rrow-down|h-outline|dleft|h-outline|iright|n-outline",
  "dright|i-outline|dup|f-down|k-outline|goutline|7cancel|d-outline|8heck|c-outline|8lock|c-outline|8og",
  "a-outline|7download|f-outline|7edit|b-outline|8ye|a-outline|7file|b-outline|7google-drive|7heart|c-outline",
  "8idden|8ome|b-outline|7image|8nformation|i-outline|7key|a-network|i-outline|boutline|7lock|b-open|g-outline",
  "dutline|7marker|d-outline|8inus|c-outline|8ove|b-outline|8ultiple|f-image|goutline|gplus|k-outline|9sic",
  "c-outline|7network|e-outline|7off|a-outline|8pen|b-outline|8utline|7play|b-outline|9us|b-outline|8ound",
  "c-outline|7question|f-outline|7refresh|e-outline|9move|d-outline|7search|d-outline|9ttings|f-outline|8tar",
  "b-multiple|k-outline|coutline|8wap|b-outline|8ync|b-outline|7table|c-outline|8ext|b-outline|7upload",
  "d-outline|7wrench|d-outline|7zip|a-outline|2nt-awesome|2od|4-apple|a-outline|5croissant|5drumstick|e-off",
  "i-outline|gutline|5fork-drink|5halal|6ot-dog|5kosher|5off|8-outline|6utline|5steak|a-off|5takeout-box",
  "g-outline|6urkey|5variant|c-off|3t-print|4ball|8-australian|9helmet|2rest|6-outline|3klift|3m-dropdown",
  "5select|5textarea|9box|c-lock|dpassword|4at-align-bottom|dcenter|djustify|dleft|dmiddle|dright|dtop",
  "8nnotation-minus|iplus|7bold|7clear|8olor-fill|dhighlight|dmarker-cancel|dtext|aumns|7float-center|dleft",
  "dnone|dright|8ont|b-size-decrease|hincrease|7header-1|e2|e3|e4|e5|e6|edecrease|eequal|eincrease|epound",
  "8orizontal-align-center|oleft|oright|7indent-decrease|eincrease|8talic|7letter-case|i-lower|jupper",
  "eends-with|ematches|espacing|l-variant|ftarts-with|8ine-height|cspacing|dtyle|cweight|9st-bulleted|k-square",
  "ltriangle|mype|ccheckbox|hs|cgroup|h-plus|cnumbered|k-rtl|ctext|7overline|7page-break|csplit|9int|9ragraph",
  "g-spacing|8ilcrow|e-arrow-left|lright|7quote-close|i-outline|dopen|h-outline|7rotate-90|7section|8ize",
  "8trikethrough|k-variant|8ubscript|9perscript|7text|b-rotation-angle-down|rup|ldown|p-vertical|lnone|lup",
  "lvertical|cvariant|j-outline|cwrapping-clip|loverflow|lwrap|bbox|8itle|7underline|g-wavy",
  "7vertical-align-bottom|mcenter|mtop|7wrap-inline|csquare|ctight|dop-bottom|3um|5-minus|b-outline|6outline",
  "6plus|a-outline|6remove|c-outline|3ward|7burger|2untain|8-pen|c-tip|1raction-one-half|2eebsd|3nch-fries",
  "3quently-asked-questions|2idge|6-alert|c-outline|7bottom|7industrial|h-alert|n-outline|ioff|l-outline",
  "jutline|7off|a-outline|8utline|7top|7variant|e-alert|k-outline|foff|i-outline|gutline|2uit-cherries|e-off",
  "7itrus|c-off|6grapes|c-outline|6pear|7ineapple|6watermelon|1uel|4-cell|2llscreen|a-exit|2nction|8-variant",
  "2rigana-horizontal|9vertical|2se|4-alert|5blade|5off|0gamepad|7-circle|e-down|fleft|foutline|fright|fup",
  "8down|8left|8outline|8right|9ound|d-down|eleft|eoutline|eright|eup|8square|e-outline|8up|8variant|f-outline",
  "3ma|2ntry-crane|2rage|6-alert|c-variant|7lock|7open|b-variant|7variant|e-lock|2s-burner|4cylinder|4station",
  "b-in-use|i-outline|coff|f-outline|dutline|2te|4-alert|6nd|6rrow-left|bright|5buffer|5nand|6or|7t|5open|6r",
  "5xnor|6or|3sby|2uge|5-empty|6full|6low|2vel|1ender-female|7male|b-female|i-variant|7non-binary|7transgender",
  "3erator-mobile|aportable|astationary|3too|2sture|7-double-tap|8pinch|8spread|9wipe|d-down|ehorizontal|eleft",
  "eright|eup|evertical|8tap|b-box|dutton|chold|9wo-double-tap|ctap|1host|5-off|9-outline|7utline|1ift|4-off",
  "8-outline|6pen|9-outline|6utline|2t|3hub|3lab|1lass-cocktail|e-off|6flute|7ragile|6mug|9-off|avariant|h-off",
  "6pint-outline|6stange|6tulip|6wine|5es|2obe-light|b-outline|6model|1mail|1nome|1o-kart|7-track|2g|2ld|3f",
  "4-cart|5tee|2ndola|2odreads|3gle|6-ads|8nalytics|8ssistant|7cardboard|8hrome|8ircles|e-communities|fextended",
  "fgroup|8lassroom|9oud|7downasaur|8rive|7earth|7fit|7glass|7hangouts|7keep|7lens|7maps|8y-business|7nearby",
  "7play|9us|8odcast|7spreadsheet|8treet-view|7translate|1radient-horizontal|9vertical|3in|3ph|5-outline|5ql",
  "3ss|3ve-stone|2ease-pencil|4ter-than|c-or-equal|3enhouse|2id|4-large|5off|3ll|5-outline|2oup|1uitar-acoustic",
  "7electric|7pick|b-outline|2y-fawkes-mask|1ymnastics|0hail|3r-dryer|a-outline|2lloween|2mburger|9-check",
  "aminus|aoff|aplus|aremove|3mer|6-screwdriver|8ickle|7wrench|2nd-back-left|e-off|i-outline|gutline|aright",
  "f-off|j-outline|hutline|5clap|9-off|6oin|9-outline|6ycle|5extended|d-outline|5front-left|f-outline|bright",
  "g-outline|5heart|a-outline|5okay|5peace|a-variant|6ointing-down|eleft|eright|eup|5saw|5wash|9-outline|7ter",
  "7ve|9-outline|4ball|4cuffs|4s-pray|5hake|9-outline|3ger|2rd-hat|4disk|8-plus|9remove|2t-fedora|2zard-lights",
  "1dmi-port|2r|3-off|1ead|4-alert|a-outline|5check|a-outline|6og|8-outline|5dots-horizontal|k-outline|5flash",
  "a-outline|5heart|a-outline|5lightbulb|e-outline|5minus|a-outline|5outline|5plus|9-outline|5question",
  "d-outline|5remove|b-outline|5snowflake|e-outline|6ync|9-outline|4phones|a-bluetooth|cox|boff|bsettings|4set",
  "7-dock|8off|3rt|5-box|9-outline|7roken|c-outline|6circle|c-outline|7og|9-outline|6flash|6half|a-full",
  "boutline|6minus|b-outline|7ultiple|e-outline|6off|9-outline|7utline|6plus|a-outline|7ulse|6remove|c-outline",
  "6search|8ttings|e-outline|3t-pump|9-outline|5wave|4ing-coil|2licopter|3p|4-box|8-multiple|h-outline|9outline",
  "5circle|b-outline|5network|c-outline|5rhombus|c-outline|2xadecimal|4gon|7-multiple|g-outline|8outline",
  "8slice-1|e2|e3|e4|e5|e6|5ram|8-outline|1igh-definition|f-box|4way|2king|2story|1ockey-puck|7sticks|2lolens",
  "2me|4-account|6lert|a-outline|6nalytics|6ssistant|6utomation|5battery|c-outline|5circle|b-outline|7ty",
  "9-outline|6lock|a-outline|5edit|9-outline|6xport-outline|5flood|9r-0|b1|b2|b3|ba|bb|bg|bl|bnegative-1|5group",
  "a-minus|bplus|bremove|5heart|5import-outline|5lightbulb|e-outline|aning-bolt|j-outline|6ock|9-open",
  "5map-marker|6inus|a-outline|6odern|5off|8-outline|6utline|5percent|c-outline|6lus|9-outline|5remove",
  "b-outline|6oof|5search|b-outline|6ilo|9-outline|6ound-in|d-outline|bout|e-outline|6witch|b-outline",
  "5thermometer|g-outline|5variant|c-outline|2ok|4-off|3p-house|2ps|2rizontal-rotate-clockwise|jounterclockwise",
  "3se|5-human|6variant|d-fast|5shoe|2spital|8-box|c-outline|auilding|9marker|2t-tub|2urs-12|624|1ub|3-outline",
  "3spot|2lu|2man|5-baby-changing-table|6cane|8pacity-decrease|fincrease|7hild|6dolly|6edit|6female|c-boy",
  "ddance|dfemale|j-child|dgirl|6greeting|e-proximity|fvariant|6handsdown|bup|6male|a-board|g-poll|dy|bchild",
  "bfemale|h-child|bgirl|bheight|h-variant|bmale|f-child|6non-binary|6pregnant|6queue|6scooter|6walker",
  "7heelchair|8ite-cane|3ble-bundle|1vac|4-off|1ydraulic-oil-level|etemperature|4o-power|5gen-station",
  "0ice-cream|9-off|4pop|1d-card|2entifier|3ogram-cjk|c-variant|1mage|5-album|7rea|a-close|7uto-adjust|6broken",
  "c-variant|6check|b-outline|6edit|a-outline|6filter-black-white|dcenter-focus|p-strong|w-outline|qweak|ddrama",
  "i-outline|dframes|dhdr|g-outline|dnone|dtilt-shift|dvintage|7rame|6lock|a-outline|6marker|c-outline|7inus",
  "b-outline|7ove|7ultiple|e-outline|6off|9-outline|7utline|6plus|a-outline|6refresh|d-outline|8move|c-outline",
  "6search|c-outline|7ize-select-actual|ilarge|ismall|7ync|a-outline|6text|2port|1nbox|5-arrow-down|g-outline",
  "cup|e-outline|6full|a-outline|6multiple|e-outline|6outline|6remove|c-outline|2cognito|9-circle|g-off|aoff",
  "2duction|2finity|3ormation|b-box|f-outline|coff|f-outline|dutline|cslab-box|k-outline|hcircle|n-outline",
  "hsymbol|dymbol|cvariant|j-box|n-outline|kcircle|q-outline|2stagram|4rument-triangle|2tegrated-circuit-chip",
  "2vert-colors|d-off|3oice|7-arrow-left|i-outline|eright|j-outline|8check|d-outline|9lock|d-outline|8edit",
  "c-outline|9xport-outline|8fast|c-outline|8import|e-outline|8list|c-outline|8minus|d-outline|9ultiple",
  "g-outline|8outline|8plus|c-outline|8remove|e-outline|8send|c-outline|8text|c-arrow-left|n-outline|jright",
  "o-outline|dcheck|i-outline|elock|i-outline|dedit|h-outline|dfast|h-outline|dminus|i-outline|eultiple",
  "l-outline|doutline|dplus|h-outline|dremove|j-outline|dsend|h-outline|1obroker|1p|2-network|a-outline",
  "3outline|2od|1ron|4-board|5outline|1sland|6-variant|1v-bag|0jabber|1eepney|2llyfish|9-outline|1ira|1query",
  "1sfiddle|1ump-rope|0kabaddi|2ngaroo|2rate|2yaking|1eg|2ttle|6-alert|c-outline|7off|a-outline|8utline",
  "7pour-over|7steam|c-outline|6bell|2y|3-alert|9-outline|5rrow-right|4chain|9-variant|7nge|4link|4minus",
  "4outline|4plus|4remove|4star|4variant|4wireless|3board|8-backspace|9caps|alose|e-outline|9esc|9f1|b0|b1|b2",
  "a2|a3|a4|a5|a6|a7|a8|a9|9off|c-outline|autline|9return|9settings|h-outline|apace|9tab|c-reverse|9variant",
  "1handa|1ickstarter|2te|4-outline|4surfing|1lingon|1nife|5-military|2ob|1oala|2di|1ubernetes|0label",
  "5-multiple|e-outline|6off|9-outline|7utline|6percent|d-outline|6variant|d-outline|2dder|3ybug|2mbda|3p",
  "4-outline|4s|5-outline|2n|3-check|5onnect|4disconnect|4pending|3d-fields|5plots|a-circle|h-variant|bmarker",
  "5rows-horizontal|avertical|4slide|9-outline|3guage-c|app|asharp|bs-3|9fortran|9go|9haskell|atml-5|9java",
  "dscript|9kotlin|9lua|9markdown|h-outline|9php|aython|9r|auby|d-on-rails|bst|9swift|9typescript|9xaml|2ptop",
  "6-account|7off|2ravel|2ser-pointer|3so|3tpass|2titude|2unch|2va-lamp|2yers|6-edit|7minus|7off|a-outline",
  "8utline|7plus|7remove|7search|d-outline|7triple|d-outline|1ead-pencil|3f|4-circle|b-outline|5maple|a-off",
  "5off|3k|4-off|2ctern|2d-off|5n|5utline|4strip|9-variant|h-off|4variant-off|dn|dutline|2ek|2ss-than",
  "9-or-equal|1ibrary|7-outline|8shelves|2cense|2febuoy|2ght-flood-down|cup|6recessed|6switch|c-off|5bulb",
  "9-alert|f-outline|buto|e-outline|acfl|d-off|espiral|k-off|afluorescent-tube|q-outline|agroup|f-off|j-outline",
  "hutline|amultiple|i-off|m-outline|kutline|anight|f-outline|aoff|d-outline|bn|c-10|d20|d30|d40|d50|d60|d70",
  "d80|d90|doutline|butline|aquestion|i-outline|aspot|e-off|avariant|h-outline|5house|a-on|5ning-bolt|e-circle",
  "foutline|2ne-scan|3gerie|3k|4-box|8-outline|9variant|g-outline|5circle|b-outline|5edit|5lock|5off|5plus",
  "5variant|c-minus|doff|dplus|dremove|4edin|3ux|5-mint|2pstick|2quid-spot|4or|2st-box|8-outline|5status",
  "2tecoin|1oading|2cation-enter|axit|3k|4-alert|a-outline|5check|a-outline|6lock|5minus|a-outline|5off",
  "8-outline|6pen|9-alert|f-outline|acheck|f-outline|aminus|f-outline|aoutline|aplus|e-outline|aremove",
  "g-outline|avariant|h-outline|6utline|5pattern|6ercent|c-open|h-outline|ivariant|p-outline|eutline|6lus",
  "9-outline|5question|5remove|b-outline|7set|5smart|4er|6-multiple|2gin|5-variant|3out|6-variant|2ngitude|2oks",
  "2tion|6-outline|7plus|b-outline|2upe|1umx|2ngs|0mace|2gazine-pistol|9rifle|3ic-staff|3net|6-on|4ify|7-close",
  "8expand|8minus|d-cursor|eoutline|8plus|c-cursor|doutline|8remove-cursor|foutline|8scan|2il|4box|7-open",
  "c-outline|dup|f-outline|9utline|8up|a-outline|2njaro|2p|3-check|9-outline|5lock|9-outline|4legend|4marker",
  "a-account|i-outline|clert|g-outline|bcheck|g-outline|circle|bdistance|cown|bleft|f-outline|bminus|g-outline",
  "cultiple|j-outline|boff|e-outline|cutline|bpath|clus|f-outline|bquestion|j-outline|bradius|h-outline|cemove",
  "h-outline|ivariant|cight|g-outline|bstar|f-outline|bup|5inus|4outline|4plus|4search|a-outline|3box|2rgin",
  "3ker|6-cancel|8heck|2stodon|2terial-design|9ui|3h-compass|7s|5integral|d-box|5log|5norm|9-box|5sin|5tan|3rix",
  "1edal|5-outline|3ical-bag|8cotton-swab|6tion|a-outline|4tation|2mory|6-arrow-down|2norah|7-fire|3u|4-close",
  "5down|9-outline|5left|9-outline|5open|5right|a-outline|5swap|9-outline|5up|7-outline|2rge|2ssage|7-alert",
  "d-outline|9rrow-left|i-outline|eright|j-outline|8badge|d-outline|9ookmark|g-outline|9ulleted|g-off|8check",
  "d-outline|9og|b-outline|8draw|8fast|c-outline|9lash|d-outline|8image|d-outline|8lock|c-outline|8minus",
  "d-outline|8off|b-outline|9utline|8plus|c-outline|9rocessing|i-outline|8question|g-outline|8reply|d-outline",
  "etext|i-outline|8settings|g-outline|9tar|c-outline|8text|c-clock|i-outline|dfast|h-outline|dlock|h-outline",
  "doutline|8video|2teor|4r-electric|e-outline|6gas|9-outline|3ronome|9-tick|1icro-sd|5phone|a-message|i-off",
  "cinus|boff|cutline|bplus|bquestion|j-outline|bsettings|bvariant|i-off|5scope|6oft|9-access|bzure|f-devops",
  "abing|adynamics-365|aedge|bxcel|ainternet-explorer|aoffice|bnedrive|dnote|butlook|apowerpoint|asharepoint",
  "ateams|avisual-studio|n-code|awindows|h-classic|bord|axbox|e-controller|p-battery-alert|ycharging|yempty",
  "yfull|ylow|ymedium|yunknown|qmenu|qoff|qview|5wave|9-off|2ddleware|a-outline|3i|4-port|2ne|4craft|3i-sd",
  "4disc|3us|5-box|9-multiple|i-outline|aoutline|6circle|c-multiple|l-outline|doff|g-outline|eutline|6network",
  "d-outline|6thick|2rror|6-rectangle|7variant|2xed-martial-arts|6reality|1olecule|8-co|b-2|2nitor|7-account",
  "9rrow-down|i-variant|8cellphone|h-star|8dashboard|8edit|9ye|8lock|8multiple|8off|8screenshot|9hare|aimmer",
  "9mall|9peaker|f-off|9tar|8vertical|2on-first-quarter|6ull|5last-quarter|5new|5waning-crescent|cgibbous",
  "7xing-crescent|cgibbous|2ped|5-electric|e-outline|6outline|2re|3tar-pestle|d-plus|2sque|6-outline",
  "2ther-heart|7nurse|3ion|6-outline|7pause|c-outline|8lay|b-outline|7sensor|d-off|3orbike|9-electric|aoff|2use",
  "5-bluetooth|6left-click|g-outline|6move-down|bup|bvertical|6off|7utline|6right-click|h-outline|6scroll-wheel",
  "6variant|d-off|2ve-resize|b-variant|3ie|5-check|b-outline|7og|9-outline|6edit|a-outline|6filter|c-outline",
  "6minus|b-outline|6off|9-outline|7pen|a-check|g-outline|cog|e-outline|bedit|f-outline|bminus|g-outline|boff",
  "e-outline|cutline|bplay|f-outline|dus|f-outline|bremove|h-outline|bsettings|j-outline|ctar|f-outline|7utline",
  "6play|a-outline|8us|a-outline|6remove|c-outline|7oll|6search|c-outline|8ttings|e-outline|7tar|a-outline|2wer",
  "5-bag|9-on|6on|1uffin|2lticast|5media|5plication|e-box|2shroom|8-off|c-outline|autline|3ic",
  "5-accidental-double-flat|osharp|hflat|hnatural|hsharp|6box|9-multiple|i-outline|aoutline|6circle|c-outline",
  "7lef-alto|bbass|btreble|6note|a-bluetooth|k-off|beighth|h-dotted|bhalf|f-dotted|bminus|boff|e-outline",
  "cutline|bplus|bquarter|i-dotted|bsixteenth|k-dotted|bwhole|g-dotted|6off|6rest-eighth|bhalf|bquarter",
  "bsixteenth|bwhole|3tache|0nail|2s|2tivescript|3ure|6-outline|7people|d-outline|2vigation|a-outline|bvariant",
  "i-outline|1ear-me|2cklace|2edle|6-off|2tflix|3work|7-off|b-outline|9utline|8pos|8strength-1|i-alert|h2",
  "i-alert|h3|i-alert|h4|i-alert|jcog|hoff|k-outline|iutline|2w-box|3spaper|9-check|aminus|aplus|aremove",
  "avariant|h-multiple|q-outline|ioutline|1fc|3-search-variant|4tap|4variant|b-off|1inja|3tendo-game-boy",
  "9switch|9wii|cu|2x|1odejs|2odles|2t-equal|9-variant|3e|4-alert|a-outline|5check|a-outline|5edit|9-outline",
  "5minus|a-outline|6ultiple|d-outline|5off|8-outline|6utline|5plus|9-outline|5remove|b-outline|5search",
  "b-outline|5text|9-outline|4book|8-check|e-outline|9edit|d-outline|9heart|e-outline|9minus|e-outline|aultiple",
  "9outline|9plus|d-outline|9remove|f-outline|3ification-clear-all|1pm|1uke|2ll|2meric|7-0|9-box|d-multiple",
  "m-outline|eoutline|acircle|g-outline|81|9-box|d-multiple|m-outline|eoutline|acircle|g-outline|90|a-box",
  "e-multiple|n-outline|foutline|bcircle|h-outline|82|9-box|d-multiple|m-outline|eoutline|acircle|g-outline|83",
  "9-box|d-multiple|m-outline|eoutline|acircle|g-outline|84|9-box|d-multiple|m-outline|eoutline|acircle",
  "g-outline|85|9-box|d-multiple|m-outline|eoutline|acircle|g-outline|86|9-box|d-multiple|m-outline|eoutline",
  "acircle|g-outline|87|9-box|d-multiple|m-outline|eoutline|acircle|g-outline|88|9-box|d-multiple|m-outline",
  "eoutline|acircle|g-outline|89|9-box|d-multiple|m-outline|eoutline|acircle|g-outline|aplus|e-box|i-multiple",
  "r-outline|joutline|fcircle|l-outline|8negative-1|8off|8positive-1|2t|3rition|2xt|0oar|1carina|2i|2r|2tagon",
  "7-outline|5ram|8-edit|d-outline|9minus|e-outline|9outline|9plus|d-outline|4hedron|a-off|1dnoklassniki|1ffer",
  "3ice-building|f-cog|j-outline|gmarker|m-outline|hinus|l-outline|goutline|gplus|k-outline|gremove|m-outline",
  "1il|3-lamp|5evel|4temperature|1m|2ega|1ne-up|3password|1pacity|2en-in-app|8new|5source-initiative|4id|3ra",
  "1rbit|5-variant|2der-alphabetical-ascending|jdescending|6bool-ascending|k-variant|bdescending|l-variant",
  "6numeric-ascending|edescending|2igin|2nament|8-variant|1utdoor-lamp|1verscan|1wl|0pac-man|3kage|7-check",
  "8down|8up|8variant|f-closed|m-check|nminus|nplus|nremove|gminus|gplus|gremove|2ge-first|5last|7yout-body",
  "cfooter|cheader|i-footer|csidebar-left|kright|5next|9-outline|5previous|d-outline|2il|4-minus|a-outline|5off",
  "8-outline|6utline|5plus|9-outline|5remove|b-outline|2lette|7-advanced|8outline|8swatch|e-outline|fvariant",
  "3m-tree|2n|3-bottom-left|bright|4down|4horizontal|4left|4right|4top-left|8right|4up|4vertical|3da|4ora",
  "3orama|8-fisheye|9horizontal|j-outline|9outline|9sphere|f-outline|9variant|g-outline|aertical|h-outline",
  "9wide-angle|j-outline|2per-cut-vertical|6roll|a-outline|5clip|9-check|alock|aminus|aoff|aplus|aremove",
  "2rachute|9-outline|4gliding|3king|3ty-popper|2ssport|8-alert|9biometric|9cancel|aheck|9minus|9plus|9remove",
  "3ta|2tio-heater|3reon|2use|5-box|9-outline|6circle|c-outline|6octagon|d-outline|2w|3-off|7-outline|5utline",
  "1eace|3nut|6-off|a-outline|8utline|2n|3-lock|4minus|4off|4plus|4remove|3cil|6-box|a-multiple|j-outline",
  "boutline|7circle|d-outline|7lock|b-outline|7minus|c-outline|7off|a-outline|8utline|7plus|b-outline|7remove",
  "d-outline|8uler|c-outline|3guin|3tagon|8-outline|6ram|2rcent|7-box|b-outline|8circle|e-outline|8outline",
  "3iodic-table|3spective-less|cmore|1h|2one|5-alert|b-outline|6bluetooth|f-outline|6cancel|c-outline|7heck",
  "b-outline|7lassic|d-off|8ock|6dial|a-outline|6forward|d-outline|6hangup|c-outline|6in-talk|d-outline|8coming",
  "e-outgoing|n-outline|iline|6lock|a-outline|8g|9-outline|6message|d-outline|7inus|b-outline|8ssed|c-outline",
  "6off|9-outline|7utgoing|e-outline|9line|6paused|c-outline|7lus|a-outline|6refresh|d-outline|8move|c-outline",
  "8turn|c-outline|7ing|a-outline|7otate-landscape|dportrait|6settings|e-outline|7ync|a-outline|6voip|1i|2-box",
  "3hole|2ano|5-off|2ckaxe|3ture-in-picture-bottom-right|v-outline|jtop-right|s-outline|2er|4-crane|2g",
  "3-variant|b-outline|3gy-bank|a-outline|2ll|4-multiple|5off|4ar|2n|3-off|7-outline|5utline|3e-tree|9-box",
  "afire|avariant|h-outline|3terest|3wheel|8-outline|2pe|4-disconnected|5leak|5valve|5wrench|2rate|2stol|5n",
  "2tchfork|2zza|1lane-car|6train|3y|4-box|8-edit-outline|9lock|d-open|i-outline|futline|9multiple|h-outline",
  "9outline|5circle|b-outline|5network|c-outline|5outline|5pause|6rotected-content|5speed|4list-check|9edit",
  "9minus|ausic|e-outline|9play|bus|9remove|9star|2ex|2iers|2us|4-box|8-multiple|h-outline|9outline|5circle",
  "b-multiple|k-outline|coutline|5lock|9-open|5minus|a-box|bvariant|5network|c-outline|5outline|5thick|1ocket",
  "2dcast|3ium|6-bronze|7gold|7silver|2int-of-sale|2keball|4mon-go|4r-chip|2laroid|3ice-badge|c-outline",
  "7station|3l|3o|3ymer|2ol|4-thermometer|2pcorn|2st|4-lamp|5outline|4age-stamp|2t|3-mix|7-outline|4outline",
  "4steam|9-outline|2und|5-box|9-outline|2wer|5-cycle|6off|7n|6plug|a-battery|i-outline|boff|e-outline|cutline",
  "6settings|7leep|7ocket|c-au|dch|dde|deu|dfr|dit|djp|duk|es|7tandby|5shell|1rescription|4entation|c-play",
  "3tzel|2inter|7-3d|a-nozzle|h-alert|n-outline|iheat|m-outline|ioff|l-outline|jutline|boff|8alert|8check|8eye",
  "8off|b-outline|9utline|8pos|b-alert|h-outline|ccancel|i-outline|dheck|h-outline|dog|f-outline|cedit",
  "g-outline|cminus|h-outline|cnetwork|j-outline|coff|f-outline|dutline|cpause|h-outline|dlay|g-outline|eus",
  "g-outline|crefresh|j-outline|emove|i-outline|cstar|g-outline|eop|g-outline|dync|g-outline|cwrench|i-outline",
  "8search|attings|8wireless|3ority-high|9low|2ofessional-hexagon|3gress-alert|9check|alock|cse|9download",
  "9helper|9pencil|9question|9star|d-four-points|9tag|9upload|9wrench|3jector|9-off|ascreen|g-off|k-outline",
  "iutline|hvariant|o-off|s-outline|qutline|3pane-tank|c-outline|3tocol|1ublish|7-off|2lse|2mp|4-off|4kin|2rse",
  "5-outline|2zzle|6-check|c-outline|7edit|b-outline|7heart|c-outline|7minus|c-outline|7outline|7plus|b-outline",
  "7remove|d-outline|7star|b-outline|1yramid|7-off|0qi|1qchat|1rcode|6-edit|7minus|7plus|7remove|7scan",
  "1uadcopter|3lity-high|8low|8medium|2eue-first-in-last-out|2ora|0rabbit|6-variant|e-outline|2cing-helmet",
  "3quetball|2dar|3iator|8-disabled|9off|4o|5-am|6fm|6handheld|6off|6tower|5active|b-circle|i-outline|coff",
  "5box-blank|9indeterminate-variant|9marked|5logy-box|d-outline|4us|6-outline|2ilroad-light|2ke|2spberry-pi|2w",
  "3-off|2y-end|7-arrow|4start|9-arrow|aend|avertex-end|4vertex|2zor-double-edge|6single-edge|1eact|3d|2ceipt",
  "7-clock|d-outline|8outline|8send|c-outline|8text|c-arrow-left|n-outline|jright|o-outline|dcheck|i-outline",
  "elock|i-outline|dedit|h-outline|dminus|i-outline|doutline|dplus|h-outline|dremove|j-outline|dsend|h-outline",
  "3ord|6-circle|d-outline|7player|7rec|3tangle|9-outline|3ycle|7-variant|2ddit|3hat|3o|4-variant",
  "2flect-horizontal|8vertical|3resh|7-auto|8circle|2gex|3istered-trademark|2iterate|2lation-many-to-many|hone",
  "k-or-many|jly-one|hzero-or-many|pone|9one-or-many-to-many|oone|r-or-many|qly-one|ozero-or-many|wone|dto-many",
  "gone|j-or-many|ily-one|gzero-or-many|oone|bly-one-to-many|lone|o-or-many|nly-one|lzero-or-many|tone",
  "9zero-or-many-to-many|pone|s-or-many|rly-one|pzero-or-many|xone|hone-to-many|oone|r-or-many|qly-one",
  "ozero-or-many|wone|6ve-scale|3oad|6-alert|2minder|3ote|6-desktop|7off|7tv|9-off|2name|6-box|a-outline",
  "7outline|2order-horizontal|8vertical|2peat|6-off|8nce|7variant|3lay|4y|5-all|9-outline|6circle|6outline",
  "3roduction|2sistor|8-nodes|4ze|6-bottom-right|3ponsive|3tart|7-alert|8off|4ore|7-alert|2wind|6-10|85|730|745",
  "75|760|7outline|1hombus|7-medium|e-outline|8outline|8split|d-outline|1ibbon|2ce|3kshaw|8-electric|2ng|2vet",
  "1oad|4-variant|2bber|3ot|5-angry|b-outline|6confused|e-outline|6dead|a-outline|6excited|d-outline|6happy",
  "b-outline|6industrial|g-outline|6love|a-outline|6mower|b-outline|6off|9-outline|7utline|6vacuum|c-alert|doff",
  "dvariant|k-alert|loff|2cket|6-launch|d-outline|7outline|2dent|2ller-shade|c-closed|8kate|c-off|6blade|b-off",
  "4upjs|3odex|7-outline|2man-numeral-1|f0|e2|e3|e4|e5|e6|e7|e8|e9|2om-service|c-outline|2tate-360|8d|9-variant",
  "7left|b-variant|7orbit|7right|c-variant|2unded-corner|3ter|6-network|e-wireless|7wireless|f-off|gsettings|5s",
  "6-clock|2wing|1ss|3-box|4off|1ug|3by|2ler|5-square|c-compass|2n|3-fast|1v-truck|0sack|4-outline|5percent|2fe",
  "4-square|b-outline|4ty-goggles|2il-boat|9-sink|2le|4-outline|4sforce|2ss|2tellite|9-uplink|avariant|2usage",
  "7-off|2w-blade|3tooth-wave|2xophone|1cale|5-balance|8throom|6off|6unbalanced|3n-helper|4ner|7-off|3tter-plot",
  "c-outline|2ent|5-off|2hool|6-outline|2issors-cutting|2ooter|7-electric|3reboard|a-outline|2reen-rotation",
  "f-lock|4w-flat-top|6lag|6machine-flat-top|eround-top|6round-top|5driver|3ipt|6-outline|7text|b-key|f-outline",
  "coutline|cplay|g-outline|1d|1eal|4-variant|3rch-web|3t|4-flat|9-angled|5individual-suite|5legroom-extra",
  "dnormal|dreduced|5outline|5passenger|5recline-extra|dnormal|4belt|2curity|8-network|2ed|4-off|8-outline",
  "6utline|5plus|9-outline|3saw|2gment|2lect|6-all|8rrow-down|dup|7color|9mpare|7drag|7group|7inverse|7marker",
  "8ultiple|f-marker|7off|7place|7remove|7search|6ion|9-drag|aellipse|h-arrow-inside|iremove|amarker|bultiple",
  "i-marker|aoff|aremove|asearch|2mantic-web|2nd|4-check|a-outline|6ircle|b-outline|6lock|a-outline|5lock",
  "9-outline|5outline|5variant|c-clock|i-outline|doutline|2rial-port|3ver|6-minus|c-outline|7network|e-off",
  "gutline|7off|8utline|7plus|b-outline|7remove|7security|2t-all|4center|a-right|4left|8-center|9right|4merge",
  "4none|4right|4split|5quare|4top-box|3tings-helper|1haker|6-outline|3pe|5-circle-plus|6outline|7val-plus",
  "6plus|a-outline|7olygon-plus|6rectangle-plus|6square-plus|drounded-plus|3re|5-all|9-outline|6circle|6off",
  "9-outline|7utline|6variant|d-outline|4k|5-fin|9-outline|6off|2eep|2ield|6-account|e-outline|fvariant",
  "m-outline|8irplane|f-outline|8lert|c-outline|7bug|a-outline|7car|8heck|c-outline|8ross|c-outline|awn",
  "c-outline|7edit|b-outline|7half|b-full|8ome|b-outline|7key|a-outline|7link-variant|j-outline|8ock|b-open",
  "g-outline|dutline|7moon|b-outline|7off|a-outline|8utline|7plus|b-outline|7refresh|e-outline|9move|d-outline",
  "7search|8tar|b-outline|8un|a-outline|8word|c-outline|8ync|b-outline|3mmer|3p-wheel|4ping-pallet|2oe-ballet",
  "5cleat|5formal|5heel|5print|5sneaker|3pping|8-music|9outline|9search|f-outline|3re|3vel|6-off|3wer|6-head",
  "2redder|2uffle|7-disabled|8variant|3riken|1ickle|2gma|5-lower|3n-caution|5direction|e-minus|fplus|fremove",
  "5language|d-outline|5pole|5real-estate|5text|5yield|4al|6-2g|73g|74g|75g|7cellular-1|g2|g3|goutline",
  "7distance-variant|7hspa|b-plus|7off|7variant|5ture|9-freehand|aimage|atext|2lo|4-outline|3verware|a-clean",
  "bfork|f-knife|bspoon|bvariant|2m|3-alert|9-outline|4off|7-outline|5utline|3ple-icons|2na-weibo|3e-wave",
  "2temap|7-outline|2ze-l|5m|5s|5xl|6s|6xl|7s|7xl|1kate|5-off|5board|aing|2ew-less|5more|2i|3-cross-country",
  "4water|3p-backward|d-outline|5forward|c-outline|5next|9-circle|g-outline|aoutline|5previous|d-circle",
  "k-outline|eoutline|2ull|5-crossbones|g-outline|6outline|6scan|a-outline|2ype|5-business|1lack|3sh-forward",
  "d-box|2edding|3ep|5-off|2ide|2ope-downhill|6uphill|3t-machine|c-outline|1mart-card|a-off|e-outline|cutline",
  "breader|h-outline|2og|3ke|5-detector|e-alert|k-outline|foff|i-outline|gutline|fvariant|m-alert|noff|4ing",
  "7-off|8pipe|c-off|1nail|3ke|3pchat|2owboard|4flake|9-alert|acheck|amelt|aoff|athermometer|avariant|4man",
  "5obile|4shoeing|1occer|6-field|3ial-distance-2-meters|g6-feet|2fa|4-outline|5single|b-outline|2lar-panel",
  "b-large|7ower|b-variant|j-outline|3dering-iron|3id|2ny-playstation|2rt|4-alphabetical-ascending|r-variant",
  "idescending|s-variant|ivariant|6scending|5bool-ascending|j-variant|adescending|k-variant|5calendar-ascending",
  "edescending|6lock-ascending|k-outline|bdescending|l-outline|5descending|5numeric-ascending|m-variant",
  "ddescending|n-variant|dvariant|5reverse-variant|5variant|c-lock|h-open|doff|dremove|2undbar|5cloud",
  "3rce-branch|d-check|eminus|eplus|erefresh|gmove|esync|7commit|d-end|h-local|elocal|enext-local|estart",
  "j-next-local|7fork|7merge|7pull|7repository|h-multiple|2y-sauce|9-off|1pa|3-outline|3ce-invaders|6station",
  "3de|2eaker|7-bluetooth|8message|9ultiple|8off|8pause|9lay|8stop|8wireless|4r|3edometer|b-medium|cslow",
  "3llcheck|2here|6-off|2ider|6-outline|7thread|7web|3rit-level|2oon-sugar|3tify|4light|9-beam|2ray|5-bottle",
  "3inkler|9-fire|avariant|3out|6-outline|1quare|6-circle|d-outline|7edit-outline|7medium|d-outline|7off",
  "a-outline|8pacity|8utline|7root|b-box|9unded|e-badge|k-outline|foutline|7small|7wave|3eegee|1sh",
  "1tack-exchange|6overflow|5path|3dium|7-outline|8variant|3irs|6-box|7down|7up|3mper|3ndard-definition|3r",
  "4-box|8-multiple|h-outline|9outline|5check|a-outline|6ircle|b-outline|6og|8-outline|6rescent|5david|5face",
  "6our-points|g-box|k-outline|hcircle|n-outline|houtline|hsmall|5half|9-full|5minus|a-outline|5off|8-outline",
  "6utline|5plus|9-outline|5remove|b-outline|5settings|d-outline|6hooting|d-outline|5three-points|h-outline",
  "3te-machine|2eam|3ering|8-off|3p-backward|d-2|5forward|c-2|3thoscope|2icker|7-alert|d-outline|8check",
  "d-outline|9ircle-outline|8emoji|8minus|d-outline|8outline|8plus|c-outline|8remove|e-outline|8text|c-outline",
  "2ocking|3mach|3ol|5-outline|3p|4-circle|b-outline|3rage-tank|c-outline|4e|5-24-hour|6alert|b-outline|6check",
  "b-outline|7lock|b-outline|7og|9-outline|6edit|a-outline|6marker|c-outline|7inus|b-outline|6off|9-outline",
  "7utline|6plus|a-outline|6remove|c-outline|6search|c-outline|8ttings|e-outline|5front|a-check|g-outline|bedit",
  "f-outline|bminus|g-outline|boutline|bplus|f-outline|bremove|h-outline|3ve|2rategy|3etch-to-page|f-outline",
  "3ing-lights|d-off|1ubdirectory-arrow-left|jright|3marine|3titles|9-outline|3way|6-alert-variant|7variant",
  "2mmit|2n-angle|9-outline|4clock|9-outline|5ompass|4snowflake|d-variant|4thermometer|f-outline|4wireless",
  "c-outline|3glasses|2rfing|3round-sound|e-20|g1|f31|f51|h2|f71|1vg|1wap-horizontal|f-bold|gcircle|m-outline",
  "ghidden|gvariant|5vertical|d-bold|ecircle|k-outline|evariant|2im|3tch|2ord|5-cross|1yllabary-hangul|biragana",
  "akatakana|i-halfwidth|2mbol|3fony|2nagogue|9-outline|3c|4-alert|5circle|5off|0tab|3-minus|4plus|4remove",
  "4search|4unselected|3le|5-account|7lert|7rrow-down|cleft|cright|cup|6border|6cancel|7hair|8eck|7lock|7og",
  "8lumn|c-plus-after|ibefore|dremove|dwidth|6edit|7ye|9-off|6filter|7urniture|6headers-eye|h-off|9rt|6key",
  "6large|b-plus|cremove|7ock|6merge-cells|7inus|7ultiple|6network|6of-contents|8f|6picnic|8vot|7lus|6question",
  "6refresh|8move|7ow|9-height|aplus-after|fbefore|aremove|6search|8ttings|7plit-cell|7tar|7ync|6tennis|5t",
  "6-cellphone|7dashboard|2co|2g|3-arrow-down|e-outline|aleft|e-outline|aright|f-outline|aup|c-outline|4check",
  "9-outline|4edit|8-outline|4faces|4heart|9-outline|5idden|4minus|9-outline|5ultiple|c-outline|4off|7-outline",
  "5utline|4plus|8-outline|4remove|a-outline|4search|a-outline|4text|8-outline|2ilwind|2lly-mark-1|b2|b3|b4|b5",
  "2ngram|3k|4er-truck|2pe-drive|5measure|2rget|6-account|7variant|2xi|1ea|3-outline|3mviewer|2ddy-bear",
  "2lescope|4vision|a-ambient-light|bbox|bclassic|i-off|bguide|boff|bpause|clay|bshimmer|cpeaker|i-off|ctop",
  "2mperature-celsius|cfahrenheit|ckelvin|4le-buddhist|f-outline|7hindu|c-outline|2nnis|6-ball|b-outline|3t",
  "2rraform|5in|2st-tube|9-empty|aoff|2xt|4-account|5box|8-check|e-outline|9edit|d-outline|9minus|e-outline",
  "aultiple|h-outline|9outline|9plus|d-outline|9remove|f-outline|9search|f-outline|5long|5recognition|5search",
  "b-variant|6hadow|7ort|4ure|7-box|1heater|3me-light-dark|3rmometer|b-alert|duto|cbluetooth|ccheck|fvron-down",
  "kup|chigh|clines|dow|cminus|coff|cplus|drobe|h-off|cwater|6stat|a-auto|bbox|e-auto|bcog|2ought-bubble",
  "e-outline|2umb-down|a-outline|6up|8-outline|5s-up-down|e-outline|1icket|6-account|7confirmation|j-outline",
  "7outline|7percent|e-outline|2e|2lde|5-off|2melapse|5ine|8-alert|e-outline|9check|e-outline|alock|e-outline",
  "9minus|e-outline|9outline|9plus|d-outline|9question|h-outline|9remove|f-outline|9text|d-outline|4r|5-10|63",
  "6alert|b-outline|6cancel|c-outline|7heck|b-outline|7og|9-outline|6edit|a-outline|6lock|a-open|f-outline",
  "cutline|6marker|c-outline|7inus|b-outline|7usic|b-outline|6off|9-outline|7utline|6pause|b-outline|7lay",
  "a-outline|8us|a-outline|6refresh|d-outline|8move|c-outline|6sand|a-complete|bempty|bfull|bpaused|7ettings",
  "e-outline|7tar|a-outline|8op|a-outline|7ync|a-outline|4table|2re|1oaster|7-off|9ven|2ggle-switch|d-off",
  "h-outline|futline|evariant|l-off|2ilet|2olbox|7-outline|4s|4tip|7-account|8cellphone|9heck|d-outline|8edit",
  "c-outline|8image|d-outline|8minus|d-outline|8outline|8plus|c-outline|8question|g-outline|8remove|e-outline",
  "8text|c-outline|3th|5-outline|5brush|a-electric|bpaste|2rch|3toise|2slink|2uch-text-outline|3rnament",
  "2w-truck|3er-beach|6fire|3n-hall|2y-brick|9-marker|g-outline|binus|f-outline|aoutline|aplus|e-outline",
  "aremove|g-outline|asearch|g-outline|1rack-light|b-off|5pad|8-lock|4tor|7-variant|3demark|3ffic-cone|8light",
  "d-outline|3in|5-bus|6car|9-autorack|abox|d-full|eopen|acaboose|benterbeam|k-full|bontainer|aflatbed|h-car",
  "itank|agondola|h-full|ahopper|g-covered|hfull|aintermodal|apassenger|j-door|o-open|kvariant|atank|6variant",
  "3m|4-side|3nscribe|a-close|5fer|8-down|9left|9right|9up|5it-connection|i-horizontal|jvariant|8detour|8skip",
  "8transfer|7ion|a-masked|5late|9-off|avariant|5mission-tower|i-export|jimport|joff|3sh-can|9-outline|3y",
  "4-alert|6rrow-down|bup|5full|5minus|5plus|5remove|2easure-chest|e-outline|3e|4-outline|3llo|3nding-down",
  "9neutral|9up|2iangle|8-down|d-outline|9outline|9small-down|fup|9wave|3force|2ophy|6-award|7broken|7outline",
  "7variant|e-outline|2uck|5-alert|b-outline|6cargo-container|7heck|b-outline|6delivery|e-outline|6fast",
  "a-outline|7latbed|6minus|b-outline|6off-road|e-off|7utline|6plus|a-outline|6remove|c-outline|6snowflake",
  "6trailer|3mpet|1shirt-crew|b-outline|7v|8-outline|2unami|1umble-dryer|c-alert|doff|2ne|4-variant|6ertical",
  "d-variant|3nel|6-outline|2rbine|3key|3nstile|9-outline|3tle|1witch|4ter|2o-factor-authentication|1ypewriter",
  "0ubisoft|2untu|1fo|3-outline|1ltra-high-definition|1mbraco|4ella|8-beach|e-outline|9closed|f-outline",
  "gvariant|9outline|1nderwear-outline|3o|4-variant|2fold-less-horizontal|cvertical|7more-horizontal|cvertical",
  "2group|2icode|5rn|7-variant|4ycle|3ty|2real|1pdate|2load|6-box|a-outline|7circle|d-outline|7lock|b-outline",
  "7multiple|f-outline|7network|e-outline|7off|a-outline|8utline|1sb|3-c-port|4flash-drive|f-outline|4port",
  "0vacuum|6-outline|2lve|5-closed|6open|2n-passenger|4utility|3ish|6-quarter|4ty-light|2riable|8-box",
  "1ector-arrange-above|fbelow|7bezier|7circle|d-variant|8ombine|8urve|7difference|h-ab|iba|7ellipse",
  "7intersection|7line|ak|7point|c-edit|dminus|dplus|dselect|9lygon|e-variant|bline|f-edit|gminus|gplus|gremove",
  "7radius|8ectangle|7selection|8quare|d-close|eedit|eminus|eopen|eplus|eremove|7triangle|7union|1hs|1ibrate",
  "7-off|2deo|5-2d|63d|8-off|9variant|64k-box|6account|6box|9-off|6check|b-outline|6high-definition|6image",
  "7nput-antenna|ccomponent|chdmi|cscart|dvideo|6marker|c-outline|7inus|b-outline|6off|9-outline|7utline|6plus",
  "a-outline|6stabilization|9ndard-definition|7witch|c-outline|6vintage|6wireless|e-outline|2ew-agenda",
  "b-outline|6rray|a-outline|5carousel|d-outline|6olumn|b-outline|7mfy|a-outline|8pact|c-outline|5dashboard",
  "e-edit|j-outline|foutline|fvariant|m-outline|7y|8-outline|5gallery|c-outline|6rid|9-compact|aoutline|aplus",
  "e-outline|5headline|5list|9-outline|5module|b-outline|5parallel|d-outline|5quilt|a-outline|5sequential",
  "f-outline|6plit-horizontal|bvertical|6tream|b-outline|5week|9-outline|2meo|2olin|2rtual-reality|3us|5-off",
  "9-outline|7utline|1lc|1oicemail|2lcano|7-outline|3leyball|3ume-equal|7high|7low|7medium|8inus|8ute|7off",
  "7plus|7source|7variant-off|8ibrate|2te|4-outline|1pn|1uejs|3tify|0walk|3l|4-fire|5sconce|b-flat|g-outline",
  "hvariant|o-outline|coutline|cround|h-outline|ivariant|p-outline|4et|6-bifold|d-outline|7giftcard|7membership",
  "7outline|7plus|b-outline|7travel|4paper|2n|2rdrobe|8-outline|3ehouse|2shing-machine|f-alert|goff|2tch",
  "5-export|c-variant|6import|c-variant|6variant|7ibrate|d-off|3er|5-alert|b-outline|6boiler|c-alert|euto|doff",
  "6check|b-outline|7ircle|6minus|b-outline|6off|9-outline|7pacity|7utline|6percent|d-alert|7lus|a-outline|7olo",
  "7ump|a-off|6remove|c-outline|6sync|6thermometer|h-outline|6well|a-outline|5fall|5ing-can|c-outline|5mark|2ve",
  "4-arrow-down|bup|5undercurrent|4form|4s|5-arrow-left|cright|cup|2ze|1eather-cloudy|e-alert|grrow-right",
  "fclock|8dust|8fog|8hail|azy|9urricane|h-outline|8lightning|h-rainy|8moonset|f-down|gup|8night",
  "d-partly-cloudy|8partly-cloudy|flightning|frainy|fsnowy|k-rainy|9ouring|8rainy|8snowy|d-heavy|erainy|9unny",
  "d-alert|eoff|bset|e-down|fup|8tornado|8windy|d-variant|2b|3-box|4cancel|5heck|5lock|4minus|4off|4plus",
  "4refresh|6move|4sync|3cam|6-off|3hook|3pack|3rtc|2chat|2ight|6-gram|7kilogram|7lifter|7pound|1hatsapp",
  "2eel-barrow|5chair|a-accessibility|2istle|7-outline|3te-balance-auto|eincandescent|fridescent|esunny|1idgets",
  "7-outline|2fi|4-alert|6rrow-down|bleft|f-right|bright|bup|d-down|5cancel|6heck|6og|5lock|9-open|5marker",
  "6inus|5off|5plus|5refresh|7move|5settings|6tar|7rength-1|f-alert|glock|k-open|e2|f-alert|glock|k-open|e3",
  "f-alert|glock|k-open|e4|f-alert|glock|k-open|ealert-outline|elock-open-outline|kutline|eoff|h-outline",
  "futline|6ync|2kipedia|2nd-power|a-outline|5turbine|c-alert|dcheck|4ow-close|cd|d-variant|7maximize|8inimize",
  "7open|b-variant|7restore|7shutter|e-alert|guto|fcog|fopen|fsettings|4sock|2per|5-wash|a-alert|2zard-hat",
  "1ordpress|1rap|4-disabled|2ench|6-check|c-outline|8lock|c-outline|8og|a-outline|7outline|0xamarin|1ml|2pp",
  "0yahoo|1east|1in-yang|1oga|2utube|7-gaming|8studio|9ubscription|8tv|1urt|0z-wave|1end|1igbee|2p-box",
  "7-outline|4disk|1odiac-aquarius|8ries|7cancer|9pricorn|7gemini|7leo|8ibra|7pisces|7sagittarius|8corpio",
  "7taurus|7virgo",
];
let cachedAllMdiIcons = null;
let cachedAllMdiSet = null;
function getAllMdiIcons() {
  if (cachedAllMdiIcons !== null) {
    return cachedAllMdiIcons;
  }
  const out = [];
  let prev = "";
  for (const chunk of PACKED_MDI_CHUNKS) {
    for (const token of chunk.split("|")) {
      if (!token) continue;
      const shared = parseInt(token[0], 36);
      const slug = prev.slice(0, shared) + token.slice(1);
      prev = slug;
      out.push(`mdi:${slug}`);
    }
  }
  cachedAllMdiIcons = out;
  return out;
}
function isKnownMdiIcon(icon) {
  const norm = normalizeMdiIconSlug(icon);
  if (!norm) return false;
  if (cachedAllMdiSet === null) {
    cachedAllMdiSet = new Set(getAllMdiIcons());
  }
  return cachedAllMdiSet.has(norm);
}
function searchMdiIcons(
  rawQuery,
  limit = 120,
) {
  const cleaned = String(rawQuery || "")
    .trim()
    .toLowerCase()
    .replace(/^mdi[-:]/, "")
    .replace(/[_\s]+/g, "-");
  const tokens = cleaned.split("-").filter(Boolean);
  if (tokens.length === 0) {
    return {
      items: CURATED_MDI_ICONS.slice(0, limit),
      totalMatches: MDI_TOTAL_ICON_COUNT,
    };
  }
  const exactNeedle = tokens.join("-");
  const ranked = [];
  for (const fullSlug of getAllMdiIcons()) {
    const name = fullSlug.slice(4);
    let allFound = true;
    for (const tok of tokens) {
      if (!name.includes(tok)) {
        allFound = false;
        break;
      }
    }
    if (!allFound) continue;
    let rank = 3;
    if (name === exactNeedle) {
      rank = 0;
    } else if (name.startsWith(exactNeedle)) {
      rank = 1;
    } else if (name.includes(`-${tokens[0]}`) || name.startsWith(tokens[0])) {
      rank = 2;
    }
    ranked.push({ slug: fullSlug, rank });
  }
  ranked.sort((a, b) => a.rank - b.rank || a.slug.localeCompare(b.slug));
  return {
    items: ranked.slice(0, limit).map((r) => r.slug),
    totalMatches: ranked.length,
  };
}

// --- src/utils/format.ts ---
/**
 * Locale-aware formatters, Title Case entity label converter (D-013), and color helpers.
 * Note: Avoid literal `#RRGGBB` color constants here so `[STUDIO TOKENS]` stays 100% pure.
 */
function hassLanguage(hass) {
  return String(hass?.locale?.language || hass?.language || navigator.language || "en");
}
function fmtNumber(
  value,
  hass,
  maximumFractionDigits = 1,
) {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  try {
    return new Intl.NumberFormat(hassLanguage(hass), { maximumFractionDigits }).format(num);
  } catch {
    return String(num);
  }
}
function fmtPercent(
  value,
  hass,
) {
  if (value === null || value === undefined || value === "") return "—";
  const num = Number(value);
  if (!Number.isFinite(num)) return String(value);
  try {
    return new Intl.NumberFormat(hassLanguage(hass), {
      style: "percent",
      maximumFractionDigits: 0,
    }).format(num / 100);
  } catch {
    return `${Math.round(num)}%`;
  }
}
function fmtDistance(
  meters,
  hass,
  feet,
) {
  const isImperial = hass?.config?.unit_system?.length === "mi";
  if (isImperial) {
    const hasFeet = feet !== null && feet !== undefined && Number.isFinite(Number(feet));
    const hasMeters = meters !== null && meters !== undefined && Number.isFinite(Number(meters));
    if (!hasFeet && !hasMeters) return "—";
    const ft = hasFeet ? Number(feet) : Number(meters) * 3.28084;
    try {
      return new Intl.NumberFormat(hassLanguage(hass), {
        style: "unit",
        unit: "foot",
        maximumFractionDigits: 1,
      }).format(ft);
    } catch {
      return `${ft.toFixed(1)} ft`;
    }
  }
  if (meters === null || meters === undefined || !Number.isFinite(Number(meters))) return "—";
  const m = Number(meters);
  try {
    return new Intl.NumberFormat(hassLanguage(hass), {
      style: "unit",
      unit: "meter",
      maximumFractionDigits: 1,
    }).format(m);
  } catch {
    return `${m.toFixed(1)} m`;
  }
}
function fmtAgo(
  secondsAgo,
  hass,
) {
  if (secondsAgo === null || secondsAgo === undefined || !Number.isFinite(Number(secondsAgo))) {
    return "—";
  }
  const secs = Math.max(0, Math.round(Number(secondsAgo)));
  try {
    const rtf = new Intl.RelativeTimeFormat(hassLanguage(hass), { numeric: "auto" });
    if (secs < 60) return rtf.format(-secs, "second");
    if (secs < 3600) return rtf.format(-Math.round(secs / 60), "minute");
    if (secs < 86400) return rtf.format(-Math.round(secs / 3600), "hour");
    return rtf.format(-Math.round(secs / 86400), "day");
  } catch {
    return `${secs}s ago`;
  }
}
function fmtDateTime(
  ts,
  hass,
) {
  if (ts === null || ts === undefined || ts === "") return "";
  const date = typeof ts === "number" ? new Date(ts < 1e12 ? ts * 1000 : ts) : new Date(ts);
  if (Number.isNaN(date.getTime())) return String(ts);
  const useServerTz = hass?.locale?.time_zone === "server" && Boolean(hass?.config?.time_zone);
  const opts = {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  };
  if (useServerTz && hass?.config?.time_zone) {
    opts.timeZone = hass.config.time_zone;
  }
  try {
    return new Intl.DateTimeFormat(hassLanguage(hass), opts).format(date);
  } catch {
    return date.toISOString();
  }
}
function capitalizeSegment(seg) {
  if (!seg) return seg;
  const low = seg.toLowerCase();
  if (LABEL_ACRONYMS[low]) return LABEL_ACRONYMS[low];
  if (/^[a-z]+[A-Z]/.test(seg) || /^[A-Z0-9]{2,}$/.test(seg)) return seg;
  return seg.charAt(0).toUpperCase() + seg.slice(1);
}
function entityLabel(rawName) {
  const cleaned = String(rawName || "").trim();
  if (!cleaned) return "—";
  const words = cleaned.split(/\s+/).filter(Boolean);
  return words
    .map((word, idx) => {
      const m = /^([([{"']*)(.*?)([)\]}"':,.?]*)$/.exec(word);
      const lead = m ? m[1] : "";
      const core = m ? m[2] : word;
      const trail = m ? m[3] : "";
      if (!core) return word;
      // Preserve parenthesized units such as (ms), (s), (dB), (dBm), (%).
      if (lead === "(" && trail === ")" && /^(ms|s|m|h|dB|dBm|Hz|kHz|MHz|V|mV|A|mA|W|%|°C|°F)$/.test(core)) {
        return word;
      }
      const isEdge = idx === 0 || idx === words.length - 1;
      const low = core.toLowerCase();
      if (!isEdge && LABEL_MINOR_WORDS.has(low)) {
        return `${lead}${low}${trail}`;
      }
      if (LABEL_ACRONYMS[low]) {
        return `${lead}${LABEL_ACRONYMS[low]}${trail}`;
      }
      const hyph = core
        .split("-")
        .map((seg) => capitalizeSegment(seg))
        .join("-");
      return `${lead}${hyph}${trail}`;
    })
    .join(" ");
}
function issueMessage(issue) {
  const kind = String(issue.kind || issue.key || "");
  const fn = ISSUE_TEXT[kind];
  if (fn) return fn(issue);
  const label = kind ? kind.replace(/_/g, " ") : "issue";
  return `Repair: ${label}.`;
}
function rssiToPercent(rssi) {
  if (rssi === null || rssi === undefined || !Number.isFinite(Number(rssi))) return 0;
  const clamped = Math.max(-95, Math.min(-35, Number(rssi)));
  return Math.round(((clamped + 95) / 60) * 100);
}
function isValidHexColor(val) {
  const s = String(val || "").trim();
  if (s.length !== 7 || s.charCodeAt(0) !== 35) return false;
  for (let i = 1; i < 7; i += 1) {
    const code = s.charCodeAt(i);
    const isDigit = code >= 48 && code <= 57;
    const isUpper = code >= 65 && code <= 70;
    const isLower = code >= 97 && code <= 102;
    if (!isDigit && !isUpper && !isLower) return false;
  }
  return true;
}
function byteToHex(b) {
  const clamped = Math.max(0, Math.min(255, Math.round(b)));
  return clamped.toString(16).padStart(2, "0").toUpperCase();
}
function rgbBytesToHex(r, g, b) {
  return String.fromCharCode(35) + byteToHex(r) + byteToHex(g) + byteToHex(b);
}
function hsvToRgbJS(h, s, v) {
  const c = v * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = v - c;
  let r1 = 0;
  let g1 = 0;
  let b1 = 0;
  if (h < 60) [r1, g1, b1] = [c, x, 0];
  else if (h < 120) [r1, g1, b1] = [x, c, 0];
  else if (h < 180) [r1, g1, b1] = [0, c, x];
  else if (h < 240) [r1, g1, b1] = [0, x, c];
  else if (h < 300) [r1, g1, b1] = [x, 0, c];
  else [r1, g1, b1] = [c, 0, x];
  return [
    Math.round((r1 + m) * 255),
    Math.round((g1 + m) * 255),
    Math.round((b1 + m) * 255),
  ];
}
function hsvToHex(h, s, v) {
  const [r, g, b] = hsvToRgbJS(h, s, v);
  return rgbBytesToHex(r, g, b);
}
function defaultThemeHex(hostEl) {
  if (hostEl && typeof getComputedStyle === "function") {
    const raw = getComputedStyle(hostEl).getPropertyValue("--primary-color").trim();
    if (isValidHexColor(raw)) return raw.toUpperCase();
  }
  return rgbBytesToHex(0, 154, 199);
}
async function copyTextToClipboard(text) {
  if (!text) return false;
  try {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // Fall back to offscreen textarea selection below.
  }
  try {
    const ta = document.createElement("textarea");
    ta.className = "offscreen";
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}
function triggerJsonDownload(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function navigateHaPath(path, replace = false) {
  if (!path) return;
  if (replace) {
    globalThis.history.replaceState(null, "", path);
  } else {
    globalThis.history.pushState(null, "", path);
  }
  globalThis.dispatchEvent(new Event("location-changed", { bubbles: true, composed: true }));
}

// --- src/components/controls.ts ---
/**
 * Shared Lit UI controls, declarative card/row/slot helpers, native ESPHome entity rows, and table headers.
 * Note: Event bindings (`@click`, `@change`) always precede `class="..."` / `role="radio"` attributes.
 */
function renderCard(opts) {
  const headingEl = opts.heading ?? html`<h3 class="card-title">${opts.title || ""}</h3>`;
  const headerInner =
    opts.subtitle || opts.headerActions
      ? html`<div class="card-heading">
            ${headingEl}
            ${opts.subtitle ? html`<p class="card-subtitle">${opts.subtitle}</p>` : nothing}
          </div>
          ${opts.headerActions && opts.headerActions !== nothing
            ? html`<div class="card-header-actions">${opts.headerActions}</div>`
            : nothing}`
      : headingEl;
  const contentCls = opts.contentClass ? `card-content ${opts.contentClass}` : "card-content";
  return html`<div id=${opts.id || nothing} class="card${opts.danger ? " danger" : ""}">
    <div class="card-header">${headerInner}</div>
    <div class=${contentCls}>${opts.body}</div>
    ${opts.footerActions && opts.footerActions !== nothing
      ? html`<div class="card-actions">${opts.footerActions}</div>`
      : nothing}
  </div>`;
}
function renderSettingsRow(opts) {
  const labelEl =
    opts.labelHtml ??
    (opts.forId
      ? html`<label for=${opts.forId} class="row-label">${opts.label || ""}</label>`
      : html`<span class="row-label">${opts.label || ""}</span>`);
  return html`<div id=${opts.id || nothing} class="settings-row${opts.stacked ? " stacked" : ""}">
    <div class="settings-row-text">
      ${labelEl}
      ${opts.description
        ? html`<p id=${opts.descId || nothing} class="row-description">${opts.description}</p>`
        : nothing}
    </div>
    <div class="settings-row-control">${opts.control}</div>
  </div>`;
}
function renderSelectRow(opts) {
  const cur = String(opts.value ?? "");
  return renderSettingsRow({
    id: opts.rowId,
    label: opts.label,
    forId: opts.id,
    description: opts.description,
    descId: opts.descId,
    control: html`<select
      id=${opts.id || nothing}
      aria-label=${opts.id ? nothing : opts.ariaLabel || opts.label}
      .value=${cur}
      @change=${(ev) => opts.onChange((ev.currentTarget).value)}
    >
      ${opts.rawOptions
        ? opts.rawOptions.map(
            (o) => html`<option value=${o.value} ?selected=${o.value === cur}>${o.label}</option>`,
          )
        : renderSelectOptions(opts.choices, cur, opts.emptyOptionLabel)}
    </select>`,
  });
}
function renderSwitchRow(opts) {
  return renderSettingsRow({
    id: opts.rowId,
    label: opts.label,
    forId: opts.id,
    description: opts.description,
    control: html`<input
      type="checkbox"
      id=${opts.id || nothing}
      role="switch"
      aria-label=${opts.id ? nothing : opts.ariaLabel || opts.label}
      .checked=${opts.checked}
      @change=${(ev) => opts.onChange((ev.currentTarget).checked)}
      class="switch"
    />`,
  });
}
function renderEntitySlotList(opts) {
  return html`<div id=${opts.id} class="stack">
    ${opts.items.length
      ? opts.items.map(
          (val, idx) => html`<div class="list-row">
            <div class="stacked-field list-row-grow">
              ${opts.slotLabel
                ? html`<span class="field-label">${opts.slotLabel(idx)}</span>`
                : nothing}
              <select
                aria-label=${opts.selectAriaLabel}
                .value=${val}
                @change=${(ev) =>
                  opts.onChange(idx, (ev.currentTarget).value)}
              >
                ${renderSelectOptions(opts.choices, val, opts.emptyOptionLabel)}
              </select>
            </div>
            ${opts.extraActions ? opts.extraActions(val, idx) : nothing}
            ${renderTrashIconButton(opts.removeAriaLabel, () => opts.onRemove(idx))}
          </div>`,
        )
      : html`<p class="empty-state">${opts.emptyStateText}</p>`}
  </div>`;
}
function renderSelectOptions(
  choices,
  selectedId,
  emptyOptionLabel = "None",
) {
  const cur = String(selectedId || "");
  const list = choices || [];
  const hasSelected = !cur || list.some((c) => c.id === cur);
  const out = [
    html`<option value="" ?selected=${cur === ""}>${emptyOptionLabel}</option>`,
  ];
  if (cur && !hasSelected) {
    out.push(html`<option value=${cur} selected>${cur} (missing)</option>`);
  }
  for (const item of list) {
    out.push(
      html`<option value=${item.id} ?selected=${item.id === cur}>${item.name || item.id}</option>`,
    );
  }
  return out;
}
function renderTrashIconButton(ariaLabel, onRemove) {
  return html`<button
    type="button"
    aria-label=${ariaLabel}
    @click=${onRemove}
    class="btn-icon danger"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 3v1H4v2h1v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6h1V4h-5V3H9m0 5h2v9H9V8m4 0h2v9h-2V8Z" />
    </svg>
  </button>`;
}
function renderSortHeader(
  store,
  field,
  label,
) {
  const isActive = store.deviceSortField === field;
  const ariaSort = isActive ? (store.deviceSortAsc ? "ascending" : "descending") : "none";
  const onSort = () => {
    if (store.deviceSortField === field) {
      store.deviceSortAsc = !store.deviceSortAsc;
    } else {
      store.deviceSortField = field;
      store.deviceSortAsc = true;
    }
    store.host.requestUpdate();
  };
  return html`<th aria-sort=${ariaSort}>
    <button type="button" @click=${onSort} class="sort-btn">${label}</button>
  </th>`;
}
function renderNativeControlRow(store, item) {
  const label = entityLabel(item.name || item.entity_id);
  const dom = item.domain;
  const st = String(item.state ?? "");
  const prefKey = item.pref_key || "";
  const unavailable = !prefKey && (st === "unavailable" || st === "unknown");
  if (dom === "switch") {
    const isOn = st === "on";
    const onToggle = (ev) => {
      const checked = (ev.currentTarget).checked;
      if (prefKey) {
        store.stageDeviceSetting(prefKey, checked);
      } else {
        void store.espAction(item.entity_id, checked ? "turn_on" : "turn_off", checked ? "on" : "off");
      }
    };
    return renderSettingsRow({
      label,
      control: html`<input
        type="checkbox"
        role="switch"
        aria-label=${label}
        ?disabled=${unavailable}
        .checked=${isOn}
        @change=${onToggle}
        class="switch"
      />`,
    });
  }
  if (dom === "select") {
    const opts = item.options || [];
    const onChange = (ev) => {
      const nextVal = (ev.currentTarget).value;
      if (prefKey) {
        store.stageDeviceSetting(prefKey, nextVal);
      } else {
        void store.espSelect(item.entity_id, nextVal);
      }
    };
    return renderSettingsRow({
      label,
      control: html`<select aria-label=${label} ?disabled=${unavailable} .value=${st} @change=${onChange}>
        ${opts.map((opt) => html`<option value=${opt} ?selected=${opt === st}>${opt}</option>`)}
      </select>`,
    });
  }
  if (dom === "number") {
    const min = item.min ?? 0;
    const max = item.max ?? 100;
    const step = item.step ?? 1;
    const numVal = Number.isFinite(Number(st)) ? Number(st) : min;
    const unitSuffix = item.unit ? ` ${item.unit}` : "";
    const onCommit = (ev) => {
      const raw = Number((ev.currentTarget).value);
      if (Number.isFinite(raw)) {
        if (prefKey) {
          store.stageDeviceSetting(prefKey, raw);
        } else {
          void store.espNumber(item.entity_id, raw);
        }
      }
    };
    if (max - min <= 250 && item.mode !== "box") {
      return renderSettingsRow({
        label,
        control: html`<span class="kv-value">${fmtNumber(numVal, store.hass)}${unitSuffix}</span>
          <input
            type="range"
            aria-label=${label}
            min=${String(min)}
            max=${String(max)}
            step=${String(step)}
            ?disabled=${unavailable}
            .value=${String(numVal)}
            @change=${onCommit}
          />`,
      });
    }
    return renderSettingsRow({
      label,
      control: html`<input
          type="number"
          aria-label=${label}
          min=${String(min)}
          max=${String(max)}
          step=${String(step)}
          ?disabled=${unavailable}
          .value=${String(numVal)}
          @change=${onCommit}
        />
        ${item.unit ? html`<span class="help-text">${item.unit}</span>` : nothing}`,
    });
  }
  if (dom === "button") {
    const buttonUnavailable = st === "unavailable";
    const toastMsg = label.toLowerCase().includes("restart")
      ? "Restarting Device…"
      : `Triggered "${label}"`;
    const onRun = () => {
      if (item.device_command) {
        void store.runDeviceAction(item.device_command, toastMsg);
      } else {
        void store.espAction(item.entity_id, "press", undefined, toastMsg);
      }
    };
    return renderSettingsRow({
      label,
      control: html`<button
        type="button"
        ?disabled=${buttonUnavailable}
        @click=${onRun}
        class="btn btn-secondary btn-compact"
      >
        Run
      </button>`,
    });
  }
  if (dom === "update") {
    const hasUpdate = st === "on";
    return renderSettingsRow({
      label,
      control: html`<span class="chip ${hasUpdate ? "chip-warning" : ""}">${hasUpdate ? "Update available" : "Up to date"}</span>
        ${hasUpdate
          ? html`<button
              type="button"
              @click=${() => void store.espAction(item.entity_id, "install")}
              class="btn btn-primary btn-compact"
            >
              Install
            </button>`
          : nothing}`,
    });
  }
  const displayVal = unavailable
    ? "—"
    : item.unit && Number.isFinite(Number(st))
      ? `${fmtNumber(Number(st), store.hass)} ${item.unit}`
      : st || "—";
  return html`<div class="kv-row">
    <span>${label}</span>
    <strong>${displayVal}</strong>
  </div>`;
}
function renderPrefControlRow(
  store,
  pref,
  labelOverride,
) {
  const label = labelOverride || pref.label || entityLabel(pref.key);
  const dom = pref.domain;
  const val = pref.value;
  if (dom === "switch") {
    const isOn = Boolean(val);
    const onToggle = (ev) => {
      const checked = (ev.currentTarget).checked;
      store.stageDeviceSetting(pref.key, checked);
    };
    return renderSettingsRow({
      label,
      control: html`<input
        type="checkbox"
        role="switch"
        aria-label=${label}
        .checked=${isOn}
        @change=${onToggle}
        class="switch"
      />`,
    });
  }
  if (dom === "select") {
    const opts = pref.options || [];
    const st = String(val ?? "");
    const onChange = (ev) => {
      const nextVal = (ev.currentTarget).value;
      store.stageDeviceSetting(pref.key, nextVal);
    };
    return renderSettingsRow({
      label,
      control: html`<select aria-label=${label} .value=${st} @change=${onChange}>
        ${opts.map((opt) => html`<option value=${opt} ?selected=${opt === st}>${opt}</option>`)}
      </select>`,
    });
  }
  if (dom === "number") {
    const min = pref.min ?? 0;
    const max = pref.max ?? 100;
    const step = pref.step ?? 1;
    const numVal = Number.isFinite(Number(val)) ? Number(val) : min;
    const unitSuffix = pref.unit ? ` ${pref.unit}` : "";
    const onCommit = (ev) => {
      const raw = Number((ev.currentTarget).value);
      if (Number.isFinite(raw)) {
        store.stageDeviceSetting(pref.key, raw);
      }
    };
    if (max - min <= 250) {
      return renderSettingsRow({
        label,
        control: html`<span class="kv-value">${fmtNumber(numVal, store.hass)}${unitSuffix}</span>
          <input
            type="range"
            aria-label=${label}
            min=${String(min)}
            max=${String(max)}
            step=${String(step)}
            .value=${String(numVal)}
            @change=${onCommit}
          />`,
      });
    }
    return renderSettingsRow({
      label,
      control: html`<input
          type="number"
          aria-label=${label}
          min=${String(min)}
          max=${String(max)}
          step=${String(step)}
          .value=${String(numVal)}
          @change=${onCommit}
        />
        ${pref.unit ? html`<span class="help-text">${pref.unit}</span>` : nothing}`,
    });
  }
  return nothing;
}
const QUICK_ACTION_RANK = {
  find_my: 0,
  voice: 1,
  screensaver: 2,
  hibernate: 3,
  restart: 4,
  other: 5,
};
function quickActionKind(item) {
  const nameLow = (item.name || "").toLowerCase();
  const idTail = item.entity_id.includes(".")
    ? item.entity_id.split(".", 2)[1].toLowerCase()
    : item.entity_id.toLowerCase();
  if (
    item.device_class === "identify" ||
    nameLow.includes("find my") ||
    idTail.endsWith("find_my_device") ||
    idTail.includes("_find_my")
  ) {
    return "find_my";
  }
  if (
    item.device_class === "restart" ||
    nameLow.includes("restart") ||
    idTail.endsWith("_restart_device") ||
    idTail.endsWith("_restart")
  ) {
    return "restart";
  }
  if (nameLow.includes("screensaver") || idTail.includes("screensaver")) {
    return "screensaver";
  }
  if (nameLow.includes("hibernate") || idTail.includes("hibernate")) {
    return "hibernate";
  }
  if (
    nameLow.includes("voice") ||
    nameLow.includes("assist") ||
    idTail.includes("trigger_voice") ||
    idTail.includes("trigger_va")
  ) {
    return "voice";
  }
  return "other";
}
function renderQuickActionIcon(kind) {
  if (kind === "find_my") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2m0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8m0-14a6 6 0 1 0 6 6 6 6 0 0 0-6-6m0 10a4 4 0 1 1 4-4 4 4 0 0 1-4 4m0-6a2 2 0 1 0 2 2 2 2 0 0 0-2-2Z"
      />
    </svg>`;
  }
  if (kind === "voice") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3m7 9c0 3.53-2.61 6.44-6 6.93V21h-2v-3.07c-3.39-.49-6-3.4-6-6.93h2a5 5 0 0 0 10 0h2Z"
      />
    </svg>`;
  }
  if (kind === "screensaver") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M20 3H4a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h6v2H7v2h10v-2h-3v-2h6a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2m0 13H4V5h16v11M11.2 6.8a3.8 3.8 0 1 0 2.4 6 3.5 3.5 0 0 1-2.4-6m5.3-.6.65 1.65 1.65.65-1.65.65-.65 1.65-.65-1.65-1.65-.65 1.65-.65.65-1.65Z"
      />
    </svg>`;
  }
  if (kind === "hibernate") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M16.56 5.44l-1.45 1.45A5.969 5.969 0 0 1 18 12a6 6 0 0 1-6 6 6 6 0 0 1-6-6c0-2.17 1.16-4.06 2.88-5.12L7.44 5.44A7.961 7.961 0 0 0 4 12a8 8 0 0 0 8 8 8 8 0 0 0 8-8c0-2.72-1.36-5.12-3.44-6.56M13 3h-2v10h2V3Z"
      />
    </svg>`;
  }
  if (kind === "restart") {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35Z"
      />
    </svg>`;
  }
  return html`<svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M7 2h10l-3.5 7H17l-7 13v-8H6l1-12Z" />
  </svg>`;
}
function sortQuickActionButtons(
  items,
) {
  return [...items].sort((a, b) => {
    const ra = QUICK_ACTION_RANK[quickActionKind(a)];
    const rb = QUICK_ACTION_RANK[quickActionKind(b)];
    if (ra !== rb) return ra - rb;
    return `${a.name || ""} ${a.entity_id}`
      .toLowerCase()
      .localeCompare(`${b.name || ""} ${b.entity_id}`.toLowerCase());
  });
}
function renderQuickActionGrid(
  store,
  buttons,
) {
  if (!buttons.length) return nothing;
  const ordered = sortQuickActionButtons(buttons);
  return html`<div class="quick-action-grid" role="group" aria-label="Device Quick Actions">
    ${ordered.map((item) => {
      const kind = quickActionKind(item);
      const label = entityLabel(item.name || item.entity_id);
      const buttonUnavailable = String(item.state ?? "") === "unavailable";
      const toastMsg =
        kind === "restart"
          ? "Restarting Device…"
          : kind === "hibernate"
            ? "Hibernating Device…"
            : `Triggered "${label}"`;
      const onTrigger = () => {
        if (item.device_command) {
          void store.runDeviceAction(item.device_command, toastMsg);
        } else {
          void store.espAction(item.entity_id, "press", undefined, toastMsg);
        }
      };
      return html`<button
        type="button"
        data-entity-id=${item.entity_id}
        ?disabled=${buttonUnavailable}
        @click=${onTrigger}
        class="btn btn-secondary quick-action-btn"
      >
        ${renderQuickActionIcon(kind)}
        <span>${label}</span>
      </button>`;
    })}
  </div>`;
}

// --- src/components/dialogs.ts ---
/**
 * Native `<dialog>` Modals for Latter Studio (Remove Device, Reset Device, Add BLE Tag, Custom Color Wheel).
 * Uses component-scoped pointer capture on `<canvas>` — zero `window.*` listeners.
 */
let cwWheelPainted = false;
function paintHsvColorWheel(canvas) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const size = canvas.width;
  const radius = size / 2;
  const img = ctx.createImageData(size, size);
  const data = img.data;
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const dx = x - radius;
      const dy = y - radius;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const idx = (y * size + x) * 4;
      if (dist > radius) {
        data[idx + 3] = 0;
        continue;
      }
      const sat = Math.min(1, dist / radius);
      const angle = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
      const [r, g, b] = hsvToRgbJS(angle, sat, 1);
      data[idx] = r;
      data[idx + 1] = g;
      data[idx + 2] = b;
      data[idx + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
}
function pickWheelHexFromEvent(canvas, ev) {
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const cx = rect.width / 2;
  const cy = rect.height / 2;
  const dx = ev.clientX - rect.left - cx;
  const dy = ev.clientY - rect.top - cy;
  const radius = Math.min(cx, cy);
  const sat = Math.min(1, Math.sqrt(dx * dx + dy * dy) / radius);
  const angle = ((Math.atan2(dy, dx) * 180) / Math.PI + 360) % 360;
  return hsvToHex(angle, sat, 1);
}
function syncStudioDialogs(renderRoot, store) {
  const pairs = [
    ["latter-rm-modal", store.removeModal.open],
    ["latter-reset-modal", store.resetModal.open],
    ["latter-add-dev-modal", store.addBleModal.open],
    ["latter-cw-modal", store.colorWheelModal.open],
    ["latter-save-group-modal", store.saveGroupModal?.open ?? false],
    ["latter-shortcut-modal", store.shortcutModal?.open ?? false],
  ];
  for (const [id, wantOpen] of pairs) {
    const dlg = renderRoot.getElementById(id);
    if (!dlg) continue;
    if (wantOpen && !dlg.open) {
      try {
        dlg.showModal();
      } catch {
        dlg.setAttribute("open", "");
      }
    } else if (!wantOpen && dlg.open) {
      try {
        dlg.close();
      } catch {
        dlg.removeAttribute("open");
      }
    }
  }
  if (store.colorWheelModal.open && !cwWheelPainted) {
    const canvas = renderRoot.getElementById("latter-cw-canvas");
    if (canvas) {
      paintHsvColorWheel(canvas);
      cwWheelPainted = true;
    }
  } else if (!store.colorWheelModal.open) {
    cwWheelPainted = false;
  }
}
function renderStudioDialogs(store) {
  const persons = store.state?.catalog?.persons || [];
  const candidates = store.state?.discovered_ble_devices || [];
  const onBackdropClick = (ev, closeFn) => {
    if (ev.target === ev.currentTarget) {
      closeFn();
    }
  };
  const onCwPointerDown = (ev) => {
    const pev = ev;
    const canvas = pev.currentTarget;
    canvas.setPointerCapture?.(pev.pointerId);
    const hex = pickWheelHexFromEvent(canvas, pev);
    if (hex) {
      store.colorWheelModal = { ...store.colorWheelModal, hex };
      store.host.requestUpdate();
    }
  };
  const onCwPointerMove = (ev) => {
    const pev = ev;
    if (pev.buttons === 0) return;
    const canvas = pev.currentTarget;
    const hex = pickWheelHexFromEvent(canvas, pev);
    if (hex) {
      store.colorWheelModal = { ...store.colorWheelModal, hex };
      store.host.requestUpdate();
    }
  };
  const onCwPointerUp = (ev) => {
    const pev = ev;
    const canvas = pev.currentTarget;
    if (canvas.hasPointerCapture?.(pev.pointerId)) {
      canvas.releasePointerCapture(pev.pointerId);
    }
  };
  const onCwHexInput = (ev) => {
    const raw = (ev.currentTarget).value;
    store.colorWheelModal = { ...store.colorWheelModal, hex: raw.toUpperCase() };
    store.host.requestUpdate();
  };
  const onCwNameInput = (ev) => {
    store.colorWheelModal = {
      ...store.colorWheelModal,
      name: (ev.currentTarget).value,
    };
  };
  const cwValidHex = isValidHexColor(store.colorWheelModal.hex)
    ? store.colorWheelModal.hex
    : "";
  const scModal = store.shortcutModal;
  const scIsDock = scModal.listKey === "dock_items";
  const scTitle =
    scModal.editIndex !== null
      ? scIsDock
        ? "Edit Dock Shortcut"
        : "Edit Pinned Shortcut"
      : scIsDock
        ? "Add Dock Shortcut"
        : "Add Pinned Shortcut";
  const devCaps = store.state?.capabilities || {};
  const availableRoutes = SHORTCUT_ROUTES_CATALOG.filter((r) => {
    if (!scIsDock && r.dockOnly) return false;
    if (scIsDock && r.token === "settings:root") return false;
    if (r.capability === "round" && devCaps.is_round === false) return false;
    if (r.capability === "imu" && devCaps.has_imu === false) return false;
    return true;
  });
  const routeGroups = [];
  for (const r of availableRoutes) {
    const grpName = r.group || "Apps";
    const existingGrp = routeGroups.find((g) => g.group === grpName);
    if (existingGrp) {
      existingGrp.items.push(r);
    } else {
      routeGroups.push({ group: grpName, items: [r] });
    }
  }
  const allShortcutEntities = store.state?.catalog?.shortcut_entities || [];
  const availableDomains = Array.from(
    new Set(allShortcutEntities.map((e) => e.domain)),
  ).sort();
  const scSearchLower = scModal.entitySearch.trim().toLowerCase();
  const filteredShortcutEntities = allShortcutEntities.filter((e) => {
    if (scModal.entityDomainFilter !== "all" && e.domain !== scModal.entityDomainFilter) {
      return false;
    }
    if (!scSearchLower) return true;
    return (
      e.name.toLowerCase().includes(scSearchLower) ||
      e.id.toLowerCase().includes(scSearchLower) ||
      e.area_name.toLowerCase().includes(scSearchLower)
    );
  });
  const selectedEntityObj =
    allShortcutEntities.find((e) => e.id === scModal.entityTarget) || null;
  const selectedEntityDomain = selectedEntityObj
    ? selectedEntityObj.domain
    : (scModal.entityTarget.split(".", 1)[0] || "");
  const availableEntityActions = SHORTCUT_DOMAIN_ACTIONS[selectedEntityDomain] || [];
  const selectedRouteSpec =
    availableRoutes.find((r) => r.token === scModal.routeTarget) ||
    SHORTCUT_ROUTES_CATALOG.find((r) => r.token === scModal.routeTarget);
  const autoDefaultLabel =
    scModal.kind === "route"
      ? selectedRouteSpec?.label || "Shortcut"
      : selectedEntityObj?.name || scModal.entityTarget || "Entity Action";
  const autoDefaultIcon =
    scModal.kind === "route"
      ? ROUTE_PREVIEW_ICONS[scModal.routeTarget] || "mdi:apps"
      : selectedEntityObj?.icon || "mdi:flash";
  const selectedCustomIcon = normalizeMdiIconSlug(scModal.icon);
  const typedSearchIcon = normalizeMdiIconSlug(scModal.iconSearch);
  const previewIcon =
    selectedCustomIcon ||
    (isKnownMdiIcon(typedSearchIcon) ? typedSearchIcon : autoDefaultIcon);
  const hasIconQuery = scModal.iconSearch.trim().length > 0;
  const { items: filteredMdiIcons, totalMatches: mdiMatchCount } = searchMdiIcons(
    scModal.iconSearch,
    120,
  );
  return html`
    <dialog
      id="latter-rm-modal"
      aria-labelledby="latter-rm-title"
      @cancel=${() => store.closeRemoveDeviceModal()}
      @click=${(ev) => onBackdropClick(ev, () => store.closeRemoveDeviceModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-rm-title" class="dialog-title">Remove Device From Latter?</h3>
        <p class="dialog-text">
          Removes "${store.removeModal.title || "Device"}" from Latter. Your ESPHome device stays in Home Assistant.
        </p>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeRemoveDeviceModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            ?disabled=${store.removeModal.busy}
            @click=${() => void store.confirmRemoveDevice()}
            class="btn btn-danger-filled"
          >
            Remove Device
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-reset-modal"
      aria-labelledby="latter-reset-title"
      @cancel=${() => store.closeResetDeviceModal()}
      @click=${(ev) => onBackdropClick(ev, () => store.closeResetDeviceModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-reset-title" class="dialog-title">Reset to Defaults?</h3>
        <div class="settings-list">
          ${renderSwitchRow({
            id: "latter-reset-device-settings",
            label: "Settings Saved on the Device",
            description: "Erases everything saved on the Device; it restarts.",
            checked: store.resetModal.deviceSettings,
            onChange: (checked) => {
              store.resetModal = { ...store.resetModal, deviceSettings: checked };
              store.host.requestUpdate();
            },
          })}
          ${renderSwitchRow({
            id: "latter-reset-latter-options",
            label: "Latter Settings for This Device",
            checked: store.resetModal.latterOptions,
            onChange: (checked) => {
              store.resetModal = { ...store.resetModal, latterOptions: checked };
              store.host.requestUpdate();
            },
          })}
        </div>
        <p class="dialog-text">
          Wi-Fi and pairing are kept, so the Device rejoins Home Assistant by itself. Its ESPHome binding and Music Assistant player link are kept too.
        </p>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeResetDeviceModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            id="latter-reset-confirm-btn"
            ?disabled=${store.resetModal.busy || (!store.resetModal.deviceSettings && !store.resetModal.latterOptions)}
            @click=${() => void store.confirmResetDevice()}
            class="btn btn-danger-filled"
          >
            Reset
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-add-dev-modal"
      aria-labelledby="latter-add-dev-title"
      @cancel=${() => store.closeAddBleModal()}
      @click=${(ev) => onBackdropClick(ev, () => store.closeAddBleModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-add-dev-title" class="dialog-title">Add a BLE Tag</h3>
        <p class="dialog-text">
          A phone, watch or Bluetooth tag that Latter tracks by Area. Latter Devices are added in Home Assistant.
        </p>
        <div class="stacked-field">
          <label for="ble-candidate-picker">Discovered Bluetooth Devices</label>
          <select
            id="ble-candidate-picker"
            .value=${store.addBleModal.candidateAddr}
            @change=${(ev) =>
              store.selectBleCandidateInModal((ev.currentTarget).value)}
          >
            <option value="">Enter manually…</option>
            ${candidates.map((c) => {
              const addr = c.target_address || c.address || "";
              const lbl =
                c.label ||
                `${c.title || c.name || addr}${c.area_name ? ` (${c.area_name})` : ""}`;
              return html`<option value=${addr} ?selected=${addr === store.addBleModal.candidateAddr}>
                ${lbl}
              </option>`;
            })}
          </select>
        </div>
        <div class="stacked-field">
          <label for="ble-custom-name">Name</label>
          <input
            type="text"
            id="ble-custom-name"
            placeholder="e.g. phone, watch, keys"
            .value=${store.addBleModal.name}
            @input=${(ev) => {
              store.addBleModal = {
                ...store.addBleModal,
                name: (ev.currentTarget).value,
              };
            }}
          />
        </div>
        <div class="stacked-field">
          <span class="field-label">Target Address or Entity</span>
          <input
            type="text"
            id="ble-custom-addr"
            placeholder="AA:BB:CC:DD:EE:FF or device_tracker.phone_ble"
            .value=${store.addBleModal.address}
            @input=${(ev) => {
              store.addBleModal = {
                ...store.addBleModal,
                address: (ev.currentTarget).value,
              };
            }}
            class="mono"
          />
        </div>
        <div class="stacked-field">
          <label for="ble-custom-person">Assigned Person (Optional)</label>
          <select
            id="ble-custom-person"
            .value=${store.addBleModal.assignedPerson}
            @change=${(ev) => {
              store.addBleModal = {
                ...store.addBleModal,
                assignedPerson: (ev.currentTarget).value,
              };
            }}
          >
            ${renderSelectOptions(persons, store.addBleModal.assignedPerson, "Unassigned")}
          </select>
        </div>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeAddBleModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            ?disabled=${store.addBleModal.busy}
            @click=${() => void store.confirmAddBleModal()}
            class="btn btn-primary"
          >
            Add BLE Tag
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-cw-modal"
      aria-labelledby="latter-cw-title"
      @cancel=${() => store.closeColorWheelModal()}
      @click=${(ev) => onBackdropClick(ev, () => store.closeColorWheelModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-cw-title" class="dialog-title">Add a Custom Color</h3>
        <div class="color-wheel" aria-hidden="true">
          <canvas
            id="latter-cw-canvas"
            width="220"
            height="220"
            @pointerdown=${onCwPointerDown}
            @pointermove=${onCwPointerMove}
            @pointerup=${onCwPointerUp}
          ></canvas>
        </div>
        <div class="color-hex-row">
          <input
            type="color"
            id="latter-cw-native"
            aria-label="Color"
            .value=${cwValidHex}
            @input=${onCwHexInput}
          />
          <input
            type="text"
            id="latter-cw-hex"
            aria-label="Hex color"
            placeholder="#RRGGBB"
            maxlength="7"
            .value=${store.colorWheelModal.hex}
            @input=${onCwHexInput}
          />
        </div>
        <div class="stacked-field">
          <label for="latter-cw-name">Name</label>
          <input
            type="text"
            id="latter-cw-name"
            placeholder="e.g. Sunset Coral"
            .value=${store.colorWheelModal.name}
            @input=${onCwNameInput}
          />
        </div>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeColorWheelModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            @click=${() => void store.saveColorWheelSelection()}
            class="btn btn-primary"
          >
            Save Color
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-save-group-modal"
      aria-labelledby="latter-save-group-title"
      @cancel=${() => store.closeSaveGroupModal()}
      @click=${(ev) => onBackdropClick(ev, () => store.closeSaveGroupModal())}
      class="studio-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-save-group-title" class="dialog-title">Save Custom Group</h3>
        <p class="dialog-text">
          Saves this Device's settings as a reusable Device Group and assigns this Device to it.
        </p>
        <div class="stacked-field">
          <label for="save-group-name">Group Name</label>
          <input
            type="text"
            id="save-group-name"
            placeholder="e.g. Nightstands, Guest Suites"
            .value=${store.saveGroupModal?.name || ""}
            @input=${(ev) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                name: (ev.currentTarget).value,
              };
            }}
          />
        </div>
        <div class="stacked-field">
          <label for="save-group-desc">Description (Optional)</label>
          <input
            type="text"
            id="save-group-desc"
            placeholder="Optional summary of these settings"
            .value=${store.saveGroupModal?.description || ""}
            @input=${(ev) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                description: (ev.currentTarget).value,
              };
            }}
          />
        </div>
        <div class="settings-list">
          ${renderSwitchRow({
            id: "save-group-include-display",
            label: "Include Display Settings",
            description: "Sync wallpapers, clock face, color profile, and media styling.",
            checked: Boolean(store.saveGroupModal?.includeDisplay),
            onChange: (checked) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                includeDisplay: checked,
              };
              store.host.requestUpdate();
            },
          })}
          ${renderSwitchRow({
            id: "save-group-include-interface",
            label: "Include Interface & Shortcuts",
            description: "Sync start screen, App Dock, pinned shortcuts, and hub categories.",
            checked: Boolean(store.saveGroupModal?.includeInterface),
            onChange: (checked) => {
              store.saveGroupModal = {
                ...store.saveGroupModal,
                includeInterface: checked,
              };
              store.host.requestUpdate();
            },
          })}
        </div>
        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeSaveGroupModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            id="latter-save-group-confirm-btn"
            ?disabled=${Boolean(store.saveGroupModal?.busy)}
            @click=${() => void store.confirmSaveGroupModal()}
            class="btn btn-primary"
          >
            Save Group
          </button>
        </div>
      </div>
    </dialog>

    <dialog
      id="latter-shortcut-modal"
      aria-labelledby="latter-shortcut-title"
      @cancel=${() => store.closeShortcutModal()}
      @click=${(ev) => onBackdropClick(ev, () => store.closeShortcutModal())}
      class="studio-dialog shortcut-dialog"
    >
      <div class="dialog-body">
        <h3 id="latter-shortcut-title" class="dialog-title">${scTitle}</h3>
        <div class="scope-tabs" role="tablist" aria-label="Shortcut Type">
          <button
            type="button"
            role="tab"
            aria-selected=${String(scModal.kind === "route")}
            @click=${() => {
              store.shortcutModal = { ...store.shortcutModal, kind: "route" };
              store.host.requestUpdate();
            }}
            class="scope-tab ${scModal.kind === "route" ? "active" : ""}"
          >
            App or Page
          </button>
          <button
            type="button"
            role="tab"
            aria-selected=${String(scModal.kind === "entity")}
            @click=${() => {
              store.shortcutModal = { ...store.shortcutModal, kind: "entity" };
              store.host.requestUpdate();
            }}
            class="scope-tab ${scModal.kind === "entity" ? "active" : ""}"
          >
            Home Assistant Entity
          </button>
        </div>

        ${scModal.kind === "route"
          ? html`<div class="stacked-field">
              <label for="shortcut-route-select">Target App or Subpage</label>
              <select
                id="shortcut-route-select"
                .value=${scModal.routeTarget}
                @change=${(ev) => {
                  const val = (ev.currentTarget).value;
                  store.shortcutModal = { ...store.shortcutModal, routeTarget: val };
                  store.host.requestUpdate();
                }}
              >
                ${routeGroups.map(
                  (grp) => html`<optgroup label=${grp.group}>
                    ${grp.items.map(
                      (item) => html`<option
                        value=${item.token}
                        ?selected=${item.token === scModal.routeTarget}
                      >
                        ${item.label}
                      </option>`,
                    )}
                  </optgroup>`,
                )}
              </select>
            </div>`
          : html`<div class="list-row-main">
                <div class="stacked-field">
                  <label for="shortcut-domain-filter">Domain Filter</label>
                  <select
                    id="shortcut-domain-filter"
                    .value=${scModal.entityDomainFilter}
                    @change=${(ev) => {
                      const nextDom = (ev.currentTarget).value;
                      const nextList = allShortcutEntities.filter(
                        (e) => nextDom === "all" || e.domain === nextDom,
                      );
                      const keepEnt = nextList.some((e) => e.id === scModal.entityTarget)
                        ? scModal.entityTarget
                        : (nextList[0]?.id || "");
                      const effDom = keepEnt.split(".", 1)[0] || nextDom;
                      const nextAct = SHORTCUT_DOMAIN_ACTIONS[effDom]?.[0]?.action || "";
                      store.shortcutModal = {
                        ...store.shortcutModal,
                        entityDomainFilter: nextDom,
                        entityTarget: keepEnt,
                        action: nextAct,
                      };
                      store.host.requestUpdate();
                    }}
                  >
                    <option value="all" ?selected=${scModal.entityDomainFilter === "all"}>
                      All Domains
                    </option>
                    ${availableDomains.map(
                      (dom) => html`<option
                        value=${dom}
                        ?selected=${dom === scModal.entityDomainFilter}
                      >
                        ${SHORTCUT_DOMAIN_LABELS[dom] || dom}
                      </option>`,
                    )}
                  </select>
                </div>
                <div class="stacked-field">
                  <label for="shortcut-entity-search">Filter Entities</label>
                  <input
                    type="search"
                    id="shortcut-entity-search"
                    placeholder="Search name, Area, or entity ID…"
                    .value=${scModal.entitySearch}
                    @input=${(ev) => {
                      const query = (ev.currentTarget).value;
                      const qLow = query.trim().toLowerCase();
                      const matches = allShortcutEntities.filter((e) => {
                        if (
                          scModal.entityDomainFilter !== "all" &&
                          e.domain !== scModal.entityDomainFilter
                        ) {
                          return false;
                        }
                        if (!qLow) return true;
                        return (
                          e.name.toLowerCase().includes(qLow) ||
                          e.id.toLowerCase().includes(qLow) ||
                          e.area_name.toLowerCase().includes(qLow)
                        );
                      });
                      const nextTarget = matches.some((e) => e.id === scModal.entityTarget)
                        ? scModal.entityTarget
                        : (matches[0]?.id || scModal.entityTarget);
                      const nextDom = nextTarget.split(".", 1)[0] || "";
                      const validActs = SHORTCUT_DOMAIN_ACTIONS[nextDom] || [];
                      const nextAct = validActs.some((a) => a.action === scModal.action)
                        ? scModal.action
                        : (validActs[0]?.action || scModal.action);
                      store.shortcutModal = {
                        ...store.shortcutModal,
                        entitySearch: query,
                        entityTarget: nextTarget,
                        action: nextAct,
                      };
                      store.host.requestUpdate();
                    }}
                  />
                </div>
              </div>
              <div class="stacked-field">
                <label for="shortcut-entity-select">Entity</label>
                <select
                  id="shortcut-entity-select"
                  .value=${scModal.entityTarget}
                  @change=${(ev) => {
                    const nextEnt = (ev.currentTarget).value;
                    const dom = nextEnt.split(".", 1)[0] || "";
                    const acts = SHORTCUT_DOMAIN_ACTIONS[dom] || [];
                    const nextAct = acts.some((a) => a.action === scModal.action)
                      ? scModal.action
                      : (acts[0]?.action || "");
                    store.shortcutModal = {
                      ...store.shortcutModal,
                      entityTarget: nextEnt,
                      action: nextAct,
                    };
                    store.host.requestUpdate();
                  }}
                >
                  ${filteredShortcutEntities.length === 0
                    ? html`<option value="">No matching Home Assistant entities</option>`
                    : filteredShortcutEntities.map(
                        (e) => html`<option
                          value=${e.id}
                          ?selected=${e.id === scModal.entityTarget}
                        >
                          ${e.area_name ? `${e.area_name} — ` : ""}${e.name} (${e.id})
                        </option>`,
                      )}
                </select>
              </div>
              <div class="stacked-field">
                <label for="shortcut-action-select">Action</label>
                <select
                  id="shortcut-action-select"
                  .value=${scModal.action}
                  @change=${(ev) => {
                    store.shortcutModal = {
                      ...store.shortcutModal,
                      action: (ev.currentTarget).value,
                    };
                    store.host.requestUpdate();
                  }}
                >
                  ${availableEntityActions.map(
                    (act) => html`<option
                      value=${act.action}
                      ?selected=${act.action === scModal.action}
                    >
                      ${act.label}
                    </option>`,
                  )}
                </select>
              </div>
              ${renderSwitchRow({
                id: "shortcut-confirm-switch",
                label: "Confirm Before Running",
                description: scIsDock
                  ? "Shows a confirmation prompt before running this action from the App Dock."
                  : "Require a confirmation tap instead of running immediately on a single tap.",
                checked: scModal.confirm,
                onChange: (checked) => {
                  store.shortcutModal = { ...store.shortcutModal, confirm: checked };
                  store.host.requestUpdate();
                },
              })}`}

        <div class="stacked-field">
          <label for="shortcut-label-input">Custom Label (Optional)</label>
          <input
            type="text"
            id="shortcut-label-input"
            maxlength=${String(SHORTCUT_LABEL_MAX)}
            placeholder=${autoDefaultLabel}
            .value=${scModal.label}
            @input=${(ev) => {
              store.shortcutModal = {
                ...store.shortcutModal,
                label: (ev.currentTarget).value,
              };
            }}
          />
        </div>

        <div class="stacked-field">
          <label for="shortcut-icon-input">Icon (Optional MDI Override)</label>
          <div class="shortcut-icon-row">
            <span class="shortcut-icon-badge" aria-hidden="true">
              <ha-icon .icon=${previewIcon}></ha-icon>
            </span>
            <input
              type="text"
              id="shortcut-icon-input"
              placeholder=${`Search all ${MDI_TOTAL_ICON_COUNT.toLocaleString()} icons (e.g. teddy-bear, baby, lamp)…`}
              .value=${scModal.iconSearch}
              @input=${(ev) => {
                const raw = (ev.currentTarget).value;
                store.shortcutModal = {
                  ...store.shortcutModal,
                  iconSearch: raw,
                };
                store.host.requestUpdate();
              }}
            />
            ${scModal.icon || scModal.iconSearch
              ? html`<button
                  type="button"
                  @click=${() => {
                    store.shortcutModal = {
                      ...store.shortcutModal,
                      icon: "",
                      iconSearch: "",
                    };
                    store.host.requestUpdate();
                  }}
                  class="btn btn-text btn-compact"
                >
                  Default Icon
                </button>`
              : nothing}
          </div>
          <p class="row-description">
            ${selectedCustomIcon
              ? `Selected: ${selectedCustomIcon}`
              : `Default: ${autoDefaultIcon}`}
            •
            ${hasIconQuery
              ? mdiMatchCount === 0
                ? "No matching icons — try another keyword"
                : mdiMatchCount > filteredMdiIcons.length
                  ? `Showing ${filteredMdiIcons.length} of ${mdiMatchCount.toLocaleString()} matches`
                  : `${mdiMatchCount.toLocaleString()} matching icon${mdiMatchCount === 1 ? "" : "s"}`
              : `Showing popular icons (${MDI_TOTAL_ICON_COUNT.toLocaleString()} searchable)`}
          </p>
          <div class="mdi-picker-grid" role="listbox" aria-label="Material Design Icons">
            ${filteredMdiIcons.map(
              (slug) => html`<button
                type="button"
                title=${slug}
                aria-label=${slug}
                aria-selected=${String(selectedCustomIcon === slug)}
                @click=${() => {
                  store.shortcutModal = {
                    ...store.shortcutModal,
                    icon: slug,
                  };
                  store.host.requestUpdate();
                }}
                class="mdi-picker-btn ${selectedCustomIcon === slug ? "selected" : ""}"
              >
                <ha-icon .icon=${slug}></ha-icon>
              </button>`,
            )}
          </div>
        </div>

        <div class="dialog-actions">
          <button
            type="button"
            @click=${() => store.closeShortcutModal()}
            class="btn btn-secondary"
          >
            Cancel
          </button>
          <button
            type="button"
            id="shortcut-save-btn"
            @click=${() => store.saveShortcutModal()}
            class="btn btn-primary"
          >
            Save Shortcut
          </button>
        </div>
      </div>
    </dialog>
  `;
}

// --- src/api/ws-client.ts ---
/**
 * Admin-gated WebSocket & Bearer-authenticated XHR multipart client for Latter Studio.
 * Enforces `studio_rev` on every read/mutation call and surfaces `studio_rev_mismatch`.
 */
const SYSTEM_WS_COMMANDS = new Set([
  "set_ble_scanner_offset",
  "capture_ble_area_signature",
  "clear_ble_area_signature",
  "set_area_fusion",
  "system_entity_action",
  "send_announcement",
  "check_system_updates",
  "clear_internal_logs",
  "remove_device",
  "add_latter_device",
  "add_ble_device",
  "create_device_group",
  "delete_device_group",
  "update_group_baseline",
  "apply_batch_device_setting",
  "test_doorbell_speaker",
  "delete_system_wallpaper",
  "save_system_config",
  "rotate_signing_key",
  "set_security_pin",
]);
const DEVICE_WS_COMMANDS = new Set([
  "esphome_entity_action",
  "device_action",
  "select_wallpaper",
  "toggle_wallpaper_favorite",
  "delete_wallpaper",
  "save_device_config",
]);
function isStudioRevMismatchError(err) {
  if (!err || typeof err !== "object") return false;
  const code = String((err).code || "");
  return code === "studio_rev_mismatch";
}
function formatWsError(err, fallback = "Action failed") {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (typeof err === "object" && "message" in err && (err).message) {
    return String((err).message);
  }
  return fallback;
}
class StudioWsClient {
          hassRef = null;
                   onRevMismatch;
  constructor(onRevMismatch) {
    this.onRevMismatch = onRevMismatch;
  }
  setHass(hass) {
    this.hassRef = hass;
  }
  get hass() {
    return this.hassRef;
  }
          requireHass() {
    if (!this.hassRef) {
      throw new Error("Home Assistant connection is not ready");
    }
    return this.hassRef;
  }
          async callWS (msg) {
    const hass = this.requireHass();
    try {
      return await hass.callWS (msg);
    } catch (err) {
      if (isStudioRevMismatchError(err)) {
        this.onRevMismatch();
      }
      throw err;
    }
  }
  async getState(options
   ) {
    const res = await this.callWS ({
      type: "latter/system/get_state",
      subentry_id: options.subentryId || null,
      include_logs: Boolean(options.includeLogs),
      studio_rev: STUDIO_REV,
    });
    if (res === null) {
      this.onRevMismatch();
    }
    return res;
  }
  async subscribe(
    options
     ,
    onEvent,
  ) {
    const hass = this.requireHass();
    if (!hass.connection) {
      throw new Error("Home Assistant WebSocket connection is unavailable");
    }
    try {
      const msg = {
        type: "latter/system/subscribe",
        subentry_id: options.subentryId || null,
        include_logs: Boolean(options.includeLogs),
        studio_rev: STUDIO_REV,
      };
      if (options.surveySubentryId) {
        msg.survey_subentry_id = options.surveySubentryId;
      }
      return await hass.connection.subscribeMessage(onEvent, msg);
    } catch (err) {
      if (isStudioRevMismatchError(err)) {
        this.onRevMismatch();
      }
      throw err;
    }
  }
  async runSystemCommand(
    cmd,
    payload = {},
    selectedSubentryId,
  ) {
    if (!SYSTEM_WS_COMMANDS.has(cmd)) {
      throw new Error(`Unknown System command: ${cmd}`);
    }
    return this.callWS ({
      type: "latter/system/command",
      command: cmd,
      subentry_id: selectedSubentryId || null,
      payload,
      studio_rev: STUDIO_REV,
    });
  }
  async runDeviceCommand(
    subentryId,
    cmd,
    payload = {},
  ) {
    if (!DEVICE_WS_COMMANDS.has(cmd)) {
      throw new Error(`Unknown Device command: ${cmd}`);
    }
    if (!subentryId) {
      throw new Error("Choose a Device first");
    }
    return this.callWS ({
      type: "latter/device/command",
      command: cmd,
      subentry_id: subentryId,
      payload,
      studio_rev: STUDIO_REV,
    });
  }
  async exportBackup(scope, subentryId) {
    if (scope === "device") {
      if (!subentryId) throw new Error("Choose a Device to export");
      return this.callWS ({
        type: "latter/device/export",
        subentry_id: subentryId,
        studio_rev: STUDIO_REV,
      });
    }
    return this.callWS ({
      type: "latter/system/export",
      studio_rev: STUDIO_REV,
    });
  }
  async importBackup(options
   ) {
    if (options.scope === "device") {
      if (!options.targetSubentryId) {
        throw new Error("Choose the Device to restore this backup onto");
      }
      return this.callWS ({
        type: "latter/device/import",
        subentry_id: options.targetSubentryId,
        bundle: options.bundle,
        studio_rev: STUDIO_REV,
      });
    }
    return this.callWS ({
      type: "latter/system/import",
      subentry_id: options.selectedSubentryId || null,
      bundle: options.bundle,
      studio_rev: STUDIO_REV,
    });
  }
  async resetDevice(options
   ) {
    return this.callWS ({
      type: "latter/device/reset",
      subentry_id: options.subentryId,
      device_settings: options.deviceSettings,
      latter_options: options.latterOptions,
      studio_rev: STUDIO_REV,
    });
  }
  async signHaPath(path, expires = 300) {
    const signed = await this.callWS ({
      type: "auth/sign_path",
      path,
      expires,
    });
    if (!signed || !signed.path) {
      throw new Error("Could not sign Home Assistant path");
    }
    return signed.path;
  }
          async getAccessToken(forceRefresh = false) {
    const hass = this.requireHass();
    const auth = hass.auth;
    if (!auth) {
      throw new Error("Home Assistant authentication session is not ready");
    }
    if ((forceRefresh || auth.expired) && typeof auth.refreshAccessToken === "function") {
      await auth.refreshAccessToken();
    }
    const token = auth.data?.access_token;
    if (!token) {
      throw new Error("Home Assistant access token is unavailable");
    }
    return token;
  }
  async uploadWallpaperMultipart(options
   ) {
    if (!options.file) {
      throw new Error("Choose an image file first");
    }
    if (options.file.size > MAX_WALLPAPER_UPLOAD_BYTES) {
      throw new Error("Wallpaper image must be 15 MB or smaller");
    }
    if (options.scope === "device" && !options.subentryId) {
      throw new Error("Choose a Device before uploading a Device wallpaper");
    }
    const UPLOAD_PATH = "/api/latter/wallpaper/upload";
    const form = new FormData();
    form.append("file", options.file, options.file.name || "wallpaper.jpg");
    form.append("scope", options.scope);
    if (options.subentryId) {
      form.append("subentry_id", options.subentryId);
    }
    const sendOnce = (bearerToken) =>
      new Promise ((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", UPLOAD_PATH, true);
        xhr.setRequestHeader("Authorization", `Bearer ${bearerToken}`);
        xhr.responseType = "json";
        if (xhr.upload && options.onProgress) {
          xhr.upload.onprogress = (ev) => {
            if (ev.lengthComputable && ev.total > 0) {
              options.onProgress?.(Math.min(100, Math.round((ev.loaded / ev.total) * 100)));
            }
          };
        }
        xhr.onload = () => {
          const body =
            xhr.response && typeof xhr.response === "object"
              ? (xhr.response)
              : null;
          resolve({ status: xhr.status, body });
        };
        xhr.onerror = () => {
          reject(new Error("Network error while uploading wallpaper"));
        };
        xhr.onabort = () => {
          reject(new Error("Wallpaper upload was canceled"));
        };
        xhr.send(form);
      });
    let token = await this.getAccessToken(false);
    let response = await sendOnce(token);
    if (
      response.status === 401 &&
      typeof this.hassRef?.auth?.refreshAccessToken === "function"
    ) {
      token = await this.getAccessToken(true);
      response = await sendOnce(token);
    }
    const { status, body } = response;
    if (status >= 200 && status < 300) {
      options.onProgress?.(100);
      return {
        ok: true,
        filename: body?.filename ? String(body.filename) : undefined,
        source_id: body?.source_id ? String(body.source_id) : undefined,
        wallpapers: Array.isArray(body?.wallpapers) ? (body.wallpapers) : undefined,
        system_wallpapers: Array.isArray(body?.system_wallpapers)
          ? (body.system_wallpapers)
          : undefined,
      };
    }
    const errMsg = body?.error
      ? String(body.error)
      : body?.message
        ? String(body.message)
        : `Wallpaper upload failed (HTTP ${status})`;
    throw new Error(errMsg);
  }
}

// --- src/state/dialogs-tools-ops.ts ---
/**
 * Security PIN, signing key rotation, diagnostics, modal dialogs (Remove/Reset/Add BLE/Color Wheel),
 * firmware update checks, announcements, backup/restore, and System & Device Logs operations.
 */
async function saveSecurityPinOp(store, fromScope) {
  const rawPin = (fromScope === "device" ? store.devicePinDraft : store.systemPinDraft).trim();
  if (!/^\d{4,12}$/.test(rawPin)) {
    store.showToast("Security PIN must be 4 to 12 digits", true);
    return;
  }
  const targetSubentryId = fromScope === "device" ? store.activeSubentryId : "";
  store.pinBusy = true;
  store.host.requestUpdate();
  try {
    const payload = { pin: rawPin };
    if (targetSubentryId) payload.subentry_id = targetSubentryId;
    const res = await store.ws.runSystemCommand(
      "set_security_pin",
      payload,
      store.activeSubentryId || null,
    );
    store.devicePinDraft = "";
    store.systemPinDraft = "";
    if (res) store.ingestPayload(res, false);
    store.showToast("Saved Security PIN");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not save Security PIN"), true);
  } finally {
    store.pinBusy = false;
    store.host.requestUpdate();
  }
}
async function clearSecurityPinOp(store, fromScope) {
  const targetSubentryId = fromScope === "device" ? store.activeSubentryId : "";
  store.pinBusy = true;
  store.host.requestUpdate();
  try {
    const payload = { clear: true };
    if (targetSubentryId) payload.subentry_id = targetSubentryId;
    const res = await store.ws.runSystemCommand(
      "set_security_pin",
      payload,
      store.activeSubentryId || null,
    );
    store.devicePinDraft = "";
    store.systemPinDraft = "";
    if (res) store.ingestPayload(res, false);
    store.showToast("Cleared Security PIN");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not clear Security PIN"), true);
  } finally {
    store.pinBusy = false;
    store.host.requestUpdate();
  }
}
async function rotateSigningKeyOp(store) {
  try {
    const res = await store.ws.runSystemCommand(
      "rotate_signing_key",
      {},
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Rotated HTTP resource signing key");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not rotate signing key"), true);
  }
}
async function downloadDeviceDiagnosticsOp(store) {
  const entryId = store.state?.links?.entry_id || "";
  const latterDeviceId = store.state?.links?.latter_device_id || "";
  if (!entryId) {
    store.showToast("Diagnostics entry ID is not available", true);
    return;
  }
  const rawPath = latterDeviceId
    ? `/api/diagnostics/config_entry/${encodeURIComponent(entryId)}/device/${encodeURIComponent(latterDeviceId)}`
    : `/api/diagnostics/config_entry/${encodeURIComponent(entryId)}`;
  try {
    const signedPath = await store.ws.signHaPath(rawPath, 300);
    const a = document.createElement("a");
    a.href = signedPath;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not download diagnostics"), true);
  }
}
function openColorWheelModalOp(store, targetScope) {
  const initial =
    targetScope === "device" && isValidHexColor(store.state?.config?.device_custom_color)
      ? String(store.state?.config?.device_custom_color).toUpperCase()
      : defaultThemeHex(store.host);
  store.colorWheelModal = {
    open: true,
    targetScope,
    hex: initial,
    name: "",
    busy: false,
  };
  store.host.requestUpdate();
}
async function saveColorWheelSelectionOp(store) {
  const hex = store.colorWheelModal.hex.trim().toUpperCase();
  if (!isValidHexColor(hex)) {
    store.showToast("Enter a valid 6-digit hex color", true);
    return;
  }
  const name = store.colorWheelModal.name.trim() || hex;
  const existing = [...(store.state?.system_config?.custom_palettes || [])];
  if (!existing.some((p) => p.hex.toUpperCase() === hex)) {
    existing.push({ name, hex });
    store.stageSystemSetting("custom_palettes", existing);
    await store.flushSystemSettings();
  }
  if (store.colorWheelModal.targetScope === "device" && store.activeSubentryId) {
    store.applyDeviceCustomColor(hex, true);
    await store.flushDeviceBucket(store.activeSubentryId);
  }
  store.closeColorWheelModal();
}
async function confirmRemoveDeviceOp(store) {
  const subId = store.removeModal.subentryId;
  if (!subId) return;
  store.removeModal = { ...store.removeModal, busy: true };
  store.host.requestUpdate();
  try {
    const res = await store.ws.runSystemCommand(
      "remove_device",
      { subentry_id: subId },
      store.activeSubentryId || null,
    );
    store.closeRemoveDeviceModal();
    if (store.activeSubentryId === subId) {
      store.activeSubentryId = "";
      store.deviceSelected = false;
      store.currentScope = "device";
      store.currentViewId = "select_device_prompt";
      store.syncUrl(true);
    }
    if (res) store.ingestPayload(res, false);
    store.showToast("Removed Device from Latter");
  } catch (err) {
    store.removeModal = { ...store.removeModal, busy: false };
    store.showToast(formatWsError(err, "Could not remove Device"), true);
    store.host.requestUpdate();
  }
}
async function confirmResetDeviceOp(store) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  if (!store.resetModal.deviceSettings && !store.resetModal.latterOptions) return;
  store.resetModal = { ...store.resetModal, busy: true };
  store.host.requestUpdate();
  try {
    const res = await store.ws.resetDevice({
      subentryId: targetSubentryId,
      deviceSettings: store.resetModal.deviceSettings,
      latterOptions: store.resetModal.latterOptions,
    });
    store.closeResetDeviceModal();
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast("Reset Device to defaults");
  } catch (err) {
    store.resetModal = { ...store.resetModal, busy: false };
    store.showToast(formatWsError(err, "Could not reset Device"), true);
    store.host.requestUpdate();
  }
}
function selectBleCandidateInModalOp(store, addr) {
  const cand = (store.state?.discovered_ble_devices || []).find(
    (c) => (c.target_address || c.address) === addr,
  );
  const candAddr = cand ? cand.target_address || cand.address || addr : addr;
  const candTitle = cand ? cand.title || cand.name || "" : "";
  store.addBleModal = {
    ...store.addBleModal,
    candidateAddr: addr,
    address: cand ? candAddr : store.addBleModal.address,
    name: candTitle || store.addBleModal.name,
  };
  store.host.requestUpdate();
}
async function adoptLatterDeviceOp(
  store,
  esphomeDeviceId,
  title,
  deviceGroup = "auto",
  assignedPerson = "",
) {
  if (!esphomeDeviceId) return;
  try {
    const res = await store.ws.runSystemCommand(
      "add_latter_device",
      {
        esphome_device_id: esphomeDeviceId,
        device_group: deviceGroup || "auto",
        assigned_person: assignedPerson,
      },
      store.activeSubentryId || null,
    );
    store.discoveredLatterGroupDrafts.delete(esphomeDeviceId);
    store.discoveredLatterPersonDrafts.delete(esphomeDeviceId);
    if (res) store.ingestPayload(res, false);
    store.showToast(`Added "${title || "Device"}" to Latter`);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not adopt Latter Device"), true);
  }
}
async function quickAdoptBleCandidateOp(
  store,
  title,
  targetAddress,
  assignedPerson = "",
) {
  if (!title || !targetAddress) return;
  try {
    const res = await store.ws.runSystemCommand(
      "add_ble_device",
      {
        name: title,
        target_address: targetAddress,
        assigned_person: assignedPerson,
      },
      store.activeSubentryId || null,
    );
    store.evictAdoptedBleCandidate(targetAddress);
    if (res) store.ingestPayload(res, false);
    store.showToast(`Added BLE tag "${title}"`);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not add BLE tag"), true);
  }
}
async function confirmAddBleModalOp(store) {
  const name = store.addBleModal.name.trim();
  const targetAddress = store.addBleModal.address.trim();
  if (!name || !targetAddress) {
    store.showToast("Enter both a name and a Bluetooth address or entity", true);
    return;
  }
  store.addBleModal = { ...store.addBleModal, busy: true };
  store.host.requestUpdate();
  try {
    const res = await store.ws.runSystemCommand(
      "add_ble_device",
      {
        name,
        target_address: targetAddress,
        assigned_person: store.addBleModal.assignedPerson,
      },
      store.activeSubentryId || null,
    );
    store.evictAdoptedBleCandidate(targetAddress);
    store.closeAddBleModal();
    if (res) store.ingestPayload(res, false);
    store.showToast(`Added BLE tag "${name}"`);
  } catch (err) {
    store.addBleModal = { ...store.addBleModal, busy: false };
    store.showToast(formatWsError(err, "Could not add BLE tag"), true);
    store.host.requestUpdate();
  }
}
async function checkSystemUpdatesOp(store) {
  store.showToast("Checking firmware updates…");
  try {
    const res = await store.ws.runSystemCommand(
      "check_system_updates",
      {},
      store.activeSubentryId || null,
    );
    if (res) {
      store.ingestPayload(res, false);
      const info = res.update_check;
      if (info) {
        store.showToast(
          info.available > 0
            ? `${info.available} firmware update(s) available across ${info.checked} checked Device(s)`
            : `Checked ${info.checked} Device(s) — all firmware is up to date`,
        );
        return;
      }
    }
    store.showToast("Firmware update check finished");
  } catch (err) {
    store.showToast(formatWsError(err, "Firmware update check failed"), true);
  }
}
async function sendAnnouncementOp(store) {
  const message = store.announceMessage.trim();
  if (!message) {
    store.showToast("Enter a message", true);
    return;
  }
  const payload = {
    mode: store.announceMode,
    target_device: store.announceTarget || "all",
    message,
  };
  if (store.announceMode === "notify") {
    const title = store.announceTitle.trim();
    if (!title) {
      store.showToast("Enter a notification title", true);
      return;
    }
    payload.title = title;
    payload.priority = store.announcePriority;
    payload.include_camera = store.announceIncludeCamera;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "send_announcement",
      payload,
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast(
      store.announceMode === "notify" ? "Sent notification" : "Broadcast announcement sent",
    );
  } catch (err) {
    store.showToast(formatWsError(err, "Could not send announcement"), true);
  }
}
async function exportBackupOp(store, explicitSubentryId) {
  try {
    const dateStr = new Date().toISOString().slice(0, 10);
    if (explicitSubentryId) {
      const { bundle } = await store.ws.exportBackup("device", explicitSubentryId);
      const slug = String(bundle.target_device || store.state?.config?.device_slug || "esphome");
      triggerJsonDownload(`latter-device-${slug}-backup-${dateStr}.json`, bundle);
      store.showToast("Downloaded the Device backup");
      return;
    }
    const choice = store.backupExportScope || "system";
    const deviceId = choice.startsWith("device:") ? choice.slice(7) : choice !== "system" ? choice : "";
    if (!deviceId) {
      const { bundle } = await store.ws.exportBackup("system");
      triggerJsonDownload(`latter-system-backup-${dateStr}.json`, bundle);
      store.showToast("Downloaded the System backup");
    } else {
      const { bundle } = await store.ws.exportBackup("device", deviceId);
      const slug = String(bundle.target_device || deviceId);
      triggerJsonDownload(`latter-device-${slug}-backup-${dateStr}.json`, bundle);
      store.showToast("Downloaded the Device backup");
    }
  } catch (err) {
    store.showToast(formatWsError(err, "Backup export failed"), true);
  }
}
async function restoreFromUploadedFileOp(store) {
  if (!store.selectedBackupFile) {
    store.showToast("Choose a JSON backup file first", true);
    return;
  }
  try {
    const text = await store.selectedBackupFile.text();
    const raw = JSON.parse(text);
    const bundle =
      raw.bundle && typeof raw.bundle === "object" ? (raw.bundle) : raw;
    const scope = String(bundle.scope || "") === "device" ? "device" : "system";
    const targetId = scope === "device" ? store.backupRestoreSubentryId || "" : "";
    if (scope === "device" && !targetId) {
      store.showToast("Choose the Device to restore this Device backup onto", true);
      return;
    }
    const res = await store.ws.importBackup({
      scope,
      bundle,
      targetSubentryId: targetId || null,
      selectedSubentryId: store.activeSubentryId || null,
    });
    store.selectedBackupFile = null;
    if (res) store.ingestPayload(res, false);
    store.showToast(scope === "device" ? "Restored the Device backup" : "Restored the System backup");
  } catch (err) {
    store.showToast(formatWsError(err, "Backup restore failed"), true);
  }
}
function formatVisibleLogsOp(store) {
  const entries = store.state?.internal_logs || [];
  const filter = store.logFilter || "all";
  const filtered = entries.filter((e) => {
    const lvl = String(e.level || "").toUpperCase();
    const src = String(e.source || "").toLowerCase();
    if (filter === "latter") return src === "studio" || src === "system" || src.includes("latter");
    if (filter === "errors") return lvl === "WARNING" || lvl === "WARN" || lvl === "ERROR" || lvl === "CRITICAL";
    if (filter.startsWith("device:") || filter.startsWith("dev:")) {
      const slug = (filter.startsWith("device:") ? filter.slice(7) : filter.slice(4)).toLowerCase();
      return src === slug || String(e.message || "").toLowerCase().includes(slug);
    }
    return true;
  });
  if (!filtered.length) return "No events logged yet.";
  return filtered
    .map((e) => {
      const rawTs = e.timestamp ?? e.ts ?? "";
      const formattedTs = rawTs !== "" ? fmtDateTime(rawTs, store.hass) : "";
      const lvl = String(e.level || "INFO").toUpperCase();
      const src = String(e.source || "latter");
      return `${formattedTs ? `[${formattedTs}] ` : ""}${lvl} (${src}): ${String(e.message || "")}`;
    })
    .join("\n");
}
async function copyLogsToClipboardOp(store) {
  const ok = await copyTextToClipboard(formatVisibleLogsOp(store));
  store.showToast(ok ? "Copied logs to clipboard" : "Could not copy logs", !ok);
}
async function clearInternalLogsOp(store) {
  try {
    const res = await store.ws.runSystemCommand(
      "clear_internal_logs",
      {},
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, true);
    store.showToast("Cleared internal logs");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not clear logs"), true);
  }
}

// --- src/state/entity-config-ops.ts ---
/**
 * Device & System configuration staging, optimistic ESPHome entity actions,
 * dock/activity/wallpaper/color mutations, and shared-entity list editors.
 */
const STRING_LIST_KEYS = [
  "calendar_entities",
  "camera_entities",
  "remotes_list",
];
const STRING_LIST_MAX_ITEMS = {
  camera_entities: 10,
  remotes_list: 10,
  calendar_entities: 50,
};
function isStringListKey(key) {
  return (
    key === "calendar_entities" ||
    key === "camera_entities" ||
    key === "remotes_list"
  );
}
function cleanPersistedStringList(items, maxItems) {
  const out = [];
  for (const raw of items) {
    const ent = String(raw || "").trim();
    if (ent && !out.includes(ent)) {
      out.push(ent);
      if (out.length >= maxItems) break;
    }
  }
  return out;
}
function mergePersistedWithBlankSlots(
  persisted,
  blankCount,
  maxItems,
  prevUiList,
) {
  const cleaned = cleanPersistedStringList(persisted, maxItems);
  const clampedBlankCount = Math.max(0, Math.min(blankCount, maxItems - cleaned.length));
  if (clampedBlankCount === 0) {
    return { uiList: cleaned, clampedBlankCount: 0 };
  }
  if (prevUiList && prevUiList.some((v) => !String(v || "").trim())) {
    const uiList = [];
    let cleanIdx = 0;
    let blanksPlaced = 0;
    for (const slot of prevUiList) {
      if (uiList.length >= maxItems) break;
      if (!String(slot || "").trim()) {
        if (blanksPlaced < clampedBlankCount) {
          uiList.push("");
          blanksPlaced += 1;
        }
      } else if (cleanIdx < cleaned.length) {
        uiList.push(cleaned[cleanIdx]);
        cleanIdx += 1;
      }
    }
    while (cleanIdx < cleaned.length && uiList.length < maxItems) {
      uiList.push(cleaned[cleanIdx]);
      cleanIdx += 1;
    }
    while (blanksPlaced < clampedBlankCount && uiList.length < maxItems) {
      uiList.push("");
      blanksPlaced += 1;
    }
    return { uiList, clampedBlankCount: blanksPlaced };
  }
  return {
    uiList: [...cleaned, ...Array (clampedBlankCount).fill("")],
    clampedBlankCount,
  };
}
function overlayPendingBlankListSlots(
  store,
  payload,
  prevSysConfig,
) {
  if (!payload.system_config) return;
  let mutated = false;
  const nextSys = { ...payload.system_config };
  for (const key of STRING_LIST_KEYS) {
    const wantBlanks = store.pendingBlankListSlots[key] || 0;
    if (wantBlanks <= 0) continue;
    const maxItems = STRING_LIST_MAX_ITEMS[key];
    const base = Array.isArray(nextSys[key]) ? nextSys[key] : [];
    const { uiList, clampedBlankCount } = mergePersistedWithBlankSlots(
      base,
      wantBlanks,
      maxItems,
      prevSysConfig?.[key],
    );
    store.pendingBlankListSlots[key] = clampedBlankCount;
    nextSys[key] = uiList;
    mutated = true;
  }
  if (mutated) {
    payload.system_config = nextSys;
  }
}
const SAVE_DEBOUNCE_MS = 220;
const ENTITY_OPTIMISTIC_TTL_MS = 8000;
const PENDING_ENTITY_STATES = new Map();
const BEHAVIOR_NON_PREF_KEY_SET = new Set (GROUP_BEHAVIOR_NON_PREF_KEYS);
const DISPLAY_NON_PREF_KEY_SET = new Set (GROUP_DISPLAY_NON_PREF_KEYS);
const INTERFACE_NON_PREF_KEY_SET = new Set (GROUP_INTERFACE_NON_PREF_KEYS);
function activeGroupKeySet(
  grp,
  devicePrefs,
) {
  const keys = new Set (BEHAVIOR_NON_PREF_KEY_SET);
  for (const p of devicePrefs) {
    if (p.group_tier === "behavior") keys.add(p.key);
    else if (p.group_tier === "display" && grp.include_display) keys.add(p.key);
    else if (p.group_tier === "interface" && grp.include_interface) keys.add(p.key);
  }
  if (grp.include_display) {
    for (const k of DISPLAY_NON_PREF_KEY_SET) keys.add(k);
  }
  if (grp.include_interface) {
    for (const k of INTERFACE_NON_PREF_KEY_SET) keys.add(k);
  }
  return keys;
}
function sameGroupControlVal(a, b) {
  if (a === b) return true;
  if ((Array.isArray(a) || (a && typeof a === "object")) || (Array.isArray(b) || (b && typeof b === "object"))) {
    return JSON.stringify(a) === JSON.stringify(b);
  }
  return String(a) === String(b);
}
function expandDevicePrefPatch(
  currentCfg,
  rawPatch,
) {
  const expanded = { ...rawPatch };
  if (rawPatch.home_screen_enabled === false) {
    const effStart = String(rawPatch.start_screen ?? currentCfg.start_screen ?? "Home");
    if (effStart === "Home") {
      expanded.start_screen = "Time App";
    }
  }
  return expanded;
}
function overlayDevicePrefsOnSections(
  payload,
  rawPatch,
) {
  if (!rawPatch || Object.keys(rawPatch).length === 0) return;
  const curCfg = (payload.config || {});
  const expanded = expandDevicePrefPatch(curCfg, rawPatch);
  const groups = payload.device_groups || [];
  const devicePrefs = payload.device_prefs || [];
  const supportedPrefKeys = new Set(devicePrefs.map((p) => p.key));
  const isRoaming = curCfg.is_roaming !== false;
  if ("device_group" in rawPatch) {
    const targetGrpId = String(rawPatch.device_group || "custom").trim() || "custom";
    expanded.device_group = targetGrpId;
    if (targetGrpId !== "custom") {
      const grp = groups.find((g) => g.id === targetGrpId);
      if (grp?.device_config) {
        const enforcedKeys = activeGroupKeySet(grp, devicePrefs);
        for (const [gk, gv] of Object.entries(grp.device_config)) {
          if (gk in rawPatch || gv === undefined || gv === null) continue;
          if (!enforcedKeys.has(gk)) continue;
          if ((gk === "sync_device_area" || gk === "area_follow_dwell_s") && !isRoaming) continue;
          if (
            BEHAVIOR_NON_PREF_KEY_SET.has(gk) ||
            DISPLAY_NON_PREF_KEY_SET.has(gk) ||
            INTERFACE_NON_PREF_KEY_SET.has(gk) ||
            supportedPrefKeys.has(gk)
          ) {
            expanded[gk] = gv;
          }
        }
      }
    }
  } else {
    const curGrpId = String(curCfg.device_group || "custom").trim() || "custom";
    if (curGrpId !== "custom") {
      const grp = groups.find((g) => g.id === curGrpId);
      if (grp?.device_config) {
        const enforcedKeys = activeGroupKeySet(grp, devicePrefs);
        for (const [ek, ev] of Object.entries(expanded)) {
          if ((ek === "sync_device_area" || ek === "area_follow_dwell_s") && !isRoaming) continue;
          if (
            enforcedKeys.has(ek) &&
            grp.device_config[ek] !== undefined &&
            !sameGroupControlVal(grp.device_config[ek], ev)
          ) {
            expanded.device_group = "custom";
            break;
          }
        }
      }
    }
  }
  payload.config = {
    ...payload.config,
    ...expanded,
  };
  if ("device_group" in expanded && Array.isArray(payload.system_devices) && payload.subentry_id) {
    const nextGrp = String(expanded.device_group || "custom");
    const nextGrpName =
      nextGrp === "custom"
        ? "Custom"
        : groups.find((g) => g.id === nextGrp)?.name || nextGrp;
    payload.system_devices = payload.system_devices.map((d) =>
      d.subentry_id === payload.subentry_id
        ? { ...d, device_group: nextGrp, device_group_name: nextGrpName }
        : d,
    );
  }
  if (payload.device_prefs) {
    payload.device_prefs = payload.device_prefs.map((p) => {
      if (p.key in expanded) {
        return { ...p, value: expanded[p.key] };
      }
      return p;
    });
  }
  const sections = payload?.esphome?.sections;
  if (!sections) return;
  payload.esphome = {
    ...payload.esphome,
    sections: sections.map((sec) => ({
      ...sec,
      items: (sec.items || []).map((item) => {
        if (item.pref_key && item.pref_key in expanded) {
          const val = expanded[item.pref_key];
          const nextState = item.domain === "switch" ? (val ? "on" : "off") : String(val ?? "");
          return { ...item, state: nextState };
        }
        if (
          "volume_step_size" in expanded &&
          item.domain === "number" &&
          item.entity_id.startsWith("media_player.")
        ) {
          const stepNum = Number(expanded.volume_step_size);
          if (Number.isFinite(stepNum) && stepNum > 0) {
            return { ...item, step: stepNum };
          }
        }
        return item;
      }),
    })),
  };
}
function overlayPendingEntityStates(
  payload,
  pendingMap = PENDING_ENTITY_STATES,
) {
  const now = Date.now();
  for (const [eid, entry] of pendingMap.entries()) {
    if (entry.expires <= now) {
      pendingMap.delete(eid);
    }
  }
  const sections = payload?.esphome?.sections;
  if (!sections || pendingMap.size === 0) return;
  payload.esphome = {
    ...payload.esphome,
    sections: sections.map((sec) => ({
      ...sec,
      items: (sec.items || []).map((item) => {
        const pending = pendingMap.get(item.entity_id);
        if (!pending) return item;
        const curState = String(item.state ?? "");
        const sameNumeric =
          curState !== "" &&
          pending.state !== "" &&
          Number.isFinite(Number(curState)) &&
          Number.isFinite(Number(pending.state)) &&
          Number(curState) === Number(pending.state);
        if (curState === pending.state || sameNumeric) {
          pendingMap.delete(item.entity_id);
          return item;
        }
        return { ...item, state: pending.state };
      }),
    })),
  };
}
async function commitEntityChange(
  store,
  entityId,
  optimisticState,
  body,
  errorPrefix,
) {
  return store.executeEntityAction(entityId, optimisticState, body, errorPrefix);
}
function stageDeviceSettingOp(
  store,
  key,
  value,
  controlDomId,
  debounceMs = SAVE_DEBOUNCE_MS,
) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  let bucket = store.pendingDeviceBuckets.get(targetSubentryId);
  if (!bucket) {
    bucket = {
      targetSubentryId,
      patch: {},
      previousValues: {},
      timer: null,
    };
    store.pendingDeviceBuckets.set(targetSubentryId, bucket);
  }
  const curCfg =
    store.state && store.state.subentry_id === targetSubentryId
      ? ((store.state.config || {}))
      : {};
  const snapshotKey = (k) => {
    if (!(k in bucket.previousValues)) {
      bucket.previousValues[k] = curCfg[k];
    }
  };
  snapshotKey(key);
  snapshotKey("device_group");
  if (key === "home_screen_enabled") {
    snapshotKey("start_screen");
  }
  if (controlDomId) {
    bucket.previousValues[`__dom:${controlDomId}`] = bucket.previousValues[key];
  }
  bucket.patch[key] = value;
  if (store.state) {
    const nextSystemDevices =
      key === "device_remote_group" && Array.isArray(store.state.system_devices)
        ? store.state.system_devices.map((d) =>
            d.subentry_id === targetSubentryId
              ? { ...d, device_remote_group: String(value || "area_auto") }
              : d,
          )
        : store.state.system_devices;
    if (store.state.subentry_id === targetSubentryId) {
      const nextPayload = {
        ...store.state,
        system_devices: nextSystemDevices,
        config: { ...store.state.config },
      };
      overlayDevicePrefsOnSections(nextPayload, { [key]: value });
      store.state = nextPayload;
    } else if (nextSystemDevices !== store.state.system_devices) {
      store.state = {
        ...store.state,
        system_devices: nextSystemDevices,
      };
    }
  }
  if (bucket.timer) clearTimeout(bucket.timer);
  bucket.timer = setTimeout(() => {
    void store.flushDeviceBucket(targetSubentryId);
  }, Math.max(0, debounceMs));
  store.host.requestUpdate();
}
async function flushDeviceBucketOp(store, targetSubentryId) {
  const bucket = store.pendingDeviceBuckets.get(targetSubentryId);
  if (!bucket) return;
  if (bucket.timer) {
    clearTimeout(bucket.timer);
    bucket.timer = null;
  }
  const patch = { ...bucket.patch };
  const previousValues = { ...bucket.previousValues };
  store.pendingDeviceBuckets.delete(targetSubentryId);
  if (Object.keys(patch).length === 0) return;
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "save_device_config", {
      config: patch,
    });
    if (res) {
      if (store.activeSubentryId === targetSubentryId) {
        store.ingestPayload(res, false);
      } else if (store.state && Array.isArray(res.system_devices)) {
        store.state = {
          ...store.state,
          system_devices: res.system_devices,
          issues: res.issues ?? store.state.issues,
        };
        store.host.requestUpdate();
      }
    }
    store.showToast("Saved");
  } catch (err) {
    const controlRevert = {};
    for (const [k, v] of Object.entries(previousValues)) {
      if (k.startsWith("__dom:")) {
        const domId = k.slice(6);
        if (typeof v === "boolean") controlRevert[domId] = v;
        else if (v !== undefined && v !== null) controlRevert[domId] = String(v);
        else controlRevert[domId] = "";
      }
    }
    if (store.state) {
      const nextSystemDevices =
        "device_remote_group" in previousValues && Array.isArray(store.state.system_devices)
          ? store.state.system_devices.map((d) =>
              d.subentry_id === targetSubentryId
                ? {
                    ...d,
                    device_remote_group: String(previousValues.device_remote_group || "area_auto"),
                  }
                : d,
            )
          : store.state.system_devices;
      if (store.state.subentry_id === targetSubentryId) {
        const restoredConfig = {
          ...(store.state.config),
        };
        const restoredPrefs = {};
        for (const [k, v] of Object.entries(previousValues)) {
          if (!k.startsWith("__dom:")) {
            restoredConfig[k] = v;
            if (v !== undefined) {
              restoredPrefs[k] = v;
            }
          }
        }
        const nextPayload = {
          ...store.state,
          system_devices: nextSystemDevices,
          config: restoredConfig,
        };
        if (Object.keys(restoredPrefs).length > 0) {
          overlayDevicePrefsOnSections(nextPayload, restoredPrefs);
        }
        store.state = nextPayload;
      } else if (nextSystemDevices !== store.state.system_devices) {
        store.state = {
          ...store.state,
          system_devices: nextSystemDevices,
        };
      }
    }
    if (Object.keys(controlRevert).length > 0) {
      store.pendingDomRevert = { controlIds: controlRevert };
    }
    store.showToast(formatWsError(err, "Could not save Device settings"), true);
    store.host.requestUpdate();
  }
}
function stageSystemSettingOp(
  store,
  key,
  value,
  controlDomId,
) {
  if (!(key in store.pendingSystemPrevious)) {
    const prev = (store.state?.system_config)?.[key];
    if (isStringListKey(key) && Array.isArray(prev)) {
      store.pendingSystemPrevious[key] = cleanPersistedStringList(prev, STRING_LIST_MAX_ITEMS[key]);
    } else {
      store.pendingSystemPrevious[key] = prev !== undefined ? structuredClone(prev) : undefined;
    }
  }
  if (controlDomId && !(`__dom:${controlDomId}` in store.pendingSystemPrevious)) {
    const prevScalar = store.pendingSystemPrevious[key];
    if (typeof prevScalar === "string" || typeof prevScalar === "number" || typeof prevScalar === "boolean") {
      store.pendingSystemPrevious[`__dom:${controlDomId}`] = prevScalar;
    }
  }
  store.pendingSystemPatch[key] = value;
  if (store.state?.system_config) {
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: value,
      },
    };
  }
  if (store.systemSaveTimer) clearTimeout(store.systemSaveTimer);
  store.systemSaveTimer = setTimeout(() => {
    void store.flushSystemSettings();
  }, SAVE_DEBOUNCE_MS);
  store.host.requestUpdate();
}
async function flushSystemSettingsOp(store) {
  if (store.systemSaveTimer) {
    clearTimeout(store.systemSaveTimer);
    store.systemSaveTimer = null;
  }
  const patch = { ...store.pendingSystemPatch };
  const previousValues = { ...store.pendingSystemPrevious };
  store.pendingSystemPatch = {};
  store.pendingSystemPrevious = {};
  if (Object.keys(patch).length === 0) return;
  try {
    const res = await store.ws.runSystemCommand(
      "save_system_config",
      { config: patch },
      store.activeSubentryId || null,
    );
    if (res) {
      store.ingestPayload(res, false);
    }
    store.showToast("Saved System settings");
  } catch (err) {
    const controlRevert = {};
    if (store.state?.system_config) {
      const prevUiSys = store.state.system_config;
      const restored = {
        ...(prevUiSys),
      };
      for (const [k, v] of Object.entries(previousValues)) {
        if (k.startsWith("__dom:")) {
          const domId = k.slice(6);
          controlRevert[domId] = typeof v === "boolean" ? v : String(v ?? "");
        } else if (v !== undefined) {
          restored[k] = v;
        }
      }
      const nextPayload = {
        ...store.state,
        system_config: restored,
      };
      overlayPendingBlankListSlots(store, nextPayload, prevUiSys);
      store.state = nextPayload;
    }
    if (Object.keys(controlRevert).length > 0) {
      store.pendingDomRevert = { controlIds: controlRevert };
    }
    store.showToast(formatWsError(err, "Could not save System settings"), true);
    store.host.requestUpdate();
  }
}
function currentEntityState(store, entityId) {
  for (const sec of store.state?.esphome?.sections || []) {
    for (const it of sec.items || []) {
      if (it.entity_id === entityId) return it.state;
    }
  }
  return "";
}
function applyOptimisticEntity(store, entityId, nextState) {
  const prev = currentEntityState(store, entityId);
  store.pendingEntityStates.set(entityId, {
    state: nextState,
    previousValue: prev,
    expires: Date.now() + ENTITY_OPTIMISTIC_TTL_MS,
  });
  if (store.state?.esphome?.sections) {
    const nextPayload = { ...store.state };
    overlayPendingEntityStates(nextPayload, store.pendingEntityStates);
    store.state = nextPayload;
    store.host.requestUpdate();
  }
  return prev;
}
function rollbackOptimisticEntity(store, entityId, prev) {
  store.pendingEntityStates.delete(entityId);
  if (store.state?.esphome?.sections) {
    store.state = {
      ...store.state,
      esphome: {
        ...store.state.esphome,
        sections: store.state.esphome.sections.map((sec) => ({
          ...sec,
          items: (sec.items || []).map((it) => (it.entity_id === entityId ? { ...it, state: prev } : it)),
        })),
      },
    };
  }
  store.host.requestUpdate();
}
async function executeEntityActionOp(
  store,
  entityId,
  optimisticState,
  body,
  errorPrefix,
) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId || !entityId) return false;
  const prev = optimisticState !== undefined ? applyOptimisticEntity(store, entityId, optimisticState) : "";
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "esphome_entity_action", {
      entity_id: entityId,
      ...body,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    return true;
  } catch (err) {
    if (optimisticState !== undefined) rollbackOptimisticEntity(store, entityId, prev);
    store.showToast(formatWsError(err, errorPrefix), true);
    return false;
  }
}
async function runDeviceActionOp(
  store,
  action,
  toastMessage,
) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId || !action) return false;
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "device_action", {
      action,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    if (toastMessage) {
      store.showToast(toastMessage);
    }
    return true;
  } catch (err) {
    store.showToast(formatWsError(err, "Device action failed"), true);
    return false;
  }
}
function sanitizeShortcutLabel(raw) {
  const str = String(raw ?? "");
  let collapsed = "";
  let prevSpace = true;
  for (const ch of str) {
    const code = ch.charCodeAt(0);
    if (
      code < 0x20 ||
      code === 0x7f ||
      ch === "|" ||
      ch === "\x1e" ||
      ch === "\x1f" ||
      ch === " " ||
      ch === "\t" ||
      ch === "\r" ||
      ch === "\n"
    ) {
      if (!prevSpace) {
        collapsed += " ";
        prevSpace = true;
      }
      continue;
    }
    collapsed += ch;
    prevSpace = false;
  }
  const trimmed = collapsed.trim();
  return trimmed.length > SHORTCUT_LABEL_MAX
    ? trimmed.slice(0, SHORTCUT_LABEL_MAX).trimEnd()
    : trimmed;
}
function defaultDockShortcutItems() {
  return DEFAULT_DOCK_ROUTES_TOKENS.map((tok) => ({
    kind: "route",
    target: tok,
    action: "",
    label: "",
    icon: "",
    confirm: false,
  }));
}
function normalizeShortcutArray(
  raw,
  isDock,
) {
  if (!Array.isArray(raw)) {
    return isDock ? defaultDockShortcutItems() : [];
  }
  const knownRoutes = new Map(SHORTCUT_ROUTES_CATALOG.map((r) => [r.token, r]));
  const maxItems = isDock ? MAX_DOCK_ITEMS : MAX_PINNED_ITEMS;
  const out = [];
  const seen = new Set();
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const rec = entry;
    const kind = String(rec.kind || "").trim().toLowerCase();
    if (kind === "route") {
      const target = String(rec.target || "").trim().toLowerCase();
      if (isDock && (target === "settings:root" || target === "app:settings")) {
        continue;
      }
      const spec = knownRoutes.get(target);
      if (!spec || (!isDock && spec.dockOnly)) continue;
      const dedupKey = `route|${target}|`;
      if (seen.has(dedupKey)) continue;
      seen.add(dedupKey);
      out.push({
        kind: "route",
        target,
        action: "",
        label: sanitizeShortcutLabel(rec.label),
        icon: normalizeMdiIconSlug(rec.icon),
        confirm: false,
      });
    } else if (kind === "entity") {
      const target = String(rec.target || "").trim().toLowerCase();
      const dotIdx = target.indexOf(".");
      if (dotIdx <= 0) continue;
      const domain = target.slice(0, dotIdx);
      const validActions = SHORTCUT_DOMAIN_ACTIONS[domain];
      if (!validActions || validActions.length === 0) continue;
      const rawAct = String(rec.action || "").trim().toLowerCase();
      const action = validActions.some((a) => a.action === rawAct)
        ? rawAct
        : validActions[0].action;
      const dedupKey = `entity|${target}|${action}`;
      if (seen.has(dedupKey)) continue;
      seen.add(dedupKey);
      out.push({
        kind: "entity",
        target,
        action,
        label: sanitizeShortcutLabel(rec.label),
        icon: normalizeMdiIconSlug(rec.icon),
        confirm: rec.confirm === undefined ? isDock : Boolean(rec.confirm),
      });
    }
    if (out.length >= maxItems) break;
  }
  return out;
}
function getDockItemsOp(store) {
  const raw = store.state?.config?.dock_items;
  if (raw === undefined || raw === null) {
    return defaultDockShortcutItems();
  }
  return normalizeShortcutArray(raw, true);
}
function getPinnedItemsOp(store) {
  const raw = store.state?.config?.pinned_items;
  if (raw === undefined || raw === null) {
    return [];
  }
  return normalizeShortcutArray(raw, false);
}
function moveShortcutItemOp(
  store,
  listKey,
  idx,
  delta,
) {
  const current = listKey === "dock_items" ? getDockItemsOp(store) : getPinnedItemsOp(store);
  const nextIdx = idx + delta;
  if (idx < 0 || nextIdx < 0 || idx >= current.length || nextIdx >= current.length) {
    return;
  }
  const next = current.map((it) => ({ ...it }));
  const [moved] = next.splice(idx, 1);
  next.splice(nextIdx, 0, moved);
  store.stageDeviceSetting(listKey, next);
}
function removeShortcutItemOp(
  store,
  listKey,
  idx,
) {
  const current = listKey === "dock_items" ? getDockItemsOp(store) : getPinnedItemsOp(store);
  if (idx < 0 || idx >= current.length) return;
  const next = current.filter((_, i) => i !== idx).map((it) => ({ ...it }));
  store.stageDeviceSetting(listKey, next);
}
function resetDockItemsToDefaultOp(store) {
  store.stageDeviceSetting("dock_items", defaultDockShortcutItems());
  store.showToast("Restored default App Dock");
}
function openShortcutModalOp(
  store,
  listKey,
  editIndex = null,
) {
  const isDock = listKey === "dock_items";
  const current = isDock ? getDockItemsOp(store) : getPinnedItemsOp(store);
  const caps = store.state?.capabilities || {};
  const compatibleRoutes = SHORTCUT_ROUTES_CATALOG.filter((r) => {
    if (!isDock && r.dockOnly) return false;
    if (isDock && r.token === "settings:root") return false;
    if (r.capability === "round" && caps.is_round === false) return false;
    if (r.capability === "imu" && caps.has_imu === false) return false;
    return true;
  });
  const firstRoute = compatibleRoutes[0]?.token || "weather:moon";
  const entities = store.state?.catalog?.shortcut_entities || [];
  const firstEnt = entities[0];
  const firstDomain = firstEnt ? firstEnt.domain : "light";
  const firstAction = SHORTCUT_DOMAIN_ACTIONS[firstDomain]?.[0]?.action || "toggle";
  if (editIndex !== null && editIndex >= 0 && editIndex < current.length) {
    const existing = current[editIndex];
    if (existing.kind === "entity") {
      const dom = existing.target.split(".", 1)[0] || firstDomain;
      store.shortcutModal = {
        open: true,
        listKey,
        editIndex,
        kind: "entity",
        routeTarget: firstRoute,
        entityDomainFilter: "all",
        entitySearch: "",
        entityTarget: existing.target,
        action: existing.action || SHORTCUT_DOMAIN_ACTIONS[dom]?.[0]?.action || "toggle",
        label: existing.label,
        icon: existing.icon,
        iconSearch: "",
        confirm: Boolean(existing.confirm),
      };
    } else {
      store.shortcutModal = {
        open: true,
        listKey,
        editIndex,
        kind: "route",
        routeTarget: existing.target,
        entityDomainFilter: "all",
        entitySearch: "",
        entityTarget: firstEnt?.id || "",
        action: firstAction,
        label: existing.label,
        icon: existing.icon,
        iconSearch: "",
        confirm: isDock,
      };
    }
  } else {
    store.shortcutModal = {
      open: true,
      listKey,
      editIndex: null,
      kind: isDock ? "route" : (entities.length > 0 ? "entity" : "route"),
      routeTarget: firstRoute,
      entityDomainFilter: "all",
      entitySearch: "",
      entityTarget: firstEnt?.id || "",
      action: firstAction,
      label: "",
      icon: "",
      iconSearch: "",
      confirm: isDock,
    };
  }
  store.host.requestUpdate();
}
function saveShortcutModalOp(store) {
  const modal = store.shortcutModal;
  const isDock = modal.listKey === "dock_items";
  const maxItems = isDock ? MAX_DOCK_ITEMS : MAX_PINNED_ITEMS;
  const current = (isDock ? getDockItemsOp(store) : getPinnedItemsOp(store)).map((it) => ({
    ...it,
  }));
  if (modal.editIndex === null && current.length >= maxItems) {
    store.showToast(
      `${isDock ? "App Dock" : "Pinned App"} supports up to ${maxItems} shortcuts`,
      true,
    );
    return;
  }
  const rawSelectedIcon = modal.icon.trim();
  const rawTypedIcon = modal.iconSearch.trim();
  let cleanIcon = "";
  if (rawSelectedIcon) {
    const candidate = normalizeMdiIconSlug(rawSelectedIcon);
    if (!candidate || !isKnownMdiIcon(candidate)) {
      store.showToast("Select a supported Material Design Icon", true);
      return;
    }
    cleanIcon = candidate;
  } else if (rawTypedIcon) {
    const candidate = normalizeMdiIconSlug(rawTypedIcon);
    if (candidate && isKnownMdiIcon(candidate)) {
      cleanIcon = candidate;
    } else {
      store.showToast("Click one of the matching icons below (or clear the icon search)", true);
      return;
    }
  }
  const cleanLabel = sanitizeShortcutLabel(modal.label);
  let built;
  if (modal.kind === "route") {
    const routeTok = modal.routeTarget.trim().toLowerCase();
    const spec = SHORTCUT_ROUTES_CATALOG.find((r) => r.token === routeTok);
    if (!spec || (!isDock && spec.dockOnly) || (isDock && routeTok === "settings:root")) {
      store.showToast("Select an app or page to pin", true);
      return;
    }
    built = {
      kind: "route",
      target: routeTok,
      action: "",
      label: cleanLabel,
      icon: cleanIcon,
      confirm: false,
    };
  } else {
    const entId = modal.entityTarget.trim().toLowerCase();
    const dotIdx = entId.indexOf(".");
    if (dotIdx <= 0) {
      store.showToast("Select a Home Assistant entity", true);
      return;
    }
    const dom = entId.slice(0, dotIdx);
    const validActs = SHORTCUT_DOMAIN_ACTIONS[dom] || [];
    const act = validActs.some((a) => a.action === modal.action)
      ? modal.action
      : (validActs[0]?.action || "");
    if (!act) {
      store.showToast(`Unsupported entity domain '${dom}'`, true);
      return;
    }
    built = {
      kind: "entity",
      target: entId,
      action: act,
      label: cleanLabel,
      icon: cleanIcon,
      confirm: Boolean(modal.confirm),
    };
  }
  const dupIdx = current.findIndex(
    (it, idx) =>
      idx !== modal.editIndex &&
      it.kind === built.kind &&
      it.target === built.target &&
      it.action === built.action,
  );
  if (dupIdx >= 0) {
    store.showToast("That shortcut is already in this list", true);
    return;
  }
  if (modal.editIndex !== null && modal.editIndex >= 0 && modal.editIndex < current.length) {
    current[modal.editIndex] = built;
  } else {
    current.push(built);
  }
  store.shortcutModal = { ...store.shortcutModal, open: false };
  store.stageDeviceSetting(modal.listKey, current);
}
function getEnabledAreaCategoriesOp(store) {
  const raw = String(store.state?.config?.area_categories ?? "");
  if (!raw.trim()) {
    return [...DEFAULT_AREA_CATEGORIES_TOKENS];
  }
  const known = new Set(AREA_CATEGORIES_CATALOG.map((c) => c.token));
  const parsed = raw
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter((s, i, arr) => Boolean(s) && known.has(s) && arr.indexOf(s) === i);
  return parsed.length > 0 ? parsed : [...DEFAULT_AREA_CATEGORIES_TOKENS];
}
function toggleAreaCategoryTokenOp(store, token) {
  const current = getEnabledAreaCategoriesOp(store);
  const idx = current.indexOf(token);
  if (idx >= 0) {
    if (current.length <= 1) {
      store.showToast("Keep at least one Area category enabled", true);
      return;
    }
    current.splice(idx, 1);
  } else {
    current.push(token);
  }
  store.stageDeviceSetting("area_categories", current.join(","));
}
function moveAreaCategoryTokenOp(store, token, delta) {
  const current = getEnabledAreaCategoriesOp(store);
  const idx = current.indexOf(token);
  const nextIdx = idx + delta;
  if (idx < 0 || nextIdx < 0 || nextIdx >= current.length) return;
  const [moved] = current.splice(idx, 1);
  current.splice(nextIdx, 0, moved);
  store.stageDeviceSetting("area_categories", current.join(","));
}
function getEnabledHomeCategoriesOp(store) {
  const raw = String(store.state?.config?.home_categories ?? "");
  if (!raw.trim()) {
    return [...DEFAULT_HOME_CATEGORIES_TOKENS];
  }
  const known = new Set(HOME_CATEGORIES_CATALOG.map((c) => c.token));
  const parsed = raw
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter((s, i, arr) => Boolean(s) && known.has(s) && arr.indexOf(s) === i);
  return parsed.length > 0 ? parsed : [...DEFAULT_HOME_CATEGORIES_TOKENS];
}
function toggleHomeCategoryTokenOp(store, token) {
  const current = getEnabledHomeCategoriesOp(store);
  const idx = current.indexOf(token);
  if (idx >= 0) {
    if (current.length <= 1) {
      store.showToast("Keep at least one Home category enabled", true);
      return;
    }
    current.splice(idx, 1);
  } else {
    current.push(token);
  }
  store.stageDeviceSetting("home_categories", current.join(","));
}
function moveHomeCategoryTokenOp(store, token, delta) {
  const current = getEnabledHomeCategoriesOp(store);
  const idx = current.indexOf(token);
  const nextIdx = idx + delta;
  if (idx < 0 || nextIdx < 0 || nextIdx >= current.length) return;
  const [moved] = current.splice(idx, 1);
  current.splice(nextIdx, 0, moved);
  store.stageDeviceSetting("home_categories", current.join(","));
}
function getEnabledActivitySourcesOp(store) {
  const rawCfg = store.state?.config?.activity_sources;
  if (rawCfg === undefined || rawCfg === null) {
    return ACTIVITY_SOURCES_CATALOG.map((s) => s.token);
  }
  return String(rawCfg)
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}
function toggleActivitySourceOp(store, sourceId) {
  const current = getEnabledActivitySourcesOp(store);
  const idx = current.indexOf(sourceId);
  if (idx >= 0) {
    current.splice(idx, 1);
  } else {
    current.push(sourceId);
  }
  store.stageDeviceSetting("activity_sources", current.join(","));
}
function applyDeviceCustomColorOp(
  store,
  hex,
  switchColorProfile = true,
) {
  if (!isValidHexColor(hex)) return;
  store.stageDeviceSetting("device_custom_color", hex.toUpperCase());
  if (switchColorProfile) {
    store.stageDeviceSetting("color_profile", "Custom");
  }
}
function deleteCustomPaletteOp(store, hex) {
  const target = hex.toUpperCase();
  const next = (store.state?.system_config?.custom_palettes || []).filter(
    (p) => p.hex.toUpperCase() !== target,
  );
  store.stageSystemSetting("custom_palettes", next);
}
async function uploadWallpaperOp(store, scope) {
  const file = scope === "device" ? store.selectedDeviceWallpaperFile : store.selectedSystemWallpaperFile;
  if (!file) {
    store.showToast("Choose an image file first", true);
    return;
  }
  const targetSubentryId = scope === "device" ? store.activeSubentryId : undefined;
  if (scope === "device" && !targetSubentryId) {
    store.showToast("Choose a Device first", true);
    return;
  }
  store.uploadScope = scope;
  store.uploadBusy = true;
  store.uploadPercent = 0;
  store.host.requestUpdate();
  try {
    const result = await store.ws.uploadWallpaperMultipart({
      scope,
      subentryId: targetSubentryId,
      file,
      onProgress: (pct) => {
        store.uploadPercent = pct;
        store.host.requestUpdate();
      },
    });
    if (scope === "device") {
      store.selectedDeviceWallpaperFile = null;
    } else {
      store.selectedSystemWallpaperFile = null;
    }
    const inputId = scope === "device" ? "input-upload-wp" : "input-upload-sys-wp";
    store.pendingDomRevert = {
      controlIds: { ...(store.pendingDomRevert?.controlIds || {}), [inputId]: "" },
    };
    if (store.state) {
      if (result.wallpapers && scope === "device" && store.activeSubentryId === targetSubentryId) {
        store.state = { ...store.state, wallpapers: result.wallpapers };
      }
      if (result.system_wallpapers) {
        store.state = { ...store.state, system_wallpapers: result.system_wallpapers };
      }
    }
    await store.refreshState();
    store.showToast("Uploaded wallpaper");
  } catch (err) {
    store.showToast(formatWsError(err, "Wallpaper upload failed"), true);
  } finally {
    store.uploadBusy = false;
    store.uploadScope = null;
    store.uploadPercent = 0;
    store.host.requestUpdate();
  }
}
function clearPendingWallpaperCycle(store, targetSubentryId) {
  const bucket = store.pendingDeviceBuckets.get(targetSubentryId);
  if (!bucket || !("wallpaper_cycle_minutes" in bucket.patch)) return;
  delete bucket.patch.wallpaper_cycle_minutes;
  delete bucket.previousValues.wallpaper_cycle_minutes;
  delete bucket.previousValues["__dom:cfg-wallpaper_cycle_minutes"];
  if (Object.keys(bucket.patch).length === 0) {
    if (bucket.timer) clearTimeout(bucket.timer);
    store.pendingDeviceBuckets.delete(targetSubentryId);
  }
}
async function selectWallpaperSourceOp(store, sourceId) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  clearPendingWallpaperCycle(store, targetSubentryId);
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "select_wallpaper", {
      source_id: sourceId,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast(sourceId ? "Wallpaper applied" : "Wallpaper turned off");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not select wallpaper"), true);
  }
}
async function setWallpaperRotationOp(store, minutes) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  const cleanMins = Math.max(0, Math.round(Number(minutes) || 0));
  clearPendingWallpaperCycle(store, targetSubentryId);
  const prevMins =
    store.state && store.state.subentry_id === targetSubentryId
      ? Number(store.state.config?.wallpaper_cycle_minutes || 0)
      : 0;
  if (store.state && store.state.subentry_id === targetSubentryId) {
    store.state = {
      ...store.state,
      config: {
        ...store.state.config,
        wallpaper_cycle_minutes: cleanMins,
      },
    };
    store.host.requestUpdate();
  }
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "save_device_config", {
      config: { wallpaper_cycle_minutes: cleanMins },
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast(cleanMins > 0 ? "Wallpaper rotation enabled" : "Wallpaper rotation stopped");
  } catch (err) {
    if (store.state && store.state.subentry_id === targetSubentryId) {
      store.state = {
        ...store.state,
        config: {
          ...store.state.config,
          wallpaper_cycle_minutes: prevMins,
        },
      };
      store.pendingDomRevert = {
        controlIds: {
          ...(store.pendingDomRevert?.controlIds || {}),
          "cfg-wallpaper_cycle_minutes": String(prevMins),
        },
      };
      store.host.requestUpdate();
    }
    store.showToast(formatWsError(err, "Could not update wallpaper rotation"), true);
  }
}
async function toggleWallpaperFavOp(store, sourceId) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "toggle_wallpaper_favorite", {
      source_id: sourceId,
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update favorite"), true);
  }
}
async function setAllWallpaperFavoritesOp(
  store,
  sourceIds,
) {
  const targetSubentryId = store.activeSubentryId;
  if (!targetSubentryId) return;
  try {
    const res = await store.ws.runDeviceCommand(targetSubentryId, "toggle_wallpaper_favorite", {
      source_ids: [...sourceIds],
    });
    if (res && store.activeSubentryId === targetSubentryId) {
      store.ingestPayload(res, false);
    }
    store.showToast(
      sourceIds.length > 0 ? "Starred all wallpapers" : "Cleared starred wallpapers",
    );
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update favorites"), true);
  }
}
async function deleteWallpaperOp(
  store,
  scope,
  sourceId,
) {
  try {
    if (scope === "device") {
      const targetSubentryId = store.activeSubentryId;
      if (!targetSubentryId) return;
      const res = await store.ws.runDeviceCommand(targetSubentryId, "delete_wallpaper", {
        source_id: sourceId,
      });
      if (res && store.activeSubentryId === targetSubentryId) {
        store.ingestPayload(res, false);
      }
    } else {
      const res = await store.ws.runSystemCommand(
        "delete_system_wallpaper",
        { source_id: sourceId },
        store.activeSubentryId || null,
      );
      if (res) store.ingestPayload(res, false);
    }
    store.showToast("Deleted wallpaper");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not delete wallpaper"), true);
  }
}
function updateStringListRowOp(
  store,
  key,
  index,
  value,
) {
  const maxItems = STRING_LIST_MAX_ITEMS[key];
  const prevUiList = [...(store.state?.system_config?.[key] || [])];
  if (index < 0 || index >= prevUiList.length) return;
  const prevPersisted = cleanPersistedStringList(prevUiList, maxItems);
  const nextRaw = [...prevUiList];
  nextRaw[index] = String(value || "").trim();
  const seen = new Set();
  const nextUiList = [];
  for (const item of nextRaw) {
    const ent = String(item || "").trim();
    if (!ent) {
      nextUiList.push("");
    } else if (!seen.has(ent)) {
      seen.add(ent);
      nextUiList.push(ent);
    }
    if (nextUiList.length >= maxItems) break;
  }
  const nextPersisted = nextUiList.filter(Boolean);
  store.pendingBlankListSlots[key] = nextUiList.length - nextPersisted.length;
  const persistedChanged =
    prevPersisted.length !== nextPersisted.length ||
    prevPersisted.some((v, i) => v !== nextPersisted[i]);
  if (persistedChanged) {
    store.stageSystemSetting(key, nextPersisted);
    if (store.state?.system_config && store.pendingBlankListSlots[key] > 0) {
      store.state = {
        ...store.state,
        system_config: {
          ...store.state.system_config,
          [key]: nextUiList,
        },
      };
      store.host.requestUpdate();
    }
  } else if (store.state?.system_config) {
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: nextUiList,
      },
    };
    store.host.requestUpdate();
  }
}
function addStringListRowOp(
  store,
  key,
  defaultEntity = "",
  maxLen = STRING_LIST_MAX_ITEMS[key],
) {
  const cap = Math.min(maxLen, STRING_LIST_MAX_ITEMS[key]);
  const list = [...(store.state?.system_config?.[key] || [])];
  if (list.length >= cap) {
    store.showToast(`Maximum of ${cap} entries reached`, true);
    return;
  }
  const cleanDefault = String(defaultEntity || "").trim();
  if (!cleanDefault) {
    list.push("");
    store.pendingBlankListSlots[key] = list.filter((s) => !String(s || "").trim()).length;
    if (store.state?.system_config) {
      store.state = {
        ...store.state,
        system_config: {
          ...store.state.system_config,
          [key]: list,
        },
      };
    }
    store.host.requestUpdate();
    return;
  }
  const nextPersisted = cleanPersistedStringList([...list, cleanDefault], cap);
  const wantBlanks = Math.max(
    0,
    Math.min(store.pendingBlankListSlots[key] || 0, cap - nextPersisted.length),
  );
  store.pendingBlankListSlots[key] = wantBlanks;
  store.stageSystemSetting(key, nextPersisted);
  if (store.state?.system_config && wantBlanks > 0) {
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: [...nextPersisted, ...Array (wantBlanks).fill("")],
      },
    };
    store.host.requestUpdate();
  }
}
function removeStringListRowOp(
  store,
  key,
  index,
) {
  const maxItems = STRING_LIST_MAX_ITEMS[key];
  const list = [...(store.state?.system_config?.[key] || [])];
  if (index < 0 || index >= list.length) return;
  const [removed] = list.splice(index, 1);
  const wasBlank = !String(removed || "").trim();
  store.pendingBlankListSlots[key] = list.filter((s) => !String(s || "").trim()).length;
  if (wasBlank) {
    if (store.state?.system_config) {
      store.state = {
        ...store.state,
        system_config: {
          ...store.state.system_config,
          [key]: list,
        },
      };
    }
    store.host.requestUpdate();
    return;
  }
  const nextPersisted = cleanPersistedStringList(list, maxItems);
  store.stageSystemSetting(key, nextPersisted);
  if (store.state?.system_config && store.pendingBlankListSlots[key] > 0) {
    const { uiList, clampedBlankCount } = mergePersistedWithBlankSlots(
      nextPersisted,
      store.pendingBlankListSlots[key],
      maxItems,
      list,
    );
    store.pendingBlankListSlots[key] = clampedBlankCount;
    store.state = {
      ...store.state,
      system_config: {
        ...store.state.system_config,
        [key]: uiList,
      },
    };
    store.host.requestUpdate();
  }
}
function addVolumeOverrideRowOp(store) {
  const list = [...(store.state?.system_config?.volume_overrides || [])];
  if (list.length >= 10) {
    store.showToast("Maximum of 10 volume overrides reached", true);
    return;
  }
  const speakers = store.state?.catalog?.ma_speakers || [];
  const targets = store.state?.catalog?.volume_targets || store.state?.catalog?.remotes || [];
  list.push({
    speaker: speakers[0]?.id || "",
    target: targets[0]?.id || speakers[0]?.id || "",
  });
  store.stageSystemSetting("volume_overrides", list);
}
function updateVolumeOverrideRowOp(
  store,
  index,
  field,
  value,
) {
  const list = (store.state?.system_config?.volume_overrides || []).map((v) => ({
    ...v,
  }));
  if (!list[index]) return;
  list[index][field] = value;
  store.stageSystemSetting("volume_overrides", list);
}
function removeVolumeOverrideRowOp(store, index) {
  const list = [...(store.state?.system_config?.volume_overrides || [])];
  list.splice(index, 1);
  store.stageSystemSetting("volume_overrides", list);
}
function addRemoteGroupRowOp(store) {
  const groups = (store.state?.system_config?.remote_groups || []).map((g) => ({
    ...g,
    remotes: [...(g.remotes || [])],
  }));
  const id = `group_${Date.now().toString(36)}`;
  groups.push({ id, name: "New Remote Group", area_id: "", remotes: [] });
  store.stageSystemSetting("remote_groups", groups);
}
function updateRemoteGroupFieldOp(
  store,
  groupId,
  field,
  value,
) {
  const groups = (store.state?.system_config?.remote_groups || []).map((g) =>
    g.id === groupId ? { ...g, [field]: value } : { ...g, remotes: [...(g.remotes || [])] },
  );
  store.stageSystemSetting("remote_groups", groups);
}
function toggleRemoteInGroupOp(
  store,
  groupId,
  remoteEntity,
) {
  const groups = (store.state?.system_config?.remote_groups || []).map((g) => {
    if (g.id !== groupId) return { ...g, remotes: [...(g.remotes || [])] };
    const remotes = [...(g.remotes || [])];
    const idx = remotes.indexOf(remoteEntity);
    if (idx >= 0) remotes.splice(idx, 1);
    else remotes.push(remoteEntity);
    return { ...g, remotes };
  });
  store.stageSystemSetting("remote_groups", groups);
}
function removeRemoteGroupRowOp(store, groupId) {
  const groups = (store.state?.system_config?.remote_groups || []).filter((g) => g.id !== groupId);
  store.stageSystemSetting("remote_groups", groups);
}
async function previewCameraOp(
  store,
  cameraEntity,
  bustCache = false,
) {
  if (!cameraEntity) {
    store.closeCameraPreview();
    return;
  }
  const dbObj = (store.state?.doorbells || []).find((b) => b.camera_entity === cameraEntity);
  const camObj = (store.state?.catalog?.cameras || []).find((c) => c.id === cameraEntity);
  const existingSigned = dbObj?.preview_url || camObj?.preview_url || "";
  if (existingSigned) {
    const sep = existingSigned.includes("?") ? "&" : "?";
    store.activeCameraPreviewEntity = cameraEntity;
    store.cameraPreviewUrl = bustCache ? `${existingSigned}${sep}_ts=${Date.now()}` : existingSigned;
    store.host.requestUpdate();
    return;
  }
  try {
    const signed = await store.ws.signHaPath(
      `/api/camera_proxy/${encodeURIComponent(cameraEntity)}`,
      300,
    );
    const sep = signed.includes("?") ? "&" : "?";
    store.activeCameraPreviewEntity = cameraEntity;
    store.cameraPreviewUrl = `${signed}${sep}_ts=${Date.now()}`;
    store.host.requestUpdate();
  } catch (err) {
    store.showToast(formatWsError(err, "Add a Latter Device to preview cameras"), true);
  }
}
async function testDoorbellSpeakerOp(store) {
  const cams = (store.state?.system_config?.camera_entities || [])
    .map((c) => String(c || "").trim())
    .filter(Boolean);
  if (!cams[0]) {
    store.showToast("Add a camera in Shared Entities first", true);
    return;
  }
  if (!store.doorbellTestSubentryId) {
    store.showToast("Choose a Device to test from", true);
    return;
  }
  const message = store.doorbellTestReply.trim() || "Testing Latter doorbell audio.";
  await store.flushSystemSettings();
  try {
    const res = await store.ws.runSystemCommand(
      "test_doorbell_speaker",
      {
        subentry_id: store.doorbellTestSubentryId,
        camera_entity: cams[0],
        message,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Played test message on door speaker");
  } catch (err) {
    store.showToast(formatWsError(err, "Door speaker test failed"), true);
  }
}

// --- src/state/groups-presence-ops.ts ---
/**
 * Device Groups, Batch Controls, BLE calibration, and Area sensor fusion operations.
 */
function slugifyGroupName(raw) {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}
async function createDeviceGroupOp(store) {
  const name = store.newGroupName.trim();
  const description = store.newGroupDesc.trim();
  const sourceSubentryId = store.newGroupSourceSubentryId.trim();
  if (!name) {
    store.showToast("Enter a Device Group name", true);
    return;
  }
  try {
    const payload = { name, description };
    if (sourceSubentryId) {
      payload.source_subentry_id = sourceSubentryId;
    }
    if (store.newGroupIncludeDisplay) {
      payload.include_display = true;
    }
    if (store.newGroupIncludeInterface) {
      payload.include_interface = true;
    }
    const res = await store.ws.runSystemCommand(
      "create_device_group",
      payload,
      store.activeSubentryId || null,
    );
    const createdId = slugifyGroupName(name) || "group";
    store.newGroupName = "";
    store.newGroupDesc = "";
    store.newGroupSourceSubentryId = "";
    store.newGroupIncludeDisplay = false;
    store.newGroupIncludeInterface = false;
    store.openGroupIds.add(createdId);
    if (res) store.ingestPayload(res, false);
    store.showToast(`Created group "${name}"`);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not create Device Group"), true);
  }
}
async function confirmSaveDeviceAsGroupOp(store) {
  const name = store.saveGroupModal.name.trim();
  const description = store.saveGroupModal.description.trim();
  const sourceSubentryId = store.saveGroupModal.subentryId || store.activeSubentryId;
  const includeDisplay = Boolean(store.saveGroupModal.includeDisplay);
  const includeInterface = Boolean(store.saveGroupModal.includeInterface);
  if (!name) {
    store.showToast("Enter a Device Group name", true);
    return;
  }
  if (!sourceSubentryId) {
    store.showToast("Choose a Device first", true);
    return;
  }
  store.saveGroupModal = { ...store.saveGroupModal, busy: true };
  store.host.requestUpdate();
  try {
    const payload = {
      name,
      description,
      source_subentry_id: sourceSubentryId,
      assign_source: true,
    };
    if (includeDisplay) payload.include_display = true;
    if (includeInterface) payload.include_interface = true;
    const res = await store.ws.runSystemCommand(
      "create_device_group",
      payload,
      store.activeSubentryId || null,
    );
    store.saveGroupModal = {
      open: false,
      subentryId: "",
      name: "",
      description: "",
      includeDisplay: false,
      includeInterface: false,
      busy: false,
    };
    if (res) store.ingestPayload(res, false);
    else store.host.requestUpdate();
    store.showToast(`Saved custom group "${name}"`);
  } catch (err) {
    store.saveGroupModal = { ...store.saveGroupModal, busy: false };
    store.host.requestUpdate();
    store.showToast(formatWsError(err, "Could not save custom Device Group"), true);
  }
}
async function deleteDeviceGroupOp(store, groupId) {
  try {
    const res = await store.ws.runSystemCommand(
      "delete_device_group",
      { group_id: groupId },
      store.activeSubentryId || null,
    );
    store.openGroupIds.delete(groupId);
    store.groupCopySourceDrafts.delete(groupId);
    if (store.batchTargetFilter === `group:${groupId}`) {
      store.batchTargetFilter = "all";
    }
    if (res) store.ingestPayload(res, false);
    store.showToast("Deleted Device Group");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not delete Device Group"), true);
  }
}
async function updateGroupBaselineOp(
  store,
  groupId,
  patch,
) {
  if (!groupId) return;
  try {
    const res = await store.ws.runSystemCommand(
      "update_group_baseline",
      {
        group_id: groupId,
        config: patch,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update group baseline"), true);
  }
}
async function updateGroupScopeOp(
  store,
  groupId,
  scope,
) {
  if (!groupId) return;
  try {
    const res = await store.ws.runSystemCommand(
      "update_group_baseline",
      {
        group_id: groupId,
        ...scope,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update group scope"), true);
  }
}
async function copyDeviceToGroupBaselineOp(
  store,
  groupId,
  sourceSubentryId,
  copyKeys,
) {
  if (!groupId || !sourceSubentryId) {
    store.showToast("Choose a Device to copy settings from", true);
    return;
  }
  try {
    const payload = {
      group_id: groupId,
      source_subentry_id: sourceSubentryId,
    };
    if (copyKeys && copyKeys.length) {
      payload.copy_keys = copyKeys;
    }
    const res = await store.ws.runSystemCommand(
      "update_group_baseline",
      payload,
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Copied Device settings into group baseline");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not copy Device settings"), true);
  }
}
function resolvedBatchTargetIdOp(store) {
  const filter = store.batchTargetFilter || "all";
  if (filter.startsWith("group:")) return filter.slice(6);
  return filter;
}
async function applyBatchDeviceSettingOp(
  store,
  patch,
) {
  try {
    const res = await store.ws.runSystemCommand(
      "apply_batch_device_setting",
      {
        target: store.batchTargetFilter || "all",
        config: patch,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Applied batch setting");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not apply batch setting"), true);
  }
}
async function applyBatchCopyFromDeviceOp(
  store,
  sourceSubentryId,
  copyKeys,
) {
  if (!sourceSubentryId || !copyKeys.length) {
    store.showToast("Choose a template Device first", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "apply_batch_device_setting",
      {
        target: store.batchTargetFilter || "all",
        source_subentry_id: sourceSubentryId,
        copy_keys: copyKeys,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Pushed list from template Device");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not copy list across target Devices"), true);
  }
}
function filteredControlTargetsOp(store, ctrl) {
  const filter = store.batchTargetFilter || "all";
  return (ctrl.targets || [])
    .filter((t) => {
      if (filter === "all") return true;
      if (filter === "online") return Boolean(t.is_online);
      if (filter === "roaming") return Boolean(t.is_roaming);
      if (filter === "stationary") return !t.is_roaming;
      const grpId = filter.startsWith("group:") ? filter.slice(6) : filter;
      return (t.device_group || "custom") === grpId;
    })
    .map((t) => t.entity_id || "")
    .filter(Boolean);
}
async function bulkColorOp(
  store,
  ctrl,
  hex,
) {
  const cleaned = String(hex || "").trim().toUpperCase();
  if (!ctrl.pref_key || !/^#[0-9A-F]{6}$/.test(cleaned)) return;
  await applyBatchDeviceSettingOp(store, { [ctrl.pref_key]: cleaned });
}
async function bulkPillsToggleOp(
  store,
  ctrl,
  token,
  currentCsv,
) {
  if (!ctrl.pref_key) return;
  const order = ctrl.options || [];
  const activeSet = new Set(
    String(currentCsv || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );
  if (activeSet.has(token)) {
    const minRequired = ctrl.min ?? 0;
    if (activeSet.size <= minRequired) {
      store.showToast("Keep at least one category enabled", true);
      return;
    }
    activeSet.delete(token);
  } else {
    activeSet.add(token);
  }
  const ordered = order.length
    ? order.filter((t) => activeSet.has(t))
    : Array.from(activeSet);
  await applyBatchDeviceSettingOp(store, { [ctrl.pref_key]: ordered.join(",") });
}
async function bulkToggleOp(
  store,
  ctrl,
  turnOn,
) {
  if (ctrl.pref_key) {
    await applyBatchDeviceSettingOp(store, { [ctrl.pref_key]: turnOn });
    return;
  }
  const entityIds = filteredControlTargetsOp(store, ctrl);
  if (!entityIds.length) return;
  try {
    const res = await store.ws.runSystemCommand(
      "system_entity_action",
      {
        entity_ids: entityIds,
        action: turnOn ? "turn_on" : "turn_off",
        group_id: resolvedBatchTargetIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Batch switch update failed"), true);
  }
}
async function bulkSelectOp(
  store,
  ctrl,
  option,
) {
  if (ctrl.pref_key) {
    await applyBatchDeviceSettingOp(store, { [ctrl.pref_key]: option });
    return;
  }
  const entityIds = filteredControlTargetsOp(store, ctrl);
  if (!entityIds.length) return;
  try {
    const res = await store.ws.runSystemCommand(
      "system_entity_action",
      {
        entity_ids: entityIds,
        option,
        group_id: resolvedBatchTargetIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Batch option update failed"), true);
  }
}
async function bulkNumberOp(
  store,
  ctrl,
  level,
) {
  if (!Number.isFinite(level)) return;
  if (ctrl.pref_key) {
    await applyBatchDeviceSettingOp(store, { [ctrl.pref_key]: level });
    return;
  }
  const entityIds = filteredControlTargetsOp(store, ctrl);
  if (!entityIds.length) return;
  try {
    const res = await store.ws.runSystemCommand(
      "system_entity_action",
      {
        entity_ids: entityIds,
        level,
        group_id: resolvedBatchTargetIdOp(store) || "all",
        canonical_key: ctrl.canonical_key,
      },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Batch number update failed"), true);
  }
}
function getActiveSurveyDeviceOp(store) {
  const devs = store.state?.system_devices || [];
  const bleDevs = devs.filter((d) => d.ble_tracked || d.kind === "ble_tag");
  return bleDevs.find((d) => d.subentry_id === store.bleSurveySubentryId);
}
async function setBleScannerOffsetOp(
  store,
  scannerSource,
  offsetDb,
) {
  const source = String(scannerSource || "").trim();
  if (!source) {
    store.showToast("Missing BLE scanner source", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "set_ble_scanner_offset",
      { scanner_source: source, offset_db: offsetDb },
      store.activeSubentryId || null,
    );
    if (res) {
      if (!store.bleLiveStreamActive && Array.isArray(res.system_devices) && store.bleSurveyFrozen) {
        const sourceNorm = source.toLowerCase();
        for (const incomingDev of res.system_devices) {
          if (!incomingDev.subentry_id) continue;
          const frozen = store.bleSurveyFrozen.get(incomingDev.subentry_id);
          if (!frozen) continue;
          const incomingRow = (incomingDev.ble_survey_rows || []).find(
            (r) => String(r.scanner_source || "").trim().toLowerCase() === sourceNorm,
          );
          if (!incomingRow) continue;
          frozen.rows = frozen.rows.map((r) => {
            if (String(r.scanner_source || "").trim().toLowerCase() !== sourceNorm) {
              return r;
            }
            return {
              ...r,
              offset_db: incomingRow.offset_db,
              effective_rssi: incomingRow.effective_rssi,
            };
          });
        }
      }
      store.ingestPayload(res, false);
    }
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update BLE scanner offset"), true);
  }
}
async function captureBleAreaSignatureOp(
  store,
  areaId,
) {
  const sysDevs = store.state?.system_devices;
  const activeDev = Array.isArray(sysDevs)
    ? getActiveSurveyDeviceOp(store) || sysDevs.find((d) => d.ble_tracked || d.kind === "ble_tag")
    : undefined;
  const surveySubentryId = Array.isArray(sysDevs)
    ? activeDev?.subentry_id || ""
    : store.bleSurveySubentryId;
  if (!surveySubentryId) {
    store.showToast("Select a calibration Device first", true);
    return;
  }
  try {
    const res = await store.ws.runSystemCommand(
      "capture_ble_area_signature",
      { area_id: areaId, survey_subentry_id: surveySubentryId },
      store.activeSubentryId || null,
    );
    store.bleCalibrateHandoffActive = false;
    if (res) store.ingestPayload(res, false);
    else store.host?.requestUpdate?.();
    store.showToast("Captured Area signature");
  } catch (err) {
    store.showToast(formatWsError(err, "Signature capture failed"), true);
  }
}
async function clearBleAreaSignatureOp(
  store,
  areaId,
) {
  try {
    const res = await store.ws.runSystemCommand(
      "clear_ble_area_signature",
      { area_id: areaId },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
    store.showToast("Cleared Area signature");
  } catch (err) {
    store.showToast(formatWsError(err, "Could not clear Area signature"), true);
  }
}
async function setAreaFusionOp(
  store,
  areaId,
  update,
) {
  try {
    const res = await store.ws.runSystemCommand(
      "set_area_fusion",
      { area_id: areaId, ...update },
      store.activeSubentryId || null,
    );
    if (res) store.ingestPayload(res, false);
  } catch (err) {
    store.showToast(formatWsError(err, "Could not update Area fusion"), true);
  }
}

// --- src/state/store.ts ---
/**
 * Encapsulated Reactive Store for Latter Studio (`StudioStore`).
 *
 * Key invariants:
 * - Zero `window.*` globals: each `<latter-studio>` element owns its `StudioStore` controller.
 * - Snapshot-isolated pending edits: `stageDeviceSetting` captures `targetSubentryId` at input time,
 *   so switching Devices or routes flushes pending edits strictly to Device A (`previousSubentryId`)
 *   before loading Device B, and rolls back cleanly on error even if the input retains focus.
 * - Streams `ble_survey_delta` over the WebSocket subscription without 1.5s full-state polling.
 * - Requests `include_logs: true` ONLY when System -> Tools -> System & Device Logs is open.
 */
function slugToView (map, slug) {
  const cleaned = String(slug || "").trim().toLowerCase();
  for (const [viewId, s] of Object.entries(map)) {
    if (s === cleaned) return viewId;
  }
  return null;
}
class StudioStore {
           host;
           ws;
  // Core navigation & lifecycle state (D-001: starts on Devices landing list)
  currentScope = "device";
  currentViewId = "select_device_prompt";
  activeSubentryId = "";
  deviceSelected = false;
  state = null;
  loading = true;
  loadError = "";
  studioRevMismatch = false;
  // Toast feedback
  toastMessage = "";
  toastIsError = false;
          toastTimer = null;
  // Upload state (`XMLHttpRequest` multipart <= 15 MB)
  uploadScope = null;
  uploadBusy = false;
  uploadPercent = 0;
  selectedDeviceWallpaperFile = null;
  selectedSystemWallpaperFile = null;
  selectedBackupFile = null;
  // Devices table & Discovered UI state
  deviceSortField = "title";
  deviceSortAsc = true;
  deviceCategoryFilter = "all";
  discoveredBleSearch = "";
  discoveredBleKindFilter = "all";
  discoveredBleSort = "name";
  discoveredBlePaused = false;
  discoveredBleFrozenSnapshot = null;
           discoveredBlePersonDrafts = new Map();
           discoveredLatterGroupDrafts = new Map();
           discoveredLatterPersonDrafts = new Map();
                   discoveredBleSeenCache = new Map
   ();
  // Device Security & Time UI draft state
  devicePinDraft = "";
  systemPinDraft = "";
  pinBusy = false;
  worldClockNewLabel = "";
  worldClockNewZone = "";
  // System Shared Entities UI state
  activeCameraPreviewEntity = "";
  cameraPreviewUrl = "";
  // System Device Groups & Batch Controls UI state
  newGroupName = "";
  newGroupDesc = "";
  newGroupSourceSubentryId = "";
  newGroupIncludeDisplay = false;
  newGroupIncludeInterface = false;
           openGroupIds = new Set();
           groupCopySourceDrafts = new Map();
  batchTargetFilter = "all";
  batchCategoryFilter = "all";
  batchCopySourceSubentryId = "";
  // System BLE & Area Presence UI state
  bleSurveySubentryId = "";
  bleCalibrateAreaId = "";
  bleCalibrateHandoffActive = false;
  bleLiveStreamActive = true;
           bleSurveyFrozen = new Map
   ();
           openProxyTrims = new Set();
  advancedBleOpen = false;
           openFusionAreas = new Set();
  // System Tools UI state
  announceMode = "notify";
  announceTarget = "all";
  announceTitle = "";
  announceMessage = "";
  announcePriority = "normal";
  announceIncludeCamera = false;
  doorbellTestSubentryId = "";
  doorbellTestReply = "";
  backupExportScope = "system";
  backupRestoreSubentryId = "";
  logsOpen = false;
  logFilter = "all";
  // Modal states
  removeModal = { open: false, subentryId: "", title: "", busy: false };
  resetModal = { open: false, deviceSettings: true, latterOptions: true, busy: false };
  addBleModal = {
    open: false,
    candidateAddr: "",
    name: "",
    address: "",
    assignedPerson: "",
    busy: false,
  };
  colorWheelModal = {
    open: false,
    targetScope: "system",
    hex: "",
    name: "",
    busy: false,
  };
  saveGroupModal = {
    open: false,
    subentryId: "",
    name: "",
    description: "",
    includeDisplay: false,
    includeInterface: false,
    busy: false,
  };
  shortcutModal = {
    open: false,
    listKey: "pinned_items",
    editIndex: null,
    kind: "route",
    routeTarget: "weather:moon",
    entityDomainFilter: "all",
    entitySearch: "",
    entityTarget: "",
    action: "",
    label: "",
    icon: "",
    iconSearch: "",
    confirm: false,
  };
  pendingScrollCardId = "";
  pendingDomRevert = null;
  // Snapshot-isolated pending settings queues (shared with `state/*-ops.ts`)
  pendingSystemPatch = {};
  pendingSystemPrevious = {};
  systemSaveTimer = null;
           pendingBlankListSlots = {
    calendar_entities: 0,
    camera_entities: 0,
    remotes_list: 0,
  };
           pendingDeviceBuckets = new Map();
           pendingEntityStates = new Map();
  // Subscription management
          subGen = 0;
          wsUnsub = null;
          subscribedKey = "";
          fallbackPollTimer = null;
          routeApplying = false;
  constructor(host) {
    this.host = host;
    this.ws = new StudioWsClient(() => {
      this.studioRevMismatch = true;
      this.host.requestUpdate();
    });
  }
  hostConnected() {
    if (this.ws.hass) {
      void this.ensureSubscription(true);
    }
  }
  hostDisconnected() {
    if (this.toastTimer) {
      clearTimeout(this.toastTimer);
      this.toastTimer = null;
    }
    if (this.fallbackPollTimer) {
      clearTimeout(this.fallbackPollTimer);
      this.fallbackPollTimer = null;
    }
    void this.flushAllPendingSettings();
    this.teardownSubscription();
  }
  hostUpdated() {
    if (this.pendingDomRevert) {
      const rev = this.pendingDomRevert;
      this.pendingDomRevert = null;
      const root = (this.host).renderRoot;
      if (root) {
        for (const [id, val] of Object.entries(rev.controlIds)) {
          const el = root.getElementById(id);
          if (!el) continue;
          if (typeof val === "boolean" && "checked" in el) {
            (el).checked = val;
          } else {
            el.value = String(val);
          }
        }
      }
    }
    if (this.pendingScrollCardId) {
      const cardId = this.pendingScrollCardId;
      this.pendingScrollCardId = "";
      const root = (this.host).renderRoot;
      const target = root?.getElementById(cardId);
      if (target && typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }
  setHass(hass) {
    const firstHass = !this.ws.hass && Boolean(hass);
    this.ws.setHass(hass);
    if (firstHass && this.host.isConnected) {
      void this.ensureSubscription(true);
    }
  }
  get hass() {
    return this.ws.hass;
  }
  reloadPage() {
    globalThis.location.reload();
  }
  showToast(message, isError = false) {
    this.toastMessage = String(message || "");
    this.toastIsError = isError;
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => {
      this.toastMessage = "";
      this.host.requestUpdate();
    }, isError ? 5000 : 3000);
    this.host.requestUpdate();
  }
  shouldIncludeLogs() {
    return this.currentScope === "system" && this.currentViewId === "system_tools" && this.logsOpen;
  }
  get pageTitle() {
    return VIEW_TITLES[this.currentViewId] || "Managed Devices";
  }
  get pageSubtitle() {
    if (
      this.currentScope === "device" &&
      this.deviceSelected &&
      this.currentViewId !== "select_device_prompt" &&
      this.currentViewId !== "discovered_devices" &&
      this.state?.title
    ) {
      return this.state.title;
    }
    return "";
  }
  // ---------- Routing & Navigation ----------
  applyRoute(route) {
    const rawPath = String(route?.path || "");
    const parts = rawPath
      .split("/")
      .filter(Boolean)
      .map((seg) => {
        try {
          return decodeURIComponent(seg);
        } catch {
          return seg;
        }
      });
    this.routeApplying = true;
    try {
      if (parts[0] === "devices" && parts[1]?.toLowerCase() === "discovered") {
        if (this.activeSubentryId) {
          void this.flushDeviceBucket(this.activeSubentryId);
        }
        this.bleCalibrateHandoffActive = false;
        this.deviceSelected = false;
        this.currentScope = "device";
        this.currentViewId = "discovered_devices";
        this.host.requestUpdate();
      } else if (parts[0] === "devices" && parts[1]) {
        const nextSubId = parts[1];
        if (
          this.state &&
          Array.isArray(this.state.system_devices) &&
          !this.state.system_devices.some((d) => d.subentry_id === nextSubId)
        ) {
          this.redirectInvalidDeviceRoute();
          return;
        }
        const viewId = slugToView(DEVICE_VIEW_SLUGS, parts[2] || "overview") || "dashboard";
        const prevSubId = this.activeSubentryId;
        const subChanged = prevSubId !== nextSubId;
        if (prevSubId && subChanged) {
          void this.flushDeviceBucket(prevSubId);
        }
        this.bleCalibrateHandoffActive = false;
        this.activeSubentryId = nextSubId;
        this.deviceSelected = true;
        this.currentScope = "device";
        this.currentViewId = viewId;
        this.host.requestUpdate();
        if (subChanged && this.ws.hass) {
          void this.ensureSubscription(true);
        }
      } else if (parts[0] === "system") {
        if (this.activeSubentryId) {
          void this.flushDeviceBucket(this.activeSubentryId);
        }
        const viewId = slugToView(SYSTEM_VIEW_SLUGS, parts[1] || "overview") || "system_overview";
        if (viewId !== "area_tracking") {
          this.bleCalibrateHandoffActive = false;
        }
        this.currentScope = "system";
        this.currentViewId = viewId;
        this.host.requestUpdate();
        if (this.ws.hass && this.shouldIncludeLogs()) {
          void this.refreshState({ includeLogs: true });
        }
      } else {
        if (this.activeSubentryId) {
          void this.flushDeviceBucket(this.activeSubentryId);
        }
        this.bleCalibrateHandoffActive = false;
        this.deviceSelected = false;
        this.currentScope = "device";
        this.currentViewId = "select_device_prompt";
        this.host.requestUpdate();
      }
    } finally {
      this.routeApplying = false;
    }
  }
          redirectInvalidDeviceRoute() {
    const invalidId = this.activeSubentryId;
    this.activeSubentryId = "";
    this.deviceSelected = false;
    this.currentScope = "system";
    this.currentViewId = "system_overview";
    navigateHaPath("/latter/system/overview", true);
    if (invalidId) {
      this.showToast("Requested Device was not found; showing System Overview.", false);
    }
    this.host.requestUpdate();
    if (this.ws.hass) {
      void this.ensureSubscription(true);
    }
  }
  syncUrl(replace = false) {
    if (this.routeApplying) return;
    let targetPath = "/latter";
    if (this.currentScope === "system") {
      const slug = SYSTEM_VIEW_SLUGS[this.currentViewId ] || "overview";
      targetPath = `/latter/system/${slug}`;
    } else if (this.currentViewId === "discovered_devices") {
      targetPath = "/latter/devices/discovered";
    } else if (
      this.deviceSelected &&
      this.activeSubentryId &&
      this.currentViewId !== "select_device_prompt"
    ) {
      const slug =
        DEVICE_VIEW_SLUGS[
          this.currentViewId
        ] || "overview";
      targetPath = `/latter/devices/${encodeURIComponent(this.activeSubentryId)}/${slug}`;
    } else {
      targetPath = "/latter/devices";
    }
    if (globalThis.location?.pathname !== targetPath) {
      navigateHaPath(targetPath, replace);
    }
  }
  openDevicesLanding() {
    if (this.activeSubentryId) {
      void this.flushDeviceBucket(this.activeSubentryId);
    }
    this.bleCalibrateHandoffActive = false;
    this.deviceSelected = false;
    this.currentScope = "device";
    this.currentViewId = "select_device_prompt";
    this.syncUrl();
    this.host.requestUpdate();
  }
  openDiscoveredDevices() {
    if (this.activeSubentryId) {
      void this.flushDeviceBucket(this.activeSubentryId);
    }
    this.bleCalibrateHandoffActive = false;
    this.deviceSelected = false;
    this.currentScope = "device";
    this.currentViewId = "discovered_devices";
    this.syncUrl();
    this.host.requestUpdate();
  }
  openDevicesWithCategory(category) {
    this.deviceCategoryFilter = category;
    this.openDevicesLanding();
  }
  setScope(scope, explicitViewId) {
    if (scope === "device" && this.currentScope !== "device") {
      void this.flushSystemSettings();
    } else if (scope === "system" && this.activeSubentryId) {
      void this.flushDeviceBucket(this.activeSubentryId);
    }
    this.bleCalibrateHandoffActive = false;
    this.currentScope = scope;
    if (explicitViewId) {
      this.currentViewId = explicitViewId;
    } else if (scope === "system") {
      this.currentViewId = "system_overview";
    } else {
      this.currentViewId = this.deviceSelected && this.activeSubentryId ? "dashboard" : "select_device_prompt";
    }
    this.syncUrl();
    this.host.requestUpdate();
    if (this.shouldIncludeLogs()) {
      void this.refreshState({ includeLogs: true });
    }
  }
  switchView(viewId) {
    if (viewId === "select_device_prompt") {
      this.openDevicesLanding();
      return;
    }
    if (viewId === "discovered_devices") {
      this.openDiscoveredDevices();
      return;
    }
    this.bleCalibrateHandoffActive = false;
    const isSys = Object.prototype.hasOwnProperty.call(SYSTEM_VIEW_SLUGS, viewId);
    this.currentScope = isSys ? "system" : "device";
    this.currentViewId = viewId;
    this.syncUrl();
    this.host.requestUpdate();
    if (viewId === "area_tracking") {
      this.ensureDefaultSurveyDevice();
      void this.ensureSubscription(false);
    } else if (this.shouldIncludeLogs()) {
      void this.refreshState({ includeLogs: true });
    }
  }
  openSystemSection(viewId, cardId = "") {
    this.pendingScrollCardId = cardId;
    this.switchView(viewId);
  }
  openManageGroups(groupId = "") {
    const cleanId = String(groupId || "").trim();
    if (cleanId && cleanId !== "custom") {
      this.openGroupIds.add(cleanId);
      this.openSystemSection("system_sync", `group-box-${cleanId}`);
      return;
    }
    this.openSystemSection("system_sync");
  }
  async switchSystemDevice(nextSubentryId, targetView = "dashboard") {
    const cleanNext = String(nextSubentryId || "").trim();
    if (!cleanNext) return;
    const prevSubId = this.activeSubentryId;
    if (prevSubId && prevSubId !== cleanNext) {
      await this.flushDeviceBucket(prevSubId);
    }
    this.bleCalibrateHandoffActive = false;
    this.activeSubentryId = cleanNext;
    this.deviceSelected = true;
    this.currentScope = "device";
    this.currentViewId =
      targetView === "select_device_prompt" || targetView === "discovered_devices"
        ? "dashboard"
        : targetView;
    this.devicePinDraft = "";
    this.worldClockNewLabel = "";
    this.worldClockNewZone = "";
    this.syncUrl();
    this.host.requestUpdate();
    await this.ensureSubscription(true);
  }
  openHaPage(path) {
    navigateHaPath(path, false);
  }
  openDeviceInHa() {
    const links = this.state?.links;
    const devId = links?.esphome_device_id || links?.latter_device_id || "";
    if (devId) {
      this.openHaPage(`/config/devices/device/${encodeURIComponent(devId)}`);
    } else {
      this.openHaPage("/config/integrations/integration/latter");
    }
  }
  toggleParentHaSidebar() {
    this.host.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
  }
  // ---------- Subscription & State Ingestion ----------
  teardownSubscription() {
    this.subGen += 1;
    if (typeof this.wsUnsub === "function") {
      try {
        this.wsUnsub();
      } catch {
        // Ignore stale unsubscribe errors on disconnect.
      }
    }
    this.wsUnsub = null;
    this.subscribedKey = "";
  }
          desiredSubscriptionKey() {
    const sub = this.activeSubentryId || "";
    const survey =
      this.currentScope === "system" && this.currentViewId === "area_tracking" && this.bleLiveStreamActive
        ? this.bleSurveySubentryId || ""
        : "";
    return `${sub}|${survey}`;
  }
  async ensureSubscription(forceRefresh = false) {
    if (!this.ws.hass?.connection) return;
    const nextKey = this.desiredSubscriptionKey();
    if (!forceRefresh && this.wsUnsub && this.subscribedKey === nextKey) {
      return;
    }
    this.teardownSubscription();
    const myGen = ++this.subGen;
    const targetSubId = this.activeSubentryId || null;
    const surveyId =
      this.currentScope === "system" && this.currentViewId === "area_tracking" && this.bleLiveStreamActive
        ? this.bleSurveySubentryId || null
        : null;
    if (forceRefresh || !this.state) {
      await this.refreshState({ includeLogs: this.shouldIncludeLogs() });
    }
    if (myGen !== this.subGen) return;
    try {
      const unsub = await this.ws.subscribe(
        {
          subentryId: targetSubId,
          surveySubentryId: surveyId,
          includeLogs: this.shouldIncludeLogs(),
        },
        (eventPayload) => {
          if (myGen !== this.subGen || !eventPayload) return;
          this.handleSubscriptionEvent(eventPayload);
        },
      );
      if (myGen !== this.subGen) {
        try {
          unsub();
        } catch {
          // Ignore stale teardown.
        }
        return;
      }
      this.wsUnsub = unsub;
      this.subscribedKey = nextKey;
    } catch {
      if (this.fallbackPollTimer) clearTimeout(this.fallbackPollTimer);
      this.fallbackPollTimer = setTimeout(() => {
        if (this.host.isConnected) {
          void this.ensureSubscription(true);
        }
      }, 10000);
    }
  }
  async refreshState(options) {
    if (!this.ws.hass) return;
    const targetSubId = this.activeSubentryId || null;
    const includeLogs = options?.includeLogs ?? this.shouldIncludeLogs();
    try {
      const payload = await this.ws.getState({
        subentryId: targetSubId,
        includeLogs,
      });
      if (payload) {
        this.loadError = "";
        this.loading = false;
        this.ingestPayload(payload, includeLogs);
      }
    } catch (err) {
      this.loading = false;
      this.loadError = formatWsError(err, "Latter Studio could not load.");
      this.host.requestUpdate();
    }
  }
          handleSubscriptionEvent(raw) {
    if (!raw || typeof raw !== "object") return;
    const rec = raw;
    const isBleDelta =
      rec.type === "ble_survey_delta" ||
      rec.event === "ble_survey_delta" ||
      (!("system_devices" in rec) &&
        ("ble_survey_rows" in rec ||
          "ble_area_signatures" in rec ||
          "ble_packets_seen" in rec ||
          "area_presence_grid" in rec));
    if (isBleDelta) {
      this.applyBleSurveyDelta(rec);
      return;
    }
    const payload = raw;
    if (
      this.activeSubentryId &&
      payload.subentry_id &&
      payload.subentry_id !== this.activeSubentryId
    ) {
      return;
    }
    this.loading = false;
    this.loadError = "";
    this.ingestPayload(payload, false);
  }
  applyBleSurveyDelta(delta) {
    if (!this.state) return;
    if (!this.bleLiveStreamActive) {
      let updated = false;
      if (Array.isArray(delta.ble_area_signatures)) {
        this.state = {
          ...this.state,
          ble_area_signatures: delta.ble_area_signatures,
        };
        updated = true;
      }
      if (Array.isArray(delta.area_presence_grid) && this.state.live) {
        this.state.live = {
          ...this.state.live,
          area_presence_grid: delta.area_presence_grid,
        };
        updated = true;
      }
      if (updated) {
        this.host.requestUpdate();
      }
      return;
    }
    const targetId = String(delta.subentry_id || this.bleSurveySubentryId || this.state.subentry_id || "");
    if (Array.isArray(delta.ble_survey_rows)) {
      const nextRows = delta.ble_survey_rows;
      const winRow = nextRows.find((r) => r.is_winner);
      if (Array.isArray(this.state.system_devices) && targetId) {
        this.state.system_devices = this.state.system_devices.map((dev) => {
          if (dev.subentry_id !== targetId) return dev;
          return {
            ...dev,
            ble_survey_rows: nextRows,
            ble_packets_seen:
              typeof delta.ble_packets_seen === "number" ? delta.ble_packets_seen : dev.ble_packets_seen,
            active_area_name: winRow?.area_name || dev.active_area_name,
          };
        });
      }
      if (this.state.subentry_id === targetId && this.state.live && typeof delta.ble_closest_proxy === "string") {
        this.state.live = {
          ...this.state.live,
          ble_closest_proxy: delta.ble_closest_proxy,
        };
      }
    }
    if (Array.isArray(delta.ble_area_signatures)) {
      this.state = {
        ...this.state,
        ble_area_signatures: delta.ble_area_signatures,
      };
    }
    if (Array.isArray(delta.area_presence_grid) && this.state.live) {
      this.state.live = {
        ...this.state.live,
        area_presence_grid: delta.area_presence_grid,
      };
    }
    this.host.requestUpdate();
  }
  ingestPayload(incoming, logsWereRequested) {
    const prevCatalog = this.state?.catalog;
    const prevLogs = this.state?.internal_logs;
    const prevSysConfig = this.state?.system_config;
    if (
      this.deviceSelected &&
      this.activeSubentryId &&
      Array.isArray(incoming.system_devices) &&
      !incoming.system_devices.some((d) => d.subentry_id === this.activeSubentryId)
    ) {
      const redirected = {
        ...incoming,
        catalog: incoming.catalog ?? prevCatalog,
        internal_logs: logsWereRequested || incoming.internal_logs?.length ? incoming.internal_logs : prevLogs || [],
      };
      overlayPendingBlankListSlots(this, redirected, prevSysConfig);
      this.state = redirected;
      this.redirectInvalidDeviceRoute();
      return;
    }
    const merged = {
      ...incoming,
      discovered_ble_devices: this.stabilizeDiscoveredBle(incoming),
      catalog: incoming.catalog ?? prevCatalog,
      internal_logs:
        logsWereRequested || (Array.isArray(incoming.internal_logs) && incoming.internal_logs.length > 0)
          ? incoming.internal_logs || []
          : prevLogs || [],
    };
    if (!this.bleLiveStreamActive && Array.isArray(merged.system_devices)) {
      const frozenMap = this.ensureBleSurveyFrozenMap();
      merged.system_devices = merged.system_devices.map((dev) => {
        if (!dev.subentry_id) return dev;
        const frozen = frozenMap.get(dev.subentry_id);
        if (frozen) {
          return {
            ...dev,
            ble_survey_rows: frozen.rows.map((r) => ({ ...r })),
            ble_packets_seen: frozen.packetsSeen,
            active_area_name: frozen.activeAreaName,
          };
        }
        frozenMap.set(dev.subentry_id, {
          rows: (dev.ble_survey_rows || []).map((r) => ({ ...r })),
          packetsSeen: dev.ble_packets_seen ?? 0,
          activeAreaName: dev.active_area_name || "",
        });
        return dev;
      });
    }
    if (Object.keys(this.pendingSystemPatch).length > 0 && merged.system_config) {
      merged.system_config = {
        ...merged.system_config,
        ...(this.pendingSystemPatch),
      };
    }
    overlayPendingBlankListSlots(this, merged, prevSysConfig);
    const devBucket = merged.subentry_id ? this.pendingDeviceBuckets.get(merged.subentry_id) : undefined;
    if (devBucket && merged.config) {
      overlayDevicePrefsOnSections(merged, devBucket.patch);
    }
    overlayPendingEntityStates(merged, this.pendingEntityStates);
    if (this.currentScope === "device" && this.deviceSelected && merged.subentry_id === this.activeSubentryId) {
      const caps = merged.capabilities || {};
      const isBleTag = merged.config?.kind === "ble_tag";
      if (
        ((this.currentViewId === "display" || this.currentViewId === "interface") &&
          (isBleTag || !caps.has_display)) ||
        (this.currentViewId === "audio_voice" && (isBleTag || (!caps.has_audio && !caps.has_voice))) ||
        (this.currentViewId === "power" && (isBleTag || !caps.has_power))
      ) {
        this.currentViewId = "dashboard";
        this.syncUrl(true);
      }
    }
    this.state = merged;
    this.ensureDefaultSurveyDevice();
    this.ensureDefaultDoorbellTester();
    this.ensureValidBatchTargetFilter();
    this.host.requestUpdate();
  }
          stabilizeDiscoveredBle(incoming) {
    const RETENTION_MS = 90_000;
    const now = Date.now();
    const onboardedSlugs = new Set(
      (incoming.system_devices || [])
        .map((d) => String(d.device_slug || "").trim().toLowerCase())
        .filter(Boolean),
    );
    for (const [addrKey, entry] of this.discoveredBleSeenCache.entries()) {
      const candSlug = String(
        (entry.candidate).slug || "",
      )
        .trim()
        .toLowerCase();
      if (now - entry.lastSeenMs > RETENTION_MS || (candSlug && onboardedSlugs.has(candSlug))) {
        this.discoveredBleSeenCache.delete(addrKey);
      }
    }
    const extraNoKey = [];
    for (const c of incoming.discovered_ble_devices || []) {
      const addrKey = String(c.target_address || c.address || "").trim().toLowerCase();
      if (addrKey) {
        this.discoveredBleSeenCache.set(addrKey, { candidate: c, lastSeenMs: now });
      } else {
        extraNoKey.push(c);
      }
    }
    return [
      ...Array.from(this.discoveredBleSeenCache.values(), (entry) => entry.candidate),
      ...extraNoKey,
    ];
  }
  toggleDiscoveredBlePause(paused) {
    const next = paused ?? !this.discoveredBlePaused;
    this.discoveredBlePaused = next;
    if (next) {
      this.discoveredBleFrozenSnapshot = [...(this.state?.discovered_ble_devices || [])];
    } else {
      this.discoveredBleFrozenSnapshot = null;
    }
    this.host.requestUpdate();
  }
  evictAdoptedBleCandidate(targetAddress) {
    const addrKey = String(targetAddress || "").trim().toLowerCase();
    if (!addrKey) return;
    this.discoveredBleSeenCache.delete(addrKey);
    this.discoveredBlePersonDrafts.delete(addrKey);
    if (this.discoveredBleFrozenSnapshot) {
      this.discoveredBleFrozenSnapshot = this.discoveredBleFrozenSnapshot.filter(
        (c) => String(c.target_address || c.address || "").trim().toLowerCase() !== addrKey,
      );
    }
  }
          ensureDefaultSurveyDevice() {
    const devs = this.state?.system_devices || [];
    const bleDevs = devs.filter((d) => d.ble_tracked || d.kind === "ble_tag");
    if (this.bleSurveySubentryId && bleDevs.some((d) => d.subentry_id === this.bleSurveySubentryId)) {
      return;
    }
    const current = bleDevs.find((d) => d.subentry_id === this.activeSubentryId);
    this.bleSurveySubentryId = current?.subentry_id || bleDevs[0]?.subentry_id || "";
  }
          ensureDefaultDoorbellTester() {
    const devs = (this.state?.system_devices || []).filter((d) => d.kind !== "ble_tag");
    if (this.doorbellTestSubentryId && devs.some((d) => d.subentry_id === this.doorbellTestSubentryId)) {
      return;
    }
    this.doorbellTestSubentryId = devs[0]?.subentry_id || "";
  }
          ensureValidBatchTargetFilter() {
    if (!this.batchTargetFilter.startsWith("group:")) return;
    const gid = this.batchTargetFilter.slice(6);
    const groups = this.state?.device_groups || [];
    const devs = (this.state?.system_devices || []).filter((d) => d.kind !== "ble_tag");
    const hasGroupWithMembers =
      groups.some((g) => g.id === gid) && devs.some((d) => d.device_group === gid);
    if (!hasGroupWithMembers) {
      this.batchTargetFilter = "all";
    }
  }
  // ---------- Delegated Domain Operations ----------
  stageDeviceSetting(
    key,
    value,
    controlDomId,
    debounceMs,
  ) {
    stageDeviceSettingOp(this, key, value, controlDomId, debounceMs);
  }
  async runDeviceAction(action, toastMessage) {
    return runDeviceActionOp(this, action, toastMessage);
  }
  async flushDeviceBucket(targetSubentryId) {
    await flushDeviceBucketOp(this, targetSubentryId);
  }
  stageSystemSetting(key, value, controlDomId) {
    stageSystemSettingOp(this, key, value, controlDomId);
  }
  async flushSystemSettings() {
    await flushSystemSettingsOp(this);
  }
  async flushAllPendingSettings() {
    const tasks = [];
    if (Object.keys(this.pendingSystemPatch).length > 0) {
      tasks.push(this.flushSystemSettings());
    }
    for (const subId of Array.from(this.pendingDeviceBuckets.keys())) {
      tasks.push(this.flushDeviceBucket(subId));
    }
    await Promise.allSettled(tasks);
  }
  getPref(key) {
    return (this.state?.device_prefs || []).find((p) => p.key === key);
  }
  getPrefs(keys) {
    const all = this.state?.device_prefs || [];
    if (!keys || keys.length === 0) return all;
    const keySet = new Set(keys);
    return all.filter((p) => keySet.has(p.key));
  }
  getSectionItems(sectionId) {
    const sec = (this.state?.esphome?.sections || []).find((s) => s.id === sectionId);
    return sec?.items || [];
  }
  async executeEntityAction(
    entityId,
    optimisticState,
    body,
    errorPrefix,
  ) {
    return executeEntityActionOp(this, entityId, optimisticState, body, errorPrefix);
  }
  async espAction(
    entityId,
    action,
    optimisticState,
    toastMessage,
  ) {
    const ok = await commitEntityChange(this, entityId, optimisticState, { action }, "Device action failed");
    if (ok && toastMessage) {
      this.showToast(toastMessage);
    }
    return ok;
  }
  async espSelect(entityId, option) {
    await commitEntityChange(this, entityId, option, { option }, "Could not update option");
  }
  async espNumber(entityId, level) {
    if (!Number.isFinite(level)) return;
    await commitEntityChange(this, entityId, String(level), { level }, "Could not update level");
  }
  async triggerHeaderFirmwareUpdate() {
    const updEntity = this.state?.live?.fw_update_entity || "";
    if (!updEntity) return;
    if (await this.espAction(updEntity, "install")) {
      this.showToast("Firmware update started");
    }
  }
  getDockItems() {
    return getDockItemsOp(this);
  }
  getPinnedItems() {
    return getPinnedItemsOp(this);
  }
  moveShortcutItem(
    listKey,
    idx,
    delta,
  ) {
    moveShortcutItemOp(this, listKey, idx, delta);
  }
  removeShortcutItem(listKey, idx) {
    removeShortcutItemOp(this, listKey, idx);
  }
  resetDockItemsToDefault() {
    resetDockItemsToDefaultOp(this);
  }
  openShortcutModal(
    listKey,
    editIndex = null,
  ) {
    openShortcutModalOp(this, listKey, editIndex);
  }
  closeShortcutModal() {
    this.shortcutModal = { ...this.shortcutModal, open: false };
    this.host.requestUpdate();
  }
  saveShortcutModal() {
    saveShortcutModalOp(this);
  }
  getEnabledAreaCategories() {
    return getEnabledAreaCategoriesOp(this);
  }
  toggleAreaCategoryToken(token) {
    toggleAreaCategoryTokenOp(this, token);
  }
  moveAreaCategoryToken(token, delta) {
    moveAreaCategoryTokenOp(this, token, delta);
  }
  getEnabledHomeCategories() {
    return getEnabledHomeCategoriesOp(this);
  }
  toggleHomeCategoryToken(token) {
    toggleHomeCategoryTokenOp(this, token);
  }
  moveHomeCategoryToken(token, delta) {
    moveHomeCategoryTokenOp(this, token, delta);
  }
  getEnabledActivitySources() {
    return getEnabledActivitySourcesOp(this);
  }
  toggleActivitySource(sourceId) {
    toggleActivitySourceOp(this, sourceId);
  }
  applyDeviceCustomColor(hex, switchColorProfile = true) {
    applyDeviceCustomColorOp(this, hex, switchColorProfile);
  }
  openColorWheelModal(targetScope) {
    openColorWheelModalOp(this, targetScope);
  }
  closeColorWheelModal() {
    this.colorWheelModal = { ...this.colorWheelModal, open: false, busy: false };
    this.host.requestUpdate();
  }
  async saveColorWheelSelection() {
    await saveColorWheelSelectionOp(this);
  }
  deleteCustomPalette(hex) {
    deleteCustomPaletteOp(this, hex);
  }
  async uploadWallpaper(scope) {
    await uploadWallpaperOp(this, scope);
  }
  async selectWallpaperSource(sourceId) {
    await selectWallpaperSourceOp(this, sourceId);
  }
  async setWallpaperRotation(minutes) {
    await setWallpaperRotationOp(this, minutes);
  }
  async toggleWallpaperFav(sourceId) {
    await toggleWallpaperFavOp(this, sourceId);
  }
  async setAllWallpaperFavorites(sourceIds) {
    await setAllWallpaperFavoritesOp(this, sourceIds);
  }
  async deleteWallpaper(scope, sourceId) {
    await deleteWallpaperOp(this, scope, sourceId);
  }
  get hasConfiguredSecurityPin() {
    return Boolean(
      this.state?.config?.has_security_pin ??
        this.state?.live?.has_security_pin ??
        this.state?.has_security_pin,
    );
  }
  async saveSecurityPin(fromScope) {
    await saveSecurityPinOp(this, fromScope);
  }
  async clearSecurityPin(fromScope) {
    await clearSecurityPinOp(this, fromScope);
  }
  async rotateSigningKey() {
    await rotateSigningKeyOp(this);
  }
  async downloadDeviceDiagnostics() {
    await downloadDeviceDiagnosticsOp(this);
  }
  openRemoveDeviceModal(subentryId, title) {
    if (!subentryId) return;
    this.removeModal = { open: true, subentryId, title: title || "Device", busy: false };
    this.host.requestUpdate();
  }
  closeRemoveDeviceModal() {
    this.removeModal = { ...this.removeModal, open: false, busy: false };
    this.host.requestUpdate();
  }
  async confirmRemoveDevice() {
    await confirmRemoveDeviceOp(this);
  }
  openResetDeviceModal() {
    if (!this.activeSubentryId) return;
    const isBleTag = this.state?.config?.kind === "ble_tag";
    this.resetModal = {
      open: true,
      deviceSettings: !isBleTag,
      latterOptions: true,
      busy: false,
    };
    this.host.requestUpdate();
  }
  closeResetDeviceModal() {
    this.resetModal = { ...this.resetModal, open: false, busy: false };
    this.host.requestUpdate();
  }
  async confirmResetDevice() {
    await confirmResetDeviceOp(this);
  }
  openAddBleModal(prefill) {
    this.addBleModal = {
      open: true,
      candidateAddr: prefill?.address || "",
      name: prefill?.name || "",
      address: prefill?.address || "",
      assignedPerson: "",
      busy: false,
    };
    this.host.requestUpdate();
  }
  closeAddBleModal() {
    this.addBleModal = { ...this.addBleModal, open: false, busy: false };
    this.host.requestUpdate();
  }
  selectBleCandidateInModal(addr) {
    selectBleCandidateInModalOp(this, addr);
  }
  async adoptLatterDevice(
    esphomeDeviceId,
    title,
    deviceGroup = "auto",
    assignedPerson = "",
  ) {
    await adoptLatterDeviceOp(this, esphomeDeviceId, title, deviceGroup, assignedPerson);
  }
  async quickAdoptBleCandidate(title, targetAddress, assignedPerson = "") {
    await quickAdoptBleCandidateOp(this, title, targetAddress, assignedPerson);
  }
  async confirmAddBleModal() {
    await confirmAddBleModalOp(this);
  }
  async checkSystemUpdates() {
    await checkSystemUpdatesOp(this);
  }
  updateStringListRow(
    key,
    index,
    value,
  ) {
    updateStringListRowOp(this, key, index, value);
  }
  addStringListRow(
    key,
    defaultEntity = "",
    maxLen = 10,
  ) {
    addStringListRowOp(this, key, defaultEntity, maxLen);
  }
  removeStringListRow(key, index) {
    removeStringListRowOp(this, key, index);
  }
  addVolumeOverrideRow() {
    addVolumeOverrideRowOp(this);
  }
  updateVolumeOverrideRow(index, field, value) {
    updateVolumeOverrideRowOp(this, index, field, value);
  }
  removeVolumeOverrideRow(index) {
    removeVolumeOverrideRowOp(this, index);
  }
  addRemoteGroupRow() {
    addRemoteGroupRowOp(this);
  }
  updateRemoteGroupField(groupId, field, value) {
    updateRemoteGroupFieldOp(this, groupId, field, value);
  }
  toggleRemoteInGroup(groupId, remoteEntity) {
    toggleRemoteInGroupOp(this, groupId, remoteEntity);
  }
  removeRemoteGroupRow(groupId) {
    removeRemoteGroupRowOp(this, groupId);
  }
  async previewCamera(cameraEntity, bustCache = false) {
    await previewCameraOp(this, cameraEntity, bustCache);
  }
  closeCameraPreview() {
    this.activeCameraPreviewEntity = "";
    this.cameraPreviewUrl = "";
    this.host.requestUpdate();
  }
  async testDoorbellSpeaker() {
    await testDoorbellSpeakerOp(this);
  }
  openSaveGroupModal() {
    if (!this.activeSubentryId) return;
    const devTitle = this.state?.title || "";
    this.saveGroupModal = {
      open: true,
      subentryId: this.activeSubentryId,
      name: "",
      description: devTitle ? `Saved from ${devTitle}` : "",
      includeDisplay: false,
      includeInterface: false,
      busy: false,
    };
    this.host.requestUpdate();
  }
  closeSaveGroupModal() {
    this.saveGroupModal = { ...this.saveGroupModal, open: false, busy: false };
    this.host.requestUpdate();
  }
  async confirmSaveGroupModal() {
    await confirmSaveDeviceAsGroupOp(this);
  }
  async createDeviceGroup() {
    await createDeviceGroupOp(this);
  }
  async deleteDeviceGroup(groupId) {
    await deleteDeviceGroupOp(this, groupId);
  }
  async updateGroupBaseline(groupId, patch) {
    await updateGroupBaselineOp(this, groupId, patch);
  }
  async updateGroupScope(
    groupId,
    scope,
  ) {
    await updateGroupScopeOp(this, groupId, scope);
  }
  async copyDeviceToGroupBaseline(
    groupId,
    sourceSubentryId,
    copyKeys,
  ) {
    await copyDeviceToGroupBaselineOp(this, groupId, sourceSubentryId, copyKeys);
  }
  resolvedBatchTargetId() {
    return resolvedBatchTargetIdOp(this);
  }
  async applyBatchDeviceSetting(patch) {
    await applyBatchDeviceSettingOp(this, patch);
  }
  async applyBatchCopyFromDevice(sourceSubentryId, copyKeys) {
    await applyBatchCopyFromDeviceOp(this, sourceSubentryId, copyKeys);
  }
  filteredControlTargets(ctrl) {
    return filteredControlTargetsOp(this, ctrl);
  }
  async bulkToggle(ctrl, turnOn) {
    await bulkToggleOp(this, ctrl, turnOn);
  }
  async bulkSelect(ctrl, option) {
    await bulkSelectOp(this, ctrl, option);
  }
  async bulkNumber(ctrl, level) {
    await bulkNumberOp(this, ctrl, level);
  }
  async bulkColor(ctrl, hex) {
    await bulkColorOp(this, ctrl, hex);
  }
  async bulkPillsToggle(
    ctrl,
    token,
    currentCsv,
  ) {
    await bulkPillsToggleOp(this, ctrl, token, currentCsv);
  }
          ensureBleSurveyFrozenMap()
    {
    if (!this.bleSurveyFrozen) {
      (
        this
      ).bleSurveyFrozen = new Map();
    }
    return this.bleSurveyFrozen;
  }
  selectBleSurveyDevice(subentryId) {
    this.bleSurveySubentryId = subentryId;
    this.host.requestUpdate();
    void this.ensureSubscription(false);
  }
  selectBleCalibrateArea(areaId, fromAreaCard = false) {
    this.bleCalibrateAreaId = String(areaId || "");
    if (fromAreaCard) {
      this.bleCalibrateHandoffActive = true;
    }
    this.host.requestUpdate();
    if (fromAreaCard && typeof globalThis.requestAnimationFrame === "function") {
      globalThis.requestAnimationFrame(() => {
        const root =
          (this.host).renderRoot ||
          this.host.shadowRoot;
        const cardEl =
          root?.getElementById("card-ble-calibration") ||
          root?.getElementById("ble-calibrate-target-box");
        if (cardEl && typeof cardEl.scrollIntoView === "function") {
          cardEl.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        const selectEl = root?.getElementById("ble-calibrate-area-select");
        if (selectEl && typeof selectEl.focus === "function") {
          try {
            selectEl.focus({ preventScroll: true });
          } catch {
            selectEl.focus();
          }
        }
      });
    }
  }
  toggleBleLiveStream(enabled) {
    const frozenMap = this.ensureBleSurveyFrozenMap();
    if (!enabled) {
      frozenMap.clear();
      for (const dev of this.state?.system_devices || []) {
        if (!dev.subentry_id) continue;
        frozenMap.set(dev.subentry_id, {
          rows: (dev.ble_survey_rows || []).map((r) => ({ ...r })),
          packetsSeen: dev.ble_packets_seen ?? 0,
          activeAreaName: dev.active_area_name || "",
        });
      }
      this.bleLiveStreamActive = false;
      this.host.requestUpdate();
      void this.ensureSubscription(false);
      return;
    }
    frozenMap.clear();
    this.bleLiveStreamActive = true;
    this.host.requestUpdate();
    void this.ensureSubscription(true);
  }
  getActiveSurveyDevice() {
    return getActiveSurveyDeviceOp(this);
  }
  async setBleScannerOffset(scannerSource, offsetDb) {
    await setBleScannerOffsetOp(this, scannerSource, offsetDb);
  }
  async captureBleAreaSignature(areaId) {
    await captureBleAreaSignatureOp(this, areaId);
  }
  async clearBleAreaSignature(areaId) {
    await clearBleAreaSignatureOp(this, areaId);
  }
  async setAreaFusion(
    areaId,
    update,
  ) {
    await setAreaFusionOp(this, areaId, update);
  }
  async sendAnnouncement() {
    await sendAnnouncementOp(this);
  }
  async exportBackup(explicitSubentryId) {
    await exportBackupOp(this, explicitSubentryId);
  }
  async restoreFromUploadedFile() {
    await restoreFromUploadedFileOp(this);
  }
  onToggleLogsDetails(open) {
    this.logsOpen = open;
    this.host.requestUpdate();
    if (open) {
      void this.refreshState({ includeLogs: true });
    }
  }
  formatVisibleLogs() {
    return formatVisibleLogsOp(this);
  }
  async copyLogsToClipboard() {
    await copyLogsToClipboardOp(this);
  }
  async clearInternalLogs() {
    await clearInternalLogsOp(this);
  }
}

// --- src/styles/tokens.ts ---
/**
 * Latter Studio Design System Tokens & Stylesheet (`docs/studio-design.md` §3).
 * Literal font sizes, pixel spacing, and colors appear ONLY inside the single `:host` block.
 */
const STUDIO_STYLES = css`
  :host {
    /* Design tokens (docs/studio-design.md section 3). Every visual value reads a token; each token
       reads a Home Assistant theme variable, with a fallback for themes that do not set it. */
    --studio-font-family: var(--ha-font-family-body, inherit);
    --studio-font-code: var(--ha-font-family-code, monospace);
    --studio-font-title: var(--ha-font-size-xl, 20px);
    --studio-font-section: var(--ha-font-size-l, 16px);
    --studio-font-body: var(--ha-font-size-m, 14px);
    --studio-font-secondary: var(--ha-font-size-s, 12px);
    --studio-font-caption: var(--ha-font-size-s, 12px);
    --studio-weight-regular: var(--ha-font-weight-normal, 400);
    --studio-weight-medium: var(--ha-font-weight-medium, 500);
    --studio-line-height: var(--ha-line-height-normal, 1.6);
    --studio-line-height-condensed: var(--ha-line-height-condensed, 1.2);
    --studio-font-card-title: var(--ha-card-header-font-size, var(--ha-font-size-2xl, 24px));
    --studio-card-title-tracking: -0.012em;
    --studio-space-1: var(--ha-space-1, 4px);
    --studio-space-2: var(--ha-space-2, 8px);
    --studio-space-3: var(--ha-space-3, 12px);
    --studio-space-4: var(--ha-space-4, 16px);
    --studio-space-card-top: var(--ha-space-5, 20px);
    --studio-space-5: var(--ha-space-6, 24px);
    --studio-radius-card: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
    --studio-radius-control: var(--ha-border-radius-md, 8px);
    --studio-radius-field: var(--ha-border-radius-sm, 4px);
    --studio-radius-button: var(--ha-button-border-radius, var(--ha-border-radius-pill, 9999px));
    --studio-radius-dialog: var(--ha-dialog-border-radius, var(--ha-border-radius-3xl, 24px));
    --studio-radius-pill: var(--ha-border-radius-pill, 9999px);
    --studio-card-border-width: var(--ha-card-border-width, 1px);
    --studio-control-height: var(--ha-button-height, 40px);
    --studio-control-height-compact: 32px;
    --studio-row-min-height: 56px;
    --studio-header-height: var(--header-height, 56px);
    --studio-sidebar-width: 244px;
    --studio-bg: var(--primary-background-color, #111111);
    --studio-surface: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    --studio-surface-alt: var(--secondary-background-color, #282828);
    --studio-header-bg: var(--app-header-background-color, var(--sidebar-background-color, #1c1c1c));
    --studio-header-text: var(--app-header-text-color, var(--primary-text-color, #e1e1e1));
    --studio-header-icon: var(--sidebar-icon-color, var(--secondary-text-color, #9b9b9b));
    --studio-header-border: var(--app-header-border-bottom, 1px solid var(--divider-color, rgba(225, 225, 225, 0.12)));
    --studio-sidebar-bg: var(--sidebar-background-color, var(--card-background-color, #1c1c1c));
    --studio-input-bg: var(--input-fill-color, rgba(255, 255, 255, 0.05));
    --studio-field-bg: var(--ha-color-form-background, var(--input-fill-color, #363636));
    --studio-field-bg-hover: var(--ha-color-form-background-hover, var(--studio-field-bg));
    --studio-field-line: var(--ha-color-border-neutral-loud, var(--input-idle-line-color, rgba(255, 255, 255, 0.42)));
    --studio-popup-bg: var(--card-background-color, #1c1c1c);
    --studio-divider: var(--divider-color, rgba(225, 225, 225, 0.12));
    --studio-card-border: var(--ha-card-border-color, var(--divider-color, rgba(225, 225, 225, 0.12)));
    --studio-text: var(--primary-text-color, #e1e1e1);
    --studio-text-secondary: var(--secondary-text-color, #9b9b9b);
    --studio-text-disabled: var(--disabled-text-color, #6f6f6f);
    --studio-primary: var(--primary-color, #009ac7);
    --studio-primary-tint: rgba(var(--rgb-primary-color, 0, 154, 199), 0.12);
    --studio-primary-tint-strong: rgba(var(--rgb-primary-color, 0, 154, 199), 0.24);
    --studio-hover: rgba(var(--rgb-primary-text-color, 225, 225, 225), 0.06);
    --studio-btn-accent-bg: var(--ha-color-fill-primary-loud-resting, var(--primary-color, #009ac7));
    --studio-btn-accent-bg-hover: var(--ha-color-fill-primary-loud-hover, var(--studio-btn-accent-bg));
    --studio-btn-accent-text: var(--ha-color-on-primary-loud, var(--text-primary-color, #ffffff));
    --studio-btn-tonal-bg: var(--ha-color-fill-primary-normal-resting, var(--studio-primary-tint));
    --studio-btn-tonal-bg-hover: var(--ha-color-fill-primary-normal-hover, var(--studio-primary-tint-strong));
    --studio-btn-tonal-text: var(--ha-color-on-primary-normal, var(--primary-color, #009ac7));
    --studio-btn-plain-hover: var(--ha-color-fill-primary-quiet-resting, var(--studio-primary-tint));
    --studio-danger-tonal-bg: var(--ha-color-fill-danger-normal-resting, var(--studio-error-tint));
    --studio-danger-tonal-text: var(--ha-color-on-danger-normal, var(--error-color, #db4437));
    --studio-danger-loud-bg: var(--ha-color-fill-danger-loud-resting, var(--error-color, #db4437));
    --studio-danger-loud-text: var(--ha-color-on-danger-loud, #ffffff);
    --studio-switch-track: var(--ha-switch-background-color, var(--ha-color-fill-disabled-quiet-resting, #202020));
    --studio-switch-border: var(--ha-switch-border-color, var(--ha-color-border-neutral-normal, #7a7a7a));
    --studio-switch-thumb: var(--ha-switch-thumb-background-color, var(--ha-color-on-neutral-normal, #989898));
    --studio-switch-on-track: var(--ha-switch-checked-background-color, var(--ha-color-fill-primary-normal-resting, var(--studio-primary-tint-strong)));
    --studio-switch-on-border: var(--ha-switch-checked-border-color, var(--ha-color-border-primary-loud, var(--primary-color, #009ac7)));
    --studio-switch-on-thumb: var(--ha-switch-checked-thumb-background-color, var(--ha-color-on-primary-normal, var(--primary-color, #009ac7)));
    --studio-switch-thumb-shadow: var(--ha-switch-thumb-box-shadow, var(--ha-box-shadow-s, 0 1px 2px rgba(0, 0, 0, 0.3)));
    --studio-toast-bg: var(--primary-text-color, #e1e1e1);
    --studio-toast-text: var(--card-background-color, #1c1c1c);
    --studio-scrollbar-thumb: var(--scrollbar-thumb-color, rgb(110, 110, 110));
    --studio-success: var(--success-color, #43a047);
    --studio-warning: var(--warning-color, #ffa600);
    --studio-error: var(--error-color, #db4437);
    --studio-info: var(--info-color, #039be5);
    --studio-success-tint: color-mix(in srgb, var(--studio-success) 14%, transparent);
    --studio-warning-tint: color-mix(in srgb, var(--studio-warning) 14%, transparent);
    --studio-error-tint: color-mix(in srgb, var(--studio-error) 14%, transparent);
    --studio-info-tint: color-mix(in srgb, var(--studio-info) 14%, transparent);
    --studio-card-shadow: var(--ha-card-box-shadow, none);
    --studio-overlay-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    --studio-scrim: rgba(0, 0, 0, 0.5);
    --studio-media-bg: var(--secondary-background-color, #000000);
    display: block;
    min-height: 100vh;
    background: var(--studio-bg);
    color: var(--studio-text);
    font-family: var(--studio-font-family);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-regular);
    line-height: var(--studio-line-height);
    -webkit-tap-highlight-color: transparent;
    color-scheme: light;
    scrollbar-color: var(--studio-scrollbar-thumb) transparent;
    scrollbar-width: thin;
  }
  :host([dark]) { color-scheme: dark; }
  * { box-sizing: border-box; }
  .hidden { display: none !important; }
  .studio-root {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: var(--studio-bg);
  }
  h2, h3, h4, p { margin: 0; }
  code, .mono {
    font-family: var(--studio-font-code);
    font-size:var(--studio-font-secondary);
  }
  a { color: var(--studio-primary); }

  /* ---------- Upgrade banner ---------- */
  .studio-rev-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-2) var(--studio-space-4);
    background: var(--studio-warning-tint);
    border-bottom: 1px solid var(--studio-warning);
    color: var(--studio-text);
    z-index: 40;
  }

  /* ---------- Title bar ---------- */
  header.latter-top-titlebar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    height: var(--studio-header-height);
    padding: 0 var(--studio-space-3);
    background: var(--studio-header-bg);
    color: var(--studio-header-text);
    border-bottom: var(--studio-header-border);
    position: sticky;
    top: 0;
    z-index: 30;
  }
  .titlebar-brand {
    display: flex;
    align-items: center;
    gap: var(--studio-space-3);
    font-size:var(--studio-font-title);
    font-weight: var(--studio-weight-regular);
    user-select: none;
  }
  .titlebar-brand .ha-menu-btn { color: var(--studio-header-icon); display: none; }
  :host([narrow]) .titlebar-brand .ha-menu-btn { display: inline-flex; }
  .titlebar-title { padding-inline-start: var(--studio-space-3); }
  :host([narrow]) .titlebar-title { padding-inline-start: 0; }
  .titlebar-actions {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
  }

  /* ---------- Shell & navigation ---------- */
  .app-shell {
    display: grid;
    grid-template-columns: var(--studio-sidebar-width) minmax(0, 1fr);
    min-height: calc(100vh - var(--studio-header-height));
  }
  aside.sidebar {
    background: var(--studio-sidebar-bg);
    border-right: 1px solid var(--studio-divider);
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-4) var(--studio-space-3);
    position: sticky;
    top: var(--studio-header-height);
    height: calc(100vh - var(--studio-header-height));
    overflow-y: auto;
  }
  .scope-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    background: var(--studio-input-bg);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .scope-tab {
    min-height: var(--studio-control-height-compact);
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
  }
  .scope-tab.active {
    background: var(--studio-btn-tonal-bg);
    color: var(--studio-btn-tonal-text);
  }
  .nav-list {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
  }
  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    width: 100%;
    min-height: var(--studio-control-height);
    padding: 0 var(--studio-space-3);
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    text-align: left;
    white-space: nowrap;
    cursor: pointer;
  }
  .nav-btn:hover { background: var(--studio-hover); }
  .nav-btn.active {
    background: var(--studio-primary-tint);
    color: var(--studio-primary);
  }
  .nav-btn.nav-back-btn { color: var(--studio-text-secondary); }
  .nav-device-title {
    padding: var(--studio-space-2) var(--studio-space-3);
    border-top: 1px solid var(--studio-divider);
    border-bottom: 1px solid var(--studio-divider);
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  #nav-scope-device .nav-btn:not(.nav-back-btn) { padding-left: var(--studio-space-4); }
  .nav-badge {
    min-width: 20px;
    padding: 0 var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    text-align: center;
    font-variant-numeric: tabular-nums;
  }
  .main-area { min-width: 0; }
  .content-wrap {
    max-width: 1140px;
    margin: 0 auto;
    padding: var(--studio-space-5) var(--studio-space-5) var(--studio-space-5);
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
    container-type: inline-size;
    container-name: studio-content;
  }
  .content-wrap > section {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
  }
  .page-title {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    font-size:var(--studio-font-title);
    font-weight: var(--studio-weight-regular);
  }
  .page-subtitle {
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .is-loading .content-wrap > section { display: none !important; }
  .columns {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-4);
    align-items: start;
  }
  .column {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
    min-width: 0;
  }
  @container studio-content (max-width: 760px) {
    .columns { grid-template-columns: minmax(0, 1fr); }
  }

  /* ---------- Card ---------- */
  .card {
    min-width: 0;
    container-type: inline-size;
    background: var(--studio-surface);
    border: var(--studio-card-border-width) solid var(--studio-card-border);
    border-radius: var(--studio-radius-card);
    box-shadow: var(--studio-card-shadow);
    color: var(--studio-text);
  }
  .card.danger { border-color: var(--studio-error); }
  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-card-top) var(--studio-space-4) 0;
  }
  .card-heading {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    min-width: 0;
    flex: 1 1 240px;
  }
  .card-title {
    font-size:var(--studio-font-card-title);
    font-weight: var(--studio-weight-regular);
    letter-spacing: var(--studio-card-title-tracking);
    line-height: var(--studio-line-height-condensed);
  }
  .card-subtitle, .row-description, .help-text {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .card-header-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .card-content {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-4);
  }
  .card-actions {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    padding: var(--studio-space-2);
    border-top: 1px solid var(--studio-divider);
  }
  details.card > summary {
    list-style: none;
    cursor: pointer;
    padding-bottom: var(--studio-space-card-top);
  }
  details.card > summary::-webkit-details-marker { display: none; }
  details.card > summary::after {
    content: "▾";
    color: var(--studio-text-secondary);
    transition: transform 0.15s ease;
  }
  details.card[open] > summary::after { transform: rotate(180deg); }
  details.card[open] > summary { border-bottom: 1px solid var(--studio-divider); }
  details.sub-collapsible {
    border-top: 1px solid var(--studio-divider);
    padding-top: var(--studio-space-3);
  }
  details.sub-collapsible > summary {
    cursor: pointer;
    font-weight: var(--studio-weight-medium);
  }
  details.sub-collapsible > .card-content { padding: var(--studio-space-3) 0 0; }
  .area-presence-box {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3) var(--studio-space-4);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    scroll-margin-top: calc(var(--studio-header-height) + var(--studio-space-4));
  }
  .area-box-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .area-box-heading {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .area-box-title {
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
  }
  .area-box-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .area-box-meta {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .area-presence-box > .settings-row {
    min-height: var(--studio-control-height);
    padding: var(--studio-space-2) 0 0;
    border-top: 1px solid var(--studio-divider);
  }
  .area-presence-box > details.sub-collapsible {
    padding-top: var(--studio-space-2);
  }
  .area-presence-box > details.sub-collapsible > summary {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .area-presence-box > details.sub-collapsible[open] > summary,
  .area-presence-box > details.sub-collapsible > summary:hover {
    color: var(--studio-text);
  }
  .subsection-title {
    padding-top: var(--studio-space-3);
    border-top: 1px solid var(--studio-divider);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-medium);
  }
  .card-content > .subsection-title:first-child { padding-top: 0; border-top: none; }

  /* ---------- Settings row & controls ---------- */
  .settings-list {
    display: flex;
    flex-direction: column;
  }
  .settings-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--studio-space-4);
    min-height: var(--studio-row-min-height);
    padding: var(--studio-space-2) 0;
  }
  .settings-row-text {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-width: 0;
  }
  .row-label { font-weight: var(--studio-weight-regular); }
  .row-description { line-height: normal; }
  .settings-row-control {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .settings-row-control select,
  .settings-row-control input[type="text"],
  .settings-row-control input[type="search"],
  .settings-row-control input[type="number"],
  .settings-row-control input[type="time"],
  .settings-row-control input[type="password"] {
    width: 260px;
    max-width: 100%;
  }
  .settings-row-control input[type="number"],
  .settings-row-control input[type="time"],
  .settings-row-control input[type="password"] { width: 140px; }
  .settings-row.stacked { grid-template-columns: minmax(0, 1fr); }
  .settings-row.stacked .settings-row-control { justify-content: stretch; }
  .settings-row.stacked .settings-row-control > * { flex: 1 1 200px; width: auto; }
  select, input[type="text"], input[type="search"], input[type="number"], input[type="time"], input[type="password"], textarea {
    min-height: var(--studio-control-height);
    padding: 0 var(--studio-space-3);
    border: none;
    border-bottom: 1px solid var(--studio-field-line);
    border-radius: var(--studio-radius-field) var(--studio-radius-field) 0 0;
    background: var(--studio-field-bg);
    color: var(--studio-text);
    color-scheme: inherit;
    font: inherit;
    transition: background-color 0.15s ease-out;
  }
  textarea {
    padding: var(--studio-space-2) var(--studio-space-3);
    resize: vertical;
  }
  select:hover, input[type="text"]:hover, input[type="search"]:hover, input[type="number"]:hover, input[type="time"]:hover, input[type="password"]:hover, textarea:hover { background: var(--studio-field-bg-hover); }
  select option, select optgroup { background-color: var(--studio-popup-bg); color: var(--studio-text); }
  input::placeholder, textarea::placeholder { color: var(--studio-text-secondary); opacity: 1; }
  input[readonly] { color: var(--studio-text-secondary); }
  input[type="file"] { color: var(--studio-text-secondary); font: inherit; }
  input[type="range"] { width: 140px; accent-color: var(--studio-primary); }
  select:focus-visible, input:focus-visible, textarea:focus-visible, button:focus-visible, summary:focus-visible, [tabindex]:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  select:focus-visible, input[type="text"]:focus-visible, input[type="search"]:focus-visible, input[type="number"]:focus-visible, input[type="time"]:focus-visible, input[type="password"]:focus-visible, textarea:focus-visible {
    outline: none;
    border-bottom-color: var(--studio-primary);
    box-shadow: inset 0 -1px 0 var(--studio-primary);
  }
  .switch {
    appearance: none;
    position: relative;
    width: 48px;
    height: 24px;
    margin: 0;
    border: 1px solid var(--studio-switch-border);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-switch-track);
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }
  .switch::after {
    content: "";
    position: absolute;
    top: 2px;
    left: 2px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--studio-switch-thumb);
    box-shadow: var(--studio-switch-thumb-shadow);
    transition: transform 0.15s ease, background-color 0.15s ease;
  }
  .switch:checked { background: var(--studio-switch-on-track); border-color: var(--studio-switch-on-border); }
  .switch:checked::after { transform: translateX(24px); background: var(--studio-switch-on-thumb); }
  .switch:disabled { opacity: 0.3; cursor: not-allowed; }
  .input-action-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .input-action-row > input:not([type="file"]), .input-action-row > select { flex: 1 1 180px; min-width: 0; }
  .input-action-row > input[type="file"] { flex: 0 1 auto; max-width: 100%; }
  .segmented {
    display: inline-flex;
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
  }
  .segmented button {
    min-height: var(--studio-control-height-compact);
    padding: 0 var(--studio-space-3);
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    cursor: pointer;
  }
  .segmented button[aria-checked="true"] { background: var(--studio-btn-tonal-bg); color: var(--studio-btn-tonal-text); }
  .inline-switch { display: inline-flex; align-items: center; gap: var(--studio-space-2); cursor: pointer; white-space: nowrap; }
  .list-row {
    display: flex;
    align-items: flex-end;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .list-row-main {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--studio-space-2);
    flex: 1;
    min-width: 0;
  }
  .list-row-grow { flex: 1; min-width: 0; }
  .list-block {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .list-row-head {
    display: flex;
    align-items: flex-end;
    gap: var(--studio-space-2);
  }
  .stacked-field {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-width: 0;
  }
  .stacked-field > label, .stacked-field > .field-label {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .stacked-field > select, .stacked-field > input { width: 100%; }
  .stack {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
  }

  /* ---------- Buttons ---------- */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height);
    padding: 0 var(--studio-space-4);
    border: none;
    border-radius: var(--studio-radius-button);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    line-height: 1;
    white-space: nowrap;
    cursor: pointer;
    transition: background-color 0.15s ease-out;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-compact {
    min-height: var(--studio-control-height-compact);
    padding: 0 var(--studio-space-3);
  }
  .btn-primary { background: var(--studio-btn-accent-bg); color: var(--studio-btn-accent-text); }
  .btn-primary:hover:not(:disabled) { background: var(--studio-btn-accent-bg-hover); }
  .btn-secondary { background: var(--studio-btn-tonal-bg); color: var(--studio-btn-tonal-text); }
  .btn-secondary:hover:not(:disabled) { background: var(--studio-btn-tonal-bg-hover); }
  .btn-text {
    background: transparent;
    color: var(--studio-btn-tonal-text);
    padding: 0 var(--studio-space-3);
  }
  .btn-text:hover:not(:disabled) { background: var(--studio-btn-plain-hover); }
  .btn-danger { background: var(--studio-danger-tonal-bg); color: var(--studio-danger-tonal-text); }
  .btn-danger:hover:not(:disabled) { filter: brightness(0.95); }
  .btn-danger-filled { background: var(--studio-danger-loud-bg); color: var(--studio-danger-loud-text); }
  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: var(--studio-control-height);
    height: var(--studio-control-height);
    padding: 0;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .btn-icon:hover { background: var(--studio-hover); }
  .btn-icon.danger { color: var(--studio-error); }
  .btn-icon svg { width: 20px; height: 20px; fill: currentColor; }
  .quick-action-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-2);
    padding-bottom: var(--studio-space-3);
    border-bottom: 1px solid var(--studio-divider);
  }
  .quick-action-grid:last-child {
    padding-bottom: 0;
    border-bottom: none;
  }
  .quick-action-btn {
    justify-content: flex-start;
    gap: var(--studio-space-2);
    min-height: var(--studio-control-height);
    padding: var(--studio-space-2) var(--studio-space-3);
    border-radius: var(--studio-radius-control);
    white-space: normal;
    text-align: left;
    line-height: var(--studio-line-height-condensed);
  }
  .quick-action-btn svg {
    width: 18px;
    height: 18px;
    fill: currentColor;
    flex-shrink: 0;
  }

  /* ---------- Data display ---------- */
  .kv-list { display: flex; flex-direction: column; gap: 0; }
  .kv-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    min-height: var(--studio-control-height);
    padding: var(--studio-space-1) 0;
  }
  .kv-row > span:first-child { color: var(--studio-text-secondary); }
  .kv-row > strong, .kv-value {
    font-weight: var(--studio-weight-medium);
    font-variant-numeric: tabular-nums;
    text-align: right;
  }
  button.kv-row {
    width: 100%;
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  button.kv-row:hover { background: var(--studio-hover); }
  button.kv-row > strong::after {
    content: " ›";
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .table-wrap {
    width: 100%;
    overflow-x: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  table.data-table {
    width: 100%;
    border-collapse: collapse;
    text-align: left;
  }
  table.data-table th {
    padding: 0;
    border-bottom: 1px solid var(--studio-divider);
    white-space: nowrap;
  }
  .sort-btn {
    width: 100%;
    padding: var(--studio-space-3) var(--studio-space-3);
    border: none;
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    text-align: left;
    cursor: pointer;
  }
  .sort-btn:hover { color: var(--studio-text); }
  th[aria-sort="ascending"] .sort-btn, th[aria-sort="descending"] .sort-btn { color: var(--studio-primary); }
  table.data-table td {
    padding: var(--studio-space-3);
    border-bottom: 1px solid var(--studio-divider);
    white-space: nowrap;
  }
  table.data-table tbody tr:last-child td { border-bottom: none; }
  table.data-table tbody tr { cursor: pointer; }
  table.data-table tbody tr:hover, table.data-table tbody tr:focus-visible { background: var(--studio-hover); }
  td.col-name { font-weight: var(--studio-weight-medium); }
  td.col-open { color: var(--studio-text-secondary); text-align: right; }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: 22px;
    padding: 0 var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .chip-primary { background: var(--studio-primary-tint); color: var(--studio-primary); }
  .chip-success { background: var(--studio-success-tint); color: var(--studio-success); }
  .chip-warning { background: var(--studio-warning-tint); color: var(--studio-warning); }
  .chip-error { background: var(--studio-error-tint); color: var(--studio-error); }
  .status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    margin-right: var(--studio-space-2);
    border-radius: 50%;
    background: var(--studio-text-disabled);
  }
  .chip > .status-dot { margin-right: var(--studio-space-1); }
  .status-dot.online { background: var(--studio-success); }
  .status-dot.update { background: var(--studio-warning); }
  .status-tiles {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-2);
  }
  @media (max-width: 480px) {
    .status-tiles { grid-template-columns: minmax(0, 1fr); }
  }
  .status-tile {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--studio-space-1);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: inherit;
    font: inherit;
    text-align: left;
  }
  button.status-tile {
    cursor: pointer;
    transition: background-color 0.15s ease-out, border-color 0.15s ease-out;
  }
  button.status-tile:hover {
    background: var(--studio-hover);
    border-color: var(--studio-primary);
  }
  button.status-tile:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .status-tile-head {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
  }
  .status-tile-head svg {
    width: 16px;
    height: 16px;
    fill: currentColor;
    flex-shrink: 0;
  }
  .status-tile-value {
    margin-top: var(--studio-space-1);
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
  }
  .status-tile-meta {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
    line-height: var(--studio-line-height-condensed);
  }
  .status-tile > .signal-track { margin-top: var(--studio-space-1); }
  .status-assignments {
    padding-top: var(--studio-space-2);
    border-top: 1px solid var(--studio-divider);
  }
  .status-assignments strong {
    display: inline-flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--studio-space-2);
  }
  .pill-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height-compact);
    padding: 0 var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font: inherit;
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
  }
  .pill.enabled {
    border-color: var(--studio-primary);
    background: var(--studio-primary-tint);
    color: var(--studio-text);
  }
  .pill-move {
    border: none;
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    padding: 0 var(--studio-space-1);
    cursor: pointer;
  }
  .pill-move:hover { color: var(--studio-primary); }
  .pill-toggle {
    padding: 0;
    border: none;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .pill-toggle:disabled { opacity: 0.5; cursor: not-allowed; }
  .swatch {
    display: inline-block;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    border: 1px solid var(--studio-divider);
    background: var(--swatch-color, var(--studio-primary));
    flex-shrink: 0;
  }

  /* ---------- BLE rows & upload progress ---------- */
  #card-ble-calibration {
    scroll-margin-top: calc(var(--studio-header-height) + var(--studio-space-4));
  }
  .calibrate-target-box {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    transition: border-color 0.2s ease, background-color 0.2s ease;
  }
  .calibrate-target-box.handoff-active {
    border: 2px solid var(--studio-warning);
    background: var(--studio-warning-tint);
  }
  .calibrate-handoff-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    font-weight: var(--studio-weight-medium);
  }
  .signal-row {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .signal-row.winner { border-color: var(--studio-primary); }
  .proxy-trim-details {
    padding-top: var(--studio-space-2);
  }
  .proxy-trim-details > summary {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .proxy-trim-details[open] > summary,
  .proxy-trim-details > summary:hover {
    color: var(--studio-text);
  }
  .proxy-trim-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding-top: var(--studio-space-2);
  }
  .signal-row-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .signal-row-title {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .signal-meta { color: var(--studio-text-secondary); font-size:var(--studio-font-secondary); }
  .signal-track, .upload-progress {
    height: 6px;
    border-radius: var(--studio-radius-pill);
    background: var(--studio-surface-alt);
    overflow: hidden;
  }
  .signal-fill {
    width: var(--signal-pct, 0%);
    height: 100%;
    background: var(--studio-primary);
    transition: width 0.25s ease;
  }
  .signal-fill.low { background: var(--studio-error); }
  .upload-progress-fill {
    width: var(--upload-pct, 0%);
    height: 100%;
    background: var(--studio-primary);
    transition: width 0.15s ease;
  }

  /* ---------- Wallpapers ---------- */
  .wp-upload-trigger {
    display: inline-flex;
    align-items: center;
  }
  .wp-upload-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    font-size:var(--studio-font-secondary);
    color: var(--studio-text-secondary);
  }
  .wp-gallery {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: var(--studio-space-3);
  }
  .wp-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    text-align: center;
  }
  .wp-gallery > .empty-state { grid-column: 1 / -1; }
  .wp-card.active { border-color: var(--studio-primary); background: var(--studio-primary-tint); }
  .wp-thumb-btn {
    padding: 0;
    border: none;
    background: transparent;
    border-radius: var(--studio-radius-control);
    cursor: pointer;
    line-height: 0;
  }
  .wp-thumb-btn.circle { border-radius: 50%; }
  .wp-thumb-btn:hover .wp-thumb { border-color: var(--studio-primary); }
  .wp-thumb-btn:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .wp-thumb {
    width: 104px;
    height: 104px;
    object-fit: cover;
    background: var(--studio-media-bg);
    border: 1px solid var(--studio-divider);
  }
  .wp-thumb.circle { border-radius: 50%; }
  .wp-thumb.square { border-radius: var(--studio-radius-control); }
  .wp-title {
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    overflow-wrap: anywhere;
  }
  .wp-actions {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
    margin-top: auto;
    width: 100%;
  }
  .btn-icon.wp-star-btn {
    width: var(--studio-control-height-compact);
    height: var(--studio-control-height-compact);
  }
  .btn-icon.wp-star-btn:hover {
    color: var(--studio-warning);
    background: var(--studio-warning-tint);
  }
  .btn-icon.wp-star-btn.starred {
    color: var(--studio-warning);
  }
  .cam-preview {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .cam-preview img {
    width: 100%;
    max-width: 360px;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    border-radius: var(--studio-radius-control);
    background: var(--studio-media-bg);
  }
  .log-output {
    max-height: 380px;
    margin: 0;
    padding: var(--studio-space-3);
    overflow: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    white-space: pre-wrap;
  }

  /* ---------- States ---------- */
  .empty-state {
    padding: var(--studio-space-3) 0;
    color: var(--studio-text-secondary);
  }
  .loading-state {
    display: flex;
    align-items: center;
    gap: var(--studio-space-3);
    padding: var(--studio-space-5) 0;
    color: var(--studio-text-secondary);
  }
  .loading-state::before {
    content: "";
    width: 20px;
    height: 20px;
    border: 2px solid var(--studio-divider);
    border-top-color: var(--studio-primary);
    border-radius: 50%;
    animation: studio-spin 0.8s linear infinite;
  }
  .studio-root:not(.is-loading) #studio-loading { display: none; }
  @keyframes studio-spin { to { transform: rotate(360deg); } }
  .alert {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-2) var(--studio-space-4);
    border-radius: var(--studio-radius-field);
    background: var(--studio-info-tint);
  }
  .alert-error { background: var(--studio-error-tint); }
  .alert-warning { background: var(--studio-warning-tint); }
  .alert-body { display: flex; flex-direction: column; gap: var(--studio-space-1); min-width: 0; }
  .alert-list { margin: 0; padding-left: var(--studio-space-5); }
  .toast {
    position: fixed;
    left: 50%;
    bottom: var(--studio-space-5);
    transform: translateX(-50%);
    z-index: 50;
    max-width: min(560px, calc(100vw - 32px));
    padding: var(--studio-space-3) var(--studio-space-4);
    border-radius: var(--studio-radius-field);
    background: var(--studio-toast-bg);
    color: var(--studio-toast-text);
    box-shadow: var(--studio-overlay-shadow);
  }
  .toast.error { background: var(--studio-danger-loud-bg); color: var(--studio-danger-loud-text); }
  .offscreen { position: fixed; top: -9999px; left: -9999px; }

  /* ---------- Dialogs ---------- */
  dialog.studio-dialog {
    width: min(460px, calc(100vw - 32px));
    padding: var(--studio-space-5);
    border: none;
    border-radius: var(--studio-radius-dialog);
    background: var(--studio-surface);
    color: var(--studio-text);
    box-shadow: var(--studio-overlay-shadow);
  }
  dialog.studio-dialog::backdrop { background: var(--studio-scrim); }
  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
  }
  .dialog-title {
    font-size:var(--studio-font-card-title);
    font-weight: var(--studio-weight-regular);
    line-height: var(--studio-line-height-condensed);
  }
  .dialog-text { color: var(--studio-text-secondary); }
  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: var(--studio-space-2);
    margin-top: var(--studio-space-2);
  }
  dialog.studio-dialog.shortcut-dialog {
    width: min(560px, calc(100vw - 32px));
    max-height: calc(100vh - 32px);
    overflow-y: auto;
  }
  .shortcut-item-row {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    padding: var(--studio-space-2) var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .shortcut-icon-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: var(--studio-control-height-compact);
    height: var(--studio-control-height-compact);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-primary-tint);
    color: var(--studio-primary);
    flex-shrink: 0;
  }
  .shortcut-item-info {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-width: 0;
    flex: 1;
  }
  .shortcut-item-title {
    font-weight: var(--studio-weight-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .shortcut-item-meta {
    font-size:var(--studio-font-secondary);
    color: var(--studio-text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .shortcut-page-group {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-surface-alt);
  }
  .shortcut-page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    color: var(--studio-text-secondary);
  }
  .shortcut-toolbar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .shortcut-icon-row {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
  }
  .shortcut-icon-row input[type="text"] {
    flex: 1;
    min-width: 0;
  }
  .mdi-picker-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
    gap: var(--studio-space-1);
    max-height: 168px;
    overflow-y: auto;
    padding: var(--studio-space-2);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .mdi-picker-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: var(--studio-control-height);
    border: 1px solid transparent;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text);
    cursor: pointer;
  }
  .mdi-picker-btn:hover {
    background: var(--studio-hover);
  }
  .mdi-picker-btn.selected {
    background: var(--studio-primary-tint-strong);
    border-color: var(--studio-primary);
    color: var(--studio-primary);
  }
  .color-wheel { display: flex; justify-content: center; }
  .color-wheel canvas { border-radius: 50%; cursor: crosshair; touch-action: none; }
  .color-hex-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-2);
  }
  .color-hex-row input[type="text"] { width: 120px; font-family: var(--studio-font-code); text-align: center; }
  .color-hex-row input[type="color"] {
    width: var(--studio-control-height);
    height: var(--studio-control-height);
    padding: 0;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: none;
    cursor: pointer;
  }

  /* ---------- Narrow cards and screens ---------- */
  @container (max-width: 520px) {
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row + .settings-row { border-top: 1px solid var(--studio-divider); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select, .settings-row-control input[type="text"], .settings-row-control input[type="password"] { width: 100%; }
  }
  @container (max-width: 360px) {
    .quick-action-grid { grid-template-columns: minmax(0, 1fr); }
  }
  @media (max-width: 860px) {
    .titlebar-brand .ha-menu-btn { display: inline-flex; }
    .titlebar-title { padding-inline-start: 0; }
    .app-shell { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
    aside.sidebar {
      align-self: start;
      position: sticky;
      top: var(--studio-header-height);
      z-index: 25;
      height: auto;
      padding: var(--studio-space-2) var(--studio-space-3);
      border-right: none;
      border-bottom: 1px solid var(--studio-divider);
    }
    .nav-device-title { display: none; }
    .nav-list { flex-direction: row; overflow-x: auto; scrollbar-width: none; }
    .nav-list::-webkit-scrollbar { display: none; }
    .nav-btn { width: auto; border: 1px solid var(--studio-divider); border-radius: var(--studio-radius-pill); }
    #nav-scope-device .nav-btn:not(.nav-back-btn) { padding-left: var(--studio-space-3); }
    .content-wrap { padding: var(--studio-space-4) var(--studio-space-3) var(--studio-space-5); }
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row + .settings-row { border-top: 1px solid var(--studio-divider); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select, .settings-row-control input[type="text"], .settings-row-control input[type="password"] { width: 100%; }
  }
  @media (max-width: 480px) {
    .list-row { flex-wrap: wrap; }
    .list-row-head { flex-wrap: wrap; }
    .list-row-main { grid-template-columns: minmax(0, 1fr); width: 100%; }
  }
`;

// --- src/views/device-audio-view.ts ---
/**
 * Device Audio & Voice View (`audio_voice`, D-031 / D-036):
 * Voice Assistant, Wake Word, Voice Follows Me, Sound & Music Assistant.
 */
function renderDeviceAudioView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const caps = data?.capabilities || {};
  const live = data?.live || {};
  const wwModePref = store.getPref("wake_word_mode");
  const wwDisabled = wwModePref ? String(wwModePref.value) === "Disabled" : false;
  const wakeScreenPref = store.getPref("wake_screen_on_assist");
  const voiceItems = store.getSectionItems("voice");
  const voicePrimary = voiceItems.filter((it) => {
    if (it.domain === "assist_satellite") return false;
    const k = it.key || it.pref_key || (it.entity_id ? it.entity_id.split(".").pop() || "" : "");
    if (k === "va_visual_profile" || k.endsWith("_visual_profile")) return false;
    if (k === "wake_word_mode" || k.endsWith("_wake_word_mode")) return false;
    if (k === "wake_screen_on_assist" || k.endsWith("_wake_screen_on_assist")) return false;
    if (k.startsWith("ww_sens_") || k.includes("_ww_sens_")) return false;
    if (
      wwDisabled &&
      (it.key === "wake_word" || it.key === "wake_word_n" || k.endsWith("_wake_word") || k.endsWith("_wake_word_n"))
    )
      return false;
    return true;
  });
  const sensitivityPrefs = wwDisabled
    ? []
    : store.getPrefs([
        "ww_sens_okay_nabu",
        "ww_sens_hey_luna",
        "ww_sens_hey_jarvis",
        "ww_sens_hey_mycroft",
        "ww_sens_alexa",
      ]);
  const soundPrefs = store.getPrefs([
    "alert_volume",
    "volume_step_size",
    "game_sound_effects",
  ]);
  const soundItems = store.getSectionItems("sound").filter((it) => !it.pref_key);
  const isRoaming = caps.is_roaming_device !== false;
  const dwellSeconds = Number(cfg.area_follow_dwell_s ?? 10);
  const autoMaEntity = cfg.device_slug ? `media_player.${cfg.device_slug}` : "";
  const savedMa = String(cfg.ma_player_entity || "").trim();
  const maUnmatched = live.ma_link_matched === false;
  const hasCustomMaOverride = Boolean(savedMa && savedMa !== autoMaEntity);
  const showMaOverrideRow = maUnmatched || hasCustomMaOverride;
  const maDescription = maUnmatched
    ? `Automatic match did not find ${autoMaEntity || "this Device's player"} in Music Assistant. Choose this Device's player for library playback, queues and lyrics.`
    : `Linked manually (${autoMaEntity || "default slug"} was not used). Clear to return to automatic matching.`;
  const speakerChoices = data?.catalog?.ma_speakers;
  return html`<section id="view-audio_voice">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Voice Assistant &amp; Wake Word</h3>`,
          contentClass: "settings-list",
          body: html`${wwModePref ? renderPrefControlRow(store, wwModePref) : nothing}
            ${voicePrimary.map((it) => renderNativeControlRow(store, it))}
            ${wakeScreenPref ? renderPrefControlRow(store, wakeScreenPref) : nothing}
            ${isRoaming
              ? html`${renderSwitchRow({
                    rowId: "row-sync-device-area",
                    id: "cfg-sync_device_area",
                    label: "Voice Follows Me",
                    description:
                      "Updates this roaming Device's Home Assistant Area when BLE presence settles in a new Area, so Area-less voice commands target where you are.",
                    checked: Boolean(cfg.sync_device_area),
                    onChange: (checked) =>
                      store.stageDeviceSetting(
                        "sync_device_area",
                        checked,
                        "cfg-sync_device_area",
                      ),
                  })}
                  ${renderSettingsRow({
                    id: "row-area-follow-dwell",
                    label: "Voice Follows Me Delay",
                    forId: "cfg-area_follow_dwell_s",
                    description:
                      "How long a BLE-detected Area stays stable before moving the Device (3 to 60 seconds).",
                    control: html`<input
                        type="range"
                        id="cfg-area_follow_dwell_s"
                        min="3"
                        max="60"
                        step="1"
                        .value=${String(dwellSeconds)}
                        @change=${(ev) =>
                          store.stageDeviceSetting(
                            "area_follow_dwell_s",
                            Number((ev.currentTarget).value) || 10,
                            "cfg-area_follow_dwell_s",
                          )}
                      />
                      <span id="dwell-value" class="chip">${fmtNumber(dwellSeconds, store.hass, 0)} s</span>`,
                  })}`
              : nothing}
            ${sensitivityPrefs.length
              ? html`<details class="sub-collapsible">
                  <summary>Wake Word Sensitivity (Per Model)</summary>
                  <div class="card-content settings-list">
                    ${sensitivityPrefs.map((p) => renderPrefControlRow(store, p))}
                  </div>
                </details>`
              : nothing}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Sound &amp; Playback</h3>`,
          contentClass: "settings-list",
          body: html`${renderSelectRow({
              id: "cfg-default_speaker",
              label: "Default Speaker",
              description: "Primary speaker controlled from Music and Home when this Device starts up.",
              value: cfg.default_speaker,
              choices: speakerChoices,
              emptyOptionLabel: "— Automatic (Built-in or Area) —",
              onChange: (val) =>
                store.stageDeviceSetting("default_speaker", val, "cfg-default_speaker"),
            })}
            ${showMaOverrideRow
              ? renderSelectRow({
                  rowId: "row-ma-player-entity",
                  id: "cfg-ma_player_entity",
                  label: "Music Assistant Player",
                  description: maDescription,
                  descId: "desc-ma-player-entity",
                  value: savedMa,
                  choices: data?.catalog?.ma_players,
                  emptyOptionLabel: "— Automatic Match —",
                  onChange: (val) =>
                    store.stageDeviceSetting("ma_player_entity", val, "cfg-ma_player_entity"),
                })
              : nothing}
            ${renderSwitchRow({
              id: "cfg-area_handoff",
              label: "Media Follows This Device to Its New Area",
              description:
                "Transfers active Music Assistant playback when this Device moves to another Area.",
              checked: Boolean(cfg.area_handoff),
              onChange: (checked) =>
                store.stageDeviceSetting("area_handoff", checked, "cfg-area_handoff"),
            })}
            ${soundPrefs.map((p) => renderPrefControlRow(store, p))}
            ${soundItems.map((it) => renderNativeControlRow(store, it))}`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/components/wallpaper-gallery.ts ---
/**
 * Wallpaper Gallery & Multipart XHR Upload Component (Device & System scopes).
 */
function renderStarIcon(filled) {
  if (filled) {
    return html`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.62L12 2 9.19 8.62 2 9.24l5.45 4.73L5.82 21 12 17.27Z"
      />
    </svg>`;
  }
  return html`<svg viewBox="0 0 24 24" aria-hidden="true">
    <path
      d="M12 15.39l-3.76 2.27.99-4.28-3.32-2.88 4.38-.38L12 6.09l1.71 4.03 4.38.38-3.32 2.88.99 4.28L12 15.39M22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.45 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24Z"
    />
  </svg>`;
}
function renderWallpaperGalleryItems(
  store,
  scope,
  items,
  displayShape,
) {
  if (!items.length) {
    return html`<p class="empty-state">No wallpapers available yet.</p>`;
  }
  const shapeClass = displayShape === "circle" ? "circle" : "square";
  return html`${repeat(
    items,
    (wp) => wp.id,
    (wp) => {
      const label = wp.name || wp.id;
      const isActive = Boolean(wp.active);
      const isFav = Boolean(wp.favorite);
      const canDelete = Boolean(wp.deletable ?? wp.kind === "upload");
      const thumbSrc = wp.thumb_url || wp.preview_url || "";
      const activeCls = isActive ? "wp-card active" : "wp-card";
      const onUse = () => {
        void store.selectWallpaperSource(wp.id);
      };
      const onFav = () => {
        void store.toggleWallpaperFav(wp.id);
      };
      const onDel = () => {
        void store.deleteWallpaper(scope, wp.id);
      };
      const thumbImg = thumbSrc
        ? html`<img src=${thumbSrc} alt=${label} loading="lazy" class="wp-thumb ${shapeClass}" />`
        : html`<div class="wp-thumb ${shapeClass}"></div>`;
      return html`<div class=${activeCls}>
        ${scope === "device" && !isActive
          ? html`<button
              type="button"
              aria-label=${`Use wallpaper ${label}`}
              @click=${onUse}
              class="wp-thumb-btn ${shapeClass}"
            >
              ${thumbImg}
            </button>`
          : thumbImg}
        <div class="wp-title">${label}</div>
        <div class="wp-actions">
          ${scope === "device"
            ? html`${isActive
                  ? html`<span class="chip chip-primary">Active</span>`
                  : html`<button type="button" @click=${onUse} class="btn btn-secondary btn-compact">
                      Use
                    </button>`}
                <button
                  type="button"
                  aria-label=${isFav ? `Remove ${label} from favorites` : `Star ${label} for rotation`}
                  aria-pressed=${String(isFav)}
                  title=${isFav ? "Starred for rotation" : "Star for rotation"}
                  @click=${onFav}
                  class="btn-icon wp-star-btn${isFav ? " starred" : ""}"
                >
                  ${renderStarIcon(isFav)}
                </button>
                ${canDelete ? renderTrashIconButton(`Delete wallpaper ${label}`, onDel) : nothing}`
            : canDelete
              ? html`<span class="chip chip-primary">Uploaded</span>
                  ${renderTrashIconButton(`Delete wallpaper ${label}`, onDel)}`
              : html`<span class="chip">Built-in</span>`}
        </div>
      </div>`;
    },
  )}`;
}
function renderWallpaperUploadTrigger(
  store,
  scope,
) {
  const isUploadingThisScope = store.uploadBusy && store.uploadScope === scope;
  const inputId = scope === "device" ? "input-upload-wp" : "input-upload-sys-wp";
  const btnId = scope === "device" ? "btn-upload-wp" : "btn-upload-sys-wp";
  const onFilePick = (ev) => {
    const input = ev.currentTarget;
    const f = input.files && input.files[0] ? input.files[0] : null;
    if (scope === "device") {
      store.selectedDeviceWallpaperFile = f;
    } else {
      store.selectedSystemWallpaperFile = f;
    }
    if (f) {
      void store.uploadWallpaper(scope);
    } else {
      store.host.requestUpdate();
    }
  };
  const onTriggerPick = (ev) => {
    const btn = ev.currentTarget;
    const fileInput = btn?.parentElement?.querySelector("input[type='file']")
            ;
    fileInput?.click();
  };
  return html`<span class="wp-upload-trigger">
    <input
      type="file"
      id=${inputId}
      accept="image/*"
      aria-label="Wallpaper image (up to 15 MB)"
      @change=${onFilePick}
      class="offscreen"
    />
    <button
      type="button"
      id=${btnId}
      ?disabled=${store.uploadBusy}
      @click=${onTriggerPick}
      class="btn btn-secondary btn-compact"
    >
      ${isUploadingThisScope ? "Uploading…" : "Upload Photo"}
    </button>
  </span>`;
}
function renderWallpaperUploadProgress(
  store,
  scope,
) {
  const isUploadingThisScope = store.uploadBusy && store.uploadScope === scope;
  if (!isUploadingThisScope) return nothing;
  const pctStyle = `--upload-pct:${store.uploadPercent}%`;
  return html`<div class="stack">
    <div class="wp-upload-status">
      <span>Uploading photo…</span>
      <span class="chip chip-primary">${store.uploadPercent}%</span>
    </div>
    <div
      class="upload-progress"
      role="progressbar"
      aria-valuenow=${String(store.uploadPercent)}
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div class="upload-progress-fill" style=${pctStyle}></div>
    </div>
  </div>`;
}

// --- src/views/device-display-view.ts ---
/**
 * Device Display View (`display`, D-027 / D-029 / D-033 / D-034 / D-036):
 * Visual & aesthetic preferences across screens.
 * Column 1: Home Screen (Wake Greeting, Weather Background & Sun & Moon), Screensavers, Voice Assistant (Visual Profile), Brightness & Clock.
 * Column 2: Colors, Wallpapers & Media Player (Album Art & Overlay Style).
 */
function renderDeviceDisplayView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const palettes = data?.system_config?.custom_palettes || [];
  // Home Screen card
  const wakeGreetingPref = store.getPref("wake_greeting");
  const weatherBgPref = store.getPref("weather_background");
  const weatherBgVal = String(weatherBgPref?.value ?? "").toLowerCase();
  const weatherBgOff =
    !weatherBgPref || !weatherBgPref.value || weatherBgVal === "off" || weatherBgVal === "disabled";
  const sunPref = store.getPref("home_sun");
  const moonPref = store.getPref("home_moon");
  const celestialItems = [
    { pref: sunPref, label: "Sun" },
    { pref: moonPref, label: "Moon" },
  ].filter((c) => Boolean(c.pref));
  const renderCelestialRow = () =>
    renderSettingsRow({
      id: "weather-celestial-bodies",
      label: "Sun & Moon",
      description: "Choose which sky bodies appear on the live Weather Background.",
      control: html`<div class="pill-list" role="group" aria-label="Sun and Moon">
        ${celestialItems.map(({ pref, label }) => {
          const isOn = Boolean(pref.value);
          return html`<span class="pill ${isOn ? "enabled" : ""}">
            <button
              type="button"
              aria-pressed=${String(isOn)}
              @click=${() => store.stageDeviceSetting(pref.key, !isOn)}
              class="pill-toggle"
            >
              ${isOn ? `✓ ${label}` : `+ ${label}`}
            </button>
          </span>`;
        })}
      </div>`,
    });
  const hasHomeCard = Boolean(wakeGreetingPref || weatherBgPref || celestialItems.length > 0);
  // Screensavers card
  const screensaverPrefs = store.getPrefs([
    "docked_screensaver",
    "screensaver_style",
    "docked_idle_timeout",
  ]);
  const activateScreensaverBtn = store
    .getSectionItems("actions")
    .find(
      (it) =>
        it.domain === "button" &&
        (it.device_command === "activate_screensaver" ||
          it.key === "activate_screensaver" ||
          it.entity_id?.endsWith("_activate_screensaver")),
    );
  // Voice Assistant card
  const voiceVisualPref = store.getPref("va_visual_profile");
  // Brightness card
  const autoBrtPref = store.getPref("auto_brightness_mode");
  const autoBrtState = String(autoBrtPref?.value ?? "").trim();
  const autoBrtOff = autoBrtState === "Disabled" || autoBrtState === "off";
  const autoBrtTimeSchedule = autoBrtState === "Time Schedule";
  const brightnessPrefs = store.getPrefs([
    "auto_brightness_mode",
    "manual_brightness",
    "day_brightness",
    "night_brightness",
    "day_start_hour",
    "night_start_hour",
  ]);
  const visibleBrightnessPrefs = brightnessPrefs.filter((p) => {
    if (autoBrtPref) {
      if (autoBrtOff && (p.key === "day_brightness" || p.key === "night_brightness")) {
        return false;
      }
      if (!autoBrtOff && p.key === "manual_brightness") {
        return false;
      }
      if (!autoBrtTimeSchedule && (p.key === "day_start_hour" || p.key === "night_start_hour")) {
        return false;
      }
    }
    return true;
  });
  // Clock card
  const clockPrefs = store.getPrefs(["clock_face", "time_format"]);
  // Column 2: Colors card
  const colorProfilePref = store.getPref("color_profile");
  const curHex = isValidHexColor(cfg.device_custom_color)
    ? String(cfg.device_custom_color).toUpperCase()
    : defaultThemeHex(store.host);
  const swatchStyle = `--swatch-color:${curHex}`;
  // Column 2: Wallpapers
  const curCycle = Number(cfg.wallpaper_cycle_minutes || 0);
  const wallpapers = data?.wallpapers || [];
  const activeWp = wallpapers.find((wp) => Boolean(wp.active)) || null;
  const hasActiveWallpaper = Boolean(activeWp);
  const isRotating = curCycle > 0;
  const starredCount = wallpapers.filter((wp) => Boolean(wp.favorite)).length;
  const allStarred = wallpapers.length > 0 && starredCount === wallpapers.length;
  const wpStatusText = isRotating
    ? `${activeWp ? `${activeWp.name} • rotating` : "Rotating"} ${
        starredCount > 0
          ? `${starredCount} starred wallpaper${starredCount === 1 ? "" : "s"}`
          : `all ${wallpapers.length} wallpapers`
      }.`
    : hasActiveWallpaper
      ? `${activeWp?.name || "Selected"} (static — not rotating).`
      : "Off — click Use on a wallpaper below or enable rotation.";
  const wpRotationHint =
    starredCount === 0
      ? "No wallpapers starred — rotation cycles through all wallpapers."
      : starredCount === 1
        ? "1 wallpaper starred — star at least 2 to cycle between favorites."
        : `${starredCount} of ${wallpapers.length} wallpapers starred for rotation.`;
  // Column 2: Media Player card
  const mediaAppearancePrefs = store.getPrefs(["album_art_style", "music_overlay_style"]);
  return html`<section id="view-display">
    <div class="columns">
      <div class="column">
        ${hasHomeCard
          ? renderCard({
              heading: html`<h3 class="card-title">Home Screen</h3>`,
              contentClass: "settings-list",
              body: html`<div id="embedded-home" class="settings-list">
                ${wakeGreetingPref ? renderPrefControlRow(store, wakeGreetingPref) : nothing}
                ${weatherBgPref ? renderPrefControlRow(store, weatherBgPref) : nothing}
                ${!weatherBgOff && celestialItems.length > 0 ? renderCelestialRow() : nothing}
              </div>`,
            })
          : nothing}

        ${screensaverPrefs.length || activateScreensaverBtn
          ? renderCard({
              heading: html`<h3 class="card-title">Screensavers</h3>`,
              contentClass: "settings-list",
              body: html`${screensaverPrefs.map((p) => renderPrefControlRow(store, p))}
                ${activateScreensaverBtn
                  ? renderSettingsRow({
                      label: entityLabel(
                        activateScreensaverBtn.name || activateScreensaverBtn.entity_id,
                      ),
                      description: "Starts the screensaver on this Device immediately.",
                      control: html`<button
                        type="button"
                        ?disabled=${String(activateScreensaverBtn.state ?? "") === "unavailable"}
                        @click=${() => {
                          const toastMsg = `Triggered "${entityLabel(activateScreensaverBtn.name || activateScreensaverBtn.entity_id)}"`;
                          if (activateScreensaverBtn.device_command) {
                            void store.runDeviceAction(
                              activateScreensaverBtn.device_command,
                              toastMsg,
                            );
                          } else {
                            void store.espAction(
                              activateScreensaverBtn.entity_id,
                              "press",
                              undefined,
                              toastMsg,
                            );
                          }
                        }}
                        class="btn btn-secondary btn-compact"
                      >
                        Preview
                      </button>`,
                    })
                  : nothing}`,
            })
          : nothing}

        ${voiceVisualPref
          ? renderCard({
              heading: html`<h3 class="card-title">Voice Assistant</h3>`,
              contentClass: "settings-list",
              body: renderPrefControlRow(store, voiceVisualPref),
            })
          : nothing}

        ${visibleBrightnessPrefs.length
          ? renderCard({
              heading: html`<h3 class="card-title">Brightness</h3>`,
              contentClass: "settings-list",
              body: visibleBrightnessPrefs.map((p) => renderPrefControlRow(store, p)),
            })
          : nothing}

        ${clockPrefs.length
          ? renderCard({
              heading: html`<h3 class="card-title">Clock</h3>`,
              contentClass: "settings-list",
              body: clockPrefs.map((p) => renderPrefControlRow(store, p)),
            })
          : nothing}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Colors</h3>`,
          contentClass: "settings-list",
          body: html`${colorProfilePref ? renderPrefControlRow(store, colorProfilePref) : nothing}
            ${renderSettingsRow({
              label: "Custom Color",
              forId: "dev-custom-palette-select",
              description: "Used when Color Profile is set to Custom.",
              control: html`<span class="swatch" style=${swatchStyle} aria-hidden="true"></span>
                <select
                  id="dev-custom-palette-select"
                  .value=${curHex}
                  @change=${(ev) => {
                    const val = (ev.currentTarget).value;
                    if (val) store.applyDeviceCustomColor(val, true);
                  }}
                >
                  ${!palettes.length
                    ? html`<option value=${curHex} selected>Current (${curHex})</option>`
                    : html`
                        ${!palettes.some((p) => p.hex.toUpperCase() === curHex)
                          ? html`<option value=${curHex} selected>Current (${curHex})</option>`
                          : nothing}
                        ${palettes.map((p) => {
                          const h = p.hex.toUpperCase();
                          return html`<option value=${h} ?selected=${h === curHex}>
                            ${p.name || h} (${h})
                          </option>`;
                        })}
                      `}
                </select>
                <button
                  type="button"
                  @click=${() => store.openColorWheelModal("device")}
                  class="btn btn-secondary btn-compact"
                >
                  Add Color
                </button>`,
            })}`,
        })}

        ${renderCard({
          heading: html`<h3 class="card-title">Wallpapers</h3>`,
          subtitle: "Shared presets and uploaded photos cropped for this display.",
          headerActions: renderWallpaperUploadTrigger(store, "device"),
          contentClass: "stack",
          body: html`${renderWallpaperUploadProgress(store, "device")}
            <div class="settings-list">
              ${renderSettingsRow({
                id: "wp-status-row",
                label: "Active Wallpaper",
                description: wpStatusText,
                control: isRotating
                  ? html`<button
                        type="button"
                        id="btn-stop-wp-rotation"
                        @click=${() => void store.setWallpaperRotation(0)}
                        class="btn btn-secondary btn-compact"
                      >
                        Stop Rotation
                      </button>
                      <button
                        type="button"
                        id="btn-turn-off-wp"
                        @click=${() => void store.selectWallpaperSource("")}
                        class="btn btn-secondary btn-compact"
                      >
                        Turn Off Wallpaper
                      </button>`
                  : hasActiveWallpaper
                    ? html`${wallpapers.length >= 2
                          ? html`<button
                              type="button"
                              id="btn-enable-wp-rotation"
                              @click=${() => void store.setWallpaperRotation(15)}
                              class="btn btn-secondary btn-compact"
                            >
                              Enable Rotation
                            </button>`
                          : nothing}
                        <button
                          type="button"
                          id="btn-turn-off-wp"
                          @click=${() => void store.selectWallpaperSource("")}
                          class="btn btn-secondary btn-compact"
                        >
                          Turn Off Wallpaper
                        </button>`
                    : wallpapers.length >= 2
                      ? html`<button
                          type="button"
                          id="btn-enable-wp-rotation"
                          @click=${() => void store.setWallpaperRotation(15)}
                          class="btn btn-primary btn-compact"
                        >
                          Enable Rotation
                        </button>`
                      : nothing,
              })}
              ${renderSettingsRow({
                id: "wp-rotation-row",
                label: "Rotation Interval",
                forId: "cfg-wallpaper_cycle_minutes",
                description: wpRotationHint,
                control: html`<select
                    id="cfg-wallpaper_cycle_minutes"
                    aria-label="Wallpaper rotation interval"
                    .value=${String(curCycle)}
                    @change=${(ev) =>
                      void store.setWallpaperRotation(
                        Number((ev.currentTarget).value) || 0,
                      )}
                  >
                    ${WALLPAPER_ROTATION_OPTIONS.map(
                      (opt) =>
                        html`<option value=${String(opt.value)} ?selected=${opt.value === curCycle}>
                          ${opt.label}
                        </option>`,
                    )}
                  </select>
                  ${wallpapers.length > 0 && !allStarred
                    ? html`<button
                        type="button"
                        id="btn-star-all-wp"
                        @click=${() =>
                          void store.setAllWallpaperFavorites(wallpapers.map((w) => w.id))}
                        class="btn btn-text btn-compact"
                      >
                        Star All
                      </button>`
                    : nothing}
                  ${starredCount > 0
                    ? html`<button
                        type="button"
                        id="btn-clear-stars-wp"
                        @click=${() => void store.setAllWallpaperFavorites([])}
                        class="btn btn-text btn-compact"
                      >
                        Clear Stars
                      </button>`
                    : nothing}`,
              })}
            </div>
            <div class="wp-gallery">
              ${renderWallpaperGalleryItems(
                store,
                "device",
                wallpapers,
                String(cfg.display_shape || "square"),
              )}
            </div>`,
        })}

        ${mediaAppearancePrefs.length
          ? renderCard({
              heading: html`<h3 class="card-title">Media Player</h3>`,
              contentClass: "settings-list",
              body: mediaAppearancePrefs.map((p) => renderPrefControlRow(store, p)),
            })
          : nothing}
      </div>
    </div>
  </section>`;
}

// --- src/views/device-interface-view.ts ---
/**
 * Device Interface View (`interface`, D-026 / D-028 / D-030 / D-033 / D-034 / D-035 / D-036 / D-037 / D-038):
 * Navigation, screen structure & content routing preferences.
 * Column 1: Home Screen (Enable Home Screen, Start Screen, Home Time Tap, Return to Home Timeout, Dock Apps & Activity Card),
 *           Home Controls & Time (Local Clock Label, Show UTC Clock, custom-labeled World Clocks & 2-way Alarms).
 * Column 2: Area Controls (Area Categories pills), Media Player (Shortcuts & Library Sorting) & Remote Controls.
 */
const DEFAULT_ALARM_SLOTS = [
  { time: "07:00", enabled: false, recurrence: 1 },
  { time: "08:30", enabled: false, recurrence: 2 },
  { time: "09:00", enabled: false, recurrence: 2 },
];
const PINNED_UTC_ZONES = new Set(["UTC", "Etc/UTC", "GMT", "Etc/GMT", "Etc/GMT+0", "Etc/GMT-0", "Etc/GMT0"]);
const IANA_ZONE_PATTERN = /^[A-Za-z0-9_+-]+(?:\/[A-Za-z0-9_+-]+)+$/;
const TEXT_INPUT_DEBOUNCE_MS = 600;
function isImeSafeEnter(ev) {
  return ev.key === "Enter" && !ev.isComposing && ev.keyCode !== 229;
}
function sanitizeClockLabel(raw, maxBytes = 32) {
  const str = String(raw ?? "");
  let collapsed = "";
  let prevSpace = true;
  for (const ch of str) {
    const code = ch.charCodeAt(0);
    if (
      code < 0x20 ||
      code === 0x7f ||
      ch === "|" ||
      ch === ";" ||
      ch === "\x1e" ||
      ch === "\x1f" ||
      ch === " " ||
      ch === "\t" ||
      ch === "\r" ||
      ch === "\n"
    ) {
      if (!prevSpace) {
        collapsed += " ";
        prevSpace = true;
      }
      continue;
    }
    collapsed += ch;
    prevSpace = false;
  }
  const trimmed = collapsed.trim();
  if (typeof TextEncoder === "undefined") {
    return trimmed.slice(0, maxBytes).trimEnd();
  }
  const enc = new TextEncoder();
  if (enc.encode(trimmed).length <= maxBytes) {
    return trimmed;
  }
  let out = "";
  for (const cp of trimmed) {
    if (enc.encode(out + cp).length > maxBytes) break;
    out += cp;
  }
  return out.trimEnd();
}
function fallbackLabelForIana(iana) {
  const tail = iana.split("/").pop() || iana;
  return sanitizeClockLabel(tail.replace(/_/g, " ")) || iana;
}
function parseWorldClocksSpec(raw) {
  const out = [];
  const seen = new Set();
  for (const part of String(raw ?? "").split(";")) {
    const rec = part.trim();
    if (!rec) continue;
    const pipeIdx = rec.indexOf("|");
    if (pipeIdx < 0) continue;
    const rawLbl = rec.slice(0, pipeIdx);
    const iana = rec.slice(pipeIdx + 1).trim();
    if (!iana || PINNED_UTC_ZONES.has(iana) || !IANA_ZONE_PATTERN.test(iana)) {
      continue;
    }
    const label = sanitizeClockLabel(rawLbl) || fallbackLabelForIana(iana);
    const dedupKey = `${label.toLowerCase()}|${iana}`;
    if (seen.has(dedupKey)) continue;
    seen.add(dedupKey);
    out.push({ label, iana });
    if (out.length >= MAX_WORLD_CLOCKS) break;
  }
  return out;
}
function serializeWorldClocksSpec(items) {
  return items
    .slice(0, MAX_WORLD_CLOCKS)
    .map((item) => {
      const cleaned = sanitizeClockLabel(item.label);
      return cleaned ? `${cleaned}|${item.iana}` : "";
    })
    .filter(Boolean)
    .join(";");
}
const KNOWN_WORLD_CLOCK_ZONES = new Set(WORLD_CLOCK_ZONES_CATALOG.map((z) => z.iana));
function parseAlarmsSummary(raw) {
  const text = String(raw || DEFAULT_ALARMS_SUMMARY).trim();
  const parts = text.split(";");
  const slots = [];
  for (let i = 0; i < 3; i++) {
    const fallback = DEFAULT_ALARM_SLOTS[i];
    const seg = (parts[i] || "").trim();
    const m = /^(\d{1,2}):(\d{2})\|([01])\|([0-3])$/.exec(seg);
    if (!m) {
      slots.push({ ...fallback });
      continue;
    }
    const hh = Number(m[1]);
    const mm = Number(m[2]);
    if (hh < 0 || hh > 23 || mm < 0 || mm > 59) {
      slots.push({ ...fallback });
      continue;
    }
    slots.push({
      time: `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`,
      enabled: m[3] === "1",
      recurrence: Number(m[4]),
    });
  }
  return [slots[0], slots[1], slots[2]];
}
function serializeAlarmsSummary(slots) {
  return slots
    .slice(0, 3)
    .map((s) => `${s.time}|${s.enabled ? 1 : 0}|${s.recurrence}`)
    .join(";");
}
function renderDeviceInterfaceView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const remoteGroups = data?.system_config?.remote_groups || [];
  const homeScreenEnabledPref = store.getPref("home_screen_enabled");
  const homeScreenEnabled = homeScreenEnabledPref
    ? Boolean(homeScreenEnabledPref.value)
    : cfg.home_screen_enabled !== false;
  const startScreenPref = store.getPref("start_screen");
  const rawStartOptions =
    startScreenPref?.options && startScreenPref.options.length > 0
      ? startScreenPref.options
      : START_SCREEN_OPTIONS;
  const visibleStartOptions = (
    homeScreenEnabled ? rawStartOptions : rawStartOptions.filter((opt) => opt !== "Home")
  ).map((opt) => ({ value: opt, label: opt }));
  const rawStartValue = String(
    startScreenPref?.value ?? cfg.start_screen ?? (homeScreenEnabled ? "Home" : "Time App"),
  );
  const startScreenValue =
    !homeScreenEnabled && rawStartValue === "Home" ? "Time App" : rawStartValue;
  const homeClockTapPref = store.getPref("home_clock_tap_action");
  const homeClockTapOptions = (
    homeClockTapPref?.options && homeClockTapPref.options.length > 0
      ? homeClockTapPref.options
      : HOME_CLOCK_TAP_OPTIONS
  ).map((opt) => ({ value: opt, label: opt }));
  const homeClockTapValue = String(
    homeClockTapPref?.value ?? cfg.home_clock_tap_action ?? "Time App",
  );
  const localClockLabelPref = store.getPref("local_clock_label");
  const localClockLabelValue = sanitizeClockLabel(
    localClockLabelPref?.value ?? cfg.local_clock_label ?? "",
  );
  const showUtcClockPref = store.getPref("show_utc_clock");
  const showUtcClock = showUtcClockPref
    ? Boolean(showUtcClockPref.value)
    : Boolean(cfg.show_utc_clock);
  const worldClocksPref = store.getPref("world_clocks");
  const enabledWorldClocks = parseWorldClocksSpec(worldClocksPref?.value ?? cfg.world_clocks ?? "");
  const atWorldClockLimit = enabledWorldClocks.length >= MAX_WORLD_CLOCKS;
  const renderWorldClockZoneOptions = (selectedIana) => {
    const missingSelected =
      selectedIana && !KNOWN_WORLD_CLOCK_ZONES.has(selectedIana)
        ? html`<option value=${selectedIana} selected>${selectedIana}</option>`
        : nothing;
    return html`${missingSelected}${WORLD_CLOCK_ZONES_CATALOG.map(
      (z) => html`<option value=${z.iana} ?selected=${z.iana === selectedIana}>${z.label}</option>`,
    )}`;
  };
  const alarmsSummaryPref = store.getPref("alarms_summary");
  const alarmSlots = parseAlarmsSummary(
    alarmsSummaryPref?.value ?? cfg.alarms_summary ?? DEFAULT_ALARMS_SUMMARY,
  );
  const updateWorldClocks = (
    nextItems,
    focusId,
    debounceMs,
  ) => {
    store.stageDeviceSetting("world_clocks", serializeWorldClocksSpec(nextItems), focusId, debounceMs);
  };
  const updateWorldClockItem = (
    idx,
    patch,
    focusId,
    debounceMs,
  ) => {
    if (idx < 0 || idx >= enabledWorldClocks.length) return;
    const prev = enabledWorldClocks[idx];
    const nextIana = (patch.iana ?? prev.iana).trim();
    if (!nextIana || PINNED_UTC_ZONES.has(nextIana) || !IANA_ZONE_PATTERN.test(nextIana)) return;
    const nextLabel =
      patch.label !== undefined ? sanitizeClockLabel(patch.label) : prev.label;
    if (!nextLabel) return;
    const dup = enabledWorldClocks.some(
      (item, i) =>
        i !== idx && item.iana === nextIana && item.label.toLowerCase() === nextLabel.toLowerCase(),
    );
    if (dup) return;
    const next = enabledWorldClocks.map((item, i) =>
      i === idx ? { label: nextLabel, iana: nextIana } : { ...item },
    );
    updateWorldClocks(next, focusId, debounceMs);
  };
  const moveWorldClock = (idx, delta) => {
    const target = idx + delta;
    if (idx < 0 || target < 0 || target >= enabledWorldClocks.length) return;
    const next = [...enabledWorldClocks];
    const [picked] = next.splice(idx, 1);
    next.splice(target, 0, picked);
    updateWorldClocks(next);
  };
  const removeWorldClock = (idx) => {
    updateWorldClocks(enabledWorldClocks.filter((_, i) => i !== idx));
  };
  const getRenderRoot = () =>
    (store.host).renderRoot ?? null;
  const onAddWorldClock = () => {
    if (atWorldClockLimit) return;
    const root = getRenderRoot();
    const newLabelEl = root?.getElementById("cfg-world_clock_new_label");
    const zoneSelEl = root?.getElementById("cfg-world_clocks_add");
    const typedLabel = sanitizeClockLabel(newLabelEl?.value ?? store.worldClockNewLabel);
    const picked = (zoneSelEl?.value ?? store.worldClockNewZone).trim();
    if (!typedLabel) {
      store.showToast("Enter a city or label for this World Clock", true);
      newLabelEl?.focus();
      return;
    }
    if (!picked || PINNED_UTC_ZONES.has(picked) || !IANA_ZONE_PATTERN.test(picked)) {
      store.showToast("Select a time zone for this World Clock", true);
      zoneSelEl?.focus();
      return;
    }
    const dup = enabledWorldClocks.some(
      (item) => item.iana === picked && item.label.toLowerCase() === typedLabel.toLowerCase(),
    );
    if (dup) {
      store.showToast("That World Clock is already added", true);
      return;
    }
    store.worldClockNewLabel = "";
    store.worldClockNewZone = "";
    if (newLabelEl) newLabelEl.value = "";
    if (zoneSelEl) zoneSelEl.value = "";
    updateWorldClocks([...enabledWorldClocks, { label: typedLabel, iana: picked }], "btn-world_clock_add");
  };
  const updateAlarmSlot = (idx, patch, focusId) => {
    const next = [
      { ...alarmSlots[0] },
      { ...alarmSlots[1] },
      { ...alarmSlots[2] },
    ];
    const merged = { ...next[idx], ...patch };
    if (!/^\d{2}:\d{2}$/.test(merged.time)) {
      return;
    }
    next[idx] = merged;
    store.stageDeviceSetting("alarms_summary", serializeAlarmsSummary(next), focusId);
  };
  const returnTimeoutPref = store.getPref("return_to_home_timeout");
  const rawReturnTimeoutOptions = (
    returnTimeoutPref?.options && returnTimeoutPref.options.length > 0
      ? returnTimeoutPref.options
      : RETURN_TO_HOME_TIMEOUT_OPTIONS
  ).map((opt) => ({ value: opt, label: opt }));
  const returnTimeoutValue = String(
    returnTimeoutPref?.value ?? cfg.return_to_home_timeout ?? "2 min",
  );
  const enabledHomeCats = store.getEnabledHomeCategories();
  const disabledHomeCats = HOME_CATEGORIES_CATALOG.filter(
    (c) => !enabledHomeCats.includes(c.token),
  );
  const areaExtraItems = store.getSectionItems("area").filter((it) => it.key !== "ble_beacon_mode");
  const enabledAreaCats = store.getEnabledAreaCategories();
  const disabledAreaCats = AREA_CATEGORIES_CATALOG.filter(
    (c) => !enabledAreaCats.includes(c.token),
  );
  // Media Player shortcuts and sorting prefs
  const showSpeakerPref = store.getPref("show_speaker_shortcut");
  const showLibraryPref = store.getPref("show_library_shortcut");
  const shortcutPrefs = [
    { pref: showSpeakerPref, label: "Speaker" },
    { pref: showLibraryPref, label: "Library" },
  ].filter((c) => Boolean(c.pref));
  const sortMusicPrefs = store.getPrefs([
    "album_sort_order",
    "artist_album_sort_order",
    "podcast_sort_order",
  ]);
  const remoteEspItems = store.getSectionItems("remote");
  const activityCardOn = cfg.activity_card !== false;
  const enabledSources = new Set(store.getEnabledActivitySources());
  const dockItems = store.getDockItems();
  const pinnedItems = store.getPinnedItems();
  const shortcutEntityMap = new Map(
    (data?.catalog?.shortcut_entities || []).map((e) => [e.id, e]),
  );
  const routeSpecMap = new Map(
    SHORTCUT_ROUTES_CATALOG.map((r) => [r.token, r]),
  );
  const renderShortcutRow = (
    listKey,
    item,
    idx,
    total,
  ) => {
    let displayTitle = item.label;
    let metaLine = "";
    let iconSlug = item.icon;
    if (item.kind === "route") {
      const spec = routeSpecMap.get(item.target);
      if (!displayTitle) {
        displayTitle = spec?.label || item.target;
      }
      metaLine = spec ? `${spec.group} • ${spec.label}` : item.target;
      if (!iconSlug) {
        iconSlug = ROUTE_PREVIEW_ICONS[item.target] || "mdi:apps";
      }
    } else {
      const ent = shortcutEntityMap.get(item.target);
      const dom = item.target.split(".", 1)[0] || "";
      const actLbl = shortcutActionLabel(dom, item.action);
      if (!displayTitle) {
        displayTitle = ent?.name || item.target;
      }
      metaLine = `${actLbl} • ${item.confirm ? "Confirm" : "1-Tap"} • ${item.target}`;
      if (!iconSlug) {
        iconSlug = ent?.icon || "mdi:flash";
      }
    }
    return html`<div class="shortcut-item-row">
      <span class="shortcut-icon-badge" aria-hidden="true">
        <ha-icon .icon=${iconSlug}></ha-icon>
      </span>
      <div class="shortcut-item-info">
        <span class="shortcut-item-title">${displayTitle}</span>
        <span class="shortcut-item-meta">${metaLine}</span>
      </div>
      ${idx > 0
        ? html`<button
            type="button"
            aria-label=${`Move ${displayTitle} up`}
            @click=${() => store.moveShortcutItem(listKey, idx, -1)}
            class="btn-icon"
          >
            ↑
          </button>`
        : nothing}
      ${idx < total - 1
        ? html`<button
            type="button"
            aria-label=${`Move ${displayTitle} down`}
            @click=${() => store.moveShortcutItem(listKey, idx, 1)}
            class="btn-icon"
          >
            ↓
          </button>`
        : nothing}
      <button
        type="button"
        aria-label=${`Edit ${displayTitle}`}
        @click=${() => store.openShortcutModal(listKey, idx)}
        class="btn btn-secondary btn-compact"
      >
        Edit
      </button>
      ${renderTrashIconButton(`Remove ${displayTitle}`, () =>
        store.removeShortcutItem(listKey, idx),
      )}
    </div>`;
  };
  const pinnedPages = [];
  for (let i = 0; i < pinnedItems.length; i += 6) {
    pinnedPages.push({
      pageNum: Math.floor(i / 6) + 1,
      startIdx: i,
      items: pinnedItems.slice(i, i + 6),
    });
  }
  const curDevEntry = (data?.system_devices || []).find(
    (d) => d.subentry_id === store.activeSubentryId,
  );
  const curRemoteMode =
    String(cfg.device_remote_group || curDevEntry?.device_remote_group || "area_auto").trim() ||
    "area_auto";
  const remoteModeOptions = [
    { value: "area_auto", label: "Follow the active Area" },
    ...remoteGroups.map((g) => ({
      value: `group:${g.id}`,
      label: `Group: ${g.name}`,
    })),
    { value: "all", label: "All System remotes" },
  ];
  if (!remoteModeOptions.some((o) => o.value === curRemoteMode)) {
    const rawId = curRemoteMode.startsWith("group:") ? curRemoteMode.slice(6) : curRemoteMode;
    remoteModeOptions.push({
      value: curRemoteMode,
      label: `Missing group (${rawId})`,
    });
  }
  return html`<section id="view-interface">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Home Screen</h3>`,
          contentClass: "settings-list",
          body: html`${renderSwitchRow({
              id: "cfg-home_screen_enabled",
              label: "Enable Home Screen",
              description:
                "Provides the Home screen and App Dock. Turn off to lock this Device to a single Start Screen app.",
              checked: homeScreenEnabled,
              onChange: (checked) => {
                store.stageDeviceSetting(
                  "home_screen_enabled",
                  checked,
                  "cfg-home_screen_enabled",
                );
              },
            })}
            ${renderSelectRow({
              id: "cfg-start_screen",
              label: "Start Screen",
              description: homeScreenEnabled
                ? "Choose the screen shown on startup. Swipe up from the bottom to return to Home."
                : "Single-app screen shown at all times while the Home screen is disabled.",
              value: startScreenValue,
              rawOptions: visibleStartOptions,
              onChange: (val) => {
                store.stageDeviceSetting(
                  "start_screen",
                  val,
                  "cfg-start_screen",
                );
              },
            })}
            ${homeScreenEnabled
              ? html`${renderSelectRow({
                    id: "cfg-home_clock_tap_action",
                    label: "Home Time Tap",
                    description:
                      "Choose whether tapping the clock readout on Home opens the Time app or the standalone Clock Face.",
                    value: homeClockTapValue,
                    rawOptions: homeClockTapOptions,
                    onChange: (val) => {
                      store.stageDeviceSetting(
                        "home_clock_tap_action",
                        val,
                        "cfg-home_clock_tap_action",
                      );
                    },
                  })}
                  ${renderSelectRow({
                    id: "cfg-return_to_home_timeout",
                    label: "Return to Home Timeout",
                    description:
                      "Resets idle screens back to Home unless media is playing or a live activity is active.",
                    value: returnTimeoutValue,
                    rawOptions: rawReturnTimeoutOptions,
                    onChange: (val) => {
                      store.stageDeviceSetting(
                        "return_to_home_timeout",
                        val,
                        "cfg-return_to_home_timeout",
                      );
                    },
                  })}
                  ${renderSettingsRow({
                    id: "dock-shortcuts-row",
                    label: "App Dock",
                    description:
                      "Configure apps, subpages, and Home Assistant entity actions in the Home Dock. Pinned hides automatically when Pinned App is empty, and Settings is always shown last.",
                    stacked: true,
                    control: html`<div
                      id="dock-shortcuts-container"
                      class="stack"
                      role="group"
                      aria-label="App Dock shortcuts"
                    >
                      ${dockItems.map((item, idx) =>
                        renderShortcutRow("dock_items", item, idx, dockItems.length),
                      )}
                      <div class="shortcut-toolbar">
                        <button
                          type="button"
                          id="btn-add-dock-item"
                          ?disabled=${dockItems.length >= MAX_DOCK_ITEMS}
                          @click=${() => store.openShortcutModal("dock_items", null)}
                          class="btn btn-secondary"
                        >
                          Add Dock Item
                        </button>
                        <button
                          type="button"
                          id="btn-reset-dock-items"
                          @click=${() => store.resetDockItemsToDefault()}
                          class="btn btn-text"
                        >
                          Reset Default Dock
                        </button>
                      </div>
                    </div>`,
                  })}
                  ${renderSettingsRow({
                    labelHtml: html`<label for="cfg-activity_card" class="row-label">Show the Activity Card</label>`,
                    description:
                      "Shows live timers, alarms, media queue, stopwatch, and next calendar event on Home.",
                    control: html`<input
                      type="checkbox"
                      id="cfg-activity_card"
                      role="switch"
                      .checked=${activityCardOn}
                      @change=${(ev) =>
                        store.stageDeviceSetting(
                          "activity_card",
                          (ev.currentTarget).checked,
                          "cfg-activity_card",
                        )}
                      class="switch"
                    />`,
                  })}
                  ${activityCardOn
                    ? renderSettingsRow({
                        id: "activity-sources",
                        label: "Activity Card Sources",
                        description: "Choose which live items appear in the Activity Card.",
                        stacked: true,
                        control: html`<div
                          class="pill-list"
                          role="group"
                          aria-label="Activity Card sources"
                        >
                          ${ACTIVITY_SOURCES_CATALOG.map((src) => {
                            const on = enabledSources.has(src.token);
                            return html`<span
                              data-src=${src.token}
                              data-label=${src.label}
                              class="pill ${on ? "enabled" : ""}"
                            >
                              <button
                                type="button"
                                aria-pressed=${String(on)}
                                @click=${() => store.toggleActivitySource(src.token)}
                                class="pill-toggle"
                              >
                                ${on ? `✓ ${src.label}` : `+ ${src.label}`}
                              </button>
                            </span>`;
                          })}
                        </div>`,
                      })
                    : nothing}`
              : nothing}`,
        })}

        ${renderCard({
          heading: html`<h3 class="card-title">Home Controls</h3>`,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
            label: "Home Categories",
            description:
              "Toggle and reorder categories shown in the Home Hub. The first available category opens by default; categories with no configured entity are not displayed.",
            stacked: true,
            control: html`<div
              id="home-categories-pills"
              class="pill-list"
              role="group"
              aria-label="Home categories"
            >
              ${enabledHomeCats.map((tok, idx) => {
                const meta = HOME_CATEGORIES_CATALOG.find((c) => c.token === tok);
                const lbl = meta ? meta.label : tok;
                return html`<span class="pill enabled">
                  ${idx > 0
                    ? html`<button
                        type="button"
                        aria-label=${`Move ${lbl} left`}
                        @click=${() => store.moveHomeCategoryToken(tok, -1)}
                        class="pill-move"
                      >
                        ‹
                      </button>`
                    : nothing}
                  <button
                    type="button"
                    aria-pressed="true"
                    @click=${() => store.toggleHomeCategoryToken(tok)}
                    class="pill-toggle"
                  >
                    ✓ ${lbl}
                  </button>
                  ${idx < enabledHomeCats.length - 1
                    ? html`<button
                        type="button"
                        aria-label=${`Move ${lbl} right`}
                        @click=${() => store.moveHomeCategoryToken(tok, 1)}
                        class="pill-move"
                      >
                        ›
                      </button>`
                    : nothing}
                </span>`;
              })}
              ${disabledHomeCats.map(
                (cat) => html`<span class="pill">
                  <button
                    type="button"
                    aria-pressed="false"
                    @click=${() => store.toggleHomeCategoryToken(cat.token)}
                    class="pill-toggle"
                  >
                    + ${cat.label}
                  </button>
                </span>`,
              )}
            </div>`,
          })}`,
        })}

        ${renderCard({
          id: "card-time",
          heading: html`<h3 class="card-title">Time</h3>`,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              id: "time-local-clock-label",
              label: "Local Clock Label",
              forId: "cfg-local_clock_label",
              description: "Optional custom label shown above local time on the Clock tab.",
              control: html`<input
                type="text"
                id="cfg-local_clock_label"
                maxlength="32"
                enterkeyhint="done"
                placeholder="Optional label…"
                .value=${localClockLabelValue}
                @input=${(ev) => {
                  const cleaned = sanitizeClockLabel((ev.currentTarget).value);
                  store.stageDeviceSetting(
                    "local_clock_label",
                    cleaned,
                    "cfg-local_clock_label",
                    TEXT_INPUT_DEBOUNCE_MS,
                  );
                }}
                @change=${(ev) => {
                  const el = ev.currentTarget;
                  const cleaned = sanitizeClockLabel(el.value);
                  el.value = cleaned;
                  store.stageDeviceSetting("local_clock_label", cleaned, "cfg-local_clock_label");
                }}
                @keydown=${(ev) => {
                  if (!isImeSafeEnter(ev)) return;
                  ev.preventDefault();
                  const el = ev.currentTarget;
                  const cleaned = sanitizeClockLabel(el.value);
                  el.value = cleaned;
                  store.stageDeviceSetting("local_clock_label", cleaned, "cfg-local_clock_label");
                  void store.flushAllPendingSettings();
                }}
              />`,
            })}
            ${renderSwitchRow({
              id: "cfg-show_utc_clock",
              label: "Show UTC Clock",
              description: "Pin a live 24-hour UTC reference row to this Device's Clock tab.",
              checked: showUtcClock,
              onChange: (checked) => {
                store.stageDeviceSetting("show_utc_clock", checked, "cfg-show_utc_clock");
              },
            })}
            ${renderSettingsRow({
              id: "time-world-clocks",
              label: "World Clocks",
              description:
                "Configure up to 4 custom-labeled time zones (UTC-12:00 to UTC+14:00) shown on this Device's Clock tab.",
              stacked: true,
              control: html`<div class="stack">
                ${enabledWorldClocks.length
                  ? html`<div
                      id="world-clocks-list"
                      class="stack"
                      role="group"
                      aria-label="Configured World Clocks"
                    >
                      ${enabledWorldClocks.map((entry, idx) => {
                        const lblId = `cfg-world_clock_${idx + 1}_label`;
                        const zoneId = `cfg-world_clock_${idx + 1}_zone`;
                        return html`<div class="list-row">
                          <div class="list-row-main">
                            <div class="stacked-field">
                              <label for=${lblId}>World Clock ${idx + 1} City Label</label>
                              <input
                                type="text"
                                id=${lblId}
                                maxlength="32"
                                enterkeyhint="done"
                                placeholder="Enter city or label…"
                                .value=${entry.label}
                                @input=${(ev) => {
                                  const cleaned = sanitizeClockLabel(
                                    (ev.currentTarget).value,
                                  );
                                  if (cleaned) {
                                    updateWorldClockItem(
                                      idx,
                                      { label: cleaned },
                                      lblId,
                                      TEXT_INPUT_DEBOUNCE_MS,
                                    );
                                  }
                                }}
                                @change=${(ev) => {
                                  const el = ev.currentTarget;
                                  const cleaned = sanitizeClockLabel(el.value);
                                  if (!cleaned) {
                                    el.value = entry.label;
                                    store.showToast("City label cannot be empty", true);
                                    return;
                                  }
                                  el.value = cleaned;
                                  updateWorldClockItem(idx, { label: cleaned }, lblId);
                                }}
                                @keydown=${(ev) => {
                                  if (!isImeSafeEnter(ev)) return;
                                  ev.preventDefault();
                                  const el = ev.currentTarget;
                                  const cleaned = sanitizeClockLabel(el.value);
                                  if (!cleaned) {
                                    el.value = entry.label;
                                    store.showToast("City label cannot be empty", true);
                                    return;
                                  }
                                  el.value = cleaned;
                                  updateWorldClockItem(idx, { label: cleaned }, lblId);
                                  void store.flushAllPendingSettings();
                                }}
                              />
                            </div>
                            <div class="stacked-field">
                              <label for=${zoneId}>World Clock ${idx + 1} Time Zone</label>
                              <select
                                id=${zoneId}
                                .value=${entry.iana}
                                @change=${(ev) =>
                                  updateWorldClockItem(
                                    idx,
                                    { iana: (ev.currentTarget).value },
                                    zoneId,
                                  )}
                              >
                                ${renderWorldClockZoneOptions(entry.iana)}
                              </select>
                            </div>
                          </div>
                          ${idx > 0
                            ? html`<button
                                type="button"
                                aria-label=${`Move ${entry.label} up`}
                                @click=${() => moveWorldClock(idx, -1)}
                                class="btn-icon"
                              >
                                ↑
                              </button>`
                            : nothing}
                          ${idx < enabledWorldClocks.length - 1
                            ? html`<button
                                type="button"
                                aria-label=${`Move ${entry.label} down`}
                                @click=${() => moveWorldClock(idx, 1)}
                                class="btn-icon"
                              >
                                ↓
                              </button>`
                            : nothing}
                          ${renderTrashIconButton(
                            `Remove ${entry.label} (${entry.iana})`,
                            () => removeWorldClock(idx),
                          )}
                        </div>`;
                      })}
                    </div>`
                  : nothing}
                <div class="list-row">
                  <div class="list-row-main">
                    <div class="stacked-field">
                      <label for="cfg-world_clock_new_label">New City Label</label>
                      <input
                        type="text"
                        id="cfg-world_clock_new_label"
                        maxlength="32"
                        enterkeyhint="done"
                        placeholder="Enter city or label…"
                        ?disabled=${atWorldClockLimit}
                        .value=${store.worldClockNewLabel}
                        @input=${(ev) => {
                          store.worldClockNewLabel = (ev.currentTarget).value;
                          store.host.requestUpdate();
                        }}
                        @keydown=${(ev) => {
                          if (!isImeSafeEnter(ev)) return;
                          ev.preventDefault();
                          onAddWorldClock();
                        }}
                      />
                    </div>
                    <div class="stacked-field">
                      <label for="cfg-world_clocks_add">Add Time Zone</label>
                      <select
                        id="cfg-world_clocks_add"
                        ?disabled=${atWorldClockLimit}
                        .value=${store.worldClockNewZone}
                        @change=${(ev) => {
                          store.worldClockNewZone = (ev.currentTarget).value;
                          store.host.requestUpdate();
                        }}
                      >
                        <option value="" ?selected=${!store.worldClockNewZone}>
                          ${atWorldClockLimit
                            ? "Maximum 4 World Clocks added"
                            : "Select a time zone (UTC-12 to UTC+14)…"}
                        </option>
                        ${atWorldClockLimit
                          ? nothing
                          : renderWorldClockZoneOptions(store.worldClockNewZone)}
                      </select>
                    </div>
                  </div>
                  <button
                    type="button"
                    id="btn-world_clock_add"
                    ?disabled=${atWorldClockLimit}
                    @click=${() => onAddWorldClock()}
                    class="btn btn-primary"
                  >
                    Add
                  </button>
                </div>
              </div>`,
            })}
            ${renderSettingsRow({
              id: "time-alarms",
              label: "Alarms",
              description: "Syncs 2-way with on-device alarm edits (1-minute precision).",
              stacked: true,
              control: html`<div class="stack" role="group" aria-label="Device alarms">
                ${([0, 1, 2]).map((idx) => {
                  const slot = alarmSlots[idx];
                  const timeId = `cfg-alarm_${idx + 1}_time`;
                  const recId = `cfg-alarm_${idx + 1}_recurrence`;
                  const enId = `cfg-alarm_${idx + 1}_enabled`;
                  return html`<div class="list-row">
                    <div class="list-row-main">
                      <div class="stacked-field">
                        <label for=${timeId}>Alarm ${idx + 1} time</label>
                        <input
                          type="time"
                          id=${timeId}
                          step="60"
                          .value=${slot.time}
                          @change=${(ev) => {
                            const val = (ev.currentTarget).value;
                            if (val) updateAlarmSlot(idx, { time: val.slice(0, 5) }, timeId);
                          }}
                        />
                      </div>
                      <div class="stacked-field">
                        <label for=${recId}>Alarm ${idx + 1} schedule</label>
                        <select
                          id=${recId}
                          .value=${String(slot.recurrence)}
                          @change=${(ev) =>
                            updateAlarmSlot(
                              idx,
                              { recurrence: Number((ev.currentTarget).value) },
                              recId,
                            )}
                        >
                          ${ALARM_RECURRENCE_OPTIONS.map(
                            (opt) =>
                              html`<option
                                value=${String(opt.value)}
                                ?selected=${opt.value === slot.recurrence}
                              >
                                ${opt.label}
                              </option>`,
                          )}
                        </select>
                      </div>
                    </div>
                    <label for=${enId} class="inline-switch">
                      <span>Enabled</span>
                      <input
                        type="checkbox"
                        id=${enId}
                        .checked=${slot.enabled}
                        @change=${(ev) =>
                          updateAlarmSlot(
                            idx,
                            { enabled: (ev.currentTarget).checked },
                            enId,
                          )}
                        role="switch"
                        class="switch"
                      />
                    </label>
                  </div>`;
                })}
              </div>`,
            })}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-pinned-app",
          heading: html`<h3 class="card-title">Pinned App</h3>`,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
            id: "pinned-shortcuts-row",
            label: "Pinned Shortcuts",
            description:
              "Assign Home Assistant entity quick actions or deep-link any Latter app or subpage (6 buttons per page, swipable vertically).",
            stacked: true,
            control: html`<div
              id="pinned-shortcuts-container"
              class="stack"
              role="group"
              aria-label="Pinned App shortcuts"
            >
              ${pinnedPages.length > 0
                ? pinnedPages.map(
                    (pg) => html`<div class="shortcut-page-group">
                      <div class="shortcut-page-header">
                        <span>Page ${pg.pageNum}</span>
                        <span>${pg.items.length} of 6 Slots</span>
                      </div>
                      ${pg.items.map((item, localIdx) =>
                        renderShortcutRow(
                          "pinned_items",
                          item,
                          pg.startIdx + localIdx,
                          pinnedItems.length,
                        ),
                      )}
                    </div>`,
                  )
                : html`<p class="row-description">
                    No pinned items configured yet. The Pinned icon stays hidden on the Home Dock until you add at least one item.
                  </p>`}
              <div class="shortcut-toolbar">
                <button
                  type="button"
                  id="btn-add-pinned-item"
                  ?disabled=${pinnedItems.length >= MAX_PINNED_ITEMS}
                  @click=${() => store.openShortcutModal("pinned_items", null)}
                  class="btn btn-primary"
                >
                  Add Pinned Item
                </button>
              </div>
            </div>`,
          })}`,
        })}

        ${renderCard({
          heading: html`<h3 class="card-title">Area Controls</h3>`,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: "Area Categories",
              description:
                "Toggle and reorder categories shown in the Area screen. The first available category opens by default; categories with no entities in the active Area are not displayed.",
              stacked: true,
              control: html`<div
                id="area-categories-pills"
                class="pill-list"
                role="group"
                aria-label="Area categories"
              >
                ${enabledAreaCats.map((tok, idx) => {
                  const meta = AREA_CATEGORIES_CATALOG.find((c) => c.token === tok);
                  const lbl = meta ? meta.label : tok;
                  return html`<span class="pill enabled">
                    ${idx > 0
                      ? html`<button
                          type="button"
                          aria-label=${`Move ${lbl} left`}
                          @click=${() => store.moveAreaCategoryToken(tok, -1)}
                          class="pill-move"
                        >
                          ‹
                        </button>`
                      : nothing}
                    <button
                      type="button"
                      aria-pressed="true"
                      @click=${() => store.toggleAreaCategoryToken(tok)}
                      class="pill-toggle"
                    >
                      ✓ ${lbl}
                    </button>
                    ${idx < enabledAreaCats.length - 1
                      ? html`<button
                          type="button"
                          aria-label=${`Move ${lbl} right`}
                          @click=${() => store.moveAreaCategoryToken(tok, 1)}
                          class="pill-move"
                        >
                          ›
                        </button>`
                      : nothing}
                  </span>`;
                })}
                ${disabledAreaCats.map(
                  (cat) => html`<span class="pill">
                    <button
                      type="button"
                      aria-pressed="false"
                      @click=${() => store.toggleAreaCategoryToken(cat.token)}
                      class="pill-toggle"
                    >
                      + ${cat.label}
                    </button>
                  </span>`,
                )}
              </div>`,
            })}
            ${areaExtraItems.map((it) => renderNativeControlRow(store, it))}`,
        })}

        ${shortcutPrefs.length || sortMusicPrefs.length
          ? renderCard({
              heading: html`<h3 class="card-title">Media Player</h3>`,
              contentClass: "settings-list",
              body: html`${shortcutPrefs.length
                  ? renderSettingsRow({
                      id: "media-player-shortcuts",
                      label: "Shortcuts",
                      description:
                        "Choose which quick-access buttons appear on the Music player screen.",
                      control: html`<div
                        class="pill-list"
                        role="group"
                        aria-label="Media Player shortcuts"
                      >
                        ${shortcutPrefs.map(({ pref, label }) => {
                          const isOn = Boolean(pref.value);
                          return html`<span class="pill ${isOn ? "enabled" : ""}">
                            <button
                              type="button"
                              aria-pressed=${String(isOn)}
                              @click=${() => store.stageDeviceSetting(pref.key, !isOn)}
                              class="pill-toggle"
                            >
                              ${isOn ? `✓ ${label}` : `+ ${label}`}
                            </button>
                          </span>`;
                        })}
                      </div>`,
                    })
                  : nothing}
                ${sortMusicPrefs.map((p) => renderPrefControlRow(store, p))}`,
            })
          : nothing}

        ${renderCard({
          heading: html`<h3 class="card-title">Remote Controls</h3>`,
          contentClass: "settings-list",
          body: html`${renderSelectRow({
              id: "cfg-device_remote_group",
              label: "Remote Control Group",
              description: "Choose which remotes appear on this Device's Remote screen.",
              value: curRemoteMode,
              rawOptions: remoteModeOptions,
              onChange: (val) =>
                store.stageDeviceSetting(
                  "device_remote_group",
                  val,
                  "cfg-device_remote_group",
                ),
            })}
            ${remoteEspItems.map((it) => renderNativeControlRow(store, it))}`,
          footerActions: html`<button
            type="button"
            @click=${() => store.openSystemSection("remotes")}
            class="btn btn-text"
          >
            Manage Remote Groups
          </button>`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/device-overview-view.ts ---
/**
 * Device Overview View (`dashboard`, D-029 / D-048 / D-049):
 * - Column 1: High-level Status card (header state pill, 2x2 tonal metric tiles, footer links)
 *   followed by Quick Actions (immediate action tiles + live volume).
 * - Column 2: Unified Assignments card (Device Group with Custom / Save Custom Group / Manage Groups,
 *   Assigned Person, Remote Control Group) followed by spillover Sensors & Controls.
 */
const ICON_AREA = "M12,6.5A2.5,2.5 0 0,1 14.5,9A2.5,2.5 0 0,1 12,11.5A2.5,2.5 0 0,1 9.5,9A2.5,2.5 0 0,1 12,6.5M12,2A7,7 0 0,1 19,9C19,14.25 12,22 12,22C12,22 5,14.25 5,9A7,7 0 0,1 12,2M12,4A5,5 0 0,0 7,9C7,10 7,12 12,18.71C17,12 17,10 17,9A5,5 0 0,0 12,4Z";
const ICON_BATTERY = "M16,20H8V6H16M16.67,4H15V2H9V4H7.33A1.33,1.33 0 0,0 6,5.33V20.67C6,21.4 6.6,22 7.33,22H16.67A1.33,1.33 0 0,0 18,20.67V5.33C18,4.6 17.4,4 16.67,4Z";
const ICON_PLUG = "M16,7V3H14V7H10V3H8V7H8C7,7 6,8 6,9V14.5L9.5,18V21H14.5V18L18,14.5V9C18,8 17,7 16,7M16,13.67L12.5,17.17V19H11.5V17.17L8,13.67V9H16V13.67Z";
const ICON_RADAR = "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12C22,10.84 21.79,9.69 21.39,8.61L19.79,10.21C19.93,10.8 20,11.4 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4C12.6,4 13.2,4.07 13.79,4.21L15.4,2.6C14.31,2.21 13.16,2 12,2M19,2A2,2 0 0,0 17,4A2,2 0 0,0 19,6A2,2 0 0,0 21,4A2,2 0 0,0 19,2M12,6A6,6 0 0,0 6,12A6,6 0 0,0 12,18A6,6 0 0,0 18,12H16A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8V6M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10Z";
const ICON_WIFI = "M12,21L15.6,16.2C14.6,15.45 13.35,15 12,15C10.65,15 9.4,15.45 8.4,16.2L12,21M12,3C7.95,3 4.21,4.34 1.2,6.6L3,9C5.5,7.12 8.62,6 12,6C15.38,6 18.5,7.12 21,9L22.8,6.6C19.79,4.34 16.05,3 12,3M12,9C9.3,9 6.81,9.89 4.8,11.4L6.6,13.8C8.1,12.67 9.97,12 12,12C14.03,12 15.9,12.67 17.4,13.8L19.2,11.4C17.19,9.89 14.7,9 12,9Z";
const ICON_BLUETOOTH = "M14.88,16.29L13,18.17V14.41M13,5.83L14.88,7.71L13,9.58M17.71,7.71L12,2H11V9.58L6.41,5L5,6.41L10.59,12L5,17.58L6.41,19L11,14.41V22H12L17.71,16.29L13.41,12L17.71,7.71Z";
const ICON_CHIP = "M17,17H7V7H17M21,11V9H19V7C19,5.89 18.1,5 17,5H15V3H13V5H11V3H9V5H7C5.89,5 5,5.89 5,7V9H3V11H5V13H3V15H5V17A2,2 0 0,0 7,19H9V21H11V19H13V21H15V19H17A2,2 0 0,0 19,17V15H21V13H19V11M15,15H9V9H15V15Z";
const ICON_TAG = "M21.41,11.58L12.41,2.58C12.05,2.22 11.55,2 11,2H4C2.9,2 2,2.9 2,4V11C2,11.55 2.22,12.05 2.59,12.42L11.59,21.42C11.95,21.78 12.45,22 13,22C13.55,22 14.05,21.78 14.41,21.41L21.41,14.41C21.78,14.05 22,13.55 22,13C22,12.45 21.77,11.94 21.41,11.58M13,20.01L4,11V4H11V3.99L20,12.99L13,20.01M6.5,5A1.5,1.5 0 0,1 8,6.5A1.5,1.5 0 0,1 6.5,8A1.5,1.5 0 0,1 5,6.5A1.5,1.5 0 0,1 6.5,5Z";
function renderTileIcon(pathD) {
  return html`<svg viewBox="0 0 24 24" aria-hidden="true"><path d=${pathD}></path></svg>`;
}
function rssiQualityLabel(rssi) {
  if (rssi === null || !Number.isFinite(rssi)) return "No reading";
  if (rssi >= -60) return "Excellent";
  if (rssi >= -70) return "Good";
  if (rssi >= -80) return "Fair";
  return "Weak";
}
function renderDeviceOverviewView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const live = data?.live || {};
  const caps = data?.capabilities || {};
  const links = data?.links || {};
  const esp = data?.esphome;
  const isBleOnly = cfg.kind === "ble_tag";
  const curDevEntry =
    (data?.system_devices || []).find((d) => d.subentry_id === store.activeSubentryId) ||
    (data?.system_devices || []).find((d) => d.is_current);
  const deviceIssues = (data?.issues || []).filter(
    (i) => i.subentry_id && i.subentry_id === store.activeSubentryId,
  );
  const hasErrorIssue = deviceIssues.some(
    (i) => i.severity === "error" || i.severity === "critical",
  );
  // Live Status calculations
  const winRow = (curDevEntry?.ble_survey_rows || []).find((r) => r.is_winner);
  const hasBatteryReading =
    !isBleOnly &&
    curDevEntry?.battery_level !== null &&
    curDevEntry?.battery_level !== undefined &&
    Number.isFinite(Number(curDevEntry.battery_level));
  const batPct = hasBatteryReading
    ? Math.max(0, Math.min(100, Math.round(Number(curDevEntry?.battery_level))))
    : 0;
  const batMeta = curDevEntry?.is_charging
    ? "Charging"
    : curDevEntry?.is_usb_connected
      ? "Plugged in"
      : "On battery";
  let rssiVal = null;
  if (!isBleOnly && curDevEntry?.wifi_rssi !== null && curDevEntry?.wifi_rssi !== undefined) {
    rssiVal = Number(curDevEntry.wifi_rssi);
  } else if (isBleOnly && winRow && winRow.effective_rssi !== null && winRow.effective_rssi !== undefined) {
    rssiVal = Number(winRow.effective_rssi);
  }
  const hasRssi = rssiVal !== null && Number.isFinite(rssiVal);
  const rssiText = hasRssi ? `${fmtNumber(rssiVal, store.hass, 0)} dBm` : "—";
  const rssiPct = hasRssi ? rssiToPercent(rssiVal) : 0;
  const hasAssignedArea = Boolean(curDevEntry?.has_assigned_area);
  const areaText = hasAssignedArea
    ? curDevEntry?.area_label || live.active_area_name || "—"
    : live.active_area_name || "—";
  const distSuffix =
    live.ble_closest_proxy && winRow && winRow.distance_m !== null && winRow.distance_m !== undefined
      ? ` (~${fmtDistance(winRow.distance_m, store.hass, winRow.distance_ft)})`
      : "";
  const showProxyMeta = Boolean(!isBleOnly && caps.has_ble_beacon && cfg.native_ble_tracking && live.ble_closest_proxy);
  const areaMetaBase = isBleOnly ? "BLE tag" : hasAssignedArea ? "Stationary" : "Roaming";
  const areaMeta = showProxyMeta
    ? `${areaMetaBase} • ${live.ble_closest_proxy}${distSuffix}`
    : areaMetaBase;
  const rawSw = String(live.device_sw_version || esp?.device?.sw_version || "").replace(/^v/i, "");
  const fwValue = rawSw ? `v${rawSw}` : "—";
  const fwMeta = live.fw_update_available
    ? "Update available"
    : rawSw
      ? "Up to date"
      : "Not reported";
  let statusChipClass = "chip";
  let statusDotClass = "status-dot";
  let statusLabel = "—";
  if (isBleOnly) {
    statusLabel = curDevEntry?.status_label || "—";
    const detected = statusLabel.toLowerCase().includes("detected") || Boolean(winRow);
    if (detected) {
      statusChipClass = "chip chip-success";
      statusDotClass = "status-dot online";
    }
  } else if (curDevEntry?.is_online && live.fw_update_available) {
    statusChipClass = "chip chip-warning";
    statusDotClass = "status-dot update";
    statusLabel = "Update available";
  } else if (curDevEntry?.is_online) {
    statusChipClass = "chip chip-success";
    statusDotClass = "status-dot online";
    statusLabel = "Online";
  } else if (curDevEntry?.is_online === false) {
    statusLabel = "Offline";
  }
  const sectionActionItems = store
    .getSectionItems("actions")
    .concat(store.getSectionItems("overview"));
  const sectionButtons = sectionActionItems.filter((it) => it.domain === "button");
  const synthesizedButtons = (data?.quick_actions || []).map((qa) => ({
    entity_id: `cmd:${qa.key}`,
    domain: "button",
    name: qa.label,
    state: qa.state,
    device_command: qa.device_command,
    device_class: qa.device_class,
  }));
  const hasRestartInSection = sectionButtons.some(
    (b) => b.device_class === "restart" || (b.name || "").toLowerCase().includes("restart"),
  );
  const quickActionButtons = sectionButtons.concat(
    synthesizedButtons.filter((sb) => !(hasRestartInSection && sb.device_command === "restart")),
  );
  const otherQuickItems = sectionActionItems.filter((it) => it.domain !== "button");
  if (
    data?.speaker_volume &&
    !otherQuickItems.some((it) => it.entity_id === data.speaker_volume?.entity_id)
  ) {
    otherQuickItems.push(data.speaker_volume);
  }
  const showQuickActionsCard =
    !isBleOnly && (quickActionButtons.length > 0 || otherQuickItems.length > 0);
  const otherSensorItems = store.getSectionItems("other");
  const groups = data?.device_groups || [];
  const rawGroupId = String(cfg.device_group || "custom").trim() || "custom";
  const curGroupId =
    rawGroupId === "custom" || groups.some((g) => g.id === rawGroupId)
      ? rawGroupId
      : "custom";
  const remoteGroups = data?.system_config?.remote_groups || [];
  const curRemoteMode =
    String(cfg.device_remote_group || curDevEntry?.device_remote_group || "area_auto").trim() ||
    "area_auto";
  let remoteSummary = "Follow Area";
  if (curRemoteMode === "all") {
    remoteSummary = "All System Remotes";
  } else if (curRemoteMode.startsWith("group:")) {
    const gid = curRemoteMode.slice(6);
    remoteSummary = remoteGroups.find((g) => g.id === gid)?.name || gid;
  }
  const powerTileBody = hasBatteryReading
    ? html`<div class="status-tile-head">
          ${renderTileIcon(ICON_BATTERY)}
          <span>Battery</span>
        </div>
        <strong class="status-tile-value">${fmtPercent(curDevEntry?.battery_level, store.hass)}</strong>
        <span class="status-tile-meta">${batMeta}</span>
        <div class="signal-track" aria-hidden="true">
          <div
            class="signal-fill${batPct <= 20 && !curDevEntry?.is_charging ? " low" : ""}"
            style=${`--signal-pct:${batPct}%`}
          ></div>
        </div>`
    : html`<div class="status-tile-head">
          ${renderTileIcon(ICON_PLUG)}
          <span>Power</span>
        </div>
        <strong class="status-tile-value">Plugged in</strong>
        <span class="status-tile-meta">${caps.has_power ? "Sleep & wake active" : "Always on"}</span>`;
  return html`<section id="view-dashboard" class="stack">
    ${deviceIssues.length
      ? html`<div role="alert" class="alert ${hasErrorIssue ? "alert-error" : "alert-warning"}">
          <div class="alert-body">
            <strong>Needs Attention</strong>
            <ul class="alert-list">
              ${deviceIssues.map((iss) => html`<li>${issueMessage(iss)}</li>`)}
            </ul>
          </div>
          <button
            type="button"
            @click=${() => store.openHaPage("/config/repairs")}
            class="btn btn-secondary btn-compact"
          >
            Open Repairs
          </button>
        </div>`
      : nothing}

    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Status</h3>`,
          headerActions: html`<span id="st-status-chip" class=${statusChipClass}>
            <span class=${statusDotClass} aria-hidden="true"></span>${statusLabel}
          </span>`,
          contentClass: "stack",
          body: html`<div class="status-tiles">
            <button
              type="button"
              @click=${() => store.switchView("presence")}
              class="status-tile"
            >
              <div class="status-tile-head">
                ${renderTileIcon(ICON_AREA)}
                <span id="st-area-label">${hasAssignedArea ? "Area" : "Current Area"}</span>
              </div>
              <strong class="status-tile-value">${areaText}</strong>
              <span class="status-tile-meta">${areaMeta}</span>
            </button>

            ${isBleOnly
              ? html`<button
                  type="button"
                  @click=${() => store.switchView("presence")}
                  class="status-tile"
                >
                  <div class="status-tile-head">
                    ${renderTileIcon(ICON_RADAR)}
                    <span>Closest Proxy</span>
                  </div>
                  <strong class="status-tile-value">${live.ble_closest_proxy || "—"}</strong>
                  <span class="status-tile-meta">
                    ${winRow && winRow.distance_m !== null && winRow.distance_m !== undefined
                      ? `~${fmtDistance(winRow.distance_m, store.hass, winRow.distance_ft)}`
                      : "BLE presence"}
                  </span>
                </button>`
              : hasBatteryReading || caps.has_power
                ? html`<button
                    type="button"
                    @click=${() => store.switchView("power")}
                    class="status-tile"
                  >
                    ${powerTileBody}
                  </button>`
                : html`<div class="status-tile">${powerTileBody}</div>`}

            <button
              type="button"
              @click=${() => store.switchView(isBleOnly ? "presence" : "tools")}
              class="status-tile"
            >
              <div class="status-tile-head">
                ${renderTileIcon(isBleOnly ? ICON_BLUETOOTH : ICON_WIFI)}
                <span id="st-wifi-label">${isBleOnly ? "BLE Signal" : "Wi-Fi Signal"}</span>
              </div>
              <strong class="status-tile-value">${rssiText}</strong>
              <span class="status-tile-meta">${rssiQualityLabel(rssiVal)}</span>
              ${hasRssi
                ? html`<div class="signal-track" aria-hidden="true">
                    <div
                      class="signal-fill${rssiVal !== null && rssiVal < -80 ? " low" : ""}"
                      style=${`--signal-pct:${rssiPct}%`}
                    ></div>
                  </div>`
                : nothing}
            </button>

            ${isBleOnly
              ? html`<button
                  type="button"
                  @click=${() => store.switchView("presence")}
                  class="status-tile"
                >
                  <div class="status-tile-head">
                    ${renderTileIcon(ICON_TAG)}
                    <span>BLE Target</span>
                  </div>
                  <strong class="status-tile-value">
                    <code>${cfg.ble_target_address || "—"}</code>
                  </strong>
                  <span class="status-tile-meta">Bluetooth address</span>
                </button>`
              : html`<button
                  type="button"
                  @click=${() => store.switchView("tools")}
                  class="status-tile"
                >
                  <div class="status-tile-head">
                    ${renderTileIcon(ICON_CHIP)}
                    <span>Firmware</span>
                  </div>
                  <strong class="status-tile-value">${fwValue}</strong>
                  <span class="status-tile-meta">${fwMeta}</span>
                </button>`}
          </div>`,
          footerActions: html`${links.esphome_device_id
              ? html`<button
                  type="button"
                  id="btn-open-in-ha"
                  @click=${() => store.openDeviceInHa()}
                  class="btn btn-text"
                >
                  Open in ESPHome
                </button>`
              : nothing}
            <button
              type="button"
              @click=${() => void store.exportBackup(store.activeSubentryId)}
              class="btn btn-text"
            >
              Download Backup
            </button>`,
        })}

        ${showQuickActionsCard
          ? renderCard({
              title: "Quick Actions",
              contentClass: "settings-list",
              body: html`${renderQuickActionGrid(store, quickActionButtons)}
                ${otherQuickItems.map((it) => renderNativeControlRow(store, it))}`,
            })
          : nothing}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-device-assignments",
          title: "Assignments",
          contentClass: "settings-list",
          body: html`${!isBleOnly
              ? renderSettingsRow({
                  label: "Device Group",
                  forId: "cfg-device_group",
                  description:
                    curGroupId === "custom"
                      ? "Uses individual operational settings; save as a reusable group or pick an existing preset."
                      : "Applies shared operational settings (power, wake word, brightness, BLE).",
                  control: html`<select
                      id="cfg-device_group"
                      .value=${curGroupId}
                      @change=${(ev) =>
                        store.stageDeviceSetting(
                          "device_group",
                          (ev.currentTarget).value,
                          "cfg-device_group",
                        )}
                    >
                      <option value="custom" ?selected=${curGroupId === "custom"}>
                        Custom
                      </option>
                      ${groups.map(
                        (g) =>
                          html`<option value=${g.id} ?selected=${g.id === curGroupId}>
                            ${g.name}
                          </option>`,
                      )}
                    </select>
                    ${curGroupId === "custom"
                      ? html`<button
                          type="button"
                          id="btn-save-custom-group"
                          @click=${() => store.openSaveGroupModal()}
                          class="btn btn-secondary btn-compact"
                        >
                          Save Custom Group
                        </button>`
                      : nothing}
                    <button
                      type="button"
                      id="btn-manage-groups"
                      @click=${() => store.openManageGroups(curGroupId)}
                      class="btn btn-text btn-compact"
                    >
                      Manage Groups
                    </button>`,
                })
              : nothing}
            ${renderSelectRow({
              id: "cfg-assigned_person",
              label: "Assigned Person",
              description: "Links this Device's Area presence to a Home Assistant person entity.",
              value: cfg.assigned_person,
              choices: data?.catalog?.persons,
              emptyOptionLabel: "— Unassigned —",
              onChange: (val) =>
                store.stageDeviceSetting("assigned_person", val, "cfg-assigned_person"),
            })}
            ${!isBleOnly && caps.has_display
              ? renderSettingsRow({
                  label: "Remote Control Group",
                  description: "Controls which TV and AV remotes appear in the Remote app.",
                  control: html`<span class="chip">${remoteSummary}</span>
                    <button
                      type="button"
                      @click=${() => store.switchView("interface")}
                      class="btn btn-text btn-compact"
                    >
                      Configure
                    </button>`,
                })
              : nothing}`,
        })}

        ${otherSensorItems.length
          ? renderCard({
              title: "Sensors & Controls",
              contentClass: "settings-list",
              body: otherSensorItems.map((it) => renderNativeControlRow(store, it)),
            })
          : nothing}
      </div>
    </div>
  </section>`;
}

// --- src/views/device-power-view.ts ---
/**
 * Device Power View (`power`, D-014 / D-027 / D-036): Sleep & Wake controls and Power & Battery telemetry.
 */
const SCREENSAVER_KEYS = new Set([
  "docked_screensaver",
  "screensaver_style",
  "docked_idle_timeout",
]);
function renderDevicePowerView(store) {
  const sleepPrefs = store
    .getPrefs([
      "tap_to_wake",
      "pickup_to_wake",
      "battery_screen_timeout",
      "battery_hibernate_timeout",
      "hold_crown_power_off",
    ])
    .filter((p) => !SCREENSAVER_KEYS.has(p.key));
  const sleepPrefKeys = new Set(sleepPrefs.map((p) => p.key));
  const sleepEntities = store.getSectionItems("sleep").filter((it) => {
    if (it.pref_key) return false;
    const k = it.key || (it.entity_id ? it.entity_id.split(".").pop() || "" : "");
    if (SCREENSAVER_KEYS.has(k) || Array.from(SCREENSAVER_KEYS).some((sk) => k.endsWith(sk))) {
      return false;
    }
    if (sleepPrefKeys.has(k) || Array.from(sleepPrefKeys).some((pk) => k.endsWith(pk))) {
      return false;
    }
    return true;
  });
  const batteryItems = store.getSectionItems("battery");
  const sleepItems = [...sleepPrefs, ...sleepEntities];
  const bothEmpty = !sleepItems.length && !batteryItems.length;
  return html`<section id="view-power">
    <div class="columns">
      <div class="column">
        ${sleepItems.length
          ? html`<div class="card" data-entity-card>
              <div class="card-header">
                <h3 class="card-title">Sleep &amp; Wake</h3>
              </div>
              <div class="card-content settings-list">
                ${sleepPrefs.map((p) => renderPrefControlRow(store, p))}
                ${sleepEntities.map((it) => renderNativeControlRow(store, it))}
              </div>
            </div>`
          : bothEmpty
            ? renderCard({
                title: "Power & Battery",
                body: html`<p class="empty-state">
                  No sleep or battery entities reported by this Device.
                </p>`,
              })
            : nothing}
      </div>
      <div class="column">
        ${batteryItems.length
          ? html`<div class="card" data-entity-card>
              <div class="card-header">
                <h3 class="card-title">Power &amp; Battery</h3>
              </div>
              <div class="card-content settings-list">
                ${batteryItems.map((it) => renderNativeControlRow(store, it))}
              </div>
            </div>`
          : nothing}
      </div>
    </div>
  </section>`;
}

// --- src/views/device-presence-view.ts ---
/**
 * Device BLE & Area Presence View (`presence`, D-032 / D-036):
 * Static Assigned Area vs. BLE Roaming, Fallback Area, and BLE Identity.
 */
function renderDevicePresenceView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const isBleOnly = cfg.kind === "ble_tag";
  const bleTracking = isBleOnly || Boolean(cfg.native_ble_tracking);
  const detectedRefPower = data?.live?.ble_detected_ref_power ?? -59;
  const refPowerPlaceholder = `Auto (${fmtNumber(detectedRefPower, store.hass, 0)} dBm)`;
  const refPowerValue =
    cfg.ble_ref_power !== null && cfg.ble_ref_power !== undefined
      ? String(cfg.ble_ref_power)
      : "";
  const bleBeaconPref = store.getPref("ble_beacon_mode");
  const bleAreaItems = store
    .getSectionItems("area")
    .filter((it) => !it.pref_key && it.key !== "ble_beacon_mode");
  return html`<section id="view-presence">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Area Tracking",
          contentClass: "settings-list",
          body: html`${!isBleOnly
              ? renderSwitchRow({
                  id: "cfg-native_ble_tracking",
                  label: "Track the Area with BLE Proxies",
                  description:
                    "Uses Home Assistant Area-assigned Bluetooth proxies to locate this Device automatically. Turn off to pin it to one assigned Area.",
                  checked: Boolean(cfg.native_ble_tracking),
                  onChange: (checked) =>
                    store.stageDeviceSetting(
                      "native_ble_tracking",
                      checked,
                      "cfg-native_ble_tracking",
                    ),
                })
              : nothing}
            ${bleTracking
              ? html`${!isBleOnly
                    ? renderSwitchRow({
                        id: "cfg-ble_auto_switch",
                        label: "Auto-Switch Active Area",
                        description:
                          "Switches the Device's active Area controls automatically when BLE detects a move.",
                        checked: Boolean(cfg.ble_auto_switch),
                        onChange: (checked) =>
                          store.stageDeviceSetting(
                            "ble_auto_switch",
                            checked,
                            "cfg-ble_auto_switch",
                          ),
                      })
                    : nothing}
                  ${renderSelectRow({
                    id: "cfg-default_area",
                    label: "Fallback Area",
                    description:
                      "Default Home Assistant Area when no Bluetooth proxy is in range.",
                    value: cfg.default_area,
                    choices: data?.catalog?.areas,
                    emptyOptionLabel: "— Automatic (ESPHome Area) —",
                    onChange: (val) =>
                      store.stageDeviceSetting(
                        "default_area",
                        val,
                        "cfg-default_area",
                      ),
                  })}
                  ${bleBeaconPref ? renderPrefControlRow(store, bleBeaconPref) : nothing}
                  ${bleAreaItems.map((it) => renderNativeControlRow(store, it))}`
              : renderSelectRow({
                  id: "cfg-default_area",
                  label: "Assigned Area",
                  description:
                    "Pins this Device's Area controls and Home Assistant Device Area to one location.",
                  value: cfg.default_area,
                  choices: data?.catalog?.areas,
                  emptyOptionLabel: "— Unassigned —",
                  onChange: (val) =>
                    store.stageDeviceSetting(
                      "default_area",
                      val,
                      "cfg-default_area",
                    ),
                })}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "BLE Identity",
          contentClass: "stack",
          body: html`<div class="stacked-field">
              <label for="cfg-ble_target_address">BLE Target Address or Entity</label>
              <input
                type="text"
                id="cfg-ble_target_address"
                placeholder="AA:BB:CC:DD:EE:FF or device_tracker.phone_ble"
                .value=${String(cfg.ble_target_address || "")}
                @change=${(ev) =>
                  store.stageDeviceSetting(
                    "ble_target_address",
                    (ev.currentTarget).value.trim(),
                    "cfg-ble_target_address",
                  )}
              />
              <span class="help-text">
                Leave blank on Latter displays to track their built-in BLE beacon MAC automatically.
              </span>
            </div>
            <div class="stacked-field">
              <label for="cfg-ble_ref_power">Reference Power (1 Meter)</label>
              <input
                type="number"
                id="cfg-ble_ref_power"
                min="-90"
                max="-30"
                step="1"
                placeholder=${refPowerPlaceholder}
                .value=${refPowerValue}
                @change=${(ev) => {
                  const raw = (ev.currentTarget).value.trim();
                  if (raw === "") {
                    store.stageDeviceSetting("ble_ref_power", null, "cfg-ble_ref_power");
                    return;
                  }
                  const num = Number(raw);
                  if (Number.isFinite(num)) {
                    store.stageDeviceSetting("ble_ref_power", Math.round(num), "cfg-ble_ref_power");
                  }
                }}
              />
              <span class="help-text">
                Leave blank to use auto-detected beacon power in dBm, or enter -90 to -30 dBm to calibrate this Device.
              </span>
            </div>
            ${!isBleOnly
              ? html`<div class="stacked-field">
                  <label for="cfg-ble_beacon_uuid">iBeacon UUID</label>
                  <input
                    type="text"
                    id="cfg-ble_beacon_uuid"
                    placeholder="Generated automatically per System"
                    .value=${String(cfg.ble_beacon_uuid || "")}
                    @change=${(ev) =>
                      store.stageDeviceSetting(
                        "ble_beacon_uuid",
                        (ev.currentTarget).value.trim(),
                        "cfg-ble_beacon_uuid",
                      )}
                  />
                </div>`
              : nothing}`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/device-tools-view.ts ---
/**
 * Device Tools View (`tools`, D-027): Standard Diagnostics + collapsed Developer & Telemetry drawer,
 * Perimeter Security Policy + write-only PIN, Replace Hardware & Danger Zone.
 */
const INTERACTIVE_ENTITY_DOMAINS = new Set([
  "update",
  "button",
  "switch",
  "select",
  "number",
]);
function isValidTelemetryState(val) {
  const s = String(val ?? "").trim();
  return s !== "" && s !== "unknown" && s !== "unavailable";
}
const INTERNAL_NETWORK_BLOB_KEYS = new Set([
  "rpc_outbox",
  "hardware_manifest",
  "link_report",
]);
function isInternalNetworkBlobEntity(it) {
  if (it.key && INTERNAL_NETWORK_BLOB_KEYS.has(it.key)) return true;
  return Array.from(INTERNAL_NETWORK_BLOB_KEYS).some((k) => it.entity_id.endsWith(`_${k}`));
}
const SUMMARY_DUPLICATE_KEYS = new Set([
  "wifi_signal",
  "ip_address",
  "mac_address",
  "firmware_version",
  "latter_sdk",
  "sdk_rev",
]);
function isSummaryDuplicateNetworkEntity(it) {
  if (it.key && SUMMARY_DUPLICATE_KEYS.has(it.key)) return true;
  return Array.from(SUMMARY_DUPLICATE_KEYS).some((k) => it.entity_id.endsWith(`_${k}`));
}
function formatTelemetryDuration(totalSec) {
  if (!Number.isFinite(totalSec) || totalSec < 0) return "—";
  const secs = Math.round(totalSec);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) {
    const remSec = secs % 60;
    return remSec > 0 ? `${mins}m ${remSec}s` : `${mins}m`;
  }
  const hours = Math.floor(mins / 60);
  if (hours < 24) {
    const remMin = mins % 60;
    return remMin > 0 ? `${hours}h ${remMin}m` : `${hours}h`;
  }
  const days = Math.floor(hours / 24);
  const remHr = hours % 24;
  return remHr > 0 ? `${days}d ${remHr}h` : `${days}d`;
}
function parseDeviceLinkReportRows(
  rawState,
  hass,
) {
  if (!isValidTelemetryState(rawState)) return [];
  const kv = new Map();
  for (const tok of rawState.trim().split(/\s+/)) {
    const eq = tok.indexOf("=");
    if (eq > 0 && eq < tok.length - 1) {
      kv.set(tok.slice(0, eq), tok.slice(eq + 1));
    }
  }
  if (!kv.size) return [];
  const rows = [];
  const upRaw = kv.get("up");
  if (upRaw !== undefined && Number.isFinite(Number(upRaw))) {
    rows.push({
      label: "Session Uptime",
      value: formatTelemetryDuration(Number(upRaw)),
    });
  }
  const rstRaw = kv.get("rst");
  if (rstRaw) {
    rows.push({ label: "Last Reset", value: rstRaw, code: true });
  }
  const discRaw = kv.get("disc");
  if (discRaw !== undefined && Number.isFinite(Number(discRaw))) {
    const btoNum = Number(kv.get("bto") ?? 0);
    const btoSuffix =
      Number.isFinite(btoNum) && btoNum > 0
        ? ` (${fmtNumber(btoNum, hass, 0)} beacon timeouts)`
        : "";
    rows.push({
      label: "Wi-Fi Disconnects",
      value: `${fmtNumber(Number(discRaw), hass, 0)}${btoSuffix}`,
    });
  }
  const rssiRaw = kv.get("rssi");
  if (rssiRaw && rssiRaw !== "na" && rssiRaw.includes("/")) {
    const [avgStr, minStr] = rssiRaw.split("/", 2);
    if (Number.isFinite(Number(avgStr)) && Number.isFinite(Number(minStr))) {
      rows.push({
        label: "Wi-Fi Avg / Min",
        value: `${fmtNumber(Number(avgStr), hass, 0)} / ${fmtNumber(Number(minStr), hass, 0)} dBm`,
      });
    }
  }
  const haRaw = kv.get("ha");
  if (haRaw !== undefined && Number.isFinite(Number(haRaw))) {
    const gapNum = Number(kv.get("gap") ?? 0);
    const gapSuffix =
      Number.isFinite(gapNum) && gapNum > 0
        ? ` (max gap ${formatTelemetryDuration(gapNum)})`
        : "";
    rows.push({
      label: "HA Sessions",
      value: `${fmtNumber(Number(haRaw), hass, 0)}${gapSuffix}`,
    });
  }
  const slpRaw = kv.get("slp");
  if (slpRaw !== undefined && Number.isFinite(Number(slpRaw))) {
    const lsNum = Number(kv.get("ls") ?? 0);
    const lsSuffix =
      Number.isFinite(lsNum) && lsNum > 0
        ? ` (${fmtNumber(lsNum, hass, 0)} cycles)`
        : "";
    rows.push({
      label: "Light Sleep Duty",
      value: `${fmtNumber(Number(slpRaw), hass, 1)}%${lsSuffix}`,
    });
  }
  const nvsRaw = kv.get("nvs");
  if (nvsRaw && nvsRaw.includes("/")) {
    const parts = nvsRaw.split("/");
    if (parts.length >= 3 && parts.every((p) => Number.isFinite(Number(p)))) {
      rows.push({
        label: "NVS Flash Writes",
        value: `${fmtNumber(Number(parts[0]), hass, 0)} writes (${fmtNumber(Number(parts[1]), hass, 0)} erases, ${fmtNumber(Number(parts[2]), hass, 0)} ms max)`,
      });
    }
  }
  return rows;
}
function parseDeviceHardwareManifestRows(
  rawState,
  hass,
) {
  if (!isValidTelemetryState(rawState)) return [];
  const trimmed = rawState.trim();
  if (!trimmed.startsWith("{")) return [];
  let parsed;
  try {
    const obj = JSON.parse(trimmed);
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return [];
    parsed = obj;
  } catch {
    return [];
  }
  const rows = [];
  const board = typeof parsed.board === "string" ? parsed.board.trim() : "";
  if (board) {
    rows.push({ label: "Hardware Board", value: board, code: true });
  }
  const chip = typeof parsed.chip === "string" ? parsed.chip.trim() : "";
  const psramMb = Number(parsed.psram_mb ?? 0);
  if (chip) {
    const psramSuffix =
      Number.isFinite(psramMb) && psramMb > 0
        ? ` • ${fmtNumber(psramMb, hass, 0)} MB PSRAM`
        : "";
    rows.push({ label: "Processor & PSRAM", value: `${chip}${psramSuffix}` });
  }
  const hasDisplay = Number(parsed.display ?? 0) === 1 && parsed.shape !== "none";
  if (parsed.display !== undefined) {
    if (!hasDisplay) {
      rows.push({ label: "Display Panel", value: "Headless" });
    } else {
      const w = Number(parsed.w ?? 0);
      const h = Number(parsed.h ?? 0);
      const shape = typeof parsed.shape === "string" ? parsed.shape.trim() : "";
      const panelTech =
        parsed.ips === 1 ? "IPS" : parsed.ips === 0 ? "AMOLED" : "";
      if (w > 0 && h > 0) {
        const parts = [`${w}×${h}`, shape, panelTech].filter(Boolean);
        rows.push({ label: "Display Panel", value: parts.join(" ") });
      }
    }
  }
  const traits = [];
  if (Number(parsed.touch) === 1) traits.push("Touch");
  if (Number(parsed.mic) === 1) traits.push("Mic");
  if (Number(parsed.spk) === 1) traits.push("Speaker");
  if (Number(parsed.mic) !== 1 && Number(parsed.spk) !== 1 && Number(parsed.audio) === 1) {
    traits.push("Audio");
  }
  if (Number(parsed.imu) === 1) traits.push("IMU");
  if (Number(parsed.battery) === 1) traits.push("Battery");
  if (Number(parsed.wearable) === 1) traits.push("Wearable");
  if (Number(parsed.stationary) === 1) traits.push("Stationary");
  if (traits.length) {
    rows.push({ label: "Hardware Traits", value: traits.join(", ") });
  }
  return rows;
}
function renderDeviceToolsView(store) {
  const data = store.state;
  const cfg = data?.config || {};
  const live = data?.live || {};
  const links = data?.links || {};
  const esp = data?.esphome;
  const isBleOnly = cfg.kind === "ble_tag";
  const curDevEntry =
    (data?.system_devices || []).find((d) => d.subentry_id === store.activeSubentryId) ||
    (data?.system_devices || []).find((d) => d.is_current);
  const networkItems = store.getSectionItems("network");
  const developerItems = store.getSectionItems("developer");
  const networkControlItems = networkItems.filter((it) =>
    INTERACTIVE_ENTITY_DOMAINS.has(it.domain),
  );
  const extraNetworkSensorItems = networkItems.filter(
    (it) =>
      !INTERACTIVE_ENTITY_DOMAINS.has(it.domain) &&
      !isInternalNetworkBlobEntity(it) &&
      !isSummaryDuplicateNetworkEntity(it),
  );
  const findNetworkState = (key) => {
    const match = networkItems.find(
      (it) => it.key === key || it.entity_id.endsWith(`_${key}`),
    );
    return isValidTelemetryState(match?.state) ? String(match?.state).trim() : "";
  };
  const winRow = (curDevEntry?.ble_survey_rows || []).find((r) => r.is_winner);
  let signalText = "—";
  if (!isBleOnly) {
    if (curDevEntry?.wifi_rssi !== null && curDevEntry?.wifi_rssi !== undefined) {
      signalText = `${fmtNumber(curDevEntry.wifi_rssi, store.hass, 0)} dBm`;
    } else {
      const rawWifi = findNetworkState("wifi_signal");
      if (rawWifi) {
        signalText = Number.isFinite(Number(rawWifi))
          ? `${fmtNumber(Number(rawWifi), store.hass, 0)} dBm`
          : rawWifi;
      }
    }
  } else if (winRow && winRow.effective_rssi !== null) {
    signalText = `${fmtNumber(winRow.effective_rssi, store.hass, 0)} dBm`;
  }
  const rawSw = String(
    live.device_sw_version || esp?.device?.sw_version || findNetworkState("firmware_version") || "",
  ).replace(/^v/i, "");
  const fwVersionText = rawSw ? `v${rawSw}` : "—";
  const modelText = curDevEntry?.model_label || esp?.device?.model || "—";
  const ipStr = curDevEntry?.ip_address || findNetworkState("ip_address") || "";
  const macStr = esp?.device?.mac || findNetworkState("mac_address") || "";
  const weatherSimPref = store.getPref("weather_sim_condition");
  const devControlItems = developerItems.filter(
    (it) =>
      INTERACTIVE_ENTITY_DOMAINS.has(it.domain) &&
      !it.pref_key &&
      it.key !== "weather_sim_condition",
  );
  const devSensorItems = developerItems.filter(
    (it) => !INTERACTIVE_ENTITY_DOMAINS.has(it.domain),
  );
  const linkReportEntity = networkItems.find(
    (it) => it.key === "link_report" || it.entity_id.endsWith("_link_report"),
  );
  const manifestEntity = networkItems.find(
    (it) => it.key === "hardware_manifest" || it.entity_id.endsWith("_hardware_manifest"),
  );
  const linkRows = parseDeviceLinkReportRows(linkReportEntity?.state, store.hass);
  const manifestRows = parseDeviceHardwareManifestRows(manifestEntity?.state, store.hass);
  const hasDeveloperDrawer =
    !isBleOnly &&
    Boolean(
      weatherSimPref ||
        devControlItems.length ||
        devSensorItems.length ||
        linkRows.length ||
        manifestRows.length,
    );
  const curPinPolicy = String(cfg.security_pin_policy || "auto");
  const hasPin = store.hasConfiguredSecurityPin;
  return html`<section id="view-tools">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Diagnostics</h3>`,
          contentClass: "stack",
          body: html`${networkControlItems.length
              ? html`<div class="settings-list">
                  ${networkControlItems.map((it) => renderNativeControlRow(store, it))}
                </div>`
              : nothing}
            <div class="kv-list">
              ${isBleOnly
                ? html`<div class="kv-row">
                      <span>BLE Signal</span>
                      <strong>${signalText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>BLE Target</span>
                      <strong>${cfg.ble_target_address ? html`<code>${cfg.ble_target_address}</code>` : "—"}</strong>
                    </div>`
                : html`<div class="kv-row">
                      <span>Model</span>
                      <strong>${modelText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>ESPHome Node</span>
                      <strong><code id="diag-node-name">${cfg.device_slug || "—"}</code></strong>
                    </div>
                    <div class="kv-row">
                      <span>Firmware Version</span>
                      <strong>${fwVersionText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>Latter SDK</span>
                      <strong id="diag-sdk-rev">${live.sdk_rev || "—"}</strong>
                    </div>
                    <div class="kv-row">
                      <span>Wi-Fi Signal</span>
                      <strong>${signalText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>IP Address</span>
                      <strong>${ipStr ? html`<code>${ipStr}</code>` : "—"}</strong>
                    </div>
                    ${macStr
                      ? html`<div class="kv-row">
                          <span>MAC Address</span>
                          <strong><code>${macStr}</code></strong>
                        </div>`
                      : nothing}
                    ${extraNetworkSensorItems.map((it) => renderNativeControlRow(store, it))}`}
            </div>
            ${links.latter_device_id || links.entry_id
              ? html`<div class="settings-list">
                  ${renderSettingsRow({
                    id: "row-diagnostics",
                    label: "Diagnostics File",
                    description: "Downloads redacted Home Assistant diagnostics for troubleshooting.",
                    control: html`<button
                      type="button"
                      @click=${() => void store.downloadDeviceDiagnostics()}
                      class="btn btn-secondary btn-compact"
                    >
                      Download Diagnostics
                    </button>`,
                  })}
                </div>`
              : nothing}
            ${hasDeveloperDrawer
              ? html`<details class="sub-collapsible">
                  <summary>Developer &amp; Telemetry</summary>
                  <div class="card-content">
                    ${weatherSimPref || devControlItems.length
                      ? html`<div class="settings-list">
                          ${weatherSimPref ? renderPrefControlRow(store, weatherSimPref) : nothing}
                          ${devControlItems.map((it) => renderNativeControlRow(store, it))}
                        </div>`
                      : nothing}
                    ${devSensorItems.length || linkRows.length || manifestRows.length
                      ? html`<div class="kv-list">
                          ${devSensorItems.map((it) => renderNativeControlRow(store, it))}
                          ${[...linkRows, ...manifestRows].map(
                            (row) => html`<div class="kv-row">
                              <span>${row.label}</span>
                              <strong>${row.code ? html`<code>${row.value}</code>` : row.value}</strong>
                            </div>`,
                          )}
                        </div>`
                      : nothing}
                  </div>
                </details>`
              : nothing}`,
          footerActions:
            !isBleOnly && (links.esphome_device_id || links.latter_device_id)
              ? html`<button
                  type="button"
                  id="btn-tools-open-in-ha"
                  @click=${() => store.openDeviceInHa()}
                  class="btn btn-text"
                >
                  Open in ESPHome
                </button>`
              : nothing,
        })}
      </div>

      <div class="column">
        ${!isBleOnly
          ? html`${renderCard({
                id: "card-device-security",
                title: "Perimeter Security",
                subtitle:
                  "Governs unlocking doors, disarming alarms, and opening garage or gate covers from this Device.",
                contentClass: "settings-list",
                body: html`${renderSelectRow({
                    id: "cfg-security_pin_policy",
                    label: "Perimeter Security Policy",
                    description: html`Auto requires a PIN on stationary wall panels when configured and allows roaming personal Devices. Effective policy: <strong>${live.effective_security_pin_policy || curPinPolicy}</strong>.`,
                    value: curPinPolicy,
                    rawOptions: SECURITY_PIN_POLICY_OPTIONS,
                    onChange: (val) =>
                      store.stageDeviceSetting(
                        "security_pin_policy",
                        val,
                        "cfg-security_pin_policy",
                      ),
                  })}
                  ${renderSettingsRow({
                    label: "Security PIN",
                    description:
                      "Write-only 4 to 12 digit numeric PIN verified server-side (PBKDF2-HMAC-SHA256) when the on-device keypad prompts. Never echoed back to the browser.",
                    stacked: true,
                    control: html`<div class="input-action-row">
                      <span class="chip ${hasPin ? "chip-success" : ""}">
                        ${hasPin ? "PIN configured" : "Not set"}
                      </span>
                      <input
                        type="password"
                        id="dev-security-pin-input"
                        inputmode="numeric"
                        pattern="[0-9]*"
                        autocomplete="new-password"
                        aria-label="New Security PIN (4 to 12 digits)"
                        placeholder=${hasPin ? "Enter new PIN to replace…" : "4 to 12 digits"}
                        .value=${store.devicePinDraft}
                        @input=${(ev) => {
                          store.devicePinDraft = (ev.currentTarget).value;
                          store.host.requestUpdate();
                        }}
                      />
                      <button
                        type="button"
                        ?disabled=${store.pinBusy || !store.devicePinDraft.trim()}
                        @click=${() => void store.saveSecurityPin("device")}
                        class="btn btn-primary btn-compact"
                      >
                        Save PIN
                      </button>
                      ${hasPin
                        ? html`<button
                            type="button"
                            ?disabled=${store.pinBusy}
                            @click=${() => void store.clearSecurityPin("device")}
                            class="btn btn-danger btn-compact"
                          >
                            Clear PIN
                          </button>`
                        : nothing}
                    </div>`,
                  })}`,
              })}
              ${renderCard({
                id: "card-replace-hardware",
                heading: html`<h3 class="card-title">Replace Hardware</h3>`,
                contentClass: "stack",
                body: html`<p class="row-description">
                    Moving to a replacement board? Download this Device's backup first, add the new ESPHome board in Home Assistant, and restore the backup onto it from System Tools.
                  </p>
                  <div class="input-action-row">
                    <button
                      type="button"
                      @click=${() => void store.exportBackup(store.activeSubentryId)}
                      class="btn btn-secondary"
                    >
                      Download Device Backup
                    </button>
                    <button
                      type="button"
                      @click=${() => store.openSystemSection("system_tools", "card-backup-restore")}
                      class="btn btn-text"
                    >
                      Open Backup &amp; Restore
                    </button>
                  </div>`,
              })}`
          : nothing}

        ${renderCard({
          heading: html`<h3 class="card-title">Danger Zone</h3>`,
          danger: true,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: "Reset to Defaults",
              description:
                "Resets on-device preferences and/or Latter settings while keeping Wi-Fi and Home Assistant pairing.",
              control: html`<button
                type="button"
                @click=${() => store.openResetDeviceModal()}
                class="btn btn-danger"
              >
                Reset to Defaults
              </button>`,
            })}
            ${renderSettingsRow({
              label: "Remove Device",
              description:
                "Removes this subentry from Latter. The ESPHome device remains in Home Assistant.",
              control: html`<button
                type="button"
                @click=${() =>
                  store.openRemoveDeviceModal(
                    store.activeSubentryId,
                    data?.title || cfg.device_slug || "Device",
                  )}
                class="btn btn-danger"
              >
                Remove Device
              </button>`,
            })}`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/devices-discovered-view.ts ---
/**
 * Discovered Devices View (`discovered_devices`): Two stacked full-width onboarding cards (`D-041`):
 * 1. `Latter Devices` — Unbound ESPHome Devices running Latter firmware ready for one-click adoption.
 * 2. `Bluetooth Devices` — Filterable, sortable (Name default so RSSI changes never reorder rows),
 *    and pausable BLE trackers, phones, and named advertisements with keyed DOM identity.
 */
function isTrackerCandidate(c) {
  const kind = String(c.kind || "").toLowerCase();
  const addr = String(c.target_address || c.address || "");
  return kind.includes("private ble") || kind.includes("ibeacon") || addr.includes(".");
}
function candidateTitle(c) {
  return c.title || c.name || c.target_address || c.address || "BLE Tag";
}
function candidateAddr(c) {
  return c.target_address || c.address || "";
}
function compareBleCandidates(
  a,
  b,
  sortMode,
) {
  const aTitle = candidateTitle(a);
  const bTitle = candidateTitle(b);
  const aAddr = candidateAddr(a);
  const bAddr = candidateAddr(b);
  if (sortMode === "rssi") {
    const aHas = a.rssi !== null && a.rssi !== undefined;
    const bHas = b.rssi !== null && b.rssi !== undefined;
    if (aHas !== bHas) return aHas ? -1 : 1;
    if (aHas && bHas && a.rssi !== b.rssi) return Number(b.rssi) - Number(a.rssi);
  } else if (sortMode === "area") {
    const aArea = String(a.area_name || "").trim();
    const bArea = String(b.area_name || "").trim();
    if (Boolean(aArea) !== Boolean(bArea)) return aArea ? -1 : 1;
    if (aArea && bArea) {
      const areaCmp = aArea.localeCompare(bArea, undefined, { sensitivity: "base" });
      if (areaCmp !== 0) return areaCmp;
    }
  }
  const nameCmp = aTitle.localeCompare(bTitle, undefined, { sensitivity: "base" });
  if (nameCmp !== 0) return nameCmp;
  return aAddr.localeCompare(bAddr);
}
function renderDevicesDiscoveredView(store) {
  const data = store.state;
  const latterCandidates = data?.discovered_latter_devices || [];
  const isPaused = Boolean(store.discoveredBlePaused);
  const bleCandidates =
    isPaused && Array.isArray(store.discoveredBleFrozenSnapshot)
      ? store.discoveredBleFrozenSnapshot
      : data?.discovered_ble_devices || [];
  const groups = data?.device_groups || [];
  const persons = data?.catalog?.persons || [];
  const groupNameMap = new Map();
  for (const g of groups) {
    if (g && g.id) {
      groupNameMap.set(g.id, g.name || entityLabel(g.id.replace(/_/g, " ")));
    }
  }
  const kindFilter = store.discoveredBleKindFilter || "all";
  const sortMode = store.discoveredBleSort || "name";
  const query = (store.discoveredBleSearch || "").trim().toLowerCase();
  const filteredBle = bleCandidates
    .filter((c) => {
      if (kindFilter === "tracker" && !isTrackerCandidate(c)) return false;
      if (kindFilter === "named" && isTrackerCandidate(c)) return false;
      if (!query) return true;
      const haystack = [
        c.title,
        c.name,
        c.target_address,
        c.address,
        c.kind,
        c.area_name,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    })
    .slice()
    .sort((a, b) => compareBleCandidates(a, b, sortMode));
  const latterDraftGroups = store.discoveredLatterGroupDrafts;
  const latterDraftPersons = store.discoveredLatterPersonDrafts;
  const bleDraftPersons = store.discoveredBlePersonDrafts;
  return html`<section id="view-discovered_devices">
    ${renderCard({
      title: "Latter Devices",
      headerActions: html`<button
        type="button"
        @click=${() => store.openHaPage("/config/integrations/integration/latter")}
        class="btn btn-secondary"
      >
        Open Integration
      </button>`,
      contentClass: "settings-list",
      body: html`<div id="latter-adopt-table-box" class="settings-list">
        ${latterCandidates.length
          ? repeat(
              latterCandidates,
              (d) => d.esphome_device_id,
              (d) => {
                const title = d.title || d.node_name || "Latter Device";
                const defGrpName =
                  groupNameMap.get(d.default_group) ||
                  entityLabel((d.default_group || "custom").replace(/_/g, " "));
                const meta = [d.model_label || "Latter ESPHome Device"];
                if (d.node_name) meta.push(`Node: ${d.node_name}`);
                if (d.area_name) meta.push(`Area: ${d.area_name}`);
                const curGrp = latterDraftGroups?.get(d.esphome_device_id) || "auto";
                const curPerson = latterDraftPersons?.get(d.esphome_device_id) || "";
                return renderSettingsRow({
                  label: title,
                  description: meta.join(" • "),
                  control: html`<select
                      data-role="group"
                      aria-label=${`Device Group for ${title}`}
                      .value=${curGrp}
                      @change=${(ev) => {
                        latterDraftGroups?.set(
                          d.esphome_device_id,
                          (ev.currentTarget).value || "auto",
                        );
                      }}
                    >
                      <option value="auto" ?selected=${curGrp === "auto"}>
                        Auto (${defGrpName})
                      </option>
                      <option value="custom" ?selected=${curGrp === "custom"}>
                        Custom
                      </option>
                      ${groups.map(
                        (g) =>
                          html`<option value=${g.id} ?selected=${curGrp === g.id}>
                            ${g.name}
                          </option>`,
                      )}
                    </select>
                    <select
                      data-role="person"
                      aria-label=${`Assigned person for ${title}`}
                      .value=${curPerson}
                      @change=${(ev) => {
                        latterDraftPersons?.set(
                          d.esphome_device_id,
                          (ev.currentTarget).value || "",
                        );
                      }}
                    >
                      <option value="" ?selected=${!curPerson}>No person</option>
                      ${persons.map(
                        (p) =>
                          html`<option value=${p.id} ?selected=${curPerson === p.id}>
                            ${p.name}
                          </option>`,
                      )}
                    </select>
                    <button
                      type="button"
                      @click=${(ev) => {
                        const btn = ev.currentTarget;
                        const parent = btn.parentElement;
                        const grpSel = parent?.querySelector(
                          'select[data-role="group"]',
                        );
                        const personSel = parent?.querySelector(
                          'select[data-role="person"]',
                        );
                        void store.adoptLatterDevice(
                          d.esphome_device_id,
                          title,
                          grpSel?.value || latterDraftGroups?.get(d.esphome_device_id) || "auto",
                          personSel?.value || latterDraftPersons?.get(d.esphome_device_id) || "",
                        );
                      }}
                      class="btn btn-secondary btn-compact"
                    >
                      Adopt
                    </button>`,
                });
              },
            )
          : html`<p class="empty-state">
              No unconfigured Latter Devices found in Home Assistant. Newly added ESPHome Devices running Latter firmware appear here automatically.
            </p>`}
      </div>`,
    })}

    ${renderCard({
      title: "Bluetooth Devices",
      headerActions: html`<input
          type="search"
          id="discovered-ble-search"
          aria-label="Search discovered Bluetooth devices"
          placeholder="Search name, address, or Area…"
          .value=${store.discoveredBleSearch}
          @input=${(ev) => {
            store.discoveredBleSearch = (ev.currentTarget).value;
            store.host.requestUpdate();
          }}
        />
        <select
          id="discovered-ble-filter"
          aria-label="Filter discovered Bluetooth devices"
          .value=${kindFilter}
          @change=${(ev) => {
            const val = (ev.currentTarget).value;
            store.discoveredBleKindFilter =
              val === "tracker" || val === "named" ? val : "all";
            store.host.requestUpdate();
          }}
        >
          <option value="all" ?selected=${kindFilter === "all"}>All Bluetooth devices</option>
          <option value="tracker" ?selected=${kindFilter === "tracker"}>
            Phones and trackers
          </option>
          <option value="named" ?selected=${kindFilter === "named"}>
            Named advertisements
          </option>
        </select>
        <select
          id="discovered-ble-sort"
          aria-label="Sort discovered Bluetooth devices"
          .value=${sortMode}
          @change=${(ev) => {
            const val = (ev.currentTarget).value;
            store.discoveredBleSort =
              val === "rssi" || val === "area" ? val : "name";
            store.host.requestUpdate();
          }}
        >
          <option value="name" ?selected=${sortMode === "name"}>Sort: Name (A–Z)</option>
          <option value="rssi" ?selected=${sortMode === "rssi"}>Sort: Signal strength</option>
          <option value="area" ?selected=${sortMode === "area"}>Sort: Nearest Area</option>
        </select>
        <button
          type="button"
          id="btn-pause-discovered-ble"
          aria-pressed=${String(isPaused)}
          @click=${() => store.toggleDiscoveredBlePause()}
          class="btn btn-secondary"
        >
          ${isPaused ? "Resume List" : "Pause List"}
        </button>
        <button
          type="button"
          @click=${() => store.openAddBleModal()}
          class="btn btn-primary"
        >
          Add BLE Tag
        </button>`,
      contentClass: "settings-list",
      body: html`<div id="ble-adopt-table-box" class="settings-list">
        ${isPaused
          ? html`<p class="help-text">
              List updates paused (${fmtNumber(filteredBle.length, store.hass, 0)} shown). Click Resume List to refresh.
            </p>`
          : nothing}
        ${filteredBle.length
          ? repeat(
              filteredBle,
              (c) => (candidateAddr(c) || candidateTitle(c)).toLowerCase(),
              (c) => {
                const title = candidateTitle(c);
                const addr = candidateAddr(c);
                const addrKey = (addr || title).toLowerCase();
                const curPerson = bleDraftPersons?.get(addrKey) || "";
                const meta = [c.kind || "BLE device", addr];
                if (c.rssi !== null && c.rssi !== undefined) {
                  meta.push(`${fmtNumber(c.rssi, store.hass, 0)} dBm`);
                }
                if (c.area_name) {
                  meta.push(`Nearest Area: ${c.area_name}`);
                }
                return renderSettingsRow({
                  label: title,
                  description: meta.join(" • "),
                  control: html`<select
                      aria-label=${`Assigned person for ${title}`}
                      .value=${curPerson}
                      @change=${(ev) => {
                        bleDraftPersons?.set(
                          addrKey,
                          (ev.currentTarget).value || "",
                        );
                      }}
                    >
                      <option value="" ?selected=${!curPerson}>No person</option>
                      ${persons.map(
                        (p) =>
                          html`<option value=${p.id} ?selected=${curPerson === p.id}>
                            ${p.name}
                          </option>`,
                      )}
                    </select>
                    <button
                      type="button"
                      @click=${(ev) => {
                        const btn = ev.currentTarget;
                        const sel = btn.parentElement?.querySelector(
                          "select",
                        );
                        void store.quickAdoptBleCandidate(
                          title,
                          addr,
                          sel?.value || bleDraftPersons?.get(addrKey) || "",
                        );
                      }}
                      class="btn btn-secondary btn-compact"
                    >
                      Adopt
                    </button>`,
                });
              },
            )
          : html`<p class="empty-state">
              ${bleCandidates.length
                ? "No Bluetooth devices match this filter."
                : "No unadopted Bluetooth devices nearby."}
            </p>`}
      </div>`,
    })}
  </section>`;
}

// --- src/views/devices-list-view.ts ---
/**
 * Managed Devices View (`select_device_prompt`): Filterable, keyboard-accessible sortable Devices table.
 * Card header dynamically reflects the active category selection (`D-041`), while zero-member groups
 * and unused specialty categories stay hidden unless active (`D-048`).
 */
function statusRank(st) {
  if (st === "Update available") return 1;
  if (st === "Offline") return 2;
  return 3;
}
function renderDevicesListView(store) {
  const allDevices = store.state?.system_devices || [];
  const groups = store.state?.device_groups || [];
  const rawCat = store.deviceCategoryFilter || "all";
  const hasBleTags = allDevices.some((d) => d.kind === "ble_tag");
  const hasAssignedPeople = allDevices.some((d) => Boolean(d.assigned_person));
  const hasUpdates = allDevices.some((d) => d.status_label === "Update available");
  const hasCustomGroup = allDevices.some(
    (d) => d.kind !== "ble_tag" && (!d.device_group || d.device_group === "custom"),
  );
  const baseCategories = [
    { id: "all", label: "All Devices" },
    { id: "online", label: "Online Devices" },
    { id: "roaming", label: "Roaming Devices" },
    { id: "stationary", label: "Stationary Devices" },
  ];
  if (rawCat === "native") {
    baseCategories.push({ id: "native", label: "Latter Displays" });
  }
  if (rawCat === "ble_tracked") {
    baseCategories.push({ id: "ble_tracked", label: "BLE-Tracked Devices" });
  }
  if (hasBleTags || rawCat === "ble_tag") {
    baseCategories.push({ id: "ble_tag", label: "BLE Tags" });
  }
  if (hasAssignedPeople || rawCat === "assigned_person") {
    baseCategories.push({ id: "assigned_person", label: "Assigned to a Person" });
  }
  if (hasUpdates || rawCat === "updates") {
    baseCategories.push({ id: "updates", label: "Updates Available" });
  }
  for (const g of groups) {
    if (!g || !g.id || g.id === "custom") continue;
    const grpFilterId = `group:${g.id}`;
    const hasMembers = allDevices.some((d) => d.kind !== "ble_tag" && d.device_group === g.id);
    if (hasMembers || rawCat === grpFilterId) {
      baseCategories.push({ id: grpFilterId, label: `Group: ${entityLabel(g.name)}` });
    }
  }
  if (hasCustomGroup || rawCat === "group:custom") {
    baseCategories.push({ id: "group:custom", label: "Group: Custom" });
  }
  const activeCategory = baseCategories.find((o) => o.id === rawCat) || baseCategories[0];
  const cat = activeCategory.id;
  const filtered = allDevices.filter((d) => {
    const isBleTag = d.kind === "ble_tag";
    const isRoaming = isBleTag || Boolean(d.is_roaming);
    if (cat === "online") return Boolean(d.is_online);
    if (cat === "native") return Boolean(d.is_latter_native);
    if (cat === "ble_tracked") return Boolean(d.ble_tracked);
    if (cat === "assigned_person") return Boolean(d.assigned_person);
    if (cat === "roaming") return isRoaming;
    if (cat === "stationary") return !isRoaming;
    if (cat === "ble_tag") return isBleTag;
    if (cat === "updates") return d.status_label === "Update available";
    if (cat === "group:custom") {
      return !isBleTag && (!d.device_group || d.device_group === "custom");
    }
    if (cat.startsWith("group:")) return !isBleTag && d.device_group === cat.slice(6);
    return true;
  });
  filtered.sort((a, b) => {
    let cmp = 0;
    if (store.deviceSortField === "status") {
      cmp = statusRank(a.status_label) - statusRank(b.status_label);
      if (cmp === 0) cmp = (a.title || "").localeCompare(b.title || "");
    } else if (store.deviceSortField === "model") {
      cmp = (a.model_label || "").localeCompare(b.model_label || "");
    } else if (store.deviceSortField === "area") {
      cmp = (a.area_label || "").localeCompare(b.area_label || "");
    } else if (store.deviceSortField === "group") {
      cmp = (a.device_group_name || "").localeCompare(b.device_group_name || "");
    } else {
      cmp = (a.title || "").localeCompare(b.title || "");
    }
    return store.deviceSortAsc ? cmp : -cmp;
  });
  return html`<section id="view-select_device_prompt">
    ${renderCard({
      title: activeCategory.label,
      headerActions: html`<select
        id="device-category-filter"
        aria-label="Filter Managed Devices by category"
        .value=${cat}
        @change=${(ev) => {
          store.deviceCategoryFilter = (ev.currentTarget).value || "all";
          store.host.requestUpdate();
        }}
      >
        ${baseCategories.map(
          (o) => html`<option value=${o.id} ?selected=${o.id === cat}>${o.label}</option>`,
        )}
      </select>`,
      body: filtered.length
        ? html`<div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  ${renderSortHeader(store, "title", "Device")}
                  ${renderSortHeader(store, "model", "Model")}
                  ${renderSortHeader(store, "area", "Area")}
                  ${renderSortHeader(store, "group", "Group")}
                  ${renderSortHeader(store, "status", "Status")}
                  <th><span class="sort-btn" aria-hidden="true"></span></th>
                </tr>
              </thead>
              <tbody>
                ${repeat(
                  filtered,
                  (d) => d.subentry_id,
                  (d) => {
                    const st = d.status_label || "—";
                    const dotCls =
                      st === "Update available" ? "update" : st === "Offline" ? "" : "online";
                    const grpCell =
                      d.kind === "ble_tag"
                        ? "—"
                        : d.device_group_name || (d.device_group === "custom" ? "Custom" : "—");
                    const openRow = () => {
                      void store.switchSystemDevice(d.subentry_id);
                    };
                    const onRowKey = (ev) => {
                      const kev = ev;
                      if (kev.key === "Enter" || kev.key === " ") {
                        kev.preventDefault();
                        openRow();
                      }
                    };
                    return html`<tr
                      tabindex="0"
                      aria-label=${`Open ${d.title}`}
                      @click=${openRow}
                      @keydown=${onRowKey}
                    >
                      <td class="col-name">${d.title}</td>
                      <td>${d.model_label || "—"}</td>
                      <td>${d.area_label || "—"}</td>
                      <td>${grpCell}</td>
                      <td><span class="status-dot ${dotCls}"></span>${st}</td>
                      <td class="col-open" aria-hidden="true">›</td>
                    </tr>`;
                  },
                )}
              </tbody>
            </table>
          </div>`
        : html`<p class="empty-state">
            ${allDevices.length
              ? "No Devices match this category."
              : "No Managed Devices yet. Adopt discovered Latter Devices or add BLE Tags in Discovered."}
          </p>`,
    })}
  </section>`;
}

// --- src/views/system-groups-view.ts ---
/**
 * System Device Groups & Batch Controls View (`system_sync`, D-048 / D-050):
 * Column 1: Enclosed per-Group containers with inline expandable Baseline Settings
 *   (Operational settings by default, plus opt-in Display and Interface & Shortcuts).
 * Column 2: Tab-aligned Batch Controls across All, Online, Roaming, Stationary,
 *   any built-in or custom Device Group, or Custom.
 */
const WAKE_WORD_MODE_OPTIONS = ["Docked Only", "Always On", "Disabled"];
const TAP_TO_WAKE_OPTIONS = [
  "Single Tap",
  "Double Tap",
  "Docked Only",
  "Disabled",
];
const WAKE_GESTURE_OPTIONS = ["Always On", "Docked Only", "Disabled"];
const BATTERY_SCREEN_TIMEOUT_OPTIONS = [
  "10s",
  "15s",
  "30s",
  "1 min",
  "2 min",
  "Never",
];
const DOCKED_IDLE_TIMEOUT_OPTIONS = [
  "10s",
  "15s",
  "30s",
  "1 min",
  "2 min",
  "5 min",
  "Never",
];
const BATTERY_HIBERNATE_TIMEOUT_OPTIONS = [
  "5 min",
  "10 min",
  "15 min",
  "30 min",
  "Disabled",
];
const AUTO_BRIGHTNESS_MODE_OPTIONS = [
  "Disabled",
  "Sun Synchronized",
  "Time Schedule",
];
const BRIGHTNESS_PCT_OPTIONS = ["60%", "70%", "80%", "90%", "100%"];
const WW_SENSITIVITY_OPTIONS = [
  "Slightly sensitive",
  "Moderately sensitive",
  "Very sensitive",
];
const BLE_BEACON_MODE_OPTIONS = [
  "Handheld Only",
  "Handheld + Screen Off",
  "Always",
];
const SCREENSAVER_STYLE_OPTIONS = [
  "Ambient Clock",
  "Aurora",
  "Starfield",
  "Digital Rain",
  "Fireworks",
];
const COLOR_PROFILE_OPTIONS = [
  "Steel Blue",
  "Pink",
  "Blue",
  "Green",
  "Custom",
];
const VA_VISUAL_PROFILE_OPTIONS = [
  "Nebula",
  "Solaris",
  "Rings",
  "Light Bar",
  "Dot Wave",
];
const CLOCK_FACE_OPTIONS = [
  "Minimal Digital",
  "Modern Analog",
  "Hybrid Digital",
];
const TIME_FORMAT_OPTIONS = ["12-Hour (AM/PM)", "24-Hour"];
const ALBUM_ART_STYLE_OPTIONS = [
  "Full Screen",
  "Letterbox",
  "Standard",
  "None",
];
const MUSIC_OVERLAY_STYLE_OPTIONS = [
  "Art Only",
  "Art + Metadata",
  "Always Visible",
];
const ALBUM_SORT_OPTIONS = [
  "Alphabetical",
  "Newest on Top",
  "Oldest on Top",
];
const ARTIST_ALBUM_SORT_OPTIONS = [
  "Oldest on Top",
  "Newest on Top",
  "Alphabetical",
];
const PODCAST_SORT_OPTIONS = ["Newest on Top", "Oldest on Top"];
const BATCH_CATEGORY_META = [
  { id: "display", title: "Display", defaultOpen: false },
  { id: "interface", title: "Interface", defaultOpen: false },
  { id: "audio", title: "Audio", defaultOpen: true },
  { id: "power", title: "Power", defaultOpen: true },
  { id: "presence", title: "Presence", defaultOpen: false },
  { id: "security", title: "Security", defaultOpen: false },
];
const DEFAULT_ACTIVITY_SOURCES_CSV = ACTIVITY_SOURCES_CATALOG.map((c) => c.token).join(",");
const DEFAULT_HOME_CATEGORIES_CSV = DEFAULT_HOME_CATEGORIES_TOKENS.join(",");
const DEFAULT_AREA_CATEGORIES_CSV = DEFAULT_AREA_CATEGORIES_TOKENS.join(",");
function renderBaselineSelect(
  store,
  groupId,
  key,
  label,
  currentVal,
  options,
  defaultVal,
) {
  const cur = typeof currentVal === "string" && options.includes(currentVal) ? currentVal : defaultVal;
  return renderSettingsRow({
    label,
    control: html`<select
      aria-label=${`${label} for ${groupId}`}
      .value=${cur}
      @change=${(ev) =>
        void store.updateGroupBaseline(groupId, {
          [key]: (ev.currentTarget).value,
        })}
    >
      ${options.map(
        (opt) => html`<option value=${opt} ?selected=${opt === cur}>${opt}</option>`,
      )}
    </select>`,
  });
}
function renderBaselineLabeledSelect(
  store,
  groupId,
  key,
  label,
  currentVal,
  options,
  defaultVal,
) {
  const curStr = currentVal !== undefined && currentVal !== null ? String(currentVal) : defaultVal;
  const cur = options.some((o) => o.value === curStr) ? curStr : defaultVal;
  return renderSettingsRow({
    label,
    control: html`<select
      aria-label=${`${label} for ${groupId}`}
      .value=${cur}
      @change=${(ev) => {
        const raw = (ev.currentTarget).value;
        const val = key === "wallpaper_cycle_minutes" ? Number(raw) || 0 : raw;
        void store.updateGroupBaseline(groupId, { [key]: val });
      }}
    >
      ${options.map(
        (opt) => html`<option value=${opt.value} ?selected=${opt.value === cur}>${opt.label}</option>`,
      )}
    </select>`,
  });
}
function renderBaselineRange(
  store,
  groupId,
  key,
  label,
  currentVal,
  min,
  max,
  step,
  unit,
  defaultVal,
) {
  const numVal = Number.isFinite(Number(currentVal)) ? Number(currentVal) : defaultVal;
  return renderSettingsRow({
    label,
    control: html`<span class="kv-value">${fmtNumber(numVal, store.hass, 0)}${unit ? ` ${unit}` : ""}</span>
      <input
        type="range"
        aria-label=${`${label} for ${groupId}`}
        min=${String(min)}
        max=${String(max)}
        step=${String(step)}
        .value=${String(numVal)}
        @change=${(ev) =>
          void store.updateGroupBaseline(groupId, {
            [key]: Number((ev.currentTarget).value),
          })}
      />`,
  });
}
function renderBaselinePills(
  store,
  groupId,
  key,
  label,
  currentVal,
  catalog,
  defaultCsv,
  minRequired,
) {
  const csvStr = typeof currentVal === "string" ? currentVal : defaultCsv;
  const activeSet = new Set(
    csvStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );
  const toggleTok = (tok) => {
    const next = new Set(activeSet);
    if (next.has(tok)) {
      if (next.size <= minRequired) {
        store.showToast("Keep at least one category enabled", true);
        return;
      }
      next.delete(tok);
    } else {
      next.add(tok);
    }
    const ordered = catalog.map((c) => c.token).filter((t) => next.has(t));
    void store.updateGroupBaseline(groupId, { [key]: ordered.join(",") });
  };
  return renderSettingsRow({
    label,
    control: html`<div class="pill-list">
      ${catalog.map((item) => {
        const on = activeSet.has(item.token);
        return html`<span class="pill ${on ? "enabled" : ""}">
          <button
            type="button"
            aria-pressed=${String(on)}
            @click=${() => toggleTok(item.token)}
            class="pill-toggle"
          >
            ${item.label}
          </button>
        </span>`;
      })}
    </div>`,
  });
}
function renderGroupBaselineDrawer(
  store,
  group,
  latterDevices,
) {
  const gid = group.id;
  const cfg = group.device_config || {};
  const includeDisplay = Boolean(group.include_display);
  const includeInterface = Boolean(group.include_interface);
  const autoBrt = String(cfg.auto_brightness_mode || "Sun Synchronized");
  const wwMode = String(cfg.wake_word_mode || "Docked Only");
  const bleOn = Boolean(cfg.native_ble_tracking);
  const autoSw = cfg.ble_auto_switch !== undefined ? Boolean(cfg.ble_auto_switch) : bleOn;
  const vfm = Boolean(cfg.sync_device_area);
  const handoff = Boolean(cfg.area_handoff);
  const pinPolicy = String(cfg.security_pin_policy || "auto");
  const colorProfile = String(cfg.color_profile || "Steel Blue");
  const customHex =
    typeof cfg.device_custom_color === "string" && /^#[0-9A-Fa-f]{6}$/.test(cfg.device_custom_color)
      ? cfg.device_custom_color.toUpperCase()
      : "#3898FF";
  const copySrc =
    store.groupCopySourceDrafts?.get(gid) ||
    store.activeSubentryId ||
    latterDevices[0]?.subentry_id ||
    "";
  const sysWallpapers = store.state?.system_wallpapers || [];
  const wallpaperOptions = [
    { value: "", label: "None (Weather / Solid)" },
    ...sysWallpapers.map((wp) => ({ value: wp.id, label: wp.name || wp.id })),
  ];
  const rotationOptions = WALLPAPER_ROTATION_OPTIONS.map(
    (o) => ({ value: String(o.value), label: o.label }),
  );
  const remoteGroups = store.state?.system_config?.remote_groups || [];
  const remoteScopeOptions = [
    { value: "area_auto", label: "Match Active Area" },
    ...remoteGroups.map((rg) => ({ value: `group:${rg.id}`, label: `Group: ${rg.name}` })),
    { value: "all", label: "All System Remotes" },
  ];
  const dockCount = Array.isArray(cfg.dock_items) ? cfg.dock_items.length : 7;
  const pinnedCount = Array.isArray(cfg.pinned_items) ? cfg.pinned_items.length : 0;
  const worldClocksStr = typeof cfg.world_clocks === "string" ? cfg.world_clocks.trim() : "";
  const clockCount = worldClocksStr ? worldClocksStr.split(";").filter(Boolean).length : 0;
  return html`<details
    ?open=${Boolean(store.openGroupIds?.has(gid))}
    @toggle=${(ev) => {
      const isOpen = (ev.currentTarget).open;
      if (isOpen) store.openGroupIds?.add(gid);
      else store.openGroupIds?.delete(gid);
    }}
    class="sub-collapsible"
  >
    <summary>Baseline Settings</summary>
    <div class="card-content stack">
      <div class="settings-list">
        ${renderSwitchRow({
          label: "Include Display Settings",
          description: "Enforce wallpapers, clock face, color profile, and media styling for this group.",
          ariaLabel: `Include Display Settings for ${gid}`,
          checked: includeDisplay,
          onChange: (checked) => void store.updateGroupScope(gid, { include_display: checked }),
        })}
        ${renderSwitchRow({
          label: "Include Interface & Shortcuts",
          description: "Enforce start screen, App Dock, pinned shortcuts, and hub categories for this group.",
          ariaLabel: `Include Interface & Shortcuts for ${gid}`,
          checked: includeInterface,
          onChange: (checked) => void store.updateGroupScope(gid, { include_interface: checked }),
        })}
      </div>

      <details class="sub-collapsible" open>
        <summary>Power &amp; Brightness</summary>
        <div class="card-content settings-list">
          ${renderBaselineSelect(
            store,
            gid,
            "tap_to_wake",
            "Tap to Wake",
            cfg.tap_to_wake,
            TAP_TO_WAKE_OPTIONS,
            "Docked Only",
          )}
          ${renderBaselineSelect(
            store,
            gid,
            "pickup_to_wake",
            "Pickup to Wake",
            cfg.pickup_to_wake,
            WAKE_GESTURE_OPTIONS,
            "Docked Only",
          )}
          ${renderBaselineSelect(
            store,
            gid,
            "battery_screen_timeout",
            "Battery Screen Timeout",
            cfg.battery_screen_timeout,
            BATTERY_SCREEN_TIMEOUT_OPTIONS,
            "30s",
          )}
          ${renderBaselineSelect(
            store,
            gid,
            "battery_hibernate_timeout",
            "Battery Hibernate Timeout",
            cfg.battery_hibernate_timeout,
            BATTERY_HIBERNATE_TIMEOUT_OPTIONS,
            "15 min",
          )}
          ${renderSwitchRow({
            label: "Docked Screensaver",
            ariaLabel: `Docked Screensaver for ${gid}`,
            checked: cfg.docked_screensaver !== false,
            onChange: (checked) =>
              void store.updateGroupBaseline(gid, { docked_screensaver: checked }),
          })}
          ${renderBaselineSelect(
            store,
            gid,
            "docked_idle_timeout",
            "Docked Idle Timeout",
            cfg.docked_idle_timeout,
            DOCKED_IDLE_TIMEOUT_OPTIONS,
            "1 min",
          )}
          ${renderSwitchRow({
            label: "Hold Crown to Power Off",
            ariaLabel: `Hold Crown to Power Off for ${gid}`,
            checked: Boolean(cfg.hold_crown_power_off),
            onChange: (checked) =>
              void store.updateGroupBaseline(gid, { hold_crown_power_off: checked }),
          })}
          ${renderBaselineSelect(
            store,
            gid,
            "auto_brightness_mode",
            "Auto Brightness Mode",
            cfg.auto_brightness_mode,
            AUTO_BRIGHTNESS_MODE_OPTIONS,
            "Sun Synchronized",
          )}
          ${autoBrt === "Disabled"
            ? renderBaselineSelect(
                store,
                gid,
                "manual_brightness",
                "Manual Brightness",
                cfg.manual_brightness,
                BRIGHTNESS_PCT_OPTIONS,
                "90%",
              )
            : html`${renderBaselineSelect(
                  store,
                  gid,
                  "day_brightness",
                  "Day Brightness",
                  cfg.day_brightness,
                  BRIGHTNESS_PCT_OPTIONS,
                  "90%",
                )}
                ${renderBaselineSelect(
                  store,
                  gid,
                  "night_brightness",
                  "Night Brightness",
                  cfg.night_brightness,
                  BRIGHTNESS_PCT_OPTIONS,
                  "70%",
                )}`}
          ${autoBrt === "Time Schedule"
            ? html`${renderBaselineRange(
                  store,
                  gid,
                  "day_start_hour",
                  "Day Start Hour",
                  cfg.day_start_hour,
                  0,
                  23,
                  1,
                  "h",
                  7,
                )}
                ${renderBaselineRange(
                  store,
                  gid,
                  "night_start_hour",
                  "Night Start Hour",
                  cfg.night_start_hour,
                  0,
                  23,
                  1,
                  "h",
                  20,
                )}`
            : nothing}
        </div>
      </details>

      <details class="sub-collapsible">
        <summary>Audio &amp; Voice</summary>
        <div class="card-content settings-list">
          ${renderBaselineSelect(
            store,
            gid,
            "wake_word_mode",
            "Wake Word Mode",
            cfg.wake_word_mode,
            WAKE_WORD_MODE_OPTIONS,
            "Docked Only",
          )}
          ${wwMode !== "Disabled"
            ? html`${renderBaselineSelect(
                  store,
                  gid,
                  "ww_sens_okay_nabu",
                  "Okay Nabu Sensitivity",
                  cfg.ww_sens_okay_nabu,
                  WW_SENSITIVITY_OPTIONS,
                  "Moderately sensitive",
                )}
                ${renderBaselineSelect(
                  store,
                  gid,
                  "ww_sens_hey_luna",
                  "Hey Luna Sensitivity",
                  cfg.ww_sens_hey_luna,
                  WW_SENSITIVITY_OPTIONS,
                  "Moderately sensitive",
                )}
                ${renderBaselineSelect(
                  store,
                  gid,
                  "ww_sens_hey_jarvis",
                  "Hey Jarvis Sensitivity",
                  cfg.ww_sens_hey_jarvis,
                  WW_SENSITIVITY_OPTIONS,
                  "Moderately sensitive",
                )}
                ${renderBaselineSelect(
                  store,
                  gid,
                  "ww_sens_hey_mycroft",
                  "Hey Mycroft Sensitivity",
                  cfg.ww_sens_hey_mycroft,
                  WW_SENSITIVITY_OPTIONS,
                  "Moderately sensitive",
                )}
                ${renderBaselineSelect(
                  store,
                  gid,
                  "ww_sens_alexa",
                  "Alexa Sensitivity",
                  cfg.ww_sens_alexa,
                  WW_SENSITIVITY_OPTIONS,
                  "Moderately sensitive",
                )}`
            : nothing}
          ${renderSwitchRow({
            label: "Wake Screen on Assist",
            ariaLabel: `Wake Screen on Assist for ${gid}`,
            checked: cfg.wake_screen_on_assist !== false,
            onChange: (checked) =>
              void store.updateGroupBaseline(gid, { wake_screen_on_assist: checked }),
          })}
          ${renderBaselineRange(store, gid, "alert_volume", "Alert Volume", cfg.alert_volume, 20, 100, 5, "%", 80)}
          ${renderBaselineRange(store, gid, "volume_step_size", "Volume Step Size", cfg.volume_step_size, 1, 10, 1, "%", 5)}
          ${renderSwitchRow({
            label: "Game Sound Effects",
            ariaLabel: `Game Sound Effects for ${gid}`,
            checked: cfg.game_sound_effects !== false,
            onChange: (checked) =>
              void store.updateGroupBaseline(gid, { game_sound_effects: checked }),
          })}
          ${bleOn
            ? html`${renderSwitchRow({
                  label: "Voice Follows Me",
                  ariaLabel: `Voice Follows Me for ${gid}`,
                  checked: vfm,
                  onChange: (checked) =>
                    void store.updateGroupBaseline(gid, { sync_device_area: checked }),
                })}
                ${vfm
                  ? renderBaselineRange(
                      store,
                      gid,
                      "area_follow_dwell_s",
                      "Area Follow Dwell",
                      cfg.area_follow_dwell_s,
                      3,
                      60,
                      1,
                      "s",
                      10,
                    )
                  : nothing}`
            : nothing}
          ${renderSwitchRow({
            label: "Media Follows Device to New Area",
            ariaLabel: `Media Follows Device to New Area for ${gid}`,
            checked: handoff,
            onChange: (checked) => void store.updateGroupBaseline(gid, { area_handoff: checked }),
          })}
        </div>
      </details>

      <details class="sub-collapsible">
        <summary>Presence &amp; Security</summary>
        <div class="card-content settings-list">
          ${renderSwitchRow({
            label: "Track the Area with BLE Proxies",
            ariaLabel: `Track the Area with BLE Proxies for ${gid}`,
            checked: bleOn,
            onChange: (checked) =>
              void store.updateGroupBaseline(gid, { native_ble_tracking: checked }),
          })}
          ${bleOn
            ? html`${renderSwitchRow({
                  label: "Auto-Switch Active Area",
                  ariaLabel: `Auto-Switch Active Area for ${gid}`,
                  checked: autoSw,
                  onChange: (checked) =>
                    void store.updateGroupBaseline(gid, { ble_auto_switch: checked }),
                })}
                ${renderBaselineSelect(
                  store,
                  gid,
                  "ble_beacon_mode",
                  "BLE Beacon Mode",
                  cfg.ble_beacon_mode,
                  BLE_BEACON_MODE_OPTIONS,
                  "Handheld Only",
                )}`
            : nothing}
          ${renderSettingsRow({
            label: "Perimeter Security Policy",
            control: html`<select
              aria-label=${`Perimeter Security Policy for ${gid}`}
              .value=${pinPolicy}
              @change=${(ev) =>
                void store.updateGroupBaseline(gid, {
                  security_pin_policy: (ev.currentTarget).value,
                })}
            >
              ${SECURITY_PIN_POLICY_OPTIONS.map(
                (opt) =>
                  html`<option value=${opt.value} ?selected=${opt.value === pinPolicy}>
                    ${opt.label}
                  </option>`,
              )}
            </select>`,
          })}
        </div>
      </details>

      ${includeDisplay
        ? html`<details class="sub-collapsible" open>
            <summary>Display</summary>
            <div class="card-content settings-list">
              ${renderBaselineLabeledSelect(
                store,
                gid,
                "wallpaper_source",
                "Wallpaper",
                cfg.wallpaper_source,
                wallpaperOptions,
                "",
              )}
              ${renderBaselineLabeledSelect(
                store,
                gid,
                "wallpaper_cycle_minutes",
                "Wallpaper Rotation",
                cfg.wallpaper_cycle_minutes,
                rotationOptions,
                "0",
              )}
              ${renderBaselineSelect(
                store,
                gid,
                "screensaver_style",
                "Screensaver Style",
                cfg.screensaver_style,
                SCREENSAVER_STYLE_OPTIONS,
                "Ambient Clock",
              )}
              ${renderBaselineSelect(
                store,
                gid,
                "color_profile",
                "Color Profile",
                cfg.color_profile,
                COLOR_PROFILE_OPTIONS,
                "Steel Blue",
              )}
              ${colorProfile === "Custom"
                ? renderSettingsRow({
                    label: "Custom Accent Color",
                    control: html`<input
                        type="color"
                        aria-label=${`Custom Accent Color for ${gid}`}
                        .value=${customHex}
                        @change=${(ev) =>
                          void store.updateGroupBaseline(gid, {
                            device_custom_color: (
                              ev.currentTarget
                            ).value.toUpperCase(),
                          })}
                      />
                      <span class="chip">${customHex}</span>`,
                  })
                : nothing}
              ${renderBaselineSelect(
                store,
                gid,
                "va_visual_profile",
                "Visual Profile",
                cfg.va_visual_profile,
                VA_VISUAL_PROFILE_OPTIONS,
                "Nebula",
              )}
              ${renderBaselineSelect(
                store,
                gid,
                "clock_face",
                "Clock Face",
                cfg.clock_face,
                CLOCK_FACE_OPTIONS,
                "Minimal Digital",
              )}
              ${renderBaselineSelect(
                store,
                gid,
                "time_format",
                "Time Format",
                cfg.time_format,
                TIME_FORMAT_OPTIONS,
                "12-Hour (AM/PM)",
              )}
              ${renderSwitchRow({
                label: "Weather Background",
                ariaLabel: `Weather Background for ${gid}`,
                checked: cfg.weather_background !== false,
                onChange: (checked) =>
                  void store.updateGroupBaseline(gid, { weather_background: checked }),
              })}
              ${renderSwitchRow({
                label: "Sun",
                ariaLabel: `Sun for ${gid}`,
                checked: cfg.home_sun !== false,
                onChange: (checked) => void store.updateGroupBaseline(gid, { home_sun: checked }),
              })}
              ${renderSwitchRow({
                label: "Moon",
                ariaLabel: `Moon for ${gid}`,
                checked: cfg.home_moon !== false,
                onChange: (checked) => void store.updateGroupBaseline(gid, { home_moon: checked }),
              })}
              ${renderSwitchRow({
                label: "Wake Greeting",
                ariaLabel: `Wake Greeting for ${gid}`,
                checked: cfg.wake_greeting !== false,
                onChange: (checked) =>
                  void store.updateGroupBaseline(gid, { wake_greeting: checked }),
              })}
              ${renderBaselineSelect(
                store,
                gid,
                "album_art_style",
                "Album Art Style",
                cfg.album_art_style,
                ALBUM_ART_STYLE_OPTIONS,
                "Full Screen",
              )}
              ${renderBaselineSelect(
                store,
                gid,
                "music_overlay_style",
                "Overlay Style",
                cfg.music_overlay_style,
                MUSIC_OVERLAY_STYLE_OPTIONS,
                "Art + Metadata",
              )}
            </div>
          </details>`
        : nothing}

      ${includeInterface
        ? html`<details class="sub-collapsible" open>
            <summary>Interface &amp; Shortcuts</summary>
            <div class="card-content settings-list">
              ${renderSwitchRow({
                label: "Enable Home Screen",
                ariaLabel: `Enable Home Screen for ${gid}`,
                checked: cfg.home_screen_enabled !== false,
                onChange: (checked) =>
                  void store.updateGroupBaseline(gid, { home_screen_enabled: checked }),
              })}
              ${renderBaselineSelect(
                store,
                gid,
                "start_screen",
                "Start Screen",
                cfg.start_screen,
                START_SCREEN_OPTIONS,
                "Home",
              )}
              ${renderBaselineSelect(
                store,
                gid,
                "home_clock_tap_action",
                "Home Time Tap",
                cfg.home_clock_tap_action,
                HOME_CLOCK_TAP_OPTIONS,
                "Time App",
              )}
              ${renderBaselineSelect(
                store,
                gid,
                "return_to_home_timeout",
                "Return to Home Timeout",
                cfg.return_to_home_timeout,
                RETURN_TO_HOME_TIMEOUT_OPTIONS,
                "2 min",
              )}
              ${renderSwitchRow({
                label: "Home Activity Card",
                ariaLabel: `Home Activity Card for ${gid}`,
                checked: cfg.activity_card !== false,
                onChange: (checked) =>
                  void store.updateGroupBaseline(gid, { activity_card: checked }),
              })}
              ${renderBaselinePills(
                store,
                gid,
                "activity_sources",
                "Activity Card Sources",
                cfg.activity_sources,
                ACTIVITY_SOURCES_CATALOG,
                DEFAULT_ACTIVITY_SOURCES_CSV,
                0,
              )}
              ${renderBaselinePills(
                store,
                gid,
                "home_categories",
                "Home Hub Categories",
                cfg.home_categories,
                HOME_CATEGORIES_CATALOG,
                DEFAULT_HOME_CATEGORIES_CSV,
                1,
              )}
              ${renderBaselinePills(
                store,
                gid,
                "area_categories",
                "Area Control Categories",
                cfg.area_categories,
                AREA_CATEGORIES_CATALOG,
                DEFAULT_AREA_CATEGORIES_CSV,
                1,
              )}
              ${renderBaselineLabeledSelect(
                store,
                gid,
                "device_remote_group",
                "Remote Control Scope",
                cfg.device_remote_group,
                remoteScopeOptions,
                "area_auto",
              )}
              ${renderSwitchRow({
                label: "Show UTC Clock",
                ariaLabel: `Show UTC Clock for ${gid}`,
                checked: Boolean(cfg.show_utc_clock),
                onChange: (checked) =>
                  void store.updateGroupBaseline(gid, { show_utc_clock: checked }),
              })}
              ${renderSwitchRow({
                label: "Show Speaker Shortcut",
                ariaLabel: `Show Speaker Shortcut for ${gid}`,
                checked: cfg.show_speaker_shortcut !== false,
                onChange: (checked) =>
                  void store.updateGroupBaseline(gid, { show_speaker_shortcut: checked }),
              })}
              ${renderSwitchRow({
                label: "Show Library Shortcut",
                ariaLabel: `Show Library Shortcut for ${gid}`,
                checked: cfg.show_library_shortcut !== false,
                onChange: (checked) =>
                  void store.updateGroupBaseline(gid, { show_library_shortcut: checked }),
              })}
              ${renderBaselineSelect(
                store,
                gid,
                "album_sort_order",
                "Album Sort Order",
                cfg.album_sort_order,
                ALBUM_SORT_OPTIONS,
                "Alphabetical",
              )}
              ${renderBaselineSelect(
                store,
                gid,
                "artist_album_sort_order",
                "Artist Album Sort Order",
                cfg.artist_album_sort_order,
                ARTIST_ALBUM_SORT_OPTIONS,
                "Oldest on Top",
              )}
              ${renderBaselineSelect(
                store,
                gid,
                "podcast_sort_order",
                "Podcast Sort Order",
                cfg.podcast_sort_order,
                PODCAST_SORT_OPTIONS,
                "Newest on Top",
              )}
              ${latterDevices.length
                ? html`${renderSettingsRow({
                      label: "App Dock",
                      description: `Baseline holds ${fmtNumber(dockCount, store.hass, 0)} shortcut${dockCount === 1 ? "" : "s"} (captures from Source Device below).`,
                      control: html`<button
                        type="button"
                        @click=${() =>
                          void store.copyDeviceToGroupBaseline(gid, copySrc, ["dock_items"])}
                        class="btn btn-secondary btn-compact"
                      >
                        Copy Dock
                      </button>`,
                    })}
                    ${renderSettingsRow({
                      label: "Pinned Shortcuts",
                      description: `Baseline holds ${fmtNumber(pinnedCount, store.hass, 0)} shortcut${pinnedCount === 1 ? "" : "s"} (captures from Source Device below).`,
                      control: html`<button
                        type="button"
                        @click=${() =>
                          void store.copyDeviceToGroupBaseline(gid, copySrc, ["pinned_items"])}
                        class="btn btn-secondary btn-compact"
                      >
                        Copy Pinned
                      </button>`,
                    })}
                    ${renderSettingsRow({
                      label: "World Clocks",
                      description: `Baseline holds ${fmtNumber(clockCount, store.hass, 0)} zone${clockCount === 1 ? "" : "s"} (captures from Source Device below).`,
                      control: html`<button
                        type="button"
                        @click=${() =>
                          void store.copyDeviceToGroupBaseline(gid, copySrc, ["world_clocks"])}
                        class="btn btn-secondary btn-compact"
                      >
                        Copy Clocks
                      </button>`,
                    })}`
                : nothing}
            </div>
          </details>`
        : nothing}

      ${latterDevices.length
        ? html`<div class="settings-list">
            <div class="subsection-title">Copy From Device</div>
            ${renderSettingsRow({
              label: "Source Device",
              description:
                "Replaces this group's active baseline scope with an existing Device's settings.",
              control: html`<select
                  aria-label=${`Copy settings into ${group.name}`}
                  .value=${copySrc}
                  @change=${(ev) => {
                    store.groupCopySourceDrafts?.set(
                      gid,
                      (ev.currentTarget).value,
                    );
                    store.host.requestUpdate();
                  }}
                >
                  ${latterDevices.map(
                    (d) =>
                      html`<option value=${d.subentry_id} ?selected=${d.subentry_id === copySrc}>
                        ${d.title}
                      </option>`,
                  )}
                </select>
                <button
                  type="button"
                  @click=${() => void store.copyDeviceToGroupBaseline(gid, copySrc)}
                  class="btn btn-secondary btn-compact"
                >
                  Copy Settings
                </button>`,
            })}
          </div>`
        : nothing}
    </div>
  </details>`;
}
function matchesBatchTargetFilter(
  filter,
  item,
) {
  if (filter === "all") return true;
  if (filter === "online") return Boolean(item.is_online);
  if (filter === "roaming") return Boolean(item.is_roaming);
  if (filter === "stationary") return !item.is_roaming;
  const grpId = filter.startsWith("group:") ? filter.slice(6) : filter;
  return (item.device_group || "custom") === grpId;
}
function renderSystemGroupsView(store) {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const latterDevices = allDevices.filter((d) => d.kind !== "ble_tag");
  const groups = data?.device_groups || [];
  const systemControls = data?.system_controls || [];
  const validTargetFilters = new Set ([
    "all",
    "online",
    "roaming",
    "stationary",
    "group:custom",
    ...groups.map((g) => `group:${g.id}`),
  ]);
  const activeFilter = validTargetFilters.has(store.batchTargetFilter || "all")
    ? store.batchTargetFilter || "all"
    : "all";
  const activeCat = store.batchCategoryFilter || "all";
  const selectedTargetName =
    activeFilter === "all"
      ? "All Latter Devices"
      : activeFilter === "online"
        ? "Online Devices"
        : activeFilter === "roaming"
          ? "Roaming Devices"
          : activeFilter === "stationary"
            ? "Stationary Devices"
            : activeFilter === "group:custom"
              ? "Custom"
              : groups.find((g) => `group:${g.id}` === activeFilter)?.name ||
                activeFilter.replace(/^group:/, "");
  const matchingDevs = latterDevices.filter((d) => matchesBatchTargetFilter(activeFilter, d));
  const batchCopySrc =
    store.batchCopySourceSubentryId ||
    store.activeSubentryId ||
    latterDevices[0]?.subentry_id ||
    "";
  const renderBatchControlRow = (fc) => {
    const targets = (fc.targets || []).filter((t) =>
      matchesBatchTargetFilter(activeFilter, t),
    );
    if (!targets.length) return nothing;
    const states = Array.from(new Set(targets.map((t) => String(t.state ?? ""))));
    const mixed = states.length > 1;
    const curState = mixed ? "" : (states[0] ?? "");
    const desc = `${fc.section_title} • ${fmtNumber(targets.length, store.hass, 0)} Device${targets.length === 1 ? "" : "s"}${mixed ? " • Mixed values" : ""}`;
    const optLabels = fc.option_labels || {};
    let control;
    if (fc.domain === "select" && fc.options && fc.options.length) {
      control = html`<select
        aria-label=${fc.name}
        .value=${curState}
        @change=${(ev) =>
          void store.bulkSelect(fc, (ev.currentTarget).value)}
      >
        ${mixed ? html`<option value="__mixed__" selected disabled>Mixed</option>` : nothing}
        ${fc.options.map(
          (opt) =>
            html`<option value=${opt} ?selected=${!mixed && opt === curState}>
              ${optLabels[opt] || opt}
            </option>`,
        )}
      </select>`;
    } else if (fc.domain === "switch") {
      control = html`${mixed ? html`<span class="chip">Mixed</span>` : nothing}
        <input
          type="checkbox"
          role="switch"
          aria-label=${fc.name}
          .checked=${curState === "on"}
          @change=${(ev) =>
            void store.bulkToggle(fc, (ev.currentTarget).checked)}
          class="switch"
        />`;
    } else if (fc.domain === "number") {
      const numVal = mixed ? (fc.min ?? 0) : Number(curState) || 0;
      control = html`<input
          type="range"
          aria-label=${fc.name}
          min=${String(fc.min ?? 0)}
          max=${String(fc.max ?? 100)}
          step=${String(fc.step ?? 1)}
          .value=${String(numVal)}
          @change=${(ev) =>
            void store.bulkNumber(fc, Number((ev.currentTarget).value))}
        />
        <span class="chip">
          ${mixed ? "Mixed" : `${curState} ${fc.unit || ""}`.trim()}
        </span>`;
    } else if (fc.domain === "color") {
      const hexVal = /^#[0-9A-Fa-f]{6}$/.test(curState) ? curState.toUpperCase() : "#3898FF";
      control = html`<input
          type="color"
          aria-label=${fc.name}
          .value=${hexVal}
          @change=${(ev) =>
            void store.bulkColor(fc, (ev.currentTarget).value)}
        />
        <span class="chip">${mixed ? "Mixed" : hexVal}</span>`;
    } else if (fc.domain === "pills" && fc.options && fc.options.length) {
      const baseCsv = mixed ? (states[0] ?? "") : curState;
      const activeSet = new Set(
        baseCsv
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      );
      control = html`<div class="pill-list">
        ${mixed ? html`<span class="chip">Mixed</span>` : nothing}
        ${fc.options.map((tok) => {
          const on = !mixed && activeSet.has(tok);
          return html`<span class="pill ${on ? "enabled" : ""}">
            <button
              type="button"
              aria-pressed=${String(on)}
              @click=${() => void store.bulkPillsToggle(fc, tok, baseCsv)}
              class="pill-toggle"
            >
              ${optLabels[tok] || tok}
            </button>
          </span>`;
        })}
      </div>`;
    } else {
      control = html`<span class="chip">${mixed ? "Mixed" : curState}</span>`;
    }
    return renderSettingsRow({ label: entityLabel(fc.name), description: desc, control });
  };
  const renderBatchCopyListsSection = () => {
    if (!latterDevices.length || !matchingDevs.some((d) => d.has_display !== false)) {
      return nothing;
    }
    return html`<div class="settings-list">
      <div class="subsection-title">Copy Multi-Item Lists</div>
      ${renderSettingsRow({
        label: "Template Device",
        description: `Copies App Dock, Pinned Shortcuts, or World Clocks to ${selectedTargetName}.`,
        control: html`<select
          id="batch-copy-source"
          aria-label="Template Device for batch list copy"
          .value=${batchCopySrc}
          @change=${(ev) => {
            store.batchCopySourceSubentryId = (ev.currentTarget).value;
            store.host.requestUpdate();
          }}
        >
          ${latterDevices.map(
            (d) =>
              html`<option value=${d.subentry_id} ?selected=${d.subentry_id === batchCopySrc}>
                ${d.title}
              </option>`,
          )}
        </select>`,
      })}
      <div class="input-action-row">
        <button
          type="button"
          @click=${() => void store.applyBatchCopyFromDevice(batchCopySrc, ["dock_items"])}
          class="btn btn-secondary btn-compact"
        >
          Push App Dock
        </button>
        <button
          type="button"
          @click=${() => void store.applyBatchCopyFromDevice(batchCopySrc, ["pinned_items"])}
          class="btn btn-secondary btn-compact"
        >
          Push Pinned Shortcuts
        </button>
        <button
          type="button"
          @click=${() => void store.applyBatchCopyFromDevice(batchCopySrc, ["world_clocks"])}
          class="btn btn-secondary btn-compact"
        >
          Push World Clocks
        </button>
      </div>
    </div>`;
  };
  return html`<section id="view-system_sync">
    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-device-groups",
          title: "Device Groups",
          subtitle:
            "Built-in hardware presets and custom Device Groups that keep assigned Devices aligned.",
          contentClass: "stack",
          body: html`<div class="list-block">
              <div class="list-row-main">
                <div class="stacked-field">
                  <label for="new-group-name">Group Name</label>
                  <input
                    type="text"
                    id="new-group-name"
                    placeholder="e.g. Guest Suites"
                    .value=${store.newGroupName}
                    @input=${(ev) => {
                      store.newGroupName = (ev.currentTarget).value;
                    }}
                  />
                </div>
                <div class="stacked-field">
                  <label for="new-group-desc">Description (Optional)</label>
                  <input
                    type="text"
                    id="new-group-desc"
                    placeholder="Optional description"
                    .value=${store.newGroupDesc}
                    @input=${(ev) => {
                      store.newGroupDesc = (ev.currentTarget).value;
                    }}
                  />
                </div>
              </div>
              <div class="pill-list">
                <span class="pill ${store.newGroupIncludeDisplay ? "enabled" : ""}">
                  <button
                    type="button"
                    aria-pressed=${String(Boolean(store.newGroupIncludeDisplay))}
                    @click=${() => {
                      store.newGroupIncludeDisplay = !store.newGroupIncludeDisplay;
                      store.host.requestUpdate();
                    }}
                    class="pill-toggle"
                  >
                    Include Display Settings
                  </button>
                </span>
                <span class="pill ${store.newGroupIncludeInterface ? "enabled" : ""}">
                  <button
                    type="button"
                    aria-pressed=${String(Boolean(store.newGroupIncludeInterface))}
                    @click=${() => {
                      store.newGroupIncludeInterface = !store.newGroupIncludeInterface;
                      store.host.requestUpdate();
                    }}
                    class="pill-toggle"
                  >
                    Include Interface &amp; Shortcuts
                  </button>
                </span>
              </div>
              <div class="input-action-row">
                <select
                  id="new-group-source"
                  aria-label="Copy settings from Device"
                  .value=${store.newGroupSourceSubentryId}
                  @change=${(ev) => {
                    store.newGroupSourceSubentryId = (ev.currentTarget).value;
                  }}
                >
                  <option value="" ?selected=${!store.newGroupSourceSubentryId}>
                    Start from default settings
                  </option>
                  ${latterDevices.map(
                    (d) =>
                      html`<option
                        value=${d.subentry_id}
                        ?selected=${d.subentry_id === store.newGroupSourceSubentryId}
                      >
                        Copy from: ${d.title}
                      </option>`,
                  )}
                </select>
                <button
                  type="button"
                  id="btn-create-device-group"
                  @click=${() => void store.createDeviceGroup()}
                  class="btn btn-primary"
                >
                  Create Group
                </button>
              </div>
            </div>

            <div id="device-groups-list" class="stack">
              ${groups.length
                ? repeat(
                    groups,
                    (g) => g.id,
                    (g) => {
                      const members = latterDevices.filter((d) => d.device_group === g.id);
                      const isDefault =
                        DEFAULT_DEVICE_GROUP_IDS.has(g.id) || Boolean(g.builtin);
                      const metaParts = [
                        g.description || "",
                        members.length
                          ? `Devices: ${members.map((m) => m.title).join(", ")}`
                          : "No Devices assigned",
                      ].filter(Boolean);
                      return html`<div id=${`group-box-${g.id}`} class="area-presence-box">
                        <div class="area-box-head">
                          <div class="area-box-heading">
                            <span class="area-box-title">${g.name}</span>
                            <span class="chip ${members.length ? "chip-primary" : ""}">
                              ${fmtNumber(members.length, store.hass, 0)}
                              ${members.length === 1 ? "Device" : "Devices"}
                            </span>
                            ${g.include_display
                              ? html`<span class="chip">Display</span>`
                              : nothing}
                            ${g.include_interface
                              ? html`<span class="chip">Interface</span>`
                              : nothing}
                          </div>
                          <div class="area-box-actions">
                            ${members.length
                              ? html`<button
                                  type="button"
                                  @click=${() => store.openDevicesWithCategory(`group:${g.id}`)}
                                  class="btn btn-text btn-compact"
                                >
                                  View Devices
                                </button>`
                              : nothing}
                            ${!isDefault
                              ? renderTrashIconButton(`Delete group ${g.name}`, () =>
                                  void store.deleteDeviceGroup(g.id),
                                )
                              : nothing}
                          </div>
                        </div>

                        <div class="area-box-meta">${metaParts.join(" • ")}</div>

                        ${renderGroupBaselineDrawer(store, g, latterDevices)}
                      </div>`;
                    },
                  )
                : html`<p class="empty-state">No Device Groups configured.</p>`}
            </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-batch-controls",
          title: "Batch Controls",
          subtitle:
            "Applies a one-time setting change across matching Devices without altering saved Group baselines.",
          headerActions: html`<select
              id="batch-target-filter"
              aria-label="Target Devices for Batch Controls"
              .value=${activeFilter}
              @change=${(ev) => {
                store.batchTargetFilter =
                  (ev.currentTarget).value || "all";
                store.host.requestUpdate();
              }}
            >
              <option value="all" ?selected=${activeFilter === "all"}>All Latter Devices</option>
              <option value="online" ?selected=${activeFilter === "online"}>Online Devices</option>
              <option value="roaming" ?selected=${activeFilter === "roaming"}>Roaming Devices</option>
              <option value="stationary" ?selected=${activeFilter === "stationary"}>
                Stationary Devices
              </option>
              ${groups.map(
                (g) =>
                  html`<option
                    value=${`group:${g.id}`}
                    ?selected=${activeFilter === `group:${g.id}`}
                  >
                    ${g.name}
                  </option>`,
              )}
              <option value="group:custom" ?selected=${activeFilter === "group:custom"}>
                Custom
              </option>
            </select>
            <select
              id="batch-cat-filter"
              aria-label="Filter Batch Controls by category"
              .value=${activeCat}
              @change=${(ev) => {
                store.batchCategoryFilter =
                  (ev.currentTarget).value || "all";
                store.host.requestUpdate();
              }}
            >
              <option value="all" ?selected=${activeCat === "all"}>All Categories</option>
              ${BATCH_CATEGORY_META.map(
                (cat) =>
                  html`<option value=${cat.id} ?selected=${activeCat === cat.id}>
                    ${cat.title}
                  </option>`,
              )}
            </select>`,
          contentClass: "stack",
          body: !matchingDevs.length
            ? html`<p class="empty-state">
                ${activeFilter === "all"
                  ? "No Latter Devices onboarded yet."
                  : `No Latter Devices currently match ${selectedTargetName}.`}
              </p>`
            : html`<div class="help-text">
                  Target (${fmtNumber(matchingDevs.length, store.hass, 0)}): ${matchingDevs.map((d) => d.title).join(", ")}
                </div>

                <div id="system-controls-list" class="stack">
                  ${activeCat === "all"
                    ? BATCH_CATEGORY_META.map((cat) => {
                        const rows = systemControls
                          .filter((fc) => fc.section === cat.id)
                          .map((fc) => renderBatchControlRow(fc))
                          .filter((row) => row !== nothing);
                        const copyBlock =
                          cat.id === "interface" ? renderBatchCopyListsSection() : nothing;
                        if (!rows.length && copyBlock === nothing) return nothing;
                        return html`<details
                          class="sub-collapsible"
                          ?open=${cat.defaultOpen}
                        >
                          <summary>${cat.title}</summary>
                          <div class="card-content stack">
                            ${rows.length
                              ? html`<div class="settings-list">${rows}</div>`
                              : nothing}
                            ${copyBlock}
                          </div>
                        </details>`;
                      })
                    : (() => {
                        const rows = systemControls
                          .filter((fc) => fc.section === activeCat)
                          .map((fc) => renderBatchControlRow(fc))
                          .filter((row) => row !== nothing);
                        const copyBlock =
                          activeCat === "interface" ? renderBatchCopyListsSection() : nothing;
                        if (!rows.length && copyBlock === nothing) {
                          return html`<p class="empty-state">
                            No batch controls match this category.
                          </p>`;
                        }
                        return html`${rows.length
                          ? html`<div class="settings-list">${rows}</div>`
                          : nothing}
                        ${copyBlock}`;
                      })()}
                </div>`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/system-overview-view.ts ---
/**
 * System Overview View (`system_overview`): Active Repairs/Issues, System Summary & Configured Items.
 */
function renderSystemOverviewView(store) {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const issues = data?.issues || [];
  const groups = data?.device_groups || [];
  const sysCfg = data?.system_config;
  const onlineCount = allDevices.filter((d) => d.is_online).length;
  const nativeCount = allDevices.filter((d) => d.is_latter_native).length;
  const bleTrackedCount = allDevices.filter((d) => d.ble_tracked).length;
  const assignedPeopleCount = allDevices.filter((d) => d.assigned_person).length;
  const verText = data?.version ? `v${String(data.version).replace(/^v/i, "")}` : "—";
  const remotesCount = (sysCfg?.remotes_list || []).filter(Boolean).length;
  const volCount = (sysCfg?.volume_overrides || []).length;
  const camerasCount = (sysCfg?.camera_entities || []).filter(Boolean).length;
  const calendarsCount = (sysCfg?.calendar_entities || []).filter(Boolean).length;
  const colorsCount = (sysCfg?.custom_palettes || []).length;
  const wallpapersCount = (data?.system_wallpapers || []).length;
  const groupsLabel = `${groups.length} group${groups.length === 1 ? "" : "s"}`;
  const makeRow = (label, value, onOpen) => html`<button
    type="button"
    @click=${onOpen}
    class="kv-row"
  >
    <span>${label}</span>
    <strong>${value}</strong>
  </button>`;
  return html`<section id="view-system_overview">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Issues",
          headerActions: html`<button
            type="button"
            @click=${() => store.openHaPage("/config/repairs")}
            class="btn btn-secondary btn-compact"
          >
            Open Repairs
          </button>`,
          contentClass: "settings-list",
          body: issues.length
            ? issues.map((iss) => {
                const isErr = iss.severity === "error" || iss.severity === "critical";
                return renderSettingsRow({
                  labelHtml: html`<span class="row-label">
                    ${iss.device_title || "Latter"}
                    <span class="chip ${isErr ? "chip-error" : "chip-warning"}">
                      ${iss.severity === "warning" ? "Warning" : "Error"}
                    </span>
                  </span>`,
                  description: issueMessage(iss),
                  control: iss.subentry_id
                    ? html`<button
                        type="button"
                        @click=${() => void store.switchSystemDevice(String(iss.subentry_id))}
                        class="btn btn-text btn-compact"
                      >
                        Open Device
                      </button>`
                    : nothing,
                });
              })
            : html`<p class="empty-state">No issues.</p>`,
        })}

        ${renderCard({
          title: "System",
          headerActions: html`<button
            type="button"
            @click=${() => void store.checkSystemUpdates()}
            class="btn btn-secondary btn-compact"
          >
            Check Firmware Updates
          </button>`,
          body: html`<div class="kv-list">
            <div class="kv-row">
              <span>Integration Version</span>
              <strong>${verText}</strong>
            </div>
            ${makeRow(
              "Devices Online",
              `${fmtNumber(onlineCount, store.hass, 0)} / ${fmtNumber(allDevices.length, store.hass, 0)}`,
              () => store.openDevicesWithCategory("online"),
            )}
            ${makeRow("Latter Displays", fmtNumber(nativeCount, store.hass, 0), () =>
              store.openDevicesWithCategory("native"),
            )}
            ${makeRow("BLE Tracked Devices", fmtNumber(bleTrackedCount, store.hass, 0), () =>
              store.openDevicesWithCategory("ble_tracked"),
            )}
            ${makeRow("Assigned People", fmtNumber(assignedPeopleCount, store.hass, 0), () =>
              store.openDevicesWithCategory("assigned_person"),
            )}
            ${makeRow("Area BLE Proxies", fmtNumber(data?.ble_proxy_count, store.hass, 0), () =>
              store.openSystemSection("area_tracking"),
            )}
          </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "Configured Items",
          body: html`<div class="kv-list">
            ${makeRow("Device Groups", groupsLabel, () => store.openSystemSection("system_sync"))}
            ${makeRow("Cameras", fmtNumber(camerasCount, store.hass, 0), () =>
              store.openSystemSection("shared_entities", "card-cameras-doorbell"),
            )}
            ${makeRow("Calendars", fmtNumber(calendarsCount, store.hass, 0), () =>
              store.openSystemSection("shared_entities", "card-calendars"),
            )}
            ${makeRow("Remote Controls", fmtNumber(remotesCount, store.hass, 0), () =>
              store.openSystemSection("remotes"),
            )}
            ${makeRow("Volume Overrides", fmtNumber(volCount, store.hass, 0), () =>
              store.openSystemSection("remotes", "card-volume-overrides"),
            )}
            ${makeRow("Custom Colors", fmtNumber(colorsCount, store.hass, 0), () =>
              store.openSystemSection("shared_entities", "card-custom-colors"),
            )}
            ${makeRow("Wallpapers", fmtNumber(wallpapersCount, store.hass, 0), () =>
              store.openSystemSection("shared_entities", "card-system-wallpapers"),
            )}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/system-presence-view.ts ---
/**
 * System BLE & Area Presence View (`area_tracking`, `D-044` / `D-045` / `D-046`):
 * Area Presence & Sensors, Walk-Around BLE Calibration, and Advanced BLE Settings.
 */
const FUSION_MODE_OPTIONS = [
  { val: "weighted", label: "Weighted (BLE and sensors)" },
  { val: "any_or", label: "Either (BLE or a sensor)" },
  { val: "ble_only", label: "BLE only" },
  { val: "ble_and_sensor", label: "Both (BLE and a sensor)" },
];
function renderSystemPresenceView(store) {
  const data = store.state;
  const sysCfg = data?.system_config;
  const presenceRows = data?.live?.area_presence_grid || [];
  const signatures = data?.ble_area_signatures || [];
  const allDevs = data?.system_devices || [];
  const bleDevs = allDevs.filter((d) => d.ble_tracked || d.kind === "ble_tag");
  const activeSurveyDev = store.getActiveSurveyDevice() || bleDevs[0];
  const surveyRows = activeSurveyDev?.ble_survey_rows || [];
  const packetsSeen = activeSurveyDev?.ble_packets_seen ?? 0;
  const sigByArea = new Map();
  for (const sig of signatures) {
    if (sig.area_id) sigByArea.set(sig.area_id, sig);
  }
  const rowByArea = new Map();
  for (const row of presenceRows) {
    if (row.area_id) rowByArea.set(row.area_id, row);
  }
  const unifiedAreas
     = [];
  for (const row of presenceRows) {
    unifiedAreas.push({
      areaId: row.area_id,
      areaName: row.area_name,
      row,
      sig: sigByArea.get(row.area_id),
    });
  }
  for (const sig of signatures) {
    if (!rowByArea.has(sig.area_id)) {
      unifiedAreas.push({
        areaId: sig.area_id,
        areaName: sig.area_name,
        row: undefined,
        sig,
      });
    }
  }
  unifiedAreas.sort((a, b) =>
    a.areaName.localeCompare(b.areaName, undefined, { sensitivity: "base" }),
  );
  const areaChoices = signatures.length
    ? signatures.map((s) => ({ area_id: s.area_id, area_name: s.area_name }))
    : (data?.catalog?.areas || []).map((a) => ({ area_id: a.id, area_name: a.name }));
  const targetAreaId =
    store.bleCalibrateAreaId && areaChoices.some((a) => a.area_id === store.bleCalibrateAreaId)
      ? store.bleCalibrateAreaId
      : areaChoices[0]?.area_id || "";
  const selectedSig = sigByArea.get(targetAreaId);
  const selectedAreaName =
    selectedSig?.area_name ||
    areaChoices.find((a) => a.area_id === targetAreaId)?.area_name ||
    "this Area";
  const calibrateDescription = !areaChoices.length
    ? "Create at least one Home Assistant Area before capturing a Bluetooth signature."
    : selectedSig?.has_signature
      ? `Replaces the saved ${fmtNumber(selectedSig.scanner_count, store.hass, 0)}-proxy signature for ${selectedAreaName} using recent live Bluetooth readings.`
      : selectedSig && !selectedSig.has_ble_proxy
        ? `Captures readings from surrounding Bluetooth proxies so ${selectedAreaName} detects presence without a local proxy.`
        : `Captures a multi-proxy signal vector for ${selectedAreaName} to sharpen Area boundaries over single-proxy distance.`;
  const hasFreshSignal = surveyRows.some(
    (r) => Boolean(r.is_fresh) && r.effective_rssi !== null && r.effective_rssi !== undefined,
  );
  return html`<section id="view-area_tracking">
    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-area-presence",
          title: "Area Presence & Sensors",
          subtitle: "Configures how each Area combines Bluetooth tracking and occupancy sensors.",
          body: html`<div id="area-presence-grid-box" class="stack">
            ${unifiedAreas.length
              ? repeat(
                  unifiedAreas,
                  (item) => item.areaId,
                  ({ areaId, areaName, row, sig }) => {
                    const isOcc = Boolean(row?.is_occupied);
                    const confPct = row?.confidence_pct ?? 100;
                    const floorLabel = String(
                      row?.floor_name || row?.floor_id || sig?.floor_id || "",
                    ).trim();
                    const hasBleProxy = sig
                      ? Boolean(sig.has_ble_proxy)
                      : Boolean(
                          (row?.winning_rssi !== null && row?.winning_rssi !== undefined) ||
                            surveyRows.some((sr) => sr.area_id === areaId),
                        );
                    const occList = row?.occupant_names || [];
                    const occNames = occList.length
                      ? occList.join(", ")
                      : isOcc
                        ? "Occupied (sensor)"
                        : "Empty";
                    const parts = [occNames];
                    if (row?.winning_rssi !== null && row?.winning_rssi !== undefined) {
                      const distPart =
                        row.closest_distance_m !== null && row.closest_distance_m !== undefined
                          ? ` (~${fmtDistance(row.closest_distance_m, store.hass, row.closest_distance_ft)})`
                          : "";
                      parts.push(`BLE ${fmtNumber(row.winning_rssi, store.hass, 0)} dBm${distPart}`);
                    }
                    if (row?.match_method === "signature") {
                      parts.push("signature match");
                    }
                    if (row?.active_sensors && row.active_sensors.length) {
                      parts.push(
                        `${row.active_sensors.length} active sensor${row.active_sensors.length > 1 ? "s" : ""}`,
                      );
                    } else if (row?.available_sensors && row.available_sensors.length) {
                      parts.push(
                        `${row.available_sensors.length} sensor${row.available_sensors.length > 1 ? "s" : ""} clear`,
                      );
                    }
                    if (sig?.has_signature && sig.captured_at) {
                      parts.push(
                        `calibrated ${fmtDateTime(sig.captured_at, store.hass)} (${fmtNumber(sig.sample_count, store.hass, 0)} samples)`,
                      );
                    } else if (!hasBleProxy && !sig?.has_signature) {
                      parts.push("calibrate with a carried Device to detect BLE presence here");
                    }
                    const curMode = row?.fusion_mode || "weighted";
                    const threshold = Number(row?.fusion_threshold_pct ?? 50);
                    const chosen = row?.fusion_sensors || [];
                    const choices = row?.fusion_sensor_choices || [];
                    const thresholdId = `fusion-threshold-${areaId}`;
                    return html`<div class="area-presence-box">
                      <div class="area-box-head">
                        <div class="area-box-heading">
                          <span class="area-box-title">${areaName}</span>
                          ${isOcc
                            ? html`<span class="chip chip-success">Occupied • ${fmtPercent(confPct, store.hass)}</span>`
                            : html`<span class="chip">Clear</span>`}
                          ${floorLabel ? html`<span class="chip">${floorLabel}</span>` : nothing}
                          ${sig?.has_signature
                            ? html`<span class="chip chip-primary">Signature (${fmtNumber(sig.scanner_count, store.hass, 0)} ${sig.scanner_count === 1 ? "Proxy" : "Proxies"})</span>`
                            : hasBleProxy
                              ? html`<span class="chip">BLE Proxy</span>`
                              : html`<span class="chip chip-warning">No BLE Proxy</span>`}
                        </div>
                        <div class="area-box-actions">
                          ${bleDevs.length > 0
                            ? html`<button
                                type="button"
                                @click=${() => store.selectBleCalibrateArea(areaId, true)}
                                class="btn btn-secondary btn-compact"
                              >
                                Calibrate
                              </button>`
                            : nothing}
                          ${sig?.has_signature
                            ? html`<button
                                type="button"
                                @click=${() => void store.clearBleAreaSignature(areaId)}
                                class="btn btn-text btn-compact"
                              >
                                Clear Signature
                              </button>`
                            : nothing}
                        </div>
                      </div>

                      <div class="area-box-meta">${parts.join(" • ")}</div>

                      ${renderSettingsRow({
                        label: "Presence Mode",
                        control: html`<select
                          aria-label=${`Presence mode for ${areaName}`}
                          .value=${curMode}
                          @change=${(ev) =>
                            void store.setAreaFusion(areaId, {
                              mode: (ev.currentTarget).value,
                            })}
                        >
                          ${FUSION_MODE_OPTIONS.map(
                            (m) =>
                              html`<option value=${m.val} ?selected=${m.val === curMode}>
                                ${m.label}
                              </option>`,
                          )}
                        </select>`,
                      })}

                      <details
                        ?open=${store.openFusionAreas.has(areaId)}
                        @toggle=${(ev) => {
                          const isOpen = (ev.currentTarget).open;
                          if (isOpen) store.openFusionAreas.add(areaId);
                          else store.openFusionAreas.delete(areaId);
                        }}
                        class="sub-collapsible"
                      >
                        <summary>Sensor &amp; Threshold Settings</summary>
                        <div class="card-content settings-list">
                          ${renderSettingsRow({
                            label: "Occupied At",
                            forId: thresholdId,
                            description:
                              curMode === "weighted"
                                ? "The Area counts as occupied when the combined BLE and sensor score reaches this."
                                : "Used by the Weighted mode only.",
                            control: html`<input
                                type="range"
                                id=${thresholdId}
                                min="20"
                                max="95"
                                step="5"
                                ?disabled=${curMode !== "weighted"}
                                .value=${String(threshold)}
                                @change=${(ev) =>
                                  void store.setAreaFusion(areaId, {
                                    threshold_pct: Number(
                                      (ev.currentTarget).value,
                                    ),
                                  })}
                              />
                              <span class="chip">${fmtPercent(threshold, store.hass)}</span>`,
                          })}
                          ${renderSettingsRow({
                            label: "Sensors That Count",
                            description: chosen.length
                              ? `${chosen.length} of ${choices.length} selected.`
                              : "None selected: every sensor in this Area counts.",
                            stacked: true,
                            control: choices.length
                              ? html`<div
                                  role="group"
                                  aria-label=${`Sensors that count in ${areaName}`}
                                  class="pill-list"
                                >
                                  ${choices.map((s) => {
                                    const on = chosen.includes(s.entity_id);
                                    const nextSensors = on
                                      ? chosen.filter((x) => x !== s.entity_id)
                                      : chosen.concat([s.entity_id]);
                                    return html`<span class="pill ${on ? "enabled" : ""}">
                                      <button
                                        type="button"
                                        aria-pressed=${String(on)}
                                        title=${s.entity_id}
                                        @click=${() =>
                                          void store.setAreaFusion(areaId, {
                                            sensors: nextSensors,
                                          })}
                                        class="pill-toggle"
                                      >
                                        ${on ? "✓ " : ""}${s.name}
                                      </button>
                                    </span>`;
                                  })}
                                </div>`
                              : html`<p class="empty-state">
                                  This Area has no occupancy, motion or door sensors.
                                </p>`,
                          })}
                        </div>
                      </details>
                    </div>`;
                  },
                )
              : html`<p class="empty-state">
                  No Home Assistant Areas, Bluetooth proxies, or occupancy sensors found yet.
                </p>`}
          </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-ble-calibration",
          title: "Walk-Around BLE Calibration",
          subtitle:
            "Carry a tracked Device into an Area to verify proxy coverage or capture a multi-scanner signature.",
          headerActions:
            bleDevs.length > 0
              ? html`<button
                  type="button"
                  aria-pressed=${String(store.bleLiveStreamActive)}
                  @click=${() => store.toggleBleLiveStream(!store.bleLiveStreamActive)}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.bleLiveStreamActive ? "Live Stream On" : "Stream Paused"}
                </button>`
              : nothing,
          footerActions:
            bleDevs.length === 0
              ? html`<button
                  type="button"
                  @click=${() => store.openDiscoveredDevices()}
                  class="btn btn-secondary"
                >
                  Open Discovered Devices
                </button>`
              : nothing,
          contentClass: "stack",
          body:
            bleDevs.length === 0
              ? html`<p class="empty-state">
                  No Devices currently have Bluetooth Area tracking enabled. Enable Track the Area with BLE Proxies on a portable Device, or adopt a phone or tag under Discovered Devices.
                </p>`
              : html`<div
                    id="ble-calibrate-target-box"
                    class="calibrate-target-box${store.bleCalibrateHandoffActive ? " handoff-active" : ""}"
                  >
                    ${store.bleCalibrateHandoffActive
                      ? html`<div id="ble-calibrate-handoff-banner" class="calibrate-handoff-banner">
                          <span>Ready to calibrate ${selectedAreaName} — carry ${activeSurveyDev?.title || "your Device"} into ${selectedAreaName} and click Calibrate Area.</span>
                          <button
                            type="button"
                            @click=${() => {
                              store.bleCalibrateHandoffActive = false;
                              store.host.requestUpdate();
                            }}
                            class="btn btn-text btn-compact"
                          >
                            Dismiss
                          </button>
                        </div>`
                      : nothing}

                    ${renderSettingsRow({
                      forId: "ble-survey-device-picker",
                      label: "Carried Device",
                      description: "Select the actively tracked Device or BLE Tag you are holding.",
                      control: html`<select
                        id="ble-survey-device-picker"
                        .value=${activeSurveyDev?.subentry_id || ""}
                        @change=${(ev) =>
                          store.selectBleSurveyDevice((ev.currentTarget).value)}
                      >
                        ${bleDevs.map(
                          (d) =>
                            html`<option
                              value=${d.subentry_id}
                              ?selected=${d.subentry_id === activeSurveyDev?.subentry_id}
                            >
                              ${d.title} (${d.active_area_name || "Unassigned"})
                            </option>`,
                        )}
                      </select>`,
                    })}

                    ${hasFreshSignal
                      ? html`<div class="alert">
                          <div class="alert-body">
                            <span>Live BLE signal active — currently detected in <strong>${activeSurveyDev?.active_area_name || "Unassigned"}</strong> (${fmtNumber(packetsSeen, store.hass, 0)} packets observed).</span>
                          </div>
                        </div>`
                      : html`<div class="alert alert-warning">
                          <div class="alert-body">
                            <span>No live BLE packets in the last 12 seconds — wake <strong>${activeSurveyDev?.title || "this Device"}</strong> or hold it in hand so its Bluetooth beacon broadcasts before calibrating.</span>
                          </div>
                        </div>`}

                    ${renderSettingsRow({
                      forId: "ble-calibrate-area-select",
                      label: "Standing In Area",
                      description: calibrateDescription,
                      stacked: true,
                      control: html`<div class="input-action-row">
                        <select
                          id="ble-calibrate-area-select"
                          .value=${targetAreaId}
                          @change=${(ev) =>
                            store.selectBleCalibrateArea((ev.currentTarget).value)}
                        >
                          ${areaChoices.length
                            ? areaChoices.map((a) => {
                                const aSig = sigByArea.get(a.area_id);
                                const suffix = aSig?.has_signature
                                  ? " (signature saved)"
                                  : aSig && !aSig.has_ble_proxy
                                    ? " (no BLE proxy)"
                                    : "";
                                return html`<option
                                  value=${a.area_id}
                                  ?selected=${a.area_id === targetAreaId}
                                >
                                  ${a.area_name}${suffix}
                                </option>`;
                              })
                            : html`<option value="">No Home Assistant Areas configured</option>`}
                        </select>
                        <button
                          id="btn-capture-area-signature"
                          type="button"
                          ?disabled=${!activeSurveyDev || !targetAreaId}
                          @click=${() => void store.captureBleAreaSignature(targetAreaId)}
                          class="btn btn-primary"
                        >
                          Calibrate Area
                        </button>
                      </div>`,
                    })}
                  </div>

                  <div class="subsection-title">Nearby Bluetooth Proxies</div>
                  ${surveyRows.length
                    ? repeat(
                        surveyRows,
                        (row) => row.scanner_source || row.area_id,
                        (row) => {
                          const scannerSrc = row.scanner_source || "";
                          const areaTitle = row.area_name || "Unassigned Proxy";
                          const scannerBadge = row.scanner_name || scannerSrc || "BLE Proxy";
                          const pct = rssiToPercent(row.effective_rssi);
                          const sigStyle = `--signal-pct:${pct}%`;
                          const offVal = Number(row.offset_db || 0);
                          const offTxt = `${offVal >= 0 ? "+" : ""}${fmtNumber(offVal, store.hass, 1)} dB`;
                          const rawTxt =
                            row.raw_rssi !== null && row.raw_rssi !== undefined
                              ? `${fmtNumber(row.raw_rssi, store.hass, 0)} dBm`
                              : "—";
                          const effTxt =
                            row.effective_rssi !== null && row.effective_rssi !== undefined
                              ? `${fmtNumber(row.effective_rssi, store.hass, 0)} dBm`
                              : "No signal";
                          const distPart =
                            row.distance_m !== null && row.distance_m !== undefined
                              ? ` • ~${fmtDistance(row.distance_m, store.hass, row.distance_ft)}`
                              : "";
                          const agePart =
                            row.age_seconds !== null && row.age_seconds !== undefined
                              ? ` • ${fmtAgo(row.age_seconds, store.hass)}${row.is_fresh === false ? " (stale)" : ""}`
                              : "";
                          const trimPart = Math.abs(offVal) >= 0.1 ? ` • trim ${offTxt}` : "";
                          const metaText = `${effTxt}${distPart}${agePart}${trimPart}`;
                          return html`<div class="signal-row ${row.is_winner ? "winner" : ""}">
                            <div class="signal-row-head">
                              <span class="signal-row-title">
                                <span class="row-label">${areaTitle}</span>
                                <span class="chip">${scannerBadge}</span>
                                ${!row.area_name
                                  ? html`<span class="chip chip-warning">Assign Area in HA</span>`
                                  : nothing}
                                ${row.is_winner
                                  ? html`<span class="chip chip-primary">Active Winner</span>`
                                  : nothing}
                              </span>
                              <span class="signal-meta">${metaText}</span>
                            </div>
                            <div class="signal-track">
                              <div class="signal-fill" style=${sigStyle}></div>
                            </div>
                            ${scannerSrc
                              ? html`<details
                                  ?open=${Boolean(store.openProxyTrims?.has(scannerSrc))}
                                  @toggle=${(ev) => {
                                    const openSet = store.openProxyTrims;
                                    if (!openSet) return;
                                    if ((ev.currentTarget).open) {
                                      openSet.add(scannerSrc);
                                    } else {
                                      openSet.delete(scannerSrc);
                                    }
                                  }}
                                  class="sub-collapsible proxy-trim-details"
                                >
                                  <summary>Antenna Trim</summary>
                                  <div class="proxy-trim-body">
                                    <span class="help-text">Raw ${rawTxt} • Gain offset ${offTxt} — adjust only if this proxy consistently reads louder or weaker across every Area.</span>
                                    <div class="input-action-row">
                                      <button
                                        type="button"
                                        @click=${() => void store.setBleScannerOffset(scannerSrc, offVal - 1)}
                                        class="btn btn-secondary btn-compact"
                                      >
                                        -1 dB
                                      </button>
                                      <button
                                        type="button"
                                        @click=${() => void store.setBleScannerOffset(scannerSrc, offVal + 1)}
                                        class="btn btn-secondary btn-compact"
                                      >
                                        +1 dB
                                      </button>
                                      <button
                                        type="button"
                                        @click=${() => void store.setBleScannerOffset(scannerSrc, 0)}
                                        class="btn btn-text btn-compact"
                                      >
                                        Reset
                                      </button>
                                    </div>
                                  </div>
                                </details>`
                              : nothing}
                          </div>`;
                        },
                      )
                    : html`<p class="empty-state">
                        No Bluetooth proxy readings yet for this Device.
                      </p>`}`,
        })}

        <details
          id="card-advanced-ble-settings"
          ?open=${store.advancedBleOpen}
          @toggle=${(ev) => {
            store.advancedBleOpen = (ev.currentTarget).open;
          }}
          class="card"
        >
          <summary class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Advanced BLE Settings</h3>
              <p class="card-subtitle">
                System-wide away timeout, maximum proxy radius, movement speed damping, and path-loss attenuation.
              </p>
            </div>
          </summary>
          <div class="card-content settings-list">
            ${renderSettingsRow({
              forId: "sys-ble_away_timeout_s",
              label: "Away Timeout",
              description:
                "Seconds without any Bluetooth packet before a tracked Tag or offline Device is marked Away.",
              control: html`<input
                type="number"
                id="sys-ble_away_timeout_s"
                min="30"
                max="900"
                step="15"
                .value=${String(sysCfg?.ble_away_timeout_s ?? 180)}
                @change=${(ev) => {
                  const val = Number((ev.currentTarget).value);
                  if (Number.isFinite(val)) {
                    store.stageSystemSetting("ble_away_timeout_s", Math.round(val), "sys-ble_away_timeout_s");
                  }
                }}
              />`,
            })}
            ${renderSettingsRow({
              forId: "sys-ble_max_radius_m",
              label: "Maximum Area Radius",
              description:
                "Ignores Bluetooth proxies farther than this distance in meters so outdoor signals do not claim indoor Areas.",
              control: html`<input
                type="number"
                id="sys-ble_max_radius_m"
                min="2"
                max="50"
                step="0.5"
                .value=${String(sysCfg?.ble_max_radius_m ?? 12)}
                @change=${(ev) => {
                  const val = Number((ev.currentTarget).value);
                  if (Number.isFinite(val)) {
                    store.stageSystemSetting("ble_max_radius_m", val, "sys-ble_max_radius_m");
                  }
                }}
              />`,
            })}
            ${renderSettingsRow({
              forId: "sys-ble_max_velocity_mps",
              label: "Maximum Movement Speed",
              description:
                "Damps sudden signal drops that imply movement faster than this speed in meters per second.",
              control: html`<input
                type="number"
                id="sys-ble_max_velocity_mps"
                min="0.5"
                max="15"
                step="0.5"
                .value=${String(sysCfg?.ble_max_velocity_mps ?? 3.5)}
                @change=${(ev) => {
                  const val = Number((ev.currentTarget).value);
                  if (Number.isFinite(val)) {
                    store.stageSystemSetting("ble_max_velocity_mps", val, "sys-ble_max_velocity_mps");
                  }
                }}
              />`,
            })}
            ${renderSettingsRow({
              forId: "sys-ble_attenuation",
              label: "Path-Loss Attenuation",
              description:
                "Controls how quickly Bluetooth signal strength drops with distance through walls (default 2.2).",
              control: html`<input
                type="number"
                id="sys-ble_attenuation"
                min="1.5"
                max="4.5"
                step="0.1"
                .value=${String(sysCfg?.ble_attenuation ?? 2.2)}
                @change=${(ev) => {
                  const val = Number((ev.currentTarget).value);
                  if (Number.isFinite(val)) {
                    store.stageSystemSetting("ble_attenuation", val, "sys-ble_attenuation");
                  }
                }}
              />`,
            })}
          </div>
        </details>
      </div>
    </div>
  </section>`;
}

// --- src/views/system-remotes-view.ts ---
/**
 * System Media & Remotes View (`remotes`): Remote Controls, Volume Overrides & Remote Control Groups.
 */
function renderSystemRemotesView(store) {
  const data = store.state;
  const sc = data?.system_config;
  const cat = data?.catalog || {};
  const remotes = sc?.remotes_list || [];
  const volOverrides = sc?.volume_overrides || [];
  const remoteGroups = sc?.remote_groups || [];
  const areas = cat.areas || [];
  const speakerChoices = cat.ma_speakers || [];
  const targetChoices = cat.volume_targets || cat.remotes || [];
  const inventoryIds = remotes.filter(Boolean);
  const friendlyRemoteLabel = (entId) => {
    const found = (cat.remotes || []).find((r) => r.id === entId);
    return found ? found.name.split(" (")[0] : entId;
  };
  return html`<section id="view-remotes">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Remote Controls",
          subtitle: "Up to 10 TV, streamer, or receiver entities controlled from the Remote screen.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addStringListRow("remotes_list", "", 10)}
            class="btn btn-secondary btn-compact"
          >
            Add Remote
          </button>`,
          body: renderEntitySlotList({
            id: "remotes-list",
            items: remotes,
            choices: cat.remotes,
            emptyOptionLabel: "— Choose a remote or media player —",
            emptyStateText: "No remote controls configured yet.",
            selectAriaLabel: "Remote or media player",
            removeAriaLabel: "Remove remote",
            slotLabel: (idx) => (idx === 0 ? "Slot 1 (Primary Power Target)" : `Slot ${idx + 1}`),
            onChange: (idx, val) => store.updateStringListRow("remotes_list", idx, val),
            onRemove: (idx) => store.removeStringListRow("remotes_list", idx),
          }),
        })}

        ${renderCard({
          id: "card-volume-overrides",
          title: "Speaker Volume Overrides",
          subtitle: "Redirects volume buttons when audio plays through an external AVR or soundbar.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addVolumeOverrideRow()}
            class="btn btn-secondary btn-compact"
          >
            Add Override
          </button>`,
          body: html`<div id="volume-overrides-list" class="stack">
            ${volOverrides.length
              ? volOverrides.map(
                  (vo, idx) => html`<div class="list-row">
                    <div class="list-row-main">
                      <div class="stacked-field">
                        <span class="field-label">When Audio Plays On</span>
                        <select
                          aria-label="Speaker"
                          .value=${vo.speaker}
                          @change=${(ev) =>
                            store.updateVolumeOverrideRow(
                              idx,
                              "speaker",
                              (ev.currentTarget).value,
                            )}
                        >
                          ${renderSelectOptions(speakerChoices, vo.speaker, "— Choose a speaker —")}
                        </select>
                      </div>
                      <div class="stacked-field">
                        <span class="field-label">Change the Volume On</span>
                        <select
                          aria-label="Volume target"
                          .value=${vo.target}
                          @change=${(ev) =>
                            store.updateVolumeOverrideRow(
                              idx,
                              "target",
                              (ev.currentTarget).value,
                            )}
                        >
                          ${renderSelectOptions(
                            targetChoices,
                            vo.target,
                            "— Choose a volume target —",
                          )}
                        </select>
                      </div>
                    </div>
                    ${renderTrashIconButton("Remove volume override", () =>
                      store.removeVolumeOverrideRow(idx),
                    )}
                  </div>`,
                )
              : html`<p class="empty-state">No volume overrides configured.</p>`}
          </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "Remote Control Groups",
          subtitle: "Bind sets of remotes to Home Assistant Areas or specific Devices.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addRemoteGroupRow()}
            class="btn btn-secondary btn-compact"
          >
            Add Group
          </button>`,
          body: html`<div id="remote-groups-list" class="stack">
            ${remoteGroups.length
              ? remoteGroups.map((grp, gIdx) => {
                  const selectedRems = Array.isArray(grp.remotes) ? grp.remotes : [];
                  const pool = selectedRems
                    .filter((id) => inventoryIds.includes(id))
                    .concat(inventoryIds.filter((id) => !selectedRems.includes(id)));
                  return html`<div class="list-block">
                    <div class="list-row-head">
                      <div class="list-row-main">
                        <div class="stacked-field">
                          <label>Group Name</label>
                          <input
                            type="text"
                            aria-label="Group name"
                            placeholder="e.g. Living Area TV"
                            .value=${grp.name || ""}
                            @change=${(ev) =>
                              store.updateRemoteGroupField(
                                grp.id,
                                "name",
                                (ev.currentTarget).value,
                              )}
                          />
                        </div>
                        <div class="stacked-field">
                          <label>Loads in Area</label>
                          <select
                            aria-label="Area"
                            .value=${grp.area_id || ""}
                            @change=${(ev) =>
                              store.updateRemoteGroupField(
                                grp.id,
                                "area_id",
                                (ev.currentTarget).value,
                              )}
                          >
                            <option value="">No Area (assign to Devices only)</option>
                            ${areas.map(
                              (a) =>
                                html`<option value=${a.id} ?selected=${a.id === grp.area_id}>
                                  ${a.name}
                                </option>`,
                            )}
                          </select>
                        </div>
                      </div>
                      ${renderTrashIconButton(`Delete remote group ${grp.name || ""}`, () =>
                        store.removeRemoteGroupRow(grp.id),
                      )}
                    </div>
                    <div class="stacked-field">
                      <span id=${`rg-remotes-${gIdx}`} class="field-label">Remote Controls</span>
                      <div role="group" aria-labelledby=${`rg-remotes-${gIdx}`} class="pill-list">
                        ${pool.length
                          ? pool.map((entId) => {
                              const pos = selectedRems.indexOf(entId);
                              const isEn = pos >= 0;
                              const badge = isEn
                                ? pos === 0
                                  ? "★ Primary: "
                                  : `#${pos + 1}: `
                                : "+ ";
                              return html`<button
                                type="button"
                                aria-pressed=${String(isEn)}
                                @click=${() => store.toggleRemoteInGroup(grp.id, entId)}
                                class="pill ${isEn ? "enabled" : ""}"
                              >
                                ${badge}${friendlyRemoteLabel(entId)}
                              </button>`;
                            })
                          : html`<span class="help-text">Add remote controls first.</span>`}
                      </div>
                    </div>
                  </div>`;
                })
              : html`<p class="empty-state">No remote groups yet.</p>`}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/system-shared-view.ts ---
/**
 * System Shared Entities View (`shared_entities`): Whole-Home Entities, Calendars, Cameras & Doorbell Audio, Custom Colors & Wallpapers (D-022).
 */
const TALK_STATE_TEXT = {
  listening: "listening",
  talking: "replying",
};
const DOORBELL_FILTER_OPTIONS = [
  { value: "strong", label: "Strong" },
  { value: "light", label: "Light" },
  { value: "off", label: "Off" },
];
function renderSystemSharedView(store) {
  const data = store.state;
  const sc = data?.system_config;
  const cat = data?.catalog || {};
  const cameras = sc?.camera_entities || [];
  const calendars = sc?.calendar_entities || [];
  const palettes = sc?.custom_palettes || [];
  const doorbells = data?.doorbells || [];
  const wallpapers = data?.system_wallpapers || [];
  const noiseRed = sc?.doorbell_noise_reduction || "strong";
  const wholeHomeFields
     = [
    { key: "weather_entity", label: "Weather", choices: cat.weathers },
    { key: "alarm_entity", label: "Alarm Control Panel", choices: cat.alarms },
    { key: "thermostat_entity", label: "Primary Thermostat", choices: cat.climates },
    { key: "lock_entity", label: "Primary Door Lock", choices: cat.locks },
    { key: "garage_entity", label: "Garage or Gate Cover", choices: cat.garages },
    { key: "vacuum_entity", label: "Robot Vacuum", choices: cat.vacuums },
  ];
  return html`<section id="view-shared_entities">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Whole-Home Entities</h3>`,
          subtitle: "Shared entities shown across Home Hub, Weather, and Area views on every Device.",
          contentClass: "settings-list",
          body: wholeHomeFields.map((f) =>
            renderSelectRow({
              id: `cfg-${f.key}`,
              label: f.label,
              value: sc?.[f.key],
              choices: f.choices,
              emptyOptionLabel: "— None —",
              onChange: (val) => store.stageSystemSetting(f.key, val, `cfg-${f.key}`),
            }),
          ),
        })}

        ${renderCard({
          id: "card-calendars",
          heading: html`<h3 class="card-title">Calendars</h3>`,
          subtitle: "Upcoming events merged into the Activity Card and agenda feed.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addStringListRow("calendar_entities", "", 50)}
            class="btn btn-secondary btn-compact"
          >
            Add Calendar
          </button>`,
          body: renderEntitySlotList({
            id: "calendars-list",
            items: calendars,
            choices: cat.calendars,
            emptyOptionLabel: "— Choose a calendar —",
            emptyStateText: "No calendars configured yet.",
            selectAriaLabel: "Calendar",
            removeAriaLabel: "Remove calendar",
            onChange: (idx, val) => store.updateStringListRow("calendar_entities", idx, val),
            onRemove: (idx) => store.removeStringListRow("calendar_entities", idx),
          }),
        })}

        ${renderCard({
          id: "card-system-wallpapers",
          heading: html`<h3 class="card-title">Wallpapers</h3>`,
          subtitle: "Shared System wallpapers and presets available to every Latter display.",
          headerActions: renderWallpaperUploadTrigger(store, "system"),
          contentClass: "stack",
          body: html`${renderWallpaperUploadProgress(store, "system")}
            <div class="wp-gallery">
              ${renderWallpaperGalleryItems(store, "system", wallpapers, "square")}
            </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-cameras-doorbell",
          heading: html`<h3 class="card-title">Cameras &amp; Doorbell Audio</h3>`,
          subtitle:
            "Up to 10 cameras. Doorbell ring sensors wake displays automatically with listen audio and push-to-talk TTS replies.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addStringListRow("camera_entities", "", 10)}
            class="btn btn-secondary btn-compact"
          >
            Add Camera
          </button>`,
          contentClass: "stack",
          body: html`<div class="settings-list">
              ${renderSelectRow({
                id: "cfg-doorbell_noise_reduction",
                label: "Doorbell Audio Filter",
                description:
                  "FFmpeg noise-reduction preset applied when listening to camera audio.",
                value: noiseRed,
                rawOptions: DOORBELL_FILTER_OPTIONS,
                onChange: (val) =>
                  store.stageSystemSetting(
                    "doorbell_noise_reduction",
                    val,
                    "cfg-doorbell_noise_reduction",
                  ),
              })}
            </div>

            ${renderEntitySlotList({
              id: "cameras-list",
              items: cameras,
              choices: cat.cameras,
              emptyOptionLabel: "— Choose a camera —",
              emptyStateText: "No cameras configured yet.",
              selectAriaLabel: "Camera",
              removeAriaLabel: "Remove camera",
              slotLabel: (idx) => (idx === 0 ? "Camera 1 (Primary)" : `Camera ${idx + 1}`),
              extraActions: (camId) => html`<button
                type="button"
                ?disabled=${!camId}
                @click=${() => void store.previewCamera(camId)}
                class="btn btn-text btn-compact"
              >
                Preview
              </button>`,
              onChange: (idx, val) => store.updateStringListRow("camera_entities", idx, val),
              onRemove: (idx) => store.removeStringListRow("camera_entities", idx),
            })}

            ${store.cameraPreviewUrl
              ? html`<div id="cam-preview-box" class="cam-preview">
                  <div class="input-action-row">
                    <span class="field-label">Preview: ${store.activeCameraPreviewEntity}</span>
                    <button
                      type="button"
                      @click=${() => void store.previewCamera(store.activeCameraPreviewEntity, true)}
                      class="btn btn-secondary btn-compact"
                    >
                      Refresh
                    </button>
                    <button
                      type="button"
                      @click=${() => store.closeCameraPreview()}
                      class="btn btn-text btn-compact"
                    >
                      Close
                    </button>
                  </div>
                  <img
                    id="cam-preview-img"
                    src=${store.cameraPreviewUrl}
                    alt="Camera preview"
                  />
                </div>`
              : nothing}

            ${doorbells.length
              ? html`<div id="doorbell-status" class="stack">
                  <h4 class="subsection-title">Doorbells</h4>
                  <div id="doorbell-status-list" class="kv-list">
                    ${doorbells.map((b) => {
                      let ring = "No ring sensor found";
                      const ringEnt = b.ring_entity || "";
                      if (ringEnt) {
                        const when = b.ring_at
                          ? fmtAgo((Date.now() - Date.parse(b.ring_at)) / 1000, store.hass)
                          : "";
                        const st = ringEnt.startsWith("event.")
                          ? when
                            ? `last ring ${when}`
                            : "no ring yet"
                          : b.ring_state === "on"
                            ? "ringing"
                            : b.ring_state
                              ? `idle${when ? `, changed ${when}` : ""}`
                              : "unavailable";
                        ring = `${b.ring_name || ringEnt}: ${st}`;
                      }
                      const talk = (b.talk || [])
                        .map((t) => `${t.device_title} ${TALK_STATE_TEXT[t.state] || t.state}`)
                        .join(", ");
                      return html`<div class="kv-row">
                        <span>${entityLabel(b.camera_name || b.camera_entity)}</span>
                        <strong>${ring}${talk ? ` • ${talk}` : ""}</strong>
                      </div>`;
                    })}
                  </div>
                </div>`
              : nothing}`,
        })}

        ${renderCard({
          id: "card-custom-colors",
          heading: html`<h3 class="card-title">Custom Colors</h3>`,
          subtitle: "Shared 24-swatch accent library available across all Devices.",
          headerActions: html`<button
            type="button"
            @click=${() => store.openColorWheelModal("system")}
            class="btn btn-secondary btn-compact"
          >
            Add Color
          </button>`,
          contentClass: "settings-list",
          body: html`<div id="sys-custom-palettes-list" class="settings-list">
            ${palettes.length
              ? palettes.map((p) => {
                  const h = p.hex.toUpperCase();
                  const swStyle = `--swatch-color:${h}`;
                  return renderSettingsRow({
                    labelHtml: html`<span class="row-label">
                      <span class="swatch" style=${swStyle} aria-hidden="true"></span>
                      ${p.name || h}
                    </span>`,
                    description: html`<code>${h}</code>`,
                    control: renderTrashIconButton(`Delete color ${p.name || h}`, () =>
                      store.deleteCustomPalette(h),
                    ),
                  });
                })
              : html`<p class="empty-state">No custom colors saved yet.</p>`}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/system-tools-view.ts ---
/**
 * System Tools View (`system_tools`): Notifications & Announcements, Doorbell & Intercom Audio,
 * Backup & Restore, Perimeter Security & Signing, and Logs-only `system_log`.
 */
function renderSystemToolsView(store) {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const latterDevices = allDevices.filter((d) => d.kind !== "ble_tag");
  const configuredCameras = (data?.system_config?.camera_entities || [])
    .map((c) => String(c || "").trim())
    .filter(Boolean);
  const primaryCamera = configuredCameras[0] || "";
  const canTestDoorbell = Boolean(primaryCamera && latterDevices.length > 0);
  const doorbellTestDescription = !primaryCamera
    ? "Map a camera with a bound door speaker in Shared Entities first to test TTS reply playback."
    : !latterDevices.length
      ? "Onboard at least one Latter Device first to route push-to-talk test replies."
      : `Plays a short TTS phrase on Camera 1's bound media player (${primaryCamera}).`;
  const hasSystemPin = Boolean(data?.has_security_pin);
  const isBroadcast = store.announceMode === "broadcast";
  const onAnnounceRadioKey = (ev) => {
    const kev = ev;
    if (kev.key !== "ArrowLeft" && kev.key !== "ArrowRight") return;
    kev.preventDefault();
    const nextMode = store.announceMode === "notify" ? "broadcast" : "notify";
    store.announceMode = nextMode;
    store.host.requestUpdate();
    const group = (kev.currentTarget).parentElement;
    const nextBtn = group?.querySelector(
      `[data-mode="${nextMode}"]`,
    );
    nextBtn?.focus();
  };
  return html`<section id="view-system_tools">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Notifications &amp; Announcements</h3>`,
          subtitle:
            "Send screen popups or spoken intercom broadcasts to all Devices, Occupied Areas, or one display.",
          contentClass: "stack",
          body: html`<div role="radiogroup" aria-label="Announcement mode" class="segmented">
              <button
                type="button"
                data-mode="notify"
                tabindex=${!isBroadcast ? "0" : "-1"}
                aria-checked=${!isBroadcast}
                @click=${() => {
                  store.announceMode = "notify";
                  store.host.requestUpdate();
                }}
                @keydown=${onAnnounceRadioKey}
                role="radio"
              >
                Screen Notification
              </button>
              <button
                type="button"
                data-mode="broadcast"
                tabindex=${isBroadcast ? "0" : "-1"}
                aria-checked=${isBroadcast}
                @click=${() => {
                  store.announceMode = "broadcast";
                  store.host.requestUpdate();
                }}
                @keydown=${onAnnounceRadioKey}
                role="radio"
              >
                Voice Broadcast
              </button>
            </div>

            <div class="stacked-field">
              <label for="ann-target">Target</label>
              <select
                id="ann-target"
                .value=${store.announceTarget}
                @change=${(ev) => {
                  store.announceTarget = (ev.currentTarget).value || "all";
                  store.host.requestUpdate();
                }}
              >
                <option value="all" ?selected=${store.announceTarget === "all"}>
                  All Latter Displays
                </option>
                <option
                  value="occupied_areas"
                  ?selected=${store.announceTarget === "occupied_areas"}
                >
                  Occupied Areas Only
                </option>
                ${latterDevices.map(
                  (d) =>
                    html`<option
                      value=${d.device_slug}
                      ?selected=${store.announceTarget === d.device_slug}
                    >
                      Device: ${d.title}
                    </option>`,
                )}
              </select>
            </div>

            ${!isBroadcast
              ? html`<div class="stacked-field">
                    <label for="ann-title">Notification Title</label>
                    <input
                      type="text"
                      id="ann-title"
                      placeholder="e.g. Front Gate"
                      .value=${store.announceTitle}
                      @input=${(ev) => {
                        store.announceTitle = (ev.currentTarget).value;
                      }}
                    />
                  </div>
                  <div class="list-row-main">
                    <div class="stacked-field">
                      <label for="ann-priority">Priority</label>
                      <select
                        id="ann-priority"
                        .value=${store.announcePriority}
                        @change=${(ev) => {
                          store.announcePriority = (ev.currentTarget).value
                                        ;
                        }}
                      >
                        <option value="normal">Normal</option>
                        <option value="warning">Warning</option>
                        <option value="critical">Critical</option>
                      </select>
                    </div>
                    <label class="inline-switch">
                      <input
                        type="checkbox"
                        role="switch"
                        .checked=${store.announceIncludeCamera}
                        @change=${(ev) => {
                          store.announceIncludeCamera = (
                            ev.currentTarget
                          ).checked;
                        }}
                        class="switch"
                      />
                      <span>Include Primary Camera</span>
                    </label>
                  </div>`
              : nothing}

            <div class="stacked-field">
              <label for="ann-message">Message</label>
              <textarea
                id="ann-message"
                rows="3"
                placeholder="Message to display or speak…"
                .value=${store.announceMessage}
                @input=${(ev) => {
                  store.announceMessage = (ev.currentTarget).value;
                }}
              ></textarea>
            </div>

            <div class="input-action-row">
              <button
                type="button"
                @click=${() => void store.sendAnnouncement()}
                class="btn btn-primary"
              >
                Send Now
              </button>
            </div>`,
        })}

        ${renderCard({
          id: "card-doorbell-intercom-audio",
          heading: html`<h3 class="card-title">Doorbell &amp; Intercom Audio</h3>`,
          subtitle:
            "Verify push-to-talk TTS reply playback through Camera 1's bound door speaker.",
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: "Source Device",
              forId: "doorbell-test-device",
              description: "Latter Device context used when routing the door speaker reply.",
              control: html`<select
                id="doorbell-test-device"
                ?disabled=${!canTestDoorbell}
                .value=${store.doorbellTestSubentryId}
                @change=${(ev) => {
                  store.doorbellTestSubentryId = (ev.currentTarget).value;
                  store.host.requestUpdate();
                }}
              >
                ${latterDevices.length
                  ? latterDevices.map(
                      (d) =>
                        html`<option
                          value=${d.subentry_id}
                          ?selected=${d.subentry_id === store.doorbellTestSubentryId}
                        >
                          ${d.title}
                        </option>`,
                    )
                  : html`<option value="">— No Latter Devices —</option>`}
              </select>`,
            })}
            ${renderSettingsRow({
              id: "row-doorbell-test-reply",
              label: "Test Door Speaker Reply",
              forId: "doorbell-test-reply",
              description: doorbellTestDescription,
              stacked: true,
              control: html`<div class="input-action-row">
                <input
                  type="text"
                  id="doorbell-test-reply"
                  maxlength="160"
                  placeholder="Testing Latter doorbell audio."
                  ?disabled=${!canTestDoorbell}
                  .value=${store.doorbellTestReply}
                  @input=${(ev) => {
                    store.doorbellTestReply = (ev.currentTarget).value;
                  }}
                />
                <button
                  type="button"
                  id="btn-play-door-speaker"
                  ?disabled=${!canTestDoorbell}
                  @click=${() => void store.testDoorbellSpeaker()}
                  class="btn btn-primary btn-compact"
                >
                  Play on Door Speaker
                </button>
                ${!primaryCamera
                  ? html`<button
                      type="button"
                      @click=${() =>
                        store.openSystemSection("shared_entities", "card-cameras-doorbell")}
                      class="btn btn-text btn-compact"
                    >
                      Open Shared Entities
                    </button>`
                  : nothing}
              </div>`,
            })}`,
        })}

        <details
          ?open=${store.logsOpen}
          @toggle=${(ev) =>
            store.onToggleLogsDetails((ev.currentTarget).open)}
          class="card"
        >
          <summary class="card-header">
            <div class="card-heading">
              <h3 class="card-title">System &amp; Device Logs</h3>
            </div>
          </summary>
          <div class="card-content stack">
            <div class="input-action-row">
              <select
                aria-label="Filter diagnostic logs"
                .value=${store.logFilter}
                @change=${(ev) => {
                  store.logFilter = (ev.currentTarget).value || "all";
                  store.host.requestUpdate();
                }}
              >
                <option value="all" ?selected=${store.logFilter === "all"}>All Events</option>
                <option value="latter" ?selected=${store.logFilter === "latter"}>Latter Studio</option>
                <option value="errors" ?selected=${store.logFilter === "errors"}>
                  Warnings &amp; Errors
                </option>
                ${allDevices.map(
                  (d) =>
                    html`<option
                      value=${`device:${d.device_slug}`}
                      ?selected=${store.logFilter === `device:${d.device_slug}`}
                    >
                      Device: ${d.title}
                    </option>`,
                )}
              </select>
              <button
                type="button"
                @click=${() => void store.refreshState({ includeLogs: true })}
                class="btn btn-secondary btn-compact"
              >
                Refresh Logs
              </button>
              <button
                type="button"
                @click=${() => void store.copyLogsToClipboard()}
                class="btn btn-secondary btn-compact"
              >
                Copy Logs
              </button>
              <button
                type="button"
                @click=${() => void store.clearInternalLogs()}
                class="btn btn-text btn-compact"
              >
                Clear Studio Events
              </button>
              <button
                type="button"
                @click=${() => store.openHaPage("/config/logs")}
                class="btn btn-text btn-compact"
              >
                Open Native HA Logs
              </button>
            </div>
            <pre class="log-output">${store.formatVisibleLogs()}</pre>
          </div>
        </details>
      </div>

      <div class="column">
        ${renderCard({
          id: "card-backup-restore",
          heading: html`<h3 class="card-title">Backup &amp; Restore</h3>`,
          subtitle:
            "Export or restore non-secret System and Device configurations as portable JSON bundles.",
          contentClass: "stack",
          body: html`<div class="stacked-field">
              <label for="bkp-scope-select">Export Scope</label>
              <div class="input-action-row">
                <select
                  id="bkp-scope-select"
                  .value=${store.backupExportScope}
                  @change=${(ev) => {
                    store.backupExportScope = (ev.currentTarget).value;
                    store.host.requestUpdate();
                  }}
                >
                  <option value="system" ?selected=${store.backupExportScope === "system"}>
                    Entire System + All Devices
                  </option>
                  ${allDevices.map(
                    (d) =>
                      html`<option
                        value=${`device:${d.subentry_id}`}
                        ?selected=${store.backupExportScope === `device:${d.subentry_id}`}
                      >
                        Device: ${d.title}
                      </option>`,
                  )}
                </select>
                <button
                  type="button"
                  @click=${() => void store.exportBackup()}
                  class="btn btn-secondary"
                >
                  Download Backup
                </button>
              </div>
            </div>

            <div class="stacked-field">
              <label for="bkp-upload-file">Restore From Backup</label>
              <input
                type="file"
                id="bkp-upload-file"
                accept=".json,application/json"
                @change=${(ev) => {
                  const inp = ev.currentTarget;
                  store.selectedBackupFile = inp.files && inp.files[0] ? inp.files[0] : null;
                  store.host.requestUpdate();
                }}
              />
            </div>

            <div class="stacked-field">
              <label for="bkp-restore-device">Target Device (for Single-Device Backups)</label>
              <select
                id="bkp-restore-device"
                .value=${store.backupRestoreSubentryId}
                @change=${(ev) => {
                  store.backupRestoreSubentryId = (ev.currentTarget).value;
                  store.host.requestUpdate();
                }}
              >
                <option value="">— Automatic (System Backup) —</option>
                ${allDevices.map(
                  (d) =>
                    html`<option
                      value=${d.subentry_id}
                      ?selected=${d.subentry_id === store.backupRestoreSubentryId}
                    >
                      ${d.title}
                    </option>`,
                )}
              </select>
            </div>

            <div class="input-action-row">
              <button
                type="button"
                ?disabled=${!store.selectedBackupFile}
                @click=${() => void store.restoreFromUploadedFile()}
                class="btn btn-primary"
              >
                Restore Backup
              </button>
            </div>`,
        })}

        ${renderCard({
          title: "Perimeter Security & Signing",
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: "System Security PIN",
              description:
                "Default numeric PIN (4 to 12 digits, PBKDF2-HMAC-SHA256) used when a Device's Perimeter Security Policy requires PIN verification.",
              stacked: true,
              control: html`<div class="input-action-row">
                <span id="sys-security-pin-status" class="chip ${hasSystemPin ? "chip-success" : ""}">
                  ${hasSystemPin ? "PIN configured" : "Not set"}
                </span>
                <input
                  type="password"
                  id="sys-security-pin-input"
                  inputmode="numeric"
                  pattern="[0-9]*"
                  autocomplete="new-password"
                  aria-label="System Security PIN (4 to 12 digits)"
                  placeholder=${hasSystemPin ? "Enter new PIN to replace…" : "4 to 12 digits"}
                  .value=${store.systemPinDraft}
                  @input=${(ev) => {
                    store.systemPinDraft = (ev.currentTarget).value;
                    store.host.requestUpdate();
                  }}
                />
                <button
                  type="button"
                  ?disabled=${store.pinBusy || !store.systemPinDraft.trim()}
                  @click=${() => void store.saveSecurityPin("system")}
                  class="btn btn-primary btn-compact"
                >
                  Save PIN
                </button>
                ${hasSystemPin
                  ? html`<button
                      type="button"
                      id="btn-clear-security-pin"
                      ?disabled=${store.pinBusy}
                      @click=${() => void store.clearSecurityPin("system")}
                      class="btn btn-danger btn-compact"
                    >
                      Clear PIN
                    </button>`
                  : nothing}
              </div>`,
            })}
            ${renderSettingsRow({
              label: "HTTP Resource Signing Key",
              description:
                "Rotates the System HMAC secret and pushes refreshed signed artwork, map, camera, and wallpaper URLs to online Devices.",
              control: html`<button
                type="button"
                @click=${() => void store.rotateSigningKey()}
                class="btn btn-secondary btn-compact"
              >
                Rotate Signing Key
              </button>`,
            })}`,
        })}
      </div>
    </div>
  </section>`;
}

// --- src/views/index.ts ---
/**
 * Active-View-Only Router (`D-023`, `D-026`): Renders ONLY the currently active Studio view.
 */
function renderActiveView(store) {
  if (store.currentScope === "system") {
    switch (store.currentViewId) {
      case "shared_entities":
        return renderSystemSharedView(store);
      case "remotes":
        return renderSystemRemotesView(store);
      case "system_sync":
        return renderSystemGroupsView(store);
      case "area_tracking":
        return renderSystemPresenceView(store);
      case "system_tools":
        return renderSystemToolsView(store);
      case "system_overview":
      default:
        return renderSystemOverviewView(store);
    }
  }
  if (store.currentViewId === "discovered_devices") {
    return renderDevicesDiscoveredView(store);
  }
  if (!store.deviceSelected || store.currentViewId === "select_device_prompt") {
    return renderDevicesListView(store);
  }
  switch (store.currentViewId) {
    case "display":
      return renderDeviceDisplayView(store);
    case "interface":
      return renderDeviceInterfaceView(store);
    case "audio_voice":
      return renderDeviceAudioView(store);
    case "power":
      return renderDevicePowerView(store);
    case "presence":
      return renderDevicePresenceView(store);
    case "tools":
      return renderDeviceToolsView(store);
    case "dashboard":
    default:
      return renderDeviceOverviewView(store);
  }
}

// --- src/latter-studio.ts ---
/**
 * `<latter-studio>` Custom Element — Modular TypeScript + Lit Architecture (`D-023`).
 *
 * - Zero global `window` property bindings; state is owned per element by `StudioStore`.
 * - Active-view-only rendering via `renderActiveView(this.store)`.
 * - Full WAI-ARIA `tablist` / roving arrow-key focus on Scope tabs and `aria-current="page"` on sidebar nav.
 * - Dedicated reload banner when `studio_rev_mismatch` is signaled after an HACS update.
 */
const SYSTEM_NAV_ITEMS = [
  { viewId: "system_overview", label: "Overview" },
  { viewId: "shared_entities", label: "Shared Entities" },
  { viewId: "remotes", label: "Media & Remotes" },
  { viewId: "system_sync", label: "Device Groups" },
  { viewId: "area_tracking", label: "BLE & Area Presence" },
  { viewId: "system_tools", label: "Tools" },
];
class LatterStudio extends LitElement {
  static styles = STUDIO_STYLES;
           store;
          _narrow = false;
          _route = null;
          _panel = null;
          _routeInitialized = false;
  constructor() {
    super();
    this.store = new StudioStore(this);
    this.addController(this.store);
  }
           connectedCallback() {
    super.connectedCallback();
    if (!this._routeInitialized) {
      this._routeInitialized = true;
      this._applyRoute();
    }
  }
  set hass(h) {
    this.toggleAttribute("dark", Boolean(h?.themes?.darkMode ?? h?.selectedTheme?.dark));
    this.store.setHass(h);
  }
  get hass() {
    return this.store.hass;
  }
  set narrow(n) {
    const next = Boolean(n);
    if (this._narrow === next) return;
    this._narrow = next;
    this.toggleAttribute("narrow", next);
    this.requestUpdate();
  }
  get narrow() {
    return this._narrow;
  }
  set panel(p) {
    this._panel = p;
  }
  get panel() {
    return this._panel;
  }
  set route(r) {
    const prevPath = this._route?.path ?? null;
    this._route = r;
    if (this._routeInitialized && r && r.path !== prevPath) {
      this._applyRoute();
    }
  }
  get route() {
    return this._route;
  }
          _applyRoute() {
    this.store.applyRoute(this._route);
  }
          _onRootKeyDown(ev) {
    if (ev.ctrlKey || ev.metaKey || ev.altKey || ev.key === "Escape" || ev.key === "Tab") {
      return;
    }
    const path = typeof ev.composedPath === "function" ? ev.composedPath() : [];
    const inner = (path[0] ?? ev.target);
    if (!inner || typeof inner.tagName !== "string") return;
    const tag = inner.tagName.toUpperCase();
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
      ev.stopPropagation();
    }
  }
          _onScopeTabKeyDown(ev) {
    if (
      ev.key !== "ArrowLeft" &&
      ev.key !== "ArrowRight" &&
      ev.key !== "Home" &&
      ev.key !== "End"
    ) {
      return;
    }
    ev.preventDefault();
    const currentIsDevice = this.store.currentScope === "device";
    let nextScope;
    if (ev.key === "Home") {
      nextScope = "device";
    } else if (ev.key === "End") {
      nextScope = "system";
    } else {
      nextScope = currentIsDevice ? "system" : "device";
    }
    if (nextScope === "device") {
      this.store.openDevicesLanding();
      const btn = this.renderRoot.querySelector("#tab-scope-device");
      btn?.focus();
    } else {
      this.store.setScope("system");
      const btn = this.renderRoot.querySelector("#tab-scope-system");
      btn?.focus();
    }
  }
                     updated() {
    syncStudioDialogs(this.renderRoot, this.store);
  }
          _renderDeviceNav() {
    const data = this.store.state;
    const caps = data?.capabilities || {};
    const isBleOnly = data?.config?.kind === "ble_tag";
    const items
       = [{ viewId: "dashboard", label: "Overview" }];
    if (!isBleOnly && caps.has_display !== false) {
      items.push({ viewId: "display", label: "Display", id: "nav-btn-display" });
      items.push({ viewId: "interface", label: "Interface", id: "nav-btn-interface" });
    }
    if (!isBleOnly && (caps.has_audio !== false || caps.has_voice !== false)) {
      items.push({ viewId: "audio_voice", label: "Audio", id: "nav-btn-audio_voice" });
    }
    if (!isBleOnly && caps.has_power) {
      items.push({ viewId: "power", label: "Power", id: "nav-btn-power" });
    }
    items.push({ viewId: "presence", label: "Presence" });
    items.push({ viewId: "tools", label: "Tools" });
    return html`<nav id="nav-scope-device" aria-label="Device pages" class="nav-list">
      <button
        type="button"
        @click=${() => this.store.openDevicesLanding()}
        class="nav-btn nav-back-btn"
      >
        <span>&larr; Managed</span>
      </button>
      <div id="nav-selected-device-label" class="nav-device-title">
        ${data?.title || "—"}
      </div>
      ${items.map((item) => {
        const active = this.store.currentViewId === item.viewId;
        return html`<button
          type="button"
          id=${item.id || nothing}
          data-view=${item.viewId}
          aria-current=${active ? "page" : nothing}
          @click=${() => this.store.switchView(item.viewId)}
          class="nav-btn ${active ? "active" : ""}"
        >
          <span>${item.label}</span>
        </button>`;
      })}
    </nav>`;
  }
          _renderSidebar() {
    const isDeviceScope = this.store.currentScope === "device";
    const deviceCount = (this.store.state?.system_devices || []).length;
    const discoveredLatterCount = (this.store.state?.discovered_latter_devices || []).length;
    const isDeviceListScope =
      !this.store.deviceSelected ||
      this.store.currentViewId === "select_device_prompt" ||
      this.store.currentViewId === "discovered_devices";
    const managedActive =
      isDeviceScope && isDeviceListScope && this.store.currentViewId !== "discovered_devices";
    const discoveredActive = isDeviceScope && this.store.currentViewId === "discovered_devices";
    return html`<aside class="sidebar">
      <div role="tablist" aria-label="Scope" class="scope-tabs">
        <button
          type="button"
          id="tab-scope-device"
          role="tab"
          aria-selected=${isDeviceScope ? "true" : "false"}
          tabindex=${isDeviceScope ? "0" : "-1"}
          @click=${() => this.store.openDevicesLanding()}
          @keydown=${(ev) => this._onScopeTabKeyDown(ev)}
          class="scope-tab ${isDeviceScope ? "active" : ""}"
        >
          Devices
        </button>
        <button
          type="button"
          id="tab-scope-system"
          role="tab"
          aria-selected=${!isDeviceScope ? "true" : "false"}
          tabindex=${!isDeviceScope ? "0" : "-1"}
          @click=${() => this.store.setScope("system")}
          @keydown=${(ev) => this._onScopeTabKeyDown(ev)}
          class="scope-tab ${!isDeviceScope ? "active" : ""}"
        >
          System
        </button>
      </div>

      ${!isDeviceScope
        ? html`<nav id="nav-scope-system" aria-label="System pages" class="nav-list">
            ${SYSTEM_NAV_ITEMS.map((item) => {
              const active = this.store.currentViewId === item.viewId;
              return html`<button
                type="button"
                data-view=${item.viewId}
                aria-current=${active ? "page" : nothing}
                @click=${() => this.store.switchView(item.viewId)}
                class="nav-btn ${active ? "active" : ""}"
              >
                <span>${item.label}</span>
              </button>`;
            })}
          </nav>`
        : !isDeviceListScope
          ? this._renderDeviceNav()
          : html`<nav id="nav-scope-devices-list" aria-label="Devices" class="nav-list">
              <button
                type="button"
                data-view="select_device_prompt"
                aria-current=${managedActive ? "page" : nothing}
                @click=${() => this.store.openDevicesLanding()}
                class="nav-btn ${managedActive ? "active" : ""}"
              >
                <span>Managed</span>
                <span id="nav-system-count" class="nav-badge">${this.store.state ? String(deviceCount) : "—"}</span>
              </button>
              <button
                type="button"
                data-view="discovered_devices"
                aria-current=${discoveredActive ? "page" : nothing}
                @click=${() => this.store.openDiscoveredDevices()}
                class="nav-btn ${discoveredActive ? "active" : ""}"
              >
                <span>Discovered</span>
                ${discoveredLatterCount > 0
                  ? html`<span id="nav-discovered-count" class="nav-badge">${String(discoveredLatterCount)}</span>`
                  : nothing}
              </button>
            </nav>`}
    </aside>`;
  }
                     render() {
    const data = this.store.state;
    const isInitialLoading = this.store.loading && !data && !this.store.loadError && !this.store.studioRevMismatch;
    const showHeaderUpdate =
      this.store.currentScope === "device" &&
      this.store.deviceSelected &&
      this.store.currentViewId !== "select_device_prompt" &&
      this.store.currentViewId !== "discovered_devices" &&
      Boolean(data?.live?.fw_update_available && data?.live?.fw_update_entity);
    const subtitle = this.store.pageSubtitle;
    return html`<div
      id="studio-root"
      @keydown=${(ev) => this._onRootKeyDown(ev)}
      class="studio-root ${isInitialLoading ? "is-loading" : ""}"
    >
      ${this.store.studioRevMismatch
        ? html`<div role="status" class="studio-rev-banner">
            <span>Latter Studio was updated — Reload Page</span>
            <button
              type="button"
              @click=${() => this.store.reloadPage()}
              class="btn btn-primary btn-compact"
            >
              Reload Page
            </button>
          </div>`
        : nothing}

      <header class="latter-top-titlebar">
        <div class="titlebar-brand">
          <button
            type="button"
            aria-label="Toggle the Home Assistant sidebar"
            @click=${() => this.store.toggleParentHaSidebar()}
            class="btn-icon ha-menu-btn"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2Z" />
            </svg>
          </button>
          <span class="titlebar-title">Latter</span>
        </div>
        <div class="titlebar-actions">
          ${showHeaderUpdate
            ? html`<button
                type="button"
                id="hdr-update-pill"
                @click=${() => void this.store.triggerHeaderFirmwareUpdate()}
                class="btn btn-secondary btn-compact"
              >
                Install Update
              </button>`
            : nothing}
        </div>
      </header>

      <div class="app-shell">
        ${this._renderSidebar()}

        <main
          class="main-area"
          @focusout=${() => void this.store.flushAllPendingSettings()}
        >
          <div class="content-wrap">
            <h2 id="unified-page-title" class="page-title">
              <span>${this.store.pageTitle}</span>
              ${subtitle ? html`<span class="page-subtitle">${subtitle}</span>` : nothing}
            </h2>

            ${isInitialLoading
              ? html`<div id="studio-loading" role="status" class="loading-state">
                  Loading Latter…
                </div>`
              : nothing}

            ${!data && this.store.loadError
              ? html`<div id="studio-load-error" role="alert" class="alert alert-error">
                  <span id="studio-load-error-text">${this.store.loadError}</span>
                  <button
                    type="button"
                    @click=${() => void this.store.refreshState()}
                    class="btn btn-secondary btn-compact"
                  >
                    Retry
                  </button>
                </div>`
              : nothing}

            ${data ? renderActiveView(this.store) : nothing}
          </div>
        </main>
      </div>

      ${renderStudioDialogs(this.store)}

      ${this.store.toastMessage
        ? html`<div
            role="status"
            aria-live="polite"
            class="toast ${this.store.toastIsError ? "error" : ""}"
          >
            ${this.store.toastMessage}
          </div>`
        : nothing}
    </div>`;
  }
}
if (!customElements.get("latter-studio")) {
  customElements.define("latter-studio", LatterStudio);
}
