/**
 * System Overview View (`system_overview`, `D-003`, `D-004`, `D-051`, `D-061`, `D-066`):
 * - Conditional top region for active Home Assistant Repairs (`role="region"` + heading, `D-21`)
 *   and unbound Discovered Latter hardware.
 * - Column 1: High-level Status card (`D-003` release meta, `D-004` People & roaming) +
 *   Area deployment (`area_id` matching `E-21`).
 * - Column 2: System capabilities (dynamic group names `E-25`, `"colors & wallpapers"` `E-22`,
 *   `isValidHexColor` swatch guard `A-07`).
 */

import { renderCard, renderSvgIcon } from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import { isPhotoUploaded } from "../state/photo-ops.js";
import type { StudioStore } from "../state/store.js";
import type { AreaPresenceRow, BleAreaSignatureSummary } from "../types.js";
import { fmtNumber, issueMessage, isValidHexColor } from "../utils/format.js";

const SYS_ICON_DEVICES =
  "M4,6H20V16H4M20,18A2,2 0 0,0 22,16V6C22,4.89 21.1,4 20,4H4C2.89,4 2,4.89 2,6V16A2,2 0 0,0 4,18H0V20H24V18H20Z";
const SYS_ICON_AREAS =
  "M12,6.5A2.5,2.5 0 0,1 14.5,9A2.5,2.5 0 0,1 12,11.5A2.5,2.5 0 0,1 9.5,9A2.5,2.5 0 0,1 12,6.5M12,2A7,7 0 0,1 19,9C19,14.25 12,22 12,22C12,22 5,14.25 5,9A7,7 0 0,1 12,2M12,4A5,5 0 0,0 7,9C7,10 7,12 12,18.71C17,12 17,10 17,9A5,5 0 0,0 12,4Z";
const SYS_ICON_ROAMING =
  "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12C22,10.84 21.79,9.69 21.39,8.61L19.79,10.21C19.93,10.8 20,11.4 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4C12.6,4 13.2,4.07 13.79,4.21L15.4,2.6C14.31,2.21 13.16,2 12,2M19,2A2,2 0 0,0 17,4A2,2 0 0,0 19,6A2,2 0 0,0 21,4A2,2 0 0,0 19,2M12,6A6,6 0 0,0 6,12A6,6 0 0,0 12,18A6,6 0 0,0 18,12H16A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8V6M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10Z";
const SYS_ICON_RELEASE =
  "M17,17H7V7H17M21,11V9H19V7C19,5.89 18.1,5 17,5H15V3H13V5H11V3H9V5H7C5.89,5 5,5.89 5,7V9H3V11H5V13H3V15H5V17A2,2 0 0,0 7,19H9V21H11V19H13V21H15V19H17A2,2 0 0,0 19,17V15H21V13H19V11M15,15H9V9H15V15Z";
const SYS_ICON_HOME =
  "M12,3L2,12H5V20H19V12H22L12,3M12,8.75A2.25,2.25 0 0,1 14.25,11A2.25,2.25 0 0,1 12,13.25A2.25,2.25 0 0,1 9.75,11A2.25,2.25 0 0,1 12,8.75M12,15C13.5,15 16.5,15.75 16.5,17.25V18H7.5V17.25C7.5,15.75 10.5,15 12,15Z";
const SYS_ICON_CAMERA =
  "M17,10.5V7A1,1 0 0,0 16,6H4A1,1 0 0,0 3,7V17A1,1 0 0,0 4,18H16A1,1 0 0,0 17,17V13.5L21,17.5V6.5L17,10.5Z";
const SYS_ICON_REMOTE =
  "M9,2A2,2 0 0,0 7,4V20A2,2 0 0,0 9,22H15A2,2 0 0,0 17,20V4A2,2 0 0,0 15,2H9M12,6A3,3 0 0,1 15,9A3,3 0 0,1 12,12A3,3 0 0,1 9,9A3,3 0 0,1 12,6M12,8A1,1 0 0,0 11,9A1,1 0 0,0 12,10A1,1 0 0,0 13,9A1,1 0 0,0 12,8M10,15H14V17H10V15M10,18H14V20H10V18Z";
