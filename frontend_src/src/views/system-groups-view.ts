/**
 * System Device Groups View (`system_sync`, D-021): Device Groups, Baseline Seeding, Tier 2 Operational & Tier 3 Appearance Bulk Controls.
 */

import {
  renderCard,
  renderSettingsRow,
  renderSwitchRow,
  renderTrashIconButton,
} from "../components/controls.js";
import { DEFAULT_DEVICE_GROUP_IDS } from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { SharedControlItem } from "../types.js";
import { entityLabel, isGroupCustomized } from "../utils/format.js";

export function renderSystemGroupsView(store: StudioStore): TemplateResult {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const latterDevices = allDevices.filter((d) => d.kind !== "ble_tag");
  const groups = data?.device_groups || [];
  const systemControls = data?.system_controls || [];

  const activeFilter = store.groupCtrlFilter || "all";
  const activeGrpId = store.resolvedGroupCtrlId();
  const selectedGrpObj = groups.find((g) => g.id === activeGrpId) || null;
  const activeCat = store.groupCtrlCategoryFilter || "all";

  const matchingDevs = latterDevices.filter((d) => {
    if (activeGrpId === "all") return true;
    if (activeGrpId === "roaming") return Boolean(d.is_roaming);
    if (activeGrpId === "stationary") return !d.is_roaming;
    return d.device_group === activeGrpId;
  });

  const baseCfg = selectedGrpObj?.device_config || {};
  const bleOn =
    selectedGrpObj && baseCfg.native_ble_tracking !== undefined
      ? Boolean(baseCfg.native_ble_tracking)
      : matchingDevs.length
        ? matchingDevs.every((d) => d.ble_tracked)
        : false;
  const autoSw =
    selectedGrpObj && baseCfg.ble_auto_switch !== undefined
      ? Boolean(baseCfg.ble_auto_switch)
      : bleOn;
  const vfm =
    selectedGrpObj && baseCfg.sync_device_area !== undefined
      ? Boolean(baseCfg.sync_device_area)
      : false;
  const handoff =
    selectedGrpObj && baseCfg.area_handoff !== undefined
      ? Boolean(baseCfg.area_handoff)
      : false;

  const renderBulkControlRow = (fc: SharedControlItem): TemplateResult | typeof nothing => {
    if (activeCat !== "all" && fc.section !== activeCat) return nothing;
    const targets = (fc.targets || []).filter((t) => {
      if (activeGrpId === "all") return true;
      if (activeGrpId === "roaming") return Boolean(t.is_roaming);
      if (activeGrpId === "stationary") return !t.is_roaming;
      return t.device_group === activeGrpId;
    });
    const baselineVal =
      selectedGrpObj?.esphome_controls && fc.canonical_key
        ? selectedGrpObj.esphome_controls[fc.canonical_key]
        : undefined;
    if (!targets.length && baselineVal === undefined) return nothing;

    const states = targets.length
      ? Array.from(new Set(targets.map((t) => String(t.state ?? ""))))
      : baselineVal !== undefined
        ? [String(baselineVal)]
        : [];
    const mixed = states.length > 1;
    const curState = mixed ? "" : (states[0] ?? "");
    const baseNote = baselineVal !== undefined ? ` • Baseline: ${String(baselineVal)}` : "";
    const desc = `${fc.section_title} • ${targets.length} Device${targets.length === 1 ? "" : "s"}${mixed ? " • Mixed values" : ""}${baseNote}`;

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
          heading: html`<h3 class="card-title">Device Groups</h3>`,
          subtitle:
            "Operational baselines (sleep, wake word, BLE) shared across assigned Devices without overwriting personal appearance.",
          contentClass: "stack",
          body: html`<div class="input-action-row">
              <input
                type="text"
                id="new-group-name"
                aria-label="New Device Group name"
                placeholder="Group name (e.g. Guest Suites)"
                .value=${store.newGroupName}
                @input=${(ev: Event) => {
                  store.newGroupName = (ev.currentTarget as HTMLInputElement).value;
                }}
              />
              <input
                type="text"
                id="new-group-desc"
                aria-label="New Device Group description"
                placeholder="Optional description"
                .value=${store.newGroupDesc}
                @input=${(ev: Event) => {
                  store.newGroupDesc = (ev.currentTarget as HTMLInputElement).value;
                }}
              />
              <button
                type="button"
                @click=${() => void store.createDeviceGroup()}
                class="btn btn-primary"
              >
                Create Group
              </button>
            </div>

            <div id="device-groups-list" class="settings-list">
              ${groups.map((g) => {
                const members = allDevices.filter((d) => d.device_group === g.id);
                const isDefault = DEFAULT_DEVICE_GROUP_IDS.has(g.id) || Boolean(g.builtin);
                const customizedCnt = members.filter((m) =>
                  isGroupCustomized(m.group_sync_status),
                ).length;
                const syncMeta =
                  g.id === "unassigned" || !members.length
                    ? ""
                    : customizedCnt
                      ? `${customizedCnt} customized`
                      : "All in sync";
                const desc = [
                  g.description || "",
                  members.length ? `Devices: ${members.map((m) => m.title).join(", ")}` : "No Devices",
                  syncMeta,
                ]
                  .filter(Boolean)
                  .join(" • ");

                return renderSettingsRow({
                  labelHtml: html`<span class="row-label">
                    ${g.name} <span class="chip">${members.length}</span>
                  </span>`,
                  description: desc,
                  control: html`<button
                      type="button"
                      @click=${() => {
                        store.groupCtrlFilter = `group:${g.id}`;
                        store.host.requestUpdate();
                      }}
                      class="btn btn-text btn-compact"
                    >
                      Edit Controls
                    </button>
                    ${g.id !== "unassigned" && members.length
                      ? html`<button
                          type="button"
                          @click=${() => void store.syncDeviceGroup(g.id)}
                          class="btn btn-secondary btn-compact"
                        >
                          Sync Group
                        </button>`
                      : nothing}
                    ${!isDefault
                      ? renderTrashIconButton(`Delete group ${g.name}`, () =>
                          void store.deleteDeviceGroup(g.id),
                        )
                      : nothing}`,
                });
              })}
            </div>`,
        })}

        ${renderCard({
          title: "Seed Baseline From Device",
          subtitle: "Captures an existing Device's operational settings as a group's baseline.",
          contentClass: "stack",
          body: html`<div class="list-row-main">
              <div class="stacked-field">
                <label for="seed-group-target">Target Group</label>
                <select
                  id="seed-group-target"
                  .value=${store.seedGroupTargetId}
                  @change=${(ev: Event) => {
                    store.seedGroupTargetId = (ev.currentTarget as HTMLSelectElement).value;
                    store.host.requestUpdate();
                  }}
                >
                  ${groups
                    .filter((g) => g.id !== "unassigned")
                    .map(
                      (g) =>
                        html`<option value=${g.id} ?selected=${g.id === store.seedGroupTargetId}>
                          ${g.name}
                        </option>`,
                    )}
                </select>
              </div>
              <div class="stacked-field">
                <label for="seed-source-device">Source Device</label>
                <select
                  id="seed-source-device"
                  .value=${store.seedSourceSubentryId}
                  @change=${(ev: Event) => {
                    store.seedSourceSubentryId = (ev.currentTarget as HTMLSelectElement).value;
                    store.host.requestUpdate();
                  }}
                >
                  ${latterDevices.map(
                    (d) =>
                      html`<option
                        value=${d.subentry_id}
                        ?selected=${d.subentry_id === store.seedSourceSubentryId}
                      >
                        ${d.title}
                      </option>`,
                  )}
                </select>
              </div>
            </div>
            <div class="input-action-row">
              <button
                type="button"
                @click=${() => void store.seedGroupBaselineFromDevice()}
                class="btn btn-secondary"
              >
                Save Group Baseline
              </button>
            </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Group Controls &amp; Baseline</h3>`,
          headerActions: html`<select
              id="group-ctrl-filter"
              aria-label="Target Devices or group"
              .value=${activeFilter}
              @change=${(ev: Event) => {
                store.groupCtrlFilter = (ev.currentTarget as HTMLSelectElement).value || "all";
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
              ${groups
                .filter((g) => g.id !== "unassigned")
                .map(
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
              id="group-ctrl-cat-filter"
              aria-label="Filter controls by category"
              .value=${activeCat}
              @change=${(ev: Event) => {
                store.groupCtrlCategoryFilter =
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
          body: html`<h4 class="subsection-title">Operational Behavior (Synced with Group)</h4>
            <div id="group-latter-behavior-list" class="settings-list">
              ${activeCat === "all" || activeCat === "area"
                ? html`${renderSwitchRow({
                      label: "Track the Area with BLE Proxies",
                      description: selectedGrpObj
                        ? `Group Baseline • ${matchingDevs.length} Device(s)`
                        : `${matchingDevs.length} Device(s)`,
                      checked: bleOn,
                      onChange: (checked) =>
                        void store.setGroupDeviceSetting({ native_ble_tracking: checked }),
                    })}
                    ${renderSwitchRow({
                      label: "Auto-Switch Active Area",
                      description: "Follows BLE Area changes automatically.",
                      checked: autoSw,
                      onChange: (checked) =>
                        void store.setGroupDeviceSetting({ ble_auto_switch: checked }),
                    })}`
                : nothing}
              ${activeCat === "all" || activeCat === "voice"
                ? renderSwitchRow({
                    label: "Voice Follows Me",
                    description: "Moves roaming Devices' Home Assistant Area with them.",
                    checked: vfm,
                    onChange: (checked) =>
                      void store.setGroupDeviceSetting({ sync_device_area: checked }),
                  })
                : nothing}
              ${activeCat === "all" || activeCat === "music"
                ? renderSwitchRow({
                    label: "Media Follows Device to New Area",
                    description: "Hands off active playback when the Area changes.",
                    checked: handoff,
                    onChange: (checked) =>
                      void store.setGroupDeviceSetting({ area_handoff: checked }),
                  })
                : nothing}
            </div>

            <div id="system-controls-list" class="settings-list">
              ${behaviorControls.length
                ? behaviorControls.map((fc) => renderBulkControlRow(fc))
                : html`<p class="empty-state">No shared Device controls found.</p>`}
            </div>

            <details class="sub-collapsible">
              <summary>Appearance &amp; Personalization (Bulk Override)</summary>
              <div id="system-appearance-controls-list" class="card-content settings-list">
                ${appearanceControls.length
                  ? appearanceControls.map((fc) => renderBulkControlRow(fc))
                  : html`<p class="empty-state">No appearance controls match this filter.</p>`}
              </div>
            </details>`,
        })}
      </div>
    </div>
  </section>`;
}
