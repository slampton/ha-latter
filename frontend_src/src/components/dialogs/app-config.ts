/**
 * Native App Configuration Modal (`#latter-app-config-modal`, `D-053`, `D-054`, `D-064`).
 * - Short-circuits closed `<dialog>` body
 * - Uses generated schema catalogs directly without fallback option arrays or runtime store method checks
 * - Editable `Clock` modal (`app === "clock"`)
 * - `renderSortableList` / `renderPillList` across Pinned, World clocks, Home categories, Area categories, Tools, & Games
 * - Single `isCatalogItemSupported(item, caps)` capability gate
 */

import {
  AREA_CATEGORIES_CATALOG,
  CALENDAR_WEEK_START_OPTIONS,
  type CatalogItem,
  GAMES_ITEMS_CATALOG,
  HOME_CATEGORIES_CATALOG,
  TOOLS_ITEMS_CATALOG,
} from "../../constants.js";
import {
  CALENDAR_LOOKAHEAD_OPTIONS,
  type StudioTranslationKey,
} from "../../i18n/index.js";
import { html, nothing, type TemplateResult } from "../../lib/lit.js";
import {
  isCatalogItemSupported,
  type StudioStore,
} from "../../state/store.js";
import { createDialogBackdropHandlers } from "../controls/aria-helpers.js";
import type { ConfigurableAppId, DeviceCapabilities } from "../../types.js";
import { defaultLocaleTimeFormat, entityLabel } from "../../utils/format.js";
import {
  type PillListItem,
  renderPillList,
  renderSelectRow,
  renderSettingsRow,
  renderSwitchRow,
} from "../controls.js";
import { renderPinnedGridEditor } from "./pinned-grid-editor.js";
import { renderTimeAppConfigBody } from "./world-clocks.js";

const APP_MODAL_TITLE_KEYS: Readonly<Record<ConfigurableAppId, StudioTranslationKey>> = {
  pinned: "dialogs.app_pinned",
  home_hub: "dialogs.app_home_hub",
  cameras: "dialogs.app_cameras",
  area: "dialogs.app_area",
  music: "dialogs.app_music",
  remote: "dialogs.app_remote",
  weather: "dialogs.app_weather",
  time: "dialogs.app_time",
  calendar: "dialogs.app_calendar",
  clock: "dialogs.app_clock",
  tools: "dialogs.app_tools",
  games: "dialogs.app_games",
};

export function buildOrderedPillItems(
  catalog: ReadonlyArray<CatalogItem>,
  enabledTokens: readonly string[],
  caps?: DeviceCapabilities,
): PillListItem[] {
  const supported = catalog.filter((c) => isCatalogItemSupported(c, caps));
  const byToken = new Map(supported.map((c) => [c.token, c]));
  const enabledSet = new Set<string>();
  const out: PillListItem[] = [];

  for (const tok of enabledTokens) {
    const meta = byToken.get(tok);
    if (!meta || enabledSet.has(tok)) continue;
    enabledSet.add(tok);
    out.push({ token: tok, label: meta.label, enabled: true });
  }
  for (const item of supported) {
    if (enabledSet.has(item.token)) continue;
    out.push({ token: item.token, label: item.label, enabled: false });
  }
  return out;
}

function resolvePrefOptions(
  store: StudioStore,
  key: string,
  caps?: DeviceCapabilities,
): readonly string[] {
  const livePref = store.entity.getPref(key);
  const spec = store.entity.getPrefSpec(key);
  const base =
    livePref?.options && livePref.options.length > 0
      ? livePref.options
      : spec?.options || [];
  if (key === "clock_face" && caps?.is_round === false) {
    return base.filter((opt) => opt !== "Modern Analog");
  }
  return base;
}

