/**
 * Device Tools View (`tools`, `D-027`, `D-064`, `D-066`):
 * - Column 1: Diagnostics + collapsed Developer & telemetry drawer + `Open in Home Assistant`.
 * - Column 2: Perimeter security policy + write-only PIN (`focusSafe` + `requestClearSecurityPin`),
 *   Replace hardware (lossless Home Assistant Reconfigure + `Download backup`), & Danger zone.
 */

import {
  renderCard,
  renderDeviceEntityRow,
  renderDeviceOfflineBanner,
  renderFirmwareOutdatedBanner,
  renderPrefControlRow,
  renderSelectRow,
  renderSettingsRow,
  renderSwitchRow,
} from "../components/controls.js";
import { SECURITY_PIN_POLICY_OPTIONS, t } from "../i18n/index.js";
import { focusSafe, html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type {
  DeviceRuntimeTelemetry,
  EspHomeEntityItem,
  HomeAssistant,
} from "../types.js";
import { fmtNumber } from "../utils/format.js";

export interface DiagnosticsTelemetryRow {
  label: string;
  value: string;
  code?: boolean;
}

const INTERACTIVE_ENTITY_DOMAINS = new Set([
  "update",
  "button",
  "switch",
  "select",
  "number",
]);

function isValidTelemetryState(val: unknown): val is string {
  const s = String(val ?? "").trim();
  return s !== "" && s !== "unknown" && s !== "unavailable";
}

function isInternalNetworkBlobEntity(it: EspHomeEntityItem): boolean {
  return it.key === "rpc_outbox" || it.entity_id.endsWith("_rpc_outbox");
}

const SUMMARY_DUPLICATE_KEYS = new Set([
  "wifi_signal",
  "ip_address",
  "mac_address",
  "firmware_version",
  "latter_core",
  "core_rev",
]);

function isSummaryDuplicateNetworkEntity(it: EspHomeEntityItem): boolean {
  if (it.key && SUMMARY_DUPLICATE_KEYS.has(it.key)) return true;
  return Array.from(SUMMARY_DUPLICATE_KEYS).some((k) => it.entity_id.endsWith(`_${k}`));
}

function formatTelemetryDuration(totalSec: number): string {
  if (!Number.isFinite(totalSec) || totalSec < 0) return "—";
  const secs = Math.round(totalSec);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) {
    const remSec = secs % 60;
    return remSec > 0 ? `${mins}m ${remSec}s` : `${mins}m`;
  }
  const hours = Math.floor(mins / 60);
  if (hours < 24) {
    const remMin = mins % 60;
    return remMin > 0 ? `${hours}h ${remMin}m` : `${hours}h`;
  }
  const days = Math.floor(hours / 24);
  const remHr = hours % 24;
  return remHr > 0 ? `${days}d ${remHr}h` : `${days}d`;
}

