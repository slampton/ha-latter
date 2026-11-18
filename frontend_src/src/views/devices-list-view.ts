/**
 * Managed Devices View (`select_device_prompt`): Filterable, keyboard-accessible sortable Devices table.
 * Card header dynamically reflects the active category selection (`D-041`), while zero-member groups
 * and unused specialty categories stay hidden unless active (`D-048`).
 */

import { renderCard, renderSortHeader } from "../components/controls.js";
import { html, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { SystemDeviceEntry } from "../types.js";
import { entityLabel } from "../utils/format.js";

function statusRank(st: string): number {
  if (st === "Update available") return 1;
  if (st === "Offline" || st === "Away" || st === "Scanning") return 2;
  return 3;
}

export function renderDevicesListView(store: StudioStore): TemplateResult {
  const allDevices: SystemDeviceEntry[] = store.state?.system_devices || [];
  const groups = store.state?.device_groups || [];
  const rawCat = store.deviceCategoryFilter || "all";

  const hasPhones = allDevices.some((d) => d.kind === "ble_tag" && d.ble_category === "phone");
  const hasBleTags = allDevices.some((d) => d.kind === "ble_tag" && d.ble_category !== "phone");
  const hasAssignedPeople = allDevices.some((d) => Boolean(d.assigned_person));
  const hasUpdates = allDevices.some((d) => d.status_label === "Update available");
  const hasCustomGroup = allDevices.some(
    (d) => d.kind !== "ble_tag" && (!d.device_group || d.device_group === "custom"),
  );

  const baseCategories: Array<{ id: string; label: string }> = [
    { id: "all", label: "All Devices" },
    { id: "online", label: "Online Devices" },
    { id: "roaming", label: "Roaming Devices" },
    { id: "stationary", label: "Stationary Devices" },
  ];
  if (rawCat === "native") {
    baseCategories.push({ id: "native", label: "Latter Displays" });
  }
  if (rawCat === "ble_tracked") {
    baseCategories.push({ id: "ble_tracked", label: "BLE-Tracked Devices" });
  }
  if (hasPhones || rawCat === "phone") {
    baseCategories.push({ id: "phone", label: "Phones" });
  }
  if (hasBleTags || rawCat === "ble_tag") {
    baseCategories.push({ id: "ble_tag", label: "BLE Tags" });
  }
  if (hasAssignedPeople || rawCat === "assigned_person") {
    baseCategories.push({ id: "assigned_person", label: "Assigned to a Person" });
  }
  if (hasUpdates || rawCat === "updates") {
    baseCategories.push({ id: "updates", label: "Updates Available" });
  }
  for (const g of groups) {
    if (!g || !g.id || g.id === "custom") continue;
    const grpFilterId = `group:${g.id}`;
    const hasMembers = allDevices.some((d) => d.kind !== "ble_tag" && d.device_group === g.id);
    if (hasMembers || rawCat === grpFilterId) {
      baseCategories.push({ id: grpFilterId, label: `Group: ${entityLabel(g.name)}` });
    }
  }
  if (hasCustomGroup || rawCat === "group:custom") {
    baseCategories.push({ id: "group:custom", label: "Group: Custom" });
  }

  const activeCategory = baseCategories.find((o) => o.id === rawCat) || baseCategories[0];
  const cat = activeCategory.id;

  const filtered = allDevices.filter((d) => {
    const isBleTag = d.kind === "ble_tag";
    const isRoaming = isBleTag || Boolean(d.is_roaming);
    if (cat === "online") return Boolean(d.is_online);
    if (cat === "native") return Boolean(d.is_latter_native);
    if (cat === "ble_tracked") return Boolean(d.ble_tracked);
    if (cat === "assigned_person") return Boolean(d.assigned_person);
    if (cat === "roaming") return isRoaming;
    if (cat === "stationary") return !isRoaming;
    if (cat === "phone") return isBleTag && d.ble_category === "phone";
    if (cat === "ble_tag") return isBleTag && d.ble_category !== "phone";
    if (cat === "updates") return d.status_label === "Update available";
    if (cat === "group:custom") {
      return !isBleTag && (!d.device_group || d.device_group === "custom");
    }
    if (cat.startsWith("group:")) return !isBleTag && d.device_group === cat.slice(6);
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
      title: activeCategory.label,
      headerActions: html`<select
        id="device-category-filter"
        aria-label="Filter Managed Devices by category"
        .value=${cat}
        @change=${(ev: Event) => {
          store.deviceCategoryFilter = (ev.currentTarget as HTMLSelectElement).value || "all";
          store.host.requestUpdate();
        }}
      >
        ${baseCategories.map(
          (o) => html`<option value=${o.id} ?selected=${o.id === cat}>${o.label}</option>`,
        )}
      </select>`,
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
                      st === "Update available" ? "update" : st === "Online" ? "online" : "";
                    const grpCell =
                      d.device_group_name ||
                      (d.kind === "ble_tag"
                        ? d.ble_category === "phone"
                          ? "Phone"
                          : "BLE Tag"
                        : d.device_group === "custom"
                          ? "Custom"
                          : "—");
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
                      <td>${grpCell}</td>
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
              : "No Managed Devices yet. Adopt discovered Latter Devices or add BLE Tags in Discovered."}
          </p>`,
    })}
  </section>`;
}
