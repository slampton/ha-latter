/**
 * Discovered Devices View (`discovered_devices`): Two stacked full-width onboarding cards (`D-041`):
 * 1. `Latter Devices` — Unbound ESPHome Devices running Latter firmware ready for one-click adoption.
 * 2. `Bluetooth Devices` — Filterable, sortable (Name default so RSSI changes never reorder rows),
 *    and pausable BLE trackers, phones, and named advertisements with keyed DOM identity.
 */

import { renderCard, renderSettingsRow } from "../components/controls.js";
import { html, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { DiscoveredBleCandidate, DiscoveredLatterDevice } from "../types.js";
import { entityLabel, fmtNumber } from "../utils/format.js";

const TRACKER_KIND_TOKENS: ReadonlyArray<string> = [
  "companion app",
  "private ble",
  "ibeacon",
  "bthome",
  "tile",
  "itag",
  "ruuvitag",
  "eddystone",
];

function isTrackerCandidate(c: DiscoveredBleCandidate): boolean {
  const kind = String(c.kind || "").toLowerCase();
  const addr = String(c.target_address || c.address || "");
  return addr.includes(".") || TRACKER_KIND_TOKENS.some((tok) => kind.includes(tok));
}

function candidateTitle(c: DiscoveredBleCandidate): string {
  return c.title || c.name || c.target_address || c.address || "BLE Tag";
}

function candidateAddr(c: DiscoveredBleCandidate): string {
  return c.target_address || c.address || "";
}

function compareBleCandidates(
  a: DiscoveredBleCandidate,
  b: DiscoveredBleCandidate,
  sortMode: "name" | "rssi" | "area",
): number {
  const aTitle = candidateTitle(a);
  const bTitle = candidateTitle(b);
  const aAddr = candidateAddr(a);
  const bAddr = candidateAddr(b);

  if (sortMode === "rssi") {
    const aHas = a.rssi !== null && a.rssi !== undefined;
    const bHas = b.rssi !== null && b.rssi !== undefined;
    if (aHas !== bHas) return aHas ? -1 : 1;
    if (aHas && bHas && a.rssi !== b.rssi) return Number(b.rssi) - Number(a.rssi);
  } else if (sortMode === "area") {
    const aArea = String(a.area_name || "").trim();
    const bArea = String(b.area_name || "").trim();
    if (Boolean(aArea) !== Boolean(bArea)) return aArea ? -1 : 1;
    if (aArea && bArea) {
      const areaCmp = aArea.localeCompare(bArea, undefined, { sensitivity: "base" });
      if (areaCmp !== 0) return areaCmp;
    }
  }

  const nameCmp = aTitle.localeCompare(bTitle, undefined, { sensitivity: "base" });
  if (nameCmp !== 0) return nameCmp;
  return aAddr.localeCompare(bAddr);
}

export function renderDevicesDiscoveredView(store: StudioStore): TemplateResult {
  const data = store.state;
  const latterCandidates: DiscoveredLatterDevice[] = data?.discovered_latter_devices || [];
  const isPaused = Boolean(store.discoveredBlePaused);
  const bleCandidates: DiscoveredBleCandidate[] =
    isPaused && Array.isArray(store.discoveredBleFrozenSnapshot)
      ? store.discoveredBleFrozenSnapshot
      : data?.discovered_ble_devices || [];
  const groups = data?.device_groups || [];
  const persons = data?.catalog?.persons || [];
  const groupNameMap = new Map<string, string>();
  for (const g of groups) {
    if (g && g.id) {
      groupNameMap.set(g.id, g.name || entityLabel(g.id.replace(/_/g, " ")));
    }
  }

  const kindFilter = store.discoveredBleKindFilter || "all";
  const sortMode = store.discoveredBleSort || "name";
  const query = (store.discoveredBleSearch || "").trim().toLowerCase();
  const filteredBle = bleCandidates
    .filter((c) => {
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
    })
    .slice()
    .sort((a, b) => compareBleCandidates(a, b, sortMode));

  const latterDraftGroups = store.discoveredLatterGroupDrafts;
  const latterDraftPersons = store.discoveredLatterPersonDrafts;
  const bleDraftPersons = store.discoveredBlePersonDrafts;

  return html`<section id="view-discovered_devices">
    ${renderCard({
      id: "card-discovered-latter",
      handoffActive: Boolean(store.isHandoffTarget?.("card-discovered-latter")),
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
          ? repeat(
              latterCandidates,
              (d) => d.esphome_device_id,
              (d) => {
                const title = d.title || d.node_name || "Latter Device";
                const defGrpName =
                  groupNameMap.get(d.default_group) ||
                  entityLabel((d.default_group || "custom").replace(/_/g, " "));
                const meta: string[] = [d.model_label || "Latter ESPHome Device"];
                if (d.node_name) meta.push(`Node: ${d.node_name}`);
                if (d.area_name) meta.push(`Area: ${d.area_name}`);
                const curGrp = latterDraftGroups?.get(d.esphome_device_id) || "auto";
                const curPerson = latterDraftPersons?.get(d.esphome_device_id) || "";

                return renderSettingsRow({
                  label: title,
                  description: meta.join(" • "),
                  control: html`<select
                      data-role="group"
                      aria-label=${`Device Group for ${title}`}
                      .value=${curGrp}
                      @change=${(ev: Event) => {
                        latterDraftGroups?.set(
                          d.esphome_device_id,
                          (ev.currentTarget as HTMLSelectElement).value || "auto",
                        );
                      }}
                    >
                      <option value="auto" ?selected=${curGrp === "auto"}>
                        Auto (${defGrpName})
                      </option>
                      <option value="custom" ?selected=${curGrp === "custom"}>
                        Custom
                      </option>
                      ${groups.map(
                        (g) =>
                          html`<option value=${g.id} ?selected=${curGrp === g.id}>
                            ${g.name}
                          </option>`,
                      )}
                    </select>
                    <select
                      data-role="person"
                      aria-label=${`Assigned person for ${title}`}
                      .value=${curPerson}
                      @change=${(ev: Event) => {
                        latterDraftPersons?.set(
                          d.esphome_device_id,
                          (ev.currentTarget as HTMLSelectElement).value || "",
                        );
                      }}
                    >
                      <option value="" ?selected=${!curPerson}>No person</option>
                      ${persons.map(
                        (p) =>
                          html`<option value=${p.id} ?selected=${curPerson === p.id}>
                            ${p.name}
                          </option>`,
                      )}
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
                          grpSel?.value || latterDraftGroups?.get(d.esphome_device_id) || "auto",
                          personSel?.value || latterDraftPersons?.get(d.esphome_device_id) || "",
                        );
                      }}
                      class="btn btn-secondary btn-compact"
                    >
                      Adopt
                    </button>`,
                });
              },
            )
          : html`<p class="empty-state">
              No unconfigured Latter Devices found in Home Assistant. Newly added ESPHome Devices running Latter firmware appear here automatically.
            </p>`}
      </div>`,
    })}

    ${renderCard({
      id: "card-discovered-ble",
      handoffActive: Boolean(store.isHandoffTarget?.("card-discovered-ble")),
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
        <select
          id="discovered-ble-sort"
          aria-label="Sort discovered Bluetooth devices"
          .value=${sortMode}
          @change=${(ev: Event) => {
            const val = (ev.currentTarget as HTMLSelectElement).value;
            store.discoveredBleSort =
              val === "rssi" || val === "area" ? val : "name";
            store.host.requestUpdate();
          }}
        >
          <option value="name" ?selected=${sortMode === "name"}>Sort: Name (A–Z)</option>
          <option value="rssi" ?selected=${sortMode === "rssi"}>Sort: Signal strength</option>
          <option value="area" ?selected=${sortMode === "area"}>Sort: Nearest Area</option>
        </select>
        <button
          type="button"
          id="btn-pause-discovered-ble"
          aria-pressed=${String(isPaused)}
          @click=${() => store.toggleDiscoveredBlePause()}
          class="btn btn-secondary"
        >
          ${isPaused ? "Resume List" : "Pause List"}
        </button>
        <button
          type="button"
          @click=${() => store.openAddBleModal()}
          class="btn btn-primary"
        >
          Add BLE Tag
        </button>`,
      contentClass: "settings-list",
      body: html`<div id="ble-adopt-table-box" class="settings-list">
        ${isPaused
          ? html`<p class="help-text">
              List updates paused (${fmtNumber(filteredBle.length, store.hass, 0)} shown). Click Resume List to refresh.
            </p>`
          : nothing}
        ${filteredBle.length
          ? repeat(
              filteredBle,
              (c) => (candidateAddr(c) || candidateTitle(c)).toLowerCase(),
              (c) => {
                const title = candidateTitle(c);
                const addr = candidateAddr(c);
                const addrKey = (addr || title).toLowerCase();
                const curPerson = bleDraftPersons?.get(addrKey) || "";
                const kindLabel = c.kind || "BLE device";
                const showAddr =
                  Boolean(addr) && !kindLabel.toLowerCase().includes(addr.toLowerCase());
                const meta = [kindLabel, ...(showAddr ? [addr] : [])];
                if (c.rssi !== null && c.rssi !== undefined) {
                  meta.push(`${fmtNumber(c.rssi, store.hass, 0)} dBm`);
                }
                if (c.area_name) {
                  meta.push(`Nearest Area: ${c.area_name}`);
                }

                return renderSettingsRow({
                  label: title,
                  description: meta.join(" • "),
                  control: html`<select
                      aria-label=${`Assigned person for ${title}`}
                      .value=${curPerson}
                      @change=${(ev: Event) => {
                        bleDraftPersons?.set(
                          addrKey,
                          (ev.currentTarget as HTMLSelectElement).value || "",
                        );
                      }}
                    >
                      <option value="" ?selected=${!curPerson}>No person</option>
                      ${persons.map(
                        (p) =>
                          html`<option value=${p.id} ?selected=${curPerson === p.id}>
                            ${p.name}
                          </option>`,
                      )}
                    </select>
                    <button
                      type="button"
                      @click=${(ev: Event) => {
                        const btn = ev.currentTarget as HTMLButtonElement;
                        const sel = btn.parentElement?.querySelector(
                          "select",
                        ) as HTMLSelectElement | null;
                        void store.quickAdoptBleCandidate(
                          title,
                          addr,
                          sel?.value || bleDraftPersons?.get(addrKey) || "",
                        );
                      }}
                      class="btn btn-secondary btn-compact"
                    >
                      Adopt
                    </button>`,
                });
              },
            )
          : html`<p class="empty-state">
              ${bleCandidates.length
                ? "No Bluetooth devices match this filter."
                : "No unadopted Bluetooth devices nearby."}
            </p>`}
      </div>`,
    })}
  </section>`;
}