function resolvePrefStringValue(
  store: StudioStore,
  key: string,
  options: readonly string[],
): string {
  const livePref = store.entity.getPref(key);
  const cfgVal = store.state?.config?.[key];
  const spec = store.entity.getPrefSpec(key);
  const rawCandidate = livePref?.value ?? cfgVal;
  const fallbackVal =
    key === "time_format"
      ? defaultLocaleTimeFormat(store.hass)
      : spec?.default ?? "";
  const raw =
    rawCandidate !== undefined && rawCandidate !== null && String(rawCandidate).trim() !== ""
      ? String(rawCandidate)
      : String(fallbackVal);
  if (options.length > 0 && !options.includes(raw)) {
    return options[0] ?? raw;
  }
  return raw;
}

function renderEditableSelectPref(
  store: StudioStore,
  key: string,
  domId: string,
  caps?: DeviceCapabilities,
  description?: string,
): TemplateResult | typeof nothing {
  const options = resolvePrefOptions(store, key, caps);
  if (options.length === 0) return nothing;
  const curVal = resolvePrefStringValue(store, key, options);
  return renderSelectRow({
    id: domId || undefined,
    label: store.tPrefLabel(key),
    description,
    value: curVal,
    rawOptions: options.map((opt) => ({
      value: opt,
      label: store.tPrefOption(key, opt),
    })),
    onChange: (val) => store.entity.stageDeviceSetting(key, val, domId || undefined),
  });
}

