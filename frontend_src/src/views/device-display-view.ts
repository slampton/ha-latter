/**
 * Device Display View (`display`, `D-027`, `D-029`, `D-033`, `D-034`, `D-036`, `D-066`, `Q7`):
 * Disambiguated visual & aesthetic preferences across screens:
 * - Column 1: Home screen appearance (Wake greeting, Weather background, Sun & Moon pills),
 *   Screensaver, Voice assistant, Brightness, & Clock.
 * - Column 2: Colors (`isValidHexColor` validation), Wallpapers, & Music appearance.
 */

import {
  renderCard,
  renderPillList,
  renderPrefControlRow,
  renderSettingsRow,
} from "../components/controls.js";
import {
  renderWallpaperGalleryItems,
  renderWallpaperUploadProgress,
  renderWallpaperUploadTrigger,
} from "../components/wallpaper-gallery.js";
import { WALLPAPER_ROTATION_OPTIONS } from "../constants.js";
import type { StudioTranslationKey } from "../i18n/index.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { DevicePrefItem } from "../types.js";
import { defaultThemeHex, entityLabel, fmtNumber, isValidHexColor } from "../utils/format.js";
import {
  defaultLocaleTimeFormat,
  renderDeviceOfflineBanner,
} from "./device-overview-view.js";

function rotationLabel(store: StudioStore, minutes: number, fallback: string): string {
  const key = `dev_display.rot_${minutes}` as StudioTranslationKey;
  const translated = store.t(key);
  return translated === key ? fallback : translated;
}

