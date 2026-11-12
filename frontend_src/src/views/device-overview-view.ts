/**
 * Device Overview View (`dashboard`): Health repairs alert, Status card (13 rows + footer), Quick Actions & Sensors.
 */

import {
  renderCard,
  renderNativeControlRow,
  renderQuickActionGrid,
  renderSelectRow,
  renderSettingsRow,
} from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import {
  fmtDistance,
  fmtNumber,
  fmtPercent,
  isGroupCustomized,
  issueMessage,
} from "../utils/format.js";

export function renderDeviceOverviewView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const live = data?.live || {};
  const caps = data?.capabilities || {};
  const links = data?.links || {};
  const esp = data?.esphome;
  const isBleOnly = cfg.kind === "ble_tag";

  const curDevEntry =
    (data?.system_devices || []).find((d) => d.subentry_id === store.activeSubentryId) ||
    (data?.system_devices || []).find((d) => d.is_current);

  const deviceIssues = (data?.issues || []).filter(
    (i) => i.subentry_id && i.subentry_id === store.activeSubentryId,
  );
  const hasErrorIssue = deviceIssues.some(
    (i) => i.severity === "error" || i.severity === "critical",
  );

  // Live Status calculations
  const winRow = (curDevEntry?.ble_survey_rows || []).find((r) => r.is_winner);
  let batText = "—";
  if (!isBleOnly && curDevEntry?.battery_level !== null && curDevEntry?.battery_level !== undefined) {
    if (curDevEntry.is_charging) {
      batText = `${fmtPercent(curDevEntry.battery_level, store.hass)} (charging)`;
    } else if (curDevEntry.is_usb_connected) {
      batText = `${fmtPercent(curDevEntry.battery_level, store.hass)} (plugged in)`;
    } else {
      batText = fmtPercent(curDevEntry.battery_level, store.hass);
    }
  }
  const showBatteryRow = Boolean(caps.has_power) || batText !== "—";

  let wifiText = "—";
  if (curDevEntry?.wifi_rssi !== null && curDevEntry?.wifi_rssi !== undefined) {
    wifiText = `${fmtNumber(curDevEntry.wifi_rssi, store.hass, 0)} dBm`;
  } else if (isBleOnly && winRow && winRow.effective_rssi !== null) {
    wifiText = `${fmtNumber(winRow.effective_rssi, store.hass, 0)} dBm (BLE)`;
  }

  const ipStr = curDevEntry?.ip_address || (isBleOnly ? cfg.ble_target_address || "—" : "—");
  const hasAssignedArea = Boolean(curDevEntry?.has_assigned_area);
  const areaText = hasAssignedArea
    ? curDevEntry?.area_label || live.active_area_name || "—"
    : live.active_area_name || "—";

  const now = live.now || { speaker_name: "", media_state: "", media_title: "", media_artist: "" };
  const playingTitle = [now.media_title, now.media_artist].filter(Boolean).join(" — ");
  const nowPlayingText = playingTitle
    ? now.media_state === "paused"
      ? `${playingTitle} (paused)`
      : playingTitle
    : now.media_state
      ? "Nothing playing"
      : "—";

  const rawSw = String(live.device_sw_version || esp?.device?.sw_version || "").replace(/^v/i, "");
  const fwText = rawSw
    ? live.fw_update_available
      ? `v${rawSw} (update available)`
      : `v${rawSw}`
    : "—";

  const statusText = isBleOnly
    ? curDevEntry?.status_label || "—"
    : curDevEntry?.is_online === undefined
      ? "—"
      : curDevEntry.is_online
        ? "Online"
        : "Offline";

  const distSuffix =
    live.ble_closest_proxy && winRow && winRow.distance_m !== null && winRow.distance_m !== undefined
      ? ` (~${fmtDistance(winRow.distance_m, store.hass, winRow.distance_ft)})`
      : "";
  const showProxyRow = Boolean(caps.has_ble_beacon && cfg.native_ble_tracking);

  const quickActionItems = store
    .getSectionItems("actions")
    .concat(store.getSectionItems("overview"));
  const quickActionButtons = quickActionItems.filter((it) => it.domain === "button");
  const otherQuickItems = quickActionItems.filter((it) => it.domain !== "button");
  const otherSensorItems = store.getSectionItems("other");

  const groups = data?.device_groups || [];
  const curGroupId = cfg.device_group || "unassigned";
  const syncStatus = live.group_sync_status ?? curDevEntry?.group_sync_status;
  const isCustomized = curGroupId !== "unassigned" && isGroupCustomized(syncStatus);

  return html`<section id="view-dashboard" class="stack">
    ${deviceIssues.length
      ? html`<div role="alert" class="alert ${hasErrorIssue ? "alert-error" : "alert-warning"}">
          <div class="alert-body">
            <strong>Needs Attention</strong>
            <ul class="alert-list">
              ${deviceIssues.map((iss) => html`<li>${issueMessage(iss)}</li>`)}
            </ul>
          </div>
          <button
            type="button"
            @click=${() => store.openHaPage("/config/repairs")}
            class="btn btn-secondary btn-compact"
          >
            Open Repairs
          </button>
        </div>`
      : nothing}

    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Status</h3>`,
          body: html`<div class="kv-list">
            <div class="kv-row"><span>Status</span><strong>${statusText}</strong></div>
            <div class="kv-row">
              <span id="st-area-label">${hasAssignedArea ? "Area" : "Current Area"}</span>
              <strong>${areaText}</strong>
            </div>
            <div class="kv-row"><span>Speaker</span><strong>${now.speaker_name || "—"}</strong></div>
            <div class="kv-row"><span>Now Playing</span><strong>${nowPlayingText}</strong></div>
            ${showBatteryRow
              ? html`<div class="kv-row"><span>Battery</span><strong>${batText}</strong></div>`
              : nothing}
            <div class="kv-row">
              <span id="st-wifi-label">${isBleOnly ? "BLE Signal" : "Wi-Fi Signal"}</span>
              <strong>${wifiText}</strong>
            </div>
            ${showProxyRow
              ? html`<div class="kv-row">
                  <span>Closest Proxy</span>
                  <strong>${(live.ble_closest_proxy || "—") + distSuffix}</strong>
                </div>`
              : nothing}
            <div class="kv-row">
              <span>Model</span>
              <strong>${curDevEntry?.model_label || esp?.device?.model || "—"}</strong>
            </div>
            <div class="kv-row"><span>Firmware</span><strong>${fwText}</strong></div>
            <div class="kv-row">
              <span>Latter SDK</span>
              <strong id="dash-sdk-rev">${live.sdk_rev || "—"}</strong>
            </div>
            <div class="kv-row">
              <span>ESPHome Node</span>
              <strong><code id="dash-node-name">${cfg.device_slug || "—"}</code></strong>
            </div>
            <div class="kv-row">
              <span>${isBleOnly ? "Target" : "IP Address"}</span>
              <strong><code>${ipStr}</code></strong>
            </div>
            <div class="kv-row">
              <span>Placement</span>
              <strong>${hasAssignedArea ? "Stationary" : "Roaming"}</strong>
            </div>
          </div>`,
          footerActions: html`${links.esphome_device_id
              ? html`<button
                  type="button"
                  id="btn-open-in-ha"
                  @click=${() => store.openDeviceInHa()}
                  class="btn btn-text"
                >
                  Open in Home Assistant
                </button>`
              : nothing}
            <button
              type="button"
              @click=${() => void store.exportBackup(store.activeSubentryId)}
              class="btn btn-text"
            >
              Download Backup
            </button>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "Quick Actions",
          contentClass: "settings-list",
          body: html`${renderQuickActionGrid(store, quickActionButtons)}
            ${!isBleOnly
              ? renderSettingsRow({
                  label: "Device Group",
                  forId: "cfg-device_group",
                  description:
                    "Shares operational behavior (sleep, wake word, BLE) across matching Devices.",
                  control: html`${curGroupId !== "unassigned"
                      ? html`<span
                          id="dash-group-sync-chip"
                          class="chip ${isCustomized ? "chip-warning" : "chip-success"}"
                        >
                          ${isCustomized ? "Customized" : "In Sync"}
                        </span>`
                      : nothing}
                    <select
                      id="cfg-device_group"
                      .value=${curGroupId}
                      @change=${(ev: Event) =>
                        store.stageDeviceSetting(
                          "device_group",
                          (ev.currentTarget as HTMLSelectElement).value,
                          "cfg-device_group",
                        )}
                    >
                      ${groups.map(
                        (g) =>
                          html`<option value=${g.id} ?selected=${g.id === curGroupId}>
                            ${g.name}
                          </option>`,
                      )}
                    </select>
                    ${isCustomized
                      ? html`<button
                          type="button"
                          id="btn-reset-to-group"
                          @click=${() => void store.syncDeviceGroup(curGroupId, store.activeSubentryId)}
                          class="btn btn-secondary btn-compact"
                        >
                          Reset to Group
                        </button>`
                      : nothing}`,
                })
              : nothing}
            ${renderSelectRow({
              id: "cfg-assigned_person",
              label: "Assigned Person",
              description: "Links this Device's Area presence to a Home Assistant person entity.",
              value: cfg.assigned_person,
              choices: data?.catalog?.persons,
              emptyOptionLabel: "— Unassigned —",
              onChange: (val) =>
                store.stageDeviceSetting("assigned_person", val, "cfg-assigned_person"),
            })}
            ${otherQuickItems.map((it) => renderNativeControlRow(store, it))}`,
        })}

        ${otherSensorItems.length
          ? renderCard({
              title: "Sensors & Controls",
              contentClass: "settings-list",
              body: otherSensorItems.map((it) => renderNativeControlRow(store, it)),
            })
          : nothing}
      </div>
    </div>
  </section>`;
}