const SYS_ICON_GROUPS =
  "M3,3H11V11H3V3M13,3H21V11H13V3M3,13H11V21H3V13M13,13H21V21H13V13M5,5V9H9V5H5M15,5V9H19V5H15M5,15V19H9V15H5M15,15V19H19V15H15Z";
const SYS_ICON_PALETTE =
  "M17.5,12A1.5,1.5 0 0,1 16,10.5A1.5,1.5 0 0,1 17.5,9A1.5,1.5 0 0,1 19,10.5A1.5,1.5 0 0,1 17.5,12M14.5,8A1.5,1.5 0 0,1 13,6.5A1.5,1.5 0 0,1 14.5,5A1.5,1.5 0 0,1 16,6.5A1.5,1.5 0 0,1 14.5,8M9.5,8A1.5,1.5 0 0,1 8,6.5A1.5,1.5 0 0,1 9.5,5A1.5,1.5 0 0,1 11,6.5A1.5,1.5 0 0,1 9.5,8M6.5,12A1.5,1.5 0 0,1 5,10.5A1.5,1.5 0 0,1 6.5,9A1.5,1.5 0 0,1 8,10.5A1.5,1.5 0 0,1 6.5,12M12,3A9,9 0 0,0 3,12A9,9 0 0,0 12,21A1.5,1.5 0 0,0 13.5,19.5C13.5,19.11 13.35,18.76 13.11,18.5C12.88,18.23 12.73,17.88 12.73,17.5A1.5,1.5 0 0,1 14.23,16H16A5,5 0 0,0 21,11C21,6.58 16.97,3 12,3Z";
const SYS_ICON_PHOTOS =
  "M22,16V4A2,2 0 0,0 20,2H8A2,2 0 0,0 6,4V16A2,2 0 0,0 8,18H20A2,2 0 0,0 22,16M11,12L13.03,14.71L16,11L20,16H8M2,6V20A2,2 0 0,0 4,22H18V20H4V6";
