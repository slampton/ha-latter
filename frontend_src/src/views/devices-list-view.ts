/**
 * Devices Scope Landing View (`select_device_prompt`): Filterable, keyboard-accessible sortable Devices table.
 */

import { renderCard, renderSortHeader } from "../components/controls.js";
import { html, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { SystemDeviceEntry } from "../types.js";

function statusRank(st: string): number {
  if (st === "Update available") return 1;
  if (st === "Offline") return 2;
  return 3;
}

export function renderDevicesListView(store: StudioStore): TemplateResult {
  const allDevices: SystemDeviceEntry[] = store.state?.system_devices || [];
  const groups = store.state?.device_groups || [];
  const cat = store.deviceCategoryFilter || "all";

  const baseCategories: Array<{ id: string; label: string }> = [
    { id: "all", label: "All Devices" },
    { id: "online", label: "Online" },
    { id: "native", label: "Latter Displays" },
    { id: "ble_tracked", label: "BLE Tracked" },
    { id: "assigned_person", label: "Assigned to a Person" },
    { id: "roaming", label: "Roaming Devices" },
    { id: "stationary", label: "Stationary Devices" },
    { id: "headless", label: "Screenless Devices" },
    { id: "ble_tag", label: "BLE tags" },
    { id: "updates", label: "Firmware update available" },
  ];
  for (const g of groups) {
    if (g && g.id && g.id !== "unassigned") {
      baseCategories.push({ id: `group:${g.id}`, label: `Group: ${g.name}` });
    }
  }

  const filtered = allDevices.filter((d) => {
    const isBleTag = d.kind === "ble_tag";
    const isRoaming = isBleTag || Boolean(d.is_roaming);
    if (cat === "online") return Boolean(d.is_online);
    if (cat === "native") return Boolean(d.is_latter_native);
    if (cat === "ble_tracked") return Boolean(d.ble_tracked);
    if (cat === "assigned_person") return Boolean(d.assigned_person);
    if (cat === "roaming") return isRoaming;
    if (cat === "stationary") return !isRoaming;
    if (cat === "headless") return isBleTag || !d.has_display;
    if (cat === "ble_tag") return isBleTag;
    if (cat === "updates") return d.status_label === "Update available";
    if (cat.startsWith("group:")) return d.device_group === cat.slice(6);
    return true;
  });

  filtered.sort((a, b) => {
    let cmp = 0;
    if (store.deviceSortField === "status") {
      cmp = statusRank(a.status_label) - statusRank(b.status_label);
      if (cmp === 0) cmp = (a.title || "").localeCompare(b.title || "");
    } else if (store.deviceSortField === "model") {
      cmp = (a.model_label || "").localeCompare(b.model_label || "");
    } else if (store.deviceSortField === "area") {
      cmp = (a.area_label || "").localeCompare(b.area_label || "");
    } else if (store.deviceSortField === "group") {
      cmp = (a.device_group_name || "").localeCompare(b.device_group_name || "");
    } else {
      cmp = (a.title || "").localeCompare(b.title || "");
    }
    return store.deviceSortAsc ? cmp : -cmp;
  });

  return html`<section id="view-select_device_prompt">
    ${renderCard({
      title: "Devices",
      headerActions: html`<select
          id="device-category-filter"
          aria-label="Filter Devices by category"
          .value=${cat}
          @change=${(ev: Event) => {
            store.deviceCategoryFilter = (ev.currentTarget as HTMLSelectElement).value || "all";
            store.host.requestUpdate();
          }}
        >
          ${baseCategories.map(
            (o) => html`<option value=${o.id} ?selected=${o.id === cat}>${o.label}</option>`,
          )}
        </select>
        <button
          type="button"
          @click=${() => store.openHaPage("/config/integrations/integration/latter")}
          class="btn btn-primary"
        >
          Add Device
        </button>
        <button
          type="button"
          @click=${() => store.openAddBleModal()}
          class="btn btn-secondary"
        >
          Add BLE Tag
        </button>`,
      body: filtered.length
        ? html`<div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  ${renderSortHeader(store, "title", "Device")}
                  ${renderSortHeader(store, "model", "Model")}
                  ${renderSortHeader(store, "area", "Area")}
                  ${renderSortHeader(store, "group", "Group")}
                  ${renderSortHeader(store, "status", "Status")}
                  <th><span class="sort-btn" aria-hidden="true"></span></th>
                </tr>
              </thead>
              <tbody>
                ${repeat(
                  filtered,
                  (d) => d.subentry_id,
                  (d) => {
                    const st = d.status_label || "—";
                    const dotCls =
                      st === "Update available" ? "update" : st === "Offline" ? "" : "online";
                    const openRow = (): void => {
                      void store.switchSystemDevice(d.subentry_id);
                    };
                    const onRowKey = (ev: Event): void => {
                      const kev = ev as KeyboardEvent;
                      if (kev.key === "Enter" || kev.key === " ") {
                        kev.preventDefault();
                        openRow();
                      }
                    };
                    return html`<tr
                      tabindex="0"
                      aria-label=${`Open ${d.title}`}
                      @click=${openRow}
                      @keydown=${onRowKey}
                    >
                      <td class="col-name">${d.title}</td>
                      <td>${d.model_label || "—"}</td>
                      <td>${d.area_label || "—"}</td>
                      <td>${d.device_group_name || "—"}</td>
                      <td><span class="status-dot ${dotCls}"></span>${st}</td>
                      <td class="col-open" aria-hidden="true">›</td>
                    </tr>`;
                  },
                )}
              </tbody>
            </table>
          </div>`
        : html`<p class="empty-state">
            ${allDevices.length
              ? "No Devices match this category."
              : "No Devices yet. Latter Devices appear here after you add them in Home Assistant."}
          </p>`,
    })}
  </section>`;
}
