/**
 * Managed Devices View (`select_device_prompt`, `D-041`, `D-048`, `D-061`, `D-066`):
 * - Sentence-case `store.t(...)` labels with `Inventory` card heading when filter is `"all"` (`R-8`).
 * - Typed `d.status_code` filtering, sorting, and status dot classes (`D-15`).
 * - Semantic `<a href="/latter/devices/<id>">` Device link in `.col-name` (`D-10`) + humanized `d.model_label` (`Q12`).
 * - Actionable 0-Device onboarding CTAs (`E-10`).
 */

import { renderCard, renderSortHeader } from "../components/controls.js";
import { html, live, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import type { DeviceStatusCode, SystemDeviceEntry } from "../types.js";
import { entityLabel } from "../utils/format.js";

function effectiveStatusCode(d: SystemDeviceEntry): DeviceStatusCode {
  if (d.status_code) return d.status_code;
  const lbl = String(d.status_label || "").trim().toLowerCase();
  if (lbl.includes("update")) return "update";
  if (lbl === "away") return "away";
  if (lbl === "scanning") return "scanning";
  if (lbl === "online" || d.is_online) return "online";
  return "offline";
}

function statusRankByCode(code: DeviceStatusCode): number {
  if (code === "update") return 1;
  if (code === "offline" || code === "away" || code === "scanning") return 2;
  return 3;
}

function localizedStatusLabel(store: StudioStore, d: SystemDeviceEntry, code: DeviceStatusCode): string {
  switch (code) {
    case "online":
      return store.t("status.online");
    case "update":
      return store.t("status.update");
    case "away":
      return store.t("status.away");
    case "scanning":
      return store.t("status.scanning");
    case "offline":
      return d.status_label && d.status_label.toLowerCase() === "sleeping"
        ? store.t("status.sleeping")
        : store.t("status.offline");
    default:
      return d.status_label || store.t("common.unknown");
  }
}

export function renderDevicesListView(store: StudioStore): TemplateResult {
  const allDevices: SystemDeviceEntry[] = store.state?.system_devices || [];
  const groups = store.state?.device_groups || [];
  const rawCat = store.deviceCategoryFilter || "all";

  const hasPhones = allDevices.some((d) => d.kind === "ble_tag" && d.ble_category === "phone");
  const hasBleTags = allDevices.some((d) => d.kind === "ble_tag" && d.ble_category !== "phone");
  const hasAssignedPeople = allDevices.some((d) => Boolean(d.assigned_person));
  const hasUpdates = allDevices.some((d) => effectiveStatusCode(d) === "update");
  const hasCustomGroup = allDevices.some(
    (d) => d.kind !== "ble_tag" && (!d.device_group || d.device_group === "custom"),
  );

  const defaultCategory = { id: "all", label: store.t("devices.all") };
  const baseCategories: Array<{ id: string; label: string }> = [
    defaultCategory,
    { id: "online", label: store.t("devices.online") },
    { id: "roaming", label: store.t("devices.roaming") },
    { id: "stationary", label: store.t("devices.stationary") },
  ];
  if (rawCat === "native") {
    baseCategories.push({ id: "native", label: store.t("devices.latter_displays") });
  }
  if (rawCat === "ble_tracked") {
    baseCategories.push({ id: "ble_tracked", label: store.t("devices.ble_tracked") });
  }
  if (hasPhones || rawCat === "phone") {
    baseCategories.push({ id: "phone", label: store.t("devices.phones") });
  }
  if (hasBleTags || rawCat === "ble_tag") {
    baseCategories.push({ id: "ble_tag", label: store.t("devices.ble_tags") });
  }
  if (hasAssignedPeople || rawCat === "assigned_person") {
    baseCategories.push({ id: "assigned_person", label: store.t("devices.assigned_person") });
  }
  if (hasUpdates || rawCat === "updates") {
    baseCategories.push({ id: "updates", label: store.t("devices.updates_available") });
  }
  for (const g of groups) {
    if (!g || !g.id || g.id === "custom") continue;
    const grpFilterId = `group:${g.id}`;
    const hasMembers = allDevices.some((d) => d.kind !== "ble_tag" && d.device_group === g.id);
    if (hasMembers || rawCat === grpFilterId) {
      baseCategories.push({
        id: grpFilterId,
        label: store.t("devices.group_prefix", { name: entityLabel(g.name) }),
      });
    }
  }
  if (hasCustomGroup || rawCat === "group:custom") {
    baseCategories.push({
      id: "group:custom",
      label: store.t("devices.group_prefix", { name: store.t("common.custom") }),
    });
  }

  const activeCategory = baseCategories.find((o) => o.id === rawCat) ?? defaultCategory;
  const cat = activeCategory.id;
  const cardHeadingTitle =
    cat === "all" ? store.t("devices.inventory_heading") : activeCategory.label;

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
    if (cat === "updates") return effectiveStatusCode(d) === "update";
    if (cat === "group:custom") {
      return !isBleTag && (!d.device_group || d.device_group === "custom");
    }
    if (cat.startsWith("group:")) return !isBleTag && d.device_group === cat.slice(6);
    return true;
  });

  filtered.sort((a, b) => {
    let cmp = 0;
    if (store.deviceSortField === "status") {
      cmp = statusRankByCode(effectiveStatusCode(a)) - statusRankByCode(effectiveStatusCode(b));
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
      title: cardHeadingTitle,
      headerActions: allDevices.length
        ? html`<select
            id="device-category-filter"
            aria-label=${store.t("devices.filter_aria")}
            .value=${live(cat)}
            @change=${(ev: Event) => {
              store.deviceCategoryFilter = (ev.currentTarget as HTMLSelectElement).value || "all";
              store.host.requestUpdate();
            }}
          >
            ${baseCategories.map(
              (o) => html`<option value=${o.id} .selected=${live(o.id === cat)}>${o.label}</option>`,
            )}
          </select>`
        : nothing,
      footerActions: !allDevices.length
        ? html`<button
              type="button"
              @click=${() => store.openDiscoveredDevices()}
              class="btn btn-primary"
            >
              ${store.t("devices.open_discovered")}
            </button>
            <button
              type="button"
              @click=${() => store.tools.openAddBleModal()}
              class="btn btn-secondary"
            >
              ${store.t("action.add_ble_tag")}
            </button>
            <button
              type="button"
              @click=${() => store.openSystemSection("area_tracking")}
              class="btn btn-text"
            >
              ${store.t("devices.open_area_presence")}
            </button>`
        : nothing,
      body: filtered.length
        ? html`<div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  ${renderSortHeader(store, "title", store.t("devices.col_device"))}
                  ${renderSortHeader(store, "model", store.t("devices.col_model"))}
                  ${renderSortHeader(store, "area", store.t("devices.col_area"))}
                  ${renderSortHeader(store, "group", store.t("devices.col_group"))}
                  ${renderSortHeader(store, "status", store.t("devices.col_status"))}
                  <th><span class="sort-btn" aria-hidden="true"></span></th>
                </tr>
              </thead>
              <tbody>
                ${repeat(
                  filtered,
                  (d) => d.subentry_id,
                  (d) => {
                    const code = effectiveStatusCode(d);
                    const st = localizedStatusLabel(store, d, code);
                    const dotCls = code === "update" ? "update" : code === "online" ? "online" : "";
                    const grpCell =
                      d.kind === "ble_tag"
                        ? d.ble_category === "phone"
                          ? store.t("devices.phones")
                          : store.t("devices.ble_tags")
                        : d.device_group === "custom"
                          ? store.t("common.custom")
                          : d.device_group_name || store.t("common.unknown");
                    const href = `/latter/devices/${encodeURIComponent(d.subentry_id)}`;
                    const onLinkClick = (ev: MouseEvent): void => {
                      if (
                        ev.defaultPrevented ||
                        ev.button !== 0 ||
                        ev.metaKey ||
                        ev.ctrlKey ||
                        ev.shiftKey ||
                        ev.altKey
                      ) {
                        return;
                      }
                      ev.preventDefault();
                      ev.stopPropagation();
                      void store.switchSystemDevice(d.subentry_id);
                    };
                    const onLinkKeydown = (ev: KeyboardEvent): void => {
                      if (
                        ev.key === " " &&
                        !ev.metaKey &&
                        !ev.ctrlKey &&
                        !ev.shiftKey &&
                        !ev.altKey
                      ) {
                        ev.preventDefault();
                        void store.switchSystemDevice(d.subentry_id);
                      }
                    };
                    const onRowClick = (ev: MouseEvent): void => {
                      if (ev.defaultPrevented || ev.button !== 0 || ev.shiftKey || ev.altKey) {
                        return;
                      }
                      const target = ev.target as Element | null;
                      if (target?.closest?.("a, button, input, select")) return;
                      if (
                        typeof globalThis.getSelection === "function" &&
                        String(globalThis.getSelection()?.toString() || "").trim() !== ""
                      ) {
                        return;
                      }
                      if (ev.metaKey || ev.ctrlKey) {
                        globalThis.open?.(href, "_blank", "noopener,noreferrer");
                        return;
                      }
                      void store.switchSystemDevice(d.subentry_id);
                    };
                    return html`<tr @click=${onRowClick}>
                      <td class="col-name">
                        <a href=${href} @click=${onLinkClick} @keydown=${onLinkKeydown}>${d.title}</a>
                      </td>
                      <td>${d.model_label || store.t("common.unknown")}</td>
                      <td>${d.area_label || store.t("common.unknown")}</td>
                      <td>${grpCell}</td>
                      <td><span class="status-dot ${dotCls}" aria-hidden="true"></span>${st}</td>
                      <td class="col-open" aria-hidden="true">›</td>
                    </tr>`;
                  },
                )}
              </tbody>
            </table>
          </div>`
        : allDevices.length
          ? html`<p class="empty-state">${store.t("devices.empty_filtered")}</p>`
          : html`<div class="stack">
              <strong>${store.t("devices.empty_zero_title")}</strong>
              <p class="empty-state">${store.t("devices.empty_zero_body")}</p>
            </div>`,
    })}
  </section>`;
}
