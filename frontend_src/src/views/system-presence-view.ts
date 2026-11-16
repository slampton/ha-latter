/**
 * System BLE & Area Presence View (`area_tracking`, `D-044`):
 * Area Presence & Sensors, Walk-Around BLE Calibration, and Advanced BLE Settings.
 */

import { renderCard, renderSettingsRow } from "../components/controls.js";
import { html, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { AreaPresenceRow, BleAreaSignatureSummary } from "../types.js";
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
  const bleDevs = allDevs.filter((d) => d.ble_tracked || d.kind === "ble_tag");
  const activeSurveyDev = store.getActiveSurveyDevice() || bleDevs[0];
  const surveyRows = activeSurveyDev?.ble_survey_rows || [];
  const trimRows = surveyRows.filter((r) => Boolean(r.scanner_source));
  const packetsSeen = activeSurveyDev?.ble_packets_seen ?? 0;

  const sigByArea = new Map<string, BleAreaSignatureSummary>();
  for (const sig of signatures) {
    if (sig.area_id) sigByArea.set(sig.area_id, sig);
  }
  const rowByArea = new Map<string, AreaPresenceRow>();
  for (const row of presenceRows) {
    if (row.area_id) rowByArea.set(row.area_id, row);
  }

  const unifiedAreas: Array<{
    areaId: string;
    areaName: string;
    row?: AreaPresenceRow;
    sig?: BleAreaSignatureSummary;
  }> = [];
  for (const row of presenceRows) {
    unifiedAreas.push({
      areaId: row.area_id,
      areaName: row.area_name,
      row,
      sig: sigByArea.get(row.area_id),
    });
  }
  for (const sig of signatures) {
    if (!rowByArea.has(sig.area_id)) {
      unifiedAreas.push({
        areaId: sig.area_id,
        areaName: sig.area_name,
        row: undefined,
        sig,
      });
    }
  }
  unifiedAreas.sort((a, b) =>
    a.areaName.localeCompare(b.areaName, undefined, { sensitivity: "base" }),
  );

  const areaChoices: Array<{ area_id: string; area_name: string }> = signatures.length
    ? signatures.map((s) => ({ area_id: s.area_id, area_name: s.area_name }))
    : (data?.catalog?.areas || []).map((a) => ({ area_id: a.id, area_name: a.name }));

  const targetAreaId =
    store.bleCalibrateAreaId && areaChoices.some((a) => a.area_id === store.bleCalibrateAreaId)
      ? store.bleCalibrateAreaId
      : areaChoices[0]?.area_id || "";
  const selectedSig = sigByArea.get(targetAreaId);
  const selectedAreaName =
    selectedSig?.area_name ||
    areaChoices.find((a) => a.area_id === targetAreaId)?.area_name ||
    "this Area";
  const calibrateDescription = !areaChoices.length
    ? "Create at least one Home Assistant Area before capturing a Bluetooth signature."
    : selectedSig?.has_signature
      ? `Replaces the saved ${fmtNumber(selectedSig.scanner_count, store.hass, 0)}-proxy signature for ${selectedAreaName} using recent live Bluetooth readings.`
      : selectedSig && !selectedSig.has_ble_proxy
        ? `Captures readings from surrounding Bluetooth proxies so ${selectedAreaName} detects presence without a local proxy.`
        : `Captures a multi-proxy signal vector for ${selectedAreaName} to sharpen Area boundaries over single-proxy distance.`;

  const hasFreshSignal = surveyRows.some(
    (r) => Boolean(r.is_fresh) && r.effective_rssi !== null && r.effective_rssi !== undefined,
  );

  return html`<section id="view-area_tracking">
    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-area-presence",
          title: "Area Presence & Sensors",
          subtitle: "Configures how each Area combines Bluetooth tracking and occupancy sensors.",
          body: html`<div id="area-presence-grid-box" class="stack">
            ${unifiedAreas.length
              ? repeat(
                  unifiedAreas,
                  (item) => item.areaId,
                  ({ areaId, areaName, row, sig }) => {
                    const isOcc = Boolean(row?.is_occupied);
                    const confPct = row?.confidence_pct ?? 100;
                    const floorLabel = String(
                      row?.floor_name || row?.floor_id || sig?.floor_id || "",
                    ).trim();
                    const hasBleProxy = sig
                      ? Boolean(sig.has_ble_proxy)
                      : Boolean(
                          (row?.winning_rssi !== null && row?.winning_rssi !== undefined) ||
                            surveyRows.some((sr) => sr.area_id === areaId),
                        );

                    const occList = row?.occupant_names || [];
                    const occNames = occList.length
                      ? occList.join(", ")
                      : isOcc
                        ? "Occupied (sensor)"
                        : "Empty";
                    const parts: string[] = [occNames];
                    if (row?.winning_rssi !== null && row?.winning_rssi !== undefined) {
                      const distPart =
                        row.closest_distance_m !== null && row.closest_distance_m !== undefined
                          ? ` (~${fmtDistance(row.closest_distance_m, store.hass, row.closest_distance_ft)})`
                          : "";
                      parts.push(`BLE ${fmtNumber(row.winning_rssi, store.hass, 0)} dBm${distPart}`);
                    }
                    if (row?.match_method === "signature") {
                      parts.push("signature match");
                    }
                    if (row?.active_sensors && row.active_sensors.length) {
                      parts.push(
                        `${row.active_sensors.length} active sensor${row.active_sensors.length > 1 ? "s" : ""}`,
                      );
                    } else if (row?.available_sensors && row.available_sensors.length) {
                      parts.push(
                        `${row.available_sensors.length} sensor${row.available_sensors.length > 1 ? "s" : ""} clear`,
                      );
                    }
                    if (sig?.has_signature && sig.captured_at) {
                      parts.push(
                        `calibrated ${fmtDateTime(sig.captured_at, store.hass)} (${fmtNumber(sig.sample_count, store.hass, 0)} samples)`,
                      );
                    } else if (!hasBleProxy && !sig?.has_signature) {
                      parts.push("calibrate with a carried Device to detect BLE presence here");
                    }

                    const curMode = row?.fusion_mode || "weighted";
                    const threshold = Number(row?.fusion_threshold_pct ?? 50);
                    const chosen = row?.fusion_sensors || [];
                    const choices = row?.fusion_sensor_choices || [];
                    const thresholdId = `fusion-threshold-${areaId}`;

                    return html`<div class="area-presence-box${isOcc ? " occupied" : ""}">
                      <div class="area-box-head">
                        <div class="area-box-heading">
                          <span class="area-box-title">${areaName}</span>
                          ${isOcc
                            ? html`<span class="chip chip-success">Occupied • ${fmtPercent(confPct, store.hass)}</span>`
                            : html`<span class="chip">Clear</span>`}
                          ${floorLabel ? html`<span class="chip">${floorLabel}</span>` : nothing}
                          ${sig?.has_signature
                            ? html`<span class="chip chip-primary">Signature (${fmtNumber(sig.scanner_count, store.hass, 0)} ${sig.scanner_count === 1 ? "Proxy" : "Proxies"})</span>`
                            : hasBleProxy
                              ? html`<span class="chip">BLE Proxy</span>`
                              : html`<span class="chip chip-warning">No BLE Proxy</span>`}
                        </div>
                        <div class="area-box-actions">
                          ${bleDevs.length > 0
                            ? html`<button
                                type="button"
                                @click=${() => store.selectBleCalibrateArea(areaId, true)}
                                class="btn btn-secondary btn-compact"
                              >
                                Calibrate
                              </button>`
                            : nothing}
                          ${sig?.has_signature
                            ? html`<button
                                type="button"
                                @click=${() => void store.clearBleAreaSignature(areaId)}
                                class="btn btn-text btn-compact"
                              >
                                Clear Signature
                              </button>`
                            : nothing}
                        </div>
                      </div>

                      <div class="area-box-meta">${parts.join(" • ")}</div>

                      ${renderSettingsRow({
                        label: "Presence Mode",
                        control: html`<select
                          aria-label=${`Presence mode for ${areaName}`}
                          .value=${curMode}
                          @change=${(ev: Event) =>
                            void store.setAreaFusion(areaId, {
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
                        ?open=${store.openFusionAreas.has(areaId)}
                        @toggle=${(ev: Event) => {
                          const isOpen = (ev.currentTarget as HTMLDetailsElement).open;
                          if (isOpen) store.openFusionAreas.add(areaId);
                          else store.openFusionAreas.delete(areaId);
                        }}
                        class="sub-collapsible"
                      >
                        <summary>Sensor &amp; Threshold Settings</summary>
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
                                  void store.setAreaFusion(areaId, {
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
                                  aria-label=${`Sensors that count in ${areaName}`}
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
                                          void store.setAreaFusion(areaId, {
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
                  No Home Assistant Areas, Bluetooth proxies, or occupancy sensors found yet.
                </p>`}
          </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-ble-calibration",
          title: "Walk-Around BLE Calibration",
          subtitle:
            "Carry a tracked Device into an Area to verify proxy coverage or capture a multi-scanner signature.",
          headerActions:
            bleDevs.length > 0
              ? html`<button
                  type="button"
                  aria-pressed=${String(store.bleLiveStreamActive)}
                  @click=${() => store.toggleBleLiveStream(!store.bleLiveStreamActive)}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.bleLiveStreamActive ? "Live Stream On" : "Stream Paused"}
                </button>`
              : nothing,
          footerActions:
            bleDevs.length === 0
              ? html`<button
                  type="button"
                  @click=${() => store.openDiscoveredDevices()}
                  class="btn btn-secondary"
                >
                  Open Discovered Devices
                </button>`
              : nothing,
          contentClass: "stack",
          body:
            bleDevs.length === 0
              ? html`<p class="empty-state">
                  No Devices currently have Bluetooth Area tracking enabled. Enable Track the Area with BLE Proxies on a portable Device, or adopt a phone or tag under Discovered Devices.
                </p>`
              : html`${renderSettingsRow({
                  forId: "ble-survey-device-picker",
                  label: "Carried Device",
                  description: "Select the actively tracked Device or BLE Tag you are holding.",
                  control: html`<select
                    id="ble-survey-device-picker"
                    .value=${activeSurveyDev?.subentry_id || ""}
                    @change=${(ev: Event) =>
                      store.selectBleSurveyDevice((ev.currentTarget as HTMLSelectElement).value)}
                  >
                    ${bleDevs.map(
                      (d) =>
                        html`<option
                          value=${d.subentry_id}
                          ?selected=${d.subentry_id === activeSurveyDev?.subentry_id}
                        >
                          ${d.title} (${d.active_area_name || "Unassigned"})
                        </option>`,
                    )}
                  </select>`,
                })}

                ${hasFreshSignal
                  ? html`<div class="alert">
                      <div class="alert-body">
                        <span>Live BLE signal active — currently detected in <strong>${activeSurveyDev?.active_area_name || "Unassigned"}</strong> (${fmtNumber(packetsSeen, store.hass, 0)} packets observed).</span>
                      </div>
                    </div>`
                  : html`<div class="alert alert-warning">
                      <div class="alert-body">
                        <span>No live BLE packets in the last 12 seconds — wake <strong>${activeSurveyDev?.title || "this Device"}</strong> or hold it in hand so its Bluetooth beacon broadcasts before calibrating.</span>
                      </div>
                    </div>`}

                ${renderSettingsRow({
                  forId: "ble-calibrate-area-select",
                  label: "Standing In Area",
                  description: calibrateDescription,
                  stacked: true,
                  control: html`<div class="input-action-row">
                    <select
                      id="ble-calibrate-area-select"
                      .value=${targetAreaId}
                      @change=${(ev: Event) =>
                        store.selectBleCalibrateArea((ev.currentTarget as HTMLSelectElement).value)}
                    >
                      ${areaChoices.length
                        ? areaChoices.map((a) => {
                            const aSig = sigByArea.get(a.area_id);
                            const suffix = aSig?.has_signature
                              ? " (signature saved)"
                              : aSig && !aSig.has_ble_proxy
                                ? " (no BLE proxy)"
                                : "";
                            return html`<option
                              value=${a.area_id}
                              ?selected=${a.area_id === targetAreaId}
                            >
                              ${a.area_name}${suffix}
                            </option>`;
                          })
                        : html`<option value="">No Home Assistant Areas configured</option>`}
                    </select>
                    <button
                      id="btn-capture-area-signature"
                      type="button"
                      ?disabled=${!activeSurveyDev || !targetAreaId}
                      @click=${() => void store.captureBleAreaSignature(targetAreaId)}
                      class="btn btn-primary"
                    >
                      Calibrate Area
                    </button>
                  </div>`,
                })}

                <div class="subsection-title">Nearby Bluetooth Proxies</div>
                ${surveyRows.length
                  ? repeat(
                      surveyRows,
                      (row) => row.scanner_source || row.area_id,
                      (row) => {
                        const scannerSrc = row.scanner_source || "";
                        const areaTitle = row.area_name || "Unassigned Proxy";
                        const scannerBadge = row.scanner_name || scannerSrc || "BLE Proxy";
                        const pct = rssiToPercent(row.effective_rssi);
                        const sigStyle = `--signal-pct:${pct}%`;
                        const offVal = Number(row.offset_db || 0);
                        const offTxt = `${offVal >= 0 ? "+" : ""}${fmtNumber(offVal, store.hass, 1)} dB`;
                        const effTxt =
                          row.effective_rssi !== null && row.effective_rssi !== undefined
                            ? `${fmtNumber(row.effective_rssi, store.hass, 0)} dBm`
                            : "No signal";
                        const distPart =
                          row.distance_m !== null && row.distance_m !== undefined
                            ? ` • ~${fmtDistance(row.distance_m, store.hass, row.distance_ft)}`
                            : "";
                        const agePart =
                          row.age_seconds !== null && row.age_seconds !== undefined
                            ? ` • ${fmtAgo(row.age_seconds, store.hass)}${row.is_fresh === false ? " (stale)" : ""}`
                            : "";
                        const trimPart = Math.abs(offVal) >= 0.1 ? ` • trim ${offTxt}` : "";
                        const metaText = `${effTxt}${distPart}${agePart}${trimPart}`;

                        return html`<div class="signal-row ${row.is_winner ? "winner" : ""}">
                          <div class="signal-row-head">
                            <span class="signal-row-title">
                              <span class="row-label">${areaTitle}</span>
                              <span class="chip">${scannerBadge}</span>
                              ${!row.area_name
                                ? html`<span class="chip chip-warning">Assign Area in HA</span>`
                                : nothing}
                              ${row.is_winner
                                ? html`<span class="chip chip-primary">Active Winner</span>`
                                : nothing}
                            </span>
                            <span class="signal-meta">${metaText}</span>
                          </div>
                          <div class="signal-track">
                            <div class="signal-fill" style=${sigStyle}></div>
                          </div>
                        </div>`;
                      },
                    )
                  : html`<p class="empty-state">
                      No Bluetooth proxy readings yet for this Device.
                    </p>`}

                <details
                  id="ble-proxy-trim-drawer"
                  ?open=${store.proxyTrimOpen}
                  @toggle=${(ev: Event) => {
                    store.proxyTrimOpen = (ev.currentTarget as HTMLDetailsElement).open;
                  }}
                  class="sub-collapsible"
                >
                  <summary>Proxy Antenna Trim</summary>
                  <div class="card-content stack">
                    <p class="help-text">
                      Adjust receiver gain only if a specific Bluetooth proxy consistently reads louder or weaker than other proxies across every Area.
                    </p>
                    ${trimRows.length
                      ? html`<div class="settings-list">
                          ${repeat(
                            trimRows,
                            (row) => row.scanner_source || row.area_id,
                            (row) => {
                              const scannerSrc = row.scanner_source || "";
                              const offVal = Number(row.offset_db || 0);
                              const offTxt = `${offVal >= 0 ? "+" : ""}${fmtNumber(offVal, store.hass, 1)} dB`;
                              const rawTxt =
                                row.raw_rssi !== null && row.raw_rssi !== undefined
                                  ? `${fmtNumber(row.raw_rssi, store.hass, 0)} dBm`
                                  : "—";
                              return renderSettingsRow({
                                label: `${row.area_name || "Unassigned"} • ${row.scanner_name || scannerSrc}`,
                                description: `raw ${rawTxt} • offset ${offTxt}`,
                                control: html`<button
                                    type="button"
                                    ?disabled=${!scannerSrc}
                                    @click=${() =>
                                      void store.setBleScannerOffset(scannerSrc, offVal - 1)}
                                    class="btn btn-secondary btn-compact"
                                  >
                                    -1 dB
                                  </button>
                                  <button
                                    type="button"
                                    ?disabled=${!scannerSrc}
                                    @click=${() =>
                                      void store.setBleScannerOffset(scannerSrc, offVal + 1)}
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
                                  </button>`,
                              });
                            },
                          )}
                        </div>`
                      : html`<p class="empty-state">
                          No Bluetooth proxy sources observed yet for this Device.
                        </p>`}
                  </div>
                </details>`,
        })}
      </div>
    </div>

    <details
      id="card-advanced-ble-settings"
      ?open=${store.advancedBleOpen}
      @toggle=${(ev: Event) => {
        store.advancedBleOpen = (ev.currentTarget as HTMLDetailsElement).open;
      }}
      class="card"
    >
      <summary class="card-header">
        <div class="card-heading">
          <h3 class="card-title">Advanced BLE Settings</h3>
          <p class="card-subtitle">
            System-wide away timeout, maximum proxy radius, movement speed damping, and path-loss attenuation.
          </p>
        </div>
      </summary>
      <div class="card-content settings-list">
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
      </div>
    </details>
  </section>`;
}
