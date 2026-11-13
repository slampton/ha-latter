/**
 * Device Display View (`display`, D-027 / D-029 / D-033 / D-034):
 * Visual & aesthetic preferences across screens.
 * Column 1: Home Screen (Wake Greeting, Weather Background & Sun & Moon), Screensavers, Voice Assistant (Visual Profile), Brightness & Clock.
 * Column 2: Colors, Wallpapers & Media Player (Album Art & Overlay Style).
 */

import {
  renderCard,
  renderNativeControlRow,
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
import type { EspHomeEntityItem } from "../types.js";
import { defaultThemeHex, entityLabel, isValidHexColor } from "../utils/format.js";

export function sortEntitiesByKeywords(
  items: readonly EspHomeEntityItem[],
  order: readonly string[],
): EspHomeEntityItem[] {
  return [...items].sort((a, b) => {
    const la = (a.name || "").toLowerCase();
    const lb = (b.name || "").toLowerCase();
    const ia = order.findIndex((k) => la.includes(k));
    const ib = order.findIndex((k) => lb.includes(k));
    const ra = ia >= 0 ? ia : order.length;
    const rb = ib >= 0 ? ib : order.length;
    return ra - rb;
  });
}

export function isInterfaceDisplayEntity(it: EspHomeEntityItem): boolean {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return (
    low.includes("enable home screen") ||
    low.includes("home_screen_enabled") ||
    low.includes("start screen") ||
    low.includes("start_screen") ||
    low.includes("return to home timeout") ||
    low.includes("return_to_home_timeout")
  );
}

function isClockDisplayEntity(it: EspHomeEntityItem): boolean {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return (
    low.includes("clock face") ||
    low.includes("clock_face") ||
    low.includes("time format") ||
    low.includes("time_format")
  );
}

export function isMediaAppearanceEntity(it: EspHomeEntityItem): boolean {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return (
    low.includes("album art style") ||
    low.includes("album_art_style") ||
    low.includes("overlay style") ||
    low.includes("music_overlay_style")
  );
}

export function isScreensaverSleepEntity(it: EspHomeEntityItem): boolean {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return (
    low.includes("screensaver") ||
    low.includes("docked idle timeout") ||
    low.includes("docked_idle_timeout")
  );
}

export function isVoiceVisualProfileEntity(it: EspHomeEntityItem): boolean {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return low.includes("visual profile") || low.includes("visual_profile");
}

function isColorDisplayEntity(it: EspHomeEntityItem): boolean {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return low.includes("color profile") || low.includes("color_profile");
}

export function renderDeviceDisplayView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const palettes = data?.system_config?.custom_palettes || [];

  const brightnessOrder = [
    "auto brightness mode",
    "manual brightness",
    "day brightness",
    "night brightness",
    "day start hour",
    "night start hour",
  ];
  const allDisplayItems = store
    .getSectionItems("display")
    .filter((it) => !isInterfaceDisplayEntity(it));
  const colorItems = allDisplayItems.filter(isColorDisplayEntity);
  const clockItems = sortEntitiesByKeywords(
    allDisplayItems.filter(isClockDisplayEntity),
    ["clock face", "time format"],
  );
  const brightnessItems = sortEntitiesByKeywords(
    allDisplayItems.filter((it) => !isColorDisplayEntity(it) && !isClockDisplayEntity(it)),
    brightnessOrder,
  );
  const autoBrtItem = brightnessItems.find((it) =>
    (it.name || "").toLowerCase().includes("auto brightness"),
  );
  const autoBrtState = String(autoBrtItem?.state ?? "").trim();
  const autoBrtKnown =
    Boolean(autoBrtItem) &&
    autoBrtState !== "" &&
    autoBrtState !== "unavailable" &&
    autoBrtState !== "unknown";
  const autoBrtOff = autoBrtKnown && (autoBrtState === "Disabled" || autoBrtState === "off");
  const autoBrtTimeSchedule = autoBrtKnown && autoBrtState === "Time Schedule";
  const visibleBrightnessItems = brightnessItems.filter((it) => {
    if (it.domain === "light") return false;
    const low = (it.name || "").toLowerCase();
    if (autoBrtKnown) {
      if (autoBrtOff && (low.includes("day brightness") || low.includes("night brightness"))) {
        return false;
      }
      if (!autoBrtOff && low.includes("manual brightness")) {
        return false;
      }
      if (
        !autoBrtTimeSchedule &&
        (low.includes("day start hour") || low.includes("night start hour"))
      ) {
        return false;
      }
    }
    return true;
  });

  const homeOrder = ["wake greeting", "weather background", "sun", "moon"];
  const homeItems = sortEntitiesByKeywords(store.getSectionItems("home"), homeOrder);
  const weatherBgSwitch = homeItems.find((it) =>
    (it.name || "").toLowerCase().includes("weather background"),
  );
  const weatherBgOff = weatherBgSwitch ? weatherBgSwitch.state === "off" : false;
  const isCelestialSwitch = (it: EspHomeEntityItem): boolean =>
    it.domain === "switch" && /^(?:home:\s*)?(?:sun|moon)$/i.test((it.name || "").trim());
  const celestialItems = homeItems.filter(isCelestialSwitch);
  const visibleHomeItems = homeItems.filter((it) => !isCelestialSwitch(it));

  const renderCelestialRow = (): TemplateResult =>
    renderSettingsRow({
      id: "weather-celestial-bodies",
      label: "Sun & Moon",
      description: "Choose which sky bodies appear on the live Weather Background.",
      control: html`<div class="pill-list" role="group" aria-label="Sun and Moon">
        ${celestialItems.map((cel) => {
          const st = String(cel.state ?? "");
          const isOn = st === "on";
          const prefKey = cel.pref_key || "";
          const unavailable = !prefKey && (st === "unavailable" || st === "unknown");
          const lbl = entityLabel((cel.name || cel.entity_id).replace(/^home:\s*/i, ""));
          return html`<span class="pill ${isOn ? "enabled" : ""}">
            <button
              type="button"
              aria-pressed=${String(isOn)}
              ?disabled=${unavailable}
              @click=${() => {
                if (prefKey) {
                  store.stageDeviceSetting(prefKey, !isOn);
                } else {
                  void store.espAction(
                    cel.entity_id,
                    isOn ? "turn_off" : "turn_on",
                    isOn ? "off" : "on",
                  );
                }
              }}
              class="pill-toggle"
            >
              ${isOn ? `✓ ${lbl}` : `+ ${lbl}`}
            </button>
          </span>`;
        })}
      </div>`,
    });

  const mediaAppearanceItems = sortEntitiesByKeywords(
    store.getSectionItems("music").filter(isMediaAppearanceEntity),
    ["album art style", "overlay style"],
  );
  const voiceVisualItems = store
    .getSectionItems("voice")
    .filter(isVoiceVisualProfileEntity);

  const curHex = isValidHexColor(cfg.device_custom_color)
    ? String(cfg.device_custom_color).toUpperCase()
    : defaultThemeHex(store.host);
  const swatchStyle = `--swatch-color:${curHex}`;

  const screensaverOrder = [
    "docked screensaver",
    "screensaver style",
    "docked idle timeout",
  ];
  const screensaverSleepItems = sortEntitiesByKeywords(
    store.getSectionItems("sleep").filter(isScreensaverSleepEntity),
    screensaverOrder,
  );
  const activateScreensaverBtn = store
    .getSectionItems("actions")
    .find(
      (it) =>
        it.domain === "button" &&
        `${it.name || ""} ${it.entity_id || ""}`.toLowerCase().includes("screensaver"),
    );

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

  return html`<section id="view-display">
    <div class="columns">
      <div class="column">
        ${visibleHomeItems.length || (!weatherBgOff && celestialItems.length > 0)
          ? renderCard({
              heading: html`<h3 class="card-title">Home Screen</h3>`,
              contentClass: "settings-list",
              body: html`<div id="embedded-home" class="settings-list">
                ${visibleHomeItems.map((it) => {
                  const row = renderNativeControlRow(store, it);
                  if (weatherBgSwitch && it.entity_id === weatherBgSwitch.entity_id) {
                    return html`${row}
                      ${!weatherBgOff && celestialItems.length > 0
                        ? renderCelestialRow()
                        : nothing}`;
                  }
                  return row;
                })}
                ${!weatherBgSwitch && !weatherBgOff && celestialItems.length > 0
                  ? renderCelestialRow()
                  : nothing}
              </div>`,
            })
          : nothing}

        ${screensaverSleepItems.length || activateScreensaverBtn
          ? renderCard({
              heading: html`<h3 class="card-title">Screensavers</h3>`,
              contentClass: "settings-list",
              body: html`${screensaverSleepItems.map((it) => renderNativeControlRow(store, it))}
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

        ${voiceVisualItems.length
          ? renderCard({
              heading: html`<h3 class="card-title">Voice Assistant</h3>`,
              contentClass: "settings-list",
              body: voiceVisualItems.map((it) => renderNativeControlRow(store, it)),
            })
          : nothing}

        ${visibleBrightnessItems.length
          ? renderCard({
              heading: html`<h3 class="card-title">Brightness</h3>`,
              contentClass: "settings-list",
              body: visibleBrightnessItems.map((it) => renderNativeControlRow(store, it)),
            })
          : nothing}

        ${clockItems.length
          ? renderCard({
              heading: html`<h3 class="card-title">Clock</h3>`,
              contentClass: "settings-list",
              body: clockItems.map((it) => renderNativeControlRow(store, it)),
            })
          : nothing}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Colors</h3>`,
          contentClass: "settings-list",
          body: html`${colorItems.map((it) => renderNativeControlRow(store, it))}
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

        ${mediaAppearanceItems.length
          ? renderCard({
              heading: html`<h3 class="card-title">Media Player</h3>`,
              contentClass: "settings-list",
              body: mediaAppearanceItems.map((it) => renderNativeControlRow(store, it)),
            })
          : nothing}
      </div>
    </div>
  </section>`;
}
