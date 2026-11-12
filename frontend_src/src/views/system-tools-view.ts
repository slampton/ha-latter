/**
 * System Tools View (`system_tools`): Notifications & Announcements, Backup & Restore, Perimeter Security & Signing, and Logs-only `system_log`.
 */

import { renderCard, renderSettingsRow } from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";

export function renderSystemToolsView(store: StudioStore): TemplateResult {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const latterDevices = allDevices.filter((d) => d.kind !== "ble_tag");
  const hasSystemPin = Boolean(data?.has_security_pin);
  const isBroadcast = store.announceMode === "broadcast";

  const onAnnounceRadioKey = (ev: Event): void => {
    const kev = ev as KeyboardEvent;
    if (kev.key !== "ArrowLeft" && kev.key !== "ArrowRight") return;
    kev.preventDefault();
    const nextMode = store.announceMode === "notify" ? "broadcast" : "notify";
    store.announceMode = nextMode;
    store.host.requestUpdate();
    const group = (kev.currentTarget as HTMLElement).parentElement;
    const nextBtn = group?.querySelector(
      `[data-mode="${nextMode}"]`,
    ) as HTMLButtonElement | null;
    nextBtn?.focus();
  };

  return html`<section id="view-system_tools">
    <div class="columns">
      <div class="column">
        ${renderCard({
          heading: html`<h3 class="card-title">Notifications &amp; Announcements</h3>`,
          subtitle:
            "Send screen popups or spoken intercom broadcasts to all Devices, Occupied Areas, or one display.",
          contentClass: "stack",
          body: html`<div role="radiogroup" aria-label="Announcement mode" class="segmented">
              <button
                type="button"
                data-mode="notify"
                tabindex=${!isBroadcast ? "0" : "-1"}
                aria-checked=${!isBroadcast}
                @click=${() => {
                  store.announceMode = "notify";
                  store.host.requestUpdate();
                }}
                @keydown=${onAnnounceRadioKey}
                role="radio"
              >
                Screen Notification
              </button>
              <button
                type="button"
                data-mode="broadcast"
                tabindex=${isBroadcast ? "0" : "-1"}
                aria-checked=${isBroadcast}
                @click=${() => {
                  store.announceMode = "broadcast";
                  store.host.requestUpdate();
                }}
                @keydown=${onAnnounceRadioKey}
                role="radio"
              >
                Voice Broadcast
              </button>
            </div>

            <div class="stacked-field">
              <label for="ann-target">Target</label>
              <select
                id="ann-target"
                .value=${store.announceTarget}
                @change=${(ev: Event) => {
                  store.announceTarget = (ev.currentTarget as HTMLSelectElement).value || "all";
                  store.host.requestUpdate();
                }}
              >
                <option value="all" ?selected=${store.announceTarget === "all"}>
                  All Latter Displays
                </option>
                <option
                  value="occupied_areas"
                  ?selected=${store.announceTarget === "occupied_areas"}
                >
                  Occupied Areas Only
                </option>
                ${latterDevices.map(
                  (d) =>
                    html`<option
                      value=${d.device_slug}
                      ?selected=${store.announceTarget === d.device_slug}
                    >
                      Device: ${d.title}
                    </option>`,
                )}
              </select>
            </div>

            ${!isBroadcast
              ? html`<div class="stacked-field">
                    <label for="ann-title">Notification Title</label>
                    <input
                      type="text"
                      id="ann-title"
                      placeholder="e.g. Front Gate"
                      .value=${store.announceTitle}
                      @input=${(ev: Event) => {
                        store.announceTitle = (ev.currentTarget as HTMLInputElement).value;
                      }}
                    />
                  </div>
                  <div class="list-row-main">
                    <div class="stacked-field">
                      <label for="ann-priority">Priority</label>
                      <select
                        id="ann-priority"
                        .value=${store.announcePriority}
                        @change=${(ev: Event) => {
                          store.announcePriority = (ev.currentTarget as HTMLSelectElement).value as
                            | "normal"
                            | "warning"
                            | "critical";
                        }}
                      >
                        <option value="normal">Normal</option>
                        <option value="warning">Warning</option>
                        <option value="critical">Critical</option>
                      </select>
                    </div>
                    <label class="inline-switch">
                      <input
                        type="checkbox"
                        role="switch"
                        .checked=${store.announceIncludeCamera}
                        @change=${(ev: Event) => {
                          store.announceIncludeCamera = (
                            ev.currentTarget as HTMLInputElement
                          ).checked;
                        }}
                        class="switch"
                      />
                      <span>Include Primary Camera</span>
                    </label>
                  </div>`
              : nothing}

            <div class="stacked-field">
              <label for="ann-message">Message</label>
              <textarea
                id="ann-message"
                rows="3"
                placeholder="Message to display or speak…"
                .value=${store.announceMessage}
                @input=${(ev: Event) => {
                  store.announceMessage = (ev.currentTarget as HTMLTextAreaElement).value;
                }}
              ></textarea>
            </div>

            <div class="input-action-row">
              <button
                type="button"
                @click=${() => void store.sendAnnouncement()}
                class="btn btn-primary"
              >
                Send Now
              </button>
            </div>`,
        })}

        <details
          ?open=${store.logsOpen}
          @toggle=${(ev: Event) =>
            store.onToggleLogsDetails((ev.currentTarget as HTMLDetailsElement).open)}
          class="card"
        >
          <summary class="card-header">
            <div class="card-heading">
              <h3 class="card-title">System &amp; Device Logs</h3>
            </div>
          </summary>
          <div class="card-content stack">
            <div class="input-action-row">
              <select
                aria-label="Filter diagnostic logs"
                .value=${store.logFilter}
                @change=${(ev: Event) => {
                  store.logFilter = (ev.currentTarget as HTMLSelectElement).value || "all";
                  store.host.requestUpdate();
                }}
              >
                <option value="all" ?selected=${store.logFilter === "all"}>All Events</option>
                <option value="latter" ?selected=${store.logFilter === "latter"}>Latter Studio</option>
                <option value="errors" ?selected=${store.logFilter === "errors"}>
                  Warnings &amp; Errors
                </option>
                ${allDevices.map(
                  (d) =>
                    html`<option
                      value=${`device:${d.device_slug}`}
                      ?selected=${store.logFilter === `device:${d.device_slug}`}
                    >
                      Device: ${d.title}
                    </option>`,
                )}
              </select>
              <button
                type="button"
                @click=${() => void store.refreshState({ includeLogs: true })}
                class="btn btn-secondary btn-compact"
              >
                Refresh Logs
              </button>
              <button
                type="button"
                @click=${() => void store.copyLogsToClipboard()}
                class="btn btn-secondary btn-compact"
              >
                Copy Logs
              </button>
              <button
                type="button"
                @click=${() => void store.clearInternalLogs()}
                class="btn btn-text btn-compact"
              >
                Clear Studio Events
              </button>
              <button
                type="button"
                @click=${() => store.openHaPage("/config/logs")}
                class="btn btn-text btn-compact"
              >
                Open Native HA Logs
              </button>
            </div>
            <pre class="log-output">${store.formatVisibleLogs()}</pre>
          </div>
        </details>
      </div>

      <div class="column">
        ${renderCard({
          id: "card-backup-restore",
          heading: html`<h3 class="card-title">Backup &amp; Restore</h3>`,
          subtitle:
            "Export or restore non-secret System and Device configurations as portable JSON bundles.",
          contentClass: "stack",
          body: html`<div class="stacked-field">
              <label for="bkp-scope-select">Export Scope</label>
              <div class="input-action-row">
                <select
                  id="bkp-scope-select"
                  .value=${store.backupExportScope}
                  @change=${(ev: Event) => {
                    store.backupExportScope = (ev.currentTarget as HTMLSelectElement).value;
                    store.host.requestUpdate();
                  }}
                >
                  <option value="system" ?selected=${store.backupExportScope === "system"}>
                    Entire System + All Devices
                  </option>
                  ${allDevices.map(
                    (d) =>
                      html`<option
                        value=${`device:${d.subentry_id}`}
                        ?selected=${store.backupExportScope === `device:${d.subentry_id}`}
                      >
                        Device: ${d.title}
                      </option>`,
                  )}
                </select>
                <button
                  type="button"
                  @click=${() => void store.exportBackup()}
                  class="btn btn-secondary"
                >
                  Download Backup
                </button>
              </div>
            </div>

            <div class="stacked-field">
              <label for="bkp-upload-file">Restore From Backup</label>
              <input
                type="file"
                id="bkp-upload-file"
                accept=".json,application/json"
                @change=${(ev: Event) => {
                  const inp = ev.currentTarget as HTMLInputElement;
                  store.selectedBackupFile = inp.files && inp.files[0] ? inp.files[0] : null;
                  store.host.requestUpdate();
                }}
              />
            </div>

            <div class="stacked-field">
              <label for="bkp-restore-device">Target Device (for Single-Device Backups)</label>
              <select
                id="bkp-restore-device"
                .value=${store.backupRestoreSubentryId}
                @change=${(ev: Event) => {
                  store.backupRestoreSubentryId = (ev.currentTarget as HTMLSelectElement).value;
                  store.host.requestUpdate();
                }}
              >
                <option value="">— Automatic (System Backup) —</option>
                ${allDevices.map(
                  (d) =>
                    html`<option
                      value=${d.subentry_id}
                      ?selected=${d.subentry_id === store.backupRestoreSubentryId}
                    >
                      ${d.title}
                    </option>`,
                )}
              </select>
            </div>

            <label class="inline-switch">
              <input
                type="checkbox"
                id="bkp-restore-esp"
                role="switch"
                .checked=${store.backupRestoreEsp}
                @change=${(ev: Event) => {
                  store.backupRestoreEsp = (ev.currentTarget as HTMLInputElement).checked;
                }}
                class="switch"
              />
              <span>Restore On-Device ESPHome Controls</span>
            </label>

            <div class="input-action-row">
              <button
                type="button"
                ?disabled=${!store.selectedBackupFile}
                @click=${() => void store.restoreFromUploadedFile()}
                class="btn btn-primary"
              >
                Restore Backup
              </button>
            </div>`,
        })}

        ${renderCard({
          title: "Perimeter Security & Signing",
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: "System Security PIN",
              description:
                "Default numeric PIN (4 to 12 digits, PBKDF2-HMAC-SHA256) used when a Device's Perimeter Security Policy requires PIN verification.",
              stacked: true,
              control: html`<div class="input-action-row">
                <span id="sys-security-pin-status" class="chip ${hasSystemPin ? "chip-success" : ""}">
                  ${hasSystemPin ? "PIN configured" : "Not set"}
                </span>
                <input
                  type="password"
                  id="sys-security-pin-input"
                  inputmode="numeric"
                  pattern="[0-9]*"
                  autocomplete="new-password"
                  aria-label="System Security PIN (4 to 12 digits)"
                  placeholder=${hasSystemPin ? "Enter new PIN to replace…" : "4 to 12 digits"}
                  .value=${store.systemPinDraft}
                  @input=${(ev: Event) => {
                    store.systemPinDraft = (ev.currentTarget as HTMLInputElement).value;
                    store.host.requestUpdate();
                  }}
                />
                <button
                  type="button"
                  ?disabled=${store.pinBusy || !store.systemPinDraft.trim()}
                  @click=${() => void store.saveSecurityPin("system")}
                  class="btn btn-primary btn-compact"
                >
                  Save PIN
                </button>
                ${hasSystemPin
                  ? html`<button
                      type="button"
                      id="btn-clear-security-pin"
                      ?disabled=${store.pinBusy}
                      @click=${() => void store.clearSecurityPin("system")}
                      class="btn btn-danger btn-compact"
                    >
                      Clear PIN
                    </button>`
                  : nothing}
              </div>`,
            })}
            ${renderSettingsRow({
              label: "HTTP Resource Signing Key",
              description:
                "Rotates the System HMAC secret and pushes refreshed signed artwork, map, camera, and wallpaper URLs to online Devices.",
              control: html`<button
                type="button"
                @click=${() => void store.rotateSigningKey()}
                class="btn btn-secondary btn-compact"
              >
                Rotate Signing Key
              </button>`,
            })}`,
        })}
      </div>
    </div>
  </section>`;
}
