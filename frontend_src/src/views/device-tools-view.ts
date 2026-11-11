/**
 * Device Tools View (`tools`): Diagnostics, All Entities, Perimeter Security Policy + write-only PIN, Replace Hardware & Danger Zone.
 */

import { renderNativeControlRow } from "../components/controls.js";
import { SECURITY_PIN_POLICY_OPTIONS } from "../constants.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { EspHomeEntityItem } from "../types.js";
import { entityLabel } from "../utils/format.js";

export function renderDeviceToolsView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const live = data?.live || {};
  const links = data?.links || {};
  const isBleOnly = cfg.kind === "ble_tag";

  const networkItems = store.getSectionItems("network");
  const developerItems = store.getSectionItems("developer");

  const allItems: EspHomeEntityItem[] = [];
  for (const sec of data?.esphome?.sections || []) {
    for (const it of sec.items || []) {
      allItems.push(it);
    }
  }
  const q = store.entitySearchQuery.trim().toLowerCase();
  const filteredEntities = q
    ? allItems.filter(
        (it) =>
          it.entity_id.toLowerCase().includes(q) ||
          (it.name || "").toLowerCase().includes(q) ||
          String(it.state || "").toLowerCase().includes(q),
      )
    : allItems;

  const curPinPolicy = String(cfg.security_pin_policy || "auto");
  const hasPin = store.hasConfiguredSecurityPin;

  return html`<section id="view-tools">
    <div class="columns">
      <div class="column">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Diagnostics</h3>
          </div>
          <div class="card-content settings-list">
            ${links.latter_device_id || links.entry_id
              ? html`<div id="row-diagnostics" class="settings-row">
                  <div class="settings-row-text">
                    <span class="row-label">Diagnostics File</span>
                    <p class="row-description">
                      Downloads redacted Home Assistant diagnostics for troubleshooting.
                    </p>
                  </div>
                  <div class="settings-row-control">
                    <button
                      type="button"
                      @click=${() => void store.downloadDeviceDiagnostics()}
                      class="btn btn-secondary btn-compact"
                    >
                      Download Diagnostics
                    </button>
                  </div>
                </div>`
              : nothing}

            ${networkItems.map((it) => renderNativeControlRow(store, it))}

            ${developerItems.length
              ? html`<details class="sub-collapsible">
                  <summary>Developer</summary>
                  <div class="card-content settings-list">
                    ${developerItems.map((it) => renderNativeControlRow(store, it))}
                  </div>
                </details>`
              : nothing}
          </div>
        </div>

        ${!isBleOnly
          ? html`<div class="card">
              <div class="card-header">
                <h3 class="card-title">All Entities</h3>
              </div>
              <div class="card-content stack">
                <input
                  type="search"
                  aria-label="Filter Device entities"
                  placeholder="Filter by entity name, ID, or state…"
                  .value=${store.entitySearchQuery}
                  @input=${(ev: Event) => {
                    store.entitySearchQuery = (ev.currentTarget as HTMLInputElement).value;
                    store.host.requestUpdate();
                  }}
                />
                ${filteredEntities.length
                  ? html`<div class="kv-list">
                      ${filteredEntities.map(
                        (it) => html`<div class="kv-row">
                          <span>${entityLabel(it.name || it.entity_id)} <code>${it.entity_id}</code></span>
                          <strong>${it.state}${it.unit ? ` ${it.unit}` : ""}</strong>
                        </div>`,
                      )}
                    </div>`
                  : html`<p class="empty-state">No entities match this filter.</p>`}
              </div>
            </div>`
          : nothing}
      </div>

      <div class="column">
        ${!isBleOnly
          ? html`<div id="card-device-security" class="card">
                <div class="card-header">
                  <div class="card-heading">
                    <h3 class="card-title">Perimeter Security</h3>
                    <p class="card-subtitle">
                      Governs unlocking doors, disarming alarms, and opening garage or gate covers from this Device.
                    </p>
                  </div>
                </div>
                <div class="card-content settings-list">
                  <div class="settings-row">
                    <div class="settings-row-text">
                      <label for="cfg-security_pin_policy" class="row-label">Perimeter Security Policy</label>
                      <p class="row-description">
                        Auto requires a PIN on stationary wall panels when configured and allows roaming personal Devices. Effective policy: <strong>${live.effective_security_pin_policy || curPinPolicy}</strong>.
                      </p>
                    </div>
                    <div class="settings-row-control">
                      <select
                        id="cfg-security_pin_policy"
                        .value=${curPinPolicy}
                        @change=${(ev: Event) =>
                          store.stageDeviceSetting(
                            "security_pin_policy",
                            (ev.currentTarget as HTMLSelectElement).value,
                            "cfg-security_pin_policy",
                          )}
                      >
                        ${SECURITY_PIN_POLICY_OPTIONS.map(
                          (opt) =>
                            html`<option value=${opt.value} ?selected=${opt.value === curPinPolicy}>
                              ${opt.label}
                            </option>`,
                        )}
                      </select>
                    </div>
                  </div>

                  <div class="settings-row stacked">
                    <div class="settings-row-text">
                      <span class="row-label">Security PIN</span>
                      <p class="row-description">
                        Write-only 4 to 12 digit numeric PIN verified server-side (PBKDF2-HMAC-SHA256) when the on-device keypad prompts. Never echoed back to the browser.
                      </p>
                    </div>
                    <div class="settings-row-control">
                      <div class="input-action-row">
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
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div id="card-replace-hardware" class="card">
                <div class="card-header">
                  <h3 class="card-title">Replace Hardware</h3>
                </div>
                <div class="card-content stack">
                  <p class="row-description">
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
                  </div>
                </div>
              </div>`
          : nothing}

        <div class="card danger">
          <div class="card-header">
            <h3 class="card-title">Danger Zone</h3>
          </div>
          <div class="card-content settings-list">
            <div class="settings-row">
              <div class="settings-row-text">
                <span class="row-label">Reset to Defaults</span>
                <p class="row-description">
                  Resets on-device preferences and/or Latter settings while keeping Wi-Fi and Home Assistant pairing.
                </p>
              </div>
              <div class="settings-row-control">
                <button
                  type="button"
                  @click=${() => store.openResetDeviceModal()}
                  class="btn btn-danger"
                >
                  Reset to Defaults
                </button>
              </div>
            </div>

            <div class="settings-row">
              <div class="settings-row-text">
                <span class="row-label">Remove Device</span>
                <p class="row-description">
                  Removes this subentry from Latter. The ESPHome device remains in Home Assistant.
                </p>
              </div>
              <div class="settings-row-control">
                <button
                  type="button"
                  @click=${() =>
                    store.openRemoveDeviceModal(
                      store.activeSubentryId,
                      data?.title || cfg.device_slug || "Device",
                    )}
                  class="btn btn-danger"
                >
                  Remove Device
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>`;
}
