/**
 * Group Baseline Drawer (`system_sync` Column 1, `D-048`, `D-050`, `D-063`, `D-064`, `D-069`, `D-071`, `D-072`).
 *
 * Renders the Behavior, Display, and Interface baseline sections with trait-gated
 * spec adapters (`isCatalogItemSupported`) and confirmation-guarded copy-from-Device actions.
 */

import {
  renderHourSelectRow,
  renderRangeRow,
  renderSettingsRow,
  renderSwitchRow,
} from "../../components/controls.js";
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
  VIRTUAL_COLLECTION_ALL,
  VIRTUAL_COLLECTION_DEFAULTS,
  VIRTUAL_COLLECTION_UPLOADS,
} from "../../constants.js";
import {
  CALENDAR_LOOKAHEAD_OPTIONS,
  SECURITY_PIN_POLICY_OPTIONS,
  WALLPAPER_ROTATION_OPTIONS,
} from "../../i18n/index.js";
import { html, live, nothing, type TemplateResult } from "../../lib/lit.js";
import { isPhotoDynamic } from "../../state/photo-ops.js";
import { isCatalogItemSupported, type StudioStore } from "../../state/store.js";
import type {
  DeviceCapabilities,
  DeviceGroup,
  SystemDeviceEntry,
} from "../../types.js";
import {
  defaultLocaleTimeFormat,
  fmtNumber,
  isValidHexColor,
} from "../../utils/format.js";

