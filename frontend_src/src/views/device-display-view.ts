/**
 * Device Display View (`display`, `D-027`, `D-029`, `D-034`, `D-036`, `D-069`, `D-072`):
 * Hardware & OS surface aesthetics across screens:
 * - Column 1: Screensaver (`screensaver_mode`, `screensaver_style`, `docked_idle_timeout`,
 *   conditional Photo Frame pool preview / rotation / shuffle / `screensaver_photo_clock`, Preview),
 *   Voice assistant, & Brightness.
 * - Column 2: Colors & Wallpapers (compact active pool preview + Choose wallpaper… / Turn off,
 *   rotation interval, clear Home + Sky & weather live-background override note, & Manage photo library).
 */

import {
  renderCard,
  renderDeviceOfflineBanner,
  renderPrefControlRow,
  renderSettingsRow,
  renderSwitchRow,
} from "../components/controls.js";
import {
  type StudioTranslationKey,
  WALLPAPER_ROTATION_OPTIONS,
} from "../i18n/index.js";
import { html, live, nothing, type TemplateResult } from "../lib/lit.js";
import {
  resolveCollectionDisplayName,
  resolvePoolPhotos,
} from "../state/photo-ops.js";
import type { StudioStore } from "../state/store.js";
import type { PhotoItem } from "../types.js";
import { defaultThemeHex, fmtNumber, isValidHexColor } from "../utils/format.js";

function rotationLabel(store: StudioStore, minutes: number, fallback: string): string {
  const key = `dev_display.rot_${minutes}` as StudioTranslationKey;
  const translated = store.t(key);
  return translated === key ? fallback : translated;
}

function parseBoolPref(raw: unknown, fallback: boolean): boolean {
  if (raw === undefined || raw === null) return fallback;
  if (typeof raw === "string") {
    return !["", "0", "false", "off", "disabled"].includes(raw.trim().toLowerCase());
  }
  return Boolean(raw);
}

function describePoolSummary(
  store: StudioStore,
  mode: string,
  singleSource: string,
  collectionId: string,
  poolPhotos: readonly PhotoItem[],
  allPhotos: readonly PhotoItem[],
): { title: string; meta: string } {
  if (mode === "off" || (mode === "single" && !singleSource)) {
    return {
      title: store.t("common.disabled"),
      meta: store.t("dev_display.pool_off_meta"),
    };
  }
  if (mode === "single") {
    const found =
      poolPhotos[0] || allPhotos.find((p) => p.id === singleSource) || null;
    const name = found?.name || singleSource;
    return {
      title: name,
      meta: store.t("dev_display.pool_single_meta", { name }),
    };
  }
  if (mode === "collection") {
    const colName = resolveCollectionDisplayName(store, collectionId);
    const count = poolPhotos.length;
    return {
      title: colName,
      meta:
        count === 1
          ? store.t("dev_display.pool_collection_one_meta", { collection: colName })
          : store.t("dev_display.pool_collection_meta", {
              collection: colName,
              count: fmtNumber(count, store.hass, 0),
            }),
    };
  }
  const count = poolPhotos.length;
  return {
    title:
      count === 1
        ? store.t("dev_display.pool_custom_one_meta")
        : store.t("dev_display.pool_custom_meta", {
            count: fmtNumber(count, store.hass, 0),
          }),
    meta:
      count > 0
        ? poolPhotos
            .slice(0, 3)
            .map((p) => p.name || p.id)
            .join(", ") + (count > 3 ? "…" : "")
        : store.t("dev_display.pool_off_meta"),
  };
}

