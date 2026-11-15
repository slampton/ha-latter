/**
 * Device Interface View (`interface`, D-026 / D-028 / D-030 / D-033 / D-034 / D-035 / D-036 / D-037):
 * Navigation, screen structure & content routing preferences.
 * Column 1: Home Screen (Enable Home Screen, Start Screen, Home Time Tap, Return to Home Timeout, Dock Apps & Activity Card),
 *           Home Controls & Time (Show UTC Clock, World Clocks & 2-way Alarms).
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
  ALARM_RECURRENCE_OPTIONS,
  AREA_CATEGORIES_CATALOG,
  DEFAULT_ALARMS_SUMMARY,
  DOCK_APPS_CATALOG,
  HOME_CATEGORIES_CATALOG,
  HOME_CLOCK_TAP_OPTIONS,
  MAX_WORLD_CLOCKS,
  RETURN_TO_HOME_TIMEOUT_OPTIONS,
  START_SCREEN_OPTIONS,
  WORLD_CLOCK_ZONES_CATALOG,
} from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { DevicePrefItem } from "../types.js";

interface AlarmSlotView {
  time: string;
  enabled: boolean;
  recurrence: number;
}

const DEFAULT_ALARM_SLOTS: ReadonlyArray<AlarmSlotView> = [
  { time: "07:00", enabled: false, recurrence: 1 },
  { time: "08:30", enabled: false, recurrence: 2 },
  { time: "09:00", enabled: false, recurrence: 2 },
];

function parseWorldClocksList(raw: unknown): string[] {
  const out: string[] = [];
  for (const part of String(raw ?? "").split(",")) {
    const tok = part.trim();
    if (!tok || tok === "UTC" || tok === "Etc/UTC" || tok === "GMT" || tok === "Etc/GMT") {
      continue;
    }
    if (!out.includes(tok)) {
      out.push(tok);
      if (out.length >= MAX_WORLD_CLOCKS) break;
    }
  }
  return out;
}

function worldClockCityLabel(iana: string): string {
  const found = WORLD_CLOCK_ZONES_CATALOG.find((z) => z.iana === iana);
  if (found) return found.city;
  const tail = iana.split("/").pop() || iana;
  return tail.replace(/_/g, " ");
}

function parseAlarmsSummary(raw: unknown): [AlarmSlotView, AlarmSlotView, AlarmSlotView] {
  const text = String(raw || DEFAULT_ALARMS_SUMMARY).trim();
  const parts = text.split(";");
  const slots: AlarmSlotView[] = [];
  for (let i = 0; i < 3; i++) {
    const fallback = DEFAULT_ALARM_SLOTS[i];
    const seg = (parts[i] || "").trim();
    const m = /^(\d{1,2}):(\d{2})\|([01])\|([0-3])$/.exec(seg);
    if (!m) {
      slots.push({ ...fallback });
      continue;
    }
    const hh = Number(m[1]);
    const mm = Number(m[2]);
    if (hh < 0 || hh > 23 || mm < 0 || mm > 59) {
      slots.push({ ...fallback });
      continue;
    }
    slots.push({
      time: `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`,
      enabled: m[3] === "1",
      recurrence: Number(m[4]),
    });
  }
  return [slots[0], slots[1], slots[2]];
}

function serializeAlarmsSummary(slots: ReadonlyArray<AlarmSlotView>): string {
  return slots
    .slice(0, 3)
    .map((s) => `${s.time}|${s.enabled ? 1 : 0}|${s.recurrence}`)
    .join(";");
}

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
    startScreenPref?.value ?? cfg.start_screen ?? (homeScreenEnabled ? "Home" : "Time App"),
  );
  const startScreenValue =
    !homeScreenEnabled && rawStartValue === "Home" ? "Time App" : rawStartValue;

  const homeClockTapPref = store.getPref("home_clock_tap_action");
  const homeClockTapOptions = (
    homeClockTapPref?.options && homeClockTapPref.options.length > 0
      ? homeClockTapPref.options
      : HOME_CLOCK_TAP_OPTIONS
  ).map((opt) => ({ value: opt, label: opt }));
  const homeClockTapValue = String(
    homeClockTapPref?.value ?? cfg.home_clock_tap_action ?? "Time App",
  );

  const showUtcClockPref = store.getPref("show_utc_clock");
  const showUtcClock = showUtcClockPref
    ? Boolean(showUtcClockPref.value)
    : Boolean(cfg.show_utc_clock);

  const worldClocksPref = store.getPref("world_clocks");
  const enabledWorldClocks = parseWorldClocksList(worldClocksPref?.value ?? cfg.world_clocks ?? "");
  const atWorldClockLimit = enabledWorldClocks.length >= MAX_WORLD_CLOCKS;
  const availableWorldClockOptions = WORLD_CLOCK_ZONES_CATALOG.filter(
    (z) => !enabledWorldClocks.includes(z.iana),
  );

  const alarmsSummaryPref = store.getPref("alarms_summary");
  const alarmSlots = parseAlarmsSummary(
    alarmsSummaryPref?.value ?? cfg.alarms_summary ?? DEFAULT_ALARMS_SUMMARY,
  );

  const updateWorldClocks = (nextZones: string[]): void => {
    store.stageDeviceSetting("world_clocks", nextZones.slice(0, MAX_WORLD_CLOCKS).join(","));
  };

  const moveWorldClock = (iana: string, delta: -1 | 1): void => {
    const idx = enabledWorldClocks.indexOf(iana);
    const target = idx + delta;
    if (idx < 0 || target < 0 || target >= enabledWorldClocks.length) return;
    const next = [...enabledWorldClocks];
    const [picked] = next.splice(idx, 1);
    next.splice(target, 0, picked);
    updateWorldClocks(next);
  };

  const removeWorldClock = (iana: string): void => {
    updateWorldClocks(enabledWorldClocks.filter((z) => z !== iana));
  };

  const onAddWorldClock = (ev: Event): void => {
    const sel = ev.currentTarget as HTMLSelectElement;
    const picked = sel.value.trim();
    sel.value = "";
    if (!picked || atWorldClockLimit || enabledWorldClocks.includes(picked)) return;
    updateWorldClocks([...enabledWorldClocks, picked]);
  };

  const updateAlarmSlot = (idx: 0 | 1 | 2, patch: Partial<AlarmSlotView>, focusId?: string): void => {
    const next: [AlarmSlotView, AlarmSlotView, AlarmSlotView] = [
      { ...alarmSlots[0] },
      { ...alarmSlots[1] },
      { ...alarmSlots[2] },
    ];
    const merged = { ...next[idx], ...patch };
    if (!/^\d{2}:\d{2}$/.test(merged.time)) {
      return;
    }
    next[idx] = merged;
    store.stageDeviceSetting("alarms_summary", serializeAlarmsSummary(next), focusId);
  };

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
                    id: "cfg-home_clock_tap_action",
                    label: "Home Time Tap",
                    description:
                      "Choose whether tapping the clock readout on Home opens the Time app or the standalone Clock Face.",
                    value: homeClockTapValue,
                    rawOptions: homeClockTapOptions,
                    onChange: (val) => {
                      store.stageDeviceSetting(
                        "home_clock_tap_action",
                        val,
                        "cfg-home_clock_tap_action",
                      );
                    },
                  })}
                  ${renderSelectRow({
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

        ${renderCard({
          id: "card-time",
          heading: html`<h3 class="card-title">Time</h3>`,
          contentClass: "settings-list",
          body: html`${renderSwitchRow({
              id: "cfg-show_utc_clock",
              label: "Show UTC Clock",
              description: "Pin a live 24-hour UTC reference card to this Device's Clock tab.",
              checked: showUtcClock,
              onChange: (checked) => {
                store.stageDeviceSetting("show_utc_clock", checked, "cfg-show_utc_clock");
              },
            })}
            ${renderSettingsRow({
              id: "time-world-clocks",
              label: "World Clocks",
              forId: "cfg-world_clocks_add",
              description:
                "Track up to 4 remote IANA time zones on the Clock tab alongside local time.",
              stacked: true,
              control: html`<div class="stack">
                ${enabledWorldClocks.length
                  ? html`<div
                      id="world-clocks-pills"
                      class="pill-list"
                      role="group"
                      aria-label="Configured World Clocks"
                    >
                      ${enabledWorldClocks.map((iana, idx) => {
                        const lbl = worldClockCityLabel(iana);
                        return html`<span class="pill enabled">
                          ${idx > 0
                            ? html`<button
                                type="button"
                                aria-label=${`Move ${lbl} left`}
                                @click=${() => moveWorldClock(iana, -1)}
                                class="pill-move"
                              >
                                ‹
                              </button>`
                            : nothing}
                          <button
                            type="button"
                            aria-pressed="true"
                            aria-label=${`Remove ${lbl} (${iana})`}
                            @click=${() => removeWorldClock(iana)}
                            class="pill-toggle"
                          >
                            ✓ ${lbl}
                          </button>
                          ${idx < enabledWorldClocks.length - 1
                            ? html`<button
                                type="button"
                                aria-label=${`Move ${lbl} right`}
                                @click=${() => moveWorldClock(iana, 1)}
                                class="pill-move"
                              >
                                ›
                              </button>`
                            : nothing}
                        </span>`;
                      })}
                    </div>`
                  : nothing}
                <div class="input-action-row">
                  <select
                    id="cfg-world_clocks_add"
                    ?disabled=${atWorldClockLimit || availableWorldClockOptions.length === 0}
                    .value=${""}
                    @change=${onAddWorldClock}
                  >
                    <option value="" selected>
                      ${atWorldClockLimit
                        ? "Maximum 4 World Clocks added"
                        : "Add a city time zone…"}
                    </option>
                    ${availableWorldClockOptions.map(
                      (z) => html`<option value=${z.iana}>${z.label}</option>`,
                    )}
                  </select>
                </div>
              </div>`,
            })}
            ${renderSettingsRow({
              id: "time-alarms",
              label: "Alarms",
              description: "Syncs 2-way with on-device alarm edits (1-minute precision).",
              stacked: true,
              control: html`<div class="stack" role="group" aria-label="Device alarms">
                ${([0, 1, 2] as const).map((idx) => {
                  const slot = alarmSlots[idx];
                  const timeId = `cfg-alarm_${idx + 1}_time`;
                  const recId = `cfg-alarm_${idx + 1}_recurrence`;
                  const enId = `cfg-alarm_${idx + 1}_enabled`;
                  return html`<div class="list-row">
                    <div class="list-row-main">
                      <div class="stacked-field">
                        <label for=${timeId}>Alarm ${idx + 1} time</label>
                        <input
                          type="time"
                          id=${timeId}
                          step="60"
                          .value=${slot.time}
                          @change=${(ev: Event) => {
                            const val = (ev.currentTarget as HTMLInputElement).value;
                            if (val) updateAlarmSlot(idx, { time: val.slice(0, 5) }, timeId);
                          }}
                        />
                      </div>
                      <div class="stacked-field">
                        <label for=${recId}>Alarm ${idx + 1} schedule</label>
                        <select
                          id=${recId}
                          .value=${String(slot.recurrence)}
                          @change=${(ev: Event) =>
                            updateAlarmSlot(
                              idx,
                              { recurrence: Number((ev.currentTarget as HTMLSelectElement).value) },
                              recId,
                            )}
                        >
                          ${ALARM_RECURRENCE_OPTIONS.map(
                            (opt) =>
                              html`<option
                                value=${String(opt.value)}
                                ?selected=${opt.value === slot.recurrence}
                              >
                                ${opt.label}
                              </option>`,
                          )}
                        </select>
                      </div>
                    </div>
                    <label for=${enId} class="inline-switch">
                      <span>Enabled</span>
                      <input
                        type="checkbox"
                        id=${enId}
                        .checked=${slot.enabled}
                        @change=${(ev: Event) =>
                          updateAlarmSlot(
                            idx,
                            { enabled: (ev.currentTarget as HTMLInputElement).checked },
                            enId,
                          )}
                        role="switch"
                        class="switch"
                      />
                    </label>
                  </div>`;
                })}
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
