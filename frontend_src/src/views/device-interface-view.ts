/**
 * Device Interface View (`interface`, `D-026`, `D-035`, `D-047`, `D-053`, `D-064`, `D-069`):
 * - Column 1: Home screen (`home_screen_enabled`, `start_screen` + inline `Configure`, `time_format`,
 *   `home_clock_tap_action` + conditional `clock_face`, `home_date_tap_action`, `return_to_home_timeout`,
 *   `wake_greeting`, `weather_background` + conditional `home_sun`/`home_moon` pills, `activity_card`,
 *   & sortable `renderPillList` for `activity_sources`).
 * - Column 2: App Dock (`renderSortableList` with `≡` drag handle + focus-preserving `↑`/`↓` and
 *   non-truncating `.dock-row` layout, `requestResetDockItems` confirmation, and Hidden from dock) —
 *   omitted cleanly when `home_screen_enabled === false` (`D-069`).
 */

import {
  renderCard,
  renderDeviceOfflineBanner,
  renderPillList,
  renderSelectRow,
  renderSettingsRow,
  renderSortableList,
  renderSwitchRow,
  renderTrashIconButton,
} from "../components/controls.js";
import {
  ACTIVITY_SOURCES_CATALOG,
  GAMES_ITEMS_CATALOG,
  HOME_CLOCK_TAP_OPTIONS,
  HOME_DATE_TAP_OPTIONS,
  MAX_DOCK_ITEMS,
  NATIVE_DOCK_APP_TOKENS,
  NATIVE_DOCK_CONFIG_APP_MAP,
  RETURN_TO_HOME_TIMEOUT_OPTIONS,
  SHORTCUT_ROUTES_CATALOG,
  START_SCREEN_CONFIG_APP_MAP,
  START_SCREEN_OPTIONS,
  TOOLS_ITEMS_CATALOG,
} from "../constants.js";
import type { StudioTranslationKey } from "../i18n/index.js";
import { html, live, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import { ROUTE_PREVIEW_ICONS, shortcutActionLabel } from "../mdi-catalog.js";
import {
  isCatalogItemSupported,
  isProtectedNativeDockItem,
  shortcutBadgeClass,
  type StudioStore,
} from "../state/store.js";
import type { ShortcutItem } from "../types.js";
import {
  defaultLocaleTimeFormat,
  fmtNumber,
  hassFirstWeekday,
} from "../utils/format.js";

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
  return isProtectedNativeDockItem(item);
}

function activitySourceLabel(store: StudioStore, token: string, fallback: string): string {
  const key = `dev_interface.activity_src_${token}` as StudioTranslationKey;
  const translated = store.t(key);
  return translated === key ? fallback : translated;
}

