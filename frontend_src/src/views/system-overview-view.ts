/**
 * System Overview View (`system_overview`): Active Repairs/Issues, System Summary & Configured Items.
 */

import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { fmtNumber, issueMessage } from "../utils/format.js";

export function renderSystemOverviewView(store: StudioStore): TemplateResult {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const issues = data?.issues || [];
  const groups = data?.device_groups || [];
  const sysCfg = data?.system_config;

  const onlineCount = allDevices.filter((d) => d.is_online).length;
  const nativeCount = allDevices.filter((d) => d.is_latter_native).length;
  const bleTrackedCount = allDevices.filter((d) => d.ble_tracked).length;
  const assignedPeopleCount = allDevices.filter((d) => d.assigned_person).length;
  const verText = data?.version ? `v${String(data.version).replace(/^v/i, "")}` : "—";

  const remotesCount = (sysCfg?.remotes_list || []).length;
  const volCount = (sysCfg?.volume_overrides || []).length;
  const camerasCount = (sysCfg?.camera_entities || []).length;
  const calendarsCount = (sysCfg?.calendar_entities || []).length;
  const colorsCount = (sysCfg?.custom_palettes || []).length;
  const wallpapersCount = (data?.system_wallpapers || []).length;
  const groupsLabel = `${groups.length} group${groups.length === 1 ? "" : "s"}`;

  const makeRow = (label: string, value: string, onOpen: () => void): TemplateResult => html`<button
    type="button"
    @click=${onOpen}
    class="kv-row"
  >
    <span>${label}</span>
    <strong>${value}</strong>
  </button>`;

  return html`<section id="view-system_overview">
    <div class="columns">
      <div class="column">
        <div class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">Issues</h3>
            </div>
            <div class="card-header-actions">
              <button
                type="button"
                @click=${() => store.openHaPage("/config/repairs")}
                class="btn btn-secondary btn-compact"
              >
                Open Repairs
              </button>
            </div>
          </div>
          <div class="card-content settings-list">
            ${issues.length
              ? issues.map((iss) => {
                  const isErr = iss.severity === "error" || iss.severity === "critical";
                  return html`<div class="settings-row">
                    <div class="settings-row-text">
                      <span class="row-label">
                        ${iss.device_title || "Latter"}
                        <span class="chip ${isErr ? "chip-error" : "chip-warning"}">
                          ${iss.severity === "warning" ? "Warning" : "Error"}
                        </span>
                      </span>
                      <p class="row-description">${issueMessage(iss)}</p>
                    </div>
                    <div class="settings-row-control">
                      ${iss.subentry_id
                        ? html`<button
                            type="button"
                            @click=${() => void store.switchSystemDevice(String(iss.subentry_id))}
                            class="btn btn-text btn-compact"
                          >
                            Open Device
                          </button>`
                        : nothing}
                    </div>
                  </div>`;
                })
              : html`<p class="empty-state">No issues.</p>`}
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div class="card-heading">
              <h3 class="card-title">System</h3>
            </div>
            <div class="card-header-actions">
              <button
                type="button"
                @click=${() => void store.checkSystemUpdates()}
                class="btn btn-secondary btn-compact"
              >
                Check Firmware Updates
              </button>
            </div>
          </div>
          <div class="card-content">
            <div class="kv-list">
              <div class="kv-row">
                <span>Integration Version</span>
                <strong>${verText}</strong>
              </div>
              ${makeRow(
                "Devices Online",
                `${fmtNumber(onlineCount, store.hass, 0)} / ${fmtNumber(allDevices.length, store.hass, 0)}`,
                () => store.openDevicesWithCategory("online"),
              )}
              ${makeRow(
                "Latter Displays",
                fmtNumber(nativeCount, store.hass, 0),
                () => store.openDevicesWithCategory("native"),
              )}
              ${makeRow(
                "BLE Tracked Devices",
                fmtNumber(bleTrackedCount, store.hass, 0),
                () => store.openDevicesWithCategory("ble_tracked"),
              )}
              ${makeRow(
                "Assigned People",
                fmtNumber(assignedPeopleCount, store.hass, 0),
                () => store.openDevicesWithCategory("assigned_person"),
              )}
              ${makeRow(
                "Area BLE Proxies",
                fmtNumber(data?.ble_proxy_count, store.hass, 0),
                () => store.openSystemSection("area_tracking"),
              )}
            </div>
          </div>
        </div>
      </div>

      <div class="column">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Configured Items</h3>
          </div>
          <div class="card-content">
            <div class="kv-list">
              ${makeRow("Device Groups", groupsLabel, () => store.openSystemSection("system_sync"))}
              ${makeRow("Cameras", fmtNumber(camerasCount, store.hass, 0), () =>
                store.openSystemSection("shared_entities", "card-cameras-doorbell"),
              )}
              ${makeRow("Calendars", fmtNumber(calendarsCount, store.hass, 0), () =>
                store.openSystemSection("shared_entities", "card-calendars"),
              )}
              ${makeRow("Remote Controls", fmtNumber(remotesCount, store.hass, 0), () =>
                store.openSystemSection("remotes"),
              )}
              ${makeRow("Volume Overrides", fmtNumber(volCount, store.hass, 0), () =>
                store.openSystemSection("remotes", "card-volume-overrides"),
              )}
              ${makeRow("Custom Colors", fmtNumber(colorsCount, store.hass, 0), () =>
                store.openSystemSection("shared_entities", "card-custom-colors"),
              )}
              ${makeRow("Wallpapers", fmtNumber(wallpapersCount, store.hass, 0), () =>
                store.openSystemSection("shared_entities", "card-system-wallpapers"),
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>`;
}
