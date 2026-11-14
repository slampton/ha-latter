/**
 * Device Display View (`display`, D-027 / D-029 / D-033 / D-034 / D-036):
 * Visual & aesthetic preferences across screens.
 * Column 1: Home Screen (Wake Greeting, Weather Background & Sun & Moon), Screensavers, Voice Assistant (Visual Profile), Brightness & Clock.
 * Column 2: Colors, Wallpapers & Media Player (Album Art & Overlay Style).
 */

import {
  renderCard,
  renderPrefControlRow,
  renderSettingsRow,
} from "../components/controls.js";
import {
  renderWallpaperGalleryItems,
  renderWallpaperUploadProgress,
  renderWallpaperUploadTrigger,
} from "../components/wallpaper-gallery.js";
import { WALLPAPER_ROTATION_OPTIONS } from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { DevicePrefItem } from "../types.js";
import { defaultThemeHex, entityLabel, isValidHexColor } from "../utils/format.js";

export function renderDeviceDisplayView(store: StudioStore): TemplateResult {
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
  ].filter((c): c is { pref: DevicePrefItem; label: string } => Boolean(c.pref));

  const renderCelestialRow = (): TemplateResult =>
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
                  @change=${(ev: Event) => {
                    const val = (ev.currentTarget as HTMLSelectElement).value;
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
                    @change=${(ev: Event) =>
                      void store.setWallpaperRotation(
                        Number((ev.currentTarget as HTMLSelectElement).value) || 0,
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