export function renderDeviceInterfaceView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const caps = data?.capabilities || {};
  const remoteGroups = data?.system_config?.remote_groups || [];

  const homeScreenEnabledPref = store.entity.getPref("home_screen_enabled");
  const homeScreenEnabled = homeScreenEnabledPref
    ? Boolean(homeScreenEnabledPref.value)
    : cfg.home_screen_enabled !== false;

  const startScreenPref = store.entity.getPref("start_screen");
  const rawStartOptions =
    startScreenPref?.options && startScreenPref.options.length > 0
      ? startScreenPref.options
      : START_SCREEN_OPTIONS;
  const visibleStartOptions = (
    homeScreenEnabled ? rawStartOptions : rawStartOptions.filter((opt) => opt !== "Home")
  ).map((opt) => ({ value: opt, label: store.tPrefOption("start_screen", opt) }));
  const rawStartValue = String(
    startScreenPref?.value ?? cfg.start_screen ?? (homeScreenEnabled ? "Home" : "Time App"),
  );
  const startScreenValue =
    !homeScreenEnabled && rawStartValue === "Home" ? "Time App" : rawStartValue;
  const startScreenConfigApp = !homeScreenEnabled
    ? START_SCREEN_CONFIG_APP_MAP[startScreenValue] || null
    : null;

  const homeClockTapPref = store.entity.getPref("home_clock_tap_action");
  const homeClockTapOptions = (
    homeClockTapPref?.options && homeClockTapPref.options.length > 0
      ? homeClockTapPref.options
      : HOME_CLOCK_TAP_OPTIONS
  ).map((opt) => ({
    value: opt,
    label: store.tPrefOption("home_clock_tap_action", opt),
  }));
  const homeClockTapValue = String(
    homeClockTapPref?.value ?? cfg.home_clock_tap_action ?? "Time App",
  );

  const homeDateTapPref = store.entity.getPref("home_date_tap_action");
  const homeDateTapOptions = (
    homeDateTapPref?.options && homeDateTapPref.options.length > 0
      ? homeDateTapPref.options
      : HOME_DATE_TAP_OPTIONS
  ).map((opt) => ({
    value: opt,
    label: store.tPrefOption("home_date_tap_action", opt),
  }));
  const homeDateTapValue = String(
    homeDateTapPref?.value ?? cfg.home_date_tap_action ?? "Overview",
  );

  const returnTimeoutPref = store.entity.getPref("return_to_home_timeout");
  const rawReturnTimeoutOptions = (
    returnTimeoutPref?.options && returnTimeoutPref.options.length > 0
      ? returnTimeoutPref.options
      : RETURN_TO_HOME_TIMEOUT_OPTIONS
  ).map((opt) => ({
    value: opt,
    label: store.tPrefOption("return_to_home_timeout", opt),
  }));
  const returnTimeoutValue = String(
    returnTimeoutPref?.value ?? cfg.return_to_home_timeout ?? "2 min",
  );

  const activityCardOn = cfg.activity_card !== false;
  const enabledSourceTokens = store.entity.getEnabledActivitySources();
  const enabledSourceSet = new Set(enabledSourceTokens);
  const activitySpecMap = new Map(ACTIVITY_SOURCES_CATALOG.map((c) => [c.token, c]));
  const activityPillItems = [
    ...enabledSourceTokens
      .map((tok) => activitySpecMap.get(tok))
      .filter((c): c is (typeof ACTIVITY_SOURCES_CATALOG)[number] =>
        Boolean(c && isCatalogItemSupported(c, caps)),
      )
      .map((c) => ({
        token: c.token,
        label: activitySourceLabel(store, c.token, c.label),
        enabled: true,
      })),
    ...ACTIVITY_SOURCES_CATALOG.filter(
      (c) => !enabledSourceSet.has(c.token) && isCatalogItemSupported(c, caps),
    ).map((c) => ({
      token: c.token,
      label: activitySourceLabel(store, c.token, c.label),
      enabled: false,
    })),
  ];

  const dockItems = store.entity.getDockItems();
  const pinnedItems = store.entity.getPinnedItems();
  const enabledHomeCats = store.entity.getEnabledHomeCategories();
  const enabledAreaCats = store.entity.getEnabledAreaCategories();
  const enabledTools = store.entity.getEnabledToolsItems();
  const toolSpecMap = new Map(TOOLS_ITEMS_CATALOG.map((t) => [t.token, t]));
  const visibleToolsCount = enabledTools.filter((tok) => {
    const spec = toolSpecMap.get(tok);
    return spec ? isCatalogItemSupported(spec, caps) : true;
  }).length;
  const enabledGames = store.entity.getEnabledGamesItems();
  const gameSpecMap = new Map(GAMES_ITEMS_CATALOG.map((g) => [g.token, g]));
  const visibleGamesCount = enabledGames.filter((tok) => {
    const spec = gameSpecMap.get(tok);
    return spec ? isCatalogItemSupported(spec, caps) : true;
  }).length;

  const curDevEntry = (data?.system_devices || []).find(
    (d) => d.subentry_id === store.activeSubentryId,
  );
  const curRemoteMode =
    String(cfg.device_remote_group || curDevEntry?.device_remote_group || "area_auto").trim() ||
    "area_auto";

  const albumArtPref = store.entity.getPref("album_art_style");
  const albumArtRaw = String(albumArtPref?.value ?? cfg.album_art_style ?? "Full Screen");
  const albumArtVal = store.tPrefOption("album_art_style", albumArtRaw);
  const albumSortPref = store.entity.getPref("album_sort_order");
  const albumSortRaw = String(albumSortPref?.value ?? cfg.album_sort_order ?? "Alphabetical");
  const albumSortVal = store.tPrefOption("album_sort_order", albumSortRaw);

  const showUtcClockPref = store.entity.getPref("show_utc_clock");
  const showUtcClock = showUtcClockPref
    ? Boolean(showUtcClockPref.value)
    : Boolean(cfg.show_utc_clock);
  const worldClocksPref = store.entity.getPref("world_clocks");
  const worldClockCount = countConfiguredWorldClocks(
    worldClocksPref?.value ?? cfg.world_clocks ?? "",
  );

  const clockFacePref = store.entity.getPref("clock_face");
  const clockFaceSpec = store.entity.getPrefSpec("clock_face");
  const rawClockFaceOpts =
    clockFacePref?.options && clockFacePref.options.length > 0
      ? clockFacePref.options
      : clockFaceSpec?.options || [];
  const filteredClockFaceOpts =
    caps.is_round === false
      ? rawClockFaceOpts.filter((opt) => opt !== "Modern Analog")
      : rawClockFaceOpts;
  const clockFaceRaw = String(clockFacePref?.value ?? cfg.clock_face ?? "Minimal Digital");
  const resolvedClockFaceValue =
    (filteredClockFaceOpts.length > 0 && !filteredClockFaceOpts.includes(clockFaceRaw)
      ? filteredClockFaceOpts[0]
      : undefined) ?? clockFaceRaw;
  const clockFaceOptions = filteredClockFaceOpts.map((opt) => ({
    value: opt,
    label: store.tPrefOption("clock_face", opt),
  }));
  const clockFaceVal = store.tPrefOption("clock_face", resolvedClockFaceValue);

  // Default unset `time_format` from `hass.locale?.time_format`
  const timeFormatPref = store.entity.getPref("time_format");
  const timeFormatSpec = store.entity.getPrefSpec("time_format");
  const rawTimeFormatOpts =
    timeFormatPref?.options && timeFormatPref.options.length > 0
      ? timeFormatPref.options
      : timeFormatSpec?.options || [];
  const rawTimeFormatVal = timeFormatPref?.value ?? cfg.time_format;
  const effectiveTimeFormat =
    rawTimeFormatVal !== undefined &&
    rawTimeFormatVal !== null &&
    String(rawTimeFormatVal).trim() !== ""
      ? String(rawTimeFormatVal)
      : defaultLocaleTimeFormat(store.hass);
  const resolvedTimeFormatValue =
    (rawTimeFormatOpts.length > 0 && !rawTimeFormatOpts.includes(effectiveTimeFormat)
      ? rawTimeFormatOpts[0]
      : undefined) ?? effectiveTimeFormat;
  const timeFormatOptions = rawTimeFormatOpts.map((opt) => ({
    value: opt,
    label: store.tPrefOption("time_format", opt),
  }));
  const shortTimeFormat = resolvedTimeFormatValue.startsWith("24")
    ? store.t("dev_interface.clock_24h")
    : store.t("dev_interface.clock_12h");

  // Home screen appearance controls consolidated into Home screen (`D-069`)
  const wakeGreetingPref = store.entity.getPref("wake_greeting");
  const wakeGreetingRaw = wakeGreetingPref?.value ?? cfg.wake_greeting;
  const wakeGreetingOn =
    wakeGreetingRaw !== undefined && wakeGreetingRaw !== null
      ? typeof wakeGreetingRaw === "string"
        ? !["", "0", "false", "off", "disabled"].includes(wakeGreetingRaw.trim().toLowerCase())
        : Boolean(wakeGreetingRaw)
      : true;
  const weatherBgPref = store.entity.getPref("weather_background");
  const weatherBgRaw = weatherBgPref?.value ?? cfg.weather_background;
  const weatherBgOn =
    weatherBgRaw !== undefined && weatherBgRaw !== null
      ? typeof weatherBgRaw === "string"
        ? !["", "0", "false", "off", "disabled"].includes(weatherBgRaw.trim().toLowerCase())
        : Boolean(weatherBgRaw)
      : true;
  const celestialPillItems = (["home_sun", "home_moon"] as const).map((key) => {
    const pref = store.entity.getPref(key);
    const rawVal = pref?.value ?? cfg[key];
    const enabled =
      rawVal !== undefined && rawVal !== null
        ? typeof rawVal === "string"
          ? !["", "0", "false", "off", "disabled"].includes(rawVal.trim().toLowerCase())
          : Boolean(rawVal)
        : true;
    return {
      token: key,
      label: store.tPrefLabel(key, pref?.label),
      enabled,
    };
  });

  const renderInlineClockFaceRow = (): TemplateResult | typeof nothing =>
    clockFaceOptions.length > 0
      ? renderSelectRow({
          id: "cfg-clock_face",
          label: store.tPrefLabel("clock_face"),
          description: store.t("dev_interface.clock_face_desc"),
          value: resolvedClockFaceValue,
          rawOptions: clockFaceOptions,
          onChange: (val) => {
            store.entity.stageDeviceSetting("clock_face", val, "cfg-clock_face");
          },
        })
      : nothing;

  const calLookaheadPref = store.entity.getPref("calendar_lookahead_days");
  const rawLookahead = Number(calLookaheadPref?.value ?? cfg.calendar_lookahead_days ?? 30);
  const calLookaheadDays =
    rawLookahead <= 10 ? 7 : rawLookahead <= 21 ? 14 : rawLookahead <= 45 ? 30 : 60;
  const calWeekStartPref = store.entity.getPref("calendar_week_start");
  const rawWeekStartVal = calWeekStartPref?.value ?? cfg.calendar_week_start;
  const effectiveWeekStart =
    rawWeekStartVal !== undefined &&
    rawWeekStartVal !== null &&
    String(rawWeekStartVal).trim() !== ""
      ? String(rawWeekStartVal)
      : hassFirstWeekday(store.hass);
  const calWeekStart = store.tPrefOption(
    "calendar_week_start",
    effectiveWeekStart === "Monday" ? "Monday" : "Sunday",
  );

  const sysCameras = store.entity.getSystemCameraEntities();
  const visibleCameras = store.entity.getVisibleCameras();
  const camViewPref = store.entity.getPref("camera_default_view");
  const camViewRaw = String(camViewPref?.value ?? cfg.camera_default_view ?? "Grid");
  const camViewVal = store.tPrefOption("camera_default_view", camViewRaw);
  const camFramingPref = store.entity.getPref("camera_framing");
  const camFramingRaw = String(camFramingPref?.value ?? cfg.camera_framing ?? "Uncropped");
  const camFramingVal = store.tPrefOption("camera_framing", camFramingRaw);

  const weatherAppBgPref = store.entity.getPref("weather_app_background");
  const weatherAppBgRaw = weatherAppBgPref?.value ?? cfg.weather_app_background;
  const weatherAppBgOn =
    weatherAppBgRaw !== undefined && weatherAppBgRaw !== null
      ? typeof weatherAppBgRaw === "string"
        ? !["", "0", "false", "off", "disabled"].includes(weatherAppBgRaw.trim().toLowerCase())
        : Boolean(weatherAppBgRaw)
      : true;

  const describeNativeDockApp = (routeToken: string): string => {
    switch (routeToken) {
      case "app:pinned": {
        if (pinnedItems.length === 0) {
          return store.t("dev_interface.pinned_empty_meta");
        }
        const pages = Math.ceil(pinnedItems.length / 6);
        return store.t("dev_interface.pinned_count_meta", {
          count: fmtNumber(pinnedItems.length, store.hass, 0),
          shortcutWord:
            pinnedItems.length === 1
              ? store.t("dev_interface.word_shortcut_one")
              : store.t("dev_interface.word_shortcut_many"),
          pages: fmtNumber(pages, store.hass, 0),
          pageWord:
            pages === 1
              ? store.t("dev_interface.word_page_one")
              : store.t("dev_interface.word_page_many"),
        });
      }
      case "app:music":
        return store.t("dev_interface.music_meta", {
          art: albumArtVal,
          albums: albumSortVal,
        });
      case "app:home_hub":
        return enabledHomeCats.length === 1
          ? store.t("dev_interface.categories_enabled_one")
          : store.t("dev_interface.categories_enabled_many", {
              count: fmtNumber(enabledHomeCats.length, store.hass, 0),
            });
      case "app:cameras":
        if (sysCameras.length === 0) {
          return store.t("dev_interface.cameras_empty_meta");
        }
        return visibleCameras.length === 1
          ? store.t("dev_interface.cameras_meta_one", {
              view: camViewVal,
              framing: camFramingVal,
            })
          : store.t("dev_interface.cameras_meta_many", {
              view: camViewVal,
              framing: camFramingVal,
              count: fmtNumber(visibleCameras.length, store.hass, 0),
            });
      case "app:area":
        return enabledAreaCats.length === 1
          ? store.t("dev_interface.categories_enabled_one")
          : store.t("dev_interface.categories_enabled_many", {
              count: fmtNumber(enabledAreaCats.length, store.hass, 0),
            });
      case "app:remote": {
        if (curRemoteMode === "all") return store.t("dev_interface.remote_all");
        if (curRemoteMode.startsWith("group:")) {
          const gid = curRemoteMode.slice(6);
          return remoteGroups.find((g) => g.id === gid)?.name || gid;
        }
        return store.t("dev_interface.remote_follow_area");
      }
      case "app:weather":
        return weatherAppBgOn
          ? store.t("dev_interface.weather_meta_live_sky")
          : store.t("dev_interface.weather_meta_wallpaper");
      case "app:time":
        if (showUtcClock && worldClockCount > 0) {
          return worldClockCount === 1
            ? store.t("dev_interface.time_utc_world_one")
            : store.t("dev_interface.time_utc_world_many", {
                count: fmtNumber(worldClockCount, store.hass, 0),
              });
        }
        if (worldClockCount > 0) {
          return worldClockCount === 1
            ? store.t("dev_interface.time_world_one")
            : store.t("dev_interface.time_world_many", {
                count: fmtNumber(worldClockCount, store.hass, 0),
              });
        }
        return showUtcClock
          ? store.t("dev_interface.time_local_utc")
          : store.t("dev_interface.time_local");
      case "app:clock":
        return `${clockFaceVal} • ${shortTimeFormat}`;
      case "app:calendar":
        return store.t("dev_interface.calendar_meta", {
          days: fmtNumber(calLookaheadDays, store.hass, 0),
          weekday: calWeekStart,
        });
      case "app:tools":
        return visibleToolsCount === 1
          ? store.t("dev_interface.tools_enabled_one")
          : store.t("dev_interface.tools_enabled_many", {
              count: fmtNumber(visibleToolsCount, store.hass, 0),
            });
      case "app:games":
        return visibleGamesCount === 1
          ? store.t("dev_interface.games_enabled_one")
          : store.t("dev_interface.games_enabled_many", {
              count: fmtNumber(visibleGamesCount, store.hass, 0),
            });
      default:
        return routeToken;
    }
  };

  const shortcutEntityMap = new Map(
    (data?.catalog?.shortcut_entities || []).map((e) => [e.id, e]),
  );
  const routeSpecMap = new Map(SHORTCUT_ROUTES_CATALOG.map((r) => [r.token, r]));

  const activeNativeSet = new Set(
    dockItems.filter((it) => isNativeDockRouteItem(it)).map((it) => it.target),
  );
  const hiddenNativeApps = NATIVE_DOCK_APP_TOKENS.filter((tok) => !activeNativeSet.has(tok));

  // Stable index-independent keys so `renderSortableList` preserves focus across keyboard `↑`/`↓` moves
  const dockItemKeys = (() => {
    const counts = new Map<string, number>();
    return dockItems.map((it) => {
      const base = isNativeDockRouteItem(it)
        ? `native:${it.target}`
        : `custom:${it.kind}:${it.target}:${it.action}:${it.label}:${it.icon}`;
      const occ = (counts.get(base) || 0) + 1;
      counts.set(base, occ);
      return occ === 1 ? base : `${base}#${occ}`;
    });
  })();

  const resolveDockItemPresentation = (
    item: ShortcutItem,
  ): { title: string; meta: string; icon: string } => {
    if (isNativeDockRouteItem(item)) {
      const spec = routeSpecMap.get(item.target);
      return {
        title: spec?.label || item.target,
        meta: describeNativeDockApp(item.target),
        icon: ROUTE_PREVIEW_ICONS[item.target] || "mdi:apps",
      };
    }

    if (item.kind === "route") {
      const spec = routeSpecMap.get(item.target);
      const title = item.label || spec?.label || item.target;
      const targetDesc = spec ? `${spec.group} • ${spec.label}` : item.target;
      return {
        title,
        meta: store.t("dev_interface.custom_route_meta", { target: targetDesc }),
        icon: item.icon || ROUTE_PREVIEW_ICONS[item.target] || "mdi:apps",
      };
    }

    const ent = shortcutEntityMap.get(item.target);
    const dom = item.target.split(".", 1)[0] || "";
    const actLbl = shortcutActionLabel(dom, item.action);
    const title = item.label || ent?.name || item.target;
    const meta = item.confirm
      ? store.t("dev_interface.custom_entity_confirm_meta", {
          action: actLbl,
          target: item.target,
        })
      : store.t("dev_interface.custom_entity_tap_meta", {
          action: actLbl,
          target: item.target,
        });
    return {
      title,
      meta,
      icon: item.icon || ent?.icon || "mdi:flash",
    };
  };

  return html`<section id="view-interface">
    ${renderDeviceOfflineBanner(store)}

    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-home-screen",
          heading: html`<h3 class="card-title">${store.t("card.home_screen")}</h3>`,
          contentClass: "settings-list",
          body: html`${renderSwitchRow({
              id: "cfg-home_screen_enabled",
              label: store.tPrefLabel("home_screen_enabled"),
              description: store.t("dev_interface.enable_home_desc"),
              checked: homeScreenEnabled,
              onChange: (checked) => {
                store.entity.stageDeviceSetting(
                  "home_screen_enabled",
                  checked,
                  "cfg-home_screen_enabled",
                );
              },
            })}
            ${renderSettingsRow({
              label: store.tPrefLabel("start_screen"),
              forId: "cfg-start_screen",
              description: homeScreenEnabled
                ? store.t("dev_interface.start_screen_multi_desc")
                : store.t("dev_interface.start_screen_single_desc"),
              control: html`<select
                  id="cfg-start_screen"
                  .value=${live(startScreenValue)}
                  @change=${(ev: Event) => {
                    store.entity.stageDeviceSetting(
                      "start_screen",
                      (ev.currentTarget as HTMLSelectElement).value,
                      "cfg-start_screen",
                    );
                  }}
                >
                  ${visibleStartOptions.map(
                    (o) =>
                      html`<option value=${o.value} .selected=${live(o.value === startScreenValue)}>
                        ${o.label}
                      </option>`,
                  )}
                </select>
                ${startScreenConfigApp
                  ? html`<button
                      type="button"
                      id="btn-configure-start-screen"
                      @click=${() => store.entity.openAppConfigModal(startScreenConfigApp)}
                      class="btn btn-secondary btn-compact"
                    >
                      ${store.t("action.configure")}
                    </button>`
                  : nothing}`,
            })}
            ${timeFormatOptions.length > 0
              ? renderSelectRow({
                  id: "cfg-time_format",
                  label: store.tPrefLabel("time_format"),
                  description: store.t("dev_interface.time_format_desc"),
                  value: resolvedTimeFormatValue,
                  rawOptions: timeFormatOptions,
                  onChange: (val) => {
                    store.entity.stageDeviceSetting("time_format", val, "cfg-time_format");
                  },
                })
              : nothing}
            ${!homeScreenEnabled && startScreenValue === "Clock Face"
              ? renderInlineClockFaceRow()
              : nothing}
            ${homeScreenEnabled
              ? html`${renderSelectRow({
                    id: "cfg-home_clock_tap_action",
                    label: store.tPrefLabel("home_clock_tap_action"),
                    description: store.t("dev_interface.home_clock_tap_desc"),
                    value: homeClockTapValue,
                    rawOptions: homeClockTapOptions,
                    onChange: (val) => {
                      store.entity.stageDeviceSetting(
                        "home_clock_tap_action",
                        val,
                        "cfg-home_clock_tap_action",
                      );
                    },
                  })}
                  ${homeClockTapValue === "Clock Face" || startScreenValue === "Clock Face"
                    ? renderInlineClockFaceRow()
                    : nothing}
                  ${renderSelectRow({
                    id: "cfg-home_date_tap_action",
                    label: store.tPrefLabel("home_date_tap_action"),
                    description: store.t("dev_interface.home_date_tap_desc"),
                    value: homeDateTapValue,
                    rawOptions: homeDateTapOptions,
                    onChange: (val) => {
                      store.entity.stageDeviceSetting(
                        "home_date_tap_action",
                        val,
                        "cfg-home_date_tap_action",
                      );
                    },
                  })}
                  ${renderSelectRow({
                    id: "cfg-return_to_home_timeout",
                    label: store.tPrefLabel("return_to_home_timeout"),
                    description: store.t("dev_interface.return_timeout_desc"),
                    value: returnTimeoutValue,
                    rawOptions: rawReturnTimeoutOptions,
                    onChange: (val) => {
                      store.entity.stageDeviceSetting(
                        "return_to_home_timeout",
                        val,
                        "cfg-return_to_home_timeout",
                      );
                    },
                  })}
                  ${renderSwitchRow({
                    id: "cfg-wake_greeting",
                    label: store.tPrefLabel("wake_greeting"),
                    description: store.t("dev_interface.wake_greeting_desc"),
                    checked: wakeGreetingOn,
                    onChange: (checked) => {
                      store.entity.stageDeviceSetting(
                        "wake_greeting",
                        checked,
                        "cfg-wake_greeting",
                      );
                    },
                  })}
                  ${renderSwitchRow({
                    id: "cfg-weather_background",
                    label: store.tPrefLabel("weather_background"),
                    description: store.t("dev_interface.weather_bg_desc"),
                    checked: weatherBgOn,
                    onChange: (checked) => {
                      store.entity.stageDeviceSetting(
                        "weather_background",
                        checked,
                        "cfg-weather_background",
                      );
                    },
                  })}
                  ${weatherBgOn
                    ? renderSettingsRow({
                        id: "weather-celestial-bodies",
                        label: store.t("dev_interface.sun_moon_label"),
                        description: store.t("dev_interface.sun_moon_desc"),
                        control: renderPillList({
                          id: "weather-celestial-pills",
                          ariaLabel: store.t("dev_interface.sun_moon_label"),
                          items: celestialPillItems,
                          onToggle: (token, nextEnabled) => {
                            store.entity.stageDeviceSetting(token, nextEnabled);
                          },
                          overlay: store.localeOverlay,
                        }),
                      })
                    : nothing}
                  ${renderSwitchRow({
                    id: "cfg-activity_card",
                    label: store.tPrefLabel("activity_card"),
                    description: store.t("dev_interface.activity_card_desc"),
                    checked: activityCardOn,
                    onChange: (checked) =>
                      store.entity.stageDeviceSetting(
                        "activity_card",
                        checked,
                        "cfg-activity_card",
                      ),
                  })}
                  ${activityCardOn
                    ? renderSettingsRow({
                        id: "activity-sources",
                        label: store.tPrefLabel("activity_sources"),
                        description: store.t("dev_interface.activity_sources_desc"),
                        stacked: true,
                        control: renderPillList({
                          id: "activity-sources-pills",
                          ariaLabel: store.tPrefLabel("activity_sources"),
                          items: activityPillItems,
                          onToggle: (token, nextEnabled) => {
                            store.entity.toggleActivitySource(token, nextEnabled);
                          },
                          onReorder: (fromIdx, toIdx) => {
                            store.entity.reorderActivitySources(fromIdx, toIdx);
                          },
                          overlay: store.localeOverlay,
                        }),
                      })
                    : nothing}`
              : nothing}`,
        })}
      </div>

      <div class="column">
        ${homeScreenEnabled
          ? renderCard({
              id: "card-app-dock",
              heading: html`<h3 class="card-title">${store.t("card.app_dock")}</h3>`,
              contentClass: "stack",
              body: html`<p class="row-description">
                  ${store.t("dev_interface.app_dock_desc")}
                </p>
                <div id="dock-shortcuts-container" class="stack">
                  ${renderSortableList({
                    id: "dock-shortcuts-list",
                    ariaLabel: store.t("dev_interface.active_dock_aria"),
                    items: dockItems,
                    rowClass: "dock-row",
                    getKey: (_item, idx) => dockItemKeys[idx] ?? String(idx),
                    getLabel: (item) => resolveDockItemPresentation(item).title,
                    onReorder: (fromIdx, toIdx) => {
                      store.entity.reorderShortcutItems("dock_items", fromIdx, toIdx);
                    },
                    renderContent: (item) => {
                      const info = resolveDockItemPresentation(item);
                      return html`<div class="input-action-row">
                        <span
                          class=${shortcutBadgeClass(item.badge_style, item.accent)}
                          aria-hidden="true"
                        >
                          <ha-icon .icon=${info.icon}></ha-icon>
                        </span>
                        <div class="shortcut-item-info">
                          <span class="shortcut-item-title">${info.title}</span>
                          <span class="shortcut-item-meta">${info.meta}</span>
                        </div>
                      </div>`;
                    },
                    renderActions: (item, idx) => {
                      const info = resolveDockItemPresentation(item);
                      if (isNativeDockRouteItem(item)) {
                        const configApp = NATIVE_DOCK_CONFIG_APP_MAP[item.target];
                        return html`${configApp
                            ? html`<button
                                type="button"
                                aria-label=${store.t("action.configure_item", {
                                  item: info.title,
                                })}
                                @click=${() => store.entity.openAppConfigModal(configApp)}
                                class="btn btn-secondary btn-compact"
                              >
                                ${store.t("action.configure")}
                              </button>`
                            : nothing}
                          <input
                            type="checkbox"
                            role="switch"
                            aria-label=${store.t("dev_interface.show_on_dock_aria", {
                              title: info.title,
                            })}
                            .checked=${live(true)}
                            @change=${(ev: Event) =>
                              store.entity.toggleNativeDockApp(
                                item.target,
                                (ev.currentTarget as HTMLInputElement).checked,
                              )}
                            class="switch"
                          />`;
                      }
                      return html`<button
                          type="button"
                          aria-label=${store.t("action.edit_item", { item: info.title })}
                          @click=${() => store.entity.openShortcutModal("dock_items", idx)}
                          class="btn btn-secondary btn-compact"
                        >
                          ${store.t("action.edit")}
                        </button>
                        ${renderTrashIconButton(
                          store.t("action.remove_item", { item: info.title }),
                          () => store.entity.removeShortcutItem("dock_items", idx),
                        )}`;
                    },
                    overlay: store.localeOverlay,
                  })}
                  <div class="dock-row shortcut-item-locked">
                    <span class="shortcut-icon-badge" aria-hidden="true">
                      <ha-icon .icon=${"mdi:cog"}></ha-icon>
                    </span>
                    <div class="shortcut-item-info">
                      <span class="shortcut-item-title">
                        ${store.t("dev_interface.settings_title")}
                      </span>
                      <span class="shortcut-item-meta">
                        ${store.t("dev_interface.settings_locked_meta")}
                      </span>
                    </div>
                  </div>
                </div>
                <div class="shortcut-toolbar">
                  <button
                    type="button"
                    id="btn-add-dock-item"
                    ?disabled=${dockItems.length >= MAX_DOCK_ITEMS}
                    @click=${() => store.entity.openShortcutModal("dock_items", null)}
                    class="btn btn-secondary"
                  >
                    ${store.t("action.add_custom_shortcut")}
                  </button>
                  <button
                    type="button"
                    id="btn-reset-dock-items"
                    @click=${() => store.entity.requestResetDockItems()}
                    class="btn btn-text"
                  >
                    ${store.t("action.reset_default_dock")}
                  </button>
                </div>
                ${hiddenNativeApps.length > 0
                  ? html`<div
                      id="dock-hidden-native-apps"
                      class="stack"
                      role="group"
                      aria-label=${store.t("dev_interface.hidden_from_dock")}
                    >
                      <div class="subsection-title">
                        ${store.t("dev_interface.hidden_from_dock")}
                      </div>
                      ${repeat(
                        hiddenNativeApps,
                        (tok) => tok,
                        (tok) => {
                          const spec = routeSpecMap.get(tok);
                          const displayTitle = spec?.label || tok;
                          const iconSlug = ROUTE_PREVIEW_ICONS[tok] || "mdi:apps";
                          const configApp = NATIVE_DOCK_CONFIG_APP_MAP[tok];
                          return html`<div class="dock-row shortcut-item-hidden">
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
                                  aria-label=${store.t("action.configure_item", {
                                    item: displayTitle,
                                  })}
                                  @click=${() => store.entity.openAppConfigModal(configApp)}
                                  class="btn btn-secondary btn-compact"
                                >
                                  ${store.t("action.configure")}
                                </button>`
                              : nothing}
                            <input
                              type="checkbox"
                              role="switch"
                              aria-label=${store.t("dev_interface.show_on_dock_aria", {
                                title: displayTitle,
                              })}
                              ?disabled=${dockItems.length >= MAX_DOCK_ITEMS}
                              .checked=${live(false)}
                              @change=${(ev: Event) =>
                                store.entity.toggleNativeDockApp(
                                  tok,
                                  (ev.currentTarget as HTMLInputElement).checked,
                                )}
                              class="switch"
                            />
                          </div>`;
                        },
                      )}
                    </div>`
                  : nothing}`,
            })
          : nothing}
      </div>
    </div>
  </section>`;
}
