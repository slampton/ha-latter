/**
 * Device Interface View (`interface`, D-026 / D-028 / D-030 / D-033 / D-034 / D-035 / D-036 / D-037 / D-038):
 * Navigation, screen structure & content routing preferences.
 * Column 1: Home Screen (Enable Home Screen, Start Screen, Home Time Tap, Return to Home Timeout, Dock Apps & Activity Card),
 *           Home Controls & Time (Local Clock Label, Show UTC Clock, custom-labeled World Clocks & 2-way Alarms).
 * Column 2: Area Controls (Area Categories pills), Media Player (Shortcuts & Library Sorting) & Remote Controls.
 */

import {
  renderCard,
  renderNativeControlRow,
  renderPrefControlRow,
  renderSelectRow,
  renderSettingsRow,
  renderSwitchRow,
  renderTrashIconButton,
} from "../components/controls.js";
import {
  ACTIVITY_SOURCES_CATALOG,
  ALARM_RECURRENCE_OPTIONS,
  AREA_CATEGORIES_CATALOG,
  DEFAULT_ALARMS_SUMMARY,
  HOME_CATEGORIES_CATALOG,
  HOME_CLOCK_TAP_OPTIONS,
  MAX_DOCK_ITEMS,
  MAX_PINNED_ITEMS,
  MAX_WORLD_CLOCKS,
  RETURN_TO_HOME_TIMEOUT_OPTIONS,
  SHORTCUT_ROUTES_CATALOG,
  START_SCREEN_OPTIONS,
  WORLD_CLOCK_ZONES_CATALOG,
} from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import { ROUTE_PREVIEW_ICONS, shortcutActionLabel } from "../mdi-catalog.js";
import type { StudioStore } from "../state/store.js";
import type { DevicePrefItem, ShortcutItem } from "../types.js";

interface AlarmSlotView {
  time: string;
  enabled: boolean;
  recurrence: number;
}

export interface WorldClockItemView {
  label: string;
  iana: string;
}

const DEFAULT_ALARM_SLOTS: ReadonlyArray<AlarmSlotView> = [
  { time: "07:00", enabled: false, recurrence: 1 },
  { time: "08:30", enabled: false, recurrence: 2 },
  { time: "09:00", enabled: false, recurrence: 2 },
];

const PINNED_UTC_ZONES = new Set(["UTC", "Etc/UTC", "GMT", "Etc/GMT", "Etc/GMT+0", "Etc/GMT-0", "Etc/GMT0"]);
const IANA_ZONE_PATTERN = /^[A-Za-z0-9_+-]+(?:\/[A-Za-z0-9_+-]+)+$/;
const TEXT_INPUT_DEBOUNCE_MS = 600;

function isImeSafeEnter(ev: KeyboardEvent): boolean {
  return ev.key === "Enter" && !ev.isComposing && ev.keyCode !== 229;
}

function sanitizeClockLabel(raw: unknown, maxBytes = 32): string {
  const str = String(raw ?? "");
  let collapsed = "";
  let prevSpace = true;
  for (const ch of str) {
    const code = ch.charCodeAt(0);
    if (
      code < 0x20 ||
      code === 0x7f ||
      ch === "|" ||
      ch === ";" ||
      ch === "\x1e" ||
      ch === "\x1f" ||
      ch === " " ||
      ch === "\t" ||
      ch === "\r" ||
      ch === "\n"
    ) {
      if (!prevSpace) {
        collapsed += " ";
        prevSpace = true;
      }
      continue;
    }
    collapsed += ch;
    prevSpace = false;
  }
  const trimmed = collapsed.trim();
  if (typeof TextEncoder === "undefined") {
    return trimmed.slice(0, maxBytes).trimEnd();
  }
  const enc = new TextEncoder();
  if (enc.encode(trimmed).length <= maxBytes) {
    return trimmed;
  }
  let out = "";
  for (const cp of trimmed) {
    if (enc.encode(out + cp).length > maxBytes) break;
    out += cp;
  }
  return out.trimEnd();
}