export function renderDeviceDisplayView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const palettes = (data?.system_config?.custom_palettes || []).filter((p) =>
    isValidHexColor(p.hex),
  );
  const curDevEntry =
    (data?.system_devices || []).find((d) => d.subentry_id === store.activeSubentryId) ||
    (data?.system_devices || []).find((d) => d.is_current);
  const isOffline = curDevEntry?.is_online === false;

  // Home screen appearance card
  const wakeGreetingPref = store.entity.getPref("wake_greeting");
  const weatherBgPref = store.entity.getPref("weather_background");
  const weatherBgVal = String(weatherBgPref?.value ?? "").toLowerCase();
  const weatherBgOff =
    !weatherBgPref || !weatherBgPref.value || weatherBgVal === "off" || weatherBgVal === "disabled";
  const sunPref = store.entity.getPref("home_sun");
  const moonPref = store.entity.getPref("home_moon");
  const celestialItems = [sunPref, moonPref].filter(
    (p): p is DevicePrefItem => Boolean(p),
  );

  const renderCelestialRow = (): TemplateResult =>
    renderSettingsRow({
      id: "weather-celestial-bodies",
      label: store.t("dev_display.sun_moon_label"),
      description: store.t("dev_display.sun_moon_desc"),
      control: renderPillList({
        id: "weather-celestial-pills",
        ariaLabel: store.t("dev_display.sun_moon_label"),
        items: celestialItems.map((pref) => ({
          token: pref.key,
          label: store.tPrefLabel(pref.key, pref.label),
          enabled: Boolean(pref.value),
        })),
        onToggle: (token, nextEnabled) => {
          store.entity.stageDeviceSetting(token, nextEnabled);
        },
        overlay: store.localeOverlay,
      }),
    });

  const hasHomeCard = Boolean(wakeGreetingPref || weatherBgPref || celestialItems.length > 0);

  // Screensaver card
  const screensaverPrefs = store.entity.getPrefs([
    "docked_screensaver",
    "screensaver_style",
    "docked_idle_timeout",
  ]);
  const activateScreensaverBtn = store.entity
    .getSectionItems("actions")
    .find(
      (it) =>
        it.domain === "button" &&
        (it.device_command === "activate_screensaver" ||
          it.key === "activate_screensaver" ||
          it.entity_id?.endsWith("_activate_screensaver")),
    );

  // Voice assistant card
  const voiceVisualPref = store.entity.getPref("va_visual_profile");

  // Brightness card
  const autoBrtPref = store.entity.getPref("auto_brightness_mode");
  const autoBrtState = String(autoBrtPref?.value ?? "").trim();
  const autoBrtOff = autoBrtState === "Disabled" || autoBrtState === "off";
  const autoBrtTimeSchedule = autoBrtState === "Time Schedule";

  const brightnessPrefs = store.entity.getPrefs([
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

  // Clock card (default unset `time_format` from `hass.locale?.time_format`, `D-14`)
  const clockPrefs = store.entity.getPrefs(["clock_face", "time_format"]).map((p) => {
    if (
      p.key === "time_format" &&
      (p.value === undefined || p.value === null || String(p.value).trim() === "")
    ) {
      return { ...p, value: defaultLocaleTimeFormat(store.hass) };
    }
    return p;
  });

  // Column 2: Colors card (`isValidHexColor` validation, `A-07`)
  const colorProfilePref = store.entity.getPref("color_profile");
  const rawThemeHex = defaultThemeHex(store.host);
  const safeThemeHex = isValidHexColor(rawThemeHex)
    ? rawThemeHex.toUpperCase()
    : defaultThemeHex(null);
  const curHex = isValidHexColor(cfg.device_custom_color)
    ? String(cfg.device_custom_color).toUpperCase()
    : safeThemeHex;
  const swatchStyle = `--swatch-color:${curHex}`;

  // Column 2: Wallpapers
  const curCycle = Number(cfg.wallpaper_cycle_minutes || 0);
  const wallpapers = data?.wallpapers || [];
  const activeWp = wallpapers.find((wp) => Boolean(wp.active)) || null;
  const hasActiveWallpaper = Boolean(activeWp);
  const isRotating = curCycle > 0;
  const starredCount = wallpapers.filter((wp) => Boolean(wp.favorite)).length;
  const allStarred = wallpapers.length > 0 && starredCount === wallpapers.length;

  let wpStatusText: string;
  if (isRotating) {
    if (activeWp) {
      if (starredCount === 1) {
        wpStatusText = store.t("dev_display.wp_rotating_named_starred_one", {
          name: activeWp.name,
        });
      } else if (starredCount > 1) {
        wpStatusText = store.t("dev_display.wp_rotating_named_starred_many", {
          name: activeWp.name,
          count: fmtNumber(starredCount, store.hass, 0),
        });
      } else {
        wpStatusText = store.t("dev_display.wp_rotating_named_all", {
          name: activeWp.name,
          count: fmtNumber(wallpapers.length, store.hass, 0),
        });
      }
    } else if (starredCount === 1) {
      wpStatusText = store.t("dev_display.wp_rotating_starred_one");
    } else if (starredCount > 1) {
      wpStatusText = store.t("dev_display.wp_rotating_starred_many", {
        count: fmtNumber(starredCount, store.hass, 0),
      });
    } else {
      wpStatusText = store.t("dev_display.wp_rotating_all", {
        count: fmtNumber(wallpapers.length, store.hass, 0),
      });
    }
  } else if (hasActiveWallpaper) {
    wpStatusText = store.t("dev_display.wp_static_named", {
      name: activeWp?.name || store.t("common.active"),
    });
  } else {
    wpStatusText = store.t("dev_display.wp_off");
  }

  const wpRotationHint =
    starredCount === 0
      ? store.t("dev_display.wp_hint_none")
      : starredCount === 1
        ? store.t("dev_display.wp_hint_one")
        : store.t("dev_display.wp_hint_many", {
            starred: fmtNumber(starredCount, store.hass, 0),
            total: fmtNumber(wallpapers.length, store.hass, 0),
          });

  // Column 2: Music appearance card (`Q7` / `E-20`)
  const mediaAppearancePrefs = store.entity.getPrefs([
    "album_art_style",
    "music_overlay_style",
  ]);

  return html`<section id="view-display">
    ${renderDeviceOfflineBanner(store)}

    <div class="columns">
      <div class="column">
        ${hasHomeCard
          ? renderCard({
              heading: html`<h3 class="card-title">
                ${store.t("card.home_screen_appearance")}
              </h3>`,
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
              heading: html`<h3 class="card-title">${store.t("card.screensaver")}</h3>`,
              contentClass: "settings-list",
              body: html`${screensaverPrefs.map((p) => renderPrefControlRow(store, p))}
                ${activateScreensaverBtn
                  ? renderSettingsRow({
                      label: entityLabel(
                        activateScreensaverBtn.name || activateScreensaverBtn.entity_id,
                      ),
                      description: store.t("dev_display.screensaver_preview_desc"),
                      control: html`<button
                        type="button"
                        ?disabled=${isOffline ||
                        String(activateScreensaverBtn.state ?? "") === "unavailable"}
                        @click=${() => {
                          const btnLabel = entityLabel(
                            activateScreensaverBtn.name || activateScreensaverBtn.entity_id,
                          );
                          const toastMsg = store.t("sync.triggered_action", {
                            label: btnLabel,
                          });
                          if (activateScreensaverBtn.device_command) {
                            void store.entity.runDeviceAction(
                              activateScreensaverBtn.device_command,
                              toastMsg,
                            );
                          } else {
                            void store.entity.espAction(
                              activateScreensaverBtn.entity_id,
                              "press",
                              undefined,
                              toastMsg,
                            );
                          }
                        }}
                        class="btn btn-secondary btn-compact"
                      >
                        ${store.t("dev_display.preview_btn")}
                      </button>`,
                    })
                  : nothing}`,
            })
          : nothing}

        ${voiceVisualPref
          ? renderCard({
              heading: html`<h3 class="card-title">
                ${store.t("dev_display.card_voice_assistant")}
              </h3>`,
              contentClass: "settings-list",
              body: renderPrefControlRow(store, voiceVisualPref),
            })
          : nothing}

        ${visibleBrightnessPrefs.length
          ? renderCard({
              heading: html`<h3 class="card-title">${store.t("card.brightness")}</h3>`,
              contentClass: "settings-list",
              body: visibleBrightnessPrefs.map((p) => renderPrefControlRow(store, p)),
            })
          : nothing}

        ${clockPrefs.length
          ? renderCard({
              heading: html`<h3 class="card-title">${store.t("card.clock")}</h3>`,
              contentClass: "settings-list",
              body: clockPrefs.map((p) => renderPrefControlRow(store, p)),
            })
          : nothing}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">${store.t("card.colors")}</h3>`,
          contentClass: "settings-list",
          body: html`${colorProfilePref ? renderPrefControlRow(store, colorProfilePref) : nothing}
            ${renderSettingsRow({
              label: store.t("dev_display.custom_color_label"),
              forId: "dev-custom-palette-select",
              description: store.t("dev_display.custom_color_desc"),
              control: html`<span class="swatch" style=${swatchStyle} aria-hidden="true"></span>
                <select
                  id="dev-custom-palette-select"
                  .value=${curHex}
                  @change=${(ev: Event) => {
                    const val = (ev.currentTarget as HTMLSelectElement).value;
                    if (isValidHexColor(val)) {
                      store.entity.applyDeviceCustomColor(val, true);
                    }
                  }}
                >
                  ${!palettes.length
                    ? html`<option value=${curHex} selected>
                        ${store.t("dev_display.current_color_option", { hex: curHex })}
                      </option>`
                    : html`
                        ${!palettes.some((p) => p.hex.toUpperCase() === curHex)
                          ? html`<option value=${curHex} selected>
                              ${store.t("dev_display.current_color_option", { hex: curHex })}
                            </option>`
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
                  @click=${() => store.tools.openColorWheelModal("device")}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.t("dev_display.add_color_btn")}
                </button>`,
            })}`,
        })}

        ${renderCard({
          heading: html`<h3 class="card-title">${store.t("card.wallpapers")}</h3>`,
          subtitle: store.t("dev_display.wallpapers_subtitle"),
          headerActions: renderWallpaperUploadTrigger(store, "device"),
          contentClass: "stack",
          body: html`${renderWallpaperUploadProgress(store, "device")}
            <div class="settings-list">
              ${renderSettingsRow({
                id: "wp-status-row",
                label: store.t("dev_display.active_wallpaper_label"),
                description: wpStatusText,
                control: isRotating
                  ? html`<button
                        type="button"
                        id="btn-stop-wp-rotation"
                        @click=${() => void store.entity.setWallpaperRotation(0)}
                        class="btn btn-secondary btn-compact"
                      >
                        ${store.t("dev_display.stop_rotation")}
                      </button>
                      <button
                        type="button"
                        id="btn-turn-off-wp"
                        @click=${() => void store.entity.selectWallpaperSource("")}
                        class="btn btn-secondary btn-compact"
                      >
                        ${store.t("dev_display.turn_off_wallpaper")}
                      </button>`
                  : hasActiveWallpaper
                    ? html`${wallpapers.length >= 2
                          ? html`<button
                              type="button"
                              id="btn-enable-wp-rotation"
                              @click=${() => void store.entity.setWallpaperRotation(15)}
                              class="btn btn-secondary btn-compact"
                            >
                              ${store.t("dev_display.enable_rotation")}
                            </button>`
                          : nothing}
                        <button
                          type="button"
                          id="btn-turn-off-wp"
                          @click=${() => void store.entity.selectWallpaperSource("")}
                          class="btn btn-secondary btn-compact"
                        >
                          ${store.t("dev_display.turn_off_wallpaper")}
                        </button>`
                    : wallpapers.length >= 2
                      ? html`<button
                          type="button"
                          id="btn-enable-wp-rotation"
                          @click=${() => void store.entity.setWallpaperRotation(15)}
                          class="btn btn-primary btn-compact"
                        >
                          ${store.t("dev_display.enable_rotation")}
                        </button>`
                      : nothing,
              })}
              ${renderSettingsRow({
                id: "wp-rotation-row",
                label: store.t("dev_display.rotation_interval_label"),
                forId: "cfg-wallpaper_cycle_minutes",
                description: wpRotationHint,
                control: html`<select
                    id="cfg-wallpaper_cycle_minutes"
                    aria-label=${store.t("dev_display.rotation_interval_aria")}
                    .value=${String(curCycle)}
                    @change=${(ev: Event) =>
                      void store.entity.setWallpaperRotation(
                        Number((ev.currentTarget as HTMLSelectElement).value) || 0,
                      )}
                  >
                    ${WALLPAPER_ROTATION_OPTIONS.map(
                      (opt) =>
                        html`<option value=${String(opt.value)} ?selected=${opt.value === curCycle}>
                          ${rotationLabel(store, opt.value, opt.label)}
                        </option>`,
                    )}
                  </select>
                  ${wallpapers.length > 0 && !allStarred
                    ? html`<button
                        type="button"
                        id="btn-star-all-wp"
                        @click=${() =>
                          void store.entity.setAllWallpaperFavorites(
                            wallpapers.map((w) => w.id),
                          )}
                        class="btn btn-text btn-compact"
                      >
                        ${store.t("dev_display.star_all")}
                      </button>`
                    : nothing}
                  ${starredCount > 0
                    ? html`<button
                        type="button"
                        id="btn-clear-stars-wp"
                        @click=${() => void store.entity.setAllWallpaperFavorites([])}
                        class="btn btn-text btn-compact"
                      >
                        ${store.t("dev_display.clear_stars")}
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
              heading: html`<h3 class="card-title">${store.t("card.music_appearance")}</h3>`,
              contentClass: "settings-list",
              body: mediaAppearancePrefs.map((p) => renderPrefControlRow(store, p)),
            })
          : nothing}
      </div>
    </div>
  </section>`;
}
