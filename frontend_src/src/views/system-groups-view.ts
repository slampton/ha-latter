/**
 * System Device Groups & Staged Batch Controls View (`system_sync`, `D-048`, `D-050`, `D-055`, `D-064`).
 * - Column 1: Non-stuttering `Group presets & custom groups` card (`R-8`) with on-demand creation form,
 *   enclosed group containers (`requestDeleteDeviceGroup` confirmation), and read-only
 *   `Custom (individual settings)` summary container (`Q6`).
 * - Column 2: Staged `Batch controls` (`batch-controls.ts`) behind **Apply to N Devices** & **Reset**.
 */

import { renderCard, renderTrashIconButton } from "../components/controls.js";
import { DEFAULT_DEVICE_GROUP_IDS } from "../constants.js";
import { focusSafe, html, nothing, repeat, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";
import { fmtNumber } from "../utils/format.js";
import { renderBatchControlsCard } from "./groups/batch-controls.js";
import { renderGroupBaselineDrawer } from "./groups/group-baseline-drawer.js";

export function renderSystemGroupsView(store: StudioStore): TemplateResult {
  const data = store.state;
  const allDevices = data?.system_devices || [];
  const latterDevices = allDevices.filter((d) => d.kind !== "ble_tag");
  const groups = data?.device_groups || [];
  const systemControls = data?.system_controls || [];
  const customMembers = latterDevices.filter(
    (d) => !d.device_group || d.device_group === "custom",
  );

  return html`<section id="view-system_sync">
    <div class="columns">
      <div class="column">
        ${renderCard({
          id: "card-device-groups",
          title: store.t("groups.card_title"),
          subtitle: store.t("groups.card_subtitle"),
          headerActions: !store.newGroupFormOpen
            ? html`<button
                type="button"
                id="btn-open-create-group"
                @click=${() => store.groups.toggleNewGroupForm(true)}
                class="btn btn-secondary btn-compact"
              >
                ${store.t("groups.create_group")}
              </button>`
            : nothing,
          contentClass: "stack",
          body: html`${store.newGroupFormOpen
              ? html`<div id="create-group-form" class="list-block">
                  <div class="list-row-main">
                    <div class="stacked-field">
                      <label for="new-group-name">${store.t("groups.group_name")}</label>
                      <input
                        type="text"
                        id="new-group-name"
                        placeholder=${store.t("groups.group_name_placeholder")}
                        .value=${focusSafe(store.newGroupName)}
                        @input=${(ev: Event) => {
                          store.newGroupName = (ev.currentTarget as HTMLInputElement).value;
                        }}
                      />
                    </div>
                    <div class="stacked-field">
                      <label for="new-group-desc">
                        ${store.t("groups.description_optional")}
                      </label>
                      <input
                        type="text"
                        id="new-group-desc"
                        placeholder=${store.t("groups.description_placeholder")}
                        .value=${focusSafe(store.newGroupDesc)}
                        @input=${(ev: Event) => {
                          store.newGroupDesc = (ev.currentTarget as HTMLInputElement).value;
                        }}
                      />
                    </div>
                  </div>
                  <div class="pill-list">
                    <span class="pill ${store.newGroupIncludeDisplay ? "enabled" : ""}">
                      <button
                        type="button"
                        aria-pressed=${store.newGroupIncludeDisplay ? "true" : "false"}
                        @click=${() => {
                          store.newGroupIncludeDisplay = !store.newGroupIncludeDisplay;
                          store.host.requestUpdate();
                        }}
                        class="pill-toggle"
                      >
                        ${store.t("groups.include_display")}
                      </button>
                    </span>
                    <span class="pill ${store.newGroupIncludeInterface ? "enabled" : ""}">
                      <button
                        type="button"
                        aria-pressed=${store.newGroupIncludeInterface ? "true" : "false"}
                        @click=${() => {
                          store.newGroupIncludeInterface = !store.newGroupIncludeInterface;
                          store.host.requestUpdate();
                        }}
                        class="pill-toggle"
                      >
                        ${store.t("groups.include_interface")}
                      </button>
                    </span>
                  </div>
                  <div class="input-action-row">
                    <select
                      id="new-group-source"
                      aria-label=${store.t("groups.copy_from_aria")}
                      .value=${store.newGroupSourceSubentryId}
                      @change=${(ev: Event) => {
                        store.newGroupSourceSubentryId = (
                          ev.currentTarget as HTMLSelectElement
                        ).value;
                      }}
                    >
                      <option value="" ?selected=${!store.newGroupSourceSubentryId}>
                        ${store.t("groups.start_from_defaults")}
                      </option>
                      ${latterDevices.map(
                        (d) =>
                          html`<option
                            value=${d.subentry_id}
                            ?selected=${d.subentry_id === store.newGroupSourceSubentryId}
                          >
                            ${store.t("groups.copy_from_prefix", { title: d.title })}
                          </option>`,
                      )}
                    </select>
                    <button
                      type="button"
                      id="btn-cancel-create-group"
                      @click=${() => store.groups.toggleNewGroupForm(false)}
                      class="btn btn-secondary"
                    >
                      ${store.t("action.cancel")}
                    </button>
                    <button
                      type="button"
                      id="btn-create-device-group"
                      @click=${() => void store.groups.createDeviceGroup()}
                      class="btn btn-primary"
                    >
                      ${store.t("groups.create_group")}
                    </button>
                  </div>
                </div>`
              : nothing}

            <div id="device-groups-list" class="stack">
              ${groups.length
                ? repeat(
                    groups,
                    (g) => g.id,
                    (g) => {
                      const members = latterDevices.filter((d) => d.device_group === g.id);
                      const isDefault =
                        DEFAULT_DEVICE_GROUP_IDS.has(g.id) || Boolean(g.builtin);
                      const metaParts = [
                        g.description || "",
                        members.length
                          ? store.t("groups.devices_list_meta", {
                              names: members.map((m) => m.title).join(", "),
                            })
                          : store.t("groups.no_devices_assigned"),
                      ].filter(Boolean);

                      const groupBoxId = `group-box-${g.id}`;
                      const isGroupHandoff = store.isHandoffTarget(groupBoxId);

                      return html`<div
                        id=${groupBoxId}
                        class="area-presence-box${isGroupHandoff ? " handoff-active" : ""}"
                      >
                        <div class="area-box-head">
                          <div class="area-box-heading">
                            <h4 class="area-box-title">${g.name}</h4>
                            <span class="chip ${members.length ? "chip-primary" : ""}">
                              ${members.length === 1
                                ? store.t("groups.members_one")
                                : store.t("groups.members_many", {
                                    count: fmtNumber(members.length, store.hass, 0),
                                  })}
                            </span>
                            ${g.include_display
                              ? html`<span class="chip">
                                  ${store.t("groups.scope_display_chip")}
                                </span>`
                              : nothing}
                            ${g.include_interface
                              ? html`<span class="chip">
                                  ${store.t("groups.scope_interface_chip")}
                                </span>`
                              : nothing}
                          </div>
                          <div class="area-box-actions">
                            ${members.length
                              ? html`<button
                                  type="button"
                                  @click=${() => store.openDevicesWithCategory(`group:${g.id}`)}
                                  class="btn btn-text btn-compact"
                                >
                                  ${store.t("groups.view_devices")}
                                </button>`
                              : nothing}
                            ${!isDefault
                              ? renderTrashIconButton(
                                  store.t("groups.delete_group_aria", { name: g.name }),
                                  () =>
                                    store.groups.requestDeleteDeviceGroup(
                                      g.id,
                                      g.name,
                                      members.length,
                                    ),
                                )
                              : nothing}
                          </div>
                        </div>

                        <div class="area-box-meta">${metaParts.join(" • ")}</div>

                        ${renderGroupBaselineDrawer(store, g, members, latterDevices)}
                      </div>`;
                    },
                  )
                : html`<p class="empty-state">${store.t("groups.empty_groups")}</p>`}

              <div id="group-box-custom" class="area-presence-box">
                <div class="area-box-head">
                  <div class="area-box-heading">
                    <h4 class="area-box-title">${store.t("groups.custom_summary_title")}</h4>
                    <span class="chip ${customMembers.length ? "chip-primary" : ""}">
                      ${customMembers.length === 1
                        ? store.t("groups.members_one")
                        : store.t("groups.members_many", {
                            count: fmtNumber(customMembers.length, store.hass, 0),
                          })}
                    </span>
                  </div>
                  <div class="area-box-actions">
                    ${customMembers.length > 0
                      ? html`<button
                          type="button"
                          id="btn-view-custom-devices"
                          @click=${() => store.openDevicesWithCategory("group:custom")}
                          class="btn btn-text btn-compact"
                        >
                          ${store.t("groups.view_devices")}
                        </button>`
                      : nothing}
                  </div>
                </div>
                <div class="area-box-meta">${store.t("groups.custom_summary_desc")}</div>
              </div>
            </div>`,
        })}
      </div>

      <div class="column">
        ${renderBatchControlsCard(store, groups, latterDevices, systemControls)}
      </div>
    </div>
  </section>`;
}
