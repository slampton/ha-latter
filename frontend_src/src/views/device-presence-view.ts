/**
 * Device BLE & Area Presence View (`presence`): Built-in BLE tracking, Fallback Area, and BLE Identity.
 */

import {
  renderCard,
  renderNativeControlRow,
  renderSelectRow,
  renderSwitchRow,
} from "../components/controls.js";
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
        ${renderCard({
          title: "Area Tracking",
          contentClass: "settings-list",
          body: html`${!isBleOnly
              ? html`${renderSwitchRow({
                    id: "cfg-native_ble_tracking",
                    label: "Track the Area with BLE Proxies",
                    description:
                      "Uses Home Assistant Area-assigned Bluetooth proxies to locate this Device automatically.",
                    checked: Boolean(cfg.native_ble_tracking),
                    onChange: (checked) =>
                      store.stageDeviceSetting(
                        "native_ble_tracking",
                        checked,
                        "cfg-native_ble_tracking",
                      ),
                  })}
                  ${renderSwitchRow({
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
                  })}`
              : nothing}
            ${renderSelectRow({
              id: "cfg-default_area",
              label: "Fallback Area",
              description:
                "Default Home Assistant Area when BLE tracking is off or no proxy is in range.",
              value: cfg.default_area,
              choices: data?.catalog?.areas,
              emptyOptionLabel: "— Automatic (ESPHome Area) —",
              onChange: (val) =>
                store.stageDeviceSetting("default_area", val, "cfg-default_area"),
            })}
            ${bleAreaItems.map((it) => renderNativeControlRow(store, it))}`,
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
