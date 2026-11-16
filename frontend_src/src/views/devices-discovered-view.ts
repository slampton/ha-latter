/**
 * Discovered Devices View (`discovered_devices`): Two stacked full-width onboarding cards (`D-041`):
 * 1. `Latter Devices` — Unbound ESPHome Devices running Latter firmware ready for one-click adoption.
 * 2. `Bluetooth Devices` — Filterable/searchable BLE trackers, phones, and named advertisements.
 */

import { renderCard, renderSettingsRow } from "../components/controls.js";
import { html, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { DiscoveredBleCandidate, DiscoveredLatterDevice } from "../types.js";
import { entityLabel, fmtNumber } from "../utils/format.js";

function isTrackerCandidate(c: DiscoveredBleCandidate): boolean {
  const kind = String(c.kind || "").toLowerCase();
  const addr = String(c.target_address || c.address || "");
  return kind.includes("private ble") || kind.includes("ibeacon") || addr.includes(".");
}

export function renderDevicesDiscoveredView(store: StudioStore): TemplateResult {
  const data = store.state;
  const latterCandidates: DiscoveredLatterDevice[] = data?.discovered_latter_devices || [];
  const bleCandidates: DiscoveredBleCandidate[] = data?.discovered_ble_devices || [];
  const groups = data?.device_groups || [];
  const persons = data?.catalog?.persons || [];
  const groupNameMap = new Map<string, string>();
  for (const g of groups) {
    if (g && g.id) {
      groupNameMap.set(g.id, g.name || entityLabel(g.id.replace(/_/g, " ")));
    }
  }

  const kindFilter = store.discoveredBleKindFilter || "all";
  const query = (store.discoveredBleSearch || "").trim().toLowerCase();
  const filteredBle = bleCandidates.filter((c) => {
    if (kindFilter === "tracker" && !isTrackerCandidate(c)) return false;
    if (kindFilter === "named" && isTrackerCandidate(c)) return false;
    if (!query) return true;
    const haystack = [
      c.title,
      c.name,
      c.target_address,
      c.address,
      c.kind,
      c.area_name,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });

  return html`<section id="view-discovered_devices">
    ${renderCard({
      title: "Latter Devices",
      headerActions: html`<button
        type="button"
        @click=${() => store.openHaPage("/config/integrations/integration/latter")}
        class="btn btn-secondary"
      >
        Open Integration
      </button>`,
      contentClass: "settings-list",
      body: html`<div id="latter-adopt-table-box" class="settings-list">
        ${latterCandidates.length
          ? latterCandidates.map((d, idx) => {
              const title = d.title || d.node_name || "Latter Device";
              const defGrpName =
                groupNameMap.get(d.default_group) ||
                entityLabel((d.default_group || "unassigned").replace(/_/g, " "));
              const meta: string[] = [d.model_label || "Latter ESPHome Device"];
              if (d.node_name) meta.push(`Node: ${d.node_name}`);
              if (d.area_name) meta.push(`Area: ${d.area_name}`);
              const grpSelId = `latter-adopt-group-${idx}`;
              const personSelId = `latter-adopt-person-${idx}`;

              return renderSettingsRow({
                label: title,
                description: meta.join(" • "),
                control: html`<select
                    id=${grpSelId}
                    data-role="group"
                    aria-label=${`Device Group for ${title}`}
                  >
                    <option value="auto">Auto (${defGrpName})</option>
                    ${groups.map((g) => html`<option value=${g.id}>${g.name}</option>`)}
                  </select>
                  <select
                    id=${personSelId}
                    data-role="person"
                    aria-label=${`Assigned person for ${title}`}
                  >
                    <option value="">No person</option>
                    ${persons.map((p) => html`<option value=${p.id}>${p.name}</option>`)}
                  </select>
                  <button
                    type="button"
                    @click=${(ev: Event) => {
                      const btn = ev.currentTarget as HTMLButtonElement;
                      const parent = btn.parentElement;
                      const grpSel = parent?.querySelector(
                        'select[data-role="group"]',
                      ) as HTMLSelectElement | null;
                      const personSel = parent?.querySelector(
                        'select[data-role="person"]',
                      ) as HTMLSelectElement | null;
                      void store.adoptLatterDevice(
                        d.esphome_device_id,
                        title,
                        grpSel?.value || "auto",
                        personSel?.value || "",
                      );
                    }}
                    class="btn btn-secondary btn-compact"
                  >
                    Adopt
                  </button>`,
              });
            })
          : html`<p class="empty-state">
              No unconfigured Latter Devices found in Home Assistant. Newly added ESPHome Devices running Latter firmware appear here automatically.
            </p>`}
      </div>`,
    })}

    ${renderCard({
      title: "Bluetooth Devices",
      headerActions: html`<input
          type="search"
          id="discovered-ble-search"
          aria-label="Search discovered Bluetooth devices"
          placeholder="Search name, address, or Area…"
          .value=${store.discoveredBleSearch}
          @input=${(ev: Event) => {
            store.discoveredBleSearch = (ev.currentTarget as HTMLInputElement).value;
            store.host.requestUpdate();
          }}
        />
        <select
          id="discovered-ble-filter"
          aria-label="Filter discovered Bluetooth devices"
          .value=${kindFilter}
          @change=${(ev: Event) => {
            const val = (ev.currentTarget as HTMLSelectElement).value;
            store.discoveredBleKindFilter =
              val === "tracker" || val === "named" ? val : "all";
            store.host.requestUpdate();
          }}
        >
          <option value="all" ?selected=${kindFilter === "all"}>All Bluetooth devices</option>
          <option value="tracker" ?selected=${kindFilter === "tracker"}>
            Phones and trackers
          </option>
          <option value="named" ?selected=${kindFilter === "named"}>
            Named advertisements
          </option>
        </select>
        <button
          type="button"
          @click=${() => store.openAddBleModal()}
          class="btn btn-primary"
        >
          Add BLE Tag
        </button>`,
      contentClass: "settings-list",
      body: html`<div id="ble-adopt-table-box" class="settings-list">
        ${filteredBle.length
          ? filteredBle.map((c, idx) => {
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
          : html`<p class="empty-state">
              ${bleCandidates.length
                ? "No Bluetooth devices match this filter."
                : "No unadopted Bluetooth devices nearby."}
            </p>`}
      </div>`,
    })}
  </section>`;
}
