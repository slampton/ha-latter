/**
 * System Device Groups & Batch Controls View (`system_sync`, D-048 / D-050):
 * Column 1: Enclosed per-Group containers with inline expandable Baseline Settings
 *   (Operational settings by default, plus opt-in Display and Interface & Shortcuts).
 * Column 2: Tab-aligned Batch Controls across All, Online, Roaming, Stationary,
 *   any built-in or custom Device Group, or Custom.
 */

import {
  renderCard,
  renderSettingsRow,
  renderSwitchRow,
  renderTrashIconButton,
} from "../components/controls.js";
import {
  ACTIVITY_SOURCES_CATALOG,
  AREA_CATEGORIES_CATALOG,
  DEFAULT_AREA_CATEGORIES_TOKENS,
  DEFAULT_DEVICE_GROUP_IDS,
  DEFAULT_HOME_CATEGORIES_TOKENS,
  HOME_CATEGORIES_CATALOG,
  HOME_CLOCK_TAP_OPTIONS,
  RETURN_TO_HOME_TIMEOUT_OPTIONS,
  SECURITY_PIN_POLICY_OPTIONS,
  START_SCREEN_OPTIONS,
  WALLPAPER_ROTATION_OPTIONS,
} from "../constants.js";
import { html, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { DeviceGroup, SharedControlItem, SharedControlTarget } from "../types.js";
import { entityLabel, fmtNumber } from "../utils/format.js";

const WAKE_WORD_MODE_OPTIONS: ReadonlyArray<string> = ["Docked Only", "Always On", "Disabled"];
const TAP_TO_WAKE_OPTIONS: ReadonlyArray<string> = [
  "Single Tap",
  "Double Tap",
  "Docked Only",
  "Disabled",
];
const WAKE_GESTURE_OPTIONS: ReadonlyArray<string> = ["Always On", "Docked Only", "Disabled"];
const BATTERY_SCREEN_TIMEOUT_OPTIONS: ReadonlyArray<string> = [
  "10s",
  "15s",
  "30s",
  "1 min",
  "2 min",
  "Never",
];
const DOCKED_IDLE_TIMEOUT_OPTIONS: ReadonlyArray<string> = [
  "10s",
  "15s",
  "30s",
  "1 min",
  "2 min",
  "5 min",
  "Never",
];
const BATTERY_HIBERNATE_TIMEOUT_OPTIONS: ReadonlyArray<string> = [
  "5 min",
  "10 min",
  "15 min",
  "30 min",
  "Disabled",
];
const AUTO_BRIGHTNESS_MODE_OPTIONS: ReadonlyArray<string> = [
  "Disabled",
  "Sun Synchronized",
  "Time Schedule",
];
const BRIGHTNESS_PCT_OPTIONS: ReadonlyArray<string> = ["60%", "70%", "80%", "90%", "100%"];
const WW_SENSITIVITY_OPTIONS: ReadonlyArray<string> = [
  "Slightly sensitive",
  "Moderately sensitive",
  "Very sensitive",
];
const BLE_BEACON_MODE_OPTIONS: ReadonlyArray<string> = [
  "Handheld Only",
  "Handheld + Screen Off",
  "Always",
];
const SCREENSAVER_STYLE_OPTIONS: ReadonlyArray<string> = [
  "Ambient Clock",
  "Aurora",
  "Starfield",
  "Digital Rain",
  "Fireworks",
];
const COLOR_PROFILE_OPTIONS: ReadonlyArray<string> = [
  "Steel Blue",
  "Pink",
  "Blue",
  "Green",
  "Custom",
];
const VA_VISUAL_PROFILE_OPTIONS: ReadonlyArray<string> = [
  "Nebula",
  "Solaris",
  "Rings",
  "Light Bar",
  "Dot Wave",
];
const CLOCK_FACE_OPTIONS: ReadonlyArray<string> = [
  "Minimal Digital",
  "Modern Analog",
  "Hybrid Digital",
];
const TIME_FORMAT_OPTIONS: ReadonlyArray<string> = ["12-Hour (AM/PM)", "24-Hour"];
const ALBUM_ART_STYLE_OPTIONS: ReadonlyArray<string> = [
  "Full Screen",
  "Letterbox",
  "Standard",
  "None",
];
const MUSIC_OVERLAY_STYLE_OPTIONS: ReadonlyArray<string> = [
  "Art Only",
  "Art + Metadata",
  "Always Visible",
];
const ALBUM_SORT_OPTIONS: ReadonlyArray<string> = [
  "Alphabetical",
  "Newest on Top",
  "Oldest on Top",
];
const ARTIST_ALBUM_SORT_OPTIONS: ReadonlyArray<string> = [
  "Oldest on Top",
  "Newest on Top",
  "Alphabetical",
];
const PODCAST_SORT_OPTIONS: ReadonlyArray<string> = ["Newest on Top", "Oldest on Top"];

const BATCH_CATEGORY_META: ReadonlyArray<{ id: string; title: string; defaultOpen: boolean }> = [
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
  store: StudioStore,
  groupId: string,
  key: string,
  label: string,
  currentVal: unknown,
  options: ReadonlyArray<string>,
  defaultVal: string,
): TemplateResult {
  const cur = typeof currentVal === "string" && options.includes(currentVal) ? currentVal : defaultVal;
  return renderSettingsRow({
    label,
    control: html`<select
      aria-label=${`${label} for ${groupId}`}
      .value=${cur}
      @change=${(ev: Event) =>
        void store.updateGroupBaseline(groupId, {
          [key]: (ev.currentTarget as HTMLSelectElement).value,
        })}
    >
      ${options.map(
        (opt) => html`<option value=${opt} ?selected=${opt === cur}>${opt}</option>`,
      )}
    </select>`,
  });
}

function renderBaselineLabeledSelect(
  store: StudioStore,
  groupId: string,
  key: string,
  label: string,
  currentVal: unknown,
  options: ReadonlyArray<{ value: string; label: string }>,
  defaultVal: string,
): TemplateResult {
  const curStr = currentVal !== undefined && currentVal !== null ? String(currentVal) : defaultVal;
  const cur = options.some((o) => o.value === curStr) ? curStr : defaultVal;
  return renderSettingsRow({
    label,
    control: html`<select
      aria-label=${`${label} for ${groupId}`}
      .value=${cur}
      @change=${(ev: Event) => {
        const raw = (ev.currentTarget as HTMLSelectElement).value;
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
  store: StudioStore,
  groupId: string,
  key: string,
  label: string,
  currentVal: unknown,
  min: number,
  max: number,
  step: number,
  unit: string,
  defaultVal: number,
): TemplateResult {
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
        @change=${(ev: Event) =>
          void store.updateGroupBaseline(groupId, {
            [key]: Number((ev.currentTarget as HTMLInputElement).value),
          })}
      />`,
  });
}

function renderBaselinePills(
  store: StudioStore,
  groupId: string,
  key: string,
  label: string,
  currentVal: unknown,
  catalog: ReadonlyArray<{ token: string; label: string }>,
  defaultCsv: string,
  minRequired: number,
): TemplateResult {
  const csvStr = typeof currentVal === "string" ? currentVal : defaultCsv;
  const activeSet = new Set(
    csvStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );
  const toggleTok = (tok: string): void => {
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
  store: StudioStore,
  group: DeviceGroup,
  latterDevices: ReadonlyArray<{ subentry_id: string; title: string }>,
): TemplateResult {
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
  const wallpaperOptions: Array<{ value: string; label: string }> = [
    { value: "", label: "None (Weather / Solid)" },
    ...sysWallpapers.map((wp) => ({ value: wp.id, label: wp.name || wp.id })),
  ];
  const rotationOptions: Array<{ value: string; label: string }> = WALLPAPER_ROTATION_OPTIONS.map(
    (o) => ({ value: String(o.value), label: o.label }),
  );
  const remoteGroups = store.state?.system_config?.remote_groups || [];
  const remoteScopeOptions: Array<{ value: string; label: string }> = [
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
    @toggle=${(ev: Event) => {
      const isOpen = (ev.currentTarget as HTMLDetailsElement).open;
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
              @change=${(ev: Event) =>
                void store.updateGroupBaseline(gid, {
                  security_pin_policy: (ev.currentTarget as HTMLSelectElement).value,
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
                        @change=${(ev: Event) =>
                          void store.updateGroupBaseline(gid, {
                            device_custom_color: (
                              ev.currentTarget as HTMLInputElement
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
                  @change=${(ev: Event) => {
                    store.groupCopySourceDrafts?.set(
                      gid,
                      (ev.currentTarget as HTMLSelectElement).value,
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
  filter: string,
  item: { is_online?: boolean; is_roaming?: boolean; device_group?: string },
): boolean {
  if (filter === "all") return true;
  if (filter === "online") return Boolean(item.is_online);
  if (filter === "roaming") return Boolean(item.is_roaming);
  if (filter === "stationary") return !item.is_roaming;
  const grpId = filter.startsWith("group:") ? filter.slice(6) : filter;
  return (item.device_group || "custom") === grpId;
}

export function renderSystemGroupsView(store: StudioStore): TemplateResult {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const latterDevices = allDevices.filter((d) => d.kind !== "ble_tag");
  const groups = data?.device_groups || [];
  const systemControls = data?.system_controls || [];

  const validTargetFilters = new Set<string>([
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

  const renderBatchControlRow = (fc: SharedControlItem): TemplateResult | typeof nothing => {
    const targets = (fc.targets || []).filter((t: SharedControlTarget) =>
      matchesBatchTargetFilter(activeFilter, t),
    );
    if (!targets.length) return nothing;

    const states = Array.from(new Set(targets.map((t) => String(t.state ?? ""))));
    const mixed = states.length > 1;
    const curState = mixed ? "" : (states[0] ?? "");
    const desc = `${fc.section_title} • ${fmtNumber(targets.length, store.hass, 0)} Device${targets.length === 1 ? "" : "s"}${mixed ? " • Mixed values" : ""}`;
    const optLabels = fc.option_labels || {};

    let control: TemplateResult;
    if (fc.domain === "select" && fc.options && fc.options.length) {
      control = html`<select
        aria-label=${fc.name}
        .value=${curState}
        @change=${(ev: Event) =>
          void store.bulkSelect(fc, (ev.currentTarget as HTMLSelectElement).value)}
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
          @change=${(ev: Event) =>
            void store.bulkToggle(fc, (ev.currentTarget as HTMLInputElement).checked)}
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
          @change=${(ev: Event) =>
            void store.bulkNumber(fc, Number((ev.currentTarget as HTMLInputElement).value))}
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
          @change=${(ev: Event) =>
            void store.bulkColor(fc, (ev.currentTarget as HTMLInputElement).value)}
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

  const renderBatchCopyListsSection = (): TemplateResult | typeof nothing => {
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
          @change=${(ev: Event) => {
            store.batchCopySourceSubentryId = (ev.currentTarget as HTMLSelectElement).value;
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
                    @input=${(ev: Event) => {
                      store.newGroupName = (ev.currentTarget as HTMLInputElement).value;
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
                    @input=${(ev: Event) => {
                      store.newGroupDesc = (ev.currentTarget as HTMLInputElement).value;
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
                  @change=${(ev: Event) => {
                    store.newGroupSourceSubentryId = (ev.currentTarget as HTMLSelectElement).value;
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
              @change=${(ev: Event) => {
                store.batchTargetFilter =
                  (ev.currentTarget as HTMLSelectElement).value || "all";
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
              @change=${(ev: Event) => {
                store.batchCategoryFilter =
                  (ev.currentTarget as HTMLSelectElement).value || "all";
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