export function parseDeviceRuntimeTelemetryRows(
  telemetry: DeviceRuntimeTelemetry | null | undefined,
  hass?: HomeAssistant | null,
  overlay?: Readonly<Record<string, string>> | null,
): DiagnosticsTelemetryRow[] {
  if (!telemetry || typeof telemetry !== "object") return [];
  const rows: DiagnosticsTelemetryRow[] = [];

  const ramFree = telemetry.int_ram_free_kb;
  const ramMin = telemetry.int_ram_min_kb;
  const ramLargest = telemetry.int_ram_largest_kb;
  if (
    (ramFree !== null && ramFree !== undefined && Number.isFinite(Number(ramFree))) ||
    (ramMin !== null && ramMin !== undefined && Number.isFinite(Number(ramMin))) ||
    (ramLargest !== null && ramLargest !== undefined && Number.isFinite(Number(ramLargest)))
  ) {
    const fmtKb = (v: number | null | undefined): string =>
      v !== null && v !== undefined && Number.isFinite(Number(v))
        ? fmtNumber(Number(v), hass, 0)
        : "—";
    rows.push({
      label: t("dev_tools.telem_int_ram", undefined, overlay),
      value: `${fmtKb(ramFree)} / ${fmtKb(ramMin)} / ${fmtKb(ramLargest)} KB`,
    });
  }

  const psramMin = telemetry.psram_min_kb;
  if (psramMin !== null && psramMin !== undefined && Number.isFinite(Number(psramMin)) && Number(psramMin) > 0) {
    rows.push({
      label: t("dev_tools.telem_psram_min", undefined, overlay),
      value: `${fmtNumber(Number(psramMin), hass, 0)} KB`,
    });
  }

  if (typeof telemetry.ble_active === "boolean") {
    rows.push({
      label: t("dev_tools.telem_ble_beacon", undefined, overlay),
      value: telemetry.ble_active
        ? t("common.active", undefined, overlay)
        : t("common.disabled", undefined, overlay),
    });
  }

  const link = telemetry.link;
  if (link && typeof link === "object" && !Array.isArray(link)) {
    const upRaw = link.up_s ?? link.up;
    if (upRaw !== undefined && upRaw !== null && Number.isFinite(Number(upRaw))) {
      rows.push({
        label: t("dev_tools.telem_uptime", undefined, overlay),
        value: formatTelemetryDuration(Number(upRaw)),
      });
    }
    const rstRaw = typeof link.rst === "string" ? link.rst.trim() : "";
    if (rstRaw) {
      rows.push({
        label: t("dev_tools.telem_last_reset", undefined, overlay),
        value: rstRaw,
        code: true,
      });
    }
    const discRaw = link.disc;
    if (discRaw !== undefined && discRaw !== null && Number.isFinite(Number(discRaw))) {
      const btoNum = Number(link.bto ?? 0);
      const btoSuffix =
        Number.isFinite(btoNum) && btoNum > 0
          ? t("dev_tools.telem_beacon_timeouts", { count: fmtNumber(btoNum, hass, 0) }, overlay)
          : "";
      rows.push({
        label: t("dev_tools.telem_wifi_disc", undefined, overlay),
        value: `${fmtNumber(Number(discRaw), hass, 0)}${btoSuffix}`,
      });
    }
    const rssiAvg = link.rssi_avg;
    const rssiMin = link.rssi_min;
    if (
      rssiAvg !== undefined &&
      rssiAvg !== null &&
      rssiMin !== undefined &&
      rssiMin !== null &&
      Number.isFinite(Number(rssiAvg)) &&
      Number.isFinite(Number(rssiMin))
    ) {
      rows.push({
        label: t("dev_tools.telem_wifi_avg_min", undefined, overlay),
        value: `${fmtNumber(Number(rssiAvg), hass, 0)} / ${fmtNumber(Number(rssiMin), hass, 0)} dBm`,
      });
    }
    const haRaw = link.ha;
    if (haRaw !== undefined && haRaw !== null && Number.isFinite(Number(haRaw))) {
      const gapNum = Number(link.gap_s ?? link.gap ?? 0);
      const gapSuffix =
        Number.isFinite(gapNum) && gapNum > 0
          ? t("dev_tools.telem_max_gap", { duration: formatTelemetryDuration(gapNum) }, overlay)
          : "";
      rows.push({
        label: t("dev_tools.telem_ha_sessions", undefined, overlay),
        value: `${fmtNumber(Number(haRaw), hass, 0)}${gapSuffix}`,
      });
    }
    const nvsW = link.nvs_w;
    const nvsE = link.nvs_e;
    const nvsMax = link.nvs_max_ms;
    if (
      nvsW !== undefined &&
      nvsW !== null &&
      Number.isFinite(Number(nvsW)) &&
      Number.isFinite(Number(nvsE ?? 0)) &&
      Number.isFinite(Number(nvsMax ?? 0))
    ) {
      rows.push({
        label: t("dev_tools.telem_nvs_writes", undefined, overlay),
        value: t(
          "dev_tools.telem_nvs_value",
          {
            writes: fmtNumber(Number(nvsW), hass, 0),
            erases: fmtNumber(Number(nvsE ?? 0), hass, 0),
            maxMs: fmtNumber(Number(nvsMax ?? 0), hass, 0),
          },
          overlay,
        ),
      });
    }
  }

  return rows;
}

