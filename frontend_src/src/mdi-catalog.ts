/**
 * Universal Shortcut Engine catalogs: domain action maps, route icon previews,
 * and firmware-verified Material Design Icons (`ui_mdi.cpp` 7,447-icon parity).
 */


import {
  MDI_SEARCH_SYNONYMS,
  MDI_TOTAL_ICON_COUNT,
  PACKED_MDI_CHUNKS,
} from "./mdi-chunks.js";

export { MDI_TOTAL_ICON_COUNT };
export type MdiIconStyleFilter = "all" | "solid" | "outline";
export const SHORTCUT_DOMAIN_ACTIONS: Readonly<
  Record<string, ReadonlyArray<{ action: string; label: string }>>
> = {
  light: [
    { action: "toggle", label: "Toggle" },
    { action: "turn_on", label: "Turn on" },
    { action: "turn_off", label: "Turn off" },
  ],
  switch: [
    { action: "toggle", label: "Toggle" },
    { action: "turn_on", label: "Turn on" },
    { action: "turn_off", label: "Turn off" },
  ],
  input_boolean: [
    { action: "toggle", label: "Toggle" },
    { action: "turn_on", label: "Turn on" },
    { action: "turn_off", label: "Turn off" },
  ],
  fan: [
    { action: "toggle", label: "Toggle" },
    { action: "turn_on", label: "Turn on" },
    { action: "turn_off", label: "Turn off" },
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
    { action: "toggle", label: "Toggle enable" },
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
    { action: "arm_home", label: "Arm home" },
    { action: "arm_away", label: "Arm away" },
    { action: "arm_night", label: "Arm night" },
    { action: "arm_vacation", label: "Arm vacation" },
  ],
  vacuum: [
    { action: "start", label: "Start" },
    { action: "pause", label: "Pause" },
    { action: "return_to_base", label: "Return to base" },
    { action: "stop", label: "Stop" },
    { action: "clean_spot", label: "Spot clean" },
    { action: "locate", label: "Locate" },
  ],
  lawn_mower: [
    { action: "start_mowing", label: "Start mowing" },
    { action: "pause", label: "Pause" },
    { action: "dock", label: "Dock" },
  ],
  media_player: [
    { action: "media_play_pause", label: "Play / pause" },
    { action: "turn_on", label: "Turn on" },
    { action: "turn_off", label: "Turn off" },
    { action: "media_next_track", label: "Next track" },
  ],
  climate: [
    { action: "turn_on", label: "Turn on" },
    { action: "turn_off", label: "Turn off" },
  ],
  humidifier: [
    { action: "toggle", label: "Toggle" },
    { action: "turn_on", label: "Turn on" },
    { action: "turn_off", label: "Turn off" },
  ],
  siren: [
    { action: "turn_on", label: "Turn on" },
    { action: "turn_off", label: "Turn off" },
  ],
  water_heater: [
    { action: "turn_on", label: "Turn on" },
    { action: "turn_off", label: "Turn off" },
  ],
  select: [
    { action: "select_next", label: "Next option" },
    { action: "select_previous", label: "Previous option" },
  ],
  input_select: [
    { action: "select_next", label: "Next option" },
    { action: "select_previous", label: "Previous option" },
  ],
};

export const SHORTCUT_DOMAIN_LABELS: Readonly<Record<string, string>> = {
  alarm_control_panel: "Security alarm",
  automation: "Automations",
  button: "Buttons",
  climate: "Climate",
  cover: "Covers & blinds",
  fan: "Fans",
  humidifier: "Humidifiers",
  input_boolean: "Input booleans",
  input_button: "Input buttons",
  input_select: "Input selects",
  lawn_mower: "Lawn mowers",
  light: "Lights",
  lock: "Locks",
  media_player: "Media players",
  scene: "Scenes",
  script: "Scripts",
  select: "Selects",
  siren: "Sirens",
  switch: "Switches",
  vacuum: "Vacuums",
  valve: "Valves",
  water_heater: "Water heaters",
};

