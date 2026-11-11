/**
 * Device BLE & Area Presence View (`presence`): Built-in BLE tracking, Fallback Area, and BLE Identity.
 */

import { renderNativeControlRow, renderSelectOptions } from "../components/controls.js";
import { html, nothing, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";

export function renderDevicePresenceView(store: StudioStore): TemplateResult {
  const data = store.state;
  const cfg = data?.config || {};
  const isBleOnly = cfg.kind === "ble_tag";

  const bleAreaItems = store
    .getSectionItems("area")
    .filter((it) => (it.name || "").toLowerCase().includes("ble"));

  return html`<section id="view-presence">
    <div class="columns">
      <div class="column">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">Area Tracking</h3>
          </div>
          <div class="card-content settings-list">
            ${!isBleOnly
              ? html`<div class="settings-row">
                    <div class="settings-row-text">
                      <label for="cfg-native_ble_tracking" class="row-label">Track the Area with BLE Proxies</label>
                      <p class="row-description">
                        Uses Home Assistant Area-assigned Bluetooth proxies to locate this Device automatically.
                      </p>
                    </div>
                    <div class="settings-row-control">
                      <input
                        type="checkbox"
                        id="cfg-native_ble_tracking"
                        role="switch"
                        .checked=${Boolean(cfg.native_ble_tracking)}
                        @change=${(ev: Event) =>
                          store.stageDeviceSetting(
                            "native_ble_tracking",
                            (ev.currentTarget as HTMLInputElement).checked,
                            "cfg-native_ble_tracking",
                          )}
                        class="switch"
                      />
                    </div>
                  </div>
                  <div class="settings-row">
                    <div class="settings-row-text">
                      <label for="cfg-ble_auto_switch" class="row-label">Auto-Switch Active Area</label>
                      <p class="row-description">
                        Switches the Device's active Area controls automatically when BLE detects a move.
                      </p>
                    </div>
                    <div class="settings-row-control">
                      <input
                        type="checkbox"
                        id="cfg-ble_auto_switch"
                        role="switch"
                        .checked=${Boolean(cfg.ble_auto_switch)}
                        @change=${(ev: Event) =>
                          store.stageDeviceSetting(
                            "ble_auto_switch",
                            (ev.currentTarget as HTMLInputElement).checked,
                            "cfg-ble_auto_switch",
                          )}
                        class="switch"
                      />
                    </div>
                  </div>`
              : nothing}

            <div class="settings-row">
              <div class="settings-row-text">
                <label for="cfg-default_area" class="row-label">Fallback Area</label>
                <p class="row-description">
                  Default Home Assistant Area when BLE tracking is off or no proxy is in range.
                </p>
              </div>
              <div class="settings-row-control">
                <select
                  id="cfg-default_area"
                  .value=${String(cfg.default_area || "")}
                  @change=${(ev: Event) =>
                    store.stageDeviceSetting(
                      "default_area",
                      (ev.currentTarget as HTMLSelectElement).value,
                      "cfg-default_area",
                    )}
                >
                  ${renderSelectOptions(
                    data?.catalog?.areas,
                    cfg.default_area,
                    "— Automatic (ESPHome Area) —",
                  )}
                </select>
              </div>
            </div>

            ${bleAreaItems.map((it) => renderNativeControlRow(store, it))}
          </div>
        </div>
      </div>

      <div class="column">
        <div class="card">
          <div class="card-header">
            <h3 class="card-title">BLE Identity</h3>
          </div>
          <div class="card-content stack">
            <div class="stacked-field">
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
              : nothing}
          </div>
        </div>
      </div>
    </div>
  </section>`;
}
