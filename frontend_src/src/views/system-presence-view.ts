/**
 * System BLE & Area Presence View (`area_tracking`):
 * Live Area Presence & Sensor Fusion, Spatial Engine Settings, Per-Scanner BLE Calibration, and Multi-Scanner Area Signatures.
 */

import { renderCard, renderSettingsRow } from "../components/controls.js";
import { html, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { fmtAgo, fmtDateTime, fmtDistance, fmtNumber, fmtPercent, rssiToPercent } from "../utils/format.js";

const FUSION_MODE_OPTIONS: ReadonlyArray<{ val: string; label: string }> = [
  { val: "weighted", label: "Weighted (BLE and sensors)" },
  { val: "any_or", label: "Either (BLE or a sensor)" },
  { val: "ble_only", label: "BLE only" },
  { val: "ble_and_sensor", label: "Both (BLE and a sensor)" },
];

export function renderSystemPresenceView(store: StudioStore): TemplateResult {
  const data = store.state;
  const sysCfg = data?.system_config;
  const presenceRows = data?.live?.area_presence_grid || [];
  const signatures = data?.ble_area_signatures || [];
  const allDevs = data?.system_devices || [];
  const bleDevs = allDevs.filter((d) => d.has_ble || d.ble_tracked || d.kind === "ble_tag");
  const activeSurveyDev = store.getActiveSurveyDevice() || bleDevs[0];
  const surveyRows = activeSurveyDev?.ble_survey_rows || [];
  const packetsSeen = activeSurveyDev?.ble_packets_seen ?? 0;

  return html`<section id="view-area_tracking">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Live Area Presence & Sensor Fusion",
          subtitle:
            "Combines Bluetooth proxy telemetry (with 6.0 dB cross-floor attenuation) and Area occupancy sensors.",
          body: html`<div id="area-presence-grid-box" class="stack">
            ${presenceRows.length
              ? repeat(
                  presenceRows,
                  (r) => r.area_id,
                  (r) => {
                    const isOcc = Boolean(r.is_occupied);
                    const occList = r.occupant_names || [];
                    const occNames = occList.length
                      ? occList.join(", ")
                      : isOcc
                        ? "Occupied (sensor)"
                        : "Empty";
                    const parts: string[] = [occNames];
                    if (r.winning_rssi !== null && r.winning_rssi !== undefined) {
                      const distPart =
                        r.closest_distance_m !== null && r.closest_distance_m !== undefined
                          ? ` (~${fmtDistance(r.closest_distance_m, store.hass, r.closest_distance_ft)})`
                          : "";
                      parts.push(`BLE ${fmtNumber(r.winning_rssi, store.hass, 0)} dBm${distPart}`);
                    }
                    if (r.match_method === "signature") {
                      parts.push("signature match");
                    }
                    if (r.active_sensors && r.active_sensors.length) {
                      parts.push(
                        `${r.active_sensors.length} active sensor${r.active_sensors.length > 1 ? "s" : ""}`,
                      );
                    } else if (r.available_sensors && r.available_sensors.length) {
                      parts.push(
                        `${r.available_sensors.length} sensor${r.available_sensors.length > 1 ? "s" : ""} clear`,
                      );
                    }
                    if (r.floor_id) parts.push(`Floor: ${r.floor_name || r.floor_id}`);

                    const curMode = r.fusion_mode || "weighted";
                    const confPct = r.confidence_pct ?? 100;
                    const threshold = Number(r.fusion_threshold_pct ?? 50);
                    const chosen = r.fusion_sensors || [];
                    const choices = r.fusion_sensor_choices || [];
                    const thresholdId = `fusion-threshold-${r.area_id}`;

                    return html`<div class="fusion-area">
                      ${renderSettingsRow({
                        labelHtml: html`<span class="row-label">
                          ${r.area_name}
                          ${isOcc
                            ? html`<span class="chip chip-success">
                                Occupied • ${fmtPercent(confPct, store.hass)}
                              </span>`
                            : html`<span class="chip">Clear</span>`}
                        </span>`,
                        description: parts.join(" • "),
                        control: html`<select
                          aria-label=${`Fusion mode for ${r.area_name}`}
                          .value=${curMode}
                          @change=${(ev: Event) =>
                            void store.setAreaFusion(r.area_id, {
                              mode: (ev.currentTarget as HTMLSelectElement).value,
                            })}
                        >
                          ${FUSION_MODE_OPTIONS.map(
                            (m) =>
                              html`<option value=${m.val} ?selected=${m.val === curMode}>
                                ${m.label}
                              </option>`,
                          )}
                        </select>`,
                      })}

                      <details
                        ?open=${store.openFusionAreas.has(r.area_id)}
                        @toggle=${(ev: Event) => {
                          const isOpen = (ev.currentTarget as HTMLDetailsElement).open;
                          if (isOpen) store.openFusionAreas.add(r.area_id);
                          else store.openFusionAreas.delete(r.area_id);
                        }}
                        class="sub-collapsible"
                      >
                        <summary>Fusion Settings</summary>
                        <div class="card-content settings-list">
                          ${renderSettingsRow({
                            label: "Occupied At",
                            forId: thresholdId,
                            description:
                              curMode === "weighted"
                                ? "The Area counts as occupied when the combined BLE and sensor score reaches this."
                                : "Used by the Weighted mode only.",
                            control: html`<input
                                type="range"
                                id=${thresholdId}
                                min="20"
                                max="95"
                                step="5"
                                ?disabled=${curMode !== "weighted"}
                                .value=${String(threshold)}
                                @change=${(ev: Event) =>
                                  void store.setAreaFusion(r.area_id, {
                                    threshold_pct: Number(
                                      (ev.currentTarget as HTMLInputElement).value,
                                    ),
                                  })}
                              />
                              <span class="chip">${fmtPercent(threshold, store.hass)}</span>`,
                          })}
                          ${renderSettingsRow({
                            label: "Sensors That Count",
                            description: chosen.length
                              ? `${chosen.length} of ${choices.length} selected.`
                              : "None selected: every sensor in this Area counts.",
                            stacked: true,
                            control: choices.length
                              ? html`<div
                                  role="group"
                                  aria-label=${`Sensors that count in ${r.area_name}`}
                                  class="pill-list"
                                >
                                  ${choices.map((s) => {
                                    const on = chosen.includes(s.entity_id);
                                    const nextSensors = on
                                      ? chosen.filter((x) => x !== s.entity_id)
                                      : chosen.concat([s.entity_id]);
                                    return html`<span class="pill ${on ? "enabled" : ""}">
                                      <button
                                        type="button"
                                        aria-pressed=${String(on)}
                                        title=${s.entity_id}
                                        @click=${() =>
                                          void store.setAreaFusion(r.area_id, {
                                            sensors: nextSensors,
                                          })}
                                        class="pill-toggle"
                                      >
                                        ${on ? "✓ " : ""}${s.name}
                                      </button>
                                    </span>`;
                                  })}
                                </div>`
                              : html`<p class="empty-state">
                                  This Area has no occupancy, motion or door sensors.
                                </p>`,
                          })}
                        </div>
                      </details>
                    </div>`;
                  },
                )
              : html`<p class="empty-state">
                  No Bluetooth proxies or Area occupancy sensors found yet.
                </p>`}
          </div>`,
        })}

        ${renderCard({
          id: "card-spatial-engine",
          title: "Spatial Engine Settings",
          subtitle: "Applies across all BLE-tracked Devices and Areas in this System.",
          contentClass: "settings-list",
          body: html`${renderSettingsRow({
              forId: "sys-ble_attenuation",
              label: "Path-Loss Attenuation",
              description:
                "Controls how quickly Bluetooth signal strength drops with distance through walls (default 2.2).",
              control: html`<input
                type="number"
                id="sys-ble_attenuation"
                min="1.5"
                max="4.5"
                step="0.1"
                .value=${String(sysCfg?.ble_attenuation ?? 2.2)}
                @change=${(ev: Event) => {
                  const val = Number((ev.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(val)) {
                    store.stageSystemSetting("ble_attenuation", val, "sys-ble_attenuation");
                  }
                }}
              />`,
            })}
            ${renderSettingsRow({
              forId: "sys-ble_max_radius_m",
              label: "Maximum Area Radius",
              description:
                "Ignores Bluetooth proxies farther than this distance in meters so outdoor signals do not claim indoor Areas.",
              control: html`<input
                type="number"
                id="sys-ble_max_radius_m"
                min="2"
                max="50"
                step="0.5"
                .value=${String(sysCfg?.ble_max_radius_m ?? 12)}
                @change=${(ev: Event) => {
                  const val = Number((ev.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(val)) {
                    store.stageSystemSetting("ble_max_radius_m", val, "sys-ble_max_radius_m");
                  }
                }}
              />`,
            })}
            ${renderSettingsRow({
              forId: "sys-ble_max_velocity_mps",
              label: "Maximum Movement Speed",
              description:
                "Damps sudden signal drops that imply movement faster than this speed in meters per second.",
              control: html`<input
                type="number"
                id="sys-ble_max_velocity_mps"
                min="0.5"
                max="15"
                step="0.5"
                .value=${String(sysCfg?.ble_max_velocity_mps ?? 3.5)}
                @change=${(ev: Event) => {
                  const val = Number((ev.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(val)) {
                    store.stageSystemSetting("ble_max_velocity_mps", val, "sys-ble_max_velocity_mps");
                  }
                }}
              />`,
            })}
            ${renderSettingsRow({
              forId: "sys-ble_away_timeout_s",
              label: "Away Timeout",
              description:
                "Seconds without any Bluetooth packet before a tracked Tag or offline Device is marked Away.",
              control: html`<input
                type="number"
                id="sys-ble_away_timeout_s"
                min="30"
                max="900"
                step="15"
                .value=${String(sysCfg?.ble_away_timeout_s ?? 180)}
                @change=${(ev: Event) => {
                  const val = Number((ev.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(val)) {
                    store.stageSystemSetting("ble_away_timeout_s", Math.round(val), "sys-ble_away_timeout_s");
                  }
                }}
              />`,
            })}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-ble-scanner-calibration",
          title: "Per-Scanner BLE Calibration",
          subtitle:
            "Streams live per-scanner RSSI deltas over WebSocket to normalize receiver hardware offsets.",
          headerActions: html`<select
              id="ble-survey-device-picker"
              aria-label="Select Device for BLE calibration"
              .value=${activeSurveyDev?.subentry_id || ""}
              @change=${(ev: Event) =>
                store.selectBleSurveyDevice((ev.currentTarget as HTMLSelectElement).value)}
            >
              ${bleDevs.length
                ? bleDevs.map(
                    (d) =>
                      html`<option
                        value=${d.subentry_id}
                        ?selected=${d.subentry_id === activeSurveyDev?.subentry_id}
                      >
                        ${d.title} (${d.active_area_name || "—"})
                      </option>`,
                  )
                : html`<option value="">No Bluetooth devices found</option>`}
            </select>
            <button
              type="button"
              aria-pressed=${String(store.bleLiveStreamActive)}
              @click=${() => store.toggleBleLiveStream(!store.bleLiveStreamActive)}
              class="btn ${store.bleLiveStreamActive ? "btn-primary" : "btn-secondary"} btn-compact"
            >
              ${store.bleLiveStreamActive ? "Live Stream On" : "Stream Paused"}
            </button>`,
          contentClass: "stack",
          body: html`<p class="help-text">
              Packets observed: <strong>${fmtNumber(packetsSeen, store.hass, 0)}</strong>
            </p>
            ${surveyRows.length
              ? repeat(
                  surveyRows,
                  (row) => row.scanner_source || row.area_id,
                  (row) => {
                    const scannerSrc = row.scanner_source || "";
                    const scannerLabel = row.scanner_name || scannerSrc || row.area_name || "Scanner";
                    const areaLabel = row.area_name || "Unmapped";
                    const pct = rssiToPercent(row.effective_rssi);
                    const sigStyle = `--signal-pct:${pct}%`;
                    const offVal = Number(row.offset_db || 0);
                    const offTxt = `${offVal >= 0 ? "+" : ""}${fmtNumber(offVal, store.hass, 1)} dB`;

                    const metaParts: string[] = [];
                    if (row.raw_rssi !== null && row.raw_rssi !== undefined) {
                      metaParts.push(`raw ${fmtNumber(row.raw_rssi, store.hass, 0)} dBm`);
                    } else {
                      metaParts.push("no signal");
                    }
                    if (row.filtered_rssi !== null && row.filtered_rssi !== undefined) {
                      metaParts.push(`filtered ${fmtNumber(row.filtered_rssi, store.hass, 1)} dBm`);
                    }
                    metaParts.push(`offset ${offTxt}`);
                    const effTxt =
                      row.effective_rssi !== null && row.effective_rssi !== undefined
                        ? `${fmtNumber(row.effective_rssi, store.hass, 0)} dBm`
                        : "—";
                    metaParts.push(`eff ${effTxt}`);
                    if (row.distance_m !== null && row.distance_m !== undefined) {
                      metaParts.push(`~${fmtDistance(row.distance_m, store.hass, row.distance_ft)}`);
                    }
                    if (row.age_seconds !== null && row.age_seconds !== undefined) {
                      metaParts.push(
                        `${fmtAgo(row.age_seconds, store.hass)}${row.is_fresh === false ? " (stale)" : ""}`,
                      );
                    }

                    return html`<div class="signal-row ${row.is_winner ? "winner" : ""}">
                      <div class="signal-row-head">
                        <span class="signal-row-title">
                          <span class="row-label">${scannerLabel}</span>
                          <span class="chip">${areaLabel}</span>
                          ${row.is_winner
                            ? html`<span class="chip chip-primary">Active Winner</span>`
                            : nothing}
                        </span>
                        <span class="signal-meta">${metaParts.join(" • ")}</span>
                      </div>
                      <div class="signal-track">
                        <div class="signal-fill" style=${sigStyle}></div>
                      </div>
                      <div class="input-action-row">
                        <button
                          type="button"
                          ?disabled=${!scannerSrc}
                          @click=${() => void store.setBleScannerOffset(scannerSrc, offVal - 1)}
                          class="btn btn-secondary btn-compact"
                        >
                          -1 dB
                        </button>
                        <button
                          type="button"
                          ?disabled=${!scannerSrc}
                          @click=${() => void store.setBleScannerOffset(scannerSrc, offVal + 1)}
                          class="btn btn-secondary btn-compact"
                        >
                          +1 dB
                        </button>
                        <button
                          type="button"
                          ?disabled=${!scannerSrc}
                          @click=${() => void store.setBleScannerOffset(scannerSrc, 0)}
                          class="btn btn-text btn-compact"
                        >
                          Reset
                        </button>
                      </div>
                    </div>`;
                  },
                )
              : html`<p class="empty-state">
                  No Bluetooth scanner readings yet for this Device.
                </p>`}`,
        })}

        ${renderCard({
          id: "card-ble-area-signatures",
          title: "Multi-Scanner Area Signatures",
          subtitle:
            "Captures full multi-proxy signal vectors for surgical boundary accuracy and proxy-less Areas.",
          contentClass: "settings-list",
          body: html`${signatures.length
            ? repeat(
                signatures,
                (sig) => sig.area_id,
                (sig) => {
                  const descParts: string[] = [];
                  if (sig.has_signature) {
                    descParts.push(`${fmtNumber(sig.sample_count, store.hass, 0)} samples`);
                    if (sig.captured_at) {
                      descParts.push(`captured ${fmtDateTime(sig.captured_at, store.hass)}`);
                    }
                  } else if (!sig.has_ble_proxy) {
                    descParts.push(
                      "Capture a multi-scanner signature to detect presence in this Area without a local Bluetooth proxy.",
                    );
                  } else {
                    descParts.push(
                      "Uses path-loss distance from the local Bluetooth proxy until a signature is captured.",
                    );
                  }
                  if (sig.floor_id) {
                    descParts.push(`Floor: ${sig.floor_id}`);
                  }

                  return renderSettingsRow({
                    labelHtml: html`<span class="row-label">
                      ${sig.area_name}
                      ${sig.has_signature
                        ? html`<span class="chip chip-success">
                            Signature (${fmtNumber(sig.scanner_count, store.hass, 0)} Scanners)
                          </span>`
                        : html`<span class="chip">Distance Model</span>`}
                      ${!sig.has_ble_proxy
                        ? html`<span class="chip">No Local Proxy</span>`
                        : nothing}
                    </span>`,
                    description: descParts.join(" • "),
                    control: html`<button
                        type="button"
                        ?disabled=${!activeSurveyDev}
                        @click=${() => void store.captureBleAreaSignature(sig.area_id)}
                        class="btn btn-secondary btn-compact"
                      >
                        Capture Signature
                      </button>
                      ${sig.has_signature
                        ? html`<button
                            type="button"
                            @click=${() => void store.clearBleAreaSignature(sig.area_id)}
                            class="btn btn-text btn-compact"
                          >
                            Clear
                          </button>`
                        : nothing}`,
                  });
                },
              )
            : html`<p class="empty-state">
                No Home Assistant Areas configured yet.
              </p>`}`,
        })}
      </div>
    </div>
  </section>`;
}
