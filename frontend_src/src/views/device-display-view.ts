/**
 * Device Display & Home View (`home_display`): Appearance, Custom Color, Activity Card, Dock Apps, Area Controls & Wallpapers.
 */

import { renderNativeControlRow } from "../components/controls.js";
import {
  renderWallpaperGalleryItems,
  renderWallpaperUploadBar,
} from "../components/wallpaper-gallery.js";
import {
  ACTIVITY_SOURCES_CATALOG,
  DOCK_APPS_CATALOG,
  WALLPAPER_ROTATION_OPTIONS,
} from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { EspHomeEntityItem } from "../types.js";
import { defaultThemeHex, isValidHexColor } from "../utils/format.js";

function sortByKeywords(items: readonly EspHomeEntityItem[], order: readonly string[]): EspHomeEntityItem[] {
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

export function renderDeviceDisplayView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const palettes = data?.system_config?.custom_palettes || [];

  const displayItems = store.getSectionItems("display");
  const autoBrtSwitch = displayItems.find((it) =>
    (it.name || "").toLowerCase().includes("auto brightness"),
  );
  const autoBrtOn = autoBrtSwitch ? autoBrtSwitch.state === "on" : false;
  const visibleDisplayItems = displayItems.filter((it) => {
    const low = (it.name || "").toLowerCase();
    if (!autoBrtOn && (low.includes("day brightness") || low.includes("night brightness"))) {
      return false;
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

  const homeOrder = ["wake greeting", "weather background", "sun", "moon"];
  const homeItems = sortByKeywords(store.getSectionItems("home"), homeOrder);
  const weatherBgSwitch = homeItems.find((it) =>
    (it.name || "").toLowerCase().includes("weather background"),
  );
  const weatherBgOff = weatherBgSwitch ? weatherBgSwitch.state === "off" : false;
  const visibleHomeItems = homeItems.filter((it) => {
    const low = (it.name || "").toLowerCase();
    if (weatherBgOff && (low.includes("sun") || low.includes("moon"))) {
      return false;
    }
    return true;
  });

  const areaOrder = ["default category", "show all category"];
  const areaEspItems = sortByKeywords(
    store.getSectionItems("area").filter((it) => !(it.name || "").toLowerCase().includes("ble")),
    areaOrder,
  );

  const activityCardOn = cfg.activity_card !== false;
  const enabledSources = new Set(store.getEnabledActivitySources());
  const enabledDock = store.getEnabledDockTokens();
  const disabledDock = DOCK_APPS_CATALOG.filter((a) => !enabledDock.includes(a.token));

  const curCycle = Number(cfg.wallpaper_cycle_minutes || 0);
  const wallpapers = data?.wallpapers || [];

  return html`<section id="view-home_display">
    <div class="columns">
      <div class="column">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Display &amp; Appearance</h3>
          </div>
          <div class="card-content settings-list">
            ${visibleDisplayItems.map((it) => renderNativeControlRow(store, it))}

            ${colorProfileItem || palettes.length || cfg.device_custom_color
              ? html`<div class="settings-row">
                  <div class="settings-row-text">
                    <label for="dev-custom-palette-select" class="row-label">Custom Color</label>
                    <p class="row-description">
                      Used when Color Profile is set to Custom.
                    </p>
                  </div>
                  <div class="settings-row-control">
                    <span class="swatch" style=${swatchStyle} aria-hidden="true"></span>
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
                    </button>
                  </div>
                </div>`
              : nothing}
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Activity Card</h3>
          </div>
          <div class="card-content settings-list">
            <div class="settings-row">
              <div class="settings-row-text">
                <label for="cfg-activity_card" class="row-label">Show the Activity Card</label>
                <p class="row-description">
                  Shows live timers, alarms, media queue, stopwatch, and next calendar event on Home.
                </p>
              </div>
              <div class="settings-row-control">
                <input
                  type="checkbox"
                  id="cfg-activity_card"
                  role="switch"
                  .checked=${activityCardOn}
                  @change=${(ev: Event) =>
                    store.stageDeviceSetting(
                      "activity_card",
                      (ev.currentTarget as HTMLInputElement).checked,
                      "cfg-activity_card",
                    )}
                  class="switch"
                />
              </div>
            </div>

            ${activityCardOn
              ? html`<div id="activity-sources" class="settings-row stacked">
                  <div class="settings-row-text">
                    <span class="row-label">Activity Card Sources</span>
                    <p class="row-description">Choose which live items appear in the Activity Card.</p>
                  </div>
                  <div class="settings-row-control">
                    <div class="pill-list" role="group" aria-label="Activity Card sources">
                      ${ACTIVITY_SOURCES_CATALOG.map((src) => {
                        const on = enabledSources.has(src.id);
                        return html`<span
                          data-src=${src.id}
                          data-label=${src.label}
                          class="pill ${on ? "enabled" : ""}"
                        >
                          <button
                            type="button"
                            aria-pressed=${String(on)}
                            @click=${() => store.toggleActivitySource(src.id)}
                            class="pill-toggle"
                          >
                            ${on ? `✓ ${src.label}` : `+ ${src.label}`}
                          </button>
                        </span>`;
                      })}
                    </div>
                  </div>
                </div>`
              : nothing}
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Wallpapers</h3>
              <p class="card-subtitle">
                Photos and presets cropped for this Device's display shape. Star favorites to rotate automatically.
              </p>
            </div>
            <div class="card-header-actions">
              <select
                id="cfg-wallpaper_cycle_minutes"
                aria-label="Wallpaper rotation interval"
                .value=${String(curCycle)}
                @change=${(ev: Event) =>
                  store.stageDeviceSetting(
                    "wallpaper_cycle_minutes",
                    Number((ev.currentTarget as HTMLSelectElement).value) || 0,
                    "cfg-wallpaper_cycle_minutes",
                  )}
              >
                ${WALLPAPER_ROTATION_OPTIONS.map(
                  (opt) =>
                    html`<option value=${String(opt.value)} ?selected=${opt.value === curCycle}>
                      ${opt.label}
                    </option>`,
                )}
              </select>
              <button
                type="button"
                @click=${() => void store.selectWallpaperSource("")}
                class="btn btn-secondary"
              >
                Turn Off Wallpaper
              </button>
            </div>
          </div>
          <div class="card-content stack">
            ${renderWallpaperUploadBar(store, "device")}
            <div class="wp-gallery">
              ${renderWallpaperGalleryItems(
                store,
                "device",
                wallpapers,
                String(cfg.display_shape || "square"),
              )}
            </div>
          </div>
        </div>
      </div>

      <div class="column">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Home Screen</h3>
          </div>
          <div class="card-content settings-list">
            <div class="settings-row stacked">
              <div class="settings-row-text">
                <span class="row-label">Dock Apps</span>
                <p class="row-description">
                  Toggle and reorder apps shown in the Home Dock.
                </p>
              </div>
              <div class="settings-row-control">
                <div id="dock-pills-container" class="pill-list" role="group" aria-label="Dock apps">
                  ${enabledDock.map((tok, idx) => {
                    const meta = DOCK_APPS_CATALOG.find((a) => a.token === tok);
                    const lbl = meta ? meta.label : tok;
                    return html`<span class="pill enabled">
                      ${idx > 0
                        ? html`<button
                            type="button"
                            aria-label=${`Move ${lbl} left`}
                            @click=${() => store.moveDockAppToken(tok, -1)}
                            class="pill-move"
                          >
                            ‹
                          </button>`
                        : nothing}
                      <button
                        type="button"
                        aria-pressed="true"
                        @click=${() => store.toggleDockAppToken(tok)}
                        class="pill-toggle"
                      >
                        ✓ ${lbl}
                      </button>
                      ${idx < enabledDock.length - 1
                        ? html`<button
                            type="button"
                            aria-label=${`Move ${lbl} right`}
                            @click=${() => store.moveDockAppToken(tok, 1)}
                            class="pill-move"
                          >
                            ›
                          </button>`
                        : nothing}
                    </span>`;
                  })}
                  ${disabledDock.map(
                    (app) => html`<span class="pill">
                      <button
                        type="button"
                        aria-pressed="false"
                        @click=${() => store.toggleDockAppToken(app.token)}
                        class="pill-toggle"
                      >
                        + ${app.label}
                      </button>
                    </span>`,
                  )}
                </div>
              </div>
            </div>

            <div id="embedded-home" class="settings-list">
              ${visibleHomeItems.map((it) => renderNativeControlRow(store, it))}
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Area Controls</h3>
          </div>
          <div class="card-content settings-list">
            <div class="settings-row">
              <div class="settings-row-text">
                <label for="cfg-default_page_size" class="row-label">Area Cards Per Page</label>
                <p class="row-description">
                  Number of entity tiles shown per page in the Area screen.
                </p>
              </div>
              <div class="settings-row-control">
                <select
                  id="cfg-default_page_size"
                  .value=${String(cfg.default_page_size ?? 3)}
                  @change=${(ev: Event) =>
                    store.stageDeviceSetting(
                      "default_page_size",
                      Number((ev.currentTarget as HTMLSelectElement).value) || 3,
                      "cfg-default_page_size",
                    )}
                >
                  ${[2, 3, 4, 6, 8].map(
                    (n) =>
                      html`<option value=${String(n)} ?selected=${Number(cfg.default_page_size ?? 3) === n}>
                        ${n} cards
                      </option>`,
                  )}
                </select>
              </div>
            </div>

            <div id="embedded-area-ui" class="settings-list">
              ${areaEspItems.map((it) => renderNativeControlRow(store, it))}
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>`;
}