export function shortcutActionLabel(domain: string, action: string): string {
  const list = SHORTCUT_DOMAIN_ACTIONS[domain] || [];
  const found = list.find((it) => it.action === action);
  return found ? found.label : action;
}

export const ROUTE_PREVIEW_ICONS: Readonly<Record<string, string>> = {
  "app:pinned": "mdi:pin",
  "app:music": "mdi:music",
  "music:speakers": "mdi:speaker-multiple",
  "music:library": "mdi:music-box",
  "music:favorites": "mdi:heart",
  "music:playlists": "mdi:playlist-music",
  "music:queue": "mdi:playlist-play",
  "music:album_tracks": "mdi:album",
  "music:lyrics": "mdi:script-text",
  "music:info": "mdi:information",
  "app:home_hub": "mdi:home",
  "home_hub:alarm": "mdi:shield-home",
  "home_hub:intercom": "mdi:bullhorn",
  "home_hub:thermostat": "mdi:thermostat",
  "home_hub:entry": "mdi:lock",
  "home_hub:vacuum": "mdi:robot-vacuum",
  "app:cameras": "mdi:cctv",
  "cameras:grid": "mdi:view-grid",
  "cameras:single": "mdi:video",
  "cameras:carousel": "mdi:view-carousel",
  "cameras:settings": "mdi:cog",
  "app:area": "mdi:sofa",
  "area:picker": "mdi:floor-plan",
  "area:scene": "mdi:shimmer",
  "area:light": "mdi:lightbulb",
  "area:cover": "mdi:blinds-horizontal",
  "area:climate": "mdi:thermometer",
  "area:fan": "mdi:fan",
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
  "app:time": "mdi:clock",
  "time:clock": "mdi:clock",
  "time:timers": "mdi:timer-sand",
  "time:alarms": "mdi:alarm",
  "time:stopwatch": "mdi:timer",
  "app:clock": "mdi:clock",
  "app:calendar": "mdi:calendar",
  "calendar:overview": "mdi:calendar-text",
  "calendar:day": "mdi:calendar-today",
  "calendar:week": "mdi:calendar-week",
  "calendar:month": "mdi:calendar-month",
  "app:tools": "mdi:view-grid",
  "tools:stopwatch": "mdi:timer",
  "tools:level": "mdi:spirit-level",
  "tools:flashlight": "mdi:flashlight",
  "tools:calculator": "mdi:calculator-variant",
  "tools:dice": "mdi:dice-5",
  "tools:coin_flip": "mdi:alpha-c-circle",
  "app:games": "mdi:controller",
  "games:marbles": "mdi:billiards",
  "games:archery": "mdi:bullseye-arrow",
  "games:bricks": "mdi:wall",
  "games:chomp": "mdi:pac-man",
  "games:blocks": "mdi:toy-brick",
  "games:snake": "mdi:snake",
  "games:drop_four": "mdi:dots-grid",
  "settings:display": "mdi:brightness-6",
  "settings:sleep": "mdi:power-sleep",
  "settings:sound": "mdi:volume-high",
  "settings:voice": "mdi:microphone",
  "settings:music": "mdi:music-box",
  "settings:home": "mdi:home",
  "settings:actions": "mdi:gesture-tap-button",
  "settings:update": "mdi:cellphone-arrow-down",
  "settings:info": "mdi:information",
};

const MDI_SLUG_PATTERN = /^mdi:[a-z0-9]+(?:-[a-z0-9]+)*$/;
const BARE_MDI_SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export function normalizeMdiIconSlug(raw: unknown): string {
  let clean = String(raw ?? "").trim().toLowerCase().replace(/_/g, "-");
  if (!clean) return "";
  if (clean.startsWith("mdi-")) {
    clean = `mdi:${clean.slice(4)}`;
  } else if (!clean.startsWith("mdi:") && BARE_MDI_SLUG_PATTERN.test(clean)) {
    clean = `mdi:${clean}`;
  }
  return MDI_SLUG_PATTERN.test(clean) ? clean : "";
}

