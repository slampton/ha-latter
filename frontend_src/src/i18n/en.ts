/**
 * Canonical English Studio UI string catalog (`D-061` — Home Assistant Sentence case).
 * Composed from disjoint slices (`en-common.ts`, `en-system.ts`, `en-devices.ts`) and mirrored
 * deterministically to `custom_components/latter/studio/locales/en.json` by `build.mjs`.
 */

import { EN_COMMON_STRINGS } from "./en-common.js";
import { EN_DEVICES_STRINGS } from "./en-devices.js";
import { EN_SYSTEM_STRINGS } from "./en-system.js";

export { EN_COMMON_STRINGS, EN_DEVICES_STRINGS, EN_SYSTEM_STRINGS };

export const EN_STRINGS = {
  ...EN_COMMON_STRINGS,
  ...EN_SYSTEM_STRINGS,
  ...EN_DEVICES_STRINGS,
} as const;

export type StudioTranslationKey = keyof typeof EN_STRINGS;

/**
 * Sentence-case labels for all 50 `DevicePrefSpec` keys + group/device setting keys.
 */
export const PREF_LABELS: Readonly<Record<string, string>> = {
  wake_word_mode: "Wake word mode",
  tap_to_wake: "Tap to wake",
  pickup_to_wake: "Pickup to wake",
  battery_screen_timeout: "Battery screen timeout",
  docked_idle_timeout: "Docked idle timeout",
  battery_hibernate_timeout: "Battery hibernate timeout",
  docked_screensaver: "Docked screensaver",
  screensaver_style: "Screensaver style",
  hold_crown_power_off: "Hold crown to power off",
  auto_brightness_mode: "Auto brightness mode",
  manual_brightness: "Manual brightness",
  day_brightness: "Day brightness",
  night_brightness: "Night brightness",
  day_start_hour: "Day start hour",
  night_start_hour: "Night start hour",
  color_profile: "Color profile",
  va_visual_profile: "Visual profile",
  home_screen_enabled: "Enable Home screen",
  start_screen: "Start screen",
  return_to_home_timeout: "Return to Home timeout",
  clock_face: "Clock face",
  time_format: "Time format",
  weather_background: "Weather background",
  home_sun: "Sun",
  home_moon: "Moon",
  wake_greeting: "Wake greeting",
  album_art_style: "Album art style",
  music_overlay_style: "Overlay style",
  album_sort_order: "Album sort order",
  artist_album_sort_order: "Artist album sort order",
  podcast_sort_order: "Podcast sort order",
  ww_sens_okay_nabu: "Okay Nabu sensitivity",
  ww_sens_hey_luna: "Hey Luna sensitivity",
  ww_sens_hey_jarvis: "Hey Jarvis sensitivity",
  ww_sens_hey_mycroft: "Hey Mycroft sensitivity",
  ww_sens_alexa: "Alexa sensitivity",
  wake_screen_on_assist: "Wake screen on Assist",
  alert_volume: "Alert volume",
  volume_step_size: "Volume step size",
  game_sound_effects: "Game sound effects",
  ble_beacon_mode: "BLE beacon mode",
  weather_sim_condition: "Weather simulation",
  home_clock_tap_action: "Home time tap",
  home_date_tap_action: "Home date tap",
  local_clock_label: "Local clock label",
  show_utc_clock: "Show UTC clock",
  world_clocks: "World clocks",
  alarms_summary: "Alarms",
  calendar_lookahead_days: "Overview lookahead",
  calendar_week_start: "Start week on",
  // Non-pref group & Device config keys
  native_ble_tracking: "BLE Area tracking",
  ble_auto_switch: "Auto-switch active Area",
  sync_device_area: "Voice Follows Me",
  area_follow_dwell_s: "Area follow dwell",
  area_handoff: "Media Area handoff",
  security_pin_policy: "Perimeter security policy",
  wallpaper_source: "Wallpaper",
  wallpaper_cycle_minutes: "Wallpaper rotation",
  device_custom_color: "Custom color",
  device_remote_group: "Remote control scope",
  activity_card: "Show Activity card",
  activity_sources: "Activity card sources",
  area_categories: "Area categories",
  home_categories: "Home categories",
  tools_items: "Enabled tools",
  games_items: "Enabled games",
};

/**
 * Maps canonical wire option strings (`protocol_v3.json` / ESPHome select options) to
 * localized Sentence-case display labels without changing wire values.
 */
