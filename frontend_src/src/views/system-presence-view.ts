/**
 * System BLE & Area Presence View (`area_tracking`): Live Area Presence & Sensor Fusion, Streaming BLE Calibration & Discovered BLE Devices.
 */

import { renderCard, renderSettingsRow } from "../components/controls.js";
import { html, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { fmtDistance, fmtNumber, fmtPercent, rssiToPercent } from "../utils/format.js";

const FUSION_MODE_OPTIONS: ReadonlyArray<{ val: string; label: string }> = [
  { val: "weighted", label: "Weighted (BLE and sensors)" },
  { val: "any_or", label: "Either (BLE or a sensor)" },
  { val: "ble_only", label: "BLE only" },
  { val: "ble_and_sensor", label: "Both (BLE and a sensor)" },
];

export function renderSystemPresenceView(store: StudioStore): TemplateResult {
  const data = store.state;
  const presenceRows = data?.live?.area_presence_grid || [];
  const allDevs = data?.system_devices || [];
  const bleDevs = allDevs.filter((d) => d.has_ble || d.ble_tracked || d.kind === "ble_tag");
  const activeSurveyDev = store.getActiveSurveyDevice() || bleDevs[0];
  const surveyRows = activeSurveyDev?.ble_survey_rows || [];
  const packetsSeen = activeSurveyDev?.ble_packets_seen ?? 0;
  const candidates = data?.discovered_ble_devices || [];
  const persons = data?.catalog?.persons || [];

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
                    if (r.active_sensors && r.active_sensors.length) {
                      parts.push(
                        `${r.active_sensors.length} active sensor${r.active_sensors.length > 1 ? "s" : ""}`,
                      );
                    } else if (r.available_sensors && r.available_sensors.length) {
                      parts.push(
                        `${r.available_sensors.length} sensor${r.available_sensors.length > 1 ? "s" : ""} clear`,
                      );
                    }
                    if (r.floor_id) parts.push(`Floor: ${r.floor_id}`);

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
      </div>

      <div class="column">
        ${renderCard({
          title: "Per-Area BLE Signal Calibration",
          subtitle: "Streams live RSSI deltas over WebSocket to tune per-Area offsets.",
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
                  (row) => row.area_id,
                  (row) => {
                    const pct = rssiToPercent(row.effective_rssi);
                    const sigStyle = `--signal-pct:${pct}%`;
                    const effTxt =
                      row.effective_rssi !== null && row.effective_rssi !== undefined
                        ? `${fmtNumber(row.effective_rssi, store.hass, 1)} dBm`
                        : "—";
                    const rawTxt =
                      row.raw_rssi !== null && row.raw_rssi !== undefined
                        ? `raw ${fmtNumber(row.raw_rssi, store.hass, 1)} dBm`
                        : "no signal";
                    const offVal = Number(row.offset_db || 0);
                    const offTxt = `${offVal >= 0 ? "+" : ""}${fmtNumber(offVal, store.hass, 1)} dB`;

                    return html`<div class="signal-row ${row.is_winner ? "winner" : ""}">
                      <div class="signal-row-head">
                        <span class="signal-row-title">
                          <span class="row-label">${row.area_name}</span>
                          ${row.is_winner
                            ? html`<span class="chip chip-primary">Active Winner</span>`
                            : ""}
                        </span>
                        <span class="signal-meta">${rawTxt} • offset ${offTxt} • eff ${effTxt}</span>
                      </div>
                      <div class="signal-track">
                        <div class="signal-fill" style=${sigStyle}></div>
                      </div>
                      <div class="input-action-row">
                        <button
                          type="button"
                          @click=${() => void store.setBleOffset(row.area_id, offVal - 1)}
                          class="btn btn-secondary btn-compact"
                        >
                          -1 dB
                        </button>
                        <button
                          type="button"
                          @click=${() => void store.setBleOffset(row.area_id, offVal + 1)}
                          class="btn btn-secondary btn-compact"
                        >
                          +1 dB
                        </button>
                        <button
                          type="button"
                          @click=${() => void store.setBleOffset(row.area_id, 0)}
                          class="btn btn-text btn-compact"
                        >
                          Reset
                        </button>
                        <button
                          type="button"
                          @click=${() => void store.autoCalibrateHere(row.area_id)}
                          class="btn btn-primary btn-compact"
                        >
                          Calibrate Current Area
                        </button>
                      </div>
                    </div>`;
                  },
                )
              : html`<p class="empty-state">
                  No Area BLE proxy readings yet for this Device.
                </p>`}`,
        })}

        ${renderCard({
          title: "Discovered Bluetooth Devices",
          contentClass: "settings-list",
          body: html`<div id="ble-adopt-table-box" class="settings-list">
            ${candidates.length
              ? candidates.map((c, idx) => {
                  const title = c.title || c.name || c.target_address || c.address || "BLE Tag";
                  const addr = c.target_address || c.address || "";
                  const meta = [c.kind || "BLE device", addr];
                  if (c.rssi !== null && c.rssi !== undefined) {
                    meta.push(`${fmtNumber(c.rssi, store.hass, 0)} dBm`);
                  }
                  if (c.area_name) {
                    meta.push(`Nearest Area: ${c.area_name}`);
                  }
                  const selId = `ble-adopt-person-${idx}`;

                  return renderSettingsRow({
                    label: title,
                    description: meta.join(" • "),
                    control: html`<select id=${selId} aria-label=${`Assigned person for ${title}`}>
                        <option value="">No person</option>
                        ${persons.map((p) => html`<option value=${p.id}>${p.name}</option>`)}
                      </select>
                      <button
                        type="button"
                        @click=${(ev: Event) => {
                          const btn = ev.currentTarget as HTMLButtonElement;
                          const sel = btn.parentElement?.querySelector(
                            "select",
                          ) as HTMLSelectElement | null;
                          void store.quickAdoptBleCandidate(title, addr, sel?.value || "");
                        }}
                        class="btn btn-secondary btn-compact"
                      >
                        Adopt
                      </button>`,
                  });
                })
              : html`<p class="empty-state">No unadopted Bluetooth devices nearby.</p>`}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}