export const CURATED_MDI_ICONS: ReadonlyArray<string> = [
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
  "mdi:controller",
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
  "mdi:view-grid-outline",
  "mdi:form-select",
];

// Replaced at bundle build time with `./latter-studio-mdi.js?v=<sha256-16>` while PACKED_MDI_CHUNKS
// stays intact in TypeScript source for cross-repo 7,447-icon firmware parity verification.
const MDI_LAZY_CHUNK_URL = "__LATTER_MDI_CHUNK_URL__";

let activePackedMdiChunks: ReadonlyArray<string> = PACKED_MDI_CHUNKS;
let activeMdiSynonyms: Readonly<Record<string, ReadonlyArray<string>>> = MDI_SEARCH_SYNONYMS;
let cachedAllMdiIcons: string[] | null = null;
let cachedAllMdiSet: Set<string> | null = null;
let cachedStyleCounts: { solid: number; outline: number } | null = null;
let cachedOutlinePopular: string[] | null = null;
let curatedIconSet: Set<string> | null = null;
let curatedFallbackSet: Set<string> | null = null;
let mdiLoadPromise: Promise<void> | null = null;

function getCuratedIconSet(): Set<string> {
  if (curatedIconSet === null) {
    curatedIconSet = new Set(CURATED_MDI_ICONS);
  }
  return curatedIconSet;
}

function matchesStyleFilter(fullSlug: string, styleFilter: MdiIconStyleFilter): boolean {
  if (styleFilter === "all") return true;
  const isOutline = fullSlug.endsWith("-outline");
  return styleFilter === "outline" ? isOutline : !isOutline;
}

function unpackMdiChunks(chunks: ReadonlyArray<string>): string[] {
  const out: string[] = [];
  let prev = "";
  for (const chunk of chunks) {
    for (const token of chunk.split("|")) {
      if (!token) continue;
      const prefix = token[0];
      if (!prefix) continue;
      const shared = parseInt(prefix, 36);
      const slug = prev.slice(0, shared) + token.slice(1);
      prev = slug;
      out.push(`mdi:${slug}`);
    }
  }
  return out;
}

export function isMdiCatalogLoaded(): boolean {
  return activePackedMdiChunks.length > 0;
}

export function registerPackedMdiChunks(
  chunks: ReadonlyArray<string>,
  synonyms?: Readonly<Record<string, ReadonlyArray<string>>>,
): void {
  if (!Array.isArray(chunks) || chunks.length === 0) return;
  activePackedMdiChunks = chunks;
  if (synonyms && typeof synonyms === "object") {
    activeMdiSynonyms = synonyms;
  }
  cachedAllMdiIcons = null;
  cachedAllMdiSet = null;
  cachedStyleCounts = null;
  cachedOutlinePopular = null;
}

export function ensureMdiCatalogLoaded(): Promise<void> {
  if (activePackedMdiChunks.length > 0) {
    return Promise.resolve();
  }
  if (mdiLoadPromise) {
    return mdiLoadPromise;
  }
  mdiLoadPromise = import(MDI_LAZY_CHUNK_URL)
    .then(
      (mod: {
        PACKED_MDI_CHUNKS?: ReadonlyArray<string>;
        MDI_SEARCH_SYNONYMS?: Readonly<Record<string, ReadonlyArray<string>>>;
      }) => {
        if (mod && Array.isArray(mod.PACKED_MDI_CHUNKS)) {
          registerPackedMdiChunks(mod.PACKED_MDI_CHUNKS, mod.MDI_SEARCH_SYNONYMS);
        }
      },
    )
    .catch((err: unknown) => {
      mdiLoadPromise = null;
      throw err;
    });
  return mdiLoadPromise;
}

export function getAllMdiIcons(): ReadonlyArray<string> {
  if (activePackedMdiChunks.length === 0) {
    return CURATED_MDI_ICONS;
  }
  if (cachedAllMdiIcons !== null) {
    return cachedAllMdiIcons;
  }
  cachedAllMdiIcons = unpackMdiChunks(activePackedMdiChunks);
  return cachedAllMdiIcons;
}

