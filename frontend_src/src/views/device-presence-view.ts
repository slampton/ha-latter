/**
 * Device BLE & Area Presence View (`presence`, D-032 / D-036):
 * Static Assigned Area vs. BLE Roaming, Fallback Area, and BLE Identity.
 */

import {
  renderCard,
  renderNativeControlRow,
  renderPrefControlRow,
  renderSelectRow,
  renderSwitchRow,
} from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { fmtNumber } from "../utils/format.js";

export function renderDevicePresenceView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const isBleOnly = cfg.kind === "ble_tag";
  const bleTracking = isBleOnly || Boolean(cfg.native_ble_tracking);
  const detectedRefPower = data?.live?.ble_detected_ref_power ?? -59;
  const refPowerPlaceholder = `Auto (${fmtNumber(detectedRefPower, store.hass, 0)} dBm)`;
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

  const bleBeaconPref = store.getPref("ble_beacon_mode");
  const bleAreaItems = store
    .getSectionItems("area")
    .filter((it) => !it.pref_key && it.key !== "ble_beacon_mode");

  return html`<section id="view-presence">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Area Tracking",
          contentClass: "settings-list",
          body: html`${!isBleOnly
              ? renderSwitchRow({
                  id: "cfg-native_ble_tracking",
                  label: "Track the Area with BLE Proxies",
                  description:
                    "Uses Home Assistant Area-assigned Bluetooth proxies to locate this Device automatically. Turn off to pin it to one assigned Area.",
                  checked: Boolean(cfg.native_ble_tracking),
                  onChange: (checked) =>
                    store.stageDeviceSetting(
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
                        label: "Auto-Switch Active Area",
                        description:
                          "Switches the Device's active Area controls automatically when BLE detects a move.",
                        checked: Boolean(cfg.ble_auto_switch),
                        onChange: (checked) =>
                          store.stageDeviceSetting(
                            "ble_auto_switch",
                            checked,
                            "cfg-ble_auto_switch",
                          ),
                      })
                    : nothing}
                  ${renderSelectRow({
                    id: "cfg-default_area",
                    label: "Fallback Area",
                    description:
                      "Default Home Assistant Area when no Bluetooth proxy is in range.",
                    value: cfg.default_area,
                    choices: data?.catalog?.areas,
                    emptyOptionLabel: "— Automatic (ESPHome Area) —",
                    onChange: (val) =>
                      store.stageDeviceSetting(
                        "default_area",
                        val,
                        "cfg-default_area",
                      ),
                  })}
                  ${bleBeaconPref ? renderPrefControlRow(store, bleBeaconPref) : nothing}
                  ${bleAreaItems.map((it) => renderNativeControlRow(store, it))}`
              : renderSelectRow({
                  id: "cfg-default_area",
                  label: "Assigned Area",
                  description:
                    "Pins this Device's Area controls and Home Assistant Device Area to one location.",
                  value: cfg.default_area,
                  choices: data?.catalog?.areas,
                  emptyOptionLabel: "— Unassigned —",
                  onChange: (val) =>
                    store.stageDeviceSetting(
                      "default_area",
                      val,
                      "cfg-default_area",
                    ),
                })}`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "BLE Identity",
          contentClass: "stack",
          body: html`<div class="stacked-field">
              <label for="cfg-ble_target_address">BLE Target Address or Entity</label>
              <input
                type="text"
                id="cfg-ble_target_address"
                placeholder="AA:BB:CC:DD:EE:FF or device_tracker.phone_ble"
                .value=${String(cfg.ble_target_address || "")}
                @change=${(ev: Event) =>
                  store.stageDeviceSetting(
                    "ble_target_address",
                    (ev.currentTarget as HTMLInputElement).value.trim(),
                    "cfg-ble_target_address",
                  )}
              />
              <span class="help-text">
                Leave blank on Latter displays to track their built-in BLE beacon MAC automatically.
              </span>
            </div>
            <div class="stacked-field">
              <label for="cfg-ble_ref_power">Reference Power (1 Meter)</label>
              <input
                type="number"
                id="cfg-ble_ref_power"
                min="-90"
                max="-30"
                step="1"
                placeholder=${refPowerPlaceholder}
                .value=${refPowerValue}
                @change=${(ev: Event) => {
                  const raw = (ev.currentTarget as HTMLInputElement).value.trim();
                  if (raw === "") {
                    store.stageDeviceSetting("ble_ref_power", null, "cfg-ble_ref_power");
                    return;
                  }
                  const num = Number(raw);
                  if (Number.isFinite(num)) {
                    store.stageDeviceSetting("ble_ref_power", Math.round(num), "cfg-ble_ref_power");
                  }
                }}
              />
              <span class="help-text">
                Leave blank to use auto-detected beacon power in dBm, or enter -90 to -30 dBm to calibrate this Device.
              </span>
            </div>
            ${showCompanionPowerTip
              ? html`<div id="ble-companion-power-tip" class="alert">
                  <div class="alert-body">
                    <strong>Companion App Low-Power Beacon Detected</strong>
                    <span>
                      This phone is advertising at <code>${txPowerRaw || "default"}</code> power${advModeRaw
                        ? html` (<code>${advModeRaw}</code> mode)`
                        : nothing}. Latter automatically compensates its 1 m reference power (${fmtNumber(detectedRefPower, store.hass, 0)} dBm), and setting <strong>Transmit Power</strong> to <strong>Medium</strong> or <strong>High</strong> and <strong>Advertise Mode</strong> to <strong>Balanced</strong> in the Home Assistant Companion App improves multi-Area accuracy through walls.
                    </span>
                  </div>
                </div>`
              : nothing}
            ${!isBleOnly
              ? html`<div class="stacked-field">
                  <label for="cfg-ble_beacon_uuid">iBeacon UUID</label>
                  <input
                    type="text"
                    id="cfg-ble_beacon_uuid"
                    placeholder="Generated automatically per System"
                    .value=${String(cfg.ble_beacon_uuid || "")}
                    @change=${(ev: Event) =>
                      store.stageDeviceSetting(
                        "ble_beacon_uuid",
                        (ev.currentTarget as HTMLInputElement).value.trim(),
                        "cfg-ble_beacon_uuid",
                      )}
                  />
                </div>`
              : nothing}`,
        })}
      </div>
    </div>
  </section>`;
}