const SYS_ICON_SHIELD =
  "M12,1L3,5V11C3,16.55 6.84,21.74 12,23C17.16,21.74 21,16.55 21,11V5L12,1M12,7C13.4,7 14.8,8.1 14.8,9.5V11C15.4,11 16,11.6 16,12.3V15.8C16,16.4 15.4,17 14.7,17H9.2C8.6,17 8,16.4 8,15.7V12.2C8,11.6 8.6,11 9.2,11V9.5C9.2,8.1 10.6,7 12,7M12,8.2C11.2,8.2 10.5,8.7 10.5,9.5V11H13.5V9.5C13.5,8.7 12.8,8.2 12,8.2Z";

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
  const phoneCount = allDevices.filter(
    (d) => d.kind === "ble_tag" && d.ble_category === "phone",
  ).length;
  const bleTagOnlyCount = allDevices.filter(
    (d) => d.kind === "ble_tag" && d.ble_category !== "phone",
  ).length;
  const audioOnlyCount = allDevices.filter((d) => d.kind !== "ble_tag" && !d.has_display).length;
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
  } else if (totalCount > 0 && offlineCount === 0) {
    sysChipClass = "chip chip-success";
    sysDotClass = "status-dot online";
    sysStatusLabel = store.t("sys_overview.all_online");
  } else if (totalCount > 0 && onlineCount > 0) {
    sysDotClass = "status-dot online";
    sysStatusLabel = store.t("sys_overview.online_ratio", {
      online: fmtNumber(onlineCount, store.hass, 0),
      total: fmtNumber(totalCount, store.hass, 0),
    });
  } else if (totalCount > 0) {
    sysStatusLabel = store.t("status.offline");
  }

  const onlinePct = totalCount > 0 ? Math.round((onlineCount / totalCount) * 100) : 0;
  const onlineSigStyle = `--signal-pct:${onlinePct}%`;
  const devMetaParts: string[] = [];
  if (totalCount === 0) {
    devMetaParts.push(store.t("sys_overview.ready_to_onboard"));
  } else {
    devMetaParts.push(
      displayCount === 1
        ? store.t("sys_overview.displays_one")
        : store.t("sys_overview.displays_many", {
            count: fmtNumber(displayCount, store.hass, 0),
          }),
    );
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
    } else if (phoneCount === 0 && audioOnlyCount > 0) {
      devMetaParts.push(
        store.t("sys_overview.audio_count", { count: fmtNumber(audioOnlyCount, store.hass, 0) }),
      );
    }
  }

  // Build unified Area Deployment map matching Areas strictly by `area_id` (E-21)
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
      .filter((d) => !d.has_assigned_area && d.is_online && d.area_id === areaId)
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
  const roamingOnlineCount = roamingDevices.filter((d) => d.is_online).length;

  // System Capabilities metrics
  const thermCount = (sysCfg?.thermostat_entities || []).filter((s) =>
    Boolean(String(s || "").trim()),
  ).length;
  const lockCount = (sysCfg?.lock_entities || []).filter((s) =>
    Boolean(String(s || "").trim()),
  ).length;
  const garageCount = (sysCfg?.garage_entities || []).filter((s) =>
    Boolean(String(s || "").trim()),
  ).length;
  const vacCount = (sysCfg?.vacuum_entities || []).filter((s) =>
    Boolean(String(s || "").trim()),
  ).length;

  const wholeHomeStatuses: ReadonlyArray<{ label: string; configured: boolean }> = [
    {
      label: store.t("sys_overview.hub_weather"),
      configured: Boolean(String(sysCfg?.weather_entity || "").trim()),
    },
    {
      label: store.t("sys_overview.hub_alarm"),
      configured: Boolean(String(sysCfg?.alarm_entity || "").trim()),
    },
    {
      label:
        thermCount > 1
          ? store.t("sys_overview.hub_zones", { count: fmtNumber(thermCount, store.hass, 0) })
          : store.t("sys_overview.hub_thermostat"),
      configured: thermCount > 0,
    },
    {
      label:
        lockCount > 1
          ? store.t("sys_overview.hub_locks", { count: fmtNumber(lockCount, store.hass, 0) })
          : store.t("sys_overview.hub_lock"),
      configured: lockCount > 0,
    },
    {
      label:
        garageCount > 1
          ? store.t("sys_overview.hub_garages", { count: fmtNumber(garageCount, store.hass, 0) })
          : store.t("sys_overview.hub_garage"),
      configured: garageCount > 0,
    },
    {
      label:
        vacCount > 1
          ? store.t("sys_overview.hub_vacuums", { count: fmtNumber(vacCount, store.hass, 0) })
          : store.t("sys_overview.hub_vacuum"),
      configured: vacCount > 0,
    },
  ];
  const wholeHomeActiveCount = wholeHomeStatuses.filter((s) => s.configured).length;

  const camerasCount = (sysCfg?.camera_entities || []).filter(Boolean).length;
  const doorbellsCount = (data?.doorbells || []).filter((b) => Boolean(b.ring_entity)).length;
  const calendarsCount = (sysCfg?.calendar_entities || []).filter(Boolean).length;

  const remotesCount = (sysCfg?.remotes_list || []).filter(Boolean).length;
  const remoteGroupsCount = remoteGroups.length;
  const volCount = (sysCfg?.volume_overrides || []).length;

  const validPalettes = (sysCfg?.custom_palettes || []).filter((p) => isValidHexColor(p.hex));
  const colorsCount = validPalettes.length;
  const wallpapers = data?.system_wallpapers || [];
  const wallpapersCount = wallpapers.length;
  const uploadedWallpapersCount = wallpapers.filter((w) => isPhotoUploaded(w)).length;
  const presetWallpapersCount = Math.max(0, wallpapersCount - uploadedWallpapersCount);
  const photoCollectionsCount = (data?.photo_collections || []).length;

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
            ? `${g.name}: ${fmtNumber(cnt, store.hass, 0)}`
            : g.name,
        active: cnt > 0,
      });
    }
  }
  const customGroupCount = latterHardwareDevices.filter(
    (d) => !d.device_group || d.device_group === "custom",
  ).length;
  if (customGroupCount > 0) {
    populatedGroupChips.push({
      label: store.t("sys_overview.custom_group_chip", {
        count: fmtNumber(customGroupCount, store.hass, 0),
      }),
      active: true,
    });
  }

  const configuredGroupNames = groups
    .filter((g) => Boolean(g?.name) && g.id !== "custom")
    .map((g) => g.name);

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
                      class="signal-fill${onlineCount === 0 ? " low" : ""}"
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
                      <span class="chip ${roamingOnlineCount > 0 ? "chip-primary" : ""}">
                        ${store.t("sys_overview.roaming_active_ratio", {
                          online: fmtNumber(roamingOnlineCount, store.hass, 0),
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
                        d.active_area_name && d.is_online
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

      <div class="column">
        ${renderCard({
          id: "card-system-capabilities",
          title: store.t("card.system_capabilities"),
          subtitle: store.t("sys_overview.capabilities_subtitle"),
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
                  <span>${store.t("card.home_hub_weather")}</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip ${wholeHomeActiveCount > 0 ? "chip-primary" : ""}">
                    ${store.t("sys_overview.active_of_six", {
                      count: fmtNumber(wholeHomeActiveCount, store.hass, 0),
                    })}
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
                  camerasCount === 0 && calendarsCount > 0
                    ? "card-calendars"
                    : "card-cameras-doorbell",
                  ["card-cameras-doorbell", "card-calendars"],
                )}
              class="overview-box"
            >
              <div class="overview-box-head">
                <span class="overview-box-title">
                  ${renderSvgIcon(SYS_ICON_CAMERA)}
                  <span>${store.t("sys_overview.cap_cameras_calendars")}</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip ${camerasCount + calendarsCount > 0 ? "chip-primary" : ""}">
                    ${camerasCount + calendarsCount > 0
                      ? store.t("common.active")
                      : store.t("sys_overview.not_set")}
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              ${camerasCount + calendarsCount > 0
                ? html`<div class="overview-chips">
                    <span class="chip ${camerasCount > 0 ? "chip-primary" : ""}">
                      ${camerasCount === 1
                        ? store.t("sys_overview.cameras_one")
                        : store.t("sys_overview.cameras_many", {
                            count: fmtNumber(camerasCount, store.hass, 0),
                          })}
                    </span>
                    ${camerasCount > 0
                      ? html`<span class="chip ${doorbellsCount > 0 ? "chip-primary" : ""}">
                          ${doorbellsCount === 1
                            ? store.t("sys_overview.doorbells_one")
                            : store.t("sys_overview.doorbells_many", {
                                count: fmtNumber(doorbellsCount, store.hass, 0),
                              })}
                        </span>`
                      : nothing}
                    <span class="chip ${calendarsCount > 0 ? "chip-primary" : ""}">
                      ${calendarsCount === 1
                        ? store.t("sys_overview.calendars_one")
                        : store.t("sys_overview.calendars_many", {
                            count: fmtNumber(calendarsCount, store.hass, 0),
                          })}
                    </span>
                  </div>`
                : html`<span class="overview-box-meta">
                    ${store.t("sys_overview.cameras_calendars_empty")}
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
                  <span>${store.t("sys_overview.cap_media_remotes")}</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip ${remotesCount + volCount > 0 ? "chip-primary" : ""}">
                    ${remotesCount > 0
                      ? remotesCount === 1
                        ? store.t("sys_overview.remotes_one")
                        : store.t("sys_overview.remotes_many", {
                            count: fmtNumber(remotesCount, store.hass, 0),
                          })
                      : volCount > 0
                        ? store.t("common.active")
                        : store.t("sys_overview.not_set")}
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              <span class="overview-box-meta">
                ${remotesCount + remoteGroupsCount + volCount > 0
                  ? store.t("sys_overview.remotes_meta", {
                      groups:
                        remoteGroupsCount === 1
                          ? store.t("sys_overview.area_groups_one")
                          : store.t("sys_overview.area_groups_many", {
                              count: fmtNumber(remoteGroupsCount, store.hass, 0),
                            }),
                      overrides:
                        volCount === 1
                          ? store.t("sys_overview.vol_overrides_one")
                          : store.t("sys_overview.vol_overrides_many", {
                              count: fmtNumber(volCount, store.hass, 0),
                            }),
                    })
                  : store.t("sys_overview.remotes_empty")}
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
                  <span>${store.t("sys_overview.cap_device_groups")}</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip">
                    ${groups.length === 1
                      ? store.t("sys_overview.groups_one")
                      : store.t("sys_overview.groups_many", {
                          count: fmtNumber(groups.length, store.hass, 0),
                        })}
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              ${populatedGroupChips.length > 0
                ? html`<div class="overview-chips">
                    ${populatedGroupChips.map(
                      (gc) =>
                        html`<span class="chip ${gc.active ? "chip-primary" : ""}">
                          ${gc.label}
                        </span>`,
                    )}
                  </div>`
                : html`<span class="overview-box-meta">
                    ${configuredGroupNames.length > 0
                      ? store.t("sys_overview.groups_meta_dynamic", {
                          names: configuredGroupNames.join(", "),
                        })
                      : store.t("sys_overview.groups_meta_empty")}
                  </span>`}
            </button>

            <button
              type="button"
              id="cap-photo-library"
              @click=${() => store.openSystemSection("photos")}
              class="overview-box"
            >
              <div class="overview-box-head">
                <span class="overview-box-title">
                  ${renderSvgIcon(SYS_ICON_PHOTOS)}
                  <span>${store.t("sys_overview.cap_photo_library")}</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip ${uploadedWallpapersCount > 0 ? "chip-primary" : ""}">
                    ${wallpapersCount === 1
                      ? store.t("sys_overview.photos_count_one")
                      : store.t("sys_overview.photos_count_many", {
                          count: fmtNumber(wallpapersCount, store.hass, 0),
                        })}
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              <span class="overview-box-meta">
                ${store.t("sys_overview.photo_library_meta", {
                  defaults:
                    presetWallpapersCount === 1
                      ? store.t("sys_overview.defaults_one")
                      : store.t("sys_overview.defaults_many", {
                          count: fmtNumber(presetWallpapersCount, store.hass, 0),
                        }),
                  photos:
                    uploadedWallpapersCount === 1
                      ? store.t("sys_overview.photos_count_one")
                      : store.t("sys_overview.photos_count_many", {
                          count: fmtNumber(uploadedWallpapersCount, store.hass, 0),
                        }),
                  collections:
                    photoCollectionsCount === 1
                      ? store.t("sys_overview.collections_one")
                      : store.t("sys_overview.collections_many", {
                          count: fmtNumber(photoCollectionsCount, store.hass, 0),
                        }),
                })}
              </span>
            </button>

            <button
              type="button"
              id="cap-custom-colors"
              @click=${() =>
                store.openSystemSection("shared_entities", "card-custom-colors")}
              class="overview-box"
            >
              <div class="overview-box-head">
                <span class="overview-box-title">
                  ${renderSvgIcon(SYS_ICON_PALETTE)}
                  <span>${store.t("sys_overview.cap_custom_colors")}</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip ${colorsCount > 0 ? "chip-primary" : ""}">
                    ${colorsCount === 1
                      ? store.t("sys_overview.custom_colors_one")
                      : store.t("sys_overview.custom_colors_many", {
                          count: fmtNumber(colorsCount, store.hass, 0),
                        })}
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              ${colorsCount > 0
                ? html`<div class="swatch-strip" aria-hidden="true">
                    ${validPalettes.slice(0, 8).map((p) => {
                      const swStyle = `--swatch-color:${p.hex.toUpperCase()}`;
                      return html`<span class="swatch swatch-sm" style=${swStyle}></span>`;
                    })}
                    ${colorsCount > 8
                      ? html`<span class="chip">
                          +${fmtNumber(colorsCount - 8, store.hass, 0)}
                        </span>`
                      : nothing}
                  </div>`
                : html`<span class="overview-box-meta">
                    ${store.t("sys_overview.custom_colors_empty")}
                  </span>`}
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
                  <span>${store.t("card.perimeter_security")}</span>
                </span>
                <span class="overview-box-end">
                  <span class="chip ${hasSystemPin ? "chip-success" : ""}">
                    ${hasSystemPin
                      ? store.t("sys_overview.system_pin_set")
                      : store.t("sys_overview.no_system_pin")}
                  </span>
                  <span class="overview-box-chevron" aria-hidden="true">›</span>
                </span>
              </div>
              <span class="overview-box-meta">
                ${hasSystemPin
                  ? store.t("sys_overview.pin_active_meta")
                  : store.t("sys_overview.pin_unset_meta")}
              </span>
            </button>`,
        })}
      </div>
    </div>
  </section>`;
}
