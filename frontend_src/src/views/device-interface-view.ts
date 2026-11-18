/**
 * Device Interface View (`interface`, D-026 / D-035 / D-047 / D-053):
 * Two balanced cards for top-level navigation and App Dock management:
 * - Column 1: Home Screen (Enable Home Screen, Start Screen with Single-App Configure safeguard,
 *   Home Time Tap, Return to Home Timeout, Show the Activity Card & Activity Card Sources).
 * - Column 2: App Dock (Active on Dock with Protected Native Apps + Custom Shortcuts + locked Settings,
 *   Add Custom Shortcut / Reset Default Dock, and Hidden From Dock) — or Single-App Mode Active when locked.
 */

import {
  renderCard,
  renderSelectRow,
  renderSettingsRow,
  renderSwitchRow,
  renderTrashIconButton,
} from "../components/controls.js";
import {
  ACTIVITY_SOURCES_CATALOG,
  DEFAULT_AREA_CATEGORIES_TOKENS,
  DEFAULT_GAMES_ITEMS_TOKENS,
  DEFAULT_HOME_CATEGORIES_TOKENS,
  DEFAULT_TOOLS_ITEMS_TOKENS,
  HOME_CLOCK_TAP_OPTIONS,
  HOME_DATE_TAP_OPTIONS,
  MAX_DOCK_ITEMS,
  NATIVE_DOCK_APP_TOKENS,
  NATIVE_DOCK_CONFIG_APP_MAP,
  RETURN_TO_HOME_TIMEOUT_OPTIONS,
  SHORTCUT_ROUTES_CATALOG,
  START_SCREEN_CONFIG_APP_MAP,
  START_SCREEN_OPTIONS,
} from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import { ROUTE_PREVIEW_ICONS, shortcutActionLabel } from "../mdi-catalog.js";
import type { StudioStore } from "../state/store.js";
import type { DeviceCapabilities, ShortcutItem } from "../types.js";

const IFACE_UTC_ZONES = new Set([
  "UTC",
  "Etc/UTC",
  "GMT",
  "Etc/GMT",
  "Etc/GMT+0",
  "Etc/GMT-0",
  "Etc/GMT0",
]);
const IFACE_IANA_PATTERN = /^[A-Za-z0-9_+-]+(?:\/[A-Za-z0-9_+-]+)+$/;

function countConfiguredWorldClocks(raw: unknown): number {
  let count = 0;
  const seen = new Set<string>();
  for (const part of String(raw ?? "").split(";")) {
    const rec = part.trim();
    if (!rec) continue;
    const pipeIdx = rec.indexOf("|");
    if (pipeIdx < 0) continue;
    const rawLbl = rec.slice(0, pipeIdx).trim();
    const iana = rec.slice(pipeIdx + 1).trim();
    if (!iana || IFACE_UTC_ZONES.has(iana) || !IFACE_IANA_PATTERN.test(iana)) {
      continue;
    }
    const key = `${rawLbl.toLowerCase()}|${iana}`;
    if (seen.has(key)) continue;
    seen.add(key);
    count += 1;
    if (count >= 4) break;
  }
  return count;
}

function isNativeDockRouteItem(item: ShortcutItem): boolean {
  return (
    item.kind === "route" &&
    NATIVE_DOCK_APP_TOKENS.includes(item.target) &&
    !item.label &&
    !item.icon
  );
}

function ifaceIsToolSupported(token: string, caps: DeviceCapabilities): boolean {
  if (token === "stopwatch" && caps.is_round === false) return false;
  if (token === "level" && caps.has_imu === false) return false;
  return true;
}

