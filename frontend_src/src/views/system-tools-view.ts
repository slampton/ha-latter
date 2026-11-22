/**
 * System tools view (`system_tools`, `D-020` / `D-040` / `D-064` / `D-066`):
 * Notifications & announcements, doorbell & intercom audio, backup & restore,
 * perimeter security & signing, System & Device logs, and Support & diagnostics.
 */

import { renderCard, renderSettingsRow } from "../components/controls.js";
import { STUDIO_REV } from "../constants.js";
import { focusSafe, html, live, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";

const DOCS_URL = "https://github.com/slampton/ha-latter";
const ISSUES_URL = "https://github.com/slampton/ha-latter/issues";

export function renderSystemToolsView(store: StudioStore): TemplateResult {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const latterDevices = allDevices.filter((d) => d.kind !== "ble_tag");
  const bleTagCount = allDevices.length - latterDevices.length;
  const configuredCameras = (data?.system_config?.camera_entities || [])
    .map((c) => String(c || "").trim())
    .filter(Boolean);
  const primaryCamera = configuredCameras[0] || "";
  const canTestDoorbell = Boolean(primaryCamera && latterDevices.length > 0);
  const doorbellTestDescription = !primaryCamera
    ? store.t("tools_sys.doorbell_desc_no_cam")
    : !latterDevices.length
      ? store.t("tools_sys.doorbell_desc_no_dev")
      : store.t("tools_sys.doorbell_desc_ready", { camera: primaryCamera });
  const hasSystemPin = Boolean(data?.has_security_pin);
  const isBroadcast = store.announceMode === "broadcast";

  const sysInfo = data?.system_info;
  const haVer = sysInfo?.ha_version || store.hass?.config?.version || store.t("common.unknown");
  const rawIntVer = sysInfo?.integration_version || data?.version || "";
  const intVer = rawIntVer ? `v${rawIntVer}` : store.t("common.unknown");
  const sdkRev = sysInfo?.min_firmware_sdk_rev
    ? String(sysInfo.min_firmware_sdk_rev)
    : store.t("common.unknown");
  const studioRev = `rev ${String(sysInfo?.studio_rev ?? STUDIO_REV)}`;

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
          id: "card-notifications-announcements",
          title: store.t("card.notifications_announcements"),
          subtitle: store.t("tools_sys.announce_subtitle"),
          contentClass: "stack",
          body: html`<div
              role="radiogroup"
              aria-label=${store.t("tools_sys.announce_mode_aria")}
              class="segmented"
            >
              <button
                type="button"
                data-mode="notify"
                tabindex=${!isBroadcast ? "0" : "-1"}
                aria-checked=${String(!isBroadcast)}
                @click=${() => {
                  store.announceMode = "notify";
                  store.host.requestUpdate();
                }}
                @keydown=${onAnnounceRadioKey}
                role="radio"
              >
                ${store.t("tools_sys.screen_notification")}
              </button>
              <button
                type="button"
                data-mode="broadcast"
                tabindex=${isBroadcast ? "0" : "-1"}
                aria-checked=${String(isBroadcast)}
                @click=${() => {
                  store.announceMode = "broadcast";
                  store.host.requestUpdate();
                }}
                @keydown=${onAnnounceRadioKey}
                role="radio"
              >
                ${store.t("tools_sys.voice_broadcast")}
              </button>
            </div>

            <div class="stacked-field">
              <label for="ann-target">${store.t("tools_sys.target_label")}</label>
              <select
                id="ann-target"
                .value=${live(store.announceTarget)}
                @change=${(ev: Event) => {
                  store.announceTarget = (ev.currentTarget as HTMLSelectElement).value || "all";
                  store.host.requestUpdate();
                }}
              >
                <option value="all" .selected=${live(store.announceTarget === "all")}>
                  ${store.t("tools_sys.all_displays")}
                </option>
                <option
                  value="occupied_areas"
                  .selected=${live(store.announceTarget === "occupied_areas")}
                >
                  ${store.t("tools_sys.occupied_areas_only")}
                </option>
                ${latterDevices.map(
                  (d) =>
                    html`<option
                      value=${d.device_slug}
                      .selected=${live(store.announceTarget === d.device_slug)}
                    >
                      ${store.t("tools_sys.device_prefix", { title: d.title })}
                    </option>`,
                )}
              </select>
            </div>

            ${!isBroadcast
              ? html`<div class="stacked-field">
                    <label for="ann-title">${store.t("tools_sys.notification_title")}</label>
                    <input
                      type="text"
                      id="ann-title"
                      placeholder=${store.t("tools_sys.notification_title_placeholder")}
                      .value=${focusSafe(store.announceTitle)}
                      @input=${(ev: Event) => {
                        store.announceTitle = (ev.currentTarget as HTMLInputElement).value;
                      }}
                    />
                  </div>
                  <div class="list-row-main">
                    <div class="stacked-field">
                      <label for="ann-priority">${store.t("tools_sys.priority")}</label>
                      <select
                        id="ann-priority"
                        .value=${live(store.announcePriority)}
                        @change=${(ev: Event) => {
                          store.announcePriority = (ev.currentTarget as HTMLSelectElement).value as
                            | "normal"
                            | "warning"
                            | "critical";
                        }}
                      >
                        <option value="normal" .selected=${live(store.announcePriority === "normal")}>
                          ${store.t("tools_sys.priority_normal")}
                        </option>
                        <option value="warning" .selected=${live(store.announcePriority === "warning")}>
                          ${store.t("tools_sys.priority_warning")}
                        </option>
                        <option value="critical" .selected=${live(store.announcePriority === "critical")}>
                          ${store.t("tools_sys.priority_critical")}
                        </option>
                      </select>
                    </div>
                    <label class="inline-switch">
                      <input
                        type="checkbox"
                        role="switch"
                        .checked=${live(store.announceIncludeCamera)}
                        @change=${(ev: Event) => {
                          store.announceIncludeCamera = (
                            ev.currentTarget as HTMLInputElement
                          ).checked;
                        }}
                        class="switch"
                      />
                      <span>${store.t("tools_sys.include_camera")}</span>
                    </label>
                  </div>`
              : nothing}

            <div class="stacked-field">
              <label for="ann-message">${store.t("tools_sys.message")}</label>
              <textarea
                id="ann-message"
                rows="3"
                placeholder=${store.t("tools_sys.message_placeholder")}
                .value=${focusSafe(store.announceMessage)}
                @input=${(ev: Event) => {
                  store.announceMessage = (ev.currentTarget as HTMLTextAreaElement).value;
                }}
              ></textarea>
            </div>

            <div class="input-action-row">
              <button
                type="button"
                id="btn-send-announcement"
                @click=${() => void store.tools.sendAnnouncement()}
                class="btn btn-primary"
              >
                ${store.t("tools_sys.send_now")}
              </button>
            </div>`,
        })}

        ${renderCard({
          id: "card-doorbell-intercom-audio",
          title: store.t("card.doorbell_intercom_audio"),
          subtitle: store.t("tools_sys.doorbell_subtitle"),
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: store.t("tools_sys.source_device"),
              forId: "doorbell-test-device",
              description: store.t("tools_sys.source_device_desc"),
              control: html`<select
                id="doorbell-test-device"
                ?disabled=${!canTestDoorbell}
                .value=${live(store.doorbellTestSubentryId)}
                @change=${(ev: Event) => {
                  store.doorbellTestSubentryId = (ev.currentTarget as HTMLSelectElement).value;
                  store.host.requestUpdate();
                }}
              >
                ${latterDevices.length
                  ? latterDevices.map(
                      (d) =>
                        html`<option
                          value=${d.subentry_id}
                          .selected=${live(d.subentry_id === store.doorbellTestSubentryId)}
                        >
                          ${d.title}
                        </option>`,
                    )
                  : html`<option value="" .selected=${live(!store.doorbellTestSubentryId)}>
                      ${store.t("tools_sys.no_latter_devices")}
                    </option>`}
              </select>`,
            })}
            ${renderSettingsRow({
              id: "row-doorbell-test-reply",
              label: store.t("tools_sys.test_door_reply"),
              forId: "doorbell-test-reply",
              description: doorbellTestDescription,
              stacked: true,
              control: html`<div class="input-action-row">
                <input
                  type="text"
                  id="doorbell-test-reply"
                  maxlength="160"
                  placeholder=${store.t("tools_sys.doorbell_reply_placeholder")}
                  ?disabled=${!canTestDoorbell}
                  .value=${focusSafe(store.doorbellTestReply)}
                  @input=${(ev: Event) => {
                    store.doorbellTestReply = (ev.currentTarget as HTMLInputElement).value;
                  }}
                />
                <button
                  type="button"
                  id="btn-play-door-speaker"
                  ?disabled=${!canTestDoorbell}
                  @click=${() => void store.entity.testDoorbellSpeaker()}
                  class="btn btn-primary btn-compact"
                >
                  ${store.t("tools_sys.play_door_speaker")}
                </button>
                ${!primaryCamera
                  ? html`<button
                      type="button"
                      @click=${() =>
                        store.openSystemSection("shared_entities", "card-cameras-doorbell")}
                      class="btn btn-text btn-compact"
                    >
                      ${store.t("action.open_shared_entities")}
                    </button>`
                  : nothing}
              </div>`,
            })}`,
        })}

        <details
          id="card-system-logs"
          ?open=${store.logsOpen}
          @toggle=${(ev: Event) =>
            store.tools.onToggleLogsDetails((ev.currentTarget as HTMLDetailsElement).open)}
          class="card"
        >
          <summary class="card-header">
            <div class="card-heading">
              <h3 class="card-title">${store.t("card.system_device_logs")}</h3>
            </div>
          </summary>
          <div class="card-content stack">
            <div class="input-action-row">
              <select
                aria-label=${store.t("tools_sys.logs_filter_aria")}
                .value=${live(store.logFilter)}
                @change=${(ev: Event) => {
                  store.logFilter = (ev.currentTarget as HTMLSelectElement).value || "all";
                  store.host.requestUpdate();
                }}
              >
                <option value="all" .selected=${live(store.logFilter === "all")}>
                  ${store.t("tools_sys.logs_all")}
                </option>
                <option value="latter" .selected=${live(store.logFilter === "latter")}>
                  ${store.t("tools_sys.logs_studio")}
                </option>
                <option value="errors" .selected=${live(store.logFilter === "errors")}>
                  ${store.t("tools_sys.logs_errors")}
                </option>
                ${allDevices.map(
                  (d) =>
                    html`<option
                      value=${`device:${d.device_slug}`}
                      .selected=${live(store.logFilter === `device:${d.device_slug}`)}
                    >
                      ${store.t("tools_sys.device_prefix", { title: d.title })}
                    </option>`,
                )}
              </select>
              <button
                type="button"
                @click=${() => void store.refreshState({ includeLogs: true })}
                class="btn btn-secondary btn-compact"
              >
                ${store.t("tools_sys.refresh_logs")}
              </button>
              <button
                type="button"
                @click=${() => void store.tools.copyLogsToClipboard()}
                class="btn btn-secondary btn-compact"
              >
                ${store.t("tools_sys.copy_logs")}
              </button>
              <button
                type="button"
                id="btn-clear-internal-logs"
                @click=${() => void store.tools.clearInternalLogs()}
                class="btn btn-text btn-compact"
              >
                ${store.t("tools_sys.clear_logs")}
              </button>
              <button
                type="button"
                @click=${() => store.openHaPage("/config/logs")}
                class="btn btn-text btn-compact"
              >
                ${store.t("action.open_ha_logs")}
              </button>
            </div>
            <pre class="log-output">${store.tools.formatVisibleLogs()}</pre>
          </div>
        </details>
      </div>

      <div class="column">
        ${renderCard({
          id: "card-backup-restore",
          handoffActive: store.isHandoffTarget("card-backup-restore"),
          title: store.t("card.backup_restore"),
          subtitle: store.t("tools_sys.backup_subtitle"),
          contentClass: "stack",
          body: html`<div class="stacked-field">
              <label for="bkp-scope-select">${store.t("tools_sys.export_scope")}</label>
              <div class="input-action-row">
                <select
                  id="bkp-scope-select"
                  .value=${live(store.backupExportScope)}
                  @change=${(ev: Event) => {
                    store.backupExportScope = (ev.currentTarget as HTMLSelectElement).value;
                    store.host.requestUpdate();
                  }}
                >
                  <option value="system" .selected=${live(store.backupExportScope === "system")}>
                    ${store.t("tools_sys.entire_system")}
                  </option>
                  ${allDevices.map(
                    (d) =>
                      html`<option
                        value=${`device:${d.subentry_id}`}
                        .selected=${live(store.backupExportScope === `device:${d.subentry_id}`)}
                      >
                        ${store.t("tools_sys.device_prefix", { title: d.title })}
                      </option>`,
                  )}
                </select>
                <button
                  type="button"
                  id="btn-download-backup"
                  @click=${() => void store.tools.exportBackup()}
                  class="btn btn-secondary"
                >
                  ${store.t("action.download_backup")}
                </button>
              </div>
            </div>

            <div class="stacked-field">
              <label for="input-restore-backup">${store.t("tools_sys.restore_from_backup")}</label>
              <input
                type="file"
                id="input-restore-backup"
                accept=".json,application/json"
                @change=${(ev: Event) => {
                  const inp = ev.currentTarget as HTMLInputElement;
                  store.selectedBackupFile = inp.files && inp.files[0] ? inp.files[0] : null;
                  store.host.requestUpdate();
                }}
              />
            </div>

            <div class="stacked-field">
              <label for="bkp-restore-device">${store.t("tools_sys.target_device_restore")}</label>
              <select
                id="bkp-restore-device"
                .value=${live(store.backupRestoreSubentryId)}
                @change=${(ev: Event) => {
                  store.backupRestoreSubentryId = (ev.currentTarget as HTMLSelectElement).value;
                  store.host.requestUpdate();
                }}
              >
                <option value="" .selected=${live(!store.backupRestoreSubentryId)}>
                  ${store.t("tools_sys.auto_system_backup")}
                </option>
                ${allDevices.map(
                  (d) =>
                    html`<option
                      value=${d.subentry_id}
                      .selected=${live(d.subentry_id === store.backupRestoreSubentryId)}
                    >
                      ${d.title}
                    </option>`,
                )}
              </select>
            </div>

            <div class="input-action-row">
              <button
                type="button"
                id="btn-restore-backup"
                ?disabled=${!store.selectedBackupFile}
                @click=${() => void store.tools.requestRestoreFromUploadedFile()}
                class="btn btn-primary"
              >
                ${store.t("action.restore_backup")}
              </button>
            </div>`,
        })}

        ${renderCard({
          id: "card-perimeter-security",
          handoffActive: store.isHandoffTarget("card-perimeter-security"),
          title: store.t("card.perimeter_security_signing"),
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              label: store.t("tools_sys.system_pin_label"),
              description: store.t("tools_sys.system_pin_desc"),
              stacked: true,
              control: html`<div class="input-action-row">
                <span
                  id="sys-security-pin-status"
                  class="chip ${hasSystemPin ? "chip-success" : ""}"
                >
                  ${hasSystemPin
                    ? store.t("status.pin_configured")
                    : store.t("status.pin_not_set")}
                </span>
                <input
                  type="password"
                  id="sys-security-pin-input"
                  inputmode="numeric"
                  pattern="[0-9]*"
                  autocomplete="new-password"
                  aria-label=${store.t("tools_sys.system_pin_aria")}
                  placeholder=${hasSystemPin
                    ? store.t("tools_sys.pin_replace_placeholder")
                    : store.t("tools_sys.pin_digits_placeholder")}
                  .value=${focusSafe(store.systemPinDraft)}
                  @input=${(ev: Event) => {
                    store.systemPinDraft = (ev.currentTarget as HTMLInputElement).value;
                    store.host.requestUpdate();
                  }}
                />
                <button
                  type="button"
                  id="btn-save-security-pin"
                  ?disabled=${store.pinBusy || !store.systemPinDraft.trim()}
                  @click=${() => void store.tools.saveSecurityPin("system")}
                  class="btn btn-primary btn-compact"
                >
                  ${store.t("tools_sys.save_pin")}
                </button>
                ${hasSystemPin
                  ? html`<button
                      type="button"
                      id="btn-clear-security-pin"
                      ?disabled=${store.pinBusy}
                      @click=${() => store.tools.requestClearSecurityPin("system")}
                      class="btn btn-danger btn-compact"
                    >
                      ${store.t("tools_sys.clear_pin")}
                    </button>`
                  : nothing}
              </div>`,
            })}
            ${renderSettingsRow({
              label: store.t("tools_sys.signing_key_label"),
              description: store.t("tools_sys.signing_key_desc"),
              control: html`<button
                type="button"
                id="btn-rotate-signing-key"
                @click=${() => store.tools.requestRotateSigningKey()}
                class="btn btn-secondary btn-compact"
              >
                ${store.t("tools_sys.rotate_signing_key")}
              </button>`,
            })}`,
        })}

        ${renderCard({
          id: "card-support-diagnostics",
          title: store.t("card.support_diagnostics"),
          subtitle: store.t("card.support_subtitle"),
          contentClass: "stack",
          footerActions: html`<a
              href=${DOCS_URL}
              target="_blank"
              rel="noopener noreferrer"
              class="btn btn-text"
            >
              ${store.t("support.documentation")}
            </a>
            <a
              href=${ISSUES_URL}
              target="_blank"
              rel="noopener noreferrer"
              class="btn btn-text"
            >
              ${store.t("support.report_issue")}
            </a>`,
          body: html`<div class="kv-list">
              <div class="kv-row">
                <span>${store.t("support.ha_version")}</span>
                <strong>${haVer}</strong>
              </div>
              <div class="kv-row">
                <span>${store.t("support.integration_version")}</span>
                <strong>${intVer}</strong>
              </div>
              <div class="kv-row">
                <span>${store.t("support.sdk_rev")}</span>
                <strong>${sdkRev}</strong>
              </div>
              <div class="kv-row">
                <span>${store.t("support.studio_rev")}</span>
                <strong>${studioRev}</strong>
              </div>
              <div class="kv-row">
                <span>${store.t("support.managed_devices")}</span>
                <strong>${store.t("support.managed_devices_value", {
                  total: allDevices.length,
                  displays: latterDevices.length,
                  trackers: bleTagCount,
                })}</strong>
              </div>
            </div>
            <div class="input-action-row">
              <button
                type="button"
                id="btn-download-system-diagnostics"
                @click=${() => void store.tools.downloadSystemDiagnostics()}
                class="btn btn-primary"
              >
                ${store.t("support.download_system_diagnostics")}
              </button>
              <button
                type="button"
                id="btn-copy-system-info"
                @click=${() => void store.tools.copySystemInfoSummary()}
                class="btn btn-secondary"
              >
                ${store.t("support.copy_summary")}
              </button>
            </div>`,
        })}
      </div>
    </div>
  </section>`;
}
