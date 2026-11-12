/**
 * Device Tools View (`tools`): Diagnostics, All Entities, Perimeter Security Policy + write-only PIN, Replace Hardware & Danger Zone.
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
        ${renderCard({
          heading: html`<h3 class="card-title">Diagnostics</h3>`,
          contentClass: "settings-list",
          body: html`${links.latter_device_id || links.entry_id
              ? renderSettingsRow({
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
                })
              : nothing}
            ${networkItems.map((it) => renderNativeControlRow(store, it))}
            ${developerItems.length
              ? html`<details class="sub-collapsible">
                  <summary>Developer</summary>
                  <div class="card-content settings-list">
                    ${developerItems.map((it) => renderNativeControlRow(store, it))}
                  </div>
                </details>`
              : nothing}`,
        })}

        ${!isBleOnly
          ? renderCard({
              title: "All Entities",
              contentClass: "stack",
              body: html`<input
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
                  : html`<p class="empty-state">No entities match this filter.</p>`}`,
            })
          : nothing}
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