export const DEV_TELEMETRY_REFRESH_DEBOUNCE_MS = 10_000;

const devTelemetryRefreshAtByStore = new WeakMap<StudioStore, Map<string, number>>();

export function handleDeveloperTelemetryDrawerToggle(
  store: StudioStore,
  open: boolean,
  isOffline: boolean,
  nowMs = Date.now(),
): boolean {
  if (!open || isOffline) return false;
  const subentryId = String(store.activeSubentryId || "").trim();
  if (!subentryId) return false;
  let bySubentry = devTelemetryRefreshAtByStore.get(store);
  if (!bySubentry) {
    bySubentry = new Map<string, number>();
    devTelemetryRefreshAtByStore.set(store, bySubentry);
  }
  const lastMs = bySubentry.get(subentryId);
  if (
    lastMs !== undefined &&
    nowMs >= lastMs &&
    nowMs - lastMs < DEV_TELEMETRY_REFRESH_DEBOUNCE_MS
  ) {
    return false;
  }
  bySubentry.set(subentryId, nowMs);
  void store.entity.runDeviceAction("request_telemetry");
  return true;
}

export function renderDeviceToolsView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const live = data?.live || {};
  const links = data?.links || {};
  const esp = data?.esphome;
  const isBleOnly = cfg.kind === "ble_tag";

  const curDevEntry =
    (data?.system_devices || []).find((d) => d.subentry_id === store.activeSubentryId) ||
    (data?.system_devices || []).find((d) => d.is_current);
  const isOffline = !isBleOnly && curDevEntry?.is_online === false;

  const networkItems = store.entity.getSectionItems("network");
  const developerItems = store.entity.getSectionItems("developer");

  const networkControlItems = networkItems.filter((it) =>
    INTERACTIVE_ENTITY_DOMAINS.has(it.domain),
  );
  const extraNetworkSensorItems = networkItems.filter(
    (it) =>
      !INTERACTIVE_ENTITY_DOMAINS.has(it.domain) &&
      !isInternalNetworkBlobEntity(it) &&
      !isSummaryDuplicateNetworkEntity(it),
  );

  const findNetworkState = (key: string): string => {
    const match = networkItems.find(
      (it) => it.key === key || it.entity_id.endsWith(`_${key}`),
    );
    return isValidTelemetryState(match?.state) ? String(match?.state).trim() : "";
  };

  const winRow = (curDevEntry?.ble_survey_rows || []).find((r) => r.is_winner);
  let signalText = store.t("common.unknown");
  if (!isBleOnly) {
    if (curDevEntry?.wifi_rssi !== null && curDevEntry?.wifi_rssi !== undefined) {
      signalText = `${fmtNumber(curDevEntry.wifi_rssi, store.hass, 0)} dBm`;
    } else {
      const rawWifi = findNetworkState("wifi_signal");
      if (rawWifi) {
        signalText = Number.isFinite(Number(rawWifi))
          ? `${fmtNumber(Number(rawWifi), store.hass, 0)} dBm`
          : rawWifi;
      }
    }
  } else if (winRow && winRow.effective_rssi !== null) {
    signalText = `${fmtNumber(winRow.effective_rssi, store.hass, 0)} dBm`;
  }

  const rawSw = String(
    live.device_sw_version || esp?.device?.sw_version || findNetworkState("firmware_version") || "",
  ).replace(/^v/i, "");
  const fwVersionText = rawSw ? `v${rawSw}` : store.t("common.unknown");
  const modelText = curDevEntry?.model_label || esp?.device?.model || store.t("common.unknown");
  const ipStr = curDevEntry?.ip_address || findNetworkState("ip_address") || "";
  const macStr = esp?.device?.mac || findNetworkState("mac_address") || "";

  const weatherSimPref = store.entity.getPref("weather_sim_condition");
  const devControlItems = developerItems.filter(
    (it) =>
      INTERACTIVE_ENTITY_DOMAINS.has(it.domain) &&
      !it.pref_key &&
      it.key !== "weather_sim_condition",
  );
  const devSensorItems = developerItems.filter(
    (it) => !INTERACTIVE_ENTITY_DOMAINS.has(it.domain),
  );
  const runtimeRows = parseDeviceRuntimeTelemetryRows(
    live.telemetry,
    store.hass,
    store.localeOverlay,
  );
  const profilerOn = Boolean(live.telemetry?.profiler_on);
  const hasDeveloperDrawer = !isBleOnly;

  const curPinPolicy = String(cfg.security_pin_policy || "auto");
  const effectivePinPolicyLabel = store.tPrefOption(
    "security_pin_policy",
    live.effective_security_pin_policy || curPinPolicy,
  );
  const localizedPinPolicyOptions = SECURITY_PIN_POLICY_OPTIONS.map((opt) => ({
    value: opt.value,
    label: store.tPrefOption("security_pin_policy", opt.value),
  }));
  const hasPin = store.hasConfiguredSecurityPin;
  const hasOpenInHa = Boolean(links.esphome_device_id || links.latter_device_id);

  return html`<section id="view-tools">
    ${renderDeviceOfflineBanner(store)}
    ${renderFirmwareOutdatedBanner(store)}

    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-device-diagnostics",
          handoffActive: store.isHandoffTarget("card-device-diagnostics"),
          heading: html`<h3 class="card-title">${store.t("card.diagnostics")}</h3>`,
          contentClass: "stack",
          body: html`${networkControlItems.length
              ? html`<div class="settings-list">
                  ${networkControlItems.map((it) => renderDeviceEntityRow(store, it))}
                </div>`
              : nothing}
            <div class="kv-list">
              ${isBleOnly
                ? html`<div class="kv-row">
                      <span>${store.t("dev_tools.ble_signal")}</span>
                      <strong>${signalText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>${store.t("dev_tools.ble_target")}</span>
                      <strong>
                        ${cfg.ble_target_address
                          ? html`<code>${cfg.ble_target_address}</code>`
                          : store.t("common.unknown")}
                      </strong>
                    </div>`
                : html`<div class="kv-row">
                      <span>${store.t("dev_tools.model")}</span>
                      <strong>${modelText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>${store.t("dev_tools.esphome_node")}</span>
                      <strong>
                        <code id="diag-node-name">
                          ${data?.esphome?.device?.node_name ||
                          cfg.device_slug ||
                          store.t("common.unknown")}
                        </code>
                      </strong>
                    </div>
                    <div class="kv-row">
                      <span>${store.t("dev_tools.firmware_version")}</span>
                      <strong>${fwVersionText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>${store.t("dev_tools.firmware_core")}</span>
                      <strong id="diag-core-rev">
                        ${live.core_rev || store.t("common.unknown")}
                      </strong>
                    </div>
                    ${live.firmware_outdated
                      ? html`<div class="kv-row">
                          <span>${store.t("dev_tools.firmware_status")}</span>
                          <span id="diag-firmware-outdated-badge" class="chip chip-warning">
                            ${store.t("status.firmware_update_required")}
                          </span>
                        </div>`
                      : nothing}
                    <div class="kv-row">
                      <span>${store.t("dev_tools.wifi_signal")}</span>
                      <strong>${signalText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>${store.t("dev_tools.ip_address")}</span>
                      <strong>
                        ${ipStr ? html`<code>${ipStr}</code>` : store.t("common.unknown")}
                      </strong>
                    </div>
                    ${macStr
                      ? html`<div class="kv-row">
                          <span>${store.t("dev_tools.mac_address")}</span>
                          <strong><code>${macStr}</code></strong>
                        </div>`
                      : nothing}
                    ${extraNetworkSensorItems.map((it) => renderDeviceEntityRow(store, it))}`}
            </div>
            <div class="settings-list">
              ${links.latter_device_id || links.entry_id
                ? renderSettingsRow({
                    id: "row-diagnostics",
                    label: store.t("dev_tools.diagnostics_file_label"),
                    description: store.t("dev_tools.diagnostics_file_desc"),
                    control: html`<button
                      type="button"
                      @click=${() => void store.tools.downloadDeviceDiagnostics()}
                      class="btn btn-secondary btn-compact"
                    >
                      ${store.t("action.download_diagnostics")}
                    </button>`,
                  })
                : nothing}
              ${isBleOnly
                ? renderSettingsRow({
                    label: store.t("dev_tools.backup_row_label"),
                    description: store.t("dev_tools.backup_row_desc"),
                    control: html`<button
                      type="button"
                      @click=${() => void store.tools.exportBackup(store.activeSubentryId)}
                      class="btn btn-secondary btn-compact"
                    >
                      ${store.t("action.download_backup")}
                    </button>`,
                  })
                : nothing}
            </div>
            ${hasDeveloperDrawer
              ? html`<details
                  class="sub-collapsible"
                  @toggle=${(ev: Event) => {
                    handleDeveloperTelemetryDrawerToggle(
                      store,
                      (ev.currentTarget as HTMLDetailsElement).open,
                      isOffline,
                    );
                  }}
                >
                  <summary>${store.t("card.developer_telemetry")}</summary>
                  <div class="card-content">
                    <div class="settings-list">
                      ${weatherSimPref ? renderPrefControlRow(store, weatherSimPref) : nothing}
                      ${renderSwitchRow({
                        id: "dev-telemetry-profiler",
                        label: store.t("dev_tools.profiler_label"),
                        description: store.t("dev_tools.profiler_desc"),
                        disabled: isOffline,
                        checked: profilerOn,
                        onChange: (checked) =>
                          void store.entity.runDeviceAction(
                            checked ? "set_profiler_on" : "set_profiler_off",
                          ),
                      })}
                      ${renderSettingsRow({
                        id: "row-refresh-telemetry",
                        label: store.t("dev_tools.refresh_telemetry_label"),
                        description: store.t("dev_tools.refresh_telemetry_desc"),
                        control: html`<button
                          type="button"
                          id="btn-refresh-telemetry"
                          ?disabled=${isOffline}
                          @click=${() =>
                            void store.entity.runDeviceAction(
                              "request_telemetry",
                              store.t("dev_tools.refresh_telemetry_toast"),
                            )}
                          class="btn btn-secondary btn-compact"
                        >
                          ${store.t("action.refresh")}
                        </button>`,
                      })}
                      ${devControlItems.map((it) => renderDeviceEntityRow(store, it))}
                    </div>
                    ${devSensorItems.length || runtimeRows.length
                      ? html`<div class="kv-list">
                          ${devSensorItems.map((it) => renderDeviceEntityRow(store, it))}
                          ${runtimeRows.map(
                            (row) => html`<div class="kv-row">
                              <span>${row.label}</span>
                              <strong>
                                ${row.code ? html`<code>${row.value}</code>` : row.value}
                              </strong>
                            </div>`,
                          )}
                        </div>`
                      : nothing}
                  </div>
                </details>`
              : nothing}`,
          footerActions: hasOpenInHa
            ? html`<button
                type="button"
                id="btn-tools-open-in-ha"
                @click=${() => store.openDeviceInHa(isBleOnly)}
                class="btn btn-text"
              >
                ${store.t("action.open_in_ha")}
              </button>`
            : nothing,
        })}
      </div>

      <div class="column">
        ${!isBleOnly
          ? html`${renderCard({
                id: "card-device-security",
                title: store.t("card.perimeter_security"),
                subtitle: store.t("dev_tools.perimeter_subtitle"),
                contentClass: "settings-list",
                body: html`${renderSelectRow({
                    id: "cfg-security_pin_policy",
                    label: store.tPrefLabel("security_pin_policy"),
                    description: html`${store.t("dev_tools.pin_policy_desc_prefix")}
                      <strong>${effectivePinPolicyLabel}</strong>.`,
                    value: curPinPolicy,
                    rawOptions: localizedPinPolicyOptions,
                    onChange: (val) =>
                      store.entity.stageDeviceSetting(
                        "security_pin_policy",
                        val,
                        "cfg-security_pin_policy",
                      ),
                  })}
                  ${renderSettingsRow({
                    label: store.t("dev_tools.security_pin_label"),
                    description: store.t("dev_tools.security_pin_desc"),
                    stacked: true,
                    control: html`<div class="input-action-row">
                      <span class="chip ${hasPin ? "chip-success" : ""}">
                        ${hasPin
                          ? store.t("status.pin_configured")
                          : store.t("status.pin_not_set")}
                      </span>
                      <input
                        type="password"
                        id="dev-security-pin-input"
                        inputmode="numeric"
                        pattern="[0-9]*"
                        autocomplete="new-password"
                        aria-label=${store.t("dev_tools.pin_input_aria")}
                        placeholder=${hasPin
                          ? store.t("dev_tools.pin_placeholder_replace")
                          : store.t("dev_tools.pin_placeholder_new")}
                        .value=${focusSafe(store.devicePinDraft)}
                        @input=${(ev: Event) => {
                          store.devicePinDraft = (ev.currentTarget as HTMLInputElement).value;
                          store.host.requestUpdate();
                        }}
                      />
                      <button
                        type="button"
                        ?disabled=${store.pinBusy || !store.devicePinDraft.trim()}
                        @click=${() => void store.tools.saveSecurityPin("device")}
                        class="btn btn-primary btn-compact"
                      >
                        ${store.t("dev_tools.save_pin")}
                      </button>
                      ${hasPin
                        ? html`<button
                            type="button"
                            ?disabled=${store.pinBusy}
                            @click=${() => store.tools.requestClearSecurityPin("device")}
                            class="btn btn-danger btn-compact"
                          >
                            ${store.t("dev_tools.clear_pin")}
                          </button>`
                        : nothing}
                    </div>`,
                  })}`,
              })}
              ${renderCard({
                id: "card-replace-hardware",
                heading: html`<h3 class="card-title">${store.t("card.replace_hardware")}</h3>`,
                contentClass: "stack",
                body: html`<p class="row-description">
                    ${store.t("card.replace_hardware_body")}
                  </p>
                  <div class="input-action-row">
                    <button
                      type="button"
                      id="btn-reconfigure-hardware"
                      @click=${() => store.openDeviceInHa(true)}
                      class="btn btn-secondary"
                    >
                      ${store.t("dev_tools.reconfigure_in_ha")}
                    </button>
                    <button
                      type="button"
                      id="btn-download-device-backup"
                      @click=${() => void store.tools.exportBackup(store.activeSubentryId)}
                      class="btn btn-text"
                    >
                      ${store.t("action.download_backup")}
                    </button>
                  </div>`,
              })}`
          : nothing}

        ${renderCard({
          heading: html`<h3 class="card-title">${store.t("card.danger_zone")}</h3>`,
          danger: true,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: store.t("dev_tools.reset_defaults_label"),
              description: store.t("dev_tools.reset_defaults_desc"),
              control: html`<button
                type="button"
                @click=${() => store.tools.openResetDeviceModal()}
                class="btn btn-danger"
              >
                ${store.t("dev_tools.reset_defaults_label")}
              </button>`,
            })}
            ${renderSettingsRow({
              label: store.t("dev_tools.remove_device_label"),
              description: store.t("dev_tools.remove_device_desc"),
              control: html`<button
                type="button"
                @click=${() =>
                  store.tools.openRemoveDeviceModal(
                    store.activeSubentryId,
                    data?.title || cfg.device_slug || store.t("devices.col_device"),
                  )}
                class="btn btn-danger"
              >
                ${store.t("dev_tools.remove_device_label")}
              </button>`,
            })}`,
        })}
      </div>
    </div>
  </section>`;
}
