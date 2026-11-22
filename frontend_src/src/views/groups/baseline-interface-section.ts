/**
 * Group Baseline Drawer — Interface Section (`views/groups/baseline-interface-section.ts`, `D-069`, `D-071`):
 * - Home screen, Clock/Date actions, Sky & weather, Activity card & sources
 * - Home Hub, Area Controls, Tools, Games category pills, Remote scope, Calendar, Music, & Cameras
 * - App Dock, Pinned shortcuts, & World clocks copy-from-Device rows
 */

import { renderSettingsRow, renderSwitchRow } from "../../components/controls.js";
import {
  ACTIVITY_SOURCES_CATALOG,
  AREA_CATEGORIES_CATALOG,
  type CatalogItem,
  DEFAULT_ACTIVITY_SOURCES,
  DEFAULT_AREA_CATEGORIES,
  DEFAULT_DOCK_ROUTES_TOKENS,
  DEFAULT_GAMES_ITEMS,
  DEFAULT_HOME_CATEGORIES,
  DEFAULT_TOOLS_ITEMS,
  GAMES_ITEMS_CATALOG,
  HOME_CATEGORIES_CATALOG,
  TOOLS_ITEMS_CATALOG,
} from "../../constants.js";
import { CALENDAR_LOOKAHEAD_OPTIONS } from "../../i18n/index.js";
import { html, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import type { DeviceCapabilities, DeviceGroup } from "../../types.js";
import { fmtNumber } from "../../utils/format.js";

export interface BaselineInterfaceHelpers {
  readonly caps: DeviceCapabilities;
  readonly hasLatterDevices: boolean;
  renderSpecSelect(key: string, currentVal: unknown): TemplateResult | typeof nothing;
  renderSpecSwitch(
    key: string,
    currentVal: unknown,
    extraGate?: boolean,
  ): TemplateResult | typeof nothing;
  renderLabeledSelect(
    key: string,
    currentVal: unknown,
    options: ReadonlyArray<{ value: string; label: string }>,
    defaultVal: string,
    asNumber?: boolean,
  ): TemplateResult;
  renderPills(
    key: string,
    currentVal: unknown,
    catalog: ReadonlyArray<CatalogItem>,
    defaultCsv: string,
    minRequired: number,
  ): TemplateResult;
  requestCopyKeys(copyKeys: string[], listLabel: string): void;
}

export function renderBaselineInterfaceSection(
  store: StudioStore,
  group: DeviceGroup,
  h: BaselineInterfaceHelpers,
): TemplateResult | typeof nothing {
  if (!group.include_interface || h.caps.has_display === false) {
    return nothing;
  }

  const gid = group.id;
  const cfg = group.device_config || {};
  const lookaheadOptions: Array<{ value: string; label: string }> = CALENDAR_LOOKAHEAD_OPTIONS.map(
    (o) => ({ value: String(o.value), label: o.label }),
  );
  const remoteGroups = store.state?.system_config?.remote_groups || [];
  const remoteScopeOptions: Array<{ value: string; label: string }> = [
    { value: "area_auto", label: store.t("groups.remote_match_area") },
    ...remoteGroups.map((rg) => ({
      value: `group:${rg.id}`,
      label: store.t("groups.remote_group_prefix", { name: rg.name }),
    })),
    { value: "all", label: store.t("groups.remote_all_system") },
  ];

  const dockCount = Array.isArray(cfg.dock_items)
    ? cfg.dock_items.length
    : DEFAULT_DOCK_ROUTES_TOKENS.length;
  const pinnedCount = Array.isArray(cfg.pinned_items) ? cfg.pinned_items.length : 0;
  const worldClocksStr = typeof cfg.world_clocks === "string" ? cfg.world_clocks.trim() : "";
  const clockCount = worldClocksStr ? worldClocksStr.split(";").filter(Boolean).length : 0;

  return html`<details class="sub-collapsible" open>
    <summary>${store.t("groups.section_interface")}</summary>
    <div class="card-content settings-list">
      ${h.renderSpecSwitch("home_screen_enabled", cfg.home_screen_enabled)}
      ${h.renderSpecSelect("start_screen", cfg.start_screen)}
      ${h.renderSpecSelect("time_format", cfg.time_format)}
      ${h.renderSpecSelect("home_clock_tap_action", cfg.home_clock_tap_action)}
      ${h.renderSpecSelect("clock_face", cfg.clock_face)}
      ${h.renderSpecSelect("home_date_tap_action", cfg.home_date_tap_action)}
      ${h.renderSpecSelect("return_to_home_timeout", cfg.return_to_home_timeout)}
      ${h.renderSpecSwitch("wake_greeting", cfg.wake_greeting)}
      ${h.renderSpecSwitch("weather_background", cfg.weather_background)}
      ${h.renderSpecSwitch("weather_app_background", cfg.weather_app_background)}
      ${h.renderSpecSwitch("home_sun", cfg.home_sun)}
      ${h.renderSpecSwitch("home_moon", cfg.home_moon)}
      ${renderSwitchRow({
        label: store.tPrefLabel("activity_card"),
        ariaLabel: store.t("groups.for_group_aria", {
          label: store.tPrefLabel("activity_card"),
          group: group.name,
        }),
        checked: cfg.activity_card !== false,
        onChange: (checked) =>
          void store.groups.updateGroupBaseline(gid, { activity_card: checked }),
      })}
      ${h.renderPills(
        "activity_sources",
        cfg.activity_sources,
        ACTIVITY_SOURCES_CATALOG,
        DEFAULT_ACTIVITY_SOURCES,
        0,
      )}
      ${h.renderPills(
        "home_categories",
        cfg.home_categories,
        HOME_CATEGORIES_CATALOG,
        DEFAULT_HOME_CATEGORIES,
        1,
      )}
      ${h.renderPills(
        "area_categories",
        cfg.area_categories,
        AREA_CATEGORIES_CATALOG,
        DEFAULT_AREA_CATEGORIES,
        1,
      )}
      ${h.renderPills(
        "tools_items",
        cfg.tools_items,
        TOOLS_ITEMS_CATALOG,
        DEFAULT_TOOLS_ITEMS,
        1,
      )}
      ${h.renderPills(
        "games_items",
        cfg.games_items,
        GAMES_ITEMS_CATALOG,
        DEFAULT_GAMES_ITEMS,
        1,
      )}
      ${h.renderLabeledSelect(
        "device_remote_group",
        cfg.device_remote_group,
        remoteScopeOptions,
        "area_auto",
      )}
      ${h.renderSpecSwitch("show_utc_clock", cfg.show_utc_clock)}
      ${h.renderLabeledSelect(
        "calendar_lookahead_days",
        cfg.calendar_lookahead_days ?? 30,
        lookaheadOptions,
        "30",
        true,
      )}
      ${h.renderSpecSelect("calendar_week_start", cfg.calendar_week_start)}
      ${h.renderSpecSelect("album_art_style", cfg.album_art_style)}
      ${h.renderSpecSelect("music_overlay_style", cfg.music_overlay_style)}
      ${h.renderSpecSelect("album_sort_order", cfg.album_sort_order)}
      ${h.renderSpecSelect("artist_album_sort_order", cfg.artist_album_sort_order)}
      ${h.renderSpecSelect("podcast_sort_order", cfg.podcast_sort_order)}
      ${h.renderSpecSelect("camera_default_view", cfg.camera_default_view)}
      ${h.renderSpecSelect("camera_framing", cfg.camera_framing)}
      ${h.renderSpecSelect("camera_carousel_interval", cfg.camera_carousel_interval)}
      ${h.renderSpecSelect("camera_stream_mode", cfg.camera_stream_mode)}
      ${h.renderSpecSelect("camera_doorbell_popup", cfg.camera_doorbell_popup)}
      ${h.hasLatterDevices
        ? html`${renderSettingsRow({
              label: store.t("card.app_dock"),
              description:
                dockCount === 1
                  ? store.t("groups.dock_baseline_desc_one")
                  : store.t("groups.dock_baseline_desc_many", {
                      count: fmtNumber(dockCount, store.hass, 0),
                    }),
              control: html`<button
                type="button"
                @click=${() => h.requestCopyKeys(["dock_items"], store.t("card.app_dock"))}
                class="btn btn-secondary btn-compact"
              >
                ${store.t("groups.copy_dock")}
              </button>`,
            })}
            ${renderSettingsRow({
              label: store.t("dialogs.pinned_label"),
              description:
                pinnedCount === 1
                  ? store.t("groups.pinned_baseline_desc_one")
                  : store.t("groups.pinned_baseline_desc_many", {
                      count: fmtNumber(pinnedCount, store.hass, 0),
                    }),
              control: html`<button
                type="button"
                @click=${() =>
                  h.requestCopyKeys(["pinned_items"], store.t("dialogs.pinned_label"))}
                class="btn btn-secondary btn-compact"
              >
                ${store.t("groups.copy_pinned")}
              </button>`,
            })}
            ${renderSettingsRow({
              label: store.t("dialogs.world_clocks_label"),
              description:
                clockCount === 1
                  ? store.t("groups.clocks_baseline_desc_one")
                  : store.t("groups.clocks_baseline_desc_many", {
                      count: fmtNumber(clockCount, store.hass, 0),
                    }),
              control: html`<button
                type="button"
                @click=${() =>
                  h.requestCopyKeys(["world_clocks"], store.t("dialogs.world_clocks_label"))}
                class="btn btn-secondary btn-compact"
              >
                ${store.t("groups.copy_clocks")}
              </button>`,
            })}`
        : nothing}
    </div>
  </details>`;
}
