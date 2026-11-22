/**
 * System Media & Remotes View (`remotes`, `D-026`, `D-042`, `D-064`):
 * - Remote controls with pointer/keyboard reordering (`reorderStringListRows("remotes_list", ...)`)
 * - Speaker volume overrides & Area-bound Remote control groups (`focusSafe` group names)
 */

import {
  renderCard,
  renderEntitySlotList,
  renderSelectOptions,
  renderTrashIconButton,
} from "../components/controls.js";
import { focusSafe, html, live, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";

export function renderSystemRemotesView(store: StudioStore): TemplateResult {
  const data = store.state;
  const sc = data?.system_config;
  const cat = data?.catalog || {};
  const remotes = sc?.remotes_list || [];
  const volOverrides = sc?.volume_overrides || [];
  const remoteGroups = sc?.remote_groups || [];
  const areas = cat.areas || [];

  const speakerChoices = cat.ma_speakers || [];
  const targetChoices = cat.volume_targets || cat.remotes || [];
  const inventoryIds = remotes.filter(Boolean);

  const friendlyRemoteLabel = (entId: string): string => {
    const found = (cat.remotes || []).find((r) => r.id === entId);
    return found ? (found.name.split(" (")[0] || entId) : entId;
  };

  return html`<section id="view-remotes">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: store.t("card.remote_controls"),
          subtitle: store.t("remotes.controls_subtitle"),
          headerActions: html`<button
            type="button"
            @click=${() => store.entity.addStringListRow("remotes_list", "", 10)}
            class="btn btn-secondary btn-compact"
          >
            ${store.t("remotes.add_remote")}
          </button>`,
          body: renderEntitySlotList({
            id: "remotes-list",
            items: remotes,
            choices: cat.remotes,
            emptyOptionLabel: store.t("remotes.choose_remote"),
            emptyStateText: store.t("remotes.empty_remotes"),
            selectAriaLabel: store.t("remotes.remote_aria"),
            removeAriaLabel: store.t("remotes.remove_remote"),
            slotLabel: (idx) =>
              idx === 0
                ? store.t("remotes.slot_primary")
                : store.t("remotes.slot_n", { index: idx + 1 }),
            onReorder: (fromIdx, toIdx) =>
              store.entity.reorderStringListRows("remotes_list", fromIdx, toIdx),
            onChange: (idx, val) => store.entity.updateStringListRow("remotes_list", idx, val),
            onRemove: (idx) => store.entity.removeStringListRow("remotes_list", idx),
          }),
        })}

        ${renderCard({
          id: "card-volume-overrides",
          title: store.t("card.volume_overrides"),
          subtitle: store.t("remotes.overrides_subtitle"),
          headerActions: html`<button
            type="button"
            @click=${() => store.entity.addVolumeOverrideRow()}
            class="btn btn-secondary btn-compact"
          >
            ${store.t("remotes.add_override")}
          </button>`,
          body: html`<div id="volume-overrides-list" class="stack">
            ${volOverrides.length
              ? volOverrides.map(
                  (vo, idx) => html`<div class="list-row">
                    <div class="list-row-main">
                      <div class="stacked-field">
                        <span class="field-label">${store.t("remotes.when_playing_on")}</span>
                        <select
                          aria-label=${store.t("remotes.speaker_aria")}
                          .value=${live(vo.speaker)}
                          @change=${(ev: Event) =>
                            store.entity.updateVolumeOverrideRow(
                              idx,
                              "speaker",
                              (ev.currentTarget as HTMLSelectElement).value,
                            )}
                        >
                          ${renderSelectOptions(
                            speakerChoices,
                            vo.speaker,
                            store.t("remotes.choose_speaker"),
                          )}
                        </select>
                      </div>
                      <div class="stacked-field">
                        <span class="field-label">${store.t("remotes.change_volume_on")}</span>
                        <select
                          aria-label=${store.t("remotes.volume_target_aria")}
                          .value=${live(vo.target)}
                          @change=${(ev: Event) =>
                            store.entity.updateVolumeOverrideRow(
                              idx,
                              "target",
                              (ev.currentTarget as HTMLSelectElement).value,
                            )}
                        >
                          ${renderSelectOptions(
                            targetChoices,
                            vo.target,
                            store.t("remotes.choose_volume_target"),
                          )}
                        </select>
                      </div>
                    </div>
                    ${renderTrashIconButton(store.t("remotes.remove_override_aria"), () =>
                      store.entity.removeVolumeOverrideRow(idx),
                    )}
                  </div>`,
                )
              : html`<p class="empty-state">${store.t("remotes.empty_overrides")}</p>`}
          </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          id: "card-remote-groups",
          handoffActive: store.isHandoffTarget("card-remote-groups"),
          title: store.t("card.remote_groups"),
          subtitle: store.t("remotes.groups_subtitle"),
          headerActions: html`<button
            type="button"
            @click=${() => store.entity.addRemoteGroupRow()}
            class="btn btn-secondary btn-compact"
          >
            ${store.t("remotes.add_group")}
          </button>`,
          body: html`<div id="remote-groups-list" class="stack">
            ${remoteGroups.length
              ? remoteGroups.map((grp, gIdx) => {
                  const selectedRems = Array.isArray(grp.remotes) ? grp.remotes : [];
                  const pool = selectedRems
                    .filter((id) => inventoryIds.includes(id))
                    .concat(inventoryIds.filter((id) => !selectedRems.includes(id)));
                  const nameId = `rg-name-${grp.id}`;
                  const areaId = `rg-area-${grp.id}`;

                  return html`<div class="list-block">
                    <div class="list-row-head">
                      <div class="list-row-main">
                        <div class="stacked-field">
                          <label for=${nameId}>${store.t("remotes.group_name")}</label>
                          <input
                            type="text"
                            id=${nameId}
                            placeholder=${store.t("remotes.group_name_placeholder")}
                            .value=${focusSafe(grp.name || "")}
                            @change=${(ev: Event) =>
                              store.entity.updateRemoteGroupField(
                                grp.id,
                                "name",
                                (ev.currentTarget as HTMLInputElement).value,
                              )}
                          />
                        </div>
                        <div class="stacked-field">
                          <label for=${areaId}>${store.t("remotes.loads_in_area")}</label>
                          <select
                            id=${areaId}
                            aria-label=${store.t("remotes.area_aria")}
                            .value=${live(grp.area_id || "")}
                            @change=${(ev: Event) =>
                              store.entity.updateRemoteGroupField(
                                grp.id,
                                "area_id",
                                (ev.currentTarget as HTMLSelectElement).value,
                              )}
                          >
                            <option value="" .selected=${live(!(grp.area_id || ""))}>
                              ${store.t("remotes.no_area_option")}
                            </option>
                            ${areas.map(
                              (a) =>
                                html`<option value=${a.id} .selected=${live(a.id === grp.area_id)}>
                                  ${a.name}
                                </option>`,
                            )}
                          </select>
                        </div>
                      </div>
                      ${renderTrashIconButton(
                        store.t("remotes.delete_group_aria", { name: grp.name || grp.id }),
                        () => store.entity.removeRemoteGroupRow(grp.id),
                      )}
                    </div>
                    <div class="stacked-field">
                      <span id=${`rg-remotes-${gIdx}`} class="field-label">
                        ${store.t("remotes.group_remotes_label")}
                      </span>
                      <div role="group" aria-labelledby=${`rg-remotes-${gIdx}`} class="pill-list">
                        ${pool.length
                          ? pool.map((entId) => {
                              const pos = selectedRems.indexOf(entId);
                              const isEn = pos >= 0;
                              const lbl = friendlyRemoteLabel(entId);
                              const text = isEn
                                ? pos === 0
                                  ? store.t("remotes.primary_badge", { name: lbl })
                                  : store.t("remotes.numbered_badge", {
                                      index: pos + 1,
                                      name: lbl,
                                    })
                                : store.t("remotes.add_badge", { name: lbl });
                              return html`<span class="pill ${isEn ? "enabled" : ""}">
                                <button
                                  type="button"
                                  aria-pressed=${isEn ? "true" : "false"}
                                  @click=${() => store.entity.toggleRemoteInGroup(grp.id, entId)}
                                  class="pill-toggle"
                                >
                                  ${text}
                                </button>
                              </span>`;
                            })
                          : html`<span class="help-text">
                              ${store.t("remotes.add_remotes_first")}
                            </span>`}
                      </div>
                    </div>
                  </div>`;
                })
              : html`<p class="empty-state">${store.t("remotes.empty_groups")}</p>`}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}
