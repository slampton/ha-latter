/**
 * Device BLE & Area Presence View (`presence`, `D-003`, `D-032`, `D-036`, `D-066`):
 * Static Assigned Area vs. BLE Roaming, Fallback Area, and BLE identity (hidden when Static).
 */

import {
  renderCard,
  renderDeviceEntityRow,
  renderDeviceOfflineBanner,
  renderPrefControlRow,
  renderSelectRow,
  renderSwitchRow,
} from "../components/controls.js";
import { focusSafe, html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { fmtNumber } from "../utils/format.js";

export function renderDevicePresenceView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const isBleOnly = cfg.kind === "ble_tag";
  const bleTracking = isBleOnly || Boolean(cfg.native_ble_tracking);

  // Strict `D-003` unknown gating: never substitute a fake `-59 dBm` reading when unknown
  const rawDetectedRef = data?.live?.ble_detected_ref_power;
  const hasDetectedRefPower =
    rawDetectedRef !== null &&
    rawDetectedRef !== undefined &&
    Number.isFinite(Number(rawDetectedRef));
  const refPowerPlaceholder = hasDetectedRefPower
    ? store.t("dev_presence.ref_power_placeholder_detected", {
        dbm: fmtNumber(Number(rawDetectedRef), store.hass, 0),
      })
    : store.t("common.auto");

  const refPowerValue =
    cfg.ble_ref_power !== null && cfg.ble_ref_power !== undefined
      ? String(cfg.ble_ref_power)
      : "";
  const txStatus = isBleOnly ? data?.live?.ble_transmitter_status : null;
  const txPowerRaw = String(txStatus?.tx_power || "").trim();
  const advModeRaw = String(txStatus?.advertise_mode || "").trim();
  const txPowerNorm = txPowerRaw.toLowerCase().replace(/[^a-z]/g, "");
  const advModeNorm = advModeRaw.toLowerCase().replace(/[^a-z]/g, "");
  const showCompanionPowerTip =
    Boolean(txStatus) &&
    (txPowerNorm === "ultralow" || txPowerNorm === "low" || advModeNorm === "lowpower");

  const bleBeaconPref = store.entity.getPref("ble_beacon_mode");
  const bleAreaItems = store.entity
    .getSectionItems("area")
    .filter((it) => !it.pref_key && it.key !== "ble_beacon_mode");

  return html`<section id="view-presence">
    ${renderDeviceOfflineBanner(store)}

    <div class="columns">
      <div class="column">
        ${renderCard({
          title: store.t("dev_presence.card_area_tracking"),
          contentClass: "settings-list",
          body: html`${!isBleOnly
              ? renderSwitchRow({
                  id: "cfg-native_ble_tracking",
                  label: store.t("dev_presence.track_ble_label"),
                  description: store.t("dev_presence.track_ble_desc"),
                  checked: Boolean(cfg.native_ble_tracking),
                  onChange: (checked) =>
                    store.entity.stageDeviceSetting(
                      "native_ble_tracking",
                      checked,
                      "cfg-native_ble_tracking",
                    ),
                })
              : nothing}
            ${bleTracking
              ? html`${!isBleOnly
                    ? renderSwitchRow({
                        id: "cfg-ble_auto_switch",
                        label: store.tPrefLabel("ble_auto_switch"),
                        description: store.t("dev_presence.auto_switch_desc"),
                        checked: Boolean(cfg.ble_auto_switch),
                        onChange: (checked) =>
                          store.entity.stageDeviceSetting(
                            "ble_auto_switch",
                            checked,
                            "cfg-ble_auto_switch",
                          ),
                      })
                    : nothing}
                  ${renderSelectRow({
                    id: "cfg-default_area",
                    label: store.t("dev_presence.fallback_area_label"),
                    description: store.t("dev_presence.fallback_area_desc"),
                    value: cfg.default_area,
                    choices: data?.catalog?.areas,
                    emptyOptionLabel: store.t("dev_presence.fallback_area_auto"),
                    onChange: (val) =>
                      store.entity.stageDeviceSetting(
                        "default_area",
                        val,
                        "cfg-default_area",
                      ),
                  })}
                  ${bleBeaconPref ? renderPrefControlRow(store, bleBeaconPref) : nothing}
                  ${bleAreaItems.map((it) => renderDeviceEntityRow(store, it))}`
              : renderSelectRow({
                  id: "cfg-default_area",
                  label: store.t("dev_presence.assigned_area_label"),
                  description: store.t("dev_presence.assigned_area_desc"),
                  value: cfg.default_area,
                  choices: data?.catalog?.areas,
                  emptyOptionLabel: store.t("dev_overview.unassigned_option"),
                  onChange: (val) =>
                    store.entity.stageDeviceSetting("default_area", val, "cfg-default_area"),
                })}`,
        })}
      </div>

      <div class="column">
        ${bleTracking
          ? renderCard({
              id: "card-ble-identity",
              handoffActive: store.isHandoffTarget("card-ble-identity"),
              title: store.t("dev_presence.card_ble_identity"),
              contentClass: "stack",
              body: html`<div class="stacked-field">
                  <label for="cfg-ble_target_address">
                    ${store.t("dev_presence.target_addr_label")}
                  </label>
                  <input
                    type="text"
                    id="cfg-ble_target_address"
                    placeholder=${store.t("dev_presence.target_addr_placeholder")}
                    .value=${focusSafe(String(cfg.ble_target_address || ""))}
                    @change=${(ev: Event) =>
                      store.entity.stageDeviceSetting(
                        "ble_target_address",
                        (ev.currentTarget as HTMLInputElement).value.trim(),
                        "cfg-ble_target_address",
                      )}
                  />
                  <span class="help-text">${store.t("dev_presence.target_addr_help")}</span>
                </div>
                <div class="stacked-field">
                  <label for="cfg-ble_ref_power">
                    ${store.t("dev_presence.ref_power_label")}
                  </label>
                  <input
                    type="number"
                    id="cfg-ble_ref_power"
                    min="-90"
                    max="-30"
                    step="1"
                    placeholder=${refPowerPlaceholder}
                    .value=${focusSafe(refPowerValue)}
                    @change=${(ev: Event) => {
                      const raw = (ev.currentTarget as HTMLInputElement).value.trim();
                      if (raw === "") {
                        store.entity.stageDeviceSetting(
                          "ble_ref_power",
                          null,
                          "cfg-ble_ref_power",
                        );
                        return;
                      }
                      const num = Number(raw);
                      if (Number.isFinite(num)) {
                        store.entity.stageDeviceSetting(
                          "ble_ref_power",
                          Math.round(num),
                          "cfg-ble_ref_power",
                        );
                      }
                    }}
                  />
                  <span class="help-text">${store.t("dev_presence.ref_power_help")}</span>
                </div>
                ${showCompanionPowerTip
                  ? html`<div id="ble-companion-power-tip" class="alert">
                      <div class="alert-body">
                        <strong>${store.t("dev_presence.companion_low_title")}</strong>
                        <span>
                          ${store.t("dev_presence.companion_low_body", {
                            txPower:
                              txPowerRaw || store.t("dev_presence.companion_default_power"),
                            modeSuffix: advModeRaw
                              ? store.t("dev_presence.companion_mode_suffix", {
                                  mode: advModeRaw,
                                })
                              : "",
                            refSuffix: hasDetectedRefPower
                              ? store.t("dev_presence.companion_ref_suffix", {
                                  dbm: fmtNumber(Number(rawDetectedRef), store.hass, 0),
                                })
                              : "",
                          })}
                        </span>
                      </div>
                    </div>`
                  : nothing}
                ${!isBleOnly
                  ? html`<div class="stacked-field">
                      <label for="cfg-ble_beacon_uuid">
                        ${store.t("dev_presence.ibeacon_uuid_label")}
                      </label>
                      <input
                        type="text"
                        id="cfg-ble_beacon_uuid"
                        placeholder=${store.t("dev_presence.ibeacon_uuid_placeholder")}
                        .value=${focusSafe(String(cfg.ble_beacon_uuid || ""))}
                        @change=${(ev: Event) =>
                          store.entity.stageDeviceSetting(
                            "ble_beacon_uuid",
                            (ev.currentTarget as HTMLInputElement).value.trim(),
                            "cfg-ble_beacon_uuid",
                          )}
                      />
                    </div>`
                  : nothing}`,
            })
          : nothing}
      </div>
    </div>
  </section>`;
}
