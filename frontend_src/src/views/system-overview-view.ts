/**
 * System Overview View (`system_overview`, D-051):
 * - Conditional top alerts for active Home Assistant Repairs and unbound Discovered Latter hardware.
 * - Column 1: High-level Status card (2x2 tonal metric tiles + Open Repairs & Check Firmware Updates footer)
 *   followed by Area Deployment (live spatial deployment, occupancy, and Bluetooth coverage across Areas).
 * - Column 2: System Capabilities (visual readiness across Home Hub & Weather, Cameras/Doorbells/Calendars,
 *   Media & Remotes, Device Groups, Colors & Wallpapers, and Perimeter Security).
 */

import { renderCard, renderSvgIcon } from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { AreaPresenceRow, BleAreaSignatureSummary, SystemConfig } from "../types.js";
import { entityLabel, fmtNumber, issueMessage } from "../utils/format.js";

const SYS_ICON_DEVICES = "M4,6H20V16H4M20,18A2,2 0 0,0 22,16V6C22,4.89 21.1,4 20,4H4C2.89,4 2,4.89 2,6V16A2,2 0 0,0 4,18H0V20H24V18H20Z";
const SYS_ICON_AREAS = "M12,6.5A2.5,2.5 0 0,1 14.5,9A2.5,2.5 0 0,1 12,11.5A2.5,2.5 0 0,1 9.5,9A2.5,2.5 0 0,1 12,6.5M12,2A7,7 0 0,1 19,9C19,14.25 12,22 12,22C12,22 5,14.25 5,9A7,7 0 0,1 12,2M12,4A5,5 0 0,0 7,9C7,10 7,12 12,18.71C17,12 17,10 17,9A5,5 0 0,0 12,4Z";
const SYS_ICON_ROAMING = "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12C22,10.84 21.79,9.69 21.39,8.61L19.79,10.21C19.93,10.8 20,11.4 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4C12.6,4 13.2,4.07 13.79,4.21L15.4,2.6C14.31,2.21 13.16,2 12,2M19,2A2,2 0 0,0 17,4A2,2 0 0,0 19,6A2,2 0 0,0 21,4A2,2 0 0,0 19,2M12,6A6,6 0 0,0 6,12A6,6 0 0,0 12,18A6,6 0 0,0 18,12H16A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8V6M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10Z";
const SYS_ICON_RELEASE = "M17,17H7V7H17M21,11V9H19V7C19,5.89 18.1,5 17,5H15V3H13V5H11V3H9V5H7C5.89,5 5,5.89 5,7V9H3V11H5V13H3V15H5V17A2,2 0 0,0 7,19H9V21H11V19H13V21H15V19H17A2,2 0 0,0 19,17V15H21V13H19V11M15,15H9V9H15V15Z";
const SYS_ICON_HOME = "M12,3L2,12H5V20H19V12H22L12,3M12,8.75A2.25,2.25 0 0,1 14.25,11A2.25,2.25 0 0,1 12,13.25A2.25,2.25 0 0,1 9.75,11A2.25,2.25 0 0,1 12,8.75M12,15C13.5,15 16.5,15.75 16.5,17.25V18H7.5V17.25C7.5,15.75 10.5,15 12,15Z";
const SYS_ICON_CAMERA = "M17,10.5V7A1,1 0 0,0 16,6H4A1,1 0 0,0 3,7V17A1,1 0 0,0 4,18H16A1,1 0 0,0 17,17V13.5L21,17.5V6.5L17,10.5Z";
const SYS_ICON_REMOTE = "M9,2A2,2 0 0,0 7,4V20A2,2 0 0,0 9,22H15A2,2 0 0,0 17,20V4A2,2 0 0,0 15,2H9M12,6A3,3 0 0,1 15,9A3,3 0 0,1 12,12A3,3 0 0,1 9,9A3,3 0 0,1 12,6M12,8A1,1 0 0,0 11,9A1,1 0 0,0 12,10A1,1 0 0,0 13,9A1,1 0 0,0 12,8M10,15H14V17H10V15M10,18H14V20H10V18Z";
const SYS_ICON_GROUPS = "M3,3H11V11H3V3M13,3H21V11H13V3M3,13H11V21H3V13M13,13H21V21H13V13M5,5V9H9V5H5M15,5V9H19V5H15M5,15V19H9V15H5M15,15V19H19V15H15Z";
const SYS_ICON_PALETTE = "M17.5,12A1.5,1.5 0 0,1 16,10.5A1.5,1.5 0 0,1 17.5,9A1.5,1.5 0 0,1 19,10.5A1.5,1.5 0 0,1 17.5,12M14.5,8A1.5,1.5 0 0,1 13,6.5A1.5,1.5 0 0,1 14.5,5A1.5,1.5 0 0,1 16,6.5A1.5,1.5 0 0,1 14.5,8M9.5,8A1.5,1.5 0 0,1 8,6.5A1.5,1.5 0 0,1 9.5,5A1.5,1.5 0 0,1 11,6.5A1.5,1.5 0 0,1 9.5,8M6.5,12A1.5,1.5 0 0,1 5,10.5A1.5,1.5 0 0,1 6.5,9A1.5,1.5 0 0,1 8,10.5A1.5,1.5 0 0,1 6.5,12M12,3A9,9 0 0,0 3,12A9,9 0 0,0 12,21A1.5,1.5 0 0,0 13.5,19.5C13.5,19.11 13.35,18.76 13.11,18.5C12.88,18.23 12.73,17.88 12.73,17.5A1.5,1.5 0 0,1 14.23,16H16A5,5 0 0,0 21,11C21,6.58 16.97,3 12,3Z";
const SYS_ICON_SHIELD = "M12,1L3,5V11C3,16.55 6.84,21.74 12,23C17.16,21.74 21,16.55 21,11V5L12,1M12,7C13.4,7 14.8,8.1 14.8,9.5V11C15.4,11 16,11.6 16,12.3V15.8C16,16.4 15.4,17 14.7,17H9.2C8.6,17 8,16.4 8,15.7V12.2C8,11.6 8.6,11 9.2,11V9.5C9.2,8.1 10.6,7 12,7M12,8.2C11.2,8.2 10.5,8.7 10.5,9.5V11H13.5V9.5C13.5,8.7 12.8,8.2 12,8.2Z";