function getAllMdiSet(): Set<string> {
  if (cachedAllMdiSet === null) {
    cachedAllMdiSet = new Set(getAllMdiIcons());
  }
  return cachedAllMdiSet;
}

function getStyleCounts(): { solid: number; outline: number } {
  if (cachedStyleCounts !== null) {
    return cachedStyleCounts;
  }
  const icons = getAllMdiIcons();
  let outline = 0;
  for (const slug of icons) {
    if (slug.endsWith("-outline")) outline += 1;
  }
  const result = { solid: icons.length - outline, outline };
  if (activePackedMdiChunks.length > 0) {
    cachedStyleCounts = result;
  }
  return result;
}

function getPopularOutlineIcons(limit: number): ReadonlyArray<string> {
  if (cachedOutlinePopular !== null && cachedOutlinePopular.length >= limit) {
    return cachedOutlinePopular.slice(0, limit);
  }
  const seen = new Set<string>();
  const out: string[] = [];
  const push = (slug: string): void => {
    if (!seen.has(slug)) {
      seen.add(slug);
      out.push(slug);
    }
  };
  for (const slug of CURATED_MDI_ICONS) {
    if (slug.endsWith("-outline")) {
      push(slug);
    }
  }
  if (activePackedMdiChunks.length > 0) {
    const allSet = getAllMdiSet();
    for (const slug of CURATED_MDI_ICONS) {
      if (!slug.endsWith("-outline")) {
        const outlinePair = `${slug}-outline`;
        if (allSet.has(outlinePair)) {
          push(outlinePair);
        }
      }
    }
    if (out.length < limit) {
      for (const slug of getAllMdiIcons()) {
        if (slug.endsWith("-outline")) {
          push(slug);
          if (out.length >= limit) break;
        }
      }
    }
    cachedOutlinePopular = out;
  }
  return out.slice(0, limit);
}

export function isKnownMdiIcon(icon: string): boolean {
  const norm = normalizeMdiIconSlug(icon);
  if (!norm) return false;
  if (activePackedMdiChunks.length === 0) {
    if (curatedFallbackSet === null) {
      curatedFallbackSet = new Set([
        ...CURATED_MDI_ICONS,
        ...Object.values(ROUTE_PREVIEW_ICONS),
      ]);
    }
    return curatedFallbackSet.has(norm);
  }
  return getAllMdiSet().has(norm);
}

function hasWholeWordToken(name: string, term: string): boolean {
  if (name === term) return true;
  if (name.startsWith(`${term}-`)) return true;
  if (name.endsWith(`-${term}`)) return true;
  return name.includes(`-${term}-`);
}

function collectSynonymsForTerm(term: string): ReadonlyArray<string> {
  const direct = activeMdiSynonyms[term];
  if (direct && direct.length > 0) return direct;
  if (term.length > 4 && term.endsWith("es")) {
    const stem = term.slice(0, -2);
    const hit = activeMdiSynonyms[stem];
    if (hit && hit.length > 0) return hit;
  }
  if (term.length > 3 && term.endsWith("s")) {
    const stem = term.slice(0, -1);
    const hit = activeMdiSynonyms[stem];
    if (hit && hit.length > 0) return hit;
  }
  return [];
}

