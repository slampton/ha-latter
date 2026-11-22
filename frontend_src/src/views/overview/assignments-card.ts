/**
 * Device Overview — Assignments Card (`views/overview/assignments-card.ts`, `D-050`, `D-064`).
 */

import {
  renderCard,
  renderSelectRow,
  renderSettingsRow,
} from "../../components/controls.js";
import { html, live, nothing, type TemplateResult } from "../../lib/lit.js";
import type { StudioStore } from "../../state/store.js";
import type { SystemDeviceEntry } from "../../types.js";

export function renderOverviewAssignmentsCard(
  store: StudioStore,
  opts: {
    curDevEntry: SystemDeviceEntry | undefined;
    isBleOnly: boolean;
  },
): TemplateResult {
  const { curDevEntry, isBleOnly } = opts;
  const data = store.state;
  const cfg = data?.config || {};
  const caps = data?.capabilities || {};

  const effBleCat = String(cfg.effective_ble_category || curDevEntry?.ble_category || "ble_tag");
  const rawBleCat = String(cfg.ble_category || "auto").trim().toLowerCase();
  const curBleCat = rawBleCat === "phone" || rawBleCat === "ble_tag" ? rawBleCat : "auto";

  const groups = data?.device_groups || [];
  const rawGroupId = String(cfg.device_group || "custom").trim() || "custom";
  const curGroupId =
    rawGroupId === "custom" || groups.some((g) => g.id === rawGroupId) ? rawGroupId : "custom";

  const remoteGroups = data?.system_config?.remote_groups || [];
  const curRemoteMode =
    String(cfg.device_remote_group || curDevEntry?.device_remote_group || "area_auto").trim() ||
    "area_auto";
  let remoteSummary = store.t("dev_overview.remote_follow_area");
  if (curRemoteMode === "all") {
    remoteSummary = store.t("dev_overview.remote_all_system");
  } else if (curRemoteMode.startsWith("group:")) {
    const gid = curRemoteMode.slice(6);
    remoteSummary = remoteGroups.find((g) => g.id === gid)?.name || gid;
  }

  return renderCard({
    id: "card-device-assignments",
    title: store.t("card.assignments"),
    contentClass: "settings-list",
    body: html`${!isBleOnly
        ? renderSettingsRow({
            label: store.t("dev_overview.device_group_label"),
            forId: "cfg-device_group",
            description:
              curGroupId === "custom"
                ? store.t("dev_overview.device_group_custom_desc")
                : store.t("dev_overview.device_group_preset_desc"),
            control: html`<select
                id="cfg-device_group"
                .value=${live(curGroupId)}
                @change=${(ev: Event) =>
                  store.entity.stageDeviceSetting(
                    "device_group",
                    (ev.currentTarget as HTMLSelectElement).value,
                    "cfg-device_group",
                  )}
              >
                <option value="custom" .selected=${live(curGroupId === "custom")}>
                  ${store.t("common.custom")}
                </option>
                ${groups.map(
                  (g) =>
                    html`<option value=${g.id} .selected=${live(g.id === curGroupId)}>
                      ${g.name}
                    </option>`,
                )}
              </select>
              ${curGroupId === "custom"
                ? html`<button
                    type="button"
                    id="btn-save-custom-group"
                    @click=${() => store.groups.openSaveGroupModal()}
                    class="btn btn-secondary btn-compact"
                  >
                    ${store.t("action.save_custom_group")}
                  </button>`
                : nothing}
              <button
                type="button"
                id="btn-manage-groups"
                @click=${() => store.openManageGroups(curGroupId)}
                class="btn btn-text btn-compact"
              >
                ${store.t("action.manage_groups")}
              </button>`,
          })
        : renderSettingsRow({
            label: store.t("dev_overview.device_category_label"),
            forId: "cfg-ble_category",
            description: store.t("dev_overview.device_category_desc"),
            control: html`<select
              id="cfg-ble_category"
              .value=${live(curBleCat)}
              @change=${(ev: Event) =>
                store.entity.stageDeviceSetting(
                  "ble_category",
                  (ev.currentTarget as HTMLSelectElement).value,
                  "cfg-ble_category",
                )}
            >
              <option value="auto" .selected=${live(curBleCat === "auto")}>
                ${store.t("dev_overview.auto_category_option", {
                  category:
                    effBleCat === "phone"
                      ? store.t("status.phone")
                      : store.t("status.ble_tag"),
                })}
              </option>
              <option value="phone" .selected=${live(curBleCat === "phone")}>
                ${store.t("status.phone")}
              </option>
              <option value="ble_tag" .selected=${live(curBleCat === "ble_tag")}>
                ${store.t("status.ble_tag")}
              </option>
            </select>`,
          })}
      ${renderSelectRow({
        id: "cfg-assigned_person",
        label: store.t("dev_overview.assigned_person_label"),
        description: store.t("dev_overview.assigned_person_desc"),
        value: cfg.assigned_person,
        choices: data?.catalog?.persons,
        emptyOptionLabel: store.t("dev_overview.unassigned_option"),
        onChange: (val) =>
          store.entity.stageDeviceSetting("assigned_person", val, "cfg-assigned_person"),
      })}
      ${!isBleOnly && caps.has_display
        ? renderSettingsRow({
            label: store.t("dev_overview.remote_group_label"),
            description: store.t("dev_overview.remote_group_desc"),
            control: html`<span class="chip">${remoteSummary}</span>
              <button
                type="button"
                id="btn-configure-remote-group"
                @click=${() => store.entity.openAppConfigModal("remote")}
                class="btn btn-text btn-compact"
              >
                ${store.t("action.configure")}
              </button>`,
          })
        : nothing}`,
  });
}
