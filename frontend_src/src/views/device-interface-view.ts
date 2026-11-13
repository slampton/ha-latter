/**
 * Device Interface View (`interface`, D-026 / D-028): Home Screen, Dock Apps, Activity Card, Area Controls, Media Player & Remote Controls.
 */

import {
  renderCard,
  renderNativeControlRow,
  renderSelectRow,
  renderSettingsRow,
} from "../components/controls.js";
import {
  ACTIVITY_SOURCES_CATALOG,
  DOCK_APPS_CATALOG,
} from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { EspHomeEntityItem } from "../types.js";
import { entityLabel } from "../utils/format.js";
import {
  isInterfaceDisplayEntity,
  sortEntitiesByKeywords,
} from "./device-display-view.js";

export function renderDeviceInterfaceView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const remoteGroups = data?.system_config?.remote_groups || [];

  const homeDisplayOrder = ["start screen", "clock face", "time format"];
  const homeDisplayItems = sortEntitiesByKeywords(
    store.getSectionItems("display").filter(isInterfaceDisplayEntity),
    homeDisplayOrder,
  );

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

  const areaOrder = ["default category", "show all category"];
  const areaEspItems = sortEntitiesByKeywords(
    store.getSectionItems("area").filter((it) => !(it.name || "").toLowerCase().includes("ble")),
    areaOrder,
  );
  const musicItems = store.getSectionItems("music");
  const isMediaShortcutSwitch = (it: EspHomeEntityItem): boolean =>
    it.domain === "switch" && /\b(speaker|library)\s+shortcut\b/i.test(it.name || it.entity_id);
  const mediaPlayerOrder = ["album art style", "overlay style"];
  const primaryMusicItems = sortEntitiesByKeywords(
    musicItems.filter(
      (it) =>
        it.domain !== "media_player" &&
        !isMediaShortcutSwitch(it) &&
        !(it.name || "").toLowerCase().includes("sort"),
    ),
    mediaPlayerOrder,
  );
  const shortcutMusicItems = sortEntitiesByKeywords(
    musicItems.filter(isMediaShortcutSwitch),
    ["speaker shortcut", "library shortcut"],
  );
  const mediaSortOrder = [
    "album sort order",
    "artist album sort order",
    "podcast sort order",
  ];
  const sortMusicItems = sortEntitiesByKeywords(
    musicItems.filter((it) => (it.name || "").toLowerCase().includes("sort")),
    mediaSortOrder,
  );
  const remoteEspItems = store.getSectionItems("remote");

  const activityCardOn = cfg.activity_card !== false;
  const enabledSources = new Set(store.getEnabledActivitySources());
  const enabledDock = store.getEnabledDockTokens();
  const disabledDock = DOCK_APPS_CATALOG.filter((a) => !enabledDock.includes(a.token));

  const curDevEntry = (data?.system_devices || []).find(
    (d) => d.subentry_id === store.activeSubentryId,
  );
  const curRemoteMode =
    String(cfg.device_remote_group || curDevEntry?.device_remote_group || "area_auto").trim() ||
    "area_auto";
  const remoteModeOptions: Array<{ value: string; label: string }> = [
    { value: "area_auto", label: "Follow the active Area" },
    ...remoteGroups.map((g) => ({
      value: `group:${g.id}`,
      label: `Group: ${g.name}`,
    })),
    { value: "all", label: "All System remotes" },
  ];
  if (!remoteModeOptions.some((o) => o.value === curRemoteMode)) {
    const rawId = curRemoteMode.startsWith("group:") ? curRemoteMode.slice(6) : curRemoteMode;
    remoteModeOptions.push({
      value: curRemoteMode,
      label: `Missing group (${rawId})`,
    });
  }

  return html`<section id="view-interface">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Home Screen</h3>`,
          contentClass: "settings-list",
          body: html`${homeDisplayItems.map((it) => renderNativeControlRow(store, it))}
            ${renderSettingsRow({
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
      </div>

      <div class="column">
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

        ${primaryMusicItems.length || shortcutMusicItems.length || sortMusicItems.length
          ? renderCard({
              heading: html`<h3 class="card-title">Media Player</h3>`,
              contentClass: "settings-list",
              body: html`${primaryMusicItems.map((it) => renderNativeControlRow(store, it))}
                ${shortcutMusicItems.length
                  ? renderSettingsRow({
                      id: "media-player-shortcuts",
                      label: "Shortcuts",
                      description:
                        "Choose which quick-access buttons appear on the Music player screen.",
                      control: html`<div
                        class="pill-list"
                        role="group"
                        aria-label="Media Player shortcuts"
                      >
                        ${shortcutMusicItems.map((sc) => {
                          const st = String(sc.state ?? "");
                          const isOn = st === "on";
                          const unavailable = st === "unavailable" || st === "unknown";
                          const rawShort = (sc.name || sc.entity_id)
                            .replace(/^music:\s*/i, "")
                            .replace(/^show\s+/i, "")
                            .replace(/\s+shortcut$/i, "")
                            .trim();
                          const lbl = entityLabel(rawShort || sc.name || sc.entity_id);
                          return html`<span class="pill ${isOn ? "enabled" : ""}">
                            <button
                              type="button"
                              aria-pressed=${String(isOn)}
                              ?disabled=${unavailable}
                              @click=${() =>
                                void store.espAction(
                                  sc.entity_id,
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
                ${sortMusicItems.length
                  ? html`<details class="sub-collapsible">
                      <summary>Library Sorting</summary>
                      <div class="card-content settings-list">
                        ${sortMusicItems.map((it) => renderNativeControlRow(store, it))}
                      </div>
                    </details>`
                  : nothing}`,
            })
          : nothing}

        ${renderCard({
          heading: html`<h3 class="card-title">Remote Controls</h3>`,
          contentClass: "settings-list",
          body: html`${renderSelectRow({
              id: "cfg-device_remote_group",
              label: "Remote Control Group",
              description: "Choose which remotes appear on this Device's Remote screen.",
              value: curRemoteMode,
              rawOptions: remoteModeOptions,
              onChange: (val) =>
                store.stageDeviceSetting(
                  "device_remote_group",
                  val,
                  "cfg-device_remote_group",
                ),
            })}
            ${remoteEspItems.map((it) => renderNativeControlRow(store, it))}`,
          footerActions: html`<button
            type="button"
            @click=${() => store.openSystemSection("remotes")}
            class="btn btn-text"
          >
            Manage Remote Groups
          </button>`,
        })}
      </div>
    </div>
  </section>`;
}
