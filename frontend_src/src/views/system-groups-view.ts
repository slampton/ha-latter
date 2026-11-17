/**
 * System Device Groups & Batch Controls View (`system_sync`, D-047):
 * Column 1: Enclosed per-Group containers with inline expandable Baseline Settings.
 * Column 2: Dedicated one-off Batch Controls across All, Roaming, Stationary, or populated Groups.
 */

import {
  renderCard,
  renderSettingsRow,
  renderSwitchRow,
  renderTrashIconButton,
} from "../components/controls.js";
import {
  DEFAULT_DEVICE_GROUP_IDS,
  POWER_PROFILE_PREFS,
  SECURITY_PIN_POLICY_OPTIONS,
} from "../constants.js";
import { html, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { DeviceGroup, SharedControlItem } from "../types.js";
import { entityLabel, fmtNumber } from "../utils/format.js";

const POWER_PROFILE_OPTIONS: ReadonlyArray<string> = [
  ...Object.keys(POWER_PROFILE_PREFS),
  "Custom",
];
const WAKE_WORD_MODE_OPTIONS: ReadonlyArray<string> = ["Docked Only", "Always On", "Disabled"];
const TAP_TO_WAKE_OPTIONS: ReadonlyArray<string> = [
  "Single Tap",
  "Double Tap",
  "Docked Only",
  "Disabled",
];
const WAKE_GESTURE_OPTIONS: ReadonlyArray<string> = ["Always On", "Docked Only", "Disabled"];
const BATTERY_SCREEN_TIMEOUT_OPTIONS: ReadonlyArray<string> = [
  "10s",
  "15s",
  "30s",
  "1 min",
  "2 min",
  "Never",
];
const DOCKED_IDLE_TIMEOUT_OPTIONS: ReadonlyArray<string> = [
  "10s",
  "15s",
  "30s",
  "1 min",
  "2 min",
  "5 min",
  "Never",
];
const BATTERY_HIBERNATE_TIMEOUT_OPTIONS: ReadonlyArray<string> = [
  "5 min",
  "10 min",
  "15 min",
  "30 min",
  "Disabled",
];
const AUTO_BRIGHTNESS_MODE_OPTIONS: ReadonlyArray<string> = [
  "Disabled",
  "Sun Synchronized",
  "Time Schedule",
];
const BRIGHTNESS_PCT_OPTIONS: ReadonlyArray<string> = ["60%", "70%", "80%", "90%", "100%"];
const WW_SENSITIVITY_OPTIONS: ReadonlyArray<string> = [
  "Slightly sensitive",
  "Moderately sensitive",
  "Very sensitive",
];
const BLE_BEACON_MODE_OPTIONS: ReadonlyArray<string> = [
  "Handheld Only",
  "Handheld + Screen Off",
  "Always",
];

function renderBaselineSelect(
  store: StudioStore,
  groupId: string,
  key: string,
  label: string,
  currentVal: unknown,
  options: ReadonlyArray<string>,
  defaultVal: string,
): TemplateResult {
  const cur = typeof currentVal === "string" && options.includes(currentVal) ? currentVal : defaultVal;
  return renderSettingsRow({
    label,
    control: html`<select
      aria-label=${`${label} for ${groupId}`}
      .value=${cur}
      @change=${(ev: Event) =>
        void store.updateGroupBaseline(groupId, {
          [key]: (ev.currentTarget as HTMLSelectElement).value,
        })}
    >
      ${options.map(
        (opt) => html`<option value=${opt} ?selected=${opt === cur}>${opt}</option>`,
      )}
    </select>`,
  });
}

function renderBaselineRange(
  store: StudioStore,
  groupId: string,
  key: string,
  label: string,
  currentVal: unknown,
  min: number,
  max: number,
  step: number,
  unit: string,
  defaultVal: number,
): TemplateResult {
  const numVal = Number.isFinite(Number(currentVal)) ? Number(currentVal) : defaultVal;
  return renderSettingsRow({
    label,
    control: html`<span class="kv-value">${fmtNumber(numVal, store.hass, 0)}${unit ? ` ${unit}` : ""}</span>
      <input
        type="range"
        aria-label=${`${label} for ${groupId}`}
        min=${String(min)}
        max=${String(max)}
        step=${String(step)}
        .value=${String(numVal)}
        @change=${(ev: Event) =>
          void store.updateGroupBaseline(groupId, {
            [key]: Number((ev.currentTarget as HTMLInputElement).value),
          })}
      />`,
  });
}

function renderGroupBaselineDrawer(
  store: StudioStore,
  group: DeviceGroup,
  latterDevices: ReadonlyArray<{ subentry_id: string; title: string }>,
): TemplateResult {
  const gid = group.id;
  const cfg = group.device_config || {};
  const autoBrt = String(cfg.auto_brightness_mode || "Sun Synchronized");
  const wwMode = String(cfg.wake_word_mode || "Docked Only");
  const bleOn = Boolean(cfg.native_ble_tracking);
  const autoSw = cfg.ble_auto_switch !== undefined ? Boolean(cfg.ble_auto_switch) : bleOn;
  const vfm = Boolean(cfg.sync_device_area);
  const handoff = Boolean(cfg.area_handoff);
  const pinPolicy = String(cfg.security_pin_policy || "auto");
  const copySrc =
    store.groupCopySourceDrafts?.get(gid) ||
    store.activeSubentryId ||
    latterDevices[0]?.subentry_id ||
    "";

  return html`<details
    ?open=${Boolean(store.openGroupIds?.has(gid))}
    @toggle=${(ev: Event) => {
      const isOpen = (ev.currentTarget as HTMLDetailsElement).open;
      if (isOpen) store.openGroupIds?.add(gid);
      else store.openGroupIds?.delete(gid);
    }}
    class="sub-collapsible"
  >
    <summary>Baseline Settings</summary>
    <div class="card-content settings-list">
      <div class="subsection-title">Power &amp; Sleep</div>
      ${renderBaselineSelect(
        store,
        gid,
        "power_profile",
        "Power Profile",
        cfg.power_profile,
        POWER_PROFILE_OPTIONS,
        "Portable Carry",
      )}
      ${renderBaselineSelect(
        store,
        gid,
        "tap_to_wake",
        "Tap to Wake",
        cfg.tap_to_wake,
        TAP_TO_WAKE_OPTIONS,
        "Docked Only",
      )}
      ${renderBaselineSelect(
        store,
        gid,
        "pickup_to_wake",
        "Pickup to Wake",
        cfg.pickup_to_wake,
        WAKE_GESTURE_OPTIONS,
        "Docked Only",
      )}
      ${renderBaselineSelect(
        store,
        gid,
        "battery_screen_timeout",
        "Battery Screen Timeout",
        cfg.battery_screen_timeout,
        BATTERY_SCREEN_TIMEOUT_OPTIONS,
        "30s",
      )}
      ${renderBaselineSelect(
        store,
        gid,
        "battery_hibernate_timeout",
        "Battery Hibernate Timeout",
        cfg.battery_hibernate_timeout,
        BATTERY_HIBERNATE_TIMEOUT_OPTIONS,
        "15 min",
      )}
      ${renderSwitchRow({
        label: "Docked Screensaver",
        ariaLabel: `Docked Screensaver for ${gid}`,
        checked: cfg.docked_screensaver !== false,
        onChange: (checked) => void store.updateGroupBaseline(gid, { docked_screensaver: checked }),
      })}
      ${renderBaselineSelect(
        store,
        gid,
        "docked_idle_timeout",
        "Docked Idle Timeout",
        cfg.docked_idle_timeout,
        DOCKED_IDLE_TIMEOUT_OPTIONS,
        "1 min",
      )}
      ${renderSwitchRow({
        label: "Hold Crown to Power Off",
        ariaLabel: `Hold Crown to Power Off for ${gid}`,
        checked: Boolean(cfg.hold_crown_power_off),
        onChange: (checked) =>
          void store.updateGroupBaseline(gid, { hold_crown_power_off: checked }),
      })}

      <div class="subsection-title">Voice &amp; Sound</div>
      ${renderBaselineSelect(
        store,
        gid,
        "wake_word_mode",
        "Wake Word Mode",
        cfg.wake_word_mode,
        WAKE_WORD_MODE_OPTIONS,
        "Docked Only",
      )}
      ${wwMode !== "Disabled"
        ? html`${renderBaselineSelect(
              store,
              gid,
              "ww_sens_okay_nabu",
              "Okay Nabu Sensitivity",
              cfg.ww_sens_okay_nabu,
              WW_SENSITIVITY_OPTIONS,
              "Moderately sensitive",
            )}
            ${renderBaselineSelect(
              store,
              gid,
              "ww_sens_hey_luna",
              "Hey Luna Sensitivity",
              cfg.ww_sens_hey_luna,
              WW_SENSITIVITY_OPTIONS,
              "Moderately sensitive",
            )}
            ${renderBaselineSelect(
              store,
              gid,
              "ww_sens_hey_jarvis",
              "Hey Jarvis Sensitivity",
              cfg.ww_sens_hey_jarvis,
              WW_SENSITIVITY_OPTIONS,
              "Moderately sensitive",
            )}
            ${renderBaselineSelect(
              store,
              gid,
              "ww_sens_hey_mycroft",
              "Hey Mycroft Sensitivity",
              cfg.ww_sens_hey_mycroft,
              WW_SENSITIVITY_OPTIONS,
              "Moderately sensitive",
            )}
            ${renderBaselineSelect(
              store,
              gid,
              "ww_sens_alexa",
              "Alexa Sensitivity",
              cfg.ww_sens_alexa,
              WW_SENSITIVITY_OPTIONS,
              "Moderately sensitive",
            )}`
        : nothing}
      ${renderSwitchRow({
        label: "Wake Screen on Assist",
        ariaLabel: `Wake Screen on Assist for ${gid}`,
        checked: cfg.wake_screen_on_assist !== false,
        onChange: (checked) =>
          void store.updateGroupBaseline(gid, { wake_screen_on_assist: checked }),
      })}
      ${renderBaselineRange(store, gid, "alert_volume", "Alert Volume", cfg.alert_volume, 20, 100, 5, "%", 80)}
      ${renderBaselineRange(store, gid, "volume_step_size", "Volume Step Size", cfg.volume_step_size, 1, 10, 1, "%", 5)}
      ${renderSwitchRow({
        label: "Game Sound Effects",
        ariaLabel: `Game Sound Effects for ${gid}`,
        checked: cfg.game_sound_effects !== false,
        onChange: (checked) =>
          void store.updateGroupBaseline(gid, { game_sound_effects: checked }),
      })}

      <div class="subsection-title">Brightness</div>
      ${renderBaselineSelect(
        store,
        gid,
        "auto_brightness_mode",
        "Auto Brightness Mode",
        cfg.auto_brightness_mode,
        AUTO_BRIGHTNESS_MODE_OPTIONS,
        "Sun Synchronized",
      )}
      ${autoBrt === "Disabled"
        ? renderBaselineSelect(
            store,
            gid,
            "manual_brightness",
            "Manual Brightness",
            cfg.manual_brightness,
            BRIGHTNESS_PCT_OPTIONS,
            "90%",
          )
        : html`${renderBaselineSelect(
              store,
              gid,
              "day_brightness",
              "Day Brightness",
              cfg.day_brightness,
              BRIGHTNESS_PCT_OPTIONS,
              "90%",
            )}
            ${renderBaselineSelect(
              store,
              gid,
              "night_brightness",
              "Night Brightness",
              cfg.night_brightness,
              BRIGHTNESS_PCT_OPTIONS,
              "70%",
            )}`}
      ${autoBrt === "Time Schedule"
        ? html`${renderBaselineRange(
              store,
              gid,
              "day_start_hour",
              "Day Start Hour",
              cfg.day_start_hour,
              0,
              23,
              1,
              "h",
              7,
            )}
            ${renderBaselineRange(
              store,
              gid,
              "night_start_hour",
              "Night Start Hour",
              cfg.night_start_hour,
              0,
              23,
              1,
              "h",
              20,
            )}`
        : nothing}

      <div class="subsection-title">Area &amp; Security</div>
      ${renderSwitchRow({
        label: "Track the Area with BLE Proxies",
        ariaLabel: `Track the Area with BLE Proxies for ${gid}`,
        checked: bleOn,
        onChange: (checked) =>
          void store.updateGroupBaseline(gid, { native_ble_tracking: checked }),
      })}
      ${bleOn
        ? html`${renderSwitchRow({
              label: "Auto-Switch Active Area",
              ariaLabel: `Auto-Switch Active Area for ${gid}`,
              checked: autoSw,
              onChange: (checked) =>
                void store.updateGroupBaseline(gid, { ble_auto_switch: checked }),
            })}
            ${renderSwitchRow({
              label: "Voice Follows Me",
              ariaLabel: `Voice Follows Me for ${gid}`,
              checked: vfm,
              onChange: (checked) =>
                void store.updateGroupBaseline(gid, { sync_device_area: checked }),
            })}
            ${vfm
              ? renderBaselineRange(
                  store,
                  gid,
                  "area_follow_dwell_s",
                  "Area Follow Dwell",
                  cfg.area_follow_dwell_s,
                  3,
                  60,
                  1,
                  "s",
                  10,
                )
              : nothing}
            ${renderBaselineSelect(
              store,
              gid,
              "ble_beacon_mode",
              "BLE Beacon Mode",
              cfg.ble_beacon_mode,
              BLE_BEACON_MODE_OPTIONS,
              "Handheld Only",
            )}`
        : nothing}
      ${renderSwitchRow({
        label: "Media Follows Device to New Area",
        ariaLabel: `Media Follows Device to New Area for ${gid}`,
        checked: handoff,
        onChange: (checked) => void store.updateGroupBaseline(gid, { area_handoff: checked }),
      })}
      ${renderSettingsRow({
        label: "Perimeter Security Policy",
        control: html`<select
          aria-label=${`Perimeter Security Policy for ${gid}`}
          .value=${pinPolicy}
          @change=${(ev: Event) =>
            void store.updateGroupBaseline(gid, {
              security_pin_policy: (ev.currentTarget as HTMLSelectElement).value,
            })}
        >
          ${SECURITY_PIN_POLICY_OPTIONS.map(
            (opt) =>
              html`<option value=${opt.value} ?selected=${opt.value === pinPolicy}>
                ${opt.label}
              </option>`,
          )}
        </select>`,
      })}

      ${latterDevices.length
        ? html`<div class="subsection-title">Copy From Device</div>
            ${renderSettingsRow({
              label: "Source Device",
              description: "Replaces this group's baseline with an existing Device's operational settings.",
              control: html`<select
                  aria-label=${`Copy settings into ${group.name}`}
                  .value=${copySrc}
                  @change=${(ev: Event) => {
                    store.groupCopySourceDrafts?.set(
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
                  @click=${() => void store.copyDeviceToGroupBaseline(gid, copySrc)}
                  class="btn btn-secondary btn-compact"
                >
                  Copy Settings
                </button>`,
            })}`
        : nothing}
    </div>
  </details>`;
}

export function renderSystemGroupsView(store: StudioStore): TemplateResult {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const latterDevices = allDevices.filter((d) => d.kind !== "ble_tag");
  const groups = data?.device_groups || [];
  const systemControls = data?.system_controls || [];

  const activeFilter = store.batchTargetFilter || "all";
  const activeTargetId = store.resolvedBatchTargetId();
  const activeCat = store.batchCategoryFilter || "all";

  const populatedGroups = groups.filter((g) =>
    latterDevices.some((d) => d.device_group === g.id),
  );

  const matchingDevs = latterDevices.filter((d) => {
    if (activeTargetId === "all") return true;
    if (activeTargetId === "roaming") return Boolean(d.is_roaming);
    if (activeTargetId === "stationary") return !d.is_roaming;
    return d.device_group === activeTargetId;
  });

  const bleStates = matchingDevs.map((d) => Boolean(d.ble_tracked));
  const bleMixed = new Set(bleStates).size > 1;
  const bleOn = matchingDevs.length > 0 && bleStates.every(Boolean);

  const renderBatchControlRow = (fc: SharedControlItem): TemplateResult | typeof nothing => {
    if (activeCat !== "all" && fc.section !== activeCat) return nothing;
    const targets = (fc.targets || []).filter((t) => {
      if (activeTargetId === "all") return true;
      if (activeTargetId === "roaming") return Boolean(t.is_roaming);
      if (activeTargetId === "stationary") return !t.is_roaming;
      return t.device_group === activeTargetId;
    });
    if (!targets.length) return nothing;

    const states = Array.from(new Set(targets.map((t) => String(t.state ?? ""))));
    const mixed = states.length > 1;
    const curState = mixed ? "" : (states[0] ?? "");
    const desc = `${fc.section_title} • ${fmtNumber(targets.length, store.hass, 0)} Device${targets.length === 1 ? "" : "s"}${mixed ? " • Mixed values" : ""}`;

    let control: TemplateResult;
    if (fc.domain === "select" && fc.options && fc.options.length) {
      control = html`<select
        aria-label=${fc.name}
        .value=${curState}
        @change=${(ev: Event) =>
          void store.bulkSelect(fc, (ev.currentTarget as HTMLSelectElement).value)}
      >
        ${mixed ? html`<option value="" selected disabled>Mixed</option>` : nothing}
        ${fc.options.map(
          (opt) => html`<option value=${opt} ?selected=${opt === curState}>${opt}</option>`,
        )}
      </select>`;
    } else if (fc.domain === "switch") {
      control = html`${mixed ? html`<span class="chip">Mixed</span>` : nothing}
        <input
          type="checkbox"
          role="switch"
          aria-label=${fc.name}
          .checked=${curState === "on"}
          @change=${(ev: Event) =>
            void store.bulkToggle(fc, (ev.currentTarget as HTMLInputElement).checked)}
          class="switch"
        />`;
    } else if (fc.domain === "number") {
      const numVal = mixed ? (fc.min ?? 0) : Number(curState) || 0;
      control = html`<input
          type="range"
          aria-label=${fc.name}
          min=${String(fc.min ?? 0)}
          max=${String(fc.max ?? 100)}
          step=${String(fc.step ?? 1)}
          .value=${String(numVal)}
          @change=${(ev: Event) =>
            void store.bulkNumber(fc, Number((ev.currentTarget as HTMLInputElement).value))}
        />
        <span class="chip">
          ${mixed ? "Mixed" : `${curState} ${fc.unit || ""}`.trim()}
        </span>`;
    } else {
      control = html`<span class="chip">${mixed ? "Mixed" : curState}</span>`;
    }

    return renderSettingsRow({ label: entityLabel(fc.name), description: desc, control });
  };

  const behaviorControls = systemControls.filter((fc) => fc.tier !== "appearance");
  const appearanceControls = systemControls.filter((fc) => fc.tier === "appearance");

  return html`<section id="view-system_sync">
    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-device-groups",
          title: "Device Groups",
          subtitle:
            "Reusable operational presets applied to assigned Devices without overwriting personal appearance.",
          contentClass: "stack",
          body: html`<div class="list-block">
              <div class="list-row-main">
                <div class="stacked-field">
                  <label for="new-group-name">Group Name</label>
                  <input
                    type="text"
                    id="new-group-name"
                    placeholder="e.g. Guest Suites"
                    .value=${store.newGroupName}
                    @input=${(ev: Event) => {
                      store.newGroupName = (ev.currentTarget as HTMLInputElement).value;
                    }}
                  />
                </div>
                <div class="stacked-field">
                  <label for="new-group-desc">Description (Optional)</label>
                  <input
                    type="text"
                    id="new-group-desc"
                    placeholder="Optional description"
                    .value=${store.newGroupDesc}
                    @input=${(ev: Event) => {
                      store.newGroupDesc = (ev.currentTarget as HTMLInputElement).value;
                    }}
                  />
                </div>
              </div>
              <div class="input-action-row">
                <select
                  id="new-group-source"
                  aria-label="Copy settings from Device"
                  .value=${store.newGroupSourceSubentryId}
                  @change=${(ev: Event) => {
                    store.newGroupSourceSubentryId = (ev.currentTarget as HTMLSelectElement).value;
                  }}
                >
                  <option value="" ?selected=${!store.newGroupSourceSubentryId}>
                    Start from default settings
                  </option>
                  ${latterDevices.map(
                    (d) =>
                      html`<option
                        value=${d.subentry_id}
                        ?selected=${d.subentry_id === store.newGroupSourceSubentryId}
                      >
                        Copy from: ${d.title}
                      </option>`,
                  )}
                </select>
                <button
                  type="button"
                  id="btn-create-device-group"
                  @click=${() => void store.createDeviceGroup()}
                  class="btn btn-primary"
                >
                  Create Group
                </button>
              </div>
            </div>

            <div id="device-groups-list" class="stack">
              ${groups.length
                ? repeat(
                    groups,
                    (g) => g.id,
                    (g) => {
                      const members = latterDevices.filter((d) => d.device_group === g.id);
                      const isDefault =
                        DEFAULT_DEVICE_GROUP_IDS.has(g.id) || Boolean(g.builtin);
                      const metaParts = [
                        g.description || "",
                        members.length
                          ? `Devices: ${members.map((m) => m.title).join(", ")}`
                          : "No Devices assigned",
                      ].filter(Boolean);

                      return html`<div id=${`group-box-${g.id}`} class="area-presence-box">
                        <div class="area-box-head">
                          <div class="area-box-heading">
                            <span class="area-box-title">${g.name}</span>
                            <span class="chip ${members.length ? "chip-primary" : ""}">
                              ${fmtNumber(members.length, store.hass, 0)}
                              ${members.length === 1 ? "Device" : "Devices"}
                            </span>
                          </div>
                          <div class="area-box-actions">
                            ${members.length
                              ? html`<button
                                  type="button"
                                  @click=${() => store.openDevicesWithCategory(`group:${g.id}`)}
                                  class="btn btn-text btn-compact"
                                >
                                  View Devices
                                </button>`
                              : nothing}
                            ${!isDefault
                              ? renderTrashIconButton(`Delete group ${g.name}`, () =>
                                  void store.deleteDeviceGroup(g.id),
                                )
                              : nothing}
                          </div>
                        </div>

                        <div class="area-box-meta">${metaParts.join(" • ")}</div>

                        ${renderGroupBaselineDrawer(store, g, latterDevices)}
                      </div>`;
                    },
                  )
                : html`<p class="empty-state">No Device Groups configured.</p>`}
            </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-batch-controls",
          title: "Batch Controls",
          subtitle:
            "Applies a one-time setting change across matching Devices without altering saved Group baselines.",
          headerActions: html`<select
              id="batch-target-filter"
              aria-label="Target Devices for Batch Controls"
              .value=${activeFilter}
              @change=${(ev: Event) => {
                store.batchTargetFilter =
                  (ev.currentTarget as HTMLSelectElement).value || "all";
                store.host.requestUpdate();
              }}
            >
              <option value="all" ?selected=${activeFilter === "all"}>All Latter Devices</option>
              <option value="trait:roaming" ?selected=${activeFilter === "trait:roaming"}>
                Roaming Devices
              </option>
              <option value="trait:stationary" ?selected=${activeFilter === "trait:stationary"}>
                Stationary Devices
              </option>
              ${populatedGroups.map(
                (g) =>
                  html`<option
                    value=${`group:${g.id}`}
                    ?selected=${activeFilter === `group:${g.id}`}
                  >
                    Group: ${g.name}
                  </option>`,
              )}
            </select>
            <select
              id="batch-cat-filter"
              aria-label="Filter Batch Controls by category"
              .value=${activeCat}
              @change=${(ev: Event) => {
                store.batchCategoryFilter =
                  (ev.currentTarget as HTMLSelectElement).value || "all";
                store.host.requestUpdate();
              }}
            >
              <option value="all" ?selected=${activeCat === "all"}>All Categories</option>
              <option value="sleep" ?selected=${activeCat === "sleep"}>Sleep &amp; Wake</option>
              <option value="voice" ?selected=${activeCat === "voice"}>Voice &amp; Wake Word</option>
              <option value="sound" ?selected=${activeCat === "sound"}>Sound</option>
              <option value="area" ?selected=${activeCat === "area"}>Area &amp; BLE</option>
              <option value="display" ?selected=${activeCat === "display"}>Display</option>
              <option value="home" ?selected=${activeCat === "home"}>Home</option>
              <option value="music" ?selected=${activeCat === "music"}>Music</option>
            </select>`,
          contentClass: "stack",
          body: !matchingDevs.length
            ? html`<p class="empty-state">No Latter Devices match the selected target.</p>`
            : html`<div class="help-text">
                  Target (${fmtNumber(matchingDevs.length, store.hass, 0)}): ${matchingDevs.map((d) => d.title).join(", ")}
                </div>

                <h4 class="subsection-title">Operational Settings</h4>
                <div id="batch-latter-behavior-list" class="settings-list">
                  ${activeCat === "all" || activeCat === "area"
                    ? html`${renderSettingsRow({
                          label: "Track the Area with BLE Proxies",
                          description: `${fmtNumber(matchingDevs.length, store.hass, 0)} Device${matchingDevs.length === 1 ? "" : "s"}${bleMixed ? " • Mixed values" : ""}`,
                          control: html`${bleMixed ? html`<span class="chip">Mixed</span>` : nothing}
                            <input
                              type="checkbox"
                              role="switch"
                              aria-label="Batch Track the Area with BLE Proxies"
                              .checked=${bleOn}
                              @change=${(ev: Event) =>
                                void store.applyBatchDeviceSetting({
                                  native_ble_tracking: (ev.currentTarget as HTMLInputElement).checked,
                                })}
                              class="switch"
                            />`,
                        })}
                        ${renderSwitchRow({
                          label: "Auto-Switch Active Area",
                          ariaLabel: "Batch Auto-Switch Active Area",
                          description: "Follows BLE Area changes automatically.",
                          checked: bleOn,
                          onChange: (checked) =>
                            void store.applyBatchDeviceSetting({ ble_auto_switch: checked }),
                        })}`
                    : nothing}
                  ${activeCat === "all" || activeCat === "voice"
                    ? renderSwitchRow({
                        label: "Voice Follows Me",
                        ariaLabel: "Batch Voice Follows Me",
                        description: "Moves roaming Devices' Home Assistant Area with them.",
                        checked: false,
                        onChange: (checked) =>
                          void store.applyBatchDeviceSetting({ sync_device_area: checked }),
                      })
                    : nothing}
                  ${activeCat === "all" || activeCat === "music"
                    ? renderSwitchRow({
                        label: "Media Follows Device to New Area",
                        ariaLabel: "Batch Media Follows Device to New Area",
                        description: "Hands off active playback when the Area changes.",
                        checked: false,
                        onChange: (checked) =>
                          void store.applyBatchDeviceSetting({ area_handoff: checked }),
                      })
                    : nothing}
                </div>

                <div id="system-controls-list" class="settings-list">
                  ${behaviorControls.length
                    ? behaviorControls.map((fc) => renderBatchControlRow(fc))
                    : html`<p class="empty-state">No shared Device controls found.</p>`}
                </div>

                <details class="sub-collapsible">
                  <summary>Appearance &amp; Personalization</summary>
                  <div id="system-appearance-controls-list" class="card-content settings-list">
                    ${appearanceControls.length
                      ? appearanceControls.map((fc) => renderBatchControlRow(fc))
                      : html`<p class="empty-state">No appearance controls match this filter.</p>`}
                  </div>
                </details>`,
        })}
      </div>
    </div>
  </section>`;
}
