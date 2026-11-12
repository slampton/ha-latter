/**
 * Device Display & Home View (`home_display`): Appearance, Custom Color, Activity Card, Dock Apps, Area Controls & Wallpapers.
 */

import {
  renderCard,
  renderNativeControlRow,
  renderSelectRow,
  renderSettingsRow,
} from "../components/controls.js";
import {
  renderWallpaperGalleryItems,
  renderWallpaperUploadProgress,
  renderWallpaperUploadTrigger,
} from "../components/wallpaper-gallery.js";
import {
  ACTIVITY_SOURCES_CATALOG,
  DOCK_APPS_CATALOG,
  WALLPAPER_ROTATION_OPTIONS,
} from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { EspHomeEntityItem } from "../types.js";
import { defaultThemeHex, entityLabel, isValidHexColor } from "../utils/format.js";

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

  const displayOrder = [
    "clock face",
    "time format",
    "start screen",
    "color profile",
    "auto brightness mode",
    "manual brightness",
    "day brightness",
    "night brightness",
    "day start hour",
    "night start hour",
  ];
  const displayItems = sortByKeywords(store.getSectionItems("display"), displayOrder);
  const autoBrtItem = displayItems.find((it) =>
    (it.name || "").toLowerCase().includes("auto brightness"),
  );
  const autoBrtState = String(autoBrtItem?.state ?? "").trim();
  const autoBrtKnown =
    Boolean(autoBrtItem) && autoBrtState !== "" && autoBrtState !== "unavailable" && autoBrtState !== "unknown";
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

  const homeOrder = ["wake greeting", "weather background", "sun", "moon"];
  const homeItems = sortByKeywords(store.getSectionItems("home"), homeOrder);
  const weatherBgSwitch = homeItems.find((it) =>
    (it.name || "").toLowerCase().includes("weather background"),
  );
  const weatherBgOff = weatherBgSwitch ? weatherBgSwitch.state === "off" : false;
  const isCelestialSwitch = (it: EspHomeEntityItem): boolean =>
    it.domain === "switch" && /^(?:home:\s*)?(?:sun|moon)$/i.test((it.name || "").trim());
  const celestialItems = homeItems.filter(isCelestialSwitch);
  const visibleHomeItems = homeItems.filter((it) => !isCelestialSwitch(it));

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

  return html`<section id="view-home_display">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Display & Appearance",
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

        ${renderCard({
          heading: html`<h3 class="card-title">Activity Card</h3>`,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              labelHtml: html`<label for="cfg-activity_card" class="row-label">Show the Activity Card</label>`,
              description:
                "Shows live timers, alarms, media queue, stopwatch, and next calendar event on Home.",
              control: html`<input
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
              />`,
            })}
            ${activityCardOn
              ? renderSettingsRow({
                  id: "activity-sources",
                  label: "Activity Card Sources",
                  description: "Choose which live items appear in the Activity Card.",
                  stacked: true,
                  control: html`<div class="pill-list" role="group" aria-label="Activity Card sources">
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
                  </div>`,
                })
              : nothing}`,
        })}

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

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Home Screen</h3>`,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: "Dock Apps",
              description: "Toggle and reorder apps shown in the Home Dock.",
              stacked: true,
              control: html`<div id="dock-pills-container" class="pill-list" role="group" aria-label="Dock apps">
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
              </div>`,
            })}
            <div id="embedded-home" class="settings-list">
              ${visibleHomeItems.map((it) => {
                const row = renderNativeControlRow(store, it);
                if (weatherBgSwitch && it.entity_id === weatherBgSwitch.entity_id) {
                  return html`${row}
                    ${!weatherBgOff && celestialItems.length > 0
                      ? renderSettingsRow({
                          id: "weather-celestial-bodies",
                          label: "Sun & Moon",
                          description:
                            "Choose which sky bodies appear on the live Weather Background.",
                          control: html`<div
                            class="pill-list"
                            role="group"
                            aria-label="Sun and Moon"
                          >
                            ${celestialItems.map((cel) => {
                              const st = String(cel.state ?? "");
                              const isOn = st === "on";
                              const unavailable = st === "unavailable" || st === "unknown";
                              const lbl = entityLabel(
                                (cel.name || cel.entity_id).replace(/^home:\s*/i, ""),
                              );
                              return html`<span class="pill ${isOn ? "enabled" : ""}">
                                <button
                                  type="button"
                                  aria-pressed=${String(isOn)}
                                  ?disabled=${unavailable}
                                  @click=${() =>
                                    void store.espAction(
                                      cel.entity_id,
                                      isOn ? "turn_off" : "turn_on",
                                      isOn ? "off" : "on",
                                    )}
                                  class="pill-toggle"
                                >
                                  ${isOn ? `✓ ${lbl}` : `+ ${lbl}`}
                                </button>
                              </span>`;
                            })}
                          </div>`,
                        })
                      : nothing}`;
                }
                return row;
              })}
              ${!weatherBgSwitch && !weatherBgOff && celestialItems.length > 0
                ? renderSettingsRow({
                    id: "weather-celestial-bodies",
                    label: "Sun & Moon",
                    description: "Choose which sky bodies appear on the live Weather Background.",
                    control: html`<div class="pill-list" role="group" aria-label="Sun and Moon">
                      ${celestialItems.map((cel) => {
                        const st = String(cel.state ?? "");
                        const isOn = st === "on";
                        const unavailable = st === "unavailable" || st === "unknown";
                        const lbl = entityLabel(
                          (cel.name || cel.entity_id).replace(/^home:\s*/i, ""),
                        );
                        return html`<span class="pill ${isOn ? "enabled" : ""}">
                          <button
                            type="button"
                            aria-pressed=${String(isOn)}
                            ?disabled=${unavailable}
                            @click=${() =>
                              void store.espAction(
                                cel.entity_id,
                                isOn ? "turn_off" : "turn_on",
                                isOn ? "off" : "on",
                              )}
                            class="pill-toggle"
                          >
                            ${isOn ? `✓ ${lbl}` : `+ ${lbl}`}
                          </button>
                        </span>`;
                      })}
                    </div>`,
                  })
                : nothing}
            </div>`,
        })}

        ${renderCard({
          heading: html`<h3 class="card-title">Area Controls</h3>`,
          contentClass: "settings-list",
          body: html`${renderSelectRow({
              id: "cfg-default_page_size",
              label: "Area Cards Per Page",
              description: "Number of entity tiles shown per page in the Area screen.",
              value: String(cfg.default_page_size ?? 3),
              rawOptions: [2, 3, 4, 6, 8].map((n) => ({ value: String(n), label: `${n} cards` })),
              onChange: (val) =>
                store.stageDeviceSetting(
                  "default_page_size",
                  Number(val) || 3,
                  "cfg-default_page_size",
                ),
            })}
            <div id="embedded-area-ui" class="settings-list">
              ${areaEspItems.map((it) => renderNativeControlRow(store, it))}
            </div>`,
        })}
      </div>
    </div>
  </section>`;
}