export function searchMdiIcons(
  rawQuery: string,
  limit = 120,
  styleFilter: MdiIconStyleFilter = "all",
): { items: ReadonlyArray<string>; totalMatches: number } {
  const cleaned = String(rawQuery || "")
    .trim()
    .toLowerCase()
    .replace(/^mdi[-:]/, "")
    .replace(/[_\s]+/g, "-");
  const tokens = cleaned.split("-").filter(Boolean);
  if (tokens.length === 0) {
    if (styleFilter === "all") {
      return {
        items: CURATED_MDI_ICONS.slice(0, limit),
        totalMatches: MDI_TOTAL_ICON_COUNT,
      };
    }
    const counts = getStyleCounts();
    if (styleFilter === "solid") {
      const solidPopular = CURATED_MDI_ICONS.filter((s) => !s.endsWith("-outline"));
      return {
        items: solidPopular.slice(0, limit),
        totalMatches: counts.solid,
      };
    }
    return {
      items: getPopularOutlineIcons(limit),
      totalMatches: counts.outline,
    };
  }

  const firstToken = tokens[0] ?? "";
  const exactNeedle = tokens.join("-");
  const joinedNeedle = tokens.join("");
  const phraseSynonyms = new Set<string>();
  for (const syn of collectSynonymsForTerm(exactNeedle)) phraseSynonyms.add(syn);
  if (joinedNeedle !== exactNeedle) {
    for (const syn of collectSynonymsForTerm(joinedNeedle)) phraseSynonyms.add(syn);
  }
  const tokenSynonymLists: ReadonlyArray<ReadonlyArray<string>> = tokens.map((tok) =>
    collectSynonymsForTerm(tok),
  );
  const hasAnySynonyms =
    phraseSynonyms.size > 0 || tokenSynonymLists.some((list) => list.length > 0);
  const isShortSynonymAbbrev =
    tokens.length === 1 && exactNeedle.length <= 2 && phraseSynonyms.size > 0;
  const curatedSet = getCuratedIconSet();

  const ranked: Array<{ slug: string; rank: number; subRank: number }> = [];
  for (const fullSlug of getAllMdiIcons()) {
    if (!matchesStyleFilter(fullSlug, styleFilter)) continue;
    const name = fullSlug.slice(4);
    let allFound = true;
    for (const tok of tokens) {
      if (!name.includes(tok)) {
        allFound = false;
        break;
      }
    }
    if (allFound) {
      let rank = 3;
      if (name === exactNeedle) {
        rank = 0;
      } else if (isShortSynonymAbbrev) {
        if (name.startsWith(`${exactNeedle}-`)) {
          rank = 1;
        } else if (hasWholeWordToken(name, exactNeedle)) {
          rank = 2;
        } else {
          // Demote accidental 2-letter partial-word matches (e.g. `account` for `"ac"`)
          // below curated synonym matches (`mdi:air-conditioner`) so short abbreviations work.
          rank = 5;
        }
      } else if (name.startsWith(exactNeedle)) {
        rank = 1;
      } else if (firstToken && (name.includes(`-${firstToken}`) || name.startsWith(firstToken))) {
        rank = 2;
      }
      ranked.push({ slug: fullSlug, rank, subRank: 0 });
      continue;
    }

    if (!hasAnySynonyms) continue;

    let matchedSynonym = false;
    let exactSynonymHit = false;
    if (phraseSynonyms.size > 0) {
      for (const syn of phraseSynonyms) {
        if (hasWholeWordToken(name, syn)) {
          matchedSynonym = true;
          if (name === syn || name === `${syn}-outline`) {
            exactSynonymHit = true;
            break;
          }
        }
      }
    }
    if (!matchedSynonym && tokens.length > 1) {
      let allTokensSatisfied = true;
      let usedAnySynonym = false;
      for (let i = 0; i < tokens.length; i += 1) {
        const tok = tokens[i] ?? "";
        if (name.includes(tok)) continue;
        const syns = tokenSynonymLists[i] ?? [];
        const hit = syns.find((syn) => hasWholeWordToken(name, syn));
        if (!hit) {
          allTokensSatisfied = false;
          break;
        }
        usedAnySynonym = true;
        if (name === hit || name === `${hit}-outline`) {
          exactSynonymHit = true;
        }
      }
      if (allTokensSatisfied && usedAnySynonym) {
        matchedSynonym = true;
      }
    }

    if (matchedSynonym) {
      const subRank = (exactSynonymHit ? 0 : 2) + (curatedSet.has(fullSlug) ? 0 : 1);
      ranked.push({ slug: fullSlug, rank: 4, subRank });
    }
  }
  ranked.sort(
    (a, b) => a.rank - b.rank || a.subRank - b.subRank || a.slug.localeCompare(b.slug),
  );
  return {
    items: ranked.slice(0, limit).map((r) => r.slug),
    totalMatches: ranked.length,
  };
}
