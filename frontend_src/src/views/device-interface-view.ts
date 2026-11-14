/**
 * Device Interface View (`interface`, D-026 / D-028 / D-030 / D-033 / D-034 / D-035 / D-036):
 * Navigation, screen structure & content routing preferences.
 * Column 1: Home Screen (Enable Home Screen, Start Screen, Return to Home Timeout, Dock Apps & Activity Card) & Home Controls.
 * Column 2: Area Controls (Area Categories pills), Media Player (Shortcuts & Library Sorting) & Remote Controls.
 */

import {
  renderCard,
  renderNativeControlRow,
  renderPrefControlRow,
  renderSelectRow,
  renderSettingsRow,
  renderSwitchRow,
} from "../components/controls.js";
import {
  ACTIVITY_SOURCES_CATALOG,
  AREA_CATEGORIES_CATALOG,
  DOCK_APPS_CATALOG,
  HOME_CATEGORIES_CATALOG,
  RETURN_TO_HOME_TIMEOUT_OPTIONS,
  START_SCREEN_OPTIONS,
} from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { DevicePrefItem } from "../types.js";

export function renderDeviceInterfaceView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const remoteGroups = data?.system_config?.remote_groups || [];

  const homeScreenEnabledPref = store.getPref("home_screen_enabled");
  const homeScreenEnabled = homeScreenEnabledPref
    ? Boolean(homeScreenEnabledPref.value)
    : cfg.home_screen_enabled !== false;

  const startScreenPref = store.getPref("start_screen");
  const rawStartOptions =
    startScreenPref?.options && startScreenPref.options.length > 0
      ? startScreenPref.options
      : START_SCREEN_OPTIONS;
  const visibleStartOptions = (
    homeScreenEnabled ? rawStartOptions : rawStartOptions.filter((opt) => opt !== "Home")
  ).map((opt) => ({ value: opt, label: opt }));
  const rawStartValue = String(
    startScreenPref?.value ?? cfg.start_screen ?? (homeScreenEnabled ? "Home" : "Clock"),
  );
  const startScreenValue =
    !homeScreenEnabled && rawStartValue === "Home" ? "Clock" : rawStartValue;

  const returnTimeoutPref = store.getPref("return_to_home_timeout");
  const rawReturnTimeoutOptions = (
    returnTimeoutPref?.options && returnTimeoutPref.options.length > 0
      ? returnTimeoutPref.options
      : RETURN_TO_HOME_TIMEOUT_OPTIONS
  ).map((opt) => ({ value: opt, label: opt }));
  const returnTimeoutValue = String(
    returnTimeoutPref?.value ?? cfg.return_to_home_timeout ?? "2 min",
  );

  const enabledHomeCats = store.getEnabledHomeCategories();
  const disabledHomeCats = HOME_CATEGORIES_CATALOG.filter(
    (c) => !enabledHomeCats.includes(c.token),
  );

  const areaExtraItems = store.getSectionItems("area").filter((it) => it.key !== "ble_beacon_mode");
  const enabledAreaCats = store.getEnabledAreaCategories();
  const disabledAreaCats = AREA_CATEGORIES_CATALOG.filter(
    (c) => !enabledAreaCats.includes(c.token),
  );

  // Media Player shortcuts and sorting prefs
  const showSpeakerPref = store.getPref("show_speaker_shortcut");
  const showLibraryPref = store.getPref("show_library_shortcut");
  const shortcutPrefs = [
    { pref: showSpeakerPref, label: "Speaker" },
    { pref: showLibraryPref, label: "Library" },
  ].filter((c): c is { pref: DevicePrefItem; label: string } => Boolean(c.pref));

  const sortMusicPrefs = store.getPrefs([
    "album_sort_order",
    "artist_album_sort_order",
    "podcast_sort_order",
  ]);

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
          body: html`${renderSwitchRow({
              id: "cfg-home_screen_enabled",
              label: "Enable Home Screen",
              description:
                "Provides the Home screen and App Dock. Turn off to lock this Device to a single Start Screen app.",
              checked: homeScreenEnabled,
              onChange: (checked) => {
                store.stageDeviceSetting(
                  "home_screen_enabled",
                  checked,
                  "cfg-home_screen_enabled",
                );
              },
            })}
            ${renderSelectRow({
              id: "cfg-start_screen",
              label: "Start Screen",
              description: homeScreenEnabled
                ? "Choose the screen shown on startup. Swipe up from the bottom to return to Home."
                : "Single-app screen shown at all times while the Home screen is disabled.",
              value: startScreenValue,
              rawOptions: visibleStartOptions,
              onChange: (val) => {
                store.stageDeviceSetting(
                  "start_screen",
                  val,
                  "cfg-start_screen",
                );
              },
            })}
            ${homeScreenEnabled
              ? html`${renderSelectRow({
                    id: "cfg-return_to_home_timeout",
                    label: "Return to Home Timeout",
                    description:
                      "Resets idle screens back to Home unless media is playing or a live activity is active.",
                    value: returnTimeoutValue,
                    rawOptions: rawReturnTimeoutOptions,
                    onChange: (val) => {
                      store.stageDeviceSetting(
                        "return_to_home_timeout",
                        val,
                        "cfg-return_to_home_timeout",
                      );
                    },
                  })}
                  ${renderSettingsRow({
                    label: "Dock Apps",
                    description: "Toggle and reorder apps shown in the Home Dock.",
                    stacked: true,
                    control: html`<div
                      id="dock-pills-container"
                      class="pill-list"
                      role="group"
                      aria-label="Dock apps"
                    >
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
                  ${renderSettingsRow({
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
                        control: html`<div
                          class="pill-list"
                          role="group"
                          aria-label="Activity Card sources"
                        >
                          ${ACTIVITY_SOURCES_CATALOG.map((src) => {
                            const on = enabledSources.has(src.token);
                            return html`<span
                              data-src=${src.token}
                              data-label=${src.label}
                              class="pill ${on ? "enabled" : ""}"
                            >
                              <button
                                type="button"
                                aria-pressed=${String(on)}
                                @click=${() => store.toggleActivitySource(src.token)}
                                class="pill-toggle"
                              >
                                ${on ? `✓ ${src.label}` : `+ ${src.label}`}
                              </button>
                            </span>`;
                          })}
                        </div>`,
                      })
                    : nothing}`
              : nothing}`,
        })}

        ${renderCard({
          heading: html`<h3 class="card-title">Home Controls</h3>`,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
            label: "Home Categories",
            description:
              "Toggle and reorder categories shown in the Home Hub. The first available category opens by default; categories with no configured entity are not displayed.",
            stacked: true,
            control: html`<div
              id="home-categories-pills"
              class="pill-list"
              role="group"
              aria-label="Home categories"
            >
              ${enabledHomeCats.map((tok, idx) => {
                const meta = HOME_CATEGORIES_CATALOG.find((c) => c.token === tok);
                const lbl = meta ? meta.label : tok;
                return html`<span class="pill enabled">
                  ${idx > 0
                    ? html`<button
                        type="button"
                        aria-label=${`Move ${lbl} left`}
                        @click=${() => store.moveHomeCategoryToken(tok, -1)}
                        class="pill-move"
                      >
                        ‹
                      </button>`
                    : nothing}
                  <button
                    type="button"
                    aria-pressed="true"
                    @click=${() => store.toggleHomeCategoryToken(tok)}
                    class="pill-toggle"
                  >
                    ✓ ${lbl}
                  </button>
                  ${idx < enabledHomeCats.length - 1
                    ? html`<button
                        type="button"
                        aria-label=${`Move ${lbl} right`}
                        @click=${() => store.moveHomeCategoryToken(tok, 1)}
                        class="pill-move"
                      >
                        ›
                      </button>`
                    : nothing}
                </span>`;
              })}
              ${disabledHomeCats.map(
                (cat) => html`<span class="pill">
                  <button
                    type="button"
                    aria-pressed="false"
                    @click=${() => store.toggleHomeCategoryToken(cat.token)}
                    class="pill-toggle"
                  >
                    + ${cat.label}
                  </button>
                </span>`,
              )}
            </div>`,
          })}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Area Controls</h3>`,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: "Area Categories",
              description:
                "Toggle and reorder categories shown in the Area screen. The first available category opens by default; categories with no entities in the active Area are not displayed.",
              stacked: true,
              control: html`<div
                id="area-categories-pills"
                class="pill-list"
                role="group"
                aria-label="Area categories"
              >
                ${enabledAreaCats.map((tok, idx) => {
                  const meta = AREA_CATEGORIES_CATALOG.find((c) => c.token === tok);
                  const lbl = meta ? meta.label : tok;
                  return html`<span class="pill enabled">
                    ${idx > 0
                      ? html`<button
                          type="button"
                          aria-label=${`Move ${lbl} left`}
                          @click=${() => store.moveAreaCategoryToken(tok, -1)}
                          class="pill-move"
                        >
                          ‹
                        </button>`
                      : nothing}
                    <button
                      type="button"
                      aria-pressed="true"
                      @click=${() => store.toggleAreaCategoryToken(tok)}
                      class="pill-toggle"
                    >
                      ✓ ${lbl}
                    </button>
                    ${idx < enabledAreaCats.length - 1
                      ? html`<button
                          type="button"
                          aria-label=${`Move ${lbl} right`}
                          @click=${() => store.moveAreaCategoryToken(tok, 1)}
                          class="pill-move"
                        >
                          ›
                        </button>`
                      : nothing}
                  </span>`;
                })}
                ${disabledAreaCats.map(
                  (cat) => html`<span class="pill">
                    <button
                      type="button"
                      aria-pressed="false"
                      @click=${() => store.toggleAreaCategoryToken(cat.token)}
                      class="pill-toggle"
                    >
                      + ${cat.label}
                    </button>
                  </span>`,
                )}
              </div>`,
            })}
            ${areaExtraItems.map((it) => renderNativeControlRow(store, it))}`,
        })}

        ${shortcutPrefs.length || sortMusicPrefs.length
          ? renderCard({
              heading: html`<h3 class="card-title">Media Player</h3>`,
              contentClass: "settings-list",
              body: html`${shortcutPrefs.length
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
                        ${shortcutPrefs.map(({ pref, label }) => {
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
                    })
                  : nothing}
                ${sortMusicPrefs.map((p) => renderPrefControlRow(store, p))}`,
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