export const PREF_OPTION_LABELS: Readonly<Record<string, string>> = {
  // Wake & power options
  "Docked Only": "Docked only",
  "Always On": "Always on",
  Disabled: "Disabled",
  "Single Tap": "Single tap",
  "Double Tap": "Double tap",
  Never: "Never",
  "10s": "10 seconds",
  "15s": "15 seconds",
  "30s": "30 seconds",
  "1 min": "1 minute",
  "2 min": "2 minutes",
  "5 min": "5 minutes",
  "10 min": "10 minutes",
  "15 min": "15 minutes",
  "30 min": "30 minutes",

  // Screensaver, brightness & colors
  "Ambient Clock": "Ambient clock",
  Aurora: "Aurora",
  Starfield: "Starfield",
  "Digital Rain": "Digital rain",
  Fireworks: "Fireworks",
  "Sun Synchronized": "Sun synchronized",
  "Time Schedule": "Time schedule",
  "60%": "60%",
  "70%": "70%",
  "80%": "80%",
  "90%": "90%",
  "100%": "100%",
  "Steel Blue": "Steel blue",
  Pink: "Pink",
  Blue: "Blue",
  Green: "Green",
  Custom: "Custom",
  Nebula: "Nebula",
  Solaris: "Solaris",
  Rings: "Rings",
  "Light Bar": "Light bar",
  "Dot Wave": "Dot wave",

  // Home, start screen, clock & calendar
  Home: "Home",
  Pinned: "Pinned",
  "Time App": "Time app",
  Calendar: "Calendar",
  "Clock Face": "Clock face",
  Media: "Media",
  "Home Hub": "Home hub",
  "Area Controls": "Area controls",
  Remote: "Remote",
  Weather: "Weather",
  Cameras: "Cameras",
  Games: "Games",
  Tools: "Tools",
  "Minimal Digital": "Minimal digital",
  "Modern Analog": "Modern analog",
  "Hybrid Digital": "Hybrid digital",
  "12-Hour (AM/PM)": "12-hour (AM/PM)",
  "24-Hour": "24-hour",
  "Day View": "Day view",
  Overview: "Overview",
  Sunday: "Sunday",
  Monday: "Monday",

  // Music & media
  "Full Screen": "Full screen",
  Letterbox: "Letterbox",
  Standard: "Standard",
  None: "None",
  "Art Only": "Art only",
  "Art + Metadata": "Art + metadata",
  "Always Visible": "Always visible",
  Alphabetical: "Alphabetical",
  "Newest on Top": "Newest on top",
  "Oldest on Top": "Oldest on top",

  // Wake word sensitivity & BLE beacon
  "Slightly sensitive": "Slightly sensitive",
  "Moderately sensitive": "Moderately sensitive",
  "Very sensitive": "Very sensitive",
  "Handheld Only": "Handheld only",
  "Handheld + Screen Off": "Handheld + screen off",
  Always: "Always",

  // Weather simulation
  "Live (Home Assistant)": "Live (Home Assistant)",
  "Clear Night": "Clear night",
  "Sunny / Clear Day": "Sunny / clear day",
  "Partly Cloudy (Day)": "Partly cloudy (day)",
  "Partly Cloudy (Night)": "Partly cloudy (night)",
  "Cloudy / Overcast (Day)": "Cloudy / overcast (day)",
  "Cloudy / Overcast (Night)": "Cloudy / overcast (night)",
  "Fog / Mist (Day)": "Fog / mist (day)",
  "Fog / Mist (Night)": "Fog / mist (night)",
  "Rainy (Day)": "Rainy (day)",
  "Rainy (Night)": "Rainy (night)",
  "Pouring / Heavy Rain": "Pouring / heavy rain",
  "Snow (Day)": "Snow (day)",
  "Snow (Night)": "Snow (night)",
  "Thunderstorm (Day)": "Thunderstorm (day)",
  "Thunderstorm (Night)": "Thunderstorm (night)",
  Windy: "Windy",

  // Security PIN policy wire tokens
  auto: "Auto (recommended)",
  allow: "Allow without PIN",
  require_pin: "Require PIN",
  block: "Block unlock & disarm",
};

/**
 * Builds the complete deterministic flat JSON catalog written to
 * `custom_components/latter/studio/locales/en.json`.
 */
export function buildStudioEnLocaleCatalog(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(EN_STRINGS)) {
    out[k] = v;
  }
  for (const [k, v] of Object.entries(PREF_LABELS)) {
    out[`pref.${k}`] = v;
  }
  for (const [k, v] of Object.entries(PREF_OPTION_LABELS)) {
    out[`pref_option.${k}`] = v;
  }
  return out;
}
