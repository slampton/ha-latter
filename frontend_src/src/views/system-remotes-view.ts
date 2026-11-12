/**
 * System Media & Remotes View (`remotes`): Remote Controls, Volume Overrides, Remote Groups & Device Assignment Status.
 */

import {
  renderCard,
  renderEntitySlotList,
  renderSelectOptions,
  renderSettingsRow,
  renderTrashIconButton,
} from "../components/controls.js";
import { html, type TemplateResult } from "../lib/lit.js";
import type { StudioStore } from "../state/store.js";

export function renderSystemRemotesView(store: StudioStore): TemplateResult {
  const data = store.state;
  const sc = data?.system_config;
  const cat = data?.catalog || {};
  const remotes = sc?.remotes_list || [];
  const volOverrides = sc?.volume_overrides || [];
  const remoteGroups = sc?.remote_groups || [];
  const areas = cat.areas || [];
  const screenDevs = (data?.system_devices || []).filter(
    (d) => d.kind !== "ble_tag" && d.has_display,
  );

  const speakerChoices = cat.ma_speakers || [];
  const targetChoices = cat.volume_targets || cat.remotes || [];
  const inventoryIds = remotes.filter(Boolean);

  const friendlyRemoteLabel = (entId: string): string => {
    const found = (cat.remotes || []).find((r) => r.id === entId);
    return found ? found.name.split(" (")[0] : entId;
  };

  const remoteAssignmentChipLabel = (rawMode: string): string => {
    const mode = String(rawMode || "area_auto").trim() || "area_auto";
    if (mode === "all") return "All System remotes";
    if (mode.startsWith("group:")) {
      const grpId = mode.slice(6);
      const matched = remoteGroups.find((g) => g.id === grpId);
      return matched ? `Group: ${matched.name}` : `Missing group (${grpId})`;
    }
    return "Follows active Area";
  };

  return html`<section id="view-remotes">
    <div class="columns">
      <div class="column">
        ${renderCard({
          title: "Remote Controls",
          subtitle: "Up to 10 TV, streamer, or receiver entities controlled from the Remote screen.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addStringListRow("remotes_list", "", 10)}
            class="btn btn-secondary btn-compact"
          >
            Add Remote
          </button>`,
          body: renderEntitySlotList({
            id: "remotes-list",
            items: remotes,
            choices: cat.remotes,
            emptyOptionLabel: "— Choose a remote or media player —",
            emptyStateText: "No remote controls configured yet.",
            selectAriaLabel: "Remote or media player",
            removeAriaLabel: "Remove remote",
            slotLabel: (idx) => (idx === 0 ? "Slot 1 (Primary Power Target)" : `Slot ${idx + 1}`),
            onChange: (idx, val) => store.updateStringListRow("remotes_list", idx, val),
            onRemove: (idx) => store.removeStringListRow("remotes_list", idx),
          }),
        })}

        ${renderCard({
          id: "card-volume-overrides",
          title: "Speaker Volume Overrides",
          subtitle: "Redirects volume buttons when audio plays through an external AVR or soundbar.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addVolumeOverrideRow()}
            class="btn btn-secondary btn-compact"
          >
            Add Override
          </button>`,
          body: html`<div id="volume-overrides-list" class="stack">
            ${volOverrides.length
              ? volOverrides.map(
                  (vo, idx) => html`<div class="list-row">
                    <div class="list-row-main">
                      <div class="stacked-field">
                        <span class="field-label">When Audio Plays On</span>
                        <select
                          aria-label="Speaker"
                          .value=${vo.speaker}
                          @change=${(ev: Event) =>
                            store.updateVolumeOverrideRow(
                              idx,
                              "speaker",
                              (ev.currentTarget as HTMLSelectElement).value,
                            )}
                        >
                          ${renderSelectOptions(speakerChoices, vo.speaker, "— Choose a speaker —")}
                        </select>
                      </div>
                      <div class="stacked-field">
                        <span class="field-label">Change the Volume On</span>
                        <select
                          aria-label="Volume target"
                          .value=${vo.target}
                          @change=${(ev: Event) =>
                            store.updateVolumeOverrideRow(
                              idx,
                              "target",
                              (ev.currentTarget as HTMLSelectElement).value,
                            )}
                        >
                          ${renderSelectOptions(
                            targetChoices,
                            vo.target,
                            "— Choose a volume target —",
                          )}
                        </select>
                      </div>
                    </div>
                    ${renderTrashIconButton("Remove volume override", () =>
                      store.removeVolumeOverrideRow(idx),
                    )}
                  </div>`,
                )
              : html`<p class="empty-state">No volume overrides configured.</p>`}
          </div>`,
        })}
      </div>

      <div class="column">
        ${renderCard({
          title: "Remote Control Groups",
          subtitle: "Bind sets of remotes to Home Assistant Areas or specific Devices.",
          headerActions: html`<button
            type="button"
            @click=${() => store.addRemoteGroupRow()}
            class="btn btn-secondary btn-compact"
          >
            Add Group
          </button>`,
          body: html`<div id="remote-groups-list" class="stack">
            ${remoteGroups.length
              ? remoteGroups.map((grp, gIdx) => {
                  const selectedRems = Array.isArray(grp.remotes) ? grp.remotes : [];
                  const pool = selectedRems
                    .filter((id) => inventoryIds.includes(id))
                    .concat(inventoryIds.filter((id) => !selectedRems.includes(id)));

                  return html`<div class="list-block">
                    <div class="list-row-head">
                      <div class="list-row-main">
                        <div class="stacked-field">
                          <label>Group Name</label>
                          <input
                            type="text"
                            aria-label="Group name"
                            placeholder="e.g. Living Area TV"
                            .value=${grp.name || ""}
                            @change=${(ev: Event) =>
                              store.updateRemoteGroupField(
                                grp.id,
                                "name",
                                (ev.currentTarget as HTMLInputElement).value,
                              )}
                          />
                        </div>
                        <div class="stacked-field">
                          <label>Loads in Area</label>
                          <select
                            aria-label="Area"
                            .value=${grp.area_id || ""}
                            @change=${(ev: Event) =>
                              store.updateRemoteGroupField(
                                grp.id,
                                "area_id",
                                (ev.currentTarget as HTMLSelectElement).value,
                              )}
                          >
                            <option value="">No Area (assign to Devices only)</option>
                            ${areas.map(
                              (a) =>
                                html`<option value=${a.id} ?selected=${a.id === grp.area_id}>
                                  ${a.name}
                                </option>`,
                            )}
                          </select>
                        </div>
                      </div>
                      ${renderTrashIconButton(`Delete remote group ${grp.name || ""}`, () =>
                        store.removeRemoteGroupRow(grp.id),
                      )}
                    </div>
                    <div class="stacked-field">
                      <span id=${`rg-remotes-${gIdx}`} class="field-label">Remote Controls</span>
                      <div role="group" aria-labelledby=${`rg-remotes-${gIdx}`} class="pill-list">
                        ${pool.length
                          ? pool.map((entId) => {
                              const pos = selectedRems.indexOf(entId);
                              const isEn = pos >= 0;
                              const badge = isEn
                                ? pos === 0
                                  ? "★ Primary: "
                                  : `#${pos + 1}: `
                                : "+ ";
                              return html`<button
                                type="button"
                                aria-pressed=${String(isEn)}
                                @click=${() => store.toggleRemoteInGroup(grp.id, entId)}
                                class="pill ${isEn ? "enabled" : ""}"
                              >
                                ${badge}${friendlyRemoteLabel(entId)}
                              </button>`;
                            })
                          : html`<span class="help-text">Add remote controls first.</span>`}
                      </div>
                    </div>
                  </div>`;
                })
              : html`<p class="empty-state">No remote groups yet.</p>`}
          </div>`,
        })}

        ${renderCard({
          title: "Device Assignments",
          subtitle: "Assigned on each Device's Interface page.",
          contentClass: "settings-list",
          body: html`<div id="device-remote-assignments-list" class="settings-list">
            ${screenDevs.length
              ? screenDevs.map((d) =>
                  renderSettingsRow({
                    label: d.title,
                    description: `Active Area: ${d.active_area_name || "—"}`,
                    control: html`<span class="chip">${remoteAssignmentChipLabel(d.device_remote_group)}</span>
                      <button
                        type="button"
                        aria-label=${`Configure remotes for ${d.title}`}
                        @click=${() => void store.switchSystemDevice(d.subentry_id, "interface")}
                        class="btn btn-secondary btn-compact"
                      >
                        Configure
                      </button>`,
                  }),
                )
              : html`<p class="empty-state">No Devices with a screen yet.</p>`}
          </div>`,
        })}
      </div>
    </div>
  </section>`;
}
