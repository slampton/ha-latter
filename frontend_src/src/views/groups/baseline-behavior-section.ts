/**
 * Group Baseline Drawer — Behavior Sections (`views/groups/baseline-behavior-section.ts`):
 * - Power & brightness
 * - Audio & voice
 * - BLE & Area presence + Security PIN policy
 */

import { renderSwitchRow } from "../../components/controls.js";
import { SECURITY_PIN_POLICY_OPTIONS } from "../../i18n/index.js";
import { html, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import type { DeviceCapabilities, DeviceGroup } from "../../types.js";

export interface BaselineBehaviorHelpers {
  readonly caps: DeviceCapabilities;
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
}

export function renderBaselineBehaviorSection(
  store: StudioStore,
  group: DeviceGroup,
  h: BaselineBehaviorHelpers,
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