function fallbackLabelForIana(iana: string): string {
  const tail = iana.split("/").pop() || iana;
  return sanitizeClockLabel(tail.replace(/_/g, " ")) || iana;
}

function parseWorldClocksSpec(raw: unknown): WorldClockItemView[] {
  const out: WorldClockItemView[] = [];
  const seen = new Set<string>();
  for (const part of String(raw ?? "").split(";")) {
    const rec = part.trim();
    if (!rec) continue;
    const pipeIdx = rec.indexOf("|");
    if (pipeIdx < 0) continue;
    const rawLbl = rec.slice(0, pipeIdx);
    const iana = rec.slice(pipeIdx + 1).trim();
    if (!iana || PINNED_UTC_ZONES.has(iana) || !IANA_ZONE_PATTERN.test(iana)) {
      continue;
    }
    const label = sanitizeClockLabel(rawLbl) || fallbackLabelForIana(iana);
    const dedupKey = `${label.toLowerCase()}|${iana}`;
    if (seen.has(dedupKey)) continue;
    seen.add(dedupKey);
    out.push({ label, iana });
    if (out.length >= MAX_WORLD_CLOCKS) break;
  }
  return out;
}

function serializeWorldClocksSpec(items: ReadonlyArray<WorldClockItemView>): string {
  return items
    .slice(0, MAX_WORLD_CLOCKS)
    .map((item) => {
      const cleaned = sanitizeClockLabel(item.label);
      return cleaned ? `${cleaned}|${item.iana}` : "";
    })
    .filter(Boolean)
    .join(";");
}

