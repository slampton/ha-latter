/**
 * Device Overview — Status Card (`views/overview/status-card.ts`, `D-003`, `D-029`, `D-030`, `D-048`).
 *
 * Strict `D-003` unknowns for battery, Wi-Fi/BLE RSSI, Area, and `update.*` Firmware gating.
 */

import { renderCard, renderSvgIcon } from "../../components/controls.js";
import { html, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import type { BleSurveyRow, SystemDeviceEntry } from "../../types.js";
import {
  fmtDistance,
  fmtNumber,
  fmtPercent,
  rssiToPercent,
} from "../../utils/format.js";

const DEV_ICON_AREA =
  "M12,6.5A2.5,2.5 0 0,1 14.5,9A2.5,2.5 0 0,1 12,11.5A2.5,2.5 0 0,1 9.5,9A2.5,2.5 0 0,1 12,6.5M12,2A7,7 0 0,1 19,9C19,14.25 12,22 12,22C12,22 5,14.25 5,9A7,7 0 0,1 12,2M12,4A5,5 0 0,0 7,9C7,10 7,12 12,18.71C17,12 17,10 17,9A5,5 0 0,0 12,4Z";
const DEV_ICON_BATTERY =
  "M16,20H8V6H16M16.67,4H15V2H9V4H7.33A1.33,1.33 0 0,0 6,5.33V20.67C6,21.4 6.6,22 7.33,22H16.67A1.33,1.33 0 0,0 18,20.67V5.33C18,4.6 17.4,4 16.67,4Z";
const DEV_ICON_PLUG =
  "M16,7V3H14V7H10V3H8V7H8C7,7 6,8 6,9V14.5L9.5,18V21H14.5V18L18,14.5V9C18,8 17,7 16,7M16,13.67L12.5,17.17V19H11.5V17.17L8,13.67V9H16V13.67Z";
const DEV_ICON_RADAR =
  "M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12C22,10.84 21.79,9.69 21.39,8.61L19.79,10.21C19.93,10.8 20,11.4 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4C12.6,4 13.2,4.07 13.79,4.21L15.4,2.6C14.31,2.21 13.16,2 12,2M19,2A2,2 0 0,0 17,4A2,2 0 0,0 19,6A2,2 0 0,0 21,4A2,2 0 0,0 19,2M12,6A6,6 0 0,0 6,12A6,6 0 0,0 12,18A6,6 0 0,0 18,12H16A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8V6M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10Z";
const DEV_ICON_WIFI =
  "M12,21L15.6,16.2C14.6,15.45 13.35,15 12,15C10.65,15 9.4,15.45 8.4,16.2L12,21M12,3C7.95,3 4.21,4.34 1.2,6.6L3,9C5.5,7.12 8.62,6 12,6C15.38,6 18.5,7.12 21,9L22.8,6.6C19.79,4.34 16.05,3 12,3M12,9C9.3,9 6.81,9.89 4.8,11.4L6.6,13.8C8.1,12.67 9.97,12 12,12C14.03,12 15.9,12.67 17.4,13.8L19.2,11.4C17.19,9.89 14.7,9 12,9Z";
const DEV_ICON_BLUETOOTH =
  "M14.88,16.29L13,18.17V14.41M13,5.83L14.88,7.71L13,9.58M17.71,7.71L12,2H11V9.58L6.41,5L5,6.41L10.59,12L5,17.58L6.41,19L11,14.41V22H12L17.71,16.29L13.41,12L17.71,7.71Z";
const DEV_ICON_CHIP =
  "M17,17H7V7H17M21,11V9H19V7C19,5.89 18.1,5 17,5H15V3H13V5H11V3H9V5H7C5.89,5 5,5.89 5,7V9H3V11H5V13H3V15H5V17A2,2 0 0,0 7,19H9V21H11V19H13V21H15V19H17A2,2 0 0,0 19,17V15H21V13H19V11M15,15H9V9H15V15Z";
const DEV_ICON_TAG =
  "M21.41,11.58L12.41,2.58C12.05,2.22 11.55,2 11,2H4C2.9,2 2,2.9 2,4V11C2,11.55 2.22,12.05 2.59,12.42L11.59,21.42C11.95,21.78 12.45,22 13,22C13.55,22 14.05,21.78 14.41,21.41L21.41,14.41C21.78,14.05 22,13.55 22,13C22,12.45 21.77,11.94 21.41,11.58M13,20.01L4,11V4H11V3.99L20,12.99L13,20.01M6.5,5A1.5,1.5 0 0,1 8,6.5A1.5,1.5 0 0,1 6.5,8A1.5,1.5 0 0,1 5,6.5A1.5,1.5 0 0,1 6.5,5Z";

function rssiQualityLabel(store: StudioStore, rssi: number | null): string {
  if (rssi === null || !Number.isFinite(rssi)) return store.t("signal.no_reading");
  if (rssi >= -60) return store.t("signal.excellent");
  if (rssi >= -70) return store.t("signal.good");
  if (rssi >= -80) return store.t("signal.fair");
  return store.t("signal.weak");
}

export function renderOverviewStatusCard(
  store: StudioStore,
  opts: {
    curDevEntry: SystemDeviceEntry | undefined;
    winRow: BleSurveyRow | undefined;
    isBleOnly: boolean;
    hasOpenInHa: boolean;
  },
): TemplateResult {
  const { curDevEntry, winRow, isBleOnly, hasOpenInHa } = opts;
  const data = store.state;
  const cfg = data?.config || {};
  const live = data?.live || {};
  const caps = data?.capabilities || {};
  const esp = data?.esphome;

  const hasBattery = Boolean(caps.has_battery || curDevEntry?.has_battery);
  const hasBatteryReading =
    !isBleOnly &&
    hasBattery &&
    curDevEntry?.battery_level !== null &&
    curDevEntry?.battery_level !== undefined &&
    Number.isFinite(Number(curDevEntry.battery_level));
  const batPct = hasBatteryReading
    ? Math.max(0, Math.min(100, Math.round(Number(curDevEntry?.battery_level))))
    : 0;
  const batSignalStyle = `--signal-pct:${batPct}%`;
  const batMeta = curDevEntry?.is_charging
    ? store.t("status.charging")
    : curDevEntry?.is_usb_connected
      ? store.t("status.plugged_in")
      : hasBatteryReading
        ? store.t("status.on_battery")
        : store.t("dev_overview.waiting_for_reading");

  let rssiVal: number | null = null;
  if (!isBleOnly && curDevEntry?.wifi_rssi !== null && curDevEntry?.wifi_rssi !== undefined) {
    rssiVal = Number(curDevEntry.wifi_rssi);
  } else if (
    isBleOnly &&
    winRow &&
    winRow.effective_rssi !== null &&
    winRow.effective_rssi !== undefined
  ) {
    rssiVal = Number(winRow.effective_rssi);
  }
  const hasRssi = rssiVal !== null && Number.isFinite(rssiVal);
  const rssiText = hasRssi
    ? `${fmtNumber(rssiVal, store.hass, 0)} dBm`
    : store.t("common.unknown");
  const rssiPct = hasRssi ? rssiToPercent(rssiVal) : 0;
  const wifiSignalStyle = `--signal-pct:${rssiPct}%`;

  const hasAssignedArea = Boolean(curDevEntry?.has_assigned_area);
  const areaText = hasAssignedArea
    ? curDevEntry?.area_label || live.active_area_name || store.t("common.unknown")
    : live.active_area_name || store.t("common.unknown");

  const effBleCat = String(cfg.effective_ble_category || curDevEntry?.ble_category || "ble_tag");
  const distSuffix =
    live.ble_closest_proxy &&
    winRow &&
    winRow.distance_m !== null &&
    winRow.distance_m !== undefined
      ? ` (~${fmtDistance(winRow.distance_m, store.hass, winRow.distance_ft)})`
      : "";
  const showProxyMeta = Boolean(
    (isBleOnly || (caps.has_ble_beacon && cfg.native_ble_tracking)) && live.ble_closest_proxy,
  );
  const areaMetaBase = isBleOnly
    ? effBleCat === "phone"
      ? store.t("status.phone")
      : store.t("status.ble_tag")
    : hasAssignedArea
      ? store.t("status.stationary")
      : store.t("status.roaming");
  const areaMeta = showProxyMeta
    ? `${areaMetaBase} • ${live.ble_closest_proxy}${distSuffix}`
    : areaMetaBase;

  const rawSw = String(live.device_sw_version || esp?.device?.sw_version || "").replace(
    /^v/i,
    "",
  );
  const fwValue = rawSw ? `v${rawSw}` : store.t("common.unknown");
  const allUpdateEntities = (esp?.sections || []).flatMap((s) =>
    (s.items || []).filter((it) => it.domain === "update"),
  );
  const fwEntityId = String(
    live.fw_update_entity || allUpdateEntities[0]?.entity_id || "",
  ).trim();
  const fwEntityItem = fwEntityId
    ? allUpdateEntities.find((it) => it.entity_id === fwEntityId)
    : allUpdateEntities[0];
  const fwEntityState = String(
    fwEntityItem?.state ?? (fwEntityId ? store.hass?.states?.[fwEntityId]?.state : "") ?? "",
  ).trim();
  const hasAvailableUpdateEntity = Boolean(
    fwEntityId && fwEntityState && fwEntityState !== "unavailable" && fwEntityState !== "unknown",
  );
  const fwMeta = live.fw_update_available
    ? store.t("status.update")
    : hasAvailableUpdateEntity
      ? store.t("status.up_to_date")
      : store.t("common.unknown");

  let statusChipClass = "chip";
  let statusDotClass = "status-dot";
  let statusLabel = store.t("common.unknown");
  if (isBleOnly) {
    if (
      curDevEntry?.status_code === "online" ||
      Boolean(curDevEntry?.is_online) ||
      Boolean(winRow)
    ) {
      statusChipClass = "chip chip-success";
      statusDotClass = "status-dot online";
      statusLabel = store.t("status.online");
    } else if (curDevEntry?.status_code === "scanning") {
      statusLabel = store.t("status.scanning");
    } else if (curDevEntry?.status_code === "away") {
      statusLabel = store.t("status.away");
    } else if (curDevEntry?.status_label) {
      statusLabel = curDevEntry.status_label;
    }
  } else if (curDevEntry?.is_online && live.fw_update_available) {
    statusChipClass = "chip chip-warning";
    statusDotClass = "status-dot update";
    statusLabel = store.t("status.update");
  } else if (curDevEntry?.is_online) {
    statusChipClass = "chip chip-success";
    statusDotClass = "status-dot online";
    statusLabel = store.t("status.online");
  } else if (curDevEntry?.is_online === false) {
    statusLabel = live.is_ble_sleep_expected
      ? store.t("status.sleeping")
      : store.t("status.offline");
  }

  const powerTileBody = hasBattery
    ? html`<div class="status-tile-head">
          ${renderSvgIcon(DEV_ICON_BATTERY)}
          <span>${store.t("dev_overview.tile_battery")}</span>
        </div>
        <strong class="status-tile-value">
          ${hasBatteryReading
            ? fmtPercent(curDevEntry?.battery_level, store.hass)
            : store.t("common.unknown")}
        </strong>
        <span class="status-tile-meta">${batMeta}</span>
        ${hasBatteryReading
          ? html`<div class="signal-track" aria-hidden="true">
              <div
                class="signal-fill${batPct <= 20 && !curDevEntry?.is_charging ? " low" : ""}"
                style=${batSignalStyle}
              ></div>
            </div>`
          : nothing}`
    : html`<div class="status-tile-head">
          ${renderSvgIcon(DEV_ICON_PLUG)}
          <span>${store.t("dev_overview.tile_power")}</span>
        </div>
        <strong class="status-tile-value">${store.t("status.plugged_in")}</strong>
        <span class="status-tile-meta">
          ${caps.has_power ? store.t("status.sleep_wake_active") : store.t("status.always_on")}
        </span>`;

  return renderCard({
    id: "card-device-status",
    heading: html`<h3 class="card-title">${store.t("card.status")}</h3>`,
    headerActions: html`<span id="st-status-chip" class=${statusChipClass}>
      <span class=${statusDotClass} aria-hidden="true"></span>${statusLabel}
    </span>`,
    contentClass: "stack",
    body: html`<div class="status-tiles">
      <button
        type="button"
        @click=${() => store.switchView("presence")}
        class="status-tile"
      >
        <div class="status-tile-head">
          ${renderSvgIcon(DEV_ICON_AREA)}
          <span id="st-area-label">
            ${hasAssignedArea
              ? store.t("dev_overview.tile_area")
              : store.t("dev_overview.tile_current_area")}
          </span>
        </div>
        <strong class="status-tile-value">${areaText}</strong>
        <span class="status-tile-meta">${areaMeta}</span>
      </button>

      ${isBleOnly
        ? html`<button
            type="button"
            @click=${() => store.switchView("presence")}
            class="status-tile"
          >
            <div class="status-tile-head">
              ${renderSvgIcon(DEV_ICON_RADAR)}
              <span>${store.t("dev_overview.tile_closest_proxy")}</span>
            </div>
            <strong class="status-tile-value">
              ${live.ble_closest_proxy || store.t("common.unknown")}
            </strong>
            <span class="status-tile-meta">
              ${winRow && winRow.distance_m !== null && winRow.distance_m !== undefined
                ? `~${fmtDistance(winRow.distance_m, store.hass, winRow.distance_ft)}`
                : store.t("dev_overview.ble_presence_meta")}
            </span>
          </button>`
        : store.deviceHasView("power")
          ? html`<button
              type="button"
              @click=${() => store.switchView("power")}
              class="status-tile"
            >
              ${powerTileBody}
            </button>`
          : html`<div class="status-tile">${powerTileBody}</div>`}

      <button
        type="button"
        @click=${() =>
          isBleOnly
            ? store.switchView("presence")
            : store.openDeviceSection("tools", "card-device-diagnostics")}
        class="status-tile"
      >
        <div class="status-tile-head">
          ${renderSvgIcon(isBleOnly ? DEV_ICON_BLUETOOTH : DEV_ICON_WIFI)}
          <span id="st-wifi-label">
            ${isBleOnly
              ? store.t("dev_overview.tile_ble_signal")
              : store.t("dev_overview.tile_wifi_signal")}
          </span>
        </div>
        <strong class="status-tile-value">${rssiText}</strong>
        <span class="status-tile-meta">${rssiQualityLabel(store, rssiVal)}</span>
        ${hasRssi
          ? html`<div class="signal-track" aria-hidden="true">
              <div
                class="signal-fill${rssiVal !== null && rssiVal < -80 ? " low" : ""}"
                style=${wifiSignalStyle}
              ></div>
            </div>`
          : nothing}
      </button>

      ${isBleOnly
        ? html`<button
            type="button"
            @click=${() => store.openDeviceSection("presence", "card-ble-identity")}
            class="status-tile"
          >
            <div class="status-tile-head">
              ${renderSvgIcon(DEV_ICON_TAG)}
              <span>${store.t("dev_overview.tile_ble_target")}</span>
            </div>
            <strong class="status-tile-value">
              <code>${cfg.ble_target_address || store.t("common.unknown")}</code>
            </strong>
            <span class="status-tile-meta">
              ${store.t("dev_overview.ble_address_meta")}
            </span>
          </button>`
        : html`<button
            type="button"
            @click=${() => store.openDeviceSection("tools", "card-device-diagnostics")}
            class="status-tile"
          >
            <div class="status-tile-head">
              ${renderSvgIcon(DEV_ICON_CHIP)}
              <span>${store.t("dev_overview.tile_firmware")}</span>
            </div>
            <strong class="status-tile-value">${fwValue}</strong>
            <span class="status-tile-meta">${fwMeta}</span>
          </button>`}
    </div>`,
    footerActions:
      isBleOnly && hasOpenInHa
        ? html`<button
            type="button"
            id="btn-open-in-ha"
            @click=${() => store.openDeviceInHa(true)}
            class="btn btn-text"
          >
            ${store.t("action.open_in_ha")}
          </button>`
        : nothing,
  });
}
