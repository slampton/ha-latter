/**
 * Device Tools View (`tools`, D-027): Standard Diagnostics + collapsed Developer & Telemetry drawer,
 * Perimeter Security Policy + write-only PIN, Replace Hardware & Danger Zone.
 */

import {
  renderCard,
  renderNativeControlRow,
  renderSelectRow,
  renderSettingsRow,
} from "../components/controls.js";
import { SECURITY_PIN_POLICY_OPTIONS } from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { EspHomeEntityItem, HomeAssistant } from "../types.js";
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
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return (
    low.includes("rpc outbox") ||
    low.includes("rpc_outbox") ||
    low.includes("hardware manifest") ||
    low.includes("hardware_manifest") ||
    low.includes("link report") ||
    low.includes("link_report")
  );
}

function isSummaryDuplicateNetworkEntity(it: EspHomeEntityItem): boolean {
  const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
  return (
    low.includes("wifi signal") ||
    low.includes("wi-fi signal") ||
    low.includes("wifi_signal") ||
    low.includes("ip address") ||
    low.includes("ip_address") ||
    low.includes("mac address") ||
    low.includes("mac_address") ||
    low.includes("firmware version") ||
    low.includes("firmware_version") ||
    low.includes("latter sdk")
  );
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

export function parseDeviceLinkReportRows(
  rawState: string | null | undefined,
  hass?: HomeAssistant | null,
): DiagnosticsTelemetryRow[] {
  if (!isValidTelemetryState(rawState)) return [];
  const kv = new Map<string, string>();
  for (const tok of rawState.trim().split(/\s+/)) {
    const eq = tok.indexOf("=");
    if (eq > 0 && eq < tok.length - 1) {
      kv.set(tok.slice(0, eq), tok.slice(eq + 1));
    }
  }
  if (!kv.size) return [];

  const rows: DiagnosticsTelemetryRow[] = [];
  const upRaw = kv.get("up");
  if (upRaw !== undefined && Number.isFinite(Number(upRaw))) {
    rows.push({
      label: "Session Uptime",
      value: formatTelemetryDuration(Number(upRaw)),
    });
  }

  const rstRaw = kv.get("rst");
  if (rstRaw) {
    rows.push({ label: "Last Reset", value: rstRaw, code: true });
  }

  const discRaw = kv.get("disc");
  if (discRaw !== undefined && Number.isFinite(Number(discRaw))) {
    const btoNum = Number(kv.get("bto") ?? 0);
    const btoSuffix =
      Number.isFinite(btoNum) && btoNum > 0
        ? ` (${fmtNumber(btoNum, hass, 0)} beacon timeouts)`
        : "";
    rows.push({
      label: "Wi-Fi Disconnects",
      value: `${fmtNumber(Number(discRaw), hass, 0)}${btoSuffix}`,
    });
  }

  const rssiRaw = kv.get("rssi");
  if (rssiRaw && rssiRaw !== "na" && rssiRaw.includes("/")) {
    const [avgStr, minStr] = rssiRaw.split("/", 2);
    if (Number.isFinite(Number(avgStr)) && Number.isFinite(Number(minStr))) {
      rows.push({
        label: "Wi-Fi Avg / Min",
        value: `${fmtNumber(Number(avgStr), hass, 0)} / ${fmtNumber(Number(minStr), hass, 0)} dBm`,
      });
    }
  }

  const haRaw = kv.get("ha");
  if (haRaw !== undefined && Number.isFinite(Number(haRaw))) {
    const gapNum = Number(kv.get("gap") ?? 0);
    const gapSuffix =
      Number.isFinite(gapNum) && gapNum > 0
        ? ` (max gap ${formatTelemetryDuration(gapNum)})`
        : "";
    rows.push({
      label: "HA Sessions",
      value: `${fmtNumber(Number(haRaw), hass, 0)}${gapSuffix}`,
    });
  }

  const slpRaw = kv.get("slp");
  if (slpRaw !== undefined && Number.isFinite(Number(slpRaw))) {
    const lsNum = Number(kv.get("ls") ?? 0);
    const lsSuffix =
      Number.isFinite(lsNum) && lsNum > 0
        ? ` (${fmtNumber(lsNum, hass, 0)} cycles)`
        : "";
    rows.push({
      label: "Light Sleep Duty",
      value: `${fmtNumber(Number(slpRaw), hass, 1)}%${lsSuffix}`,
    });
  }

  const nvsRaw = kv.get("nvs");
  if (nvsRaw && nvsRaw.includes("/")) {
    const parts = nvsRaw.split("/");
    if (parts.length >= 3 && parts.every((p) => Number.isFinite(Number(p)))) {
      rows.push({
        label: "NVS Flash Writes",
        value: `${fmtNumber(Number(parts[0]), hass, 0)} writes (${fmtNumber(Number(parts[1]), hass, 0)} erases, ${fmtNumber(Number(parts[2]), hass, 0)} ms max)`,
      });
    }
  }

  return rows;
}

export function parseDeviceHardwareManifestRows(
  rawState: string | null | undefined,
  hass?: HomeAssistant | null,
): DiagnosticsTelemetryRow[] {
  if (!isValidTelemetryState(rawState)) return [];
  const trimmed = rawState.trim();
  if (!trimmed.startsWith("{")) return [];

  let parsed: Record<string, unknown>;
  try {
    const obj = JSON.parse(trimmed);
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) return [];
    parsed = obj as Record<string, unknown>;
  } catch {
    return [];
  }

  const rows: DiagnosticsTelemetryRow[] = [];
  const board = typeof parsed.board === "string" ? parsed.board.trim() : "";
  if (board) {
    rows.push({ label: "Hardware Board", value: board, code: true });
  }

  const chip = typeof parsed.chip === "string" ? parsed.chip.trim() : "";
  const psramMb = Number(parsed.psram_mb ?? 0);
  if (chip) {
    const psramSuffix =
      Number.isFinite(psramMb) && psramMb > 0
        ? ` • ${fmtNumber(psramMb, hass, 0)} MB PSRAM`
        : "";
    rows.push({ label: "Processor & PSRAM", value: `${chip}${psramSuffix}` });
  }

  const hasDisplay = Number(parsed.display ?? 0) === 1 && parsed.shape !== "none";
  if (parsed.display !== undefined) {
    if (!hasDisplay) {
      rows.push({ label: "Display Panel", value: "Headless" });
    } else {
      const w = Number(parsed.w ?? 0);
      const h = Number(parsed.h ?? 0);
      const shape = typeof parsed.shape === "string" ? parsed.shape.trim() : "";
      const panelTech =
        parsed.ips === 1 ? "IPS" : parsed.ips === 0 ? "AMOLED" : "";
      if (w > 0 && h > 0) {
        const parts = [`${w}×${h}`, shape, panelTech].filter(Boolean);
        rows.push({ label: "Display Panel", value: parts.join(" ") });
      }
    }
  }

  const traits: string[] = [];
  if (Number(parsed.touch) === 1) traits.push("Touch");
  if (Number(parsed.mic) === 1) traits.push("Mic");
  if (Number(parsed.spk) === 1) traits.push("Speaker");
  if (Number(parsed.mic) !== 1 && Number(parsed.spk) !== 1 && Number(parsed.audio) === 1) {
    traits.push("Audio");
  }
  if (Number(parsed.imu) === 1) traits.push("IMU");
  if (Number(parsed.battery) === 1) traits.push("Battery");
  if (Number(parsed.wearable) === 1) traits.push("Wearable");
  if (Number(parsed.stationary) === 1) traits.push("Stationary");
  if (traits.length) {
    rows.push({ label: "Hardware Traits", value: traits.join(", ") });
  }

  return rows;
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

  const networkItems = store.getSectionItems("network");
  const developerItems = store.getSectionItems("developer");

  const networkControlItems = networkItems.filter((it) =>
    INTERACTIVE_ENTITY_DOMAINS.has(it.domain),
  );
  const extraNetworkSensorItems = networkItems.filter(
    (it) =>
      !INTERACTIVE_ENTITY_DOMAINS.has(it.domain) &&
      !isInternalNetworkBlobEntity(it) &&
      !isSummaryDuplicateNetworkEntity(it),
  );

  const findNetworkState = (keyword: string): string => {
    const match = networkItems.find((it) =>
      `${it.name || ""} ${it.entity_id || ""}`.toLowerCase().includes(keyword),
    );
    return isValidTelemetryState(match?.state) ? String(match?.state).trim() : "";
  };

  const winRow = (curDevEntry?.ble_survey_rows || []).find((r) => r.is_winner);
  let signalText = "—";
  if (!isBleOnly) {
    if (curDevEntry?.wifi_rssi !== null && curDevEntry?.wifi_rssi !== undefined) {
      signalText = `${fmtNumber(curDevEntry.wifi_rssi, store.hass, 0)} dBm`;
    } else {
      const rawWifi = findNetworkState("wifi signal") || findNetworkState("wi-fi signal");
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
    live.device_sw_version || esp?.device?.sw_version || findNetworkState("firmware version") || "",
  ).replace(/^v/i, "");
  const fwVersionText = rawSw ? `v${rawSw}` : "—";
  const modelText = curDevEntry?.model_label || esp?.device?.model || "—";
  const ipStr = curDevEntry?.ip_address || findNetworkState("ip address") || "";
  const macStr = esp?.device?.mac || findNetworkState("mac address") || "";

  const devControlItems = developerItems.filter((it) =>
    INTERACTIVE_ENTITY_DOMAINS.has(it.domain),
  );
  const devSensorItems = developerItems.filter(
    (it) => !INTERACTIVE_ENTITY_DOMAINS.has(it.domain),
  );
  const linkReportEntity = networkItems.find((it) => {
    const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
    return low.includes("link report") || low.includes("link_report");
  });
  const manifestEntity = networkItems.find((it) => {
    const low = `${it.name || ""} ${it.entity_id || ""}`.toLowerCase();
    return low.includes("hardware manifest") || low.includes("hardware_manifest");
  });
  const linkRows = parseDeviceLinkReportRows(linkReportEntity?.state, store.hass);
  const manifestRows = parseDeviceHardwareManifestRows(manifestEntity?.state, store.hass);
  const hasDeveloperDrawer =
    !isBleOnly &&
    Boolean(
      devControlItems.length ||
        devSensorItems.length ||
        linkRows.length ||
        manifestRows.length,
    );

  const curPinPolicy = String(cfg.security_pin_policy || "auto");
  const hasPin = store.hasConfiguredSecurityPin;

  return html`<section id="view-tools">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Diagnostics</h3>`,
          contentClass: "stack",
          body: html`${networkControlItems.length
              ? html`<div class="settings-list">
                  ${networkControlItems.map((it) => renderNativeControlRow(store, it))}
                </div>`
              : nothing}
            <div class="kv-list">
              ${isBleOnly
                ? html`<div class="kv-row">
                      <span>BLE Signal</span>
                      <strong>${signalText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>BLE Target</span>
                      <strong>${cfg.ble_target_address ? html`<code>${cfg.ble_target_address}</code>` : "—"}</strong>
                    </div>`
                : html`<div class="kv-row">
                      <span>Model</span>
                      <strong>${modelText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>ESPHome Node</span>
                      <strong><code id="diag-node-name">${cfg.device_slug || "—"}</code></strong>
                    </div>
                    <div class="kv-row">
                      <span>Firmware Version</span>
                      <strong>${fwVersionText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>Latter SDK</span>
                      <strong id="diag-sdk-rev">${live.sdk_rev || "—"}</strong>
                    </div>
                    <div class="kv-row">
                      <span>Wi-Fi Signal</span>
                      <strong>${signalText}</strong>
                    </div>
                    <div class="kv-row">
                      <span>IP Address</span>
                      <strong>${ipStr ? html`<code>${ipStr}</code>` : "—"}</strong>
                    </div>
                    ${macStr
                      ? html`<div class="kv-row">
                          <span>MAC Address</span>
                          <strong><code>${macStr}</code></strong>
                        </div>`
                      : nothing}
                    ${extraNetworkSensorItems.map((it) => renderNativeControlRow(store, it))}`}
            </div>
            ${links.latter_device_id || links.entry_id
              ? html`<div class="settings-list">
                  ${renderSettingsRow({
                    id: "row-diagnostics",
                    label: "Diagnostics File",
                    description: "Downloads redacted Home Assistant diagnostics for troubleshooting.",
                    control: html`<button
                      type="button"
                      @click=${() => void store.downloadDeviceDiagnostics()}
                      class="btn btn-secondary btn-compact"
                    >
                      Download Diagnostics
                    </button>`,
                  })}
                </div>`
              : nothing}
            ${hasDeveloperDrawer
              ? html`<details class="sub-collapsible">
                  <summary>Developer &amp; Telemetry</summary>
                  <div class="card-content">
                    ${devControlItems.length
                      ? html`<div class="settings-list">
                          ${devControlItems.map((it) => renderNativeControlRow(store, it))}
                        </div>`
                      : nothing}
                    ${devSensorItems.length || linkRows.length || manifestRows.length
                      ? html`<div class="kv-list">
                          ${devSensorItems.map((it) => renderNativeControlRow(store, it))}
                          ${[...linkRows, ...manifestRows].map(
                            (row) => html`<div class="kv-row">
                              <span>${row.label}</span>
                              <strong>${row.code ? html`<code>${row.value}</code>` : row.value}</strong>
                            </div>`,
                          )}
                        </div>`
                      : nothing}
                  </div>
                </details>`
              : nothing}`,
          footerActions:
            !isBleOnly && (links.esphome_device_id || links.latter_device_id)
              ? html`<button
                  type="button"
                  id="btn-tools-open-in-ha"
                  @click=${() => store.openDeviceInHa()}
                  class="btn btn-text"
                >
                  Open in ESPHome
                </button>`
              : nothing,
        })}
      </div>

      <div class="column">
        ${!isBleOnly
          ? html`${renderCard({
                id: "card-device-security",
                title: "Perimeter Security",
                subtitle:
                  "Governs unlocking doors, disarming alarms, and opening garage or gate covers from this Device.",
                contentClass: "settings-list",
                body: html`${renderSelectRow({
                    id: "cfg-security_pin_policy",
                    label: "Perimeter Security Policy",
                    description: html`Auto requires a PIN on stationary wall panels when configured and allows roaming personal Devices. Effective policy: <strong>${live.effective_security_pin_policy || curPinPolicy}</strong>.`,
                    value: curPinPolicy,
                    rawOptions: SECURITY_PIN_POLICY_OPTIONS,
                    onChange: (val) =>
                      store.stageDeviceSetting(
                        "security_pin_policy",
                        val,
                        "cfg-security_pin_policy",
                      ),
                  })}
                  ${renderSettingsRow({
                    label: "Security PIN",
                    description:
                      "Write-only 4 to 12 digit numeric PIN verified server-side (PBKDF2-HMAC-SHA256) when the on-device keypad prompts. Never echoed back to the browser.",
                    stacked: true,
                    control: html`<div class="input-action-row">
                      <span class="chip ${hasPin ? "chip-success" : ""}">
                        ${hasPin ? "PIN configured" : "Not set"}
                      </span>
                      <input
                        type="password"
                        id="dev-security-pin-input"
                        inputmode="numeric"
                        pattern="[0-9]*"
                        autocomplete="new-password"
                        aria-label="New Security PIN (4 to 12 digits)"
                        placeholder=${hasPin ? "Enter new PIN to replace…" : "4 to 12 digits"}
                        .value=${store.devicePinDraft}
                        @input=${(ev: Event) => {
                          store.devicePinDraft = (ev.currentTarget as HTMLInputElement).value;
                          store.host.requestUpdate();
                        }}
                      />
                      <button
                        type="button"
                        ?disabled=${store.pinBusy || !store.devicePinDraft.trim()}
                        @click=${() => void store.saveSecurityPin("device")}
                        class="btn btn-primary btn-compact"
                      >
                        Save PIN
                      </button>
                      ${hasPin
                        ? html`<button
                            type="button"
                            ?disabled=${store.pinBusy}
                            @click=${() => void store.clearSecurityPin("device")}
                            class="btn btn-danger btn-compact"
                          >
                            Clear PIN
                          </button>`
                        : nothing}
                    </div>`,
                  })}`,
              })}
              ${renderCard({
                id: "card-replace-hardware",
                heading: html`<h3 class="card-title">Replace Hardware</h3>`,
                contentClass: "stack",
                body: html`<p class="row-description">
                    Moving to a replacement board? Download this Device's backup first, add the new ESPHome board in Home Assistant, and restore the backup onto it from System Tools.
                  </p>
                  <div class="input-action-row">
                    <button
                      type="button"
                      @click=${() => void store.exportBackup(store.activeSubentryId)}
                      class="btn btn-secondary"
                    >
                      Download Device Backup
                    </button>
                    <button
                      type="button"
                      @click=${() => store.openSystemSection("system_tools", "card-backup-restore")}
                      class="btn btn-text"
                    >
                      Open Backup &amp; Restore
                    </button>
                  </div>`,
              })}`
          : nothing}

        ${renderCard({
          heading: html`<h3 class="card-title">Danger Zone</h3>`,
          danger: true,
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: "Reset to Defaults",
              description:
                "Resets on-device preferences and/or Latter settings while keeping Wi-Fi and Home Assistant pairing.",
              control: html`<button
                type="button"
                @click=${() => store.openResetDeviceModal()}
                class="btn btn-danger"
              >
                Reset to Defaults
              </button>`,
            })}
            ${renderSettingsRow({
              label: "Remove Device",
              description:
                "Removes this subentry from Latter. The ESPHome device remains in Home Assistant.",
              control: html`<button
                type="button"
                @click=${() =>
                  store.openRemoveDeviceModal(
                    store.activeSubentryId,
                    data?.title || cfg.device_slug || "Device",
                  )}
                class="btn btn-danger"
              >
                Remove Device
              </button>`,
            })}`,
        })}
      </div>
    </div>
  </section>`;
}