export function renderDeviceInterfaceView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const caps = data?.capabilities || {};
  const remoteGroups = data?.system_config?.remote_groups || [];

  const homeScreenEnabledPref =
    typeof store.getPref === "function" ? store.getPref("home_screen_enabled") : undefined;
  const homeScreenEnabled = homeScreenEnabledPref
    ? Boolean(homeScreenEnabledPref.value)
    : cfg.home_screen_enabled !== false;

  const startScreenPref =
    typeof store.getPref === "function" ? store.getPref("start_screen") : undefined;
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
  const startScreenConfigApp = !homeScreenEnabled
    ? START_SCREEN_CONFIG_APP_MAP[startScreenValue] || null
    : null;

  const homeClockTapPref =
    typeof store.getPref === "function" ? store.getPref("home_clock_tap_action") : undefined;
  const homeClockTapOptions = (
    homeClockTapPref?.options && homeClockTapPref.options.length > 0
      ? homeClockTapPref.options
      : HOME_CLOCK_TAP_OPTIONS
  ).map((opt) => ({ value: opt, label: opt }));
  const homeClockTapValue = String(
    homeClockTapPref?.value ?? cfg.home_clock_tap_action ?? "Time App",
  );

  const homeDateTapPref =
    typeof store.getPref === "function" ? store.getPref("home_date_tap_action") : undefined;
  const homeDateTapOptions = (
    homeDateTapPref?.options && homeDateTapPref.options.length > 0
      ? homeDateTapPref.options
      : HOME_DATE_TAP_OPTIONS
  ).map((opt) => ({ value: opt, label: opt }));
  const homeDateTapValue = String(
    homeDateTapPref?.value ?? cfg.home_date_tap_action ?? "Day View",
  );

  const returnTimeoutPref =
    typeof store.getPref === "function" ? store.getPref("return_to_home_timeout") : undefined;
  const rawReturnTimeoutOptions = (
    returnTimeoutPref?.options && returnTimeoutPref.options.length > 0
      ? returnTimeoutPref.options
      : RETURN_TO_HOME_TIMEOUT_OPTIONS
  ).map((opt) => ({ value: opt, label: opt }));
  const returnTimeoutValue = String(
    returnTimeoutPref?.value ?? cfg.return_to_home_timeout ?? "2 min",
  );

  const activityCardOn = cfg.activity_card !== false;
  const enabledSources = new Set(
    typeof store.getEnabledActivitySources === "function"
      ? store.getEnabledActivitySources()
      : ACTIVITY_SOURCES_CATALOG.map((c) => c.token),
  );
  const dockItems =
    typeof store.getDockItems === "function" ? store.getDockItems() : [];
  const pinnedItems =
    typeof store.getPinnedItems === "function" ? store.getPinnedItems() : [];
  const enabledHomeCats =
    typeof store.getEnabledHomeCategories === "function"
      ? store.getEnabledHomeCategories()
      : [...DEFAULT_HOME_CATEGORIES_TOKENS];
  const enabledAreaCats =
    typeof store.getEnabledAreaCategories === "function"
      ? store.getEnabledAreaCategories()
      : [...DEFAULT_AREA_CATEGORIES_TOKENS];
  const enabledTools =
    typeof store.getEnabledToolsItems === "function"
      ? store.getEnabledToolsItems()
      : [...DEFAULT_TOOLS_ITEMS_TOKENS];
  const visibleToolsCount = enabledTools.filter((tok) => ifaceIsToolSupported(tok, caps)).length;
  const enabledGames =
    typeof store.getEnabledGamesItems === "function"
      ? store.getEnabledGamesItems()
      : [...DEFAULT_GAMES_ITEMS_TOKENS];

  const curDevEntry = (data?.system_devices || []).find(
    (d) => d.subentry_id === store.activeSubentryId,
  );
  const curRemoteMode =
    String(cfg.device_remote_group || curDevEntry?.device_remote_group || "area_auto").trim() ||
    "area_auto";

  const albumSortPref =
    typeof store.getPref === "function" ? store.getPref("album_sort_order") : undefined;
  const albumSortVal = String(albumSortPref?.value ?? cfg.album_sort_order ?? "Alphabetical");
  const artistSortPref =
    typeof store.getPref === "function" ? store.getPref("artist_album_sort_order") : undefined;
  const artistSortVal = String(
    artistSortPref?.value ?? cfg.artist_album_sort_order ?? "Oldest on Top",
  );

  const showUtcClockPref =
    typeof store.getPref === "function" ? store.getPref("show_utc_clock") : undefined;
  const showUtcClock = showUtcClockPref
    ? Boolean(showUtcClockPref.value)
    : Boolean(cfg.show_utc_clock);
  const worldClocksPref =
    typeof store.getPref === "function" ? store.getPref("world_clocks") : undefined;
  const worldClockCount = countConfiguredWorldClocks(
    worldClocksPref?.value ?? cfg.world_clocks ?? "",
  );

  const clockFacePref =
    typeof store.getPref === "function" ? store.getPref("clock_face") : undefined;
  const clockFaceVal = String(clockFacePref?.value ?? cfg.clock_face ?? "Minimal Digital");
  const timeFormatPref =
    typeof store.getPref === "function" ? store.getPref("time_format") : undefined;
  const rawTimeFormat = String(timeFormatPref?.value ?? cfg.time_format ?? "12-Hour (AM/PM)");
  const shortTimeFormat = rawTimeFormat.startsWith("24") ? "24-Hour" : "12-Hour";

  const calLookaheadPref =
    typeof store.getPref === "function" ? store.getPref("calendar_lookahead_days") : undefined;
  const rawLookahead = Number(calLookaheadPref?.value ?? cfg.calendar_lookahead_days ?? 30);
  const calLookaheadDays =
    rawLookahead <= 10 ? 7 : rawLookahead <= 21 ? 14 : rawLookahead <= 45 ? 30 : 60;
  const calWeekStartPref =
    typeof store.getPref === "function" ? store.getPref("calendar_week_start") : undefined;
  const calWeekStart =
    String(calWeekStartPref?.value ?? cfg.calendar_week_start ?? "Sunday") === "Monday"
      ? "Monday"
      : "Sunday";

  const describeNativeDockApp = (routeToken: string): string => {
    switch (routeToken) {
      case "app:pinned": {
        if (pinnedItems.length === 0) {
          return "Empty — auto-hidden on Dock";
        }
        const pages = Math.ceil(pinnedItems.length / 6);
        return `${pinnedItems.length} shortcut${pinnedItems.length === 1 ? "" : "s"} • ${pages} page${pages === 1 ? "" : "s"}`;
      }
      case "app:music":
        return `Albums: ${albumSortVal} • Artists: ${artistSortVal}`;
      case "app:home_hub":
        return `${enabledHomeCats.length} ${enabledHomeCats.length === 1 ? "category" : "categories"} enabled`;
      case "app:area":
        return `${enabledAreaCats.length} ${enabledAreaCats.length === 1 ? "category" : "categories"} enabled`;
      case "app:remote": {
        if (curRemoteMode === "all") return "All System remotes";
        if (curRemoteMode.startsWith("group:")) {
          const gid = curRemoteMode.slice(6);
          return remoteGroups.find((g) => g.id === gid)?.name || gid;
        }
        return "Follow the active Area";
      }
      case "app:weather":
        return "Current, Forecast, Sun & Moon";
      case "app:time":
        if (showUtcClock && worldClockCount > 0) {
          return `UTC + ${worldClockCount} World Clock${worldClockCount === 1 ? "" : "s"}`;
        }
        if (worldClockCount > 0) {
          return `${worldClockCount} World Clock${worldClockCount === 1 ? "" : "s"}`;
        }
        return showUtcClock ? "Local time + UTC" : "Local time";
      case "app:clock":
        return `${clockFaceVal} • ${shortTimeFormat}`;
      case "app:calendar":
        return `${calLookaheadDays}-day lookahead • Starts ${calWeekStart}`;
      case "app:tools":
        return `${visibleToolsCount} tool${visibleToolsCount === 1 ? "" : "s"} enabled`;
      case "app:games":
        return `${enabledGames.length} game${enabledGames.length === 1 ? "" : "s"} enabled`;
      default:
        return routeToken;
    }
  };

  const shortcutEntityMap = new Map(
    (data?.catalog?.shortcut_entities || []).map((e) => [e.id, e]),
  );
  const routeSpecMap = new Map(
    SHORTCUT_ROUTES_CATALOG.map((r) => [r.token, r]),
  );

  const activeNativeSet = new Set(
    dockItems.filter((it) => isNativeDockRouteItem(it)).map((it) => it.target),
  );
  const hiddenNativeApps = NATIVE_DOCK_APP_TOKENS.filter((tok) => !activeNativeSet.has(tok));

  const renderActiveDockRow = (
    item: ShortcutItem,
    idx: number,
    total: number,
  ): TemplateResult => {
    if (isNativeDockRouteItem(item)) {
      const spec = routeSpecMap.get(item.target);
      const displayTitle = spec?.label || item.target;
      const iconSlug = ROUTE_PREVIEW_ICONS[item.target] || "mdi:apps";
      const configApp = NATIVE_DOCK_CONFIG_APP_MAP[item.target];
      return html`<div class="shortcut-item-row">
        <span class="shortcut-icon-badge" aria-hidden="true">
          <ha-icon .icon=${iconSlug}></ha-icon>
        </span>
        <div class="shortcut-item-info">
          <span class="shortcut-item-title">${displayTitle}</span>
          <span class="shortcut-item-meta">${describeNativeDockApp(item.target)}</span>
        </div>
        ${idx > 0
          ? html`<button
              type="button"
              aria-label=${`Move ${displayTitle} up`}
              @click=${() => store.moveShortcutItem("dock_items", idx, -1)}
              class="btn-icon"
            >
              ↑
            </button>`
          : nothing}
        ${idx < total - 1
          ? html`<button
              type="button"
              aria-label=${`Move ${displayTitle} down`}
              @click=${() => store.moveShortcutItem("dock_items", idx, 1)}
              class="btn-icon"
            >
              ↓
            </button>`
          : nothing}
        ${configApp
          ? html`<button
              type="button"
              aria-label=${`Configure ${displayTitle}`}
              @click=${() => store.openAppConfigModal(configApp)}
              class="btn btn-secondary btn-compact"
            >
              Configure
            </button>`
          : nothing}
        <input
          type="checkbox"
          role="switch"
          aria-label=${`Show ${displayTitle} on App Dock`}
          .checked=${true}
          @change=${(ev: Event) =>
            store.toggleNativeDockApp(item.target, (ev.currentTarget as HTMLInputElement).checked)}
          class="switch"
        />
      </div>`;
    }

    let displayTitle = item.label;
    let metaLine = "";
    let iconSlug = item.icon;
    if (item.kind === "route") {
      const spec = routeSpecMap.get(item.target);
      if (!displayTitle) {
        displayTitle = spec?.label || item.target;
      }
      metaLine = `Custom • ${spec ? `${spec.group} • ${spec.label}` : item.target}`;
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
      metaLine = `Custom • ${actLbl} • ${item.confirm ? "Confirm" : "1-Tap"} • ${item.target}`;
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
            @click=${() => store.moveShortcutItem("dock_items", idx, -1)}
            class="btn-icon"
          >
            ↑
          </button>`
        : nothing}
      ${idx < total - 1
        ? html`<button
            type="button"
            aria-label=${`Move ${displayTitle} down`}
            @click=${() => store.moveShortcutItem("dock_items", idx, 1)}
            class="btn-icon"
          >
            ↓
          </button>`
        : nothing}
      <button
        type="button"
        aria-label=${`Edit ${displayTitle}`}
        @click=${() => store.openShortcutModal("dock_items", idx)}
        class="btn btn-secondary btn-compact"
      >
        Edit
      </button>
      ${renderTrashIconButton(`Remove ${displayTitle}`, () =>
        store.removeShortcutItem("dock_items", idx),
      )}
    </div>`;
  };

  return html`<section id="view-interface">
    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-home-screen",
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
            ${renderSettingsRow({
              label: "Start Screen",
              forId: "cfg-start_screen",
              description: homeScreenEnabled
                ? "Choose the screen shown on startup. Swipe up from the bottom to return to Home."
                : "Single-app screen shown at all times while the Home screen is disabled.",
              control: html`<select
                  id="cfg-start_screen"
                  .value=${startScreenValue}
                  @change=${(ev: Event) => {
                    store.stageDeviceSetting(
                      "start_screen",
                      (ev.currentTarget as HTMLSelectElement).value,
                      "cfg-start_screen",
                    );
                  }}
                >
                  ${visibleStartOptions.map(
                    (o) =>
                      html`<option value=${o.value} ?selected=${o.value === startScreenValue}>
                        ${o.label}
                      </option>`,
                  )}
                </select>
                ${startScreenConfigApp
                  ? html`<button
                      type="button"
                      id="btn-configure-start-screen"
                      @click=${() => store.openAppConfigModal(startScreenConfigApp)}
                      class="btn btn-secondary btn-compact"
                    >
                      Configure
                    </button>`
                  : nothing}`,
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
                    id: "cfg-home_date_tap_action",
                    label: "Home Date Tap",
                    description:
                      "Choose whether tapping the date readout on Home opens Day View or Overview in the Calendar app.",
                    value: homeDateTapValue,
                    rawOptions: homeDateTapOptions,
                    onChange: (val) => {
                      store.stageDeviceSetting(
                        "home_date_tap_action",
                        val,
                        "cfg-home_date_tap_action",
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
      </div>

      <div class="column">
        ${homeScreenEnabled
          ? renderCard({
              id: "card-app-dock",
              heading: html`<h3 class="card-title">App Dock</h3>`,
              contentClass: "stack",
              body: html`<p class="row-description">
                  Toggle, reorder, and configure apps on the Home Dock, or add custom subpage and Home Assistant entity shortcuts. Pinned hides automatically when empty.
                </p>
                <div
                  id="dock-shortcuts-container"
                  class="stack"
                  role="group"
                  aria-label="Active on App Dock"
                >
                  ${dockItems.map((item, idx) =>
                    renderActiveDockRow(item, idx, dockItems.length),
                  )}
                  <div class="shortcut-item-row shortcut-item-locked">
                    <span class="shortcut-icon-badge" aria-hidden="true">
                      <ha-icon .icon=${"mdi:cog"}></ha-icon>
                    </span>
                    <div class="shortcut-item-info">
                      <span class="shortcut-item-title">Settings</span>
                      <span class="shortcut-item-meta">Always shown last on the App Dock</span>
                    </div>
                  </div>
                </div>
                <div class="shortcut-toolbar">
                  <button
                    type="button"
                    id="btn-add-dock-item"
                    ?disabled=${dockItems.length >= MAX_DOCK_ITEMS}
                    @click=${() => store.openShortcutModal("dock_items", null)}
                    class="btn btn-secondary"
                  >
                    Add Custom Shortcut
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
                ${hiddenNativeApps.length > 0
                  ? html`<div
                      id="dock-hidden-native-apps"
                      class="stack"
                      role="group"
                      aria-label="Hidden From Dock"
                    >
                      <div class="subsection-title">Hidden From Dock</div>
                      ${hiddenNativeApps.map((tok) => {
                        const spec = routeSpecMap.get(tok);
                        const displayTitle = spec?.label || tok;
                        const iconSlug = ROUTE_PREVIEW_ICONS[tok] || "mdi:apps";
                        const configApp = NATIVE_DOCK_CONFIG_APP_MAP[tok];
                        return html`<div class="shortcut-item-row shortcut-item-hidden">
                          <span class="shortcut-icon-badge" aria-hidden="true">
                            <ha-icon .icon=${iconSlug}></ha-icon>
                          </span>
                          <div class="shortcut-item-info">
                            <span class="shortcut-item-title">${displayTitle}</span>
                            <span class="shortcut-item-meta">${describeNativeDockApp(tok)}</span>
                          </div>
                          ${configApp
                            ? html`<button
                                type="button"
                                aria-label=${`Configure ${displayTitle}`}
                                @click=${() => store.openAppConfigModal(configApp)}
                                class="btn btn-secondary btn-compact"
                              >
                                Configure
                              </button>`
                            : nothing}
                          <input
                            type="checkbox"
                            role="switch"
                            aria-label=${`Show ${displayTitle} on App Dock`}
                            ?disabled=${dockItems.length >= MAX_DOCK_ITEMS}
                            .checked=${false}
                            @change=${(ev: Event) =>
                              store.toggleNativeDockApp(
                                tok,
                                (ev.currentTarget as HTMLInputElement).checked,
                              )}
                            class="switch"
                          />
                        </div>`;
                      })}
                    </div>`
                  : nothing}`,
            })
          : renderCard({
              id: "card-single-app-mode",
              heading: html`<h3 class="card-title">Single-App Mode Active</h3>`,
              contentClass: "stack",
              body: html`<p class="row-description">
                  The Home Screen and App Dock are disabled while this Device is locked to ${startScreenValue}. Turn on Enable Home Screen to restore multi-app navigation and the App Dock.
                </p>
                ${startScreenConfigApp
                  ? html`<div class="shortcut-toolbar">
                      <button
                        type="button"
                        id="btn-configure-locked-app"
                        @click=${() => store.openAppConfigModal(startScreenConfigApp)}
                        class="btn btn-secondary"
                      >
                        ${`Configure ${startScreenValue}`}
                      </button>
                    </div>`
                  : nothing}`,
            })}
      </div>
    </div>
  </section>`;
}
