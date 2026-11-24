/**
 * System Overview View (`system_overview`, `D-003`, `D-004`, `D-051`, `D-061`, `D-066`, `D-076`):
 * - Conditional top region for active Home Assistant Repairs (`role="region"` + heading)
 *   and unbound Discovered Latter hardware.
 * - Column 1: High-level Status card (`D-003` release meta, `D-004` People & roaming, `D-076`
 *   Sleeping / Away / Offline / Low-battery operational distinction).
 * - Column 2: Area deployment promoted above the fold (strict `area_id` matching).
 */

import { renderCard, renderSvgIcon } from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { AreaPresenceRow, BleAreaSignatureSummary, SystemDeviceEntry } from "../types.js";
import { fmtNumber, issueMessage } from "../utils/format.js";

const SYS_ICON_DEVICES =
  "M4,6H20V16H4M20,18A2,2 0 0,0 22,16V6C22,4.89 21.1,4 20,4H4C2.89,4 2,4.89 2,6V16A2,2 0 0,0 4,18H0V20H24V18H20Z";
const SYS_ICON_AREAS =
  "M12,6.5A2.5,2.5 0 0,1 14.5,9A2.5,2.5 0 0,1 12,11.5A2.5,2.5 0 0,1 9.5,9A2.5,2.5 0 0,1 12,6.5M12,2A7,7 0 0,1 19,9C19,14.25 12,22 12,22C12,22 5,14.25 5,9A7,7 0 0,1 12,2M12,4A5,5 0 0,0 7,9C7,10 7,12 12,18.71C17,12 17,10 17,9A5,5 0 0,0 12,4Z";
const SYS_ICON_ROAMING =
  "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12C22,10.84 21.79,9.69 21.39,8.61L19.79,10.21C19.93,10.8 20,11.4 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4C12.6,4 13.2,4.07 13.79,4.21L15.4,2.6C14.31,2.21 13.16,2 12,2M19,2A2,2 0 0,0 17,4A2,2 0 0,0 19,6A2,2 0 0,0 21,4A2,2 0 0,0 19,2M12,6A6,6 0 0,0 6,12A6,6 0 0,0 12,18A6,6 0 0,0 18,12H16A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8V6M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10Z";
const SYS_ICON_RELEASE =
  "M17,17H7V7H17M21,11V9H19V7C19,5.89 18.1,5 17,5H15V3H13V5H11V3H9V5H7C5.89,5 5,5.89 5,7V9H3V11H5V13H3V15H5V17A2,2 0 0,0 7,19H9V21H11V19H13V21H15V19H17A2,2 0 0,0 19,17V15H21V13H19V11M15,15H9V9H15V15Z";

function isDeviceSleeping(d: SystemDeviceEntry): boolean {
  return (
    !d.is_online &&
    d.kind !== "ble_tag" &&
    String(d.status_label || "").trim().toLowerCase() === "sleeping"
  );
}

function isDeviceAway(d: SystemDeviceEntry): boolean {
  return (
    !d.is_online &&
    d.kind === "ble_tag" &&
    (d.status_code === "away" || String(d.status_label || "").trim().toLowerCase() === "away")
  );
}

function isDeviceScanning(d: SystemDeviceEntry): boolean {
  return (
    !d.is_online &&
    d.kind === "ble_tag" &&
    (d.status_code === "scanning" ||
      String(d.status_label || "").trim().toLowerCase() === "scanning")
  );
}

