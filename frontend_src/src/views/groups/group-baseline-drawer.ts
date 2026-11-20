/**
 * Group Baseline Drawer (`system_sync` Column 1, `D-048`, `D-050`, `D-063`, `D-064`).
 * - Zero hardcoded option arrays (`A-12`): reads options/bounds/defaults from `store.entity.getPrefSpec(key)`
 * - Localizes labels/options via `store.tPrefLabel` & `store.tPrefOption`
 * - Trait-gates group baseline rows (`E-14`) via single `isCatalogItemSupported` (`A-14`)
 * - Confirms `copyDeviceToGroupBaseline` (`Q5`)
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
  CALENDAR_LOOKAHEAD_OPTIONS,
  type CatalogItem,
  DEFAULT_ACTIVITY_SOURCES,
  DEFAULT_AREA_CATEGORIES,
  DEFAULT_DOCK_ROUTES_TOKENS,
  DEFAULT_GAMES_ITEMS,
  DEFAULT_HOME_CATEGORIES,
  DEFAULT_TOOLS_ITEMS,
  GAMES_ITEMS_CATALOG,
  HOME_CATEGORIES_CATALOG,
  SECURITY_PIN_POLICY_OPTIONS,
  TOOLS_ITEMS_CATALOG,
  VIRTUAL_COLLECTION_ALL,
  VIRTUAL_COLLECTION_DEFAULTS,
  VIRTUAL_COLLECTION_UPLOADS,
  WALLPAPER_ROTATION_OPTIONS,
} from "../../constants.js";
import { html, nothing, type TemplateResult } from "../../lib/lit.js";
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

function deriveGroupCapabilities(
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
    };
  }
  if (group.id === "handhelds") {
    return {
      has_display: true,
      is_round: false,
      has_imu: true,
      has_battery: true,
      has_ble_beacon: true,
      has_voice: true,
      has_audio: true,
      is_roaming_device: true,
      hw_jpeg: members.length > 0 ? members.some((m) => m.hw_jpeg === true) : true,
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
    };
  }
  if (members.length > 0) {
    return {
      has_display: members.some((m) => m.has_display !== false),
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
    typeof currentVal === "string" && options.includes(currentVal)
      ? currentVal
      : fallbackVal;
  const label = store.tPrefLabel(key, spec.label);
  return renderSettingsRow({
    label,
    control: html`<select
      aria-label=${store.t("groups.for_group_aria", { label, group: group.name })}
      .value=${cur}
      @change=${(ev: Event) =>
        void store.groups.updateGroupBaseline(group.id, {
          [key]: (ev.currentTarget as HTMLSelectElement).value,
        })}
    >
      ${options.map(
        (opt) => html`<option value=${opt} ?selected=${opt === cur}>
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
    onChange: (next) =>
      void store.groups.updateGroupBaseline(group.id, { [key]: next }),
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
      .value=${cur}
      @change=${(ev: Event) => {
        const raw = (ev.currentTarget as HTMLSelectElement).value;
        const val = asNumber ? Number(raw) || 0 : raw;
        void store.groups.updateGroupBaseline(group.id, { [key]: val });
      }}
    >
      ${options.map(
        (opt) =>
          html`<option value=${opt.value} ?selected=${opt.value === cur}>
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
      if (next.size <= minRequired) {
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

export function renderGroupBaselineDrawer(
  store: StudioStore,
  group: DeviceGroup,
  members: readonly SystemDeviceEntry[],
  latterDevices: readonly SystemDeviceEntry[],
): TemplateResult {
  const gid = group.id;
  const cfg = group.device_config || {};
  const caps = deriveGroupCapabilities(group, members);
  const includeDisplay = Boolean(group.include_display);
  const includeInterface = Boolean(group.include_interface);
  const autoBrt = String(cfg.auto_brightness_mode || "Sun Synchronized");
  const wwMode = String(cfg.wake_word_mode || "Docked Only");
  const bleOn = Boolean(cfg.native_ble_tracking);
  const autoSw = cfg.ble_auto_switch !== undefined ? Boolean(cfg.ble_auto_switch) : bleOn;
  const vfm = Boolean(cfg.sync_device_area);
  const handoff = Boolean(cfg.area_handoff);
  const pinPolicy = String(cfg.security_pin_policy || "auto");
  const colorProfile = String(cfg.color_profile || "Steel Blue");
  const rawCustomHex =
    typeof cfg.device_custom_color === "string" ? cfg.device_custom_color : null;
  const customHex = isValidHexColor(rawCustomHex)
    ? String(rawCustomHex).toUpperCase()
    : "#3898FF";
  const copySrc =
    store.groupCopySourceDrafts.get(gid) ||
    store.activeSubentryId ||
    latterDevices[0]?.subentry_id ||
    "";

  const sysWallpapers = store.state?.system_wallpapers || [];
  const photoCollections = store.state?.photo_collections || [];

  const buildCompactPoolOptions = (excludeDynamic: boolean): Array<{ value: string; label: string }> => {
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

  const encodePoolSelectValue = (
    modeVal: unknown,
    sourceVal: unknown,
    colVal: unknown,
  ): string => {
    const mode = String(modeVal || "");
    const src = String(sourceVal || "");
    const col = String(colVal || "");
    if (mode === "collection" && col) return `collection:${col}`;
    if (mode === "single" && src) return `single:${src}`;
    if (!mode && src) return `single:${src}`;
    return "off";
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
  const groupSsMode = String(cfg.screensaver_mode ?? "Docked Only");
  const groupSsStyle = String(cfg.screensaver_style ?? "Ambient Clock");
  const rotationOptions: Array<{ value: string; label: string }> = WALLPAPER_ROTATION_OPTIONS.map(
    (o) => ({ value: String(o.value), label: o.label }),
  );
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

      <details class="sub-collapsible" open>
        <summary>${store.t("groups.section_power_brightness")}</summary>
        <div class="card-content settings-list">
          ${renderSpecSelect(store, group, "tap_to_wake", cfg.tap_to_wake, caps)}
          ${renderSpecSelect(store, group, "pickup_to_wake", cfg.pickup_to_wake, caps)}
          ${renderSpecSelect(
            store,
            group,
            "battery_screen_timeout",
            cfg.battery_screen_timeout,
            caps,
          )}
          ${renderSpecSelect(
            store,
            group,
            "battery_hibernate_timeout",
            cfg.battery_hibernate_timeout,
            caps,
          )}
          ${renderSpecSelect(store, group, "screensaver_mode", cfg.screensaver_mode, caps)}
          ${caps.has_battery !== false || groupSsMode !== "Never"
            ? renderSpecSelect(store, group, "docked_idle_timeout", cfg.docked_idle_timeout, caps)
            : nothing}
          ${renderSpecSwitch(
            store,
            group,
            "hold_crown_power_off",
            cfg.hold_crown_power_off,
            caps,
            caps.has_battery !== false,
          )}
          ${renderSpecSelect(
            store,
            group,
            "auto_brightness_mode",
            cfg.auto_brightness_mode,
            caps,
          )}
          ${autoBrt === "Disabled"
            ? renderSpecRange(store, group, "manual_brightness", cfg.manual_brightness, caps)
            : html`${renderSpecRange(store, group, "day_brightness", cfg.day_brightness, caps)}
                ${renderSpecRange(
                  store,
                  group,
                  "night_brightness",
                  cfg.night_brightness,
                  caps,
                )}`}
          ${autoBrt === "Time Schedule"
            ? html`${renderSpecHourSelect(store, group, "day_start_hour", cfg.day_start_hour, caps)}
                ${renderSpecHourSelect(store, group, "night_start_hour", cfg.night_start_hour, caps)}`
            : nothing}
          ${renderSpecSelect(store, group, "bedtime_display", cfg.bedtime_display, caps)}
          ${renderSpecRange(store, group, "bedtime_brightness", cfg.bedtime_brightness, caps)}
          ${renderSpecSwitch(store, group, "bedtime_schedule", cfg.bedtime_schedule, caps)}
          ${Boolean(cfg.bedtime_schedule)
            ? html`${renderSpecHourSelect(
                  store,
                  group,
                  "bedtime_start_hour",
                  cfg.bedtime_start_hour,
                  caps,
                )}
                ${renderSpecHourSelect(
                  store,
                  group,
                  "bedtime_end_hour",
                  cfg.bedtime_end_hour,
                  caps,
                )}`
            : nothing}
        </div>
      </details>

      <details class="sub-collapsible">
        <summary>${store.t("groups.section_audio_voice")}</summary>
        <div class="card-content settings-list">
          ${renderSpecSelect(store, group, "wake_word_mode", cfg.wake_word_mode, caps)}
          ${wwMode !== "Disabled"
            ? html`${renderSpecSelect(
                  store,
                  group,
                  "ww_sens_okay_nabu",
                  cfg.ww_sens_okay_nabu,
                  caps,
                )}
                ${renderSpecSelect(
                  store,
                  group,
                  "ww_sens_hey_luna",
                  cfg.ww_sens_hey_luna,
                  caps,
                )}
                ${renderSpecSelect(
                  store,
                  group,
                  "ww_sens_hey_jarvis",
                  cfg.ww_sens_hey_jarvis,
                  caps,
                )}
                ${renderSpecSelect(
                  store,
                  group,
                  "ww_sens_hey_mycroft",
                  cfg.ww_sens_hey_mycroft,
                  caps,
                )}
                ${renderSpecSelect(store, group, "ww_sens_alexa", cfg.ww_sens_alexa, caps)}`
            : nothing}
          ${renderSpecSwitch(
            store,
            group,
            "wake_screen_on_assist",
            cfg.wake_screen_on_assist,
            caps,
          )}
          ${renderSpecRange(store, group, "alert_volume", cfg.alert_volume, caps)}
          ${renderSpecRange(store, group, "volume_step_size", cfg.volume_step_size, caps)}
          ${renderSpecSwitch(store, group, "game_sound_effects", cfg.game_sound_effects, caps)}
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
                  ? renderSpecRange(
                      store,
                      group,
                      "area_follow_dwell_s",
                      cfg.area_follow_dwell_s,
                      caps,
                      { min: 3, max: 60, step: 1, unit: "s", defaultVal: 10 },
                    )
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
                ${renderSpecSelect(store, group, "ble_beacon_mode", cfg.ble_beacon_mode, caps)}`
            : nothing}
          ${renderBaselineLabeledSelect(
            store,
            group,
            "security_pin_policy",
            pinPolicy,
            SECURITY_PIN_POLICY_OPTIONS.map((opt) => ({
              value: opt.value,
              label: store.tPrefOption("security_pin_policy", opt.value),
            })),
            "auto",
          )}
        </div>
      </details>

      ${includeDisplay && caps.has_display !== false
        ? html`<details class="sub-collapsible" open>
            <summary>${store.t("groups.section_display")}</summary>
            <div class="card-content settings-list">
              ${renderSettingsRow({
                label: store.t("groups.wallpaper_pool_label"),
                control: html`<select
                  aria-label=${store.t("groups.for_group_aria", {
                    label: store.t("groups.wallpaper_pool_label"),
                    group: group.name,
                  })}
                  .value=${wpPoolCurrent}
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
                    (opt) => html`<option value=${opt.value} ?selected=${opt.value === wpPoolCurrent}>
                      ${opt.label}
                    </option>`,
                  )}
                </select>`,
              })}
              ${renderBaselineLabeledSelect(
                store,
                group,
                "wallpaper_cycle_minutes",
                cfg.wallpaper_cycle_minutes,
                rotationOptions,
                "0",
                true,
              )}
              ${renderSpecSelect(store, group, "screensaver_style", cfg.screensaver_style, caps)}
              ${groupSsStyle === "Photo Frame"
                ? html`${renderSettingsRow({
                      label: store.t("groups.screensaver_pool_label"),
                      control: html`<select
                        aria-label=${store.t("groups.for_group_aria", {
                          label: store.t("groups.screensaver_pool_label"),
                          group: group.name,
                        })}
                        .value=${ssPoolCurrent}
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
                            ?selected=${opt.value === ssPoolCurrent}
                          >
                            ${opt.label}
                          </option>`,
                        )}
                      </select>`,
                    })}
                    ${renderBaselineLabeledSelect(
                      store,
                      group,
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
                    ${renderSpecSwitch(
                      store,
                      group,
                      "screensaver_photo_clock",
                      cfg.screensaver_photo_clock,
                      caps,
                    )}`
                : nothing}
              ${renderSpecSelect(store, group, "color_profile", cfg.color_profile, caps)}
              ${colorProfile === "Custom"
                ? renderSettingsRow({
                    label: store.tPrefLabel("device_custom_color"),
                    control: html`<input
                        type="color"
                        aria-label=${store.t("groups.for_group_aria", {
                          label: store.tPrefLabel("device_custom_color"),
                          group: group.name,
                        })}
                        .value=${customHex}
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
              ${renderSpecSelect(store, group, "va_visual_profile", cfg.va_visual_profile, caps)}
            </div>
          </details>`
        : nothing}

      ${includeInterface && caps.has_display !== false
        ? html`<details class="sub-collapsible" open>
            <summary>${store.t("groups.section_interface")}</summary>
            <div class="card-content settings-list">
              ${renderSpecSwitch(
                store,
                group,
                "home_screen_enabled",
                cfg.home_screen_enabled,
                caps,
              )}
              ${renderSpecSelect(store, group, "start_screen", cfg.start_screen, caps)}
              ${renderSpecSelect(store, group, "time_format", cfg.time_format, caps)}
              ${renderSpecSelect(
                store,
                group,
                "home_clock_tap_action",
                cfg.home_clock_tap_action,
                caps,
              )}
              ${renderSpecSelect(store, group, "clock_face", cfg.clock_face, caps)}
              ${renderSpecSelect(
                store,
                group,
                "home_date_tap_action",
                cfg.home_date_tap_action,
                caps,
              )}
              ${renderSpecSelect(
                store,
                group,
                "return_to_home_timeout",
                cfg.return_to_home_timeout,
                caps,
              )}
              ${renderSpecSwitch(store, group, "wake_greeting", cfg.wake_greeting, caps)}
              ${renderSpecSwitch(
                store,
                group,
                "weather_background",
                cfg.weather_background,
                caps,
              )}
              ${renderSpecSwitch(
                store,
                group,
                "weather_app_background",
                cfg.weather_app_background,
                caps,
              )}
              ${renderSpecSwitch(store, group, "home_sun", cfg.home_sun, caps)}
              ${renderSpecSwitch(store, group, "home_moon", cfg.home_moon, caps)}
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
              ${renderBaselinePills(
                store,
                group,
                "activity_sources",
                cfg.activity_sources,
                ACTIVITY_SOURCES_CATALOG,
                DEFAULT_ACTIVITY_SOURCES,
                0,
                caps,
              )}
              ${renderBaselinePills(
                store,
                group,
                "home_categories",
                cfg.home_categories,
                HOME_CATEGORIES_CATALOG,
                DEFAULT_HOME_CATEGORIES,
                1,
                caps,
              )}
              ${renderBaselinePills(
                store,
                group,
                "area_categories",
                cfg.area_categories,
                AREA_CATEGORIES_CATALOG,
                DEFAULT_AREA_CATEGORIES,
                1,
                caps,
              )}
              ${renderBaselinePills(
                store,
                group,
                "tools_items",
                cfg.tools_items,
                TOOLS_ITEMS_CATALOG,
                DEFAULT_TOOLS_ITEMS,
                1,
                caps,
              )}
              ${renderBaselinePills(
                store,
                group,
                "games_items",
                cfg.games_items,
                GAMES_ITEMS_CATALOG,
                DEFAULT_GAMES_ITEMS,
                1,
                caps,
              )}
              ${renderBaselineLabeledSelect(
                store,
                group,
                "device_remote_group",
                cfg.device_remote_group,
                remoteScopeOptions,
                "area_auto",
              )}
              ${renderSpecSwitch(store, group, "show_utc_clock", cfg.show_utc_clock, caps)}
              ${renderBaselineLabeledSelect(
                store,
                group,
                "calendar_lookahead_days",
                cfg.calendar_lookahead_days ?? 30,
                lookaheadOptions,
                "30",
                true,
              )}
              ${renderSpecSelect(
                store,
                group,
                "calendar_week_start",
                cfg.calendar_week_start,
                caps,
              )}
              ${renderSpecSelect(store, group, "album_art_style", cfg.album_art_style, caps)}
              ${renderSpecSelect(
                store,
                group,
                "music_overlay_style",
                cfg.music_overlay_style,
                caps,
              )}
              ${renderSpecSelect(store, group, "album_sort_order", cfg.album_sort_order, caps)}
              ${renderSpecSelect(
                store,
                group,
                "artist_album_sort_order",
                cfg.artist_album_sort_order,
                caps,
              )}
              ${renderSpecSelect(
                store,
                group,
                "podcast_sort_order",
                cfg.podcast_sort_order,
                caps,
              )}
              ${renderSpecSelect(
                store,
                group,
                "camera_default_view",
                cfg.camera_default_view,
                caps,
              )}
              ${renderSpecSelect(store, group, "camera_framing", cfg.camera_framing, caps)}
              ${renderSpecSelect(
                store,
                group,
                "camera_carousel_interval",
                cfg.camera_carousel_interval,
                caps,
              )}
              ${renderSpecSelect(
                store,
                group,
                "camera_stream_mode",
                cfg.camera_stream_mode,
                caps,
              )}
              ${renderSpecSelect(
                store,
                group,
                "camera_doorbell_popup",
                cfg.camera_doorbell_popup,
                caps,
              )}
              ${latterDevices.length
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
                        @click=${() =>
                          requestCopyDeviceIntoGroup(
                            store,
                            group,
                            members.length,
                            copySrc,
                            latterDevices,
                            ["dock_items"],
                            store.t("card.app_dock"),
                          )}
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
                          requestCopyDeviceIntoGroup(
                            store,
                            group,
                            members.length,
                            copySrc,
                            latterDevices,
                            ["pinned_items"],
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
                          requestCopyDeviceIntoGroup(
                            store,
                            group,
                            members.length,
                            copySrc,
                            latterDevices,
                            ["world_clocks"],
                            store.t("dialogs.world_clocks_label"),
                          )}
                        class="btn btn-secondary btn-compact"
                      >
                        ${store.t("groups.copy_clocks")}
                      </button>`,
                    })}`
                : nothing}
            </div>
          </details>`
        : nothing}

      ${latterDevices.length
        ? html`<div class="settings-list">
            <div class="subsection-title">${store.t("groups.copy_from_device")}</div>
            ${renderSettingsRow({
              label: store.t("groups.source_device"),
              description: store.t("groups.source_device_desc"),
              control: html`<select
                  aria-label=${store.t("groups.copy_into_aria", { name: group.name })}
                  .value=${copySrc}
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
                      html`<option value=${d.subentry_id} ?selected=${d.subentry_id === copySrc}>
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
