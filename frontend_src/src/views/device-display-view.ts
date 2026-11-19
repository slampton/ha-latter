/**
 * Device Display View (`display`, `D-027`, `D-029`, `D-034`, `D-036`, `D-069`):
 * Hardware & OS surface aesthetics across screens:
 * - Column 1: Screensaver, Voice assistant, & Brightness.
 * - Column 2: Colors (`isValidHexColor` validation) & Wallpapers (with Home weather-background hint).
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
import type { StudioTranslationKey } from "../i18n/index.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { defaultThemeHex, entityLabel, fmtNumber, isValidHexColor } from "../utils/format.js";
import { renderDeviceOfflineBanner } from "./device-overview-view.js";

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

  const bedtimeActive = Boolean(
    store.entity.getPref("bedtime_active")?.value ?? cfg.bedtime_active,
  );

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

  // Column 2: Wallpapers + cross-tab Home weather-background hint (`D-069`)
  const weatherBgRaw =
    store.entity.getPref("weather_background")?.value ?? cfg.weather_background;
  const weatherBgOn =
    weatherBgRaw !== undefined && weatherBgRaw !== null
      ? typeof weatherBgRaw === "string"
        ? !["", "0", "false", "off", "disabled"].includes(weatherBgRaw.trim().toLowerCase())
        : Boolean(weatherBgRaw)
      : true;
  const homeScreenRaw =
    store.entity.getPref("home_screen_enabled")?.value ?? cfg.home_screen_enabled;
  const homeScreenEnabled = homeScreenRaw !== false;

  const curCycle = Number(cfg.wallpaper_cycle_minutes || 0);
  const wallpapers = data?.wallpapers || [];
  const activeWp = wallpapers.find((wp) => Boolean(wp.active)) || null;
  const hasActiveWallpaper = Boolean(activeWp);
  const isRotating = curCycle > 0;
  const starredCount = wallpapers.filter((wp) => Boolean(wp.favorite)).length;
  const allStarred = wallpapers.length > 0 && starredCount === wallpapers.length;

  let wpStatusBase: string;
  if (isRotating) {
    if (activeWp) {
      if (starredCount === 1) {
        wpStatusBase = store.t("dev_display.wp_rotating_named_starred_one", {
          name: activeWp.name,
        });
      } else if (starredCount > 1) {
        wpStatusBase = store.t("dev_display.wp_rotating_named_starred_many", {
          name: activeWp.name,
          count: fmtNumber(starredCount, store.hass, 0),
        });
      } else {
        wpStatusBase = store.t("dev_display.wp_rotating_named_all", {
          name: activeWp.name,
          count: fmtNumber(wallpapers.length, store.hass, 0),
        });
      }
    } else if (starredCount === 1) {
      wpStatusBase = store.t("dev_display.wp_rotating_starred_one");
    } else if (starredCount > 1) {
      wpStatusBase = store.t("dev_display.wp_rotating_starred_many", {
        count: fmtNumber(starredCount, store.hass, 0),
      });
    } else {
      wpStatusBase = store.t("dev_display.wp_rotating_all", {
        count: fmtNumber(wallpapers.length, store.hass, 0),
      });
    }
  } else if (hasActiveWallpaper) {
    wpStatusBase = store.t("dev_display.wp_static_named", {
      name: activeWp?.name || store.t("common.active"),
    });
  } else {
    wpStatusBase = store.t("dev_display.wp_off");
  }

  const wpStatusText =
    (isRotating || hasActiveWallpaper) && homeScreenEnabled && weatherBgOn
      ? `${wpStatusBase} ${store.t("dev_display.wp_weather_bg_note")}`
      : wpStatusBase;

  const wpRotationHint =
    starredCount === 0
      ? store.t("dev_display.wp_hint_none")
      : starredCount === 1
        ? store.t("dev_display.wp_hint_one")
        : store.t("dev_display.wp_hint_many", {
            starred: fmtNumber(starredCount, store.hass, 0),
            total: fmtNumber(wallpapers.length, store.hass, 0),
          });

  return html`<section id="view-display">
    ${renderDeviceOfflineBanner(store)}

    <div class="columns">
      <div class="column">
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
              id: "card-brightness",
              heading: html`<h3 class="card-title">${store.t("card.brightness")}</h3>`,
              subtitle: bedtimeActive
                ? store.t("dev_display.bedtime_brightness_override_note")
                : undefined,
              contentClass: "settings-list",
              body: visibleBrightnessPrefs.map((p) => renderPrefControlRow(store, p)),
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
      </div>
    </div>
  </section>`;
}