const WHOLE_HOME_DOMAINS: ReadonlyArray<{
  key: keyof Pick<
    SystemConfig,
    | "weather_entity"
    | "alarm_entity"
    | "thermostat_entity"
    | "lock_entity"
    | "garage_entity"
    | "vacuum_entity"
  >;
  label: string;
}> = [
  { key: "weather_entity", label: "Weather" },
  { key: "alarm_entity", label: "Alarm" },
  { key: "thermostat_entity", label: "Thermostat" },
  { key: "lock_entity", label: "Door Lock" },
  { key: "garage_entity", label: "Garage" },
  { key: "vacuum_entity", label: "Vacuum" },
];

interface OverviewAreaEntry {
  areaId: string;
  areaName: string;
  floorLabel: string;
  isOccupied: boolean;
  occupants: string[];
  hasBleProxy: boolean;
  hasSignature: boolean;
  scannerCount: number;
  stationedTitles: string[];
  roamingHereTitles: string[];
  remoteCount: number;
  sensorCount: number;
  activeSensorCount: number;
  isDeployed: boolean;
}

export function renderSystemOverviewView(store: StudioStore): TemplateResult {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const issues = data?.issues || [];
  const discoveredLatter = data?.discovered_latter_devices || [];
  const groups = data?.device_groups || [];
  const sysCfg = data?.system_config;
  const presenceRows = data?.live?.area_presence_grid || [];
  const signatures = data?.ble_area_signatures || [];

  const totalCount = allDevices.length;
  const onlineCount = allDevices.filter((d) => d.is_online).length;
  const offlineCount = Math.max(0, totalCount - onlineCount);
  const displayCount = allDevices.filter((d) => d.kind !== "ble_tag" && d.has_display).length;
  const bleTagCount = allDevices.filter((d) => d.kind === "ble_tag").length;
  const audioOnlyCount = allDevices.filter((d) => d.kind !== "ble_tag" && !d.has_display).length;
  const bleTrackedCount = allDevices.filter((d) => d.ble_tracked || d.kind === "ble_tag").length;
  const assignedPeopleCount = allDevices.filter((d) => Boolean(d.assigned_person)).length;
  const updatesCount = Math.max(
    allDevices.filter((d) => d.status_label === "Update available").length,
    Number(data?.update_check?.available || 0),
  );
  const verText = data?.version ? `v${String(data.version).replace(/^v/i, "")}` : "—";
  const bleProxyCount = Number(data?.ble_proxy_count ?? 0);

  const hasErrorIssue = issues.some((i) => i.severity === "error" || i.severity === "critical");

  let sysChipClass = "chip";
  let sysDotClass = "status-dot";
  let sysStatusLabel = "No Devices";
  if (issues.length > 0) {
    sysChipClass = hasErrorIssue ? "chip chip-error" : "chip chip-warning";
    sysDotClass = "status-dot update";
    sysStatusLabel = `${fmtNumber(issues.length, store.hass, 0)} ${issues.length === 1 ? "Issue" : "Issues"}`;
  } else if (totalCount > 0 && updatesCount > 0) {
    sysChipClass = "chip chip-warning";
    sysDotClass = "status-dot update";
    sysStatusLabel = `${fmtNumber(updatesCount, store.hass, 0)} ${updatesCount === 1 ? "Update" : "Updates"}`;
  } else if (totalCount > 0 && offlineCount === 0) {
    sysChipClass = "chip chip-success";
    sysDotClass = "status-dot online";
    sysStatusLabel = "All Online";
  } else if (totalCount > 0 && onlineCount > 0) {
    sysDotClass = "status-dot online";
    sysStatusLabel = `${fmtNumber(onlineCount, store.hass, 0)} / ${fmtNumber(totalCount, store.hass, 0)} Online`;
  } else if (totalCount > 0) {
    sysStatusLabel = "Offline";
  }

  const onlinePct = totalCount > 0 ? Math.round((onlineCount / totalCount) * 100) : 0;
  const devMetaParts: string[] = [];
  if (totalCount === 0) {
    devMetaParts.push("Ready to onboard");
  } else {
    devMetaParts.push(`${fmtNumber(displayCount, store.hass, 0)} ${displayCount === 1 ? "display" : "displays"}`);
    if (bleTagCount > 0) {
      devMetaParts.push(`${fmtNumber(bleTagCount, store.hass, 0)} BLE ${bleTagCount === 1 ? "tag" : "tags"}`);
    } else if (audioOnlyCount > 0) {
      devMetaParts.push(`${fmtNumber(audioOnlyCount, store.hass, 0)} audio`);
    }
  }

  // Build unified Area Deployment map from existing payload fields
  const sigByArea = new Map<string, BleAreaSignatureSummary>();
  for (const sig of signatures) {
    if (sig.area_id) sigByArea.set(sig.area_id, sig);
  }
  const rowByArea = new Map<string, AreaPresenceRow>();
  for (const row of presenceRows) {
    if (row.area_id) rowByArea.set(row.area_id, row);
  }
  const remoteGroups = sysCfg?.remote_groups || [];
  const allAreaIds: string[] = [];
  const seenAreaIds = new Set<string>();
  for (const row of presenceRows) {
    if (row.area_id && !seenAreaIds.has(row.area_id)) {
      seenAreaIds.add(row.area_id);
      allAreaIds.push(row.area_id);
    }
  }
  for (const sig of signatures) {
    if (sig.area_id && !seenAreaIds.has(sig.area_id)) {
      seenAreaIds.add(sig.area_id);
      allAreaIds.push(sig.area_id);
    }
  }
  for (const catArea of data?.catalog?.areas || []) {
    if (catArea.id && !seenAreaIds.has(catArea.id)) {
      seenAreaIds.add(catArea.id);
      allAreaIds.push(catArea.id);
    }
  }

  const areaEntries: OverviewAreaEntry[] = allAreaIds.map((areaId) => {
    const row = rowByArea.get(areaId);
    const sig = sigByArea.get(areaId);
    const catArea = (data?.catalog?.areas || []).find((a) => a.id === areaId);
    const areaName = row?.area_name || sig?.area_name || catArea?.name || areaId;
    const areaLow = areaName.trim().toLowerCase();

    const stationedTitles = allDevices
      .filter((d) => d.has_assigned_area && (d.area_label || "").trim().toLowerCase() === areaLow)
      .map((d) => d.title);
    const roamingHereTitles = allDevices
      .filter(
        (d) =>
          !d.has_assigned_area &&
          d.is_online &&
          (d.active_area_name || "").trim().toLowerCase() === areaLow,
      )
      .map((d) => d.title);

    const areaRemoteCount = remoteGroups
      .filter((rg) => rg.area_id === areaId)
      .reduce((acc, rg) => acc + (rg.remotes || []).filter(Boolean).length, 0);

    const hasBleProxy = sig
      ? Boolean(sig.has_ble_proxy)
      : Boolean(row?.winning_rssi !== null && row?.winning_rssi !== undefined);
    const hasSignature = Boolean(sig?.has_signature);
    const activeSensorCount = (row?.active_sensors || []).length;
    const sensorCount = Math.max((row?.fusion_sensors || []).length, activeSensorCount);
    const isOccupied = Boolean(row?.is_occupied);
    const occupants = row?.occupant_names || [];

    const isDeployed =
      isOccupied ||
      stationedTitles.length > 0 ||
      roamingHereTitles.length > 0 ||
      hasSignature ||
      hasBleProxy ||
      areaRemoteCount > 0 ||
      sensorCount > 0;

    return {
      areaId,
      areaName,
      floorLabel: String(row?.floor_name || "").trim(),
      isOccupied,
      occupants,
      hasBleProxy,
      hasSignature,
      scannerCount: Number(sig?.scanner_count || 0),
      stationedTitles,
      roamingHereTitles,
      remoteCount: areaRemoteCount,
      sensorCount,
      activeSensorCount,
      isDeployed,
    };
  });

  areaEntries.sort((a, b) => {
    if (a.isOccupied !== b.isOccupied) return a.isOccupied ? -1 : 1;
    const aDev = a.stationedTitles.length + a.roamingHereTitles.length;
    const bDev = b.stationedTitles.length + b.roamingHereTitles.length;
    if ((aDev > 0) !== (bDev > 0)) return aDev > 0 ? -1 : 1;
    return a.areaName.localeCompare(b.areaName, undefined, { sensitivity: "base" });
  });

  const totalAreas = areaEntries.length;
  const occupiedAreasCount = areaEntries.filter((a) => a.isOccupied).length;
  const deployedAreas = areaEntries.filter((a) => a.isDeployed);
  const shownAreas = deployedAreas.length > 0 ? deployedAreas : areaEntries.slice(0, 6);
  const unconfiguredAreaCount =
    deployedAreas.length > 0 ? Math.max(0, totalAreas - deployedAreas.length) : Math.max(0, totalAreas - shownAreas.length);

  const roamingDevices = allDevices.filter((d) => !d.has_assigned_area && (d.is_roaming || d.kind === "ble_tag"));
  const roamingOnlineCount = roamingDevices.filter((d) => d.is_online).length;

  // System Capabilities metrics
  const wholeHomeStatuses = WHOLE_HOME_DOMAINS.map((d) => ({
    label: d.label,
    configured: Boolean(String(sysCfg?.[d.key] || "").trim()),
  }));
  const wholeHomeActiveCount = wholeHomeStatuses.filter((s) => s.configured).length;

  const camerasCount = (sysCfg?.camera_entities || []).filter(Boolean).length;
  const doorbellsCount = (data?.doorbells || []).filter((b) => Boolean(b.ring_entity)).length;
  const calendarsCount = (sysCfg?.calendar_entities || []).filter(Boolean).length;

  const remotesCount = (sysCfg?.remotes_list || []).filter(Boolean).length;
  const remoteGroupsCount = remoteGroups.length;
  const volCount = (sysCfg?.volume_overrides || []).length;

  const palettes = sysCfg?.custom_palettes || [];
  const colorsCount = palettes.length;
  const wallpapers = data?.system_wallpapers || [];
  const wallpapersCount = wallpapers.length;
  const uploadedWallpapersCount = wallpapers.filter((w) => w.kind === "upload" || w.deletable).length;
  const presetWallpapersCount = Math.max(0, wallpapersCount - uploadedWallpapersCount);

  const hasSystemPin = Boolean(data?.has_security_pin);

  const latterHardwareDevices = allDevices.filter((d) => d.kind !== "ble_tag");
  const populatedGroupChips: Array<{ label: string; active: boolean }> = [];
  for (const g of groups) {
    if (!g?.id || g.id === "custom") continue;
    const cnt = latterHardwareDevices.filter((d) => d.device_group === g.id).length;
    if (cnt > 0 || latterHardwareDevices.length === 0) {
      populatedGroupChips.push({
        label:
          latterHardwareDevices.length > 0
            ? `${entityLabel(g.name)}: ${fmtNumber(cnt, store.hass, 0)}`
            : entityLabel(g.name),
        active: cnt > 0,
      });
    }
  }
  const customGroupCount = latterHardwareDevices.filter(
    (d) => !d.device_group || d.device_group === "custom",
  ).length;
  if (customGroupCount > 0) {
    populatedGroupChips.push({
      label: `Custom: ${fmtNumber(customGroupCount, store.hass, 0)}`,
      active: true,
    });
  }

  return html`<section id="view-system_overview" class="stack">
    ${issues.length
      ? html`<div
          id="sys-issues-banner"
          role="alert"
          class="alert ${hasErrorIssue ? "alert-error" : "alert-warning"}"
        >
          <div class="alert-body">
            <strong>Needs Attention</strong>
            <ul class="alert-list">
              ${issues.map(
                (iss) => html`<li>
                  <strong>${iss.device_title || "Latter"}:</strong> ${issueMessage(iss)}
                  ${iss.subentry_id
                    ? html`<button
                        type="button"
                        @click=${() => void store.switchSystemDevice(String(iss.subentry_id))}
                        class="btn btn-text btn-compact"
                      >
                        Open Device
                      </button>`
                    : nothing}
                </li>`,
              )}
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

    ${discoveredLatter.length
      ? html`<div id="sys-discovered-banner" class="alert">
          <div class="alert-body">
            <strong>Hardware Ready to Adopt</strong>
            <p class="row-description">
              ${fmtNumber(discoveredLatter.length, store.hass, 0)} unbound Latter
              ${discoveredLatter.length === 1 ? "Device" : "Devices"} detected on your network
              (${discoveredLatter
                .slice(0, 3)
                .map((d) => d.title || d.node_name)
                .join(", ")}${discoveredLatter.length > 3 ? "…" : ""}).
            </p>
          </div>
          <button
            type="button"
            @click=${() => store.openDiscoveredDevices()}
            class="btn btn-secondary btn-compact"
          >
            Open Discovered
          </button>
        </div>`
      : nothing}

    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-system-status",
          heading: html`<h3 class="card-title">Status</h3>`,
          headerActions: html`<span id="sys-status-chip" class=${sysChipClass}>
            <span class=${sysDotClass} aria-hidden="true"></span>${sysStatusLabel}
          </span>`,
          contentClass: "stack",
          body: html`<div class="status-tiles">
            <button
              type="button"
              id="sys-tile-devices"
              @click=${() => store.openDevicesWithCategory("all")}
              class="status-tile"
            >
              <div class="status-tile-head">
                ${renderSvgIcon(SYS_ICON_DEVICES)}
                <span>Managed Devices</span>
              </div>
              <strong class="status-tile-value">
                ${totalCount > 0
                  ? `${fmtNumber(onlineCount, store.hass, 0)} / ${fmtNumber(totalCount, store.hass, 0)} Online`
                  : "0 Devices"}
              </strong>
              <span class="status-tile-meta">${devMetaParts.join(" • ")}</span>
              ${totalCount > 0
                ? html`<div class="signal-track" aria-hidden="true">
                    <div
                      class="signal-fill${onlineCount === 0 ? " low" : ""}"
                      style=${`--signal-pct:${onlinePct}%`}
                    ></div>
                  </div>`
                : nothing}
            </button>

            <button
              type="button"
              id="sys-tile-areas"
              @click=${() => store.openSystemSection("area_tracking")}
              class="status-tile"
            >
              <div class="status-tile-head">
                ${renderSvgIcon(SYS_ICON_AREAS)}
                <span>Area Presence</span>
              </div>
              <strong class="status-tile-value">
                ${totalAreas > 0 ? `${fmtNumber(occupiedAreasCount, store.hass, 0)} Occupied` : "—"}
              </strong>
              <span class="status-tile-meta">
                ${totalAreas > 0
                  ? `${fmtNumber(totalAreas, store.hass, 0)} ${totalAreas === 1 ? "Area" : "Areas"} • ${fmtNumber(bleProxyCount, store.hass, 0)} BLE ${bleProxyCount === 1 ? "proxy" : "proxies"}`
                  : "No Areas configured"}
              </span>
            </button>

            <button
              type="button"
              id="sys-tile-roaming"
              @click=${() =>
                store.openDevicesWithCategory(
                  assignedPeopleCount > 0
                    ? "assigned_person"
                    : bleTrackedCount > 0
                      ? "ble_tracked"
                      : "roaming",
                )}
              class="status-tile"
            >
              <div class="status-tile-head">
                ${renderSvgIcon(SYS_ICON_ROAMING)}
                <span>People &amp; Roaming</span>
              </div>
              <strong class="status-tile-value">
                ${fmtNumber(bleTrackedCount, store.hass, 0)} Tracked
              </strong>
              <span class="status-tile-meta">
                ${fmtNumber(assignedPeopleCount, store.hass, 0)}
                ${assignedPeopleCount === 1 ? "person" : "people"} assigned
              </span>
            </button>

            <button
              type="button"
              id="sys-tile-release"
              @click=${() =>
                updatesCount > 0
                  ? store.openDevicesWithCategory("updates")
                  : store.openSystemSection("system_tools")}
              class="status-tile"
            >
              <div class="status-tile-head">
                ${renderSvgIcon(SYS_ICON_RELEASE)}
                <span>System Release</span>
              </div>
              <strong class="status-tile-value">${verText}</strong>
              <span class="status-tile-meta">
                ${updatesCount > 0
                  ? `${fmtNumber(updatesCount, store.hass, 0)} FW ${updatesCount === 1 ? "update" : "updates"} available`
                  : totalCount > 0
                    ? "Firmware up to date"
                    : "Latter hub active"}
              </span>
            </button>
          </div>`,
          footerActions: html`<button
              type="button"
              @click=${() => store.openHaPage("/config/repairs")}
              class="btn btn-text"
            >
              Open Repairs
            </button>
            <button
              type="button"
              @click=${() => void store.checkSystemUpdates()}
              class="btn btn-text"
            >
              Check Firmware Updates
            </button>`,
        })}

        ${renderCard({
          id: "card-area-deployment",
          title: "Area Deployment",
          subtitle: "Live occupancy, assigned Devices, and Bluetooth coverage across your Areas.",
          headerActions: html`<button
            type="button"
            @click=${() => store.openSystemSection("area_tracking")}
            class="btn btn-text btn-compact"
          >
            Manage Presence
          </button>`,
          contentClass: "stack",
          body: html`${roamingDevices.length > 0
              ? html`<button
                  type="button"
                  id="sys-deploy-roaming"
                  @click=${() => store.openDevicesWithCategory("roaming")}
                  class="overview-box"
                >
                  <div class="overview-box-head">
                    <span class="overview-box-title">
                      ${renderSvgIcon(SYS_ICON_ROAMING)}
                      <span>Roaming Devices</span>
                    </span>
                    <span class="overview-box-end">
                      <span class="chip ${roamingOnlineCount > 0 ? "chip-primary" : ""}">
                        ${fmtNumber(roamingOnlineCount, store.hass, 0)} /
                        ${fmtNumber(roamingDevices.length, store.hass, 0)} Active
                      </span>
                      <span class="overview-box-chevron" aria-hidden="true">›</span>
                    </span>
                  </div>
                  <span class="overview-box-meta">
                    ${roamingDevices
                      .slice(0, 4)
                      .map((d) =>
                        d.active_area_name && d.is_online
                          ? `${d.title} (${d.active_area_name})`
                          : d.title,
                      )
                      .join(" • ")}${roamingDevices.length > 4
                      ? ` • +${fmtNumber(roamingDevices.length - 4, store.hass, 0)} more`
                      : ""}
                  </span>
                </button>`
              : nothing}
            ${shownAreas.length > 0
              ? shownAreas.map((area) => {
                  const detailParts: string[] = [];
                  if (area.stationedTitles.length > 0) {
                    detailParts.push(area.stationedTitles.join(", "));
                  }
                  if (area.roamingHereTitles.length > 0) {
                    detailParts.push(`Here: ${area.roamingHereTitles.join(", ")}`);
                  } else if (area.occupants.length > 0) {
                    detailParts.push(area.occupants.join(", "));
                  }
                  if (area.remoteCount > 0) {
                    detailParts.push(
                      `${fmtNumber(area.remoteCount, store.hass, 0)} ${area.remoteCount === 1 ? "remote" : "remotes"}`,
                    );
                  }
                  if (area.activeSensorCount > 0) {
                    detailParts.push(
                      `${fmtNumber(area.activeSensorCount, store.hass, 0)} active ${area.activeSensorCount === 1 ? "sensor" : "sensors"}`,
                    );
                  } else if (area.sensorCount > 0) {
                    detailParts.push(
                      `${fmtNumber(area.sensorCount, store.hass, 0)} ${area.sensorCount === 1 ? "sensor" : "sensors"}`,
                    );
                  }
                  if (!detailParts.length) {
                    detailParts.push(area.isOccupied ? "Occupied" : "No Devices stationed");
                  }
                  const needsCoverageHint =
                    !area.hasSignature &&
                    !area.hasBleProxy &&
                    (area.stationedTitles.length > 0 || area.sensorCount > 0);

                  return html`<button
                    type="button"
                    @click=${() => store.openSystemSection("area_tracking", `area-box-${area.areaId}`)}
                    class="overview-box"
                  >
                    <div class="overview-box-head">
                      <span class="overview-box-title">
                        <span>${area.areaName}</span>
                        ${area.floorLabel ? html`<span class="chip">${area.floorLabel}</span>` : nothing}
                      </span>
                      <span class="overview-box-end">
                        ${area.isOccupied
                          ? html`<span class="chip chip-success">Occupied</span>`
                          : nothing}
                        ${area.hasSignature
                          ? html`<span class="chip chip-primary">
                              Signature (${fmtNumber(area.scannerCount, store.hass, 0)})
                            </span>`
                          : area.hasBleProxy
                            ? html`<span class="chip">BLE Proxy</span>`
                            : html`<span class="chip ${needsCoverageHint ? "chip-warning" : ""}">
                                No BLE Proxy
                              </span>`}
                        <span class="overview-box-chevron" aria-hidden="true">›</span>
                      </span>
                    </div>
                    <span class="overview-box-meta">${detailParts.join(" • ")}</span>
                  </button>`;
                })
              : roamingDevices.length === 0
                ? html`<p class="empty-state">
                    No Home Assistant Areas or Managed Devices configured yet.
                  </p>`
                : nothing}
            ${unconfiguredAreaCount > 0
              ? html`<p class="help-text">
                  +${fmtNumber(unconfiguredAreaCount, store.hass, 0)} additional Home Assistant
                  ${unconfiguredAreaCount === 1 ? "Area" : "Areas"} without Latter Devices or BLE
                  coverage.
                </p>`
              : nothing}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-system-capabilities",
          title: "System Capabilities",
          subtitle: "Shared entities, media routing, Device Groups, themes, and security policies.",
          contentClass: "stack",
          body: html`<button
              type="button"
              id="cap-home-hub"
              @click=${() => store.openSystemSection("shared_entities", "card-whole-home")}
              class="overview-box"
            >
              <div class="overview-box-head">
                <span class="overview-box-title">
                  ${renderSvgIcon(SYS_ICON_HOME)}
                  <span>Home Hub &amp; Weather</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip ${wholeHomeActiveCount > 0 ? "chip-primary" : ""}">
                    ${fmtNumber(wholeHomeActiveCount, store.hass, 0)} / 6 Active
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              <div class="overview-chips">
                ${wholeHomeStatuses.map(
                  (s) =>
                    html`<span class="chip ${s.configured ? "chip-primary" : ""}">
                      ${s.configured ? `✓ ${s.label}` : s.label}
                    </span>`,
                )}
              </div>
            </button>

            <button
              type="button"
              id="cap-cameras-calendars"
              @click=${() =>
                store.openSystemSection(
                  "shared_entities",
                  camerasCount === 0 && calendarsCount > 0 ? "card-calendars" : "card-cameras-doorbell",
                )}
              class="overview-box"
            >
              <div class="overview-box-head">
                <span class="overview-box-title">
                  ${renderSvgIcon(SYS_ICON_CAMERA)}
                  <span>Cameras, Doorbells &amp; Calendars</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip ${camerasCount + calendarsCount > 0 ? "chip-primary" : ""}">
                    ${camerasCount + calendarsCount > 0 ? "Active" : "Not Set"}
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              ${camerasCount + calendarsCount > 0
                ? html`<div class="overview-chips">
                    <span class="chip ${camerasCount > 0 ? "chip-primary" : ""}">
                      ${fmtNumber(camerasCount, store.hass, 0)}
                      ${camerasCount === 1 ? "Camera" : "Cameras"}
                    </span>
                    ${camerasCount > 0
                      ? html`<span class="chip ${doorbellsCount > 0 ? "chip-primary" : ""}">
                          ${fmtNumber(doorbellsCount, store.hass, 0)}
                          ${doorbellsCount === 1 ? "Doorbell" : "Doorbells"}
                        </span>`
                      : nothing}
                    <span class="chip ${calendarsCount > 0 ? "chip-primary" : ""}">
                      ${fmtNumber(calendarsCount, store.hass, 0)}
                      ${calendarsCount === 1 ? "Calendar" : "Calendars"}
                    </span>
                  </div>`
                : html`<span class="overview-box-meta">
                    Connect cameras for doorbell popups and calendars for the Home agenda.
                  </span>`}
            </button>

            <button
              type="button"
              id="cap-media-remotes"
              @click=${() => store.openSystemSection("remotes")}
              class="overview-box"
            >
              <div class="overview-box-head">
                <span class="overview-box-title">
                  ${renderSvgIcon(SYS_ICON_REMOTE)}
                  <span>Media &amp; Remotes</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip ${remotesCount + volCount > 0 ? "chip-primary" : ""}">
                    ${remotesCount > 0
                      ? `${fmtNumber(remotesCount, store.hass, 0)} ${remotesCount === 1 ? "Remote" : "Remotes"}`
                      : volCount > 0
                        ? "Active"
                        : "Not Set"}
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              <span class="overview-box-meta">
                ${remotesCount + remoteGroupsCount + volCount > 0
                  ? `${fmtNumber(remoteGroupsCount, store.hass, 0)} Area ${remoteGroupsCount === 1 ? "group" : "groups"} • ${fmtNumber(volCount, store.hass, 0)} volume ${volCount === 1 ? "override" : "overrides"}`
                  : "Add TV, streaming, or AV receiver remotes and volume overrides."}
              </span>
            </button>

            <button
              type="button"
              id="cap-device-groups"
              @click=${() => store.openSystemSection("system_sync")}
              class="overview-box"
            >
              <div class="overview-box-head">
                <span class="overview-box-title">
                  ${renderSvgIcon(SYS_ICON_GROUPS)}
                  <span>Device Groups</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip">
                    ${fmtNumber(groups.length, store.hass, 0)}
                    ${groups.length === 1 ? "Group" : "Groups"}
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              ${populatedGroupChips.length > 0
                ? html`<div class="overview-chips">
                    ${populatedGroupChips.map(
                      (gc) =>
                        html`<span class="chip ${gc.active ? "chip-primary" : ""}">${gc.label}</span>`,
                    )}
                  </div>`
                : html`<span class="overview-box-meta">
                    Shared baselines across Pocket Carry, Handhelds, Wearables, and Wall &amp; Desk Panels.
                  </span>`}
            </button>

            <button
              type="button"
              id="cap-colors-wallpapers"
              @click=${() =>
                store.openSystemSection(
                  "shared_entities",
                  colorsCount > 0 ? "card-custom-colors" : "card-system-wallpapers",
                )}
              class="overview-box"
            >
              <div class="overview-box-head">
                <span class="overview-box-title">
                  ${renderSvgIcon(SYS_ICON_PALETTE)}
                  <span>Colors &amp; Wallpapers</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip">
                    ${fmtNumber(wallpapersCount, store.hass, 0)}
                    ${wallpapersCount === 1 ? "Wallpaper" : "Wallpapers"}
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              ${colorsCount > 0
                ? html`<div class="swatch-strip" aria-hidden="true">
                    ${palettes.slice(0, 8).map((p) => {
                      const swStyle = `--swatch-color:${p.hex.toUpperCase()}`;
                      return html`<span class="swatch swatch-sm" style=${swStyle}></span>`;
                    })}
                    ${colorsCount > 8
                      ? html`<span class="chip">+${fmtNumber(colorsCount - 8, store.hass, 0)}</span>`
                      : nothing}
                  </div>`
                : nothing}
              <span class="overview-box-meta">
                ${fmtNumber(colorsCount, store.hass, 0)} custom
                ${colorsCount === 1 ? "color" : "colors"} •
                ${fmtNumber(presetWallpapersCount, store.hass, 0)}
                ${presetWallpapersCount === 1 ? "preset" : "presets"}${uploadedWallpapersCount > 0
                  ? `, ${fmtNumber(uploadedWallpapersCount, store.hass, 0)} uploaded`
                  : ""}
              </span>
            </button>

            <button
              type="button"
              id="cap-perimeter-security"
              @click=${() => store.openSystemSection("system_tools", "card-perimeter-security")}
              class="overview-box"
            >
              <div class="overview-box-head">
                <span class="overview-box-title">
                  ${renderSvgIcon(SYS_ICON_SHIELD)}
                  <span>Perimeter Security</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip ${hasSystemPin ? "chip-success" : ""}">
                    ${hasSystemPin ? "System PIN Set" : "No System PIN"}
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              <span class="overview-box-meta">
                ${hasSystemPin
                  ? "Default PIN active for opening locks, garage covers, and code-less alarms."
                  : "Set a fallback System Security PIN for perimeter locks, covers, and alarms."}
              </span>
            </button>`,
        })}
      </div>
    </div>
  </section>`;
}
