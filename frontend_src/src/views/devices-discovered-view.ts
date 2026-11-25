/**
 * Discovered Devices View (`discovered_devices`, `D-041`, `D-066`):
 * Two stacked full-width onboarding cards:
 * 1. `Latter Devices` — Unbound ESPHome Devices running Latter firmware ready for adoption or ignore,
 *    plus collapsible `Ignored (N)` restore drawer and Web Installer / Getting started empty-state links.
 * 2. `Bluetooth devices` — Filterable (`c.is_tracker`), sortable, and pausable BLE trackers, phones,
 *    and named advertisements with unique keyed DOM identity.
 */

import { renderCard, renderSettingsRow } from "../components/controls.js";
import { focusSafe, html, live, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { DiscoveredBleCandidate, DiscoveredLatterDevice } from "../types.js";
import { entityLabel, fmtNumber } from "../utils/format.js";

const WEB_INSTALLER_URL = "https://slampton.github.io/esphome-latter-core/";
const GETTING_STARTED_URL =
  "https://github.com/slampton/ha-latter/blob/main/docs/getting-started.md";

export const DISCOVERED_BLE_PAGE_SIZE = 30;
const bleVisibleLimitByStore = new WeakMap<StudioStore, number>();

export function discoveredBleCandidateKey(
  store: StudioStore,
  c: DiscoveredBleCandidate,
): string {
  return (c.target_address || candidateTitle(store, c)).toLowerCase();
}

export function discoveredLatterDeviceKey(d: DiscoveredLatterDevice): string {
  return d.esphome_device_id || d.node_name || d.title;
}

function candidateTitle(store: StudioStore, c: DiscoveredBleCandidate): string {
  return c.title || c.target_address || store.t("status.ble_tag");
}

function compareBleCandidates(
  store: StudioStore,
  a: DiscoveredBleCandidate,
  b: DiscoveredBleCandidate,
  sortMode: "name" | "rssi" | "area",
): number {
  const aTitle = candidateTitle(store, a);
  const bTitle = candidateTitle(store, b);
  const aAddr = a.target_address || "";
  const bAddr = b.target_address || "";

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
  const ignoredLatter: DiscoveredLatterDevice[] = data?.ignored_latter_devices || [];
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
      if (kindFilter === "tracker" && !c.is_tracker) return false;
      if (kindFilter === "named" && c.is_tracker) return false;
      if (!query) return true;
      const haystack = [c.title, c.target_address, c.kind, c.area_name]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    })
    .slice()
    .sort((a, b) => compareBleCandidates(store, a, b, sortMode));

  const visibleBleLimit = bleVisibleLimitByStore.get(store) ?? DISCOVERED_BLE_PAGE_SIZE;
  const visibleBle = filteredBle.slice(0, visibleBleLimit);
  const remainingBleCount = Math.max(0, filteredBle.length - visibleBle.length);

  const latterDraftGroups = store.discoveredLatterGroupDrafts;
  const latterDraftPersons = store.discoveredLatterPersonDrafts;
  const bleDraftPersons = store.discoveredBlePersonDrafts;

  return html`<section id="view-discovered_devices">
    ${renderCard({
      id: "card-discovered-latter",
      handoffActive: store.isHandoffTarget("card-discovered-latter"),
      title: store.t("discovered.latter_devices"),
      headerActions: html`<button
        type="button"
        @click=${() => store.openHaPage("/config/integrations/integration/latter")}
        class="btn btn-secondary"
      >
        ${store.t("action.open_integration")}
      </button>`,
      contentClass: "stack",
      body: html`<div id="latter-adopt-table-box" class="settings-list">
          ${latterCandidates.length
            ? repeat(
                latterCandidates,
                (d) => discoveredLatterDeviceKey(d),
                (d) => {
                  const title =
                    d.title || d.node_name || store.t("discovered.default_latter_title");
                  const defGrpName =
                    groupNameMap.get(d.default_group) ||
                    entityLabel((d.default_group || "custom").replace(/_/g, " "));
                  const meta: string[] = [
                    d.model_label || store.t("discovered.default_latter_model"),
                  ];
                  if (d.node_name) {
                    meta.push(store.t("discovered.meta_node", { node: d.node_name }));
                  }
                  if (d.area_name) {
                    meta.push(store.t("discovered.meta_area", { area: d.area_name }));
                  }
                  const curGrp = latterDraftGroups.get(d.esphome_device_id) || "auto";
                  const curPerson = latterDraftPersons.get(d.esphome_device_id) || "";

                  return renderSettingsRow({
                    label: title,
                    description: meta.join(" • "),
                    control: html`<select
                        aria-label=${store.t("discovered.group_select_aria", { title })}
                        .value=${live(curGrp)}
                        @change=${(ev: Event) => {
                          latterDraftGroups.set(
                            d.esphome_device_id,
                            (ev.currentTarget as HTMLSelectElement).value || "auto",
                          );
                          store.host.requestUpdate();
                        }}
                      >
                        <option value="auto" .selected=${live(curGrp === "auto")}>
                          ${store.t("discovered.auto_group_option", { group: defGrpName })}
                        </option>
                        <option value="custom" .selected=${live(curGrp === "custom")}>
                          ${store.t("common.custom")}
                        </option>
                        ${groups.map(
                          (g) =>
                            html`<option value=${g.id} .selected=${live(curGrp === g.id)}>
                              ${g.name}
                            </option>`,
                        )}
                      </select>
                      <select
                        aria-label=${store.t("discovered.person_select_aria", { title })}
                        .value=${live(curPerson)}
                        @change=${(ev: Event) => {
                          latterDraftPersons.set(
                            d.esphome_device_id,
                            (ev.currentTarget as HTMLSelectElement).value || "",
                          );
                          store.host.requestUpdate();
                        }}
                      >
                        <option value="" .selected=${live(!curPerson)}>
                          ${store.t("common.no_person")}
                        </option>
                        ${persons.map(
                          (p) =>
                            html`<option value=${p.id} .selected=${live(curPerson === p.id)}>
                              ${p.name}
                            </option>`,
                        )}
                      </select>
                      <button
                        type="button"
                        @click=${() =>
                          void store.tools.adoptLatterDevice(
                            d.esphome_device_id,
                            title,
                            latterDraftGroups.get(d.esphome_device_id) || "auto",
                            latterDraftPersons.get(d.esphome_device_id) || "",
                          )}
                        class="btn btn-primary btn-compact"
                      >
                        ${store.t("action.adopt")}
                      </button>
                      <button
                        type="button"
                        aria-label=${store.t("discovered.ignore_aria", { title })}
                        @click=${() =>
                          void store.tools.ignoreDiscoveredDevice(d.esphome_device_id, title)}
                        class="btn btn-text btn-compact"
                      >
                        ${store.t("action.ignore")}
                      </button>`,
                  });
                },
              )
            : html`<div class="stack">
                <p class="empty-state">${store.t("discovered.empty_latter")}</p>
                <div class="input-action-row">
                  <a
                    href=${WEB_INSTALLER_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="btn btn-secondary btn-compact"
                  >
                    ${store.t("discovered.web_installer")}
                  </a>
                  <a
                    href=${GETTING_STARTED_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="btn btn-text btn-compact"
                  >
                    ${store.t("discovered.getting_started")}
                  </a>
                </div>
              </div>`}
        </div>
        ${ignoredLatter.length > 0
          ? html`<details
              id="discovered-ignored-drawer"
              class="sub-collapsible summary-row"
              ?open=${store.discoveredIgnoredOpen}
              @toggle=${(ev: Event) => {
                const isOpen = (ev.currentTarget as HTMLDetailsElement).open;
                if (store.discoveredIgnoredOpen !== isOpen) {
                  store.discoveredIgnoredOpen = isOpen;
                  store.host.requestUpdate();
                }
              }}
            >
              <summary>
                <span class="row-label">
                  ${store.t("discovered.ignored_count", {
                    count: fmtNumber(ignoredLatter.length, store.hass, 0),
                  })}
                </span>
                <span class="summary-row-end">
                  <span class="summary-chevron" aria-hidden="true">▾</span>
                </span>
              </summary>
              ${store.discoveredIgnoredOpen
                ? html`<div class="card-content settings-list">
                    ${repeat(
                      ignoredLatter,
                      (d) => `ignored::${discoveredLatterDeviceKey(d)}`,
                      (d) => {
                        const title =
                          d.title || d.node_name || store.t("discovered.default_latter_title");
                        const meta: string[] = [
                          d.model_label || store.t("discovered.default_latter_model"),
                        ];
                        if (d.node_name) {
                          meta.push(store.t("discovered.meta_node", { node: d.node_name }));
                        }
                        if (d.area_name) {
                          meta.push(store.t("discovered.meta_area", { area: d.area_name }));
                        }
                        return renderSettingsRow({
                          label: title,
                          description: meta.join(" • "),
                          control: html`<button
                            type="button"
                            aria-label=${store.t("discovered.restore_aria", { title })}
                            @click=${() =>
                              void store.tools.unignoreDiscoveredDevice(d.esphome_device_id, title)}
                            class="btn btn-secondary btn-compact"
                          >
                            ${store.t("action.unignore")}
                          </button>`,
                        });
                      },
                    )}
                  </div>`
                : nothing}
            </details>`
          : nothing}`,
    })}

    ${renderCard({
      id: "card-discovered-ble",
      handoffActive: store.isHandoffTarget("card-discovered-ble"),
      title: store.t("discovered.bluetooth_devices"),
      headerActions: html`<input
          type="search"
          id="discovered-ble-search"
          aria-label=${store.t("discovered.search_ble_aria")}
          placeholder=${store.t("discovered.search_ble_placeholder")}
          .value=${focusSafe(store.discoveredBleSearch)}
          @input=${(ev: Event) => {
            store.discoveredBleSearch = (ev.currentTarget as HTMLInputElement).value;
            bleVisibleLimitByStore.delete(store);
            store.host.requestUpdate();
          }}
        />
        <select
          id="discovered-ble-filter"
          aria-label=${store.t("discovered.filter_ble_aria")}
          .value=${live(kindFilter)}
          @change=${(ev: Event) => {
            const val = (ev.currentTarget as HTMLSelectElement).value;
            store.discoveredBleKindFilter =
              val === "tracker" || val === "named" ? val : "all";
            bleVisibleLimitByStore.delete(store);
            store.host.requestUpdate();
          }}
        >
          <option value="all" .selected=${live(kindFilter === "all")}>
            ${store.t("discovered.all_ble")}
          </option>
          <option value="tracker" .selected=${live(kindFilter === "tracker")}>
            ${store.t("discovered.phones_trackers")}
          </option>
          <option value="named" .selected=${live(kindFilter === "named")}>
            ${store.t("discovered.named_ble")}
          </option>
        </select>
        <select
          id="discovered-ble-sort"
          aria-label=${store.t("discovered.sort_ble_aria")}
          .value=${live(sortMode)}
          @change=${(ev: Event) => {
            const val = (ev.currentTarget as HTMLSelectElement).value;
            store.discoveredBleSort =
              val === "rssi" || val === "area" ? val : "name";
            bleVisibleLimitByStore.delete(store);
            store.host.requestUpdate();
          }}
        >
          <option value="name" .selected=${live(sortMode === "name")}>
            ${store.t("discovered.sort_name")}
          </option>
          <option value="rssi" .selected=${live(sortMode === "rssi")}>
            ${store.t("discovered.sort_rssi")}
          </option>
          <option value="area" .selected=${live(sortMode === "area")}>
            ${store.t("discovered.sort_area")}
          </option>
        </select>
        <button
          type="button"
          id="btn-pause-discovered-ble"
          aria-pressed=${String(isPaused)}
          @click=${() => store.toggleDiscoveredBlePause()}
          class="btn btn-secondary"
        >
          ${isPaused ? store.t("discovered.resume_list") : store.t("discovered.pause_list")}
        </button>
        <button
          type="button"
          @click=${() => store.tools.openAddBleModal()}
          class="btn btn-primary"
        >
          ${store.t("action.add_ble_tag")}
        </button>`,
      contentClass: "settings-list",
      body: html`<div id="ble-adopt-table-box" class="settings-list">
        ${isPaused
          ? html`<p class="help-text">
              ${store.t("discovered.paused_hint", {
                count: fmtNumber(filteredBle.length, store.hass, 0),
              })}
            </p>`
          : nothing}
        ${visibleBle.length
          ? html`${repeat(
                visibleBle,
                (c) => discoveredBleCandidateKey(store, c),
                (c) => {
                  const title = candidateTitle(store, c);
                  const addr = c.target_address || "";
                  const addrKey = (addr || title).toLowerCase();
                  const curPerson = bleDraftPersons.get(addrKey) || "";
                  const kindLabel = c.kind || store.t("discovered.default_ble_kind");
                  const showAddr =
                    Boolean(addr) && !kindLabel.toLowerCase().includes(addr.toLowerCase());
                  const meta = [kindLabel, ...(showAddr ? [addr] : [])];
                  if (c.rssi !== null && c.rssi !== undefined) {
                    meta.push(`${fmtNumber(c.rssi, store.hass, 0)} dBm`);
                  }
                  if (c.area_name) {
                    meta.push(store.t("discovered.meta_nearest_area", { area: c.area_name }));
                  }

                  return renderSettingsRow({
                    label: title,
                    description: meta.join(" • "),
                    control: html`<select
                        aria-label=${store.t("discovered.person_select_aria", { title })}
                        .value=${live(curPerson)}
                        @change=${(ev: Event) => {
                          bleDraftPersons.set(
                            addrKey,
                            (ev.currentTarget as HTMLSelectElement).value || "",
                          );
                          store.host.requestUpdate();
                        }}
                      >
                        <option value="" .selected=${live(!curPerson)}>
                          ${store.t("common.no_person")}
                        </option>
                        ${persons.map(
                          (p) =>
                            html`<option value=${p.id} .selected=${live(curPerson === p.id)}>
                              ${p.name}
                            </option>`,
                        )}
                      </select>
                      <button
                        type="button"
                        @click=${() =>
                          void store.tools.quickAdoptBleCandidate(
                            title,
                            addr,
                            bleDraftPersons.get(addrKey) || "",
                          )}
                        class="btn btn-secondary btn-compact"
                      >
                        ${store.t("action.adopt")}
                      </button>`,
                  });
                },
              )}
              ${filteredBle.length > DISCOVERED_BLE_PAGE_SIZE
                ? html`<div class="input-action-row">
                    <span class="row-description">
                      ${store.t("photos.page_status", {
                        start: fmtNumber(1, store.hass, 0),
                        end: fmtNumber(visibleBle.length, store.hass, 0),
                        total: fmtNumber(filteredBle.length, store.hass, 0),
                      })}
                    </span>
                    ${remainingBleCount > 0
                      ? html`<button
                          type="button"
                          id="btn-discovered-ble-show-more"
                          @click=${() => {
                            bleVisibleLimitByStore.set(
                              store,
                              visibleBleLimit + DISCOVERED_BLE_PAGE_SIZE,
                            );
                            store.host.requestUpdate();
                          }}
                          class="btn btn-secondary btn-compact"
                        >
                          Show more (${store.t("sys_overview.plus_more", {
                            count: fmtNumber(remainingBleCount, store.hass, 0),
                          })})
                        </button>`
                      : nothing}
                    ${visibleBleLimit > DISCOVERED_BLE_PAGE_SIZE
                      ? html`<button
                          type="button"
                          id="btn-discovered-ble-show-fewer"
                          @click=${() => {
                            bleVisibleLimitByStore.delete(store);
                            store.host.requestUpdate();
                          }}
                          class="btn btn-text btn-compact"
                        >
                          Show fewer
                        </button>`
                      : nothing}
                  </div>`
                : nothing}`
          : html`<p class="empty-state">
              ${bleCandidates.length
                ? store.t("discovered.empty_ble_filtered")
                : store.t("discovered.empty_ble_none")}
            </p>`}
      </div>`,
    })}
  </section>`;
}
