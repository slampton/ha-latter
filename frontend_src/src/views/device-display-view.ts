/**
 * Device Display View (`display`, D-026): Panel Brightness, Theme / Custom Color & Wallpapers.
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
import { defaultThemeHex, isValidHexColor } from "../utils/format.js";

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
  const low = (it.name || "").toLowerCase();
  return (
    low.includes("clock face") ||
    low.includes("time format") ||
    low.includes("start screen")
  );
}

export function renderDeviceDisplayView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const palettes = data?.system_config?.custom_palettes || [];

  const displayOrder = [
    "color profile",
    "auto brightness mode",
    "manual brightness",
    "day brightness",
    "night brightness",
    "day start hour",
    "night start hour",
  ];
  const displayItems = sortEntitiesByKeywords(
    store.getSectionItems("display").filter((it) => !isInterfaceDisplayEntity(it)),
    displayOrder,
  );
  const autoBrtItem = displayItems.find((it) =>
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
  const visibleDisplayItems = displayItems.filter((it) => {
    if (it.domain === "light") return false;
    const low = (it.name || "").toLowerCase();
    if (autoBrtKnown) {
      if (autoBrtOff && (low.includes("day brightness") || low.includes("night brightness"))) {
        return false;
      }
      if (!autoBrtOff && low.includes("manual brightness")) {
        return false;
      }
      if (!autoBrtTimeSchedule && (low.includes("day start hour") || low.includes("night start hour"))) {
        return false;
      }
    }
    return true;
  });

  const colorProfileItem = displayItems.find((it) =>
    (it.name || "").toLowerCase().includes("color profile"),
  );
  const curHex = isValidHexColor(cfg.device_custom_color)
    ? String(cfg.device_custom_color).toUpperCase()
    : defaultThemeHex(store.host);
  const swatchStyle = `--swatch-color:${curHex}`;

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
        ${renderCard({
          title: "Brightness & Theme",
          contentClass: "settings-list",
          body: html`${visibleDisplayItems.map((it) => renderNativeControlRow(store, it))}
            ${colorProfileItem || palettes.length || cfg.device_custom_color
              ? renderSettingsRow({
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
                })
              : nothing}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "Wallpapers",
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
      </div>
    </div>
  </section>`;
}
