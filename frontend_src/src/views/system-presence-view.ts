/**
 * System BLE & Area presence view (`area_tracking`, `D-044` / `D-045` / `D-046` / `D-058` / `D-064`):
 * Area presence & sensors, walk-around BLE calibration, and advanced BLE settings.
 */

import { renderCard, renderRangeRow, renderSettingsRow } from "../components/controls.js";
import { focusSafe, html, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { AreaPresenceRow, BleAreaSignatureSummary } from "../types.js";
import {
  fmtAgo,
  fmtDateTime,
  fmtDistance,
  fmtNumber,
  fmtPercent,
  rssiToPercent,
} from "../utils/format.js";

export function renderSystemPresenceView(store: StudioStore): TemplateResult {
  const data = store.state;
  const sysCfg = data?.system_config;
  const presenceRows = data?.live?.area_presence_grid || [];
  const signatures = data?.ble_area_signatures || [];
  const allDevs = data?.system_devices || [];
  const bleDevs = allDevs.filter((d) => d.ble_tracked || d.kind === "ble_tag");
  const activeSurveyDev = store.groups.getActiveSurveyDevice() || bleDevs[0];
  const surveyRows = activeSurveyDev?.ble_survey_rows || [];
  const packetsSeen = activeSurveyDev?.ble_packets_seen ?? 0;

  const fusionModeOptions: ReadonlyArray<{ val: string; label: string }> = [
    { val: "weighted", label: store.t("presence_sys.mode_weighted") },
    { val: "any_or", label: store.t("presence_sys.mode_any_or") },
    { val: "ble_only", label: store.t("presence_sys.mode_ble_only") },
    { val: "ble_and_sensor", label: store.t("presence_sys.mode_both") },
  ];

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
    store.t("presence_sys.this_area");

  const calibrateDescription = !areaChoices.length
    ? store.t("presence_sys.cal_desc_no_areas")
    : selectedSig?.has_signature
      ? store.t("presence_sys.cal_desc_replace", {
          count: fmtNumber(selectedSig.scanner_count, store.hass, 0),
          area: selectedAreaName,
        })
      : selectedSig && !selectedSig.has_ble_proxy
        ? store.t("presence_sys.cal_desc_proxyless", { area: selectedAreaName })
        : store.t("presence_sys.cal_desc_new", { area: selectedAreaName });

  const hasFreshSignal = surveyRows.some(
    (r) => Boolean(r.is_fresh) && r.effective_rssi !== null && r.effective_rssi !== undefined,
  );

  const hasAnyLuxSensor = unifiedAreas.some(
    ({ row }) => (row?.illuminance_sensor_choices?.length || 0) > 0,
  );

  return html`<section id="view-area_tracking">
    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-area-presence",
          title: store.t("card.area_presence_sensors"),
          subtitle: store.t("presence_sys.area_card_subtitle"),
          headerActions: hasAnyLuxSensor
            ? html`<button
                type="button"
                class="btn btn-secondary btn-compact"
                @click=${() => void store.groups.calibrateAreaIlluminance()}
              >
                ${store.t("presence_sys.calibrate_all_lux")}
              </button>`
            : nothing,
          body: html`<div id="area-presence-grid-box" class="stack">
            ${unifiedAreas.length
              ? repeat(
                  unifiedAreas,
                  (item) => item.areaId,
                  ({ areaId, areaName, row, sig }) => {
                    const isOcc = Boolean(row?.is_occupied);
                    const hasConf =
                      row?.confidence_pct !== null &&
                      row?.confidence_pct !== undefined &&
                      Number.isFinite(Number(row.confidence_pct));
                    const confStr = hasConf
                      ? fmtPercent(Number(row?.confidence_pct), store.hass)
                      : store.t("common.unknown");
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
                        ? store.t("presence_sys.occupied_sensor")
                        : store.t("presence_sys.empty");
                    const parts: string[] = [occNames];
                    if (row?.winning_rssi !== null && row?.winning_rssi !== undefined) {
                      const distPart =
                        row.closest_distance_m !== null && row.closest_distance_m !== undefined
                          ? ` (~${fmtDistance(row.closest_distance_m, store.hass, row.closest_distance_ft)})`
                          : "";
                      parts.push(
                        store.t("presence_sys.ble_dbm", {
                          rssi: fmtNumber(row.winning_rssi, store.hass, 0),
                          distance: distPart,
                        }),
                      );
                    }
                    if (row?.match_method === "signature") {
                      parts.push(store.t("presence_sys.signature_match"));
                    }
                    if (row?.active_sensors && row.active_sensors.length) {
                      parts.push(
                        row.active_sensors.length === 1
                          ? store.t("presence_sys.active_sensors_one")
                          : store.t("presence_sys.active_sensors_many", {
                              count: row.active_sensors.length,
                            }),
                      );
                    } else if (row?.available_sensors && row.available_sensors.length) {
                      parts.push(
                        row.available_sensors.length === 1
                          ? store.t("presence_sys.clear_sensors_one")
                          : store.t("presence_sys.clear_sensors_many", {
                              count: row.available_sensors.length,
                            }),
                      );
                    }
                    if (sig?.has_signature && sig.captured_at) {
                      parts.push(
                        store.t("presence_sys.calibrated_meta", {
                          when: fmtDateTime(sig.captured_at, store.hass),
                          samples: fmtNumber(sig.sample_count, store.hass, 0),
                        }),
                      );
                    } else if (!hasBleProxy && !sig?.has_signature) {
                      parts.push(store.t("presence_sys.calibrate_hint"));
                    }

                    const curMode = row?.fusion_mode || "weighted";
                    const threshold = Number(row?.fusion_threshold_pct ?? 50);
                    const chosen = row?.fusion_sensors || [];
                    const choices = row?.fusion_sensor_choices || [];
                    const luxChoices = row?.illuminance_sensor_choices || [];
                    const luxEntity = String(row?.illuminance_entity || "auto");
                    const luxResolvedName = String(
                      row?.illuminance_resolved_name || row?.illuminance_resolved_entity || "",
                    );
                    const luxDisplay = String(row?.illuminance_lux_display || "");
                    const luxAmbPct =
                      row?.illuminance_ambient_pct !== null &&
                      row?.illuminance_ambient_pct !== undefined
                        ? Number(row.illuminance_ambient_pct)
                        : null;
                    const luxDark = Number(row?.illuminance_dark_lux ?? 0.5);
                    const luxBright = Number(row?.illuminance_bright_lux ?? 40);
                    const thresholdId = `fusion-threshold-${areaId}`;
                    const areaBoxId = `area-box-${areaId}`;
                    const isAreaHandoff = store.isHandoffTarget(areaBoxId);

                    return html`<div id=${areaBoxId} class="area-presence-box${isAreaHandoff ? " handoff-active" : ""}">
                      <div class="area-box-head">
                        <h4 class="area-box-title">${areaName}</h4>
                        <div class="area-box-actions">
                          ${sig?.has_signature
                            ? html`<button
                                type="button"
                                @click=${() =>
                                  store.groups.requestClearBleAreaSignature(areaId, areaName)}
                                class="btn btn-text btn-compact"
                              >
                                ${store.t("presence_sys.clear_signature")}
                              </button>`
                            : nothing}
                          ${bleDevs.length > 0
                            ? html`<button
                                type="button"
                                @click=${() => store.groups.selectBleCalibrateArea(areaId, true)}
                                class="btn btn-secondary btn-compact"
                              >
                                ${store.t("presence_sys.calibrate")}
                              </button>`
                            : nothing}
                        </div>
                      </div>

                      <div class="area-box-badges">
                        ${isOcc
                          ? html`<span class="chip chip-success">${store.t("presence_sys.occupied_chip", { confidence: confStr })}</span>`
                          : html`<span class="chip">${store.t("presence_sys.clear_chip")}</span>`}
                        ${floorLabel ? html`<span class="chip">${floorLabel}</span>` : nothing}
                        ${sig?.has_signature
                          ? html`<span class="chip chip-primary">${sig.scanner_count === 1
                              ? store.t("presence_sys.signature_proxies_one")
                              : store.t("presence_sys.signature_proxies_many", {
                                  count: fmtNumber(sig.scanner_count, store.hass, 0),
                                })}</span>`
                          : hasBleProxy
                            ? html`<span class="chip">${store.t("sys_overview.ble_proxy")}</span>`
                            : html`<span class="chip chip-warning">${store.t("sys_overview.no_ble_proxy")}</span>`}
                        ${luxDisplay && luxAmbPct !== null && Number.isFinite(luxAmbPct)
                          ? html`<span class="chip"
                              >${store.t("presence_sys.lux_chip", {
                                lux: luxDisplay,
                                level: fmtNumber(luxAmbPct, store.hass, 0),
                              })}</span
                            >`
                          : nothing}
                      </div>

                      <div class="area-box-meta">${parts.join(" • ")}</div>

                      ${renderSettingsRow({
                        label: store.t("presence_sys.presence_mode"),
                        control: html`<select
                          aria-label=${store.t("presence_sys.presence_mode_aria", { area: areaName })}
                          .value=${curMode}
                          @change=${(ev: Event) =>
                            void store.groups.setAreaFusion(areaId, {
                              mode: (ev.currentTarget as HTMLSelectElement).value,
                            })}
                        >
                          ${fusionModeOptions.map(
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
                        <summary>${store.t("presence_sys.sensor_threshold_drawer")}</summary>
                        <div class="card-content settings-list">
                          ${renderRangeRow({
                            id: thresholdId,
                            label: store.t("presence_sys.occupied_at"),
                            ariaLabel: store.t("presence_sys.occupied_at"),
                            description:
                              curMode === "weighted"
                                ? store.t("presence_sys.occupied_at_weighted_desc")
                                : store.t("presence_sys.occupied_at_other_desc"),
                            value: threshold,
                            min: 20,
                            max: 95,
                            step: 5,
                            unit: "%",
                            disabled: curMode !== "weighted",
                            hass: store.hass,
                            onCommit: (nextVal) =>
                              void store.groups.setAreaFusion(areaId, {
                                threshold_pct: nextVal,
                              }),
                          })}
                          ${renderSettingsRow({
                            label: store.t("presence_sys.sensors_that_count"),
                            description: chosen.length
                              ? store.t("presence_sys.sensors_selected_desc", {
                                  selected: chosen.length,
                                  total: choices.length,
                                })
                              : store.t("presence_sys.sensors_all_desc"),
                            stacked: true,
                            control: choices.length
                              ? html`<div
                                  role="group"
                                  aria-label=${store.t("presence_sys.sensors_group_aria", {
                                    area: areaName,
                                  })}
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
                                          void store.groups.setAreaFusion(areaId, {
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
                                  ${store.t("presence_sys.no_area_sensors")}
                                </p>`,
                          })}
                          ${luxChoices.length > 0 || luxEntity !== "auto"
                            ? html`${renderSettingsRow({
                                  label: store.t("presence_sys.ambient_sensor"),
                                  control: html`<select
                                    aria-label=${store.t("presence_sys.ambient_sensor_aria", {
                                      area: areaName,
                                    })}
                                    .value=${luxEntity}
                                    @change=${(ev: Event) =>
                                      void store.groups.setAreaIlluminance(areaId, {
                                        entity_id: (ev.currentTarget as HTMLSelectElement).value,
                                      })}
                                  >
                                    <option value="auto" ?selected=${luxEntity === "auto"}>
                                      ${luxResolvedName && luxEntity === "auto"
                                        ? store.t("presence_sys.ambient_sensor_auto", {
                                            sensor: luxResolvedName,
                                          })
                                        : store.t("presence_sys.ambient_sensor_auto_none")}
                                    </option>
                                    ${luxChoices.map(
                                      (s) =>
                                        html`<option
                                          value=${s.entity_id}
                                          ?selected=${luxEntity === s.entity_id}
                                        >
                                          ${s.name}${s.lux_display ? ` (${s.lux_display} lx)` : ""}
                                        </option>`,
                                    )}
                                    <option value="disabled" ?selected=${luxEntity === "disabled"}>
                                      ${store.t("presence_sys.ambient_sensor_disabled")}
                                    </option>
                                  </select>`,
                                })}
                                ${luxEntity !== "disabled"
                                  ? renderSettingsRow({
                                      label: store.t("presence_sys.calibrate_lux_btn"),
                                      description: store.t("presence_sys.ambient_calibration_desc"),
                                      stacked: true,
                                      control: html`<div class="lux-bounds-row">
                                        <label class="lux-bound-field">
                                          <span>${store.t("presence_sys.ambient_dark_lux")}</span>
                                          <input
                                            type="number"
                                            class="lux-number-input"
                                            min="0"
                                            max="500"
                                            step="0.1"
                                            aria-label=${`${store.t("presence_sys.ambient_dark_lux")} (${areaName})`}
                                            .value=${String(luxDark)}
                                            @change=${(ev: Event) => {
                                              const v = Number(
                                                (ev.currentTarget as HTMLInputElement).value,
                                              );
                                              if (Number.isFinite(v)) {
                                                void store.groups.setAreaIlluminance(areaId, {
                                                  dark_lux: v,
                                                });
                                              }
                                            }}
                                          />
                                        </label>
                                        <label class="lux-bound-field">
                                          <span>${store.t("presence_sys.ambient_bright_lux")}</span>
                                          <input
                                            type="number"
                                            class="lux-number-input"
                                            min="1"
                                            max="100000"
                                            step="1"
                                            aria-label=${`${store.t("presence_sys.ambient_bright_lux")} (${areaName})`}
                                            .value=${String(luxBright)}
                                            @change=${(ev: Event) => {
                                              const v = Number(
                                                (ev.currentTarget as HTMLInputElement).value,
                                              );
                                              if (Number.isFinite(v)) {
                                                void store.groups.setAreaIlluminance(areaId, {
                                                  bright_lux: v,
                                                });
                                              }
                                            }}
                                          />
                                        </label>
                                        <button
                                          type="button"
                                          class="btn btn-secondary btn-compact"
                                          @click=${() =>
                                            void store.groups.calibrateAreaIlluminance(areaId)}
                                        >
                                          ${store.t("presence_sys.calibrate_lux_btn")}
                                        </button>
                                      </div>`,
                                    })
                                  : nothing}`
                            : nothing}
                        </div>
                      </details>
                    </div>`;
                  },
                )
              : html`<p class="empty-state">
                  ${store.t("presence_sys.empty_areas")}
                </p>`}
          </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-ble-calibration",
          title: store.t("card.ble_calibration"),
          subtitle: store.t("presence_sys.calibration_subtitle"),
          headerActions:
            bleDevs.length > 0
              ? html`<button
                  type="button"
                  id="btn-toggle-ble-stream"
                  @click=${() => store.groups.toggleBleLiveStream(!store.bleLiveStreamActive)}
                  class="btn btn-secondary btn-compact"
                >
                  ${store.bleLiveStreamActive
                    ? store.t("presence_sys.pause_stream")
                    : store.t("presence_sys.resume_stream")}
                </button>`
              : nothing,
          footerActions:
            bleDevs.length === 0
              ? html`<button
                  type="button"
                  @click=${() => store.openDiscoveredDevices("card-discovered-ble")}
                  class="btn btn-secondary"
                >
                  ${store.t("presence_sys.open_discovered")}
                </button>`
              : nothing,
          contentClass: "stack",
          body:
            bleDevs.length === 0
              ? html`<p class="empty-state">
                  ${store.t("presence_sys.empty_ble_devices")}
                </p>`
              : html`<div
                    id="ble-calibrate-target-box"
                    class="calibrate-target-box${store.bleCalibrateHandoffActive ? " handoff-active" : ""}"
                  >
                    ${store.bleCalibrateHandoffActive
                      ? html`<div id="ble-calibrate-handoff-banner" class="calibrate-handoff-banner">
                          <span>${store.t("presence_sys.handoff_ready", {
                            area: selectedAreaName,
                            device:
                              activeSurveyDev?.title || store.t("presence_sys.your_device"),
                          })}</span>
                          <button
                            type="button"
                            @click=${() => {
                              store.bleCalibrateHandoffActive = false;
                              store.host.requestUpdate();
                            }}
                            class="btn btn-text btn-compact"
                          >
                            ${store.t("action.dismiss")}
                          </button>
                        </div>`
                      : nothing}

                    ${renderSettingsRow({
                      forId: "ble-survey-device-picker",
                      label: store.t("presence_sys.carried_device"),
                      description: store.t("presence_sys.carried_device_desc"),
                      control: html`<select
                        id="ble-survey-device-picker"
                        .value=${activeSurveyDev?.subentry_id || ""}
                        @change=${(ev: Event) =>
                          store.groups.selectBleSurveyDevice(
                            (ev.currentTarget as HTMLSelectElement).value,
                          )}
                      >
                        ${bleDevs.map(
                          (d) =>
                            html`<option
                              value=${d.subentry_id}
                              ?selected=${d.subentry_id === activeSurveyDev?.subentry_id}
                            >
                              ${d.title} (${d.active_area_name || store.t("common.unassigned")})
                            </option>`,
                        )}
                      </select>`,
                    })}

                    ${hasFreshSignal
                      ? html`<div class="alert">
                          <div class="alert-body">
                            <span>${store.t("presence_sys.live_signal_active")}<strong>${activeSurveyDev?.active_area_name || store.t("common.unassigned")}</strong>${store.t("presence_sys.packets_observed", {
                              count: fmtNumber(packetsSeen, store.hass, 0),
                            })}</span>
                          </div>
                        </div>`
                      : html`<div class="alert alert-warning">
                          <div class="alert-body">
                            <span>${store.t("presence_sys.no_recent_packets_prefix")}<strong>${activeSurveyDev?.title || store.t("presence_sys.this_device")}</strong>${store.t("presence_sys.no_recent_packets_suffix")}</span>
                          </div>
                        </div>`}

                    ${renderSettingsRow({
                      forId: "ble-calibrate-area-select",
                      label: store.t("presence_sys.standing_in_area"),
                      description: calibrateDescription,
                      stacked: true,
                      control: html`<div class="input-action-row">
                        <select
                          id="ble-calibrate-area-select"
                          .value=${targetAreaId}
                          @change=${(ev: Event) =>
                            store.groups.selectBleCalibrateArea(
                              (ev.currentTarget as HTMLSelectElement).value,
                            )}
                        >
                          ${areaChoices.length
                            ? areaChoices.map((a) => {
                                const aSig = sigByArea.get(a.area_id);
                                const suffix = aSig?.has_signature
                                  ? store.t("presence_sys.suffix_saved")
                                  : aSig && !aSig.has_ble_proxy
                                    ? store.t("presence_sys.suffix_no_proxy")
                                    : "";
                                return html`<option
                                  value=${a.area_id}
                                  ?selected=${a.area_id === targetAreaId}
                                >
                                  ${a.area_name}${suffix}
                                </option>`;
                              })
                            : html`<option value="">${store.t("presence_sys.no_ha_areas_option")}</option>`}
                        </select>
                        <button
                          id="btn-capture-area-signature"
                          type="button"
                          ?disabled=${!activeSurveyDev || !targetAreaId}
                          @click=${() =>
                            void store.groups.captureBleAreaSignature(targetAreaId)}
                          class="btn btn-primary"
                        >
                          ${store.t("presence_sys.calibrate_area_btn")}
                        </button>
                      </div>`,
                    })}
                  </div>

                  <div class="subsection-title">${store.t("presence_sys.nearby_proxies")}</div>
                  ${surveyRows.length
                    ? repeat(
                        surveyRows,
                        (row, idx) => `${row.area_id}::${row.scanner_source || idx}`,
                        (row) => {
                          const scannerSrc = row.scanner_source || "";
                          const areaTitle =
                            row.area_name || store.t("presence_sys.unassigned_proxy");
                          const scannerBadge =
                            row.scanner_name || scannerSrc || store.t("sys_overview.ble_proxy");
                          const pct = rssiToPercent(row.effective_rssi);
                          const sigStyle = `--signal-pct:${pct}%`;
                          const offVal = Number(row.offset_db || 0);
                          const offTxt = `${offVal >= 0 ? "+" : ""}${fmtNumber(offVal, store.hass, 1)} dB`;
                          const rawTxt =
                            row.raw_rssi !== null && row.raw_rssi !== undefined
                              ? `${fmtNumber(row.raw_rssi, store.hass, 0)} dBm`
                              : store.t("common.unknown");
                          const effTxt =
                            row.effective_rssi !== null && row.effective_rssi !== undefined
                              ? `${fmtNumber(row.effective_rssi, store.hass, 0)} dBm`
                              : store.t("signal.no_reading");
                          const distPart =
                            row.distance_m !== null && row.distance_m !== undefined
                              ? ` • ~${fmtDistance(row.distance_m, store.hass, row.distance_ft)}`
                              : "";
                          const agePart =
                            row.age_seconds !== null && row.age_seconds !== undefined
                              ? ` • ${fmtAgo(row.age_seconds, store.hass)}${row.is_fresh === false ? store.t("presence_sys.stale_suffix") : ""}`
                              : "";
                          const trimPart =
                            Math.abs(offVal) >= 0.1
                              ? store.t("presence_sys.trim_suffix", { offset: offTxt })
                              : "";
                          const metaText = `${effTxt}${distPart}${agePart}${trimPart}`;

                          return html`<div class="signal-row ${row.is_winner ? "winner" : ""}">
                            <div class="signal-row-head">
                              <span class="signal-row-title">
                                <span class="row-label">${areaTitle}</span>
                                <span class="chip">${scannerBadge}</span>
                                ${!row.area_name
                                  ? html`<span class="chip chip-warning">${store.t("presence_sys.assign_area_in_ha")}</span>`
                                  : nothing}
                                ${row.is_winner
                                  ? html`<span class="chip chip-primary">${store.t("presence_sys.active_winner")}</span>`
                                  : nothing}
                              </span>
                              <span class="signal-meta">${metaText}</span>
                            </div>
                            <div class="signal-track">
                              <div class="signal-fill" style=${sigStyle}></div>
                            </div>
                            ${scannerSrc
                              ? html`<details
                                  ?open=${store.openProxyTrims.has(scannerSrc)}
                                  @toggle=${(ev: Event) => {
                                    if ((ev.currentTarget as HTMLDetailsElement).open) {
                                      store.openProxyTrims.add(scannerSrc);
                                    } else {
                                      store.openProxyTrims.delete(scannerSrc);
                                    }
                                  }}
                                  class="sub-collapsible proxy-trim-details"
                                >
                                  <summary>${store.t("presence_sys.antenna_trim")}</summary>
                                  <div class="proxy-trim-body">
                                    <span class="help-text">${store.t("presence_sys.antenna_trim_help", {
                                      raw: rawTxt,
                                      offset: offTxt,
                                    })}</span>
                                    <div class="input-action-row">
                                      <button
                                        type="button"
                                        @click=${() =>
                                          void store.groups.setBleScannerOffset(
                                            scannerSrc,
                                            offVal - 1,
                                          )}
                                        class="btn btn-secondary btn-compact"
                                      >
                                        ${store.t("presence_sys.minus_one_db")}
                                      </button>
                                      <button
                                        type="button"
                                        @click=${() =>
                                          void store.groups.setBleScannerOffset(
                                            scannerSrc,
                                            offVal + 1,
                                          )}
                                        class="btn btn-secondary btn-compact"
                                      >
                                        ${store.t("presence_sys.plus_one_db")}
                                      </button>
                                      <button
                                        type="button"
                                        @click=${() =>
                                          void store.groups.setBleScannerOffset(scannerSrc, 0)}
                                        class="btn btn-text btn-compact"
                                      >
                                        ${store.t("action.reset")}
                                      </button>
                                    </div>
                                  </div>
                                </details>`
                              : nothing}
                          </div>`;
                        },
                      )
                    : html`<p class="empty-state">
                        ${store.t("presence_sys.empty_survey")}
                      </p>`}`,
        })}

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
              <h3 class="card-title">${store.t("card.advanced_ble")}</h3>
              <p class="card-subtitle">
                ${store.t("presence_sys.advanced_subtitle")}
              </p>
            </div>
          </summary>
          <div class="card-content settings-list">
            ${renderSettingsRow({
              forId: "sys-ble_away_timeout_s",
              label: store.t("presence_sys.away_timeout"),
              description: store.t("presence_sys.away_timeout_desc"),
              control: html`<input
                type="number"
                id="sys-ble_away_timeout_s"
                min="30"
                max="900"
                step="15"
                .value=${focusSafe(String(sysCfg?.ble_away_timeout_s ?? 180))}
                @change=${(ev: Event) => {
                  const val = Number((ev.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(val)) {
                    store.entity.stageSystemSetting(
                      "ble_away_timeout_s",
                      Math.round(val),
                      "sys-ble_away_timeout_s",
                    );
                  }
                }}
              />`,
            })}
            ${renderSettingsRow({
              forId: "sys-ble_max_radius_m",
              label: store.t("presence_sys.max_radius"),
              description: store.t("presence_sys.max_radius_desc"),
              control: html`<input
                type="number"
                id="sys-ble_max_radius_m"
                min="2"
                max="50"
                step="0.5"
                .value=${focusSafe(String(sysCfg?.ble_max_radius_m ?? 12))}
                @change=${(ev: Event) => {
                  const val = Number((ev.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(val)) {
                    store.entity.stageSystemSetting(
                      "ble_max_radius_m",
                      val,
                      "sys-ble_max_radius_m",
                    );
                  }
                }}
              />`,
            })}
            ${renderSettingsRow({
              forId: "sys-ble_max_velocity_mps",
              label: store.t("presence_sys.max_speed"),
              description: store.t("presence_sys.max_speed_desc"),
              control: html`<input
                type="number"
                id="sys-ble_max_velocity_mps"
                min="0.5"
                max="15"
                step="0.5"
                .value=${focusSafe(String(sysCfg?.ble_max_velocity_mps ?? 3.5))}
                @change=${(ev: Event) => {
                  const val = Number((ev.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(val)) {
                    store.entity.stageSystemSetting(
                      "ble_max_velocity_mps",
                      val,
                      "sys-ble_max_velocity_mps",
                    );
                  }
                }}
              />`,
            })}
            ${renderSettingsRow({
              forId: "sys-ble_attenuation",
              label: store.t("presence_sys.attenuation"),
              description: store.t("presence_sys.attenuation_desc"),
              control: html`<input
                type="number"
                id="sys-ble_attenuation"
                min="1.5"
                max="4.5"
                step="0.1"
                .value=${focusSafe(String(sysCfg?.ble_attenuation ?? 2.2))}
                @change=${(ev: Event) => {
                  const val = Number((ev.currentTarget as HTMLInputElement).value);
                  if (Number.isFinite(val)) {
                    store.entity.stageSystemSetting(
                      "ble_attenuation",
                      val,
                      "sys-ble_attenuation",
                    );
                  }
                }}
              />`,
            })}
          </div>
        </details>
      </div>
    </div>
  </section>`;
}