interface BaselineSectionHelpers {
  readonly caps: DeviceCapabilities;
  readonly hasLatterDevices: boolean;
  renderSpecSelect(key: string, currentVal: unknown): TemplateResult | typeof nothing;
  renderSpecSwitch(
    key: string,
    currentVal: unknown,
    extraGate?: boolean,
  ): TemplateResult | typeof nothing;
  renderSpecRange(
    key: string,
    currentVal: unknown,
    fallbackBounds?: { min: number; max: number; step: number; unit: string; defaultVal: number },
  ): TemplateResult | typeof nothing;
  renderSpecHourSelect(key: string, currentVal: unknown): TemplateResult | typeof nothing;
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

function deriveMembersHasImu(members: readonly SystemDeviceEntry[]): boolean | undefined {
  if (members.length === 0) return undefined;
  const hasImu = members.some((m) => m.has_imu === true);
  const noImu = members.some((m) => m.has_imu === false);
  return hasImu && !noImu ? true : !hasImu && noImu ? false : undefined;
}

export function deriveGroupCapabilities(
  group: DeviceGroup,
  members: readonly SystemDeviceEntry[],
): DeviceCapabilities {
  if (group.id === "pocket_carry") {
    return {
      has_display: true,
      is_round: true,
      has_imu: true,
      has_battery: true,
      has_ble_beacon: true,
      has_voice: true,
      has_audio: true,
      is_roaming_device: true,
      hw_jpeg: false,
      grid_cols: 2,
      grid_rows: 3,
    };
  }
  if (group.id === "handhelds") {
    return {
      has_display: true,
      is_round: false,
      has_imu: deriveMembersHasImu(members),
      has_battery: true,
      has_ble_beacon: true,
      has_voice: true,
      has_audio: true,
      is_roaming_device: true,
      hw_jpeg: members.length > 0 ? members.some((m) => m.hw_jpeg === true) : true,
      grid_cols: 2,
      grid_rows: 3,
    };
  }
  if (group.id === "wearables") {
    return {
      has_display: true,
      is_round: false,
      has_imu: true,
      has_battery: true,
      has_ble_beacon: true,
      has_voice: true,
      has_audio: true,
      is_roaming_device: true,
      hw_jpeg: false,
      grid_cols: 2,
      grid_rows: 3,
    };
  }
  if (group.id === "wall_panels") {
    return {
      has_display: true,
      is_round: false,
      has_imu: false,
      has_battery: false,
      has_ble_beacon: true,
      has_voice: true,
      has_audio: true,
      is_roaming_device: false,
      hw_jpeg: true,
      grid_cols: 3,
      grid_rows: 3,
    };
  }
  if (members.length > 0) {
    return {
      has_display: members.some((m) => m.has_display !== false),
      has_imu: deriveMembersHasImu(members),
      has_battery: members.some((m) => m.has_battery !== false),
      has_ble_beacon: members.some((m) => m.has_ble !== false),
      is_roaming_device: members.some((m) => m.is_roaming !== false),
      hw_jpeg: members.some((m) => m.hw_jpeg === true),
    };
  }
  return { hw_jpeg: true };
}

function renderSpecSelect(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  caps: DeviceCapabilities,
): TemplateResult | typeof nothing {
  const spec = store.entity.getPrefSpec(key);
  if (!spec || !isCatalogItemSupported(spec, caps)) {
    return nothing;
  }
  const options = spec.options || [];
  if (options.length === 0) return nothing;
  const fallbackVal = String(spec.default ?? options[0]);
  const cur =
    typeof currentVal === "string" && options.includes(currentVal) ? currentVal : fallbackVal;
  const label = store.tPrefLabel(key, spec.label);
  return renderSettingsRow({
    label,
    control: html`<select
      aria-label=${store.t("groups.for_group_aria", { label, group: group.name })}
      .value=${live(cur)}
      @change=${(ev: Event) =>
        void store.groups.updateGroupBaseline(group.id, {
          [key]: (ev.currentTarget as HTMLSelectElement).value,
        })}
    >
      ${options.map(
        (opt) => html`<option value=${opt} .selected=${live(opt === cur)}>
          ${store.tPrefOption(key, opt)}
        </option>`,
      )}
    </select>`,
  });
}

function renderSpecSwitch(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  caps: DeviceCapabilities,
  extraGate = true,
): TemplateResult | typeof nothing {
  if (!extraGate) return nothing;
  const spec = store.entity.getPrefSpec(key);
  if (spec && !isCatalogItemSupported(spec, caps)) {
    return nothing;
  }
  const defaultBool = spec ? Boolean(spec.default) : true;
  const checked =
    currentVal !== undefined && currentVal !== null ? Boolean(currentVal) : defaultBool;
  const label = store.tPrefLabel(key, spec?.label);
  return renderSwitchRow({
    label,
    ariaLabel: store.t("groups.for_group_aria", { label, group: group.name }),
    checked,
    onChange: (next) => void store.groups.updateGroupBaseline(group.id, { [key]: next }),
  });
}

function renderSpecRange(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  caps: DeviceCapabilities,
  fallbackBounds?: { min: number; max: number; step: number; unit: string; defaultVal: number },
): TemplateResult | typeof nothing {
  const spec = store.entity.getPrefSpec(key);
  if (spec && !isCatalogItemSupported(spec, caps)) {
    return nothing;
  }
  const min = spec?.min ?? fallbackBounds?.min ?? 0;
  const max = spec?.max ?? fallbackBounds?.max ?? 100;
  const step = spec?.step ?? fallbackBounds?.step ?? 1;
  const unit = spec?.unit ?? fallbackBounds?.unit ?? "";
  const defNum = Number(spec?.default ?? fallbackBounds?.defaultVal ?? min);
  const numVal = Number.isFinite(Number(currentVal)) ? Number(currentVal) : defNum;
  const label = store.tPrefLabel(key, spec?.label);

  return renderRangeRow({
    label,
    ariaLabel: store.t("groups.for_group_aria", { label, group: group.name }),
    value: numVal,
    min,
    max,
    step,
    unit,
    is24h: defaultLocaleTimeFormat(store.hass).startsWith("24"),
    hass: store.hass,
    onCommit: (nextVal) =>
      void store.groups.updateGroupBaseline(group.id, { [key]: nextVal }),
  });
}

function renderSpecHourSelect(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  caps: DeviceCapabilities,
): TemplateResult | typeof nothing {
  const spec = store.entity.getPrefSpec(key);
  if (spec && !isCatalogItemSupported(spec, caps)) {
    return nothing;
  }
  const defNum = Number(spec?.default ?? 0);
  const numVal = Number.isFinite(Number(currentVal)) ? Number(currentVal) : defNum;
  const label = store.tPrefLabel(key, spec?.label);

  return renderHourSelectRow({
    label,
    ariaLabel: store.t("groups.for_group_aria", { label, group: group.name }),
    value: numVal,
    is24h: defaultLocaleTimeFormat(store.hass).startsWith("24"),
    hass: store.hass,
    onCommit: (nextHour) =>
      void store.groups.updateGroupBaseline(group.id, { [key]: nextHour }),
  });
}

function renderBaselineLabeledSelect(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  options: ReadonlyArray<{ value: string; label: string }>,
  defaultVal: string,
  asNumber = false,
): TemplateResult {
  const curStr =
    currentVal !== undefined && currentVal !== null ? String(currentVal) : defaultVal;
  const cur = options.some((o) => o.value === curStr) ? curStr : defaultVal;
  const label = store.tPrefLabel(key);
  return renderSettingsRow({
    label,
    control: html`<select
      aria-label=${store.t("groups.for_group_aria", { label, group: group.name })}
      .value=${live(cur)}
      @change=${(ev: Event) => {
        const raw = (ev.currentTarget as HTMLSelectElement).value;
        const val = asNumber ? Number(raw) || 0 : raw;
        void store.groups.updateGroupBaseline(group.id, { [key]: val });
      }}
    >
      ${options.map(
        (opt) =>
          html`<option value=${opt.value} .selected=${live(opt.value === cur)}>
            ${opt.label}
          </option>`,
      )}
    </select>`,
  });
}

function renderBaselinePills(
  store: StudioStore,
  group: DeviceGroup,
  key: string,
  currentVal: unknown,
  catalog: ReadonlyArray<CatalogItem>,
  defaultCsv: string,
  minRequired: number,
  caps: DeviceCapabilities,
): TemplateResult {
  const supportedCatalog = catalog.filter((c) => isCatalogItemSupported(c, caps));
  const supportedTokens = new Set(supportedCatalog.map((c) => c.token));
  const csvStr = typeof currentVal === "string" ? currentVal : defaultCsv;
  const activeSet = new Set(
    csvStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );
  const label = store.tPrefLabel(key);

  const toggleTok = (tok: string): void => {
    const next = new Set(activeSet);
    if (next.has(tok)) {
      const visibleActiveCount = Array.from(activeSet).filter((t) =>
        supportedTokens.has(t),
      ).length;
      if (
        next.size <= minRequired ||
        (supportedTokens.has(tok) && visibleActiveCount <= minRequired)
      ) {
        const noun =
          key === "tools_items"
            ? "tool"
            : key === "games_items"
              ? "game"
              : "category";
        store.showToast(store.t("common.keep_one_enabled", { noun }), true);
        return;
      }
      next.delete(tok);
    } else {
      next.add(tok);
    }
    const ordered = catalog.map((c) => c.token).filter((t) => next.has(t));
    void store.groups.updateGroupBaseline(group.id, { [key]: ordered.join(",") });
  };

  return renderSettingsRow({
    label,
    stacked: true,
    control: html`<div
      role="group"
      aria-label=${store.t("groups.for_group_aria", { label, group: group.name })}
      class="pill-list"
    >
      ${supportedCatalog.map((item) => {
        const on = activeSet.has(item.token);
        return html`<span class="pill ${on ? "enabled" : ""}">
          <button
            type="button"
            aria-pressed=${on ? "true" : "false"}
            @click=${() => toggleTok(item.token)}
            class="pill-toggle"
          >
            ${item.label}
          </button>
        </span>`;
      })}
    </div>`,
  });
}

function requestCopyDeviceIntoGroup(
  store: StudioStore,
  group: DeviceGroup,
  memberCount: number,
  sourceSubentryId: string,
  latterDevices: readonly SystemDeviceEntry[],
  copyKeys?: string[],
  listLabel?: string,
): void {
  const srcDev = latterDevices.find((d) => d.subentry_id === sourceSubentryId);
  const devName = srcDev?.title || sourceSubentryId;
  store.openConfirm({
    kind: "copy_group_baseline",
    title: store.t("groups.confirm_copy_title", { group: group.name }),
    consequence: listLabel
      ? store.t("groups.confirm_copy_list_body", {
          listLabel,
          device: devName,
          group: group.name,
        })
      : store.t("groups.confirm_copy_body", {
          group: group.name,
          device: devName,
        }),
    confirmLabel: store.t("groups.confirm_copy_confirm"),
    danger: false,
    blastRadiusCount: memberCount > 0 ? memberCount : null,
    onConfirm: async () => {
      await store.groups.copyDeviceToGroupBaseline(group.id, sourceSubentryId, copyKeys);
    },
  });
}

function encodePoolSelectValue(modeVal: unknown, sourceVal: unknown, colVal: unknown): string {
  const mode = String(modeVal || "");
  const src = String(sourceVal || "");
  const col = String(colVal || "");
  if (mode === "collection" && col) return `collection:${col}`;
  if (mode === "single" && src) return `single:${src}`;
  if (!mode && src) return `single:${src}`;
  return "off";
}

function renderBaselineBehaviorSection(
  store: StudioStore,
  group: DeviceGroup,
  h: BaselineSectionHelpers,
): TemplateResult {
  const gid = group.id;
  const cfg = group.device_config || {};
  const { caps } = h;
  const autoBrt = String(cfg.auto_brightness_mode || "Sun Synchronized");
  const wwMode = String(cfg.wake_word_mode || "Docked Only");
  const bleOn = Boolean(cfg.native_ble_tracking);
  const autoSw = cfg.ble_auto_switch !== undefined ? Boolean(cfg.ble_auto_switch) : bleOn;
  const vfm = Boolean(cfg.sync_device_area);
  const handoff = Boolean(cfg.area_handoff);
  const pinPolicy = String(cfg.security_pin_policy || "auto");
  const groupSsMode = String(cfg.screensaver_mode ?? "Docked Only");

  return html`<details class="sub-collapsible" open>
      <summary>${store.t("groups.section_power_brightness")}</summary>
      <div class="card-content settings-list">
        ${h.renderSpecSelect("tap_to_wake", cfg.tap_to_wake)}
        ${h.renderSpecSelect("pickup_to_wake", cfg.pickup_to_wake)}
        ${h.renderSpecSelect("battery_screen_timeout", cfg.battery_screen_timeout)}
        ${h.renderSpecSelect("battery_hibernate_timeout", cfg.battery_hibernate_timeout)}
        ${h.renderSpecSelect("screensaver_mode", cfg.screensaver_mode)}
        ${caps.has_battery !== false || groupSsMode !== "Never"
          ? h.renderSpecSelect("docked_idle_timeout", cfg.docked_idle_timeout)
          : nothing}
        ${h.renderSpecSelect("auto_brightness_mode", cfg.auto_brightness_mode)}
        ${autoBrt === "Disabled"
          ? h.renderSpecRange("manual_brightness", cfg.manual_brightness)
          : html`${h.renderSpecRange("day_brightness", cfg.day_brightness)}
              ${h.renderSpecRange("night_brightness", cfg.night_brightness)}`}
        ${autoBrt === "Time Schedule"
          ? html`${h.renderSpecHourSelect("day_start_hour", cfg.day_start_hour)}
              ${h.renderSpecHourSelect("night_start_hour", cfg.night_start_hour)}`
          : nothing}
        ${h.renderSpecSelect("bedtime_display", cfg.bedtime_display)}
        ${h.renderSpecRange("bedtime_brightness", cfg.bedtime_brightness)}
        ${h.renderSpecSwitch("bedtime_schedule", cfg.bedtime_schedule)}
        ${Boolean(cfg.bedtime_schedule)
          ? html`${h.renderSpecHourSelect("bedtime_start_hour", cfg.bedtime_start_hour)}
              ${h.renderSpecHourSelect("bedtime_end_hour", cfg.bedtime_end_hour)}`
          : nothing}
      </div>
    </details>

    <details class="sub-collapsible">
      <summary>${store.t("groups.section_audio_voice")}</summary>
      <div class="card-content settings-list">
        ${h.renderSpecSelect("wake_word_mode", cfg.wake_word_mode)}
        ${wwMode !== "Disabled"
          ? html`${h.renderSpecSelect("ww_sens_okay_nabu", cfg.ww_sens_okay_nabu)}
              ${h.renderSpecSelect("ww_sens_hey_luna", cfg.ww_sens_hey_luna)}
              ${h.renderSpecSelect("ww_sens_hey_jarvis", cfg.ww_sens_hey_jarvis)}
              ${h.renderSpecSelect("ww_sens_hey_mycroft", cfg.ww_sens_hey_mycroft)}
              ${h.renderSpecSelect("ww_sens_alexa", cfg.ww_sens_alexa)}`
          : nothing}
        ${h.renderSpecSwitch("wake_screen_on_assist", cfg.wake_screen_on_assist)}
        ${h.renderSpecRange("alert_volume", cfg.alert_volume)}
        ${h.renderSpecRange("volume_step_size", cfg.volume_step_size)}
        ${h.renderSpecSwitch("game_sound_effects", cfg.game_sound_effects)}
        ${bleOn && caps.is_roaming_device !== false
          ? html`${renderSwitchRow({
                label: store.tPrefLabel("sync_device_area"),
                ariaLabel: store.t("groups.for_group_aria", {
                  label: store.tPrefLabel("sync_device_area"),
                  group: group.name,
                }),
                checked: vfm,
                onChange: (checked) =>
                  void store.groups.updateGroupBaseline(gid, { sync_device_area: checked }),
              })}
              ${vfm
                ? h.renderSpecRange("area_follow_dwell_s", cfg.area_follow_dwell_s, {
                    min: 3,
                    max: 60,
                    step: 1,
                    unit: "s",
                    defaultVal: 10,
                  })
                : nothing}`
          : nothing}
        ${renderSwitchRow({
          label: store.tPrefLabel("area_handoff"),
          ariaLabel: store.t("groups.for_group_aria", {
            label: store.tPrefLabel("area_handoff"),
            group: group.name,
          }),
          checked: handoff,
          onChange: (checked) =>
            void store.groups.updateGroupBaseline(gid, { area_handoff: checked }),
        })}
      </div>
    </details>

    <details class="sub-collapsible">
      <summary>${store.t("groups.section_presence_security")}</summary>
      <div class="card-content settings-list">
        ${renderSwitchRow({
          label: store.tPrefLabel("native_ble_tracking"),
          ariaLabel: store.t("groups.for_group_aria", {
            label: store.tPrefLabel("native_ble_tracking"),
            group: group.name,
          }),
          checked: bleOn,
          onChange: (checked) =>
            void store.groups.updateGroupBaseline(gid, { native_ble_tracking: checked }),
        })}
        ${bleOn
          ? html`${renderSwitchRow({
                label: store.tPrefLabel("ble_auto_switch"),
                ariaLabel: store.t("groups.for_group_aria", {
                  label: store.tPrefLabel("ble_auto_switch"),
                  group: group.name,
                }),
                checked: autoSw,
                onChange: (checked) =>
                  void store.groups.updateGroupBaseline(gid, { ble_auto_switch: checked }),
              })}
              ${h.renderSpecSelect("ble_beacon_mode", cfg.ble_beacon_mode)}`
          : nothing}
        ${h.renderLabeledSelect(
          "security_pin_policy",
          pinPolicy,
          SECURITY_PIN_POLICY_OPTIONS.map((opt) => ({
            value: opt.value,
            label: store.tPrefOption("security_pin_policy", opt.value),
          })),
          "auto",
        )}
      </div>
    </details>`;
}

function renderBaselineDisplaySection(
  store: StudioStore,
  group: DeviceGroup,
  h: BaselineSectionHelpers,
): TemplateResult | typeof nothing {
  if (!group.include_display || h.caps.has_display === false) {
    return nothing;
  }

  const gid = group.id;
  const cfg = group.device_config || {};
  const colorProfile = String(cfg.color_profile || "Steel Blue");
  const rawCustomHex =
    typeof cfg.device_custom_color === "string" ? cfg.device_custom_color : null;
  const customHex = isValidHexColor(rawCustomHex)
    ? String(rawCustomHex).toUpperCase()
    : "#3898FF";
  const groupSsStyle = String(cfg.screensaver_style ?? "Ambient Clock");

  const sysWallpapers = store.state?.system_wallpapers || [];
  const photoCollections = store.state?.photo_collections || [];

  const buildCompactPoolOptions = (
    excludeDynamic: boolean,
  ): Array<{ value: string; label: string }> => {
    const photos = excludeDynamic
      ? sysWallpapers.filter((wp) => !isPhotoDynamic(wp))
      : sysWallpapers;
    return [
      { value: "off", label: store.t("groups.pool_off") },
      { value: `collection:${VIRTUAL_COLLECTION_ALL}`, label: store.t("groups.pool_all") },
      {
        value: `collection:${VIRTUAL_COLLECTION_DEFAULTS}`,
        label: store.t("groups.pool_defaults"),
      },
      {
        value: `collection:${VIRTUAL_COLLECTION_UPLOADS}`,
        label: store.t("groups.pool_uploads"),
      },
      ...photoCollections.map((c) => ({
        value: `collection:${c.id}`,
        label: store.t("groups.pool_collection_prefix", { name: c.name }),
      })),
      ...photos.map((wp) => ({
        value: `single:${wp.id}`,
        label: store.t("groups.pool_photo_prefix", { name: wp.name || wp.id }),
      })),
    ];
  };

  const wpPoolOptions = buildCompactPoolOptions(false);
  const wpPoolCurrent = encodePoolSelectValue(
    cfg.wallpaper_mode,
    cfg.wallpaper_source,
    cfg.wallpaper_collection,
  );
  const ssPoolOptions = buildCompactPoolOptions(true);
  const ssPoolCurrent = encodePoolSelectValue(
    cfg.screensaver_photo_mode,
    cfg.screensaver_photo_source,
    cfg.screensaver_photo_collection,
  );
  const rotationOptions: Array<{ value: string; label: string }> = WALLPAPER_ROTATION_OPTIONS.map(
    (o) => ({ value: String(o.value), label: o.label }),
  );

  return html`<details class="sub-collapsible" open>
    <summary>${store.t("groups.section_display")}</summary>
    <div class="card-content settings-list">
      ${renderSettingsRow({
        label: store.t("groups.wallpaper_pool_label"),
        control: html`<select
          aria-label=${store.t("groups.for_group_aria", {
            label: store.t("groups.wallpaper_pool_label"),
            group: group.name,
          })}
          .value=${live(wpPoolCurrent)}
          @change=${(ev: Event) => {
            const raw = (ev.currentTarget as HTMLSelectElement).value;
            if (raw.startsWith("collection:")) {
              void store.groups.updateGroupBaseline(gid, {
                wallpaper_mode: "collection",
                wallpaper_collection: raw.slice(11),
                wallpaper_source: "",
              });
            } else if (raw.startsWith("single:")) {
              void store.groups.updateGroupBaseline(gid, {
                wallpaper_mode: "single",
                wallpaper_source: raw.slice(7),
                wallpaper_collection: "",
              });
            } else {
              void store.groups.updateGroupBaseline(gid, {
                wallpaper_mode: "off",
                wallpaper_source: "",
                wallpaper_collection: "",
              });
            }
          }}
        >
          ${wpPoolOptions.map(
            (opt) => html`<option value=${opt.value} .selected=${live(opt.value === wpPoolCurrent)}>
              ${opt.label}
            </option>`,
          )}
        </select>`,
      })}
      ${h.renderLabeledSelect(
        "wallpaper_cycle_minutes",
        cfg.wallpaper_cycle_minutes,
        rotationOptions,
        "0",
        true,
      )}
      ${h.renderSpecSelect("screensaver_style", cfg.screensaver_style)}
      ${groupSsStyle === "Photo Frame"
        ? html`${renderSettingsRow({
              label: store.t("groups.screensaver_pool_label"),
              control: html`<select
                aria-label=${store.t("groups.for_group_aria", {
                  label: store.t("groups.screensaver_pool_label"),
                  group: group.name,
                })}
                .value=${live(ssPoolCurrent)}
                @change=${(ev: Event) => {
                  const raw = (ev.currentTarget as HTMLSelectElement).value;
                  if (raw.startsWith("collection:")) {
                    void store.groups.updateGroupBaseline(gid, {
                      screensaver_photo_mode: "collection",
                      screensaver_photo_collection: raw.slice(11),
                      screensaver_photo_source: "",
                    });
                  } else if (raw.startsWith("single:")) {
                    void store.groups.updateGroupBaseline(gid, {
                      screensaver_photo_mode: "single",
                      screensaver_photo_source: raw.slice(7),
                      screensaver_photo_collection: "",
                    });
                  } else {
                    void store.groups.updateGroupBaseline(gid, {
                      screensaver_photo_mode: "off",
                      screensaver_photo_source: "",
                      screensaver_photo_collection: "",
                    });
                  }
                }}
              >
                ${ssPoolOptions.map(
                  (opt) => html`<option
                    value=${opt.value}
                    .selected=${live(opt.value === ssPoolCurrent)}
                  >
                    ${opt.label}
                  </option>`,
                )}
              </select>`,
            })}
            ${h.renderLabeledSelect(
              "screensaver_cycle_minutes",
              cfg.screensaver_cycle_minutes,
              rotationOptions,
              "15",
              true,
            )}
            ${renderSwitchRow({
              label: store.tPrefLabel("screensaver_shuffle"),
              ariaLabel: store.t("groups.for_group_aria", {
                label: store.tPrefLabel("screensaver_shuffle"),
                group: group.name,
              }),
              checked: Boolean(cfg.screensaver_shuffle),
              onChange: (checked) =>
                void store.groups.updateGroupBaseline(gid, {
                  screensaver_shuffle: checked,
                }),
            })}
            ${h.renderSpecSwitch("screensaver_photo_clock", cfg.screensaver_photo_clock)}`
        : nothing}
      ${h.renderSpecSelect("color_profile", cfg.color_profile)}
      ${colorProfile === "Custom"
        ? renderSettingsRow({
            label: store.tPrefLabel("device_custom_color"),
            control: html`<input
                type="color"
                aria-label=${store.t("groups.for_group_aria", {
                  label: store.tPrefLabel("device_custom_color"),
                  group: group.name,
                })}
                .value=${live(customHex)}
                @change=${(ev: Event) => {
                  const raw = (ev.currentTarget as HTMLInputElement).value.toUpperCase();
                  if (isValidHexColor(raw)) {
                    void store.groups.updateGroupBaseline(gid, {
                      device_custom_color: raw,
                    });
                  }
                }}
              />
              <span class="chip">${customHex}</span>`,
          })
        : nothing}
      ${h.renderSpecSelect("glass_style", cfg.glass_style)}
      ${h.renderSpecSelect("va_visual_profile", cfg.va_visual_profile)}
    </div>
  </details>`;
}

function renderBaselineInterfaceSection(
  store: StudioStore,
  group: DeviceGroup,
  h: BaselineSectionHelpers,
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
      ${h.renderSpecSelect("return_to_home_timeout", cfg.return_to_home_timeout)}
      ${h.renderSpecSelect("time_format", cfg.time_format)}
      ${h.renderSpecSwitch("home_show_time", cfg.home_show_time)}
      ${cfg.home_show_time !== false
        ? h.renderSpecSelect("home_clock_tap_action", cfg.home_clock_tap_action)
        : nothing}
      ${h.renderSpecSelect("clock_face", cfg.clock_face)}
      ${h.renderSpecSwitch("home_show_date", cfg.home_show_date)}
      ${cfg.home_show_date !== false
        ? h.renderSpecSelect("home_date_tap_action", cfg.home_date_tap_action)
        : nothing}
      ${h.renderSpecSwitch("home_show_weather", cfg.home_show_weather)}
      ${cfg.home_show_weather !== false
        ? h.renderSpecSelect("home_weather_tap_action", cfg.home_weather_tap_action)
        : nothing}
      ${h.renderSpecSwitch("home_show_battery", cfg.home_show_battery)}
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
      ${h.renderSpecSelect("music_auto_open", cfg.music_auto_open)}
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
                  h.requestCopyKeys(
                    ["pinned_items", "pinned_page_titles"],
                    store.t("dialogs.pinned_label"),
                  )}
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

export function renderGroupBaselineDrawer(
  store: StudioStore,
  group: DeviceGroup,
  members: readonly SystemDeviceEntry[],
  latterDevices: readonly SystemDeviceEntry[],
): TemplateResult {
  const gid = group.id;
  const caps = deriveGroupCapabilities(group, members);
  const includeDisplay = Boolean(group.include_display);
  const includeInterface = Boolean(group.include_interface);
  const copySrc =
    store.groupCopySourceDrafts.get(gid) ||
    store.activeSubentryId ||
    latterDevices[0]?.subentry_id ||
    "";

  const helpers: BaselineSectionHelpers = {
    caps,
    hasLatterDevices: latterDevices.length > 0,
    renderSpecSelect: (key: string, currentVal: unknown) =>
      renderSpecSelect(store, group, key, currentVal, caps),
    renderSpecSwitch: (key: string, currentVal: unknown, extraGate = true) =>
      renderSpecSwitch(store, group, key, currentVal, caps, extraGate),
    renderSpecRange: (
      key: string,
      currentVal: unknown,
      fallbackBounds?: { min: number; max: number; step: number; unit: string; defaultVal: number },
    ) => renderSpecRange(store, group, key, currentVal, caps, fallbackBounds),
    renderSpecHourSelect: (key: string, currentVal: unknown) =>
      renderSpecHourSelect(store, group, key, currentVal, caps),
    renderLabeledSelect: (
      key: string,
      currentVal: unknown,
      options: ReadonlyArray<{ value: string; label: string }>,
      defaultVal: string,
      asNumber = false,
    ) =>
      renderBaselineLabeledSelect(store, group, key, currentVal, options, defaultVal, asNumber),
    renderPills: (
      key: string,
      currentVal: unknown,
      catalog: ReadonlyArray<CatalogItem>,
      defaultCsv: string,
      minRequired: number,
    ) => renderBaselinePills(store, group, key, currentVal, catalog, defaultCsv, minRequired, caps),
    requestCopyKeys: (copyKeys: string[], listLabel: string) =>
      requestCopyDeviceIntoGroup(
        store,
        group,
        members.length,
        copySrc,
        latterDevices,
        copyKeys,
        listLabel,
      ),
  };

  return html`<details
    ?open=${store.openGroupIds.has(gid)}
    @toggle=${(ev: Event) => {
      if (ev.target !== ev.currentTarget) return;
      const isOpen = (ev.currentTarget as HTMLDetailsElement).open;
      if (isOpen) store.openGroupIds.add(gid);
      else store.openGroupIds.delete(gid);
    }}
    class="sub-collapsible"
  >
    <summary>${store.t("groups.baseline_settings")}</summary>
    <div class="card-content stack">
      <div class="settings-list">
        ${renderSwitchRow({
          label: store.t("groups.include_display"),
          description: store.t("groups.include_display_desc"),
          ariaLabel: store.t("groups.for_group_aria", {
            label: store.t("groups.include_display"),
            group: group.name,
          }),
          checked: includeDisplay,
          onChange: (checked) =>
            void store.groups.updateGroupScope(gid, { include_display: checked }),
        })}
        ${renderSwitchRow({
          label: store.t("groups.include_interface"),
          description: store.t("groups.include_interface_desc"),
          ariaLabel: store.t("groups.for_group_aria", {
            label: store.t("groups.include_interface"),
            group: group.name,
          }),
          checked: includeInterface,
          onChange: (checked) =>
            void store.groups.updateGroupScope(gid, { include_interface: checked }),
        })}
      </div>

      ${renderBaselineBehaviorSection(store, group, helpers)}
      ${renderBaselineDisplaySection(store, group, helpers)}
      ${renderBaselineInterfaceSection(store, group, helpers)}

      ${latterDevices.length
        ? html`<div class="settings-list">
            <h3 class="subsection-title">${store.t("groups.copy_from_device")}</h3>
            ${renderSettingsRow({
              label: store.t("groups.source_device"),
              description: store.t("groups.source_device_desc"),
              control: html`<select
                  aria-label=${store.t("groups.copy_into_aria", { name: group.name })}
                  .value=${live(copySrc)}
                  @change=${(ev: Event) => {
                    store.groupCopySourceDrafts.set(
                      gid,
                      (ev.currentTarget as HTMLSelectElement).value,
                    );
                    store.host.requestUpdate();
                  }}
                >
                  ${latterDevices.map(
                    (d) =>
                      html`<option value=${d.subentry_id} .selected=${live(d.subentry_id === copySrc)}>
                        ${d.title}
                      </option>`,
                  )}
                </select>
                <button
                  type="button"
                  @click=${() =>
                    requestCopyDeviceIntoGroup(
                      store,
                      group,
                      members.length,
                      copySrc,
                      latterDevices,
                    )}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.t("groups.copy_settings")}
                </button>`,
            })}
          </div>`
        : nothing}
    </div>
  </details>`;
}