const KNOWN_WORLD_CLOCK_ZONES = new Set(WORLD_CLOCK_ZONES_CATALOG.map((z) => z.iana));

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

  const localClockLabelPref = store.getPref("local_clock_label");
  const localClockLabelValue = sanitizeClockLabel(
    localClockLabelPref?.value ?? cfg.local_clock_label ?? "",
  );

  const showUtcClockPref = store.getPref("show_utc_clock");
  const showUtcClock = showUtcClockPref
    ? Boolean(showUtcClockPref.value)
    : Boolean(cfg.show_utc_clock);

  const worldClocksPref = store.getPref("world_clocks");
  const enabledWorldClocks = parseWorldClocksSpec(worldClocksPref?.value ?? cfg.world_clocks ?? "");
  const atWorldClockLimit = enabledWorldClocks.length >= MAX_WORLD_CLOCKS;

  const renderWorldClockZoneOptions = (selectedIana: string): TemplateResult => {
    const missingSelected =
      selectedIana && !KNOWN_WORLD_CLOCK_ZONES.has(selectedIana)
        ? html`<option value=${selectedIana} selected>${selectedIana}</option>`
        : nothing;
    return html`${missingSelected}${WORLD_CLOCK_ZONES_CATALOG.map(
      (z) => html`<option value=${z.iana} ?selected=${z.iana === selectedIana}>${z.label}</option>`,
    )}`;
  };

  const alarmsSummaryPref = store.getPref("alarms_summary");
  const alarmSlots = parseAlarmsSummary(
    alarmsSummaryPref?.value ?? cfg.alarms_summary ?? DEFAULT_ALARMS_SUMMARY,
  );

  const updateWorldClocks = (
    nextItems: WorldClockItemView[],
    focusId?: string,
    debounceMs?: number,
  ): void => {
    store.stageDeviceSetting("world_clocks", serializeWorldClocksSpec(nextItems), focusId, debounceMs);
  };

  const updateWorldClockItem = (
    idx: number,
    patch: Partial<WorldClockItemView>,
    focusId?: string,
    debounceMs?: number,
  ): void => {
    if (idx < 0 || idx >= enabledWorldClocks.length) return;
    const prev = enabledWorldClocks[idx];
    const nextIana = (patch.iana ?? prev.iana).trim();
    if (!nextIana || PINNED_UTC_ZONES.has(nextIana) || !IANA_ZONE_PATTERN.test(nextIana)) return;
    const nextLabel =
      patch.label !== undefined ? sanitizeClockLabel(patch.label) : prev.label;
    if (!nextLabel) return;
    const dup = enabledWorldClocks.some(
      (item, i) =>
        i !== idx && item.iana === nextIana && item.label.toLowerCase() === nextLabel.toLowerCase(),
    );
    if (dup) return;
    const next = enabledWorldClocks.map((item, i) =>
      i === idx ? { label: nextLabel, iana: nextIana } : { ...item },
    );
    updateWorldClocks(next, focusId, debounceMs);
  };

  const moveWorldClock = (idx: number, delta: -1 | 1): void => {
    const target = idx + delta;
    if (idx < 0 || target < 0 || target >= enabledWorldClocks.length) return;
    const next = [...enabledWorldClocks];
    const [picked] = next.splice(idx, 1);
    next.splice(target, 0, picked);
    updateWorldClocks(next);
  };

  const removeWorldClock = (idx: number): void => {
    updateWorldClocks(enabledWorldClocks.filter((_, i) => i !== idx));
  };

  const getRenderRoot = (): ShadowRoot | null =>
    (store.host as unknown as { renderRoot?: ShadowRoot }).renderRoot ?? null;

  const onAddWorldClock = (): void => {
    if (atWorldClockLimit) return;
    const root = getRenderRoot();
    const newLabelEl = root?.getElementById("cfg-world_clock_new_label") as HTMLInputElement | null;
    const zoneSelEl = root?.getElementById("cfg-world_clocks_add") as HTMLSelectElement | null;
    const typedLabel = sanitizeClockLabel(newLabelEl?.value ?? store.worldClockNewLabel);
    const picked = (zoneSelEl?.value ?? store.worldClockNewZone).trim();
    if (!typedLabel) {
      store.showToast("Enter a city or label for this World Clock", true);
      newLabelEl?.focus();
      return;
    }
    if (!picked || PINNED_UTC_ZONES.has(picked) || !IANA_ZONE_PATTERN.test(picked)) {
      store.showToast("Select a time zone for this World Clock", true);
      zoneSelEl?.focus();
      return;
    }
    const dup = enabledWorldClocks.some(
      (item) => item.iana === picked && item.label.toLowerCase() === typedLabel.toLowerCase(),
    );
    if (dup) {
      store.showToast("That World Clock is already added", true);
      return;
    }
    store.worldClockNewLabel = "";
    store.worldClockNewZone = "";
    if (newLabelEl) newLabelEl.value = "";
    if (zoneSelEl) zoneSelEl.value = "";
    updateWorldClocks([...enabledWorldClocks, { label: typedLabel, iana: picked }], "btn-world_clock_add");
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
  const dockItems = store.getDockItems();
  const pinnedItems = store.getPinnedItems();
  const shortcutEntityMap = new Map(
    (data?.catalog?.shortcut_entities || []).map((e) => [e.id, e]),
  );
  const routeSpecMap = new Map(
    SHORTCUT_ROUTES_CATALOG.map((r) => [r.token, r]),
  );

  const renderShortcutRow = (
    listKey: "dock_items" | "pinned_items",
    item: ShortcutItem,
    idx: number,
    total: number,
  ): TemplateResult => {
    let displayTitle = item.label;
    let metaLine = "";
    let iconSlug = item.icon;
    if (item.kind === "route") {
      const spec = routeSpecMap.get(item.target);
      if (!displayTitle) {
        displayTitle = spec?.label || item.target;
      }
      metaLine = spec ? `${spec.group} • ${spec.label}` : item.target;
      if (!iconSlug) {
        iconSlug = ROUTE_PREVIEW_ICONS[item.target] || "mdi:apps";
      }
    } else {
      const ent = shortcutEntityMap.get(item.target);
      const dom = item.target.split(".", 1)[0] || "";
      const actLbl = shortcutActionLabel(dom, item.action);
      if (!displayTitle) {
        displayTitle = ent?.name || item.target;
      }
      metaLine = `${actLbl} • ${item.confirm ? "Confirm" : "1-Tap"} • ${item.target}`;
      if (!iconSlug) {
        iconSlug = ent?.icon || "mdi:flash";
      }
    }
    return html`<div class="shortcut-item-row">
      <span class="shortcut-icon-badge" aria-hidden="true">
        <ha-icon .icon=${iconSlug}></ha-icon>
      </span>
      <div class="shortcut-item-info">
        <span class="shortcut-item-title">${displayTitle}</span>
        <span class="shortcut-item-meta">${metaLine}</span>
      </div>
      ${idx > 0
        ? html`<button
            type="button"
            aria-label=${`Move ${displayTitle} up`}
            @click=${() => store.moveShortcutItem(listKey, idx, -1)}
            class="btn-icon"
          >
            ↑
          </button>`
        : nothing}
      ${idx < total - 1
        ? html`<button
            type="button"
            aria-label=${`Move ${displayTitle} down`}
            @click=${() => store.moveShortcutItem(listKey, idx, 1)}
            class="btn-icon"
          >
            ↓
          </button>`
        : nothing}
      <button
        type="button"
        aria-label=${`Edit ${displayTitle}`}
        @click=${() => store.openShortcutModal(listKey, idx)}
        class="btn btn-secondary btn-compact"
      >
        Edit
      </button>
      ${renderTrashIconButton(`Remove ${displayTitle}`, () =>
        store.removeShortcutItem(listKey, idx),
      )}
    </div>`;
  };

  const pinnedPages: Array<{ pageNum: number; startIdx: number; items: ShortcutItem[] }> = [];
  for (let i = 0; i < pinnedItems.length; i += 6) {
    pinnedPages.push({
      pageNum: Math.floor(i / 6) + 1,
      startIdx: i,
      items: pinnedItems.slice(i, i + 6),
    });
  }

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
                    id: "dock-shortcuts-row",
                    label: "App Dock",
                    description:
                      "Configure apps, subpages, and Home Assistant entity actions in the Home Dock. Pinned hides automatically when Pinned App is empty, and Settings is always shown last.",
                    stacked: true,
                    control: html`<div
                      id="dock-shortcuts-container"
                      class="stack"
                      role="group"
                      aria-label="App Dock shortcuts"
                    >
                      ${dockItems.map((item, idx) =>
                        renderShortcutRow("dock_items", item, idx, dockItems.length),
                      )}
                      <div class="shortcut-toolbar">
                        <button
                          type="button"
                          id="btn-add-dock-item"
                          ?disabled=${dockItems.length >= MAX_DOCK_ITEMS}
                          @click=${() => store.openShortcutModal("dock_items", null)}
                          class="btn btn-secondary"
                        >
                          Add Dock Item
                        </button>
                        <button
                          type="button"
                          id="btn-reset-dock-items"
                          @click=${() => store.resetDockItemsToDefault()}
                          class="btn btn-text"
                        >
                          Reset Default Dock
                        </button>
                      </div>
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
          body: html`${renderSettingsRow({
              id: "time-local-clock-label",
              label: "Local Clock Label",
              forId: "cfg-local_clock_label",
              description: "Optional custom label shown above local time on the Clock tab.",
              control: html`<input
                type="text"
                id="cfg-local_clock_label"
                maxlength="32"
                enterkeyhint="done"
                placeholder="Optional label…"
                .value=${localClockLabelValue}
                @input=${(ev: Event) => {
                  const cleaned = sanitizeClockLabel((ev.currentTarget as HTMLInputElement).value);
                  store.stageDeviceSetting(
                    "local_clock_label",
                    cleaned,
                    "cfg-local_clock_label",
                    TEXT_INPUT_DEBOUNCE_MS,
                  );
                }}
                @change=${(ev: Event) => {
                  const el = ev.currentTarget as HTMLInputElement;
                  const cleaned = sanitizeClockLabel(el.value);
                  el.value = cleaned;
                  store.stageDeviceSetting("local_clock_label", cleaned, "cfg-local_clock_label");
                }}
                @keydown=${(ev: KeyboardEvent) => {
                  if (!isImeSafeEnter(ev)) return;
                  ev.preventDefault();
                  const el = ev.currentTarget as HTMLInputElement;
                  const cleaned = sanitizeClockLabel(el.value);
                  el.value = cleaned;
                  store.stageDeviceSetting("local_clock_label", cleaned, "cfg-local_clock_label");
                  void store.flushAllPendingSettings();
                }}
              />`,
            })}
            ${renderSwitchRow({
              id: "cfg-show_utc_clock",
              label: "Show UTC Clock",
              description: "Pin a live 24-hour UTC reference row to this Device's Clock tab.",
              checked: showUtcClock,
              onChange: (checked) => {
                store.stageDeviceSetting("show_utc_clock", checked, "cfg-show_utc_clock");
              },
            })}
            ${renderSettingsRow({
              id: "time-world-clocks",
              label: "World Clocks",
              description:
                "Configure up to 4 custom-labeled time zones (UTC-12:00 to UTC+14:00) shown on this Device's Clock tab.",
              stacked: true,
              control: html`<div class="stack">
                ${enabledWorldClocks.length
                  ? html`<div
                      id="world-clocks-list"
                      class="stack"
                      role="group"
                      aria-label="Configured World Clocks"
                    >
                      ${enabledWorldClocks.map((entry, idx) => {
                        const lblId = `cfg-world_clock_${idx + 1}_label`;
                        const zoneId = `cfg-world_clock_${idx + 1}_zone`;
                        return html`<div class="list-row">
                          <div class="list-row-main">
                            <div class="stacked-field">
                              <label for=${lblId}>World Clock ${idx + 1} City Label</label>
                              <input
                                type="text"
                                id=${lblId}
                                maxlength="32"
                                enterkeyhint="done"
                                placeholder="Enter city or label…"
                                .value=${entry.label}
                                @input=${(ev: Event) => {
                                  const cleaned = sanitizeClockLabel(
                                    (ev.currentTarget as HTMLInputElement).value,
                                  );
                                  if (cleaned) {
                                    updateWorldClockItem(
                                      idx,
                                      { label: cleaned },
                                      lblId,
                                      TEXT_INPUT_DEBOUNCE_MS,
                                    );
                                  }
                                }}
                                @change=${(ev: Event) => {
                                  const el = ev.currentTarget as HTMLInputElement;
                                  const cleaned = sanitizeClockLabel(el.value);
                                  if (!cleaned) {
                                    el.value = entry.label;
                                    store.showToast("City label cannot be empty", true);
                                    return;
                                  }
                                  el.value = cleaned;
                                  updateWorldClockItem(idx, { label: cleaned }, lblId);
                                }}
                                @keydown=${(ev: KeyboardEvent) => {
                                  if (!isImeSafeEnter(ev)) return;
                                  ev.preventDefault();
                                  const el = ev.currentTarget as HTMLInputElement;
                                  const cleaned = sanitizeClockLabel(el.value);
                                  if (!cleaned) {
                                    el.value = entry.label;
                                    store.showToast("City label cannot be empty", true);
                                    return;
                                  }
                                  el.value = cleaned;
                                  updateWorldClockItem(idx, { label: cleaned }, lblId);
                                  void store.flushAllPendingSettings();
                                }}
                              />
                            </div>
                            <div class="stacked-field">
                              <label for=${zoneId}>World Clock ${idx + 1} Time Zone</label>
                              <select
                                id=${zoneId}
                                .value=${entry.iana}
                                @change=${(ev: Event) =>
                                  updateWorldClockItem(
                                    idx,
                                    { iana: (ev.currentTarget as HTMLSelectElement).value },
                                    zoneId,
                                  )}
                              >
                                ${renderWorldClockZoneOptions(entry.iana)}
                              </select>
                            </div>
                          </div>
                          ${idx > 0
                            ? html`<button
                                type="button"
                                aria-label=${`Move ${entry.label} up`}
                                @click=${() => moveWorldClock(idx, -1)}
                                class="btn-icon"
                              >
                                ↑
                              </button>`
                            : nothing}
                          ${idx < enabledWorldClocks.length - 1
                            ? html`<button
                                type="button"
                                aria-label=${`Move ${entry.label} down`}
                                @click=${() => moveWorldClock(idx, 1)}
                                class="btn-icon"
                              >
                                ↓
                              </button>`
                            : nothing}
                          ${renderTrashIconButton(
                            `Remove ${entry.label} (${entry.iana})`,
                            () => removeWorldClock(idx),
                          )}
                        </div>`;
                      })}
                    </div>`
                  : nothing}
                <div class="list-row">
                  <div class="list-row-main">
                    <div class="stacked-field">
                      <label for="cfg-world_clock_new_label">New City Label</label>
                      <input
                        type="text"
                        id="cfg-world_clock_new_label"
                        maxlength="32"
                        enterkeyhint="done"
                        placeholder="Enter city or label…"
                        ?disabled=${atWorldClockLimit}
                        .value=${store.worldClockNewLabel}
                        @input=${(ev: Event) => {
                          store.worldClockNewLabel = (ev.currentTarget as HTMLInputElement).value;
                          store.host.requestUpdate();
                        }}
                        @keydown=${(ev: KeyboardEvent) => {
                          if (!isImeSafeEnter(ev)) return;
                          ev.preventDefault();
                          onAddWorldClock();
                        }}
                      />
                    </div>
                    <div class="stacked-field">
                      <label for="cfg-world_clocks_add">Add Time Zone</label>
                      <select
                        id="cfg-world_clocks_add"
                        ?disabled=${atWorldClockLimit}
                        .value=${store.worldClockNewZone}
                        @change=${(ev: Event) => {
                          store.worldClockNewZone = (ev.currentTarget as HTMLSelectElement).value;
                          store.host.requestUpdate();
                        }}
                      >
                        <option value="" ?selected=${!store.worldClockNewZone}>
                          ${atWorldClockLimit
                            ? "Maximum 4 World Clocks added"
                            : "Select a time zone (UTC-12 to UTC+14)…"}
                        </option>
                        ${atWorldClockLimit
                          ? nothing
                          : renderWorldClockZoneOptions(store.worldClockNewZone)}
                      </select>
                    </div>
                  </div>
                  <button
                    type="button"
                    id="btn-world_clock_add"
                    ?disabled=${atWorldClockLimit}
                    @click=${() => onAddWorldClock()}
                    class="btn btn-primary"
                  >
                    Add
                  </button>
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
          id: "card-pinned-app",
          heading: html`<h3 class="card-title">Pinned App</h3>`,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
            id: "pinned-shortcuts-row",
            label: "Pinned Shortcuts",
            description:
              "Assign Home Assistant entity quick actions or deep-link any Latter app or subpage (6 buttons per page, swipable vertically).",
            stacked: true,
            control: html`<div
              id="pinned-shortcuts-container"
              class="stack"
              role="group"
              aria-label="Pinned App shortcuts"
            >
              ${pinnedPages.length > 0
                ? pinnedPages.map(
                    (pg) => html`<div class="shortcut-page-group">
                      <div class="shortcut-page-header">
                        <span>Page ${pg.pageNum}</span>
                        <span>${pg.items.length} of 6 Slots</span>
                      </div>
                      ${pg.items.map((item, localIdx) =>
                        renderShortcutRow(
                          "pinned_items",
                          item,
                          pg.startIdx + localIdx,
                          pinnedItems.length,
                        ),
                      )}
                    </div>`,
                  )
                : html`<p class="row-description">
                    No pinned items configured yet. The Pinned icon stays hidden on the Home Dock until you add at least one item.
                  </p>`}
              <div class="shortcut-toolbar">
                <button
                  type="button"
                  id="btn-add-pinned-item"
                  ?disabled=${pinnedItems.length >= MAX_PINNED_ITEMS}
                  @click=${() => store.openShortcutModal("pinned_items", null)}
                  class="btn btn-primary"
                >
                  Add Pinned Item
                </button>
              </div>
            </div>`,
          })}`,
        })}

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