function isDeviceLowBattery(d: SystemDeviceEntry): boolean {
  return (
    d.kind !== "ble_tag" &&
    Boolean(d.has_battery) &&
    !d.is_charging &&
    d.battery_level !== null &&
    d.battery_level !== undefined &&
    Number.isFinite(Number(d.battery_level)) &&
    Number(d.battery_level) <= 20
  );
}

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
  const sysCfg = data?.system_config;
  const presenceRows = data?.live?.area_presence_grid || [];
  const signatures = data?.ble_area_signatures || [];

  const totalCount = allDevices.length;
  const onlineCount = allDevices.filter((d) => d.is_online).length;
  const sleepingCount = allDevices.filter((d) => isDeviceSleeping(d)).length;
  const awayCount = allDevices.filter((d) => isDeviceAway(d)).length;
  const scanningCount = allDevices.filter((d) => isDeviceScanning(d)).length;
  const unexpectedOfflineCount = Math.max(
    0,
    totalCount - onlineCount - sleepingCount - awayCount - scanningCount,
  );
  const lowBatteryCount = allDevices.filter((d) => isDeviceLowBattery(d)).length;

  const displayCount = allDevices.filter((d) => d.kind !== "ble_tag" && d.has_display).length;
  const phoneCount = allDevices.filter(
    (d) => d.kind === "ble_tag" && d.ble_category === "phone",
  ).length;
  const bleTagOnlyCount = allDevices.filter(
    (d) => d.kind === "ble_tag" && d.ble_category !== "phone",
  ).length;
  const screenlessCount = allDevices.filter(
    (d) => d.kind !== "ble_tag" && !d.has_display,
  ).length;
  const bleTrackedCount = allDevices.filter((d) => d.ble_tracked || d.kind === "ble_tag").length;
  const assignedPeopleCount = allDevices.filter((d) => Boolean(d.assigned_person)).length;

  const updatesCount = Math.max(
    allDevices.filter((d) => d.status_code === "update" || d.status_label === "Update available")
      .length,
    Number(data?.update_check?.available || 0),
  );
  const hasVerifiedUpToDate = Boolean(data?.update_check && data.update_check.checked > 0);
  const verText = data?.version
    ? `v${String(data.version).replace(/^v/i, "")}`
    : store.t("common.unknown");
  const bleProxyCount = Number(data?.ble_proxy_count ?? 0);

  const hasErrorIssue = issues.some((i) => i.severity === "error" || i.severity === "critical");

  let sysChipClass = "chip";
  let sysDotClass = "status-dot";
  let sysStatusLabel = store.t("sys_overview.no_devices");
  if (issues.length > 0) {
    sysChipClass = hasErrorIssue ? "chip chip-error" : "chip chip-warning";
    sysDotClass = "status-dot update";
    sysStatusLabel =
      issues.length === 1
        ? store.t("sys_overview.issues_one")
        : store.t("sys_overview.issues_many", { count: fmtNumber(issues.length, store.hass, 0) });
  } else if (totalCount > 0 && updatesCount > 0) {
    sysChipClass = "chip chip-warning";
    sysDotClass = "status-dot update";
    sysStatusLabel =
      updatesCount === 1
        ? store.t("sys_overview.updates_one")
        : store.t("sys_overview.updates_many", {
            count: fmtNumber(updatesCount, store.hass, 0),
          });
  } else if (totalCount > 0 && unexpectedOfflineCount === totalCount) {
    sysStatusLabel = store.t("status.offline");
  } else if (totalCount > 0 && unexpectedOfflineCount > 0) {
    sysChipClass = "chip chip-warning";
    sysDotClass = "status-dot update";
    sysStatusLabel = store.t("sys_overview.offline_count", {
      count: fmtNumber(unexpectedOfflineCount, store.hass, 0),
    });
  } else if (totalCount > 0 && lowBatteryCount > 0) {
    sysChipClass = "chip chip-warning";
    sysDotClass = "status-dot update";
    sysStatusLabel = store.t("sys_overview.low_battery_count", {
      count: fmtNumber(lowBatteryCount, store.hass, 0),
    });
  } else if (totalCount > 0 && onlineCount === totalCount) {
    sysChipClass = "chip chip-success";
    sysDotClass = "status-dot online";
    sysStatusLabel = store.t("sys_overview.all_online");
  } else if (totalCount > 0) {
    sysChipClass = "chip chip-success";
    sysDotClass = "status-dot online";
    sysStatusLabel = store.t("sys_overview.healthy");
  }

  const onlinePct = totalCount > 0 ? Math.round((onlineCount / totalCount) * 100) : 0;
  const onlineSigStyle = `--signal-pct:${onlinePct}%`;
  const devMetaParts: string[] = [];
  if (totalCount === 0) {
    devMetaParts.push(store.t("sys_overview.ready_to_onboard"));
  } else {
    const hasNonOnlineState =
      unexpectedOfflineCount > 0 || sleepingCount > 0 || awayCount > 0 || scanningCount > 0;
    if (unexpectedOfflineCount > 0) {
      devMetaParts.push(
        store.t("sys_overview.offline_count", {
          count: fmtNumber(unexpectedOfflineCount, store.hass, 0),
        }),
      );
    }
    if (lowBatteryCount > 0) {
      devMetaParts.push(
        store.t("sys_overview.low_battery_count", {
          count: fmtNumber(lowBatteryCount, store.hass, 0),
        }),
      );
    }
    if (sleepingCount > 0) {
      devMetaParts.push(
        store.t("sys_overview.sleeping_count", {
          count: fmtNumber(sleepingCount, store.hass, 0),
        }),
      );
    }
    if (awayCount > 0) {
      devMetaParts.push(
        store.t("sys_overview.away_count", {
          count: fmtNumber(awayCount, store.hass, 0),
        }),
      );
    }
    if (scanningCount > 0) {
      devMetaParts.push(
        store.t("sys_overview.scanning_count", {
          count: fmtNumber(scanningCount, store.hass, 0),
        }),
      );
    }
    if (!hasNonOnlineState) {
      if (displayCount > 0 || screenlessCount === 0) {
        devMetaParts.push(
          displayCount === 1
            ? store.t("sys_overview.displays_one")
            : store.t("sys_overview.displays_many", {
                count: fmtNumber(displayCount, store.hass, 0),
              }),
        );
      }
      if (screenlessCount > 0) {
        devMetaParts.push(
          screenlessCount === 1
            ? store.t("sys_overview.screenless_one")
            : store.t("sys_overview.screenless_many", {
                count: fmtNumber(screenlessCount, store.hass, 0),
              }),
        );
      }
      if (phoneCount > 0) {
        devMetaParts.push(
          phoneCount === 1
            ? store.t("sys_overview.phones_one")
            : store.t("sys_overview.phones_many", { count: fmtNumber(phoneCount, store.hass, 0) }),
        );
      }
      if (bleTagOnlyCount > 0) {
        devMetaParts.push(
          bleTagOnlyCount === 1
            ? store.t("sys_overview.ble_tags_one")
            : store.t("sys_overview.ble_tags_many", {
                count: fmtNumber(bleTagOnlyCount, store.hass, 0),
              }),
        );
      }
    }
  }

  // Build unified Area Deployment map matching Areas strictly by `area_id`
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

    const stationedTitles = allDevices
      .filter((d) => d.has_assigned_area && d.area_id === areaId)
      .map((d) => d.title);
    const roamingHereTitles = allDevices
      .filter((d) => !d.has_assigned_area && (d.is_online || isDeviceSleeping(d)) && d.area_id === areaId)
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
    if (aDev > 0 !== bDev > 0) return aDev > 0 ? -1 : 1;
    return a.areaName.localeCompare(b.areaName, undefined, { sensitivity: "base" });
  });

  const totalAreas = areaEntries.length;
  const occupiedAreasCount = areaEntries.filter((a) => a.isOccupied).length;
  const deployedAreas = areaEntries.filter((a) => a.isDeployed);
  const shownAreas = deployedAreas.length > 0 ? deployedAreas : areaEntries.slice(0, 6);
  const unconfiguredAreaCount =
    deployedAreas.length > 0
      ? Math.max(0, totalAreas - deployedAreas.length)
      : Math.max(0, totalAreas - shownAreas.length);

  const roamingDevices = allDevices.filter(
    (d) => !d.has_assigned_area && (d.is_roaming || d.kind === "ble_tag"),
  );
  const roamingActiveCount = roamingDevices.filter(
    (d) => d.is_online || isDeviceSleeping(d),
  ).length;

  const discoveredPreviewNames =
    discoveredLatter
      .slice(0, 3)
      .map((d) => d.title || d.node_name)
      .join(", ") + (discoveredLatter.length > 3 ? "…" : "");

  return html`<section id="view-system_overview" class="stack">
    ${issues.length
      ? html`<div
          id="sys-issues-banner"
          role="region"
          aria-labelledby="sys-issues-heading"
          class="alert ${hasErrorIssue ? "alert-error" : "alert-warning"}"
        >
          <div class="alert-body">
            <h2 id="sys-issues-heading" class="row-label">
              ${store.t("status.needs_attention")}
            </h2>
            <ul class="alert-list">
              ${issues.map(
                (iss) => html`<li>
                  <strong>${iss.device_title || store.t("shell.title")}:</strong>
                  ${issueMessage(iss, store.hass)}
                  ${iss.subentry_id
                    ? html`<button
                        type="button"
                        @click=${() => void store.switchSystemDevice(String(iss.subentry_id))}
                        class="btn btn-text btn-compact"
                      >
                        ${store.t("sys_overview.open_device")}
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
            ${store.t("action.open_repairs")}
          </button>
        </div>`
      : nothing}

    ${discoveredLatter.length
      ? html`<div id="sys-discovered-banner" class="alert">
          <div class="alert-body">
            <strong>${store.t("sys_overview.discovered_banner_title")}</strong>
            <p class="row-description">
              ${discoveredLatter.length === 1
                ? store.t("sys_overview.discovered_banner_one", { names: discoveredPreviewNames })
                : store.t("sys_overview.discovered_banner_many", {
                    count: fmtNumber(discoveredLatter.length, store.hass, 0),
                    names: discoveredPreviewNames,
                  })}
            </p>
          </div>
          <button
            type="button"
            @click=${() => store.openDiscoveredDevices("card-discovered-latter")}
            class="btn btn-secondary btn-compact"
          >
            ${store.t("sys_overview.open_discovered")}
          </button>
        </div>`
      : nothing}

    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-system-status",
          title: store.t("card.status"),
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
                <span>${store.t("sys_overview.tile_devices")}</span>
              </div>
              <strong class="status-tile-value">
                ${totalCount > 0
                  ? store.t("sys_overview.online_ratio", {
                      online: fmtNumber(onlineCount, store.hass, 0),
                      total: fmtNumber(totalCount, store.hass, 0),
                    })
                  : store.t("sys_overview.zero_devices")}
              </strong>
              <span class="status-tile-meta">${devMetaParts.join(" • ")}</span>
              ${totalCount > 0
                ? html`<div class="signal-track" aria-hidden="true">
                    <div
                      class="signal-fill${unexpectedOfflineCount > 0 && onlineCount === 0 ? " low" : ""}"
                      style=${onlineSigStyle}
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
                <span>${store.t("sys_overview.tile_areas")}</span>
              </div>
              <strong class="status-tile-value">
                ${totalAreas > 0
                  ? store.t("sys_overview.occupied_count", {
                      count: fmtNumber(occupiedAreasCount, store.hass, 0),
                    })
                  : store.t("common.unknown")}
              </strong>
              <span class="status-tile-meta">
                ${totalAreas > 0
                  ? store.t("sys_overview.areas_proxies_meta", {
                      areas:
                        totalAreas === 1
                          ? store.t("sys_overview.areas_one")
                          : store.t("sys_overview.areas_many", {
                              count: fmtNumber(totalAreas, store.hass, 0),
                            }),
                      proxies:
                        bleProxyCount === 1
                          ? store.t("sys_overview.proxies_one")
                          : store.t("sys_overview.proxies_many", {
                              count: fmtNumber(bleProxyCount, store.hass, 0),
                            }),
                    })
                  : store.t("sys_overview.no_areas")}
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
                <span>${store.t("sys_overview.tile_people_roaming")}</span>
              </div>
              <strong class="status-tile-value">
                ${assignedPeopleCount === 1
                  ? store.t("sys_overview.people_assigned_one")
                  : store.t("sys_overview.people_assigned_many", {
                      count: fmtNumber(assignedPeopleCount, store.hass, 0),
                    })}
              </strong>
              <span class="status-tile-meta">
                ${store.t("sys_overview.ble_tracked_meta", {
                  count: fmtNumber(bleTrackedCount, store.hass, 0),
                })}
              </span>
            </button>

            <button
              type="button"
              id="sys-tile-release"
              @click=${() =>
                updatesCount > 0
                  ? store.openDevicesWithCategory("updates")
                  : store.openSystemSection("system_tools", "card-support-diagnostics")}
              class="status-tile"
            >
              <div class="status-tile-head">
                ${renderSvgIcon(SYS_ICON_RELEASE)}
                <span>${store.t("sys_overview.tile_release")}</span>
              </div>
              <strong class="status-tile-value">${verText}</strong>
              <span class="status-tile-meta">
                ${updatesCount > 0
                  ? updatesCount === 1
                    ? store.t("sys_overview.fw_updates_one")
                    : store.t("sys_overview.fw_updates_many", {
                        count: fmtNumber(updatesCount, store.hass, 0),
                      })
                  : hasVerifiedUpToDate
                    ? store.t("status.up_to_date")
                    : store.t("common.unknown")}
              </span>
            </button>
          </div>`,
          footerActions: html`<button
              type="button"
              @click=${() => store.openHaPage("/config/repairs")}
              class="btn btn-text"
            >
              ${store.t("action.open_repairs")}
            </button>
            <button
              type="button"
              @click=${() => void store.tools.checkSystemUpdates()}
              class="btn btn-text"
            >
              ${store.t("sys_overview.check_fw_updates")}
            </button>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-area-deployment",
          title: store.t("card.area_deployment"),
          subtitle: store.t("sys_overview.area_deployment_subtitle"),
          headerActions: html`<button
            type="button"
            @click=${() => store.openSystemSection("area_tracking")}
            class="btn btn-text btn-compact"
          >
            ${store.t("sys_overview.manage_presence")}
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
                      <span>${store.t("sys_overview.roaming_devices")}</span>
                    </span>
                    <span class="overview-box-end">
                      <span class="chip ${roamingActiveCount > 0 ? "chip-primary" : ""}">
                        ${store.t("sys_overview.roaming_active_ratio", {
                          online: fmtNumber(roamingActiveCount, store.hass, 0),
                          total: fmtNumber(roamingDevices.length, store.hass, 0),
                        })}
                      </span>
                      <span class="overview-box-chevron" aria-hidden="true">›</span>
                    </span>
                  </div>
                  <span class="overview-box-meta">
                    ${roamingDevices
                      .slice(0, 4)
                      .map((d) =>
                        d.area_id && d.active_area_name && (d.is_online || isDeviceSleeping(d))
                          ? `${d.title} (${d.active_area_name})`
                          : d.title,
                      )
                      .join(" • ")}${roamingDevices.length > 4
                      ? ` • ${store.t("sys_overview.plus_more", {
                          count: fmtNumber(roamingDevices.length - 4, store.hass, 0),
                        })}`
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
                    detailParts.push(
                      store.t("sys_overview.here_prefix", {
                        names: area.roamingHereTitles.join(", "),
                      }),
                    );
                  } else if (area.occupants.length > 0) {
                    detailParts.push(area.occupants.join(", "));
                  }
                  if (area.remoteCount > 0) {
                    detailParts.push(
                      area.remoteCount === 1
                        ? store.t("sys_overview.remotes_one")
                        : store.t("sys_overview.remotes_many", {
                            count: fmtNumber(area.remoteCount, store.hass, 0),
                          }),
                    );
                  }
                  if (area.activeSensorCount > 0) {
                    detailParts.push(
                      area.activeSensorCount === 1
                        ? store.t("sys_overview.active_sensors_one")
                        : store.t("sys_overview.active_sensors_many", {
                            count: fmtNumber(area.activeSensorCount, store.hass, 0),
                          }),
                    );
                  } else if (area.sensorCount > 0) {
                    detailParts.push(
                      area.sensorCount === 1
                        ? store.t("sys_overview.sensors_one")
                        : store.t("sys_overview.sensors_many", {
                            count: fmtNumber(area.sensorCount, store.hass, 0),
                          }),
                    );
                  }
                  if (!detailParts.length) {
                    detailParts.push(
                      area.isOccupied
                        ? store.t("sys_overview.occupied")
                        : store.t("sys_overview.no_devices_stationed"),
                    );
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
                          ? html`<span class="chip chip-success">
                              ${store.t("sys_overview.occupied")}
                            </span>`
                          : nothing}
                        ${area.hasSignature
                          ? html`<span class="chip chip-primary">
                              ${store.t("sys_overview.signature_count", {
                                count: fmtNumber(area.scannerCount, store.hass, 0),
                              })}
                            </span>`
                          : area.hasBleProxy
                            ? html`<span class="chip">${store.t("sys_overview.ble_proxy")}</span>`
                            : html`<span class="chip ${needsCoverageHint ? "chip-warning" : ""}">
                                ${store.t("sys_overview.no_ble_proxy")}
                              </span>`}
                        <span class="overview-box-chevron" aria-hidden="true">›</span>
                      </span>
                    </div>
                    <span class="overview-box-meta">${detailParts.join(" • ")}</span>
                  </button>`;
                })
              : roamingDevices.length === 0
                ? html`<p class="empty-state">${store.t("sys_overview.empty_deployment")}</p>`
                : nothing}
            ${unconfiguredAreaCount > 0
              ? html`<p class="help-text">
                  ${unconfiguredAreaCount === 1
                    ? store.t("sys_overview.unconfigured_areas_one")
                    : store.t("sys_overview.unconfigured_areas_many", {
                        count: fmtNumber(unconfiguredAreaCount, store.hass, 0),
                      })}
                </p>`
              : nothing}`,
        })}
      </div>
    </div>
  </section>`;
}