export function renderDeviceDisplayView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const liveData = data?.live || {};
  const palettes = (data?.system_config?.custom_palettes || []).filter((p) =>
    isValidHexColor(p.hex),
  );
  const curDevEntry =
    (data?.system_devices || []).find((d) => d.subentry_id === store.activeSubentryId) ||
    (data?.system_devices || []).find((d) => d.is_current);
  const isOffline = curDevEntry?.is_online === false;
  const shapeClass = String(cfg.display_shape || "square") === "circle" ? "circle" : "";

  const allPhotos =
    (data?.wallpapers && data.wallpapers.length > 0
      ? data.wallpapers
      : data?.system_wallpapers) || [];

  // Screensaver card
  const ssModePref = store.entity.getPref("screensaver_mode");
  const ssStylePref = store.entity.getPref("screensaver_style");
  const ssIdlePref = store.entity.getPref("docked_idle_timeout");
  const ssPhotoClockPref = store.entity.getPref("screensaver_photo_clock");

  const ssModeVal = String(ssModePref?.value ?? cfg.screensaver_mode ?? "Docked Only");
  const ssNever = ssModeVal === "Never";
  const ssStyleVal = String(ssStylePref?.value ?? cfg.screensaver_style ?? "Ambient Clock");
  const ssIsPhotoFrame = !ssNever && ssStyleVal === "Photo Frame";
  const ssPhotoClockOn = parseBoolPref(
    ssPhotoClockPref?.value ?? cfg.screensaver_photo_clock,
    false,
  );

  const ssModePool = String(cfg.screensaver_photo_mode || "off");
  const ssSingleSource = String(cfg.screensaver_photo_source || "");
  const ssCollection = String(cfg.screensaver_photo_collection || "");
  const ssCustomIds = Array.isArray(cfg.screensaver_photo_ids) ? cfg.screensaver_photo_ids : [];
  const ssCycle = Number(cfg.screensaver_cycle_minutes ?? 15);
  const ssShuffle = Boolean(cfg.screensaver_shuffle);

  const ssPoolPhotos = resolvePoolPhotos(
    allPhotos,
    ssModePool,
    ssSingleSource,
    ssCollection,
    ssCustomIds,
    { excludeDynamic: true },
  );
  const ssSummary = describePoolSummary(
    store,
    ssModePool,
    ssSingleSource,
    ssCollection,
    ssPoolPhotos,
    allPhotos,
  );
  const ssPreviewThumbs: string[] = [];
  if (liveData.active_screensaver_photo_thumb_url) {
    ssPreviewThumbs.push(liveData.active_screensaver_photo_thumb_url);
  }
  for (const p of ssPoolPhotos) {
    const u = p.thumb_url || p.preview_url || "";
    if (u && !ssPreviewThumbs.includes(u) && ssPreviewThumbs.length < 3) {
      ssPreviewThumbs.push(u);
    }
  }

  const ssActive = Boolean(liveData.screensaver_active);
  const hasScreensaverCard = Boolean(ssModePref || ssStylePref || ssIdlePref);

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
  const autoBrtAmbient = autoBrtState === "Ambient Light";
  const activeAreaName = String(liveData.active_area_name || "").trim();
  const activeAreaLux = String(liveData.active_area_lux_display || "").trim();
  const activeAreaAmbPct =
    liveData.active_area_ambient_pct !== null && liveData.active_area_ambient_pct !== undefined
      ? Number(liveData.active_area_ambient_pct)
      : null;
  let ambientBrightnessSubtitle: string | undefined;
  if (autoBrtAmbient) {
    if (activeAreaLux && activeAreaAmbPct !== null && Number.isFinite(activeAreaAmbPct)) {
      ambientBrightnessSubtitle = store.t("dev_display.ambient_live_status", {
        area: activeAreaName || store.t("common.unknown"),
        lux: activeAreaLux,
        level: fmtNumber(activeAreaAmbPct, store.hass, 0),
      });
    } else if (activeAreaName && activeAreaName !== "Unassigned") {
      ambientBrightnessSubtitle = store.t("dev_display.ambient_fallback_status", {
        area: activeAreaName,
      });
    } else {
      ambientBrightnessSubtitle = store.t("dev_display.ambient_unassigned_status");
    }
  }

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

  // Column 2: Colors card (`isValidHexColor` validation)
  const colorProfilePref = store.entity.getPref("color_profile");
  const rawThemeHex = defaultThemeHex(store.host);
  const safeThemeHex = isValidHexColor(rawThemeHex)
    ? rawThemeHex.toUpperCase()
    : defaultThemeHex(null);
  const curHex = isValidHexColor(cfg.device_custom_color)
    ? String(cfg.device_custom_color).toUpperCase()
    : safeThemeHex;
  const swatchStyle = `--swatch-color:${curHex}`;

  // Column 2: Wallpaper card + clear Home & Sky & weather override note (`D-069`, `D-072`)
  const homeScreenEnabled =
    (store.entity.getPref("home_screen_enabled")?.value ?? cfg.home_screen_enabled) !== false;
  const homeWeatherBgOn = parseBoolPref(
    store.entity.getPref("weather_background")?.value ?? cfg.weather_background,
    true,
  );
  const weatherAppBgOn = parseBoolPref(
    store.entity.getPref("weather_app_background")?.value ?? cfg.weather_app_background,
    true,
  );

  const wpRawMode = String(cfg.wallpaper_mode || "");
  const wpSingleSource = String(cfg.wallpaper_source || "");
  const wpCollection = String(cfg.wallpaper_collection || "");
  const wpCustomIds = Array.isArray(cfg.wallpaper_favorites) ? cfg.wallpaper_favorites : [];
  const wpCycle = Number(cfg.wallpaper_cycle_minutes || 0);
  const wpMode =
    wpRawMode ||
    (wpSingleSource ? "single" : wpCustomIds.length > 0 && wpCycle > 0 ? "custom" : "off");

  const wpPoolPhotos = resolvePoolPhotos(
    allPhotos,
    wpMode,
    wpSingleSource,
    wpCollection,
    wpCustomIds,
  );
  const wpActiveItem =
    allPhotos.find((w) => w.id === liveData.active_wallpaper_id) ||
    allPhotos.find((w) => Boolean(w.active)) ||
    wpPoolPhotos[0] ||
    null;
  const wpIsActive = wpMode !== "off" && (Boolean(wpActiveItem) || wpPoolPhotos.length > 0);
  const wpSummary = describePoolSummary(
    store,
    wpMode,
    wpSingleSource || wpActiveItem?.id || "",
    wpCollection,
    wpPoolPhotos,
    allPhotos,
  );

  const wpPreviewThumbs: string[] = [];
  if (liveData.active_wallpaper_thumb_url) {
    wpPreviewThumbs.push(liveData.active_wallpaper_thumb_url);
  } else if (wpActiveItem?.thumb_url || wpActiveItem?.preview_url) {
    wpPreviewThumbs.push(wpActiveItem.thumb_url || wpActiveItem.preview_url || "");
  }
  for (const p of wpPoolPhotos) {
    const u = p.thumb_url || p.preview_url || "";
    if (u && !wpPreviewThumbs.includes(u) && wpPreviewThumbs.length < 3) {
      wpPreviewThumbs.push(u);
    }
  }

  let wpOverrideNote = "";
  if (wpIsActive) {
    const homeOverride = homeScreenEnabled && homeWeatherBgOn;
    if (homeOverride && weatherAppBgOn) {
      wpOverrideNote = store.t("dev_display.wp_override_home_and_weather");
    } else if (homeOverride) {
      wpOverrideNote = store.t("dev_display.wp_override_home_only");
    } else if (weatherAppBgOn) {
      wpOverrideNote = store.t("dev_display.wp_override_weather_only");
    }
  }

  return html`<section id="view-display">
    ${renderDeviceOfflineBanner(store)}

    <div class="columns">
      <div class="column">
        ${hasScreensaverCard
          ? renderCard({
              id: "card-screensaver",
              heading: html`<h3 class="card-title">${store.t("card.screensaver")}</h3>`,
              contentClass: "stack",
              body: html`<div class="settings-list">
                  ${ssModePref ? renderPrefControlRow(store, ssModePref) : nothing}
                  ${!ssNever && ssStylePref ? renderPrefControlRow(store, ssStylePref) : nothing}
                  ${!ssNever && ssIdlePref ? renderPrefControlRow(store, ssIdlePref) : nothing}
                </div>

                ${ssIsPhotoFrame
                  ? html`<div id="screensaver-photo-frame-section" class="stack">
                      <div class="photo-pool-preview">
                        ${ssPreviewThumbs.length > 0
                          ? html`<div class="photo-pool-thumbs">
                              ${ssPreviewThumbs.map(
                                (src) => html`<img
                                  src=${src}
                                  alt=""
                                  loading="lazy"
                                  class="photo-pool-thumb ${shapeClass}"
                                />`,
                              )}
                            </div>`
                          : nothing}
                        <div class="photo-pool-info">
                          <span class="photo-pool-title">
                            ${store.t("dev_display.screensaver_pool_label")}
                          </span>
                          <span class="photo-pool-meta">
                            ${ssPoolPhotos.length > 0
                              ? ssSummary.meta
                              : store.t("dev_display.screensaver_pool_empty")}
                          </span>
                        </div>
                        <div class="photo-pool-actions">
                          <button
                            type="button"
                            id="btn-choose-ss-photos"
                            @click=${() => store.entity.openPhotoPickerModal("screensaver")}
                            class="btn btn-secondary btn-compact"
                          >
                            ${store.t("dev_display.screensaver_choose_photos")}
                          </button>
                        </div>
                      </div>

                      <div class="settings-list">
                        ${renderSettingsRow({
                          label: store.tPrefLabel("screensaver_cycle_minutes"),
                          forId: "cfg-screensaver_cycle_minutes",
                          control: html`<select
                            id="cfg-screensaver_cycle_minutes"
                            .value=${live(String(ssCycle))}
                            @change=${(ev: Event) =>
                              void store.entity.setScreensaverRotation(
                                Number((ev.currentTarget as HTMLSelectElement).value) || 0,
                              )}
                          >
                            ${WALLPAPER_ROTATION_OPTIONS.map(
                              (opt) => html`<option
                                value=${String(opt.value)}
                                .selected=${live(opt.value === ssCycle)}
                              >
                                ${rotationLabel(store, opt.value, opt.label)}
                              </option>`,
                            )}
                          </select>`,
                        })}
                        ${renderSwitchRow({
                          id: "cfg-screensaver_shuffle",
                          label: store.tPrefLabel("screensaver_shuffle"),
                          description: store.t("dev_display.screensaver_shuffle_desc"),
                          checked: ssShuffle,
                          onChange: (checked) =>
                            void store.entity.setScreensaverRotation(ssCycle, checked),
                        })}
                        ${ssPhotoClockPref
                          ? renderPrefControlRow(store, ssPhotoClockPref)
                          : renderSwitchRow({
                              id: "cfg-screensaver_photo_clock",
                              label: store.tPrefLabel("screensaver_photo_clock"),
                              description: store.t("dev_display.screensaver_photo_clock_desc"),
                              checked: ssPhotoClockOn,
                              onChange: (checked) =>
                                store.entity.stageDeviceSetting(
                                  "screensaver_photo_clock",
                                  checked,
                                  "cfg-screensaver_photo_clock",
                                ),
                            })}
                      </div>
                    </div>`
                  : nothing}

                ${!ssNever
                  ? html`<div class="settings-list">
                      ${renderSettingsRow({
                        id: "row-screensaver-preview",
                        label: ssActive
                          ? store.t("dev_overview.qa_exit_screensaver")
                          : store.t("dev_overview.qa_activate_screensaver"),
                        description: ssActive
                          ? store.t("dev_display.screensaver_exit_desc")
                          : store.t("dev_display.screensaver_preview_desc"),
                        control: html`<button
                          type="button"
                          id="btn-screensaver-preview"
                          ?disabled=${isOffline}
                          @click=${() => {
                            const actionCmd = ssActive
                              ? "deactivate_screensaver"
                              : "activate_screensaver";
                            const actionLabel = ssActive
                              ? store.t("dev_overview.qa_exit_screensaver")
                              : store.t("dev_overview.qa_activate_screensaver");
                            void store.entity.runDeviceAction(
                              actionCmd,
                              store.t("sync.triggered_action", { label: actionLabel }),
                            );
                          }}
                          class="btn btn-secondary btn-compact"
                        >
                          ${ssActive
                            ? store.t("dev_display.exit_screensaver_btn")
                            : store.t("dev_display.preview_btn")}
                        </button>`,
                      })}
                    </div>`
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
                : ambientBrightnessSubtitle,
              contentClass: "settings-list",
              body: visibleBrightnessPrefs.map((p) => {
                const labelOverride =
                  autoBrtAmbient && p.key === "day_brightness"
                    ? store.t("dev_display.bright_brightness_label")
                    : autoBrtAmbient && p.key === "night_brightness"
                      ? store.t("dev_display.dark_brightness_label")
                      : undefined;
                return renderPrefControlRow(store, p, labelOverride);
              }),
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
                  .value=${live(curHex)}
                  @change=${(ev: Event) => {
                    const val = (ev.currentTarget as HTMLSelectElement).value;
                    if (isValidHexColor(val)) {
                      store.entity.applyDeviceCustomColor(val, true);
                    }
                  }}
                >
                  ${!palettes.length
                    ? html`<option value=${curHex} .selected=${live(true)}>
                        ${store.t("dev_display.current_color_option", { hex: curHex })}
                      </option>`
                    : html`
                        ${!palettes.some((p) => p.hex.toUpperCase() === curHex)
                          ? html`<option value=${curHex} .selected=${live(true)}>
                              ${store.t("dev_display.current_color_option", { hex: curHex })}
                            </option>`
                          : nothing}
                        ${palettes.map((p) => {
                          const h = p.hex.toUpperCase();
                          return html`<option value=${h} .selected=${live(h === curHex)}>
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
          id: "card-device-wallpapers",
          heading: html`<h3 class="card-title">${store.t("card.wallpapers")}</h3>`,
          subtitle: store.t("dev_display.wallpapers_subtitle"),
          headerActions: html`<button
            type="button"
            id="btn-manage-photo-library"
            @click=${() => store.openSystemSection("photos")}
            class="btn btn-text btn-compact"
          >
            ${store.t("dev_display.manage_photo_library")}
          </button>`,
          contentClass: "stack",
          body: html`<div id="wp-status-row" class="photo-pool-preview">
              ${wpPreviewThumbs.length > 0
                ? html`<div class="photo-pool-thumbs">
                    ${wpPreviewThumbs.map(
                      (src) => html`<img
                        src=${src}
                        alt=""
                        loading="lazy"
                        class="photo-pool-thumb ${shapeClass}"
                      />`,
                    )}
                  </div>`
                : nothing}
              <div class="photo-pool-info">
                <span class="photo-pool-title">${wpSummary.title}</span>
                <span class="photo-pool-meta">${wpSummary.meta}</span>
              </div>
              <div class="photo-pool-actions">
                <button
                  type="button"
                  id="btn-choose-wallpaper"
                  @click=${() => store.entity.openPhotoPickerModal("wallpaper")}
                  class="btn btn-primary btn-compact"
                >
                  ${store.t("dev_display.choose_wallpaper")}
                </button>
                ${wpIsActive
                  ? html`<button
                      type="button"
                      id="btn-turn-off-wp"
                      @click=${() =>
                        void store.entity.setDevicePhotoPool(
                          { target: "wallpaper", mode: "off", cycleMinutes: 0 },
                          store.t("dev_display.turn_off_wallpaper"),
                        )}
                      class="btn btn-secondary btn-compact"
                    >
                      ${store.t("dev_display.turn_off_wallpaper")}
                    </button>`
                  : nothing}
              </div>
            </div>

            ${wpMode === "collection" || wpMode === "custom" || wpCycle > 0
              ? html`<div class="settings-list">
                  ${renderSettingsRow({
                    id: "wp-rotation-row",
                    label: store.t("dev_display.rotation_interval_label"),
                    forId: "cfg-wallpaper_cycle_minutes",
                    control: html`<select
                      id="cfg-wallpaper_cycle_minutes"
                      aria-label=${store.t("dev_display.rotation_interval_aria")}
                      .value=${live(String(wpCycle))}
                      @change=${(ev: Event) =>
                        void store.entity.setWallpaperRotation(
                          Number((ev.currentTarget as HTMLSelectElement).value) || 0,
                        )}
                    >
                      ${WALLPAPER_ROTATION_OPTIONS.map(
                        (opt) => html`<option
                          value=${String(opt.value)}
                          .selected=${live(opt.value === wpCycle)}
                        >
                          ${rotationLabel(store, opt.value, opt.label)}
                        </option>`,
                      )}
                    </select>`,
                  })}
                </div>`
              : nothing}

            ${wpOverrideNote
              ? html`<div id="wp-weather-override-note" class="alert">
                  <div class="alert-body">
                    <span>${wpOverrideNote}</span>
                  </div>
                  <button
                    type="button"
                    id="btn-wp-open-interface"
                    @click=${() => store.openDeviceSection("interface", "card-home-screen")}
                    class="btn btn-text btn-compact"
                  >
                    ${store.t("dev_display.open_interface")}
                  </button>
                </div>`
              : nothing}`,
        })}
      </div>
    </div>
  </section>`;
}