export function renderAppConfigModalBody(store: StudioStore): TemplateResult | typeof nothing {
  const app = store.appConfigModal.app;
  if (!app) return nothing;

  const data = store.state;
  const cfg = data?.config || {};
  const caps = data?.capabilities;
  const title = store.t(APP_MODAL_TITLE_KEYS[app]);

  let body: TemplateResult;
  let extraAction: TemplateResult | typeof nothing = nothing;
  let donePrimary = true;

  if (app === "pinned") {
    donePrimary = false;
    body = renderPinnedGridEditor(store);
  } else if (app === "home_hub") {
    const enabledHomeCats = store.entity.getEnabledHomeCategories();
    const pillItems = buildOrderedPillItems(HOME_CATEGORIES_CATALOG, enabledHomeCats, caps);
    const sysSpeakers = store.entity.getSystemBroadcastSpeakers();
    const activeSpeakers = store.entity.getBroadcastSpeakers();
    const spkCatalogMap = new Map((data?.catalog?.ma_speakers || []).map((s) => [s.id, s]));
    const speakerPillLabel = (entityId: string): string => {
      const meta = spkCatalogMap.get(entityId);
      if (!meta?.name) return entityId;
      const stripped = meta.name.replace(/\s*\([^)]*\)\s*(?:\(unavailable\))?$/, "").trim();
      return stripped ? entityLabel(stripped) : entityId;
    };
    const activeSpkSet = new Set(activeSpeakers);
    const speakerPillItems: PillListItem[] = [
      ...activeSpeakers.map((id) => ({
        token: id,
        label: speakerPillLabel(id),
        enabled: true,
      })),
      ...sysSpeakers
        .filter((id) => !activeSpkSet.has(id))
        .map((id) => ({
          token: id,
          label: speakerPillLabel(id),
          enabled: false,
        })),
    ];

    body = html`<div class="settings-list">
      ${renderSettingsRow({
        label: store.t("dialogs.home_cats_label"),
        description: store.t("dialogs.home_cats_desc"),
        stacked: true,
        control: renderPillList({
          id: "home-categories-pills",
          ariaLabel: store.t("dialogs.home_cats_label"),
          items: pillItems,
          onToggle: (tok, next) => store.entity.toggleHomeCategoryToken(tok, next),
          onReorder: (fromIdx, toIdx) => store.entity.reorderHomeCategories(fromIdx, toIdx),
          overlay: store.localeOverlay,
        }),
      })}
      ${renderSettingsRow({
        id: "home-broadcast-speakers-row",
        label: store.t("dialogs.broadcast_speakers_label"),
        description: store.t("dialogs.broadcast_speakers_desc"),
        stacked: true,
        control:
          sysSpeakers.length > 0
            ? renderPillList({
                id: "broadcast-speakers-pills",
                ariaLabel: store.t("dialogs.broadcast_speakers_label"),
                items: speakerPillItems,
                onToggle: (tok, next) => store.entity.toggleBroadcastSpeaker(tok, next),
                onReorder: (fromIdx, toIdx) => store.entity.reorderBroadcastSpeakers(fromIdx, toIdx),
                overlay: store.localeOverlay,
              })
            : html`<p class="empty-state">
                ${store.t("dialogs.broadcast_speakers_empty_system")}
              </p>`,
      })}
    </div>`;
    extraAction = html`<button
      type="button"
      @click=${() => {
        store.entity.closeAppConfigModal();
        store.openSystemSection("shared_entities", "card-whole-home");
      }}
      class="btn btn-text"
    >
      ${store.t("action.open_shared_entities")}
    </button>`;
  } else if (app === "cameras") {
    const sysCameras = store.entity.getSystemCameraEntities();
    const visibleCameras = store.entity.getVisibleCameras();
    const carouselCameras = store.entity.getCarouselCameras();
    const camCatalogMap = new Map((data?.catalog?.cameras || []).map((c) => [c.id, c]));
    const camConfigs = data?.system_config?.camera_configs || {};
    const cameraPillLabel = (entityId: string): string => {
      const customLbl = String(camConfigs[entityId]?.label || "").trim();
      if (customLbl) return customLbl;
      const meta = camCatalogMap.get(entityId);
      return meta?.name ? entityLabel(meta.name) : entityId;
    };

    const visibleSet = new Set(visibleCameras);
    const visiblePillItems: PillListItem[] = [
      ...visibleCameras.map((id) => ({
        token: id,
        label: cameraPillLabel(id),
        enabled: true,
      })),
      ...sysCameras
        .filter((id) => !visibleSet.has(id))
        .map((id) => ({
          token: id,
          label: cameraPillLabel(id),
          enabled: false,
        })),
    ];

    const carouselSet = new Set(carouselCameras);
    const carouselPillItems: PillListItem[] = [
      ...carouselCameras.map((id) => ({
        token: id,
        label: cameraPillLabel(id),
        enabled: true,
      })),
      ...visibleCameras
        .filter((id) => !carouselSet.has(id))
        .map((id) => ({
          token: id,
          label: cameraPillLabel(id),
          enabled: false,
        })),
    ];

    body = html`<div class="settings-list">
      ${renderEditableSelectPref(
        store,
        "camera_default_view",
        "cfg-camera_default_view",
        caps,
        store.t("dialogs.camera_default_view_desc"),
      )}
      ${renderEditableSelectPref(
        store,
        "camera_framing",
        "cfg-camera_framing",
        caps,
        store.t("dialogs.camera_framing_desc"),
      )}
      ${renderEditableSelectPref(
        store,
        "camera_carousel_interval",
        "cfg-camera_carousel_interval",
        caps,
        store.t("dialogs.camera_carousel_interval_desc"),
      )}
      ${renderEditableSelectPref(
        store,
        "camera_stream_mode",
        "cfg-camera_stream_mode",
        caps,
        store.t("dialogs.camera_stream_mode_desc"),
      )}
      ${caps?.hw_jpeg === true
        ? renderEditableSelectPref(
            store,
            "camera_doorbell_popup",
            "cfg-camera_doorbell_popup",
            caps,
            store.t("dialogs.camera_doorbell_popup_desc"),
          )
        : nothing}
      ${renderSettingsRow({
        id: "camera-visible-row",
        label: store.t("dialogs.camera_visible_label"),
        description: store.t("dialogs.camera_visible_desc"),
        stacked: true,
        control:
          sysCameras.length > 0
            ? renderPillList({
                id: "camera-visible-pills",
                ariaLabel: store.t("dialogs.camera_visible_label"),
                items: visiblePillItems,
                onToggle: (tok, next) => store.entity.toggleVisibleCamera(tok, next),
                onReorder: (fromIdx, toIdx) => store.entity.reorderVisibleCameras(fromIdx, toIdx),
                overlay: store.localeOverlay,
              })
            : html`<p class="empty-state">${store.t("dialogs.cameras_empty_system")}</p>`,
      })}
      ${sysCameras.length > 0
        ? renderSettingsRow({
            id: "camera-carousel-row",
            label: store.t("dialogs.camera_carousel_label"),
            description: store.t("dialogs.camera_carousel_desc"),
            stacked: true,
            control: renderPillList({
              id: "camera-carousel-pills",
              ariaLabel: store.t("dialogs.camera_carousel_label"),
              items: carouselPillItems,
              onToggle: (tok, next) => store.entity.toggleCarouselCamera(tok, next),
              onReorder: (fromIdx, toIdx) => store.entity.reorderCarouselCameras(fromIdx, toIdx),
              overlay: store.localeOverlay,
            }),
          })
        : nothing}
    </div>`;
    extraAction = html`<button
      type="button"
      id="btn-cameras-open-shared"
      @click=${() => {
        store.entity.closeAppConfigModal();
        store.openSystemSection("shared_entities", "card-cameras-doorbell");
      }}
      class="btn btn-text"
    >
      ${store.t("action.open_shared_entities")}
    </button>`;
  } else if (app === "area") {
    const enabledAreaCats = store.entity.getEnabledAreaCategories();
    const pillItems = buildOrderedPillItems(AREA_CATEGORIES_CATALOG, enabledAreaCats, caps);
    body = html`<div class="settings-list">
      ${renderSettingsRow({
        label: store.t("dialogs.area_cats_label"),
        description: store.t("dialogs.area_cats_desc"),
        stacked: true,
        control: renderPillList({
          id: "area-categories-pills",
          ariaLabel: store.t("dialogs.area_cats_label"),
          items: pillItems,
          onToggle: (tok, next) => store.entity.toggleAreaCategoryToken(tok, next),
          onReorder: (fromIdx, toIdx) => store.entity.reorderAreaCategories(fromIdx, toIdx),
          overlay: store.localeOverlay,
        }),
      })}
    </div>`;
  } else if (app === "music") {
    const musicKeys = [
      "album_art_style",
      "music_overlay_style",
      "music_auto_open",
      "album_sort_order",
      "artist_album_sort_order",
      "podcast_sort_order",
    ] as const;
    body = html`<div class="settings-list">
      ${musicKeys.map((k) =>
        renderEditableSelectPref(
          store,
          k,
          `cfg-${k}`,
          caps,
          k === "music_auto_open" ? store.t("dialogs.music_auto_open_desc") : undefined,
        ),
      )}
    </div>`;
  } else if (app === "remote") {
    const remoteGroups = data?.system_config?.remote_groups || [];
    const curDevEntry = (data?.system_devices || []).find(
      (d) => d.subentry_id === store.activeSubentryId,
    );
    const curRemoteMode =
      String(cfg.device_remote_group || curDevEntry?.device_remote_group || "area_auto").trim() ||
      "area_auto";
    const remoteModeOptions: Array<{ value: string; label: string }> = [
      { value: "area_auto", label: store.t("dialogs.remote_follow_area") },
      ...remoteGroups.map((g) => ({
        value: `group:${g.id}`,
        label: store.t("dialogs.remote_group_option", { name: g.name }),
      })),
      { value: "all", label: store.t("dialogs.remote_all_system") },
    ];
    if (!remoteModeOptions.some((o) => o.value === curRemoteMode)) {
      const rawId = curRemoteMode.startsWith("group:") ? curRemoteMode.slice(6) : curRemoteMode;
      remoteModeOptions.push({
        value: curRemoteMode,
        label: store.t("dialogs.remote_missing_group", { id: rawId }),
      });
    }
    body = html`<div class="settings-list">
      ${renderSelectRow({
        id: "cfg-device_remote_group",
        label: store.t("dialogs.remote_group_label"),
        description: store.t("dialogs.remote_group_desc"),
        value: curRemoteMode,
        rawOptions: remoteModeOptions,
        onChange: (val) =>
          store.entity.stageDeviceSetting("device_remote_group", val, "cfg-device_remote_group"),
      })}
    </div>`;
    extraAction = html`<button
      type="button"
      @click=${() => {
        store.entity.closeAppConfigModal();
        store.openSystemSection("remotes", "card-remote-groups");
      }}
      class="btn btn-text"
    >
      ${store.t("dialogs.manage_remote_groups")}
    </button>`;
  } else if (app === "weather") {
    const weatherAppBgPref = store.entity.getPref("weather_app_background");
    const weatherAppBgRaw = weatherAppBgPref?.value ?? cfg.weather_app_background;
    const weatherAppBgOn =
      weatherAppBgRaw !== undefined && weatherAppBgRaw !== null
        ? typeof weatherAppBgRaw === "string"
          ? !["", "0", "false", "off", "disabled"].includes(weatherAppBgRaw.trim().toLowerCase())
          : Boolean(weatherAppBgRaw)
        : true;
    body = html`<div class="settings-list">
      ${renderSwitchRow({
        id: "cfg-weather_app_background",
        label: store.t("dialogs.weather_bg_label"),
        description: store.t("dialogs.weather_bg_desc"),
        checked: weatherAppBgOn,
        onChange: (checked) =>
          store.entity.stageDeviceSetting(
            "weather_app_background",
            checked,
            "cfg-weather_app_background",
          ),
      })}
    </div>`;
    extraAction = html`<button
      type="button"
      id="btn-weather-open-shared"
      @click=${() => {
        store.entity.closeAppConfigModal();
        store.openSystemSection("shared_entities", "card-whole-home");
      }}
      class="btn btn-text"
    >
      ${store.t("action.open_shared_entities")}
    </button>`;
  } else if (app === "time") {
    donePrimary = false;
    body = renderTimeAppConfigBody(store);
  } else if (app === "clock") {
    body = html`<div class="settings-list">
      ${renderEditableSelectPref(store, "clock_face", "cfg-clock_face", caps)}
      ${renderEditableSelectPref(store, "time_format", "cfg-time_format", caps)}
    </div>`;
  } else if (app === "calendar") {
    const lookaheadPref = store.entity.getPref("calendar_lookahead_days");
    const rawLookahead = Number(lookaheadPref?.value ?? cfg.calendar_lookahead_days ?? 30);
    const lookaheadDays =
      rawLookahead <= 10 ? 7 : rawLookahead <= 21 ? 14 : rawLookahead <= 45 ? 30 : 60;

    const weekStartOpts = resolvePrefOptions(store, "calendar_week_start", caps);
    const resolvedWeekOpts = weekStartOpts.length > 0 ? weekStartOpts : CALENDAR_WEEK_START_OPTIONS;
    const weekStartVal = resolvePrefStringValue(
      store,
      "calendar_week_start",
      resolvedWeekOpts,
    );

    body = html`<div class="settings-list">
      ${renderSelectRow({
        id: "cfg-calendar_lookahead_days",
        label: store.t("dialogs.calendar_lookahead_label"),
        description: store.t("dialogs.calendar_lookahead_desc"),
        value: String(lookaheadDays),
        rawOptions: CALENDAR_LOOKAHEAD_OPTIONS.map((o) => ({
          value: String(o.value),
          label: o.label,
        })),
        onChange: (val) =>
          store.entity.stageDeviceSetting(
            "calendar_lookahead_days",
            Number(val),
            "cfg-calendar_lookahead_days",
          ),
      })}
      ${renderSelectRow({
        id: "cfg-calendar_week_start",
        label: store.t("dialogs.calendar_week_start_label"),
        description: store.t("dialogs.calendar_week_start_desc"),
        value: weekStartVal,
        rawOptions: resolvedWeekOpts.map((opt) => ({
          value: opt,
          label: store.tPrefOption("calendar_week_start", opt),
        })),
        onChange: (val) =>
          store.entity.stageDeviceSetting("calendar_week_start", val, "cfg-calendar_week_start"),
      })}
    </div>`;
    extraAction = html`<button
      type="button"
      @click=${() => {
        store.entity.closeAppConfigModal();
        store.openSystemSection("shared_entities", "card-calendars");
      }}
      class="btn btn-text"
    >
      ${store.t("action.open_shared_entities")}
    </button>`;
  } else if (app === "tools") {
    const enabledTools = store.entity.getEnabledToolsItems();
    const pillItems = buildOrderedPillItems(TOOLS_ITEMS_CATALOG, enabledTools, caps);
    body = html`<div class="settings-list">
      ${renderSettingsRow({
        label: store.t("dialogs.tools_label"),
        description: store.t("dialogs.tools_desc"),
        stacked: true,
        control: renderPillList({
          id: "tools-items-pills",
          ariaLabel: store.t("dialogs.tools_label"),
          items: pillItems,
          onToggle: (tok, next) => store.entity.toggleToolItemToken(tok, next),
          onReorder: (fromIdx, toIdx) => store.entity.reorderToolsItems(fromIdx, toIdx),
          overlay: store.localeOverlay,
        }),
      })}
    </div>`;
  } else {
    const enabledGames = store.entity.getEnabledGamesItems();
    const pillItems = buildOrderedPillItems(GAMES_ITEMS_CATALOG, enabledGames, caps);
    body = html`<div class="settings-list">
      ${renderSettingsRow({
        label: store.t("dialogs.games_label"),
        description: store.t("dialogs.games_desc"),
        stacked: true,
        control: renderPillList({
          id: "games-items-pills",
          ariaLabel: store.t("dialogs.games_label"),
          items: pillItems,
          onToggle: (tok, next) => store.entity.toggleGameItemToken(tok, next),
          onReorder: (fromIdx, toIdx) => store.entity.reorderGamesItems(fromIdx, toIdx),
          overlay: store.localeOverlay,
        }),
      })}
    </div>`;
  }

  return html`<div class="dialog-body">
    <h1 id="latter-app-config-title" class="dialog-title">${title}</h1>
    ${body}
    <div class="dialog-actions">
      ${extraAction}
      <button
        type="button"
        id="app-config-done-btn"
        @click=${() => store.entity.closeAppConfigModal()}
        class="btn ${donePrimary ? "btn-primary" : "btn-secondary"}"
      >
        ${store.t("action.done")}
      </button>
    </div>
  </div>`;
}

export function renderAppConfigDialog(store: StudioStore): TemplateResult {
  const close = (): void => {
    if (store.appConfigModal.open) {
      store.entity.closeAppConfigModal();
    }
  };
  const backdrop = createDialogBackdropHandlers(close);
  const isPinnedGrid = store.appConfigModal.open && store.appConfigModal.app === "pinned";

  return html`<dialog
    id="latter-app-config-modal"
    aria-labelledby="latter-app-config-title"
    closedby="any"
    @cancel=${close}
    @close=${close}
    @pointerdown=${backdrop.onPointerDown}
    @click=${backdrop.onClick}
    class="studio-dialog ${isPinnedGrid ? "grid-editor-dialog" : "shortcut-dialog"}"
  >
    ${store.appConfigModal.open ? renderAppConfigModalBody(store) : nothing}
  </dialog>`;
}
